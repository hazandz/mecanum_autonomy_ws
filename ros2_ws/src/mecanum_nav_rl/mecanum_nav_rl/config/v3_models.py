"""Architecture-target configuration types, parallel to legacy v1.

Legacy v1 remains the existing input surface. These v3 types model the frozen
architecture target only; A0.3 owns compiler and loader migration.
"""

from __future__ import annotations

from enum import Enum
from math import isclose
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

AMCL_YAW_COVARIANCE_ROUNDOFF_TOLERANCE_RAD2 = 1e-12


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
    odom_to_base_link_authority: Literal['EKF']
    base_link_to_lidar_authority: Literal["robot_state_publisher"]
    ground_truth_isolation_policy_id: IdentifierV3


class LocalTrainingFrameTfContractV31(ConfigModelV3):
    """Schema 3.1 frame declarations without invented map/odom authority."""

    map_frame: None
    odom_frame: None
    base_frame: Literal['base_link']
    lidar_frame: Literal['lidar_frame']
    map_to_odom_authority: None
    odom_to_base_link_authority: None
    base_link_to_lidar_authority: Literal['robot_state_publisher']
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


class LocalTrainingStateEstimationV31(ConfigModelV3):
    """Schema 3.1 local-training estimate; internal and without a TF edge."""

    provider: Literal['INTERNAL_SIMULATED_ODOMETRY']
    policy_pose_source: Literal['NOISY_SIMULATED_ODOMETRY']
    ground_truth_policy_access: Literal[False]


class NotApplicableLocalizationV31(ConfigModelV3):
    """Explicit absence of map localization in LOCAL_TRAINING."""

    provider: Literal['NOT_APPLICABLE_LOCAL_TRAINING']
    map_id: None
    lifecycle_contract_id: None
    covariance_jump_contract_id: None


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
    local_training: 'LocalTrainingNavigationV31 | None' = None

    @model_validator(mode="after")
    def reject_explicit_null_step07_policy(self) -> "NavigationContractV3":
        if "step07_acceptance" in self.model_fields_set and self.step07_acceptance is None:
            raise ValueError("navigation.step07_acceptance must be omitted, not null")
        return self

    @model_validator(mode='after')
    def reject_explicit_null_local_training(self) -> 'NavigationContractV3':
        """Treat explicit null as an invalid mode-specific contract value."""
        if (
            'local_training' in self.model_fields_set
            and self.local_training is None
        ):
            raise ValueError(
                'navigation.local_training must be omitted, not null'
            )
        return self

    @model_serializer(mode="wrap")
    def omit_absent_step07_policy(self, handler):
        data = handler(self)
        if self.step07_acceptance is None:
            data.pop("step07_acceptance", None)
        if self.local_training is None:
            data.pop('local_training', None)
        return data


class LocalTrainingNavigationV31(ConfigModelV3):
    """NAV2-free planner, controller, and goal ownership for local training."""

    planner_owner: Literal['NONE']
    controller_owner: Literal['PPO']
    goal_source: Literal['LOCAL_TASK_GOAL']
    requires_amcl: Literal[False]
    requires_nav2: Literal[False]
    requires_follow_path: Literal[False]


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
    amcl_yaw_covariance_roundoff_tolerance_rad2: StrictFiniteFloatV3
    observation_twist_scales: tuple[StrictPositiveFiniteFloatV3, StrictPositiveFiniteFloatV3, StrictPositiveFiniteFloatV3]
    require_nonzero_nav2_command: StrictBool

    @model_validator(mode="after")
    def validate_policy_values(self) -> "Step07AcceptancePolicyV3":
        if (self.amcl_yaw_covariance_roundoff_tolerance_rad2
                != AMCL_YAW_COVARIANCE_ROUNDOFF_TOLERANCE_RAD2):
            raise ValueError(
                'Step07 AMCL yaw covariance roundoff tolerance is not approved'
            )
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
    canonical_manifest_sha256: Sha256V3 | None = None
    artifact_contract_id: IdentifierV3 | None = None
    training_binding: 'TrainingScenarioBindingV31 | None' = None

    @model_serializer(mode='wrap')
    def omit_absent_training_fields(self, handler):
        """Keep schema 3.0 output free of optional schema 3.1 keys."""
        data = handler(self)
        optional_fields = (
            'canonical_manifest_sha256',
            'artifact_contract_id',
            'training_binding',
        )
        for name in optional_fields:
            if name not in self.model_fields_set:
                data.pop(name, None)
        return data

    @model_validator(mode='after')
    def validate_map_binding(self) -> 'MapIdentityV3':
        """Require either a complete map identity or a scenario identity."""
        if (
            'training_binding' in self.model_fields_set
            and self.training_binding is None
        ):
            raise ValueError(
                'map_identity.training_binding must be omitted, not null'
            )
        if self.training_binding is None:
            if (
                self.canonical_manifest_sha256 is None
                or self.artifact_contract_id is None
            ):
                raise ValueError(
                    'map identity requires canonical map manifest fields'
                )
        elif (
            self.canonical_manifest_sha256 is not None
            or self.artifact_contract_id is not None
        ):
            raise ValueError(
                'training scenario binding cannot claim an occupancy-map hash'
            )
        return self


class TrainingScenarioBindingV31(ConfigModelV3):
    """World/scenario identity carried before future asset resolution."""

    scenario_id: IdentifierV3
    world_id: IdentifierV3
    asset_manifest_sha256: Sha256V3 | None = None
    binding_status: Literal['UNRESOLVED', 'BOUND', 'TEST_ONLY']

    @model_validator(mode='after')
    def validate_binding_status(self) -> 'TrainingScenarioBindingV31':
        """Keep unbound and test-only manifests out of production identity."""
        if (
            self.binding_status == 'BOUND'
            and self.asset_manifest_sha256 is None
        ):
            raise ValueError(
                'BOUND scenario requires an asset manifest SHA-256'
            )
        if (
            self.binding_status != 'BOUND'
            and self.asset_manifest_sha256 is not None
        ):
            raise ValueError(
                'unresolved and TEST_ONLY bindings cannot carry '
                'production hashes'
            )
        return self


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
    local_training: 'LocalTrainingContractV31 | None' = None

    @model_serializer(mode='wrap')
    def omit_absent_local_training(self, handler):
        """Keep schema 3.0 training serialization byte-compatible."""
        data = handler(self)
        if self.local_training is None:
            data.pop('local_training', None)
        return data

    @model_validator(mode='after')
    def reject_explicit_null_local_training(self) -> 'TrainingContractV3':
        """Disallow null as a schema 3.1 contract substitute."""
        if (
            'local_training' in self.model_fields_set
            and self.local_training is None
        ):
            raise ValueError(
                'training.local_training must be omitted, not null'
            )
        return self


class LocalTrainingContractV31(ConfigModelV3):
    """Typed simulation-only B2 training/noise/reset/scenario contract."""

    schema_id: Literal['mecanum.local_training/v1']
    backend_id: Literal['NATIVE_B2_BACKEND_PENDING']
    observation_schema_id: Literal['obs-v3-l72-g3-t3-c3-f32']
    command_components: tuple[Literal['vx'], Literal['vy'], Literal['wz']]
    max_vx_mps: StrictPositiveFiniteFloatV3
    max_vy_mps: StrictPositiveFiniteFloatV3
    max_wz_radps: StrictPositiveFiniteFloatV3
    max_planar_speed_mps: StrictPositiveFiniteFloatV3
    max_accel_xy_mps2: StrictPositiveFiniteFloatV3
    max_accel_yaw_radps2: StrictPositiveFiniteFloatV3
    max_jerk_xy_mps3: StrictPositiveFiniteFloatV3
    max_jerk_yaw_radps3: StrictPositiveFiniteFloatV3
    safety_period_ms: StrictInt
    policy_ttl_ms: StrictInt
    final_command_timeout_ms: StrictInt
    actuator_watchdog_ms: StrictInt
    scan_max_age_ms: StrictInt
    odometry_max_age_ms: StrictInt
    oracle_max_age_ms: StrictInt
    lifecycle_max_age_ms: StrictInt
    b1_receipt_max_age_ms: StrictInt
    backend_status_receive_age_ms: StrictInt
    robot_bounding_radius_m: StrictPositiveFiniteFloatV3
    clearance_margin_m: StrictPositiveFiniteFloatV3
    geometry_reserve_m: StrictPositiveFiniteFloatV3
    ros_scan_age_budget_s: StrictPositiveFiniteFloatV3
    steady_pipeline_budget_s: StrictPositiveFiniteFloatV3
    ros_steady_advance_envelope: StrictPositiveFiniteFloatV3
    physics_step_s: StrictPositiveFiniteFloatV3
    clock_quantization_reserve_s: StrictPositiveFiniteFloatV3
    proposed_braking_deceleration_mps2: StrictPositiveFiniteFloatV3
    braking_jerk_mps3: StrictPositiveFiniteFloatV3
    stopping_distance_m: StrictPositiveFiniteFloatV3
    stopping_distance_limit_m: StrictPositiveFiniteFloatV3
    noise_profile_id: Literal['B2_NOISE_N0_V1']
    position_bias_sigma_m: StrictFiniteFloatV3
    yaw_bias_sigma_rad: StrictFiniteFloatV3
    position_drift_sigma_m_per_tick: StrictFiniteFloatV3
    yaw_drift_sigma_rad_per_tick: StrictFiniteFloatV3
    linear_velocity_noise_sigma_mps: StrictFiniteFloatV3
    yaw_rate_noise_sigma_radps: StrictFiniteFloatV3
    noise_input_rate_hz: StrictPositiveFiniteFloatV3
    noise_delay_samples: StrictInt
    noise_dropout_probability: StrictFiniteFloatV3
    negative_delay_profile_id: Literal['B2_NOISE_DELAY_V1']
    negative_delay_samples: StrictInt
    negative_dropout_profile_id: Literal['B2_NOISE_DROP_V1']
    negative_dropout_probability: StrictFiniteFloatV3
    world_seed: StrictInt
    soak_seed_base: StrictInt
    soak_episode_count: StrictInt
    fault_seed_base: StrictInt
    world_id: Literal['b2_training_arena']
    robot_entity: Literal['mecanum_b2']
    arena_size_m: tuple[
        StrictPositiveFiniteFloatV3,
        StrictPositiveFiniteFloatV3,
    ]
    wall_height_m: StrictPositiveFiniteFloatV3
    wall_thickness_m: StrictPositiveFiniteFloatV3
    obstacle_center_xy_m: tuple[StrictFiniteFloatV3, StrictFiniteFloatV3]
    obstacle_size_xyz_m: tuple[
        StrictPositiveFiniteFloatV3,
        StrictPositiveFiniteFloatV3,
        StrictPositiveFiniteFloatV3,
    ]
    sensor_profile_id: Literal['B2_GENERIC_2D_V1']
    lidar_rate_hz: StrictPositiveFiniteFloatV3
    lidar_beam_count: StrictInt
    lidar_min_range_m: StrictPositiveFiniteFloatV3
    lidar_max_range_m: StrictPositiveFiniteFloatV3
    lidar_frame: Literal['lidar_frame']
    ground_truth_rate_hz: StrictPositiveFiniteFloatV3
    exact_scan_odometry_pairing: Literal[True]
    pairing_tolerance_ns: StrictInt
    buffer_capacity: StrictInt
    reference_source: Literal['GT_ODOM_2D']
    policy_reference_source: Literal['NOISY_EMULATOR_ODOMETRY']
    world_to_task_mapping: Literal['IDENTITY_XY_YAW']
    nominal_collection_period_s: StrictPositiveFiniteFloatV3
    successful_reset_count: StrictInt
    issued_policy_command_count: StrictInt
    collection_cutoff_semantics: Literal['CENSORED_EXPOSURE_NOT_TERMINAL']
    baseline_controller: Literal['Nav2_DWB_NOT_RUN_IN_LOCAL_TRAINING']
    physics_target_realtime_factor: StrictPositiveFiniteFloatV3
    spawn_xyz_yaw: tuple[
        StrictFiniteFloatV3,
        StrictFiniteFloatV3,
        StrictFiniteFloatV3,
        StrictFiniteFloatV3,
    ]
    contact_probe_size_m: StrictPositiveFiniteFloatV3
    contact_probe_mass_kg: StrictPositiveFiniteFloatV3
    scan_angle_min_rad: StrictFiniteFloatV3
    scan_angle_max_rad: StrictFiniteFloatV3
    scenario_soak_start_xy_yaw: tuple[
        StrictFiniteFloatV3,
        StrictFiniteFloatV3,
        StrictFiniteFloatV3,
    ]
    scenario_soak_goal_xy: tuple[StrictFiniteFloatV3, StrictFiniteFloatV3]
    scenario_goal_settle_zero_command: tuple[
        StrictFiniteFloatV3,
        StrictFiniteFloatV3,
        StrictFiniteFloatV3,
    ]
    scenario_goal_settle_position_xy: tuple[
        StrictFiniteFloatV3,
        StrictFiniteFloatV3,
    ]
    scenario_contact_start_xy_yaw: tuple[
        StrictFiniteFloatV3,
        StrictFiniteFloatV3,
        StrictFiniteFloatV3,
    ]
    scenario_contact_goal_xy: tuple[StrictFiniteFloatV3, StrictFiniteFloatV3]
    reset_total_deadline_steady_s: StrictPositiveFiniteFloatV3
    reset_standstill_phase_deadline_steady_s: StrictPositiveFiniteFloatV3
    reset_braking_target_ros_s: StrictPositiveFiniteFloatV3
    reset_service_timeout_s: StrictPositiveFiniteFloatV3
    reset_pause_resume_timeout_s: StrictPositiveFiniteFloatV3
    reset_xy_tolerance_m: StrictPositiveFiniteFloatV3
    reset_yaw_tolerance_rad: StrictPositiveFiniteFloatV3
    reset_roll_pitch_tolerance_rad: StrictPositiveFiniteFloatV3
    reset_z_tolerance_m: StrictPositiveFiniteFloatV3
    standstill_linear_speed_mps: StrictPositiveFiniteFloatV3
    standstill_angular_speed_radps: StrictPositiveFiniteFloatV3
    standstill_duration_ros_s: StrictPositiveFiniteFloatV3
    standstill_minimum_samples: StrictInt
    reset_footprint_clearance_expansion_m: StrictPositiveFiniteFloatV3
    ingress_queue_capacity: StrictInt
    maximum_tracked_collisions: StrictInt
    clock_unintended_stall_zero_ms: StrictInt
    clock_stall_infrastructure_abort_ms: StrictInt
    observation0_requires_post_barrier_zero_receipt: Literal[True]
    receipt_is_publication_evidence_only: Literal[True]
    backend_status_not_actuator_ack: Literal[True]
    paused_contact_heartbeat_advances_coverage: Literal[False]
    spawn_pose_proposal_test_only: Literal[True]
    scenario_soak_id: Literal['B2_SOAK_V1']
    scenario_goal_settle_id: Literal['B2_GOAL_SETTLE_V1']
    scenario_contact_id: Literal['B2_CONTACT_V1']
    soak_first_episode_count: StrictInt
    soak_first_episode_steps: StrictInt
    soak_remaining_episode_count: StrictInt
    soak_remaining_episode_steps: StrictInt
    motion_coverage_required: tuple[
        Literal['forward'],
        Literal['reverse'],
        Literal['lateral'],
        Literal['rotation'],
        Literal['diagonal'],
        Literal['mixed'],
    ]
    evaluation_horizon: Literal['TASK_HORIZON']
    reset_control_service: Literal[
        '/world/b2_training_arena/control'
    ]
    reset_pose_service: Literal[
        '/world/b2_training_arena/set_pose'
    ]
    reset_pose_service_type: Literal['ros_gz_interfaces/srv/SetEntityPose']

    @model_validator(mode='after')
    def validate_local_training_contract(self) -> 'LocalTrainingContractV31':
        """Reject values outside the Owner-approved simulation descriptor."""
        exact = {
            'max_vx_mps': 0.25, 'max_vy_mps': 0.20, 'max_wz_radps': 0.80,
            'max_planar_speed_mps': 0.32015621187164245,
            'max_accel_xy_mps2': 0.50, 'max_accel_yaw_radps2': 1.0,
            'max_jerk_xy_mps3': 2.0, 'max_jerk_yaw_radps3': 4.0,
            'safety_period_ms': 20, 'policy_ttl_ms': 200,
            'final_command_timeout_ms': 100, 'actuator_watchdog_ms': 100,
            'scan_max_age_ms': 500, 'odometry_max_age_ms': 250,
            'oracle_max_age_ms': 250, 'lifecycle_max_age_ms': 500,
            'b1_receipt_max_age_ms': 500, 'backend_status_receive_age_ms': 200,
            'stopping_distance_limit_m': 0.92,
            'robot_bounding_radius_m': 0.35, 'clearance_margin_m': 0.05,
            'geometry_reserve_m': 0.02, 'ros_scan_age_budget_s': 0.50,
            'steady_pipeline_budget_s': 0.10,
            'ros_steady_advance_envelope': 2.0, 'physics_step_s': 0.01,
            'clock_quantization_reserve_s': 0.01,
            'proposed_braking_deceleration_mps2': 0.50,
            'braking_jerk_mps3': 2.0,
            'position_bias_sigma_m': 0.005, 'yaw_bias_sigma_rad': 0.010,
            'position_drift_sigma_m_per_tick': 0.0001,
            'yaw_drift_sigma_rad_per_tick': 0.0001,
            'linear_velocity_noise_sigma_mps': 0.003,
            'yaw_rate_noise_sigma_radps': 0.005,
            'noise_input_rate_hz': 100.0,
            'noise_delay_samples': 0, 'noise_dropout_probability': 0.0,
            'negative_delay_samples': 30, 'negative_dropout_probability': 1.0,
            'world_seed': 20261029, 'soak_seed_base': 2026102900,
            'soak_episode_count': 30, 'fault_seed_base': 2026103000,
            'lidar_beam_count': 500, 'pairing_tolerance_ns': 0,
            'buffer_capacity': 64, 'successful_reset_count': 30,
            'issued_policy_command_count': 1000,
            'physics_target_realtime_factor': 1.0,
            'contact_probe_size_m': 0.10, 'contact_probe_mass_kg': 1.0,
            'scenario_goal_settle_zero_command': (0.0, 0.0, 0.0),
            'reset_total_deadline_steady_s': 15.0,
            'reset_standstill_phase_deadline_steady_s': 5.0,
            'reset_braking_target_ros_s': 2.0,
            'reset_service_timeout_s': 1.0,
            'reset_pause_resume_timeout_s': 2.0,
            'reset_xy_tolerance_m': 0.01, 'reset_yaw_tolerance_rad': 0.02,
            'reset_roll_pitch_tolerance_rad': 0.05,
            'reset_z_tolerance_m': 0.02,
            'standstill_linear_speed_mps': 0.01,
            'standstill_angular_speed_radps': 0.02,
            'standstill_duration_ros_s': 0.20,
            'standstill_minimum_samples': 21,
            'reset_footprint_clearance_expansion_m': 0.05,
            'ingress_queue_capacity': 128, 'maximum_tracked_collisions': 64,
            'clock_unintended_stall_zero_ms': 200,
            'clock_stall_infrastructure_abort_ms': 1000,
            'scenario_goal_settle_position_xy': (0.0, 0.0),
            'soak_first_episode_count': 10,
            'soak_first_episode_steps': 34,
            'soak_remaining_episode_count': 20,
            'soak_remaining_episode_steps': 33,
        }
        for name, value in exact.items():
            if getattr(self, name) != value:
                raise ValueError(
                    f'LOCAL_TRAINING {name} differs from approved contract'
                )
        if not isclose(
            self.stopping_distance_m, 0.906224, rel_tol=0.0, abs_tol=1e-6
        ):
            raise ValueError(
                'LOCAL_TRAINING stopping envelope calculation is invalid'
            )
        if self.stopping_distance_limit_m < self.stopping_distance_m:
            raise ValueError(
                'stopping-distance limit is below the proposed envelope'
            )
        if (
            self.scan_angle_min_rad != -3.141592653589793
            or self.scan_angle_max_rad != 3.141592653589793
        ):
            raise ValueError(
                'LOCAL_TRAINING LiDAR angular range differs from contract'
            )
        if (
            self.arena_size_m != (8.0, 8.0)
            or self.wall_height_m != 1.0
            or self.wall_thickness_m != 0.20
        ):
            raise ValueError(
                'LOCAL_TRAINING world dimensions differ from '
                'approved descriptor'
            )
        if (
            self.obstacle_center_xy_m != (2.5, 0.0)
            or self.obstacle_size_xyz_m != (0.20, 1.0, 1.0)
        ):
            raise ValueError(
                'LOCAL_TRAINING obstacle descriptor differs from contract'
            )
        if (
            self.lidar_rate_hz != 10.0
            or self.lidar_min_range_m != 0.10
            or self.lidar_max_range_m != 8.0
            or self.ground_truth_rate_hz != 100.0
        ):
            raise ValueError(
                'LOCAL_TRAINING sensor descriptor differs from contract'
            )
        return self


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

    schema_version: Literal['3.0', '3.1']
    project: ProjectIdentityV3
    runtime: RuntimeSelectionV3
    provenance: ConfigProvenanceV3
    frames_tf: FrameTfContractV3 | LocalTrainingFrameTfContractV31
    topics_qos: tuple[TopicQosContractV3, ...]
    state_estimation: (
        StateEstimationContractV3 | LocalTrainingStateEstimationV31
    )
    localization: LocalizationContractV3 | NotApplicableLocalizationV31
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
        local_training = (
            self.runtime.navigation_mode is NavigationModeV3.LOCAL_TRAINING
        )
        if self.schema_version == '3.0' and (
            isinstance(self.state_estimation, LocalTrainingStateEstimationV31)
            or isinstance(self.localization, NotApplicableLocalizationV31)
            or isinstance(self.frames_tf, LocalTrainingFrameTfContractV31)
        ):
            raise ValueError(
                'schema 3.0 cannot use schema 3.1 training domains'
            )
        if self.schema_version == '3.1':
            if (
                not local_training
                or self.runtime.runtime_profile
                is not RuntimeProfileV3.SIM_TRAIN
            ):
                raise ValueError(
                    'schema 3.1 is restricted to sim_train/LOCAL_TRAINING'
                )
            if not isinstance(
                self.state_estimation, LocalTrainingStateEstimationV31
            ):
                raise ValueError(
                    'schema 3.1 requires internal simulated odometry domain'
                )
            if not isinstance(self.localization, NotApplicableLocalizationV31):
                raise ValueError(
                    'schema 3.1 requires NOT_APPLICABLE_LOCAL_TRAINING'
                )
            if not isinstance(self.frames_tf, LocalTrainingFrameTfContractV31):
                raise ValueError(
                    'schema 3.1 requires the local-training frame contract'
                )
            if self.training.local_training is None:
                raise ValueError(
                    'schema 3.1 requires typed LOCAL_TRAINING contract'
                )
            if self.map_identity.training_binding is None:
                raise ValueError(
                    'schema 3.1 requires scenario/world binding input'
                )
            if self.map_identity.training_binding.binding_status != 'BOUND':
                raise ValueError(
                    'production compiler rejects unresolved or TEST_ONLY '
                    'assets'
                )
            if (
                self.frames_tf.map_frame is not None
                or self.frames_tf.odom_frame is not None
            ):
                raise ValueError(
                    'LOCAL_TRAINING must not claim map or odom frames'
                )
            if (
                self.frames_tf.map_to_odom_authority is not None
                or self.frames_tf.odom_to_base_link_authority is not None
            ):
                raise ValueError(
                    'LOCAL_TRAINING must not claim map/odom TF authority'
                )
            if (
                self.frames_tf.base_frame != 'base_link'
                or self.frames_tf.lidar_frame != 'lidar_frame'
            ):
                raise ValueError(
                    'LOCAL_TRAINING requires base_link and lidar_frame'
                )
            if (
                self.navigation.local_training is None
                or self.navigation.step07_acceptance is not None
            ):
                raise ValueError(
                    'schema 3.1 requires local-task navigation without '
                    'Step07 policy'
                )
            if (
                self.navigation.planner_owner != 'NONE'
                or self.navigation.controller_owner != 'PPO'
            ):
                raise ValueError(
                    'LOCAL_TRAINING cannot activate Nav2 planner/controller'
                )
        elif (
            self.training.local_training is not None
            or self.navigation.local_training is not None
            or self.map_identity.training_binding is not None
        ):
            raise ValueError(
                'schema 3.0 serialization cannot contain '
                'LOCAL_TRAINING additions'
            )
        if (
            self.runtime.runtime_profile is RuntimeProfileV3.DEPLOY_REAL
            and self.motion_limits.source_class != "MEASURED_REGISTRY"
        ):
            raise ValueError("deploy_real requires resolved measured motion limits")
        return self
