import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NODE = ROOT / "mecanum_base_bridge/sim_eval_wheel_imu_ingress_node.py"


def test_sim_time_is_forced_and_verified_before_any_ros_endpoint_creation():
    source = NODE.read_text(encoding="utf-8")
    tree = ast.parse(source)
    assert "from rclpy.parameter import Parameter" in source
    init = next(
        node for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "__init__"
    )
    calls = [
        node for node in ast.walk(init)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    ]
    set_call = next(call for call in calls if call.func.attr == "set_parameters_atomically")
    assert set_call.lineno > next(call.lineno for call in calls if call.func.attr == "__init__")
    assert ast.unparse(set_call.args[0]) == "[Parameter('use_sim_time', value=True)]"
    endpoint_lines = [
        call.lineno for call in calls
        if call.func.attr in {"create_publisher", "create_subscription"}
    ]
    assert endpoint_lines and set_call.lineno < min(endpoint_lines)
    assert any(isinstance(node, ast.Attribute) and node.attr == "successful" for node in ast.walk(init))
    assert "self.get_parameter(\"use_sim_time\").value is not True" in source
    assert "raise RuntimeError" in source
    assert "has_parameter" not in source
    assert "declare_parameter" not in source


def test_node_owns_only_two_staging_subscriptions_and_two_canonical_publishers():
    tree = ast.parse(NODE.read_text(encoding="utf-8"))
    endpoints = {"publisher": [], "subscription": []}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr == "create_publisher":
            endpoints["publisher"].append(ast.literal_eval(node.args[1]))
        elif node.func.attr == "create_subscription":
            endpoints["subscription"].append(ast.literal_eval(node.args[1]))
    assert set(endpoints["publisher"]) == {"/wheel/odometry_raw", "/imu/data"}
    assert set(endpoints["subscription"]) == {
        "/sim_eval/wheel_joint_states", "/sim_eval/imu_raw"
    }
    source = NODE.read_text(encoding="utf-8")
    assert "/cmd_vel" not in source
    assert "/ground_truth/odom" not in source
    assert "TransformBroadcaster" not in source
    assert "ros_gz_bridge" not in source
    imports = {
        alias.name.split(".", 1)[0]
        for node in ast.walk(tree) if isinstance(node, ast.Import)
        for alias in node.names
    }
    imports.update(
        node.module.split(".", 1)[0]
        for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module
    )
    assert "tf2_ros" not in imports
    assert "ros_gz_bridge" not in imports
