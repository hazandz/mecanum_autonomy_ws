"""Capacity-one pending guard for the separately authorized Run 003 session."""

from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import tempfile


SCHEMA = "mecanum_scan_endpoint_probe_run003_guard/v1"
PENDING = "PENDING_EXACT_INTEGRATION_AND_USER_AUTHORIZATION"
CONSUMED = "CONSUMED"

# Filled from the finalized decision/source pins during candidate preparation.
EXPECTED_CONTEXT = {'authority_packet': {'path': 'docs/governance/decisions/WP-06_SCAN_PROBE_OBSERVATION_AND_TEARDOWN_REMEDIATION_L2_DECISION.md',
                      'sha256': 'ffef8345556eef997476e042a0e433e7c138fe5537cfbb7cf30caedc620867f5'},
 'bootstrap_command_literal': 'ros2 launch ROBOT_URDF_final_description '
                              'sim_eval_scan_probe_run003_bootstrap.launch.py',
 'capacity': 1,
 'commands': {'bootstrap': 'ros2 launch ROBOT_URDF_final_description '
                           'sim_eval_scan_probe_run003_bootstrap.launch.py',
              'probe': 'python3 -m mecanum_nav_bringup.sim_eval_scan_endpoint_probe '
                       '--transcript-directory {run_directory}/transcripts'},
 'gz_partition': 'wp06_scan_probe_run_003',
 'manifest_path': 'docs/governance/evidence/WP-06_SCAN_PROBE_RUN_003_RUNTIME_GUARD_MANIFEST.json',
 'probe_command_literal': 'python3 -m mecanum_nav_bringup.sim_eval_scan_endpoint_probe '
                          '--transcript-directory {run_directory}/transcripts',
 'run_id': 'WP06_6D_SIM_EVAL_SCAN_ENDPOINT_PROBE_RUN_003',
 'runtime_authorization_required': True,
 'source_pins': {'artifacts/simulation/sim_eval_scan_endpoint_probe_evidence/tools/run_scan_endpoint_probe_run003_session.py': 'f00b2c9a54b1105237b3e742a8d0c20d2cae8414de26fab4a233c9b2169453f6',
                 'ros2_ws/src/ROBOT_URDF_final_description/launch/sim_eval_scan_probe.world.sdf': '9978241fe970a24bb2b5f0aefcba41f69164bf5784e3bf6440596f6a975e2736',
                 'ros2_ws/src/ROBOT_URDF_final_description/launch/sim_eval_scan_probe_run003_bootstrap.launch.py': 'a488601483a3fcf558db946063fe13d35b6dc89d20a86ae5218ced14b54f0db7',
                 'ros2_ws/src/ROBOT_URDF_final_description/urdf/ROBOT_URDF_final.gazebo': '1e97b6ea340adc9aecaf320cc432007c6bb37f5922cdc0366dbee50a9a26ff0e',
                 'ros2_ws/src/mecanum_nav_bringup/config/bridge/sim_eval_scan_endpoint_probe.static.yaml': '7e61c620fa03643b4b834ac4a804b252126cde4b224f59bd56c4a431abf20343',
                 'ros2_ws/src/mecanum_nav_bringup/mecanum_nav_bringup/sim_eval_scan_endpoint_probe.py': 'b1f67a0e67fb543e102ea91fd5d6cab7582f3066ecca5bbd95f898642d0dd52e'},
 'teardown_policy': {'signals': ['SIGINT', 'SIGTERM', 'SIGKILL'], 'wait_seconds_each': 10},
 'timeouts': {'bootstrap_readiness_seconds': 90,
              'gz_command_seconds': 5.0,
              'probe_session_seconds': 90}}


class GuardError(ValueError):
    """Raised when the one-shot guard is absent, stale, or mismatched."""


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
        text = raw.decode("utf-8", errors="strict")
        return json.loads(text, object_pairs_hook=_unique_object)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GuardError("invalid UTF-8 JSON") from exc


def canonical_json_bytes(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


@contextmanager
def _exclusive_lock(lock_path):
    lock_path = Path(lock_path)
    descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def _atomic_write(path, raw):
    path = Path(path)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass


def consume_guard(guard_path, expected_context=None):
    """Atomically consume exactly one pending guard after exact context match."""
    path = Path(guard_path)
    context = EXPECTED_CONTEXT if expected_context is None else expected_context
    if not isinstance(context, dict) or not context:
        raise GuardError("expected context is not configured")
    with _exclusive_lock(path.with_suffix(path.suffix + ".lock")):
        source_bytes = path.read_bytes()
        current = load_json_bytes(source_bytes)
        if source_bytes.endswith(b"\n") or canonical_json_bytes(current) != source_bytes:
            raise GuardError("guard bytes are not canonical compact JSON")
        if type(current) is not dict or set(current) != {"schema", "capacity", "state", "context"}:
            raise GuardError("guard shape mismatch")
        if current["schema"] != SCHEMA or type(current["capacity"]) is not int or current["capacity"] != 1:
            raise GuardError("guard schema or capacity mismatch")
        if current["state"] != PENDING:
            raise GuardError("guard is not pending; retries are prohibited")
        if current["context"] != context:
            raise GuardError("guard context mismatch")
        current["state"] = CONSUMED
        raw = canonical_json_bytes(current)
        _atomic_write(path, raw)
        return hashlib.sha256(raw).hexdigest()
