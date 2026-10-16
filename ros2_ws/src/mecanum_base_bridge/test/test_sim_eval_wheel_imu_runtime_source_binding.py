import ast
from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from mecanum_base_bridge.sim_eval_wheel_imu_runtime_source_binding import (
    RuntimeSourceBindingError,
    SOURCE_BINDING_DESCRIPTOR,
    validate_sim_eval_wheel_imu_runtime_source_descriptor,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/sim_eval_wheel_imu_runtime_source.yaml"


class UniqueKeyLoader(yaml.SafeLoader):
    pass


def _construct_mapping(loader, node, deep=False):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in result:
            raise ValueError(f"duplicate YAML key: {key}")
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


UniqueKeyLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_mapping)


def _load_yaml():
    raw = CONFIG.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf")
    raw.decode("utf-8")
    return yaml.load(raw, Loader=UniqueKeyLoader)


def test_runtime_source_yaml_is_utf8_duplicate_free_and_exact():
    descriptor = _load_yaml()
    assert descriptor == SOURCE_BINDING_DESCRIPTOR
    assert descriptor["runtime_eligible"] is False
    assert descriptor["bridge_implementation_status"] == "PENDING_WP06_6E"
    assert descriptor["runtime_evidence_status"] == "NOT_CREATED"
    assert validate_sim_eval_wheel_imu_runtime_source_descriptor(descriptor) is None


@pytest.mark.parametrize("mutation", ["missing", "extra", "pin", "qos", "eligible", "forbidden"])
def test_exact_validator_rejects_contract_mutations(mutation):
    descriptor = deepcopy(SOURCE_BINDING_DESCRIPTOR)
    if mutation == "missing":
        del descriptor["timing"]
    elif mutation == "extra":
        descriptor["bridge_endpoint"] = "/guessed"
    elif mutation == "pin":
        descriptor["gazebo_sources"]["wheel"]["endpoint"] = "/joint_states/guessed"
    elif mutation == "qos":
        descriptor["canonical_outputs"]["imu"]["qos"]["reliability"] = "BEST_EFFORT"
    elif mutation == "eligible":
        descriptor["runtime_eligible"] = True
    else:
        descriptor["prohibitions"]["forbidden_ekf_inputs"].remove("/ground_truth/odom")
    with pytest.raises(RuntimeSourceBindingError):
        validate_sim_eval_wheel_imu_runtime_source_descriptor(descriptor)


def test_config_contains_only_declared_pair_of_staging_and_canonical_endpoints():
    descriptor = _load_yaml()
    assert {item["endpoint"] for item in descriptor["staging_inputs"].values()} == {
        "/sim_eval/wheel_joint_states",
        "/sim_eval/imu_raw",
    }
    assert {item["endpoint"] for item in descriptor["canonical_outputs"].values()} == {
        "/wheel/odometry_raw",
        "/imu/data",
    }
    assert descriptor["prohibitions"]["forbidden_ekf_inputs"] == ["/odom", "/ground_truth/odom"]
    assert descriptor["prohibitions"]["no_tf_publication"] is True


def test_package_declares_only_the_required_ingress_runtime_dependencies():
    import xml.etree.ElementTree as ET

    package = ET.parse(ROOT / "package.xml").getroot()
    runtime_dependencies = {node.text for node in package.findall("exec_depend")}
    assert runtime_dependencies == {"rclpy", "nav_msgs", "sensor_msgs"}


def test_gazebo_xml_has_one_exact_base_link_imu_and_world_plugin_is_unchanged():
    import xml.etree.ElementTree as ET

    gazebo = ROOT.parent / "ROBOT_URDF_final_description/urdf/ROBOT_URDF_final.gazebo"
    sdf = ROOT.parent / "ROBOT_URDF_final_description/launch/tugbot_depot.sdf"
    robot = ET.parse(gazebo).getroot()
    sensors = [node for node in robot.findall("gazebo[@reference='base_link']/sensor") if node.get("type") == "imu"]
    assert len(sensors) == 1
    sensor = sensors[0]
    assert sensor.get("name") == "sim_eval_base_imu"
    assert sensor.findtext("pose") == "0 0 0 0 0 0"
    assert sensor.findtext("always_on") == "true"
    assert sensor.findtext("update_rate") == "50.0"
    assert sensor.findtext("topic") == "/sim_eval/imu/raw"
    world = ET.parse(sdf).getroot()
    assert sum(1 for p in world.iter("plugin") if p.get("name") == "gz::sim::systems::Imu") == 1


def test_no_duplicate_or_alternate_ros_gazebo_ingress_runtime_implementation():
    module = ROOT / "mecanum_base_bridge/sim_eval_wheel_imu_runtime_source_binding.py"
    tree = ast.parse(module.read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".", 1)[0])
    assert imported.isdisjoint({"rclpy", "gazebo", "gz", "ros_gz_bridge", "ros_gz_sim"})
