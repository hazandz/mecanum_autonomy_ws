"""Define and validate the PPO agent input-output contract."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, FiniteFloat, model_validator

from mecanum_nav_rl.config.models import (
    ConfigModel,
    ResolvedConfig,
)


AGENT_SPEC_VERSION = "1.0"

OBSERVATION_BLOCK_ORDER = (
    "lidar_sectors",
    "goal_features",
    "measured_twist",
    "previous_command",
)

ACTION_COMPONENT_ORDER = (
    "vx_normalized",
    "vy_normalized",
    "wz_normalized",
)


class AgentSpec(ConfigModel):
    """
    Immutable input-output contract required by one PPO policy.

    This object describes what the policy observes and what its normalized
    action means. It does not create or train the neural network.
    """

    agent_spec_version: Literal["1.0"] = AGENT_SPEC_VERSION

    observation_block_order: tuple[str, ...] = OBSERVATION_BLOCK_ORDER
    lidar_sector_count: int = Field(gt=0)
    goal_feature_count: int = Field(gt=0)
    measured_twist_feature_count: int = Field(gt=0)
    previous_command_feature_count: int = Field(gt=0)
    observation_dimension: int = Field(gt=0)

    action_component_order: tuple[str, ...] = ACTION_COMPONENT_ORDER
    action_dimension: int = Field(gt=0)
    normalized_low: FiniteFloat
    normalized_high: FiniteFloat

    max_vx_mps: FiniteFloat = Field(gt=0.0)
    max_vy_mps: FiniteFloat = Field(gt=0.0)
    max_wz_radps: FiniteFloat = Field(gt=0.0)

    @model_validator(mode="after")
    def validate_agent_contract(self) -> "AgentSpec":
        """Ensure the stored dimensions and meanings are self-consistent."""

        expected_observation_dimension = (
            self.lidar_sector_count
            + self.goal_feature_count
            + self.measured_twist_feature_count
            + self.previous_command_feature_count
        )

        if self.observation_dimension != expected_observation_dimension:
            raise ValueError(
                "observation_dimension does not match the sum of "
                "observation feature counts"
            )

        if self.observation_block_order != OBSERVATION_BLOCK_ORDER:
            raise ValueError(
                "observation_block_order does not match the "
                "project observation contract"
            )

        if self.action_component_order != ACTION_COMPONENT_ORDER:
            raise ValueError(
                "action_component_order does not match the "
                "Mecanum action contract"
            )

        if self.action_dimension != len(ACTION_COMPONENT_ORDER):
            raise ValueError(
                "action_dimension does not match the Mecanum action "
                "component count"
            )

        if self.normalized_low != -1.0:
            raise ValueError("normalized_low must be -1.0")

        if self.normalized_high != 1.0:
            raise ValueError("normalized_high must be 1.0")

        return self


def build_agent_spec(config: ResolvedConfig) -> AgentSpec:
    """
    Build the PPO agent contract from one validated runtime configuration.
    """

    if not isinstance(config, ResolvedConfig):
        raise TypeError(
            "config must be a validated ResolvedConfig instance"
        )

    observation = config.observation
    action = config.action
    motion_limits = config.motion_limits

    return AgentSpec(
        lidar_sector_count=observation.lidar_sector_count,
        goal_feature_count=observation.goal_feature_count,
        measured_twist_feature_count=(
            observation.measured_twist_feature_count
        ),
        previous_command_feature_count=(
            observation.previous_command_feature_count
        ),
        observation_dimension=observation.dimension,
        action_dimension=action.dimension,
        normalized_low=action.normalized_low,
        normalized_high=action.normalized_high,
        max_vx_mps=motion_limits.max_vx_mps,
        max_vy_mps=motion_limits.max_vy_mps,
        max_wz_radps=motion_limits.max_wz_radps,
    )


def agent_spec_mismatches(
    saved_spec: AgentSpec,
    runtime_spec: AgentSpec,
) -> tuple[str, ...]:
    """
    Return descriptions of every difference between two agent contracts.

    saved_spec comes from the checkpoint metadata.
    runtime_spec comes from the configuration being used now.
    """

    if not isinstance(saved_spec, AgentSpec):
        raise TypeError("saved_spec must be an AgentSpec instance")

    if not isinstance(runtime_spec, AgentSpec):
        raise TypeError("runtime_spec must be an AgentSpec instance")

    mismatches: list[str] = []

    for field_name in AgentSpec.model_fields:
        saved_value = getattr(saved_spec, field_name)
        runtime_value = getattr(runtime_spec, field_name)

        if saved_value != runtime_value:
            mismatches.append(
                f"{field_name}: checkpoint={saved_value!r}, "
                f"runtime={runtime_value!r}"
            )

    return tuple(mismatches)


def assert_agent_spec_compatible(
    saved_spec: AgentSpec,
    runtime_spec: AgentSpec,
) -> None:
    """
    Raise an error if a checkpoint agent contract differs from runtime.
    """

    mismatches = agent_spec_mismatches(
        saved_spec,
        runtime_spec,
    )

    if mismatches:
        details = "; ".join(mismatches)
        raise ValueError(
            "checkpoint AgentSpec is incompatible with runtime "
            f"AgentSpec: {details}"
        )
