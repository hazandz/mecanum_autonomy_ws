"""Nối observation, reward, terminal và history trong một giao dịch B1."""
from __future__ import annotations

from dataclasses import dataclass, replace

from mecanum_nav_rl.core.episode_lifecycle import (
    CommittedRewardBaseline,
    EpisodeLifecycle,
    EpisodeLifecycleResult,
    EpisodeLifecycleState,
    EpisodeOperationStatus,
    GoalProgressInput,
    LifecycleStateError,
    StepCommitCandidate,
)
from mecanum_nav_rl.core.goal_facts import TaskOracleResult, TaskOracleStatus
from mecanum_nav_rl.core.issued_command_cutoff import (
    CutoffSelection,
    CutoffStatus,
    IssuedCommandReceiptView,
    PolicyActionIssuance,
    ReceiptSource,
)
from mecanum_nav_rl.core.lifecycle_types import (
    CORE_TRANSACTION_LOCK,
    CommittedGoalSettleState,
    CommittedTaskHistorySample,
    ExactObservationProvenance,
    TransitionIdentity,
)
from mecanum_nav_rl.observations.local_training_reference import (
    LocalReferenceResult,
    LocalTrainingGoal,
    NoisyOdometryContext,
    build_local_training_reference,
)
from mecanum_nav_rl.observations.measured_twist import (
    MeasuredTwistFeatureResult,
    MeasuredTwistFeatureStatus,
)
from mecanum_nav_rl.observations.previous_command import (
    PreviousNormalizedCommand,
)
from mecanum_nav_rl.observations.v3_observation_assembler import (
    assemble_observation,
)
from mecanum_nav_rl.observations.v3_snapshot_types import (
    ActiveLifecycleConfigContext,
    LIFECYCLE_BARRIER_CONTRACT_ID,
)
from mecanum_nav_rl.observations.v3_snapshot_validation import (
    ValidatedObservationInputs,
)
from mecanum_nav_rl.rewards.manager import (
    RewardManager,
    RewardResult,
    TransitionRewardInput,
)
from mecanum_nav_rl.simulation.contact_latch import ContactLatch
from mecanum_nav_rl.tasks.local_training_goal import (
    GoalSettleResult,
    GoalSettleState,
    OracleGoalSample,
    evaluate_local_training_goal,
)
from mecanum_nav_rl.termination.manager import (
    EpisodeTaskSample,
    TerminationInput,
    TerminationManager,
    TerminationReason,
    TerminationResult,
    ValidArea,
)

import numpy as np


@dataclass(frozen=True, slots=True)
class RLTransitionContext:
    """Giữ facts bất biến được kiểm tra cho một transition B1."""

    transition_identity: TransitionIdentity
    lifecycle_candidate: StepCommitCandidate
    observation: np.ndarray
    reward: RewardResult
    termination: TerminationResult
    info: tuple[tuple[str, str | int | float | bool], ...]
    issued_receipt_id: str
    cutoff_selection: CutoffSelection
    command_history: tuple[float, float, float]
    contact_transition_id: str
    contact_latch: ContactLatch
    policy_issuance: PolicyActionIssuance
    policy_issuance_receipt: IssuedCommandReceiptView
    clearance_m: float
    clearance_observation_provenance: ExactObservationProvenance
    observation_inputs: ValidatedObservationInputs
    local_reference_result: LocalReferenceResult
    noisy_odometry_context: NoisyOdometryContext
    measured_twist_result: MeasuredTwistFeatureResult
    goal_sample: OracleGoalSample
    expected_task_id: str
    expected_session_id: str
    expected_goal_id: str
    expected_goal_xy_m: tuple[float, float]
    valid_area: ValidArea | None
    goal_settle_result: GoalSettleResult | None = None
    task_history_sample: CommittedTaskHistorySample | None = None


@dataclass(frozen=True, slots=True)
class CommittedRLTransition:
    """Lưu kết quả được publish bởi một transition commit thành công."""

    transition_identity: TransitionIdentity
    observation: np.ndarray
    reward: RewardResult
    termination: TerminationResult
    info: tuple[tuple[str, str | int | float | bool], ...]
    issued_receipt_id: str
    command_history: tuple[float, float, float]
    lifecycle_result: EpisodeLifecycleResult
    goal_settle_result: GoalSettleResult


@dataclass(frozen=True, slots=True)
class TransitionCommitResult:
    """Báo transition commit thành công hay bị từ chối."""

    committed: bool
    transition: CommittedRLTransition | None
    reason: str | None = None


class RLTransitionCommitter:
    """Prepare every B1 value before delegating the single lifecycle commit."""

    def __init__(self, lifecycle: EpisodeLifecycle) -> None:
        """Gắn committer vào lifecycle transaction owner."""
        if not isinstance(lifecycle, EpisodeLifecycle):
            raise TypeError('lifecycle must be EpisodeLifecycle')
        self._lifecycle = lifecycle
        self._lock = CORE_TRANSACTION_LOCK
        self._committed: tuple[CommittedRLTransition, ...] = ()

    @property
    def committed(self) -> tuple[CommittedRLTransition, ...]:
        """Trả về lịch sử transition đã commit, dưới dạng tuple bất biến."""
        with CORE_TRANSACTION_LOCK:
            return self._committed

    def commit(
        self, context: RLTransitionContext
    ) -> TransitionCommitResult:
        """Commit transition hoặc từ chối mà không đổi committed state."""
        with self._lock:
            if (
                isinstance(context, RLTransitionContext)
                and any(
                    old.transition_identity == context.transition_identity
                    for old in self._committed
                )
            ):
                return TransitionCommitResult(
                    False, None, 'transition was already committed'
                )
            try:
                if not isinstance(context, RLTransitionContext):
                    raise TypeError('context must be RLTransitionContext')
                (
                    baseline,
                    previous_command,
                    goal_progress,
                    goal_settle_state,
                    task_history,
                    reset_timestamp_ns,
                ) = (
                    self._lifecycle._prepare_step_reward_facts(
                        context.lifecycle_candidate
                    )
                )
                prepared = self._prepare(
                    context,
                    baseline,
                    previous_command,
                    goal_progress,
                    goal_settle_state,
                    task_history,
                    reset_timestamp_ns,
                )
            except (
                TypeError,
                ValueError,
                OverflowError,
                LifecycleStateError,
            ) as error:
                return TransitionCommitResult(False, None, str(error))
            if not prepared.contact_latch.can_commit_transition(
                prepared.contact_transition_id,
                prepared.transition_identity.identity,
            ):
                return TransitionCommitResult(
                    False,
                    None,
                    'contact pulse cannot be consumed for this transition',
                )
            try:
                lifecycle_result = self._lifecycle.commit_step(
                    context.lifecycle_candidate,
                    goal_settle_state=_committed_goal_state(
                        prepared.goal_settle_result
                    ),
                    task_history_sample=prepared.task_history_sample,
                )
            except LifecycleStateError as error:
                return TransitionCommitResult(False, None, str(error))
            if (
                lifecycle_result.status
                is not EpisodeOperationStatus.STEP_COMMITTED
            ):
                return TransitionCommitResult(
                    False,
                    None,
                    lifecycle_result.reason or 'lifecycle rejected commit',
                )
            contact_result = prepared.contact_latch.commit_transition(
                prepared.contact_transition_id,
                prepared.transition_identity.identity,
            )
            if not contact_result.accepted:
                raise RuntimeError(
                    'contact state changed during atomic commit'
                )
            committed = CommittedRLTransition(
                prepared.transition_identity,
                prepared.observation,
                prepared.reward,
                prepared.termination,
                prepared.info,
                prepared.issued_receipt_id,
                prepared.command_history,
                lifecycle_result,
                prepared.goal_settle_result,
            )
            self._committed = (*self._committed, committed)
            return TransitionCommitResult(True, committed)

    @staticmethod
    def _prepare(
        context: RLTransitionContext,
        reward_baseline: CommittedRewardBaseline,
        previous_command: PreviousNormalizedCommand,
        goal_progress: GoalProgressInput,
        committed_goal_state: CommittedGoalSettleState | None,
        committed_task_history: tuple[CommittedTaskHistorySample, ...],
        reset_timestamp_ns: int,
    ) -> RLTransitionContext:
        if not isinstance(context, RLTransitionContext):
            raise TypeError('context must be RLTransitionContext')
        if not isinstance(context.transition_identity, TransitionIdentity):
            raise TypeError('transition identity is required')
        if not isinstance(context.lifecycle_candidate, StepCommitCandidate):
            raise TypeError('lifecycle candidate is required')
        if (
            context.lifecycle_candidate.transition_identity
            != context.transition_identity
        ):
            raise ValueError(
                'lifecycle candidate identity differs from transition'
            )
        if not isinstance(reward_baseline, CommittedRewardBaseline):
            raise TypeError(
                'reward baseline must come from committed lifecycle state'
            )
        if not isinstance(previous_command, PreviousNormalizedCommand):
            raise TypeError(
                'previous command must come from committed lifecycle state'
            )
        if not isinstance(goal_progress, GoalProgressInput):
            raise TypeError('current goal facts must be admitted by lifecycle')
        observation = context.observation
        if (
            type(observation) is not np.ndarray
            or observation.shape != (81,)
            or observation.dtype != np.float32
        ):
            raise ValueError('observation must be float32[81]')
        if not bool(np.isfinite(observation).all()):
            raise ValueError('observation must be finite')
        if type(context.reward) is not RewardResult:
            raise TypeError('caller reward assertion must be a RewardResult')
        if not isinstance(context.termination, TerminationResult):
            raise TypeError('caller termination assertion must be typed')
        receipt = context.lifecycle_candidate.command_receipt
        if context.issued_receipt_id != receipt.receipt_id:
            raise ValueError(
                'transition receipt does not match lifecycle candidate'
            )
        selection = context.cutoff_selection
        if (
            not isinstance(selection, CutoffSelection)
            or selection.status is not CutoffStatus.READY
        ):
            raise ValueError(
                'transition requires a ready receipt cutoff selection'
            )
        selected = selection.receipt
        binding = selection.stream_binding
        if (
            selected is None
            or selection.normalized_command is None
            or binding is None
            or selection.cutoff_ros_ns is None
        ):
            raise ValueError('ready cutoff selection is incomplete')
        provenance = context.lifecycle_candidate.observation_provenance
        if (
            selection.cutoff_ros_ns != provenance.observation_timestamp_ns
            or binding.lifecycle != context.transition_identity.identity
            or selected.lifecycle != context.transition_identity.identity
            or selected.receipt_key != receipt.receipt_id
        ):
            raise ValueError(
                'selected receipt does not bind this observation cutoff'
            )
        issuance = context.policy_issuance
        issuance_receipt = context.policy_issuance_receipt
        if (
            not isinstance(issuance, PolicyActionIssuance)
            or type(issuance_receipt) is not IssuedCommandReceiptView
        ):
            raise TypeError('transition requires POLICY issuance proof facts')
        if (
            issuance.lifecycle != context.transition_identity.identity
            or issuance.step_index != context.transition_identity.step_index
            or issuance.transition_id
            != context.transition_identity.transition_id
            or issuance_receipt.source is not ReceiptSource.POLICY
            or issuance_receipt.source_instance_id
            != issuance.source_instance_id
            or issuance_receipt.source_sequence != issuance.source_sequence
            or issuance_receipt.step_index != issuance.step_index
            or issuance_receipt.transition_id != issuance.transition_id
            or issuance_receipt.lifecycle != issuance.lifecycle
        ):
            raise ValueError('POLICY issuance does not bind this transition')
        if (
            issuance_receipt.final_publisher_instance_id
            != binding.final_publisher_instance_id
            or issuance_receipt.session_id != binding.session_id
            or issuance_receipt.ingress_config_hash != binding.config_hash
            or issuance_receipt.frame_id != binding.frame_id
            or issuance_receipt.publish_stamp_ns > selection.cutoff_ros_ns
            or issuance_receipt.final_publish_sequence
            > selected.final_publish_sequence
        ):
            raise ValueError(
                'POLICY issuance is outside the selected receipt stream'
            )
        ros_age = (
            selection.evaluation_ros_now_ns
            - issuance_receipt.publish_stamp_ns
        )
        steady_age = (
            selection.evaluation_steady_now_ns
            - issuance_receipt.received_steady_ns
        )
        if (
            ros_age < 0
            or ros_age > 500000000
            or steady_age < 0
            or steady_age > 500000000
            or not issuance_receipt.admission_valid
        ):
            raise ValueError('POLICY issuance receipt is stale or invalid')
        if (
            issuance_receipt.source_instance_id != issuance.source_instance_id
            or issuance_receipt.source_sequence != issuance.source_sequence
        ):
            raise ValueError(
                'POLICY issuance source key differs from its receipt'
            )
        if selected.source not in (
            ReceiptSource.POLICY,
            ReceiptSource.SAFE_STOP,
        ):
            raise ValueError(
                'selected command source is invalid for LOCAL_TRAINING'
            )
        if selected.source is ReceiptSource.SAFE_STOP and any(
            value != 0.0 for value in selected.final_command
        ):
            raise ValueError('selected SAFE_STOP must carry actual zero')
        if selected.source is ReceiptSource.POLICY and (
            selected.source_instance_id != issuance.source_instance_id
            or selected.source_sequence != issuance.source_sequence
            or selected.step_index != issuance.step_index
            or selected.transition_id != issuance.transition_id
        ):
            raise ValueError(
                'selected POLICY receipt differs from issuance proof'
            )
        selected_command = tuple(
            float(value) for value in np.asarray(
                selection.normalized_command, dtype=np.float32
            )
        )
        copied = _validate_v3_observation(
            context, provenance, binding.config_hash, selected_command
        )
        prior_command = tuple(
            float(value) for value in np.asarray((
                previous_command.vx, previous_command.vy, previous_command.wz
            ), dtype=np.float32)
        )
        if (
            type(context.command_history) is not tuple
            or len(context.command_history) != 3
        ):
            raise ValueError('command history must be a three-value tuple')
        supplied_history = tuple(
            float(value) for value in context.command_history
        )
        if any(
            not np.isfinite(value) or value < -1.0 or value > 1.0
            for value in supplied_history
        ):
            raise ValueError(
                'command history must be normalized final-issued values'
            )
        history_v3 = tuple(
            float(value)
            for value in np.asarray(supplied_history, dtype=np.float32)
        )
        receipt_command_v3 = tuple(
            float(value)
            for value in np.asarray(
                (
                    receipt.final_issued_command.vx,
                    receipt.final_issued_command.vy,
                    receipt.final_issued_command.wz,
                ),
                dtype=np.float32,
            )
        )
        if (
            history_v3 != selected_command
            or receipt_command_v3 != selected_command
        ):
            raise ValueError(
                'command history must match the selected final-issued command'
            )
        if (
            type(context.clearance_observation_provenance)
            is not ExactObservationProvenance
            or context.clearance_observation_provenance != provenance
            or context.clearance_observation_provenance.scan_timestamp_ns
            != provenance.scan_timestamp_ns
        ):
            raise ValueError('clearance must join the selected scan snapshot')
        if (
            type(context.contact_transition_id) is not str
            or context.contact_transition_id
            != context.transition_identity.transition_id
        ):
            raise ValueError(
                'contact consumption must use this transition identity'
            )
        if not isinstance(context.contact_latch, ContactLatch):
            raise TypeError('transition commit requires ContactLatch state')
        if type(committed_task_history) is not tuple:
            raise TypeError(
                'committed task history must be an immutable tuple'
            )
        if type(context.info) is not tuple or any(
            type(item) is not tuple or len(item) != 2
            for item in context.info
        ):
            raise TypeError(
                'info must be an immutable tuple of key/value pairs'
            )
        for item in context.info:
            value = item[1]
            if type(value) not in (str, int, float, bool):
                raise TypeError('info values must be immutable scalars')
            if type(value) is float and not np.isfinite(value):
                raise ValueError('info floats must be finite')
        keys = tuple((pair[0] for pair in context.info))
        if (
            any(type(key) is not str or not key for key in keys)
            or len(set(keys)) != len(keys)
        ):
            raise ValueError('info keys must be unique non-empty strings')
        if (
            goal_progress.previous_observation_timestamp_ns
            != reward_baseline.previous_committed_sim_time_ns
            or goal_progress.previous_observation_timestamp_ns
            != reward_baseline.observation_provenance.observation_timestamp_ns
            or goal_progress.current_observation_timestamp_ns
            != provenance.observation_timestamp_ns
        ):
            raise ValueError(
                'reward timestamps do not join committed and current cutoffs'
            )
        dt_ns = (
            provenance.observation_timestamp_ns
            - reward_baseline.previous_committed_sim_time_ns
        )
        if dt_ns <= 0:
            raise ValueError('simulation cutoff time must strictly increase')
        if type(context.clearance_m) not in (int, float) or isinstance(
            context.clearance_m, bool
        ) or not np.isfinite(context.clearance_m) or context.clearance_m < 0:
            raise ValueError('clearance must be a finite non-negative scalar')
        goal_sample = context.goal_sample
        if type(goal_sample) is not OracleGoalSample:
            raise TypeError('transition requires a typed oracle goal sample')
        if (
            type(context.expected_task_id) is not str
            or not context.expected_task_id
            or type(context.expected_session_id) is not str
            or not context.expected_session_id
            or type(context.expected_goal_id) is not str
            or not context.expected_goal_id
            or type(context.expected_goal_xy_m) is not tuple
            or len(context.expected_goal_xy_m) != 2
        ):
            raise ValueError(
                'expected task/session/goal identity is incomplete'
            )
        if context.expected_session_id != binding.session_id:
            raise ValueError(
                'task session differs from the selected receipt stream'
            )
        if committed_goal_state is None:
            previous_settle_state = GoalSettleState()
        else:
            if (
                type(committed_goal_state) is not CommittedGoalSettleState
                or committed_goal_state.lifecycle
                != context.transition_identity.identity
            ):
                raise ValueError(
                    'committed goal settle state has another lifecycle'
                )
            previous_settle_state = GoalSettleState(
                lifecycle_key=(
                    committed_goal_state.lifecycle.episode_generation,
                    committed_goal_state.lifecycle.reset_epoch,
                    committed_goal_state.lifecycle.runtime_generation,
                ),
                settled_since_ros_ns=committed_goal_state.settled_since_ros_ns,
                last_ros_ns=committed_goal_state.last_ros_ns,
                success=committed_goal_state.success,
                scenario_session_binding=(
                    goal_progress.scenario_session_binding
                ),
                task_id=committed_goal_state.task_id,
                session_id=committed_goal_state.session_id,
                goal_id=committed_goal_state.goal_id,
                goal_xy_m=committed_goal_state.goal_xy_m,
            )
        goal_health = evaluate_local_training_goal(
            goal_sample,
            previous_settle_state,
            expected_scenario_session_binding=(
                goal_progress.scenario_session_binding
            ),
            expected_task_id=context.expected_task_id,
            expected_session_id=context.expected_session_id,
            expected_goal_id=context.expected_goal_id,
            expected_goal_xy_m=context.expected_goal_xy_m,
        )
        if not goal_health.healthy:
            raise ValueError(
                goal_health.reason
                or 'current LOCAL_TRAINING health is invalid'
            )
        if (
            goal_sample.health.contact_source_healthy is not True
            or
            goal_sample.timestamp_ns != provenance.observation_timestamp_ns
            or goal_sample.health.cutoff_ros_ns != selection.cutoff_ros_ns
            or goal_sample.health.evaluation_ros_now_ns
            != selection.evaluation_ros_now_ns
            or goal_sample.health.evaluation_steady_now_ns
            != selection.evaluation_steady_now_ns
            or goal_sample.health.scan_timestamp_ns
            != provenance.scan_timestamp_ns
            or goal_sample.health.noisy_odometry_timestamp_ns
            != provenance.odometry_timestamp_ns
            or goal_sample.health.receipt_timestamp_ns
            != selected.publish_stamp_ns
            or goal_sample.health.receipt_received_steady_ns
            != selected.received_steady_ns
            or goal_sample.health.receipt_session_id != binding.session_id
            or goal_sample.health.receipt_lifecycle_key
            != _lifecycle_key(context.transition_identity.identity)
        ):
            raise ValueError(
                'goal health does not bind this receipt and sensor cutoff'
            )
        current_goal_fact = context.lifecycle_candidate.goal_result.fact
        if (
            current_goal_fact is None
            or current_goal_fact.provenance.scenario_session_binding
            != goal_progress.scenario_session_binding
            or current_goal_fact.provenance.source_timestamp_ns
            != goal_sample.timestamp_ns
            or goal_health.distance_m != goal_progress.current_goal_distance_m
        ):
            raise ValueError(
                'oracle sample and lifecycle goal fact do not join'
            )
        task_key = (
            context.transition_identity.identity,
            context.expected_task_id,
            context.expected_session_id,
            context.expected_goal_id,
            context.expected_goal_xy_m,
        )
        prior_samples: list[EpisodeTaskSample] = []
        for committed_sample in committed_task_history:
            if type(committed_sample) is not CommittedTaskHistorySample:
                raise TypeError(
                    'committed task history contains an invalid sample'
                )
            sample_key = (
                committed_sample.lifecycle,
                committed_sample.task_id,
                committed_sample.session_id,
                committed_sample.goal_id,
                committed_sample.goal_xy_m,
            )
            if sample_key == task_key:
                prior_samples.append(
                    EpisodeTaskSample(
                        committed_sample.ros_time_ns,
                        committed_sample.x_m,
                        committed_sample.y_m,
                        committed_sample.true_goal_distance_m,
                        committed_sample.required_health_valid,
                    )
                )
        current_task_sample = EpisodeTaskSample(
            goal_sample.timestamp_ns,
            goal_sample.pose_x_m,
            goal_sample.pose_y_m,
            goal_progress.current_goal_distance_m,
            goal_health.healthy,
        )
        if type(reset_timestamp_ns) is not int or reset_timestamp_ns < 0:
            raise ValueError('committed reset timestamp is invalid')
        elapsed_ros_ns = (
            provenance.observation_timestamp_ns - reset_timestamp_ns
        )
        if elapsed_ros_ns < 0:
            raise ValueError('episode ROS time precedes committed reset')
        contact_state = context.contact_latch.state
        if contact_state.source_healthy is False:
            raise ValueError(
                'contact source health is invalid for this transition'
            )
        if context.valid_area is not None and (
            not isinstance(context.valid_area, ValidArea)
            or context.valid_area.scenario_session_binding
            != goal_progress.scenario_session_binding
            or context.valid_area.task_id != context.expected_task_id
            or context.valid_area.session_id != context.expected_session_id
        ):
            raise ValueError(
                'valid area is not bound to this task and session'
            )
        collision_active = (
            contact_state.contact_active
            or contact_state.collision_pulse_pending
        )
        termination = TerminationManager().evaluate(
            TerminationInput(
                elapsed_ros_ns=elapsed_ros_ns,
                current_sample=current_task_sample,
                trajectory=tuple(prior_samples),
                collision=collision_active,
                goal_settled_success=goal_health.success,
                valid_area=context.valid_area,
            )
        )
        if context.termination != termination:
            raise ValueError(
                'caller termination assertion differs from current task facts'
            )
        expected_state = (
            EpisodeLifecycleState.TERMINATED if termination.terminated else
            EpisodeLifecycleState.TRUNCATED if termination.truncated else
            EpisodeLifecycleState.RUNNING
        )
        if context.lifecycle_candidate.committed_state is not expected_state:
            raise ValueError(
                'lifecycle state does not match computed termination'
            )
        reason = termination.reason
        task_history_sample = CommittedTaskHistorySample(
            lifecycle=context.transition_identity.identity,
            task_id=context.expected_task_id,
            session_id=context.expected_session_id,
            goal_id=context.expected_goal_id,
            goal_xy_m=context.expected_goal_xy_m,
            ros_time_ns=goal_sample.timestamp_ns,
            x_m=goal_sample.pose_x_m,
            y_m=goal_sample.pose_y_m,
            true_goal_distance_m=goal_progress.current_goal_distance_m,
            required_health_valid=goal_health.healthy,
        )
        canonical_reward = RewardManager().compute(
            TransitionRewardInput(
                previous_true_goal_distance_m=(
                    goal_progress.previous_goal_distance_m
                ),
                current_true_goal_distance_m=(
                    goal_progress.current_goal_distance_m
                ),
                clearance_m=float(context.clearance_m),
                dt_sim_s=dt_ns / 1_000_000_000.0,
                final_issued_normalized=selected_command,
                previous_final_issued_normalized=prior_command,
                goal=reason is TerminationReason.GOAL,
                collision=reason is TerminationReason.COLLISION,
                stuck=reason is TerminationReason.STUCK,
            )
        )
        if context.reward != canonical_reward:
            raise ValueError(
                'caller reward assertion differs from canonical reward'
            )
        return replace(
            context,
            observation=copied,
            reward=canonical_reward,
            termination=termination,
            command_history=selected_command,
            goal_settle_result=goal_health,
            task_history_sample=task_history_sample,
        )


def _lifecycle_key(identity):
    return (
        identity.episode_generation,
        identity.reset_epoch,
        identity.runtime_generation,
    )


def _committed_goal_state(result):
    if type(result) is not GoalSettleResult or not result.healthy:
        raise ValueError('only a healthy goal evaluation can be committed')
    state = result.state
    if (
        type(state) is not GoalSettleState
        or state.scenario_session_binding is None
    ):
        raise ValueError('goal evaluation has no bound task state')
    lifecycle_key = _lifecycle_key(
        state.scenario_session_binding.lifecycle_identity
    )
    if state.lifecycle_key != lifecycle_key:
        raise ValueError(
            'goal settle lifecycle differs from its scenario binding'
        )
    if type(state.goal_xy_m) is not tuple or len(state.goal_xy_m) != 2:
        raise ValueError('goal settle state has no bound goal coordinates')
    return CommittedGoalSettleState(
        lifecycle=state.scenario_session_binding.lifecycle_identity,
        task_id=state.task_id,
        session_id=state.session_id,
        goal_id=state.goal_id,
        goal_xy_m=state.goal_xy_m,
        settled_since_ros_ns=state.settled_since_ros_ns,
        last_ros_ns=state.last_ros_ns,
        success=state.success,
    )


def _validate_v3_observation(
    context, provenance, config_hash, selected_command
):
    inputs = context.observation_inputs
    if type(inputs) is not ValidatedObservationInputs:
        raise TypeError('transition requires validated Observation V3 inputs')
    identity = context.transition_identity.identity
    if type(context.goal_sample) is not OracleGoalSample:
        raise TypeError('transition requires a typed oracle goal sample')
    if (
        type(context.lifecycle_candidate.goal_result) is not TaskOracleResult
        or context.lifecycle_candidate.goal_result.status
        is not TaskOracleStatus.READY
        or context.lifecycle_candidate.goal_result.fact is None
    ):
        raise ValueError('transition requires an admitted oracle goal fact')
    common = (
        identity.episode_generation,
        identity.reset_epoch,
        identity.runtime_generation,
        config_hash,
    )
    if inputs.context != ActiveLifecycleConfigContext(
        LIFECYCLE_BARRIER_CONTRACT_ID, *common
    ):
        raise ValueError(
            'Observation V3 config/lifecycle differs from receipt stream'
        )
    assembly = assemble_observation(inputs)
    if not assembly.ready or assembly.vector is None:
        raise ValueError('Observation V3 snapshots are not valid together')
    lidar = inputs.lidar
    reference = inputs.local_reference
    twist = inputs.measured_twist
    receipt = inputs.receipt
    if any(snapshot.config_hash != config_hash for snapshot in (
        lidar, reference, twist, receipt
    )):
        raise ValueError(
            'Observation V3 snapshot config differs from receipt stream'
        )
    if any(value < 0.0 or value > 1.0 for value in lidar.sectors):
        raise ValueError('V3 LiDAR features must be normalized in [0, 1]')
    if not 0.0 <= reference.features[0] <= 1.0 or any(
        value < -1.0 or value > 1.0 for value in reference.features[1:]
    ):
        raise ValueError(
            'V3 LOCAL_TRAINING reference is outside normalized bounds'
        )
    if any(value < -1.0 or value > 1.0 for value in (
        *twist.components, *receipt.final_command
    )):
        raise ValueError('V3 twist and command features must be normalized')
    if tuple(receipt.final_command) != tuple(selected_command):
        raise ValueError('V3 command tail differs from the selected receipt')

    goal_fact = context.lifecycle_candidate.goal_result.fact
    binding = goal_fact.provenance.scenario_session_binding
    odometry = context.noisy_odometry_context
    local_result = context.local_reference_result
    twist_result = context.measured_twist_result
    if type(odometry) is not NoisyOdometryContext:
        raise TypeError(
            'transition requires the selected noisy odometry snapshot'
        )
    snapshot = odometry.snapshot
    if (
        odometry.lifecycle != identity
        or odometry.scenario_frame_id != binding.coordinate_reference_id
        or odometry.scenario_identity != binding.scenario_id
        or snapshot.timestamp_ns != provenance.odometry_timestamp_ns
        or snapshot.timestamp_ns != provenance.scan_timestamp_ns
    ):
        raise ValueError(
            'noisy odometry does not bind the selected sensor pair'
        )
    if (
        type(local_result) is not LocalReferenceResult
        or not local_result.ready
    ):
        raise ValueError(
            'transition requires a ready LOCAL_TASK_GOAL reference'
        )
    health = context.goal_sample.health
    expected_reference = build_local_training_reference(
        LocalTrainingGoal(
            context.expected_goal_xy_m[0],
            context.expected_goal_xy_m[1],
            binding.coordinate_reference_id,
            binding.scenario_id,
        ),
        odometry,
        evaluation_ros_now_ns=health.evaluation_ros_now_ns,
        evaluation_steady_now_ns=health.evaluation_steady_now_ns,
        scan_timestamp_ns=provenance.scan_timestamp_ns,
        scan_lifecycle=identity,
        scan_scenario_identity=binding.scenario_id,
    )
    if (
        not expected_reference.ready
        or local_result != expected_reference
        or reference.features
        != tuple(float(value) for value in local_result.features)
        or local_result.timestamp_ns != provenance.odometry_timestamp_ns
        or local_result.sequence != snapshot.sequence
        or local_result.lifecycle != identity
        or local_result.scenario_identity != binding.scenario_id
        or local_result.source != 'LOCAL_TASK_GOAL'
    ):
        raise ValueError(
            'LOCAL_TRAINING reference differs from selected noisy snapshot'
        )
    if (
        type(twist_result) is not MeasuredTwistFeatureResult
        or twist_result.status is not MeasuredTwistFeatureStatus.READY
        or twist_result.timestamp_ns != snapshot.timestamp_ns
        or twist_result.odometry_sequence != snapshot.sequence
        or tuple(float(value) for value in twist_result.features)
        != tuple(twist.components)
    ):
        raise ValueError(
            'measured twist does not come from selected odometry snapshot'
        )
    assembled = assembly.vector
    if not np.array_equal(assembled, context.observation):
        raise ValueError(
            'observation vector differs from validated V3 snapshots'
        )
    # Mảng dựa trên bytes không thể được caller bật write trở lại.
    copied = np.frombuffer(assembled.tobytes(), dtype=np.float32)
    if copied.shape != (81,) or not np.isfinite(copied).all():
        raise ValueError('assembled V3 observation is invalid')
    return copied


__all__ = (
    'CommittedRLTransition',
    'RLTransitionCommitter',
    'RLTransitionContext',
    'TransitionCommitResult',
)
