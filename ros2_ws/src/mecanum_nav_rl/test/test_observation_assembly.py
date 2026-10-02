"""Unit tests for core-only policy observation assembly from exact pairs."""

from __future__ import annotations

import ast
from math import isfinite, pi, tau
from pathlib import Path

import pytest

from mecanum_nav_rl.config.models import (
    FramesConfig,
    MotionLimitsConfig,
    ResolvedConfig,
    RuntimeConfig,
    RuntimeProfile,
)
from mecanum_nav_rl.observations.assembly import (
    ObservationAssembler,
    ObservationAssemblyStatus,
)
from mecanum_nav_rl.observations.goal_features import LocalGoal2D
from mecanum_nav_rl.observations.lidar import RawLidarScan
from mecanum_nav_rl.observations.previous_command import PreviousNormalizedCommand
from mecanum_nav_rl.observations.synchronizer import (
    ActiveLifecycleContext,
    ExactSnapshotPairGate,
    SynchronizationMetadata,
    SynchronizedSensorInput,
)
from mecanum_nav_rl.simulation.simulated_odometry import (
    SimulatedOdometryMeasurement,
    SimulatedOdometrySnapshot,
    SimulatedOdometryStatus,
)


def _config() -> ResolvedConfig:
    """Return a resolved sim_train configuration using official typed models."""

    return ResolvedConfig(
        runtime=RuntimeConfig(profile=RuntimeProfile.SIM_TRAIN, use_sim_time=True),
        frames=FramesConfig(
            world_frame="world",
            map_frame=None,
            odom_frame="odom",
            base_frame="base_link",
            lidar_frame="lidar",
        ),
        motion_limits=MotionLimitsConfig(
            max_vx_mps=1.0,
            max_vy_mps=1.0,
            max_wz_radps=1.0,
        ),
    )


def _metadata() -> SynchronizationMetadata:
    """Return matching test-only metadata for a post-barrier exact pair."""

    return SynchronizationMetadata(
        reset_epoch=4,
        runtime_generation=7,
        received_steady_ns=20_000,
        action_barrier_ros_ns=100,
        reset_barrier_ros_ns=99,
    )


def _context() -> ActiveLifecycleContext:
    """Return the active lifecycle context matching the fixture metadata."""

    return ActiveLifecycleContext(
        reset_epoch=4,
        runtime_generation=7,
        action_barrier_ros_ns=100,
        reset_barrier_ros_ns=99,
    )


def _scan(timestamp_ns: int = 101) -> RawLidarScan:
    """Create a complete full-coverage raw scan for the configured 72 sectors."""

    beam_count = _config().observation.lidar_sector_count * 5
    return RawLidarScan(
        timestamp_ns=timestamp_ns,
        angle_min_rad=-pi,
        angle_increment_rad=tau / beam_count,
        range_min_m=0.1,
        range_max_m=10.0,
        ranges=(1.0,) * beam_count,
    )


def _odometry(
    timestamp_ns: int = 101,
    status: SimulatedOdometryStatus = SimulatedOdometryStatus.VALID,
) -> SimulatedOdometrySnapshot:
    """Create policy-safe simulated odometry for an exact-pair candidate."""

    measurement = None
    if status is SimulatedOdometryStatus.VALID:
        measurement = SimulatedOdometryMeasurement(
            x_m=1.0,
            y_m=2.0,
            yaw_rad=0.0,
            vx_mps=0.25,
            vy_mps=-0.5,
            wz_radps=0.75,
        )
    return SimulatedOdometrySnapshot(
        timestamp_ns=timestamp_ns,
        status=status,
        sequence=11,
        measurement=measurement,
    )


def _exact_input(
    *,
    scan: RawLidarScan | None = None,
    odometry: SimulatedOdometrySnapshot | None = None,
) -> SynchronizedSensorInput | None:
    """Use the exact gate; a rejected pair deliberately yields no input."""

    scan_candidate = _scan() if scan is None else scan
    odometry_candidate = _odometry() if odometry is None else odometry
    result = ExactSnapshotPairGate().synchronize(
        scan_candidate,
        _metadata(),
        odometry_candidate,
        _metadata(),
        _context(),
    )
    return result.sensor_input


def _assembler(config: ResolvedConfig | None = None) -> ObservationAssembler:
    """Create the explicit core-only assembler used by each test."""

    return ObservationAssembler(_config() if config is None else config)


def _goal() -> LocalGoal2D:
    """Return a typed local-frame policy goal supplied by the caller."""

    return LocalGoal2D(x_m=3.0, y_m=2.0)


def _previous_command() -> PreviousNormalizedCommand:
    """Return a caller-issued normalized previous command, not a default."""

    return PreviousNormalizedCommand(vx=0.25, vy=-0.5, wz=0.75)


def test_exact_valid_pair_assembles_a_finite_81_element_policy_vector() -> None:
    """Only the exact gate's ready policy-safe input reaches encoder assembly."""

    result = _assembler().assemble(_exact_input(), _goal(), _previous_command())

    assert result.status is ObservationAssemblyStatus.READY
    assert result.ready is True
    assert result.vector is not None
    assert len(result.vector) == _config().observation.dimension == 81
    assert all(isfinite(value) for value in result.vector)
    assert result.vector[:72] == pytest.approx((1.0,) * 72)
    assert result.vector[72:75] == pytest.approx((2.0, 0.0, 1.0))
    assert result.vector[78:] == pytest.approx((0.25, -0.5, 0.75))


def test_gate_rejected_one_nanosecond_skew_never_assembles_a_vector() -> None:
    """The assembler receives no fabricated replacement after gate rejection."""

    rejected_input = _exact_input(odometry=_odometry(timestamp_ns=102))
    result = _assembler().assemble(rejected_input, _goal(), _previous_command())

    assert rejected_input is None
    assert result.status is ObservationAssemblyStatus.SYNCHRONIZED_INPUT_NOT_READY
    assert result.ready is False
    assert result.vector is None


def test_partial_fov_lidar_fails_closed_without_an_observation() -> None:
    """A scan with every other sector empty cannot be represented as complete data."""

    partial_scan = RawLidarScan(
        timestamp_ns=101,
        angle_min_rad=-pi / 2.0,
        angle_increment_rad=pi / 360.0,
        range_min_m=0.1,
        range_max_m=10.0,
        ranges=tuple(1.0 for _ in range(360)),
    )
    result = _assembler().assemble(_exact_input(scan=partial_scan), _goal(), _previous_command())

    assert result.status is ObservationAssemblyStatus.LIDAR_INVALID
    assert result.vector is None


@pytest.mark.parametrize(
    "odometry_status",
    (SimulatedOdometryStatus.DELAYED, SimulatedOdometryStatus.DROPPED),
)
def test_delayed_or_dropped_odometry_never_assembles_a_vector(
    odometry_status: SimulatedOdometryStatus,
) -> None:
    """Unavailable odometry cannot become a stale policy observation."""

    result = _assembler().assemble(
        _exact_input(odometry=_odometry(status=odometry_status)),
        _goal(),
        _previous_command(),
    )

    assert result.status is ObservationAssemblyStatus.SYNCHRONIZED_INPUT_NOT_READY
    assert result.vector is None


def test_invalid_goal_is_reported_without_an_observation() -> None:
    """A corrupted typed goal is rejected instead of replaced or clamped."""

    goal = _goal()
    object.__setattr__(goal, "x_m", float("nan"))
    result = _assembler().assemble(_exact_input(), goal, _previous_command())

    assert result.status is ObservationAssemblyStatus.GOAL_INVALID
    assert result.vector is None


def test_invalid_previous_command_is_reported_without_an_observation() -> None:
    """A corrupted previous command never falls back to a zero command."""

    previous_command = _previous_command()
    object.__setattr__(previous_command, "vx", 1.1)
    result = _assembler().assemble(_exact_input(), _goal(), previous_command)

    assert result.status is ObservationAssemblyStatus.PREVIOUS_COMMAND_INVALID
    assert result.vector is None


def test_corrupted_observation_dimension_fails_closed_at_construction() -> None:
    """The official dimension invariant cannot be bypassed into assembly."""

    config = _config()
    invalid_observation = config.observation.model_construct(
        lidar_sector_count=config.observation.lidar_sector_count,
        goal_feature_count=config.observation.goal_feature_count,
        measured_twist_feature_count=config.observation.measured_twist_feature_count,
        previous_command_feature_count=config.observation.previous_command_feature_count,
        dimension=config.observation.dimension - 1,
    )
    invalid_config = ResolvedConfig.model_construct(
        schema_version=config.schema_version,
        runtime=config.runtime,
        frames=config.frames,
        observation=invalid_observation,
        action=config.action,
        motion_limits=config.motion_limits,
    )

    with pytest.raises(ValueError, match="sum of its feature blocks"):
        ObservationAssembler(invalid_config)


def test_production_assembly_module_has_no_runtime_or_truth_imports() -> None:
    """Assembly remains pure and cannot access transport, simulator, or truth data."""

    source_path = Path(__file__).parents[1] / "mecanum_nav_rl" / "observations" / "assembly.py"
    source_text = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source_text)
    prohibited_roots = {
        "rclpy",
        "tf2_ros",
        "geometry_msgs",
        "sensor_msgs",
        "nav_msgs",
        "gazebo",
        "gz",
        "gymnasium",
        "stable_baselines3",
    }

    assert "GroundTruthSample" not in source_text
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots = {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            roots = {node.module.split(".")[0]}
        else:
            continue
        assert prohibited_roots.isdisjoint(roots), source_path
