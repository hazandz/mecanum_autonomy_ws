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
    profile = {'schema': 'b22_gui_profile/v1', 'run_id': args.run_id,
        'source_commit': args.source_commit, 'authority': args.authority,
        'install': str(prefix), 'evidence': str(tmp_path),
        'python': str(Path(runner.sys.executable).resolve()),
        'files': {str(p): runner.digest(p.read_bytes()) for p in runner.profile_inputs(prefix)}}
    raw = json.dumps(profile).encode()
    Path(args.profile).write_bytes(raw)
    args.profile_sha256 = runner.digest(raw)
    return args, profile


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
