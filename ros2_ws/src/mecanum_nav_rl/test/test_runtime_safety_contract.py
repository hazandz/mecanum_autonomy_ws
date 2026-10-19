"""Unit tests for fail-closed lifecycle and planar command safety rules."""
from dataclasses import replace

from mecanum_nav_rl.runtime_safety.safety_contract import (
    BarrierState, PrimaryLifecycle, SafetyInputs, SafetyLifecycleCore,
    SafetySupervisorCore,
)


def _valid(now: int, command=(0.1, 0.1, 0.2)) -> SafetyInputs:
    return SafetyInputs(now, now, now, now, now, BarrierState.READY, True, True, False, command)


def test_lifecycle_owns_identity_and_primary_state_sequence() -> None:
    core = SafetyLifecycleCore()
    assert core.snapshot().primary_state is PrimaryLifecycle.UNCONFIGURED
    configured = core.configure(10)
    assert configured.primary_state is PrimaryLifecycle.INACTIVE
    assert configured.barrier_state is BarrierState.NON_READY
    active = core.activate(20)
    assert active.primary_state is PrimaryLifecycle.ACTIVE
    assert active.barrier_state is BarrierState.READY and active.motion_permitted
    reset = core.begin_reset(30)
    assert reset.reset_epoch == 1 and reset.episode_generation == 1
    assert reset.barrier_state is BarrierState.NON_READY and not reset.motion_permitted
    assert core.refresh(40).sequence == reset.sequence


def test_safety_fails_closed_for_stale_invalid_estop_and_nonfinite_inputs() -> None:
    core = SafetySupervisorCore()
    cases = [
        (replace(_valid(1_000_000_000), command_stamp_ns=1), "COMMAND_STALE_OR_INVALID"),
        (replace(_valid(1_000_000_000), sensor_values_finite=False), "SCAN_NON_FINITE"),
        (replace(_valid(1_000_000_000), odometry_values_finite=False), "FILTERED_ODOMETRY_NON_FINITE"),
        (replace(_valid(1_000_000_000), tf_valid=False), "TF_INVALID"),
        (replace(_valid(1_000_000_000), localization_valid=False), "LOCALIZATION_INVALID"),
        (replace(_valid(1_000_000_000), estop_active=True), "ESTOP_ACTIVE"),
        (replace(_valid(1_000_000_000), lifecycle=BarrierState.NON_READY), "LIFECYCLE_BARRIER_NOT_READY"),
        (replace(_valid(1_000_000_000), command=(float("nan"), 0.0, 0.0)), "COMMAND_NON_FINITE"),
    ]
    for inputs, literal in cases:
        result = core.evaluate(inputs)
        assert not result.accepted and result.command == (0.0, 0.0, 0.0)
        assert literal in result.reasons


def test_velocity_acceleration_and_jerk_limits_are_applied() -> None:
    core = SafetySupervisorCore()
    first = core.evaluate(_valid(1_000_000_000, (0.25, 0.20, 0.80)))
    assert not first.accepted and first.reasons == ("LIMITER_PRIMED",)
    second = core.evaluate(_valid(1_050_000_000, (0.25, 0.20, 0.80)))
    assert second.accepted
    assert max(abs(v) for v in second.command) <= 0.025000001
    assert abs(second.command[0]) <= 0.25
    assert abs(second.command[1]) <= 0.20
    assert abs(second.command[2]) <= 0.80


def test_control_time_regression_fails_closed() -> None:
    core = SafetySupervisorCore()
    core.evaluate(_valid(1_000_000_000))
    core.evaluate(_valid(1_050_000_000))
    result = core.evaluate(_valid(1_040_000_000))
    assert not result.accepted
    assert result.reasons == ("CONTROL_TIMESTAMP_NOT_MONOTONIC",)
