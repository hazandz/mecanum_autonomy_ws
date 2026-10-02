"""Core-only exact timestamp gate for policy-safe scan and odometry inputs.

This module deliberately has no queue, receive-age calculation, overflow
policy, runtime ingress adapter, or ROS/Gazebo dependency.  It evaluates one
caller-supplied scan/odometry candidate pair only.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from numbers import Integral

from mecanum_nav_rl.observations.lidar import RawLidarScan
from mecanum_nav_rl.simulation.simulated_odometry import (
    SimulatedOdometrySnapshot,
    SimulatedOdometryStatus,
)


def _require_non_negative_integer(field_name: str, value: object) -> int:
    """Return one exact, non-negative integer while rejecting booleans."""

    if isinstance(value, bool) or not isinstance(value, Integral):
        raise TypeError(f"{field_name} must be an integer")
    integer_value = int(value)
    if integer_value < 0:
        raise ValueError(f"{field_name} must be non-negative")
    return integer_value


class SynchronizationStatus(str, Enum):
    """Explicit result of one exact candidate-pair evaluation."""

    READY = "ready"
    ODOMETRY_DELAYED = "odometry_delayed"
    ODOMETRY_DROPPED = "odometry_dropped"
    LIFECYCLE_MISMATCH = "lifecycle_mismatch"
    ACTION_BARRIER_REJECTED = "action_barrier_rejected"
    RESET_BARRIER_REJECTED = "reset_barrier_rejected"
    TIMESTAMP_MISMATCH = "timestamp_mismatch"


@dataclass(frozen=True, slots=True)
class SynchronizationMetadata:
    """Caller-provided ingress and barrier metadata for one sensor candidate.

    ``received_steady_ns`` is carried unchanged for a future approved
    freshness policy.  This exact-pair gate intentionally does not compare it
    against a current time or another clock domain.
    """

    reset_epoch: int
    runtime_generation: int
    received_steady_ns: int
    action_barrier_ros_ns: int
    reset_barrier_ros_ns: int

    def __post_init__(self) -> None:
        """Reject missing, boolean, negative, or non-integral metadata."""

        for field_name in (
            "reset_epoch",
            "runtime_generation",
            "received_steady_ns",
            "action_barrier_ros_ns",
            "reset_barrier_ros_ns",
        ):
            object.__setattr__(
                self,
                field_name,
                _require_non_negative_integer(field_name, getattr(self, field_name)),
            )


@dataclass(frozen=True, slots=True)
class ActiveLifecycleContext:
    """Active caller-owned lifecycle values against which candidates are gated."""

    reset_epoch: int
    runtime_generation: int
    action_barrier_ros_ns: int
    reset_barrier_ros_ns: int

    def __post_init__(self) -> None:
        """Validate lifecycle context without inventing a runtime source."""

        for field_name in (
            "reset_epoch",
            "runtime_generation",
            "action_barrier_ros_ns",
            "reset_barrier_ros_ns",
        ):
            object.__setattr__(
                self,
                field_name,
                _require_non_negative_integer(field_name, getattr(self, field_name)),
            )


@dataclass(frozen=True, slots=True)
class SynchronizedSensorInput:
    """Policy-safe inputs for a single exact, valid sensor pair."""

    scan: RawLidarScan
    odometry: SimulatedOdometrySnapshot
    scan_metadata: SynchronizationMetadata
    odometry_metadata: SynchronizationMetadata

    def __post_init__(self) -> None:
        """Require only the types and validity allowed into a ready result."""

        if not isinstance(self.scan, RawLidarScan):
            raise TypeError("scan must be a RawLidarScan")
        if not isinstance(self.odometry, SimulatedOdometrySnapshot):
            raise TypeError("odometry must be a SimulatedOdometrySnapshot")
        if self.odometry.status is not SimulatedOdometryStatus.VALID:
            raise ValueError("a synchronized input requires valid odometry")
        if self.odometry.measurement is None:
            raise ValueError("a synchronized input requires an odometry measurement")
        if not isinstance(self.scan_metadata, SynchronizationMetadata):
            raise TypeError("scan_metadata must be a SynchronizationMetadata")
        if not isinstance(self.odometry_metadata, SynchronizationMetadata):
            raise TypeError("odometry_metadata must be a SynchronizationMetadata")


@dataclass(frozen=True, slots=True)
class SynchronizationResult:
    """A policy-safe exact pair or an explicit non-ready outcome."""

    status: SynchronizationStatus
    sensor_input: SynchronizedSensorInput | None

    def __post_init__(self) -> None:
        """Make a ready/non-ready result unambiguous and immutable."""

        if not isinstance(self.status, SynchronizationStatus):
            raise TypeError("status must be a SynchronizationStatus")
        if self.status is SynchronizationStatus.READY:
            if not isinstance(self.sensor_input, SynchronizedSensorInput):
                raise ValueError("a ready result requires synchronized sensor input")
        elif self.sensor_input is not None:
            raise ValueError("a non-ready result must not carry sensor input")

    @property
    def ready(self) -> bool:
        """Return whether this result carries one exact policy-safe pair."""

        return self.status is SynchronizationStatus.READY


class ExactSnapshotPairGate:
    """Evaluate exactly one scan/odometry candidate pair with zero tolerance."""

    def synchronize(
        self,
        scan: RawLidarScan,
        scan_metadata: SynchronizationMetadata,
        odometry: SimulatedOdometrySnapshot,
        odometry_metadata: SynchronizationMetadata,
        active_context: ActiveLifecycleContext,
    ) -> SynchronizationResult:
        """Return ready only for matching lifecycle, barriers, and exact stamps.

        The method never searches for a nearest candidate and never retains an
        older candidate.  Buffering, freshness, capacity, overflow, and ingress
        lifecycle ownership remain outside this deliberately narrow phase.
        """

        if not isinstance(scan, RawLidarScan):
            raise TypeError("scan must be a RawLidarScan")
        if not isinstance(scan_metadata, SynchronizationMetadata):
            raise TypeError("scan_metadata must be a SynchronizationMetadata")
        if not isinstance(odometry, SimulatedOdometrySnapshot):
            raise TypeError("odometry must be a SimulatedOdometrySnapshot")
        if not isinstance(odometry_metadata, SynchronizationMetadata):
            raise TypeError("odometry_metadata must be a SynchronizationMetadata")
        if not isinstance(active_context, ActiveLifecycleContext):
            raise TypeError("active_context must be an ActiveLifecycleContext")

        if odometry.status is SimulatedOdometryStatus.DELAYED:
            return SynchronizationResult(SynchronizationStatus.ODOMETRY_DELAYED, None)
        if odometry.status is SimulatedOdometryStatus.DROPPED:
            return SynchronizationResult(SynchronizationStatus.ODOMETRY_DROPPED, None)

        if not self._metadata_matches_active(scan_metadata, active_context) or not self._metadata_matches_active(
            odometry_metadata, active_context
        ):
            return SynchronizationResult(SynchronizationStatus.LIFECYCLE_MISMATCH, None)

        if not self._is_newer_than_barrier(
            scan.timestamp_ns, active_context.action_barrier_ros_ns
        ) or not self._is_newer_than_barrier(
            odometry.timestamp_ns, active_context.action_barrier_ros_ns
        ):
            return SynchronizationResult(SynchronizationStatus.ACTION_BARRIER_REJECTED, None)

        if not self._is_newer_than_barrier(
            scan.timestamp_ns, active_context.reset_barrier_ros_ns
        ) or not self._is_newer_than_barrier(
            odometry.timestamp_ns, active_context.reset_barrier_ros_ns
        ):
            return SynchronizationResult(SynchronizationStatus.RESET_BARRIER_REJECTED, None)

        if scan.timestamp_ns != odometry.timestamp_ns:
            return SynchronizationResult(SynchronizationStatus.TIMESTAMP_MISMATCH, None)

        return SynchronizationResult(
            SynchronizationStatus.READY,
            SynchronizedSensorInput(
                scan=scan,
                odometry=odometry,
                scan_metadata=scan_metadata,
                odometry_metadata=odometry_metadata,
            ),
        )

    @staticmethod
    def _metadata_matches_active(
        metadata: SynchronizationMetadata, active_context: ActiveLifecycleContext
    ) -> bool:
        """Require lifecycle and barrier provenance to match the active context."""

        return (
            metadata.reset_epoch == active_context.reset_epoch
            and metadata.runtime_generation == active_context.runtime_generation
            and metadata.action_barrier_ros_ns == active_context.action_barrier_ros_ns
            and metadata.reset_barrier_ros_ns == active_context.reset_barrier_ros_ns
        )

    @staticmethod
    def _is_newer_than_barrier(timestamp_ns: int, barrier_ros_ns: int) -> bool:
        """Apply the approved strict-after barrier rule in the ROS time domain."""

        return timestamp_ns > barrier_ros_ns
