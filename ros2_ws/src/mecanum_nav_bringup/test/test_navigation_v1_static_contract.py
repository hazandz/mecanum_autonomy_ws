from copy import deepcopy
from pathlib import Path

import pytest

from mecanum_nav_bringup.navigation_v1_static_contract import (
    EXPECTED_DIRECT_DEPENDENCY_ROOTS,
    REQUIRED_WORKSPACE_SOURCE_ROLES,
    StaticContractError,
    validate_navigation_v1_runtime_inputs,
)


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
TEST_MAP_ID = "fixture_map"
TEST_MAP_HASH = "a" * 64


def _valid_source_lock():
    return {
        "schema": "mecanum_navigation_v1_dependency_lock/v2",
        "direct_dependency_roots": list(EXPECTED_DIRECT_DEPENDENCY_ROOTS),
        "external_package_locks": [
            {
                "ros_distribution": "fixture",
                "ubuntu_release": "fixture",
                "ros_package_name": package,
                "debian_package_name": f"fixture-{package}",
                "installed_version": "fixture-version",
                "architecture": "fixture-architecture",
                "apt_repository_origin": "fixture-origin",
                "deb_sha256": "b" * 64,
                "dependency_closure_sha256": "c" * 64,
                "evidence_capture_method": "test-fixture-only",
            }
            for package in EXPECTED_DIRECT_DEPENDENCY_ROOTS
        ],
        "artifact_baseline_provenance": {
            "baseline_identity": {
                "base_image_digest": "ubuntu@sha256:" + "e" * 64,
                "platform": "linux/amd64",
                "source_repository": "https://example.invalid/repo.git",
                "source_commit": "1" * 40,
                "purpose": "synthetic-test-only",
            },
            "artifact_closure": {
                "artifact_locator": "synthetic-test-only",
                "closure_manifest_relative_path": "metadata/closure.sha256",
                "closure_manifest_sha256": "2" * 64,
                "closure_artifact_count": 1,
                "closure_total_bytes": 1,
            },
            "ros_signing_key": {
                "keyring_relative_path": "apt_sources/keyring.gpg",
                "keyring_sha256": "3" * 64,
                "primary_fingerprint": "A" * 40,
                "fingerprint_record_sha256": "4" * 64,
            },
            "correction_report_sha256": "5" * 64,
            "quarantined_non_closure_artifacts": {
                "manifest_relative_path": "metadata/quarantine.sha256",
                "manifest_sha256": "6" * 64,
                "artifact_count": 0,
                "classification": "QUARANTINED_NON_CLOSURE_ARTIFACT_NOT_PART_OF_NAVIGATION_V1_LOCK",
            },
        },
        "workspace_source_locks": [
            {
                "repository_commit": "1" * 40,
                "repository_relative_path": f"fixture/{role}.py",
                "source_file_sha256": "d" * 64,
                "owner_package": "mecanum_nav_bringup",
                "role": role,
                "status": "FIXTURE_PIN",
            }
            for role in REQUIRED_WORKSPACE_SOURCE_ROLES
        ],
    }


def _valid_bringup():
    return {
        "map_server": {
            "map_id": TEST_MAP_ID,
            "artifact_identity": "fixture-only",
            "map_content_hash": TEST_MAP_HASH,
            "artifact_root": f"artifacts/maps/{TEST_MAP_ID}/",
        },
        "tf_owners": {
            "map -> odom": "AMCL",
            "odom -> base_link": "robot_localization",
            "base_link -> lidar_frame": "robot_state_publisher",
        },
        "scan": {
            "topic": "/scan",
            "type": "sensor_msgs/msg/LaserScan",
            "header_frame_id": "lidar_frame",
        },
        "lifecycle": {
            "health_gated": True,
            "startup_order": [
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
            ],
        },
    }


def _validate(source_lock=None, bringup=None, *, map_id=TEST_MAP_ID, map_hash=TEST_MAP_HASH):
    return validate_navigation_v1_runtime_inputs(
        _valid_source_lock() if source_lock is None else source_lock,
        _valid_bringup() if bringup is None else bringup,
        expected_map_id=map_id,
        expected_map_content_hash=map_hash,
    )


def test_valid_complete_injected_fixture_is_accepted_without_resolved_output():
    assert _validate() is None


def test_missing_artifact_baseline_provenance_is_rejected():
    lock = _valid_source_lock()
    del lock["artifact_baseline_provenance"]
    with pytest.raises(StaticContractError, match="fields are incomplete or unexpected"):
        _validate(source_lock=lock)


def test_checked_in_templates_are_rejected_as_unresolved_runtime_inputs():
    source_text = (PACKAGE_ROOT / "config/navigation_v1_source_lock.template.yaml").read_text()
    bringup_text = (PACKAGE_ROOT / "config/navigation_v1_static_bringup.template.yaml").read_text()
    from mecanum_nav_bringup.navigation_v1_static_contract import reject_pending_markers

    with pytest.raises(StaticContractError, match="unresolved marker"):
        reject_pending_markers(source_text, bringup_text)


def test_missing_external_package_lock_is_rejected():
    lock = _valid_source_lock()
    lock["external_package_locks"].pop()
    with pytest.raises(StaticContractError, match="roots are incomplete"):
        _validate(source_lock=lock)


def test_missing_workspace_source_pin_is_rejected():
    lock = _valid_source_lock()
    lock["workspace_source_locks"].pop()
    with pytest.raises(StaticContractError, match="source pins are incomplete"):
        _validate(source_lock=lock)


@pytest.mark.parametrize(
    "map_id,map_hash",
    [(None, TEST_MAP_HASH), (TEST_MAP_ID, None), ("other_map", TEST_MAP_HASH), (TEST_MAP_ID, "e" * 64)],
)
def test_missing_or_mismatched_map_identity_and_hash_are_rejected(map_id, map_hash):
    with pytest.raises(StaticContractError, match="map_id|map_content_hash|expected_map"):
        _validate(map_id=map_id, map_hash=map_hash)


def test_package_local_or_legacy_map_path_is_rejected():
    config = _valid_bringup()
    config["map_server"]["artifact_root"] = "ros2_ws/src/package/maps/fixture_map/"
    with pytest.raises(StaticContractError, match="map path"):
        _validate(bringup=config)


@pytest.mark.parametrize(
    "edge,wrong_owner",
    [
        ("map -> odom", "slam_toolbox"),
        ("odom -> base_link", "mecanum_base_bridge"),
        ("base_link -> lidar_frame", "static_transform_publisher"),
    ],
)
def test_each_tf_edge_rejects_wrong_owner(edge, wrong_owner):
    config = _valid_bringup()
    config["tf_owners"][edge] = wrong_owner
    with pytest.raises(StaticContractError, match="TF owner mismatch"):
        _validate(bringup=config)


@pytest.mark.parametrize("frame", ["base_scan", "RPLiDAR_A1M8_1", "lidar_link", "other_frame"])
def test_scan_alias_or_noncanonical_frame_is_rejected(frame):
    config = _valid_bringup()
    config["scan"]["header_frame_id"] = frame
    with pytest.raises(StaticContractError, match="scan header_frame_id"):
        _validate(bringup=config)


def test_explicit_frame_alias_list_is_rejected():
    config = _valid_bringup()
    config["scan"]["frame_aliases"] = ["base_scan"]
    with pytest.raises(StaticContractError, match="fields are incomplete or unexpected"):
        _validate(bringup=config)


def test_unresolved_marker_nested_in_runtime_input_is_rejected():
    config = deepcopy(_valid_bringup())
    config["lifecycle"]["source_pin"] = "PENDING_IMPLEMENTATION_SOURCE_PIN"
    with pytest.raises(StaticContractError, match="unresolved marker"):
        _validate(bringup=config)


def test_missing_health_gate_is_rejected():
    config = _valid_bringup()
    config["lifecycle"]["health_gated"] = False
    with pytest.raises(StaticContractError, match="health-gated"):
        _validate(bringup=config)
