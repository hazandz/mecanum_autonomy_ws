#!/usr/bin/env python3
"""Generic typed-Scene approval guard; no runtime APIs or default authority."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import stat
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

PENDING = "pending_user_approval"
AUTHORIZED = "authorized_not_consumed"
CONSUMED = "consumed"
SUPPORTED_SCHEMA = "s3_d3_typed_scene_runtime_guard/v1"
LOCK_METADATA = "lease.json"
SUPERVISOR_PATH = "artifacts/simulation/contact_producer_evidence/tools/run_typed_scene_observer.py"
SOURCE_LAUNCH_PATH = "ros2_ws/src/ROBOT_URDF_final_description/launch/native_sdf_contact_diagnostic.launch.py"
INSTALLED_LAUNCH_PATH = "ros2_ws/install/ROBOT_URDF_final_description/share/ROBOT_URDF_final_description/launch/native_sdf_contact_diagnostic.launch.py"
SOURCE_NATIVE_MODEL_PATH = "ros2_ws/src/ROBOT_URDF_final_description/models/ROBOT_URDF_final/model.sdf"
INSTALLED_NATIVE_MODEL_PATH = "ros2_ws/install/ROBOT_URDF_final_description/share/ROBOT_URDF_final_description/models/ROBOT_URDF_final/model.sdf"
HELPER_PATH = "artifacts/simulation/contact_producer_evidence/tools/typed_scene_observer.cpp"
WORLD_PATH = "ros2_ws/src/ROBOT_URDF_final_description/launch/tugbot_depot.sdf"
CREATE_EXECUTABLE = Path("/opt/ros/jazzy/lib/ros_gz_sim/create")
GUARD_DIRECTORY = "artifacts/simulation/contact_producer_evidence/approval_guards"
PKG_CONFIG_DIRECTORIES = (
    "/opt/ros/jazzy/opt/gz_transport_vendor/lib/pkgconfig",
    "/opt/ros/jazzy/opt/gz_msgs_vendor/lib/pkgconfig",
    "/opt/ros/jazzy/opt/gz_cmake_vendor/lib/pkgconfig",
    "/opt/ros/jazzy/opt/gz_utils_vendor/lib/pkgconfig",
    "/opt/ros/jazzy/opt/gz_math_vendor/lib/pkgconfig",
)
PKG_CONFIG_RUNTIME_VERSIONS = {"gz-transport13": "13.5.0", "gz-msgs10": "10.3.2"}
PKG_CONFIG_FILES = (
    ("gz-transport13.pc", "13.5.0"), ("gz-msgs10.pc", "10.3.2"),
    ("gz-cmake3.pc", "3.5.6"), ("gz-utils2.pc", "2.2.1"),
    ("gz-math7.pc", "7.6.0"),
)


class TrustedContextError(ValueError):
    pass


@dataclass(frozen=True)
class TypedSceneApprovalSpec:
    """Explicit, immutable authority identity; no approval default exists."""

    approval_id: str
    schema: str
    packet_path: str
    guard_path: str


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


def _directory_not_symlink(path: Path) -> bool:
    try:
        return stat.S_ISDIR(path.stat(follow_symlinks=False).st_mode) and not path.is_symlink()
    except OSError:
        return False


def _locked_relative(value: str) -> Path:
    if not isinstance(value, str) or not value or "\\" in value:
        raise TrustedContextError("workspace path is not canonical relative text")
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts or not relative.parts:
        raise TrustedContextError("workspace path is not a locked relative path")
    return relative


def _resolve_relative(root: Path, value: str, require_regular: bool) -> Path:
    relative = _locked_relative(value)
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise TrustedContextError("workspace path contains a symlink")
    try:
        resolved = current.resolve(strict=require_regular)
        resolved.relative_to(root)
    except (OSError, ValueError) as exc:
        raise TrustedContextError("workspace file missing or escapes root") from exc
    if require_regular and not _regular_not_symlink(current):
        raise TrustedContextError("workspace path is not a regular file")
    return resolved


def resolve_workspace_regular(workspace_root: Path, relative_path: str) -> Path:
    return _resolve_relative(workspace_root.resolve(strict=True), relative_path, True)


def validate_spec(spec: TypedSceneApprovalSpec, workspace_root: Path,
                  require_packet: bool = True, require_guard: bool = False) -> tuple[Path | None, Path]:
    root = workspace_root.resolve(strict=True)
    if not isinstance(spec, TypedSceneApprovalSpec):
        raise TrustedContextError("approval spec type invalid")
    if spec.schema != SUPPORTED_SCHEMA:
        raise TrustedContextError("approval spec schema unsupported")
    if not isinstance(spec.approval_id, str) or not re.fullmatch(r"[A-Za-z0-9._-]{8,160}", spec.approval_id):
        raise TrustedContextError("approval ID invalid")
    packet_relative = _locked_relative(spec.packet_path)
    guard_relative = _locked_relative(spec.guard_path)
    if packet_relative.parts[0] != "docs":
        raise TrustedContextError("packet path must remain under docs")
    if guard_relative.parent.as_posix() != GUARD_DIRECTORY or guard_relative.name != spec.approval_id + ".json":
        raise TrustedContextError("guard path does not match approval spec")
    packet = _resolve_relative(root, spec.packet_path, require_packet)
    guard = _resolve_relative(root, spec.guard_path, require_guard)
    return (packet if require_packet else None), guard


def spec_from_cli(approval_id: str, packet_path: str, guard_path: str) -> TypedSceneApprovalSpec:
    return TypedSceneApprovalSpec(approval_id, SUPPORTED_SCHEMA, packet_path, guard_path)


def resolve_direct_create_executable() -> Path:
    if not _regular_not_symlink(CREATE_EXECUTABLE):
        raise TrustedContextError("direct create executable missing, symlinked, or not regular")
    return CREATE_EXECUTABLE


def native_create_argv(workspace_root: Path) -> list[str]:
    """Return the sole approved direct native-SDF create argv for this root."""
    model = resolve_workspace_regular(workspace_root, INSTALLED_NATIVE_MODEL_PATH)
    return [
        "-world", "world_demo", "-file", str(model),
        "-name", "ROBOT_URDF_final", "-allow_renaming", "false",
        "-x", "0", "-y", "0", "-z", "0.1", "-Y", "0",
    ]


def runtime_guard_module_identity(workspace_root: Path) -> tuple[str, Path]:
    root = workspace_root.resolve(strict=True)
    candidate = Path(__file__)
    if candidate.is_symlink() or not _regular_not_symlink(candidate):
        raise TrustedContextError("runtime guard module missing, symlinked, or not regular")
    try:
        resolved = candidate.resolve(strict=True)
        relative = resolved.relative_to(root).as_posix()
    except (OSError, ValueError) as exc:
        raise TrustedContextError("runtime guard module escapes workspace") from exc
    verified = resolve_workspace_regular(root, relative)
    if verified != resolved:
        raise TrustedContextError("runtime guard module canonical path mismatch")
    return relative, resolved


def pkg_config_identity() -> tuple[tuple[str, ...], dict[str, str]]:
    files = tuple(Path(directory) / filename for directory, (filename, _) in zip(PKG_CONFIG_DIRECTORIES, PKG_CONFIG_FILES, strict=True))
    if any(not _directory_not_symlink(Path(directory)) for directory in PKG_CONFIG_DIRECTORIES):
        raise TrustedContextError("pkg-config directory missing or symlinked")
    if any(not _regular_not_symlink(file) for file in files):
        raise TrustedContextError("pkg-config metadata missing or symlinked")
    versions: dict[str, str] = {}
    for file, (_, expected) in zip(files, PKG_CONFIG_FILES, strict=True):
        actual = next((line.partition(":")[2].strip() for line in file.read_text(encoding="utf-8").splitlines() if line.startswith("Version:")), None)
        if actual != expected:
            raise TrustedContextError("pkg-config metadata version mismatch")
        versions[file.stem] = actual
    return PKG_CONFIG_DIRECTORIES, versions


def build_trusted_context(workspace_root: Path, spec: TypedSceneApprovalSpec) -> dict[str, Any]:
    root = workspace_root.resolve(strict=True)
    packet, _ = validate_spec(spec, root, True, False)
    assert packet is not None
    runtime_guard_module_path, runtime_guard_module = runtime_guard_module_identity(root)
    directories, versions = pkg_config_identity()
    supervisor = resolve_workspace_regular(root, SUPERVISOR_PATH)
    source_launch = resolve_workspace_regular(root, SOURCE_LAUNCH_PATH)
    installed_launch = resolve_workspace_regular(root, INSTALLED_LAUNCH_PATH)
    source_model = resolve_workspace_regular(root, SOURCE_NATIVE_MODEL_PATH)
    installed_model = resolve_workspace_regular(root, INSTALLED_NATIVE_MODEL_PATH)
    helper = resolve_workspace_regular(root, HELPER_PATH)
    world = resolve_workspace_regular(root, WORLD_PATH)
    create = resolve_direct_create_executable()
    create_argv = native_create_argv(root)
    return {
        "schema": spec.schema,
        "approval_id": spec.approval_id,
        "packet_path": spec.packet_path,
        "guard_path": spec.guard_path,
        "packet_sha256": sha(packet),
        "supervisor_path": SUPERVISOR_PATH, "supervisor_sha256": sha(supervisor),
        "runtime_guard_module_path": runtime_guard_module_path,
        "runtime_guard_module_sha256": sha(runtime_guard_module),
        "helper_path": HELPER_PATH, "helper_sha256": sha(helper),
        "source_launch_path": SOURCE_LAUNCH_PATH, "source_launch_sha256": sha(source_launch),
        "installed_launch_path": INSTALLED_LAUNCH_PATH, "installed_launch_sha256": sha(installed_launch),
        "source_native_model_path": SOURCE_NATIVE_MODEL_PATH, "source_native_model_sha256": sha(source_model),
        "installed_native_model_path": INSTALLED_NATIVE_MODEL_PATH, "installed_native_model_sha256": sha(installed_model),
        "world_path": WORLD_PATH, "world_sha256": sha(world),
        "create_executable": str(create), "create_executable_sha256": sha(create),
        "pkg_config_directories": list(directories), "pkg_config_versions": versions,
        "literals": {
            "world": "world_demo", "entity": "ROBOT_URDF_final", "service": "/world/world_demo/scene/info",
            "request_type": "gz::msgs::Empty", "response_type": "gz::msgs::Scene",
            "link": "base_link", "sensor": "s3_d3_base_contact_sensor", "collision": "s3_d3_base_contact_collision",
            "ownership_mode": "SUPERVISOR_OWNED_CREATE_V1",
            "create_argv": create_argv,
            "create_timeout_ms": 90000, "post_create_delay_ms": 2000, "create_shutdown_grace_ms": 5000,
            "helper_preflight_wait_ms": 90000, "helper_request_timeout_ms": 5000, "helper_polling_interval_ms": 10,
            "negative_taxonomy": "SCENE_*_NOT_OBSERVED_AFTER_DELAY", "request_count": 1,
            "retry": "FORBIDDEN", "shutdown": "SUPERVISOR_SIGINT_ONLY_LAUNCHER_ESCALATION_POSSIBLE",
        },
        "capacity": 1,
    }


def load(path: Path) -> tuple[bool, dict[str, Any] | None, str]:
    try:
        if not _regular_not_symlink(path):
            return False, None, "guard file missing, non-regular, or symlinked"
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return False, None, f"malformed guard: {type(exc).__name__}"
    return (True, value, "ready") if isinstance(value, dict) else (False, None, "malformed guard: top-level object required")


def validate(record: dict[str, Any], context: dict[str, Any], spec: TypedSceneApprovalSpec,
             require_authorized: bool) -> tuple[bool, str]:
    if record.get("approval_id") != spec.approval_id or record.get("schema") != spec.schema:
        return False, "guard approval spec mismatch"
    if record.get("packet_path") != spec.packet_path or record.get("guard_path") != spec.guard_path:
        return False, "guard approval path mismatch"
    for key in context:
        if record.get(key) != context[key]:
            return False, f"guard mismatch: {key}"
    if record.get("state") not in (PENDING, AUTHORIZED, CONSUMED) or record.get("capacity") != 1:
        return False, "malformed guard state or capacity"
    if require_authorized and record.get("state") != AUTHORIZED:
        return False, "guard not authorized"
    return True, "ready"


def atomic_replace(path: Path, value: dict[str, Any], replace: Callable[[str, str], None] = os.replace) -> tuple[bool, str]:
    temporary = path.with_name(f".{path.name}.tmp.{os.getpid()}.{secrets.token_hex(8)}")
    try:
        with temporary.open("xb") as handle:
            handle.write(canonical(value)); handle.flush(); os.fsync(handle.fileno())
        replace(str(temporary), str(path))
        return True, "ready"
    except OSError as exc:
        try: temporary.unlink(missing_ok=True)
        except OSError: pass
        return False, f"atomic-write failure: {type(exc).__name__}"


def initialize(spec: TypedSceneApprovalSpec, workspace_root: Path, created_at_utc: str) -> tuple[bool, str]:
    try:
        context = build_trusted_context(workspace_root, spec)
        _, path = validate_spec(spec, workspace_root, True, False)
    except TrustedContextError as exc:
        return False, f"trusted-context failure: {exc}"
    record = dict(context)
    record.update({"state": PENDING, "created_at_utc": created_at_utc, "run_id": None, "consumed_at_utc": None, "final_status": None})
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.parent.is_symlink(): raise OSError("guard parent symlink")
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(canonical(record)); handle.flush(); os.fsync(handle.fileno())
        return True, "ready"
    except OSError as exc:
        return False, f"atomic-write failure: {type(exc).__name__}"


def _lease_metadata(lease: ApprovalLease, spec: TypedSceneApprovalSpec) -> dict[str, str]:
    return {"approval_id": spec.approval_id, "guard_path": spec.guard_path,
            "context_digest": lease.context_digest, "nonce": lease.nonce}


def acquire_trusted(spec: TypedSceneApprovalSpec, workspace_root: Path) -> tuple[bool, str, ApprovalLease | None]:
    try:
        context = build_trusted_context(workspace_root, spec)
        _, path = validate_spec(spec, workspace_root, True, True)
    except TrustedContextError as exc:
        return False, f"trusted-context failure: {exc}", None
    ok, record, reason = load(path)
    if not ok or record is None: return False, reason, None
    ok, reason = validate(record, context, spec, True)
    if not ok: return False, reason, None
    lock = path.with_name(path.name + ".lock")
    try:
        lock.mkdir()
        lease = ApprovalLease(spec.approval_id, context_digest(context), lock, secrets.token_urlsafe(32))
        with (lock / LOCK_METADATA).open("xb") as handle:
            handle.write(canonical(_lease_metadata(lease, spec))); handle.flush(); os.fsync(handle.fileno())
    except OSError as exc:
        return False, f"lock failure: {type(exc).__name__}", None
    return True, "ready", lease


def consume_trusted(spec: TypedSceneApprovalSpec, lease: ApprovalLease, workspace_root: Path,
                    run_id: str, final_status: str, when_utc: str) -> tuple[bool, str]:
    if not run_id or not final_status or not when_utc or lease.approval_id != spec.approval_id:
        return False, "consumption precondition failed"
    try:
        context = build_trusted_context(workspace_root, spec)
        _, path = validate_spec(spec, workspace_root, True, True)
    except TrustedContextError as exc:
        return False, f"trusted-context failure: {exc}"
    expected_lock = path.with_name(path.name + ".lock")
    if lease.lock_path != expected_lock or not expected_lock.is_dir(): return False, "lease lock unavailable"
    if not hmac.compare_digest(lease.context_digest, context_digest(context)): return False, "lease context mismatch"
    ok, stored, reason = load(expected_lock / LOCK_METADATA)
    if not ok or stored is None or stored != _lease_metadata(lease, spec): return False, "lease metadata mismatch"
    ok, record, reason = load(path)
    if not ok or record is None: return False, reason
    ok, reason = validate(record, context, spec, True)
    if not ok: return False, reason
    record.update({"state": CONSUMED, "run_id": run_id, "final_status": final_status, "consumed_at_utc": when_utc})
    ok, reason = atomic_replace(path, record)
    if not ok: return False, reason
    try:
        (expected_lock / LOCK_METADATA).unlink(); expected_lock.rmdir()
    except OSError:
        return False, "consumed guard cleanup incomplete"
    return True, "ready"
