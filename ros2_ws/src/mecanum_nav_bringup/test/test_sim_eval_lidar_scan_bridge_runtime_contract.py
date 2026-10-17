"""Offline tests for the profile-specific Gazebo-to-ROS scan bridge."""

import ast
from copy import deepcopy
import hashlib
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest
import yaml

from mecanum_nav_bringup import sim_eval_lidar_scan_bridge_runtime_contract as contract


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PACKAGE_ROOT.parents[2]
RUNTIME_YAML = PACKAGE_ROOT / "config/bridge/sim_eval_lidar_scan_bridge.runtime.yaml"
LAUNCH_FILE = PACKAGE_ROOT / "launch/sim_eval_lidar_scan_bridge.launch.py"
SETUP_FILE = PACKAGE_ROOT / "setup.py"
PACKAGE_XML = PACKAGE_ROOT / "package.xml"
BASE_STATIC_PINS = {
    "ros2_ws/src/mecanum_nav_bringup/config/bridge/sim_eval_lidar_scan_bridge.static.yaml":
        "60a012fd2fd8f743658cdfb4fc3e910d728b17b2bea5d7dece3316bd4f12ff7e",
    "ros2_ws/src/mecanum_nav_bringup/mecanum_nav_bringup/sim_eval_lidar_scan_bridge_contract.py":
        "984ee08b9338ae407c779efe5a69c1f55862cf6e739b9a9e6454da5054c0f5ed",
}


class UniqueKeyLoader(yaml.SafeLoader):
    pass


def _construct_unique_mapping(loader, node, deep=False):
    mapping = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise ValueError(f"duplicate YAML key: {key!r}")
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


def _load_yaml():
    raw = RUNTIME_YAML.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf")
    raw.decode("utf-8")
    return yaml.load(raw, Loader=UniqueKeyLoader)


def _tamper(key, value):
    result = deepcopy(contract.RUNTIME_YAML)
    result[0][key] = value
    return result


def test_runtime_yaml_is_exact_singleton_sequence_and_validates():
    document = _load_yaml()
    assert type(document) is list
    assert len(document) == 1
    assert document == contract.RUNTIME_YAML
    assert document[0] == {
        "ros_topic_name": "/scan",
        "gz_topic_name": "/scan",
        "ros_type_name": "sensor_msgs/msg/LaserScan",
        "gz_type_name": "gz.msgs.LaserScan",
        "subscriber_queue": 10,
        "publisher_queue": 10,
        "lazy": False,
        "direction": "GZ_TO_ROS",
    }
    assert contract.validate_runtime_mapping(document) is True


@pytest.mark.parametrize(
    "document",
    [
        {"ros_topic_name": "/scan"},
        [],
        [contract.RUNTIME_MAPPING, contract.RUNTIME_MAPPING],
        [{"ros_topic_name": "/scan", "extra_tf": True}],
    ],
)
def test_validator_rejects_wrong_root_or_mapping_cardinality(document):
    with pytest.raises(contract.RuntimeScanBridgeContractError):
        contract.validate_runtime_mapping(document)


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("ros_topic_name", "/other"),
        ("gz_topic_name", "/other"),
        ("ros_type_name", "sensor_msgs/msg/Imu"),
        ("gz_type_name", "gz.msgs.PointCloudPacked"),
        ("direction", "BIDIRECTIONAL"),
        ("direction", "ROS_TO_GZ"),
        ("lazy", True),
        ("subscriber_queue", 9),
        ("publisher_queue", 11),
        ("subscriber_queue", True),
        ("unexpected_tf", True),
        ("odom_topic", "/odom"),
        ("command_topic", "/cmd_vel"),
        ("map_topic", "/map"),
        ("nav2", True),
        ("amcl", True),
        ("ekf", True),
    ],
)
def test_validator_rejects_tampered_mapping_fields(key, value):
    with pytest.raises(contract.RuntimeScanBridgeContractError):
        contract.validate_runtime_mapping(_tamper(key, value))


@pytest.mark.parametrize(
    ("use_sim_time", "partition"),
    [
        (False, "sim_eval"),
        ("true", "sim_eval"),
        (None, "sim_eval"),
        (True, ""),
        (True, "  \t"),
        (True, None),
    ],
)
def test_launch_value_validator_rejects_false_or_invalid_values(use_sim_time, partition):
    with pytest.raises(contract.RuntimeScanBridgeContractError):
        contract.validate_launch_values(use_sim_time, partition)


def test_launch_value_validator_accepts_true_and_nonempty_partition():
    assert contract.validate_launch_values(True, "sim_eval") is True
    assert contract.validate_launch_values(True, "isolated_partition") is True


def _launch_ast():
    return ast.parse(LAUNCH_FILE.read_text(encoding="utf-8"))


def _call_name(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def test_launch_declares_partition_and_sim_time_then_sets_partition_before_one_bridge():
    tree = _launch_ast()
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
    declarations = {
        node.args[0].value: node
        for node in calls
        if _call_name(node.func) == "DeclareLaunchArgument"
        and node.args
        and isinstance(node.args[0], ast.Constant)
    }
    assert set(declarations) == {"use_sim_time", "gz_partition"}
    defaults = {
        name: next(
            keyword.value.value
            for keyword in declaration.keywords
            if keyword.arg == "default_value"
            and isinstance(keyword.value, ast.Constant)
        )
        for name, declaration in declarations.items()
    }
    assert defaults == {"use_sim_time": "true", "gz_partition": "sim_eval"}

    launch_function = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "generate_launch_description"
    )
    actions = next(
        node for node in ast.walk(launch_function)
        if isinstance(node, ast.Call) and _call_name(node.func) == "LaunchDescription"
    )
    assert isinstance(actions, ast.Call)
    action_list = actions.args[0]
    assert isinstance(action_list, ast.List)
    action_names = [_call_name(item.func) for item in action_list.elts if isinstance(item, ast.Call)]
    assert action_names.count("SetEnvironmentVariable") == 1
    assert action_names.count("Node") == 1
    assert action_names.index("SetEnvironmentVariable") < action_names.index("Node")

    nodes = [node for node in calls if _call_name(node.func) == "Node"]
    assert len(nodes) == 1
    node_keywords = {keyword.arg: keyword.value for keyword in nodes[0].keywords}
    assert ast.literal_eval(node_keywords["package"]) == "ros_gz_bridge"
    assert ast.literal_eval(node_keywords["executable"]) == "parameter_bridge"
    assert "config_file" in ast.unparse(node_keywords["parameters"])
    assert "use_sim_time" in ast.unparse(node_keywords["parameters"])

    env_calls = [node for node in calls if _call_name(node.func) == "SetEnvironmentVariable"]
    assert len(env_calls) == 1
    env_keywords = {keyword.arg: keyword.value for keyword in env_calls[0].keywords}
    assert ast.literal_eval(env_keywords["name"]) == "GZ_PARTITION"
    assert ast.unparse(env_keywords["value"]) == "gz_partition"

    validate = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_validate_launch_contract"
    )
    validate_source = ast.unparse(validate)
    assert "partition.strip()" in validate_source
    assert "!= 'true'" in validate_source
    assert "RuntimeError" in validate_source


def test_launch_has_no_server_spawn_graph_publishers_or_forbidden_topics():
    tree = _launch_ast()
    source = LAUNCH_FILE.read_text(encoding="utf-8")
    forbidden_terms = (
        "ros_gz_sim", "gz sim", "create", "robot_state_publisher",
        "static_transform_publisher", "tf2_ros", "create_publisher",
        "create_subscription", "/odom", "/ground_truth/odom", "/cmd_vel",
        "nav2", "amcl", "ekf", "map_server",
    )
    lowered = source.lower()
    for term in forbidden_terms:
        assert term.lower() not in lowered
    imported_roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_roots.add(node.module.split(".", 1)[0])
    assert "rclpy" not in imported_roots
    assert "sensor_msgs" not in imported_roots


def test_package_manifest_and_setup_install_runtime_artifacts_and_dependencies():
    package = ET.parse(PACKAGE_XML).getroot()
    dependencies = [node.text for node in package.findall("exec_depend")]
    assert dependencies.count("ros_gz_bridge") == 1
    assert dependencies.count("launch") == 1
    assert dependencies.count("launch_ros") == 1

    setup_text = SETUP_FILE.read_text(encoding="utf-8")
    ast.parse(setup_text)
    assert "config/bridge/sim_eval_lidar_scan_bridge.runtime.yaml" in setup_text
    assert "launch/sim_eval_lidar_scan_bridge.launch.py" in setup_text
    assert '"share/" + package_name + "/config/bridge"' in setup_text
    assert '"share/" + package_name + "/launch"' in setup_text


def test_static_bridge_provenance_files_remain_at_base_bytes():
    for relative, expected_sha in BASE_STATIC_PINS.items():
        path = REPO_ROOT / relative
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected_sha
