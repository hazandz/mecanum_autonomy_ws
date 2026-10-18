"""Offline contract checks and provenance pins for WP06-6F source."""

from __future__ import annotations

import hashlib
from pathlib import Path
from collections.abc import Mapping


PARTITION = "wp06_scan_probe_run_002"
RUN_ID = "WP06_6F_TF_EKF_RUNTIME_INGRESS_RUN_001"
PENDING_GUARD_STATE = "PENDING_EXACT_INTEGRATION_AND_USER_AUTHORIZATION"
EVIDENCE_CEILING = "IMPLEMENTED_OFFLINE_TF_EKF_SOURCE_AND_GUARD_ONLY"

CLOCK_MAPPING = {
    "ros_topic_name": "/clock",
    "gz_topic_name": "/clock",
    "ros_type_name": "rosgraph_msgs/msg/Clock",
    "gz_type_name": "gz.msgs.Clock",
    "direction": "GZ_TO_ROS",
}
FORBIDDEN_BRIDGE_TOPICS = {
    "/odom", "/ground_truth/odom", "/tf", "/tf_static", "/cmd_vel", "/map"
}
EKF_CONFIG_PATH = "ros2_ws/src/mecanum_nav_bringup/config/state_estimation/ekf_sim.yaml"
CLOCK_CONFIG_PATH = "ros2_ws/src/mecanum_nav_bringup/config/bridge/sim_eval_clock.runtime.yaml"
COMPOSITE_LAUNCH_PATH = "ros2_ws/src/mecanum_nav_bringup/launch/sim_eval_tf_ekf_state_estimation.launch.py"
INGRESS_LAUNCH_PATH = "ros2_ws/src/mecanum_base_bridge/launch/sim_eval_wheel_imu_ingress.launch.py"
INGRESS_CONFIG_PATH = "ros2_ws/src/mecanum_base_bridge/config/bridge/sim_eval_wheel_imu_ingress.runtime.yaml"
BOOTSTRAP_PATH = "ros2_ws/src/ROBOT_URDF_final_description/launch/sim_eval_scan_probe_bootstrap.launch.py"
ROBOT_XACRO_PATH = "ros2_ws/src/ROBOT_URDF_final_description/urdf/ROBOT_URDF_final.xacro"
GAZEBO_SOURCE_PATH = "ros2_ws/src/ROBOT_URDF_final_description/urdf/ROBOT_URDF_final.gazebo"
DECISION_PATH = "docs/governance/decisions/WP-06_SIM_EVAL_TF_EKF_RUNTIME_STATE_ESTIMATION_INGRESS_L2_DECISION.md"

EXPECTED_EKF_PARAMETERS = {
    "use_sim_time": True,
    "frequency": 30.0,
    "sensor_timeout": 0.20,
    "two_d_mode": True,
    "publish_tf": True,
    "publish_acceleration": False,
    "reset_on_time_jump": True,
    "use_control": False,
    "map_frame": "map",
    "odom_frame": "odom",
    "base_link_frame": "base_link",
    "world_frame": "odom",
    "odom0": "/wheel/odometry_raw",
    "imu0": "/imu/data",
    "odom0_config": [False, False, False, False, False, False, True, True, False, False, False, False, False, False, False],
    "imu0_config": [False, False, False, False, False, True, False, False, False, False, False, True, False, False, False],
    "odom0_differential": False,
    "odom0_relative": False,
    "imu0_differential": False,
    "imu0_relative": False,
    "odom0_queue_size": 10,
    "imu0_queue_size": 20,
}

PROTECTED_PATH_PREFIXES = (
    "artifacts/simulation/sim_eval_scan_endpoint_probe_evidence/runs/",
)


def _strict_equal(actual, expected):
    if isinstance(expected, Mapping):
        return (
            isinstance(actual, Mapping)
            and set(actual) == set(expected)
            and all(_strict_equal(actual[key], value) for key, value in expected.items())
        )
    if isinstance(expected, list):
        return (
            type(actual) is list
            and len(actual) == len(expected)
            and all(_strict_equal(left, right) for left, right in zip(actual, expected))
        )
    return type(actual) is type(expected) and actual == expected


def validate_clock_mapping(document):
    """Accept only the one approved GZ-to-ROS clock mapping."""
    return type(document) is list and len(document) == 1 and _strict_equal(document[0], CLOCK_MAPPING)


def validate_ekf_config(document):
    """Fail closed unless the EKF uses the exact approved input/frame/fusion contract."""
    if not isinstance(document, Mapping) or set(document) != {"ekf_filter_node"}:
        return False
    node = document.get("ekf_filter_node")
    if not isinstance(node, Mapping) or set(node) != {"ros__parameters"}:
        return False
    params = node["ros__parameters"]
    if not isinstance(params, Mapping) or set(params) != set(EXPECTED_EKF_PARAMETERS):
        return False
    return _strict_equal(params, EXPECTED_EKF_PARAMETERS)


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_source_pins(repository_root, source_pins):
    """Verify exact local bytes against manifest-provided SHA-256 pins."""
    root = Path(repository_root).resolve()
    if not isinstance(source_pins, Mapping) or not source_pins:
        return False, "SOURCE_PINS_EMPTY"
    for relative, expected in source_pins.items():
        if not isinstance(relative, str) or not isinstance(expected, str):
            return False, "SOURCE_PIN_SCHEMA_INVALID"
        if len(expected) != 64 or any(char not in "0123456789abcdef" for char in expected):
            return False, f"SOURCE_PIN_SHA_INVALID:{relative}"
        path = (root / relative).resolve()
        if root not in path.parents or not path.is_file():
            return False, f"SOURCE_PIN_PATH_INVALID:{relative}"
        if sha256_file(path) != expected:
            return False, f"SOURCE_PIN_MISMATCH:{relative}"
    return True, "SOURCE_PINS_PASS"


def expected_tf_contract():
    return {
        "dynamic_edge": {"parent": "odom", "child": "base_link", "owner": "ekf_filter_node"},
        "static_edge": {
            "parent": "base_link", "child": "lidar_frame", "owner": "bootstrap_robot_state_publisher",
            "translation": [-0.031765, 0.0, 0.140], "rotation_xyzw": [0.0, 0.0, 0.0, 1.0],
        },
        "forbidden_edge": {"parent": "map", "child": "odom"},
    }
