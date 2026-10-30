"""Injected process/readiness tests; no Gazebo or ROS process is spawned."""
import asyncio
import signal

from mecanum_nav_bringup.local_training_launch_contract import LaunchPlan
from mecanum_nav_bringup.local_training_process_supervisor import (
    LocalTrainingProcessSupervisor,
)


class FakeProcess:
    """Fake child process used by supervisor tests."""

    def __init__(self, pid, exit_status=None):
        """Initialize fake process state."""
        self.pid = pid
        self.returncode = exit_status
        self.wait_count = 0

    async def wait(self):
        """Return the configured process status."""
        self.wait_count += 1
        return self.returncode or 0


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
        """Record a stop request and mark its process as stopped."""
        self.stopped.append((process.pid, sig))
        process.returncode = 0


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

    async def gui_rendered(self, plan, process, timeout_s):
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
        'a' * 64, 'b' * 64, commands, {'GZ_PARTITION': 'partition'},
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
