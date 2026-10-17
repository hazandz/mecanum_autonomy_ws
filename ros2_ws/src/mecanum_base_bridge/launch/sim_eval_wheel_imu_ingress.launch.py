"""Launch the bounded sim_eval wheel/IMU Gazebo ingress path."""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction, SetEnvironmentVariable
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


RUNTIME_CONFIG = PathJoinSubstitution([
    FindPackageShare("mecanum_base_bridge"),
    "config",
    "bridge",
    "sim_eval_wheel_imu_ingress.runtime.yaml",
])


def _create_nodes(context):
    partition = LaunchConfiguration("gz_partition").perform(context)
    if not partition or not partition.strip():
        raise RuntimeError("gz_partition must be non-empty")

    use_sim_time = LaunchConfiguration("use_sim_time").perform(context).strip().lower()
    if use_sim_time != "true":
        raise RuntimeError("sim_eval wheel/IMU ingress requires use_sim_time=true")

    return [
        Node(
            package="ros_gz_bridge",
            executable="parameter_bridge",
            name="sim_eval_wheel_imu_ingress_bridge",
            output="screen",
            parameters=[{"config_file": RUNTIME_CONFIG}],
        ),
        Node(
            package="mecanum_base_bridge",
            executable="sim_eval_wheel_imu_ingress",
            name="sim_eval_wheel_imu_ingress",
            output="screen",
            parameters=[{"use_sim_time": True}],
        ),
    ]


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument("gz_partition", default_value="sim_eval"),
        DeclareLaunchArgument("use_sim_time", default_value="true"),
        SetEnvironmentVariable("GZ_PARTITION", LaunchConfiguration("gz_partition")),
        OpaqueFunction(function=_create_nodes),
    ])
