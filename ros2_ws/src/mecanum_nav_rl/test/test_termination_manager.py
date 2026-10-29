"""Pure termination precedence, stuck-window, and censoring regressions."""

from dataclasses import replace

from mecanum_nav_rl.termination.manager import (
    EpisodeTaskSample,
    TerminationInput,
    TerminationManager,
    TerminationReason,
    ValidArea,
    collection_cutoff,
)

import pytest


def sample(t, x=0.0, y=0.0, distance=1.0, healthy=True):
    """Construct one immutable oracle task sample."""
    return EpisodeTaskSample(t, x, y, distance, healthy)


def terminal(**kwargs):
    """Evaluate a task result with a fully covered default history."""
    facts = {
        'elapsed_ros_ns': 1,
        'current_sample': sample(10_000_000_000),
        'trajectory': tuple(sample(i * 250_000_000) for i in range(40)),
        'collision': False,
        'goal_settled_success': False,
    }
    facts.update(kwargs)
    return TerminationManager().evaluate(TerminationInput(**facts))


def test_precedence_and_simultaneous_episode_limit():
    """Collision outranks goal, bounds, stuck, and simultaneous horizon."""
    area = ValidArea(-1, 1, -1, 1, 'approved-valid-area')
    result = terminal(
        elapsed_ros_ns=120_000_000_000,
        collision=True,
        goal_settled_success=True,
        valid_area=area,
    )
    assert result.reason is TerminationReason.COLLISION
    assert result.terminated and not result.truncated
    assert terminal(goal_settled_success=True).reason is TerminationReason.GOAL
    moving = tuple(
        sample(i * 250_000_000, x=i * 0.01) for i in range(40)
    )
    limited = terminal(
        elapsed_ros_ns=120_000_000_000, trajectory=moving
    )
    assert limited.reason is TerminationReason.EPISODE_SIM_TIME_LIMIT


def test_out_of_bounds_requires_explicit_valid_area():
    """Candidate coordinates alone do not establish valid-area bounds."""
    outside = sample(10_000_000_000, x=100)
    assert terminal(current_sample=outside).reason is None
    area = ValidArea(-1, 1, -1, 1, 'bound-authority')
    result = terminal(current_sample=outside, valid_area=area)
    assert result.reason is TerminationReason.OUT_OF_BOUNDS


def test_stuck_requires_full_covered_window_and_strict_thresholds():
    """Stuck requires complete healthy coverage and strict sub-thresholds."""
    history = tuple(
        sample(i * 250_000_000, distance=1.0) for i in range(40)
    )
    ready = terminal(trajectory=history)
    assert ready.stuck_window_ready
    assert ready.reason is TerminationReason.STUCK
    too_short = terminal(trajectory=history[1:])
    assert not too_short.stuck_window_ready
    positions = tuple(
        sample(i * 250_000_000, x=0.1 if i == 0 else 0, distance=1.0)
        for i in range(40)
    )
    assert not terminal(trajectory=positions).stuck_window_ready
    reduction = tuple(
        sample(i * 250_000_000, distance=1.0 if i < 39 else 0.9)
        for i in range(40)
    )
    result = terminal(
        trajectory=reduction,
        current_sample=sample(10_000_000_000, distance=0.9),
    )
    assert not result.stuck_window_ready


def test_health_gap_and_rollback_do_not_extend_stuck_window():
    """Unhealthy or non-monotonic samples cannot bridge the window."""
    history = [sample(i * 250_000_000) for i in range(40)]
    history[20] = replace(history[20], required_health_valid=False)
    assert not terminal(trajectory=tuple(history)).stuck_window_ready
    rollback = tuple(sample(i * 250_000_000) for i in range(39)) + (sample(1),)
    assert not terminal(trajectory=rollback).stuck_window_ready


def test_stuck_uses_real_samples_bracketing_unaligned_window_boundary():
    """Real samples bracket the ten-second boundary without interpolation."""
    history = tuple(
        sample(i * 200_000_000, distance=1.0) for i in range(51)
    )
    result = terminal(
        current_sample=sample(10_100_000_000, distance=1.0),
        trajectory=history,
    )
    assert result.reason is TerminationReason.STUCK
    assert result.stuck_window_ready
    incomplete = tuple(
        sample(i * 200_000_000, distance=1.0) for i in range(1, 51)
    )
    result = terminal(
        current_sample=sample(10_100_000_000), trajectory=incomplete
    )
    assert not result.stuck_window_ready


def test_stuck_threshold_edges_are_strict_without_tolerance():
    """Exactly 0.10 m spread or progress does not satisfy STUCK."""
    history = tuple(
        sample(i * 250_000_000, distance=1.0) for i in range(40)
    )
    spread_edge = tuple(
        sample(i * 250_000_000, x=0.1 if i == 0 else 0.0, distance=1.0)
        for i in range(40)
    )
    progress_edge = tuple(
        sample(i * 250_000_000, distance=1.0 if i < 39 else 0.9)
        for i in range(40)
    )
    assert not terminal(trajectory=spread_edge).stuck_window_ready
    result = terminal(
        trajectory=progress_edge,
        current_sample=sample(10_000_000_000, distance=0.9),
    )
    assert not result.stuck_window_ready
    assert terminal(trajectory=history).stuck_window_ready


def test_collection_cutoff_is_censored_metadata_not_task_terminal():
    """Collection cutoff keeps task outcome censored and incomplete."""
    cutoff = collection_cutoff(
        elapsed_ros_ns=5, length=6, return_to_date=2.4
    )
    assert cutoff.reason == 'COLLECTION_CUTOFF'
    assert not cutoff.episode_complete and cutoff.censored
    assert cutoff.length == 6 and cutoff.return_to_date == 2.4


def test_missing_health_is_not_a_task_penalty_or_terminal():
    """Missing required health rejects task evaluation as infrastructure."""
    with pytest.raises(ValueError, match='infrastructure'):
        terminal(current_sample=sample(10_000_000_000, healthy=False))
