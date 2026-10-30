"""Typed simulation I/O boundaries with exact stamps and no GT policy data."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Generic, TypeVar


T = TypeVar('T')
MAX_PAIR_BUFFER = 64
PAIR_TOLERANCE_NS = 0


@dataclass(frozen=True)
class NoisyOdometrySample:
    """Carry one noisy odometry sample with its original source identity."""

    stamp_ns: int
    sequence: int
    status: str
    frame_id: str
    measured_twist: tuple[float, float, float] | None


@dataclass(frozen=True)
class ScanSample:
    """Carry one scan sample and its source frame and stamp."""

    stamp_ns: int
    frame_id: str
    ranges_m: tuple[float, ...]


@dataclass(frozen=True)
class ExactSensorPair:
    """Bind scan and noisy odometry with one exact source timestamp."""

    stamp_ns: int
    scan: ScanSample
    odometry: NoisyOdometrySample


class ExactTimestampPairer(Generic[T]):
    """Bounded exact-key join; never nearest-matches or edits timestamps."""

    def __init__(self, capacity: int = MAX_PAIR_BUFFER) -> None:
        """Create a bounded pairer with a validated capacity."""
        if type(capacity) is not int or not 1 <= capacity <= MAX_PAIR_BUFFER:
            raise ValueError(
                'pair buffer capacity must be within 1..64'
            )
        self._capacity = capacity
        self._items: dict[int, T] = {}

    def push(self, stamp_ns: int, item: T) -> None:
        """Store an item under its exact source timestamp."""
        if type(stamp_ns) is not int or stamp_ns < 0:
            raise ValueError(
                'timestamp must be a non-negative integer nanosecond'
            )
        if stamp_ns in self._items:
            raise ValueError('duplicate timestamp in exact-pair buffer')
        if len(self._items) >= self._capacity:
            raise OverflowError('exact-pair buffer overflow')
        self._items[stamp_ns] = item

    def pop(self, stamp_ns: int) -> T | None:
        """Remove and return the item with the exact timestamp, if present."""
        return self._items.pop(stamp_ns, None)

    def discard_before(self, cutoff_ns: int) -> tuple[int, ...]:
        """Drop older keys and return the dropped timestamps."""
        dropped = tuple(sorted(key for key in self._items if key < cutoff_ns))
        for key in dropped:
            del self._items[key]
        return dropped

    @property
    def size(self) -> int:
        """Return the current number of buffered timestamps."""
        return len(self._items)


def pair_exact(
    scan: ScanSample, odometry: NoisyOdometrySample,
) -> ExactSensorPair:
    """Validate and bind one scan with one exact-stamp odometry sample."""
    if scan.stamp_ns != odometry.stamp_ns:
        raise ValueError(
            'scan/noisy-odometry timestamp mismatch; tolerance is 0 ns'
        )
    if odometry.status != 'VALID' or odometry.measured_twist is None:
        raise ValueError(
            'delayed/dropped odometry has no current measurement'
        )
    if scan.frame_id != 'lidar_frame' or odometry.frame_id != 'base_link':
        raise ValueError(
            'scan/odometry frame does not match LOCAL_TRAINING contract'
        )
    if (
        len(odometry.measured_twist) != 3
        or not all(math.isfinite(v) for v in odometry.measured_twist)
    ):
        raise ValueError(
            'noisy measured twist must be exactly three finite values'
        )
    if not scan.ranges_m or any(
        not math.isfinite(value) for value in scan.ranges_m
    ):
        raise ValueError(
            'scan ranges must be non-empty and finite after source validation'
        )
    return ExactSensorPair(scan.stamp_ns, scan, odometry)


def validate_dual_clock_freshness(
    *, source_ros_ns: int, now_ros_ns: int, receive_steady_ns: int,
    now_steady_ns: int, max_age_ns: int,
) -> None:
    """Validate ROS source age and local steady receive age separately."""
    values = (
        source_ros_ns, now_ros_ns, receive_steady_ns, now_steady_ns,
        max_age_ns,
    )
    if any(type(value) is not int or value < 0 for value in values):
        raise ValueError('freshness timestamps must be non-negative')
    if (
        source_ros_ns > now_ros_ns
        or receive_steady_ns > now_steady_ns
    ):
        raise ValueError('future timestamps are invalid')
    if (
        now_ros_ns - source_ros_ns > max_age_ns
        or now_steady_ns - receive_steady_ns > max_age_ns
    ):
        raise ValueError('input exceeds ROS or local steady receive age')
