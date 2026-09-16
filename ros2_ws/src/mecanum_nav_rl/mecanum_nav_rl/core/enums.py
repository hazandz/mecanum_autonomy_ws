"""Stable enum contracts shared by the Mecanum DRL system."""

from __future__ import annotations

from enum import Enum, unique


@unique
class TerminationReason(str, Enum):
    """Reasons for a task to end as a true terminal state."""

    GOAL_REACHED = "goal_reached"
    COLLISION = "collision"
    OUT_OF_BOUNDS = "out_of_bounds"


@unique
class TruncationReason(str, Enum):
    """Reasons for an episode to stop due to an external limit."""

    TIME_LIMIT = "time_limit"

