"""Pure-Python wheel-state to planar odometry conversion for sim_eval."""

from dataclasses import dataclass
import math
from typing import Optional, Sequence


LOGICAL_WHEEL_ORDER = ("FL", "FR", "RL", "RR")
JOINT_NAMES = {
    "FL": "Wheel_LF_Joint",
    "FR": "Wheel_RF_Joint",
    "RL": "Wheel_LB_Joint",
    "RR": "Wheel_RB_Joint",
}
WHEEL_RADIUS_M = 0.0485
WHEELBASE_M = 0.216
TRACK_M = 0.22218
WHEEL_SIGNS = (1, 1, 1, 1)
MAX_SOURCE_GAP_S = 0.20

POSE_COVARIANCE_DIAGONAL = (0.0025, 0.0025, 1_000_000.0, 1_000_000.0, 1_000_000.0, 0.007615435)
TWIST_COVARIANCE_DIAGONAL = (0.01, 0.01, 1_000_000.0, 1_000_000.0, 1_000_000.0, 0.04)


@dataclass(frozen=True)
class WheelOdometrySample:
    stamp_ns: int
    x: float
    y: float
    yaw: float
    linear_x: float
    linear_y: float
    angular_z: float
    pose_covariance: tuple
    twist_covariance: tuple


def _covariance_matrix(diagonal):
    matrix = [0.0] * 36
    for index, value in enumerate(diagonal):
        matrix[index * 6 + index] = value
    return tuple(matrix)


POSE_COVARIANCE = _covariance_matrix(POSE_COVARIANCE_DIAGONAL)
TWIST_COVARIANCE = _covariance_matrix(TWIST_COVARIANCE_DIAGONAL)


class WheelOdometryEmulator:
    """Integrate accepted wheel velocities in SE(2); never publishes TF."""

    def __init__(self):
        self.reset()

    def reset(self):
        self._last_stamp_ns = None
        self._x = 0.0
        self._y = 0.0
        self._yaw = 0.0

    @property
    def pose(self):
        return (self._x, self._y, self._yaw)

    def process(self, names: Sequence[str], velocities: Sequence[float], stamp_ns: int) -> Optional[WheelOdometrySample]:
        """Return a sample only after a valid positive source interval."""
        if type(stamp_ns) is not int or stamp_ns < 0:
            return None

        if self._last_stamp_ns is not None:
            dt = (stamp_ns - self._last_stamp_ns) / 1_000_000_000.0
            if dt <= 0.0 or dt > MAX_SOURCE_GAP_S:
                self.reset()
                return None

        if not isinstance(names, (list, tuple)) or not isinstance(velocities, (list, tuple)):
            return None
        if len(names) != len(velocities):
            return None
        index_by_name = {}
        for index, name in enumerate(names):
            if name in JOINT_NAMES.values():
                if name in index_by_name:
                    return None
                index_by_name[name] = index
        if set(index_by_name) != set(JOINT_NAMES.values()):
            return None
        wheel_rates = []
        for logical_name in LOGICAL_WHEEL_ORDER:
            value = velocities[index_by_name[JOINT_NAMES[logical_name]]]
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                return None
            wheel_rates.append(float(value) * WHEEL_SIGNS[len(wheel_rates)])

        if self._last_stamp_ns is None:
            self._last_stamp_ns = stamp_ns
            return None

        w_fl, w_fr, w_rl, w_rr = wheel_rates
        radius = WHEEL_RADIUS_M
        linear_x = radius / 4.0 * (w_fl + w_fr + w_rl + w_rr)
        linear_y = radius / 4.0 * (-w_fl + w_fr + w_rl - w_rr)
        angular_z = radius / (4.0 * (WHEELBASE_M + TRACK_M)) * (-w_fl + w_fr - w_rl + w_rr)
        dt = (stamp_ns - self._last_stamp_ns) / 1_000_000_000.0

        theta = angular_z * dt
        if abs(angular_z) < 1e-12:
            body_dx = linear_x * dt
            body_dy = linear_y * dt
        else:
            sin_theta = math.sin(theta)
            one_minus_cos = 1.0 - math.cos(theta)
            body_dx = (sin_theta * linear_x - one_minus_cos * linear_y) / angular_z
            body_dy = (one_minus_cos * linear_x + sin_theta * linear_y) / angular_z
        cos_yaw = math.cos(self._yaw)
        sin_yaw = math.sin(self._yaw)
        self._x += cos_yaw * body_dx - sin_yaw * body_dy
        self._y += sin_yaw * body_dx + cos_yaw * body_dy
        self._yaw = math.atan2(math.sin(self._yaw + theta), math.cos(self._yaw + theta))
        self._last_stamp_ns = stamp_ns
        values = (self._x, self._y, self._yaw, linear_x, linear_y, angular_z)
        if not all(math.isfinite(value) for value in values):
            self.reset()
            return None
        return WheelOdometrySample(
            stamp_ns=stamp_ns,
            x=self._x,
            y=self._y,
            yaw=self._yaw,
            linear_x=linear_x,
            linear_y=linear_y,
            angular_z=angular_z,
            pose_covariance=POSE_COVARIANCE,
            twist_covariance=TWIST_COVARIANCE,
        )
