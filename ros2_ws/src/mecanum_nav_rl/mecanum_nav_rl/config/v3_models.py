"""Architecture-target configuration types, parallel to legacy v1.

Legacy v1 remains the existing input surface. These v3 types model the frozen
architecture target only; A0.3 owns compiler and loader migration.
"""

from __future__ import annotations

from enum import Enum
from types import MappingProxyType
from typing import Annotated, Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field, StrictBool, model_validator
from pydantic.types import StringConstraints


IdentifierV3 = Annotated[
    str, StringConstraints(strict=True, min_length=1, pattern=r"^\S+$")
]
Sha256V3 = Annotated[
    str, StringConstraints(strict=True, pattern=r"^[0-9a-f]{64}$")
]
StrictFiniteFloatV3 = Annotated[float, Field(strict=True, allow_inf_nan=False)]
StrictPositiveFiniteFloatV3 = Annotated[
    float, Field(strict=True, gt=0.0, allow_inf_nan=False)
]


class ConfigModelV3(BaseModel):
    """Strict immutable base for every architecture-target config model."""

    model_config = ConfigDict(extra="forbid", frozen=True, validate_default=True)


class RuntimeProfileV3(str, Enum):
    """Exact architecture runtime-profile literals."""

    SIM_TRAIN = "sim_train"
    SIM_EVAL = "sim_eval"
    DEPLOY_SIM = "deploy_sim"
    DEPLOY_REAL = "deploy_real"


class NavigationModeV3(str, Enum):
    """Exact architecture navigation-mode literals."""

    LOCAL_TRAINING = "LOCAL_TRAINING"
    MAPPING = "MAPPING"
    NAV2_BASELINE = "NAV2_BASELINE"
    HYBRID_AI_LOCAL = "HYBRID_AI_LOCAL"


_VALID_NAVIGATION_MODES_BY_PROFILE_V3: Mapping[RuntimeProfileV3, frozenset[NavigationModeV3]] = MappingProxyType({
    RuntimeProfileV3.SIM_TRAIN: frozenset({NavigationModeV3.LOCAL_TRAINING}),
    RuntimeProfileV3.SIM_EVAL: frozenset(
        {NavigationModeV3.NAV2_BASELINE, NavigationModeV3.HYBRID_AI_LOCAL}
    ),
    RuntimeProfileV3.DEPLOY_SIM: frozenset(
        {
            NavigationModeV3.MAPPING,
            NavigationModeV3.NAV2_BASELINE,
            NavigationModeV3.HYBRID_AI_LOCAL,
        }
    ),
    RuntimeProfileV3.DEPLOY_REAL: frozenset(
        {
            NavigationModeV3.MAPPING,
            NavigationModeV3.NAV2_BASELINE,
            NavigationModeV3.HYBRID_AI_LOCAL,
        }
    ),
})


def validate_profile_mode_v3(
    runtime_profile: RuntimeProfileV3,
    navigation_mode: NavigationModeV3,
) -> None:
    """Reject a D03 pair not explicitly allowed by the frozen architecture."""

    if not isinstance(runtime_profile, RuntimeProfileV3):
        raise TypeError("runtime_profile must be RuntimeProfileV3")
    if not isinstance(navigation_mode, NavigationModeV3):
        raise TypeError("navigation_mode must be NavigationModeV3")
    if navigation_mode not in _VALID_NAVIGATION_MODES_BY_PROFILE_V3[runtime_profile]:
        raise ValueError(
            "navigation mode is not permitted for runtime profile: "
            f"{runtime_profile.value}/{navigation_mode.value}"
        )


class ConfigTokenV3(str, Enum):
    """Architecture token classes permitted only before resolution."""

    FIXED_ARCH = "FIXED_ARCH"
    SIM_BASELINE = "SIM_BASELINE"
    TBD_MEASURED = "TBD_MEASURED"
    TBD_PROJECT_ACCEPTANCE = "TBD_PROJECT_ACCEPTANCE"
    REQUIRED_BUILD_INPUT = "REQUIRED_BUILD_INPUT"


class TokenizedConfigInputV3(ConfigModelV3):
    """One unresolved input; it cannot be supplied as a resolved config."""

    field_path: IdentifierV3
    token: ConfigTokenV3
    reference_id: IdentifierV3


class ProjectIdentityV3(ConfigModelV3):
    """Project and robot identity bound into configuration provenance."""

    project_id: IdentifierV3
    robot_model_id: IdentifierV3
    architecture_sha256: Sha256V3


class ConfigProvenanceV3(ConfigModelV3):
    """Hashes and IDs that identify a fully resolved configuration."""

    config_hash: Sha256V3
    config_hash_algorithm: Literal["sha256"]
    resolution_policy_id: IdentifierV3
    source_manifest_sha256: Sha256V3


class RuntimeSelectionV3(ConfigModelV3):
    """Selected target/mode and the architecture time-source literal."""

    runtime_profile: RuntimeProfileV3
    navigation_mode: NavigationModeV3
    use_sim_time: StrictBool

    @model_validator(mode="after")
    def validate_profile_time_source(self) -> "RuntimeSelectionV3":
        validate_profile_mode_v3(self.runtime_profile, self.navigation_mode)
        expected = self.runtime_profile is not RuntimeProfileV3.DEPLOY_REAL
        if self.use_sim_time != expected:
            raise ValueError(
                "runtime profile requires its architecture-defined use_sim_time value"
            )
        return self


class FrameTfContractV3(ConfigModelV3):
    """Frame names and single-authority ownership declarations."""

    map_frame: IdentifierV3
    odom_frame: IdentifierV3
    base_frame: IdentifierV3
    lidar_frame: IdentifierV3
    map_to_odom_authority: IdentifierV3
    odom_to_base_link_authority: Literal["EKF"]
    base_link_to_lidar_authority: Literal["robot_state_publisher"]
    ground_truth_isolation_policy_id: IdentifierV3


class TopicQosContractV3(ConfigModelV3):
    """One topic with exact ownership, QoS, frame, and freshness IDs."""

    name: IdentifierV3
    message_type: IdentifierV3
    publisher_owner: IdentifierV3
    subscriber_owner: IdentifierV3
    qos_profile_id: IdentifierV3
    frame_contract_id: IdentifierV3
    freshness_policy_id: IdentifierV3


class StateEstimationContractV3(ConfigModelV3):
    """Wheel/IMU-to-EKF ownership contract."""

    wheel_odometry_source: IdentifierV3
    imu_source: IdentifierV3
    ekf_owner: Literal["robot_localization_EKF"]
    two_d_mode: StrictBool
    covariance_contract_id: IdentifierV3


class LocalizationContractV3(ConfigModelV3):
    """Localization provider and map-health contract."""

    provider: IdentifierV3
    map_id: IdentifierV3
    lifecycle_contract_id: IdentifierV3
    covariance_jump_contract_id: IdentifierV3


class NavigationContractV3(ConfigModelV3):
    """Planner/controller ownership and D10 position-settle contract IDs."""

    planner_owner: IdentifierV3
    controller_owner: IdentifierV3
    path_validity_contract_id: IdentifierV3
    local_reference_contract_id: IdentifierV3
    goal_type: Literal["position_only"]
    goal_settle_contract_id: IdentifierV3


class ObservationContractV3(ConfigModelV3):
    """The fixed D05 observation schema."""

    schema_id: Literal["obs-v3-l72-g3-t3-c3-f32"]
    dtype: Literal["float32"]
    lidar_sector_count: Literal[72]
    local_reference_components: tuple[
        Literal["distance"], Literal["sin_bearing"], Literal["cos_bearing"]
    ]
    measured_twist_components: tuple[Literal["vx"], Literal["vy"], Literal["wz"]]
    previous_final_issued_command_components: tuple[
        Literal["vx"], Literal["vy"], Literal["wz"]
    ]
    dimension: Literal[81]


class ActionContractV3(ConfigModelV3):
    """The fixed normalized holonomic action schema."""

    component_order: tuple[Literal["vx"], Literal["vy"], Literal["wz"]]
    dimension: Literal[3]
    normalized_minimum: Literal[-1.0]
    normalized_maximum: Literal[1.0]


class MotionLimitTargetPolicyV3(ConfigModelV3):
    """Resolved limit values plus their approved source class."""

    source_class: Literal["SIM_BASELINE", "MEASURED_REGISTRY"]
    source_id: IdentifierV3
    max_vx_mps: StrictPositiveFiniteFloatV3
    max_vy_mps: StrictPositiveFiniteFloatV3
    max_wz_radps: StrictPositiveFiniteFloatV3


class MapIdentityV3(ConfigModelV3):
    """Canonical map-artifact identity, not a package-local mutable copy."""

    map_id: IdentifierV3
    canonical_manifest_sha256: Sha256V3
    artifact_contract_id: IdentifierV3


class CommandSafetyContractV3(ConfigModelV3):
    """D06/D07 envelope and final-command ownership declarations."""

    command_envelope_contract_id: IdentifierV3
    safety_supervisor_owner: Literal["SafetySupervisor"]
    final_twist_publisher_owner: Literal["FinalTwistPublisher"]
    final_command_topic: Literal["/cmd_vel"]
    safety_policy_id: IdentifierV3


class RewardContractV3(ConfigModelV3):
    """Versioned reward boundary without runtime behavior."""

    contract_id: IdentifierV3
    contract_sha256: Sha256V3


class TrainingContractV3(ConfigModelV3):
    """Versioned training boundary without choosing unresolved settings."""

    algorithm_id: IdentifierV3
    contract_sha256: Sha256V3


class EvaluationContractV3(ConfigModelV3):
    """Versioned evaluation boundary and final-evaluation designation."""

    contract_id: IdentifierV3
    contract_sha256: Sha256V3
    final_evaluation: StrictBool


class AcceptanceContractV3(ConfigModelV3):
    """Pre-registered acceptance boundary; thresholds stay external."""

    contract_id: IdentifierV3
    contract_sha256: Sha256V3


class ResolvedConfigV3(ConfigModelV3):
    """Complete v3 resolved configuration; it has no tokenized fields."""

    schema_version: Literal["3.0"]
    project: ProjectIdentityV3
    runtime: RuntimeSelectionV3
    provenance: ConfigProvenanceV3
    frames_tf: FrameTfContractV3
    topics_qos: tuple[TopicQosContractV3, ...]
    state_estimation: StateEstimationContractV3
    localization: LocalizationContractV3
    navigation: NavigationContractV3
    observation: ObservationContractV3
    action: ActionContractV3
    motion_limits: MotionLimitTargetPolicyV3
    map_identity: MapIdentityV3
    command_safety: CommandSafetyContractV3
    reward: RewardContractV3
    training: TrainingContractV3
    evaluation: EvaluationContractV3
    acceptance: AcceptanceContractV3

    @model_validator(mode="after")
    def validate_deploy_real_measurement_source(self) -> "ResolvedConfigV3":
        if (
            self.runtime.runtime_profile is RuntimeProfileV3.DEPLOY_REAL
            and self.motion_limits.source_class != "MEASURED_REGISTRY"
        ):
            raise ValueError("deploy_real requires resolved measured motion limits")
        return self
