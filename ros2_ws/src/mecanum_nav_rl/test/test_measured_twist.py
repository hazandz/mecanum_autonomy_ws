"""Tests for core-only measured-twist feature extraction."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from mecanum_nav_rl.config.models import MotionLimitsConfig, ObservationConfig
from mecanum_nav_rl.observations.measured_twist import (
    MeasuredTwistFeatureExtractor,
    MeasuredTwistFeatureStatus,
)
from mecanum_nav_rl.simulation.simulated_odometry import (
    SimulatedOdometryMeasurement,
    SimulatedOdometrySnapshot,
    SimulatedOdometryStatus,
)


def _motion_limits() -> MotionLimitsConfig:
    """Return explicit test-only physical limits."""

    return MotionLimitsConfig(
        max_vx_mps=2.0,
        max_vy_mps=4.0,
        max_wz_radps=8.0,
    )


def _snapshot(
    *,
    status: SimulatedOdometryStatus = SimulatedOdometryStatus.VALID,
    vx_mps: float = 1.0,
    vy_mps: float = -2.0,
    wz_radps: float = 4.0,
) -> SimulatedOdometrySnapshot:
    """Build a policy-safe odometry snapshot for one extractor test."""

    measurement = None
    if status is SimulatedOdometryStatus.VALID:
        measurement = SimulatedOdometryMeasurement(
            x_m=0.0,
            y_m=0.0,
            yaw_rad=0.0,
            vx_mps=vx_mps,
            vy_mps=vy_mps,
            wz_radps=wz_radps,
        )
    return SimulatedOdometrySnapshot(
        timestamp_ns=1_000_000_000_000_000_001,
        status=status,
        sequence=7,
        measurement=measurement,
    )


def _extractor() -> MeasuredTwistFeatureExtractor:
    """Create an extractor with actual configuration-model instances."""

    return MeasuredTwistFeatureExtractor(ObservationConfig(), _motion_limits())


def test_normalizes_positive_and_negative_measured_twist() -> None:
    """Features use the supplied MotionLimitsConfig in fixed vx/vy/wz order."""

    result = _extractor().extract(_snapshot())

    assert result.status is MeasuredTwistFeatureStatus.READY
    assert result.ready is True
    assert result.timestamp_ns == 1_000_000_000_000_000_001
    assert result.odometry_sequence == 7
    assert result.features == pytest.approx((0.5, -0.5, 0.5))


@pytest.mark.parametrize(
    ("odometry_status", "expected_status"),
    (
        (
            SimulatedOdometryStatus.DELAYED,
            MeasuredTwistFeatureStatus.ODOMETRY_DELAYED,
        ),
        (
            SimulatedOdometryStatus.DROPPED,
            MeasuredTwistFeatureStatus.ODOMETRY_DROPPED,
        ),
    ),
)
def test_delayed_or_dropped_odometry_is_explicitly_non_ready(
    odometry_status: SimulatedOdometryStatus,
    expected_status: MeasuredTwistFeatureStatus,
) -> None:
    """Unavailable odometry must not become a stale or fabricated feature vector."""

    result = _extractor().extract(_snapshot(status=odometry_status))

    assert result.status is expected_status
    assert result.ready is False
    assert result.features is None


def test_invalid_feature_count_is_rejected_before_extraction() -> None:
    """The extractor rejects an observation configuration with the wrong block size."""

    valid_config = ObservationConfig()
    invalid_config = ObservationConfig.model_construct(
        lidar_sector_count=valid_config.lidar_sector_count,
        goal_feature_count=valid_config.goal_feature_count,
        measured_twist_feature_count=2,
        previous_command_feature_count=valid_config.previous_command_feature_count,
        dimension=valid_config.dimension,
    )

    with pytest.raises(ValueError, match="measured_twist_feature_count"):
        MeasuredTwistFeatureExtractor(invalid_config, _motion_limits())


@pytest.mark.parametrize("field_name", ("vx_mps", "vy_mps", "wz_radps"))
@pytest.mark.parametrize(
    "invalid_value",
    (float("nan"), float("inf"), float("-inf")),
)
def test_non_finite_measured_twist_is_rejected(
    field_name: str,
    invalid_value: float,
) -> None:
    """Defensive validation rejects invalid data even if an object was corrupted."""

    odometry = _snapshot()
    assert odometry.measurement is not None
    object.__setattr__(odometry.measurement, field_name, invalid_value)

    with pytest.raises(ValueError, match=field_name):
        _extractor().extract(odometry)


@pytest.mark.parametrize(
    ("component", "value", "expected_limit_name"),
    (
        ("vx_mps", 2.1, "max_vx_mps"),
        ("vy_mps", -4.1, "max_vy_mps"),
        ("wz_radps", 8.1, "max_wz_radps"),
    ),
)
def test_measured_twist_above_limit_is_rejected_without_clipping(
    component: str,
    value: float,
    expected_limit_name: str,
) -> None:
    """Out-of-contract measured motion fails closed instead of being clipped."""

    values = {"vx_mps": 1.0, "vy_mps": -2.0, "wz_radps": 4.0}
    values[component] = value

    with pytest.raises(ValueError, match=expected_limit_name):
        _extractor().extract(_snapshot(**values))


def test_production_module_has_no_runtime_or_ground_truth_imports() -> None:
    """Keep the extractor pure and prevent direct ground-truth access."""

    module_path = Path(__file__).parents[1] / "mecanum_nav_rl" / "observations" / "measured_twist.py"
    source = module_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_modules: list[str] = []
    imported_names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module is not None:
                imported_modules.append(node.module)
            imported_names.extend(alias.name for alias in node.names)

    forbidden = ("rclpy", "gazebo", "gz", "tf2", "gymnasium", "stable_baselines3")
    for imported_module in imported_modules:
        assert not imported_module.startswith(forbidden)
    assert "GroundTruthSample" not in imported_names
    assert "GroundTruthSample" not in source
