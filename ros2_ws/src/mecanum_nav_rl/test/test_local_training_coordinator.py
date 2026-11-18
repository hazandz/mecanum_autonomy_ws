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
from mecanum_nav_rl.core.issued_command_cutoff import ReceiptSource
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


def test_policy_commit_uses_freshest_applied_repeat_for_same_issuance():
    """Repeated publication refreshes receipt age without another issuance."""
    identity = SimpleNamespace(episode_generation=2, reset_epoch=3,
        runtime_generation=4)
    token = SimpleNamespace(identity=identity, transition_id='step-1',
        step_index=1)
    older = SimpleNamespace(source=ReceiptSource.POLICY, lifecycle=identity,
        transition_id='step-1', source_instance_id=77, source_sequence=1,
        step_index=1, publish_stamp_ns=1_000_000_000,
        final_publish_sequence=10)
    refreshed = SimpleNamespace(source=ReceiptSource.POLICY,
        lifecycle=identity, transition_id='step-1', source_instance_id=77,
        source_sequence=1, step_index=1, publish_stamp_ns=1_400_000_000,
        final_publish_sequence=20)
    adapter = object.__new__(LocalTrainingB1Adapter)
    adapter.ingress = SimpleNamespace(policy_source_id=77,
        # Deliberately reverse callback order; final sequence is authoritative.
        receipts=[refreshed, older])
    proved = []

    def prove(receipt, cutoff_ns):
        proved.append((receipt.final_publish_sequence, cutoff_ns))
        return {'applied_sequence':receipt.final_publish_sequence}

    adapter._prove_application = prove

    selected = adapter._applied_policy_receipt_at_cutoff(token, 1_450_000_000)

    assert selected == (refreshed, {'applied_sequence':20})
    assert proved == [(20, 1_450_000_000)]


def test_policy_commit_falls_back_only_when_newest_repeat_lacks_application():
    """A later unapplied repeat cannot hide an earlier applied publication."""
    identity = SimpleNamespace(episode_generation=2, reset_epoch=3,
        runtime_generation=4)
    token = SimpleNamespace(identity=identity, transition_id='step-1',
        step_index=1)
    older = SimpleNamespace(source=ReceiptSource.POLICY, lifecycle=identity,
        transition_id='step-1', source_instance_id=77, source_sequence=1,
        step_index=1, publish_stamp_ns=1_000_000_000,
        final_publish_sequence=10)
    newer = SimpleNamespace(source=ReceiptSource.POLICY, lifecycle=identity,
        transition_id='step-1', source_instance_id=77, source_sequence=1,
        step_index=1, publish_stamp_ns=1_100_000_000,
        final_publish_sequence=11)
    adapter = object.__new__(LocalTrainingB1Adapter)
    adapter.ingress = SimpleNamespace(policy_source_id=77,
        receipts=[older, newer])
    proved = []

    def prove(receipt, cutoff_ns):
        proved.append(receipt.final_publish_sequence)
        if receipt is newer:
            raise B1SnapshotPending('native application not observed')
        return {'applied_sequence':receipt.final_publish_sequence}

    adapter._prove_application = prove

    selected = adapter._applied_policy_receipt_at_cutoff(token, 1_150_000_000)

    assert selected == (older, {'applied_sequence':10})
    assert proved == [11, 10]


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
        ros_time_at_receive=lambda _steady_ns: 1_300_000_000,
        ros_now=lambda: 1_300_000_000,
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
        # A retained goal sample must use the ROS clock paired with its last
        # source receive, not the later B1 decision clock.
        if evaluation_ros_now_ns < stamp:
            raise ValueError('future timestamps are invalid')
        evaluation_times[stamp] = (evaluation_ros_now_ns,
                                   evaluation_steady_now_ns)
        return {**pair_facts[stamp], 'ros_now': evaluation_ros_now_ns,
                'steady_now': evaluation_steady_now_ns}
    adapter._joined = joined
    adapter._goal_settle_zero_receipt_candidate = lambda stamp, _identity: (
        receipt_rows[stamps.index(stamp)], stamp - 5_000_000,
        receipt_rows[stamps.index(stamp)].received_steady_ns)
    adapter._goal_settle_zero_receipt_at_cutoff = lambda facts, candidate: (
        candidate[0], {'application_stamp_ns':candidate[1],
            'application_received_steady_ns':candidate[2],
            'native_zero_override':False, 'native_actuator_inhibited':False})
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
        stamp: (1_300_000_000, stamp) for stamp in stamps
    }


def test_goal_settle_window_skips_missing_cutoff_when_valid_cadence_is_within_limit():
    """An omitted source cutoff does not erase valid samples within 250 ms."""
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
        ros_time_at_receive=lambda _steady_ns: 1_400_000_000,
        ros_now=lambda: 1_400_000_000,
        now=lambda: 1_300_000_000,
    )
    adapter.binding = SimpleNamespace(lifecycle_identity=identity)
    adapter.emit = lambda name, facts: events.append((name, facts))
    adapter._goal_settle_zero_receipt_candidate = lambda stamp, _identity: (
        (next((item for item in receipt_rows
               if item.publish_stamp_ns < stamp), None), stamp - 1,
         next((item.received_steady_ns for item in receipt_rows
               if item.publish_stamp_ns < stamp), None))
        if any(item.publish_stamp_ns < stamp for item in receipt_rows) else None)
    adapter._goal_settle_zero_receipt_at_cutoff = lambda facts, candidate: (
        candidate[0], {'application_stamp_ns':candidate[1],
            'application_received_steady_ns':candidate[2],
            'native_zero_override':False, 'native_actuator_inhibited':False})
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

    assert not reset_prior
    assert [item.timestamp_ns for item in samples] == [
        1_100_000_000, 1_300_000_000, 1_400_000_000,
    ]
    assert any(name == 'GOAL_SETTLE_SAMPLE_GAP' for name, _ in events)


def test_goal_settle_selects_only_a_fresh_applied_zero_receipt_under_override():
    """The production selector uses pinned native application bytes, not a fabricated flag."""
    from rclpy.serialization import serialize_message
    from mecanum_nav_rl_interfaces.msg import SimulationContactState
    from mecanum_nav_rl.core.issued_command_cutoff import ReceiptSource
    from mecanum_nav_rl.core.lifecycle_types import EpisodeLifecycleIdentity
    import threading

    adapter = object.__new__(LocalTrainingB1Adapter)
    identity = EpisodeLifecycleIdentity(2, 3, 4)
    receipt = SimpleNamespace(final_publish_sequence=7, lifecycle=identity,
        final_publisher_instance_id=11, source=ReceiptSource.POLICY,
        session_id='bound-session', ingress_config_hash='a' * 64,
        publish_stamp_ns=1_000_000_000, received_steady_ns=2_000_000_000,
        final_command=(0.0, 0.0, 0.0), frame_id='base_link',
        receipt_key='11:7', admission_valid=True)
    applied = SimulationContactState()
    applied.header.stamp.sec = 1; applied.header.stamp.nanosec = 20_000_000
    applied.session_id = 'bound-session'; applied.config_hash = 'a' * 64
    applied.backend_instance_id = 13
    applied.episode_generation = 2; applied.reset_epoch = 3
    applied.runtime_generation = 4; applied.physics_iteration = 102
    applied.applied_receipt_valid = True
    applied.applied_final_publisher_instance_id = 11
    applied.applied_final_publish_sequence = 7
    applied.applied_physics_iteration = 102
    applied.applied_sim_stamp.sec = 1; applied.applied_sim_stamp.nanosec = 20_000_000
    current = SimulationContactState()
    current.header.stamp.sec = 1; current.header.stamp.nanosec = 100_000_000
    current.session_id = 'bound-session'; current.config_hash = 'a' * 64
    current.backend_instance_id = 13
    current.episode_generation = 2; current.reset_epoch = 3
    current.runtime_generation = 4; current.physics_iteration = 110
    current.local_zero_override = True; current.actuator_inhibited = True
    source = SimpleNamespace(receipts=[receipt], _receipt_views={7:receipt},
        _application_bytes={7:serialize_message(applied)},
        _application_received_ns={7:2_020_000_000},
        profile={'b1_receipt_max_age_ms':500}, lock=threading.RLock(),
        identity=SimpleNamespace(session_id='bound-session', config_hash='a'*64,
                                 backend_instance_id=13), final_publisher_id=11)
    adapter.ingress = source
    candidate = adapter._goal_settle_zero_receipt_candidate(1_100_000_000, identity)
    assert candidate == (receipt, 1_020_000_000, 2_020_000_000)
    selected = adapter._goal_settle_zero_receipt_at_cutoff({
        'cutoff':1_100_000_000, 'ros_now':1_100_000_000,
        'steady_now':2_100_000_000, 'identity':identity, 'status':current,
    }, candidate)
    assert selected is not None
    assert selected[0] is receipt
    assert selected[1]['native_zero_override'] is True
    assert selected[1]['native_actuator_inhibited'] is True


def test_goal_settle_accepts_applied_safe_stop_zero_while_inhibited():
    """A bound SAFE_STOP zero is physical zero evidence during an inhibited gap."""
    from rclpy.serialization import serialize_message
    from mecanum_nav_rl_interfaces.msg import SimulationContactState
    from mecanum_nav_rl.core.issued_command_cutoff import ReceiptSource
    from mecanum_nav_rl.core.lifecycle_types import EpisodeLifecycleIdentity
    import threading

    adapter = object.__new__(LocalTrainingB1Adapter)
    identity = EpisodeLifecycleIdentity(2, 3, 4)
    receipt = SimpleNamespace(final_publish_sequence=7, lifecycle=identity,
        final_publisher_instance_id=11, source=ReceiptSource.SAFE_STOP,
        session_id='bound-session', ingress_config_hash='a' * 64,
        publish_stamp_ns=1_000_000_000, received_steady_ns=2_000_000_000,
        final_command=(0.0, 0.0, 0.0), frame_id='base_link',
        receipt_key='11:7', admission_valid=True)

    def applied_status(stamp_ns, *, inhibited):
        status = SimulationContactState()
        status.header.stamp.sec, status.header.stamp.nanosec = divmod(
            stamp_ns, 1_000_000_000)
        status.session_id = 'bound-session'; status.config_hash = 'a' * 64
        status.backend_instance_id = 13
        status.episode_generation = 2; status.reset_epoch = 3
        status.runtime_generation = 4
        status.physics_iteration = stamp_ns // 10_000_000
        status.actuator_inhibited = inhibited
        status.applied_receipt_valid = True
        status.applied_final_publisher_instance_id = 11
        status.applied_final_publish_sequence = 7
        status.applied_physics_iteration = status.physics_iteration
        status.applied_sim_stamp.sec, status.applied_sim_stamp.nanosec = divmod(
            stamp_ns, 1_000_000_000)
        return status

    applied = applied_status(1_020_000_000, inhibited=True)
    current = applied_status(1_100_000_000, inhibited=True)
    source = SimpleNamespace(receipts=[receipt], _receipt_views={7:receipt},
        _application_bytes={7:serialize_message(applied)},
        _application_received_ns={7:2_020_000_000},
        profile={'b1_receipt_max_age_ms':500}, lock=threading.RLock(),
        identity=SimpleNamespace(session_id='bound-session', config_hash='a'*64,
                                 backend_instance_id=13), final_publisher_id=11)
    adapter.ingress = source

    candidate = adapter._goal_settle_zero_receipt_candidate(1_100_000_000, identity)
    assert candidate is not None
    assert candidate[0] is receipt
    selected = adapter._goal_settle_zero_receipt_at_cutoff({
        'cutoff':1_100_000_000, 'ros_now':1_100_000_000,
        'steady_now':2_100_000_000, 'identity':identity, 'status':current,
    }, candidate)
    assert selected is not None
    assert selected[0] is receipt
    assert selected[1]['native_actuator_inhibited'] is True
    assert selected[1]['native_zero_override'] is False

    # Inhibition does not turn a POLICY receipt into a valid admitted zero.
    policy_receipt = SimpleNamespace(**{
        **receipt.__dict__, 'source':ReceiptSource.POLICY,
    })
    source.receipts = [policy_receipt]
    source._receipt_views = {7:policy_receipt}
    assert adapter._goal_settle_zero_receipt_candidate(
        1_100_000_000, identity) is None


def test_goal_settle_accepts_current_zero_state_within_fresh_receipt_age():
    """A real zero receipt may remain current across a later exact sample cutoff."""
    from mecanum_nav_rl_interfaces.msg import SimulationContactState
    from mecanum_nav_rl.core.issued_command_cutoff import ReceiptSource
    from mecanum_nav_rl.core.lifecycle_types import EpisodeLifecycleIdentity

    adapter = object.__new__(LocalTrainingB1Adapter)
    identity = EpisodeLifecycleIdentity(2, 3, 4)
    receipt = SimpleNamespace(final_publish_sequence=7, lifecycle=identity,
        final_publisher_instance_id=11, source=ReceiptSource.POLICY,
        session_id='bound-session', ingress_config_hash='a' * 64,
        publish_stamp_ns=1_080_000_000, received_steady_ns=2_080_000_000,
        final_command=(0.0, 0.0, 0.0), frame_id='base_link',
        receipt_key='11:7', admission_valid=True)
    current = SimulationContactState()
    current.header.stamp.sec = 1; current.header.stamp.nanosec = 100_000_000
    current.session_id = 'bound-session'; current.config_hash = 'a' * 64
    current.backend_instance_id = 13
    current.episode_generation = 2; current.reset_epoch = 3
    current.runtime_generation = 4; current.physics_iteration = 110
    current.applied_receipt_valid = True
    current.applied_final_publisher_instance_id = 11
    current.applied_final_publish_sequence = 7
    current.applied_physics_iteration = 110
    current.applied_sim_stamp.sec = 1
    current.applied_sim_stamp.nanosec = 100_000_000
    source = SimpleNamespace(profile={'b1_receipt_max_age_ms':500},
        identity=SimpleNamespace(session_id='bound-session', config_hash='a' * 64,
            backend_instance_id=13), final_publisher_id=11)
    adapter.ingress = source

    selected = adapter._goal_settle_zero_receipt_at_cutoff({
        'cutoff':1_100_000_000, 'ros_now':1_100_000_000,
        'steady_now':2_100_000_000, 'identity':identity, 'status':current,
    }, (receipt, 1_080_000_000, 2_080_000_000))

    assert selected is not None
    assert selected[0] is receipt
    assert selected[1]['application_stamp_ns'] == 1_080_000_000
    assert selected[1]['application_proof'] == 'current_tick'

    # Native publishes applied-receipt fields for the consuming physics tick
    # only. At the next exact scan cutoff the fields are zeroed, while the
    # latest receipt-keyed application remains the real current zero command.
    current.applied_receipt_valid = False
    current.applied_final_publisher_instance_id = 0
    current.applied_final_publish_sequence = 0
    current.applied_physics_iteration = 0
    current.applied_sim_stamp.sec = 0
    current.applied_sim_stamp.nanosec = 0
    retained = adapter._goal_settle_zero_receipt_at_cutoff({
        'cutoff':1_100_000_000, 'ros_now':1_100_000_000,
        'steady_now':2_100_000_000, 'identity':identity, 'status':current,
    }, (receipt, 1_080_000_000, 2_080_000_000))
    assert retained is not None
    assert retained[0] is receipt
    assert retained[1]['application_proof'] == 'retained_applied_zero_no_later_nonzero'
    received_receipt = SimpleNamespace(**{
        **receipt.__dict__, 'received_steady_ns': 2_100_000_000})
    stale = adapter._goal_settle_zero_receipt_at_cutoff({
        'cutoff':1_100_000_000, 'ros_now':1_100_000_000,
        'steady_now':2_590_000_000, 'identity':identity, 'status':current,
    }, (received_receipt, 1_080_000_000, 2_080_000_000))
    assert stale is None


def test_goal_settle_sequence_uses_current_zero_across_dense_scan_cutoffs():
    """The production sequence retains actual 100 ms cutoffs under one fresh zero receipt."""
    from rclpy.serialization import serialize_message
    from mecanum_nav_rl_interfaces.msg import SimulationContactState
    from mecanum_nav_rl.core.issued_command_cutoff import ReceiptSource
    from mecanum_nav_rl.core.lifecycle_types import EpisodeLifecycleIdentity
    import threading

    adapter = object.__new__(LocalTrainingB1Adapter)
    events, evaluation_times = [], {}
    identity = EpisodeLifecycleIdentity(2, 3, 4)
    receipt = SimpleNamespace(final_publish_sequence=7, lifecycle=identity,
        final_publisher_instance_id=11, source=ReceiptSource.POLICY,
        session_id='bound-session', ingress_config_hash='a'*64,
        publish_stamp_ns=1_080_000_000, received_steady_ns=2_080_000_000,
        final_command=(0.0, 0.0, 0.0), frame_id='base_link',
        receipt_key='11:7', admission_valid=True)

    def status(stamp, *, applied, override=False):
        msg = SimulationContactState()
        msg.header.stamp.sec, msg.header.stamp.nanosec = divmod(stamp, 1_000_000_000)
        msg.session_id = 'bound-session'; msg.config_hash = 'a'*64
        msg.backend_instance_id = 13
        msg.episode_generation = 2; msg.reset_epoch = 3
        msg.runtime_generation = 4; msg.physics_iteration = stamp // 10_000_000
        msg.local_zero_override = override
        msg.actuator_inhibited = override
        if applied:
            msg.applied_receipt_valid = True
            msg.applied_final_publisher_instance_id = 11
            msg.applied_final_publish_sequence = 7
            msg.applied_physics_iteration = msg.physics_iteration
            msg.applied_sim_stamp.sec, msg.applied_sim_stamp.nanosec = divmod(
                stamp, 1_000_000_000)
        return msg

    applied = status(1_100_000_000, applied=True)
    rows = []
    scans, noisy, pairs, safety = {}, {}, [], []
    for stamp in (1_100_000_000, 1_200_000_000):
        current = applied if stamp == 1_100_000_000 else status(stamp, applied=True)
        scans[stamp] = SimpleNamespace(received_steady_ns=2_095_000_000 + stamp - 1_100_000_000)
        noisy[stamp] = SimpleNamespace(received_steady_ns=2_096_000_000 + stamp - 1_100_000_000)
        pairs.append(SimpleNamespace(stamp_ns=stamp,
            oracle_received_steady_ns=2_097_000_000 + stamp - 1_100_000_000,
            backend_received_steady_ns=2_098_000_000 + stamp - 1_100_000_000,
            backend_bytes=serialize_message(current)))
        safety.append((stamp, 2_099_000_000 + stamp - 1_100_000_000,
            SimpleNamespace(reset_epoch=3, runtime_generation=4)))
        rows.append(current)
    adapter.ingress = SimpleNamespace(scans=scans, noisy_samples=noisy,
        physics_pairs=pairs, receipts=[receipt], safety_states=safety,
        final_publisher_id=11, identity=SimpleNamespace(session_id='bound-session',
            config_hash='a'*64, backend_instance_id=13),
        lifecycle_received_ns=2_000_000_000,
        profile={'b1_receipt_max_age_ms':500}, lock=threading.RLock(),
        _receipt_views={7:receipt}, _application_bytes={7:serialize_message(applied)},
        _application_received_ns={7:2_100_000_000},
        ros_time_at_receive=lambda _steady_ns: 1_300_000_000,
        ros_now=lambda:1_300_000_000, now=lambda:2_300_000_000)
    adapter.binding = SimpleNamespace(lifecycle_identity=identity)
    adapter.emit = lambda name, facts: events.append((name, facts))

    def joined(stamp, *, evaluation_ros_now_ns=None,
               evaluation_steady_now_ns=None):
        evaluation_times[stamp] = (evaluation_ros_now_ns, evaluation_steady_now_ns)
        current = rows[(stamp - 1_100_000_000) // 100_000_000]
        return {'identity':identity, 'cutoff':stamp,
            'ros_now':evaluation_ros_now_ns, 'steady_now':evaluation_steady_now_ns,
            'status':current}
    adapter._joined = joined
    def make_goal_sample(facts, chosen, _safety, _received):
        health = SimpleNamespace(receipt_timestamp_ns=chosen.publish_stamp_ns,
            receipt_received_steady_ns=chosen.received_steady_ns,
            evaluation_ros_now_ns=facts['ros_now'],
            evaluation_steady_now_ns=facts['steady_now'],
            scan_timestamp_ns=facts['cutoff'],
            noisy_odometry_timestamp_ns=facts['cutoff'],
            scan_steady_age_ns=0, noisy_odom_steady_age_ns=0,
            oracle_steady_age_ns=0,
            receipt_steady_age_ns=facts['steady_now']-chosen.received_steady_ns,
            healthy=lambda:True)
        return SimpleNamespace(timestamp_ns=facts['cutoff'],
            received_steady_ns=facts['steady_now'], pose_x_m=0., pose_y_m=0.,
            body_vx_mps=0., body_vy_mps=0., body_wz_radps=0.,
            lifecycle_key=(2,3,4), health=health)
    adapter._goal_settle_sample_for_exact_cutoff = make_goal_sample
    final = SimpleNamespace(timestamp_ns=1_300_000_000,
        received_steady_ns=2_250_000_000, pose_x_m=0., pose_y_m=0.,
        body_vx_mps=0., body_vy_mps=0., body_wz_radps=0., lifecycle_key=(2,3,4),
        health=SimpleNamespace(receipt_timestamp_ns=1_080_000_000,
            receipt_received_steady_ns=2_080_000_000,
            evaluation_ros_now_ns=1_300_000_000,
            evaluation_steady_now_ns=2_250_000_000,
            scan_timestamp_ns=1_300_000_000,
            noisy_odometry_timestamp_ns=1_300_000_000,
            scan_steady_age_ns=0, noisy_odom_steady_age_ns=0,
            oracle_steady_age_ns=0, receipt_steady_age_ns=170_000_000,
            healthy=lambda:True))

    samples, reset_prior = adapter._goal_settle_sample_sequence(
        1_300_000_000, {}, SimpleNamespace(receipt=receipt), final,
        SimpleNamespace(last_ros_ns=1_000_000_000), True)

    assert not reset_prior, [event for event in events if event[0] == 'GOAL_SETTLE_SAMPLE_GAP']
    assert [item.timestamp_ns for item in samples] == [
        1_100_000_000, 1_200_000_000, 1_300_000_000]
    selected = [facts for name, facts in events if name == 'GOAL_SETTLE_ZERO_RECEIPT_SELECTED']
    assert [item['cutoff_ns'] for item in selected] == [1_100_000_000, 1_200_000_000]
    assert selected[1]['native_zero_override'] is False
    assert evaluation_times[1_100_000_000] == (1_300_000_000, 2_100_000_000)
    assert evaluation_times[1_200_000_000] == (1_300_000_000, 2_199_000_000)


def test_goal_settle_sequence_checks_freshness_at_each_actual_collection_clock():
    """Historical samples remain real and fresh at receive, not decision, time."""
    from rclpy.serialization import serialize_message
    from nav_msgs.msg import Odometry
    from sensor_msgs.msg import LaserScan
    from mecanum_nav_rl_interfaces.msg import SimulationContactState
    from mecanum_nav_rl.core.lifecycle_types import EpisodeLifecycleIdentity

    adapter = object.__new__(LocalTrainingB1Adapter)
    events = []
    identity = EpisodeLifecycleIdentity(2, 3, 4)
    lifecycle = SimpleNamespace(
        episode_generation=2, reset_epoch=3, runtime_generation=4,
        header=SimpleNamespace(stamp=SimpleNamespace(sec=1, nanosec=0)),
        barrier_stamp=SimpleNamespace(sec=1, nanosec=0),
    )
    stamps = (1_100_000_000, 1_200_000_000, 1_300_000_000)
    scans, noisy, pairs, receipt_candidates, safety = {}, {}, [], {}, []
    for index, stamp in enumerate(stamps, start=1):
        scan = LaserScan()
        scan.header.stamp.sec, scan.header.stamp.nanosec = divmod(stamp, 1_000_000_000)
        scans[stamp] = SimpleNamespace(received_steady_ns=2_000_000_000 + index * 100_000_000,
            message_bytes=serialize_message(scan))
        noisy[stamp] = SimpleNamespace(
            received_steady_ns=2_005_000_000 + index * 100_000_000,
            output=SimpleNamespace(snapshot=SimpleNamespace(timestamp_ns=stamp)),
            lifecycle=identity)
        oracle = Odometry()
        oracle.header.stamp.sec, oracle.header.stamp.nanosec = divmod(stamp, 1_000_000_000)
        oracle.pose.pose.orientation.w = 1.0
        status = SimulationContactState()
        status.header.stamp.sec, status.header.stamp.nanosec = divmod(stamp, 1_000_000_000)
        status.episode_generation, status.reset_epoch, status.runtime_generation = (2, 3, 4)
        status.physics_iteration = index
        status.backend_instance_id = 13
        status.session_id = 'session'
        status.config_hash = 'a' * 64
        pairs.append(SimpleNamespace(stamp_ns=stamp, iteration=index,
            oracle_bytes=serialize_message(oracle), backend_bytes=serialize_message(status),
            oracle_received_steady_ns=2_008_000_000 + index * 100_000_000,
            backend_received_steady_ns=2_010_000_000 + index * 100_000_000))
        receipt = SimpleNamespace(receipt_key=f'11:{index}',
            publish_stamp_ns=stamp - 1_000_000,
            received_steady_ns=2_012_000_000 + index * 100_000_000)
        receipt_candidates[stamp] = (receipt, stamp, 2_013_000_000 + index * 100_000_000)
        safety.append((stamp, 2_015_000_000 + index * 100_000_000,
            SimpleNamespace(reset_epoch=3, runtime_generation=4)))
    # The middle native status was already 200 ms old when its last source
    # arrived, so production _joined must omit it under this 100 ms budget.
    pairs[1] = SimpleNamespace(**{**pairs[1].__dict__,
        'backend_received_steady_ns':2_020_000_000})
    ingress = SimpleNamespace(
        fault=None, binding=None, lifecycle=lifecycle,
        lifecycle_received_ns=2_000_000_000,
        scans=scans, noisy_samples=noisy, physics_pairs=pairs,
        safety_states=safety,
        identity=SimpleNamespace(session_id='session', config_hash='a' * 64,
            backend_instance_id=13),
        ros_time_at_receive=lambda steady_ns: steady_ns - 1_000_000_000,
        profile={'scan_max_age_ms':500,'odometry_max_age_ms':500,
            'oracle_max_age_ms':500,'lifecycle_max_age_ms':5_000,
            'backend_status_receive_age_ms':100},
        ros_now=lambda:1_300_000_000, now=lambda:2_600_000_000)
    adapter.ingress = ingress
    adapter.binding = SimpleNamespace(lifecycle_identity=identity)
    adapter.emit = lambda name, facts: events.append((name, facts))
    adapter._goal_settle_zero_receipt_candidate = lambda stamp, _identity: receipt_candidates[stamp]
    adapter._goal_settle_zero_receipt_at_cutoff = lambda facts, candidate: (
        candidate[0], {'application_stamp_ns':candidate[1],
            'application_received_steady_ns':candidate[2],
            'native_zero_override':False,'native_actuator_inhibited':False})

    def make_sample(facts, receipt, _safety_state, _safety_received_ns):
        health = SimpleNamespace(
            receipt_timestamp_ns=receipt.publish_stamp_ns,
            receipt_received_steady_ns=receipt.received_steady_ns,
            evaluation_ros_now_ns=facts['ros_now'],
            evaluation_steady_now_ns=facts['steady_now'],
            scan_timestamp_ns=facts['cutoff'],
            noisy_odometry_timestamp_ns=facts['cutoff'],
            scan_steady_age_ns=facts['steady_now']-scans[facts['cutoff']].received_steady_ns,
            noisy_odom_steady_age_ns=facts['steady_now']-noisy[facts['cutoff']].received_steady_ns,
            oracle_steady_age_ns=facts['steady_now']-next(p for p in pairs if p.stamp_ns==facts['cutoff']).oracle_received_steady_ns,
            receipt_steady_age_ns=facts['steady_now']-receipt.received_steady_ns,
            healthy=lambda:True)
        return SimpleNamespace(timestamp_ns=facts['cutoff'],
            received_steady_ns=health.evaluation_steady_now_ns,
            pose_x_m=0.,pose_y_m=0.,body_vx_mps=0.,body_vy_mps=0.,body_wz_radps=0.,
            lifecycle_key=(2,3,4),health=health)

    adapter._goal_settle_sample_for_exact_cutoff = make_sample
    final = make_sample({'cutoff':1_300_000_000,'ros_now':1_300_000_000,
        'steady_now':2_600_000_000}, receipt_candidates[1_300_000_000][0], None, None)
    samples, reset_prior = adapter._goal_settle_sample_sequence(
        1_300_000_000, {}, SimpleNamespace(receipt=receipt_candidates[1_300_000_000][0]),
        final, SimpleNamespace(last_ros_ns=1_000_000_000), True)

    assert not reset_prior
    assert [sample.timestamp_ns for sample in samples] == [
        1_100_000_000, 1_300_000_000]
    assert samples[0].health.evaluation_steady_now_ns == 2_115_000_000
    assert samples[0].health.evaluation_ros_now_ns == 1_115_000_000
    from mecanum_nav_rl.simulation.local_training_io import validate_dual_clock_freshness
    with pytest.raises(ValueError, match='input exceeds ROS or local steady receive age'):
        validate_dual_clock_freshness(source_ros_ns=1_090_000_000,
            now_ros_ns=1_300_000_000, receive_steady_ns=2_115_000_000,
            now_steady_ns=2_115_000_000, max_age_ns=100_000_000)
    assert samples[0].health.evaluation_steady_now_ns < ingress.now()
    gaps = [facts for name, facts in events if name == 'GOAL_SETTLE_SAMPLE_GAP']
    expired_backend = next(item for item in gaps if item['cutoff_ns'] == 1_200_000_000
        and item['reason'] == 'joined backend state receive age expired')
    assert expired_backend['backend_receive_age_ns'] > expired_backend['backend_receive_age_limit_ns']
    assert expired_backend['evaluation_steady_ns'] >= expired_backend['backend_received_steady_ns']
    assert expired_backend['sample_source_receive_ns']['backend'] == expired_backend[
        'backend_received_steady_ns']
    assert any(name=='GOAL_SETTLE_ZERO_RECEIPT_SELECTED'
        and facts['sample_collection_steady_ns'] < facts['sample_decision_steady_ns']
        for name, facts in events)


def test_goal_settle_zero_receipt_candidate_rejects_nonzero_and_stale_commands():
    from mecanum_nav_rl.core.issued_command_cutoff import ReceiptSource
    import threading

    adapter = object.__new__(LocalTrainingB1Adapter)
    identity = SimpleNamespace(episode_generation=2, reset_epoch=3,
                               runtime_generation=4)
    receipt = SimpleNamespace(final_publish_sequence=3, lifecycle=identity,
        final_publisher_instance_id=11, source=ReceiptSource.POLICY,
        session_id='bound-session', ingress_config_hash='a'*64,
        publish_stamp_ns=500_000_000, received_steady_ns=1_000_000_000,
        final_command=(0.1, 0.0, 0.0), frame_id='base_link',
        receipt_key='11:3', admission_valid=True)
    source = SimpleNamespace(receipts=[receipt], _receipt_views={3:receipt},
        _application_bytes={}, _application_received_ns={},
        profile={'b1_receipt_max_age_ms':500}, lock=threading.RLock(),
        identity=SimpleNamespace(session_id='bound-session', config_hash='a'*64,
                                 backend_instance_id=13), final_publisher_id=11)
    adapter.ingress = source
    assert adapter._goal_settle_zero_receipt_candidate(1_100_000_000, identity) is None
    receipt.final_command = (0.0, 0.0, 0.0)
    receipt.publish_stamp_ns = 500_000_000
    assert adapter._goal_settle_zero_receipt_candidate(1_100_000_000, identity) is None


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


def test_policy_cutoff_before_final_policy_receipt_is_pending_then_later_cutoff_is_ready():
    """An early scan cutoff waits for the real POLICY receipt; a later one commits normally."""
    from builtin_interfaces.msg import Time
    from mecanum_nav_rl.core.issued_command_cutoff import (
        IssuedCommandReceiptView, PolicyActionIssuance,
    )
    from mecanum_nav_rl.core.lifecycle_types import EpisodeLifecycleIdentity

    lifecycle = EpisodeLifecycleIdentity(1, 1, 2)
    policy = IssuedCommandReceiptView(
        1_510_000_000, 77, 57, ReceiptSource.POLICY, 88, 1, 1, 'step-1',
        lifecycle, 'session', 'a' * 64, (0.1, 0.0, 0.0), 9_990_000_000,
        'base_link', True)
    adjacent = IssuedCommandReceiptView(
        1_530_000_000, 77, 58, ReceiptSource.SAFE_STOP, 99, 2, 0, '',
        lifecycle, 'session', 'a' * 64, (0.0, 0.0, 0.0), 10_010_000_000,
        'base_link', True)
    adapter = object.__new__(LocalTrainingB1Adapter)
    adapter.ingress = SimpleNamespace(
        final_publisher_id=77,
        identity=SimpleNamespace(session_id='session', config_hash='a' * 64),
        lifecycle=SimpleNamespace(barrier_stamp=Time(sec=1, nanosec=0)),
        receipts=(policy, adjacent))
    adapter.scales = (0.25, 0.2, 0.8)
    adapter.action_barrier_ns = 1_490_000_000
    adapter.issuance = PolicyActionIssuance(88, 1, lifecycle, 1, 'step-1')
    early = {'identity':lifecycle, 'cutoff':1_500_000_000,
        'ros_now':1_540_000_000, 'steady_now':10_050_000_000}
    later = {**early, 'cutoff':1_520_000_000}

    with pytest.raises(B1SnapshotPending, match='POLICY receipt follows observation cutoff'):
        adapter._selection(early, reset=False)
    selected = adapter._selection(later, reset=False)
    assert selected.status.value == 'ready'
    assert selected.receipt.final_publish_sequence == 57
    assert selected.adjacent_receipt.final_publish_sequence == 58


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
