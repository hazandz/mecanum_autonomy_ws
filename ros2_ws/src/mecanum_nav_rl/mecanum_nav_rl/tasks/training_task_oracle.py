"""Pure-core derived goal facts for one already-validated scenario artifact."""

from __future__ import annotations

from dataclasses import dataclass
from math import hypot, isfinite
from numbers import Real

from mecanum_nav_rl.core.goal_facts import (
    GoalFactJoinMode,
    GoalFactProvenance,
    GoalOracleFact,
    TaskOracleResult,
    TaskOracleStatus,
)
from mecanum_nav_rl.core.lifecycle_types import EpisodeLifecycleIdentity, TransitionIdentity
from mecanum_nav_rl.core.scenario_session import ScenarioSessionBinding
from mecanum_nav_rl.tasks.scenario_artifact import ScenarioArtifactLoadResult


_GOAL_RULE_ID = "distance_to_goal_lte_radius_2d"


@dataclass(frozen=True, slots=True)
class OraclePose2D:
    """Caller-supplied scalar pose with scalar-only trusted session provenance."""

    x_m: float
    y_m: float
    yaw_rad: float
    scenario_session_binding: ScenarioSessionBinding



def _is_finite_real(value: object) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, Real)
        and isfinite(float(value))
    )


class TrainingTaskOracle:
    """Stateless goal-fact-only core logic for one validated scenario result."""

    @staticmethod
    def _result(status: TaskOracleStatus) -> TaskOracleResult:
        return TaskOracleResult(status=status, fact=None)

    @staticmethod
    def _pose_has_valid_scalars(pose: object) -> bool:
        return isinstance(pose, OraclePose2D) and all(
            _is_finite_real(value) for value in (pose.x_m, pose.y_m, pose.yaw_rad)
        )

    @staticmethod
    def _artifact_matches_binding(
        artifact_result: ScenarioArtifactLoadResult,
        binding: ScenarioSessionBinding,
    ) -> bool:
        if not artifact_result.ready or artifact_result.artifact is None:
            return False
        identity = artifact_result.artifact.identity
        return (
            identity.scenario_id == binding.scenario_id
            and identity.scenario_version == binding.scenario_version
            and identity.scenario_content_sha256 == binding.scenario_content_sha256
            and identity.gazebo_world_name == binding.gazebo_world_name
            and identity.world_file_sha256 == binding.world_file_sha256
            and identity.coordinate_reference_id == binding.coordinate_reference_id
        )

    def derive_goal_fact(
        self,
        *,
        artifact_result: object,
        pose: object,
        provenance: object,
        expected_transition_identity: object | None = None,
    ) -> TaskOracleResult:
        """Return one derived 2D goal fact or an explicit fail-closed status."""

        if not isinstance(artifact_result, ScenarioArtifactLoadResult):
            return self._result(TaskOracleStatus.SCENARIO_UNAVAILABLE)
        if not artifact_result.ready or artifact_result.artifact is None:
            return self._result(TaskOracleStatus.SCENARIO_UNAVAILABLE)
        if not isinstance(provenance, GoalFactProvenance):
            return self._result(TaskOracleStatus.INVALID_PROVENANCE)
        if not self._pose_has_valid_scalars(pose):
            return self._result(TaskOracleStatus.INVALID_POSE)
        assert isinstance(pose, OraclePose2D)
        if pose.scenario_session_binding != provenance.scenario_session_binding:
            return self._result(TaskOracleStatus.SCENARIO_IDENTITY_MISMATCH)
        if not self._artifact_matches_binding(
            artifact_result, provenance.scenario_session_binding
        ):
            return self._result(TaskOracleStatus.SCENARIO_IDENTITY_MISMATCH)
        if pose.scenario_session_binding.lifecycle_identity != provenance.lifecycle_identity:
            return self._result(TaskOracleStatus.INVALID_PROVENANCE)

        if provenance.join_mode is GoalFactJoinMode.RESET_OBSERVATION0:
            if expected_transition_identity is not None:
                return self._result(TaskOracleStatus.INVALID_PROVENANCE)
        elif not isinstance(expected_transition_identity, TransitionIdentity):
            return self._result(TaskOracleStatus.INVALID_PROVENANCE)
        elif provenance.transition_identity != expected_transition_identity:
            return self._result(TaskOracleStatus.TRANSITION_IDENTITY_MISMATCH)

        goal = artifact_result.artifact.task_definition.goal
        if goal.goal_rule_id != _GOAL_RULE_ID:
            return self._result(TaskOracleStatus.UNSUPPORTED_GOAL_RULE)

        goal_distance_m = hypot(float(pose.x_m) - goal.x_m, float(pose.y_m) - goal.y_m)
        if not isfinite(goal_distance_m):
            return self._result(TaskOracleStatus.NUMERIC_DERIVATION_INVALID)
        return TaskOracleResult(
            status=TaskOracleStatus.READY,
            fact=GoalOracleFact(
                goal_distance_m=goal_distance_m,
                goal_reached=goal_distance_m <= goal.goal_radius_m,
                provenance=provenance,
            ),
        )


__all__ = (
    "GoalFactJoinMode",
    "GoalFactProvenance",
    "GoalOracleFact",
    "OraclePose2D",
    "TaskOracleResult",
    "TaskOracleStatus",
    "TrainingTaskOracle",
)
