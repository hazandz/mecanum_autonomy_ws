"""Control production với generated types và I/O giả; không tạo ROS graph."""
import asyncio
from types import SimpleNamespace

import pytest
from rclpy.serialization import serialize_message
from mecanum_nav_rl_interfaces.srv import LocalTrainingBackendControl as Control
from mecanum_nav_rl_interfaces.msg import SafetyLifecycleState
from mecanum_nav_rl.runtime_simulation.local_training_ports import LocalTrainingBackendControlPort
from mecanum_nav_rl.runtime_simulation.local_training_coordinator import (
    BackendSessionIdentity, BackendControlSession, BackendControlError,
    LocalTrainingB1Adapter, B1SnapshotPending, lifecycle_request_fields,
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


def test_goal_settle_window_collects_only_exact_applied_intermediate_cutoffs():
    """Production coordinator carries retained sample gaps into B1."""
    from rclpy.serialization import serialize_message
    from mecanum_nav_rl_interfaces.msg import SimulationContactState

    adapter = object.__new__(LocalTrainingB1Adapter)
    events = []
    identity = SimpleNamespace(episode_generation=2, reset_epoch=3,
                               runtime_generation=4)
    receipt_rows = []
    safety_rows = []
    pairs = []
    scans, noisy_samples = {}, {}
    stamps = (1_100_000_000, 1_200_000_000, 1_250_000_000)
    for sequence, stamp in enumerate(stamps, start=1):
        receipt_rows.append(SimpleNamespace(
            final_publish_sequence=sequence,
            lifecycle=identity,
            final_publisher_instance_id=7,
            session_id='session', ingress_config_hash='a' * 64,
            publish_stamp_ns=stamp - 10_000_000,
            received_steady_ns=stamp,
            receipt_key=f'7:{sequence}', admission_valid=True,
        ))
        safety_rows.append((stamp - 1, stamp,
                            SimpleNamespace(reset_epoch=3,
                                            runtime_generation=4)))
        scans[stamp] = SimpleNamespace(received_steady_ns=stamp - 2_000_000)
        noisy_samples[stamp] = SimpleNamespace(received_steady_ns=stamp - 1_000_000)
        status = SimulationContactState()
        status.applied_final_publish_sequence = sequence
        pairs.append(SimpleNamespace(stamp_ns=stamp,
            oracle_received_steady_ns=stamp - 3_000_000,
            backend_received_steady_ns=stamp - 2_500_000,
            backend_bytes=serialize_message(status)))
    adapter.ingress = SimpleNamespace(
        scans=scans, noisy_samples=noisy_samples, physics_pairs=pairs,
        receipts=receipt_rows, safety_states=safety_rows,
        final_publisher_id=7,
        identity=SimpleNamespace(session_id='session', config_hash='a' * 64),
        lifecycle_received_ns=1_000_000_000,
        now=lambda: 1_300_000_000,
    )
    adapter.binding = SimpleNamespace(lifecycle_identity=identity)
    adapter.emit = lambda name, facts: events.append((name, facts))
    pair_facts = {}
    for sequence, stamp in enumerate(stamps, start=1):
        pair_facts[stamp] = {
            'identity': identity,
            'steady_now': 1_300_000_000,
            'status': SimpleNamespace(
                applied_sim_stamp=SimpleNamespace(
                    sec=stamp // 1_000_000_000,
                    nanosec=stamp % 1_000_000_000,
                ),
                applied_final_publish_sequence=sequence,
                applied_receipt_valid=True,
                local_zero_override=False,
            ),
        }
    evaluation_times = {}
    def joined(stamp, *, evaluation_ros_now_ns=None,
               evaluation_steady_now_ns=None):
        evaluation_times[stamp] = (evaluation_ros_now_ns,
                                   evaluation_steady_now_ns)
        return {**pair_facts[stamp], 'ros_now': evaluation_ros_now_ns,
                'steady_now': evaluation_steady_now_ns}
    adapter._joined = joined
    def make_sample(facts, receipt, safety_state, safety_received_ns):
        return SimpleNamespace(
            timestamp_ns=facts['status'].applied_sim_stamp.sec * 1_000_000_000
                + facts['status'].applied_sim_stamp.nanosec,
            received_steady_ns=receipt.received_steady_ns,
            pose_x_m=0.0, pose_y_m=0.0, body_vx_mps=0.0,
            body_vy_mps=0.0, body_wz_radps=0.0,
            lifecycle_key=(2, 3, 4),
            health=SimpleNamespace(
                receipt_timestamp_ns=receipt.publish_stamp_ns,
                receipt_received_steady_ns=receipt.received_steady_ns,
                    evaluation_ros_now_ns=facts['status'].applied_sim_stamp.sec
                        * 1_000_000_000 + facts['status'].applied_sim_stamp.nanosec,
                    evaluation_steady_now_ns=receipt.received_steady_ns,
                scan_timestamp_ns=facts['status'].applied_sim_stamp.sec
                    * 1_000_000_000 + facts['status'].applied_sim_stamp.nanosec,
                noisy_odometry_timestamp_ns=facts['status'].applied_sim_stamp.sec
                    * 1_000_000_000 + facts['status'].applied_sim_stamp.nanosec,
                    scan_steady_age_ns=0, noisy_odom_steady_age_ns=0,
                    oracle_steady_age_ns=0, receipt_steady_age_ns=0,
                healthy=lambda: True,
            ),
        )
    adapter._goal_settle_sample_for_exact_cutoff = make_sample
    final = SimpleNamespace(timestamp_ns=1_300_000_000,
        received_steady_ns=1_300_000_000, pose_x_m=0.0, pose_y_m=0.0,
        body_vx_mps=0.0, body_vy_mps=0.0, body_wz_radps=0.0,
        lifecycle_key=(2, 3, 4), health=SimpleNamespace(
            receipt_timestamp_ns=1_290_000_000,
            receipt_received_steady_ns=1_300_000_000,
            evaluation_ros_now_ns=1_300_000_000,
            evaluation_steady_now_ns=1_300_000_000,
            scan_timestamp_ns=1_300_000_000,
            noisy_odometry_timestamp_ns=1_300_000_000,
            scan_steady_age_ns=0, noisy_odom_steady_age_ns=0,
            oracle_steady_age_ns=0, receipt_steady_age_ns=0,
            healthy=lambda: True))
    final_selection = SimpleNamespace(receipt=SimpleNamespace(receipt_key='7:4'))
    prior = SimpleNamespace(last_ros_ns=1_000_000_000)

    samples, reset_prior = adapter._goal_settle_sample_sequence(
        1_300_000_000, {}, final_selection, final, prior, True)

    assert not reset_prior
    assert [item.timestamp_ns for item in samples] == [
        1_100_000_000, 1_200_000_000, 1_250_000_000,
        1_300_000_000,
    ]
    assert events[-1][0] == 'GOAL_SETTLE_SAMPLE_WINDOW'
    assert events[-1][1]['sample_count'] == 4
    assert evaluation_times == {
        stamp: (stamp, stamp) for stamp in stamps
    }


def test_goal_settle_window_breaks_continuity_when_exact_pair_is_missing():
    """A missing source cutoff cannot be bridged by later samples."""
    from rclpy.serialization import serialize_message
    from mecanum_nav_rl_interfaces.msg import SimulationContactState

    adapter = object.__new__(LocalTrainingB1Adapter)
    events = []
    identity = SimpleNamespace(episode_generation=2, reset_epoch=3,
                               runtime_generation=4)
    receipt_rows = []
    safety_rows = []
    pairs = []
    stamps = (1_100_000_000, 1_300_000_000)
    for sequence, stamp in enumerate(stamps, start=1):
        receipt_rows.append(SimpleNamespace(
            final_publish_sequence=sequence, lifecycle=identity,
            final_publisher_instance_id=7, session_id='session',
            ingress_config_hash='a' * 64,
            publish_stamp_ns=stamp - 10_000_000,
            received_steady_ns=stamp, receipt_key=f'7:{sequence}',
        ))
        safety_rows.append((stamp, stamp,
            SimpleNamespace(reset_epoch=3, runtime_generation=4)))
        status = SimulationContactState()
        status.applied_final_publish_sequence = sequence
        pairs.append(SimpleNamespace(stamp_ns=stamp,
            oracle_received_steady_ns=stamp,
            backend_received_steady_ns=stamp,
            backend_bytes=serialize_message(status)))
    adapter.ingress = SimpleNamespace(
        scans={stamp: SimpleNamespace(received_steady_ns=stamp)
               for stamp in (1_100_000_000, 1_200_000_000, 1_300_000_000)},
        noisy_samples={stamp: SimpleNamespace(received_steady_ns=stamp)
                       for stamp in (1_100_000_000, 1_200_000_000, 1_300_000_000)},
        physics_pairs=pairs,
        receipts=receipt_rows, safety_states=safety_rows,
        final_publisher_id=7,
        identity=SimpleNamespace(session_id='session', config_hash='a' * 64),
        lifecycle_received_ns=1_000_000_000,
        now=lambda: 1_300_000_000,
    )
    adapter.binding = SimpleNamespace(lifecycle_identity=identity)
    adapter.emit = lambda name, facts: events.append((name, facts))
    def joined(stamp, *, evaluation_ros_now_ns=None,
               evaluation_steady_now_ns=None):
        if stamp == 1_200_000_000:
            raise B1SnapshotPending('exact oracle/backend pair unavailable')
        sequence = 1 if stamp == 1_100_000_000 else 2
        return {'identity': identity, 'ros_now': evaluation_ros_now_ns,
            'steady_now': evaluation_steady_now_ns,
            'status': SimpleNamespace(
                applied_sim_stamp=SimpleNamespace(sec=stamp // 1_000_000_000,
                    nanosec=stamp % 1_000_000_000),
                applied_final_publish_sequence=sequence,
                applied_receipt_valid=True, local_zero_override=False)}
    adapter._joined = joined
    adapter._goal_settle_sample_for_exact_cutoff = lambda facts, receipt, safety, received: SimpleNamespace(
        timestamp_ns=facts['status'].applied_sim_stamp.sec * 1_000_000_000
            + facts['status'].applied_sim_stamp.nanosec,
        received_steady_ns=receipt.received_steady_ns,
        pose_x_m=0.0, pose_y_m=0.0, body_vx_mps=0.0,
        body_vy_mps=0.0, body_wz_radps=0.0, lifecycle_key=(2, 3, 4),
        health=SimpleNamespace(receipt_timestamp_ns=receipt.publish_stamp_ns,
            receipt_received_steady_ns=receipt.received_steady_ns,
            evaluation_ros_now_ns=facts['status'].applied_sim_stamp.sec * 1_000_000_000
                + facts['status'].applied_sim_stamp.nanosec,
            evaluation_steady_now_ns=receipt.received_steady_ns,
            scan_timestamp_ns=facts['status'].applied_sim_stamp.sec * 1_000_000_000
                + facts['status'].applied_sim_stamp.nanosec,
            noisy_odometry_timestamp_ns=facts['status'].applied_sim_stamp.sec * 1_000_000_000
                + facts['status'].applied_sim_stamp.nanosec,
            scan_steady_age_ns=0, noisy_odom_steady_age_ns=0,
            oracle_steady_age_ns=0, receipt_steady_age_ns=0,
            healthy=lambda: True))
    final = SimpleNamespace(timestamp_ns=1_400_000_000,
        received_steady_ns=1_300_000_000, pose_x_m=0.0, pose_y_m=0.0,
        body_vx_mps=0.0, body_vy_mps=0.0, body_wz_radps=0.0,
        lifecycle_key=(2, 3, 4), health=SimpleNamespace(
            receipt_timestamp_ns=1_390_000_000,
            receipt_received_steady_ns=1_300_000_000,
            evaluation_ros_now_ns=1_400_000_000,
            evaluation_steady_now_ns=1_300_000_000,
            scan_timestamp_ns=1_400_000_000,
            noisy_odometry_timestamp_ns=1_400_000_000,
            scan_steady_age_ns=0, noisy_odom_steady_age_ns=0,
            oracle_steady_age_ns=0, receipt_steady_age_ns=0,
            healthy=lambda: True))

    samples, reset_prior = adapter._goal_settle_sample_sequence(
        1_400_000_000, {}, SimpleNamespace(receipt=SimpleNamespace(receipt_key='7:3')),
        final, SimpleNamespace(last_ros_ns=1_000_000_000), True)

    assert reset_prior
    assert [item.timestamp_ns for item in samples] == [
        1_300_000_000, 1_400_000_000,
    ]
    assert any(name == 'GOAL_SETTLE_SAMPLE_GAP' for name, _ in events)


def test_non_pending_response_cannot_leak_a_token():
    def respond(req):
        out = response(req); out.pending_admission_token = [1] * 16; return out
    session, _, clock, _ = setup(respond)
    with pytest.raises(BackendControlError, match='non-pending'):
        asyncio.run(session.transact(Control.Request.OP_BIND_SESSION, deadline_ns=clock.ns + 1_000_000_000))


def _b1_cutoff_fixture(receipts, *, cutoff_ns=1_000_000_000, steady_now_ns=10_000_000_000):
    from builtin_interfaces.msg import Time
    from mecanum_nav_rl.core.issued_command_cutoff import IssuedCommandReceiptView, ReceiptSource
    from mecanum_nav_rl.core.lifecycle_types import EpisodeLifecycleIdentity

    lifecycle = EpisodeLifecycleIdentity(1, 2, 3)
    source = SimpleNamespace(
        final_publisher_id=77,
        identity=SimpleNamespace(session_id='session', config_hash='a' * 64),
        lifecycle=SimpleNamespace(barrier_stamp=Time(sec=0, nanosec=800_000_000)),
        receipts=tuple(IssuedCommandReceiptView(
            publish_stamp_ns=publish_ns,
            final_publisher_instance_id=77,
            final_publish_sequence=sequence,
            source=ReceiptSource.SAFE_STOP,
            source_instance_id=88,
            source_sequence=sequence,
            step_index=0,
            transition_id='',
            lifecycle=lifecycle,
            session_id='session',
            ingress_config_hash='a' * 64,
            final_command=(0.0, 0.0, 0.0),
            received_steady_ns=received_ns,
            frame_id='base_link',
            admission_valid=True,
        ) for sequence, publish_ns, received_ns in receipts),
    )
    adapter = object.__new__(LocalTrainingB1Adapter)
    adapter.ingress = source
    adapter.scales = (0.25, 0.2, 0.8)
    adapter.action_barrier_ns = None
    return adapter, {'identity': lifecycle, 'cutoff': cutoff_ns,
        'ros_now': 1_030_000_000, 'steady_now': steady_now_ns}


def test_b1_reset_cutoff_ignores_expired_history_when_fresh_boundary_exists():
    """Lịch sử receipt hết hạn không được làm hỏng cặp mới đủ freshness."""
    from mecanum_nav_rl.core.lifecycle_types import EpisodeLifecycleIdentity

    stale = (8, 950_000_000, 9_000_000_000)
    selected = (9, 990_000_000, 9_800_000_000)
    adjacent = (10, 1_020_000_000, 9_900_000_000)
    adapter, facts = _b1_cutoff_fixture((stale, selected, adjacent))

    selection = adapter._selection(facts, reset=True)

    assert selection.status.value == 'ready'
    assert selection.receipt.final_publish_sequence == selected[0]
    assert selection.adjacent_receipt.final_publish_sequence == adjacent[0]
    assert selection.receipt.lifecycle == EpisodeLifecycleIdentity(1, 2, 3)


def test_b1_reset_cutoff_does_not_fallback_when_required_zero_receipt_is_stale():
    from mecanum_nav_rl.runtime_simulation.local_training_coordinator import B1SnapshotPending

    stale_selected = (9, 990_000_000, 9_400_000_000)
    fresh_adjacent = (10, 1_020_000_000, 9_900_000_000)
    adapter, facts = _b1_cutoff_fixture((stale_selected, fresh_adjacent))

    with pytest.raises(B1SnapshotPending, match='unchanged 500 ms freshness limit'):
        adapter._selection(facts, reset=True)


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


def test_replay_response_from_replacement_backend_is_retained_as_rejected_ack():
    session, client, clock, events = setup()
    async def exercise():
        original = await session.transact(Control.Request.OP_VERIFY_CONTACT_CAPABILITY,
            deadline_ns=clock.ns + 1_000_000_000,
            probe_action=Control.Request.PROBE_ACTION_QUERY,
            probe_start_request_sequence=1)
        def replacement_response(req, _n):
            out = response(req)
            out.backend_instance_id = 9
            out.result = Control.Response.RESULT_REJECTED
            out.reason_code = Control.Response.REASON_IDENTITY_MISMATCH
            out.contact_capability_state = Control.Response.CAPABILITY_INVALIDATED
            return out
        client.respond = replacement_response
        with pytest.raises(BackendControlError, match='identity/schema mismatch') as caught:
            await session.replay(original, deadline_ns=clock.ns + 1_000_000_000)
        rejected = caught.value.ack
        assert rejected is not None
        assert rejected.request_bytes == original.request_bytes
        assert rejected.request.operation == Control.Request.OP_VERIFY_CONTACT_CAPABILITY
        assert rejected.response.backend_instance_id == 9
        assert rejected.response.reason_code == Control.Response.REASON_IDENTITY_MISMATCH
        assert rejected.response.contact_capability_state != Control.Response.CAPABILITY_VERIFIED
        assert client.raw == [original.request_bytes, original.request_bytes]
        rejected_events = [facts for name, facts in events
            if name == 'CONTROL_REPLAY_RESPONSE_REJECTED']
        assert rejected_events[-1]['response_cdr_hex'] == rejected.response_bytes.hex()
        assert events[-1][0] == 'CONTROL_REPLAY_UNCERTAIN'
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
