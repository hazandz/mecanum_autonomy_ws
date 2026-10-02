"""Tests for core-only previous-issued-command feature extraction."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from mecanum_nav_rl.config.models import ActionConfig, ObservationConfig
from mecanum_nav_rl.observations.previous_command import (
    PreviousCommandFeatureExtractor,
    PreviousNormalizedCommand,
)


def _extractor() -> PreviousCommandFeatureExtractor:
    """Return an extractor backed by actual configuration models."""

    return PreviousCommandFeatureExtractor(ObservationConfig(), ActionConfig())


def test_valid_command_preserves_vx_vy_wz_order_without_transformation() -> None:
    """The features are exactly the previously issued normalized command."""

    command = PreviousNormalizedCommand(vx=0.25, vy=-0.5, wz=0.75)

    assert _extractor().extract(command).features == (0.25, -0.5, 0.75)


@pytest.mark.parametrize("value", (ActionConfig().normalized_low, ActionConfig().normalized_high))
def test_action_config_bounds_are_accepted(value: float) -> None:
    """Both inclusive normalized bounds remain valid previous commands."""

    command = PreviousNormalizedCommand(vx=value, vy=value, wz=value)

    assert _extractor().extract(command).features == (value, value, value)


@pytest.mark.parametrize("value", (ActionConfig().normalized_low - 0.1, ActionConfig().normalized_high + 0.1))
def test_command_outside_action_bounds_is_rejected_without_clipping(value: float) -> None:
    """Out-of-bounds commands fail closed rather than being silently clipped."""

    with pytest.raises(ValueError, match="normalized bounds"):
        _extractor().extract(PreviousNormalizedCommand(vx=value, vy=0.0, wz=0.0))


@pytest.mark.parametrize(
    "invalid_value",
    (float("nan"), float("inf"), float("-inf"), True),
)
def test_non_finite_or_boolean_command_component_is_rejected(
    invalid_value: object,
) -> None:
    """Finite real normalized components are required before extraction."""

    with pytest.raises((TypeError, ValueError)):
        PreviousNormalizedCommand(vx=invalid_value, vy=0.0, wz=0.0)


def test_matching_non_three_component_configs_are_rejected_immediately() -> None:
    """Matching corrupted configs cannot bypass the fixed three-value contract."""

    valid_config = ObservationConfig()
    invalid_config = ObservationConfig.model_construct(
        lidar_sector_count=valid_config.lidar_sector_count,
        goal_feature_count=valid_config.goal_feature_count,
        measured_twist_feature_count=valid_config.measured_twist_feature_count,
        previous_command_feature_count=2,
        dimension=valid_config.dimension,
    )

    invalid_action_config = ActionConfig.model_construct(
        dimension=2,
        normalized_low=ActionConfig().normalized_low,
        normalized_high=ActionConfig().normalized_high,
    )

    with pytest.raises(ValueError, match="previous_command_feature_count"):
        PreviousCommandFeatureExtractor(invalid_config, invalid_action_config)


def test_invalid_action_dimension_is_rejected_immediately() -> None:
    """A corrupted action schema cannot reach extraction with a wrong dimension."""

    invalid_action_config = ActionConfig.model_construct(
        dimension=2,
        normalized_low=ActionConfig().normalized_low,
        normalized_high=ActionConfig().normalized_high,
    )

    with pytest.raises(ValueError, match="ActionConfig dimension"):
        PreviousCommandFeatureExtractor(ObservationConfig(), invalid_action_config)


def test_episode_initial_command_is_explicit_zero_vector() -> None:
    """A new episode begins with a typed zero command rather than a sentinel."""

    command = PreviousNormalizedCommand.episode_initial(ActionConfig())

    assert command == PreviousNormalizedCommand(vx=0.0, vy=0.0, wz=0.0)
    assert _extractor().extract(command).features == (0.0, 0.0, 0.0)


def test_episode_initial_command_rejects_bounds_that_exclude_zero() -> None:
    """Zero is valid only when the supplied action configuration includes it."""

    action_config_without_zero = ActionConfig.model_construct(
        dimension=ActionConfig().dimension,
        normalized_low=0.1,
        normalized_high=1.0,
    )

    with pytest.raises(ValueError, match="include zero"):
        PreviousNormalizedCommand.episode_initial(action_config_without_zero)


def test_episode_initial_command_rejects_invalid_action_dimension() -> None:
    """The explicit episode command retains the fixed three-component contract."""

    invalid_action_config = ActionConfig.model_construct(
        dimension=2,
        normalized_low=ActionConfig().normalized_low,
        normalized_high=ActionConfig().normalized_high,
    )

    with pytest.raises(ValueError, match="ActionConfig dimension"):
        PreviousNormalizedCommand.episode_initial(invalid_action_config)


def test_equal_action_bounds_are_rejected_even_if_model_validation_is_bypassed() -> None:
    """A zero-width normalized range is invalid under the fixed action contract."""

    equal_bounds_action_config = ActionConfig.model_construct(
        dimension=ActionConfig().dimension,
        normalized_low=0.0,
        normalized_high=0.0,
    )

    with pytest.raises(ValueError, match="must be less than"):
        PreviousCommandFeatureExtractor(ObservationConfig(), equal_bounds_action_config)


def test_production_module_has_no_runtime_or_ground_truth_imports() -> None:
    """Keep previous-command features pure and independent of runtime systems."""

    module_path = (
        Path(__file__).parents[1]
        / "mecanum_nav_rl"
        / "observations"
        / "previous_command.py"
    )
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
