#!/usr/bin/env python3
"""Pure-Python, approval-bound capacity-one guard for passive evidence runs."""
from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

STATE_AUTHORIZED = "authorized_not_consumed"
STATE_CONSUMED = "consumed"


def _json_bytes(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True) + "\n").encode("utf-8")


def atomic_write_json(path: Path, value: dict[str, Any]) -> tuple[bool, str]:
    """Write only by same-directory temporary file plus os.replace; fail closed."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.tmp.{os.getpid()}")
        with temporary.open("xb") as handle:
            handle.write(_json_bytes(value))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        return True, "ready"
    except OSError as exc:
        try:
            temporary.unlink(missing_ok=True)  # type: ignore[name-defined]
        except Exception:
            pass
        return False, f"atomic-write failure: {type(exc).__name__}: {exc}"


def load_json_object(path: Path) -> tuple[bool, dict[str, Any] | None, str]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return False, None, f"malformed or unreadable guard record: {type(exc).__name__}: {exc}"
    if not isinstance(value, dict):
        return False, None, "malformed guard record: root must be an object"
    return True, value, "ready"


def _expected_record(context: dict[str, Any], created_at_utc: str) -> dict[str, Any]:
    return {
        "schema": "s3_d3_approval_bound_guard/v1",
        "approval_id": context["approval_id"],
        "authority_packet": context["authority_packet"],
        "authority_packet_sha256": context["authority_packet_sha256"],
        "world": context["world"],
        "world_sha256": context["world_sha256"],
        "literals": context["literals"],
        "capacity": 1,
        "state": STATE_AUTHORIZED,
        "created_at_utc": created_at_utc,
        "run_id": None,
        "consumed_at_utc": None,
        "final_status": None,
    }


def validate_record(record: dict[str, Any], context: dict[str, Any], *, require_authorized: bool) -> tuple[bool, str]:
    required = {
        "schema": "s3_d3_approval_bound_guard/v1",
        "approval_id": context["approval_id"],
        "authority_packet": context["authority_packet"],
        "authority_packet_sha256": context["authority_packet_sha256"],
        "world": context["world"],
        "world_sha256": context["world_sha256"],
        "literals": context["literals"],
        "capacity": 1,
    }
    for key, expected in required.items():
        if record.get(key) != expected:
            return False, f"approval-bound guard mismatch: {key}"
    state = record.get("state")
    if state not in (STATE_AUTHORIZED, STATE_CONSUMED):
        return False, "malformed guard record: invalid state"
    if require_authorized and state != STATE_AUTHORIZED:
        return False, "approval already consumed"
    if state == STATE_AUTHORIZED and any(record.get(key) is not None for key in ("run_id", "consumed_at_utc", "final_status")):
        return False, "malformed guard record: authorized record contains consumption fields"
    if state == STATE_CONSUMED and (not isinstance(record.get("run_id"), str) or not record["run_id"] or not isinstance(record.get("final_status"), str) or not record["final_status"]):
        return False, "malformed guard record: consumed record lacks final identity/status"
    return True, "ready"


def initialize_guard(path: Path, context: dict[str, Any], created_at_utc: str) -> tuple[bool, str]:
    if path.exists():
        ok, record, reason = load_json_object(path)
        if not ok or record is None:
            return False, reason
        return validate_record(record, context, require_authorized=False)
    return atomic_write_json(path, _expected_record(context, created_at_utc))


def acquire_guard(path: Path, context: dict[str, Any]) -> tuple[bool, str, Path | None]:
    ok, record, reason = load_json_object(path)
    if not ok or record is None:
        return False, reason, None
    ok, reason = validate_record(record, context, require_authorized=True)
    if not ok:
        return False, reason, None
    lock = path.with_name(path.name + ".lock")
    try:
        lock.mkdir()
    except OSError as exc:
        return False, f"approval lock unavailable: {type(exc).__name__}: {exc}", None
    ok, record, reason = load_json_object(path)
    if not ok or record is None:
        shutil.rmtree(lock, ignore_errors=True)
        return False, reason, None
    ok, reason = validate_record(record, context, require_authorized=True)
    if not ok:
        shutil.rmtree(lock, ignore_errors=True)
        return False, reason, None
    return True, "ready", lock


def consume_guard(path: Path, lock: Path, context: dict[str, Any], run_id: str, final_status: str, consumed_at_utc: str) -> tuple[bool, str]:
    if not isinstance(run_id, str) or not run_id or not isinstance(final_status, str) or not final_status:
        return False, "invalid consumption identity/status"
    if not lock.is_dir():
        return False, "approval lock missing before consumption"
    ok, record, reason = load_json_object(path)
    if not ok or record is None:
        return False, reason
    ok, reason = validate_record(record, context, require_authorized=True)
    if not ok:
        return False, reason
    consumed = dict(record)
    consumed.update({"state": STATE_CONSUMED, "run_id": run_id, "consumed_at_utc": consumed_at_utc, "final_status": final_status})
    ok, reason = atomic_write_json(path, consumed)
    if not ok:
        return False, reason
    try:
        lock.rmdir()
    except OSError as exc:
        return False, f"approval consumed but lock cleanup failed: {type(exc).__name__}: {exc}"
    return True, "ready"


def offline_self_test() -> tuple[bool, dict[str, Any]]:
    """Exercise guard state/atomicity in a temporary directory only; no ROS/Gazebo."""
    context = {
        "approval_id": "S3.3.15_POST_REPAIR_PASSIVE_CONTACT_RUN",
        "authority_packet": "docs/S3_D3_Post_Repair_Passive_Contact_Run_Approval_Packet_DRAFT.md",
        "authority_packet_sha256": "a" * 64,
        "world": "world_demo",
        "world_sha256": "b" * 64,
        "literals": {"collision": "s3_d3_base_contact_collision", "sensor": "s3_d3_base_contact_sensor", "raw_topic": "/s3_d3/contact/raw", "gz_type": "gz.msgs.Contacts", "ros_type": "ros_gz_interfaces/msg/Contacts", "direction": "GZ_TO_ROS"},
    }
    results: dict[str, Any] = {}
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        old = base / "replacement_run_consumed.json"
        old_bytes = b'{"old":"S3.3.12"}\n'
        old.write_bytes(old_bytes)
        guard = base / "approval_guards/S3.3.15_POST_REPAIR_PASSIVE_CONTACT_RUN.json"
        ok, reason = initialize_guard(guard, context, "2026-09-26T00:00:00Z")
        results["initialize_authorized"] = {"passed": ok, "reason": reason}
        results["old_record_unchanged"] = {"passed": old.read_bytes() == old_bytes}
        ok, reason, lock = acquire_guard(guard, context)
        results["old_consumed_does_not_block_new_approval"] = {"passed": ok, "reason": reason}
        if ok and lock is not None:
            consumed_ok, consumed_reason = consume_guard(guard, lock, context, "test-run", "INVALID", "2026-09-26T00:00:01Z")
        else:
            consumed_ok, consumed_reason = False, "acquire failed"
        results["single_acquire_and_consume"] = {"passed": consumed_ok, "reason": consumed_reason}
        ok, reason, _ = acquire_guard(guard, context)
        results["second_acquire_rejected"] = {"passed": not ok and reason == "approval already consumed", "reason": reason}
        mismatch = dict(context); mismatch["authority_packet_sha256"] = "c" * 64
        ok, reason = initialize_guard(guard, mismatch, "unused")
        results["packet_hash_mismatch_rejected"] = {"passed": not ok and "authority_packet_sha256" in reason, "reason": reason}
        world_hash_mismatch = dict(context); world_hash_mismatch["world_sha256"] = "d" * 64
        ok, reason, _ = acquire_guard(guard, world_hash_mismatch)
        results["world_hash_mismatch_rejected"] = {"passed": not ok and "world_sha256" in reason, "reason": reason}
        literals_mismatch = dict(context); literals_mismatch["literals"] = dict(context["literals"]); literals_mismatch["literals"]["world"] = "wrong"
        other = base / "other.json"
        initialize_guard(other, context, "2026-09-26T00:00:00Z")
        ok, reason, _ = acquire_guard(other, literals_mismatch)
        results["literal_mismatch_rejected"] = {"passed": not ok and "literals" in reason, "reason": reason}
        malformed = base / "malformed.json"; malformed.write_text("not-json", encoding="utf-8")
        ok, reason, _ = acquire_guard(malformed, context)
        results["malformed_record_rejected"] = {"passed": not ok and "malformed" in reason, "reason": reason}
        locked = base / "locked.json"; initialize_guard(locked, context, "2026-09-26T00:00:00Z"); locked.with_name(locked.name + ".lock").mkdir()
        ok, reason, _ = acquire_guard(locked, context)
        results["lock_failure_rejected"] = {"passed": not ok and "lock unavailable" in reason, "reason": reason}
        parent_file = base / "parent_file"; parent_file.write_text("x", encoding="utf-8")
        ok, reason = atomic_write_json(parent_file / "child.json", {"x": 1})
        results["atomic_write_failure_rejected"] = {"passed": not ok and "atomic-write failure" in reason, "reason": reason}
    passed = all(value["passed"] for value in results.values())
    return passed, {"offline_approval_bound_guard_self_test": "PASS" if passed else "FAIL", "results": results}


if __name__ == "__main__":
    ok, result = offline_self_test()
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    raise SystemExit(0 if ok else 1)
