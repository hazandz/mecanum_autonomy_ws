import xml.etree.ElementTree as ET
from pathlib import Path

import yaml

from mecanum_base_bridge.sim_eval_wheel_imu_runtime_source_binding import EXPECTED_DESCRIPTOR


ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[2]
BRIDGE_CONFIG = ROOT / "config/bridge/sim_eval_wheel_imu_ingress.runtime.yaml"
GAZEBO_SOURCE = REPO / "ros2_ws/src/ROBOT_URDF_final_description/urdf/ROBOT_URDF_final.gazebo"


class UniqueKeyLoader(yaml.SafeLoader):
    pass


def _mapping(loader, node, deep=False):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in result:
            raise ValueError(f"duplicate key: {key}")
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


UniqueKeyLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping)


def _read_yaml(path):
    raw = path.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf")
    raw.decode("utf-8")
    return yaml.load(raw, Loader=UniqueKeyLoader)


def test_runtime_bridge_yaml_has_exactly_two_one_way_staging_mappings():
    actual = _read_yaml(BRIDGE_CONFIG)
    expected = EXPECTED_DESCRIPTOR["bridge_mappings"]
    assert type(actual) is list
    assert actual == expected
    assert len(actual) == 2
    assert [entry["gz_topic_name"] for entry in actual] == ["/joint_states", "/sim_eval/imu/raw"]
    assert [entry["ros_topic_name"] for entry in actual] == ["/sim_eval/wheel_joint_states", "/sim_eval/imu_raw"]
    for entry in actual:
        assert entry["direction"] == "GZ_TO_ROS"
        assert entry["lazy"] is False
        assert entry["subscriber_queue"] == entry["publisher_queue"] == 10
        assert entry["qos_profile"] == "SENSOR_DATA"
    assert not {"/odom", "/ground_truth/odom", "/tf", "/tf_static", "/cmd_vel"}.intersection(
        {entry["gz_topic_name"] for entry in actual} | {entry["ros_topic_name"] for entry in actual}
    )


def test_runtime_source_descriptor_preserves_geometry_covariance_and_bounded_status():
    descriptor = _read_yaml(ROOT / "config/sim_eval_wheel_imu_runtime_source.yaml")
    assert descriptor == EXPECTED_DESCRIPTOR
    assert descriptor["runtime_eligible"] is False
    assert descriptor["runtime_evidence_status"] == "NOT_CREATED"
    assert descriptor["bridge_implementation_status"] == "IMPLEMENTED_OFFLINE_ONLY_PENDING_RUNTIME_AUDIT"
    assert descriptor["prohibitions"]["forbidden_inputs"] == ["/odom", "/ground_truth/odom"]
    assert descriptor["prohibitions"]["tf_publication"] is False
    assert descriptor["wheel_geometry"] == {
        "logical_order": ["FL", "FR", "RL", "RR"],
        "joint_names": {"FL": "Wheel_LF_Joint", "FR": "Wheel_RF_Joint", "RL": "Wheel_LB_Joint", "RR": "Wheel_RB_Joint"},
        "wheel_radius_m": 0.0485, "wheelbase_m": 0.216, "track_m": 0.22218, "wheel_signs": [1, 1, 1, 1],
    }
    assert descriptor["timing"]["imu_update_rate_hz"] == 50.0
    assert descriptor["covariance"]["wheel_pose_diagonal"] == [0.0025, 0.0025, 1000000.0, 1000000.0, 1000000.0, 0.007615435]


def test_gazebo_imu_source_has_exact_dual_frame_tags_without_changing_source_contract():
    root = ET.fromstring(GAZEBO_SOURCE.read_bytes())
    base = [element for element in root.findall("gazebo") if element.get("reference") == "base_link"]
    assert len(base) == 1
    sensors = [sensor for sensor in base[0].findall("sensor") if sensor.get("name") == "sim_eval_base_imu"]
    assert len(sensors) == 1
    sensor = sensors[0]
    assert sensor.get("type") == "imu"
    for name in ("frame_id", "gz_frame_id"):
        tags = sensor.findall(name)
        assert len(tags) == 1
        assert tags[0].text == "base_link"
    assert sensor.findtext("topic") == "/sim_eval/imu/raw"
    assert sensor.findtext("update_rate") == "50.0"
    assert sensor.findtext("always_on") == "true"
    plugins = root.findall("gazebo/plugin")
    joint_state = [plugin for plugin in plugins if plugin.get("name") == "gz::sim::systems::JointStatePublisher"]
    assert len(joint_state) == 1 and joint_state[0].findtext("topic") == "/joint_states"
    mecanum = [plugin for plugin in plugins if plugin.get("name") == "gz::sim::systems::MecanumDrive"]
    assert len(mecanum) == 1
    assert mecanum[0].findtext("wheel_radius") == "0.0485"
    assert mecanum[0].findtext("wheelbase") == "0.216"
    assert mecanum[0].findtext("wheel_separation") == "0.22218"


def test_package_declares_dependencies_and_installs_runtime_artifacts():
    package_xml = ET.parse(ROOT / "package.xml").getroot()
    dependencies = [element.text for element in package_xml.findall("exec_depend")]
    assert {"ros_gz_bridge", "launch", "launch_ros"}.issubset(dependencies)
    assert package_xml.findtext("version") == "0.3.0"
    setup = (ROOT / "setup.py").read_text(encoding="utf-8")
    assert "version='0.3.0'" in setup
    assert "config/bridge/sim_eval_wheel_imu_ingress.runtime.yaml" in setup
    assert "launch/sim_eval_wheel_imu_ingress.launch.py" in setup
    assert "share/' + package_name + '/config/bridge" in setup
    assert "share/' + package_name + '/launch" in setup
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "## 0.3.0" in changelog
