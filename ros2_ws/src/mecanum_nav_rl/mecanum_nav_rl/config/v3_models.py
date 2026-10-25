"""Architecture-target configuration types, parallel to legacy v1.

Legacy v1 remains the existing input surface. These v3 types model the frozen
architecture target only; A0.3 owns compiler and loader migration.
"""

from __future__ import annotations

from enum import Enum
from types import MappingProxyType
from typing import Annotated, Literal, Mapping

from pydantic import (BaseModel, ConfigDict, Field, StrictBool, StrictInt,
                      model_serializer, model_validator)
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
    step07_acceptance: "Step07AcceptancePolicyV3 | None" = None

    @model_validator(mode="after")
    def reject_explicit_null_step07_policy(self) -> "NavigationContractV3":
        if "step07_acceptance" in self.model_fields_set and self.step07_acceptance is None:
            raise ValueError("navigation.step07_acceptance must be omitted, not null")
        return self

    @model_serializer(mode="wrap")
    def omit_absent_step07_policy(self, handler):
        data = handler(self)
        if self.step07_acceptance is None:
            data.pop("step07_acceptance", None)
        return data


class Step07AcceptancePolicyV3(ConfigModelV3):
    """SIM-only integrated runtime acceptance policy included in config_hash."""

    schema_id: Literal["mecanum.step07.research_acceptance/v1"]
    runtime_profile: Literal["sim_eval"]
    navigation_mode: Literal["NAV2_BASELINE"]
    use_sim_time: StrictBool
    freshness_ms: Mapping[str, StrictInt]
    synchronization_ms: StrictInt
    reference_age_ms: StrictInt
    tf_wait_ms: StrictInt
    buffer_capacity: StrictInt
    observation_samples_minimum: StrictInt
    sample_report_limit: StrictInt
    local_reference_lookahead_m: StrictPositiveFiniteFloatV3
    local_reference_backtrack_m: StrictFiniteFloatV3
    local_reference_forward_window_m: StrictPositiveFiniteFloatV3
    local_reference_max_deviation_m: StrictPositiveFiniteFloatV3
    mission_deadline_s: StrictPositiveFiniteFloatV3
    campaign_deadline_s: StrictPositiveFiniteFloatV3
    shutdown_reserve_s: StrictPositiveFiniteFloatV3
    goal_settle_s: StrictPositiveFiniteFloatV3
    goal_xy_tolerance_m: StrictPositiveFiniteFloatV3
    goal_linear_speed_mps: StrictFiniteFloatV3
    goal_angular_speed_radps: StrictFiniteFloatV3
    localization_max_covariance: StrictPositiveFiniteFloatV3
    localization_pose_max_age_s: StrictPositiveFiniteFloatV3
    localization_translation_jump_base_m: StrictPositiveFiniteFloatV3
    localization_translation_jump_speed_mps: StrictPositiveFiniteFloatV3
    localization_yaw_jump_base_rad: StrictPositiveFiniteFloatV3
    localization_yaw_jump_speed_radps: StrictPositiveFiniteFloatV3
    observation_twist_scales: tuple[StrictPositiveFiniteFloatV3, StrictPositiveFiniteFloatV3, StrictPositiveFiniteFloatV3]
    require_nonzero_nav2_command: StrictBool

    @model_validator(mode="after")
    def validate_policy_values(self) -> "Step07AcceptancePolicyV3":
        expected = {
            "scan": 500, "wheel_ingress": 200, "imu_ingress": 200,
            "filtered_odometry": 250, "lifecycle": 500, "receipt": 500,
        }
        if dict(self.freshness_ms) != expected:
            raise ValueError("Step07 freshness policy must match approved SIM_BASELINE")
        if (self.use_sim_time is not True or self.synchronization_ms != 50
                or self.reference_age_ms != 250 or self.tf_wait_ms != 200
                or self.buffer_capacity != 64 or self.observation_samples_minimum != 5
                or self.sample_report_limit != 5
                or self.local_reference_lookahead_m != 0.50
                or self.local_reference_backtrack_m != 0.10
                or self.local_reference_forward_window_m != 1.0
                or self.local_reference_max_deviation_m != 0.50):
            raise ValueError("Step07 synchronization/sample policy differs from SIM_BASELINE")
        if (self.mission_deadline_s != 240 or self.campaign_deadline_s != 480
                or self.shutdown_reserve_s != 20 or self.goal_settle_s != 1.0
                or self.goal_xy_tolerance_m != 0.15
                or self.goal_linear_speed_mps != 0.03
                or self.goal_angular_speed_radps != 0.05
                or self.localization_max_covariance != 0.25
                or self.localization_pose_max_age_s != 2.0
                or self.localization_translation_jump_base_m != 0.50
                or self.localization_translation_jump_speed_mps != 0.35
                or self.localization_yaw_jump_base_rad != 0.50
                or self.localization_yaw_jump_speed_radps != 1.0
                or self.observation_twist_scales != (0.25, 0.20, 0.80)
                or self.require_nonzero_nav2_command is not True):
            raise ValueError("Step07 mission acceptance differs from approved SIM_BASELINE")
        return self


class ObservationInputProfileV3(ConfigModelV3):
    """The fixed D05 observation input profile."""

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


class ObservationContractV3(ConfigModelV3):
    """Observation root with the architecture-required nested profile."""

    input_profile: ObservationInputProfileV3

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy_constructor_fields(cls, value: object) -> object:
        """Accept the pre-nesting Python constructor while serializing nested.

        This is a source compatibility shim for callers constructing the model
        directly. Mapping/config inputs remain required to use input_profile.
        """
        if not isinstance(value, Mapping):
            return value
        flat_names = {
            "schema_id",
            "dtype",
            "lidar_sector_count",
            "local_reference_components",
            "measured_twist_components",
            "previous_final_issued_command_components",
            "dimension",
        }
        if "input_profile" in value or not (flat_names & set(value)):
            return value
        if set(value) != flat_names:
            return value
        return {"input_profile": dict(value)}

    @property
    def schema_id(self) -> str:
        return self.input_profile.schema_id

    @property
    def dtype(self) -> str:
        return self.input_profile.dtype

    @property
    def lidar_sector_count(self) -> int:
        return self.input_profile.lidar_sector_count

    @property
    def local_reference_components(self) -> tuple[str, str, str]:
        return self.input_profile.local_reference_components

    @property
    def measured_twist_components(self) -> tuple[str, str, str]:
        return self.input_profile.measured_twist_components

    @property
    def previous_final_issued_command_components(self) -> tuple[str, str, str]:
        return self.input_profile.previous_final_issued_command_components

    @property
    def dimension(self) -> int:
        return self.input_profile.dimension


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
