"""Pure domain value objects used across the Mecanum DRL system."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from numbers import Real


def _require_finite_number(field_name: str, value: object) -> float:
    """Return a finite float or raise a clear error."""

    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"{field_name} must be a real number")

    try:
        numeric_value = float(value)
    except OverflowError as error:
        raise ValueError(
            f"{field_name} must be finite, not NaN or infinity"
        ) from error

    if not isfinite(numeric_value):
        raise ValueError(f"{field_name} must be finite, not NaN or infinity")

    return numeric_value


@dataclass(frozen=True, slots=True)
class Pose2D:
    """A 2D position in metres and orientation in radians."""

    x: float
    y: float
    yaw: float

    def __post_init__(self) -> None:
        """Validate and convert numeric values after creation."""

        object.__setattr__(self, "x", _require_finite_number("x", self.x))
        object.__setattr__(self, "y", _require_finite_number("y", self.y))
        object.__setattr__(self, "yaw", _require_finite_number("yaw", self.yaw))


@dataclass(frozen=True, slots=True)
class VelocityCommand:
    """Physical Mecanum velocity command expressed in the base_link frame.

    vx: forward/backward speed in m/s.
    vy: lateral speed in m/s; positive means robot-left in ROS base_link.
    wz: angular speed around z axis in rad/s; positive is counter-clockwise.
    """

    vx: float
    vy: float
    wz: float

    def __post_init__(self) -> None:
        """Validate and convert numeric values after creation."""

        object.__setattr__(self, "vx", _require_finite_number("vx", self.vx))
        object.__setattr__(self, "vy", _require_finite_number("vy", self.vy))
        object.__setattr__(self, "wz", _require_finite_number("wz", self.wz))