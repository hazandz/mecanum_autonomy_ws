"""Exact, offline validator for the bounded sim_eval ingress descriptor."""

from collections.abc import Mapping


SOURCE_BINDING_DESCRIPTOR = {
    "schema": "mecanum_sim_eval_wheel_imu_runtime_source/v1",
    "profile": "sim_eval",
    "navigation_mode": "NAV2_BASELINE",
    "runtime_eligible": False,
    "use_sim_time": True,
    "gazebo_sources": {
        "wheel": {"endpoint": "/joint_states", "message_type": "gz.msgs.Model"},
        "imu": {"endpoint": "/sim_eval/imu/raw", "message_type": "gz.msgs.IMU"},
    },
    "staging_inputs": {
        "wheel": {
            "endpoint": "/sim_eval/wheel_joint_states",
            "message_type": "sensor_msgs/msg/JointState",
            "qos": {"reliability": "BEST_EFFORT", "durability": "VOLATILE", "history": "KEEP_LAST", "depth": 10},
        },
        "imu": {
            "endpoint": "/sim_eval/imu_raw",
            "message_type": "sensor_msgs/msg/Imu",
            "qos": {"reliability": "BEST_EFFORT", "durability": "VOLATILE", "history": "KEEP_LAST", "depth": 10},
        },
    },
    "canonical_outputs": {
        "wheel": {
            "endpoint": "/wheel/odometry_raw",
            "message_type": "nav_msgs/msg/Odometry",
            "header_frame_id": "odom",
            "child_frame_id": "base_link",
            "publishes_tf": False,
            "qos": {"reliability": "RELIABLE", "durability": "VOLATILE", "history": "KEEP_LAST", "depth": 10},
        },
        "imu": {
            "endpoint": "/imu/data",
            "message_type": "sensor_msgs/msg/Imu",
            "header_frame_id": "base_link",
            "publishes_tf": False,
            "qos": {"reliability": "RELIABLE", "durability": "VOLATILE", "history": "KEEP_LAST", "depth": 10},
        },
    },
    "wheel_geometry": {
        "logical_order": ["FL", "FR", "RL", "RR"],
        "joint_names": {"FL": "Wheel_LF_Joint", "FR": "Wheel_RF_Joint", "RL": "Wheel_LB_Joint", "RR": "Wheel_RB_Joint"},
        "wheel_radius_m": 0.0485,
        "wheelbase_m": 0.216,
        "track_m": 0.22218,
        "wheel_signs": [1, 1, 1, 1],
    },
    "timing": {"imu_update_rate_hz": 50.0, "max_source_gap_s": 0.20},
    "covariance": {
        "wheel_pose_diagonal": [0.0025, 0.0025, 1000000.0, 1000000.0, 1000000.0, 0.007615435],
        "wheel_twist_diagonal": [0.01, 0.01, 1000000.0, 1000000.0, 1000000.0, 0.04],
        "imu_orientation_diagonal": [1000000.0, 1000000.0, 0.007615435],
        "imu_angular_velocity_diagonal": [1000000.0, 1000000.0, 0.01],
        "imu_linear_acceleration_diagonal": [1000000.0, 1000000.0, 1000000.0],
    },
    "prohibitions": {"forbidden_ekf_inputs": ["/odom", "/ground_truth/odom"], "no_tf_publication": True},
    "bridge_implementation_status": "PENDING_WP06_6E",
    "runtime_evidence_status": "NOT_CREATED",
}


class RuntimeSourceBindingError(ValueError):
    """Raised when a source-binding descriptor differs from its exact contract."""


def _validate_exact(actual, expected, path="descriptor"):
    if isinstance(expected, dict):
        if not isinstance(actual, Mapping) or set(actual) != set(expected):
            raise RuntimeSourceBindingError(f"{path}: mapping keys differ")
        for key, value in expected.items():
            _validate_exact(actual[key], value, f"{path}.{key}")
        return
    if isinstance(expected, list):
        if type(actual) is not list or len(actual) != len(expected):
            raise RuntimeSourceBindingError(f"{path}: list shape differs")
        for index, (item, wanted) in enumerate(zip(actual, expected)):
            _validate_exact(item, wanted, f"{path}[{index}]")
        return
    if type(actual) is not type(expected) or actual != expected:
        raise RuntimeSourceBindingError(f"{path}: literal value differs")


def validate_sim_eval_wheel_imu_runtime_source_descriptor(descriptor):
    """Validate an injected mapping without I/O, ROS, or Gazebo imports."""
    _validate_exact(descriptor, SOURCE_BINDING_DESCRIPTOR)
    return None
