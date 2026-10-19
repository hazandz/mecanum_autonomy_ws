"""Static ownership and publication-order contract for final command output."""
from pathlib import Path

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


def test_receipt_identity_only_comes_from_safety_lifecycle_and_publish_failure_emits_none() -> None:
    source = (ROOT / "ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/runtime_safety/final_twist_publisher_node.py").read_text()
    assert 'create_subscription(SafetyLifecycleState, "/mecanum/safety_lifecycle_state"' in source
    assert "receipt.episode_generation = identity.episode_generation" in source
    failure_block = source.split("except Exception as error:", 1)[1].split("return", 1)[0]
    assert "_receipt_pub.publish" not in failure_block
