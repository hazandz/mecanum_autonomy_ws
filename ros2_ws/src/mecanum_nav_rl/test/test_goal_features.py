"""Unit tests for core-only, policy-safe local-goal features."""

from __future__ import annotations

import ast
from math import inf, nan, pi, sin, cos
from pathlib import Path

import pytest

from mecanum_nav_rl.config.models import ObservationConfig
from mecanum_nav_rl.observations.goal_features import (
    GoalFeatureExtractor,
    GoalFeatureStatus,
    LocalGoal2D,
)
from mecanum_nav_rl.simulation.simulated_odometry import (
    SimulatedOdometryMeasurement,
    SimulatedOdometrySnapshot,
    SimulatedOdometryStatus,
)


def _extractor() -> GoalFeatureExtractor:
    return GoalFeatureExtractor(ObservationConfig())


def _odometry(
    *,
    x_m: float = 0.0,
    y_m: float = 0.0,
    yaw_rad: float = 0.0,
    status: SimulatedOdometryStatus = SimulatedOdometryStatus.VALID,
) -> SimulatedOdometrySnapshot:
    measurement = None
    if status is SimulatedOdometryStatus.VALID:
        measurement = SimulatedOdometryMeasurement(
            x_m=x_m,
            y_m=y_m,
            yaw_rad=yaw_rad,
            vx_mps=0.0,
            vy_mps=0.0,
            wz_radps=0.0,
        )
    return SimulatedOdometrySnapshot(
        timestamp_ns=123,
        status=status,
        sequence=9,
        measurement=measurement,
    )


def test_straight_ahead_goal_has_distance_zero_sine_and_unit_cosine() -> None:
    result = _extractor().extract(_odometry(), LocalGoal2D(3.0, 0.0))

    assert result.status is GoalFeatureStatus.READY
    assert result.features == pytest.approx((3.0, 0.0, 1.0))


@pytest.mark.parametrize(
    ("local_goal", "expected_sine"),
    [
        (LocalGoal2D(0.0, 2.0), 1.0),
        (LocalGoal2D(0.0, -2.0), -1.0),
    ],
)
def test_left_and_right_goals_have_signed_heading_error(
    local_goal: LocalGoal2D,
    expected_sine: float,
) -> None:
    result = _extractor().extract(_odometry(), local_goal)

    assert result.features is not None
    assert result.features[0] == pytest.approx(2.0)
    assert result.features[1] == pytest.approx(expected_sine)
    assert result.features[2] == pytest.approx(0.0, abs=1e-12)


def test_goal_heading_respects_nonzero_robot_yaw() -> None:
    result = _extractor().extract(_odometry(yaw_rad=pi / 2.0), LocalGoal2D(2.0, 0.0))

    assert result.features == pytest.approx((2.0, -1.0, 0.0), abs=1e-12)


def test_heading_error_normalizes_across_pi_boundary() -> None:
    desired_heading = -pi + 0.1
    result = _extractor().extract(
        _odometry(yaw_rad=pi - 0.1),
        LocalGoal2D(cos(desired_heading), sin(desired_heading)),
    )

    assert result.features is not None
    assert result.features[0] == pytest.approx(1.0)
    assert result.features[1] == pytest.approx(sin(0.2))
    assert result.features[2] == pytest.approx(cos(0.2))


def test_goal_at_robot_position_uses_deterministic_heading_convention() -> None:
    result = _extractor().extract(
        _odometry(x_m=1.5, y_m=-2.0, yaw_rad=1.0),
        LocalGoal2D(1.5, -2.0),
    )

    assert result.features == (0.0, 0.0, 1.0)


@pytest.mark.parametrize(
    ("odometry_status", "expected_status"),
    [
        (SimulatedOdometryStatus.DELAYED, GoalFeatureStatus.ODOMETRY_DELAYED),
        (SimulatedOdometryStatus.DROPPED, GoalFeatureStatus.ODOMETRY_DROPPED),
    ],
)
def test_delayed_or_dropped_odometry_returns_non_ready_without_features(
    odometry_status: SimulatedOdometryStatus,
    expected_status: GoalFeatureStatus,
) -> None:
    result = _extractor().extract(_odometry(status=odometry_status), LocalGoal2D(1.0, 0.0))

    assert result.status is expected_status
    assert result.ready is False
    assert result.features is None


def test_non_three_goal_feature_config_is_rejected() -> None:
    config = ObservationConfig()
    invalid_config = ObservationConfig.model_construct(
        lidar_sector_count=config.lidar_sector_count,
        goal_feature_count=config.goal_feature_count - 1,
        measured_twist_feature_count=config.measured_twist_feature_count,
        previous_command_feature_count=config.previous_command_feature_count,
        dimension=config.dimension - 1,
    )

    with pytest.raises(ValueError, match="goal_feature_count"):
        GoalFeatureExtractor(invalid_config)


@pytest.mark.parametrize(
    ("goal_x_m", "goal_y_m"),
    [(nan, 0.0), (0.0, inf), (0.0, -inf)],
)
def test_non_finite_goal_coordinates_are_rejected(
    goal_x_m: float,
    goal_y_m: float,
) -> None:
    with pytest.raises(ValueError):
        LocalGoal2D(goal_x_m, goal_y_m)


@pytest.mark.parametrize("field_name", ["x_m", "y_m", "yaw_rad"])
def test_non_finite_measured_pose_or_yaw_is_rejected(field_name: str) -> None:
    odometry = _odometry()
    assert odometry.measurement is not None
    object.__setattr__(odometry.measurement, field_name, nan)

    with pytest.raises(ValueError, match=rf"measurement.{field_name}"):
        _extractor().extract(odometry, LocalGoal2D(1.0, 0.0))


def test_production_goal_feature_module_has_no_prohibited_runtime_or_truth_imports() -> None:
    source_path = Path(__file__).resolve().parents[1] / "mecanum_nav_rl" / "observations" / "goal_features.py"
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
