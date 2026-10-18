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
import time
from datetime import datetime, timezone


TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
from wp06_6f_tf_ekf_run007_runtime_guard import (  # noqa: E402
    CONSUMED,
    PARTITION,
    PENDING,
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
OBSERVER_EXECUTABLE = ["ros2", "run", "wp06_6f_tf_ekf_runtime_observer", "wp06_6f_tf_ekf_runtime_observer"]
FORBIDDEN_TOPICS = {
    "/odom", "/ground_truth/odom", "/tf_static", "/cmd_vel", "/map"
}
STALE_MARKERS = (
    "sim_eval_scan_probe_bootstrap.launch.py",
    "sim_eval_tf_ekf_state_estimation.launch.py",
    "sim_eval_wheel_imu_ingress.launch.py",
    "sim_eval_clock_bridge",
    "ekf_filter_node",
)
RECORD_SCHEMA = "wp06_6f_tf_ekf_runtime_record/v1"
EKF_SUBSCRIBER_TOPICS = {"/clock", "/imu/data", "/wheel/odometry_raw", "/set_pose"}
EKF_PUBLISHER_TOPICS = {"/odometry/filtered", "/tf", "/diagnostics"}
ROS_STANDARD_ENDPOINTS_BY_DIRECTION = {
    "Subscribers": {"/parameter_events"},
    "Publishers": {"/parameter_events", "/rosout"},
}


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
    for package in ("ros_gz_sim", "ros_gz_bridge", "mecanum_base_bridge", "mecanum_nav_bringup", "robot_localization", "wp06_6f_tf_ekf_runtime_observer"):
        result = subprocess.run(
            ["ros2", "pkg", "prefix", package], capture_output=True, text=True, timeout=5, check=False
        )
        if result.returncode != 0 or not result.stdout.strip():
            raise GuardError(f"PACKAGE_PREFIX_UNAVAILABLE:{package}")
        if package == "wp06_6f_tf_ekf_runtime_observer":
            executable = Path(result.stdout.strip()) / "lib" / package / "wp06_6f_tf_ekf_runtime_observer"
            if not executable.is_file() or not os.access(executable, os.X_OK):
                raise GuardError("CPP_OBSERVER_EXECUTABLE_UNAVAILABLE")
    for module_name in (
        "rclpy", "tf2_ros", "tf2_msgs.msg", "rosgraph_msgs.msg", "nav_msgs.msg", "yaml",
        "mecanum_nav_bringup.sim_eval_tf_ekf_runtime_observer",
    ):
        try:
            module = importlib.import_module(module_name)
            if module_name == "mecanum_nav_bringup.sim_eval_tf_ekf_runtime_observer":
                prefix = Path(subprocess.run(["ros2", "pkg", "prefix", "mecanum_nav_bringup"],
                    capture_output=True, text=True, timeout=5, check=True).stdout.strip()).resolve()
                if prefix not in Path(module.__file__).resolve().parents:
                    raise GuardError("OBSERVER_PARSER_NOT_FROM_INSTALLED_OVERLAY")
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
            "timeline": timeline, "final_snapshot": final,
            "live_member_pids": [item["pid"] for item in final["live_members"]],
            "zombie_member_pids": [item["pid"] for item in final["zombie_members"]],
            "outcome": "STOPPED" if stopped else "TEARDOWN_FAILED"}


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


def _classify_node_endpoints(text, section_name):
    """Separate exact business topics from direction-allowed ROS endpoints."""
    if section_name not in ROS_STANDARD_ENDPOINTS_BY_DIRECTION:
        raise ValueError(f"NODE_INFO_SECTION_UNSUPPORTED:{section_name}")
    exact_topics = _node_section_topics(text, section_name)
    standard_topics = exact_topics & {"/parameter_events", "/rosout"}
    allowed_standard = ROS_STANDARD_ENDPOINTS_BY_DIRECTION[section_name]
    return {
        "business": exact_topics - standard_topics,
        "standard": standard_topics & allowed_standard,
        "wrong_direction": standard_topics - allowed_standard,
    }


def _topic_policy_violations(node_infos):
    """Apply topic policy to parsed exact names, never substring matches."""
    violations = []
    for node, text in node_infos.items():
        subscriber_class = _classify_node_endpoints(text, "Subscribers")
        publisher_class = _classify_node_endpoints(text, "Publishers")
        subscribers = subscriber_class["business"]
        publishers = publisher_class["business"]
        for direction, classification in (("Subscribers", subscriber_class), ("Publishers", publisher_class)):
            if classification["wrong_direction"]:
                violations.append({"node": node, "reason": "ROS_STANDARD_ENDPOINT_WRONG_DIRECTION",
                                   "direction": direction, "topics": sorted(classification["wrong_direction"])})
        endpoints = subscribers | publishers
        banned = endpoints & FORBIDDEN_TOPICS
        if banned:
            violations.append({"node": node, "reason": "FORBIDDEN_TOPIC", "topics": sorted(banned)})
        if node != "ekf" and "/set_pose" in endpoints:
            violations.append({"node": node, "reason": "SET_POSE_OUTSIDE_EKF_SUBSCRIBER"})
        if "/set_pose" in publishers:
            violations.append({"node": node, "reason": "EKF_SET_POSE_EXTERNAL_PUBLISHER_OBSERVED"})
        if node == "ekf":
            if subscribers != EKF_SUBSCRIBER_TOPICS:
                violations.append({"node": node, "reason": "EKF_SUBSCRIBER_SET_OUT_OF_CONTRACT",
                                   "topics": sorted(subscribers)})
            if publishers != EKF_PUBLISHER_TOPICS:
                violations.append({"node": node, "reason": "EKF_PUBLISHER_SET_OUT_OF_CONTRACT",
                                   "topics": sorted(publishers)})
        elif node == "ingress":
            if subscribers != {"/clock", "/sim_eval/imu_raw", "/sim_eval/wheel_joint_states"}:
                violations.append({"node": node, "reason": "INGRESS_SUBSCRIBER_SET_OUT_OF_CONTRACT",
                                   "topics": sorted(subscribers)})
            if publishers != {"/wheel/odometry_raw", "/imu/data"}:
                violations.append({"node": node, "reason": "INGRESS_PUBLISHER_SET_OUT_OF_CONTRACT",
                                   "topics": sorted(publishers)})
        elif node == "ingress_bridge":
            if subscribers:
                violations.append({"node": node, "reason": "INGRESS_BRIDGE_SUBSCRIBER_SET_OUT_OF_CONTRACT",
                                   "topics": sorted(subscribers)})
            if publishers != {"/sim_eval/wheel_joint_states", "/sim_eval/imu_raw"}:
                violations.append({"node": node, "reason": "INGRESS_BRIDGE_PUBLISHER_SET_OUT_OF_CONTRACT",
                                   "topics": sorted(publishers)})
        elif node == "clock_bridge":
            if subscribers != {"/clock"}:
                violations.append({"node": node, "reason": "CLOCK_BRIDGE_SUBSCRIBER_SET_OUT_OF_CONTRACT",
                                   "topics": sorted(subscribers)})
            if publishers != {"/clock"}:
                violations.append({"node": node, "reason": "CLOCK_BRIDGE_PUBLISHER_SET_OUT_OF_CONTRACT",
                                   "topics": sorted(publishers)})
    return violations


def _set_pose_endpoint_contract(info_text, echo_stdout, echo_exit_code, ekf_subscribers):
    import re
    topic_type = re.search(r"^Type:\s*(.+?)\s*$", info_text, re.MULTILINE)
    publisher_count = re.search(r"^Publisher count:\s*(\d+)\s*$", info_text, re.MULTILINE)
    subscription_count = re.search(r"^Subscription count:\s*(\d+)\s*$", info_text, re.MULTILINE)
    endpoint_is_ekf = ("Node name: ekf_filter_node" in info_text
                       and "Endpoint type: SUBSCRIPTION" in info_text
                       and subscription_count is not None and int(subscription_count.group(1)) == 1)
    return {
        "type_exact": bool(topic_type and topic_type.group(1) == "geometry_msgs/msg/PoseWithCovarianceStamped"),
        "publisher_count_zero": bool(publisher_count and int(publisher_count.group(1)) == 0),
        "ekf_is_subscriber": "/set_pose" in ekf_subscribers and endpoint_is_ekf,
        "no_payload": echo_exit_code == 124 and echo_stdout == b"",
    }


def _set_pose_failure_reason(info_text, echo_stdout, echo_exit_code, ekf_subscribers):
    import re
    count = re.search(r"^Publisher count:\s*(\d+)\s*$", info_text, re.MULTILINE)
    if count and int(count.group(1)) > 0:
        return "EKF_SET_POSE_EXTERNAL_PUBLISHER_OBSERVED"
    contract = _set_pose_endpoint_contract(info_text, echo_stdout, echo_exit_code, ekf_subscribers)
    if not all(contract.values()):
        return "EKF_SET_POSE_CONTRACT_FAILED"
    return None


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


def _imu_quaternion_norm(mapping):
    orientation = mapping.get("orientation")
    if not isinstance(orientation, dict):
        return None
    try:
        return math.sqrt(sum(float(orientation[key]) ** 2 for key in ("x", "y", "z", "w")))
    except (KeyError, TypeError, ValueError):
        return None


def _bootstrap_readiness_and_stability(readiness_seen, alive_after_stability):
    return {"bootstrap_readiness": readiness_seen, "bootstrap_stability_20_seconds": readiness_seen and alive_after_stability}


def _composite_liveness(process_alive, observer_completed):
    return process_alive and observer_completed


def _teardown_is_clean(teardown):
    return all(_teardown_predicate(row) for row in teardown)


def _teardown_order_and_count_correct(teardown):
    return len(teardown) == 2 and [row.get("name") for row in teardown] == ["composite", "bootstrap"]


def _teardown_predicate(row):
    return (row.get("leader_returncode") == 0
            and row.get("live_member_pids") == []
            and row.get("zombie_member_pids") == []
            and row.get("outcome") == "STOPPED")


def _teardown_verdict(teardown, reported_aggregate=None):
    predicate = _teardown_is_clean(teardown)
    if reported_aggregate is not None and reported_aggregate is not predicate:
        return "INTERNAL_EVIDENCE_INCONSISTENCY"
    return predicate


def _run_cpp_observer(output_path, env, transcripts):
    command = OBSERVER_EXECUTABLE + ["--output", str(output_path), "--duration-seconds", "30",
                                    "--expected-ekf-node-name", "ekf_filter_node"]
    result = subprocess.run(command, cwd=env["WP06_REPOSITORY_ROOT"], env=env,
                            capture_output=True, timeout=40, check=False)
    (transcripts / "runtime_observer.stdout.bin").write_bytes(result.stdout)
    (transcripts / "runtime_observer.stderr.bin").write_bytes(result.stderr)
    return {"command": command, "exit_code": result.returncode, "stdout_sha256": hashlib.sha256(result.stdout).hexdigest(),
            "stderr_sha256": hashlib.sha256(result.stderr).hexdigest(), "timestamp": _now()}


def _collect_post_observer_transcripts(observer_path, observer_module, env, transcript_dir):
    """Validate observer semantics, then collect the required ROS transcripts."""
    observer_document = observer_module.load_observer_json(observer_path)
    command_specs = [
        ("wheel_echo", ["ros2", "topic", "echo", "/wheel/odometry_raw", "nav_msgs/msg/Odometry", "--once"]),
        ("imu_echo", ["ros2", "topic", "echo", "/imu/data", "sensor_msgs/msg/Imu", "--once"]),
        ("wheel_info", ["ros2", "topic", "info", "--verbose", "/wheel/odometry_raw"]),
        ("imu_info", ["ros2", "topic", "info", "--verbose", "/imu/data"]),
        ("filtered_info", ["ros2", "topic", "info", "--verbose", "/odometry/filtered"]),
        ("ekf_node_info", ["ros2", "node", "info", "/ekf_filter_node"]),
        ("ingress_node_info", ["ros2", "node", "info", "/sim_eval_wheel_imu_ingress"]),
        ("ingress_bridge_node_info", ["ros2", "node", "info", "/sim_eval_wheel_imu_ingress_bridge"]),
        ("clock_bridge_node_info", ["ros2", "node", "info", "/sim_eval_clock_bridge"]),
        ("ekf_use_sim_time", ["ros2", "param", "get", "/ekf_filter_node", "use_sim_time"]),
        ("ingress_use_sim_time", ["ros2", "param", "get", "/sim_eval_wheel_imu_ingress", "use_sim_time"]),
        ("set_pose_info", ["ros2", "topic", "info", "--verbose", "/set_pose"]),
        ("set_pose_echo", ["ros2", "topic", "echo", "/set_pose", "geometry_msgs/msg/PoseWithCovarianceStamped", "--once"]),
    ]
    outputs, transcripts = {}, {}
    for name, command in command_specs:
        timeout = 3 if name == "set_pose_echo" else 8
        meta, stdout, _stderr = _run_transcript(command, env, transcript_dir, name, timeout=timeout)
        transcripts[name] = meta
        outputs[name] = stdout
        if name == "set_pose_echo":
            outputs["set_pose_echo_exit_code"] = str(meta["exit_code"]).encode("ascii")
    return observer_document, transcripts, outputs


def _wheel_imu_sample_contract(wheel, imu, wheel_info_ok, imu_info_ok):
    wheel_ok = (wheel_info_ok and _valid_stamp(wheel)
                and wheel.get("header", {}).get("frame_id") == "odom"
                and wheel.get("child_frame_id") == "base_link"
                and _finite_tree(wheel.get("twist")))
    norm = _imu_quaternion_norm(imu)
    imu_ok = (imu_info_ok and _valid_stamp(imu)
              and imu.get("header", {}).get("frame_id") == "base_link"
              and _finite_tree(imu) and norm is not None and 0.999 <= norm <= 1.001)
    return {"wheel_sample_contract": wheel_ok, "imu_sample_contract": imu_ok}


def _process_group_commands(pgid):
    commands = []
    observable = True
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            stat = (entry / "stat").read_text(encoding="utf-8")
            tail = stat[stat.rfind(")") + 1 :].split()
            if int(tail[2]) == pgid:
                command = (entry / "cmdline").read_bytes().replace(b"\0", b" ").decode("utf-8", "replace").strip()
                commands.append({"pid": int(entry.name), "command": command})
        except FileNotFoundError:
            continue
        except (OSError, ValueError, IndexError):
            observable = False
    return {"commands": commands, "observable": observable}


def _forbidden_process_present(process_group_commands):
    forbidden = ("nav2", "amcl", "slam_toolbox", "map_server", "cmd_vel")
    return any(any(marker in row["command"].lower() for marker in forbidden) for row in process_group_commands.get("commands", []))


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
    observer_module = importlib.import_module("mecanum_nav_bringup.sim_eval_tf_ekf_runtime_observer")
    guard_state_before = verified["guard"]["state"]
    consumed = acquire_guard(guard_file, expected_review_commit, expected_integration_base)
    run_dir.mkdir(parents=True, mode=0o700)
    (run_dir / "transcripts").mkdir(mode=0o700)
    (run_dir / "logs").mkdir(mode=0o700)
    start = _now()
    monotonic_start = time.monotonic()
    record = {
        "schema": RECORD_SCHEMA, "run_id": RUN_ID, "review_commit": expected_review_commit,
        "integration_base": expected_integration_base, "guard_state_before": guard_state_before,
        "guard_state_after_acquire": consumed["state"], "gz_partition": PARTITION, "started_at": start,
        "preflight": {"guard_manifest_sha256": _sha256(root / "docs/governance/evidence/WP-06_6F_TF_EKF_RUNTIME_INGRESS_RUN_007_GUARD_MANIFEST.json"),
                      "decision_sha256": _sha256(root / "docs/governance/decisions/WP-06_SIM_EVAL_TF_EKF_RUNTIME_STATE_ESTIMATION_INGRESS_L2_DECISION.md"),
                      "source_pins": verified["source_pins"], "authorization_acquisition_count": consumed["acquisition_count"]},
        "processes": {}, "transcripts": {},
        "pre_teardown_runtime_acceptance": {key: False for key in (
            "bootstrap_readiness", "bootstrap_stability_20_seconds", "composite_live_through_evidence",
            "composite_stability_5_seconds", "clock_minimum_five_nonzero_strictly_increasing",
            "wheel_info_one_publisher_and_type", "imu_info_one_publisher_and_type",
            "filtered_info_one_publisher_and_type", "wheel_sample_contract", "imu_sample_contract",
            "filtered_odometry_minimum_five_contract_and_monotonicity",
            "dynamic_odom_to_base_link_minimum_five_strictly_increasing_single_gid_owned_by_ekf",
            "dynamic_tf_subscription_qos_contract", "static_base_link_to_lidar_frame_exact",
            "static_tf_edge_publisher_gid_mappable", "static_tf_edge_publisher_gid_unique_mapped",
            "static_tf_owner_is_robot_state_publisher", "static_tf_subscription_qos_contract",
            "map_to_odom_absent_during_full_window", "observer_errors_absent",
            "ekf_use_sim_time_true", "ingress_use_sim_time_true", "ekf_inputs_and_outputs_bounded",
            "ekf_set_pose_admin_endpoint", "ekf_set_pose_zero_publishers_no_payload",
            "ingress_outputs_bounded", "ingress_bridge_outputs_bounded", "clock_bridge_outputs_only_clock",
            "forbidden_topics_and_processes_absent", "runtime_session_completed_without_exception")},
        "teardown_acceptance": {}, "acceptance": {},
    }
    sessions = {}
    observer_document = None
    try:
        bootstrap_log = run_dir / "logs/bootstrap.log"
        sessions["bootstrap"] = _spawn(BOOTSTRAP_COMMAND, bootstrap_log, env)
        sessions["bootstrap"]["log_path"] = str(bootstrap_log)
        record["processes"]["bootstrap"] = {k: sessions["bootstrap"][k] for k in ("pid", "pgid", "command")}
        bootstrap_ready = _wait_readiness(sessions["bootstrap"], b"Entity creation successful.", 90)
        record["pre_teardown_runtime_acceptance"]["bootstrap_readiness"] = bootstrap_ready
        if not bootstrap_ready:
            raise GuardError("BOOTSTRAP_READINESS_FAILED")
        time.sleep(20)
        if sessions["bootstrap"]["process"].poll() is not None:
            raise GuardError("BOOTSTRAP_DIED_DURING_STABILIZATION")
        record["pre_teardown_runtime_acceptance"]["bootstrap_stability_20_seconds"] = True
        (run_dir / "authorization_state.txt").write_text("CONSUMED\n", encoding="utf-8")
        composite_log = run_dir / "logs/composite.log"
        sessions["composite"] = _spawn(COMPOSITE_COMMAND, composite_log, env)
        sessions["composite"]["log_path"] = str(composite_log)
        record["processes"]["composite"] = {k: sessions["composite"][k] for k in ("pid", "pgid", "command")}
        time.sleep(5)
        if sessions["composite"]["process"].poll() is not None:
            record["pre_teardown_runtime_acceptance"]["composite_live_through_evidence"] = False
            raise GuardError("COMPOSITE_EXITED_BEFORE_OBSERVER")
        record["pre_teardown_runtime_acceptance"]["composite_stability_5_seconds"] = True
        observer_path = run_dir / "transcripts/runtime_observer.json"
        record["transcripts"]["runtime_observer"] = _run_cpp_observer(observer_path, env, run_dir / "transcripts")
        observer_document, post_observer_transcripts, outputs = _collect_post_observer_transcripts(
            observer_path, observer_module, env, run_dir / "transcripts")
        record["transcripts"].update(post_observer_transcripts)
        record["observer"] = {
            "path": "transcripts/runtime_observer.json",
            "schema": observer_document.get("schema"),
            "acceptance": observer_document.get("acceptance", {}),
            "failure_reason_literals": observer_document.get("failure_reason_literals", {}),
            "observer_errors": observer_document.get("observer_errors", []),
        }
        process_groups = {name: _process_group_commands(session["pgid"]) for name, session in sessions.items()}
        record["process_group_commands"] = process_groups
        evaluated = _evaluate_acceptance(outputs, observer_document, process_groups)
        record["pre_teardown_runtime_acceptance"].update(evaluated)
        record["pre_teardown_runtime_acceptance"]["composite_live_through_evidence"] = sessions["composite"]["process"].poll() is None
        record["pre_teardown_runtime_acceptance"]["runtime_session_completed_without_exception"] = True
    except Exception as exc:
        record["runtime_exception"] = f"{type(exc).__name__}:{exc}"
    finally:
        teardown = []
        for label in ("composite", "bootstrap"):
            if label in sessions:
                teardown.append(_teardown(sessions[label], label))
        record["teardown"] = teardown
        record["teardown_acceptance"] = {
            "process_group_teardown_clean": _teardown_is_clean(teardown),
            "teardown_order_and_count_correct": _teardown_order_and_count_correct(teardown),
        }
        if record.get("runtime_exception"):
            record["pre_teardown_runtime_acceptance"]["runtime_session_completed_without_exception"] = False
        record["acceptance"] = _finalize_acceptance(record)
        record["failure_reason_literals"] = _failure_reasons(record["acceptance"], observer_document)
        if "outputs" in locals():
            set_pose_text = outputs.get("set_pose_info", b"").decode("utf-8", "replace")
            ekf_info = outputs.get("ekf_node_info", b"").decode("utf-8", "replace")
            ekf_subscribers = _node_section_topics(ekf_info, "Subscribers")
            set_pose_reason = _set_pose_failure_reason(
                set_pose_text, outputs.get("set_pose_echo", b""),
                int(outputs.get("set_pose_echo_exit_code", b"-1")), ekf_subscribers)
            if set_pose_reason:
                record["failure_reason_literals"]["ekf_set_pose_zero_publishers_no_payload"] = set_pose_reason
        record["finished_at"] = _now()
        record["duration_seconds"] = round(time.monotonic() - monotonic_start, 6)
        record["artifact_sha256"] = {}
        for path in sorted(run_dir.rglob("*")):
            if path.is_file() and path.name not in {"artifact_manifest.json", "run_record.json"}:
                record["artifact_sha256"][str(path.relative_to(run_dir))] = _sha256(path)
        _write_json(run_dir / "run_record.json", record)
        files = dict(record["artifact_sha256"])
        files["run_record.json"] = _sha256(run_dir / "run_record.json")
        sums = "".join(f"{digest}  {relative}\n" for relative, digest in sorted(files.items()))
        (run_dir / "SHA256SUMS.txt").write_text(sums, encoding="utf-8")
        files["SHA256SUMS.txt"] = _sha256(run_dir / "SHA256SUMS.txt")
        manifest = {"schema": "wp06_6f_tf_ekf_runtime_artifacts/v1", "files": files}
        _write_json(run_dir / "artifact_manifest.json", manifest)
    return 0 if record["terminal_outcome"] == "WP06_6F_RUNTIME_RUN007_PASS_PENDING_INDEPENDENT_EVIDENCE_AUDIT" else 1


def _finalize_acceptance(record):
    """Compute acceptance and assign exactly one terminal outcome after teardown."""
    runtime = record.get("pre_teardown_runtime_acceptance", {})
    teardown = record.get("teardown_acceptance", {})
    final = {**runtime, **teardown}
    record["teardown_pass"] = teardown.get("process_group_teardown_clean") is True
    runtime_failures = sorted(key for key, value in runtime.items() if value is not True)
    teardown_clean = teardown.get("process_group_teardown_clean") is True
    teardown_order = teardown.get("teardown_order_and_count_correct") is True
    if not teardown_clean:
        failure = "PROCESS_GROUP_TEARDOWN_FAILED"
    elif not teardown_order:
        failure = "TEARDOWN_SEQUENCE_OR_COUNT_INVALID"
    elif runtime_failures:
        runtime_exception = record.get("runtime_exception")
        if runtime_exception:
            failure = f"RUNTIME_SESSION_EXCEPTION:{runtime_exception}"
        else:
            failure = "RUNTIME_ACCEPTANCE_FAILED:" + ",".join(runtime_failures)
    else:
        failure = None
    pass_outcome = "WP06_6F_RUNTIME_RUN007_PASS_PENDING_INDEPENDENT_EVIDENCE_AUDIT"
    fail_outcome = "WP06_6F_RUNTIME_RUN007_FAIL_NO_RETRY_GUARD_CONSUMED"
    outcome = pass_outcome if failure is None else fail_outcome
    if all(value is True for value in final.values()) != (outcome == pass_outcome):
        failure = "INTERNAL_EVIDENCE_INCONSISTENCY"
        outcome = fail_outcome
    if failure is None:
        record.pop("failure", None)
    else:
        record["failure"] = failure
    record["terminal_outcome"] = outcome
    return final


def _evaluate_acceptance(outputs, observer_document, process_groups):
    result = {}
    for name, expected in (("wheel_info", "nav_msgs/msg/Odometry"), ("imu_info", "sensor_msgs/msg/Imu"), ("filtered_info", "nav_msgs/msg/Odometry")):
        text = outputs[name].decode("utf-8", "replace")
        result[f"{name}_one_publisher_and_type"] = _verify_topic_info(text, expected)
    observer_acceptance = (observer_document or {}).get("acceptance", {})
    result.update(observer_acceptance)
    result["ekf_use_sim_time_true"] = outputs["ekf_use_sim_time"].decode("utf-8", "replace").strip().lower().endswith("true")
    result["ingress_use_sim_time_true"] = outputs["ingress_use_sim_time"].decode("utf-8", "replace").strip().lower().endswith("true")
    try:
        wheel = _parse_single_yaml_mapping(outputs["wheel_echo"])
        imu = _parse_single_yaml_mapping(outputs["imu_echo"])
        result.update(_wheel_imu_sample_contract(
            wheel, imu, result.get("wheel_info_one_publisher_and_type", False),
            result.get("imu_info_one_publisher_and_type", False)))
    except Exception:
        result["wheel_sample_contract"] = result["imu_sample_contract"] = False
    result["filtered_odometry_minimum_five_contract_and_monotonicity"] = (
        result.get("filtered_odometry_minimum_five_contract_and_monotonicity", False)
        and result.get("filtered_info_one_publisher_and_type", False)
    )
    ekf_info = outputs["ekf_node_info"].decode("utf-8", "replace")
    ingress_info = outputs["ingress_node_info"].decode("utf-8", "replace")
    ingress_bridge_info = outputs["ingress_bridge_node_info"].decode("utf-8", "replace")
    clock_bridge_info = outputs["clock_bridge_node_info"].decode("utf-8", "replace")
    node_infos = {"ekf": ekf_info, "ingress": ingress_info,
                  "ingress_bridge": ingress_bridge_info, "clock_bridge": clock_bridge_info}
    ekf_subscriber_class = _classify_node_endpoints(ekf_info, "Subscribers")
    ekf_publisher_class = _classify_node_endpoints(ekf_info, "Publishers")
    ekf_subscribers = ekf_subscriber_class["business"]
    ekf_publishers = ekf_publisher_class["business"]
    result["ekf_inputs_and_outputs_bounded"] = (
        ekf_subscribers == EKF_SUBSCRIBER_TOPICS
        and ekf_publishers == EKF_PUBLISHER_TOPICS
        and not ekf_subscriber_class["wrong_direction"]
        and not ekf_publisher_class["wrong_direction"])
    set_pose = _set_pose_endpoint_contract(
        outputs["set_pose_info"].decode("utf-8", "replace"), outputs["set_pose_echo"],
        int(outputs["set_pose_echo_exit_code"]), ekf_subscribers)
    result["ekf_set_pose_admin_endpoint"] = set_pose["type_exact"] and set_pose["ekf_is_subscriber"]
    result["ekf_set_pose_zero_publishers_no_payload"] = set_pose["publisher_count_zero"] and set_pose["no_payload"]
    ingress_publishers = _data_topics(ingress_info, "Publishers")
    result["ingress_outputs_bounded"] = ingress_publishers == {"/wheel/odometry_raw", "/imu/data"}
    ingress_bridge_publishers = _data_topics(ingress_bridge_info, "Publishers")
    result["ingress_bridge_outputs_bounded"] = ingress_bridge_publishers == {"/sim_eval/wheel_joint_states", "/sim_eval/imu_raw"}
    clock_bridge_publishers = _data_topics(clock_bridge_info, "Publishers")
    result["clock_bridge_outputs_only_clock"] = clock_bridge_publishers == {"/clock"}
    forbidden_topic = bool(_topic_policy_violations(node_infos))
    forbidden_process = any(_forbidden_process_present(value) for value in process_groups.values())
    result["forbidden_topics_and_processes_absent"] = not forbidden_topic and not forbidden_process
    return result


def _failure_reasons(acceptance, observer_document):
    observer_reasons = (observer_document or {}).get("failure_reason_literals", {})
    reasons = {}
    defaults = {
        "bootstrap_readiness": "BOOTSTRAP_READINESS_FAILED",
        "bootstrap_stability_20_seconds": "BOOTSTRAP_DIED_DURING_STABILIZATION",
        "composite_live_through_evidence": "COMPOSITE_EXITED_DURING_EVIDENCE",
        "composite_stability_5_seconds": "COMPOSITE_DIED_DURING_STABILITY_WINDOW",
        "wheel_info_one_publisher_and_type": "WHEEL_INPUT_TYPE_OR_PUBLISHER_FAILED",
        "imu_info_one_publisher_and_type": "IMU_INPUT_TYPE_OR_PUBLISHER_FAILED",
        "filtered_info_one_publisher_and_type": "FILTERED_ODOMETRY_TYPE_OR_PUBLISHER_FAILED",
        "wheel_sample_contract": "WHEEL_INPUT_SAMPLE_CONTRACT_FAILED",
        "imu_sample_contract": "IMU_INPUT_SAMPLE_CONTRACT_FAILED",
        "ingress_use_sim_time_true": "INGRESS_USE_SIM_TIME_FALSE_OR_UNAVAILABLE",
        "ekf_use_sim_time_true": "EKF_USE_SIM_TIME_FALSE_OR_UNAVAILABLE",
        "ekf_inputs_and_outputs_bounded": "EKF_NODE_TOPOLOGY_OUT_OF_CONTRACT",
        "ekf_set_pose_admin_endpoint": "EKF_SET_POSE_CONTRACT_FAILED",
        "ekf_set_pose_zero_publishers_no_payload": "EKF_SET_POSE_CONTRACT_FAILED",
        "ingress_outputs_bounded": "INGRESS_NODE_TOPOLOGY_OUT_OF_CONTRACT",
        "ingress_bridge_outputs_bounded": "INGRESS_BRIDGE_TOPOLOGY_OUT_OF_CONTRACT",
        "clock_bridge_outputs_only_clock": "CLOCK_BRIDGE_TOPOLOGY_OUT_OF_CONTRACT",
        "forbidden_topics_and_processes_absent": "FORBIDDEN_BRIDGE_TOPIC_OR_PROCESS_OBSERVED",
        "process_group_teardown_clean": "PROCESS_GROUP_TEARDOWN_FAILED",
        "teardown_order_and_count_correct": "TEARDOWN_SEQUENCE_OR_COUNT_INVALID",
        "clock_minimum_five_nonzero_strictly_increasing": "CLOCK_TIMESTAMP_NOT_STRICTLY_INCREASING_OR_TIMEOUT",
        "dynamic_odom_to_base_link_minimum_five_strictly_increasing_single_gid_owned_by_ekf": "TF_EDGE_PUBLISHER_GID_UNMAPPABLE",
        "filtered_odometry_minimum_five_contract_and_monotonicity": "FILTERED_ODOMETRY_CONTRACT_OR_TIMEOUT",
        "dynamic_tf_subscription_qos_contract": "DYNAMIC_TF_QOS_CONTRACT_MISMATCH",
        "static_base_link_to_lidar_frame_exact": "TF_STATIC_EDGE_MISSING_OR_TRANSFORM_MISMATCH",
        "static_tf_edge_publisher_gid_mappable": "TF_STATIC_EDGE_PUBLISHER_GID_UNMAPPABLE",
        "static_tf_edge_publisher_gid_unique_mapped": "TF_STATIC_EDGE_PUBLISHER_GID_UNMAPPABLE",
        "static_tf_owner_is_robot_state_publisher": "TF_STATIC_EDGE_PUBLISHER_NOT_ROBOT_STATE_PUBLISHER",
        "static_tf_subscription_qos_contract": "TF_STATIC_QOS_CONTRACT_MISMATCH",
        "map_to_odom_absent_during_full_window": "MAP_TO_ODOM_EDGE_OBSERVED_OR_WINDOW_INCOMPLETE",
        "observer_errors_absent": "RUNTIME_OBSERVER_CALLBACK_OR_API_ERROR",
        "runtime_session_completed_without_exception": "RUNTIME_SESSION_EXCEPTION_OCCURRED",
    }
    for key, reason in defaults.items():
        if acceptance.get(key) is not True:
            reasons[key] = observer_reasons.get(key) or reason
    for key, reason in observer_reasons.items():
        reasons[key] = reason
    return reasons


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
