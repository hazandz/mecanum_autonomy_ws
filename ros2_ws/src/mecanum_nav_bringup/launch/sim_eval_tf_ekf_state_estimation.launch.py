"""Compose the bounded wheel/IMU ingress, isolated clock bridge, and EKF."""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    IncludeLaunchDescription,
    OpaqueFunction,
    SetEnvironmentVariable,
)
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


EXPECTED_PARTITION = "wp06_scan_probe_run_002"
CLOCK_CONFIG = PathJoinSubstitution([
    FindPackageShare("mecanum_nav_bringup"),
    "config",
    "bridge",
    "sim_eval_clock.runtime.yaml",
])
EKF_CONFIG = PathJoinSubstitution([
    FindPackageShare("mecanum_nav_bringup"),
    "config",
    "state_estimation",
    "ekf_sim.yaml",
])


def _create_runtime_actions(context):
    partition = LaunchConfiguration("gz_partition").perform(context)
    if partition != EXPECTED_PARTITION:
        raise RuntimeError("WP06-6F requires the bootstrap's exact GZ_PARTITION")

    use_sim_time = LaunchConfiguration("use_sim_time").perform(context).strip().lower()
    if use_sim_time != "true":
        raise RuntimeError("WP06-6F requires use_sim_time=true")

    ingress_launch = os.path.join(
        get_package_share_directory("mecanum_base_bridge"),
        "launch",
        "sim_eval_wheel_imu_ingress.launch.py",
    )
    return [
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(ingress_launch),
            launch_arguments={
                "gz_partition": EXPECTED_PARTITION,
                "use_sim_time": "true",
            }.items(),
        ),
        Node(
            package="ros_gz_bridge",
            executable="parameter_bridge",
            name="sim_eval_clock_bridge",
            output="screen",
            parameters=[{"config_file": CLOCK_CONFIG, "use_sim_time": True}],
        ),
        Node(
            package="robot_localization",
            executable="ekf_node",
            name="ekf_filter_node",
            output="screen",
            parameters=[EKF_CONFIG, {"use_sim_time": True}],
        ),
    ]


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument("gz_partition", default_value=EXPECTED_PARTITION),
        DeclareLaunchArgument("use_sim_time", default_value="true"),
        SetEnvironmentVariable("GZ_PARTITION", LaunchConfiguration("gz_partition")),
        OpaqueFunction(function=_create_runtime_actions),
    ])
