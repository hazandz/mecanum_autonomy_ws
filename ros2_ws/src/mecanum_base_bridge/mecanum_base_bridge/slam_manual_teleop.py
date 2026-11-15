"""Pure Joy mapping and wheel-rate limiting for the isolated SLAM bench."""
from __future__ import annotations

import math
from dataclasses import dataclass


SPEED_LEVELS = (0.2, 0.4, 0.6, 0.8, 1.0)
FACE_BUTTON_COUNT = 4
L1_BUTTON_INDEX = 4
R1_BUTTON_INDEX = 5


@dataclass(frozen=True)
class BodyCommand:
    vx: float = 0.0
    vy: float = 0.0
    wz: float = 0.0


@dataclass(frozen=True)
class SlamBenchMotionProfile:
    """Named wheel-target profile for offline SLAM bench mapping.

    ``owner_design_172rpm`` treats 172 RPM as speed at the gearbox output and
    does not multiply by the motor-to-output reduction. ``pid4_experimental_1400cps``
    uses only the evidence-backed 1400 tick/s experimental ceiling. The
    wheel-to-gearbox-output ratio remains required input; zero is invalid.
    """

    wheel_diameter_m: float
    wheelbase_m: float
    track_m: float
    ticks_per_wheel_revolution: float
    profile_name: str = "pid4_experimental_1400cps"
    owner_design_output_rpm: float = 172.0
    motor_to_gearbox_output_ratio: float = 21.3
    wheel_rpm_per_gearbox_output_rpm: float = 0.0
    experimental_max_wheel_target_cps: float = 1400.0
    deadzone_radius: float = 0.12
    full_command_radius: float = 0.20
    sideways_fade_start_deg: float = 75.0

    @property
    def valid(self) -> bool:
        positive = (
            self.wheel_diameter_m,
            self.wheelbase_m,
            self.track_m,
            self.ticks_per_wheel_revolution,
            self.owner_design_output_rpm,
            self.motor_to_gearbox_output_ratio,
            self.wheel_rpm_per_gearbox_output_rpm,
            self.experimental_max_wheel_target_cps,
        )
        return (
            all(math.isfinite(value) and value > 0.0 for value in positive)
            and math.isfinite(self.deadzone_radius)
            and math.isfinite(self.full_command_radius)
            and 0.0 <= self.deadzone_radius < self.full_command_radius <= 1.0
            and math.isfinite(self.sideways_fade_start_deg)
            and 0.0 < self.sideways_fade_start_deg < 90.0
            and self.profile_name in (
                "owner_design_172rpm", "pid4_experimental_1400cps")
        )

    @property
    def max_wheel_target_cps(self) -> float:
        if self.profile_name == "owner_design_172rpm":
            # The design speed is already at the gearbox output shaft.
            return (self.owner_design_output_rpm
                    * self.wheel_rpm_per_gearbox_output_rpm
                    * self.ticks_per_wheel_revolution / 60.0)
        return self.experimental_max_wheel_target_cps

    @property
    def rotation_radius_m(self) -> float:
        return 0.5 * (self.wheelbase_m + self.track_m)

    @property
    def max_translation_mps(self) -> float:
        counts_per_meter = self.ticks_per_wheel_revolution / (math.pi * self.wheel_diameter_m)
        return self.max_wheel_target_cps / counts_per_meter


def wheel_target_cps(command: BodyCommand, profile: SlamBenchMotionProfile) -> tuple[float, ...]:
    """Tính cps FL/FR/RL/RR theo cùng quy ước với STM32 KIN: vx, vy, wz."""
    if not profile.valid or not all(math.isfinite(v) for v in (command.vx, command.vy, command.wz)):
        return (0.0, 0.0, 0.0, 0.0)
    lever = profile.rotation_radius_m
    counts_per_meter = profile.ticks_per_wheel_revolution / (math.pi * profile.wheel_diameter_m)
    wheel_mps = (
        command.vx - command.vy - lever * command.wz,
        command.vx + command.vy + lever * command.wz,
        command.vx + command.vy - lever * command.wz,
        command.vx - command.vy + lever * command.wz,
    )
    return tuple(value * counts_per_meter for value in wheel_mps)


def limit_command_to_wheel_cps(
    command: BodyCommand, profile: SlamBenchMotionProfile,
    target_limit_cps: float | None = None,
) -> BodyCommand:
    """Giảm đồng tỷ lệ vx/vy/wz theo trần profile hoặc trần cấp tốc độ."""
    if not all(math.isfinite(value) for value in (command.vx, command.vy, command.wz)):
        return BodyCommand()
    targets = wheel_target_cps(command, profile)
    if not profile.valid or not all(math.isfinite(value) for value in targets):
        return BodyCommand()
    limit = profile.max_wheel_target_cps if target_limit_cps is None else target_limit_cps
    if not math.isfinite(limit) or limit <= 0.0 or limit > profile.max_wheel_target_cps:
        return BodyCommand()
    peak = max(abs(value) for value in targets)
    scale = min(1.0, limit / peak) if peak > 0.0 else 1.0
    return BodyCommand(command.vx * scale, command.vy * scale, command.wz * scale)


def _smoothstep(value: float) -> float:
    value = min(1.0, max(0.0, value))
    return value * value * (3.0 - 2.0 * value)


def _analog_command(
    x: float, y: float, level: float, profile: SlamBenchMotionProfile,
) -> BodyCommand:
    # Radial clamp preserves direction for diagonal Joy axes outside the unit circle.
    radius = math.hypot(x, y)
    if radius == 0.0 or radius <= profile.deadzone_radius:
        return BodyCommand()
    if radius > 1.0:
        x, y = x / radius, y / radius
        radius = 1.0

    activation = _smoothstep(
        (radius - profile.deadzone_radius) /
        (profile.full_command_radius - profile.deadzone_radius))
    # This bench gamepad reports stick-up as axes[1] = +1.0.
    forward, left = y, -x
    direction_norm = math.hypot(forward, left)
    if direction_norm == 0.0:
        return BodyCommand()

    theta = math.atan2(abs(left), abs(forward))
    fade_start = math.radians(profile.sideways_fade_start_deg)
    translation_fade = 1.0 - _smoothstep(
        (theta - fade_start) / (math.pi / 2.0 - fade_start))

    speed_mps = profile.max_translation_mps * level * activation
    translation_magnitude = speed_mps * translation_fade
    vx = translation_magnitude * forward / direction_norm
    vy = translation_magnitude * left / direction_norm

    # Yaw follows lateral stick direction and increases smoothly to full turn
    # at 3/9 o'clock. The same level scales both translation and rotation.
    wz_magnitude = (speed_mps / profile.rotation_radius_m
                    * abs(left) / direction_norm)
    wz = math.copysign(wz_magnitude, left) if left != 0.0 else 0.0
    return BodyCommand(vx, vy, wz)


def _button_command(buttons: tuple[int, ...], level: float,
                    profile: SlamBenchMotionProfile) -> BodyCommand:
    # Xbox Joy indices inherited from the existing mapper: A=0, B=1, X=2, Y=3.
    # Any directional button owns the whole command, so opposed pairs cannot
    # accidentally restore analog movement after cancelling one axis.
    forward = buttons[3] - buttons[0]
    left = buttons[2] - buttons[1]
    magnitude = math.hypot(forward, left)
    if magnitude == 0.0:
        return BodyCommand()
    speed_mps = profile.max_translation_mps * level
    return BodyCommand(speed_mps * forward / magnitude,
                       speed_mps * left / magnitude, 0.0)


def map_joystick(axes, buttons, level: float,
                 profile: SlamBenchMotionProfile | None,
                 motion_enabled: bool = False) -> BodyCommand:
    """Pure Joy→body command map; invalid/missing profile or disarm returns zero."""
    if profile is None or not profile.valid or not motion_enabled:
        return BodyCommand()
    try:
        if len(axes) < 2 or len(buttons) < 6:
            return BodyCommand()
        x, y = float(axes[0]), float(axes[1])
        pressed = tuple(1 if int(buttons[i]) else 0 for i in range(6))
        level = float(level)
    except (IndexError, TypeError, ValueError, OverflowError):
        return BodyCommand()
    if (not all(math.isfinite(value) for value in (x, y, level))
            or not -1.0 <= x <= 1.0 or not -1.0 <= y <= 1.0
            or not 0.0 < level <= 1.0):
        return BodyCommand()

    if any(pressed[:FACE_BUTTON_COUNT]):
        command = _button_command(pressed, level, profile)
        activation = 1.0
    else:
        command = _analog_command(x, y, level, profile)
        radius = min(1.0, math.hypot(x, y))
        activation = _smoothstep(
            (radius - profile.deadzone_radius) /
            (profile.full_command_radius - profile.deadzone_radius))
    # Normalize each direction to the selected fraction of the profile ceiling.
    # This preserves five distinct tiers instead of clipping upper tiers from
    # the separate 172 RPM design target down to the experimental 1400 cps cap.
    targets = wheel_target_cps(command, profile)
    peak = max(abs(value) for value in targets)
    if peak <= 0.0:
        return BodyCommand()
    tier_limit = profile.max_wheel_target_cps * level * activation
    if tier_limit <= 0.0:
        return BodyCommand()
    normalized = BodyCommand(
        command.vx * tier_limit / peak,
        command.vy * tier_limit / peak,
        command.wz * tier_limit / peak,
    )
    return limit_command_to_wheel_cps(normalized, profile, tier_limit)


class SlamManualTeleop:
    """Five fixed speed tiers with edge-triggered L1/R1 and fail-closed motion."""

    def __init__(self, profile: SlamBenchMotionProfile | None = None,
                 motion_enabled: bool = False):
        self._profile = profile
        self._motion_enabled = bool(motion_enabled)
        self._waiting_for_neutral = False
        self._level_index = 0  # 20 percent after startup
        self._previous_buttons: tuple[int, ...] = (0,) * 6

    @property
    def level(self) -> int:
        return self._level_index

    @property
    def level_percent(self) -> int:
        return int(SPEED_LEVELS[self._level_index] * 100)

    def disconnected(self) -> BodyCommand:
        self._previous_buttons = (0,) * 6
        self._motion_enabled = False
        self._waiting_for_neutral = False
        return BodyCommand()

    def request_enable(self) -> bool:
        """Require an explicit service request followed by a fresh neutral Joy."""
        if self._profile is None or not self._profile.valid:
            self.disconnected()
            return False
        self._motion_enabled = False
        self._waiting_for_neutral = True
        self._previous_buttons = (0,) * 6
        return True

    def request_disarm(self) -> None:
        self.disconnected()

    def update(self, axes, buttons) -> BodyCommand:
        try:
            if len(axes) < 2 or len(buttons) < 6:
                self._previous_buttons = (0,) * 6
                self._motion_enabled = False
                self._waiting_for_neutral = False
                return BodyCommand()
        except TypeError:
            self._previous_buttons = (0,) * 6
            self._motion_enabled = False
            self._waiting_for_neutral = False
            return BodyCommand()
        try:
            values = (float(axes[0]), float(axes[1]))
            pressed = tuple(1 if int(buttons[i]) else 0 for i in range(6))
        except (IndexError, TypeError, ValueError, OverflowError):
            self._previous_buttons = (0,) * 6
            self._motion_enabled = False
            self._waiting_for_neutral = False
            return BodyCommand()
        if not all(math.isfinite(value) and -1.0 <= value <= 1.0 for value in values):
            self._previous_buttons = (0,) * 6
            self._motion_enabled = False
            self._waiting_for_neutral = False
            return BodyCommand()

        rising = tuple(pressed[i] and not self._previous_buttons[i] for i in range(6))
        self._previous_buttons = pressed
        l1_rising = bool(rising[L1_BUTTON_INDEX])
        r1_rising = bool(rising[R1_BUTTON_INDEX])
        if l1_rising != r1_rising:
            delta = 1 if l1_rising else -1
            self._level_index = min(len(SPEED_LEVELS) - 1,
                                    max(0, self._level_index + delta))

        level = SPEED_LEVELS[self._level_index]
        neutral = (self._profile is not None and self._profile.valid
                   and math.hypot(values[0], values[1]) <= self._profile.deadzone_radius
                   and not any(pressed[:FACE_BUTTON_COUNT]))
        if self._waiting_for_neutral:
            if neutral:
                self._waiting_for_neutral = False
                self._motion_enabled = True
            return BodyCommand()
        return map_joystick(values, pressed, level, self._profile,
                            self._motion_enabled)
