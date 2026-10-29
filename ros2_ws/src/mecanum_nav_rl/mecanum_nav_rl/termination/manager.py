"""Termination precedence, continuous stuck window and collection censoring."""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from math import hypot, isclose, isfinite
from numbers import Real

class TerminationReason(str, Enum):
    COLLISION = 'collision'
    GOAL = 'goal'
    OUT_OF_BOUNDS = 'out_of_bounds'
    STUCK = 'stuck'
    EPISODE_SIM_TIME_LIMIT = 'episode_sim_time_limit'

@dataclass(frozen=True, slots=True)

class EpisodeTaskSample:
    ros_time_ns: int
    x_m: float
    y_m: float
    true_goal_distance_m: float
    required_health_valid: bool

@dataclass(frozen=True, slots=True)

class ValidArea:
    min_x_m: float
    max_x_m: float
    min_y_m: float
    max_y_m: float
    authority_id: str

    def __post_init__(self) -> None:
        values = tuple((_finite(n, getattr(self, n)) for n in ('min_x_m',
            'max_x_m', 'min_y_m', 'max_y_m')))
        if values[0] >= values[1] or values[2] >= values[3]:
            raise ValueError('valid area bounds are unordered')
        if type(self.authority_id) is not str or not self.authority_id.strip():
            raise ValueError('valid area must carry an authority identity')

    def contains(self, x: float, y: float) -> bool:
        return self.min_x_m <= x <= self.max_x_m and self.min_y_m <= y <= self.max_y_m

@dataclass(frozen=True, slots=True)

class EpisodeTimeLimit:
    horizon_ns: int = 120000000000

    def __post_init__(self):
        if type(self.horizon_ns) is not int or self.horizon_ns <= 0:
            raise ValueError('horizon_ns must be positive')

@dataclass(frozen=True, slots=True)

class TerminationInput:
    elapsed_ros_ns: int
    current_sample: EpisodeTaskSample
    trajectory: tuple[EpisodeTaskSample, ...]
    collision: bool
    goal_settled_success: bool
    valid_area: ValidArea | None = None
    episode_limit: EpisodeTimeLimit = EpisodeTimeLimit()
    maximum_health_gap_ns: int = 250000000

@dataclass(frozen=True, slots=True)

class TerminationResult:
    terminated: bool
    truncated: bool
    reason: TerminationReason | None
    stuck_window_ready: bool

    def __post_init__(self):
        if self.terminated and self.truncated:
            raise ValueError('terminated and truncated are exclusive')
        if (self.terminated or self.truncated) != (self.reason is not None):
            raise ValueError('terminal reason must match task terminal flags')

class TerminationManager:

    def evaluate(self, context: TerminationInput) -> TerminationResult:
        if not isinstance(context, TerminationInput):
            raise TypeError('context must be TerminationInput')
        if type(context.elapsed_ros_ns) is not int or context.elapsed_ros_ns < 0:
            raise ValueError('elapsed_ros_ns must be non-negative')
        if type(context.collision) is not bool or type(context.goal_settled_success) is not bool:
            raise TypeError('collision and goal success must be bool')
        if not isinstance(context.current_sample,
            EpisodeTaskSample) or type(context.trajectory) is not tuple:
            raise TypeError('current sample and trajectory must be immutable task facts')
        if type(context.maximum_health_gap_ns) is not int or context.maximum_health_gap_ns < 0:
            raise ValueError('maximum_health_gap_ns must be non-negative')
        current = context.current_sample
        if type(current.required_health_valid) is not bool:
            raise TypeError('current required health must be bool')
        _finite('current x_m', current.x_m)
        _finite('current y_m', current.y_m)
        _finite('current true_goal_distance_m', current.true_goal_distance_m)
        if not current.required_health_valid:
            raise ValueError('missing required health is infrastructure non-readiness')
        if not isinstance(context.episode_limit, EpisodeTimeLimit):
            raise TypeError('episode_limit must be EpisodeTimeLimit')
        if context.valid_area is not None and (not isinstance(context.valid_area, ValidArea)):
            raise TypeError('out-of-bounds requires a bound ValidArea')
        oob = context.valid_area is not None and (not context.valid_area.contains(current.x_m, current.y_m))
        stuck = self._stuck(context.trajectory, current,
            context.maximum_health_gap_ns)
        timed_out = context.elapsed_ros_ns >= context.episode_limit.horizon_ns
        if context.collision:
            return TerminationResult(True, False, TerminationReason.COLLISION,
                stuck)
        if context.goal_settled_success:
            return TerminationResult(True, False, TerminationReason.GOAL,
                stuck)
        if oob:
            return TerminationResult(True, False,
                TerminationReason.OUT_OF_BOUNDS, stuck)
        if stuck:
            return TerminationResult(True, False, TerminationReason.STUCK,
                True)
        if timed_out:
            return TerminationResult(False, True,
                TerminationReason.EPISODE_SIM_TIME_LIMIT, stuck)
        return TerminationResult(False, False, None, stuck)

    @staticmethod
    def _stuck(trajectory: tuple[EpisodeTaskSample, ...],
        current: EpisodeTaskSample, max_gap: int) -> bool:
        samples = (*trajectory, current)
        if any((not isinstance(s, EpisodeTaskSample) for s in samples)):
            return False
        if any((type(s.ros_time_ns) is not int or s.ros_time_ns < 0 for s in samples)):
            return False
        if any((a.ros_time_ns >= b.ros_time_ns for a, b in zip(samples,
            samples[1:]))):
            return False
        end = current.ros_time_ns
        eligible = tuple((s for s in samples if end - 10000000000 <= s.ros_time_ns <= end))
        if any((not s.required_health_valid for s in eligible)):
            return False
        if len(eligible) < 2 or eligible[0].ros_time_ns > end - 10000000000:
            return False
        if any((b.ros_time_ns - a.ros_time_ns > max_gap for a,
            b in zip(eligible, eligible[1:]))):
            return False
        positions = tuple(((_finite('x_m', s.x_m), _finite('y_m',
            s.y_m)) for s in eligible))
        spread = max((hypot(a[0] - b[0],
            a[1] - b[1]) for a in positions for b in positions))
        reduction = _finite('start goal distance',
            eligible[0].true_goal_distance_m) - _finite('end goal distance', current.true_goal_distance_m)
        return spread < 0.1 and reduction < 0.1 and (not isclose(reduction,
            0.1, rel_tol=0.0, abs_tol=1e-12))

@dataclass(frozen=True, slots=True)

class CollectionCutoff:
    reason: str
    episode_complete: bool
    elapsed_ros_ns: int
    length: int
    return_to_date: float
    censored: bool

def collection_cutoff(*, elapsed_ros_ns: int, length: int,
    return_to_date: float) -> CollectionCutoff:
    if type(elapsed_ros_ns) is not int or elapsed_ros_ns < 0 or type(length) is not int or (length < 0):
        raise ValueError('collection counters must be non-negative integers')
    value = _finite('return_to_date', return_to_date)
    return CollectionCutoff('COLLECTION_CUTOFF', False, elapsed_ros_ns, length,
        value, True)

def _finite(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value,
        Real) or (not isfinite(float(value))):
        raise ValueError(f'{name} must be finite')
    return float(value)
__all__ = ('EpisodeTaskSample', 'EpisodeTimeLimit', 'TerminationInput',
    'TerminationManager', 'TerminationReason', 'TerminationResult', 'ValidArea', 'CollectionCutoff', 'collection_cutoff')
