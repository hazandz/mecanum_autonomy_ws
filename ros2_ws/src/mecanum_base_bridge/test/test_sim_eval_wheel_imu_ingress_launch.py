import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LAUNCH = ROOT / "launch/sim_eval_wheel_imu_ingress.launch.py"


def _calls(tree, name):
    return [node for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == name]


def _literal_keyword(call, name):
    for keyword in call.keywords:
        if keyword.arg == name and isinstance(keyword.value, ast.Constant):
            return keyword.value.value
    return None


def test_launch_declares_partition_and_sim_time_and_sets_partition_from_argument():
    source = LAUNCH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    declarations = _calls(tree, "DeclareLaunchArgument")
    found = {}
    for call in declarations:
        if call.args and isinstance(call.args[0], ast.Constant):
            found[call.args[0].value] = _literal_keyword(call, "default_value")
    assert found["gz_partition"] == "sim_eval"
    assert found["use_sim_time"] == "true"
    env_calls = _calls(tree, "SetEnvironmentVariable")
    assert len(env_calls) == 1
    env = env_calls[0]
    assert isinstance(env.args[0], ast.Constant) and env.args[0].value == "GZ_PARTITION"
    assert isinstance(env.args[1], ast.Call) and isinstance(env.args[1].func, ast.Name)
    assert env.args[1].func.id == "LaunchConfiguration"
    assert isinstance(env.args[1].args[0], ast.Constant) and env.args[1].args[0].value == "gz_partition"
    assert 'if not partition or not partition.strip()' in source
    assert 'use_sim_time != "true"' in source


def test_launch_starts_only_bridge_and_ingress_and_uses_installed_config_file():
    source = LAUNCH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    node_calls = _calls(tree, "Node")
    assert len(node_calls) == 2
    actual = {(_literal_keyword(call, "package"), _literal_keyword(call, "executable")) for call in node_calls}
    assert actual == {
        ("ros_gz_bridge", "parameter_bridge"),
        ("mecanum_base_bridge", "sim_eval_wheel_imu_ingress"),
    }
    assert 'FindPackageShare("mecanum_base_bridge")' in source
    assert '"config",\n    "bridge",\n    "sim_eval_wheel_imu_ingress.runtime.yaml"' in source
    assert '{"config_file": RUNTIME_CONFIG}' in source
    assert '{"use_sim_time": True}' in source
    forbidden = ("robot_localization", "nav2", "amcl", "map_server", "static_transform_publisher", "tf2_ros", "ros_gz_sim", "spawn_entity", "/odom", "/ground_truth/odom", "/tf", "/cmd_vel")
    assert all(token not in source.lower() for token in forbidden)
    assert "create_publisher" not in source and "create_subscription" not in source
