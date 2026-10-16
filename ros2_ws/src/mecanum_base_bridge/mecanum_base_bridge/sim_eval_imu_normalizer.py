"""Pure-Python validation and covariance assignment for sim_eval IMU samples."""

from dataclasses import dataclass
import math


FRAME_ID = "base_link"
QUATERNION_NORM_BOUNDS = (0.999, 1.001)
ORIENTATION_COVARIANCE_DIAGONAL = (1000000.0, 1000000.0, 0.007615435)
ANGULAR_VELOCITY_COVARIANCE_DIAGONAL = (1000000.0, 1000000.0, 0.01)
LINEAR_ACCELERATION_COVARIANCE_DIAGONAL = (1000000.0, 1000000.0, 1000000.0)


@dataclass(frozen=True)
class NormalizedImuSample:
    stamp_ns: int
    frame_id: str
    orientation_xyzw: tuple
    angular_velocity_xyz: tuple
    linear_acceleration_xyz: tuple
    orientation_covariance: tuple
    angular_velocity_covariance: tuple
    linear_acceleration_covariance: tuple
    publishes_tf: bool = False


def _finite_real(value):
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    try:
        return math.isfinite(value)
    except (OverflowError, TypeError):
        return False


def _diagonal_matrix(diagonal):
    return tuple(diagonal[row] if row == column else 0.0
                 for row in range(len(diagonal)) for column in range(len(diagonal)))


def _stamp_ns(message):
    try:
        stamp = message.header.stamp
        sec, nanosec = stamp.sec, stamp.nanosec
    except (AttributeError, TypeError):
        return None
    if (type(sec) is not int or type(nanosec) is not int or sec < 0 or sec > 2_147_483_647
            or nanosec < 0 or nanosec >= 1_000_000_000):
        return None
    return sec * 1_000_000_000 + nanosec


class SimEvalImuNormalizer:
    """Drop invalid or non-monotonic IMU samples; never repair source values."""

    def __init__(self):
        self._last_stamp_ns = None

    @property
    def last_stamp_ns(self):
        return self._last_stamp_ns

    def process(self, message):
        stamp_ns = _stamp_ns(message)
        try:
            frame_id = message.header.frame_id
            orientation = message.orientation
            angular = message.angular_velocity
            acceleration = message.linear_acceleration
            q = (orientation.x, orientation.y, orientation.z, orientation.w)
            w = (angular.x, angular.y, angular.z)
            a = (acceleration.x, acceleration.y, acceleration.z)
        except (AttributeError, TypeError):
            return None
        if stamp_ns is None or frame_id != FRAME_ID:
            return None
        if not all(_finite_real(value) for value in q + w + a):
            return None
        norm = math.sqrt(sum(float(value) * float(value) for value in q))
        if not math.isfinite(norm) or not QUATERNION_NORM_BOUNDS[0] <= norm <= QUATERNION_NORM_BOUNDS[1]:
            return None
        if self._last_stamp_ns is not None and stamp_ns <= self._last_stamp_ns:
            return None
        sample = NormalizedImuSample(
            stamp_ns=stamp_ns,
            frame_id=FRAME_ID,
            orientation_xyzw=tuple(float(value) for value in q),
            angular_velocity_xyz=tuple(float(value) for value in w),
            linear_acceleration_xyz=tuple(float(value) for value in a),
            orientation_covariance=_diagonal_matrix(ORIENTATION_COVARIANCE_DIAGONAL),
            angular_velocity_covariance=_diagonal_matrix(ANGULAR_VELOCITY_COVARIANCE_DIAGONAL),
            linear_acceleration_covariance=_diagonal_matrix(LINEAR_ACCELERATION_COVARIANCE_DIAGONAL),
        )
        self._last_stamp_ns = stamp_ns
        return sample
