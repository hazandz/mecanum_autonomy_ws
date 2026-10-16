"""Deterministic, non-publishing command-safety decision core.

This module accepts internal Python values only. It has no ROS, transport,
clock, filesystem, or hardware integration. All operating limits and health
inputs are supplied by the caller; this module defines no motion defaults.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
import math
from typing import Optional, Sequence, Tuple


class CommandSource(str, Enum):
    UNKNOWN = "UNKNOWN"
    POLICY = "POLICY"
    NAV2 = "NAV2"
    TELEOP = "TELEOP"
    SAFE_STOP = "SAFE_STOP"


class SafetyState(str, Enum):
    NORMAL = "NORMAL"
    LIMITED = "LIMITED"
    STOPPED = "STOPPED"
    ESTOPPED = "ESTOPPED"
    FAULT = "FAULT"


@dataclass(frozen=True)
class VelocityCommand:
    linear_x: float
    linear_y: float
    angular_z: float


@dataclass(frozen=True)
class CommandEnvelopeCandidate:
    """Internal envelope representation; not a ROS message parser."""

    source: CommandSource
    sequence: int
    reset_epoch: int
    runtime_generation: int
    source_instance_id: int
    frame_id: str
    twist: VelocityCommand
    steady_received_s: float


@dataclass(frozen=True)
class MotionLimits:
    """Injected symmetric hard velocity, acceleration, and jerk limits."""

    max_abs_linear_x: float
    max_abs_linear_y: float
    max_abs_angular_z: float
    max_acceleration_linear_x: float
    max_acceleration_linear_y: float
    max_acceleration_angular_z: float
    max_jerk_linear_x: float
    max_jerk_linear_y: float
    max_jerk_angular_z: float


@dataclass(frozen=True)
class SafetyContext:
    expected_reset_epoch: int
    expected_runtime_generation: int
    allowed_normal_source: CommandSource
    allowed_source_instance_id: int
    command_ttl_s: float
    motion_limits: MotionLimits
    motion_permitted: bool
    safety_loop_healthy: bool
    command_source_healthy: bool
    scan_fresh: bool
    odom_fresh: bool
    tf_valid: bool
    localization_valid: bool
    navigation_state_fresh: bool
    path_valid: bool
    mcu_healthy: bool
    collision_clear: bool
    reset_in_progress: bool
    estop_active: bool
    critical_fault_active: bool


@dataclass(frozen=True)
class SafetyMemory:
    last_accepted_source: Optional[CommandSource]
    last_accepted_source_instance_id: Optional[int]
    last_accepted_sequence: Optional[int]
    previous_final_velocity: VelocityCommand
    previous_final_acceleration: VelocityCommand
    last_evaluation_steady_s: Optional[float] = None


@dataclass(frozen=True)
class SafetyCommandDecision:
    safety_state: SafetyState
    selected_source: Optional[CommandSource]
    raw_command: Optional[VelocityCommand]
    final_command: VelocityCommand
    reason_codes: Tuple[str, ...]
    next_memory: SafetyMemory
    is_unpublished_decision: bool


_ZERO = VelocityCommand(0.0, 0.0, 0.0)
_HEALTH_FIELDS = (
    "motion_permitted",
    "safety_loop_healthy",
    "command_source_healthy",
    "scan_fresh",
    "odom_fresh",
    "tf_valid",
    "localization_valid",
    "navigation_state_fresh",
    "path_valid",
    "mcu_healthy",
    "collision_clear",
)
_LIMIT_FIELDS = (
    "max_abs_linear_x",
    "max_abs_linear_y",
    "max_abs_angular_z",
    "max_acceleration_linear_x",
    "max_acceleration_linear_y",
    "max_acceleration_angular_z",
    "max_jerk_linear_x",
    "max_jerk_linear_y",
    "max_jerk_angular_z",
)
_NORMAL_SOURCES = (CommandSource.POLICY, CommandSource.NAV2, CommandSource.TELEOP)


def _finite_number(value: object) -> bool:
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value)
    except (OverflowError, TypeError, ValueError):
        return False


def _valid_identifier(value: object) -> bool:
    return type(value) is int and 0 <= value <= (2**64 - 1)


def _valid_velocity(value: object) -> bool:
    return (
        type(value) is VelocityCommand
        and _finite_number(value.linear_x)
        and _finite_number(value.linear_y)
        and _finite_number(value.angular_z)
    )


def _components(value: VelocityCommand) -> Tuple[float, float, float]:
    return (float(value.linear_x), float(value.linear_y), float(value.angular_z))


def _velocity(values: Sequence[float]) -> VelocityCommand:
    return VelocityCommand(float(values[0]), float(values[1]), float(values[2]))


def _zero_memory(memory: SafetyMemory, *, invalidate_sequence: bool = False) -> SafetyMemory:
    if invalidate_sequence:
        return SafetyMemory(None, None, None, _ZERO, _ZERO, None)
    return replace(memory, previous_final_velocity=_ZERO, previous_final_acceleration=_ZERO)


def _decision(
    state: SafetyState,
    reason: str,
    memory: SafetyMemory,
    *,
    selected_source: Optional[CommandSource] = None,
    raw_command: Optional[VelocityCommand] = None,
    invalidate_sequence: bool = False,
) -> SafetyCommandDecision:
    return SafetyCommandDecision(
        safety_state=state,
        selected_source=selected_source,
        raw_command=raw_command,
        final_command=_ZERO,
        reason_codes=(reason,),
        next_memory=_zero_memory(memory, invalidate_sequence=invalidate_sequence),
        is_unpublished_decision=True,
    )


def _valid_limits(limits: object) -> bool:
    if type(limits) is not MotionLimits:
        return False
    return all(
        _finite_number(getattr(limits, field)) and getattr(limits, field) >= 0.0
        for field in _LIMIT_FIELDS
    )


def _valid_context(context: object) -> bool:
    if type(context) is not SafetyContext:
        return False
    if not _valid_identifier(context.expected_reset_epoch):
        return False
    if not _valid_identifier(context.expected_runtime_generation):
        return False
    if (
        type(context.allowed_normal_source) is not CommandSource
        or context.allowed_normal_source not in _NORMAL_SOURCES
    ):
        return False
    if not _valid_identifier(context.allowed_source_instance_id):
        return False
    if not _finite_number(context.command_ttl_s) or context.command_ttl_s <= 0.0:
        return False
    if not _valid_limits(context.motion_limits):
        return False
    return all(type(getattr(context, field)) is bool for field in _HEALTH_FIELDS + (
        "reset_in_progress", "estop_active", "critical_fault_active"
    ))


def _valid_memory(memory: object) -> bool:
    if type(memory) is not SafetyMemory:
        return False
    if memory.last_accepted_source is not None and type(memory.last_accepted_source) is not CommandSource:
        return False
    if memory.last_accepted_source_instance_id is not None and not _valid_identifier(
        memory.last_accepted_source_instance_id
    ):
        return False
    if memory.last_accepted_sequence is not None and not _valid_identifier(memory.last_accepted_sequence):
        return False
    if not _valid_velocity(memory.previous_final_velocity):
        return False
    if not _valid_velocity(memory.previous_final_acceleration):
        return False
    if memory.last_evaluation_steady_s is not None and not _finite_number(
        memory.last_evaluation_steady_s
    ):
        return False
    identity = (
        memory.last_accepted_source,
        memory.last_accepted_source_instance_id,
        memory.last_accepted_sequence,
    )
    if any(value is None for value in identity) and not all(value is None for value in identity):
        return False
    if memory.last_accepted_source is not None and memory.last_evaluation_steady_s is None:
        return False
    return True


def _valid_candidate(candidate: object) -> bool:
    return (
        type(candidate) is CommandEnvelopeCandidate
        and type(candidate.source) is CommandSource
        and _valid_identifier(candidate.sequence)
        and _valid_identifier(candidate.reset_epoch)
        and _valid_identifier(candidate.runtime_generation)
        and _valid_identifier(candidate.source_instance_id)
        and type(candidate.frame_id) is str
        and _valid_velocity(candidate.twist)
        and _finite_number(candidate.steady_received_s)
    )


def _context_is_healthy(context: SafetyContext) -> bool:
    return all(getattr(context, field) is True for field in _HEALTH_FIELDS) and not context.reset_in_progress


def _clamp(value: float, lower: float, upper: float) -> float:
    return min(max(value, lower), upper)


def _apply_limits(
    requested: VelocityCommand,
    previous_velocity: VelocityCommand,
    previous_acceleration: VelocityCommand,
    limits: MotionLimits,
    dt: float,
) -> VelocityCommand:
    raw = _components(requested)
    previous = _components(previous_velocity)
    previous_accel = _components(previous_acceleration)
    hard = (limits.max_abs_linear_x, limits.max_abs_linear_y, limits.max_abs_angular_z)
    accel_max = (
        limits.max_acceleration_linear_x,
        limits.max_acceleration_linear_y,
        limits.max_acceleration_angular_z,
    )
    jerk_max = (limits.max_jerk_linear_x, limits.max_jerk_linear_y, limits.max_jerk_angular_z)
    output = []
    for target, old_v, old_a, vmax, amax, jmax in zip(
        raw, previous, previous_accel, hard, accel_max, jerk_max
    ):
        hard_target = _clamp(target, -vmax, vmax)
        requested_accel = (hard_target - old_v) / dt
        accel_limited = _clamp(requested_accel, -amax, amax)
        jerk_limited = _clamp(accel_limited, old_a - jmax * dt, old_a + jmax * dt)
        output.append(_clamp(old_v + jerk_limited * dt, -vmax, vmax))
    return _velocity(output)


def evaluate_safety(
    context: SafetyContext,
    memory: SafetyMemory,
    candidates: Sequence[CommandEnvelopeCandidate],
    now_steady_s: float,
) -> SafetyCommandDecision:
    """Evaluate one unambiguous candidate and return an unpublished decision.

    Any invalid boundary input or missing health evidence returns zero. TTL and
    limiter time use only the caller-supplied monotonic/steady time values.
    """

    if type(context) is not SafetyContext:
        fallback = memory if type(memory) is SafetyMemory else SafetyMemory(None, None, None, _ZERO, _ZERO)
        return _decision(SafetyState.FAULT, "INVALID_CONTEXT", fallback)
    if type(memory) is not SafetyMemory:
        memory = SafetyMemory(None, None, None, _ZERO, _ZERO)
        return _decision(SafetyState.FAULT, "INVALID_MEMORY", memory)
    if context.estop_active is True:
        return _decision(SafetyState.ESTOPPED, "ESTOP_ACTIVE", memory)
    if context.critical_fault_active is True:
        return _decision(SafetyState.FAULT, "CRITICAL_FAULT_ACTIVE", memory)
    if not _valid_context(context):
        return _decision(SafetyState.FAULT, "INVALID_CONTEXT_INPUT", memory)
    if not _valid_memory(memory):
        return _decision(SafetyState.FAULT, "INVALID_MEMORY_INPUT", memory)
    if not _finite_number(now_steady_s):
        return _decision(SafetyState.FAULT, "INVALID_STEADY_TIME", memory)
    if context.reset_in_progress:
        return _decision(
            SafetyState.STOPPED,
            "RESET_IN_PROGRESS",
            memory,
            invalidate_sequence=True,
        )
    if not _context_is_healthy(context):
        return _decision(SafetyState.STOPPED, "HEALTH_OR_MOTION_PERMIT_MISSING", memory)
    if type(candidates) not in (tuple, list):
        return _decision(SafetyState.FAULT, "INVALID_CANDIDATE_COLLECTION", memory)
    if len(candidates) != 1:
        return _decision(SafetyState.STOPPED, "CANDIDATE_SELECTION_NOT_UNIQUE", memory)
    candidate = candidates[0]
    if not _valid_candidate(candidate):
        return _decision(SafetyState.FAULT, "INVALID_CANDIDATE", memory)
    raw = candidate.twist
    if candidate.source is CommandSource.SAFE_STOP:
        return _decision(SafetyState.STOPPED, "SAFE_STOP_SOURCE", memory, raw_command=raw)
    if candidate.source not in _NORMAL_SOURCES:
        return _decision(SafetyState.STOPPED, "INVALID_COMMAND_SOURCE", memory, raw_command=raw)
    if candidate.source is not context.allowed_normal_source:
        return _decision(SafetyState.STOPPED, "SOURCE_NOT_ALLOWED", memory, raw_command=raw)
    if candidate.source_instance_id != context.allowed_source_instance_id:
        return _decision(SafetyState.STOPPED, "SOURCE_INSTANCE_MISMATCH", memory, raw_command=raw)
    if candidate.reset_epoch != context.expected_reset_epoch:
        return _decision(SafetyState.STOPPED, "RESET_EPOCH_MISMATCH", memory, raw_command=raw)
    if candidate.runtime_generation != context.expected_runtime_generation:
        return _decision(SafetyState.STOPPED, "RUNTIME_GENERATION_MISMATCH", memory, raw_command=raw)
    if candidate.frame_id != "base_link":
        return _decision(SafetyState.STOPPED, "FRAME_MISMATCH", memory, raw_command=raw)
    if not _finite_number(context.command_ttl_s) or context.command_ttl_s <= 0.0:
        return _decision(SafetyState.FAULT, "INVALID_COMMAND_TTL", memory, raw_command=raw)
    if candidate.steady_received_s > now_steady_s:
        return _decision(SafetyState.STOPPED, "COMMAND_FROM_FUTURE", memory, raw_command=raw)
    if now_steady_s - candidate.steady_received_s > context.command_ttl_s:
        return _decision(SafetyState.STOPPED, "COMMAND_EXPIRED", memory, raw_command=raw)
    same_instance = (
        memory.last_accepted_source_instance_id is not None
        and memory.last_accepted_source_instance_id == candidate.source_instance_id
    )
    if same_instance and memory.last_accepted_sequence is not None:
        if candidate.sequence <= memory.last_accepted_sequence:
            return _decision(SafetyState.STOPPED, "SEQUENCE_NOT_STRICTLY_NEWER", memory, raw_command=raw)
    if not _valid_limits(context.motion_limits):
        return _decision(SafetyState.FAULT, "INVALID_MOTION_LIMITS", memory, raw_command=raw)

    limits = context.motion_limits
    old_velocity = _components(memory.previous_final_velocity)
    old_acceleration = _components(memory.previous_final_acceleration)
    hard_limits = (
        limits.max_abs_linear_x,
        limits.max_abs_linear_y,
        limits.max_abs_angular_z,
    )
    acceleration_limits = (
        limits.max_acceleration_linear_x,
        limits.max_acceleration_linear_y,
        limits.max_acceleration_angular_z,
    )
    if any(abs(value) > bound for value, bound in zip(old_velocity, hard_limits)):
        return _decision(SafetyState.FAULT, "MEMORY_VELOCITY_OUTSIDE_HARD_LIMIT", memory, raw_command=raw)
    if any(abs(value) > bound for value, bound in zip(old_acceleration, acceleration_limits)):
        return _decision(SafetyState.FAULT, "MEMORY_ACCELERATION_OUTSIDE_LIMIT", memory, raw_command=raw)
    target = _components(raw)
    hard = (limits.max_abs_linear_x, limits.max_abs_linear_y, limits.max_abs_angular_z)
    if memory.last_evaluation_steady_s is None:
        # There is no measured steady-time interval yet. Record this fresh
        # candidate and begin from zero; no arbitrary ramp interval is invented.
        final = _ZERO if any(value != 0.0 for value in target) else _ZERO
        reason = "LIMIT_TIMEBASE_UNAVAILABLE" if any(value != 0.0 for value in target) else "COMMAND_ACCEPTED"
        next_memory = SafetyMemory(
            candidate.source,
            candidate.source_instance_id,
            candidate.sequence,
            final,
            _ZERO,
            float(now_steady_s),
        )
        state = SafetyState.LIMITED if final != raw else SafetyState.NORMAL
        return SafetyCommandDecision(state, candidate.source, raw, final, (reason,), next_memory, True)

    dt = now_steady_s - memory.last_evaluation_steady_s
    if not math.isfinite(dt) or dt <= 0.0:
        return _decision(SafetyState.STOPPED, "LIMIT_TIMEBASE_NOT_ADVANCED", memory, raw_command=raw)
    if not all(_finite_number(value) for value in target + hard):
        return _decision(SafetyState.FAULT, "NONFINITE_COMMAND_OR_LIMIT", memory, raw_command=raw)
    final = _apply_limits(
        raw,
        memory.previous_final_velocity,
        memory.previous_final_acceleration,
        limits,
        dt,
    )
    final_values = _components(final)
    old_values = _components(memory.previous_final_velocity)
    actual_acceleration = _velocity(
        tuple((new - old) / dt for new, old in zip(final_values, old_values))
    )
    if not _valid_velocity(final) or not _valid_velocity(actual_acceleration):
        return _decision(SafetyState.FAULT, "NONFINITE_LIMIT_RESULT", memory, raw_command=raw)
    limited = final != raw
    reason_codes = ("COMMAND_LIMITED",) if limited else ("COMMAND_ACCEPTED",)
    next_memory = SafetyMemory(
        candidate.source,
        candidate.source_instance_id,
        candidate.sequence,
        final,
        actual_acceleration,
        float(now_steady_s),
    )
    return SafetyCommandDecision(
        SafetyState.LIMITED if limited else SafetyState.NORMAL,
        candidate.source,
        raw,
        final,
        reason_codes,
        next_memory,
        True,
    )
