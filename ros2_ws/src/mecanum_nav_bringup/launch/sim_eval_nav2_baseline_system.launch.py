"""Canonical sim_eval/NAV2_BASELINE composite source; static-only until campaign."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, OpaqueFunction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

EXPECTED_PARTITION = "wp06_scan_probe_run_002"
MAP_FILES = {
    "map.yaml": "5073762401784f67e856b5018656ad869ecc26e723f85e5979054eadc7876a68",
    "map.pgm": "32f8a3eb626ebddecc15843748de0db8c6f7adc1b45a5edc1b1b1886407aef55",
    "metadata.yaml": "45450a2d62b38560200d11fef6ece8505eef5a3e3d73e27f7b091de022e793c1",
    "map_manifest.json": "7e0a380b0d8df32f9a4fc30dd0dbbe9ed08aafdcd5efb3764bccd844b98c1cb1",
}


def _checked_map_yaml():
    root = Path.cwd() / "artifacts" / "maps" / "warehouse_map2"
    for name, expected in MAP_FILES.items():
        path = root / name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise RuntimeError(f"SIM_EVAL_MAP_ARTIFACT_IDENTITY_FAILURE:{name}")
    return str(root / "map.yaml")


def _actions(context):
    partition = LaunchConfiguration("gz_partition").perform(context)
    if partition != EXPECTED_PARTITION:
        raise RuntimeError("SIM_EVAL_NAV2_BASELINE_PARTITION_MISMATCH")
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
    ingress_ekf = os.path.join(share, "launch", "sim_eval_tf_ekf_state_estimation.launch.py")
    nav_config = os.path.join(share, "config", "navigation", "sim_eval_nav2_baseline.runtime.yaml")
    amcl_config = os.path.join(share, "config", "localization", "amcl_omni.yaml")
    lifecycle_config = os.path.join(share, "config", "lifecycle", "sim_eval_nav2_baseline.runtime.yaml")
    safety_config = os.path.join(rl_share, "config", "safety", "sim_eval_nav2_baseline_safety.yaml")
    map_yaml = _checked_map_yaml()
    pose = {key: LaunchConfiguration(key) for key in ("initial_pose_map_x", "initial_pose_map_y", "initial_pose_map_yaw")}
    nav2 = [
        Node(package="nav2_map_server", executable="map_server", name="map_server",
             parameters=[{"use_sim_time": True, "frame_id": "map", "yaml_filename": map_yaml}], output="screen"),
        Node(package="nav2_amcl", executable="amcl", name="amcl",
             parameters=[amcl_config, {"use_sim_time": True, "set_initial_pose": True,
                 "initial_pose.x": pose["initial_pose_map_x"],
                 "initial_pose.y": pose["initial_pose_map_y"],
                 "initial_pose.yaw": pose["initial_pose_map_yaw"]}], output="screen"),
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
             parameters=[lifecycle_config, {"use_sim_time": True, "autostart": True,
                 "node_names": ["map_server", "amcl", "planner_server", "controller_server", "behavior_server", "bt_navigator"]}], output="screen"),
    ]
    return [
        IncludeLaunchDescription(PythonLaunchDescriptionSource(bootstrap), launch_arguments={
            "gz_partition": EXPECTED_PARTITION,
            **{k: LaunchConfiguration(k) for k in pose},
        }.items()),
        IncludeLaunchDescription(PythonLaunchDescriptionSource(ingress_ekf), launch_arguments={
            "gz_partition": EXPECTED_PARTITION, "use_sim_time": "true",
        }.items()),
        Node(package="ros_gz_bridge", executable="parameter_bridge", name="sim_eval_scan_bridge",
             parameters=[{"config_file": os.path.join(share, "config", "bridge", "sim_eval_lidar_scan_bridge.runtime.yaml"), "use_sim_time": True}], output="screen"),
        *nav2,
        Node(package="mecanum_nav_rl", executable="safety_lifecycle", name="safety_lifecycle",
             parameters=[{"use_sim_time": True}], output="screen"),
        Node(package="mecanum_nav_rl", executable="safety_supervisor", name="safety_supervisor",
             parameters=[safety_config, {"use_sim_time": True}], output="screen"),
        Node(package="mecanum_nav_rl", executable="final_twist_publisher", name="final_twist_publisher",
             parameters=[{"use_sim_time": True}], output="screen"),
        Node(package="ros_gz_bridge", executable="parameter_bridge", name="sim_eval_cmd_vel_bridge",
             parameters=[{"config_file": os.path.join(share, "config", "bridge", "sim_eval_cmd_vel.runtime.yaml"), "use_sim_time": True}], output="screen"),
    ]


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument("gz_partition"),
        DeclareLaunchArgument("initial_pose_map_x"),
        DeclareLaunchArgument("initial_pose_map_y"),
        DeclareLaunchArgument("initial_pose_map_yaw"),
        OpaqueFunction(function=_actions),
    ])
