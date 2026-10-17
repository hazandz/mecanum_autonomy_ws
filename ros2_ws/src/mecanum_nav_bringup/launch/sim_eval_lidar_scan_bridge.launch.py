"""Launch only the profile-specific one-way Gazebo scan bridge."""

from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction, SetEnvironmentVariable
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def _validate_launch_contract(context):
    partition = LaunchConfiguration("gz_partition").perform(context)
    if not partition.strip():
        raise RuntimeError("gz_partition must not be empty or whitespace")
    if LaunchConfiguration("use_sim_time").perform(context) != "true":
        raise RuntimeError("use_sim_time must be exactly true")
    return []


def generate_launch_description():
    package_share = Path(get_package_share_directory("mecanum_nav_bringup"))
    config_file = str(
        package_share / "config" / "bridge" / "sim_eval_lidar_scan_bridge.runtime.yaml"
    )
    use_sim_time = LaunchConfiguration("use_sim_time")
    gz_partition = LaunchConfiguration("gz_partition")

    return LaunchDescription(
        [
            DeclareLaunchArgument("use_sim_time", default_value="true"),
            DeclareLaunchArgument("gz_partition", default_value="sim_eval"),
            OpaqueFunction(function=_validate_launch_contract),
            SetEnvironmentVariable(name="GZ_PARTITION", value=gz_partition),
            Node(
                package="ros_gz_bridge",
                executable="parameter_bridge",
                name="sim_eval_lidar_scan_bridge",
                output="screen",
                parameters=[
                    {"config_file": config_file},
                    {
                        "use_sim_time": ParameterValue(
                            use_sim_time, value_type=bool
                        )
                    },
                ],
            ),
        ]
    )
