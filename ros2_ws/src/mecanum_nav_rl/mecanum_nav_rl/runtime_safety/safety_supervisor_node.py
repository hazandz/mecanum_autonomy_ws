"""Fail-closed NAV2_BASELINE command selector and limiter."""
from __future__ import annotations

from geometry_msgs.msg import Twist
import math
from nav_msgs.msg import Odometry
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import LaserScan
from std_msgs.msg import Bool
from tf2_ros import Buffer, TransformListener
from mecanum_nav_rl_interfaces.msg import CommandEnvelope, SafetyLifecycleState, SafetyState

from mecanum_nav_rl.runtime_safety.safety_contract import BarrierState, SafetyInputs, SafetySupervisorCore


class SafetySupervisorNode(Node):
    def __init__(self) -> None:
        super().__init__("safety_supervisor")
        self.declare_parameter("use_sim_time", True)
        self._core = SafetySupervisorCore()
        self._command: Twist | None = None
        self._command_stamp_ns = 0
        self._scan_stamp_ns = 0
        self._scan_finite = False
        self._odom_stamp_ns = 0
        self._odom_finite = False
        self._barrier: SafetyLifecycleState | None = None
        # Unknown E-stop state is treated as active. The physical E-stop remains
        # independent of ROS and is not replaced by this supplemental boundary.
        self._estop_active = True
        self._source_sequence = 0
        self._tf_buffer = Buffer()
        self._tf_listener = TransformListener(self._tf_buffer, self)
        self._accepted_pub = self.create_publisher(CommandEnvelope, "/mecanum/safety_accepted_cmd", 10)
        self._state_pub = self.create_publisher(SafetyState, "/mecanum/safety_state", 10)
        self.create_subscription(Twist, "/mecanum/nav2_candidate_cmd", self._on_command, 10)
        self.create_subscription(LaserScan, "/scan", self._on_scan, 10)
        self.create_subscription(Odometry, "/odometry/filtered", self._on_odometry, 10)
        self.create_subscription(SafetyLifecycleState, "/mecanum/safety_lifecycle_state", self._on_barrier, 10)
        self.create_subscription(Bool, "/mecanum/estop_active", self._on_estop, 10)
        self.create_timer(0.05, self._evaluate_and_publish)

    def _on_command(self, msg: Twist) -> None:
        self._command = msg
        self._command_stamp_ns = self.get_clock().now().nanoseconds
        self._evaluate_and_publish()

    def _on_scan(self, msg: LaserScan) -> None:
        self._scan_stamp_ns = self._stamp(msg.header.stamp)
        self._scan_finite = all(math.isfinite(value) for value in msg.ranges)

    def _on_odometry(self, msg: Odometry) -> None:
        self._odom_stamp_ns = self._stamp(msg.header.stamp)
        values = [
            msg.twist.twist.linear.x, msg.twist.twist.linear.y,
            msg.twist.twist.angular.z, *msg.pose.covariance, *msg.twist.covariance,
        ]
        self._odom_finite = all(math.isfinite(value) for value in values)

    def _on_barrier(self, msg: SafetyLifecycleState) -> None:
        self._barrier = msg

    def _on_estop(self, msg: Bool) -> None:
        self._estop_active = bool(msg.data)

    @staticmethod
    def _stamp(stamp: object) -> int:
        return int(stamp.sec) * 1_000_000_000 + int(stamp.nanosec)

    def _evaluate_and_publish(self) -> None:
        if self._command is None or self._barrier is None:
            return
        now = self.get_clock().now().nanoseconds
        barrier_ns = self._stamp(self._barrier.barrier_stamp)
        barrier = BarrierState.READY if (
            self._barrier.barrier_state == SafetyLifecycleState.BARRIER_READY
            and self._barrier.motion_permitted
        ) else BarrierState.NON_READY
        try:
            tf_valid = self._tf_buffer.can_transform("odom", "base_link", rclpy.time.Time())
            localization_valid = self._tf_buffer.can_transform("map", "odom", rclpy.time.Time())
        except Exception:
            tf_valid = localization_valid = False
        values = self._command
        result = self._core.evaluate(SafetyInputs(
            now, self._command_stamp_ns, self._scan_stamp_ns, self._odom_stamp_ns,
            barrier_ns, barrier, bool(tf_valid), bool(localization_valid), self._estop_active,
            (values.linear.x, values.linear.y, values.angular.z),
            self._scan_finite, self._odom_finite,
        ))
        output = Twist()
        output.linear.x, output.linear.y, output.angular.z = result.command
        envelope = CommandEnvelope()
        envelope.header.stamp = self.get_clock().now().to_msg()
        envelope.header.frame_id = "base_link"
        envelope.source = CommandEnvelope.SOURCE_NAV2 if result.accepted else CommandEnvelope.SOURCE_SAFE_STOP
        self._source_sequence += 1
        envelope.sequence = self._source_sequence
        envelope.reset_epoch = self._barrier.reset_epoch
        envelope.runtime_generation = self._barrier.runtime_generation
        import os
        envelope.source_instance_id = os.getpid()
        envelope.twist = output
        self._accepted_pub.publish(envelope)
        state = SafetyState()
        state.header = envelope.header
        state.state = SafetyState.STATE_NORMAL if result.accepted else SafetyState.STATE_STOPPED
        state.reset_epoch = envelope.reset_epoch
        state.runtime_generation = envelope.runtime_generation
        state.active_command_source = envelope.source
        state.command_valid = result.accepted
        state.scan_fresh = not any(r == "SCAN_STALE_OR_INVALID" for r in result.reasons)
        state.odom_fresh = not any(r == "FILTERED_ODOMETRY_STALE_OR_INVALID" for r in result.reasons)
        state.tf_valid = bool(tf_valid)
        state.localization_valid = bool(localization_valid)
        state.motion_permitted = result.accepted
        state.estop_active = self._estop_active
        state.intervention_reasons = list(result.reasons)
        state.raw_command = self._command
        state.limited_command = output
        state.final_command = output
        self._state_pub.publish(state)


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = SafetySupervisorNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
