"""Static semantic validation of fully resolved architecture v3 config."""

from __future__ import annotations

from collections.abc import Mapping

from mecanum_nav_rl.config.v3_models import (
    ActionContractV3,
    LocalTrainingContractV31,
    LocalTrainingFrameTfContractV31,
    LocalTrainingNavigationV31,
    LocalTrainingStateEstimationV31,
    MapIdentityV3,
    MotionLimitTargetPolicyV3,
    NavigationContractV3,
    NavigationModeV3,
    NotApplicableLocalizationV31,
    ResolvedConfigV3,
    RuntimeProfileV3,
    RuntimeSelectionV3,
    TopicQosContractV3,
)
from mecanum_nav_rl.config.v3_policy import validate_profile_mode_v3

from pydantic import ValidationError


def validate_local_training_static_input_v3(
    document: Mapping[str, object],
) -> None:
    """Validate schema 3.1 structure and cross-section invariants pre-binding.

    This accepts unresolved build inputs but never creates a resolved model or
    hash. Asset binding remains the production compiler's later gate.
    """
    if document.get('schema_version') != '3.1':
        return
    if 'action' not in document:
        raise ValueError('schema 3.1 requires the action contract')
    expected_roots = set(ResolvedConfigV3.model_fields)
    if set(document) != expected_roots:
        raise ValueError(
            'schema 3.1 canonical root set differs from ResolvedConfigV3'
        )
    try:
        runtime = RuntimeSelectionV3.model_validate(document['runtime'])
        if (
            runtime.runtime_profile is not RuntimeProfileV3.SIM_TRAIN
            or runtime.navigation_mode is not NavigationModeV3.LOCAL_TRAINING
        ):
            raise ValueError(
                'schema 3.1 requires sim_train/LOCAL_TRAINING mode'
            )
        try:
            action = ActionContractV3.model_validate(document['action'])
        except ValidationError as error:
            raise ValueError(f'invalid action contract: {error}') from error
        if action.component_order != ('vx', 'vy', 'wz'):
            raise ValueError('action contract order must be vx, vy, wz')
        frames = LocalTrainingFrameTfContractV31.model_validate(
            document['frames_tf']
        )
        if frames.map_frame is not None or frames.odom_frame is not None:
            raise ValueError(
                'LOCAL_TRAINING frame contract cannot claim map/odom'
            )
        LocalTrainingStateEstimationV31.model_validate(
            document['state_estimation']
        )
        NotApplicableLocalizationV31.model_validate(document['localization'])
        navigation = NavigationContractV3.model_validate(
            document['navigation']
        )
        local_navigation = navigation.local_training
        if not isinstance(local_navigation, LocalTrainingNavigationV31):
            raise ValueError('LOCAL_TRAINING navigation domain is missing')
        if (
            navigation.planner_owner != 'NONE'
            or navigation.controller_owner != 'PPO'
            or navigation.step07_acceptance is not None
        ):
            raise ValueError('LOCAL_TRAINING cannot mix Nav2/Step07 domains')
        training_root = document['training']
        if not isinstance(training_root, Mapping):
            raise ValueError('training section must be a mapping')
        training = LocalTrainingContractV31.model_validate(
            training_root.get('local_training')
        )
        motion = MotionLimitTargetPolicyV3.model_validate(
            document['motion_limits']
        )
        map_raw = document['map_identity']
        if not isinstance(map_raw, Mapping) or not isinstance(
            map_raw.get('training_binding'), Mapping
        ):
            raise ValueError('schema 3.1 requires an asset/scenario binding')
        map_identity = MapIdentityV3.model_validate(map_raw)
        binding = map_identity.training_binding
        if binding is None:
            raise ValueError(
                'training world/scenario binding input is required'
            )
        if (
            binding.world_id != training.world_id
            or map_identity.map_id != training.world_id
        ):
            raise ValueError('training world binding differs across sections')
        if (
            binding.binding_status == 'BOUND'
            and binding.scenario_id == 'B2_TRAINING_SCENARIO_REQUIRED'
        ):
            raise ValueError('placeholder scenario cannot be production-bound')
        if motion.source_class != 'SIM_BASELINE':
            raise ValueError('motion_limits.source_class must be SIM_BASELINE')
        expected_limits = {
            'max_vx_mps': 0.25,
            'max_vy_mps': 0.20,
            'max_wz_radps': 0.80,
        }
        for field, expected in expected_limits.items():
            if getattr(motion, field) != expected:
                raise ValueError(
                    f'motion_limits.{field} differs from approved value'
                )
            if getattr(training, field) != getattr(motion, field):
                raise ValueError(
                    f'motion_limits.{field} differs from '
                    'training.local_training'
                )
        topics_raw = document['topics_qos']
        if not isinstance(topics_raw, (list, tuple)):
            raise ValueError('topics_qos must be a list of topic contracts')
        topics = tuple(
            TopicQosContractV3.model_validate(item) for item in topics_raw
        )
        names = tuple(topic.name for topic in topics)
        if len(names) != len(set(names)):
            raise ValueError('topics_qos contains duplicate topic names')
        scan = tuple(topic for topic in topics if topic.name == '/scan')
        if len(scan) != 1:
            raise ValueError('topics_qos requires exactly one /scan topic')
        if scan[0].qos_profile_id != 'BEST_EFFORT_VOLATILE_KEEP_LAST_5':
            raise ValueError(
                '/scan QoS must be BEST_EFFORT_VOLATILE_KEEP_LAST_5'
            )
    except (KeyError, TypeError) as error:
        raise ValueError(
            f'invalid schema 3.1 static input: {error}'
        ) from error
    except ValueError:
        raise


def validate_resolved_config_v3(config: ResolvedConfigV3) -> None:
    """Fail closed on architecture semantics representable by the v3 model."""

    if not isinstance(config, ResolvedConfigV3):
        raise TypeError("config must be ResolvedConfigV3")
    validate_profile_mode_v3(
        config.runtime.runtime_profile, config.runtime.navigation_mode
    )
    expected_sim_time = config.runtime.runtime_profile is not RuntimeProfileV3.DEPLOY_REAL
    if config.runtime.use_sim_time != expected_sim_time:
        raise ValueError("resolved v3 use_sim_time violates its runtime profile")
    step07_policy = config.navigation.step07_acceptance
    if (config.runtime.runtime_profile is RuntimeProfileV3.SIM_EVAL
            and config.runtime.navigation_mode.value == "NAV2_BASELINE"
            and step07_policy is None):
        raise ValueError("sim_eval/NAV2_BASELINE requires hashed Step07 acceptance policy")
    if step07_policy is not None and (
        config.runtime.runtime_profile is not RuntimeProfileV3.SIM_EVAL
        or config.runtime.navigation_mode.value != "NAV2_BASELINE"
    ):
        raise ValueError("Step07 acceptance policy is restricted to sim_eval/NAV2_BASELINE")
    if config.schema_version == '3.1':
        if config.frames_tf.odom_to_base_link_authority is not None:
            raise ValueError(
                'LOCAL_TRAINING must not advertise a TF odometry authority'
            )
        if config.frames_tf.map_to_odom_authority is not None:
            raise ValueError(
                'LOCAL_TRAINING must not advertise map to odom authority'
            )
    elif config.frames_tf.odom_to_base_link_authority != 'EKF':
        raise ValueError("only EKF may own odom to base_link")
    if config.frames_tf.base_link_to_lidar_authority != "robot_state_publisher":
        raise ValueError("robot_state_publisher must own base_link to lidar")
    if (
        config.schema_version != '3.1'
        and (
            config.frames_tf.map_to_odom_authority
            != config.localization.provider
        )
    ):
        raise ValueError("map to odom authority must match localization provider")
    if not config.topics_qos:
        raise ValueError("resolved v3 config requires at least one topic/QoS contract")
    if config.observation.dimension != 81 or config.observation.dtype != "float32":
        raise ValueError("observation must preserve the fixed 81-D float32 contract")
    if config.action.component_order != ("vx", "vy", "wz"):
        raise ValueError("action order must be vx, vy, wz")
    if (
        config.action.dimension != 3
        or config.action.normalized_minimum != -1.0
        or config.action.normalized_maximum != 1.0
    ):
        raise ValueError("action must preserve the fixed normalized 3-D contract")
    if (
        config.command_safety.final_twist_publisher_owner != "FinalTwistPublisher"
        or config.command_safety.final_command_topic != "/cmd_vel"
    ):
        raise ValueError("FinalTwistPublisher must be the only final /cmd_vel owner")
    if (
        config.motion_limits.source_class == "SIM_BASELINE"
        and config.runtime.runtime_profile
        not in {RuntimeProfileV3.SIM_TRAIN, RuntimeProfileV3.SIM_EVAL}
    ):
        raise ValueError(
            "SIM_BASELINE motion limits are valid only for sim_train or sim_eval"
        )
    if (
        config.runtime.runtime_profile is RuntimeProfileV3.DEPLOY_REAL
        and config.motion_limits.source_class != "MEASURED_REGISTRY"
    ):
        raise ValueError("deploy_real requires a measured-registry motion source")
