"""Bridge-free, future-only bootstrap source for the scan endpoint probe."""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, SetEnvironmentVariable
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node
import xacro


GZ_PARTITION = "wp06_scan_probe_run_001"
ENTITY_NAME = "ROBOT_URDF_final"


def generate_launch_description():
    """Create only Gazebo, one RSP, and one robot creation action."""
    ros_gz_sim_share = get_package_share_directory("ros_gz_sim")
    robot_share = get_package_share_directory("ROBOT_URDF_final_description")
    resource_parent = os.path.dirname(robot_share)
    existing_resources = os.environ.get("GZ_SIM_RESOURCE_PATH", "")
    resource_path = ":".join(
        item for item in (resource_parent, existing_resources) if item
    )
    robot_xacro = os.path.join(robot_share, "urdf", "ROBOT_URDF_final.xacro")
    world_sdf = os.path.join(robot_share, "launch", "tugbot_depot.sdf")
    robot_description = {"robot_description": xacro.process_file(robot_xacro).toxml()}

    set_resource_path = SetEnvironmentVariable(
        name="GZ_SIM_RESOURCE_PATH", value=resource_path
    )
    # This is deliberately unconditional: no inherited partition is permitted.
    set_partition = SetEnvironmentVariable(name="GZ_PARTITION", value=GZ_PARTITION)
    robot_state_publisher = Node(
        package="robot_state_publisher",
        executable="robot_state_publisher",
        name="robot_state_publisher",
        parameters=[robot_description, {"use_sim_time": False}],
        output="screen",
    )
    gazebo = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(ros_gz_sim_share, "launch", "gz_sim.launch.py")
        ),
        launch_arguments={"gz_args": f"-r -v 4 {world_sdf}"}.items(),
    )
    spawn_robot = Node(
        package="ros_gz_sim",
        executable="create",
        arguments=[
            "-topic", "/robot_description",
            "-name", ENTITY_NAME,
            "-allow_renaming", "false",
            "-x", "0.0", "-y", "0.0", "-z", "0.1", "-Y", "0.0",
        ],
        output="screen",
    )
    return LaunchDescription(
        [set_resource_path, set_partition, robot_state_publisher, gazebo, spawn_robot]
    )
