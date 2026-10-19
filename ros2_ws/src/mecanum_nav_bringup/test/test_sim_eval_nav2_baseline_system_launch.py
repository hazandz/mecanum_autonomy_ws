"""Static-only import and ownership checks for the consolidated launch."""
from pathlib import Path

from launch import LaunchDescription

ROOT = Path(__file__).resolve().parents[4]


def test_composite_launch_imports_without_starting_processes(monkeypatch, tmp_path) -> None:
    import importlib.util

    monkeypatch.setenv("ROS_HOME", str(tmp_path / "ros_home"))
    monkeypatch.setenv("ROS_LOG_DIR", str(tmp_path / "ros_log"))

    path = ROOT / "ros2_ws/src/mecanum_nav_bringup/launch/sim_eval_nav2_baseline_system.launch.py"
    spec = importlib.util.spec_from_file_location("sim_eval_nav2_baseline_system", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    description = module.generate_launch_description()
    assert isinstance(description, LaunchDescription)
    # OpaqueFunction is left unevaluated, so no process is launched by this test.
    assert len(description.entities) == 5


def test_system_launch_has_exact_command_route_and_safety_executables() -> None:
    source = (ROOT / "ros2_ws/src/mecanum_nav_bringup/launch/sim_eval_nav2_baseline_system.launch.py").read_text()
    assert '("cmd_vel", "/mecanum/nav2_candidate_cmd")' in source
    assert 'executable="safety_lifecycle"' in source
    assert 'executable="safety_supervisor"' in source
    assert 'executable="final_twist_publisher"' in source
    assert "sim_eval_tf_ekf_state_estimation.launch.py" in source
    assert "sim_eval_lidar_scan_bridge.runtime.yaml" in source
    assert "sim_eval_cmd_vel.runtime.yaml" in source
    assert "gazebo.launch.py" not in source
    assert "ground_truth" not in source
    assert '"/odom"' not in source
    assert '"/tf"' not in source


def test_map_localization_and_tf_ownership_are_declared_once() -> None:
    navigation = (ROOT / "ros2_ws/src/mecanum_nav_bringup/config/navigation/sim_eval_nav2_baseline.runtime.yaml").read_text()
    assert "topic_name: /map" in navigation
    assert "yaml_filename: artifacts/maps/warehouse_map2/map.yaml" in navigation
    assert "global_frame: map" in navigation
    assert "odom_topic: /odometry/filtered" in navigation
    ekf = (ROOT / "ros2_ws/src/mecanum_nav_bringup/config/state_estimation/ekf_sim.yaml").read_text()
    assert "world_frame: odom" in ekf
    assert "base_link_frame: base_link" in ekf
    amcl = (ROOT / "ros2_ws/src/mecanum_nav_bringup/config/localization/amcl_omni.yaml").read_text()
    assert "global_frame_id: map" in amcl
    assert "odom_frame_id: odom" in amcl
    assert "base_frame_id: base_link" in amcl
    xacro = (ROOT / "ros2_ws/src/ROBOT_URDF_final_description/urdf/ROBOT_URDF_final.xacro").read_text()
    assert "lidar_frame" in xacro
