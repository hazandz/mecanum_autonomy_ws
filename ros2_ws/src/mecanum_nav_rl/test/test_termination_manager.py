from dataclasses import replace
import pytest
from mecanum_nav_rl.termination.manager import EpisodeTaskSample, TerminationInput, TerminationManager, TerminationReason, ValidArea, collection_cutoff

def sample(t, x=0.0, y=0.0, d=1.0, healthy=True):
    return EpisodeTaskSample(t, x, y, d, healthy)

def terminal(**kwargs):
    base = dict(elapsed_ros_ns=1, current_sample=sample(10000000000),
        trajectory=tuple((sample(i * 250000000) for i in range(40))), collision=False, goal_settled_success=False)
    base.update(kwargs)
    return TerminationManager().evaluate(TerminationInput(**base))

def test_precedence_and_simultaneous_episode_limit():
    area = ValidArea(-1, 1, -1, 1, 'approved-valid-area')
    result = terminal(elapsed_ros_ns=120000000000, collision=True,
        goal_settled_success=True, valid_area=area)
    assert result.reason is TerminationReason.COLLISION and result.terminated and (not result.truncated)
    assert terminal(goal_settled_success=True).reason is TerminationReason.GOAL
    moving = tuple((sample(i * 250000000, x=i * 0.01,
        d=1.0) for i in range(40)))
    assert terminal(elapsed_ros_ns=120000000000,
        trajectory=moving).reason is TerminationReason.EPISODE_SIM_TIME_LIMIT

def test_out_of_bounds_requires_explicit_valid_area_and_never_uses_candidate_bounds():
    assert terminal(current_sample=sample(10000000000, x=100)).reason is None
    result = terminal(current_sample=sample(10000000000, x=100),
        valid_area=ValidArea(-1, 1, -1, 1, 'bound-authority'))
    assert result.reason is TerminationReason.OUT_OF_BOUNDS

def test_stuck_requires_full_covered_window_and_strict_thresholds():
    history = tuple((sample(i * 250000000, d=1.0) for i in range(40)))
    ready = terminal(trajectory=history)
    assert ready.stuck_window_ready and ready.reason is TerminationReason.STUCK
    too_short = terminal(trajectory=history[1:])
    assert not too_short.stuck_window_ready
    positions = tuple((sample(i * 250000000, x=0.1 if i == 0 else 0,
        d=1.0) for i in range(40)))
    assert not terminal(trajectory=positions).stuck_window_ready
    reduction = tuple((sample(i * 250000000,
        d=1.0 if i < 39 else 0.9) for i in range(40)))
    assert not terminal(trajectory=reduction,
        current_sample=sample(10000000000, d=0.9)).stuck_window_ready

def test_health_gap_and_rollback_do_not_extend_stuck_window():
    history = list((sample(i * 250000000) for i in range(40)))
    history[20] = replace(history[20], required_health_valid=False)
    assert not terminal(trajectory=tuple(history)).stuck_window_ready
    rollback = tuple((sample(i * 250000000) for i in range(39))) + (sample(1),)
    assert not terminal(trajectory=rollback).stuck_window_ready

def test_collection_cutoff_is_censored_metadata_not_task_terminal():
    cutoff = collection_cutoff(elapsed_ros_ns=5, length=6, return_to_date=2.4)
    assert cutoff.reason == 'COLLECTION_CUTOFF' and (not cutoff.episode_complete) and cutoff.censored
    assert cutoff.length == 6 and cutoff.return_to_date == 2.4

def test_missing_health_is_not_a_task_penalty_or_terminal():
    with pytest.raises(ValueError, match='infrastructure'):
        terminal(current_sample=sample(10000000000, healthy=False))
