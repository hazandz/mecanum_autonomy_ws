"""Canonical sim_eval/NAV2_BASELINE composite source; static-only until campaign."""
from __future__ import annotations

import hashlib
import importlib.util
import os
from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, OpaqueFunction, RegisterEventHandler, EmitEvent
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch.event_handlers import OnProcessStart
from launch_ros.actions import Node, LifecycleNode
from launch_ros.event_handlers import OnStateTransition
from launch_ros.events.lifecycle import ChangeState
from launch_ros.parameter_descriptions import ParameterValue
from launch.events import matches_action
from lifecycle_msgs.msg import Transition

MAP_FILES = {
    "map.yaml": "5073762401784f67e856b5018656ad869ecc26e723f85e5979054eadc7876a68",
    "map.pgm": "32f8a3eb626ebddecc15843748de0db8c6f7adc1b45a5edc1b1b1886407aef55",
    "metadata.yaml": "45450a2d62b38560200d11fef6ece8505eef5a3e3d73e27f7b091de022e793c1",
    "map_manifest.json": "7e0a380b0d8df32f9a4fc30dd0dbbe9ed08aafdcd5efb3764bccd844b98c1cb1",
}


def checked_map_yaml(map_root: str | Path) -> str:
    root = Path(map_root)
    if not root.is_absolute():
        raise RuntimeError("SIM_EVAL_CANONICAL_MAP_ROOT_MUST_BE_ABSOLUTE")
    if not root.is_dir():
        raise RuntimeError("SIM_EVAL_CANONICAL_MAP_ROOT_MISSING")
    root = root.resolve(strict=True)
    for name, expected in MAP_FILES.items():
        path = root / name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise RuntimeError(f"SIM_EVAL_MAP_ARTIFACT_IDENTITY_FAILURE:{name}")
    return str(root / "map.yaml")


def _literal_bool(value: str, name: str) -> bool:
    if value == "true":
        return True
    if value == "false":
        return False
    raise RuntimeError(f"INVALID_LITERAL_BOOLEAN:{name}")


def _bootstrap_include(start_bootstrap: str, bootstrap: str, partition: str,
                       fuel_cache_root: str, pose: dict[str, str]):
    if not _literal_bool(start_bootstrap, "start_bootstrap"):
        return []
    return [IncludeLaunchDescription(PythonLaunchDescriptionSource(bootstrap), launch_arguments={
        "gz_partition": partition,
        "fuel_cache_root": fuel_cache_root,
        **pose,
    }.items())]


NAV2_LIFECYCLE_NODES = [
    "map_server", "amcl", "planner_server", "controller_server",
    "behavior_server", "bt_navigator",
]


def lifecycle_manager_parameters(path):
    """Policy barrier không phải ROS parameter file; kiểm trước khi dựng topology."""
    import yaml
    policy = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    expected = {
        "schema": "mecanum.sim_eval_nav2_baseline_lifecycle/v1",
        "use_sim_time": True, "primary_states": ["Unconfigured", "Inactive", "Active"],
        "barrier_owner": "SafetyLifecycle", "barrier_topic": "/mecanum/safety_lifecycle_state",
        "barrier_freshness_max_ms": 500, "motion_requires": ["READY", "fresh_barrier"],
        "reset_owner": "SafetyLifecycle", "missing_stale_invalid_or_mismatched_input": "FAIL_CLOSED",
    }
    if policy != expected:
        raise RuntimeError("SIM_EVAL_LIFECYCLE_POLICY_INVALID")
    return {"use_sim_time": True, "autostart": True,
            "node_names": list(NAV2_LIFECYCLE_NODES), "bond_timeout": 4.0}


def safety_lifecycle_actions():
    node = LifecycleNode(package="mecanum_nav_rl", executable="safety_lifecycle",
                         name="safety_lifecycle", namespace="",
                         parameters=[{"use_sim_time": True}], output="screen")
    configure = RegisterEventHandler(OnProcessStart(
        target_action=node, handle_once=True, on_start=[EmitEvent(event=ChangeState(
            lifecycle_node_matcher=matches_action(node),
            transition_id=Transition.TRANSITION_CONFIGURE))]))
    activate = RegisterEventHandler(OnStateTransition(
        target_lifecycle_node=node, goal_state="inactive", handle_once=True,
        entities=[EmitEvent(event=ChangeState(lifecycle_node_matcher=matches_action(node),
                                             transition_id=Transition.TRANSITION_ACTIVATE))]))
    return [configure, activate, node]


def _actions(context):
    partition = LaunchConfiguration("gz_partition").perform(context)
    if not partition.strip():
        raise RuntimeError("SIM_EVAL_GZ_PARTITION_REQUIRED")
    start_bootstrap = LaunchConfiguration("start_bootstrap").perform(context)
    _literal_bool(start_bootstrap, "start_bootstrap")
    map_yaml = checked_map_yaml(LaunchConfiguration("canonical_map_root").perform(context))
    fuel_cache_root = LaunchConfiguration("fuel_cache_root").perform(context)
    sim_estop_release_authorized = _literal_bool(
        LaunchConfiguration("sim_estop_release_authorized").perform(context),
        "sim_estop_release_authorized",
    )
    for arg in ("initial_pose_map_x", "initial_pose_map_y", "initial_pose_map_yaw"):
        value = LaunchConfiguration(arg).perform(context)
        try:
            number = float(value)
        except ValueError as error:
            raise RuntimeError(f"INVALID_REQUIRED_{arg.upper()}") from error
        if not __import__("math").isfinite(number):
            raise RuntimeError(f"INVALID_REQUIRED_{arg.upper()}")
    share = get_package_share_directory("mecanum_nav_bringup")
    description_share = get_package_share_directory("ROBOT_URDF_final_description")
    rl_share = get_package_share_directory("mecanum_nav_rl")
    bootstrap = os.path.join(description_share, "launch", "sim_eval_nav2_baseline_bootstrap.launch.py")
    bootstrap_spec = importlib.util.spec_from_file_location("sim_eval_nav2_baseline_bootstrap_preflight", bootstrap)
    if bootstrap_spec is None or bootstrap_spec.loader is None:
        raise RuntimeError("SIM_EVAL_BOOTSTRAP_PREFLIGHT_UNAVAILABLE")
    bootstrap_module = importlib.util.module_from_spec(bootstrap_spec)
    bootstrap_spec.loader.exec_module(bootstrap_module)
    bootstrap_module.validate_fuel_cache(
        os.path.join(description_share, "launch", "tugbot_depot.sdf"), fuel_cache_root
    )
    ingress_ekf = os.path.join(share, "launch", "sim_eval_tf_ekf_state_estimation.launch.py")
    nav_config = os.path.join(share, "config", "navigation", "sim_eval_nav2_baseline.runtime.yaml")
    amcl_config = os.path.join(share, "config", "localization", "amcl_omni.yaml")
    lifecycle_config = os.path.join(share, "config", "lifecycle", "sim_eval_nav2_baseline.runtime.yaml")
    safety_config = os.path.join(rl_share, "config", "safety", "sim_eval_nav2_baseline_safety.yaml")
    import yaml
    safety_policy = yaml.safe_load(Path(safety_config).read_text(encoding="utf-8"))
    safety_parameters = {
        **{f"freshness_ns.{key}": value for key, value in safety_policy["freshness_ns"].items()},
        **{f"limits.{key}": value for key, value in safety_policy["limits"].items()},
        "sim_estop_release_authorized": sim_estop_release_authorized,
    }
    pose = {key: LaunchConfiguration(key) for key in ("initial_pose_map_x", "initial_pose_map_y", "initial_pose_map_yaw")}
    bootstrap_actions = _bootstrap_include(
        start_bootstrap, bootstrap, partition, fuel_cache_root,
        {key: value for key, value in pose.items()},
    )
    nav2 = [
        Node(package="nav2_map_server", executable="map_server", name="map_server",
             parameters=[{"use_sim_time": True, "frame_id": "map", "yaml_filename": map_yaml}], output="screen"),
        Node(package="nav2_amcl", executable="amcl", name="amcl",
             parameters=[
                 amcl_config,
                 {
                     'use_sim_time': True,
                     'set_initial_pose': True,
                     'initial_pose.x': ParameterValue(
                         pose['initial_pose_map_x'], value_type=float),
                     'initial_pose.y': ParameterValue(
                         pose['initial_pose_map_y'], value_type=float),
                     'initial_pose.yaw': ParameterValue(
                         pose['initial_pose_map_yaw'], value_type=float),
                 },
             ], output='screen'),
        Node(package="nav2_planner", executable="planner_server", name="planner_server",
             parameters=[nav_config, {"use_sim_time": True}], output="screen"),
        Node(package="nav2_controller", executable="controller_server", name="controller_server",
             parameters=[nav_config, {"use_sim_time": True}],
             remappings=[("cmd_vel", "/mecanum/nav2_candidate_cmd")], output="screen"),
        Node(package="nav2_behaviors", executable="behavior_server", name="behavior_server",
             parameters=[nav_config, {"use_sim_time": True}],
             remappings=[("cmd_vel", "/mecanum/nav2_candidate_cmd")], output="screen"),
        Node(package="nav2_bt_navigator", executable="bt_navigator", name="bt_navigator",
             parameters=[nav_config, {"use_sim_time": True}], output="screen"),
        Node(package="nav2_lifecycle_manager", executable="lifecycle_manager", name="lifecycle_manager_navigation",
             parameters=[lifecycle_manager_parameters(lifecycle_config)], output="screen"),
    ]
    return [
        *bootstrap_actions,
        IncludeLaunchDescription(PythonLaunchDescriptionSource(ingress_ekf), launch_arguments={
            "gz_partition": partition, "use_sim_time": "true",
        }.items()),
        Node(package="ros_gz_bridge", executable="parameter_bridge", name="sim_eval_scan_bridge",
             parameters=[{"config_file": os.path.join(share, "config", "bridge", "sim_eval_lidar_scan_bridge.runtime.yaml"), "use_sim_time": True}], output="screen"),
        *nav2,
        *safety_lifecycle_actions(),
        Node(package="mecanum_nav_rl", executable="safety_supervisor", name="safety_supervisor",
             parameters=[safety_parameters, {"use_sim_time": True}], output="screen"),
        Node(package="mecanum_nav_rl", executable="final_twist_publisher", name="final_twist_publisher",
             parameters=[{"use_sim_time": True}], output="screen"),
        Node(package="ros_gz_bridge", executable="parameter_bridge", name="sim_eval_cmd_vel_bridge",
             parameters=[{"config_file": os.path.join(share, "config", "bridge", "sim_eval_cmd_vel.runtime.yaml"), "use_sim_time": True}], output="screen"),
    ]


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument("gz_partition"),
        DeclareLaunchArgument("start_bootstrap", default_value="true"),
        DeclareLaunchArgument("canonical_map_root"),
        DeclareLaunchArgument("fuel_cache_root"),
        DeclareLaunchArgument("sim_estop_release_authorized", default_value="false"),
        DeclareLaunchArgument("initial_pose_map_x"),
        DeclareLaunchArgument("initial_pose_map_y"),
        DeclareLaunchArgument("initial_pose_map_yaw"),
        OpaqueFunction(function=_actions),
    ])
