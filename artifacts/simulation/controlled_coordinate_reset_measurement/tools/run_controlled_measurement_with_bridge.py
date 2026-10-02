#!/usr/bin/env python3
"""Run one approved Gazebo-only pose measurement with one temporary bridge.

This artifact-owned supervisor starts only the existing Gazebo launch and the
single approved ``SetEntityPose`` service bridge.  It delegates all ROS graph
inspection, subscriptions, and the three immutable pose requests to the
collector.  It creates no publishers, action clients, or control clients.
"""

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENTITY_NAME = "ROBOT_URDF_final"
POSE_SERVICE = "/world/world_demo/set_pose"
POSE_SERVICE_TYPE = "ros_gz_interfaces/srv/SetEntityPose"
BRIDGE_ARGUMENT = (
    "/world/world_demo/set_pose@ros_gz_interfaces/srv/SetEntityPose@"
    "gz.msgs.Pose@gz.msgs.Boolean"
)
GAZEBO_COMMAND = ["ros2", "launch", "ROBOT_URDF_final_description", "gazebo.launch.py"]
BRIDGE_COMMAND = ["ros2", "run", "ros_gz_bridge", "parameter_bridge", BRIDGE_ARGUMENT]
APPROVED_PROBES = (
    ("P0", -4.0, -3.0, 0.1, 0.0),
    ("P1", -4.0, 0.0, 0.1, 1.57079632679),
    ("P2", -2.0, -3.0, 0.1, -1.57079632679),
)
PREFLIGHT_STOP_GUARD_SECONDS = 90


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def stop_process(process, name: str) -> dict:
    if process is None:
        return {"name": name, "started": False}
    record = {"name": name, "pid": process.pid, "sigint_sent_utc_ns": time.time_ns()}
    if process.poll() is None:
        process.send_signal(signal.SIGINT)
        try:
            record["exit_status"] = process.wait(timeout=20)
        except subprocess.TimeoutExpired:
            record["sigkill_sent_utc_ns"] = time.time_ns()
            process.kill()
            record["exit_status"] = process.wait(timeout=10)
    else:
        record["exit_status"] = process.returncode
    record["stopped_utc_ns"] = time.time_ns()
    return record


def transport_pose_service_ready(log_path: Path) -> bool:
    """Read Gazebo transport service inventory; never invoke a service."""
    try:
        result = subprocess.run(
            ["gz", "service", "-l"], capture_output=True, text=True, timeout=5, check=False
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(f"{time.time_ns()} gz service -l error: {exc!r}\n")
        return False
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(f"{time.time_ns()} exit={result.returncode}\n{result.stdout}{result.stderr}\n")
    return result.returncode == 0 and POSE_SERVICE in result.stdout.splitlines()


def main() -> int:
    parser = argparse.ArgumentParser(description="One approved controlled simulation measurement supervisor")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--replacement-run", action="store_true")
    args = parser.parse_args()
    if not args.replacement_run:
        raise RuntimeError("replacement-run authorization flag is required")
    if BRIDGE_COMMAND != ["ros2", "run", "ros_gz_bridge", "parameter_bridge", BRIDGE_ARGUMENT]:
        raise RuntimeError("bridge command changed from the sole approved service argument")
    if tuple(item[0] for item in APPROVED_PROBES) != ("P0", "P1", "P2"):
        raise RuntimeError("probe order changed")

    run_dir = ROOT / args.run_id
    if run_dir.exists():
        raise RuntimeError(f"run directory already exists: {run_dir}")
    run_dir.mkdir(parents=True)
    ros_log_dir = run_dir / "ros_logs"
    ros_log_dir.mkdir()
    environment = os.environ.copy()
    environment["ROS_LOG_DIR"] = str(ros_log_dir)
    lifecycle = {
        "schema_version": "s3_controlled_measurement_bridge_lifecycle/v2_post_response_provenance",
        "run_id": args.run_id,
        "scope": "one user-approved replacement Gazebo simulation-only measurement with post-response provenance",
        "entity": ENTITY_NAME,
        "approved_probes": [
            {"probe_id": name, "x": x, "y": y, "z": z, "yaw_rad": yaw}
            for name, x, y, z, yaw in APPROVED_PROBES
        ],
        "preflight_stop_guard": {
            "topic_wait_seconds": PREFLIGHT_STOP_GUARD_SECONDS,
            "classification": "PREFLIGHT_STOP_GUARD; not a settle, freshness, reset, or measurement policy",
        },
        "gazebo": {"command": GAZEBO_COMMAND, "started_utc_ns": None},
        "bridge": {
            "owner": "measurement artifact",
            "command": BRIDGE_COMMAND,
            "argument": BRIDGE_ARGUMENT,
            "service_name": POSE_SERVICE,
            "service_type": POSE_SERVICE_TYPE,
            "topic_bridge_count": 0,
            "service_bridge_count": 1,
            "started_utc_ns": None,
        },
    }
    write_json(run_dir / "supervisor_metadata.json", lifecycle)
    transport_log = run_dir / "gazebo_transport_service_inventory.log"
    started_monotonic_ns = time.monotonic_ns()
    deadline = started_monotonic_ns + PREFLIGHT_STOP_GUARD_SECONDS * 1_000_000_000
    gazebo = bridge = None
    exit_code = 2
    try:
        with (run_dir / "gazebo_stdout.log").open("w", encoding="utf-8") as stdout, (run_dir / "gazebo_stderr.log").open("w", encoding="utf-8") as stderr:
            gazebo = subprocess.Popen(GAZEBO_COMMAND, stdout=stdout, stderr=stderr, env=environment)
            lifecycle["gazebo"].update({"pid": gazebo.pid, "started_utc_ns": time.time_ns()})
            write_json(run_dir / "supervisor_metadata.json", lifecycle)
            while time.monotonic_ns() < deadline and gazebo.poll() is None:
                if transport_pose_service_ready(transport_log):
                    break
                time.sleep(0.5)
            else:
                lifecycle["preflight_result"] = "INVALID: Gazebo transport pose service was not observed before the approved stop guard"
                return 2
        with (run_dir / "bridge_stdout.log").open("w", encoding="utf-8") as stdout, (run_dir / "bridge_stderr.log").open("w", encoding="utf-8") as stderr:
            bridge = subprocess.Popen(BRIDGE_COMMAND, stdout=stdout, stderr=stderr, env=environment)
            lifecycle["bridge"].update({"pid": bridge.pid, "started_utc_ns": time.time_ns()})
            write_json(run_dir / "supervisor_metadata.json", lifecycle)
            collector = [
                sys.executable,
                str(ROOT / "tools" / "controlled_measurement_collector.py"),
                "--run-id", args.run_id,
                "--run-dir", str(run_dir),
                "--topic-wait-seconds", "90",
                "--preflight-deadline-steady-ns", str(deadline),
            ]
            with (run_dir / "collector_stdout.log").open("w", encoding="utf-8") as stdout_collector, (run_dir / "collector_stderr.log").open("w", encoding="utf-8") as stderr_collector:
                result = subprocess.run(collector, stdout=stdout_collector, stderr=stderr_collector, env=environment, check=False)
            lifecycle["collector"] = {"command": collector, "exit_status": result.returncode, "ended_utc_ns": time.time_ns()}
            exit_code = result.returncode
    finally:
        lifecycle["bridge_shutdown"] = stop_process(bridge, "temporary_measurement_owned_bridge")
        lifecycle["gazebo_shutdown"] = stop_process(gazebo, "measurement_owned_gazebo")
        lifecycle["ended_utc_ns"] = time.time_ns()
        write_json(run_dir / "supervisor_metadata.json", lifecycle)
        metadata_path = run_dir / "capture_metadata.json"
        if metadata_path.exists():
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            metadata["bridge_lifecycle"] = lifecycle["bridge"] | {"shutdown": lifecycle["bridge_shutdown"]}
            metadata["gazebo_lifecycle"] = lifecycle["gazebo"] | {"shutdown": lifecycle["gazebo_shutdown"]}
            metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            analyzer = [sys.executable, str(ROOT / "tools" / "analyze_controlled_measurement.py"), "--run-dir", str(run_dir)]
            subprocess.run(analyzer, env=environment, check=False)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
