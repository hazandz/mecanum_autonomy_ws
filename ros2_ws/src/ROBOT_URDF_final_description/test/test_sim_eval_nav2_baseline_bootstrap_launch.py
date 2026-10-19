"""Static import contract for the bootstrap; no launch execution occurs."""
from pathlib import Path

from launch import LaunchDescription

ROOT = Path(__file__).resolve().parents[4]


def test_bootstrap_launch_imports_without_starting_processes(monkeypatch, tmp_path) -> None:
    import importlib.util

    monkeypatch.setenv("ROS_HOME", str(tmp_path / "ros_home"))
    monkeypatch.setenv("ROS_LOG_DIR", str(tmp_path / "ros_log"))

    path = ROOT / "ros2_ws/src/ROBOT_URDF_final_description/launch/sim_eval_nav2_baseline_bootstrap.launch.py"
    spec = importlib.util.spec_from_file_location("sim_eval_nav2_baseline_bootstrap", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert isinstance(module.generate_launch_description(), LaunchDescription)


def test_bootstrap_requires_explicit_partition_and_map_initial_pose() -> None:
    path = ROOT / "ros2_ws/src/ROBOT_URDF_final_description/launch/sim_eval_nav2_baseline_bootstrap.launch.py"
    source = path.read_text(encoding="utf-8")
    for argument in ("gz_partition", "initial_pose_map_x", "initial_pose_map_y", "initial_pose_map_yaw"):
        assert f'DeclareLaunchArgument("{argument}")' in source
    assert 'SetEnvironmentVariable("GZ_PARTITION", EXPECTED_PARTITION)' in source
    assert 'package="robot_state_publisher"' in source
    assert "Map-frame initial pose" in source
    assert "world-frame transform" in source
