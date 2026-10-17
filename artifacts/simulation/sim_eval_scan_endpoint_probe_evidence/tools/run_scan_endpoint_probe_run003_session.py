"""One-shot Run 003 session source; importing this module is inert."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import threading
import time

try:
    from . import scan_endpoint_probe_run003_runtime_guard as guard_module
except ImportError:  # Direct ``python path/to/script.py`` execution.
    import scan_endpoint_probe_run003_runtime_guard as guard_module


SCHEMA = "mecanum_scan_endpoint_probe_run003_session_manifest/v1"
RUN_ID = "WP06_6D_SIM_EVAL_SCAN_ENDPOINT_PROBE_RUN_003"
PARTITION = "wp06_scan_probe_run_003"
DECISION_PATH = "docs/governance/decisions/WP-06_SCAN_PROBE_OBSERVATION_AND_TEARDOWN_REMEDIATION_L2_DECISION.md"
MANIFEST_PATH = "docs/governance/evidence/WP-06_SCAN_PROBE_RUN_003_RUNTIME_GUARD_MANIFEST.json"
GUARD_RELATIVE_PATH = "artifacts/simulation/sim_eval_scan_endpoint_probe_evidence/approval_guards/WP06_6D_SIM_EVAL_SCAN_ENDPOINT_PROBE_RUN_003.json"
PROBE_MODULE_PATH = "ros2_ws/src/mecanum_nav_bringup/mecanum_nav_bringup/sim_eval_scan_endpoint_probe.py"
DESCRIPTOR_PATH = "ros2_ws/src/mecanum_nav_bringup/config/bridge/sim_eval_scan_endpoint_probe.static.yaml"
BOOTSTRAP_PATH = "ros2_ws/src/ROBOT_URDF_final_description/launch/sim_eval_scan_probe_run003_bootstrap.launch.py"
WORLD_PATH = "ros2_ws/src/ROBOT_URDF_final_description/launch/sim_eval_scan_probe.world.sdf"
GAZEBO_SOURCE_PATH = "ros2_ws/src/ROBOT_URDF_final_description/urdf/ROBOT_URDF_final.gazebo"
GUARD_TOOL_PATH = "artifacts/simulation/sim_eval_scan_endpoint_probe_evidence/tools/scan_endpoint_probe_run003_runtime_guard.py"
RUNNER_PATH = "artifacts/simulation/sim_eval_scan_endpoint_probe_evidence/tools/run_scan_endpoint_probe_run003_session.py"
SOURCE_PIN_PATHS = (
    GAZEBO_SOURCE_PATH,
    DESCRIPTOR_PATH,
    PROBE_MODULE_PATH,
    BOOTSTRAP_PATH,
    WORLD_PATH,
    GUARD_RELATIVE_PATH,
    GUARD_TOOL_PATH,
    RUNNER_PATH,
)
BOOTSTRAP_COMMAND = "ros2 launch ROBOT_URDF_final_description sim_eval_scan_probe_run003_bootstrap.launch.py"
PROBE_COMMAND = "python3 -m mecanum_nav_bringup.sim_eval_scan_endpoint_probe --transcript-directory {run_directory}/transcripts"
READINESS_LINE = b"Entity creation successful."
TIMEOUTS = {
    "bootstrap_readiness_seconds": 90,
    "probe_session_seconds": 90,
    "gz_command_seconds": 5.0,
}
TEARDOWN = {"signals": ["SIGINT", "SIGTERM", "SIGKILL"], "wait_seconds_each": 10}


class SessionPreflightError(ValueError):
    """Raised before guard consumption when any exact context check fails."""


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise SessionPreflightError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def canonical_json_bytes(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _load_canonical_json(path):
    raw = Path(path).read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raise SessionPreflightError(f"BOM forbidden: {path}")
    try:
        value = json.loads(raw.decode("utf-8", errors="strict"), object_pairs_hook=_unique_object)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SessionPreflightError(f"invalid JSON: {path}") from exc
    if canonical_json_bytes(value) != raw:
        raise SessionPreflightError(f"JSON is not canonical compact sorted bytes: {path}")
    return value, raw


def _sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def _git_bytes(repo_root, revision_path, git_runner):
    completed = git_runner(
        ["git", "-C", str(repo_root), "show", revision_path],
        shell=False,
        capture_output=True,
        text=False,
        check=False,
    )
    if completed.returncode != 0:
        raise SessionPreflightError(f"git show failed for {revision_path}")
    return completed.stdout


def _git_text(repo_root, args, git_runner):
    completed = git_runner(
        ["git", "-C", str(repo_root), *args],
        shell=False,
        capture_output=True,
        text=False,
        check=False,
    )
    if completed.returncode != 0:
        raise SessionPreflightError(f"git command failed: {' '.join(args)}")
    return completed.stdout.decode("utf-8", errors="strict").strip()


def _validate_manifest(manifest):
    expected_keys = {
        "schema", "classification", "evidence_level", "run_id", "gz_partition",
        "authority_packet", "source_pins", "guard_context", "commands", "timeouts",
        "teardown_policy", "probe_contract",
    }
    if type(manifest) is not dict or set(manifest) != expected_keys:
        raise SessionPreflightError("manifest key set mismatch")
    if manifest["schema"] != SCHEMA or manifest["classification"] != "L2_RUNTIME_OBSERVABILITY_AND_PROCESS_OWNERSHIP_REMEDIATION":
        raise SessionPreflightError("manifest schema/classification mismatch")
    if manifest["evidence_level"] != "IMPLEMENTED_OFFLINE_GUARD_AND_SESSION_SOURCE_ONLY":
        raise SessionPreflightError("manifest evidence level mismatch")
    if manifest["run_id"] != RUN_ID or manifest["gz_partition"] != PARTITION:
        raise SessionPreflightError("manifest run context mismatch")
    authority = manifest["authority_packet"]
    if type(authority) is not dict or set(authority) != {"path", "sha256"} or authority["path"] != DECISION_PATH:
        raise SessionPreflightError("authority packet path mismatch")
    if type(authority["sha256"]) is not str or re.fullmatch(r"[0-9a-f]{64}", authority["sha256"]) is None:
        raise SessionPreflightError("authority packet hash malformed")
    pins = manifest["source_pins"]
    if type(pins) is not dict or set(pins) != set(SOURCE_PIN_PATHS):
        raise SessionPreflightError("source pin key set mismatch")
    if any(type(value) is not str or re.fullmatch(r"[0-9a-f]{64}", value) is None for value in pins.values()):
        raise SessionPreflightError("invalid source hash")
    commands = manifest["commands"]
    if type(commands) is not dict or commands != {
        "bootstrap": BOOTSTRAP_COMMAND,
        "probe": PROBE_COMMAND,
    }:
        raise SessionPreflightError("command literal mismatch")
    if manifest["timeouts"] != TIMEOUTS or manifest["teardown_policy"] != TEARDOWN:
        raise SessionPreflightError("timeout or teardown policy mismatch")
    if manifest["probe_contract"] != {
        "expected_gz_type": "gz.msgs.LaserScan",
        "candidate_leaf": "scan",
        "maximum_candidate_topics": 16,
        "maximum_transcript_bytes_per_stream": 1048576,
        "future_ros_boundary_non_claim": "GZ_TO_ROS /scan sensor_msgs/msg/LaserScan",
    }:
        raise SessionPreflightError("probe contract mismatch")
    return manifest


def preflight(
    repository_root,
    guard_path,
    run_directory,
    run_id,
    gz_partition,
    expected_integration_commit,
    *,
    git_runner=subprocess.run,
):
    """Verify repository, authority, manifest, pending guard and exact pins."""
    root = Path(repository_root).resolve()
    guard_file = Path(guard_path).resolve()
    run_dir = Path(run_directory).resolve()
    if re.fullmatch(r"[0-9a-f]{40}", expected_integration_commit or "") is None:
        raise SessionPreflightError("integration commit must be exact 40-hex")
    expected_commit = expected_integration_commit
    if run_id != RUN_ID or gz_partition != PARTITION:
        raise SessionPreflightError("run ID or partition mismatch")
    if guard_file != (root / GUARD_RELATIVE_PATH).resolve():
        raise SessionPreflightError("guard path mismatch")
    expected_run_dir = root / "artifacts/simulation/sim_eval_scan_endpoint_probe_evidence/runs" / RUN_ID
    if run_dir != expected_run_dir.resolve():
        raise SessionPreflightError("run directory path mismatch")
    if run_dir.exists():
        raise SessionPreflightError("run directory already exists")
    origin = _git_text(root, ["remote", "get-url", "origin"], git_runner)
    if origin != "https://github.com/hazandz/mecanum_autonomy_ws.git":
        raise SessionPreflightError("origin mismatch")
    head = _git_text(root, ["rev-parse", "HEAD"], git_runner)
    integration = _git_text(root, ["rev-parse", "origin/integration/implementation"], git_runner)
    if head != expected_commit or integration != expected_commit:
        raise SessionPreflightError("HEAD/integration ref mismatch")
    if _git_text(root, ["status", "--porcelain"], git_runner):
        raise SessionPreflightError("worktree is not clean")

    manifest_path = root / MANIFEST_PATH
    manifest, manifest_raw = _load_canonical_json(manifest_path)
    _validate_manifest(manifest)
    if _git_bytes(root, f"{expected_commit}:{MANIFEST_PATH}", git_runner) != manifest_raw:
        raise SessionPreflightError("manifest bytes differ from integrated commit")

    decision_path = root / DECISION_PATH
    decision_raw = decision_path.read_bytes()
    if _sha256(decision_raw) != manifest["authority_packet"]["sha256"]:
        raise SessionPreflightError("decision authority SHA mismatch")
    if _git_bytes(root, f"{expected_commit}:{DECISION_PATH}", git_runner) != decision_raw:
        raise SessionPreflightError("decision bytes differ from integrated commit")

    for relative_path, expected_hash in manifest["source_pins"].items():
        local_raw = (root / relative_path).read_bytes()
        if _sha256(local_raw) != expected_hash:
            raise SessionPreflightError(f"source pin mismatch: {relative_path}")
        if _git_bytes(root, f"{expected_commit}:{relative_path}", git_runner) != local_raw:
            raise SessionPreflightError(f"source differs from integrated blob: {relative_path}")

    guard_raw = guard_file.read_bytes()
    if _git_bytes(root, f"{expected_commit}:{GUARD_RELATIVE_PATH}", git_runner) != guard_raw:
        raise SessionPreflightError("guard bytes differ from integrated commit")
    guard_record = guard_module.load_json_bytes(guard_raw)
    if guard_raw.endswith(b"\n") or guard_module.canonical_json_bytes(guard_record) != guard_raw:
        raise SessionPreflightError("guard bytes are not canonical compact JSON")
    if type(guard_record) is not dict or set(guard_record) != {"schema", "capacity", "state", "context"}:
        raise SessionPreflightError("guard shape mismatch")
    if guard_record["schema"] != guard_module.SCHEMA or guard_record["capacity"] != 1:
        raise SessionPreflightError("guard schema/capacity mismatch")
    if guard_record["state"] != guard_module.PENDING:
        raise SessionPreflightError("guard is not pending")
    if guard_record["context"] != manifest["guard_context"]:
        raise SessionPreflightError("guard context differs from manifest")
    if guard_record["context"] != guard_module.EXPECTED_CONTEXT:
        raise SessionPreflightError("guard context differs from guard tool")
    if guard_record["context"].get("run_id") != RUN_ID or guard_record["context"].get("gz_partition") != PARTITION:
        raise SessionPreflightError("guard run context mismatch")
    if guard_record["context"].get("authority_packet") != manifest["authority_packet"]:
        raise SessionPreflightError("guard authority mismatch")
    if guard_record["context"].get("source_pins") != {
        key: value for key, value in manifest["source_pins"].items()
        if key not in {GUARD_RELATIVE_PATH, GUARD_TOOL_PATH}
    }:
        raise SessionPreflightError("guard source pins mismatch")
    if guard_record["context"].get("commands") != manifest["commands"]:
        raise SessionPreflightError("guard commands mismatch")
    return {
        "repository_root": root,
        "guard_path": guard_file,
        "run_directory": run_dir,
        "integration_commit": expected_commit,
        "manifest": manifest,
        "manifest_sha256": _sha256(manifest_raw),
    }


def _utc_now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _read_bootstrap_output(process, log_path, readiness_event):
    carry = b""
    with open(log_path, "wb") as log:
        while True:
            chunk = process.stdout.read(65536)
            if not chunk:
                break
            log.write(chunk)
            log.flush()
            carry = (carry + chunk)[-len(READINESS_LINE) - 8:]
            if READINESS_LINE in carry:
                readiness_event.set()


def _wait_for_ready(process, event, timeout_seconds, *, clock=time.monotonic, sleeper=time.sleep):
    deadline = clock() + timeout_seconds
    while clock() < deadline:
        if event.is_set():
            return True
        if process.poll() is not None:
            return False
        sleeper(min(0.1, max(0.0, deadline - clock())))
    return event.is_set()


def _process_group_exists(pgid):
    try:
        os.killpg(pgid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def _teardown_process_group(process, signal_group, *, group_exists=_process_group_exists, sleeper=time.sleep):
    timeline = []
    if process is None:
        return timeline, "NOT_STARTED"
    pgid = process.pid
    if not group_exists(pgid):
        return timeline, "ALREADY_EXITED"
    for label, sig in (("SIGINT", signal.SIGINT), ("SIGTERM", signal.SIGTERM), ("SIGKILL", signal.SIGKILL)):
        entry = {"signal": label, "pgid": pgid, "sent_utc": _utc_now()}
        try:
            signal_group(pgid, sig)
            entry["sent"] = True
        except ProcessLookupError:
            entry["sent"] = False
            entry["process_lookup_error"] = True
            entry["exited"] = True
            timeline.append(entry)
            return timeline, "STOPPED"
        # The launch parent may exit while descendants remain in its session.
        # Check the whole runner-owned group, not just the Popen leader.
        group_gone = False
        for _ in range(TEARDOWN["wait_seconds_each"] * 10):
            try:
                exists = group_exists(pgid)
            except OSError:
                exists = True
            if not exists:
                group_gone = True
                break
            sleeper(0.1)
        if group_gone:
            if process.poll() is None:
                try:
                    process.wait(timeout=0)
                except subprocess.TimeoutExpired:
                    pass
            entry["exited"] = True
            timeline.append(entry)
            return timeline, "STOPPED"
        entry["exited"] = False
        timeline.append(entry)
    return timeline, "STILL_RUNNING_AFTER_SIGKILL_WAIT"


def _probe_argv(run_directory):
    return [
        "python3", "-m", "mecanum_nav_bringup.sim_eval_scan_endpoint_probe",
        "--transcript-directory", str(Path(run_directory) / "transcripts"),
    ]


def _validate_transcript_observations(probe_result, run_directory):
    observations = probe_result.get("command_observations")
    if type(observations) is not list:
        raise ValueError("probe command observations missing")
    root = Path(run_directory).resolve()
    transcript_hashes = []
    for observation in observations:
        if type(observation) is not dict or type(observation.get("argv")) is not list:
            raise ValueError("malformed command observation")
        for stream in ("stdout", "stderr"):
            relative_path = observation.get(f"{stream}_path")
            expected_hash = observation.get(f"{stream}_sha256")
            expected_size = observation.get(f"{stream}_size_bytes")
            if type(relative_path) is not str or not relative_path.startswith("transcripts/"):
                raise ValueError("transcript path must be relative under transcripts/")
            path = (root / relative_path).resolve()
            if root not in path.parents:
                raise ValueError("transcript path escaped run directory")
            raw = path.read_bytes()
            actual_hash = _sha256(raw)
            if actual_hash != expected_hash or len(raw) != expected_size:
                raise ValueError(f"transcript bytes do not match metadata: {relative_path}")
            transcript_hashes.append({
                "path": relative_path,
                "sha256": actual_hash,
                "size_bytes": len(raw),
            })
    return transcript_hashes


def execute_session(
    repository_root,
    guard_path,
    run_directory,
    run_id,
    gz_partition,
    expected_integration_commit,
    *,
    git_runner=subprocess.run,
    process_factory=subprocess.Popen,
    probe_runner=subprocess.run,
    signal_group=os.killpg,
    group_exists=_process_group_exists,
    clock=time.monotonic,
    sleeper=time.sleep,
    readiness_waiter=_wait_for_ready,
):
    """Consume the pending guard, run one bootstrap/probe session, then teardown."""
    checked = preflight(
        repository_root, guard_path, run_directory, run_id, gz_partition,
        expected_integration_commit, git_runner=git_runner,
    )
    root = checked["repository_root"]
    run_dir = checked["run_directory"]
    run_dir.mkdir(mode=0o700, parents=True, exist_ok=False)
    transcript_dir = run_dir / "transcripts"
    transcript_dir.mkdir(mode=0o700)
    record = {
        "schema": "mecanum_scan_endpoint_probe_run003_record/v1",
        "run_id": RUN_ID,
        "integration_commit": checked["integration_commit"],
        "manifest_sha256": checked["manifest_sha256"],
        "source_pins": checked["manifest"]["source_pins"],
        "started_utc": _utc_now(),
        "bootstrap_readiness": False,
        "bootstrap_pid": None,
        "bootstrap_pgid": None,
        "probe_result": None,
        "probe_stdout_sha256": None,
        "probe_stderr_sha256": None,
        "signal_timeline": [],
        "teardown_outcome": "NOT_STARTED",
        "session_error": None,
    }
    process = None
    reader = None
    return_code = 1
    try:
        context = checked["manifest"]["guard_context"]
        guard_module.consume_guard(checked["guard_path"], context)
        env = os.environ.copy()
        env["GZ_PARTITION"] = PARTITION
        bootstrap_argv = ["ros2", "launch", "ROBOT_URDF_final_description", "sim_eval_scan_probe_run003_bootstrap.launch.py"]
        process = process_factory(
            bootstrap_argv,
            cwd=str(root),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            shell=False,
            start_new_session=True,
        )
        record["bootstrap_pid"] = process.pid
        record["bootstrap_pgid"] = process.pid
        ready_event = threading.Event()
        reader = threading.Thread(
            target=_read_bootstrap_output,
            args=(process, run_dir / "bootstrap.log", ready_event),
            daemon=True,
        )
        reader.start()
        ready_start = clock()
        ready = readiness_waiter(
            process, ready_event, TIMEOUTS["bootstrap_readiness_seconds"],
            clock=clock, sleeper=sleeper,
        )
        record["bootstrap_readiness_wait_seconds"] = round(clock() - ready_start, 6)
        record["bootstrap_readiness"] = bool(ready)
        if ready and process.poll() is not None:
            record["bootstrap_readiness"] = False
            ready = False
        if ready:
            probe_argv = _probe_argv(run_dir)
            probe_start = clock()
            try:
                result = probe_runner(
                    probe_argv,
                    cwd=str(root),
                    env=env,
                    shell=False,
                    capture_output=True,
                    text=False,
                    timeout=TIMEOUTS["probe_session_seconds"],
                    check=False,
                )
                stdout = result.stdout or b""
                stderr = result.stderr or b""
                record["probe_exit_code"] = result.returncode
                record["probe_result"] = json.loads(stdout.decode("utf-8", errors="strict"))
                record["transcript_hashes"] = _validate_transcript_observations(
                    record["probe_result"], run_dir
                )
                return_code = 0 if result.returncode == 0 and record["probe_result"].get("outcome") == "EXACTLY_ONE_MATCH" else 1
            except subprocess.TimeoutExpired as exc:
                stdout = exc.stdout or b""
                stderr = exc.stderr or b""
                record["probe_exit_code"] = None
                record["probe_timeout"] = True
                return_code = 1
            except Exception as exc:  # Keep the one-shot consumed and preserve the error.
                stdout, stderr = b"", b""
                record["probe_exit_code"] = None
                record["session_error"] = f"probe: {type(exc).__name__}: {exc}"
                return_code = 1
            record["probe_duration_seconds"] = round(clock() - probe_start, 6)
            record["probe_stdout_sha256"] = _sha256(stdout)
            record["probe_stderr_sha256"] = _sha256(stderr)
            record["probe_stdout_size_bytes"] = len(stdout)
            record["probe_stderr_size_bytes"] = len(stderr)
        else:
            record["session_error"] = "bootstrap readiness line not observed within 90 seconds"
            return_code = 1
    except Exception as exc:
        record["session_error"] = f"{type(exc).__name__}: {exc}"
        return_code = 1
    finally:
        timeline, teardown = _teardown_process_group(
            process, signal_group, group_exists=group_exists, sleeper=sleeper
        )
        record["signal_timeline"] = timeline
        record["teardown_outcome"] = teardown
        if reader is not None:
            reader.join(timeout=2)
        log_path = run_dir / "bootstrap.log"
        if log_path.exists():
            raw_log = log_path.read_bytes()
            record["bootstrap_log_sha256"] = _sha256(raw_log)
            record["bootstrap_log_size_bytes"] = len(raw_log)
        if process is not None:
            record["bootstrap_exit_status"] = process.poll()
        record["finished_utc"] = _utc_now()
        record_raw = canonical_json_bytes(record)
        temp_path = run_dir / ".run_record.json.tmp"
        temp_path.write_bytes(record_raw)
        os.replace(temp_path, run_dir / "run_record.json")
    return record, return_code


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", required=True)
    parser.add_argument("--guard-path", required=True)
    parser.add_argument("--run-directory", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--gz-partition", required=True)
    parser.add_argument("--expected-integration-commit", required=True)
    args = parser.parse_args(argv)
    record, code = execute_session(
        args.repository_root, args.guard_path, args.run_directory,
        args.run_id, args.gz_partition, args.expected_integration_commit,
    )
    print(json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
