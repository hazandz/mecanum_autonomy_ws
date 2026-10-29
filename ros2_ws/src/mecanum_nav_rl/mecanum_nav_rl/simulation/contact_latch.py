"""Pure contact active/pulse state; silence is not an empty-contact fact."""
from __future__ import annotations
from dataclasses import dataclass
from mecanum_nav_rl.core.lifecycle_types import EpisodeLifecycleIdentity

@dataclass(frozen=True, slots=True)

class ContactFact:
    lifecycle: EpisodeLifecycleIdentity
    event_id: str
    contact_active: bool
    source_healthy: bool

    def __post_init__(self) -> None:
        if not isinstance(self.lifecycle, EpisodeLifecycleIdentity):
            raise TypeError('lifecycle must be EpisodeLifecycleIdentity')
        if type(self.event_id) is not str or not self.event_id:
            raise ValueError('event_id must be non-empty')
        if type(self.contact_active) is not bool or type(self.source_healthy) is not bool:
            raise TypeError('contact state and source health must be bool')

@dataclass(frozen=True, slots=True)

class ContactLatchState:
    lifecycle: EpisodeLifecycleIdentity | None = None
    contact_active: bool = False
    collision_pulse_pending: bool = False
    last_event_id: str | None = None
    consumed_transition_ids: tuple[str, ...] = ()

@dataclass(frozen=True, slots=True)

class ContactLatchResult:
    accepted: bool
    state: ContactLatchState
    reason: str | None = None

class ContactLatch:
    """Small deterministic state holder consumed only by committed transitions."""

    def __init__(self) -> None:
        self._state = ContactLatchState()

    @property
    def state(self) -> ContactLatchState:
        return self._state

    def reset(self, lifecycle: EpisodeLifecycleIdentity) -> ContactLatchState:
        if not isinstance(lifecycle, EpisodeLifecycleIdentity):
            raise TypeError('lifecycle must be EpisodeLifecycleIdentity')
        self._state = ContactLatchState(lifecycle=lifecycle)
        return self._state

    def observe(self, fact: ContactFact) -> ContactLatchResult:
        if not isinstance(fact, ContactFact):
            return ContactLatchResult(False, self._state,
                'invalid contact fact')
        state = self._state
        if state.lifecycle is None or fact.lifecycle != state.lifecycle:
            return ContactLatchResult(False, state,
                'contact lifecycle is stale or unbound')
        if not fact.source_healthy:
            return ContactLatchResult(False, state,
                'contact source is unhealthy')
        if fact.event_id == state.last_event_id:
            return ContactLatchResult(True, state, 'duplicate event ignored')
        if fact.contact_active:
            state = ContactLatchState(fact.lifecycle, True, True,
                fact.event_id, state.consumed_transition_ids)
        else:
            state = ContactLatchState(fact.lifecycle, False,
                state.collision_pulse_pending, fact.event_id, state.consumed_transition_ids)
        self._state = state
        return ContactLatchResult(True, state)

    def commit_transition(self, transition_id: str,
        lifecycle: EpisodeLifecycleIdentity) -> ContactLatchResult:
        state = self._state
        if type(transition_id) is not str or not transition_id:
            return ContactLatchResult(False, state,
                'transition_id must be non-empty')
        if lifecycle != state.lifecycle:
            return ContactLatchResult(False, state,
                'transition lifecycle does not match contact')
        if transition_id in state.consumed_transition_ids:
            return ContactLatchResult(False, state,
                'transition already consumed contact pulse')
        next_state = ContactLatchState(state.lifecycle, state.contact_active,
            False, state.last_event_id, (*state.consumed_transition_ids,
            transition_id))
        self._state = next_state
        return ContactLatchResult(True, next_state)

    def can_commit_transition(self, transition_id: str,
        lifecycle: EpisodeLifecycleIdentity) -> bool:
        state = self._state
        return type(transition_id) is str and bool(transition_id) and (lifecycle == state.lifecycle) and (transition_id not in state.consumed_transition_ids)
__all__ = ('ContactFact', 'ContactLatch', 'ContactLatchResult',
    'ContactLatchState')
