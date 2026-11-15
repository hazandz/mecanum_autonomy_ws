from pathlib import Path
import importlib.util

from launch import LaunchContext
from launch_ros.actions import LifecycleNode, Node


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
    assert "wheel_geometry(manifest_data)" in source
    assert 'geometry["ticks_per_wheel_revolution"] != 937.2' in source


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


def test_jazzy_actions_construct_with_lifecycle_namespace_and_joy_clock(monkeypatch, tmp_path):
    manifest = ROOT / (
        "artifacts/hardware/mecanum_f411_tb6612_ga25_370_rev_a/"
        "hardware_manifest_slam_manual_bench.yaml"
    )
    launch_file = LAUNCH
    ekf_file = tmp_path / "ekf.yaml"
    ekf_file.write_text("ekf_filter_node:\n  ros__parameters: {}\n")
    spec = importlib.util.spec_from_file_location("manual_slam_launch_test", LAUNCH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(
        module, "get_package_share_directory",
        lambda package: str(ROOT / "ros2_ws/src/mecanum_base_bridge"),
    )
    context = LaunchContext()
    args = {
        "serial_device": "/dev/null",
        "hardware_manifest": str(manifest),
        "ekf_params_file": str(ekf_file),
        "lidar_launch_file": str(launch_file),
        "imu_launch_file": str(launch_file),
        "lidar_port": "/dev/null",
        "lidar_port_arg": "port",
        "lidar_frame_arg": "frame_id",
        "lidar_use_sim_time_arg": "use_sim_time",
        "imu_bus": "1",
        "imu_address": "41",
        "imu_bus_arg": "i2c_bus",
        "imu_address_arg": "i2c_address",
        "imu_frame_arg": "frame_id",
        "imu_use_sim_time_arg": "use_sim_time",
        "joy_device_id": "0",
        "joy_autorepeat_rate": "20.0",
    }
    args.update({name: "0.0" for name in (
        "lidar_x", "lidar_y", "lidar_z", "lidar_roll", "lidar_pitch", "lidar_yaw",
        "imu_x", "imu_y", "imu_z", "imu_roll", "imu_pitch", "imu_yaw",
    )})
    context.launch_configurations.update(args)

    actions = module._actions(context)
    lifecycle = next(action for action in actions if isinstance(action, LifecycleNode))
    joy = next(action for action in actions
               if isinstance(action, Node) and action._Node__node_name == "joy_node")
    assert lifecycle._Node__node_name == "safety_lifecycle"
    assert lifecycle._Node__node_namespace == "/"
    assert any(
        key[0].text == "use_sim_time" and value is False
        for group in joy._Node__parameters for key, value in group.items()
    )
