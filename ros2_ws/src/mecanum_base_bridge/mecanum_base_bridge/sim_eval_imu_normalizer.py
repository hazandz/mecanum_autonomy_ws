"""Pure-Python validation for the configured sim_eval IMU source."""

from dataclasses import dataclass
import math
from typing import Optional, Sequence


IMU_FRAME_ID = "base_link"
QUATERNION_NORM_MIN = 0.999
QUATERNION_NORM_MAX = 1.001
ORIENTATION_COVARIANCE_DIAGONAL = (1_000_000.0, 1_000_000.0, 0.007615435)
ANGULAR_VELOCITY_COVARIANCE_DIAGONAL = (1_000_000.0, 1_000_000.0, 0.01)
LINEAR_ACCELERATION_COVARIANCE_DIAGONAL = (1_000_000.0, 1_000_000.0, 1_000_000.0)


@dataclass(frozen=True)
class NormalizedImuSample:
    stamp_ns: int
    frame_id: str
    orientation_xyzw: tuple
    angular_velocity_xyz: tuple
    linear_acceleration_xyz: tuple


def covariance_matrix(diagonal):
    matrix = [0.0] * 9
    for index, value in enumerate(diagonal):
        matrix[index * 3 + index] = value
    return tuple(matrix)


ORIENTATION_COVARIANCE = covariance_matrix(ORIENTATION_COVARIANCE_DIAGONAL)
ANGULAR_VELOCITY_COVARIANCE = covariance_matrix(ANGULAR_VELOCITY_COVARIANCE_DIAGONAL)
LINEAR_ACCELERATION_COVARIANCE = covariance_matrix(LINEAR_ACCELERATION_COVARIANCE_DIAGONAL)


class ImuNormalizer:
    """Accept valid base_link IMU samples without altering data or timestamp."""

    def __init__(self):
        self._last_stamp_ns = None

    def reset(self):
        self._last_stamp_ns = None

    def process(self, stamp_ns: int, frame_id: str, orientation_xyzw: Sequence[float],
                angular_velocity_xyz: Sequence[float], linear_acceleration_xyz: Sequence[float]) -> Optional[NormalizedImuSample]:
        if type(stamp_ns) is not int or stamp_ns < 0 or frame_id != IMU_FRAME_ID:
            return None
        if self._last_stamp_ns is not None and stamp_ns <= self._last_stamp_ns:
            return None
        vectors = (orientation_xyzw, angular_velocity_xyz, linear_acceleration_xyz)
        if any(not isinstance(vector, (tuple, list)) or len(vector) != expected for vector, expected in zip(vectors, (4, 3, 3))):
            return None
        flattened = tuple(value for vector in vectors for value in vector)
        if any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) for value in flattened):
            return None
        orientation = tuple(float(value) for value in orientation_xyzw)
        norm = math.sqrt(sum(value * value for value in orientation))
        if not QUATERNION_NORM_MIN <= norm <= QUATERNION_NORM_MAX:
            return None
        self._last_stamp_ns = stamp_ns
        return NormalizedImuSample(
            stamp_ns=stamp_ns,
            frame_id=frame_id,
            orientation_xyzw=orientation,
            angular_velocity_xyz=tuple(float(value) for value in angular_velocity_xyz),
            linear_acceleration_xyz=tuple(float(value) for value in linear_acceleration_xyz),
        )
