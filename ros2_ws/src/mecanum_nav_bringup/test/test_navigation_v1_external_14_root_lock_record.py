"""Static schema and boundary checks for the external 14-root lock record."""

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from mecanum_nav_bringup.navigation_v1_static_contract import (
    EXPECTED_DIRECT_DEPENDENCY_ROOTS,
    StaticContractError,
    validate_navigation_v1_runtime_inputs,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
SCHEMA_PATH = REPOSITORY_ROOT / "docs/governance/evidence/WP-05_NAVIGATION_V1_DEPENDENCY_LOCK_SCHEMA.json"
LOCK_PATH = REPOSITORY_ROOT / "docs/governance/evidence/WP-05_NAVIGATION_V1_EXTERNAL_14_ROOT_DEPENDENCY_LOCK.json"


def _reject_duplicate_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


@pytest.fixture(scope="module")
def schema_and_lock():
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    lock = json.loads(
        LOCK_PATH.read_text(encoding="utf-8"), object_pairs_hook=_reject_duplicate_pairs
    )
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(lock)
    return schema, lock


def test_record_conforms_to_active_schema_and_has_ordered_14_roots(schema_and_lock):
    schema, lock = schema_and_lock
    assert set(lock) == set(schema["properties"])
    assert lock["schema"] == "mecanum_navigation_v1_dependency_lock/v2"
    assert tuple(lock["direct_dependency_roots"]) == EXPECTED_DIRECT_DEPENDENCY_ROOTS
    assert tuple(entry["ros_package_name"] for entry in lock["external_package_locks"]) == EXPECTED_DIRECT_DEPENDENCY_ROOTS
    assert len(lock["external_package_locks"]) == 14


def test_launch_ros_is_not_a_logical_root_or_lock_entry(schema_and_lock):
    _, lock = schema_and_lock
    assert "launch_ros" not in lock["direct_dependency_roots"]
    assert all(entry["ros_package_name"] != "launch_ros" for entry in lock["external_package_locks"])


def test_record_has_complete_artifact_baseline_provenance(schema_and_lock):
    _, lock = schema_and_lock
    envelope = lock["artifact_baseline_provenance"]
    assert set(envelope) == {
        "baseline_identity",
        "artifact_closure",
        "ros_signing_key",
        "correction_report_sha256",
        "quarantined_non_closure_artifacts",
    }
    assert envelope["artifact_closure"]["closure_artifact_count"] == 1280
    assert envelope["artifact_closure"]["closure_total_bytes"] == 700260532
    assert envelope["quarantined_non_closure_artifacts"]["artifact_count"] == 6
    assert lock["workspace_source_locks"] == []


def test_runtime_validator_rejects_record_without_workspace_source_roles(schema_and_lock):
    _, lock = schema_and_lock
    with pytest.raises(StaticContractError, match="workspace source pins are incomplete"):
        validate_navigation_v1_runtime_inputs(
            lock,
            {},
            expected_map_id="warehouse_map2",
            expected_map_content_hash="2bd9ff0a40eaeb61c2359aab4bb213da623ab56746debe591edd4a54c2229f90",
        )
