"""Tests for episode-scoped history of validated PPO normalized actions."""

from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError
from math import pi, tau
from pathlib import Path

import pytest

from mecanum_nav_rl.actions.ppo_decoder import PpoActionDecoder
from mecanum_nav_rl.actions.previous_action_history import (
    PreviousActionHistory,
    PreviousActionHistoryStatus,
)
from mecanum_nav_rl.config.models import (
    ActionConfig,
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
from mecanum_nav_rl.observations.synchronizer import (
    ActiveLifecycleContext,
    ExactSnapshotPairGate,
    SynchronizationMetadata,
)
from mecanum_nav_rl.simulation.simulated_odometry import (
    SimulatedOdometryMeasurement,
    SimulatedOdometrySnapshot,
    SimulatedOdometryStatus,
)


def _config() -> ResolvedConfig:
    """Build one typed sim_train fixture with asymmetric action scaling."""

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


def _decoder() -> PpoActionDecoder:
    """Return the only raw-action validator used by this history test."""

    return PpoActionDecoder(_config())


def _history() -> PreviousActionHistory:
    """Return an explicitly uninitialized episode history."""

    return PreviousActionHistory(ActionConfig())


def _exact_input():
    """Build one complete policy-safe exact pair for assembler compatibility."""

    timestamp_ns = 101
    beam_count = _config().observation.lidar_sector_count * 5
    scan = RawLidarScan(
        timestamp_ns=timestamp_ns,
        angle_min_rad=-pi,
        angle_increment_rad=tau / beam_count,
        range_min_m=0.1,
        range_max_m=10.0,
        ranges=(1.0,) * beam_count,
    )
    odometry = SimulatedOdometrySnapshot(
        timestamp_ns=timestamp_ns,
        status=SimulatedOdometryStatus.VALID,
        sequence=1,
        measurement=SimulatedOdometryMeasurement(
            x_m=0.0,
            y_m=0.0,
            yaw_rad=0.0,
            vx_mps=0.0,
            vy_mps=0.0,
            wz_radps=0.0,
        ),
    )
    metadata = SynchronizationMetadata(
        reset_epoch=1,
        runtime_generation=1,
        received_steady_ns=1_000,
        action_barrier_ros_ns=100,
        reset_barrier_ros_ns=99,
    )
    context = ActiveLifecycleContext(
        reset_epoch=1,
        runtime_generation=1,
        action_barrier_ros_ns=100,
        reset_barrier_ros_ns=99,
    )
    return ExactSnapshotPairGate().synchronize(
        scan, metadata, odometry, metadata, context
    ).sensor_input


def test_reset_creates_explicit_zero_previous_action_for_new_episode() -> None:
    """Reset zero is a defined episode state, never invalid-action fallback."""

    history = _history()
    result = history.reset(10)

    assert result.status is PreviousActionHistoryStatus.RESET
    assert result.updated is False
    assert result.accepted_action is None
    assert result.state is not None
    assert result.state.episode_generation == 10
    assert (result.state.previous_command.vx, result.state.previous_command.vy, result.state.previous_command.wz) == (
        0.0,
        0.0,
        0.0,
    )


def test_update_before_reset_is_explicitly_uninitialized_and_does_not_create_action() -> None:
    """A decoder-ready candidate has no effect until an episode generation is reset."""

    history = _history()
    result = history.update(10, _decoder().decode((0.25, -0.5, 0.75)))

    assert result.status is PreviousActionHistoryStatus.UNINITIALIZED
    assert result.state is None
    assert result.accepted_action is None
    assert history.state is None


def test_ready_action_a_then_b_replaces_history_for_the_same_episode() -> None:
    """Only decoder-READY normalized actions become next-step observation history."""

    history = _history()
    history.reset(10)
    action_a = history.update(10, _decoder().decode((0.25, -0.5, 0.75)))
    action_b = history.update(10, _decoder().decode((-0.5, 0.25, -0.75)))

    assert action_a.status is PreviousActionHistoryStatus.UPDATED
    assert action_a.accepted_action is not None
    assert (action_a.accepted_action.vx, action_a.accepted_action.vy, action_a.accepted_action.wz) == (
        0.25,
        -0.5,
        0.75,
    )
    assert action_b.status is PreviousActionHistoryStatus.UPDATED
    assert history.state is not None
    assert history.state.previous_command == action_b.accepted_action
    assert history.state.previous_command != action_a.accepted_action


def test_future_generation_is_rejected_without_updating_current_episode_history() -> None:
    """A post-reset action tagged with a future generation cannot be accepted early."""

    history = _history()
    history.reset(10)
    history.update(10, _decoder().decode((0.1, 0.2, 0.3)))
    prior = history.state
    result = history.update(11, _decoder().decode((0.9, 0.8, 0.7)))

    assert result.status is PreviousActionHistoryStatus.FUTURE_GENERATION
    assert result.accepted_action is None
    assert result.state == prior == history.state
    assert result.state is not None
    assert result.state.episode_generation == 10
    assert (result.state.previous_command.vx, result.state.previous_command.vy, result.state.previous_command.wz) == (
        0.1,
        0.2,
        0.3,
    )


@pytest.mark.parametrize(
    "raw_action",
    ((1.1, 0.0, 0.0), (float("nan"), 0.0, 0.0)),
)
def test_non_ready_decode_does_not_create_or_replace_history(raw_action: tuple[float, float, float]) -> None:
    """Invalid or out-of-bounds decoder output retains prior state but no new action."""

    history = _history()
    history.reset(10)
    prior = history.update(10, _decoder().decode((0.1, 0.2, 0.3))).state
    result = history.update(10, _decoder().decode(raw_action))

    assert result.status is PreviousActionHistoryStatus.DECODE_NOT_READY
    assert result.updated is False
    assert result.accepted_action is None
    assert result.state == prior == history.state


def test_invalid_configuration_decode_does_not_update_history() -> None:
    """Decoder configuration failure does not turn retained history into new action."""

    history = _history()
    history.reset(10)
    prior = history.state
    corrupt_config = ResolvedConfig.model_construct(
        schema_version="1.0",
        runtime=_config().runtime,
        frames=_config().frames,
        observation=_config().observation,
        action=ActionConfig.model_construct(dimension=2, normalized_low=-1.0, normalized_high=1.0),
        motion_limits=_config().motion_limits,
    )
    result = history.update(10, PpoActionDecoder(corrupt_config).decode((0.0, 0.0, 0.0)))

    assert result.status is PreviousActionHistoryStatus.DECODE_NOT_READY
    assert result.accepted_action is None
    assert result.state == prior == history.state


def test_stale_generation_is_rejected_without_state_mutation() -> None:
    """An action from a prior reset token cannot alter the current episode history."""

    history = _history()
    history.reset(10)
    history.update(10, _decoder().decode((0.1, 0.2, 0.3)))
    prior = history.state
    result = history.update(9, _decoder().decode((0.9, 0.9, 0.9)))

    assert result.status is PreviousActionHistoryStatus.STALE_GENERATION
    assert result.accepted_action is None
    assert result.state == prior == history.state


def test_reset_with_new_generation_clears_the_prior_episode_action() -> None:
    """A new reset token replaces old action history with its explicit zero state."""

    history = _history()
    history.reset(10)
    history.update(10, _decoder().decode((0.1, 0.2, 0.3)))
    result = history.reset(11)

    assert result.status is PreviousActionHistoryStatus.RESET
    assert result.state is not None
    assert result.state.episode_generation == 11
    assert result.state.previous_command.vx == 0.0
    assert result.state.previous_command.vy == 0.0
    assert result.state.previous_command.wz == 0.0


def test_equal_or_older_reset_generation_is_rejected_without_state_mutation() -> None:
    """A reset token must be strictly newer, so it cannot erase current history."""

    history = _history()
    history.reset(10)
    history.update(10, _decoder().decode((0.1, 0.2, 0.3)))
    prior = history.state

    repeated = history.reset(10)
    older = history.reset(9)

    assert repeated.status is PreviousActionHistoryStatus.STALE_GENERATION
    assert older.status is PreviousActionHistoryStatus.STALE_GENERATION
    assert repeated.accepted_action is None
    assert older.accepted_action is None
    assert repeated.state == prior
    assert older.state == prior == history.state


@pytest.mark.parametrize(
    ("invalid_generation", "error_type"),
    (
        (True, TypeError),
        (-1, ValueError),
        (10.0, TypeError),
        ("10", TypeError),
    ),
)
def test_invalid_generation_is_rejected_by_reset_and_update_without_mutation(
    invalid_generation: object,
    error_type: type[Exception],
) -> None:
    """Generation validation is explicit and leaves the current episode untouched."""

    history = _history()
    history.reset(10)
    history.update(10, _decoder().decode((0.1, 0.2, 0.3)))
    prior = history.state
    ready_decode = _decoder().decode((0.9, 0.8, 0.7))

    with pytest.raises(error_type):
        history.reset(invalid_generation)  # type: ignore[arg-type]
    assert history.state == prior
    with pytest.raises(error_type):
        history.update(invalid_generation, ready_decode)  # type: ignore[arg-type]
    assert history.state == prior


def test_history_output_is_directly_accepted_by_observation_assembler() -> None:
    """History returns the exact typed input expected by ObservationAssembler."""

    history = _history()
    history.reset(10)
    update = history.update(10, _decoder().decode((0.25, -0.5, 0.75)))
    assert update.accepted_action is not None

    result = ObservationAssembler(_config()).assemble(
        _exact_input(),
        LocalGoal2D(x_m=1.0, y_m=0.0),
        update.accepted_action,
    )

    assert result.status is ObservationAssemblyStatus.READY
    assert result.vector is not None
    assert result.vector[-3:] == pytest.approx((0.25, -0.5, 0.75))


def test_state_and_result_are_immutable() -> None:
    """Callers cannot mutate a state/result into a fabricated accepted action."""

    history = _history()
    reset = history.reset(10)
    assert reset.state is not None
    with pytest.raises((FrozenInstanceError, AttributeError)):
        reset.state.episode_generation = 11  # type: ignore[misc]
    with pytest.raises((FrozenInstanceError, AttributeError)):
        reset.status = PreviousActionHistoryStatus.UPDATED  # type: ignore[misc]


def test_history_production_module_has_no_runtime_or_ground_truth_imports() -> None:
    """History remains core-only and cannot publish or control the robot."""

    source_path = Path(__file__).parents[1] / "mecanum_nav_rl" / "actions" / "previous_action_history.py"
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
    assert "physical command" in source_text
    assert "VelocityCommand" not in source_text
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots = {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            roots = {node.module.split(".")[0]}
        else:
            continue
        assert prohibited_roots.isdisjoint(roots), source_path
