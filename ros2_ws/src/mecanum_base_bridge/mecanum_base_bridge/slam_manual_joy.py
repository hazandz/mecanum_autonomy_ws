"""Offline fail-closed Joy mapper publishing the raw MAPPING teleop topic."""
from __future__ import annotations

import math
import time

from geometry_msgs.msg import Twist
import rclpy
from rclpy.node import Node
from rclpy.qos import (DurabilityPolicy, HistoryPolicy, QoSProfile,
                       ReliabilityPolicy)
from sensor_msgs.msg import Joy

from .hardware_config import load_manifest, wheel_geometry
from .slam_manual_teleop import BodyCommand, SlamBenchMotionProfile, SlamManualTeleop


JOY_RAW_TOPIC = "/cmd_vel_teleop_raw"
JOY_TIMEOUT_S = 0.25


def _reliable_volatile(depth: int) -> QoSProfile:
    return QoSProfile(
        history=HistoryPolicy.KEEP_LAST, depth=depth,
        reliability=ReliabilityPolicy.RELIABLE,
        durability=DurabilityPolicy.VOLATILE,
    )


class SlamManualJoyNode(Node):
    """Map Joy to the raw teleop topic; never owns safety or serial output."""

    def __init__(self) -> None:
        super().__init__("slam_manual_joy")
        self.declare_parameter("use_sim_time", False)
        self.declare_parameter("hardware_manifest", "")
        self.declare_parameter("profile_name", "pid4_experimental_1400cps")
        self.declare_parameter("owner_design_output_rpm", 172.0)
        self.declare_parameter("motor_to_gearbox_output_ratio", 21.3)
        self.declare_parameter("wheel_rpm_per_gearbox_output_rpm", 0.0)
        self.declare_parameter("experimental_max_wheel_target_cps", 1400.0)
        self.declare_parameter("joy_timeout_s", JOY_TIMEOUT_S)
        self.declare_parameter("joy_deadzone_radius", 0.12)
        self.declare_parameter("joy_full_command_radius", 0.20)
        self.declare_parameter("sideways_fade_start_deg", 75.0)

        self._last_joy_received = None
        self._last_timeout_stop = None
        self._steady = time.monotonic
        self._joy_timeout = float(self.get_parameter("joy_timeout_s").value)
        if not math.isfinite(self._joy_timeout) or self._joy_timeout <= 0.0:
            raise ValueError("joy_timeout_s must be finite and positive")

        profile = None
        manifest_path = str(self.get_parameter("hardware_manifest").value)
        if manifest_path.strip():
            try:
                geometry = wheel_geometry(load_manifest(manifest_path))
                profile = SlamBenchMotionProfile(
                    wheel_diameter_m=geometry["wheel_diameter_m"],
                    wheelbase_m=geometry["wheelbase_m"],
                    track_m=geometry["track_m"],
                    ticks_per_wheel_revolution=geometry["ticks_per_wheel_revolution"],
                    profile_name=str(self.get_parameter("profile_name").value),
                    owner_design_output_rpm=float(
                        self.get_parameter("owner_design_output_rpm").value),
                    motor_to_gearbox_output_ratio=float(
                        self.get_parameter("motor_to_gearbox_output_ratio").value),
                    wheel_rpm_per_gearbox_output_rpm=float(
                        self.get_parameter("wheel_rpm_per_gearbox_output_rpm").value),
                    experimental_max_wheel_target_cps=float(
                        self.get_parameter("experimental_max_wheel_target_cps").value),
                    deadzone_radius=float(self.get_parameter("joy_deadzone_radius").value),
                    full_command_radius=float(
                        self.get_parameter("joy_full_command_radius").value),
                    sideways_fade_start_deg=float(
                        self.get_parameter("sideways_fade_start_deg").value),
                )
                if not profile.valid:
                    profile = None
            except (OSError, TypeError, ValueError, KeyError, OverflowError):
                profile = None

        # Kept false in this review candidate. The mapper remains testable as a
        # pure function, while this ROS adapter cannot request motion.
        self._teleop = SlamManualTeleop(profile, motion_enabled=False)
        self._raw_pub = self.create_publisher(
            Twist, JOY_RAW_TOPIC, _reliable_volatile(1))
        self.create_subscription(
            Joy, "/joy", self._on_joy,
            QoSProfile(history=HistoryPolicy.KEEP_LAST, depth=10,
                       reliability=ReliabilityPolicy.BEST_EFFORT,
                       durability=DurabilityPolicy.VOLATILE),
        )
        self.create_timer(min(0.05, self._joy_timeout / 2.0), self._watchdog_tick)

    @staticmethod
    def _stamp_ns(stamp) -> int:
        return int(stamp.sec) * 1_000_000_000 + int(stamp.nanosec)

    @staticmethod
    def _valid_joy(message: Joy) -> bool:
        try:
            axes = tuple(float(value) for value in message.axes[:2])
            buttons = tuple(message.buttons[:6])
        except (AttributeError, IndexError, TypeError, ValueError, OverflowError):
            return False
        return bool(
            len(axes) == 2 and len(buttons) == 6
            and all(math.isfinite(value) and -1.0 <= value <= 1.0 for value in axes)
            and all(type(value) is int and value in (0, 1) for value in buttons)
        )

    def _publish(self, command) -> None:
        message = Twist()
        message.linear.x = command.vx
        message.linear.y = command.vy
        message.angular.z = command.wz
        self._raw_pub.publish(message)

    def _on_joy(self, message: Joy) -> None:
        now_ns = self.get_clock().now().nanoseconds
        joy_ns = self._stamp_ns(message.header.stamp)
        fresh = joy_ns > 0 and 0 <= now_ns - joy_ns <= int(self._joy_timeout * 1e9)
        received = self._steady()
        self._last_joy_received = received
        self._last_timeout_stop = None
        if not fresh or not self._valid_joy(message):
            self._teleop.disconnected()
            self._publish(BodyCommand())
            return
        command = self._teleop.update(message.axes, message.buttons)
        self._publish(command)

    def _watchdog_tick(self) -> None:
        now = self._steady()
        expired = (self._last_joy_received is None
                   or now - self._last_joy_received > self._joy_timeout)
        if expired and self._last_timeout_stop != self._last_joy_received:
            self._teleop.disconnected()
            self._publish(BodyCommand())
            self._last_timeout_stop = self._last_joy_received


def main(args=None) -> None:
    rclpy.init(args=args)
    node = SlamManualJoyNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
