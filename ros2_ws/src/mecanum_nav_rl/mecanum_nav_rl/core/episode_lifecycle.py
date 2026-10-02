"""Core-only, transactional episode lifecycle facts and state machine.

This module coordinates immutable caller-supplied test facts only.  It does
not publish commands, read sensors, call an oracle, evaluate reward or
termination, or implement a runtime contact latch.  A command receipt and
contact candidate accepted here are explicit test/core facts, not evidence
that a runtime producer exists.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite
from numbers import Real
from threading import RLock

from mecanum_nav_rl.core.goal_facts import (
    GoalFactJoinMode,
    GoalOracleFact,
    TaskOracleResult,
    TaskOracleStatus,
)
from mecanum_nav_rl.core.lifecycle_types import (
    EpisodeLifecycleIdentity,
    ExactObservationProvenance,
    TransitionIdentity,
    require_non_negative_finite_real as _require_non_negative_finite_real,
    require_non_negative_integer as _require_non_negative_integer,
    require_sha256 as _require_sha256,
)
from mecanum_nav_rl.core.scenario_session import ScenarioSessionBinding
from mecanum_nav_rl.observations.previous_command import PreviousNormalizedCommand


class LifecycleIdentityError(ValueError):
    """Raised when an operation carries stale, future, or mismatched identity."""

    def __init__(self, relation: str, message: str) -> None:
        super().__init__(message)
        self.relation = relation


class LifecycleStateError(RuntimeError):
    """Raised when reset/step operations are attempted in an invalid state."""


class EpisodeLifecycleState(str, Enum):
    """Lifecycle state; RESETTING/WAITING states are not Gym transitions."""

    UNINITIALIZED = "uninitialized"
    RESETTING = "resetting"
    WAITING_FOR_INITIAL_OBSERVATION = "waiting_for_initial_observation"
    RUNNING = "running"
    TERMINATED = "terminated"
    TRUNCATED = "truncated"
    FAULT = "fault"


class EpisodeOperationStatus(str, Enum):
    """Core operation outcomes, including aborts that are not RL transitions."""

    RESET_STARTED = "reset_started"
    WAITING_FOR_INITIAL_OBSERVATION = "waiting_for_initial_observation"
    RESET_COMMITTED = "reset_committed"
    RESET_ABORT = "reset_abort"
    STEP_STARTED = "step_started"
    CONTACT_STAGED = "contact_staged"
    STEP_COMMITTED = "step_committed"
    STEP_ABORT = "step_abort"


@dataclass(frozen=True, slots=True)
class ContactCandidateSnapshot:
    """Read-only test-only contact candidate; construction never consumes it."""

    transition_identity: TransitionIdentity
    event_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.transition_identity, TransitionIdentity):
            raise TypeError("transition_identity must be a TransitionIdentity")
        if not isinstance(self.event_id, str) or not self.event_id.strip():
            raise ValueError("event_id must be a non-empty string")


@dataclass(frozen=True, slots=True)
class CommandReceiptSnapshot:
    """Injected test-only receipt fact for one transition.

    ``final_issued_command`` is already represented in the normalized feature
    domain expected by the existing observation core.  This value object
    neither publishes nor proves a real command was issued; runtime receipt
    ownership and physical-to-normalized mapping remain outside this module.
    """

    transition_identity: TransitionIdentity
    receipt_id: str
    final_issued_command: PreviousNormalizedCommand

    def __post_init__(self) -> None:
        if not isinstance(self.transition_identity, TransitionIdentity):
            raise TypeError("transition_identity must be a TransitionIdentity")
        if not isinstance(self.receipt_id, str) or not self.receipt_id.strip():
            raise ValueError("receipt_id must be a non-empty string")
        if not isinstance(self.final_issued_command, PreviousNormalizedCommand):
            raise TypeError(
                "final_issued_command must be a PreviousNormalizedCommand"
            )


@dataclass(frozen=True, slots=True)
class ResetCommitCandidate:
    """Immutable, untrusted test facts to validate before reset commit.

    Numeric baseline fields are intentionally validated by the manager's
    transaction boundary, so malformed/missing oracle facts produce a typed
    RESET_ABORT and FAULT rather than escaping before the lifecycle can fail
    closed.  No oracle implementation is provided here.
    """

    identity: EpisodeLifecycleIdentity
    observation_provenance: ExactObservationProvenance | None
    goal_result: object
    previous_issued_command: object


@dataclass(frozen=True, slots=True)
class ResetCommitFacts:
    """Validated reset commit facts, including observation0 reward baseline."""

    identity: EpisodeLifecycleIdentity
    observation_provenance: ExactObservationProvenance
    previous_goal_distance_m: float
    previous_committed_sim_time_ns: int
    scenario_session_binding: ScenarioSessionBinding
    previous_issued_command: PreviousNormalizedCommand

    def __post_init__(self) -> None:
        if not isinstance(self.identity, EpisodeLifecycleIdentity):
            raise TypeError("identity must be an EpisodeLifecycleIdentity")
        if not isinstance(self.observation_provenance, ExactObservationProvenance):
            raise TypeError("observation_provenance must be exact provenance")
        object.__setattr__(
            self,
            "previous_goal_distance_m",
            _require_non_negative_finite_real(
                "previous_goal_distance_m", self.previous_goal_distance_m
            ),
        )
        object.__setattr__(
            self,
            "previous_committed_sim_time_ns",
            _require_non_negative_integer(
                "previous_committed_sim_time_ns",
                self.previous_committed_sim_time_ns,
            ),
        )
        if not isinstance(self.scenario_session_binding, ScenarioSessionBinding):
            raise TypeError("scenario_session_binding must be a ScenarioSessionBinding")
        if self.identity != self.scenario_session_binding.lifecycle_identity:
            raise ValueError("reset facts and scenario session lifecycle do not match")
        if not isinstance(self.previous_issued_command, PreviousNormalizedCommand):
            raise TypeError(
                "previous_issued_command must be a PreviousNormalizedCommand"
            )
        if any(
            component != 0.0
            for component in (
                self.previous_issued_command.vx,
                self.previous_issued_command.vy,
                self.previous_issued_command.wz,
            )
        ):
            raise ValueError("reset previous issued command must be exactly zero")
        if self.identity != self.observation_provenance.identity:
            raise ValueError("reset facts and observation lifecycle do not match")
        if not self.observation_provenance.exact:
            raise ValueError("reset observation provenance must be exact")
        if (
            self.previous_committed_sim_time_ns
            != self.observation_provenance.observation_timestamp_ns
        ):
            raise ValueError("reset baseline timestamp must match observation0")

    @property
    def scenario_content_sha256(self) -> str:
        return self.scenario_session_binding.scenario_content_sha256


@dataclass(frozen=True, slots=True)
class CommittedRewardBaseline:
    """Committed distance/time point used as the next step's before-state."""

    identity: EpisodeLifecycleIdentity
    observation_provenance: ExactObservationProvenance
    previous_goal_distance_m: float
    previous_committed_sim_time_ns: int
    scenario_session_binding: ScenarioSessionBinding

    def __post_init__(self) -> None:
        if not isinstance(self.identity, EpisodeLifecycleIdentity):
            raise TypeError("identity must be an EpisodeLifecycleIdentity")
        if not isinstance(self.observation_provenance, ExactObservationProvenance):
            raise TypeError("observation_provenance must be exact provenance")
        object.__setattr__(
            self,
            "previous_goal_distance_m",
            _require_non_negative_finite_real(
                "previous_goal_distance_m", self.previous_goal_distance_m
            ),
        )
        object.__setattr__(
            self,
            "previous_committed_sim_time_ns",
            _require_non_negative_integer(
                "previous_committed_sim_time_ns",
                self.previous_committed_sim_time_ns,
            ),
        )
        if not isinstance(self.scenario_session_binding, ScenarioSessionBinding):
            raise TypeError("scenario_session_binding must be a ScenarioSessionBinding")
        if self.identity != self.scenario_session_binding.lifecycle_identity:
            raise ValueError("baseline and scenario session lifecycle do not match")
        if self.identity != self.observation_provenance.identity:
            raise ValueError("baseline lifecycle and observation do not match")
        if not self.observation_provenance.exact:
            raise ValueError("baseline observation provenance must be exact")
        if (
            self.previous_committed_sim_time_ns
            != self.observation_provenance.observation_timestamp_ns
        ):
            raise ValueError("baseline timestamp must match its observation")

    @property
    def scenario_content_sha256(self) -> str:
        return self.scenario_session_binding.scenario_content_sha256


@dataclass(frozen=True, slots=True)
class GoalProgressInput:
    """Derived, commit-bound goal progress without reward or raw pose data."""

    transition_identity: TransitionIdentity
    scenario_session_binding: ScenarioSessionBinding
    previous_goal_distance_m: float
    current_goal_distance_m: float
    delta_d: float
    previous_observation_timestamp_ns: int
    current_observation_timestamp_ns: int

    def __post_init__(self) -> None:
        if not isinstance(self.transition_identity, TransitionIdentity):
            raise TypeError("transition_identity must be a TransitionIdentity")
        if not isinstance(self.scenario_session_binding, ScenarioSessionBinding):
            raise TypeError("scenario_session_binding must be a ScenarioSessionBinding")
        if self.transition_identity.identity != self.scenario_session_binding.lifecycle_identity:
            raise ValueError("goal progress transition and scenario session do not match")
        for field_name in ("previous_goal_distance_m", "current_goal_distance_m"):
            object.__setattr__(
                self,
                field_name,
                _require_non_negative_finite_real(field_name, getattr(self, field_name)),
            )
        if isinstance(self.delta_d, bool) or not isinstance(self.delta_d, Real):
            raise TypeError("delta_d must be a real number")
        if not isfinite(float(self.delta_d)):
            raise ValueError("delta_d must be finite")
        object.__setattr__(self, "delta_d", float(self.delta_d))
        for field_name in ("previous_observation_timestamp_ns", "current_observation_timestamp_ns"):
            object.__setattr__(
                self, field_name, _require_non_negative_integer(field_name, getattr(self, field_name))
            )
        if self.current_observation_timestamp_ns <= self.previous_observation_timestamp_ns:
            raise ValueError("current observation timestamp must strictly increase")
        if self.delta_d != self.previous_goal_distance_m - self.current_goal_distance_m:
            raise ValueError("delta_d must equal previous minus current goal distance")

    @property
    def scenario_content_sha256(self) -> str:
        return self.scenario_session_binding.scenario_content_sha256


@dataclass(frozen=True, slots=True)
class StepCommitCandidate:
    """Immutable test-only, prevalidated candidate for one transition commit."""

    transition_identity: TransitionIdentity
    observation_provenance: ExactObservationProvenance
    goal_result: object
    command_receipt: CommandReceiptSnapshot
    committed_state: EpisodeLifecycleState = EpisodeLifecycleState.RUNNING

    @property
    def identity(self) -> EpisodeLifecycleIdentity:
        """Expose the lifecycle identity carried by the transition token."""

        return self.transition_identity.identity

    @property
    def step_index(self) -> int:
        """Expose the step index carried by the transition token."""

        return self.transition_identity.step_index


@dataclass(frozen=True, slots=True)
class EpisodeLifecycleSnapshot:
    """Immutable view of lifecycle state and currently committed core facts."""

    state: EpisodeLifecycleState
    identity: EpisodeLifecycleIdentity | None
    step_index: int | None
    pending_scenario_session_binding: ScenarioSessionBinding | None
    committed_scenario_session_binding: ScenarioSessionBinding | None
    reward_baseline: CommittedRewardBaseline | None
    reset_commit_facts: ResetCommitFacts | None
    previous_issued_command: PreviousNormalizedCommand | None
    last_committed_command_receipt: CommandReceiptSnapshot | None
    last_committed_goal_progress: GoalProgressInput | None
    staged_contact_candidate: ContactCandidateSnapshot | None
    consumed_contact_event_ids: tuple[str, ...]
    consumed_receipt_ids: tuple[str, ...]
    active_transition_identity: TransitionIdentity | None
    committed_transition_ids: tuple[str, ...]
    reset_in_progress: bool
    step_in_progress: bool


@dataclass(frozen=True, slots=True)
class EpisodeLifecycleResult:
    """Explicit lifecycle operation outcome; abort statuses are not transitions."""

    status: EpisodeOperationStatus
    snapshot: EpisodeLifecycleSnapshot
    reason: str | None = None
    consumed_contact_event_id: str | None = None
    goal_progress_input: GoalProgressInput | None = None


class EpisodeLifecycle:
    """Pure-core transactional reset/step lifecycle contract.

    The manager accepts immutable facts and commits internal state only after
    validating lifecycle identity and provenance.  It does not call a
    simulator, publish/inhibit commands, evaluate reward/termination, or own a
    runtime ContactLatch.
    """

    def __init__(self) -> None:
        self._lock = RLock()
        self._state = EpisodeLifecycleState.UNINITIALIZED
        self._identity: EpisodeLifecycleIdentity | None = None
        self._step_index: int | None = None
        self._pending_scenario_session_binding: ScenarioSessionBinding | None = None
        self._committed_scenario_session_binding: ScenarioSessionBinding | None = None
        self._reward_baseline: CommittedRewardBaseline | None = None
        self._reset_commit_facts: ResetCommitFacts | None = None
        self._previous_issued_command: PreviousNormalizedCommand | None = None
        self._last_committed_command_receipt: CommandReceiptSnapshot | None = None
        self._last_committed_goal_progress: GoalProgressInput | None = None
        self._staged_contact_candidate: ContactCandidateSnapshot | None = None
        self._consumed_contact_event_ids: tuple[str, ...] = ()
        self._consumed_receipt_ids: tuple[str, ...] = ()
        self._active_transition_identity: TransitionIdentity | None = None
        self._committed_transition_ids: tuple[str, ...] = ()
        self._reset_in_progress = False
        self._step_in_progress = False

    @property
    def snapshot(self) -> EpisodeLifecycleSnapshot:
        """Return an immutable snapshot of current lifecycle facts."""

        with self._lock:
            return self._snapshot()

    def begin_reset(
        self,
        identity: EpisodeLifecycleIdentity,
        scenario_session_binding: ScenarioSessionBinding,
    ) -> EpisodeLifecycleResult:
        """Start a new generation and clear all prior episode state immediately."""

        if not isinstance(identity, EpisodeLifecycleIdentity):
            raise TypeError("identity must be an EpisodeLifecycleIdentity")
        if not isinstance(scenario_session_binding, ScenarioSessionBinding):
            raise TypeError("scenario_session_binding must be a ScenarioSessionBinding")
        if scenario_session_binding.lifecycle_identity != identity:
            raise ValueError("scenario session lifecycle must match reset identity")
        with self._lock:
            if self._reset_in_progress or self._step_in_progress:
                raise LifecycleStateError("reset and step transactions cannot overlap")
            self._validate_new_reset_identity(identity)
            self._identity = identity
            self._state = EpisodeLifecycleState.RESETTING
            self._clear_episode_facts()
            self._pending_scenario_session_binding = scenario_session_binding
            self._reset_in_progress = True
            return self._result(EpisodeOperationStatus.RESET_STARTED)

    def wait_for_initial_observation(
        self, identity: EpisodeLifecycleIdentity
    ) -> EpisodeLifecycleResult:
        """Enter the observation0 wait phase for the active reset identity."""

        with self._lock:
            self._require_identity(identity)
            if self._state is not EpisodeLifecycleState.RESETTING:
                raise LifecycleStateError("initial observation wait requires RESETTING")
            self._state = EpisodeLifecycleState.WAITING_FOR_INITIAL_OBSERVATION
            return self._result(
                EpisodeOperationStatus.WAITING_FOR_INITIAL_OBSERVATION
            )

    def commit_reset(self, candidate: ResetCommitCandidate) -> EpisodeLifecycleResult:
        """Validate observation0 and oracle baseline, then atomically enter RUNNING.

        Any malformed or mismatched candidate produces RESET_ABORT and FAULT;
        no baseline/history from an earlier episode survives ``begin_reset``.
        """

        with self._lock:
            if self._state is not EpisodeLifecycleState.WAITING_FOR_INITIAL_OBSERVATION:
                raise LifecycleStateError("reset commit requires initial observation wait")
            try:
                facts = self._validate_reset_candidate(candidate)
            except (TypeError, ValueError, OverflowError) as error:
                return self._abort_reset_locked(str(error))

            self._reset_commit_facts = facts
            self._reward_baseline = CommittedRewardBaseline(
                identity=facts.identity,
                observation_provenance=facts.observation_provenance,
                previous_goal_distance_m=facts.previous_goal_distance_m,
                previous_committed_sim_time_ns=facts.previous_committed_sim_time_ns,
                scenario_session_binding=facts.scenario_session_binding,
            )
            self._committed_scenario_session_binding = facts.scenario_session_binding
            self._pending_scenario_session_binding = None
            self._previous_issued_command = facts.previous_issued_command
            self._step_index = 0
            self._state = EpisodeLifecycleState.RUNNING
            self._reset_in_progress = False
            return self._result(EpisodeOperationStatus.RESET_COMMITTED)

    def abort_reset(self, reason: str) -> EpisodeLifecycleResult:
        """Fail the reset without returning observation0 or retaining old facts."""

        with self._lock:
            if not self._reset_in_progress:
                raise LifecycleStateError("there is no active reset to abort")
            return self._abort_reset_locked(reason)

    def begin_step(self, transition_identity: TransitionIdentity) -> EpisodeLifecycleResult:
        """Bind one caller-supplied token to a step with a committed baseline."""

        if not isinstance(transition_identity, TransitionIdentity):
            raise TypeError("transition_identity must be a TransitionIdentity")
        with self._lock:
            self._require_identity(transition_identity.identity)
            if self._state is not EpisodeLifecycleState.RUNNING:
                raise LifecycleStateError("begin_step requires RUNNING")
            if self._reset_in_progress or self._step_in_progress:
                raise LifecycleStateError("reset and step transactions cannot overlap")
            if (
                self._reward_baseline is None
                or self._committed_scenario_session_binding is None
                or self._step_index is None
            ):
                raise LifecycleStateError("RUNNING requires a committed reset baseline and session")
            next_step_index = self._step_index + 1
            if transition_identity.step_index != next_step_index:
                relation = "stale" if transition_identity.step_index < next_step_index else "future"
                raise LifecycleIdentityError(relation, "transition step_index is not the next step")
            if transition_identity.transition_id in self._committed_transition_ids:
                raise LifecycleIdentityError("stale", "transition_id has already been committed")
            self._active_transition_identity = transition_identity
            self._step_in_progress = True
            return self._result(EpisodeOperationStatus.STEP_STARTED)

    def stage_contact_candidate(
        self, candidate: ContactCandidateSnapshot
    ) -> EpisodeLifecycleResult:
        """Stage an immutable contact snapshot without consuming its event."""

        if not isinstance(candidate, ContactCandidateSnapshot):
            raise TypeError("candidate must be a ContactCandidateSnapshot")
        with self._lock:
            if not self._step_in_progress or self._state is not EpisodeLifecycleState.RUNNING:
                raise LifecycleStateError("contact candidate requires an active step")
            if candidate.transition_identity != self._active_transition_identity:
                return self._abort_step_locked("contact transition identity does not match active step")
            if candidate.event_id in self._consumed_contact_event_ids:
                raise LifecycleStateError("contact event has already been consumed")
            if self._staged_contact_candidate is not None:
                if self._staged_contact_candidate == candidate:
                    raise LifecycleStateError("contact candidate is already staged")
                raise LifecycleStateError("only one contact candidate may be staged")
            self._staged_contact_candidate = candidate
            return self._result(EpisodeOperationStatus.CONTACT_STAGED)

    def commit_step(self, candidate: StepCommitCandidate) -> EpisodeLifecycleResult:
        """Atomically commit validated goal progress and other transition facts."""

        with self._lock:
            if not self._step_in_progress or self._state is not EpisodeLifecycleState.RUNNING:
                raise LifecycleStateError("step commit requires an active RUNNING step")
            try:
                validated, goal_progress = self._validate_step_candidate(candidate)
            except (TypeError, ValueError, OverflowError) as error:
                return self._abort_step_locked(str(error))

            goal_fact = validated.goal_result.fact
            if goal_fact is None:
                return self._abort_step_locked("ready goal result did not contain a fact")
            new_baseline = CommittedRewardBaseline(
                identity=validated.identity,
                observation_provenance=validated.observation_provenance,
                previous_goal_distance_m=goal_fact.goal_distance_m,
                previous_committed_sim_time_ns=goal_fact.provenance.source_timestamp_ns,
                scenario_session_binding=goal_fact.provenance.scenario_session_binding,
            )
            old_contact = self._staged_contact_candidate
            consumed_event_id = old_contact.event_id if old_contact is not None else None
            if consumed_event_id is not None:
                self._consumed_contact_event_ids = (
                    *self._consumed_contact_event_ids,
                    consumed_event_id,
                )

            self._consumed_receipt_ids = (
                *self._consumed_receipt_ids,
                validated.command_receipt.receipt_id,
            )
            self._committed_transition_ids = (
                *self._committed_transition_ids,
                validated.transition_identity.transition_id,
            )
            self._reward_baseline = new_baseline
            self._committed_scenario_session_binding = new_baseline.scenario_session_binding
            self._previous_issued_command = validated.command_receipt.final_issued_command
            self._last_committed_command_receipt = validated.command_receipt
            self._last_committed_goal_progress = goal_progress
            self._step_index = validated.step_index
            self._state = validated.committed_state
            self._staged_contact_candidate = None
            self._active_transition_identity = None
            self._step_in_progress = False
            return self._result(
                EpisodeOperationStatus.STEP_COMMITTED,
                consumed_contact_event_id=consumed_event_id,
                goal_progress_input=goal_progress,
            )

    def abort_step(self, reason: str) -> EpisodeLifecycleResult:
        """Abort before commit; retain committed before-state and do not consume contact."""

        with self._lock:
            if not self._step_in_progress:
                raise LifecycleStateError("there is no active step to abort")
            return self._abort_step_locked(reason)

    def _validate_new_reset_identity(self, identity: EpisodeLifecycleIdentity) -> None:
        if self._identity is None:
            return
        if identity.episode_generation <= self._identity.episode_generation:
            raise LifecycleIdentityError(
                "stale", "new reset episode_generation must strictly increase"
            )
        if identity.reset_epoch <= self._identity.reset_epoch:
            raise LifecycleIdentityError("stale", "new reset_epoch must strictly increase")
        if identity.runtime_generation < self._identity.runtime_generation:
            raise LifecycleIdentityError("stale", "runtime_generation cannot decrease")

    def _require_identity(self, identity: EpisodeLifecycleIdentity) -> None:
        if not isinstance(identity, EpisodeLifecycleIdentity):
            raise TypeError("identity must be an EpisodeLifecycleIdentity")
        if self._identity is None:
            raise LifecycleIdentityError("uninitialized", "no active lifecycle identity")
        if identity == self._identity:
            return
        if identity.episode_generation < self._identity.episode_generation:
            raise LifecycleIdentityError("stale", "operation carries a stale generation")
        if identity.episode_generation > self._identity.episode_generation:
            raise LifecycleIdentityError("future", "operation carries a future generation")
        raise LifecycleIdentityError("mismatch", "lifecycle identity does not match")

    def _require_ready_goal_fact(
        self, goal_result: object, expected_mode: GoalFactJoinMode
    ) -> GoalOracleFact:
        """Return a ready shared-core derived fact in the required mode."""

        if not isinstance(goal_result, TaskOracleResult):
            raise TypeError("goal_result must be a TaskOracleResult")
        if goal_result.status is not TaskOracleStatus.READY or goal_result.fact is None:
            raise ValueError("goal result must be READY with a fact")
        if goal_result.fact.provenance.join_mode is not expected_mode:
            raise ValueError("goal fact join mode does not match lifecycle operation")
        return goal_result.fact

    def _validate_reset_candidate(self, candidate: ResetCommitCandidate) -> ResetCommitFacts:
        if not isinstance(candidate, ResetCommitCandidate):
            raise TypeError("candidate must be a ResetCommitCandidate")
        self._require_identity(candidate.identity)
        provenance = candidate.observation_provenance
        if not isinstance(provenance, ExactObservationProvenance):
            raise TypeError("reset requires exact observation provenance")
        self._require_identity(provenance.identity)
        if not provenance.exact:
            raise ValueError("reset observation scan/odometry/observation stamps must match")
        if self._pending_scenario_session_binding is None:
            raise ValueError("reset requires a pending scenario session binding")
        goal_fact = self._require_ready_goal_fact(
            candidate.goal_result, GoalFactJoinMode.RESET_OBSERVATION0
        )
        goal_provenance = goal_fact.provenance
        if goal_provenance.scenario_session_binding != self._pending_scenario_session_binding:
            raise ValueError("reset goal fact scenario session does not match pending binding")
        if goal_provenance.lifecycle_identity != candidate.identity:
            raise ValueError("reset goal fact lifecycle does not match active lifecycle")
        if goal_provenance.observation_provenance != provenance:
            raise ValueError("reset goal fact does not join observation0")
        if goal_provenance.source_timestamp_ns != provenance.observation_timestamp_ns:
            raise ValueError("reset goal fact timestamp must match exact observation0")
        if goal_provenance.transition_identity is not None:
            raise ValueError("reset goal fact must not carry a transition identity")
        distance = _require_non_negative_finite_real("previous_goal_distance_m", goal_fact.goal_distance_m)
        if not isinstance(candidate.previous_issued_command, PreviousNormalizedCommand):
            raise TypeError("reset requires a PreviousNormalizedCommand")
        return ResetCommitFacts(
            identity=candidate.identity,
            observation_provenance=provenance,
            previous_goal_distance_m=distance,
            previous_committed_sim_time_ns=goal_provenance.source_timestamp_ns,
            scenario_session_binding=goal_provenance.scenario_session_binding,
            previous_issued_command=candidate.previous_issued_command,
        )

    def _validate_step_candidate(
        self, candidate: StepCommitCandidate
    ) -> tuple[StepCommitCandidate, GoalProgressInput]:
        if not isinstance(candidate, StepCommitCandidate):
            raise TypeError("candidate must be a StepCommitCandidate")
        if not isinstance(candidate.transition_identity, TransitionIdentity):
            raise TypeError("step requires a TransitionIdentity")
        if candidate.transition_identity != self._active_transition_identity:
            raise ValueError("candidate transition identity does not match active step")
        self._require_identity(candidate.identity)
        if (
            self._reward_baseline is None
            or self._committed_scenario_session_binding is None
            or self._step_index is None
        ):
            raise ValueError("step requires a committed reward baseline and session")
        if candidate.step_index != self._step_index + 1:
            raise ValueError("step_index must advance exactly once")
        provenance = candidate.observation_provenance
        if not isinstance(provenance, ExactObservationProvenance):
            raise TypeError("step requires exact observation provenance")
        self._require_identity(provenance.identity)
        if not provenance.exact:
            raise ValueError("step observation scan/odometry/observation stamps must match")
        goal_fact = self._require_ready_goal_fact(
            candidate.goal_result, GoalFactJoinMode.STEP_TRANSITION
        )
        goal_provenance = goal_fact.provenance
        if goal_provenance.scenario_session_binding != self._committed_scenario_session_binding:
            raise ValueError("step goal fact scenario session does not match committed binding")
        if goal_provenance.lifecycle_identity != candidate.identity:
            raise ValueError("step goal fact lifecycle does not match active lifecycle")
        if goal_provenance.transition_identity != self._active_transition_identity:
            raise ValueError("step goal fact transition identity does not match active step")
        if goal_provenance.observation_provenance != provenance:
            raise ValueError("step goal fact does not join current exact observation")
        if goal_provenance.source_timestamp_ns != provenance.observation_timestamp_ns:
            raise ValueError("step goal fact timestamp must match current observation")
        if (
            self._reward_baseline.scenario_session_binding
            != self._committed_scenario_session_binding
        ):
            raise ValueError("committed baseline scenario session does not match lifecycle")
        sim_time = goal_provenance.source_timestamp_ns
        if sim_time <= self._reward_baseline.previous_committed_sim_time_ns:
            raise ValueError("committed simulation time must strictly increase")
        progress = GoalProgressInput(
            transition_identity=candidate.transition_identity,
            scenario_session_binding=goal_provenance.scenario_session_binding,
            previous_goal_distance_m=self._reward_baseline.previous_goal_distance_m,
            current_goal_distance_m=goal_fact.goal_distance_m,
            delta_d=(self._reward_baseline.previous_goal_distance_m - goal_fact.goal_distance_m),
            previous_observation_timestamp_ns=self._reward_baseline.observation_provenance.observation_timestamp_ns,
            current_observation_timestamp_ns=sim_time,
        )
        receipt = candidate.command_receipt
        if not isinstance(receipt, CommandReceiptSnapshot):
            raise TypeError("step requires a CommandReceiptSnapshot")
        if receipt.transition_identity != self._active_transition_identity:
            raise ValueError("command receipt transition identity does not match active step")
        if receipt.receipt_id in self._consumed_receipt_ids:
            raise ValueError("command receipt ID has already been committed")
        if candidate.transition_identity.transition_id in self._committed_transition_ids:
            raise ValueError("transition_id has already been committed")
        if not isinstance(candidate.committed_state, EpisodeLifecycleState) or candidate.committed_state not in (
            EpisodeLifecycleState.RUNNING,
            EpisodeLifecycleState.TERMINATED,
            EpisodeLifecycleState.TRUNCATED,
        ):
            raise ValueError("step commit state must be RUNNING, TERMINATED, or TRUNCATED")
        return candidate, progress

    def _abort_reset_locked(self, reason: str) -> EpisodeLifecycleResult:
        self._state = EpisodeLifecycleState.FAULT
        self._reset_in_progress = False
        self._step_in_progress = False
        self._clear_episode_facts()
        return self._result(EpisodeOperationStatus.RESET_ABORT, reason=str(reason))

    def _abort_step_locked(self, reason: str) -> EpisodeLifecycleResult:
        self._state = EpisodeLifecycleState.FAULT
        self._step_in_progress = False
        # Preserve the staged candidate as unconsumed diagnostic state.  The
        # next begin_reset clears it before any new observation can be built.
        return self._result(EpisodeOperationStatus.STEP_ABORT, reason=str(reason))

    def _clear_episode_facts(self) -> None:
        self._step_index = None
        self._pending_scenario_session_binding = None
        self._committed_scenario_session_binding = None
        self._reward_baseline = None
        self._reset_commit_facts = None
        self._previous_issued_command = None
        self._last_committed_command_receipt = None
        self._last_committed_goal_progress = None
        self._staged_contact_candidate = None
        self._consumed_contact_event_ids = ()
        self._consumed_receipt_ids = ()
        self._active_transition_identity = None
        self._committed_transition_ids = ()

    def _snapshot(self) -> EpisodeLifecycleSnapshot:
        return EpisodeLifecycleSnapshot(
            state=self._state,
            identity=self._identity,
            step_index=self._step_index,
            pending_scenario_session_binding=self._pending_scenario_session_binding,
            committed_scenario_session_binding=self._committed_scenario_session_binding,
            reward_baseline=self._reward_baseline,
            reset_commit_facts=self._reset_commit_facts,
            previous_issued_command=self._previous_issued_command,
            last_committed_command_receipt=self._last_committed_command_receipt,
            last_committed_goal_progress=self._last_committed_goal_progress,
            staged_contact_candidate=self._staged_contact_candidate,
            consumed_contact_event_ids=self._consumed_contact_event_ids,
            consumed_receipt_ids=self._consumed_receipt_ids,
            active_transition_identity=self._active_transition_identity,
            committed_transition_ids=self._committed_transition_ids,
            reset_in_progress=self._reset_in_progress,
            step_in_progress=self._step_in_progress,
        )

    def _result(
        self,
        status: EpisodeOperationStatus,
        reason: str | None = None,
        consumed_contact_event_id: str | None = None,
        goal_progress_input: GoalProgressInput | None = None,
    ) -> EpisodeLifecycleResult:
        return EpisodeLifecycleResult(
            status=status,
            snapshot=self._snapshot(),
            reason=reason,
            consumed_contact_event_id=consumed_contact_event_id,
            goal_progress_input=goal_progress_input,
        )


__all__ = (
    "CommandReceiptSnapshot",
    "CommittedRewardBaseline",
    "ContactCandidateSnapshot",
    "EpisodeLifecycle",
    "EpisodeLifecycleIdentity",
    "EpisodeLifecycleResult",
    "EpisodeLifecycleSnapshot",
    "EpisodeLifecycleState",
    "EpisodeOperationStatus",
    "ExactObservationProvenance",
    "GoalProgressInput",
    "LifecycleIdentityError",
    "LifecycleStateError",
    "ResetCommitCandidate",
    "ResetCommitFacts",
    "ScenarioSessionBinding",
    "StepCommitCandidate",
    "TransitionIdentity",
)
