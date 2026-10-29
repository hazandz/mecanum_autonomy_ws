"""Stateless reward-v3-baseline calculation over immutable facts."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from numbers import Real


@dataclass(frozen=True, slots=True)
class TransitionRewardInput:
    """Validated scalar facts used for one reward calculation."""

    previous_true_goal_distance_m: float
    current_true_goal_distance_m: float
    clearance_m: float
    dt_sim_s: float
    final_issued_normalized: tuple[float, float, float]
    previous_final_issued_normalized: tuple[float, float, float]
    goal: bool = False
    collision: bool = False
    stuck: bool = False


@dataclass(frozen=True, slots=True)
class RewardTerms:
    """Individual reward-v3-baseline terms."""

    progress: float
    time: float
    clearance: float
    smooth: float
    terminal: float

    @property
    def total(self) -> float:
        """Return the sum of the five reward terms."""
        return (
            self.progress + self.time + self.clearance + self.smooth
            + self.terminal
        )


@dataclass(frozen=True, slots=True)
class RewardResult:
    """Canonical reward and its committed distance baseline."""

    terms: RewardTerms
    total: float
    baseline_distance_m: float


class RewardManager:
    """Compute reward without callbacks, mutable state, or clock reads."""

    def compute(self, context: TransitionRewardInput) -> RewardResult:
        """Compute all reward terms from one explicit transition input."""
        if not isinstance(context, TransitionRewardInput):
            raise TypeError('context must be TransitionRewardInput')
        previous = _finite(
            'previous_true_goal_distance_m',
            context.previous_true_goal_distance_m,
        )
        current = _finite(
            'current_true_goal_distance_m',
            context.current_true_goal_distance_m,
        )
        clearance = _finite('clearance_m', context.clearance_m)
        dt = _finite('dt_sim_s', context.dt_sim_s)
        if previous < 0 or current < 0 or clearance < 0 or dt <= 0:
            raise ValueError(
                'distances must be non-negative and dt_sim_s must be positive'
            )
        _bool('goal', context.goal)
        _bool('collision', context.collision)
        _bool('stuck', context.stuck)
        command = _command(
            'final_issued_normalized', context.final_issued_normalized
        )
        previous_command = _command(
            'previous_final_issued_normalized',
            context.previous_final_issued_normalized,
        )
        progress = _clip(2.0 * (previous - current), -1.0, 1.0)
        time = -0.1 * dt
        clearance_term = (
            -0.2 * max(0.0, (0.3 - clearance) / 0.3) * dt / 0.1
        )
        squared = sum(
            (a - b) * (a - b)
            for a, b in zip(command, previous_command, strict=True)
        )
        smooth = _clip(-0.005 * squared / max(dt, 1e-6), -1.0, 0.0)
        terminal = (
            -15.0 if context.collision else
            15.0 if context.goal else
            -3.0 if context.stuck else 0.0
        )
        terms = RewardTerms(
            progress, time, clearance_term, smooth, terminal
        )
        total = terms.total
        expected_sum = sum((
            terms.progress, terms.time, terms.clearance, terms.smooth,
            terms.terminal,
        ))
        if not isfinite(total) or abs(total - expected_sum) > 1e-6:
            raise ValueError('reward sum is non-finite or inconsistent')
        return RewardResult(terms, total, previous)


def _finite(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f'{name} must be finite')
    if not isfinite(float(value)):
        raise ValueError(f'{name} must be finite')
    return float(value)


def _command(name: str, value: object) -> tuple[float, float, float]:
    if type(value) is not tuple or len(value) != 3:
        raise TypeError(f'{name} must be a three-value tuple')
    result = tuple(
        _finite(f'{name}[{index}]', component)
        for index, component in enumerate(value)
    )
    if any(component < -1.0 or component > 1.0 for component in result):
        raise ValueError(f'{name} values must be normalized in [-1,1]')
    return result


def _bool(name: str, value: object) -> None:
    if type(value) is not bool:
        raise TypeError(f'{name} must be bool')


def _clip(value: float, low: float, high: float) -> float:
    return min(high, max(low, value))


__all__ = (
    'RewardManager',
    'RewardResult',
    'RewardTerms',
    'TransitionRewardInput',
)
