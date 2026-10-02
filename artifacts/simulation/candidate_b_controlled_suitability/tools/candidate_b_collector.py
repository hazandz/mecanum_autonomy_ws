#!/usr/bin/env python3
"""One approved, Gazebo-only controlled coordinate measurement collector.

This tool creates subscriptions for the three scoped streams and one client for
SetEntityPose only. It creates no publishers, action clients, or world-control
clients. The six literal requests below are intentionally immutable.
"""

import argparse
import json
import math
import signal
import sys
import time
from pathlib import Path

import rclpy
from nav_msgs.msg import Odometry
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from ros_gz_interfaces.msg import Entity
from ros_gz_interfaces.srv import SetEntityPose
from rosgraph_msgs.msg import Clock
from sensor_msgs.msg import LaserScan


ENTITY_NAME = "ROBOT_URDF_final"
POSE_SERVICE = "/world/world_demo/set_pose"
POSE_SERVICE_TYPE = "ros_gz_interfaces/srv/SetEntityPose"
SCOPED_TYPES = {
    "/clock": "rosgraph_msgs/msg/Clock",
    "/ground_truth/odom": "nav_msgs/msg/Odometry",
    "/scan": "sensor_msgs/msg/LaserScan",
}
APPROVED_PROBES = (
    ("B0_START_P0", -4.0, -3.0, 0.1, 0.0),
    ("B1_GOAL_P2", -2.0, -3.0, 0.1, -1.57079632679),
    ("B2_RECT_LL", -4.5, -3.5, 0.1, 0.0),
    ("B3_RECT_LR", -1.5, -3.5, 0.1, 0.0),
    ("B4_RECT_UR", -1.5, -2.5, 0.1, 0.0),
    ("B5_RECT_UL", -4.5, -2.5, 0.1, 0.0),
)
ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "measurement_manifest.json"


def offline_bootstrap_self_test() -> int:
    """Validate static run inputs without initializing ROS or creating a client."""
    try:
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        expected = [
            {"probe_id": name, "x_m": x, "y_m": y, "z_m": z, "yaw_rad": yaw}
            for name, x, y, z, yaw in APPROVED_PROBES
        ]
        if manifest.get("entity") != ENTITY_NAME:
            raise ValueError("manifest entity differs")
        if manifest.get("bridge_argument") != (
            "/world/world_demo/set_pose@ros_gz_interfaces/srv/SetEntityPose@"
            "gz.msgs.Pose@gz.msgs.Boolean"
        ):
            raise ValueError("manifest bridge literal differs")
        if manifest.get("observed_streams") != [
            "/ground_truth/odom", "/scan", "/clock", "graph metadata"
        ]:
            raise ValueError("manifest observed streams differ")
        if manifest.get("probes") != [
            {"order": index + 1, **probe} for index, probe in enumerate(expected)
        ]:
            raise ValueError("manifest probe literals or order differ")
    except Exception as exc:
        print(json.dumps({"offline_bootstrap_self_test": "FAIL", "error": repr(exc)}))
        return 2
    print(json.dumps({
        "offline_bootstrap_self_test": "PASS",
        "rclpy_initialized": False,
        "publishers_created": 0,
        "clients_created": 0,
        "processes_spawned": 0,
    }))
    return 0


def stamp_ns(stamp):
    return int(stamp.sec) * 1_000_000_000 + int(stamp.nanosec)


def json_safe(value):
    """Preserve non-finite float values in valid JSON without silently dropping them."""
    if isinstance(value, float):
        if math.isnan(value):
            return {"float_encoding": "nan"}
        if math.isinf(value):
            return {"float_encoding": "inf" if value > 0 else "-inf"}
        return value
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    return value


def message_payload(message):
    from rosidl_runtime_py.convert import message_to_ordereddict

    return json_safe(message_to_ordereddict(message))


def scan_sanity(message):
    """Validate only structural scan evidence; no clearance or collision inference."""
    try:
        if not str(message.header.frame_id):
            return {"valid": False, "reason": "missing_frame_id"}
        stamp_ns(message.header.stamp)
        if not (math.isfinite(message.angle_increment) and message.angle_increment != 0.0):
            return {"valid": False, "reason": "invalid_angle_increment"}
        if not (math.isfinite(message.range_min) and math.isfinite(message.range_max)
                and message.range_min >= 0.0 and message.range_max >= message.range_min):
            return {"valid": False, "reason": "invalid_range_bounds"}
        if not message.ranges:
            return {"valid": False, "reason": "empty_ranges"}
        for value in message.ranges:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                return {"valid": False, "reason": "non_numeric_range"}
            value = float(value)
            if math.isnan(value) or value == float("-inf") or value < 0.0:
                return {"valid": False, "reason": "malformed_range"}
        return {"valid": True, "reason": None}
    except Exception as exc:
        return {"valid": False, "reason": type(exc).__name__}


def endpoint_record(endpoint):
    namespace = str(endpoint.node_namespace)
    node_name = str(endpoint.node_name)
    publisher_name = "/" + node_name.lstrip("/") if namespace == "/" else namespace.rstrip("/") + "/" + node_name.lstrip("/")
    return {
        "publisher_name": publisher_name,
        "node_name": node_name,
        "node_namespace": namespace,
        "topic_type": str(endpoint.topic_type),
    }


def canonical(records):
    return sorted(records, key=lambda record: json.dumps(record, sort_keys=True))


class ControlledMeasurementCollector(Node):
    """Scoped subscriptions plus exactly one SetEntityPose service client."""

    def __init__(self, run_id, run_dir):
        super().__init__("s3_controlled_coordinate_measurement_collector")
        self.run_id = run_id
        self.run_dir = run_dir
        self.trace_file = (run_dir / "stream_trace.jsonl").open("w", encoding="utf-8")
        self.capture_enabled = False
        self.interrupted = False
        self.message_index = {topic: 0 for topic in SCOPED_TYPES}
        self.record_count = {topic: 0 for topic in SCOPED_TYPES}
        self.latest = {topic: None for topic in SCOPED_TYPES}
        self.create_subscription(Clock, "/clock", self.clock_callback, qos_profile_sensor_data)
        self.create_subscription(Odometry, "/ground_truth/odom", self.gt_odom_callback, qos_profile_sensor_data)
        self.create_subscription(LaserScan, "/scan", self.scan_callback, qos_profile_sensor_data)
        self.pose_client = self.create_client(SetEntityPose, POSE_SERVICE)

    def graph_snapshot(self):
        names_and_types = dict(self.get_topic_names_and_types())
        snapshot = {}
        for topic, expected in SCOPED_TYPES.items():
            publishers = canonical([endpoint_record(item) for item in self.get_publishers_info_by_topic(topic)])
            snapshot[topic] = {
                "expected_type": expected,
                "observed_types": sorted(names_and_types.get(topic, [])),
                "publisher_count": len(publishers),
                "publishers": publishers,
            }
        publishers = canonical([endpoint_record(item) for item in self.get_publishers_info_by_topic("/cmd_vel")])
        snapshot["/cmd_vel"] = {
            "observed_types": sorted(names_and_types.get("/cmd_vel", [])),
            "publisher_count": len(publishers),
            "publishers": publishers,
        }
        return snapshot

    def service_graph_snapshot(self):
        names_and_types = self.get_service_names_and_types()
        all_services = [
            {"service_name": str(name), "types": sorted(str(item) for item in types)}
            for name, types in names_and_types
        ]
        all_services.sort(key=lambda item: item["service_name"])
        expected_types = next(
            (item["types"] for item in all_services if item["service_name"] == POSE_SERVICE),
            [],
        )
        return {
            "expected_service_name": POSE_SERVICE,
            "expected_service_type": POSE_SERVICE_TYPE,
            "observed_expected_service_types": expected_types,
            "all_services": all_services,
        }

    def exact_pose_service_ready(self, snapshot):
        return snapshot["observed_expected_service_types"] == [POSE_SERVICE_TYPE]

    def graph_ready(self, snapshot):
        return all(
            expected in snapshot[topic]["observed_types"] and snapshot[topic]["publisher_count"] > 0
            for topic, expected in SCOPED_TYPES.items()
        )

    def cmd_vel_allowlist_resolved(self, snapshot):
        return all(
            item["node_name"] != "_NODE_NAME_UNKNOWN_"
            and item["node_namespace"] != "_NODE_NAMESPACE_UNKNOWN_"
            and bool(item["topic_type"])
            for item in snapshot["/cmd_vel"]["publishers"]
        )

    def barrier(self):
        return {
            "captured_steady_ns": time.monotonic_ns(),
            "streams": {topic: self.latest[topic] for topic in SCOPED_TYPES},
        }

    def write_record(self, topic, message, record_kind):
        self.message_index[topic] += 1
        self.record_count[topic] += 1
        metadata = {"index": self.record_count[topic], "message_index": self.message_index[topic], "received_steady_ns": time.monotonic_ns()}
        if topic == "/clock":
            metadata["ros_stamp_ns"] = stamp_ns(message.clock)
        elif topic in ("/ground_truth/odom", "/scan"):
            metadata["ros_stamp_ns"] = stamp_ns(message.header.stamp)
            metadata["frame_id"] = str(message.header.frame_id)
            if topic == "/ground_truth/odom":
                metadata["child_frame_id"] = str(message.child_frame_id)
            if topic == "/scan":
                metadata["scan_sanity"] = scan_sanity(message)
        self.latest[topic] = metadata
        if not self.capture_enabled:
            return
        record = {
            "run_id": self.run_id,
            "stream": topic,
            "record_kind": record_kind,
            **metadata,
            "payload": message_payload(message),
        }
        self.trace_file.write(json.dumps(record, sort_keys=True, allow_nan=False) + "\n")
        self.trace_file.flush()

    def clock_callback(self, message):
        self.write_record("/clock", message, "clock")

    def gt_odom_callback(self, message):
        self.write_record("/ground_truth/odom", message, "odometry")


    def scan_callback(self, message):
        self.write_record("/scan", message, "scan")


    def close(self):
        self.trace_file.close()


def spin_for(node, seconds):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline and not node.interrupted:
        rclpy.spin_once(node, timeout_sec=0.1)


def request_for(probe):
    probe_id, x, y, z, yaw = probe
    request = SetEntityPose.Request()
    request.entity.name = ENTITY_NAME
    request.entity.type = Entity.MODEL
    request.pose.position.x = x
    request.pose.position.y = y
    request.pose.position.z = z
    request.pose.orientation.x = 0.0
    request.pose.orientation.y = 0.0
    request.pose.orientation.z = math.sin(yaw / 2.0)
    request.pose.orientation.w = math.cos(yaw / 2.0)
    return probe_id, request


def main():
    parser = argparse.ArgumentParser(description="One approved controlled coordinate measurement")
    parser.add_argument("--offline-bootstrap-self-test", action="store_true")
    parser.add_argument("--run-id")
    parser.add_argument("--run-dir")
    parser.add_argument("--warmup-seconds", type=float, default=10.0)
    parser.add_argument("--post-probe-guard-seconds", type=float, default=10.0)
    parser.add_argument("--topic-wait-seconds", type=float, default=90.0)
    parser.add_argument("--preflight-deadline-steady-ns", type=int)
    args = parser.parse_args()
    if args.offline_bootstrap_self_test:
        return offline_bootstrap_self_test()
    if not args.run_id or not args.run_dir:
        parser.error("--run-id and --run-dir are required unless --offline-bootstrap-self-test is used")
    if args.warmup_seconds != 10.0 or args.post_probe_guard_seconds != 10.0 or args.topic_wait_seconds != 90.0:
        raise ValueError("only the approved 10-second guards and 90-second preflight stop guard are allowed")

    run_dir = Path(args.run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    rclpy.init()
    node = ControlledMeasurementCollector(args.run_id, run_dir)
    invalid_reasons = []
    sent = []
    request_records = []

    def on_signal(_signum, _frame):
        node.interrupted = True

    signal.signal(signal.SIGINT, on_signal)
    signal.signal(signal.SIGTERM, on_signal)
    started_utc_ns = time.time_ns()
    try:
        pre_snapshot = None
        pre_service_snapshot = None
        local_deadline = time.monotonic() + args.topic_wait_seconds
        deadline = min(local_deadline, args.preflight_deadline_steady_ns / 1_000_000_000) if args.preflight_deadline_steady_ns else local_deadline
        if deadline <= time.monotonic():
            invalid_reasons.append("shared preflight stop guard expired before collector started")
        while not invalid_reasons and time.monotonic() < deadline and not node.interrupted:
            candidate = node.graph_snapshot()
            candidate_service = node.service_graph_snapshot()
            if (node.graph_ready(candidate)
                    and node.cmd_vel_allowlist_resolved(candidate)
                    and node.exact_pose_service_ready(candidate_service)
                    and node.pose_client.service_is_ready()):
                pre_snapshot = candidate
                pre_service_snapshot = candidate_service
                break
            rclpy.spin_once(node, timeout_sec=0.2)
        if pre_snapshot is None:
            pre_snapshot = node.graph_snapshot()
            pre_service_snapshot = node.service_graph_snapshot()
            if not node.graph_ready(pre_snapshot) or not node.cmd_vel_allowlist_resolved(pre_snapshot):
                invalid_reasons.append("scoped graph/type metadata incomplete before measurement")
            if not (node.exact_pose_service_ready(pre_service_snapshot) and node.pose_client.service_is_ready()):
                invalid_reasons.append("SetEntityPose service unavailable or type mismatch")
        allowlist = canonical(pre_snapshot["/cmd_vel"]["publishers"])
        if not invalid_reasons:
            spin_for(node, args.warmup_seconds)
            startup_baseline = node.barrier()
            if any(startup_baseline["streams"][topic] is None for topic in SCOPED_TYPES):
                invalid_reasons.append("missing startup baseline stream metadata")
        else:
            startup_baseline = node.barrier()
        node.capture_enabled = not invalid_reasons
        for call_order, probe in enumerate(APPROVED_PROBES, 1):
            if invalid_reasons or node.interrupted:
                break
            before_graph = node.graph_snapshot()
            before_service_graph = node.service_graph_snapshot()
            if (not node.graph_ready(before_graph) or not node.cmd_vel_allowlist_resolved(before_graph)
                    or not node.exact_pose_service_ready(before_service_graph)
                    or not node.pose_client.service_is_ready()
                    or canonical(before_graph["/cmd_vel"]["publishers"]) != allowlist):
                invalid_reasons.append("graph/type, exact pose-service, or frozen cmd_vel allowlist invalid before " + probe[0])
                break
            pre_call_streams = {topic: node.latest[topic] for topic in SCOPED_TYPES}
            pre_call_steady_ns = time.monotonic_ns()
            barrier = {"captured_steady_ns": pre_call_steady_ns, "streams": pre_call_streams}
            probe_id, request = request_for(probe)
            future = node.pose_client.call_async(request)
            ros_request_dispatched_steady_ns = time.monotonic_ns()
            sent.append(probe_id)
            probe_deadline = time.monotonic() + args.post_probe_guard_seconds
            while time.monotonic() < probe_deadline and not future.done() and not node.interrupted:
                rclpy.spin_once(node, timeout_sec=0.1)
            if not future.done():
                request_records.append({"probe_id": probe_id, "call_order": call_order, "entity": ENTITY_NAME, "request": message_payload(request), "barrier": barrier, "pre_call_steady_ns": pre_call_steady_ns, "ros_request_dispatched_steady_ns": ros_request_dispatched_steady_ns, "ros_response_received_steady_ns": None, "post_response_barrier_steady_ns": None, "response": None, "error": "service response not received before administrative stop guard"})
                invalid_reasons.append("service response unavailable for " + probe_id)
                break
            ros_response_received_steady_ns = time.monotonic_ns()
            try:
                response = future.result()
            except Exception as exc:
                request_records.append({"probe_id": probe_id, "call_order": call_order, "entity": ENTITY_NAME, "request": message_payload(request), "barrier": barrier, "pre_call_steady_ns": pre_call_steady_ns, "ros_request_dispatched_steady_ns": ros_request_dispatched_steady_ns, "ros_response_received_steady_ns": ros_response_received_steady_ns, "post_response_barrier_steady_ns": None, "response": None, "error": repr(exc)})
                invalid_reasons.append("service exception for " + probe_id)
                break
            record = {"probe_id": probe_id, "call_order": call_order, "entity": ENTITY_NAME, "request": message_payload(request), "barrier": barrier, "pre_call_steady_ns": pre_call_steady_ns, "ros_request_dispatched_steady_ns": ros_request_dispatched_steady_ns, "ros_response_received_steady_ns": ros_response_received_steady_ns, "post_response_barrier_steady_ns": None, "pre_probe_service_graph_snapshot": before_service_graph, "response": message_payload(response), "error": None}
            request_records.append(record)
            if not bool(response.success):
                invalid_reasons.append("SetEntityPose rejected " + probe_id)
                break
            post_response_barrier = node.barrier()
            record["post_response_barrier"] = post_response_barrier
            record["post_response_barrier_steady_ns"] = post_response_barrier["captured_steady_ns"]
            if not (pre_call_steady_ns <= ros_request_dispatched_steady_ns <= ros_response_received_steady_ns <= record["post_response_barrier_steady_ns"]):
                invalid_reasons.append("steady-clock provenance ordering invalid for " + probe_id)
                break
            while time.monotonic() < probe_deadline and not node.interrupted:
                rclpy.spin_once(node, timeout_sec=0.1)
            latest_gt = node.latest["/ground_truth/odom"]
            latest_scan = node.latest["/scan"]
            if latest_gt is None or latest_gt["received_steady_ns"] <= record["post_response_barrier_steady_ns"]:
                invalid_reasons.append("no GT received after post-response barrier for " + probe_id)
                break
            if (latest_scan is None
                    or latest_scan["received_steady_ns"] <= record["post_response_barrier_steady_ns"]
                    or not latest_scan.get("scan_sanity", {}).get("valid", False)):
                invalid_reasons.append("INVALID_FOR_SCAN_SUITABILITY after " + probe_id)
                break
            record["post_response_gt_metadata"] = latest_gt
            record["post_response_scan_metadata"] = latest_scan
            after_graph = node.graph_snapshot()
            after_service_graph = node.service_graph_snapshot()
            record["post_probe_graph_snapshot"] = after_graph
            record["post_probe_service_graph_snapshot"] = after_service_graph
            record["post_probe_barrier"] = node.barrier()
            if (not node.graph_ready(after_graph) or not node.cmd_vel_allowlist_resolved(after_graph)
                    or not node.exact_pose_service_ready(after_service_graph)
                    or not node.pose_client.service_is_ready()
                    or canonical(after_graph["/cmd_vel"]["publishers"]) != allowlist):
                invalid_reasons.append("graph/type, exact pose-service, or frozen cmd_vel allowlist invalid after " + probe_id)
                break
        node.capture_enabled = False
        post_snapshot = node.graph_snapshot()
        post_service_snapshot = node.service_graph_snapshot()
        if node.interrupted:
            invalid_reasons.append("collector interrupted")
        if not node.graph_ready(post_snapshot) or not node.cmd_vel_allowlist_resolved(post_snapshot):
            invalid_reasons.append("scoped graph/type metadata incomplete after measurement")
        if not node.exact_pose_service_ready(post_service_snapshot):
            invalid_reasons.append("exact SetEntityPose service graph/type incomplete after measurement")
        if canonical(post_snapshot["/cmd_vel"]["publishers"]) != allowlist:
            invalid_reasons.append("cmd_vel publisher allowlist changed during measurement")
        metadata = {
            "schema_version": "s3_candidate_b_controlled_suitability/v1",
            "run_id": args.run_id,
            "started_utc_ns": started_utc_ns,
            "ended_utc_ns": time.time_ns(),
            "scope": "one user-approved Candidate B Gazebo simulation-only suitability measurement",
            "entity": ENTITY_NAME,
            "pose_service": POSE_SERVICE,
            "pose_service_type": POSE_SERVICE_TYPE,
            "approved_probe_order": [item[0] for item in APPROVED_PROBES],
            "approved_probes": [{"probe_id": name, "x": x, "y": y, "z": z, "yaw_rad": yaw} for name, x, y, z, yaw in APPROVED_PROBES],
            "sent_probe_order": sent,
            "warmup_seconds": args.warmup_seconds,
            "post_probe_administrative_guard_seconds": args.post_probe_guard_seconds,
            "topic_wait_seconds": args.topic_wait_seconds,
            "preflight_deadline_steady_ns": args.preflight_deadline_steady_ns,
            "topic_wait_classification": "USER_APPROVED_PREFLIGHT_STOP_GUARD; not a settle, freshness, reset, or measurement-acceptance policy",
            "clock_domain_policy": "ROS/simulation stamps and steady receive timestamps are retained separately and never subtracted across domains.",
            "pre_run_graph_snapshot": pre_snapshot,
            "pre_run_service_graph_snapshot": pre_service_snapshot,
            "frozen_cmd_vel_allowlist": allowlist,
            "post_run_graph_snapshot": post_snapshot,
            "post_run_service_graph_snapshot": post_service_snapshot,
            "startup_baseline": startup_baseline,
            "collector_cmd_vel_publishers_created": False,
            "collector_published_command": False,
            "collector_control_services_called": [],
            "collector_created_clients": [{"service": POSE_SERVICE, "type": POSE_SERVICE_TYPE}],
            "run_status": "INVALID" if invalid_reasons else "VALID",
            "invalid_reasons": invalid_reasons,
        }
        (run_dir / "capture_metadata.json").write_text(json.dumps(metadata, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
        (run_dir / "request_response_records.json").write_text(json.dumps(request_records, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
        (run_dir / "pre_run_graph_snapshot.json").write_text(json.dumps(pre_snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        (run_dir / "pre_run_service_graph_snapshot.json").write_text(json.dumps(pre_service_snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        (run_dir / "post_run_graph_snapshot.json").write_text(json.dumps(post_snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        (run_dir / "post_run_service_graph_snapshot.json").write_text(json.dumps(post_service_snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        for record in request_records:
            (run_dir / (record["probe_id"] + "_summary.json")).write_text(json.dumps(record, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
        print(json.dumps({"run_id": args.run_id, "status": metadata["run_status"], "sent_probes": sent, "reasons": invalid_reasons}))
        return 0 if not invalid_reasons else 2
    finally:
        node.close()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    sys.exit(main())
