#!/usr/bin/env python3
"""One-shot SIGINT-only supervisor for the approved passive contact run."""
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
from pathlib import Path

ROOT = Path("/home/hazan/mecanum_autonomy_ws")
WS = ROOT / "ros2_ws"
ART = ROOT / "artifacts/simulation/contact_producer_evidence"
EXPECTED_SHA = "a5e9c9b1e9b8ad11e0399855f06de687f04c702258b8b74ce563523d78ed55fe"
RAW = "/s3_d3/contact/raw"
BRIDGE_ARG = "/s3_d3/contact/raw@ros_gz_interfaces/msg/Contacts[gz.msgs.Contacts"

def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def shell(command):
    return ["/bin/bash", "-lc", "source /opt/ros/jazzy/setup.bash && source " + str(WS) + "/install/setup.bash && " + command]

def output(command):
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    return result.returncode, result.stdout + result.stderr

def launch(command, log):
    handle = log.open("w", encoding="utf-8")
    process = subprocess.Popen(command, stdout=handle, stderr=subprocess.STDOUT, text=True, start_new_session=True)
    return process, handle

def stop_sigint(process, label, records):
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

def scan_tools():
    banned = ("create_publisher", "create_client", "ActionClient", "publish(", "call_async")
    result = {}
    violations = []
    for path in (ART / "tools/contact_collector.py", ART / "tools/analyze_contact_trace.py"):
        text = path.read_text(encoding="utf-8")
        result[path.name] = {term: term in text for term in banned}
        violations.extend(path.name + ":" + term for term in banned if term in text)
    return {"scan": result, "violations": violations}

def static_checks(run):
    source_world = WS / "src/ROBOT_URDF_final_description/launch/tugbot_depot.sdf"
    if sha(source_world) != EXPECTED_SHA:
        return False, "source world SHA-256 mismatch"
    rc, prefix_text = output(shell("ros2 pkg prefix ROBOT_URDF_final_description"))
    if rc:
        return False, "package prefix unavailable"
    prefix = Path(prefix_text.strip().splitlines()[-1])
    installed_world = prefix / "share/ROBOT_URDF_final_description/launch/tugbot_depot.sdf"
    if not installed_world.exists() or sha(installed_world) != EXPECTED_SHA:
        return False, "installed world SHA-256 mismatch"
    rc, xacro = output(shell("ros2 run xacro xacro $(ros2 pkg prefix ROBOT_URDF_final_description)/share/ROBOT_URDF_final_description/urdf/ROBOT_URDF_final.xacro"))
    record = {"xacro_exit_code": rc, "collision_name_count": xacro.count("s3_d3_base_contact_collision"), "sensor_name_count": xacro.count("s3_d3_base_contact_sensor"), "raw_topic_count": xacro.count(RAW), "source_world_sha256": sha(source_world), "installed_world_sha256": sha(installed_world)}
    dump(run / "static_robot_validation.json", record)
    if rc or record["collision_name_count"] != 2 or record["sensor_name_count"] != 1 or record["raw_topic_count"] != 1:
        return False, "generated robot description preflight failed"
    return True, "ready"

def wait_for_gz_topic(log):
    deadline = time.monotonic() + 90.0
    latest = ""
    while time.monotonic() < deadline:
        rc, names = output(shell("gz topic -l"))
        latest = names
        if rc == 0 and RAW in names.splitlines():
            rc, info = output(shell("gz topic -i -t " + RAW))
            log.write_text(info, encoding="utf-8")
            return rc == 0 and "gz.msgs.Contacts" in info, info
        time.sleep(1.0)
    log.write_text(latest, encoding="utf-8")
    return False, "GZ raw Contacts topic absent at preflight deadline"

def report(run, final):
    loaded = {}
    for name in ("collector_summary.json", "analysis_summary.json", "runtime_preflight_result.json", "shutdown_record.json"):
        path = run / name
        if path.exists():
            loaded[name] = json.loads(path.read_text(encoding="utf-8"))
    text = "# S3 D3 Contact Producer Evidence Report\n\n"
    text += "Run: " + run.name + "\n\nStatus: " + final["status"] + "\n\n"
    text += "Scope: one passive raw-contact observation only. No command publisher, service/action client, simulator control, or hardware operation was created by measurement tooling.\n\n"
    text += "Bridge: " + BRIDGE_ARG + "\n\n"
    text += "Direction proof: installed parameter_bridge help states that [ means Gazebo to ROS.\n\n"
    text += "Observed summary:\n\n    " + json.dumps(loaded, ensure_ascii=True, sort_keys=True).replace("\n", "\n    ") + "\n\n"
    text += "Raw CDR and decoded payloads are retained in raw_contacts.jsonl. Empty/absent contact payloads do not prove absence of collision. No payload proves collision policy, ContactLatch, transition provenance, reset semantics, reward, termination, Gymnasium, training, or hardware readiness.\n"
    (run / "Contact_Producer_Evidence_Report.md").write_text(text, encoding="utf-8")
    (ART / "Contact_Producer_Evidence_Report.md").write_text(text, encoding="utf-8")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--capture-seconds", type=float, default=30.0)
    args = ap.parse_args()
    if (ART / "one_run_consumed.json").exists():
        raise SystemExit("refusing another evidence run: one_run_consumed.json exists")
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run = ART / ("run-contact-" + stamp + "-01")
    run.mkdir(parents=True, exist_ok=False)
    logs = run / "logs"
    logs.mkdir()
    manifest = {"scope": "one passive S3 D3 raw-contact evidence run", "world": "world_demo", "world_sha256_expected": EXPECTED_SHA, "raw_gz_topic": RAW, "raw_ros_topic": RAW, "bridge_argument": BRIDGE_ARG, "bridge_direction": "GZ_TO_ROS", "target_collision": "s3_d3_base_contact_collision", "sensor_name": "s3_d3_base_contact_sensor", "capture_seconds_administrative_guard": args.capture_seconds, "forbidden": ["/cmd_vel publish", "teleop", "Nav2", "PPO", "Gymnasium", "SB3", "pose", "reset", "pause", "step", "spawn", "delete", "world-control", "hardware"]}
    dump(run / "manifest.json", manifest)
    scan = scan_tools()
    dump(run / "tool_source_scan.json", scan)
    status, reason, processes, handles, shutdown = "INVALID", "not started", [], [], []
    try:
        if scan["violations"]:
            reason = "tool source scan violation: " + ", ".join(scan["violations"])
            return 2
        ok, reason = static_checks(run)
        if not ok:
            return 2
        gazebo, handle = launch(shell("exec ros2 launch ROBOT_URDF_final_description gazebo.launch.py"), logs / "gazebo_launch.log")
        processes.append((gazebo, "gazebo_launch"))
        handles.append(handle)
        time.sleep(5.0)
        if gazebo.poll() is not None:
            reason = "Gazebo launch exited before GZ contact preflight"
            return 2
        ok, gz_info = wait_for_gz_topic(logs / "gz_topic_info.log")
        if not ok:
            reason = "GZ raw Contacts preflight failed"
            return 2
        bridge, handle = launch(shell("exec ros2 run ros_gz_bridge parameter_bridge " + BRIDGE_ARG), logs / "temporary_contact_bridge.log")
        processes.append((bridge, "temporary_contact_bridge"))
        handles.append(handle)
        collector_cmd = "exec python3 " + str(ART / "tools/contact_collector.py") + " --run-dir " + str(run) + " --preflight-seconds 90 --capture-seconds " + str(args.capture_seconds)
        collector, handle = launch(shell(collector_cmd), logs / "collector.log")
        processes.append((collector, "passive_contact_collector"))
        handles.append(handle)
        deadline = time.monotonic() + 140.0
        while time.monotonic() < deadline and collector.poll() is None:
            time.sleep(0.2)
        if collector.poll() is None:
            reason = "collector administrative timeout"
            return 3
        rc, text = output([sys.executable, str(ART / "tools/analyze_contact_trace.py"), "--run-dir", str(run)])
        (logs / "analyzer.log").write_text(text, encoding="utf-8")
        summary_path = run / "collector_summary.json"
        summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else {"status": "INVALID", "reason": "collector summary missing"}
        gaz_log = (logs / "gazebo_launch.log").read_text(encoding="utf-8", errors="replace")
        runtime = {"collector_status": summary.get("status"), "collector_reason": summary.get("reason"), "gz_topic_info": gz_info, "gz_contacts_type_verified": "gz.msgs.Contacts" in gz_info, "contact_system_log_marker": "Contact system publishing on" in gaz_log, "bridge_argument": BRIDGE_ARG, "direction_proof": "installed parameter_bridge --help: [ means Gazebo to ROS"}
        dump(run / "runtime_preflight_result.json", runtime)
        if summary.get("status") != "VALID":
            reason = "collector preflight/capture invalid"
            return 3
        if not runtime["gz_contacts_type_verified"]:
            reason = "GZ topic type did not verify as gz.msgs.Contacts"
            return 3
        status, reason = "VALID", "passive capture complete"
        return 0
    except Exception as exc:
        reason = "supervisor exception: " + type(exc).__name__ + ": " + str(exc)
        return 5
    finally:
        complete = True
        for process, label in reversed(processes):
            complete = stop_sigint(process, label, shutdown) and complete
        for handle in handles:
            handle.close()
        if not complete:
            status, reason = "SHUTDOWN_INCOMPLETE", "SIGINT-only shutdown incomplete"
        dump(run / "shutdown_record.json", {"records": shutdown, "complete": complete})
        final = {"status": status, "reason": reason, "run_dir": str(run), "bridge_argument": BRIDGE_ARG, "probes_sent": 0, "commands_published": 0, "control_services_called": 0, "hardware_operations": 0}
        dump(run / "run_result.json", final)
        dump(ART / "one_run_consumed.json", final)
        report(run, final)
        os.chmod(run / "manifest.json", 0o444)

if __name__ == "__main__":
    sys.exit(main())
