"""Regression ngoại tuyến cho wiring display và binding review thật."""
import asyncio
import importlib.util
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
    result = {**request, 'source': 'codex_image_review',
              'owner_visual_review': 'NOT_PERFORMED', 'verdict': 'PASS'}
    return request, result, png


def test_review_keeps_hash_identity_deadline_and_no_human_ack():
    request, result, png = request_and_review()
    assert runner.review_result(request, result, png, 99)
    assert not runner.review_result(request, {**result, 'verdict': 'FAIL'}, png, 99)
    for key in ('run_id', 'session_id', 'nonce', 'screenshot_sha256', 'source', 'owner_visual_review', 'verdict'):
        with pytest.raises(ValueError, match='.'):
            runner.review_result(request, {**result, key: 'wrong'}, png, 99)
    with pytest.raises(ValueError, match='expired'):
        runner.review_result(request, result, png, 100)
    with pytest.raises(ValueError, match='changed'):
        runner.review_result(request, result, png+b'changed', 99)


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
