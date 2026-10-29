"""Production-path regressions for LOCAL_TRAINING goal health and settle."""

from dataclasses import replace

from mecanum_nav_rl.core.lifecycle_types import EpisodeLifecycleIdentity
from mecanum_nav_rl.core.scenario_session import ScenarioSessionBinding
from mecanum_nav_rl.tasks.local_training_goal import (
    GoalSettleState,
    LocalTrainingHealth,
    OracleGoalSample,
    evaluate_local_training_goal,
)

import pytest


_BINDING = ScenarioSessionBinding(
    EpisodeLifecycleIdentity(1, 2, 3),
    'scenario-a',
    '1.0.0',
    'a' * 64,
    'world-a',
    'b' * 64,
    'map-frame-a',
)
_TASK_ID = 'task-a'
_SESSION_ID = 'session-a'
_GOAL_ID = 'goal-a'
_GOAL_XY_M = (0.0, 0.0)
_LIFECYCLE_KEY = (1, 2, 3)


def health(
    timestamp_ns: int,
    *,
    evaluation_ros_now_ns: int | None = None,
    evaluation_steady_now_ns: int | None = None,
    scenario_session_binding: ScenarioSessionBinding = _BINDING,
    task_id: str = _TASK_ID,
    session_id: str = _SESSION_ID,
    lifecycle_key: tuple[int, int, int] = _LIFECYCLE_KEY,
    goal_id: str = _GOAL_ID,
    goal_xy_m: tuple[float, float] = _GOAL_XY_M,
    receipt_session_id: str | None = None,
    receipt_lifecycle_key: tuple[int, int, int] | None = None,
    source_timestamps: dict[str, int] | None = None,
    source_receives: dict[str, int] | None = None,
    flag_overrides: dict[str, object] | None = None,
) -> LocalTrainingHealth:
    """Build internally consistent health facts for one cutoff evaluation."""
    ros_now = (
        timestamp_ns
        if evaluation_ros_now_ns is None
        else evaluation_ros_now_ns
    )
    steady_now = (
        timestamp_ns if evaluation_steady_now_ns is None
        else evaluation_steady_now_ns
    )
    stamps = {
        'oracle': timestamp_ns,
        'oracle_twist': timestamp_ns,
        'scan': timestamp_ns,
        'noisy_odometry': timestamp_ns,
        'reference': timestamp_ns,
        'measured_twist': timestamp_ns,
        'lifecycle': max(0, timestamp_ns - 100_000_000),
        'receipt': max(0, timestamp_ns - 200_000_000),
    }
    if source_timestamps:
        stamps.update(source_timestamps)
    receives = {name: steady_now for name in stamps}
    if source_receives:
        receives.update(source_receives)
    ages = {
        name: (
            ros_now - stamps[name],
            steady_now - receives[name],
        )
        for name in stamps
    }
    flags = {
        name: True for name in (
            'simulator_valid', 'clock_valid', 'reset_complete',
            'scenario_identity_valid', 'world_identity_valid',
            'session_identity_valid', 'lifecycle_valid', 'barrier_valid',
            'safety_ready', 'scan_valid', 'noisy_odometry_valid',
            'reference_valid', 'measured_twist_valid', 'oracle_pose_valid',
            'oracle_twist_valid', 'contact_source_healthy', 'receipt_valid',
            'context_matches',
        )
    }
    flags.update(
        safety_fault=False,
        estop_active=False,
        reset_pending=False,
    )
    if flag_overrides:
        flags.update(flag_overrides)
    return LocalTrainingHealth(
        **flags,
        scenario_session_binding=scenario_session_binding,
        task_id=task_id,
        session_id=session_id,
        lifecycle_key=lifecycle_key,
        goal_id=goal_id,
        goal_x_m=goal_xy_m[0],
        goal_y_m=goal_xy_m[1],
        receipt_session_id=(
            session_id if receipt_session_id is None else receipt_session_id
        ),
        receipt_lifecycle_key=(
            lifecycle_key if receipt_lifecycle_key is None
            else receipt_lifecycle_key
        ),
        oracle_timestamp_ns=stamps['oracle'],
        oracle_twist_timestamp_ns=stamps['oracle_twist'],
        scan_timestamp_ns=stamps['scan'],
        noisy_odometry_timestamp_ns=stamps['noisy_odometry'],
        reference_timestamp_ns=stamps['reference'],
        measured_twist_timestamp_ns=stamps['measured_twist'],
        lifecycle_timestamp_ns=stamps['lifecycle'],
        receipt_timestamp_ns=stamps['receipt'],
        cutoff_ros_ns=timestamp_ns,
        evaluation_ros_now_ns=ros_now,
        oracle_received_steady_ns=receives['oracle'],
        oracle_twist_received_steady_ns=receives['oracle_twist'],
        scan_received_steady_ns=receives['scan'],
        noisy_odometry_received_steady_ns=receives['noisy_odometry'],
        lifecycle_received_steady_ns=receives['lifecycle'],
        receipt_received_steady_ns=receives['receipt'],
        evaluation_steady_now_ns=steady_now,
        scan_ros_age_ns=ages['scan'][0],
        scan_steady_age_ns=ages['scan'][1],
        noisy_odom_ros_age_ns=ages['noisy_odometry'][0],
        noisy_odom_steady_age_ns=ages['noisy_odometry'][1],
        oracle_ros_age_ns=ages['oracle'][0],
        oracle_steady_age_ns=ages['oracle'][1],
        oracle_twist_ros_age_ns=ages['oracle_twist'][0],
        oracle_twist_steady_age_ns=ages['oracle_twist'][1],
        lifecycle_ros_age_ns=ages['lifecycle'][0],
        lifecycle_steady_age_ns=ages['lifecycle'][1],
        receipt_ros_age_ns=ages['receipt'][0],
        receipt_steady_age_ns=ages['receipt'][1],
    )


def sample(
    timestamp_ns: int,
    *,
    x: float = 0.0,
    y: float = 0.0,
    vx: float = 0.03,
    vy: float = 0.0,
    wz: float = 0.05,
    health_facts: LocalTrainingHealth | None = None,
    scenario_session_binding: ScenarioSessionBinding = _BINDING,
    task_id: str = _TASK_ID,
    session_id: str = _SESSION_ID,
    lifecycle_key: tuple[int, int, int] = _LIFECYCLE_KEY,
    goal_id: str = _GOAL_ID,
    goal_xy_m: tuple[float, float] = _GOAL_XY_M,
) -> OracleGoalSample:
    """Build an oracle sample joined to matching default health facts."""
    selected_health = health_facts or health(timestamp_ns)
    return OracleGoalSample(
        timestamp_ns=selected_health.oracle_timestamp_ns,
        received_steady_ns=selected_health.oracle_received_steady_ns,
        lifecycle_key=lifecycle_key,
        scenario_session_binding=scenario_session_binding,
        task_id=task_id,
        session_id=session_id,
        goal_id=goal_id,
        goal_x_m=goal_xy_m[0],
        goal_y_m=goal_xy_m[1],
        pose_x_m=x,
        pose_y_m=y,
        body_vx_mps=vx,
        body_vy_mps=vy,
        body_wz_radps=wz,
        health=selected_health,
    )


def evaluate(
    value: OracleGoalSample,
    state: GoalSettleState,
    *,
    binding: ScenarioSessionBinding = _BINDING,
    task_id: str = _TASK_ID,
    session_id: str = _SESSION_ID,
    goal_id: str = _GOAL_ID,
    goal_xy_m: tuple[float, float] = _GOAL_XY_M,
    settle_time_ns: int = 1_000_000_000,
):
    """Call production evaluation with this test's expected context."""
    return evaluate_local_training_goal(
        value,
        state,
        expected_scenario_session_binding=binding,
        expected_task_id=task_id,
        expected_session_id=session_id,
        expected_goal_id=goal_id,
        expected_goal_xy_m=goal_xy_m,
        settle_time_ns=settle_time_ns,
    )


def test_goal_success_requires_full_ros_second_and_has_no_yaw_requirement():
    """Samples before one ROS second do not succeed; final yaw is absent."""
    state = GoalSettleState()
    for timestamp_ns in (0, 250_000_000, 500_000_000, 750_000_000):
        result = evaluate(sample(timestamp_ns), state)
        state = result.state
        assert not result.success
    result = evaluate(sample(1_000_000_000), state)
    assert result.success
    assert result.state.success


@pytest.mark.parametrize(
    'kwargs',
    [
        {'x': 0.150001, 'vx': 0.0, 'vy': 0.0, 'wz': 0.0},
        {'x': 0.0, 'vx': 0.030001, 'vy': 0.0, 'wz': 0.0},
        {'x': 0.0, 'vx': 0.0, 'vy': 0.0, 'wz': 0.050001},
    ],
)
def test_values_outside_settle_boundaries_clear_the_window(kwargs):
    """Distance and speed checks reject values just outside locked limits."""
    result = evaluate(sample(0, **kwargs), GoalSettleState())
    assert result.healthy
    assert not result.success
    assert result.state.settled_since_ros_ns is None


def test_exact_distance_and_speed_boundaries_are_inclusive():
    """The approved distance and body-speed limits use inclusive bounds."""
    state = GoalSettleState()
    for timestamp_ns in (0, 250_000_000, 500_000_000, 750_000_000):
        edge_sample = sample(
            timestamp_ns,
            x=0.15,
            vx=0.03,
            vy=0.0,
            wz=0.05,
        )
        result = evaluate(edge_sample, state)
        assert result.healthy
        state = result.state
    result = evaluate(
        sample(
            1_000_000_000,
            x=0.15,
            vx=0.03,
            vy=0.0,
            wz=0.05,
        ),
        state,
    )
    assert result.healthy
    assert result.success


def test_health_derives_ros_and_steady_ages_without_cutoff_aliasing():
    """Lifecycle and receipt stamps may differ from the exact sensor cutoff."""
    health_facts = health(
        1_000_000_000,
        evaluation_ros_now_ns=1_200_000_000,
        evaluation_steady_now_ns=2_000_000_000,
        source_timestamps={
            'oracle': 1_100_000_000,
            'oracle_twist': 1_100_000_000,
            'lifecycle': 900_000_000,
            'receipt': 800_000_000,
        },
        source_receives={
            'oracle': 1_900_000_000,
            'oracle_twist': 1_900_000_000,
            'lifecycle': 1_800_000_000,
            'receipt': 1_700_000_000,
        },
    )
    assert health_facts.healthy()
    assert health_facts.lifecycle_timestamp_ns != health_facts.cutoff_ros_ns
    assert health_facts.receipt_timestamp_ns != health_facts.cutoff_ros_ns


def test_stale_source_timestamp_with_claimed_zero_age_is_rejected():
    """Age fields cannot override timestamps from the same evaluation."""
    valid = health(1_000_000_000)
    stale = replace(valid, oracle_timestamp_ns=700_000_000)
    result = evaluate(
        sample(1_000_000_000, health_facts=stale),
        GoalSettleState(),
    )
    assert not result.healthy
    assert not result.success
    assert result.state == GoalSettleState()


def test_steady_receive_age_and_missing_or_future_receives_fail_closed():
    """Receive age is independently derived and missing/future times reject."""
    stale_receive = health(
        1_000_000_000,
        evaluation_steady_now_ns=1_300_000_000,
        source_receives={'oracle': 1_000_000_000},
    )
    missing_receive = replace(stale_receive, oracle_received_steady_ns=None)
    future_receive = health(
        1_000_000_000,
        source_receives={'oracle': 1_000_000_001},
    )
    for facts in (stale_receive, missing_receive, future_receive):
        result = evaluate(
            sample(1_000_000_000, health_facts=facts),
            GoalSettleState(),
        )
        assert not result.healthy
        assert not result.success


def test_context_mismatch_rejects_and_clears_prior_settle_state():
    """A mismatched sample or health cannot reuse the preceding task timer."""
    prior = evaluate(sample(0), GoalSettleState()).state
    matching = health(1_000_000_000)
    wrong_session = replace(matching, session_id='other-session')
    result = evaluate(sample(1_000_000_000, health_facts=wrong_session), prior)
    assert not result.healthy
    assert not result.success
    assert result.state == GoalSettleState()


@pytest.mark.parametrize(
    'mismatch',
    [
        'sample-task',
        'sample-scenario',
        'sample-lifecycle',
        'health-task',
        'health-scenario',
        'health-receipt-lifecycle',
    ],
)
def test_expected_scenario_task_and_lifecycle_context_are_joined(mismatch):
    """No source context can override the expected task binding."""
    value = sample(0)
    if mismatch == 'sample-task':
        value = replace(value, task_id='task-other')
    elif mismatch == 'sample-scenario':
        other_binding = replace(_BINDING, scenario_id='scenario-other')
        value = replace(value, scenario_session_binding=other_binding)
    elif mismatch == 'sample-lifecycle':
        value = replace(value, lifecycle_key=(1, 2, 4))
    elif mismatch == 'health-task':
        value = replace(
            value,
            health=replace(value.health, task_id='task-other'),
        )
    elif mismatch == 'health-scenario':
        other_binding = replace(_BINDING, scenario_id='scenario-other')
        value = replace(value, health=replace(
            value.health, scenario_session_binding=other_binding
        ))
    else:
        value = replace(value, health=replace(
            value.health, receipt_lifecycle_key=(1, 2, 4)
        ))
    result = evaluate(value, GoalSettleState())
    assert not result.healthy
    assert not result.success
    assert result.state == GoalSettleState()


def test_valid_task_and_session_transition_starts_a_fresh_settle_window():
    """New task/session identity with equal coordinates starts a new window."""
    prior = evaluate(sample(0), GoalSettleState()).state
    next_health = health(
        1_000_000_000,
        task_id='task-b',
        session_id='session-b',
    )
    next_sample = sample(
        1_000_000_000,
        health_facts=next_health,
        task_id='task-b',
        session_id='session-b',
    )
    result = evaluate(
        next_sample,
        prior,
        task_id='task-b',
        session_id='session-b',
    )
    assert result.healthy
    assert not result.success
    assert result.state.settled_since_ros_ns == 1_000_000_000


def test_authoritative_reset_lifecycle_starts_a_fresh_settle_window():
    """A new authoritative lifecycle cannot inherit its predecessor timer."""
    prior = evaluate(sample(0), GoalSettleState()).state
    next_binding = replace(
        _BINDING,
        lifecycle_identity=EpisodeLifecycleIdentity(2, 3, 4),
    )
    next_lifecycle = (2, 3, 4)
    next_health = health(
        1_000_000_000,
        scenario_session_binding=next_binding,
        session_id='session-reset',
        lifecycle_key=next_lifecycle,
    )
    next_sample = sample(
        1_000_000_000,
        health_facts=next_health,
        scenario_session_binding=next_binding,
        session_id='session-reset',
        lifecycle_key=next_lifecycle,
    )
    result = evaluate(
        next_sample,
        prior,
        binding=next_binding,
        session_id='session-reset',
    )
    assert result.healthy
    assert not result.success
    assert result.state.lifecycle_key == next_lifecycle
    assert result.state.settled_since_ros_ns == 1_000_000_000


def test_goal_identity_change_resets_but_coordinate_mutation_rejects():
    """New goal identity resets time; old-ID geometry mutation rejects."""
    prior = evaluate(sample(0), GoalSettleState()).state
    identity_health = health(1_000_000_000, goal_id='goal-b')
    identity_change = sample(
        1_000_000_000, health_facts=identity_health, goal_id='goal-b'
    )
    identity_result = evaluate(
        identity_change, prior, goal_id='goal-b'
    )
    assert identity_result.healthy
    assert not identity_result.success
    assert identity_result.state.settled_since_ros_ns == 1_000_000_000

    geometry_health = health(
        1_000_000_000, goal_xy_m=(0.01, 0.0)
    )
    geometry_change = sample(
        1_000_000_000,
        health_facts=geometry_health,
        goal_xy_m=(0.01, 0.0),
    )
    geometry_result = evaluate(
        geometry_change, prior, goal_xy_m=(0.01, 0.0)
    )
    assert not geometry_result.healthy
    assert not geometry_result.success
    assert geometry_result.state == GoalSettleState()


@pytest.mark.parametrize(
    'flag_value', [0, 1, 'true']
)
def test_boolean_health_flags_require_actual_bool_values(flag_value):
    """Truthy integers and strings are not accepted as health evidence."""
    facts = health(0, flag_overrides={'safety_ready': flag_value})
    result = evaluate(sample(0, health_facts=facts), GoalSettleState())
    assert not result.healthy
    assert not result.success


def test_malformed_health_sample_state_and_nonfinite_pose_fail_closed():
    """Malformed public inputs reject without leaking attribute errors."""
    valid = sample(0)
    malformed_health = replace(valid, health=object())
    malformed_state = GoalSettleState(success=1)
    nonfinite_pose = replace(valid, pose_x_m=float('nan'))
    for value, state in (
        (malformed_health, GoalSettleState()),
        (valid, malformed_state),
        (nonfinite_pose, GoalSettleState()),
    ):
        result = evaluate(value, state)
        assert not result.healthy
        assert not result.success
        assert result.state == GoalSettleState()


def test_pause_does_not_advance_ros_settle_time_but_freshness_is_checked():
    """Steady callbacks during ROS pause do not add settle duration."""
    first = evaluate(sample(0), GoalSettleState())
    quarter_second = evaluate(sample(250_000_000), first.state)
    half_second = evaluate(sample(500_000_000), quarter_second.state)
    paused_health = health(
        500_000_000,
        evaluation_steady_now_ns=600_000_000,
    )
    paused = evaluate(
        sample(500_000_000, health_facts=paused_health), half_second.state
    )
    assert paused.healthy
    assert not paused.success
    assert paused.state.settled_since_ros_ns == 0
    assert paused.state.last_ros_ns == 500_000_000

    three_quarters = evaluate(sample(750_000_000), paused.state)
    finished = evaluate(sample(1_000_000_000), three_quarters.state)
    assert finished.success


def test_rollback_and_missing_health_gap_do_not_bridge_settle_window():
    """Rollback and invalid health clear prior settle time."""
    initial = evaluate(sample(500), GoalSettleState()).state
    rollback = evaluate(sample(100), initial)
    assert not rollback.healthy
    assert rollback.state == GoalSettleState()

    missing_health = replace(
        health(250_000_000), contact_source_healthy=False
    )
    gap = evaluate(
        sample(250_000_000, health_facts=missing_health), initial
    )
    assert not gap.healthy
    assert gap.state == GoalSettleState()


def test_health_gap_over_budget_restarts_window_without_interpolation():
    """A long gap starts a new interval at the current observed sample."""
    initial = evaluate(sample(0), GoalSettleState()).state
    gap = evaluate(sample(250_000_001), initial)
    assert gap.healthy
    assert not gap.success
    assert gap.state.settled_since_ros_ns == 250_000_001


@pytest.mark.parametrize(
    ('timestamp_field', 'age_field'),
    [
        ('lifecycle_timestamp_ns', 'lifecycle_ros_age_ns'),
        ('receipt_timestamp_ns', 'receipt_ros_age_ns'),
        ('scan_timestamp_ns', 'scan_ros_age_ns'),
        ('noisy_odometry_timestamp_ns', 'noisy_odom_ros_age_ns'),
    ],
)
def test_stale_lifecycle_receipt_or_sensor_timestamp_cannot_claim_zero_age(
    timestamp_field, age_field
):
    """Every ROS age is checked against its source's own timestamp."""
    facts = health(1_000_000_000)
    stale = replace(
        facts,
        **{timestamp_field: 1},
        **{age_field: 0},
    )
    assert not stale.healthy()


@pytest.mark.parametrize(
    'source_name',
    [
        'scan',
        'noisy_odometry',
        'oracle',
        'oracle_twist',
        'lifecycle',
        'receipt',
    ],
)
def test_steady_receive_age_is_derived_for_each_required_source(source_name):
    """No source can claim a fresh steady receive time independently."""
    facts = health(
        1_000_000_000,
        evaluation_steady_now_ns=1_000_000_000,
        source_receives={source_name: 400_000_000},
    )
    assert not facts.healthy()


def test_invalid_expected_context_rejects_sample_identity():
    """The evaluator needs explicit expected identity from its caller."""
    result = evaluate(sample(0), GoalSettleState(), task_id='')
    assert not result.healthy
    assert result.state == GoalSettleState()


def test_failed_evaluation_does_not_mutate_health_sample_or_prior_state():
    """Input facts and the caller's prior settle state remain unchanged."""
    prior = evaluate(sample(0), GoalSettleState()).state
    invalid_health = replace(health(1_000_000_000), reset_pending=True)
    value = sample(1_000_000_000, health_facts=invalid_health)
    before = (value, value.health, prior)
    result = evaluate(value, prior)
    assert not result.success
    assert (value, value.health, prior) == before
    assert result.state == GoalSettleState()


def test_goal_evaluator_has_no_amcl_nav2_gate_or_ground_truth_alias():
    """LOCAL_TRAINING omits localization gates and raw oracle aliases."""
    assert not any(
        'amcl' in name or 'nav2' in name
        for name in LocalTrainingHealth.__dataclass_fields__
    )
    result = evaluate(sample(0), GoalSettleState())
    assert not hasattr(result, 'pose')
    assert not hasattr(result.state, 'reference')
