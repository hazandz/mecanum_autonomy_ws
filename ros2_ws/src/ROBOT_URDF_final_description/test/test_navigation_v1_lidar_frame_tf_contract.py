import ast
import hashlib
from pathlib import Path
import re
import xml.etree.ElementTree as ET


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
XACRO_PATH = PACKAGE_ROOT / "urdf" / "ROBOT_URDF_final.xacro"
GAZEBO_PATH = PACKAGE_ROOT / "urdf" / "ROBOT_URDF_final.gazebo"
LAUNCH_PATH = PACKAGE_ROOT / "launch" / "navigation_v1_robot_state_publisher.launch.py"


def _xml_root(path):
    return ET.parse(path).getroot()


def test_xacro_is_well_formed_and_defines_one_canonical_direct_fixed_edge():
    root = _xml_root(XACRO_PATH)
    links = [element for element in root.findall("link") if element.get("name") == "lidar_frame"]
    lidar_named_links = [
        element.get("name")
        for element in root.findall("link")
        if "lidar" in element.get("name", "").lower()
    ]
    assert len(links) == 1
    assert lidar_named_links == ["lidar_frame"]

    edges = []
    for joint in root.findall("joint"):
        parent = joint.find("parent")
        child = joint.find("child")
        if parent is not None and child is not None:
            if parent.get("link") == "base_link" and child.get("link") == "lidar_frame":
                edges.append(joint)

    assert len(edges) == 1
    assert edges[0].get("type") == "fixed"
    origin = edges[0].find("origin")
    assert origin is not None
    assert origin.get("xyz") == "-0.031765 0 0.140"
    assert origin.get("rpy") == "0 0 0"
    assert "RPLiDAR_A1M8_1" not in XACRO_PATH.read_text(encoding="utf-8")


def test_target_sources_use_only_literal_lidar_frame_without_alias_or_bridge():
    sources = [
        XACRO_PATH.read_text(encoding="utf-8"),
        GAZEBO_PATH.read_text(encoding="utf-8"),
        LAUNCH_PATH.read_text(encoding="utf-8"),
    ]
    joined = "\n".join(sources)
    for forbidden in (
        "RPLiDAR_A1M8_1",
        "base_scan",
        "rplidar_link",
        "static_transform_publisher",
        "tf_bridge",
        "frame_alias",
    ):
        assert forbidden not in joined

    root = _xml_root(XACRO_PATH)
    lidar_links = [
        element.get("name")
        for element in root.findall("link")
        if re.search(r"lidar|scan", element.get("name", ""), re.IGNORECASE)
    ]
    assert lidar_links == ["lidar_frame"]


def test_gazebo_source_has_exact_static_ydlidar_x3_pro_ray_sensor():
    root = _xml_root(GAZEBO_PATH)
    references = [element for element in root.findall("gazebo") if element.get("reference") == "lidar_frame"]
    assert len(references) == 1
    assert len([sensor for sensor in root.findall(".//sensor") if sensor.get("name") == "YDLIDAR_X3_PRO"]) == 1
    sensors = references[0].findall("sensor")
    assert len(sensors) == 1
    sensor = sensors[0]
    assert sensor.attrib == {"name": "YDLIDAR_X3_PRO", "type": "gpu_lidar"}
    assert [child.tag for child in sensor] == [
        'frame_id', 'gz_frame_id', 'topic', 'update_rate', 'ray'
    ]
    assert sensor.findtext('frame_id') == 'lidar_frame'
    assert sensor.findtext('gz_frame_id') == 'lidar_frame'
    assert sensor.findtext("topic") == "scan"
    assert sensor.findtext("update_rate") == "6.0"

    ray = sensor.find("ray")
    assert ray is not None
    assert [child.tag for child in ray] == ["scan", "range"]
    scan = ray.find("scan")
    assert scan is not None
    assert [child.tag for child in scan] == ["horizontal"]
    horizontal = scan.find("horizontal")
    assert horizontal is not None
    assert [child.tag for child in horizontal] == ["samples", "resolution", "min_angle", "max_angle"]
    assert horizontal.findtext("samples") == "500"
    assert horizontal.findtext("resolution") == "1"
    assert horizontal.findtext("min_angle") == "-3.141592653589793"
    assert horizontal.findtext("max_angle") == "3.141592653589793"

    range_element = ray.find("range")
    assert range_element is not None
    assert [child.tag for child in range_element] == ["min", "max"]
    assert range_element.findtext("min") == "0.10"
    assert range_element.findtext("max") == "8.00"
    assert range_element.find("resolution") is None
    assert scan.find("vertical") is None

    subtree = ET.tostring(sensor, encoding="unicode").lower()
    for forbidden in (
        'pose', 'plugin', 'tf', 'noise', 'always_on', 'visualize',
        "vertical", "rplidar_a1m8_1", "base_scan", "rplidar_link",
        "static_transform_publisher", "tf_bridge", "frame_alias",
        "ros_gz_bridge", "ros_gz", "sensor_msgs", "laserscan", "profile",
        "config_hash", "resolvedconfig", "nav2", "amcl", "robot_localization",
        "runtime_approved",
    ):
        assert forbidden not in subtree


def test_xacro_and_robot_state_publisher_launch_are_unchanged_dependencies():
    assert hashlib.sha256(XACRO_PATH.read_bytes()).hexdigest() == (
        "d80f46f3b5f273257072d800b9ba0b34c763128bfeefc32959363babf106cc0d"
    )
    assert hashlib.sha256(LAUNCH_PATH.read_bytes()).hexdigest() == (
        "b5c939ed662b5f789d008dd34777363ffeb5bbc373b596e97b75c1e097dcb511"
    )


def test_launch_source_prepares_only_robot_state_publisher_from_canonical_xacro():
    source = LAUNCH_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_modules = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported_modules.update(
        node.module.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    )
    assert imported_modules == {"launch", "launch_ros"}

    node_calls = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "Node"
    ]
    assert len(node_calls) == 1
    node_keywords = {keyword.arg: keyword.value for keyword in node_calls[0].keywords}
    assert ast.literal_eval(node_keywords["package"]) == "robot_state_publisher"
    assert ast.literal_eval(node_keywords["executable"]) == "robot_state_publisher"
    assert "ROBOT_URDF_final_description" in source
    assert "ROBOT_URDF_final.xacro" in source
    for forbidden in (
        "static_transform_publisher",
        "nav2",
        "amcl",
        "robot_localization",
        "map_server",
        "lifecycle_manager",
        "gazebo",
        "remappings",
        "namespace=",
        "config_hash",
        "ResolvedConfig",
    ):
        assert forbidden.lower() not in source.lower()


def test_sources_make_no_profile_map_world_gate_or_runtime_approval_claim():
    target_sources = "\n".join(
        path.read_text(encoding="utf-8") for path in (XACRO_PATH, GAZEBO_PATH, LAUNCH_PATH)
    ).lower()
    for forbidden in (
        "resolvedconfig",
        "config_hash",
        "map_approval",
        "world_frame",
        "gate b",
        "runtime_approved",
    ):
        assert forbidden not in target_sources


def test_static_test_source_does_not_import_or_execute_ros_runtime():
    test_path = Path(__file__)
    tree = ast.parse(test_path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported = {alias.name.split(".")[0] for alias in node.names}
            assert imported.isdisjoint({"rclpy", "launch", "launch_ros", "gazebo", "xacro"})
        elif isinstance(node, ast.ImportFrom):
            assert (node.module or "").split(".")[0] not in {
                "rclpy", "launch", "launch_ros", "gazebo", "xacro"
            }
