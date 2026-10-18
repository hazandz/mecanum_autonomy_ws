"""Static launch topology checks; these tests never instantiate ROS launch."""

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SOURCE = ROOT / "ros2_ws/src/mecanum_nav_bringup/launch/sim_eval_tf_ekf_state_estimation.launch.py"


def test_composite_launch_only_composes_ingress_clock_and_one_ekf():
    text = SOURCE.read_text(encoding="utf-8")
    tree = ast.parse(text)
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
    nodes = [call for call in calls if isinstance(call.func, ast.Name) and call.func.id == "Node"]
    includes = [call for call in calls if isinstance(call.func, ast.Name) and call.func.id == "IncludeLaunchDescription"]
    assert len(nodes) == 2
    assert len(includes) == 1
    node_packages = []
    node_executables = []
    for node in nodes:
        keywords = {item.arg: item.value for item in node.keywords}
        node_packages.append(ast.literal_eval(keywords["package"]))
        node_executables.append(ast.literal_eval(keywords["executable"]))
    assert sorted(zip(node_packages, node_executables)) == sorted([
        ("ros_gz_bridge", "parameter_bridge"),
        ("robot_localization", "ekf_node"),
    ])
    assert "mecanum_base_bridge" in text
    assert "sim_eval_wheel_imu_ingress.launch.py" in text
    assert "EXPECTED_PARTITION = \"wp06_scan_probe_run_002\"" in text
    assert 'DeclareLaunchArgument("use_sim_time", default_value="true")' in text
    assert 'DeclareLaunchArgument("gz_partition", default_value=EXPECTED_PARTITION)' in text
    assert "SetEnvironmentVariable(\"GZ_PARTITION\"" in text
    assert "raise RuntimeError" in text
    for forbidden in (
        "robot_state_publisher", "gazebo.launch.py", "bootstrap.launch.py", "nav2", "amcl",
        "slam", "map_server", "static_transform_publisher", "cmd_vel", "tf2_ros",
    ):
        assert forbidden not in text.lower()


def test_launch_uses_installed_configs_and_forces_sim_time_for_both_nodes():
    text = SOURCE.read_text(encoding="utf-8")
    assert '"sim_eval_clock.runtime.yaml"' in text
    assert '"ekf_sim.yaml"' in text
    assert '"use_sim_time": True' in text
    assert '"use_sim_time": "true"' in text
    assert '"gz_partition": EXPECTED_PARTITION' in text
