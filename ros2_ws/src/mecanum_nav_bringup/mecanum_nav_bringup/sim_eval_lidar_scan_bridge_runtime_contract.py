"""Pure-Python validator for the one-way sim_eval scan bridge source."""

from collections.abc import Mapping


SCHEMA = "mecanum_sim_eval_lidar_scan_bridge_runtime/v1"
PROFILE = "sim_eval"
ROS_TOPIC = "/scan"
GAZEBO_TOPIC = "/scan"
ROS_TYPE = "sensor_msgs/msg/LaserScan"
GAZEBO_TYPE = "gz.msgs.LaserScan"
DIRECTION = "GZ_TO_ROS"
LAZY = False
SUBSCRIBER_QUEUE = 10
PUBLISHER_QUEUE = 10
USE_SIM_TIME = True
DEFAULT_GZ_PARTITION = "sim_eval"

RUNTIME_MAPPING = {
    "ros_topic_name": ROS_TOPIC,
    "gz_topic_name": GAZEBO_TOPIC,
    "ros_type_name": ROS_TYPE,
    "gz_type_name": GAZEBO_TYPE,
    "subscriber_queue": SUBSCRIBER_QUEUE,
    "publisher_queue": PUBLISHER_QUEUE,
    "lazy": LAZY,
    "direction": DIRECTION,
}
RUNTIME_YAML = [RUNTIME_MAPPING]


class RuntimeScanBridgeContractError(ValueError):
    """Raised when bridge data or launch values violate the exact contract."""


def validate_runtime_mapping(document):
    """Accept only one exact mapping with the approved GZ-to-ROS fields."""
    if type(document) is not list or len(document) != 1:
        raise RuntimeScanBridgeContractError(
            "runtime bridge YAML must be a sequence containing exactly one mapping"
        )
    actual = document[0]
    if not isinstance(actual, Mapping) or set(actual) != set(RUNTIME_MAPPING):
        raise RuntimeScanBridgeContractError(
            "runtime bridge mapping has missing or unexpected fields"
        )
    for key, expected in RUNTIME_MAPPING.items():
        value = actual[key]
        if type(value) is not type(expected) or value != expected:
            raise RuntimeScanBridgeContractError(
                f"runtime bridge field {key!r} differs from the approved value"
            )
    return True


def validate_launch_values(use_sim_time, gz_partition):
    """Validate launch-level values before any bridge process is started."""
    if type(use_sim_time) is not bool or use_sim_time is not USE_SIM_TIME:
        raise RuntimeScanBridgeContractError("use_sim_time must be boolean true")
    if not isinstance(gz_partition, str) or not gz_partition.strip():
        raise RuntimeScanBridgeContractError("gz_partition must be non-empty")
    return True
