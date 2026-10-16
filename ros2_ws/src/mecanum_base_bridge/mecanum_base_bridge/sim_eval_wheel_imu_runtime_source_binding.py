"""Exact-key, fail-closed static validator for sim_eval ingress source binding."""

from collections.abc import Mapping


SIM_EVAL_WHEEL_IMU_RUNTIME_SOURCE_BINDING = {
    "schema": "mecanum_sim_eval_wheel_imu_runtime_source/v1",
    "profile": "sim_eval",
    "navigation_mode": "NAV2_BASELINE",
    "runtime_eligible": False,
    "use_sim_time": True,
    "sources": {
        "wheel": {"gazebo_endpoint": "/joint_states", "gazebo_message_type": "gz.msgs.Model", "staging_endpoint": "/sim_eval/wheel_joint_states", "staging_message_type": "sensor_msgs/msg/JointState"},
        "imu": {"gazebo_endpoint": "/sim_eval/imu/raw", "gazebo_message_type": "gz.msgs.IMU", "staging_endpoint": "/sim_eval/imu_raw", "staging_message_type": "sensor_msgs/msg/Imu"},
    },
    "canonical_outputs": {
        "wheel_odometry": {
            "endpoint": "/wheel/odometry_raw", "message_type": "nav_msgs/msg/Odometry", "header_frame_id": "odom", "child_frame_id": "base_link",
            "qos": {"reliability": "RELIABLE", "durability": "VOLATILE", "history": "KEEP_LAST", "depth": 10},
        },
        "imu": {
            "endpoint": "/imu/data", "message_type": "sensor_msgs/msg/Imu", "header_frame_id": "base_link",
            "qos": {"reliability": "RELIABLE", "durability": "VOLATILE", "history": "KEEP_LAST", "depth": 10},
        },
    },
    "staging_qos": {"reliability": "BEST_EFFORT", "durability": "VOLATILE", "history": "KEEP_LAST", "depth": 10},
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
    "prohibitions": {"forbidden_ekf_inputs": ["/odom", "/ground_truth/odom"], "tf_publishing": False},
    "bridge_implementation_status": "PENDING_WP06_6E",
    "runtime_evidence_status": "NOT_CREATED",
}


class RuntimeSourceBindingError(ValueError):
    """Descriptor does not exactly match the approved non-executable binding."""


def _compare(expected, actual, path="descriptor"):
    if isinstance(expected, Mapping):
        if not isinstance(actual, Mapping) or set(actual) != set(expected):
            raise RuntimeSourceBindingError(f"{path} has missing or unexpected keys")
        for key, value in expected.items():
            _compare(value, actual[key], f"{path}.{key}")
        return
    if isinstance(expected, list):
        if type(actual) is not list or len(actual) != len(expected):
            raise RuntimeSourceBindingError(f"{path} must be the exact ordered list")
        for index, (left, right) in enumerate(zip(expected, actual)):
            _compare(left, right, f"{path}[{index}]")
        return
    if type(actual) is not type(expected) or actual != expected:
        raise RuntimeSourceBindingError(f"{path} does not match its pinned value")


def validate_sim_eval_wheel_imu_runtime_source_binding(descriptor):
    """Validate a caller-owned mapping without performing I/O or ROS work."""
    _compare(SIM_EVAL_WHEEL_IMU_RUNTIME_SOURCE_BINDING, descriptor)
    return True
