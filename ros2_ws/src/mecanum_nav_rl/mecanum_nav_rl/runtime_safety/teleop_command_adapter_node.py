"""Adapt the raw MAPPING teleop Twist into the typed safety candidate route."""
from __future__ import annotations

import math
import os
import time

from geometry_msgs.msg import Twist
import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from mecanum_nav_rl_interfaces.msg import CommandEnvelope, SafetyLifecycleState


RAW_TOPIC = "/cmd_vel_teleop_raw"
CANDIDATE_TOPIC = "/mecanum/cmd_teleop"
LIFECYCLE_TOPIC = "/mecanum/safety_lifecycle_state"
LIFECYCLE_TTL_S = 0.6


def _qos(depth: int) -> QoSProfile:
    return QoSProfile(
        history=HistoryPolicy.KEEP_LAST, depth=depth,
        reliability=ReliabilityPolicy.RELIABLE,
        durability=DurabilityPolicy.VOLATILE,
    )


class TeleopCommandAdapterNode(Node):
    """Tag source identity and lifecycle fields; never selects final /cmd_vel."""

    def __init__(self) -> None:
        super().__init__("teleop_command_adapter")
        self.declare_parameter("use_sim_time", False)
        self.declare_parameter("navigation_mode", "")
        self._navigation_mode = str(self.get_parameter("navigation_mode").value)
        self._source_instance_id = os.getpid()
        self._sequence = 0
        self._steady = time.monotonic
        self._lifecycle = None
        self._lifecycle_received_s = None
        self._publisher = self.create_publisher(CommandEnvelope, CANDIDATE_TOPIC, _qos(10))
        self.create_subscription(Twist, RAW_TOPIC, self._on_raw, _qos(1))
        self.create_subscription(
            SafetyLifecycleState, LIFECYCLE_TOPIC, self._on_lifecycle, _qos(10))

    def _on_lifecycle(self, message: SafetyLifecycleState) -> None:
        self._lifecycle = message
        self._lifecycle_received_s = self._steady()

    def _ready_identity(self) -> bool:
        identity = self._lifecycle
        if identity is None or self._lifecycle_received_s is None:
            return False
        age = self._steady() - self._lifecycle_received_s
        return bool(
            self._navigation_mode == "MAPPING"
            and math.isfinite(age) and 0.0 <= age <= LIFECYCLE_TTL_S
            and identity.header.frame_id == "base_link"
            and identity.primary_state == SafetyLifecycleState.PRIMARY_ACTIVE
            and identity.barrier_state == SafetyLifecycleState.BARRIER_READY
            and identity.motion_permitted is True
        )

    def _publish(self, command: Twist, source: int) -> None:
        self._sequence += 1
        envelope = CommandEnvelope()
        envelope.header.stamp = self.get_clock().now().to_msg()
        envelope.header.frame_id = "base_link"
        envelope.source = source
        envelope.sequence = self._sequence
        if self._lifecycle is not None:
            envelope.episode_generation = self._lifecycle.episode_generation
            envelope.reset_epoch = self._lifecycle.reset_epoch
            envelope.runtime_generation = self._lifecycle.runtime_generation
        envelope.source_instance_id = self._source_instance_id
        envelope.twist = command
        self._publisher.publish(envelope)

    def _on_raw(self, message: Twist) -> None:
        values = (message.linear.x, message.linear.y, message.angular.z)
        if not all(math.isfinite(value) for value in values) or not self._ready_identity():
            self._publish(Twist(), CommandEnvelope.SOURCE_SAFE_STOP)
            return
        self._publish(message, CommandEnvelope.SOURCE_TELEOP)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = TeleopCommandAdapterNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
