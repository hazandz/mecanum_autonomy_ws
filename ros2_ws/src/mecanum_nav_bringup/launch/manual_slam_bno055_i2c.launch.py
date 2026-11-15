"""BNO055 I2C wrapper for the Pi-side ROS driver."""
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument("i2c_bus", default_value="1"),
        DeclareLaunchArgument("i2c_address", default_value="41"),
        DeclareLaunchArgument("frame_id", default_value="imu_link"),
        DeclareLaunchArgument("use_sim_time", default_value="false"),
        Node(package="bno055", executable="bno055", name="bno055", output="screen",
             parameters=[{
                 "i2c_bus": LaunchConfiguration("i2c_bus"),
                 "i2c_address": LaunchConfiguration("i2c_address"),
                 "frame_id": LaunchConfiguration("frame_id"),
                 "data_query_frequency": 50,
                 "use_sim_time": LaunchConfiguration("use_sim_time"),
             }]),
    ])
