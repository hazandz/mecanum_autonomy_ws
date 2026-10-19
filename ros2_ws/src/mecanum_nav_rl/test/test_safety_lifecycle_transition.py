"""Isolated rclpy lifecycle transition coverage; no launch or simulator."""

import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[4]


def test_lifecycle_managed_publisher_follows_standard_transitions(tmp_path) -> None:
    script = r'''
import rclpy
from rclpy.lifecycle import TransitionCallbackReturn
from std_srvs.srv import Trigger
from mecanum_nav_rl.runtime_safety.safety_contract import BarrierState, PrimaryLifecycle
from mecanum_nav_rl.runtime_safety.safety_lifecycle_node import SafetyLifecycleNode

class RecordingSafetyLifecycleNode(SafetyLifecycleNode):
    def __init__(self):
        self.observed_activation = []
        super().__init__()
    def _publish_current(self):
        self.observed_activation.append(self._publisher.is_activated)
        super()._publish_current()

rclpy.init()
node=RecordingSafetyLifecycleNode()
try:
    assert node._core.snapshot().primary_state is PrimaryLifecycle.UNCONFIGURED
    assert node._core.snapshot().barrier_state is BarrierState.INIT
    assert not node._publisher.is_activated
    node._publish_current()
    assert node.observed_activation[-1] is False
    assert node.trigger_configure() == TransitionCallbackReturn.SUCCESS
    assert node._core.snapshot().primary_state is PrimaryLifecycle.INACTIVE
    assert node._core.snapshot().barrier_state is BarrierState.NON_READY
    assert not node._publisher.is_activated
    assert node.trigger_activate() == TransitionCallbackReturn.SUCCESS
    assert node._publisher.is_activated
    assert node._core.snapshot().primary_state is PrimaryLifecycle.ACTIVE
    assert node._core.snapshot().barrier_state is BarrierState.NON_READY
    assert not node._core.snapshot().motion_permitted
    assert node.observed_activation[-1] is True
    response=node._request_rearm(Trigger.Request(),Trigger.Response())
    assert response.success and node._core.snapshot().barrier_state is BarrierState.READY
    assert node._core.snapshot().motion_permitted
    assert node.trigger_deactivate() == TransitionCallbackReturn.SUCCESS
    assert node.observed_activation[-1] is True
    assert not node._publisher.is_activated
    assert node._core.snapshot().primary_state is PrimaryLifecycle.INACTIVE
    assert node._core.snapshot().barrier_state is BarrierState.NON_READY
    assert not node._core.snapshot().motion_permitted
    assert node.trigger_cleanup() == TransitionCallbackReturn.SUCCESS
    assert node._core.snapshot().primary_state is PrimaryLifecycle.UNCONFIGURED
finally:
    node.destroy_node()
    rclpy.shutdown()
'''
    env = os.environ.copy()
    env["ROS_HOME"] = str(tmp_path / "ros-home")
    env["ROS_LOG_DIR"] = str(tmp_path / "ros-log")
    Path(env["ROS_HOME"]).mkdir()
    Path(env["ROS_LOG_DIR"]).mkdir()
    subprocess.run([sys.executable, "-c", script], env=env, check=True, capture_output=True, text=True)


def test_lifecycle_callbacks_delegate_managed_entity_transitions() -> None:
    source = (ROOT / "ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/runtime_safety/safety_lifecycle_node.py").read_text(encoding="utf-8")
    for callback in ("on_configure", "on_activate", "on_deactivate", "on_cleanup", "on_error"):
        body = source.split(f"def {callback}(", 1)[1].split("\n    def ", 1)[0]
        assert f"super().{callback}(state)" in body
    activate = source.split("def on_activate(", 1)[1].split("\n    def ", 1)[0]
    assert activate.index("super().on_activate(state)") < activate.index("self._publish_current()")
    deactivate = source.split("def on_deactivate(", 1)[1].split("\n    def ", 1)[0]
    assert deactivate.index("self._publish_current()") < deactivate.index("super().on_deactivate(state)")
