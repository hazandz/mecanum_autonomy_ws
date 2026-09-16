"""Typed configuration models for the Mecanum navigation DRL system."""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    FiniteFloat,
    StrictBool,
    field_validator,
    model_validator,
)


class ConfigModel(BaseModel):
    """Base class shared by all validated configuration models."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        validate_default=True,
    )


class RuntimeProfile(str, Enum):
    """Profiles supported by the project runtime."""

    SIM_TRAIN = "sim_train"
    SIM_EVAL = "sim_eval"
    DEPLOY_SIM = "deploy_sim"
    DEPLOY_REAL = "deploy_real"


class RuntimeConfig(ConfigModel):
    """Runtime mode selected before the system starts."""

    profile: RuntimeProfile
    use_sim_time: StrictBool


class FramesConfig(ConfigModel):
    """
    TF frame names used by one selected runtime profile.

    world_frame is used for Gazebo ground truth.
    map_frame is not required during sim_train because that profile uses
    ground-truth world coordinates rather than localization.
    """

    world_frame: str | None = Field(default=None, min_length=1)
    map_frame: str | None = Field(default=None, min_length=1)
    odom_frame: str = Field(min_length=1)
    base_frame: str = Field(min_length=1)
    lidar_frame: str = Field(min_length=1)

    @field_validator(
        "world_frame",
        "map_frame",
        "odom_frame",
        "base_frame",
        "lidar_frame",
    )
    @classmethod
    def validate_frame_name(cls, value: str | None) -> str | None:
        """Reject invalid TF frame names early."""

        if value is None:
            return None

        if value != value.strip():
            raise ValueError(
                "frame name must not have leading or trailing whitespace"
            )

        if any(character.isspace() for character in value):
            raise ValueError("frame name must not contain whitespace")

        if value.startswith("/"):
            raise ValueError("frame name must not start with '/'")

        return value

    @model_validator(mode="after")
    def validate_unique_frame_names(self) -> "FramesConfig":
        """Ensure configured frame names do not represent the same frame."""

        frame_names = [
            frame_name
            for frame_name in (
                self.world_frame,
                self.map_frame,
                self.odom_frame,
                self.base_frame,
                self.lidar_frame,
            )
            if frame_name is not None
        ]

        if len(frame_names) != len(set(frame_names)):
            raise ValueError("configured frame names must be unique")

        return self


class ObservationConfig(ConfigModel):
    """Fixed 81-element observation schema used by the PPO policy."""

    lidar_sector_count: Literal[72] = 72
    goal_feature_count: Literal[3] = 3
    measured_twist_feature_count: Literal[3] = 3
    previous_command_feature_count: Literal[3] = 3
    dimension: Literal[81] = 81


class ActionConfig(ConfigModel):
    """Fixed normalized three-element action schema for Mecanum motion."""

    dimension: Literal[3] = 3

    normalized_low: float = Field(
        default=-1.0,
        ge=-1.0,
        le=-1.0,
    )
    normalized_high: float = Field(
        default=1.0,
        ge=1.0,
        le=1.0,
    )


class MotionLimitsConfig(ConfigModel):
    """Maximum physical velocity magnitudes for one runtime profile."""

    max_vx_mps: FiniteFloat = Field(gt=0.0)
    max_vy_mps: FiniteFloat = Field(gt=0.0)
    max_wz_radps: FiniteFloat = Field(gt=0.0)


class ResolvedConfig(ConfigModel):
    """
    Complete validated configuration shared by the runtime.

    Other modules should receive this object instead of reading YAML files
    independently.
    """

    schema_version: Literal["1.0"] = "1.0"

    runtime: RuntimeConfig
    frames: FramesConfig

    observation: ObservationConfig = Field(
        default_factory=ObservationConfig
    )
    action: ActionConfig = Field(
        default_factory=ActionConfig
    )

    motion_limits: MotionLimitsConfig

    @model_validator(mode="after")
    def validate_runtime_contract(self) -> "ResolvedConfig":
        """Check rules that depend on the selected runtime profile."""

        profile = self.runtime.profile

        expected_use_sim_time = (
            profile != RuntimeProfile.DEPLOY_REAL
        )

        if self.runtime.use_sim_time != expected_use_sim_time:
            expected_text = str(expected_use_sim_time).lower()
            raise ValueError(
                f"profile '{profile.value}' must set "
                f"use_sim_time to {expected_text}"
            )

        ground_truth_profiles = {
            RuntimeProfile.SIM_TRAIN,
            RuntimeProfile.SIM_EVAL,
        }

        if (
            profile in ground_truth_profiles
            and self.frames.world_frame is None
        ):
            raise ValueError(
                f"profile '{profile.value}' requires "
                "frames.world_frame for Gazebo ground truth"
            )

        map_required_profiles = {
            RuntimeProfile.SIM_EVAL,
            RuntimeProfile.DEPLOY_SIM,
            RuntimeProfile.DEPLOY_REAL,
        }

        if (
            profile in map_required_profiles
            and self.frames.map_frame is None
        ):
            raise ValueError(
                f"profile '{profile.value}' requires "
                "frames.map_frame"
            )

        if (
            profile == RuntimeProfile.SIM_TRAIN
            and self.frames.map_frame is not None
        ):
            raise ValueError(
                "profile 'sim_train' must set frames.map_frame to null "
                "because the baseline training policy uses world ground truth"
            )

        if (
            profile == RuntimeProfile.DEPLOY_REAL
            and self.frames.world_frame is not None
        ):
            raise ValueError(
                "profile 'deploy_real' must set frames.world_frame to null"
            )

        return self