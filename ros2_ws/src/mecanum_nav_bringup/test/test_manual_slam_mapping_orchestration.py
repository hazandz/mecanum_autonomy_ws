from pathlib import Path
import importlib.util

import pytest
import rclpy
import yaml
from launch import LaunchContext
from launch.substitutions import LaunchConfiguration
from launch.actions import DeclareLaunchArgument, RegisterEventHandler
from launch_ros.actions import LifecycleNode, Node
from lifecycle_msgs.msg import State, Transition

from mecanum_nav_bringup.manual_slam_orchestration import (
    BNO055_NODE_NAME, DEFAULT_IMU_TOPIC, Readiness,
    fresh_neutral_after_enable, joy_is_neutral,
    joy_sample_valid, missing_dependencies,
    run_shutdown_sequence, run_startup_sequence, runtime_missing_dependencies,
    startup_actions,
)
from mecanum_nav_bringup.manual_slam_orchestrator import ManualSlamOrchestrator


ROOT = Path(__file__).resolve().parents[4]
LAUNCH = ROOT / "ros2_ws/src/mecanum_nav_bringup/launch/manual_slam_mapping.launch.py"
PARAMS = ROOT / (
    "ros2_ws/src/mecanum_nav_bringup/config/manual_slam/"
    "mapper_params_online_async.yaml"
)


class FakeOperations:
    def __init__(self, fail_at=None):
        self.calls = []
        self.fail_at = fail_at

    def _call(self, name):
        self.calls.append(name)
        if self.fail_at == name:
            raise TimeoutError(f"not ready: {name}")

    def ensure_slam_active(self): self._call("slam_active")
    def ensure_safety_active(self): self._call("safety_active")
    def wait_hardware_ready(self): self._call("hardware_ready")
    def wait_fresh_neutral_joy(self): self._call("neutral_joy")
    def rearm_safety(self): self._call("rearm")
    def wait_motion_permission(self): self._call("motion_permission")
    def enable_mapper(self): self._call("enable")
    def wait_post_enable_joy(self): self._call("post_enable_joy")
    def disarm_mapper(self): self._call("disarm")


class ImmediateFuture:
    def __init__(self, result): self._result = result
    def done(self): return True
    def exception(self): return None
    def result(self): return self._result


class LifecycleClient:
    def __init__(self, state=None, responses=None, on_transition=None):
        self.state = state
        self.responses = list(responses or [])
        self.on_transition = on_transition
        self.requests = []

    def call_async(self, request):
        self.requests.append(request)
        if self.state is not None:
            response = type("GetStateResponse", (), {})()
            response.current_state = type("CurrentState", (), {"id": self.state})()
            return ImmediateFuture(response)
        success = self.responses.pop(0) if self.responses else True
        if success and self.on_transition is not None:
            self.on_transition(request.transition.id)
        return ImmediateFuture(type("ChangeStateResponse", (), {"success": success})())

    def service_is_ready(self): return True


class LifecycleHarness:
    _startup_deadline = 60.0
    _service_timeout = 10.0

    def __init__(self, state, responses=None):
        self.get_client = LifecycleClient(state=state)
        def transition(transition_id):
            self.get_client.state = {
                Transition.TRANSITION_CONFIGURE: State.PRIMARY_STATE_INACTIVE,
                Transition.TRANSITION_ACTIVATE: State.PRIMARY_STATE_ACTIVE,
            }[transition_id]
        self.change_client = LifecycleClient(responses=responses, on_transition=transition)
        self._slam_get = self.get_client
        self._service_timeout = 10.0
        self.service_waits = []
        self.logs = []

    def _now(self): return 0.0
    def _step_deadline(self, timeout): return min(self._startup_deadline, timeout)
    def _service_ready(self, _client, label, _deadline): self.service_waits.append(label)
    def _wait_future(self, future, _label, _deadline): return future.result()
    def _spin(self, _duration=0.05): pass
    def get_logger(self): return self
    def info(self, message): self.logs.append(message)


def test_startup_orchestration_orders_lifecycle_health_neutral_rearm_and_enable():
    ops = FakeOperations()
    run_startup_sequence(ops)
    assert ops.calls == [
        "slam_active", "safety_active", "hardware_ready", "neutral_joy",
        "rearm", "motion_permission", "neutral_joy", "enable", "post_enable_joy",
    ]


def test_lifecycle_service_transitions_configure_then_activate_from_unconfigured():
    harness = LifecycleHarness(State.PRIMARY_STATE_UNCONFIGURED)
    ManualSlamOrchestrator._ensure_active(
        harness, "/slam_toolbox", harness.get_client, harness.change_client)
    assert [request.transition.id for request in harness.change_client.requests] == [
        Transition.TRANSITION_CONFIGURE, Transition.TRANSITION_ACTIVATE,
    ]
    assert harness.service_waits == [
        "/slam_toolbox/get_state", "/slam_toolbox/change_state",
    ]
    assert len(harness.get_client.requests) == 3


def test_lifecycle_service_activates_inactive_node_and_rejects_failed_transition():
    inactive = LifecycleHarness(State.PRIMARY_STATE_INACTIVE)
    ManualSlamOrchestrator._ensure_active(
        inactive, "/safety_lifecycle", inactive.get_client, inactive.change_client)
    assert [request.transition.id for request in inactive.change_client.requests] == [
        Transition.TRANSITION_ACTIVATE,
    ]
    rejected = LifecycleHarness(State.PRIMARY_STATE_UNCONFIGURED, responses=[False])
    with pytest.raises(RuntimeError, match="configure transition rejected"):
        ManualSlamOrchestrator._ensure_active(
            rejected, "/slam_toolbox", rejected.get_client, rejected.change_client)
    assert len(rejected.change_client.requests) == 1


@pytest.mark.parametrize("failure", ["slam_active", "safety_active", "hardware_ready"])
def test_dependency_timeout_stops_before_rearm_or_enable(failure):
    ops = FakeOperations(fail_at=failure)
    with pytest.raises(TimeoutError, match="not ready"):
        run_startup_sequence(ops)
    assert "rearm" not in ops.calls
    assert "enable" not in ops.calls


def test_non_neutral_joy_timeout_prevents_rearm_and_mapper_enable():
    ops = FakeOperations(fail_at="neutral_joy")
    with pytest.raises(TimeoutError, match="neutral_joy"):
        run_startup_sequence(ops)
    assert ops.calls[-1] == "neutral_joy"
    assert "rearm" not in ops.calls
    assert "enable" not in ops.calls


def test_rearm_or_motion_permission_failure_prevents_mapper_enable():
    for failure in ("rearm", "motion_permission"):
        ops = FakeOperations(fail_at=failure)
        with pytest.raises(TimeoutError, match=failure):
            run_startup_sequence(ops)
        assert "enable" not in ops.calls


def test_shutdown_requests_software_disarm():
    ops = FakeOperations()
    run_shutdown_sequence(ops)
    assert ops.calls == ["disarm"]


def test_readiness_requires_all_live_dependencies_and_neutral_joy():
    ready = Readiness(True, True, True, True, True, True, True)
    assert not missing_dependencies(ready)
    assert startup_actions(ready) == (
        "rearm", "wait_motion_permission", "enable_mapper", "wait_fresh_joy")
    assert missing_dependencies(Readiness(True, True, True, False, True, True, True)) == (
        "neutral /joy",
    )
    assert "healthy UART/session heartbeat" in missing_dependencies(
        Readiness(True, True, True, True, True, False, True))
    assert runtime_missing_dependencies(Readiness(
        True, True, True, False, True, True, True, True)) == ()
    assert "healthy UART/session heartbeat" in runtime_missing_dependencies(Readiness(
        True, True, True, False, True, False, True, True))
    assert DEFAULT_IMU_TOPIC in missing_dependencies(
        Readiness(True, False, True, True, True, True, True))
    assert DEFAULT_IMU_TOPIC in runtime_missing_dependencies(
        Readiness(True, False, True, False, True, True, True, True))
    wrong_imu_topic = "/wrong/imu_topic"
    assert missing_dependencies(
        Readiness(True, False, True, True, True, True, True),
        imu_topic=wrong_imu_topic) == (wrong_imu_topic,)
    assert runtime_missing_dependencies(
        Readiness(True, False, True, False, True, True, True, True),
        imu_topic=wrong_imu_topic) == (wrong_imu_topic,)


def test_joy_neutral_gate_rejects_invalid_shape_motion_and_pressed_buttons():
    centered = [-0.0039, 0.0039]
    released = [0, 0, 0, 0, 0, 0]
    assert joy_sample_valid(centered, released)
    assert joy_is_neutral(centered, released, 0.12)
    assert not joy_is_neutral([0.1, 0.1], released, 0.12)
    assert not joy_is_neutral([0.5, 0.0], released, 0.12)
    assert not joy_is_neutral(centered, [0, 0, 1, 0, 0, 0], 0.12)
    assert not joy_sample_valid([float("nan"), 0.0], released)
    assert not joy_sample_valid(centered, [0, 0])


def test_mapper_enable_requires_new_fresh_neutral_joy_after_service_call():
    fresh_neutral = Readiness(True, True, True, True, True, True, True, True)
    fresh_moving = Readiness(True, True, True, False, True, True, True, True)
    stale_neutral = Readiness(True, True, False, True, True, True, True, True)
    assert fresh_neutral_after_enable(fresh_neutral, 2.0, 1.0)
    assert not fresh_neutral_after_enable(fresh_neutral, 1.0, 1.0)
    assert not fresh_neutral_after_enable(fresh_moving, 2.0, 1.0)
    assert not fresh_neutral_after_enable(stale_neutral, 2.0, 1.0)


def test_mapping_launch_creates_async_lifecycle_and_coordinator_with_timeouts():
    spec = importlib.util.spec_from_file_location("manual_slam_mapping_launch", LAUNCH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    description = module.generate_launch_description()
    actions = description.entities
    lifecycle = next(action for action in actions if isinstance(action, LifecycleNode))
    orchestrator = next(action for action in actions
                        if isinstance(action, Node) and not isinstance(action, LifecycleNode))
    context = LaunchContext()
    declarations = {action.name: action.default_value[0].perform(context) for action in actions
                    if isinstance(action, DeclareLaunchArgument)}
    assert lifecycle.node_package == "slam_toolbox"
    assert lifecycle.node_executable == "async_slam_toolbox_node"
    assert lifecycle._Node__node_name == "slam_toolbox"
    assert orchestrator.node_package == "mecanum_nav_bringup"
    assert orchestrator.node_executable == "manual_slam_orchestrator"
    assert declarations["dependency_timeout_s"] == "30.0"
    assert declarations["service_timeout_s"] == "10.0"
    assert declarations["imu_topic"] == DEFAULT_IMU_TOPIC
    assert declarations["slam_state_check_period_s"] == "0.5"
    assert declarations["joy_max_age_s"] == "0.25"
    assert sum(isinstance(action, RegisterEventHandler) for action in actions) == 2
    assert PARAMS.is_file()
    slam_parameters = lifecycle._Node__parameters
    assert isinstance(slam_parameters[0]._ParameterFile__param_file[0], LaunchConfiguration)
    assert len(slam_parameters[1]) == 1
    (sim_time_key, sim_time_value), = slam_parameters[1].items()
    assert sim_time_key[0].text == "use_sim_time"
    assert sim_time_value is False
    coordinator_params = orchestrator._Node__parameters[0]
    context.launch_configurations["imu_topic"] = declarations["imu_topic"]
    imu_parameter = next(
        (key, value) for key, value in coordinator_params.items()
        if key[0].text == "imu_topic")
    assert imu_parameter[1][0].perform(context) == DEFAULT_IMU_TOPIC


def test_coordinator_imu_topic_matches_bno055_wrapper_pi_topic_contract():
    wrapper_path = ROOT / (
        "ros2_ws/src/mecanum_nav_bringup/launch/manual_slam_bno055_i2c.launch.py")
    wrapper_spec = importlib.util.spec_from_file_location("bno055_wrapper_test", wrapper_path)
    wrapper = importlib.util.module_from_spec(wrapper_spec)
    wrapper_spec.loader.exec_module(wrapper)
    wrapper_node = next(
        entity for entity in wrapper.generate_launch_description().entities
        if isinstance(entity, Node))
    assert wrapper_node._Node__node_name == BNO055_NODE_NAME == "bno055"
    assert wrapper_node._Node__remappings == []
    assert DEFAULT_IMU_TOPIC == "/bno055/imu"

    spec = importlib.util.spec_from_file_location("manual_slam_mapping_imu_topic", LAUNCH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    actions = module.generate_launch_description().entities
    declaration = next(action for action in actions
                       if isinstance(action, DeclareLaunchArgument)
                       and action.name == "imu_topic")
    assert declaration.default_value[0].perform(LaunchContext()) == DEFAULT_IMU_TOPIC
    hardware_launch = (ROOT / "ros2_ws/src/mecanum_nav_bringup/launch/manual_slam.launch.py")
    assert "manual_slam_bno055_i2c.launch.py" in hardware_launch.read_text()


@pytest.mark.parametrize("state_id", [
    State.PRIMARY_STATE_INACTIVE,
    State.PRIMARY_STATE_FINALIZED,
])
def test_monitor_rejects_slam_toolbox_leaving_active(state_id):
    active = LifecycleHarness(State.PRIMARY_STATE_ACTIVE)
    ManualSlamOrchestrator._assert_slam_toolbox_active(active)

    harness = LifecycleHarness(state_id)
    with pytest.raises(RuntimeError, match=r"/slam_toolbox lifecycle left ACTIVE"):
        ManualSlamOrchestrator._assert_slam_toolbox_active(harness)


def test_monitor_checks_slam_lifecycle_and_main_finally_requests_disarm(monkeypatch):
    from mecanum_nav_bringup import manual_slam_orchestrator as orchestrator_module

    monitor = LifecycleHarness(State.PRIMARY_STATE_FINALIZED)
    monitor._assert_slam_toolbox_active = lambda: (
        ManualSlamOrchestrator._assert_slam_toolbox_active(monitor))
    monkeypatch.setattr(orchestrator_module.rclpy, "ok", lambda: True)
    with pytest.raises(RuntimeError, match=r"/slam_toolbox lifecycle left ACTIVE"):
        ManualSlamOrchestrator.monitor_ready(monitor)

    class FailedMappingNode:
        def __init__(self):
            self.disarm_requests = 0
            self.destroyed = False

        def run_sequence(self): pass
        def monitor_ready(self):
            raise RuntimeError("/slam_toolbox lifecycle left ACTIVE (state id 4)")
        def disarm_mapper(self): self.disarm_requests += 1
        def destroy_node(self): self.destroyed = True
        def get_logger(self): return self
        def fatal(self, _message): pass

    failed_node = FailedMappingNode()
    monkeypatch.setattr(orchestrator_module.rclpy, "init", lambda **_kwargs: None)
    monkeypatch.setattr(orchestrator_module.rclpy, "shutdown", lambda: None)
    monkeypatch.setattr(orchestrator_module.signal, "signal", lambda *_args: None)
    monkeypatch.setattr(orchestrator_module, "ManualSlamOrchestrator", lambda: failed_node)
    with pytest.raises(SystemExit) as exit_info:
        orchestrator_module.main()
    assert exit_info.value.code == 2
    assert failed_node.disarm_requests == 1
    assert failed_node.destroyed


def test_manual_mapping_parameters_match_existing_async_mapping_configuration():
    original = ROOT / (
        "ros2_ws/src/ROBOT_URDF_final_description/config/"
        "mapper_params_online_async.yaml"
    )
    assert yaml.safe_load(PARAMS.read_text()) == yaml.safe_load(original.read_text())


def test_orchestrator_ros_jazzy_constructor_creates_only_gates_and_services():
    rclpy.init(args=None)
    node = None
    try:
        node = ManualSlamOrchestrator()
        assert node._slam_get.srv_name == "/slam_toolbox/get_state"
        assert node._safety_change.srv_name == "/safety_lifecycle/change_state"
        assert node._rearm.srv_name == "/mecanum/safety/rearm"
        assert node._enable.srv_name == "/manual_slam/enable"
        assert node._disarm.srv_name == "/manual_slam/disarm"
        assert node._last_joy is None
        assert node._imu_topic == DEFAULT_IMU_TOPIC
    finally:
        if node is not None:
            node.destroy_node()
        rclpy.shutdown()
