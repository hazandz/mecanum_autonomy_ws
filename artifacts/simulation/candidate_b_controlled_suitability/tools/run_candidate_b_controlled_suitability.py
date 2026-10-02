#!/usr/bin/env python3
"""Run one approved Candidate B Gazebo-only suitability measurement with one temporary bridge.

This artifact-owned supervisor starts only the existing Gazebo launch and the
single approved ``SetEntityPose`` service bridge.  It delegates all ROS graph
inspection, subscriptions, and the three immutable pose requests to the
collector.  It creates no publishers, action clients, or control clients.
"""

import argparse
import hashlib
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
    ("B0_START_P0", -4.0, -3.0, 0.1, 0.0),
    ("B1_GOAL_P2", -2.0, -3.0, 0.1, -1.57079632679),
    ("B2_RECT_LL", -4.5, -3.5, 0.1, 0.0),
    ("B3_RECT_LR", -1.5, -3.5, 0.1, 0.0),
    ("B4_RECT_UR", -1.5, -2.5, 0.1, 0.0),
    ("B5_RECT_UL", -4.5, -2.5, 0.1, 0.0),
)
PREFLIGHT_STOP_GUARD_SECONDS = 90
WORLD_FILE = ROOT.parents[2] / "ros2_ws/src/ROBOT_URDF_final_description/launch/tugbot_depot.sdf"
EXPECTED_WORLD_SHA256 = "a5e9c9b1e9b8ad11e0399855f06de687f04c702258b8b74ce563523d78ed55fe"


def world_sha256() -> str:
    return hashlib.sha256(WORLD_FILE.read_bytes()).hexdigest()


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


SHUTDOWN_BLOCKER = ROOT / "SHUTDOWN_INCOMPLETE"


def stop_process(process, name: str) -> dict:
    """Use SIGINT only; no escalation is permitted."""
    if process is None:
        return {"name": name, "started": False, "shutdown_complete": True}
    record = {
        "name": name,
        "pid": process.pid,
        "signal": "SIGINT",
        "sigint_sent_utc_ns": time.time_ns(),
        "process_group": process.pid,
    }
    if process.poll() is None:
        os.killpg(process.pid, signal.SIGINT)
        try:
            record["exit_status"] = process.wait(timeout=20)
            record["shutdown_complete"] = True
        except subprocess.TimeoutExpired:
            record["shutdown_complete"] = False
            record["shutdown_status"] = "SHUTDOWN_INCOMPLETE"
            record["operator_decision_required"] = True
            return record
    else:
        record["exit_status"] = process.returncode
        record["shutdown_complete"] = True
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
    parser.add_argument("--candidate-b-run", action="store_true")
    args = parser.parse_args()
    if not args.candidate_b_run:
        raise RuntimeError("Candidate B authorization flag is required")
    if SHUTDOWN_BLOCKER.exists():
        raise RuntimeError("replacement run blocked: SHUTDOWN_INCOMPLETE requires user/operator decision")
    if BRIDGE_COMMAND != ["ros2", "run", "ros_gz_bridge", "parameter_bridge", BRIDGE_ARGUMENT]:
        raise RuntimeError("bridge command changed from the sole approved service argument")
    if tuple(item[0] for item in APPROVED_PROBES) != ("B0_START_P0", "B1_GOAL_P2", "B2_RECT_LL", "B3_RECT_LR", "B4_RECT_UR", "B5_RECT_UL"):
        raise RuntimeError("probe order changed")
    if not WORLD_FILE.is_file() or world_sha256() != EXPECTED_WORLD_SHA256:
        raise RuntimeError("world file missing or SHA-256 differs from the approved literal")

    run_dir = ROOT / args.run_id
    if run_dir.exists():
        raise RuntimeError(f"run directory already exists: {run_dir}")
    run_dir.mkdir(parents=True)
    ros_log_dir = run_dir / "ros_logs"
    ros_log_dir.mkdir()
    environment = os.environ.copy()
    environment["ROS_LOG_DIR"] = str(ros_log_dir)
    lifecycle = {
        "schema_version": "s3_candidate_b_controlled_suitability/v1",
        "run_id": args.run_id,
        "scope": "one user-approved Candidate B Gazebo simulation-only suitability measurement",
        "entity": ENTITY_NAME,
        "world": {
            "gazebo_world_name": "world_demo",
            "world_file": str(WORLD_FILE),
            "sha256": world_sha256(),
            "expected_sha256": EXPECTED_WORLD_SHA256,
        },
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
            gazebo = subprocess.Popen(GAZEBO_COMMAND, stdout=stdout, stderr=stderr, env=environment, start_new_session=True)
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
            bridge = subprocess.Popen(BRIDGE_COMMAND, stdout=stdout, stderr=stderr, env=environment, start_new_session=True)
            lifecycle["bridge"].update({"pid": bridge.pid, "started_utc_ns": time.time_ns()})
            write_json(run_dir / "supervisor_metadata.json", lifecycle)
            collector = [
                sys.executable,
                str(ROOT / "tools" / "candidate_b_collector.py"),
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
        if not (lifecycle["bridge_shutdown"]["shutdown_complete"]
                and lifecycle["gazebo_shutdown"]["shutdown_complete"]):
            lifecycle["shutdown_status"] = "SHUTDOWN_INCOMPLETE"
            lifecycle["replacement_run_blocked"] = True
            write_json(SHUTDOWN_BLOCKER, {
                "status": "SHUTDOWN_INCOMPLETE",
                "run_id": args.run_id,
                "operator_decision_required": True,
            })
        lifecycle["ended_utc_ns"] = time.time_ns()
        write_json(run_dir / "supervisor_metadata.json", lifecycle)
        metadata_path = run_dir / "capture_metadata.json"
        if metadata_path.exists():
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            metadata["bridge_lifecycle"] = lifecycle["bridge"] | {"shutdown": lifecycle["bridge_shutdown"]}
            metadata["gazebo_lifecycle"] = lifecycle["gazebo"] | {"shutdown": lifecycle["gazebo_shutdown"]}
            metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            analyzer = [sys.executable, str(ROOT / "tools" / "analyze_candidate_b.py"), "--run-dir", str(run_dir)]
            subprocess.run(analyzer, env=environment, check=False)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
