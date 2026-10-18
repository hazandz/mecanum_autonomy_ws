"""One-shot future WP06-6F runtime supervisor; never execute in candidate checks."""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import importlib
import json
import math
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone


TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
from wp06_6f_tf_ekf_runtime_guard import (  # noqa: E402
    CONSUMED,
    PARTITION,
    RUN_ID,
    GuardError,
    acquire_guard,
    verify_runtime_preconditions,
)


BOOTSTRAP_COMMAND = [
    "ros2", "launch", "ROBOT_URDF_final_description",
    "sim_eval_scan_probe_bootstrap.launch.py",
]
COMPOSITE_COMMAND = [
    "ros2", "launch", "mecanum_nav_bringup",
    "sim_eval_tf_ekf_state_estimation.launch.py",
    f"gz_partition:={PARTITION}", "use_sim_time:=true",
]
FORBIDDEN_TOPICS = {
    "/odom", "/ground_truth/odom", "/tf", "/tf_static", "/cmd_vel", "/map"
}
STALE_MARKERS = (
    "sim_eval_scan_probe_bootstrap.launch.py",
    "sim_eval_tf_ekf_state_estimation.launch.py",
    "sim_eval_wheel_imu_ingress.launch.py",
    "sim_eval_clock_bridge",
    "ekf_filter_node",
)
RECORD_SCHEMA = "wp06_6f_tf_ekf_runtime_record/v1"


def _now():
    return datetime.now(timezone.utc).isoformat()


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path, value):
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    Path(path).write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


def _getifaddrs_passes():
    libc = ctypes.CDLL(None, use_errno=True)
    result = ctypes.c_void_p()
    if libc.getifaddrs(ctypes.byref(result)) != 0:
        return False
    libc.freeifaddrs(result)
    return True


def _host_preflight(repository_root):
    if not os.path.isdir("/dev/shm") or not os.access("/dev/shm", os.W_OK):
        raise GuardError("DEV_SHM_NOT_WRITABLE")
    if not _getifaddrs_passes():
        raise GuardError("GETIFADDRS_UNAVAILABLE")
    for executable in ("ros2", "gz"):
        if shutil.which(executable) is None:
            raise GuardError(f"EXECUTABLE_UNAVAILABLE:{executable}")
    for package in ("ros_gz_sim", "ros_gz_bridge", "mecanum_base_bridge", "mecanum_nav_bringup", "robot_localization"):
        result = subprocess.run(
            ["ros2", "pkg", "prefix", package], capture_output=True, text=True, timeout=5, check=False
        )
        if result.returncode != 0 or not result.stdout.strip():
            raise GuardError(f"PACKAGE_PREFIX_UNAVAILABLE:{package}")
    for module_name in ("rclpy", "tf2_ros", "tf2_msgs.msg", "rosgraph_msgs.msg", "yaml"):
        try:
            importlib.import_module(module_name)
        except Exception as exc:
            raise GuardError(f"RUNTIME_IMPORT_UNAVAILABLE:{module_name}:{exc}") from exc


def _proc_snapshot(pgid):
    live = []
    zombies = []
    observable = True
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            raw = (entry / "stat").read_text(encoding="utf-8")
            tail = raw[raw.rfind(")") + 1 :].split()
            state, member_pgid = tail[0], int(tail[2])
            if member_pgid == pgid:
                item = {"pid": int(entry.name), "state": state}
                (zombies if state in {"Z", "X"} else live).append(item)
        except FileNotFoundError:
            continue
        except (OSError, ValueError, IndexError):
            observable = False
    return {"live_members": live, "zombie_members": zombies, "observable": observable}


def _stale_processes():
    found = []
    own = {os.getpid()}
    parent = os.getppid()
    while parent > 1 and parent not in own:
        own.add(parent)
        try:
            fields = Path(f"/proc/{parent}/stat").read_text(encoding="utf-8")
            parent = int(fields[fields.rfind(")") + 1 :].split()[1])
        except (OSError, ValueError, IndexError):
            break
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit() or int(entry.name) in own:
            continue
        try:
            command = (entry / "cmdline").read_bytes().replace(b"\0", b" ").decode("utf-8", "replace").strip()
            if any(marker in command for marker in STALE_MARKERS):
                stat = (entry / "stat").read_text(encoding="utf-8")
                tail = stat[stat.rfind(")") + 1 :].split()
                found.append({"pid": int(entry.name), "ppid": int(tail[1]), "pgid": int(tail[2]), "state": tail[0], "command": command})
        except (FileNotFoundError, OSError, ValueError, IndexError):
            continue
    if found:
        raise GuardError("STALE_SESSION_PRESENT:" + json.dumps(found, sort_keys=True))


def _spawn(argv, log_path, env):
    stream = Path(log_path).open("wb")
    process = subprocess.Popen(argv, cwd=env["WP06_REPOSITORY_ROOT"], env=env,
                               stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT,
                               start_new_session=True, close_fds=True)
    pgid = os.getpgid(process.pid)
    if pgid != process.pid:
        stream.close()
        raise GuardError("PROCESS_GROUP_NOT_ISOLATED")
    return {"process": process, "stream": stream, "pid": process.pid, "pgid": pgid, "command": list(argv)}


def _wait_readiness(session, token, timeout):
    path = Path(session["log_path"])
    deadline = time.monotonic() + timeout
    offset = 0
    while time.monotonic() < deadline:
        process = session["process"]
        if process.poll() is not None:
            return False
        try:
            with path.open("rb") as stream:
                stream.seek(offset)
                chunk = stream.read()
                offset += len(chunk)
            if token in chunk:
                return True
        except FileNotFoundError:
            pass
        time.sleep(0.2)
    return False


def _teardown(session, label):
    process = session["process"]
    pgid = session["pgid"]
    timeline = []
    actual_pgid = os.getpgid(process.pid) if process.poll() is None else pgid
    if actual_pgid != pgid:
        return {"name": label, "pid": process.pid, "pgid": pgid, "outcome": "UNEXPECTED_PGID", "final_snapshot": _proc_snapshot(pgid), "timeline": timeline}
    for sig, wait_s in ((signal.SIGINT, 10), (signal.SIGTERM, 5), (signal.SIGKILL, 5)):
        snapshot = _proc_snapshot(pgid)
        if process.poll() is not None and not snapshot["live_members"]:
            break
        timeline.append({"signal": sig.name, "timestamp": _now()})
        try:
            os.killpg(pgid, sig)
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=wait_s)
        except subprocess.TimeoutExpired:
            pass
        if sig == signal.SIGKILL and process.poll() is None:
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                pass
    final = _proc_snapshot(pgid)
    process.poll()
    session["stream"].close()
    stopped = process.returncode is not None and final["observable"] and not final["live_members"] and not final["zombie_members"]
    return {"name": label, "pid": process.pid, "pgid": pgid, "leader_returncode": process.returncode,
            "timeline": timeline, "final_snapshot": final, "outcome": "STOPPED" if stopped else "TEARDOWN_FAILED"}


def _run_transcript(command, env, directory, name, timeout=8):
    try:
        result = subprocess.run(command, cwd=env["WP06_REPOSITORY_ROOT"], env=env,
                                capture_output=True, timeout=timeout, check=False)
        stdout, stderr, code = result.stdout, result.stderr, result.returncode
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or b""
        stderr = exc.stderr or b""
        code = 124
    (directory / f"{name}.stdout.bin").write_bytes(stdout)
    (directory / f"{name}.stderr.bin").write_bytes(stderr)
    meta = {"command": command, "exit_code": code, "stdout_sha256": hashlib.sha256(stdout).hexdigest(),
            "stderr_sha256": hashlib.sha256(stderr).hexdigest(), "timestamp": _now()}
    return meta, stdout, stderr


def _message_info_callback(records, lock, topic, kind):
    def callback(message, info):
        gid = bytes(info.publisher_gid).hex()
        for transform in message.transforms:
            stamp = transform.header.stamp
            row = {
                "topic": topic, "kind": kind, "parent": transform.header.frame_id,
                "child": transform.child_frame_id,
                "stamp_ns": int(stamp.sec) * 1_000_000_000 + int(stamp.nanosec),
                "publisher_gid": gid,
                "translation": [transform.transform.translation.x, transform.transform.translation.y, transform.transform.translation.z],
                "rotation_xyzw": [transform.transform.rotation.x, transform.transform.rotation.y, transform.transform.rotation.z, transform.transform.rotation.w],
            }
            with lock:
                records.append(row)
    return callback


def _start_tf_observer():
    import rclpy
    from rclpy.executors import SingleThreadedExecutor
    from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy
    from tf2_msgs.msg import TFMessage

    rclpy.init(args=None)
    node = rclpy.create_node("wp06_6f_tf_observer", parameter_overrides=[])
    records, lock = [], threading.Lock()
    node.create_subscription(TFMessage, "/tf", _message_info_callback(records, lock, "/tf", "dynamic"), QoSProfile(depth=100), with_info=True)
    static_qos = QoSProfile(depth=100, reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.TRANSIENT_LOCAL)
    node.create_subscription(TFMessage, "/tf_static", _message_info_callback(records, lock, "/tf_static", "static"), static_qos, with_info=True)
    executor = SingleThreadedExecutor()
    executor.add_node(node)
    thread = threading.Thread(target=executor.spin, daemon=True)
    thread.start()
    return {"rclpy": rclpy, "node": node, "executor": executor, "thread": thread, "records": records, "lock": lock}


def _stop_tf_observer(observer):
    observer["executor"].shutdown(timeout_sec=2)
    observer["node"].destroy_node()
    observer["rclpy"].shutdown()
    observer["thread"].join(timeout=2)


def _parse_single_yaml_mapping(raw):
    import yaml
    documents = [item for item in yaml.safe_load_all(raw.decode("utf-8")) if item is not None]
    if len(documents) != 1 or not isinstance(documents[0], dict):
        raise ValueError("EXPECTED_EXACTLY_ONE_YAML_MAPPING")
    return documents[0]


def _finite_tree(value):
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return True
    if isinstance(value, (int, float)):
        return math.isfinite(float(value))
    if isinstance(value, list):
        return all(_finite_tree(item) for item in value)
    if isinstance(value, dict):
        return all(_finite_tree(item) for item in value.values())
    return False


def _verify_topic_info(text, expected_type, count=1):
    return expected_type in text and f"Publisher count: {count}" in text


def _node_section_topics(text, section_name):
    topics = set()
    active = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped == f"{section_name}:":
            active = True
            continue
        if active and stripped.endswith(":") and not stripped.startswith("/"):
            break
        if active and stripped.startswith("/") and ":" in stripped:
            topics.add(stripped.split(":", 1)[0])
    return topics


def _data_topics(text, section_name):
    return _node_section_topics(text, section_name) - {"/parameter_events", "/rosout"}


def _valid_stamp(mapping):
    stamp = mapping.get("header", {}).get("stamp", {})
    return (isinstance(stamp, dict) and type(stamp.get("sec")) is int
            and type(stamp.get("nanosec")) is int and stamp["sec"] >= 0
            and 0 <= stamp["nanosec"] < 1_000_000_000
            and (stamp["sec"] > 0 or stamp["nanosec"] > 0))


def _quaternion_norm(mapping):
    orientation = mapping.get("pose", {}).get("pose", {}).get("orientation")
    if not isinstance(orientation, dict):
        return None
    try:
        return math.sqrt(sum(float(orientation[key]) ** 2 for key in ("x", "y", "z", "w")))
    except (KeyError, TypeError, ValueError):
        return None


def _tf_acceptance(records):
    dynamic = [row for row in records if row["topic"] == "/tf" and row["parent"] == "odom" and row["child"] == "base_link"]
    static = [row for row in records if row["topic"] == "/tf_static" and row["parent"] == "base_link" and row["child"] == "lidar_frame"]
    forbidden = [row for row in records if row["parent"] == "map" and row["child"] == "odom"]
    gids = {row["publisher_gid"] for row in dynamic}
    stamps = [row["stamp_ns"] for row in dynamic]
    expected_translation = [-0.031765, 0.0, 0.140]
    expected_rotation = [0.0, 0.0, 0.0, 1.0]
    static_signatures = {
        (row["publisher_gid"], tuple(row["translation"]), tuple(row["rotation_xyzw"]))
        for row in static
    }
    static_exact = len(static_signatures) == 1 and bool(static_signatures) and all(abs(a-b) <= 1e-9 for a, b in zip(static[0]["translation"], expected_translation)) and all(abs(a-b) <= 1e-9 for a, b in zip(static[0]["rotation_xyzw"], expected_rotation))
    return {
        "dynamic_edge_samples": len(dynamic), "dynamic_gids": sorted(gids),
        "dynamic_timestamps_strictly_increasing": len(stamps) >= 5 and all(a < b for a, b in zip(stamps, stamps[1:])),
        "dynamic_unique_gid": len(gids) == 1,
        "static_edge_exactly_one_with_xacro_transform": static_exact,
        "map_to_odom_absent": not forbidden,
    }


def run_session(repository_root, guard_path, run_directory, run_id, gz_partition,
                expected_review_commit, expected_integration_base):
    """Run exactly one authorized future session. Offline tests must never call this."""
    root = Path(repository_root).resolve()
    guard_file = Path(guard_path).resolve()
    run_dir = Path(run_directory).resolve()
    if run_id != RUN_ID or gz_partition != PARTITION:
        raise GuardError("RUN_OR_PARTITION_MISMATCH")
    verified = verify_runtime_preconditions(root, guard_file, run_dir, expected_review_commit, expected_integration_base)
    _host_preflight(root)
    _stale_processes()
    env = os.environ.copy()
    env.update({"GZ_PARTITION": PARTITION, "GZ_IP": "127.0.0.1", "WP06_REPOSITORY_ROOT": str(root)})
    consumed = acquire_guard(guard_file, expected_review_commit, expected_integration_base)
    run_dir.mkdir(parents=True, mode=0o700)
    (run_dir / "transcripts").mkdir(mode=0o700)
    (run_dir / "logs").mkdir(mode=0o700)
    start = _now()
    monotonic_start = time.monotonic()
    record = {
        "schema": RECORD_SCHEMA, "run_id": RUN_ID, "review_commit": expected_review_commit,
        "integration_base": expected_integration_base, "guard_state_before": "PENDING",
        "guard_state_after": CONSUMED, "gz_partition": PARTITION, "started_at": start,
        "preflight": {"guard_manifest_sha256": _sha256(root / "docs/governance/evidence/WP-06_6F_TF_EKF_RUNTIME_INGRESS_RUN_001_GUARD_MANIFEST.json"),
                      "decision_sha256": _sha256(root / "docs/governance/decisions/WP-06_SIM_EVAL_TF_EKF_RUNTIME_STATE_ESTIMATION_INGRESS_L2_DECISION.md"),
                      "source_pins": verified["source_pins"], "authorization_acquisition_count": consumed["acquisition_count"]},
        "processes": {}, "transcripts": {}, "acceptance": {}, "terminal_outcome": "FAIL_NO_RETRY",
    }
    sessions = {}
    observer = None
    try:
        bootstrap_log = run_dir / "logs/bootstrap.log"
        sessions["bootstrap"] = _spawn(BOOTSTRAP_COMMAND, bootstrap_log, env)
        sessions["bootstrap"]["log_path"] = str(bootstrap_log)
        record["processes"]["bootstrap"] = {k: sessions["bootstrap"][k] for k in ("pid", "pgid", "command")}
        bootstrap_ready = _wait_readiness(sessions["bootstrap"], b"Entity creation successful.", 90)
        record["acceptance"]["bootstrap_readiness"] = bootstrap_ready
        if not bootstrap_ready:
            raise GuardError("BOOTSTRAP_READINESS_FAILED")
        time.sleep(20)
        if sessions["bootstrap"]["process"].poll() is not None:
            raise GuardError("BOOTSTRAP_DIED_DURING_STABILIZATION")
        (run_dir / "authorization_state.txt").write_text("CONSUMED\n", encoding="utf-8")
        composite_log = run_dir / "logs/composite.log"
        sessions["composite"] = _spawn(COMPOSITE_COMMAND, composite_log, env)
        sessions["composite"]["log_path"] = str(composite_log)
        record["processes"]["composite"] = {k: sessions["composite"][k] for k in ("pid", "pgid", "command")}
        observer = _start_tf_observer()
        command_specs = [
            ("clock_echo", ["ros2", "topic", "echo", "/clock", "rosgraph_msgs/msg/Clock", "--once"]),
            ("wheel_echo", ["ros2", "topic", "echo", "/wheel/odometry_raw", "nav_msgs/msg/Odometry", "--once"]),
            ("imu_echo", ["ros2", "topic", "echo", "/imu/data", "sensor_msgs/msg/Imu", "--once"]),
            ("filtered_echo", ["ros2", "topic", "echo", "/odometry/filtered", "nav_msgs/msg/Odometry", "--once"]),
            ("wheel_info", ["ros2", "topic", "info", "--verbose", "/wheel/odometry_raw"]),
            ("imu_info", ["ros2", "topic", "info", "--verbose", "/imu/data"]),
            ("filtered_info", ["ros2", "topic", "info", "--verbose", "/odometry/filtered"]),
            ("ekf_node_info", ["ros2", "node", "info", "/ekf_filter_node"]),
            ("ingress_node_info", ["ros2", "node", "info", "/sim_eval_wheel_imu_ingress"]),
            ("ingress_bridge_node_info", ["ros2", "node", "info", "/sim_eval_wheel_imu_ingress_bridge"]),
            ("clock_bridge_node_info", ["ros2", "node", "info", "/sim_eval_clock_bridge"]),
            ("use_sim_time", ["ros2", "param", "get", "/ekf_filter_node", "use_sim_time"]),
        ]
        outputs = {}
        for name, command in command_specs:
            meta, stdout, stderr = _run_transcript(command, env, run_dir / "transcripts", name)
            record["transcripts"][name] = meta
            outputs[name] = stdout
        time.sleep(1)
        record["tf_observer"] = {"records": list(observer["records"])}
        record["acceptance"].update(_evaluate_acceptance(outputs, record["processes"], observer["records"]))
        if not all(value is True for value in record["acceptance"].values() if isinstance(value, bool)):
            raise GuardError("RUNTIME_ACCEPTANCE_FAILED")
        record["terminal_outcome"] = "OBSERVATION_ONLY_PASS_NOT_RUNTIME_APPROVAL"
    except Exception as exc:
        record["failure"] = f"{type(exc).__name__}:{exc}"
    finally:
        if observer is not None:
            try:
                _stop_tf_observer(observer)
            except Exception as exc:
                record.setdefault("teardown_errors", []).append(f"observer:{exc}")
        teardown = []
        for label in ("composite", "bootstrap"):
            if label in sessions:
                teardown.append(_teardown(sessions[label], label))
        record["teardown"] = teardown
        record["teardown_pass"] = all(item["outcome"] == "STOPPED" for item in teardown)
        if not record["teardown_pass"]:
            record["terminal_outcome"] = "FAIL_NO_RETRY"
        elif record["terminal_outcome"] != "OBSERVATION_ONLY_PASS_NOT_RUNTIME_APPROVAL":
            record["terminal_outcome"] = "FAIL_NO_RETRY"
        record["finished_at"] = _now()
        record["duration_seconds"] = round(time.monotonic() - monotonic_start, 6)
        record["artifact_sha256"] = {}
        for path in sorted(run_dir.rglob("*")):
            if path.is_file() and path.name not in {"artifact_manifest.json", "run_record.json"}:
                record["artifact_sha256"][str(path.relative_to(run_dir))] = _sha256(path)
        _write_json(run_dir / "run_record.json", record)
        files = dict(record["artifact_sha256"])
        files["run_record.json"] = _sha256(run_dir / "run_record.json")
        manifest = {"schema": "wp06_6f_tf_ekf_runtime_artifacts/v1", "files": files}
        _write_json(run_dir / "artifact_manifest.json", manifest)
    return 0 if record["terminal_outcome"] == "OBSERVATION_ONLY_PASS_NOT_RUNTIME_APPROVAL" else 1


def _evaluate_acceptance(outputs, processes, tf_records):
    result = {}
    for name, expected in (("wheel_info", "nav_msgs/msg/Odometry"), ("imu_info", "sensor_msgs/msg/Imu"), ("filtered_info", "nav_msgs/msg/Odometry")):
        text = outputs[name].decode("utf-8", "replace")
        result[f"{name}_one_publisher_and_type"] = _verify_topic_info(text, expected)
    result["clock_message_received"] = bool(outputs["clock_echo"].strip())
    result["use_sim_time_true"] = outputs["use_sim_time"].decode("utf-8", "replace").strip().lower().endswith("true")
    try:
        wheel = _parse_single_yaml_mapping(outputs["wheel_echo"])
        imu = _parse_single_yaml_mapping(outputs["imu_echo"])
        filtered = _parse_single_yaml_mapping(outputs["filtered_echo"])
        result["wheel_sample_contract"] = _valid_stamp(wheel) and wheel.get("header", {}).get("frame_id") == "odom" and wheel.get("child_frame_id") == "base_link" and _finite_tree(wheel.get("twist"))
        result["imu_sample_finite"] = _valid_stamp(imu) and imu.get("header", {}).get("frame_id") == "base_link" and _finite_tree(imu)
        filtered_norm = _quaternion_norm(filtered)
        result["filtered_sample_contract"] = _valid_stamp(filtered) and filtered.get("header", {}).get("frame_id") == "odom" and filtered.get("child_frame_id") == "base_link" and _finite_tree(filtered) and filtered_norm is not None and 0.999 <= filtered_norm <= 1.001
    except Exception:
        result["wheel_sample_contract"] = result["imu_sample_finite"] = result["filtered_sample_contract"] = False
    ekf_info = outputs["ekf_node_info"].decode("utf-8", "replace")
    ingress_info = outputs["ingress_node_info"].decode("utf-8", "replace")
    ingress_bridge_info = outputs["ingress_bridge_node_info"].decode("utf-8", "replace")
    clock_bridge_info = outputs["clock_bridge_node_info"].decode("utf-8", "replace")
    ekf_inputs = _data_topics(ekf_info, "Subscribers")
    result["ekf_inputs_exactly_wheel_imu_clock"] = ekf_inputs == {"/wheel/odometry_raw", "/imu/data", "/clock"}
    ekf_publishers = _data_topics(ekf_info, "Publishers")
    result["ekf_filtered_output_and_tf"] = {"/odometry/filtered", "/tf"}.issubset(ekf_publishers)
    ingress_publishers = _data_topics(ingress_info, "Publishers")
    result["ingress_outputs_bounded"] = ingress_publishers == {"/wheel/odometry_raw", "/imu/data"}
    ingress_bridge_publishers = _data_topics(ingress_bridge_info, "Publishers")
    result["ingress_bridge_outputs_bounded"] = ingress_bridge_publishers == {"/sim_eval/wheel_joint_states", "/sim_eval/imu_raw"}
    clock_bridge_publishers = _data_topics(clock_bridge_info, "Publishers")
    result["clock_bridge_outputs_only_clock"] = clock_bridge_publishers == {"/clock"}
    result["forbidden_topics_absent_from_ingress_nodes"] = not any(topic in ingress_info or topic in ingress_bridge_info or topic in clock_bridge_info for topic in FORBIDDEN_TOPICS)
    result.update({f"tf_{key}": value for key, value in _tf_acceptance(tf_records).items()})
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", required=True)
    parser.add_argument("--guard-path", required=True)
    parser.add_argument("--run-directory", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--gz-partition", required=True)
    parser.add_argument("--expected-review-commit", required=True)
    parser.add_argument("--expected-integration-base", required=True)
    args = parser.parse_args(argv)
    try:
        return run_session(args.repository_root, args.guard_path, args.run_directory, args.run_id,
                           args.gz_partition, args.expected_review_commit, args.expected_integration_base)
    except Exception as exc:
        print(f"PREFLIGHT_OR_RUN_FAILURE:{type(exc).__name__}:{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
