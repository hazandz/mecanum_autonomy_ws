import hashlib
import json
from pathlib import Path
import unittest

import pytest
import yaml

from mecanum_base_bridge.sim_eval_wheel_imu_runtime_source_binding import (
    SIM_EVAL_WHEEL_IMU_RUNTIME_SOURCE_BINDING,
    RuntimeSourceBindingError,
    validate_sim_eval_wheel_imu_runtime_source_binding,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/sim_eval_wheel_imu_runtime_source.yaml"


def _no_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate key: {key}")
        result[key] = value
    return result


class UniqueKeyLoader(yaml.SafeLoader):
    def construct_mapping(self, node, deep=False):
        return _no_duplicate_keys(self.construct_pairs(node, deep=deep))


def test_yaml_is_exact_and_keeps_runtime_and_bridge_pending():
    raw = CONFIG.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8")
    descriptor = yaml.load(text, Loader=UniqueKeyLoader)
    assert descriptor == SIM_EVAL_WHEEL_IMU_RUNTIME_SOURCE_BINDING
    assert validate_sim_eval_wheel_imu_runtime_source_binding(descriptor) is True
    assert descriptor["runtime_eligible"] is False
    assert descriptor["bridge_implementation_status"] == "PENDING_WP06_6E"
    assert descriptor["runtime_evidence_status"] == "NOT_CREATED"
    assert hashlib.sha256(raw).hexdigest() == hashlib.sha256(CONFIG.read_bytes()).hexdigest()


def test_exact_validator_rejects_tampering_and_unknown_keys():
    import copy

    descriptor = copy.deepcopy(SIM_EVAL_WHEEL_IMU_RUNTIME_SOURCE_BINDING)
    descriptor["runtime_eligible"] = True
    with pytest.raises(RuntimeSourceBindingError):
        validate_sim_eval_wheel_imu_runtime_source_binding(descriptor)
    descriptor = copy.deepcopy(SIM_EVAL_WHEEL_IMU_RUNTIME_SOURCE_BINDING)
    descriptor["sources"]["imu"]["gazebo_endpoint"] = "/some/other/topic"
    with pytest.raises(RuntimeSourceBindingError):
        validate_sim_eval_wheel_imu_runtime_source_binding(descriptor)
    descriptor = copy.deepcopy(SIM_EVAL_WHEEL_IMU_RUNTIME_SOURCE_BINDING)
    descriptor["unexpected"] = None
    with pytest.raises(RuntimeSourceBindingError):
        validate_sim_eval_wheel_imu_runtime_source_binding(descriptor)


def test_yaml_duplicate_keys_are_rejected():
    with pytest.raises(ValueError):
        yaml.load("schema: a\nschema: b\n", Loader=UniqueKeyLoader)


def test_binding_module_has_no_ros_gazebo_or_io_imports():
    import ast

    source = (ROOT / "mecanum_base_bridge/sim_eval_wheel_imu_runtime_source_binding.py").read_text()
    tree = ast.parse(source)
    forbidden = {"rclpy", "nav_msgs", "sensor_msgs", "gz", "gazebo", "subprocess", "socket", "urllib", "pathlib"}
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".")[0])
    assert not (imports & forbidden)


class ColconBindingContractTests(unittest.TestCase):
    """Expose the offline pytest assertions to ament_python's unittest runner."""

    def test_yaml_contract(self):
        test_yaml_is_exact_and_keeps_runtime_and_bridge_pending()

    def test_validator_tamper_rejection(self):
        test_exact_validator_rejects_tampering_and_unknown_keys()

    def test_duplicate_key_rejection(self):
        test_yaml_duplicate_keys_are_rejected()

    def test_import_boundary(self):
        test_binding_module_has_no_ros_gazebo_or_io_imports()
