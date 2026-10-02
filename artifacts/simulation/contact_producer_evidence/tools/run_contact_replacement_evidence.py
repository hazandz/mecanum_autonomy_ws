#!/usr/bin/env python3
"""One-shot, SIGINT-only supervisor for an explicitly approved passive contact run.

The offline preflight self-test performs XML/parser checks only. It does not initialize
rclpy, create ROS entities, spawn a process, or inspect a live Gazebo graph.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import signal
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from approval_bound_guard import acquire_guard, consume_guard, initialize_guard, offline_self_test

ROOT = Path("/home/hazan/mecanum_autonomy_ws")
WS = ROOT / "ros2_ws"
ART = ROOT / "artifacts/simulation/contact_producer_evidence"
EXPECTED_SHA = "1c50f90d151a12559d426796c5d153c829b8777a5b4e8ef94c007a2023f6e271"
WORLD = "world_demo"
RAW = "/s3_d3/contact/raw"
RAW_ROS_TYPE = "ros_gz_interfaces/msg/Contacts"
RAW_GZ_TYPE = "gz.msgs.Contacts"
BRIDGE_ARG = "/s3_d3/contact/raw@ros_gz_interfaces/msg/Contacts[gz.msgs.Contacts"
COLLISION = "s3_d3_base_contact_collision"
SENSOR = "s3_d3_base_contact_sensor"
APPROVAL_ID = "S3.3.15_POST_REPAIR_PASSIVE_CONTACT_RUN"
AUTHORITY_PACKET = ROOT / "docs/S3_D3_Post_Repair_Passive_Contact_Run_Approval_Packet_DRAFT.md"
APPROVAL_GUARD = ART / "approval_guards/S3.3.15_POST_REPAIR_PASSIVE_CONTACT_RUN.json"


def approval_context() -> dict[str, Any]:
    if not AUTHORITY_PACKET.is_file():
        raise RuntimeError("approval authority packet is unavailable")
    return {
        "approval_id": APPROVAL_ID,
        "authority_packet": "docs/S3_D3_Post_Repair_Passive_Contact_Run_Approval_Packet_DRAFT.md",
        "authority_packet_sha256": sha256(AUTHORITY_PACKET),
        "world": WORLD,
        "world_sha256": EXPECTED_SHA,
        "literals": {
            "collision": COLLISION,
            "sensor": SENSOR,
            "raw_gz_topic": RAW,
            "raw_ros_topic": RAW,
            "gz_type": RAW_GZ_TYPE,
            "ros_type": RAW_ROS_TYPE,
            "bridge_direction": "GZ_TO_ROS",
            "bridge_argument": BRIDGE_ARG,
        },
    }


def dump(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def local_tag(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def preflight_failure(stage: str, reason: str) -> dict[str, str]:
    return {"stage": stage, "reason": reason}


def parse_single_world_name(sdf_xml: str, expected_world: str = WORLD) -> tuple[bool, dict[str, Any]]:
    """Parse XML/SDF and require exactly one named world equal to expected_world."""
    try:
        root = ET.fromstring(sdf_xml)
    except ET.ParseError as exc:
        return False, preflight_failure("world_name", f"malformed XML/SDF: {exc}")
    if local_tag(root.tag) != "sdf":
        return False, preflight_failure("world_name", "root element is not sdf")
    worlds = [element for element in root.iter() if local_tag(element.tag) == "world"]
    if len(worlds) != 1:
        return False, preflight_failure("world_name", f"expected exactly one world element, found {len(worlds)}")
    name = worlds[0].get("name")
    if name is None or not name.strip():
        return False, preflight_failure("world_name", "world element has missing or empty name")
    if name != expected_world:
        return False, preflight_failure("world_name", f"world name mismatch: expected {expected_world!r}, got {name!r}")
    return True, {"stage": "world_name", "reason": "ready", "world_name": name, "world_element_count": 1}


def ros_shell(command: str) -> list[str]:
    return ["/bin/bash", "-lc", f"source /opt/ros/jazzy/setup.bash && source {WS}/install/setup.bash && {command}"]


def command_output(command: list[str]) -> tuple[int, str]:
    result = subprocess.run(command, text=True, capture_output=True, check=False)
    return result.returncode, result.stdout + result.stderr


def start_process(command: list[str], log_path: Path) -> tuple[subprocess.Popen[str], object]:
    handle = log_path.open("w", encoding="utf-8")
    process = subprocess.Popen(command, stdout=handle, stderr=subprocess.STDOUT, text=True, start_new_session=True)
    return process, handle


def stop_sigint_only(process: subprocess.Popen[str], label: str, records: list[dict[str, object]]) -> bool:
    if process.poll() is not None:
        records.append({"process": label, "pid": process.pid, "already_exited": True, "exit_code": process.returncode})
        return True
    os.killpg(process.pid, signal.SIGINT)
    deadline = time.monotonic() + 20.0
    while time.monotonic() < deadline:
        if process.poll() is not None:
            records.append({"process": label, "pid": process.pid, "signal": "SIGINT", "exit_code": process.returncode, "complete": True})
            return True
        time.sleep(0.2)
    records.append({"process": label, "pid": process.pid, "signal": "SIGINT", "complete": False, "status": "SHUTDOWN_INCOMPLETE"})
    return False


def static_source_scan() -> dict[str, object]:
    banned = ("create_publisher", "create_client", "ActionClient", "publish(", "call_async")
    paths = [ART / "tools/contact_collector.py", ART / "tools/analyze_contact_trace.py"]
    scan: dict[str, dict[str, bool]] = {}
    violations: list[str] = []
    for path in paths:
        source = path.read_text(encoding="utf-8")
        scan[path.name] = {term: term in source for term in banned}
        violations.extend(f"{path.name}:{term}" for term in banned if term in source)
    return {"scan": scan, "violations": violations}


def static_preflight(run: Path) -> tuple[bool, str, str]:
    source_world = WS / "src/ROBOT_URDF_final_description/launch/tugbot_depot.sdf"
    source_xacro = WS / "src/ROBOT_URDF_final_description/urdf/ROBOT_URDF_final.xacro"
    source_gazebo = WS / "src/ROBOT_URDF_final_description/urdf/ROBOT_URDF_final.gazebo"
    source_hash = sha256(source_world)
    if source_hash != EXPECTED_SHA:
        dump(run / "preflight_failure.json", preflight_failure("world_sha256", "source world SHA-256 mismatch"))
        return False, "world_sha256", "source world SHA-256 mismatch"
    world_ok, world_record = parse_single_world_name(source_world.read_text(encoding="utf-8"))
    if not world_ok:
        dump(run / "preflight_failure.json", world_record)
        return False, str(world_record["stage"]), str(world_record["reason"])
    xacro_text = source_xacro.read_text(encoding="utf-8")
    gazebo_text = source_gazebo.read_text(encoding="utf-8")
    literals = {
        "contact_system_count": source_world.read_text(encoding="utf-8").count('filename="gz-sim-contact-system" name="gz::sim::systems::Contact"'),
        "collision_name_count": xacro_text.count(f'name="{COLLISION}"'),
        "sensor_name_count": gazebo_text.count(f'name="{SENSOR}"'),
        "sensor_collision_target_count": gazebo_text.count(f'<collision>{COLLISION}</collision>'),
        "sensor_topic_count": gazebo_text.count(f'<topic>{RAW}</topic>'),
    }
    rc, prefix_text = command_output(ros_shell("ros2 pkg prefix ROBOT_URDF_final_description"))
    if rc != 0:
        record = {"stage": "package_prefix", "reason": "package prefix unavailable", "literals": literals, "output": prefix_text}
        dump(run / "static_robot_validation.json", record)
        return False, "package_prefix", "package prefix unavailable"
    prefix = Path(prefix_text.strip().splitlines()[-1])
    installed_world = prefix / "share/ROBOT_URDF_final_description/launch/tugbot_depot.sdf"
    if not installed_world.exists() or sha256(installed_world) != EXPECTED_SHA:
        record = {"stage": "world_sha256", "reason": "installed world SHA-256 mismatch", "literals": literals, "installed_world": str(installed_world), "installed_world_sha256": sha256(installed_world) if installed_world.exists() else None}
        dump(run / "static_robot_validation.json", record)
        return False, "world_sha256", "installed world SHA-256 mismatch"
    rc, rendered = command_output(ros_shell("ros2 run xacro xacro $(ros2 pkg prefix ROBOT_URDF_final_description)/share/ROBOT_URDF_final_description/urdf/ROBOT_URDF_final.xacro"))
    record = {
        "stage": "xacro_validation",
        "reason": "ready" if rc == 0 else "xacro render command failed",
        "source_world_sha256": source_hash,
        "installed_world_sha256": sha256(installed_world),
        "world": world_record,
        "literals": literals,
        "xacro_exit_code": rc,
        "rendered_collision_occurrences": rendered.count(COLLISION),
        "rendered_sensor_occurrences": rendered.count(SENSOR),
        "rendered_topic_occurrences": rendered.count(RAW),
    }
    dump(run / "static_robot_validation.json", record)
    valid = rc == 0 and all(value == 1 for value in literals.values()) and record["rendered_collision_occurrences"] == 2 and record["rendered_sensor_occurrences"] == 1 and record["rendered_topic_occurrences"] == 1
    if not valid:
        return False, "xacro_validation", "static generated robot-description validation failed"
    return True, "ready", "ready"


def wait_for_gz_contacts_topic(log_path: Path) -> tuple[bool, str]:
    deadline = time.monotonic() + 90.0
    latest = ""
    while time.monotonic() < deadline:
        rc, topics = command_output(ros_shell("gz topic -l"))
        latest = topics
        if rc == 0 and RAW in topics.splitlines():
            info_rc, info = command_output(ros_shell(f"gz topic -i -t {RAW}"))
            log_path.write_text(info, encoding="utf-8")
            return (info_rc == 0 and RAW_GZ_TYPE in info, info)
        time.sleep(1.0)
    log_path.write_text(latest, encoding="utf-8")
    return False, "GZ raw Contacts topic absent before 90-second preflight stop guard"


def write_report(run: Path, final: dict[str, object]) -> None:
    loaded: dict[str, object] = {}
    for name in ("preflight_failure.json", "static_robot_validation.json", "tool_source_scan.json", "collector_preflight.json", "collector_summary.json", "analysis_summary.json", "runtime_preflight_result.json", "shutdown_record.json"):
        candidate = run / name
        if candidate.exists():
            loaded[name] = json.loads(candidate.read_text(encoding="utf-8"))
    summary = loaded.get("collector_summary.json", {})
    payloads = int(summary.get("contacts_payloads", 0)) if isinstance(summary, dict) else 0
    report = f"""# S3 D3 Contact Producer Evidence Report

Run: `{run.name}`

Classification: **{final['status']}**

This is one passive raw-contact evidence run. The collector creates subscriptions only to raw Contacts and `/clock`; it creates no publisher, service client, or action client.

## Bridge and graph provenance

- temporary one-topic bridge argument: `{BRIDGE_ARG}`;
- requested direction: `GZ_TO_ROS`; `[` is the locally documented parameter_bridge Gazebo-to-ROS marker;
- final result stage/reason: `{final.get('stage', 'unknown')}` / `{final['reason']}`.

## Capture summary

- raw Contacts payloads: `{payloads}`;
- aggregate header/timestamp, entity/scoped-name, multiplicity, and duplicate evidence are retained only when raw payloads are received;
- `/clock`, graph snapshots, bridge provenance, and shutdown records are retained where the applicable phase ran.

## Recorded evidence

```json
{json.dumps(loaded, ensure_ascii=True, indent=2, sort_keys=True)}
```

## Retained non-claims

Raw Contacts evidence does not approve collision policy/filtering, ContactLatch, collision severity, transition membership, reset semantics, reward, termination, Gym/SB3/training, command publication, or hardware. `VALID_NO_RAW_CONTACT` neither proves delivery failure nor proves no contact.
"""
    (run / "Contact_Producer_Evidence_Report.md").write_text(report, encoding="utf-8")
    (ART / "Contact_Producer_Evidence_Report.md").write_text(report, encoding="utf-8")


def offline_preflight_self_test() -> int:
    source = WS / "src/ROBOT_URDF_final_description/launch/tugbot_depot.sdf"
    cases = {
        "current_single_quote": (source.read_text(encoding="utf-8"), True, "world_name"),
        "equivalent_double_quote": ('<sdf version="1.9"><world name="world_demo"/></sdf>', True, "world_name"),
        "wrong_world_name": ("<sdf><world name='wrong_world'/></sdf>", False, "world_name"),
        "missing_world_name": ("<sdf><world/></sdf>", False, "world_name"),
        "malformed_xml": ("<sdf><world name='world_demo'></sdf>", False, "world_name"),
        "multiple_world_elements": ("<sdf><world name='world_demo'/><world name='world_demo'/></sdf>", False, "world_name"),
    }
    results: dict[str, dict[str, object]] = {}
    passed = True
    for name, (fixture, expected_ok, expected_stage) in cases.items():
        ok, record = parse_single_world_name(fixture)
        case_ok = ok == expected_ok and record.get("stage") == expected_stage
        results[name] = {"passed": case_ok, "ok": ok, "record": record}
        passed = passed and case_ok
    world_failure = preflight_failure("world_name", "world name mismatch")
    xacro_failure = preflight_failure("xacro_validation", "static generated robot-description validation failed")
    stage_mapping_ok = world_failure["stage"] == "world_name" and xacro_failure["stage"] == "xacro_validation" and world_failure["reason"] != xacro_failure["reason"]
    results["stage_reason_mapping"] = {"passed": stage_mapping_ok, "world_failure": world_failure, "xacro_failure": xacro_failure}
    passed = passed and stage_mapping_ok
    print(json.dumps({"offline_preflight_self_test": "PASS" if passed else "FAIL", "results": results}, ensure_ascii=True, sort_keys=True))
    return 0 if passed else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--capture-seconds", type=float, default=30.0)
    parser.add_argument("--offline-preflight-self-test", action="store_true")
    parser.add_argument("--offline-approval-guard-self-test", action="store_true")
    parser.add_argument("--initialize-s3-3-15-approval-guard", action="store_true")
    args = parser.parse_args()
    if args.offline_preflight_self_test:
        return offline_preflight_self_test()
    if args.offline_approval_guard_self_test:
        ok, result = offline_self_test()
        print(json.dumps(result, ensure_ascii=True, sort_keys=True))
        return 0 if ok else 1
    context = approval_context()
    if args.initialize_s3_3_15_approval_guard:
        ok, reason = initialize_guard(APPROVAL_GUARD, context, datetime.datetime.now(datetime.timezone.utc).isoformat())
        print(json.dumps({"approval_id": APPROVAL_ID, "guard": str(APPROVAL_GUARD), "result": "authorized_not_consumed" if ok else "INVALID", "reason": reason}, ensure_ascii=True, sort_keys=True))
        return 0 if ok else 1
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run = ART / f"run-contact-replacement-{stamp}-01"
    acquired, acquisition_reason, approval_lock = acquire_guard(APPROVAL_GUARD, context)
    if not acquired or approval_lock is None:
        raise SystemExit("refusing S3.3.15 run: " + acquisition_reason)
    run.mkdir(parents=True, exist_ok=False)
    logs = run / "logs"
    logs.mkdir()
    manifest = {"scope": "one approved passive raw-contact replacement evidence run", "world": WORLD, "world_sha256_expected": EXPECTED_SHA, "target_collision": COLLISION, "sensor_name": SENSOR, "raw_gz_topic": RAW, "raw_ros_topic": RAW, "gz_type": RAW_GZ_TYPE, "ros_type": RAW_ROS_TYPE, "bridge_argument": BRIDGE_ARG, "bridge_direction": "GZ_TO_ROS", "capture_seconds_administrative_guard": args.capture_seconds}
    dump(run / "manifest.json", manifest)
    scan = static_source_scan()
    dump(run / "tool_source_scan.json", scan)
    processes: list[tuple[subprocess.Popen[str], str]] = []
    handles: list[object] = []
    status, stage, reason = "INVALID", "not_started", "not started"
    try:
        if scan["violations"]:
            stage, reason = "tool_source_scan", "collector/analyzer source-scan violation: " + ", ".join(scan["violations"])
            return 2
        static_ok, stage, reason = static_preflight(run)
        if not static_ok:
            return 2
        gazebo, handle = start_process(ros_shell("exec ros2 launch ROBOT_URDF_final_description gazebo.launch.py"), logs / "gazebo_launch.log")
        processes.append((gazebo, "gazebo_launch")); handles.append(handle)
        time.sleep(5.0)
        if gazebo.poll() is not None:
            stage, reason = "gazebo_launch", "Gazebo launch exited before raw-contact preflight"
            return 2
        gz_ok, gz_info = wait_for_gz_contacts_topic(logs / "gz_topic_info.log")
        if not gz_ok:
            stage, reason = "gz_topic", "GZ raw Contacts topic/type preflight failed"
            return 2
        bridge, handle = start_process(ros_shell(f"exec ros2 run ros_gz_bridge parameter_bridge {BRIDGE_ARG}"), logs / "temporary_contact_bridge.log")
        processes.append((bridge, "temporary_one_topic_contact_bridge")); handles.append(handle)
        collector_cmd = f"exec python3 {ART / 'tools/contact_collector.py'} --run-dir {run} --preflight-seconds 90 --capture-seconds {args.capture_seconds}"
        collector, handle = start_process(ros_shell(collector_cmd), logs / "collector.log")
        processes.append((collector, "passive_contact_collector")); handles.append(handle)
        deadline = time.monotonic() + 140.0
        while collector.poll() is None and time.monotonic() < deadline:
            time.sleep(0.2)
        if collector.poll() is None:
            stage, reason = "collector", "collector administrative stop guard elapsed"
            return 3
        analysis_rc, analysis_log = command_output([sys.executable, str(ART / "tools/analyze_contact_trace.py"), "--run-dir", str(run)])
        (logs / "analyzer.log").write_text(analysis_log, encoding="utf-8")
        summary_path = run / "collector_summary.json"
        summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else {"status": "INVALID"}
        runtime = {"world": WORLD, "world_sha256": EXPECTED_SHA, "static_sensor_target": COLLISION, "gz_raw_topic": RAW, "gz_raw_topic_info": gz_info, "gz_contacts_type_verified": RAW_GZ_TYPE in gz_info, "bridge_argument": BRIDGE_ARG, "bridge_direction": "GZ_TO_ROS", "one_topic_bridge_process": True, "collector_status": summary.get("status"), "analyzer_exit_code": analysis_rc}
        dump(run / "runtime_preflight_result.json", runtime)
        if summary.get("status") != "VALID" or not runtime["gz_contacts_type_verified"] or analysis_rc != 0:
            stage, reason = "runtime_preflight", "collector/graph/type/analyzer gate failed"
            return 3
        status = "VALID_WITH_RAW_CONTACT" if int(summary.get("contacts_payloads", 0)) > 0 else "VALID_NO_RAW_CONTACT"
        stage, reason = "complete", "passive capture complete"
        return 0
    except Exception as exc:
        stage, reason = "supervisor_exception", f"supervisor exception: {type(exc).__name__}: {exc}"
        return 5
    finally:
        shutdown: list[dict[str, object]] = []
        complete = True
        for process, label in reversed(processes):
            complete = stop_sigint_only(process, label, shutdown) and complete
        for handle in handles:
            handle.close()
        if not complete:
            status, stage, reason = "SHUTDOWN_INCOMPLETE", "shutdown", "SIGINT-only shutdown incomplete"
        dump(run / "shutdown_record.json", {"complete": complete, "records": shutdown})
        final = {"status": status, "stage": stage, "reason": reason, "run_dir": str(run), "bridge_argument": BRIDGE_ARG, "commands_published": 0, "control_services_called": 0, "hardware_operations": 0}
        consumed_ok, consumed_reason = consume_guard(APPROVAL_GUARD, approval_lock, context, run.name, status, datetime.datetime.now(datetime.timezone.utc).isoformat())
        if not consumed_ok:
            final["status"] = "INVALID"
            final["stage"] = "approval_guard_commit"
            final["reason"] = consumed_reason
            final["approval_guard_commit_failed"] = True
        dump(run / "run_result.json", final)
        write_report(run, final)
        os.chmod(run / "manifest.json", 0o444)


if __name__ == "__main__":
    sys.exit(main())
