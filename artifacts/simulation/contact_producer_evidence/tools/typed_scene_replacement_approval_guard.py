#!/usr/bin/env python3
"""Trusted, approval-bound capacity-one guard for S3.3.47; no runtime APIs."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import shutil
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

AUTHORIZED = "authorized_not_consumed"
CONSUMED = "consumed"
APPROVAL_ID = "S3.3.47_TYPED_SCENE_OBSERVER_REPLACEMENT_RUNTIME_RUN"
SCHEMA = "s3_d3_typed_scene_replacement_guard/v4"
PACKET_PATH = "docs/S3_D3_Typed_Scene_Observer_S3_3_47_Replacement_Runtime_Run_Approval_Packet_DRAFT.md"
SUPERVISOR_PATH = "artifacts/simulation/contact_producer_evidence/tools/run_typed_scene_observer.py"
LAUNCH_PATH = "ros2_ws/src/ROBOT_URDF_final_description/launch/typed_scene_observer.launch.py"
HELPER_PATH = "artifacts/simulation/contact_producer_evidence/tools/typed_scene_observer.cpp"
GUARD_HELPER_PATH = "artifacts/simulation/contact_producer_evidence/tools/typed_scene_replacement_approval_guard.py"
WORLD_PATH = "ros2_ws/src/ROBOT_URDF_final_description/launch/tugbot_depot.sdf"
CREATE_EXECUTABLE = Path("/opt/ros/jazzy/lib/ros_gz_sim/create")

LOCK_METADATA = "lease.json"


class TrustedContextError(ValueError):
    pass


@dataclass(frozen=True)
class ApprovalLease:
    approval_id: str
    context_digest: str
    lock_path: Path
    nonce: str


def canonical(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def context_digest(context: dict[str, Any]) -> str:
    return hashlib.sha256(canonical(context)).hexdigest()


def _regular_not_symlink(path: Path) -> bool:
    try:
        return stat.S_ISREG(path.stat(follow_symlinks=False).st_mode) and not path.is_symlink()
    except OSError:
        return False


def resolve_workspace_regular(workspace_root: Path, relative_path: str) -> Path:
    root = workspace_root.resolve(strict=True)
    relative = Path(relative_path)
    if relative.is_absolute() or ".." in relative.parts or not relative.parts:
        raise TrustedContextError("workspace path is not a locked relative path")
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise TrustedContextError("workspace path contains a symlink")
    try:
        resolved = current.resolve(strict=True)
    except OSError as exc:
        raise TrustedContextError(f"workspace file missing: {type(exc).__name__}") from exc
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise TrustedContextError("workspace path escapes root") from exc
    if not _regular_not_symlink(current):
        raise TrustedContextError("workspace path is not a regular file")
    return resolved


def resolve_direct_create_executable() -> Path:
    if CREATE_EXECUTABLE.is_symlink() or not _regular_not_symlink(CREATE_EXECUTABLE):
        raise TrustedContextError("direct create executable missing, symlinked, or not regular")
    return CREATE_EXECUTABLE


def build_trusted_context(workspace_root: Path) -> dict[str, Any]:
    """Build the only admissible context by hashing locked filesystem inputs."""
    root = workspace_root.resolve(strict=True)
    packet = resolve_workspace_regular(root, PACKET_PATH)
    supervisor = resolve_workspace_regular(root, SUPERVISOR_PATH)
    launch = resolve_workspace_regular(root, LAUNCH_PATH)
    helper = resolve_workspace_regular(root, HELPER_PATH)
    guard_helper = resolve_workspace_regular(root, GUARD_HELPER_PATH)
    world = resolve_workspace_regular(root, WORLD_PATH)
    create = resolve_direct_create_executable()
    return {
        "schema": SCHEMA,
        "approval_id": APPROVAL_ID,
        "packet_path": PACKET_PATH,
        "packet_sha256": sha(packet),
        "supervisor_path": SUPERVISOR_PATH,
        "supervisor_sha256": sha(supervisor),
        "launch_path": LAUNCH_PATH,
        "launch_sha256": sha(launch),
        "helper_path": HELPER_PATH,
        "helper_sha256": sha(helper),
        "guard_helper_path": GUARD_HELPER_PATH,
        "guard_helper_sha256": sha(guard_helper),
        "world_path": WORLD_PATH,
        "world_sha256": sha(world),
        "create_executable": str(create),
        "create_executable_sha256": sha(create),
        "literals": {
            "world": "world_demo",
            "entity": "ROBOT_URDF_final",
            "service": "/world/world_demo/scene/info",
            "request_type": "gz::msgs::Empty",
            "response_type": "gz::msgs::Scene",
            "link": "base_link",
            "sensor": "s3_d3_base_contact_sensor",
            "collision": "s3_d3_base_contact_collision",
            "ownership_mode": "SUPERVISOR_OWNED_CREATE_V1",
            "create_argv": ["-topic", "/robot_description", "-name", "ROBOT_URDF_final", "-allow_renaming", "false", "-x", "0", "-y", "0", "-z", "0.1", "-Y", "0"],
            "create_timeout_ms": 90000,
            "post_create_delay_ms": 2000,
            "create_shutdown_grace_ms": 5000,
            "helper_preflight_wait_ms": 90000,
            "helper_request_timeout_ms": 5000,
            "helper_polling_interval_ms": 10,
            "negative_taxonomy": "SCENE_*_NOT_OBSERVED_AFTER_DELAY",
            "request_count": 1,
            "retry": "FORBIDDEN",
            "shutdown": "SIGINT_ONLY",
        },
        "capacity": 1,
    }


def load(path: Path) -> tuple[bool, dict[str, Any] | None, str]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return False, None, f"malformed guard: {type(exc).__name__}"
    if not isinstance(value, dict):
        return False, None, "malformed guard: top-level object required"
    return True, value, "ready"


def validate(record: dict[str, Any], context: dict[str, Any], require_authorized: bool) -> tuple[bool, str]:
    required = (
        "schema", "approval_id", "packet_path", "packet_sha256",
        "supervisor_path", "supervisor_sha256", "launch_path", "launch_sha256",
        "helper_path", "helper_sha256", "guard_helper_path", "guard_helper_sha256",
        "world_path", "world_sha256", "create_executable", "create_executable_sha256",
        "literals", "capacity",
    )
    for key in required:
        if record.get(key) != context.get(key):
            return False, f"guard mismatch: {key}"
    if record.get("state") not in (AUTHORIZED, CONSUMED) or record.get("capacity") != 1:
        return False, "malformed guard state or capacity"
    if require_authorized and record.get("state") != AUTHORIZED:
        return False, "approval already consumed"
    return True, "ready"


def atomic_replace(path: Path, value: dict[str, Any], replace: Callable[[str, str], None] = os.replace) -> tuple[bool, str]:
    temporary = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    try:
        with temporary.open("xb") as handle:
            handle.write(canonical(value)); handle.flush(); os.fsync(handle.fileno())
        replace(str(temporary), str(path))
        return True, "ready"
    except OSError as exc:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        return False, f"atomic-write failure: {type(exc).__name__}"


def initialize(path: Path, workspace_root: Path, created_at_utc: str) -> tuple[bool, str]:
    try:
        context = build_trusted_context(workspace_root)
    except TrustedContextError as exc:
        return False, f"trusted-context failure: {exc}"
    record = dict(context)
    record.update({"state": AUTHORIZED, "created_at_utc": created_at_utc, "run_id": None, "consumed_at_utc": None, "final_status": None})
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(canonical(record)); handle.flush(); os.fsync(handle.fileno())
        return True, "ready"
    except FileExistsError:
        ok, old, reason = load(path)
        return validate(old, context, False) if ok and old is not None else (False, reason)
    except OSError as exc:
        return False, f"atomic-write failure: {type(exc).__name__}"


def _lease_metadata(lease: ApprovalLease) -> dict[str, str]:
    return {"approval_id": lease.approval_id, "context_digest": lease.context_digest, "nonce": lease.nonce}


def _write_lease_metadata(lock: Path, lease: ApprovalLease) -> tuple[bool, str]:
    metadata = lock / LOCK_METADATA
    try:
        with metadata.open("xb") as handle:
            handle.write(canonical(_lease_metadata(lease))); handle.flush(); os.fsync(handle.fileno())
        return True, "ready"
    except OSError as exc:
        return False, f"lock metadata failure: {type(exc).__name__}"


def acquire_trusted(path: Path, workspace_root: Path) -> tuple[bool, str, ApprovalLease | None]:
    try:
        context = build_trusted_context(workspace_root)
    except TrustedContextError as exc:
        return False, f"trusted-context failure: {exc}", None
    ok, record, reason = load(path)
    if not ok or record is None:
        return False, reason, None
    ok, reason = validate(record, context, True)
    if not ok:
        return False, reason, None
    lock = path.with_name(path.name + ".lock")
    try:
        lock.mkdir()
    except OSError as exc:
        return False, f"lock failure: {type(exc).__name__}", None
    lease = ApprovalLease(APPROVAL_ID, context_digest(context), lock, secrets.token_urlsafe(32))
    ok, reason = _write_lease_metadata(lock, lease)
    if not ok:
        return False, reason, None
    ok, record, reason = load(path)
    if not ok or record is None:
        return False, reason, None
    ok, reason = validate(record, context, True)
    if not ok:
        return False, reason, None
    return True, "ready", lease


def consume_trusted(path: Path, lease: ApprovalLease, workspace_root: Path, run_id: str, final_status: str, when_utc: str) -> tuple[bool, str]:
    if not run_id or not final_status or not when_utc or lease.approval_id != APPROVAL_ID:
        return False, "consumption precondition failed"
    expected_lock = path.with_name(path.name + ".lock")
    if lease.lock_path != expected_lock or not expected_lock.is_dir():
        return False, "lease lock unavailable"
    try:
        context = build_trusted_context(workspace_root)
    except TrustedContextError as exc:
        return False, f"trusted-context failure: {exc}"
    if not hmac.compare_digest(lease.context_digest, context_digest(context)):
        return False, "lease context mismatch"
    metadata = expected_lock / LOCK_METADATA
    ok, stored, reason = load(metadata)
    if not ok or stored is None:
        return False, f"lease metadata invalid: {reason}"
    expected = _lease_metadata(lease)
    if any(not hmac.compare_digest(str(stored.get(key, "")), value) for key, value in expected.items()):
        return False, "lease metadata mismatch"
    ok, record, reason = load(path)
    if not ok or record is None:
        return False, reason
    ok, reason = validate(record, context, True)
    if not ok:
        return False, reason
    record.update({"state": CONSUMED, "run_id": run_id, "final_status": final_status, "consumed_at_utc": when_utc})
    ok, reason = atomic_replace(path, record)
    if not ok:
        return False, reason
    try:
        metadata.unlink(); expected_lock.rmdir()
    except OSError:
        return False, "consumed guard cleanup incomplete"
    return True, "ready"


def offline_self_test() -> tuple[bool, dict[str, bool]]:
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        for relative, content in ((PACKET_PATH, b"packet"), (SUPERVISOR_PATH, b"supervisor"), (LAUNCH_PATH, b"launch"), (HELPER_PATH, b"helper"), (GUARD_HELPER_PATH, b"guard helper"), (WORLD_PATH, b"world")):
            target = root / relative; target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(content)
        guard = root / "guard.json"
        results: dict[str, bool] = {"canonical_deterministic": canonical({"b": 1, "a": 2}) == canonical({"a": 2, "b": 1})}
        results["initialize"] = initialize(guard, root, "2026-09-27T00:00:00Z")[0]
        ok, _, lease = acquire_trusted(guard, root); results["acquire_once"] = ok and lease is not None
        results["second_acquire_rejected"] = not acquire_trusted(guard, root)[0]
        results["consume"] = bool(lease and consume_trusted(guard, lease, root, "run", "INVALID", "2026-09-27T00:00:01Z")[0])
        results["consumed_rejected"] = not acquire_trusted(guard, root)[0]
        return all(results.values()), results


if __name__ == "__main__":
    ok, results = offline_self_test()
    print(json.dumps({"passed": ok, "results": results}, sort_keys=True))
    raise SystemExit(0 if ok else 1)
