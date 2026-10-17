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


def _diagnostic_value(value):
    """Return a JSON-safe representation without repairing source values."""
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if math.isnan(value):
            return "NaN"
        if math.isinf(value):
            return "+Infinity" if value > 0 else "-Infinity"
        return value
    return repr(value)


class SimEvalImuNormalizer:
    """Drop invalid or non-monotonic IMU samples; never repair source values."""

    def __init__(self):
        self._last_stamp_ns = None

    @property
    def last_stamp_ns(self):
        return self._last_stamp_ns

    def process(self, message):
        sample, _ = self.process_with_diagnostics(message)
        return sample

    def process_with_diagnostics(self, message):
        """Process one IMU message and return bounded rejection diagnostics.

        The first rejection gate follows the same fail-closed order as the
        original ``process`` contract. Calling this method does not publish,
        repair, or retain the input message.
        """
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
            return None, {
                "accepted": False,
                "rejection_gate": "payload_structure",
                "stamp": None,
                "frame_id": None,
                "finite_values": None,
                "values": None,
                "quaternion_norm": None,
                "monotonic_timestamp": None,
            }

        try:
            raw_stamp = message.header.stamp
            stamp_record = {
                "sec": _diagnostic_value(raw_stamp.sec),
                "nanosec": _diagnostic_value(raw_stamp.nanosec),
                "stamp_ns": stamp_ns,
            }
        except (AttributeError, TypeError):
            stamp_record = {"sec": None, "nanosec": None, "stamp_ns": None}

        q_finite = all(_finite_real(value) for value in q)
        w_finite = all(_finite_real(value) for value in w)
        a_finite = all(_finite_real(value) for value in a)
        norm = math.sqrt(sum(float(value) * float(value) for value in q)) if q_finite else None
        monotonic = None if stamp_ns is None else (
            self._last_stamp_ns is None or stamp_ns > self._last_stamp_ns
        )
        diagnostics = {
            "accepted": False,
            "rejection_gate": None,
            "stamp": stamp_record,
            "frame_id": _diagnostic_value(frame_id),
            "finite_values": {
                "orientation_xyzw": q_finite,
                "angular_velocity_xyz": w_finite,
                "linear_acceleration_xyz": a_finite,
                "all": q_finite and w_finite and a_finite,
            },
            "values": {
                "orientation_xyzw": [_diagnostic_value(value) for value in q],
                "angular_velocity_xyz": [_diagnostic_value(value) for value in w],
                "linear_acceleration_xyz": [_diagnostic_value(value) for value in a],
            },
            "quaternion_norm": _diagnostic_value(norm),
            "monotonic_timestamp": {
                "last_accepted_stamp_ns": self._last_stamp_ns,
                "strictly_increasing": monotonic,
            },
        }
        if stamp_ns is None:
            diagnostics["rejection_gate"] = "stamp"
            return None, diagnostics
        if frame_id != FRAME_ID:
            diagnostics["rejection_gate"] = "frame_id"
            return None, diagnostics
        if not (q_finite and w_finite and a_finite):
            diagnostics["rejection_gate"] = "finite_values"
            return None, diagnostics
        if norm is None or not math.isfinite(norm) or not QUATERNION_NORM_BOUNDS[0] <= norm <= QUATERNION_NORM_BOUNDS[1]:
            diagnostics["rejection_gate"] = "quaternion_norm"
            return None, diagnostics
        if not monotonic:
            diagnostics["rejection_gate"] = "monotonic_timestamp"
            return None, diagnostics
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
        diagnostics["accepted"] = True
        return sample, diagnostics
