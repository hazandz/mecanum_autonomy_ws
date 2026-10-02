"""Unit tests for the pure, policy-safe 81-element observation encoder."""

from __future__ import annotations

import ast
import math
from pathlib import Path

import pytest

from mecanum_nav_rl.config.models import ObservationConfig
from mecanum_nav_rl.core.types import Pose2D, VelocityCommand
from mecanum_nav_rl.observations.encoder import ObservationEncoder
from mecanum_nav_rl.observations.snapshot import ObservationEncodingStatus
from mecanum_nav_rl.simulation.simulated_odometry import (
    GroundTruthSample,
    SimulatedOdometryMeasurement,
    SimulatedOdometrySnapshot,
    SimulatedOdometryStatus,
)


def _config() -> ObservationConfig:
    return ObservationConfig()


def _encoder(config: ObservationConfig | None = None) -> ObservationEncoder:
    return ObservationEncoder(_config() if config is None else config)


def _valid_odometry() -> SimulatedOdometrySnapshot:
    return SimulatedOdometrySnapshot(
        timestamp_ns=123,
        status=SimulatedOdometryStatus.VALID,
        sequence=9,
        measurement=SimulatedOdometryMeasurement(
            x_m=4.0,
            y_m=-5.0,
            yaw_rad=0.5,
            vx_mps=0.25,
            vy_mps=-0.5,
            wz_radps=0.75,
        ),
    )


def _encode(
    odometry: SimulatedOdometrySnapshot | object = None,
    config: ObservationConfig | None = None,
) -> object:
    observation_config = _config() if config is None else config
    return _encoder(observation_config).encode(
        lidar_sectors=tuple(
            float(index) for index in range(observation_config.lidar_sector_count)
        ),
        goal_features=(0.1, -0.2, 0.3),
        odometry=_valid_odometry() if odometry is None else odometry,
        previous_normalized_command=(-1.0, 0.0, 1.0),
    )


def test_vector_has_81_values_in_the_fixed_architecture_order() -> None:
    config = _config()
    result = _encode()

    assert result.status is ObservationEncodingStatus.READY
    assert result.ready is True
    assert result.vector is not None
    assert len(result.vector) == config.dimension == 81
    lidar_end = config.lidar_sector_count
    goal_end = lidar_end + config.goal_feature_count
    twist_end = goal_end + config.measured_twist_feature_count
    command_end = twist_end + config.previous_command_feature_count
    assert result.vector[:lidar_end] == tuple(float(index) for index in range(lidar_end))
    assert result.vector[lidar_end:goal_end] == (0.1, -0.2, 0.3)
    assert result.vector[goal_end:twist_end] == (0.25, -0.5, 0.75)
    assert result.vector[twist_end:command_end] == (-1.0, 0.0, 1.0)


def test_valid_simulated_odometry_is_the_measured_twist_source() -> None:
    result = _encode()

    assert result.vector is not None
    assert result.vector[75:78] == (0.25, -0.5, 0.75)
    assert result.timestamp_ns == 123
    assert result.odometry_sequence == 9


@pytest.mark.parametrize(
    ("odometry_status", "expected_status"),
    [
        (SimulatedOdometryStatus.DELAYED, ObservationEncodingStatus.ODOMETRY_DELAYED),
        (SimulatedOdometryStatus.DROPPED, ObservationEncodingStatus.ODOMETRY_DROPPED),
    ],
)
def test_delayed_or_dropped_odometry_never_falls_back_to_an_observation(
    odometry_status: SimulatedOdometryStatus,
    expected_status: ObservationEncodingStatus,
) -> None:
    result = _encode(
        SimulatedOdometrySnapshot(
            timestamp_ns=123,
            status=odometry_status,
            sequence=9,
            measurement=None,
        )
    )

    assert result.status is expected_status
    assert result.ready is False
    assert result.vector is None


def test_ground_truth_sample_is_not_an_encoder_input() -> None:
    ground_truth = GroundTruthSample(
        timestamp_ns=123,
        pose=Pose2D(x=1.0, y=2.0, yaw=0.0),
        twist=VelocityCommand(vx=0.1, vy=0.2, wz=0.3),
    )

    with pytest.raises(TypeError, match="SimulatedOdometrySnapshot"):
        _encode(ground_truth)


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("lidar_sectors", tuple(0.0 for _ in range(71))),
        ("goal_features", (0.0, 0.0)),
        ("previous_normalized_command", (0.0, 0.0)),
    ],
)
def test_wrong_feature_block_lengths_are_rejected(
    field_name: str,
    value: tuple[float, ...],
) -> None:
    config = _config()
    kwargs: dict[str, object] = {
        "lidar_sectors": tuple(0.0 for _ in range(config.lidar_sector_count)),
        "goal_features": (0.0, 0.0, 0.0),
        "odometry": _valid_odometry(),
        "previous_normalized_command": (0.0, 0.0, 0.0),
    }
    kwargs[field_name] = value

    with pytest.raises(ValueError):
        _encoder(config).encode(**kwargs)


@pytest.mark.parametrize("invalid_value", [math.nan, math.inf, -math.inf])
def test_nan_and_infinite_features_are_rejected(invalid_value: float) -> None:
    config = _config()
    with pytest.raises(ValueError):
        _encoder().encode(
            lidar_sectors=(invalid_value,)
            + tuple(0.0 for _ in range(config.lidar_sector_count - 1)),
            goal_features=(0.0, 0.0, 0.0),
            odometry=_valid_odometry(),
            previous_normalized_command=(0.0, 0.0, 0.0),
        )


@pytest.mark.parametrize("command", [(-1.1, 0.0, 0.0), (0.0, 0.0, 1.1)])
def test_out_of_range_normalized_command_is_rejected(
    command: tuple[float, float, float],
) -> None:
    with pytest.raises(ValueError, match=r"\[-1, 1\]"):
        _encoder().encode(
            lidar_sectors=tuple(0.0 for _ in range(72)),
            goal_features=(0.0, 0.0, 0.0),
            odometry=_valid_odometry(),
            previous_normalized_command=command,
        )


def test_encoder_rejects_a_constructed_config_with_inconsistent_dimension() -> None:
    config = _config()
    invalid_config = ObservationConfig.model_construct(
        lidar_sector_count=config.lidar_sector_count,
        goal_feature_count=config.goal_feature_count,
        measured_twist_feature_count=config.measured_twist_feature_count,
        previous_command_feature_count=config.previous_command_feature_count,
        dimension=config.dimension - 1,
    )

    with pytest.raises(ValueError, match="sum of its feature blocks"):
        ObservationEncoder(invalid_config)


def test_production_observation_sources_have_no_prohibited_runtime_or_truth_imports() -> None:
    observations_dir = Path(__file__).resolve().parents[1] / "mecanum_nav_rl" / "observations"
    prohibited_roots = {
        "rclpy",
        "tf2_ros",
        "geometry_msgs",
        "nav_msgs",
        "gazebo",
        "gz",
        "stable_baselines3",
        "gymnasium",
    }

    for source_path in observations_dir.glob("*.py"):
        source_text = source_path.read_text(encoding="utf-8")
        assert "GroundTruthSample" not in source_text, source_path
        tree = ast.parse(source_text)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots = {alias.name.split(".")[0] for alias in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                roots = {node.module.split(".")[0]}
            else:
                continue
            assert prohibited_roots.isdisjoint(roots), source_path
