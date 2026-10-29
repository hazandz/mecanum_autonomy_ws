"""Pure reward calculation and package-discovery regressions."""

from pathlib import Path

from mecanum_nav_rl.rewards.manager import (
    RewardManager,
    TransitionRewardInput,
)

import pytest

from setuptools import find_packages


def test_reward_terms_use_actual_dt_clearance_and_final_issued_command():
    """Every reward term follows the supplied final command and actual dt."""
    facts = TransitionRewardInput(
        previous_true_goal_distance_m=2.0,
        current_true_goal_distance_m=1.8,
        clearance_m=0.15,
        dt_sim_s=0.2,
        final_issued_normalized=(0.5, -0.5, 0.0),
        previous_final_issued_normalized=(0.0, 0.0, 0.0),
    )
    result = RewardManager().compute(facts)
    assert result.terms.progress == pytest.approx(0.4)
    assert result.terms.time == pytest.approx(-0.02)
    assert result.terms.clearance == pytest.approx(-0.2)
    assert result.terms.smooth == pytest.approx(-0.0125)
    assert result.terms.terminal == 0
    terms_sum = sum((
        result.terms.progress,
        result.terms.time,
        result.terms.clearance,
        result.terms.smooth,
        result.terms.terminal,
    ))
    assert result.total == pytest.approx(terms_sum, abs=1e-6)


def test_terminal_precedence_collision_over_goal_and_no_double_bonus():
    """Collision's terminal term wins simultaneous other task facts."""
    facts = TransitionRewardInput(
        1, 0, 0.3, 0.1, (0, 0, 0), (0, 0, 0),
        goal=True, collision=True, stuck=True,
    )
    assert RewardManager().compute(facts).terms.terminal == -15


@pytest.mark.parametrize('dt', [0, float('nan'), float('inf'), -0.1])
def test_invalid_dt_is_infrastructure_error_not_reward(dt):
    """Invalid simulation duration cannot produce a reward tuple."""
    facts = TransitionRewardInput(1, 0, 0.4, dt, (0, 0, 0), (0, 0, 0))
    with pytest.raises(ValueError):
        RewardManager().compute(facts)


def test_candidate_command_is_not_reward_input_and_invalid_envelope_rejects():
    """Only normalized final-issued payloads are valid reward commands."""
    with pytest.raises(ValueError, match='normalized'):
        RewardManager().compute(TransitionRewardInput(
            1, 0, 1, 0.1, (1.01, 0, 0), (0, 0, 0)
        ))
    first = RewardManager().compute(TransitionRewardInput(
        2, 1.9, 1, 0.1, (0.5, 0, 0), (0, 0, 0)
    ))
    second = RewardManager().compute(TransitionRewardInput(
        2, 1.9, 1, 0.1, (0.0, 0, 0), (0, 0, 0)
    ))
    assert first.terms.smooth < second.terms.smooth


def test_reward_packages_are_discovered_without_new_entrypoint():
    """The existing package discovery includes both pure subpackages."""
    root = Path(__file__).parents[1]
    packages = find_packages(where=str(root), exclude=('test', 'test.*'))
    assert 'mecanum_nav_rl.rewards' in packages
    assert 'mecanum_nav_rl.termination' in packages
    setup = (root / 'setup.py').read_text(encoding='utf-8')
    assert 'rewards:' not in setup
    assert 'termination:' not in setup
