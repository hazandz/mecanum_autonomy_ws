"""Pure extraction of exact Odometry twist fields to a measured-twist snapshot."""

import math

from .v3_ingress_binding_types import IngressMessageBinding
from .v3_snapshot_types import (
    BASE_FRAME,
    FRAME_TF_CONTRACT_ID,
    MEASURED_TWIST_CONTRACT_ID,
    ActiveLifecycleConfigContext,
    MeasuredTwistSnapshot,
)


EXPECTED_ODOMETRY_TOPIC = "/odometry/filtered"
EXPECTED_ODOMETRY_TYPE = "nav_msgs/msg/Odometry"
EXPECTED_ODOMETRY_FRAME = "odom"


def adapt_measured_twist_message(
    message: object, *, binding: IngressMessageBinding,
    context: ActiveLifecycleConfigContext,
) -> MeasuredTwistSnapshot | None:
    """Extract three exact float fields; do not add validity or freshness policy."""
    try:
        if type(binding) is not IngressMessageBinding:
            return None
        if type(context) is not ActiveLifecycleConfigContext:
            return None
        if (binding.expected_topic != EXPECTED_ODOMETRY_TOPIC
                or binding.expected_type != EXPECTED_ODOMETRY_TYPE
                or binding.expected_frame_id != EXPECTED_ODOMETRY_FRAME
                or binding.expected_child_frame_id != BASE_FRAME
                or binding.converter is not None):
            return None
        if type(message) is not binding.expected_message_class:
            return None
        header = message.header
        frame_id = header.frame_id
        child_frame_id = message.child_frame_id
        if (type(frame_id) is not str or frame_id != EXPECTED_ODOMETRY_FRAME
                or type(child_frame_id) is not str or child_frame_id != BASE_FRAME):
            return None
        twist = message.twist.twist
        components = (twist.linear.x, twist.linear.y, twist.angular.z)
        if any(type(value) is not float or not math.isfinite(value) for value in components):
            return None
        return MeasuredTwistSnapshot(
            contract_id=MEASURED_TWIST_CONTRACT_ID,
            frame_contract_id=FRAME_TF_CONTRACT_ID,
            episode_generation=context.episode_generation,
            reset_epoch=context.reset_epoch,
            runtime_generation=context.runtime_generation,
            config_hash=context.config_hash,
            frame_id=BASE_FRAME,
            components=components,
            topic_claim=EXPECTED_ODOMETRY_TOPIC,
            type_claim=EXPECTED_ODOMETRY_TYPE,
        )
    except Exception:
        return None
