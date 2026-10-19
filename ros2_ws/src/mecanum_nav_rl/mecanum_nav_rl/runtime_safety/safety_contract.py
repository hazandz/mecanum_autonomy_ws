"""Pure, fail-closed lifecycle and command-safety rules for sim_eval."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
from collections.abc import Mapping


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
    """Single owner for identity counters and explicit motion rearm barrier."""

    def __init__(self) -> None:
        self.episode_generation = 0
        self.reset_epoch = 0
        self.runtime_generation = 0
        self.sequence = 0
        self.primary_state = PrimaryLifecycle.UNCONFIGURED
        self.barrier_state = BarrierState.INIT
        self.reason = "STARTUP"
        self.barrier_ros_time_ns = 0
        self._last_clock_ns = 0

    def configure(self, now_ns: int) -> LifecycleIdentity:
        if self.primary_state is not PrimaryLifecycle.UNCONFIGURED:
            raise ValueError("LIFECYCLE_CONFIGURE_INVALID_PRIMARY_STATE")
        self.primary_state = PrimaryLifecycle.INACTIVE
        return self._set(BarrierState.NON_READY, "CONFIGURED_NOT_ACTIVE", now_ns)

    def activate(self, now_ns: int) -> LifecycleIdentity:
        if self.primary_state is not PrimaryLifecycle.INACTIVE:
            raise ValueError("LIFECYCLE_ACTIVATE_INVALID_PRIMARY_STATE")
        self.primary_state = PrimaryLifecycle.ACTIVE
        return self._set(BarrierState.NON_READY, "ACTIVE_REARM_REQUIRED", now_ns)

    def rearm(self, now_ns: int) -> LifecycleIdentity:
        if self.primary_state is not PrimaryLifecycle.ACTIVE:
            raise ValueError("LIFECYCLE_REARM_REQUIRES_ACTIVE")
        self.runtime_generation += 1
        return self._set(BarrierState.READY, "EXPLICIT_REARM", now_ns)

    def mark_non_ready(self, reason: str, now_ns: int) -> LifecycleIdentity:
        if not reason:
            raise ValueError("LIFECYCLE_REASON_REQUIRED")
        return self._set(BarrierState.NON_READY, reason, now_ns)

    def fault(self, reason: str, now_ns: int) -> LifecycleIdentity:
        if not reason:
            raise ValueError("LIFECYCLE_REASON_REQUIRED")
        self.primary_state = PrimaryLifecycle.INACTIVE
        return self._set(BarrierState.FAULT, reason, now_ns)

    def deactivate(self, now_ns: int) -> LifecycleIdentity:
        if self.primary_state is not PrimaryLifecycle.ACTIVE:
            raise ValueError("LIFECYCLE_DEACTIVATE_INVALID_PRIMARY_STATE")
        self.primary_state = PrimaryLifecycle.INACTIVE
        return self._set(BarrierState.NON_READY, "LIFECYCLE_DEACTIVATED", now_ns)

    def cleanup(self, now_ns: int) -> LifecycleIdentity:
        self.primary_state = PrimaryLifecycle.UNCONFIGURED
        return self._set(BarrierState.NON_READY, "LIFECYCLE_CLEANUP", now_ns)

    def begin_reset(self, now_ns: int) -> LifecycleIdentity:
        self.reset_epoch += 1
        self.episode_generation += 1
        return self._set(BarrierState.NON_READY, "RESET_BARRIER", now_ns)

    def _set(self, state: BarrierState, reason: str, now_ns: int) -> LifecycleIdentity:
        if type(now_ns) is not int or now_ns < self._last_clock_ns:
            self.primary_state = PrimaryLifecycle.INACTIVE
            state, reason, now_ns = BarrierState.FAULT, "LIFECYCLE_CLOCK_REGRESSION", self._last_clock_ns
        if type(now_ns) is not int or now_ns < 0:
            raise ValueError("LIFECYCLE_TIMESTAMP_INVALID")
        self._last_clock_ns = now_ns
        self.sequence += 1
        self.barrier_state = state
        self.reason = reason
        self.barrier_ros_time_ns = now_ns
        return self.snapshot()

    def snapshot(self) -> LifecycleIdentity:
        return LifecycleIdentity(
            self.episode_generation, self.reset_epoch, self.runtime_generation,
            self.sequence, self.primary_state, self.barrier_state,
            self.barrier_ros_time_ns,
            self.primary_state is PrimaryLifecycle.ACTIVE and self.barrier_state is BarrierState.READY,
            self.reason,
        )

    def refresh(self, now_ns: int) -> LifecycleIdentity:
        """Refresh timestamp; a backwards ROS clock transition faults closed."""
        if type(now_ns) is not int or now_ns < self._last_clock_ns:
            return self._set(BarrierState.FAULT, "LIFECYCLE_CLOCK_REGRESSION", self._last_clock_ns)
        self.barrier_ros_time_ns = now_ns
        self._last_clock_ns = now_ns
        return self.snapshot()


@dataclass(frozen=True)
class SafetyPolicy:
    command_ttl_ns: int
    scan_max_age_ns: int
    filtered_odometry_max_age_ns: int
    lifecycle_barrier_max_age_ns: int
    velocity: tuple[float, float, float]
    acceleration: tuple[float, float, float]
    jerk: tuple[float, float, float]

    @classmethod
    def from_mapping(cls, data: Mapping[str, object]) -> "SafetyPolicy":
        try:
            freshness = data["freshness_ns"]
            limits = data["limits"]
            if not isinstance(freshness, Mapping) or not isinstance(limits, Mapping):
                raise ValueError
            names = ("command_ttl", "scan_max_age", "filtered_odometry_max_age", "lifecycle_barrier_max_age")
            ages = [freshness[name] for name in names]
            if any(type(value) is not int or value <= 0 for value in ages):
                raise ValueError
            vectors = [limits[name] for name in ("velocity", "acceleration", "jerk")]
            if any(not isinstance(vector, (tuple, list)) or len(vector) != 3 for vector in vectors):
                raise ValueError
            if any(type(value) not in (int, float) for vector in vectors for value in vector):
                raise ValueError
            converted = [tuple(float(value) for value in vector) for vector in vectors]
            if any(not math.isfinite(v) or v <= 0 for vector in converted for v in vector):
                raise ValueError
            return cls(*ages, *converted)
        except (KeyError, TypeError, ValueError, OverflowError) as error:
            raise ValueError("SAFETY_POLICY_MISSING_INVALID_OR_NONFINITE") from error


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
    sim_estop_release_authorized: bool
    command: tuple[float, float, float]
    sensor_values_finite: bool = True
    odometry_values_finite: bool = True
    scan_frame_valid: bool = True
    odometry_frame_valid: bool = True


@dataclass(frozen=True)
class SafetyResult:
    command: tuple[float, float, float]
    accepted: bool
    reasons: tuple[str, ...]


class SafetySupervisorCore:
    """Validate and limit one NAV2_BASELINE candidate using immutable policy."""

    def __init__(self, policy: SafetyPolicy) -> None:
        self.policy = policy
        self._last_command = (0.0, 0.0, 0.0)
        self._last_acceleration = (0.0, 0.0, 0.0)
        self._last_stamp_ns: int | None = None

    @staticmethod
    def _age_valid(now_ns: int, stamp_ns: int, limit_ns: int) -> bool:
        return stamp_ns > 0 and now_ns >= stamp_ns and now_ns - stamp_ns <= limit_ns

    def evaluate(self, inputs: SafetyInputs) -> SafetyResult:
        p = self.policy
        reasons: list[str] = []
        if not all(math.isfinite(value) for value in inputs.command):
            reasons.append("COMMAND_NON_FINITE")
        if not self._age_valid(inputs.now_ns, inputs.command_stamp_ns, p.command_ttl_ns):
            reasons.append("COMMAND_STALE_OR_INVALID")
        scan_valid = self._age_valid(inputs.now_ns, inputs.scan_stamp_ns, p.scan_max_age_ns) and inputs.sensor_values_finite and inputs.scan_frame_valid
        odom_valid = self._age_valid(inputs.now_ns, inputs.odometry_stamp_ns, p.filtered_odometry_max_age_ns) and inputs.odometry_values_finite and inputs.odometry_frame_valid
        lifecycle_valid = self._age_valid(inputs.now_ns, inputs.lifecycle_stamp_ns, p.lifecycle_barrier_max_age_ns)
        if not scan_valid:
            reasons.append("SCAN_FRAME_INVALID" if not inputs.scan_frame_valid else "SCAN_STALE_OR_INVALID" if inputs.sensor_values_finite else "SCAN_NON_FINITE")
        if not odom_valid:
            reasons.append("FILTERED_ODOMETRY_FRAME_INVALID" if not inputs.odometry_frame_valid else "FILTERED_ODOMETRY_STALE_OR_INVALID" if inputs.odometry_values_finite else "FILTERED_ODOMETRY_NON_FINITE")
        if not lifecycle_valid:
            reasons.append("LIFECYCLE_BARRIER_STALE_OR_INVALID")
        if inputs.lifecycle is not BarrierState.READY:
            reasons.append("LIFECYCLE_BARRIER_NOT_READY")
        if not inputs.tf_valid:
            reasons.append("TF_INVALID")
        if not inputs.localization_valid:
            reasons.append("LOCALIZATION_INVALID")
        if not inputs.sim_estop_release_authorized or not (scan_valid and odom_valid and lifecycle_valid and inputs.lifecycle is BarrierState.READY and inputs.tf_valid and inputs.localization_valid):
            reasons.append("SIM_ESTOP_ACTIVE")
        if reasons:
            self._last_command = (0.0, 0.0, 0.0)
            self._last_acceleration = (0.0, 0.0, 0.0)
            self._last_stamp_ns = inputs.now_ns
            return SafetyResult(self._last_command, False, tuple(dict.fromkeys(reasons)))
        if self._last_stamp_ns is None:
            self._last_stamp_ns = inputs.now_ns
            return SafetyResult((0.0, 0.0, 0.0), False, ("LIMITER_PRIMED",))
        if inputs.now_ns <= self._last_stamp_ns:
            return SafetyResult((0.0, 0.0, 0.0), False, ("CONTROL_TIMESTAMP_NOT_MONOTONIC",))
        dt = (inputs.now_ns - self._last_stamp_ns) / 1_000_000_000.0
        target = tuple(max(-limit, min(limit, value)) for value, limit in zip(inputs.command, p.velocity))
        output: list[float] = []
        acceleration: list[float] = []
        for index, (target_value, previous, previous_accel) in enumerate(zip(target, self._last_command, self._last_acceleration)):
            desired_accel = (target_value - previous) / dt
            desired_accel = max(-p.acceleration[index], min(p.acceleration[index], desired_accel))
            jerk_step = p.jerk[index] * dt
            desired_accel = max(previous_accel - jerk_step, min(previous_accel + jerk_step, desired_accel))
            candidate = previous + desired_accel * dt
            output.append(max(-p.velocity[index], min(p.velocity[index], candidate)))
            acceleration.append(desired_accel)
        self._last_command = tuple(output)
        self._last_acceleration = tuple(acceleration)
        self._last_stamp_ns = inputs.now_ns
        return SafetyResult(self._last_command, True, ())
