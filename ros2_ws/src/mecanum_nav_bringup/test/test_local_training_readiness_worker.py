"""Process-isolated readiness tests using child-side middleware fakes."""
import asyncio
import hashlib
import json
import os
import signal
import sys
import tempfile
import time
import uuid
from dataclasses import replace
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


class GatedStream:
    """Pipe double that remains open until the owned worker exits."""

    def __init__(self):
        """Create an unopened stream that waits for worker exit."""
        self.closed = asyncio.Event()

    async def read(self, _size):
        """Wait until the owning fake worker closes the stream."""
        await self.closed.wait()
        return b''


class ControlledInput:
    """Input pipe double with a selectable pending drain/close phase."""

    def __init__(self, mode, release):
        """Create an input pipe with the selected gated operation."""
        self.mode = mode
        self.release = release
        self.closed = False
        self.wait_closed_calls = 0

    def write(self, _data):
        """Accept request bytes without a real pipe."""
        return None

    async def drain(self):
        """Optionally hold request drain until released by the test."""
        if self.mode == 'drain':
            await self.release.wait()

    def is_closing(self):
        """Return whether close has been requested."""
        return self.closed

    def close(self):
        """Close the fake input and release drain-mode tests."""
        self.closed = True
        if self.mode == 'drain':
            self.release.set()

    async def wait_closed(self):
        """Wait on the actual child/pipe close state on every call."""
        self.wait_closed_calls += 1
        if self.mode == 'wait_closed':
            await self.release.wait()


class ControlledWorker:
    """Owned worker fake with independently gated pipes and wait status."""

    def __init__(self, mode):
        """Create a fake process with independently gated I/O streams."""
        self.pid = 77123
        self.returncode = None
        self.exited = asyncio.Event()
        self.stdout = GatedStream()
        self.stderr = GatedStream()
        self.stdin = ControlledInput(mode, self.exited)

    async def wait(self):
        """Wait for the test to mark this worker exited."""
        await self.exited.wait()
        return self.returncode

    def stop(self):
        """Mark the worker exited and close both fake output streams."""
        self.returncode = 0
        self.exited.set()
        self.stdout.closed.set()
        self.stderr.closed.set()


def protocol_transcript(request, *, scene_outcome='MATCH', ready=True):
    """Build a canonical worker transcript for drainer regressions."""
    digest = hashlib.sha256(canonical_request_bytes(request)).hexdigest()
    binding = {key: request[key] for key in (
        'session_id', 'config_hash', 'asset_manifest_sha256',
        'coordinator_ingress_instance_id',
    )}
    status = {
        'world_id': request['world_id'], 'session_id': request['session_id'],
        'config_hash': request['config_hash'], 'backend_instance_id': 9,
        'status_sequence': 1, 'fault_flags': 0, 'actuator_inhibited': True,
    }
    scene = {
        'world_name': request['world_id'] if scene_outcome == 'MATCH'
        else 'other_world',
        'matching_model_count': 1 if scene_outcome == 'MATCH' else 0,
    }
    specifications = [
        ('worker_started', {'request_binding': binding}),
        ('status_wait_started', {
            'topic': '/mecanum/local_training/backend_state', 'qos_depth': 50,
        }),
        ('status_matched', {'status': status, 'request_binding': binding}),
        ('scene_query_started', {
            'service': '/world/b2_training_arena/scene/info',
            'timeout_ms': 500,
        }),
        ('scene_query_finished', {
            **scene, 'duration_ns': 100, 'outcome': scene_outcome,
            'error': 'injected query error' if scene_outcome == 'ERROR'
            else None,
        }),
    ]
    verdict = 'READY' if ready else 'FAIL'
    result_facts = {
        'verdict': verdict,
        'reason': '' if ready else 'early injected failure',
        'facts': {
            'status': status, 'scene': scene, 'request_binding': binding,
        } if ready else {},
        'cleanup_errors': [], 'cleanup_elapsed_ns': 100,
    }
    specifications.append(('worker_result', result_facts))
    records = []
    for sequence, (event, facts) in enumerate(specifications, 1):
        records.append({
            'schema_id': 'mecanum_b2_scene_readiness_event/v1',
            'request_id': request['request_id'], 'request_sha256': digest,
            'sequence': sequence, 'event': event,
            'monotonic_ns': time.monotonic_ns(), 'facts': facts,
        })
    return digest, records


def run_emitted_full_window(monkeypatch, *, match_at):
    """Exercise production emitter and FSM using a fake clock."""
    import mecanum_nav_bringup.local_training_readiness_worker as worker_module

    class Clock:
        def __init__(self):
            self.now_ns = time.monotonic_ns()
            self.starts = []

        def __call__(self):
            return self.now_ns

        def sleep(self, seconds):
            self.now_ns += int(seconds * 1_000_000_000)

    class TimeProxy:
        monotonic = staticmethod(time.monotonic)
        monotonic_ns = staticmethod(time.monotonic_ns)

        @staticmethod
        def sleep(seconds):
            clock.sleep(seconds)

    clock = Clock()
    monkeypatch.setattr(worker_module, 'time', TimeProxy)
    monkeypatch.setenv('GZ_PARTITION', 'mecanum_b2_testpartition')
    monkeypatch.setenv('ROS_DOMAIN_ID', '83')
    plan = replace(
        make_plan(), coordinator_ingress_instance_id=(1 << 64) - 1,
    )
    request = RclpyReadiness()._make_request(
        plan, CONFIG_HASH, clock.now_ns + 30_000_000_000,
    )

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
            """Start the deterministic fake status source."""

        def next_status(self, _timeout_s):
            """Return the same healthy, exactly bound status."""
            return Status()

        def close(self):
            """Close the fake source without external resources."""

    query_starts = []

    class E(TimeoutError):
        """Short timeout type maximizes bounded escaped error evidence."""

    def scene_query(_service, _timeout_ms):
        query_starts.append(clock.now_ns)
        if match_at is not None and len(query_starts) == match_at:
            return SimpleNamespace(
                name=request['world_id'],
                model=[SimpleNamespace(
                    name=request['model_id'], model=[],
                )],
            )
        if match_at is None or len(query_starts) % 2 == 0:
            raise E('é\\"\n' + '\x00' * 249)
        return None

    request_digest = hashlib.sha256(
        canonical_request_bytes(request),
    ).hexdigest()

    class RecordingEmitter:
        def __init__(self, delegate):
            self.delegate = delegate
            self.failure = None

        def emit(self, event, facts):
            try:
                return self.delegate.emit(event, facts)
            except RuntimeError as error:
                self.failure = str(error)
                raise

        def close(self):
            self.delegate.close()

    with tempfile.TemporaryFile() as output:
        emitter = RecordingEmitter(worker_module._ProtocolEmitter(
            os.dup(output.fileno()), request['request_id'], request_digest,
        ))
        result = worker_module.run_worker(
            request, status_source_factory=StatusSource,
            scene_query=scene_query, emitter=emitter, clock_ns=clock,
        )
        emitter.close()
        output.seek(0)
        payload = output.read()

    lines = payload.splitlines(keepends=True)
    parent = RclpyReadiness()
    parent._active_request = request
    parent.bind_evidence_sink(Sink())
    parent._worker = SimpleNamespace(stdout=ChunkStream([payload]))
    asyncio.run(parent._drain_stdout(request['request_id'], request_digest))
    records = [json.loads(line) for line in lines]
    return {
        'request': request,
        'query_starts': query_starts,
        'result': result,
        'emitter_failure': emitter.failure,
        'payload_bytes': len(payload),
        'record_bytes': [len(line) for line in lines],
        'records': records,
        'protocol_error': parent._protocol_error,
        'protocol_state': parent._protocol_state,
    }


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
        else:
            time.sleep(min(timeout_sec, 0.005))
    def remove_node(self, node):
        record('executor.remove_node')
        if os.environ.get('FAKE_REMOVE_NODE_FAIL') == '1':
            raise RuntimeError('injected remove_node failure')
        if node is self.node:
            self.node = None
        return None
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
    def __init__(self, mode=None):
        if mode is None:
            modes = os.environ.get('FAKE_SCENE_SEQUENCE', '').split(',')
            index = int(os.environ.get('FAKE_SCENE_INDEX', '0'))
            mode = (
                modes[min(index, len(modes) - 1)] if modes[0]
                else os.environ.get('FAKE_SCENE', 'match')
            )
            os.environ['FAKE_SCENE_INDEX'] = str(index + 1)
        self.name = 'other_world' if mode == 'world' else 'b2_training_arena'
        count = (
            0 if mode == 'missing'
            else 2 if mode == 'duplicate' else 1
        )
        self.model = [Model('mecanum_b2') for _ in range(count)]
scene_module.Scene = Scene
transport = module('gz.transport13'); transport.__path__ = []
class TransportNode:
    def __init__(self): self.calls = 0
    def request(
        self, service, request, request_type, response_type, timeout_ms,
    ):
        assert service == '/world/b2_training_arena/scene/info'
        self.calls += 1
        if (self.calls == 1
                and os.environ.get('FAKE_QUERY_TIMEOUT_FIRST') == '1'):
            raise TimeoutError('injected first-query timeout')
        if os.environ.get('FAKE_QUERY_UNEXPECTED') == '1':
            raise RuntimeError('injected unexpected query error')
        delay = float(os.environ.get('FAKE_SCENE_DELAY', '0'))
        if delay:
            time.sleep(delay)
        return True, Scene()
transport.Node = TransportNode
"""
    (root / 'sitecustomize.py').write_text(code, encoding='utf-8')


def readiness_with_child_fakes(
    monkeypatch, tmp_path, sink_fail_event=None, monotonic=None, sink=None,
    **child_values,
):
    """Bind an isolated middleware-fake environment to the default client."""
    fake_root = tmp_path / 'child-fakes'
    install_child_middleware_fakes(fake_root)
    monkeypatch.setenv(
        'PYTHONPATH',
        str(fake_root) + os.pathsep + os.environ.get('PYTHONPATH', ''),
    )
    monkeypatch.setenv('FAKE_TRACE', str(fake_root / 'trace'))
    for key, value in child_values.items():
        monkeypatch.setenv(key, str(value))
    monkeypatch.setattr(
        supervisor, 'load_bound_config',
        lambda _path: (None, CONFIG_HASH, MANIFEST_HASH, 'B2_SOAK_V1'),
    )
    readiness_kwargs = {} if monotonic is None else {'monotonic': monotonic}
    readiness = RclpyReadiness(**readiness_kwargs)
    sink = sink or Sink(fail_event=sink_fail_event)
    LocalTrainingProcessSupervisor(
        plan=make_plan(), launcher=object(), readiness=readiness,
        evidence_sink=sink,
    )
    return readiness, sink


def readiness_with_controlled_worker(monkeypatch, worker, sink=None):
    """Bind an owned fake process to the real parent readiness entry."""
    identity = {
        'pid': worker.pid, 'process_group_id': worker.pid,
        'session_id': worker.pid, 'start_ticks': 987,
    }

    async def factory(_environment):
        return worker

    readiness = RclpyReadiness(
        worker_factory=factory,
        identity_reader=lambda _pid: identity,
        signal_group=lambda _process, _identity, _sig: worker.stop(),
    )
    sink = sink or Sink()
    monkeypatch.setattr(supervisor.os, 'killpg', lambda *_args: (
        _ for _ in ()
    ).throw(ProcessLookupError()))
    monkeypatch.setattr(
        supervisor, 'load_bound_config',
        lambda _path: (None, CONFIG_HASH, MANIFEST_HASH, 'B2_SOAK_V1'),
    )
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


def test_jazzy_remove_node_none_does_not_block_ready(monkeypatch, tmp_path):
    """Treat the Jazzy remove_node None return as successful cleanup."""
    readiness, sink = readiness_with_child_fakes(monkeypatch, tmp_path)
    asyncio.run(readiness.server_scene(make_plan(), ServerProcess(), 2.0))
    result = next(facts['record']['facts'] for name, facts in sink.events
                  if name == 'readiness_worker_event'
                  and facts['record']['event'] == 'worker_result')
    trace = Path(os.environ['PYTHONPATH'].split(os.pathsep)[0]) / 'trace'
    assert result['verdict'] == 'READY'
    assert trace.read_text(encoding='utf-8').splitlines()[-4:] == [
        'executor.remove_node', 'executor.shutdown', 'node.destroy',
        'context.shutdown',
    ]


def test_remove_node_exception_still_attempts_remaining_cleanup(
    monkeypatch, tmp_path,
):
    """Continue executor/node/context cleanup after remove_node raises."""
    readiness, sink = readiness_with_child_fakes(
        monkeypatch, tmp_path, FAKE_REMOVE_NODE_FAIL='1',
    )
    with pytest.raises(RuntimeError, match='readiness worker exited 1'):
        asyncio.run(readiness.server_scene(make_plan(), ServerProcess(), 2.0))
    result = next(facts['record']['facts'] for name, facts in sink.events
                  if name == 'readiness_worker_event'
                  and facts['record']['event'] == 'worker_result')
    trace = Path(os.environ['PYTHONPATH'].split(os.pathsep)[0]) / 'trace'
    events = trace.read_text(encoding='utf-8').splitlines()
    assert result['verdict'] == 'FAIL'
    assert 'executor.shutdown' in events
    assert 'node.destroy' in events
    assert 'context.shutdown' in events


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


def test_nonpositive_budget_does_not_spawn_worker(monkeypatch):
    """Reject an exhausted readiness budget before the process factory."""
    calls = []

    async def factory(_environment):
        calls.append(True)
        raise AssertionError('worker factory must not be called')

    readiness = RclpyReadiness(worker_factory=factory, monotonic=lambda: 7.0)
    sink = Sink()
    monkeypatch.setattr(
        supervisor, 'load_bound_config',
        lambda _path: (None, CONFIG_HASH, MANIFEST_HASH, 'B2_SOAK_V1'),
    )
    LocalTrainingProcessSupervisor(
        plan=make_plan(), launcher=object(), readiness=readiness,
        evidence_sink=sink,
    )
    with pytest.raises(TimeoutError, match='before worker spawn'):
        asyncio.run(readiness.server_scene(make_plan(), ServerProcess(), 0.0))
    assert calls == []


@pytest.mark.parametrize('mode', ['drain', 'wait_closed'])
def test_pending_request_pipe_phase_is_deadline_bounded(
    monkeypatch, mode,
):
    """Request drain and stdin close wait share the parent deadline."""
    worker = ControlledWorker(mode)
    readiness, sink = readiness_with_controlled_worker(
        monkeypatch, worker,
    )
    with pytest.raises(TimeoutError, match='deadline expired during'):
        asyncio.run(readiness.server_scene(make_plan(), ServerProcess(), 0.05))
    assert worker.returncode == 0
    assert readiness._process_residue == 'NONE'
    assert readiness._task_residue == 'NONE', sink.events[-1][1]['task_states']
    assert readiness._residue == 'NONE'


def test_persistent_stdin_close_does_not_block_verified_worker_signal(
    monkeypatch,
):
    """Signal the verified worker while the same close waiter stays pending."""
    worker = ControlledWorker('wait_closed')
    readiness, sink = readiness_with_controlled_worker(monkeypatch, worker)
    signal_events = []

    def stop_on_verified_signal(process, identity, sig):
        assert process is worker
        assert identity['pid'] == worker.pid
        signal_events.append(sig)
        worker.stop()

    readiness._signal_group = stop_on_verified_signal
    with pytest.raises(
        TimeoutError, match='deadline expired during stdin close',
    ):
        asyncio.run(readiness.server_scene(make_plan(), ServerProcess(), 0.05))
    assert signal_events == [signal.SIGINT]
    assert worker.returncode == 0
    assert worker.stdin.wait_closed_calls == 1
    events = [event for event, _facts in sink.events]
    assert events.index('readiness_worker_cleanup_signal') < events.index(
        'readiness_worker_stdin_closed'
    )
    assert readiness._process_residue == 'NONE'
    assert readiness._task_residue == 'NONE'
    assert readiness._residue == 'NONE'


def test_server_exit_during_request_drain_cleans_worker(monkeypatch):
    """The parent notices server exit while request transfer is pending."""
    worker = ControlledWorker('drain')
    readiness, sink = readiness_with_controlled_worker(monkeypatch, worker)
    server = ServerProcess()

    async def exercise():
        loop = asyncio.get_running_loop()
        loop.call_later(0.03, setattr, server, 'returncode', 9)
        with pytest.raises(
            RuntimeError, match='server exited during readiness',
        ):
            await readiness.server_scene(make_plan(), server, 1.0)

    asyncio.run(exercise())
    assert worker.returncode == 0
    event = next(facts for name, facts in sink.events
                 if name == 'readiness_server_exit_detected')
    assert event['readiness_phase'] == 'request drain'
    assert readiness._residue == 'NONE'


def test_failed_drain_task_is_classified_separately_from_process(monkeypatch):
    """A finished process does not hide a failed pipe-drain task."""
    worker = ControlledWorker('normal')
    worker.stop()
    readiness = RclpyReadiness(monotonic=lambda: 5.0)
    readiness.bind_evidence_sink(Sink())
    readiness._worker = worker
    readiness._worker_identity = {
        'pid': worker.pid, 'process_group_id': worker.pid,
        'session_id': worker.pid, 'start_ticks': 987,
    }
    monkeypatch.setattr(supervisor.os, 'killpg', lambda *_args: (
        _ for _ in ()
    ).throw(ProcessLookupError()))

    async def exercise():
        async def fail_drain():
            raise OSError('injected pipe read failure')
        readiness._stdout_task = asyncio.create_task(fail_drain())
        await asyncio.sleep(0)
        await readiness._finalize_worker()
        assert readiness._process_residue == 'NONE'
        assert readiness._task_residue == 'FAILED'
        assert readiness._residue == 'UNKNOWN'

    asyncio.run(exercise())


def test_spawn_handle_returned_during_cleanup_is_adopted_and_stopped(
    monkeypatch,
):
    """Retain and clean a worker handle that arrives after spawn timeout."""
    started = asyncio.Event()
    release = asyncio.Event()
    worker = ControlledWorker('normal')
    calls = []

    async def factory(_environment):
        calls.append(True)
        started.set()
        await release.wait()
        return worker

    identity = {'pid': worker.pid, 'process_group_id': worker.pid,
                'session_id': worker.pid, 'start_ticks': 987}
    readiness = RclpyReadiness(
        worker_factory=factory, identity_reader=lambda _pid: identity,
        signal_group=lambda _process, _identity, _sig: worker.stop(),
    )
    sink = Sink()
    monkeypatch.setattr(supervisor.os, 'killpg', lambda *_args: (
        _ for _ in ()
    ).throw(ProcessLookupError()))
    monkeypatch.setattr(
        supervisor, 'load_bound_config',
        lambda _path: (None, CONFIG_HASH, MANIFEST_HASH, 'B2_SOAK_V1'),
    )
    LocalTrainingProcessSupervisor(
        plan=make_plan(), launcher=object(), readiness=readiness,
        evidence_sink=sink,
    )

    async def exercise():
        loop = asyncio.get_running_loop()
        task = asyncio.create_task(
            readiness.server_scene(make_plan(), ServerProcess(), 0.04),
        )
        await started.wait()
        loop.call_later(0.06, release.set)
        with pytest.raises(TimeoutError, match='worker spawn'):
            await task

    asyncio.run(exercise())
    assert calls == [True]
    assert readiness._worker is worker
    assert worker.returncode == 0
    assert readiness._process_residue == 'NONE'
    assert readiness._residue == 'NONE'


def test_cancellation_near_spawn_completion_keeps_handle_owned(monkeypatch):
    """Cancellation while spawn is pending still adopts its eventual handle."""
    started = asyncio.Event()
    release = asyncio.Event()
    worker = ControlledWorker('normal')

    async def factory(_environment):
        started.set()
        await release.wait()
        return worker

    identity = {'pid': worker.pid, 'process_group_id': worker.pid,
                'session_id': worker.pid, 'start_ticks': 987}
    readiness = RclpyReadiness(
        worker_factory=factory, identity_reader=lambda _pid: identity,
        signal_group=lambda _process, _identity, _sig: worker.stop(),
    )
    monkeypatch.setattr(supervisor.os, 'killpg', lambda *_args: (
        _ for _ in ()
    ).throw(ProcessLookupError()))
    monkeypatch.setattr(
        supervisor, 'load_bound_config',
        lambda _path: (None, CONFIG_HASH, MANIFEST_HASH, 'B2_SOAK_V1'),
    )
    LocalTrainingProcessSupervisor(
        plan=make_plan(), launcher=object(), readiness=readiness,
        evidence_sink=Sink(),
    )

    async def exercise():
        loop = asyncio.get_running_loop()
        task = asyncio.create_task(
            readiness.server_scene(make_plan(), ServerProcess(), 2.0),
        )
        await started.wait()
        loop.call_later(0.05, release.set)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(exercise())
    assert readiness._worker is worker
    assert worker.returncode == 0
    assert readiness._process_residue == 'NONE'


def test_evidence_validation_overrun_cannot_return_ready(
    monkeypatch, tmp_path,
):
    """A slow final validation evidence write invalidates timely READY."""
    readiness, _sink = readiness_with_child_fakes(monkeypatch, tmp_path)

    class SlowValidationSink(Sink):
        def record(self, event, facts):
            super().record(event, facts)
            if event == 'readiness_worker_parent_validated':
                time.sleep(0.2)

    sink = SlowValidationSink()
    readiness._evidence_sink = sink
    with pytest.raises(TimeoutError, match='validation evidence'):
        asyncio.run(readiness.server_scene(make_plan(), ServerProcess(), 0.15))
    assert readiness._residue == 'NONE'


@pytest.mark.parametrize(
    'advance_at', [
        None, 'readiness_worker_cleanup_started',
        'readiness_worker_cleanup_finished',
    ],
)
def test_parent_success_requires_deadline_after_finalization(
    monkeypatch, tmp_path, advance_at,
):
    """The parent entry includes cleanup evidence in its READY deadline."""
    class Clock:
        now = 0.0

        def __call__(self):
            return self.now

    clock = Clock()

    class SinkWithClock(Sink):
        def record(self, event, facts):
            super().record(event, facts)
            if event == advance_at:
                clock.now = 1.1

    sink = SinkWithClock()
    readiness, sink = readiness_with_child_fakes(
        monkeypatch, tmp_path, monotonic=clock, sink=sink,
    )
    if advance_at is None:
        asyncio.run(readiness.server_scene(make_plan(), ServerProcess(), 1.0))
        assert readiness._residue == 'NONE'
    else:
        with pytest.raises(TimeoutError, match='finalization'):
            asyncio.run(
                readiness.server_scene(make_plan(), ServerProcess(), 1.0)
            )
        assert readiness._readiness_deadline_violation
        assert readiness._residue == 'NONE'
        assert 'readiness_deadline_violation_after_finalization' in [
            event for event, _facts in sink.events
        ]


def test_cleanup_finished_deadline_overrun_is_sticky_and_not_ready(
    monkeypatch, tmp_path,
):
    """Late cleanup evidence cannot turn a worker READY result into success."""
    class Clock:
        now = 0.0

        def __call__(self):
            return self.now

    clock = Clock()

    class SlowCleanupFinishedSink(Sink):
        def record(self, event, facts):
            super().record(event, facts)
            if event == 'readiness_worker_cleanup_finished':
                clock.now = 3.1

    sink = SlowCleanupFinishedSink()
    readiness, sink = readiness_with_child_fakes(
        monkeypatch, tmp_path, monotonic=clock, sink=sink,
    )
    with pytest.raises(TimeoutError, match='cleanup deadline'):
        asyncio.run(readiness.server_scene(make_plan(), ServerProcess(), 10.0))
    assert readiness._cleanup_deadline_violation
    assert readiness._process_residue == 'NONE'
    assert readiness._task_residue == 'NONE'
    assert 'readiness_worker_cleanup_deadline_violation' in [
        event for event, _facts in sink.events
    ]


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
    with pytest.raises((RuntimeError, TimeoutError)):
        asyncio.run(readiness.server_scene(make_plan(), ServerProcess(), 1.0))
    results = [facts['record']['facts'] for name, facts in sink.events
               if name == 'readiness_worker_event'
               and facts['record']['event'] == 'worker_result']
    assert all(result['verdict'] != 'READY' for result in results)


@pytest.mark.parametrize('child_values', [
    {'FAKE_QUERY_TIMEOUT_FIRST': '1'},
    {'FAKE_SCENE_SEQUENCE': 'missing,match'},
])
def test_worker_requeries_until_matching_scene_in_same_attempt(
    monkeypatch, tmp_path, child_values,
):
    """A transient query timeout or missing model can converge in-place."""
    readiness, sink = readiness_with_child_fakes(
        monkeypatch, tmp_path, **child_values,
    )
    asyncio.run(readiness.server_scene(make_plan(), ServerProcess(), 3.0))
    records = [facts['record'] for name, facts in sink.events
               if name == 'readiness_worker_event']
    starts = [record['monotonic_ns'] for record in records
              if record['event'] == 'scene_query_started']
    finished = [record['facts'] for record in records
                if record['event'] == 'scene_query_finished']
    result = records[-1]['facts']
    assert result['verdict'] == 'READY'
    assert len(starts) == 2
    assert starts[1] - starts[0] >= 2_000_000_000
    assert finished[0]['outcome'] in {'ERROR', 'MISMATCH'}
    assert finished[1]['outcome'] == 'MATCH'
    assert len([event for event, _ in sink.events
                if event == 'readiness_worker_spawned']) == 1
    assert len({record['request_id'] for record in records}) == 1


def test_worker_core_retries_timeout_without_new_attempt(monkeypatch):
    """Exercise retry convergence in the production worker core with fakes."""
    import mecanum_nav_bringup.local_training_readiness_worker as worker_module

    monkeypatch.setenv('GZ_PARTITION', 'mecanum_b2_testpartition')
    monkeypatch.setenv('ROS_DOMAIN_ID', '83')
    request = RclpyReadiness()._make_request(
        make_plan(), CONFIG_HASH, time.monotonic_ns() + 2_500_000_000,
    )
    status = SimpleNamespace(
        header=SimpleNamespace(frame_id=request['world_id']),
        session_id=request['session_id'], config_hash=request['config_hash'],
        backend_instance_id=9, status_sequence=1, fault_flags=0,
        actuator_inhibited=True,
    )
    source = SimpleNamespace(
        start=lambda: None, next_status=lambda _timeout: status,
        close=lambda: None,
    )
    calls = []
    query_starts = []

    def query(_service, _timeout_ms):
        calls.append(True)
        query_starts.append(time.monotonic_ns())
        if len(calls) == 1:
            raise TimeoutError('injected first query timeout')
        return SimpleNamespace(
            name=request['world_id'],
            model=[SimpleNamespace(name=request['model_id'], model=[])],
        )

    class Emitter:
        def __init__(self): self.records = []
        def emit(self, event, facts): self.records.append((event, facts))

    emitter = Emitter()
    result = worker_module.run_worker(
        request, status_source_factory=lambda: source,
        scene_query=query, emitter=emitter,
    )
    assert result == 0
    assert len(calls) == 2
    assert query_starts[1] - query_starts[0] >= 2_000_000_000
    assert [event for event, _ in emitter.records].count(
        'scene_query_finished',
    ) == 2
    assert emitter.records[-1][1]['verdict'] == 'READY'


def test_full_window_emitter_and_parent_fsm_fit_with_late_match(
    monkeypatch, tmp_path,
):
    """Prove a 30 s producer window fits and can match at query fifteen."""
    result = run_emitted_full_window(monkeypatch, match_at=15)
    intervals = [b - a for a, b in zip(
        result['query_starts'], result['query_starts'][1:],
    )]
    metrics = {
        'query_count': len(result['query_starts']),
        'query_intervals_ns': intervals,
        'payload_bytes': result['payload_bytes'],
        'max_record_bytes': max(result['record_bytes']),
        'result': result['records'][-1]['facts']['verdict'],
        'coordinator_ingress_instance_id': result['request'][
            'coordinator_ingress_instance_id'
        ],
        'parent_protocol_state': result['protocol_state'],
        'emitter_failure': result['emitter_failure'],
    }
    (tmp_path / 'metrics.json').write_text(
        json.dumps(metrics, sort_keys=True), encoding='utf-8',
    )
    assert metrics['coordinator_ingress_instance_id'] == (1 << 64) - 1
    assert metrics['query_count'] == 15
    assert all(interval >= 2_000_000_000 for interval in intervals)
    assert metrics['max_record_bytes'] <= 4 * 1024
    assert metrics['payload_bytes'] <= 64 * 1024
    assert result['result'] == 0
    assert metrics['result'] == 'READY'
    assert result['protocol_error'] is None
    assert result['protocol_state'] == 'TERMINAL'
    assert result['emitter_failure'] is None


def test_full_window_no_match_emitter_stays_bounded_and_returns_fail(
    monkeypatch, tmp_path,
):
    """Bound all 15 query cycles with escaped transient errors to deadline."""
    result = run_emitted_full_window(monkeypatch, match_at=None)
    terminal = next((record for record in result['records']
                     if record['event'] == 'worker_result'), None)
    intervals = [b - a for a, b in zip(
        result['query_starts'], result['query_starts'][1:],
    )]
    metrics = {
        'query_count': len(result['query_starts']),
        'query_intervals_ns': intervals,
        'payload_bytes': result['payload_bytes'],
        'max_record_bytes': max(result['record_bytes']),
        'result': (terminal['facts'].get('verdict')
                   if terminal is not None else None),
        'parent_protocol_state': result['protocol_state'],
        'emitter_failure': result['emitter_failure'],
        'error_sample': next(
            record['facts']['error']
            for record in result['records']
            if record['event'] == 'scene_query_finished'
            and record['facts']['error'] is not None
        ),
    }
    (tmp_path / 'metrics.json').write_text(
        json.dumps(metrics, ensure_ascii=True, sort_keys=True),
        encoding='utf-8',
    )
    assert metrics['query_count'] == 15
    assert all(interval >= 2_000_000_000 for interval in intervals)
    assert metrics['max_record_bytes'] <= 4 * 1024
    assert metrics['payload_bytes'] <= 64 * 1024
    assert '\\u0000' in json.dumps(metrics['error_sample'])
    assert result['result'] == 1
    assert metrics['result'] == 'FAIL'
    assert result['protocol_error'] is None
    assert result['protocol_state'] == 'TERMINAL'
    assert result['emitter_failure'] is None


def test_always_mismatched_scene_times_out_without_ready(
    monkeypatch, tmp_path,
):
    """A persistent scene mismatch remains bounded and never becomes ready."""
    readiness, sink = readiness_with_child_fakes(
        monkeypatch, tmp_path, FAKE_SCENE='missing',
    )
    with pytest.raises(TimeoutError):
        asyncio.run(readiness.server_scene(make_plan(), ServerProcess(), 0.35))
    results = [facts['record']['facts'] for name, facts in sink.events
               if name == 'readiness_worker_event'
               and facts['record']['event'] == 'worker_result']
    assert all(result['verdict'] != 'READY' for result in results)
    assert len([1 for name, facts in sink.events
                if name == 'readiness_worker_event'
                and facts['record']['event'] == 'scene_query_started']) == 1


def test_cancellation_between_scene_queries_does_not_start_another(
    monkeypatch, tmp_path,
):
    """Cancellation during the one-second cadence prevents another query."""
    readiness, sink = readiness_with_child_fakes(
        monkeypatch, tmp_path, FAKE_SCENE='missing',
    )

    async def exercise():
        task = asyncio.create_task(
            readiness.server_scene(make_plan(), ServerProcess(), 3.0),
        )
        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline:
            if any(name == 'readiness_worker_event'
                   and facts['record']['event'] == 'scene_query_finished'
                   for name, facts in sink.events):
                break
            await asyncio.sleep(0.005)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(exercise())
    starts = [facts['record'] for name, facts in sink.events
              if name == 'readiness_worker_event'
              and facts['record']['event'] == 'scene_query_started']
    assert len(starts) == 1


def test_unexpected_scene_query_exception_is_not_retried(
    monkeypatch, tmp_path,
):
    """Only timeouts and OSError converge; unexpected exceptions fail."""
    readiness, sink = readiness_with_child_fakes(
        monkeypatch, tmp_path, FAKE_QUERY_UNEXPECTED='1',
    )
    with pytest.raises(RuntimeError, match='worker exited 1'):
        asyncio.run(readiness.server_scene(make_plan(), ServerProcess(), 2.0))
    records = [facts['record'] for name, facts in sink.events
               if name == 'readiness_worker_event']
    finished = [record for record in records
                if record['event'] == 'scene_query_finished']
    assert len(finished) == 1
    assert finished[0]['facts']['outcome'] == 'ERROR'
    assert records[-1]['facts']['verdict'] == 'FAIL'


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


@pytest.mark.parametrize('fail_event', [
    'readiness_worker_cleanup_started',
    'readiness_worker_stdin_closed',
    'readiness_worker_cleanup_finished',
])
def test_cleanup_evidence_failure_is_sticky_after_process_exit(
    monkeypatch, tmp_path, fail_event,
):
    """Clean process state cannot erase missing cleanup evidence."""
    readiness, sink = readiness_with_child_fakes(
        monkeypatch, tmp_path, sink_fail_event=fail_event,
    )
    with pytest.raises(RuntimeError, match='evidence_errors'):
        asyncio.run(readiness.server_scene(make_plan(), ServerProcess(), 2.0))
    assert readiness._process_residue == 'NONE'
    assert readiness._task_residue == 'NONE'
    assert readiness._residue == 'NONE'
    assert any(item.startswith(f'{fail_event}:')
               for item in readiness._evidence_errors)
    assert fail_event not in [event for event, _ in sink.events]


def test_cleanup_signal_evidence_failure_does_not_erase_timeout(
    monkeypatch, tmp_path,
):
    """Signal-event write failure remains sticky while cleanup is attempted."""
    readiness, _sink = readiness_with_child_fakes(
        monkeypatch, tmp_path,
        sink_fail_event='readiness_worker_cleanup_signal',
        FAKE_SCENE_DELAY='0.5',
    )
    with pytest.raises(TimeoutError):
        asyncio.run(readiness.server_scene(make_plan(), ServerProcess(), 0.1))
    assert any(item.startswith('readiness_worker_cleanup_signal:')
               for item in readiness._evidence_errors)
    assert readiness._process_residue == 'NONE'
    assert readiness._residue == 'NONE'


def test_exited_process_with_pending_drain_is_not_clean_and_deadline_is_stable(
    monkeypatch,
):
    """Separate process cleanup from task residue across finalization."""
    worker = ControlledWorker('normal')
    worker.stop()
    readiness = RclpyReadiness(monotonic=lambda: 10.0)
    sink = Sink()
    readiness.bind_evidence_sink(sink)
    readiness._worker = worker
    readiness._worker_identity = {
        'pid': worker.pid, 'process_group_id': worker.pid,
        'session_id': worker.pid, 'start_ticks': 987,
    }
    readiness._worker_cleanup_deadline = 10.0
    monkeypatch.setattr(supervisor.os, 'killpg', lambda *_args: (
        _ for _ in ()
    ).throw(ProcessLookupError()))
    release = asyncio.Event()
    entered = asyncio.Event()

    async def cancellation_resistant_drain():
        entered.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            await release.wait()

    async def exercise():
        task = asyncio.create_task(cancellation_resistant_drain())
        readiness._stdout_task = task
        await entered.wait()
        await readiness._finalize_worker()
        fixed_deadline = readiness._worker_cleanup_deadline
        assert readiness._process_residue == 'NONE'
        assert readiness._task_residue == 'UNKNOWN'
        assert readiness._residue == 'UNKNOWN'
        assert not task.done()
        release.set()
        await asyncio.wait_for(task, timeout=0.2)
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        await readiness._finalize_worker()
        assert readiness._worker_cleanup_deadline == fixed_deadline
        assert readiness._process_residue == 'NONE'
        assert readiness._task_residue == 'UNKNOWN'

    asyncio.run(exercise())


def test_persistent_stdin_pending_escalates_and_remains_unknown(monkeypatch):
    """Escalate verified signals despite a pending pipe and retain residue."""
    worker = ControlledWorker('wait_closed')
    signals = []
    clock = [0.0]
    readiness = RclpyReadiness(
        monotonic=lambda: clock[0],
        identity_reader=lambda _pid: {
            'pid': worker.pid, 'process_group_id': worker.pid,
            'session_id': worker.pid, 'start_ticks': 987,
        },
        signal_group=lambda _proc, _identity, sig: signals.append(sig),
    )
    sink = Sink()
    readiness.bind_evidence_sink(sink)
    readiness._worker = worker
    readiness._worker_identity = {
        'pid': worker.pid, 'process_group_id': worker.pid,
        'session_id': worker.pid, 'start_ticks': 987,
    }
    monkeypatch.setattr(supervisor.os, 'killpg', lambda *_args: None)

    async def consume_phase_budget(timeout):
        clock[0] += timeout
        return False

    readiness._wait_worker = consume_phase_budget

    async def exercise():
        readiness._worker_wait_task = asyncio.create_task(worker.wait())
        await readiness._finalize_worker()
        fixed = readiness._worker_cleanup_deadline
        assert signals == [signal.SIGINT, signal.SIGTERM, signal.SIGKILL]
        assert readiness._process_residue == 'UNKNOWN'
        assert readiness._task_residue == 'UNKNOWN'
        assert readiness._residue == 'UNKNOWN'
        assert readiness._cleanup_deadline_violation
        await readiness._finalize_worker()
        assert readiness._worker_cleanup_deadline == fixed
        assert signals == [signal.SIGINT, signal.SIGTERM, signal.SIGKILL]
        assert readiness._cleanup_deadline_violation
        assert readiness._residue == 'UNKNOWN'

    asyncio.run(exercise())


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


def test_parent_protocol_caps_cumulative_transcript_with_max_error_field():
    """Enforce the 64 KiB cap across a full stream, not one record."""
    readiness = RclpyReadiness()
    request = readiness._make_request(
        make_plan(), CONFIG_HASH, time.monotonic_ns() + 5_000_000_000,
    )
    readiness._active_request = request
    readiness.bind_evidence_sink(Sink())
    digest, cycle = protocol_transcript(
        request, scene_outcome='ERROR', ready=False,
    )
    first_cycle = cycle[:-1]
    for record in first_cycle:
        if record['event'] == 'scene_query_finished':
            record['facts']['error'] = 'x' * 256
            record['facts']['world_name'] = None
            record['facts']['matching_model_count'] = 0
    records = []
    for cycle_index in range(70):
        selected = first_cycle if cycle_index == 0 else first_cycle[1:]
        records.extend(dict(record) for record in selected)
    terminal = dict(cycle[-1])
    records.append(terminal)
    for sequence, record in enumerate(records, 1):
        record['sequence'] = sequence
        record['request_sha256'] = digest
    lines = [json.dumps(record).encode() + b'\n' for record in records]
    assert max(map(len, lines)) <= readiness.MAX_RECORD_BYTES
    payload = b''.join(lines)
    assert len(payload) > readiness.MAX_STREAM_BYTES
    chunks = [payload[offset:offset + 2048]
              for offset in range(0, len(payload), 2048)]
    readiness._worker = SimpleNamespace(stdout=ChunkStream(chunks))
    asyncio.run(readiness._drain_stdout(request['request_id'], digest))
    assert readiness._stdout_total == len(payload)
    assert 'worker stdout exceeded 64 KiB' in readiness._protocol_error


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


@pytest.mark.parametrize('case', [
    'ready_sequence_one', 'missing_status_wait', 'missing_status_stage',
    'query_finish_without_start', 'missing_query_finish',
    'ready_after_mismatch', 'ready_after_query_error',
    'terminal_facts_disagree', 'duplicate_result', 'output_after_terminal',
])
def test_protocol_drainer_rejects_invalid_ready_history(case):
    """Validate the entire event history rather than terminal READY alone."""
    readiness = RclpyReadiness()
    request = readiness._make_request(
        make_plan(), CONFIG_HASH, time.monotonic_ns() + 5_000_000_000,
    )
    readiness._active_request = request
    sink = Sink()
    readiness.bind_evidence_sink(sink)
    digest, records = protocol_transcript(request)
    if case == 'ready_sequence_one':
        records = [records[-1]]
    elif case == 'missing_status_wait':
        records = [record for record in records
                   if record['event'] != 'status_wait_started']
    elif case == 'missing_status_stage':
        records = [record for record in records
                   if record['event'] != 'status_matched']
    elif case == 'query_finish_without_start':
        records = [record for record in records
                   if record['event'] != 'scene_query_started']
    elif case == 'missing_query_finish':
        records = [record for record in records
                   if record['event'] != 'scene_query_finished']
    elif case == 'ready_after_mismatch':
        digest, records = protocol_transcript(
            request, scene_outcome='MISMATCH',
        )
    elif case == 'ready_after_query_error':
        digest, records = protocol_transcript(
            request, scene_outcome='ERROR',
        )
    elif case == 'terminal_facts_disagree':
        records[-1]['facts']['facts']['status'] = {
            **records[-1]['facts']['facts']['status'],
            'status_sequence': 2,
        }
    elif case in {'duplicate_result', 'output_after_terminal'}:
        extra = dict(records[-1])
        extra['sequence'] = len(records) + 1
        if case == 'output_after_terminal':
            extra['event'] = 'worker_started'
        records.append(extra)
    for sequence, record in enumerate(records, 1):
        record['sequence'] = sequence
        record['request_sha256'] = digest
    raw = b''.join(json.dumps(record).encode() + b'\n'
                   for record in records)
    readiness._worker = SimpleNamespace(stdout=ChunkStream([raw]))
    asyncio.run(readiness._drain_stdout(request['request_id'], digest))
    assert readiness._protocol_error is not None


@pytest.mark.parametrize('early_fail', [False, True])
def test_protocol_drainer_accepts_full_ready_and_early_fail(early_fail):
    """Accept only a complete matching READY history or active early FAIL."""
    readiness = RclpyReadiness()
    request = readiness._make_request(
        make_plan(), CONFIG_HASH, time.monotonic_ns() + 5_000_000_000,
    )
    readiness._active_request = request
    readiness.bind_evidence_sink(Sink())
    digest, records = protocol_transcript(request, ready=not early_fail)
    if early_fail:
        records = [records[0], records[-1]]
        records[1]['sequence'] = 2
    raw = b''.join(json.dumps(record).encode() + b'\n'
                   for record in records)
    readiness._worker = SimpleNamespace(stdout=ChunkStream([raw]))
    asyncio.run(readiness._drain_stdout(request['request_id'], digest))
    assert readiness._protocol_error is None
    assert readiness._protocol_state == 'TERMINAL'


def test_parent_entry_rejects_ready_without_protocol_history(monkeypatch):
    """The production parent entry rejects a forged terminal-only READY."""
    class Input:
        def __init__(self, stream):
            """Bind the fake stdin to its paired stdout protocol stream."""
            self.stream = stream
            self.data = bytearray()
            self.closed = False

        def write(self, data):
            """Retain the exact request bytes sent by the parent."""
            self.data.extend(data)

        async def drain(self):
            """Complete request draining immediately."""
            return None

        def is_closing(self):
            """Report whether the parent closed stdin."""
            return self.closed

        def close(self):
            """Mark stdin closed for the paired worker fake."""
            self.closed = True

        async def wait_closed(self):
            """Publish a deliberately terminal-only READY result."""
            request = strict_json_loads(bytes(self.data).rstrip(b'\n'))
            digest = hashlib.sha256(
                canonical_request_bytes(request)
            ).hexdigest()
            binding = {key: request[key] for key in (
                'session_id', 'config_hash', 'asset_manifest_sha256',
                'coordinator_ingress_instance_id',
            )}
            status = {
                'world_id': request['world_id'], 'session_id': request[
                    'session_id'], 'config_hash': request['config_hash'],
                'backend_instance_id': 9, 'status_sequence': 1,
                'fault_flags': 0, 'actuator_inhibited': True,
            }
            result = {
                'schema_id': 'mecanum_b2_scene_readiness_event/v1',
                'request_id': request['request_id'],
                'request_sha256': digest, 'sequence': 1,
                'event': 'worker_result', 'monotonic_ns': time.monotonic_ns(),
                'facts': {'verdict': 'READY', 'reason': '', 'facts': {
                    'status': status, 'scene': {
                        'world_name': request['world_id'],
                        'matching_model_count': 1,
                    }, 'request_binding': binding,
                }, 'cleanup_errors': [], 'cleanup_elapsed_ns': 1},
            }
            self.stream.publish(json.dumps(result).encode() + b'\n')

    class Output:
        def __init__(self):
            """Initialize an event-driven in-memory output stream."""
            self.event = asyncio.Event()
            self.chunks = []

        def publish(self, data):
            """Queue one protocol record and wake the reader."""
            self.chunks.append(data)
            self.event.set()

        async def read(self, _size):
            """Return a queued record after it becomes available."""
            if not self.chunks:
                await self.event.wait()
            return self.chunks.pop(0) if self.chunks else b''

    class Worker:
        """Expose process and pipe interfaces required by the parent client."""

        pid = 556677
        returncode = 0

        def __init__(self):
            """Create the terminal-only fake worker."""
            self.stdout = Output()
            self.stderr = ChunkStream([])
            self.stdin = Input(self.stdout)

        async def wait(self):
            """Report successful process exit after publishing the response."""
            return 0

    worker = Worker()

    async def factory(_environment):
        return worker
    identity = {'pid': worker.pid, 'process_group_id': worker.pid,
                'session_id': worker.pid, 'start_ticks': 456}
    monkeypatch.setattr(
        supervisor.os, 'killpg',
        lambda *_args: (_ for _ in ()).throw(ProcessLookupError()),
    )
    readiness = RclpyReadiness(worker_factory=factory,
                               identity_reader=lambda _pid: identity)
    sink = Sink()
    monkeypatch.setattr(
        supervisor, 'load_bound_config',
        lambda _path: (None, CONFIG_HASH, MANIFEST_HASH, 'B2_SOAK_V1'),
    )
    LocalTrainingProcessSupervisor(
        plan=make_plan(), launcher=object(), readiness=readiness,
        evidence_sink=sink,
    )
    with pytest.raises(RuntimeError, match='worker protocol invalid'):
        asyncio.run(readiness.server_scene(make_plan(), ServerProcess(), 1.0))
    assert readiness._residue == 'NONE'


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
    with pytest.raises((RuntimeError, TimeoutError)):
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
    with pytest.raises(OSError, match='identity unavailable'):
        asyncio.run(readiness.server_scene(make_plan(), ServerProcess(), 0.05))
    assert sent == []
    assert readiness._process_residue == 'UNKNOWN'
    assert readiness._residue == 'UNKNOWN'
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
