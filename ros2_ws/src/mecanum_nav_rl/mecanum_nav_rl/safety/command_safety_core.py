"""Deterministic, fail-closed command policy core with no runtime I/O.

This module evaluates injected values only. A returned decision is not a
receipt and does not assert that a command was published or issued.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
import math
from typing import Iterable, Optional, Tuple


UINT32_MAX = (1 << 32) - 1
UINT64_MAX = (1 << 64) - 1
ZERO_COMMAND = None  # Constructed by _zero() to keep the value immutable.


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
    hard_max_linear_x: float
    hard_max_linear_y: float
    hard_max_angular_z: float
    acceleration_max_linear_x: float
    acceleration_max_linear_y: float
    acceleration_max_angular_z: float
    jerk_max_linear_x: float
    jerk_max_linear_y: float
    jerk_max_angular_z: float


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
    manual_reset_authorized: bool


@dataclass(frozen=True)
class SafetyMemory:
    last_accepted_source: Optional[CommandSource] = None
    last_accepted_source_instance_id: Optional[int] = None
    last_accepted_sequence: Optional[int] = None
    last_accepted_reset_epoch: Optional[int] = None
    last_accepted_runtime_generation: Optional[int] = None
    previous_final_velocity: VelocityCommand = VelocityCommand(0.0, 0.0, 0.0)
    previous_final_acceleration: VelocityCommand = VelocityCommand(0.0, 0.0, 0.0)
    last_evaluation_steady_s: Optional[float] = None
    emergency_latch: Optional[SafetyState] = None
    emergency_latch_reset_epoch: Optional[int] = None


@dataclass(frozen=True)
class SafetyCommandDecision:
    safety_state: SafetyState
    selected_source: CommandSource
    raw_command: Optional[VelocityCommand]
    final_command: VelocityCommand
    reason_codes: Tuple[str, ...]
    next_memory: SafetyMemory
    is_unpublished_decision: bool


def _is_int_in_range(value: object, maximum: int) -> bool:
    return type(value) is int and 0 <= value <= maximum


def _is_finite_number(value: object) -> bool:
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value)
    except (OverflowError, TypeError, ValueError):
        return False


def _xyz(command: VelocityCommand) -> Tuple[float, float, float]:
    return (command.linear_x, command.linear_y, command.angular_z)


def _from_xyz(values: Tuple[float, float, float]) -> VelocityCommand:
    return VelocityCommand(*values)


def _valid_velocity(command: object) -> bool:
    return type(command) is VelocityCommand and all(_is_finite_number(v) for v in _xyz(command))


def _zero() -> VelocityCommand:
    return VelocityCommand(0.0, 0.0, 0.0)


def _clear_command_memory(memory: SafetyMemory, *, now: Optional[float] = None) -> SafetyMemory:
    return SafetyMemory(
        previous_final_velocity=_zero(),
        previous_final_acceleration=_zero(),
        last_evaluation_steady_s=now,
        emergency_latch=memory.emergency_latch,
        emergency_latch_reset_epoch=memory.emergency_latch_reset_epoch,
    )


def _valid_limits(limits: object) -> bool:
    if type(limits) is not MotionLimits:
        return False
    values = tuple(getattr(limits, field) for field in MotionLimits.__dataclass_fields__)
    return all(_is_finite_number(value) and value > 0 for value in values)


def _valid_context(context: object) -> bool:
    if type(context) is not SafetyContext:
        return False
    if not _is_int_in_range(context.expected_reset_epoch, UINT32_MAX):
        return False
    if not _is_int_in_range(context.expected_runtime_generation, UINT32_MAX):
        return False
    if not _is_int_in_range(context.allowed_source_instance_id, UINT64_MAX):
        return False
    if type(context.allowed_normal_source) is not CommandSource or context.allowed_normal_source in (
        CommandSource.UNKNOWN,
        CommandSource.SAFE_STOP,
    ):
        return False
    if not _is_finite_number(context.command_ttl_s) or context.command_ttl_s <= 0:
        return False
    if not _valid_limits(context.motion_limits):
        return False
    for field in (
        "motion_permitted", "safety_loop_healthy", "command_source_healthy",
        "scan_fresh", "odom_fresh", "tf_valid", "localization_valid",
        "navigation_state_fresh", "path_valid", "mcu_healthy", "collision_clear",
        "reset_in_progress", "estop_active", "critical_fault_active",
        "manual_reset_authorized",
    ):
        if type(getattr(context, field)) is not bool:
            return False
    return True


def _valid_memory(memory: object) -> bool:
    if type(memory) is not SafetyMemory:
        return False
    fields = (
        memory.last_accepted_source,
        memory.last_accepted_source_instance_id,
        memory.last_accepted_sequence,
        memory.last_accepted_reset_epoch,
        memory.last_accepted_runtime_generation,
    )
    if any(value is None for value in fields) and not all(value is None for value in fields):
        return False
    if memory.last_accepted_source is not None and type(memory.last_accepted_source) is not CommandSource:
        return False
    if memory.last_accepted_source_instance_id is not None and not _is_int_in_range(memory.last_accepted_source_instance_id, UINT64_MAX):
        return False
    if memory.last_accepted_sequence is not None and not _is_int_in_range(memory.last_accepted_sequence, UINT64_MAX):
        return False
    if memory.last_accepted_reset_epoch is not None and not _is_int_in_range(memory.last_accepted_reset_epoch, UINT32_MAX):
        return False
    if memory.last_accepted_runtime_generation is not None and not _is_int_in_range(memory.last_accepted_runtime_generation, UINT32_MAX):
        return False
    if not _valid_velocity(memory.previous_final_velocity) or not _valid_velocity(memory.previous_final_acceleration):
        return False
    if memory.last_evaluation_steady_s is not None and not _is_finite_number(memory.last_evaluation_steady_s):
        return False
    if memory.emergency_latch not in (None, SafetyState.ESTOPPED, SafetyState.FAULT):
        return False
    if memory.emergency_latch is None:
        return memory.emergency_latch_reset_epoch is None
    return _is_int_in_range(memory.emergency_latch_reset_epoch, UINT32_MAX)


def _memory_within_limits(memory: SafetyMemory, limits: MotionLimits) -> bool:
    velocity_bounds = _limits_tuple(limits, "hard_max")
    acceleration_bounds = _limits_tuple(limits, "acceleration_max")
    return all(
        abs(value) <= bound
        for value, bound in zip(_xyz(memory.previous_final_velocity), velocity_bounds)
    ) and all(
        abs(value) <= bound
        for value, bound in zip(_xyz(memory.previous_final_acceleration), acceleration_bounds)
    )


def _valid_candidate(candidate: object) -> bool:
    return (
        type(candidate) is CommandEnvelopeCandidate
        and type(candidate.source) is CommandSource
        and _is_int_in_range(candidate.sequence, UINT64_MAX)
        and _is_int_in_range(candidate.source_instance_id, UINT64_MAX)
        and _is_int_in_range(candidate.reset_epoch, UINT32_MAX)
        and _is_int_in_range(candidate.runtime_generation, UINT32_MAX)
        and type(candidate.frame_id) is str
        and _valid_velocity(candidate.twist)
        and _is_finite_number(candidate.steady_received_s)
    )


def _decision(
    state: SafetyState,
    reason: str,
    memory: SafetyMemory,
    *,
    source: CommandSource = CommandSource.SAFE_STOP,
    raw: Optional[VelocityCommand] = None,
) -> SafetyCommandDecision:
    return SafetyCommandDecision(state, source, raw, _zero(), (reason,), memory, True)


def _limits_tuple(limits: MotionLimits, prefix: str) -> Tuple[float, float, float]:
    return tuple(float(getattr(limits, f"{prefix}_{axis}")) for axis in ("linear_x", "linear_y", "angular_z"))


def _clip(value: float, bound: float) -> float:
    return max(-bound, min(bound, value))


def _healthy(context: SafetyContext) -> bool:
    return all((
        context.motion_permitted,
        context.safety_loop_healthy,
        context.command_source_healthy,
        context.scan_fresh,
        context.odom_fresh,
        context.tf_valid,
        context.localization_valid,
        context.navigation_state_fresh,
        context.path_valid,
        context.mcu_healthy,
        context.collision_clear,
    ))


def evaluate_safety(
    context: SafetyContext,
    memory: SafetyMemory,
    candidates: Iterable[CommandEnvelopeCandidate],
    now_steady_s: float,
) -> SafetyCommandDecision:
    """Evaluate injected command data and return an unpublished decision.

    All malformed, missing, stale, ambiguous, or unhealthy input fails closed.
    Only local monotonic/steady timestamps are used for command TTL and limits.
    """
    if not _valid_context(context) or not _valid_memory(memory) or not _is_finite_number(now_steady_s):
        return _decision(SafetyState.FAULT, "INVALID_CONTEXT_MEMORY_OR_TIME", SafetyMemory())
    if not _memory_within_limits(memory, context.motion_limits):
        return _decision(SafetyState.FAULT, "MEMORY_OUTSIDE_INJECTED_LIMITS", SafetyMemory())

    now = float(now_steady_s)
    if context.estop_active or context.critical_fault_active:
        latch = SafetyState.ESTOPPED if context.estop_active else SafetyState.FAULT
        latched_memory = replace(
            _clear_command_memory(memory, now=now),
            emergency_latch=latch,
            emergency_latch_reset_epoch=context.expected_reset_epoch,
        )
        return _decision(latch, "ESTOP_LATCHED" if latch is SafetyState.ESTOPPED else "CRITICAL_FAULT_LATCHED", latched_memory)

    if memory.emergency_latch is not None:
        released = (
            context.manual_reset_authorized
            and not context.reset_in_progress
            and context.expected_reset_epoch != memory.emergency_latch_reset_epoch
        )
        if released:
            cleared = SafetyMemory(last_evaluation_steady_s=now)
            return _decision(SafetyState.STOPPED, "EMERGENCY_LATCH_RELEASE_BARRIER", cleared)
        return _decision(memory.emergency_latch, "EMERGENCY_LATCH_REQUIRES_AUTHORIZED_NEW_EPOCH", _clear_command_memory(memory, now=now))

    if context.reset_in_progress:
        return _decision(SafetyState.STOPPED, "RESET_IN_PROGRESS_BARRIER", _clear_command_memory(memory, now=now))

    if memory.last_accepted_source is not None and (
        memory.last_accepted_reset_epoch != context.expected_reset_epoch
        or memory.last_accepted_runtime_generation != context.expected_runtime_generation
    ):
        return _decision(SafetyState.STOPPED, "EPOCH_OR_GENERATION_BARRIER", _clear_command_memory(memory, now=now))

    try:
        candidate_list = list(candidates)
    except (TypeError, ValueError):
        return _decision(SafetyState.STOPPED, "INVALID_CANDIDATE_COLLECTION", _clear_command_memory(memory, now=now))
    if not _healthy(context):
        return _decision(SafetyState.STOPPED, "UPSTREAM_NOT_HEALTHY", _clear_command_memory(memory, now=now))
    if not candidate_list:
        return _decision(SafetyState.STOPPED, "NO_COMMAND_CANDIDATE", _clear_command_memory(memory, now=now))
    if any(not _valid_candidate(candidate) for candidate in candidate_list):
        return _decision(SafetyState.STOPPED, "MALFORMED_COMMAND_CANDIDATE", _clear_command_memory(memory, now=now))
    if len(candidate_list) != 1:
        return _decision(SafetyState.STOPPED, "AMBIGUOUS_COMMAND_CANDIDATES", _clear_command_memory(memory, now=now))

    candidate = candidate_list[0]
    if candidate.source is CommandSource.SAFE_STOP:
        return _decision(SafetyState.STOPPED, "SAFE_STOP_SELECTED", _clear_command_memory(memory, now=now), source=CommandSource.SAFE_STOP, raw=candidate.twist)
    if candidate.source is not context.allowed_normal_source:
        return _decision(SafetyState.STOPPED, "SOURCE_NOT_ALLOWED", _clear_command_memory(memory, now=now), raw=candidate.twist)
    if candidate.source_instance_id != context.allowed_source_instance_id:
        return _decision(SafetyState.STOPPED, "SOURCE_INSTANCE_MISMATCH", _clear_command_memory(memory, now=now), raw=candidate.twist)
    if candidate.frame_id != "base_link":
        return _decision(SafetyState.STOPPED, "FRAME_MISMATCH", _clear_command_memory(memory, now=now), raw=candidate.twist)
    if candidate.reset_epoch != context.expected_reset_epoch or candidate.runtime_generation != context.expected_runtime_generation:
        return _decision(SafetyState.STOPPED, "CANDIDATE_EPOCH_OR_GENERATION_MISMATCH", _clear_command_memory(memory, now=now), raw=candidate.twist)

    if memory.last_accepted_source is not None:
        if candidate.source is not memory.last_accepted_source:
            return _decision(SafetyState.STOPPED, "SOURCE_HANDOVER_BARRIER", _clear_command_memory(memory, now=now), raw=candidate.twist)
        if candidate.source_instance_id != memory.last_accepted_source_instance_id:
            return _decision(SafetyState.STOPPED, "SOURCE_INSTANCE_HANDOVER_BARRIER", _clear_command_memory(memory, now=now), raw=candidate.twist)
        if candidate.sequence <= memory.last_accepted_sequence:
            return _decision(SafetyState.STOPPED, "SEQUENCE_NOT_STRICTLY_NEWER", _clear_command_memory(memory, now=now), raw=candidate.twist)

    received = float(candidate.steady_received_s)
    age = now - received
    if age < 0.0 or age > context.command_ttl_s:
        return _decision(SafetyState.STOPPED, "COMMAND_TTL_INVALID_OR_EXPIRED", _clear_command_memory(memory, now=now), raw=candidate.twist)

    hard = _limits_tuple(context.motion_limits, "hard_max")
    accel_limits = _limits_tuple(context.motion_limits, "acceleration_max")
    jerk_limits = _limits_tuple(context.motion_limits, "jerk_max")
    raw_values = tuple(float(v) for v in _xyz(candidate.twist))
    target = tuple(_clip(v, bound) for v, bound in zip(raw_values, hard))
    identity_memory = SafetyMemory(
        candidate.source,
        candidate.source_instance_id,
        candidate.sequence,
        candidate.reset_epoch,
        candidate.runtime_generation,
        memory.previous_final_velocity,
        memory.previous_final_acceleration,
        now,
    )

    if memory.last_evaluation_steady_s is None:
        next_memory = replace(identity_memory, previous_final_velocity=_zero(), previous_final_acceleration=_zero())
        return _decision(SafetyState.LIMITED, "LIMITER_INITIALIZATION_ZERO", next_memory, source=candidate.source, raw=candidate.twist)
    dt = now - memory.last_evaluation_steady_s
    if not math.isfinite(dt) or dt <= 0.0:
        return _decision(SafetyState.STOPPED, "STEADY_TIME_NOT_INCREASING", _clear_command_memory(memory, now=now), raw=candidate.twist)

    previous_velocity = _xyz(memory.previous_final_velocity)
    previous_acceleration = _xyz(memory.previous_final_acceleration)
    desired_acceleration = tuple(
        _clip((target[i] - previous_velocity[i]) / dt, accel_limits[i])
        for i in range(3)
    )
    limited_acceleration = tuple(
        _clip(desired_acceleration[i], jerk_limits[i] * dt)
        if abs(desired_acceleration[i] - previous_acceleration[i]) > jerk_limits[i] * dt
        else desired_acceleration[i]
        for i in range(3)
    )
    output = tuple(_clip(previous_velocity[i] + limited_acceleration[i] * dt, hard[i]) for i in range(3))
    actual_acceleration = tuple((output[i] - previous_velocity[i]) / dt for i in range(3))
    limited = any(not math.isclose(output[i], raw_values[i], rel_tol=0.0, abs_tol=1e-12) for i in range(3))
    next_memory = replace(
        identity_memory,
        previous_final_velocity=_from_xyz(output),
        previous_final_acceleration=_from_xyz(actual_acceleration),
    )
    return SafetyCommandDecision(
        SafetyState.LIMITED if limited else SafetyState.NORMAL,
        candidate.source,
        candidate.twist,
        _from_xyz(output),
        ("MOTION_LIMIT_APPLIED",) if limited else ("COMMAND_ACCEPTED",),
        next_memory,
        True,
    )
