"""Unit tests for the pure, immutable scenario-artifact validator."""

from __future__ import annotations

import ast
import hashlib
from copy import deepcopy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from mecanum_nav_rl.tasks.scenario_artifact import (
    GT_ODOM_2D_REFERENCE_ID,
    SCENARIO_ARTIFACT_HASH_VERSION,
    SCENARIO_ARTIFACT_SCHEMA_VERSION,
    ScenarioArtifactLoader,
    ScenarioArtifactLoadStatus,
    canonical_scenario_artifact_json,
    scenario_artifact_sha256,
)


WORLD_NAME = "world_demo"
WORLD_SHA256 = "a5e9c9b1e9b8ad11e0399855f06de687f04c702258b8b74ce563523d78ed55fe"


def _unsigned_candidate_b_mapping() -> dict[str, object]:
    """Return test-only selected Candidate B values without a content digest."""

    return {
        "artifact_hash_version": SCENARIO_ARTIFACT_HASH_VERSION,
        "identity": {
            "artifact_schema_version": SCENARIO_ARTIFACT_SCHEMA_VERSION,
            "scenario_id": "world_demo_candidate_b_v1",
            "scenario_version": "1.0.0",
            "gazebo_world_name": WORLD_NAME,
            "world_file_sha256": WORLD_SHA256,
            "coordinate_reference_id": GT_ODOM_2D_REFERENCE_ID,
        },
        "task_definition": {
            "goal": {
                "x_m": -2.0,
                "y_m": -3.0,
                "goal_radius_m": 0.25,
                "goal_rule_id": "distance_to_goal_lte_radius_2d",
            },
            "start_pose_catalog": [
                {
                    "start_id": "p0",
                    "x_m": -4.0,
                    "y_m": -3.0,
                    "yaw_rad": 0.0,
                }
            ],
            "candidate_task_bounds": {
                "shape_type": "axis_aligned_rectangle",
                "min_x_m": -4.5,
                "max_x_m": -1.5,
                "min_y_m": -3.5,
                "max_y_m": -2.5,
                "boundary_semantics": "boundary_invalid",
            },
            "forbidden_zone_policy": "none_provisional",
            "forbidden_zones": [],
            "randomization": "disabled",
        },
    }


def _signed_mapping(unsigned_mapping: dict[str, object]) -> dict[str, object]:
    """Attach a test-only canonical digest without mutating the input mapping."""

    signed = deepcopy(unsigned_mapping)
    identity = signed["identity"]
    assert isinstance(identity, dict)
    identity["scenario_content_sha256"] = scenario_artifact_sha256(unsigned_mapping)
    return signed


def _loader() -> ScenarioArtifactLoader:
    return ScenarioArtifactLoader(
        expected_gazebo_world_name=WORLD_NAME,
        expected_world_file_sha256=WORLD_SHA256,
    )


def _reverse_mapping_order(value: object) -> object:
    if isinstance(value, dict):
        return {
            key: _reverse_mapping_order(value[key])
            for key in reversed(tuple(value))
        }
    if isinstance(value, list):
        return [_reverse_mapping_order(item) for item in value]
    return value


def test_valid_candidate_b_mapping_and_json_text_are_ready() -> None:
    unsigned = _unsigned_candidate_b_mapping()
    signed = _signed_mapping(unsigned)

    mapping_result = _loader().load(signed)
    json_result = _loader().load(json.dumps(signed))

    assert mapping_result.status is ScenarioArtifactLoadStatus.READY
    assert mapping_result.ready
    assert mapping_result.artifact is not None
    assert mapping_result.artifact.identity.scenario_id == "world_demo_candidate_b_v1"
    assert (
        mapping_result.artifact.task_definition.goal.goal_rule_id
        == "distance_to_goal_lte_radius_2d"
    )
    assert mapping_result.artifact.task_definition.candidate_task_bounds.min_x_m == -4.5
    assert not hasattr(mapping_result.artifact.task_definition, "valid_area")
    assert json_result.status is ScenarioArtifactLoadStatus.READY


def test_canonical_hash_is_stable_when_mapping_key_order_changes() -> None:
    unsigned = _unsigned_candidate_b_mapping()
    reordered = _reverse_mapping_order(unsigned)
    assert isinstance(reordered, dict)

    assert canonical_scenario_artifact_json(unsigned) == canonical_scenario_artifact_json(reordered)
    assert scenario_artifact_sha256(unsigned) == scenario_artifact_sha256(reordered)


def test_goal_rule_is_required_and_rejects_invalid_literals() -> None:
    missing_rule = _signed_mapping(_unsigned_candidate_b_mapping())
    missing_task = missing_rule["task_definition"]
    assert isinstance(missing_task, dict)
    missing_goal = missing_task["goal"]
    assert isinstance(missing_goal, dict)
    del missing_goal["goal_rule_id"]

    invalid_type = _signed_mapping(_unsigned_candidate_b_mapping())
    invalid_type_task = invalid_type["task_definition"]
    assert isinstance(invalid_type_task, dict)
    invalid_type_goal = invalid_type_task["goal"]
    assert isinstance(invalid_type_goal, dict)
    invalid_type_goal["goal_rule_id"] = True

    invalid_literal = _signed_mapping(_unsigned_candidate_b_mapping())
    invalid_literal_task = invalid_literal["task_definition"]
    assert isinstance(invalid_literal_task, dict)
    invalid_literal_goal = invalid_literal_task["goal"]
    assert isinstance(invalid_literal_goal, dict)
    invalid_literal_goal["goal_rule_id"] = "distance_to_goal_lt_radius_2d"

    for invalid_mapping in (missing_rule, invalid_type, invalid_literal):
        result = _loader().load(invalid_mapping)
        assert result.status is ScenarioArtifactLoadStatus.MALFORMED_TASK_DEFINITION
        assert result.artifact is None


def test_goal_rule_is_in_canonical_hash_and_cannot_bypass_schema() -> None:
    unsigned = _unsigned_candidate_b_mapping()
    canonical_json = canonical_scenario_artifact_json(unsigned)
    canonical_digest = scenario_artifact_sha256(unsigned)

    assert "\"goal_rule_id\":\"distance_to_goal_lte_radius_2d\"" in canonical_json
    altered_payload = canonical_json.replace(
        "distance_to_goal_lte_radius_2d",
        "distance_to_goal_lt_radius_2d",
        1,
    )
    assert hashlib.sha256(altered_payload.encode("utf-8")).hexdigest() != canonical_digest

    changed_rule = _unsigned_candidate_b_mapping()
    changed_task = changed_rule["task_definition"]
    assert isinstance(changed_task, dict)
    changed_goal = changed_task["goal"]
    assert isinstance(changed_goal, dict)
    changed_goal["goal_rule_id"] = "distance_to_goal_lt_radius_2d"
    with pytest.raises(ValidationError):
        scenario_artifact_sha256(changed_rule)


def test_hash_mismatch_returns_no_partial_artifact() -> None:
    signed = _signed_mapping(_unsigned_candidate_b_mapping())
    identity = signed["identity"]
    assert isinstance(identity, dict)
    identity["scenario_content_sha256"] = "0" * 64

    result = _loader().load(signed)

    assert result.status is ScenarioArtifactLoadStatus.HASH_MISMATCH
    assert not result.ready
    assert result.artifact is None


@pytest.mark.parametrize(
    ("field_path", "value"),
    (
        (("identity", "artifact_schema_version"), "future/v2"),
        (("artifact_hash_version",), "future_hash/v2"),
    ),
)
def test_unknown_schema_or_hash_version_is_rejected(
    field_path: tuple[str, ...],
    value: str,
) -> None:
    signed = _signed_mapping(_unsigned_candidate_b_mapping())
    target: dict[str, object] = signed
    for key in field_path[:-1]:
        child = target[key]
        assert isinstance(child, dict)
        target = child
    target[field_path[-1]] = value

    result = _loader().load(signed)

    assert result.status is ScenarioArtifactLoadStatus.UNKNOWN_SCHEMA_VERSION
    assert result.artifact is None


@pytest.mark.parametrize(
    ("path", "value"),
    (
        (("task_definition", "goal", "x_m"), True),
        (("task_definition", "goal", "x_m"), float("nan")),
        (("task_definition", "goal", "y_m"), float("inf")),
        (("task_definition", "goal", "goal_radius_m"), 0.0),
        (("identity", "scenario_id"), " "),
    ),
)
def test_numeric_and_identifier_invalid_input_fails_closed(
    path: tuple[str, ...],
    value: object,
) -> None:
    signed = _signed_mapping(_unsigned_candidate_b_mapping())
    target: dict[str, object] = signed
    for key in path[:-1]:
        child = target[key]
        assert isinstance(child, dict)
        target = child
    target[path[-1]] = value

    result = _loader().load(signed)

    assert result.status is ScenarioArtifactLoadStatus.MALFORMED_TASK_DEFINITION
    assert result.artifact is None


def test_invalid_bounds_and_duplicate_start_id_fail_closed() -> None:
    invalid_bounds = _signed_mapping(_unsigned_candidate_b_mapping())
    task = invalid_bounds["task_definition"]
    assert isinstance(task, dict)
    bounds = task["candidate_task_bounds"]
    assert isinstance(bounds, dict)
    bounds["min_x_m"] = bounds["max_x_m"]

    duplicate_start = _signed_mapping(_unsigned_candidate_b_mapping())
    duplicate_task = duplicate_start["task_definition"]
    assert isinstance(duplicate_task, dict)
    starts = duplicate_task["start_pose_catalog"]
    assert isinstance(starts, list)
    starts.append(deepcopy(starts[0]))

    for invalid_mapping in (invalid_bounds, duplicate_start):
        result = _loader().load(invalid_mapping)
        assert result.status is ScenarioArtifactLoadStatus.MALFORMED_TASK_DEFINITION
        assert result.artifact is None


@pytest.mark.parametrize(
    ("policy", "zones"),
    (
        ("none_provisional", [{"zone_id": "unexpected"}]),
        ("other_policy", []),
    ),
)
def test_forbidden_zone_rules_fail_closed(policy: str, zones: list[dict[str, str]]) -> None:
    signed = _signed_mapping(_unsigned_candidate_b_mapping())
    task = signed["task_definition"]
    assert isinstance(task, dict)
    task["forbidden_zone_policy"] = policy
    task["forbidden_zones"] = zones

    result = _loader().load(signed)

    assert result.status is ScenarioArtifactLoadStatus.FORBIDDEN_ZONE_INVALID
    assert result.artifact is None


def test_world_and_coordinate_reference_mismatches_are_explicit() -> None:
    changed_world = _unsigned_candidate_b_mapping()
    world_identity = changed_world["identity"]
    assert isinstance(world_identity, dict)
    world_identity["gazebo_world_name"] = "other_world"

    changed_world_hash = _unsigned_candidate_b_mapping()
    world_hash_identity = changed_world_hash["identity"]
    assert isinstance(world_hash_identity, dict)
    world_hash_identity["world_file_sha256"] = "b" * 64

    changed_reference = _unsigned_candidate_b_mapping()
    reference_identity = changed_reference["identity"]
    assert isinstance(reference_identity, dict)
    reference_identity["coordinate_reference_id"] = "OTHER_REFERENCE"

    world_result = _loader().load(_signed_mapping(changed_world))
    world_hash_result = _loader().load(_signed_mapping(changed_world_hash))
    reference_result = _loader().load(_signed_mapping(changed_reference))

    assert world_result.status is ScenarioArtifactLoadStatus.WORLD_IDENTITY_MISMATCH
    assert world_result.artifact is None
    assert world_hash_result.status is ScenarioArtifactLoadStatus.WORLD_IDENTITY_MISMATCH
    assert world_hash_result.artifact is None
    assert reference_result.status is ScenarioArtifactLoadStatus.COORDINATE_REFERENCE_MISMATCH
    assert reference_result.artifact is None


def test_missing_extra_and_randomization_fields_fail_closed() -> None:
    missing_field = _signed_mapping(_unsigned_candidate_b_mapping())
    missing_task = missing_field["task_definition"]
    assert isinstance(missing_task, dict)
    del missing_task["randomization"]

    invalid_randomization = _signed_mapping(_unsigned_candidate_b_mapping())
    randomization_task = invalid_randomization["task_definition"]
    assert isinstance(randomization_task, dict)
    randomization_task["randomization"] = "enabled"

    extra_field = _signed_mapping(_unsigned_candidate_b_mapping())
    extra_task = extra_field["task_definition"]
    assert isinstance(extra_task, dict)
    extra_task["unexpected"] = True

    for invalid_mapping in (missing_field, invalid_randomization, extra_field):
        result = _loader().load(invalid_mapping)
        assert result.status is ScenarioArtifactLoadStatus.MALFORMED_TASK_DEFINITION
        assert result.artifact is None


def test_models_and_load_result_are_immutable() -> None:
    result = _loader().load(_signed_mapping(_unsigned_candidate_b_mapping()))
    assert result.artifact is not None

    with pytest.raises(ValidationError):
        result.artifact.identity.scenario_id = "mutated"  # type: ignore[misc]
    with pytest.raises(AttributeError):
        result.status = ScenarioArtifactLoadStatus.HASH_MISMATCH  # type: ignore[misc]


def test_production_source_is_isolated_from_runtime_and_policy_imports() -> None:
    source_path = Path(__file__).parents[1] / "mecanum_nav_rl" / "tasks" / "scenario_artifact.py"
    source_text = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source_text)
    imported_modules: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported_modules.add(node.module)

    forbidden_roots = {
        "rclpy",
        "tf2_ros",
        "geometry_msgs",
        "nav_msgs",
        "sensor_msgs",
        "gymnasium",
        "stable_baselines3",
        "gz",
        "gazebo",
    }
    assert not any(module.split(".")[0] in forbidden_roots for module in imported_modules)
    assert "GroundTruthSample" not in source_text
    assert "ground_truth" not in source_text.lower()
    assert "observations" not in imported_modules
    declared_names = {
        node.target.id
        for node in ast.walk(tree)
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
    }
    assert "valid_area" not in declared_names
