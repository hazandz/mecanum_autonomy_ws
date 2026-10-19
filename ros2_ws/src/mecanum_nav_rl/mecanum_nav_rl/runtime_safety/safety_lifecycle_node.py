"""Lifecycle barrier publisher with explicit reset and rearm services."""
from __future__ import annotations

from lifecycle_msgs.msg import State
from rclpy.lifecycle import LifecycleNode, TransitionCallbackReturn
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from std_srvs.srv import Trigger
from mecanum_nav_rl_interfaces.msg import SafetyLifecycleState

from mecanum_nav_rl.runtime_safety.safety_contract import SafetyLifecycleCore


class SafetyLifecycleNode(LifecycleNode):
    def __init__(self) -> None:
        super().__init__("safety_lifecycle")
        self._core = SafetyLifecycleCore()
        state_qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST, depth=10,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.VOLATILE,
        )
        self._publisher = self.create_lifecycle_publisher(
            SafetyLifecycleState, "/mecanum/safety_lifecycle_state", state_qos
        )
        self._timer = self.create_timer(0.2, self._publish_barrier)
        self._reset_service = self.create_service(
            Trigger, "/mecanum/safety/request_reset", self._request_reset
        )
        self._rearm_service = self.create_service(
            Trigger, "/mecanum/safety/rearm", self._request_rearm
        )

    def on_configure(self, state: State) -> TransitionCallbackReturn:
        self._core.configure(self.get_clock().now().nanoseconds)
        result = super().on_configure(state)
        if result != TransitionCallbackReturn.SUCCESS:
            self._core.fault("LIFECYCLE_CONFIGURE_PARENT_FAILED", self.get_clock().now().nanoseconds)
        return result

    def on_activate(self, state: State) -> TransitionCallbackReturn:
        self._core.activate(self.get_clock().now().nanoseconds)
        result = super().on_activate(state)
        if result == TransitionCallbackReturn.SUCCESS:
            self._publish_current()
        else:
            self._core.fault("LIFECYCLE_ACTIVATE_PARENT_FAILED", self.get_clock().now().nanoseconds)
        return result

    def on_deactivate(self, state: State) -> TransitionCallbackReturn:
        self._core.deactivate(self.get_clock().now().nanoseconds)
        # This callback runs while the lifecycle publisher is still active.
        self._publish_current()
        return super().on_deactivate(state)

    def on_cleanup(self, state: State) -> TransitionCallbackReturn:
        self._core.cleanup(self.get_clock().now().nanoseconds)
        return super().on_cleanup(state)

    def on_error(self, state: State) -> TransitionCallbackReturn:
        self._core.fault("LIFECYCLE_TRANSITION_ERROR", self.get_clock().now().nanoseconds)
        self._publish_current()
        return super().on_error(state)

    def _request_reset(self, _request: Trigger.Request, response: Trigger.Response) -> Trigger.Response:
        identity = self._core.begin_reset(self.get_clock().now().nanoseconds)
        response.success = not identity.motion_permitted
        response.message = identity.reason
        self._publish_current()
        return response

    def _request_rearm(self, _request: Trigger.Request, response: Trigger.Response) -> Trigger.Response:
        try:
            identity = self._core.rearm(self.get_clock().now().nanoseconds)
        except ValueError as error:
            response.success = False
            response.message = str(error)
            return response
        response.success = identity.motion_permitted
        response.message = identity.reason
        self._publish_current()
        return response

    def _publish_barrier(self) -> None:
        self._core.refresh(self.get_clock().now().nanoseconds)
        self._publish_current()

    def _publish_current(self) -> None:
        if not self._publisher.is_activated:
            return
        identity = self._core.snapshot()
        msg = SafetyLifecycleState()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = "base_link"
        msg.episode_generation = identity.episode_generation
        msg.reset_epoch = identity.reset_epoch
        msg.runtime_generation = identity.runtime_generation
        msg.sequence = identity.sequence
        msg.primary_state = {
            "Unconfigured": SafetyLifecycleState.PRIMARY_UNCONFIGURED,
            "Inactive": SafetyLifecycleState.PRIMARY_INACTIVE,
            "Active": SafetyLifecycleState.PRIMARY_ACTIVE,
        }[identity.primary_state.value]
        msg.barrier_state = {
            "INIT": SafetyLifecycleState.BARRIER_INIT,
            "READY": SafetyLifecycleState.BARRIER_READY,
            "NON_READY": SafetyLifecycleState.BARRIER_NON_READY,
            "FAULT": SafetyLifecycleState.BARRIER_FAULT,
        }[identity.barrier_state.value]
        msg.barrier_stamp.sec = identity.barrier_ros_time_ns // 1_000_000_000
        msg.barrier_stamp.nanosec = identity.barrier_ros_time_ns % 1_000_000_000
        msg.motion_permitted = identity.motion_permitted
        msg.reason = identity.reason
        self._publisher.publish(msg)


def main(args: list[str] | None = None) -> None:
    import rclpy
    rclpy.init(args=args)
    node = SafetyLifecycleNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
