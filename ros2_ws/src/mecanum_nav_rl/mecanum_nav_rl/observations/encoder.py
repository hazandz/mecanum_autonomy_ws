"""Core-only encoder for the immutable, configuration-owned PPO observation."""

from __future__ import annotations

from collections.abc import Sequence
from math import isfinite
from numbers import Real

from mecanum_nav_rl.config.models import ObservationConfig
from mecanum_nav_rl.observations.snapshot import (
    ObservationEncodingResult,
    ObservationEncodingStatus,
)
from mecanum_nav_rl.simulation.simulated_odometry import (
    SimulatedOdometrySnapshot,
    SimulatedOdometryStatus,
)


def _require_finite_feature_vector(
    field_name: str,
    values: object,
    expected_length: int,
) -> tuple[float, ...]:
    """Copy one fixed-size finite feature block or reject it fail-closed."""

    if isinstance(values, (str, bytes, bytearray)) or not isinstance(
        values, Sequence
    ):
        raise TypeError(f"{field_name} must be a sequence")
    if len(values) != expected_length:
        raise ValueError(f"{field_name} must contain {expected_length} values")

    copied_values: list[float] = []
    for value in values:
        if isinstance(value, bool) or not isinstance(value, Real):
            raise TypeError(f"{field_name} values must be real numbers")
        numeric_value = float(value)
        if not isfinite(numeric_value):
            raise ValueError(f"{field_name} values must be finite")
        copied_values.append(numeric_value)
    return tuple(copied_values)


class ObservationEncoder:
    """Build a policy vector solely from policy-safe sensor-side measurements."""

    def __init__(self, config: ObservationConfig) -> None:
        """Bind one validated ObservationConfig as the sole schema source."""

        if not isinstance(config, ObservationConfig):
            raise TypeError("config must be an ObservationConfig")

        expected_dimension = (
            config.lidar_sector_count
            + config.goal_feature_count
            + config.measured_twist_feature_count
            + config.previous_command_feature_count
        )
        if config.dimension != expected_dimension:
            raise ValueError(
                "ObservationConfig dimension must equal the sum of its feature blocks"
            )

        self._config = config

    def encode(
        self,
        *,
        lidar_sectors: object,
        goal_features: object,
        odometry: SimulatedOdometrySnapshot,
        previous_normalized_command: object,
    ) -> ObservationEncodingResult:
        """Return a copied policy vector or an explicit non-ready odometry result."""

        lidar = _require_finite_feature_vector(
            "lidar_sectors", lidar_sectors, self._config.lidar_sector_count
        )
        goal = _require_finite_feature_vector(
            "goal_features", goal_features, self._config.goal_feature_count
        )
        previous_command = _require_finite_feature_vector(
            "previous_normalized_command",
            previous_normalized_command,
            self._config.previous_command_feature_count,
        )
        if any(value < -1.0 or value > 1.0 for value in previous_command):
            raise ValueError(
                "previous_normalized_command values must be in the closed interval [-1, 1]"
            )

        if not isinstance(odometry, SimulatedOdometrySnapshot):
            raise TypeError("odometry must be a SimulatedOdometrySnapshot")

        status_map = {
            SimulatedOdometryStatus.DELAYED: ObservationEncodingStatus.ODOMETRY_DELAYED,
            SimulatedOdometryStatus.DROPPED: ObservationEncodingStatus.ODOMETRY_DROPPED,
        }
        if odometry.status in status_map:
            return ObservationEncodingResult(
                status=status_map[odometry.status],
                timestamp_ns=odometry.timestamp_ns,
                odometry_sequence=odometry.sequence,
                vector=None,
            )

        if odometry.status is not SimulatedOdometryStatus.VALID:
            raise ValueError("odometry has an unsupported status")
        if odometry.measurement is None:
            raise ValueError("valid odometry must carry a measurement")

        measured_twist = (
            odometry.measurement.vx_mps,
            odometry.measurement.vy_mps,
            odometry.measurement.wz_radps,
        )
        measured_twist = _require_finite_feature_vector(
            "measured_twist",
            measured_twist,
            self._config.measured_twist_feature_count,
        )
        vector = lidar + goal + measured_twist + previous_command
        if len(vector) != self._config.dimension:
            raise RuntimeError(
                "encoded vector does not match the ObservationConfig dimension"
            )

        return ObservationEncodingResult(
            status=ObservationEncodingStatus.READY,
            timestamp_ns=odometry.timestamp_ns,
            odometry_sequence=odometry.sequence,
            vector=vector,
        )
