from dataclasses import replace
import ast
from pathlib import Path

import pytest

from mecanum_nav_rl.safety.command_safety_core import (
    CommandEnvelopeCandidate,
    CommandSource,
    MotionLimits,
    SafetyContext,
    SafetyMemory,
    SafetyState,
    VelocityCommand,
    evaluate_safety,
)


ROOT = Path(__file__).resolve().parents[1]
UINT32_MAX = (1 << 32) - 1
UINT64_MAX = (1 << 64) - 1


def limits():
    return MotionLimits(
        2.0, 2.0, 2.0,
        10.0, 10.0, 10.0,
        100.0, 100.0, 100.0,
    )


def context(**changes):
    value = SafetyContext(
        expected_reset_epoch=4,
        expected_runtime_generation=7,
        allowed_normal_source=CommandSource.NAV2,
        allowed_source_instance_id=17,
        command_ttl_s=0.5,
        motion_limits=limits(),
        motion_permitted=True,
        safety_loop_healthy=True,
        command_source_healthy=True,
        scan_fresh=True,
        odom_fresh=True,
        tf_valid=True,
        localization_valid=True,
        navigation_state_fresh=True,
        path_valid=True,
        mcu_healthy=True,
        collision_clear=True,
        reset_in_progress=False,
        estop_active=False,
        critical_fault_active=False,
        manual_reset_authorized=False,
    )
    return replace(value, **changes)


def command(**changes):
    value = CommandEnvelopeCandidate(
        source=CommandSource.NAV2,
        sequence=1,
        reset_epoch=4,
        runtime_generation=7,
        source_instance_id=17,
        frame_id="base_link",
        twist=VelocityCommand(0.6, 0.2, 0.3),
        steady_received_s=10.0,
    )
    return replace(value, **changes)


def step(ctx=None, mem=None, cmd=None, now=10.01):
    return evaluate_safety(ctx or context(), mem or SafetyMemory(), [cmd or command()], now)


def prime_memory():
    first = step(now=10.01)
    assert first.safety_state is SafetyState.LIMITED
    return first.next_memory


def test_first_candidate_initializes_limiter_at_zero_then_moves_deterministically():
    first = step(now=10.01)
    assert first.final_command == VelocityCommand(0.0, 0.0, 0.0)
    assert first.next_memory.last_accepted_sequence == 1
    second = step(mem=first.next_memory, cmd=command(sequence=2, steady_received_s=10.02), now=10.03)
    assert second.final_command.linear_x > 0
    assert second.is_unpublished_decision is True


@pytest.mark.parametrize("field", ["expected_reset_epoch", "expected_runtime_generation"])
def test_uint32_maximum_is_valid_for_context(field):
    ctx = context(**{field: UINT32_MAX})
    cmd = command(**{ "reset_epoch" if field == "expected_reset_epoch" else "runtime_generation": UINT32_MAX })
    # First call has a valid contract and initializes the limiter at zero.
    result = step(ctx=ctx, cmd=cmd)
    assert result.reason_codes == ("LIMITER_INITIALIZATION_ZERO",)
    assert result.safety_state is SafetyState.LIMITED


@pytest.mark.parametrize("field", ["expected_reset_epoch", "expected_runtime_generation"])
def test_uint32_overflow_in_context_fails_closed(field):
    result = step(ctx=context(**{field: UINT32_MAX + 1}))
    assert result.final_command == VelocityCommand(0.0, 0.0, 0.0)
    assert result.safety_state is SafetyState.FAULT


@pytest.mark.parametrize("field", ["reset_epoch", "runtime_generation"])
def test_uint32_overflow_in_candidate_fails_closed(field):
    result = step(cmd=command(**{field: UINT32_MAX + 1}))
    assert result.final_command == VelocityCommand(0.0, 0.0, 0.0)
    assert result.safety_state is SafetyState.STOPPED


def test_memory_uint32_and_uint64_fields_have_distinct_ranges():
    valid = SafetyMemory(
        last_accepted_source=CommandSource.NAV2,
        last_accepted_source_instance_id=UINT64_MAX,
        last_accepted_sequence=UINT64_MAX - 1,
        last_accepted_reset_epoch=UINT32_MAX,
        last_accepted_runtime_generation=UINT32_MAX,
        last_evaluation_steady_s=1.0,
    )
    assert evaluate_safety(context(expected_reset_epoch=UINT32_MAX, expected_runtime_generation=UINT32_MAX,
        allowed_source_instance_id=UINT64_MAX), valid,
                          [command(sequence=UINT64_MAX, source_instance_id=UINT64_MAX,
                                   reset_epoch=UINT32_MAX, runtime_generation=UINT32_MAX,
                                   steady_received_s=1.0)], 1.1).safety_state in (
        SafetyState.LIMITED, SafetyState.NORMAL
    )
    for field, value in (("last_accepted_reset_epoch", UINT32_MAX + 1),
                         ("last_accepted_runtime_generation", UINT32_MAX + 1),
                         ("last_accepted_sequence", UINT64_MAX + 1),
                         ("last_accepted_source_instance_id", UINT64_MAX + 1)):
        result = evaluate_safety(context(), replace(SafetyMemory(), **{field: value}), [], 1.0)
        assert result.safety_state is SafetyState.FAULT
        assert result.final_command == VelocityCommand(0.0, 0.0, 0.0)


@pytest.mark.parametrize("field", ["sequence", "source_instance_id"])
def test_uint64_overflow_in_candidate_fails_closed(field):
    result = step(cmd=command(**{field: UINT64_MAX + 1}))
    assert result.final_command == VelocityCommand(0.0, 0.0, 0.0)


@pytest.mark.parametrize("signal,state", [("estop_active", SafetyState.ESTOPPED),
                                            ("critical_fault_active", SafetyState.FAULT)])
def test_emergency_latches_and_bypasses_ramp_until_authorized_new_epoch(signal, state):
    # Seed non-zero velocity so immediate emergency behavior cannot be confused with a ramp.
    prior = replace(prime_memory(), previous_final_velocity=VelocityCommand(0.4, 0.1, 0.2),
                    previous_final_acceleration=VelocityCommand(0.7, 0.3, 0.5))
    active = step(ctx=context(**{signal: True}), mem=prior, now=10.1)
    assert active.safety_state is state
    assert active.final_command == VelocityCommand(0.0, 0.0, 0.0)
    assert active.next_memory.emergency_latch is state
    assert active.next_memory.last_accepted_source is None
    assert active.next_memory.previous_final_acceleration == VelocityCommand(0.0, 0.0, 0.0)

    inactive_no_reset = step(ctx=context(), mem=active.next_memory, cmd=command(sequence=2), now=10.2)
    assert inactive_no_reset.safety_state is state
    assert inactive_no_reset.final_command == VelocityCommand(0.0, 0.0, 0.0)

    same_epoch_reset = step(ctx=context(manual_reset_authorized=True), mem=active.next_memory,
                            cmd=command(sequence=2), now=10.3)
    assert same_epoch_reset.safety_state is state
    assert same_epoch_reset.next_memory.emergency_latch is state

    release = step(ctx=context(expected_reset_epoch=5, manual_reset_authorized=True),
                   mem=active.next_memory, cmd=command(sequence=3, reset_epoch=5), now=10.4)
    assert release.safety_state is SafetyState.STOPPED
    assert release.final_command == VelocityCommand(0.0, 0.0, 0.0)
    assert release.next_memory.emergency_latch is None
    assert release.next_memory.last_accepted_source is None

    fresh = step(ctx=context(expected_reset_epoch=5, manual_reset_authorized=True),
                 mem=release.next_memory, cmd=command(sequence=0, reset_epoch=5, steady_received_s=10.41), now=10.42)
    assert fresh.next_memory.last_accepted_source is CommandSource.NAV2
    assert fresh.safety_state in (SafetyState.LIMITED, SafetyState.NORMAL)


def test_emergency_latch_does_not_release_while_reset_is_in_progress():
    latched = step(ctx=context(estop_active=True), now=10.1)
    result = step(ctx=context(expected_reset_epoch=5, reset_in_progress=True, manual_reset_authorized=True),
                  mem=latched.next_memory, now=10.2)
    assert result.safety_state is SafetyState.ESTOPPED
    assert result.next_memory.emergency_latch is SafetyState.ESTOPPED


def test_reset_in_progress_clears_cache_and_zeros():
    mem = prime_memory()
    result = step(ctx=context(reset_in_progress=True), mem=mem, now=10.2)
    assert result.safety_state is SafetyState.STOPPED
    assert result.final_command == VelocityCommand(0.0, 0.0, 0.0)
    assert result.next_memory.last_accepted_source is None


@pytest.mark.parametrize("change,reason", [
    ("source", "SOURCE_HANDOVER_BARRIER"),
    ("instance", "SOURCE_INSTANCE_HANDOVER_BARRIER"),
    ("generation", "EPOCH_OR_GENERATION_BARRIER"),
    ("epoch", "EPOCH_OR_GENERATION_BARRIER"),
])
def test_identity_handover_barrier_zeros_then_allows_fresh_command_next_cycle(change, reason):
    mem = prime_memory()
    ctx = context()
    next_cmd = command(sequence=2, steady_received_s=10.1)
    if change == "source":
        ctx = context(allowed_normal_source=CommandSource.POLICY)
        next_cmd = command(source=CommandSource.POLICY, steady_received_s=10.1)
    elif change == "instance":
        ctx = context(allowed_source_instance_id=18)
        next_cmd = command(source_instance_id=18, sequence=0, steady_received_s=10.1)
    elif change == "generation":
        ctx = context(expected_runtime_generation=8)
        next_cmd = command(runtime_generation=8, sequence=0, steady_received_s=10.1)
    elif change == "epoch":
        ctx = context(expected_reset_epoch=5)
        next_cmd = command(reset_epoch=5, sequence=0, steady_received_s=10.1)

    barrier = step(ctx=ctx, mem=mem, cmd=next_cmd, now=10.11)
    assert barrier.safety_state is SafetyState.STOPPED
    assert barrier.final_command == VelocityCommand(0.0, 0.0, 0.0)
    assert reason in barrier.reason_codes
    assert barrier.next_memory.last_accepted_source is None

    fresh = step(ctx=ctx, mem=barrier.next_memory,
                 cmd=replace(next_cmd, sequence=next_cmd.sequence + 1, steady_received_s=10.12), now=10.13)
    assert fresh.next_memory.last_accepted_source is ctx.allowed_normal_source
    assert fresh.safety_state in (SafetyState.NORMAL, SafetyState.LIMITED)


@pytest.mark.parametrize("changes", [
    {"source": CommandSource.POLICY},
    {"source_instance_id": 18},
    {"reset_epoch": 5},
    {"runtime_generation": 8},
])
def test_candidate_identity_change_from_accepted_identity_is_a_barrier(changes):
    mem = prime_memory()
    ctx_changes = {}
    if "source" in changes:
        ctx_changes["allowed_normal_source"] = changes["source"]
    if "source_instance_id" in changes:
        ctx_changes["allowed_source_instance_id"] = changes["source_instance_id"]
    if "reset_epoch" in changes:
        ctx_changes["expected_reset_epoch"] = changes["reset_epoch"]
    if "runtime_generation" in changes:
        ctx_changes["expected_runtime_generation"] = changes["runtime_generation"]
    cmd_changes = dict(changes)
    candidate = command(**cmd_changes)
    barrier = step(ctx=context(**ctx_changes), mem=mem, cmd=candidate, now=10.11)
    assert barrier.final_command == VelocityCommand(0.0, 0.0, 0.0)
    assert barrier.safety_state is SafetyState.STOPPED


@pytest.mark.parametrize("field,value", [
    ("frame_id", "odom"),
    ("sequence", 1),
    ("steady_received_s", 9.0),
    ("steady_received_s", 10.5),
])
def test_frame_sequence_and_ttl_rejections_fail_closed(field, value):
    mem = prime_memory() if field == "sequence" else SafetyMemory()
    result = step(mem=mem, cmd=command(**{field: value}), now=10.1)
    assert result.final_command == VelocityCommand(0.0, 0.0, 0.0)
    assert result.safety_state is SafetyState.STOPPED


@pytest.mark.parametrize("twist", [
    VelocityCommand(float("nan"), 0.0, 0.0),
    VelocityCommand(float("inf"), 0.0, 0.0),
    VelocityCommand(0.0, float("-inf"), 0.0),
])
def test_non_finite_command_fails_closed(twist):
    result = step(cmd=command(twist=twist))
    assert result.final_command == VelocityCommand(0.0, 0.0, 0.0)


@pytest.mark.parametrize("field", [
    "motion_permitted", "safety_loop_healthy", "command_source_healthy", "scan_fresh",
    "odom_fresh", "tf_valid", "localization_valid", "navigation_state_fresh",
    "path_valid", "mcu_healthy", "collision_clear",
])
def test_every_health_or_permit_boundary_must_be_explicitly_true(field):
    result = step(ctx=context(**{field: False}), now=10.1)
    assert result.safety_state is SafetyState.STOPPED
    assert result.final_command == VelocityCommand(0.0, 0.0, 0.0)


def test_safe_stop_is_zero_and_clears_motion_memory():
    result = step(cmd=command(source=CommandSource.SAFE_STOP), now=10.1)
    assert result.safety_state is SafetyState.STOPPED
    assert result.selected_source is CommandSource.SAFE_STOP
    assert result.next_memory.last_accepted_source is None


def test_velocity_acceleration_and_jerk_limits_are_injected_and_deterministic():
    tight = MotionLimits(0.5, 0.4, 0.3, 0.2, 0.2, 0.2, 0.5, 0.5, 0.5)
    ctx = context(motion_limits=tight)
    first = step(ctx=ctx, now=10.01)
    assert first.final_command == VelocityCommand(0.0, 0.0, 0.0)
    second = step(ctx=ctx, mem=first.next_memory, cmd=command(sequence=2, steady_received_s=10.02), now=10.12)
    assert second.safety_state is SafetyState.LIMITED
    assert abs(second.final_command.linear_x) <= 0.5
    assert abs(second.final_command.linear_y) <= 0.4
    assert abs(second.final_command.angular_z) <= 0.3
    assert abs(second.next_memory.previous_final_acceleration.linear_x) <= 0.2
    assert abs(second.next_memory.previous_final_acceleration.linear_y) <= 0.2
    assert abs(second.next_memory.previous_final_acceleration.angular_z) <= 0.2
    # A second interval verifies the injected jerk bound against prior acceleration.
    third = step(ctx=ctx, mem=second.next_memory,
                 cmd=command(sequence=3, steady_received_s=10.13), now=10.22)
    dt = 0.1
    assert abs(third.next_memory.previous_final_acceleration.linear_x - second.next_memory.previous_final_acceleration.linear_x) <= 0.5 * dt + 1e-9


def test_output_is_unpublished_decision_not_receipt_and_has_no_nonzero_defaults():
    result = step(now=10.1)
    assert result.is_unpublished_decision is True
    assert "receipt" not in {field.lower() for field in result.__dataclass_fields__}
    assert SafetyMemory().previous_final_velocity == VelocityCommand(0.0, 0.0, 0.0)
    assert SafetyMemory().previous_final_acceleration == VelocityCommand(0.0, 0.0, 0.0)


def test_core_module_has_no_runtime_imports_or_runtime_graph_symbols():
    source_path = ROOT / "mecanum_nav_rl" / "safety" / "command_safety_core.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    forbidden_import_roots = {"rclpy", "gazebo", "nav2", "numpy", "pydantic", "subprocess", "socket"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert not any(alias.name.split(".")[0] in forbidden_import_roots for alias in node.names)
        if isinstance(node, ast.ImportFrom):
            assert (node.module or "").split(".")[0] not in forbidden_import_roots
    forbidden_symbols = {"Node", "Publisher", "Subscriber", "Timer", "LaunchDescription", "Popen", "run"}
    assert not any(
        isinstance(node, ast.Name) and node.id in forbidden_symbols
        or isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in forbidden_symbols
        for node in ast.walk(tree)
    )
