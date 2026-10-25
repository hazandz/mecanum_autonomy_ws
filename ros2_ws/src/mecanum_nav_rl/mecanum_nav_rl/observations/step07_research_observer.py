"""In-process ROS observer for the simplified Step 7 runner.

ROS dependencies are imported only when constructing the runtime adapter so
the acceptance core and its offline tests remain usable without a ROS graph.
"""

from __future__ import annotations

from collections import deque
import math
import threading
from typing import Any

from .step07_research_acceptance import ClockRollbackGuard, Context, StampedFact


class Step07ResearchObserver:
    """ROS subscriptions, exact-time TF lookup, and direct Nav2 action clients."""

    def __init__(self, *, config_hash: str, node_name: str = "step07_research_runner") -> None:
        import rclpy
        from rclpy.action import ActionClient
        from rclpy.duration import Duration
        from rclpy.node import Node
        from rclpy.qos import (DurabilityPolicy, HistoryPolicy, QoSProfile,
                               ReliabilityPolicy)
        from sensor_msgs.msg import LaserScan, Imu
        from nav_msgs.msg import Odometry, Path
        from geometry_msgs.msg import PoseWithCovarianceStamped
        from geometry_msgs.msg import Twist
        from rosgraph_msgs.msg import Clock
        from nav2_msgs.action import ComputePathToPose, NavigateToPose
        from tf2_ros import Buffer, TransformListener
        from mecanum_nav_rl_interfaces.msg import (SafetyLifecycleState,
            FinalIssuedCommandReceipt, CommandEnvelope, SafetyState)
        from std_srvs.srv import Trigger
        from nav_msgs.msg import OccupancyGrid
        from lifecycle_msgs.srv import GetState

        self._rclpy = rclpy
        self._Duration = Duration
        self._ComputePathToPose = ComputePathToPose
        self._NavigateToPose = NavigateToPose
        self._Trigger = Trigger
        self._GetState = GetState
        self._lock = threading.RLock()
        self._config_hash = config_hash
        self.context: Context | None = None
        self.barrier_stamp_ns = 0
        self.barrier_sequence = 0
        self.clock_ns = 0
        self.clock_advance_count = 0
        self._last_clock_ns = 0
        self.scans: deque[StampedFact] = deque(maxlen=64)
        self.odometry: deque[StampedFact] = deque(maxlen=64)
        self.wheel: deque[StampedFact] = deque(maxlen=64)
        self.imu: deque[StampedFact] = deque(maxlen=64)
        self.receipts: deque[StampedFact] = deque(maxlen=64)
        self.nav2_candidates: deque[StampedFact] = deque(maxlen=64)
        self.accepted_envelopes: deque[StampedFact] = deque(maxlen=64)
        self.safety_states: deque[StampedFact] = deque(maxlen=64)
        self.lifecycle: StampedFact | None = None
        self.localization: deque[dict[str, Any]] = deque(maxlen=64)
        self.clock_rollback = False
        self.clock_guard = ClockRollbackGuard((self._clear_buffers,))
        self.path_result: Any = None
        self.action_events: deque[dict[str, Any]] = deque(maxlen=128)
        self.map_message: Any = None
        self.node = Node(node_name, parameter_overrides=[])
        self.node.set_parameters([rclpy.parameter.Parameter("use_sim_time", value=True)])
        self.tf_buffer = Buffer(node=self.node)
        self.tf_listener = TransformListener(self.tf_buffer, self.node, spin_thread=False)
        self.compute_path_client = ActionClient(self.node, ComputePathToPose, "/compute_path_to_pose")
        self.navigate_client = ActionClient(self.node, NavigateToPose, "/navigate_to_pose")
        scan_qos = QoSProfile(history=HistoryPolicy.KEEP_LAST, depth=5,
                              reliability=ReliabilityPolicy.BEST_EFFORT,
                              durability=DurabilityPolicy.VOLATILE)
        reliable = QoSProfile(history=HistoryPolicy.KEEP_LAST, depth=10,
                              reliability=ReliabilityPolicy.RELIABLE,
                              durability=DurabilityPolicy.VOLATILE)
        receipt_qos = QoSProfile(history=HistoryPolicy.KEEP_LAST, depth=1,
                                 reliability=ReliabilityPolicy.RELIABLE,
                                 durability=DurabilityPolicy.TRANSIENT_LOCAL)
        self._subs = [
            self.node.create_subscription(Clock, "/clock", self._clock_cb, reliable),
            self.node.create_subscription(LaserScan, "/scan", self._scan, scan_qos),
            self.node.create_subscription(Odometry, "/wheel/odometry_raw", self._wheel, reliable),
            self.node.create_subscription(Imu, "/imu/data", self._imu, reliable),
            self.node.create_subscription(Odometry, "/odometry/filtered", self._odom, reliable),
            self.node.create_subscription(PoseWithCovarianceStamped, "/amcl_pose", self._amcl, reliable),
            self.node.create_subscription(SafetyLifecycleState, "/mecanum/safety_lifecycle_state", self._lifecycle_cb, reliable),
            self.node.create_subscription(FinalIssuedCommandReceipt, "/mecanum/final_issued_command", self._receipt, receipt_qos),
            self.node.create_subscription(Twist, "/mecanum/nav2_candidate_cmd", self._candidate, reliable),
            self.node.create_subscription(CommandEnvelope, "/mecanum/safety_accepted_cmd", self._accepted, reliable),
            self.node.create_subscription(SafetyState, "/mecanum/safety_state", self._safety, reliable),
            self.node.create_subscription(OccupancyGrid, "/map", self._map, reliable),
        ]
        self.safety_reset_client = self.node.create_client(Trigger, "/mecanum/safety/request_reset")
        self.lifecycle_clients = {name: self.node.create_client(GetState, f"/{name}/get_state")
                                  for name in ("map_server", "amcl", "planner_server",
                                               "controller_server", "behavior_server", "bt_navigator")}

    @staticmethod
    def _stamp(value: Any) -> int:
        return int(value.sec) * 1_000_000_000 + int(value.nanosec)

    def _receive_ns(self) -> int:
        return int(self.node.get_clock().now().nanoseconds)

    def _steady_ns(self) -> int:
        return int(self._rclpy.clock.Clock(clock_type=self._rclpy.clock.ClockType.STEADY_TIME).now().nanoseconds)

    def _fact(self, msg: Any, frame: str, value: Any, identity: tuple[Any, ...] = ()) -> StampedFact | None:
        stamp = self._stamp(msg.header.stamp)
        if stamp <= 0:
            return None
        context = self.context
        if context is None:
            return None
        return StampedFact(stamp, self._steady_ns(), frame, value, context, identity)

    def _clear_buffers(self) -> None:
        for stream in (self.scans, self.odometry, self.wheel, self.imu, self.receipts,
                       self.nav2_candidates, self.accepted_envelopes, self.safety_states,
                       self.localization):
            stream.clear()

    @staticmethod
    def _insert_ordered(stream: deque[StampedFact], fact: StampedFact) -> None:
        if any(old.stamp_ns == fact.stamp_ns and old.context == fact.context for old in stream):
            return
        items = list(stream)
        items.append(fact)
        items.sort(key=lambda item: item.stamp_ns)
        stream.clear()
        stream.extend(items[-stream.maxlen:])

    def _scan(self, msg: Any) -> None:
        fact = self._fact(msg, msg.header.frame_id, msg, (self._stamp(msg.header.stamp),))
        if fact:
            with self._lock: self._insert_ordered(self.scans, fact)

    def _clock_cb(self, msg: Any) -> None:
        self.clock_ns = self._stamp(msg.clock)
        if self.clock_ns > self._last_clock_ns:
            self.clock_advance_count += 1
        self._last_clock_ns = self.clock_ns
        if not self.clock_guard.observe(self.clock_ns) and self.clock_guard.failed:
            self.clock_rollback = True

    def _candidate(self, msg: Any) -> None:
        stamp = self._receive_ns()
        context = self.context
        if context is None:
            return
        value = (float(msg.linear.x), float(msg.linear.y), float(msg.angular.z))
        with self._lock:
            self._insert_ordered(self.nav2_candidates, StampedFact(stamp, self._steady_ns(), "base_link",
                value, context, (stamp, value)))

    def _accepted(self, msg: Any) -> None:
        stamp = self._stamp(msg.header.stamp)
        context = Context(int(msg.episode_generation), int(msg.reset_epoch),
                          int(msg.runtime_generation), self._config_hash)
        value = {"source": int(msg.source), "sequence": int(msg.sequence),
                 "source_instance_id": int(msg.source_instance_id),
                 "command": (float(msg.twist.linear.x), float(msg.twist.linear.y),
                             float(msg.twist.angular.z))}
        with self._lock:
            self._insert_ordered(self.accepted_envelopes, StampedFact(stamp, self._steady_ns(),
                msg.header.frame_id, value, context, (int(msg.source_instance_id), int(msg.sequence))))

    def _safety(self, msg: Any) -> None:
        stamp = self._stamp(msg.header.stamp)
        context = self.context
        if context is None or (context.reset_epoch, context.runtime_generation) != (
                int(msg.reset_epoch), int(msg.runtime_generation)):
            return
        value = {"state": int(msg.state), "active_command_source": int(msg.active_command_source),
                 "command_valid": bool(msg.command_valid), "motion_permitted": bool(msg.motion_permitted),
                 "final_command": (float(msg.final_command.linear.x), float(msg.final_command.linear.y),
                                   float(msg.final_command.angular.z)),
                 "intervention_reasons": tuple(msg.intervention_reasons)}
        with self._lock:
            self._insert_ordered(self.safety_states, StampedFact(stamp, self._steady_ns(), msg.header.frame_id,
                value, context, (stamp, int(msg.reset_epoch), int(msg.runtime_generation))))

    def _map(self, msg: Any) -> None:
        with self._lock:
            self.map_message = msg

    def _wheel(self, msg: Any) -> None:
        fact = self._fact(msg, msg.header.frame_id, msg, (self._stamp(msg.header.stamp),))
        if fact:
            with self._lock: self._insert_ordered(self.wheel, fact)

    def _imu(self, msg: Any) -> None:
        fact = self._fact(msg, msg.header.frame_id, msg, (self._stamp(msg.header.stamp),))
        if fact:
            with self._lock: self._insert_ordered(self.imu, fact)

    def _odom(self, msg: Any) -> None:
        fact = self._fact(msg, msg.child_frame_id, msg, (self._stamp(msg.header.stamp),))
        if fact:
            with self._lock: self._insert_ordered(self.odometry, fact)

    def _amcl(self, msg: Any) -> None:
        pose = msg.pose.pose
        q = pose.orientation
        yaw = math.atan2(2.0*(q.w*q.z + q.x*q.y), 1.0-2.0*(q.y*q.y+q.z*q.z))
        covariance = msg.pose.covariance
        with self._lock:
            item = {
                "stamp_ns": self._stamp(msg.header.stamp), "received_steady_ns": self._steady_ns(),
                "frame_id": msg.header.frame_id, "pose": (pose.position.x, pose.position.y, yaw),
                "covariance": (covariance[0], covariance[7], covariance[35]),
            }
            if not any(old["stamp_ns"] == item["stamp_ns"] for old in self.localization):
                items = list(self.localization); items.append(item)
                items.sort(key=lambda value: value["stamp_ns"])
                self.localization.clear(); self.localization.extend(items[-64:])

    def _lifecycle_cb(self, msg: Any) -> None:
        stamp = self._stamp(msg.header.stamp)
        barrier_stamp = self._stamp(msg.barrier_stamp)
        observed_context = Context(int(msg.episode_generation), int(msg.reset_epoch),
                                   int(msg.runtime_generation), self._config_hash)
        with self._lock:
            prior = self.lifecycle
            prior_value = prior.value if prior else None
            prior_context = prior.context if prior else None
            if (prior_value is not None and
                    (barrier_stamp != self.barrier_stamp
                     or (prior_value.barrier_state, msg.barrier_state) in ((1, 2), (2, 1), (1, 3), (3, 1)))):
                self.barrier_sequence += 1
            self.barrier_stamp_ns = barrier_stamp
            self.context = observed_context
            value = {"primary_state": int(msg.primary_state), "barrier_state": int(msg.barrier_state),
                     "motion_permitted": bool(msg.motion_permitted), "reason": str(msg.reason),
                     "sequence": int(msg.sequence), "barrier_stamp_ns": barrier_stamp}
            self.lifecycle = StampedFact(stamp, self._steady_ns(), msg.header.frame_id,
                                         value, observed_context, (int(msg.sequence),))
            if prior_context is not None and prior_context != observed_context:
                self.action_events.append({"event": "LIFECYCLE_CONTEXT_CHANGED", "stamp_ns": stamp})

    def _receipt(self, msg: Any) -> None:
        stamp = self._stamp(msg.header.stamp)
        if stamp <= 0:
            return
        context = Context(int(msg.episode_generation), int(msg.reset_epoch),
                          int(msg.runtime_generation), self._config_hash)
        command = (float(msg.final_command.linear.x), float(msg.final_command.linear.y),
                   float(msg.final_command.angular.z))
        fact = StampedFact(stamp, self._steady_ns(), msg.header.frame_id,
                           {"command": command, "source": int(msg.source),
                            "sequence": int(msg.sequence),
                            "final_publish_sequence": int(msg.final_publish_sequence),
                            "source_instance_id": int(msg.source_instance_id),
                            "publisher_instance": int(msg.final_publisher_instance_id)},
                           context, (int(msg.final_publisher_instance_id), int(msg.final_publish_sequence)))
        with self._lock: self._insert_ordered(self.receipts, fact)

    def lookup_local_reference_transform(self, odom_stamp_ns: int) -> Any:
        """Single exact-time lookup; caller polls this nonblocking for <=200 ms."""
        from rclpy.time import Time
        stamp = Time(nanoseconds=odom_stamp_ns, clock_type=self._rclpy.clock.ClockType.ROS_TIME)
        return self.tf_buffer.lookup_transform("base_link", "map", stamp, timeout=self._Duration(seconds=0.0))

    def lookup_transform(self, target_frame: str, source_frame: str, stamp_ns: int) -> Any:
        from rclpy.time import Time
        stamp = Time(nanoseconds=stamp_ns, clock_type=self._rclpy.clock.ClockType.ROS_TIME)
        return self.tf_buffer.lookup_transform(target_frame, source_frame, stamp,
                                               timeout=self._Duration(seconds=0.0))

    def wait_for_actions(self, timeout_sec: float) -> bool:
        return bool(self.compute_path_client.wait_for_server(timeout_sec=timeout_sec)
                    and self.navigate_client.wait_for_server(timeout_sec=timeout_sec))

    def graph_snapshot(self) -> dict[str, Any]:
        """Read the local ROS graph directly; no ros2 CLI daemon or shell query."""
        node_names = set(self.node.get_node_names())
        topics: dict[str, Any] = {}
        for name, types in self.node.get_topic_names_and_types():
            publishers = self.node.get_publishers_info_by_topic(name)
            subscriptions = self.node.get_subscriptions_info_by_topic(name)
            topics[name] = {
                "types": tuple(types),
                "publishers": tuple((p.node_name, p.node_namespace, p.topic_type,
                                      p.qos_profile.reliability, p.qos_profile.durability,
                                      p.qos_profile.depth) for p in publishers),
                "subscriptions": tuple((s.node_name, s.node_namespace, s.topic_type,
                                         s.qos_profile.reliability, s.qos_profile.durability,
                                         s.qos_profile.depth) for s in subscriptions),
            }
        return {"nodes": node_names, "topics": topics}

    def recording_ready(self, topic_names: tuple[str, ...]) -> tuple[bool, tuple[str, ...]]:
        graph = self.graph_snapshot()
        missing = []
        for topic in topic_names:
            endpoints = graph["topics"].get(topic, {}).get("subscriptions", ())
            if not any(str(endpoint[0]).startswith("rosbag2_recorder") for endpoint in endpoints):
                missing.append(topic)
        return not missing, tuple(missing)

    def request_safe_stop(self) -> Any:
        """Ask existing SafetyLifecycle to enter its non-ready/reset path."""
        request = self._Trigger.Request()
        return self.safety_reset_client.call_async(request)

    def query_lifecycle_states(self) -> dict[str, Any]:
        """Issue direct GetState service calls; no CLI output parsing."""
        return {name: client.call_async(self._GetState.Request())
                for name, client in self.lifecycle_clients.items()}

    def send_compute_path(self, goal_pose: Any, *, request_stamp: Any) -> Any:
        goal = self._ComputePathToPose.Goal()
        goal.goal = goal_pose
        goal.start = type(goal_pose)()
        goal.start.header.frame_id = "map"
        goal.use_start = False
        goal.planner_id = "GridBased"
        goal.goal.header.stamp = request_stamp
        future = self.compute_path_client.send_goal_async(goal)
        self.action_events.append({"event": "COMPUTE_PATH_SENT", "stamp_ns": self._receive_ns()})
        return future

    def send_navigation(self, goal_pose: Any) -> Any:
        goal = self._NavigateToPose.Goal()
        goal.pose = goal_pose
        future = self.navigate_client.send_goal_async(goal, feedback_callback=self._feedback)
        self.action_events.append({"event": "NAVIGATE_SENT", "stamp_ns": self._receive_ns()})
        return future

    def _feedback(self, message: Any) -> None:
        self.action_events.append({"event": "NAVIGATE_FEEDBACK", "stamp_ns": self._receive_ns(),
                                  "feedback_stamp": self._stamp(message.feedback.current_pose.header.stamp)})

    def destroy(self) -> None:
        self.node.destroy_node()
