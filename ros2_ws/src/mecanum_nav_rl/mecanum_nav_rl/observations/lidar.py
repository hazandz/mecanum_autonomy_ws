"""Core-only angular binning from raw ranges into a policy LiDAR sector scan."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from math import isfinite, pi, tau
from numbers import Integral, Real

from mecanum_nav_rl.config.models import ObservationConfig


def _require_timestamp_ns(timestamp_ns: object) -> int:
    """Return an exact non-negative integer timestamp without float rounding."""

    if isinstance(timestamp_ns, bool):
        raise TypeError("timestamp_ns must be an integer nanosecond value")
    if isinstance(timestamp_ns, Integral):
        value = int(timestamp_ns)
        if value < 0:
            raise ValueError("timestamp_ns must be non-negative")
        return value
    if not isinstance(timestamp_ns, Real):
        raise TypeError("timestamp_ns must be an integer nanosecond value")

    value = float(timestamp_ns)
    if (
        not isfinite(value)
        or value < 0.0
        or value > 2**53
        or not value.is_integer()
    ):
        raise ValueError("timestamp_ns must be an exact, non-negative integer")
    return int(value)


def _require_finite_real(field_name: str, value: object) -> float:
    """Return one finite real value while rejecting booleans and non-finite data."""

    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"{field_name} must be a real number")
    numeric_value = float(value)
    if not isfinite(numeric_value):
        raise ValueError(f"{field_name} must be finite")
    return numeric_value


@dataclass(frozen=True, slots=True)
class RawLidarScan:
    """Immutable raw angular scan; ranges retain their raw ``+inf`` readings."""

    timestamp_ns: int
    angle_min_rad: float
    angle_increment_rad: float
    range_min_m: float
    range_max_m: float
    ranges: tuple[float, ...]

    def __post_init__(self) -> None:
        """Validate scan bounds and raw beam values before sectorization."""

        object.__setattr__(self, "timestamp_ns", _require_timestamp_ns(self.timestamp_ns))
        object.__setattr__(
            self,
            "angle_min_rad",
            _require_finite_real("angle_min_rad", self.angle_min_rad),
        )
        angle_increment_rad = _require_finite_real(
            "angle_increment_rad", self.angle_increment_rad
        )
        if angle_increment_rad == 0.0:
            raise ValueError("angle_increment_rad must be non-zero")
        object.__setattr__(self, "angle_increment_rad", angle_increment_rad)

        range_min_m = _require_finite_real("range_min_m", self.range_min_m)
        range_max_m = _require_finite_real("range_max_m", self.range_max_m)
        if range_min_m < 0.0 or range_max_m <= range_min_m:
            raise ValueError("range bounds must satisfy 0 <= min < max")
        object.__setattr__(self, "range_min_m", range_min_m)
        object.__setattr__(self, "range_max_m", range_max_m)

        if isinstance(self.ranges, (str, bytes, bytearray)) or not isinstance(
            self.ranges, Sequence
        ):
            raise TypeError("ranges must be a non-empty sequence")
        if not self.ranges:
            raise ValueError("ranges must not be empty")

        copied_ranges: list[float] = []
        for index, raw_range in enumerate(self.ranges):
            if isinstance(raw_range, bool) or not isinstance(raw_range, Real):
                raise TypeError(f"ranges[{index}] must be a real number")
            numeric_range = float(raw_range)
            if numeric_range == float("inf"):
                copied_ranges.append(numeric_range)
                continue
            if not isfinite(numeric_range):
                raise ValueError(f"ranges[{index}] must not be NaN or -inf")
            if numeric_range < range_min_m or numeric_range > range_max_m:
                raise ValueError(f"ranges[{index}] is outside the declared range bounds")
            copied_ranges.append(numeric_range)
        object.__setattr__(self, "ranges", tuple(copied_ranges))


@dataclass(frozen=True, slots=True)
class SectorLidarScan:
    """Immutable, finite policy-sector ranges in canonical increasing-angle order."""

    timestamp_ns: int
    sector_ranges_m: tuple[float, ...]

    def __post_init__(self) -> None:
        """Copy finite sector values and preserve the timestamp exactly."""

        object.__setattr__(self, "timestamp_ns", _require_timestamp_ns(self.timestamp_ns))
        if isinstance(self.sector_ranges_m, (str, bytes, bytearray)) or not isinstance(
            self.sector_ranges_m, Sequence
        ):
            raise TypeError("sector_ranges_m must be a sequence")

        copied_ranges: list[float] = []
        for index, sector_range in enumerate(self.sector_ranges_m):
            copied_ranges.append(
                _require_finite_real(f"sector_ranges_m[{index}]", sector_range)
            )
        object.__setattr__(self, "sector_ranges_m", tuple(copied_ranges))


class LidarAngularBinner:
    """Bin beams into configured sectors without using simulator or ROS objects.

    Sectors partition ``[-pi, pi)`` in increasing-angle order. Every beam angle
    is normalized into that interval, then assigned to its containing sector.
    Multiple beams in one sector use their minimum finite range. A raw ``+inf``
    beam means no in-range reflection and becomes ``range_max_m`` explicitly.

    This core requires coverage of every configured sector. Any empty sector
    raises ``ValueError`` rather than emitting a synthetic far range, so a
    partial scan cannot masquerade as a valid full-coverage sim_train scan.
    """

    def __init__(self, config: ObservationConfig) -> None:
        """Use the immutable observation config as the sole sector-count source."""

        if not isinstance(config, ObservationConfig):
            raise TypeError("config must be an ObservationConfig")
        if config.lidar_sector_count <= 0:
            raise ValueError("ObservationConfig lidar_sector_count must be positive")
        self._config = config

    def bin_scan(self, scan: RawLidarScan) -> SectorLidarScan:
        """Return one complete canonical sector scan or fail closed on a gap."""

        if not isinstance(scan, RawLidarScan):
            raise TypeError("scan must be a RawLidarScan")

        sector_count = self._config.lidar_sector_count
        sector_ranges: list[float | None] = [None] * sector_count
        for beam_index, raw_range in enumerate(scan.ranges):
            beam_angle = scan.angle_min_rad + beam_index * scan.angle_increment_rad
            if not isfinite(beam_angle):
                raise ValueError("beam angle is not finite")
            normalized_angle = (beam_angle + pi) % tau - pi
            sector_index = int(((normalized_angle + pi) / tau) * sector_count)
            sector_index = min(sector_index, sector_count - 1)

            normalized_range = (
                scan.range_max_m if raw_range == float("inf") else raw_range
            )
            existing_range = sector_ranges[sector_index]
            if existing_range is None or normalized_range < existing_range:
                sector_ranges[sector_index] = normalized_range

        if any(sector_range is None for sector_range in sector_ranges):
            raise ValueError(
                "scan does not cover every configured lidar sector; refusing partial coverage"
            )

        return SectorLidarScan(
            timestamp_ns=scan.timestamp_ns,
            sector_ranges_m=tuple(
                sector_range for sector_range in sector_ranges if sector_range is not None
            ),
        )
