"""Offline-only unit tests for the B22 RUN001 packet and tool boundaries."""
from __future__ import annotations

import concurrent.futures
import importlib
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest

HERE = Path(__file__).resolve().parent


def _tool_modules():
    if str(HERE) not in sys.path:
        sys.path.insert(0, str(HERE))
    return (
        importlib.import_module('observation_guard'),
        importlib.import_module('observation_runner'),
        importlib.import_module('observation_sink'),
    )


guard, runner, sink = _tool_modules()
ObservationFailure = runner.ObservationFailure
OwnerAbort = runner.OwnerAbort
ScreenshotReadiness = runner.ScreenshotReadiness
assert_packet_inputs = runner.assert_packet_inputs
enforce_runtime_cap = runner.enforce_runtime_cap
evaluate_observation = runner.evaluate_observation
preflight_desktop = runner.preflight_desktop
require_run_gui = runner.require_run_gui
classify_final_status = runner.classify_final_status
_run = runner._run
TOOL_PATHS = runner.TOOL_PATHS
strict_gui_value = runner.strict_gui_value
ObservationEvidenceSink = sink.ObservationEvidenceSink


def _payload(index=1):
    return {'run_id': guard.RUN_ID, 'contender': index}


def test_acquire_once_and_replay_refusal(tmp_path):
    """Test acquire once and replay refusal."""
    path = tmp_path / 'acquisition.json'
    guard.acquire_once(path, _payload())
    assert json.loads(path.read_text()) == _payload()
    with pytest.raises(guard.GuardError, match='already exists'):
        guard.acquire_once(path, _payload(2))
    assert json.loads(path.read_text()) == _payload()


def test_two_contenders_have_exactly_one_winner(tmp_path):
    """Test two contenders have exactly one winner."""
    path = tmp_path / 'acquisition.json'

    def contend(index):
        try:
            guard.acquire_once(path, _payload(index))
            return 'won'
        except guard.GuardError:
            return 'lost'

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(contend, (1, 2)))
    assert sorted(outcomes) == ['lost', 'won']
    assert json.loads(path.read_text())['contender'] in (1, 2)


def test_dangling_partial_acquisition_is_still_consumed(tmp_path):
    """Test dangling partial acquisition is still consumed."""
    path = tmp_path / 'acquisition.json'
    path.write_bytes(b'{"partial":')
    with pytest.raises(guard.GuardError, match='already exists'):
        guard.acquire_once(path, _payload())
    assert path.read_bytes() == b'{"partial":'


def test_acquisition_write_failure_retains_exclusive_file(tmp_path):
    """Test acquisition write failure retains exclusive file."""
    path = tmp_path / 'acquisition.json'

    def fail_open(_path, flags, mode):
        descriptor = os.open(path, flags, mode)
        os.write(descriptor, b'{')
        os.close(descriptor)
        raise OSError('injected write/open failure')

    with pytest.raises(OSError, match='injected'):
        guard.acquire_once(path, _payload(), open_fn=fail_open)
    assert path.exists()
    with pytest.raises(guard.GuardError):
        guard.acquire_once(path, _payload())


def test_approval_packet_and_tool_pin_mismatch_rejects(tmp_path):
    """Test approval packet and tool pin mismatch rejects."""
    packet_path = tmp_path / 'packet.json'
    tool = tmp_path / 'tool.py'
    approval_path = tmp_path / 'approval.json'
    tool.write_text('tool bytes')
    packet = {
        'run_id': guard.RUN_ID,
        'production_source_pin': guard.PRODUCTION_SOURCE_PIN,
        'tool_sha256': {'tool.py': guard.sha256_file(tool)},
    }
    packet_path.write_text(json.dumps(packet))
    approval = {
        'schema_id': 'b22_gui_observation_owner_approval/v1',
        'run_id': guard.RUN_ID,
        'packet_sha256': guard.sha256_file(packet_path),
        'packet_commit': 'a' * 40,
        'production_source_pin': guard.PRODUCTION_SOURCE_PIN,
        'tool_sha256': {'tool.py': '0' * 64},
    }
    approval_path.write_text(json.dumps(approval))
    with pytest.raises(guard.GuardError, match='tool_sha256'):
        guard.validate_approval(
            packet_path=packet_path, approval_path=approval_path,
            expected_commit='a' * 40, tool_paths={'tool.py': tool},
        )


def test_packet_input_pin_mismatch_fails_closed():
    """Test packet input pin mismatch fails closed."""
    packet = {
        'run_id': guard.RUN_ID, 'capacity': 1, 'gui': True,
        'scenario_id': 'B2_SOAK_V1', 'world': 'b2_training_arena',
        'robot': 'mecanum_b2', 'backend': 'NATIVE_B2_BACKEND_V1',
        'production_source_pin': guard.PRODUCTION_SOURCE_PIN,
        'input_sha256': {
            'asset_manifest': guard.MANIFEST_SHA256,
            'resolved_soak': guard.RESOLVED_SHA256,
            'config_hash': guard.CONFIG_HASH,
            'scenario': guard.SCENARIO_SHA256,
        },
        'tool_sha256': {},
    }
    assert_packet_inputs(packet, {})
    packet['production_source_pin'] = '0' * 40
    with pytest.raises(guard.GuardError, match='production_source_pin'):
        assert_packet_inputs(packet, {})


@pytest.mark.parametrize('value, expected', [('true', True), ('false', False)])
def test_gui_parser_accepts_only_lowercase_literals(value, expected):
    """Test gui parser accepts only lowercase literals."""
    assert strict_gui_value(value) is expected


@pytest.mark.parametrize('value', ['True', 'FALSE', 'yes', '1', '', ' true'])
def test_gui_parser_rejects_noncanonical_values(value):
    """Test gui parser rejects noncanonical values."""
    with pytest.raises(Exception):
        strict_gui_value(value)


def test_run001_rejects_gui_false_before_acquisition():
    """Test run001 rejects gui false before acquisition."""
    with pytest.raises(ObservationFailure, match='--gui true'):
        require_run_gui(False)
    require_run_gui(True)


def test_tty_and_existing_desktop_socket_are_mandatory():
    """Test tty and existing desktop socket are mandatory."""
    with pytest.raises(ObservationFailure, match='TTY'):
        preflight_desktop(False, {'DISPLAY': ':0'}, lambda _path: True)
    with pytest.raises(ObservationFailure, match='desktop socket'):
        preflight_desktop(True, {'DISPLAY': ':0'}, lambda _path: False)
    preflight_desktop(
        True, {
            'WAYLAND_DISPLAY': 'wayland-0',
            'XDG_RUNTIME_DIR': '/run/user/9',
        },
        lambda path: Path(path) == Path('/run/user/9/wayland-0'),
    )


def test_owner_ack_requires_a_real_screenshot_file(tmp_path):
    """Test owner ack requires a real screenshot file."""
    class Readiness:
        async def owner_ack(self, _timeout):
            return True, str(tmp_path / 'missing.png')

    async def check():
        with pytest.raises(FileNotFoundError):
            await ScreenshotReadiness(Readiness()).owner_ack(60.0)

    import asyncio
    asyncio.run(check())


def test_owner_ack_does_not_invent_acknowledgment(tmp_path):
    """Test owner ack does not invent acknowledgment."""
    class Readiness:
        async def owner_ack(self, _timeout):
            return False, 'owner_ack_timeout'

    async def check():
        result = await ScreenshotReadiness(Readiness()).owner_ack(60.0)
        assert result == (False, 'owner_ack_timeout')

    import asyncio
    asyncio.run(check())


def test_owner_ack_cancellation_is_preserved():
    """Test owner ack cancellation is preserved."""
    import asyncio

    class Readiness:
        async def owner_ack(self, _timeout):
            await asyncio.Future()

    async def check():
        readiness = ScreenshotReadiness(Readiness())
        task = asyncio.create_task(readiness.owner_ack(60.0))
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert readiness.owner_ack_cancelled is True

    asyncio.run(check())


def test_evidence_is_exclusive_correlated_and_append_only(tmp_path):
    """Test evidence is exclusive correlated and append only."""
    sink = ObservationEvidenceSink(
        tmp_path, guard.RUN_ID, 'session-1', monotonic_ns=lambda: 42,
    )
    sink.record('fact', {'paused': True})
    sink.close()
    rows = [
        json.loads(line)
        for line in (tmp_path / 'observation.jsonl').read_text().splitlines()
    ]
    assert rows[0]['sequence'] == 1
    assert rows[0]['steady_time_ns'] == 42
    assert rows[0]['run_id'] == guard.RUN_ID
    assert rows[0]['session_id'] == 'session-1'
    with pytest.raises(FileExistsError):
        ObservationEvidenceSink(tmp_path, guard.RUN_ID, 'session-2')


def test_evidence_write_failure_propagates(tmp_path):
    """Test evidence write failure propagates."""
    class BrokenStream:
        def write(self, _value):
            raise OSError('disk full')

        def close(self):
            pass

    sink = ObservationEvidenceSink.__new__(ObservationEvidenceSink)
    import threading
    from datetime import datetime, timezone
    sink.root = tmp_path
    sink.run_id = guard.RUN_ID
    sink.session_id = 'session'
    sink._monotonic_ns = lambda: 1
    sink._utc_now = lambda: datetime.now(timezone.utc)
    sink._lock = threading.Lock()
    sink._sequence = 0
    sink._stream = BrokenStream()
    with pytest.raises(OSError, match='disk full'):
        sink.record('must-fail', {})


def test_fallback_cleanup_signals_only_captured_owned_groups():
    """Test fallback cleanup signals only captured owned groups."""
    from observation_runner import _fallback_cleanup

    class Launcher:
        def __init__(self):
            self.live = {101, 202, 303}
            self.signaled = []

        def group_alive(self, process):
            return process.pid in self.live

        async def stop_group(self, process, sig):
            self.signaled.append((process.pid, sig))
            self.live.discard(process.pid)

    class Record:
        def __init__(self, pid):
            self.pid = pid
            self.name = f'owned-{pid}'
            self.process = SimpleNamespace(pid=pid)

    import asyncio
    launcher = Launcher()
    errors = []
    asyncio.run(_fallback_cleanup(
        launcher, [Record(101), Record(202)], None, errors,
    ))
    assert {pid for pid, _sig in launcher.signaled} == {101, 202}
    assert 303 in launcher.live
    assert errors == []


class _Observer:
    def __init__(self, tick=0.1, change_clock=False, unpause=False):
        from collections import deque
        self.events = deque()
        self.tick = tick
        self.calls = 0
        self.change_clock = change_clock
        self.unpause = unpause
        self.now = 0.0

    def spin_once(self, timeout_s):
        self.now += min(self.tick, timeout_s)
        self.calls += 1
        clock = SimpleNamespace(sec=0, nanosec=0)
        if self.change_clock and self.calls > 5:
            clock.nanosec = 1
        self.events.append(('clock', clock, self.now))
        message = SimpleNamespace(
            session_id='session', config_hash='config',
            backend_instance_id=9,
            header=SimpleNamespace(frame_id='b2_training_arena'),
            paused=not (self.unpause and self.calls > 4),
            actuator_inhibited=True, fault_flags=0,
            applied_receipt_valid=False, status_sequence=self.calls,
        )
        self.events.append(('backend', message, self.now))


def test_paused_observation_does_not_grade_scan_or_contact_health():
    """Test paused observation does not grade scan or contact health."""
    observer = _Observer(tick=0.25)

    def clock():
        return observer.now

    result = evaluate_observation(
        plan=SimpleNamespace(session_id='session', config_hash='config'),
        observer=observer, duration_s=2.0, steady=clock,
        sleep=lambda duration: setattr(
            observer, 'now', observer.now + duration,
        ),
    )
    assert result['observed_seconds'] >= 2.0


def test_clock_advance_and_loss_of_inhibit_fail_paused_observation():
    """Test clock advance and loss of inhibit fail paused observation."""
    plan = SimpleNamespace(session_id='session', config_hash='config')
    for observer in (_Observer(change_clock=True), _Observer(unpause=True)):
        with pytest.raises(ObservationFailure):
            evaluate_observation(
                plan=plan, observer=observer, duration_s=2.0,
                steady=lambda: observer.now,
                sleep=lambda duration: setattr(
                    observer, 'now', observer.now + duration,
                ),
            )


def test_owner_gui_close_is_aborted_not_pass():
    """Test owner gui close is aborted not pass."""
    observer = _Observer()

    class Exited:
        def done(self):
            return True
    with pytest.raises(OwnerAbort):
        evaluate_observation(
            plan=SimpleNamespace(session_id='session', config_hash='config'),
            observer=observer, duration_s=2.0, gui_exit=Exited(),
        )


def test_runtime_cap_no_retry_and_final_status_contract(tmp_path):
    """Test runtime cap no retry and final status contract."""
    enforce_runtime_cap(10.0, 249.9)
    with pytest.raises(ObservationFailure, match='240 s'):
        enforce_runtime_cap(10.0, 250.1)
    path = tmp_path / f'{guard.RUN_ID}-test.json'
    guard.acquire_once(path, _payload())
    with pytest.raises(guard.GuardError):
        guard.acquire_once(path, _payload(2))
    assert classify_final_status(True, False, []) == 'PASS'
    assert classify_final_status(False, False, []) == 'FAIL'
    assert classify_final_status(False, True, []) == 'ABORTED_BY_OWNER'
    assert classify_final_status(True, False, ['residue']) == 'FAIL'


class _FakeSink:
    def __init__(self, events, fail_first=False):
        self.events = events
        self.fail_first = fail_first

    def record(self, event, _facts):
        self.events.append(f'evidence:{event}')
        if self.fail_first:
            self.fail_first = False
            raise OSError('injected evidence write failure')

    def close(self):
        self.events.append('sink-close')


class _FakeProcess:
    def __init__(self, pid):
        self.pid = pid
        self.returncode = None
        self.exited = __import__('asyncio').Event()

    async def wait(self):
        await self.exited.wait()
        self.returncode = 0
        return 0


class _FakeLauncher:
    def __init__(self, events):
        self.events = events
        self.processes = []

    async def start(self, command, _environment):
        self.events.append('process-start')
        process = _FakeProcess(os.getpid())
        process.command = command
        self.processes.append(process)
        return process

    def group_alive(self, _process):
        return False

    async def stop_group(self, _process, _sig):
        self.events.append('signal-owned')


class _FakeReadiness:
    def __init__(self, screenshot):
        self.screenshot = screenshot

    async def owner_ack(self, _timeout):
        return True, str(self.screenshot)

    def bind_environment(self, _environment):
        pass


class _FakeObserver:
    def __init__(self, events):
        self.events = events

    def start(self):
        self.events.append('observer-start')

    def close(self):
        self.events.append('observer-close')


def _fake_runner_inputs(tmp_path, *, fail_start=False, sink_failure=False,
                        mismatch=False):
    from types import SimpleNamespace

    events = []
    screenshot = tmp_path / 'owner.png'
    screenshot.write_bytes(b'owner screenshot bytes')
    installs = {'installed-fixture': 'a' * 64}
    dependencies = {'fixture_dependency': 'present'}
    tools = guard.tool_hashes(TOOL_PATHS)
    packet = {
        'run_id': guard.RUN_ID, 'capacity': 1, 'gui': True,
        'scenario_id': 'B2_SOAK_V1', 'world': 'b2_training_arena',
        'robot': 'mecanum_b2', 'backend': 'NATIVE_B2_BACKEND_V1',
        'production_source_pin': guard.PRODUCTION_SOURCE_PIN,
        'input_sha256': {
            'asset_manifest': guard.MANIFEST_SHA256,
            'resolved_soak': guard.RESOLVED_SHA256,
            'config_hash': guard.CONFIG_HASH,
            'scenario': guard.SCENARIO_SHA256,
        },
        'tool_sha256': tools,
        'installed_sha256': installs,
        'dependency_fingerprints': dependencies,
    }
    if mismatch:
        packet['tool_sha256']['observation_runner.py'] = '0' * 64
    packet_path = tmp_path / 'packet.json'
    packet_path.write_text(json.dumps(packet, sort_keys=True))
    approval = {
        'schema_id': 'b22_gui_observation_owner_approval/v1',
        'run_id': guard.RUN_ID,
        'packet_sha256': guard.sha256_file(packet_path),
        'packet_commit': 'a' * 40,
        'production_source_pin': guard.PRODUCTION_SOURCE_PIN,
        'tool_sha256': tools,
    }
    approval_path = tmp_path / 'approval.json'
    approval_path.write_text(json.dumps(approval))
    paths = {
        'description_share': tmp_path / 'description',
        'rl_share': tmp_path / 'rl',
        'bringup_share': tmp_path / 'bringup',
        'backend_prefix': tmp_path / 'backend',
        'interfaces_prefix': tmp_path / 'interfaces',
        'physics_engine_path': tmp_path / 'physics',
    }
    runtime_plan = {}

    @dataclass(frozen=True)
    class FakePlan:
        session_id: str
        config_hash: str
        coordinator_ingress_instance_id: int
        environment: dict
        commands: tuple
        world_file: Path

    def build_plan(_gui, runtime_dir):
        events.append('build-plan')
        world = runtime_dir / 'world.runtime.sdf'
        world.write_bytes(b'bound world')
        params = runtime_dir / 'robot_state_publisher.params.yaml'
        params.write_text('params')
        descriptor_path = runtime_dir / 'run_descriptor.json'
        descriptor_path.write_text('{}\n')
        descriptor = {
            'world_source_sha256': '1' * 64,
            'runtime_bound_world_sha256': guard.sha256_file(world),
            'coordinator_ingress_instance_id': 99,
            'robot_state_publisher_params_sha256': guard.sha256_file(params),
        }
        plan = FakePlan(
            'session-test', guard.CONFIG_HASH, 99,
            {'GZ_PARTITION': 'test_partition'},
            (('gz', 'sim', str(world)), ('gz', 'gui')), world,
        )
        runtime_plan.update(plan=plan, params=params)
        return plan, paths, descriptor, descriptor_path

    class Supervisor:
        def __init__(self, plan, launcher, readiness, evidence_sink):
            self.plan = plan
            self.launcher = launcher
            self.readiness = readiness
            self.evidence_sink = evidence_sink
            self.owned = []
            self.gui_opened = False

        async def start(self):
            events.append('supervisor-start')
            accepted, ref = await self.readiness.owner_ack(60)
            assert accepted and ref == str(screenshot.resolve())
            from mecanum_nav_bringup.local_training_process_supervisor import (
                ProcessRecord,
            )
            for name in ('parameter_bridge', 'server', 'gui'):
                process = _FakeProcess(os.getpid())
                self.owned.append(ProcessRecord(
                    name, (name,), os.getpid(), process,
                ))
            self.gui_opened = True
            if fail_start:
                raise RuntimeError('injected partial startup failure')

        async def cleanup(self):
            events.append('cleanup')
            for record in self.owned:
                record.process.exited.set()

    def acquire(_path, _payload):
        events.append('consume')

    def sink_factory(_root, _run_id, _session):
        return _FakeSink(events, fail_first=sink_failure)

    args = SimpleNamespace(
        gui=True, packet=str(packet_path), approval_file=str(approval_path),
        approved_commit='a' * 40, temp_root=str(tmp_path),
        evidence_root=str(tmp_path / 'evidence'),
        guard_path=str(tmp_path / 'guard.json'),
    )
    (tmp_path / 'evidence').mkdir()
    deps = {
        'preflight': lambda *_args: None,
        'stdin_isatty': True,
        'environ': {},
        'exists': lambda _path: True,
        'verify_commit': lambda *_args: None,
        'install_preflight': lambda: installs,
        'build_plan': build_plan,
        'acquire': acquire,
        'sink_factory': sink_factory,
        'launcher': _FakeLauncher(events),
        'readiness': _FakeReadiness(screenshot),
        'supervisor_factory': Supervisor,
        'observer_factory': lambda: _FakeObserver(events),
        'evaluate_observation': lambda **_kwargs: {'observed_seconds': 1.0},
        'observation_duration': 0.01,
    }
    return args, deps, events


def test_no_runtime_process_before_consume_and_cleanup_after_partial_start(
    tmp_path,
):
    """Test pre-consume ordering and partial-start cleanup."""
    import asyncio
    args, deps, events = _fake_runner_inputs(tmp_path, fail_start=True)
    with pytest.raises(RuntimeError, match='partial startup'):
        asyncio.run(_run(args, dependencies=deps))
    assert events.index('consume') < events.index('process-start')
    assert 'cleanup' in events


def test_pin_mismatch_blocks_before_consume_or_process(tmp_path):
    """Test pin mismatch blocks before consume or process."""
    import asyncio
    args, deps, events = _fake_runner_inputs(tmp_path, mismatch=True)
    with pytest.raises(guard.GuardError):
        asyncio.run(_run(args, dependencies=deps))
    assert 'consume' not in events
    assert 'process-start' not in events


def test_evidence_failure_after_consume_stops_owned_startup(tmp_path):
    """Test evidence failure after consume stops owned startup."""
    import asyncio
    args, deps, events = _fake_runner_inputs(tmp_path, sink_failure=True)
    with pytest.raises(OSError, match='evidence write failure'):
        asyncio.run(_run(args, dependencies=deps))
    assert 'consume' in events
    assert 'process-start' not in events
