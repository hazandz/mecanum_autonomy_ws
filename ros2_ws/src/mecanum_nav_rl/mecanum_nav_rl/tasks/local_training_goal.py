"""Pure LOCAL_TRAINING oracle goal health and settle evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from math import hypot, isfinite
from numbers import Real

from mecanum_nav_rl.core.scenario_session import ScenarioSessionBinding


_SETTLE_TIME_NS = 1_000_000_000
_MAX_SENSOR_AGE_NS = 500_000_000
_MAX_ODOMETRY_AGE_NS = 250_000_000
_MAX_ORACLE_AGE_NS = 250_000_000
_MAX_LIFECYCLE_AGE_NS = 500_000_000
_MAX_RECEIPT_AGE_NS = 500_000_000
_MAX_SETTLE_SAMPLE_GAP_NS = _MAX_ORACLE_AGE_NS


@dataclass(frozen=True, slots=True)
class LocalTrainingHealth:
    """Copied health, identity, and timestamp facts for one evaluation."""

    simulator_valid: bool
    clock_valid: bool
    reset_complete: bool
    scenario_identity_valid: bool
    world_identity_valid: bool
    session_identity_valid: bool
    lifecycle_valid: bool
    barrier_valid: bool
    safety_ready: bool
    safety_fault: bool
    estop_active: bool
    reset_pending: bool
    scan_valid: bool
    noisy_odometry_valid: bool
    reference_valid: bool
    measured_twist_valid: bool
    oracle_pose_valid: bool
    oracle_twist_valid: bool
    contact_source_healthy: bool
    receipt_valid: bool
    context_matches: bool
    scenario_session_binding: ScenarioSessionBinding
    task_id: str
    session_id: str
    lifecycle_key: tuple[int, int, int]
    goal_id: str
    goal_x_m: float
    goal_y_m: float
    receipt_session_id: str
    receipt_lifecycle_key: tuple[int, int, int]
    oracle_timestamp_ns: int
    oracle_twist_timestamp_ns: int
    scan_timestamp_ns: int
    noisy_odometry_timestamp_ns: int
    reference_timestamp_ns: int
    measured_twist_timestamp_ns: int
    lifecycle_timestamp_ns: int
    receipt_timestamp_ns: int
    cutoff_ros_ns: int
    evaluation_ros_now_ns: int
    oracle_received_steady_ns: int
    oracle_twist_received_steady_ns: int
    scan_received_steady_ns: int
    noisy_odometry_received_steady_ns: int
    lifecycle_received_steady_ns: int
    receipt_received_steady_ns: int
    evaluation_steady_now_ns: int
    scan_ros_age_ns: int
    scan_steady_age_ns: int
    noisy_odom_ros_age_ns: int
    noisy_odom_steady_age_ns: int
    oracle_ros_age_ns: int
    oracle_steady_age_ns: int
    oracle_twist_ros_age_ns: int
    oracle_twist_steady_age_ns: int
    lifecycle_ros_age_ns: int
    lifecycle_steady_age_ns: int
    receipt_ros_age_ns: int
    receipt_steady_age_ns: int

    def healthy(self) -> bool:
        """Check flags, source pairing, and derived freshness budgets."""
        try:
            bool_fields = (
                'simulator_valid', 'clock_valid', 'reset_complete',
                'scenario_identity_valid', 'world_identity_valid',
                'session_identity_valid', 'lifecycle_valid', 'barrier_valid',
                'safety_ready', 'safety_fault', 'estop_active',
                'reset_pending', 'scan_valid', 'noisy_odometry_valid',
                'reference_valid', 'measured_twist_valid', 'oracle_pose_valid',
                'oracle_twist_valid', 'contact_source_healthy',
                'receipt_valid', 'context_matches',
            )
            if any(
                type(getattr(self, name)) is not bool for name in bool_fields
            ):
                return False
            if not all((
                self.simulator_valid,
                self.clock_valid,
                self.reset_complete,
                self.scenario_identity_valid,
                self.world_identity_valid,
                self.session_identity_valid,
                self.lifecycle_valid,
                self.barrier_valid,
                self.safety_ready,
                not self.safety_fault,
                not self.estop_active,
                not self.reset_pending,
                self.scan_valid,
                self.noisy_odometry_valid,
                self.reference_valid,
                self.measured_twist_valid,
                self.oracle_pose_valid,
                self.oracle_twist_valid,
                self.contact_source_healthy,
                self.receipt_valid,
                self.context_matches,
            )):
                return False

            if not _valid_context_fields(
                self.scenario_session_binding, self.task_id, self.session_id,
                self.lifecycle_key, self.goal_id, self.goal_x_m, self.goal_y_m,
            ):
                return False
            if (
                self.receipt_session_id != self.session_id
                or self.receipt_lifecycle_key != self.lifecycle_key
                or type(self.receipt_session_id) is not str
                or not self.receipt_session_id
                or not _valid_lifecycle_key(self.receipt_lifecycle_key)
            ):
                return False

            source_facts = (
                (self.scan_timestamp_ns, self.scan_received_steady_ns,
                    self.scan_ros_age_ns, self.scan_steady_age_ns,
                    _MAX_SENSOR_AGE_NS),
                (self.noisy_odometry_timestamp_ns,
                    self.noisy_odometry_received_steady_ns,
                    self.noisy_odom_ros_age_ns,
                    self.noisy_odom_steady_age_ns,
                    _MAX_ODOMETRY_AGE_NS),
                (self.oracle_timestamp_ns, self.oracle_received_steady_ns,
                    self.oracle_ros_age_ns, self.oracle_steady_age_ns,
                    _MAX_ORACLE_AGE_NS),
                (self.oracle_twist_timestamp_ns,
                    self.oracle_twist_received_steady_ns,
                    self.oracle_twist_ros_age_ns,
                    self.oracle_twist_steady_age_ns, _MAX_ORACLE_AGE_NS),
                (self.lifecycle_timestamp_ns,
                    self.lifecycle_received_steady_ns,
                    self.lifecycle_ros_age_ns,
                    self.lifecycle_steady_age_ns,
                    _MAX_LIFECYCLE_AGE_NS),
                (self.receipt_timestamp_ns,
                    self.receipt_received_steady_ns,
                    self.receipt_ros_age_ns,
                    self.receipt_steady_age_ns, _MAX_RECEIPT_AGE_NS),
            )
            now_values = (
                self.evaluation_ros_now_ns,
                self.evaluation_steady_now_ns,
                self.cutoff_ros_ns,
            )
            if any(
                type(value) is not int or value < 0 for value in now_values
            ):
                return False
            if any(
                type(value) is not int or value < 0
                for facts in source_facts for value in facts[:2]
            ):
                return False
            for source_fact in source_facts:
                stamp_ns, received_ns, ros_age_ns, steady_age_ns, budget_ns = (
                    source_fact
                )
                if (
                    type(ros_age_ns) is not int
                    or type(steady_age_ns) is not int
                ):
                    return False
                derived_ros_age = self.evaluation_ros_now_ns - stamp_ns
                derived_steady_age = (
                    self.evaluation_steady_now_ns - received_ns
                )
                if (
                    derived_ros_age < 0
                    or derived_steady_age < 0
                    or ros_age_ns != derived_ros_age
                    or steady_age_ns != derived_steady_age
                    or ros_age_ns > budget_ns
                    or steady_age_ns > budget_ns
                ):
                    return False

            sensor_cutoff = self.cutoff_ros_ns
            return (
                self.scan_timestamp_ns == sensor_cutoff
                and self.noisy_odometry_timestamp_ns == sensor_cutoff
                and self.reference_timestamp_ns == sensor_cutoff
                and self.measured_twist_timestamp_ns == sensor_cutoff
                and self.oracle_timestamp_ns == self.oracle_twist_timestamp_ns
            )
        except (AttributeError, TypeError, ValueError, OverflowError):
            return False


@dataclass(frozen=True, slots=True)
class OracleGoalSample:
    """Oracle pose/twist scalars and their exact task context."""

    timestamp_ns: int
    received_steady_ns: int
    lifecycle_key: tuple[int, int, int]
    scenario_session_binding: ScenarioSessionBinding
    task_id: str
    session_id: str
    goal_id: str
    goal_x_m: float
    goal_y_m: float
    pose_x_m: float
    pose_y_m: float
    body_vx_mps: float
    body_vy_mps: float
    body_wz_radps: float
    health: LocalTrainingHealth


@dataclass(frozen=True, slots=True)
class GoalSettleState:
    """Immutable settle clock bound to one lifecycle, task, and goal."""

    lifecycle_key: tuple[int, int, int] | None = None
    settled_since_ros_ns: int | None = None
    last_ros_ns: int | None = None
    success: bool = False
    scenario_session_binding: ScenarioSessionBinding | None = None
    task_id: str | None = None
    session_id: str | None = None
    goal_id: str | None = None
    goal_xy_m: tuple[float, float] | None = None

    @property
    def context_values(self) -> tuple[object, ...] | None:
        """Return the bound task/goal identity used by the settle clock."""
        if self.scenario_session_binding is None:
            return None
        return _context_values(
            self.scenario_session_binding,
            self.task_id,
            self.session_id,
            self.goal_id,
            self.goal_xy_m,
        )


@dataclass(frozen=True, slots=True)
class GoalSettleResult:
    """Fail-closed result and next immutable settle state."""

    state: GoalSettleState
    healthy: bool
    distance_m: float | None
    success: bool
    reason: str | None = None


def evaluate_local_training_goal(
    sample: OracleGoalSample,
    state: GoalSettleState,
    *,
    expected_scenario_session_binding: ScenarioSessionBinding,
    expected_task_id: str,
    expected_session_id: str,
    expected_goal_id: str,
    expected_goal_xy_m: tuple[float, float],
    settle_time_ns: int = _SETTLE_TIME_NS,
) -> GoalSettleResult:
    """Evaluate one oracle sample against an explicit expected task context."""
    try:
        if not isinstance(sample, OracleGoalSample):
            return _invalid_result('invalid oracle sample type')
        if not isinstance(state, GoalSettleState):
            return _invalid_result('invalid settle state type')
        if not _valid_state(state):
            return _invalid_result('malformed settle state')
        if (
            type(settle_time_ns) is not int
            or settle_time_ns != _SETTLE_TIME_NS
        ):
            return _invalid_result(
                'LOCAL_TRAINING settle duration is fixed at one ROS second'
            )
        if not _valid_expected_context(
            expected_scenario_session_binding,
            expected_task_id,
            expected_session_id,
            expected_goal_id,
            expected_goal_xy_m,
        ):
            return _invalid_result('expected goal context is malformed')
        if not _valid_lifecycle_key(sample.lifecycle_key):
            return _invalid_result('sample lifecycle identity is malformed')
        if not _valid_context_fields(
            sample.scenario_session_binding,
            sample.task_id,
            sample.session_id,
            sample.lifecycle_key,
            sample.goal_id,
            sample.goal_x_m,
            sample.goal_y_m,
        ):
            return _invalid_result('sample task context is malformed')
        sample_health = sample.health
        if not isinstance(sample_health, LocalTrainingHealth):
            return _invalid_result('required health facts have the wrong type')
        if not sample_health.healthy():
            return _invalid_result('required LOCAL_TRAINING health is invalid')
        if not _same_context(
            sample,
            sample_health,
            expected_scenario_session_binding,
            expected_task_id,
            expected_session_id,
            expected_goal_id,
            expected_goal_xy_m,
        ):
            return _invalid_result(
                'sample or health context differs from expected task'
            )
        if (
            type(sample.timestamp_ns) is not int
            or type(sample.received_steady_ns) is not int
            or sample.timestamp_ns != sample_health.oracle_timestamp_ns
            or sample.received_steady_ns
            != sample_health.oracle_received_steady_ns
        ):
            return _invalid_result(
                'oracle sample timing differs from admitted health'
            )

        values = (
            sample.pose_x_m, sample.pose_y_m, sample.body_vx_mps,
            sample.body_vy_mps, sample.body_wz_radps,
        )
        if not all(_finite_real(value) for value in values):
            return _invalid_result('oracle pose or twist is malformed')

        expected_x, expected_y = expected_goal_xy_m
        distance = hypot(
            expected_x - float(sample.pose_x_m),
            expected_y - float(sample.pose_y_m),
        )
        speed = hypot(float(sample.body_vx_mps), float(sample.body_vy_mps))
        is_settled = (
            distance <= 0.15
            and speed <= 0.03
            and abs(float(sample.body_wz_radps)) <= 0.05
        )
        context = _context_values(
            expected_scenario_session_binding,
            expected_task_id,
            expected_session_id,
            expected_goal_id,
            expected_goal_xy_m,
        )
        if _goal_geometry_changed_within_identity(state, context):
            return _invalid_result(
                'goal coordinates changed without a new task or goal identity'
            )
        if not is_settled:
            return GoalSettleResult(
                _bound_state(context, last_ros_ns=sample.timestamp_ns),
                True,
                distance,
                False,
            )

        if state.context_values != context or state.last_ros_ns is None:
            settled_since = sample.timestamp_ns
        elif sample.timestamp_ns < state.last_ros_ns:
            return _invalid_result('ROS clock rolled back during goal settle')
        elif (
            sample.timestamp_ns - state.last_ros_ns
            > _MAX_SETTLE_SAMPLE_GAP_NS
        ):
            settled_since = sample.timestamp_ns
        else:
            settled_since = state.settled_since_ros_ns
        if settled_since is None:
            settled_since = sample.timestamp_ns
        success = sample.timestamp_ns - settled_since >= _SETTLE_TIME_NS
        next_state = _bound_state(
            context,
            settled_since_ros_ns=settled_since,
            last_ros_ns=sample.timestamp_ns,
            success=success,
        )
        return GoalSettleResult(next_state, True, distance, success)
    except (AttributeError, TypeError, ValueError, OverflowError) as error:
        return _invalid_result(str(error))


def _valid_expected_context(
    binding: object,
    task_id: object,
    session_id: object,
    goal_id: object,
    goal_xy_m: object,
) -> bool:
    """Validate the caller-owned immutable task and goal identity."""
    return (
        isinstance(binding, ScenarioSessionBinding)
        and _valid_identifier(task_id)
        and _valid_identifier(session_id)
        and _valid_identifier(goal_id)
        and type(goal_xy_m) is tuple
        and len(goal_xy_m) == 2
        and all(_finite_real(value) for value in goal_xy_m)
    )


def _valid_context_fields(
    binding: object,
    task_id: object,
    session_id: object,
    lifecycle_key: object,
    goal_id: object,
    goal_x_m: object,
    goal_y_m: object,
) -> bool:
    """Check copied sample/health context fields and their lifecycle join."""
    if not isinstance(binding, ScenarioSessionBinding):
        return False
    if not _valid_lifecycle_key(lifecycle_key):
        return False
    identity = binding.lifecycle_identity
    return (
        lifecycle_key == (
            identity.episode_generation,
            identity.reset_epoch,
            identity.runtime_generation,
        )
        and _valid_identifier(task_id)
        and _valid_identifier(session_id)
        and _valid_identifier(goal_id)
        and _finite_real(goal_x_m)
        and _finite_real(goal_y_m)
    )


def _same_context(
    sample: OracleGoalSample,
    health: LocalTrainingHealth,
    expected_binding: ScenarioSessionBinding,
    expected_task_id: str,
    expected_session_id: str,
    expected_goal_id: str,
    expected_goal_xy_m: tuple[float, float],
) -> bool:
    """Join expected, oracle, and health context without mutable aliases."""
    expected_lifecycle = expected_binding.lifecycle_identity
    lifecycle_key = (
        expected_lifecycle.episode_generation,
        expected_lifecycle.reset_epoch,
        expected_lifecycle.runtime_generation,
    )
    expected_x, expected_y = (float(value) for value in expected_goal_xy_m)
    return (
        sample.scenario_session_binding == expected_binding
        and health.scenario_session_binding == expected_binding
        and sample.task_id == expected_task_id == health.task_id
        and sample.session_id == expected_session_id == health.session_id
        and sample.lifecycle_key == lifecycle_key == health.lifecycle_key
        and health.receipt_session_id == expected_session_id
        and health.receipt_lifecycle_key == lifecycle_key
        and sample.goal_id == expected_goal_id == health.goal_id
        and float(sample.goal_x_m) == expected_x == float(health.goal_x_m)
        and float(sample.goal_y_m) == expected_y == float(health.goal_y_m)
    )


def _valid_state(state: GoalSettleState) -> bool:
    """Reject forged or malformed state before it can carry settle time."""
    try:
        if type(state.success) is not bool:
            return False
        if state.lifecycle_key is not None and not _valid_lifecycle_key(
            state.lifecycle_key
        ):
            return False
        for value in (state.settled_since_ros_ns, state.last_ros_ns):
            if value is not None and (type(value) is not int or value < 0):
                return False
        if (
            state.settled_since_ros_ns is not None
            and state.last_ros_ns is not None
            and state.last_ros_ns < state.settled_since_ros_ns
        ):
            return False
        if state.scenario_session_binding is None:
            return (
                state.lifecycle_key is None
                and state.settled_since_ros_ns is None
                and state.last_ros_ns is None
                and not state.success
                and all(value is None for value in (
                    state.task_id, state.session_id, state.goal_id,
                    state.goal_xy_m,
                ))
            )
        if not isinstance(
            state.scenario_session_binding, ScenarioSessionBinding
        ):
            return False
        if not all(_valid_identifier(value) for value in (
            state.task_id, state.session_id, state.goal_id,
        )):
            return False
        if (
            type(state.goal_xy_m) is not tuple
            or len(state.goal_xy_m) != 2
            or not all(_finite_real(value) for value in state.goal_xy_m)
        ):
            return False
        identity = state.scenario_session_binding.lifecycle_identity
        expected_key = (
            identity.episode_generation,
            identity.reset_epoch,
            identity.runtime_generation,
        )
        return state.lifecycle_key == expected_key
    except (AttributeError, TypeError, ValueError, OverflowError):
        return False


def _goal_geometry_changed_within_identity(
    state: GoalSettleState,
    context: tuple[object, ...],
) -> bool:
    """Reject coordinate mutation under an unchanged goal identity."""
    if state.context_values is None:
        return False
    old_values = state.context_values
    old_binding, old_task, old_session = old_values[:3]
    old_lifecycle, old_goal, old_x, old_y = old_values[3:]
    binding, task, session, lifecycle, goal, goal_x, goal_y = context
    same_identity = (
        old_binding == binding
        and old_task == task
        and old_session == session
        and old_lifecycle == lifecycle
        and old_goal == goal
    )
    return same_identity and (old_x, old_y) != (goal_x, goal_y)


def _valid_lifecycle_key(value: object) -> bool:
    """Check the copied three-counter lifecycle identity representation."""
    return (
        type(value) is tuple
        and len(value) == 3
        and all(type(part) is int and part >= 0 for part in value)
    )


def _valid_identifier(value: object) -> bool:
    """Require a non-empty, trimmed scalar identifier."""
    return (
        type(value) is str
        and bool(value)
        and value == value.strip()
    )


def _finite_real(value: object) -> bool:
    """Return whether a non-bool numeric scalar is finite."""
    return (
        not isinstance(value, bool)
        and isinstance(value, Real)
        and isfinite(float(value))
    )


def _context_values(
    binding: ScenarioSessionBinding,
    task_id: str,
    session_id: str,
    goal_id: str,
    goal_xy_m: tuple[float, float],
) -> tuple[object, ...]:
    """Return the immutable key stored beside the settle clock."""
    return (
        binding,
        task_id,
        session_id,
        binding.lifecycle_identity,
        goal_id,
        float(goal_xy_m[0]),
        float(goal_xy_m[1]),
    )


def _bound_state(
    context: tuple[object, ...],
    *,
    settled_since_ros_ns: int | None = None,
    last_ros_ns: int | None = None,
    success: bool = False,
) -> GoalSettleState:
    """Create a state whose settle clock belongs to the supplied context."""
    binding, task_id, session_id, lifecycle, goal_id, goal_x, goal_y = context
    assert isinstance(binding, ScenarioSessionBinding)
    return GoalSettleState(
        lifecycle_key=(
            lifecycle.episode_generation,
            lifecycle.reset_epoch,
            lifecycle.runtime_generation,
        ),
        settled_since_ros_ns=settled_since_ros_ns,
        last_ros_ns=last_ros_ns,
        success=success,
        scenario_session_binding=binding,
        task_id=task_id,
        session_id=session_id,
        goal_id=goal_id,
        goal_xy_m=(goal_x, goal_y),
    )


def _invalid_result(reason: str) -> GoalSettleResult:
    """Clear settle state for every malformed or unhealthy evaluation."""
    return GoalSettleResult(GoalSettleState(), False, None, False, reason)


__all__ = (
    'GoalSettleResult',
    'GoalSettleState',
    'LocalTrainingHealth',
    'OracleGoalSample',
    'evaluate_local_training_goal',
)
