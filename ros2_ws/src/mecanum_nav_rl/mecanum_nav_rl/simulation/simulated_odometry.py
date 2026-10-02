"""Deterministic, policy-safe simulated odometry measurement emulator."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from enum import Enum
from math import isfinite, pi, tau
from numbers import Integral, Real
from random import Random

from mecanum_nav_rl.core.types import Pose2D, VelocityCommand


def _require_non_negative_finite(field_name: str, value: object) -> float:
    """Return a finite, non-negative float or raise a clear error."""

    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"{field_name} must be a real number")

    numeric_value = float(value)
    if not isfinite(numeric_value) or numeric_value < 0.0:
        raise ValueError(f"{field_name} must be finite and non-negative")

    return numeric_value


def _require_probability(field_name: str, value: object) -> float:
    """Return a finite probability in the closed unit interval."""

    probability = _require_non_negative_finite(field_name, value)
    if probability > 1.0:
        raise ValueError(f"{field_name} must be less than or equal to one")
    return probability


def _require_seed(seed: object) -> int:
    """Return an integer episode seed without accepting booleans."""

    if isinstance(seed, bool) or not isinstance(seed, Integral):
        raise TypeError("seed must be an integer")
    return int(seed)


def _require_timestamp_ns(timestamp_ns: object) -> int:
    """Return an exact, finite, non-negative integer nanosecond timestamp."""

    if isinstance(timestamp_ns, bool):
        raise TypeError("timestamp_ns must be a finite integer nanosecond value")

    if isinstance(timestamp_ns, Integral):
        integer_timestamp = int(timestamp_ns)
        if integer_timestamp < 0:
            raise ValueError("timestamp_ns must be non-negative")
        return integer_timestamp

    if not isinstance(timestamp_ns, Real):
        raise TypeError("timestamp_ns must be a finite integer nanosecond value")

    numeric_timestamp = float(timestamp_ns)
    if not isfinite(numeric_timestamp):
        raise ValueError("timestamp_ns must be finite")
    if numeric_timestamp < 0.0:
        raise ValueError("timestamp_ns must be non-negative")
    if numeric_timestamp > 2**53:
        raise ValueError(
            "non-integral timestamp_ns values above 2**53 are not exact"
        )
    if not numeric_timestamp.is_integer():
        raise ValueError("timestamp_ns must be an integer nanosecond value")
    return int(numeric_timestamp)


def normalize_yaw(yaw_rad: float) -> float:
    """Normalize a finite yaw angle into the half-open interval [-pi, pi)."""

    if not isfinite(yaw_rad):
        raise ValueError("yaw_rad must be finite")
    return (yaw_rad + pi) % tau - pi


class SimulatedOdometryStatus(str, Enum):
    """Explicit delivery status for one emulator step result."""

    VALID = "valid"
    DELAYED = "delayed"
    DROPPED = "dropped"


@dataclass(frozen=True, slots=True)
class GroundTruthSample:
    """Internal simulator input: true pose and base-frame twist at one time."""

    timestamp_ns: object
    pose: Pose2D
    twist: VelocityCommand


@dataclass(frozen=True, slots=True)
class SimulatedOdometryNoiseConfig:
    """Explicit episode noise inputs; callers choose every parameter."""

    position_bias_stddev_m: float
    yaw_bias_stddev_rad: float
    position_drift_stddev_m_per_step: float
    yaw_drift_stddev_rad_per_step: float
    velocity_noise_stddev_mps: float
    yaw_rate_noise_stddev_radps: float
    delay_samples: int
    dropout_probability: float

    def __post_init__(self) -> None:
        """Validate explicit simulation-only noise inputs."""

        for field_name in (
            "position_bias_stddev_m",
            "yaw_bias_stddev_rad",
            "position_drift_stddev_m_per_step",
            "yaw_drift_stddev_rad_per_step",
            "velocity_noise_stddev_mps",
            "yaw_rate_noise_stddev_radps",
        ):
            object.__setattr__(
                self,
                field_name,
                _require_non_negative_finite(field_name, getattr(self, field_name)),
            )

        if isinstance(self.delay_samples, bool) or not isinstance(
            self.delay_samples, Integral
        ):
            raise TypeError("delay_samples must be an integer")
        if self.delay_samples < 0:
            raise ValueError("delay_samples must be non-negative")
        object.__setattr__(self, "delay_samples", int(self.delay_samples))
        object.__setattr__(
            self,
            "dropout_probability",
            _require_probability("dropout_probability", self.dropout_probability),
        )


@dataclass(frozen=True, slots=True)
class SimulatedOdometryMeasurement:
    """Policy-safe noisy pose and measured twist with no ground-truth link."""

    x_m: float
    y_m: float
    yaw_rad: float
    vx_mps: float
    vy_mps: float
    wz_radps: float

    def __post_init__(self) -> None:
        """Validate and normalize independently copied measurement values."""

        for field_name in ("x_m", "y_m", "vx_mps", "vy_mps", "wz_radps"):
            value = getattr(self, field_name)
            if isinstance(value, bool) or not isinstance(value, Real):
                raise TypeError(f"{field_name} must be a real number")
            numeric_value = float(value)
            if not isfinite(numeric_value):
                raise ValueError(f"{field_name} must be finite")
            object.__setattr__(self, field_name, numeric_value)

        if isinstance(self.yaw_rad, bool) or not isinstance(self.yaw_rad, Real):
            raise TypeError("yaw_rad must be a real number")
        object.__setattr__(self, "yaw_rad", normalize_yaw(float(self.yaw_rad)))


@dataclass(frozen=True, slots=True)
class SimulatedOdometrySnapshot:
    """One policy-safe delivery result without a raw ground-truth reference."""

    timestamp_ns: int
    status: SimulatedOdometryStatus
    sequence: int
    measurement: SimulatedOdometryMeasurement | None

    def __post_init__(self) -> None:
        """Enforce unambiguous status and measurement combinations."""

        object.__setattr__(self, "timestamp_ns", _require_timestamp_ns(self.timestamp_ns))
        if isinstance(self.sequence, bool) or not isinstance(self.sequence, Integral):
            raise TypeError("sequence must be an integer")
        if self.sequence < 0:
            raise ValueError("sequence must be non-negative")
        object.__setattr__(self, "sequence", int(self.sequence))

        if not isinstance(self.status, SimulatedOdometryStatus):
            raise TypeError("status must be a SimulatedOdometryStatus")
        if self.status is SimulatedOdometryStatus.VALID:
            if not isinstance(self.measurement, SimulatedOdometryMeasurement):
                raise TypeError("a valid snapshot requires a measurement")
        elif self.measurement is not None:
            raise ValueError("delayed and dropped snapshots must not carry a measurement")

    @property
    def valid(self) -> bool:
        """Return whether this snapshot carries one usable measurement."""

        return self.status is SimulatedOdometryStatus.VALID


@dataclass(frozen=True, slots=True)
class _QueuedMeasurement:
    """Internal delayed-delivery record; never exposed to policy consumers."""

    timestamp_ns: int
    sequence: int
    measurement: SimulatedOdometryMeasurement | None


class SimulatedOdometryEmulator:
    """Create delayed, dropped, noisy policy measurements from internal truth."""

    def __init__(self) -> None:
        """Create an unconfigured emulator that must be reset before use."""

        self._rng: Random | None = None
        self._config: SimulatedOdometryNoiseConfig | None = None
        self._last_timestamp_ns: int | None = None
        self._sequence = 0
        self._position_bias_x_m = 0.0
        self._position_bias_y_m = 0.0
        self._yaw_bias_rad = 0.0
        self._position_drift_x_m = 0.0
        self._position_drift_y_m = 0.0
        self._yaw_drift_rad = 0.0
        self._delay_queue: deque[_QueuedMeasurement] = deque()

    def reset(self, seed: int, config: SimulatedOdometryNoiseConfig) -> None:
        """Start a deterministic episode and clear all prior emulator state."""

        if not isinstance(config, SimulatedOdometryNoiseConfig):
            raise TypeError("config must be a SimulatedOdometryNoiseConfig")

        self._rng = Random(_require_seed(seed))
        self._config = config
        self._last_timestamp_ns = None
        self._sequence = 0
        self._position_bias_x_m = self._rng.gauss(
            0.0, config.position_bias_stddev_m
        )
        self._position_bias_y_m = self._rng.gauss(
            0.0, config.position_bias_stddev_m
        )
        self._yaw_bias_rad = self._rng.gauss(0.0, config.yaw_bias_stddev_rad)
        self._position_drift_x_m = 0.0
        self._position_drift_y_m = 0.0
        self._yaw_drift_rad = 0.0
        self._delay_queue.clear()

    def step(self, ground_truth_sample: GroundTruthSample) -> SimulatedOdometrySnapshot:
        """Return one explicit valid, delayed, or dropped policy-safe snapshot."""

        if not isinstance(ground_truth_sample, GroundTruthSample):
            raise TypeError("ground_truth_sample must be a GroundTruthSample")
        if not isinstance(ground_truth_sample.pose, Pose2D):
            raise TypeError("ground_truth_sample.pose must be a Pose2D")
        if not isinstance(ground_truth_sample.twist, VelocityCommand):
            raise TypeError("ground_truth_sample.twist must be a VelocityCommand")
        if self._rng is None or self._config is None:
            raise RuntimeError("reset must be called before step")

        timestamp_ns = _require_timestamp_ns(ground_truth_sample.timestamp_ns)
        if (
            self._last_timestamp_ns is not None
            and timestamp_ns <= self._last_timestamp_ns
        ):
            raise ValueError("timestamp_ns must be strictly monotonic")

        self._last_timestamp_ns = timestamp_ns
        self._sequence += 1
        queued_measurement = self._make_queued_measurement(
            ground_truth_sample,
            timestamp_ns,
            self._sequence,
        )
        self._delay_queue.append(queued_measurement)

        if len(self._delay_queue) <= self._config.delay_samples:
            return SimulatedOdometrySnapshot(
                timestamp_ns=timestamp_ns,
                status=SimulatedOdometryStatus.DELAYED,
                sequence=self._sequence,
                measurement=None,
            )

        delivered = self._delay_queue.popleft()
        if delivered.measurement is None:
            return SimulatedOdometrySnapshot(
                timestamp_ns=delivered.timestamp_ns,
                status=SimulatedOdometryStatus.DROPPED,
                sequence=delivered.sequence,
                measurement=None,
            )
        return SimulatedOdometrySnapshot(
            timestamp_ns=delivered.timestamp_ns,
            status=SimulatedOdometryStatus.VALID,
            sequence=delivered.sequence,
            measurement=delivered.measurement,
        )

    def _make_queued_measurement(
        self,
        ground_truth_sample: GroundTruthSample,
        timestamp_ns: int,
        sequence: int,
    ) -> _QueuedMeasurement:
        """Sample one independent measurement or explicit dropout record."""

        assert self._rng is not None
        assert self._config is not None

        self._position_drift_x_m += self._rng.gauss(
            0.0, self._config.position_drift_stddev_m_per_step
        )
        self._position_drift_y_m += self._rng.gauss(
            0.0, self._config.position_drift_stddev_m_per_step
        )
        self._yaw_drift_rad += self._rng.gauss(
            0.0, self._config.yaw_drift_stddev_rad_per_step
        )

        if self._rng.random() < self._config.dropout_probability:
            return _QueuedMeasurement(timestamp_ns, sequence, None)

        pose = ground_truth_sample.pose
        twist = ground_truth_sample.twist
        measurement = SimulatedOdometryMeasurement(
            x_m=pose.x + self._position_bias_x_m + self._position_drift_x_m,
            y_m=pose.y + self._position_bias_y_m + self._position_drift_y_m,
            yaw_rad=normalize_yaw(
                pose.yaw + self._yaw_bias_rad + self._yaw_drift_rad
            ),
            vx_mps=twist.vx
            + self._rng.gauss(0.0, self._config.velocity_noise_stddev_mps),
            vy_mps=twist.vy
            + self._rng.gauss(0.0, self._config.velocity_noise_stddev_mps),
            wz_radps=twist.wz
            + self._rng.gauss(0.0, self._config.yaw_rate_noise_stddev_radps),
        )
        return _QueuedMeasurement(timestamp_ns, sequence, measurement)
