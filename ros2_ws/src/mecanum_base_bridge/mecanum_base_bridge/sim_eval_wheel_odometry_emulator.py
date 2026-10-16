"""Pure-Python wheel-velocity odometry with strict invalid-interval barriers."""

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
    stamp_sec: int
    stamp_nanosec: int
    x: float
    y: float
    yaw: float
    linear_x: float
    linear_y: float
    angular_z: float
    pose_covariance: tuple[float, ...]
    twist_covariance: tuple[float, ...]
    header_frame_id: str = "odom"
    child_frame_id: str = "base_link"
    publishes_tf: bool = False


def _finite_number(value):
    return type(value) in (int, float) and math.isfinite(value)


def _stamp_parts(message):
    try:
        stamp = message.header.stamp
        sec, nanosec = stamp.sec, stamp.nanosec
    except (AttributeError, TypeError):
        return None
    if type(sec) is not int or type(nanosec) is not int:
        return None
    if not 0 <= sec <= 2_147_483_647 or not 0 <= nanosec < 1_000_000_000:
        return None
    return sec, nanosec, sec * 1_000_000_000 + nanosec


def _covariance_matrix(diagonal):
    values = [0.0] * 36
    for index, value in enumerate(diagonal):
        values[index * 6 + index] = value
    return tuple(values)


class SimEvalWheelOdometryEmulator:
    """Convert staging JointState structure into odometry samples, never TF."""

    def __init__(self):
        self._x = 0.0
        self._y = 0.0
        self._yaw = 0.0
        self._last_stamp_ns = None

    @property
    def trusted_pose(self):
        return self._x, self._y, self._yaw

    def clear_interval_keep_trusted_pose(self):
        self._last_stamp_ns = None

    def reset_pose_and_baseline(self):
        self._last_stamp_ns = None
        self._x = self._y = self._yaw = 0.0

    def process(self, message):
        stamp = _stamp_parts(message)
        if stamp is None:
            self.clear_interval_keep_trusted_pose()
            return None
        sec, nanosec, stamp_ns = stamp
        if self._last_stamp_ns is not None and stamp_ns < self._last_stamp_ns:
            self.reset_pose_and_baseline()
            return None
        if self._last_stamp_ns is not None and stamp_ns == self._last_stamp_ns:
            self.clear_interval_keep_trusted_pose()
            return None

        try:
            names = message.name
            velocities = message.velocity
        except AttributeError:
            self.clear_interval_keep_trusted_pose()
            return None
        if type(names) not in (list, tuple) or type(velocities) not in (list, tuple):
            self.clear_interval_keep_trusted_pose()
            return None
        if len(names) != len(velocities):
            self.clear_interval_keep_trusted_pose()
            return None
        if any(not isinstance(name, str) for name in names):
            self.clear_interval_keep_trusted_pose()
            return None
        if any(not _finite_number(value) for value in velocities):
            self.clear_interval_keep_trusted_pose()
            return None

        selected = {}
        for logical, required_name in JOINT_NAMES.items():
            indices = [index for index, name in enumerate(names) if name == required_name]
            if len(indices) != 1:
                self.clear_interval_keep_trusted_pose()
                return None
            selected[logical] = velocities[indices[0]] * WHEEL_SIGNS[LOGICAL_WHEEL_ORDER.index(logical)]

        if self._last_stamp_ns is None:
            self._last_stamp_ns = stamp_ns
            return None

        dt = (stamp_ns - self._last_stamp_ns) / 1_000_000_000.0
        if not math.isfinite(dt) or dt <= 0.0:
            self.clear_interval_keep_trusted_pose()
            return None
        if dt > MAX_SOURCE_GAP_S:
            self.clear_interval_keep_trusted_pose()
            return None

        w_fl, w_fr, w_rl, w_rr = (selected[key] for key in LOGICAL_WHEEL_ORDER)
        vx = WHEEL_RADIUS_M / 4.0 * (w_fl + w_fr + w_rl + w_rr)
        vy = WHEEL_RADIUS_M / 4.0 * (-w_fl + w_fr + w_rl - w_rr)
        wz = WHEEL_RADIUS_M / (4.0 * (WHEELBASE_M + TRACK_M)) * (-w_fl + w_fr - w_rl + w_rr)
        if not all(math.isfinite(value) for value in (vx, vy, wz, dt)):
            self.clear_interval_keep_trusted_pose()
            return None

        theta = wz * dt
        if abs(wz) < 1e-12:
            body_dx, body_dy = vx * dt, vy * dt
        else:
            body_dx = math.sin(theta) / wz * vx - (1.0 - math.cos(theta)) / wz * vy
            body_dy = (1.0 - math.cos(theta)) / wz * vx + math.sin(theta) / wz * vy
        cos_yaw, sin_yaw = math.cos(self._yaw), math.sin(self._yaw)
        next_x = self._x + cos_yaw * body_dx - sin_yaw * body_dy
        next_y = self._y + sin_yaw * body_dx + cos_yaw * body_dy
        next_yaw = self._yaw + theta
        if not all(math.isfinite(value) for value in (body_dx, body_dy, next_x, next_y, next_yaw)):
            self.clear_interval_keep_trusted_pose()
            return None

        sample = WheelOdometrySample(
            sec,
            nanosec,
            next_x,
            next_y,
            next_yaw,
            vx,
            vy,
            wz,
            _covariance_matrix(POSE_COVARIANCE_DIAGONAL),
            _covariance_matrix(TWIST_COVARIANCE_DIAGONAL),
        )
        # Commit only after every prospective output value has passed finite checks.
        self._x, self._y, self._yaw = next_x, next_y, next_yaw
        self._last_stamp_ns = stamp_ns
        return sample
