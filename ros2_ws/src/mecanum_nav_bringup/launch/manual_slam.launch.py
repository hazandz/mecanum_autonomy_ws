"""Hardware MANUAL_SLAM source candidate. SLAM Toolbox stays in a second terminal."""
from __future__ import annotations

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, OpaqueFunction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import LifecycleNode, Node
from mecanum_base_bridge.hardware_config import (
    communication_config_valid, load_manifest, manual_slam_drive_ratios,
    wheel_geometry,
)


def _required(context, name: str) -> str:
    value = LaunchConfiguration(name).perform(context).strip()
    if not value:
        raise RuntimeError(f"manual_slam requires launch argument: {name}")
    return value


def _actions(context):
    manifest = _required(context, "hardware_manifest")
    serial_device = _required(context, "serial_device")
    lidar_port = _required(context, "lidar_port")
    ekf_params = _required(context, "ekf_params_file")
    lidar_params = _required(context, "lidar_parameter_file")
    required_files = {
        "hardware_manifest": manifest,
        "ekf_params_file": ekf_params,
        "lidar_parameter_file": lidar_params,
    }
    for label, path in required_files.items():
        if not os.path.isfile(path):
            raise RuntimeError(f"manual_slam {label} is not a file: {path}")
    try:
        manifest_data = load_manifest(manifest)
        geometry = wheel_geometry(manifest_data)
        ratios = manual_slam_drive_ratios(manifest_data)
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise RuntimeError(f"MANUAL_SLAM hardware manifest is unresolved: {error}") from error
    if (not communication_config_valid(manifest_data)
            or geometry["ticks_per_wheel_revolution"] != 937.2
            or ratios["motor_to_gearbox_output_ratio"] != 21.3
            or ratios["wheel_rpm_per_gearbox_output_rpm"] != 1.0):
        raise RuntimeError("MANUAL_SLAM manifest does not match the selected bench profile")
    transforms = {}
    for name in ("lidar_x", "lidar_y", "lidar_z", "lidar_roll", "lidar_pitch", "lidar_yaw",
                 "imu_x", "imu_y", "imu_z", "imu_roll", "imu_pitch", "imu_yaw"):
        value = _required(context, name)
        try:
            transforms[name] = float(value)
        except ValueError as error:
            raise RuntimeError(f"manual_slam {name} must be finite numeric") from error
        if not (-float("inf") < transforms[name] < float("inf")):
            raise RuntimeError(f"manual_slam {name} must be finite numeric")

    share_bridge = get_package_share_directory("mecanum_base_bridge")
    share_bringup = get_package_share_directory("mecanum_nav_bringup")
    lidar_launch = os.path.join(share_bringup, "launch", "manual_slam_ydlidar_x3.launch.py")
    imu_launch = os.path.join(share_bringup, "launch", "manual_slam_bno055_i2c.launch.py")
    for wrapper in (lidar_launch, imu_launch):
        if not os.path.isfile(wrapper):
            raise RuntimeError(f"MANUAL_SLAM sensor wrapper missing: {wrapper}")
    joy_config = os.path.join(share_bridge, "config", "slam_manual_joy.yaml")
    joy_device_id = int(LaunchConfiguration("joy_device_id").perform(context))
    joy_rate = float(LaunchConfiguration("joy_autorepeat_rate").perform(context))
    if joy_rate <= 0.0:
        raise RuntimeError("joy_autorepeat_rate must be positive for Joy timeout operation")

    lidar_arg_map = {
        LaunchConfiguration("lidar_port_arg").perform(context): lidar_port,
        LaunchConfiguration("lidar_frame_arg").perform(context): "lidar_frame",
        LaunchConfiguration("lidar_use_sim_time_arg").perform(context): "false",
        "parameter_file": lidar_params,
    }
    imu_arg_map = {
        LaunchConfiguration("imu_bus_arg").perform(context): LaunchConfiguration("imu_bus"),
        LaunchConfiguration("imu_address_arg").perform(context): LaunchConfiguration("imu_address"),
        LaunchConfiguration("imu_frame_arg").perform(context): "imu_link",
        LaunchConfiguration("imu_use_sim_time_arg").perform(context): "false",
    }
    for mapping in (lidar_arg_map, imu_arg_map):
        if any(not key for key in mapping):
            raise RuntimeError("driver launch argument names must be non-empty")

    return [
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(lidar_launch), launch_arguments=lidar_arg_map.items()),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(imu_launch), launch_arguments=imu_arg_map.items()),
        Node(
            package="joy", executable="joy_node", name="joy_node", output="screen",
            parameters=[{
                "use_sim_time": False,
                "device_id": joy_device_id,
                "deadzone": 0.0,
                "autorepeat_rate": joy_rate,
                "coalesce_interval_ms": 1,
                "sticky_buttons": False,
            }],
        ),
        Node(
            package="mecanum_base_bridge", executable="slam_manual_joy",
            name="slam_manual_joy", output="screen",
            parameters=[joy_config, {
                "use_sim_time": False,
                "control_mode": "MANUAL_SLAM",
                "manual_slam_selected": True,
                "hardware_manifest": manifest,
                "profile_name": "pid4_experimental_1400cps",
                "owner_design_output_rpm": 172.0,
                "motor_to_gearbox_output_ratio": 21.3,
                "wheel_rpm_per_gearbox_output_rpm": 1.0,
                "experimental_max_wheel_target_cps": 1400.0,
                "joy_timeout_s": 0.25,
            }],
        ),
        Node(
            package="mecanum_base_bridge", executable="mecanum_uart_bridge",
            name="mecanum_uart_bridge", output="screen",
            parameters=[{
                "use_sim_time": False,
                "serial_device": serial_device,
                "hardware_manifest": manifest,
                "heartbeat_topic": "/mcu/heartbeat",
                "lifecycle_timeout_s": 0.6,
                "manual_slam_bench_unmonitored_estop": True,
            }],
        ),
        LifecycleNode(
            package="mecanum_nav_rl", executable="safety_lifecycle",
            name="safety_lifecycle", namespace="/", output="screen",
            parameters=[{"use_sim_time": False}],
        ),
        Node(
            package="robot_localization", executable="ekf_node", name="ekf_filter_node",
            output="screen", parameters=[ekf_params, {"use_sim_time": False}],
            remappings=[("odometry/filtered", "/odometry/filtered")],
        ),
        Node(
            package="tf2_ros", executable="static_transform_publisher",
            name="base_to_lidar_tf", output="screen",
            arguments=["--x", str(transforms["lidar_x"]),
                       "--y", str(transforms["lidar_y"]),
                       "--z", str(transforms["lidar_z"]),
                       "--roll", str(transforms["lidar_roll"]),
                       "--pitch", str(transforms["lidar_pitch"]),
                       "--yaw", str(transforms["lidar_yaw"]),
                       "--frame-id", "base_link", "--child-frame-id", "lidar_frame"],
            parameters=[{"use_sim_time": False}],
        ),
        Node(
            package="tf2_ros", executable="static_transform_publisher",
            name="base_to_imu_tf", output="screen",
            arguments=["--x", str(transforms["imu_x"]),
                       "--y", str(transforms["imu_y"]),
                       "--z", str(transforms["imu_z"]),
                       "--roll", str(transforms["imu_roll"]),
                       "--pitch", str(transforms["imu_pitch"]),
                       "--yaw", str(transforms["imu_yaw"]),
                       "--frame-id", "base_link", "--child-frame-id", "imu_link"],
            parameters=[{"use_sim_time": False}],
        ),
    ]


def generate_launch_description():
    args = [
        ("serial_device", ""),
        ("hardware_manifest", ""),
        ("ekf_params_file", ""),
        ("lidar_parameter_file", ""),
        ("lidar_port", ""),
        ("lidar_port_arg", "port"),
        ("lidar_frame_arg", "frame_id"),
        ("lidar_use_sim_time_arg", "use_sim_time"),
        ("imu_bus", "1"),
        ("imu_address", "41"),
        ("imu_bus_arg", "i2c_bus"),
        ("imu_address_arg", "i2c_addr"),
        ("imu_frame_arg", "frame_id"),
        ("imu_use_sim_time_arg", "use_sim_time"),
        ("joy_device_id", "0"),
        ("joy_autorepeat_rate", "20.0"),
    ]
    args.extend((name, "") for name in (
        "lidar_x", "lidar_y", "lidar_z", "lidar_roll", "lidar_pitch", "lidar_yaw",
        "imu_x", "imu_y", "imu_z", "imu_roll", "imu_pitch", "imu_yaw",
    ))
    return LaunchDescription([
        *(DeclareLaunchArgument(name, default_value=value) for name, value in args),
        OpaqueFunction(function=_actions),
    ])
