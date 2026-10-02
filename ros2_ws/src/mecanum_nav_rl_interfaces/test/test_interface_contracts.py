from mecanum_nav_rl_interfaces.msg import (
    CommandEnvelope,
    Heartbeat,
    NavigationState,
    SafetyState,
)


EXPECTED_CONSTANTS = {
    Heartbeat: {
        "SOURCE_UNKNOWN": 0,
        "SOURCE_POLICY": 1,
        "SOURCE_MCU": 2,
        "FAULT_NONE": 0,
        "FAULT_TRANSPORT": 1,
        "FAULT_ESTOP_ACTIVE": 2,
        "FAULT_POLICY_INFERENCE": 4,
        "FAULT_POLICY_COMMAND_INVALID": 8,
        "FAULT_POLICY_CONTROL_LOOP": 16,
        "FAULT_POLICY_MODEL_CONTRACT": 32,
        "FAULT_MCU_COMMAND_TIMEOUT": 256,
        "FAULT_MCU_COMMAND_INVALID": 512,
        "FAULT_MCU_CONTROL_LOOP": 1024,
        "FAULT_MOTOR_DRIVER": 2048,
        "FAULT_ENCODER": 4096,
        "FAULT_IMU": 8192,
    },
    SafetyState: {
        "STATE_INIT": 0,
        "STATE_NORMAL": 1,
        "STATE_LIMITED": 2,
        "STATE_STOPPED": 3,
        "STATE_ESTOPPED": 4,
        "STATE_FAULT": 5,
        "COMMAND_SOURCE_NONE": 0,
        "COMMAND_SOURCE_POLICY": 1,
        "COMMAND_SOURCE_NAV2": 2,
        "COMMAND_SOURCE_TELEOP": 3,
        "COMMAND_SOURCE_SAFE_STOP": 4,
        "COMMAND_SOURCE_ESTOP": 5,
    },
    NavigationState: {
        "STATE_IDLE": 0,
        "STATE_PLANNING": 1,
        "STATE_FOLLOWING": 2,
        "STATE_REPLANNING": 3,
        "STATE_STOPPING": 4,
        "STATE_SUCCEEDED": 5,
        "STATE_CANCELED": 6,
        "STATE_FAILED": 7,
        "ERROR_NONE": 0,
        "ERROR_INVALID_GOAL": 1,
        "ERROR_LOCALIZATION_INVALID": 2,
        "ERROR_PLANNER_UNAVAILABLE": 3,
        "ERROR_PLANNING_FAILED": 4,
        "ERROR_PATH_INVALID": 5,
        "ERROR_PATH_EXPIRED": 6,
        "ERROR_TF_FAILURE": 7,
        "ERROR_INTERNAL": 8,
    },
    CommandEnvelope: {
        "SOURCE_UNKNOWN": 0,
        "SOURCE_POLICY": 1,
        "SOURCE_NAV2": 2,
        "SOURCE_TELEOP": 3,
        "SOURCE_SAFE_STOP": 4,
    },
}


EXPECTED_FIELDS = {
    Heartbeat: [
        ("header", "std_msgs/Header"),
        ("source", "uint8"),
        ("sequence", "uint32"),
        ("reset_epoch", "uint32"),
        ("healthy", "boolean"),
        ("fault_bits", "uint32"),
        ("detail", "string"),
    ],
    SafetyState: [
        ("header", "std_msgs/Header"),
        ("state", "uint8"),
        ("reset_epoch", "uint32"),
        ("runtime_generation", "uint32"),
        ("active_command_source", "uint8"),
        ("command_valid", "boolean"),
        ("scan_fresh", "boolean"),
        ("odom_fresh", "boolean"),
        ("tf_valid", "boolean"),
        ("localization_valid", "boolean"),
        ("navigation_state_fresh", "boolean"),
        ("path_valid", "boolean"),
        ("motion_permitted", "boolean"),
        ("policy_alive", "boolean"),
        ("mcu_alive", "boolean"),
        ("estop_active", "boolean"),
        ("scan_age_ms", "uint32"),
        ("odom_age_ms", "uint32"),
        ("policy_heartbeat_age_ms", "uint32"),
        ("mcu_heartbeat_age_ms", "uint32"),
        ("command_age_ms", "uint32"),
        ("navigation_state_age_ms", "uint32"),
        ("fault_bits", "uint32"),
        ("intervention_reasons", "sequence<string>"),
        ("raw_command", "geometry_msgs/Twist"),
        ("limited_command", "geometry_msgs/Twist"),
        ("final_command", "geometry_msgs/Twist"),
    ],
    NavigationState: [
        ("header", "std_msgs/Header"),
        ("state", "uint8"),
        ("goal_id", "string"),
        ("path_sequence", "uint64"),
        ("reset_epoch", "uint32"),
        ("runtime_generation", "uint32"),
        ("source_instance_id", "uint64"),
        ("sequence", "uint64"),
        ("path_valid", "boolean"),
        ("motion_permitted", "boolean"),
        ("distance_remaining_m", "float"),
        ("error_code", "uint32"),
        ("detail", "string"),
    ],
    CommandEnvelope: [
        ("header", "std_msgs/Header"),
        ("source", "uint8"),
        ("sequence", "uint64"),
        ("reset_epoch", "uint32"),
        ("runtime_generation", "uint32"),
        ("source_instance_id", "uint64"),
        ("twist", "geometry_msgs/Twist"),
    ],
}


def test_all_messages_import() -> None:
    for message_type in (
        Heartbeat,
        SafetyState,
        NavigationState,
        CommandEnvelope,
    ):
        assert isinstance(message_type, type)


def test_constants_match_contract() -> None:
    for message_type, expected_constants in EXPECTED_CONSTANTS.items():
        for name, value in expected_constants.items():
            assert getattr(message_type, name) == value


def test_field_names_types_and_order_match_contract() -> None:
    for message_type, expected_fields in EXPECTED_FIELDS.items():
        actual_fields = list(
            message_type.get_fields_and_field_types().items()
        )
        assert actual_fields == expected_fields
