"""Unit tests for the core-only simulated odometry emulator."""

from __future__ import annotations

import ast
import math
from dataclasses import fields
from pathlib import Path

import pytest

from mecanum_nav_rl.core.types import Pose2D, VelocityCommand
from mecanum_nav_rl.simulation.simulated_odometry import (
    GroundTruthSample,
    SimulatedOdometryEmulator,
    SimulatedOdometryNoiseConfig,
    SimulatedOdometryStatus,
)


def _config(**overrides: object) -> SimulatedOdometryNoiseConfig:
    values: dict[str, object] = {
        "position_bias_stddev_m": 0.0,
        "yaw_bias_stddev_rad": 0.0,
        "position_drift_stddev_m_per_step": 0.0,
        "yaw_drift_stddev_rad_per_step": 0.0,
        "velocity_noise_stddev_mps": 0.0,
        "yaw_rate_noise_stddev_radps": 0.0,
        "delay_samples": 0,
        "dropout_probability": 0.0,
    }
    values.update(overrides)
    return SimulatedOdometryNoiseConfig(**values)  # type: ignore[arg-type]


def _sample(timestamp_ns: object, yaw_rad: float = 0.25) -> GroundTruthSample:
    return GroundTruthSample(
        timestamp_ns=timestamp_ns,
        pose=Pose2D(x=1.25, y=-2.5, yaw=yaw_rad),
        twist=VelocityCommand(vx=0.4, vy=-0.2, wz=0.3),
    )


def _trace() -> list[GroundTruthSample]:
    return [_sample(100), _sample(200, 0.5), _sample(300, -0.5)]


def _run_trace(seed: int, config: SimulatedOdometryNoiseConfig) -> list[object]:
    emulator = SimulatedOdometryEmulator()
    emulator.reset(seed, config)
    return [emulator.step(sample) for sample in _trace()]


def test_zero_noise_is_an_exact_valid_measurement_copy() -> None:
    emulator = SimulatedOdometryEmulator()
    emulator.reset(7, _config())

    snapshot = emulator.step(_sample(100))

    assert snapshot.status is SimulatedOdometryStatus.VALID
    assert snapshot.valid is True
    assert snapshot.measurement is not None
    assert snapshot.timestamp_ns == 100
    assert snapshot.measurement.x_m == pytest.approx(1.25)
    assert snapshot.measurement.y_m == pytest.approx(-2.5)
    assert snapshot.measurement.yaw_rad == pytest.approx(0.25)
    assert snapshot.measurement.vx_mps == pytest.approx(0.4)
    assert snapshot.measurement.vy_mps == pytest.approx(-0.2)
    assert snapshot.measurement.wz_radps == pytest.approx(0.3)


def test_same_seed_config_and_trace_are_reproducible() -> None:
    config = _config(
        position_bias_stddev_m=0.1,
        yaw_bias_stddev_rad=0.05,
        position_drift_stddev_m_per_step=0.01,
        yaw_drift_stddev_rad_per_step=0.02,
        velocity_noise_stddev_mps=0.03,
        yaw_rate_noise_stddev_radps=0.04,
        delay_samples=1,
        dropout_probability=0.25,
    )

    assert _run_trace(1234, config) == _run_trace(1234, config)


def test_different_seed_samples_a_different_episode_error_state() -> None:
    config = _config(position_bias_stddev_m=0.5, yaw_bias_stddev_rad=0.5)

    first = _run_trace(1, config)
    second = _run_trace(2, config)

    assert first != second


def test_reset_clears_drift_and_delay_queue() -> None:
    emulator = SimulatedOdometryEmulator()
    config = _config(
        position_drift_stddev_m_per_step=0.5,
        delay_samples=1,
    )
    emulator.reset(99, config)
    assert emulator.step(_sample(100)).status is SimulatedOdometryStatus.DELAYED
    first_episode_delivery = emulator.step(_sample(200))

    emulator.reset(99, config)
    assert emulator.step(_sample(100)).status is SimulatedOdometryStatus.DELAYED
    second_episode_delivery = emulator.step(_sample(200))

    assert first_episode_delivery == second_episode_delivery
    assert first_episode_delivery.timestamp_ns == 100


def test_delay_delivers_measurements_in_input_sample_order() -> None:
    emulator = SimulatedOdometryEmulator()
    emulator.reset(1, _config(delay_samples=2))

    first = emulator.step(_sample(100))
    second = emulator.step(_sample(200))
    third = emulator.step(_sample(300))

    assert first.status is SimulatedOdometryStatus.DELAYED
    assert second.status is SimulatedOdometryStatus.DELAYED
    assert third.status is SimulatedOdometryStatus.VALID
    assert third.timestamp_ns == 100
    assert third.sequence == 1


def test_dropout_is_explicit_and_never_substitutes_ground_truth() -> None:
    emulator = SimulatedOdometryEmulator()
    emulator.reset(3, _config(dropout_probability=1.0))

    snapshot = emulator.step(_sample(100))

    assert snapshot.status is SimulatedOdometryStatus.DROPPED
    assert snapshot.valid is False
    assert snapshot.measurement is None


@pytest.mark.parametrize(
    "timestamp_ns",
    [math.nan, math.inf, -1, 100.5],
)
def test_invalid_timestamp_fails_closed(timestamp_ns: object) -> None:
    emulator = SimulatedOdometryEmulator()
    emulator.reset(1, _config())

    with pytest.raises((TypeError, ValueError)):
        emulator.step(_sample(timestamp_ns))


def test_non_monotonic_timestamp_fails_closed() -> None:
    emulator = SimulatedOdometryEmulator()
    emulator.reset(1, _config())
    emulator.step(_sample(100))

    with pytest.raises(ValueError, match="strictly monotonic"):
        emulator.step(_sample(100))


def test_large_integer_nanosecond_timestamp_is_preserved_exactly() -> None:
    timestamp_ns = 1_000_000_000_000_000_001
    emulator = SimulatedOdometryEmulator()
    emulator.reset(1, _config())

    snapshot = emulator.step(_sample(timestamp_ns))

    assert snapshot.timestamp_ns == timestamp_ns


def test_adjacent_large_integer_nanosecond_timestamps_are_monotonic() -> None:
    first_timestamp_ns = 1_000_000_000_000_000_001
    second_timestamp_ns = first_timestamp_ns + 1
    emulator = SimulatedOdometryEmulator()
    emulator.reset(1, _config())

    first = emulator.step(_sample(first_timestamp_ns))
    second = emulator.step(_sample(second_timestamp_ns))

    assert first.timestamp_ns == first_timestamp_ns
    assert second.timestamp_ns == second_timestamp_ns
    assert second.timestamp_ns > first.timestamp_ns


def test_float_timestamp_above_double_exact_integer_range_is_rejected() -> None:
    emulator = SimulatedOdometryEmulator()
    emulator.reset(1, _config())

    with pytest.raises(ValueError, match=r"2\*\*53"):
        emulator.step(_sample(float((2**53) + 2)))


def test_yaw_is_normalized_to_half_open_interval() -> None:
    emulator = SimulatedOdometryEmulator()
    emulator.reset(1, _config())

    snapshot = emulator.step(_sample(100, 3.0 * math.pi))

    assert snapshot.measurement is not None
    assert snapshot.measurement.yaw_rad == pytest.approx(-math.pi)
    assert -math.pi <= snapshot.measurement.yaw_rad < math.pi


def test_snapshot_does_not_hold_a_raw_ground_truth_reference() -> None:
    ground_truth = _sample(100)
    emulator = SimulatedOdometryEmulator()
    emulator.reset(1, _config())

    snapshot = emulator.step(ground_truth)

    assert all(field.name != "ground_truth_sample" for field in fields(snapshot))
    assert snapshot.measurement is not ground_truth.pose
    assert snapshot.measurement is not ground_truth.twist
    assert snapshot.measurement is not ground_truth


def test_simulation_package_has_no_prohibited_runtime_imports() -> None:
    simulation_dir = Path(__file__).resolve().parents[1] / "mecanum_nav_rl" / "simulation"
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

    for source_path in simulation_dir.glob("*.py"):
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots = {alias.name.split(".")[0] for alias in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                roots = {node.module.split(".")[0]}
            else:
                continue
            assert prohibited_roots.isdisjoint(roots), source_path
