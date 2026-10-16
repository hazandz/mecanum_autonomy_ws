"""Offline mecanum wheel-odometry integration for sim_eval staging samples."""

from collections.abc import Sequence
from dataclasses import dataclass
import math


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

POSE_COVARIANCE_DIAGONAL = (0.0025, 0.0025, 1000000.0, 1000000.0, 1000000.0, 0.007615435)
TWIST_COVARIANCE_DIAGONAL = (0.01, 0.01, 1000000.0, 1000000.0, 1000000.0, 0.04)


@dataclass(frozen=True)
class WheelOdometrySample:
    stamp_ns: int
    frame_id: str
    child_frame_id: str
    x: float
    y: float
    yaw: float
    linear_x: float
    linear_y: float
    angular_z: float
    pose_covariance: tuple
    twist_covariance: tuple
    publishes_tf: bool = False


def _is_sequence(value):
    return isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray))


def _finite_real(value):
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    try:
        return math.isfinite(value)
    except (OverflowError, TypeError):
        return False


def _diagonal_matrix(diagonal):
    return tuple(diagonal[row] if row == column else 0.0 for row in range(6) for column in range(6))


class SimEvalWheelOdometryEmulator:
    """Integrate only adjacent, structurally valid, trusted JointState samples."""

    def __init__(self):
        self._last_stamp_ns = None
        self._x = 0.0
        self._y = 0.0
        self._yaw = 0.0

    @property
    def trusted_pose(self):
        return self._x, self._y, self._yaw

    @property
    def last_stamp_ns(self):
        return self._last_stamp_ns

    def clear_interval_keep_trusted_pose(self):
        self._last_stamp_ns = None

    def reset_pose_and_baseline(self):
        self._last_stamp_ns = None
        self._x = 0.0
        self._y = 0.0
        self._yaw = 0.0

    @staticmethod
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

    def _invalid(self):
        self.clear_interval_keep_trusted_pose()
        return None

    def process(self, message):
        """Return an odometry-shaped pure value, or None for an untrusted sample."""
        try:
            names = message.name
            velocities = message.velocity
        except (AttributeError, TypeError):
            return self._invalid()
        if not _is_sequence(names) or not _is_sequence(velocities):
            return self._invalid()
        if any(not isinstance(name, str) for name in names) or len(names) != len(velocities):
            return self._invalid()
        required = tuple(JOINT_NAMES[key] for key in LOGICAL_WHEEL_ORDER)
        if any(names.count(joint) != 1 for joint in required):
            return self._invalid()
        rates_by_name = {}
        for joint, rate in zip(names, velocities):
            if joint in required:
                if not _finite_real(rate):
                    return self._invalid()
                rates_by_name[joint] = float(rate)
        rates = tuple(rates_by_name[JOINT_NAMES[key]] * sign
                      for key, sign in zip(LOGICAL_WHEEL_ORDER, WHEEL_SIGNS))

        stamp_ns = self._stamp_ns(message)
        if stamp_ns is None:
            return self._invalid()
        if self._last_stamp_ns is not None and stamp_ns < self._last_stamp_ns:
            self.reset_pose_and_baseline()
            return None
        if self._last_stamp_ns is None:
            self._last_stamp_ns = stamp_ns
            return None
        if stamp_ns == self._last_stamp_ns:
            return self._invalid()
        dt = (stamp_ns - self._last_stamp_ns) / 1_000_000_000.0
        if not _finite_real(dt) or dt <= 0.0 or dt > MAX_SOURCE_GAP_S:
            return self._invalid()

        fl, fr, rl, rr = rates
        radius_quarter = WHEEL_RADIUS_M / 4.0
        vx = radius_quarter * (fl + fr + rl + rr)
        vy = radius_quarter * (-fl + fr + rl - rr)
        wz = WHEEL_RADIUS_M / (4.0 * (WHEELBASE_M + TRACK_M)) * (-fl + fr - rl + rr)
        if not all(math.isfinite(value) for value in (vx, vy, wz)):
            return self._invalid()

        theta = wz * dt
        if abs(wz) < 1e-12:
            body_dx, body_dy = vx * dt, vy * dt
        else:
            sine_over_w = math.sin(theta) / wz
            one_minus_cos_over_w = (1.0 - math.cos(theta)) / wz
            body_dx = sine_over_w * vx - one_minus_cos_over_w * vy
            body_dy = one_minus_cos_over_w * vx + sine_over_w * vy
        cosine, sine = math.cos(self._yaw), math.sin(self._yaw)
        next_x = self._x + cosine * body_dx - sine * body_dy
        next_y = self._y + sine * body_dx + cosine * body_dy
        next_yaw = math.atan2(math.sin(self._yaw + theta), math.cos(self._yaw + theta))
        result_values = (next_x, next_y, next_yaw, vx, vy, wz, body_dx, body_dy)
        if not all(math.isfinite(value) for value in result_values):
            return self._invalid()

        sample = WheelOdometrySample(
            stamp_ns=stamp_ns,
            frame_id="odom",
            child_frame_id="base_link",
            x=next_x,
            y=next_y,
            yaw=next_yaw,
            linear_x=vx,
            linear_y=vy,
            angular_z=wz,
            pose_covariance=_diagonal_matrix(POSE_COVARIANCE_DIAGONAL),
            twist_covariance=_diagonal_matrix(TWIST_COVARIANCE_DIAGONAL),
        )
        self._x, self._y, self._yaw, self._last_stamp_ns = next_x, next_y, next_yaw, stamp_ns
        return sample
