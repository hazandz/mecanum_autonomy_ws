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
    if type(samples) is not list or len(samples) < minimum:
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


def peer_evidence_ready(path, config_hash):
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
    except (OSError, ValueError):
        return False
    if not isinstance(document, dict) or "config_hash" not in document:
        return False
    if document["config_hash"] != config_hash:
        raise ValueError("GATE_B_PEER_CONFIG_HASH_MISMATCH")
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
        self.node.create_subscription(LaserScan, "/scan", self._scan, sensor_qos)
        self.node.create_subscription(Odometry, "/odometry/filtered", self._odom, sensor_qos)
        self.node.create_subscription(SafetyLifecycleState, LIFECYCLE_STATE_TOPIC, self._lifecycle, lifecycle_qos)
        self.node.create_subscription(FinalIssuedCommandReceipt, "/mecanum/final_issued_command", self._receipt, receipt_qos)
        self.compute = ActionClient(self.node, ComputePathToPose, "/compute_path_to_pose")
        self.navigate = ActionClient(self.node, NavigateToPose, "/navigate_to_pose")
        clock = importlib.import_module("rclpy.clock")
        self.timer = self.node.create_timer(0.02, self._tick,
            clock=clock.Clock(clock_type=clock.ClockType.STEADY_TIME))
        self.deadline = time.monotonic() + args.timeout_sec

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
        if self._compute_path_requested or not self.compute.server_is_ready():
            return
        goal = self.ComputePathToPose.Goal()
        goal.goal = self._goal_pose()
        goal.use_start = False
        self._compute_path_requested = True
        self._compute_path_calls += 1
        future = self.compute.send_goal_async(goal)
        future.add_done_callback(self._path_goal_response)

    def _path_goal_response(self, future):
        try:
            handle = future.result()
            if not handle.accepted:
                raise RuntimeError("COMPUTE_PATH_TO_POSE_REJECTED")
            handle.get_result_async().add_done_callback(self._path_result)
        except Exception as error:
            self.errors.append(f"COMPUTE_PATH_TO_POSE_FAILURE:{error}")

    def _path_result(self, future):
        try:
            wrapped = future.result()
            if wrapped.status != self.GoalStatus.STATUS_SUCCEEDED or wrapped.result.path.header.frame_id != "map":
                raise RuntimeError("COMPUTE_PATH_TO_POSE_NOT_SUCCESSFUL")
            self.path = wrapped.result.path
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

    def _navigate_once(self):
        if self._navigate_requested:
            self.errors.append("NAVIGATE_TO_POSE_RETRY_FORBIDDEN")
            return
        if not self.navigate.server_is_ready():
            return
        goal = self.NavigateToPose.Goal()
        goal.pose = self._goal_pose()
        self._navigate_requested = True
        self._navigate_calls += 1
        future = self.navigate.send_goal_async(goal)
        future.add_done_callback(self._navigate_goal_response)

    def _navigate_goal_response(self, future):
        try:
            handle = future.result()
            if not handle.accepted:
                self.navigate_result = {"accepted": False, "status": "REJECTED"}
                return
            handle.get_result_async().add_done_callback(self._navigate_done)
        except Exception as error:
            self.errors.append(f"NAVIGATE_TO_POSE_FAILURE:{error}")

    def _navigate_done(self, future):
        try:
            wrapped = future.result()
            self.navigate_result = {"accepted": True, "status": int(wrapped.status),
                                    "succeeded": wrapped.status == self.GoalStatus.STATUS_SUCCEEDED}
        except Exception as error:
            self.errors.append(f"NAVIGATE_TO_POSE_FAILURE:{error}")

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
        self.raw["lifecycle"].append({"episode_generation": msg.episode_generation, "reset_epoch": msg.reset_epoch, "runtime_generation": msg.runtime_generation, "primary_state": msg.primary_state, "barrier_state": msg.barrier_state, "motion_permitted": msg.motion_permitted, "reason": msg.reason})

    def _receipt(self, msg):
        self.latest_receipt = msg
        self.raw["receipt"].append({"episode_generation": msg.episode_generation, "reset_epoch": msg.reset_epoch, "runtime_generation": msg.runtime_generation, "sequence": msg.final_publish_sequence, "source": msg.source, "final_command": [msg.final_command.linear.x, msg.final_command.linear.y, msg.final_command.angular.z]})

    def _tick(self):
        if self._finished:
            self._wait_peer()
            return
        if self.errors:
            self._finish()
            return
        now = self.node.get_clock().now().nanoseconds
        if time.monotonic() >= self.deadline:
            self.errors.append("GATE_B_SAMPLE_TIMEOUT")
            self._finish()
            return
        if now <= 0:
            return
        stamp_type = importlib.import_module("rclpy.time").Time
        if not self._compute_path_requested:
            if self.tf_buffer.can_transform("base_link", "map", stamp_type(nanoseconds=now)):
                self._request_path_once()
        if self.path is not None and not self._navigate_requested:
            self._navigate_once()
        lifecycle, scan, odom, receipt = self.latest_lifecycle, self.latest_scan, self.latest_odom, self.latest_receipt
        if lifecycle is None or scan is None or odom is None or receipt is None or self.path is None:
            return
        if lifecycle.primary_state != 2 or lifecycle.barrier_state != 1 or not lifecycle.motion_permitted:
            return
        identity = (lifecycle.episode_generation, lifecycle.reset_epoch, lifecycle.runtime_generation)
        if (identity != (receipt.episode_generation, receipt.reset_epoch, receipt.runtime_generation)
                or not self.config_hash or receipt.source not in (1, 2, 4)):
            return
        scan_stamp = scan.header.stamp.sec * 1_000_000_000 + scan.header.stamp.nanosec
        odom_stamp = odom.header.stamp.sec * 1_000_000_000 + odom.header.stamp.nanosec
        if scan.header.frame_id != "lidar_frame" or odom.header.frame_id != "odom" or odom.child_frame_id != "base_link":
            self.errors.append("GATE_B_SENSOR_FRAME_CONTRACT_FAILURE")
            return
        if any(not math.isfinite(float(value)) for value in tuple(odom.pose.covariance) + tuple(odom.twist.covariance)):
            self.errors.append("GATE_B_FILTERED_ODOMETRY_COVARIANCE_INVALID")
            return
        if (not fresh_stamp(now, scan_stamp, 500_000_000)
                or not fresh_stamp(now, odom_stamp, 250_000_000)
                or not fresh_stamp(now, lifecycle.header.stamp.sec * 1_000_000_000 + lifecycle.header.stamp.nanosec, 500_000_000)
                or not fresh_stamp(now, receipt.header.stamp.sec * 1_000_000_000 + receipt.header.stamp.nanosec, 500_000_000)):
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
                return
            self.errors.append(str(error))
            self._finish()
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
            return
        admitted = validate_observation_inputs(context=context, lidar=lidar, local_reference=local,
            measured_twist=twist, receipt=receipt_context, fixture_claims=BINDING_CLAIMS)
        assembly = assemble_observation(admitted) if admitted is not None else None
        if assembly is None or not assembly.ready:
            self.errors.append("GATE_B_OBSERVATION_ASSEMBLY_REJECTED")
            return
        stamp = now
        if self.samples and stamp <= self.samples[-1]["stamp_ns"]:
            self.errors.append("GATE_B_SAMPLE_TIMESTAMP_NOT_MONOTONIC")
            return
        values = [float(value) for value in assembly.vector.tolist()]
        self.samples.append({"stamp_ns": int(stamp), "dimension": 81, "dtype": "float32", "values": values})
        self._last_measurement_key = measurement_key
        if len(self.samples) >= 5 and self.navigate_result is not None:
            self._finish()

    def _finish(self):
        if self._finished:
            return
        self._finished = True
        self._peer_deadline = time.monotonic() + self.args.peer_timeout_sec
        document = {
            "schema_version": "1.0", "config_hash": self.config_hash,
            "source_contract": "LIDAR72_LOCAL_REFERENCE3_FILTERED_TWIST3_FINAL_RECEIPT3",
            "sample_count": len(self.samples), "samples": self.samples,
            "raw_transcripts": self.raw, "compute_path_to_pose": {"requested_once": self._compute_path_requested, "success": self.path is not None, "frame_id": getattr(getattr(self.path, "header", None), "frame_id", None), "transcript": self.path_transcript},
            "navigate_to_pose": {**(self.navigate_result or {"accepted": False, "status": "NO_RESULT"}), "requested_once": self._navigate_requested},
            "acceptance": {"five_immutable_observation81": validate_vector_samples(self.samples),
                "compute_path_success_map_frame": self._compute_path_calls == 1 and self.path is not None and getattr(self.path.header, "frame_id", None) == "map",
                "navigate_to_pose_requested_once": self._navigate_calls == 1,
                "navigate_to_pose_succeeded": bool(self.navigate_result and self.navigate_result.get("succeeded")),
                "no_command_or_policy_publisher": True, "errors_absent": not self.errors},
            "errors": list(dict.fromkeys(self.errors)),
        }
        atomic_json(self.args.output, document)
        self._wait_peer()

    def _wait_peer(self):
        try:
            self._peer_verified = peer_evidence_ready(self.args.peer_evidence_path, self.config_hash)
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
            self._closed = True
            self.timer.cancel()
            self.node.destroy_node()
            if self.rclpy.ok():
                self.rclpy.shutdown()

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
    parser.add_argument("--peer-timeout-sec", type=float, default=60.0)
    parser.add_argument("--goal-x", type=float, default=-4.0)
    parser.add_argument("--goal-y", type=float, default=0.0)
    parser.add_argument("--goal-yaw", type=float, default=0.0)
    parser.add_argument("--timeout-sec", type=int, default=900)
    args = parser.parse_args(argv)
    if len(args.config_hash) != 64 or not all(ch in "0123456789abcdef" for ch in args.config_hash):
        raise SystemExit("CONFIG_HASH_INVALID")
    rclpy = importlib.import_module("rclpy")
    rclpy.init()
    collector = _Collector(args)
    try:
        rclpy.spin(collector.node)
    except KeyboardInterrupt:
        if rclpy.ok():
            collector.errors.append("OBSERVER_INTERRUPTED")
            collector._finish()
    finally:
        collector._close()
    return 0 if collector.passed() else 2


if __name__ == "__main__":
    raise SystemExit(main())
