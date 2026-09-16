"""Immutable context objects for one PPO control transition."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from numbers import Integral, Real

from mecanum_nav_rl.core.snapshots import SensorSnapshot
from mecanum_nav_rl.core.types import Pose2D, VelocityCommand


def _require_non_negative_integer(field_name: str, value: object) -> int:
    """Return a non-negative integer or raise a clear error."""

    if isinstance(value, bool) or not isinstance(value, Integral):
        raise TypeError(f"{field_name} must be an integer")

    integer_value = int(value)

    if integer_value < 0:
        raise ValueError(f"{field_name} must be non-negative")

    return integer_value


def _require_positive_finite_seconds(field_name: str, value: object) -> float:
    """Return a positive finite duration in seconds or raise a clear error."""

    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"{field_name} must be a real number")

    try:
        seconds = float(value)
    except OverflowError as error:
        raise ValueError(
            f"{field_name} must be finite and greater than zero"
        ) from error

    if not isfinite(seconds) or seconds <= 0.0:
        raise ValueError(f"{field_name} must be finite and greater than zero")

    return seconds


@dataclass(frozen=True, slots=True)
class TaskState:
    """Immutable task information shared by transitions in one episode.

    goal_pose must use the same configured coordinate frame as the poses in
    the associated SensorSnapshot objects.
    """

    episode_id: int
    step_index: int
    goal_pose: Pose2D

    def __post_init__(self) -> None:
        """Validate task identity, step index, and goal type."""

        object.__setattr__(
            self,
            "episode_id",
            _require_non_negative_integer("episode_id", self.episode_id),
        )
        object.__setattr__(
            self,
            "step_index",
            _require_non_negative_integer("step_index", self.step_index),
        )

        if not isinstance(self.goal_pose, Pose2D):
            raise TypeError("goal_pose must be a Pose2D")


@dataclass(frozen=True, slots=True)
class TransitionContext:
    """Immutable data required to evaluate one PPO control transition.

    Reward and termination logic must use this same context rather than read
    newer ROS data independently.
    """

    task_state: TaskState
    before_snapshot: SensorSnapshot
    after_snapshot: SensorSnapshot

    previous_applied_command: VelocityCommand
    applied_command: VelocityCommand

    delta_time_s: float

    def __post_init__(self) -> None:
        """Validate transition consistency across state, time, and commands."""

        if not isinstance(self.task_state, TaskState):
            raise TypeError("task_state must be a TaskState")

        if not isinstance(self.before_snapshot, SensorSnapshot):
            raise TypeError("before_snapshot must be a SensorSnapshot")

        if not isinstance(self.after_snapshot, SensorSnapshot):
            raise TypeError("after_snapshot must be a SensorSnapshot")

        if not isinstance(self.previous_applied_command, VelocityCommand):
            raise TypeError(
                "previous_applied_command must be a VelocityCommand"
            )

        if not isinstance(self.applied_command, VelocityCommand):
            raise TypeError("applied_command must be a VelocityCommand")

        if (
            self.before_snapshot.reset_epoch
            != self.after_snapshot.reset_epoch
        ):
            raise ValueError(
                "before_snapshot and after_snapshot must have the same "
                "reset_epoch"
            )

        if (
            self.before_snapshot.runtime_generation
            != self.after_snapshot.runtime_generation
        ):
            raise ValueError(
                "before_snapshot and after_snapshot must have the same "
                "runtime_generation"
            )

        if (
            self.after_snapshot.scan_stamp_ns
            < self.before_snapshot.scan_stamp_ns
        ):
            raise ValueError(
                "after_snapshot scan_stamp_ns must not be earlier than "
                "before_snapshot scan_stamp_ns"
            )

        if (
            self.after_snapshot.odom_stamp_ns
            < self.before_snapshot.odom_stamp_ns
        ):
            raise ValueError(
                "after_snapshot odom_stamp_ns must not be earlier than "
                "before_snapshot odom_stamp_ns"
            )

        object.__setattr__(
            self,
            "delta_time_s",
            _require_positive_finite_seconds(
                "delta_time_s",
                self.delta_time_s,
            ),
        )
