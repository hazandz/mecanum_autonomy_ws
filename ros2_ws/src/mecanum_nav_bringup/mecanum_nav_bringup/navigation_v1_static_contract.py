"""Pure-Python fail-closed checks for Navigation V1 static inputs.

This module validates caller-supplied mappings. It performs no file, ROS, TF,
package-manager, or runtime I/O and never resolves a profile or config hash.
"""

from collections.abc import Mapping
import re


class StaticContractError(ValueError):
    """Raised when a static Navigation V1 input is incomplete or inconsistent."""


DEPENDENCY_LOCK_SCHEMA = "mecanum_navigation_v1_dependency_lock/v1"
EXPECTED_DIRECT_DEPENDENCY_ROOTS = (
    "nav2_bringup",
    "nav2_amcl",
    "nav2_map_server",
    "nav2_lifecycle_manager",
    "nav2_planner",
    "nav2_controller",
    "nav2_bt_navigator",
    "nav2_costmap_2d",
    "robot_localization",
    "tf2_ros",
    "robot_state_publisher",
    "sensor_msgs",
    "nav_msgs",
    "geometry_msgs",
)

REQUIRED_WORKSPACE_SOURCE_ROLES = (
    "nav2_lifecycle_bringup",
    "map_server",
    "amcl_omni",
    "robot_localization_ekf",
    "robot_state_publisher",
    "tf_ownership",
    "scan_adapter",
    "map_artifact_binding",
    "remap_namespace_policy",
    "lifecycle_startup_policy",
)

EXPECTED_STARTUP_ORDER = (
    "robot_description",
    "drivers_bridge",
    "EKF",
    "Map_Server",
    "AMCL",
    "healthy_LocalizationMonitor",
    "Planner_global_costmap",
    "Safety",
    "selected_controller_or_manager",
    "mission_acceptance",
)

TF_EDGE_OWNERS = {
    "map -> odom": "AMCL",
    "odom -> base_link": "robot_localization",
    "base_link -> lidar_frame": "robot_state_publisher",
}

SCAN_BINDING = {
    "topic": "/scan",
    "type": "sensor_msgs/msg/LaserScan",
    "header_frame_id": "lidar_frame",
}

_EXTERNAL_LOCK_FIELDS = (
    "ros_distribution",
    "ubuntu_release",
    "ros_package_name",
    "debian_package_name",
    "installed_version",
    "architecture",
    "apt_repository_origin",
    "deb_sha256",
    "dependency_closure_sha256",
    "evidence_capture_method",
)
_HEX_40 = re.compile(r"^[0-9a-f]{40}$")
_HEX_64 = re.compile(r"^[0-9a-f]{64}$")
_PENDING = re.compile(r"\bPENDING_[A-Z0-9_]+\b")


def reject_pending_markers(*texts: str) -> None:
    """Reject static template text containing any unresolved pending token."""
    for index, text in enumerate(texts):
        if not isinstance(text, str):
            raise StaticContractError(f"template text {index} is not a string")
        match = _PENDING.search(text)
        if match:
            raise StaticContractError(
                f"unresolved marker {match.group(0)} in template text {index}"
            )


def _reject_pending_values(value: object, path: str = "input") -> None:
    if isinstance(value, str) and _PENDING.search(value):
        raise StaticContractError(f"unresolved marker at {path}")
    if isinstance(value, Mapping):
        for key, child in value.items():
            _reject_pending_values(child, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _reject_pending_values(child, f"{path}[{index}]")


def _require_mapping(value: object, label: str) -> Mapping:
    if not isinstance(value, Mapping):
        raise StaticContractError(f"{label} must be a mapping")
    return value


def _require_exact_keys(value: Mapping, expected: set, label: str) -> None:
    if set(value) != expected:
        raise StaticContractError(f"{label} fields are incomplete or unexpected")


def _require_nonempty_string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise StaticContractError(f"{label} must be a non-empty string")
    return value


def _require_digest(value: object, label: str) -> str:
    digest = _require_nonempty_string(value, label)
    if not _HEX_64.fullmatch(digest):
        raise StaticContractError(f"{label} must be a lowercase SHA-256 digest")
    return digest


def _validate_external_package_locks(value: object) -> None:
    if not isinstance(value, list):
        raise StaticContractError("external_package_locks must be a complete list")
    names = []
    for index, raw_entry in enumerate(value):
        entry = _require_mapping(raw_entry, f"external_package_locks[{index}]")
        _require_exact_keys(entry, set(_EXTERNAL_LOCK_FIELDS), f"external lock {index}")
        for field in _EXTERNAL_LOCK_FIELDS:
            _require_nonempty_string(entry.get(field), f"external lock {index}.{field}")
        names.append(entry["ros_package_name"])
        _require_digest(entry["deb_sha256"], f"external lock {index}.deb_sha256")
        _require_digest(
            entry["dependency_closure_sha256"],
            f"external lock {index}.dependency_closure_sha256",
        )
    if len(names) != len(set(names)):
        raise StaticContractError("external package locks contain duplicate roots")
    if set(names) != set(EXPECTED_DIRECT_DEPENDENCY_ROOTS):
        raise StaticContractError("external package lock roots are incomplete or unexpected")


def _validate_workspace_source_locks(value: object) -> None:
    if not isinstance(value, list):
        raise StaticContractError("workspace_source_locks must be a complete list")
    roles = []
    for index, raw_entry in enumerate(value):
        entry = _require_mapping(raw_entry, f"workspace_source_locks[{index}]")
        _require_exact_keys(
            entry,
            {
                "repository_commit",
                "repository_relative_path",
                "source_file_sha256",
                "owner_package",
                "role",
                "status",
            },
            f"workspace source {index}",
        )
        commit = _require_nonempty_string(
            entry.get("repository_commit"), f"workspace source {index}.repository_commit"
        )
        if not _HEX_40.fullmatch(commit):
            raise StaticContractError("workspace source commit must be a full lowercase SHA")
        path = _require_nonempty_string(
            entry.get("repository_relative_path"),
            f"workspace source {index}.repository_relative_path",
        )
        if path.startswith("/") or ".." in path.split("/"):
            raise StaticContractError("workspace source path must stay repository-relative")
        _require_digest(
            entry.get("source_file_sha256"), f"workspace source {index}.source_file_sha256"
        )
        _require_nonempty_string(entry.get("owner_package"), f"workspace source {index}.owner_package")
        role = _require_nonempty_string(entry.get("role"), f"workspace source {index}.role")
        _require_nonempty_string(entry.get("status"), f"workspace source {index}.status")
        roles.append(role)
    if len(roles) != len(set(roles)):
        raise StaticContractError("workspace source roles contain duplicates")
    if set(roles) != set(REQUIRED_WORKSPACE_SOURCE_ROLES):
        raise StaticContractError("workspace source pins are incomplete or unexpected")


def _validate_map_binding(
    map_server: Mapping, expected_map_id: object, expected_map_content_hash: object
) -> None:
    _reject_pending_values(expected_map_id, "expected_map_id")
    _reject_pending_values(expected_map_content_hash, "expected_map_content_hash")
    map_id = _require_nonempty_string(expected_map_id, "expected_map_id")
    expected_hash = _require_digest(expected_map_content_hash, "expected_map_content_hash")
    if "/" in map_id or map_id in (".", ".."):
        raise StaticContractError("map_id must be a single artifact-root path component")
    if map_server.get("map_id") != map_id:
        raise StaticContractError("map_id is missing or does not match the expected identity")
    if map_server.get("map_content_hash") != expected_hash:
        raise StaticContractError("map_content_hash is missing or does not match the expected identity")
    _require_exact_keys(
        map_server,
        {"map_id", "artifact_identity", "map_content_hash", "artifact_root"},
        "map_server",
    )
    _require_nonempty_string(map_server.get("artifact_identity"), "map_server.artifact_identity")
    expected_root = f"artifacts/maps/{map_id}/"
    if map_server.get("artifact_root") != expected_root:
        raise StaticContractError("map path must be exactly under artifacts/maps/<map_id>/")


def validate_navigation_v1_runtime_inputs(
    source_lock: object,
    bringup: object,
    *,
    expected_map_id: object,
    expected_map_content_hash: object,
) -> None:
    """Validate a fully pinned input set without creating a profile or hash.

    The function returns no resolved object. Expected map identity must be
    injected by a separately authorized caller; this module has no map default.
    """
    lock = _require_mapping(source_lock, "source_lock")
    config = _require_mapping(bringup, "bringup")
    _reject_pending_values(lock, "source_lock")
    _reject_pending_values(config, "bringup")

    if lock.get("schema") != DEPENDENCY_LOCK_SCHEMA:
        raise StaticContractError("source lock schema is missing or unsupported")
    _require_exact_keys(
        lock,
        {"schema", "direct_dependency_roots", "external_package_locks", "workspace_source_locks"},
        "source_lock",
    )
    roots = lock.get("direct_dependency_roots")
    if not isinstance(roots, list) or tuple(roots) != EXPECTED_DIRECT_DEPENDENCY_ROOTS:
        raise StaticContractError("direct dependency roots do not match the active lock schema")
    _validate_external_package_locks(lock.get("external_package_locks"))
    _validate_workspace_source_locks(lock.get("workspace_source_locks"))

    map_server = _require_mapping(config.get("map_server"), "map_server")
    _validate_map_binding(map_server, expected_map_id, expected_map_content_hash)

    tf_owners = _require_mapping(config.get("tf_owners"), "tf_owners")
    _require_exact_keys(tf_owners, set(TF_EDGE_OWNERS), "tf_owners")
    for edge, expected_owner in TF_EDGE_OWNERS.items():
        if tf_owners.get(edge) != expected_owner:
            raise StaticContractError(f"TF owner mismatch for {edge}")

    scan = _require_mapping(config.get("scan"), "scan")
    _require_exact_keys(scan, set(SCAN_BINDING), "scan")
    for field, expected in SCAN_BINDING.items():
        if scan.get(field) != expected:
            raise StaticContractError(f"scan {field} must exactly match the target binding")
    lifecycle = _require_mapping(config.get("lifecycle"), "lifecycle")
    _require_exact_keys(lifecycle, {"health_gated", "startup_order"}, "lifecycle")
    if lifecycle.get("health_gated") is not True:
        raise StaticContractError("lifecycle startup must be health-gated")
    if not isinstance(lifecycle.get("startup_order"), list) or tuple(
        lifecycle["startup_order"]
    ) != EXPECTED_STARTUP_ORDER:
        raise StaticContractError("lifecycle startup order does not match Architecture §49")

    _require_exact_keys(
        config,
        {"map_server", "tf_owners", "scan", "lifecycle"},
        "bringup",
    )
