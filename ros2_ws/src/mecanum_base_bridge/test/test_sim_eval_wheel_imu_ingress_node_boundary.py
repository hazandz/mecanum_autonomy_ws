import ast
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
NODE = ROOT / "mecanum_base_bridge/sim_eval_wheel_imu_ingress_node.py"
GAZEBO = ROOT.parents[0] / "ROBOT_URDF_final_description/urdf/ROBOT_URDF_final.gazebo"
SDF = ROOT.parents[0] / "ROBOT_URDF_final_description/launch/tugbot_depot.sdf"


def test_gazebo_imu_sensor_and_world_imu_system_are_exactly_declared():
    root = ET.parse(GAZEBO).getroot()
    matches = []
    for gazebo in root.findall("gazebo"):
        for sensor in gazebo.findall("sensor"):
            if sensor.get("name") == "sim_eval_base_imu":
                matches.append((gazebo, sensor))
    assert len(matches) == 1
    parent, sensor = matches[0]
    assert parent.get("reference") == "base_link"
    assert sensor.get("type") == "imu"
    assert sensor.findtext("pose") == "0 0 0 0 0 0"
    assert sensor.findtext("always_on") == "true"
    assert float(sensor.findtext("update_rate")) == 50.0
    assert sensor.findtext("topic") == "/sim_eval/imu/raw"
    sdf = ET.parse(SDF).getroot()
    world = sdf.find("world")
    assert len(world.findall('plugin[@filename="gz-sim-imu-system"]')) == 1
    assert world.find('plugin[@filename="gz-sim-imu-system"]').get("name") == "gz::sim::systems::Imu"


def test_runtime_node_has_only_authorized_endpoints_and_no_bridge_tf_or_other_io():
    tree = ast.parse(NODE.read_text(encoding="utf-8"))
    forbidden_imports = {"tf2_ros", "ros_gz_bridge", "ros_gz_sim", "gz", "gazebo"}
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".")[0])
    assert not (imports & forbidden_imports)
    publishers = []
    subscriptions = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr == "create_publisher":
                publishers.append(ast.literal_eval(node.args[1]))
            if node.func.attr == "create_subscription":
                subscriptions.append(ast.literal_eval(node.args[1]))
    assert publishers == ["/wheel/odometry_raw", "/imu/data"]
    assert subscriptions == ["/sim_eval/wheel_joint_states", "/sim_eval/imu_raw"]
    sim_time_declarations = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "declare_parameter"
        and len(node.args) >= 2
        and ast.literal_eval(node.args[0]) == "use_sim_time"
    ]
    assert len(sim_time_declarations) == 1
    assert ast.literal_eval(sim_time_declarations[0].args[1]) is True
    literals = {node.value for node in ast.walk(tree) if isinstance(node, ast.Constant) and isinstance(node.value, str)}
    for forbidden in ("/cmd_vel", "/odom", "/ground_truth/odom", "TransformBroadcaster", "tf2_ros", "ros_gz_bridge"):
        assert forbidden not in literals
    called_attributes = {
        node.func.attr for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert "create_timer" not in called_attributes


class ColconIngressBoundaryTests(unittest.TestCase):
    """Expose static XML/AST boundaries to ament_python's unittest runner."""

    def test_gazebo_source_boundary(self):
        test_gazebo_imu_sensor_and_world_imu_system_are_exactly_declared()

    def test_node_endpoint_and_import_boundary(self):
        test_runtime_node_has_only_authorized_endpoints_and_no_bridge_tf_or_other_io()
