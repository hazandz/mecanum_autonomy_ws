"""Gate-B Observation81 evidence collector; it never publishes commands."""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import math
import os
from pathlib import Path
import tempfile
import time

import numpy as np

from mecanum_nav_rl.observations.v3_ingress_binding_types import IngressMessageBinding
from mecanum_nav_rl.observations.v3_lidar_ingress_adapter import adapt_lidar_message
from mecanum_nav_rl.observations.v3_local_reference_ingress_adapter import adapt_local_reference_message
from mecanum_nav_rl.observations.v3_measured_twist_ingress_adapter import adapt_measured_twist_message
from mecanum_nav_rl.observations.v3_observation_assembler import assemble_observation
from mecanum_nav_rl.observations.v3_snapshot_types import (
    FRAME_TF_CONTRACT_ID, LIFECYCLE_BARRIER_CONTRACT_ID,
    ActiveLifecycleConfigContext, FinalIssuedReceiptContext,
)
from mecanum_nav_rl.observations.v3_snapshot_validation import FixtureBindingClaims, validate_observation_inputs


LIFECYCLE_STATE_TOPIC = "/mecanum/safety_lifecycle_state"
OBSOLETE_LIFECYCLE_STATE_TOPIC = "/mecanum/safety/lifecycle_state"
LIFECYCLE_STATE_QOS_CONTRACT = {
    "history": "KEEP_LAST", "depth": 10,
    "reliability": "RELIABLE", "durability": "VOLATILE",
}
FINAL_RECEIPT_QOS_CONTRACT = {
    "history": "KEEP_LAST", "depth": 1,
    "reliability": "RELIABLE", "durability": "TRANSIENT_LOCAL",
}


def _new_collector_diagnostics():
    predicates = (
        "GOAL_TRIGGER_NOT_VALID", "CLOCK_NOT_VALID", "TF_TRANSFORM_UNAVAILABLE",
        "TF_LOOKUP_EXCEPTION", "COMPUTE_PATH_NOT_READY", "NAVIGATE_ACTION_SERVER_NOT_READY",
        "COMPUTE_PATH_ACTION_SERVER_NOT_READY", "SENSOR_INPUT_MISSING", "LIFECYCLE_BARRIER_BLOCKED",
        "GENERATION_MISMATCH", "SENSOR_FRAME_INVALID", "SENSOR_TIMESTAMP_NOT_FRESH",
        "PATH_FEATURE_TF_FAILURE", "ADAPTER_REJECTED", "ASSEMBLY_REJECTED", "DEADLINE_EXPIRED")
    return {
        "schema_version": "1.0",
        "goal_trigger": {"state": "NOT_READ", "read_count": 0, "failure": None},
        "clock": {"state": "NOT_QUERIED", "last_ros_time_ns": None, "query_count": 0},
        "tf": {"state": "NOT_QUERIED", "query_count": 0,
            "last_query_time_ns": None, "last_error_type": None},
        "actions": {
            "compute_path_to_pose": {"state": "NOT_REQUESTED", "server_state": "UNKNOWN",
                "response": "NOT_REQUESTED", "result": "NOT_REQUESTED", "request_time_ns": None,
                "terminal_status": None},
            "navigate_to_pose": {"state": "NOT_REQUESTED", "server_state": "UNKNOWN",
                "response": "NOT_REQUESTED", "result": "NOT_REQUESTED", "request_time_ns": None,
                "terminal_status": None},
        },
        "predicate_counts": {name: 0 for name in predicates},
        "first_blocking_predicate": None, "last_blocking_predicate": None,
        "generation_mismatch": None, "freshness": {},
    }


def lifecycle_state_qos_profile(qos=None):
    """Build lifecycle subscription QoS independently from receipt QoS."""
    if qos is None:
        qos = importlib.import_module("rclpy.qos")
    return qos.QoSProfile(
        history=qos.HistoryPolicy.KEEP_LAST,
        depth=10,
        reliability=qos.ReliabilityPolicy.RELIABLE,
        durability=qos.DurabilityPolicy.VOLATILE,
    )


def _json_bytes(document: dict) -> bytes:
    return json.dumps(document, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def atomic_json(path: str | Path, document: dict) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=target.parent, prefix=f".{target.name}.", delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(_json_bytes(document))
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, target)


def validate_vector_samples(samples: list[dict], *, minimum: int = 5) -> bool:
    if type(samples) is not list or len(samples) != minimum:
        return False
    previous = None
    for row in samples:
        if type(row) is not dict or row.get("dtype") != "float32" or row.get("dimension") != 81:
            return False
        stamp = row.get("stamp_ns")
        values = row.get("values")
        if type(stamp) is not int or stamp <= 0 or (previous is not None and stamp <= previous):
            return False
        if type(values) is not list or len(values) != 81:
            return False
        if any(type(value) not in (float, int) or not math.isfinite(value) for value in values):
            return False
        previous = stamp
    return True


BINDING_CLAIMS = FixtureBindingClaims(
    lidar_topic="/scan", lidar_type="sensor_msgs/msg/LaserScan",
    local_reference_topic=None, local_reference_type="nav_msgs/msg/Path",
    measured_twist_topic="/odometry/filtered", measured_twist_type="nav_msgs/msg/Odometry",
    receipt_topic="/mecanum/final_issued_command",
    receipt_type="mecanum_nav_rl_interfaces/msg/FinalIssuedCommandReceipt",
)


def fresh_stamp(now, stamp, limit):
    return stamp > 0 and 0 <= now - stamp <= limit


def peer_evidence_ready(path, config_hash, invocation_id=None):
    """File đang ghi/chưa đủ trường phải chờ; identity khác phải fail closed."""
    def pairs(rows):
        result = {}
        for key, value in rows:
            if key in result:
                raise ValueError("PEER_DUPLICATE_KEY")
            result[key] = value
        return result
    try:
        document = json.loads(Path(path).read_bytes(), object_pairs_hook=pairs,
                              parse_constant=lambda _: (_ for _ in ()).throw(ValueError("PEER_NONFINITE")))
    except FileNotFoundError:
        return False
    except (OSError, ValueError) as error:
        raise ValueError("GATE_B_PEER_ARTIFACT_INVALID") from error
    if not isinstance(document, dict) or document.get("schema_version") != "1.0":
        raise ValueError("GATE_B_PEER_SCHEMA_INVALID")
    if document.get("config_hash") != config_hash:
        raise ValueError("GATE_B_PEER_CONFIG_HASH_MISMATCH")
    if invocation_id is not None and document.get("invocation_id") != invocation_id:
        raise ValueError("GATE_B_PEER_INVOCATION_MISMATCH")
    if invocation_id is not None and document.get("snapshot_complete") is not True:
        raise ValueError("GATE_B_PEER_SNAPSHOT_INCOMPLETE")
    acceptance = document.get("acceptance")
    return (type(acceptance) is dict and bool(acceptance)
            and all(type(value) is bool for value in acceptance.values()))


def _features_from_path(path, tf_buffer, synchronized_stamp_ns):
    """Transform a successful map-frame ComputePathToPose result into base_link."""
    importlib.import_module("tf2_geometry_msgs")
    PoseStamped = importlib.import_module("geometry_msgs.msg").PoseStamped
    TransformException = importlib.import_module("tf2_ros").TransformException
    if path.header.frame_id != "map" or len(path.poses) < 2:
        raise ValueError("COMPUTE_PATH_RESULT_INVALID_OR_EMPTY")
    selected = path.poses[1]
    if selected.header.frame_id != "map":
        raise ValueError("COMPUTE_PATH_POSE_FRAME_MISMATCH")
    pose = PoseStamped()
    pose.header = selected.header
    pose.header.stamp.sec = int(synchronized_stamp_ns // 1_000_000_000)
    pose.header.stamp.nanosec = int(synchronized_stamp_ns % 1_000_000_000)
    pose.pose = selected.pose
    try:
        base_pose = tf_buffer.transform(pose, "base_link")
    except TransformException as error:
        raise ValueError("LOCAL_REFERENCE_TF_TRANSFORM_FAILED") from error
    x = float(base_pose.pose.position.x)
    y = float(base_pose.pose.position.y)
    if not math.isfinite(x) or not math.isfinite(y):
        raise ValueError("LOCAL_REFERENCE_NONFINITE")
    bearing = math.atan2(y, x)
    return (float(math.hypot(x, y)), float(math.sin(bearing)), float(math.cos(bearing)))


class _Collector:
    """ROS implementation kept behind main so offline contract tests need no graph."""

    def __init__(self, args):
        rclpy = importlib.import_module("rclpy")
        GoalStatus = importlib.import_module("action_msgs.msg").GoalStatus
        PoseStamped = importlib.import_module("geometry_msgs.msg").PoseStamped
        interfaces = importlib.import_module("mecanum_nav_rl_interfaces.msg")
        FinalIssuedCommandReceipt = interfaces.FinalIssuedCommandReceipt
        SafetyLifecycleState = interfaces.SafetyLifecycleState
        nav2_actions = importlib.import_module("nav2_msgs.action")
        ComputePathToPose = nav2_actions.ComputePathToPose
        NavigateToPose = nav2_actions.NavigateToPose
        Odometry = importlib.import_module("nav_msgs.msg").Odometry
        ActionClient = importlib.import_module("rclpy.action").ActionClient
        qos = importlib.import_module("rclpy.qos")
        QoSProfile = qos.QoSProfile
        ReliabilityPolicy = qos.ReliabilityPolicy
        DurabilityPolicy = qos.DurabilityPolicy
        HistoryPolicy = qos.HistoryPolicy
        qos_profile_sensor_data = qos.qos_profile_sensor_data
        LaserScan = importlib.import_module("sensor_msgs.msg").LaserScan
        tf2 = importlib.import_module("tf2_ros")
        Buffer = tf2.Buffer
        TransformListener = tf2.TransformListener
        from mecanum_nav_rl.observations.lidar import LidarAngularBinner
        from mecanum_nav_rl.config.models import ObservationConfig
        from mecanum_nav_rl.observations.v3_snapshot_types import (
            LIFECYCLE_BARRIER_CONTRACT_ID, LIDAR_CONTRACT_ID,
            LOCAL_REFERENCE_CONTRACT_ID, MEASURED_TWIST_CONTRACT_ID,
        )

        self.rclpy = rclpy
        self.GoalStatus = GoalStatus
        self.PoseStamped = PoseStamped
        self.ComputePathToPose = ComputePathToPose
        self.NavigateToPose = NavigateToPose
        Parameter = importlib.import_module("rclpy.parameter").Parameter
        self.node = rclpy.create_node("step07_gate_b_observer",
                                     parameter_overrides=[Parameter("use_sim_time", value=True)])
        self.args = args
        self.config_hash = args.config_hash
        self.goal = (args.goal_x, args.goal_y, args.goal_yaw)
        self.tf_buffer = Buffer(node=self.node)
        self.tf_listener = TransformListener(self.tf_buffer, self.node)
        self.path = None
        self._finished = False
        self._closed = False
        self._peer_verified = False
        self._peer_deadline = None
        self._compute_path_calls = 0
        self._navigate_calls = 0
        self._compute_path_requested = False
        self._navigate_requested = False
        self.diagnostics = _new_collector_diagnostics()
        self.path_error = None
        self.navigate_result = None
        self.path_transcript = None
        self.latest_scan = None
        self.latest_odom = None
        self.latest_lifecycle = None
        self.latest_receipt = None
        self.samples = []
        self._last_measurement_key = None
        self.sample_rows = []
        self.raw = {"scan": [], "filtered_odometry": [], "lifecycle": [], "receipt": []}
        self.errors = []
        self.binner = LidarAngularBinner(ObservationConfig())
        self.lidar_binding = IngressMessageBinding(LaserScan, "/scan", "sensor_msgs/msg/LaserScan", "lidar_frame", self._sectorize, None)
        self.odom_binding = IngressMessageBinding(Odometry, "/odometry/filtered", "nav_msgs/msg/Odometry", "odom", None, "base_link")
        self.path_binding = IngressMessageBinding(type(None), None, "nav_msgs/msg/Path", "map", None, None)
        sensor_qos = qos_profile_sensor_data
        lifecycle_qos = lifecycle_state_qos_profile(qos)
        receipt_qos = QoSProfile(history=HistoryPolicy.KEEP_LAST, depth=1,
                                 reliability=ReliabilityPolicy.RELIABLE,
                                 durability=DurabilityPolicy.TRANSIENT_LOCAL)
        self.subscriptions = [
            self.node.create_subscription(LaserScan, "/scan", self._scan, sensor_qos),
            self.node.create_subscription(Odometry, "/odometry/filtered", self._odom, sensor_qos),
            self.node.create_subscription(SafetyLifecycleState, LIFECYCLE_STATE_TOPIC, self._lifecycle, lifecycle_qos),
            self.node.create_subscription(FinalIssuedCommandReceipt, "/mecanum/final_issued_command", self._receipt, receipt_qos),
        ]
        self.compute = ActionClient(self.node, ComputePathToPose, "/compute_path_to_pose")
        self.navigate = ActionClient(self.node, NavigateToPose, "/navigate_to_pose")
        clock = importlib.import_module("rclpy.clock")
        self.timer = self.node.create_timer(0.02, self._tick,
            clock=clock.Clock(clock_type=clock.ClockType.STEADY_TIME))
        self.deadline = time.monotonic() + args.timeout_sec
        self._goal_triggered = False
        self._ready_written = False

    def _ready_document(self):
        context_valid = bool(self.rclpy.ok() and self.node.context.ok())
        subscriptions = ["/scan", "/odometry/filtered", LIFECYCLE_STATE_TOPIC,
                         "/mecanum/final_issued_command"]
        return {"schema_version": "1.0", "collector": "step07_gate_b_observer",
                "config_hash": self.config_hash, "pid": os.getpid(),
                "ros_context_valid": context_valid,
                "process_alive": True,
                "subscriptions_created": subscriptions if len(self.subscriptions) == 4 else [],
                "navigate_to_pose_action_server_ready": bool(self.navigate.server_is_ready()),
                "state": "READY" if context_valid and len(self.subscriptions) == 4
                    and self.navigate.server_is_ready() else "NOT_READY"}

    def _publish_ready_when_complete(self):
        if getattr(self, "_ready_written", False) or not hasattr(self, "navigate"):
            return
        ready = self._ready_document()
        if ready["state"] == "READY":
            ready_path = getattr(self.args, "ready_path", None)
            if ready_path:
                atomic_json(ready_path, ready)
            self._ready_written = True

    def _read_goal_trigger(self):
        if getattr(self, "_goal_triggered", False):
            self._set_trigger_diagnostic("TRIGGER_GOAL_VALID")
            return True
        trigger_path = getattr(getattr(self, "args", None), "start_path", None)
        if not trigger_path:
            self._set_trigger_diagnostic("TRIGGER_PATH_NOT_CONFIGURED")
            return True
        try:
            trigger = json.loads(Path(trigger_path).read_bytes())
        except FileNotFoundError:
            self._set_trigger_diagnostic("TRIGGER_FILE_MISSING")
            return False
        except (OSError, ValueError) as error:
            self._set_trigger_diagnostic(f"TRIGGER_READ_FAILED:{type(error).__name__}")
            return False
        if (type(trigger) is dict and trigger.get("state") == "TRIGGER_GOAL"
                and trigger.get("config_hash") == self.config_hash
                and trigger.get("collector_ready") is True
                and trigger.get("navigate_to_pose_action_server_ready") is True
                and trigger.get("ready_collectors") == ["step07_nav2_baseline_runtime_observer",
                    "step07_gate_b_observer", "navigation_evidence_chain_collector"]):
            self._goal_triggered = True
            self._set_trigger_diagnostic("TRIGGER_GOAL_VALID")
        else:
            self._set_trigger_diagnostic("TRIGGER_SCHEMA_OR_IDENTITY_INVALID")
        return getattr(self, "_goal_triggered", False)

    def _set_trigger_diagnostic(self, state):
        if not hasattr(self, "diagnostics"):
            return
        trigger = self.diagnostics["goal_trigger"]
        trigger["read_count"] = min(2_147_483_647, trigger.get("read_count", 0) + 1)
        trigger["state"] = state
        trigger["failure"] = state if state != "TRIGGER_GOAL_VALID" else None

    def _record_blocker(self, predicate, now_ns=None, evidence=None):
        diagnostics = getattr(self, "diagnostics", None)
        if type(diagnostics) is not dict or predicate not in diagnostics["predicate_counts"]:
            return
        counts = diagnostics["predicate_counts"]
        counts[predicate] = min(2_147_483_647, counts[predicate] + 1)
        event = {"predicate": predicate, "ros_time_ns": now_ns}
        if type(evidence) is dict:
            event["evidence"] = {str(key): value for key, value in list(evidence.items())[:8]
                if value is None or type(value) in (str, int, float, bool)}
        if diagnostics["first_blocking_predicate"] is None:
            diagnostics["first_blocking_predicate"] = event
        diagnostics["last_blocking_predicate"] = event

    @staticmethod
    def _set_action_state(diagnostics, name, *, state=None, response=None, result=None,
                          request_time_ns=None, terminal_status=None):
        if type(diagnostics) is not dict:
            return
        action = diagnostics.get("actions", {}).get(name)
        if type(action) is not dict:
            return
        if state is not None:
            action["state"] = state
        if response is not None:
            action["response"] = response
        if result is not None:
            action["result"] = result
        if request_time_ns is not None:
            action["request_time_ns"] = int(request_time_ns)
        if terminal_status is not None:
            action["terminal_status"] = terminal_status

    def _goal_pose(self):
        pose = self.PoseStamped()
        pose.header.frame_id = "map"
        pose.header.stamp = self.node.get_clock().now().to_msg()
        pose.pose.position.x = float(self.goal[0])
        pose.pose.position.y = float(self.goal[1])
        pose.pose.orientation.z = math.sin(float(self.goal[2]) / 2.0)
        pose.pose.orientation.w = math.cos(float(self.goal[2]) / 2.0)
        return pose

    def _request_path_once(self):
        if type(getattr(self, "diagnostics", None)) is not dict:
            self.diagnostics = _new_collector_diagnostics()
        if self._compute_path_requested:
            return
        server_ready = self.compute.server_is_ready()
        self.diagnostics["actions"]["compute_path_to_pose"]["server_state"] = (
            "READY" if server_ready else "NOT_READY")
        if not server_ready:
            self._record_blocker("COMPUTE_PATH_ACTION_SERVER_NOT_READY",
                getattr(self, "_last_ros_time_ns", None))
            return
        goal = self.ComputePathToPose.Goal()
        goal.goal = self._goal_pose()
        goal.use_start = False
        self._compute_path_requested = True
        self._compute_path_calls += 1
        now_ns = self.node.get_clock().now().nanoseconds
        self._set_action_state(self.diagnostics, "compute_path_to_pose", state="RESPONSE_PENDING",
            response="PENDING", result="NOT_REQUESTED", request_time_ns=now_ns)
        future = self.compute.send_goal_async(goal)
        future.add_done_callback(self._path_goal_response)

    def _path_goal_response(self, future):
        try:
            handle = future.result()
            if not handle.accepted:
                self._set_action_state(self.diagnostics, "compute_path_to_pose", state="REJECTED",
                    response="REJECTED", terminal_status="GOAL_REJECTED")
                raise RuntimeError("COMPUTE_PATH_TO_POSE_REJECTED")
            self._set_action_state(self.diagnostics, "compute_path_to_pose", state="RESULT_PENDING",
                response="ACCEPTED", result="PENDING")
            handle.get_result_async().add_done_callback(self._path_result)
        except Exception as error:
            self.errors.append(f"COMPUTE_PATH_TO_POSE_FAILURE:{error}")
            self._set_action_state(self.diagnostics, "compute_path_to_pose", state="TERMINAL",
                response="ERROR", result="FAILED", terminal_status=type(error).__name__)

    def _path_result(self, future):
        try:
            wrapped = future.result()
            if wrapped.status != self.GoalStatus.STATUS_SUCCEEDED or wrapped.result.path.header.frame_id != "map":
                raise RuntimeError("COMPUTE_PATH_TO_POSE_NOT_SUCCESSFUL")
            self.path = wrapped.result.path
            self._set_action_state(self.diagnostics, "compute_path_to_pose", state="TERMINAL",
                result="SUCCEEDED", terminal_status=int(wrapped.status))
            self.path_transcript = {
                "goal": {"frame_id": "map", "x": self.goal[0], "y": self.goal[1], "yaw": self.goal[2]},
                "path_frame_id": self.path.header.frame_id,
                "poses": [{"frame_id": pose.header.frame_id,
                           "stamp_sec": pose.header.stamp.sec,
                           "stamp_nanosec": pose.header.stamp.nanosec,
                           "x": pose.pose.position.x, "y": pose.pose.position.y,
                           "z": pose.pose.position.z}
                          for pose in self.path.poses],
            }
        except Exception as error:
            self.errors.append(f"COMPUTE_PATH_TO_POSE_FAILURE:{error}")
            self._set_action_state(self.diagnostics, "compute_path_to_pose", state="TERMINAL",
                result="FAILED", terminal_status=type(error).__name__)

    def _navigate_once(self):
        if type(getattr(self, "diagnostics", None)) is not dict:
            self.diagnostics = _new_collector_diagnostics()
        if self._navigate_requested:
            self.errors.append("NAVIGATE_TO_POSE_RETRY_FORBIDDEN")
            return
        server_ready = self.navigate.server_is_ready()
        self.diagnostics["actions"]["navigate_to_pose"]["server_state"] = (
            "READY" if server_ready else "NOT_READY")
        if not server_ready:
            self._record_blocker("NAVIGATE_ACTION_SERVER_NOT_READY",
                getattr(self, "_last_ros_time_ns", None))
            return
        goal = self.NavigateToPose.Goal()
        goal.pose = self._goal_pose()
        self._navigate_requested = True
        self._navigate_calls += 1
        now_ns = self.node.get_clock().now().nanoseconds
        self._set_action_state(self.diagnostics, "navigate_to_pose", state="RESPONSE_PENDING",
            response="PENDING", result="NOT_REQUESTED", request_time_ns=now_ns)
        future = self.navigate.send_goal_async(goal)
        future.add_done_callback(self._navigate_goal_response)

    def _navigate_goal_response(self, future):
        try:
            handle = future.result()
            if not handle.accepted:
                self.navigate_result = {"accepted": False, "status": "REJECTED"}
                self._set_action_state(self.diagnostics, "navigate_to_pose", state="REJECTED",
                    response="REJECTED", result="NOT_REQUESTED", terminal_status="GOAL_REJECTED")
                return
            self._set_action_state(self.diagnostics, "navigate_to_pose", state="RESULT_PENDING",
                response="ACCEPTED", result="PENDING")
            handle.get_result_async().add_done_callback(self._navigate_done)
        except Exception as error:
            self.errors.append(f"NAVIGATE_TO_POSE_FAILURE:{error}")
            self._set_action_state(self.diagnostics, "navigate_to_pose", state="TERMINAL",
                response="ERROR", result="FAILED", terminal_status=type(error).__name__)

    def _navigate_done(self, future):
        try:
            wrapped = future.result()
            self.navigate_result = {"accepted": True, "status": int(wrapped.status),
                                    "succeeded": wrapped.status == self.GoalStatus.STATUS_SUCCEEDED}
            self._set_action_state(self.diagnostics, "navigate_to_pose", state="TERMINAL",
                result="SUCCEEDED" if self.navigate_result["succeeded"] else "FAILED",
                terminal_status=int(wrapped.status))
        except Exception as error:
            self.errors.append(f"NAVIGATE_TO_POSE_FAILURE:{error}")
            self._set_action_state(self.diagnostics, "navigate_to_pose", state="TERMINAL",
                result="FAILED", terminal_status=type(error).__name__)

    def _sectorize(self, msg):
        from mecanum_nav_rl.observations.lidar import RawLidarScan
        scan = RawLidarScan(timestamp_ns=msg.header.stamp.sec * 1_000_000_000 + msg.header.stamp.nanosec,
                            angle_min_rad=float(msg.angle_min), angle_increment_rad=float(msg.angle_increment),
                            range_min_m=float(msg.range_min), range_max_m=float(msg.range_max),
                            ranges=tuple(float(value) for value in msg.ranges))
        return tuple(float(value) for value in self.binner.bin_scan(scan).sector_ranges_m)

    def _scan(self, msg):
        self.latest_scan = msg
        self.raw["scan"].append({"frame_id": msg.header.frame_id, "stamp_ns": msg.header.stamp.sec * 1_000_000_000 + msg.header.stamp.nanosec, "range_count": len(msg.ranges)})

    def _odom(self, msg):
        self.latest_odom = msg
        self.raw["filtered_odometry"].append({"frame_id": msg.header.frame_id, "child_frame_id": msg.child_frame_id, "stamp_ns": msg.header.stamp.sec * 1_000_000_000 + msg.header.stamp.nanosec})

    def _lifecycle(self, msg):
        self.latest_lifecycle = msg
        self.raw["lifecycle"].append({"stamp_ns": msg.header.stamp.sec * 1_000_000_000 + msg.header.stamp.nanosec,
            "episode_generation": msg.episode_generation, "reset_epoch": msg.reset_epoch,
            "runtime_generation": msg.runtime_generation, "sequence": msg.sequence,
            "primary_state": msg.primary_state, "barrier_state": msg.barrier_state,
            "motion_permitted": msg.motion_permitted, "reason": msg.reason})

    def _receipt(self, msg):
        self.latest_receipt = msg
        self.raw["receipt"].append({"stamp_ns": msg.header.stamp.sec * 1_000_000_000 + msg.header.stamp.nanosec,
            "episode_generation": msg.episode_generation, "reset_epoch": msg.reset_epoch,
            "runtime_generation": msg.runtime_generation, "sequence": msg.final_publish_sequence,
            "source": msg.source, "final_command": [msg.final_command.linear.x,
                msg.final_command.linear.y, msg.final_command.angular.z]})

    def _tick(self):
        if type(getattr(self, "diagnostics", None)) is not dict:
            self.diagnostics = _new_collector_diagnostics()
        if self._finished:
            self._wait_peer()
            return
        self._publish_ready_when_complete()
        if len(self.samples) == 5 and self.navigate_result is not None:
            self._finish()
            return
        if self.errors:
            if self.navigate_result is not None:
                self._finish()
                return
        if self.navigate_result is not None and self.navigate_result.get("succeeded") is not True:
            self.errors.append("GATE_B_NAVIGATION_TERMINAL_FAILURE")
            self._finish()
            return
        try:
            now = self.node.get_clock().now().nanoseconds
        except Exception as error:
            now = None
            self._record_blocker("CLOCK_NOT_VALID", evidence={"query_error_type": type(error).__name__})
            if type(getattr(self, "diagnostics", None)) is dict:
                self.diagnostics["clock"].update(state="QUERY_ERROR", last_error_type=type(error).__name__)
        if type(getattr(self, "diagnostics", None)) is dict:
            clock_diag = self.diagnostics["clock"]
            clock_diag["query_count"] = min(2_147_483_647, clock_diag["query_count"] + 1)
            clock_diag["last_ros_time_ns"] = now
            if now is not None:
                clock_diag["state"] = "VALID" if now > 0 else "NOT_STARTED"
        self._last_ros_time_ns = now
        if time.monotonic() >= self.deadline:
            if "GATE_B_SAMPLE_TIMEOUT" not in self.errors:
                self.errors.append("GATE_B_SAMPLE_TIMEOUT")
            self._record_blocker("DEADLINE_EXPIRED", now)
            self._finish()
            return
        if now is None or now <= 0:
            self._record_blocker("CLOCK_NOT_VALID", now)
            return
        if not self._read_goal_trigger():
            self._record_blocker("GOAL_TRIGGER_NOT_VALID", now,
                {"trigger_state": self.diagnostics.get("goal_trigger", {}).get("state")})
            return
        stamp_type = importlib.import_module("rclpy.time").Time
        if not self._compute_path_requested:
            if type(self.diagnostics) is dict:
                tf_diag = self.diagnostics["tf"]
                tf_diag["query_count"] = min(2_147_483_647, tf_diag["query_count"] + 1)
                tf_diag["last_query_time_ns"] = int(now)
            try:
                can_transform = self.tf_buffer.can_transform("base_link", "map", stamp_type(nanoseconds=now))
            except Exception as error:
                can_transform = False
                if type(self.diagnostics) is dict:
                    self.diagnostics["tf"].update(state="QUERY_ERROR", last_error_type=type(error).__name__)
                self._record_blocker("TF_LOOKUP_EXCEPTION", now,
                    {"query_error_type": type(error).__name__})
            if can_transform:
                if type(self.diagnostics) is dict:
                    self.diagnostics["tf"].update(state="AVAILABLE", last_error_type=None)
                self._request_path_once()
            elif type(self.diagnostics) is dict and self.diagnostics["tf"].get("state") != "QUERY_ERROR":
                self.diagnostics["tf"].update(state="UNAVAILABLE", last_error_type=None)
                self._record_blocker("TF_TRANSFORM_UNAVAILABLE", now,
                    {"target_frame": "base_link", "source_frame": "map"})
        if self.path is not None and not self._navigate_requested:
            self._navigate_once()
        if self.path is None:
            self._record_blocker("COMPUTE_PATH_NOT_READY", now,
                {"action_state": self.diagnostics["actions"]["compute_path_to_pose"]["state"]})
        lifecycle, scan, odom, receipt = self.latest_lifecycle, self.latest_scan, self.latest_odom, self.latest_receipt
        if lifecycle is None or scan is None or odom is None or receipt is None or self.path is None:
            missing = [name for name, value in (("lifecycle", lifecycle), ("scan", scan),
                ("odometry", odom), ("receipt", receipt), ("path", self.path)) if value is None]
            self._record_blocker("SENSOR_INPUT_MISSING", now, {"missing": ",".join(missing)})
            return
        if lifecycle.primary_state != 2 or lifecycle.barrier_state != 1 or not lifecycle.motion_permitted:
            self._record_blocker("LIFECYCLE_BARRIER_BLOCKED", now, {
                "primary_state": int(lifecycle.primary_state), "barrier_state": int(lifecycle.barrier_state),
                "motion_permitted": bool(lifecycle.motion_permitted)})
            return
        identity = (lifecycle.episode_generation, lifecycle.reset_epoch, lifecycle.runtime_generation)
        if (identity != (receipt.episode_generation, receipt.reset_epoch, receipt.runtime_generation)
                or not self.config_hash or receipt.source not in (1, 2, 4)):
            self.diagnostics["generation_mismatch"] = {
                "lifecycle": {"episode_generation": int(lifecycle.episode_generation),
                    "reset_epoch": int(lifecycle.reset_epoch), "runtime_generation": int(lifecycle.runtime_generation),
                    "sequence": int(lifecycle.sequence)},
                "receipt": {"episode_generation": int(receipt.episode_generation),
                    "reset_epoch": int(receipt.reset_epoch), "runtime_generation": int(receipt.runtime_generation),
                    "sequence": int(receipt.final_publish_sequence), "source": int(receipt.source)},
                "config_hash_present": bool(self.config_hash)}
            self._record_blocker("GENERATION_MISMATCH", now, {"identity_matches": identity == (
                receipt.episode_generation, receipt.reset_epoch, receipt.runtime_generation),
                "receipt_source": int(receipt.source), "config_hash_present": bool(self.config_hash)})
            return
        scan_stamp = scan.header.stamp.sec * 1_000_000_000 + scan.header.stamp.nanosec
        odom_stamp = odom.header.stamp.sec * 1_000_000_000 + odom.header.stamp.nanosec
        if scan.header.frame_id != "lidar_frame" or odom.header.frame_id != "odom" or odom.child_frame_id != "base_link":
            self.errors.append("GATE_B_SENSOR_FRAME_CONTRACT_FAILURE")
            self._record_blocker("SENSOR_FRAME_INVALID", now, {"scan_frame": scan.header.frame_id,
                "odometry_frame": odom.header.frame_id, "odometry_child_frame": odom.child_frame_id})
            return
        if any(not math.isfinite(float(value)) for value in tuple(odom.pose.covariance) + tuple(odom.twist.covariance)):
            self.errors.append("GATE_B_FILTERED_ODOMETRY_COVARIANCE_INVALID")
            return
        lifecycle_stamp = lifecycle.header.stamp.sec * 1_000_000_000 + lifecycle.header.stamp.nanosec
        receipt_stamp = receipt.header.stamp.sec * 1_000_000_000 + receipt.header.stamp.nanosec
        freshness = {
            "scan": {"stamp_ns": int(scan_stamp), "age_ns": int(now - scan_stamp), "limit_ns": 500_000_000},
            "odometry": {"stamp_ns": int(odom_stamp), "age_ns": int(now - odom_stamp), "limit_ns": 250_000_000},
            "lifecycle": {"stamp_ns": int(lifecycle_stamp), "age_ns": int(now - lifecycle_stamp), "limit_ns": 500_000_000},
            "receipt": {"stamp_ns": int(receipt_stamp), "age_ns": int(now - receipt_stamp), "limit_ns": 500_000_000},
        }
        for name, item in freshness.items():
            item["state"] = ("FUTURE" if item["age_ns"] < 0 else
                "STALE" if item["age_ns"] > item["limit_ns"] else "FRESH")
        self.diagnostics["freshness"] = freshness
        if any(item["state"] != "FRESH" for item in freshness.values()):
            self._record_blocker("SENSOR_TIMESTAMP_NOT_FRESH", now,
                {"stale_or_future": ",".join(name for name, item in freshness.items()
                    if item["state"] != "FRESH")})
            return
        measurement_key = (scan_stamp, odom_stamp, int(receipt.final_publish_sequence), int(lifecycle.sequence))
        if measurement_key == self._last_measurement_key:
            return
        context = ActiveLifecycleConfigContext(LIFECYCLE_BARRIER_CONTRACT_ID,
            int(lifecycle.episode_generation), int(lifecycle.reset_epoch), int(lifecycle.runtime_generation), self.config_hash)
        lidar = adapt_lidar_message(scan, binding=self.lidar_binding, context=context)
        twist = adapt_measured_twist_message(odom, binding=self.odom_binding, context=context)
        try:
            path_features = _features_from_path(self.path, self.tf_buffer, now)
            path_binding = IngressMessageBinding(type(self.path), None, "nav_msgs/msg/Path", "map",
                lambda _: path_features, None)
            local = adapt_local_reference_message(self.path, binding=path_binding, context=context)
        except ValueError as error:
            if str(error) == "LOCAL_REFERENCE_TF_TRANSFORM_FAILED":
                self._record_blocker("PATH_FEATURE_TF_FAILURE", now,
                    {"failure": str(error)})
                return
            self.errors.append(str(error))
            self._record_blocker("ADAPTER_REJECTED", now, {"failure": str(error)})
            # Preserve the collector until five valid samples or an action
            # terminal result lets us write complete failure evidence.
            return
        receipt_context = FinalIssuedReceiptContext(
            contract_id=LIFECYCLE_BARRIER_CONTRACT_ID, frame_contract_id=FRAME_TF_CONTRACT_ID,
            episode_generation=context.episode_generation, reset_epoch=context.reset_epoch,
            runtime_generation=context.runtime_generation, config_hash=context.config_hash,
            frame_id="base_link", final_command=(float(receipt.final_command.linear.x),
                float(receipt.final_command.linear.y), float(receipt.final_command.angular.z)),
            topic_claim="/mecanum/final_issued_command",
            type_claim="mecanum_nav_rl_interfaces/msg/FinalIssuedCommandReceipt")
        if lidar is None or local is None or twist is None:
            self.errors.append("GATE_B_INPUT_ADAPTER_REJECTED")
            self._record_blocker("ADAPTER_REJECTED", now,
                {"lidar": lidar is not None, "local_reference": local is not None,
                 "measured_twist": twist is not None})
            return
        admitted = validate_observation_inputs(context=context, lidar=lidar, local_reference=local,
            measured_twist=twist, receipt=receipt_context, fixture_claims=BINDING_CLAIMS)
        assembly = assemble_observation(admitted) if admitted is not None else None
        if assembly is None or not assembly.ready:
            self.errors.append("GATE_B_OBSERVATION_ASSEMBLY_REJECTED")
            self._record_blocker("ASSEMBLY_REJECTED", now,
                {"assembly_present": assembly is not None,
                 "assembly_ready": bool(assembly is not None and assembly.ready)})
            return
        stamp = now
        if self.samples and stamp <= self.samples[-1]["stamp_ns"]:
            self.errors.append("GATE_B_SAMPLE_TIMESTAMP_NOT_MONOTONIC")
            return
        values = [float(value) for value in assembly.vector.tolist()]
        if len(self.samples) >= 5:
            return
        self.samples.append({"stamp_ns": int(stamp), "dimension": 81, "dtype": "float32", "values": values,
            "correlation": {"episode_generation": int(lifecycle.episode_generation),
                "reset_epoch": int(lifecycle.reset_epoch), "runtime_generation": int(lifecycle.runtime_generation),
                "lifecycle_sequence": int(lifecycle.sequence),
                "receipt_sequence": int(receipt.final_publish_sequence),
                "scan_stamp_ns": int(scan_stamp), "odometry_stamp_ns": int(odom_stamp),
                "receipt_stamp_ns": int(receipt.header.stamp.sec * 1_000_000_000 + receipt.header.stamp.nanosec)}})
        self._last_measurement_key = measurement_key
        if len(self.samples) == 5 and self.navigate_result is not None:
            self._finish()

    def _finish(self):
        if self._finished:
            return
        self._finished = True
        self._peer_deadline = time.monotonic() + self.args.peer_timeout_sec
        document = {
            "schema_version": "1.0", "config_hash": self.config_hash,
            "handshake_protocol": "2.0",
            "invocation_id": getattr(self.args, "invocation_id", ""),
            "protocol_phase": "COLLECTION_COMPLETE_AWAITING_PEER",
            "source_contract": "LIDAR72_LOCAL_REFERENCE3_FILTERED_TWIST3_FINAL_RECEIPT3",
            "sample_count": len(self.samples), "samples": self.samples,
            "diagnostics": getattr(self, "diagnostics", _new_collector_diagnostics()),
            "raw_transcripts": self.raw, "compute_path_to_pose": {"requested_once": self._compute_path_requested, "success": self.path is not None, "frame_id": getattr(getattr(self.path, "header", None), "frame_id", None), "transcript": self.path_transcript},
            "navigate_to_pose": {**(self.navigate_result or {"accepted": False, "status": "NO_RESULT"}), "requested_once": self._navigate_requested},
            "acceptance": {"five_immutable_observation81": validate_vector_samples(self.samples),
                "compute_path_success_map_frame": self._compute_path_calls == 1 and self.path is not None and getattr(self.path.header, "frame_id", None) == "map",
                "navigate_to_pose_requested_once": self._navigate_calls == 1,
                "navigate_to_pose_succeeded": bool(self.navigate_result and self.navigate_result.get("succeeded")),
                "no_command_or_policy_publisher": True, "errors_absent": not self.errors},
            "errors": list(dict.fromkeys(self.errors)),
            "collector_failure": ({"literal": self.errors[0], "exit_code": 2,
                "lifecycle_state": self.raw.get("lifecycle", [])[-1] if self.raw.get("lifecycle") else
                    {"state": "UNOBSERVED", "reason": "NO_LIFECYCLE_SAMPLE_IN_GATE_WINDOW"},
                "partial_artifact": "gate_b_vectors.json", "valid_sample_count": len(self.samples)}
                if self.errors else None),
            "collector_terminal_state": ("FIVE_VALID_SAMPLES_AND_ACTION_TERMINAL"
                if len(self.samples) == 5 and self.navigate_result is not None else
                "ACTION_TERMINAL_RESULT_WITH_PARTIAL_EVIDENCE" if self.navigate_result is not None else
                "COLLECTOR_INTERRUPTED_BEFORE_ACTION_TERMINAL"),
        }
        atomic_json(self.args.output, document)
        self._collection_document = document
        self._wait_peer()

    def _wait_peer(self):
        try:
            self._peer_verified = peer_evidence_ready(self.args.peer_evidence_path, self.config_hash,
                getattr(self.args, "invocation_id", None))
        except ValueError as error:
            self.errors.append(str(error))
            print(str(error), flush=True)
            self._close()
            return
        if self._peer_verified:
            self._close()
        elif time.monotonic() >= self._peer_deadline:
            self.errors.append("GATE_B_PEER_EVIDENCE_TIMEOUT")
            print("GATE_B_PEER_EVIDENCE_TIMEOUT", flush=True)
            self._close()

    def _close(self):
        if not self._closed:
            if self._finished and not getattr(self, "_terminal_written", False):
                if not self._peer_verified and not self.errors:
                    self.errors.append("GATE_B_PEER_HANDSHAKE_INCOMPLETE")
                self._write_terminal()
            self._closed = True
            self.timer.cancel()
            self.node.destroy_node()
            if self.rclpy.ok():
                self.rclpy.shutdown()

    def _write_terminal(self):
        """Collection bất biến; terminal handshake ghi riêng đúng một lần."""
        if getattr(self, "_terminal_written", False):
            return
        raw = Path(self.args.output).read_bytes()
        peer = None
        if self._peer_verified:
            content = Path(self.args.peer_evidence_path).read_bytes()
            peer = {"path": Path(self.args.peer_evidence_path).name,
                    "sha256": hashlib.sha256(content).hexdigest(), "size_bytes": len(content)}
        document = {"schema_version": "1.0", "collector": "step07_gate_b_observer",
            "protocol_phase": "TERMINAL", "invocation_id": getattr(self.args, "invocation_id", ""),
            "config_hash": self.config_hash, "peer_verified": self._peer_verified,
            "status": "PASS" if self.passed() else "FAIL", "errors": list(dict.fromkeys(self.errors)),
            "collection_artifact": {"path": Path(self.args.output).name,
                "sha256": hashlib.sha256(raw).hexdigest(), "size_bytes": len(raw)},
            "peer_artifact": peer}
        terminal = getattr(self.args, "terminal_output", None) or Path(self.args.output).with_name("gate_b_terminal.json")
        atomic_json(terminal, document)
        self._terminal_written = True

    def passed(self):
        return (self._finished and self._peer_verified and not self.errors
                and self._compute_path_calls == self._navigate_calls == 1
                and self.path is not None and bool(self.navigate_result and self.navigate_result.get("succeeded"))
                and validate_vector_samples(self.samples))


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--config-hash", required=True)
    parser.add_argument("--peer-evidence-path", required=True)
    parser.add_argument("--ready-path", required=True)
    parser.add_argument("--start-path", required=True)
    parser.add_argument("--invocation-id", required=True)
    parser.add_argument("--terminal-output")
    parser.add_argument("--peer-timeout-sec", type=float, default=60.0)
    parser.add_argument("--goal-x", type=float, default=-4.0)
    parser.add_argument("--goal-y", type=float, default=0.0)
    parser.add_argument("--goal-yaw", type=float, default=0.0)
    parser.add_argument("--timeout-sec", type=int, default=900)
    args = parser.parse_args(argv)
    if len(args.config_hash) != 64 or not all(ch in "0123456789abcdef" for ch in args.config_hash):
        raise SystemExit("CONFIG_HASH_INVALID")
    import signal
    rclpy = importlib.import_module("rclpy")
    signal_options = importlib.import_module("rclpy.signals").SignalHandlerOptions
    rclpy.init(signal_handler_options=signal_options.NO)
    stop_requested = {"value": False}
    previous_handlers = {}
    def request_stop(_signum, _frame):
        stop_requested["value"] = True
    for signum in (signal.SIGINT, signal.SIGTERM):
        previous_handlers[signum] = signal.getsignal(signum)
        signal.signal(signum, request_stop)
    collector = _Collector(args)
    try:
        while rclpy.ok() and not collector._closed and not stop_requested["value"]:
            rclpy.spin_once(collector.node, timeout_sec=0.1)
        if stop_requested["value"]:
            collector.errors.append("GATE_B_COLLECTOR_INTERRUPTED")
            if not collector._finished:
                collector._finish()
    except Exception as error:
        collector.errors.append(f"GATE_B_COLLECTOR_EXCEPTION:{type(error).__name__}:{error}")
        if not collector._finished:
            collector._finish()
    finally:
        collector._close()
        if rclpy.ok():
            rclpy.shutdown()
        for signum, handler in previous_handlers.items():
            signal.signal(signum, handler)
    return 0 if collector.passed() else 2


if __name__ == "__main__":
    raise SystemExit(main())
