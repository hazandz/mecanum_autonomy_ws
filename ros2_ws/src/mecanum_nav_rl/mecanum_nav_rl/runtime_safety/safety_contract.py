"""Pure, fail-closed lifecycle and command-safety rules for sim_eval."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math


class PrimaryLifecycle(str, Enum):
    UNCONFIGURED = "Unconfigured"
    INACTIVE = "Inactive"
    ACTIVE = "Active"


class BarrierState(str, Enum):
    INIT = "INIT"
    READY = "READY"
    NON_READY = "NON_READY"
    FAULT = "FAULT"


@dataclass(frozen=True)
class LifecycleIdentity:
    episode_generation: int
    reset_epoch: int
    runtime_generation: int
    sequence: int
    primary_state: PrimaryLifecycle
    barrier_state: BarrierState
    barrier_ros_time_ns: int
    motion_permitted: bool
    reason: str


class SafetyLifecycleCore:
    """Single owner for identity counters and the explicit motion barrier."""

    def __init__(self) -> None:
        self.episode_generation = 0
        self.reset_epoch = 0
        self.runtime_generation = 0
        self.sequence = 0
        self.primary_state = PrimaryLifecycle.UNCONFIGURED
        self.barrier_state = BarrierState.INIT
        self.reason = "STARTUP"
        self.barrier_ros_time_ns = 0

    def configure(self, now_ns: int) -> LifecycleIdentity:
        if self.primary_state is not PrimaryLifecycle.UNCONFIGURED:
            raise ValueError("LIFECYCLE_CONFIGURE_INVALID_PRIMARY_STATE")
        self.primary_state = PrimaryLifecycle.INACTIVE
        return self._set(BarrierState.NON_READY, "CONFIGURED_NOT_ACTIVE", now_ns)

    def activate(self, now_ns: int) -> LifecycleIdentity:
        if self.primary_state is not PrimaryLifecycle.INACTIVE:
            raise ValueError("LIFECYCLE_ACTIVATE_INVALID_PRIMARY_STATE")
        self.primary_state = PrimaryLifecycle.ACTIVE
        return self._set(BarrierState.READY, "ACTIVE_BARRIER", now_ns)

    def mark_non_ready(self, reason: str, now_ns: int) -> LifecycleIdentity:
        if not reason:
            raise ValueError("LIFECYCLE_REASON_REQUIRED")
        return self._set(BarrierState.NON_READY, reason, now_ns)

    def fault(self, reason: str, now_ns: int) -> LifecycleIdentity:
        if not reason:
            raise ValueError("LIFECYCLE_REASON_REQUIRED")
        self.primary_state = PrimaryLifecycle.INACTIVE
        return self._set(BarrierState.FAULT, reason, now_ns)

    def begin_reset(self, now_ns: int) -> LifecycleIdentity:
        self.reset_epoch += 1
        self.episode_generation += 1
        self.primary_state = PrimaryLifecycle.INACTIVE
        return self._set(BarrierState.NON_READY, "RESET_BARRIER", now_ns)

    def _set(self, state: BarrierState, reason: str, now_ns: int) -> LifecycleIdentity:
        if type(now_ns) is not int or now_ns < 0:
            raise ValueError("LIFECYCLE_TIMESTAMP_INVALID")
        self.sequence += 1
        self.barrier_state = state
        self.reason = reason
        self.barrier_ros_time_ns = now_ns
        return self.snapshot()

    def snapshot(self) -> LifecycleIdentity:
        return LifecycleIdentity(
            self.episode_generation,
            self.reset_epoch,
            self.runtime_generation,
            self.sequence,
            self.primary_state,
            self.barrier_state,
            self.barrier_ros_time_ns,
            self.primary_state is PrimaryLifecycle.ACTIVE and self.barrier_state is BarrierState.READY,
            self.reason,
        )

    def refresh(self, now_ns: int) -> LifecycleIdentity:
        """Refresh the barrier timestamp without minting a new identity sequence."""
        if type(now_ns) is not int or now_ns < self.barrier_ros_time_ns:
            return self._set(BarrierState.FAULT, "LIFECYCLE_CLOCK_REGRESSION", max(0, now_ns))
        self.barrier_ros_time_ns = now_ns
        return self.snapshot()


@dataclass(frozen=True)
class SafetyInputs:
    now_ns: int
    command_stamp_ns: int
    scan_stamp_ns: int
    odometry_stamp_ns: int
    lifecycle_stamp_ns: int
    lifecycle: BarrierState
    tf_valid: bool
    localization_valid: bool
    estop_active: bool
    command: tuple[float, float, float]
    sensor_values_finite: bool = True
    odometry_values_finite: bool = True


@dataclass(frozen=True)
class SafetyResult:
    command: tuple[float, float, float]
    accepted: bool
    reasons: tuple[str, ...]


class SafetySupervisorCore:
    """Validate and limit the sole NAV2_BASELINE candidate command."""

    COMMAND_TTL_NS = 200_000_000
    SCAN_MAX_AGE_NS = 500_000_000
    ODOM_MAX_AGE_NS = 250_000_000
    LIFECYCLE_MAX_AGE_NS = 500_000_000
    MAX_VELOCITY = (0.25, 0.20, 0.80)
    MAX_ACCELERATION = (0.50, 0.50, 1.00)
    MAX_JERK = (2.0, 2.0, 4.0)

    def __init__(self) -> None:
        self._last_command = (0.0, 0.0, 0.0)
        self._last_acceleration = (0.0, 0.0, 0.0)
        self._last_stamp_ns: int | None = None

    @staticmethod
    def _age_valid(now_ns: int, stamp_ns: int, limit_ns: int) -> bool:
        return stamp_ns > 0 and now_ns >= stamp_ns and now_ns - stamp_ns <= limit_ns

    def evaluate(self, inputs: SafetyInputs) -> SafetyResult:
        reasons: list[str] = []
        if not all(math.isfinite(value) for value in inputs.command):
            reasons.append("COMMAND_NON_FINITE")
        if not self._age_valid(inputs.now_ns, inputs.command_stamp_ns, self.COMMAND_TTL_NS):
            reasons.append("COMMAND_STALE_OR_INVALID")
        if not self._age_valid(inputs.now_ns, inputs.scan_stamp_ns, self.SCAN_MAX_AGE_NS):
            reasons.append("SCAN_STALE_OR_INVALID")
        if not self._age_valid(inputs.now_ns, inputs.odometry_stamp_ns, self.ODOM_MAX_AGE_NS):
            reasons.append("FILTERED_ODOMETRY_STALE_OR_INVALID")
        if not self._age_valid(inputs.now_ns, inputs.lifecycle_stamp_ns, self.LIFECYCLE_MAX_AGE_NS):
            reasons.append("LIFECYCLE_BARRIER_STALE_OR_INVALID")
        if inputs.lifecycle is not BarrierState.READY:
            reasons.append("LIFECYCLE_BARRIER_NOT_READY")
        if not inputs.tf_valid:
            reasons.append("TF_INVALID")
        if not inputs.localization_valid:
            reasons.append("LOCALIZATION_INVALID")
        if inputs.estop_active:
            reasons.append("ESTOP_ACTIVE")
        if not inputs.sensor_values_finite:
            reasons.append("SCAN_NON_FINITE")
        if not inputs.odometry_values_finite:
            reasons.append("FILTERED_ODOMETRY_NON_FINITE")
        if reasons:
            self._last_command = (0.0, 0.0, 0.0)
            self._last_acceleration = (0.0, 0.0, 0.0)
            self._last_stamp_ns = inputs.now_ns
            return SafetyResult(self._last_command, False, tuple(reasons))
        if self._last_stamp_ns is None:
            self._last_stamp_ns = inputs.now_ns
            self._last_command = (0.0, 0.0, 0.0)
            return SafetyResult(self._last_command, False, ("LIMITER_PRIMED",))
        if inputs.now_ns <= self._last_stamp_ns:
            return SafetyResult((0.0, 0.0, 0.0), False, ("CONTROL_TIMESTAMP_NOT_MONOTONIC",))
        dt = (inputs.now_ns - self._last_stamp_ns) / 1_000_000_000.0
        target = tuple(max(-limit, min(limit, value)) for value, limit in zip(inputs.command, self.MAX_VELOCITY))
        output: list[float] = []
        acceleration: list[float] = []
        for index, (target_value, previous, previous_accel) in enumerate(zip(target, self._last_command, self._last_acceleration)):
            desired_accel = (target_value - previous) / dt
            desired_accel = max(-self.MAX_ACCELERATION[index], min(self.MAX_ACCELERATION[index], desired_accel))
            jerk_step = self.MAX_JERK[index] * dt
            desired_accel = max(previous_accel - jerk_step, min(previous_accel + jerk_step, desired_accel))
            candidate = previous + desired_accel * dt
            output.append(max(-self.MAX_VELOCITY[index], min(self.MAX_VELOCITY[index], candidate)))
            acceleration.append(desired_accel)
        self._last_command = tuple(output)
        self._last_acceleration = tuple(acceleration)
        self._last_stamp_ns = inputs.now_ns
        return SafetyResult(self._last_command, True, ())
