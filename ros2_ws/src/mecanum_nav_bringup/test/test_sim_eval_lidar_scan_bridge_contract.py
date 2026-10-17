"""Offline tests for the static sim_eval Gazebo-to-ROS scan bridge contract."""

import ast
from copy import deepcopy
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest
import yaml

from mecanum_nav_bringup import sim_eval_lidar_scan_bridge_contract as contract


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PACKAGE_ROOT.parents[2]
YAML_PATH = PACKAGE_ROOT / "config/bridge/sim_eval_lidar_scan_bridge.static.yaml"
GAZEBO_PATH = REPO_ROOT / "ros2_ws/src/ROBOT_URDF_final_description/urdf/ROBOT_URDF_final.gazebo"
XACRO_PATH = REPO_ROOT / "ros2_ws/src/ROBOT_URDF_final_description/urdf/ROBOT_URDF_final.xacro"


def _descriptor():
    return yaml.safe_load(YAML_PATH.read_text(encoding="utf-8"))


def _tamper(path, value):
    result = deepcopy(contract.STATIC_DESCRIPTOR)
    current = result
    for part in path[:-1]:
        current = current[part]
    current[path[-1]] = value
    return result


def _has_expected_lidar_source(root):
    gazebo_blocks = [
        node for node in root.findall("gazebo")
        if node.get("reference") == "lidar_frame"
    ]
    if len(gazebo_blocks) != 1:
        return False
    sensors = gazebo_blocks[0].findall("sensor")
    if len(sensors) != 1:
        return False
    sensor = sensors[0]
    return (
        sensor.get("name") == "YDLIDAR_X3_PRO"
        and sensor.get("type") == "gpu_lidar"
        and len(sensor.findall("frame_id")) == 1
        and sensor.findtext("frame_id") == "lidar_frame"
        and len(sensor.findall("gz_frame_id")) == 1
        and sensor.findtext("gz_frame_id") == "lidar_frame"
    )


def test_yaml_has_exact_static_contract_and_validator_accepts_it():
    descriptor = _descriptor()
    assert descriptor == contract.STATIC_DESCRIPTOR
    assert descriptor["schema"] == "mecanum_sim_eval_lidar_scan_bridge_static/v1"
    assert descriptor["profile"] == "sim_eval"
    assert descriptor["classification"] == "STATIC_CONTRACT_ONLY"
    assert descriptor["runtime_eligible"] is False
    assert descriptor["use_sim_time"] is True
    assert contract.validate_sim_eval_lidar_scan_bridge_descriptor(descriptor) is None


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("ros_output", "topic"), "/other_scan"),
        (("ros_output", "ros_message_type"), "sensor_msgs/msg/Imu"),
        (("transport_binding", "gz_message_type"), "gz.msgs.PointCloudPacked"),
        (("ros_output", "required_header_frame_id"), "base_link"),
        (("ros_output", "publishes_tf"), True),
        (("tf_contract", "bridge_publishes_tf"), True),
        (("transport_binding", "gz_transport_endpoint"), "/world/default/model/robot/link/lidar_frame/sensor/scan/scan"),
        (("transport_binding", "bridge_implementation"), "ros_gz_bridge parameter_bridge"),
        (("transport_binding", "observed_scan_timing"), 6.0),
        (("runtime_eligible",), True),
        (("prohibitions", "forbidden_ros_topics"), ["/ground_truth/odom"]),
        (("prohibitions", "forbidden_frame_aliases"), ["rplidar_link"]),
    ],
)
def test_validator_rejects_tampered_contract_values(path, value):
    with pytest.raises(contract.StaticLidarBridgeContractError):
        contract.validate_sim_eval_lidar_scan_bridge_descriptor(_tamper(path, value))


def test_validator_rejects_missing_and_unknown_fields():
    missing = deepcopy(contract.STATIC_DESCRIPTOR)
    del missing["transport_binding"]["gz_transport_endpoint"]
    with pytest.raises(contract.StaticLidarBridgeContractError):
        contract.validate_sim_eval_lidar_scan_bridge_descriptor(missing)

    unknown = deepcopy(contract.STATIC_DESCRIPTOR)
    unknown["unexpected"] = "value"
    with pytest.raises(contract.StaticLidarBridgeContractError):
        contract.validate_sim_eval_lidar_scan_bridge_descriptor(unknown)


def test_sdf_static_source_matches_declared_sensor_provenance():
    root = ET.parse(GAZEBO_PATH).getroot()
    gazebo = [node for node in root.findall("gazebo") if node.get("reference") == "lidar_frame"]
    assert len(gazebo) == 1
    sensors = gazebo[0].findall("sensor")
    assert len(sensors) == 1
    sensor = sensors[0]
    assert sensor.get("name") == "YDLIDAR_X3_PRO"
    assert sensor.get("type") == "gpu_lidar"
    assert sensor.findtext("topic") == "scan"
    assert len(sensor.findall("frame_id")) == 1
    assert sensor.findtext("frame_id") == "lidar_frame"
    assert len(sensor.findall("gz_frame_id")) == 1
    assert sensor.findtext("gz_frame_id") == "lidar_frame"
    assert _has_expected_lidar_source(root)
    assert float(sensor.findtext("update_rate")) == 6.0
    assert int(sensor.findtext("ray/scan/horizontal/samples")) == 500
    assert float(sensor.findtext("ray/range/min")) == 0.10
    assert float(sensor.findtext("ray/range/max")) == 8.00


@pytest.mark.parametrize(
    "mutation",
    [
        "remove_frame_id",
        "remove_gz_frame_id",
        "wrong_frame_id",
        "wrong_gz_frame_id",
        "duplicate_frame_id",
        "duplicate_gz_frame_id",
        "wrong_sensor_name",
        "wrong_gazebo_reference",
        "frame_tags_on_different_sensor",
    ],
)
def test_sdf_lidar_source_rejects_invalid_dual_frame_contract(mutation):
    root = ET.parse(GAZEBO_PATH).getroot()
    gazebo = [node for node in root.findall("gazebo") if node.get("reference") == "lidar_frame"]
    sensor = gazebo[0].findall("sensor")[0]
    if mutation == "remove_frame_id":
        sensor.remove(sensor.find("frame_id"))
    elif mutation == "remove_gz_frame_id":
        sensor.remove(sensor.find("gz_frame_id"))
    elif mutation == "wrong_frame_id":
        sensor.find("frame_id").text = "ROBOT_URDF_final/base_link/YDLIDAR_X3_PRO"
    elif mutation == "wrong_gz_frame_id":
        sensor.find("gz_frame_id").text = "sensor_frame"
    elif mutation == "duplicate_frame_id":
        ET.SubElement(sensor, "frame_id").text = "lidar_frame"
    elif mutation == "duplicate_gz_frame_id":
        ET.SubElement(sensor, "gz_frame_id").text = "lidar_frame"
    elif mutation == "wrong_sensor_name":
        sensor.set("name", "other_lidar")
    elif mutation == "wrong_gazebo_reference":
        gazebo[0].set("reference", "base_link")
    elif mutation == "frame_tags_on_different_sensor":
        sensor.remove(sensor.find("frame_id"))
        sensor.remove(sensor.find("gz_frame_id"))
        other_sensor = ET.SubElement(gazebo[0], "sensor", name="other_lidar", type="gpu_lidar")
        ET.SubElement(other_sensor, "frame_id").text = "lidar_frame"
        ET.SubElement(other_sensor, "gz_frame_id").text = "lidar_frame"
    assert not _has_expected_lidar_source(root)


def test_xacro_keeps_direct_fixed_base_to_lidar_edge():
    root = ET.parse(XACRO_PATH).getroot()
    joints = [
        joint
        for joint in root.findall("joint")
        if joint.get("type") == "fixed"
        and joint.find("parent") is not None
        and joint.find("child") is not None
        and joint.find("parent").get("link") == "base_link"
        and joint.find("child").get("link") == "lidar_frame"
    ]
    assert len(joints) == 1


def test_module_and_test_have_no_ros_gazebo_runtime_imports_or_graph_symbols():
    forbidden_import_roots = {
        "rclpy", "launch", "launch_ros", "tf2_ros", "ros_gz_bridge",
        "ros_gz_sim", "gz", "gazebo", "sensor_msgs", "nav_msgs",
    }
    graph_symbols = {
        "Node", "LifecycleNode", "LaunchDescription", "create_node",
        "create_publisher", "create_subscription", "Publisher", "Subscriber",
        "TransformBroadcaster", "Timer", "subprocess", "Popen", "socket",
    }
    for path in (
        PACKAGE_ROOT / "mecanum_nav_bringup/sim_eval_lidar_scan_bridge_contract.py",
        Path(__file__),
    ):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported = {alias.name.split(".", 1)[0] for alias in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported = {node.module.split(".", 1)[0]}
            else:
                imported = set()
            assert not imported.intersection(forbidden_import_roots)
            if isinstance(node, ast.Name):
                assert node.id not in graph_symbols
            if isinstance(node, ast.Attribute):
                assert node.attr not in graph_symbols
