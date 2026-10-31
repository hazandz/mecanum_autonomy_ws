"""Injected process/readiness tests; no Gazebo or ROS process is spawned."""
import asyncio
import contextlib
import os
import signal
import sys
from types import SimpleNamespace

from mecanum_nav_bringup import (
    local_training_process_supervisor as supervisor_module,
)
from mecanum_nav_bringup.local_training_launch_contract import LaunchPlan
from mecanum_nav_bringup.local_training_process_supervisor import (
    LocalTrainingProcessSupervisor,
    RclpyReadiness,
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


class FakeReadiness:
    """Record readiness checks and return an injected owner acknowledgment."""

    def __init__(self, ack=(True, 'screenshot://scene'), failure=None):
        """Initialize fake readiness responses."""
        self.ack = ack
        self.failure = failure
        self.calls = []

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
        {'GZ_PARTITION': 'partition'},
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
        assert launcher.started[0][1] == launcher.started[1][1]
        assert [call[0] for call in readiness.calls] == [
            'server', 'gui', 'ack',
        ]
        event = dict(sink.events)['gui_scene_owner_confirmed']
        assert event['confirmation_source'] == 'human_owner'
        assert event['screenshot_ref'] == 'screenshot://scene'
        assert event['environment']['GZ_PARTITION'] == 'partition'
    asyncio.run(run())


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
        assert (
            dict(sink.events)['owned_process_cleanup']['escalation']
            == 'SIGINT'
        )
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
        ('paused', True),
        ('actuator_inhibited', False),
    ):
        altered = SimpleNamespace(**vars(message))
        setattr(altered, field, value)
        assert not matches(altered, expected_plan, expected_hash)


def test_production_scene_adapter_queries_world_scene_and_checks_cardinality():
    """Interpret Gazebo Scene replies separately from backend heartbeats."""
    calls = []
    current = [SimpleNamespace(
        name='b2_training_arena',
        model=[SimpleNamespace(name='mecanum_b2', model=[])],
    )]

    def query(service, timeout_ms):
        calls.append((service, timeout_ms))
        return current[0]

    readiness = RclpyReadiness(scene_query=query)
    expected_plan = plan(False)
    assert asyncio.run(readiness._query_scene_matches(expected_plan))
    assert calls == [('/world/b2_training_arena/scene/info', 500)]

    current[0] = SimpleNamespace(
        name='other_world',
        model=[SimpleNamespace(name='mecanum_b2', model=[])],
    )
    assert not asyncio.run(readiness._query_scene_matches(expected_plan))
    current[0] = SimpleNamespace(name='b2_training_arena', model=[])
    assert not asyncio.run(readiness._query_scene_matches(expected_plan))
    current[0] = SimpleNamespace(
        name='b2_training_arena',
        model=[
            SimpleNamespace(name='mecanum_b2', model=[]),
            SimpleNamespace(name='mecanum_b2', model=[]),
        ],
    )
    assert not asyncio.run(readiness._query_scene_matches(expected_plan))


def test_integrated_backend_status_requires_bound_status_and_scene(
    monkeypatch,
):
    """Join injected status and typed scene data through production entry."""
    monkeypatch.setattr(
        supervisor_module, 'load_bound_config',
        lambda _path: (None, 'a' * 64, None, None),
    )
    expected_plan = plan(False)
    status = SimpleNamespace(
        header=SimpleNamespace(frame_id='b2_training_arena'),
        session_id=expected_plan.session_id,
        config_hash='a' * 64,
        backend_instance_id=17,
        status_sequence=2,
        fault_flags=0,
        paused=False,
        actuator_inhibited=True,
    )
    scene = SimpleNamespace(
        name='b2_training_arena',
        model=[SimpleNamespace(name='mecanum_b2', model=[])],
    )

    class StatusSource:
        def __init__(self, messages):
            self.messages = list(messages)
            self.started = 0
            self.closed = 0

        async def start(self):
            self.started += 1

        async def next_status(self, timeout_s):
            assert 0 < timeout_s <= 0.1
            return self.messages.pop(0) if self.messages else None

        async def close(self):
            self.closed += 1

    source = StatusSource([status])
    query_calls = []
    readiness = RclpyReadiness(
        scene_query=lambda endpoint, timeout: (
            query_calls.append((endpoint, timeout)) or scene
        ),
        backend_status_source_factory=lambda: source,
        steady_clock=lambda: 10.0,
    )
    process = FakeProcess(700)
    asyncio.run(readiness._backend_status(expected_plan, process))
    assert source.started == source.closed == 1
    assert query_calls == [('/world/b2_training_arena/scene/info', 500)]


def test_integrated_backend_status_rejects_status_or_scene_mismatch(
    monkeypatch,
):
    """A healthy heartbeat cannot substitute for the expected scene."""
    monkeypatch.setattr(
        supervisor_module, 'load_bound_config',
        lambda _path: (None, 'a' * 64, None, None),
    )
    expected_plan = plan(False)
    good_status = SimpleNamespace(
        header=SimpleNamespace(frame_id='b2_training_arena'),
        session_id=expected_plan.session_id,
        config_hash='a' * 64,
        backend_instance_id=17,
        status_sequence=2,
        fault_flags=0,
        paused=False,
        actuator_inhibited=True,
    )

    class StatusSource:
        def __init__(self, message):
            self.message = message

        async def start(self):
            return None

        async def next_status(self, timeout_s):
            del timeout_s
            return self.message

        async def close(self):
            return None

    wrong_status = SimpleNamespace(**vars(good_status))
    wrong_status.session_id = 'foreign-session'
    for status, scene in (
        (good_status, SimpleNamespace(name='wrong-world', model=[])),
        (wrong_status, SimpleNamespace(
            name='b2_training_arena',
            model=[SimpleNamespace(name='mecanum_b2', model=[])],
        )),
    ):
        ticks = iter((0.0, 31.0))
        readiness = RclpyReadiness(
            scene_query=lambda _endpoint, _timeout: scene,
            backend_status_source_factory=lambda: StatusSource(status),
            steady_clock=lambda: next(ticks),
        )
        try:
            asyncio.run(readiness._backend_status(
                expected_plan, FakeProcess(701),
            ))
        except TimeoutError:
            pass
        else:
            raise AssertionError('mismatched status or scene was accepted')


def test_integrated_backend_status_closes_partial_source_on_start_failure(
    monkeypatch,
):
    """A failed status-source startup is closed without runtime fallback."""
    monkeypatch.setattr(
        supervisor_module, 'load_bound_config',
        lambda _path: (None, 'a' * 64, None, None),
    )

    class PartialSource:
        def __init__(self):
            self.closed = 0

        async def start(self):
            raise RuntimeError('injected status subscription failure')

        async def next_status(self, timeout_s):
            del timeout_s
            raise AssertionError('failed source must not be polled')

        async def close(self):
            self.closed += 1

    source = PartialSource()
    readiness = RclpyReadiness(
        scene_query=lambda *_args: (_ for _ in ()).throw(
            AssertionError('scene query must not start after status failure')
        ),
        backend_status_source_factory=lambda: source,
    )
    try:
        asyncio.run(readiness._backend_status(plan(False), FakeProcess(702)))
    except RuntimeError as error:
        assert str(error) == 'injected status subscription failure'
    else:
        raise AssertionError('partial status-source failure was accepted')
    assert source.closed == 1


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
