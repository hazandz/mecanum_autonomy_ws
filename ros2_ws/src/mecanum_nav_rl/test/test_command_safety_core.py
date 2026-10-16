"""Offline tests for the pure command-safety decision core."""

import ast
from dataclasses import MISSING
from pathlib import Path

import pytest

from mecanum_nav_rl.safety.command_safety_core import (
    CommandEnvelopeCandidate,
    CommandSource,
    MotionLimits,
    SafetyCommandDecision,
    SafetyContext,
    SafetyMemory,
    SafetyState,
    VelocityCommand,
    evaluate_safety,
)


ROOT = Path(__file__).resolve().parents[1]
ZERO = VelocityCommand(0.0, 0.0, 0.0)


def limits(**overrides):
    values = {
        "max_abs_linear_x": 0.5,
        "max_abs_linear_y": 0.4,
        "max_abs_angular_z": 1.0,
        "max_acceleration_linear_x": 20.0,
        "max_acceleration_linear_y": 20.0,
        "max_acceleration_angular_z": 20.0,
        "max_jerk_linear_x": 200.0,
        "max_jerk_linear_y": 200.0,
        "max_jerk_angular_z": 200.0,
    }
    values.update(overrides)
    return MotionLimits(**values)


def context(**overrides):
    values = {
        "expected_reset_epoch": 4,
        "expected_runtime_generation": 7,
        "allowed_normal_source": CommandSource.NAV2,
        "allowed_source_instance_id": 21,
        "command_ttl_s": 0.5,
        "motion_limits": limits(),
        "motion_permitted": True,
        "safety_loop_healthy": True,
        "command_source_healthy": True,
        "scan_fresh": True,
        "odom_fresh": True,
        "tf_valid": True,
        "localization_valid": True,
        "navigation_state_fresh": True,
        "path_valid": True,
        "mcu_healthy": True,
        "collision_clear": True,
        "reset_in_progress": False,
        "estop_active": False,
        "critical_fault_active": False,
    }
    values.update(overrides)
    return SafetyContext(**values)


def memory(**overrides):
    values = {
        "last_accepted_source": None,
        "last_accepted_source_instance_id": None,
        "last_accepted_sequence": None,
        "previous_final_velocity": ZERO,
        "previous_final_acceleration": ZERO,
        "last_evaluation_steady_s": None,
    }
    values.update(overrides)
    return SafetyMemory(**values)


def candidate(**overrides):
    values = {
        "source": CommandSource.NAV2,
        "sequence": 10,
        "reset_epoch": 4,
        "runtime_generation": 7,
        "source_instance_id": 21,
        "frame_id": "base_link",
        "twist": VelocityCommand(0.2, -0.1, 0.3),
        "steady_received_s": 10.0,
    }
    values.update(overrides)
    return CommandEnvelopeCandidate(**values)


def evaluate(item=None, *, ctx=None, mem=None, now=10.1, candidates=None):
    return evaluate_safety(
        ctx or context(),
        mem or memory(),
        [item or candidate()] if candidates is None else candidates,
        now,
    )


def assert_zero(decision, state=None):
    assert decision.final_command == ZERO
    assert decision.is_unpublished_decision is True
    if state is not None:
        assert decision.safety_state is state


def test_only_context_allowed_source_instance_can_select_motion():
    selected = evaluate(candidate(twist=VelocityCommand(0.0, 0.0, 0.0)))
    assert selected.selected_source is CommandSource.NAV2

    rejected = evaluate(candidate(source=CommandSource.POLICY))
    assert_zero(rejected, SafetyState.STOPPED)
    assert "SOURCE_NOT_ALLOWED" in rejected.reason_codes

    rejected_instance = evaluate(candidate(source_instance_id=22))
    assert_zero(rejected_instance, SafetyState.STOPPED)
    assert "SOURCE_INSTANCE_MISMATCH" in rejected_instance.reason_codes


@pytest.mark.parametrize(
    ("candidate_changes", "now", "memory_changes", "reason"),
    [
        ({"reset_epoch": 3}, 10.1, {}, "RESET_EPOCH_MISMATCH"),
        ({"runtime_generation": 6}, 10.1, {}, "RUNTIME_GENERATION_MISMATCH"),
        ({"frame_id": "odom"}, 10.1, {}, "FRAME_MISMATCH"),
        ({"sequence": 9}, 10.1, {"last_accepted_source": CommandSource.NAV2,
                                  "last_accepted_source_instance_id": 21,
                                  "last_accepted_sequence": 9,
                                  "last_evaluation_steady_s": 10.0}, "SEQUENCE_NOT_STRICTLY_NEWER"),
        ({}, 10.6, {}, "COMMAND_EXPIRED"),
        ({"twist": VelocityCommand(float("nan"), 0.0, 0.0)}, 10.1, {}, "INVALID_CANDIDATE"),
        ({"steady_received_s": float("inf")}, 10.1, {}, "INVALID_CANDIDATE"),
        ({"twist": VelocityCommand(10**1000, 0.0, 0.0)}, 10.1, {}, "INVALID_CANDIDATE"),
    ],
)
def test_invalid_identity_frame_sequence_ttl_or_finite_value_fails_closed(
    candidate_changes, now, memory_changes, reason
):
    result = evaluate(
        candidate(**candidate_changes), now=now, mem=memory(**memory_changes)
    )
    assert_zero(result)
    assert reason in result.reason_codes


def test_future_timestamp_and_ambiguous_candidates_fail_closed():
    future = evaluate(candidate(steady_received_s=10.2), now=10.1)
    assert_zero(future, SafetyState.STOPPED)
    assert "COMMAND_FROM_FUTURE" in future.reason_codes

    ambiguous = evaluate(candidates=[candidate(), candidate(sequence=11)])
    assert_zero(ambiguous, SafetyState.STOPPED)
    assert "CANDIDATE_SELECTION_NOT_UNIQUE" in ambiguous.reason_codes


@pytest.mark.parametrize(
    "field",
    [
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
    ],
)
def test_each_missing_health_or_motion_condition_stops(field):
    result = evaluate(ctx=context(**{field: False}))
    assert_zero(result, SafetyState.STOPPED)
    assert result.next_memory.previous_final_acceleration == ZERO


def test_reset_invalidates_cached_sequence_and_stops():
    prior = memory(
        last_accepted_source=CommandSource.NAV2,
        last_accepted_source_instance_id=21,
        last_accepted_sequence=9,
        previous_final_velocity=VelocityCommand(0.2, 0.0, 0.0),
        previous_final_acceleration=VelocityCommand(1.0, 0.0, 0.0),
        last_evaluation_steady_s=9.9,
    )
    result = evaluate(ctx=context(reset_in_progress=True), mem=prior)
    assert_zero(result, SafetyState.STOPPED)
    assert result.next_memory.last_accepted_sequence is None
    assert result.next_memory.last_evaluation_steady_s is None


@pytest.mark.parametrize(
    ("field", "expected_state", "reason"),
    [
        ("estop_active", SafetyState.ESTOPPED, "ESTOP_ACTIVE"),
        ("critical_fault_active", SafetyState.FAULT, "CRITICAL_FAULT_ACTIVE"),
    ],
)
def test_estop_and_critical_fault_are_immediate_zero_without_ramp(field, expected_state, reason):
    prior = memory(
        previous_final_velocity=VelocityCommand(0.3, 0.2, 0.4),
        previous_final_acceleration=VelocityCommand(2.0, -2.0, 1.0),
        last_evaluation_steady_s=10.0,
    )
    result = evaluate(ctx=context(**{field: True}), mem=prior, now=10.001)
    assert_zero(result, expected_state)
    assert result.next_memory.previous_final_acceleration == ZERO
    assert result.next_memory.previous_final_velocity == ZERO
    assert reason in result.reason_codes


def test_velocity_acceleration_and_jerk_limits_are_deterministic():
    constrained = limits(
        max_abs_linear_x=0.25,
        max_acceleration_linear_x=0.5,
        max_jerk_linear_x=100.0,
        max_abs_linear_y=0.4,
        max_abs_angular_z=1.0,
    )
    first = evaluate(
        candidate(twist=VelocityCommand(1.0, 0.0, 0.0), steady_received_s=1.0),
        ctx=context(motion_limits=constrained, command_ttl_s=2.0),
        now=1.0,
    )
    assert first.safety_state is SafetyState.LIMITED
    assert first.final_command == ZERO  # no invented initial limiter interval

    second_candidate = candidate(sequence=11, twist=VelocityCommand(1.0, 0.0, 0.0), steady_received_s=1.0)
    second_a = evaluate(
        second_candidate,
        ctx=context(motion_limits=constrained, command_ttl_s=2.0),
        mem=first.next_memory,
        now=2.0,
    )
    second_b = evaluate(
        second_candidate,
        ctx=context(motion_limits=constrained, command_ttl_s=2.0),
        mem=first.next_memory,
        now=2.0,
    )
    assert second_a == second_b
    assert second_a.safety_state is SafetyState.LIMITED
    assert second_a.final_command.linear_x == pytest.approx(0.25)
    assert abs(second_a.next_memory.previous_final_acceleration.linear_x) <= 0.5

    jerk_limited = limits(
        max_abs_linear_x=2.0,
        max_acceleration_linear_x=2.0,
        max_jerk_linear_x=4.0,
    )
    prior = memory(
        last_accepted_source=CommandSource.NAV2,
        last_accepted_source_instance_id=21,
        last_accepted_sequence=10,
        previous_final_velocity=ZERO,
        previous_final_acceleration=ZERO,
        last_evaluation_steady_s=1.0,
    )
    jerk = evaluate(
        candidate(sequence=11, twist=VelocityCommand(1.0, 0.0, 0.0), steady_received_s=1.0),
        ctx=context(motion_limits=jerk_limited),
        mem=prior,
        now=1.1,
    )
    assert jerk.safety_state is SafetyState.LIMITED
    assert jerk.final_command.linear_x == pytest.approx(0.04)
    assert jerk.next_memory.previous_final_acceleration.linear_x == pytest.approx(0.4)


def test_normal_state_requires_exact_unmodified_target():
    prior = memory(
        last_accepted_source=CommandSource.NAV2,
        last_accepted_source_instance_id=21,
        last_accepted_sequence=9,
        previous_final_velocity=VelocityCommand(0.1, -0.05, 0.2),
        previous_final_acceleration=ZERO,
        last_evaluation_steady_s=10.0,
    )
    result = evaluate(
        candidate(sequence=10, twist=prior.previous_final_velocity, steady_received_s=10.0),
        mem=prior,
        now=10.1,
    )
    assert result.safety_state is SafetyState.NORMAL
    assert result.final_command == result.raw_command


def test_safe_stop_source_and_wrong_input_types_never_create_motion():
    safe_stop = evaluate(candidate(source=CommandSource.SAFE_STOP))
    assert_zero(safe_stop, SafetyState.STOPPED)
    bad_context = evaluate_safety(object(), memory(), [candidate()], 10.1)
    assert_zero(bad_context, SafetyState.FAULT)
    bad_limits = evaluate(ctx=context(motion_limits=object()))
    assert_zero(bad_limits, SafetyState.FAULT)
    bad_time = evaluate_safety(context(), memory(), [candidate()], float("nan"))
    assert_zero(bad_time, SafetyState.FAULT)


def test_output_is_an_unpublished_decision_and_module_has_no_ros_runtime_imports():
    result = evaluate(candidate(twist=ZERO))
    assert type(result) is SafetyCommandDecision
    assert result.is_unpublished_decision is True
    assert not hasattr(result, "receipt")
    assert not hasattr(result, "published")
    forbidden = {
        "rclpy", "sensor_msgs", "geometry_msgs", "nav_msgs", "mecanum_nav_rl_interfaces",
        "gazebo", "gz", "nav2", "numpy", "pydantic",
    }
    forbidden_runtime_symbols = {
        "Node", "LifecycleNode", "Publisher", "Subscriber", "Timer",
        "LaunchDescription", "create_publisher", "create_subscription",
        "create_timer", "subprocess", "socket", "urlopen",
    }
    for path in (ROOT / "mecanum_nav_rl/safety/command_safety_core.py", Path(__file__)):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imported = set()
        identifiers = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        assert imported.isdisjoint(forbidden)
        assert identifiers.isdisjoint(forbidden_runtime_symbols)


def test_unpublished_result_and_memory_have_no_nonzero_defaults():
    assert VelocityCommand.__dataclass_fields__["linear_x"].default is MISSING
    assert SafetyMemory.__dataclass_fields__["previous_final_velocity"].default is MISSING
    with pytest.raises(TypeError):
        VelocityCommand()
