"""Pure-Python, fail-closed static contract for the sim_eval LiDAR scan bridge."""

from collections.abc import Mapping


SCHEMA = "mecanum_sim_eval_lidar_scan_bridge_static/v1"
PROFILE = "sim_eval"
CLASSIFICATION = "STATIC_CONTRACT_ONLY"
RUNTIME_ELIGIBLE = False
USE_SIM_TIME = True

GAZEBO_SENSOR = {
    "source_file": "ros2_ws/src/ROBOT_URDF_final_description/urdf/ROBOT_URDF_final.gazebo",
    "reference_link": "lidar_frame",
    "sensor_name": "YDLIDAR_X3_PRO",
    "sensor_type": "gpu_lidar",
    "declared_sensor_topic": "scan",
    "declared_update_rate_hz": 6.0,
    "declared_horizontal_samples": 500,
    "declared_range_min_m": 0.10,
    "declared_range_max_m": 8.00,
}

TRANSPORT_BINDING = {
    "direction": "GZ_TO_ROS",
    "gz_transport_endpoint": "PENDING_GZ_LIDAR_TRANSPORT_ENDPOINT_PIN",
    "gz_message_type": "gz.msgs.LaserScan",
    "bridge_implementation": "PENDING_PROFILE_SPECIFIC_ROS_GZ_BRIDGE_SOURCE_PIN",
    "observed_scan_timing": "PENDING_S2_SENSOR_TIMING_DECISION",
}

ROS_OUTPUT = {
    "topic": "/scan",
    "ros_message_type": "sensor_msgs/msg/LaserScan",
    "required_header_frame_id": "lidar_frame",
    "publishes_tf": False,
}

TF_CONTRACT = {
    "base_to_lidar_owner": "robot_state_publisher",
    "required_static_edge": "base_link -> lidar_frame",
    "bridge_publishes_tf": False,
}

PROHIBITIONS = {
    "no_runtime_bridge_activation": True,
    "forbidden_ros_topics": ["/odom", "/ground_truth/odom"],
    "forbidden_frame_aliases": ["base_scan", "rplidar_link"],
    "forbidden_inferences": [
        "gazebo_transport_is_not_ros_scan",
        "relative_sensor_topic_is_not_full_transport_endpoint",
    ],
}

STATIC_DESCRIPTOR = {
    "schema": SCHEMA,
    "profile": PROFILE,
    "classification": CLASSIFICATION,
    "runtime_eligible": RUNTIME_ELIGIBLE,
    "use_sim_time": USE_SIM_TIME,
    "gazebo_sensor": GAZEBO_SENSOR,
    "transport_binding": TRANSPORT_BINDING,
    "ros_output": ROS_OUTPUT,
    "tf_contract": TF_CONTRACT,
    "prohibitions": PROHIBITIONS,
}


class StaticLidarBridgeContractError(ValueError):
    """Raised when a descriptor is not exactly the static, pending contract."""


def _validate_exact(actual, expected, path):
    if isinstance(expected, Mapping):
        if not isinstance(actual, Mapping):
            raise StaticLidarBridgeContractError(f"{path} must be a mapping")
        if set(actual) != set(expected):
            raise StaticLidarBridgeContractError(f"{path} has missing or unexpected fields")
        for key, expected_value in expected.items():
            _validate_exact(actual[key], expected_value, f"{path}.{key}")
        return

    if isinstance(expected, list):
        if type(actual) is not list or len(actual) != len(expected):
            raise StaticLidarBridgeContractError(f"{path} does not match the static contract")
        for index, (actual_value, expected_value) in enumerate(zip(actual, expected)):
            _validate_exact(actual_value, expected_value, f"{path}[{index}]")
        return

    if type(actual) is not type(expected) or actual != expected:
        raise StaticLidarBridgeContractError(f"{path} does not match the static contract")


def validate_sim_eval_lidar_scan_bridge_descriptor(descriptor):
    """Validate a caller-supplied mapping without I/O or runtime interaction."""
    _validate_exact(descriptor, STATIC_DESCRIPTOR, "descriptor")
    return None
