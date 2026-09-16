#!/usr/bin/env python3
"""Gymnasium environment and shared contracts for Mecanum DRL navigation.

This module intentionally separates policy observations from Gazebo ground
truth.  LiDAR, a robot-frame local goal, and measured body velocity are the
only policy inputs.  Gazebo ground-truth odometry is used for task pose,
physical body velocity, reward and reset validation; contacts are the only
collision ground truth.

The same :class:`ObservationPreprocessor` and :class:`SafetySupervisor` are
imported by ``mecanum_policy_node.py``.  Keep OBSERVATION_SCHEMA_VERSION stable
for compatible changes and increment it for any feature/order/normalization
change.
"""

from __future__ import annotations

import argparse
import copy
import math
import os
import threading
import time
import uuid
from collections import deque
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Deque, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import gymnasium as gym
from gymnasium import spaces
import numpy as np

import rclpy
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from rclpy.executors import SingleThreadedExecutor
from rclpy.node import Node
from rclpy.parameter import Parameter
from rclpy.qos import HistoryPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import LaserScan

from ros_gz_interfaces.msg import Contacts, Entity
from ros_gz_interfaces.srv import ControlWorld, SetEntityPose


OBSERVATION_SCHEMA_VERSION = "mecanum-local-nav-v2"
REQUIRED_INFO_KEYS = (
    "is_success",
    "collision",
    "deadlock",
    "timeout",
    "sensor_timeout",
    "distance_to_goal",
    "navigation_time",
    "path_length",
    "episode_min_clearance",
    "sensor_skew",
    "episode_step",
)


def wrap_angle(angle: float) -> float:
    """Wrap an angle to [-pi, pi]."""
    return math.atan2(math.sin(angle), math.cos(angle))


def quaternion_to_yaw(quaternion: Any) -> float:
    """Extract planar yaw from a geometry_msgs quaternion."""
    siny_cosp = 2.0 * (
        float(quaternion.w) * float(quaternion.z)
        + float(quaternion.x) * float(quaternion.y)
    )
    cosy_cosp = 1.0 - 2.0 * (
        float(quaternion.y) ** 2 + float(quaternion.z) ** 2
    )
    return math.atan2(siny_cosp, cosy_cosp)


def stamp_to_seconds(stamp: Any) -> float:
    """Convert a ROS builtin time message to seconds."""
    return float(stamp.sec) + 1e-9 * float(stamp.nanosec)


def finite(value: Any, name: str) -> float:
    """Return a finite float or fail instead of silently corrupting state."""
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} is NaN/Inf")
    return result


def dataclass_dict(value: Any) -> Dict[str, Any]:
    """Return a JSON-friendly recursive dataclass dictionary."""
    return asdict(value)


@dataclass(frozen=True)
class RosInterfaceConfig:
    """ROS and Gazebo interface names used by one environment instance."""

    world_name: str = "world_demo"
    robot_entity_name: str = "ROBOT_URDF_final"
    cmd_vel_topic: str = "/cmd_vel"
    scan_topic: str = "/scan"
    odom_topic: str = "/odom"
    ground_truth_odom_topic: str = "/ground_truth/odom"
    collision_topic: str = "/collision"
    set_pose_service: str = "/world/world_demo/set_pose"
    control_world_service: str = "/world/world_demo/control"
    use_sim_time: bool = True
    startup_timeout: float = 10.0
    require_ground_truth_collision: bool = True
    require_cmd_subscriber: bool = True
    contact_exclude_patterns: Tuple[str, ...] = (
        "ground_plane",
        "Wheel_LF_1",
        "Wheel_RF_1",
        "Wheel_LB_1",
        "Wheel_RB_1",
    )


@dataclass(frozen=True)
class SensorConfig:
    """Sensor preprocessing and transition synchronization contract."""

    lidar_sectors: int = 72
    lidar_min_valid: float = 0.12
    lidar_max: float = 8.0
    lidar_yaw_offset: float = 0.0
    goal_normalization_distance: float = 10.0
    max_invalid_lidar_fraction: float = 0.25
    invalid_below_min_is_obstacle: bool = True
    sensor_timeout: float = 2.0
    wall_timeout: float = 5.0
    max_sensor_skew: float = 0.08
    max_sensor_age: float = 0.25
    min_transition_fraction: float = 0.80
    require_fresh_contact_each_step: bool = True


@dataclass(frozen=True)
class ActionConfig:
    """Normalized-policy to physical-command limits."""

    max_vx: float = 0.60
    max_vy: float = 0.50
    max_wz: float = 1.20
    max_ax: float = 0.80
    max_ay: float = 0.65
    max_awz: float = 2.00
    max_jerk_x: Optional[float] = 4.0
    max_jerk_y: Optional[float] = 3.0
    max_jerk_wz: Optional[float] = 8.0


@dataclass(frozen=True)
class SafetyConfig:
    """Independent command safety limits shared with deployment."""

    enabled: bool = True
    footprint_radius: float = 0.25
    obstacle_margin: float = 0.12
    emergency_margin: float = 0.04
    braking_acceleration: float = 0.80
    total_latency: float = 0.18
    motion_cone_half_angle: float = math.radians(35.0)
    command_watchdog: float = 0.30
    stop_on_invalid_observation: bool = True


@dataclass(frozen=True)
class RewardConfig:
    """Reward terms; every component is emitted in ``info``."""

    progress_gain: float = 8.0
    step_penalty: float = 0.05
    safety_gain: float = 0.60
    safety_distance: float = 0.55
    smoothness_gain: float = 0.04
    stuck_penalty: float = 3.0
    success_reward: float = 100.0
    collision_reward: float = -120.0
    timeout_reward: float = -5.0
    sensor_failure_reward: float = -20.0


@dataclass(frozen=True)
class DomainRandomizationConfig:
    """Seeded observation/communication/actuator randomization ranges.

    Friction, mass, inertia, wheel radius and obstacle geometry are not changed
    through fictitious Python APIs.  The command-layer parameters below are
    actuator proxies.  True physics randomization requires SDF/launch variants.
    """

    enabled: bool = False
    profile: str = "nominal"
    lidar_noise_std: Tuple[float, float] = (0.0, 0.025)
    lidar_bias: Tuple[float, float] = (-0.02, 0.02)
    lidar_ray_dropout: Tuple[float, float] = (0.0, 0.02)
    lidar_sector_dropout: Tuple[float, float] = (0.0, 0.02)
    lidar_outlier_probability: Tuple[float, float] = (0.0, 0.005)
    lidar_max_return_probability: Tuple[float, float] = (0.0, 0.01)
    scan_hold_probability: Tuple[float, float] = (0.0, 0.04)
    observation_delay_steps: Tuple[int, int] = (0, 2)
    odom_xy_noise_std: Tuple[float, float] = (0.0, 0.015)
    odom_yaw_noise_std: Tuple[float, float] = (0.0, 0.015)
    odom_velocity_noise_std: Tuple[float, float] = (0.0, 0.025)
    odom_scale_error: Tuple[float, float] = (0.98, 1.02)
    odom_drift_per_second: Tuple[float, float] = (-0.002, 0.002)
    timestamp_jitter: Tuple[float, float] = (0.0, 0.015)
    command_delay_steps: Tuple[int, int] = (0, 2)
    command_hold_probability: Tuple[float, float] = (0.0, 0.05)
    actuator_time_constant: Tuple[float, float] = (0.04, 0.18)
    actuator_deadzone: Tuple[float, float] = (0.0, 0.06)
    motor_gain: Tuple[float, float] = (0.90, 1.10)
    left_right_mismatch: Tuple[float, float] = (-0.06, 0.06)
    front_rear_mismatch: Tuple[float, float] = (-0.05, 0.05)
    lateral_slip: Tuple[float, float] = (0.75, 1.05)
    yaw_coupling: Tuple[float, float] = (-0.08, 0.08)


@dataclass(frozen=True)
class ScenarioConfig:
    """Start/goal sampling and episode outcome settings."""

    split: str = "train"
    sampling_mode: str = "fixed_waypoint"
    map_yaml_path: Optional[str] = None
    minimum_clearance: float = 0.35
    min_start_goal_distance: float = 1.5
    max_start_goal_distance: float = 14.0
    goal_radius: float = 0.35
    max_episode_steps: int = 500
    reset_retries: int = 5
    reset_settle_time: float = 0.35
    reset_pose_tolerance: float = 0.08
    reset_yaw_tolerance: float = 0.15
    reset_velocity_tolerance: float = 0.12
    start_z: float = 0.10
    deadlock_window_seconds: float = 5.0
    deadlock_min_progress: float = 0.08
    deadlock_min_displacement: float = 0.10
    deadlock_command_threshold: float = 0.08
    deadlock_measured_threshold: float = 0.035
    oscillation_sign_flips: int = 8
    fixed_waypoints: Tuple[Tuple[float, float], ...] = (
        (0.0, 0.0),
        (0.0, 1.2),
        (0.0, 3.8),
        (0.0, -1.0),
        (0.0, -6.0),
        (4.0, 1.2),
        (8.0, 1.2),
        (4.0, 3.8),
        (8.0, 3.8),
        (4.0, -1.0),
        (8.0, -1.0),
        (4.0, -6.0),
        (8.0, -6.0),
        (-2.0, 1.2),
        (-2.0, -1.0),
        (-2.0, -6.0),
    )


@dataclass(frozen=True)
class EnvConfig:
    """Complete source-of-truth configuration for :class:`MecanumEnv`."""

    ros: RosInterfaceConfig = field(default_factory=RosInterfaceConfig)
    sensor: SensorConfig = field(default_factory=SensorConfig)
    action: ActionConfig = field(default_factory=ActionConfig)
    safety: SafetyConfig = field(default_factory=SafetyConfig)
    reward: RewardConfig = field(default_factory=RewardConfig)
    domain_randomization: DomainRandomizationConfig = field(
        default_factory=DomainRandomizationConfig
    )
    scenario: ScenarioConfig = field(default_factory=ScenarioConfig)
    control_dt: float = 0.10
    stepping_mode: str = "sim_time"
    physics_step_size: float = 0.01


@dataclass(frozen=True)
class SensorSnapshot:
    """Immutable references and timing captured under the bridge lock."""

    scan: Optional[LaserScan]
    odom: Optional[Odometry]
    ground_truth_odom: Optional[Odometry]
    scan_stamp: Optional[float]
    odom_stamp: Optional[float]
    ground_truth_odom_stamp: Optional[float]
    contact_stamp: Optional[float]
    scan_wall_time: Optional[float]
    odom_wall_time: Optional[float]
    ground_truth_odom_wall_time: Optional[float]
    contact_wall_time: Optional[float]
    scan_seq: int
    odom_seq: int
    ground_truth_odom_seq: int
    contact_seq: int
    collision_latched: bool


@dataclass(frozen=True)
class PreprocessedObservation:
    """Policy observation plus unnormalized safety/debug values."""

    observation: np.ndarray
    sector_ranges: np.ndarray
    invalid_lidar_fraction: float
    min_clearance: float
    distance_to_goal: float
    robot_x: float
    robot_y: float
    robot_yaw: float
    measured_velocity: np.ndarray


@dataclass(frozen=True)
class SafetyResult:
    """Result of applying the independent safety supervisor."""

    command: np.ndarray
    status: str
    limited: bool
    directional_clearance: float
    stopping_distance: float


class OccupancyMapSampler:
    """Continuous, seeded sampling from a Nav2 PGM/YAML occupancy map."""

    def __init__(self, yaml_path: str, clearance: float):
        try:
            import yaml
        except ImportError as exc:
            raise RuntimeError(
                "continuous_free_space sampling requires PyYAML/python3-yaml"
            ) from exc

        self.yaml_path = Path(yaml_path).expanduser().resolve()
        metadata = yaml.safe_load(self.yaml_path.read_text(encoding="utf-8"))
        image_path = (self.yaml_path.parent / metadata["image"]).resolve()
        pixels = self._read_pgm(image_path)
        self.height, self.width = pixels.shape
        self.resolution = float(metadata["resolution"])
        self.origin_x = float(metadata["origin"][0])
        self.origin_y = float(metadata["origin"][1])
        negate = bool(int(metadata.get("negate", 0)))
        normalized = pixels.astype(np.float32) / 255.0
        occupancy = normalized if negate else 1.0 - normalized
        free = occupancy <= float(metadata.get("free_thresh", 0.196))

        radius = max(1, int(math.ceil(clearance / self.resolution)))
        occupied = (~free).astype(np.int32)
        integral = np.pad(occupied, ((1, 0), (1, 0))).cumsum(0).cumsum(1)
        safe = np.zeros_like(free, dtype=bool)
        for row in range(radius, self.height - radius):
            top, bottom = row - radius, row + radius + 1
            centers = np.arange(radius, self.width - radius)
            left = centers - radius
            right = centers + radius + 1
            counts = (
                integral[bottom, right]
                - integral[top, right]
                - integral[bottom, left]
                + integral[top, left]
            )
            safe[row, radius : self.width - radius] = counts == 0

        self.safe_mask = safe
        self.components = self._label_components(safe)
        ids, counts = np.unique(self.components[self.components >= 0], return_counts=True)
        self.valid_components = ids[counts >= 20]
        if self.valid_components.size == 0:
            raise ValueError(
                f"No connected free-space component remains at {clearance:.3f} m clearance"
            )

    @staticmethod
    def _read_pgm(path: Path) -> np.ndarray:
        with path.open("rb") as stream:
            def token() -> bytes:
                while True:
                    value = stream.readline()
                    if not value:
                        raise ValueError(f"Malformed PGM: {path}")
                    value = value.split(b"#", 1)[0]
                    parts = value.split()
                    if parts:
                        token.buffer.extend(parts[1:])
                        return parts[0]

            token.buffer = []  # type: ignore[attr-defined]

            def next_token() -> bytes:
                if token.buffer:  # type: ignore[attr-defined]
                    return token.buffer.pop(0)  # type: ignore[attr-defined]
                return token()

            magic = next_token()
            width = int(next_token())
            height = int(next_token())
            maximum = int(next_token())
            if maximum > 255:
                raise ValueError("16-bit PGM maps are not supported")
            if magic == b"P5":
                data = np.frombuffer(stream.read(width * height), dtype=np.uint8)
            elif magic == b"P2":
                values: List[int] = []
                while len(values) < width * height:
                    line = stream.readline().split(b"#", 1)[0]
                    values.extend(int(item) for item in line.split())
                data = np.asarray(values, dtype=np.uint8)
            else:
                raise ValueError(f"Unsupported PGM format {magic!r}")
        if data.size != width * height:
            raise ValueError(f"PGM size mismatch in {path}")
        return data.reshape(height, width)

    @staticmethod
    def _label_components(mask: np.ndarray) -> np.ndarray:
        labels = np.full(mask.shape, -1, dtype=np.int32)
        component = 0
        height, width = mask.shape
        for row, col in np.argwhere(mask):
            if labels[row, col] >= 0:
                continue
            labels[row, col] = component
            pending = [(int(row), int(col))]
            while pending:
                current_row, current_col = pending.pop()
                for next_row, next_col in (
                    (current_row - 1, current_col),
                    (current_row + 1, current_col),
                    (current_row, current_col - 1),
                    (current_row, current_col + 1),
                ):
                    if (
                        0 <= next_row < height
                        and 0 <= next_col < width
                        and mask[next_row, next_col]
                        and labels[next_row, next_col] < 0
                    ):
                        labels[next_row, next_col] = component
                        pending.append((next_row, next_col))
            component += 1
        return labels

    def sample_pair(
        self,
        rng: np.random.Generator,
        min_distance: float,
        max_distance: float,
        attempts: int = 2000,
    ) -> Tuple[Tuple[float, float], Tuple[float, float]]:
        component = int(rng.choice(self.valid_components))
        cells = np.argwhere(self.components == component)
        for _ in range(attempts):
            first, second = cells[rng.integers(0, len(cells), size=2)]
            start = self._cell_to_world(int(first[0]), int(first[1]))
            goal = self._cell_to_world(int(second[0]), int(second[1]))
            distance = math.dist(start, goal)
            if min_distance <= distance <= max_distance:
                return start, goal
        raise RuntimeError(
            "Unable to sample a connected start/goal pair within configured distance"
        )

    def _cell_to_world(self, row: int, column: int) -> Tuple[float, float]:
        x = self.origin_x + (column + 0.5) * self.resolution
        y = self.origin_y + (self.height - row - 0.5) * self.resolution
        return float(x), float(y)


class ObservationPreprocessor:
    """The single training/deployment observation implementation."""

    schema_version = OBSERVATION_SCHEMA_VERSION

    def __init__(self, sensor: SensorConfig, action: ActionConfig):
        self.sensor = sensor
        self.action = action
        if sensor.lidar_sectors <= 0:
            raise ValueError("lidar_sectors must be positive")
        if min(action.max_vx, action.max_vy, action.max_wz) <= 0.0:
            raise ValueError("physical action limits must be positive")
        self.observation_size = sensor.lidar_sectors + 5

    def build(
        self,
        scan: LaserScan,
        odom: Odometry,
        goal_world: Tuple[float, float],
        *,
        pose_override: Optional[Tuple[float, float, float]] = None,
        rng: Optional[np.random.Generator] = None,
        randomization: Optional[Mapping[str, float]] = None,
        elapsed: float = 0.0,
    ) -> PreprocessedObservation:
        randomization = randomization or {}
        sector_ranges, invalid_fraction = self.process_lidar(
            scan, rng=rng, randomization=randomization
        )
        pose = odom.pose.pose
        twist = odom.twist.twist
        if pose_override is None:
            x = finite(pose.position.x, "odom.x")
            y = finite(pose.position.y, "odom.y")
            yaw = quaternion_to_yaw(pose.orientation)
        else:
            x = finite(pose_override[0], "task_pose.x")
            y = finite(pose_override[1], "task_pose.y")
            yaw = wrap_angle(finite(pose_override[2], "task_pose.yaw"))
        vx = finite(twist.linear.x, "odom.vx")
        vy = finite(twist.linear.y, "odom.vy")
        wz = finite(twist.angular.z, "odom.wz")

        if rng is not None and randomization:
            xy_std = randomization.get("odom_xy_noise_std", 0.0)
            yaw_std = randomization.get("odom_yaw_noise_std", 0.0)
            vel_std = randomization.get("odom_velocity_noise_std", 0.0)
            drift = randomization.get("odom_drift_per_second", 0.0) * elapsed
            scale = randomization.get("odom_scale_error", 1.0)
            x = x * scale + drift + float(rng.normal(0.0, xy_std))
            y = y * scale + drift + float(rng.normal(0.0, xy_std))
            yaw = wrap_angle(yaw + float(rng.normal(0.0, yaw_std)))
            vx += float(rng.normal(0.0, vel_std))
            vy += float(rng.normal(0.0, vel_std))
            wz += float(rng.normal(0.0, vel_std))

        dx = finite(goal_world[0], "goal.x") - x
        dy = finite(goal_world[1], "goal.y") - y
        cosine, sine = math.cos(yaw), math.sin(yaw)
        goal_x_robot = cosine * dx + sine * dy
        goal_y_robot = -sine * dx + cosine * dy
        goal_scale = self.sensor.goal_normalization_distance

        features = np.asarray(
            [
                np.clip(goal_x_robot / goal_scale, -1.0, 1.0),
                np.clip(goal_y_robot / goal_scale, -1.0, 1.0),
                np.clip(vx / self.action.max_vx, -1.0, 1.0),
                np.clip(vy / self.action.max_vy, -1.0, 1.0),
                np.clip(wz / self.action.max_wz, -1.0, 1.0),
            ],
            dtype=np.float32,
        )
        observation = np.concatenate(
            (sector_ranges / self.sensor.lidar_max, features)
        ).astype(np.float32)
        observation = np.clip(observation, -1.0, 1.0).astype(np.float32)
        if observation.shape != (self.observation_size,):
            raise RuntimeError(
                f"Observation shape {observation.shape}, expected {(self.observation_size,)}"
            )
        if not np.isfinite(observation).all():
            raise RuntimeError("Observation contains NaN/Inf")
        return PreprocessedObservation(
            observation=observation,
            sector_ranges=sector_ranges.astype(np.float32),
            invalid_lidar_fraction=float(invalid_fraction),
            min_clearance=float(np.min(sector_ranges)),
            distance_to_goal=float(math.hypot(dx, dy)),
            robot_x=float(x),
            robot_y=float(y),
            robot_yaw=float(yaw),
            measured_velocity=np.asarray([vx, vy, wz], dtype=np.float32),
        )

    def process_lidar(
        self,
        scan: LaserScan,
        *,
        rng: Optional[np.random.Generator] = None,
        randomization: Optional[Mapping[str, float]] = None,
    ) -> Tuple[np.ndarray, float]:
        ranges = np.asarray(scan.ranges, dtype=np.float32)
        if ranges.size == 0:
            raise ValueError("LaserScan contains no rays")
        configured_min = max(float(scan.range_min), self.sensor.lidar_min_valid)
        configured_max = min(float(scan.range_max), self.sensor.lidar_max)
        finite_mask = np.isfinite(ranges)
        positive_infinity = np.isposinf(ranges)
        below = finite_mask & (ranges < configured_min)
        above = finite_mask & (ranges > configured_max)
        invalid = ((~finite_mask) & ~positive_infinity) | below | above
        invalid_fraction = float(np.mean(invalid))
        if invalid_fraction > self.sensor.max_invalid_lidar_fraction:
            raise ValueError(
                f"LaserScan invalid fraction {invalid_fraction:.3f} exceeds "
                f"{self.sensor.max_invalid_lidar_fraction:.3f}"
            )
        clean = np.full(ranges.shape, self.sensor.lidar_max, dtype=np.float32)
        valid = finite_mask & ~below & ~above
        clean[valid] = np.clip(ranges[valid], configured_min, configured_max)
        if self.sensor.invalid_below_min_is_obstacle:
            clean[below] = self.sensor.lidar_min_valid

        randomization = randomization or {}
        if rng is not None and randomization:
            clean += float(randomization.get("lidar_bias", 0.0))
            clean += rng.normal(
                0.0,
                float(randomization.get("lidar_noise_std", 0.0)),
                size=clean.shape,
            ).astype(np.float32)
            ray_dropout = rng.random(clean.size) < float(
                randomization.get("lidar_ray_dropout", 0.0)
            )
            max_returns = rng.random(clean.size) < float(
                randomization.get("lidar_max_return_probability", 0.0)
            )
            outliers = rng.random(clean.size) < float(
                randomization.get("lidar_outlier_probability", 0.0)
            )
            clean[ray_dropout | max_returns] = self.sensor.lidar_max
            if np.any(outliers):
                clean[outliers] = rng.uniform(
                    configured_min, self.sensor.lidar_max, int(np.sum(outliers))
                )
        clean = np.clip(
            clean, self.sensor.lidar_min_valid, self.sensor.lidar_max
        ).astype(np.float32)

        if not math.isfinite(float(scan.angle_increment)) or float(scan.angle_increment) == 0.0:
            raise ValueError("LaserScan angle_increment must be finite and non-zero")
        angles = self.sensor.lidar_yaw_offset + float(scan.angle_min) + np.arange(
            clean.size, dtype=np.float32
        ) * float(scan.angle_increment)
        phases = np.mod(angles, 2.0 * np.pi)
        sector_width = 2.0 * np.pi / self.sensor.lidar_sectors
        sector_ids = np.floor(phases / sector_width).astype(np.int32)
        sector_ids = np.clip(sector_ids, 0, self.sensor.lidar_sectors - 1)
        sectors = np.full(
            self.sensor.lidar_sectors, self.sensor.lidar_max, dtype=np.float32
        )
        np.minimum.at(sectors, sector_ids, clean)
        if rng is not None and randomization:
            drop_probability = float(
                randomization.get("lidar_sector_dropout", 0.0)
            )
            sectors[rng.random(sectors.size) < drop_probability] = (
                self.sensor.lidar_max
            )
        return sectors, invalid_fraction

    def schema(self) -> Dict[str, Any]:
        """Serializable feature contract saved next to every model."""
        return {
            "version": self.schema_version,
            "dtype": "float32",
            "shape": [self.observation_size],
            "features": [
                f"lidar_sector_{index}" for index in range(self.sensor.lidar_sectors)
            ]
            + ["goal_robot_x", "goal_robot_y", "measured_vx", "measured_vy", "measured_wz"],
            "sensor": dataclass_dict(self.sensor),
            "action": dataclass_dict(self.action),
        }


class SafetySupervisor:
    """Stateful velocity/acceleration/jerk and stopping-distance supervisor."""

    def __init__(
        self,
        action: ActionConfig,
        safety: SafetyConfig,
        lidar_sectors: int,
    ):
        self.action = action
        self.safety = safety
        self.lidar_sectors = int(lidar_sectors)
        self.last_command = np.zeros(3, dtype=np.float32)
        self.last_acceleration = np.zeros(3, dtype=np.float32)
        self.last_update_time: Optional[float] = None
        self.last_proposal_wall_time: Optional[float] = None

    def reset(self, now: Optional[float] = None) -> None:
        self.last_command[:] = 0.0
        self.last_acceleration[:] = 0.0
        self.last_update_time = now
        self.last_proposal_wall_time = time.monotonic()

    def limit(
        self,
        proposed: Sequence[float],
        sector_ranges: Optional[np.ndarray],
        *,
        dt: float,
        sensor_healthy: bool,
        measured_velocity: Optional[Sequence[float]] = None,
        now: Optional[float] = None,
    ) -> SafetyResult:
        command = np.asarray(proposed, dtype=np.float32).reshape(-1)
        self.last_proposal_wall_time = time.monotonic()
        if command.shape != (3,) or not np.isfinite(command).all():
            return self._stop("invalid_command")
        if not sensor_healthy and self.safety.stop_on_invalid_observation:
            return self._stop("sensor_unhealthy")
        if not self.safety.enabled:
            return SafetyResult(command.copy(), "disabled", False, math.inf, 0.0)

        hard = np.asarray(
            [self.action.max_vx, self.action.max_vy, self.action.max_wz],
            dtype=np.float32,
        )
        clipped = np.clip(command, -hard, hard)
        limited = not np.allclose(clipped, command)
        dt = max(float(dt), 1e-4)
        max_acceleration = np.asarray(
            [self.action.max_ax, self.action.max_ay, self.action.max_awz],
            dtype=np.float32,
        )
        requested_acceleration = (clipped - self.last_command) / dt
        acceleration = np.clip(
            requested_acceleration, -max_acceleration, max_acceleration
        )
        if not np.allclose(acceleration, requested_acceleration):
            limited = True
        jerk_limits = (self.action.max_jerk_x, self.action.max_jerk_y, self.action.max_jerk_wz)
        for index, jerk_limit in enumerate(jerk_limits):
            if jerk_limit is None:
                continue
            lower = self.last_acceleration[index] - float(jerk_limit) * dt
            upper = self.last_acceleration[index] + float(jerk_limit) * dt
            new_value = float(np.clip(acceleration[index], lower, upper))
            limited = limited or not math.isclose(new_value, float(acceleration[index]))
            acceleration[index] = new_value
        safe_command = self.last_command + acceleration * dt

        directional_clearance = math.inf
        stopping_distance = 0.0
        measured = (
            np.asarray(measured_velocity, dtype=np.float32).reshape(-1)
            if measured_velocity is not None
            else np.zeros(3, dtype=np.float32)
        )
        if measured.shape != (3,) or not np.isfinite(measured).all():
            return self._stop("invalid_measured_velocity")
        commanded_speed = float(np.linalg.norm(safe_command[:2]))
        measured_speed = float(np.linalg.norm(measured[:2]))
        linear_speed = max(commanded_speed, measured_speed)
        status = "limited" if limited else "ok"
        if sector_ranges is None or sector_ranges.shape != (self.lidar_sectors,):
            return self._stop("invalid_lidar_geometry")
        if linear_speed > 1e-5:
            motion_vector = measured[:2] if measured_speed > commanded_speed else safe_command[:2]
            heading = math.atan2(float(motion_vector[1]), float(motion_vector[0]))
            sector_angles = np.arange(self.lidar_sectors) * (
                2.0 * np.pi / self.lidar_sectors
            )
            angular_error = np.abs(
                np.arctan2(np.sin(sector_angles - heading), np.cos(sector_angles - heading))
            )
            cone = angular_error <= self.safety.motion_cone_half_angle
            directional_clearance = float(np.min(sector_ranges[cone]))
            stopping_distance = (
                linear_speed**2 / (2.0 * self.safety.braking_acceleration)
                + linear_speed * self.safety.total_latency
                + self.safety.footprint_radius
                + self.safety.obstacle_margin
            )
            emergency_distance = (
                self.safety.footprint_radius + self.safety.emergency_margin
            )
            if directional_clearance <= emergency_distance:
                return self._stop(
                    "emergency_obstacle", directional_clearance, stopping_distance
                )
            if directional_clearance < stopping_distance:
                usable = max(directional_clearance - emergency_distance, 0.0)
                span = max(stopping_distance - emergency_distance, 1e-6)
                safe_command[:2] *= float(np.clip(usable / span, 0.0, 1.0))
                limited = True
                status = "braking_for_obstacle"

        safe_command = safe_command.astype(np.float32)
        self.last_acceleration = (safe_command - self.last_command) / dt
        self.last_command = safe_command.copy()
        self.last_update_time = now
        return SafetyResult(
            safe_command, status, limited, directional_clearance, stopping_distance
        )

    def watchdog(self) -> SafetyResult:
        if self.last_proposal_wall_time is None:
            return self._stop("watchdog_not_started")
        if time.monotonic() - self.last_proposal_wall_time > self.safety.command_watchdog:
            return self._stop("command_watchdog")
        return SafetyResult(self.last_command.copy(), "watchdog_ok", False, math.inf, 0.0)

    def _stop(
        self,
        status: str,
        clearance: float = math.inf,
        stopping_distance: float = 0.0,
    ) -> SafetyResult:
        self.last_command[:] = 0.0
        self.last_acceleration[:] = 0.0
        return SafetyResult(
            np.zeros(3, dtype=np.float32),
            status,
            True,
            float(clearance),
            float(stopping_distance),
        )


class RLBridgeNode(Node):
    """Asynchronous ROS callbacks exposed through synchronized snapshots."""

    def __init__(self, config: RosInterfaceConfig):
        super().__init__(f"mecanum_rl_bridge_{uuid.uuid4().hex[:8]}")
        self.config = config
        self.set_parameters(
            [Parameter("use_sim_time", value=config.use_sim_time)]
        )
        sensor_qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=20,
        )
        command_qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
        )
        self.lock = threading.RLock()
        self.cmd_vel_publisher = self.create_publisher(
            Twist, config.cmd_vel_topic, command_qos
        )
        self.scan_subscription = self.create_subscription(
            LaserScan, config.scan_topic, self._scan_callback, sensor_qos
        )
        self.odom_subscription = self.create_subscription(
            Odometry, config.odom_topic, self._odom_callback, sensor_qos
        )
        self.ground_truth_odom_subscription = self.create_subscription(
            Odometry,
            config.ground_truth_odom_topic,
            self._ground_truth_odom_callback,
            sensor_qos,
        )
        self.contact_subscription = None
        if config.collision_topic:
            self.contact_subscription = self.create_subscription(
                Contacts, config.collision_topic, self._contact_callback, sensor_qos
            )
        self.set_pose_client = self.create_client(
            SetEntityPose, config.set_pose_service
        )
        self.control_world_client = self.create_client(
            ControlWorld, config.control_world_service
        )
        self.latest_scan: Optional[LaserScan] = None
        self.latest_odom: Optional[Odometry] = None
        self.latest_ground_truth_odom: Optional[Odometry] = None
        self.scan_stamp: Optional[float] = None
        self.odom_stamp: Optional[float] = None
        self.ground_truth_odom_stamp: Optional[float] = None
        self.contact_stamp: Optional[float] = None
        self.scan_wall_time: Optional[float] = None
        self.odom_wall_time: Optional[float] = None
        self.ground_truth_odom_wall_time: Optional[float] = None
        self.contact_wall_time: Optional[float] = None
        self.scan_seq = 0
        self.odom_seq = 0
        self.ground_truth_odom_seq = 0
        self.contact_seq = 0
        self.collision_active = False
        self.collision_latched = False

    def _scan_callback(self, message: LaserScan) -> None:
        with self.lock:
            self.latest_scan = message
            self.scan_stamp = stamp_to_seconds(message.header.stamp)
            self.scan_wall_time = time.monotonic()
            self.scan_seq += 1

    def _odom_callback(self, message: Odometry) -> None:
        with self.lock:
            self.latest_odom = message
            self.odom_stamp = stamp_to_seconds(message.header.stamp)
            self.odom_wall_time = time.monotonic()
            self.odom_seq += 1

    def _ground_truth_odom_callback(self, message: Odometry) -> None:
        with self.lock:
            self.latest_ground_truth_odom = message
            self.ground_truth_odom_stamp = stamp_to_seconds(message.header.stamp)
            self.ground_truth_odom_wall_time = time.monotonic()
            self.ground_truth_odom_seq += 1

    def _contact_callback(self, message: Contacts) -> None:
        active = any(self._relevant_contact(contact) for contact in message.contacts)
        with self.lock:
            self.contact_stamp = stamp_to_seconds(message.header.stamp)
            self.contact_wall_time = time.monotonic()
            self.contact_seq += 1
            self.collision_active = bool(active)
            self.collision_latched = self.collision_latched or bool(active)

    def _relevant_contact(self, contact: Any) -> bool:
        names: List[str] = []
        for field_name in ("collision1", "collision2"):
            entity = getattr(contact, field_name, None)
            name = getattr(entity, "name", "")
            if name:
                names.append(str(name))
        if not names:
            return True
        robot_name = self.config.robot_entity_name
        if not any(robot_name in name for name in names):
            return False
        non_robot = [name for name in names if robot_name not in name]
        if non_robot and all(
            any(pattern in name for pattern in self.config.contact_exclude_patterns)
            for name in non_robot
        ):
            return False
        return True

    def snapshot(self) -> SensorSnapshot:
        with self.lock:
            return SensorSnapshot(
                self.latest_scan,
                self.latest_odom,
                self.latest_ground_truth_odom,
                self.scan_stamp,
                self.odom_stamp,
                self.ground_truth_odom_stamp,
                self.contact_stamp,
                self.scan_wall_time,
                self.odom_wall_time,
                self.ground_truth_odom_wall_time,
                self.contact_wall_time,
                self.scan_seq,
                self.odom_seq,
                self.ground_truth_odom_seq,
                self.contact_seq,
                self.collision_latched,
            )

    def begin_transition(self) -> SensorSnapshot:
        """Atomically clear the contact latch and capture sequence barriers."""
        with self.lock:
            self.collision_latched = False
            return SensorSnapshot(
                self.latest_scan,
                self.latest_odom,
                self.latest_ground_truth_odom,
                self.scan_stamp,
                self.odom_stamp,
                self.ground_truth_odom_stamp,
                self.contact_stamp,
                self.scan_wall_time,
                self.odom_wall_time,
                self.ground_truth_odom_wall_time,
                self.contact_wall_time,
                self.scan_seq,
                self.odom_seq,
                self.ground_truth_odom_seq,
                self.contact_seq,
                False,
            )

    def clear_collision_latch(self) -> None:
        with self.lock:
            self.collision_latched = False
            self.collision_active = False

    def publish_command(self, command: Sequence[float]) -> None:
        values = np.asarray(command, dtype=np.float32)
        if values.shape != (3,) or not np.isfinite(values).all():
            values = np.zeros(3, dtype=np.float32)
        message = Twist()
        message.linear.x = float(values[0])
        message.linear.y = float(values[1])
        message.angular.z = float(values[2])
        self.cmd_vel_publisher.publish(message)

    def stop(self) -> None:
        self.publish_command((0.0, 0.0, 0.0))

    def call_service(self, client: Any, request: Any, timeout: float) -> Any:
        if not client.wait_for_service(timeout_sec=timeout):
            raise TimeoutError(f"ROS service unavailable: {client.srv_name}")
        future = client.call_async(request)
        deadline = time.monotonic() + timeout
        while rclpy.ok() and time.monotonic() < deadline:
            if future.done():
                result = future.result()
                if result is None:
                    raise RuntimeError(f"ROS service returned no result: {client.srv_name}")
                return result
            time.sleep(0.001)
        raise TimeoutError(f"ROS service timed out: {client.srv_name}")

    def set_pose(self, x: float, y: float, z: float, yaw: float, timeout: float) -> None:
        request = SetEntityPose.Request()
        request.entity.name = self.config.robot_entity_name
        request.entity.type = Entity.MODEL
        request.pose.position.x = float(x)
        request.pose.position.y = float(y)
        request.pose.position.z = float(z)
        request.pose.orientation.z = math.sin(0.5 * yaw)
        request.pose.orientation.w = math.cos(0.5 * yaw)
        result = self.call_service(self.set_pose_client, request, timeout)
        if not bool(getattr(result, "success", False)):
            raise RuntimeError(
                f"SetEntityPose rejected entity {self.config.robot_entity_name!r}"
            )

    def control_world(
        self, *, pause: bool, multi_step: int = 0, timeout: float
    ) -> None:
        request = ControlWorld.Request()
        request.world_control.pause = bool(pause)
        request.world_control.multi_step = int(multi_step)
        result = self.call_service(self.control_world_client, request, timeout)
        if not bool(getattr(result, "success", False)):
            raise RuntimeError("Gazebo ControlWorld request was rejected")


class MecanumEnv(gym.Env):
    """ROS 2 Mecanum local-navigation environment using the Gymnasium API."""

    metadata = {"render_modes": []}

    def __init__(self, config: Optional[EnvConfig] = None):
        super().__init__()
        self.config = config or EnvConfig()
        self._validate_config()
        if not rclpy.ok():
            rclpy.init(args=None)
        self.node = RLBridgeNode(self.config.ros)
        self.executor = SingleThreadedExecutor()
        self.executor.add_node(self.node)
        self.closed = False
        self.executor_thread = threading.Thread(
            target=self._spin, name=f"{self.node.get_name()}_executor", daemon=True
        )
        self.executor_thread.start()

        self.preprocessor = ObservationPreprocessor(
            self.config.sensor, self.config.action
        )
        self.safety = SafetySupervisor(
            self.config.action,
            self.config.safety,
            self.config.sensor.lidar_sectors,
        )
        observation_size = self.preprocessor.observation_size
        self.observation_space = spaces.Box(
            low=-1.0,
            high=1.0,
            shape=(observation_size,),
            dtype=np.float32,
        )
        self.action_space = spaces.Box(
            low=-1.0, high=1.0, shape=(3,), dtype=np.float32
        )
        self.map_sampler = None
        if self.config.scenario.sampling_mode == "continuous_free_space":
            if not self.config.scenario.map_yaml_path:
                raise ValueError(
                    "continuous_free_space requires scenario.map_yaml_path"
                )
            self.map_sampler = OccupancyMapSampler(
                self.config.scenario.map_yaml_path,
                self.config.scenario.minimum_clearance,
            )

        self.curriculum_progress = 1.0
        self.randomization: Dict[str, float] = {}
        self.action_queue: Deque[np.ndarray] = deque()
        self.observation_queue: Deque[np.ndarray] = deque()
        self.last_physical_command = np.zeros(3, dtype=np.float32)
        self.last_measured_velocity = np.zeros(3, dtype=np.float32)
        self.actuator_state = np.zeros(3, dtype=np.float32)
        self.previous_policy_action = np.zeros(3, dtype=np.float32)
        self.last_observation = np.zeros(observation_size, dtype=np.float32)
        self.last_sector_ranges = np.full(
            self.config.sensor.lidar_sectors,
            self.config.sensor.lidar_max,
            dtype=np.float32,
        )
        self.history: Deque[Dict[str, float]] = deque()
        self.action_sign_history: Deque[int] = deque(maxlen=100)
        self.episode_step = 0
        self.episode_start_sim_time = 0.0
        self.start = (0.0, 0.0)
        self.goal = (0.0, 0.0)
        self.start_yaw = 0.0
        self.initial_distance = 0.0
        self.previous_distance = 0.0
        self.previous_position = (0.0, 0.0)
        self.path_length = 0.0
        self.episode_min_clearance = self.config.sensor.lidar_max
        self.missed_deadlines = 0
        self.ready = False

    def _validate_config(self) -> None:
        config = self.config
        if config.control_dt <= 0.0 or config.physics_step_size <= 0.0:
            raise ValueError("control_dt and physics_step_size must be positive")
        if config.stepping_mode not in {"sim_time", "control_world"}:
            raise ValueError("stepping_mode must be sim_time or control_world")
        if config.scenario.sampling_mode not in {
            "fixed_waypoint",
            "continuous_free_space",
        }:
            raise ValueError("Unsupported sampling_mode")
        if config.scenario.split not in {"train", "validation", "holdout"}:
            raise ValueError("scenario.split must be train, validation, or holdout")
        if config.ros.require_ground_truth_collision and not config.ros.collision_topic:
            raise ValueError(
                "Ground-truth collision is required, but collision_topic is empty"
            )
        if config.stepping_mode == "control_world":
            steps = config.control_dt / config.physics_step_size
            if not math.isclose(steps, round(steps), abs_tol=1e-8):
                raise ValueError(
                    "control_dt must be an integer multiple of physics_step_size"
                )

    def _spin(self) -> None:
        try:
            self.executor.spin()
        except Exception as exc:
            if not self.closed:
                self.node.get_logger().error(f"ROS executor failed: {exc!r}")

    def set_training_progress(self, progress: float) -> None:
        """Set optional curriculum strength in [0, 1]."""
        self.curriculum_progress = float(np.clip(progress, 0.0, 1.0))

    def stop_robot(self) -> None:
        self.node.stop()

    def pause_world(self) -> None:
        self.node.control_world(
            pause=True, timeout=self.config.sensor.wall_timeout
        )

    def _ensure_ready(self) -> None:
        if self.ready:
            return
        deadline = time.monotonic() + self.config.ros.startup_timeout
        missing: List[str] = []
        while rclpy.ok() and time.monotonic() < deadline:
            snapshot = self.node.snapshot()
            missing = []
            if snapshot.scan is None:
                missing.append(self.config.ros.scan_topic)
            if snapshot.odom is None:
                missing.append(self.config.ros.odom_topic)
            if snapshot.ground_truth_odom is None:
                missing.append(self.config.ros.ground_truth_odom_topic)
            if (
                self.config.ros.require_ground_truth_collision
                and snapshot.contact_seq == 0
            ):
                missing.append(self.config.ros.collision_topic)
            if not self.node.set_pose_client.service_is_ready():
                missing.append(self.config.ros.set_pose_service)
            if (
                self.config.stepping_mode == "control_world"
                and not self.node.control_world_client.service_is_ready()
            ):
                missing.append(self.config.ros.control_world_service)
            if (
                self.config.ros.require_cmd_subscriber
                and self.node.cmd_vel_publisher.get_subscription_count() == 0
            ):
                missing.append(f"subscriber:{self.config.ros.cmd_vel_topic}")
            if not missing:
                self.ready = True
                break
            time.sleep(0.02)
        if not self.ready:
            raise RuntimeError(
                "ROS/Gazebo startup contract failed; unavailable interfaces: "
                + ", ".join(sorted(set(missing)))
            )
        if self.config.stepping_mode == "control_world":
            self.pause_world()

    def _sim_time(self) -> float:
        return self.node.get_clock().now().nanoseconds * 1e-9

    def _advance(self, duration: float) -> bool:
        if self.config.stepping_mode == "control_world":
            steps = int(round(duration / self.config.physics_step_size))
            self.node.control_world(
                pause=True,
                multi_step=max(1, steps),
                timeout=self.config.sensor.wall_timeout,
            )
            return True
        start = self._sim_time()
        target = start + duration
        deadline = time.monotonic() + self.config.sensor.wall_timeout
        while rclpy.ok() and time.monotonic() < deadline:
            if self._sim_time() >= target:
                return True
            time.sleep(0.001)
        return False

    def _wait_for_fresh_sensors(
        self,
        barrier: SensorSnapshot,
        minimum_stamp: float,
        timeout: Optional[float] = None,
    ) -> SensorSnapshot:
        timeout = timeout or self.config.sensor.sensor_timeout
        deadline = time.monotonic() + timeout
        sensor = self.config.sensor
        while rclpy.ok() and time.monotonic() < deadline:
            snapshot = self.node.snapshot()
            scan_fresh = (
                snapshot.scan is not None
                and snapshot.scan_seq > barrier.scan_seq
                and snapshot.scan_stamp is not None
                and snapshot.scan_stamp > (barrier.scan_stamp or -math.inf)
                and snapshot.scan_stamp >= minimum_stamp
            )
            odom_fresh = (
                snapshot.odom is not None
                and snapshot.odom_seq > barrier.odom_seq
                and snapshot.odom_stamp is not None
                and snapshot.odom_stamp > (barrier.odom_stamp or -math.inf)
                and snapshot.odom_stamp >= minimum_stamp
            )
            ground_truth_odom_fresh = (
                snapshot.ground_truth_odom is not None
                and snapshot.ground_truth_odom_seq > barrier.ground_truth_odom_seq
                and snapshot.ground_truth_odom_stamp is not None
                and snapshot.ground_truth_odom_stamp
                > (barrier.ground_truth_odom_stamp or -math.inf)
                and snapshot.ground_truth_odom_stamp >= minimum_stamp
            )
            contact_fresh = (
                not self.config.ros.require_ground_truth_collision
                or not sensor.require_fresh_contact_each_step
                or (
                    snapshot.contact_seq > barrier.contact_seq
                    and snapshot.contact_stamp is not None
                    and snapshot.contact_stamp > (barrier.contact_stamp or -math.inf)
                    and snapshot.contact_stamp >= minimum_stamp
                )
            )
            if scan_fresh and odom_fresh and ground_truth_odom_fresh and contact_fresh:
                skew = abs(snapshot.scan_stamp - snapshot.ground_truth_odom_stamp)
                sim_now = self._sim_time()
                scan_age = sim_now - snapshot.scan_stamp
                odom_age = sim_now - snapshot.odom_stamp
                ground_truth_odom_age = sim_now - snapshot.ground_truth_odom_stamp
                wall_now = time.monotonic()
                wall_fresh = (
                    snapshot.scan_wall_time is not None
                    and snapshot.odom_wall_time is not None
                    and snapshot.ground_truth_odom_wall_time is not None
                    and wall_now - snapshot.scan_wall_time <= timeout
                    and wall_now - snapshot.odom_wall_time <= timeout
                    and wall_now - snapshot.ground_truth_odom_wall_time <= timeout
                )
                if self.config.ros.require_ground_truth_collision:
                    wall_fresh = bool(
                        wall_fresh
                        and snapshot.contact_wall_time is not None
                        and wall_now - snapshot.contact_wall_time <= timeout
                    )
                if (
                    skew <= sensor.max_sensor_skew
                    and -sensor.max_sensor_skew <= scan_age <= sensor.max_sensor_age
                    and -sensor.max_sensor_skew <= odom_age <= sensor.max_sensor_age
                    and -sensor.max_sensor_skew
                    <= ground_truth_odom_age
                    <= sensor.max_sensor_age
                    and wall_fresh
                ):
                    return snapshot
            time.sleep(0.001)
        raise TimeoutError(
            "fresh synchronized scan/odom/ground_truth_odom/contact not received after transition; "
            f"seq=({self.node.scan_seq},{self.node.odom_seq},"
            f"{self.node.ground_truth_odom_seq},{self.node.contact_seq})"
        )

    def _sample_start_goal(self) -> Tuple[Tuple[float, float], Tuple[float, float]]:
        scenario = self.config.scenario
        if self.map_sampler is not None:
            return self.map_sampler.sample_pair(
                self.np_random,
                scenario.min_start_goal_distance,
                scenario.max_start_goal_distance,
            )
        waypoints = list(scenario.fixed_waypoints)
        indices = np.array_split(np.arange(len(waypoints)), 3)
        split_index = {"train": 0, "validation": 1, "holdout": 2}[scenario.split]
        selected = [waypoints[int(index)] for index in indices[split_index]]
        if len(selected) < 2:
            raise ValueError(f"Not enough fixed waypoints for {scenario.split}")
        candidates = [
            (start, goal)
            for start in selected
            for goal in selected
            if start != goal
            and scenario.min_start_goal_distance
            <= math.dist(start, goal)
            <= scenario.max_start_goal_distance
        ]
        if not candidates:
            raise ValueError(
                f"No fixed start/goal candidates satisfy distances for {scenario.split}"
            )
        return candidates[int(self.np_random.integers(len(candidates)))]

    def _sample_randomization(self) -> Dict[str, float]:
        config = self.config.domain_randomization
        if not config.enabled or config.profile == "nominal":
            return {}
        strength = self.curriculum_progress
        profile_scale = {"easy": 0.45, "hard": 1.0}.get(config.profile, 0.75)
        scale = strength * profile_scale
        result: Dict[str, float] = {}
        integer_fields = {"observation_delay_steps", "command_delay_steps"}
        for name, bounds in asdict(config).items():
            if name in {"enabled", "profile"}:
                continue
            low, high = bounds
            if name in integer_fields:
                scaled_high = int(round(int(low) + scale * (int(high) - int(low))))
                result[name] = float(
                    self.np_random.integers(int(low), scaled_high + 1)
                )
                continue
            nominal = 1.0 if name in {"odom_scale_error", "motor_gain", "lateral_slip"} else 0.0
            sampled = float(self.np_random.uniform(float(low), float(high)))
            result[name] = nominal + scale * (sampled - nominal)
        return result

    def _reset_state(self) -> None:
        self.episode_step = 0
        self.path_length = 0.0
        self.episode_min_clearance = self.config.sensor.lidar_max
        self.previous_policy_action[:] = 0.0
        self.last_physical_command[:] = 0.0
        self.last_measured_velocity[:] = 0.0
        self.actuator_state[:] = 0.0
        self.history.clear()
        self.action_sign_history.clear()
        self.action_queue.clear()
        self.observation_queue.clear()
        self.safety.reset(self._sim_time())
        self.node.clear_collision_latch()
        self.randomization = self._sample_randomization()

    def reset(self, *, seed: Optional[int] = None, options: Optional[dict] = None):
        super().reset(seed=seed)
        if self.closed:
            raise RuntimeError("Environment is closed")
        self._ensure_ready()
        errors: List[str] = []
        scenario = self.config.scenario
        for attempt in range(1, scenario.reset_retries + 1):
            try:
                self._reset_state()
                self.start, self.goal = self._sample_start_goal()
                self.start_yaw = float(self.np_random.uniform(-math.pi, math.pi))
                self.node.stop()
                barrier = self.node.snapshot()
                self.node.set_pose(
                    self.start[0],
                    self.start[1],
                    scenario.start_z,
                    self.start_yaw,
                    self.config.sensor.wall_timeout,
                )
                settle_steps = max(1, int(math.ceil(scenario.reset_settle_time / self.config.control_dt)))
                for _ in range(settle_steps):
                    self.node.stop()
                    if not self._advance(self.config.control_dt):
                        raise TimeoutError("simulation clock did not advance during reset")
                minimum_stamp = self._sim_time() - self.config.sensor.max_sensor_age
                snapshot = self._wait_for_fresh_sensors(
                    barrier, minimum_stamp, timeout=self.config.ros.startup_timeout
                )
                raw_processed = self.preprocessor.build(
                    snapshot.scan,
                    snapshot.ground_truth_odom,
                    self.goal,
                )
                policy_processed = self.preprocessor.build(
                    snapshot.scan,
                    snapshot.ground_truth_odom,
                    self.goal,
                    rng=self.np_random if self.randomization else None,
                    randomization=self.randomization,
                    elapsed=0.0,
                )
                self._validate_reset(snapshot, raw_processed)
                self.episode_start_sim_time = self._sim_time()
                self.initial_distance = raw_processed.distance_to_goal
                self.previous_distance = raw_processed.distance_to_goal
                self.previous_position = (
                    raw_processed.robot_x,
                    raw_processed.robot_y,
                )
                self.episode_min_clearance = raw_processed.min_clearance
                self.last_observation = policy_processed.observation.copy()
                self.last_sector_ranges = policy_processed.sector_ranges.copy()
                self.last_measured_velocity = raw_processed.measured_velocity.copy()
                delay = int(self.randomization.get("observation_delay_steps", 0.0))
                for _ in range(delay + 1):
                    self.observation_queue.append(policy_processed.observation.copy())
                info = self._info(
                    processed=raw_processed,
                    snapshot=snapshot,
                    success=False,
                    collision=False,
                    deadlock=False,
                    timeout=False,
                    sensor_timeout=False,
                    safety_result=None,
                    reward_components=self._zero_reward_components(),
                )
                info["reset_attempt"] = attempt
                info["reachability_validated"] = bool(self.map_sampler is not None)
                info["ground_truth_odom_active"] = True
                return policy_processed.observation.copy(), info
            except Exception as exc:
                errors.append(f"attempt {attempt}: {exc}")
                self.node.stop()
                time.sleep(0.02)
        raise RuntimeError(
            "Transactional reset failed after bounded retries: " + " | ".join(errors)
        )

    def _validate_reset(
        self, snapshot: SensorSnapshot, processed: PreprocessedObservation
    ) -> None:
        scenario = self.config.scenario
        position_error = math.dist(
            (processed.robot_x, processed.robot_y), self.start
        )
        yaw_error = abs(wrap_angle(processed.robot_yaw - self.start_yaw))
        velocity = float(np.linalg.norm(processed.measured_velocity))
        if position_error > scenario.reset_pose_tolerance:
            raise RuntimeError(f"reset position error {position_error:.3f} m")
        if yaw_error > scenario.reset_yaw_tolerance:
            raise RuntimeError(f"reset yaw error {yaw_error:.3f} rad")
        if velocity > scenario.reset_velocity_tolerance:
            raise RuntimeError(f"reset velocity {velocity:.3f} exceeds tolerance")
        if processed.min_clearance < scenario.minimum_clearance:
            raise RuntimeError(
                f"spawn clearance {processed.min_clearance:.3f} m is unsafe"
            )
        if self.config.ros.require_ground_truth_collision and snapshot.collision_latched:
            raise RuntimeError("fresh contact reports collision after reset")

    def _scale_and_randomize_action(self, action: Sequence[float]) -> np.ndarray:
        normalized = np.asarray(action, dtype=np.float32).reshape(-1)
        if normalized.shape != (3,) or not np.isfinite(normalized).all():
            raise ValueError("Action must be a finite float vector with shape (3,)")
        if np.any(normalized < -1.00001) or np.any(normalized > 1.00001):
            raise ValueError("Normalized action is outside action_space [-1, 1]")
        normalized = np.clip(normalized, -1.0, 1.0)
        limits = np.asarray(
            [
                self.config.action.max_vx,
                self.config.action.max_vy,
                self.config.action.max_wz,
            ],
            dtype=np.float32,
        )
        target = normalized * limits
        randomization = self.randomization
        if randomization:
            deadzone = randomization.get("actuator_deadzone", 0.0)
            target[np.abs(normalized) < deadzone] = 0.0
            gain = randomization.get("motor_gain", 1.0)
            left_right = randomization.get("left_right_mismatch", 0.0)
            front_rear = randomization.get("front_rear_mismatch", 0.0)
            target[0] *= gain * (1.0 + front_rear)
            target[1] *= gain * (1.0 + left_right) * randomization.get("lateral_slip", 1.0)
            target[2] = gain * target[2] + randomization.get("yaw_coupling", 0.0) * target[1]
            tau = max(randomization.get("actuator_time_constant", 0.0), 0.0)
            alpha = 1.0 if tau == 0.0 else self.config.control_dt / (tau + self.config.control_dt)
            self.actuator_state += alpha * (target - self.actuator_state)
            target = self.actuator_state.copy()
            delay = int(randomization.get("command_delay_steps", 0.0))
            self.action_queue.append(target.copy())
            while len(self.action_queue) <= delay:
                self.action_queue.appendleft(np.zeros(3, dtype=np.float32))
            target = self.action_queue.popleft()
            if self.np_random.random() < randomization.get("command_hold_probability", 0.0):
                target = self.last_physical_command.copy()
        return target.astype(np.float32)

    def _delayed_observation(self, observation: np.ndarray) -> np.ndarray:
        if not self.randomization:
            return observation.copy()
        delay = int(self.randomization.get("observation_delay_steps", 0.0))
        self.observation_queue.append(observation.copy())
        while len(self.observation_queue) > delay + 1:
            self.observation_queue.popleft()
        jitter_hold_probability = min(
            self.randomization.get("timestamp_jitter", 0.0)
            / max(self.config.control_dt, 1e-6),
            1.0,
        )
        held = self.np_random.random() < min(
            self.randomization.get("scan_hold_probability", 0.0)
            + 0.5 * jitter_hold_probability,
            1.0,
        )
        if held:
            return self.last_observation.copy()
        return self.observation_queue[0].copy()

    def step(self, action: Sequence[float]):
        if self.closed:
            raise RuntimeError("Environment is closed")
        self.episode_step += 1
        normalized_action = np.asarray(action, dtype=np.float32).reshape(-1)
        proposed = self._scale_and_randomize_action(normalized_action)
        barrier = self.node.begin_transition()
        start_sim = self._sim_time()
        safety_result = self.safety.limit(
            proposed,
            self.last_sector_ranges,
            dt=self.config.control_dt,
            sensor_healthy=True,
            measured_velocity=self.last_measured_velocity,
            now=start_sim,
        )
        self.node.publish_command(safety_result.command)
        self.last_physical_command = safety_result.command.copy()
        wall_start = time.monotonic()
        if not self._advance(self.config.control_dt):
            self.missed_deadlines += 1
            return self._sensor_failure("clock_timeout")
        minimum_stamp = start_sim + (
            self.config.control_dt * self.config.sensor.min_transition_fraction
        )
        try:
            snapshot = self._wait_for_fresh_sensors(barrier, minimum_stamp)
            elapsed = max(0.0, self._sim_time() - self.episode_start_sim_time)
            raw_processed = self.preprocessor.build(
                snapshot.scan,
                snapshot.ground_truth_odom,
                self.goal,
            )
            policy_processed = self.preprocessor.build(
                snapshot.scan,
                snapshot.ground_truth_odom,
                self.goal,
                rng=self.np_random if self.randomization else None,
                randomization=self.randomization,
                elapsed=elapsed,
            )
        except (TimeoutError, ValueError, RuntimeError) as exc:
            self.missed_deadlines += 1
            return self._sensor_failure(str(exc))

        collision = bool(
            self.config.ros.collision_topic and snapshot.collision_latched
        )
        success = bool(
            raw_processed.distance_to_goal <= self.config.scenario.goal_radius
            and not collision
        )
        timeout = self.episode_step >= self.config.scenario.max_episode_steps
        displacement = math.dist(
            self.previous_position,
            (raw_processed.robot_x, raw_processed.robot_y),
        )
        self.path_length += displacement
        self.previous_position = (
            raw_processed.robot_x,
            raw_processed.robot_y,
        )
        self.episode_min_clearance = min(
            self.episode_min_clearance, raw_processed.min_clearance
        )
        deadlock = bool(
            self._update_deadlock(raw_processed, safety_result.command)
            and not success
            and not collision
        )
        terminated = bool(success or collision)
        truncated = bool((timeout or deadlock) and not terminated)
        timeout = bool(timeout and not terminated and not deadlock)
        reward, components = self._reward(
            normalized_action,
            raw_processed.distance_to_goal,
            raw_processed.min_clearance,
            success,
            collision,
            timeout,
            deadlock,
        )
        self.previous_distance = raw_processed.distance_to_goal
        self.previous_policy_action = np.clip(
            normalized_action, -1.0, 1.0
        ).astype(np.float32)
        self.last_sector_ranges = policy_processed.sector_ranges.copy()
        self.last_measured_velocity = raw_processed.measured_velocity.copy()
        observation = self._delayed_observation(policy_processed.observation)
        self.last_observation = observation.copy()
        if terminated or truncated:
            self.node.stop()
        info = self._info(
            processed=raw_processed,
            snapshot=snapshot,
            success=success,
            collision=collision,
            deadlock=deadlock,
            timeout=timeout,
            sensor_timeout=False,
            safety_result=safety_result,
            reward_components=components,
        )
        info["control_period_ms"] = 1000.0 * (time.monotonic() - wall_start)
        return observation, float(reward), terminated, truncated, info

    def _update_deadlock(
        self, processed: PreprocessedObservation, command: np.ndarray
    ) -> bool:
        now = self._sim_time()
        measured_linear = float(np.linalg.norm(processed.measured_velocity[:2]))
        commanded_linear = float(np.linalg.norm(command[:2]))
        yaw_sign = int(np.sign(command[2]))
        if yaw_sign:
            self.action_sign_history.append(yaw_sign)
        self.history.append(
            {
                "time": now,
                "distance": processed.distance_to_goal,
                "x": processed.robot_x,
                "y": processed.robot_y,
                "cmd_linear": commanded_linear,
                "cmd_angular": abs(float(command[2])),
                "measured_linear": measured_linear,
            }
        )
        window = self.config.scenario.deadlock_window_seconds
        while self.history and now - self.history[0]["time"] > window:
            self.history.popleft()
        if len(self.history) < 2 or now - self.history[0]["time"] < 0.9 * window:
            return False
        first, last = self.history[0], self.history[-1]
        progress = first["distance"] - last["distance"]
        displacement = math.hypot(last["x"] - first["x"], last["y"] - first["y"])
        mean_command = float(np.mean([item["cmd_linear"] for item in self.history]))
        mean_measured = float(np.mean([item["measured_linear"] for item in self.history]))
        mean_angular = float(np.mean([item["cmd_angular"] for item in self.history]))
        signs = list(self.action_sign_history)
        flips = sum(a != b for a, b in zip(signs, signs[1:]))
        rotating_to_search = mean_angular > 0.25 and flips < self.config.scenario.oscillation_sign_flips
        if rotating_to_search:
            return False
        commanded_but_stuck = (
            mean_command >= self.config.scenario.deadlock_command_threshold
            and mean_measured <= self.config.scenario.deadlock_measured_threshold
        )
        oscillating = flips >= self.config.scenario.oscillation_sign_flips
        no_task_progress = (
            progress < self.config.scenario.deadlock_min_progress
            and displacement < self.config.scenario.deadlock_min_displacement
        )
        return bool(no_task_progress and (commanded_but_stuck or oscillating))

    def _reward(
        self,
        action: np.ndarray,
        distance: float,
        clearance: float,
        success: bool,
        collision: bool,
        timeout: bool,
        deadlock: bool,
    ) -> Tuple[float, Dict[str, float]]:
        config = self.config.reward
        progress = self.previous_distance - distance
        r_progress = config.progress_gain * progress
        r_time = -config.step_penalty
        proximity = np.clip(
            (config.safety_distance - clearance) / config.safety_distance,
            0.0,
            1.0,
        )
        r_safety = -config.safety_gain * float(proximity**2)
        delta = np.clip(action, -1.0, 1.0) - self.previous_policy_action
        r_smooth = -config.smoothness_gain * float(np.dot(delta, delta))
        r_stuck = -config.stuck_penalty if deadlock else 0.0
        r_terminal = 0.0
        if success:
            r_terminal = config.success_reward
        elif collision:
            r_terminal = config.collision_reward
        elif timeout:
            r_terminal = config.timeout_reward
        reward = r_progress + r_time + r_safety + r_smooth + r_stuck + r_terminal
        components = {
            "r_progress": float(r_progress),
            "r_time": float(r_time),
            "r_safety": float(r_safety),
            "r_smooth": float(r_smooth),
            "r_stuck": float(r_stuck),
            "r_terminal": float(r_terminal),
            "progress": float(progress),
        }
        return float(reward), components

    @staticmethod
    def _zero_reward_components() -> Dict[str, float]:
        return {
            "r_progress": 0.0,
            "r_time": 0.0,
            "r_safety": 0.0,
            "r_smooth": 0.0,
            "r_stuck": 0.0,
            "r_terminal": 0.0,
            "progress": 0.0,
        }

    def _sensor_failure(self, reason: str):
        self.node.stop()
        components = self._zero_reward_components()
        components["r_terminal"] = self.config.reward.sensor_failure_reward
        snapshot = self.node.snapshot()
        info = self._info(
            processed=None,
            snapshot=snapshot,
            success=False,
            collision=False,
            deadlock=False,
            timeout=False,
            sensor_timeout=True,
            safety_result=None,
            reward_components=components,
        )
        info["failure_reason"] = reason
        info["stale_observation_returned"] = True
        return (
            self.last_observation.copy(),
            float(self.config.reward.sensor_failure_reward),
            False,
            True,
            info,
        )

    def _info(
        self,
        *,
        processed: Optional[PreprocessedObservation],
        snapshot: SensorSnapshot,
        success: bool,
        collision: bool,
        deadlock: bool,
        timeout: bool,
        sensor_timeout: bool,
        safety_result: Optional[SafetyResult],
        reward_components: Mapping[str, float],
    ) -> Dict[str, Any]:
        distance = (
            processed.distance_to_goal if processed is not None else self.previous_distance
        )
        navigation_time = max(0.0, self._sim_time() - self.episode_start_sim_time)
        skew = self.config.sensor.max_sensor_skew + 1.0
        if (
            snapshot.scan_stamp is not None
            and snapshot.ground_truth_odom_stamp is not None
        ):
            skew = abs(snapshot.scan_stamp - snapshot.ground_truth_odom_stamp)
        path_efficiency = 0.0
        if success and self.path_length > 0.0:
            path_efficiency = self.initial_distance / max(
                self.path_length, self.initial_distance
            )
        info: Dict[str, Any] = {
            "is_success": bool(success),
            "collision": bool(collision),
            "deadlock": bool(deadlock),
            "timeout": bool(timeout),
            "sensor_timeout": bool(sensor_timeout),
            "distance_to_goal": float(distance),
            "navigation_time": float(navigation_time),
            "path_length": float(self.path_length),
            "episode_min_clearance": float(self.episode_min_clearance),
            "sensor_skew": float(skew),
            "episode_step": int(self.episode_step),
            "min_lidar_distance": float(
                processed.min_clearance
                if processed is not None
                else np.min(self.last_sector_ranges)
            ),
            "invalid_lidar_fraction": float(
                processed.invalid_lidar_fraction if processed is not None else 1.0
            ),
            "scan_seq": int(snapshot.scan_seq),
            "odom_seq": int(snapshot.odom_seq),
            "ground_truth_odom_seq": int(snapshot.ground_truth_odom_seq),
            "contact_seq": int(snapshot.contact_seq),
            "path_efficiency": float(path_efficiency),
            "spl": float(path_efficiency),
            "ground_truth_collision_enabled": bool(self.config.ros.collision_topic),
            "safety_status": safety_result.status if safety_result else "reset",
            "safety_limited": bool(safety_result.limited) if safety_result else False,
            "directional_clearance": float(
                min(safety_result.directional_clearance, self.config.sensor.lidar_max)
                if safety_result
                else self.config.sensor.lidar_max
            ),
            "stopping_distance": float(
                safety_result.stopping_distance if safety_result else 0.0
            ),
            "cmd_vx": float(self.last_physical_command[0]),
            "cmd_vy": float(self.last_physical_command[1]),
            "cmd_wz": float(self.last_physical_command[2]),
            "missed_deadlines": int(self.missed_deadlines),
            "scenario_split": self.config.scenario.split,
            "domain_randomization_profile": self.config.domain_randomization.profile,
        }
        info.update({key: float(value) for key, value in reward_components.items()})
        missing = set(REQUIRED_INFO_KEYS) - set(info)
        if missing:
            raise RuntimeError(f"Internal info contract violation: {sorted(missing)}")
        return info

    def model_metadata(self, seed: Optional[int] = None) -> Dict[str, Any]:
        return {
            "observation_schema": self.preprocessor.schema(),
            "action_scaling": dataclass_dict(self.config.action),
            "safety": dataclass_dict(self.config.safety),
            "environment": dataclass_dict(self.config),
            "training_seed": seed,
            "ros_domain_id": os.environ.get("ROS_DOMAIN_ID", "0"),
            "randomization_sample": copy.deepcopy(self.randomization),
        }

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        try:
            self.node.stop()
        except Exception:
            pass
        try:
            self.executor.shutdown(timeout_sec=1.0)
        except Exception:
            pass
        if self.executor_thread.is_alive():
            self.executor_thread.join(timeout=1.0)
        try:
            self.executor.remove_node(self.node)
        except Exception:
            pass
        try:
            self.node.destroy_node()
        except Exception:
            pass


def _offline_contract_smoke() -> None:
    """Check pure action/safety contracts without launching Gazebo."""
    sensor = SensorConfig()
    action = ActionConfig()
    preprocessor = ObservationPreprocessor(sensor, action)
    assert preprocessor.observation_size == 77
    supervisor = SafetySupervisor(action, SafetyConfig(), sensor.lidar_sectors)
    supervisor.reset(0.0)
    clear = np.full(sensor.lidar_sectors, sensor.lidar_max, dtype=np.float32)
    result = supervisor.limit((10.0, -10.0, 10.0), clear, dt=0.1, sensor_healthy=True)
    assert result.command.dtype == np.float32
    assert np.isfinite(result.command).all()
    assert abs(result.command[0]) <= action.max_vx
    stopped = supervisor.limit((0.1, 0.0, 0.0), None, dt=0.1, sensor_healthy=False)
    assert np.array_equal(stopped.command, np.zeros(3, dtype=np.float32))
    print("offline contract smoke test: PASS")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline-smoke", action="store_true")
    parser.add_argument("--seed", type=int, default=42)
    arguments = parser.parse_args()
    if arguments.offline_smoke:
        _offline_contract_smoke()
        return
    environment: Optional[MecanumEnv] = None
    try:
        environment = MecanumEnv()
        observation, info = environment.reset(seed=arguments.seed)
        print(environment.observation_space, environment.action_space)
        print(observation.shape, info)
    finally:
        if environment is not None:
            environment.close()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
