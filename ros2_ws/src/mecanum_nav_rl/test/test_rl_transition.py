"""Kiểm thử các giao dịch chuyển trạng thái RL thuần."""

import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from threading import Barrier, Event, Thread

from mecanum_nav_rl.config.models import MotionLimitsConfig, ObservationConfig
from mecanum_nav_rl.core.episode_lifecycle import (
    CommandReceiptSnapshot,
    EpisodeLifecycle,
    EpisodeLifecycleState,
    EpisodeOperationStatus,
    ResetCommitCandidate,
    ResetZeroReceipt,
    StepCommitCandidate,
)
from mecanum_nav_rl.core.goal_facts import (
    GoalFactJoinMode,
    GoalFactProvenance,
    GoalOracleFact,
    TaskOracleResult,
    TaskOracleStatus,
)
from mecanum_nav_rl.core.issued_command_cutoff import (
    IssuedCommandReceiptView,
    PolicyActionIssuance,
    ReceiptSource,
    ReceiptStreamBinding,
    select_final_issued_at_cutoff,
    select_reset_zero_at_cutoff,
)
from mecanum_nav_rl.core.lifecycle_types import (
    CORE_TRANSACTION_LOCK,
    EpisodeLifecycleIdentity,
    ExactObservationProvenance,
    TransitionIdentity,
)
from mecanum_nav_rl.core.rl_transition import (
    RLTransitionCommitter,
    RLTransitionContext,
)
from mecanum_nav_rl.core.scenario_session import ScenarioSessionBinding
from mecanum_nav_rl.observations.local_training_reference import (
    LocalTrainingGoal,
    NoisyOdometryContext,
    build_local_training_reference,
)
from mecanum_nav_rl.observations.measured_twist import (
    MeasuredTwistFeatureExtractor,
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
    FRAME_TF_CONTRACT_ID,
    FinalIssuedReceiptContext,
    LIDAR_CONTRACT_ID,
    LIDAR_FRAME,
    LIFECYCLE_BARRIER_CONTRACT_ID,
    LOCAL_REFERENCE_CONTRACT_ID,
    LidarSnapshot,
    LocalReferenceSnapshot,
    MEASURED_TWIST_CONTRACT_ID,
    MeasuredTwistSnapshot,
)
from mecanum_nav_rl.observations.v3_snapshot_validation import (
    validate_observation_inputs,
)
from mecanum_nav_rl.rewards.manager import (
    RewardManager,
    TransitionRewardInput,
)
from mecanum_nav_rl.simulation.contact_latch import ContactFact, ContactLatch
from mecanum_nav_rl.simulation.simulated_odometry import (
    SimulatedOdometryMeasurement, SimulatedOdometrySnapshot,
    SimulatedOdometryStatus,
)
from mecanum_nav_rl.tasks.local_training_goal import (
    GoalSettleState, LocalTrainingHealth, OracleGoalSample,
    evaluate_local_training_goal,
)
from mecanum_nav_rl.termination.manager import (
    EpisodeTaskSample,
    TerminationInput,
    TerminationManager,
    TerminationReason,
    TerminationResult,
)

import numpy as np

import pytest


def ready_lifecycle():
    """Tạo lifecycle đã reset và một candidate step hợp lệ."""
    identity = EpisodeLifecycleIdentity(1, 1, 1)
    binding = ScenarioSessionBinding(
        identity, 'scenario', '1', 'a' * 64,
        'world', 'b' * 64, 'local-frame'
    )
    lifecycle = EpisodeLifecycle()
    lifecycle.begin_reset(identity, binding)
    lifecycle.wait_for_initial_observation(identity)
    provenance = ExactObservationProvenance(
        identity, 1_000_000_000, 1_000_000_000, 1_000_000_000
    )
    reset_fact = GoalOracleFact(
        2.0, False,
        GoalFactProvenance(
            GoalFactJoinMode.RESET_OBSERVATION0, binding,
            provenance, 1_000_000_000, None
        )
    )
    reset_stream = ReceiptStreamBinding(
        89, 'reset-session', 'a' * 64, identity, 'base_link'
    )
    reset_zero = IssuedCommandReceiptView(
        999_999_999, 89, 1, ReceiptSource.SAFE_STOP, 8, 1, 0, '',
        identity, 'reset-session', 'a' * 64, (0, 0, 0),
        1_000_000_000, 'base_link', True
    )
    reset_boundary = IssuedCommandReceiptView(
        1_000_000_001, 89, 2, ReceiptSource.SAFE_STOP, 8, 2, 0, '',
        identity, 'reset-session', 'a' * 64, (0, 0, 0),
        1_000_000_001, 'base_link', True
    )
    reset_selection = select_reset_zero_at_cutoff(
        (reset_zero, reset_boundary),
        binding=reset_stream, cutoff_ros_ns=1_000_000_000,
        evaluation_ros_now_ns=1_000_000_001,
        evaluation_steady_now_ns=1_000_000_001, reset_barrier_ros_ns=0,
        physical_scales=(0.25, 0.2, 0.8)
    )
    lifecycle.commit_reset(
        ResetCommitCandidate(
            identity, provenance,
            TaskOracleResult(TaskOracleStatus.READY, reset_fact),
            PreviousNormalizedCommand(0, 0, 0),
            'task', 'session', 'goal', (0.0, 0.0), 0,
            ResetZeroReceipt(
                reset_zero.receipt_key, identity,
                reset_zero.publish_stamp_ns, 'SAFE_STOP',
                PreviousNormalizedCommand(0, 0, 0), reset_selection,
                reset_stream
            )
        )
    )
    token = TransitionIdentity(identity, 1, 'transition-1')
    lifecycle.begin_step(token)
    next_provenance = ExactObservationProvenance(
        identity, 1_200_000_000, 1_200_000_000, 1_200_000_000
    )
    next_fact = GoalOracleFact(
        1.9, False,
        GoalFactProvenance(
            GoalFactJoinMode.STEP_TRANSITION, binding,
            next_provenance, 1_200_000_000, token
        )
    )
    candidate = StepCommitCandidate(
        token, next_provenance,
        TaskOracleResult(TaskOracleStatus.READY, next_fact),
        CommandReceiptSnapshot(
            token, '90:1', PreviousNormalizedCommand(0.1, 0.2, 0.3)
        )
    )
    return (lifecycle, identity, token, candidate)


def _valid_v3_observation(identity, final_command):
    common = (
        identity.episode_generation, identity.reset_epoch,
        identity.runtime_generation, 'a' * 64
    )
    inputs = validate_observation_inputs(
        context=ActiveLifecycleConfigContext(
            LIFECYCLE_BARRIER_CONTRACT_ID, *common
        ),
        lidar=LidarSnapshot(
            LIDAR_CONTRACT_ID, FRAME_TF_CONTRACT_ID,
            *common, LIDAR_FRAME, (0.5,) * 72
        ),
        local_reference=LocalReferenceSnapshot(
            LOCAL_REFERENCE_CONTRACT_ID, FRAME_TF_CONTRACT_ID, *common,
            'base_link', (0.5, 0.0, 1.0)),
        measured_twist=MeasuredTwistSnapshot(
            MEASURED_TWIST_CONTRACT_ID, FRAME_TF_CONTRACT_ID, *common,
            'base_link', (0.0, 0.0, 0.0)),
        receipt=FinalIssuedReceiptContext(
            LIFECYCLE_BARRIER_CONTRACT_ID, FRAME_TF_CONTRACT_ID,
            *common, 'base_link', final_command),
    )
    assembly = assemble_observation(inputs)
    assert assembly.ready and assembly.vector is not None
    return assembly.vector


def _with_unavailable_odometry(context_value, status):
    """Tạo reference và twist không sẵn sàng từ snapshot nguồn thực."""
    source_snapshot = replace(
        context_value.noisy_odometry_context.snapshot,
        status=status,
        measurement=None,
    )
    odometry = replace(
        context_value.noisy_odometry_context,
        snapshot=source_snapshot,
    )
    health = context_value.goal_sample.health
    unavailable_twist = MeasuredTwistFeatureExtractor(
        ObservationConfig(),
        MotionLimitsConfig(max_vx_mps=0.25, max_vy_mps=0.2, max_wz_radps=0.8),
    ).extract(source_snapshot)
    binding = context_value.goal_sample.scenario_session_binding
    unavailable_reference = build_local_training_reference(
        LocalTrainingGoal(
            context_value.expected_goal_xy_m[0],
            context_value.expected_goal_xy_m[1],
            binding.coordinate_reference_id,
            binding.scenario_id,
        ),
        odometry,
        evaluation_ros_now_ns=health.evaluation_ros_now_ns,
        evaluation_steady_now_ns=health.evaluation_steady_now_ns,
        scan_timestamp_ns=context_value.lifecycle_candidate
        .observation_provenance.odometry_timestamp_ns,
        scan_lifecycle=context_value.transition_identity.identity,
        scan_scenario_identity=binding.scenario_id,
    )
    assert not unavailable_reference.ready
    assert not unavailable_twist.ready
    assert unavailable_twist.features is None
    unavailable_health = replace(
        health,
        noisy_odometry_valid=False,
        reference_valid=False,
        measured_twist_valid=False,
    )
    return replace(
        context_value,
        noisy_odometry_context=odometry,
        local_reference_result=unavailable_reference,
        measured_twist_result=unavailable_twist,
        goal_sample=replace(
            context_value.goal_sample,
            health=unavailable_health,
        ),
    )


def context(
    lifecycle, identity, token, candidate, observation, contact,
    *, selected_source=ReceiptSource.POLICY, clearance_m=0.5,
    clearance_provenance=None, reason=TerminationReason.COLLISION,
    final_sequence=1, source_sequence=11,
    policy_physical=(0.025, 0.04, 0.24), oracle_pose_xy=None,
    measured_twist=(0.0, 0.0, 0.0), twist_features_override=None,
    task_id='task', session_id='session', goal_id='goal',
    goal_xy_m=(0.0, 0.0),
):
    """Tạo dữ kiện transition nhất quán cho kiểm thử commit."""
    cutoff = candidate.observation_provenance.observation_timestamp_ns
    binding = ReceiptStreamBinding(
        90, session_id, 'a' * 64, identity, 'base_link'
    )
    if selected_source is ReceiptSource.POLICY:
        policy_stamp = cutoff
        policy = IssuedCommandReceiptView(
            policy_stamp, 90, final_sequence, ReceiptSource.POLICY, 7,
            source_sequence, token.step_index, token.transition_id,
            identity, session_id, 'a' * 64, policy_physical,
            policy_stamp, 'base_link', True
        )
        selected = policy
        trailing = IssuedCommandReceiptView(
            cutoff + 1, 90, final_sequence + 1, ReceiptSource.SAFE_STOP,
            8, 1, 0, '', identity, session_id, 'a' * 64, (0, 0, 0),
            cutoff + 1, 'base_link', True
        )
        receipts = (policy, trailing)
    else:
        policy_stamp = cutoff - 100_000_000
        policy = IssuedCommandReceiptView(
            policy_stamp, 90, final_sequence, ReceiptSource.POLICY, 7,
            source_sequence, token.step_index, token.transition_id,
            identity, session_id, 'a' * 64, policy_physical,
            policy_stamp, 'base_link', True
        )
        selected = IssuedCommandReceiptView(
            cutoff, 90, final_sequence + 1, ReceiptSource.SAFE_STOP, 8,
            1, 0, '', identity, session_id, 'a' * 64, (0, 0, 0),
            cutoff, 'base_link', True
        )
        trailing = IssuedCommandReceiptView(
            cutoff + 1, 90, final_sequence + 2,
            ReceiptSource.SAFE_STOP, 8, 2, 0, '', identity, session_id,
            'a' * 64, (0, 0, 0), cutoff + 1, 'base_link', True
        )
        receipts = (policy, selected, trailing)
    evaluation_ros_now = cutoff + 1
    evaluation_steady_now = cutoff + 1
    issuance = PolicyActionIssuance(
        7, source_sequence, identity, token.step_index, token.transition_id
    )
    selection = select_final_issued_at_cutoff(
        receipts, binding=binding, issuance=issuance, cutoff_ros_ns=cutoff,
        evaluation_ros_now_ns=evaluation_ros_now,
        evaluation_steady_now_ns=evaluation_steady_now,
        reset_barrier_ros_ns=0, action_barrier_ros_ns=0,
        physical_scales=(0.25, 0.2, 0.8)
    )
    normalized = selection.normalized_command
    candidate = replace(candidate, command_receipt=CommandReceiptSnapshot(
        token, selected.receipt_key,
        PreviousNormalizedCommand(*normalized)))
    baseline = lifecycle.snapshot.reward_baseline
    previous_command = lifecycle.snapshot.previous_issued_command
    current_fact = candidate.goal_result.fact
    goal_xy = goal_xy_m
    pose_x, pose_y = (
        (-current_fact.goal_distance_m, 0.0)
        if oracle_pose_xy is None else oracle_pose_xy
    )
    measured_goal_distance = float(np.hypot(
        pose_x - goal_xy[0], pose_y - goal_xy[1]
    ))
    if measured_goal_distance != current_fact.goal_distance_m:
        current_fact = replace(
            current_fact, goal_distance_m=measured_goal_distance
        )
        candidate = replace(candidate, goal_result=TaskOracleResult(
            TaskOracleStatus.READY, current_fact
        ))
    scenario_binding = current_fact.provenance.scenario_session_binding
    odometry = SimulatedOdometrySnapshot(
        cutoff, SimulatedOdometryStatus.VALID, 100 + token.step_index,
        SimulatedOdometryMeasurement(
            pose_x, pose_y, 0.0, *measured_twist
        ),
    )
    evaluation_ros_now = selection.evaluation_ros_now_ns
    evaluation_steady_now = selection.evaluation_steady_now_ns
    received_steady = evaluation_steady_now - 1
    lifecycle_stamp = cutoff - 100_000_000
    selected_stamp = selection.receipt.publish_stamp_ns
    selected_received = selection.receipt.received_steady_ns
    health_values = {
        name: True for name in (
            'simulator_valid', 'clock_valid', 'reset_complete',
            'scenario_identity_valid', 'world_identity_valid',
            'session_identity_valid', 'lifecycle_valid', 'barrier_valid',
            'safety_ready', 'safety_fault', 'estop_active', 'reset_pending',
            'scan_valid', 'noisy_odometry_valid', 'reference_valid',
            'measured_twist_valid', 'oracle_pose_valid', 'oracle_twist_valid',
            'contact_source_healthy', 'receipt_valid', 'context_matches',
        )
    }
    health_values.update({
        'safety_fault': False, 'estop_active': False, 'reset_pending': False,
        'scenario_session_binding': scenario_binding,
        'task_id': task_id, 'session_id': session_id,
        'lifecycle_key': (identity.episode_generation, identity.reset_epoch,
                          identity.runtime_generation),
        'goal_id': goal_id, 'goal_x_m': goal_xy[0], 'goal_y_m': goal_xy[1],
        'receipt_session_id': binding.session_id,
        'receipt_lifecycle_key': (identity.episode_generation,
                                  identity.reset_epoch,
                                  identity.runtime_generation),
        'oracle_timestamp_ns': cutoff, 'oracle_twist_timestamp_ns': cutoff,
        'scan_timestamp_ns': cutoff, 'noisy_odometry_timestamp_ns': cutoff,
        'reference_timestamp_ns': cutoff,
        'measured_twist_timestamp_ns': cutoff,
        'lifecycle_timestamp_ns': lifecycle_stamp,
        'receipt_timestamp_ns': selected_stamp, 'cutoff_ros_ns': cutoff,
        'evaluation_ros_now_ns': evaluation_ros_now,
        'oracle_received_steady_ns': received_steady,
        'oracle_twist_received_steady_ns': received_steady,
        'scan_received_steady_ns': received_steady,
        'noisy_odometry_received_steady_ns': received_steady,
        'lifecycle_received_steady_ns': (
            evaluation_steady_now - 100_000_000
        ),
        'receipt_received_steady_ns': selected_received,
        'evaluation_steady_now_ns': evaluation_steady_now,
    })
    source_times = (
        ('scan', cutoff, received_steady),
        ('noisy_odom', cutoff, received_steady),
        ('oracle', cutoff, received_steady),
        ('oracle_twist', cutoff, received_steady),
        (
            'lifecycle', lifecycle_stamp,
            evaluation_steady_now - 100_000_000
        ),
        ('receipt', selected_stamp, selected_received),
    )
    for prefix, stamp, received in source_times:
        health_values[f'{prefix}_ros_age_ns'] = evaluation_ros_now - stamp
        health_values[f'{prefix}_steady_age_ns'] = (
            evaluation_steady_now - received
        )
    health = LocalTrainingHealth(**health_values)
    goal_sample = OracleGoalSample(
        timestamp_ns=cutoff, received_steady_ns=received_steady,
        lifecycle_key=health.lifecycle_key,
        scenario_session_binding=scenario_binding, task_id=task_id,
        session_id=session_id, goal_id=goal_id,
        goal_x_m=goal_xy[0], goal_y_m=goal_xy[1],
        pose_x_m=pose_x, pose_y_m=pose_y,
        body_vx_mps=0.0, body_vy_mps=0.0, body_wz_radps=0.0,
        health=health,
    )
    lifecycle_snapshot = lifecycle.snapshot
    contact_snapshot = contact.state
    health_continuity = (
        lifecycle_snapshot.task_health_epoch
        == lifecycle_snapshot.committed_task_health_epoch
        and contact_snapshot.health_epoch
        == lifecycle_snapshot.committed_contact_health_epoch
    )
    settle_before = (
        lifecycle_snapshot.goal_settle_state if health_continuity else None
    )
    if settle_before is None:
        settle_state = GoalSettleState()
    else:
        settle_state = GoalSettleState(
            lifecycle_key=health.lifecycle_key,
            settled_since_ros_ns=settle_before.settled_since_ros_ns,
            last_ros_ns=settle_before.last_ros_ns,
            success=settle_before.success,
            scenario_session_binding=scenario_binding,
            task_id=settle_before.task_id,
            session_id=settle_before.session_id,
            goal_id=settle_before.goal_id,
            goal_xy_m=settle_before.goal_xy_m,
        )
    goal_result = evaluate_local_training_goal(
        goal_sample, settle_state,
        expected_scenario_session_binding=scenario_binding,
        expected_task_id=task_id, expected_session_id=session_id,
        expected_goal_id=goal_id, expected_goal_xy_m=goal_xy,
    )
    odometry_context = NoisyOdometryContext(
        odometry, identity, scenario_binding.coordinate_reference_id,
        scenario_binding.scenario_id, received_steady,
    )
    reference_result = build_local_training_reference(
        LocalTrainingGoal(
            *goal_xy, scenario_binding.coordinate_reference_id,
            scenario_binding.scenario_id
        ),
        odometry_context, evaluation_ros_now_ns=evaluation_ros_now,
        evaluation_steady_now_ns=evaluation_steady_now,
        scan_timestamp_ns=cutoff, scan_lifecycle=identity,
        scan_scenario_identity=scenario_binding.scenario_id,
    )
    assert reference_result.ready
    twist_scales = selection.physical_scales
    twist_features = (
        tuple(
            physical / scale
            for physical, scale in zip(
                measured_twist, twist_scales, strict=True
            )
        )
        if twist_features_override is None
        else twist_features_override
    )
    twist_result = MeasuredTwistFeatureResult(
        MeasuredTwistFeatureStatus.READY, cutoff, odometry.sequence,
        twist_features,
    )
    common = (
        identity.episode_generation, identity.reset_epoch,
        identity.runtime_generation, binding.config_hash
    )
    observation_inputs = validate_observation_inputs(
        context=ActiveLifecycleConfigContext(
            LIFECYCLE_BARRIER_CONTRACT_ID, *common
        ),
        lidar=LidarSnapshot(
            LIDAR_CONTRACT_ID, FRAME_TF_CONTRACT_ID,
            *common, LIDAR_FRAME, (0.5,) * 72
        ),
        local_reference=LocalReferenceSnapshot(
            LOCAL_REFERENCE_CONTRACT_ID, FRAME_TF_CONTRACT_ID, *common,
            'base_link', tuple(
                float(value) for value in reference_result.features
            )
        ),
        measured_twist=MeasuredTwistSnapshot(
            MEASURED_TWIST_CONTRACT_ID, FRAME_TF_CONTRACT_ID, *common,
            'base_link', twist_result.features),
        receipt=FinalIssuedReceiptContext(
            LIFECYCLE_BARRIER_CONTRACT_ID, FRAME_TF_CONTRACT_ID, *common,
            'base_link', tuple(
                float(value) for value in np.asarray(
                    normalized, dtype=np.float32
                )
            )
        ),
    )
    assert observation_inputs is not None
    assembled = assemble_observation(observation_inputs)
    assert assembled.ready and assembled.vector is not None
    # Existing malformed-vector tests pass their deliberate mutation through.
    legacy_fixture = _valid_v3_observation(identity, normalized)
    if observation is None or np.array_equal(observation, legacy_fixture):
        observation = assembled.vector
    committed_samples = tuple(
        EpisodeTaskSample(
            sample.ros_time_ns, sample.x_m, sample.y_m,
            sample.true_goal_distance_m, sample.required_health_valid
        )
        for sample in (
            lifecycle_snapshot.task_history if health_continuity else ()
        )
        if (sample.lifecycle == identity and sample.task_id == task_id
            and sample.session_id == session_id and sample.goal_id == goal_id
            and sample.goal_xy_m == goal_xy)
    )
    contact_state = contact.state
    termination = TerminationManager().evaluate(
        TerminationInput(
            elapsed_ros_ns=(
                cutoff - lifecycle.snapshot.reset_commit_facts
                .observation_provenance.observation_timestamp_ns
            ),
            current_sample=EpisodeTaskSample(
                cutoff, pose_x, pose_y, goal_result.distance_m,
                goal_result.healthy
            ),
            trajectory=committed_samples,
            collision=(
                contact_state.contact_active
                or contact_state.collision_pulse_pending
            ),
            goal_settled_success=goal_result.success,
        )
    )
    reason = termination.reason
    state = (
        EpisodeLifecycleState.TERMINATED if termination.terminated else
        EpisodeLifecycleState.TRUNCATED if termination.truncated else
        EpisodeLifecycleState.RUNNING
    )
    candidate = replace(candidate, committed_state=state)
    dt_sim_s = (
        cutoff - baseline.previous_committed_sim_time_ns
    ) / 1_000_000_000.0
    reward = RewardManager().compute(TransitionRewardInput(
        baseline.previous_goal_distance_m,
        current_fact.goal_distance_m,
        clearance_m,
        dt_sim_s,
        tuple(
            float(value) for value in np.asarray(
                normalized, dtype=np.float32
            )
        ),
        tuple(float(value) for value in np.asarray((
            previous_command.vx, previous_command.vy, previous_command.wz
        ), dtype=np.float32)),
        goal=reason is TerminationReason.GOAL,
        collision=reason is TerminationReason.COLLISION,
        stuck=reason is TerminationReason.STUCK,
    ))
    return RLTransitionContext(
        transition_identity=token,
        lifecycle_candidate=candidate,
        observation=observation,
        reward=reward,
        termination=termination,
        info=(('step', 1),),
        issued_receipt_id=selected.receipt_key,
        cutoff_selection=selection,
        command_history=tuple(float(value) for value in np.asarray(
            normalized, dtype=np.float32)),
        contact_transition_id=token.transition_id,
        contact_latch=contact,
        policy_issuance=issuance,
        policy_issuance_receipt=policy,
        clearance_m=clearance_m,
        clearance_observation_provenance=(
            candidate.observation_provenance if clearance_provenance is None
            else clearance_provenance
        ),
        observation_inputs=observation_inputs,
        local_reference_result=reference_result,
        noisy_odometry_context=odometry_context,
        measured_twist_result=twist_result,
        goal_sample=goal_sample,
        expected_task_id=task_id,
        expected_session_id=session_id,
        expected_goal_id=goal_id,
        expected_goal_xy_m=goal_xy,
        valid_area=None,
    )


def test_atomic_commit_copies_observation_and_commits_full_tuple_once():
    """Commit duy nhất và cô lập dữ liệu đã lưu khỏi input."""
    lifecycle, identity, token, candidate = ready_lifecycle()
    contact = ContactLatch()
    contact.reset(identity)
    contact.observe(ContactFact(identity, 'collision-pulse', 1, True, True))
    source = _valid_v3_observation(identity, (0.1, 0.2, 0.3)).copy()
    committer = RLTransitionCommitter(lifecycle)
    context_value = context(
        lifecycle, identity, token, candidate, source, contact
    )
    assert context_value.reward.terms.time == pytest.approx(-0.02)
    assert context_value.reward.terms.smooth == pytest.approx(-0.0035)
    result = committer.commit(context_value)
    assert result.committed and result.transition is not None
    assert (
        result.transition.lifecycle_result.status
        is EpisodeOperationStatus.STEP_COMMITTED
    )
    assert not result.transition.observation.flags.writeable
    with pytest.raises(ValueError):
        result.transition.observation.setflags(write=True)
    source[0] = 999
    assert result.transition.observation[0] == 0.5
    assert (
        contact.state.contact_active
        and not contact.state.collision_pulse_pending
    )
    assert (
        committer.commit(context_value).reason
        == 'transition was already committed'
    )


def test_two_committers_sharing_lifecycle_cannot_commit_step_twice():
    """Chặn commit lặp từ hai committer cùng lifecycle."""
    lifecycle, identity, token, candidate = ready_lifecycle()
    contact = ContactLatch()
    contact.reset(identity)
    contact.observe(ContactFact(identity, 'collision', 1, True, True))
    fact = context(
        lifecycle, identity, token, candidate,
        _valid_v3_observation(identity, (0.1, 0.2, 0.3)), contact
    )
    first = RLTransitionCommitter(lifecycle)
    second = RLTransitionCommitter(lifecycle)
    assert first.commit(fact).committed
    result = second.commit(fact)
    assert not result.committed
    assert lifecycle.snapshot.step_index == 1
    assert len(first.committed) == 1
    assert second.committed == ()


def test_two_concurrent_committers_publish_one_transition_once():
    """Tuần tự hóa hai commit cạnh tranh trên cùng transition."""
    """Two simultaneous owners publish the same lifecycle step at most once."""
    lifecycle, identity, token, candidate = ready_lifecycle()
    contact = ContactLatch()
    contact.reset(identity)
    contact.observe(ContactFact(identity, 'collision', 1, True, True))
    fact = context(
        lifecycle, identity, token, candidate,
        _valid_v3_observation(identity, (0.1, 0.2, 0.3)), contact,
    )
    committers = (
        RLTransitionCommitter(lifecycle),
        RLTransitionCommitter(lifecycle),
    )
    start = Barrier(3)
    results = []

    def run(committer):
        start.wait()
        results.append(committer.commit(fact))

    threads = [
        Thread(target=run, args=(committer,)) for committer in committers
    ]
    for thread in threads:
        thread.start()
    start.wait()
    for thread in threads:
        thread.join(timeout=2)
        assert not thread.is_alive()

    assert sum(result.committed for result in results) == 1
    assert lifecycle.snapshot.step_index == 1
    assert sum(len(committer.committed) for committer in committers) == 1
    assert lifecycle.snapshot.consumed_receipt_ids == ('90:1',)
    assert contact.state.consumed_transition_ids == ('transition-1',)
    assert not contact.state.collision_pulse_pending
    assert contact.state.contact_active


def test_contact_before_commit_boundary_cannot_be_hidden_by_stale_context():
    """Tính contact đã nhận trước commit vào transition."""
    """A new collision rejects the stale non-collision transition."""
    lifecycle, identity, token, candidate = ready_lifecycle()
    contact = ContactLatch()
    contact.reset(identity)
    stale_noncollision = context(
        lifecycle, identity, token, candidate,
        _valid_v3_observation(identity, (0.1, 0.2, 0.3)), contact,
        reason=None,
    )
    assert contact.observe(ContactFact(
        identity, 'before-cut', 1, True, True
    )).accepted
    before = lifecycle.snapshot
    committer = RLTransitionCommitter(lifecycle)

    rejected = committer.commit(stale_noncollision)

    assert not rejected.committed
    assert lifecycle.snapshot == before
    assert contact.state.collision_pulse_pending
    assert contact.state.consumed_transition_ids == ()
    assert committer.committed == ()

    collision_context = context(
        lifecycle, identity, token, candidate,
        _valid_v3_observation(identity, (0.1, 0.2, 0.3)), contact,
        reason=TerminationReason.COLLISION,
    )
    committed = committer.commit(collision_context)
    assert committed.committed
    assert committed.transition.reward.terms.terminal == -15.0
    assert (
        committed.transition.termination.reason is
        TerminationReason.COLLISION
    )
    assert contact.state.contact_active
    assert not contact.state.collision_pulse_pending


def test_contact_arriving_while_commit_holds_boundary_is_retained_afterward(
    monkeypatch,
):
    """Giữ event contact đến trong lúc commit đang chạy."""
    """An event waiting on commit is admitted after the committed boundary."""
    lifecycle, identity, token, candidate = ready_lifecycle()
    contact = ContactLatch()
    contact.reset(identity)
    fact = context(
        lifecycle, identity, token, candidate,
        _valid_v3_observation(identity, (0.1, 0.2, 0.3)), contact,
        reason=None,
    )
    committer = RLTransitionCommitter(lifecycle)
    entered_commit = Event()
    release_commit = Event()
    event_started = Event()
    original_commit_step = lifecycle.commit_step

    def paused_commit_step(step_candidate, **commit_kwargs):
        entered_commit.set()
        assert release_commit.wait(timeout=2)
        return original_commit_step(step_candidate, **commit_kwargs)

    monkeypatch.setattr(lifecycle, 'commit_step', paused_commit_step)
    commit_results = []

    def run_commit():
        commit_results.append(committer.commit(fact))

    event_results = []

    def publish_contact():
        event_started.set()
        event_results.append(contact.observe(ContactFact(
            identity, 'after-cut', 1, True, True
        )))

    commit_thread = Thread(target=run_commit)
    commit_thread.start()
    assert entered_commit.wait(timeout=2)
    event_thread = Thread(target=publish_contact)
    event_thread.start()
    assert event_started.wait(timeout=2)
    release_commit.set()
    commit_thread.join(timeout=2)
    event_thread.join(timeout=2)

    assert not commit_thread.is_alive() and not event_thread.is_alive()
    assert commit_results[0].committed
    assert event_results[0].accepted
    assert commit_results[0].transition.termination.reason is None
    assert contact.state.contact_active
    assert contact.state.collision_pulse_pending
    assert contact.state.consumed_transition_ids == ('transition-1',)


def test_reset_after_commit_uses_same_boundary_and_clears_old_contact_identity(
    monkeypatch,
):
    """Đồng bộ reset với commit và loại contact identity cũ."""
    """A competing reset follows the commit and clears old contact identity."""
    lifecycle, identity, token, candidate = ready_lifecycle()
    contact = ContactLatch()
    contact.reset(identity)
    contact.observe(ContactFact(identity, 'collision', 1, True, True))
    fact = context(
        lifecycle, identity, token, candidate,
        _valid_v3_observation(identity, (0.1, 0.2, 0.3)), contact,
    )
    committer = RLTransitionCommitter(lifecycle)
    entered_commit = Event()
    release_commit = Event()
    reset_started = Event()
    original_commit_step = lifecycle.commit_step

    def paused_commit_step(step_candidate, **commit_kwargs):
        entered_commit.set()
        assert release_commit.wait(timeout=2)
        return original_commit_step(step_candidate, **commit_kwargs)

    monkeypatch.setattr(lifecycle, 'commit_step', paused_commit_step)
    commit_results = []
    reset_results = []
    next_identity = EpisodeLifecycleIdentity(2, 2, 1)
    next_binding = ScenarioSessionBinding(
        next_identity, 'scenario', '1', 'a' * 64, 'world', 'b' * 64,
        'local-frame',
    )

    def reset_episode():
        reset_started.set()
        with CORE_TRANSACTION_LOCK:
            reset_results.append(lifecycle.begin_reset(
                next_identity, next_binding
            ))
            contact.reset(next_identity)

    commit_thread = Thread(target=lambda: commit_results.append(
        committer.commit(fact)
    ))
    commit_thread.start()
    assert entered_commit.wait(timeout=2)
    reset_thread = Thread(target=reset_episode)
    reset_thread.start()
    assert reset_started.wait(timeout=2)
    release_commit.set()
    commit_thread.join(timeout=2)
    reset_thread.join(timeout=2)

    assert not commit_thread.is_alive() and not reset_thread.is_alive()
    assert commit_results[0].committed
    assert reset_results[0].status is EpisodeOperationStatus.RESET_STARTED
    assert lifecycle.snapshot.identity == next_identity
    assert lifecycle.snapshot.step_index is None
    assert contact.state.lifecycle == next_identity
    assert not contact.state.contact_active
    assert not contact.state.collision_pulse_pending


def test_invalid_prepare_keeps_baseline_history_and_contact_pulse_untouched():
    """Không đổi state đã commit khi bước chuẩn bị bị từ chối."""
    lifecycle, identity, token, candidate = ready_lifecycle()
    contact = ContactLatch()
    contact.reset(identity)
    contact.observe(ContactFact(identity, 'pulse', 1, True, True))
    before = lifecycle.snapshot
    committer = RLTransitionCommitter(lifecycle)
    invalid = np.full(80, 0, dtype=np.float32)
    result = committer.commit(context(
        lifecycle, identity, token, candidate, invalid, contact
    ))
    assert not result.committed and 'float32[81]' in result.reason
    assert (
        lifecycle.snapshot == before
        and contact.state.collision_pulse_pending
    )
    assert committer.committed == ()


def test_unhealthy_contact_source_rejects_transition_without_consuming_state():
    """Từ chối transition khi nguồn contact không khỏe."""
    lifecycle, identity, token, candidate = ready_lifecycle()
    contact = ContactLatch()
    contact.reset(identity)
    contact.observe(ContactFact(identity, 'collision', 1, True, True))
    fact = context(
        lifecycle, identity, token, candidate,
        _valid_v3_observation(identity, (0.1, 0.2, 0.3)), contact,
    )
    contact.observe(ContactFact(identity, 'health-loss', 2, False, False))
    lifecycle_before = lifecycle.snapshot
    contact_before = contact.state
    committer = RLTransitionCommitter(lifecycle)

    rejected = committer.commit(fact)

    assert not rejected.committed
    lifecycle_after = lifecycle.snapshot
    assert lifecycle_after.reward_baseline == lifecycle_before.reward_baseline
    assert lifecycle_after.previous_issued_command == (
        lifecycle_before.previous_issued_command
    )
    assert lifecycle_after.consumed_receipt_ids == (
        lifecycle_before.consumed_receipt_ids
    )
    assert lifecycle_after.committed_transition_ids == (
        lifecycle_before.committed_transition_ids
    )
    assert lifecycle_after.task_history == lifecycle_before.task_history
    assert lifecycle_after.task_health_epoch > (
        lifecycle_before.task_health_epoch
    )
    assert contact.state == contact_before
    assert contact.state.collision_pulse_pending
    assert committer.committed == ()

    assert contact.observe(ContactFact(
        identity, 'health-restored', 3, True, True
    )).accepted
    accepted = committer.commit(fact)
    assert accepted.committed
    assert accepted.transition.reward.terms.terminal == -15.0
    assert contact.state.contact_active
    assert not contact.state.collision_pulse_pending


def test_committer_rejects_reward_time_that_disagrees_with_cutoff_timestamps():
    """Đối chiếu thời gian reward với timestamp cutoff thực."""
    lifecycle, identity, token, candidate = ready_lifecycle()
    contact = ContactLatch()
    contact.reset(identity)
    contact.observe(ContactFact(identity, 'collision-pulse', 1, True, True))
    timestamp_ns = 1_000_000_100
    provenance = ExactObservationProvenance(
        identity, timestamp_ns, timestamp_ns, timestamp_ns
    )
    oracle_fact = replace(
        candidate.goal_result.fact,
        provenance=GoalFactProvenance(
            GoalFactJoinMode.STEP_TRANSITION,
            lifecycle.snapshot.committed_scenario_session_binding,
            provenance, timestamp_ns, token),
        )
    candidate = replace(
        candidate, observation_provenance=provenance,
        goal_result=TaskOracleResult(TaskOracleStatus.READY, oracle_fact)
    )
    observation = _valid_v3_observation(identity, (0.1, 0.2, 0.3))
    before = lifecycle.snapshot
    context_value = context(
        lifecycle, identity, token, candidate, observation, contact
    )
    wrong_reward = RewardManager().compute(
        TransitionRewardInput(
            2.0, 1.9, 0.5, 0.1, (0.1, 0.2, 0.3), (0.0, 0.0, 0.0),
            collision=True,
        )
    )
    context_value = replace(context_value, reward=wrong_reward)
    result = RLTransitionCommitter(lifecycle).commit(context_value)
    assert not result.committed
    assert lifecycle.snapshot == before
    assert contact.state.collision_pulse_pending


def test_safe_stop_selected_after_policy_issuance_drives_v3_and_reward():
    """Dùng lệnh SAFE_STOP thực tế trong observation và reward."""
    lifecycle, identity, token, candidate = ready_lifecycle()
    contact = ContactLatch()
    contact.reset(identity)
    value = context(
        lifecycle, identity, token, candidate, None, contact,
        selected_source=ReceiptSource.SAFE_STOP, reason=None
    )
    assert value.policy_issuance_receipt.final_command != (0.0, 0.0, 0.0)
    assert value.cutoff_selection.receipt.source is ReceiptSource.SAFE_STOP
    assert value.observation[78:81].tolist() == [0.0, 0.0, 0.0]
    result = RLTransitionCommitter(lifecycle).commit(value)
    assert result.committed
    assert result.transition.command_history == (0.0, 0.0, 0.0)
    assert result.transition.reward.terms.smooth == 0.0
    assert lifecycle.snapshot.previous_issued_command == (
        PreviousNormalizedCommand(0.0, 0.0, 0.0)
    )


@pytest.mark.parametrize(
    'field', ['progress', 'time', 'clearance', 'smooth', 'terminal', 'total',
              'baseline_distance_m', 'previous_distance', 'previous_command']
)
def test_any_supplied_reward_mismatch_rejects_without_state_or_pulse_change(
    field,
):
    """Từ chối mọi reward do caller cung cấp nếu sai facts."""
    lifecycle, identity, token, candidate = ready_lifecycle()
    contact = ContactLatch()
    contact.reset(identity)
    contact.observe(ContactFact(identity, 'reward-mismatch', 1, True, True))
    value = context(
        lifecycle, identity, token, candidate,
        _valid_v3_observation(identity, (0.1, 0.2, 0.3)), contact
    )
    before = lifecycle.snapshot
    if field in ('previous_distance', 'previous_command'):
        baseline = lifecycle.snapshot.reward_baseline
        previous = lifecycle.snapshot.previous_issued_command
        cutoff = (
            value.lifecycle_candidate.observation_provenance
            .observation_timestamp_ns
        )
        current = value.lifecycle_candidate.goal_result.fact
        bad_reward = RewardManager().compute(TransitionRewardInput(
            baseline.previous_goal_distance_m + (
                0.1 if field == 'previous_distance' else 0.0
            ),
            current.goal_distance_m,
            value.clearance_m,
            (cutoff - baseline.previous_committed_sim_time_ns) / 1e9,
            value.command_history,
            (0.9, 0.8, 0.7) if field == 'previous_command' else (
                previous.vx, previous.vy, previous.wz
            ),
            collision=(
                value.termination.reason is TerminationReason.COLLISION
            ),
        ))
    elif field == 'total':
        bad_reward = replace(value.reward, total=value.reward.total + 0.01)
    elif field == 'baseline_distance_m':
        bad_reward = replace(
            value.reward,
            baseline_distance_m=value.reward.baseline_distance_m + 0.01
        )
    else:
        terms = replace(
            value.reward.terms,
            **{field: getattr(value.reward.terms, field) + 0.01}
        )
        bad_reward = replace(
            value.reward, terms=terms, total=value.reward.total + 0.01
        )
    rejected = RLTransitionCommitter(lifecycle).commit(
        replace(value, reward=bad_reward)
    )
    assert not rejected.committed
    assert lifecycle.snapshot == before
    assert contact.state.collision_pulse_pending


def test_clearance_is_snapshot_bound_and_changes_only_its_reward_term():
    """Nối clearance đúng snapshot vào đúng reward term."""
    lifecycle, identity, token, candidate = ready_lifecycle()
    contact = ContactLatch()
    contact.reset(identity)
    wrong = context(
        lifecycle, identity, token, candidate,
        _valid_v3_observation(identity, (0.1, 0.2, 0.3)), contact,
        clearance_m=0.15,
        clearance_provenance=ExactObservationProvenance(
            identity, 1_199_999_999, 1_199_999_999, 1_200_000_000
        ), reason=None
    )
    before = lifecycle.snapshot
    assert not RLTransitionCommitter(lifecycle).commit(wrong).committed
    assert lifecycle.snapshot == before
    valid = context(
        lifecycle, identity, token, candidate,
        _valid_v3_observation(identity, (0.1, 0.2, 0.3)), contact,
        clearance_m=0.15, reason=None
    )
    result = RLTransitionCommitter(lifecycle).commit(valid)
    assert result.committed
    assert result.transition.reward.terms.clearance == pytest.approx(-0.2)


def test_second_step_uses_committed_distance_and_command_as_before_state():
    """Dùng baseline và command của transition đã commit trước."""
    lifecycle, identity, token, candidate = ready_lifecycle()
    contact = ContactLatch()
    contact.reset(identity)
    first = context(
        lifecycle, identity, token, candidate,
        _valid_v3_observation(identity, (0.1, 0.2, 0.3)), contact,
        reason=None
    )
    first_result = RLTransitionCommitter(lifecycle).commit(first)
    assert first_result.committed
    next_token = TransitionIdentity(identity, 2, 'transition-2')
    lifecycle.begin_step(next_token)
    session = lifecycle.snapshot.committed_scenario_session_binding
    provenance = ExactObservationProvenance(
        identity, 1_400_000_000, 1_400_000_000, 1_400_000_000
    )
    fact = GoalOracleFact(
        1.8, False,
        GoalFactProvenance(
            GoalFactJoinMode.STEP_TRANSITION, session, provenance,
            1_400_000_000, next_token
        )
    )
    next_candidate = StepCommitCandidate(
        next_token, provenance,
        TaskOracleResult(TaskOracleStatus.READY, fact),
        CommandReceiptSnapshot(
            next_token, '90:3', PreviousNormalizedCommand(0.2, 0.0, 0.0)
        )
    )
    next_contact = ContactLatch()
    next_contact.reset(identity)
    second = context(
        lifecycle, identity, next_token, next_candidate,
        _valid_v3_observation(identity, (0.2, 0.0, 0.0)), next_contact,
        reason=None, final_sequence=3, source_sequence=12,
        policy_physical=(0.05, 0.0, 0.0)
    )
    second_result = RLTransitionCommitter(lifecycle).commit(second)
    assert second_result.committed
    assert second_result.transition.reward.terms.progress == pytest.approx(0.2)
    assert second_result.transition.reward.terms.smooth == pytest.approx(
        -0.0035
    )
    assert second_result.transition.reward.baseline_distance_m == 1.9


@pytest.mark.parametrize(
    ('collision', 'expected_reason', 'expected_state', 'expected_terminal'),
    [
        (True, TerminationReason.COLLISION,
            EpisodeLifecycleState.TERMINATED, -15.0),
        (False, None, EpisodeLifecycleState.RUNNING, 0.0),
    ],
)
def test_reward_terminal_term_follows_typed_task_termination(
    collision, expected_reason, expected_state, expected_terminal
):
    """Ánh xạ termination đã định kiểu sang terminal reward."""
    lifecycle, identity, token, candidate = ready_lifecycle()
    contact = ContactLatch()
    contact.reset(identity)
    if collision:
        contact.observe(
            ContactFact(identity, 'terminal-collision', 1, True, True)
        )
    value = context(
        lifecycle, identity, token, candidate, None, contact,
        reason=expected_reason
    )

    result = RLTransitionCommitter(lifecycle).commit(value)

    assert result.committed
    assert result.transition.reward.terms.terminal == expected_terminal
    assert result.transition.termination.reason is expected_reason
    assert result.transition.termination.terminated is (
        expected_state is EpisodeLifecycleState.TERMINATED
    )
    assert result.transition.termination.truncated is (
        expected_state is EpisodeLifecycleState.TRUNCATED
    )
    assert result.transition.lifecycle_result.snapshot.state is expected_state


def test_goal_termination_comes_from_same_task_settle_across_commits():
    """Nối settle goal của cùng task qua các commit liên tiếp."""
    lifecycle, identity, first_token, first_candidate = ready_lifecycle()
    contact = ContactLatch()
    contact.reset(identity)
    committer = RLTransitionCommitter(lifecycle)
    transitions = []
    for step in range(1, 6):
        timestamp = 1_200_000_000 + (step - 1) * 250_000_000
        if step == 1:
            token = first_token
            candidate = replace(
                first_candidate,
                transition_identity=token,
                observation_provenance=ExactObservationProvenance(
                    identity, timestamp, timestamp, timestamp
                ),
            )
            fact = candidate.goal_result.fact
            candidate = replace(candidate, goal_result=TaskOracleResult(
                TaskOracleStatus.READY,
                replace(
                    fact, goal_distance_m=0.0, goal_reached=False,
                    provenance=GoalFactProvenance(
                        GoalFactJoinMode.STEP_TRANSITION,
                        lifecycle.snapshot
                        .committed_scenario_session_binding,
                        candidate.observation_provenance, timestamp, token,
                    )),
            ))
        else:
            token = TransitionIdentity(identity, step, f'goal-step-{step}')
            assert lifecycle.begin_step(token).status is (
                EpisodeOperationStatus.STEP_STARTED
            )
            provenance = ExactObservationProvenance(
                identity, timestamp, timestamp, timestamp
            )
            binding = lifecycle.snapshot.committed_scenario_session_binding
            candidate = StepCommitCandidate(
                token, provenance,
                TaskOracleResult(TaskOracleStatus.READY, GoalOracleFact(
                    0.0, False, GoalFactProvenance(
                        GoalFactJoinMode.STEP_TRANSITION, binding,
                        provenance, timestamp, token,
                    ),
                )),
                CommandReceiptSnapshot(
                    token, f'candidate-{step}',
                    PreviousNormalizedCommand(0, 0, 0)
                ),
            )
        value = context(
            lifecycle, identity, token, candidate, None, contact,
            selected_source=ReceiptSource.SAFE_STOP, reason=None,
            final_sequence=step * 10, source_sequence=10 + step,
            oracle_pose_xy=(0.0, 0.0),
        )
        result = committer.commit(value)
        assert result.committed, result.reason
        transitions.append(result.transition)

    assert [item.goal_settle_result.success for item in transitions] == [
        False, False, False, False, True
    ]
    assert transitions[-1].termination.reason is TerminationReason.GOAL
    assert transitions[-1].reward.terms.terminal == 15.0
    assert transitions[-1].observation[78:81].tolist() == [0.0, 0.0, 0.0]
    assert transitions[-1].command_history == (0.0, 0.0, 0.0)


@pytest.mark.parametrize('attempt_during_health_loss', [False, True])
def test_health_interruption_restarts_goal_settle_window(
    attempt_during_health_loss,
):
    """Health gap cắt settle dù commit trong lúc lỗi hay không."""
    lifecycle, identity, first_token, first_candidate = ready_lifecycle()
    contact = ContactLatch()
    contact.reset(identity)
    committer = RLTransitionCommitter(lifecycle)

    def goal_step(step, timestamp, first=None):
        if first is None:
            token = TransitionIdentity(identity, step, f'health-step-{step}')
            lifecycle.begin_step(token)
            provenance = ExactObservationProvenance(
                identity, timestamp, timestamp, timestamp
            )
            binding = lifecycle.snapshot.committed_scenario_session_binding
            candidate = StepCommitCandidate(
                token,
                provenance,
                TaskOracleResult(TaskOracleStatus.READY, GoalOracleFact(
                    0.0,
                    False,
                    GoalFactProvenance(
                        GoalFactJoinMode.STEP_TRANSITION,
                        binding,
                        provenance,
                        timestamp,
                        token,
                    ),
                )),
                CommandReceiptSnapshot(
                    token,
                    f'health-candidate-{step}',
                    PreviousNormalizedCommand(0.0, 0.0, 0.0),
                ),
            )
        else:
            token = first_token
            provenance = ExactObservationProvenance(
                identity, timestamp, timestamp, timestamp
            )
            fact = first.goal_result.fact
            candidate = replace(
                first,
                observation_provenance=provenance,
                goal_result=TaskOracleResult(TaskOracleStatus.READY, replace(
                    fact,
                    goal_distance_m=0.0,
                    goal_reached=False,
                    provenance=GoalFactProvenance(
                        GoalFactJoinMode.STEP_TRANSITION,
                        lifecycle.snapshot.committed_scenario_session_binding,
                        provenance,
                        timestamp,
                        token,
                    ),
                )),
            )
        value = context(
            lifecycle,
            identity,
            token,
            candidate,
            None,
            contact,
            selected_source=ReceiptSource.SAFE_STOP,
            final_sequence=step * 10,
            source_sequence=10 + step,
            oracle_pose_xy=(0.0, 0.0),
        )
        return token, candidate, value

    for step in range(1, 5):
        timestamp = 1_200_000_000 + (step - 1) * 250_000_000
        if step == 1:
            token, candidate, value = goal_step(
                step, timestamp, first_candidate
            )
        else:
            token, candidate, value = goal_step(step, timestamp)
        result = committer.commit(value)
        assert result.committed, result.reason
    assert lifecycle.snapshot.goal_settle_state.settled_since_ros_ns == (
        1_200_000_000
    )

    assert not contact.observe(ContactFact(
        identity, 'health-gap', 1, False, False
    )).accepted
    next_timestamp = 2_200_000_000
    token, candidate, value = goal_step(5, next_timestamp)
    if attempt_during_health_loss:
        rejected = committer.commit(value)
        assert not rejected.committed
        before_recovery = lifecycle.snapshot
        assert (
            before_recovery.reward_baseline.previous_committed_sim_time_ns
            == 1_950_000_000
        )
        assert (
            before_recovery.task_history[-1].ros_time_ns
            == 1_950_000_000
        )
    assert contact.observe(ContactFact(
        identity, 'health-restored', 2, False, True
    )).accepted
    value = context(
        lifecycle,
        identity,
        token,
        candidate,
        None,
        contact,
        selected_source=ReceiptSource.SAFE_STOP,
        final_sequence=50,
        source_sequence=15,
        oracle_pose_xy=(0.0, 0.0),
    )
    recovered = committer.commit(value)
    assert recovered.committed, recovered.reason
    assert not recovered.transition.goal_settle_result.success
    assert recovered.transition.termination.reason is None
    assert recovered.transition.reward.terms.terminal == 0.0
    assert lifecycle.snapshot.goal_settle_state.settled_since_ros_ns == (
        next_timestamp
    )

    for step in range(6, 10):
        timestamp = next_timestamp + (step - 5) * 250_000_000
        token, candidate, value = goal_step(step, timestamp)
        result = committer.commit(value)
        assert result.committed, result.reason
    assert result.transition.goal_settle_result.success
    assert result.transition.termination.reason is TerminationReason.GOAL
    assert result.transition.reward.terms.terminal == 15.0


@pytest.mark.parametrize(
    'odometry_status',
    [SimulatedOdometryStatus.DROPPED, SimulatedOdometryStatus.DELAYED],
)
def test_required_source_rejection_before_goal_evaluation_breaks_settle(
    odometry_status,
):
    """Odometry dropout bị bác bỏ vẫn phải ngắt cửa sổ settle hiện tại."""
    lifecycle, identity, first_token, first_candidate = ready_lifecycle()
    contact = ContactLatch()
    contact.reset(identity)
    committer = RLTransitionCommitter(lifecycle)

    def goal_step(step, timestamp, first=False, begin=True):
        token = first_token if first else TransitionIdentity(
            identity, step, f'early-health-{step}'
        )
        provenance = ExactObservationProvenance(
            identity, timestamp, timestamp, timestamp
        )
        binding = lifecycle.snapshot.committed_scenario_session_binding
        base_fact = (
            first_candidate.goal_result.fact if first
            else GoalOracleFact(
                0.0,
                False,
                GoalFactProvenance(
                    GoalFactJoinMode.STEP_TRANSITION,
                    binding,
                    provenance,
                    timestamp,
                    token,
                ),
            )
        )
        fact = replace(
            base_fact,
            goal_distance_m=0.0,
            goal_reached=False,
            provenance=GoalFactProvenance(
                GoalFactJoinMode.STEP_TRANSITION,
                binding,
                provenance,
                timestamp,
                token,
            ),
        )
        if not first and begin:
            lifecycle.begin_step(token)
        candidate = StepCommitCandidate(
            token,
            provenance,
            TaskOracleResult(TaskOracleStatus.READY, fact),
            CommandReceiptSnapshot(
                token,
                f'early-health-receipt-{step}',
                PreviousNormalizedCommand(0.0, 0.0, 0.0),
            ),
        )
        value = context(
            lifecycle,
            identity,
            token,
            candidate,
            None,
            contact,
            selected_source=ReceiptSource.SAFE_STOP,
            final_sequence=step * 10,
            source_sequence=20 + step,
            oracle_pose_xy=(0.0, 0.0),
        )
        return token, candidate, value

    timestamps = (
        1_200_000_000,
        1_450_000_000,
        1_700_000_000,
        1_950_000_000,
    )
    for index, timestamp in enumerate(timestamps):
        _, _, value = goal_step(index + 1, timestamp, first=index == 0)
        result = committer.commit(value)
        assert result.committed, result.reason
    before_gap = lifecycle.snapshot
    assert before_gap.goal_settle_state.settled_since_ros_ns == 1_200_000_000

    token, candidate, valid_at_gap = goal_step(5, 2_050_000_000)
    before_rejection = lifecycle.snapshot
    invalid = _with_unavailable_odometry(valid_at_gap, odometry_status)
    rejected = committer.commit(invalid)
    assert not rejected.committed
    assert rejected.reason == (
        'a bound required observation source lost health'
    )
    after_gap = lifecycle.snapshot
    assert after_gap.reward_baseline == before_rejection.reward_baseline
    assert (
        after_gap.previous_issued_command
        == before_rejection.previous_issued_command
    )
    assert after_gap.task_history == before_rejection.task_history
    assert (
        after_gap.committed_transition_ids
        == before_rejection.committed_transition_ids
    )
    assert after_gap.consumed_receipt_ids == (
        before_rejection.consumed_receipt_ids
    )
    assert after_gap.active_transition_identity == (
        before_rejection.active_transition_identity
    )
    assert contact.state.collision_pulse_pending is False
    assert after_gap.task_health_epoch > after_gap.committed_task_health_epoch

    _, _, recovered_facts = goal_step(
        5, 2_200_000_000, begin=False
    )
    recovered = committer.commit(recovered_facts)
    assert recovered.committed, recovered.reason
    assert not recovered.transition.goal_settle_result.success
    assert recovered.transition.reward.terms.terminal == 0.0
    assert lifecycle.snapshot.goal_settle_state.settled_since_ros_ns == (
        2_200_000_000
    )

    token, candidate, healthy_value = goal_step(6, 2_300_000_000)
    epoch_before_assertions = lifecycle.snapshot.task_health_epoch
    assert not committer.commit(replace(
        healthy_value, expected_task_id='other-task'
    )).committed
    assert lifecycle.snapshot.task_health_epoch == epoch_before_assertions
    bad_reward = replace(
        healthy_value,
        reward=replace(
            healthy_value.reward,
            total=healthy_value.reward.total + 1.0,
        ),
    )
    assert not committer.commit(bad_reward).committed
    assert lifecycle.snapshot.task_health_epoch == epoch_before_assertions
    healthy_retry = committer.commit(healthy_value)
    assert healthy_retry.committed, healthy_retry.reason
    assert not healthy_retry.transition.goal_settle_result.success

    for step, timestamp in zip(
        range(7, 11),
        (2_450_000_000, 2_700_000_000, 2_950_000_000, 3_200_000_000),
        strict=True,
    ):
        _, _, value = goal_step(step, timestamp)
        result = committer.commit(value)
        assert result.committed, result.reason
    assert result.transition.goal_settle_result.success
    assert result.transition.termination.reason is TerminationReason.GOAL


def test_early_required_source_rejection_preserves_contact_pulse():
    """Rejected source gap records continuity without consuming a pulse."""
    lifecycle, identity, token, candidate = ready_lifecycle()
    contact = ContactLatch()
    contact.reset(identity)
    assert contact.observe(ContactFact(
        identity, 'pulse-before-source-gap', 1, True, True
    )).accepted
    value = context(
        lifecycle, identity, token, candidate, None, contact, reason=None
    )
    invalid = _with_unavailable_odometry(
        value, SimulatedOdometryStatus.DROPPED
    )
    lifecycle_before = lifecycle.snapshot
    contact_before = contact.state

    rejected = RLTransitionCommitter(lifecycle).commit(invalid)

    assert not rejected.committed
    lifecycle_after = lifecycle.snapshot
    assert lifecycle_after.reward_baseline == lifecycle_before.reward_baseline
    assert lifecycle_after.task_history == lifecycle_before.task_history
    assert lifecycle_after.committed_transition_ids == (
        lifecycle_before.committed_transition_ids
    )
    assert lifecycle_after.consumed_receipt_ids == (
        lifecycle_before.consumed_receipt_ids
    )
    assert contact.state == contact_before
    assert contact.state.collision_pulse_pending
    assert lifecycle_after.task_health_epoch > (
        lifecycle_after.committed_task_health_epoch
    )


def test_bound_unavailable_reference_records_health_interruption():
    """Reference stale thuộc đúng transition được ghi thành health gap."""
    lifecycle, identity, token, candidate = ready_lifecycle()
    contact = ContactLatch()
    contact.reset(identity)
    value = context(
        lifecycle, identity, token, candidate, None, contact, reason=None
    )
    health = value.goal_sample.health
    stale_received_steady = health.evaluation_steady_now_ns - 250_000_001
    stale_odometry = replace(
        value.noisy_odometry_context,
        received_steady_ns=stale_received_steady,
    )
    binding = value.goal_sample.scenario_session_binding
    stale_reference = build_local_training_reference(
        LocalTrainingGoal(
            value.expected_goal_xy_m[0],
            value.expected_goal_xy_m[1],
            binding.coordinate_reference_id,
            binding.scenario_id,
        ),
        stale_odometry,
        evaluation_ros_now_ns=health.evaluation_ros_now_ns,
        evaluation_steady_now_ns=health.evaluation_steady_now_ns,
        scan_timestamp_ns=value.lifecycle_candidate
        .observation_provenance.odometry_timestamp_ns,
        scan_lifecycle=identity,
        scan_scenario_identity=binding.scenario_id,
    )
    assert not stale_reference.ready
    stale_health = replace(
        health,
        noisy_odometry_valid=False,
        reference_valid=False,
        noisy_odometry_received_steady_ns=stale_received_steady,
        noisy_odom_steady_age_ns=(
            health.evaluation_steady_now_ns - stale_received_steady
        ),
    )
    invalid = replace(
        value,
        noisy_odometry_context=stale_odometry,
        local_reference_result=stale_reference,
        goal_sample=replace(value.goal_sample, health=stale_health),
    )
    before = lifecycle.snapshot

    rejected = RLTransitionCommitter(lifecycle).commit(invalid)

    assert not rejected.committed
    assert rejected.reason == (
        'a bound required observation source lost health'
    )
    after = lifecycle.snapshot
    assert after.reward_baseline == before.reward_baseline
    assert after.task_history == before.task_history
    assert after.committed_transition_ids == before.committed_transition_ids
    assert after.task_health_epoch > after.committed_task_health_epoch


@pytest.mark.parametrize('gap_source', ['contact', 'noisy_odometry'])
def test_required_health_gap_clears_committed_stuck_trajectory(gap_source):
    """STUCK không nối trajectory qua health gap của nguồn bắt buộc."""
    lifecycle, identity, first_token, first_candidate = ready_lifecycle()
    contact = ContactLatch()
    contact.reset(identity)
    committer = RLTransitionCommitter(lifecycle)

    def stuck_step(step, timestamp, first=False, begin=True):
        if first:
            token = first_token
            provenance = ExactObservationProvenance(
                identity, timestamp, timestamp, timestamp
            )
            fact = first_candidate.goal_result.fact
            candidate = replace(
                first_candidate,
                observation_provenance=provenance,
                goal_result=TaskOracleResult(TaskOracleStatus.READY, replace(
                    fact,
                    goal_distance_m=1.0,
                    goal_reached=False,
                    provenance=GoalFactProvenance(
                        GoalFactJoinMode.STEP_TRANSITION,
                        lifecycle.snapshot.committed_scenario_session_binding,
                        provenance,
                        timestamp,
                        token,
                    ),
                )),
            )
        else:
            token = TransitionIdentity(identity, step, f'stuck-step-{step}')
            if begin:
                lifecycle.begin_step(token)
            provenance = ExactObservationProvenance(
                identity, timestamp, timestamp, timestamp
            )
            candidate = StepCommitCandidate(
                token,
                provenance,
                TaskOracleResult(TaskOracleStatus.READY, GoalOracleFact(
                    1.0,
                    False,
                    GoalFactProvenance(
                        GoalFactJoinMode.STEP_TRANSITION,
                        lifecycle.snapshot.committed_scenario_session_binding,
                        provenance,
                        timestamp,
                        token,
                    ),
                )),
                CommandReceiptSnapshot(
                    token,
                    f'stuck-candidate-{step}',
                    PreviousNormalizedCommand(0.0, 0.0, 0.0),
                ),
            )
        return context(
            lifecycle,
            identity,
            token,
            candidate,
            None,
            contact,
            selected_source=ReceiptSource.SAFE_STOP,
            final_sequence=step * 10,
            source_sequence=100 + step,
            oracle_pose_xy=(-1.0, 0.0),
        )

    for step in range(1, 41):
        timestamp = 1_200_000_000 + (step - 1) * 250_000_000
        value = stuck_step(step, timestamp, first=(step == 1))
        result = committer.commit(value)
        assert result.committed, result.reason
        assert result.transition.termination.reason is None
    assert lifecycle.snapshot.task_history[0].ros_time_ns <= 1_200_000_000

    value = stuck_step(41, 11_200_000_000)
    if gap_source == 'contact':
        assert not contact.observe(ContactFact(
            identity, 'stuck-health-loss', 1, False, False
        )).accepted
        assert contact.observe(ContactFact(
            identity, 'stuck-health-restored', 2, False, True
        )).accepted
        value = context(
            lifecycle,
            identity,
            value.transition_identity,
            value.lifecycle_candidate,
            None,
            contact,
            selected_source=ReceiptSource.SAFE_STOP,
            final_sequence=410,
            source_sequence=141,
            oracle_pose_xy=(-1.0, 0.0),
        )
    else:
        before_gap = lifecycle.snapshot
        rejected = committer.commit(_with_unavailable_odometry(
            value, SimulatedOdometryStatus.DROPPED
        ))
        assert not rejected.committed
        after_gap = lifecycle.snapshot
        assert after_gap.reward_baseline == before_gap.reward_baseline
        assert after_gap.task_history == before_gap.task_history
        assert after_gap.committed_transition_ids == (
            before_gap.committed_transition_ids
        )
        assert after_gap.task_health_epoch > (
            after_gap.committed_task_health_epoch
        )
        value = stuck_step(
            41, 11_200_000_000, begin=False
        )

    recovered = committer.commit(value)

    assert recovered.committed, recovered.reason
    assert recovered.transition.termination.reason is None
    assert recovered.transition.reward.terms.terminal == 0.0
    assert tuple(
        sample.ros_time_ns for sample in lifecycle.snapshot.task_history
    ) == (11_200_000_000,)


def test_forged_goal_termination_and_reward_reject_without_commit():
    """Không chấp nhận goal hoặc reward terminal bị caller giả."""
    lifecycle, identity, token, candidate = ready_lifecycle()
    contact = ContactLatch()
    contact.reset(identity)
    value = context(
        lifecycle, identity, token, candidate, None, contact, reason=None
    )
    forged_candidate = replace(
        value.lifecycle_candidate,
        committed_state=EpisodeLifecycleState.TERMINATED,
    )
    forged = replace(
        value,
        lifecycle_candidate=forged_candidate,
        termination=TerminationResult(
            True, False, TerminationReason.GOAL, False
        ),
        reward=RewardManager().compute(TransitionRewardInput(
            2.0, 1.9, value.clearance_m, 0.2, value.command_history,
            (0.0, 0.0, 0.0), goal=True,
        )),
    )
    before = lifecycle.snapshot
    contact_before = contact.state
    rejected = RLTransitionCommitter(lifecycle).commit(forged)
    assert not rejected.committed
    assert lifecycle.snapshot == before
    assert contact.state == contact_before


@pytest.mark.parametrize(
    ('field', 'replacement'),
    [
        ('goal_id', 'another-goal'),
        ('goal_xy_m', (1.0, 0.0)),
        ('task_id', 'another-task'),
        ('session_id', 'another-session'),
    ],
)
def test_reward_rejects_task_goal_changed_since_reset_baseline(
    field, replacement
):
    """Không dùng baseline reset cho task, session hoặc goal khác."""
    lifecycle, identity, token, candidate = ready_lifecycle()
    contact = ContactLatch()
    contact.reset(identity)
    contact.observe(ContactFact(identity, 'kept-pulse', 1, True, True))
    changed_goal = context(
        lifecycle,
        identity,
        token,
        candidate,
        None,
        contact,
        reason=None,
        **{field: replacement},
    )
    before = lifecycle.snapshot
    contact_before = contact.state

    result = RLTransitionCommitter(lifecycle).commit(changed_goal)

    assert not result.committed
    assert lifecycle.snapshot == before
    assert contact.state == contact_before


def test_reset_bound_goal_facts_seed_the_first_reward_baseline():
    """First-step reward dùng đúng task-goal binding tại reset."""
    lifecycle, identity, token, candidate = ready_lifecycle()
    baseline = lifecycle.snapshot.reward_baseline
    assert baseline is not None
    assert (
        baseline.task_id,
        baseline.session_id,
        baseline.goal_id,
        baseline.goal_xy_m,
    ) == ('task', 'session', 'goal', (0.0, 0.0))
    contact = ContactLatch()
    contact.reset(identity)
    first = context(
        lifecycle, identity, token, candidate, None, contact, reason=None
    )

    result = RLTransitionCommitter(lifecycle).commit(first)

    assert result.committed
    assert result.transition.reward.baseline_distance_m == 2.0
    assert result.transition.reward.terms.progress == pytest.approx(0.2)


def test_twist_features_are_recomputed_from_selected_noisy_measurement():
    """Không chấp nhận twist zero giả khi noisy odometry đo vx khác zero."""
    lifecycle, identity, token, candidate = ready_lifecycle()
    contact = ContactLatch()
    contact.reset(identity)
    value = context(
        lifecycle, identity, token, candidate, None, contact, reason=None,
        measured_twist=(0.05, 0.0, 0.0),
        twist_features_override=(0.0, 0.0, 0.0),
    )
    before = lifecycle.snapshot

    result = RLTransitionCommitter(lifecycle).commit(value)

    assert not result.committed
    assert lifecycle.snapshot == before


def test_valid_lateral_twist_is_recomputed_from_selected_v3_scales():
    """Giữ vy và tính V3 measured twist theo scales đã chọn."""
    lifecycle, identity, token, candidate = ready_lifecycle()
    contact = ContactLatch()
    contact.reset(identity)
    value = context(
        lifecycle, identity, token, candidate, None, contact, reason=None,
        measured_twist=(0.0, 0.1, 0.0),
    )

    result = RLTransitionCommitter(lifecycle).commit(value)

    assert result.committed
    assert result.transition.observation[75:78].tolist() == [0.0, 0.5, 0.0]


def test_wrong_measured_twist_normalization_is_rejected():
    """Từ chối result không khớp scale V3 của cutoff selection."""
    lifecycle, identity, token, candidate = ready_lifecycle()
    contact = ContactLatch()
    contact.reset(identity)
    value = context(
        lifecycle, identity, token, candidate, None, contact, reason=None,
        measured_twist=(0.05, 0.0, 0.0),
        twist_features_override=(0.1, 0.0, 0.0),
    )
    before = lifecycle.snapshot

    result = RLTransitionCommitter(lifecycle).commit(value)

    assert not result.committed
    assert lifecycle.snapshot == before


@pytest.mark.parametrize('corruption', ['same_sequence', 'pre_action_barrier'])
def test_policy_issuance_proof_must_match_cutoff_publication_and_barrier(
    corruption,
):
    """Không nhận POLICY proof xung đột với STOP hoặc trước action barrier."""
    lifecycle, identity, token, candidate = ready_lifecycle()
    contact = ContactLatch()
    contact.reset(identity)
    value = context(
        lifecycle, identity, token, candidate, None, contact,
        selected_source=ReceiptSource.SAFE_STOP, reason=None,
    )
    selected = value.cutoff_selection.receipt
    if corruption == 'same_sequence':
        bad_proof = replace(
            value.policy_issuance_receipt,
            final_publish_sequence=selected.final_publish_sequence,
        )
        value = replace(value, policy_issuance_receipt=bad_proof)
    else:
        barrier = value.policy_issuance_receipt.publish_stamp_ns
        value = replace(
            value,
            cutoff_selection=replace(
                value.cutoff_selection, action_barrier_ros_ns=barrier
            ),
        )
    before = lifecycle.snapshot
    contact_before = contact.state

    result = RLTransitionCommitter(lifecycle).commit(value)

    assert not result.committed
    assert lifecycle.snapshot == before
    assert contact.state == contact_before
    assert contact.state == contact_before
    assert lifecycle.snapshot.goal_settle_state is None
    assert lifecycle.snapshot.task_history == ()


def test_wrong_v3_final_command_tail_rejects_without_mutation():
    """Từ chối observation có command tail khác receipt."""
    lifecycle, identity, token, candidate = ready_lifecycle()
    contact = ContactLatch()
    contact.reset(identity)
    contact.observe(ContactFact(identity, 'pulse', 1, True, True))
    source = _valid_v3_observation(identity, (0.1, 0.2, 0.3)).copy()
    source[78] = 0.0
    before = lifecycle.snapshot
    result = RLTransitionCommitter(lifecycle).commit(
        context(lifecycle, identity, token, candidate, source, contact))
    assert not result.committed
    assert lifecycle.snapshot == before
    assert contact.state.collision_pulse_pending


@pytest.mark.parametrize('change', ['info', 'receipt', 'history', 'terminal'])
def test_each_precommit_contract_failure_leaves_all_state_unchanged(change):
    """Giữ nguyên state khi contract đầu vào không hợp lệ."""
    lifecycle, identity, token, candidate = ready_lifecycle()
    contact = ContactLatch()
    contact.reset(identity)
    contact.observe(ContactFact(identity, 'pulse', 1, True, True))
    observation = _valid_v3_observation(identity, (0.1, 0.2, 0.3))
    value = context(
        lifecycle, identity, token, candidate, observation, contact
    )
    if change == 'info':
        value = replace(value, info=(('step', 1), ('step', 2)))
    elif change == 'receipt':
        value = replace(value, issued_receipt_id='different')
    elif change == 'history':
        value = replace(value, command_history=(0, 0, 0))
    elif change == 'terminal':
        value = replace(
            value, termination=TerminationResult(False, False, None, False)
        )
    before = lifecycle.snapshot
    result = RLTransitionCommitter(lifecycle).commit(value)
    assert not result.committed
    assert (
        lifecycle.snapshot == before
        and contact.state.collision_pulse_pending
    )


def test_clean_subprocess_import_has_no_ros_gazebo_gym_sb3_or_torch_modules():
    """Xác nhận import pure-core không nạp runtime dependencies."""
    code = (
        'import sys; '
        'from mecanum_nav_rl.core.issued_command_cutoff import *; '
        'from mecanum_nav_rl.core.episode_lifecycle import *; '
        'from mecanum_nav_rl.core.rl_transition import *; '
        'from mecanum_nav_rl.observations.local_training_reference import *; '
        'from mecanum_nav_rl.observations.v3_observation_assembler import *; '
        'from mecanum_nav_rl.rewards.manager import *; '
        'from mecanum_nav_rl.termination.manager import *; '
        'from mecanum_nav_rl.tasks.training_task_oracle import *; '
        'from mecanum_nav_rl.simulation.simulated_odometry import *; '
        'from mecanum_nav_rl.actions.ppo_decoder import *; '
        "forbidden=('rclpy','geometry_msgs','sensor_msgs','nav_msgs','gazebo',"
        "'gz','gymnasium','stable_baselines3','torch'); "
        'assert not any(any(name==root or name.startswith(root+".") '
        'for root in forbidden) for name in sys.modules)'
    )
    package_root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, '-c', code], cwd=package_root,
        capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr
