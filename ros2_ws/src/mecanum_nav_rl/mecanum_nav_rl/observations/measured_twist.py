"""Core-only, policy-safe measured-twist feature extraction."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite
from numbers import Integral, Real

from mecanum_nav_rl.config.models import MotionLimitsConfig, ObservationConfig
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


class MeasuredTwistFeatureStatus(str, Enum):
    """Explicit availability status for one measured-twist feature result."""

    READY = "ready"
    ODOMETRY_DELAYED = "odometry_delayed"
    ODOMETRY_DROPPED = "odometry_dropped"


@dataclass(frozen=True, slots=True)
class MeasuredTwistFeatureResult:
    """Three normalized measured-twist features or a non-ready result."""

    status: MeasuredTwistFeatureStatus
    timestamp_ns: int
    odometry_sequence: int
    features: tuple[float, float, float] | None

    def __post_init__(self) -> None:
        """Keep result metadata and feature availability unambiguous."""

        if not isinstance(self.status, MeasuredTwistFeatureStatus):
            raise TypeError("status must be a MeasuredTwistFeatureStatus")
        for field_name in ("timestamp_ns", "odometry_sequence"):
            value = getattr(self, field_name)
            if isinstance(value, bool) or not isinstance(value, Integral):
                raise TypeError(f"{field_name} must be an integer")
            if value < 0:
                raise ValueError(f"{field_name} must be non-negative")
            object.__setattr__(self, field_name, int(value))

        if self.status is MeasuredTwistFeatureStatus.READY:
            if self.features is None:
                raise ValueError("a ready result requires features")
        elif self.features is not None:
            raise ValueError("a non-ready result must not carry features")

        if self.features is not None:
            if len(self.features) != 3:
                raise ValueError(
                    "measured-twist features must contain exactly three values"
                )
            copied_features = tuple(
                _require_finite_real(f"features[{index}]", value)
                for index, value in enumerate(self.features)
            )
            object.__setattr__(self, "features", copied_features)

    @property
    def ready(self) -> bool:
        """Return whether this result carries usable measured-twist features."""

        return self.status is MeasuredTwistFeatureStatus.READY


class MeasuredTwistFeatureExtractor:
    """Normalize measured base-frame twist from policy-safe odometry only."""

    def __init__(
        self,
        observation_config: ObservationConfig,
        motion_limits: MotionLimitsConfig,
    ) -> None:
        """Bind the observation cardinality and physical motion limits."""

        if not isinstance(observation_config, ObservationConfig):
            raise TypeError("observation_config must be an ObservationConfig")
        if not isinstance(motion_limits, MotionLimitsConfig):
            raise TypeError("motion_limits must be a MotionLimitsConfig")
        if observation_config.measured_twist_feature_count != 3:
            raise ValueError(
                "ObservationConfig measured_twist_feature_count must be exactly three"
            )

        self._observation_config = observation_config
        self._motion_limits = motion_limits

    def extract(
        self,
        odometry: SimulatedOdometrySnapshot,
    ) -> MeasuredTwistFeatureResult:
        """Return normalized twist features or an explicit non-ready result."""

        if not isinstance(odometry, SimulatedOdometrySnapshot):
            raise TypeError("odometry must be a SimulatedOdometrySnapshot")

        status_map = {
            SimulatedOdometryStatus.DELAYED: (
                MeasuredTwistFeatureStatus.ODOMETRY_DELAYED
            ),
            SimulatedOdometryStatus.DROPPED: (
                MeasuredTwistFeatureStatus.ODOMETRY_DROPPED
            ),
        }
        if odometry.status in status_map:
            return MeasuredTwistFeatureResult(
                status=status_map[odometry.status],
                timestamp_ns=odometry.timestamp_ns,
                odometry_sequence=odometry.sequence,
                features=None,
            )

        if odometry.status is not SimulatedOdometryStatus.VALID:
            raise ValueError("odometry has an unsupported status")
        if odometry.measurement is None:
            raise ValueError("valid odometry must carry a measurement")

        measured_vx_mps = _require_finite_real(
            "measurement.vx_mps", odometry.measurement.vx_mps
        )
        measured_vy_mps = _require_finite_real(
            "measurement.vy_mps", odometry.measurement.vy_mps
        )
        measured_wz_radps = _require_finite_real(
            "measurement.wz_radps", odometry.measurement.wz_radps
        )

        limits = self._motion_limits
        if abs(measured_vx_mps) > limits.max_vx_mps:
            raise ValueError("measurement.vx_mps exceeds configured max_vx_mps")
        if abs(measured_vy_mps) > limits.max_vy_mps:
            raise ValueError("measurement.vy_mps exceeds configured max_vy_mps")
        if abs(measured_wz_radps) > limits.max_wz_radps:
            raise ValueError("measurement.wz_radps exceeds configured max_wz_radps")

        features = (
            measured_vx_mps / limits.max_vx_mps,
            measured_vy_mps / limits.max_vy_mps,
            measured_wz_radps / limits.max_wz_radps,
        )
        if len(features) != self._observation_config.measured_twist_feature_count:
            raise RuntimeError(
                "generated feature count does not match ObservationConfig"
            )
        return MeasuredTwistFeatureResult(
            status=MeasuredTwistFeatureStatus.READY,
            timestamp_ns=odometry.timestamp_ns,
            odometry_sequence=odometry.sequence,
            features=features,
        )
