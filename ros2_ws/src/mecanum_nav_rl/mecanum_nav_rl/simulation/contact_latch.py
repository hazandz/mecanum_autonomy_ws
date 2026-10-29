"""Pure contact active/pulse state; silence is not an empty fact."""

from __future__ import annotations

from dataclasses import dataclass

from mecanum_nav_rl.core.lifecycle_types import (
    CORE_TRANSACTION_LOCK,
    EpisodeLifecycleIdentity,
)


@dataclass(frozen=True, slots=True)
class ContactFact:
    """Copied contact event with lifecycle and monotonic source ordering."""

    lifecycle: EpisodeLifecycleIdentity
    event_id: str
    event_sequence: int
    contact_active: bool
    source_healthy: bool

    def __post_init__(self) -> None:
        """Reject malformed event identities, order, and health flags."""
        if not isinstance(self.lifecycle, EpisodeLifecycleIdentity):
            raise TypeError('lifecycle must be EpisodeLifecycleIdentity')
        if type(self.event_id) is not str or not self.event_id:
            raise ValueError('event_id must be non-empty')
        if type(self.event_sequence) is not int or self.event_sequence <= 0:
            raise ValueError(
                'event_sequence must be a positive source sequence'
            )
        if (
            type(self.contact_active) is not bool
            or type(self.source_healthy) is not bool
        ):
            raise TypeError('contact state and source health must be bool')


@dataclass(frozen=True, slots=True)
class ContactLatchState:
    """Immutable contact, pending pulse, and bounded event watermarks."""

    lifecycle: EpisodeLifecycleIdentity | None = None
    contact_active: bool = False
    collision_pulse_pending: bool = False
    last_event_id: str | None = None
    consumed_transition_ids: tuple[str, ...] = ()
    last_event_sequence: int = 0
    seen_event_ids: tuple[str, ...] = ()
    source_healthy: bool | None = None
    health_epoch: int = 0


@dataclass(frozen=True, slots=True)
class ContactLatchResult:
    """Contact admission or consumption result and immutable state snapshot."""

    accepted: bool
    state: ContactLatchState
    reason: str | None = None


class ContactLatch:
    """Deterministic contact state consumed only by committed transitions."""

    def __init__(self) -> None:
        """Create an unbound contact latch."""
        self._state = ContactLatchState()

    @property
    def state(self) -> ContactLatchState:
        """Return a synchronized immutable state snapshot."""
        with CORE_TRANSACTION_LOCK:
            return self._state

    def reset(self, lifecycle: EpisodeLifecycleIdentity) -> ContactLatchState:
        """Bind a new lifecycle and clear all previous contact state."""
        if not isinstance(lifecycle, EpisodeLifecycleIdentity):
            raise TypeError('lifecycle must be EpisodeLifecycleIdentity')
        with CORE_TRANSACTION_LOCK:
            self._state = ContactLatchState(lifecycle=lifecycle)
            return self._state

    def observe(self, fact: ContactFact) -> ContactLatchResult:
        """Admit a newer healthy fact or retain the pulse on a health loss."""
        with CORE_TRANSACTION_LOCK:
            if not isinstance(fact, ContactFact):
                return ContactLatchResult(
                    False, self._state, 'invalid contact fact'
                )
            state = self._state
            if state.lifecycle is None or fact.lifecycle != state.lifecycle:
                return ContactLatchResult(
                    False, state, 'contact lifecycle is stale or unbound'
                )
            if fact.event_id in state.seen_event_ids:
                return ContactLatchResult(
                    False, state, 'replayed contact event rejected'
                )
            if fact.event_sequence <= state.last_event_sequence:
                return ContactLatchResult(
                    False, state, 'contact event sequence is stale'
                )
            seen = (*state.seen_event_ids, fact.event_id)[-256:]
            if not fact.source_healthy:
                state = ContactLatchState(
                    lifecycle=state.lifecycle,
                    contact_active=state.contact_active,
                    collision_pulse_pending=state.collision_pulse_pending,
                    last_event_id=fact.event_id,
                    consumed_transition_ids=state.consumed_transition_ids,
                    last_event_sequence=fact.event_sequence,
                    seen_event_ids=seen,
                    source_healthy=False,
                    health_epoch=state.health_epoch + 1,
                )
                self._state = state
                return ContactLatchResult(
                    False, state, 'contact source is unhealthy'
                )
            if fact.contact_active:
                state = ContactLatchState(
                    lifecycle=fact.lifecycle,
                    contact_active=True,
                    collision_pulse_pending=True,
                    last_event_id=fact.event_id,
                    consumed_transition_ids=state.consumed_transition_ids,
                    last_event_sequence=fact.event_sequence,
                    seen_event_ids=seen,
                    source_healthy=True,
                    health_epoch=state.health_epoch,
                )
            else:
                state = ContactLatchState(
                    lifecycle=fact.lifecycle,
                    contact_active=False,
                    collision_pulse_pending=state.collision_pulse_pending,
                    last_event_id=fact.event_id,
                    consumed_transition_ids=state.consumed_transition_ids,
                    last_event_sequence=fact.event_sequence,
                    seen_event_ids=seen,
                    source_healthy=True,
                    health_epoch=state.health_epoch,
                )
            self._state = state
            return ContactLatchResult(True, state)

    def commit_transition(
        self, transition_id: str, lifecycle: EpisodeLifecycleIdentity
    ) -> ContactLatchResult:
        """Consume one pending pulse while preserving sustained contact."""
        with CORE_TRANSACTION_LOCK:
            state = self._state
            if type(transition_id) is not str or not transition_id:
                return ContactLatchResult(
                    False, state, 'transition_id must be non-empty'
                )
            if lifecycle != state.lifecycle:
                return ContactLatchResult(
                    False, state, 'transition lifecycle does not match contact'
                )
            if state.source_healthy is False:
                return ContactLatchResult(
                    False, state,
                    'contact source health is not valid for commit'
                )
            if transition_id in state.consumed_transition_ids:
                return ContactLatchResult(
                    False, state, 'transition already consumed contact pulse'
                )
            next_state = ContactLatchState(
                lifecycle=state.lifecycle,
                contact_active=state.contact_active,
                collision_pulse_pending=False,
                last_event_id=state.last_event_id,
                consumed_transition_ids=(
                    *state.consumed_transition_ids, transition_id
                ),
                last_event_sequence=state.last_event_sequence,
                seen_event_ids=state.seen_event_ids,
                source_healthy=state.source_healthy,
                health_epoch=state.health_epoch,
            )
            self._state = next_state
            return ContactLatchResult(True, next_state)

    def can_commit_transition(
        self, transition_id: str, lifecycle: EpisodeLifecycleIdentity
    ) -> bool:
        """Report whether shared contact state admits this transition."""
        with CORE_TRANSACTION_LOCK:
            state = self._state
            return (
                type(transition_id) is str
                and bool(transition_id)
                and lifecycle == state.lifecycle
                and state.source_healthy is not False
                and transition_id not in state.consumed_transition_ids
            )


__all__ = (
    'ContactFact',
    'ContactLatch',
    'ContactLatchResult',
    'ContactLatchState',
)
