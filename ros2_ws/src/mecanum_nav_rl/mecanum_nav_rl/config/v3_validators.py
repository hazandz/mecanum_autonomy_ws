"""Static semantic validation of fully resolved architecture v3 config."""

from __future__ import annotations

from mecanum_nav_rl.config.v3_models import ResolvedConfigV3, RuntimeProfileV3
from mecanum_nav_rl.config.v3_policy import validate_profile_mode_v3


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
    if config.frames_tf.odom_to_base_link_authority != "EKF":
        raise ValueError("only EKF may own odom to base_link")
    if config.frames_tf.base_link_to_lidar_authority != "robot_state_publisher":
        raise ValueError("robot_state_publisher must own base_link to lidar")
    if config.frames_tf.map_to_odom_authority != config.localization.provider:
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
