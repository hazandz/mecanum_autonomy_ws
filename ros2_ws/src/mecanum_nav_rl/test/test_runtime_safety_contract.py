"""Unit tests for explicit lifecycle barriers and immutable safety policy."""
from dataclasses import replace
from pathlib import Path

import pytest
import yaml

from mecanum_nav_rl.runtime_safety.safety_contract import (
    BarrierState, PrimaryLifecycle, SafetyInputs, SafetyLifecycleCore,
    SafetyPolicy, SafetySupervisorCore,
)


def _policy(**updates) -> SafetyPolicy:
    data = {
        "freshness_ns": {
            "command_ttl": 200_000_000, "scan_max_age": 500_000_000,
            "filtered_odometry_max_age": 250_000_000,
            "lifecycle_barrier_max_age": 500_000_000,
        },
        "limits": {"velocity": [0.25, 0.20, 0.80],
                   "acceleration": [0.50, 0.50, 1.00], "jerk": [2.0, 2.0, 4.0]},
    }
    for section, values in updates.items():
        data[section].update(values)
    return SafetyPolicy.from_mapping(data)


def _valid(now: int, command=(0.1, 0.1, 0.2)) -> SafetyInputs:
    return SafetyInputs(now, now, now, now, now, BarrierState.READY, True, True, True, command)


def test_lifecycle_requires_explicit_rearm_after_activation_and_reset() -> None:
    core = SafetyLifecycleCore()
    assert core.snapshot().primary_state is PrimaryLifecycle.UNCONFIGURED
    assert not core.snapshot().motion_permitted
    configured = core.configure(10)
    assert configured.primary_state is PrimaryLifecycle.INACTIVE
    assert configured.barrier_state is BarrierState.NON_READY and not configured.motion_permitted
    with pytest.raises(ValueError, match="LIFECYCLE_REARM_REQUIRES_ACTIVE"):
        core.rearm(15)
    active = core.activate(20)
    assert active.primary_state is PrimaryLifecycle.ACTIVE
    assert active.barrier_state is BarrierState.NON_READY and not active.motion_permitted
    ready = core.rearm(25)
    assert ready.barrier_state is BarrierState.READY and ready.motion_permitted
    assert ready.runtime_generation == 1
    reset = core.begin_reset(30)
    assert reset.reset_epoch == 1 and reset.episode_generation == 1
    assert reset.barrier_state is BarrierState.NON_READY and not reset.motion_permitted
    rearmed = core.rearm(35)
    assert rearmed.runtime_generation == 2 and rearmed.motion_permitted


def test_lifecycle_clock_regression_faults_closed() -> None:
    core = SafetyLifecycleCore()
    core.configure(100)
    core.activate(110)
    identity = core.refresh(99)
    assert identity.barrier_state is BarrierState.FAULT
    assert not identity.motion_permitted
    assert identity.reason == "LIFECYCLE_CLOCK_REGRESSION"


def test_safety_fails_closed_for_missing_stale_invalid_and_unreleased_estop() -> None:
    core = SafetySupervisorCore(_policy())
    cases = [
        (replace(_valid(1_000_000_000), command_stamp_ns=1), "COMMAND_STALE_OR_INVALID"),
        (replace(_valid(1_000_000_000), sensor_values_finite=False), "SCAN_NON_FINITE"),
        (replace(_valid(1_000_000_000), odometry_values_finite=False), "FILTERED_ODOMETRY_NON_FINITE"),
        (replace(_valid(1_000_000_000), tf_valid=False), "TF_INVALID"),
        (replace(_valid(1_000_000_000), localization_valid=False), "LOCALIZATION_INVALID"),
        (replace(_valid(1_000_000_000), sim_estop_release_authorized=False), "SIM_ESTOP_ACTIVE"),
        (replace(_valid(1_000_000_000), lifecycle=BarrierState.NON_READY), "LIFECYCLE_BARRIER_NOT_READY"),
        (replace(_valid(1_000_000_000), scan_stamp_ns=0), "SCAN_STALE_OR_INVALID"),
        (replace(_valid(1_000_000_000), odometry_stamp_ns=0), "FILTERED_ODOMETRY_STALE_OR_INVALID"),
        (replace(_valid(1_000_000_000), lifecycle_stamp_ns=0), "LIFECYCLE_BARRIER_STALE_OR_INVALID"),
        (replace(_valid(1_000_000_000), scan_frame_valid=False), "SCAN_FRAME_INVALID"),
        (replace(_valid(1_000_000_000), odometry_frame_valid=False), "FILTERED_ODOMETRY_FRAME_INVALID"),
        (replace(_valid(1_000_000_000), command=(float("nan"), 0.0, 0.0)), "COMMAND_NON_FINITE"),
    ]
    for inputs, literal in cases:
        result = core.evaluate(inputs)
        assert not result.accepted and result.command == (0.0, 0.0, 0.0)
        assert literal in result.reasons


@pytest.mark.parametrize(
    ("field", "configured_limit"),
    (("velocity", 0.05), ("acceleration", 0.10), ("jerk", 0.20)),
)
def test_each_configured_limit_group_changes_core_behavior(field: str, configured_limit: float) -> None:
    baseline_policy = _policy()
    values = {"velocity": list(baseline_policy.velocity),
              "acceleration": list(baseline_policy.acceleration),
              "jerk": list(baseline_policy.jerk)}
    values[field][0] = configured_limit
    changed_policy = SafetyPolicy(
        baseline_policy.command_ttl_ns, baseline_policy.scan_max_age_ns,
        baseline_policy.filtered_odometry_max_age_ns, baseline_policy.lifecycle_barrier_max_age_ns,
        tuple(values["velocity"]), tuple(values["acceleration"]), tuple(values["jerk"]),
    )
    baseline = SafetySupervisorCore(baseline_policy)
    changed = SafetySupervisorCore(changed_policy)
    command = (0.25, 0.0, 0.0)
    baseline.evaluate(_valid(1_000_000_000, command))
    changed.evaluate(_valid(1_000_000_000, command))
    standard = baseline.evaluate(_valid(2_000_000_000, command))
    limited = changed.evaluate(_valid(2_000_000_000, command))
    assert standard.accepted and limited.accepted
    assert abs(limited.command[0]) < abs(standard.command[0])


@pytest.mark.parametrize(
    ("field", "stamp_field", "reason"),
    (("command_ttl_ns", "command_stamp_ns", "COMMAND_STALE_OR_INVALID"),
     ("scan_max_age_ns", "scan_stamp_ns", "SCAN_STALE_OR_INVALID"),
     ("filtered_odometry_max_age_ns", "odometry_stamp_ns", "FILTERED_ODOMETRY_STALE_OR_INVALID"),
     ("lifecycle_barrier_max_age_ns", "lifecycle_stamp_ns", "LIFECYCLE_BARRIER_STALE_OR_INVALID")),
)
def test_each_configured_freshness_value_changes_acceptance(field: str, stamp_field: str, reason: str) -> None:
    policy = replace(_policy(), **{field: 10})
    core = SafetySupervisorCore(policy)
    stale = replace(_valid(100), **{stamp_field: 50})
    result = core.evaluate(stale)
    assert not result.accepted and result.command == (0.0, 0.0, 0.0)
    assert reason in result.reasons


def test_lifecycle_node_has_only_explicit_reset_and_rearm_services_and_no_auto_transition() -> None:
    root = Path(__file__).resolve().parents[1]
    source = (root / "mecanum_nav_rl/runtime_safety/safety_lifecycle_node.py").read_text(encoding="utf-8")
    assert '"/mecanum/safety/request_reset"' in source
    assert '"/mecanum/safety/rearm"' in source
    assert source.count("self.create_service(") == 2
    assert "trigger_configure" not in source and "trigger_activate" not in source
    assert "self._publisher.is_activated" in source
    for callback in ("on_configure", "on_activate", "on_deactivate", "on_cleanup", "on_error"):
        block = source.split(f"def {callback}(", 1)[1].split("\n    def ", 1)[0]
        assert f"super().{callback}(state)" in block
    assert source.index("super().on_activate(state)") < source.index("self._publish_current()", source.index("super().on_activate(state)"))
    deactivate = source.split("def on_deactivate(", 1)[1].split("\n    def ", 1)[0]
    assert deactivate.index("self._publish_current()") < deactivate.index("super().on_deactivate(state)")


def test_supervisor_defaults_to_estop_active_and_emits_safe_stop_without_inputs() -> None:
    root = Path(__file__).resolve().parents[1]
    source = (root / "mecanum_nav_rl/runtime_safety/safety_supervisor_node.py").read_text(encoding="utf-8")
    assert 'declare_parameter("sim_estop_release_authorized", False)' in source
    assert "if self._command is None" not in source
    assert "self._accepted_pub.publish(envelope)" in source
    assert "create_publisher(Bool" not in source
    assert "envelope.episode_generation = barrier_msg.episode_generation if barrier_msg is not None else 0" in source
    assert "envelope.reset_epoch = barrier_msg.reset_epoch if barrier_msg is not None else 0" in source
    assert "envelope.runtime_generation = barrier_msg.runtime_generation if barrier_msg is not None else 0" in source
    assert "SOURCE_SAFE_STOP" in source


def test_safety_policy_is_loaded_from_selected_yaml_values() -> None:
    root = Path(__file__).resolve().parents[1]
    config = yaml.safe_load((root / "config/safety/sim_eval_nav2_baseline_safety.yaml").read_text(encoding="utf-8"))
    policy = SafetyPolicy.from_mapping(config)
    assert policy.command_ttl_ns == config["freshness_ns"]["command_ttl"]
    assert policy.scan_max_age_ns == config["freshness_ns"]["scan_max_age"]
    assert policy.filtered_odometry_max_age_ns == config["freshness_ns"]["filtered_odometry_max_age"]
    assert policy.lifecycle_barrier_max_age_ns == config["freshness_ns"]["lifecycle_barrier_max_age"]
    assert policy.velocity == tuple(config["limits"]["velocity"])
    assert policy.acceleration == tuple(config["limits"]["acceleration"])
    assert policy.jerk == tuple(config["limits"]["jerk"])
    launch = (root.parent / "mecanum_nav_bringup/launch/sim_eval_nav2_baseline_system.launch.py").read_text(encoding="utf-8")
    assert 'yaml.safe_load(Path(safety_config).read_text(encoding="utf-8"))' in launch
    assert '"freshness_ns.{key}": value' in launch and '"limits.{key}": value' in launch


def test_policy_validation_rejects_missing_wrong_negative_and_nonfinite_values() -> None:
    with pytest.raises(ValueError, match="SAFETY_POLICY_MISSING_INVALID_OR_NONFINITE"):
        SafetyPolicy.from_mapping({"freshness_ns": {}, "limits": {}})
    with pytest.raises(ValueError, match="SAFETY_POLICY_MISSING_INVALID_OR_NONFINITE"):
        SafetyPolicy.from_mapping({
            "freshness_ns": {"command_ttl": -1, "scan_max_age": 1,
                "filtered_odometry_max_age": 1, "lifecycle_barrier_max_age": 1},
            "limits": {"velocity": [1, 1, 1], "acceleration": [1, 1, 1], "jerk": [1, 1, float("inf")]},
        })


def test_control_time_regression_fails_closed() -> None:
    core = SafetySupervisorCore(_policy())
    core.evaluate(_valid(1_000_000_000))
    core.evaluate(_valid(1_050_000_000))
    result = core.evaluate(_valid(1_040_000_000))
    assert not result.accepted
    assert result.reasons == ("CONTROL_TIMESTAMP_NOT_MONOTONIC",)


def test_supervisor_predeclared_sim_clock_and_scan_validity_without_ros_graph(tmp_path):
    import os
    import subprocess
    import sys
    script = r'''
from types import SimpleNamespace as NS
import math
import rclpy.node
from sensor_msgs.msg import LaserScan
class Node:
    clock_value = True
    def __init__(self, name):
        self.parameters = {"use_sim_time": self.clock_value}
    def declare_parameter(self, name, value=None):
        assert name not in self.parameters, "PARAMETER_ALREADY_DECLARED"
        if name.startswith("freshness_ns."):
            value = 500000000
        elif name.startswith("limits."):
            value = [0.25, 0.20, 0.80]
        self.parameters[name] = value
    def get_parameter(self, name): return NS(value=self.parameters[name])
    def create_publisher(self, *args): return NS(publish=lambda msg: None)
    def create_subscription(self, *args): return NS()
    def create_timer(self, *args): return NS()
rclpy.node.Node = Node
from mecanum_nav_rl.runtime_safety import safety_supervisor_node as module
module.Buffer = lambda: NS()
module.TransformListener = lambda *args: NS()
n = module.SafetySupervisorNode()
assert n.get_parameter("use_sim_time").value is True
for invalid in (False, 1, "true"):
    Node.clock_value = invalid
    try: module.SafetySupervisorNode()
    except ValueError as error: assert str(error) == "SIM_EVAL_USE_SIM_TIME_MUST_BE_TRUE"
    else: raise AssertionError("clock sai vẫn được nhận")
def scan(values):
    msg = LaserScan()
    msg.header.frame_id = "lidar_frame"
    msg.header.stamp.sec = 1
    msg.angle_min = -math.pi; msg.angle_increment = 0.1
    msg.range_min = 0.1; msg.range_max = 10.0
    msg.ranges = values
    return msg
for values, expected in (([1.0,2.0],True),([1.0,math.inf],True),([math.inf]*3,True),
                         ([math.nan],False),([-math.inf],False),([],False)):
    msg = scan(values)
    module.SafetySupervisorNode._on_scan(n, msg)
    assert n._scan_finite is expected
for field, value in (("range_min",-1.0),("range_max",0.0),("range_max",math.inf),
                     ("angle_increment",0.0),("angle_min",math.nan)):
    msg = scan([math.inf]); setattr(msg,field,value)
    assert not module.scan_values_valid(msg)
from builtin_interfaces.msg import Time
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from mecanum_nav_rl_interfaces.msg import SafetyLifecycleState, CommandEnvelope
outputs=[]; states=[]
n._accepted_pub=NS(publish=outputs.append); n._state_pub=NS(publish=states.append)
n._tf_buffer=NS(can_transform=lambda *args: True)
n._sim_estop_release_authorized=True
barrier=SafetyLifecycleState(); barrier.barrier_state=1; barrier.motion_permitted=True
barrier.barrier_stamp=Time(sec=1)
n._barrier=barrier
odom=Odometry(); odom.header.frame_id="odom"; odom.child_frame_id="base_link"; odom.header.stamp.sec=1
n._on_odometry(odom); n._on_scan(scan([math.inf]*3))
n._command=Twist(); n._command_stamp_ns=1000000000
now=1000000000
n.get_clock=lambda:NS(now=lambda:NS(nanoseconds=now,to_msg=lambda:Time(sec=now//1000000000)))
n._evaluate_and_publish()
assert "LIMITER_PRIMED" in states[-1].intervention_reasons
now=1050000000
n._evaluate_and_publish()
assert outputs[-1].source==CommandEnvelope.SOURCE_NAV2 and states[-1].scan_fresh
now=2000000000
n._command_stamp_ns=n._odom_stamp_ns=now; barrier.barrier_stamp.sec=2
n._evaluate_and_publish()
assert outputs[-1].source==CommandEnvelope.SOURCE_SAFE_STOP and not states[-1].scan_fresh
assert "SCAN_STALE_OR_INVALID" in states[-1].intervention_reasons
'''
    env = dict(os.environ)
    env["PYTHONPATH"] = str(Path(__file__).parents[1]) + os.pathsep + env.get("PYTHONPATH", "")
    result = subprocess.run([sys.executable, "-c", script], env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
