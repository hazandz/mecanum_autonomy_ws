"""Process-isolated readiness tests using child-side middleware fakes."""
import asyncio
import hashlib
import json
import os
import signal
import sys
import time
import uuid
from pathlib import Path
from types import SimpleNamespace

from mecanum_nav_bringup import local_training_process_supervisor as supervisor
from mecanum_nav_bringup.local_training_launch_contract import LaunchPlan
from mecanum_nav_bringup.local_training_process_supervisor import (
    LocalTrainingProcessSupervisor,
    RclpyReadiness,
)
from mecanum_nav_bringup.local_training_readiness_worker import (
    REQUEST_SCHEMA,
    canonical_request_bytes,
    run_worker,
    strict_json_loads,
    validate_request,
)

import pytest


CONFIG_HASH = 'a' * 64
MANIFEST_HASH = 'b' * 64
SESSION = '9f5df3be-6fc3-4c2a-a08c-4c39f1f76672'


class Sink:
    """Collect readiness evidence or fail at one selected event."""

    def __init__(self, fail_event=None):
        """Initialize the in-memory sink."""
        self.events = []
        self.fail_event = fail_event

    def record(self, event, facts):
        """Append one event unless the configured fault is selected."""
        if event == self.fail_event:
            raise OSError('injected evidence sink failure')
        self.events.append((event, facts))


class ServerProcess:
    """Represent a live parent-owned simulator process in unit tests."""

    pid = 99001
    returncode = None


class ChunkStream:
    """Provide fixed pipe bytes to the production protocol drainer."""

    def __init__(self, chunks):
        """Keep byte chunks queued for asynchronous reads."""
        self._chunks = list(chunks)

    async def read(self, _size):
        """Return the next chunk or EOF."""
        return self._chunks.pop(0) if self._chunks else b''


def make_plan():
    """Build a valid immutable launch-plan binding for the worker tests."""
    return LaunchPlan(
        True, Path('/tmp/world.sdf'), Path('/tmp/gui.config'),
        Path('/tmp/config.json'), SESSION, CONFIG_HASH, MANIFEST_HASH, 17,
        (('gz', 'sim', '-s', '/tmp/world.sdf'),),
        {'GZ_PARTITION': 'mecanum_b2_testpartition', 'ROS_DOMAIN_ID': '83'},
    )


def install_child_middleware_fakes(root, **values):
    """Create import shims loaded only by the worker subprocess."""
    root.mkdir()
    code = r"""
import os, sys, time, types

def record(event):
    path = os.environ.get('FAKE_TRACE')
    if path:
        with open(path, 'a', encoding='utf-8') as stream:
            stream.write(event + '\n')

def module(name):
    value = types.ModuleType(name)
    sys.modules[name] = value
    return value

rclpy = module('rclpy')
context_module = module('rclpy.context')
executors_module = module('rclpy.executors')
node_module = module('rclpy.node')

class Context:
    def __init__(self): self.initialized = False; self.closed = False
    def init(self, args=None):
        if os.environ.get('FAKE_CONTEXT_INIT_FAIL') == '1':
            raise RuntimeError('injected context init failure')
        self.initialized = True
        record('context.init')
    def shutdown(self):
        self.closed = True
        record('context.shutdown')
context_module.Context = Context

class Status:
    def __init__(self):
        self.header = types.SimpleNamespace(
            frame_id=os.environ.get('FAKE_WORLD', 'b2_training_arena'))
        self.session_id = os.environ.get(
            'FAKE_SESSION', '9f5df3be-6fc3-4c2a-a08c-4c39f1f76672')
        self.config_hash = os.environ.get('FAKE_CONFIG', 'a' * 64)
        self.backend_instance_id = int(os.environ.get('FAKE_BACKEND', '9'))
        self.status_sequence = int(os.environ.get('FAKE_SEQUENCE', '1'))
        self.fault_flags = int(os.environ.get('FAKE_FAULT', '0'))
        self.actuator_inhibited = os.environ.get('FAKE_INHIBITED', '1') == '1'

class Node:
    def __init__(self, name, *, context):
        assert name == 'b2_server_scene_readiness' and context.initialized
        self.context = context; self.callback = None
    def create_subscription(self, _type, topic, callback, qos):
        assert topic == '/mecanum/local_training/backend_state' and qos == 50
        record('subscription.create')
        if os.environ.get('FAKE_SUBSCRIPTION_FAIL') == '1':
            raise RuntimeError('injected status subscription failure')
        self.callback = callback
        return object()
    def destroy_subscription(self, _sub):
        record('subscription.destroy')
        return None
    def destroy_node(self):
        record('node.destroy')
        return True
node_module.Node = Node

class Executor:
    def __init__(self, *, context):
        self.context = context
        self.node = None
        self.closed = False

    def add_node(self, node):
        assert node.context is self.context
        self.node = node
        record('executor.add_node')
        return True
    def spin_once(self, *, timeout_sec):
        if self.node.callback is not None:
            self.node.callback(Status())
            self.node.callback = None
        else:
            time.sleep(min(timeout_sec, 0.005))
    def remove_node(self, node):
        record('executor.remove_node')
        return node is self.node
    def shutdown(self, timeout_sec=None):
        self.closed = True
        record('executor.shutdown')
        return True
executors_module.SingleThreadedExecutor = Executor

interfaces = module('mecanum_nav_rl_interfaces')
interfaces.__path__ = []
messages = module('mecanum_nav_rl_interfaces.msg')
messages.SimulationContactState = Status

gz = module('gz'); gz.__path__ = []
msgs = module('gz.msgs10'); msgs.__path__ = []
empty_module = module('gz.msgs10.empty_pb2')
scene_module = module('gz.msgs10.scene_pb2')
class Empty: pass
empty_module.Empty = Empty
class Model:
    def __init__(self, name): self.name = name; self.model = []
class Scene:
    def __init__(self):
        mode = os.environ.get('FAKE_SCENE', 'match')
        self.name = 'other_world' if mode == 'world' else 'b2_training_arena'
        count = (
            0 if mode == 'missing'
            else 2 if mode == 'duplicate' else 1
        )
        self.model = [Model('mecanum_b2') for _ in range(count)]
scene_module.Scene = Scene
transport = module('gz.transport13'); transport.__path__ = []
class TransportNode:
    def request(
        self, service, request, request_type, response_type, timeout_ms,
    ):
        assert service == '/world/b2_training_arena/scene/info'
        delay = float(os.environ.get('FAKE_SCENE_DELAY', '0'))
        if delay:
            time.sleep(delay)
        return True, Scene()
transport.Node = TransportNode
"""
    (root / 'sitecustomize.py').write_text(code, encoding='utf-8')


def readiness_with_child_fakes(
    monkeypatch, tmp_path, sink_fail_event=None, **child_values,
):
    """Bind an isolated middleware-fake environment to the default client."""
    fake_root = tmp_path / 'child-fakes'
    install_child_middleware_fakes(fake_root)
    monkeypatch.setenv(
        'PYTHONPATH',
        str(fake_root) + os.pathsep + os.environ.get('PYTHONPATH', ''),
    )
    for key, value in child_values.items():
        monkeypatch.setenv(key, str(value))
    monkeypatch.setattr(
        supervisor, 'load_bound_config',
        lambda _path: (None, CONFIG_HASH, MANIFEST_HASH, 'B2_SOAK_V1'),
    )
    readiness = RclpyReadiness()
    sink = Sink(fail_event=sink_fail_event)
    LocalTrainingProcessSupervisor(
        plan=make_plan(), launcher=object(), readiness=readiness,
        evidence_sink=sink,
    )
    return readiness, sink


def test_request_is_canonical_strict_and_binds_domain_partition():
    """Validate canonical binding, field types and duplicate-key rejection."""
    request = {
        'schema_id': REQUEST_SCHEMA,
        'request_id': str(uuid.uuid4()),
        'session_id': SESSION,
        'config_hash': CONFIG_HASH,
        'asset_manifest_sha256': MANIFEST_HASH,
        'coordinator_ingress_instance_id': 17,
        'world_id': 'b2_training_arena',
        'model_id': 'mecanum_b2',
        'gz_partition': 'mecanum_b2_testpartition',
        'ros_domain_id': '83',
        'deadline_monotonic_ns': (
            time.monotonic_ns() + 1_000_000_000
        ),
    }
    raw = canonical_request_bytes(request)
    assert strict_json_loads(raw) == request
    env = {'GZ_PARTITION': request['gz_partition'], 'ROS_DOMAIN_ID': '83'}
    assert validate_request(request, env) is request
    with pytest.raises(ValueError, match='duplicate'):
        strict_json_loads(b'{"x":1,"x":2}')
    with pytest.raises(ValueError, match='uint64'):
        validate_request(
            {**request, 'coordinator_ingress_instance_id': True}, env,
        )


def test_default_parent_client_uses_isolated_production_worker(
    monkeypatch, tmp_path,
):
    """Use the default subprocess client and installed worker module."""
    readiness, sink = readiness_with_child_fakes(monkeypatch, tmp_path)
    before = os.environ.get('GZ_PARTITION')
    asyncio.run(readiness.server_scene(make_plan(), ServerProcess(), 2.0))
    names = [name for name, _ in sink.events]
    assert 'readiness_worker_spawned' in names
    assert 'readiness_worker_parent_validated' in names
    assert 'server_scene_ready' not in names
    worker_event = next(
        facts for name, facts in sink.events
        if name == 'readiness_worker_spawned'
    )
    assert worker_event['worker_identity']['pid'] != os.getpid()
    assert readiness._residue == 'NONE'
    assert os.environ.get('GZ_PARTITION') == before
    protocol = [facts['record']['event'] for name, facts in sink.events
                if name == 'readiness_worker_event']
    assert protocol == [
        'worker_started', 'status_wait_started', 'status_matched',
        'scene_query_started', 'scene_query_finished', 'worker_result',
    ]
    result = next(facts['record']['facts'] for name, facts in sink.events
                  if name == 'readiness_worker_event'
                  and facts['record']['event'] == 'worker_result')
    assert result['verdict'] == 'READY'
    assert result['facts']['status']['backend_instance_id'] == 9
    assert result['facts']['scene']['matching_model_count'] == 1


def test_slow_child_query_does_not_block_parent_ticker(monkeypatch, tmp_path):
    """Keep event-loop health polling live during slow child scene queries."""
    readiness, _sink = readiness_with_child_fakes(
        monkeypatch, tmp_path, FAKE_SCENE_DELAY='0.18',
    )

    async def exercise():
        """Run one readiness attempt alongside a 10 ms health ticker."""
        ticks = []
        stop = asyncio.Event()

        async def ticker():
            """Record the live event-loop cadence until readiness completes."""
            while not stop.is_set():
                ticks.append(time.monotonic())
                await asyncio.sleep(0.01)
        task = asyncio.create_task(ticker())
        await readiness.server_scene(make_plan(), ServerProcess(), 2.0)
        await asyncio.sleep(0.02)
        stop.set()
        await task
        return max(b-a for a, b in zip(ticks, ticks[1:]))
    max_gap = asyncio.run(exercise())
    assert max_gap < 0.08


def test_parent_deadline_is_detected_before_slow_scene_query_returns(
    monkeypatch, tmp_path,
):
    """Detect the parent deadline while the child query remains blocked."""
    readiness, sink = readiness_with_child_fakes(
        monkeypatch, tmp_path, FAKE_SCENE_DELAY='0.35',
    )
    with pytest.raises(TimeoutError, match='parent deadline'):
        asyncio.run(readiness.server_scene(make_plan(), ServerProcess(), 0.12))
    failure = next(facts for name, facts in sink.events
                   if name == 'readiness_failure_detected')
    query_finished = next(
        facts for name, facts in sink.events
        if name == 'readiness_worker_event'
        and facts['record']['event'] == 'scene_query_finished'
    )
    assert failure['detection_monotonic_ns'] < query_finished[
        'parent_received_monotonic_ns'
    ]
    assert readiness._residue == 'NONE'


@pytest.mark.parametrize('key,value', [
    ('FAKE_WORLD', 'other_world'),
    ('FAKE_SESSION', 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'),
    ('FAKE_CONFIG', 'c' * 64),
    ('FAKE_BACKEND', '0'),
    ('FAKE_SEQUENCE', '0'),
    ('FAKE_FAULT', '1'),
    ('FAKE_INHIBITED', '0'),
])
def test_status_mismatch_never_returns_ready(
    monkeypatch, tmp_path, key, value,
):
    """Reject every unhealthy or foreign backend status binding."""
    readiness, sink = readiness_with_child_fakes(
        monkeypatch, tmp_path, **{key: value},
    )
    with pytest.raises((RuntimeError, TimeoutError)):
        asyncio.run(readiness.server_scene(make_plan(), ServerProcess(), 0.15))
    results = [facts['record']['facts'] for name, facts in sink.events
               if name == 'readiness_worker_event'
               and facts['record']['event'] == 'worker_result']
    assert not results or results[0]['verdict'] != 'READY'


@pytest.mark.parametrize('scene_mode', ['world', 'missing', 'duplicate'])
def test_scene_mismatch_never_returns_ready(monkeypatch, tmp_path, scene_mode):
    """Reject a wrong world and missing or duplicate robot model."""
    readiness, sink = readiness_with_child_fakes(
        monkeypatch, tmp_path, FAKE_SCENE=scene_mode,
    )
    with pytest.raises(RuntimeError, match='readiness worker'):
        asyncio.run(readiness.server_scene(make_plan(), ServerProcess(), 1.0))
    result = next(facts['record']['facts'] for name, facts in sink.events
                  if name == 'readiness_worker_event'
                  and facts['record']['event'] == 'worker_result')
    assert result['verdict'] == 'FAIL'


def test_supervisor_binds_evidence_sink_without_changing_ack_contract():
    """Bind the sink while retaining canonical GUI acknowledgment methods."""
    readiness = RclpyReadiness()
    sink = Sink()
    LocalTrainingProcessSupervisor(
        plan=make_plan(), launcher=object(), readiness=readiness,
        evidence_sink=sink,
    )
    assert readiness._evidence_sink is sink
    assert asyncio.iscoroutinefunction(readiness.owner_ack)


def test_identity_mismatch_never_signals_worker_group():
    """Refuse to signal a reused worker PID or process-group identity."""
    sent = []
    baseline = {
        'pid': 123, 'process_group_id': 123, 'session_id': 123,
        'start_ticks': 456,
    }
    readiness = RclpyReadiness(
        identity_reader=lambda _pid: {**baseline, 'start_ticks': 457},
        signal_group=lambda *args: sent.append(args),
    )
    readiness._worker = SimpleNamespace(pid=123, returncode=None)
    readiness._worker_identity = baseline
    sent_ok, reason = readiness._verified_signal(signal.SIGINT)
    assert not sent_ok
    assert reason == 'identity_mismatch_or_pid_reuse'
    assert sent == []


def test_worker_module_import_has_no_middleware_participant():
    """Importing the worker module must stay free of middleware imports."""
    import mecanum_nav_bringup.local_training_readiness_worker as worker
    assert callable(worker.validate_request)
    assert 'rclpy' not in sys.modules
    assert 'gz.transport13' not in sys.modules


def test_failure_sink_does_not_erase_worker_ownership():
    """Keep worker ownership explicit when evidence recording fails."""
    readiness = RclpyReadiness()
    sink = Sink(fail_event='readiness_worker_cleanup_finished')
    readiness.bind_evidence_sink(sink)
    assert readiness._worker is None
    assert readiness._residue == 'NONE'


def test_parent_protocol_rejects_bad_event_binding_and_missing_result():
    """Reject malformed facts and EOF without the unique terminal record."""
    request = RclpyReadiness()._make_request(
        make_plan(), CONFIG_HASH, time.monotonic_ns() + 1_000_000_000,
    )
    digest = hashlib.sha256(
        RclpyReadiness._canonical_request(request),
    ).hexdigest()
    readiness = RclpyReadiness()
    readiness._active_request = request
    sink = Sink()
    readiness.bind_evidence_sink(sink)
    event = {
        'schema_id': readiness.EVENT_SCHEMA,
        'request_id': request['request_id'],
        'request_sha256': digest,
        'sequence': 1,
        'event': 'worker_started',
        'monotonic_ns': time.monotonic_ns(),
        'facts': {'request_binding': {
            'session_id': request['session_id'],
            'config_hash': request['config_hash'],
            'asset_manifest_sha256': request['asset_manifest_sha256'],
            'coordinator_ingress_instance_id': (
                request['coordinator_ingress_instance_id']
            ),
        }},
    }
    line = json.dumps(event).encode() + b'\n'
    readiness._worker = SimpleNamespace(stdout=ChunkStream([line]))
    asyncio.run(readiness._drain_stdout(request['request_id'], digest))
    assert readiness._protocol_error == 'worker result missing or duplicated'


def test_parent_protocol_rejects_oversized_record():
    """Bound individual worker protocol records before JSON parsing."""
    request = RclpyReadiness()._make_request(
        make_plan(), CONFIG_HASH, time.monotonic_ns() + 1_000_000_000,
    )
    digest = '0' * 64
    readiness = RclpyReadiness()
    readiness._active_request = request
    readiness._worker = SimpleNamespace(
        stdout=ChunkStream([b'x' * readiness.MAX_RECORD_BYTES + b'\n']),
    )
    asyncio.run(readiness._drain_stdout(request['request_id'], digest))
    assert 'worker record exceeded 4 KiB' in readiness._protocol_error


def test_parent_protocol_rejects_duplicate_terminal_result():
    """Require one terminal result and reject a replayed second one."""
    request = RclpyReadiness()._make_request(
        make_plan(), CONFIG_HASH, time.monotonic_ns() + 1_000_000_000,
    )
    digest = hashlib.sha256(
        RclpyReadiness._canonical_request(request),
    ).hexdigest()
    readiness = RclpyReadiness()
    readiness._active_request = request
    readiness.bind_evidence_sink(Sink())
    common = {
        'schema_id': readiness.EVENT_SCHEMA,
        'request_id': request['request_id'],
        'request_sha256': digest,
        'monotonic_ns': time.monotonic_ns(),
    }
    binding = {
        key: request[key] for key in (
            'session_id', 'config_hash', 'asset_manifest_sha256',
            'coordinator_ingress_instance_id',
        )
    }
    records = [
        {**common, 'sequence': 1, 'event': 'worker_started',
         'facts': {'request_binding': binding}},
        {**common, 'sequence': 2, 'event': 'worker_result', 'facts': {
            'verdict': 'FAIL', 'reason': 'injected failure', 'facts': {},
            'cleanup_errors': [], 'cleanup_elapsed_ns': 0,
        }},
        {**common, 'sequence': 3, 'event': 'worker_result', 'facts': {
            'verdict': 'FAIL', 'reason': 'injected failure', 'facts': {},
            'cleanup_errors': [], 'cleanup_elapsed_ns': 0,
        }},
    ]
    raw = b''.join(json.dumps(item).encode() + b'\n' for item in records)
    readiness._worker = SimpleNamespace(stdout=ChunkStream([raw]))
    asyncio.run(readiness._drain_stdout(request['request_id'], digest))
    assert 'duplicate worker_result' in readiness._protocol_error


def test_ready_result_rejects_boolean_scene_cardinality():
    """Do not accept bool as the integer one-model scene measurement."""
    readiness = RclpyReadiness()
    request = readiness._make_request(
        make_plan(), CONFIG_HASH, time.monotonic_ns() + 1_000_000_000,
    )
    result = {
        'facts': {
            'verdict': 'READY', 'reason': '', 'cleanup_errors': [],
            'facts': {
                'status': {
                    'world_id': request['world_id'],
                    'session_id': request['session_id'],
                    'config_hash': request['config_hash'],
                    'backend_instance_id': 9, 'status_sequence': 1,
                    'fault_flags': 0, 'actuator_inhibited': True,
                },
                'scene': {
                    'world_name': request['world_id'],
                    'matching_model_count': True,
                },
                'request_binding': {
                    key: request[key] for key in (
                        'session_id', 'config_hash',
                        'asset_manifest_sha256',
                        'coordinator_ingress_instance_id',
                    )
                },
            },
        },
    }
    with pytest.raises(RuntimeError, match='scene facts'):
        readiness._validate_ready_result(
            result, request, '0' * 64,
        )


def test_worker_attempt_is_not_restarted_after_failure(monkeypatch, tmp_path):
    """Keep one readiness instance capacity-one after its first failure."""
    readiness, _sink = readiness_with_child_fakes(
        monkeypatch, tmp_path, FAKE_SCENE='missing',
    )
    with pytest.raises(RuntimeError):
        asyncio.run(readiness.server_scene(make_plan(), ServerProcess(), 1.0))
    with pytest.raises(RuntimeError, match='attempt already consumed'):
        asyncio.run(readiness.server_scene(make_plan(), ServerProcess(), 1.0))


def test_parent_fails_closed_on_worker_crash(monkeypatch):
    """Treat an abrupt child exit without a result as a readiness failure."""
    spawned = []

    class InputPipe:
        """Model a request pipe for a crashed worker process."""

        def __init__(self):
            self.closed = False

        def write(self, _data):
            """Accept the single bounded request write."""

        async def drain(self):
            """Complete the fake pipe drain."""

        def is_closing(self):
            """Report the request pipe state."""
            return self.closed

        def close(self):
            """Close the request pipe."""
            self.closed = True

        async def wait_closed(self):
            """Complete the fake pipe close."""

    class CrashedWorker:
        pid = 876543
        returncode = 17

        def __init__(self):
            self.stdin = InputPipe()
            self.stdout = ChunkStream([])
            self.stderr = ChunkStream([])

        async def wait(self):
            """Expose the observed crash code through the owned handle."""
            return self.returncode

    async def factory(_environment):
        """Return one fake process handle without spawning an OS process."""
        spawned.append(True)
        return CrashedWorker()

    identity = {
        'pid': 876543, 'process_group_id': 876543, 'session_id': 876543,
        'start_ticks': 321,
    }
    readiness = RclpyReadiness(
        worker_factory=factory, identity_reader=lambda _pid: identity,
    )
    sink = Sink()
    LocalTrainingProcessSupervisor(
        plan=make_plan(), launcher=object(), readiness=readiness,
        evidence_sink=sink,
    )
    monkeypatch.setattr(
        supervisor, 'load_bound_config',
        lambda _path: (None, CONFIG_HASH, MANIFEST_HASH, 'B2_SOAK_V1'),
    )
    monkeypatch.setattr(
        supervisor.os, 'killpg',
        lambda _pgid, _sig: (_ for _ in ()).throw(ProcessLookupError()),
    )
    with pytest.raises(RuntimeError, match='worker result missing'):
        asyncio.run(readiness.server_scene(make_plan(), ServerProcess(), 1.0))
    assert spawned == [True]
    assert readiness._residue == 'NONE'
    assert 'readiness_worker_cleanup_finished' in [
        event for event, _facts in sink.events
    ]


def test_unjoinable_worker_is_not_reported_clean_or_ready(monkeypatch):
    """Bound and cancel a wait task while preserving unknown residue."""
    sent = []

    class InputPipe:
        """Model the parent-owned request pipe."""

        def __init__(self):
            self.closed = False

        def write(self, _data):
            """Accept the one request."""

        async def drain(self):
            """Complete request transfer."""

        def is_closing(self):
            """Report the pipe state."""
            return self.closed

        def close(self):
            """Close request transfer."""
            self.closed = True

        async def wait_closed(self):
            """Finish fake pipe closure."""

    class HangingWorker:
        pid = 765432
        returncode = None

        def __init__(self):
            self.stdin = InputPipe()
            self.stdout = ChunkStream([])
            self.stderr = ChunkStream([])

        async def wait(self):
            """Remain pending until the parent cancels its wait task."""
            await asyncio.Event().wait()

    async def factory(_environment):
        """Return one non-joinable process double."""
        return HangingWorker()

    readiness = RclpyReadiness(
        worker_factory=factory,
        identity_reader=lambda _pid: (_ for _ in ()).throw(
            OSError('identity unavailable'),
        ),
        signal_group=lambda *args: sent.append(args),
    )
    sink = Sink()
    LocalTrainingProcessSupervisor(
        plan=make_plan(), launcher=object(), readiness=readiness,
        evidence_sink=sink,
    )
    monkeypatch.setattr(
        supervisor, 'load_bound_config',
        lambda _path: (None, CONFIG_HASH, MANIFEST_HASH, 'B2_SOAK_V1'),
    )
    with pytest.raises(RuntimeError, match='cleanup not verified: UNKNOWN'):
        asyncio.run(readiness.server_scene(make_plan(), ServerProcess(), 0.05))
    assert sent == []
    assert readiness._worker_wait_task.cancelled()
    assert readiness._residue == 'UNKNOWN'
    cleanup = next(facts for event, facts in sink.events
                   if event == 'readiness_worker_cleanup_finished')
    assert cleanup['joined'] is False
    assert cleanup['residue'] == 'UNKNOWN'


def test_partial_worker_startup_is_finalized_without_readiness(
    monkeypatch, tmp_path,
):
    """Convert a child context startup failure into a clean FAIL result."""
    readiness, sink = readiness_with_child_fakes(
        monkeypatch, tmp_path, FAKE_CONTEXT_INIT_FAIL='1',
    )
    with pytest.raises(RuntimeError, match='readiness worker exited 1'):
        asyncio.run(readiness.server_scene(make_plan(), ServerProcess(), 1.0))
    result = next(facts['record']['facts'] for name, facts in sink.events
                  if name == 'readiness_worker_event'
                  and facts['record']['event'] == 'worker_result')
    assert result['verdict'] == 'FAIL'
    assert 'injected context init failure' in result['reason']
    assert readiness._residue == 'NONE'


def test_partial_status_source_startup_releases_owned_resources(
    monkeypatch, tmp_path,
):
    """Release context, node and executor after subscription startup fails."""
    trace_path = tmp_path / 'worker-cleanup.trace'
    readiness, sink = readiness_with_child_fakes(
        monkeypatch, tmp_path,
        FAKE_SUBSCRIPTION_FAIL='1', FAKE_TRACE=str(trace_path),
    )
    with pytest.raises(RuntimeError, match='readiness worker exited 1'):
        asyncio.run(readiness.server_scene(make_plan(), ServerProcess(), 1.0))
    result = next(facts['record']['facts'] for name, facts in sink.events
                  if name == 'readiness_worker_event'
                  and facts['record']['event'] == 'worker_result')
    assert result['verdict'] == 'FAIL'
    assert 'injected status subscription failure' in result['reason']
    trace = trace_path.read_text(encoding='utf-8').splitlines()
    assert trace == [
        'context.init', 'executor.add_node', 'subscription.create',
        'executor.remove_node', 'executor.shutdown', 'node.destroy',
        'context.shutdown',
    ]
    assert readiness._residue == 'NONE'


def test_parent_cancellation_finalizes_slow_child(monkeypatch, tmp_path):
    """Propagate cancellation after the owned child is reaped."""
    readiness, _sink = readiness_with_child_fakes(
        monkeypatch, tmp_path, FAKE_SCENE_DELAY='0.35',
    )

    async def exercise():
        """Cancel an active query and await the same readiness task."""
        task = asyncio.create_task(
            readiness.server_scene(make_plan(), ServerProcess(), 2.0),
        )
        await asyncio.sleep(0.08)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(exercise())
    assert readiness._residue == 'NONE'


def test_server_exit_is_detected_while_child_query_is_slow(
    monkeypatch, tmp_path,
):
    """Do not wait for a blocked child query after the server exits."""
    readiness, sink = readiness_with_child_fakes(
        monkeypatch, tmp_path, FAKE_SCENE_DELAY='0.35',
    )
    started = time.monotonic()

    class ExitingServer:
        pid = 99001

        @property
        def returncode(self):
            return 1 if time.monotonic() - started >= 0.08 else None

    with pytest.raises(RuntimeError, match='server exited during readiness'):
        asyncio.run(readiness.server_scene(make_plan(), ExitingServer(), 2.0))
    assert readiness._residue == 'NONE'
    assert 'readiness_server_exit_detected' in [
        event for event, _facts in sink.events
    ]


@pytest.mark.parametrize('fail_event', [
    'readiness_worker_parent_validated',
    'readiness_worker_stdin_closed',
])
def test_parent_sink_failure_still_finalizes_worker(
    monkeypatch, tmp_path, fail_event,
):
    """Evidence failure cannot skip child cleanup or turn into success."""
    readiness, sink = readiness_with_child_fakes(
        monkeypatch, tmp_path, sink_fail_event=fail_event,
    )
    with pytest.raises((OSError, RuntimeError)):
        asyncio.run(readiness.server_scene(make_plan(), ServerProcess(), 1.0))
    assert readiness._residue == 'NONE'
    assert 'readiness_worker_cleanup_finished' in [
        event for event, _facts in sink.events
    ]


def test_unknown_worker_identity_is_not_signalled_and_remains_unknown():
    """Do not signal a worker after its live identity becomes unreadable."""
    sent = []

    class InputPipe:
        """Model the parent-owned request pipe for a spawned worker."""

        def __init__(self):
            self.closed = False

        def is_closing(self):
            """Report whether the pipe has been closed."""
            return self.closed

        def close(self):
            """Deliver EOF to a worker that never received its request."""
            self.closed = True

        async def wait_closed(self):
            """Complete the local pipe close without external I/O."""

    baseline = {
        'pid': 123, 'process_group_id': 123, 'session_id': 123,
        'start_ticks': 456,
    }
    readiness = RclpyReadiness(
        identity_reader=lambda _pid: (_ for _ in ()).throw(OSError('denied')),
        signal_group=lambda *args: sent.append(args),
    )
    readiness.bind_evidence_sink(Sink())
    stdin = InputPipe()
    readiness._worker = SimpleNamespace(
        pid=123, returncode=None,
        stdin=stdin, stdout=ChunkStream([]), stderr=ChunkStream([]),
    )
    readiness._worker_identity = baseline

    async def finalize():
        """Run finalization with a completed wait handle and unknown PID."""
        readiness._worker_wait_task = asyncio.create_task(asyncio.sleep(0))
        await readiness._finalize_worker()
        deadline = readiness._worker_cleanup_deadline
        await readiness._finalize_worker()
        assert readiness._worker_cleanup_deadline == deadline

    asyncio.run(finalize())
    assert sent == []
    assert readiness._residue == 'UNKNOWN'
    assert stdin.closed


def test_worker_cleanup_after_readiness_deadline_cannot_return_ready(
    monkeypatch,
):
    """A delayed worker finalizer invalidates otherwise matching facts."""
    request = RclpyReadiness()._make_request(
        make_plan(), CONFIG_HASH, time.monotonic_ns() + 300_000_000,
    )
    monkeypatch.setenv('GZ_PARTITION', request['gz_partition'])
    monkeypatch.setenv('ROS_DOMAIN_ID', request['ros_domain_id'])

    class Status:
        header = SimpleNamespace(frame_id=request['world_id'])
        session_id = request['session_id']
        config_hash = request['config_hash']
        backend_instance_id = 9
        status_sequence = 1
        fault_flags = 0
        actuator_inhibited = True

    class StatusSource:
        def start(self):
            """Start a no-op fake source."""

        def next_status(self, _timeout_s):
            """Return one contract-matching fake status."""
            return Status()

        def close(self):
            """Hold fake finalization beyond the request deadline."""
            time.sleep(0.4)

    class Emitter:
        def __init__(self):
            self.records = []

        def emit(self, event, facts):
            self.records.append((event, facts))

    emitter = Emitter()
    result = run_worker(
        request, status_source_factory=StatusSource,
        scene_query=lambda *_args: SimpleNamespace(
            name=request['world_id'],
            model=[SimpleNamespace(name=request['model_id'], model=[])],
        ),
        emitter=emitter,
    )
    assert result == 1
    worker_result = emitter.records[-1][1]
    assert worker_result['verdict'] == 'FAIL'
    assert worker_result['reason'] == (
        'readiness deadline expired during cleanup'
    )
