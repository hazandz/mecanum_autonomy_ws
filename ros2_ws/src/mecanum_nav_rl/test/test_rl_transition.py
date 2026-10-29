import numpy as np
from dataclasses import replace
import subprocess
import sys
from pathlib import Path
from mecanum_nav_rl.core.episode_lifecycle import CommandReceiptSnapshot, EpisodeLifecycle, EpisodeOperationStatus, EpisodeLifecycleState, ResetCommitCandidate, ResetZeroReceipt, StepCommitCandidate
from mecanum_nav_rl.core.issued_command_cutoff import IssuedCommandReceiptView, PolicyActionIssuance, ReceiptSource, ReceiptStreamBinding, select_final_issued_at_cutoff
from mecanum_nav_rl.core.goal_facts import GoalFactJoinMode, GoalFactProvenance, GoalOracleFact, TaskOracleResult, TaskOracleStatus
from mecanum_nav_rl.core.lifecycle_types import EpisodeLifecycleIdentity, ExactObservationProvenance, TransitionIdentity
from mecanum_nav_rl.core.rl_transition import RLTransitionCommitter, RLTransitionContext
from mecanum_nav_rl.core.scenario_session import ScenarioSessionBinding
from mecanum_nav_rl.observations.previous_command import PreviousNormalizedCommand
from mecanum_nav_rl.rewards.manager import RewardManager, TransitionRewardInput
from mecanum_nav_rl.simulation.contact_latch import ContactFact, ContactLatch
from mecanum_nav_rl.termination.manager import TerminationReason, TerminationResult
import pytest

def ready_lifecycle():
    identity = EpisodeLifecycleIdentity(1, 1, 1)
    binding = ScenarioSessionBinding(identity, 'scenario', '1', 'a' * 64,
        'world', 'b' * 64, 'local-frame')
    lifecycle = EpisodeLifecycle()
    lifecycle.begin_reset(identity, binding)
    lifecycle.wait_for_initial_observation(identity)
    provenance = ExactObservationProvenance(identity, 100, 100, 100)
    reset_fact = GoalOracleFact(2.0, False,
        GoalFactProvenance(GoalFactJoinMode.RESET_OBSERVATION0, binding,
        provenance, 100, None))
    lifecycle.commit_reset(ResetCommitCandidate(identity, provenance,
        TaskOracleResult(TaskOracleStatus.READY,
        reset_fact), PreviousNormalizedCommand(0, 0, 0), 0, ResetZeroReceipt('zero', identity, 50, 'SAFE_STOP', PreviousNormalizedCommand(0, 0, 0))))
    token = TransitionIdentity(identity, 1, 'transition-1')
    lifecycle.begin_step(token)
    next_provenance = ExactObservationProvenance(identity, 200, 200, 200)
    next_fact = GoalOracleFact(1.9, False,
        GoalFactProvenance(GoalFactJoinMode.STEP_TRANSITION, binding,
        next_provenance, 200, token))
    candidate = StepCommitCandidate(token, next_provenance,
        TaskOracleResult(TaskOracleStatus.READY,
        next_fact), CommandReceiptSnapshot(token, '90:1', PreviousNormalizedCommand(0.1, 0.2, 0.3)))
    return (lifecycle, identity, token, candidate)

def context(lifecycle, identity, token, candidate, observation, contact):
    candidate = replace(candidate,
        committed_state=EpisodeLifecycleState.TERMINATED)
    reward = RewardManager().compute(TransitionRewardInput(2, 1.9, 0.5, 0.1,
        (0.1, 0.2, 0.3), (0, 0, 0), collision=True))
    binding = ReceiptStreamBinding(90, 'session', 'a' * 64, identity)
    policy = IssuedCommandReceiptView(200, 90, 1, ReceiptSource.POLICY, 7, 11,
        1, token.transition_id, identity, 'session', 'a' * 64, (0.025, 0.04,
        0.24))
    trailing = IssuedCommandReceiptView(201, 90, 2, ReceiptSource.SAFE_STOP, 8,
        1, 1, token.transition_id, identity, 'session', 'a' * 64, (0, 0, 0))
    selection = select_final_issued_at_cutoff((policy, trailing),
        binding=binding, issuance=PolicyActionIssuance(7, 11, identity, 1,
        token.transition_id), cutoff_ros_ns=200, evaluation_ros_now_ns=201, physical_scales=(0.25, 0.2, 0.8))
    return RLTransitionContext(token, candidate, observation, reward,
        TerminationResult(True, False, TerminationReason.COLLISION,
        False), (('step',
        1),), '90:1', selection, (0.1, 0.2, 0.3), token.transition_id, contact)

def test_atomic_commit_copies_observation_and_commits_full_tuple_once():
    lifecycle, identity, token, candidate = ready_lifecycle()
    contact = ContactLatch()
    contact.reset(identity)
    contact.observe(ContactFact(identity, 'collision-pulse', True, True))
    source = np.arange(81, dtype=np.float32)
    committer = RLTransitionCommitter(lifecycle)
    result = committer.commit(context(lifecycle, identity, token, candidate,
        source, contact))
    assert result.committed and result.transition is not None
    assert result.transition.lifecycle_result.status is EpisodeOperationStatus.STEP_COMMITTED
    assert not result.transition.observation.flags.writeable
    source[0] = 999
    assert result.transition.observation[0] == 0
    assert contact.state.contact_active and (not contact.state.collision_pulse_pending)
    assert committer.commit(context(lifecycle, identity, token, candidate,
        source, contact)).reason == 'transition was already committed'

def test_invalid_prepare_keeps_baseline_history_and_contact_pulse_untouched():
    lifecycle, identity, token, candidate = ready_lifecycle()
    contact = ContactLatch()
    contact.reset(identity)
    contact.observe(ContactFact(identity, 'pulse', True, True))
    before = lifecycle.snapshot
    committer = RLTransitionCommitter(lifecycle)
    invalid = np.full(80, 0, dtype=np.float32)
    result = committer.commit(context(lifecycle, identity, token, candidate,
        invalid, contact))
    assert not result.committed and 'float32[81]' in result.reason
    assert lifecycle.snapshot == before and contact.state.collision_pulse_pending
    assert committer.committed == ()

@pytest.mark.parametrize('change', ['info', 'receipt', 'history', 'terminal'])

def test_each_precommit_contract_failure_leaves_all_state_unchanged(change):
    lifecycle, identity, token, candidate = ready_lifecycle()
    contact = ContactLatch()
    contact.reset(identity)
    contact.observe(ContactFact(identity, 'pulse', True, True))
    observation = np.zeros(81, dtype=np.float32)
    value = context(lifecycle, identity, token, candidate, observation,
        contact)
    if change == 'info':
        value = replace(value, info=(('step', 1), ('step', 2)))
    elif change == 'receipt':
        value = replace(value, issued_receipt_id='different')
    elif change == 'history':
        value = replace(value, command_history=(0, 0, 0))
    elif change == 'terminal':
        value = replace(value, termination=TerminationResult(False, False,
            None, False))
    before = lifecycle.snapshot
    result = RLTransitionCommitter(lifecycle).commit(value)
    assert not result.committed
    assert lifecycle.snapshot == before and contact.state.collision_pulse_pending

def test_clean_subprocess_import_has_no_ros_gazebo_gym_sb3_or_torch_modules():
    code = "import sys; from mecanum_nav_rl.core.issued_command_cutoff import *; from mecanum_nav_rl.core.episode_lifecycle import *; from mecanum_nav_rl.core.rl_transition import *; from mecanum_nav_rl.observations.local_training_reference import *; from mecanum_nav_rl.observations.v3_observation_assembler import *; from mecanum_nav_rl.rewards.manager import *; from mecanum_nav_rl.termination.manager import *; from mecanum_nav_rl.tasks.training_task_oracle import *; from mecanum_nav_rl.simulation.simulated_odometry import *; from mecanum_nav_rl.actions.ppo_decoder import *; forbidden=('rclpy','geometry_msgs','sensor_msgs','nav_msgs','gazebo','gz','gymnasium','stable_baselines3','torch'); assert not any(any(name==root or name.startswith(root+'.') for root in forbidden) for name in sys.modules)"
    package_root = Path(__file__).resolve().parents[1]
    result = subprocess.run([sys.executable, '-c', code], cwd=package_root,
        capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
