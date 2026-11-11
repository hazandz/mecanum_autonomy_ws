"""Pure Xbox mapping for the isolated SLAM bench; no serial or ROS ownership."""
from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class BodyCommand:
    vx: float = 0.0
    vy: float = 0.0
    wz: float = 0.0


class SlamManualTeleop:
    """Map Joy arrays to a bounded body command. Speed levels are explicit."""

    def __init__(self, speed_levels: tuple[float, ...] = (), yaw_scale: float = 0.0):
        # Levels are bench vx/vy limits in m/s; yaw_scale is rad/s at full stick.
        # Empty levels deliberately disarm translation pending approved limits.
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
        x, y = values[0], values[1]
        # Stick always supplies forward/reverse; horizontal stick only steers.
        stick_vx = y * scale
        wz = -x * self._yaw_scale
        # Direction buttons replace stick longitudinal intent, while lateral
        # buttons combine with it to form the four requested diagonal pairs.
        vx = (scale * (int(bool(pressed[3])) - int(bool(pressed[0])))
              if pressed[3] or pressed[0] else stick_vx)
        right = int(bool(pressed[1]))
        left = int(bool(pressed[2]))
        vy = scale * (left - right)
        norm = math.hypot(vx, vy)
        if scale and norm > scale:
            vx, vy = vx * scale / norm, vy * scale / norm
        return BodyCommand(vx, vy, wz)
