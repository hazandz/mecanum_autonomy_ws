"""Run 002-only pending capacity-one guard; standard library only."""

from __future__ import annotations

from contextlib import contextmanager
import fcntl
import hashlib
import json
from pathlib import Path
import tempfile

RUN_ID = "WP06_6D_SIM_EVAL_SCAN_ENDPOINT_PROBE_RUN_002"
GZ_PARTITION = "wp06_scan_probe_run_002"
GUARD_PATH = "artifacts/simulation/sim_eval_scan_endpoint_probe_evidence/approval_guards/WP06_6D_SIM_EVAL_SCAN_ENDPOINT_PROBE_RUN_002.json"
AUTHORITY_PACKET = {
    "path": "docs/governance/decisions/WP-06_SIM_EVAL_SCAN_ENDPOINT_PROBE_DETERMINISTIC_BOOTSTRAP_REMEDIATION_L2_DECISION.md",
    "sha256": "1971fed2517dfa3c726f3b00b3c5ab7756dde86355a8845d55a88b5781fd151f",
}
COMMAND_LITERAL = (
    "env GZ_PARTITION=wp06_scan_probe_run_002 "
    "PYTHONPATH={repo_root}/ros2_ws/src/mecanum_nav_bringup "
    "python3 -m mecanum_nav_bringup.sim_eval_scan_endpoint_probe"
)
SOURCE_PINS = {
    "bootstrap_launch": {
        "path": "ros2_ws/src/ROBOT_URDF_final_description/launch/sim_eval_scan_probe_bootstrap.launch.py",
        "sha256": "64a5f2f0e6435e56004fe050d8d5e70bfb06d33a98fdbf01a6599f129ae82ac0",
    },
    "probe_world": {
        "path": "ros2_ws/src/ROBOT_URDF_final_description/launch/sim_eval_scan_probe.world.sdf",
        "sha256": "9978241fe970a24bb2b5f0aefcba41f69164bf5784e3bf6440596f6a975e2736",
    },
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
}
GUARD_CONTEXT = {
    "authority_packet": AUTHORITY_PACKET,
    "bootstrap_readiness_evidence": "ros_gz_sim create must log exact line: Entity creation successful.",
    "candidate_runtime_authorization": False,
    "command_literal": COMMAND_LITERAL,
    "expected_gz_type": "gz.msgs.LaserScan",
    "future_ros_boundary": "GZ_TO_ROS /scan sensor_msgs/msg/LaserScan",
    "gz_partition": GZ_PARTITION,
    "profile": "sim_eval",
    "run_id": RUN_ID,
    "source_pins": SOURCE_PINS,
    "world_name": "wp06_scan_probe_world",
}
PENDING = "PENDING_EXACT_INTEGRATION_AND_USER_AUTHORIZATION"
CONSUMED = "CONSUMED"


class GuardError(RuntimeError):
    """Raised on any mismatch or exhausted capacity."""


def canonical_json_bytes(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _pairs_no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise GuardError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def read_canonical_record(path: Path) -> dict:
    return read_canonical_record_bytes(path.read_bytes())


def read_canonical_record_bytes(raw: bytes) -> dict:
    if raw.startswith(b"\xef\xbb\xbf") or raw.endswith(b"\n"):
        raise GuardError("guard must be UTF-8 without BOM or trailing newline")
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs_no_duplicates)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GuardError("invalid guard JSON") from exc
    if type(value) is not dict or canonical_json_bytes(value) != raw:
        raise GuardError("guard JSON is not canonical")
    return value


def _validate_record(record: dict, expected_context: dict) -> None:
    if set(record) != {"capacity", "context", "state", "version"}:
        raise GuardError("guard schema mismatch")
    if type(record["capacity"]) is not int or record["capacity"] != 1:
        raise GuardError("only capacity one is accepted")
    if type(record["version"]) is not int or record["version"] != 1:
        raise GuardError("guard version mismatch")
    if record["context"] != expected_context or expected_context != GUARD_CONTEXT:
        raise GuardError("Run 002 context mismatch")
    if record["state"] not in {PENDING, CONSUMED}:
        raise GuardError("invalid guard state")


@contextmanager
def _exclusive_lock(path: Path):
    lock_path = path.with_name(path.name + ".lock")
    with lock_path.open("a+b") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _atomic_write(path: Path, record: dict) -> None:
    data = canonical_json_bytes(record)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".run002-guard-", delete=False) as handle:
        handle.write(data)
        handle.flush()
        temporary = Path(handle.name)
    temporary.replace(path)


def consume_run002_guard(repository_root: Path, guard_path: Path, expected_context: dict = GUARD_CONTEXT) -> dict:
    root = repository_root.resolve()
    target = guard_path.resolve()
    if target != (root / GUARD_PATH).resolve():
        raise GuardError("Run 001 or noncanonical guard path is forbidden")
    packet = root / AUTHORITY_PACKET["path"]
    if not packet.is_file() or hashlib.sha256(packet.read_bytes()).hexdigest() != AUTHORITY_PACKET["sha256"]:
        raise GuardError("authority decision byte SHA-256 mismatch")
    with _exclusive_lock(target):
        record = read_canonical_record(target)
        _validate_record(record, expected_context)
        if record["state"] != PENDING:
            raise GuardError("capacity already consumed; retry forbidden")
        consumed = dict(record)
        consumed["state"] = CONSUMED
        _atomic_write(target, consumed)
        return consumed


def verify_authority_packet(repository_root: Path) -> None:
    packet = repository_root.resolve() / AUTHORITY_PACKET["path"]
    if not packet.is_file() or hashlib.sha256(packet.read_bytes()).hexdigest() != AUTHORITY_PACKET["sha256"]:
        raise GuardError("authority decision byte SHA-256 mismatch")
