"""Shared pure value types for episode lifecycle identity and provenance."""

from __future__ import annotations

import re
from dataclasses import dataclass
from math import isfinite
from numbers import Integral, Real
from threading import RLock
from uuid import UUID, uuid5

_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")
CORE_TRANSACTION_LOCK = RLock()


def require_non_negative_integer(field_name: str, value: object) -> int:
    """Return an exact non-negative integer while rejecting booleans."""

    if isinstance(value, bool) or not isinstance(value, Integral):
        raise TypeError(f"{field_name} must be an integer")
    result = int(value)
    if result < 0:
        raise ValueError(f"{field_name} must be non-negative")
    return result


def require_non_negative_finite_real(field_name: str, value: object) -> float:
    """Return one finite non-negative real value without coercing booleans."""

    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"{field_name} must be a real number")
    try:
        result = float(value)
    except OverflowError as error:
        raise ValueError(f"{field_name} must be finite") from error
    if not isfinite(result):
        raise ValueError(f"{field_name} must be finite")
    if result < 0.0:
        raise ValueError(f"{field_name} must be non-negative")
    return result


def require_sha256(field_name: str, value: object) -> str:
    """Return a lowercase complete SHA-256 digest."""

    if not isinstance(value, str) or _SHA256_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{field_name} must be a lowercase SHA-256")
    return value


@dataclass(frozen=True, slots=True)
class EpisodeLifecycleIdentity:
    """Immutable episode/reset/runtime identity used to reject stale facts."""

    episode_generation: int
    reset_epoch: int
    runtime_generation: int

    def __post_init__(self) -> None:
        for field_name in (
            "episode_generation",
            "reset_epoch",
            "runtime_generation",
        ):
            object.__setattr__(
                self,
                field_name,
                require_non_negative_integer(field_name, getattr(self, field_name)),
            )


@dataclass(frozen=True, slots=True)
class CommittedGoalSettleState:
    """Scalar settle clock committed for one lifecycle and task goal."""

    lifecycle: EpisodeLifecycleIdentity
    task_id: str
    session_id: str
    goal_id: str
    goal_xy_m: tuple[float, float]
    settled_since_ros_ns: int | None
    last_ros_ns: int | None
    success: bool

    def __post_init__(self) -> None:
        """Kiểm tra và chuẩn hóa state settle đã commit."""
        if not isinstance(self.lifecycle, EpisodeLifecycleIdentity):
            raise TypeError('lifecycle must be EpisodeLifecycleIdentity')
        for name in ('task_id', 'session_id', 'goal_id'):
            value = getattr(self, name)
            if type(value) is not str or not value or value != value.strip():
                raise ValueError(f'{name} must be a non-empty trimmed string')
        if type(self.goal_xy_m) is not tuple or len(self.goal_xy_m) != 2:
            raise TypeError('goal_xy_m must be a two-value tuple')
        for value in self.goal_xy_m:
            if isinstance(value, bool) or not isinstance(value, Real):
                raise TypeError('goal coordinates must be finite real values')
            if not isfinite(float(value)):
                raise ValueError('goal coordinates must be finite real values')
        object.__setattr__(
            self, 'goal_xy_m',
            (float(self.goal_xy_m[0]), float(self.goal_xy_m[1]))
        )
        for name in ('settled_since_ros_ns', 'last_ros_ns'):
            value = getattr(self, name)
            if value is not None and (type(value) is not int or value < 0):
                raise ValueError(
                    f'{name} must be None or a non-negative integer'
                )
        if type(self.success) is not bool:
            raise TypeError('success must be bool')
        if (
            self.settled_since_ros_ns is not None
            and self.last_ros_ns is not None
            and self.last_ros_ns < self.settled_since_ros_ns
        ):
            raise ValueError('settle state ROS time cannot move backward')


@dataclass(frozen=True, slots=True)
class CommittedTaskHistorySample:
    """One true task sample retained for the lifecycle's STUCK window."""

    lifecycle: EpisodeLifecycleIdentity
    task_id: str
    session_id: str
    goal_id: str
    goal_xy_m: tuple[float, float]
    ros_time_ns: int
    x_m: float
    y_m: float
    true_goal_distance_m: float
    required_health_valid: bool

    def __post_init__(self) -> None:
        """Kiểm tra mẫu trajectory oracle trước khi lưu vào lifecycle."""
        if not isinstance(self.lifecycle, EpisodeLifecycleIdentity):
            raise TypeError('lifecycle must be EpisodeLifecycleIdentity')
        for name in ('task_id', 'session_id', 'goal_id'):
            value = getattr(self, name)
            if type(value) is not str or not value or value != value.strip():
                raise ValueError(f'{name} must be a non-empty trimmed string')
        if type(self.goal_xy_m) is not tuple or len(self.goal_xy_m) != 2:
            raise TypeError('goal_xy_m must be a two-value tuple')
        xy = tuple(
            _finite_scalar('goal coordinate', value)
            for value in self.goal_xy_m
        )
        object.__setattr__(self, 'goal_xy_m', xy)
        if type(self.ros_time_ns) is not int or self.ros_time_ns < 0:
            raise ValueError('ros_time_ns must be a non-negative integer')
        for name in ('x_m', 'y_m', 'true_goal_distance_m'):
            object.__setattr__(
                self, name, _finite_scalar(name, getattr(self, name))
            )
        if self.true_goal_distance_m < 0:
            raise ValueError('true_goal_distance_m must be non-negative')
        if type(self.required_health_valid) is not bool:
            raise TypeError('required_health_valid must be bool')


def _finite_scalar(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f'{name} must be a finite real number')
    numeric = float(value)
    if not isfinite(numeric):
        raise ValueError(f'{name} must be a finite real number')
    return numeric


@dataclass(frozen=True, slots=True)
class PendingScenarioSession:
    """Giữ scenario binding trước identity rearm authoritative."""

    scenario_id: str
    scenario_version: str
    scenario_content_sha256: str
    gazebo_world_name: str
    world_file_sha256: str
    coordinate_reference_id: str

    def __post_init__(self) -> None:
        """Kiểm tra scalar scenario binding đang chờ identity authoritative."""
        for name in (
            'scenario_id', 'scenario_version', 'gazebo_world_name',
            'coordinate_reference_id'
        ):
            value = getattr(self, name)
            if type(value) is not str or not value or value != value.strip():
                raise ValueError(f'{name} must be a non-empty trimmed string')
        require_sha256('scenario_content_sha256', self.scenario_content_sha256)
        require_sha256('world_file_sha256', self.world_file_sha256)


@dataclass(frozen=True, slots=True)
class TransitionIdentity:
    """Caller-supplied identity for one step; core never generates its token."""

    identity: EpisodeLifecycleIdentity
    step_index: int
    transition_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.identity, EpisodeLifecycleIdentity):
            raise TypeError('identity must be an EpisodeLifecycleIdentity')
        object.__setattr__(
            self,
            'step_index',
            require_non_negative_integer('step_index', self.step_index),
        )
        if self.step_index == 0:
            raise ValueError('transition step_index must be positive')
        if not isinstance(self.transition_id, str) or not self.transition_id.strip():
            raise ValueError('transition_id must be a non-empty string')
        if len(self.transition_id) > 36:
            raise ValueError('transition_id must fit receipt-v2 string<=36')


_POLICY_TRANSITION_NAMESPACE = UUID('d61c9b6a-9ea5-5e98-8fe7-c2746be4d25e')


def policy_transition_identity(
    *,
    identity: EpisodeLifecycleIdentity,
    session_id: str,
    source_instance_id: int,
    source_sequence: int,
    step_index: int,
) -> TransitionIdentity:
    """Tạo identity UUIDv5 ổn định từ session, lifecycle và khóa POLICY."""
    if not isinstance(identity, EpisodeLifecycleIdentity):
        raise TypeError('identity must be EpisodeLifecycleIdentity')
    if (
        type(session_id) is not str
        or not session_id
        or session_id != session_id.strip()
    ):
        raise ValueError('session_id must be non-empty and trimmed')
    for name, value in (
        ('source_instance_id', source_instance_id),
        ('source_sequence', source_sequence),
    ):
        if type(value) is not int or value < 0:
            raise ValueError(f'{name} must be a non-negative integer')
    if source_sequence == 0:
        raise ValueError('POLICY source sequence must be positive')
    if type(step_index) is not int or step_index <= 0:
        raise ValueError('step_index must be positive')
    name = (
        f'{session_id}|{identity.episode_generation}|{identity.reset_epoch}|'
        f'{identity.runtime_generation}|{source_instance_id}|{source_sequence}'
    )
    token = str(uuid5(_POLICY_TRANSITION_NAMESPACE, name))
    return TransitionIdentity(identity, step_index, token)


@dataclass(frozen=True, slots=True)
class ExactObservationProvenance:
    """Test-only exact scan/odometry/observation provenance without raw messages."""

    identity: EpisodeLifecycleIdentity
    scan_timestamp_ns: int
    odometry_timestamp_ns: int
    observation_timestamp_ns: int

    def __post_init__(self) -> None:
        if not isinstance(self.identity, EpisodeLifecycleIdentity):
            raise TypeError("identity must be an EpisodeLifecycleIdentity")
        for field_name in (
            "scan_timestamp_ns",
            "odometry_timestamp_ns",
            "observation_timestamp_ns",
        ):
            object.__setattr__(
                self,
                field_name,
                require_non_negative_integer(field_name, getattr(self, field_name)),
            )

    @property
    def exact(self) -> bool:
        """Whether scan, odometry, and encoded observation share one timestamp."""

        return (
            self.scan_timestamp_ns
            == self.odometry_timestamp_ns
            == self.observation_timestamp_ns
        )

