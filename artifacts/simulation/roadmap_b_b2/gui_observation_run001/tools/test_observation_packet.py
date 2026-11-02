"""Offline-only regressions for the canonical B22 RUN001 packet and runner."""
from __future__ import annotations

import asyncio
import concurrent.futures
import hashlib
import importlib
import json
import os
import signal
import sys
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest

HERE = Path(__file__).resolve().parent
BUNDLE_PACKET = HERE.parent / 'packet.json'
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

guard = importlib.import_module('observation_guard')
runner = importlib.import_module('observation_runner')
sink_module = importlib.import_module('observation_sink')

RUN_TEST_ID = 'B22_GUI_OBSERVATION_TEST_R1_R7'
ObservationEvidenceSink = sink_module.ObservationEvidenceSink
ObservationFailure = runner.ObservationFailure
OwnerAbort = runner.OwnerAbort
PassiveBackendObserver = runner.PassiveBackendObserver
ScreenshotReadiness = runner.ScreenshotReadiness
TOOL_PATHS = runner.TOOL_PATHS


def _bundle_packet():
    return json.loads(BUNDLE_PACKET.read_text(encoding='utf-8'))


def _payload(index=1):
    return {'run_id': RUN_TEST_ID, 'contender': index}


def test_acquire_once_and_replay_refusal(tmp_path):
    """Test atomic acquisition admits exactly one call and rejects replay."""
    path = tmp_path / 'acquisition.json'
    guard.acquire_once(path, _payload())
    assert json.loads(path.read_text()) == _payload()
    with pytest.raises(guard.GuardError, match='already exists'):
        guard.acquire_once(path, _payload(2))
    assert json.loads(path.read_text()) == _payload()


def test_two_contenders_have_exactly_one_winner(tmp_path):
    """Test concurrent contenders cannot consume capacity twice."""
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
    """Test a partial guard is permanent and never reset for replay."""
    path = tmp_path / 'acquisition.json'
    path.write_bytes(b'{"partial":')
    with pytest.raises(guard.GuardError, match='already exists'):
        guard.acquire_once(path, _payload())
    assert path.read_bytes() == b'{"partial":'


def test_acquisition_write_failure_retains_exclusive_file(tmp_path):
    """Test a failed acquisition write retains its consumed file."""
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


def test_packet_bundle_is_canonical_and_binds_installation(tmp_path):
    """Test the checked packet uses the sole nested production schema."""
    packet = _bundle_packet()
    tools = guard.tool_hashes(TOOL_PATHS)
    bindings = guard.packet_bindings(packet, tools)
    assert packet['repository']['production_source_pin'] == (
        guard.PRODUCTION_SOURCE_PIN
    )
    assert bindings['file_sha256'] == packet['installation']['file_sha256']
    assert bindings['dependency_fingerprints'] == (
        packet['installation']['dependency_fingerprints']
    )
    assert len(bindings['file_sha256']) == 47
    assert 'production_source_pin' not in packet
    assert not (tmp_path / guard.GUARD_PATH.name).exists()


def test_packet_missing_nested_source_pin_rejects_before_acquisition():
    """Test a missing canonical nested source pin fails closed."""
    packet = _bundle_packet()
    del packet['repository']['production_source_pin']
    with pytest.raises(guard.GuardError, match='repository fields'):
        guard.packet_bindings(packet, guard.tool_hashes(TOOL_PATHS))


def test_packet_wrong_type_and_wrong_source_pin_reject():
    """Test malformed type and wrong nested source pin both fail closed."""
    packet = _bundle_packet()
    packet['capacity'] = True
    with pytest.raises(guard.GuardError, match='capacity'):
        guard.packet_bindings(packet, guard.tool_hashes(TOOL_PATHS))
    packet = _bundle_packet()
    packet['repository']['production_source_pin'] = '0' * 40
    with pytest.raises(guard.GuardError, match='source pins'):
        guard.packet_bindings(packet, guard.tool_hashes(TOOL_PATHS))


def test_packet_rejects_conflicting_extra_schema_field():
    """Test the packet cannot add an alternative top-level pin schema."""
    packet = _bundle_packet()
    packet['production_source_pin'] = guard.PRODUCTION_SOURCE_PIN
    with pytest.raises(guard.GuardError, match='canonical schema'):
        guard.packet_bindings(packet, guard.tool_hashes(TOOL_PATHS))


def test_approval_binds_actual_bundle_packet_and_all_tools(tmp_path):
    """Test approval validation hashes the real packet bytes and all tools."""
    packet_path = tmp_path / 'packet.json'
    packet_path.write_bytes(BUNDLE_PACKET.read_bytes())
    approval_path = tmp_path / 'approval.json'
    tools = guard.tool_hashes(TOOL_PATHS)
    approval = {
        'schema_id': 'b22_gui_observation_owner_approval/v1',
        'run_id': guard.RUN_ID,
        'packet_sha256': hashlib.sha256(packet_path.read_bytes()).hexdigest(),
        'packet_commit': 'a' * 40,
        'production_source_pin': guard.PRODUCTION_SOURCE_PIN,
        'tool_sha256': tools,
    }
    approval_path.write_text(json.dumps(approval))
    packet, digest, actual = guard.validate_approval(
        packet_path=packet_path, approval_path=approval_path,
        expected_commit='a' * 40, tool_paths=TOOL_PATHS,
    )
    assert packet == _bundle_packet()
    assert digest == approval['packet_sha256']
    assert actual == tools
    approval['tool_sha256']['observation_runner.py'] = '0' * 64
    approval_path.write_text(json.dumps(approval))
    with pytest.raises(guard.GuardError, match='tool_sha256'):
        guard.validate_approval(
            packet_path=packet_path, approval_path=approval_path,
            expected_commit='a' * 40, tool_paths=TOOL_PATHS,
        )


def test_run_roots_are_fixed_and_reject_symlink_redirect(tmp_path):
    """Test injected roots remain isolated and symlink aliases are refused."""
    root = tmp_path / 'evidence'
    root.mkdir()
    guard_path = root / 'acquisition.json'
    assert runner.validate_run_roots(
        guard_path, root, expected_guard=guard_path,
        expected_evidence=root,
    ) == (guard_path, root)
    alias = tmp_path / 'evidence-alias'
    alias.symlink_to(root, target_is_directory=True)
    with pytest.raises(guard.GuardError, match='canonical|symlink'):
        runner.validate_run_roots(
            guard_path, alias, expected_guard=guard_path,
            expected_evidence=alias,
        )
    assert not guard_path.exists()


def test_run_roots_reject_existing_partial_guard_and_old_evidence(tmp_path):
    """Test existing guard bytes and evidence are preserved and block use."""
    root = tmp_path / 'evidence'
    root.mkdir()
    guard_path = root / 'acquisition.json'
    guard_path.write_bytes(b'')
    with pytest.raises(guard.GuardError, match='already exists'):
        runner.validate_run_roots(
            guard_path, root, expected_guard=guard_path,
            expected_evidence=root,
        )
    assert guard_path.read_bytes() == b''
    guard_path.unlink()
    old = root / 'old.jsonl'
    old.write_text('prior evidence')
    with pytest.raises(guard.GuardError, match='contains data'):
        runner.validate_run_roots(
            guard_path, root, expected_guard=guard_path,
            expected_evidence=root,
        )
    assert old.read_text() == 'prior evidence'


def test_cli_has_no_acquisition_or_evidence_root_override():
    """Test production CLI keeps canonical guard and evidence destinations."""
    args = runner.parse_args([
        '--gui', 'true', '--approval-file', '/tmp/approval.json',
        '--approved-commit', 'a' * 40,
    ])
    assert not hasattr(args, 'guard_path')
    assert not hasattr(args, 'evidence_root')
    for option in ('--guard-path', '--evidence-root'):
        with pytest.raises(SystemExit):
            runner.parse_args([
                '--gui', 'true', '--approval-file', '/tmp/a.json',
                '--approved-commit', 'a' * 40, option, '/tmp/alternate',
            ])


def test_gui_parser_and_run001_gui_true_are_strict():
    """Test GUI parsing is strict and RUN001 cannot disable its GUI."""
    assert runner.strict_gui_value('true') is True
    assert runner.strict_gui_value('false') is False
    for value in ('True', 'FALSE', 'yes', '1', '', ' true'):
        with pytest.raises(Exception):
            runner.strict_gui_value(value)
    with pytest.raises(ObservationFailure, match='--gui true'):
        runner.require_run_gui(False)


def test_tty_and_existing_desktop_socket_are_mandatory():
    """Test preflight requires Owner TTY and an existing desktop socket."""
    with pytest.raises(ObservationFailure, match='TTY'):
        runner.preflight_desktop(False, {'DISPLAY': ':0'}, lambda _p: True)
    with pytest.raises(ObservationFailure, match='desktop socket'):
        runner.preflight_desktop(True, {'DISPLAY': ':0'}, lambda _p: False)
    runner.preflight_desktop(
        True,
        {'WAYLAND_DISPLAY': 'wayland-0', 'XDG_RUNTIME_DIR': '/run/user/9'},
        lambda path: Path(path) == Path('/run/user/9/wayland-0'),
    )


def test_owner_ack_requires_a_real_screenshot_and_direct_token(tmp_path):
    """Test screenshot verification does not invent Owner acknowledgment."""
    class Readiness:
        async def owner_ack(self, _timeout):
            return True, str(tmp_path / 'missing.png')

    async def check():
        with pytest.raises(FileNotFoundError):
            await ScreenshotReadiness(Readiness()).owner_ack(60.0)

    asyncio.run(check())


def test_owner_ack_timeout_and_cancellation_are_not_auto_accepted():
    """Test Owner input timeout and cancellation do not synthesize consent."""
    class Readiness:
        async def owner_ack(self, _timeout):
            return False, 'owner_ack_timeout'

    async def check():
        readiness = ScreenshotReadiness(Readiness())
        assert await readiness.owner_ack(60.0) == (False, 'owner_ack_timeout')

        class Pending:
            async def owner_ack(self, _timeout):
                await asyncio.Future()

        wrapper = ScreenshotReadiness(Pending())
        task = asyncio.create_task(wrapper.owner_ack(60.0))
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert wrapper.owner_ack_cancelled

    asyncio.run(check())


def test_evidence_is_exclusive_correlated_and_append_only(tmp_path):
    """Test JSONL sink records ordered identity and refuses overwrite."""
    evidence = ObservationEvidenceSink(
        tmp_path, RUN_TEST_ID, 'session-1', monotonic_ns=lambda: 42,
    )
    evidence.record('fact', {'paused': True})
    evidence.close()
    rows = [
        json.loads(line)
        for line in (tmp_path / 'observation.jsonl').read_text().splitlines()
    ]
    assert rows[0]['sequence'] == 1
    assert rows[0]['steady_time_ns'] == 42
    assert rows[0]['run_id'] == RUN_TEST_ID
    assert rows[0]['session_id'] == 'session-1'
    with pytest.raises(FileExistsError):
        ObservationEvidenceSink(tmp_path, RUN_TEST_ID, 'session-2')


def test_evidence_write_failure_propagates(tmp_path):
    """Test a JSONL write failure propagates to the run boundary."""
    class BrokenStream:
        def write(self, _value):
            raise OSError('disk full')

        def close(self):
            pass

    evidence = ObservationEvidenceSink.__new__(ObservationEvidenceSink)
    import threading
    from datetime import datetime, timezone
    evidence.root = tmp_path
    evidence.run_id = RUN_TEST_ID
    evidence.session_id = 'session'
    evidence._monotonic_ns = lambda: 1
    evidence._utc_now = lambda: datetime.now(timezone.utc)
    evidence._lock = threading.Lock()
    evidence._sequence = 0
    evidence.events = []
    evidence._stream = BrokenStream()
    with pytest.raises(OSError, match='disk full'):
        evidence.record('must-fail', {})


def _fake_ros_api():
    """Build a ROS API double that captures the production subscription QoS."""
    state = {'subscriptions': [], 'init': [], 'shutdown': 0, 'destroy': 0}

    class Context:
        pass

    class Node:
        def __init__(self, _name, *, context):
            self.context = context

        def create_subscription(self, *args):
            state['subscriptions'].append(args)
            return object()

        def get_node_names_and_namespaces(self):
            return []

        def destroy_node(self):
            state['destroy'] += 1

    class Rclpy:
        @staticmethod
        def init(*, context, domain_id):
            state['init'].append((context, domain_id))

        @staticmethod
        def ok(*, context):
            return True

        @staticmethod
        def shutdown(*, context):
            state['shutdown'] += 1

    class QoSProfile:
        def __init__(self, **kwargs):
            self.settings = kwargs

    return state, SimpleNamespace(
        rclpy=Rclpy, Context=Context, Node=Node,
        SimulationContactState=object, Clock=object, QoSProfile=QoSProfile,
        HistoryPolicy=SimpleNamespace(KEEP_LAST='keep_last'),
        ReliabilityPolicy=SimpleNamespace(BEST_EFFORT='best_effort'),
        DurabilityPolicy=SimpleNamespace(VOLATILE='volatile'),
    )


def test_production_observer_passes_clock_qos_to_subscription_factory():
    """Test CLOCK-compatible QoS reaches the production subscriber."""
    state, api = _fake_ros_api()
    observer = PassiveBackendObserver(ros_api_factory=lambda: api)
    observer.start()
    clock_subscription = state['subscriptions'][1]
    assert clock_subscription[1] == '/clock'
    assert clock_subscription[3].settings == {
        'history': 'keep_last', 'depth': 10,
        'reliability': 'best_effort', 'durability': 'volatile',
    }
    assert state['init'][0][1] == 83
    observer.close()
    observer.close()
    assert state['destroy'] == 1
    assert state['shutdown'] == 1


class _EvaluationObserver:
    def __init__(
        self, clock, *, emit_clock=True, emit_backend=True,
        inhibit_after=None, change_clock_at=None, duplicate_sequence=False,
        backend_once=False, foreign_node=False, graph_schedule=None,
        readiness_event=None, ack_event=None, duplicate_backend=False,
    ):
        self.clock = clock
        self.emit_clock = emit_clock
        self.emit_backend = emit_backend
        self.inhibit_after = inhibit_after
        self.change_clock_at = change_clock_at
        self.duplicate_sequence = duplicate_sequence
        self.backend_once = backend_once
        self.foreign_node = foreign_node
        self.graph_schedule = graph_schedule
        self.readiness_event = readiness_event
        self.ack_event = ack_event
        self.duplicate_backend = duplicate_backend
        self.graph_calls = 0
        self.events = __import__('collections').deque()
        self.calls = 0
        self.close_count = 0
        self.started = False

    def start(self):
        self.started = True

    def spin_once(self, _timeout_s=0.05):
        self.clock[0] += 0.05
        self.calls += 1
        now = self.clock[0]
        if self.emit_clock:
            nanosec = (
                1 if (
                    self.change_clock_at
                    and self.calls >= self.change_clock_at
                )
                else 0
            )
            self.events.append((
                'clock', SimpleNamespace(sec=0, nanosec=nanosec),
                now, int(now * 1e9),
            ))
        if self.emit_backend and (not self.backend_once or self.calls == 1):
            sequence = 1 if self.duplicate_sequence else self.calls
            inhibited = not (
                self.inhibit_after is not None
                and self.calls >= self.inhibit_after
            )
            message = SimpleNamespace(
                session_id='session-test', config_hash=guard.CONFIG_HASH,
                backend_instance_id=19,
                header=SimpleNamespace(frame_id='b2_training_arena'),
                status_sequence=sequence, paused=True,
                actuator_inhibited=inhibited, fault_flags=0,
                applied_receipt_valid=False,
            )
            self.events.append(('backend', message, now, int(now * 1e9)))

    def node_inventory(self):
        persistent = [
            ('b22_gui_observation_observer', '/'),
            ('mecanum_sim_backend', '/'),
            ('robot_state_publisher', '/'), ('ros_gz_bridge', '/'),
        ]
        if self.graph_schedule is not None:
            names = self.graph_schedule[min(
                self.graph_calls, len(self.graph_schedule) - 1,
            )]
            self.graph_calls += 1
            if (self.readiness_event is not None
                    and ('b2_server_scene_readiness', '/') not in names
                    and self.graph_calls >= len(self.graph_schedule)):
                self.readiness_event.set()
                if self.ack_event is not None:
                    self.ack_event.set()
            return names
        names = list(persistent)
        if self.duplicate_backend:
            names.append(('mecanum_sim_backend', '/'))
        if self.foreign_node:
            names.append(('foreign_robot', '/'))
        return names

    def close(self):
        self.close_count += 1


class _Sink:
    def __init__(self, fail_event=None):
        self.records = []
        self.fail_event = fail_event
        self.closed = 0

    def record(self, event, facts):
        self.records.append((event, facts))
        if event == self.fail_event:
            raise OSError(f'injected evidence failure: {event}')

    def close(self):
        self.closed += 1


def _observation_inputs(**kwargs):
    clock = [0.0]
    observer = _EvaluationObserver(clock, **kwargs)
    sink = _Sink()
    ack = asyncio.Event()
    ack.set()
    return clock, observer, sink, ack


def test_observer_requires_stable_clock_paused_inhibit_and_heartbeat():
    """Test good samples produce detailed facts only after clock stability."""
    async def check():
        clock, observer, evidence, ack = _observation_inputs()
        result = await runner.evaluate_observation(
            plan=SimpleNamespace(
                session_id='session-test', config_hash=guard.CONFIG_HASH,
            ),
            observer=observer, duration_s=1.0, steady=lambda: clock[0],
            ack_event=ack, deadline=10.0, sink=evidence,
        )
        assert result['observed_seconds'] >= 1.0
        assert result['backend_status_samples'] > 1
        assert result['clock_samples'] > 1
        assert any(
            name == 'backend_status_sample' for name, _ in evidence.records
        )
        assert any(name == 'clock_sample' for name, _ in evidence.records)

    asyncio.run(check())


def test_missing_clock_times_out_instead_of_becoming_stable():
    """Test silence on /clock times out and cannot satisfy the stable gate."""
    async def check():
        clock, observer, evidence, ack = _observation_inputs(emit_clock=False)
        with pytest.raises(ObservationFailure, match='clock readiness'):
            await runner.evaluate_observation(
                plan=SimpleNamespace(
                    session_id='session-test', config_hash=guard.CONFIG_HASH,
                ), observer=observer, duration_s=1.0,
                steady=lambda: clock[0], ack_event=ack, deadline=2.0,
                sink=evidence, clock_ready_timeout_s=0.2,
            )

    asyncio.run(check())


def test_clock_progress_and_clock_sample_loss_fail():
    """Test changed clock and silent clock stream both fail closed."""
    async def check():
        clock, observer, evidence, ack = _observation_inputs(change_clock_at=4)
        with pytest.raises(ObservationFailure, match='clock advanced'):
            await runner.evaluate_observation(
                plan=SimpleNamespace(
                    session_id='session-test', config_hash=guard.CONFIG_HASH,
                ), observer=observer, duration_s=1,
                steady=lambda: clock[0], ack_event=ack,
                deadline=20, sink=evidence,
            )
        clock, observer, evidence, ack = _observation_inputs()
        observer.emit_clock = False
        with pytest.raises(ObservationFailure, match='clock readiness'):
            await runner.evaluate_observation(
                plan=SimpleNamespace(
                    session_id='session-test', config_hash=guard.CONFIG_HASH,
                ), observer=observer, duration_s=10,
                clock_ready_timeout_s=0.2,
                steady=lambda: clock[0], ack_event=ack,
                deadline=20, sink=evidence,
            )

    asyncio.run(check())


def test_heartbeat_gap_duplicate_sequence_and_inhibit_loss_fail():
    """Test stale, repeated and unsafe backend statuses cannot pass."""
    async def check():
        plan = SimpleNamespace(
            session_id='session-test', config_hash=guard.CONFIG_HASH,
        )
        clock, observer, evidence, ack = _observation_inputs(backend_once=True)
        with pytest.raises(ObservationFailure, match='heartbeat lost'):
            await runner.evaluate_observation(
                plan=plan, observer=observer, duration_s=3,
                steady=lambda: clock[0], ack_event=ack,
                deadline=10, sink=evidence,
            )
        clock, observer, evidence, ack = _observation_inputs(
            duplicate_sequence=True,
        )
        with pytest.raises(
            ObservationFailure, match='sequence did not increase',
        ):
            await runner.evaluate_observation(
                plan=plan, observer=observer, duration_s=2,
                steady=lambda: clock[0], ack_event=ack,
                deadline=10, sink=evidence,
            )
        clock, observer, evidence, ack = _observation_inputs(inhibit_after=5)
        with pytest.raises(ObservationFailure, match='paused and inhibited'):
            await runner.evaluate_observation(
                plan=plan, observer=observer, duration_s=2,
                steady=lambda: clock[0], ack_event=ack,
                deadline=10, sink=evidence,
            )

    asyncio.run(check())


def test_foreign_graph_participant_and_background_evidence_fail():
    """Test foreign nodes and failed evidence abort observation."""
    async def check():
        plan = SimpleNamespace(
            session_id='session-test', config_hash=guard.CONFIG_HASH,
        )
        clock, observer, evidence, ack = _observation_inputs(foreign_node=True)
        with pytest.raises(ObservationFailure, match='unexpected ROS graph'):
            await runner.evaluate_observation(
                plan=plan, observer=observer, duration_s=1,
                steady=lambda: clock[0], ack_event=ack,
                deadline=10, sink=evidence,
            )
        clock, observer, evidence, ack = _observation_inputs()
        evidence.fail_event = 'backend_status_sample'
        with pytest.raises(OSError, match='injected evidence failure'):
            await runner.evaluate_observation(
                plan=plan, observer=observer, duration_s=1,
                steady=lambda: clock[0], ack_event=ack,
                deadline=10, sink=evidence,
            )

    asyncio.run(check())


def test_ros_graph_real_readiness_node_lifecycle_and_convergence():
    """Test backend permanence and temporary readiness-node lifecycle."""
    async def check():
        clock = [0.0]
        ack = asyncio.Event()
        ready = asyncio.Event()
        persistent = [
            ('b22_gui_observation_observer', '/'),
            ('mecanum_sim_backend', '/'),
            ('robot_state_publisher', '/'), ('ros_gz_bridge', '/'),
        ]
        schedule = [
            [persistent[0], persistent[2], persistent[3]],
            list(persistent),
            [*persistent, ('b2_server_scene_readiness', '/')],
            list(persistent),
        ]
        observer = _EvaluationObserver(
            clock, graph_schedule=schedule, readiness_event=ready,
            ack_event=ack,
        )
        evidence = _Sink()
        result = await runner.evaluate_observation(
            plan=SimpleNamespace(
                session_id='session-test', config_hash=guard.CONFIG_HASH,
            ), observer=observer, duration_s=0.2,
            steady=lambda: clock[0], ack_event=ack,
            readiness_complete_event=ready, deadline=10, sink=evidence,
        )
        assert result['observed_seconds'] >= 0.2
        inventories = [
            facts['participants'] for name, facts in evidence.records
            if name == 'ros_graph_inventory'
        ]
        assert any(
            ['mecanum_sim_backend', '/'] in item for item in inventories
        )
        assert any(
            ['b2_server_scene_readiness', '/'] in item
            for item in inventories
        )
        assert set(map(tuple, inventories[-1])) == set(persistent)

        clock_delayed = [0.0]
        ack_delayed = asyncio.Event()
        ready_delayed = asyncio.Event()
        ready_delayed.set()
        startup_without_backend = [
            persistent[0], persistent[2], persistent[3],
        ]
        delayed = _EvaluationObserver(
            clock_delayed,
            graph_schedule=[startup_without_backend] * 6 + [persistent],
            readiness_event=ready_delayed, ack_event=ack_delayed,
        )
        result = await runner.evaluate_observation(
            plan=SimpleNamespace(
                session_id='session-test', config_hash=guard.CONFIG_HASH,
            ), observer=delayed, duration_s=0.1,
            steady=lambda: clock_delayed[0], ack_event=ack_delayed,
            readiness_complete_event=ready_delayed,
            graph_convergence_s=1.0, deadline=10,
        )
        assert result['observed_seconds'] >= 0.1

        for options, message in (
            ({'graph_schedule': [[
                ('b22_gui_observation_observer', '/'),
                ('robot_state_publisher', '/'), ('ros_gz_bridge', '/'),
            ]], 'readiness_event': asyncio.Event()}, 'did not converge'),
            ({'duplicate_backend': True}, 'duplicate ROS graph'),
            ({'graph_schedule': [[
                ('b22_gui_observation_observer', '/'),
                ('mecanum_sim_backend', '/'),
                ('robot_state_publisher', '/'), ('ros_gz_bridge', '/'),
                ('b2_server_scene_readiness', '/'),
            ]]}, 'temporary readiness ROS node remained'),
        ):
            clock2 = [0.0]
            observer2 = _EvaluationObserver(clock2, **options)
            ready2 = options.get('readiness_event')
            if ready2 is not None:
                ready2.set()
            if 'temporary readiness' in message:
                ready2 = asyncio.Event()
                ready2.set()
            with pytest.raises(ObservationFailure, match=message):
                await runner.evaluate_observation(
                    plan=SimpleNamespace(
                        session_id='session-test',
                        config_hash=guard.CONFIG_HASH,
                    ), observer=observer2, duration_s=2,
                    steady=lambda: clock2[0], ack_event=asyncio.Event(),
                    readiness_complete_event=ready2,
                    graph_convergence_s=0.1, temporary_stale_s=0.1,
                    deadline=10,
                )

    asyncio.run(check())


def test_observation_deadline_and_cancellation_stop_the_loop():
    """Test steady deadline and task cancellation stop observer spinning."""
    async def check():
        plan = SimpleNamespace(
            session_id='session-test', config_hash=guard.CONFIG_HASH,
        )
        clock, observer, evidence, ack = _observation_inputs()
        with pytest.raises(ObservationFailure, match='deadline'):
            await runner.evaluate_observation(
                plan=plan, observer=observer, duration_s=60,
                steady=lambda: clock[0], ack_event=ack,
                deadline=0.2, sink=evidence,
            )
        clock, observer, evidence, ack = _observation_inputs()
        task = asyncio.create_task(runner.evaluate_observation(
            plan=plan, observer=observer, duration_s=60,
            steady=lambda: clock[0], ack_event=ack,
            deadline=100, sink=evidence,
        ))
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        calls = observer.calls
        await asyncio.sleep(0)
        assert observer.calls == calls

    asyncio.run(check())


def test_paused_mode_does_not_grade_scan_or_contact_as_pass():
    """Test paused observation records no scan or contact health verdict."""
    async def check():
        clock, observer, evidence, ack = _observation_inputs()
        result = await runner.evaluate_observation(
            plan=SimpleNamespace(
                session_id='session-test', config_hash=guard.CONFIG_HASH,
            ), observer=observer, duration_s=1,
            steady=lambda: clock[0], ack_event=ack,
            deadline=10, sink=evidence,
        )
        assert result['observed_seconds'] >= 1
        event_names = {name for name, _facts in evidence.records}
        assert not any('scan' in name.lower() for name in event_names)
        assert not any('contact' in name.lower() for name in event_names)

    asyncio.run(check())


class _FakeProcess:
    def __init__(self, pid, role):
        self.pid = pid
        self.role = role
        self.returncode = None
        self._exit = asyncio.Event()

    def finish(self, status=0):
        self.returncode = status
        self._exit.set()

    async def wait(self):
        await self._exit.wait()
        return self.returncode


class _FakeLauncher:
    def __init__(self, state, *, exit_role=None, exit_status=0):
        self.state = state
        self.exit_role = exit_role
        self.exit_status = exit_status
        self.processes = []
        self.signals = []

    async def start(self, command, _environment):
        text = tuple(str(item) for item in command)
        if 'parameter_bridge' in text:
            role = 'parameter_bridge'
        elif '-s' in text:
            role = 'server'
        elif '-g' in text:
            role = 'gui'
        elif 'robot_state_publisher' in text:
            role = 'robot_state_publisher'
        else:
            role = 'unknown'
        self.state['events'].append(f'spawn:{role}')
        process = _FakeProcess(10000 + len(self.processes), role)
        process.command = text
        self.processes.append(process)
        if self.exit_role == role:
            process.finish(self.exit_status)
        return process

    def group_alive(self, process):
        return process.returncode is None

    async def stop_group(self, process, sig):
        self.signals.append((process.role, sig))
        if sig == signal.SIGKILL:
            process.finish(-sig)


class _FakeReadiness:
    def __init__(self, state, *, wait_for_owner=False):
        self.state = state
        self.wait_for_owner = wait_for_owner
        self.abort_requested = asyncio.Event()

    def bind_environment(self, _environment):
        self.state['events'].append('bind-environment')

    async def server_scene(self, _plan, _process, _timeout):
        self.state['events'].append('scene-ready')

    async def gui_process_started(self, _plan, _process, _timeout):
        self.state['events'].append('gui-process-ready')

    async def owner_ack(self, _timeout):
        self.state['events'].append('owner-ack-requested')
        self.state['owner_ack_started'].set()
        if self.wait_for_owner:
            await asyncio.Future()
        return True, str(self.state['screenshot'])

    async def _read_stdin_line(self, _prompt):
        await self.abort_requested.wait()
        return 'OWNER_ABORT_GUI'


class _FakeObserver:
    def __init__(self, clock, state, *, emit_clock=True, emit_backend=True,
                 inhibit_after=None, exit_clock=False):
        self.clock = clock
        self.state = state
        self.emit_clock = emit_clock
        self.emit_backend = emit_backend
        self.inhibit_after = inhibit_after
        self.exit_clock = exit_clock
        self.events = __import__('collections').deque()
        self.calls = 0
        self.close_count = 0

    def start(self):
        self.state['events'].append('observer-start')

    def spin_once(self, _timeout_s=0.05):
        self.clock[0] += 0.05
        self.calls += 1
        now = self.clock[0]
        if self.emit_clock and not (
            self.exit_clock and self.calls > 3
        ):
            self.events.append((
                'clock', SimpleNamespace(sec=0, nanosec=0),
                now, int(now * 1e9),
            ))
        if self.emit_backend:
            inhibited = not (
                self.inhibit_after is not None
                and self.calls >= self.inhibit_after
            )
            message = SimpleNamespace(
                session_id='session-test', config_hash=guard.CONFIG_HASH,
                backend_instance_id=19,
                header=SimpleNamespace(frame_id='b2_training_arena'),
                status_sequence=self.calls, paused=True,
                actuator_inhibited=inhibited, fault_flags=0,
                applied_receipt_valid=False,
            )
            self.events.append(('backend', message, now, int(now * 1e9)))

    def node_inventory(self):
        return [
            ('b22_gui_observation_observer', '/'),
            ('mecanum_sim_backend', '/'),
            ('robot_state_publisher', '/'), ('ros_gz_bridge', '/'),
        ]

    def close(self):
        self.close_count += 1
        self.state['events'].append('observer-close')


class _FakeSink:
    def __init__(self, state, fail_event=None, fail_close=False):
        self.state = state
        self.fail_event = fail_event
        self.records = []
        self.events = []
        self.closed = 0
        self.fail_close = fail_close

    def record(self, event, facts):
        self.records.append((event, facts))
        self.events.append(event)
        self.state['events'].append(f'evidence:{event}')
        if event == self.fail_event:
            raise OSError(f'injected sink failure: {event}')

    def close(self):
        self.closed += 1
        self.state['events'].append('sink-close')
        if self.fail_close:
            raise OSError('injected sink close failure')


@dataclass(frozen=True)
class _FakePlan:
    session_id: str
    config_hash: str
    coordinator_ingress_instance_id: int
    environment: dict
    commands: tuple
    world_file: Path
    bridge_command: tuple
    gui_requested: bool = True


class _FakeSupervisor:
    def __init__(self, state, plan, launcher, readiness, evidence_sink, *,
                 fail_start=False, output_failure=False):
        self.state = state
        self.plan = plan
        self.launcher = launcher
        self.readiness = readiness
        self.evidence_sink = evidence_sink
        self.fail_start = fail_start
        self.output_failure = output_failure
        self.owned = []
        self.gui_opened = False

    async def start(self):
        self.state['events'].append('supervisor-start')
        self.readiness.bind_environment(self.plan.environment)
        for name, command in (
            ('parameter_bridge', self.plan.bridge_command),
            ('server', self.plan.commands[0]), ('gui', self.plan.commands[1]),
        ):
            process = await self.launcher.start(command, self.plan.environment)
            from mecanum_nav_bringup.local_training_process_supervisor import (
                ProcessRecord,
            )
            record = ProcessRecord(name, command, process.pid, process)
            self.owned.append(record)
            self.state['roles'][name] = process
        await self.readiness.server_scene(
            self.plan, self.state['roles']['server'], 30,
        )
        await self.readiness.gui_process_started(
            self.plan, self.state['roles']['gui'], 30,
        )
        accepted, screenshot = await self.readiness.owner_ack(60)
        assert accepted and screenshot == str(self.state['screenshot'])
        self.gui_opened = True
        self.state['owner_ack_complete'].set()
        if self.output_failure:
            async def fail_output():
                raise OSError('injected background output error')
            task = asyncio.create_task(fail_output())
            self.owned[-1].output_tasks = (task,)
            await asyncio.sleep(0)
        if self.fail_start:
            raise RuntimeError('injected partial startup failure')

    async def cleanup(self):
        self.state['events'].append('supervisor-cleanup')
        for process in self.state['roles'].values():
            process.finish(0)
        self.state['clock'][0] += self.state.get(
            'cleanup_clock_advance', 0.0,
        )


def _fake_runner_inputs(
    tmp_path, *, fail_start=False, sink_failure=None, packet_mutation=None,
    exit_role=None, exit_status=0, inhibit_after=None, output_failure=False,
    wait_for_owner=False, emit_clock=True, emit_backend=True,
    temporary_cleanup_failure=False, sink_close_failure=False,
    temporary_cleanup_clock_advance=0.0,
):
    """Build an actual-packet positive control with injected runtime edges."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    state = {
        'events': [], 'roles': {}, 'owner_ack_started': asyncio.Event(),
        'owner_ack_complete': asyncio.Event(),
        'screenshot': tmp_path / 'owner.png',
        'clock': [0.0], 'observer': None, 'sink': None,
        'supervisors': [], 'acquisitions': [], 'readiness': None,
        'temporary_cleanup_failure': temporary_cleanup_failure,
        'temporary_cleanup_clock_advance': temporary_cleanup_clock_advance,
        'cleanup_clock_advance': 0.0,
    }
    state['screenshot'].write_bytes(b'test-only screenshot placeholder')
    packet_bytes = BUNDLE_PACKET.read_bytes()
    packet = json.loads(packet_bytes)
    if packet_mutation is not None:
        packet_mutation(packet)
        packet_bytes = json.dumps(packet, sort_keys=True).encode()
    packet_path = tmp_path / 'packet.json'
    packet_path.write_bytes(packet_bytes)
    tool_hashes = guard.tool_hashes(TOOL_PATHS)
    approval = {
        'schema_id': 'b22_gui_observation_owner_approval/v1',
        'run_id': guard.RUN_ID,
        'packet_sha256': hashlib.sha256(packet_bytes).hexdigest(),
        'packet_commit': 'a' * 40,
        'production_source_pin': guard.PRODUCTION_SOURCE_PIN,
        'tool_sha256': tool_hashes,
    }
    approval_path = tmp_path / 'approval.json'
    approval_path.write_text(json.dumps(approval))
    evidence_root = tmp_path / 'evidence'
    evidence_root.mkdir()
    guard_path = tmp_path / 'test-acquisition.json'
    install_map = packet['installation']['file_sha256']
    templates = packet['commands_argv']['exact_templates']
    role_commands = {key: tuple(value) for key, value in templates.items()}
    state['readiness'] = _FakeReadiness(state, wait_for_owner=wait_for_owner)

    def build_plan(_gui, runtime_dir):
        state['events'].append('build-plan')
        world = runtime_dir / 'world.runtime.sdf'
        world.write_bytes(b'test-only runtime-bound world')
        params = runtime_dir / 'robot_state_publisher.params.yaml'
        params.write_text('test-only params')
        descriptor_path = runtime_dir / 'run_descriptor.json'
        descriptor_path.write_text('{}\n')
        descriptor = {
            'world_source_sha256': '1' * 64,
            'runtime_bound_world_sha256': guard.sha256_file(world),
            'coordinator_ingress_instance_id': 99,
            'robot_state_publisher_params_sha256': guard.sha256_file(params),
        }
        server = role_commands['server'][:-1] + (str(world),)
        plan = _FakePlan(
            'session-test', guard.CONFIG_HASH, 99,
            {'GZ_PARTITION': 'test_partition'},
            (server, role_commands['gui']), world,
            role_commands['parameter_bridge'],
        )
        return plan, {
            'description_share': tmp_path / 'description',
            'rl_share': tmp_path / 'rl',
            'bringup_share': tmp_path / 'bringup',
            'backend_prefix': tmp_path / 'backend',
            'interfaces_prefix': tmp_path / 'interfaces',
            'physics_engine_path': tmp_path / 'physics',
        }, descriptor, descriptor_path

    class RuntimeTemporaryDirectory:
        def __init__(self, **kwargs):
            self._context = runner.tempfile.TemporaryDirectory(**kwargs)
            self.name = self._context.name

        def cleanup(self):
            state['events'].append('temporary-directory-cleanup')
            self._context.cleanup()
            state['clock'][0] += state['temporary_cleanup_clock_advance']
            if state['temporary_cleanup_failure']:
                raise OSError('injected temporary directory cleanup failure')

    launcher = _FakeLauncher(
        state, exit_role=exit_role, exit_status=exit_status,
    )

    def supervisor_factory(plan, launcher, readiness, evidence_sink):
        supervisor = _FakeSupervisor(
            state, plan, launcher, readiness, evidence_sink,
            fail_start=fail_start, output_failure=output_failure,
        )
        state['supervisors'].append(supervisor)
        return supervisor

    def acquire(_path, payload):
        state['events'].append('guard-consume-fake')
        state['acquisitions'].append(payload)

    def sink_factory(_root, _run_id, _session):
        state['sink'] = _FakeSink(
            state, sink_failure, sink_close_failure,
        )
        return state['sink']

    def observer_factory():
        observer = _FakeObserver(
            state['clock'], state, emit_clock=emit_clock,
            emit_backend=emit_backend, inhibit_after=inhibit_after,
        )
        state['observer'] = observer
        return observer

    args = SimpleNamespace(
        gui=True, packet=str(packet_path), approval_file=str(approval_path),
        approved_commit='a' * 40, temp_root=str(tmp_path),
    )
    dependencies = {
        'run_id': RUN_TEST_ID,
        'preflight': lambda *_args: None,
        'stdin_isatty': True, 'environ': {}, 'exists': lambda _p: True,
        'verify_commit': lambda *_args: None,
        'install_preflight': lambda: install_map,
        'ros2_executable': packet['commands_argv']['exact_templates'][
            'robot_state_publisher'
        ][0],
        'build_plan': build_plan, 'acquire': acquire,
        'guard_path': guard_path, 'evidence_root': evidence_root,
        'sink_factory': sink_factory, 'launcher': launcher,
        'readiness': state['readiness'],
        'observer_factory': observer_factory,
        'supervisor_factory': supervisor_factory,
        'process_identity_reader': lambda pid: {
            'pid': pid, 'process_group_id': pid,
            'session_id': pid, 'start_ticks': 1,
        },
        'runner_process_identity': lambda _pid: {
            'pid': 7, 'process_group_id': 7,
            'session_id': 7, 'start_ticks': 10,
        },
        'host_identity': lambda: {
            'hostname': 'test-host', 'boot_id': 'test-boot',
        },
        'monotonic_ns': lambda: int(state['clock'][0] * 1e9),
        'monotonic': lambda: state['clock'][0],
        'temporary_directory_factory': RuntimeTemporaryDirectory,
    }
    return args, dependencies, state


def test_actual_packet_positive_control_reaches_fake_acquisition(tmp_path):
    """Test bundle packet preflight reaches injected acquisition."""
    args, dependencies, state = _fake_runner_inputs(tmp_path)
    result = asyncio.run(runner._run(args, dependencies=dependencies))
    assert state['acquisitions'][0]['run_id'] == RUN_TEST_ID
    assert state['acquisitions'][0]['production_source_pin'] == (
        guard.PRODUCTION_SOURCE_PIN
    )
    assert state['events'].index('guard-consume-fake') < next(
        index for index, event in enumerate(state['events'])
        if event.startswith('spawn:')
    )
    assert result == 'PASS'
    final = [
        facts for name, facts in state['sink'].records
        if name == 'final_status'
    ]
    assert final[-1]['status'] == 'PASS'
    assert state['observer'].close_count == 1
    assert state['sink'].closed == 1
    assert state['events'].index('temporary-directory-cleanup') < next(
        index for index, event in enumerate(state['events'])
        if event == 'evidence:final_status'
    )


def test_final_evidence_follows_cleanup_and_records_cleanup_failure(tmp_path):
    """Test final PASS follows cleanup and cleanup failure is final FAIL."""
    args, dependencies, state = _fake_runner_inputs(tmp_path / 'pass')
    result = asyncio.run(runner._run(args, dependencies=dependencies))
    assert result == 'PASS'
    assert state['events'].index('temporary-directory-cleanup') < next(
        index for index, event in enumerate(state['events'])
        if event == 'evidence:final_status'
    )

    args, dependencies, state = _fake_runner_inputs(
        tmp_path / 'tmp-fail', temporary_cleanup_failure=True,
    )
    result = asyncio.run(runner._run(args, dependencies=dependencies))
    final = [
        facts for name, facts in state['sink'].records
        if name == 'final_status'
    ][-1]
    assert result == final['status'] == 'FAIL'
    assert final['observation_status'] == 'PASS'
    assert any('runtime_dir_cleanup:OSError' in item
               for item in final['cleanup_errors'])


def test_cleanup_deadline_and_evidence_failures_cannot_return_pass(tmp_path):
    """Test cleanup timeout and sink write/close errors invalidate PASS."""
    args, dependencies, state = _fake_runner_inputs(tmp_path / 'deadline')
    state['cleanup_clock_advance'] = 61
    result = asyncio.run(runner._run(args, dependencies=dependencies))
    assert result == 'FAIL'
    final = [
        facts for name, facts in state['sink'].records
        if name == 'final_status'
    ][-1]
    assert 'cleanup_deadline_exceeded' in final['cleanup_errors']

    args, dependencies, state = _fake_runner_inputs(
        tmp_path / 'temp-deadline', temporary_cleanup_clock_advance=61,
    )
    assert asyncio.run(runner._run(args, dependencies=dependencies)) == 'FAIL'
    final = [
        facts for name, facts in state['sink'].records
        if name == 'final_status'
    ][-1]
    assert 'cleanup_deadline_exceeded' in final['cleanup_errors']

    args, dependencies, state = _fake_runner_inputs(
        tmp_path / 'write-fail', sink_failure='final_status',
    )
    assert asyncio.run(runner._run(args, dependencies=dependencies)) == 'FAIL'
    assert any(name == 'evidence_incomplete'
               for name, _facts in state['sink'].records)

    args, dependencies, state = _fake_runner_inputs(
        tmp_path / 'close-fail', sink_close_failure=True,
    )
    assert asyncio.run(runner._run(args, dependencies=dependencies)) == 'FAIL'
    assert any(name == 'evidence_incomplete'
               for name, _facts in state['sink'].records)


def test_malformed_packet_stops_before_fake_acquisition_or_spawn(tmp_path):
    """Test missing packet fields block before injected side effects."""
    def remove_source_pin(packet):
        del packet['repository']['production_source_pin']

    args, dependencies, state = _fake_runner_inputs(
        tmp_path, packet_mutation=remove_source_pin,
    )
    with pytest.raises(guard.GuardError, match='repository fields'):
        asyncio.run(runner._run(args, dependencies=dependencies))
    assert not state['acquisitions']
    assert not any(event.startswith('spawn:') for event in state['events'])


def test_wrong_hash_and_command_contract_block_preconsume(tmp_path):
    """Test install hash or launch argv mismatch blocks capacity use."""
    args, dependencies, state = _fake_runner_inputs(tmp_path)
    dependencies['install_preflight'] = lambda: {'wrong': '0' * 64}
    with pytest.raises(
        ObservationFailure, match='installed file fingerprints',
    ):
        asyncio.run(runner._run(args, dependencies=dependencies))
    assert not state['acquisitions']
    args, dependencies, state = _fake_runner_inputs(tmp_path / 'argv')
    original = dependencies['build_plan']

    def wrong_plan(gui, runtime_dir):
        plan, paths, descriptor, path = original(gui, runtime_dir)
        return (
            _FakePlan(
                plan.session_id, plan.config_hash,
                plan.coordinator_ingress_instance_id, plan.environment,
                (plan.commands[0], ('gz', 'sim', '-g')),
                plan.world_file, plan.bridge_command,
            ), paths, descriptor, path,
        )
    dependencies['build_plan'] = wrong_plan
    with pytest.raises(ObservationFailure, match='GUI argv'):
        asyncio.run(runner._run(args, dependencies=dependencies))
    assert not state['acquisitions']


def test_gui_exit_and_partial_start_fail_and_cleanup(tmp_path):
    """Test role exits and partial startup failures clean up as FAIL."""
    for failure in (
        {'exit_role': 'robot_state_publisher'},
        {'exit_role': 'parameter_bridge'},
        {'exit_role': 'server'},
        {'exit_role': 'gui'},
        {'fail_start': True},
    ):
        run_dir = tmp_path / str(len(list(tmp_path.iterdir())))
        run_dir.mkdir()
        args, dependencies, state = _fake_runner_inputs(run_dir, **failure)
        result = asyncio.run(runner._run(args, dependencies=dependencies))
        assert result == 'FAIL'
        assert 'supervisor-cleanup' in state['events']
        assert state['observer'].close_count == 1
        assert state['sink'].closed == 1
        assert any(
            facts['status'] == 'FAIL'
            for name, facts in state['sink'].records if name == 'final_status'
        )


def test_inhibit_loss_while_owner_ack_waits_cleans_and_fails(tmp_path):
    """Test inhibit loss during Owner wait fails before acknowledgment."""
    args, dependencies, state = _fake_runner_inputs(
        tmp_path, wait_for_owner=True, inhibit_after=4,
    )
    result = asyncio.run(runner._run(args, dependencies=dependencies))
    assert result == 'FAIL'
    assert 'owner-ack-requested' in state['events']
    assert 'supervisor-cleanup' in state['events']
    assert not state['owner_ack_complete'].is_set()
    assert state['observer'].close_count == 1


def test_background_sink_failure_fails_run_and_cleanup_continues(tmp_path):
    """Test sink error fails the run while cleanup closes owned resources."""
    args, dependencies, state = _fake_runner_inputs(
        tmp_path, sink_failure='backend_status_sample',
    )
    result = asyncio.run(runner._run(args, dependencies=dependencies))
    assert result == 'FAIL'
    assert 'supervisor-cleanup' in state['events']
    assert state['observer'].close_count == 1
    assert state['sink'].closed == 1


def test_background_output_task_failure_is_not_swallowed(tmp_path):
    """Test supervisor-drained output task exception reaches run outcome."""
    args, dependencies, state = _fake_runner_inputs(
        tmp_path, output_failure=True,
    )
    result = asyncio.run(runner._run(args, dependencies=dependencies))
    assert result == 'FAIL'
    assert any(
        'background_output_failure' in error
        for name, facts in state['sink'].records
        if name == 'final_status'
        for error in facts['cleanup_errors']
    ) or any(
        name == 'background_output_failure'
        for name, _facts in state['sink'].records
    )
    assert 'supervisor-cleanup' in state['events']


def test_owner_cancel_is_aborted_by_owner_in_final_run_evidence(tmp_path):
    """Test direct TTY abort remains ABORTED_BY_OWNER in final status."""
    args, dependencies, state = _fake_runner_inputs(tmp_path)
    dependencies['readiness'].abort_requested.set()
    result = asyncio.run(runner._run(args, dependencies=dependencies))
    assert result == 'ABORTED_BY_OWNER'
    final = [
        facts for name, facts in state['sink'].records
        if name == 'final_status'
    ]
    assert final[-1]['status'] == 'ABORTED_BY_OWNER'
    assert any(name == 'owner_abort' for name, _facts in state['sink'].records)
    assert 'supervisor-cleanup' in state['events']


def test_owner_token_without_normal_gui_exit_does_not_mask_crash(tmp_path):
    """Test an abnormal GUI exit remains FAIL even after Owner abort token."""
    args, dependencies, state = _fake_runner_inputs(
        tmp_path, exit_role='gui', exit_status=17,
    )
    dependencies['readiness'].abort_requested.set()
    result = asyncio.run(runner._run(args, dependencies=dependencies))
    assert result == 'FAIL'
    final = [
        facts for name, facts in state['sink'].records
        if name == 'final_status'
    ]
    assert final[-1]['status'] == 'FAIL'


def test_startup_cancellation_joins_observer_and_process_tasks(tmp_path):
    """Test startup cancellation joins observer and owned tasks."""
    async def check():
        args, dependencies, state = _fake_runner_inputs(
            tmp_path, wait_for_owner=True,
        )
        task = asyncio.create_task(
            runner._run(args, dependencies=dependencies),
        )
        await asyncio.wait_for(state['owner_ack_started'].wait(), timeout=1)
        task.cancel()
        result = await asyncio.wait_for(task, timeout=2)
        assert result == 'FAIL'
        assert state['observer'].close_count == 1
        assert 'supervisor-cleanup' in state['events']
        pending = [
            other for other in asyncio.all_tasks()
            if other is not asyncio.current_task() and not other.done()
        ]
        assert pending == []

    asyncio.run(check())


def test_runner_without_clock_times_out_and_records_failure(tmp_path):
    """Test missing clock fails and cleans up owned resources."""
    args, dependencies, state = _fake_runner_inputs(
        tmp_path, emit_clock=False,
    )
    # A clockless observer fails after the packet's bounded server readiness.
    result = asyncio.run(runner._run(args, dependencies=dependencies))
    assert result == 'FAIL'
    assert state['observer'].close_count == 1
    assert 'supervisor-cleanup' in state['events']


def test_runner_context_closed_once_after_observation_timeout(tmp_path):
    """Test observation timeout is a failure with one observer close."""
    args, dependencies, state = _fake_runner_inputs(tmp_path)
    dependencies['monotonic'] = lambda: state['clock'][0]
    # Stop simulated steady progress after acknowledgment to exercise deadline.
    original = dependencies['observer_factory']

    def held_observer():
        observer = original()
        base_spin = observer.spin_once

        def spin(timeout):
            if state['owner_ack_complete'].is_set():
                # Advance beyond the shared post-consume deadline.
                state['clock'][0] = 241.0
                observer.calls += 1
                now = state['clock'][0]
                observer.events.append((
                    'clock', SimpleNamespace(sec=0, nanosec=0),
                    now, int(now * 1e9),
                ))
                message = SimpleNamespace(
                    session_id='session-test', config_hash=guard.CONFIG_HASH,
                    backend_instance_id=19,
                    header=SimpleNamespace(frame_id='b2_training_arena'),
                    status_sequence=observer.calls, paused=True,
                    actuator_inhibited=True, fault_flags=0,
                    applied_receipt_valid=False,
                )
                observer.events.append((
                    'backend', message, now, int(now * 1e9),
                ))
            else:
                base_spin(timeout)
        observer.spin_once = spin
        return observer

    dependencies['observer_factory'] = held_observer
    # The shared fake clock hits the hard cap without a worker thread.
    result = asyncio.run(runner._run(args, dependencies=dependencies))
    assert result == 'FAIL'
    assert state['observer'].close_count == 1


def test_fallback_cleanup_escalates_and_is_idempotent():
    """Test bounded INT/TERM/KILL escalation preserves owned records."""
    class Process:
        pid = 4001
        returncode = None

    class Launcher:
        def __init__(self):
            self.calls = []
            self.live = True

        def group_alive(self, _process):
            return self.live

        async def stop_group(self, _process, sig):
            self.calls.append(sig)
            if sig == signal.SIGKILL:
                self.live = False

    record = SimpleNamespace(
        name='owned-server', pid=4001, process=Process(),
    )
    launcher = Launcher()
    errors = []
    now = [0.0]

    async def sleep(duration):
        now[0] += duration

    async def check():
        await runner._fallback_cleanup(
            launcher, [record], None, errors, deadline=10,
            steady=lambda: now[0], sleep=sleep,
            escalation_grace=(0.1, 0.1, 0.1),
        )
        assert launcher.calls == [
            signal.SIGINT, signal.SIGTERM, signal.SIGKILL,
        ]
        assert errors == []
        await runner._fallback_cleanup(
            launcher, [record], None, errors, deadline=10,
            steady=lambda: now[0], sleep=sleep,
            escalation_grace=(0.1, 0.1, 0.1),
        )
        assert launcher.calls == [
            signal.SIGINT, signal.SIGTERM, signal.SIGKILL,
        ]
        assert record.pid == 4001

    asyncio.run(check())


def test_shared_cleanup_window_is_fixed_and_wrapper_joins_cancelled_base():
    """Test wrapped cleanup uses one deadline and joins cancellation paths."""
    async def check():
        now = [0.0]
        window = runner.CleanupWindow(0.0, 300.0, lambda: now[0])
        first = window.begin()
        now[0] = 55.0
        assert window.begin() == first == 60.0

        process = _FakeProcess(8401, 'server')
        record = SimpleNamespace(
            name='server', pid=process.pid, process=process,
        )

        class Launcher:
            def __init__(self):
                self.signals = []

            def group_alive(self, proc):
                return proc.returncode is None

            async def stop_group(self, proc, sig):
                self.signals.append(sig)
                proc.finish(-sig)

        launcher = Launcher()

        class Base:
            def __init__(self, **_kwargs):
                self.owned = [record]
                self.launcher = launcher
                self.evidence_sink = None
                self.waiter = None

            async def cleanup(self):
                self.waiter = asyncio.current_task()
                await asyncio.Future()

        errors = []
        wrapped = runner.ResilientSupervisor(
            Base, cleanup_window=runner.CleanupWindow(
                0.0, 300.0, lambda: now[0],
            ), cleanup_errors=errors,
            cleanup_options={
                'sleep': asyncio.sleep,
                'escalation_grace': (0, 0, 0),
            },
        )
        task = asyncio.create_task(wrapped.cleanup())
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert wrapped.waiter.done() and wrapped.waiter.cancelled()
        assert launcher.signals == [signal.SIGINT]
        assert not [
            item for item in asyncio.all_tasks()
            if item is not asyncio.current_task() and not item.done()
        ]

    asyncio.run(check())


def test_cleanup_window_deadline_does_not_renew_after_exception():
    """Test base cleanup failure near deadline cannot grant another budget."""
    async def check():
        now = [0.0]
        window = runner.CleanupWindow(0.0, 300.0, lambda: now[0])
        process = _FakeProcess(8402, 'server')
        record = SimpleNamespace(name='server', pid=8402, process=process)

        class Launcher:
            def group_alive(self, _process):
                return True

            async def stop_group(self, _process, _sig):
                now[0] = 60.0

        class Base:
            def __init__(self, **_kwargs):
                self.owned = [record]
                self.launcher = Launcher()
                self.evidence_sink = None
                self.calls = 0

            async def cleanup(self):
                self.calls += 1
                if self.calls == 1:
                    now[0] = 59.0
                raise RuntimeError('near-deadline cleanup failure')

        errors = []
        wrapped = runner.ResilientSupervisor(
            Base, cleanup_window=window, cleanup_errors=errors,
            cleanup_options={'escalation_grace': (5, 3, 3)},
        )
        with pytest.raises(ObservationFailure, match='residue'):
            await wrapped.cleanup()
        assert window.begin() == 60.0
        assert now[0] == 60.0
        assert any('base_cleanup:RuntimeError' in item for item in errors)
        assert any('residue' in item for item in errors)
        with pytest.raises(ObservationFailure, match='residue'):
            await wrapped.cleanup()
        assert window.begin() == 60.0
        assert now[0] == 60.0

    asyncio.run(check())


def test_launcher_retains_ownership_before_identity_or_evidence_failure():
    """Test ownership survives identity and evidence callback failures."""
    class Delegate(_FakeLauncher):
        pass

    async def check():
        state = {'events': []}
        delegate = Delegate(state)
        launcher = runner.TrackedProcessLauncher(
            delegate, identity_reader=lambda _pid: (_ for _ in ()).throw(
                OSError('proc read failed')
            ),
        )
        with pytest.raises(OSError, match='proc read failed'):
            await launcher.start(('gz', 'sim', '-s'), {})
        assert len(launcher.records) == 1
        assert launcher.records[0].identity_error.startswith('OSError')
        await runner._fallback_cleanup(
            launcher, launcher.records, None, [],
            deadline=10,
            escalation_grace=(0, 0, 0),
        )
        assert len(launcher.records) == 1

        delegate = Delegate(state)
        launcher = runner.TrackedProcessLauncher(
            delegate, on_start=lambda *_args: (_ for _ in ()).throw(
                OSError('evidence callback failed')
            ),
            identity_reader=lambda pid: {
                'pid': pid, 'process_group_id': pid,
                'session_id': pid, 'start_ticks': 1,
            },
        )
        with pytest.raises(OSError, match='evidence callback'):
            await launcher.start(('gz', 'sim', '-s'), {})
        assert len(launcher.records) == 1
        assert launcher.records[0].identity is not None
        await runner._fallback_cleanup(
            launcher, launcher.records, None, [],
            deadline=10,
            escalation_grace=(0, 0, 0),
        )
        for waiter in launcher.waiters.values():
            if not waiter.done():
                waiter.cancel()
        await asyncio.gather(
            *launcher.waiters.values(), return_exceptions=True,
        )

    asyncio.run(check())


def test_cleanup_unknown_identity_is_fail_closed_and_does_not_drop_record():
    """Test unknown group identity remains recorded instead of guessed away."""
    process = _FakeProcess(7001, 'unknown')
    record = SimpleNamespace(
        name='unknown-group', pid=7001, process=process,
    )

    class Launcher:
        def group_alive(self, _process):
            raise OSError('cannot inspect process group')

        async def stop_group(self, _process, _sig):
            raise OSError('must not signal unknown group')

    errors = []
    asyncio.run(runner._fallback_cleanup(
        Launcher(), [record], None, errors,
        deadline=10,
        escalation_grace=(0, 0, 0),
    ))
    assert any(
        error.startswith('residue_unknown:unknown-group') for error in errors
    )
    assert record.process is process


def test_runtime_status_and_observation_contract_values():
    """Test exact caps and final status classifications remain fail closed."""
    runner.enforce_runtime_cap(10.0, 249.9)
    with pytest.raises(ObservationFailure, match='240 s'):
        runner.enforce_runtime_cap(10.0, 250.1)
    assert runner.classify_final_status(True, False, []) == 'PASS'
    assert runner.classify_final_status(False, False, []) == 'FAIL'
    assert runner.classify_final_status(False, True, []) == 'ABORTED_BY_OWNER'
    assert runner.classify_final_status(True, False, ['residue']) == 'FAIL'
