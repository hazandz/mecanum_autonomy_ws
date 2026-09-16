"""Immutable sensor snapshots selected by the ROS synchronizer."""

from __future__ import annotations

from dataclasses import dataclass
from numbers import Integral

import numpy as np

from mecanum_nav_rl.core.frozen_array import (
    FrozenFloat32Array,
    freeze_float32_array,
)
from mecanum_nav_rl.core.types import Pose2D, VelocityCommand


def _require_non_negative_integer(field_name: str, value: object) -> int:
    """Return a non-negative integer or raise a clear error."""

    if isinstance(value, bool) or not isinstance(value, Integral):
        raise TypeError(f"{field_name} must be an integer")

    integer_value = int(value)

    if integer_value < 0:
        raise ValueError(f"{field_name} must be non-negative")

    return integer_value


@dataclass(frozen=True, slots=True)
class SensorSnapshot:
    """Immutable sensor state selected by the ROS synchronizer.

    The synchronizer is responsible for validating timestamp compatibility
    before creating this object.

    scan_ranges_m contains finite LiDAR ranges in metres. The ROS adapter must
    handle raw LaserScan invalid values before creating this snapshot.
    """

    reset_epoch: int
    runtime_generation: int

    scan_stamp_ns: int
    odom_stamp_ns: int

    pose: Pose2D
    measured_twist: VelocityCommand
    scan_ranges_m: FrozenFloat32Array

    def __post_init__(self) -> None:
        """Validate fields and freeze the LiDAR range array."""

        object.__setattr__(
            self,
            "reset_epoch",
            _require_non_negative_integer("reset_epoch", self.reset_epoch),
        )
        object.__setattr__(
            self,
            "runtime_generation",
            _require_non_negative_integer(
                "runtime_generation",
                self.runtime_generation,
            ),
        )
        object.__setattr__(
            self,
            "scan_stamp_ns",
            _require_non_negative_integer("scan_stamp_ns", self.scan_stamp_ns),
        )
        object.__setattr__(
            self,
            "odom_stamp_ns",
            _require_non_negative_integer("odom_stamp_ns", self.odom_stamp_ns),
        )

        if not isinstance(self.pose, Pose2D):
            raise TypeError("pose must be a Pose2D")

        if not isinstance(self.measured_twist, VelocityCommand):
            raise TypeError("measured_twist must be a VelocityCommand")

        frozen_scan_ranges_m = freeze_float32_array(
            self.scan_ranges_m,
            name="scan_ranges_m",
            expected_ndim=1,
        )

        if frozen_scan_ranges_m.size == 0:
            raise ValueError("scan_ranges_m must not be empty")

        if np.any(frozen_scan_ranges_m < 0.0):
            raise ValueError("scan_ranges_m must not contain negative ranges")

        object.__setattr__(self, "scan_ranges_m", frozen_scan_ranges_m)
