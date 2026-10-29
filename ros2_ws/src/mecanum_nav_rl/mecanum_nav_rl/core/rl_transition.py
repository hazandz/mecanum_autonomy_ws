"""Atomic B1 transaction joining observation, reward, terminal and histories."""
from __future__ import annotations
from dataclasses import dataclass
from threading import RLock
import numpy as np
from mecanum_nav_rl.core.episode_lifecycle import EpisodeLifecycle, EpisodeLifecycleResult, EpisodeLifecycleState, EpisodeOperationStatus, StepCommitCandidate
from mecanum_nav_rl.core.issued_command_cutoff import CutoffSelection, CutoffStatus
from mecanum_nav_rl.core.lifecycle_types import TransitionIdentity
from mecanum_nav_rl.rewards.manager import RewardResult
from mecanum_nav_rl.simulation.contact_latch import ContactLatch
from mecanum_nav_rl.termination.manager import TerminationResult
from mecanum_nav_rl.termination.manager import TerminationReason

@dataclass(frozen=True, slots=True)

class RLTransitionContext:
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

@dataclass(frozen=True, slots=True)

class CommittedRLTransition:
    transition_identity: TransitionIdentity
    observation: np.ndarray
    reward: RewardResult
    termination: TerminationResult
    info: tuple[tuple[str, str | int | float | bool], ...]
    issued_receipt_id: str
    command_history: tuple[float, float, float]
    lifecycle_result: EpisodeLifecycleResult

@dataclass(frozen=True, slots=True)

class TransitionCommitResult:
    committed: bool
    transition: CommittedRLTransition | None
    reason: str | None = None

class RLTransitionCommitter:
    """Prepare every B1 value before delegating the single lifecycle commit."""

    def __init__(self, lifecycle: EpisodeLifecycle) -> None:
        if not isinstance(lifecycle, EpisodeLifecycle):
            raise TypeError('lifecycle must be EpisodeLifecycle')
        self._lifecycle = lifecycle
        self._lock = RLock()
        self._committed: tuple[CommittedRLTransition, ...] = ()

    @property
    def committed(self) -> tuple[CommittedRLTransition, ...]:
        return self._committed

    def commit(self, context: RLTransitionContext) -> TransitionCommitResult:
        """Return a rejection without state changes when any fact is invalid."""
        with self._lock:
            if isinstance(context,
                RLTransitionContext) and any((old.transition_identity == context.transition_identity for old in self._committed)):
                return TransitionCommitResult(False, None,
                    'transition was already committed')
            try:
                prepared = self._prepare(context,
                    self._lifecycle.snapshot.reward_baseline)
            except (TypeError, ValueError, OverflowError) as error:
                return TransitionCommitResult(False, None, str(error))
            if not prepared.contact_latch.can_commit_transition(prepared.contact_transition_id, prepared.transition_identity.identity):
                return TransitionCommitResult(False, None,
                    'contact pulse cannot be consumed for this transition')
            lifecycle_result = self._lifecycle.commit_step(context.lifecycle_candidate)
            if lifecycle_result.status is not EpisodeOperationStatus.STEP_COMMITTED:
                return TransitionCommitResult(False, None,
                    lifecycle_result.reason or 'lifecycle rejected commit')
            contact_result = prepared.contact_latch.commit_transition(prepared.contact_transition_id, prepared.transition_identity.identity)
            if not contact_result.accepted:
                raise RuntimeError('contact state changed during atomic commit')
            committed = CommittedRLTransition(prepared.transition_identity,
                prepared.observation, prepared.reward, prepared.termination, prepared.info, prepared.issued_receipt_id, prepared.command_history, lifecycle_result)
            self._committed = (*self._committed, committed)
            return TransitionCommitResult(True, committed)

    @staticmethod
    def _prepare(context: RLTransitionContext,
        reward_baseline: object) -> RLTransitionContext:
        if not isinstance(context, RLTransitionContext):
            raise TypeError('context must be RLTransitionContext')
        if not isinstance(context.transition_identity, TransitionIdentity):
            raise TypeError('transition identity is required')
        if not isinstance(context.lifecycle_candidate, StepCommitCandidate):
            raise TypeError('lifecycle candidate is required')
        if context.lifecycle_candidate.transition_identity != context.transition_identity:
            raise ValueError('lifecycle candidate identity differs from transition')
        observation = context.observation
        if type(observation) is not np.ndarray or observation.shape != (81,
            ) or observation.dtype != np.float32:
            raise ValueError('observation must be float32[81]')
        if not bool(np.isfinite(observation).all()):
            raise ValueError('observation must be finite')
        copied = np.array(observation, dtype=np.float32, copy=True)
        copied.setflags(write=False)
        if not isinstance(context.reward,
            RewardResult) or not isinstance(context.termination, TerminationResult):
            raise TypeError('reward and termination must be complete typed results')
        if not isinstance(context.lifecycle_candidate.committed_state,
            EpisodeLifecycleState):
            raise TypeError('lifecycle committed_state must be typed')
        expected_state = 'TERMINATED' if context.termination.terminated else 'TRUNCATED' if context.termination.truncated else 'RUNNING'
        if context.lifecycle_candidate.committed_state.value.upper() != expected_state:
            raise ValueError('lifecycle state does not match termination flags')
        receipt = context.lifecycle_candidate.command_receipt
        if context.issued_receipt_id != receipt.receipt_id:
            raise ValueError('transition receipt does not match lifecycle candidate')
        if not isinstance(context.cutoff_selection,
            CutoffSelection) or context.cutoff_selection.status is not CutoffStatus.READY:
            raise ValueError('transition requires a ready receipt cutoff selection')
        selected = context.cutoff_selection.receipt
        if selected is None or context.cutoff_selection.normalized_command is None:
            raise ValueError('ready cutoff selection is incomplete')
        if selected.receipt_key != receipt.receipt_id or selected.lifecycle != context.transition_identity.identity or selected.step_index != context.transition_identity.step_index or (selected.transition_id != context.transition_identity.transition_id):
            raise ValueError('selected receipt does not bind this lifecycle step')
        expected_terminal = -15.0 if context.termination.reason is TerminationReason.COLLISION else 15.0 if context.termination.reason is TerminationReason.GOAL else -3.0 if context.termination.reason is TerminationReason.STUCK else 0.0
        if context.reward.terms.terminal != expected_terminal:
            raise ValueError('reward terminal term does not match termination reason')
        if type(context.info) is not tuple or any((type(item) is not tuple or len(item) != 2 for item in context.info)):
            raise TypeError('info must be an immutable tuple of key/value pairs')
        keys = tuple((pair[0] for pair in context.info))
        if any((type(key) is not str or not key for key in keys)) or len(set(keys)) != len(keys):
            raise ValueError('info keys must be unique non-empty strings')
        if type(context.issued_receipt_id) is not str or not context.issued_receipt_id:
            raise ValueError('issued receipt identity is required')
        if type(context.command_history) is not tuple or len(context.command_history) != 3:
            raise ValueError('command history must be a three-value tuple')
        command = tuple((float(value) for value in context.command_history))
        if any((not np.isfinite(value) or value < -1.0 or value > 1.0 for value in command)):
            raise ValueError('command history must be normalized final-issued values')
        if context.contact_transition_id != context.transition_identity.transition_id:
            raise ValueError('contact consumption must use this transition identity')
        if not isinstance(context.contact_latch, ContactLatch):
            raise TypeError('transition commit requires ContactLatch state')
        collision_active = context.contact_latch.state.contact_active or context.contact_latch.state.collision_pulse_pending
        if (context.termination.reason is TerminationReason.COLLISION) != collision_active:
            raise ValueError('collision termination must match latched contact state')
        if context.command_history != (receipt.final_issued_command.vx,
            receipt.final_issued_command.vy, receipt.final_issued_command.wz):
            raise ValueError('command history must equal final-issued receipt payload')
        if any((abs(selected_value - history_value) > 1e-12 for selected_value,
            history_value in zip(context.cutoff_selection.normalized_command,
            context.command_history, strict=True))):
            raise ValueError('command history must come from selected cutoff receipt')
        goal_result = context.lifecycle_candidate.goal_result
        goal_fact = getattr(goal_result, 'fact', None)
        if goal_fact is None or reward_baseline is None:
            raise ValueError('transition reward baseline is incomplete')
        if context.reward.baseline_distance_m != reward_baseline.previous_goal_distance_m:
            raise ValueError('reward previous distance differs from committed baseline')
        expected_progress = min(1.0, max(-1.0,
            2.0 * (reward_baseline.previous_goal_distance_m - goal_fact.goal_distance_m)))
        if context.reward.terms.progress != expected_progress:
            raise ValueError('reward progress term does not match exact oracle facts')
        return RLTransitionContext(context.transition_identity,
            context.lifecycle_candidate, copied, context.reward, context.termination, context.info, context.issued_receipt_id, context.cutoff_selection, command, context.contact_transition_id, context.contact_latch)
__all__ = ('CommittedRLTransition', 'RLTransitionCommitter',
    'RLTransitionContext', 'TransitionCommitResult')
