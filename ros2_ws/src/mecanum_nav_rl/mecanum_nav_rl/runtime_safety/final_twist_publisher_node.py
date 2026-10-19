"""Single ROS /cmd_vel publisher with publish-before-receipt ordering."""
from __future__ import annotations

import os
from geometry_msgs.msg import Twist
import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from mecanum_nav_rl_interfaces.msg import CommandEnvelope, FinalIssuedCommandReceipt, SafetyLifecycleState


class FinalTwistPublisherNode(Node):
    def __init__(self) -> None:
        super().__init__("final_twist_publisher")
        self.declare_parameter("use_sim_time", True)
        self._identity: SafetyLifecycleState | None = None
        self._final_publish_sequence = 0
        self._publisher_instance_id = os.getpid()
        command_qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST, depth=1,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.VOLATILE,
        )
        receipt_qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST, depth=1,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
        )
        reliable_volatile = QoSProfile(
            history=HistoryPolicy.KEEP_LAST, depth=10,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.VOLATILE,
        )
        self._cmd_pub = self.create_publisher(Twist, "/cmd_vel", command_qos)
        self._receipt_pub = self.create_publisher(FinalIssuedCommandReceipt, "/mecanum/final_issued_command", receipt_qos)
        self.create_subscription(CommandEnvelope, "/mecanum/safety_accepted_cmd", self._on_accepted, reliable_volatile)
        self.create_subscription(SafetyLifecycleState, "/mecanum/safety_lifecycle_state", self._on_lifecycle, reliable_volatile)

    def _on_lifecycle(self, msg: SafetyLifecycleState) -> None:
        self._identity = msg

    def _on_accepted(self, envelope: CommandEnvelope) -> None:
        identity = self._identity
        is_safe_stop = envelope.source == CommandEnvelope.SOURCE_SAFE_STOP
        if not is_safe_stop and envelope.source != CommandEnvelope.SOURCE_NAV2:
            return
        if not is_safe_stop:
            if identity is None:
                return
            envelope_identity = (
                envelope.episode_generation,
                envelope.reset_epoch,
                envelope.runtime_generation,
            )
            lifecycle_identity = (
                identity.episode_generation,
                identity.reset_epoch,
                identity.runtime_generation,
            )
            if envelope_identity != lifecycle_identity:
                self.get_logger().error("NAV2_COMMAND_LIFECYCLE_IDENTITY_MISMATCH")
                return
            now_ns = self.get_clock().now().nanoseconds
            identity_ns = identity.header.stamp.sec * 1_000_000_000 + identity.header.stamp.nanosec
            identity_fresh = identity_ns > 0 and 0 <= now_ns - identity_ns <= 500_000_000
            if not identity.motion_permitted or not identity_fresh:
                self.get_logger().error("NAV2_COMMAND_LIFECYCLE_BARRIER_NOT_READY_OR_STALE")
                return
        final_command = Twist() if is_safe_stop else envelope.twist
        try:
            self._cmd_pub.publish(final_command)
        except Exception as error:
            self.get_logger().error(f"FINAL_CMD_PUBLISH_FAILED:{type(error).__name__}")
            return
        self._final_publish_sequence += 1
        receipt = FinalIssuedCommandReceipt()
        receipt.header.stamp = self.get_clock().now().to_msg()
        receipt.header.frame_id = "base_link"
        receipt.episode_generation = envelope.episode_generation
        receipt.reset_epoch = envelope.reset_epoch
        receipt.runtime_generation = envelope.runtime_generation
        receipt.step_index = envelope.sequence
        receipt.transition_id = "sim_eval_nav2_baseline"
        receipt.source = envelope.source
        receipt.sequence = envelope.sequence
        receipt.source_instance_id = envelope.source_instance_id
        receipt.final_publisher_instance_id = self._publisher_instance_id
        receipt.final_publish_sequence = self._final_publish_sequence
        receipt.final_command = final_command
        self._receipt_pub.publish(receipt)


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = FinalTwistPublisherNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
