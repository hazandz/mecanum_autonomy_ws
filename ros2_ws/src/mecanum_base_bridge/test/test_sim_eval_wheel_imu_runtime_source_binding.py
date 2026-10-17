import ast
from copy import deepcopy
import json
from pathlib import Path

import pytest
import yaml

from mecanum_base_bridge.sim_eval_wheel_imu_runtime_source_binding import (
    EXPECTED_DESCRIPTOR,
    RuntimeSourceBindingError,
    validate_sim_eval_wheel_imu_runtime_source_binding,
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
            raise ValueError(f"duplicate key: {key}")
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


UniqueKeyLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_mapping)


def load_descriptor():
    raw = CONFIG.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf")
    raw.decode("utf-8")
    return yaml.load(raw, Loader=UniqueKeyLoader)


def test_binding_yaml_is_exact_and_validator_accepts_it():
    descriptor = load_descriptor()
    assert descriptor == EXPECTED_DESCRIPTOR
    assert descriptor["runtime_eligible"] is False
    assert descriptor["use_sim_time"] is True
    assert descriptor["bridge_implementation_status"] == "IMPLEMENTED_OFFLINE_ONLY_PENDING_RUNTIME_AUDIT"
    assert descriptor["runtime_evidence_status"] == "NOT_CREATED"
    assert descriptor["gazebo_sources"]["imu"]["frame_id"] == "base_link"
    assert descriptor["gazebo_sources"]["imu"]["gz_frame_id"] == "base_link"
    assert len(descriptor["bridge_mappings"]) == 2
    assert all(mapping["direction"] == "GZ_TO_ROS" for mapping in descriptor["bridge_mappings"])
    assert validate_sim_eval_wheel_imu_runtime_source_binding(descriptor) is None


@pytest.mark.parametrize("mutate", [
    lambda d: d["staging_inputs"]["wheel"].update(topic="/other"),
    lambda d: d["canonical_outputs"]["imu"].update(message_type="wrong/msg/Type"),
    lambda d: d["wheel_geometry"].update(wheel_radius_m=0.05),
    lambda d: d.update(runtime_eligible=True),
    lambda d: d["canonical_outputs"]["wheel"].update(publishes_tf=True),
    lambda d: d["gazebo_sources"]["wheel"].update(endpoint="/pinned/wheel/source"),
    lambda d: d["gazebo_sources"]["imu"].update(frame_id="other_frame"),
    lambda d: d["gazebo_sources"]["imu"].update(gz_frame_id="other_frame"),
    lambda d: d["bridge_mappings"][0].update(direction="BIDIRECTIONAL"),
    lambda d: d["bridge_mappings"][1].update(gz_type_name="gz.msgs.Other"),
    lambda d: d["bridge_mappings"][0].update(ros_topic_name="/odom"),
    lambda d: d["bridge_mappings"][1].update(qos_profile="DEFAULT"),
    lambda d: d["bridge_mappings"][0].update(publisher_queue=9),
    lambda d: d["covariance"].update(imu_orientation_diagonal=[0.0, 0.0, 0.0]),
    lambda d: d.update(bridge_implementation_status="RUNTIME_VALIDATED"),
    lambda d: d.update(runtime_evidence_status="CREATED"),
    lambda d: d["prohibitions"].update(no_ros_gazebo_bridge_implementation=True),
    lambda d: d.update(extra_runtime_endpoint="/unexpected"),
])
def test_validator_fails_closed_for_endpoint_type_direction_frame_qos_and_status_mutations(mutate):
    descriptor = deepcopy(load_descriptor())
    mutate(descriptor)
    with pytest.raises(RuntimeSourceBindingError):
        validate_sim_eval_wheel_imu_runtime_source_binding(descriptor)


def test_descriptor_validator_is_pure_python_without_runtime_imports():
    tree = ast.parse((ROOT / "mecanum_base_bridge/sim_eval_wheel_imu_runtime_source_binding.py").read_text())
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".", 1)[0])
    assert imports.isdisjoint({"rclpy", "nav_msgs", "sensor_msgs", "gazebo", "gz", "ros_gz_bridge"})
    assert json.loads('{"schema":"ok"}') == {"schema": "ok"}
