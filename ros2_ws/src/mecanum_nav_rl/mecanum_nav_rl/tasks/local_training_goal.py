"""LOCAL_TRAINING goal health and continuous true-state settle contract."""
from __future__ import annotations
from dataclasses import dataclass
from math import hypot, isfinite
from numbers import Real

@dataclass(frozen=True, slots=True)

class LocalTrainingHealth:
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
    oracle_timestamp_ns: int
    oracle_twist_timestamp_ns: int
    scan_timestamp_ns: int
    noisy_odometry_timestamp_ns: int
    cutoff_ros_ns: int
    evaluation_ros_now_ns: int
    oracle_received_steady_ns: int
    evaluation_steady_now_ns: int
    scan_ros_age_ns: int
    scan_steady_age_ns: int
    noisy_odom_ros_age_ns: int
    noisy_odom_steady_age_ns: int
    oracle_ros_age_ns: int
    oracle_steady_age_ns: int
    lifecycle_ros_age_ns: int
    lifecycle_steady_age_ns: int
    receipt_ros_age_ns: int
    receipt_steady_age_ns: int

    def healthy(self) -> bool:
        booleans = (self.simulator_valid, self.clock_valid,
            self.reset_complete, self.scenario_identity_valid, self.world_identity_valid, self.session_identity_valid, self.lifecycle_valid, self.barrier_valid, self.safety_ready, not self.safety_fault, not self.estop_active, not self.reset_pending, self.scan_valid, self.noisy_odometry_valid, self.reference_valid, self.measured_twist_valid, self.oracle_pose_valid, self.oracle_twist_valid, self.contact_source_healthy, self.receipt_valid, self.context_matches)
        ages = ((self.scan_ros_age_ns, self.scan_steady_age_ns, 500000000),
            (self.noisy_odom_ros_age_ns, self.noisy_odom_steady_age_ns,
            250000000), (self.oracle_ros_age_ns, self.oracle_steady_age_ns, 250000000), (self.lifecycle_ros_age_ns, self.lifecycle_steady_age_ns, 500000000), (self.receipt_ros_age_ns, self.receipt_steady_age_ns, 500000000))
        timestamps = (self.oracle_timestamp_ns, self.oracle_twist_timestamp_ns,
            self.scan_timestamp_ns, self.noisy_odometry_timestamp_ns, self.cutoff_ros_ns, self.evaluation_ros_now_ns, self.oracle_received_steady_ns, self.evaluation_steady_now_ns)
        return all((value is True for value in booleans)) and all((type(x) is int and 0 <= x <= limit for a, b, limit in ages for x in (a, b))) and all((type(x) is int and x >= 0 for x in timestamps)) and (self.oracle_timestamp_ns == self.cutoff_ros_ns) and (self.oracle_twist_timestamp_ns == self.cutoff_ros_ns) and (self.scan_timestamp_ns == self.cutoff_ros_ns) and (self.noisy_odometry_timestamp_ns == self.cutoff_ros_ns) and (self.cutoff_ros_ns <= self.evaluation_ros_now_ns) and (self.oracle_received_steady_ns <= self.evaluation_steady_now_ns)

@dataclass(frozen=True, slots=True)

class OracleGoalSample:
    timestamp_ns: int
    received_steady_ns: int
    lifecycle_key: tuple[int, int, int]
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
    lifecycle_key: tuple[int, int, int] | None = None
    settled_since_ros_ns: int | None = None
    last_ros_ns: int | None = None
    success: bool = False

@dataclass(frozen=True, slots=True)

class GoalSettleResult:
    state: GoalSettleState
    healthy: bool
    distance_m: float | None
    success: bool
    reason: str | None = None

def evaluate_local_training_goal(sample: OracleGoalSample,
    state: GoalSettleState, *, settle_time_ns: int=1000000000) -> GoalSettleResult:
    """Require full local-training health and one uninterrupted ROS-second settle."""
    if not isinstance(sample, OracleGoalSample) or not isinstance(state,
        GoalSettleState):
        return GoalSettleResult(GoalSettleState(), False, None, False,
            'invalid typed input')
    try:
        if type(sample.lifecycle_key) is not tuple or len(sample.lifecycle_key) != 3:
            raise ValueError('lifecycle_key must contain generation, epoch and runtime generation')
        if any((type(value) is not int or value < 0 for value in sample.lifecycle_key)):
            raise ValueError('lifecycle_key values must be non-negative integers')
        if type(settle_time_ns) is not int or settle_time_ns <= 0:
            raise ValueError('settle_time_ns must be positive')
        if not sample.health.healthy():
            return GoalSettleResult(GoalSettleState(sample.lifecycle_key),
                False, None, False, 'required LOCAL_TRAINING health is invalid')
        if sample.timestamp_ns != sample.health.oracle_timestamp_ns or sample.received_steady_ns != sample.health.oracle_received_steady_ns:
            raise ValueError('oracle sample timestamp/receive identity differs from health context')
        values = (sample.goal_x_m, sample.goal_y_m, sample.pose_x_m,
            sample.pose_y_m, sample.body_vx_mps, sample.body_vy_mps, sample.body_wz_radps)
        if any((isinstance(x, bool) or not isinstance(x,
            Real) or (not isfinite(float(x))) for x in values)):
            raise ValueError('oracle state contains non-finite values')
        distance = hypot(float(sample.goal_x_m) - float(sample.pose_x_m),
            float(sample.goal_y_m) - float(sample.pose_y_m))
        speed = hypot(float(sample.body_vx_mps), float(sample.body_vy_mps))
        settled = distance <= 0.15 and speed <= 0.03 and (abs(float(sample.body_wz_radps)) <= 0.05)
        if not settled:
            return GoalSettleResult(GoalSettleState(sample.lifecycle_key,
                last_ros_ns=sample.timestamp_ns), True, distance, False)
        if state.lifecycle_key != sample.lifecycle_key or state.last_ros_ns is None:
            since = sample.timestamp_ns
        elif sample.timestamp_ns <= state.last_ros_ns:
            return GoalSettleResult(GoalSettleState(sample.lifecycle_key),
                False, distance, False, 'ROS clock did not advance monotonically')
        elif sample.timestamp_ns - state.last_ros_ns > 250000000:
            since = sample.timestamp_ns
        else:
            since = state.settled_since_ros_ns
        if since is None:
            since = sample.timestamp_ns
        success = sample.timestamp_ns - since >= settle_time_ns
        return GoalSettleResult(GoalSettleState(sample.lifecycle_key, since,
            sample.timestamp_ns, success), True, distance, success)
    except (TypeError, ValueError, OverflowError) as error:
        return GoalSettleResult(GoalSettleState(sample.lifecycle_key), False,
            None, False, str(error))
__all__ = ('GoalSettleResult', 'GoalSettleState', 'LocalTrainingHealth',
    'OracleGoalSample', 'evaluate_local_training_goal')
