"""Tests for pure PPO normalized-action decoding into physical velocity commands."""

from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError
from math import inf, nan
from pathlib import Path

import pytest

from mecanum_nav_rl.actions.ppo_decoder import (
    NormalizedPpoAction,
    PpoActionDecodeStatus,
    PpoActionDecoder,
)
from mecanum_nav_rl.config.models import (
    ActionConfig,
    FramesConfig,
    MotionLimitsConfig,
    ResolvedConfig,
    RuntimeConfig,
    RuntimeProfile,
)


def _config(
    *,
    action: ActionConfig | None = None,
    limits: MotionLimitsConfig | None = None,
) -> ResolvedConfig:
    """Build an official typed sim_train config with explicit test limits."""

    return ResolvedConfig(
        runtime=RuntimeConfig(profile=RuntimeProfile.SIM_TRAIN, use_sim_time=True),
        frames=FramesConfig(
            world_frame="world",
            map_frame=None,
            odom_frame="odom",
            base_frame="base_link",
            lidar_frame="lidar",
        ),
        action=ActionConfig() if action is None else action,
        motion_limits=MotionLimitsConfig(
            max_vx_mps=2.0,
            max_vy_mps=4.0,
            max_wz_radps=8.0,
        )
        if limits is None
        else limits,
    )


def _decoder(config: ResolvedConfig | None = None) -> PpoActionDecoder:
    """Create a decoder with known axis-specific scaling limits."""

    return PpoActionDecoder(_config() if config is None else config)


def test_zero_action_decodes_to_an_explicit_physical_zero_command() -> None:
    """Zero is accepted because it is a valid input, not a decoder fallback."""

    result = _decoder().decode((0.0, 0.0, 0.0))

    assert result.status is PpoActionDecodeStatus.READY
    assert result.ready is True
    assert result.command is not None
    assert (result.command.vx, result.command.vy, result.command.wz) == (0.0, 0.0, 0.0)


@pytest.mark.parametrize(
    ("raw_action", "expected_command"),
    (
        ((1.0, 0.0, 0.0), (2.0, 0.0, 0.0)),
        ((-1.0, 0.0, 0.0), (-2.0, 0.0, 0.0)),
        ((0.0, 1.0, 0.0), (0.0, 4.0, 0.0)),
        ((0.0, -1.0, 0.0), (0.0, -4.0, 0.0)),
        ((0.0, 0.0, 1.0), (0.0, 0.0, 8.0)),
        ((0.0, 0.0, -1.0), (0.0, 0.0, -8.0)),
    ),
)
def test_unit_axis_bounds_scale_to_the_corresponding_physical_limit(
    raw_action: tuple[float, float, float],
    expected_command: tuple[float, float, float],
) -> None:
    """Index order is fixed: vx, then vy, then wz."""

    result = _decoder().decode(raw_action)

    assert result.status is PpoActionDecodeStatus.READY
    assert result.command is not None
    assert (result.command.vx, result.command.vy, result.command.wz) == expected_command


def test_mixed_normalized_values_scale_in_fixed_vx_vy_wz_order() -> None:
    """Axis-specific limits prove components cannot be reordered silently."""

    result = _decoder().decode((0.5, -0.25, 0.125))

    assert result.status is PpoActionDecodeStatus.READY
    assert result.normalized_action == NormalizedPpoAction(0.5, -0.25, 0.125)
    assert result.command is not None
    assert (result.command.vx, result.command.vy, result.command.wz) == (1.0, -1.0, 1.0)


@pytest.mark.parametrize("bound", (-1.0, 1.0))
def test_closed_normalized_bounds_are_valid(bound: float) -> None:
    """The contract includes both normalized endpoints."""

    result = _decoder().decode((bound, bound, bound))

    assert result.status is PpoActionDecodeStatus.READY
    assert result.command is not None


@pytest.mark.parametrize("raw_action", ((1.000001, 0.0, 0.0), (0.0, -1.000001, 0.0)))
def test_out_of_bounds_action_is_rejected_without_clamping(
    raw_action: tuple[float, float, float],
) -> None:
    """Invalid PPO values produce no zero, prior, or clipped command."""

    result = _decoder().decode(raw_action)

    assert result.status is PpoActionDecodeStatus.OUT_OF_BOUNDS
    assert result.ready is False
    assert result.normalized_action is None
    assert result.command is None


@pytest.mark.parametrize(
    "raw_action",
    (
        (nan, 0.0, 0.0),
        (inf, 0.0, 0.0),
        (-inf, 0.0, 0.0),
        (True, 0.0, 0.0),
        ("invalid", 0.0, 0.0),
        object(),
        "not an action sequence",
    ),
)
def test_non_finite_boolean_or_non_real_input_is_rejected(
    raw_action: object,
) -> None:
    """Raw PPO ingress accepts only finite real values."""

    result = _decoder().decode(raw_action)

    assert result.status is PpoActionDecodeStatus.INVALID_INPUT
    assert result.command is None


@pytest.mark.parametrize("raw_action", ((0.0, 0.0), (0.0, 0.0, 0.0, 0.0), ()))
def test_wrong_action_dimension_is_explicitly_rejected(raw_action: tuple[float, ...]) -> None:
    """No partial action is padded, truncated, or reused."""

    result = _decoder().decode(raw_action)

    assert result.status is PpoActionDecodeStatus.INVALID_DIMENSION
    assert result.command is None


def test_finite_three_value_generator_decodes_without_materializing_the_iterable() -> None:
    """A finite generator is a valid PPO ingress representation."""

    result = _decoder().decode(value for value in (0.5, -0.25, 0.125))

    assert result.status is PpoActionDecodeStatus.READY
    assert result.command is not None
    assert (result.command.vx, result.command.vy, result.command.wz) == (1.0, -1.0, 1.0)


@pytest.mark.parametrize(
    "raw_action",
    (
        (value for value in (0.0, 0.0)),
        (value for value in (0.0, 0.0, 0.0, 0.0)),
    ),
)
def test_generator_with_wrong_dimension_is_rejected(raw_action: object) -> None:
    """The parser treats finite generator length exactly like tuple/list length."""

    result = _decoder().decode(raw_action)

    assert result.status is PpoActionDecodeStatus.INVALID_DIMENSION
    assert result.command is None


def test_long_iterator_is_consumed_at_most_four_times_before_dimension_rejection() -> None:
    """A deliberately unbounded iterator proves parsing never materializes all input."""

    class LongIteratorProbe:
        def __init__(self) -> None:
            self.next_call_count = 0

        def __iter__(self) -> "LongIteratorProbe":
            return self

        def __next__(self) -> float:
            self.next_call_count += 1
            return 0.0

    probe = LongIteratorProbe()
    result = _decoder().decode(probe)

    assert result.status is PpoActionDecodeStatus.INVALID_DIMENSION
    assert result.command is None
    assert probe.next_call_count == 4


@pytest.mark.parametrize(
    "corrupt_config",
    (
        lambda valid: ResolvedConfig.model_construct(
            schema_version=valid.schema_version,
            runtime=valid.runtime,
            frames=valid.frames,
            observation=valid.observation,
            action=ActionConfig.model_construct(dimension=2, normalized_low=-1.0, normalized_high=1.0),
            motion_limits=valid.motion_limits,
        ),
        lambda valid: ResolvedConfig.model_construct(
            schema_version=valid.schema_version,
            runtime=valid.runtime,
            frames=valid.frames,
            observation=valid.observation,
            action=ActionConfig.model_construct(dimension=3, normalized_low=-0.9, normalized_high=1.0),
            motion_limits=valid.motion_limits,
        ),
        lambda valid: ResolvedConfig.model_construct(
            schema_version=valid.schema_version,
            runtime=valid.runtime,
            frames=valid.frames,
            observation=valid.observation,
            action=valid.action,
            motion_limits=MotionLimitsConfig.model_construct(
                max_vx_mps=nan, max_vy_mps=1.0, max_wz_radps=1.0
            ),
        ),
        lambda valid: ResolvedConfig.model_construct(
            schema_version=valid.schema_version,
            runtime=valid.runtime,
            frames=valid.frames,
            observation=valid.observation,
            action=valid.action,
            motion_limits=MotionLimitsConfig.model_construct(
                max_vx_mps=0.0, max_vy_mps=1.0, max_wz_radps=1.0
            ),
        ),
    ),
)
def test_corrupt_configuration_fails_closed_without_a_command(corrupt_config) -> None:
    """Bypassed Pydantic validation still cannot reach scaling."""

    result = _decoder(corrupt_config(_config())).decode((0.0, 0.0, 0.0))

    assert result.status is PpoActionDecodeStatus.INVALID_CONFIGURATION
    assert result.normalized_action is None
    assert result.command is None


def test_ready_output_is_immutable_and_finite() -> None:
    """The later safety/runtime layer receives a frozen, finite command object."""

    result = _decoder().decode((0.25, -0.5, 0.75))

    assert result.command is not None
    with pytest.raises((FrozenInstanceError, AttributeError)):
        result.command.vx = 9.0  # type: ignore[misc]
    assert all(isinstance(value, float) for value in (result.command.vx, result.command.vy, result.command.wz))


def test_production_decoder_has_no_runtime_or_ground_truth_imports() -> None:
    """The decoder cannot publish, access simulation, or train a policy."""

    source_path = Path(__file__).parents[1] / "mecanum_nav_rl" / "actions" / "ppo_decoder.py"
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
    assert "PreviousNormalizedCommand" in source_text
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots = {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            roots = {node.module.split(".")[0]}
        else:
            continue
        assert prohibited_roots.isdisjoint(roots), source_path
