"""Fail-closed NAV2_BASELINE command selector and limiter."""
from __future__ import annotations

from geometry_msgs.msg import Twist
import math
from nav_msgs.msg import Odometry
import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import LaserScan
from tf2_ros import Buffer, TransformListener
from mecanum_nav_rl_interfaces.msg import CommandEnvelope, SafetyLifecycleState, SafetyState

from mecanum_nav_rl.runtime_safety.safety_contract import (
    BarrierState, SafetyInputs, SafetyLifecycleCore, SafetyPolicy, SafetySupervisorCore,
)


class SafetySupervisorNode(Node):
    _POLICY_NAMES = (
        "freshness_ns.command_ttl", "freshness_ns.scan_max_age",
        "freshness_ns.filtered_odometry_max_age", "freshness_ns.lifecycle_barrier_max_age",
        "limits.velocity", "limits.acceleration", "limits.jerk",
    )

    def __init__(self) -> None:
        super().__init__("safety_supervisor")
        self.declare_parameter("use_sim_time", True)
        for name in self._POLICY_NAMES:
            self.declare_parameter(name)
        self.declare_parameter("sim_estop_release_authorized", False)
        self._policy = SafetyPolicy.from_mapping({
            "freshness_ns": {
                "command_ttl": self.get_parameter("freshness_ns.command_ttl").value,
                "scan_max_age": self.get_parameter("freshness_ns.scan_max_age").value,
                "filtered_odometry_max_age": self.get_parameter("freshness_ns.filtered_odometry_max_age").value,
                "lifecycle_barrier_max_age": self.get_parameter("freshness_ns.lifecycle_barrier_max_age").value,
            },
            "limits": {
                "velocity": self.get_parameter("limits.velocity").value,
                "acceleration": self.get_parameter("limits.acceleration").value,
                "jerk": self.get_parameter("limits.jerk").value,
            },
        })
        estop_parameter = self.get_parameter("sim_estop_release_authorized").value
        if type(estop_parameter) is not bool:
            raise ValueError("SIM_ESTOP_RELEASE_AUTHORIZATION_MUST_BE_BOOLEAN")
        self._sim_estop_release_authorized = estop_parameter
        self._core = SafetySupervisorCore(self._policy)
        self._command: Twist | None = None
        self._command_stamp_ns = 0
        self._scan_stamp_ns = 0
        self._scan_finite = False
        self._scan_frame_valid = False
        self._odom_stamp_ns = 0
        self._odom_finite = False
        self._odom_frame_valid = False
        self._barrier: SafetyLifecycleState | None = None
        self._source_sequence = 0
        self._tf_buffer = Buffer()
        self._tf_listener = TransformListener(self._tf_buffer, self)
        reliable_volatile = QoSProfile(
            history=HistoryPolicy.KEEP_LAST, depth=10,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.VOLATILE,
        )
        sensor_data_qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST, depth=10,
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE,
        )
        self._accepted_pub = self.create_publisher(
            CommandEnvelope, "/mecanum/safety_accepted_cmd", reliable_volatile
        )
        self._state_pub = self.create_publisher(SafetyState, "/mecanum/safety_state", reliable_volatile)
        self.create_subscription(Twist, "/mecanum/nav2_candidate_cmd", self._on_command, reliable_volatile)
        self.create_subscription(LaserScan, "/scan", self._on_scan, sensor_data_qos)
        self.create_subscription(Odometry, "/odometry/filtered", self._on_odometry, reliable_volatile)
        self.create_subscription(SafetyLifecycleState, "/mecanum/safety_lifecycle_state", self._on_barrier, reliable_volatile)
        self.create_timer(0.05, self._evaluate_and_publish)

    def _on_command(self, msg: Twist) -> None:
        self._command = msg
        self._command_stamp_ns = self.get_clock().now().nanoseconds

    def _on_scan(self, msg: LaserScan) -> None:
        self._scan_stamp_ns = self._stamp(msg.header.stamp)
        self._scan_frame_valid = msg.header.frame_id == "lidar_frame"
        self._scan_finite = bool(msg.ranges) and all(math.isfinite(value) for value in msg.ranges)

    def _on_odometry(self, msg: Odometry) -> None:
        self._odom_stamp_ns = self._stamp(msg.header.stamp)
        self._odom_frame_valid = msg.header.frame_id == "odom" and msg.child_frame_id == "base_link"
        values = [msg.twist.twist.linear.x, msg.twist.twist.linear.y, msg.twist.twist.angular.z,
                  *msg.pose.covariance, *msg.twist.covariance]
        self._odom_finite = len(msg.pose.covariance) == 36 and len(msg.twist.covariance) == 36 and all(math.isfinite(value) for value in values)

    def _on_barrier(self, msg: SafetyLifecycleState) -> None:
        self._barrier = msg

    @staticmethod
    def _stamp(stamp: object) -> int:
        return int(stamp.sec) * 1_000_000_000 + int(stamp.nanosec)

    def _evaluate_and_publish(self) -> None:
        now = self.get_clock().now().nanoseconds
        command = self._command or Twist()
        barrier_msg = self._barrier
        barrier_ns = self._stamp(barrier_msg.barrier_stamp) if barrier_msg is not None else 0
        barrier = BarrierState.READY if barrier_msg is not None and (
            barrier_msg.barrier_state == SafetyLifecycleState.BARRIER_READY and barrier_msg.motion_permitted
        ) else BarrierState.NON_READY
        try:
            tf_valid = bool(self._tf_buffer.can_transform("odom", "base_link", rclpy.time.Time())) and self._odom_frame_valid
            localization_valid = bool(self._tf_buffer.can_transform("map", "odom", rclpy.time.Time()))
        except Exception:
            tf_valid = localization_valid = False
        result = self._core.evaluate(SafetyInputs(
            now, self._command_stamp_ns, self._scan_stamp_ns, self._odom_stamp_ns,
            barrier_ns, barrier, tf_valid, localization_valid,
            self._sim_estop_release_authorized,
            (command.linear.x, command.linear.y, command.angular.z),
            self._scan_finite, self._odom_finite,
            self._scan_frame_valid, self._odom_frame_valid,
        ))
        output = Twist()
        output.linear.x, output.linear.y, output.angular.z = result.command
        envelope = CommandEnvelope()
        envelope.header.stamp = self.get_clock().now().to_msg()
        envelope.header.frame_id = "base_link"
        envelope.source = CommandEnvelope.SOURCE_NAV2 if result.accepted else CommandEnvelope.SOURCE_SAFE_STOP
        self._source_sequence += 1
        envelope.sequence = self._source_sequence
        envelope.episode_generation = barrier_msg.episode_generation if barrier_msg is not None else 0
        envelope.reset_epoch = barrier_msg.reset_epoch if barrier_msg is not None else 0
        envelope.runtime_generation = barrier_msg.runtime_generation if barrier_msg is not None else 0
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
        state.scan_fresh = self._scan_frame_valid and self._scan_stamp_ns > 0
        state.odom_fresh = self._odom_frame_valid and self._odom_stamp_ns > 0
        state.tf_valid = tf_valid
        state.localization_valid = localization_valid
        state.motion_permitted = result.accepted
        state.estop_active = "SIM_ESTOP_ACTIVE" in result.reasons
        state.intervention_reasons = list(result.reasons)
        state.raw_command = command
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
