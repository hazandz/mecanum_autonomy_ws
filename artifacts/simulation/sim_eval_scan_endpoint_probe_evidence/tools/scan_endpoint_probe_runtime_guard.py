"""Durable capacity-one guard for a separately authorized future probe run."""

from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import tempfile


SCHEMA = "mecanum_sim_eval_scan_endpoint_probe_runtime_guard/v1"
EXPECTED_PACKET_SHA256 = "9b31b7f32e60dad7832807668488f3213f06a28a975a31c6581d65be754f39aa"
EXPECTED_AUTHORIZATION = {
    "approval_id": "WP06_6D_SIM_EVAL_SCAN_ENDPOINT_PROBE_RUN_001",
    "capacity": 1,
    "command_template": [
        "env",
        "GZ_PARTITION=wp06_scan_probe_run_001",
        "PYTHONPATH={repo_root}/ros2_ws/src/mecanum_nav_bringup",
        "python3",
        "-m",
        "mecanum_nav_bringup.sim_eval_scan_endpoint_probe",
    ],
    "expected_gz_type": "gz.msgs.LaserScan",
    "future_ros_boundary": "GZ_TO_ROS /scan sensor_msgs/msg/LaserScan",
    "gz_partition": "wp06_scan_probe_run_001",
    "max_runtime_seconds": 75,
    "packet_use": "GUARD_SEED_ONLY_REQUIRES_EXACT_INTEGRATED_REF_USER_AUTHORIZATION",
    "pass_criteria": {
        "endpoint_status": "OBSERVED_NOT_PINNED",
        "message_type": "gz.msgs.LaserScan",
        "outcome": "EXACTLY_ONE_MATCH",
    },
    "profile": "sim_eval",
    "run_id": "WP06_6D_SIM_EVAL_SCAN_ENDPOINT_PROBE_RUN_001",
    "source_pins": {
        "gazebo_source": {
            "path": "ros2_ws/src/ROBOT_URDF_final_description/urdf/ROBOT_URDF_final.gazebo",
            "sha256": "1e97b6ea340adc9aecaf320cc432007c6bb37f5922cdc0366dbee50a9a26ff0e",
        },
        "probe_descriptor": {
            "path": "ros2_ws/src/mecanum_nav_bringup/config/bridge/sim_eval_scan_endpoint_probe.static.yaml",
            "sha256": "b18ca0dbec05bfe3031a3ff32be130ccb03e3f78814ca70f26fa9a88525fcee5",
        },
        "probe_module": {
            "path": "ros2_ws/src/mecanum_nav_bringup/mecanum_nav_bringup/sim_eval_scan_endpoint_probe.py",
            "sha256": "450b7f5ad975286e4647fdaab6a2bbd477d09e9d99035c9dd6a143869f1bb7b1",
        },
    },
    "timeout_semantics": "launcher-managed escalation; not SIGINT-only",
}


class GuardRejected(RuntimeError):
    """Raised when the exact one-shot authorization guard cannot be used."""


def canonical_json_bytes(value):
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise GuardRejected(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _read_record(path):
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf") or raw.endswith(b"\n"):
        raise GuardRejected("guard record must be UTF-8 without BOM/final newline")
    try:
        record = json.loads(raw.decode("utf-8"), object_pairs_hook=_reject_duplicate_keys)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GuardRejected("invalid guard record JSON") from exc
    if canonical_json_bytes(record) != raw:
        raise GuardRejected("guard record is not canonical JSON")
    if not isinstance(record, dict):
        raise GuardRejected("guard record must be an object")
    return record


def _atomic_write(path, value):
    data = canonical_json_bytes(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@contextmanager
def _exclusive_lock(path):
    lock_path = path.with_name(path.name + ".lock")
    path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+b") as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


class CapacityOneGuard:
    """Validate exact guard context, atomically consume once, and record outcome."""

    def __init__(self, guard_path, expected_packet_sha256=EXPECTED_PACKET_SHA256):
        self.guard_path = Path(guard_path)
        self.expected_packet_sha256 = expected_packet_sha256

    def acquire(
        self,
        *,
        packet_sha256,
        run_id,
        guard_context,
        source_pins,
        command_literal,
        partition,
    ):
        with _exclusive_lock(self.guard_path):
            record = _read_record(self.guard_path)
            expected = {
                "authorization": EXPECTED_AUTHORIZATION,
                "packet_sha256": self.expected_packet_sha256,
                "schema": SCHEMA,
                "state": "AUTHORIZED_NOT_CONSUMED",
            }
            if record != expected:
                raise GuardRejected("packet, schema, or state does not match exact guard")
            calculated = hashlib.sha256(canonical_json_bytes(record["authorization"])).hexdigest()
            if calculated != self.expected_packet_sha256 or packet_sha256 != calculated:
                raise GuardRejected("packet hash mismatch")
            if canonical_json_bytes(guard_context) != canonical_json_bytes(
                EXPECTED_AUTHORIZATION
            ):
                raise GuardRejected("guard context mismatch")
            if canonical_json_bytes(source_pins) != canonical_json_bytes(
                EXPECTED_AUTHORIZATION["source_pins"]
            ):
                raise GuardRejected("source pins mismatch")
            if canonical_json_bytes(command_literal) != canonical_json_bytes(
                EXPECTED_AUTHORIZATION["command_template"]
            ):
                raise GuardRejected("command literal mismatch")
            if partition != EXPECTED_AUTHORIZATION["gz_partition"]:
                raise GuardRejected("GZ_PARTITION mismatch")
            if run_id != EXPECTED_AUTHORIZATION["run_id"]:
                raise GuardRejected("run ID mismatch")

            # Consume atomically before the subprocess can start: a crash cannot
            # leave a retryable authorization behind. finalize() records outcome.
            record = dict(record)
            record["state"] = "CONSUMED"
            record["consumption"] = {"outcome": "IN_PROGRESS", "run_id": run_id}
            _atomic_write(self.guard_path, record)
            return run_id

    def finalize(self, *, run_id, outcome):
        if not isinstance(outcome, str) or not outcome:
            raise GuardRejected("outcome must be a non-empty string")
        with _exclusive_lock(self.guard_path):
            record = _read_record(self.guard_path)
            if (
                record.get("schema") != SCHEMA
                or record.get("packet_sha256") != self.expected_packet_sha256
                or record.get("state") != "CONSUMED"
                or record.get("authorization") != EXPECTED_AUTHORIZATION
                or record.get("consumption", {}).get("run_id") != run_id
            ):
                raise GuardRejected("cannot finalize a different or unconsumed guard")
            record["consumption"] = {"outcome": outcome, "run_id": run_id}
            _atomic_write(self.guard_path, record)
