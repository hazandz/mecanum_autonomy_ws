"""Unit tests for pure-core, derived goal facts only."""

from __future__ import annotations

import ast
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pytest

from mecanum_nav_rl.core.episode_lifecycle import (
    EpisodeLifecycleIdentity,
    ExactObservationProvenance,
    TransitionIdentity,
)
from mecanum_nav_rl.tasks.scenario_artifact import (
    GT_ODOM_2D_REFERENCE_ID,
    SCENARIO_ARTIFACT_HASH_VERSION,
    SCENARIO_ARTIFACT_SCHEMA_VERSION,
    ScenarioArtifactLoadResult,
    ScenarioArtifactLoadStatus,
    ScenarioArtifactLoader,
    scenario_artifact_sha256,
    scenario_session_binding_from_ready_artifact,
)
from mecanum_nav_rl.core.scenario_session import ScenarioSessionBinding
from mecanum_nav_rl.tasks.training_task_oracle import (
    GoalFactJoinMode,
    GoalFactProvenance,
    GoalOracleFact,
    OraclePose2D,
    TaskOracleStatus,
    TrainingTaskOracle,
)


WORLD_NAME = "world_demo"
WORLD_SHA256 = "a5e9c9b1e9b8ad11e0399855f06de687f04c702258b8b74ce563523d78ed55fe"
GOAL_RULE_ID = "distance_to_goal_lte_radius_2d"


def _unsigned_candidate_b_mapping() -> dict[str, object]:
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
                "goal_rule_id": GOAL_RULE_ID,
            },
            "start_pose_catalog": [
                {"start_id": "p0", "x_m": -4.0, "y_m": -3.0, "yaw_rad": 0.0}
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


def _ready_artifact_result() -> ScenarioArtifactLoadResult:
    unsigned = _unsigned_candidate_b_mapping()
    signed = deepcopy(unsigned)
    identity = signed["identity"]
    assert isinstance(identity, dict)
    identity["scenario_content_sha256"] = scenario_artifact_sha256(unsigned)
    return ScenarioArtifactLoader(
        expected_gazebo_world_name=WORLD_NAME,
        expected_world_file_sha256=WORLD_SHA256,
    ).load(signed)


def _transition(token: str = "transition-a") -> TransitionIdentity:
    return TransitionIdentity(
        identity=EpisodeLifecycleIdentity(
            episode_generation=1,
            reset_epoch=2,
            runtime_generation=3,
        ),
        step_index=1,
        transition_id=token,
    )


def _observation(
    identity: EpisodeLifecycleIdentity, timestamp_ns: int = 100
) -> ExactObservationProvenance:
    return ExactObservationProvenance(
        identity=identity,
        scan_timestamp_ns=timestamp_ns,
        odometry_timestamp_ns=timestamp_ns,
        observation_timestamp_ns=timestamp_ns,
    )


def _binding(
    identity: EpisodeLifecycleIdentity | None = None,
) -> ScenarioSessionBinding:
    active_identity = identity or _transition().identity
    return scenario_session_binding_from_ready_artifact(
        _ready_artifact_result(), active_identity
    )


def _goal_provenance(
    *,
    join_mode: GoalFactJoinMode = GoalFactJoinMode.STEP_TRANSITION,
    identity: EpisodeLifecycleIdentity | None = None,
    observation: ExactObservationProvenance | None = None,
    transition_identity: TransitionIdentity | None = None,
    binding: ScenarioSessionBinding | None = None,
) -> GoalFactProvenance:
    active_identity = identity or _transition().identity
    active_observation = observation or _observation(active_identity)
    if join_mode is GoalFactJoinMode.STEP_TRANSITION:
        active_transition = transition_identity or _transition()
    else:
        active_transition = None
    return GoalFactProvenance(
        join_mode=join_mode,
        scenario_session_binding=binding or _binding(active_identity),
        observation_provenance=active_observation,
        source_timestamp_ns=active_observation.observation_timestamp_ns,
        transition_identity=active_transition,
    )


def _pose(
    *,
    x_m: object = -2.0,
    y_m: object = -3.0,
    yaw_rad: object = 0.0,
    binding: object | None = None,
) -> OraclePose2D:
    return OraclePose2D(
        x_m=x_m,  # type: ignore[arg-type]
        y_m=y_m,  # type: ignore[arg-type]
        yaw_rad=yaw_rad,  # type: ignore[arg-type]
        scenario_session_binding=(
            _binding() if binding is None else binding  # type: ignore[arg-type]
        ),
    )


def _derive(
    pose: object,
    expected: object | None = None,
    provenance: GoalFactProvenance | None = None,
):
    transition = _transition() if expected is None else expected
    active_provenance = provenance or _goal_provenance(
        transition_identity=transition if isinstance(transition, TransitionIdentity) else None
    )
    return TrainingTaskOracle().derive_goal_fact(
        artifact_result=_ready_artifact_result(),
        pose=pose,
        provenance=active_provenance,
        expected_transition_identity=transition,
    )


def test_reset_observation0_goal_fact_has_exact_provenance_without_token() -> None:
    identity = _transition().identity
    observation = _observation(identity, 100)
    provenance = _goal_provenance(
        join_mode=GoalFactJoinMode.RESET_OBSERVATION0,
        identity=identity,
        observation=observation,
    )
    result = TrainingTaskOracle().derive_goal_fact(
        artifact_result=_ready_artifact_result(),
        pose=_pose(binding=_binding(identity)),
        provenance=provenance,
    )
    assert result.status is TaskOracleStatus.READY
    assert result.fact is not None
    assert result.fact.provenance.join_mode is GoalFactJoinMode.RESET_OBSERVATION0
    assert result.fact.transition_identity is None
    assert result.fact.provenance.source_timestamp_ns == 100
    assert result.fact.provenance.observation_provenance == observation


def test_reset_provenance_rejects_transition_token_and_step_requires_expected_token() -> None:
    identity = _transition().identity
    observation = _observation(identity)
    with pytest.raises(ValueError, match="must not carry"):
        GoalFactProvenance(
            join_mode=GoalFactJoinMode.RESET_OBSERVATION0,
            scenario_session_binding=_binding(identity),
            observation_provenance=observation,
            source_timestamp_ns=100,
            transition_identity=_transition(),
        )
    step_provenance = _goal_provenance()
    result = TrainingTaskOracle().derive_goal_fact(
        artifact_result=_ready_artifact_result(),
        pose=_pose(),
        provenance=step_provenance,
    )
    assert result.status is TaskOracleStatus.INVALID_PROVENANCE
    assert result.fact is None


def test_zero_distance_is_reached_and_returns_only_derived_fact() -> None:
    pose = _pose()
    result = _derive(pose)

    assert result.status is TaskOracleStatus.READY
    assert result.fact is not None
    assert result.fact.goal_distance_m == 0.0
    assert result.fact.goal_reached
    assert result.fact.transition_identity == _transition()
    assert not hasattr(result.fact, "x_m")
    assert not hasattr(result.fact, "y_m")
    assert not hasattr(result.fact, "yaw_rad")
    assert not hasattr(result.fact, "artifact")


@pytest.mark.parametrize(
    ("x_m", "expected_reached"),
    ((-1.75, True), (-1.9, True), (-1.749, False)),
)
def test_goal_radius_uses_less_than_or_equal_semantics(
    x_m: float,
    expected_reached: bool,
) -> None:
    result = _derive(_pose(x_m=x_m))

    assert result.status is TaskOracleStatus.READY
    assert result.fact is not None
    assert result.fact.goal_reached is expected_reached


def test_yaw_does_not_affect_2d_goal_distance() -> None:
    first = _derive(_pose(x_m=-1.9, y_m=-3.0, yaw_rad=0.0))
    second = _derive(_pose(x_m=-1.9, y_m=-3.0, yaw_rad=2.5))

    assert first.fact is not None
    assert second.fact is not None
    assert first.fact.goal_distance_m == pytest.approx(0.1)
    assert second.fact.goal_distance_m == pytest.approx(0.1)


def test_transition_and_scenario_identity_mismatches_fail_closed() -> None:
    expected = _transition()
    wrong_transition = _transition("transition-b")
    transition_result = _derive(
        _pose(), expected,
        _goal_provenance(transition_identity=wrong_transition),
    )

    mismatched_hash = _pose(binding=replace(_binding(), scenario_content_sha256="0" * 64))
    hash_result = _derive(mismatched_hash)

    assert transition_result.status is TaskOracleStatus.TRANSITION_IDENTITY_MISMATCH
    assert transition_result.fact is None
    assert hash_result.status is TaskOracleStatus.SCENARIO_IDENTITY_MISMATCH
    assert hash_result.fact is None


@pytest.mark.parametrize("value", (True, float("nan"), float("inf")))
def test_invalid_pose_scalars_fail_closed(value: object) -> None:
    result = _derive(_pose(x_m=value))

    assert result.status is TaskOracleStatus.INVALID_POSE
    assert result.fact is None


def test_missing_pose_provenance_and_unready_artifact_fail_closed() -> None:
    missing_provenance = _derive(_pose(binding=object()))
    unready = TrainingTaskOracle().derive_goal_fact(
        artifact_result=ScenarioArtifactLoadResult(
            status=ScenarioArtifactLoadStatus.HASH_MISMATCH,
            artifact=None,
            diagnostic_code="test",
        ),
        pose=_pose(),
        provenance=_goal_provenance(),
        expected_transition_identity=_transition(),
    )

    assert missing_provenance.status is TaskOracleStatus.SCENARIO_IDENTITY_MISMATCH
    assert missing_provenance.fact is None
    assert unready.status is TaskOracleStatus.SCENARIO_UNAVAILABLE
    assert unready.fact is None


def test_unknown_goal_rule_fails_closed_without_using_bounds() -> None:
    ready = _ready_artifact_result()
    assert ready.artifact is not None
    changed_goal = ready.artifact.task_definition.goal.model_copy(
        update={"goal_rule_id": "unknown_rule"}
    )
    changed_task = ready.artifact.task_definition.model_copy(update={"goal": changed_goal})
    changed_artifact = ready.artifact.model_copy(update={"task_definition": changed_task})
    bypassed_result = ScenarioArtifactLoadResult(
        status=ScenarioArtifactLoadStatus.READY,
        artifact=changed_artifact,
    )

    result = TrainingTaskOracle().derive_goal_fact(
        artifact_result=bypassed_result,
        pose=_pose(),
        provenance=_goal_provenance(),
        expected_transition_identity=_transition(),
    )

    assert result.status is TaskOracleStatus.UNSUPPORTED_GOAL_RULE
    assert result.fact is None


def test_finite_pose_that_overflows_distance_fails_closed() -> None:
    result = _derive(_pose(x_m=1e308, y_m=1.6e308))

    assert result.status is TaskOracleStatus.NUMERIC_DERIVATION_INVALID
    assert result.fact is None


@pytest.mark.parametrize("non_finite_distance", (float("inf"), float("nan")))
def test_ready_result_and_goal_fact_cannot_carry_non_finite_distance(
    non_finite_distance: float,
) -> None:
    result = _derive(_pose(x_m=-1.9))

    assert result.status is TaskOracleStatus.READY
    assert result.fact is not None
    assert result.fact.goal_distance_m == pytest.approx(0.1)

    with pytest.raises(ValueError, match="finite"):
        GoalOracleFact(
            goal_distance_m=non_finite_distance,
            goal_reached=False,
            provenance=_goal_provenance(),
        )


def test_result_is_immutable() -> None:
    result = _derive(_pose())
    assert result.fact is not None

    with pytest.raises(FrozenInstanceError):
        result.fact.goal_distance_m = 3.0  # type: ignore[misc]


def test_production_source_has_no_runtime_policy_or_extra_task_logic() -> None:
    source_path = Path(__file__).parents[1] / "mecanum_nav_rl" / "tasks" / "training_task_oracle.py"
    source_text = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source_text)
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imports.add(node.module)

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
    assert not any(module.split(".")[0] in forbidden_roots for module in imports)
    assert "GroundTruthSample" not in source_text
    assert "observations" not in imports
    assert "valid_area" not in source_text
    assert "collision" not in source_text
    assert "reward" not in source_text
    assert "termination" not in source_text


@pytest.mark.parametrize(
    ("field_name", "replacement"),
    (
        ("scenario_id", "other-scenario"),
        ("scenario_version", "9.9.9"),
        ("scenario_content_sha256", "b" * 64),
        ("gazebo_world_name", "other-world"),
        ("world_file_sha256", "d" * 64),
        ("coordinate_reference_id", "OTHER_REFERENCE"),
    ),
)
def test_complete_session_binding_mismatch_fails_closed(
    field_name: str, replacement: str
) -> None:
    identity = _transition().identity
    expected = _binding(identity)
    mismatched = replace(expected, **{field_name: replacement})
    observation = _observation(identity)
    provenance = _goal_provenance(
        identity=identity,
        observation=observation,
        transition_identity=_transition(),
        binding=mismatched,
    )
    result = TrainingTaskOracle().derive_goal_fact(
        artifact_result=_ready_artifact_result(),
        pose=_pose(binding=mismatched),
        provenance=provenance,
        expected_transition_identity=_transition(),
    )
    assert result.status is TaskOracleStatus.SCENARIO_IDENTITY_MISMATCH
    assert result.fact is None


def test_session_binding_factory_requires_ready_artifact_and_copies_only_scalars() -> None:
    identity = _transition().identity
    ready = _ready_artifact_result()
    binding = scenario_session_binding_from_ready_artifact(ready, identity)
    assert binding.lifecycle_identity == identity
    assert ready.artifact is not None
    assert binding.scenario_content_sha256 == ready.artifact.identity.scenario_content_sha256
    assert not hasattr(binding, "artifact")
    with pytest.raises(ValueError, match="READY"):
        scenario_session_binding_from_ready_artifact(
            ScenarioArtifactLoadResult(
                status=ScenarioArtifactLoadStatus.HASH_MISMATCH,
                artifact=None,
                diagnostic_code="test",
            ),
            identity,
        )


def test_session_binding_modules_have_no_runtime_or_policy_imports() -> None:
    """The shared join contract remains independent of runtime and policy code."""
    package_root = Path(__file__).resolve().parents[1] / "mecanum_nav_rl"
    module_paths = (
        package_root / "core" / "lifecycle_types.py",
        package_root / "core" / "scenario_session.py",
        package_root / "core" / "goal_facts.py",
        package_root / "tasks" / "scenario_artifact.py",
        package_root / "tasks" / "training_task_oracle.py",
    )
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

    for source_path in module_paths:
        source_text = source_path.read_text(encoding="utf-8")
        tree = ast.parse(source_text)
        imports: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                imports.add(node.module)

        assert not any(
            module.split(".")[0] in forbidden_roots for module in imports
        ), source_path
        assert "GroundTruthSample" not in source_text
        assert "mecanum_nav_rl.observations" not in imports
