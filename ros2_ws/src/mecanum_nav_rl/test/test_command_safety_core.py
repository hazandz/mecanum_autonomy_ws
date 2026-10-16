import ast
from dataclasses import replace
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


PKG = Path(__file__).resolve().parents[1]
U32_MAX = (1 << 32) - 1
U64_MAX = (1 << 64) - 1
TOL = 1e-12


def make_limits(*, vmax=(3.0, 3.0, 3.0), amax=(4.0, 4.0, 4.0), jmax=(20.0, 20.0, 20.0)):
    return MotionLimits(*vmax, *amax, *jmax)


def ctx(**changes):
    value = SafetyContext(
        expected_reset_epoch=6,
        expected_runtime_generation=9,
        allowed_normal_source=CommandSource.NAV2,
        allowed_source_instance_id=31,
        command_ttl_s=0.5,
        motion_limits=make_limits(),
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


def cmd(**changes):
    value = CommandEnvelopeCandidate(
        source=CommandSource.NAV2,
        sequence=1,
        reset_epoch=6,
        runtime_generation=9,
        source_instance_id=31,
        frame_id="base_link",
        twist=VelocityCommand(0.8, 0.5, 0.6),
        steady_received_s=20.0,
    )
    return replace(value, **changes)


def evaluate(c=None, m=None, candidate=None, now=20.01):
    return evaluate_safety(c or ctx(), m or SafetyMemory(), [candidate or cmd()], now)


def seed_memory():
    first = evaluate(now=20.01)
    assert first.final_command == VelocityCommand(0.0, 0.0, 0.0)
    return evaluate(m=first.next_memory, candidate=cmd(sequence=2, steady_received_s=20.02), now=20.11).next_memory


def assert_envelope(decision, prior, limits, dt):
    v0 = (prior.previous_final_velocity.linear_x, prior.previous_final_velocity.linear_y,
          prior.previous_final_velocity.angular_z)
    a0 = (prior.previous_final_acceleration.linear_x, prior.previous_final_acceleration.linear_y,
          prior.previous_final_acceleration.angular_z)
    v1 = (decision.final_command.linear_x, decision.final_command.linear_y,
          decision.final_command.angular_z)
    a1 = (decision.next_memory.previous_final_acceleration.linear_x,
          decision.next_memory.previous_final_acceleration.linear_y,
          decision.next_memory.previous_final_acceleration.angular_z)
    vmax = (limits.hard_max_linear_x, limits.hard_max_linear_y, limits.hard_max_angular_z)
    amax = (limits.acceleration_max_linear_x, limits.acceleration_max_linear_y,
            limits.acceleration_max_angular_z)
    jmax = (limits.jerk_max_linear_x, limits.jerk_max_linear_y, limits.jerk_max_angular_z)
    for i in range(3):
        actual = (v1[i] - v0[i]) / dt
        assert abs(v1[i]) <= vmax[i] + TOL
        assert abs(actual) <= amax[i] + TOL
        assert abs(actual - a0[i]) <= jmax[i] * dt + TOL
        assert a1[i] == pytest.approx(actual, abs=TOL)


def test_initialization_is_zero_then_valid_fresh_command_is_limited_with_all_envelopes():
    first = evaluate(now=20.01)
    assert first.safety_state is SafetyState.LIMITED
    assert first.reason_codes == ("LIMITER_TIMEBASE_INITIALIZATION",)
    prior = first.next_memory
    result = evaluate(m=prior, candidate=cmd(sequence=2, steady_received_s=20.02), now=20.11)
    assert result.safety_state is SafetyState.LIMITED
    assert_envelope(result, prior, ctx().motion_limits, 0.1)


@pytest.mark.parametrize("member", ["expected_reset_epoch", "expected_runtime_generation"])
def test_u32_max_is_valid_and_overflow_fails_closed_in_context(member):
    expected = U32_MAX
    candidate_member = "reset_epoch" if member == "expected_reset_epoch" else "runtime_generation"
    valid = evaluate(c=ctx(**{member: expected}), candidate=cmd(**{candidate_member: expected}))
    assert valid.safety_state is SafetyState.LIMITED
    invalid = evaluate(c=ctx(**{member: U32_MAX + 1}))
    assert invalid.safety_state is SafetyState.FAULT
    assert invalid.final_command == VelocityCommand(0.0, 0.0, 0.0)


@pytest.mark.parametrize("member", ["reset_epoch", "runtime_generation"])
def test_u32_overflow_in_candidate_fails_closed(member):
    result = evaluate(candidate=cmd(**{member: U32_MAX + 1}))
    assert result.safety_state is SafetyState.STOPPED
    assert result.final_command == VelocityCommand(0.0, 0.0, 0.0)


def test_u64_max_sequence_and_source_instance_are_valid_but_overflow_is_rejected():
    memory = SafetyMemory(
        last_source=CommandSource.NAV2,
        last_source_instance_id=U64_MAX,
        last_sequence=U64_MAX - 1,
        last_reset_epoch=6,
        last_runtime_generation=9,
        last_evaluation_steady_s=1.0,
    )
    context = ctx(allowed_source_instance_id=U64_MAX)
    valid = evaluate(c=context, m=memory,
                     candidate=cmd(sequence=U64_MAX, source_instance_id=U64_MAX, steady_received_s=1.0), now=1.1)
    assert valid.safety_state in (SafetyState.NORMAL, SafetyState.LIMITED)
    assert evaluate(candidate=cmd(sequence=U64_MAX + 1)).safety_state is SafetyState.STOPPED
    assert evaluate(candidate=cmd(source_instance_id=U64_MAX + 1)).safety_state is SafetyState.STOPPED


@pytest.mark.parametrize("member,value", [
    ("last_reset_epoch", U32_MAX + 1),
    ("last_runtime_generation", U32_MAX + 1),
    ("last_sequence", U64_MAX + 1),
    ("last_source_instance_id", U64_MAX + 1),
])
def test_memory_uses_exact_integer_domain_per_field(member, value):
    result = evaluate(m=replace(SafetyMemory(), **{member: value}), candidate=None)
    assert result.safety_state is SafetyState.FAULT
    assert result.final_command == VelocityCommand(0.0, 0.0, 0.0)


@pytest.mark.parametrize("signal,state", [
    ("estop_active", SafetyState.ESTOPPED),
    ("critical_fault_active", SafetyState.FAULT),
])
def test_estop_and_critical_fault_latch_without_ramp_and_require_manual_new_epoch(signal, state):
    prior = replace(seed_memory(),
                    previous_final_velocity=VelocityCommand(0.7, -0.2, 0.4),
                    previous_final_acceleration=VelocityCommand(1.2, -0.4, 0.6))
    emergency = evaluate(c=ctx(**{signal: True}), m=prior, now=20.2)
    assert emergency.safety_state is state
    assert emergency.final_command == VelocityCommand(0.0, 0.0, 0.0)
    assert emergency.next_memory.emergency_latch is state
    assert emergency.next_memory.last_source is None
    assert emergency.next_memory.previous_final_acceleration == VelocityCommand(0.0, 0.0, 0.0)

    signal_cleared = evaluate(c=ctx(), m=emergency.next_memory,
                              candidate=cmd(sequence=3), now=20.3)
    assert signal_cleared.safety_state is state
    same_epoch = evaluate(c=ctx(manual_reset_authorized=True), m=emergency.next_memory,
                          now=20.4)
    assert same_epoch.safety_state is state
    assert same_epoch.next_memory.emergency_latch is state

    released = evaluate(c=ctx(expected_reset_epoch=7, manual_reset_authorized=True),
                        m=emergency.next_memory,
                        candidate=cmd(reset_epoch=7, sequence=0, steady_received_s=20.5), now=20.51)
    assert released.safety_state is SafetyState.STOPPED
    assert released.final_command == VelocityCommand(0.0, 0.0, 0.0)
    assert released.next_memory.emergency_latch is None
    assert released.next_memory.last_source is None

    next_cycle = evaluate(c=ctx(expected_reset_epoch=7, manual_reset_authorized=True),
                          m=released.next_memory,
                          candidate=cmd(reset_epoch=7, sequence=0, steady_received_s=20.52), now=20.53)
    assert next_cycle.next_memory.last_source is CommandSource.NAV2


def test_latch_is_not_released_while_reset_is_in_progress():
    latched = evaluate(c=ctx(estop_active=True), now=20.1)
    still_latched = evaluate(c=ctx(expected_reset_epoch=7, reset_in_progress=True,
                                   manual_reset_authorized=True), m=latched.next_memory, now=20.2)
    assert still_latched.safety_state is SafetyState.ESTOPPED
    assert still_latched.next_memory.emergency_latch is SafetyState.ESTOPPED


def test_estop_state_has_priority_over_a_stale_motion_envelope():
    stale_motion = replace(SafetyMemory(),
                           previous_final_velocity=VelocityCommand(999.0, 0.0, 0.0))
    result = evaluate(c=ctx(estop_active=True), m=stale_motion, now=20.1)
    assert result.safety_state is SafetyState.ESTOPPED
    assert result.final_command == VelocityCommand(0.0, 0.0, 0.0)


def test_reset_in_progress_is_zero_barrier_and_invalidates_command_identity():
    memory = seed_memory()
    result = evaluate(c=ctx(reset_in_progress=True), m=memory, now=20.2)
    assert result.final_command == VelocityCommand(0.0, 0.0, 0.0)
    assert result.next_memory.last_source is None


@pytest.mark.parametrize("kind", ["source", "source_instance", "runtime_generation", "reset_epoch"])
def test_identity_handover_has_zero_barrier_then_next_cycle_accepts_fresh_command(kind):
    memory = seed_memory()
    c = ctx()
    command = cmd(sequence=3, steady_received_s=20.2)
    if kind == "source":
        c = ctx(allowed_normal_source=CommandSource.POLICY)
        command = cmd(source=CommandSource.POLICY, steady_received_s=20.2)
    elif kind == "source_instance":
        c = ctx(allowed_source_instance_id=32)
        command = cmd(source_instance_id=32, sequence=0, steady_received_s=20.2)
    elif kind == "runtime_generation":
        c = ctx(expected_runtime_generation=10)
        command = cmd(runtime_generation=10, sequence=0, steady_received_s=20.2)
    else:
        c = ctx(expected_reset_epoch=7)
        command = cmd(reset_epoch=7, sequence=0, steady_received_s=20.2)

    barrier = evaluate(c=c, m=memory, candidate=command, now=20.21)
    assert barrier.safety_state is SafetyState.STOPPED
    assert barrier.final_command == VelocityCommand(0.0, 0.0, 0.0)
    assert barrier.next_memory.last_source is None
    fresh = evaluate(c=c, m=barrier.next_memory,
                     candidate=replace(command, sequence=command.sequence + 1, steady_received_s=20.22), now=20.23)
    assert fresh.next_memory.last_source is c.allowed_normal_source


@pytest.mark.parametrize("source", [CommandSource.POLICY, CommandSource.TELEOP])
def test_source_change_even_with_same_instance_id_is_barrier(source):
    prior = seed_memory()
    c = ctx(allowed_normal_source=source)
    result = evaluate(c=c, m=prior,
                      candidate=cmd(source=source, steady_received_s=20.2), now=20.21)
    assert result.safety_state is SafetyState.STOPPED
    assert result.next_memory.last_source is None


@pytest.mark.parametrize("field,value", [
    ("frame_id", "odom"),
    ("steady_received_s", 19.0),
    ("steady_received_s", 20.8),
])
def test_wrong_frame_and_expired_or_future_ttl_fail_closed(field, value):
    result = evaluate(candidate=cmd(**{field: value}), now=20.1)
    assert result.safety_state is SafetyState.STOPPED
    assert result.final_command == VelocityCommand(0.0, 0.0, 0.0)


@pytest.mark.parametrize("twist", [
    VelocityCommand(float("nan"), 0.0, 0.0),
    VelocityCommand(0.0, float("inf"), 0.0),
    VelocityCommand(0.0, 0.0, float("-inf")),
])
def test_non_finite_command_fails_closed(twist):
    assert evaluate(candidate=cmd(twist=twist)).final_command == VelocityCommand(0.0, 0.0, 0.0)


@pytest.mark.parametrize("field", [
    "motion_permitted", "safety_loop_healthy", "command_source_healthy", "scan_fresh",
    "odom_fresh", "tf_valid", "localization_valid", "navigation_state_fresh",
    "path_valid", "mcu_healthy", "collision_clear",
])
def test_every_health_boundary_fails_closed(field):
    result = evaluate(c=ctx(**{field: False}), now=20.1)
    assert result.safety_state is SafetyState.STOPPED
    assert result.final_command == VelocityCommand(0.0, 0.0, 0.0)


def test_safe_stop_and_ambiguous_candidates_are_zero():
    safe = evaluate(candidate=cmd(source=CommandSource.SAFE_STOP), now=20.1)
    assert safe.safety_state is SafetyState.STOPPED
    assert safe.selected_source is CommandSource.SAFE_STOP
    ambiguous = evaluate_safety(ctx(), SafetyMemory(), [cmd(), cmd(sequence=2)], 20.1)
    assert ambiguous.safety_state is SafetyState.STOPPED
    assert ambiguous.reason_codes == ("AMBIGUOUS_COMMAND_SET",)


def test_rejected_duplicate_does_not_clear_anti_replay_sequence_cache():
    accepted = seed_memory()
    duplicate = evaluate(m=accepted,
                         candidate=cmd(sequence=accepted.last_sequence,
                                       steady_received_s=20.2), now=20.21)
    assert duplicate.safety_state is SafetyState.STOPPED
    assert duplicate.next_memory.last_sequence == accepted.last_sequence
    assert duplicate.final_command == VelocityCommand(0.0, 0.0, 0.0)
    replay = evaluate(m=duplicate.next_memory,
                      candidate=cmd(sequence=accepted.last_sequence,
                                    steady_received_s=20.22), now=20.23)
    assert replay.reason_codes == ("SEQUENCE_NOT_NEW",)
    assert replay.final_command == VelocityCommand(0.0, 0.0, 0.0)


@pytest.mark.parametrize("axis,previous_a,target", [
    ("linear_x", 1.0, -1.0),
    ("linear_y", 1.0, -1.0),
    ("angular_z", 1.0, -1.0),
    ("linear_x", -1.0, 1.0),
    ("linear_y", -1.0, 1.0),
    ("angular_z", -1.0, 1.0),
])
def test_jerk_interval_is_anchored_on_prior_acceleration_for_each_axis(axis, previous_a, target):
    axes = {"linear_x": 0, "linear_y": 1, "angular_z": 2}
    i = axes[axis]
    v0 = [0.0, 0.0, 0.0]
    a0 = [0.0, 0.0, 0.0]
    a0[i] = previous_a
    memory = SafetyMemory(
        last_source=CommandSource.NAV2,
        last_source_instance_id=31,
        last_sequence=10,
        last_reset_epoch=6,
        last_runtime_generation=9,
        previous_final_velocity=VelocityCommand(*v0),
        previous_final_acceleration=VelocityCommand(*a0),
        last_evaluation_steady_s=2.0,
    )
    target_v = [0.2, 0.2, 0.2]
    target_v[i] = target
    c = ctx(motion_limits=make_limits(vmax=(2.0, 2.0, 2.0), amax=(3.0, 3.0, 3.0), jmax=(2.0, 2.0, 2.0)))
    result = evaluate(c=c, m=memory, candidate=cmd(sequence=11, twist=VelocityCommand(*target_v), steady_received_s=2.01), now=2.1)
    assert result.safety_state in (SafetyState.NORMAL, SafetyState.LIMITED)
    new_acc = _component(result.next_memory.previous_final_acceleration, i)
    dt = 0.1
    assert abs(new_acc - previous_a) <= 2.0 * dt + TOL
    assert new_acc == pytest.approx((
        _component(result.final_command, i) - _component(memory.previous_final_velocity, i)
    ) / dt, abs=TOL)
    assert_envelope(result, memory, c.motion_limits, dt)


def _component(v, i):
    return (v.linear_x, v.linear_y, v.angular_z)[i]


@pytest.mark.parametrize("axis", ["linear_x", "linear_y", "angular_z"])
def test_velocity_boundary_can_make_intersection_infeasible_without_post_clip(axis):
    index = {"linear_x": 0, "linear_y": 1, "angular_z": 2}[axis]
    velocity = [0.0, 0.0, 0.0]
    acceleration = [0.0, 0.0, 0.0]
    velocity[index] = 1.0
    acceleration[index] = 1.0
    previous = SafetyMemory(
        last_source=CommandSource.NAV2,
        last_source_instance_id=31,
        last_sequence=4,
        last_reset_epoch=6,
        last_runtime_generation=9,
        previous_final_velocity=VelocityCommand(*velocity),
        previous_final_acceleration=VelocityCommand(*acceleration),
        last_evaluation_steady_s=5.0,
    )
    limits = make_limits(vmax=(1.0, 1.0, 1.0), amax=(2.0, 2.0, 2.0), jmax=(0.5, 0.5, 0.5))
    c = ctx(motion_limits=limits)
    target = [0.0, 0.0, 0.0]
    target[index] = -1.0
    result = evaluate(c=c, m=previous,
                      candidate=cmd(sequence=5, twist=VelocityCommand(*target), steady_received_s=5.01), now=5.1)
    assert result.safety_state is SafetyState.FAULT
    assert result.reason_codes == ("INFEASIBLE_HARD_VELOCITY_ACCELERATION_JERK_ENVELOPE",)
    assert result.final_command == VelocityCommand(0.0, 0.0, 0.0)
    assert result.next_memory.last_source is None


def test_successful_jerk_limited_result_never_post_clips_velocity_and_stores_actual_acceleration():
    previous = SafetyMemory(
        last_source=CommandSource.NAV2,
        last_source_instance_id=31,
        last_sequence=8,
        last_reset_epoch=6,
        last_runtime_generation=9,
        previous_final_velocity=VelocityCommand(0.3, -0.2, 0.1),
        previous_final_acceleration=VelocityCommand(0.8, -0.6, 0.4),
        last_evaluation_steady_s=3.0,
    )
    limits = make_limits(vmax=(0.5, 0.5, 0.5), amax=(1.0, 1.0, 1.0), jmax=(0.5, 0.5, 0.5))
    c = ctx(motion_limits=limits)
    result = evaluate(c=c, m=previous,
                      candidate=cmd(sequence=9, twist=VelocityCommand(4.0, -4.0, 4.0), steady_received_s=3.01), now=3.1)
    assert result.safety_state is SafetyState.LIMITED
    assert_envelope(result, previous, limits, 0.1)
    assert result.is_unpublished_decision is True
    assert "receipt" not in {field.lower() for field in result.__dataclass_fields__}


def test_unpublished_decision_and_module_do_not_import_or_create_runtime_graph():
    path = PKG / "mecanum_nav_rl" / "safety" / "command_safety_core.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    banned_imports = {"rclpy", "launch", "launch_ros", "tf2_ros", "nav_msgs", "geometry_msgs",
                      "gazebo", "nav2", "numpy", "pydantic", "socket", "subprocess"}
    banned_symbols = {"Node", "Publisher", "Subscriber", "Timer", "LaunchDescription",
                      "Popen", "create_publisher", "create_subscription"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(alias.name.split(".")[0] not in banned_imports for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert (node.module or "").split(".")[0] not in banned_imports
        if isinstance(node, ast.Name):
            assert node.id not in banned_symbols
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id not in banned_symbols
    assert evaluate().is_unpublished_decision is True
    assert SafetyMemory().previous_final_velocity == VelocityCommand(0.0, 0.0, 0.0)
