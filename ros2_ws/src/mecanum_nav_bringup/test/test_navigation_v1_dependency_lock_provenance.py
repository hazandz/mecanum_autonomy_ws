"""Static tests for the Navigation V1 dependency-lock provenance envelope."""

from copy import deepcopy
import ast
import json
from pathlib import Path

import pytest

from mecanum_nav_bringup.navigation_v1_static_contract import (
    EXPECTED_DIRECT_DEPENDENCY_ROOTS,
    StaticContractError,
    _validate_artifact_baseline_provenance,
    _validate_external_package_locks,
)

ROOT = Path(__file__).resolve().parents[4]
SCHEMA_PATH = ROOT / "docs/governance/evidence/WP-05_NAVIGATION_V1_DEPENDENCY_LOCK_SCHEMA.json"
VALID = {
    "baseline_identity": {
        "base_image_digest": "ubuntu@sha256:" + "a" * 64,
        "platform": "linux/amd64",
        "source_repository": "https://example.invalid/repository.git",
        "source_commit": "b" * 40,
        "purpose": "synthetic-test-only",
    },
    "artifact_closure": {
        "artifact_locator": "synthetic-locator",
        "closure_manifest_relative_path": "metadata/closure.sha256",
        "closure_manifest_sha256": "c" * 64,
        "closure_artifact_count": 1,
        "closure_total_bytes": 1,
    },
    "ros_signing_key": {
        "keyring_relative_path": "apt_sources/keyring.gpg",
        "keyring_sha256": "d" * 64,
        "primary_fingerprint": "A" * 40,
        "fingerprint_record_sha256": "e" * 64,
    },
    "correction_report_sha256": "f" * 64,
    "quarantined_non_closure_artifacts": {
        "manifest_relative_path": "metadata/quarantine.sha256",
        "manifest_sha256": "0" * 64,
        "artifact_count": 0,
        "classification": "QUARANTINED_NON_CLOSURE_ARTIFACT_NOT_PART_OF_NAVIGATION_V1_LOCK",
    },
}


def test_valid_typed_envelope_is_accepted():
    assert _validate_artifact_baseline_provenance(deepcopy(VALID)) is None


@pytest.mark.parametrize(
    "group,field",
    [
        ("baseline_identity", "base_image_digest"),
        ("baseline_identity", "platform"),
        ("baseline_identity", "source_repository"),
        ("baseline_identity", "source_commit"),
        ("baseline_identity", "purpose"),
        ("artifact_closure", "artifact_locator"),
        ("artifact_closure", "closure_manifest_relative_path"),
        ("artifact_closure", "closure_manifest_sha256"),
        ("artifact_closure", "closure_artifact_count"),
        ("artifact_closure", "closure_total_bytes"),
        ("ros_signing_key", "keyring_relative_path"),
        ("ros_signing_key", "keyring_sha256"),
        ("ros_signing_key", "primary_fingerprint"),
        ("ros_signing_key", "fingerprint_record_sha256"),
        (None, "correction_report_sha256"),
        ("quarantined_non_closure_artifacts", "manifest_relative_path"),
        ("quarantined_non_closure_artifacts", "manifest_sha256"),
        ("quarantined_non_closure_artifacts", "artifact_count"),
        ("quarantined_non_closure_artifacts", "classification"),
    ],
)
def test_each_required_envelope_field_is_required(group, field):
    value = deepcopy(VALID)
    target = value if group is None else value[group]
    del target[field]
    with pytest.raises(StaticContractError):
        _validate_artifact_baseline_provenance(value)


def test_unknown_fields_at_each_envelope_level_are_rejected():
    value = deepcopy(VALID)
    value["unexpected"] = "x"
    with pytest.raises(StaticContractError):
        _validate_artifact_baseline_provenance(value)
    for group in ("baseline_identity", "artifact_closure", "ros_signing_key", "quarantined_non_closure_artifacts"):
        value = deepcopy(VALID)
        value[group]["unexpected"] = "x"
        with pytest.raises(StaticContractError):
            _validate_artifact_baseline_provenance(value)


@pytest.mark.parametrize(
    "path,value",
    [
        (("baseline_identity", "base_image_digest"), "ubuntu:latest"),
        (("baseline_identity", "source_repository"), "file:///tmp/repo"),
        (("baseline_identity", "source_commit"), "g" * 40),
        (("artifact_closure", "closure_manifest_sha256"), "F" * 64),
        (("ros_signing_key", "keyring_sha256"), "x" * 64),
        (("ros_signing_key", "primary_fingerprint"), "a" * 40),
        ((None, "correction_report_sha256"), "z" * 64),
    ],
)
def test_malformed_immutable_identifiers_are_rejected(path, value):
    result = deepcopy(VALID)
    group, field = path
    (result if group is None else result[group])[field] = value
    with pytest.raises(StaticContractError):
        _validate_artifact_baseline_provenance(result)


@pytest.mark.parametrize(
    "group,field,value",
    [
        ("artifact_closure", "closure_artifact_count", 0),
        ("artifact_closure", "closure_artifact_count", True),
        ("artifact_closure", "closure_total_bytes", -1),
        ("artifact_closure", "closure_total_bytes", 1.5),
        ("quarantined_non_closure_artifacts", "artifact_count", -1),
        ("quarantined_non_closure_artifacts", "artifact_count", False),
    ],
)
def test_invalid_counts_and_byte_sizes_are_rejected(group, field, value):
    result = deepcopy(VALID)
    result[group][field] = value
    with pytest.raises(StaticContractError):
        _validate_artifact_baseline_provenance(result)


def test_quarantine_classification_must_match_exact_constant():
    result = deepcopy(VALID)
    result["quarantined_non_closure_artifacts"]["classification"] = "NOT_QUARANTINED"
    with pytest.raises(StaticContractError, match="classification"):
        _validate_artifact_baseline_provenance(result)


def test_logical_root_set_remains_exactly_14_and_excludes_launch_ros():
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    roots = schema["properties"]["direct_dependency_roots"]["const"]
    assert tuple(roots) == EXPECTED_DIRECT_DEPENDENCY_ROOTS
    assert len(roots) == 14
    assert "launch_ros" not in roots


def test_launch_ros_is_rejected_as_a_logical_external_lock_root():
    entries = [
        {
            "ros_distribution": "fixture",
            "ubuntu_release": "fixture",
            "ros_package_name": package,
            "debian_package_name": "fixture-deb",
            "installed_version": "fixture-version",
            "architecture": "fixture-architecture",
            "apt_repository_origin": "fixture-origin",
            "deb_sha256": "a" * 64,
            "dependency_closure_sha256": "b" * 64,
            "evidence_capture_method": "synthetic-test",
        }
        for package in EXPECTED_DIRECT_DEPENDENCY_ROOTS
    ]
    entries[-1]["ros_package_name"] = "launch_ros"
    with pytest.raises(StaticContractError, match="roots are incomplete or unexpected"):
        _validate_external_package_locks(entries)


def test_relative_paths_reject_absolute_parent_and_backslash_paths():
    for field_group, field in (
        ("artifact_closure", "closure_manifest_relative_path"),
        ("ros_signing_key", "keyring_relative_path"),
        ("quarantined_non_closure_artifacts", "manifest_relative_path"),
    ):
        for path in ("/absolute/path", "metadata/../escape", "metadata\\escape"):
            result = deepcopy(VALID)
            result[field_group][field] = path
            with pytest.raises(StaticContractError):
                _validate_artifact_baseline_provenance(result)


def test_schema_is_draft_2020_12_and_requires_strict_nested_envelope():
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    assert schema["$schema"].endswith("2020-12/schema")
    assert "artifact_baseline_provenance" in schema["required"]
    envelope = schema["properties"]["artifact_baseline_provenance"]
    assert envelope["additionalProperties"] is False
    for group in envelope["properties"].values():
        if group.get("type") == "object":
            assert group["additionalProperties"] is False


def test_validator_module_has_no_ros_runtime_imports():
    source = (ROOT / "ros2_ws/src/mecanum_nav_bringup/mecanum_nav_bringup/navigation_v1_static_contract.py").read_text()
    tree = ast.parse(source)
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    assert not any(name == "rclpy" or name.startswith(("ros2", "launch", "nav2_")) for name in imports)
