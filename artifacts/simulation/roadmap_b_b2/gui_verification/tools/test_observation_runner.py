"""Regression ngoại tuyến cho wiring display và binding review thật."""
import asyncio
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

spec = importlib.util.spec_from_file_location('b22_current_runner', Path(__file__).with_name('observation_runner.py'))
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def test_xcb_environment_binds_gui_helpers_without_mutating_parent(tmp_path):
    authority = tmp_path/'auth'
    authority.write_text('test')
    parent = {'DISPLAY': ':0', 'QT_QPA_PLATFORM': 'wayland', 'KEEP': 'yes'}
    actual = runner.xcb_environment(parent, ':105', authority)
    assert actual['DISPLAY'] == ':105'
    assert actual['XAUTHORITY'] == str(authority.resolve())
    assert actual['QT_QPA_PLATFORM'] == 'xcb'
    assert actual['KEEP'] == 'yes'
    assert parent['DISPLAY'] == ':0'
    assert parent['QT_QPA_PLATFORM'] == 'wayland'
    with pytest.raises(ValueError):
        runner.xcb_environment(parent, 'remote:0', authority)


def request_and_review():
    png = b'bytes bound to reviewed screenshot'
    request = {'run_id': 'new-run', 'session_id': 'session', 'nonce': 'nonce',
               'screenshot_sha256': runner.digest(png), 'deadline_ns': 100}
    raw = json.dumps(request, sort_keys=True).encode()
    result = {**request, 'source': 'codex_image_review',
              'owner_visual_review': 'NOT_PERFORMED', 'verdict': 'PASS',
              'request_sha256': runner.digest(raw)}
    return request, result, png, raw


def test_review_keeps_hash_identity_deadline_and_no_human_ack():
    request, result, png, raw = request_and_review()
    assert runner.review_result(request, result, png, 99, raw)
    assert not runner.review_result(request, {**result, 'verdict': 'FAIL'}, png, 99, raw)
    for key in ('run_id', 'session_id', 'nonce', 'screenshot_sha256', 'source', 'owner_visual_review', 'verdict'):
        with pytest.raises(ValueError, match='.'):
            runner.review_result(request, {**result, key: 'wrong'}, png, 99, raw)
    with pytest.raises(ValueError, match='expired'):
        runner.review_result(request, result, png, 100, raw)
    with pytest.raises(ValueError, match='changed'):
        runner.review_result(request, result, png+b'changed', 99, raw)


@pytest.mark.parametrize('value', [None, '', '0'*64])
def test_review_requires_exact_request_bytes_hash(value):
    request, result, png, raw = request_and_review()
    if value is None:
        result.pop('request_sha256')
    else:
        result['request_sha256'] = value
    with pytest.raises(ValueError, match='request SHA-256'):
        runner.review_result(request, result, png, 99, raw)


def test_equal_request_document_with_different_bytes_is_rejected():
    request, result, png, raw = request_and_review()
    with pytest.raises(ValueError, match='request SHA-256'):
        runner.review_result(request, result, png, 99, raw+b'\n')


def profile_fixture(tmp_path):
    prefix = tmp_path/'install'
    prefix.mkdir()
    for rel in runner.INSTALL_INPUTS:
        file = prefix/rel
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_bytes(b'pinned install bytes')
    args = SimpleNamespace(profile=str(tmp_path/'profile.json'),
        install=str(prefix), evidence=str(tmp_path), run_id='TEST_A01',
        source_commit='a'*40, authority='Owner offline fakes')
    profile = {'schema': 'b22_gui_profile/v2', 'run_id': args.run_id,
        'unit': 'b22-test.service', 'parent_argv': ['/bin/bash', str(tmp_path/'wrapper.sh')],
        'source_commit': args.source_commit, 'authority': args.authority,
        'install': str(prefix), 'evidence': str(tmp_path),
        'python': str(Path(runner.sys.executable).resolve()),
        'files': {str(p): runner.digest(p.read_bytes()) for p in runner.profile_inputs(prefix)}}
    raw = json.dumps(profile).encode()
    Path(args.profile).write_bytes(raw)
    args.profile_sha256 = runner.digest(raw)
    return args, profile


def execution_fixture(profile, argv):
    """Dữ liệu /proc giả cùng schema Linux; toàn bộ kiểm tra do runner thật làm."""
    group = '/user.slice/app.slice/'+profile['unit']
    def process(pid, ppid, command):
        fields = ['S', str(ppid), str(pid), str(pid)]+['0']*16
        fields[19] = str(pid*100)
        stat = (str(pid)+' (fixture) '+' '.join(fields)+'\n').encode().hex()
        return {'stat': stat, 'stat_after': stat,
            'cmdline': (b'\0'.join(s.encode() for s in command)+b'\0').hex(),
            'cgroup': ('0::'+group+'\n').encode().hex(),
            'status': ('Uid:\t'+'\t'.join([str(runner.os.geteuid())]*4)+'\n').encode().hex()}
    return {'parent': process(321, 1, profile['parent_argv']),
            'worker': process(322, 321, argv), 'invocation_id': '1'*32,
            'collected_ns': 1234}


def test_profile_checks_every_required_install_and_source_input(tmp_path):
    args, profile = profile_fixture(tmp_path)
    assert runner.verify_profile(args) == profile
    (Path(args.install)/runner.INSTALL_INPUTS[0]).write_bytes(b'changed binary')
    with pytest.raises(ValueError, match='file SHA-256'):
        runner.verify_profile(args)


@pytest.mark.parametrize('field,value', [
    ('run_id', 'OTHER'), ('source_commit', 'b'*40),
    ('install', '/different/install'), ('python', '/different/python'),
    ('schema', 'unsupported'),
])
def test_profile_rejects_changed_binding_before_spawn(tmp_path, monkeypatch, field, value):
    args, profile = profile_fixture(tmp_path)
    profile[field] = value
    raw = json.dumps(profile).encode()
    Path(args.profile).write_bytes(raw)
    args.profile_sha256 = runner.digest(raw)
    def forbidden(*args, **kwargs):
        pytest.fail('invalid profile must not spawn a child')
    monkeypatch.setattr(runner.asyncio, 'create_subprocess_exec', forbidden)
    with pytest.raises(ValueError):
        asyncio.run(runner.run(args))
    assert not (tmp_path/args.run_id).exists()


def test_profile_requires_complete_inventory_and_external_hash(tmp_path):
    args, profile = profile_fixture(tmp_path)
    args.profile_sha256 = '0'*64
    with pytest.raises(ValueError, match='profile SHA-256'):
        runner.verify_profile(args)
    profile['files'].pop(next(iter(profile['files'])))
    raw = json.dumps(profile).encode()
    Path(args.profile).write_bytes(raw)
    args.profile_sha256 = runner.digest(raw)
    with pytest.raises(ValueError, match='inventory'):
        runner.verify_profile(args)


def test_import_origin_must_belong_to_pinned_install(tmp_path):
    args, _ = profile_fixture(tmp_path)
    file = Path(args.install)/runner.INSTALL_INPUTS[3]
    assert runner.verify_import_origins(Path(args.install), {'supervisor': SimpleNamespace(__file__=str(file))})
    with pytest.raises(ValueError, match='outside pinned install'):
        runner.verify_import_origins(Path(args.install), {'supervisor': runner})


def test_single_consume_timestamp_is_passed_without_refresh(tmp_path, monkeypatch):
    args, profile = profile_fixture(tmp_path)
    observed = []
    monkeypatch.setattr(runner.time, 'monotonic_ns', lambda: 123456789)
    raw = execution_fixture(profile, runner.worker_command(args))
    monkeypatch.setattr(runner, 'execution_observations', lambda: raw)
    async def downstream(actual, root, consumed, verified):
        observed.append((actual, root, consumed, verified))
        return 0
    # Biên gọi xuống orchestration; không thay logic consume/profile đang kiểm.
    monkeypatch.setattr(runner, 'run_consumed', downstream)
    assert asyncio.run(runner.run(args)) == 0
    consumed = json.loads((tmp_path/args.run_id/'consumed.json').read_text())
    assert observed[0][2] == consumed['at_ns'] == 123456789
    assert consumed['active_deadline_ns'] == 123456789+240_000_000_000
    assert consumed['total_deadline_ns'] == 123456789+300_000_000_000
    assert consumed['profile_sha256'] == args.profile_sha256
    with pytest.raises(FileExistsError):
        asyncio.run(runner.run(args))


class FakeXauth:
    """I/O fake: không tạo process, signal hoặc service thật."""
    pid = 123
    returncode = None

    def __init__(self, authority, *, ignore_term=False, immediate=False):
        self.authority = authority
        self.ignore_term = ignore_term
        self.immediate = immediate
        self.signals = []
        self.waited = False
        self.finished = asyncio.Event()

    async def communicate(self):
        if self.immediate:
            self.authority.write_bytes(b'fake authority')
            self.returncode = 0
            self.finished.set()
        await self.finished.wait()
        return b'', b''

    def terminate(self):
        self.signals.append('TERM')
        if not self.ignore_term:
            self.returncode = -15
            self.finished.set()

    def kill(self):
        self.signals.append('KILL')
        self.returncode = -9
        self.finished.set()

    async def wait(self):
        await self.finished.wait()
        self.waited = True
        return self.returncode


def test_xauth_success_is_joined_without_signalling(tmp_path, monkeypatch):
    async def exercise():
        auth = tmp_path/'auth'
        child = FakeXauth(auth, immediate=True)
        async def spawn(*args, **kwargs):
            assert kwargs['start_new_session'] is True
            return child
        monkeypatch.setattr(runner.asyncio, 'create_subprocess_exec', spawn)
        now = runner.time.monotonic()
        result = await runner.prepare_xauthority(auth, ':105', now+1, now+5)
        assert result['joined'] and child.waited and not child.signals
        assert auth.stat().st_mode & 0o777 == 0o600
    asyncio.run(exercise())


@pytest.mark.parametrize('cancel,late_spawn,ignore_term', [(False, False, True), (True, False, False), (True, True, False)])
def test_xauth_timeout_cancel_and_late_handle_are_reaped(tmp_path, monkeypatch, cancel, late_spawn, ignore_term):
    async def exercise():
        child = FakeXauth(tmp_path/'auth', ignore_term=ignore_term)
        started = asyncio.Event()
        async def spawn(*args, **kwargs):
            started.set()
            if late_spawn:
                await asyncio.sleep(.03)
            return child
        monkeypatch.setattr(runner.asyncio, 'create_subprocess_exec', spawn)
        now = runner.time.monotonic()
        task = asyncio.create_task(runner.prepare_xauthority(tmp_path/'auth', ':105', now+.01, now+2))
        await started.wait()
        if cancel:
            await asyncio.sleep(0)
            task.cancel()
        with pytest.raises(asyncio.CancelledError if cancel else TimeoutError):
            await task
        record = json.loads((tmp_path/'xauth-record.json').read_text())
        assert child.waited and record['joined'] and not record['cleanup_errors']
        assert child.signals == (['TERM', 'KILL'] if ignore_term else ['TERM'])
        assert record['cleanup_deadline_ns'] <= int((now+2)*1e9)
    asyncio.run(exercise())


def test_monitor_detects_critical_role_exit_without_signalling():
    async def exercise():
        sup = SimpleNamespace(owned=[SimpleNamespace(name='gui',process=SimpleNamespace(returncode=2))], _heartbeat_observer_process=None)
        with pytest.raises(RuntimeError, match='gui:2'):
            await runner.monitor_owned(sup,asyncio.Event(),float('inf'),None,None)
    asyncio.run(exercise())


def test_capture_requires_viewable_geometry_depth_and_matching_pid():
    info = 'Map State: IsViewable\n Width: 1280\n Height: 800\n Depth: 24\n'
    runner.validate_window_metadata(info, '_NET_WM_PID(CARDINAL) = 123', 123)
    for text in (info.replace('IsViewable','IsUnMapped'), info.replace('Depth: 24','Depth: 0'), info.replace('Width: 1280','')):
        with pytest.raises(ValueError):
            runner.validate_window_metadata(text, '_NET_WM_PID(CARDINAL) = 123', 123)
    with pytest.raises(ValueError):
        runner.validate_window_metadata(info, '_NET_WM_PID(CARDINAL) = 999', 123)


def test_tracked_identity_error_is_retained_instead_of_raising_from_finalization():
    def unknown(process):
        raise ValueError('identity unknown')
    launcher = SimpleNamespace(records=[SimpleNamespace(pid=321,process=SimpleNamespace(returncode=0))],group_alive=unknown)
    assert runner.tracked_residue(launcher) == [{'pid':321,'state':'UNKNOWN','error':'identity unknown'}]


def test_monitor_does_not_reclassify_requested_cleanup_exit():
    async def exercise():
        stop = asyncio.Event()
        sup = SimpleNamespace(_cleanup_requested=True)
        task = asyncio.create_task(runner.monitor_owned(sup,stop,float('inf'),None,None))
        await asyncio.sleep(0)
        assert not task.done()
        stop.set()
        await task
    asyncio.run(exercise())


def test_startup_cleanup_preserves_primary_over_late_graph_error():
    async def exercise():
        evaluator = asyncio.get_running_loop().create_future()
        monitor = asyncio.get_running_loop().create_future()
        class Supervisor:
            _cleanup_requested = False
            async def start(self):
                self._cleanup_requested = True
                evaluator.set_exception(RuntimeError('secondary graph disappeared'))
                await asyncio.sleep(.01)
                raise RuntimeError('primary review rejected')
        with pytest.raises(RuntimeError, match='primary review rejected'):
            await runner.await_start(Supervisor(),evaluator,monitor,float('inf'),float('inf'))
        evaluator.exception()
        monitor.cancel()
    asyncio.run(exercise())


@pytest.mark.parametrize('late_at', ['none', 'hash', 'completion', 'receipt'])
def test_completion_deadline_includes_hash_and_publications(tmp_path, late_at):
    clock = [1_000_000_000]
    start = clock[0]
    deadline = start+300_000_000_000
    stored = {}
    def read_log(path):
        assert path == tmp_path/'observation.jsonl'
        if late_at == 'hash':
            clock[0] = deadline
        return b'original evidence bytes\n'
    def publish(path, raw):
        stored[path.name] = raw
        if ((late_at == 'completion' and path.name == 'completion.json')
                or (late_at == 'receipt' and path.name == 'completion-publication.json')):
            clock[0] = deadline+1
    status = runner.publish_completion(tmp_path, {'cleanup_clean': True, 'failures': []},
        start, now_ns=lambda: clock[0], publish=publish, read_log=read_log)
    assert set(stored) == {'completion.json', 'completion-publication.json'}
    assert status == (0 if late_at == 'none' else 3)
    errors = runner.completion_timing_errors(
        {'at_ns': start, 'total_deadline_ns': deadline}, stored['completion.json'],
        json.loads(stored['completion-publication.json']), status, clock[0])
    assert bool(errors) == (late_at != 'none'), errors


def test_process_ending_late_fails_even_with_successful_marker(tmp_path):
    start = 100
    deadline = start+300_000_000_000
    stored = {}
    assert runner.publish_completion(tmp_path, {'cleanup_clean': True, 'failures': []},
        start, now_ns=lambda: start+1, read_log=lambda path: b'log',
        publish=lambda path, raw: stored.setdefault(path.name, raw)) == 0
    consumed = {'at_ns': start, 'total_deadline_ns': deadline}
    receipt = json.loads(stored['completion-publication.json'])
    assert runner.completion_timing_errors(consumed, stored['completion.json'], receipt, 0, start+2) == ()
    for ended in [deadline, deadline+1]:
        assert 'completion_or_process_after_total_deadline' in runner.completion_timing_errors(
            consumed, stored['completion.json'], receipt, 0, ended)
    assert 'process_exit_nonzero' in runner.completion_timing_errors(
        consumed, stored['completion.json'], receipt, 3, start+2)
    assert runner.completion_timing_errors(consumed, stored['completion.json'], receipt, 0, None)
    assert 'completion_hash_mismatch' in runner.completion_timing_errors(
        consumed, stored['completion.json']+b'\n', receipt, 0, start+2)


@pytest.mark.parametrize('case', ['on_time', 'late', 'invocation_changed', 'unloaded_defaults',
    'terminal_group_not_retained', 'different_group', 'foreign_unit', 'foreign_initial_invocation',
    'foreign_main_pid', 'wrong_command', 'wrong_run_id', 'wrong_profile_hash', 'wrong_worker_argv',
    'changed_wrapper', 'wrong_packet_hash', 'wrong_executable_path'])
def test_terminal_cli_uses_real_exit_properties_and_timing_gate(tmp_path, monkeypatch, case):
    args, profile = profile_fixture(tmp_path)
    root = tmp_path/args.run_id
    root.mkdir()
    wrapper = Path(profile['parent_argv'][1])
    wrapper.write_text('#!/bin/bash\n# fixture only; never executed\n')
    argv = runner.worker_command(args)
    execution_raw = execution_fixture(profile, argv)
    execution_raw['collected_ns'] = 500
    execution = runner.normalize_execution(profile, argv, execution_raw)
    start = 1000
    deadline = start+300_000_000_000
    consumed = {'at_ns': start, 'total_deadline_ns': deadline, 'source_commit': 'a'*40,
        'run_id': args.run_id, 'profile_sha256': args.profile_sha256, 'execution': execution}
    (root/'observation.jsonl').write_bytes(b'log\n')
    assert runner.publish_completion(root, {'cleanup_clean': True, 'failures': []},
        start, now_ns=lambda: start+1000) == 0
    packet = {'run_id': args.run_id, 'source_commit': args.source_commit,
        'profile': args.profile, 'profile_sha256': args.profile_sha256,
        'source_runner_sha256': runner.digest(Path(runner.__file__).read_bytes()),
        'unit': profile['unit'], 'parent_argv': profile['parent_argv'],
        'worker_argv': argv, 'wrapper_sha256': runner.digest(wrapper.read_bytes()),
        'launch_command': ['systemd-run', '--unit='+profile['unit'], *profile['parent_argv']]}
    initial = {'Id': profile['unit'], 'InvocationID': '1'*32,
               'ControlGroup': execution['parent']['cgroup'], 'MainPID': '321',
               'ExecStart': '{ path=/bin/bash ; argv[]='+ ' '.join(profile['parent_argv'])+' ; ignore_errors=no ; }'}
    terminal = {**initial, 'MainPID': '0', 'ExecMainPID': '321',
        'ExecMainCode': str(runner.os.CLD_EXITED), 'ExecMainStatus': '0',
        'ExecMainExitTimestampMonotonic': '20', 'Result': 'success',
        'LoadState': 'loaded', 'ActiveState': 'active', 'SubState': 'exited'}
    if case == 'late':
        terminal['ExecMainExitTimestampMonotonic'] = str(deadline//1000)
    elif case == 'invocation_changed':
        terminal['InvocationID'] = 'inv-2'
    elif case == 'unloaded_defaults':
        terminal.update(InvocationID='', ControlGroup='', LoadState='not-found',
                        ActiveState='inactive', SubState='dead', ExecMainCode='0')
    elif case == 'terminal_group_not_retained':
        terminal['ControlGroup'] = ''
    elif case == 'different_group':
        terminal['ControlGroup'] = '/different/group'
    elif case == 'foreign_unit':
        initial['Id'] = terminal['Id'] = 'b22-foreign.service'
    elif case == 'foreign_initial_invocation':
        initial['InvocationID'] = terminal['InvocationID'] = '2'*32
    elif case == 'foreign_main_pid':
        initial['MainPID'] = terminal['ExecMainPID'] = '999'
    elif case == 'wrong_command':
        initial['ExecStart'] = terminal['ExecStart'] = '{ path=/bin/bash ; argv[]=/bin/bash /different.sh ; ignore_errors=no ; }'
    elif case == 'wrong_executable_path':
        initial['ExecStart'] = terminal['ExecStart'] = initial['ExecStart'].replace('path=/bin/bash', 'path=/foreign/program')
    elif case == 'wrong_run_id':
        consumed['run_id'] = 'ANOTHER_RUN'
    elif case == 'wrong_profile_hash':
        consumed['profile_sha256'] = '0'*64
    elif case == 'wrong_worker_argv':
        packet['worker_argv'] = ['different', 'command']
    elif case == 'changed_wrapper':
        wrapper.write_text('changed after packet hash')
    (root/'consumed.json').write_text(json.dumps(consumed))
    serialize = lambda values: ''.join(k+'='+v+'\n' for k,v in values.items())
    evidence = tmp_path/'unit.json'
    evidence.write_text(json.dumps({'initial_unit': serialize(initial),
        'terminal_unit': serialize(terminal), 'collected_end_ns': deadline+10_000}))
    packet_path = tmp_path/'packet.json'
    packet_path.write_text(json.dumps(packet))
    checksum = runner.digest(packet_path.read_bytes())
    if case == 'wrong_packet_hash':
        checksum = '0'*64
    monkeypatch.setattr(runner.sys, 'argv', ['runner', '--validate-terminal', str(root), str(evidence), str(packet_path), checksum])
    if case == 'wrong_packet_hash':
        with pytest.raises(ValueError, match='packet SHA-256'):
            runner.main()
        assert not (root/'completion-acceptance.json').exists()
        return
    accepted = case in ('on_time', 'terminal_group_not_retained')
    assert runner.main() == (0 if accepted else 3)
    result = json.loads((root/'completion-acceptance.json').read_text())
    assert result['timing_verdict'] == ('PASS' if accepted else 'FAIL')


@pytest.mark.parametrize('mutation', ['nonce', 'parent_argv', 'worker_argv', 'cgroup', 'identity', 'uid'])
def test_proc_normalization_rejects_wrong_ownership(tmp_path, mutation):
    args, profile = profile_fixture(tmp_path)
    argv = runner.worker_command(args)
    raw = execution_fixture(profile, argv)
    if mutation == 'nonce':
        raw['invocation_id'] = None
    elif mutation == 'parent_argv':
        raw['parent']['cmdline'] = b'/bin/bash\0/foreign\0'.hex()
    elif mutation == 'worker_argv':
        raw['worker']['cmdline'] = b'foreign\0'.hex()
    elif mutation == 'cgroup':
        raw['worker']['cgroup'] = b'0::/foreign\n'.hex()
    elif mutation == 'identity':
        raw['worker']['stat_after'] = raw['parent']['stat']
    elif mutation == 'uid':
        raw['parent']['status'] = b'Uid:\t0\t0\t0\t0\n'.hex()
    with pytest.raises(ValueError):
        runner.normalize_execution(profile, argv, raw)
