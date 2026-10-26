"""Adapter ROS 2 cho session UART hiện có; không sở hữu motor hoặc TF."""
from __future__ import annotations

import math
import time
from dataclasses import replace

from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
import rclpy
from rclpy.executors import SingleThreadedExecutor
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from std_srvs.srv import Trigger
from mecanum_nav_rl_interfaces.msg import Heartbeat, SafetyLifecycleState

from .bridge_session import BridgeSession, LifecycleIdentity, SessionState
from .hardware_config import (HardwareConfigError, communication_config_valid,
                              load_manifest, manifest_digest, wheel_geometry)
from .heartbeat import make_heartbeat
from .telemetry_state import telemetry_health
from .transport import SerialTransport
from .wheel_odometry import WheelOdometry


LIFECYCLE_TOPIC = "/mecanum/safety_lifecycle_state"
RESET_SERVICE = "/mecanum/safety/request_reset"
ODOMETRY_TOPIC = "/wheel/odometry_raw"
HEARTBEAT_TOPIC = "/mcu/heartbeat"
LIFECYCLE_TIMEOUT_S = 0.6


def lifecycle_identity(message, received_at: float, now: float,
                       timeout_s: float = LIFECYCLE_TIMEOUT_S) -> LifecycleIdentity:
    fresh = math.isfinite(now - received_at) and 0.0 <= now - received_at <= timeout_s
    ready = bool(message.primary_state == SafetyLifecycleState.PRIMARY_ACTIVE
                 and message.barrier_state == SafetyLifecycleState.BARRIER_READY
                 and message.motion_permitted)
    return LifecycleIdentity(int(message.reset_epoch), int(message.runtime_generation),
                             ready, int(message.sequence), fresh)


def lifecycle_qos_profile():
    return QoSProfile(history=HistoryPolicy.KEEP_LAST, depth=10,
                      reliability=ReliabilityPolicy.RELIABLE,
                      durability=DurabilityPolicy.VOLATILE)


class UartBridgeNode(Node):
    def __init__(self) -> None:
        super().__init__("mecanum_uart_bridge")
        self._transport = None
        self._session = None
        try:
            # Jazzy Node/TimeSource thường khai báo use_sim_time từ constructor.
            if not self.has_parameter("use_sim_time"):
                self.declare_parameter("use_sim_time", False)
            self.declare_parameter("serial_device", "")
            self.declare_parameter("hardware_manifest", "")
            self.declare_parameter("heartbeat_topic", HEARTBEAT_TOPIC)
            self.declare_parameter("lifecycle_timeout_s", LIFECYCLE_TIMEOUT_S)
            if bool(self.get_parameter("use_sim_time").value):
                raise ValueError("UART hardware adapter requires use_sim_time=false")
            port = str(self.get_parameter("serial_device").value)
            manifest_path = str(self.get_parameter("hardware_manifest").value)
            if not port.strip() or not manifest_path.strip():
                raise ValueError("serial_device and hardware_manifest must be supplied explicitly")
            try:
                lifecycle_timeout = float(self.get_parameter("lifecycle_timeout_s").value)
            except (TypeError, ValueError, OverflowError) as exc:
                raise ValueError("lifecycle_timeout_s must be finite and positive") from exc
            if not math.isfinite(lifecycle_timeout) or lifecycle_timeout <= 0.0:
                raise ValueError("lifecycle_timeout_s must be finite and positive")
            manifest = load_manifest(manifest_path)
            if not communication_config_valid(manifest):
                raise HardwareConfigError("manifest communication profile is unsupported")
            digest = manifest_digest(manifest)
            geometry = wheel_geometry(manifest)
            self._wheel_odom = WheelOdometry(
                geometry["wheel_diameter_m"], geometry["wheelbase_m"], geometry["track_m"],
                geometry["ticks_per_wheel_revolution"], tuple(geometry["encoder_tick_signs"]))
            self._steady_clock = time.monotonic
            self._lifecycle_timeout = lifecycle_timeout
            self._transport = SerialTransport(port)
            self._session = BridgeSession(self._transport, digest,
                                          monotonic=self._steady_clock)
            self._owner_message = None
            self._owner_received_at = 0.0
            self._lifecycle_baseline_observed = False
            self._last_generation = None
            self._reset_future = None
            self._latest_report = None
            self._heartbeat_sequence = 0
            qos = lifecycle_qos_profile()
            self._odom_pub = self.create_publisher(Odometry, ODOMETRY_TOPIC, 10)
            self._heartbeat_pub = self.create_publisher(
                Heartbeat, str(self.get_parameter("heartbeat_topic").value), 10)
            self.create_subscription(Twist, "/cmd_vel", self._on_cmd_vel, 10)
            self.create_subscription(SafetyLifecycleState, LIFECYCLE_TOPIC,
                                     self._on_lifecycle, qos)
            self._reset_client = self.create_client(Trigger, RESET_SERVICE)
            self.create_timer(0.005, self._io_tick)
            self.create_timer(0.1, self._heartbeat_tick)
        except Exception:
            if self._session is not None:
                self._session.shutdown()
            elif self._transport is not None:
                self._transport.close()
            super().destroy_node()
            raise

    def _on_lifecycle(self, message: SafetyLifecycleState) -> None:
        self._owner_message = message
        self._owner_received_at = self._steady_clock()
        generation = int(message.runtime_generation)
        if self._last_generation is not None and generation != self._last_generation:
            self._session.request_rearm_generation()
        self._last_generation = generation

    def _on_cmd_vel(self, message: Twist) -> None:
        self._session.receive_cmd_vel(message.linear.x, message.linear.y,
                                     message.angular.z, self._steady_clock())

    def _request_owner_reset(self) -> None:
        if not self._lifecycle_baseline_observed:
            return
        if self._reset_future is not None and not self._reset_future.done():
            return
        if self._reset_client.service_is_ready() and self._session.take_owner_reset_request():
            self._reset_future = self._reset_client.call_async(Trigger.Request())

    def _io_tick(self) -> None:
        now = self._steady_clock()
        if self._owner_message is not None:
            try:
                message = self._owner_message
                uint_fields = ((message.reset_epoch, 0xFFFFFFFF),
                               (message.runtime_generation, 0xFFFFFFFF),
                               (message.sequence, 0xFFFFFFFFFFFFFFFF))
                valid_states = (
                    message.primary_state in (
                        SafetyLifecycleState.PRIMARY_UNCONFIGURED,
                        SafetyLifecycleState.PRIMARY_INACTIVE,
                        SafetyLifecycleState.PRIMARY_ACTIVE),
                    message.barrier_state in (
                        SafetyLifecycleState.BARRIER_INIT,
                        SafetyLifecycleState.BARRIER_READY,
                        SafetyLifecycleState.BARRIER_NON_READY,
                        SafetyLifecycleState.BARRIER_FAULT),
                    type(message.motion_permitted) is bool,
                )
                if (any(type(value) is not int or not 0 <= value <= maximum
                        for value, maximum in uint_fields) or not all(valid_states)):
                    raise ValueError("lifecycle snapshot fields are invalid")
                identity = lifecycle_identity(self._owner_message, self._owner_received_at, now,
                                              self._lifecycle_timeout)
                observed = self._session.observe_lifecycle_snapshot(identity)
                self._lifecycle_baseline_observed = bool(identity.fresh and observed)
            except (AttributeError, TypeError, ValueError, OverflowError):
                self._lifecycle_baseline_observed = False
                known_identity = self._session._identity
                if known_identity is not None:
                    self._session.observe_lifecycle_snapshot(
                        replace(known_identity, fresh=False))
        self._request_owner_reset()
        self._session.io_once()
        for _ in range(8):
            report = self._session.take_accepted_telemetry()
            if report is None:
                break
            self._latest_report = report
            continuity = self._session.continuity_reset
            if self._session.state == SessionState.ACTIVE and self._wheel_odom is not None:
                stamp = self.get_clock().now().to_msg()
                stamp_ns = int(stamp.sec) * 1_000_000_000 + int(stamp.nanosec)
                sample = self._wheel_odom.update(report.packet, stamp_ns, continuity)
                if sample is not None:
                    self._publish_odometry(sample)

    def _publish_odometry(self, sample) -> None:
        msg = Odometry()
        msg.header.stamp.sec = sample.stamp_ns // 1_000_000_000
        msg.header.stamp.nanosec = sample.stamp_ns % 1_000_000_000
        msg.header.frame_id = "odom"
        msg.child_frame_id = "base_link"
        msg.pose.pose.position.x = sample.x
        msg.pose.pose.position.y = sample.y
        msg.pose.pose.orientation.z = math.sin(sample.yaw / 2.0)
        msg.pose.pose.orientation.w = math.cos(sample.yaw / 2.0)
        msg.twist.twist.linear.x = sample.vx
        msg.twist.twist.linear.y = sample.vy
        msg.twist.twist.angular.z = sample.wz
        msg.pose.covariance = list(sample.pose_covariance)
        msg.twist.covariance = list(sample.twist_covariance)
        self._odom_pub.publish(msg)

    def _heartbeat_tick(self) -> None:
        now = self._steady_clock()
        report = self._latest_report
        fresh = bool(report is not None and now >= report.pi_receive_time
                     and now - report.pi_receive_time < 0.2)
        identity = self._session._identity
        owner_epoch = None if identity is None else identity.reset_epoch
        if report is not None and (owner_epoch is None
                                   or report.packet.reset_epoch != owner_epoch):
            report = None
            fresh = False
        health = telemetry_health(self._session.state == SessionState.ACTIVE, fresh, report)
        state = make_heartbeat(self._heartbeat_sequence,
            report.packet.reset_epoch if report is not None else (owner_epoch or 0),
            health.active, health.fresh, report if health.fresh else None,
            self._session.transport_healthy)
        message = Heartbeat()
        stamp = self.get_clock().now().to_msg()
        message.header.stamp = stamp
        message.source = Heartbeat.SOURCE_MCU
        message.sequence = state.sequence
        message.reset_epoch = state.reset_epoch
        message.healthy = state.healthy
        message.fault_bits = state.fault_bits
        message.detail = state.detail
        self._heartbeat_pub.publish(message)
        self._heartbeat_sequence = (self._heartbeat_sequence + 1) & 0xFFFFFFFF

    def destroy_node(self):
        self._session.shutdown()
        return super().destroy_node()


def main(args=None) -> None:
    rclpy.init(args=args)
    node = None
    executor = SingleThreadedExecutor()
    try:
        node = UartBridgeNode()
        executor.add_node(node)
        executor.spin()
    finally:
        if node is not None:
            executor.remove_node(node)
            node.destroy_node()
        executor.shutdown()
        rclpy.shutdown()
