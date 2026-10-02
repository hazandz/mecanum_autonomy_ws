"""Core-only tests for the parallel architecture v3 configuration surface."""

from __future__ import annotations

import ast
from math import inf, nan
from pathlib import Path

import pytest
from pydantic import ValidationError

import mecanum_nav_rl.config as config_api
from mecanum_nav_rl.config.models import ResolvedConfig as LegacyResolvedConfig
import mecanum_nav_rl.config.v3_models as v3_models
import mecanum_nav_rl.config.v3_policy as v3_policy
from mecanum_nav_rl.config.v3_models import (
    AcceptanceContractV3,
    ActionContractV3,
    CommandSafetyContractV3,
    ConfigProvenanceV3,
    ConfigTokenV3,
    EvaluationContractV3,
    FrameTfContractV3,
    LocalizationContractV3,
    MapIdentityV3,
    MotionLimitTargetPolicyV3,
    NavigationContractV3,
    NavigationModeV3,
    ObservationContractV3,
    ProjectIdentityV3,
    ResolvedConfigV3,
    RewardContractV3,
    RuntimeProfileV3,
    RuntimeSelectionV3,
    StateEstimationContractV3,
    TokenizedConfigInputV3,
    TopicQosContractV3,
    TrainingContractV3,
)
from mecanum_nav_rl.config.v3_policy import (
    ResolutionStageV3,
    TokenPolicyContextV3,
    validate_profile_mode_v3,
    validate_tokenized_input_v3,
)


_HASH = "a" * 64


def _config(
    *,
    profile: RuntimeProfileV3 = RuntimeProfileV3.SIM_TRAIN,
    mode: NavigationModeV3 = NavigationModeV3.LOCAL_TRAINING,
) -> ResolvedConfigV3:
    """Build a complete test-only resolved v3 object without tokens."""

    return ResolvedConfigV3(
        schema_version="3.0",
        project=ProjectIdentityV3(
            project_id="test_project",
            robot_model_id="test_robot",
            architecture_sha256=_HASH,
        ),
        runtime=RuntimeSelectionV3(
            runtime_profile=profile,
            navigation_mode=mode,
            use_sim_time=profile is not RuntimeProfileV3.DEPLOY_REAL,
        ),
        provenance=ConfigProvenanceV3(
            config_hash=_HASH,
            config_hash_algorithm="sha256",
            resolution_policy_id="test_resolution_v3",
            source_manifest_sha256=_HASH,
        ),
        frames_tf=FrameTfContractV3(
            map_frame="map",
            odom_frame="odom",
            base_frame="base_link",
            lidar_frame="lidar_frame",
            map_to_odom_authority="AMCL",
            odom_to_base_link_authority="EKF",
            base_link_to_lidar_authority="robot_state_publisher",
            ground_truth_isolation_policy_id="hidden_gt_v1",
        ),
        topics_qos=(
            TopicQosContractV3(
                name="/scan",
                message_type="sensor_msgs/msg/LaserScan",
                publisher_owner="test_sensor",
                subscriber_owner="test_observer",
                qos_profile_id="Q_SCAN",
                frame_contract_id="scan_frame_v1",
                freshness_policy_id="scan_freshness_v1",
            ),
        ),
        state_estimation=StateEstimationContractV3(
            wheel_odometry_source="test_wheel_odometry",
            imu_source="test_imu",
            ekf_owner="robot_localization_EKF",
            two_d_mode=True,
            covariance_contract_id="test_covariance_v1",
        ),
        localization=LocalizationContractV3(
            provider="AMCL",
            map_id="test_map",
            lifecycle_contract_id="test_localization_lifecycle_v1",
            covariance_jump_contract_id="test_localization_health_v1",
        ),
        navigation=NavigationContractV3(
            planner_owner="Nav2PlannerServer",
            controller_owner="PPO",
            path_validity_contract_id="test_path_v1",
            local_reference_contract_id="test_reference_v1",
            goal_type="position_only",
            goal_settle_contract_id="test_settle_v1",
        ),
        observation=ObservationContractV3(
            schema_id="obs-v3-l72-g3-t3-c3-f32",
            dtype="float32",
            lidar_sector_count=72,
            local_reference_components=("distance", "sin_bearing", "cos_bearing"),
            measured_twist_components=("vx", "vy", "wz"),
            previous_final_issued_command_components=("vx", "vy", "wz"),
            dimension=81,
        ),
        action=ActionContractV3(
            component_order=("vx", "vy", "wz"),
            dimension=3,
            normalized_minimum=-1.0,
            normalized_maximum=1.0,
        ),
        motion_limits=MotionLimitTargetPolicyV3(
            source_class=(
                "MEASURED_REGISTRY"
                if profile is RuntimeProfileV3.DEPLOY_REAL
                else "SIM_BASELINE"
            ),
            source_id=(
                "test_measured_registry_v1"
                if profile is RuntimeProfileV3.DEPLOY_REAL
                else "test_sim_baseline_v1"
            ),
            max_vx_mps=0.4,
            max_vy_mps=0.4,
            max_wz_radps=1.0,
        ),
        map_identity=MapIdentityV3(
            map_id="test_map",
            canonical_manifest_sha256=_HASH,
            artifact_contract_id="artifact_map_manifest_v1",
        ),
        command_safety=CommandSafetyContractV3(
            command_envelope_contract_id="command_envelope_v1",
            safety_supervisor_owner="SafetySupervisor",
            final_twist_publisher_owner="FinalTwistPublisher",
            final_command_topic="/cmd_vel",
            safety_policy_id="test_safety_v1",
        ),
        reward=RewardContractV3(contract_id="test_reward_v1", contract_sha256=_HASH),
        training=TrainingContractV3(algorithm_id="PPO", contract_sha256=_HASH),
        evaluation=EvaluationContractV3(
            contract_id="test_evaluation_v1",
            contract_sha256=_HASH,
            final_evaluation=False,
        ),
        acceptance=AcceptanceContractV3(
            contract_id="test_acceptance_v1", contract_sha256=_HASH
        ),
    )


def _context(
    *,
    profile: RuntimeProfileV3 = RuntimeProfileV3.SIM_TRAIN,
    final_evaluation: bool = False,
    gate4: bool = False,
    stage: ResolutionStageV3 = ResolutionStageV3.CONFIG_INPUT,
) -> TokenPolicyContextV3:
    return TokenPolicyContextV3(profile, final_evaluation, gate4, stage)


def _token(token: ConfigTokenV3) -> TokenizedConfigInputV3:
    return TokenizedConfigInputV3(
        field_path="test_field", token=token, reference_id="test_reference"
    )


def test_enum_literals_are_exact() -> None:
    assert tuple(item.value for item in RuntimeProfileV3) == (
        "sim_train", "sim_eval", "deploy_sim", "deploy_real"
    )
    assert tuple(item.value for item in NavigationModeV3) == (
        "LOCAL_TRAINING", "MAPPING", "NAV2_BASELINE", "HYBRID_AI_LOCAL"
    )


@pytest.mark.parametrize(
    ("profile", "mode"),
    (
        (RuntimeProfileV3.SIM_TRAIN, NavigationModeV3.LOCAL_TRAINING),
        (RuntimeProfileV3.SIM_EVAL, NavigationModeV3.NAV2_BASELINE),
        (RuntimeProfileV3.SIM_EVAL, NavigationModeV3.HYBRID_AI_LOCAL),
        (RuntimeProfileV3.DEPLOY_SIM, NavigationModeV3.MAPPING),
        (RuntimeProfileV3.DEPLOY_SIM, NavigationModeV3.NAV2_BASELINE),
        (RuntimeProfileV3.DEPLOY_SIM, NavigationModeV3.HYBRID_AI_LOCAL),
        (RuntimeProfileV3.DEPLOY_REAL, NavigationModeV3.MAPPING),
        (RuntimeProfileV3.DEPLOY_REAL, NavigationModeV3.NAV2_BASELINE),
        (RuntimeProfileV3.DEPLOY_REAL, NavigationModeV3.HYBRID_AI_LOCAL),
    ),
)
def test_all_allowed_profile_mode_pairs_pass(
    profile: RuntimeProfileV3, mode: NavigationModeV3
) -> None:
    validate_profile_mode_v3(profile, mode)


def test_invalid_profile_mode_pair_fails_closed() -> None:
    with pytest.raises(ValueError, match="not permitted"):
        validate_profile_mode_v3(
            RuntimeProfileV3.SIM_TRAIN, NavigationModeV3.NAV2_BASELINE
        )


@pytest.mark.parametrize(
    ("profile", "mode"),
    (
        (RuntimeProfileV3.SIM_TRAIN, NavigationModeV3.LOCAL_TRAINING),
        (RuntimeProfileV3.SIM_EVAL, NavigationModeV3.NAV2_BASELINE),
        (RuntimeProfileV3.SIM_EVAL, NavigationModeV3.HYBRID_AI_LOCAL),
        (RuntimeProfileV3.DEPLOY_SIM, NavigationModeV3.MAPPING),
        (RuntimeProfileV3.DEPLOY_SIM, NavigationModeV3.NAV2_BASELINE),
        (RuntimeProfileV3.DEPLOY_SIM, NavigationModeV3.HYBRID_AI_LOCAL),
        (RuntimeProfileV3.DEPLOY_REAL, NavigationModeV3.MAPPING),
        (RuntimeProfileV3.DEPLOY_REAL, NavigationModeV3.NAV2_BASELINE),
        (RuntimeProfileV3.DEPLOY_REAL, NavigationModeV3.HYBRID_AI_LOCAL),
    ),
)
def test_allowed_pairs_construct_runtime_and_complete_resolved_models(
    profile: RuntimeProfileV3, mode: NavigationModeV3
) -> None:
    runtime = RuntimeSelectionV3.model_validate(
        {
            "runtime_profile": profile,
            "navigation_mode": mode,
            "use_sim_time": profile is not RuntimeProfileV3.DEPLOY_REAL,
        }
    )
    assert runtime.runtime_profile is profile
    assert _config(profile=profile, mode=mode).runtime == runtime


@pytest.mark.parametrize(
    ("profile", "mode"),
    (
        (RuntimeProfileV3.SIM_TRAIN, NavigationModeV3.NAV2_BASELINE),
        (RuntimeProfileV3.SIM_TRAIN, NavigationModeV3.HYBRID_AI_LOCAL),
        (RuntimeProfileV3.SIM_TRAIN, NavigationModeV3.MAPPING),
        (RuntimeProfileV3.SIM_EVAL, NavigationModeV3.LOCAL_TRAINING),
        (RuntimeProfileV3.SIM_EVAL, NavigationModeV3.MAPPING),
        (RuntimeProfileV3.DEPLOY_SIM, NavigationModeV3.LOCAL_TRAINING),
        (RuntimeProfileV3.DEPLOY_REAL, NavigationModeV3.LOCAL_TRAINING),
    ),
)
def test_invalid_pairs_fail_at_runtime_and_resolved_pydantic_boundaries(
    profile: RuntimeProfileV3, mode: NavigationModeV3
) -> None:
    runtime_payload = {
        "runtime_profile": profile,
        "navigation_mode": mode,
        "use_sim_time": profile is not RuntimeProfileV3.DEPLOY_REAL,
    }
    with pytest.raises(ValidationError, match="not permitted"):
        RuntimeSelectionV3.model_validate(runtime_payload)
    payload = _config().model_dump()
    payload["runtime"] = runtime_payload
    with pytest.raises(ValidationError, match="not permitted"):
        ResolvedConfigV3.model_validate(payload)


def test_time_source_invariants_remain_model_boundary_rejections() -> None:
    with pytest.raises(ValidationError):
        RuntimeSelectionV3.model_validate(
            {
                "runtime_profile": RuntimeProfileV3.DEPLOY_REAL,
                "navigation_mode": NavigationModeV3.NAV2_BASELINE,
                "use_sim_time": True,
            }
        )
    with pytest.raises(ValidationError):
        RuntimeSelectionV3.model_validate(
            {
                "runtime_profile": RuntimeProfileV3.SIM_TRAIN,
                "navigation_mode": NavigationModeV3.LOCAL_TRAINING,
                "use_sim_time": False,
            }
        )


def test_policy_reexports_the_single_model_d03_validator() -> None:
    assert v3_policy.validate_profile_mode_v3 is v3_models.validate_profile_mode_v3


@pytest.mark.parametrize(
    ("token", "context"),
    (
        (ConfigTokenV3.SIM_BASELINE, _context()),
        (ConfigTokenV3.FIXED_ARCH, _context(profile=RuntimeProfileV3.DEPLOY_REAL)),
        (ConfigTokenV3.TBD_MEASURED, _context()),
        (ConfigTokenV3.TBD_PROJECT_ACCEPTANCE, _context()),
        (ConfigTokenV3.REQUIRED_BUILD_INPUT, _context()),
    ),
)
def test_token_policy_accepts_only_unresolved_inputs_allowed_at_context(
    token: ConfigTokenV3, context: TokenPolicyContextV3
) -> None:
    validate_tokenized_input_v3(_token(token), context)


@pytest.mark.parametrize(
    ("token", "context"),
    (
        (ConfigTokenV3.SIM_BASELINE, _context(profile=RuntimeProfileV3.DEPLOY_SIM)),
        (ConfigTokenV3.TBD_MEASURED, _context(profile=RuntimeProfileV3.DEPLOY_REAL)),
        (ConfigTokenV3.TBD_MEASURED, _context(gate4=True)),
        (ConfigTokenV3.TBD_PROJECT_ACCEPTANCE, _context(final_evaluation=True)),
        (ConfigTokenV3.REQUIRED_BUILD_INPUT, _context(stage=ResolutionStageV3.BUILD_OUTPUT)),
    ),
)
def test_token_policy_rejects_forbidden_context(
    token: ConfigTokenV3, context: TokenPolicyContextV3
) -> None:
    with pytest.raises(ValueError):
        validate_tokenized_input_v3(_token(token), context)


def test_resolved_config_rejects_extra_mutation_token_and_missing_section() -> None:
    config = _config()
    with pytest.raises(ValidationError):
        ResolvedConfigV3.model_validate({**config.model_dump(), "extra": "no"})
    with pytest.raises(ValidationError):
        config.project.project_id = "mutated"  # type: ignore[misc]
    payload = config.model_dump()
    payload["project"] = _token(ConfigTokenV3.FIXED_ARCH).model_dump()
    with pytest.raises(ValidationError):
        ResolvedConfigV3.model_validate(payload)
    payload = config.model_dump()
    del payload["command_safety"]
    with pytest.raises(ValidationError):
        ResolvedConfigV3.model_validate(payload)


@pytest.mark.parametrize("invalid", ("A" * 64, "a" * 63, "a" * 63 + "G"))
def test_sha_and_identity_are_strict(invalid: str) -> None:
    payload = _config().model_dump()
    payload["project"]["architecture_sha256"] = invalid
    with pytest.raises(ValidationError):
        ResolvedConfigV3.model_validate(payload)
    payload = _config().model_dump()
    payload["project"]["project_id"] = "contains whitespace"
    with pytest.raises(ValidationError):
        ResolvedConfigV3.model_validate(payload)


@pytest.mark.parametrize("invalid", (True, nan, inf, -inf))
def test_motion_limit_rejects_boolean_nan_and_inf(invalid: object) -> None:
    payload = _config().model_dump()
    payload["motion_limits"]["max_vx_mps"] = invalid
    with pytest.raises(ValidationError):
        ResolvedConfigV3.model_validate(payload)


def test_observation_and_action_contracts_are_exact() -> None:
    config = _config()
    assert config.observation.dimension == 81
    assert config.observation.lidar_sector_count == 72
    assert config.observation.local_reference_components == (
        "distance", "sin_bearing", "cos_bearing"
    )
    assert config.observation.previous_final_issued_command_components == (
        "vx", "vy", "wz"
    )
    assert config.action.component_order == ("vx", "vy", "wz")
    assert config.action.dimension == 3
    assert config.action.normalized_minimum == -1.0
    assert config.action.normalized_maximum == 1.0


def test_v1_v3_boundary_is_explicit() -> None:
    assert LegacyResolvedConfig is not ResolvedConfigV3
    assert not hasattr(config_api, "ResolvedConfig")
    config_root = Path(__file__).resolve().parents[1] / "mecanum_nav_rl" / "config"
    for name in ("models.py", "loader.py", "compiler.py", "hashing.py"):
        assert "v3_" not in (config_root / name).read_text(encoding="utf-8")


def test_v3_modules_import_no_runtime_or_policy_frameworks() -> None:
    config_root = Path(__file__).resolve().parents[1] / "mecanum_nav_rl" / "config"
    prohibited_roots = {
        "rclpy", "gazebo", "gz", "ignition", "gymnasium",
        "stable_baselines3", "subprocess",
    }
    for name in (
        "v3_models.py",
        "v3_policy.py",
        "v3_loader.py",
        "v3_compiler.py",
        "v3_hashing.py",
        "v3_validators.py",
    ):
        tree = ast.parse((config_root / name).read_text(encoding="utf-8"))
        imported = {
            alias.name.split(".", 1)[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        imported.update(
            node.module.split(".", 1)[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module is not None
        )
        assert not imported & prohibited_roots
