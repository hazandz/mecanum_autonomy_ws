"""Core-only assembly of one policy-safe exact pair into a PPO observation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite
from numbers import Integral, Real

from mecanum_nav_rl.config.models import ResolvedConfig
from mecanum_nav_rl.observations.encoder import ObservationEncoder
from mecanum_nav_rl.observations.goal_features import GoalFeatureExtractor, LocalGoal2D
from mecanum_nav_rl.observations.lidar import LidarAngularBinner
from mecanum_nav_rl.observations.measured_twist import MeasuredTwistFeatureExtractor
from mecanum_nav_rl.observations.previous_command import (
    PreviousCommandFeatureExtractor,
    PreviousNormalizedCommand,
)
from mecanum_nav_rl.observations.synchronizer import SynchronizedSensorInput
from mecanum_nav_rl.simulation.simulated_odometry import SimulatedOdometryStatus


class ObservationAssemblyStatus(str, Enum):
    """Explicit result of assembling one policy observation candidate."""

    READY = "ready"
    SYNCHRONIZED_INPUT_NOT_READY = "synchronized_input_not_ready"
    SYNCHRONIZED_INPUT_INVALID = "synchronized_input_invalid"
    LIDAR_INVALID = "lidar_invalid"
    GOAL_INVALID = "goal_invalid"
    GOAL_NOT_READY = "goal_not_ready"
    MEASURED_TWIST_INVALID = "measured_twist_invalid"
    MEASURED_TWIST_NOT_READY = "measured_twist_not_ready"
    PREVIOUS_COMMAND_INVALID = "previous_command_invalid"
    ENCODER_INVALID = "encoder_invalid"
    ENCODER_NOT_READY = "encoder_not_ready"
    DIMENSION_MISMATCH = "dimension_mismatch"


def _optional_non_negative_integer(field_name: str, value: int | None) -> int | None:
    """Validate optional result provenance without inventing a sentinel value."""

    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise TypeError(f"{field_name} must be an integer or None")
    integer_value = int(value)
    if integer_value < 0:
        raise ValueError(f"{field_name} must be non-negative")
    return integer_value


@dataclass(frozen=True, slots=True)
class ObservationAssemblyResult:
    """An immutable policy vector or an explicit fail-closed assembly status."""

    status: ObservationAssemblyStatus
    timestamp_ns: int | None
    odometry_sequence: int | None
    vector: tuple[float, ...] | None

    def __post_init__(self) -> None:
        """Keep ready/non-ready output and policy values unambiguous."""

        if not isinstance(self.status, ObservationAssemblyStatus):
            raise TypeError("status must be an ObservationAssemblyStatus")
        object.__setattr__(
            self, "timestamp_ns", _optional_non_negative_integer("timestamp_ns", self.timestamp_ns)
        )
        object.__setattr__(
            self,
            "odometry_sequence",
            _optional_non_negative_integer("odometry_sequence", self.odometry_sequence),
        )

        if self.status is ObservationAssemblyStatus.READY:
            if self.timestamp_ns is None or self.odometry_sequence is None or self.vector is None:
                raise ValueError("a ready assembly result requires provenance and a vector")
        elif self.vector is not None:
            raise ValueError("a non-ready assembly result must not carry a vector")

        if self.vector is not None:
            copied_vector: list[float] = []
            for index, value in enumerate(self.vector):
                if isinstance(value, bool) or not isinstance(value, Real):
                    raise TypeError(f"vector[{index}] must be a real number")
                numeric_value = float(value)
                if not isfinite(numeric_value):
                    raise ValueError(f"vector[{index}] must be finite")
                copied_vector.append(numeric_value)
            object.__setattr__(self, "vector", tuple(copied_vector))

    @property
    def ready(self) -> bool:
        """Return whether an 81-element policy observation is present."""

        return self.status is ObservationAssemblyStatus.READY


class ObservationAssembler:
    """Compose existing policy-safe feature blocks without runtime ownership."""

    def __init__(self, config: ResolvedConfig) -> None:
        """Bind all schema and motion-limit inputs from one resolved config."""

        if not isinstance(config, ResolvedConfig):
            raise TypeError("config must be a ResolvedConfig")
        self._config = config
        self._lidar_binner = LidarAngularBinner(config.observation)
        self._goal_extractor = GoalFeatureExtractor(config.observation)
        self._measured_twist_extractor = MeasuredTwistFeatureExtractor(
            config.observation, config.motion_limits
        )
        self._previous_command_extractor = PreviousCommandFeatureExtractor(
            config.observation, config.action
        )
        self._encoder = ObservationEncoder(config.observation)

    def assemble(
        self,
        synchronized_input: SynchronizedSensorInput | None,
        local_goal: LocalGoal2D,
        previous_command: PreviousNormalizedCommand,
    ) -> ObservationAssemblyResult:
        """Assemble only one exact valid pair; never synthesize unavailable data."""

        if synchronized_input is None:
            return ObservationAssemblyResult(
                ObservationAssemblyStatus.SYNCHRONIZED_INPUT_NOT_READY,
                timestamp_ns=None,
                odometry_sequence=None,
                vector=None,
            )
        if not isinstance(synchronized_input, SynchronizedSensorInput):
            raise TypeError("synchronized_input must be a SynchronizedSensorInput or None")
        if not isinstance(local_goal, LocalGoal2D):
            raise TypeError("local_goal must be a LocalGoal2D")
        if not isinstance(previous_command, PreviousNormalizedCommand):
            raise TypeError("previous_command must be a PreviousNormalizedCommand")

        odometry = synchronized_input.odometry
        timestamp_ns = odometry.timestamp_ns
        sequence = odometry.sequence
        if not self._is_policy_safe_exact_input(synchronized_input):
            return self._not_ready(
                ObservationAssemblyStatus.SYNCHRONIZED_INPUT_INVALID,
                timestamp_ns,
                sequence,
            )

        try:
            sector_scan = self._lidar_binner.bin_scan(synchronized_input.scan)
        except (TypeError, ValueError, RuntimeError):
            return self._not_ready(ObservationAssemblyStatus.LIDAR_INVALID, timestamp_ns, sequence)

        try:
            goal_result = self._goal_extractor.extract(odometry, local_goal)
        except (TypeError, ValueError, RuntimeError):
            return self._not_ready(ObservationAssemblyStatus.GOAL_INVALID, timestamp_ns, sequence)
        if not goal_result.ready or goal_result.features is None:
            return self._not_ready(ObservationAssemblyStatus.GOAL_NOT_READY, timestamp_ns, sequence)

        try:
            twist_result = self._measured_twist_extractor.extract(odometry)
        except (TypeError, ValueError, RuntimeError):
            return self._not_ready(
                ObservationAssemblyStatus.MEASURED_TWIST_INVALID, timestamp_ns, sequence
            )
        if not twist_result.ready or twist_result.features is None:
            return self._not_ready(
                ObservationAssemblyStatus.MEASURED_TWIST_NOT_READY, timestamp_ns, sequence
            )

        try:
            previous_result = self._previous_command_extractor.extract(previous_command)
        except (TypeError, ValueError, RuntimeError):
            return self._not_ready(
                ObservationAssemblyStatus.PREVIOUS_COMMAND_INVALID, timestamp_ns, sequence
            )

        try:
            encoded = self._encoder.encode(
                lidar_sectors=sector_scan.sector_ranges_m,
                goal_features=goal_result.features,
                odometry=odometry,
                previous_normalized_command=previous_result.features,
            )
        except (TypeError, ValueError, RuntimeError):
            return self._not_ready(ObservationAssemblyStatus.ENCODER_INVALID, timestamp_ns, sequence)
        if not encoded.ready or encoded.vector is None:
            return self._not_ready(ObservationAssemblyStatus.ENCODER_NOT_READY, timestamp_ns, sequence)
        if len(encoded.vector) != self._config.observation.dimension:
            return self._not_ready(
                ObservationAssemblyStatus.DIMENSION_MISMATCH, timestamp_ns, sequence
            )

        return ObservationAssemblyResult(
            ObservationAssemblyStatus.READY,
            timestamp_ns=encoded.timestamp_ns,
            odometry_sequence=encoded.odometry_sequence,
            vector=encoded.vector,
        )

    @staticmethod
    def _not_ready(
        status: ObservationAssemblyStatus, timestamp_ns: int, sequence: int
    ) -> ObservationAssemblyResult:
        """Return a status-only result with known policy-safe provenance."""

        return ObservationAssemblyResult(status, timestamp_ns, sequence, None)

    @staticmethod
    def _is_policy_safe_exact_input(synchronized_input: SynchronizedSensorInput) -> bool:
        """Defend against manually constructed objects that bypass the exact gate."""

        odometry = synchronized_input.odometry
        scan_metadata = synchronized_input.scan_metadata
        odometry_metadata = synchronized_input.odometry_metadata
        return (
            odometry.status is SimulatedOdometryStatus.VALID
            and odometry.measurement is not None
            and synchronized_input.scan.timestamp_ns == odometry.timestamp_ns
            and scan_metadata.reset_epoch == odometry_metadata.reset_epoch
            and scan_metadata.runtime_generation == odometry_metadata.runtime_generation
            and scan_metadata.action_barrier_ros_ns == odometry_metadata.action_barrier_ros_ns
            and scan_metadata.reset_barrier_ros_ns == odometry_metadata.reset_barrier_ros_ns
            and synchronized_input.scan.timestamp_ns > scan_metadata.action_barrier_ros_ns
            and synchronized_input.scan.timestamp_ns > scan_metadata.reset_barrier_ros_ns
        )
