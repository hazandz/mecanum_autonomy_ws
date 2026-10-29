from mecanum_nav_rl.core.lifecycle_types import EpisodeLifecycleIdentity
from mecanum_nav_rl.simulation.contact_latch import ContactFact, ContactLatch

def test_sustained_contact_and_pulse_consume_once_without_clearing_active():
    identity = EpisodeLifecycleIdentity(1, 1, 1)
    latch = ContactLatch()
    latch.reset(identity)
    assert latch.observe(ContactFact(identity, 'touch-1', True,
        True)).state.contact_active
    assert latch.state.collision_pulse_pending
    result = latch.commit_transition('transition-1', identity)
    assert result.accepted and result.state.contact_active and (not result.state.collision_pulse_pending)
    assert not latch.commit_transition('transition-1', identity).accepted

def test_explicit_empty_clears_active_but_not_pending_pulse_and_silence_is_no_call():
    identity = EpisodeLifecycleIdentity(1, 1, 1)
    latch = ContactLatch()
    latch.reset(identity)
    latch.observe(ContactFact(identity, 'touch', True, True))
    latch.observe(ContactFact(identity, 'empty', False, True))
    assert not latch.state.contact_active and latch.state.collision_pulse_pending

def test_old_epoch_true_false_reset_during_contact_and_duplicate_events():
    current = EpisodeLifecycleIdentity(2, 2, 1)
    old = EpisodeLifecycleIdentity(1, 1, 1)
    latch = ContactLatch()
    latch.reset(current)
    assert not latch.observe(ContactFact(old, 'old-true', True, True)).accepted
    assert not latch.observe(ContactFact(old, 'old-false', False,
        True)).accepted
    true = ContactFact(current, 'same', True, True)
    assert latch.observe(true).accepted
    before = latch.state
    duplicate = latch.observe(true)
    assert duplicate.accepted and duplicate.state == before
    latch.reset(EpisodeLifecycleIdentity(3, 3, 2))
    assert not latch.state.contact_active and (not latch.state.collision_pulse_pending)

def test_abort_keeps_pending_pulse_until_successful_transition_commit():
    identity = EpisodeLifecycleIdentity(1, 1, 1)
    latch = ContactLatch()
    latch.reset(identity)
    latch.observe(ContactFact(identity, 'collision', True, True))
    assert latch.state.collision_pulse_pending
    assert latch.commit_transition('committed', identity).accepted
    assert not latch.state.collision_pulse_pending
