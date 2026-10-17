"""Bridge-free bootstrap source for the future Run 003 probe session."""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, SetEnvironmentVariable
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node
import xacro


GZ_PARTITION = "wp06_scan_probe_run_003"
WORLD_NAME = "wp06_scan_probe_world"
ENTITY_NAME = "ROBOT_URDF_final"


def generate_launch_description():
    """Declare one server, one robot_state_publisher, and one robot create."""
    ros_gz_sim_share = get_package_share_directory("ros_gz_sim")
    robot_share = get_package_share_directory("ROBOT_URDF_final_description")
    resource_parent = os.path.dirname(robot_share)
    existing_resources = os.environ.get("GZ_SIM_RESOURCE_PATH", "")
    resource_path = ":".join(item for item in (resource_parent, existing_resources) if item)
    xacro_path = os.path.join(robot_share, "urdf", "ROBOT_URDF_final.xacro")
    world_path = os.path.join(robot_share, "launch", "sim_eval_scan_probe.world.sdf")
    robot_description = {"robot_description": xacro.process_file(xacro_path).toxml()}

    set_resources = SetEnvironmentVariable(name="GZ_SIM_RESOURCE_PATH", value=resource_path)
    set_partition = SetEnvironmentVariable(name="GZ_PARTITION", value=GZ_PARTITION)
    state_publisher = Node(
        package="robot_state_publisher",
        executable="robot_state_publisher",
        name="robot_state_publisher",
        parameters=[robot_description, {"use_sim_time": True}],
        output="screen",
    )
    gazebo_server = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(ros_gz_sim_share, "launch", "gz_sim.launch.py")
        ),
        launch_arguments={"gz_args": f"-r -s -v 4 {world_path}"}.items(),
    )
    spawn_robot = Node(
        package="ros_gz_sim",
        executable="create",
        arguments=[
            "-world", WORLD_NAME,
            "-topic", "/robot_description",
            "-name", ENTITY_NAME,
            "-allow_renaming", "false",
            "-x", "0.0", "-y", "0.0", "-z", "0.1", "-Y", "0.0",
        ],
        output="screen",
    )
    # Future session readiness is the create log line "Entity creation successful.".
    return LaunchDescription([set_resources, set_partition, state_publisher, gazebo_server, spawn_robot])
