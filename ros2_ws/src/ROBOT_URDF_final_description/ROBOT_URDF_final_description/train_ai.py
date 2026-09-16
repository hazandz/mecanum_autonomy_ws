#!/usr/bin/env python3
"""Train, validate, stress-test, and evaluate PPO Mecanum policies.

The script uses contacts as collision truth, safety-oriented model selection,
seeded domain randomization, disjoint scenario splits, and an independent
ControlWorld-stepped validation simulator.  It never treats increasing reward
as evidence that a policy is safe or deployable.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import platform
import random
import subprocess
import sys
import time
from collections import deque
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any, Deque, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import gymnasium
import numpy as np
import rclpy
import stable_baselines3
import torch
from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import BaseCallback, CallbackList
from stable_baselines3.common.env_checker import check_env
from stable_baselines3.common.monitor import Monitor

try:
    from ROBOT_URDF_final_description.mecanum_env import (
        ActionConfig,
        DomainRandomizationConfig,
        EnvConfig,
        MecanumEnv,
        REQUIRED_INFO_KEYS,
        RewardConfig,
        RosInterfaceConfig,
        SafetyConfig,
        ScenarioConfig,
        SensorConfig,
    )
except ImportError:
    from mecanum_env import (  # type: ignore[no-redef]
        ActionConfig,
        DomainRandomizationConfig,
        EnvConfig,
        MecanumEnv,
        REQUIRED_INFO_KEYS,
        RewardConfig,
        RosInterfaceConfig,
        SafetyConfig,
        ScenarioConfig,
        SensorConfig,
    )


MONITOR_INFO_KEYS = tuple(REQUIRED_INFO_KEYS) + (
    # Episode-local SE(2) odom->task alignment diagnostics from mecanum_env.py.
    # These are diagnostics only; they are not policy observations.
    "odom_task_frame_aligned",
    "odom_to_task_x",
    "odom_to_task_y",
    "odom_to_task_yaw",
    "path_efficiency",
    "spl",
    "r_progress",
    "r_time",
    "r_safety",
    "r_smooth",
    "r_stuck",
    "r_terminal",
)


def set_global_seed(seed: int) -> None:
    """Seed Python, NumPy, PyTorch, CUDA and SB3's global helpers."""
    os.environ["PYTHONHASHSEED"] = str(seed)
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    try:
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False
    except Exception:
        pass


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=("train", "evaluate", "robustness", "smoke"),
        default="train",
    )
    parser.add_argument("--seeds", nargs="+", type=int, default=[0])
    parser.add_argument("--timesteps", type=int, default=2_000_000)
    parser.add_argument("--output-dir", default="./runs/mecanum_ppo")
    parser.add_argument("--model-path")
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument(
        "--progress-bar", action=argparse.BooleanOptionalAction, default=True
    )

    parser.add_argument("--n-steps", type=int, default=2048)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--n-epochs", type=int, default=10)
    parser.add_argument("--learning-rate", type=float, default=3e-4)
    parser.add_argument("--gamma", type=float, default=0.99)
    parser.add_argument("--gae-lambda", type=float, default=0.95)
    parser.add_argument("--clip-range", type=float, default=0.20)
    parser.add_argument("--ent-coef", type=float, default=0.01)
    parser.add_argument("--vf-coef", type=float, default=0.50)
    parser.add_argument("--max-grad-norm", type=float, default=0.50)
    parser.add_argument("--checkpoint-freq", type=int, default=50_000)

    parser.add_argument("--world-name", default="world_demo")
    parser.add_argument("--robot-entity", default="ROBOT_URDF_final")
    parser.add_argument("--cmd-vel-topic", default="/cmd_vel")
    parser.add_argument("--scan-topic", default="/scan")
    parser.add_argument("--odom-topic", default="/odom")
    parser.add_argument("--collision-topic", default="/collision")
    parser.add_argument("--set-pose-service")
    parser.add_argument("--control-world-service")
    parser.add_argument(
        "--require-ground-truth-collision",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    parser.add_argument(
        "--stepping-mode",
        choices=("sim_time", "control_world"),
        default="sim_time",
    )
    parser.add_argument("--physics-step-size", type=float, default=0.01)
    parser.add_argument("--control-dt", type=float, default=0.10)
    parser.add_argument("--startup-timeout", type=float, default=10.0)
    parser.add_argument("--sensor-timeout", type=float, default=2.0)
    parser.add_argument("--wall-timeout", type=float, default=5.0)
    parser.add_argument("--max-sensor-skew", type=float, default=0.08)
    parser.add_argument("--max-sensor-age", type=float, default=0.25)

    parser.add_argument("--lidar-sectors", type=int, default=72)
    parser.add_argument("--lidar-min", type=float, default=0.12)
    parser.add_argument("--lidar-max", type=float, default=8.0)
    parser.add_argument("--lidar-yaw-offset", type=float, default=0.0)
    parser.add_argument("--goal-normalization-distance", type=float, default=10.0)
    parser.add_argument("--max-vx", type=float, default=0.60)
    parser.add_argument("--max-vy", type=float, default=0.50)
    parser.add_argument("--max-wz", type=float, default=1.20)
    parser.add_argument("--max-ax", type=float, default=0.80)
    parser.add_argument("--max-ay", type=float, default=0.65)
    parser.add_argument("--max-awz", type=float, default=2.00)
    parser.add_argument("--max-jerk-x", type=float, default=4.0)
    parser.add_argument("--max-jerk-y", type=float, default=3.0)
    parser.add_argument("--max-jerk-wz", type=float, default=8.0)

    parser.add_argument(
        "--sampling-mode",
        choices=("fixed_waypoint", "continuous_free_space"),
        default="fixed_waypoint",
    )
    parser.add_argument("--map-yaml")
    parser.add_argument("--validation-map-yaml")
    parser.add_argument("--holdout-map-yaml")
    parser.add_argument("--minimum-clearance", type=float, default=0.35)
    parser.add_argument("--min-start-goal-distance", type=float, default=1.5)
    parser.add_argument("--max-start-goal-distance", type=float, default=14.0)
    parser.add_argument("--goal-radius", type=float, default=0.35)
    parser.add_argument("--max-episode-steps", type=int, default=500)
    parser.add_argument("--reset-retries", type=int, default=5)

    parser.add_argument(
        "--domain-profile", choices=("nominal", "easy", "hard"), default="hard"
    )
    parser.add_argument(
        "--curriculum", action=argparse.BooleanOptionalAction, default=True
    )

    parser.add_argument(
        "--enable-validation", action=argparse.BooleanOptionalAction, default=False
    )
    parser.add_argument("--validation-freq", type=int, default=100_000)
    parser.add_argument("--validation-episodes", type=int, default=75)
    parser.add_argument("--eval-episodes", type=int, default=500)
    parser.add_argument("--validation-world-name")
    parser.add_argument("--validation-robot-entity")
    parser.add_argument("--validation-cmd-vel-topic")
    parser.add_argument("--validation-scan-topic")
    parser.add_argument("--validation-odom-topic")
    parser.add_argument("--validation-collision-topic")
    parser.add_argument("--validation-set-pose-service")
    parser.add_argument("--validation-control-world-service")

    parser.add_argument(
        "--check-env", action=argparse.BooleanOptionalAction, default=True
    )
    parser.add_argument("--smoke-resets", type=int, default=5)
    parser.add_argument("--smoke-steps", type=int, default=200)
    arguments = parser.parse_args(argv)
    validate_args(arguments)
    return arguments


def validate_args(args: argparse.Namespace) -> None:
    positive = {
        "timesteps": args.timesteps,
        "n_steps": args.n_steps,
        "batch_size": args.batch_size,
        "n_epochs": args.n_epochs,
        "checkpoint_freq": args.checkpoint_freq,
        "control_dt": args.control_dt,
        "physics_step_size": args.physics_step_size,
        "validation_episodes": args.validation_episodes,
        "eval_episodes": args.eval_episodes,
    }
    invalid = [name for name, value in positive.items() if value <= 0]
    if invalid:
        raise ValueError("The following arguments must be positive: " + ", ".join(invalid))
    if args.n_steps % args.batch_size:
        raise ValueError(
            "For one training environment, --n-steps must be divisible by --batch-size"
        )
    if len(set(args.seeds)) != len(args.seeds):
        raise ValueError("--seeds contains duplicates")
    if args.sampling_mode == "continuous_free_space" and not args.map_yaml:
        raise ValueError("continuous_free_space requires --map-yaml")
    if args.mode in {"evaluate", "robustness"} and not args.model_path:
        raise ValueError(f"--mode {args.mode} requires --model-path")
    if args.enable_validation:
        required = {
            "validation_world_name": args.validation_world_name,
            "validation_robot_entity": args.validation_robot_entity,
            "validation_cmd_vel_topic": args.validation_cmd_vel_topic,
            "validation_scan_topic": args.validation_scan_topic,
            "validation_odom_topic": args.validation_odom_topic,
            "validation_collision_topic": args.validation_collision_topic,
            "validation_set_pose_service": args.validation_set_pose_service,
            "validation_control_world_service": args.validation_control_world_service,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ValueError(
                "Independent periodic validation is missing: " + ", ".join(missing)
            )
        if args.stepping_mode != "control_world":
            raise ValueError(
                "Periodic validation requires --stepping-mode control_world so the "
                "training world remains paused during validation"
            )
        validate_independent_interfaces(args)


def validate_independent_interfaces(args: argparse.Namespace) -> None:
    comparisons = {
        "cmd_vel": (args.cmd_vel_topic, args.validation_cmd_vel_topic),
        "scan": (args.scan_topic, args.validation_scan_topic),
        "odom": (args.odom_topic, args.validation_odom_topic),
        "contacts": (args.collision_topic, args.validation_collision_topic),
        "set_pose": (args.set_pose_service or f"/world/{args.world_name}/set_pose", args.validation_set_pose_service),
        "control_world": (
            args.control_world_service or f"/world/{args.world_name}/control",
            args.validation_control_world_service,
        ),
    }
    shared = [name for name, values in comparisons.items() if values[0] == values[1]]
    if shared:
        raise ValueError(
            "Training and validation share safety-critical interfaces: "
            + ", ".join(shared)
        )
    if (
        args.world_name == args.validation_world_name
        and args.robot_entity == args.validation_robot_entity
    ):
        raise ValueError("Training and validation identify the same Gazebo entity")


def make_domain_profile(name: str) -> DomainRandomizationConfig:
    if name == "nominal":
        return DomainRandomizationConfig(enabled=False, profile="nominal")
    return DomainRandomizationConfig(enabled=True, profile=name)


def robustness_profile(name: str) -> DomainRandomizationConfig:
    nominal = DomainRandomizationConfig(enabled=False, profile=name)
    if name == "nominal":
        return nominal
    base = DomainRandomizationConfig(enabled=True, profile="hard")
    zero_float = (0.0, 0.0)
    zero_int = (0, 0)
    disabled = replace(
        base,
        lidar_noise_std=zero_float,
        lidar_bias=zero_float,
        lidar_ray_dropout=zero_float,
        lidar_sector_dropout=zero_float,
        lidar_outlier_probability=zero_float,
        lidar_max_return_probability=zero_float,
        scan_hold_probability=zero_float,
        observation_delay_steps=zero_int,
        odom_xy_noise_std=zero_float,
        odom_yaw_noise_std=zero_float,
        odom_velocity_noise_std=zero_float,
        odom_scale_error=(1.0, 1.0),
        odom_drift_per_second=zero_float,
        timestamp_jitter=zero_float,
        command_delay_steps=zero_int,
        command_hold_probability=zero_float,
        actuator_time_constant=zero_float,
        actuator_deadzone=zero_float,
        motor_gain=(1.0, 1.0),
        left_right_mismatch=zero_float,
        front_rear_mismatch=zero_float,
        lateral_slip=(1.0, 1.0),
        yaw_coupling=zero_float,
    )
    if name == "lidar_noise":
        return replace(
            disabled,
            profile=name,
            lidar_noise_std=(0.02, 0.04),
            lidar_bias=(-0.03, 0.03),
            lidar_ray_dropout=(0.01, 0.04),
            lidar_sector_dropout=(0.0, 0.03),
        )
    if name == "odom_noise":
        return replace(
            disabled,
            profile=name,
            odom_xy_noise_std=(0.01, 0.03),
            odom_yaw_noise_std=(0.01, 0.03),
            odom_velocity_noise_std=(0.02, 0.05),
            odom_scale_error=(0.97, 1.03),
            odom_drift_per_second=(-0.003, 0.003),
        )
    if name == "sensor_latency":
        return replace(
            disabled,
            profile=name,
            observation_delay_steps=(1, 3),
            scan_hold_probability=(0.02, 0.08),
            timestamp_jitter=(0.01, 0.03),
        )
    if name == "command_latency":
        return replace(
            disabled,
            profile=name,
            command_delay_steps=(1, 3),
            command_hold_probability=(0.02, 0.08),
            actuator_time_constant=(0.12, 0.25),
        )
    if name == "slip_proxy":
        return replace(
            disabled,
            profile=name,
            lateral_slip=(0.60, 0.85),
            yaw_coupling=(-0.12, 0.12),
        )
    if name == "motor_asymmetry":
        return replace(
            disabled,
            profile=name,
            motor_gain=(0.82, 1.12),
            left_right_mismatch=(-0.10, 0.10),
            front_rear_mismatch=(-0.08, 0.08),
            actuator_deadzone=(0.03, 0.08),
        )
    if name == "mixed":
        return replace(base, profile=name)
    raise ValueError(f"Unknown robustness profile {name!r}")


def build_config(
    args: argparse.Namespace,
    *,
    split: str,
    validation: bool = False,
    domain_profile: Optional[DomainRandomizationConfig] = None,
) -> EnvConfig:
    if validation:
        world = args.validation_world_name
        entity = args.validation_robot_entity
        cmd_vel = args.validation_cmd_vel_topic
        scan = args.validation_scan_topic
        odom = args.validation_odom_topic
        contacts = args.validation_collision_topic
        set_pose = args.validation_set_pose_service
        control_world = args.validation_control_world_service
    else:
        world = args.world_name
        entity = args.robot_entity
        cmd_vel = args.cmd_vel_topic
        scan = args.scan_topic
        odom = args.odom_topic
        contacts = args.collision_topic
        set_pose = args.set_pose_service or f"/world/{world}/set_pose"
        control_world = args.control_world_service or f"/world/{world}/control"

    map_yaml = args.map_yaml
    if split == "validation":
        map_yaml = args.validation_map_yaml or args.map_yaml
    elif split == "holdout":
        map_yaml = args.holdout_map_yaml or args.map_yaml

    ros = RosInterfaceConfig(
        world_name=str(world),
        robot_entity_name=str(entity),
        cmd_vel_topic=str(cmd_vel),
        scan_topic=str(scan),
        odom_topic=str(odom),
        collision_topic=str(contacts),
        set_pose_service=str(set_pose),
        control_world_service=str(control_world),
        startup_timeout=args.startup_timeout,
        require_ground_truth_collision=args.require_ground_truth_collision,
    )
    sensor = SensorConfig(
        lidar_sectors=args.lidar_sectors,
        lidar_min_valid=args.lidar_min,
        lidar_max=args.lidar_max,
        lidar_yaw_offset=args.lidar_yaw_offset,
        goal_normalization_distance=args.goal_normalization_distance,
        sensor_timeout=args.sensor_timeout,
        wall_timeout=args.wall_timeout,
        max_sensor_skew=args.max_sensor_skew,
        max_sensor_age=args.max_sensor_age,
    )
    action = ActionConfig(
        max_vx=args.max_vx,
        max_vy=args.max_vy,
        max_wz=args.max_wz,
        max_ax=args.max_ax,
        max_ay=args.max_ay,
        max_awz=args.max_awz,
        max_jerk_x=args.max_jerk_x,
        max_jerk_y=args.max_jerk_y,
        max_jerk_wz=args.max_jerk_wz,
    )
    scenario = ScenarioConfig(
        split=split,
        sampling_mode=args.sampling_mode,
        map_yaml_path=map_yaml,
        minimum_clearance=args.minimum_clearance,
        min_start_goal_distance=args.min_start_goal_distance,
        max_start_goal_distance=args.max_start_goal_distance,
        goal_radius=args.goal_radius,
        max_episode_steps=args.max_episode_steps,
        reset_retries=args.reset_retries,
    )
    return EnvConfig(
        ros=ros,
        sensor=sensor,
        action=action,
        safety=SafetyConfig(),
        reward=RewardConfig(),
        domain_randomization=domain_profile or make_domain_profile(args.domain_profile),
        scenario=scenario,
        control_dt=args.control_dt,
        stepping_mode=args.stepping_mode,
        physics_step_size=args.physics_step_size,
    )


def make_environment(config: EnvConfig, monitor_path: Optional[Path] = None):
    base = MecanumEnv(config)
    if monitor_path is None:
        return base
    monitor_path.parent.mkdir(parents=True, exist_ok=True)
    return Monitor(base, str(monitor_path), info_keywords=MONITOR_INFO_KEYS)


def unwrap_environment(environment: Any) -> MecanumEnv:
    current = environment
    for _ in range(20):
        if isinstance(current, MecanumEnv):
            return current
        if hasattr(current, "env"):
            current = current.env
            continue
        if hasattr(current, "venv"):
            current = current.venv
            continue
        break
    raise TypeError("Could not find MecanumEnv under wrappers")


def safe_close(environment: Any) -> None:
    if environment is None:
        return
    try:
        unwrap_environment(environment).stop_robot()
    except Exception:
        pass
    try:
        environment.close()
    except Exception:
        pass


def git_snapshot() -> Dict[str, Any]:
    result: Dict[str, Any] = {"commit": None, "dirty": None}
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=3.0,
        )
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            check=True,
            capture_output=True,
            text=True,
            timeout=3.0,
        )
        result = {
            "commit": commit.stdout.strip(),
            "dirty": bool(status.stdout.strip()),
        }
    except Exception:
        pass
    return result


def run_paths(root: Path, seed: int) -> Dict[str, Path]:
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    run = root.expanduser().resolve() / f"seed_{seed}_{timestamp}"
    paths = {
        "root": run,
        "tensorboard": run / "tensorboard",
        "checkpoints": run / "checkpoints",
        "best": run / "best",
        "monitor": run / "monitor",
        "evaluation": run / "evaluation",
    }
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)
    return paths


def ppo_parameters(args: argparse.Namespace) -> Dict[str, Any]:
    return {
        "learning_rate": args.learning_rate,
        "n_steps": args.n_steps,
        "batch_size": args.batch_size,
        "n_epochs": args.n_epochs,
        "gamma": args.gamma,
        "gae_lambda": args.gae_lambda,
        "clip_range": args.clip_range,
        "ent_coef": args.ent_coef,
        "vf_coef": args.vf_coef,
        "max_grad_norm": args.max_grad_norm,
        "policy_kwargs": {"net_arch": {"pi": [256, 256], "vf": [256, 256]}},
    }


def experiment_snapshot(
    args: argparse.Namespace,
    seed: int,
    environment: MecanumEnv,
) -> Dict[str, Any]:
    return {
        "seed": seed,
        "reproducibility_note": (
            "All software RNGs are seeded; ROS 2/Gazebo scheduling is not claimed "
            "to be bitwise deterministic."
        ),
        "arguments": vars(args),
        "environment": environment.model_metadata(seed),
        "ppo": ppo_parameters(args),
        "versions": {
            "python": sys.version,
            "platform": platform.platform(),
            "numpy": np.__version__,
            "torch": torch.__version__,
            "gymnasium": gymnasium.__version__,
            "stable_baselines3": stable_baselines3.__version__,
        },
        "git": git_snapshot(),
    }


def metadata_path(model_path: Path) -> Path:
    base = model_path.with_suffix("") if model_path.suffix == ".zip" else model_path
    return base.with_suffix(".metadata.json")


def save_model_bundle(
    model: PPO,
    model_path: Path,
    environment: MecanumEnv,
    seed: int,
    extra: Optional[Mapping[str, Any]] = None,
) -> None:
    model_path.parent.mkdir(parents=True, exist_ok=True)
    model.save(str(model_path))
    payload = environment.model_metadata(seed)
    payload["code"] = git_snapshot()
    if extra:
        payload.update(dict(extra))
    metadata_path(model_path).write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
    )


class TaskMetricsCallback(BaseCallback):
    """Log task outcomes and decomposed rewards instead of reward alone."""

    def __init__(self, window: int = 100):
        super().__init__(verbose=0)
        self.window = window
        self.outcomes: Dict[str, Deque[float]] = {
            name: deque(maxlen=window)
            for name in ("success", "collision", "deadlock", "timeout", "sensor_timeout")
        }

    def _on_step(self) -> bool:
        infos = self.locals.get("infos", [])
        dones = self.locals.get("dones", [])
        for index, info in enumerate(infos):
            for key in (
                "distance_to_goal",
                "path_length",
                "navigation_time",
                "episode_min_clearance",
                "sensor_skew",
                "r_progress",
                "r_time",
                "r_safety",
                "r_smooth",
                "r_stuck",
                "r_terminal",
            ):
                value = info.get(key)
                if value is not None and np.isfinite(value):
                    self.logger.record(f"task/{key}", float(value))
            if index >= len(dones) or not dones[index]:
                continue
            values = {
                "success": float(bool(info["is_success"])),
                "collision": float(bool(info["collision"])),
                "deadlock": float(bool(info["deadlock"])),
                "timeout": float(bool(info["timeout"])),
                "sensor_timeout": float(bool(info["sensor_timeout"])),
            }
            for name, value in values.items():
                self.outcomes[name].append(value)
                self.logger.record(f"episode/{name}", value)
                self.logger.record(
                    f"rollout_task/{name}_rate", float(np.mean(self.outcomes[name]))
                )
        return True


class CurriculumCallback(BaseCallback):
    """Increase randomization strength as total training progress advances."""

    def __init__(self, environment: MecanumEnv, total_timesteps: int):
        super().__init__(verbose=0)
        self.environment = environment
        self.total_timesteps = max(1, total_timesteps)

    def _on_step(self) -> bool:
        progress = min(1.0, self.num_timesteps / self.total_timesteps)
        self.environment.set_training_progress(progress)
        self.logger.record("curriculum/progress", progress)
        return True


class MetadataCheckpointCallback(BaseCallback):
    """Save model and schema metadata together at a fixed frequency."""

    def __init__(
        self,
        directory: Path,
        frequency: int,
        environment: MecanumEnv,
        seed: int,
    ):
        super().__init__(verbose=0)
        self.directory = directory
        self.frequency = frequency
        self.environment = environment
        self.seed = seed

    def _on_step(self) -> bool:
        if self.num_timesteps % self.frequency == 0:
            path = self.directory / f"ppo_mecanum_{self.num_timesteps}_steps"
            save_model_bundle(
                self.model,
                path,
                self.environment,
                self.seed,
                {"num_timesteps": self.num_timesteps, "kind": "checkpoint"},
            )
        return True


class CollapseWarningCallback(BaseCallback):
    """Emit warnings for persistent pathological PPO diagnostics."""

    def __init__(self):
        super().__init__(verbose=0)
        self.bad_rollouts = 0

    def _on_step(self) -> bool:
        return True

    def _on_rollout_end(self) -> None:
        values = getattr(self.model.logger, "name_to_value", {})
        explained = values.get("train/explained_variance")
        approximate_kl = values.get("train/approx_kl")
        bad = (
            explained is not None
            and float(explained) < -0.5
        ) or (
            approximate_kl is not None
            and float(approximate_kl) > 0.20
        )
        self.bad_rollouts = self.bad_rollouts + 1 if bad else 0
        if self.bad_rollouts >= 3:
            print(
                "[WARNING] PPO diagnostics are pathological for three rollouts; "
                "inspect explained variance, KL, entropy, clip fraction and rewards.",
                file=sys.stderr,
            )


def wilson_interval(successes: int, total: int, z: float = 1.959964) -> Tuple[float, float]:
    if total <= 0:
        return math.nan, math.nan
    probability = successes / total
    denominator = 1.0 + z * z / total
    center = (probability + z * z / (2.0 * total)) / denominator
    margin = z * math.sqrt(
        probability * (1.0 - probability) / total + z * z / (4.0 * total * total)
    ) / denominator
    return max(0.0, center - margin), min(1.0, center + margin)


def evaluate_model(
    model: PPO,
    environment: Any,
    episodes: int,
    seed: int,
) -> Dict[str, Any]:
    records: List[Dict[str, float]] = []
    for episode in range(episodes):
        observation, _ = environment.reset(seed=seed + episode)
        terminated = truncated = False
        reward_sum = 0.0
        final_info: Dict[str, Any] = {}
        while not (terminated or truncated):
            action, _ = model.predict(observation, deterministic=True)
            observation, reward, terminated, truncated, final_info = environment.step(action)
            reward_sum += float(reward)
        records.append(
            {
                "reward": reward_sum,
                "success": float(bool(final_info["is_success"])),
                "collision": float(bool(final_info["collision"])),
                "deadlock": float(bool(final_info["deadlock"])),
                "timeout": float(bool(final_info["timeout"])),
                "sensor_timeout": float(bool(final_info["sensor_timeout"])),
                "path_length": float(final_info["path_length"]),
                "navigation_time": float(final_info["navigation_time"]),
                "final_distance": float(final_info["distance_to_goal"]),
                "min_clearance": float(final_info["episode_min_clearance"]),
                "spl": float(final_info["spl"]),
            }
        )
    result: Dict[str, Any] = {"episodes": episodes}
    for outcome in ("success", "collision", "deadlock", "timeout", "sensor_timeout"):
        values = np.asarray([record[outcome] for record in records], dtype=np.float64)
        result[f"{outcome}_rate"] = float(np.mean(values))
        lower, upper = wilson_interval(int(np.sum(values)), len(values))
        result[f"{outcome}_rate_ci95"] = [lower, upper]
    for metric in (
        "reward",
        "path_length",
        "navigation_time",
        "final_distance",
        "min_clearance",
        "spl",
    ):
        values = np.asarray([record[metric] for record in records], dtype=np.float64)
        result[f"mean_{metric}"] = float(np.mean(values))
        result[f"median_{metric}"] = float(np.median(values))
        result[f"std_{metric}"] = float(np.std(values, ddof=1)) if len(values) > 1 else 0.0
    result["episode_records"] = records
    return result


class IndependentValidationCallback(BaseCallback):
    """Select checkpoints by success, collision, deadlock, SPL, then reward."""

    def __init__(
        self,
        environment: Any,
        training_environment: MecanumEnv,
        frequency: int,
        episodes: int,
        seed: int,
        output_directory: Path,
    ):
        super().__init__(verbose=1)
        self.environment = environment
        self.training_environment = training_environment
        self.frequency = frequency
        self.episodes = episodes
        self.seed = seed
        self.output_directory = output_directory
        self.best_score = (-1.0, -1.0, -1.0, -1.0, -math.inf)

    def _on_step(self) -> bool:
        if self.num_timesteps % self.frequency:
            return True
        self.training_environment.pause_world()
        metrics = evaluate_model(
            self.model, self.environment, self.episodes, self.seed + self.num_timesteps
        )
        score = (
            metrics["success_rate"],
            -metrics["collision_rate"],
            -metrics["deadlock_rate"],
            metrics["median_spl"],
            metrics["mean_reward"],
        )
        summary = {"num_timesteps": self.num_timesteps, **metrics}
        with (self.output_directory / "validation.jsonl").open(
            "a", encoding="utf-8"
        ) as stream:
            compact = dict(summary)
            compact.pop("episode_records", None)
            stream.write(json.dumps(compact) + "\n")
        for key, value in metrics.items():
            if isinstance(value, (int, float)):
                self.logger.record(f"validation/{key}", value)
        if score > self.best_score:
            self.best_score = score
            save_model_bundle(
                self.model,
                self.output_directory / "best_model",
                self.training_environment,
                self.seed,
                {
                    "selection_rule": (
                        "success desc, collision asc, deadlock asc, median SPL desc, "
                        "mean reward desc"
                    ),
                    "validation_metrics": {k: v for k, v in metrics.items() if k != "episode_records"},
                    "num_timesteps": self.num_timesteps,
                },
            )
        print(
            f"[validation] step={self.num_timesteps} "
            f"success={metrics['success_rate']:.3f} "
            f"collision={metrics['collision_rate']:.3f} "
            f"deadlock={metrics['deadlock_rate']:.3f} "
            f"SPL={metrics['mean_spl']:.3f}"
        )
        return True


def run_training_seed(args: argparse.Namespace, seed: int) -> Dict[str, Any]:
    set_global_seed(seed)
    paths = run_paths(Path(args.output_dir), seed)
    training_environment = validation_environment = None
    training_base: Optional[MecanumEnv] = None
    model: Optional[PPO] = None
    result: Dict[str, Any] = {"seed": seed, "run_directory": str(paths["root"])}
    try:
        training_config = build_config(args, split="train")
        training_base = MecanumEnv(training_config)
        if args.curriculum:
            training_base.set_training_progress(0.0)
        training_environment = Monitor(
            training_base,
            str(paths["monitor"] / "train.csv"),
            info_keywords=MONITOR_INFO_KEYS,
        )
        snapshot = experiment_snapshot(args, seed, training_base)
        (paths["root"] / "config_snapshot.json").write_text(
            json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8"
        )
        if args.check_env:
            check_env(training_base, warn=True, skip_render_check=True)
        observation, info = training_environment.reset(seed=seed)
        if not training_environment.observation_space.contains(observation):
            raise RuntimeError("reset observation violates observation_space")
        print(
            f"[seed {seed}] sensors ready; distance={info['distance_to_goal']:.3f} m"
        )
        print(
            f"[seed {seed}] world={training_config.ros.world_name} "
            f"entity={training_config.ros.robot_entity_name} "
            f"cmd={training_config.ros.cmd_vel_topic} "
            f"scan={training_config.ros.scan_topic} "
            f"odom={training_config.ros.odom_topic} "
            f"contacts={training_config.ros.collision_topic} "
            f"ROS_DOMAIN_ID={os.environ.get('ROS_DOMAIN_ID', '0')}"
        )

        callbacks: List[BaseCallback] = [
            TaskMetricsCallback(),
            MetadataCheckpointCallback(
                paths["checkpoints"], args.checkpoint_freq, training_base, seed
            ),
            CollapseWarningCallback(),
        ]
        if args.curriculum:
            callbacks.append(CurriculumCallback(training_base, args.timesteps))
        if args.enable_validation:
            validation_config = build_config(
                args,
                split="validation",
                validation=True,
                domain_profile=make_domain_profile("nominal"),
            )
            validation_environment = make_environment(
                validation_config, paths["monitor"] / "validation.csv"
            )
            validation_environment.reset(seed=seed + 100_000)
            callbacks.append(
                IndependentValidationCallback(
                    validation_environment,
                    training_base,
                    args.validation_freq,
                    args.validation_episodes,
                    seed + 100_000,
                    paths["best"],
                )
            )

        parameters = ppo_parameters(args)
        model = PPO(
            "MlpPolicy",
            training_environment,
            tensorboard_log=str(paths["tensorboard"]),
            verbose=1,
            device=args.device,
            seed=seed,
            **parameters,
        )
        model.learn(
            total_timesteps=args.timesteps,
            callback=CallbackList(callbacks),
            progress_bar=args.progress_bar,
            reset_num_timesteps=True,
            tb_log_name=f"ppo_seed_{seed}",
        )
        final_path = paths["root"] / "final_model"
        save_model_bundle(
            model,
            final_path,
            training_base,
            seed,
            {"kind": "final", "timesteps": args.timesteps},
        )
        result["final_model"] = str(final_path.with_suffix(".zip"))
        if validation_environment is not None:
            training_base.pause_world()
            metrics = evaluate_model(
                model,
                validation_environment,
                args.validation_episodes,
                seed + 200_000,
            )
            (paths["evaluation"] / "final_validation.json").write_text(
                json.dumps(metrics, indent=2), encoding="utf-8"
            )
            result["validation_metrics"] = {
                key: value for key, value in metrics.items() if key != "episode_records"
            }
        return result
    except KeyboardInterrupt:
        if model is not None and training_base is not None:
            save_model_bundle(
                model,
                paths["root"] / "interrupted_model",
                training_base,
                seed,
                {"kind": "interrupted"},
            )
        raise
    finally:
        safe_close(validation_environment)
        safe_close(training_environment)


def aggregate_seed_results(results: Sequence[Mapping[str, Any]], output: Path) -> Dict[str, Any]:
    summaries = [result.get("validation_metrics") for result in results]
    summaries = [summary for summary in summaries if isinstance(summary, Mapping)]
    aggregate: Dict[str, Any] = {
        "seed_count": len(results),
        "seeds": [int(result["seed"]) for result in results],
        "evaluated_seed_count": len(summaries),
    }
    if summaries:
        common = sorted(
            set.intersection(
                *(set(key for key, value in summary.items() if isinstance(value, (int, float))) for summary in summaries)
            )
        )
        metrics: Dict[str, Any] = {}
        for key in common:
            values = np.asarray([float(summary[key]) for summary in summaries])
            metrics[key] = {
                "mean": float(np.mean(values)),
                "std": float(np.std(values, ddof=1)) if len(values) > 1 else 0.0,
                "median": float(np.median(values)),
                "min": float(np.min(values)),
                "max": float(np.max(values)),
                "mean_ci95": [
                    float(np.mean(values) - 1.96 * np.std(values, ddof=1) / math.sqrt(len(values)))
                    if len(values) > 1 else float(values[0]),
                    float(np.mean(values) + 1.96 * np.std(values, ddof=1) / math.sqrt(len(values)))
                    if len(values) > 1 else float(values[0]),
                ],
            }
        aggregate["metrics"] = metrics
    output.mkdir(parents=True, exist_ok=True)
    (output / "multi_seed_summary.json").write_text(
        json.dumps(aggregate, indent=2), encoding="utf-8"
    )
    with (output / "multi_seed_runs.csv").open("w", newline="", encoding="utf-8") as stream:
        rows = []
        for result in results:
            row = {"seed": result["seed"], "run_directory": result["run_directory"]}
            row.update(result.get("validation_metrics", {}))
            rows.append(row)
        fieldnames = sorted(set().union(*(row.keys() for row in rows)))
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return aggregate


def load_model_with_schema(model_path: Path, environment: MecanumEnv, device: str) -> PPO:
    sidecar = metadata_path(model_path)
    if not sidecar.exists():
        raise FileNotFoundError(
            f"Model metadata is required for evaluation/deployment: {sidecar}"
        )
    metadata = json.loads(sidecar.read_text(encoding="utf-8"))
    expected = environment.preprocessor.schema()
    actual = metadata.get("observation_schema")
    if actual != expected:
        raise RuntimeError(
            "Model observation schema does not match this environment; refusing load"
        )
    return PPO.load(str(model_path), device=device)


def run_evaluation(args: argparse.Namespace) -> Dict[str, Any]:
    set_global_seed(args.seeds[0])
    config = build_config(
        args,
        split="holdout",
        domain_profile=make_domain_profile("nominal"),
    )
    environment = None
    try:
        environment = MecanumEnv(config)
        model = load_model_with_schema(Path(args.model_path), environment, args.device)
        metrics = evaluate_model(model, environment, args.eval_episodes, args.seeds[0])
        output = Path(args.output_dir).expanduser().resolve()
        output.mkdir(parents=True, exist_ok=True)
        (output / "holdout_evaluation.json").write_text(
            json.dumps(metrics, indent=2), encoding="utf-8"
        )
        return metrics
    finally:
        safe_close(environment)


def run_robustness_matrix(args: argparse.Namespace) -> Dict[str, Any]:
    profiles = (
        "nominal",
        "lidar_noise",
        "odom_noise",
        "sensor_latency",
        "command_latency",
        "slip_proxy",
        "motor_asymmetry",
        "mixed",
    )
    output = Path(args.output_dir).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    matrix: Dict[str, Any] = {
        "physics_warning": (
            "slip_proxy and motor_asymmetry are command-layer tests. True friction, "
            "mass, inertia, wheel-radius and obstacle-layout shifts need external "
            "SDF/launch variants and are NEEDS EXTERNAL VALIDATION."
        ),
        "profiles": {},
    }
    csv_rows: List[Dict[str, Any]] = []
    for index, name in enumerate(profiles):
        environment = None
        try:
            config = build_config(
                args,
                split="holdout",
                domain_profile=robustness_profile(name),
            )
            environment = MecanumEnv(config)
            model = load_model_with_schema(Path(args.model_path), environment, args.device)
            metrics = evaluate_model(
                model,
                environment,
                args.eval_episodes,
                args.seeds[0] + index * 100_000,
            )
            matrix["profiles"][name] = metrics
            row = {"profile": name}
            row.update({key: value for key, value in metrics.items() if isinstance(value, (int, float))})
            csv_rows.append(row)
        finally:
            safe_close(environment)
    (output / "robustness_matrix.json").write_text(
        json.dumps(matrix, indent=2), encoding="utf-8"
    )
    with (output / "robustness_matrix.csv").open("w", newline="", encoding="utf-8") as stream:
        fieldnames = sorted(set().union(*(row.keys() for row in csv_rows)))
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(csv_rows)
    return matrix


def run_smoke(args: argparse.Namespace) -> None:
    config = build_config(
        args,
        split="train",
        domain_profile=make_domain_profile("nominal"),
    )
    environment = None
    try:
        environment = MecanumEnv(config)
        if args.check_env:
            check_env(environment, warn=True, skip_render_check=True)
        for reset_index in range(args.smoke_resets):
            observation, info = environment.reset(seed=args.seeds[0] + reset_index)
            assert environment.observation_space.contains(observation)
            assert set(REQUIRED_INFO_KEYS).issubset(info)
        observation, _ = environment.reset(seed=args.seeds[0] + 10_000)
        for _ in range(args.smoke_steps):
            action = environment.action_space.sample()
            assert environment.action_space.contains(action)
            observation, _, terminated, truncated, info = environment.step(action)
            assert environment.observation_space.contains(observation)
            assert np.isfinite(observation).all()
            assert set(REQUIRED_INFO_KEYS).issubset(info)
            if terminated or truncated:
                observation, _ = environment.reset()
        print(
            f"smoke PASS: {args.smoke_resets} resets, {args.smoke_steps} random steps"
        )
    finally:
        safe_close(environment)


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = parse_args(argv)
    try:
        if args.mode == "train":
            results = []
            for seed in args.seeds:
                print(f"\n=== independent training seed {seed} ===")
                results.append(run_training_seed(args, seed))
            aggregate = aggregate_seed_results(results, Path(args.output_dir))
            print(json.dumps(aggregate, indent=2))
        elif args.mode == "evaluate":
            print(json.dumps(run_evaluation(args), indent=2))
        elif args.mode == "robustness":
            print(json.dumps(run_robustness_matrix(args), indent=2))
        else:
            run_smoke(args)
    finally:
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
