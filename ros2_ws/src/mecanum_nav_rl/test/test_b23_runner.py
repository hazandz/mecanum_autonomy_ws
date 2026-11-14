"""Biên deadline/ownership worker bằng I/O fakes, không tạo ROS context."""
import asyncio
import json
import threading
from types import SimpleNamespace as NS
import pytest
from mecanum_nav_rl.runtime_simulation.b23_runner import (
    TrainingWorkerIO, case_environment, case_fault_hooks, technical_outcome,
    verify_r01b_external_pause_rejection, verify_r01_pause_ack_failure,
    verify_r02_policy_order, verify_r02f_safety_hold,
)


def test_case_phase_is_bound_in_packet_and_capacity_one_guard():
    from mecanum_nav_rl.runtime_simulation.b23_runner import campaign_phase, verify_guard_authority
    assert campaign_phase('R01a') == 'smoke'
    assert campaign_phase('R01e') == 'fault_task'
    assert campaign_phase('R02a') == 'fault_task'
    assert campaign_phase('R02b') == 'fault_task'
    assert campaign_phase('R02f') == 'fault_task'
    assert campaign_phase('R08') == 'soak'
    packet = {'case': 'R01e', 'run_id': 'B23_R01E_TEST'}
    authority = {'run_id': packet['run_id'], 'capacity': 1, 'packet_sha256': 'a'*64,
        'phase': 'fault_task', 'consumed': False}
    assert verify_guard_authority(packet, authority, 'a'*64) == 'fault_task'
    for key, bad in [('phase', 'smoke'), ('run_id', 'B23_R01A_TEST'),
                     ('capacity', 2), ('packet_sha256', 'b'*64), ('consumed', True)]:
        original = authority[key]
        authority[key] = bad
        with pytest.raises(RuntimeError, match='authority does not match packet case/phase'):
            verify_guard_authority(packet, authority, 'a'*64)
        authority[key] = original
    with pytest.raises(ValueError, match='unsupported B2.3 campaign case'):
        campaign_phase('R02c')


def test_d04_soak_schedule_and_unit_budget_are_exact():
    from mecanum_nav_rl.runtime_simulation.b23_runner import soak_action, service_properties_for
    assert soak_action(0, 1) == (0., 0., 0.)
    assert soak_action(0, 5) == (0., 0., 0.)
    assert soak_action(0, 6) == (0.40, 0., 0.)
    assert soak_action(1, 25) == (-0.40, 0., 0.)
    assert soak_action(5, 6) == (0.30, -0.25, 0.30)
    assert soak_action(29, 26) == (0., 0., 0.)
    assert len([soak_action(i, step) for i in range(30)
        for step in range(1, (34 if i < 10 else 33)+1)]) == 1000
    assert 'RuntimeMaxSec=180s' in service_properties_for(120)
    assert 'RuntimeMaxSec=960s' in service_properties_for(900)
    with pytest.raises(ValueError, match='active runtime budget'):
        service_properties_for(180)


def test_case_hook_and_assessment_are_bound_to_packet_case():
    assert case_fault_hooks('R01a') == []
    assert case_fault_hooks('R01b') == ['external_pause_after_w1_before_native_dispatch']
    assert case_fault_hooks('R01c') == ['delay_native_pause_ack_1500ms_once']
    assert case_fault_hooks('R01d') == ['drop_native_pause_ack_once']
    assert case_fault_hooks('R01e') == ['pause_request_replay_after_terminal']
    assert case_fault_hooks('R02a') == []
    assert case_fault_hooks('R02b') == ['native_hold_admission_until_receipt']
    assert case_fault_hooks('R02f') == ['safety_hold_after_adapter_issuance']
    assert case_environment('R02b',case_fault_hooks('R02b')) == {
        'B23_ADMISSION_ORDER_FAULT':'receipt_before_admission'}
    assert case_environment('R01c', case_fault_hooks('R01c')) == {
        'B23_PAUSE_ACK_FAULT':'delay_1500ms_once'}
    assert case_environment('R01d', case_fault_hooks('R01d')) == {
        'B23_PAUSE_ACK_FAULT':'drop_once'}
    assert case_environment('R01a', []) == {}
    with pytest.raises(ValueError, match='not approved for campaign case'):
        case_fault_hooks('R01a', 'pause_request_replay_after_terminal')
    assert technical_outcome('R01a', True) == 'R01a_COMPLETED'
    assert technical_outcome('R01e', True) == 'R01e_COMPLETED'
    assert technical_outcome('R01e', False) == 'INCOMPLETE'


def test_r02f_requires_policy_hold_rejection_and_exact_zero_native_receipt():
    from mecanum_nav_rl.core.issued_command_cutoff import ReceiptSource
    from mecanum_nav_rl_interfaces.msg import CommandEnvelope
    receipt=NS(source=ReceiptSource.SAFE_STOP, final_command=(0.,0.,0.),
        final_publisher_instance_id=17, final_publish_sequence=42)
    state=NS(fault_flags=0, local_zero_override=False, applied_receipt_valid=True,
        applied_final_publisher_instance_id=17, applied_final_publish_sequence=42,
        applied_physics_iteration=101)
    io=NS(events=[('SAFETY_REJECTED', {'sequence':7,
        'source':CommandEnvelope.SOURCE_SAFE_STOP,
        'candidate_sequence':1,'candidate_source':CommandEnvelope.SOURCE_POLICY,
        'candidate_source_instance_id':33,'reasons':['POLICY_HELD']})],
        ingress=NS(receipts=[]), policy_source_id=33)
    result=verify_r02f_safety_hold(io,step_index=1,receipt=receipt,backend_state=state)
    assert result == {'safety_rejected':True,'reasons':['POLICY_HELD'],
        'safe_stop_applied':True,'final_publish_sequence':42,'backend_iteration':101,
        'policy_receipt_absent':True}
    io.events=[]
    with pytest.raises(RuntimeError,match='Safety rejection'):
        verify_r02f_safety_hold(io,step_index=1,receipt=receipt,backend_state=state)
    io.events=[('SAFETY_REJECTED', {'sequence':7,
        'source':CommandEnvelope.SOURCE_SAFE_STOP,
        'candidate_sequence':1,'candidate_source':CommandEnvelope.SOURCE_POLICY,
        'candidate_source_instance_id':33,'reasons':['POLICY_HELD']})]
    io.ingress.receipts=[NS(source=ReceiptSource.POLICY,sequence=1)]
    with pytest.raises(RuntimeError,match='reached the final receipt'):
        verify_r02f_safety_hold(io,step_index=1,receipt=receipt,backend_state=state)


def test_final_publication_view_selects_retained_receipt_for_exact_safety_sequence():
    from rclpy.serialization import serialize_message
    from mecanum_nav_rl_interfaces.msg import FinalIssuedCommandReceipt
    from mecanum_nav_rl.core.issued_command_cutoff import ReceiptSource
    from mecanum_nav_rl.runtime_simulation.b23_runner import FinalPublicationView
    expected = FinalIssuedCommandReceipt()
    expected.source = expected.SOURCE_SAFE_STOP
    expected.sequence = 31
    expected.source_instance_id = 44
    expected.final_publisher_instance_id = 55
    expected.final_publish_sequence = 20
    expected.final_command.linear.x = expected.final_command.linear.y = 0.
    expected.final_command.angular.z = 0.
    view = FinalPublicationView(55)
    view.ingress = NS(
        receipts=[
            NS(source=ReceiptSource.SAFE_STOP, source_sequence=31,
                final_publisher_instance_id=55, final_publish_sequence=20),
            NS(source=ReceiptSource.SAFE_STOP, source_sequence=32,
                final_publisher_instance_id=55, final_publish_sequence=21),
        ],
        _receipt_bytes={20:serialize_message(expected)},
    )
    selected = view.publication_for_source_sequence(
        source=FinalIssuedCommandReceipt.SOURCE_SAFE_STOP, sequence=31)
    assert selected is not None
    assert selected.sequence == 31 and selected.final_publish_sequence == 20
    assert view.publication_for_source_sequence(
        source=FinalIssuedCommandReceipt.SOURCE_SAFE_STOP, sequence=30) is None


def test_r02_order_assessment_requires_actual_native_gate_timestamps(tmp_path):
    import json
    path=tmp_path/'native-events.jsonl'
    rows=[
        {'kind':'B23_POLICY_RECEIPT_INGRESS','fields':{'step':'1','receive_ns':'300'}},
        {'kind':'B23_ADMISSION_ACCEPTED','fields':{'receive_ns':'100','processed_ns':'200'}},
    ]
    path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
    assert verify_r02_policy_order(tmp_path,case='R02a',step_started_ns=50)['order']=='admission_before_receipt'
    rows[0]['fields']['receive_ns']='150'
    rows[1]['fields']['receive_ns']='100'; rows[1]['fields']['processed_ns']='200'
    rows.append({'kind':'B23_POLICY_ADMISSION_HELD','fields':{'receive_ns':'100'}})
    path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
    assert verify_r02_policy_order(tmp_path,case='R02b',step_started_ns=50)['order']=='receipt_before_admission'
    rows[0]['fields']['receive_ns']='300'
    path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
    with pytest.raises(RuntimeError,match='order mismatch'):
        verify_r02_policy_order(tmp_path,case='R02b',step_started_ns=50)


def test_r01b_requires_native_unexpected_pause_and_zero_without_reset_commit():
    from mecanum_nav_rl_interfaces.srv import LocalTrainingBackendControl as Control
    from mecanum_nav_rl.runtime_simulation.local_training_coordinator import BackendControlError
    response = Control.Response()
    response.result = response.RESULT_REJECTED
    response.reason_code = response.REASON_BARRIER_INVALID
    ack = NS(response=response, request=NS(request_sequence=24))
    error = BackendControlError('backend rejected pause', ack)
    io = NS(events=[('FAULT_HOOK_EXTERNAL_PAUSE_AFTER_W1', {'sequence': 11})],
        ingress=NS(backend_state=NS(fault_flags=1, local_zero_override=True)))
    result = verify_r01b_external_pause_rejection(io, error)
    assert result == {'reason_code': response.REASON_BARRIER_INVALID,
        'request_sequence': 24, 'native_fault_flags': 1, 'local_zero_override': True,
        'no_pose_mutation': True, 'no_observation0_commit': True}
    io.events.append(('B1_RESET_COMMITTED', {}))
    with pytest.raises(RuntimeError, match='continued reset'):
        verify_r01b_external_pause_rejection(io, error)
    io.events = [('FAULT_HOOK_EXTERNAL_PAUSE_AFTER_W1', {})]
    io.ingress.backend_state.local_zero_override = False
    with pytest.raises(RuntimeError, match='zero override'):
        verify_r01b_external_pause_rejection(io, error)


def test_r01c_d_wait_bounded_for_native_fault_status_after_expired_ack():
    from mecanum_nav_rl_interfaces.srv import LocalTrainingBackendControl as Control
    from mecanum_nav_rl.runtime_simulation.local_training_coordinator import BackendControlError
    response = Control.Response()
    response.result = response.RESULT_REJECTED
    response.reason_code = response.REASON_CONTROL_EXPIRED
    error = BackendControlError('native pause ACK expired', NS(response=response))
    clock = NS(ns=10_000_000_000)
    state = NS(fault_flags=0, local_zero_override=False)
    async def pause(duration):
        clock.ns += int(duration * 1e9)
        if clock.ns >= 10_050_000_000:
            state.fault_flags, state.local_zero_override = 1, True
    io = NS(events=[], now=lambda:clock.ns, pause=pause, deadline_ns=11_000_000_000,
        ingress=NS(backend_state=state))
    result = asyncio.run(verify_r01_pause_ack_failure(io, error))
    assert result['reason_code'] == response.REASON_CONTROL_EXPIRED
    assert result['native_fault_flags'] == 1 and result['local_zero_override'] is True
    assert result['no_pose_mutation'] and result['no_observation0_commit']
    io.events.append(('B1_RESET_COMMITTED', {}))
    with pytest.raises(RuntimeError, match='continued reset'):
        asyncio.run(verify_r01_pause_ack_failure(io, TimeoutError('late ACK')))


def test_r01c_d_fail_when_native_fault_status_never_arrives():
    clock = NS(ns=20_000_000_000)
    async def pause(duration): clock.ns += int(duration * 1e9)
    io = NS(events=[], now=lambda:clock.ns, pause=pause, deadline_ns=21_000_000_000,
        ingress=NS(backend_state=NS(fault_flags=0, local_zero_override=False)))
    with pytest.raises(RuntimeError, match='did not retain native fault and zero override'):
        asyncio.run(verify_r01_pause_ack_failure(io, TimeoutError('bounded fault timeout')))


class Clock:
    def __init__(self): self.ns = 1_000_000_000
    def now(self): return self.ns
    async def pause(self, seconds):
        self.ns += round(seconds * 10**9)
        await asyncio.sleep(0)


def worker():
    value = TrainingWorkerIO.__new__(TrainingWorkerIO)
    clock = Clock()
    value.now, value.pause = clock.now, clock.pause
    value.deadline_ns = clock.ns + 100_000_000
    value.stop_requested, value.abort_requested = False, None
    value.pump_error, value.expected_paused = None, True
    value.last_clock_ns, value.last_clock_advance_ns = 0, clock.ns
    value.node = NS(get_clock=lambda: NS(now=lambda: NS(nanoseconds=0)))
    value.emit = lambda _name, _facts: None
    value.ingress = NS(fault=None, backend_state=None)
    return value, clock


def test_until_waits_in_common_budget_and_does_not_accept_late_data():
    value, clock = worker()
    deadline = clock.ns + 5_000_000
    seen = []
    def observation():
        seen.append(clock.ns)
        return 'ready' if clock.ns >= 1_004_000_000 else None
    assert asyncio.run(value.until(observation, deadline_ns=deadline, phase='test')) == 'ready'
    assert seen == [1_000_000_000, 1_002_000_000, 1_004_000_000]
    value, clock = worker()
    def late():
        clock.ns += 6_000_000
        return 'ready'
    with pytest.raises(TimeoutError, match='completed late'):
        asyncio.run(value.until(late, deadline_ns=1_005_000_000, phase='test'))


def test_until_none_and_frozen_pause_fail_bounded():
    value, clock = worker()
    with pytest.raises(TimeoutError, match='deadline expired'):
        asyncio.run(value.until(lambda: None, deadline_ns=clock.ns + 5_000_000, phase='none'))
    assert clock.ns == 1_005_000_000
    value, clock = worker()
    async def frozen(seconds): await asyncio.sleep(0)
    value.pause = frozen
    with pytest.raises(RuntimeError, match='did not advance'):
        asyncio.run(value.until(lambda: None, deadline_ns=clock.ns + 5_000_000, phase='frozen'))


def test_active_deadline_is_never_extended_by_predicate_budget():
    value, clock = worker()
    value.deadline_ns = clock.ns + 3_000_000
    with pytest.raises(TimeoutError):
        asyncio.run(value.until(lambda: None, deadline_ns=clock.ns + 10_000_000, phase='test'))
    assert clock.ns == value.deadline_ns == 1_003_000_000


def test_terminal_pause_replay_resubmits_exact_owned_bytes_and_records_evidence():
    value, clock = worker()
    from rclpy.serialization import serialize_message
    from mecanum_nav_rl.runtime_simulation.local_training_coordinator import BackendControlAck
    from mecanum_nav_rl_interfaces.srv import LocalTrainingBackendControl as Control
    request = Control.Request(); request.request_sequence = 17
    response = Control.Response(); response.schema_version = response.RESPONSE_SCHEMA_VERSION
    response.result = response.RESULT_APPLIED; response.reason_code = response.REASON_NONE
    response.request_sequence = 17; response.backend_instance_id = 22
    response.binding_revision = response.applied_binding_revision = 4
    response.applied_physics_iteration = 90
    original = BackendControlAck(serialize_message(request), serialize_message(response), clock.ns)
    # Response CDR bytes can differ in padding after ROSIDL serialization;
    # the replay contract is exact request plus the same decoded response fields.
    replayed = NS(request_bytes=original.request_bytes, response_bytes=b'raw-replay-cdr-differs',
                  response=response, observed_steady_ns=clock.ns + 1)
    calls, events = [], []
    async def replay(ack, *, deadline_ns):
        calls.append((ack, deadline_ns))
        return replayed
    value.pause_ack = original
    value.control = NS(replay=replay)
    value.emit = lambda name, fields: events.append((name, fields))
    assert asyncio.run(value.replay_pause_intent_after_terminal()) is replayed
    assert calls == [(original, value.deadline_ns)]
    assert events[0][0] == 'PAUSE_INTENT_EXACT_REPLAY_AFTER_TERMINAL'
    assert events[0][1]['request_sequence'] == 17
    assert events[0][1]['exact_request_bytes'] is True
    assert events[0][1]['semantic_response_match'] is True
    assert events[0][1]['original_response_cdr_hex'] != events[0][1]['response_cdr_hex']


def test_terminal_pause_replay_rejects_different_response_bytes():
    value, clock = worker()
    from rclpy.serialization import serialize_message
    from mecanum_nav_rl.runtime_simulation.local_training_coordinator import BackendControlAck
    from mecanum_nav_rl_interfaces.srv import LocalTrainingBackendControl as Control
    request = Control.Request(); request.request_sequence = 4
    response = Control.Response(); response.schema_version = response.RESPONSE_SCHEMA_VERSION
    response.result = response.RESULT_APPLIED; response.request_sequence = 4
    original = BackendControlAck(serialize_message(request), serialize_message(response), clock.ns)
    rejected = Control.Response(); rejected.schema_version = rejected.RESPONSE_SCHEMA_VERSION
    rejected.result = rejected.RESULT_REJECTED; rejected.request_sequence = 4
    value.pause_ack = original
    async def replay(ack, *, deadline_ns):
        return NS(request_bytes=ack.request_bytes, response_bytes=b'different',
                  response=rejected, observed_steady_ns=clock.ns)
    value.control = NS(replay=replay)
    value.emit = lambda *_: None
    with pytest.raises(RuntimeError, match='semantic response differs'):
        asyncio.run(value.replay_pause_intent_after_terminal())


def test_abort_native_fault_and_callback_error_remain_visible():
    value, clock = worker()
    value.abort_requested = 'SIGTERM'
    with pytest.raises(RuntimeError, match='SIGTERM'):
        asyncio.run(value.until(lambda: True, deadline_ns=clock.ns + 1_000_000, phase='test'))
    value.abort_requested = None
    value.pump_error = ValueError('callback invalid')
    with pytest.raises(RuntimeError, match='callback failed') as error:
        value.check()
    assert str(error.value.__cause__) == 'callback invalid'
    value.pump_error = None; value.ingress.backend_state = NS(fault_flags=64)
    with pytest.raises(RuntimeError, match='fault flags=64'):
        value.check()


@pytest.fixture
def native_reader(tmp_path):
    value, clock = worker()
    path = tmp_path/'native-events.jsonl'
    value.descriptor = dict(native_events_path=str(path), run_id='B23_TEST', session_id='own-session',
        backend_instance_id=22, coordinator_ingress_instance_id=11,
        server_leader_pid=777, invocation_id='inv-1')
    value._native_offset, value._native_partial, value._native_input_watermark = 0, b'', 0
    record = dict(kind='B23_SAFETY_INPUT_OBSERVED',
        fields=dict(session='own-session', backend='22', ingress='11', sample='9'),
        server_leader_pid=777, invocation_id='inv-1')
    return value, path, record


def test_native_ack_reader_retains_partial_and_raw_ownership(native_reader):
    value, path, record = native_reader
    assert value.read_native_input_watermark() == 0
    raw = json.dumps(record).encode() + b'\n'
    path.write_bytes(raw[:20])
    assert value.read_native_input_watermark() == 0
    with path.open('ab') as stream: stream.write(raw[20:])
    assert value.read_native_input_watermark() == 9
    assert value.read_native_input_watermark() == 9


@pytest.mark.parametrize('key,bad', [('invocation_id', 'inv-2'), ('server_leader_pid', 888)])
def test_native_ack_other_invocation_cannot_supply_drain_proof(native_reader, key, bad):
    value, path, record = native_reader
    record[key] = bad
    path.write_text(json.dumps(record) + '\n')
    with pytest.raises(RuntimeError, match='ownership mismatch'):
        value.read_native_input_watermark()
    assert value._native_input_watermark == 0


@pytest.mark.parametrize('key,bad', [('session', 'other'), ('backend', '23'), ('ingress', '12')])
def test_native_ack_other_source_cannot_supply_drain_proof(native_reader, key, bad):
    value, path, record = native_reader
    record['fields'][key] = bad
    path.write_text(json.dumps(record) + '\n')
    with pytest.raises(RuntimeError, match='ownership mismatch'):
        value.read_native_input_watermark()


def test_native_ack_corrupt_complete_record_is_not_an_empty_scan(native_reader):
    value, path, record = native_reader
    path.write_bytes(b'{invalid json}\n')
    with pytest.raises(json.JSONDecodeError):
        value.read_native_input_watermark()
    assert value._native_input_watermark == 0


def test_native_policy_admission_ack_is_bound_before_stream_freeze(native_reader):
    value, path, record = native_reader
    record['kind'] = 'B23_ADMISSION_ACCEPTED'
    path.write_text(json.dumps(record) + '\n')
    assert value.read_native_input_watermark() == 9


@pytest.mark.parametrize('last_source', ['safe_stop', 'policy'])
def test_freeze_step_streams_keeps_zero_receipts_alive_under_native_watchdog(last_source):
    from mecanum_nav_rl_interfaces.msg import CommandEnvelope
    value, clock = worker()
    calls, events = [], []
    source = CommandEnvelope.SOURCE_SAFE_STOP if last_source == 'safe_stop' else CommandEnvelope.SOURCE_POLICY
    adapter = NS(safe_stop_sequence=7, last_output=NS(source=source, source_instance_id=44, sequence=7),
        set_policy_hold=lambda hold: calls.append(('hold', hold)),
        set_stream_enabled=lambda enabled: calls.append(('stream', enabled)))
    value.safety = NS(local_training=adapter)
    value.ingress.last_published_sample_sequence = 9
    value.ingress.pause_admission_publication = lambda: calls.append(('pause_admission',))
    value.read_native_input_watermark = lambda: 9
    stop = NS(SOURCE_SAFE_STOP=CommandEnvelope.SOURCE_SAFE_STOP)
    value.final = NS(publisher_instance_id=55, last_publication=NS(source=source,
        source_instance_id=44, sequence=7, final_publish_sequence=20))
    value.ingress.backend_state = NS(fault_flags=0, applied_final_publish_sequence=20,
        applied_final_publisher_instance_id=55, local_zero_override=False)
    value.last_safe_stop_publish_sequence = 20
    async def pause(seconds):
        await clock.pause(seconds)
        adapter.safe_stop_sequence = 8
        adapter.last_output = NS(source=stop.SOURCE_SAFE_STOP, source_instance_id=44, sequence=8)
        value.final.last_publication = NS(source=stop.SOURCE_SAFE_STOP,
            source_instance_id=44, sequence=8, final_publish_sequence=21)
        value.ingress.backend_state.applied_final_publish_sequence = 21
    value.pause = pause
    value.emit = lambda name, record: (calls.append((name, record)), events.append((name, record)))
    asyncio.run(value.freeze_step_streams(deadline_ns=clock.ns+20_000_000))
    assert ('hold', True) in calls
    assert ('stream', True) in calls
    assert ('stream', False) not in calls
    assert adapter.last_output.source == CommandEnvelope.SOURCE_SAFE_STOP
    assert calls.index(('hold', True)) < calls.index(('stream', True))
    assert events[-1][0] == 'STEP_STREAMS_FROZEN'
    assert events[-1][1]['source'] == CommandEnvelope.SOURCE_SAFE_STOP
    assert events[-1][1]['publish_sequence'] == 21


@pytest.mark.parametrize('timing', ['ready','late_commit','late_publish'])
def test_policy_step_orders_ack_sample_issue_safety_application_and_commit(timing):
    from builtin_interfaces.msg import Time
    from mecanum_nav_rl_interfaces.msg import CommandEnvelope, LocalTrainingSafetyInput, SafetyLifecycleState
    from mecanum_nav_rl_interfaces.srv import LocalTrainingBackendControl as Control
    from mecanum_nav_rl.runtime_simulation.local_training_coordinator import BackendControlAck, B1SnapshotPending
    from rclpy.serialization import serialize_message
    value, clock = worker()
    value.deadline_ns = clock.ns + 3_000_000_000
    ros = lambda: clock.ns
    value.ros_now = ros
    value.document = {'training': {'local_training': {'max_vx_mps': .25, 'max_vy_mps': .2, 'max_wz_radps': .8}}}
    value.policy_source_id = 33
    history = []
    life = SafetyLifecycleState(); life.barrier_stamp = Time(nanosec=900_000_000)
    life.episode_generation, life.reset_epoch, life.runtime_generation = 1, 2, 3
    adapter = NS(safe_stop_sequence=1,
        last_output=NS(source=CommandEnvelope.SOURCE_SAFE_STOP, source_instance_id=44, sequence=1),
        command=None, noisy=None, set_stream_enabled=lambda state: history.append(('stream', state)),
        set_policy_hold=lambda state: history.append(('hold', state)))
    value.safety = NS(local_training=adapter)
    value.final = NS(publisher_instance_id=55, last_publication=NS(source=CommandEnvelope.SOURCE_SAFE_STOP,
        source_instance_id=44, sequence=1, final_publish_sequence=2))
    value.ingress.lifecycle = life
    value.ingress.last_published_sample_sequence = 1
    value.ingress.pause_admission_publication = lambda: history.append(('freeze_admission',))
    value.ingress.scans = {}
    value.ingress.profile = {'safety_period_ms':20, 'final_command_timeout_ms':100,
        'scan_max_age_ms':500}
    value.ingress.backend_state = NS(fault_flags=0, applied_final_publish_sequence=2,
        applied_final_publisher_instance_id=55, local_zero_override=False)
    value.read_native_input_watermark = lambda: 1
    def emit(event, facts):
        history.append((event, facts))
        if event == 'POLICY_STEP_COMPLETE' and timing == 'late_publish': clock.ns = 3_000_000_000
    value.emit = emit
    async def transact(operation, **fields):
        history.append(('bind', operation))
        req, res = Control.Request(), Control.Response()
        req.operation = operation; req.pending_step_index = fields['pending_step_index']
        req.action_barrier_stamp = fields['action_barrier_stamp']
        res.pending_admission_token = [7]*16
        return BackendControlAck(serialize_message(req), serialize_message(res), clock.ns)
    value.control = NS(transact=transact)
    armed = []
    def arm(ack):
        history.append(('arm', ack.observed_steady_ns)); armed.append(ack)
    value.ingress.arm_pending = arm
    def publish(envelope):
        history.append(('publish', envelope)); adapter.command = envelope
    value.policy_publisher = NS(publish=publish)
    async def pause(seconds):
        await clock.pause(seconds)
        if armed:
            value.ingress.last_published_sample_sequence = 2
            adapter.noisy = NS(admission_state=LocalTrainingSafetyInput.ADMISSION_POLICY_OPEN,
                admission_token=[7]*16, sample_sequence=2)
        else:
            adapter.safe_stop_sequence = 2
            adapter.last_output = NS(source=CommandEnvelope.SOURCE_SAFE_STOP,
                source_instance_id=44, sequence=2)
            value.final.last_publication = NS(source=CommandEnvelope.SOURCE_SAFE_STOP,
                source_instance_id=44, sequence=2, final_publish_sequence=3)
            value.ingress.backend_state.applied_final_publish_sequence = 3
        if adapter.command:
            value.ingress.scans[clock.ns] = True
    value.pause = pause
    pending = NS(step_index=1, transition_id='actual-b1-token')
    commit_calls = []
    def record(envelope, *, action_barrier_ns):
        nonlocal minimum_cutoff
        history.append(('issued', envelope.sequence))
        assert history[-2][0] == 'publish'
        assert action_barrier_ns <= envelope.header.stamp.sec*10**9+envelope.header.stamp.nanosec
        minimum_cutoff = envelope.header.stamp.sec*10**9+envelope.header.stamp.nanosec + 100_000_000
    transition = object()
    minimum_cutoff = None
    def commit(cutoff):
        commit_calls.append(cutoff)
        if minimum_cutoff is None:
            raise B1SnapshotPending('application not received yet')
        if cutoff == minimum_cutoff:
            raise B1SnapshotPending('receipt boundary at cutoff is not applied')
        if timing == 'late_commit': clock.ns = 3_000_000_000
        return transition
    b1 = NS(begin_step=lambda: pending, record_issuance=record, commit_step=commit)
    if timing == 'ready':
        assert asyncio.run(value.policy_step(b1, (0., .4, 0.))) is transition
    else:
        with pytest.raises(TimeoutError, match='step deadline'):
            asyncio.run(value.policy_step(b1, (0., .4, 0.)))
    tags = [row[0] for row in history]
    assert tags.index('hold') < tags.index('bind') < tags.index('arm') < tags.index('publish') < tags.index('issued')
    assert ('hold', True) in history
    assert ('stream', True) in history
    stream_off = history.index(('stream', False))
    bind = next(i for i, row in enumerate(history) if row[0] == 'bind')
    issued = next(i for i, row in enumerate(history) if row[0] == 'issued')
    stream_on_after_issue = next(i for i, row in enumerate(history)
        if i > issued and row == ('stream', True))
    hold_off_after_issue = next(i for i, row in enumerate(history)
        if i > issued and row == ('hold', False))
    assert stream_off < bind < issued < stream_on_after_issue < hold_off_after_issue
    envelope = next(row[1] for row in history if row[0] == 'publish')
    assert envelope.twist.linear.y == pytest.approx(.08)
    assert len([row for row in history if row[0] == 'publish']) == 1
    assert len(commit_calls) >= 2
    expected_minimum = envelope.header.stamp.sec*10**9 + envelope.header.stamp.nanosec + 100_000_000
    assert min(commit_calls) == expected_minimum
    assert commit_calls[-1] > expected_minimum
    assert clock.ns < 3_000_000_000 if timing == 'ready' else clock.ns == 3_000_000_000
    assert all(row[0] != 'align_policy_boundary' for row in history)
    assert ('stream', False) in history  # only pending-step freeze before bind
    assert not any(i > issued and row == ('stream', False) for i, row in enumerate(history))


def test_evidence_sink_routes_actual_server_output_and_keeps_books_distinct(tmp_path):
    from mecanum_nav_rl.runtime_simulation.b23_runner import RunEvidence
    sink = RunEvidence(tmp_path, 'parent', run_id='run', invocation_id='inv-1')
    facts = dict(process='server', pid=777, command=['gz', 'sim'], stream='stdout',
        text='[Msg] B23_ADMISSION_ACCEPTED session=run backend=22 ingress=11 sample=9')
    sink.record('owned_process_output', facts)
    sink.record('policy_backend_applied', {'step_index': 1})
    sink.close()
    raw = (tmp_path/'native-events.jsonl').read_bytes().splitlines()
    assert len(raw) == 1
    record = json.loads(raw[0])
    assert record['server_leader_pid'] == 777 and record['invocation_id'] == 'inv-1'
    assert record['fields']['sample'] == '9' and record['raw_record']['facts'] == facts
    assert len((tmp_path/'policy_backend_applied.jsonl').read_bytes().splitlines()) == 1
    assert not (tmp_path/'policy_adapter_issued.jsonl').exists()
    with pytest.raises(RuntimeError, match='already closed'):
        sink.record('late', {})


def test_cleanup_ack_is_bound_to_exact_batch_after_flush(tmp_path, monkeypatch):
    from mecanum_nav_rl.runtime_simulation import b23_runner as module
    from mecanum_nav_bringup.local_training_process_supervisor import CleanupEvidenceBatch
    clock = NS(ns=1_000_000_000)
    monkeypatch.setattr(module.time, 'monotonic', lambda: clock.ns/1e9)
    monkeypatch.setattr(module.time, 'monotonic_ns', lambda: clock.ns)
    sink = module.RunEvidence(tmp_path, 'parent', run_id='run', invocation_id='inv-1')
    sink.record('application', {'key': [55, 2]})
    batch = CleanupEvidenceBatch('batch-1', ())
    ack = asyncio.run(sink.cleanup_publisher(batch, 2.))
    assert ack.batch_id == 'batch-1' and ack.acknowledged
    assert json.loads((tmp_path/'cleanup-ack.json').read_bytes())['batch_id'] == 'batch-1'
    sink.close()
    second = tmp_path/'late'; second.mkdir()
    sink = module.RunEvidence(second, 'parent', run_id='run', invocation_id='inv-1')
    def late_sync(): clock.ns = 3_000_000_000
    monkeypatch.setattr(sink, 'sync', late_sync)
    with pytest.raises(TimeoutError, match='after deadline'):
        asyncio.run(sink.cleanup_publisher(batch, 2.))
    assert (second/'cleanup-batch.json').exists() and not (second/'cleanup-ack.json').exists()


def test_immutable_record_refuses_to_overwrite_consumed_evidence(tmp_path):
    from mecanum_nav_rl.runtime_simulation.b23_runner import write_record_once
    import hashlib
    path = tmp_path/'record.json'
    expected = write_record_once(path, {'run_id': 'run'})
    raw = path.read_bytes()
    assert raw.endswith(b'\n') and expected == hashlib.sha256(raw).hexdigest()
    with pytest.raises(FileExistsError): write_record_once(path, {'run_id': 'other'})
    assert path.read_bytes() == raw


def test_proc_identity_argv_and_start_ticks_are_derived_from_saved_bytes(monkeypatch):
    from mecanum_nav_rl.runtime_simulation import b23_runner as module
    from pathlib import Path
    fields = {3:'S', 4:'55', 5:'77', 6:'77', 22:'12345'}
    stat = b'77 (worker (owned)) ' + ' '.join(fields.get(i, '0') for i in range(3, 24)).encode()
    raw = {'stat': stat,
        'status': b'Name:\tworker\nUid:\t1000\t1000\t1000\t1000\n',
        'cmdline': b'/pinned/python\0-B\0-m\0b23_runner\0',
        'cgroup': b'0::/user.slice/user-1000.slice/user@1000.service/app.slice/b23-test.service\n'}
    monkeypatch.setattr(Path, 'read_bytes', lambda path: raw[path.name])
    result = module.process_identity(77)
    assert result['argv'] == ['/pinned/python','-B','-m','b23_runner']
    assert result['start_ticks'] == 12345 and result['uid'] == 1000
    assert result['raw_hex'] == {name:value.hex() for name,value in raw.items()}
    assert (result['ppid'], result['pgid'], result['sid']) == (55,77,77)


def test_cgroup_scan_read_error_and_incomplete_walk_are_never_empty(monkeypatch):
    from mecanum_nav_rl.runtime_simulation import b23_runner as module
    from pathlib import Path
    import os
    path = '/user.slice/user-1000.slice/user@1000.service/app.slice/b23-test.service'
    monkeypatch.setattr(Path, 'stat', lambda p, *a, **k: object())
    monkeypatch.setattr(os, 'walk', lambda p, **kwargs: iter([(str(p), [], ['cgroup.procs'])]))
    def denied(path): raise PermissionError('test denied cgroup.procs')
    monkeypatch.setattr(Path, 'read_bytes', denied)
    result = module.scan_pinned_cgroup(path)
    assert result['status'] == 'incomplete' and result['errors'] and not result['files']
    monkeypatch.setattr(os, 'walk', lambda p, **kwargs: iter([]))
    result = module.scan_pinned_cgroup(path)
    assert result['status'] == 'incomplete'
    def missing(path, *a, **k): raise FileNotFoundError('exact pinned path removed')
    monkeypatch.setattr(Path, 'stat', missing)
    result = module.scan_pinned_cgroup(path)
    assert result['status'] == 'path_removed_confirmed' and not result['errors']
    with pytest.raises(ValueError, match='unverified'):
        module.scan_pinned_cgroup('/')


def test_cgroup_walk_error_is_preserved_even_if_one_procs_file_is_empty(monkeypatch):
    from mecanum_nav_rl.runtime_simulation import b23_runner as module
    from pathlib import Path
    import os
    monkeypatch.setattr(Path, 'stat', lambda *a, **k: object())
    monkeypatch.setattr(Path, 'read_bytes', lambda p: b'')
    def walk(path, **kwargs):
        kwargs['onerror'](OSError('child cgroup unreadable'))
        yield str(path), [], ['cgroup.procs']
    monkeypatch.setattr(os, 'walk', walk)
    result = module.scan_pinned_cgroup('/user.slice/user-1000.slice/user@1000.service/b23-test.service')
    assert result['status'] == 'incomplete' and result['files'] and result['errors']


def test_command_adapter_preserves_timeout_bytes_and_exit(monkeypatch):
    from mecanum_nav_rl.runtime_simulation import b23_runner as module
    import subprocess
    calls = []
    def execute(argv, **kwargs):
        calls.append((argv,kwargs)); raise subprocess.TimeoutExpired(argv, kwargs['timeout'], b'raw output', b'bus denied')
    monkeypatch.setattr(subprocess, 'run', execute)
    result = module.command_record(['systemctl','--user','show'], timeout_s=.5)
    assert result['error'] == 'timeout' and result['returncode'] is None
    assert bytes.fromhex(result['stderr_hex']) == b'bus denied' and result['stdout'] == 'raw output'
    assert calls[0][1]['timeout'] == .5
    assert module.command_record(['systemctl'], timeout_s=0)['error'] == 'no_remaining_budget'
    assert len(calls) == 1


def test_main_invalid_case_and_child_without_guard_never_start_ros(tmp_path, monkeypatch):
    from mecanum_nav_rl.runtime_simulation import b23_runner as module
    with pytest.raises(SystemExit) as error:
        module.main(['invalid-case'])
    assert error.value.code == 2
    path = tmp_path/'descriptor.json'
    path.write_text(json.dumps({'schema':'b23_owned_child/v1','role':'worker','invocation_id':'inv-1'}))
    monkeypatch.delenv('INVOCATION_ID', raising=False)
    with pytest.raises(RuntimeError, match='authority/profile/parent'):
        module.load_child_descriptor(path, 'worker')


def test_launch_plan_serialization_preserves_frozen_environment_and_exact_argv(tmp_path):
    from mecanum_nav_rl.runtime_simulation.b23_runner import launch_plan_record
    from mecanum_nav_bringup.local_training_launch_contract import LaunchPlan
    plan = LaunchPlan(False,tmp_path/'world',tmp_path/'gui',tmp_path/'config', 'run', 'a'*64,'b'*64,11,
        (('gz','sim','--headless-rendering',str(tmp_path/'world')),), {'GZ_PARTITION':'private'},
        ('ros2','run','ros_gz_bridge','parameter_bridge'))
    raw = json.dumps(launch_plan_record(plan)).encode()
    saved = json.loads(raw)
    assert saved['commands'] == [list(plan.commands[0])]
    assert saved['environment'] == {'GZ_PARTITION':'private'}
    saved['environment']['GZ_PARTITION'] = 'changed'
    assert plan.environment['GZ_PARTITION'] == 'private'


def test_pending_cleanup_batch_is_preserved_in_failure_summary(tmp_path):
    from mecanum_nav_rl.runtime_simulation.b23_runner import write_record_once
    from mecanum_nav_bringup.local_training_process_supervisor import CleanupEvidenceBatch
    pending = CleanupEvidenceBatch('batch-not-acked', (('group_residue', (('pid',77),)),))
    path = tmp_path/'failed-summary.json'
    write_record_once(path, {'primary_error':'worker failed', 'pending_batch':pending})
    result = json.loads(path.read_bytes())
    assert result['primary_error'] == 'worker failed'
    assert result['pending_batch']['batch_id'] == 'batch-not-acked'
    assert result['pending_batch']['events'][0][0] == 'group_residue'


def test_actual_unit_properties_are_checked_exactly_without_duration_rounding():
    from mecanum_nav_rl.runtime_simulation.b23_runner import verify_unit_configuration
    properties = dict(Type='exec',Restart='no',KillMode='control-group',RemainAfterExit='yes',
        RuntimeMaxUSec='3min',RuntimeRandomizedExtraUSec='0',TimeoutStartUSec='5s',TimeoutStopUSec='2s',
        MemoryMax='5368709120',OOMPolicy='stop',
        SendSIGKILL='yes',KillSignal='15',FinalKillSignal='9')
    verify_unit_configuration(properties)
    for key,bad in [('RuntimeMaxUSec','3min 500ms'),('RuntimeRandomizedExtraUSec','500ms'),
            ('KillSignal','9'),('KillMode','process'),('TimeoutStopUSec','2.5s')]:
        with pytest.raises(ValueError, match=key): verify_unit_configuration(dict(properties, **{key:bad}))
    properties.pop('RemainAfterExit')
    with pytest.raises(ValueError, match='RemainAfterExit'): verify_unit_configuration(properties)
    soak=dict(Type='exec',Restart='no',KillMode='control-group',RemainAfterExit='yes',
        RuntimeMaxUSec='16min',RuntimeRandomizedExtraUSec='0',TimeoutStartUSec='5s',TimeoutStopUSec='2s',
        MemoryMax='5368709120',OOMPolicy='stop',SendSIGKILL='yes',KillSignal='15',FinalKillSignal='9')
    verify_unit_configuration(soak,active_s=900,cleanup_s=60)
    with pytest.raises(ValueError,match='RuntimeMaxUSec'):
        verify_unit_configuration(dict(soak,RuntimeMaxUSec='16min 1ms'),active_s=900,cleanup_s=60)


def test_terminal_evidence_is_joined_to_actual_main_pid_invocation_and_argv(tmp_path):
    from mecanum_nav_rl.runtime_simulation.b23_runner import terminal_binding_errors, MODULE
    packet = dict(run_id='B23_R01A_TEST',unit='b23-r01a-test.service',python='/pinned/python',run_root=str(tmp_path))
    sha = 'a'*64
    identity = dict(pid=77,start_ticks=12345,uid=1000,argv=[packet['python'],'-B','-m',MODULE,
        'parent','--packet',str(tmp_path/'packet.json'),'--packet-sha256',sha])
    parent = dict(identity=identity,run_id=packet['run_id'],invocation_id='inv-1',packet_sha256=sha)
    terminal = dict(InvocationID='inv-1',Id=packet['unit'],ExecMainPID='77')
    observed = {(77,12345):dict(identity)}
    assert terminal_binding_errors(packet,terminal,parent,observed,'inv-1',sha) == []
    assert terminal_binding_errors(packet,dict(terminal,ExecMainPID='78'),parent,observed,'inv-1',sha)
    assert terminal_binding_errors(packet,terminal,parent,observed,'inv-2',sha)
    assert terminal_binding_errors(packet,terminal,parent,{},'inv-1',sha)
    observed[(77,12345)]['argv'] = ['bash','unrelated']
    assert terminal_binding_errors(packet,terminal,parent,observed,'inv-1',sha)


def test_cleanup_budget_is_not_renewed_when_parent_follows_worker():
    from mecanum_nav_rl.runtime_simulation.b23_runner import cleanup_window_deadline
    marker = dict(run_id='run',invocation_id='inv-1',started_ns=2_000_000_000,deadline_ns=62_000_000_000)
    assert cleanup_window_deadline(marker,run_id='run',invocation='inv-1',total_end=180_000_000_000,
        now_ns=61_000_000_000) == 62_000_000_000
    for invalid in (dict(marker,deadline_ns=122_000_000_000),dict(marker,invocation_id='inv-2')):
        with pytest.raises(ValueError, match='identity/budget'):
            cleanup_window_deadline(invalid,run_id='run',invocation='inv-1',total_end=180_000_000_000,now_ns=61_000_000_000)


def test_unit_wrapper_preserves_real_invocation_and_literal_environment_without_leak():
    from mecanum_nav_rl.runtime_simulation.b23_runner import unit_parent_command
    import subprocess
    command = unit_parent_command({'environment':{'B23_LITERAL':'literal $HOME; $(echo not-executed)\nnext'},
        'python':'/pinned/python'}, '/packet.json', 'a'*64)
    # Thay argv program sau biên env bằng shell in hai biến; không systemd,
    # ROS hoặc helper probe. Cùng wrapper/argv literal production.
    index = command.index('/pinned/python')
    actual = command[:index]+['/bin/bash','-c','printf "%s\\n" "$INVOCATION_ID" "$B23_LITERAL" "${UNRELATED_SECRET-unset}"']
    result = subprocess.run(actual, env={'INVOCATION_ID':'inv-from-systemd','UNRELATED_SECRET':'must-not-leak'},
        capture_output=True,text=True,timeout=2)
    assert result.returncode == 0, result.stderr
    assert result.stdout == 'inv-from-systemd\nliteral $HOME; $(echo not-executed)\nnext\nunset\n'
    missing = subprocess.run(actual,env={},capture_output=True,text=True,timeout=2)
    assert missing.returncode != 0 and 'INVOCATION_ID' in missing.stderr
    assert command[index:] == ['/pinned/python','-B','-m',
        'mecanum_nav_rl.runtime_simulation.b23_runner','parent','--packet','/packet.json','--packet-sha256','a'*64]


def test_launch_template_pins_properties_env_and_only_substitutes_self_hash():
    from mecanum_nav_rl.runtime_simulation.b23_runner import service_launch_command, service_properties_for
    packet = dict(unit='b23-test.service',environment={'ROS_DOMAIN_ID':'84'},python='/pinned/python')
    template = service_launch_command(packet,'/packet.json','{PACKET_SHA256}')
    actual = service_launch_command(packet,'/packet.json','a'*64)
    assert actual == [value.replace('{PACKET_SHA256}','a'*64) for value in template]
    assert actual[:3] == ['systemd-run','--user','--unit=b23-test.service']
    assert '--scope' not in actual and '--collect' not in actual
    assert '--expand-environment=no' in actual
    assert set(value for value in actual if value.startswith('--property=')) == {'--property='+v for v in service_properties_for(120)}
    assert '--property=KillMode=control-group' in actual and '--property=RuntimeMaxSec=180s' in actual


def test_headless_smoke_seed_is_in_real_gazebo_server_argv(tmp_path):
    from mecanum_nav_rl.runtime_simulation.b23_runner import b23_server_argv
    command = b23_server_argv(tmp_path/'bound-world.sdf')
    assert command[:2] == ('gz','sim') and command[-1] == str(tmp_path/'bound-world.sdf')
    assert command[command.index('--seed')+1] == '20261029' and command.count('--seed') == 1
    assert command[command.index('--force-version')+1] == '8'
    assert '-s' in command and '--headless-rendering' in command and '-r' not in command


def test_worker_publishes_envelope_on_architecture_canonical_policy_topic():
    import ast
    from pathlib import Path
    from mecanum_nav_rl.runtime_simulation import b23_runner as module
    from mecanum_nav_rl_interfaces.msg import CommandEnvelope
    tree = ast.parse(Path(module.__file__).read_bytes())
    worker = next(node for node in tree.body if isinstance(node,ast.ClassDef) and node.name == 'TrainingWorkerIO')
    constructor = next(node for node in worker.body if isinstance(node,ast.FunctionDef) and node.name == '__init__')
    assignment = next(node for node in ast.walk(constructor) if isinstance(node,ast.Assign)
        and any(isinstance(target,ast.Attribute) and target.attr == 'policy_publisher' for target in node.targets))
    calls = []
    node = NS(node=NS(create_publisher=lambda *args:calls.append(args)))
    qos = object()
    statement = ast.fix_missing_locations(ast.Module(body=[assignment],type_ignores=[]))
    exec(compile(statement,module.__file__,'exec'), {'self':node,'CommandEnvelope':CommandEnvelope,'reliable':qos})
    assert calls == [(CommandEnvelope,'/mecanum/cmd_policy',qos)]


def test_packet_argv_is_stable_across_canonical_json_roundtrip():
    from mecanum_nav_rl.runtime_simulation.b23_runner import service_launch_command
    packet = dict(unit='b23-test.service',python='/pinned/python',
        environment={'Z_LAST':'literal value','A_FIRST':'other'})
    before = service_launch_command(packet,'/packet.json','{PACKET_SHA256}')
    restored = json.loads(json.dumps(packet,sort_keys=True,separators=(',',':')))
    after = service_launch_command(restored,'/packet.json','{PACKET_SHA256}')
    assert before == after


def test_prepared_session_identity_satisfies_real_readiness_contract():
    import ast,uuid
    from pathlib import Path
    from mecanum_nav_rl.runtime_simulation import b23_runner as module
    from mecanum_nav_bringup.local_training_process_supervisor import RclpyReadiness
    tree=ast.parse(Path(module.__file__).read_bytes())
    producer=next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='prepare_packet')
    call=next(node for node in ast.walk(producer) if isinstance(node,ast.Call)
        and isinstance(node.func,ast.Name) and node.func.id=='build_launch_plan')
    namespace={'args':NS(run_id='B23_R01A_TEST'),'uuid':uuid,'str':str}
    for node in producer.body:
        if isinstance(node,ast.Assign) and any(isinstance(target,ast.Name) and target.id=='session_id' for target in node.targets):
            exec(compile(ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[])),module.__file__,'exec'),namespace)
    expression=next(keyword.value for keyword in call.keywords if keyword.arg=='session_id')
    session=eval(compile(ast.fix_missing_locations(ast.Expression(expression)),module.__file__,'eval'),namespace)
    plan=NS(session_id=session,coordinator_ingress_instance_id=11,config_hash='a'*64,
        asset_manifest_sha256='b'*64,environment={'ROS_DOMAIN_ID':'84','GZ_PARTITION':'private'})
    request=RclpyReadiness()._make_request(plan,'a'*64,1_000_000_000)
    assert request['session_id']==session and session != namespace['args'].run_id
    assert str(uuid.UUID(session))==session


def test_failed_state_clear_only_targets_the_bound_completed_invocation(monkeypatch):
    from mecanum_nav_rl.runtime_simulation import b23_runner as module
    import subprocess
    calls,events=[],[]
    props=dict(Id='b23-test.service',InvocationID='inv-1',ExecMainPID='77',MainPID='0',
        ActiveState='failed',ControlGroup='',ExecStart='pinned argv --packet-sha256 '+'a'*64)
    def execute(argv,**kwargs):
        calls.append(argv)
        return NS(returncode=0,stdout=('\n'.join(k+'='+v for k,v in props.items())+'\n').encode()
            if 'show' in argv else b'',stderr=b'')
    monkeypatch.setattr(subprocess,'run',execute)
    module.clear_owned_failed_state('b23-test.service','inv-1','77','a'*64,deadline_ns=2_000_000_000,
        now_ns=lambda:1_000_000_000,emit=lambda n,r:events.append((n,r)))
    assert calls[-1]==['systemctl','--user','reset-failed','b23-test.service']
    for key,bad in [('InvocationID','inv-2'),('ExecMainPID','88'),('MainPID','88'),('ControlGroup','/foreign')]:
        original=props[key];props[key]=bad;calls.clear()
        with pytest.raises(RuntimeError,match='ownership changed'):
            module.clear_owned_failed_state('b23-test.service','inv-1','77','a'*64,deadline_ns=2_000_000_000,
                now_ns=lambda:1_000_000_000,emit=lambda n,r:events.append((n,r)))
        assert not any('reset-failed' in a for a in calls)
        props[key]=original
    calls.clear()
    with pytest.raises(TimeoutError):
        module.clear_owned_failed_state('b23-test.service','inv-1','77','a'*64,deadline_ns=1_000_000_000,
            now_ns=lambda:1_000_000_000,emit=lambda n,r:None)
    assert not calls


def test_packet_environment_keeps_gazebo_vendor_discovery_without_unlisted_values():
    import ast
    from pathlib import Path
    from mecanum_nav_rl.runtime_simulation import b23_runner as module
    tree=ast.parse(Path(module.__file__).read_bytes())
    producer=next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='prepare_packet')
    statements=[node for node in producer.body if isinstance(node,ast.Assign) and
        any(isinstance(target,ast.Name) and target.id in ('environment_keys','environment') for target in node.targets)]
    namespace={'os':NS(environ={'GZ_CONFIG_PATH':'/vendor/sim/share/gz:/vendor/transport/share/gz',
        'PATH':'/vendor/bin','UNLISTED_SECRET':'must-not-leak'})}
    exec(compile(ast.fix_missing_locations(ast.Module(body=statements,type_ignores=[])),module.__file__,'exec'),namespace)
    environment=namespace['environment']
    assert environment.get('GZ_CONFIG_PATH')==namespace['os'].environ['GZ_CONFIG_PATH'], environment
    assert environment['PATH']=='/vendor/bin' and 'UNLISTED_SECRET' not in environment


def test_graph_failure_preserves_observed_endpoint_identity_without_binding():
    value,clock=worker();events=[];bound=[]
    def endpoint(name):return NS(node_name=name,node_namespace='/',topic_type='actual/type',endpoint_gid=bytes(range(16)))
    groups={'/cmd_vel':[endpoint('unexpected')],'/mecanum/safety_state':[endpoint('safety_supervisor')],
        '/mecanum/local_training/safety_input':[endpoint('b23_coordinator_ingress')]}
    value.node.get_publishers_info_by_topic=lambda topic:groups[topic]
    value.emit=lambda event,facts:events.append((event,facts))
    value.ingress.bind_safety_publisher_gid=lambda gid:bound.append(gid)
    with pytest.raises(RuntimeError,match='unexpected graph publisher ownership'):
        asyncio.run(value.pin_graph(deadline_ns=clock.ns+10_000_000))
    assert not bound and [event for event,_ in events]==['GRAPH_OBSERVATION']
    assert events[0][1]['cmd_vel'][0]==dict(node='unexpected',namespace='/',type='actual/type',gid_hex=bytes(range(16)).hex())


def test_graph_undiscovered_ros_node_waits_without_binding_or_extending_deadline():
    value,clock=worker();events=[];bound=[]
    def endpoint(name):return NS(node_name=name,node_namespace='/',topic_type='actual/type',endpoint_gid=bytes(range(16)))
    cmd=endpoint('_NODE_NAME_UNKNOWN_');cmd.node_namespace='_NODE_NAMESPACE_UNKNOWN_'
    groups={'/cmd_vel':[cmd],'/mecanum/safety_state':[endpoint('safety_supervisor')],
        '/mecanum/local_training/safety_input':[endpoint('b23_coordinator_ingress')]}
    value.node.get_publishers_info_by_topic=lambda topic:groups[topic]
    value.emit=lambda event,facts:events.append((event,facts))
    value.ingress.bind_safety_publisher_gid=lambda gid:bound.append(gid)
    async def pause(seconds):
        assert not bound
        await clock.pause(seconds)
        cmd.node_name='final_twist_publisher';cmd.node_namespace='/'
    value.pause=pause
    asyncio.run(value.pin_graph(deadline_ns=clock.ns+5_000_000))
    assert bound==[bytes(range(16))] and clock.ns==1_002_000_000
    assert [name for name,_ in events]==['GRAPH_OBSERVATION','GRAPH_OBSERVATION','GRAPH_BOUND']
    cmd.node_name='_NODE_NAME_UNKNOWN_';cmd.node_namespace='_NODE_NAMESPACE_UNKNOWN_'
    bound.clear();value.pause=clock.pause
    deadline=clock.ns+5_000_000
    with pytest.raises(TimeoutError,match='source graph binding'):
        asyncio.run(value.pin_graph(deadline_ns=deadline))
    assert not bound and clock.ns==deadline


def test_subscription_keeps_actual_wire_before_decode_and_callback_failure():
    from nav_msgs.msg import Odometry
    from rclpy.serialization import serialize_message
    import hashlib
    value,clock=worker();events=[];seen=[]
    value.emit=lambda event,facts:events.append((event,facts))
    original=Odometry();original.header.frame_id='world';original.pose.pose.orientation.w=1.
    wire=serialize_message(original);info={'source_timestamp':123,'received_timestamp':456}
    def consumer(msg):
        seen.append(msg)
        assert events[-1][0]=='INGRESS_WIRE_RECEIVED'
        assert events[-1][1]['wire_cdr_hex']==wire.hex()
        return 'actual-result'
    receive=value.observed_callback(Odometry,'/actual/oracle',consumer)
    assert receive(wire,info)=='actual-result' and seen==[original]
    assert events[0][1]['message_info']==info
    def reject(msg):raise ValueError('actual rejected sample')
    receive=value.observed_callback(Odometry,'/actual/oracle',reject)
    with pytest.raises(ValueError,match='actual rejected sample'):receive(wire,info)
    assert [x[0] for x in events][-2:]==['INGRESS_WIRE_RECEIVED','INGRESS_CALLBACK_ERROR']
    assert events[-1][1]['wire_sha256']==hashlib.sha256(wire).hexdigest()


def test_reset_measurements_wait_for_scan_with_original_deadline():
    value, clock=worker()
    value.ingress.scans={}
    value.ingress.lifecycle=NS(barrier_stamp=NS(sec=0,nanosec=90))
    value.ingress.profile={"scan_max_age_ms":500}
    value.ingress.scan_reset_stamp_ns=90
    value.ingress.physics_pairs=[]
    value.ros_now=lambda:100
    async def consume():
        async for _ in value.measurements(deadline_ns=clock.ns+5_000_000,after_iteration=0):
            pytest.fail('measurement requires actual physics pair')
    with pytest.raises(TimeoutError,match='fresh reset scan'):
        asyncio.run(consume())
    assert clock.ns==1_005_000_000


def test_reset_scan_rejects_old_delayed_and_stale_samples():
    value,clock=worker()
    value.ingress.lifecycle=NS(barrier_stamp=NS(sec=1,nanosec=0))
    value.ingress.profile={'scan_max_age_ms':100}
    value.ingress.scan_reset_stamp_ns=1_001_000_000
    value.ingress.scans={999_999_999:NS(received_steady_ns=clock.ns)}
    assert value.fresh_reset_scan(now_ros_ns=1_010_000_000,now_steady_ns=clock.ns) is None
    value.ingress.scans[1_001_000_000]=NS(received_steady_ns=clock.ns)
    assert value.fresh_reset_scan(now_ros_ns=1_010_000_000,now_steady_ns=clock.ns) is None
    value.ingress.scans[1_001_000_001]=NS(received_steady_ns=clock.ns-200_000_000)
    assert value.fresh_reset_scan(now_ros_ns=1_010_000_000,now_steady_ns=clock.ns) is None
    fresh=NS(received_steady_ns=clock.ns)
    value.ingress.scans[1_002_000_000]=fresh
    assert value.fresh_reset_scan(now_ros_ns=1_010_000_000,now_steady_ns=clock.ns) is fresh
    later=NS(received_steady_ns=clock.ns)
    value.ingress.scans[1_009_000_000]=later
    assert value.fresh_reset_scan(now_ros_ns=1_010_000_000,now_steady_ns=clock.ns,
        at_or_before_ns=1_005_000_000) is fresh


def test_observation0_handoff_rejects_pre_reset_scan_until_deadline():
    from mecanum_nav_rl_interfaces.msg import LocalTrainingSafetyInput
    value,clock=worker();calls=[]
    value.ros_now=lambda:100
    value.ingress.lifecycle=NS(barrier_stamp=NS(sec=0,nanosec=90))
    value.ingress.scan_reset_stamp_ns=95
    value.ingress.profile={'scan_max_age_ms':500}
    value.ingress.scans={95:NS(stamp_ns=95,received_steady_ns=clock.ns)}
    value.ingress.admission_state=LocalTrainingSafetyInput.ADMISSION_INHIBITED
    value.ingress.confirm_observation0=lambda ack:calls.append('confirmed')
    b1=NS(commit_observation0=lambda cutoff:calls.append('committed'))
    with pytest.raises(TimeoutError,match='observation0 did not confirm'):
        asyncio.run(value.commit_and_confirm_observation0(b1,deadline_ns=clock.ns+5_000_000))
    assert calls==[] and value.ingress.admission_state==LocalTrainingSafetyInput.ADMISSION_INHIBITED


def test_observation0_handoff_uses_fresh_scan_after_zero_anchor():
    from mecanum_nav_rl_interfaces.msg import LocalTrainingSafetyInput
    from mecanum_nav_rl_interfaces.srv import LocalTrainingBackendControl as Control
    from mecanum_nav_rl.runtime_simulation import local_training_coordinator

    value,clock=worker(); calls=[]; ack=NS(request_bytes=b'confirm-request',response_bytes=b'confirm-response')
    value.ros_now=lambda:1_010_000_000
    value.ingress.lifecycle=NS(barrier_stamp=NS(sec=0,nanosec=90))
    value.ingress.scan_reset_stamp_ns=95
    value.ingress.profile={'scan_max_age_ms':500}
    fresh=NS(stamp_ns=1_000_000_000,received_steady_ns=clock.ns)
    value.ingress.scans={fresh.stamp_ns:fresh}
    value.ingress.admission_state=LocalTrainingSafetyInput.ADMISSION_INHIBITED
    value.final=NS(publisher_instance_id=33)
    value.ingress.confirm_observation0=lambda result:calls.append(('confirmed',result))
    receipt=NS(final_publish_sequence=27,final_publisher_instance_id=33,receipt_key=('p',27))
    adjacent=NS(final_publish_sequence=28,final_publisher_instance_id=33,receipt_key=('p',28))
    selection=NS(receipt=receipt,adjacent_receipt=adjacent)
    b1=NS(preview_observation0_selection=lambda cutoff:selection,
        _prove_application=lambda _receipt, _cutoff:{'iteration':9,'stamp_ns':1_090_000_000},
        commit_observation0=lambda cutoff, **kwargs:(calls.append(('committed',cutoff,kwargs)) or ('observation0',selection)))
    value.native_adjacent_boundary_application=lambda _selection, _cutoff:{'iteration':10,'stamp_ns':1_120_000_000}
    async def transact(operation,**kwargs):
        calls.append(('control',operation,kwargs['observation0_cutoff']))
        return ack
    value.control=NS(transact=transact)
    original=local_training_coordinator.lifecycle_request_fields
    local_training_coordinator.lifecycle_request_fields=lambda _snapshot:{}
    try:
        result,cutoff=asyncio.run(value.commit_and_confirm_observation0(
            b1,deadline_ns=clock.ns+5_000_000,
            zero_receipt=NS(applied_sim_stamp_ns=990_000_000)))
    finally:
        local_training_coordinator.lifecycle_request_fields=original

    assert result=='observation0' and cutoff==fresh.stamp_ns, calls
    assert calls[0][0:2]==('committed',fresh.stamp_ns), calls
    assert calls[0][2]['expected_selection_keys']==(receipt.receipt_key,adjacent.receipt_key)
    assert calls[1][0]=='control' and calls[1][1]==Control.Request.OP_CONFIRM_OBSERVATION0, calls
    assert calls[2]==('confirmed',ack), calls
    assert value.ingress.admission_state==LocalTrainingSafetyInput.ADMISSION_INHIBITED


def test_observation0_waits_for_native_adjacent_receipt_application_before_b1_commit():
    import threading
    from builtin_interfaces.msg import Time
    from mecanum_nav_rl_interfaces.msg import LocalTrainingSafetyInput, SimulationContactState
    from mecanum_nav_rl_interfaces.srv import LocalTrainingBackendControl as Control
    from mecanum_nav_rl.runtime_simulation import local_training_coordinator
    from rclpy.serialization import serialize_message

    value, clock = worker()
    cutoff = 1_100_000_000
    adjacent_stamp = 1_120_000_000
    value.ros_now = lambda: 1_200_000_000
    value.ingress.lifecycle = NS(barrier_stamp=Time(sec=0, nanosec=900_000_000))
    value.ingress.scan_reset_stamp_ns = 900_000_000
    value.ingress.profile = {'scan_max_age_ms': 500}
    scan = NS(stamp_ns=cutoff, received_steady_ns=clock.ns)
    value.ingress.scans = {cutoff: scan}
    value.ingress.admission_state = LocalTrainingSafetyInput.ADMISSION_INHIBITED
    value.ingress.lock = threading.Lock()
    value.ingress._application_bytes = {}
    value.final = NS(publisher_instance_id=55)
    receipt = NS(receipt_key=('session', 8), final_publish_sequence=8,
        final_publisher_instance_id=55)
    adjacent = NS(receipt_key=('session', 9), final_publish_sequence=9,
        final_publisher_instance_id=55)
    selection = NS(receipt=receipt, adjacent_receipt=adjacent)
    commit_calls, control_calls, confirmations, events = [], [], [], []

    def commit(selected_cutoff, *, expected_selection_keys=None):
        assert 9 in value.ingress._application_bytes, 'B1 commit preceded native application'
        commit_calls.append((selected_cutoff, expected_selection_keys))
        return 'observation0', selection

    b1 = NS(preview_observation0_selection=lambda selected_cutoff:selection,
        _prove_application=lambda _receipt, _cutoff:{'iteration':11,'stamp_ns':1_090_000_000},
        commit_observation0=commit)
    value.ingress.confirm_observation0 = lambda ack: confirmations.append(ack)
    value.emit = lambda name, fields: events.append((name, fields))
    async def transact(operation, **fields):
        control_calls.append((operation, fields['selected_zero_final_publish_sequence'],
            fields['adjacent_boundary_final_publish_sequence']))
        return 'confirm-ack'
    value.control = NS(transact=transact)

    status = SimulationContactState()
    status.applied_receipt_valid = True
    status.local_zero_override = False
    status.applied_final_publisher_instance_id = 55
    status.applied_final_publish_sequence = 9
    status.applied_physics_iteration = 12
    status.physics_iteration = 12
    status.applied_sim_stamp = Time(sec=1, nanosec=120_000_000)
    status.header.stamp = Time(sec=1, nanosec=120_000_000)
    raw_application = serialize_message(status)
    pause_calls = []
    async def pause(seconds):
        pause_calls.append(seconds)
        await clock.pause(seconds)
        value.ingress._application_bytes[9] = raw_application
    value.pause = pause
    original = local_training_coordinator.lifecycle_request_fields
    local_training_coordinator.lifecycle_request_fields = lambda _snapshot:{}
    try:
        result, selected_cutoff = asyncio.run(value.commit_and_confirm_observation0(
            b1, deadline_ns=clock.ns + 20_000_000,
            zero_receipt=NS(applied_sim_stamp_ns=1_000_000_000)))
    finally:
        local_training_coordinator.lifecycle_request_fields = original

    assert result == 'observation0' and selected_cutoff == cutoff
    assert len(pause_calls) == 1, 'caller must wait after receipt publication until native application'
    assert commit_calls == [(cutoff, (receipt.receipt_key, adjacent.receipt_key))]
    assert control_calls == [(Control.Request.OP_CONFIRM_OBSERVATION0, 8, 9)]
    assert confirmations == ['confirm-ack']
    deferred = [fields for name, fields in events if name == 'RESET_ADJACENT_BOUNDARY_DEFERRED']
    applied = [fields for name, fields in events if name == 'RESET_ADJACENT_BOUNDARY_NATIVE_APPLIED']
    assert len(deferred) == len(applied) == 1
    assert deferred[0]['adjacent_publish_sequence'] == applied[0]['adjacent_publish_sequence'] == 9
    assert applied[0]['application_iteration'] == 12
    assert applied[0]['application_stamp_ns'] == adjacent_stamp


def test_observation0_handoff_rejects_scan_before_zero_anchor():
    from mecanum_nav_rl_interfaces.msg import LocalTrainingSafetyInput
    value,clock=worker()
    value.ros_now=lambda:1_010_000_000
    value.ingress.lifecycle=NS(barrier_stamp=NS(sec=0,nanosec=90))
    value.ingress.scan_reset_stamp_ns=95
    value.ingress.profile={'scan_max_age_ms':500}
    value.ingress.scans={980_000_000:NS(stamp_ns=980_000_000,received_steady_ns=clock.ns)}
    value.ingress.admission_state=LocalTrainingSafetyInput.ADMISSION_INHIBITED
    value.ingress.confirm_observation0=lambda _ack:pytest.fail('pre-anchor scan cannot confirm')
    b1=NS(preview_observation0_selection=lambda _cutoff:pytest.fail('pre-anchor scan cannot preview'),
        commit_observation0=lambda _cutoff, **_kwargs:pytest.fail('pre-anchor scan cannot commit'))
    with pytest.raises(TimeoutError,match='observation0 did not confirm'):
        asyncio.run(value.commit_and_confirm_observation0(
            b1,deadline_ns=clock.ns+5_000_000,
            zero_receipt=NS(applied_sim_stamp_ns=990_000_000)))
    assert value.ingress.admission_state==LocalTrainingSafetyInput.ADMISSION_INHIBITED


def test_observation0_aligns_safe_stop_receipt_away_from_scan_cutoff():
    from collections import deque
    from builtin_interfaces.msg import Time
    from mecanum_nav_rl.core.issued_command_cutoff import (
        IssuedCommandReceiptView, ReceiptSource, ReceiptStreamBinding,
        CutoffStatus, select_reset_zero_at_cutoff,
    )
    from mecanum_nav_rl.core.lifecycle_types import EpisodeLifecycleIdentity
    from mecanum_nav_rl_interfaces.msg import (
        CommandEnvelope, LocalTrainingSafetyInput, SimulationContactState,
    )
    from mecanum_nav_rl_interfaces.srv import LocalTrainingBackendControl as Control
    from mecanum_nav_rl.runtime_simulation import local_training_coordinator
    from mecanum_nav_rl.runtime_simulation.local_training_coordinator import B1SnapshotPending
    from rclpy.serialization import serialize_message

    value, clock = worker()
    value.deadline_ns = clock.ns + 1_000_000_000
    ros_ns = [1_090_000_000]
    value.ros_now = lambda: ros_ns[0]
    lifecycle = NS(episode_generation=1, reset_epoch=2, runtime_generation=3,
        barrier_stamp=Time(sec=0, nanosec=800_000_000))
    value.ingress.lifecycle = lifecycle
    value.ingress.scan_reset_stamp_ns = 800_000_000
    value.ingress.profile = {'scan_max_age_ms': 500, 'safety_period_ms': 20,
        'final_command_timeout_ms': 100}
    value.ingress.scans = {
        900_000_000: NS(stamp_ns=900_000_000, received_steady_ns=clock.ns),
        1_000_000_000: NS(stamp_ns=1_000_000_000, received_steady_ns=clock.ns),
    }
    value.ingress.admission_state = LocalTrainingSafetyInput.ADMISSION_INHIBITED
    value.ingress.last_published_admission_state = LocalTrainingSafetyInput.ADMISSION_INHIBITED
    value.ingress.fault = None
    value.ingress.backend_state = NS(fault_flags=0)
    value.ingress.receipts = deque()
    identity = EpisodeLifecycleIdentity(1, 2, 3)
    receipt = NS(source=ReceiptSource.SAFE_STOP, lifecycle=identity,
        publish_stamp_ns=1_080_000_000, final_publisher_instance_id=55,
        final_publish_sequence=8, final_command=(0.0, 0.0, 0.0),
        received_steady_ns=clock.ns)
    value.ingress.receipts.append(receipt)
    status = SimulationContactState()
    status.applied_receipt_valid = True
    status.local_zero_override = False
    status.applied_final_publisher_instance_id = 55
    status.applied_final_publish_sequence = 8
    status.applied_physics_iteration = 9
    status.applied_sim_stamp = Time(sec=1, nanosec=90_000_000)
    value.ingress.physics_pairs = [NS(stamp_ns=1_090_000_000, iteration=9,
        backend_bytes=serialize_message(status))]

    stream_history, events = [], []
    alignment_calls = []
    adapter = NS(policy_hold=True,
        last_output=NS(source=CommandEnvelope.SOURCE_SAFE_STOP),
        set_stream_enabled=lambda enabled: stream_history.append((enabled, clock.ns)))
    value.safety = NS(local_training=adapter)
    async def align(*, failed_cutoff_ns, deadline_ns):
        alignment_calls.append((failed_cutoff_ns, deadline_ns))
        return True
    value.align_reset_zero_receipt_boundary = align
    value.final = NS(publisher_instance_id=55)
    value.emit = lambda name, fields: events.append((name, fields))
    async def pause(seconds):
        await clock.pause(seconds)
        ros_ns[0] += 10_000_000
        if ros_ns[0] == 1_100_000_000:
            value.ingress.scans[ros_ns[0]] = NS(stamp_ns=ros_ns[0], received_steady_ns=clock.ns)
        if ros_ns[0] == 1_120_000_000:
            value.ingress.receipts.append(NS(source=ReceiptSource.SAFE_STOP, lifecycle=identity,
                publish_stamp_ns=ros_ns[0], final_publisher_instance_id=55,
                final_publish_sequence=9, final_command=(0.0, 0.0, 0.0),
                received_steady_ns=clock.ns))
    value.pause = pause

    cutoffs = []
    binding = ReceiptStreamBinding(55, 'session', 'a' * 64, identity, 'base_link')
    def receipt_view(sequence, stamp, received):
        return IssuedCommandReceiptView(stamp, 55, sequence, ReceiptSource.SAFE_STOP,
            66, sequence, 0, '', identity, 'session', 'a' * 64, (0.0, 0.0, 0.0),
            received, 'base_link', True)
    selected_view = receipt_view(8, 1_080_000_000, clock.ns)
    adjacent_view = receipt_view(9, 1_120_000_000, clock.ns + 40_000_000)
    selection = select_reset_zero_at_cutoff((selected_view, adjacent_view), binding=binding,
        cutoff_ros_ns=1_100_000_000, evaluation_ros_now_ns=1_120_000_000,
        evaluation_steady_now_ns=clock.ns + 50_000_000, reset_barrier_ros_ns=800_000_000,
        physical_scales=(0.25, 0.2, 0.8))
    assert selection.status is CutoffStatus.READY, selection.reason
    assert selection.receipt.final_publish_sequence == 8
    assert selection.adjacent_receipt.final_publish_sequence == 9
    def preview(cutoff):
        previewed.append(cutoff)
        return selection
    previewed=[]
    def commit(cutoff, *, expected_selection_keys=None):
        cutoffs.append(cutoff)
        assert expected_selection_keys == (selection.receipt.receipt_key,
            selection.adjacent_receipt.receipt_key)
        return 'observation0', selection

    application_checks = []
    def prove_selected_application(_receipt, cutoff):
        application_checks.append(cutoff)
        if len(application_checks) == 1:
            raise B1SnapshotPending('selected receipt lacks native application at/before cutoff')
        return {'iteration':11,'stamp_ns':cutoff}
    confirmations, control_calls = [], []
    value.ingress.confirm_observation0 = lambda ack: confirmations.append(ack)
    value.native_adjacent_boundary_application=lambda _selection, cutoff:{
        'iteration':10,'stamp_ns':cutoff+20_000_000}
    async def transact(operation, **fields):
        control_calls.append((operation, fields['observation0_cutoff'].nanosec))
        return 'actual-ack'
    value.control = NS(transact=transact)
    original = local_training_coordinator.lifecycle_request_fields
    local_training_coordinator.lifecycle_request_fields = lambda _snapshot: {}
    try:
        result, cutoff = asyncio.run(value.commit_and_confirm_observation0(
            NS(preview_observation0_selection=preview,
                _prove_application=prove_selected_application, commit_observation0=commit),
            deadline_ns=clock.ns + 500_000_000))
    finally:
        local_training_coordinator.lifecycle_request_fields = original

    assert result == 'observation0' and cutoff == 1_100_000_000
    assert previewed == [1_000_000_000, 1_100_000_000]
    assert application_checks == [1_000_000_000, 1_100_000_000]
    assert cutoffs == [1_100_000_000]
    assert alignment_calls and alignment_calls[0][0] == 1_000_000_000
    assert not stream_history
    assert not [name for name, _ in events if name == 'RESET_RECEIPT_ALIGNMENT_DEFERRED']
    assert 'RESET_ADJACENT_BOUNDARY_NATIVE_APPLIED' in [name for name, _ in events]
    assert control_calls == [(Control.Request.OP_CONFIRM_OBSERVATION0, 100_000_000)]
    assert confirmations == ['actual-ack']


def test_observation0_defers_scan_alignment_until_two_post_reset_scans():
    from builtin_interfaces.msg import Time
    from mecanum_nav_rl.runtime_simulation import local_training_coordinator
    from mecanum_nav_rl.runtime_simulation.local_training_coordinator import B1SnapshotPending

    value, clock = worker()
    value.deadline_ns = clock.ns + 200_000_000
    ros_ns = [1_020_000_000]
    value.ros_now = lambda: ros_ns[0]
    value.node = NS(get_clock=lambda: NS(now=lambda: NS(nanoseconds=ros_ns[0])))
    life = NS(barrier_stamp=Time(sec=0, nanosec=900_000_000))
    first = NS(stamp_ns=1_000_000_000, received_steady_ns=clock.ns)
    second = NS(stamp_ns=1_100_000_000, received_steady_ns=clock.ns)
    value.ingress = NS(lifecycle=life, scan_reset_stamp_ns=900_000_000,
        scans={first.stamp_ns:first}, profile={'scan_max_age_ms':500}, fault=None,
        backend_state=NS(fault_flags=0), admission_state=0,
        confirm_observation0=lambda ack: confirmations.append(ack))
    value.final = NS(publisher_instance_id=55)
    value.control = NS(transact=lambda *args, **kwargs: asyncio.sleep(0, result='ack'))
    confirmations, cutoffs, align_calls, events = [], [], [], []
    receipt = NS(receipt_key=('session', 8), final_publish_sequence=8,
        final_publisher_instance_id=55)
    adjacent = NS(receipt_key=('session', 9), final_publish_sequence=9,
        final_publisher_instance_id=55)
    selection = NS(receipt=receipt, adjacent_receipt=adjacent)
    previewed = []

    def preview(cutoff):
        previewed.append(cutoff)
        if len(previewed) < 3:
            raise B1SnapshotPending('selected receipt lacks native application at/before cutoff')
        return selection

    def commit(cutoff, *, expected_selection_keys=None):
        cutoffs.append(cutoff)
        assert expected_selection_keys == (receipt.receipt_key, adjacent.receipt_key)
        return 'observation0', selection

    b1 = NS(preview_observation0_selection=preview,
        _prove_application=lambda _receipt, _cutoff:{'iteration':12,'stamp_ns':1_120_000_000},
        commit_observation0=commit)
    value.native_adjacent_boundary_application = lambda _selection, cutoff:{
        'iteration':12, 'stamp_ns':cutoff + 20_000_000}

    async def pause(duration):
        await clock.pause(duration)
        ros_ns[0] = 1_120_000_000
        value.ingress.scans[second.stamp_ns] = second

    async def align(*, failed_cutoff_ns, deadline_ns):
        stamps = sorted(stamp for stamp in value.ingress.scans
            if value.ingress.scan_reset_stamp_ns < stamp <= failed_cutoff_ns)
        align_calls.append((failed_cutoff_ns, stamps))
        return True

    value.pause = pause
    value.align_reset_zero_receipt_boundary = align
    value.emit = lambda name, fields: events.append((name, fields))
    original = local_training_coordinator.lifecycle_request_fields
    local_training_coordinator.lifecycle_request_fields = lambda _snapshot: {}
    try:
        result, cutoff = asyncio.run(value.commit_and_confirm_observation0(
            b1, deadline_ns=clock.ns + 100_000_000,
            zero_receipt=NS(applied_sim_stamp_ns=950_000_000)))
    finally:
        local_training_coordinator.lifecycle_request_fields = original

    assert result == 'observation0' and cutoff == second.stamp_ns
    assert previewed == [first.stamp_ns, second.stamp_ns, second.stamp_ns]
    assert cutoffs == [second.stamp_ns]
    assert align_calls == [(second.stamp_ns, [first.stamp_ns, second.stamp_ns])]
    assert [name for name, _ in events] == [
        'RESET_RECEIPT_ALIGNMENT_DEFERRED', 'RESET_ADJACENT_BOUNDARY_NATIVE_APPLIED']
    assert confirmations == ['ack']


def test_reset_zero_alignment_uses_observed_applied_receipt_not_predicted_stamp():
    """Timer phase may skip target-safety_period; pin the real applied zero."""
    from builtin_interfaces.msg import Time
    from mecanum_nav_rl_interfaces.msg import SimulationContactState
    from rclpy.serialization import serialize_message
    from mecanum_nav_rl.core.issued_command_cutoff import ReceiptSource
    from mecanum_nav_rl.runtime_simulation.local_training_ingress import lifecycle_identity

    value, clock = worker()
    value.deadline_ns = clock.ns + 300_000_000
    ros_ns = [1_000_000_000]
    target = 1_100_000_000
    life = NS(episode_generation=1, reset_epoch=2, runtime_generation=3,
        barrier_stamp=Time(sec=0, nanosec=800_000_000))
    identity = lifecycle_identity(life)
    applied = SimulationContactState()
    applied.applied_receipt_valid = True
    applied.local_zero_override = False
    applied.applied_final_publisher_instance_id = 55
    applied.applied_final_publish_sequence = 11
    applied.applied_physics_iteration = 108
    applied.applied_sim_stamp = Time(sec=1, nanosec=80_000_000)
    receipt = NS(source=ReceiptSource.SAFE_STOP, lifecycle=identity,
        publish_stamp_ns=1_060_000_000, received_steady_ns=clock.ns,
        final_publisher_instance_id=55, final_publish_sequence=11,
        final_command=(0., 0., 0.))
    adjacent = NS(source=ReceiptSource.SAFE_STOP, lifecycle=identity,
        publish_stamp_ns=1_120_000_000, received_steady_ns=0,
        final_publisher_instance_id=55, final_publish_sequence=12,
        final_command=(0., 0., 0.))
    suppressed = NS(_reset_boundary_suppressed_stamp_ns=None,
        _reset_scan_boundary_stamp_ns=None, policy_hold=True,
        last_output=NS(source=1))
    armed = []
    def arm(stamp):
        armed.append(stamp)
        suppressed._reset_scan_boundary_stamp_ns = stamp
    suppressed.arm_reset_scan_boundary = arm
    suppressed.cancel_reset_scan_boundary = lambda stamp: setattr(
        suppressed, '_reset_scan_boundary_stamp_ns', None)
    value.node = NS(get_clock=lambda: NS(now=lambda: NS(nanoseconds=ros_ns[0])))
    value.ros_now = lambda: ros_ns[0]
    value.ingress = NS(lifecycle=life, scan_reset_stamp_ns=800_000_000,
        scans={900_000_000: NS(stamp_ns=900_000_000), 1_000_000_000: NS(stamp_ns=1_000_000_000)},
        profile={'safety_period_ms': 20, 'scan_max_age_ms': 500,
            'final_command_timeout_ms': 100, 'b1_receipt_max_age_ms': 500}, receipts=[receipt],
        physics_pairs=[NS(stamp_ns=1_080_000_000, iteration=108,
            backend_bytes=serialize_message(applied))], admission_state=0,
        last_published_admission_state=0, fault=None, backend_state=NS(fault_flags=0),
        lock=threading.RLock())
    from mecanum_nav_rl_interfaces.msg import CommandEnvelope
    suppressed.last_output.source = CommandEnvelope.SOURCE_SAFE_STOP
    value.safety = NS(local_training=suppressed)
    value.final = NS(publisher_instance_id=55)
    value.pause = None
    events = []
    value.emit = lambda name, fields: events.append((name, fields))

    boundary_overrun_polls = [0]
    async def advance(seconds):
        before = ros_ns[0]
        await clock.pause(seconds)
        ros_ns[0] = min(target + 10_000_000, before + 10_000_000)
        if ros_ns[0] == target:
            suppressed._reset_boundary_suppressed_stamp_ns = target
        elif ros_ns[0] > target:
            boundary_overrun_polls[0] += 1
        if ros_ns[0] > target and boundary_overrun_polls[0] >= 60 and len(value.ingress.receipts) == 1:
            # Clock/suppression may advance before the scan callback is
            # delivered. The production wait must keep polling in the same
            # 500 ms receipt-age budget, independent of the 100 ms command
            # watchdog, until that exact post-barrier sample is visible.
            value.ingress.scans[target] = NS(stamp_ns=target)
            adjacent.received_steady_ns = clock.ns
            value.ingress.receipts.append(adjacent)

    value.pause = advance
    result = asyncio.run(value.align_reset_zero_receipt_boundary(
        failed_cutoff_ns=1_000_000_000, deadline_ns=clock.ns + 300_000_000))
    assert result is True
    assert armed == [target]
    boundary = next(fields for name, fields in events if name == 'RESET_RECEIPT_ALIGNMENT_BOUNDARY')
    assert boundary['target_scan_ns'] == target
    assert boundary['selected_receipt_sequence'] == 11
    assert boundary['adjacent_receipt_sequence'] == 12
    assert boundary['receipt_receive_gap_ns'] <= 500_000_000
    pending = next(fields for name, fields in events
        if name == 'RESET_RECEIPT_ALIGNMENT_BOUNDARY_PENDING')
    assert pending['suppressed'] is True
    assert pending['target_scan_ns'] == target
    assert events.index(('RESET_RECEIPT_ALIGNMENT_BOUNDARY_PENDING', pending)) < events.index(
        ('RESET_RECEIPT_ALIGNMENT_BOUNDARY', boundary))


def test_observation0_reanchors_zero_after_pause_before_b1_cutoff():
    """A >500 ms W1 is retained for pause, while B1 receives fresh L2 zero."""
    value, clock = worker()
    clock.ns = 2_000_000_000
    w1 = NS(final_publish_sequence=24, received_steady_ns=1_400_000_000,
        applied_sim_stamp_ns=630_000_000)
    fresh = NS(final_publish_sequence=25, received_steady_ns=clock.ns,
        applied_sim_stamp_ns=900_000_000, applied_physics_iteration=90)
    order, events = [], []
    b1 = NS(begin_reset=lambda: order.append(('begin_reset', clock.ns)))
    value.ingress = NS(inhibit=lambda: order.append(('inhibit', clock.ns)))
    value.safety = NS(local_training=NS(set_stream_enabled=lambda enabled:
        order.append(('stream', enabled, clock.ns))))
    async def freeze_zero(*, deadline_ns):
        order.append(('fresh_zero_applied', clock.ns, deadline_ns))
        return fresh
    async def confirm(b1_arg, *, deadline_ns, zero_receipt):
        order.append(('b1_cutoff', clock.ns, deadline_ns, zero_receipt))
        assert b1_arg is b1
        assert zero_receipt is fresh
        assert clock.ns - zero_receipt.received_steady_ns <= 500_000_000
        assert clock.ns - w1.received_steady_ns > 500_000_000
        return 'confirmed-observation0', 910_000_000
    value.freeze_zero = freeze_zero
    value.commit_and_confirm_observation0 = confirm
    value.now = clock.now
    value.emit = lambda name, fields: events.append((name, fields))

    result = asyncio.run(value.confirm_observation0_after_resume(
        b1, deadline_ns=clock.ns + 15_000_000_000,
        seed=2026102900, w0=NS(final_publish_sequence=11), w1=w1,
        l1=NS(sequence=3), l2=NS(sequence=4), started_ns=1_000_000_000))

    assert result == 'confirmed-observation0'
    assert [item[0] for item in order] == [
        'begin_reset', 'inhibit', 'stream', 'fresh_zero_applied', 'stream', 'b1_cutoff']
    assert order[-1][3] is fresh
    assert events[0][0] == 'OBSERVATION0_ZERO_ANCHOR'
    assert events[0][1]['publish_sequence'] == 25
    assert events[-1][0] == 'RESET_COMPLETE'
    assert events[-1][1]['W1'] == 24
    assert events[-1][1]['zero_anchor_sequence'] == 25


def test_observation0_reanchor_keeps_real_b1_receipt_selection_within_500ms():
    """Old W1 fails the real cutoff selector; the post-resume anchor is selected."""
    from mecanum_nav_rl.core.issued_command_cutoff import (
        CutoffStatus, IssuedCommandReceiptView, ReceiptSource, ReceiptStreamBinding,
        select_reset_zero_at_cutoff,
    )
    from mecanum_nav_rl.core.lifecycle_types import EpisodeLifecycleIdentity

    value, clock = worker()
    clock.ns = 2_000_000_000
    lifecycle = EpisodeLifecycleIdentity(1, 2, 3)
    binding = ReceiptStreamBinding(90, 'session-1', 'a' * 64, lifecycle, 'base_link')
    scales = (0.25, 0.2, 0.8)

    def receipt(sequence, stamp_ns, received_ns):
        return IssuedCommandReceiptView(
            stamp_ns, 90, sequence, ReceiptSource.SAFE_STOP, 7, sequence,
            0, '', lifecycle, 'session-1', 'a' * 64, (0.0, 0.0, 0.0),
            received_ns, 'base_link', True)

    # Reproduce _005: W1 #24 is the last zero at/before 890 ms. The next
    # receipt is after the scan cutoff, while B1 evaluates #24 at +547.8 ms.
    old_w1 = receipt(24, 630_000_000, 1_400_000_000)
    after_old_cutoff = receipt(25, 900_000_000, 1_900_000_000)
    stale = select_reset_zero_at_cutoff(
        (old_w1, after_old_cutoff), binding=binding,
        cutoff_ros_ns=890_000_000, evaluation_ros_now_ns=900_000_000,
        evaluation_steady_now_ns=1_947_800_000,
        reset_barrier_ros_ns=600_000_000, physical_scales=scales)
    assert stale.status is CutoffStatus.REJECTED
    assert 'stale or future' in stale.reason

    refreshed = receipt(26, 910_000_000, 2_000_000_000)
    adjacent = receipt(27, 920_000_000, 2_020_000_000)
    calls, events = [], []
    b1 = NS(begin_reset=lambda: calls.append(('begin_reset', clock.ns)))
    value.ingress = NS(inhibit=lambda: calls.append(('inhibit', clock.ns)))
    value.safety = NS(local_training=NS(set_stream_enabled=lambda enabled:
        calls.append(('stream', enabled, clock.ns))))

    async def freeze_zero(*, deadline_ns):
        calls.append(('fresh_zero_applied', clock.ns, deadline_ns))
        return NS(final_publish_sequence=26, received_steady_ns=2_000_000_000,
            applied_sim_stamp_ns=910_000_000, applied_physics_iteration=91)

    async def commit_with_real_selector(b1_arg, *, deadline_ns, zero_receipt):
        assert b1_arg is b1
        assert zero_receipt.final_publish_sequence == 26
        selection = select_reset_zero_at_cutoff(
            (refreshed, adjacent), binding=binding,
            cutoff_ros_ns=910_000_000, evaluation_ros_now_ns=930_000_000,
            evaluation_steady_now_ns=2_030_000_000,
            reset_barrier_ros_ns=600_000_000, physical_scales=scales)
        assert selection.status is CutoffStatus.READY, selection.reason
        assert selection.receipt.final_publish_sequence == 26
        calls.append(('b1_selected', selection.receipt.final_publish_sequence,
            selection.evaluation_steady_now_ns - selection.receipt.received_steady_ns))
        return 'confirmed-observation0', 910_000_000

    value.freeze_zero = freeze_zero
    value.commit_and_confirm_observation0 = commit_with_real_selector
    value.now = clock.now
    value.emit = lambda name, fields: events.append((name, fields))
    result = asyncio.run(value.confirm_observation0_after_resume(
        b1, deadline_ns=clock.ns + 15_000_000_000, seed=2026102900,
        w0=NS(final_publish_sequence=11), w1=NS(final_publish_sequence=24),
        l1=NS(sequence=3), l2=NS(sequence=4), started_ns=1_000_000_000))

    assert result == 'confirmed-observation0'
    assert ('b1_selected', 26, 30_000_000) in calls
    assert events[0][0] == 'OBSERVATION0_ZERO_ANCHOR'
    assert events[0][1]['publish_sequence'] == 26
    assert events[-1][0] == 'RESET_COMPLETE'
