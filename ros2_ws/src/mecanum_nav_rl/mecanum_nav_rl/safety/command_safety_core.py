"""Pure deterministic safety decision logic; no runtime transport or I/O."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
from typing import Iterable, Optional, Tuple


UINT32_MAX = 0xFFFFFFFF
UINT64_MAX = 0xFFFFFFFFFFFFFFFF
_AXES = ("linear_x", "linear_y", "angular_z")
_ZERO = (0.0, 0.0, 0.0)


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
    last_source: Optional[CommandSource] = None
    last_source_instance_id: Optional[int] = None
    last_sequence: Optional[int] = None
    last_reset_epoch: Optional[int] = None
    last_runtime_generation: Optional[int] = None
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


def _uint(value: object, bits: int) -> bool:
    return type(value) is int and 0 <= value <= ((1 << bits) - 1)


def _finite(value: object) -> bool:
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value)
    except (OverflowError, TypeError, ValueError):
        return False


def _triple(command: VelocityCommand) -> Tuple[float, float, float]:
    return command.linear_x, command.linear_y, command.angular_z


def _velocity(values: Tuple[float, float, float]) -> VelocityCommand:
    return VelocityCommand(*values)


def _is_velocity(value: object) -> bool:
    return type(value) is VelocityCommand and all(_finite(v) for v in _triple(value))


def _all_zero() -> VelocityCommand:
    return _velocity(_ZERO)


def _bounds(limits: MotionLimits, family: str) -> Tuple[float, float, float]:
    return tuple(float(getattr(limits, f"{family}_{axis}")) for axis in _AXES)


def _valid_limits(value: object) -> bool:
    if type(value) is not MotionLimits:
        return False
    vals = tuple(getattr(value, f) for f in MotionLimits.__dataclass_fields__)
    return all(_finite(v) and v > 0 for v in vals)


def _valid_context(c: object) -> bool:
    if type(c) is not SafetyContext:
        return False
    if not _uint(c.expected_reset_epoch, 32) or not _uint(c.expected_runtime_generation, 32):
        return False
    if not _uint(c.allowed_source_instance_id, 64):
        return False
    if type(c.allowed_normal_source) is not CommandSource or c.allowed_normal_source in (
        CommandSource.UNKNOWN, CommandSource.SAFE_STOP,
    ):
        return False
    if not _finite(c.command_ttl_s) or c.command_ttl_s <= 0 or not _valid_limits(c.motion_limits):
        return False
    return all(type(getattr(c, field)) is bool for field in (
        "motion_permitted", "safety_loop_healthy", "command_source_healthy",
        "scan_fresh", "odom_fresh", "tf_valid", "localization_valid",
        "navigation_state_fresh", "path_valid", "mcu_healthy", "collision_clear",
        "reset_in_progress", "estop_active", "critical_fault_active",
        "manual_reset_authorized",
    ))


def _valid_memory(m: object) -> bool:
    if type(m) is not SafetyMemory:
        return False
    identity = (m.last_source, m.last_source_instance_id, m.last_sequence,
                m.last_reset_epoch, m.last_runtime_generation)
    if any(x is None for x in identity) and not all(x is None for x in identity):
        return False
    if m.last_source is not None and type(m.last_source) is not CommandSource:
        return False
    if m.last_source_instance_id is not None and not _uint(m.last_source_instance_id, 64):
        return False
    if m.last_sequence is not None and not _uint(m.last_sequence, 64):
        return False
    if m.last_reset_epoch is not None and not _uint(m.last_reset_epoch, 32):
        return False
    if m.last_runtime_generation is not None and not _uint(m.last_runtime_generation, 32):
        return False
    if not _is_velocity(m.previous_final_velocity) or not _is_velocity(m.previous_final_acceleration):
        return False
    if m.last_evaluation_steady_s is not None and not _finite(m.last_evaluation_steady_s):
        return False
    if m.emergency_latch not in (None, SafetyState.ESTOPPED, SafetyState.FAULT):
        return False
    if m.emergency_latch is None:
        return m.emergency_latch_reset_epoch is None
    return _uint(m.emergency_latch_reset_epoch, 32)


def _valid_candidate(c: object) -> bool:
    return (
        type(c) is CommandEnvelopeCandidate
        and type(c.source) is CommandSource
        and _uint(c.sequence, 64)
        and _uint(c.source_instance_id, 64)
        and _uint(c.reset_epoch, 32)
        and _uint(c.runtime_generation, 32)
        and type(c.frame_id) is str
        and _is_velocity(c.twist)
        and _finite(c.steady_received_s)
    )


def _clear(m: SafetyMemory, *, when: Optional[float] = None,
           keep_latch: bool = True) -> SafetyMemory:
    latch = m.emergency_latch if keep_latch else None
    latch_epoch = m.emergency_latch_reset_epoch if latch is not None else None
    return SafetyMemory(
        previous_final_velocity=_all_zero(),
        previous_final_acceleration=_all_zero(),
        last_evaluation_steady_s=when,
        emergency_latch=latch,
        emergency_latch_reset_epoch=latch_epoch,
    )


def _zero_preserving_sequence(m: SafetyMemory, *, when: float) -> SafetyMemory:
    """Select zero while retaining accepted identity to prevent replay."""
    return SafetyMemory(
        last_source=m.last_source,
        last_source_instance_id=m.last_source_instance_id,
        last_sequence=m.last_sequence,
        last_reset_epoch=m.last_reset_epoch,
        last_runtime_generation=m.last_runtime_generation,
        previous_final_velocity=_all_zero(),
        previous_final_acceleration=_all_zero(),
        last_evaluation_steady_s=when,
        emergency_latch=m.emergency_latch,
        emergency_latch_reset_epoch=m.emergency_latch_reset_epoch,
    )


def _zero_decision(state: SafetyState, reason: str, memory: SafetyMemory,
                   *, source: CommandSource = CommandSource.SAFE_STOP,
                   raw: Optional[VelocityCommand] = None) -> SafetyCommandDecision:
    return SafetyCommandDecision(state, source, raw, _all_zero(), (reason,), memory, True)


def _healthy(c: SafetyContext) -> bool:
    return all((c.motion_permitted, c.safety_loop_healthy, c.command_source_healthy,
                c.scan_fresh, c.odom_fresh, c.tf_valid, c.localization_valid,
                c.navigation_state_fresh, c.path_valid, c.mcu_healthy,
                c.collision_clear))


def _between(value: float, lower: float, upper: float) -> float:
    return min(upper, max(lower, value))


def _memory_is_within_envelope(m: SafetyMemory, c: SafetyContext) -> bool:
    vmax = _bounds(c.motion_limits, "hard_max")
    amax = _bounds(c.motion_limits, "acceleration_max")
    return all(abs(v) <= lim for v, lim in zip(_triple(m.previous_final_velocity), vmax)) and all(
        abs(a) <= lim for a, lim in zip(_triple(m.previous_final_acceleration), amax)
    )


def evaluate_safety(
    context: SafetyContext,
    memory: SafetyMemory,
    candidates: Iterable[CommandEnvelopeCandidate],
    now_steady_s: float,
) -> SafetyCommandDecision:
    """Return one unpublished decision; malformed or unsafe inputs select zero."""
    if not _valid_context(context) or not _valid_memory(memory) or not _finite(now_steady_s):
        return _zero_decision(SafetyState.FAULT, "INVALID_CONTEXT_MEMORY_OR_TIME", SafetyMemory())
    now = float(now_steady_s)

    # Emergency signals bypass every motion limiter and are latched until an
    # explicit reset authorization advances the reset epoch.
    if context.estop_active or context.critical_fault_active:
        latched = SafetyState.ESTOPPED if context.estop_active else SafetyState.FAULT
        cleared = _clear(memory, when=now, keep_latch=False)
        latched_memory = SafetyMemory(
            previous_final_velocity=cleared.previous_final_velocity,
            previous_final_acceleration=cleared.previous_final_acceleration,
            last_evaluation_steady_s=now,
            emergency_latch=latched,
            emergency_latch_reset_epoch=context.expected_reset_epoch,
        )
        return _zero_decision(latched, "ESTOP_LATCHED" if latched is SafetyState.ESTOPPED else "CRITICAL_FAULT_LATCHED", latched_memory)

    if memory.emergency_latch is not None:
        releasable = (
            context.manual_reset_authorized
            and not context.reset_in_progress
            and context.expected_reset_epoch != memory.emergency_latch_reset_epoch
        )
        if releasable:
            return _zero_decision(SafetyState.STOPPED, "EMERGENCY_RELEASE_BARRIER",
                                  _clear(memory, when=now, keep_latch=False))
        return _zero_decision(memory.emergency_latch, "EMERGENCY_LATCH_STILL_ACTIVE",
                              _clear(memory, when=now))

    if context.reset_in_progress:
        return _zero_decision(SafetyState.STOPPED, "RESET_BARRIER", _clear(memory, when=now))
    if not _memory_is_within_envelope(memory, context):
        return _zero_decision(SafetyState.FAULT, "MEMORY_OUTSIDE_INJECTED_ENVELOPE", SafetyMemory())

    # An identity transition consumes a full zero cycle and discards cached
    # sequence and trajectory state before accepting a new envelope.
    if memory.last_source is not None and (
        memory.last_reset_epoch != context.expected_reset_epoch
        or memory.last_runtime_generation != context.expected_runtime_generation
    ):
        return _zero_decision(SafetyState.STOPPED, "EPOCH_GENERATION_BARRIER", _clear(memory, when=now))
    if not _healthy(context):
        return _zero_decision(SafetyState.STOPPED, "UPSTREAM_NOT_HEALTHY", _zero_preserving_sequence(memory, when=now))

    try:
        command_set = list(candidates)
    except (TypeError, ValueError):
        return _zero_decision(SafetyState.STOPPED, "INVALID_CANDIDATE_SET", _zero_preserving_sequence(memory, when=now))
    if not command_set:
        return _zero_decision(SafetyState.STOPPED, "NO_COMMAND", _zero_preserving_sequence(memory, when=now))
    if any(not _valid_candidate(item) for item in command_set):
        return _zero_decision(SafetyState.STOPPED, "INVALID_COMMAND_CANDIDATE", _zero_preserving_sequence(memory, when=now))
    if len(command_set) != 1:
        return _zero_decision(SafetyState.STOPPED, "AMBIGUOUS_COMMAND_SET", _zero_preserving_sequence(memory, when=now))
    cmd = command_set[0]
    if cmd.source is CommandSource.SAFE_STOP:
        return _zero_decision(SafetyState.STOPPED, "SAFE_STOP", _clear(memory, when=now),
                              source=CommandSource.SAFE_STOP, raw=cmd.twist)
    if cmd.source is not context.allowed_normal_source:
        return _zero_decision(SafetyState.STOPPED, "SOURCE_NOT_ALLOWED", _zero_preserving_sequence(memory, when=now), raw=cmd.twist)
    if cmd.source_instance_id != context.allowed_source_instance_id:
        return _zero_decision(SafetyState.STOPPED, "SOURCE_INSTANCE_MISMATCH", _zero_preserving_sequence(memory, when=now), raw=cmd.twist)
    if cmd.frame_id != "base_link":
        return _zero_decision(SafetyState.STOPPED, "FRAME_NOT_BASE_LINK", _zero_preserving_sequence(memory, when=now), raw=cmd.twist)
    if (cmd.reset_epoch != context.expected_reset_epoch
            or cmd.runtime_generation != context.expected_runtime_generation):
        return _zero_decision(SafetyState.STOPPED, "COMMAND_EPOCH_GENERATION_MISMATCH", _clear(memory, when=now), raw=cmd.twist)

    if memory.last_source is not None:
        if cmd.source is not memory.last_source:
            return _zero_decision(SafetyState.STOPPED, "SOURCE_HANDOVER_BARRIER", _clear(memory, when=now), raw=cmd.twist)
        if cmd.source_instance_id != memory.last_source_instance_id:
            return _zero_decision(SafetyState.STOPPED, "SOURCE_INSTANCE_HANDOVER_BARRIER", _clear(memory, when=now), raw=cmd.twist)
        if cmd.sequence <= memory.last_sequence:
            return _zero_decision(SafetyState.STOPPED, "SEQUENCE_NOT_NEW", _zero_preserving_sequence(memory, when=now), raw=cmd.twist)

    age = now - float(cmd.steady_received_s)
    if age < 0 or age > context.command_ttl_s:
        return _zero_decision(SafetyState.STOPPED, "TTL_INVALID_OR_EXPIRED", _zero_preserving_sequence(memory, when=now), raw=cmd.twist)

    raw = _triple(cmd.twist)
    previous_v = _triple(memory.previous_final_velocity)
    previous_a = _triple(memory.previous_final_acceleration)
    vmax = _bounds(context.motion_limits, "hard_max")
    amax = _bounds(context.motion_limits, "acceleration_max")
    jmax = _bounds(context.motion_limits, "jerk_max")
    dt = None if memory.last_evaluation_steady_s is None else now - memory.last_evaluation_steady_s

    accepted = SafetyMemory(
        last_source=cmd.source,
        last_source_instance_id=cmd.source_instance_id,
        last_sequence=cmd.sequence,
        last_reset_epoch=cmd.reset_epoch,
        last_runtime_generation=cmd.runtime_generation,
        previous_final_velocity=memory.previous_final_velocity,
        previous_final_acceleration=memory.previous_final_acceleration,
        last_evaluation_steady_s=now,
    )
    if dt is None:
        return _zero_decision(SafetyState.LIMITED, "LIMITER_TIMEBASE_INITIALIZATION", accepted,
                              source=cmd.source, raw=cmd.twist)
    if not _finite(dt) or dt <= 0:
        return _zero_decision(SafetyState.STOPPED, "STEADY_TIME_NOT_INCREASING", _zero_preserving_sequence(memory, when=now), raw=cmd.twist)

    output_values = []
    acceleration_values = []
    for axis in range(3):
        # All three admissible acceleration intervals are intersected before
        # deriving velocity. No post-limit velocity clipping is performed.
        lower = max(
            -amax[axis],
            previous_a[axis] - jmax[axis] * dt,
            (-vmax[axis] - previous_v[axis]) / dt,
        )
        upper = min(
            +amax[axis],
            previous_a[axis] + jmax[axis] * dt,
            (+vmax[axis] - previous_v[axis]) / dt,
        )
        if not math.isfinite(lower) or not math.isfinite(upper) or lower > upper:
            return _zero_decision(
                SafetyState.FAULT,
                "INFEASIBLE_HARD_VELOCITY_ACCELERATION_JERK_ENVELOPE",
                _clear(memory, when=now),
                raw=cmd.twist,
            )
        desired_acceleration = (raw[axis] - previous_v[axis]) / dt
        limited_acceleration = _between(desired_acceleration, lower, upper)
        final_velocity = previous_v[axis] + limited_acceleration * dt
        actual_acceleration = (final_velocity - previous_v[axis]) / dt
        tol = 1e-12
        if (
            not math.isfinite(final_velocity)
            or not math.isfinite(actual_acceleration)
            or abs(final_velocity) > vmax[axis] + tol
            or abs(actual_acceleration) > amax[axis] + tol
            or abs(actual_acceleration - previous_a[axis]) > jmax[axis] * dt + tol
        ):
            return _zero_decision(
                SafetyState.FAULT,
                "INFEASIBLE_HARD_VELOCITY_ACCELERATION_JERK_ENVELOPE",
                _clear(memory, when=now),
                raw=cmd.twist,
            )
        output_values.append(final_velocity)
        acceleration_values.append(actual_acceleration)

    final = _velocity(tuple(output_values))
    actual_acceleration = _velocity(tuple(acceleration_values))
    limited = any(not math.isclose(final_value, raw_value, rel_tol=0.0, abs_tol=1e-12)
                  for final_value, raw_value in zip(output_values, raw))
    next_memory = SafetyMemory(
        last_source=cmd.source,
        last_source_instance_id=cmd.source_instance_id,
        last_sequence=cmd.sequence,
        last_reset_epoch=cmd.reset_epoch,
        last_runtime_generation=cmd.runtime_generation,
        previous_final_velocity=final,
        previous_final_acceleration=actual_acceleration,
        last_evaluation_steady_s=now,
    )
    return SafetyCommandDecision(
        SafetyState.LIMITED if limited else SafetyState.NORMAL,
        cmd.source,
        cmd.twist,
        final,
        ("ENVELOPE_LIMIT_APPLIED",) if limited else ("COMMAND_ACCEPTED",),
        next_memory,
        True,
    )
