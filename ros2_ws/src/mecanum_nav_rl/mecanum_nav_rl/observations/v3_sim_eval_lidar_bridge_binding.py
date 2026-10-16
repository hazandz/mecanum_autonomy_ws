"""Nonexecuting WP08 public-boundary guard for the existing V3 LiDAR adapter."""

from collections.abc import Mapping

from .v3_ingress_binding_types import IngressMessageBinding
from .v3_lidar_ingress_adapter import adapt_lidar_message
from .v3_snapshot_types import ActiveLifecycleConfigContext, LidarSnapshot


SCHEMA = "mecanum_sim_eval_lidar_scan_bridge_static/v1"
PROFILE = "sim_eval"
CLASSIFICATION = "STATIC_CONTRACT_ONLY"
RUNTIME_ELIGIBLE = False
USE_SIM_TIME = True

TRANSPORT_DIRECTION = "GZ_TO_ROS"
PENDING_GZ_ENDPOINT = "PENDING_GZ_LIDAR_TRANSPORT_ENDPOINT_PIN"
GZ_MESSAGE_TYPE = "gz.msgs.LaserScan"
PENDING_BRIDGE_IMPLEMENTATION = "PENDING_PROFILE_SPECIFIC_ROS_GZ_BRIDGE_SOURCE_PIN"
PENDING_SCAN_TIMING = "PENDING_S2_SENSOR_TIMING_DECISION"

ROS_SCAN_TOPIC = "/scan"
ROS_SCAN_TYPE = "sensor_msgs/msg/LaserScan"
LIDAR_FRAME = "lidar_frame"
ROS_SCAN_PUBLISHES_TF = False

BASE_TO_LIDAR_OWNER = "robot_state_publisher"
BASE_TO_LIDAR_EDGE = "base_link -> lidar_frame"
BRIDGE_PUBLISHES_TF = False


def _boundary_matches(claim):
    """Check only WP08's public bridge boundary, not its Gazebo provenance."""
    if not isinstance(claim, Mapping):
        return False
    for key, expected in (
        ("schema", SCHEMA),
        ("profile", PROFILE),
        ("classification", CLASSIFICATION),
        ("runtime_eligible", RUNTIME_ELIGIBLE),
        ("use_sim_time", USE_SIM_TIME),
    ):
        value = claim.get(key)
        if type(value) is not type(expected) or value != expected:
            return False

    transport = claim.get("transport_binding")
    if not isinstance(transport, Mapping):
        return False
    for key, expected in (
        ("direction", TRANSPORT_DIRECTION),
        ("gz_transport_endpoint", PENDING_GZ_ENDPOINT),
        ("gz_message_type", GZ_MESSAGE_TYPE),
        ("bridge_implementation", PENDING_BRIDGE_IMPLEMENTATION),
        ("observed_scan_timing", PENDING_SCAN_TIMING),
    ):
        value = transport.get(key)
        if type(value) is not type(expected) or value != expected:
            return False

    ros_output = claim.get("ros_output")
    if not isinstance(ros_output, Mapping):
        return False
    for key, expected in (
        ("topic", ROS_SCAN_TOPIC),
        ("ros_message_type", ROS_SCAN_TYPE),
        ("required_header_frame_id", LIDAR_FRAME),
        ("publishes_tf", ROS_SCAN_PUBLISHES_TF),
    ):
        value = ros_output.get(key)
        if type(value) is not type(expected) or value != expected:
            return False

    tf_contract = claim.get("tf_contract")
    if not isinstance(tf_contract, Mapping):
        return False
    for key, expected in (
        ("base_to_lidar_owner", BASE_TO_LIDAR_OWNER),
        ("required_static_edge", BASE_TO_LIDAR_EDGE),
        ("bridge_publishes_tf", BRIDGE_PUBLISHES_TF),
    ):
        value = tf_contract.get(key)
        if type(value) is not type(expected) or value != expected:
            return False
    return True


def build_sim_eval_lidar_binding_from_static_bridge_claim(
    claim, *, expected_message_class, converter
):
    """Build an injected binding only for the exact pending WP08 boundary.

    This function neither imports nor resolves a ROS message class and never
    invokes the injected converter. Gazebo sensor provenance is not pinned here.
    """
    try:
        if not _boundary_matches(claim):
            return None
        if not isinstance(expected_message_class, type) or not callable(converter):
            return None
        return IngressMessageBinding(
            expected_message_class=expected_message_class,
            expected_topic=ROS_SCAN_TOPIC,
            expected_type=ROS_SCAN_TYPE,
            expected_frame_id=LIDAR_FRAME,
            converter=converter,
            expected_child_frame_id=None,
        )
    except Exception:
        return None


def adapt_sim_eval_lidar_from_static_bridge_claim(
    message,
    claim,
    *,
    expected_message_class,
    converter,
    context,
) -> LidarSnapshot | None:
    """Delegate admitted messages to the existing V3 adapter, fail-closed."""
    binding = build_sim_eval_lidar_binding_from_static_bridge_claim(
        claim,
        expected_message_class=expected_message_class,
        converter=converter,
    )
    if binding is None:
        return None
    try:
        return adapt_lidar_message(message, binding=binding, context=context)
    except Exception:
        return None
