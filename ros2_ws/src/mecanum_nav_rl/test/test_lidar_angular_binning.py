"""Unit tests for core-only LiDAR angular binning."""

from __future__ import annotations

import ast
from math import inf, nan, pi, tau
from pathlib import Path

import pytest

from mecanum_nav_rl.config.models import ObservationConfig
from mecanum_nav_rl.observations.lidar import (
    LidarAngularBinner,
    RawLidarScan,
)


def _config() -> ObservationConfig:
    return ObservationConfig()


def _binner() -> LidarAngularBinner:
    return LidarAngularBinner(_config())


def _full_circle_scan(
    beam_count: int,
    *,
    timestamp_ns: int = 123,
    angle_min_rad: float = -pi,
    ranges: tuple[float, ...] | None = None,
) -> RawLidarScan:
    return RawLidarScan(
        timestamp_ns=timestamp_ns,
        angle_min_rad=angle_min_rad,
        angle_increment_rad=tau / beam_count,
        range_min_m=0.1,
        range_max_m=10.0,
        ranges=(inf,) * beam_count if ranges is None else ranges,
    )


def test_full_circle_scan_matches_configured_sector_count() -> None:
    config = _config()

    sector_scan = _binner().bin_scan(_full_circle_scan(360))

    assert sector_scan.timestamp_ns == 123
    assert len(sector_scan.sector_ranges_m) == config.lidar_sector_count
    assert sector_scan.sector_ranges_m == (10.0,) * config.lidar_sector_count


def test_different_beam_counts_preserve_an_obstacle_at_the_same_angle() -> None:
    first_ranges = [inf] * 360
    first_ranges[180] = 2.5
    second_ranges = [inf] * 720
    second_ranges[360] = 2.5

    first = _binner().bin_scan(_full_circle_scan(360, ranges=tuple(first_ranges)))
    second = _binner().bin_scan(_full_circle_scan(720, ranges=tuple(second_ranges)))

    assert first.sector_ranges_m == second.sector_ranges_m


def test_multiple_beams_in_one_sector_keep_the_closest_obstacle() -> None:
    ranges = [inf] * 360
    ranges[180] = 4.0
    ranges[181] = 1.5

    sector_scan = _binner().bin_scan(_full_circle_scan(360, ranges=tuple(ranges)))

    zero_angle_sector = _config().lidar_sector_count // 2
    assert sector_scan.sector_ranges_m[zero_angle_sector] == pytest.approx(1.5)


def test_negative_pi_and_positive_pi_normalize_to_the_same_first_sector() -> None:
    negative_pi_ranges = [inf] * 360
    negative_pi_ranges[0] = 2.0
    positive_pi_ranges = [inf] * 360
    positive_pi_ranges[0] = 2.0

    negative_pi = _binner().bin_scan(
        _full_circle_scan(360, angle_min_rad=-pi, ranges=tuple(negative_pi_ranges))
    )
    positive_pi = _binner().bin_scan(
        _full_circle_scan(360, angle_min_rad=pi, ranges=tuple(positive_pi_ranges))
    )

    assert negative_pi.sector_ranges_m[0] == pytest.approx(2.0)
    assert positive_pi.sector_ranges_m[0] == pytest.approx(2.0)


def test_positive_infinity_means_explicit_no_reflection_at_range_max() -> None:
    sector_scan = _binner().bin_scan(_full_circle_scan(360))

    assert all(value == 10.0 for value in sector_scan.sector_ranges_m)


@pytest.mark.parametrize(
    "scan_kwargs",
    [
        {"ranges": (nan,)},
        {"ranges": (-inf,)},
        {"ranges": (-1.0,)},
        {"angle_increment_rad": 0.0, "ranges": (1.0,)},
        {"angle_increment_rad": nan, "ranges": (1.0,)},
        {"range_min_m": 2.0, "range_max_m": 2.0, "ranges": (2.0,)},
    ],
)
def test_invalid_raw_scan_values_are_rejected(scan_kwargs: dict[str, object]) -> None:
    values: dict[str, object] = {
        "timestamp_ns": 1,
        "angle_min_rad": 0.0,
        "angle_increment_rad": 0.1,
        "range_min_m": 0.1,
        "range_max_m": 10.0,
        "ranges": (1.0,),
    }
    values.update(scan_kwargs)

    with pytest.raises((TypeError, ValueError)):
        RawLidarScan(**values)  # type: ignore[arg-type]


def test_partial_sector_coverage_is_rejected_instead_of_filling_empty_sectors() -> None:
    scan = _full_circle_scan(36)

    with pytest.raises(ValueError, match="does not cover every configured lidar sector"):
        _binner().bin_scan(scan)


def test_dense_half_field_of_view_is_rejected_for_missing_sector_coverage() -> None:
    # 360 beams are dense, but this scan spans only 180 degrees and leaves a blind half.
    scan = RawLidarScan(
        timestamp_ns=123,
        angle_min_rad=-pi / 2.0,
        angle_increment_rad=pi / 360.0,
        range_min_m=0.1,
        range_max_m=10.0,
        ranges=(inf,) * 360,
    )

    with pytest.raises(ValueError, match="does not cover every configured lidar sector"):
        _binner().bin_scan(scan)


def test_large_integer_nanosecond_timestamp_is_preserved_exactly() -> None:
    timestamp_ns = 1_000_000_000_000_000_001

    sector_scan = _binner().bin_scan(_full_circle_scan(360, timestamp_ns=timestamp_ns))

    assert sector_scan.timestamp_ns == timestamp_ns


def test_production_lidar_module_has_no_prohibited_runtime_or_truth_imports() -> None:
    source_path = Path(__file__).resolve().parents[1] / "mecanum_nav_rl" / "observations" / "lidar.py"
    source_text = source_path.read_text(encoding="utf-8")
    prohibited_roots = {
        "rclpy",
        "tf2_ros",
        "geometry_msgs",
        "sensor_msgs",
        "nav_msgs",
        "gazebo",
        "gz",
        "stable_baselines3",
        "gymnasium",
    }

    assert "GroundTruthSample" not in source_text
    tree = ast.parse(source_text)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots = {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            roots = {node.module.split(".")[0]}
        else:
            continue
        assert prohibited_roots.isdisjoint(roots), source_path
