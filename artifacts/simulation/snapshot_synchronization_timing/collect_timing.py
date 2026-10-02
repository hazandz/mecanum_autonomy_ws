#!/usr/bin/env python3
"""Read-only ROS 2 timing collector for /scan and /odom."""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import rclpy
from nav_msgs.msg import Odometry
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import LaserScan


class TimingCollector(Node):
    """Subscribe only to timing-relevant scan and odometry message headers."""

    def __init__(self, trace_path: Path) -> None:
        super().__init__("snapshot_synchronization_timing_collector")
        self._trace_file = trace_path.open("w", encoding="utf-8")
        self._counts = {"scan": 0, "odom": 0}
        self.create_subscription(
            LaserScan, "/scan", self._on_scan, qos_profile_sensor_data
        )
        self.create_subscription(
            Odometry, "/odom", self._on_odom, qos_profile_sensor_data
        )

    @property
    def counts(self) -> dict[str, int]:
        """Return copied callback counts."""

        return dict(self._counts)

    def close_trace(self) -> None:
        """Flush the append-only trace before process exit."""

        self._trace_file.close()

    def _on_scan(self, message: LaserScan) -> None:
        self._record("scan", message.header.stamp.sec, message.header.stamp.nanosec)

    def _on_odom(self, message: Odometry) -> None:
        self._record("odom", message.header.stamp.sec, message.header.stamp.nanosec)

    def _record(self, stream: str, seconds: int, nanoseconds: int) -> None:
        self._counts[stream] += 1
        record = {
            "stream": stream,
            "stamp_ns": seconds * 1_000_000_000 + nanoseconds,
            "receive_steady_ns": time.monotonic_ns(),
            "message_index": self._counts[stream],
        }
        self._trace_file.write(json.dumps(record, separators=(",", ":")) + "\n")
        self._trace_file.flush()


def parse_arguments() -> argparse.Namespace:
    """Parse bounded, read-only capture controls."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--minimum-duration-s", type=float, default=60.0)
    parser.add_argument("--minimum-scan-count", type=int, default=200)
    parser.add_argument("--hard-timeout-s", type=float, default=180.0)
    return parser.parse_args()


def main() -> int:
    """Capture only message-header and local receive-time timing evidence."""

    arguments = parse_arguments()
    if arguments.minimum_duration_s <= 0.0:
        raise ValueError("minimum-duration-s must be positive")
    if arguments.minimum_scan_count <= 0:
        raise ValueError("minimum-scan-count must be positive")
    if arguments.hard_timeout_s < arguments.minimum_duration_s:
        raise ValueError("hard-timeout-s must be at least minimum-duration-s")

    arguments.output_dir.mkdir(parents=True, exist_ok=True)
    trace_path = arguments.output_dir / "trace.jsonl"
    metadata_path = arguments.output_dir / "capture_metadata.json"
    started_steady_ns = time.monotonic_ns()
    started_utc = datetime.now(timezone.utc).isoformat()

    rclpy.init()
    collector = TimingCollector(trace_path)
    termination = "hard_timeout_without_minimum"
    try:
        while True:
            rclpy.spin_once(collector, timeout_sec=0.1)
            elapsed_s = (time.monotonic_ns() - started_steady_ns) / 1_000_000_000
            if (
                elapsed_s >= arguments.minimum_duration_s
                and collector.counts["scan"] >= arguments.minimum_scan_count
            ):
                termination = "minimum_duration_and_scan_count_reached"
                break
            if elapsed_s >= arguments.hard_timeout_s:
                break
    finally:
        ended_steady_ns = time.monotonic_ns()
        ended_utc = datetime.now(timezone.utc).isoformat()
        counts = collector.counts
        collector.close_trace()
        collector.destroy_node()
        rclpy.shutdown()

    metadata: dict[str, Any] = {
        "captured_at_utc": started_utc,
        "finished_at_utc": ended_utc,
        "duration_steady_ns": ended_steady_ns - started_steady_ns,
        "termination": termination,
        "minimum_duration_s": arguments.minimum_duration_s,
        "minimum_scan_count": arguments.minimum_scan_count,
        "hard_timeout_s": arguments.hard_timeout_s,
        "counts": counts,
        "subscriptions": {
            "/scan": "sensor_msgs/msg/LaserScan",
            "/odom": "nav_msgs/msg/Odometry",
        },
        "publisher_operations": 0,
        "service_operations": 0,
    }
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(metadata, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
