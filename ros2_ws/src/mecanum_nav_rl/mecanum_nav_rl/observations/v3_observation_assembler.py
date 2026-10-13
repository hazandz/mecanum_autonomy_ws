"""Pure-core 81-value assembler for already validated immutable snapshots."""

from dataclasses import dataclass

import numpy as np

from .v3_snapshot_validation import ValidatedObservationInputs, revalidate_inputs


@dataclass(frozen=True, slots=True)
class ObservationAssembly:
    ready: bool
    vector: np.ndarray | None

    def __post_init__(self):
        if type(self.ready) is not bool:
            raise TypeError("ready must be bool")
        if not self.ready:
            if self.vector is not None:
                raise ValueError("non-ready assembly cannot carry a partial vector")
            return
        if (type(self.vector) is not np.ndarray or self.vector.shape != (81,)
                or self.vector.dtype != np.dtype(np.float32) or self.vector.flags.writeable):
            raise ValueError("ready assembly requires a read-only float32 vector of length 81")


def assemble_observation(inputs):
    """Assemble all 81 features atomically, or return not-ready with no vector."""
    validated = revalidate_inputs(inputs)
    if validated is None:
        return ObservationAssembly(False, None)

    values = (validated.lidar.sectors + validated.local_reference.features
              + validated.measured_twist.components + validated.receipt.final_command)
    try:
        with np.errstate(over="ignore", invalid="ignore"):
            vector = np.asarray(values, dtype=np.float32)
    except (OverflowError, TypeError, ValueError):
        return ObservationAssembly(False, None)
    if vector.shape != (81,) or not bool(np.isfinite(vector).all()):
        return ObservationAssembly(False, None)
    vector.setflags(write=False)
    return ObservationAssembly(True, vector)
