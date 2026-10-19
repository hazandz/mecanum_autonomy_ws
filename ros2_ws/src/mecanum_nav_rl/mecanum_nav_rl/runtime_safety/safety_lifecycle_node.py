"""Lifecycle barrier publisher; owns all episode/reset/runtime identity."""
from __future__ import annotations

from lifecycle_msgs.msg import State
from rclpy.lifecycle import LifecycleNode, TransitionCallbackReturn
from mecanum_nav_rl_interfaces.msg import SafetyLifecycleState

from mecanum_nav_rl.runtime_safety.safety_contract import SafetyLifecycleCore


class SafetyLifecycleNode(LifecycleNode):
    def __init__(self) -> None:
        super().__init__("safety_lifecycle")
        self._core = SafetyLifecycleCore()
        self._publisher = self.create_lifecycle_publisher(
            SafetyLifecycleState, "/mecanum/safety_lifecycle_state", 10
        )
        self._timer = self.create_timer(0.2, self._publish_barrier)
        self.trigger_configure()
        self.trigger_activate()

    def on_configure(self, _state: State) -> TransitionCallbackReturn:
        self._core.configure(self.get_clock().now().nanoseconds)
        return TransitionCallbackReturn.SUCCESS

    def on_activate(self, _state: State) -> TransitionCallbackReturn:
        self._core.activate(self.get_clock().now().nanoseconds)
        return TransitionCallbackReturn.SUCCESS

    def on_deactivate(self, _state: State) -> TransitionCallbackReturn:
        self._core.mark_non_ready("LIFECYCLE_DEACTIVATED", self.get_clock().now().nanoseconds)
        return TransitionCallbackReturn.SUCCESS

    def on_cleanup(self, _state: State) -> TransitionCallbackReturn:
        self._core.mark_non_ready("LIFECYCLE_CLEANUP", self.get_clock().now().nanoseconds)
        return TransitionCallbackReturn.SUCCESS

    def on_error(self, _state: State) -> TransitionCallbackReturn:
        self._core.fault("LIFECYCLE_TRANSITION_ERROR", self.get_clock().now().nanoseconds)
        return TransitionCallbackReturn.SUCCESS

    def _publish_barrier(self) -> None:
        identity = self._core.refresh(self.get_clock().now().nanoseconds)
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
