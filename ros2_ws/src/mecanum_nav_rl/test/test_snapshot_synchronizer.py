"""Unit tests for the core-only exact snapshot pairing gate."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from mecanum_nav_rl.observations.lidar import RawLidarScan
from mecanum_nav_rl.observations.synchronizer import (
    ActiveLifecycleContext,
    ExactSnapshotPairGate,
    SynchronizationMetadata,
    SynchronizationStatus,
)
from mecanum_nav_rl.simulation.simulated_odometry import (
    SimulatedOdometryMeasurement,
    SimulatedOdometrySnapshot,
    SimulatedOdometryStatus,
)


def _scan(timestamp_ns: int = 101) -> RawLidarScan:
    """Build one policy-safe raw scan candidate without a runtime adapter."""

    return RawLidarScan(
        timestamp_ns=timestamp_ns,
        angle_min_rad=0.0,
        angle_increment_rad=1.0,
        range_min_m=0.1,
        range_max_m=10.0,
        ranges=(1.0,),
    )


def _odometry(
    timestamp_ns: int = 101,
    status: SimulatedOdometryStatus = SimulatedOdometryStatus.VALID,
) -> SimulatedOdometrySnapshot:
    """Build one policy-safe odometry candidate with explicit availability."""

    measurement = None
    if status is SimulatedOdometryStatus.VALID:
        measurement = SimulatedOdometryMeasurement(
            x_m=1.0,
            y_m=-2.0,
            yaw_rad=0.25,
            vx_mps=0.5,
            vy_mps=-0.25,
            wz_radps=0.75,
        )
    return SimulatedOdometrySnapshot(
        timestamp_ns=timestamp_ns,
        status=status,
        sequence=7,
        measurement=measurement,
    )


def _metadata(
    *,
    reset_epoch: int = 3,
    runtime_generation: int = 5,
    received_steady_ns: int = 9_000,
    action_barrier_ros_ns: int = 100,
    reset_barrier_ros_ns: int = 99,
) -> SynchronizationMetadata:
    """Return test-only caller-provided ingress metadata."""

    return SynchronizationMetadata(
        reset_epoch=reset_epoch,
        runtime_generation=runtime_generation,
        received_steady_ns=received_steady_ns,
        action_barrier_ros_ns=action_barrier_ros_ns,
        reset_barrier_ros_ns=reset_barrier_ros_ns,
    )


def _context() -> ActiveLifecycleContext:
    """Return the active lifecycle context matching the default test metadata."""

    return ActiveLifecycleContext(
        reset_epoch=3,
        runtime_generation=5,
        action_barrier_ros_ns=100,
        reset_barrier_ros_ns=99,
    )


def _synchronize(
    *,
    scan: RawLidarScan | None = None,
    scan_metadata: SynchronizationMetadata | None = None,
    odometry: SimulatedOdometrySnapshot | None = None,
    odometry_metadata: SynchronizationMetadata | None = None,
    context: ActiveLifecycleContext | None = None,
):
    """Evaluate one exact candidate pair with all default metadata valid."""

    return ExactSnapshotPairGate().synchronize(
        _scan() if scan is None else scan,
        _metadata() if scan_metadata is None else scan_metadata,
        _odometry() if odometry is None else odometry,
        _metadata(received_steady_ns=9_001)
        if odometry_metadata is None
        else odometry_metadata,
        _context() if context is None else context,
    )


def test_exact_valid_pair_is_ready_and_contains_policy_safe_input() -> None:
    """An exact valid pair passes with no tolerance or replacement candidate."""

    result = _synchronize()

    assert result.status is SynchronizationStatus.READY
    assert result.ready is True
    assert result.sensor_input is not None
    assert result.sensor_input.scan.timestamp_ns == 101
    assert result.sensor_input.odometry.timestamp_ns == 101
    assert result.sensor_input.odometry.measurement is not None
    assert not hasattr(result.sensor_input, "ground_truth")
    assert not hasattr(result.sensor_input, "world_pose")


def test_one_nanosecond_stamp_difference_is_not_nearest_paired() -> None:
    """A 1 ns difference is explicit non-ready under the approved zero tolerance."""

    result = _synchronize(odometry=_odometry(timestamp_ns=102))

    assert result.status is SynchronizationStatus.TIMESTAMP_MISMATCH
    assert result.ready is False
    assert result.sensor_input is None


@pytest.mark.parametrize(
    ("odometry_status", "expected_status"),
    (
        (SimulatedOdometryStatus.DELAYED, SynchronizationStatus.ODOMETRY_DELAYED),
        (SimulatedOdometryStatus.DROPPED, SynchronizationStatus.ODOMETRY_DROPPED),
    ),
)
def test_delayed_or_dropped_odometry_never_uses_a_previous_valid_candidate(
    odometry_status: SimulatedOdometryStatus,
    expected_status: SynchronizationStatus,
) -> None:
    """Diagnostic odometry events never produce a pair or fallback input."""

    result = _synchronize(odometry=_odometry(status=odometry_status))

    assert result.status is expected_status
    assert result.ready is False
    assert result.sensor_input is None


@pytest.mark.parametrize(
    ("scan_metadata", "odometry_metadata"),
    (
        (_metadata(reset_epoch=4), _metadata(received_steady_ns=9_001)),
        (_metadata(), _metadata(runtime_generation=6, received_steady_ns=9_001)),
    ),
)
def test_epoch_or_generation_mismatch_is_rejected(
    scan_metadata: SynchronizationMetadata,
    odometry_metadata: SynchronizationMetadata,
) -> None:
    """Both sensor candidates must match each other and active lifecycle state."""

    result = _synchronize(
        scan_metadata=scan_metadata,
        odometry_metadata=odometry_metadata,
    )

    assert result.status is SynchronizationStatus.LIFECYCLE_MISMATCH
    assert result.sensor_input is None


def test_metadata_barrier_provenance_must_match_active_context() -> None:
    """A caller cannot supply sensor metadata from a different barrier lifecycle."""

    result = _synchronize(scan_metadata=_metadata(action_barrier_ros_ns=98))

    assert result.status is SynchronizationStatus.LIFECYCLE_MISMATCH
    assert result.sensor_input is None


def test_action_barrier_rejects_a_timestamp_at_the_barrier() -> None:
    """Candidates must be strictly newer than the action barrier."""

    result = _synchronize(
        scan=_scan(timestamp_ns=100),
        odometry=_odometry(timestamp_ns=100),
    )

    assert result.status is SynchronizationStatus.ACTION_BARRIER_REJECTED
    assert result.sensor_input is None


def test_reset_barrier_rejects_a_timestamp_at_the_barrier() -> None:
    """Reset barriers use the same strict-after ROS-time contract."""

    context = ActiveLifecycleContext(
        reset_epoch=3,
        runtime_generation=5,
        action_barrier_ros_ns=90,
        reset_barrier_ros_ns=101,
    )
    scan_metadata = _metadata(action_barrier_ros_ns=90, reset_barrier_ros_ns=101)
    odometry_metadata = _metadata(
        received_steady_ns=9_001,
        action_barrier_ros_ns=90,
        reset_barrier_ros_ns=101,
    )

    result = _synchronize(
        scan=_scan(timestamp_ns=101),
        scan_metadata=scan_metadata,
        odometry=_odometry(timestamp_ns=101),
        odometry_metadata=odometry_metadata,
        context=context,
    )

    assert result.status is SynchronizationStatus.RESET_BARRIER_REJECTED
    assert result.sensor_input is None


def test_production_synchronizer_has_no_runtime_or_truth_imports() -> None:
    """The exact gate remains pure and cannot directly access simulator truth."""

    source_path = Path(__file__).parents[1] / "mecanum_nav_rl" / "observations" / "synchronizer.py"
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
