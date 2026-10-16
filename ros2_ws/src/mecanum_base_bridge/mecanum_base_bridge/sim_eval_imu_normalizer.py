"""Pure-Python validation and covariance normalization for a staging IMU."""

from dataclasses import dataclass
import math


IMU_ORIENTATION_COVARIANCE_DIAGONAL = (1000000.0, 1000000.0, 0.007615435)
IMU_ANGULAR_VELOCITY_COVARIANCE_DIAGONAL = (1000000.0, 1000000.0, 0.01)
IMU_LINEAR_ACCELERATION_COVARIANCE_DIAGONAL = (1000000.0, 1000000.0, 1000000.0)


def _finite_number(value):
    return type(value) in (int, float) and math.isfinite(value)


def _stamp_parts(message):
    try:
        sec, nanosec = message.header.stamp.sec, message.header.stamp.nanosec
    except AttributeError:
        return None
    if type(sec) is not int or type(nanosec) is not int:
        return None
    if not 0 <= sec <= 2_147_483_647 or not 0 <= nanosec < 1_000_000_000:
        return None
    return sec, nanosec, sec * 1_000_000_000 + nanosec


def _vector3_values(value):
    try:
        result = (value.x, value.y, value.z)
    except AttributeError:
        return None
    return result if all(_finite_number(item) for item in result) else None


def _covariance_matrix(diagonal):
    values = [0.0] * 9
    for index, value in enumerate(diagonal):
        values[index * 3 + index] = value
    return tuple(values)


@dataclass(frozen=True)
class NormalizedImuSample:
    stamp_sec: int
    stamp_nanosec: int
    orientation_xyzw: tuple[float, float, float, float]
    angular_velocity_xyz: tuple[float, float, float]
    linear_acceleration_xyz: tuple[float, float, float]
    orientation_covariance: tuple[float, ...]
    angular_velocity_covariance: tuple[float, ...]
    linear_acceleration_covariance: tuple[float, ...]
    header_frame_id: str = "base_link"
    publishes_tf: bool = False


class SimEvalImuNormalizer:
    def __init__(self):
        self._last_stamp_ns = None

    def process(self, message):
        stamp = _stamp_parts(message)
        if stamp is None:
            return None
        sec, nanosec, stamp_ns = stamp
        try:
            if message.header.frame_id != "base_link":
                return None
            orientation = message.orientation
            quaternion = (orientation.x, orientation.y, orientation.z, orientation.w)
        except AttributeError:
            return None
        if not all(_finite_number(value) for value in quaternion):
            return None
        norm = math.sqrt(sum(value * value for value in quaternion))
        if not math.isfinite(norm) or not 0.999 <= norm <= 1.001:
            return None
        angular = _vector3_values(getattr(message, "angular_velocity", None))
        acceleration = _vector3_values(getattr(message, "linear_acceleration", None))
        if angular is None or acceleration is None:
            return None
        if self._last_stamp_ns is not None and stamp_ns <= self._last_stamp_ns:
            return None
        sample = NormalizedImuSample(
            sec,
            nanosec,
            tuple(quaternion),
            angular,
            acceleration,
            _covariance_matrix(IMU_ORIENTATION_COVARIANCE_DIAGONAL),
            _covariance_matrix(IMU_ANGULAR_VELOCITY_COVARIANCE_DIAGONAL),
            _covariance_matrix(IMU_LINEAR_ACCELERATION_COVARIANCE_DIAGONAL),
        )
        self._last_stamp_ns = stamp_ns
        return sample
