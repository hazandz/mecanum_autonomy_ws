"""Biên deadline/ownership worker bằng I/O fakes, không tạo ROS context."""
import asyncio
import json
from types import SimpleNamespace as NS
import pytest
from mecanum_nav_rl.runtime_simulation.b23_runner import TrainingWorkerIO


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
def test_freeze_step_streams_keeps_closing_order_without_issuing_stop(last_source):
    from mecanum_nav_rl_interfaces.msg import CommandEnvelope
    value, clock = worker()
    calls = []
    source = CommandEnvelope.SOURCE_SAFE_STOP if last_source == 'safe_stop' else CommandEnvelope.SOURCE_POLICY
    value.safety = NS(local_training=NS(last_output=NS(source=source, source_instance_id=44, sequence=7),
        set_stream_enabled=lambda enabled: calls.append(('stream', enabled))))
    value.ingress.last_published_sample_sequence = 9
    value.ingress.pause_admission_publication = lambda: calls.append(('pause_admission',))
    value.read_native_input_watermark = lambda: 9
    value.final = NS(publisher_instance_id=55, last_publication=NS(source=source,
        source_instance_id=44, sequence=7, final_publish_sequence=20))
    value.ingress.backend_state = NS(fault_flags=0, applied_final_publish_sequence=20,
        applied_final_publisher_instance_id=55, local_zero_override=False)
    value.emit = lambda name, record: calls.append((name, record))
    asyncio.run(value.freeze_step_streams(deadline_ns=clock.ns+20_000_000))
    assert calls[0:2] == [('stream', False), ('pause_admission',)]
    assert calls[-1][0] == 'STEP_STREAMS_FROZEN'
    assert calls[-1][1]['source'] == source
    assert not any(name == 'hold' for name, *rest in calls)


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
    adapter = NS(last_output=NS(source=CommandEnvelope.SOURCE_SAFE_STOP, source_instance_id=44, sequence=1),
        command=None, noisy=None, set_stream_enabled=lambda state: history.append(('stream', state)),
        set_policy_hold=lambda state: history.append(('hold', state)))
    value.safety = NS(local_training=adapter)
    value.final = NS(publisher_instance_id=55, last_publication=NS(source=CommandEnvelope.SOURCE_SAFE_STOP,
        source_instance_id=44, sequence=1, final_publish_sequence=2))
    value.ingress.lifecycle = life
    value.ingress.last_published_sample_sequence = 1
    value.ingress.pause_admission_publication = lambda: history.append(('freeze_admission',))
    value.ingress.scans = {}
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
        if adapter.command:
            value.ingress.scans[clock.ns] = True
    value.pause = pause
    pending = NS(step_index=1, transition_id='actual-b1-token')
    commit_calls = []
    def record(envelope, *, action_barrier_ns):
        history.append(('issued', envelope.sequence))
        assert history[-2][0] == 'publish'
        assert action_barrier_ns <= envelope.header.stamp.sec*10**9+envelope.header.stamp.nanosec
    transition = object()
    def commit(cutoff):
        commit_calls.append(cutoff)
        if len(commit_calls) == 1: raise B1SnapshotPending('application not received yet')
        if timing == 'late_commit': clock.ns = 3_000_000_000
        return transition
    b1 = NS(begin_step=lambda: pending, record_issuance=record, commit_step=commit)
    if timing == 'ready':
        assert asyncio.run(value.policy_step(b1, (0., .4, 0.))) is transition
    else:
        with pytest.raises(TimeoutError, match='step deadline'):
            asyncio.run(value.policy_step(b1, (0., .4, 0.)))
    tags = [row[0] for row in history]
    assert tags.index('bind') < tags.index('arm') < tags.index('publish') < tags.index('issued') < tags.index('hold')
    envelope = next(row[1] for row in history if row[0] == 'publish')
    assert envelope.twist.linear.y == pytest.approx(.08)
    assert len([row for row in history if row[0] == 'publish']) == 1
    assert len(commit_calls) == 2 and min(commit_calls) >= 1_102_000_000
    assert clock.ns < 3_000_000_000 if timing == 'ready' else clock.ns == 3_000_000_000


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
    from mecanum_nav_rl.runtime_simulation.b23_runner import service_launch_command, SERVICE_PROPERTIES
    packet = dict(unit='b23-test.service',environment={'ROS_DOMAIN_ID':'84'},python='/pinned/python')
    template = service_launch_command(packet,'/packet.json','{PACKET_SHA256}')
    actual = service_launch_command(packet,'/packet.json','a'*64)
    assert actual == [value.replace('{PACKET_SHA256}','a'*64) for value in template]
    assert actual[:3] == ['systemd-run','--user','--unit=b23-test.service']
    assert '--scope' not in actual and '--collect' not in actual
    assert '--expand-environment=no' in actual
    assert set(value for value in actual if value.startswith('--property=')) == {'--property='+v for v in SERVICE_PROPERTIES}
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
