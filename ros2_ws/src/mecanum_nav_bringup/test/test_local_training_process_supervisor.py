"""Injected process/readiness tests; no Gazebo or ROS process is spawned."""
import asyncio
import contextlib
import json
import os
import signal
import sys
import threading
from types import SimpleNamespace

from mecanum_nav_bringup.local_training_launch_contract import LaunchPlan
from mecanum_nav_bringup.local_training_process_supervisor import (
    LocalTrainingProcessSupervisor,
    RclpyReadiness,
)
from mecanum_nav_bringup.local_training_readiness_worker import (
    WORLD_IDENTITY_SOURCE,
    scene_facts,
    scene_readiness_matches,
)


class FakeProcess:
    """Fake child process used by supervisor tests."""

    def __init__(self, pid, exit_status=None):
        """Initialize fake process state."""
        self.pid = pid
        self.returncode = exit_status
        self.wait_count = 0

    async def wait(self):
        """Wait until the injected process exits."""
        self.wait_count += 1
        while self.returncode is None:
            await asyncio.sleep(0.001)
        return self.returncode


class FakeLauncher:
    """Record process starts and stops without launching real processes."""

    def __init__(self, fail_on=None):
        """Initialize fake launcher state."""
        self.started = []
        self.stopped = []
        self.fail_on = fail_on
        self.next_pid = 100
        self.controlled_starts = []

    async def start(self, command, environment):
        """Record a launch request or raise at the selected call."""
        if len(self.started) == self.fail_on:
            raise OSError('process start failed')
        p = FakeProcess(self.next_pid)
        self.next_pid += 1
        self.started.append((command, environment, p))
        return p

    async def stop_group(self, process, sig):
        """Record a stop request and mark its owned group as stopped."""
        self.stopped.append((process.pid, sig))
        process.returncode = 0

    def group_alive(self, process):
        """Treat the fake group as alive until its leader is stopped."""
        return process.returncode is None

    async def start_controlled(self, command, environment):
        """Reject child starts unless a test configures a protocol fake."""
        raise AssertionError('controlled observer spawn was not configured')


def _control_frame(message):
    return b'HBTRACE_CONTROL ' + json.dumps(
        message, sort_keys=True, separators=(',', ':'),
    ).encode() + b'\n'


class ControlledObserverProcess:
    """Pipe-compatible child fake; it never imports or starts ROS."""

    def __init__(self, pid, mode='clean'):
        """Create a fake child and its private protocol pipes."""
        self.pid = pid
        self.returncode = None
        self.mode = mode
        self.stdout = asyncio.StreamReader()
        self.stderr = asyncio.StreamReader()
        self._exit = asyncio.Event()
        self.stdin = self._Stdin(self)

    class _Stdin:
        def __init__(self, process):
            """Bind the writer to its simulated child."""
            self.process = process
            self.closed = False

        def write(self, raw):
            message = json.loads(raw)
            if message['kind'] == 'bind':
                response = {
                    'kind': 'bound', 'nonce': message['nonce'],
                    'accepted': True, 'snapshot': {'ready': True},
                }
                self.process.stdout.feed_data(_control_frame(response))
            elif message['kind'] == 'stop':
                joined = self.process.mode in {
                    'clean', 'end-fail', 'clean-nonzero-exit',
                }
                end_written = joined and self.process.mode != 'end-fail'
                handle_closed = joined
                writer_closed = end_written and handle_closed
                response = {
                    'kind': 'stopped', 'nonce': message['nonce'],
                    'joined': joined, 'end_written': end_written,
                    'handle_closed': handle_closed,
                    'writer_closed': writer_closed,
                    'snapshot': {
                        'ready': True, 'joined': joined,
                        'end_written': end_written,
                        'handle_closed': handle_closed,
                        'writer_closed': writer_closed, 'errors': (),
                    },
                }
                self.process.stdout.feed_data(_control_frame(response))
                if joined:
                    status = (
                        9 if self.process.mode == 'clean-nonzero-exit'
                        else 0 if writer_closed else 4
                    )
                    self.process.finish(status)

        async def drain(self):
            return None

        def close(self):
            self.closed = True

        async def wait_closed(self):
            return None

    async def wait(self):
        """Wait for the fake child to publish its exit status."""
        await self._exit.wait()
        return self.returncode

    def finish(self, status):
        """Close both output streams after assigning one exit status."""
        if self.returncode is None:
            self.returncode = status
            self._exit.set()
            self.stdout.feed_eof()
            self.stderr.feed_eof()


class ControlledObserverLauncher(FakeLauncher):
    """Supply an in-memory protocol child to the production supervisor path."""

    def __init__(self, mode='clean'):
        """Configure cooperative, stubborn, or TERM-responsive behavior."""
        super().__init__()
        self.mode = mode
        self.signals = []
        self.child = None

    async def start_controlled(self, command, environment):
        """Return a fake process with production-shaped handshake frames."""
        import importlib.util
        import pathlib

        self.controlled_starts.append((command, environment))
        self.child = ControlledObserverProcess(self.next_pid, self.mode)
        self.next_pid += 1
        spec = importlib.util.find_spec(
            'mecanum_nav_bringup.local_training_heartbeat_trace_observer',
        )
        hello = {
            'kind': 'hello',
            'nonce': environment['MECANUM_B2_HEARTBEAT_WORKER_NONCE'],
            'module_path': str(pathlib.Path(spec.origin).resolve()),
            'executable': str(pathlib.Path(sys.executable).resolve()),
            'prefix': str(pathlib.Path(sys.prefix).resolve()),
        }
        started = {
            'kind': 'started',
            'nonce': environment['MECANUM_B2_HEARTBEAT_WORKER_NONCE'],
            'started': True,
            'snapshot': {'ready': True, 'errors': ()},
            'clock_domain_certificate': None,
        }
        self.child.stdout.feed_data(
            _control_frame(hello) + _control_frame(started),
        )
        return self.child

    async def stop_group(self, process, sig):
        """Record the signal and apply the configured fake process response."""
        self.signals.append((process.pid, sig))
        if sig == signal.SIGTERM and process.mode == 'term-exits':
            process.finish(-signal.SIGTERM)
        elif sig == signal.SIGKILL:
            process.finish(-signal.SIGKILL)

    def group_alive(self, process):
        """Report whether the fake process group still has its leader."""
        return process.returncode is None


class FakeReadiness:
    """Record readiness checks and return an injected owner acknowledgment."""

    def __init__(self, ack=(True, 'screenshot://scene'), failure=None):
        """Initialize fake readiness responses."""
        self.ack = ack
        self.failure = failure
        self.calls = []
        self.accepted_backend_status = {
            'world_id': 'b2_training_arena', 'session_id': 'run-1',
            'config_hash': 'a' * 64, 'backend_instance_id': 42,
            'status_sequence': 1, 'fault_flags': 0,
            'actuator_inhibited': True,
        }

    async def server_scene(self, plan, process, timeout_s):
        """Record the server scene check."""
        self.calls.append(('server', timeout_s))

    async def gui_process_started(self, plan, process, timeout_s):
        """Record the GUI rendering check."""
        self.calls.append(('gui', timeout_s))

    async def owner_ack(self, timeout_s):
        """Return the injected human confirmation."""
        self.calls.append(('ack', timeout_s))
        return self.ack


class FakeSink:
    """Capture evidence events in memory."""

    def __init__(self):
        """Initialize the event list."""
        self.events = []

    def record(self, event, facts):
        """Append an event and its facts."""
        self.events.append((event, facts))


def plan(gui):
    """Build an isolated launch plan for the fake supervisor."""
    commands = (
        ('gz', 'sim', '--force-version', '8', '-s',
         '--headless-rendering', '/tmp/world.sdf'),
    )
    if gui:
        commands += (
            ('gz', 'sim', '--force-version', '8', '-g', '--gui-config',
             '/tmp/gui.config'),
        )
    return LaunchPlan(
        gui, __import__('pathlib').Path('/tmp/world.sdf'),
        __import__('pathlib').Path('/tmp/gui.config'),
        __import__('pathlib').Path('/tmp/config.json'), 'run-1',
        'a' * 64, 'b' * 64, 17, commands,
        {
            'GZ_PARTITION': 'partition',
            'ROS_DOMAIN_ID': '83',
            'GZ_SIM_RESOURCE_PATH': '/tmp/resources',
            'GZ_SIM_SYSTEM_PLUGIN_PATH': '/tmp/plugins',
            'GZ_SIM_PHYSICS_ENGINE_PATH': '/tmp/physics-plugins',
        },
    )


def test_server_only_starts_one_process_and_needs_no_gui_ack():
    """Server-only launch starts one process and skips GUI acknowledgment."""
    async def run():
        launcher = FakeLauncher()
        readiness = FakeReadiness()
        sink = FakeSink()
        supervisor = LocalTrainingProcessSupervisor(
            plan=plan(False), launcher=launcher, readiness=readiness,
            evidence_sink=sink,
        )
        await supervisor.start()
        assert len(launcher.started) == 1
        assert [item[0] for item in readiness.calls] == ['server']
        assert supervisor.owned[0].name == 'server'
    asyncio.run(run())


def test_heartbeat_diagnostics_default_off_creates_no_trace_resources():
    """Keep trace imports, files and observer creation disabled by default."""
    async def run():
        launcher = FakeLauncher()
        sink = FakeSink()
        calls = []

        def observer_factory(**_kwargs):
            calls.append('factory')
            raise AssertionError('diagnostic observer must remain lazy')

        supervisor = LocalTrainingProcessSupervisor(
            plan=plan(False), launcher=launcher, readiness=FakeReadiness(),
            evidence_sink=sink, heartbeat_observer_factory=observer_factory,
            heartbeat_library_path='/path/that/must/not/load.so',
        )
        await supervisor.start()
        assert calls == []
        assert launcher.controlled_starts == []
        assert all(env.get('MECANUM_B2_HEARTBEAT_DIAGNOSTICS') == '0'
                   for command, env, _ in launcher.started
                   if command == plan(False).commands[0])
        assert not any(event == 'heartbeat_trace_collection'
                       for event, _ in sink.events)
        assert supervisor._heartbeat_files == ()
    asyncio.run(run())


def test_inherited_backend_writer_flag_is_forced_off_for_default_server():
    """A parent-shell opt-in cannot turn on the backend writer by accident."""
    import os
    old = os.environ.get('MECANUM_B2_HEARTBEAT_DIAGNOSTICS')
    os.environ['MECANUM_B2_HEARTBEAT_DIAGNOSTICS'] = '1'
    try:
        async def run():
            launcher = FakeLauncher()
            supervisor = LocalTrainingProcessSupervisor(
                plan=plan(False), launcher=launcher,
                readiness=FakeReadiness(), evidence_sink=FakeSink(),
            )
            await supervisor.start()
            server_env = next(
                env for command, env, _ in launcher.started
                if command == plan(False).commands[0]
            )
            assert server_env['MECANUM_B2_HEARTBEAT_DIAGNOSTICS'] == '0'
            assert 'MECANUM_B2_HEARTBEAT_BACKEND_FILE' not in server_env
        asyncio.run(run())
    finally:
        if old is None:
            os.environ.pop('MECANUM_B2_HEARTBEAT_DIAGNOSTICS', None)
        else:
            os.environ['MECANUM_B2_HEARTBEAT_DIAGNOSTICS'] = old


def test_heartbeat_diagnostics_opt_in_is_supervisor_owned_and_joined(tmp_path):
    """Let the supervisor own and join opt-in diagnostic resources."""
    import os

    class FakeObserver:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.stopped = False

        def start(self):
            return True

        def bind_readiness_backend(self, status):
            self.readiness_status = status
            return True

        def stop(self, _timeout):
            self.stopped = True
            return True

        def snapshot(self):
            return {
                'ready': True, 'joined': self.stopped, 'thread_alive': False,
                'end_written': self.stopped,
                'handle_closed': self.stopped,
                'writer_closed': self.stopped, 'errors': (),
            }

    async def run():
        os.chmod(tmp_path, 0o700)
        library = tmp_path / 'writer.so'
        library.write_bytes(b'fake-test-library-path')
        holder = {}

        def observer_factory(**kwargs):
            holder['observer'] = FakeObserver(**kwargs)
            return holder['observer']

        launcher = FakeLauncher()
        sink = FakeSink()
        supervisor = LocalTrainingProcessSupervisor(
            plan=plan(False), launcher=launcher, readiness=FakeReadiness(),
            evidence_sink=sink, heartbeat_diagnostics_enabled=True,
            heartbeat_trace_directory=tmp_path,
            heartbeat_observer_factory=observer_factory,
            heartbeat_library_path=library,
        )
        await supervisor.start()
        server_env = launcher.started[0][1]
        assert server_env['MECANUM_B2_HEARTBEAT_DIAGNOSTICS'] == '1'
        assert server_env['MECANUM_B2_HEARTBEAT_SESSION_ID'] == 'run-1'
        assert len(supervisor._heartbeat_files) == 2
        await supervisor.cleanup()
        assert holder['observer'].stopped
        event = dict(sink.events)['heartbeat_trace_collection']
        assert event['observer']['joined'] is True
        assert len(event['files']) == 2
        assert event['readiness_backend_status']['backend_instance_id'] == 42
    asyncio.run(run())


def test_observer_initialization_failure_keeps_collection_unready(tmp_path):
    """A failed optional observer never enables backend trace writes."""
    class FailedObserver:
        def __init__(self, **_kwargs):
            pass

        def start(self):
            return False

        def snapshot(self):
            return {'ready': False, 'joined': True, 'errors': ('init',)}

        def stop(self, _timeout):
            return True

    async def run():
        os.chmod(tmp_path, 0o700)
        library = tmp_path / 'writer.so'
        library.write_bytes(b'fake-test-library-path')
        launcher = FakeLauncher()
        sink = FakeSink()
        supervisor = LocalTrainingProcessSupervisor(
            plan=plan(False), launcher=launcher,
            readiness=FakeReadiness(), evidence_sink=sink,
            heartbeat_diagnostics_enabled=True,
            heartbeat_trace_directory=tmp_path,
            heartbeat_observer_factory=FailedObserver,
            heartbeat_library_path=library,
        )
        await supervisor.start()
        server_env = launcher.started[0][1]
        assert server_env['MECANUM_B2_HEARTBEAT_DIAGNOSTICS'] == '0'
        assert (
            'observer_initialization_failed'
            in supervisor._heartbeat_trace_error
        )
        await supervisor.cleanup()
        event = dict(sink.events)['heartbeat_trace_collection']
        assert event['trace_error']
        assert event['observer']['ready'] is False
    asyncio.run(run())


def test_nonjoined_observer_residue_is_reported_by_supervisor(tmp_path):
    """Keep a live observer thread unknown instead of claiming a join."""
    import os

    class NonresponsiveObserver:
        def __init__(self, **_kwargs):
            pass

        def start(self):
            return True

        def bind_readiness_backend(self, _status):
            return True

        async def stop_async(self, _timeout):
            return False

        def snapshot(self):
            return {
                'ready': True, 'joined': False, 'thread_alive': True,
                'writer_closed': False, 'errors': (
                    'observer_thread_residue_unknown',
                ),
            }

    async def run():
        os.chmod(tmp_path, 0o700)
        library = tmp_path / 'writer.so'
        library.write_bytes(b'fake-test-library-path')
        sink = FakeSink()
        supervisor = LocalTrainingProcessSupervisor(
            plan=plan(False), launcher=FakeLauncher(),
            readiness=FakeReadiness(), evidence_sink=sink,
            heartbeat_diagnostics_enabled=True,
            heartbeat_trace_directory=tmp_path,
            heartbeat_observer_factory=NonresponsiveObserver,
            heartbeat_library_path=library,
        )
        await supervisor.start()
        await supervisor.cleanup()
        event = dict(sink.events)['heartbeat_trace_collection']
        assert event['observer']['thread_alive'] is True
        assert event['observer']['joined'] is False
        assert event['observer']['writer_closed'] is False
        assert 'observer_thread_residue_unknown' in (
            event['observer']['errors']
        )

    asyncio.run(run())


def _fake_process_identity(pid, *, start_ticks=456):
    return {
        'pid': pid, 'process_group_id': pid, 'session_id': pid,
        'start_ticks': start_ticks,
    }


def _controlled_supervisor(tmp_path, launcher, identity_reader):
    os.chmod(tmp_path, 0o700)
    library = tmp_path / 'writer.so'
    library.write_bytes(b'fake-test-library-path')
    sink = FakeSink()
    supervisor = LocalTrainingProcessSupervisor(
        plan=plan(False), launcher=launcher, readiness=FakeReadiness(),
        evidence_sink=sink, heartbeat_diagnostics_enabled=True,
        heartbeat_trace_directory=tmp_path,
        heartbeat_library_path=library,
        heartbeat_identity_reader=identity_reader,
    )
    return supervisor, sink


async def _start_fake_observer(supervisor):
    await supervisor._prepare_heartbeat_diagnostics()
    await supervisor._bind_heartbeat_readiness()


def test_isolated_observer_clean_exit_uses_process_join_evidence(tmp_path):
    """The default path starts and joins a separate protocol child."""
    async def run():
        launcher = ControlledObserverLauncher('clean')
        identities = {}

        def read_identity(pid):
            return identities.setdefault(pid, _fake_process_identity(pid))

        supervisor, sink = _controlled_supervisor(
            tmp_path, launcher, read_identity,
        )
        await _start_fake_observer(supervisor)
        assert len(launcher.controlled_starts) == 1
        command, environment = launcher.controlled_starts[0]
        assert command == (
            sys.executable,
            '-m',
            'mecanum_nav_bringup.local_training_heartbeat_trace_observer',
            '--worker',
        )
        assert environment['ROS_DOMAIN_ID'] == '83'
        await supervisor._stop_heartbeat_diagnostics()
        event = dict(sink.events)['heartbeat_trace_collection']
        join = event['join_evidence']
        assert join['observer_process_joined'] is True
        assert join['observer_process_group_absent'] is True
        assert join['observer_stop_acknowledged'] is True
        assert join['observer_end_written'] is True
        assert join['observer_handle_closed'] is True
        assert join['observer_writer_closed'] is True
        assert 'observer_thread_joined' not in join
        assert join['observer_termination'] == 'CLEAN_COOPERATIVE'
    asyncio.run(run())


def test_isolated_observer_ignoring_term_escalates_and_is_not_clean(tmp_path):
    """TERM-resistant child is killed and cannot claim a clean close."""
    async def run():
        launcher = ControlledObserverLauncher('hang')
        supervisor, sink = _controlled_supervisor(
            tmp_path, launcher,
            lambda pid: _fake_process_identity(pid),
        )
        supervisor.HEARTBEAT_OBSERVER_CLEANUP_CAP_S = 1.0
        await _start_fake_observer(supervisor)
        await supervisor._stop_heartbeat_diagnostics()
        assert [sig for _, sig in launcher.signals] == [
            signal.SIGTERM, signal.SIGKILL,
        ]
        join = dict(sink.events)['heartbeat_trace_collection']['join_evidence']
        assert join['observer_process_joined'] is True
        assert join['observer_exit_status'] == -signal.SIGKILL
        assert join['observer_writer_closed'] is False
        assert join['observer_end_written'] is False
        assert join['observer_handle_closed'] is False
        assert join['observer_stop_acknowledged'] is False
        assert join['observer_termination'] == 'SIGKILL'
    asyncio.run(run())


def test_failed_end_marker_cannot_be_acknowledged_as_clean_close(tmp_path):
    """A closed handle without a committed END remains incomplete."""
    async def run():
        launcher = ControlledObserverLauncher('end-fail')
        supervisor, sink = _controlled_supervisor(
            tmp_path, launcher, lambda pid: _fake_process_identity(pid),
        )
        await _start_fake_observer(supervisor)
        await supervisor._stop_heartbeat_diagnostics()
        event = dict(sink.events)['heartbeat_trace_collection']
        join = event['join_evidence']
        assert join['observer_process_joined'] is True
        assert join['observer_exit_status'] == 4
        assert join['observer_stop_acknowledged'] is False
        assert join['observer_end_written'] is False
        assert join['observer_handle_closed'] is True
        assert join['observer_writer_closed'] is False
        assert join['observer_termination'] == 'UNCONFIRMED_EXIT'
        assert supervisor._heartbeat_trace_error is not None
    asyncio.run(run())


def test_clean_ack_with_nonzero_exit_is_not_clean_cooperative(tmp_path):
    """A valid stop ACK cannot override an abnormal child exit status."""
    async def run():
        launcher = ControlledObserverLauncher('clean-nonzero-exit')
        supervisor, sink = _controlled_supervisor(
            tmp_path, launcher, lambda pid: _fake_process_identity(pid),
        )
        await _start_fake_observer(supervisor)
        await supervisor._stop_heartbeat_diagnostics()
        event = dict(sink.events)['heartbeat_trace_collection']
        join = event['join_evidence']
        assert join['observer_process_joined'] is True
        assert join['observer_process_group_absent'] is True
        assert join['observer_stop_acknowledged'] is True
        assert join['observer_end_written'] is True
        assert join['observer_handle_closed'] is True
        assert join['observer_writer_closed'] is True
        assert join['observer_exit_status'] == 9
        assert join['observer_termination'] == 'UNCONFIRMED_EXIT'
        assert 'observer_stop_ack_exit_status_nonzero' in (
            event['observer']['errors']
        )
        assert supervisor._heartbeat_trace_error == (
            'observer_stop_ack_exit_status_nonzero'
        )
    asyncio.run(run())


def test_observer_identity_change_blocks_signal_and_reports_residue(tmp_path):
    """A changed process-start identity is never signalled."""
    async def run():
        launcher = ControlledObserverLauncher('hang')
        calls = 0

        def read_identity(pid):
            nonlocal calls
            calls += 1
            return _fake_process_identity(
                pid, start_ticks=456 if calls <= 2 else 999,
            )

        supervisor, sink = _controlled_supervisor(
            tmp_path, launcher, read_identity,
        )
        supervisor.HEARTBEAT_OBSERVER_CLEANUP_CAP_S = 0.12
        await _start_fake_observer(supervisor)
        await supervisor._stop_heartbeat_diagnostics()
        assert launcher.signals == []
        assert supervisor._process_residue == 'UNKNOWN'
        join = dict(sink.events)['heartbeat_trace_collection']['join_evidence']
        assert join['observer_process_joined'] is False
        assert join['observer_termination'] == 'UNKNOWN'
    asyncio.run(run())


def test_reaped_observer_group_wait_obeys_deadline(tmp_path):
    """A reaped leader cannot make the remaining group wait spin forever."""
    async def run():
        launcher = ControlledObserverLauncher('clean')
        launcher.group_alive = lambda _process: True
        supervisor, sink = _controlled_supervisor(
            tmp_path, launcher, lambda pid: _fake_process_identity(pid),
        )
        supervisor.HEARTBEAT_OBSERVER_CLEANUP_CAP_S = 0.06
        await _start_fake_observer(supervisor)
        await asyncio.wait_for(
            supervisor._stop_heartbeat_diagnostics(), timeout=0.3,
        )
        assert launcher.child.returncode == 0
        assert launcher.signals == []
        assert supervisor._process_residue == 'UNKNOWN'
        join = dict(sink.events)['heartbeat_trace_collection']['join_evidence']
        assert join['observer_process_joined'] is True
        assert join['observer_process_group_absent'] is False
        assert join['observer_termination'] == 'UNKNOWN'
    asyncio.run(run())


def test_spawn_timeout_cancels_launcher_before_cleanup_summary(tmp_path):
    """A canceled spawn cannot create a child after cleanup has returned."""
    async def run():
        gate = asyncio.Event()

        class DelayedLauncher(ControlledObserverLauncher):
            async def start_controlled(self, command, environment):
                await gate.wait()
                return await super().start_controlled(command, environment)

        launcher = DelayedLauncher('hang')
        supervisor, sink = _controlled_supervisor(
            tmp_path, launcher,
            lambda pid: _fake_process_identity(pid),
        )
        supervisor.HEARTBEAT_OBSERVER_START_CAP_S = 0.01
        supervisor.HEARTBEAT_OBSERVER_CLEANUP_CAP_S = 0.5
        await supervisor._prepare_heartbeat_diagnostics()
        assert supervisor._heartbeat_trace_error is not None
        assert supervisor._heartbeat_observer_spawn_task.cancelled()
        await supervisor._stop_heartbeat_diagnostics()
        assert dict(sink.events)['heartbeat_trace_collection'][
            'join_evidence'
        ]['task_residue'] == 'UNKNOWN'
        gate.set()
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        assert launcher.child is None
    asyncio.run(run())


def test_spawn_cancellation_prevents_child_after_cleanup_summary(tmp_path):
    """Cancellation completes before cleanup and leaves no future spawn."""
    async def run():
        gate = asyncio.Event()

        class DelayedLauncher(ControlledObserverLauncher):
            async def start_controlled(self, command, environment):
                await gate.wait()
                return await super().start_controlled(command, environment)

        launcher = DelayedLauncher('hang')
        supervisor, _sink = _controlled_supervisor(
            tmp_path, launcher,
            lambda pid: _fake_process_identity(pid),
        )
        supervisor.HEARTBEAT_OBSERVER_START_CAP_S = 2.0
        supervisor.HEARTBEAT_OBSERVER_CLEANUP_CAP_S = 0.5
        prepare = asyncio.create_task(
            supervisor._prepare_heartbeat_diagnostics(),
        )
        await asyncio.sleep(0)
        prepare.cancel()
        try:
            await prepare
        except asyncio.CancelledError:
            pass
        else:
            raise AssertionError('observer startup cancellation was swallowed')
        assert supervisor._heartbeat_observer_spawn_task.cancelled()
        await supervisor._stop_heartbeat_diagnostics()
        gate.set()
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        assert launcher.child is None
    asyncio.run(run())


def test_spawn_timeout_reaps_process_returned_after_cancel_request(tmp_path):
    """A nonconforming delayed launcher still yields its handle to cleanup."""
    async def run():
        gate = asyncio.Event()
        started = asyncio.Event()

        class DelayedLauncher(ControlledObserverLauncher):
            async def start_controlled(self, command, environment):
                started.set()
                try:
                    await gate.wait()
                except asyncio.CancelledError:
                    await gate.wait()
                return await super().start_controlled(command, environment)

        launcher = DelayedLauncher('hang')
        supervisor, sink = _controlled_supervisor(
            tmp_path, launcher, lambda pid: _fake_process_identity(pid),
        )
        supervisor.HEARTBEAT_OBSERVER_START_CAP_S = 0.01
        supervisor.HEARTBEAT_OBSERVER_CLEANUP_CAP_S = 0.5
        prepare = asyncio.create_task(
            supervisor._prepare_heartbeat_diagnostics(),
        )
        await started.wait()
        await asyncio.sleep(0.02)
        assert not prepare.done()
        gate.set()
        await prepare
        assert supervisor._heartbeat_trace_error is not None
        assert supervisor._heartbeat_observer_process is launcher.child
        await supervisor._stop_heartbeat_diagnostics()
        assert supervisor._heartbeat_observer_wait_task is not None
        assert supervisor._heartbeat_observer_wait_task.done()
        assert launcher.child.returncode == -signal.SIGKILL
        event = dict(sink.events)['heartbeat_trace_collection']
        assert event['join_evidence']['observer_process_joined'] is True
        assert event['join_evidence']['observer_writer_closed'] is False
        assert event['trace_error'] is not None
    asyncio.run(run())


def test_heartbeat_diagnostic_cleanup_does_not_mask_start_failure(tmp_path):
    """Preserve startup failure if diagnostic cleanup also fails."""
    import os

    class FakeObserver:
        def __init__(self, **_kwargs):
            self.stopped = False

        def start(self):
            return True

        def stop(self, _timeout):
            self.stopped = True
            return True

        def snapshot(self):
            return {'joined': self.stopped, 'errors': ('injected',)}

    class FailedReadiness(FakeReadiness):
        async def server_scene(self, *_args):
            raise RuntimeError('original readiness failure')

    async def run():
        os.chmod(tmp_path, 0o700)
        library = tmp_path / 'writer.so'
        library.write_bytes(b'fake-test-library-path')
        sink = FakeSink()
        supervisor = LocalTrainingProcessSupervisor(
            plan=plan(False), launcher=FakeLauncher(),
            readiness=FailedReadiness(), evidence_sink=sink,
            heartbeat_diagnostics_enabled=True,
            heartbeat_trace_directory=tmp_path,
            heartbeat_observer_factory=FakeObserver,
            heartbeat_library_path=library,
        )
        try:
            await supervisor.start()
        except RuntimeError as error:
            assert str(error) == 'original readiness failure'
        else:
            raise AssertionError('readiness failure was not preserved')
        assert dict(sink.events)['heartbeat_trace_collection']['observer'][
            'errors'
        ] == ('injected',)
    asyncio.run(run())


def test_gui_mode_uses_same_partition_and_requires_owner_confirmation():
    """GUI launch shares its partition and requires owner confirmation."""
    async def run():
        launcher = FakeLauncher()
        readiness = FakeReadiness()
        sink = FakeSink()
        supervisor = LocalTrainingProcessSupervisor(
            plan=plan(True), launcher=launcher, readiness=readiness,
            evidence_sink=sink,
        )
        await supervisor.start()
        assert len(launcher.started) == 2
        server_environment = launcher.started[0][1]
        gui_environment = launcher.started[1][1]
        assert server_environment['MECANUM_B2_HEARTBEAT_DIAGNOSTICS'] == '0'
        assert gui_environment == plan(True).environment
        assert (
            server_environment['GZ_PARTITION']
            == gui_environment['GZ_PARTITION']
        )
        assert [call[0] for call in readiness.calls] == [
            'server', 'gui', 'ack',
        ]
        event = dict(sink.events)['gui_scene_owner_confirmed']
        assert event['confirmation_source'] == 'human_owner'
        assert event['screenshot_ref'] == 'screenshot://scene'
        assert event['environment']['GZ_PARTITION'] == 'partition'
    asyncio.run(run())


def test_bridge_server_gui_and_scene_query_share_run_environment():
    """Every Gazebo participant receives the immutable plan environment."""
    async def run():
        base_plan = plan(True)
        bridge = (
            'ros2', 'run', 'ros_gz_bridge', 'parameter_bridge',
            '--ros-args', '-p', 'config_file:=/tmp/bridge.yaml',
        )
        values = vars(base_plan).copy()
        values['bridge_command'] = bridge
        bound_plan = SimpleNamespace(**values)
        launcher = FakeLauncher()
        supervisor = LocalTrainingProcessSupervisor(
            plan=bound_plan, launcher=launcher, readiness=FakeReadiness(),
            evidence_sink=FakeSink(),
        )
        await supervisor.start()
        assert [item[0] for item in launcher.started] == [
            bridge, *base_plan.commands,
        ]
        assert launcher.started[0][1] == base_plan.environment
        server_environment = launcher.started[1][1]
        assert server_environment['MECANUM_B2_HEARTBEAT_DIAGNOSTICS'] == '0'
        assert (
            server_environment['GZ_PARTITION']
            == base_plan.environment['GZ_PARTITION']
        )
        assert launcher.started[2][1] == base_plan.environment
        assert isinstance(base_plan.environment, type(plan(False).environment))
    asyncio.run(run())


def test_readiness_request_uses_plan_binding_without_mutating_parent_env():
    """Worker requests copy the launch binding without editing parent env."""
    values = vars(plan(False)).copy()
    values['session_id'] = 'bc3bffce-eb9e-4b78-b1ac-b8f1de32b692'
    bound_plan = LaunchPlan(**values)
    previous = dict(os.environ)
    readiness = RclpyReadiness()
    request = readiness._make_request(bound_plan, 'a' * 64, 123456789)
    assert request['session_id'] == bound_plan.session_id
    assert request['coordinator_ingress_instance_id'] == 17
    assert request['gz_partition'] == bound_plan.environment['GZ_PARTITION']
    assert request['ros_domain_id'] == bound_plan.environment['ROS_DOMAIN_ID']
    assert dict(os.environ) == previous


def test_gui_start_failure_cleans_server_without_headless_fallback():
    """GUI startup failure stops the server without headless fallback."""
    async def run():
        launcher = FakeLauncher(fail_on=1)
        readiness = FakeReadiness()
        sink = FakeSink()
        supervisor = LocalTrainingProcessSupervisor(
            plan=plan(True), launcher=launcher, readiness=readiness,
            evidence_sink=sink,
        )
        try:
            await supervisor.start()
        except OSError:
            pass
        else:
            raise AssertionError('GUI start failure did not fail launch')
        assert len(launcher.started) == 1
        assert launcher.stopped == [(100, signal.SIGINT)]
        assert not any(
            '-s' in call[0] and 'headless' in call[0]
            for call in launcher.started[1:]
        )
    asyncio.run(run())


def test_missing_owner_ack_fails_and_does_not_open_collection():
    """Missing owner confirmation fails launch and leaves collection closed."""
    async def run():
        launcher = FakeLauncher()
        readiness = FakeReadiness(ack=(False, 'owner_ack_timeout'))
        sink = FakeSink()
        supervisor = LocalTrainingProcessSupervisor(
            plan=plan(True), launcher=launcher, readiness=readiness,
            evidence_sink=sink,
        )
        try:
            await supervisor.start()
        except RuntimeError as error:
            assert 'confirmation' in str(error)
        else:
            raise AssertionError('missing acknowledgment accepted')
        assert len(launcher.stopped) == 2
        assert 'gui_owner_ack_failed' in [
            event for event, _ in sink.events
        ]
    asyncio.run(run())


def test_cleanup_signals_owned_group_after_leader_exit():
    """An exited leader does not hide owned group members from cleanup."""
    async def run():
        launcher = FakeLauncher()
        process = FakeProcess(101, exit_status=0)
        group_members = {101}
        launcher.group_alive = lambda candidate: candidate.pid in group_members

        async def stop_group(candidate, sig):
            launcher.stopped.append((candidate.pid, sig))
            group_members.discard(candidate.pid)
        launcher.stop_group = stop_group
        readiness = FakeReadiness()
        sink = FakeSink()
        supervisor = LocalTrainingProcessSupervisor(
            plan=plan(False), launcher=launcher, readiness=readiness,
            evidence_sink=sink,
        )
        record = type('Record', (), {
            'name': 'server', 'command': ('gz', 'sim'),
            'pid': 101, 'process': process, 'output_tasks': (),
        })()
        supervisor.owned.append(record)
        await supervisor.cleanup()
        assert launcher.stopped == [(101, signal.SIGINT)]
        cleanup_facts = dict(sink.events)['owned_process_cleanup']
        assert cleanup_facts['escalation'] == 'SIGINT'
        assert cleanup_facts['process_joined'] is True
        assert cleanup_facts['group_absent'] is True
        assert cleanup_facts['output_tasks_joined'] is True
        assert cleanup_facts['residue'] == 'NONE'
    asyncio.run(run())


def _cancellation_stubborn_task(release, cancelled):
    async def run():
        try:
            await asyncio.Future()
        except asyncio.CancelledError:
            cancelled.set()
            await release.wait()
    return asyncio.create_task(run())


def test_cleanup_observer_task_cancel_join_is_bounded():
    """A task that suppresses cancellation cannot hold cleanup forever."""
    async def run():
        supervisor = LocalTrainingProcessSupervisor(
            plan=plan(False), launcher=FakeLauncher(),
            readiness=FakeReadiness(), evidence_sink=FakeSink(),
        )
        supervisor.CLEANUP_OBSERVER_TASK_JOIN_CAP_S = 0.02
        release = asyncio.Event()
        cancelled = asyncio.Event()
        task = _cancellation_stubborn_task(release, cancelled)
        supervisor._track_observer(task)
        cleanup = asyncio.create_task(supervisor.cleanup())
        try:
            await asyncio.wait_for(cancelled.wait(), timeout=0.5)
            done, _ = await asyncio.wait({cleanup}, timeout=0.05)
            assert cleanup in done, 'cleanup blocked joining a canceled task'
        finally:
            release.set()
            if not cleanup.done():
                await asyncio.wait_for(cleanup, timeout=1.0)
            else:
                await cleanup
    asyncio.run(run())


def test_cleanup_output_drain_cancel_join_is_bounded():
    """A stalled output task remains residue instead of blocking cleanup."""
    async def run():
        supervisor = LocalTrainingProcessSupervisor(
            plan=plan(False), launcher=FakeLauncher(),
            readiness=FakeReadiness(), evidence_sink=FakeSink(),
        )
        supervisor.CLEANUP_CAP_S = 0.02
        release = asyncio.Event()
        cancelled = asyncio.Event()
        task = _cancellation_stubborn_task(release, cancelled)
        process = FakeProcess(121, exit_status=0)
        supervisor.owned.append(type('Record', (), {
            'name': 'server', 'command': ('gz', 'sim'), 'pid': 121,
            'process': process, 'output_tasks': (task,),
        })())
        cleanup = asyncio.create_task(supervisor.cleanup())
        try:
            done, _ = await asyncio.wait({cleanup}, timeout=0.2)
            assert cleanup in done, 'cleanup exceeded the shared deadline'
            assert await cleanup is False
            await asyncio.wait_for(supervisor._cleanup_task, timeout=1.0)
            assert task in supervisor._cleanup_residue_tasks
            assert supervisor._cleanup_residue == 'UNKNOWN'
        finally:
            release.set()
            if not cleanup.done():
                await asyncio.wait_for(cleanup, timeout=1.0)
            else:
                await cleanup
            if not task.done():
                await asyncio.wait_for(task, timeout=1.0)
    asyncio.run(run())


def test_cleanup_reserves_observer_budget_across_owned_groups():
    """Several groups cannot spend the observer's reserved cleanup budget."""
    class Clock:
        now = 0.0

        async def sleep(self, duration):
            self.now += duration

    async def run():
        clock = Clock()
        launcher = FakeLauncher()
        launcher.group_alive = lambda _process: True

        async def no_op_stop(process, sig):
            launcher.stopped.append((process.pid, sig))
            return None
        launcher.stop_group = no_op_stop
        supervisor = LocalTrainingProcessSupervisor(
            plan=plan(False), launcher=launcher,
            readiness=FakeReadiness(), evidence_sink=FakeSink(),
            monotonic=lambda: clock.now, sleep=clock.sleep,
        )
        supervisor.CLEANUP_CAP_S = 2.0
        supervisor.HEARTBEAT_OBSERVER_CLEANUP_CAP_S = 0.25
        supervisor.heartbeat_diagnostics_enabled = True
        for pid, role in ((131, 'gui'), (132, 'server'),
                          (133, 'parameter_bridge')):
            supervisor.owned.append(type('Record', (), {
                'name': role, 'command': ('child',), 'pid': pid,
                'process': FakeProcess(pid), 'output_tasks': (),
            })())
        observed = []

        async def stop_heartbeat():
            observed.append(clock.now)
        supervisor._stop_heartbeat_diagnostics = stop_heartbeat
        await supervisor.cleanup()
        assert observed and observed[0] <= supervisor.CLEANUP_CAP_S
        assert supervisor._cleanup_residue == 'UNKNOWN'
        assert {pid for pid, _sig in launcher.stopped} == {131, 132, 133}
        original_deadline = supervisor._cleanup_deadline
        clock.now = 10.0
        await supervisor.cleanup()
        assert supervisor._cleanup_deadline == original_deadline
        assert observed == [observed[0]]
    asyncio.run(run())


def test_cleanup_sink_failure_does_not_mask_start_failure_or_skip_groups():
    """A cleanup journal error is secondary to startup failure and rollback."""
    class FailingCleanupSink(FakeSink):
        def record(self, event, facts):
            if event == 'owned_process_cleanup':
                raise OSError('injected cleanup sink failure')
            super().record(event, facts)

    async def run():
        launcher = FakeLauncher(fail_on=2)
        supervisor = LocalTrainingProcessSupervisor(
            plan=_plan_with_bridge(True), launcher=launcher,
            readiness=FakeReadiness(), evidence_sink=FailingCleanupSink(),
        )
        try:
            await supervisor.start()
        except OSError as error:
            assert str(error) == 'process start failed'
        else:
            raise AssertionError('startup failure was not preserved')
        assert launcher.stopped == [
            (101, signal.SIGINT), (100, signal.SIGINT),
        ]
        assert supervisor._cleanup_residue == 'UNKNOWN'
        assert any('cleanup_sink:owned_process_cleanup:OSError' in item
                   for item in supervisor._cleanup_errors)
    asyncio.run(run())


def test_cleanup_identity_unknown_does_not_signal_or_drop_process():
    """An unverified process-group identity remains owned and UNKNOWN."""
    async def run():
        launcher = FakeLauncher()

        def unknown_identity(_process):
            raise ProcessLookupError('identity changed')

        launcher.group_alive = unknown_identity
        supervisor = LocalTrainingProcessSupervisor(
            plan=plan(False), launcher=launcher,
            readiness=FakeReadiness(), evidence_sink=FakeSink(),
        )
        process = FakeProcess(149)
        record = type('Record', (), {
            'name': 'server', 'command': ('gz', 'sim'), 'pid': 149,
            'process': process, 'output_tasks': (),
        })()
        supervisor.owned.append(record)
        assert await supervisor.cleanup() is False
        assert launcher.stopped == []
        assert supervisor.owned == [record]
        assert supervisor._cleanup_residue == 'UNKNOWN'
    asyncio.run(run())


def test_cleanup_concurrent_call_shares_and_shortens_absolute_deadline():
    """A second cleanup caller can shorten but never restart the operation."""
    async def run():
        entered = asyncio.Event()
        release = asyncio.Event()
        launcher = FakeLauncher()

        async def blocked_stop(process, sig):
            launcher.stopped.append((process.pid, sig))
            entered.set()
            await release.wait()

        launcher.stop_group = blocked_stop
        launcher.group_alive = lambda _process: True
        supervisor = LocalTrainingProcessSupervisor(
            plan=plan(False), launcher=launcher,
            readiness=FakeReadiness(), evidence_sink=FakeSink(),
        )
        supervisor.CLEANUP_CAP_S = 5.0
        assert LocalTrainingProcessSupervisor.CLEANUP_CAP_S <= 30.0
        process = FakeProcess(151)
        supervisor.owned.append(type('Record', (), {
            'name': 'server', 'command': ('gz', 'sim'), 'pid': 151,
            'process': process, 'output_tasks': (),
        })())
        first = asyncio.create_task(supervisor.cleanup())
        try:
            await asyncio.wait_for(entered.wait(), timeout=0.5)
            owned_cleanup = supervisor._cleanup_task
            original_deadline = supervisor._cleanup_deadline
            shorter = asyncio.get_running_loop().time() + 0.03
            assert await supervisor.cleanup(deadline=shorter) is False
            assert supervisor._cleanup_task is owned_cleanup
            assert supervisor._cleanup_deadline == shorter
            assert shorter < original_deadline
            assert await asyncio.wait_for(first, timeout=0.5) is False
            assert supervisor._cleanup_residue == 'UNKNOWN'
        finally:
            release.set()
            if not first.done():
                await asyncio.wait_for(first, timeout=1.0)
            if supervisor._cleanup_task is not None:
                with contextlib.suppress(asyncio.CancelledError):
                    await asyncio.wait_for(
                        supervisor._cleanup_task, timeout=1.0,
                    )
    asyncio.run(run())


def test_blocking_cleanup_sink_does_not_block_other_group_cleanup():
    """Cleanup signals every group before bounded off-loop sink publication."""
    class BlockingSink(FakeSink):
        def __init__(self):
            super().__init__()
            self.entered = threading.Event()
            self.release = threading.Event()

        def record(self, event, facts):
            if event.startswith('owned_process_cleanup'):
                self.entered.set()
                self.release.wait()
            super().record(event, facts)

    async def run():
        launcher = FakeLauncher()
        sink = BlockingSink()
        supervisor = LocalTrainingProcessSupervisor(
            plan=plan(False), launcher=launcher,
            readiness=FakeReadiness(), evidence_sink=sink,
        )
        supervisor.CLEANUP_CAP_S = 0.05
        for pid, role in ((161, 'gui'), (162, 'server')):
            supervisor.owned.append(type('Record', (), {
                'name': role, 'command': ('child',), 'pid': pid,
                'process': FakeProcess(pid), 'output_tasks': (),
            })())
        cleanup = asyncio.create_task(supervisor.cleanup())
        try:
            for _ in range(500):
                if sink.entered.is_set():
                    break
                await asyncio.sleep(0.001)
            assert sink.entered.is_set()
            assert await asyncio.wait_for(cleanup, timeout=0.5) is False
            assert {pid for pid, _sig in launcher.stopped} == {161, 162}
            assert supervisor._cleanup_residue == 'UNKNOWN'
            assert supervisor._cleanup_sink_thread is not None
            assert supervisor._cleanup_sink_thread.is_alive()
        finally:
            sink.release.set()
            if supervisor._cleanup_sink_thread is not None:
                supervisor._cleanup_sink_thread.join(timeout=1.0)
                assert not supervisor._cleanup_sink_thread.is_alive()
            if not cleanup.done():
                await asyncio.wait_for(cleanup, timeout=1.0)
    asyncio.run(run())


def test_cleanup_owns_all_processes_for_both_gui_modes():
    """The shared cleanup path closes server-only and GUI launches."""
    async def run():
        for gui in (False, True):
            launcher = FakeLauncher()
            sink = FakeSink()
            supervisor = LocalTrainingProcessSupervisor(
                plan=plan(gui), launcher=launcher,
                readiness=FakeReadiness(), evidence_sink=sink,
            )
            await supervisor.start()
            assert await supervisor.cleanup() is True
            cleanup = [facts for event, facts in sink.events
                       if event == 'owned_process_cleanup']
            expected = {'server', 'gui'} if gui else {'server'}
            assert {facts['process'] for facts in cleanup} == expected
            assert supervisor.owned == []
    asyncio.run(run())


def test_monitor_cancellation_does_not_gather_waiters_without_deadline():
    """Monitor delegates cancellation joins to bounded supervisor cleanup."""
    async def run():
        entered = asyncio.Event()
        release = asyncio.Event()

        class StubbornWaitProcess(FakeProcess):
            def __init__(self, pid):
                super().__init__(pid)
                self.calls = 0

            async def wait(self):
                self.calls += 1
                if self.calls == 1:
                    entered.set()
                    try:
                        await asyncio.Future()
                    except asyncio.CancelledError:
                        await release.wait()
                return self.returncode

        process = StubbornWaitProcess(141)
        launcher = FakeLauncher()
        supervisor = LocalTrainingProcessSupervisor(
            plan=plan(False), launcher=launcher,
            readiness=FakeReadiness(), evidence_sink=FakeSink(),
        )
        record = type('Record', (), {
            'name': 'server', 'command': ('gz', 'sim'), 'pid': 141,
            'process': process, 'output_tasks': (),
        })()
        supervisor.owned.append(record)
        supervisor._server_process_record = record
        monitor = asyncio.create_task(supervisor.monitor())
        try:
            await asyncio.wait_for(entered.wait(), timeout=0.5)
            monitor.cancel()
            done, _ = await asyncio.wait({monitor}, timeout=0.75)
            assert monitor in done, 'monitor waited forever outside cleanup'
            with contextlib.suppress(asyncio.CancelledError):
                await monitor
            assert process.returncode == 0
            assert supervisor.owned == []
        finally:
            release.set()
            if not monitor.done():
                monitor.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await asyncio.wait_for(monitor, timeout=1.0)
    asyncio.run(run())


def test_owner_input_partial_line_is_cancellable_and_resumable():
    """Partial stdin never blocks the loop and cancellation removes reader."""
    read_fd, write_fd = os.pipe()
    original_stdin = sys.stdin
    readiness = RclpyReadiness()

    class PipeInput:
        def fileno(self):
            return read_fd

    async def run():
        sys.stdin = PipeInput()
        try:
            pending = asyncio.create_task(
                readiness._read_stdin_line('ack: '),
            )
            os.write(write_fd, b'OWNER')
            await asyncio.sleep(0.02)
            assert not pending.done()
            pending.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await pending
            os.write(write_fd, b'_ACK_SCENE\n')
            result = await asyncio.wait_for(
                readiness._read_stdin_line('ack: '), timeout=0.5,
            )
            assert result == 'OWNER_ACK_SCENE'
        finally:
            sys.stdin = original_stdin
            os.close(read_fd)
            os.close(write_fd)

    asyncio.run(run())


def test_production_scene_status_requires_fault_free_bound_identity():
    """The callback predicate rejects an unhealthy matching heartbeat."""
    readiness = RclpyReadiness()
    expected_plan = plan(False)
    expected_hash = 'a' * 64
    message = SimpleNamespace(
        header=SimpleNamespace(frame_id='b2_training_arena'),
        session_id=expected_plan.session_id,
        config_hash=expected_hash,
        backend_instance_id=17,
        status_sequence=4,
        fault_flags=0,
        paused=False,
        actuator_inhibited=True,
    )
    matches = readiness._matches_bound_scene_status
    assert matches(message, expected_plan, expected_hash)

    for field, value in (
        ('header', SimpleNamespace(frame_id='wrong_world')),
        ('session_id', 'foreign-session'),
        ('config_hash', 'b' * 64),
        ('backend_instance_id', 0),
        ('status_sequence', 0),
        ('fault_flags', 1),
        ('actuator_inhibited', False),
    ):
        altered = SimpleNamespace(**vars(message))
        setattr(altered, field, value)
        assert not matches(altered, expected_plan, expected_hash)


def test_paused_inhibited_scene_is_ready_for_passive_observation():
    """A healthy paused scene may open the GUI while policy stays inhibited."""
    readiness = RclpyReadiness()
    expected_plan = plan(False)
    expected_hash = 'a' * 64
    message = SimpleNamespace(
        header=SimpleNamespace(frame_id='b2_training_arena'),
        session_id=expected_plan.session_id,
        config_hash=expected_hash,
        backend_instance_id=17,
        status_sequence=4,
        fault_flags=0,
        paused=True,
        actuator_inhibited=True,
    )
    assert readiness._matches_bound_scene_status(
        message, expected_plan, expected_hash,
    )


def test_paused_scene_opens_gui_without_world_control():
    """Paused inhibited readiness starts the requested GUI without control."""
    class PausedReadiness(FakeReadiness):
        async def server_scene(self, bound_plan, process, timeout_s):
            del process, timeout_s
            status = SimpleNamespace(
                header=SimpleNamespace(frame_id='b2_training_arena'),
                session_id=bound_plan.session_id,
                config_hash='a' * 64,
                backend_instance_id=17,
                status_sequence=4,
                fault_flags=0,
                paused=True,
                actuator_inhibited=True,
            )
            assert RclpyReadiness._matches_bound_scene_status(
                status, bound_plan, 'a' * 64,
            )
            self.calls.append(('paused_scene', 30.0))

    async def run():
        launcher = FakeLauncher()
        supervisor = LocalTrainingProcessSupervisor(
            plan=plan(True), launcher=launcher,
            readiness=PausedReadiness(), evidence_sink=FakeSink(),
        )
        await supervisor.start()
        assert [command for command, _, _ in launcher.started] == list(
            plan(True).commands,
        )
        assert len(launcher.started) == 2
    asyncio.run(run())


def test_shared_scene_binding_predicate_uses_service_partition_and_backend():
    """Use bound transport and backend facts instead of Scene.name."""
    expected_plan = plan(False)
    request = {
        'world_id': 'b2_training_arena', 'model_id': 'mecanum_b2',
        'session_id': expected_plan.session_id, 'config_hash': 'a' * 64,
        'gz_partition': 'mecanum_b2_testpartition',
    }
    status = {
        'world_id': request['world_id'],
        'session_id': request['session_id'],
        'config_hash': request['config_hash'], 'backend_instance_id': 17,
        'status_sequence': 4, 'fault_flags': 0,
        'actuator_inhibited': True,
    }
    service = '/world/b2_training_arena/scene/info'
    model = SimpleNamespace(name='mecanum_b2', model=[])
    unnamed = scene_facts(
        SimpleNamespace(name='', model=[model]), service,
        request['gz_partition'], request,
    )
    assert unnamed['scene_name'] == ''
    assert unnamed['world_identity_source'] == WORLD_IDENTITY_SOURCE
    assert scene_readiness_matches(status, unnamed, request)

    labeled = {**unnamed, 'scene_name': 'not-a-world-identity'}
    assert scene_readiness_matches(status, labeled, request)
    assert not scene_readiness_matches(
        {**status, 'world_id': 'other_world'}, unnamed, request,
    )
    assert not scene_readiness_matches(
        {**status, 'session_id': 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'},
        unnamed, request,
    )
    assert not scene_readiness_matches(
        {**status, 'config_hash': 'c' * 64}, unnamed, request,
    )
    assert not scene_readiness_matches(
        status, {**unnamed, 'query_service': '/world/other/scene/info'},
        request,
    )
    assert not scene_readiness_matches(
        status, {**unnamed, 'query_partition': 'foreign-partition'}, request,
    )
    assert not scene_readiness_matches(
        status, scene_facts(None, service, request['gz_partition'], request),
        request,
    )
    assert not scene_readiness_matches(
        status, {**unnamed, 'matching_model_count': 0}, request,
    )
    assert not scene_readiness_matches(
        status, {**unnamed, 'matching_model_count': 2}, request,
    )


def test_gui_exit_cancels_production_owner_ack_wait():
    """A GUI exit bounds the production liveness wait and cancels input."""
    class WaitingReadiness(FakeReadiness):
        def __init__(self):
            super().__init__()
            self.started = asyncio.Event()
            self.cancelled = False

        async def owner_ack(self, timeout_s):
            del timeout_s
            self.started.set()
            try:
                await asyncio.Future()
            except asyncio.CancelledError:
                self.cancelled = True
                raise

    async def run():
        launcher = FakeLauncher()
        readiness = WaitingReadiness()
        sink = FakeSink()
        supervisor = LocalTrainingProcessSupervisor(
            plan=plan(True), launcher=launcher, readiness=readiness,
            evidence_sink=sink,
        )
        process = FakeProcess(102)
        record = type('Record', (), {
            'name': 'gui', 'command': ('gz', 'sim', '-g'),
            'pid': 102, 'process': process, 'output_tasks': (),
        })()
        pending = asyncio.create_task(
            supervisor._owner_ack_with_liveness(record),
        )
        await readiness.started.wait()
        process.returncode = 1
        result = await asyncio.wait_for(pending, timeout=0.5)
        assert result == (False, 'gui_exited_during_owner_confirmation')
        assert readiness.cancelled
        assert 'gui_closed_or_crashed' in [
            event for event, _ in sink.events
        ]
        assert launcher.started == []

    asyncio.run(run())


def _plan_with_bridge(gui):
    """Build the production-shaped participant set with a bridge record."""
    base_plan = plan(gui)
    values = vars(base_plan).copy()
    values['bridge_command'] = (
        'ros2', 'run', 'ros_gz_bridge', 'parameter_bridge',
        '--ros-args', '-p', 'config_file:=/tmp/bridge.yaml',
    )
    return SimpleNamespace(**values)


def test_monitor_reports_server_exit_by_role_when_bridge_is_first():
    """A bridge-first owned list still monitors and reports server exit."""
    async def run():
        launcher = FakeLauncher()
        sink = FakeSink()
        supervisor = LocalTrainingProcessSupervisor(
            plan=_plan_with_bridge(False), launcher=launcher,
            readiness=FakeReadiness(), evidence_sink=sink,
        )
        await supervisor.start()
        assert [record.name for record in supervisor.owned] == [
            'parameter_bridge', 'server',
        ]
        monitor = asyncio.create_task(supervisor.monitor())
        await asyncio.sleep(0)
        server = next(
            record.process for record in supervisor.owned
            if record.name == 'server'
        )
        server.returncode = 7
        assert await asyncio.wait_for(monitor, timeout=0.5) == 7
        cleanup = [facts for event, facts in sink.events
                   if event == 'owned_process_cleanup']
        assert {item['process'] for item in cleanup} == {
            'parameter_bridge', 'server',
        }
    asyncio.run(run())


def test_monitor_fails_when_bridge_exits_while_server_lives():
    """A failed bridge is infrastructure loss, not a server exit."""
    async def run():
        launcher = FakeLauncher()
        supervisor = LocalTrainingProcessSupervisor(
            plan=_plan_with_bridge(False), launcher=launcher,
            readiness=FakeReadiness(), evidence_sink=FakeSink(),
        )
        await supervisor.start()
        bridge = next(r.process for r in supervisor.owned
                      if r.name == 'parameter_bridge')
        monitor = asyncio.create_task(supervisor.monitor())
        await asyncio.sleep(0)
        bridge.returncode = 9
        try:
            await asyncio.wait_for(monitor, timeout=0.5)
        except RuntimeError as error:
            assert 'parameter_bridge' in str(error)
        else:
            raise AssertionError('bridge exit was reported as server exit')
    asyncio.run(run())


def test_monitor_records_gui_exit_by_role_with_bridge_and_server_alive():
    """Closing the GUI is recorded without restarting owned infrastructure."""
    async def run():
        launcher = FakeLauncher()
        sink = FakeSink()
        supervisor = LocalTrainingProcessSupervisor(
            plan=_plan_with_bridge(True), launcher=launcher,
            readiness=FakeReadiness(), evidence_sink=sink,
        )
        await supervisor.start()
        roles = {record.name: record.process for record in supervisor.owned}
        monitor = asyncio.create_task(supervisor.monitor())
        await asyncio.sleep(0)
        roles['gui'].returncode = 4
        for _ in range(50):
            if any(
                event == 'gui_closed_or_crashed' for event, _ in sink.events
            ):
                break
            await asyncio.sleep(0.001)
        gui_events = [facts for name, facts in sink.events
                      if name == 'gui_closed_or_crashed']
        assert len(gui_events) == 1, gui_events
        event = gui_events[0]
        assert event['process'] == 'gui'
        assert event['server_restart'] is False
        assert event['gui_restart'] is False
        assert not monitor.done()
        roles['server'].returncode = 0
        assert await asyncio.wait_for(monitor, timeout=0.5) == 0
        assert [pid for pid, _ in launcher.stopped] == [
            roles['parameter_bridge'].pid,
        ]
        cleanup = [facts for name, facts in sink.events
                   if name == 'owned_process_cleanup']
        assert {facts['process'] for facts in cleanup} == {
            'gui', 'server', 'parameter_bridge',
        }
    asyncio.run(run())


def test_bridge_start_is_rolled_back_when_server_spawn_fails():
    """A bridge child is cleaned if a later server spawn cannot start."""
    async def run():
        launcher = FakeLauncher(fail_on=1)
        sink = FakeSink()
        supervisor = LocalTrainingProcessSupervisor(
            plan=_plan_with_bridge(False), launcher=launcher,
            readiness=FakeReadiness(), evidence_sink=sink,
        )
        try:
            await supervisor.start()
        except OSError:
            pass
        else:
            raise AssertionError('server spawn failure was accepted')
        assert [pid for pid, _ in launcher.stopped] == [100]
        assert supervisor.owned == []
        cleanup = [facts for event, facts in sink.events
                   if event == 'owned_process_cleanup']
        assert [record['process'] for record in cleanup] == [
            'parameter_bridge',
        ]
    asyncio.run(run())


def test_startup_cancellation_rolls_back_registered_children():
    """Cancellation during server readiness cleans bridge and server once."""
    class BlockingReadiness(FakeReadiness):
        def __init__(self):
            super().__init__()
            self.entered = asyncio.Event()

        async def server_scene(self, plan, process, timeout_s):
            del plan, process, timeout_s
            self.entered.set()
            await asyncio.Future()

    async def run():
        launcher = FakeLauncher()
        sink = FakeSink()
        readiness = BlockingReadiness()
        supervisor = LocalTrainingProcessSupervisor(
            plan=_plan_with_bridge(False), launcher=launcher,
            readiness=readiness, evidence_sink=sink,
        )
        startup = asyncio.create_task(supervisor.start())
        await readiness.entered.wait()
        startup.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await startup
        assert [pid for pid, _ in launcher.stopped] == [101, 100]
        assert supervisor.owned == []
        await supervisor.cleanup()
        assert [pid for pid, _ in launcher.stopped] == [101, 100]
    asyncio.run(run())
