"""Exact, fail-closed static descriptor validator for the sim_eval ingress."""

from collections.abc import Mapping


SCHEMA = "mecanum_base_bridge_sim_eval_wheel_imu_runtime_source/v1"
EXPECTED_DESCRIPTOR = {
    "schema": SCHEMA,
    "profile": "sim_eval",
    "navigation_mode": "NAV2_BASELINE",
    "runtime_eligible": False,
    "use_sim_time": True,
    "gazebo_sources": {
        "wheel": {"endpoint": "/joint_states", "message_type": "gz.msgs.Model"},
        "imu": {"endpoint": "/sim_eval/imu/raw", "message_type": "gz.msgs.IMU",
                "frame_id": "base_link", "gz_frame_id": "base_link"},
    },
    "staging_inputs": {
        "wheel": {"topic": "/sim_eval/wheel_joint_states", "message_type": "sensor_msgs/msg/JointState",
                  "reliability": "BEST_EFFORT", "durability": "VOLATILE", "history": "KEEP_LAST", "depth": 10},
        "imu": {"topic": "/sim_eval/imu_raw", "message_type": "sensor_msgs/msg/Imu",
                "reliability": "BEST_EFFORT", "durability": "VOLATILE", "history": "KEEP_LAST", "depth": 10},
    },
    "bridge_mappings": [
        {"ros_topic_name": "/sim_eval/wheel_joint_states", "gz_topic_name": "/joint_states",
         "ros_type_name": "sensor_msgs/msg/JointState", "gz_type_name": "gz.msgs.Model",
         "direction": "GZ_TO_ROS", "lazy": False, "subscriber_queue": 10,
         "publisher_queue": 10, "qos_profile": "SENSOR_DATA"},
        {"ros_topic_name": "/sim_eval/imu_raw", "gz_topic_name": "/sim_eval/imu/raw",
         "ros_type_name": "sensor_msgs/msg/Imu", "gz_type_name": "gz.msgs.IMU",
         "direction": "GZ_TO_ROS", "lazy": False, "subscriber_queue": 10,
         "publisher_queue": 10, "qos_profile": "SENSOR_DATA"},
    ],
    "canonical_outputs": {
        "wheel": {"topic": "/wheel/odometry_raw", "message_type": "nav_msgs/msg/Odometry",
                  "header_frame_id": "odom", "child_frame_id": "base_link", "publishes_tf": False,
                  "reliability": "RELIABLE", "durability": "VOLATILE", "history": "KEEP_LAST", "depth": 10},
        "imu": {"topic": "/imu/data", "message_type": "sensor_msgs/msg/Imu",
                "header_frame_id": "base_link", "publishes_tf": False,
                "reliability": "RELIABLE", "durability": "VOLATILE", "history": "KEEP_LAST", "depth": 10},
    },
    "wheel_geometry": {
        "logical_order": ["FL", "FR", "RL", "RR"],
        "joint_names": {"FL": "Wheel_LF_Joint", "FR": "Wheel_RF_Joint", "RL": "Wheel_LB_Joint", "RR": "Wheel_RB_Joint"},
        "wheel_radius_m": 0.0485, "wheelbase_m": 0.216, "track_m": 0.22218, "wheel_signs": [1, 1, 1, 1],
    },
    "timing": {"imu_update_rate_hz": 50.0, "max_source_gap_s": 0.20},
    "covariance": {
        "wheel_pose_diagonal": [0.0025, 0.0025, 1000000.0, 1000000.0, 1000000.0, 0.007615435],
        "wheel_twist_diagonal": [0.01, 0.01, 1000000.0, 1000000.0, 1000000.0, 0.04],
        "imu_orientation_diagonal": [1000000.0, 1000000.0, 0.007615435],
        "imu_angular_velocity_diagonal": [1000000.0, 1000000.0, 0.01],
        "imu_linear_acceleration_diagonal": [1000000.0, 1000000.0, 1000000.0],
    },
    "prohibitions": {
        "forbidden_inputs": ["/odom", "/ground_truth/odom"],
        "tf_publication": False,
    },
    "bridge_implementation_status": "IMPLEMENTED_OFFLINE_ONLY_PENDING_RUNTIME_AUDIT",
    "runtime_evidence_status": "NOT_CREATED",
}


class RuntimeSourceBindingError(ValueError):
    """Raised when a runtime source descriptor differs from the exact contract."""


def _same_exactly(actual, expected):
    if isinstance(expected, Mapping):
        return (isinstance(actual, Mapping) and set(actual) == set(expected)
                and all(_same_exactly(actual[key], value) for key, value in expected.items()))
    if isinstance(expected, list):
        return type(actual) is list and len(actual) == len(expected) and all(
            _same_exactly(left, right) for left, right in zip(actual, expected)
        )
    return type(actual) is type(expected) and actual == expected


def validate_sim_eval_wheel_imu_runtime_source_binding(descriptor):
    """Accept only the complete static binding descriptor, without I/O."""
    if not _same_exactly(descriptor, EXPECTED_DESCRIPTOR):
        raise RuntimeSourceBindingError("descriptor differs from exact sim_eval runtime source binding")
    return None
