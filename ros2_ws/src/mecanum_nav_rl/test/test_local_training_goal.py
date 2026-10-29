from dataclasses import replace
import pytest
from mecanum_nav_rl.tasks.local_training_goal import GoalSettleState, LocalTrainingHealth, OracleGoalSample, evaluate_local_training_goal

def health(t, *, ok=True):
    values = {name: ok for name in ('simulator_valid', 'clock_valid',
        'reset_complete', 'scenario_identity_valid', 'world_identity_valid', 'session_identity_valid', 'lifecycle_valid', 'barrier_valid', 'safety_ready', 'scan_valid', 'noisy_odometry_valid', 'reference_valid', 'measured_twist_valid', 'oracle_pose_valid', 'oracle_twist_valid', 'contact_source_healthy', 'receipt_valid', 'context_matches')}
    values.update(safety_fault=False, estop_active=False, reset_pending=False,
        oracle_timestamp_ns=t, oracle_twist_timestamp_ns=t, scan_timestamp_ns=t, noisy_odometry_timestamp_ns=t, cutoff_ros_ns=t, evaluation_ros_now_ns=t, oracle_received_steady_ns=t, evaluation_steady_now_ns=t, scan_ros_age_ns=0, scan_steady_age_ns=0, noisy_odom_ros_age_ns=0, noisy_odom_steady_age_ns=0, oracle_ros_age_ns=0, oracle_steady_age_ns=0, lifecycle_ros_age_ns=0, lifecycle_steady_age_ns=0, receipt_ros_age_ns=0, receipt_steady_age_ns=0)
    return LocalTrainingHealth(**values)

def sample(t, *, x=0.0, y=0.0, vx=0.03, vy=0.0, wz=0.05, h=None, key=(1, 2,
    3)):
    return OracleGoalSample(t, t, key, 0, 0, x, y, vx, vy, wz,
        health(t) if h is None else h)

def test_goal_success_requires_full_second_and_has_no_yaw_requirement():
    state = GoalSettleState()
    for t in (0, 250000000, 500000000, 750000000):
        result = evaluate_local_training_goal(sample(t), state)
        state = result.state
        assert not result.success
    result = evaluate_local_training_goal(sample(1000000000), state)
    assert result.success and result.state.success

@pytest.mark.parametrize('kwargs', [{'x': 0.150001, 'vx': 0, 'vy': 0, 'wz': 0},
    {'x': 0, 'vx': 0.030001, 'vy': 0, 'wz': 0}, {'x': 0, 'vx': 0, 'vy': 0,
    'wz': 0.050001}])

def test_distance_and_speed_outside_boundary_clear_settle(kwargs):
    result = evaluate_local_training_goal(sample(0, **kwargs),
        GoalSettleState())
    assert not result.success
    assert result.state.settled_since_ros_ns is None

def test_true_oracle_controls_success_and_missing_required_health_never_succeeds():
    first = evaluate_local_training_goal(sample(0), GoalSettleState()).state
    noisy_estimate_near_goal_does_not_change_oracle_state = sample(1000000000,
        x=0.2)
    result = evaluate_local_training_goal(noisy_estimate_near_goal_does_not_change_oracle_state, first)
    assert not result.success
    bad_health = replace(health(1000000000), contact_source_healthy=False)
    assert not evaluate_local_training_goal(sample(1000000000, h=bad_health),
        first).success

def test_pause_health_gap_rollback_and_reset_break_continuous_window():
    initial = evaluate_local_training_goal(sample(500),
        GoalSettleState()).state
    gap = evaluate_local_training_goal(sample(500000001), initial)
    assert not gap.success and gap.state.settled_since_ros_ns == 500000001
    rollback = evaluate_local_training_goal(sample(100), initial)
    assert not rollback.success and rollback.state.settled_since_ros_ns is None
    reset = evaluate_local_training_goal(sample(250000000, key=(2, 3, 4)),
        initial)
    assert not reset.success and reset.state.settled_since_ros_ns == 250000000

def test_local_training_health_does_not_require_amcl_or_nav2_fields():
    assert not any(('amcl' in name or 'nav2' in name for name in LocalTrainingHealth.__dataclass_fields__))
    assert health(1).healthy()
