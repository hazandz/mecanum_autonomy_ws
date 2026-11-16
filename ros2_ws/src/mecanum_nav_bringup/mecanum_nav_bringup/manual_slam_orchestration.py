"""Pure startup gate/order helpers for MANUAL_SLAM's terminal-2 coordinator."""
from __future__ import annotations

from dataclasses import dataclass
import math

JOY_DEADZONE_RADIUS = 0.12


@dataclass(frozen=True)
class Readiness:
    scan_fresh: bool
    imu_fresh: bool
    joy_fresh: bool
    joy_neutral: bool
    heartbeat_fresh: bool
    heartbeat_healthy: bool
    safety_active: bool
    safety_motion_permitted: bool = False


def joy_sample_valid(axes, buttons) -> bool:
    try:
        values = tuple(float(value) for value in axes[:2])
        button_values = tuple(buttons[:6])
        return bool(
            len(values) == 2 and len(button_values) == 6 and len(buttons) >= 6
            and all(math.isfinite(value) and -1.0 <= value <= 1.0 for value in values)
            and all(type(value) is int and value in (0, 1) for value in button_values)
        )
    except (AttributeError, IndexError, TypeError, ValueError, OverflowError):
        return False


def joy_is_neutral(axes, buttons, deadzone: float) -> bool:
    if (type(deadzone) not in (float, int) or not math.isfinite(float(deadzone))
            or not 0.0 <= float(deadzone) < 1.0 or not joy_sample_valid(axes, buttons)):
        return False
    return (math.hypot(float(axes[0]), float(axes[1])) <= float(deadzone)
            and all(value == 0 for value in buttons[:6]))


def missing_dependencies(state: Readiness, *, require_motion_permitted: bool = False) -> tuple[str, ...]:
    missing = []
    for field, label in ((state.scan_fresh, "/scan"), (state.imu_fresh, "/imu/data"),
                         (state.joy_fresh, "fresh /joy"), (state.joy_neutral, "neutral /joy"),
                         (state.heartbeat_fresh, "fresh /mcu/heartbeat"),
                         (state.heartbeat_healthy, "healthy UART/session heartbeat"),
                         (state.safety_active, "active /safety_lifecycle")):
        if not field:
            missing.append(label)
    if require_motion_permitted and not state.safety_motion_permitted:
        missing.append("safety lifecycle motion permission")
    return tuple(missing)


def runtime_missing_dependencies(state: Readiness) -> tuple[str, ...]:
    """Runtime health omits neutral-stick gating after intentional control starts."""
    missing = []
    for field, label in ((state.scan_fresh, "/scan"), (state.imu_fresh, "/imu/data"),
                         (state.joy_fresh, "fresh /joy"),
                         (state.heartbeat_fresh, "fresh /mcu/heartbeat"),
                         (state.heartbeat_healthy, "healthy UART/session heartbeat"),
                         (state.safety_active, "active /safety_lifecycle"),
                         (state.safety_motion_permitted, "safety lifecycle motion permission")):
        if not field:
            missing.append(label)
    return tuple(missing)


def fresh_neutral_after_enable(state: Readiness, last_joy_at, enable_started_at) -> bool:
    return bool(
        state.joy_fresh and state.joy_neutral and last_joy_at is not None
        and enable_started_at is not None and last_joy_at > enable_started_at
    )


def startup_actions(state: Readiness) -> tuple[str, ...]:
    """Return ordered logical gates; no action is allowed until all are ready."""
    if missing_dependencies(state):
        return ()
    return ("rearm", "wait_motion_permission", "enable_mapper", "wait_fresh_joy")


def run_startup_sequence(operations) -> None:
    """Run the terminal-2 state machine through an injectable operations port.

    Each operation owns its own timeout and raises on failure. Straight-line
    execution makes it impossible to rearm or enable after a failed gate.
    """
    operations.ensure_slam_active()
    operations.ensure_safety_active()
    operations.wait_hardware_ready()
    operations.wait_fresh_neutral_joy()
    operations.rearm_safety()
    operations.wait_motion_permission()
    operations.wait_fresh_neutral_joy()
    operations.enable_mapper()
    operations.wait_post_enable_joy()


def run_shutdown_sequence(operations) -> None:
    """Request software disarm before terminal-2 process teardown."""
    operations.disarm_mapper()
