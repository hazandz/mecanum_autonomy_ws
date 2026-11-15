from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
LAUNCH = ROOT / "ros2_ws/src/mecanum_nav_bringup/launch/manual_slam.launch.py"


def test_manual_slam_launch_has_only_explicit_direct_joy_route():
    source = LAUNCH.read_text()
    assert 'executable="slam_manual_joy"' in source
    assert '"control_mode": "MANUAL_SLAM"' in source
    assert '"manual_slam_selected": True' in source
    assert 'executable="mecanum_uart_bridge"' in source
    assert '"hardware_manifest": manifest' in source
    assert '"serial_device": serial_device' in source
    assert 'executable="safety_lifecycle"' in source
    assert 'executable="lifecycle_manager"' in source
    assert 'executable="safety_supervisor"' not in source
    assert 'executable="final_twist_publisher"' not in source
    assert "slam_toolbox" not in source


def test_manual_slam_launch_requires_real_paths_and_measured_sensor_transforms():
    source = LAUNCH.read_text()
    for argument in (
        "serial_device", "hardware_manifest", "ekf_params_file",
        "lidar_launch_file", "lidar_port", "imu_launch_file",
        "lidar_x", "lidar_y", "lidar_z", "lidar_roll", "lidar_pitch", "lidar_yaw",
        "imu_x", "imu_y", "imu_z", "imu_roll", "imu_pitch", "imu_yaw",
    ):
        assert f'"{argument}"' in source
    assert 'value = _required(context, name)' in source
    assert '"autorepeat_rate": joy_rate' in source
    assert '"joy_autorepeat_rate", "20.0"' in source
    assert '"use_sim_time": False' in source
