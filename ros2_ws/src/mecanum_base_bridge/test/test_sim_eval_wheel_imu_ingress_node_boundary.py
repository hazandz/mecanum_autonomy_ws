import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NODE = ROOT / "mecanum_base_bridge/sim_eval_wheel_imu_ingress_node.py"


def test_effective_sim_time_is_forced_and_verified_before_any_ros_endpoint():
    source = NODE.read_text(encoding="utf-8")
    tree = ast.parse(source)
    assert "from rclpy.parameter import Parameter" in source
    set_lines = [node.lineno for node in ast.walk(tree) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Attribute) and node.func.attr == "set_parameters_atomically"]
    publisher_lines = [node.lineno for node in ast.walk(tree) if isinstance(node, ast.Call)
                       and isinstance(node.func, ast.Attribute) and node.func.attr == "create_publisher"]
    subscription_lines = [node.lineno for node in ast.walk(tree) if isinstance(node, ast.Call)
                          and isinstance(node.func, ast.Attribute) and node.func.attr == "create_subscription"]
    assert len(set_lines) == 1
    assert len(publisher_lines) == 2 and len(subscription_lines) == 2
    assert set_lines[0] < min(publisher_lines + subscription_lines)
    assert 'Parameter("use_sim_time", value=True)' in source
    assert "if not result.successful:" in source
    assert 'self.get_parameter("use_sim_time").value is not True' in source
    assert "raise RuntimeError" in source
    assert "has_parameter" not in source
    assert "declare_parameter" not in source


def test_node_boundary_is_limited_to_two_staging_inputs_and_two_outputs_without_tf_or_bridge():
    source = NODE.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".", 1)[0])
    assert imports.isdisjoint({"tf2_ros", "ros_gz_bridge", "ros_gz_sim", "gazebo", "gz"})
    assert source.count("create_publisher(") == 2
    assert source.count("create_subscription(") == 2
    assert '"/wheel/odometry_raw"' in source
    assert '"/imu/data"' in source
    assert '"/sim_eval/wheel_joint_states"' in source
    assert '"/sim_eval/imu_raw"' in source
    assert "TransformBroadcaster" not in source
    for forbidden in ('"/cmd_vel"', '"/odom"', '"/ground_truth/odom"'):
        assert forbidden not in source


def test_wheel_emulator_uses_sequence_protocol_without_generator_coercion():
    source = (ROOT / "mecanum_base_bridge/sim_eval_wheel_odometry_emulator.py").read_text(encoding="utf-8")
    assert "from collections.abc import Sequence" in source
    assert "isinstance(value, Sequence)" in source
    assert "type(velocities) in (list, tuple)" not in source
    assert "list(velocities)" not in source
