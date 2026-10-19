"""Bootstrap the selected Tugbot depot world and the sole robot_state_publisher."""
from __future__ import annotations

import os
from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, OpaqueFunction, SetEnvironmentVariable
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
import xacro

EXPECTED_PARTITION = "wp06_scan_probe_run_002"
WORLD_NAME = "world_demo"
ENTITY_NAME = "ROBOT_URDF_final"


def _actions(context):
    partition = LaunchConfiguration("gz_partition").perform(context)
    if partition != EXPECTED_PARTITION:
        raise RuntimeError("SIM_EVAL_NAV2_BASELINE_PARTITION_MISMATCH")
    # Map-frame initial pose is passed to AMCL by the composite launch. It is
    # deliberately not treated as a world-frame transform or Gazebo spawn pose.
    pose = {name: LaunchConfiguration(name).perform(context) for name in (
        "initial_pose_map_x", "initial_pose_map_y", "initial_pose_map_yaw"
    )}
    for name, value in pose.items():
        try:
            number = float(value)
        except ValueError as error:
            raise RuntimeError(f"INVALID_REQUIRED_{name.upper()}") from error
        if not __import__("math").isfinite(number):
            raise RuntimeError(f"INVALID_REQUIRED_{name.upper()}")

    ros_gz_sim_share = get_package_share_directory("ros_gz_sim")
    robot_share = get_package_share_directory("ROBOT_URDF_final_description")
    parent_resources = os.path.dirname(robot_share)
    existing_resources = os.environ.get("GZ_SIM_RESOURCE_PATH", "")
    resource_path = ":".join(item for item in (parent_resources, existing_resources) if item)
    world = os.path.join(robot_share, "launch", "tugbot_depot.sdf")
    xacro_path = os.path.join(robot_share, "urdf", "ROBOT_URDF_final.xacro")
    description = {"robot_description": xacro.process_file(xacro_path).toxml()}
    return [
        SetEnvironmentVariable("GZ_SIM_RESOURCE_PATH", resource_path),
        SetEnvironmentVariable("GZ_PARTITION", EXPECTED_PARTITION),
        Node(
            package="robot_state_publisher", executable="robot_state_publisher",
            name="robot_state_publisher", parameters=[description, {"use_sim_time": True}],
            output="screen",
        ),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(os.path.join(ros_gz_sim_share, "launch", "gz_sim.launch.py")),
            launch_arguments={"gz_args": f"-r -s -v 4 {world}"}.items(),
        ),
        Node(
            package="ros_gz_sim", executable="create", name="spawn_robot",
            arguments=["-world", WORLD_NAME, "-topic", "/robot_description", "-name", ENTITY_NAME,
                       "-allow_renaming", "false", "-x", "0", "-y", "0", "-z", "0.1", "-Y", "0"],
            output="screen",
        ),
    ]


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument("gz_partition"),
        DeclareLaunchArgument("initial_pose_map_x"),
        DeclareLaunchArgument("initial_pose_map_y"),
        DeclareLaunchArgument("initial_pose_map_yaw"),
        OpaqueFunction(function=_actions),
    ])
