"""Pure conversion of an upstream-verified LaserScan object to an OIC snapshot."""

import math

from .v3_ingress_binding_types import IngressMessageBinding
from .v3_snapshot_types import (
    FRAME_TF_CONTRACT_ID,
    LIDAR_CONTRACT_ID,
    LIDAR_FRAME,
    ActiveLifecycleConfigContext,
    LidarSnapshot,
)


EXPECTED_LIDAR_TOPIC = "/scan"
EXPECTED_LIDAR_TYPE = "sensor_msgs/msg/LaserScan"


def adapt_lidar_message(message: object, *, binding: IngressMessageBinding,
                        context: ActiveLifecycleConfigContext) -> LidarSnapshot | None:
    """Convert only an exact-frame scan using one injected sectorization callback."""
    try:
        if type(binding) is not IngressMessageBinding:
            return None
        if type(context) is not ActiveLifecycleConfigContext:
            return None
        if (binding.expected_topic != EXPECTED_LIDAR_TOPIC
                or binding.expected_type != EXPECTED_LIDAR_TYPE
                or binding.expected_frame_id != LIDAR_FRAME
                or binding.expected_child_frame_id is not None
                or binding.converter is None):
            return None
        if type(message) is not binding.expected_message_class:
            return None
        header = message.header
        frame_id = header.frame_id
        if type(frame_id) is not str or frame_id != LIDAR_FRAME:
            return None
        sectors = binding.converter(message)
        if type(sectors) is not tuple or len(sectors) != 72:
            return None
        if any(type(value) is not float or not math.isfinite(value) for value in sectors):
            return None
        return LidarSnapshot(
            contract_id=LIDAR_CONTRACT_ID,
            frame_contract_id=FRAME_TF_CONTRACT_ID,
            episode_generation=context.episode_generation,
            reset_epoch=context.reset_epoch,
            runtime_generation=context.runtime_generation,
            config_hash=context.config_hash,
            frame_id=frame_id,
            sectors=sectors,
            topic_claim=EXPECTED_LIDAR_TOPIC,
            type_claim=EXPECTED_LIDAR_TYPE,
        )
    except Exception:
        return None
