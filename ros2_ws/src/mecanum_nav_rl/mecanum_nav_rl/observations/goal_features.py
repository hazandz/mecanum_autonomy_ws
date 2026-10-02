"""Core-only, policy-safe local-goal feature extraction."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import atan2, hypot, isfinite, pi, sin, cos, tau
from numbers import Integral, Real

from mecanum_nav_rl.config.models import ObservationConfig
from mecanum_nav_rl.simulation.simulated_odometry import (
    SimulatedOdometrySnapshot,
    SimulatedOdometryStatus,
)


def _require_finite_real(field_name: str, value: object) -> float:
    """Return a finite real value while rejecting booleans and invalid values."""

    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"{field_name} must be a real number")
    numeric_value = float(value)
    if not isfinite(numeric_value):
        raise ValueError(f"{field_name} must be finite")
    return numeric_value


def _normalize_angle(angle_rad: float) -> float:
    """Normalize a finite angle into the half-open interval ``[-pi, pi)``."""

    if not isfinite(angle_rad):
        raise ValueError("heading error must be finite")
    return (angle_rad + pi) % tau - pi


class GoalFeatureStatus(str, Enum):
    """Explicit availability status for one local-goal feature result."""

    READY = "ready"
    ODOMETRY_DELAYED = "odometry_delayed"
    ODOMETRY_DROPPED = "odometry_dropped"


@dataclass(frozen=True, slots=True)
class LocalGoal2D:
    """A policy-safe local goal expressed in the same odom frame as measurement."""

    x_m: float
    y_m: float

    def __post_init__(self) -> None:
        """Copy finite goal coordinates into an immutable value object."""

        object.__setattr__(self, "x_m", _require_finite_real("x_m", self.x_m))
        object.__setattr__(self, "y_m", _require_finite_real("y_m", self.y_m))


@dataclass(frozen=True, slots=True)
class GoalFeatureResult:
    """Three local-goal features or an explicit non-ready odometry status."""

    status: GoalFeatureStatus
    timestamp_ns: int
    odometry_sequence: int
    features: tuple[float, float, float] | None

    def __post_init__(self) -> None:
        """Keep result metadata and feature availability unambiguous."""

        if not isinstance(self.status, GoalFeatureStatus):
            raise TypeError("status must be a GoalFeatureStatus")
        for field_name in ("timestamp_ns", "odometry_sequence"):
            value = getattr(self, field_name)
            if isinstance(value, bool) or not isinstance(value, Integral):
                raise TypeError(f"{field_name} must be an integer")
            if value < 0:
                raise ValueError(f"{field_name} must be non-negative")
            object.__setattr__(self, field_name, int(value))

        if self.status is GoalFeatureStatus.READY:
            if self.features is None:
                raise ValueError("a ready result requires features")
        elif self.features is not None:
            raise ValueError("a non-ready result must not carry features")

        if self.features is not None:
            if len(self.features) != 3:
                raise ValueError("goal features must contain exactly three values")
            copied_features = tuple(
                _require_finite_real(f"features[{index}]", value)
                for index, value in enumerate(self.features)
            )
            object.__setattr__(self, "features", copied_features)

    @property
    def ready(self) -> bool:
        """Return whether this result carries usable goal features."""

        return self.status is GoalFeatureStatus.READY


class GoalFeatureExtractor:
    """Derive local-goal features from policy-safe odometry measurement only."""

    def __init__(self, config: ObservationConfig) -> None:
        """Bind the configuration that owns the fixed goal-feature cardinality."""

        if not isinstance(config, ObservationConfig):
            raise TypeError("config must be an ObservationConfig")
        if config.goal_feature_count != 3:
            raise ValueError("ObservationConfig goal_feature_count must be exactly three")
        self._config = config

    def extract(
        self,
        odometry: SimulatedOdometrySnapshot,
        local_goal: LocalGoal2D,
    ) -> GoalFeatureResult:
        """Return distance/sine/cosine features or an explicit non-ready result."""

        if not isinstance(odometry, SimulatedOdometrySnapshot):
            raise TypeError("odometry must be a SimulatedOdometrySnapshot")
        if not isinstance(local_goal, LocalGoal2D):
            raise TypeError("local_goal must be a LocalGoal2D")

        status_map = {
            SimulatedOdometryStatus.DELAYED: GoalFeatureStatus.ODOMETRY_DELAYED,
            SimulatedOdometryStatus.DROPPED: GoalFeatureStatus.ODOMETRY_DROPPED,
        }
        if odometry.status in status_map:
            return GoalFeatureResult(
                status=status_map[odometry.status],
                timestamp_ns=odometry.timestamp_ns,
                odometry_sequence=odometry.sequence,
                features=None,
            )

        if odometry.status is not SimulatedOdometryStatus.VALID:
            raise ValueError("odometry has an unsupported status")
        if odometry.measurement is None:
            raise ValueError("valid odometry must carry a measurement")

        measured_x_m = _require_finite_real("measurement.x_m", odometry.measurement.x_m)
        measured_y_m = _require_finite_real("measurement.y_m", odometry.measurement.y_m)
        measured_yaw_rad = _require_finite_real(
            "measurement.yaw_rad", odometry.measurement.yaw_rad
        )
        delta_x_m = local_goal.x_m - measured_x_m
        delta_y_m = local_goal.y_m - measured_y_m
        distance_m = hypot(delta_x_m, delta_y_m)
        if not isfinite(distance_m):
            raise ValueError("distance_m must be finite")

        if distance_m == 0.0:
            features = (0.0, 0.0, 1.0)
        else:
            heading_error_rad = _normalize_angle(
                atan2(delta_y_m, delta_x_m) - measured_yaw_rad
            )
            features = (
                distance_m,
                sin(heading_error_rad),
                cos(heading_error_rad),
            )

        if len(features) != self._config.goal_feature_count:
            raise RuntimeError("generated feature count does not match ObservationConfig")
        return GoalFeatureResult(
            status=GoalFeatureStatus.READY,
            timestamp_ns=odometry.timestamp_ns,
            odometry_sequence=odometry.sequence,
            features=features,
        )
