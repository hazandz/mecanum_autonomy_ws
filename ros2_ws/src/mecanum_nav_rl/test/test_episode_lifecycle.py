"""Core-only tests for transactional episode reset/step lifecycle facts."""

from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pytest

from mecanum_nav_rl.core.episode_lifecycle import (
    CommandReceiptSnapshot,
    ContactCandidateSnapshot,
    EpisodeLifecycle,
    EpisodeLifecycleIdentity,
    EpisodeLifecycleState,
    EpisodeOperationStatus,
    ExactObservationProvenance,
    LifecycleIdentityError,
    LifecycleStateError,
    ResetCommitCandidate,
    StepCommitCandidate,
    TransitionIdentity,
)
from mecanum_nav_rl.observations.previous_command import PreviousNormalizedCommand
from mecanum_nav_rl.core.scenario_session import ScenarioSessionBinding
from mecanum_nav_rl.tasks.training_task_oracle import (
    GoalFactJoinMode,
    GoalFactProvenance,
    GoalOracleFact,
    TaskOracleResult,
    TaskOracleStatus,
)


def _identity(generation: int) -> EpisodeLifecycleIdentity:
    return EpisodeLifecycleIdentity(
        episode_generation=generation,
        reset_epoch=generation + 10,
        runtime_generation=4,
    )


def _provenance(identity: EpisodeLifecycleIdentity, timestamp_ns: int) -> ExactObservationProvenance:
    return ExactObservationProvenance(
        identity=identity,
        scan_timestamp_ns=timestamp_ns,
        odometry_timestamp_ns=timestamp_ns,
        observation_timestamp_ns=timestamp_ns,
    )


_SCENARIO_HASH = "a" * 64
_WORLD_HASH = "c" * 64


def _binding(
    identity: EpisodeLifecycleIdentity,
    *,
    scenario_id: str = "scenario-a",
    scenario_version: str = "1.0.0",
    scenario_hash: str = _SCENARIO_HASH,
    gazebo_world_name: str = "world_demo",
    world_file_sha256: str = _WORLD_HASH,
    coordinate_reference_id: str = "GT_ODOM_2D",
) -> ScenarioSessionBinding:
    return ScenarioSessionBinding(
        lifecycle_identity=identity,
        scenario_id=scenario_id,
        scenario_version=scenario_version,
        scenario_content_sha256=scenario_hash,
        gazebo_world_name=gazebo_world_name,
        world_file_sha256=world_file_sha256,
        coordinate_reference_id=coordinate_reference_id,
    )


def _goal_result(
    identity: EpisodeLifecycleIdentity,
    observation: ExactObservationProvenance,
    distance: object,
    *,
    mode: GoalFactJoinMode,
    transition_identity: TransitionIdentity | None = None,
    scenario_hash: str = _SCENARIO_HASH,
    binding: ScenarioSessionBinding | None = None,
) -> TaskOracleResult:
    if (
        isinstance(distance, bool)
        or not isinstance(distance, (int, float))
        or not __import__("math").isfinite(float(distance))
        or float(distance) < 0.0
    ):
        return TaskOracleResult(TaskOracleStatus.NUMERIC_DERIVATION_INVALID, None)
    provenance = GoalFactProvenance(
        join_mode=mode,
        scenario_session_binding=binding or _binding(identity, scenario_hash=scenario_hash),
        observation_provenance=observation,
        source_timestamp_ns=observation.observation_timestamp_ns,
        transition_identity=transition_identity,
    )
    return TaskOracleResult(
        TaskOracleStatus.READY,
        GoalOracleFact(
            goal_distance_m=float(distance),
            goal_reached=False,
            provenance=provenance,
        ),
    )


def _malformed_goal_fact(
    provenance: object,
    distance: object,
) -> GoalOracleFact:
    """Create a test-only invalid frozen fact for lifecycle-boundary coverage."""

    fact = object.__new__(GoalOracleFact)
    object.__setattr__(fact, "goal_distance_m", distance)
    object.__setattr__(fact, "goal_reached", False)
    object.__setattr__(fact, "provenance", provenance)
    return fact


def _malformed_goal_provenance(
    *,
    identity: object,
    observation: object,
    source_timestamp_ns: object,
    transition_identity: object | None = None,
) -> GoalFactProvenance:
    """Create test-only malformed provenance to exercise commit_reset."""

    provenance = object.__new__(GoalFactProvenance)
    object.__setattr__(provenance, "join_mode", GoalFactJoinMode.RESET_OBSERVATION0)
    session_identity = identity if isinstance(identity, EpisodeLifecycleIdentity) else _identity(0)
    object.__setattr__(provenance, "scenario_session_binding", _binding(session_identity))
    object.__setattr__(provenance, "observation_provenance", observation)
    object.__setattr__(provenance, "source_timestamp_ns", source_timestamp_ns)
    object.__setattr__(provenance, "transition_identity", transition_identity)
    return provenance


def _reset_candidate(
    identity: EpisodeLifecycleIdentity,
    *,
    distance: object = 2.5,
    sim_time_ns: object = 100,
    provenance: ExactObservationProvenance | None = None,
    previous_command: object | None = None,
    goal_result: object | None = None,
    binding: ScenarioSessionBinding | None = None,
) -> ResetCommitCandidate:
    observation = provenance or _provenance(identity, 100)
    if goal_result is None:
        if isinstance(sim_time_ns, bool) or not isinstance(sim_time_ns, int) or sim_time_ns < 0:
            goal_result = TaskOracleResult(TaskOracleStatus.INVALID_PROVENANCE, None)
        else:
            fact_observation = _provenance(identity, sim_time_ns)
            goal_result = _goal_result(
                identity, fact_observation, distance,
                mode=GoalFactJoinMode.RESET_OBSERVATION0,
                binding=binding or _binding(identity),
            )
    return ResetCommitCandidate(
        identity=identity,
        observation_provenance=observation,
        goal_result=goal_result,
        previous_issued_command=(
            previous_command
            if previous_command is not None
            else PreviousNormalizedCommand(0.0, 0.0, 0.0)
        ),
    )


def _commit_reset(
    lifecycle: EpisodeLifecycle,
    identity: EpisodeLifecycleIdentity,
    *,
    distance: object = 2.5,
    timestamp_ns: object = 100,
    provenance: ExactObservationProvenance | None = None,
) -> None:
    binding = _binding(identity)
    lifecycle.begin_reset(identity, binding)
    lifecycle.wait_for_initial_observation(identity)
    lifecycle.commit_reset(
        _reset_candidate(
            identity,
            binding=binding,
            distance=distance,
            sim_time_ns=timestamp_ns,
            provenance=provenance or _provenance(identity, 100),
        )
    )


def _begin_running_episode(
    generation: int = 0,
) -> tuple[EpisodeLifecycle, EpisodeLifecycleIdentity]:
    lifecycle = EpisodeLifecycle()
    identity = _identity(generation)
    _commit_reset(lifecycle, identity)
    return lifecycle, identity


def _transition(
    identity: EpisodeLifecycleIdentity,
    step_index: int = 1,
    transition_id: str | None = None,
) -> TransitionIdentity:
    return TransitionIdentity(
        identity,
        step_index,
        transition_id or f"transition-{identity.episode_generation}-{step_index}",
    )


def _begin_step(
    lifecycle: EpisodeLifecycle, identity: EpisodeLifecycleIdentity
) -> object:
    next_index = (lifecycle.snapshot.step_index or 0) + 1
    return lifecycle.begin_step(_transition(identity, next_index))


def _contact(lifecycle: EpisodeLifecycle, event_id: str) -> ContactCandidateSnapshot:
    active = lifecycle.snapshot.active_transition_identity
    assert active is not None
    return ContactCandidateSnapshot(active, event_id)


def _step_candidate(
    identity: EpisodeLifecycleIdentity,
    *,
    step_index: int = 1,
    timestamp_ns: int = 120,
    command: PreviousNormalizedCommand | None = None,
    committed_state: EpisodeLifecycleState = EpisodeLifecycleState.RUNNING,
    distance: object = 2.0,
    goal_result: object | None = None,
    observation: ExactObservationProvenance | None = None,
    scenario_hash: str = _SCENARIO_HASH,
    binding: ScenarioSessionBinding | None = None,
    transition_id: str | None = None,
) -> StepCommitCandidate:
    token = _transition(identity, step_index, transition_id)
    exact_observation = observation or _provenance(identity, timestamp_ns)
    result = goal_result or _goal_result(
        identity, exact_observation, distance,
        mode=GoalFactJoinMode.STEP_TRANSITION,
        transition_identity=token,
        scenario_hash=scenario_hash,
        binding=binding or _binding(identity, scenario_hash=scenario_hash),
    )
    return StepCommitCandidate(
        transition_identity=token,
        observation_provenance=exact_observation,
        goal_result=result,
        command_receipt=CommandReceiptSnapshot(
            transition_identity=token,
            receipt_id=f"receipt-{identity.episode_generation}-{step_index}",
            final_issued_command=command or PreviousNormalizedCommand(0.3, -0.2, 0.1),
        ),
        committed_state=committed_state,
    )


def test_initial_state_and_successful_reset_commit_baseline_before_first_step() -> None:
    lifecycle = EpisodeLifecycle()
    identity = _identity(0)

    assert lifecycle.snapshot.state is EpisodeLifecycleState.UNINITIALIZED
    assert lifecycle.snapshot.reward_baseline is None
    assert lifecycle.snapshot.previous_issued_command is None
    assert lifecycle.begin_reset(identity, _binding(identity)).status is EpisodeOperationStatus.RESET_STARTED
    assert lifecycle.snapshot.state is EpisodeLifecycleState.RESETTING
    assert lifecycle.snapshot.reward_baseline is None

    lifecycle.wait_for_initial_observation(identity)
    committed = lifecycle.commit_reset(_reset_candidate(identity))

    assert committed.status is EpisodeOperationStatus.RESET_COMMITTED
    assert committed.snapshot.state is EpisodeLifecycleState.RUNNING
    assert committed.snapshot.step_index == 0
    assert committed.snapshot.reset_commit_facts is not None
    assert committed.snapshot.reward_baseline is not None
    assert committed.snapshot.reward_baseline.previous_goal_distance_m == 2.5
    assert committed.snapshot.reward_baseline.previous_committed_sim_time_ns == 100
    assert committed.snapshot.previous_issued_command == PreviousNormalizedCommand(0.0, 0.0, 0.0)
    assert _begin_step(lifecycle, identity).status is EpisodeOperationStatus.STEP_STARTED


def test_invalid_reset_goal_fact_or_provenance_aborts_and_clears_state() -> None:
    invalid_cases = (
        ResetCommitCandidate(
            identity=_identity(0),
            observation_provenance=None,
            goal_result=TaskOracleResult(TaskOracleStatus.INVALID_PROVENANCE, None),
            previous_issued_command=PreviousNormalizedCommand(0.0, 0.0, 0.0),
        ),
        ResetCommitCandidate(
            identity=_identity(0),
            observation_provenance=ExactObservationProvenance(_identity(0), 100, 99, 100),
            goal_result=TaskOracleResult(TaskOracleStatus.INVALID_PROVENANCE, None),
            previous_issued_command=PreviousNormalizedCommand(0.0, 0.0, 0.0),
        ),
        _reset_candidate(
            _identity(0),
            goal_result=TaskOracleResult(TaskOracleStatus.NUMERIC_DERIVATION_INVALID, None),
        ),
        _reset_candidate(
            _identity(0),
            previous_command=PreviousNormalizedCommand(0.1, 0.0, 0.0),
        ),
    )
    for candidate in invalid_cases:
        lifecycle = EpisodeLifecycle()
        identity = _identity(0)
        lifecycle.begin_reset(identity, _binding(identity))
        lifecycle.wait_for_initial_observation(identity)
        result = lifecycle.commit_reset(candidate)
        assert result.status is EpisodeOperationStatus.RESET_ABORT
        assert result.snapshot.state is EpisodeLifecycleState.FAULT
        assert result.snapshot.reward_baseline is None
        assert result.snapshot.reset_commit_facts is None
        assert result.snapshot.previous_issued_command is None
        assert result.snapshot.step_index is None
        with pytest.raises(LifecycleStateError):
            _begin_step(lifecycle, identity)


@pytest.mark.parametrize(
    "case",
    (
        "missing_observation_provenance",
        "goal_result_wrong_type",
        "goal_result_non_ready",
        "ready_result_without_fact",
        "distance_none",
        "distance_bool",
        "distance_nan",
        "distance_positive_infinity",
        "distance_negative_infinity",
        "distance_negative_finite",
        "timestamp_none",
        "timestamp_nan",
        "timestamp_bool",
        "timestamp_negative",
        "timestamp_mismatch",
        "inexact_scan_odom_observation",
        "lifecycle_identity_mismatch",
        "candidate_identity_mismatch",
        "reset_fact_with_transition_token",
        "nonzero_previous_issued_command",
    ),
)
def test_reset_fail_closed_boundary_preserves_no_partial_candidate_state(case: str) -> None:
    """Exercise legacy reset failure classes through commit_reset, not constructors."""

    identity = _identity(0)
    observation: ExactObservationProvenance | None = _provenance(identity, 100)
    goal_result: object = _goal_result(
        identity,
        observation,
        2.5,
        mode=GoalFactJoinMode.RESET_OBSERVATION0,
    )
    previous_command: object = PreviousNormalizedCommand(0.0, 0.0, 0.0)
    candidate_identity = identity

    if case == "missing_observation_provenance":
        observation = None
    elif case == "goal_result_wrong_type":
        goal_result = "not-a-task-oracle-result"
    elif case == "goal_result_non_ready":
        goal_result = TaskOracleResult(TaskOracleStatus.INVALID_PROVENANCE, None)
    elif case == "ready_result_without_fact":
        goal_result = object.__new__(TaskOracleResult)
        object.__setattr__(goal_result, "status", TaskOracleStatus.READY)
        object.__setattr__(goal_result, "fact", None)
    elif case in {
        "distance_none",
        "distance_bool",
        "distance_nan",
        "distance_positive_infinity",
        "distance_negative_infinity",
        "distance_negative_finite",
    }:
        invalid_distance = {
            "distance_none": None,
            "distance_bool": True,
            "distance_nan": float("nan"),
            "distance_positive_infinity": float("inf"),
            "distance_negative_infinity": float("-inf"),
            "distance_negative_finite": -0.1,
        }[case]
        goal_result = TaskOracleResult(
            TaskOracleStatus.READY,
            _malformed_goal_fact(goal_result.fact.provenance, invalid_distance),
        )
    elif case in {"timestamp_none", "timestamp_nan", "timestamp_bool", "timestamp_negative", "timestamp_mismatch"}:
        invalid_timestamp = {
            "timestamp_none": None,
            "timestamp_nan": float("nan"),
            "timestamp_bool": True,
            "timestamp_negative": -1,
            "timestamp_mismatch": 99,
        }[case]
        malformed = _malformed_goal_provenance(
            identity=identity,
            observation=observation,
            source_timestamp_ns=invalid_timestamp,
        )
        goal_result = TaskOracleResult(
            TaskOracleStatus.READY,
            _malformed_goal_fact(malformed, 2.5),
        )
    elif case == "inexact_scan_odom_observation":
        observation = ExactObservationProvenance(identity, 100, 99, 100)
        malformed = _malformed_goal_provenance(
            identity=identity,
            observation=observation,
            source_timestamp_ns=100,
        )
        goal_result = TaskOracleResult(
            TaskOracleStatus.READY,
            _malformed_goal_fact(malformed, 2.5),
        )
    elif case == "lifecycle_identity_mismatch":
        other_identity = _identity(1)
        other_observation = _provenance(other_identity, 100)
        goal_result = _goal_result(
            other_identity,
            other_observation,
            2.5,
            mode=GoalFactJoinMode.RESET_OBSERVATION0,
        )
    elif case == "candidate_identity_mismatch":
        candidate_identity = _identity(1)
    elif case == "reset_fact_with_transition_token":
        malformed = _malformed_goal_provenance(
            identity=identity,
            observation=observation,
            source_timestamp_ns=100,
            transition_identity=_transition(identity, 1, "illegal-reset-token"),
        )
        goal_result = TaskOracleResult(
            TaskOracleStatus.READY,
            _malformed_goal_fact(malformed, 2.5),
        )
    elif case == "nonzero_previous_issued_command":
        previous_command = PreviousNormalizedCommand(0.1, 0.0, 0.0)
    else:
        raise AssertionError(f"unhandled case: {case}")

    lifecycle = EpisodeLifecycle()
    lifecycle.begin_reset(identity, _binding(identity))
    lifecycle.wait_for_initial_observation(identity)
    result = lifecycle.commit_reset(
        ResetCommitCandidate(
            identity=candidate_identity,
            observation_provenance=observation,
            goal_result=goal_result,
            previous_issued_command=previous_command,
        )
    )

    snapshot = result.snapshot
    assert result.status is EpisodeOperationStatus.RESET_ABORT
    assert snapshot.state is EpisodeLifecycleState.FAULT
    assert snapshot.reward_baseline is None
    assert snapshot.reset_commit_facts is None
    assert snapshot.previous_issued_command is None
    assert snapshot.step_index is None
    assert snapshot.last_committed_goal_progress is None
    assert snapshot.staged_contact_candidate is None
    assert snapshot.last_committed_command_receipt is None
    assert snapshot.consumed_contact_event_ids == ()
    assert snapshot.consumed_receipt_ids == ()
    assert snapshot.committed_transition_ids == ()
    assert snapshot.active_transition_identity is None


def test_reset_two_times_clears_previous_baseline_history_and_contact() -> None:
    lifecycle, first = _begin_running_episode(0)
    _begin_step(lifecycle, first)
    lifecycle.stage_contact_candidate(_contact(lifecycle, "contact-old"))
    first_step = lifecycle.commit_step(
        _step_candidate(
            first,
            command=PreviousNormalizedCommand(0.7, -0.4, 0.2),
        )
    )
    assert first_step.snapshot.consumed_contact_event_ids == ("contact-old",)
    assert first_step.snapshot.previous_issued_command == PreviousNormalizedCommand(0.7, -0.4, 0.2)
    assert first_step.snapshot.last_committed_command_receipt is not None
    assert first_step.snapshot.last_committed_command_receipt.receipt_id == "receipt-0-1"

    second = _identity(1)
    lifecycle.begin_reset(second, _binding(second))
    during_second_reset = lifecycle.snapshot
    assert during_second_reset.reward_baseline is None
    assert during_second_reset.previous_issued_command is None
    assert during_second_reset.last_committed_command_receipt is None
    assert during_second_reset.staged_contact_candidate is None
    assert during_second_reset.consumed_contact_event_ids == ()
    lifecycle.wait_for_initial_observation(second)
    second_result = lifecycle.commit_reset(
        _reset_candidate(second, distance=9.0, sim_time_ns=200, provenance=_provenance(second, 200))
    )
    assert second_result.snapshot.reward_baseline is not None
    assert second_result.snapshot.reward_baseline.previous_goal_distance_m == 9.0
    assert second_result.snapshot.previous_issued_command == PreviousNormalizedCommand(0.0, 0.0, 0.0)

    third = _identity(2)
    lifecycle.begin_reset(third, _binding(third))
    assert lifecycle.snapshot.reward_baseline is None
    assert lifecycle.snapshot.previous_issued_command is None
    assert lifecycle.snapshot.consumed_contact_event_ids == ()
    lifecycle.wait_for_initial_observation(third)
    third_result = lifecycle.commit_reset(
        _reset_candidate(third, distance=4.0, sim_time_ns=300, provenance=_provenance(third, 300))
    )
    assert third_result.snapshot.reward_baseline is not None
    assert third_result.snapshot.reward_baseline.previous_goal_distance_m == 4.0
    assert third_result.snapshot.reward_baseline.previous_committed_sim_time_ns == 300
    assert third_result.snapshot.previous_issued_command == PreviousNormalizedCommand(0.0, 0.0, 0.0)


def test_failed_repeated_reset_clears_all_prior_committed_episode_facts() -> None:
    lifecycle, first = _begin_running_episode()
    _begin_step(lifecycle, first)
    lifecycle.stage_contact_candidate(_contact(lifecycle, "prior-contact"))
    lifecycle.commit_step(_step_candidate(first))
    assert lifecycle.snapshot.last_committed_command_receipt is not None

    next_identity = _identity(1)
    lifecycle.begin_reset(next_identity, _binding(next_identity))
    assert lifecycle.snapshot.reward_baseline is None
    assert lifecycle.snapshot.previous_issued_command is None
    assert lifecycle.snapshot.last_committed_command_receipt is None
    assert lifecycle.snapshot.staged_contact_candidate is None
    assert lifecycle.snapshot.consumed_contact_event_ids == ()
    lifecycle.wait_for_initial_observation(next_identity)
    aborted = lifecycle.commit_reset(
        _reset_candidate(
            next_identity,
            distance=float("nan"),
            sim_time_ns=200,
            provenance=_provenance(next_identity, 200),
        )
    )

    assert aborted.status is EpisodeOperationStatus.RESET_ABORT
    assert aborted.snapshot.state is EpisodeLifecycleState.FAULT
    assert aborted.snapshot.reward_baseline is None
    assert aborted.snapshot.reset_commit_facts is None
    assert aborted.snapshot.previous_issued_command is None
    assert aborted.snapshot.last_committed_command_receipt is None
    assert aborted.snapshot.staged_contact_candidate is None
    assert aborted.snapshot.consumed_contact_event_ids == ()
    assert aborted.snapshot.step_index is None


def test_begin_step_before_reset_or_without_committed_baseline_is_rejected() -> None:
    lifecycle = EpisodeLifecycle()
    with pytest.raises(LifecycleIdentityError, match="no active lifecycle"):
        _begin_step(lifecycle, _identity(0))

    identity = _identity(0)
    lifecycle.begin_reset(identity, _binding(identity))
    with pytest.raises(LifecycleStateError, match="requires RUNNING"):
        _begin_step(lifecycle, identity)
    lifecycle.wait_for_initial_observation(identity)
    lifecycle.abort_reset("missing baseline")
    with pytest.raises(LifecycleStateError):
        _begin_step(lifecycle, identity)


def test_staged_contact_is_not_consumed_until_successful_atomic_commit() -> None:
    lifecycle, identity = _begin_running_episode()
    _begin_step(lifecycle, identity)
    staged = lifecycle.stage_contact_candidate(_contact(lifecycle, "event-1"))
    assert staged.status is EpisodeOperationStatus.CONTACT_STAGED
    assert staged.snapshot.staged_contact_candidate is not None
    assert staged.snapshot.consumed_contact_event_ids == ()

    committed = lifecycle.commit_step(_step_candidate(identity))
    assert committed.status is EpisodeOperationStatus.STEP_COMMITTED
    assert committed.consumed_contact_event_id == "event-1"
    assert committed.snapshot.staged_contact_candidate is None
    assert committed.snapshot.consumed_contact_event_ids == ("event-1",)
    assert committed.snapshot.consumed_contact_event_ids.count("event-1") == 1
    assert committed.snapshot.step_index == 1


def test_step_abort_does_not_consume_contact_or_advance_committed_state() -> None:
    lifecycle, identity = _begin_running_episode()
    before = lifecycle.snapshot
    _begin_step(lifecycle, identity)
    active_step = lifecycle.snapshot
    with pytest.raises(LifecycleStateError, match="cannot overlap"):
        lifecycle.begin_reset(_identity(1), _binding(_identity(1)))
    assert lifecycle.snapshot == active_step
    lifecycle.stage_contact_candidate(_contact(lifecycle, "pending-event"))

    aborted = lifecycle.abort_step("post-issue sensor/observation failure")

    assert aborted.status is EpisodeOperationStatus.STEP_ABORT
    assert aborted.snapshot.state is EpisodeLifecycleState.FAULT
    assert aborted.snapshot.step_index == before.step_index == 0
    assert aborted.snapshot.reward_baseline == before.reward_baseline
    assert aborted.snapshot.previous_issued_command == before.previous_issued_command
    assert aborted.snapshot.staged_contact_candidate is not None
    assert aborted.snapshot.staged_contact_candidate.event_id == "pending-event"
    assert aborted.snapshot.consumed_contact_event_ids == ()

    next_identity = _identity(1)
    lifecycle.begin_reset(next_identity, _binding(next_identity))
    assert lifecycle.snapshot.staged_contact_candidate is None
    assert lifecycle.snapshot.reward_baseline is None
    assert lifecycle.snapshot.previous_issued_command is None
    lifecycle.wait_for_initial_observation(next_identity)
    reset = lifecycle.commit_reset(
        _reset_candidate(next_identity, distance=3.0, sim_time_ns=200, provenance=_provenance(next_identity, 200))
    )
    assert reset.snapshot.consumed_contact_event_ids == ()
    assert reset.snapshot.reward_baseline is not None
    assert reset.snapshot.reward_baseline.previous_goal_distance_m == 3.0


@pytest.mark.parametrize("generation,relation", [(0, "stale"), (2, "future")])
def test_stale_and_future_generation_are_rejected_without_mutation(
    generation: int, relation: str
) -> None:
    lifecycle, active = _begin_running_episode(1)
    before = lifecycle.snapshot

    with pytest.raises(LifecycleIdentityError) as error:
        _begin_step(lifecycle, _identity(generation))

    assert error.value.relation == relation
    assert lifecycle.snapshot == before


@pytest.mark.parametrize(
    "values",
    [
        (True, 1, 1),
        (-1, 1, 1),
        (1.0, 1, 1),
    ],
)
def test_lifecycle_identity_rejects_bool_negative_and_non_integer(values: tuple[object, ...]) -> None:
    with pytest.raises((TypeError, ValueError)):
        EpisodeLifecycleIdentity(*values)


def test_snapshot_and_facts_are_immutable() -> None:
    lifecycle, _ = _begin_running_episode()
    snapshot = lifecycle.snapshot
    assert snapshot.reset_commit_facts is not None
    with pytest.raises(FrozenInstanceError):
        snapshot.state = EpisodeLifecycleState.FAULT  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        snapshot.reset_commit_facts.previous_goal_distance_m = 0.0  # type: ignore[misc]



def _committed_state(snapshot: object) -> tuple[object, ...]:
    """Compare only committed facts; FAULT/transaction flags may change on abort."""

    return (
        snapshot.step_index,
        snapshot.reward_baseline,
        snapshot.previous_issued_command,
        snapshot.last_committed_command_receipt,
        snapshot.consumed_receipt_ids,
        snapshot.consumed_contact_event_ids,
        snapshot.committed_transition_ids,
    )


@pytest.mark.parametrize(
    "terminal_state",
    [EpisodeLifecycleState.TERMINATED, EpisodeLifecycleState.TRUNCATED],
)
def test_terminal_commit_blocks_step_and_new_generation_clears_facts(
    terminal_state: EpisodeLifecycleState,
) -> None:
    lifecycle, identity = _begin_running_episode()
    _begin_step(lifecycle, identity)
    lifecycle.stage_contact_candidate(_contact(lifecycle, "terminal-contact"))
    command = PreviousNormalizedCommand(0.4, -0.1, 0.2)
    candidate = _step_candidate(identity, command=command, committed_state=terminal_state)

    result = lifecycle.commit_step(candidate)

    assert result.status is EpisodeOperationStatus.STEP_COMMITTED
    assert result.snapshot.state is terminal_state
    assert result.snapshot.step_index == 1
    assert result.snapshot.reward_baseline is not None
    assert result.snapshot.reward_baseline.previous_goal_distance_m == 2.0
    assert result.snapshot.reward_baseline.previous_committed_sim_time_ns == 120
    assert result.snapshot.previous_issued_command == command
    assert result.snapshot.last_committed_command_receipt == candidate.command_receipt
    assert result.snapshot.consumed_receipt_ids == (candidate.command_receipt.receipt_id,)
    assert result.snapshot.consumed_contact_event_ids == ("terminal-contact",)
    assert result.consumed_contact_event_id == "terminal-contact"
    assert result.snapshot.staged_contact_candidate is None
    terminal_snapshot = lifecycle.snapshot
    with pytest.raises(LifecycleStateError, match="requires RUNNING"):
        _begin_step(lifecycle, identity)
    assert lifecycle.snapshot == terminal_snapshot

    next_identity = _identity(1)
    reset = lifecycle.begin_reset(next_identity, _binding(next_identity))
    assert reset.status is EpisodeOperationStatus.RESET_STARTED
    assert reset.snapshot.state is EpisodeLifecycleState.RESETTING
    assert reset.snapshot.identity == next_identity
    assert reset.snapshot.step_index is None
    assert reset.snapshot.reward_baseline is None
    assert reset.snapshot.previous_issued_command is None
    assert reset.snapshot.last_committed_command_receipt is None
    assert reset.snapshot.staged_contact_candidate is None
    assert reset.snapshot.consumed_receipt_ids == ()
    assert reset.snapshot.consumed_contact_event_ids == ()


@pytest.mark.parametrize("mismatch", ["lifecycle", "step_index"])
def test_mismatched_receipt_aborts_without_advancing_committed_facts(mismatch: str) -> None:
    lifecycle, identity = _begin_running_episode()
    _begin_step(lifecycle, identity)
    first = lifecycle.commit_step(_step_candidate(identity))
    assert first.status is EpisodeOperationStatus.STEP_COMMITTED
    before = lifecycle.snapshot
    _begin_step(lifecycle, identity)
    candidate = _step_candidate(identity, step_index=2, timestamp_ns=140)
    receipt = candidate.command_receipt
    if mismatch == "lifecycle":
        receipt = replace(receipt, transition_identity=_transition(_identity(1), 2))
    else:
        receipt = replace(receipt, transition_identity=_transition(identity, 1))
    candidate = replace(candidate, command_receipt=receipt)

    aborted = lifecycle.commit_step(candidate)

    assert aborted.status is EpisodeOperationStatus.STEP_ABORT
    assert aborted.snapshot.state is EpisodeLifecycleState.FAULT
    assert _committed_state(aborted.snapshot) == _committed_state(before)
    assert candidate.command_receipt.receipt_id not in aborted.snapshot.consumed_receipt_ids


def test_committed_receipt_id_cannot_be_reused_on_a_later_step() -> None:
    lifecycle, identity = _begin_running_episode()
    _begin_step(lifecycle, identity)
    first = lifecycle.commit_step(_step_candidate(identity))
    assert first.snapshot.consumed_receipt_ids == ("receipt-0-1",)
    before = lifecycle.snapshot
    _begin_step(lifecycle, identity)
    candidate = _step_candidate(identity, step_index=2, timestamp_ns=140)
    reused = replace(candidate.command_receipt, receipt_id="receipt-0-1")

    aborted = lifecycle.commit_step(replace(candidate, command_receipt=reused))

    assert aborted.status is EpisodeOperationStatus.STEP_ABORT
    assert aborted.snapshot.state is EpisodeLifecycleState.FAULT
    assert _committed_state(aborted.snapshot) == _committed_state(before)
    assert aborted.snapshot.consumed_receipt_ids == ("receipt-0-1",)


def test_failed_commit_and_explicit_abort_do_not_consume_receipt_ids() -> None:
    lifecycle, identity = _begin_running_episode()
    before = lifecycle.snapshot
    _begin_step(lifecycle, identity)
    candidate = _step_candidate(identity)
    invalid = _step_candidate(
        identity,
        goal_result=_goal_result(
            identity, _provenance(identity, 119), 2.0,
            mode=GoalFactJoinMode.STEP_TRANSITION,
            transition_identity=_transition(identity, 1),
        ),
    )

    aborted = lifecycle.commit_step(invalid)

    assert aborted.status is EpisodeOperationStatus.STEP_ABORT
    assert _committed_state(aborted.snapshot) == _committed_state(before)
    assert aborted.snapshot.consumed_receipt_ids == ()
    next_identity = _identity(1)
    _commit_reset(lifecycle, next_identity)
    before_explicit_abort = lifecycle.snapshot
    _begin_step(lifecycle, next_identity)
    explicit_abort = lifecycle.abort_step("pre-commit failure")
    assert explicit_abort.status is EpisodeOperationStatus.STEP_ABORT
    assert _committed_state(explicit_abort.snapshot) == _committed_state(before_explicit_abort)
    assert explicit_abort.snapshot.consumed_receipt_ids == ()


def test_consumed_contact_cannot_be_restaged_in_same_episode() -> None:
    lifecycle, identity = _begin_running_episode()
    _begin_step(lifecycle, identity)
    lifecycle.stage_contact_candidate(_contact(lifecycle, "contact-1"))
    committed = lifecycle.commit_step(_step_candidate(identity))
    assert committed.snapshot.consumed_contact_event_ids == ("contact-1",)
    _begin_step(lifecycle, identity)
    before_reject = lifecycle.snapshot

    with pytest.raises(LifecycleStateError, match="already been consumed"):
        lifecycle.stage_contact_candidate(_contact(lifecycle, "contact-1"))

    assert lifecycle.snapshot == before_reject
    assert _committed_state(lifecycle.snapshot) == _committed_state(committed.snapshot)


def test_duplicate_staged_contact_is_rejected_and_invalid_commit_does_not_consume() -> None:
    lifecycle, identity = _begin_running_episode()
    before = lifecycle.snapshot
    _begin_step(lifecycle, identity)
    contact = _contact(lifecycle, "pending-contact")
    lifecycle.stage_contact_candidate(contact)
    staged = lifecycle.snapshot

    with pytest.raises(LifecycleStateError, match="already staged"):
        lifecycle.stage_contact_candidate(contact)
    assert lifecycle.snapshot == staged

    candidate = _step_candidate(identity)
    invalid = replace(
        candidate,
        command_receipt=replace(
            candidate.command_receipt,
            transition_identity=_transition(identity, 2),
        ),
    )
    aborted = lifecycle.commit_step(invalid)
    assert aborted.status is EpisodeOperationStatus.STEP_ABORT
    assert aborted.snapshot.state is EpisodeLifecycleState.FAULT
    assert aborted.snapshot.staged_contact_candidate == contact
    assert _committed_state(aborted.snapshot) == _committed_state(before)
    assert aborted.snapshot.consumed_contact_event_ids == ()
    assert aborted.snapshot.consumed_receipt_ids == ()

    next_identity = _identity(1)
    reset = lifecycle.begin_reset(next_identity, _binding(next_identity))
    assert reset.snapshot.staged_contact_candidate is None
    assert reset.snapshot.consumed_contact_event_ids == ()
    assert reset.snapshot.consumed_receipt_ids == ()



@pytest.mark.parametrize("bad_step_index", [True, -1, 0, 1.0, float("nan"), "1"])
def test_transition_identity_rejects_invalid_step_index(bad_step_index: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        TransitionIdentity(_identity(0), bad_step_index, "caller-token")


@pytest.mark.parametrize("bad_token", [None, True, 42, float("nan"), "", "   "])
def test_transition_identity_rejects_invalid_token(bad_token: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        TransitionIdentity(_identity(0), 1, bad_token)


def test_one_token_joins_receipt_contact_and_successful_commit_once() -> None:
    lifecycle, identity = _begin_running_episode()
    token = _transition(identity, 1, "caller-issued-token")
    started = lifecycle.begin_step(token)
    assert started.snapshot.active_transition_identity == token
    contact = ContactCandidateSnapshot(token, "contact-for-token")
    receipt = CommandReceiptSnapshot(
        token, "receipt-for-token", PreviousNormalizedCommand(0.2, -0.1, 0.3)
    )
    candidate = replace(
        _step_candidate(identity, transition_id="caller-issued-token"),
        command_receipt=receipt,
    )
    staged = lifecycle.stage_contact_candidate(contact)
    assert staged.snapshot.consumed_contact_event_ids == ()
    assert staged.snapshot.consumed_receipt_ids == ()
    assert staged.snapshot.committed_transition_ids == ()

    committed = lifecycle.commit_step(candidate)

    assert committed.status is EpisodeOperationStatus.STEP_COMMITTED
    assert committed.snapshot.last_committed_command_receipt == receipt
    assert committed.snapshot.consumed_receipt_ids == ("receipt-for-token",)
    assert committed.snapshot.consumed_contact_event_ids == ("contact-for-token",)
    assert committed.snapshot.committed_transition_ids == ("caller-issued-token",)
    assert committed.snapshot.active_transition_identity is None
    assert committed.consumed_contact_event_id == "contact-for-token"
    before_replay = lifecycle.snapshot
    with pytest.raises(LifecycleStateError, match="active RUNNING step"):
        lifecycle.commit_step(candidate)
    assert lifecycle.snapshot == before_replay


def test_receipt_token_mismatch_in_same_lifecycle_and_step_aborts() -> None:
    lifecycle, identity = _begin_running_episode()
    active = _transition(identity, 1, "active-token")
    lifecycle.begin_step(active)
    before = lifecycle.snapshot
    candidate = _step_candidate(identity)
    wrong_receipt = replace(
        candidate.command_receipt,
        transition_identity=_transition(identity, 1, "different-token"),
    )
    candidate = replace(
        candidate, transition_identity=active, command_receipt=wrong_receipt
    )

    aborted = lifecycle.commit_step(candidate)

    assert aborted.status is EpisodeOperationStatus.STEP_ABORT
    assert aborted.snapshot.state is EpisodeLifecycleState.FAULT
    assert _committed_state(aborted.snapshot) == _committed_state(before)
    assert aborted.snapshot.consumed_receipt_ids == ()
    assert aborted.snapshot.committed_transition_ids == ()


@pytest.mark.parametrize("token_kind", ["same_step_other", "stale", "future", "wrong_lifecycle"])
def test_contact_token_mismatch_aborts_without_consuming(token_kind: str) -> None:
    lifecycle, identity = _begin_running_episode()
    if token_kind == "stale":
        lifecycle.begin_step(_transition(identity, 1, "prior-token"))
        lifecycle.commit_step(
            _step_candidate(identity, transition_id="prior-token")
        )
        active = _transition(identity, 2, "active-token")
        wrong = _transition(identity, 1, "prior-token")
    else:
        active = _transition(identity, 1, "active-token")
        wrong = {
            "same_step_other": _transition(identity, 1, "other-token"),
            "future": _transition(identity, 3, "future-token"),
            "wrong_lifecycle": _transition(_identity(1), 1, "other-episode"),
        }[token_kind]
    lifecycle.begin_step(active)
    before = lifecycle.snapshot
    result = lifecycle.stage_contact_candidate(ContactCandidateSnapshot(wrong, "event"))

    assert result.status is EpisodeOperationStatus.STEP_ABORT
    assert result.snapshot.state is EpisodeLifecycleState.FAULT
    assert result.snapshot.staged_contact_candidate is None
    assert _committed_state(result.snapshot) == _committed_state(before)
    assert result.snapshot.consumed_contact_event_ids == before.consumed_contact_event_ids
    assert result.snapshot.consumed_receipt_ids == before.consumed_receipt_ids


@pytest.mark.parametrize("token_kind", ["same_step_other", "stale", "future"])
def test_candidate_token_mismatch_aborts_without_advancing(token_kind: str) -> None:
    lifecycle, identity = _begin_running_episode()
    if token_kind == "stale":
        prior = _transition(identity, 1, "prior-token")
        lifecycle.begin_step(prior)
        prior_candidate = _step_candidate(identity)
        lifecycle.commit_step(
            _step_candidate(identity, transition_id="prior-token")
        )
        active = _transition(identity, 2, "active-token")
        wrong = prior
    else:
        active = _transition(identity, 1, "active-token")
        wrong = {
            "same_step_other": _transition(identity, 1, "other-token"),
            "future": _transition(identity, 3, "future-token"),
        }[token_kind]
    lifecycle.begin_step(active)
    before = lifecycle.snapshot
    step_index = active.step_index
    candidate = _step_candidate(identity, step_index=step_index, timestamp_ns=100 + 20 * step_index)
    candidate = replace(candidate, transition_identity=wrong)

    result = lifecycle.commit_step(candidate)

    assert result.status is EpisodeOperationStatus.STEP_ABORT
    assert result.snapshot.state is EpisodeLifecycleState.FAULT
    assert _committed_state(result.snapshot) == _committed_state(before)
    assert result.snapshot.consumed_receipt_ids == before.consumed_receipt_ids
    assert result.snapshot.committed_transition_ids == before.committed_transition_ids


@pytest.mark.parametrize(
    ("next_index", "token_id", "relation"),
    [(1, "old-step", "stale"), (3, "future-step", "future"), (2, "used-token", "stale")],
)
def test_stale_future_and_replayed_begin_step_token_are_rejected_without_mutation(
    next_index: int, token_id: str, relation: str
) -> None:
    lifecycle, identity = _begin_running_episode()
    used = _transition(identity, 1, "used-token")
    lifecycle.begin_step(used)
    candidate = _step_candidate(identity, transition_id="used-token")
    lifecycle.commit_step(candidate)
    before = lifecycle.snapshot

    with pytest.raises(LifecycleIdentityError) as error:
        lifecycle.begin_step(_transition(identity, next_index, token_id))

    assert error.value.relation == relation
    assert lifecycle.snapshot == before


def test_abort_and_new_reset_clear_old_transition_and_fact_state() -> None:
    lifecycle, identity = _begin_running_episode()
    old = _transition(identity, 1, "reusable-after-reset")
    lifecycle.begin_step(old)
    lifecycle.stage_contact_candidate(ContactCandidateSnapshot(old, "pending-event"))
    candidate = _step_candidate(identity)
    wrong_receipt = replace(
        candidate.command_receipt,
        transition_identity=_transition(identity, 1, "wrong-token"),
    )
    aborted = lifecycle.commit_step(
        replace(candidate, transition_identity=old, command_receipt=wrong_receipt)
    )
    assert aborted.status is EpisodeOperationStatus.STEP_ABORT
    assert aborted.snapshot.active_transition_identity == old
    assert aborted.snapshot.staged_contact_candidate is not None
    assert aborted.snapshot.committed_transition_ids == ()
    assert aborted.snapshot.consumed_receipt_ids == ()
    assert aborted.snapshot.consumed_contact_event_ids == ()

    next_identity = _identity(1)
    reset = lifecycle.begin_reset(next_identity, _binding(next_identity))
    assert reset.snapshot.active_transition_identity is None
    assert reset.snapshot.staged_contact_candidate is None
    assert reset.snapshot.committed_transition_ids == ()
    assert reset.snapshot.consumed_receipt_ids == ()
    assert reset.snapshot.consumed_contact_event_ids == ()
    lifecycle.wait_for_initial_observation(next_identity)
    lifecycle.commit_reset(
        _reset_candidate(
            next_identity,
            distance=3.0,
            sim_time_ns=200,
            provenance=_provenance(next_identity, 200),
        )
    )
    new_token = _transition(next_identity, 1, "reusable-after-reset")
    started = lifecycle.begin_step(new_token)
    assert started.snapshot.active_transition_identity == new_token
    assert started.snapshot.staged_contact_candidate is None


def test_terminal_commit_with_token_still_blocks_next_step() -> None:
    lifecycle, identity = _begin_running_episode()
    token = _transition(identity, 1, "terminal-token")
    lifecycle.begin_step(token)
    candidate = _step_candidate(
        identity,
        transition_id="terminal-token",
        committed_state=EpisodeLifecycleState.TERMINATED,
    )
    committed = lifecycle.commit_step(candidate)
    assert committed.snapshot.state is EpisodeLifecycleState.TERMINATED
    assert committed.snapshot.committed_transition_ids == ("terminal-token",)
    before = lifecycle.snapshot

    with pytest.raises(LifecycleStateError, match="requires RUNNING"):
        lifecycle.begin_step(_transition(identity, 2))
    assert lifecycle.snapshot == before


def test_reset_requires_observation0_goal_fact_without_transition_token() -> None:
    lifecycle = EpisodeLifecycle()
    identity = _identity(0)
    observation = _provenance(identity, 100)
    lifecycle.begin_reset(identity, _binding(identity))
    lifecycle.wait_for_initial_observation(identity)
    step_fact = _goal_result(
        identity,
        observation,
        2.5,
        mode=GoalFactJoinMode.STEP_TRANSITION,
        transition_identity=_transition(identity, 1, "must-not-be-reset-token"),
    )
    result = lifecycle.commit_reset(
        ResetCommitCandidate(
            identity=identity,
            observation_provenance=observation,
            goal_result=step_fact,
            previous_issued_command=PreviousNormalizedCommand(0.0, 0.0, 0.0),
        )
    )
    assert result.status is EpisodeOperationStatus.RESET_ABORT
    assert result.snapshot.reward_baseline is None
    assert result.snapshot.step_index is None


def test_goal_progress_is_commit_bound_and_contains_no_pose_or_artifact() -> None:
    lifecycle, identity = _begin_running_episode()
    token = _transition(identity, 1, "goal-progress-token")
    lifecycle.begin_step(token)
    committed = lifecycle.commit_step(
        _step_candidate(
            identity,
            transition_id="goal-progress-token",
            timestamp_ns=120,
            distance=2.0,
        )
    )
    progress = committed.goal_progress_input
    assert committed.status is EpisodeOperationStatus.STEP_COMMITTED
    assert progress is not None
    assert progress.delta_d == pytest.approx(0.5)
    assert progress.transition_identity == token
    assert progress.scenario_content_sha256 == _SCENARIO_HASH
    assert committed.snapshot.reward_baseline is not None
    assert committed.snapshot.reward_baseline.previous_goal_distance_m == 2.0
    assert committed.snapshot.reward_baseline.previous_committed_sim_time_ns == 120
    assert committed.snapshot.last_committed_goal_progress == progress
    for forbidden_field in ("x_m", "y_m", "yaw_rad", "artifact", "ground_truth"):
        assert not hasattr(progress, forbidden_field)


def test_step_goal_fact_mismatches_abort_without_advancing_committed_baseline() -> None:
    for kind in ("token", "observation", "timestamp", "hash"):
        lifecycle, identity = _begin_running_episode()
        active = _transition(identity, 1, "active-token")
        lifecycle.begin_step(active)
        observation = _provenance(identity, 120)
        if kind == "token":
            fact_observation = observation
            fact_token = _transition(identity, 1, "other-token")
            scenario_hash = _SCENARIO_HASH
        elif kind in ("observation", "timestamp"):
            fact_observation = _provenance(identity, 121)
            fact_token = active
            scenario_hash = _SCENARIO_HASH
        else:
            fact_observation = observation
            fact_token = active
            scenario_hash = "b" * 64
        fact_result = _goal_result(
            identity, fact_observation, 2.0,
            mode=GoalFactJoinMode.STEP_TRANSITION,
            transition_identity=fact_token,
            scenario_hash=scenario_hash,
        )
        candidate = _step_candidate(
            identity,
            transition_id="active-token",
            observation=observation,
            goal_result=fact_result,
        )
        before = lifecycle.snapshot
        aborted = lifecycle.commit_step(candidate)
        assert aborted.status is EpisodeOperationStatus.STEP_ABORT
        assert aborted.snapshot.step_index == before.step_index == 0
        assert aborted.snapshot.reward_baseline == before.reward_baseline
        assert aborted.snapshot.last_committed_goal_progress is None


def test_new_reset_generation_clears_goal_progress_and_prior_hash() -> None:
    lifecycle, identity = _begin_running_episode()
    lifecycle.begin_step(_transition(identity, 1))
    lifecycle.commit_step(_step_candidate(identity))
    assert lifecycle.snapshot.last_committed_goal_progress is not None
    next_identity = _identity(1)
    reset_started = lifecycle.begin_reset(next_identity, _binding(next_identity))
    assert reset_started.snapshot.reward_baseline is None
    assert reset_started.snapshot.last_committed_goal_progress is None
    assert reset_started.snapshot.reset_commit_facts is None


def test_production_lifecycle_module_has_no_runtime_or_ground_truth_imports() -> None:
    module_path = Path(__file__).parents[1] / "mecanum_nav_rl" / "core" / "episode_lifecycle.py"
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    imported = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported.update(
        node.module.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    )
    forbidden = {
        "rclpy",
        "rospy",
        "sensor_msgs",
        "geometry_msgs",
        "nav_msgs",
        "tf2_ros",
        "gazebo",
        "gz",
        "gymnasium",
        "stable_baselines3",
    }
    assert imported.isdisjoint(forbidden)
    assert "GroundTruthSample" not in module_path.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("field_name", "replacement"),
    (
        ("scenario_id", "other-scenario"),
        ("scenario_version", "2.0.0"),
        ("scenario_content_sha256", "b" * 64),
        ("gazebo_world_name", "other-world"),
        ("world_file_sha256", "d" * 64),
        ("coordinate_reference_id", "OTHER_REFERENCE"),
    ),
)
def test_reset_rejects_any_full_session_binding_mismatch_without_partial_commit(
    field_name: str, replacement: str
) -> None:
    lifecycle = EpisodeLifecycle()
    identity = _identity(0)
    expected = _binding(identity)
    lifecycle.begin_reset(identity, expected)
    lifecycle.wait_for_initial_observation(identity)
    candidate = _reset_candidate(
        identity,
        binding=replace(expected, **{field_name: replacement}),
    )
    result = lifecycle.commit_reset(candidate)
    assert result.status is EpisodeOperationStatus.RESET_ABORT
    assert result.snapshot.state is EpisodeLifecycleState.FAULT
    assert result.snapshot.pending_scenario_session_binding is None
    assert result.snapshot.committed_scenario_session_binding is None
    assert result.snapshot.reward_baseline is None
    assert result.snapshot.reset_commit_facts is None
    assert result.snapshot.previous_issued_command is None
    assert result.snapshot.step_index is None


def test_pending_binding_commits_once_and_new_generation_clears_it() -> None:
    lifecycle = EpisodeLifecycle()
    first = _identity(0)
    first_binding = _binding(first)
    started = lifecycle.begin_reset(first, first_binding)
    assert started.snapshot.pending_scenario_session_binding == first_binding
    assert started.snapshot.committed_scenario_session_binding is None
    lifecycle.wait_for_initial_observation(first)
    committed = lifecycle.commit_reset(_reset_candidate(first, binding=first_binding))
    assert committed.snapshot.pending_scenario_session_binding is None
    assert committed.snapshot.committed_scenario_session_binding == first_binding
    assert committed.snapshot.reward_baseline is not None
    assert committed.snapshot.reward_baseline.scenario_session_binding == first_binding

    second = _identity(1)
    second_binding = _binding(second)
    reset = lifecycle.begin_reset(second, second_binding)
    assert reset.snapshot.pending_scenario_session_binding == second_binding
    assert reset.snapshot.committed_scenario_session_binding is None
    assert reset.snapshot.reward_baseline is None


def test_goal_fact_cannot_self_anchor_a_reset_session() -> None:
    lifecycle = EpisodeLifecycle()
    identity = _identity(0)
    before = lifecycle.snapshot
    fact = _goal_result(
        identity,
        _provenance(identity, 100),
        2.5,
        mode=GoalFactJoinMode.RESET_OBSERVATION0,
        binding=_binding(identity),
    )
    with pytest.raises(TypeError, match="ScenarioSessionBinding"):
        lifecycle.begin_reset(identity, fact)  # type: ignore[arg-type]
    assert lifecycle.snapshot == before


def test_lifecycle_source_has_no_tasks_dependency_even_locally() -> None:
    module_path = Path(__file__).parents[1] / "mecanum_nav_rl" / "core" / "episode_lifecycle.py"
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    imported_modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    imported_modules.update(
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    )
    assert not any(module.startswith("mecanum_nav_rl.tasks") for module in imported_modules)
