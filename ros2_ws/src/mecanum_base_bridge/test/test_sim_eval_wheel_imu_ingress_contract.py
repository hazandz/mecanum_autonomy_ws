import ast
from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from mecanum_base_bridge.sim_eval_wheel_imu_ingress_contract import (
    CLASSIFICATION,
    FORBIDDEN_FRAME_ALIASES,
    FORBIDDEN_INPUT_TOPICS,
    FORBIDDEN_TF_EDGES,
    IMU_HEADER_FRAME,
    IMU_MESSAGE_TYPE,
    IMU_TOPIC,
    PENDING_SENSOR_TIMING,
    PENDING_SIM_IMU_ENDPOINT,
    PENDING_SIM_WHEEL_ENDPOINT,
    PROFILE,
    SCHEMA,
    StaticIngressContractError,
    USE_SIM_TIME,
    WHEEL_CHILD_FRAME,
    WHEEL_HEADER_FRAME,
    WHEEL_MESSAGE_TYPE,
    WHEEL_TOPIC,
    validate_sim_eval_wheel_imu_ingress_descriptor,
)


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = PACKAGE_ROOT / "config/sim_eval_wheel_imu_ingress.static.yaml"


def load_contract():
    return yaml.safe_load(CONTRACT_PATH.read_text(encoding="utf-8"))


def test_static_yaml_parses_and_has_exact_canonical_contract_values():
    descriptor = load_contract()
    assert descriptor["schema"] == SCHEMA
    assert descriptor["profile"] == PROFILE
    assert descriptor["classification"] == CLASSIFICATION
    assert descriptor["runtime_eligible"] is False
    assert descriptor["use_sim_time"] is USE_SIM_TIME
    assert descriptor["wheel_odometry"] == {
        "topic": WHEEL_TOPIC,
        "ros_message_type": WHEEL_MESSAGE_TYPE,
        "header_frame_id": WHEEL_HEADER_FRAME,
        "child_frame_id": WHEEL_CHILD_FRAME,
        "publishes_tf": False,
    }
    assert descriptor["imu"] == {
        "topic": IMU_TOPIC,
        "ros_message_type": IMU_MESSAGE_TYPE,
        "header_frame_id": IMU_HEADER_FRAME,
        "publishes_tf": False,
    }
    assert descriptor["source_bindings"] == {
        "sim_wheel_endpoint": PENDING_SIM_WHEEL_ENDPOINT,
        "sim_imu_endpoint": PENDING_SIM_IMU_ENDPOINT,
        "sensor_timing": PENDING_SENSOR_TIMING,
        "runtime_eligibility": False,
    }
    assert descriptor["prohibitions"] == {
        "no_tf_publication": True,
        "forbidden_input_topics": list(FORBIDDEN_INPUT_TOPICS),
        "forbidden_tf_edges": list(FORBIDDEN_TF_EDGES),
        "forbidden_frame_aliases": list(FORBIDDEN_FRAME_ALIASES),
    }


def test_validator_accepts_exact_static_descriptor():
    assert validate_sim_eval_wheel_imu_ingress_descriptor(load_contract()) is None


@pytest.mark.parametrize(
    "path,value",
    [
        (("wheel_odometry", "topic"), "/wrong/wheel"),
        (("wheel_odometry", "ros_message_type"), "wrong/msg/Type"),
        (("wheel_odometry", "header_frame_id"), "base_link"),
        (("wheel_odometry", "child_frame_id"), "odom"),
        (("imu", "topic"), "/wrong/imu"),
        (("imu", "ros_message_type"), "wrong/msg/Type"),
    ],
)
def test_validator_rejects_wrong_topic_type_or_frame(path, value):
    descriptor = deepcopy(load_contract())
    descriptor[path[0]][path[1]] = value
    with pytest.raises(StaticIngressContractError):
        validate_sim_eval_wheel_imu_ingress_descriptor(descriptor)


def test_validator_rejects_wheel_or_imu_tf_publication():
    for section in ("wheel_odometry", "imu"):
        descriptor = deepcopy(load_contract())
        descriptor[section]["publishes_tf"] = True
        with pytest.raises(StaticIngressContractError):
            validate_sim_eval_wheel_imu_ingress_descriptor(descriptor)


@pytest.mark.parametrize("topic", ["/odom", "/ground_truth/odom"])
def test_validator_rejects_forbidden_odometry_input(topic):
    descriptor = deepcopy(load_contract())
    descriptor["wheel_odometry"]["topic"] = topic
    with pytest.raises(StaticIngressContractError):
        validate_sim_eval_wheel_imu_ingress_descriptor(descriptor)


@pytest.mark.parametrize("frame", ["base_scan", "rplidar_link"])
def test_validator_rejects_legacy_frame_alias(frame):
    descriptor = deepcopy(load_contract())
    descriptor["imu"]["header_frame_id"] = frame
    with pytest.raises(StaticIngressContractError):
        validate_sim_eval_wheel_imu_ingress_descriptor(descriptor)


@pytest.mark.parametrize(
    "field,replacement",
    [
        ("sim_wheel_endpoint", "/some/wheel/endpoint"),
        ("sim_imu_endpoint", "/some/imu/endpoint"),
        ("sensor_timing", "100 Hz"),
    ],
)
def test_validator_rejects_inferred_source_or_timing_pin(field, replacement):
    descriptor = deepcopy(load_contract())
    descriptor["source_bindings"][field] = replacement
    with pytest.raises(StaticIngressContractError):
        validate_sim_eval_wheel_imu_ingress_descriptor(descriptor)


def test_validator_rejects_runtime_eligibility_true():
    descriptor = deepcopy(load_contract())
    descriptor["runtime_eligible"] = True
    with pytest.raises(StaticIngressContractError):
        validate_sim_eval_wheel_imu_ingress_descriptor(descriptor)
    descriptor = deepcopy(load_contract())
    descriptor["source_bindings"]["runtime_eligibility"] = True
    with pytest.raises(StaticIngressContractError):
        validate_sim_eval_wheel_imu_ingress_descriptor(descriptor)


@pytest.mark.parametrize(
    "field,replacement",
    [
        ("forbidden_input_topics", ["/odom"]),
        ("forbidden_tf_edges", ["odom -> base_link"]),
        ("forbidden_frame_aliases", ["base_scan"]),
        ("forbidden_frame_aliases", None),
    ],
)
def test_validator_rejects_missing_or_malformed_prohibition_declarations(field, replacement):
    descriptor = deepcopy(load_contract())
    descriptor["prohibitions"][field] = replacement
    with pytest.raises(StaticIngressContractError):
        validate_sim_eval_wheel_imu_ingress_descriptor(descriptor)


def test_module_and_test_are_free_of_ros_gazebo_runtime_imports_and_graph_symbols():
    forbidden_imports = {
        "rclpy", "launch", "launch_ros", "tf2_ros", "nav_msgs", "sensor_msgs",
        "gazebo", "ros_gz_bridge", "ros_gz_sim",
    }
    forbidden_symbols = {
        "Node", "Publisher", "Subscriber", "Timer", "LifecycleNode",
        "TransformBroadcaster", "LaunchDescription",
    }
    for path in (
        PACKAGE_ROOT / "mecanum_base_bridge/sim_eval_wheel_imu_ingress_contract.py",
        Path(__file__),
    ):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imported = set()
        symbols = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".", 1)[0])
            if isinstance(node, ast.Name):
                symbols.add(node.id)
        assert imported.isdisjoint(forbidden_imports)
        assert symbols.isdisjoint(forbidden_symbols)
