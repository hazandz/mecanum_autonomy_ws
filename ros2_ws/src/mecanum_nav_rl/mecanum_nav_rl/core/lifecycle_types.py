"""Shared pure value types for episode lifecycle identity and provenance."""

from __future__ import annotations

from dataclasses import dataclass
from numbers import Integral, Real
from math import isfinite
import re

_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")


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
class TransitionIdentity:
    """Caller-supplied identity for one step; core never generates its token."""

    identity: EpisodeLifecycleIdentity
    step_index: int
    transition_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.identity, EpisodeLifecycleIdentity):
            raise TypeError("identity must be an EpisodeLifecycleIdentity")
        object.__setattr__(
            self,
            "step_index",
            require_non_negative_integer("step_index", self.step_index),
        )
        if self.step_index == 0:
            raise ValueError("transition step_index must be positive")
        if not isinstance(self.transition_id, str) or not self.transition_id.strip():
            raise ValueError("transition_id must be a non-empty string")


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

