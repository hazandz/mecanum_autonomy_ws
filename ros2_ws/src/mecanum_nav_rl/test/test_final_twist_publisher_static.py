"""Static ownership and publication-order contract for final command output."""
from pathlib import Path
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[4]


def test_final_publisher_is_the_only_declared_ros_cmd_vel_publisher() -> None:
    source = (ROOT / "ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/runtime_safety/final_twist_publisher_node.py").read_text()
    assert source.count('self.create_publisher(Twist, "/cmd_vel", command_qos)') == 1
    assert 'create_subscription(CommandEnvelope, "/mecanum/safety_accepted_cmd"' in source
    assert "create_publisher(Twist, \"/cmd_vel\"" not in (
        ROOT / "ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/runtime_safety/safety_supervisor_node.py"
    ).read_text()
    assert source.index("self._cmd_pub.publish(final_command)") < source.index("self._receipt_pub.publish(receipt)")
    assert "history=HistoryPolicy.KEEP_LAST, depth=1" in source
    assert "reliability=ReliabilityPolicy.RELIABLE" in source
    assert "durability=DurabilityPolicy.VOLATILE" in source
    assert "durability=DurabilityPolicy.TRANSIENT_LOCAL" in source


def test_receipt_identity_is_mirrored_from_validated_envelope() -> None:
    source = (ROOT / "ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/runtime_safety/final_twist_publisher_node.py").read_text()
    assert 'create_subscription(SafetyLifecycleState, "/mecanum/safety_lifecycle_state"' in source
    assert "receipt.episode_generation = envelope.episode_generation" in source
    assert "receipt.reset_epoch = envelope.reset_epoch" in source
    assert "receipt.runtime_generation = envelope.runtime_generation" in source
    assert "envelope_identity != lifecycle_identity" in source
    failure_block = source.split("except Exception as error:", 1)[1].split("return", 1)[0]
    assert "_receipt_pub.publish" not in failure_block


def test_receipt_publication_contract_in_isolated_ros_python_process(tmp_path) -> None:
    script = r'''
from types import SimpleNamespace
from geometry_msgs.msg import Twist
from mecanum_nav_rl_interfaces.msg import CommandEnvelope, SafetyLifecycleState
from mecanum_nav_rl.runtime_safety.final_twist_publisher_node import FinalTwistPublisherNode

class Publisher:
    def __init__(self, events, name, fail=False):
        self.events, self.name, self.fail, self.messages = events, name, fail, []
    def publish(self, message):
        self.events.append(self.name)
        if self.fail:
            raise RuntimeError("publish failed")
        self.messages.append(message)

def stamp(sec, nanosec=0):
    return SimpleNamespace(sec=sec, nanosec=nanosec)

def identity(episode=7, reset=8, runtime=9, ready=True):
    value = SafetyLifecycleState()
    value.header.stamp = stamp(10)
    value.episode_generation, value.reset_epoch, value.runtime_generation = episode, reset, runtime
    value.motion_permitted = ready
    return value

def envelope(source, episode=7, reset=8, runtime=9, command=(0.1, -0.2, 0.3)):
    value = CommandEnvelope()
    value.source, value.sequence = source, 41
    value.episode_generation, value.reset_epoch, value.runtime_generation = episode, reset, runtime
    value.source_instance_id = 1234
    value.twist.linear.x, value.twist.linear.y, value.twist.angular.z = command
    return value

def node(current_identity, events, fail=False):
    now = SimpleNamespace(nanoseconds=10_100_000_000, to_msg=lambda: stamp(10, 100_000_000))
    value = SimpleNamespace(
        _identity=current_identity, _final_publish_sequence=0, _publisher_instance_id=77,
        _cmd_pub=Publisher(events, "cmd", fail), _receipt_pub=Publisher(events, "receipt"),
        get_clock=lambda: SimpleNamespace(now=lambda: now),
        get_logger=lambda: SimpleNamespace(error=lambda _message: None),
    )
    return value

events=[]; n=node(identity(), events); e=envelope(CommandEnvelope.SOURCE_NAV2)
FinalTwistPublisherNode._on_accepted(n,e)
assert events == ["cmd", "receipt"] and len(n._receipt_pub.messages) == 1
r=n._receipt_pub.messages[0]
assert (r.episode_generation,r.reset_epoch,r.runtime_generation)==(e.episode_generation,e.reset_epoch,e.runtime_generation)
assert r.sequence == r.step_index == e.sequence and r.source_instance_id == e.source_instance_id
assert (r.final_command.linear.x,r.final_command.linear.y,r.final_command.angular.z)==(e.twist.linear.x,e.twist.linear.y,e.twist.angular.z)

events=[]; n=node(None,events); e=envelope(CommandEnvelope.SOURCE_SAFE_STOP,0,0,0,(0.0,0.0,0.0))
FinalTwistPublisherNode._on_accepted(n,e)
assert events == ["cmd", "receipt"] and len(n._receipt_pub.messages)==1
r=n._receipt_pub.messages[0]
assert (r.episode_generation,r.reset_epoch,r.runtime_generation)==(0,0,0)
assert (r.final_command.linear.x,r.final_command.linear.y,r.final_command.angular.z)==(0.0,0.0,0.0)

events=[]; n=node(identity(),events,True)
FinalTwistPublisherNode._on_accepted(n,envelope(CommandEnvelope.SOURCE_NAV2))
assert events == ["cmd"] and not n._receipt_pub.messages

events=[]; n=node(identity(episode=7),events)
FinalTwistPublisherNode._on_accepted(n,envelope(CommandEnvelope.SOURCE_NAV2,episode=6))
assert events == [] and not n._cmd_pub.messages and not n._receipt_pub.messages
'''
    env = os.environ.copy()
    env["ROS_HOME"] = str(tmp_path / "ros-home")
    env["ROS_LOG_DIR"] = str(tmp_path / "ros-log")
    Path(env["ROS_HOME"]).mkdir()
    Path(env["ROS_LOG_DIR"]).mkdir()
    subprocess.run([sys.executable, "-c", script], env=env, check=True, capture_output=True, text=True)
