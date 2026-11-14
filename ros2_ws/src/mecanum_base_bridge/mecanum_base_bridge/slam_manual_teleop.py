"""Pure Xbox mapping for the isolated SLAM bench; no serial or ROS ownership."""
from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class BodyCommand:
    vx: float = 0.0
    vy: float = 0.0
    wz: float = 0.0


def map_joystick(axes, buttons, speed_scale: float, yaw_scale: float) -> BodyCommand:
    """Pure mapping for Xbox Joy axes/buttons to a body-frame command.

    Stick convention: axis 0 is positive to the right and axis 1 is negative
    forward. Translation follows the stick direction on the forward/reverse
    half-planes, fades to zero at a pure sideways stick, and yaw remains so a
    horizontal stick turns in place instead of commanding lateral slip.
    """
    if len(axes) < 2 or len(buttons) < 6:
        return BodyCommand()
    try:
        x, y = float(axes[0]), float(axes[1])
        pressed = tuple(1 if int(buttons[i]) else 0 for i in range(6))
        speed_scale, yaw_scale = float(speed_scale), float(yaw_scale)
    except (TypeError, ValueError, OverflowError):
        return BodyCommand()
    if (not all(math.isfinite(value) for value in (x, y, speed_scale, yaw_scale))
            or not -1.0 <= x <= 1.0 or not -1.0 <= y <= 1.0
            or speed_scale <= 0.0 or yaw_scale < 0.0):
        return BodyCommand()

    # A missing approved speed profile keeps every motion axis disarmed,
    # including yaw, even if a nonzero yaw scale was supplied separately.
    radius = math.hypot(x, y)
    if radius == 0.0:
        stick_vx = stick_vy = wz = 0.0
    else:
        # Normalize diagonal input to the unit circle while preserving angle.
        if radius > 1.0:
            x, y = x / radius, y / radius
            radius = 1.0
        forward = -y
        left = -x
        # Scale the travel vector by its forward component. This keeps its
        # direction at 1/2 o'clock, while a 3/9 o'clock stick has no vy/vx.
        travel_gain = abs(forward) / max(math.hypot(forward, left), 1e-12)
        stick_vx = speed_scale * forward * travel_gain
        stick_vy = speed_scale * left * travel_gain
        wz = -x * yaw_scale

    # Existing face-button convention: A/Y select reverse/forward, X/B
    # select left/right; pairing one from each axis makes a diagonal.
    longitudinal = int(bool(pressed[3])) - int(bool(pressed[0]))
    lateral = int(bool(pressed[2])) - int(bool(pressed[1]))
    vx = speed_scale * longitudinal if longitudinal else stick_vx
    vy = speed_scale * lateral if lateral else stick_vy
    norm = math.hypot(vx, vy)
    if norm > speed_scale:
        vx, vy = vx * speed_scale / norm, vy * speed_scale / norm
    return BodyCommand(vx, vy, wz)


class SlamManualTeleop:
    """Map Joy arrays to a bounded body command. Speed levels are explicit."""

    def __init__(self, speed_levels: tuple[float, ...] = (), yaw_scale: float = 0.0):
        # Levels are bench vx/vy limits in m/s; yaw_scale is rad/s at full stick.
        # Empty levels deliberately disarm all motion pending approved limits.
        if any(not math.isfinite(v) or v <= 0.0 for v in speed_levels):
            raise ValueError("speed levels must be finite and positive")
        if tuple(sorted(speed_levels)) != speed_levels:
            raise ValueError("speed levels must be ascending")
        if not math.isfinite(yaw_scale) or yaw_scale < 0.0:
            raise ValueError("yaw scale must be finite and nonnegative")
        self._levels = speed_levels
        self._yaw_scale = yaw_scale
        self._level = 0
        self._previous_buttons: tuple[int, ...] = ()

    @property
    def level(self) -> int:
        return self._level

    def disconnected(self) -> BodyCommand:
        self._previous_buttons = ()
        return BodyCommand()

    def update(self, axes, buttons) -> BodyCommand:
        if len(axes) < 2 or len(buttons) < 6:
            self._previous_buttons = ()
            return BodyCommand()
        try:
            values = (float(axes[0]), float(axes[1]))
            pressed = tuple(1 if int(buttons[i]) else 0 for i in range(6))
        except (TypeError, ValueError, OverflowError):
            self._previous_buttons = ()
            return BodyCommand()
        if not all(math.isfinite(v) and -1.0 <= v <= 1.0 for v in values):
            self._previous_buttons = ()
            return BodyCommand()
        rising = [pressed[i] and (i >= len(self._previous_buttons) or not self._previous_buttons[i])
                  for i in range(6)]
        self._previous_buttons = pressed
        if self._levels:
            if rising[4]:
                self._level = min(self._level + 1, len(self._levels) - 1)
            if rising[5]:
                self._level = max(self._level - 1, 0)
        scale = self._levels[self._level] if self._levels else 0.0
        return map_joystick(values, pressed, scale, self._yaw_scale)
