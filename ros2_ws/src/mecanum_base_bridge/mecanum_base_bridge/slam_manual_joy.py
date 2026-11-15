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
from std_srvs.srv import Trigger

from .hardware_config import (load_manifest, manual_slam_drive_ratios,
                              wheel_geometry)
from .slam_manual_teleop import BodyCommand, SlamBenchMotionProfile, SlamManualTeleop


CMD_VEL_TOPIC = "/cmd_vel"
JOY_TIMEOUT_S = 0.25


def _reliable_volatile(depth: int) -> QoSProfile:
    return QoSProfile(
        history=HistoryPolicy.KEEP_LAST, depth=depth,
        reliability=ReliabilityPolicy.RELIABLE,
        durability=DurabilityPolicy.VOLATILE,
    )


class SlamManualJoyNode(Node):
    """MANUAL_SLAM-only Joy mapper; serial remains owned by UartBridgeNode."""

    def __init__(self) -> None:
        super().__init__("slam_manual_joy")
        self.declare_parameter("use_sim_time", False)
        self.declare_parameter("control_mode", "")
        self.declare_parameter("manual_slam_selected", False)
        self.declare_parameter("hardware_manifest", "")
        self.declare_parameter("profile_name", "pid4_experimental_1400cps")
        self.declare_parameter("owner_design_output_rpm", 172.0)
        self.declare_parameter("motor_to_gearbox_output_ratio", 21.3)
        self.declare_parameter("wheel_rpm_per_gearbox_output_rpm", 1.0)
        self.declare_parameter("experimental_max_wheel_target_cps", 1400.0)
        self.declare_parameter("joy_timeout_s", JOY_TIMEOUT_S)
        self.declare_parameter("joy_deadzone_radius", 0.12)
        self.declare_parameter("joy_full_command_radius", 0.20)
        self.declare_parameter("sideways_fade_start_deg", 75.0)

        self._last_joy_received = None
        self._last_timeout_stop = object()
        self._publisher_conflict = False
        self._conflict_stop_published = False
        self._steady = time.monotonic
        self._joy_timeout = float(self.get_parameter("joy_timeout_s").value)
        if not math.isfinite(self._joy_timeout) or self._joy_timeout <= 0.0:
            raise ValueError("joy_timeout_s must be finite and positive")

        profile = None
        self._manual_slam_selected = (
            str(self.get_parameter("control_mode").value) == "MANUAL_SLAM"
            and self.get_parameter("manual_slam_selected").value is True
        )
        manifest_path = str(self.get_parameter("hardware_manifest").value)
        if manifest_path.strip():
            try:
                manifest = load_manifest(manifest_path)
                geometry = wheel_geometry(manifest)
                ratios = manual_slam_drive_ratios(manifest)
                configured_ratios = (
                    float(self.get_parameter("motor_to_gearbox_output_ratio").value),
                    float(self.get_parameter(
                        "wheel_rpm_per_gearbox_output_rpm").value),
                )
                manifest_ratios = (
                    ratios["motor_to_gearbox_output_ratio"],
                    ratios["wheel_rpm_per_gearbox_output_rpm"],
                )
                if configured_ratios != manifest_ratios:
                    raise ValueError("MANUAL_SLAM ratios disagree with hardware manifest")
                profile = SlamBenchMotionProfile(
                    wheel_diameter_m=geometry["wheel_diameter_m"],
                    wheelbase_m=geometry["wheelbase_m"],
                    track_m=geometry["track_m"],
                    ticks_per_wheel_revolution=geometry["ticks_per_wheel_revolution"],
                    profile_name=str(self.get_parameter("profile_name").value),
                    owner_design_output_rpm=float(
                        self.get_parameter("owner_design_output_rpm").value),
                    motor_to_gearbox_output_ratio=ratios[
                        "motor_to_gearbox_output_ratio"],
                    wheel_rpm_per_gearbox_output_rpm=ratios[
                        "wheel_rpm_per_gearbox_output_rpm"],
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

        self._profile_valid = profile is not None and profile.valid
        self._manual_valid = self._manual_slam_selected and self._profile_valid
        self._teleop = SlamManualTeleop(profile, motion_enabled=False)
        self._cmd_pub = self.create_publisher(
            Twist, CMD_VEL_TOPIC, _reliable_volatile(1))
        self.create_subscription(
            Joy, "/joy", self._on_joy,
            QoSProfile(history=HistoryPolicy.KEEP_LAST, depth=10,
                       reliability=ReliabilityPolicy.BEST_EFFORT,
                       durability=DurabilityPolicy.VOLATILE),
        )
        self.create_service(Trigger, "/manual_slam/enable", self._on_enable)
        self.create_service(Trigger, "/manual_slam/disarm", self._on_disarm)
        self.create_timer(min(0.05, self._joy_timeout / 2.0), self._watchdog_tick)
        if not self._manual_valid:
            self.get_logger().error(
                "MANUAL_SLAM chưa được chọn hoặc manifest/profile không hợp lệ; mapper disarmed")

    @staticmethod
    def _stamp_ns(stamp) -> int:
        return int(stamp.sec) * 1_000_000_000 + int(stamp.nanosec)

    @staticmethod
    def _valid_joy(message: Joy) -> bool:
        try:
            axes = tuple(float(value) for value in message.axes[:2])
            buttons = tuple(message.buttons[:6])
            button_count = len(message.buttons)
        except (AttributeError, IndexError, TypeError, ValueError, OverflowError):
            return False
        return bool(
            len(axes) == 2 and button_count >= 6 and len(buttons) == 6
            and all(math.isfinite(value) and -1.0 <= value <= 1.0 for value in axes)
            and all(type(value) is int and value in (0, 1) for value in buttons)
        )

    def _publish(self, command) -> None:
        message = Twist()
        if not self._publisher_conflict:
            message.linear.x = command.vx
            message.linear.y = command.vy
            message.angular.z = command.wz
        self._cmd_pub.publish(message)

    def _has_unexpected_cmd_vel_publisher(self) -> bool:
        try:
            endpoints = self.get_publishers_info_by_topic(CMD_VEL_TOPIC)
        except Exception:
            return True
        return any(
            endpoint.node_name != self.get_name()
            or endpoint.node_namespace != self.get_namespace()
            for endpoint in endpoints
        )

    def _on_enable(self, _request: Trigger.Request,
                   response: Trigger.Response) -> Trigger.Response:
        if not self._manual_valid:
            response.success = False
            response.message = "MANUAL_SLAM_NOT_SELECTED_OR_PROFILE_INVALID"
            return response
        if self._has_unexpected_cmd_vel_publisher():
            self._publisher_conflict = True
            self._teleop.disconnected()
            response.success = False
            response.message = "UNEXPECTED_CMD_VEL_PUBLISHER_DETECTED"
            return response
        self._publisher_conflict = False
        response.success = self._teleop.request_enable()
        response.message = ("WAITING_FOR_FRESH_NEUTRAL_JOY"
                            if response.success else "MAPPER_PROFILE_INVALID")
        return response

    def _on_disarm(self, _request: Trigger.Request,
                   response: Trigger.Response) -> Trigger.Response:
        self._teleop.request_disarm()
        self._publish(BodyCommand())
        response.success = True
        response.message = "SOFTWARE_DISARMED_NOT_PHYSICAL_ESTOP"
        return response

    def _on_joy(self, message: Joy) -> None:
        now_ns = self.get_clock().now().nanoseconds
        joy_ns = self._stamp_ns(message.header.stamp)
        fresh = joy_ns > 0 and 0 <= now_ns - joy_ns <= int(self._joy_timeout * 1e9)
        received = self._steady()
        self._last_joy_received = received
        self._last_timeout_stop = None
        if (not self._manual_valid or self._publisher_conflict
                or not fresh or not self._valid_joy(message)):
            self._teleop.disconnected()
            self._publish(BodyCommand())
            return
        command = self._teleop.update(message.axes, message.buttons)
        self._publish(command)

    def _watchdog_tick(self) -> None:
        now = self._steady()
        conflict = self._has_unexpected_cmd_vel_publisher()
        if conflict:
            self._publisher_conflict = True
            self._teleop.disconnected()
            if not self._conflict_stop_published:
                self._publish(BodyCommand())
                self._conflict_stop_published = True
            self.get_logger().error(
                "Phát hiện publisher /cmd_vel khác; mapper disarmed; graph discovery không chứng minh độc quyền")
            return
        self._conflict_stop_published = False
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
