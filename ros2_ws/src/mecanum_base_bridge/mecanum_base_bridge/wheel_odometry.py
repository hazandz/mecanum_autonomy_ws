"""Odometry mecanum thuần Python từ hai telemetry đã được session chấp nhận."""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Optional

INT64_MIN = -(1 << 63)
INT64_MAX = (1 << 63) - 1


@dataclass(frozen=True)
class WheelOdometrySample:
    stamp_ns: int
    x: float
    y: float
    yaw: float
    vx: float
    vy: float
    wz: float
    pose_covariance: tuple[float, ...]
    twist_covariance: tuple[float, ...]


class WheelOdometry:
    """Tích phân SE(2); constructor từ chối signs chưa được xác nhận."""
    POSE_VARIANCES = (0.04, 0.04, 1e6, 1e6, 1e6, 0.08)
    TWIST_VARIANCES = (0.10, 0.10, 1e6, 1e6, 1e6, 0.15)

    def __init__(self, diameter_m: float, wheelbase_m: float, track_m: float,
                 ticks_per_wheel_revolution: float, signs: tuple[int, int, int, int]):
        values = (diameter_m, wheelbase_m, track_m, ticks_per_wheel_revolution)
        if any(type(v) not in (int, float) or not math.isfinite(v) or v <= 0 for v in values):
            raise ValueError("Kích thước bánh xe chưa hợp lệ")
        if len(signs) != 4 or any(type(s) is not int or s not in (-1, 1) for s in signs):
            raise ValueError("Dấu encoder phải được xác nhận cho FL/FR/RL/RR")
        self._distance_per_tick = math.pi * diameter_m / ticks_per_wheel_revolution
        self._lever = (wheelbase_m + track_m) / 2.0
        self._signs = signs
        self._previous = None
        self._x = self._y = self._yaw = 0.0

    def reset_baseline(self) -> None:
        self._previous = None

    def update(self, packet, stamp_ns: int, continuity_reset: bool = False) -> Optional[WheelOdometrySample]:
        if type(stamp_ns) is not int or stamp_ns <= 0:
            self.reset_baseline()
            return None
        if continuity_reset:
            self.reset_baseline()
        ticks = (packet.ticks_fl, packet.ticks_fr, packet.ticks_rl, packet.ticks_rr)
        if any(type(v) is not int or not INT64_MIN <= v <= INT64_MAX for v in ticks):
            self.reset_baseline()
            return None
        current = (packet.mcu_boot_id, packet.reset_epoch, packet.telemetry_sequence,
                   packet.mcu_monotonic_time_us, ticks, stamp_ns)
        if self._previous is None:
            self._previous = current
            return None
        boot, epoch, sequence, mcu_time, old_ticks, old_stamp = self._previous
        if (packet.mcu_boot_id != boot or packet.reset_epoch != epoch
                or type(packet.telemetry_sequence) is not int or packet.telemetry_sequence != sequence + 1
                or type(packet.mcu_monotonic_time_us) is not int
                or packet.mcu_monotonic_time_us <= mcu_time or stamp_ns < old_stamp):
            self._previous = current
            return None
        raw_deltas = tuple(ticks[i] - old_ticks[i] for i in range(4))
        if any(delta < INT64_MIN or delta > INT64_MAX for delta in raw_deltas):
            # Counter jump vượt khả năng biểu diễn signed int64: không đổi pose;
            # mẫu mới chỉ là baseline cho cặp adjacent tiếp theo.
            self._previous = current
            return None
        wheel = tuple(float(raw_deltas[i] * self._signs[i]) * self._distance_per_tick for i in range(4))
        dx = sum(wheel) / 4.0
        dy = (-wheel[0] + wheel[1] + wheel[2] - wheel[3]) / 4.0
        dtheta = (-wheel[0] + wheel[1] - wheel[2] + wheel[3]) / (4.0 * self._lever)
        if abs(dtheta) < 1e-6:
            a = 1.0 - dtheta * dtheta / 6.0
            b = dtheta / 2.0 - dtheta * dtheta * dtheta / 24.0
        else:
            a = math.sin(dtheta) / dtheta
            b = (1.0 - math.cos(dtheta)) / dtheta
        local_x, local_y = a * dx - b * dy, b * dx + a * dy
        c, s = math.cos(self._yaw), math.sin(self._yaw)
        self._x += c * local_x - s * local_y
        self._y += s * local_x + c * local_y
        self._yaw = math.atan2(math.sin(self._yaw + dtheta), math.cos(self._yaw + dtheta))
        dt = (packet.mcu_monotonic_time_us - mcu_time) / 1_000_000.0
        self._previous = current
        pose_cov = self._covariance(self.POSE_VARIANCES)
        twist_cov = self._covariance(self.TWIST_VARIANCES)
        return WheelOdometrySample(stamp_ns, self._x, self._y, self._yaw,
                                   dx / dt, dy / dt, dtheta / dt, pose_cov, twist_cov)

    @staticmethod
    def _covariance(diagonal: tuple[float, ...]) -> tuple[float, ...]:
        values = [0.0] * 36
        for i, value in zip((0, 7, 14, 21, 28, 35), diagonal):
            values[i] = value
        return tuple(values)
