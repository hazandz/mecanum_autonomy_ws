"""Pure-Python static contract checks for sim_eval wheel and IMU ingress."""

from collections.abc import Mapping


SCHEMA = "mecanum_sim_eval_wheel_imu_ingress_static/v1"
PROFILE = "sim_eval"
CLASSIFICATION = "STATIC_CONTRACT_ONLY"
RUNTIME_ELIGIBLE = False
USE_SIM_TIME = True

WHEEL_TOPIC = "/wheel/odometry_raw"
WHEEL_MESSAGE_TYPE = "nav_msgs/msg/Odometry"
WHEEL_HEADER_FRAME = "odom"
WHEEL_CHILD_FRAME = "base_link"
WHEEL_PUBLISHES_TF = False

IMU_TOPIC = "/imu/data"
IMU_MESSAGE_TYPE = "sensor_msgs/msg/Imu"
IMU_HEADER_FRAME = "__PENDING_IMU_GEOMETRY_SOURCE_PIN__"
IMU_PUBLISHES_TF = False

PENDING_SIM_WHEEL_ENDPOINT = "PENDING_SIM_WHEEL_ENDPOINT_PIN"
PENDING_SIM_IMU_ENDPOINT = "PENDING_SIM_IMU_ENDPOINT_PIN"
PENDING_SENSOR_TIMING = "PENDING_S2_SENSOR_TIMING_DECISION"

FORBIDDEN_INPUT_TOPICS = ("/odom", "/ground_truth/odom")
FORBIDDEN_TF_EDGES = ("map -> odom", "odom -> base_link")
FORBIDDEN_FRAME_ALIASES = ("base_scan", "rplidar_link")


class StaticIngressContractError(ValueError):
    """Raised when an ingress descriptor differs from the approved static contract."""


def _mapping(value, label):
    if not isinstance(value, Mapping):
        raise StaticIngressContractError(f"{label} must be a mapping")
    return value


def _exact_keys(value, expected, label):
    if set(value) != set(expected):
        raise StaticIngressContractError(f"{label} has missing or unexpected fields")


def _literal(value, expected, label):
    if type(value) is not type(expected) or value != expected:
        raise StaticIngressContractError(f"{label} does not match the static contract")


def validate_sim_eval_wheel_imu_ingress_descriptor(descriptor):
    """Validate one caller-supplied mapping; performs no I/O or runtime work."""
    root = _mapping(descriptor, "descriptor")
    _exact_keys(
        root,
        {
            "schema",
            "profile",
            "classification",
            "runtime_eligible",
            "use_sim_time",
            "wheel_odometry",
            "imu",
            "source_bindings",
            "prohibitions",
        },
        "descriptor",
    )
    for field, expected in (
        ("schema", SCHEMA),
        ("profile", PROFILE),
        ("classification", CLASSIFICATION),
        ("runtime_eligible", RUNTIME_ELIGIBLE),
        ("use_sim_time", USE_SIM_TIME),
    ):
        _literal(root[field], expected, field)

    wheel = _mapping(root["wheel_odometry"], "wheel_odometry")
    _exact_keys(
        wheel,
        {"topic", "ros_message_type", "header_frame_id", "child_frame_id", "publishes_tf"},
        "wheel_odometry",
    )
    for field, expected in (
        ("topic", WHEEL_TOPIC),
        ("ros_message_type", WHEEL_MESSAGE_TYPE),
        ("header_frame_id", WHEEL_HEADER_FRAME),
        ("child_frame_id", WHEEL_CHILD_FRAME),
        ("publishes_tf", WHEEL_PUBLISHES_TF),
    ):
        _literal(wheel[field], expected, f"wheel_odometry.{field}")

    imu = _mapping(root["imu"], "imu")
    _exact_keys(imu, {"topic", "ros_message_type", "header_frame_id", "publishes_tf"}, "imu")
    for field, expected in (
        ("topic", IMU_TOPIC),
        ("ros_message_type", IMU_MESSAGE_TYPE),
        ("header_frame_id", IMU_HEADER_FRAME),
        ("publishes_tf", IMU_PUBLISHES_TF),
    ):
        _literal(imu[field], expected, f"imu.{field}")

    bindings = _mapping(root["source_bindings"], "source_bindings")
    _exact_keys(
        bindings,
        {"sim_wheel_endpoint", "sim_imu_endpoint", "sensor_timing", "runtime_eligibility"},
        "source_bindings",
    )
    for field, expected in (
        ("sim_wheel_endpoint", PENDING_SIM_WHEEL_ENDPOINT),
        ("sim_imu_endpoint", PENDING_SIM_IMU_ENDPOINT),
        ("sensor_timing", PENDING_SENSOR_TIMING),
        ("runtime_eligibility", False),
    ):
        _literal(bindings[field], expected, f"source_bindings.{field}")

    prohibitions = _mapping(root["prohibitions"], "prohibitions")
    _exact_keys(
        prohibitions,
        {"no_tf_publication", "forbidden_input_topics", "forbidden_tf_edges", "forbidden_frame_aliases"},
        "prohibitions",
    )
    _literal(prohibitions["no_tf_publication"], True, "prohibitions.no_tf_publication")
    _literal(prohibitions["forbidden_input_topics"], list(FORBIDDEN_INPUT_TOPICS), "forbidden_input_topics")
    _literal(prohibitions["forbidden_tf_edges"], list(FORBIDDEN_TF_EDGES), "forbidden_tf_edges")
    _literal(prohibitions["forbidden_frame_aliases"], list(FORBIDDEN_FRAME_ALIASES), "forbidden_frame_aliases")
    return None
