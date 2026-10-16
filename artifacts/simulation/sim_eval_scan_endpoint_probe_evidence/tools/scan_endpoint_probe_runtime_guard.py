"""Atomic capacity-one guard for a separately authorized future probe run."""

from __future__ import annotations

from contextlib import contextmanager
import fcntl
import hashlib
import json
from pathlib import Path
import tempfile
from typing import Any, Mapping


AUTHORITY_PACKET = {
    "path": "docs/governance/decisions/WP-06_SIM_EVAL_SCAN_ENDPOINT_PROBE_RUNTIME_BOOTSTRAP_AND_GUARD.md",
    "sha256": "d053fb4e6623cd753d63d4e1c646c476124579946671d389a16aba333d1b69e6",
}
RUN_ID = "WP06_6D_SIM_EVAL_SCAN_ENDPOINT_PROBE_RUN_001"
GZ_PARTITION = "wp06_scan_probe_run_001"
COMMAND_LITERAL = (
    "env GZ_PARTITION=wp06_scan_probe_run_001 "
    "PYTHONPATH={repo_root}/ros2_ws/src/mecanum_nav_bringup "
    "python3 -m mecanum_nav_bringup.sim_eval_scan_endpoint_probe"
)
SOURCE_PINS = {
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
    "command_literal": COMMAND_LITERAL,
    "expected_gz_type": "gz.msgs.LaserScan",
    "future_ros_boundary": "GZ_TO_ROS /scan sensor_msgs/msg/LaserScan",
    "gz_partition": GZ_PARTITION,
    "profile": "sim_eval",
    "run_id": RUN_ID,
    "source_pins": SOURCE_PINS,
}
PENDING = "PENDING_EXACT_INTEGRATION_AND_USER_AUTHORIZATION"
CONSUMED = "CONSUMED"


class GuardError(RuntimeError):
    """Raised whenever the capacity-one context is not exactly valid."""


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _duplicate_key_reject(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise GuardError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def read_canonical_record(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf") or raw.endswith(b"\n"):
        raise GuardError("guard JSON must be UTF-8 without BOM or final newline")
    try:
        record = json.loads(raw.decode("utf-8"), object_pairs_hook=_duplicate_key_reject)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise GuardError("guard JSON is invalid") from error
    if type(record) is not dict or canonical_json_bytes(record) != raw:
        raise GuardError("guard JSON is not canonical")
    return record


def _validate_record(record: Mapping[str, Any], context: Mapping[str, Any]) -> None:
    if set(record) != {"capacity", "context", "state", "version"}:
        raise GuardError("guard record keys differ from the exact schema")
    if record["version"] != 1 or record["capacity"] != 1:
        raise GuardError("guard capacity/version differs from the exact context")
    if record["context"] != context:
        raise GuardError("guard context mismatch")
    if record["state"] not in {PENDING, CONSUMED}:
        raise GuardError("guard state is invalid")


@contextmanager
def _locked(path: Path):
    lock_path = path.with_name(path.name + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def _atomic_write(path: Path, record: Mapping[str, Any]) -> None:
    payload = canonical_json_bytes(record)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".guard-", delete=False) as handle:
        handle.write(payload)
        handle.flush()
        handle_name = handle.name
    Path(handle_name).replace(path)


def consume_pending_guard(path: Path, expected_context: Mapping[str, Any]) -> dict[str, Any]:
    """Atomically transition only the exact pending capacity-one record."""
    with _locked(path):
        record = read_canonical_record(path)
        _validate_record(record, expected_context)
        if record["state"] != PENDING:
            raise GuardError("guard capacity has already been consumed")
        consumed = dict(record)
        consumed["state"] = CONSUMED
        _atomic_write(path, consumed)
        return consumed


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_authority_packet(repository_root: Path, authority_packet: Mapping[str, Any] = AUTHORITY_PACKET) -> None:
    if authority_packet != AUTHORITY_PACKET:
        raise GuardError("authority packet context mismatch")
    packet_path = repository_root / AUTHORITY_PACKET["path"]
    if not packet_path.is_file() or sha256_file(packet_path) != AUTHORITY_PACKET["sha256"]:
        raise GuardError("authority packet byte SHA-256 mismatch")
