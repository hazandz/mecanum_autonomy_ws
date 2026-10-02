#!/usr/bin/env python3
"""Subscriber-only S3 passive stream collector outside production packages."""

import argparse
import json
import signal
import sys
import time
from pathlib import Path

import rclpy
from nav_msgs.msg import Odometry
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from rosgraph_msgs.msg import Clock
from sensor_msgs.msg import LaserScan
from tf2_msgs.msg import TFMessage

SCOPED_TYPES = {
    "/clock": "rosgraph_msgs/msg/Clock",
    "/ground_truth/odom": "nav_msgs/msg/Odometry",
    "/odom": "nav_msgs/msg/Odometry",
    "/scan": "sensor_msgs/msg/LaserScan",
    "/tf": "tf2_msgs/msg/TFMessage",
}


def stamp_ns(stamp):
    return int(stamp.sec) * 1_000_000_000 + int(stamp.nanosec)


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
    return sorted(records, key=lambda value: json.dumps(value, sort_keys=True))


class PassiveCollector(Node):
    """This node creates subscriptions only. No publisher or control client exists."""

    def __init__(self, run_id, run_dir):
        super().__init__("s3_passive_stream_collector")
        self.run_id = run_id
        self.run_dir = run_dir
        self.trace_file = (run_dir / "stream_trace.jsonl").open("w", encoding="utf-8")
        self.capture_enabled = False
        self.interrupted = False
        self.message_index = {topic: 0 for topic in SCOPED_TYPES}
        self.record_count = {topic: 0 for topic in SCOPED_TYPES}
        self.create_subscription(Clock, "/clock", self.clock_callback, qos_profile_sensor_data)
        self.create_subscription(Odometry, "/ground_truth/odom", self.gt_odom_callback, qos_profile_sensor_data)
        self.create_subscription(Odometry, "/odom", self.odom_callback, qos_profile_sensor_data)
        self.create_subscription(LaserScan, "/scan", self.scan_callback, qos_profile_sensor_data)
        self.create_subscription(TFMessage, "/tf", self.tf_callback, qos_profile_sensor_data)

    def graph_snapshot(self):
        names_and_types = dict(self.get_topic_names_and_types())
        snapshot = {}
        for topic, expected in SCOPED_TYPES.items():
            publishers = canonical([endpoint_record(info) for info in self.get_publishers_info_by_topic(topic)])
            snapshot[topic] = {
                "expected_type": expected,
                "observed_types": sorted(names_and_types.get(topic, [])),
                "publisher_count": len(publishers),
                "publishers": publishers,
            }
        command_publishers = canonical([endpoint_record(info) for info in self.get_publishers_info_by_topic("/cmd_vel")])
        snapshot["/cmd_vel"] = {
            "observed_types": sorted(names_and_types.get("/cmd_vel", [])),
            "publisher_count": len(command_publishers),
            "publishers": command_publishers,
        }
        return snapshot

    def graph_ready(self, snapshot):
        return all(
            expected in snapshot[topic]["observed_types"] and snapshot[topic]["publisher_count"] > 0
            for topic, expected in SCOPED_TYPES.items()
        )

    def cmd_vel_allowlist_resolved(self, snapshot):
        publishers = snapshot["/cmd_vel"]["publishers"]
        return all(
            item["node_name"] != "_NODE_NAME_UNKNOWN_"
            and item["node_namespace"] != "_NODE_NAMESPACE_UNKNOWN_"
            and bool(item["topic_type"])
            for item in publishers
        )

    def write_record(self, topic, details):
        if not self.capture_enabled:
            return
        self.message_index[topic] += 1
        self.record_count[topic] += 1
        record = {
            "run_id": self.run_id,
            "stream": topic,
            "index": self.record_count[topic],
            "message_index": self.message_index[topic],
            "received_steady_ns": time.monotonic_ns(),
        }
        record.update(details)
        self.trace_file.write(json.dumps(record, sort_keys=True, allow_nan=False) + "\n")
        self.trace_file.flush()

    def clock_callback(self, message):
        self.write_record("/clock", {"record_kind": "clock", "ros_stamp_ns": stamp_ns(message.clock)})

    def odometry_record(self, topic, message):
        self.write_record(topic, {
            "record_kind": "odometry",
            "ros_stamp_ns": stamp_ns(message.header.stamp),
            "frame_id": str(message.header.frame_id),
            "child_frame_id": str(message.child_frame_id),
            "pose_twist_present": True,
        })

    def gt_odom_callback(self, message):
        self.odometry_record("/ground_truth/odom", message)

    def odom_callback(self, message):
        self.odometry_record("/odom", message)

    def scan_callback(self, message):
        self.write_record("/scan", {
            "record_kind": "scan",
            "ros_stamp_ns": stamp_ns(message.header.stamp),
            "frame_id": str(message.header.frame_id),
            "range_count": len(message.ranges),
            "angle_min_rad": float(message.angle_min),
            "angle_increment_rad": float(message.angle_increment),
            "range_min_m": float(message.range_min),
            "range_max_m": float(message.range_max),
        })

    def tf_callback(self, message):
        if not self.capture_enabled:
            return
        self.message_index["/tf"] += 1
        message_index = self.message_index["/tf"]
        for transform_index, transform in enumerate(message.transforms):
            self.record_count["/tf"] += 1
            record = {
                "run_id": self.run_id,
                "stream": "/tf",
                "index": self.record_count["/tf"],
                "message_index": message_index,
                "transform_index": transform_index,
                "record_kind": "transform",
                "ros_stamp_ns": stamp_ns(transform.header.stamp),
                "frame_id": str(transform.header.frame_id),
                "child_frame_id": str(transform.child_frame_id),
                "received_steady_ns": time.monotonic_ns(),
            }
            self.trace_file.write(json.dumps(record, sort_keys=True, allow_nan=False) + "\n")
        self.trace_file.flush()

    def close(self):
        self.trace_file.close()


def spin_for(node, duration):
    deadline = time.monotonic() + duration
    while time.monotonic() < deadline and not node.interrupted:
        rclpy.spin_once(node, timeout_sec=0.1)


def main():
    parser = argparse.ArgumentParser(description="S3 passive subscriber-only collector")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--warmup-seconds", type=float, default=10.0)
    parser.add_argument("--capture-seconds", type=float, default=60.0)
    parser.add_argument("--topic-wait-seconds", type=float, default=90.0)
    args = parser.parse_args()
    if args.warmup_seconds < 0 or args.capture_seconds < 60 or args.topic_wait_seconds <= 0:
        raise ValueError("invalid capture duration")

    run_dir = Path(args.run_dir)
    run_dir.mkdir(parents=True, exist_ok=False)
    rclpy.init()
    node = PassiveCollector(args.run_id, run_dir)

    def on_signal(_signum, _frame):
        node.interrupted = True

    signal.signal(signal.SIGINT, on_signal)
    signal.signal(signal.SIGTERM, on_signal)
    started_utc_ns = time.time_ns()
    invalid_reasons = []
    try:
        pre_snapshot = None
        deadline = time.monotonic() + args.topic_wait_seconds
        while time.monotonic() < deadline and not node.interrupted:
            candidate = node.graph_snapshot()
            if node.graph_ready(candidate) and node.cmd_vel_allowlist_resolved(candidate):
                pre_snapshot = candidate
                break
            rclpy.spin_once(node, timeout_sec=0.2)
        if pre_snapshot is None:
            pre_snapshot = node.graph_snapshot()
            invalid_reasons.append("scoped stream missing, type mismatch, or publisher unavailable")
        allowlist = canonical(pre_snapshot["/cmd_vel"]["publishers"])
        if not invalid_reasons and not node.interrupted:
            spin_for(node, args.warmup_seconds)
            node.capture_enabled = True
            spin_for(node, args.capture_seconds)
            node.capture_enabled = False
        post_snapshot = node.graph_snapshot()
        if node.interrupted:
            invalid_reasons.append("collector interrupted before clean capture completion")
        if not node.graph_ready(post_snapshot) or not node.cmd_vel_allowlist_resolved(post_snapshot):
            invalid_reasons.append("post-run scoped graph/type snapshot incomplete")
        if canonical(post_snapshot["/cmd_vel"]["publishers"]) != allowlist:
            invalid_reasons.append("cmd_vel publisher allowlist changed during run")
        missing = [topic for topic, count in node.record_count.items() if count == 0]
        if missing:
            invalid_reasons.append("no captured records for: " + ", ".join(missing))
        metadata = {
            "schema_version": "s3_passive_stream_timing_run/v1",
            "run_id": args.run_id,
            "started_utc_ns": started_utc_ns,
            "ended_utc_ns": time.time_ns(),
            "warmup_seconds": args.warmup_seconds,
            "capture_seconds_requested": args.capture_seconds,
            "topic_wait_seconds": args.topic_wait_seconds,
            "scoped_topics": SCOPED_TYPES,
            "pre_capture_graph_snapshot": pre_snapshot,
            "frozen_cmd_vel_allowlist": allowlist,
            "post_run_graph_snapshot": post_snapshot,
            "cmd_vel_allowlist_changed": canonical(post_snapshot["/cmd_vel"]["publishers"]) != allowlist,
            "collector_cmd_vel_publishers_created": False,
            "collector_published_command": False,
            "collector_control_service_called": False,
            "capture_record_counts": node.record_count,
            "run_status": "INVALID" if invalid_reasons else "VALID",
            "invalid_reasons": invalid_reasons,
            "note": "Subscriber-only collector; no publisher, service client, or action client is created.",
        }
        (run_dir / "capture_metadata.json").write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        (run_dir / "summary.json").write_text(json.dumps({
            "run_id": args.run_id,
            "run_status": metadata["run_status"],
            "invalid_reasons": invalid_reasons,
            "capture_record_counts": node.record_count,
        }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps({"run_id": args.run_id, "status": metadata["run_status"], "reasons": invalid_reasons}))
        return 0 if not invalid_reasons else 2
    finally:
        node.close()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    sys.exit(main())
