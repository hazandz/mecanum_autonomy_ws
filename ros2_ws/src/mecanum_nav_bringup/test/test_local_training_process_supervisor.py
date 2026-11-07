"""Injected process/readiness tests; no Gazebo or ROS process is spawned."""
import asyncio
import contextlib
import json
import os
import signal
import sys
from types import SimpleNamespace

from mecanum_nav_bringup.local_training_launch_contract import LaunchPlan
from mecanum_nav_bringup.local_training_process_supervisor import (
    CleanupEvidenceAck,
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
                    'clean', 'end-fail', 'clean-nonzero-exit', 'ack-hang',
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
                if joined and self.process.mode != 'ack-hang':
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
            process.finish(
                0 if process.mode == 'ack-hang' else -signal.SIGKILL,
            )

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


def _thaw_cleanup_value(value):
    if (isinstance(value, tuple) and all(
            isinstance(item, tuple) and len(item) == 2
            and isinstance(item[0], str) for item in value)):
        return {key: _thaw_cleanup_value(item) for key, item in value}
    if isinstance(value, tuple):
        return [_thaw_cleanup_value(item) for item in value]
    return value


class FakeCleanupPublisher:
    """Test-only async publisher requiring a batch-bound explicit ACK."""

    def __init__(self, sink=None, *, behavior='ack', gate=None):
        """Configure a deterministic publisher response for cleanup tests."""
        self.sink = sink
        self.behavior = behavior
        self.gate = gate
        self.calls = []

    async def __call__(self, batch, deadline):
        """Capture the batch and return or await the selected result."""
        self.calls.append((batch, deadline))
        if self.behavior == 'raise':
            raise OSError('injected publisher failure')
        if self.behavior == 'hold':
            await self.gate.wait()
        if self.behavior == 'false_ack':
            return CleanupEvidenceAck(batch.batch_id, False)
        if self.behavior == 'wrong_ack':
            return CleanupEvidenceAck('different-batch', True)
        if self.sink is not None:
            for event, frozen_facts in batch.events:
                self.sink.record(event, _thaw_cleanup_value(frozen_facts))
        return CleanupEvidenceAck(batch.batch_id, True)


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
            cleanup_evidence_publisher=FakeCleanupPublisher(sink),
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
            cleanup_evidence_publisher=FakeCleanupPublisher(sink),
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
            cleanup_evidence_publisher=FakeCleanupPublisher(sink),
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
            cleanup_evidence_publisher=FakeCleanupPublisher(sink),
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
        assert join['observer_termination'] == 'UNCONFIRMED_EXIT'
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
            cleanup_evidence_publisher=FakeCleanupPublisher(sink),
        )
        try:
            await supervisor.start()
        except RuntimeError as error:
            assert str(error) == 'original readiness failure'
        else:
            raise AssertionError('readiness failure was not preserved')
        assert dict(sink.events)['heartbeat_trace_collection']['observer'][
            'errors'
        ] == ['injected']
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
            cleanup_evidence_publisher=FakeCleanupPublisher(sink),
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
    async def run():
        launcher = FakeLauncher()
        launcher.group_alive = lambda _process: True

        async def no_op_stop(process, sig):
            launcher.stopped.append((process.pid, sig))
            return None
        launcher.stop_group = no_op_stop
        supervisor = LocalTrainingProcessSupervisor(
            plan=plan(False), launcher=launcher,
            readiness=FakeReadiness(), evidence_sink=FakeSink(),
            cleanup_evidence_publisher=FakeCleanupPublisher(),
        )
        supervisor.CLEANUP_CAP_S = 0.3
        supervisor.HEARTBEAT_OBSERVER_CLEANUP_CAP_S = 0.1
        supervisor.heartbeat_diagnostics_enabled = True
        for pid, role in ((131, 'gui'), (132, 'server'),
                          (133, 'parameter_bridge')):
            supervisor.owned.append(type('Record', (), {
                'name': role, 'command': ('child',), 'pid': pid,
                'process': FakeProcess(pid), 'output_tasks': (),
            })())
        observed = []

        async def stop_heartbeat():
            observed.append(asyncio.get_running_loop().time())
        supervisor._stop_heartbeat_diagnostics = stop_heartbeat
        await supervisor.cleanup()
        assert observed
        assert observed[0] <= supervisor._cleanup_deadline
        assert supervisor._cleanup_residue == 'UNKNOWN'
        assert {pid for pid, _sig in launcher.stopped} == {131, 132, 133}
        original_deadline = supervisor._cleanup_deadline
        await supervisor.cleanup()
        assert supervisor._cleanup_deadline == original_deadline
        assert observed == [observed[0]]
    asyncio.run(run())


def test_legacy_sink_is_not_called_during_cleanup_and_primary_is_preserved():
    """Missing async publisher fails closed without blocking rollback."""
    class FailingCleanupSink(FakeSink):
        def __init__(self):
            super().__init__()
            self.cleanup_calls = 0

        def record(self, event, facts):
            if event == 'owned_process_cleanup':
                self.cleanup_calls += 1
                raise OSError('injected cleanup sink failure')
            super().record(event, facts)

    async def run():
        launcher = FakeLauncher(fail_on=2)
        sink = FailingCleanupSink()
        supervisor = LocalTrainingProcessSupervisor(
            plan=_plan_with_bridge(True), launcher=launcher,
            readiness=FakeReadiness(), evidence_sink=sink,
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
        assert sink.cleanup_calls == 0
        assert 'cleanup_evidence_publisher_unavailable' in (
            supervisor._cleanup_errors
        )
        assert supervisor.cleanup_snapshot()['primary_failure']['message'] == (
            'process start failed'
        )
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


def test_cleanup_never_calls_legacy_sync_sink_and_stops_all_groups():
    """A blocking legacy sink is excluded from the cleanup critical path."""
    async def run():
        launcher = FakeLauncher()

        class BlockingSink(FakeSink):
            def __init__(self):
                super().__init__()
                self.calls = 0

            def record(self, event, facts):
                self.calls += 1
                raise AssertionError('sync sink must not run during cleanup')

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
        assert await asyncio.wait_for(
            supervisor.cleanup(), timeout=0.5,
        ) is False
        assert {pid for pid, _sig in launcher.stopped} == {161, 162}
        assert supervisor._cleanup_residue == 'UNKNOWN'
        assert sink.calls == 0
        assert not hasattr(supervisor, '_cleanup_sink_thread')
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
                cleanup_evidence_publisher=FakeCleanupPublisher(sink),
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
            cleanup_evidence_publisher=FakeCleanupPublisher(sink),
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
            cleanup_evidence_publisher=FakeCleanupPublisher(sink),
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
            cleanup_evidence_publisher=FakeCleanupPublisher(sink),
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


def test_cleanup_without_publisher_fails_closed_and_snapshot_is_detached():
    """Missing publication fails closed while snapshots remain detached."""
    async def run():
        supervisor = LocalTrainingProcessSupervisor(
            plan=plan(False), launcher=FakeLauncher(),
            readiness=FakeReadiness(), evidence_sink=FakeSink(),
        )
        supervisor._safe_cleanup_record('retained_fact', {'nested': [1]})
        assert await supervisor.cleanup() is False
        snapshot = supervisor.cleanup_snapshot()
        assert 'cleanup_evidence_publisher_unavailable' in (
            snapshot['cleanup_errors']
        )
        assert snapshot['publication']['failed'] is True
        assert snapshot['publication']['pending'] is True
        snapshot['cleanup_errors'].clear()
        snapshot['pending_facts'][0][1]['nested'].append(2)
        assert 'cleanup_evidence_publisher_unavailable' in (
            supervisor.cleanup_snapshot()['cleanup_errors']
        )
        assert supervisor._cleanup_evidence[0][1]['nested'] == [1]
    asyncio.run(run())


def test_cleanup_batch_requires_exact_ack_and_is_not_republished():
    """Only an exact ACK clears facts; later cleanup does not retry."""
    async def run():
        sink = FakeSink()
        publisher = FakeCleanupPublisher(sink)
        supervisor = LocalTrainingProcessSupervisor(
            plan=plan(False), launcher=FakeLauncher(),
            readiness=FakeReadiness(), evidence_sink=sink,
            cleanup_evidence_publisher=publisher,
        )
        supervisor._safe_cleanup_record('batch_fact', {'value': 7})
        assert await supervisor.cleanup() is True
        snapshot = supervisor.cleanup_snapshot()
        assert snapshot['publication']['acknowledged'] is True
        assert snapshot['publication']['pending'] is False
        assert snapshot['pending_facts'] == []
        assert len(publisher.calls) == 1
        assert isinstance(publisher.calls[0][0].events, tuple)
        assert sink.events == [('batch_fact', {'value': 7})]
        assert await supervisor.cleanup() is True
        assert len(publisher.calls) == 1
    asyncio.run(run())


def test_cleanup_publisher_failure_and_false_ack_preserve_facts():
    """Publisher errors and invalid ACKs preserve the pending batch."""
    async def run():
        for behavior in ('raise', 'false_ack', 'wrong_ack'):
            publisher = FakeCleanupPublisher(behavior=behavior)
            supervisor = LocalTrainingProcessSupervisor(
                plan=plan(False), launcher=FakeLauncher(),
                readiness=FakeReadiness(), evidence_sink=FakeSink(),
                cleanup_evidence_publisher=publisher,
            )
            supervisor._safe_cleanup_record('must_remain', {'case': behavior})
            assert await supervisor.cleanup() is False
            state = supervisor.cleanup_snapshot()
            assert state['pending_facts'][0][1]['case'] == behavior
            assert state['publication']['acknowledged'] is False
            assert state['publication']['pending'] is True
            assert len(publisher.calls) == 1
            assert await supervisor.cleanup() is False
            assert len(publisher.calls) == 1
    asyncio.run(run())


def test_cleanup_publisher_timeout_keeps_owned_task_and_runs_no_retry():
    """An unjoined publisher remains owned after the common deadline."""
    async def run():
        gate = asyncio.Event()
        publisher = FakeCleanupPublisher(behavior='hold', gate=gate)
        supervisor = LocalTrainingProcessSupervisor(
            plan=plan(False), launcher=FakeLauncher(),
            readiness=FakeReadiness(), evidence_sink=FakeSink(),
            cleanup_evidence_publisher=publisher,
        )
        supervisor.CLEANUP_CAP_S = 0.03
        supervisor._safe_cleanup_record('held', {'value': 1})
        assert await asyncio.wait_for(
            supervisor.cleanup(), timeout=0.3,
        ) is False
        assert supervisor._cleanup_publisher_task is not None
        assert not supervisor._cleanup_publisher_task.done()
        assert supervisor.cleanup_snapshot()['publisher_task_done'] is False
        assert supervisor.cleanup_snapshot()['publication']['pending'] is True
        gate.set()
        await asyncio.wait_for(supervisor._cleanup_publisher_task, timeout=0.3)
        assert await supervisor.cleanup() is False
        assert len(publisher.calls) == 1
        assert supervisor._cleanup_evidence
    asyncio.run(run())


def test_cleanup_dispatches_each_group_before_waiting_for_a_stalled_group():
    """Every group gets its initial stop dispatch before grace waits."""
    async def run():
        launcher = FakeLauncher()
        alive = {201, 202}
        launcher.group_alive = lambda process: process.pid in alive
        gate = asyncio.Event()
        dispatches = []

        async def stop_group(process, sig):
            dispatches.append((process.pid, sig))
            if process.pid == 201 and sig == signal.SIGINT:
                await gate.wait()
            else:
                alive.discard(process.pid)
                process.returncode = 0

        launcher.stop_group = stop_group
        supervisor = LocalTrainingProcessSupervisor(
            plan=plan(False), launcher=launcher,
            readiness=FakeReadiness(), evidence_sink=FakeSink(),
        )
        supervisor.CLEANUP_CAP_S = 0.08
        for pid in (201, 202):
            process = FakeProcess(pid)
            supervisor.owned.append(type('Record', (), {
                'name': f'child-{pid}', 'command': ('child',),
                'pid': pid, 'process': process, 'output_tasks': (),
            })())
        cleanup = asyncio.create_task(supervisor.cleanup())
        try:
            assert await asyncio.wait_for(cleanup, timeout=0.3) is False
            assert {
                pid for pid, sig in dispatches if sig == signal.SIGINT
            } == {201, 202}
            assert 202 not in alive
        finally:
            gate.set()
            pending = list(supervisor._cleanup_residue_tasks)
            for task in pending:
                if not task.done():
                    task.cancel()
            if pending:
                await asyncio.wait(pending, timeout=0.3)
    asyncio.run(run())


def test_group_dispatch_error_does_not_prevent_other_group_stop():
    """A failed dispatch for one group does not block the next group."""
    async def run():
        launcher = FakeLauncher()
        alive = {211, 212}
        launcher.group_alive = lambda process: process.pid in alive
        attempts = []

        async def stop_group(process, sig):
            attempts.append((process.pid, sig))
            if process.pid == 211:
                raise OSError('dispatch rejected')
            alive.discard(process.pid)
            process.returncode = 0

        launcher.stop_group = stop_group
        supervisor = LocalTrainingProcessSupervisor(
            plan=plan(False), launcher=launcher,
            readiness=FakeReadiness(), evidence_sink=FakeSink(),
        )
        supervisor.CLEANUP_CAP_S = 0.08
        for pid in (211, 212):
            process = FakeProcess(pid)
            supervisor.owned.append(type('Record', (), {
                'name': f'child-{pid}', 'command': ('child',),
                'pid': pid, 'process': process, 'output_tasks': (),
            })())
        assert await asyncio.wait_for(
            supervisor.cleanup(), timeout=0.3,
        ) is False
        assert (211, signal.SIGINT) in attempts
        assert (212, signal.SIGINT) in attempts
        assert 212 not in alive
        assert any('sigint_dispatch:child-211:OSError' in item
                   for item in supervisor._cleanup_errors)
    asyncio.run(run())


def test_cleanup_publisher_failure_does_not_skip_other_group_dispatches():
    """Publisher failure does not prevent process-group stop attempts."""
    async def run():
        launcher = FakeLauncher()
        supervisor = LocalTrainingProcessSupervisor(
            plan=plan(False), launcher=launcher,
            readiness=FakeReadiness(), evidence_sink=FakeSink(),
            cleanup_evidence_publisher=FakeCleanupPublisher(
                behavior='raise',
            ),
        )
        for pid in (221, 222):
            process = FakeProcess(pid)
            supervisor.owned.append(type('Record', (), {
                'name': f'child-{pid}', 'command': ('child',),
                'pid': pid, 'process': process, 'output_tasks': (),
            })())
        assert await asyncio.wait_for(
            supervisor.cleanup(), timeout=0.5,
        ) is False
        assert {pid for pid, _sig in launcher.stopped} == {221, 222}
        assert 'cleanup_evidence_publisher:OSError' in (
            supervisor._cleanup_errors
        )
    asyncio.run(run())


def test_observer_close_outcomes_are_part_of_cleanup_verdict(tmp_path):
    """ACK, writer close, forced stop, and exit status all affect cleanup."""
    async def run():
        for mode in (
                'clean', 'clean-nonzero-exit', 'end-fail', 'hang',
                'ack-hang'):
            launcher = ControlledObserverLauncher(mode)
            case_dir = tmp_path / mode
            case_dir.mkdir()
            supervisor, _sink = _controlled_supervisor(
                case_dir, launcher,
                lambda pid: _fake_process_identity(pid),
            )
            supervisor.cleanup_evidence_publisher = FakeCleanupPublisher()
            supervisor.HEARTBEAT_OBSERVER_CLEANUP_CAP_S = 0.12
            await _start_fake_observer(supervisor)
            cleanup_ok = await supervisor.cleanup()
            state = supervisor.cleanup_snapshot()
            join = state['observer_facts']['join_evidence']
            if mode == 'clean':
                assert cleanup_ok is True
                assert join['observer_exit_status'] == 0
                assert join['observer_end_written'] is True
                assert join['observer_handle_closed'] is True
                assert join['observer_writer_closed'] is True
            else:
                assert cleanup_ok is False, (mode, state)
                if mode == 'clean-nonzero-exit':
                    assert join['observer_exit_status'] == 9
                    assert join['observer_stop_acknowledged'] is True
                    assert join['observer_termination'] == 'UNCONFIRMED_EXIT'
                    assert 'observer_stop_ack_exit_status_nonzero' in (
                        state['cleanup_errors'][0]
                    )
                if mode == 'end-fail':
                    assert join['observer_exit_status'] == 4
                    assert join['observer_handle_closed'] is True
                    assert join['observer_writer_closed'] is False
                if mode == 'hang':
                    assert join['observer_exit_status'] == -signal.SIGKILL
                    assert join['observer_termination'] == 'SIGKILL'
                if mode == 'ack-hang':
                    assert join['observer_exit_status'] == 0
                    assert join['observer_stop_acknowledged'] is True
                    assert join['observer_termination'] == (
                        'ESCALATED_AFTER_ACK'
                    )
                    assert join['observer_signal_dispatches'][-1][
                        'signal'
                    ] == 'SIGKILL'
                    assert join['observer_signal_dispatches'][-1][
                        'outcome'
                    ] == 'DISPATCHED'
                    assert any(
                        item.endswith('observer_ack_followed_by_escalation')
                        for item in state['cleanup_errors']
                    )
                assert state['process_residue'] == 'NONE'
            assert state['publication']['acknowledged'] is True
    asyncio.run(run())


def test_thread_observer_stop_async_false_fails_without_fake_process_residue():
    """A failed thread observer join is not misreported as process residue."""
    class Observer:
        async def stop_async(self, _timeout):
            return False

        def snapshot(self):
            return {
                'joined': False, 'thread_alive': True,
                'writer_closed': False, 'errors': ('not_joined',),
            }

    async def run():
        supervisor = LocalTrainingProcessSupervisor(
            plan=plan(False), launcher=FakeLauncher(),
            readiness=FakeReadiness(), evidence_sink=FakeSink(),
            heartbeat_diagnostics_enabled=True,
            cleanup_evidence_publisher=FakeCleanupPublisher(),
        )
        supervisor._heartbeat_observer = Observer()
        assert await supervisor.cleanup() is False
        state = supervisor.cleanup_snapshot()
        assert state['observer_facts']['observer']['joined'] is False
        assert state['observer_facts']['join_evidence'][
            'observer_process_joined'
        ] is False
        assert state['process_facts'] == []
        assert state['process_residue'] == 'NONE'
        assert state['publication']['acknowledged'] is True
        assert any('observer_join_residue_unknown' in error
                   for error in state['cleanup_errors'])
    asyncio.run(run())


def test_monitor_surfaces_cleanup_publication_failure_after_exit_zero():
    """Monitor raises when an exit-zero server has unconfirmed cleanup."""
    async def run():
        supervisor = LocalTrainingProcessSupervisor(
            plan=plan(False), launcher=FakeLauncher(),
            readiness=FakeReadiness(), evidence_sink=FakeSink(),
            cleanup_evidence_publisher=FakeCleanupPublisher(
                behavior='false_ack',
            ),
        )
        process = FakeProcess(231, exit_status=0)
        supervisor.owned.append(type('Record', (), {
            'name': 'server', 'command': ('server',), 'pid': 231,
            'process': process, 'output_tasks': (),
        })())
        try:
            await supervisor.monitor()
        except RuntimeError as error:
            assert 'cleanup/evidence was not confirmed' in str(error)
        else:
            raise AssertionError('monitor returned zero after cleanup failure')
        assert supervisor.cleanup_snapshot()['publication']['failed'] is True
        assert process.returncode == 0
    asyncio.run(run())


def test_cli_boundary_exits_nonzero_for_monitor_cleanup_failure(monkeypatch):
    """The CLI maps a monitor cleanup failure to a nonzero process exit."""
    import mecanum_nav_bringup.local_training_process_supervisor as module

    async def failed_run(_args):
        raise RuntimeError(
            'owned server exited but cleanup/evidence was not confirmed',
        )

    monkeypatch.setattr(module, '_run_from_cli', failed_run)
    monkeypatch.setattr(
        sys, 'argv', ['local_training_process_supervisor', '--gui', 'false',
                      '--resolved-config', '/unused/config.json'],
    )
    try:
        module.main()
    except SystemExit as error:
        assert error.code != 0
        assert 'cleanup/evidence was not confirmed' in str(error.code)
    else:
        raise AssertionError('CLI returned success after cleanup failure')


def test_observer_writer_failure_does_not_falsify_reaped_process_facts(
        tmp_path):
    """Writer failure keeps its own fact without falsifying process reap."""
    async def run():
        launcher = ControlledObserverLauncher('end-fail')
        supervisor, _sink = _controlled_supervisor(
            tmp_path, launcher,
            lambda pid: _fake_process_identity(pid),
        )
        supervisor.cleanup_evidence_publisher = FakeCleanupPublisher()
        await _start_fake_observer(supervisor)
        assert await supervisor.cleanup() is False
        snapshot = supervisor.cleanup_snapshot()
        join = snapshot['observer_facts']['join_evidence']
        assert join['observer_process_joined'] is True
        assert join['observer_process_group_absent'] is True
        assert join['observer_exit_status'] == 4
        assert join['observer_writer_closed'] is False
        assert snapshot['process_residue'] == 'NONE'
        assert snapshot['publication']['acknowledged'] is True
    asyncio.run(run())


def test_cleanup_waits_past_first_poll_for_publisher_ack():
    """An ACK after several 50 ms polls is still observed before deadline."""
    async def run():
        entered = asyncio.Event()

        class DelayedPublisher(FakeCleanupPublisher):
            async def __call__(self, batch, deadline):
                self.calls.append((batch, deadline))
                entered.set()
                await asyncio.sleep(0.14)
                return CleanupEvidenceAck(batch.batch_id, True)

        supervisor = LocalTrainingProcessSupervisor(
            plan=plan(False), launcher=FakeLauncher(),
            readiness=FakeReadiness(), evidence_sink=FakeSink(),
            cleanup_evidence_publisher=DelayedPublisher(),
        )
        supervisor.CLEANUP_CAP_S = 0.8
        supervisor._safe_cleanup_record('delayed_ack', {'value': 1})
        result = await asyncio.wait_for(supervisor.cleanup(), timeout=0.7)
        assert entered.is_set()
        assert result is True
        assert supervisor.cleanup_snapshot()['publication']['acknowledged']
    asyncio.run(run())


def test_cleanup_waits_past_first_poll_for_process_group_reap():
    """A group that exits after 50 ms remains within the shared deadline."""
    class DelayedLauncher(FakeLauncher):
        async def stop_group(self, process, sig):
            self.stopped.append((process.pid, sig))
            await asyncio.sleep(0.14)
            process.returncode = 0

    async def run():
        launcher = DelayedLauncher()
        supervisor = LocalTrainingProcessSupervisor(
            plan=plan(False), launcher=launcher,
            readiness=FakeReadiness(), evidence_sink=FakeSink(),
            cleanup_evidence_publisher=FakeCleanupPublisher(),
        )
        supervisor.CLEANUP_CAP_S = 0.8
        process = FakeProcess(701)
        supervisor.owned.append(type('Record', (), {
            'name': 'server', 'command': ('server',), 'pid': 701,
            'process': process, 'output_tasks': (),
        })())
        assert await asyncio.wait_for(supervisor.cleanup(), timeout=0.7)
        assert process.returncode == 0
        assert launcher.stopped == [(701, signal.SIGINT)]
    asyncio.run(run())


def test_cleanup_task_wait_reaches_deadline_and_accepts_shorter_caller():
    """A pending publisher follows the shorter concurrent absolute deadline."""
    async def run():
        entered = asyncio.Event()
        release = asyncio.Event()

        class HeldPublisher(FakeCleanupPublisher):
            async def __call__(self, batch, deadline):
                self.calls.append((batch, deadline))
                entered.set()
                await release.wait()
                return CleanupEvidenceAck(batch.batch_id, True)

        supervisor = LocalTrainingProcessSupervisor(
            plan=plan(False), launcher=FakeLauncher(),
            readiness=FakeReadiness(), evidence_sink=FakeSink(),
            cleanup_evidence_publisher=HeldPublisher(),
        )
        supervisor.CLEANUP_CAP_S = 1.0
        supervisor._safe_cleanup_record('held', {'value': 1})
        started = asyncio.get_running_loop().time()
        first = asyncio.create_task(supervisor.cleanup())
        await entered.wait()
        second = asyncio.create_task(supervisor.cleanup(
            deadline=asyncio.get_running_loop().time() + 0.16,
        ))
        assert await asyncio.wait_for(asyncio.gather(first, second), 0.6) == [
            False, False,
        ]
        assert asyncio.get_running_loop().time() - started < 0.5
        assert supervisor.cleanup_snapshot()['publication']['pending'] is True
        release.set()
        if supervisor._cleanup_publisher_task is not None:
            await asyncio.wait_for(supervisor._cleanup_publisher_task, 0.3)
    asyncio.run(run())


def test_start_launch_operation_is_owned_when_cleanup_races_startup():
    """Cleanup closes admission and owns a launcher that ignores cancel."""
    class DelayedLauncher(FakeLauncher):
        def __init__(self):
            super().__init__()
            self.entered = asyncio.Event()
            self.release = asyncio.Event()
            self.cancel_seen = False

        async def start(self, command, environment):
            self.entered.set()
            try:
                await self.release.wait()
            except asyncio.CancelledError:
                self.cancel_seen = True
                await self.release.wait()
            process = FakeProcess(self.next_pid)
            self.next_pid += 1
            self.started.append((command, environment, process))
            return process

    async def run():
        launcher = DelayedLauncher()
        supervisor = LocalTrainingProcessSupervisor(
            plan=plan(False), launcher=launcher,
            readiness=FakeReadiness(), evidence_sink=FakeSink(),
            cleanup_evidence_publisher=FakeCleanupPublisher(),
        )
        supervisor.CLEANUP_CAP_S = 0.35
        startup = asyncio.create_task(supervisor.start(), name='startup-test')
        await launcher.entered.wait()
        cleanup = asyncio.create_task(supervisor.cleanup())
        await asyncio.sleep(0.04)
        assert not cleanup.done()
        launcher.release.set()
        with contextlib.suppress(asyncio.CancelledError, RuntimeError):
            await asyncio.wait_for(startup, 0.3)
        assert await asyncio.wait_for(cleanup, 0.5) is True
        assert launcher.cancel_seen
        assert [record.name for record in supervisor.owned] == []
        assert supervisor.cleanup_snapshot()['launch_facts'][0][
            'handle_registered'
        ] is True
    asyncio.run(run())


def test_start_unresolved_launch_is_unknown_and_late_handle_stays_owned():
    """A handle after cleanup summary is retained without restart/readiness."""
    class DelayedLauncher(FakeLauncher):
        def __init__(self):
            super().__init__()
            self.entered = asyncio.Event()
            self.release = asyncio.Event()
            self.cancel_seen = False

        async def start(self, command, environment):
            self.entered.set()
            try:
                await self.release.wait()
            except asyncio.CancelledError:
                self.cancel_seen = True
                await self.release.wait()
            process = FakeProcess(self.next_pid)
            self.next_pid += 1
            self.started.append((command, environment, process))
            return process

    async def run():
        launcher = DelayedLauncher()
        sink = FakeSink()
        readiness = FakeReadiness()
        supervisor = LocalTrainingProcessSupervisor(
            plan=plan(False), launcher=launcher,
            readiness=readiness, evidence_sink=sink,
            cleanup_evidence_publisher=FakeCleanupPublisher(),
        )
        supervisor.CLEANUP_CAP_S = 0.12
        startup = asyncio.create_task(supervisor.start(), name='late-startup')
        await launcher.entered.wait()
        assert await asyncio.wait_for(supervisor.cleanup(), 0.4) is False
        pending_snapshot = supervisor.cleanup_snapshot()
        assert pending_snapshot['launch_facts'][0]['task_done'] is False
        assert pending_snapshot['launch_facts'][0][
            'handle_registered'
        ] is False
        launcher.release.set()
        operation = next(iter(supervisor._launch_operations.values()))
        await asyncio.wait_for(operation.task, 0.3)
        with contextlib.suppress(asyncio.CancelledError, RuntimeError):
            await asyncio.wait_for(startup, 0.3)
        snapshot = supervisor.cleanup_snapshot()
        assert snapshot['owned_process_count'] == 1
        assert snapshot['launch_facts'][0][
            'owned_process_residue'
        ] == 'UNKNOWN'
        assert any(
            fact.get('reason') == 'handle_registered_after_cleanup_deadline'
            for fact in snapshot['pipe_facts']
        )
        assert readiness.calls == []
        assert not any(event == 'server_requested' for event, _ in sink.events)
        supervisor.owned.clear()
    asyncio.run(run())


def test_start_admission_is_closed_after_cleanup_request():
    """A new start after cleanup cannot create a child."""
    async def run():
        launcher = FakeLauncher()
        supervisor = LocalTrainingProcessSupervisor(
            plan=plan(False), launcher=launcher,
            readiness=FakeReadiness(), evidence_sink=FakeSink(),
            cleanup_evidence_publisher=FakeCleanupPublisher(),
        )
        assert await supervisor.cleanup() is True
        try:
            await supervisor.start()
        except RuntimeError as error:
            assert 'admission_closed' in str(error)
        else:
            raise AssertionError('startup continued after cleanup request')
        assert launcher.started == []
    asyncio.run(run())


def test_cleanup_task_facts_show_bounded_join_result_and_are_detached():
    """Final task facts agree with a successful cancellation join."""
    async def run():
        entered = asyncio.Event()

        async def observed_task():
            entered.set()
            try:
                await asyncio.Future()
            except asyncio.CancelledError:
                await asyncio.sleep(0.02)

        supervisor = LocalTrainingProcessSupervisor(
            plan=plan(False), launcher=FakeLauncher(),
            readiness=FakeReadiness(), evidence_sink=FakeSink(),
            cleanup_evidence_publisher=FakeCleanupPublisher(),
        )
        task = asyncio.create_task(observed_task(), name='join-facts')
        supervisor._track_observer(task)
        await entered.wait()
        supervisor._safe_cleanup_record('task', {'value': 1})
        assert await supervisor.cleanup() is True
        snapshot = supervisor.cleanup_snapshot()
        fact = next(item for item in snapshot['task_facts']
                    if item['task_name'] == 'join-facts')
        assert fact['phase'] == 'final_after_bounded_join'
        assert fact['cancel_requested'] is True
        assert fact['joined'] is True
        assert fact['residue'] == 'NONE'
        snapshot['task_facts'][0]['joined'] = False
        final_fact = next(
            item for item in supervisor.cleanup_snapshot()['task_facts']
            if item['task_name'] == 'join-facts'
        )
        assert final_fact['joined'] is True
    asyncio.run(run())


def test_process_launcher_protocol_owns_group_methods():
    """The protocol assigns process-group operations to their owner."""
    import inspect

    launcher_type = __import__(
            'mecanum_nav_bringup.local_training_process_supervisor',
            fromlist=['ProcessLauncher'],
        ).ProcessLauncher
    publisher_type = __import__(
            'mecanum_nav_bringup.local_training_process_supervisor',
            fromlist=['CleanupEvidencePublisher'],
        ).CleanupEvidencePublisher
    launcher_methods = {
        name for name, member in inspect.getmembers(launcher_type)
        if callable(member)
    }
    publisher_methods = {
        name for name, member in inspect.getmembers(publisher_type)
        if callable(member)
    }
    assert {'start', 'stop_group', 'group_alive'} <= launcher_methods
    assert '__call__' in publisher_methods
    assert 'stop_group' not in publisher_methods
    assert 'group_alive' not in publisher_methods


def test_noncooperative_task_child_exits_only_after_parent_watchdog():
    """Bounded cleanup can return while a non-cooperative whole child lives."""
    import subprocess
    import select

    child_code = r"""
import asyncio, json
from types import SimpleNamespace
from mecanum_nav_bringup.local_training_process_supervisor import (
    LocalTrainingProcessSupervisor,
)
print('CHILD_READY', flush=True)
class Launcher:
    async def start(self, *_args): raise AssertionError
    async def stop_group(self, *_args): raise AssertionError
    def group_alive(self, *_args): return False
class Readiness: pass
class Sink:
    def record(self, *_args): raise AssertionError("cleanup called sync sink")
async def stubborn():
    while True:
        try: await asyncio.Future()
        except asyncio.CancelledError: continue
async def main():
    plan=SimpleNamespace(
        gui_requested=False, environment={}, session_id='child',
        config_hash='config',
    )
    supervisor=LocalTrainingProcessSupervisor(
        plan=plan, launcher=Launcher(), readiness=Readiness(),
        evidence_sink=Sink(),
    )
    supervisor.CLEANUP_CAP_S=0.03
    task=asyncio.create_task(stubborn(),name='stubborn-child-task')
    supervisor._track_observer(task)
    result=await supervisor.cleanup()
    print(json.dumps({
        'cleanup_returned': True, 'cleanup_ok': result,
        'task_done': task.done(),
        'residue': supervisor.cleanup_snapshot()['task_residue'],
    }), flush=True)
asyncio.run(main())
"""
    process = subprocess.Popen(
        [sys.executable, '-c', child_code], stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True,
    )
    try:
        # Thời gian import không thuộc ngân sách đo cleanup của child.
        ready, _, _ = select.select([process.stdout], [], [], 5.0)
        assert ready, 'child did not finish imports'
        assert process.stdout.readline().strip() == 'CHILD_READY'
        try:
            stdout, stderr = process.communicate(timeout=0.35)
            raise AssertionError(
                f'child unexpectedly exited before watchdog: {stdout} {stderr}'
            )
        except subprocess.TimeoutExpired as timeout:
            output = timeout.output or b''
            if isinstance(output, bytes):
                output = output.decode('utf-8', errors='replace')
            assert '"cleanup_returned": true' in output, output
            assert '"cleanup_ok": false' in output, output
            assert '"task_done": false' in output, output
            assert '"residue": "UNKNOWN"' in output, output
            assert process.poll() is None
    finally:
        if process.poll() is None:
            process.kill()
        process.communicate(timeout=1.0)
        assert process.returncode is not None


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


class _F11PendingLaunchLauncher:
    """Hold a server launch while recording production cleanup dispatches."""

    def __init__(self, *, hold_bridge_stop=False):
        self.next_pid = 880
        self.server_entered = asyncio.Event()
        self.server_release = asyncio.Event()
        self.bridge_stop = asyncio.Event()
        self.bridge_stop_release = asyncio.Event()
        self.server_stop = asyncio.Event()
        self.calls = []
        self.hold_bridge_stop = hold_bridge_stop
        self.processes = []

    async def start(self, command, _environment):
        process = FakeProcess(self.next_pid)
        self.next_pid += 1
        self.processes.append((command, process))
        if command[0] == 'ros2':
            return process
        self.server_entered.set()
        try:
            await self.server_release.wait()
        except asyncio.CancelledError:
            await self.server_release.wait()
        return process

    async def stop_group(self, process, sig):
        self.calls.append((process.pid, sig))
        if process.pid == 880:
            self.bridge_stop.set()
            if self.hold_bridge_stop:
                await self.bridge_stop_release.wait()
        else:
            self.server_stop.set()
        process.returncode = 0

    def group_alive(self, process):
        return process.returncode is None


class _F11ImmediateLauncher(_F11PendingLaunchLauncher):
    async def start(self, command, _environment):
        process = FakeProcess(self.next_pid)
        self.next_pid += 1
        self.processes.append((command, process))
        return process


class _F11PendingReadiness(FakeReadiness):
    def __init__(self):
        super().__init__()
        self.entered = asyncio.Event()
        self.release = asyncio.Event()

    async def server_scene(self, *_args):
        self.entered.set()
        try:
            await self.release.wait()
        except asyncio.CancelledError:
            await self.release.wait()


def _f11_supervisor(launcher, readiness=None, cap=0.8):
    supervisor = LocalTrainingProcessSupervisor(
        plan=_plan_with_bridge(False), launcher=launcher,
        readiness=readiness or FakeReadiness(), evidence_sink=FakeSink(),
        cleanup_evidence_publisher=FakeCleanupPublisher(),
    )
    supervisor.CLEANUP_CAP_S = cap
    return supervisor


async def _f11_expect(event, timeout, label):
    try:
        await asyncio.wait_for(event.wait(), timeout)
    except TimeoutError as error:
        raise AssertionError(
            f'{label} was not observed before the bounded check'
        ) from error


async def _f11_release_and_join(
    launcher, readiness, startup, cleanup_tasks,
):
    launcher.server_release.set()
    launcher.bridge_stop_release.set()
    if readiness is not None:
        readiness.release.set()
    if startup is not None and not startup.done():
        with contextlib.suppress(BaseException):
            await asyncio.wait_for(startup, 0.7)
    for task in cleanup_tasks:
        if task is not None and not task.done():
            with contextlib.suppress(BaseException):
                await asyncio.wait_for(task, 1.0)


def test_f11a_registered_bridge_stopped_while_server_launch_unresolved():
    """Stop a registered bridge before a server launcher joins."""
    async def run():
        launcher = _F11PendingLaunchLauncher()
        supervisor = _f11_supervisor(launcher)
        startup = asyncio.create_task(supervisor.start())
        cleanup = None
        try:
            await asyncio.wait_for(launcher.server_entered.wait(), 0.3)
            cleanup = asyncio.create_task(supervisor.cleanup())
            await _f11_expect(launcher.bridge_stop, 0.25, 'bridge stop')
            assert not launcher.server_release.is_set()
        finally:
            await _f11_release_and_join(
                launcher, None, startup, (cleanup,),
            )
    asyncio.run(run())


def test_f11b_registered_server_stopped_before_readiness_join():
    """Stop a registered server while readiness ignores cancellation."""
    async def run():
        launcher = _F11ImmediateLauncher()
        readiness = _F11PendingReadiness()
        supervisor = _f11_supervisor(launcher, readiness)
        startup = asyncio.create_task(supervisor.start())
        cleanup = None
        try:
            await asyncio.wait_for(readiness.entered.wait(), 0.3)
            cleanup = asyncio.create_task(supervisor.cleanup())
            await _f11_expect(launcher.server_stop, 0.25, 'server stop')
            assert not readiness.release.is_set()
            assert not startup.done()
            pending = [
                item for item in supervisor.cleanup_snapshot()['task_facts']
                if item.get('task_name') == startup.get_name()
            ]
            assert pending and pending[0]['joined'] is False
        finally:
            await _f11_release_and_join(
                launcher, readiness, startup, (cleanup,),
            )
    asyncio.run(run())


def test_f11c_late_handle_joins_same_cleanup_while_known_stop_is_pending():
    """Reclaim a late server handle under the existing cleanup operation."""
    async def run():
        launcher = _F11PendingLaunchLauncher(hold_bridge_stop=True)
        supervisor = _f11_supervisor(launcher, cap=1.2)
        startup = asyncio.create_task(supervisor.start())
        cleanup = None
        try:
            await asyncio.wait_for(launcher.server_entered.wait(), 0.3)
            cleanup = asyncio.create_task(supervisor.cleanup())
            await _f11_expect(launcher.bridge_stop, 0.25, 'bridge stop')
            launcher.server_release.set()
            await _f11_expect(launcher.server_stop, 0.3, 'late server stop')
            assert sum(pid == 880 for pid, _ in launcher.calls) == 1
            assert sum(pid == 881 for pid, _ in launcher.calls) == 1
            launcher.bridge_stop_release.set()
            with contextlib.suppress(BaseException):
                await asyncio.wait_for(startup, 0.5)
            assert await asyncio.wait_for(cleanup, 0.7) is True
            snapshot = supervisor.cleanup_snapshot()
            assert snapshot['owned_process_count'] == 0
            assert {item['pid'] for item in snapshot['process_facts']} == {
                880, 881,
            }
        finally:
            await _f11_release_and_join(
                launcher, None, startup, (cleanup,),
            )
    asyncio.run(run())


def test_f11d_shortened_deadline_retains_late_handle_without_redispatch():
    """Retain late ownership after a caller shortens the deadline."""
    async def run():
        launcher = _F11PendingLaunchLauncher()
        supervisor = _f11_supervisor(launcher, cap=1.2)
        startup = asyncio.create_task(supervisor.start())
        cleanup_a = cleanup_b = None
        try:
            await asyncio.wait_for(launcher.server_entered.wait(), 0.3)
            cleanup_a = asyncio.create_task(supervisor.cleanup())
            await _f11_expect(launcher.bridge_stop, 0.25, 'bridge stop')
            cleanup_b = asyncio.create_task(supervisor.cleanup(
                deadline=asyncio.get_running_loop().time() + 0.16,
            ))
            first, second = await asyncio.wait_for(
                asyncio.gather(cleanup_a, cleanup_b), 0.6,
            )
            assert first is False and second is False
            assert sum(pid == 880 for pid, _ in launcher.calls) == 1
            launcher.server_release.set()
            operation = next(iter(supervisor._launch_operations.values()))
            with contextlib.suppress(BaseException):
                await asyncio.wait_for(operation.task, 0.4)
            snapshot = supervisor.cleanup_snapshot()
            assert snapshot['owned_process_count'] == 1
            assert snapshot['launch_facts'][0][
                'owned_process_residue'
            ] == 'UNKNOWN'
            assert not any(pid == 881 for pid, _ in launcher.calls)
            assert sum(
                item['pid'] == 880 for item in
                snapshot['process_cleanup_operations']
            ) == 1
        finally:
            await _f11_release_and_join(
                launcher, None, startup, (cleanup_a, cleanup_b),
            )
    asyncio.run(run())


def test_codex_gui_confirmation_is_not_recorded_as_human_ack():
    """Giữ nguồn review Codex riêng với xác nhận của Owner."""
    async def run():
        readiness = FakeReadiness()
        readiness.gui_confirmation_source = 'codex_image_review'
        sink = FakeSink()
        supervisor = LocalTrainingProcessSupervisor(
            plan=plan(True), launcher=FakeLauncher(), readiness=readiness,
            evidence_sink=sink,
        )
        await supervisor.start()
        events = dict(sink.events)
        assert 'gui_scene_owner_confirmed' not in events
        assert events['gui_scene_codex_confirmed']['confirmation_source'] == (
            'codex_image_review'
        )
    asyncio.run(run())
