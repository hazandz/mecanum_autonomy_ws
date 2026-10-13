"""Pure conversion of an upstream-transformed Nav2 Path to LocalReference."""

import math

from .v3_ingress_binding_types import IngressMessageBinding
from .v3_snapshot_types import (
    BASE_FRAME,
    FRAME_TF_CONTRACT_ID,
    LOCAL_REFERENCE_CONTRACT_ID,
    ActiveLifecycleConfigContext,
    LocalReferenceSnapshot,
)


EXPECTED_PATH_TYPE = "nav_msgs/msg/Path"
EXPECTED_PATH_SOURCE_FRAME = "map"


def adapt_local_reference_message(
    message: object, *, binding: IngressMessageBinding,
    context: ActiveLifecycleConfigContext,
) -> LocalReferenceSnapshot | None:
    """Project a map-frame path only through its injected verified callback."""
    try:
        if type(binding) is not IngressMessageBinding:
            return None
        if type(context) is not ActiveLifecycleConfigContext:
            return None
        if (binding.expected_topic is not None
                or binding.expected_type != EXPECTED_PATH_TYPE
                or binding.expected_frame_id != EXPECTED_PATH_SOURCE_FRAME
                or binding.expected_child_frame_id is not None
                or binding.converter is None):
            return None
        if type(message) is not binding.expected_message_class:
            return None
        header = message.header
        frame_id = header.frame_id
        if type(frame_id) is not str or frame_id != EXPECTED_PATH_SOURCE_FRAME:
            return None
        features = binding.converter(message)
        if type(features) is not tuple or len(features) != 3:
            return None
        if any(type(value) is not float or not math.isfinite(value) for value in features):
            return None
        return LocalReferenceSnapshot(
            contract_id=LOCAL_REFERENCE_CONTRACT_ID,
            frame_contract_id=FRAME_TF_CONTRACT_ID,
            episode_generation=context.episode_generation,
            reset_epoch=context.reset_epoch,
            runtime_generation=context.runtime_generation,
            config_hash=context.config_hash,
            frame_id=BASE_FRAME,
            features=features,
            topic_claim=None,
            type_claim=EXPECTED_PATH_TYPE,
        )
    except Exception:
        return None
