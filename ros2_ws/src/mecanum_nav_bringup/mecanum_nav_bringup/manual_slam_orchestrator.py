"""Terminal-2 readiness, lifecycle, rearm and Joy-enable coordinator.

This node never publishes movement. It calls the existing rearm/enable services
only after observing live sensor, Joy, session and lifecycle state.
"""
from __future__ import annotations

import time
import signal
import math

import rclpy
from lifecycle_msgs.msg import State, Transition
from lifecycle_msgs.srv import ChangeState, GetState
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from rclpy.signals import SignalHandlerOptions
from sensor_msgs.msg import Imu, Joy, LaserScan
from std_srvs.srv import Trigger

from mecanum_nav_rl_interfaces.msg import Heartbeat, SafetyLifecycleState

from .manual_slam_orchestration import (
    DEFAULT_IMU_TOPIC, JOY_DEADZONE_RADIUS, Readiness,
    fresh_neutral_after_enable, joy_is_neutral,
    joy_sample_valid, missing_dependencies,
    run_shutdown_sequence, run_startup_sequence, runtime_missing_dependencies,
)


class ManualSlamOrchestrator(Node):
    def __init__(self) -> None:
        super().__init__("manual_slam_orchestrator")
        self.declare_parameter("startup_timeout_s", 90.0)
        self.declare_parameter("dependency_timeout_s", 30.0)
        self.declare_parameter("service_timeout_s", 10.0)
        self.declare_parameter("slam_state_check_period_s", 0.5)
        self.declare_parameter("imu_topic", DEFAULT_IMU_TOPIC)
        self.declare_parameter("joy_max_age_s", 0.25)
        self.declare_parameter("heartbeat_max_age_s", 0.6)
        self._startup_timeout = float(self.get_parameter("startup_timeout_s").value)
        self._dependency_timeout = float(self.get_parameter("dependency_timeout_s").value)
        self._service_timeout = float(self.get_parameter("service_timeout_s").value)
        self._slam_state_check_period = float(
            self.get_parameter("slam_state_check_period_s").value)
        self._imu_topic = str(self.get_parameter("imu_topic").value).strip()
        self._joy_deadzone = JOY_DEADZONE_RADIUS
        self._joy_max_age = float(self.get_parameter("joy_max_age_s").value)
        self._heartbeat_max_age = float(self.get_parameter("heartbeat_max_age_s").value)
        self._last_joy_valid = False
        self._last_scan = self._last_imu = self._last_joy = self._last_heartbeat = None
        self._last_safety = None
        self._joy_neutral = False
        self._heartbeat_ok = False
        self._heartbeat_active_estop = False
        self._safety = None
        self._scan_sub = self.create_subscription(
            LaserScan, "/scan", self._on_scan, qos_profile_sensor_data)
        self._imu_sub = self.create_subscription(
            Imu, self._imu_topic, self._on_imu, qos_profile_sensor_data)
        self._joy_sub = self.create_subscription(
            Joy, "/joy", self._on_joy, qos_profile_sensor_data)
        self._heartbeat_sub = self.create_subscription(
            Heartbeat, "/mcu/heartbeat", self._on_heartbeat, 10)
        self._safety_sub = self.create_subscription(
            SafetyLifecycleState, "/mecanum/safety_lifecycle_state", self._on_safety, 10)
        self._rearm = self.create_client(Trigger, "/mecanum/safety/rearm")
        self._enable = self.create_client(Trigger, "/manual_slam/enable")
        self._disarm = self.create_client(Trigger, "/manual_slam/disarm")
        self._slam_get = self.create_client(GetState, "/slam_toolbox/get_state")
        self._slam_change = self.create_client(ChangeState, "/slam_toolbox/change_state")
        self._safety_get = self.create_client(GetState, "/safety_lifecycle/get_state")
        self._safety_change = self.create_client(ChangeState, "/safety_lifecycle/change_state")
        timeouts = (self._startup_timeout, self._dependency_timeout, self._service_timeout,
                    self._slam_state_check_period, self._joy_max_age,
                    self._heartbeat_max_age)
        if not all(math.isfinite(value) and value > 0.0 for value in timeouts):
            raise ValueError(
                "startup/dependency/service/SLAM/Joy/heartbeat timeouts must be positive")
        if not self._imu_topic.startswith("/"):
            raise ValueError("imu_topic must be an absolute topic name")
        self._startup_deadline = self._now() + self._startup_timeout

    def _now(self) -> float:
        return time.monotonic()

    def _on_scan(self, _msg: LaserScan) -> None: self._last_scan = self._now()
    def _on_imu(self, _msg: Imu) -> None: self._last_imu = self._now()

    def _on_joy(self, msg: Joy) -> None:
        now = self._now()
        self._last_joy = now
        stamp_ns = int(msg.header.stamp.sec) * 1_000_000_000 + int(msg.header.stamp.nanosec)
        age_ns = self.get_clock().now().nanoseconds - stamp_ns
        self._last_joy_valid = bool(
            stamp_ns > 0 and 0 <= age_ns <= int(self._joy_max_age * 1e9)
            and joy_sample_valid(msg.axes, msg.buttons))
        self._joy_neutral = bool(self._last_joy_valid and joy_is_neutral(
            msg.axes, msg.buttons, self._joy_deadzone))

    def _on_heartbeat(self, msg: Heartbeat) -> None:
        self._last_heartbeat = self._now()
        self._heartbeat_ok = (msg.source == Heartbeat.SOURCE_MCU and msg.healthy
                              and msg.fault_bits == 0)
        self._heartbeat_active_estop = msg.estop_aux_state == Heartbeat.ESTOP_AUX_ACTIVE

    def _on_safety(self, msg: SafetyLifecycleState) -> None:
        self._safety = msg
        self._last_safety = self._now()

    def _spin(self, duration: float = 0.05) -> None:
        rclpy.spin_once(self, timeout_sec=duration)

    def _wait_future(self, future, label: str, deadline: float):
        while rclpy.ok() and not future.done() and self._now() < deadline:
            self._spin()
        if not future.done():
            raise RuntimeError(f"timeout waiting for {label} response")
        exc = future.exception()
        if exc:
            raise RuntimeError(f"{label} call failed: {exc}") from exc
        return future.result()

    def _service_ready(self, client, label: str, deadline: float) -> None:
        self.get_logger().info(f"waiting for service {label}")
        while rclpy.ok() and self._now() < deadline:
            if client.wait_for_service(timeout_sec=0.1):
                return
        raise RuntimeError(f"timeout: service {label} unavailable")

    def _call_trigger(self, client, label: str, deadline: float):
        self._service_ready(client, label, deadline)
        response = self._wait_future(client.call_async(Trigger.Request()), label, deadline)
        if not response.success:
            raise RuntimeError(f"{label} rejected request: {response.message}")
        self.get_logger().info(f"{label}: {response.message}")
        return response

    def _ensure_active(self, name: str, get_client, change_client) -> None:
        self._service_ready(
            get_client, f"{name}/get_state", self._step_deadline(self._service_timeout))
        self._service_ready(
            change_client, f"{name}/change_state", self._step_deadline(self._service_timeout))
        result = self._wait_future(get_client.call_async(GetState.Request()),
                                   f"{name}/get_state",
                                   self._step_deadline(self._service_timeout))
        current = result.current_state.id
        if current == State.PRIMARY_STATE_UNCONFIGURED:
            self.get_logger().info(f"configuring lifecycle node {name}")
            request = ChangeState.Request()
            request.transition.id = Transition.TRANSITION_CONFIGURE
            response = self._wait_future(change_client.call_async(request),
                                        f"{name} configure",
                                        self._step_deadline(self._service_timeout))
            if not response.success:
                raise RuntimeError(f"{name} configure transition rejected")
            result = self._wait_future(
                get_client.call_async(GetState.Request()), f"{name}/get_state after configure",
                self._step_deadline(self._service_timeout))
            current = result.current_state.id
            if current != State.PRIMARY_STATE_INACTIVE:
                raise RuntimeError(
                    f"{name} did not reach inactive after configure; state id {current}")
        if current == State.PRIMARY_STATE_INACTIVE:
            self.get_logger().info(f"activating lifecycle node {name}")
            request = ChangeState.Request()
            request.transition.id = Transition.TRANSITION_ACTIVATE
            response = self._wait_future(change_client.call_async(request),
                                        f"{name} activate",
                                        self._step_deadline(self._service_timeout))
            if not response.success:
                raise RuntimeError(f"{name} activate transition rejected")
            result = self._wait_future(
                get_client.call_async(GetState.Request()), f"{name}/get_state after activate",
                self._step_deadline(self._service_timeout))
            current = result.current_state.id
        if current != State.PRIMARY_STATE_ACTIVE:
            raise RuntimeError(f"{name} lifecycle is state id {current}; expected active")
        self.get_logger().info(f"{name} lifecycle is active")

    def ensure_slam_active(self) -> None:
        self._ensure_active("/slam_toolbox", self._slam_get, self._slam_change)

    def ensure_safety_active(self) -> None:
        self._ensure_active("/safety_lifecycle", self._safety_get, self._safety_change)

    def _assert_slam_toolbox_active(self) -> None:
        deadline = self._now() + self._service_timeout
        if not self._slam_get.service_is_ready():
            self._service_ready(self._slam_get, "/slam_toolbox/get_state", deadline)
        result = self._wait_future(
            self._slam_get.call_async(GetState.Request()),
            "/slam_toolbox/get_state during mapping", deadline)
        state_id = result.current_state.id
        if state_id != State.PRIMARY_STATE_ACTIVE:
            raise RuntimeError(
                "/slam_toolbox lifecycle left ACTIVE while mapping "
                f"(state id {state_id}, expected {State.PRIMARY_STATE_ACTIVE})")

    def _step_deadline(self, timeout: float) -> float:
        return min(self._startup_deadline, self._now() + timeout)

    def wait_hardware_ready(self) -> None:
        self._wait_readiness("hardware readiness", self._step_deadline(self._dependency_timeout))

    def wait_fresh_neutral_joy(self) -> None:
        self._fresh_neutral_joy(self._step_deadline(self._dependency_timeout))

    def rearm_safety(self) -> None:
        self._call_trigger(
            self._rearm, "/mecanum/safety/rearm", self._step_deadline(self._service_timeout))

    def wait_motion_permission(self) -> None:
        self._wait_readiness(
            "safety rearm", self._step_deadline(self._dependency_timeout), motion=True)

    def enable_mapper(self) -> None:
        self._joy_sequence_before_enable = self._last_joy
        self._call_trigger(
            self._enable, "/manual_slam/enable", self._step_deadline(self._service_timeout))

    def wait_post_enable_joy(self) -> None:
        before = self._joy_sequence_before_enable
        deadline = self._step_deadline(self._dependency_timeout)
        self.get_logger().info("waiting for a new /joy sample after mapper enable")
        while rclpy.ok() and self._now() < deadline:
            self._spin()
            if fresh_neutral_after_enable(self._readiness(), self._last_joy, before):
                self.get_logger().info(
                    "MANUAL_SLAM enable confirmed by fresh neutral Joy; deliberate stick movement is required")
                return
        raise RuntimeError("timeout: no new /joy sample after mapper enable")

    def _readiness(self) -> Readiness:
        now = self._now()
        fresh = lambda stamp, age=1.0: stamp is not None and 0.0 <= now - stamp <= age
        safety_active = (fresh(self._last_safety, 0.6) and self._safety is not None and
                         self._safety.primary_state == SafetyLifecycleState.PRIMARY_ACTIVE)
        motion_permitted = bool(self._safety and self._safety.motion_permitted)
        hb_fresh = fresh(self._last_heartbeat, self._heartbeat_max_age)
        return Readiness(fresh(self._last_scan), fresh(self._last_imu),
                         fresh(self._last_joy, self._joy_max_age) and self._last_joy_valid,
                         self._joy_neutral, hb_fresh,
                         bool(hb_fresh and self._heartbeat_ok and not self._heartbeat_active_estop),
                         safety_active, motion_permitted)

    def _wait_readiness(self, label: str, deadline: float, *, motion: bool = False) -> None:
        last_report = 0.0
        while rclpy.ok() and self._now() < deadline:
            self._spin()
            state = self._readiness()
            missing = missing_dependencies(
                state, require_motion_permitted=motion, imu_topic=self._imu_topic)
            if not missing:
                return
            if self._now() - last_report >= 3.0:
                self.get_logger().info(f"{label}: waiting for {', '.join(missing)}")
                last_report = self._now()
        missing = missing_dependencies(
            self._readiness(), require_motion_permitted=motion, imu_topic=self._imu_topic)
        raise RuntimeError(f"timeout during {label}; not ready: {', '.join(missing)}")

    def _fresh_neutral_joy(self, deadline: float) -> None:
        while rclpy.ok() and self._now() < deadline:
            self._spin()
            if self._readiness().joy_fresh and self._joy_neutral:
                return
        raise RuntimeError("timeout waiting for a new neutral /joy sample; no synthetic Joy is sent")

    def run_sequence(self) -> None:
        deadline = self._now() + self._startup_timeout
        self._startup_deadline = deadline
        self.get_logger().info(
            "MANUAL_SLAM mapping startup: waiting for SLAM lifecycle, safety lifecycle, "
            "fresh sensors, neutral Joy and healthy UART/session heartbeat")
        run_startup_sequence(self)
        self.get_logger().info("startup gates passed; no nonzero movement command was issued")

    def monitor_ready(self) -> None:
        self.get_logger().info(
            "monitoring fresh sensor, Joy, safety, UART/session and SLAM lifecycle state")
        next_slam_check = self._now()
        while rclpy.ok():
            self._spin()
            now = self._now()
            if now >= next_slam_check:
                self._assert_slam_toolbox_active()
                next_slam_check = now + self._slam_state_check_period
            missing = runtime_missing_dependencies(
                self._readiness(), imu_topic=self._imu_topic)
            if missing:
                raise RuntimeError(f"runtime dependency lost: {', '.join(missing)}")

    def disarm_mapper(self) -> None:
        try:
            self._call_trigger(self._disarm, "/manual_slam/disarm", self._now() + 2.0)
        except Exception as error:  # cleanup must still let launch shut down
            self.get_logger().error(f"software disarm on shutdown failed: {error}")


def _terminate_gracefully(signum, _frame) -> None:
    raise SystemExit(128 + signum)


def main(args=None) -> None:
    # Keep Python's SIGINT/SIGTERM path so finally can request software disarm
    # before the ROS context is shut down by rclpy's default signal handler.
    rclpy.init(args=args, signal_handler_options=SignalHandlerOptions.NO)
    signal.signal(signal.SIGTERM, _terminate_gracefully)
    node = None
    try:
        node = ManualSlamOrchestrator()
        node.run_sequence()
        node.monitor_ready()
    except Exception as error:
        if node is not None:
            node.get_logger().fatal(f"MANUAL_SLAM orchestration failed; not ready: {error}")
        raise SystemExit(2) from error
    finally:
        if node is not None:
            run_shutdown_sequence(node)
            node.destroy_node()
        rclpy.shutdown()
