from types import SimpleNamespace
import importlib
import inspect
import math
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest
import rclpy.node

from mecanum_nav_rl_interfaces.msg import SafetyLifecycleState

from mecanum_base_bridge.bridge_node import (HEARTBEAT_TOPIC, LIFECYCLE_TOPIC,
    ODOMETRY_TOPIC, RESET_SERVICE, UartBridgeNode, lifecycle_identity,
    lifecycle_qos_profile)
from mecanum_base_bridge import bridge_node as bridge_node_module
from mecanum_base_bridge.hardware_config import HardwareConfigError


def test_existing_lifecycle_fields_map_without_synthetic_ready():
    msg = SafetyLifecycleState()
    msg.reset_epoch=0; msg.runtime_generation=4; msg.sequence=7
    msg.primary_state=SafetyLifecycleState.PRIMARY_ACTIVE
    msg.barrier_state=SafetyLifecycleState.BARRIER_NON_READY
    msg.motion_permitted=False
    identity = lifecycle_identity(msg, 10.0, 10.1)
    assert identity.reset_epoch == 0 and identity.runtime_generation == 4
    assert identity.fresh and not identity.ready
    msg.barrier_state=SafetyLifecycleState.BARRIER_READY; msg.motion_permitted=True
    assert lifecycle_identity(msg, 10.0, 10.1).ready
    assert not lifecycle_identity(msg, 10.0, 10.7).fresh
    assert LIFECYCLE_TOPIC == "/mecanum/safety_lifecycle_state"
    assert RESET_SERVICE == "/mecanum/safety/request_reset"
    init = inspect.getsource(UartBridgeNode.__init__)
    assert 'serial_device' in init and 'hardware_manifest' in init
    assert 'use_sim_time' in init and 'Reliable' not in init  # QoS uses enum constants.
    assert 'create_subscription(Twist, "/cmd_vel"' in init
    assert 'create_publisher(Twist' not in init
    source = inspect.getsource(UartBridgeNode)
    assert 'create_publisher(Odometry, ODOMETRY_TOPIC' in source
    assert 'create_timer(0.1, self._heartbeat_tick)' in source
    assert '"/mecanum/safety/rearm"' not in source
    assert ODOMETRY_TOPIC == "/wheel/odometry_raw"
    assert HEARTBEAT_TOPIC == "/mcu/heartbeat"


def test_lifecycle_qos_matches_existing_owner_and_reset_is_async_coalesced():
    from rclpy.qos import DurabilityPolicy, HistoryPolicy, ReliabilityPolicy
    qos = lifecycle_qos_profile()
    assert qos.history == HistoryPolicy.KEEP_LAST and qos.depth == 10
    assert qos.reliability == ReliabilityPolicy.RELIABLE
    assert qos.durability == DurabilityPolicy.VOLATILE

    class Session:
        pending=True
        def take_owner_reset_request(self):
            was_pending=self.pending; self.pending=False; return was_pending
    class Future:
        def done(self): return False
    class Client:
        calls=0
        def service_is_ready(self): return True
        def call_async(self, request):
            assert isinstance(request, Trigger.Request)
            self.calls += 1
            return Future()
    from std_srvs.srv import Trigger
    adapter=SimpleNamespace(_session=Session(),_reset_client=Client(),_reset_future=None,
                            _lifecycle_baseline_observed=True)
    UartBridgeNode._request_owner_reset(adapter)
    UartBridgeNode._request_owner_reset(adapter)
    assert adapter._reset_client.calls == 1


def test_twist_callback_forwards_latest_values_and_shutdown_closes_without_zero():
    received=[]
    adapter=SimpleNamespace(_session=SimpleNamespace(receive_cmd_vel=lambda *v: received.append(v)),
                            _steady_clock=lambda: 12.5)
    twist=SimpleNamespace(linear=SimpleNamespace(x=0.1,y=-0.2),
                          angular=SimpleNamespace(z=0.3))
    UartBridgeNode._on_cmd_vel(adapter,twist)
    assert received == [(0.1,-0.2,0.3,12.5)]
    source=inspect.getsource(UartBridgeNode.destroy_node)
    assert '_session.shutdown()' in source
    shutdown=inspect.getsource(UartBridgeNode._heartbeat_tick)
    assert 'SOURCE_MCU' in shutdown


class _FaithfulNodeBase:
    """Offline double for Jazzy Node's already-declared use_sim_time."""
    instances = []
    def __init__(self, name):
        type(self).instances.append(self)
        self.name = name
        self._clock = _RosClock(ros_sec=400, ros_nanosec=123)
        self.parameters = {
            "use_sim_time": SimpleNamespace(value=False),
        }
        self.overrides = {
            "serial_device": "/dev/fake-uart",
            "hardware_manifest": "/tmp/manifest.yaml",
            "heartbeat_topic": HEARTBEAT_TOPIC,
            "lifecycle_timeout_s": 0.6,
        }
        self.destroyed = False
        self.timer_count = 0
        self.timers = []
    def has_parameter(self, name):
        return name in self.parameters
    def declare_parameter(self, name, value):
        if name in self.parameters:
            raise RuntimeError(f"parameter {name} already declared by Node")
        self.parameters[name] = SimpleNamespace(value=self.overrides.get(name, value))
    def get_parameter(self, name):
        return self.parameters[name]
    def get_logger(self):
        return SimpleNamespace(error=lambda message: None)
    def create_publisher(self, *args):
        publisher = SimpleNamespace(messages=[])
        publisher.publish = publisher.messages.append
        return publisher
    def create_subscription(self, *args):
        return object()
    def create_client(self, *args):
        return SimpleNamespace(service_is_ready=lambda: True,
                               call_async=lambda request: None)
    def get_clock(self):
        return self._clock
    def create_timer(self, timer_period_sec, callback, callback_group=None, clock=None):
        self.timer_count += 1
        selected_clock = self._clock if clock is None else clock
        if selected_clock is not self._clock:
            raise AssertionError("timer must use the Node-owned ROS clock")
        self.timers.append((timer_period_sec, callback, selected_clock))
        if getattr(type(self), "fail_timer", False):
            raise RuntimeError("offline timer initialization failure")
        return object()
    def destroy_node(self):
        self.destroyed = True
        return True


class _RosClock:
    """Offline ROS-clock double; deliberately differs from steady time."""
    def __init__(self, ros_sec, ros_nanosec):
        self.ros_sec = ros_sec
        self.ros_nanosec = ros_nanosec
    def now(self):
        from builtin_interfaces.msg import Time
        stamp = Time(sec=self.ros_sec, nanosec=self.ros_nanosec)
        return SimpleNamespace(to_msg=lambda: stamp)


class _SteadyClock:
    def __init__(self, value): self.value = value
    def __call__(self): return self.value


def _patch_constructor_dependencies(monkeypatch):
    made = {"transports": [], "sessions": []}
    class Transport:
        def __init__(self, port):
            self.port = port
            self.open_calls = 0
            made["transports"].append(self)
        def open(self):
            self.open_calls += 1
            return True
        def close(self):
            pass
    class Session:
        def __init__(self, transport, digest, monotonic):
            self.transport = transport
            self.monotonic = monotonic
            self.shutdown_calls = 0
            from mecanum_base_bridge.bridge_session import LifecycleIdentity, SessionState
            self.state = SessionState.ACTIVE
            self._identity = LifecycleIdentity(7, 0, True, 3, True)
            self.transport_healthy = False
            self.received_commands = []
            self.observed_identities = []
            self.reports = []
            self.continuity_reset = False
            made["sessions"].append(self)
        def shutdown(self):
            self.shutdown_calls += 1
        def receive_cmd_vel(self, *values): self.received_commands.append(values)
        def observe_lifecycle_snapshot(self, identity): self.observed_identities.append(identity)
        def take_owner_reset_request(self): return False
        def io_once(self): pass
        def take_accepted_telemetry(self):
            return self.reports.pop(0) if self.reports else None
    monkeypatch.setattr(rclpy.node, "Node", _FaithfulNodeBase)
    module = importlib.reload(bridge_node_module)
    monkeypatch.setattr(module, "SerialTransport", Transport)
    monkeypatch.setattr(module, "BridgeSession", Session)
    monkeypatch.setattr(module, "load_manifest", lambda path: {"fixture": True})
    monkeypatch.setattr(module, "communication_config_valid", lambda manifest: True)
    monkeypatch.setattr(module, "manifest_digest", lambda manifest: bytes(32))
    monkeypatch.setattr(module, "wheel_geometry", lambda manifest: {
        "wheel_diameter_m": 0.097, "wheelbase_m": 0.216, "track_m": 0.190,
        "ticks_per_wheel_revolution": 937.2, "encoder_tick_signs": (1, 1, 1, 1)})
    steady = _SteadyClock(100.0)
    monkeypatch.setattr(module, "time", SimpleNamespace(monotonic=steady))
    return made, module, steady


def test_constructor_initializes_with_existing_sim_time_and_no_serial_open(monkeypatch):
    made, module, steady = _patch_constructor_dependencies(monkeypatch)
    # Node đã sở hữu use_sim_time; override của adapter được nhận khi khai báo.
    node = module.UartBridgeNode()
    assert node.get_parameter("use_sim_time").value is False
    assert node.get_clock() is node._clock
    assert node._clock is not steady
    assert node._steady_clock is steady
    assert made["transports"][0].port == "/dev/fake-uart"
    assert made["transports"][0].open_calls == 0
    assert made["sessions"][0].monotonic is steady
    assert [timer[0] for timer in node.timers] == [0.005, 0.1]
    assert all(timer[2] is node.get_clock() for timer in node.timers)
    node.destroy_node()


def test_adapter_keeps_ros_clock_for_messages_and_steady_clock_for_freshness(monkeypatch):
    made, module, steady = _patch_constructor_dependencies(monkeypatch)
    node = module.UartBridgeNode()
    session = made["sessions"][0]
    session.transport_healthy = True
    session.reports = [
        SimpleNamespace(packet=SimpleNamespace(
            mcu_boot_id=44, reset_epoch=7, telemetry_sequence=4,
            mcu_monotonic_time_us=1_000_000, ticks_fl=0, ticks_fr=0,
            ticks_rl=0, ticks_rr=0, mcu_fault_bits=0, estop_aux_active=0),
            pi_receive_time=99.95),
        SimpleNamespace(packet=SimpleNamespace(
            mcu_boot_id=44, reset_epoch=7, telemetry_sequence=5,
            mcu_monotonic_time_us=1_020_000, ticks_fl=10, ticks_fr=10,
            ticks_rl=10, ticks_rr=10, mcu_fault_bits=0, estop_aux_active=0),
            pi_receive_time=99.95),
    ]

    from geometry_msgs.msg import Twist
    twist = Twist()
    twist.linear.x = 0.1
    twist.linear.y = -0.2
    twist.angular.z = 0.3
    node._on_cmd_vel(twist)
    assert session.received_commands[-1] == (0.1, -0.2, 0.3, 100.0)

    owner = SafetyLifecycleState()
    owner.reset_epoch = 7
    owner.runtime_generation = 0
    owner.sequence = 9
    owner.primary_state = SafetyLifecycleState.PRIMARY_ACTIVE
    owner.barrier_state = SafetyLifecycleState.BARRIER_READY
    owner.motion_permitted = True
    node._on_lifecycle(owner)
    assert node._owner_received_at == steady()
    node._io_tick()

    odometry = node._odom_pub.messages[-1]
    assert (odometry.header.stamp.sec, odometry.header.stamp.nanosec) == (400, 123)
    assert session.observed_identities[-1].fresh
    assert node._latest_report.pi_receive_time == 99.95

    node._heartbeat_tick()
    heartbeat = node._heartbeat_pub.messages[-1]
    assert (heartbeat.header.stamp.sec, heartbeat.header.stamp.nanosec) == (400, 123)
    assert heartbeat.healthy
    node.destroy_node()


def test_constructor_rejects_sim_time_true_and_cleans_node(monkeypatch):
    made, module, _ = _patch_constructor_dependencies(monkeypatch)
    original = _FaithfulNodeBase.__init__
    def init_with_sim_time(self, name):
        original(self, name)
        self.parameters["use_sim_time"] = SimpleNamespace(value=True)
    monkeypatch.setattr(_FaithfulNodeBase, "__init__", init_with_sim_time)
    before = len(_FaithfulNodeBase.instances)
    with pytest.raises(ValueError, match="use_sim_time=false"):
        module.UartBridgeNode()
    assert made["transports"] == []
    assert _FaithfulNodeBase.instances[before].destroyed


def test_constructor_fails_closed_before_transport_when_signs_missing(monkeypatch):
    made, module, _ = _patch_constructor_dependencies(monkeypatch)
    monkeypatch.setattr(module, "wheel_geometry",
                        lambda manifest: (_ for _ in ()).throw(
                            HardwareConfigError("encoder signs are unresolved")))
    with pytest.raises(HardwareConfigError, match="signs"):
        module.UartBridgeNode()
    assert made["transports"] == [] and made["sessions"] == []


@pytest.mark.parametrize("timeout", [float("nan"), float("inf"), 0.0, -0.1])
def test_constructor_rejects_nonpositive_or_nonfinite_lifecycle_timeout(monkeypatch, timeout):
    made, module, _ = _patch_constructor_dependencies(monkeypatch)
    original = _FaithfulNodeBase.__init__
    def init_with_timeout(self, name):
        original(self, name)
        self.overrides["lifecycle_timeout_s"] = timeout
    monkeypatch.setattr(_FaithfulNodeBase, "__init__", init_with_timeout)
    with pytest.raises(ValueError, match="lifecycle_timeout_s"):
        module.UartBridgeNode()
    assert made["transports"] == [] and made["sessions"] == []


def test_constructor_failure_cleans_session_and_node(monkeypatch):
    made, module, _ = _patch_constructor_dependencies(monkeypatch)
    monkeypatch.setattr(_FaithfulNodeBase, "fail_timer", True, raising=False)
    before = len(_FaithfulNodeBase.instances)
    with pytest.raises(RuntimeError, match="timer initialization"):
        module.UartBridgeNode()
    assert made["sessions"][0].shutdown_calls == 1
    assert made["transports"][0].open_calls == 0
    assert _FaithfulNodeBase.instances[before].destroyed


class _R2Transport:
    """Fake UART transport; production BridgeSession vẫn được dùng trong test."""
    def __init__(self):
        self.is_open = False
        self.open_calls = 0
        self.close_calls = 0
        self.rx = bytearray()
        self.writes = []
    def open(self):
        self.open_calls += 1
        self.is_open = True
        return True
    def close(self):
        self.close_calls += 1
        self.is_open = False
    def read(self, max_bytes=256):
        result = bytes(self.rx[:max_bytes])
        del self.rx[:max_bytes]
        return result
    def write(self, data):
        self.writes.append(bytes(data))
        return len(data)
    def inject(self, data): self.rx.extend(data)


class _R2Future:
    def __init__(self, done=False): self.is_done = done
    def done(self): return self.is_done
    def result(self): return SimpleNamespace(success=True)


class _R2ResetClient:
    def __init__(self, on_call=None, ready=True, future_done=False):
        self.on_call = on_call
        self.ready = ready
        self.future = _R2Future(future_done)
        self.calls = 0
    def service_is_ready(self): return self.ready
    def call_async(self, request):
        from std_srvs.srv import Trigger
        assert isinstance(request, Trigger.Request)
        self.calls += 1
        if self.on_call is not None:
            self.on_call()
        return self.future


def _safety_lifecycle_core_type():
    path = Path(__file__).resolve().parents[4] / (
        "ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/runtime_safety/safety_contract.py")
    spec = spec_from_file_location("u5_r2_test_safety_contract", path)
    module = module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.SafetyLifecycleCore


def _safety_snapshot_message(snapshot):
    message = SafetyLifecycleState()
    message.episode_generation = snapshot.episode_generation
    message.reset_epoch = snapshot.reset_epoch
    message.runtime_generation = snapshot.runtime_generation
    message.sequence = snapshot.sequence
    message.primary_state = {
        "Unconfigured": SafetyLifecycleState.PRIMARY_UNCONFIGURED,
        "Inactive": SafetyLifecycleState.PRIMARY_INACTIVE,
        "Active": SafetyLifecycleState.PRIMARY_ACTIVE,
    }[snapshot.primary_state.value]
    message.barrier_state = {
        "INIT": SafetyLifecycleState.BARRIER_INIT,
        "READY": SafetyLifecycleState.BARRIER_READY,
        "NON_READY": SafetyLifecycleState.BARRIER_NON_READY,
        "FAULT": SafetyLifecycleState.BARRIER_FAULT,
    }[snapshot.barrier_state.value]
    message.motion_permitted = snapshot.motion_permitted
    return message


def _new_r2_production_session_node(monkeypatch, steady):
    transport = _R2Transport()
    monkeypatch.setattr(rclpy.node, "Node", _FaithfulNodeBase)
    module = importlib.reload(bridge_node_module)
    monkeypatch.setattr(module, "SerialTransport", lambda port: transport)
    monkeypatch.setattr(module, "load_manifest", lambda path: {"fixture": True})
    monkeypatch.setattr(module, "communication_config_valid", lambda manifest: True)
    monkeypatch.setattr(module, "manifest_digest", lambda manifest: bytes(range(32)))
    monkeypatch.setattr(module, "wheel_geometry", lambda manifest: {
        "wheel_diameter_m": 0.097, "wheelbase_m": 0.216, "track_m": 0.190,
        "ticks_per_wheel_revolution": 937.2, "encoder_tick_signs": (1, 1, 1, 1)})
    monkeypatch.setattr(module, "time", SimpleNamespace(monotonic=steady))
    return module.UartBridgeNode(), module, transport


def _deliver_owner_snapshot(node, core):
    node._on_lifecycle(_safety_snapshot_message(core.snapshot()))


def _decode_config_request(frame):
    from mecanum_base_bridge.uart_v1_codec import decode_frame, parse_config_request
    return parse_config_request(decode_frame(frame).payload)


def test_owner_reset_waits_for_late_baseline_then_configures_non_ready_session(monkeypatch):
    from mecanum_base_bridge.bridge_session import SessionState
    from mecanum_base_bridge.protocol_constants import (
        CONFIG_ACCEPTED, MESSAGE_COMMAND, MESSAGE_CONFIG, MESSAGE_TELEMETRY,
        REJECT_NONE)
    from mecanum_base_bridge.uart_v1_codec import (
        ConfigStatusPacket, TelemetryPacket, build_wire_frame,
        serialize_config_status, serialize_telemetry)
    Core = _safety_lifecycle_core_type()
    core = Core()
    steady = _SteadyClock(0.0)
    node, _module, transport = _new_r2_production_session_node(monkeypatch, steady)
    def reset_after_baseline():
        baseline = node._session._baseline_identity
        assert baseline is not None and baseline.reset_epoch == 0 and not baseline.ready
        core.begin_reset(1)
        _deliver_owner_snapshot(node, core)
    client = _R2ResetClient(on_call=reset_after_baseline)
    node._reset_client = client

    # Startup can open the port, but repeated ticks cannot consume reset work
    # before a first owner snapshot has established the epoch baseline.
    for _ in range(4):
        node._io_tick()
    assert transport.open_calls == 1
    assert client.calls == 0
    assert node._session._owner_reset_pending

    _deliver_owner_snapshot(node, core)  # epoch 0, INIT/NON_READY owner baseline
    node._io_tick()
    assert client.calls == 1
    assert node._session._owner_reset_pending is False
    assert node._session.state == SessionState.PORT_OPEN
    assert transport.writes == []  # reset response alone has not made an epoch

    node._io_tick()  # observe Owner's epoch 1 / NON_READY snapshot, then CONFIG
    assert node._session._identity.reset_epoch == 1
    assert not node._session._identity.ready
    assert node._session.state == SessionState.CONFIGURING
    request = _decode_config_request(transport.writes[-1])
    assert request.reset_epoch == 1

    accepted = ConfigStatusPacket(request.config_sequence, request.reset_epoch,
                                  request.hardware_config_hash, 44,
                                  CONFIG_ACCEPTED, REJECT_NONE)
    transport.inject(build_wire_frame(MESSAGE_CONFIG, serialize_config_status(accepted)))
    steady.value += 0.001
    node._io_tick()
    assert node._session.state == SessionState.CONFIGURING  # status alone is not ACTIVE

    first = TelemetryPacket(1, 44, 1, 1000, 0, 0, 0, 0, 0, 0, 0)
    transport.inject(build_wire_frame(MESSAGE_TELEMETRY, serialize_telemetry(first)))
    steady.value += 0.001
    node._io_tick()
    assert node._session.state == SessionState.ACTIVE
    # NON_READY owner and absence of fresh post-activation cmd_vel block COMMAND.
    assert [_decode_frame_type(frame) for frame in transport.writes] == [MESSAGE_CONFIG]
    from geometry_msgs.msg import Twist
    node._on_cmd_vel(Twist())
    steady.value += 0.020
    node._io_tick()
    assert all(_decode_frame_type(frame) != MESSAGE_COMMAND for frame in transport.writes)
    node.destroy_node()


def _decode_frame_type(frame):
    from mecanum_base_bridge.uart_v1_codec import decode_frame
    return decode_frame(frame).message_type


def test_baseline_before_port_open_uses_same_reset_path(monkeypatch):
    Core = _safety_lifecycle_core_type()
    core = Core()
    steady = _SteadyClock(0.0)
    node, _module, transport = _new_r2_production_session_node(monkeypatch, steady)
    def reset_after_baseline():
        baseline = node._session._baseline_identity
        assert baseline is not None and baseline.reset_epoch == 0 and not baseline.ready
        core.begin_reset(1)
        _deliver_owner_snapshot(node, core)
    client = _R2ResetClient(on_call=reset_after_baseline)
    node._reset_client = client

    _deliver_owner_snapshot(node, core)
    node._io_tick()
    assert transport.open_calls == 1 and client.calls == 0
    assert node._session._owner_reset_pending
    node._io_tick()
    assert client.calls == 1
    node._io_tick()
    assert node._session.state.value == "CONFIGURING"
    assert _decode_config_request(transport.writes[-1]).reset_epoch == 1
    node.destroy_node()


def test_stale_or_invalid_baseline_keeps_reset_pending_until_fresh_snapshot(monkeypatch):
    Core = _safety_lifecycle_core_type()
    core = Core()
    steady = _SteadyClock(0.0)
    node, _module, _transport = _new_r2_production_session_node(monkeypatch, steady)
    client = _R2ResetClient()
    node._reset_client = client
    node._io_tick()  # open and queue owner reset
    assert node._session._owner_reset_pending

    stale = _safety_snapshot_message(core.snapshot())
    node._on_lifecycle(stale)
    steady.value = 1.0  # lifecycle timeout is 0.6 s
    node._io_tick()
    assert client.calls == 0 and node._session._owner_reset_pending

    invalid = _safety_snapshot_message(core.snapshot())
    invalid.reset_epoch = -1
    node._on_lifecycle(invalid)
    node._io_tick()
    assert client.calls == 0 and node._session._owner_reset_pending

    _deliver_owner_snapshot(node, core)  # fresh same-sequence baseline is accepted
    node._io_tick()
    assert client.calls == 1
    node.destroy_node()


def test_reset_request_survives_unready_service_and_inflight_call_is_coalesced(monkeypatch):
    Core = _safety_lifecycle_core_type()
    core = Core()
    steady = _SteadyClock(0.0)
    node, _module, _transport = _new_r2_production_session_node(monkeypatch, steady)
    client = _R2ResetClient(ready=False)
    node._reset_client = client
    node._io_tick()
    _deliver_owner_snapshot(node, core)
    node._io_tick()
    assert client.calls == 0 and node._session._owner_reset_pending

    client.ready = True
    node._io_tick()
    assert client.calls == 1 and not node._session._owner_reset_pending
    node._io_tick()
    node._io_tick()
    assert client.calls == 1
    node.destroy_node()


def test_successful_service_response_without_new_epoch_does_not_start_config(monkeypatch):
    from mecanum_base_bridge.bridge_session import SessionState
    Core = _safety_lifecycle_core_type()
    core = Core()
    steady = _SteadyClock(0.0)
    node, _module, transport = _new_r2_production_session_node(monkeypatch, steady)
    client = _R2ResetClient(future_done=True)  # success response, no owner snapshot
    node._reset_client = client
    node._io_tick()
    _deliver_owner_snapshot(node, core)
    node._io_tick()
    assert client.calls == 1
    for _ in range(3): node._io_tick()
    assert client.future.result().success
    assert node._session.state == SessionState.PORT_OPEN
    assert transport.writes == []
    assert node._session._await_owner_reset

    reset = core.begin_reset(1)
    node._on_lifecycle(_safety_snapshot_message(reset))
    node._io_tick()
    assert node._session.state == SessionState.CONFIGURING
    assert _decode_config_request(transport.writes[-1]).reset_epoch == 1
    node.destroy_node()
