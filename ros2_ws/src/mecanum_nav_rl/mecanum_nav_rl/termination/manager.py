"""Pure task termination, stuck-window, and collection-censor decisions."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from math import hypot, isfinite
from numbers import Real

from mecanum_nav_rl.core.scenario_session import ScenarioSessionBinding


class TerminationReason(str, Enum):
    """Terminal outcomes defined by the Roadmap B task contract."""

    COLLISION = 'collision'
    GOAL = 'goal'
    OUT_OF_BOUNDS = 'out_of_bounds'
    STUCK = 'stuck'
    EPISODE_SIM_TIME_LIMIT = 'episode_sim_time_limit'


@dataclass(frozen=True, slots=True)
class EpisodeTaskSample:
    """One oracle trajectory sample used only for task evaluation."""

    ros_time_ns: int
    x_m: float
    y_m: float
    true_goal_distance_m: float
    required_health_valid: bool


@dataclass(frozen=True, slots=True)
class ValidArea:
    """Task bounds, optionally bound to a scenario/session/task identity."""

    min_x_m: float
    max_x_m: float
    min_y_m: float
    max_y_m: float
    authority_id: str
    scenario_session_binding: ScenarioSessionBinding | None = None
    task_id: str | None = None
    session_id: str | None = None

    def __post_init__(self) -> None:
        """Validate bounds and any supplied task-context binding."""
        values = tuple(
            _finite(name, getattr(self, name))
            for name in ('min_x_m', 'max_x_m', 'min_y_m', 'max_y_m')
        )
        if values[0] >= values[1] or values[2] >= values[3]:
            raise ValueError('valid area bounds are unordered')
        if type(self.authority_id) is not str or not self.authority_id.strip():
            raise ValueError('valid area must carry an authority identity')
        bound_values = (
            self.scenario_session_binding, self.task_id, self.session_id
        )
        if any(value is not None for value in bound_values):
            if not isinstance(
                self.scenario_session_binding, ScenarioSessionBinding
            ):
                raise TypeError(
                    'bound valid area requires scenario session binding'
                )
            if any(
                type(value) is not str or not value or value != value.strip()
                for value in (self.task_id, self.session_id)
            ):
                raise ValueError(
                    'bound valid area requires task and session identity'
                )

    def contains(self, x: float, y: float) -> bool:
        """Return whether a planar point lies inside the inclusive bounds."""
        return (
            self.min_x_m <= x <= self.max_x_m
            and self.min_y_m <= y <= self.max_y_m
        )


@dataclass(frozen=True, slots=True)
class EpisodeTimeLimit:
    """ROS-time task horizon."""

    horizon_ns: int = 120_000_000_000

    def __post_init__(self) -> None:
        """Require a positive integer ROS-time horizon."""
        if type(self.horizon_ns) is not int or self.horizon_ns <= 0:
            raise ValueError('horizon_ns must be positive')


@dataclass(frozen=True, slots=True)
class TerminationInput:
    """Current task facts plus the bounded committed oracle trajectory."""

    elapsed_ros_ns: int
    current_sample: EpisodeTaskSample
    trajectory: tuple[EpisodeTaskSample, ...]
    collision: bool
    goal_settled_success: bool
    valid_area: ValidArea | None = None
    episode_limit: EpisodeTimeLimit = EpisodeTimeLimit()
    maximum_health_gap_ns: int = 250_000_000


@dataclass(frozen=True, slots=True)
class TerminationResult:
    """Task terminal flags and reason from one evaluation."""

    terminated: bool
    truncated: bool
    reason: TerminationReason | None
    stuck_window_ready: bool

    def __post_init__(self) -> None:
        """Keep outcome flags and reason in the contract-defined mapping."""
        if (
            type(self.terminated) is not bool
            or type(self.truncated) is not bool
        ):
            raise TypeError('termination flags must be bool')
        if type(self.stuck_window_ready) is not bool:
            raise TypeError('stuck_window_ready must be bool')
        if self.terminated and self.truncated:
            raise ValueError('terminated and truncated are exclusive')
        if (self.terminated or self.truncated) != (self.reason is not None):
            raise ValueError('terminal reason must match task terminal flags')
        if self.reason is not None and not isinstance(
            self.reason, TerminationReason
        ):
            raise TypeError('reason must be a TerminationReason')
        task_terminal = self.reason in (
            TerminationReason.COLLISION,
            TerminationReason.GOAL,
            TerminationReason.OUT_OF_BOUNDS,
            TerminationReason.STUCK,
        )
        time_limit = self.reason is TerminationReason.EPISODE_SIM_TIME_LIMIT
        if (self.terminated, self.truncated) != (task_terminal, time_limit):
            raise ValueError('termination flags do not match reason')


class TerminationManager:
    """Compute precedence and stuck state from immutable task facts."""

    def evaluate(self, context: TerminationInput) -> TerminationResult:
        """Return one terminal result, rejecting unhealthy task evidence."""
        if not isinstance(context, TerminationInput):
            raise TypeError('context must be TerminationInput')
        if (
            type(context.elapsed_ros_ns) is not int
            or context.elapsed_ros_ns < 0
        ):
            raise ValueError('elapsed_ros_ns must be non-negative')
        if (
            type(context.collision) is not bool
            or type(context.goal_settled_success) is not bool
        ):
            raise TypeError('collision and goal success must be bool')
        if (
            not isinstance(context.current_sample, EpisodeTaskSample)
            or type(context.trajectory) is not tuple
        ):
            raise TypeError(
                'current sample and trajectory must be immutable task facts'
            )
        if (
            type(context.maximum_health_gap_ns) is not int
            or context.maximum_health_gap_ns < 0
        ):
            raise ValueError('maximum_health_gap_ns must be non-negative')
        current = context.current_sample
        if type(current.required_health_valid) is not bool:
            raise TypeError('current required health must be bool')
        _finite('current x_m', current.x_m)
        _finite('current y_m', current.y_m)
        _finite('current true_goal_distance_m', current.true_goal_distance_m)
        if not current.required_health_valid:
            raise ValueError(
                'missing required health is infrastructure non-readiness'
            )
        if not isinstance(context.episode_limit, EpisodeTimeLimit):
            raise TypeError('episode_limit must be EpisodeTimeLimit')
        if context.valid_area is not None and not isinstance(
            context.valid_area, ValidArea
        ):
            raise TypeError('out-of-bounds requires a bound ValidArea')
        out_of_bounds = (
            context.valid_area is not None
            and not context.valid_area.contains(current.x_m, current.y_m)
        )
        stuck = self._stuck(
            context.trajectory, current, context.maximum_health_gap_ns
        )
        timed_out = context.elapsed_ros_ns >= context.episode_limit.horizon_ns
        if context.collision:
            return TerminationResult(
                True, False, TerminationReason.COLLISION, stuck
            )
        if context.goal_settled_success:
            return TerminationResult(
                True, False, TerminationReason.GOAL, stuck
            )
        if out_of_bounds:
            return TerminationResult(
                True, False, TerminationReason.OUT_OF_BOUNDS, stuck
            )
        if stuck:
            return TerminationResult(
                True, False, TerminationReason.STUCK, True
            )
        if timed_out:
            return TerminationResult(
                False, True, TerminationReason.EPISODE_SIM_TIME_LIMIT, stuck
            )
        return TerminationResult(False, False, None, stuck)

    @staticmethod
    def _stuck(
        trajectory: tuple[EpisodeTaskSample, ...],
        current: EpisodeTaskSample,
        max_gap: int,
    ) -> bool:
        """Check ten seconds of real, healthy samples without interpolation."""
        samples = (*trajectory, current)
        if any(type(sample) is not EpisodeTaskSample for sample in samples):
            return False
        if any(
            type(sample.ros_time_ns) is not int or sample.ros_time_ns < 0
            for sample in samples
        ):
            return False
        if any(
            type(sample.required_health_valid) is not bool
            or not sample.required_health_valid
            for sample in samples
        ):
            return False
        if any(
            earlier.ros_time_ns >= later.ros_time_ns
            for earlier, later in zip(samples, samples[1:])
        ):
            return False
        end = current.ros_time_ns
        start = end - 10_000_000_000
        before = tuple(
            sample for sample in samples if sample.ros_time_ns <= start
        )
        after = tuple(
            sample for sample in samples if sample.ros_time_ns >= start
        )
        if not before or not after:
            return False
        left = before[-1]
        right = after[0]
        if right.ros_time_ns - left.ros_time_ns > max_gap:
            return False
        eligible = tuple(
            sample for sample in samples
            if left.ros_time_ns <= sample.ros_time_ns <= end
        )
        if len(eligible) < 2 or eligible[0] != left:
            return False
        if any(
            later.ros_time_ns - earlier.ros_time_ns > max_gap
            for earlier, later in zip(eligible, eligible[1:])
        ):
            return False
        positions = tuple(
            (_finite('x_m', sample.x_m), _finite('y_m', sample.y_m))
            for sample in eligible
        )
        spread = max(
            hypot(first[0] - second[0], first[1] - second[1])
            for first in positions for second in positions
        )
        start_distance = Decimal(str(_finite(
            'start goal distance', eligible[0].true_goal_distance_m
        )))
        end_distance = Decimal(str(_finite(
            'end goal distance', current.true_goal_distance_m
        )))
        reduction = start_distance - end_distance
        return spread < 0.1 and reduction < Decimal('0.1')


@dataclass(frozen=True, slots=True)
class CollectionCutoff:
    """Censored rollout metadata; not an MDP terminal result."""

    reason: str
    episode_complete: bool
    elapsed_ros_ns: int
    length: int
    return_to_date: float
    censored: bool


def collection_cutoff(
    *, elapsed_ros_ns: int, length: int, return_to_date: float
) -> CollectionCutoff:
    """Describe orchestration censoring without manufacturing task outcome."""
    if (
        type(elapsed_ros_ns) is not int
        or elapsed_ros_ns < 0
        or type(length) is not int
        or length < 0
    ):
        raise ValueError('collection counters must be non-negative integers')
    value = _finite('return_to_date', return_to_date)
    return CollectionCutoff(
        'COLLECTION_CUTOFF', False, elapsed_ros_ns, length, value, True
    )


def _finite(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f'{name} must be finite')
    if not isfinite(float(value)):
        raise ValueError(f'{name} must be finite')
    return float(value)


__all__ = (
    'EpisodeTaskSample',
    'EpisodeTimeLimit',
    'TerminationInput',
    'TerminationManager',
    'TerminationReason',
    'TerminationResult',
    'ValidArea',
    'CollectionCutoff',
    'collection_cutoff',
)
