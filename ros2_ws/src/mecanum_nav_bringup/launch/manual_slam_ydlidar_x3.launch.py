"""LiDAR X3 wrapper; consumes the existing driver parameter YAML explicitly."""
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument("port"),
        DeclareLaunchArgument("frame_id", default_value="lidar_frame"),
        DeclareLaunchArgument("use_sim_time", default_value="false"),
        DeclareLaunchArgument("parameter_file"),
        Node(package="ydlidar_ros2_driver", executable="ydlidar_ros2_driver_node",
             name="ydlidar_ros2_driver_node", output="screen",
             parameters=[LaunchConfiguration("parameter_file"), {
                 "port": LaunchConfiguration("port"),
                 "frame_id": LaunchConfiguration("frame_id"),
                 "use_sim_time": LaunchConfiguration("use_sim_time"),
             }]),
    ])
