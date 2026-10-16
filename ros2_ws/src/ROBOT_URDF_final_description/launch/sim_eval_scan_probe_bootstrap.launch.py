import os
from os.path import join

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    IncludeLaunchDescription,
    SetEnvironmentVariable,
    TimerAction,
)
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import Command, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    package_name = "ROBOT_URDF_final_description"
    package_share = get_package_share_directory(package_name)
    package_share_parent = os.path.dirname(package_share)
    world_path = join(package_share, "launch", "tugbot_depot.sdf")
    ros_gz_sim_share = get_package_share_directory("ros_gz_sim")
    current_resource_path = os.environ.get("GZ_SIM_RESOURCE_PATH", "")
    resource_paths = [package_share_parent]
    if current_resource_path:
        resource_paths.append(current_resource_path)

    robot_description = ParameterValue(
        Command(
            [
                "xacro ",
                PathJoinSubstitution(
                    [
                        FindPackageShare(package_name),
                        "urdf",
                        "ROBOT_URDF_final.xacro",
                    ]
                ),
            ]
        ),
        value_type=str,
    )

    gazebo = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            join(ros_gz_sim_share, "launch", "gz_sim.launch.py")
        ),
        launch_arguments={"gz_args": f"-r -v 4 {world_path}"}.items(),
    )

    robot_state_publisher = Node(
        package="robot_state_publisher",
        executable="robot_state_publisher",
        name="robot_state_publisher",
        output="screen",
        parameters=[
            {"robot_description": robot_description},
            {"use_sim_time": False},
        ],
    )

    create_robot = TimerAction(
        period=3.0,
        actions=[
            Node(
                package="ros_gz_sim",
                executable="create",
                arguments=[
                    "-topic",
                    "/robot_description",
                    "-name",
                    "ROBOT_URDF_final",
                    "-allow_renaming",
                    "false",
                    "-x",
                    "0.0",
                    "-y",
                    "0.0",
                    "-z",
                    "0.1",
                    "-Y",
                    "0.0",
                ],
                output="screen",
            )
        ],
    )

    return LaunchDescription(
        [
            SetEnvironmentVariable(
                name="GZ_SIM_RESOURCE_PATH",
                value=":".join(resource_paths),
            ),
            gazebo,
            robot_state_publisher,
            create_robot,
        ]
    )
