"""Offline tests for the fail-closed architecture-target V3 compiler."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest
from pydantic import ValidationError

from mecanum_nav_rl.config.v3_compiler import (
    ApprovalProvenanceV3,
    ApprovedExperimentOverrideV3,
    ApprovedMeasuredRegistryV3,
    compile_v3_config,
    deep_merge_v3,
)
from mecanum_nav_rl.config.v3_hashing import (
    canonical_v3_hash_payload,
    config_v3_sha256,
    hash_payload_from_resolved_v3,
)
from mecanum_nav_rl.config.v3_loader import load_v3_mapping, load_v3_yaml_mapping
from mecanum_nav_rl.config.v3_policy import ResolutionStageV3


_HASH = "a" * 64
_APPROVAL = ApprovalProvenanceV3("approval_test_v3", "b" * 64)


def _base_layer() -> dict[str, object]:
    """Complete synthetic resolved data, deliberately without config_hash."""

    return {
        "schema_version": "3.0",
        "project": {
            "project_id": "test_project",
            "robot_model_id": "test_robot",
            "architecture_sha256": _HASH,
        },
        "runtime": {
            "runtime_profile": "sim_train",
            "navigation_mode": "LOCAL_TRAINING",
            "use_sim_time": True,
        },
        "provenance": {
            "config_hash_algorithm": "sha256",
            "resolution_policy_id": "test_resolution_v3",
            "source_manifest_sha256": _HASH,
        },
        "frames_tf": {
            "map_frame": "map",
            "odom_frame": "odom",
            "base_frame": "base_link",
            "lidar_frame": "lidar_frame",
            "map_to_odom_authority": "AMCL",
            "odom_to_base_link_authority": "EKF",
            "base_link_to_lidar_authority": "robot_state_publisher",
            "ground_truth_isolation_policy_id": "hidden_gt_v1",
        },
        "topics_qos": [
            {
                "name": "/scan",
                "message_type": "sensor_msgs/msg/LaserScan",
                "publisher_owner": "test_sensor",
                "subscriber_owner": "test_observer",
                "qos_profile_id": "Q_SCAN",
                "frame_contract_id": "scan_frame_v1",
                "freshness_policy_id": "scan_freshness_v1",
            }
        ],
        "state_estimation": {
            "wheel_odometry_source": "test_wheel_odometry",
            "imu_source": "test_imu",
            "ekf_owner": "robot_localization_EKF",
            "two_d_mode": True,
            "covariance_contract_id": "test_covariance_v1",
        },
        "localization": {
            "provider": "AMCL",
            "map_id": "test_map",
            "lifecycle_contract_id": "test_localization_lifecycle_v1",
            "covariance_jump_contract_id": "test_localization_health_v1",
        },
        "navigation": {
            "planner_owner": "Nav2PlannerServer",
            "controller_owner": "PPO",
            "path_validity_contract_id": "test_path_v1",
            "local_reference_contract_id": "base_reference_v1",
            "goal_type": "position_only",
            "goal_settle_contract_id": "test_settle_v1",
        },
        "observation": {
            "schema_id": "obs-v3-l72-g3-t3-c3-f32",
            "dtype": "float32",
            "lidar_sector_count": 72,
            "local_reference_components": ["distance", "sin_bearing", "cos_bearing"],
            "measured_twist_components": ["vx", "vy", "wz"],
            "previous_final_issued_command_components": ["vx", "vy", "wz"],
            "dimension": 81,
        },
        "action": {
            "component_order": ["vx", "vy", "wz"],
            "dimension": 3,
            "normalized_minimum": -1.0,
            "normalized_maximum": 1.0,
        },
        "motion_limits": {
            "source_class": "SIM_BASELINE",
            "source_id": "test_sim_baseline_v1",
            "max_vx_mps": 0.4,
            "max_vy_mps": 0.4,
            "max_wz_radps": 1.0,
        },
        "map_identity": {
            "map_id": "test_map",
            "canonical_manifest_sha256": _HASH,
            "artifact_contract_id": "artifact_map_manifest_v1",
        },
        "command_safety": {
            "command_envelope_contract_id": "command_envelope_v1",
            "safety_supervisor_owner": "SafetySupervisor",
            "final_twist_publisher_owner": "FinalTwistPublisher",
            "final_command_topic": "/cmd_vel",
            "safety_policy_id": "test_safety_v1",
        },
        "reward": {"contract_id": "test_reward_v1", "contract_sha256": _HASH},
        "training": {"algorithm_id": "PPO", "contract_sha256": _HASH},
        "evaluation": {
            "contract_id": "test_evaluation_v1",
            "contract_sha256": _HASH,
            "final_evaluation": False,
        },
        "acceptance": {"contract_id": "test_acceptance_v1", "contract_sha256": _HASH},
    }


def _compile(
    base: dict[str, object] | None = None,
    *,
    runtime: dict[str, object] | None = None,
    navigation: dict[str, object] | None = None,
    experiment: ApprovedExperimentOverrideV3 | None = None,
    measured: ApprovedMeasuredRegistryV3 | None = None,
    output_stage: ResolutionStageV3 = ResolutionStageV3.CONFIG_INPUT,
    gate4: bool = False,
) -> object:
    return compile_v3_config(
        base_layer=_base_layer() if base is None else base,
        runtime_profile_layer=runtime or {"runtime": {"runtime_profile": "sim_train", "use_sim_time": True}},
        navigation_mode_layer=navigation or {"runtime": {"navigation_mode": "LOCAL_TRAINING"}},
        experiment_override_layer=experiment,
        measured_hardware_registry_layer=measured,
        output_stage=output_stage,
        gate4=gate4,
    )


def test_valid_five_layer_merge_is_immutable_and_non_mutating() -> None:
    base = _base_layer()
    before = deepcopy(base)
    experiment = ApprovedExperimentOverrideV3(
        {"navigation": {"local_reference_contract_id": "experiment_reference_v1"}},
        _APPROVAL,
    )
    measured = ApprovedMeasuredRegistryV3(
        {"navigation": {"local_reference_contract_id": "measured_reference_v1"}},
        "synthetic_measured_registry_v1",
        "c" * 64,
        _APPROVAL,
    )
    config = _compile(base, experiment=experiment, measured=measured)
    assert config.navigation.local_reference_contract_id == "measured_reference_v1"
    assert base == before
    with pytest.raises(Exception):
        config.runtime.use_sim_time = False  # type: ignore[misc]


def test_deep_merge_is_nested_deterministic_and_non_mutating() -> None:
    lower = {"a": {"b": 1, "c": 2}}
    higher = {"a": {"b": 3}}
    assert deep_merge_v3(lower, higher) == {"a": {"b": 3, "c": 2}}
    assert lower == {"a": {"b": 1, "c": 2}}
    with pytest.raises(ValueError, match="type conflict"):
        deep_merge_v3({"a": {"b": 1}}, {"a": 2})


def test_compiler_enforces_d03_and_time_source_without_caller_validator() -> None:
    with pytest.raises(ValueError, match="not permitted"):
        _compile(runtime={"runtime": {"runtime_profile": "sim_train", "use_sim_time": True}}, navigation={"runtime": {"navigation_mode": "NAV2_BASELINE"}})
    with pytest.raises(ValueError, match="invalid use_sim_time"):
        _compile(runtime={"runtime": {"runtime_profile": "deploy_real", "use_sim_time": True}}, navigation={"runtime": {"navigation_mode": "NAV2_BASELINE"}})


def test_compiler_rejects_invalid_and_unresolved_tokens() -> None:
    invalid = _base_layer()
    invalid["motion_limits"] = {
        "field_path": "motion_limits.max_vx_mps",
        "token": "SIM_BASELINE",
        "reference_id": "sim_limits",
    }
    with pytest.raises(ValueError, match="SIM_BASELINE"):
        _compile(
            invalid,
            runtime={"runtime": {"runtime_profile": "deploy_sim", "use_sim_time": True}},
            navigation={"runtime": {"navigation_mode": "NAV2_BASELINE"}},
        )
    unresolved = _base_layer()
    unresolved["reward"] = {
        "field_path": "reward.contract_id",
        "token": "FIXED_ARCH",
        "reference_id": "pending_reward",
    }
    with pytest.raises(ValueError, match="unresolved"):
        _compile(unresolved)


def test_privileged_layers_and_deploy_real_measured_registry_are_fail_closed() -> None:
    with pytest.raises(TypeError, match="approved provenance wrapper"):
        _compile(experiment={"navigation": {}})  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="approved provenance wrapper"):
        _compile(measured={"motion_limits": {}})  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="SIM_BASELINE motion limits"):
        _compile(
            runtime={"runtime": {"runtime_profile": "deploy_real", "use_sim_time": False}},
            navigation={"runtime": {"navigation_mode": "NAV2_BASELINE"}},
        )
    registry = ApprovedMeasuredRegistryV3(
        {
            "motion_limits": {
                "source_class": "MEASURED_REGISTRY",
                "source_id": "synthetic_measured_registry_v1",
                "max_vx_mps": 0.4,
                "max_vy_mps": 0.4,
                "max_wz_radps": 1.0,
            }
        },
        "synthetic_measured_registry_v1",
        "c" * 64,
        _APPROVAL,
    )
    assert _compile(
        runtime={"runtime": {"runtime_profile": "deploy_real", "use_sim_time": False}},
        navigation={"runtime": {"navigation_mode": "NAV2_BASELINE"}},
        measured=registry,
    ).motion_limits.source_class == "MEASURED_REGISTRY"


def test_hash_is_canonical_semantic_and_never_self_referential() -> None:
    first = _base_layer()
    second = {key: first[key] for key in reversed(tuple(first))}
    assert config_v3_sha256(first) == config_v3_sha256(second)
    changed = deepcopy(first)
    changed["navigation"]["local_reference_contract_id"] = "other_reference_v1"  # type: ignore[index]
    assert config_v3_sha256(first) != config_v3_sha256(changed)
    config = _compile(first)
    assert config.provenance.config_hash == config_v3_sha256(first)
    payload = hash_payload_from_resolved_v3(config)
    assert "config_hash" not in payload["resolved_config_without_config_hash"]["provenance"]  # type: ignore[index]
    with_hash = _base_layer()
    with_hash["provenance"]["config_hash"] = _HASH  # type: ignore[index]
    with pytest.raises(ValueError, match="config_hash"):
        _compile(with_hash)
    with pytest.raises(ValueError, match="config_hash"):
        canonical_v3_hash_payload(with_hash)


def test_loader_rejects_invalid_yaml_keys_duplicates_and_unknown_runtime_fields(
    tmp_path: Path,
) -> None:
    duplicate = tmp_path / "duplicate.yaml"
    duplicate.write_text("a: 1\na: 2\n", encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate"):
        load_v3_yaml_mapping(duplicate)
    malformed = tmp_path / "malformed.yaml"
    malformed.write_text("a: [unterminated\n", encoding="utf-8")
    with pytest.raises(ValueError, match="invalid v3 YAML"):
        load_v3_yaml_mapping(malformed)
    with pytest.raises(ValueError, match="string"):
        load_v3_mapping({1: "not_allowed"})  # type: ignore[dict-item]
    extra = _base_layer()
    extra["runtime_timestamp"] = "2026-01-01T00:00:00Z"
    with pytest.raises(ValidationError, match="runtime_timestamp"):
        _compile(extra)


def _measured_registry() -> ApprovedMeasuredRegistryV3:
    return ApprovedMeasuredRegistryV3(
        {
            "motion_limits": {
                "source_class": "MEASURED_REGISTRY",
                "source_id": "synthetic_measured_registry_v1",
                "max_vx_mps": 0.4,
                "max_vy_mps": 0.4,
                "max_wz_radps": 1.0,
            }
        },
        "synthetic_measured_registry_v1",
        "c" * 64,
        _APPROVAL,
    )


@pytest.mark.parametrize(
    ("profile", "mode"),
    (
        ("deploy_sim", "NAV2_BASELINE"),
        ("deploy_real", "NAV2_BASELINE"),
    ),
)
def test_compiler_rejects_sim_baseline_for_deployment_profiles(
    profile: str, mode: str
) -> None:
    with pytest.raises(ValueError, match="SIM_BASELINE motion limits"):
        _compile(
            runtime={"runtime": {"runtime_profile": profile, "use_sim_time": profile != "deploy_real"}},
            navigation={"runtime": {"navigation_mode": mode}},
        )


def test_measured_source_class_requires_matching_registry_provenance() -> None:
    base = _base_layer()
    base["motion_limits"] = {
        "source_class": "MEASURED_REGISTRY",
        "source_id": "synthetic_measured_registry_v1",
        "max_vx_mps": 0.4,
        "max_vy_mps": 0.4,
        "max_wz_radps": 1.0,
    }
    with pytest.raises(ValueError, match="require an approved measured registry"):
        _compile(base)
    with pytest.raises(ValueError, match="require an approved measured registry"):
        _compile(
            base,
            runtime={"runtime": {"runtime_profile": "deploy_real", "use_sim_time": False}},
            navigation={"runtime": {"navigation_mode": "NAV2_BASELINE"}},
        )
    mismatched = ApprovedMeasuredRegistryV3(
        {
            "motion_limits": {
                "source_class": "MEASURED_REGISTRY",
                "source_id": "different_registry_v1",
                "max_vx_mps": 0.4,
                "max_vy_mps": 0.4,
                "max_wz_radps": 1.0,
            }
        },
        "synthetic_measured_registry_v1",
        "c" * 64,
        _APPROVAL,
    )
    with pytest.raises(ValueError, match="source_id must match registry_id"):
        _compile(base, measured=mismatched)


@pytest.mark.parametrize(
    ("profile", "mode", "source_class"),
    (
        ("sim_train", "LOCAL_TRAINING", "SIM_BASELINE"),
        ("sim_eval", "NAV2_BASELINE", "SIM_BASELINE"),
        ("sim_train", "LOCAL_TRAINING", "MEASURED_REGISTRY"),
        ("sim_eval", "NAV2_BASELINE", "MEASURED_REGISTRY"),
        ("deploy_sim", "NAV2_BASELINE", "MEASURED_REGISTRY"),
        ("deploy_real", "NAV2_BASELINE", "MEASURED_REGISTRY"),
    ),
)
def test_profile_source_class_policy_accepts_only_approved_combinations(
    profile: str, mode: str, source_class: str
) -> None:
    measured = _measured_registry() if source_class == "MEASURED_REGISTRY" else None
    config = _compile(
        runtime={"runtime": {"runtime_profile": profile, "use_sim_time": profile != "deploy_real"}},
        navigation={"runtime": {"navigation_mode": mode}},
        measured=measured,
    )
    assert config.motion_limits.source_class == source_class


@pytest.mark.parametrize(
    ("token", "profile", "mode", "final_evaluation", "gate4", "stage", "message"),
    (
        ("TBD_MEASURED", "deploy_real", "NAV2_BASELINE", False, False, ResolutionStageV3.CONFIG_INPUT, "TBD_MEASURED"),
        ("TBD_MEASURED", "sim_train", "LOCAL_TRAINING", False, True, ResolutionStageV3.CONFIG_INPUT, "TBD_MEASURED"),
        ("TBD_PROJECT_ACCEPTANCE", "sim_train", "LOCAL_TRAINING", True, False, ResolutionStageV3.CONFIG_INPUT, "TBD_PROJECT_ACCEPTANCE"),
        ("REQUIRED_BUILD_INPUT", "sim_train", "LOCAL_TRAINING", False, False, ResolutionStageV3.BUILD_OUTPUT, "REQUIRED_BUILD_INPUT"),
        ("REQUIRED_BUILD_INPUT", "sim_train", "LOCAL_TRAINING", False, False, ResolutionStageV3.DEPLOY_OUTPUT, "REQUIRED_BUILD_INPUT"),
    ),
)
def test_compiler_applies_each_required_token_context(
    token: str,
    profile: str,
    mode: str,
    final_evaluation: bool,
    gate4: bool,
    stage: ResolutionStageV3,
    message: str,
) -> None:
    base = _base_layer()
    base["reward"] = {
        "field_path": "reward.contract_id",
        "token": token,
        "reference_id": "pending_input",
    }
    base["evaluation"]["final_evaluation"] = final_evaluation  # type: ignore[index]
    with pytest.raises(ValueError, match=message):
        _compile(
            base,
            runtime={"runtime": {"runtime_profile": profile, "use_sim_time": profile != "deploy_real"}},
            navigation={"runtime": {"navigation_mode": mode}},
            output_stage=stage,
            gate4=gate4,
        )


def test_compiler_rejects_tf_localization_and_empty_topic_contracts() -> None:
    wrong_authority = _base_layer()
    wrong_authority["frames_tf"]["map_to_odom_authority"] = "SLAM"  # type: ignore[index]
    with pytest.raises(ValueError, match="map to odom authority"):
        _compile(wrong_authority)
    empty_topics = _base_layer()
    empty_topics["topics_qos"] = []
    with pytest.raises(ValueError, match="at least one topic/QoS"):
        _compile(empty_topics)
