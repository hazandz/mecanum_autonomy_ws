"""Atomic capacity-one guard for a separately authorized Run 004 session."""

from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import tempfile


SCHEMA = "mecanum_scan_endpoint_probe_run004_guard/v1"
PENDING = "PENDING_EXACT_INTEGRATION_AND_USER_AUTHORIZATION"
CONSUMED = "CONSUMED"

# Exact non-self-referential context is populated from the finalized packet.
EXPECTED_CONTEXT = {'authority_packet': {'path': 'docs/governance/decisions/WP-06_SCAN_PROBE_READINESS_AND_TEARDOWN_ACCOUNTING_REMEDIATION_L2_DECISION.md', 'sha256': 'f7662d0266563badd73acce5594c52c37c79186570b83fecd7e866f343645e1d'}, 'capacity': 1, 'commands': {'bootstrap': ['ros2', 'launch', 'ROBOT_URDF_final_description', 'sim_eval_scan_probe_run004_server.launch.py'], 'create': ['ros2', 'run', 'ros_gz_sim', 'create', '-world', 'wp06_scan_probe_world', '-topic', '/robot_description', '-name', 'ROBOT_URDF_final', '-allow_renaming', 'false', '-x', '0.0', '-y', '0.0', '-z', '0.1', '-Y', '0.0'], 'probe': ['python3', '-m', 'mecanum_nav_bringup.sim_eval_scan_endpoint_probe', '--transcript-directory', '{run_directory}/transcripts'], 'service': ['gz', 'service', '--list']}, 'guard_path': 'artifacts/simulation/sim_eval_scan_endpoint_probe_evidence/approval_guards/WP06_6D_SIM_EVAL_SCAN_ENDPOINT_PROBE_RUN_004.json', 'gz_partition': 'wp06_scan_probe_run_004', 'manifest_path': 'docs/governance/evidence/WP-06_SCAN_PROBE_RUN_004_RUNTIME_GUARD_MANIFEST.json', 'manifest_sha256': '1c5e9756b8b380166d05aa5c93d449dddb18b07eb9c148ca8dcbfdca400f396b', 'run_id': 'WP06_6D_SIM_EVAL_SCAN_ENDPOINT_PROBE_RUN_004', 'runtime_authorization_required': True, 'source_pins': {'docs/governance/decisions/WP-06_SCAN_PROBE_READINESS_AND_TEARDOWN_ACCOUNTING_REMEDIATION_L2_DECISION.md': 'f7662d0266563badd73acce5594c52c37c79186570b83fecd7e866f343645e1d', 'ros2_ws/src/ROBOT_URDF_final_description/launch/sim_eval_scan_probe.world.sdf': '9978241fe970a24bb2b5f0aefcba41f69164bf5784e3bf6440596f6a975e2736', 'ros2_ws/src/ROBOT_URDF_final_description/launch/sim_eval_scan_probe_run004_server.launch.py': '343ec10823e1e3907f158b2025855025468fd18595957c0bda071cad614fb6f8', 'ros2_ws/src/ROBOT_URDF_final_description/urdf/ROBOT_URDF_final.gazebo': '1e97b6ea340adc9aecaf320cc432007c6bb37f5922cdc0366dbee50a9a26ff0e', 'ros2_ws/src/mecanum_nav_bringup/config/bridge/sim_eval_scan_endpoint_probe.static.yaml': '7e61c620fa03643b4b834ac4a804b252126cde4b224f59bd56c4a431abf20343', 'ros2_ws/src/mecanum_nav_bringup/mecanum_nav_bringup/sim_eval_scan_endpoint_probe.py': '6584ac43ec68080c5915c934b01b52a08a9c48d4d2fb5c3b279bf238326000b2'}, 'teardown_policy': {'direct_child_reap_required': True, 'linux_proc_group_snapshot_required': True, 'signals': ['SIGINT', 'SIGTERM', 'SIGKILL'], 'wait_seconds_each': 10, 'zombies_are_not_live_members': True}, 'timeouts': {'create_seconds': 30, 'probe_seconds': 90, 'service_command_seconds': 2, 'service_poll_interval_seconds': 0.5, 'service_readiness_total_seconds': 30, 'stabilization_seconds': 20, 'teardown_signal_wait_seconds': 10}}


class GuardError(ValueError):
    """Raised when the pending Run 004 guard is invalid or already consumed."""


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise GuardError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_json_bytes(raw):
    if raw.startswith(b"\xef\xbb\xbf"):
        raise GuardError("BOM is forbidden")
    try:
        return json.loads(raw.decode("utf-8", errors="strict"), object_pairs_hook=_unique_object)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GuardError("invalid UTF-8 JSON") from exc


def canonical_json_bytes(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


@contextmanager
def _exclusive_lock(lock_path):
    descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def validate_pending_record(record, expected_context=None):
    expected = EXPECTED_CONTEXT if expected_context is None else expected_context
    if not expected:
        raise GuardError("Run 004 expected context is not configured")
    if type(record) is not dict or set(record) != {"schema", "capacity", "state", "context"}:
        raise GuardError("guard key set mismatch")
    if record["schema"] != SCHEMA or type(record["capacity"]) is not int or record["capacity"] != 1:
        raise GuardError("guard schema or capacity mismatch")
    if record["state"] != PENDING:
        raise GuardError("guard is not pending; retry is prohibited")
    if type(record["context"]) is not dict or record["context"] != expected:
        raise GuardError("guard context mismatch")
    return record


def _atomic_write(path, raw):
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def consume_guard(path, expected_context=None):
    """Atomically transition one exact pending guard to CONSUMED."""
    path = Path(path)
    expected = EXPECTED_CONTEXT if expected_context is None else expected_context
    if not expected:
        raise GuardError("Run 004 expected context is not configured")
    lock_path = path.with_suffix(path.suffix + ".lock")
    with _exclusive_lock(lock_path):
        raw = path.read_bytes()
        if raw.endswith(b"\n"):
            raise GuardError("final newline is forbidden")
        record = load_json_bytes(raw)
        if canonical_json_bytes(record) != raw:
            raise GuardError("guard is not canonical compact JSON")
        validate_pending_record(record, expected)
        record["state"] = CONSUMED
        updated = canonical_json_bytes(record)
        _atomic_write(path, updated)
        return hashlib.sha256(updated).hexdigest()
