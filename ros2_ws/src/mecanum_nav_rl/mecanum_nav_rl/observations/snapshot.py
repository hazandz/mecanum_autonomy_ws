"""Typed outputs for the policy-safe observation encoder."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite
from numbers import Integral, Real


class ObservationEncodingStatus(str, Enum):
    """Explicit availability state of one policy observation result."""

    READY = "ready"
    ODOMETRY_DELAYED = "odometry_delayed"
    ODOMETRY_DROPPED = "odometry_dropped"


@dataclass(frozen=True, slots=True)
class ObservationEncodingResult:
    """A copied policy vector or an explicit non-ready odometry status."""

    status: ObservationEncodingStatus
    timestamp_ns: int
    odometry_sequence: int
    vector: tuple[float, ...] | None

    def __post_init__(self) -> None:
        """Reject ambiguous status/vector combinations and invalid metadata."""

        if not isinstance(self.status, ObservationEncodingStatus):
            raise TypeError("status must be an ObservationEncodingStatus")

        for field_name in ("timestamp_ns", "odometry_sequence"):
            value = getattr(self, field_name)
            if isinstance(value, bool) or not isinstance(value, Integral):
                raise TypeError(f"{field_name} must be an integer")
            if value < 0:
                raise ValueError(f"{field_name} must be non-negative")
            object.__setattr__(self, field_name, int(value))

        if self.status is ObservationEncodingStatus.READY:
            if self.vector is None:
                raise ValueError("a ready result requires an observation vector")
        elif self.vector is not None:
            raise ValueError("a non-ready result must not carry an observation vector")

        if self.vector is not None:
            copied_vector: list[float] = []
            for value in self.vector:
                if isinstance(value, bool) or not isinstance(value, Real):
                    raise TypeError("observation vector values must be real numbers")
                numeric_value = float(value)
                if not isfinite(numeric_value):
                    raise ValueError("observation vector values must be finite")
                copied_vector.append(numeric_value)
            object.__setattr__(self, "vector", tuple(copied_vector))

    @property
    def ready(self) -> bool:
        """Return whether this result carries a policy observation vector."""

        return self.status is ObservationEncodingStatus.READY
