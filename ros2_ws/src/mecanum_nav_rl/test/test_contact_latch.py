"""Pure regressions for contact pulse and active-state semantics."""

from mecanum_nav_rl.core.lifecycle_types import EpisodeLifecycleIdentity
from mecanum_nav_rl.simulation.contact_latch import ContactFact, ContactLatch


def test_sustained_contact_and_pulse_consume_once_without_clearing_active():
    """Pulse consumption preserves sustained active contact."""
    identity = EpisodeLifecycleIdentity(1, 1, 1)
    latch = ContactLatch()
    latch.reset(identity)
    observed = latch.observe(ContactFact(identity, 'touch-1', 1, True, True))
    assert observed.state.contact_active
    assert latch.state.collision_pulse_pending
    result = latch.commit_transition('transition-1', identity)
    assert result.accepted
    assert result.state.contact_active
    assert not result.state.collision_pulse_pending
    assert not latch.commit_transition('transition-1', identity).accepted


def test_explicit_empty_preserves_pending_pulse_and_silence_is_no_call():
    """An explicit empty clears active and preserves an unconsumed pulse."""
    identity = EpisodeLifecycleIdentity(1, 1, 1)
    latch = ContactLatch()
    latch.reset(identity)
    latch.observe(ContactFact(identity, 'touch', 1, True, True))
    latch.observe(ContactFact(identity, 'empty', 2, False, True))
    assert not latch.state.contact_active
    assert latch.state.collision_pulse_pending


def test_old_epoch_true_false_reset_during_contact_and_duplicate_events():
    """Old lifecycle facts and duplicate event ids do not alter state."""
    current = EpisodeLifecycleIdentity(2, 2, 1)
    old = EpisodeLifecycleIdentity(1, 1, 1)
    latch = ContactLatch()
    latch.reset(current)
    old_true = ContactFact(old, 'old-true', 1, True, True)
    old_false = ContactFact(old, 'old-false', 2, False, True)
    assert not latch.observe(old_true).accepted
    assert not latch.observe(old_false).accepted
    true = ContactFact(current, 'same', 1, True, True)
    assert latch.observe(true).accepted
    before = latch.state
    duplicate = latch.observe(true)
    assert not duplicate.accepted and duplicate.state == before
    latch.reset(EpisodeLifecycleIdentity(3, 3, 2))
    assert not latch.state.contact_active
    assert not latch.state.collision_pulse_pending


def test_abort_keeps_pending_pulse_until_successful_transition_commit():
    """A pending pulse stays set until successful transition consumption."""
    identity = EpisodeLifecycleIdentity(1, 1, 1)
    latch = ContactLatch()
    latch.reset(identity)
    latch.observe(ContactFact(identity, 'collision', 1, True, True))
    assert latch.state.collision_pulse_pending
    assert latch.commit_transition('committed', identity).accepted
    assert not latch.state.collision_pulse_pending


def test_delayed_true_or_empty_cannot_replay_across_newer_events_or_commit():
    """Sequence order rejects delayed contact facts after newer commits."""
    identity = EpisodeLifecycleIdentity(1, 1, 1)
    latch = ContactLatch()
    latch.reset(identity)
    assert latch.observe(ContactFact(identity, 'A', 1, True, True)).accepted
    assert latch.observe(ContactFact(identity, 'B', 2, False, True)).accepted
    assert latch.commit_transition('step-1', identity).accepted
    before = latch.state
    assert not latch.observe(ContactFact(
        identity, 'A', 1, True, True
    )).accepted
    assert latch.state == before
    assert not latch.observe(ContactFact(
        identity, 'delayed-empty', 2, False, True
    )).accepted
    assert latch.state == before
    assert not latch.observe(ContactFact(
        identity, 'unhealthy', 3, True, False
    )).accepted
    assert latch.state.source_healthy is False
    assert not latch.can_commit_transition('step-2', identity)
    assert latch.observe(ContactFact(identity, 'C', 4, True, True)).accepted
    assert latch.state.source_healthy is True
    assert latch.state.collision_pulse_pending


def test_monotonic_sequence_blocks_replay_after_event_id_cache_eviction():
    """The monotonic watermark rejects replays after bounded-cache eviction."""
    identity = EpisodeLifecycleIdentity(1, 1, 1)
    latch = ContactLatch()
    latch.reset(identity)
    assert latch.observe(ContactFact(
        identity, 'old-true', 1, True, True
    )).accepted
    for sequence in range(2, 260):
        result = latch.observe(ContactFact(
            identity, f'event-{sequence}', sequence, False, True
        ))
        assert result.accepted
    assert 'old-true' not in latch.state.seen_event_ids
    before = latch.state
    assert not latch.observe(ContactFact(
        identity, 'replayed-old-true', 1, True, True
    )).accepted
    assert latch.state == before


def test_unhealthy_source_blocks_contact_consumption_until_new_healthy_fact():
    """An unhealthy event blocks pulse consumption until health recovers."""
    identity = EpisodeLifecycleIdentity(1, 1, 1)
    latch = ContactLatch()
    latch.reset(identity)
    assert latch.observe(ContactFact(
        identity, 'touch', 1, True, True
    )).accepted
    assert latch.state.health_epoch == 0
    unhealthy = latch.observe(ContactFact(
        identity, 'health-loss', 2, False, False
    ))
    assert not unhealthy.accepted
    assert unhealthy.state.contact_active
    assert unhealthy.state.collision_pulse_pending
    assert unhealthy.state.source_healthy is False
    assert unhealthy.state.health_epoch == 1
    before = latch.state
    rejected = latch.commit_transition('step-1', identity)
    assert not rejected.accepted and latch.state == before
    restored = latch.observe(ContactFact(
        identity, 'health-restored', 3, False, True
    ))
    assert restored.accepted
    assert not restored.state.contact_active
    assert restored.state.collision_pulse_pending
    assert restored.state.health_epoch == 1
    consumed = latch.commit_transition('step-1', identity)
    assert consumed.accepted
    assert not consumed.state.contact_active
    assert not consumed.state.collision_pulse_pending
