"""Control production với generated types và I/O giả; không tạo ROS graph."""
import asyncio
from types import SimpleNamespace

import pytest
from rclpy.serialization import serialize_message
from mecanum_nav_rl_interfaces.srv import LocalTrainingBackendControl as Control
from mecanum_nav_rl_interfaces.msg import SafetyLifecycleState
from mecanum_nav_rl.runtime_simulation.local_training_ports import LocalTrainingBackendControlPort
from mecanum_nav_rl.runtime_simulation.local_training_coordinator import (
    BackendSessionIdentity, BackendControlSession, BackendControlError, lifecycle_request_fields,
)
from mecanum_nav_rl.runtime_safety.safety_contract import SafetyLifecycleCore


class Clock:
    def __init__(self): self.ns = 1_000_000_000
    def now(self): return self.ns
    async def pause(self, seconds): self.ns += round(seconds * 1_000_000_000)


class Client:
    def __init__(self, respond): self.respond, self.raw = respond, []
    def call_async(self, request):
        self.raw.append(serialize_message(request))
        response = self.respond(request, len(self.raw))
        return SimpleNamespace(done=lambda: True, result=lambda: response)


def response(request, result=None):
    out = Control.Response()
    out.schema_version = out.RESPONSE_SCHEMA_VERSION
    out.backend_instance_id = 8
    out.request_sequence = request.request_sequence
    out.result = out.RESULT_APPLIED if result is None else result
    out.reason_code = out.REASON_NONE
    out.binding_revision = request.expected_binding_revision + int(request.operation != request.OP_VERIFY_CONTACT_CAPABILITY)
    if out.result == out.RESULT_APPLIED:
        out.applied_binding_revision = out.binding_revision
        out.applied_physics_iteration = 100
        out.applied_sim_stamp.sec = 1
        if request.operation == request.OP_BIND_PENDING_STEP:
            out.pending_admission_token = list(range(16))
    return out


def setup(respond=response):
    clock, events = Clock(), []
    client = Client(lambda req, n: respond(req))
    session = BackendControlSession(LocalTrainingBackendControlPort(client),
        BackendSessionIdentity('session', 'a'*64, 'b'*64, 7, 8),
        emit=lambda name, facts: events.append((name, facts)), now_ns=clock.now, pause=clock.pause)
    return session, client, clock, events


def test_exact_queued_replay_preserves_bytes_sequence_and_deadline():
    session, client, clock, events = setup()
    client.respond = lambda req, n: response(req, Control.Response.RESULT_QUEUED if n < 3 else Control.Response.RESULT_APPLIED)
    ack = asyncio.run(session.transact(Control.Request.OP_BIND_PENDING_STEP,
        deadline_ns=clock.ns + 2_000_000_000, pending_step_index=1, pending_source_sequence=1,
        pending_transition_id='step-1'))
    assert len(client.raw) == 3 and len(set(client.raw)) == 1
    assert session.revision == 1
    assert any(ack.response.pending_admission_token)
    assert [name for name, _ in events].count('CONTROL_REQUEST') == 1
    assert events[0][1]['deadline_ns'] == 2_000_000_000
    assert events[-1][0] == 'ACK_OBSERVED'
    altered = ack.response; altered.binding_revision = 99
    assert ack.response.binding_revision == 1


@pytest.mark.parametrize('field, value, reason', [
    ('backend_instance_id', 9, 'identity/schema'), ('schema_version', 1, 'identity/schema'),
    ('request_sequence', 999, 'identity/schema'), ('applied_binding_revision', 2, 'revision/application'),
    ('applied_physics_iteration', 0, 'revision/application'),
    ('pending_admission_token', [0]*16, 'without admission token'),
])
def test_wrong_ack_cannot_update_revision_or_expose_token(field, value, reason):
    def respond(req):
        out = response(req); setattr(out, field, value); return out
    session, client, clock, events = setup(respond)
    with pytest.raises(BackendControlError, match=reason):
        asyncio.run(session.transact(Control.Request.OP_BIND_PENDING_STEP,
                                    deadline_ns=clock.ns + 1_000_000_000))
    assert session.revision == 0
    assert events[-1][0] == 'CONTROL_UNCERTAIN'


def test_queued_cannot_publish_token_and_never_counts_as_applied():
    def respond(req):
        out = response(req, Control.Response.RESULT_QUEUED)
        out.pending_admission_token = [1]*16
        return out
    session, client, clock, events = setup(respond)
    with pytest.raises(BackendControlError, match='QUEUED'):
        asyncio.run(session.transact(Control.Request.OP_BIND_PENDING_STEP, deadline_ns=clock.ns + 10_000_000))
    assert session.revision == 0 and len(client.raw) == 1


def test_queued_until_deadline_is_bounded_and_faults_session():
    session, client, clock, events = setup(lambda req: response(req, Control.Response.RESULT_QUEUED))
    with pytest.raises(TimeoutError):
        asyncio.run(session.transact(Control.Request.OP_BIND_PENDING_STEP, deadline_ns=clock.ns + 12_000_000))
    assert clock.ns == 1_012_000_000
    assert len(set(client.raw)) == 1 and session.revision == 0
    with pytest.raises(BackendControlError, match='uncertain/faulted'):
        asyncio.run(session.transact(Control.Request.OP_BIND_PENDING_STEP, deadline_ns=clock.ns + 10_000_000))


def test_late_observation_of_applied_ack_cannot_succeed():
    session, client, clock, events = setup()
    def respond(req, n):
        clock.ns += 1_000_000_001
        return response(req)
    client.respond = respond
    with pytest.raises(TimeoutError, match='after deadline'):
        asyncio.run(session.transact(Control.Request.OP_BIND_PENDING_STEP, deadline_ns=clock.ns + 2_000_000_000))
    assert session.revision == 0


def test_invalid_overrides_do_not_send_or_consume_local_sequence():
    session, client, clock, events = setup()
    with pytest.raises(ValueError, match='pinned'):
        asyncio.run(session.transact(Control.Request.OP_INHIBIT, deadline_ns=clock.ns + 1_000_000_000,
                                    session_id='foreign'))
    assert not client.raw
    ack = asyncio.run(session.transact(Control.Request.OP_INHIBIT, deadline_ns=clock.ns + 1_000_000_000))
    assert ack.request.request_sequence == 1


def test_nonadvancing_pause_dependency_fails_instead_of_looping():
    session, client, clock, events = setup(lambda req: response(req, Control.Response.RESULT_QUEUED))
    async def frozen_pause(seconds): pass
    session._pause = frozen_pause
    with pytest.raises(BackendControlError, match='did not advance'):
        asyncio.run(session.transact(Control.Request.OP_INHIBIT, deadline_ns=clock.ns + 1_000_000_000))
    assert len(client.raw) == 1


def test_real_lifecycle_core_motion_flag_is_copied_without_fabricating_hold():
    core = SafetyLifecycleCore()
    core.configure(1); core.activate(2)
    actual = core.rearm(3)
    assert actual.motion_permitted
    msg = SafetyLifecycleState()
    msg.episode_generation = actual.episode_generation
    msg.reset_epoch = actual.reset_epoch
    msg.runtime_generation = actual.runtime_generation
    msg.sequence = actual.sequence
    msg.primary_state = msg.PRIMARY_ACTIVE
    msg.barrier_state = msg.BARRIER_READY
    msg.motion_permitted = actual.motion_permitted
    msg.header.frame_id = 'b2_training_arena'
    fields = lifecycle_request_fields(msg)
    assert fields['motion_permitted'] is True
    assert fields['runtime_generation'] == actual.runtime_generation
    assert fields['lifecycle_sequence'] == actual.sequence


def test_non_pending_response_cannot_leak_a_token():
    def respond(req):
        out = response(req); out.pending_admission_token = [1] * 16; return out
    session, _, clock, _ = setup(respond)
    with pytest.raises(BackendControlError, match='non-pending'):
        asyncio.run(session.transact(Control.Request.OP_BIND_SESSION, deadline_ns=clock.ns + 1_000_000_000))


def test_evidence_sink_failure_preserves_original_error_and_faults_sequence():
    session, client, clock, _ = setup()
    def fail_sink(name, facts):
        raise OSError('evidence disk unavailable')
    session._emit = fail_sink
    with pytest.raises(OSError, match='evidence disk unavailable'):
        asyncio.run(session.transact(Control.Request.OP_BIND_SESSION, deadline_ns=clock.ns + 1_000_000_000))
    assert not client.raw and session.evidence_errors
    assert session.owned_calls == ()
    with pytest.raises(BackendControlError, match='uncertain/faulted'):
        asyncio.run(session.transact(Control.Request.OP_BIND_SESSION, deadline_ns=clock.ns + 1_000_000_000))


def test_inhibit_cancels_waiting_client_but_requires_native_ack():
    async def exercise():
        session, client, clock, events = setup()
        waiting = asyncio.Future()
        history = []
        def submit(req):
            history.append(req)
            if req.operation != req.OP_INHIBIT:
                return waiting
            answer = asyncio.Future(); answer.set_result(response(req)); return answer
        client.call_async = submit
        async def pause(seconds):
            clock.ns += round(seconds * 1e9)
            await asyncio.sleep(0)
        session._pause = pause
        transaction = asyncio.create_task(session.transact(Control.Request.OP_BIND_PENDING_STEP,
            deadline_ns=clock.ns + 1_000_000_000))
        await asyncio.sleep(0)
        assert len(history) == 1 and not transaction.done()
        ack = await session.inhibit(deadline_ns=clock.ns + 100_000_000)
        assert transaction.cancelled()
        assert [req.operation for req in history] == [Control.Request.OP_BIND_PENDING_STEP, Control.Request.OP_INHIBIT]
        assert [req.request_sequence for req in history] == [1, 2]
        assert ack.response.result == ack.response.RESULT_APPLIED
        assert waiting in session.owned_calls  # Server chưa được coi là đã hủy bởi client cancel.
        session.cancel_pending_calls()
        assert waiting.cancelled() and session.owned_calls == ()
        assert clock.ns < 1_100_000_000
    asyncio.run(exercise())


@pytest.mark.parametrize('deadline', [1., True, None])
def test_invalid_deadline_never_submits(deadline):
    session, client, _, _ = setup()
    with pytest.raises(TypeError, match='integer nanoseconds'):
        asyncio.run(session.transact(Control.Request.OP_INHIBIT, deadline_ns=deadline))
    assert not client.raw


def test_completed_replay_preserves_sequence_and_allows_revoked_query_proof():
    session, client, clock, events = setup()
    async def exercise():
        ack = await session.transact(Control.Request.OP_VERIFY_CONTACT_CAPABILITY,
            deadline_ns=clock.ns + 1_000_000_000, probe_action=Control.Request.PROBE_ACTION_QUERY,
            probe_start_request_sequence=1)
        revision = session.revision
        def revoked(req, n):
            result = response(req)
            result.contact_capability_state = result.CAPABILITY_INVALIDATED
            return result
        client.respond = revoked
        repeated = await session.replay(ack, deadline_ns=clock.ns + 1_000_000_000)
        assert repeated.response.contact_capability_state == Control.Response.CAPABILITY_INVALIDATED
        assert session.revision == revision
        assert client.raw == [ack.request_bytes, ack.request_bytes]
        fresh = await session.transact(Control.Request.OP_INHIBIT, deadline_ns=clock.ns + 1_000_000_000)
        assert fresh.request.request_sequence == 2
    asyncio.run(exercise())


def test_foreign_completed_ack_cannot_be_replayed():
    from mecanum_nav_rl.runtime_simulation.local_training_coordinator import BackendControlAck
    session, client, clock, _ = setup()
    async def exercise():
        ack = await session.transact(Control.Request.OP_INHIBIT, deadline_ns=clock.ns + 1_000_000_000)
        req = ack.request; req.session_id = 'other'
        foreign = BackendControlAck(serialize_message(req), ack.response_bytes, ack.observed_steady_ns)
        with pytest.raises(BackendControlError, match='not a retained owned'):
            await session.replay(foreign, deadline_ns=clock.ns + 1_000_000_000)
        assert len(client.raw) == 1
    asyncio.run(exercise())


def test_waiting_for_control_lock_uses_original_absolute_budget():
    session, client, clock, _ = setup()
    async def exercise():
        await session._lock.acquire()
        try:
            with pytest.raises(TimeoutError):
                await session.transact(Control.Request.OP_INHIBIT, deadline_ns=clock.ns + 12_000_000)
            assert clock.ns == 1_012_000_000 and not client.raw
        finally:
            session._lock.release()
    asyncio.run(exercise())


def test_inhibit_accepts_native_paused_initial_iteration_without_fabricated_proof():
    def respond(req):
        out=response(req);out.applied_physics_iteration=0
        out.applied_sim_stamp.sec=0;out.applied_sim_stamp.nanosec=0
        return out
    session,client,clock,events=setup(respond)
    ack=asyncio.run(session.transact(Control.Request.OP_INHIBIT,deadline_ns=clock.ns+1_000_000_000))
    assert ack.response.applied_physics_iteration==0 and ack.response.applied_sim_stamp.sec==0
    assert session.revision==1 and len(client.raw)==1
    assert events[-1][0]=='ACK_OBSERVED'
    session,client,clock,events=setup(respond)
    with pytest.raises(BackendControlError,match='revision/application'):
        asyncio.run(session.transact(Control.Request.OP_BIND_SESSION,deadline_ns=clock.ns+1_000_000_000))
    assert session.revision==0


def test_inhibit_accepts_pinned_native_applied_revision_after_unobserved_prior_mutation():
    def respond(req):
        out = response(req)
        # Native có thể đã áp dụng giao dịch trước trong lúc client mất ACK.
        out.binding_revision = req.expected_binding_revision + 2
        out.applied_binding_revision = out.binding_revision
        return out
    session, client, clock, events = setup(respond)
    async def run():
        client.respond = lambda req, n: response(req, Control.Response.RESULT_QUEUED)
        with pytest.raises(TimeoutError):
            await session.transact(Control.Request.OP_PREPARE_RESET_PAUSE, deadline_ns=clock.ns + 12_000_000)
        client.respond = lambda req, n: respond(req)
        return await session.inhibit(deadline_ns=clock.ns + 1_000_000_000)
    ack = asyncio.run(run())
    assert ack.response.result == Control.Response.RESULT_APPLIED
    assert ack.response.binding_revision == session.revision == 2
    assert [name for name, _ in events][-1] == 'ACK_OBSERVED'
    assert len(set(client.raw[:-1])) == 1


@pytest.mark.parametrize('binding, applied', [(0, 0), (1, 2), (2, 1), (2, 2)])
def test_inhibit_rejects_nonadvancing_or_inconsistent_native_revision(binding, applied):
    def respond(req):
        out = response(req); out.binding_revision = binding; out.applied_binding_revision = applied
        return out
    session, client, clock, events = setup(respond)
    with pytest.raises(BackendControlError, match='revision/application'):
        asyncio.run(session.inhibit(deadline_ns=clock.ns + 1_000_000_000))
    assert session.revision == 0
