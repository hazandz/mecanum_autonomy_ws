"""Shared immutable derived-goal fact contracts with no task computation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from mecanum_nav_rl.core.lifecycle_types import (
    EpisodeLifecycleIdentity,
    ExactObservationProvenance,
    TransitionIdentity,
    require_non_negative_finite_real,
    require_non_negative_integer,
)
from mecanum_nav_rl.core.scenario_session import ScenarioSessionBinding


class TaskOracleStatus(str, Enum):
    """Explicit outcomes for one stateless derived-goal calculation."""

    READY = "ready"
    INVALID_POSE = "invalid_pose"
    INVALID_PROVENANCE = "invalid_provenance"
    TRANSITION_IDENTITY_MISMATCH = "transition_identity_mismatch"
    SCENARIO_UNAVAILABLE = "scenario_unavailable"
    SCENARIO_IDENTITY_MISMATCH = "scenario_identity_mismatch"
    UNSUPPORTED_GOAL_RULE = "unsupported_goal_rule"
    NUMERIC_DERIVATION_INVALID = "numeric_derivation_invalid"


class GoalFactJoinMode(str, Enum):
    """Exclusive provenance modes for reset observation0 and one step."""

    RESET_OBSERVATION0 = "reset_observation0"
    STEP_TRANSITION = "step_transition"


@dataclass(frozen=True, slots=True)
class GoalFactProvenance:
    """Exact-observation and scenario-session provenance for a derived fact."""

    join_mode: GoalFactJoinMode
    scenario_session_binding: ScenarioSessionBinding
    observation_provenance: ExactObservationProvenance
    source_timestamp_ns: int
    transition_identity: TransitionIdentity | None

    def __post_init__(self) -> None:
        if not isinstance(self.join_mode, GoalFactJoinMode):
            raise TypeError("join_mode must be a GoalFactJoinMode")
        if not isinstance(self.scenario_session_binding, ScenarioSessionBinding):
            raise TypeError(
                "scenario_session_binding must be a ScenarioSessionBinding"
            )
        if not isinstance(self.observation_provenance, ExactObservationProvenance):
            raise TypeError(
                "observation_provenance must be ExactObservationProvenance"
            )
        if self.observation_provenance.identity != self.lifecycle_identity:
            raise ValueError(
                "goal fact observation lifecycle must match scenario session"
            )
        if not self.observation_provenance.exact:
            raise ValueError("goal fact requires exact observation provenance")
        object.__setattr__(
            self,
            "source_timestamp_ns",
            require_non_negative_integer(
                "source_timestamp_ns", self.source_timestamp_ns
            ),
        )
        if self.source_timestamp_ns != self.observation_provenance.observation_timestamp_ns:
            raise ValueError(
                "goal fact source timestamp must match observation timestamp"
            )
        if self.join_mode is GoalFactJoinMode.RESET_OBSERVATION0:
            if self.transition_identity is not None:
                raise ValueError(
                    "reset observation0 goal fact must not carry a transition identity"
                )
        elif not isinstance(self.transition_identity, TransitionIdentity):
            raise ValueError(
                "step transition goal fact requires a transition identity"
            )
        elif self.transition_identity.identity != self.lifecycle_identity:
            raise ValueError(
                "goal fact transition lifecycle must match scenario session"
            )

    @property
    def lifecycle_identity(self) -> EpisodeLifecycleIdentity:
        """Expose the lifecycle identity held by the trusted binding."""

        return self.scenario_session_binding.lifecycle_identity

    @property
    def scenario_content_sha256(self) -> str:
        """Compatibility projection; the binding is the complete evidence."""

        return self.scenario_session_binding.scenario_content_sha256


@dataclass(frozen=True, slots=True)
class GoalOracleFact:
    """Derived goal-only scalar fact; never contains raw pose or artifact."""

    goal_distance_m: float
    goal_reached: bool
    provenance: GoalFactProvenance

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "goal_distance_m",
            require_non_negative_finite_real(
                "goal_distance_m", self.goal_distance_m
            ),
        )
        if type(self.goal_reached) is not bool:
            raise TypeError("goal_reached must be bool")
        if not isinstance(self.provenance, GoalFactProvenance):
            raise TypeError("provenance must be a GoalFactProvenance")

    @property
    def transition_identity(self) -> TransitionIdentity | None:
        return self.provenance.transition_identity

    @property
    def scenario_content_sha256(self) -> str:
        return self.provenance.scenario_content_sha256


@dataclass(frozen=True, slots=True)
class TaskOracleResult:
    """Immutable result; a non-ready outcome never carries a partial fact."""

    status: TaskOracleStatus
    fact: GoalOracleFact | None

    def __post_init__(self) -> None:
        if not isinstance(self.status, TaskOracleStatus):
            raise TypeError("status must be a TaskOracleStatus")
        if self.status is TaskOracleStatus.READY:
            if not isinstance(self.fact, GoalOracleFact):
                raise ValueError("READY result must contain a GoalOracleFact")
        elif self.fact is not None:
            raise ValueError("non-ready result must not contain a fact")

    @property
    def ready(self) -> bool:
        return self.status is TaskOracleStatus.READY

