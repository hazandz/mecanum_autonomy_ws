"""RUN007 guard, mailbox, observer, and orchestration regressions."""
from __future__ import annotations

import asyncio
import hashlib
import importlib
import json
import multiprocessing
import os
import signal
import socket
import subprocess
import sys
import time
import uuid
from collections import deque
from dataclasses import make_dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest
HERE = Path(__file__).resolve().parent
BUNDLE = HERE.parent
PACKET = BUNDLE / 'packet.json'
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
for import_root in (
        Path('/tmp/b22-run005-fresh-d6dc1c9/install')
        / 'lib/python3.12/site-packages',
        Path('/opt/ros/jazzy/lib/python3.12/site-packages')):
    if import_root.is_dir() and str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))
guard = importlib.import_module('observation_guard')
runner = importlib.import_module('observation_runner')
sink = importlib.import_module('observation_sink')


def bundle_packet():
    """Test helper for RUN007 offline behavior."""
    return json.loads(PACKET.read_text(encoding='utf-8'))


def tools_hashes():
    """Test helper for RUN007 offline behavior."""
    return guard.tool_hashes(runner.TOOL_PATHS)


def _readiness_worker_fake_child(request, result_queue):
    """Run the installed worker with child-local middleware fakes."""
    import os

    import mecanum_nav_bringup.local_training_readiness_worker as worker

    os.environ['GZ_PARTITION'] = request['gz_partition']
    os.environ['ROS_DOMAIN_ID'] = request['ros_domain_id']

    class FakeSource:
        def __init__(self):
            self.sent = False

        def start(self):
            return None

        def next_status(self, _timeout_s):
            if self.sent:
                return None
            self.sent = True
            return SimpleNamespace(
                header=SimpleNamespace(frame_id=request['world_id']),
                session_id=request['session_id'],
                config_hash=request['config_hash'],
                backend_instance_id=5, status_sequence=1,
                fault_flags=0, actuator_inhibited=True,
            )

        def close(self):
            return None

    class FakeScene:
        def __init__(self):
            self.name = ''
            self.model = [SimpleNamespace(
                name=request['model_id'], model=[],
            )]

    class FakeEmitter:
        def __init__(self):
            self.records = []

        def emit(self, event, facts):
            self.records.append((event, facts))

    emitter = FakeEmitter()
    result = worker.run_worker(
        request, status_source_factory=FakeSource,
        scene_query=lambda _service, _timeout_ms: FakeScene(),
        emitter=emitter,
    )
    result_queue.put((result, emitter.records))


def test_actual_bundle_packet_validates_complete_run007_schema():
    """Test helper for RUN007 offline behavior."""
    packet = bundle_packet()
    bindings = guard.packet_bindings(packet, tools_hashes())
    assert packet['run_id'] == guard.RUN_ID
    assert packet['runtime_authorization'] == 'NOT_GRANTED'
    assert (
        packet['repository']['remote_status_at_executor']
        == 'VERIFIED_DIRECT_READBACK'
    )
    assert len(bindings['file_sha256']) == packet['installation']['file_count']
    worker_path = packet['installation']['resolved_paths'][
        'readiness_worker'
    ]
    assert bindings['file_sha256'][worker_path] == (
        '94ac394d282cae0b419b766220bf836309ba377d25617a6f6ab6015a6be1d948'
    )
    assert bindings['production_source_pin'] == guard.PRODUCTION_SOURCE_PIN
    assert packet['timing']['review_checkpoint_s'] == 60
    assert packet['acceptance']['owner_visual_review'] == 'NOT_PERFORMED'
    assert packet['composition']['startup_helper_roles'] == [
        'readiness_worker',
    ]
    assert packet['repository']['remote_candidate_sha'] == guard.STARTING_HEAD


def test_installed_worker_module_runs_in_child_with_fake_middleware():
    """Exercise the production worker in an isolated fake-only child."""
    request = {
        'schema_id': 'mecanum_b2_scene_readiness_request/v1',
        'request_id': str(uuid.uuid4()), 'session_id': str(uuid.uuid4()),
        'config_hash': 'c' * 64, 'asset_manifest_sha256': 'd' * 64,
        'coordinator_ingress_instance_id': 7,
        'world_id': 'b2_training_arena', 'model_id': 'mecanum_b2',
        'gz_partition': 'mecanum_b2_fakechild', 'ros_domain_id': '83',
        'deadline_monotonic_ns': time.monotonic_ns() + 5_000_000_000,
    }
    context = multiprocessing.get_context('fork')
    result_queue = context.Queue()
    process = context.Process(
        target=_readiness_worker_fake_child,
        args=(request, result_queue),
    )
    process.start()
    process.join(4)
    if process.is_alive():
        process.terminate()
        process.join(1)
        pytest.fail('fake readiness worker child did not exit')
    assert process.exitcode == 0
    result, records = result_queue.get(timeout=1)
    assert result == 0
    assert [event for event, _facts in records] == [
        'worker_started', 'status_wait_started', 'status_matched',
        'scene_query_started', 'scene_query_finished', 'worker_result',
    ]
    assert records[-1][1]['verdict'] == 'READY'


def test_packet_missing_field_rejects_before_any_acquisition(tmp_path):
    """Test helper for RUN007 offline behavior."""
    packet = bundle_packet()
    del packet['composition']
    with pytest.raises(guard.GuardError, match='canonical schema'):
        guard.packet_bindings(packet, tools_hashes())
    assert list(tmp_path.iterdir()) == []


def test_packet_wrong_source_pin_or_alternate_schema_rejects():
    """Test helper for RUN007 offline behavior."""
    packet = bundle_packet()
    packet['repository']['production_source_pin'] = '0' * 40
    with pytest.raises(guard.GuardError, match='repository pins'):
        guard.packet_bindings(packet, tools_hashes())
    packet = bundle_packet()
    packet['production_source_pin'] = guard.PRODUCTION_SOURCE_PIN
    with pytest.raises(guard.GuardError, match='canonical schema'):
        guard.packet_bindings(packet, tools_hashes())


def test_packet_rejects_changed_tool_hash_and_input_pin():
    """Test helper for RUN007 offline behavior."""
    packet = bundle_packet()
    wrong = dict(tools_hashes())
    wrong['observation_runner.py'] = '0' * 64
    with pytest.raises(guard.GuardError, match='tool hashes'):
        guard.packet_bindings(packet, wrong)
    packet = bundle_packet()
    packet['inputs']['config_hash'] = '0' * 64
    with pytest.raises(guard.GuardError, match='input pins'):
        guard.packet_bindings(packet, tools_hashes())
    packet = bundle_packet()
    packet['installation']['dependency_fingerprints']['backend_source'][
        'fingerprint_sha256'
    ] = '0' * 64
    with pytest.raises(guard.GuardError, match='backend source fingerprint'):
        guard.packet_bindings(packet, tools_hashes())


def test_packet_coordinator_id_contract_is_typed_uint64_policy():
    """Test helper for RUN007 offline behavior."""
    packet = bundle_packet()
    assert packet['identity']['coordinator_ingress_instance_id'].endswith(
        'uint64 generated once before participant creation'
    )
    assert packet['identity']['session_id'].startswith('canonical UUID')
    fake_values = [True, 0, -1, 1 << 64]
    for value in fake_values:
        with pytest.raises(guard.GuardError):
            guard._integer(value, 'coordinator', minimum=1,
                           maximum=(1 << 64) - 1)
    assert guard._integer(1, 'coordinator', minimum=1,
                          maximum=(1 << 64) - 1) == 1


def test_strict_json_rejects_duplicate_keys_nonfinite_and_trailing_data():
    """Test helper for RUN007 offline behavior."""
    for raw in (b'{"x":1,"x":2}', b'{"x":NaN}', b'{} {}'):
        with pytest.raises(guard.GuardError):
            guard.strict_json_loads(raw)


def test_gui_parser_is_strict_and_run007_rejects_false_before_side_effect():
    """Test helper for RUN007 offline behavior."""
    assert runner.strict_gui_value('true') is True
    assert runner.strict_gui_value('false') is False
    for value in ('True', '1', 'yes', ''):
        with pytest.raises(Exception):
            runner.strict_gui_value(value)
    with pytest.raises(runner.ObservationFailure, match='requires --gui true'):
        runner.require_run_gui(False)


def test_production_paths_are_fixed_but_internal_test_root_is_injectable(
    tmp_path,
):
    """Test helper for RUN007 offline behavior."""
    root = tmp_path / 'test-evidence'
    root.mkdir(mode=448)
    guard_path = root / 'acquisition.json'
    assert runner.validate_run_roots(
        guard_path, root, expected_guard=guard_path,
        expected_evidence=root,
    ) == (guard_path, root)
    with pytest.raises(guard.GuardError, match='override'):
        runner.validate_run_roots(guard_path, root,
                                  expected_guard=guard.GUARD_PATH,
                                  expected_evidence=guard.EVIDENCE_ROOT)


def test_symlink_root_and_existing_partial_guard_fail_closed(tmp_path):
    """Test helper for RUN007 offline behavior."""
    target = tmp_path / 'target'
    target.mkdir()
    alias = tmp_path / 'alias'
    alias.symlink_to(target, target_is_directory=True)
    with pytest.raises(guard.GuardError, match='symlink'):
        guard.validate_run_roots(alias / 'acquisition.json', alias,
                                 expected_guard=alias / 'acquisition.json',
                                 expected_evidence=alias)
    path = target / 'acquisition.json'
    path.write_bytes(b'')
    with pytest.raises(guard.GuardError, match='already exists'):
        guard.acquire_once(path, {'run_id': 'TEST_ONLY'})
    assert path.read_bytes() == b''


def test_capacity_one_two_contenders_and_replay(tmp_path):
    """Test helper for RUN007 offline behavior."""
    path = tmp_path / 'acquisition.json'
    outcomes = []
    import concurrent.futures

    def acquire(index):
        """Test helper for RUN007 offline behavior."""
        try:
            guard.acquire_once(path, {'run_id': 'RUN007_TEST',
                                      'contender': index})
            return 'won'
        except guard.GuardError:
            return 'lost'
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        outcomes.extend(pool.map(acquire, (1, 2)))
    assert sorted(outcomes) == ['lost', 'won']
    before = path.read_bytes()
    with pytest.raises(guard.GuardError, match='already exists'):
        guard.acquire_once(path, {'run_id': 'RUN007_TEST', 'contender': 3})
    assert path.read_bytes() == before


def test_partial_acquisition_is_never_repaired_or_reused(tmp_path):
    """Test helper for RUN007 offline behavior."""
    path = tmp_path / 'acquisition.json'
    path.write_bytes(b'{partial')
    with pytest.raises(guard.GuardError, match='already exists'):
        guard.acquire_once(path, {'run_id': 'RUN007_TEST'})
    assert path.read_bytes() == b'{partial'


def request_fixture(root, *, packet_hash='a' * 64, session_id=None,
                    steady_ns=1000000000):
    """Test helper for RUN007 offline behavior."""
    session_id = session_id or str(uuid.uuid4())
    request_id = str(uuid.uuid4())
    req_dir = root / 'review_mailbox' / 'requests'
    result_dir = root / 'review_mailbox' / 'results'
    screenshot_dir = root / 'screenshots'
    for path in (root / 'review_mailbox', req_dir, result_dir, screenshot_dir):
        path.mkdir(mode=448, exist_ok=True)
    image = b'not-a-real-runtime-image; offline fixture only'
    image_hash = hashlib.sha256(image).hexdigest()
    image_path = screenshot_dir / f'{request_id}-{image_hash}.png'
    runner.atomic_publish(image_path, image)
    now_ns = steady_ns
    request = {
        'schema_id': 'b22_gui_codex_review_request/v1',
        'schema_version': 1,
        'run_id': guard.RUN_ID,
        'session_id': session_id,
        'packet_sha256': packet_hash,
        'review_request_id': request_id,
        'screenshot_path': str(image_path),
        'screenshot_sha256': hashlib.sha256(image).hexdigest(),
        'window_process_identity': {
            'evidence_sequence': 4,
            'window_id': '0x000010',
            'pid': 101,
            'pgid': 101,
            'process_start_ticks': 71,
            'gz_partition': (
                f"mecanum_b2_{session_id.replace('-', '')}"
            ),
        },
        'request_created_utc': '2026-11-02T00:00:00Z',
        'request_created_steady_ns': now_ns,
        'review_deadline_steady_ns': now_ns + 60000000000,
        'result_path': str(result_dir / f'{request_id}.json'),
    }
    data = (
        json.dumps(request, sort_keys=True, separators=(',', ':')) + '\n'
    ).encode()
    request_path = req_dir / f'{request_id}.json'
    runner.atomic_publish(request_path, data)
    return (request_path, data, request, image)


def test_review_request_schema_paths_and_binding(tmp_path):
    """Test helper for RUN007 offline behavior."""
    path, data, request, _ = request_fixture(tmp_path)
    loaded = guard.strict_json_loads(runner.read_published(path))
    assert runner.validate_review_request(
        loaded, evidence_root=tmp_path,
        packet_hash=request['packet_sha256'],
        session_id=request['session_id'],
    ) == request
    assert len(data) < 16 * 1024
    changed = dict(request)
    changed['result_path'] = '/tmp/other.json'
    with pytest.raises(runner.ObservationFailure, match='result_path'):
        runner.validate_review_request(changed, evidence_root=tmp_path,
                                       packet_hash=request['packet_sha256'],
                                       session_id=request['session_id'])


def test_mailbox_rejects_extra_field_wrong_hash_and_wrong_run(tmp_path):
    """Test helper for RUN007 offline behavior."""
    _, _, request, _ = request_fixture(tmp_path)
    for key, value in (('extra', 1), ('run_id', 'B22_GUI_OBSERVATION_RUN001'),
                       ('screenshot_sha256', '0' * 64)):
        altered = dict(request)
        altered[key] = value
        with pytest.raises(runner.ObservationFailure):
            runner.validate_review_request(
                altered, evidence_root=tmp_path,
                packet_hash=request['packet_sha256'],
                session_id=request['session_id'],
            )


def result_for(request_bytes, request, *, verdict='PASS'):
    """Test helper for RUN007 offline behavior."""
    return {
        'schema_id': 'b22_gui_codex_review_result/v1',
        'schema_version': 1,
        'run_id': request['run_id'],
        'session_id': request['session_id'],
        'packet_sha256': request['packet_sha256'],
        'review_request_id': request['review_request_id'],
        'request_sha256': hashlib.sha256(request_bytes).hexdigest(),
        'screenshot_sha256': request['screenshot_sha256'],
        'reviewer_kind': 'CODEX',
        'verdict': verdict,
        'reason': 'rendered world and robot visible in the supplied capture',
        'viewer_interaction_ref': None,
        'viewer_ref_state': 'TOOL_NO_STABLE_REFERENCE',
        'result_created_utc': '2026-11-02T00:00:01Z',
    }


def test_result_schema_binding_and_late_result_rejection(tmp_path):
    """Test helper for RUN007 offline behavior."""
    _, request_bytes, request, _ = request_fixture(tmp_path)
    result = result_for(request_bytes, request)
    assert runner.validate_review_result(
        result, request_bytes, request,
        now_ns=request['request_created_steady_ns'] + 2,
    ) == result
    with pytest.raises(runner.ReviewInvalidated, match='late|deadline'):
        runner.validate_review_result(
            result, request_bytes, request,
            now_ns=request['review_deadline_steady_ns'],
        )
    result['request_sha256'] = '0' * 64
    with pytest.raises(runner.ObservationFailure, match='request_sha256'):
        runner.validate_review_result(
            result, request_bytes, request,
            now_ns=request['request_created_steady_ns'] + 2,
        )


def test_result_worker_hashes_screenshot_and_publishes_once(tmp_path):
    """Test helper for RUN007 offline behavior."""
    request_path, _, request, _ = request_fixture(tmp_path)
    result_path = Path(request['result_path'])
    assert runner.publish_review_result_worker(request_path, verdict='PASS',
                                               reason='scene visible',
                                               root=tmp_path) == result_path
    data = runner.read_published(result_path)
    result = guard.strict_json_loads(data)
    assert result['reviewer_kind'] == 'CODEX'
    assert result['verdict'] == 'PASS'
    with pytest.raises(FileExistsError):
        runner.publish_review_result_worker(request_path, verdict='FAIL',
                                            reason='different result',
                                            root=tmp_path)
    assert runner.read_published(result_path) == data


def test_result_worker_refuses_changed_screenshot(tmp_path):
    """Test helper for RUN007 offline behavior."""
    request_path, _, request, _ = request_fixture(tmp_path)
    Path(request['screenshot_path']).write_bytes(b'changed bytes')
    with pytest.raises(runner.ObservationFailure, match='hash changed'):
        runner.publish_review_result_worker(request_path, verdict='PASS',
                                            reason='scene visible',
                                            root=tmp_path)


def test_atomic_publication_no_overwrite_and_symlink_component(tmp_path):
    """Test helper for RUN007 offline behavior."""
    path = tmp_path / 'result.json'
    runner.atomic_publish(path, b'first')
    with pytest.raises(FileExistsError):
        runner.atomic_publish(path, b'second')
    assert runner.read_published(path) == b'first'
    destination = tmp_path / 'destination'
    destination.mkdir()
    alias = tmp_path / 'alias'
    alias.symlink_to(destination, target_is_directory=True)
    with pytest.raises(runner.ObservationFailure):
        runner.atomic_publish(alias / 'escape.json', b'no')
    assert not (destination / 'escape.json').exists()


def test_review_wait_timeout_does_not_accept_silence(tmp_path):
    """Test helper for RUN007 offline behavior."""
    _, request_bytes, request, _ = request_fixture(tmp_path)
    clock = [0.0]

    async def tick(delay):
        """Test helper for RUN007 offline behavior."""
        clock[0] += max(delay, 0.1)
    with pytest.raises(runner.ReviewInvalidated, match='deadline'):
        asyncio.run(runner.await_codex_review(
            request_path=Path(request['result_path']),
            request_bytes=request_bytes, request=request, deadline=0.2,
            steady=lambda: clock[0], sink=None,
            read_file=lambda _p, **_kw: (
                _ for _ in ()
            ).throw(FileNotFoundError()),
            sleep=tick,
        ))


def test_review_cancel_invalidates_without_replay(tmp_path):
    """Test helper for RUN007 offline behavior."""
    _, request_bytes, request, _ = request_fixture(tmp_path)
    stop = SimpleNamespace(is_set=lambda: True)
    with pytest.raises(runner.ReviewInvalidated, match='invalidated'):
        asyncio.run(runner.await_codex_review(
            request_path=Path(request['result_path']),
            request_bytes=request_bytes, request=request, deadline=10,
            steady=lambda: 0, sink=None, stop_event=stop,
        ))


def test_bounded_publisher_requires_budget_and_runs_gated_target():
    """Publisher entry retains the budget gate and separate command facts."""
    with pytest.raises(runner.ReviewInvalidated, match='7 seconds'):
        runner.publish_review_result_bounded(
            '/tmp/request.json', verdict='PASS', reason='visible',
            request_deadline=6, steady=lambda: 0,
        )
    result = runner.publish_review_result_bounded(
        '/tmp/request.json', verdict='PASS', reason='visible',
        request_deadline=time.monotonic() + 8,
        helper_command_factory=lambda _role, _planned: _python_target(
            'print("ok", end="")'
        ),
    )
    assert result['exit_status'] == 0
    assert result['stdout'] == 'ok'
    assert result['ownership_facts'][0]['evidence_before_release'] is False


def test_publisher_timeout_escalates_only_injected_owned_group(monkeypatch):
    """A timed out gated target is stopped only through its owned group."""
    signals = []
    started = []

    def stop_group(pgid, sig):
        signals.append(sig)
        os.killpg(pgid, sig)
    with pytest.raises(runner.ObservationFailure, match='timed out'):
        runner.publish_review_result_bounded(
            '/tmp/request.json', verdict='PASS', reason='visible',
            request_deadline=time.monotonic() + 7.5,
            signal_group=stop_group, on_started=started.append,
            helper_command_factory=lambda _role, _planned: _python_target(
                'import time; time.sleep(30)'
            ),
        )
    assert signals and signals[0] == signal.SIGTERM
    assert started[0]['identity']['pid'] == started[0]['process'].pid


def test_publisher_identity_uncertainty_does_not_signal(monkeypatch):
    """Identity uncertainty fails closed before the publisher is released."""
    signals = []
    with pytest.raises(runner.ObservationFailure, match='ownership'):
        runner.publish_review_result_bounded('/tmp/request.json',
                                             verdict='PASS',
                                             reason='visible',
                                             request_deadline=(
                                                 time.monotonic() + 8
                                             ),
                                             steady=lambda: 0,
                                             popen=subprocess.Popen,
                                             identity_reader=lambda _pid: {
                                                 'pid': 1})
    assert signals == []


def test_observer_uses_its_own_context_executor_and_private_spin():
    """Test helper for RUN007 offline behavior."""
    calls = []

    class Context:

        def __init__(self):
            """Test helper for RUN007 offline behavior."""
            calls.append(('context', self))

    class Executor:

        def __init__(self, *, context):
            """Test helper for RUN007 offline behavior."""
            self.context = context
            calls.append(('executor', context))

        def add_node(self, node):
            """Test helper for RUN007 offline behavior."""
            calls.append(('add', node.context))
            return True

        def spin_once(self, timeout_sec):
            """Test helper for RUN007 offline behavior."""
            calls.append(('spin', timeout_sec))

        def remove_node(self, node):
            """Test helper for RUN007 offline behavior."""
            calls.append(('remove', node.context))

        def shutdown(self, timeout_sec):
            """Test helper for RUN007 offline behavior."""
            calls.append(('executor_shutdown', timeout_sec))
            return True

    class Node:

        def __init__(self, name, *, context):
            """Test helper for RUN007 offline behavior."""
            self.context = context
            calls.append(('node', name, context))

        def create_subscription(self, *args):
            """Test helper for RUN007 offline behavior."""
            calls.append(('subscription', args[1], args[3]))
            return object()

        def destroy_node(self):
            """Test helper for RUN007 offline behavior."""
            calls.append(('destroy_node', self.context))

        def get_node_names_and_namespaces(self):
            """Test helper for RUN007 offline behavior."""
            return []

    class Rclpy:

        def init(self, *, context, domain_id):
            """Test helper for RUN007 offline behavior."""
            calls.append(('init', context, domain_id))

        def ok(self, *, context):
            """Test helper for RUN007 offline behavior."""
            return True

        def shutdown(self, *, context):
            """Test helper for RUN007 offline behavior."""
            calls.append(('context_shutdown', context))

        def spin_once(self, *_args, **_kwargs):
            """Test helper for RUN007 offline behavior."""
            raise AssertionError('global spin forbidden')

    class QoS:

        def __init__(self, **kwargs):
            """Test helper for RUN007 offline behavior."""
            self.kwargs = kwargs
    api = SimpleNamespace(rclpy=Rclpy(), Context=Context,
                          SingleThreadedExecutor=Executor, Node=Node,
                          SimulationContactState=object, Clock=object,
                          QoSProfile=QoS,
                          HistoryPolicy=SimpleNamespace(KEEP_LAST='KEEP_LAST'),
                          ReliabilityPolicy=SimpleNamespace(
                              BEST_EFFORT='BEST_EFFORT'),
                          DurabilityPolicy=SimpleNamespace(
                              VOLATILE='VOLATILE'))
    observer = runner.PassiveBackendObserver(ros_api_factory=lambda: api)
    observer.start()
    observer.spin_once(0.01)
    context = observer.context
    assert observer.executor.context is context
    assert observer.node.context is context
    qos = next(item[2] for item in calls
               if item[0] == 'subscription' and item[1] == '/clock')
    assert qos.kwargs == {'history': 'KEEP_LAST', 'depth': 10,
                          'reliability': 'BEST_EFFORT',
                          'durability': 'VOLATILE'}
    observer.close()
    observer.close()
    release_calls = [item[0] for item in calls
                     if item[0] in ('remove', 'executor_shutdown',
                                    'destroy_node', 'context_shutdown')]
    assert release_calls == [
        'remove', 'executor_shutdown', 'destroy_node', 'context_shutdown']


def test_observer_partial_initialization_cleanup_and_release_errors():
    """Test helper for RUN007 offline behavior."""
    calls = []

    class Context:

        def __init__(self):
            """Test helper for RUN007 offline behavior."""
            calls.append('context')

    class Executor:

        def __init__(self, *, context):
            """Test helper for RUN007 offline behavior."""
            self.context = context
            calls.append('executor')

        def add_node(self, node):
            """Test helper for RUN007 offline behavior."""
            return True

        def remove_node(self, node):
            """Test helper for RUN007 offline behavior."""
            calls.append('remove')

        def shutdown(self, timeout_sec):
            """Test helper for RUN007 offline behavior."""
            calls.append('executor_shutdown')
            raise RuntimeError('injected')

    class Node:

        def __init__(self, name, *, context):
            """Test helper for RUN007 offline behavior."""
            self.context = context
            calls.append('node')

        def create_subscription(self, *args):
            """Test helper for RUN007 offline behavior."""
            return object()

        def destroy_node(self):
            """Test helper for RUN007 offline behavior."""
            calls.append('destroy_node')

    class Rclpy:

        def init(self, *, context, domain_id):
            """Test helper for RUN007 offline behavior."""
            calls.append('init')

        def ok(self, *, context):
            """Test helper for RUN007 offline behavior."""
            return True

        def shutdown(self, *, context):
            """Test helper for RUN007 offline behavior."""
            calls.append('context_shutdown')

    class QoS:

        def __init__(self, **kwargs):
            """Test helper for RUN007 offline behavior."""
            pass
    api = SimpleNamespace(rclpy=Rclpy(), Context=Context,
                          SingleThreadedExecutor=Executor, Node=Node,
                          SimulationContactState=object, Clock=object,
                          QoSProfile=QoS,
                          HistoryPolicy=SimpleNamespace(KEEP_LAST=1),
                          ReliabilityPolicy=SimpleNamespace(BEST_EFFORT=2),
                          DurabilityPolicy=SimpleNamespace(VOLATILE=3))
    observer = runner.PassiveBackendObserver(ros_api_factory=lambda: api)
    observer.start()
    with pytest.raises(runner.ObservationFailure, match='cleanup failed'):
        observer.close()
    observer.close()
    assert 'destroy_node' in calls and 'context_shutdown' in calls


def test_clock_and_backend_health_facts_are_required_after_review():
    """Test helper for RUN007 offline behavior."""

    class FakeObserver:

        def __init__(self):
            """Test helper for RUN007 offline behavior."""
            self.events = deque()
            self.samples = 0

        def spin_once(self, _timeout):
            """Test helper for RUN007 offline behavior."""
            self.samples += 1
            now = clock[0]
            self.events.append(('clock', SimpleNamespace(sec=1, nanosec=2),
                                now, int(now * 1000000000.0)))
            status = SimpleNamespace(
                session_id=session,
                config_hash=config,
                backend_instance_id='backend-1',
                header=SimpleNamespace(frame_id='b2_training_arena'),
                paused=True,
                actuator_inhibited=True,
                fault_flags=0,
                applied_receipt_valid=False,
                status_sequence=self.samples)
            self.events.append(('backend', status, now,
                                int(now * 1000000000.0)))
            clock[0] += 0.1

        def node_inventory(self):
            """Test helper for RUN007 offline behavior."""
            return list(runner.EXPECTED_ROS_NODES)
    from collections import deque
    clock = [0.0]
    session = str(uuid.uuid4())
    config = 'c' * 64
    event = SimpleNamespace(is_set=lambda: clock[0] >= 0.2)
    plan = SimpleNamespace(session_id=session, config_hash=config)
    result = asyncio.run(
        runner.evaluate_observation(
            plan=plan, observer=FakeObserver(), duration_s=0.2,
            steady=lambda: clock[0], ack_event=event, deadline=5, sink=None,
            readiness_complete_event=SimpleNamespace(
                is_set=lambda: True)))
    assert (result['automated_observation_verdict']
            if 'automated_observation_verdict' in result
            else result['backend_status_samples'] > 0)
    assert result['clock_samples'] > 0


def test_invalid_backend_status_is_persisted_before_validation_failure():
    """Keep the triggering receive fact before reporting its failure."""
    from collections import deque

    received = 4.25
    status = SimpleNamespace(
        session_id='wrong-session', config_hash='c' * 64,
        backend_instance_id=9,
        header=SimpleNamespace(frame_id='b2_training_arena'),
        status_sequence=12, paused=True, actuator_inhibited=True,
        fault_flags=0, applied_receipt_valid=False,
    )

    class Observer:
        events = deque([('backend', status, received, 4_250_000_000)])

        def spin_once(self, _timeout):
            return None

    class Sink:
        def __init__(self):
            self.records = []

        def record(self, event, facts):
            self.records.append((event, facts))

    sink_recorder = Sink()
    plan = SimpleNamespace(session_id='expected', config_hash='c' * 64)
    with pytest.raises(runner.ObservationFailure, match='identity mismatch'):
        asyncio.run(runner.evaluate_observation(
            plan=plan, observer=Observer(), duration_s=0, steady=lambda: 5,
            deadline=10, sink=sink_recorder,
        ))
    names = [name for name, _facts in sink_recorder.records]
    assert names[:2] == [
        'backend_status_sample', 'backend_status_validation_failed',
    ]
    sample = sink_recorder.records[0][1]
    failure = sink_recorder.records[1][1]
    assert sample['validation_state'] == 'RECEIVED_NOT_VALIDATED'
    assert sample['received_sample_index'] == failure['sample_index'] == 1
    assert sample['receive_steady_ns'] == failure['receive_steady_ns']
    assert failure['detection_steady_ns'] >= sample['processing_steady_ns']


def test_clock_sample_is_persisted_before_clock_gap_failure():
    """Retain the clock callback that trips the local receive-gap gate."""
    from collections import deque

    class Observer:
        events = deque([
            ('clock', SimpleNamespace(sec=0, nanosec=0), 1.0, 1_000_000_000),
            ('clock', SimpleNamespace(sec=0, nanosec=0), 2.1, 2_100_000_000),
        ])

        def spin_once(self, _timeout):
            return None

    class Sink:
        def __init__(self):
            self.records = []

        def record(self, event, facts):
            self.records.append((event, facts))

    recorder = Sink()
    with pytest.raises(runner.ObservationFailure, match='clock sample gap'):
        asyncio.run(runner.evaluate_observation(
            plan=SimpleNamespace(session_id='s', config_hash='c'),
            observer=Observer(), duration_s=0, steady=lambda: 2.2,
            deadline=10, sink=recorder,
        ))
    assert [name for name, _ in recorder.records] == [
        'clock_sample', 'clock_sample', 'clock_validation_failed',
    ]
    assert recorder.records[1][1]['validation_state'] == (
        'RECEIVED_NOT_VALIDATED'
    )
    assert recorder.records[-1][1]['sample_index'] == 2


def test_run007_readiness_adapter_forwards_sink_without_delegate_env_api():
    """Use canonical readiness binding names and mark completion on success."""
    class Delegate:
        def __init__(self):
            self.sink = None
            self.calls = []

        def bind_evidence_sink(self, evidence_sink):
            self.sink = evidence_sink

        async def server_scene(self, _plan, _process, _timeout):
            self.calls.append('server_scene')

        async def gui_process_started(self, *_args):
            self.calls.append('gui_ready')

    environment = {'ROS_DOMAIN_ID': '83', 'GZ_PARTITION': 'partition'}
    delegate = Delegate()
    complete = asyncio.Event()
    adapter = runner.ReadinessAdapter(delegate, complete, environment)
    sink_obj = object()
    adapter.bind_evidence_sink(sink_obj)
    adapter.bind_environment(environment)
    asyncio.run(adapter.server_scene(
        SimpleNamespace(environment=environment), object(), 30,
    ))
    assert delegate.sink is sink_obj
    assert delegate.calls == ['server_scene']
    assert complete.is_set()


def test_review_result_write_failure_cannot_be_passed_by_waiter(tmp_path):
    """Test helper for RUN007 offline behavior."""
    _, request_bytes, request, _ = request_fixture(tmp_path)

    def fail_read(_path, **_kwargs):
        """Test helper for RUN007 offline behavior."""
        raise OSError('evidence read failed')
    with pytest.raises(OSError):
        asyncio.run(runner.await_codex_review(
            request_path=Path(request['result_path']),
            request_bytes=request_bytes, request=request, deadline=1,
            steady=lambda: 0, sink=None, read_file=fail_read))


def test_production_cli_has_no_root_or_owner_input_override():
    """Test helper for RUN007 offline behavior."""
    parser = runner.parse_args(['--gui', 'true', '--approved-commit',
                                'a' * 40])
    assert parser.gui is True
    assert not hasattr(parser, 'approval_file')
    assert not hasattr(parser, 'packet')
    assert not hasattr(parser, 'evidence_root')
    with pytest.raises(SystemExit):
        runner.parse_args(['--gui', 'true', '--approved-commit', 'a' * 40,
                           '--approval-file', '/tmp/approval.json'])


def test_owner_ack_tokens_and_control_operations_absent_from_runner_source():
    """Test helper for RUN007 offline behavior."""
    source = Path(runner.__file__).read_text(encoding='utf-8')
    for forbidden in ('OWNER_ACK_SCENE', 'OWNER_ABORT_GUI',
                      'create_publisher(', 'create_client(', 'world_control',
                      'set_pose', 'rearm'):
        assert forbidden not in source


def test_review_deadline_is_absolute_and_duplicate_read_does_not_refresh(
        tmp_path):
    """Test helper for RUN007 offline behavior."""
    _, request_bytes, request, _ = request_fixture(tmp_path)
    result = result_for(request_bytes, request)
    result_path = Path(request['result_path'])
    runner.atomic_publish(
        result_path,
        (
            json.dumps(
                result, sort_keys=True, separators=(',', ':'),
            ) + '\n'
        ).encode(),
    )
    initial_deadline = request['review_deadline_steady_ns']
    seen = []

    async def observe():
        """Test helper for RUN007 offline behavior."""
        accepted = await runner.await_codex_review(
            request_path=Path(request['result_path']),
            request_bytes=request_bytes, request=request, deadline=10,
            steady=lambda: 0, sink=None,
            monotonic_ns=lambda: request['request_created_steady_ns'] + 1)
        seen.append(accepted)
    asyncio.run(observe())
    assert request['review_deadline_steady_ns'] == initial_deadline
    assert len(seen) == 1


def make_runner_inputs(
        tmp_path, *, startup_failure=False, production_supervisor=False):
    """Build _run dependencies entirely from local fakes and temp files."""
    packet = bundle_packet()
    packet_path = tmp_path / 'packet.json'
    packet_path.write_bytes(PACKET.read_bytes())
    hashes = tools_hashes()
    packet_hash = hashlib.sha256(packet_path.read_bytes()).hexdigest()
    commit = 'a' * 40
    approval_path = tmp_path / 'approval.json'
    approval_path.write_text(json.dumps({'schema_id': guard.APPROVAL_SCHEMA_ID,
                                         'run_id': guard.RUN_ID,
                                         'packet_sha256': packet_hash,
                                         'packet_commit': commit,
                                         'production_source_pin':
                                             guard.PRODUCTION_SOURCE_PIN,
                                         'tool_sha256': hashes}))
    root = tmp_path / 'evidence'
    guard_path = root / 'acquisition.json'
    events = []
    processes = []
    counter = [900000]
    state = {
        'capture_started': asyncio.Event(),
        'capture_released': asyncio.Event(),
        'capture_cancelled': [],
        'owner_ack_calls': [],
        'readiness_failure': None,
    }
    png = (b'\x89PNG\r\n\x1a\n' + b'\x00\x00\x00\rIHDR'
           + (2).to_bytes(4, 'big') + (1).to_bytes(4, 'big') + b'fixture')

    class FakeProcess:

        def __init__(self, pid, command):
            """Test helper for RUN007 offline behavior."""
            self.pid = pid
            self.command = tuple(command)
            self.returncode = None
            self.event = asyncio.Event()

        async def wait(self):
            """Test helper for RUN007 offline behavior."""
            await self.event.wait()
            return self.returncode

        async def communicate(self):
            """Test helper for RUN007 offline behavior."""
            if '--capture-worker' in self.command:
                state['capture_started'].set()
                if state.get('capture_hang'):
                    try:
                        await state['capture_released'].wait()
                    except asyncio.CancelledError:
                        state['capture_cancelled'].append(self.pid)
                        raise
                self.finish()
                return (png, b'')
            return (b'', b'')

        def finish(self, status=0):
            """Test helper for RUN007 offline behavior."""
            self.returncode = status
            self.event.set()

    class FakeLauncher:

        async def start(self, command, environment):
            """Test helper for RUN007 offline behavior."""
            counter[0] += 1
            proc = FakeProcess(counter[0], command)
            processes.append((tuple(command), proc))
            events.append(('spawn', runner._process_label(command)))
            return proc

        def group_alive(self, process):
            """Test helper for RUN007 offline behavior."""
            return process.returncode is None

        async def stop_group(self, process, _sig):
            """Test helper for RUN007 offline behavior."""
            process.finish()

    class FakeReadiness:

        def bind_evidence_sink(self, evidence_sink):
            """Test helper for readiness sink forwarding."""
            events.append(('bind_evidence_sink', evidence_sink))

        def bind_environment(self, environment):
            """Test helper for RUN007 offline behavior."""
            events.append(('bind_env', dict(environment)))

        async def server_scene(self, plan, process, timeout_s):
            """Test helper for RUN007 offline behavior."""
            events.append(('scene_ready', timeout_s))
            if state['readiness_failure'] == 'server':
                raise TimeoutError('injected readiness timeout')
            if state['readiness_failure'] == 'server_exit_during_cleanup':
                process.finish(0)
                raise TimeoutError('injected readiness timeout')
            if state['readiness_failure'] == 'server_exit_with_descendant':
                state['descendant_leader_pid'] = process.pid
                state['descendant_alive'] = True
                process.finish(0)
                raise TimeoutError('injected readiness timeout')
            if state['readiness_failure'] == 'server_identity_changed':
                state['identity_changed_pid'] = process.pid
                raise TimeoutError('injected readiness timeout')
            if state['readiness_failure'] == 'server_cancel':
                raise asyncio.CancelledError

        async def gui_process_started(self, plan, process, timeout_s):
            """Test helper for RUN007 offline behavior."""
            events.append(('gui_ready', timeout_s))
            if state['readiness_failure'] == 'gui':
                raise RuntimeError('injected GUI readiness failure')

        async def owner_ack(self, _timeout_s):
            """Fail if a RUN007 path accidentally requests human ACK."""
            state['owner_ack_calls'].append(True)
            raise AssertionError('RUN007 must not request Owner ACK')

    class FakeSupervisor:

        def __init__(self, *, plan, launcher, readiness, evidence_sink):
            """Test helper for RUN007 offline behavior."""
            self.plan = plan
            self.launcher = launcher
            self.readiness = readiness
            self.owned = []

        async def start(self):
            """Test helper for RUN007 offline behavior."""
            if startup_failure:
                process = await self.launcher.start(self.plan.commands[0],
                                                    self.plan.environment)
                self.owned.append(SimpleNamespace(name='server',
                                                  process=process,
                                                  output_tasks=[]))
                raise RuntimeError('injected partial startup')
            roles = {}
            self.readiness.bind_environment(self.plan.environment)
            bridge = await self.launcher.start(self.plan.bridge_command,
                                               self.plan.environment)
            bridge_record = SimpleNamespace(
                name='parameter_bridge',
                command=tuple(self.plan.bridge_command), pid=bridge.pid,
                process=bridge, output_tasks=[])
            self.owned.append(bridge_record)
            roles['parameter_bridge'] = bridge
            for command in self.plan.commands:
                process = await self.launcher.start(command,
                                                    self.plan.environment)
                record = SimpleNamespace(name=runner._process_label(command),
                                         command=tuple(command),
                                         pid=process.pid, process=process,
                                         output_tasks=[])
                self.owned.append(record)
                roles[record.name] = process
            await self.readiness.server_scene(self.plan, roles['server'], 30)
            await self.readiness.gui_process_started(self.plan, roles['gui'],
                                                     30)

        async def cleanup(self):
            """Test helper for RUN007 offline behavior."""
            events.append(('cleanup',))
            for _command, process in processes:
                process.finish()

    class FakeObserver:

        def __init__(self):
            """Test helper for RUN007 offline behavior."""
            self.closed = 0

        def start(self):
            """Test helper for RUN007 offline behavior."""
            events.append(('observer_start',))

        def close(self, **_kwargs):
            """Test helper for RUN007 offline behavior."""
            self.closed += 1
            events.append(('observer_close',))
    observer = FakeObserver()
    template = packet['commands_argv']['exact_templates']
    holder = {}

    def build_plan(gui, temp_dir):
        """Test helper for RUN007 offline behavior."""
        session = str(uuid.uuid4())
        world = temp_dir / (
            f'b2_training_arena.B2_SOAK_V1.{session}.runtime.sdf'
        )
        world.write_text('<sdf/>')
        params = temp_dir / 'robot_state_publisher.params.yaml'
        params.write_text('params')
        descriptor_path = temp_dir / 'run_descriptor.json'
        descriptor_path.write_text('{}')
        partition = f"mecanum_b2_{session.replace('-', '')}"
        FakePlan = make_dataclass(
            'FakePlan',
            [
                ('gui_requested', bool),
                ('session_id', str),
                ('coordinator_ingress_instance_id', int),
                ('config_hash', str),
                ('asset_manifest_sha256', str),
                ('resolved_config', Path),
                ('world_file', Path),
                ('commands', tuple),
                ('bridge_command', tuple),
                ('environment', dict),
            ],
        )
        plan = FakePlan(
            True, session, 17, packet['inputs']['config_hash'],
            packet['inputs']['manifest_sha256'], Path(
                packet['installation']['resolved_paths']['rl_share']
            ) / (
                'config/v3/resolved/'
                'sim_train_local_training_soak.resolved.json'
            ),
            world,
            (
                tuple(template['server'][:-1]) + (str(world),),
                tuple(template['gui']),
            ),
            tuple(template['parameter_bridge']),
            {
                'GZ_PARTITION': partition,
                'GZ_RESOURCE_PATH': '/installed/resources',
                'GZ_SIM_SYSTEM_PLUGIN_PATH': '/installed/plugins',
            },
        )
        descriptor = {'world_source_sha256': '1' * 64,
                      'runtime_bound_world_sha256':
                          hashlib.sha256(b'<sdf/>').hexdigest(),
                      'robot_state_publisher_params_sha256':
                          hashlib.sha256(b'params').hexdigest()}
        holder['plan'] = plan
        paths = {key: Path('/tmp') for key in ('backend_prefix',
                                               'bringup_share',
                                               'description_share',
                                               'rl_share')}
        return (plan, paths, descriptor, descriptor_path)

    async def evaluate(*, ack_event, **_kwargs):
        """Test helper for RUN007 offline behavior."""
        await ack_event.wait()
        return {'backend_identity': ['session', 'config', 'backend', 'world'],
                'last_status_sequence': 3, 'backend_status_samples': 3,
                'clock_samples': 3, 'clock_stamp': [0, 0],
                'observed_seconds': 60}

    async def bind_window(**_kwargs):
        """Test helper for RUN007 offline behavior."""
        return {'evidence_sequence': 9, 'window_id': '0x123', 'pid': 900010,
                'pgid': 900010, 'process_start_ticks': 31,
                'gz_partition': holder['plan'].environment['GZ_PARTITION'],
                'executable': '/usr/bin/gz', 'argv': ['/usr/bin/gz', 'sim'],
                'gui_process_identity': {'pid': 900010}}

    async def revalidate_window(expected_window, **_kwargs):
        """Keep orchestration revalidation fake-only in generic fixtures."""
        return dict(expected_window)

    async def capture_window_fake(*_args, **_kwargs):
        """Keep orchestration fake-only; native gate has its own tests."""
        state['capture_started'].set()
        if state.get('capture_hang'):
            try:
                await state['capture_released'].wait()
            except asyncio.CancelledError:
                state['capture_cancelled'].append('injected_capture')
                raise
        return runner._capture_payload_facts(png)

    async def review_waiter(*, request, request_bytes, **_kwargs):
        """Test helper for RUN007 offline behavior."""
        state['request'] = request
        result = runner._review_result_bytes(
            request_bytes, request, verdict='PASS',
            reason='fake visual review in test only')
        runner.atomic_publish(Path(request['result_path']), result)
        return {'verdict': 'PASS', 'reason': 'test fake review only',
                'viewer_ref_state': 'TOOL_NO_STABLE_REFERENCE'}

    def identity_reader(pid):
        identity = {
            'pid': pid,
            'process_group_id': pid,
            'session_id': pid,
            'start_ticks': 1,
        }
        if state.get('identity_changed_pid') == pid:
            identity['start_ticks'] = 2
        return identity
    dependencies = {'preflight': lambda *_args: events.append(('preflight',)),
                    'stdin_isatty': False, 'environ': {},
                    'exists': lambda _path: True, 'packet_path': packet_path,
                    'approval_path': approval_path,
                    'verify_commit': lambda *_args: None,
                    'guard_path': guard_path, 'evidence_root': root,
                    'temp_root': tmp_path,
                    'install_preflight': lambda:
                        packet['installation']['file_sha256'],
                    'build_plan': build_plan,
                    'ros2_executable': '/opt/ros/jazzy/bin/ros2',
                    'run_id': 'B22_GUI_OBSERVATION_TEST_ONLY',
                    'runner_process_identity': lambda _pid: {
                        'pid': 1, 'process_group_id': 1,
                        'session_id': 1, 'start_ticks': 2},
                    'host_identity': lambda: {'host': 'test-only'},
                    'acquire': guard.acquire_once,
                    'launcher': FakeLauncher(),
                    'process_identity_reader': identity_reader,
                    'process_inventory': lambda: [
                        identity_reader(process.pid)
                        for _command, process in processes
                        if process.returncode is None
                    ],
                    'signal_group': lambda pid, _sig: next(
                        process.finish() for _command, process in processes
                        if process.pid == pid
                    ),
                    'readiness': FakeReadiness(),
                    'observer_factory': lambda: observer,
                    'evaluate_observation': evaluate,
                    'bind_gui_window': bind_window,
                    'revalidate_gui_window': revalidate_window,
                    'capture_window_bounded': capture_window_fake,
                    'await_review': review_waiter,
                    'cleanup_escalation_grace': (0, 0, 0)}
    if not production_supervisor:
        dependencies['supervisor_factory'] = FakeSupervisor
    dependencies.update(_host_dependency_fakes(packet))
    return (SimpleNamespace(gui=True, approved_commit=commit), dependencies,
            events, processes, root, observer, state)


def _host_dependency_fakes(packet):
    """Inject pinned host metadata without importing Qt or middleware."""
    fingerprints = packet['installation']['dependency_fingerprints']
    qt = fingerprints['qt']
    desktop = fingerprints['desktop_tools']
    python = fingerprints['python']
    readiness = fingerprints['readiness_worker_provenance']
    modules = {
        'PyQt5': SimpleNamespace(__file__=qt['PyQt5_origin']),
        'PyQt5.QtCore': SimpleNamespace(
            __file__=qt['QtCore_origin'],
            PYQT_VERSION_STR=qt['PyQt5_version'],
            qVersion=lambda: qt['Qt_version'],
        ),
        'PyQt5.QtGui': SimpleNamespace(__file__=qt['QtGui_origin']),
        'rclpy': SimpleNamespace(__file__=readiness['rclpy_origin']),
        'gz.transport13': SimpleNamespace(
            __file__=readiness['gz_transport_wrapper_origin'],
        ),
    }
    for name, item in python['modules'].items():
        modules[name] = SimpleNamespace(
            __file__=item['origin'], __version__=item['version'],
        )
    file_hashes = {
        qt['PyQt5_origin']: qt['PyQt5_sha256'],
        qt['QtCore_origin']: qt['QtCore_sha256'],
        qt['QtGui_origin']: qt['QtGui_sha256'],
        qt['platform_plugin']: qt['platform_plugin_sha256'],
        desktop['xwininfo']['path']: desktop['xwininfo']['sha256'],
        desktop['xprop']['path']: desktop['xprop']['sha256'],
        readiness['rclpy_origin']: readiness['rclpy_sha256'],
        readiness['rclpy_executor_path']:
            readiness['rclpy_executor_sha256'],
        readiness['rclpy_context_path']:
            readiness['rclpy_context_sha256'],
        readiness['gz_transport_wrapper_origin']:
            readiness['gz_transport_wrapper_sha256'],
        readiness['gz_transport_native_origin']:
            readiness['gz_transport_native_sha256'],
    }
    package_versions = {
        **fingerprints['system_packages'],
        'x11-utils': desktop['xwininfo']['package_version'],
        'python3-pyqt5': desktop['python3_pyqt5_package_version'],
        'libqt5gui5t64': desktop['libqt5gui5t64_package_version'],
    }
    return {
        'module_importer': modules.__getitem__,
        'dependency_file_hasher': lambda path: file_hashes[str(path)],
        'package_version_reader': lambda _packages: package_versions,
        'python_executable': python['executable'],
        'python_version': python['version'],
        'dependency_path_resolver': lambda path, strict=True: Path(path),
    }


def test_complete_runtime_entry_path_passes_only_with_injected_components(
        tmp_path):
    """Test helper for RUN007 offline behavior."""
    args, deps, events, processes, root, observer, state = \
        make_runner_inputs(tmp_path, production_supervisor=True)
    verdict = asyncio.run(runner._run(args, dependencies=deps))
    assert verdict == 'PASS'
    assert [runner._process_label(command)
            for command, _proc in processes] == [
        'robot_state_publisher', 'parameter_bridge', 'server', 'gui',
    ]
    assert observer.closed == 1
    records = [json.loads(line) for line in
               (root / 'observation.jsonl').read_text().splitlines()]
    final = [record['facts'] for record in records
             if record['event'] == 'final_status'][-1]
    assert final['status'] == 'PASS'
    assert final['automated_observation_verdict'] == 'PASS'
    assert final['owner_visual_review'] == 'NOT_PERFORMED'
    completion = json.loads((root / 'final_result.json').read_text())
    assert completion['status'] == 'PASS'


def test_partial_startup_rolls_back_all_created_fake_children(tmp_path):
    """Test helper for RUN007 offline behavior."""
    args, deps, events, processes, root, observer, _state = \
        make_runner_inputs(tmp_path, startup_failure=True)
    verdict = asyncio.run(runner._run(args, dependencies=deps))
    assert verdict == 'FAIL'
    assert len(processes) == 2
    assert ('cleanup',) in events
    assert observer.closed == 1
    result = json.loads((root / 'final_result.json').read_text())
    assert result['status'] == 'FAIL'


def test_default_production_supervisor_reaches_codex_review_without_owner_ack(
        tmp_path, monkeypatch):
    """Test RUN007's actual wrapper start path omits human confirmation."""
    args, deps, events, _processes, root, _observer, state = \
        make_runner_inputs(tmp_path, production_supervisor=True)
    from mecanum_nav_bringup.local_training_process_supervisor import (
        LocalTrainingProcessSupervisor,
    )

    async def forbidden_owner_ack(*_args, **_kwargs):
        raise AssertionError('installed Owner ACK path must not be called')

    monkeypatch.setattr(
        LocalTrainingProcessSupervisor, '_owner_ack_with_liveness',
        forbidden_owner_ack,
    )
    verdict = asyncio.run(runner._run(args, dependencies=deps))
    assert verdict == 'PASS'
    assert state['owner_ack_calls'] == []
    assert any(event[0] == 'gui_ready' for event in events)
    records = [json.loads(line) for line in
               (root / 'observation.jsonl').read_text().splitlines()]
    assert not any(
        record['facts'].get('confirmation_source') == 'human_owner'
        for record in records
    )
    assert not any(record['event'] == 'gui_scene_owner_confirmed'
                   for record in records)


def test_first_failure_survives_cleanup_signal_and_server_exit_zero(tmp_path):
    """Default production wrapper retains readiness timeout as primary."""
    args, deps, _events, _processes, root, _observer, state = \
        make_runner_inputs(tmp_path, production_supervisor=True)
    state['readiness_failure'] = 'server'

    assert asyncio.run(runner._run(args, dependencies=deps)) == 'FAIL'
    records = [json.loads(line) for line in
               (root / 'observation.jsonl').read_text().splitlines()]
    event_names = [record['event'] for record in records]
    latch_index = event_names.index('first_failure_latched')
    signal_index = event_names.index('cleanup_signal_intent')
    exit_index = event_names.index('owned_process_cleanup_exit')
    assert latch_index < signal_index < exit_index
    cleanup_exit = next(
        record['facts'] for record in records
        if record['event'] == 'owned_process_cleanup_exit'
        and record['facts']['process'] == 'server'
    )
    assert cleanup_exit['process'] == 'server'
    assert cleanup_exit['exit_status'] == 0
    assert cleanup_exit['dispatch_observed_before_exit'] is True
    assert cleanup_exit['causation_claimed'] is False
    final = [record['facts'] for record in records
             if record['event'] == 'final_status'][-1]
    assert final['status'] == 'FAIL'
    assert final['primary_failure']['source'] == 'readiness'
    assert final['primary_failure']['phase'] == 'server_scene'
    assert 'injected readiness timeout' in final['primary_failure']['reason']
    completion = json.loads((root / 'final_result.json').read_text())
    assert completion['primary_failure'] == final['primary_failure']


def test_readiness_latch_survives_evidence_sink_failure():
    """The in-memory primary remains after its durable event write fails."""
    class FailingSink:
        def record(self, *_args, **_kwargs):
            raise OSError('injected evidence write failure')

    latch = runner.FirstFailureLatch(monotonic_ns=lambda: 123)
    latch.bind_evidence_sink(FailingSink())
    wrapped = runner.FirstFailureEvidenceSink(FailingSink(), latch)
    with pytest.raises(OSError, match='injected evidence write failure'):
        wrapped.record('readiness_failure_detected', {
            'error': 'timeout', 'detection_monotonic_ns': 100,
        })
    assert latch.primary_failure['reason'] == 'timeout'
    assert latch.primary_failure['source'] == 'readiness'
    assert latch.primary_failure['phase'] == 'server_scene'
    assert latch.primary_failure['detection_monotonic_ns'] == 100
    assert latch.primary_failure['traceback'] is None
    assert latch.cleanup_errors


def test_unexpected_owned_process_exit_is_primary_before_timeout(tmp_path):
    """The production process monitor latches an unrequested role exit."""
    args, deps, _events, processes, root, _observer, _state = \
        make_runner_inputs(tmp_path, production_supervisor=True)

    async def exit_server_during_binding(**kwargs):
        server = next(
            process for command, process in processes
            if runner._process_label(command) == 'server'
        )
        server.finish(23)
        await asyncio.Event().wait()

    deps['bind_gui_window'] = exit_server_during_binding
    assert asyncio.run(runner._run(args, dependencies=deps)) == 'FAIL'
    records = [json.loads(line) for line in
               (root / 'observation.jsonl').read_text().splitlines()]
    final = [record['facts'] for record in records
             if record['event'] == 'final_status'][-1]
    assert final['primary_failure']['source'] == 'process_monitor'
    assert 'server (23)' in final['primary_failure']['reason']
    assert final['status'] == 'FAIL'


def test_unrequested_exit_during_readiness_cleanup_is_secondary(tmp_path):
    """Keep a rollback exit separate from the readiness primary failure."""
    args, deps, _events, _processes, root, _observer, state = \
        make_runner_inputs(tmp_path, production_supervisor=True)
    state['readiness_failure'] = 'server_exit_during_cleanup'

    assert asyncio.run(runner._run(args, dependencies=deps)) == 'FAIL'
    records = [json.loads(line) for line in
               (root / 'observation.jsonl').read_text().splitlines()]
    final = [record['facts'] for record in records
             if record['event'] == 'final_status'][-1]
    assert final['primary_failure']['source'] == 'readiness'
    assert any(
        item['source'] == 'cleanup'
        and item['phase'] == 'process_exit'
        and 'server (0)' in item['reason']
        for item in final['secondary_failures']
    )
    exits = [record for record in records
             if record['event'] == 'owned_process_exit_during_cleanup']
    assert any(item['facts']['process'] == 'server'
               and item['facts']['exit_status'] == 0
               and item['facts']['dispatch_observed_before_exit'] is False
               for item in exits)
    assert not any(
        item['facts'].get('process') == 'server'
        for item in records
        if item['event'] == 'cleanup_signal_dispatched'
    )


def test_leader_exit_is_unrequested_when_only_descendant_is_dispatched(
        tmp_path):
    """Descendant cleanup cannot reclassify a departed group leader exit."""
    args, deps, _events, processes, root, _observer, state = \
        make_runner_inputs(tmp_path, production_supervisor=True)
    state['readiness_failure'] = 'server_exit_with_descendant'
    original_inventory = deps['process_inventory']
    original_reader = deps['process_identity_reader']
    signals = []

    def inventory():
        values = list(original_inventory())
        if state.get('descendant_alive'):
            leader_pid = state['descendant_leader_pid']
            values.append({
                'pid': leader_pid + 10000,
                'process_group_id': leader_pid,
                'session_id': leader_pid,
                'start_ticks': 2,
            })
        return values

    def signal_process(pid, sig):
        signals.append((pid, sig))
        if pid == state['descendant_leader_pid'] + 10000:
            state['descendant_alive'] = False

    deps['process_inventory'] = inventory
    deps['signal_process'] = signal_process
    deps['process_identity_reader'] = lambda pid: (
        next((item for item in inventory() if item['pid'] == pid), None)
        or original_reader(pid)
    )
    assert asyncio.run(runner._run(args, dependencies=deps)) == 'FAIL'
    assert signals
    records = [json.loads(line) for line in
               (root / 'observation.jsonl').read_text().splitlines()]
    server_exit = next(
        item for item in records
        if item['event'] == 'owned_process_exit_during_cleanup'
        and item['facts']['process'] == 'server'
    )
    assert server_exit['facts']['dispatch_observed_before_exit'] is False
    assert server_exit['facts']['causation_claimed'] is False
    assert any(
        item['event'] == 'cleanup_signal_dispatched'
        and item['facts']['process'] == 'server'
        and item['facts']['leader_dispatched'] is False
        for item in records
    )
    final = [item['facts'] for item in records
             if item['event'] == 'final_status'][-1]
    assert final['primary_failure']['source'] == 'readiness'


def test_identity_change_during_cleanup_never_creates_requested_exit(
        tmp_path):
    """Changed identity fails closed without dispatch evidence."""
    args, deps, _events, _processes, root, _observer, state = \
        make_runner_inputs(tmp_path, production_supervisor=True)
    state['readiness_failure'] = 'server_identity_changed'
    assert asyncio.run(runner._run(args, dependencies=deps)) == 'FAIL'
    records = [json.loads(line) for line in
               (root / 'observation.jsonl').read_text().splitlines()]
    assert not any(
        item['event'] == 'cleanup_signal_dispatched'
        and item['facts'].get('process') == 'server'
        for item in records
    )
    assert any(
        item['event'] == 'fallback_cleanup_attempt'
        and item['facts'].get('process') == 'server'
        for item in records
    )
    assert any(
        'PID reuse suspected' in str(error)
        for item in records if item['event'] == 'final_status'
        for error in item['facts'].get('cleanup_errors', [])
    )
    final = [item['facts'] for item in records
             if item['event'] == 'final_status'][-1]
    assert final['primary_failure']['source'] == 'readiness'


def test_dispatch_error_does_not_create_requested_exit_classification(
        tmp_path):
    """A failed verified group signal remains an unrequested process exit."""
    args, deps, _events, _processes, root, _observer, state = \
        make_runner_inputs(tmp_path, production_supervisor=True)
    state['readiness_failure'] = 'server'

    def fail_group(pid, _sig):
        raise PermissionError(f'injected signal dispatch rejection for {pid}')

    deps['signal_group'] = fail_group
    assert asyncio.run(runner._run(args, dependencies=deps)) == 'FAIL'
    records = [json.loads(line) for line in
               (root / 'observation.jsonl').read_text().splitlines()]
    assert not any(
        item['event'] == 'cleanup_signal_dispatched'
        and item['facts'].get('process') == 'server'
        for item in records
    )
    final = [item['facts'] for item in records
             if item['event'] == 'final_status'][-1]
    assert final['primary_failure']['source'] == 'readiness'
    assert any('PermissionError' in str(item)
               for item in final['cleanup_errors'])


def test_simultaneous_competing_failures_do_not_replace_prior_latch():
    """Each producer latches at detection; done-set order is irrelevant."""
    async def run_pair(first_source):
        latch = runner.FirstFailureLatch(monotonic_ns=lambda: 200)
        first_detected = asyncio.Event()
        second_detected = asyncio.Event()
        both_started = asyncio.Event()
        starts = 0
        detections = []

        # Force both tasks into one done-set after ordered detection.
        async def ordered_producer(source, release_gate):
            nonlocal starts
            starts += 1
            if starts == 2:
                both_started.set()
            await both_started.wait()
            await release_gate.wait()
            error = RuntimeError(f'{source} detected failure')
            detections.append(source)
            latch.detect(
                str(error), source, 'simultaneous', error=error,
                detection_monotonic_ns=100 if source == first_source else 101,
            )
            if len(detections) == 1:
                first_detected.set()
            else:
                second_detected.set()
            raise error

        operation_gate = asyncio.Event()
        monitor_gate = asyncio.Event()
        if first_source == 'operation':
            operation_gate.set()
        else:
            monitor_gate.set()

        class DoneWait:
            async def __call__(self, futures, **_kwargs):
                await asyncio.gather(*futures, return_exceptions=True)
                return set(futures), set()

        monitor = asyncio.create_task(
            ordered_producer('process_monitor', monitor_gate),
        )
        # Let the first producer record, then release the second.
        competing = asyncio.create_task(runner._wait_competing(
            ordered_producer('operation', operation_gate),
            monitor, 500, lambda: 100,
            wait_fn=DoneWait(), failure_latch=latch,
            phase='simultaneous',
        ))
        await first_detected.wait()
        (monitor_gate if first_source == 'operation' else operation_gate).set()
        with pytest.raises(RuntimeError):
            await competing
        assert detections == [first_source,
                              'process_monitor' if first_source == 'operation'
                              else 'operation']
        assert latch.primary_failure['source'] == first_source
        assert len(latch.secondary_failures) == 1
        return latch.primary_failure['source'], {
            item['source'] for item in latch.secondary_failures
        }

    assert asyncio.run(run_pair('operation')) == (
        'operation', {'process_monitor'},
    )
    assert asyncio.run(run_pair('process_monitor')) == (
        'process_monitor', {'operation'},
    )


def test_completion_retains_latch_only_evidence_error_after_sink_recovers(
        tmp_path):
    """A recovered sink publishes sticky latch errors and keeps the cause."""
    args, deps, _events, _processes, root, _observer, state = \
        make_runner_inputs(tmp_path, production_supervisor=True)
    state['readiness_failure'] = 'server'
    original_factory = deps['sink_factory'] if 'sink_factory' in deps else None

    class FailFirstFailureRecord:
        def __init__(self, delegate):
            self.delegate = delegate
            self.failed = False

        def record(self, event, facts):
            if event == 'first_failure_latched' and not self.failed:
                self.failed = True
                raise OSError('latch journal write failed once')
            return self.delegate.record(event, facts)

        def close(self):
            return self.delegate.close()

    deps['sink_factory'] = lambda *items: FailFirstFailureRecord(
        (original_factory or runner.ObservationEvidenceSink)(*items),
    )
    assert asyncio.run(runner._run(args, dependencies=deps)) == 'FAIL'
    records = [json.loads(line) for line in
               (root / 'observation.jsonl').read_text().splitlines()]
    final = [item['facts'] for item in records
             if item['event'] == 'final_status'][-1]
    completion = json.loads((root / 'final_result.json').read_text())
    assert final['status'] == completion['status'] == 'FAIL'
    assert final['primary_failure'] == completion['primary_failure']
    assert final['primary_failure']['source'] == 'readiness'
    assert any('latch journal write failed once' in str(item)
               for item in final['cleanup_errors'])
    assert any('latch journal write failed once' in str(item)
               for item in completion['cleanup_errors'])


def _observer_with_events(events, *, inventory=None):
    """Construct a passive-only evaluator fake with one fixed event batch."""
    class Observer:
        def __init__(self):
            self.events = deque(events)

        def spin_once(self, _timeout):
            return None

        def node_inventory(self):
            return inventory if inventory is not None else []

    return Observer()


def _health_test_plan():
    return SimpleNamespace(session_id='session', config_hash='config')


def test_backend_health_failure_latches_before_validation_event_sink_error():
    """Invalid backend status remains primary if failure journaling fails."""
    message = SimpleNamespace(
        session_id='wrong-session', config_hash='config',
        backend_instance_id=7,
        header=SimpleNamespace(frame_id='b2_training_arena'), paused=True,
        actuator_inhibited=True, fault_flags=0,
        applied_receipt_valid=False, status_sequence=4,
    )
    events = [('status', message, 1.0, 1_000_000_000)]

    class Sink:
        def record(self, event, _facts):
            if event == 'backend_status_validation_failed':
                raise OSError('backend failure journal unavailable')

    latch = runner.FirstFailureLatch(monotonic_ns=lambda: 55)
    with pytest.raises(runner.ObservationFailure, match='backend identity'):
        asyncio.run(runner.evaluate_observation(
            plan=_health_test_plan(), observer=_observer_with_events(events),
            sink=Sink(), failure_latch=latch, steady=lambda: 1.0,
        ))
    assert latch.primary_failure['reason'] == 'backend identity mismatch'
    assert latch.primary_failure['source'] == 'observer_health'
    assert latch.primary_failure['phase'] == 'backend_status_validation'
    assert latch.primary_failure['detection_monotonic_ns'] == 1_000_000_000
    assert any(item['source'] == 'evidence_sink'
               for item in latch.secondary_failures)


def test_clock_health_failure_latches_before_validation_event_sink_error():
    """Clock failure stays primary when its event cannot persist."""
    events = [
        ('clock', SimpleNamespace(sec=0, nanosec=0), 1.0, 1_000_000_000),
        ('clock', SimpleNamespace(sec=0, nanosec=1), 1.1, 1_100_000_000),
    ]

    class Sink:
        def record(self, event, _facts):
            if event == 'clock_validation_failed':
                raise OSError('clock failure journal unavailable')

    latch = runner.FirstFailureLatch(monotonic_ns=lambda: 77)
    with pytest.raises(runner.ObservationFailure, match='clock advanced'):
        asyncio.run(runner.evaluate_observation(
            plan=_health_test_plan(), observer=_observer_with_events(events),
            sink=Sink(), failure_latch=latch, steady=lambda: 1.0,
        ))
    assert latch.primary_failure['reason'] == 'simulation clock advanced'
    assert latch.primary_failure['phase'] == 'clock_validation'
    assert latch.primary_failure['detection_monotonic_ns'] == 1_000_000_000
    assert any(item['source'] == 'evidence_sink'
               for item in latch.secondary_failures)


def test_graph_failure_is_latched_before_later_cleanup_error():
    """Graph failure remains primary over a later cleanup fault."""
    observer = _observer_with_events([], inventory=[
        ('foreign_node', '/'), ('foreign_node', '/'),
    ])
    latch = runner.FirstFailureLatch(monotonic_ns=lambda: 99)
    with pytest.raises(runner.ObservationFailure, match='duplicate ROS graph'):
        asyncio.run(runner.evaluate_observation(
            plan=_health_test_plan(), observer=observer,
            failure_latch=latch, steady=lambda: 1.0,
        ))
    latch.detect('cleanup failed', 'cleanup', 'rollback')
    assert 'duplicate ROS graph' in latch.primary_failure['reason']
    assert latch.primary_failure['phase'] == 'graph_validation'
    assert latch.primary_failure['detection_monotonic_ns'] == 1_000_000_000
    assert latch.secondary_failures[0]['source'] == 'cleanup'


def test_heartbeat_gap_is_latched_before_cleanup_failure():
    """Heartbeat gap retains its producer timestamp as primary evidence."""
    def status(sequence):
        return SimpleNamespace(
            session_id='session', config_hash='config',
            backend_instance_id=7,
            header=SimpleNamespace(frame_id='b2_training_arena'),
            paused=True, actuator_inhibited=True, fault_flags=0,
            applied_receipt_valid=False, status_sequence=sequence,
        )

    observer = _observer_with_events([
        ('status', status(1), 1.0, 1_000_000_000),
        ('status', status(2), 2.1, 2_100_000_000),
    ])
    latch = runner.FirstFailureLatch(monotonic_ns=lambda: 200)
    with pytest.raises(runner.ObservationFailure, match='heartbeat gap'):
        asyncio.run(runner.evaluate_observation(
            plan=_health_test_plan(), observer=observer,
            failure_latch=latch, steady=lambda: 3.0,
        ))
    assert latch.primary_failure['phase'] == 'backend_status_validation'
    assert latch.primary_failure['detection_monotonic_ns'] == 3_000_000_000
    latch.detect('cleanup failed', 'cleanup', 'rollback')
    assert latch.primary_failure['reason'] == (
        'backend heartbeat gap exceeded 1 s'
    )
    assert latch.secondary_failures[0]['source'] == 'cleanup'


def test_run007_default_supervisor_uses_canonical_readiness_parent(
        tmp_path, monkeypatch):
    """Run _run through canonical readiness with a fake worker OS seam."""
    args, deps, events, _processes, root, _observer, state = \
        make_runner_inputs(tmp_path, production_supervisor=True)
    deps.pop('readiness')
    from mecanum_nav_bringup.local_training_process_supervisor import (
        LocalTrainingProcessSupervisor,
    )

    async def forbidden_owner_ack(*_args, **_kwargs):
        raise AssertionError('Owner ACK path must not run')

    monkeypatch.setattr(
        LocalTrainingProcessSupervisor, '_owner_ack_with_liveness',
        forbidden_owner_ack,
    )

    class ByteStream:
        def __init__(self):
            self.data = bytearray()

        def feed(self, data):
            self.data.extend(data)

        async def read(self, _size):
            await asyncio.sleep(0)
            data = bytes(self.data)
            self.data.clear()
            return data

    class Worker:
        pid = 990001
        returncode = None

        def __init__(self):
            self.stdout = ByteStream()
            self.stderr = ByteStream()
            self.stdin = WorkerInput(self)

        async def wait(self):
            await asyncio.sleep(0)
            self.returncode = 0
            return 0

    class WorkerInput:
        def __init__(self, owner):
            self.owner = owner
            self.closed = False

        def is_closing(self):
            return self.closed

        def close(self):
            self.closed = True

        async def drain(self):
            await asyncio.sleep(0)

        async def wait_closed(self):
            await asyncio.sleep(0)

        def write(self, data):
            request = json.loads(data)
            canonical = json.dumps(
                request, ensure_ascii=False, sort_keys=True,
                separators=(',', ':'), allow_nan=False,
            ).encode('utf-8')
            digest = hashlib.sha256(canonical).hexdigest()
            binding = {key: request[key] for key in (
                'session_id', 'config_hash', 'asset_manifest_sha256',
                'coordinator_ingress_instance_id',
            )}
            status = {
                'world_id': request['world_id'],
                'session_id': request['session_id'],
                'config_hash': request['config_hash'],
                'backend_instance_id': 81, 'status_sequence': 1,
                'fault_flags': 0, 'actuator_inhibited': True,
            }
            scene = {
                'scene_name': '',
                'matching_model_count': 1,
                'query_service': (
                    '/world/b2_training_arena/scene/info'
                ),
                'query_partition': request['gz_partition'],
                'world_identity_source': (
                    'WORLD_SCOPED_SERVICE_AND_BOUND_BACKEND'
                ),
            }
            frames = [
                ('worker_started', {'request_binding': binding}),
                ('status_wait_started', {
                    'topic': '/mecanum/local_training/backend_state',
                    'qos_depth': 50,
                }),
                ('status_matched', {
                    'status': status, 'request_binding': binding,
                }),
                ('scene_query_started', {
                    'service': '/world/b2_training_arena/scene/info',
                    'timeout_ms': 500,
                }),
                ('scene_query_finished', {
                    **scene, 'duration_ns': 1, 'outcome': 'MATCH',
                    'error': None,
                }),
                ('worker_result', {
                    'verdict': 'READY', 'reason': '',
                    'facts': {
                        'status': status, 'scene': scene,
                        'request_binding': binding,
                    },
                    'cleanup_errors': [], 'cleanup_elapsed_ns': 1,
                }),
            ]
            lines = []
            for seq, (event, facts) in enumerate(frames, 1):
                record = {
                    'schema_id': 'mecanum_b2_scene_readiness_event/v2',
                    'request_id': request['request_id'],
                    'request_sha256': digest, 'sequence': seq,
                    'event': event, 'monotonic_ns': seq, 'facts': facts,
                }
                lines.append(json.dumps(
                    record, sort_keys=True, separators=(',', ':'),
                ).encode() + b'\n')
            self.owner.stdout.feed(b''.join(lines))

    workers = []

    async def spawn_worker(_environment):
        worker = Worker()
        workers.append(worker)
        return worker

    def factory(readiness_type):
        return readiness_type(
            worker_factory=spawn_worker,
            identity_reader=lambda pid: {
                'pid': pid, 'process_group_id': pid, 'session_id': pid,
                'start_ticks': 1,
            },
            signal_group=lambda *_args: None,
        )

    deps['readiness_factory'] = factory
    assert asyncio.run(runner._run(args, dependencies=deps)) == 'PASS'
    assert len(workers) == 1
    assert state['owner_ack_calls'] == []
    records = [json.loads(line) for line in
               (root / 'observation.jsonl').read_text().splitlines()]
    assert any(row['event'] == 'readiness_worker_parent_validated'
               for row in records)
    assert not any(row.get('facts', {}).get('confirmation_source')
                   == 'human_owner' for row in records)


@pytest.mark.parametrize('failure', ['server', 'gui', 'server_cancel'])
def test_default_production_supervisor_rolls_back_readiness_failures(
        tmp_path, failure):
    """Test production wrapper owns and rolls back partial compositions."""
    args, deps, _events, processes, root, observer, state = \
        make_runner_inputs(tmp_path, production_supervisor=True)
    state['readiness_failure'] = failure
    verdict = asyncio.run(runner._run(args, dependencies=deps))
    assert verdict == 'FAIL'
    assert processes
    assert all(process.returncode is not None
               for _command, process in processes)
    assert observer.closed == 1
    records = [json.loads(line) for line in
               (root / 'observation.jsonl').read_text().splitlines()]
    assert not any(record['event'] == 'codex_review_request_published'
                   for record in records)
    assert state['owner_ack_calls'] == []


@pytest.mark.parametrize('cause', ['health', 'gui_exit', 'deadline', 'cancel'])
def test_window_binding_is_invalidated_before_capture(tmp_path, cause):
    """Test health, process, deadline and cancellation cancel window bind."""
    args, deps, _events, processes, root, _observer, state = \
        make_runner_inputs(tmp_path, production_supervisor=True)
    bind_started = asyncio.Event()
    clock = [100.0]
    deps['monotonic'] = lambda: clock[0]

    async def immediate_deadline(_futures, *, timeout, **_wait_kwargs):
        await asyncio.sleep(0)
        clock[0] += timeout
        return set(), set(_futures)

    if cause == 'deadline':
        deps['binding_wait_fn'] = immediate_deadline

    async def binding_wait(**kwargs):
        state['binding_cancelled'] = False
        bind_started.set()
        try:
            if cause == 'deadline':
                await asyncio.Event().wait()
            if cause == 'gui_exit':
                gui = next(
                    process for command, process in processes
                    if runner._process_label(command) == 'gui'
                )
                gui.finish(1)
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            state['binding_cancelled'] = True
            raise

    async def health_failure(**_kwargs):
        await bind_started.wait()
        if cause == 'health':
            raise runner.ObservationFailure('injected backend health loss')
        await asyncio.Event().wait()

    deps['bind_gui_window'] = binding_wait
    deps['evaluate_observation'] = health_failure

    async def execute():
        run_task = asyncio.create_task(runner._run(args, dependencies=deps))
        try:
            await asyncio.wait_for(bind_started.wait(), timeout=5)
        except asyncio.TimeoutError:
            if not run_task.done():
                run_task.cancel()
                await asyncio.gather(run_task, return_exceptions=True)
            else:
                await run_task
            raise AssertionError(
                f'runner did not reach window binding; events={_events!r}'
            )
        if cause == 'cancel':
            run_task.cancel()
        return await run_task
    verdict = asyncio.run(execute())
    assert verdict == 'FAIL'
    assert state['binding_cancelled'] is True
    assert not (root / 'screenshots').exists()
    records = [json.loads(line) for line in
               (root / 'observation.jsonl').read_text().splitlines()]
    assert not any(record['event'] == 'codex_review_request_published'
                   for record in records)
    assert all(process.returncode is not None
               for _command, process in processes)


def test_unknown_owned_identity_is_never_signalled_while_verified_group_cleans(
        tmp_path):
    """Test cleanup preserves unknown ownership and reclaims verified group."""
    class Process:

        def __init__(self, pid):
            self.pid = pid
            self.returncode = None
            self.event = asyncio.Event()

        async def wait(self):
            await self.event.wait()
            return self.returncode

        def finish(self):
            self.returncode = 0
            self.event.set()

    first = Process(910001)
    second = Process(910002)
    signals = []

    class Delegate:

        def __init__(self):
            self.started = [first, second]

        async def start(self, _command, _environment):
            return self.started.pop(0)

        def group_alive(self, process):
            return process.returncode is None

        async def stop_group(self, process, sig):
            signals.append((process.pid, sig))
            if sig != signal.SIGINT:
                process.finish()

    def identity_reader(pid):
        if pid == first.pid:
            raise OSError('injected proc identity read failure')
        return {'pid': pid, 'process_group_id': pid, 'session_id': pid,
                'start_ticks': 12}

    launcher = runner.TrackedProcessLauncher(
        Delegate(), identity_reader=identity_reader,
        signal_group=lambda pgid, sig: (
            signals.append((pgid, sig)),
            second.finish() if sig != signal.SIGINT else None,
        ),
        process_inventory=lambda: [identity_reader(second.pid)]
        if second.returncode is None else [],
    )
    with pytest.raises(OSError):
        asyncio.run(launcher.start(['server'], {}))
    asyncio.run(launcher.start(['gui'], {}))
    errors = []
    asyncio.run(runner._fallback_cleanup(
        launcher, launcher.records, None, errors,
        deadline=10, steady=lambda: 0,
        sleep=lambda _delay: asyncio.sleep(0),
        escalation_grace=(0, 0, 0),
    ))
    assert first.returncode is None
    assert second.returncode == 0
    assert [sig for pid, sig in signals if pid == second.pid] == [
        signal.SIGINT, signal.SIGTERM,
    ]
    assert launcher.records[0].identity is None
    assert launcher.records[0].identity_error
    assert any('identity' in error or 'unverified' in error
               for error in errors)


def test_reused_owned_leader_is_not_signalled(tmp_path):
    """Test PID reuse fails closed before any group signal."""
    class Process:

        def __init__(self):
            self.pid = 910003
            self.returncode = None
            self.event = asyncio.Event()

        async def wait(self):
            await self.event.wait()
            return self.returncode

    process = Process()
    signals = []
    current = {'start_ticks': 20}

    class Delegate:

        async def start(self, _command, _environment):
            return process

        def group_alive(self, _process):
            raise AssertionError('must not delegate group liveness')

        async def stop_group(self, _process, _sig):
            signals.append(True)

    def identity_reader(pid):
        return {'pid': pid, 'process_group_id': pid, 'session_id': pid,
                'start_ticks': current['start_ticks']}

    launcher = runner.TrackedProcessLauncher(
        Delegate(), identity_reader=identity_reader,
        process_inventory=lambda: [identity_reader(process.pid)],
    )
    asyncio.run(launcher.start(['gui'], {}))
    current['start_ticks'] = 21
    with pytest.raises(runner.ObservationFailure, match='PID reuse'):
        launcher.group_alive(process)
    with pytest.raises(runner.ObservationFailure, match='PID reuse'):
        asyncio.run(launcher.stop_group(process, 2))
    assert signals == []


@pytest.mark.parametrize('identity', [
    {'pid': 44, 'process_group_id': 44, 'session_id': 44},
    {'pid': 44, 'process_group_id': 44, 'session_id': 44,
     'start_ticks': True},
])
def test_missing_or_wrong_type_start_identity_stays_unknown(identity):
    """Test incomplete process start identity cannot authorize cleanup."""
    class Process:

        pid = 44
        returncode = None

        async def wait(self):
            await asyncio.Event().wait()

    process = Process()
    signals = []

    class Delegate:

        async def start(self, _command, _environment):
            return process

        async def stop_group(self, _process, _sig):
            signals.append(True)

        def group_alive(self, _process):
            return True

    launcher = runner.TrackedProcessLauncher(
        Delegate(), identity_reader=lambda _pid: identity,
    )
    with pytest.raises(runner.ObservationFailure):
        asyncio.run(launcher.start(['gui'], {}))
    assert launcher.records[0].identity is None
    assert launcher.records[0].identity_error
    with pytest.raises(runner.ObservationFailure, match='unknown'):
        launcher.group_alive(process)
    with pytest.raises(runner.ObservationFailure, match='verified identity'):
        asyncio.run(launcher.stop_group(process, signal.SIGINT))
    assert process.returncode is None
    assert signals == []


def test_absent_leader_allows_only_verified_descendant_cleanup():
    """Test confirmed leader exit retains safe descendant cleanup path."""
    class Process:

        pid = 910004
        returncode = 0

        async def wait(self):
            return 0

    process = Process()
    leader = {'pid': process.pid, 'process_group_id': process.pid,
              'session_id': process.pid, 'start_ticks': 30}
    child = {'pid': 910005, 'process_group_id': process.pid,
             'session_id': process.pid, 'start_ticks': 31}
    live = {child['pid']: child}
    signals = []

    class Delegate:

        async def start(self, _command, _environment):
            return process

        async def stop_group(self, _process, _sig):
            raise AssertionError('absent leader must use verified child path')

    def identity_reader(pid):
        return live[pid]

    def signal_member(pid, sig):
        signals.append((pid, sig))
        live.pop(pid)

    launcher = runner.TrackedProcessLauncher(
        Delegate(), identity_reader=lambda pid: leader if pid == process.pid
        else identity_reader(pid),
        signal_process=signal_member,
        process_inventory=lambda: list(live.values()),
    )
    asyncio.run(launcher.start(['server'], {}))
    identity, members = launcher._members(process)
    assert identity == leader
    assert members == [child]
    asyncio.run(launcher.stop_group(process, signal.SIGTERM))
    assert signals == [(child['pid'], signal.SIGTERM)]
    assert live == {}


def test_incomplete_identity_blocks_signal_and_marks_runner_residue(
        tmp_path):
    """Test identity failure after spawn remains owned, unknown and FAIL."""
    args, deps, _events, processes, root, _observer, _state = \
        make_runner_inputs(tmp_path, production_supervisor=True)
    signals = []
    deps['process_identity_reader'] = lambda _pid: {
        'pid': 1, 'process_group_id': 1, 'session_id': 1,
    }
    deps['signal_process'] = lambda pid, sig: signals.append((pid, sig))
    verdict = asyncio.run(runner._run(args, dependencies=deps))
    assert verdict == 'FAIL'
    assert processes and processes[0][1].returncode is None
    assert signals == []
    completion = json.loads((root / 'final_result.json').read_text())
    assert completion['status'] == 'FAIL'
    assert any('identity_unknown' in item or 'unverified' in item
               for item in completion['cleanup_errors'])


@pytest.mark.parametrize('stage', [
    'record', 'close', 'stream_hash', 'publication', 'boundary',
])
def test_finalization_deadline_controls_runner_verdict_and_marker(
        tmp_path, stage, capsys):
    """Test _run returns FAIL when any finalization step crosses deadline."""
    args, deps, _events, _processes, root, _observer, _state = \
        make_runner_inputs(tmp_path, production_supervisor=True)
    clock = [100.0]
    deps['monotonic'] = lambda: clock[0]
    sink_factory = runner.ObservationEvidenceSink

    class TimedSink:

        def __init__(self, *args, **kwargs):
            self.inner = sink_factory(*args, **kwargs)

        def record(self, event, facts):
            result = self.inner.record(event, facts)
            if stage == 'record' and event == 'final_status':
                clock[0] = 161.0
            if stage == 'boundary' and event == 'final_status':
                clock[0] = 159.9
            return result

        def close(self):
            self.inner.close()
            if stage == 'close':
                clock[0] = 161.0

    deps['sink_factory'] = TimedSink
    if stage == 'stream_hash':
        def late_hash(path):
            value = runner.sha256_file(path)
            clock[0] = 161.0
            return value
        deps['stream_hasher'] = late_hash
    if stage == 'publication':
        def late_publish(path, data):
            runner.atomic_publish(path, data)
            clock[0] = 161.0
        deps['completion_publisher'] = late_publish

    verdict = asyncio.run(runner._run(args, dependencies=deps))
    completion_path = root / 'final_result.json'
    assert completion_path.exists()
    completion = json.loads(completion_path.read_text())
    if stage == 'boundary':
        assert verdict == 'PASS'
        assert completion['status'] == 'PASS'
    elif stage == 'publication':
        assert verdict == 'FAIL'
        assert completion['status'] == 'PASS'
        assert (
            'RUN007_FINALIZATION_DEADLINE_VIOLATION'
            in capsys.readouterr().err
        )
    else:
        assert verdict == 'FAIL'
        assert completion['status'] == 'FAIL'
        assert any('finalization_deadline_exceeded' in item
                   for item in completion['cleanup_errors'])


def test_codex_result_and_owner_review_labels_are_distinct_in_source():
    """Test helper for RUN007 offline behavior."""
    source = Path(runner.__file__).read_text(encoding='utf-8')
    assert 'automated_observation_verdict' in source
    assert 'owner_visual_review' in source
    assert 'OWNER_ACK_SCENE' not in source and 'OWNER_ABORT_GUI' not in source
    assert 'create_publisher(' not in source and 'create_client(' not in source


def _window_discovery_fakes(snapshots, property_snapshots=None,
                            *, identity_reader=None, partition_reader=None,
                            helper_failures=None):
    """Build deterministic X11 transcripts without opening an X connection."""
    gui_identity = {
        'pid': 101, 'process_group_id': 101, 'session_id': 101,
        'start_ticks': 7,
    }
    child_identity = {
        'pid': 102, 'process_group_id': 101, 'session_id': 101,
        'start_ticks': 9,
    }
    clock = [0.0]
    sink = SimpleNamespace(records=[])

    def record(event, facts):
        sink.records.append((event, facts))

    sink.record = record

    class Process:
        def __init__(self, pid, output=b'', status=0, stderr=b''):
            self.pid = pid
            self.output = output
            self.status = status
            self.stderr = stderr

        async def communicate(self):
            return self.output, self.stderr

        async def wait(self):
            return self.status

    class Launcher:
        def __init__(self):
            self.records = [SimpleNamespace(
                name='gui', pid=101, identity=gui_identity,
                process=object(), command=('/usr/bin/gz', 'sim', '-g'))]
            self.pass_index = -1
            self.commands = []

        async def start_gated(self, command, _environment, *, role,
                              deadline, steady):
            command = tuple(command)
            self.commands.append((command, deadline))
            if command[0].endswith('xwininfo'):
                self.pass_index = min(self.pass_index + 1,
                                      len(snapshots) - 1)
                output = snapshots[self.pass_index].encode()
                status, stderr = 0, b''
            else:
                window_id = command[2]
                entry = (property_snapshots or [{}])[self.pass_index]
                value = entry.get(window_id, b'')
                if isinstance(value, tuple):
                    output, status, stderr = value
                else:
                    output, status, stderr = value, 0, b''
            if helper_failures and command[0].endswith('xprop'):
                failure = helper_failures.get(command[2])
                if failure:
                    output, status, stderr = failure
            process = Process(200 + len(self.records), output, status,
                              stderr)
            identity = {'pid': process.pid, 'process_group_id': process.pid,
                        'session_id': process.pid, 'start_ticks': 1}
            record = SimpleNamespace(
                name=role, pid=process.pid, process=process,
                identity=identity, command=command,
                wrapper_command=('fake-gate-wrapper',),
                gate={'nonce': 'fake-nonce', 'binding_sha256': 'f' * 64,
                      'role': role,
                      'verified_identity': dict(identity),
                      'planned_command': list(command)},
                gate_released=True,
            )
            if (len(command) >= 3 and runner._xprop_discovery_command(
                    role, command, command[2])):
                record.helper_classification = {
                    'state': 'pending', 'owner': asyncio.current_task(),
                    'deadline': deadline, 'window_id': command[2],
                }
            self.records.append(record)
            return process

    def read_identity(pid):
        if identity_reader is not None:
            return identity_reader(pid)
        return {101: gui_identity, 102: child_identity, 901: {
            'pid': 901, 'process_group_id': 901,
            'session_id': 901, 'start_ticks': 12,
        }}[pid]

    def read_parent(pid):
        return {102: 101, 101: 1, 901: 900, 900: 1}[pid]

    async def advance(delay):
        clock[0] += delay
        await asyncio.sleep(0)

    return {
        'launcher': Launcher(), 'sink': sink, 'clock': clock,
        'steady': lambda: clock[0], 'sleep': advance,
        'process_identity_reader': read_identity,
        'parent_reader': read_parent,
        'executable_reader': lambda _path: '/usr/bin/gz',
        'argv_reader': lambda _pid: ['/usr/bin/gz', 'sim', '-g'],
        'partition_reader': partition_reader or (
            lambda _pid: 'mecanum_b2_test'),
    }


def _window_line(window_id, title='Gazebo'):
    """Render one private test-only xwininfo row."""
    return f'  {window_id} "{title}" 800x600+0+0\n'


def _gazebo_properties(pid=102):
    """Return a default Gazebo WM_CLASS with optional PID metadata."""
    return (f'_NET_WM_PID(CARDINAL) = {pid}\n'
            'WM_CLASS(STRING) = "gz sim", "Gazebo"\n'
            '_NET_WM_NAME(UTF8_STRING) = "test title only"\n').encode()


def test_window_binding_matches_unique_owned_process_and_partition():
    """Test helper for RUN007 offline behavior."""

    class FakeProcess:

        def __init__(self, pid, stdout):
            """Test helper for RUN007 offline behavior."""
            self.pid = pid
            self.stdout = stdout

        async def communicate(self):
            """Test helper for RUN007 offline behavior."""
            return (self.stdout, b'')

        async def wait(self):
            """Test helper for RUN007 offline behavior."""
            return 0

    class FakeLauncher:

        def __init__(self, tree, props):
            """Test helper for RUN007 offline behavior."""
            self.records = [SimpleNamespace(
                name='gui', pid=101,
                identity={
                    'pid': 101, 'process_group_id': 101,
                    'session_id': 101, 'start_ticks': 7,
                },
                process=object(), command=('/usr/bin/gz', 'sim', '-g'),
            )]
            self.waiters = {}
            self.tree = tree
            self.props = props

        async def start_gated(self, command, _environment, *, role,
                              deadline, steady):
            """Test helper for RUN007 offline behavior."""
            output = (self.tree if command[0] == '/usr/bin/xwininfo'
                      else self.props)
            process = FakeProcess(
                202 if command[0].endswith('xwininfo') else 203, output)
            self.records.append(SimpleNamespace(
                name=role, pid=process.pid, process=process,
                identity={'pid': process.pid}, command=tuple(command),
                wrapper_command=('fake-gate-wrapper',),
                gate={'nonce': 'fake-nonce', 'binding_sha256': 'f' * 64},
                gate_released=True,
            ))
            return process
    tree = b'  0x000010 "Gazebo": ("gz sim", "Gazebo") 800x600+0+0\n'
    props = (b'_NET_WM_PID(CARDINAL) = 101\n'
             b'WM_CLASS(STRING) = "gz sim", "Gazebo"\n'
             b'_NET_WM_NAME(UTF8_STRING) = "Gazebo"\n')
    launcher = FakeLauncher(tree, props)
    identity = {'pid': 101, 'process_group_id': 101, 'session_id': 101,
                'start_ticks': 7}
    result = asyncio.run(runner.bind_gui_window(
        launcher=launcher,
        environment={'GZ_PARTITION': 'mecanum_b2_test'},
        partition='mecanum_b2_test', deadline=10, steady=lambda: 0,
        process_identity_reader=lambda _pid: identity,
        executable_reader=lambda _path: '/usr/bin/gz',
        argv_reader=lambda _pid: ['/usr/bin/gz', 'sim', '-g'],
        partition_reader=lambda _pid: 'mecanum_b2_test'))
    assert result['window_id'] == '0x000010'
    assert result['pid'] == 101 and result['pgid'] == 101
    assert result['process_start_ticks'] == 7


@pytest.mark.parametrize(
    'observed_partition,tree,expected_error',
    [('foreign', b'  0x000010 "Gazebo"\n',
      'window discovery review deadline expired without a unique'),
     ('mecanum_b2_test', b'  0x000010 "Gazebo"\n'
      b'    0x000011 "Gazebo child"\n',
      'window discovery review deadline expired with ambiguous')],
    ids=[
        'foreign-  0x000010 "Gazebo"\n',
        'mecanum_b2_test-  0x000010 "Gazebo"\n  '
        '0x000011 "Gazebo"\n',
    ],
)
def test_window_binding_rejects_partition_mismatch_or_ambiguity(
        observed_partition, tree, expected_error):
    """Test helper for RUN007 offline behavior."""

    class FakeProcess:

        def __init__(self, pid, output):
            """Test helper for RUN007 offline behavior."""
            self.pid = pid
            self.output = output

        async def communicate(self):
            """Test helper for RUN007 offline behavior."""
            return (self.output, b'')

        async def wait(self):
            """Test helper for RUN007 offline behavior."""
            return 0

    class FakeLauncher:

        def __init__(self):
            """Test helper for RUN007 offline behavior."""
            self.records = [SimpleNamespace(
                name='gui', pid=101,
                identity={
                    'pid': 101,
                    'process_group_id': 101,
                    'session_id': 101,
                    'start_ticks': 7},
                process=object(),
                command=('/usr/bin/gz', 'sim', '-g'))]
            self.waiters = {}

        async def start_gated(self, command, _env, *, role,
                              deadline, steady):
            """Test helper for RUN007 offline behavior."""
            out = (tree if command[0].endswith('xwininfo') else
                   b'_NET_WM_PID(CARDINAL) = 101\n'
                   b'WM_CLASS(STRING) = "gz", "Gazebo"\n')
            proc = FakeProcess(202, out)
            self.records.append(SimpleNamespace(
                name=role, pid=202, process=proc,
                identity={'pid': 202}, command=tuple(command),
                wrapper_command=('fake-gate-wrapper',),
                gate={'nonce': 'fake-nonce', 'binding_sha256': 'f' * 64},
                gate_released=True,
            ))
            return proc
    identity = {'pid': 101, 'process_group_id': 101, 'session_id': 101,
                'start_ticks': 7}
    clock = [0.0]

    async def advance(delay):
        """Advance an injected clock while discovery yields asynchronously."""
        clock[0] += delay
        await asyncio.sleep(0)

    with pytest.raises(runner.ReviewInvalidated, match=expected_error):
        asyncio.run(runner.bind_gui_window(launcher=FakeLauncher(),
                                           environment={},
                                           partition='mecanum_b2_test',
                                           deadline=0.25,
                                           steady=lambda: clock[0],
                                           sleep=advance,
                                           process_identity_reader=(
                                               lambda _pid: identity),
                                           executable_reader=(
                                               lambda _path: '/usr/bin/gz'),
                                           argv_reader=(
                                               lambda _pid: ['/usr/bin/gz',
                                                             'sim', '-g']),
                                           partition_reader=(
                                               lambda _pid:
                                               observed_partition)))


def test_window_discovery_repeats_same_attempt_until_owned_window_appears():
    """A later X11 snapshot binds without restarting the owned GUI."""
    fake = _window_discovery_fakes(
        ['', _window_line('0x22')],
        [{}, {'0x22': _gazebo_properties()}],
    )
    kwargs = dict(fake)
    launcher = kwargs.pop('launcher')
    sink = kwargs.pop('sink')
    kwargs.pop('clock')
    kwargs.pop('steady')
    kwargs.pop('sleep')
    result = asyncio.run(runner.bind_gui_window(
        launcher=launcher, environment={'GZ_PARTITION': 'mecanum_b2_test'},
        partition='mecanum_b2_test', deadline=1.0,
        steady=fake['steady'], sink=sink, sleep=fake['sleep'], **kwargs,
    ))
    assert result['window_id'] == '0x22'
    assert sum(r.name == 'gui' for r in launcher.records) == 1
    assert sum(c[0][0].endswith('xwininfo') for c in launcher.commands) == 2
    assert {deadline for _command, deadline in launcher.commands} == {1.0}
    passes = [facts for event, facts in sink.records
              if event == 'gui_window_discovery_pass']
    assert [item['outcome'] for item in passes] == [
        'NO_OWNED_MATCH', 'UNIQUE_OWNED_MATCH',
    ]
    assert passes[0]['remaining_deadline_after_s'] > 0


def test_window_discovery_rechecks_metadata_that_arrives_late():
    """Missing PID metadata is diagnosed then evaluated on the next pass."""
    missing = b'WM_CLASS(STRING) = "gz sim", "Gazebo"\n'
    fake = _window_discovery_fakes(
        [_window_line('0x23'), _window_line('0x23')],
        [{'0x23': missing}, {'0x23': _gazebo_properties()}],
    )
    kwargs = dict(fake)
    launcher, sink = kwargs.pop('launcher'), kwargs.pop('sink')
    kwargs.pop('clock')
    kwargs.pop('steady')
    kwargs.pop('sleep')
    result = asyncio.run(runner.bind_gui_window(
        launcher=launcher, environment={'GZ_PARTITION': 'mecanum_b2_test'},
        partition='mecanum_b2_test', deadline=1.0,
        steady=fake['steady'], sleep=fake['sleep'], sink=sink, **kwargs,
    ))
    assert result['window_id'] == '0x23'
    passes = [facts for event, facts in sink.records
              if event == 'gui_window_discovery_pass']
    assert passes[0]['candidate_diagnostics'][0]['state'] == (
        'missing_pid_metadata')
    assert passes[1]['candidate_diagnostics'][0]['state'] == 'owned_match'


def test_window_discovery_excludes_foreign_gazebo_then_binds_owned():
    """A foreign Gazebo client is diagnosed and never selected."""
    fake = _window_discovery_fakes(
        [_window_line('0x31', 'foreign title') +
         _window_line('0x32', 'owned title')],
        [{'0x31': _gazebo_properties(901),
          '0x32': _gazebo_properties(102)}],
    )
    kwargs = dict(fake)
    launcher, sink = kwargs.pop('launcher'), kwargs.pop('sink')
    kwargs.pop('clock')
    kwargs.pop('steady')
    kwargs.pop('sleep')
    result = asyncio.run(runner.bind_gui_window(
        launcher=launcher, environment={'GZ_PARTITION': 'mecanum_b2_test'},
        partition='mecanum_b2_test', deadline=1.0,
        steady=fake['steady'], sleep=fake['sleep'], sink=sink, **kwargs,
    ))
    assert result['window_id'] == '0x32'
    diag = next(facts for event, facts in sink.records
                if event == 'gui_window_discovery_pass')
    assert [item['state'] for item in diag['candidate_diagnostics']] == [
        'foreign_identity', 'owned_match',
    ]
    serialized = json.dumps(diag, sort_keys=True)
    assert 'foreign title' not in serialized
    assert 'owned title' not in serialized


def test_window_discovery_keeps_decision_complete_when_diagnostics_truncate():
    """The logging cap does not remove late candidates from the decision."""
    ids = [f'0x{i:04x}' for i in range(70)]
    tree = ''.join(_window_line(item, f'title {item}') for item in ids)
    properties = {
        item: (b'WM_CLASS(STRING) = "other", "OtherApp"\n'
               if item != ids[-1] else _gazebo_properties())
        for item in ids
    }
    fake = _window_discovery_fakes([tree], [properties])
    kwargs = dict(fake)
    launcher, sink = kwargs.pop('launcher'), kwargs.pop('sink')
    kwargs.pop('clock')
    kwargs.pop('steady')
    kwargs.pop('sleep')
    result = asyncio.run(runner.bind_gui_window(
        launcher=launcher, environment={'GZ_PARTITION': 'mecanum_b2_test'},
        partition='mecanum_b2_test', deadline=5.0,
        steady=fake['steady'], sleep=fake['sleep'], sink=sink, **kwargs,
    ))
    assert result['window_id'] == ids[-1]
    diag = next(facts for event, facts in sink.records
                if event == 'gui_window_discovery_pass')
    assert diag['candidate_count'] == 70
    assert diag['owned_match_count'] == 1
    assert diag['diagnostics_truncated'] is True
    assert len(runner._canonical_json_bytes(diag)) <= 12 * 1024
    assert len([c for c, _deadline in launcher.commands
                if c[0].endswith('xprop')]) == 70
    assert 'title 0x' not in json.dumps(diag, sort_keys=True)


def test_window_discovery_retries_only_a_window_that_disappears_mid_read():
    """A vanished X11 id is stale; an unrelated xprop error is not hidden."""
    fake = _window_discovery_fakes(
        [_window_line('0x44'), _window_line('0x44')],
        [{'0x44': (b'', 1, b'X Error of failed request: BadWindow')},
         {'0x44': _gazebo_properties()}],
    )
    kwargs = dict(fake)
    launcher, sink = kwargs.pop('launcher'), kwargs.pop('sink')
    kwargs.pop('clock')
    kwargs.pop('steady')
    kwargs.pop('sleep')
    result = asyncio.run(runner.bind_gui_window(
        launcher=launcher, environment={'GZ_PARTITION': 'mecanum_b2_test'},
        partition='mecanum_b2_test', deadline=1.0,
        steady=fake['steady'], sleep=fake['sleep'], sink=sink, **kwargs,
    ))
    assert result['window_id'] == '0x44'
    exits = [facts for event, facts in sink.records
             if event == 'owned_helper_exit'
             and facts.get('window_id') == '0x44']
    assert exits[0]['result'] == 'WINDOW_DISAPPEARED_DURING_PROPERTY_READ'


def test_window_discovery_helper_failure_is_not_reported_as_no_window():
    """An X transport/parser helper failure aborts instead of polling on."""
    fake = _window_discovery_fakes(
        [_window_line('0x51')], [{}],
        helper_failures={'0x51': (b'', 1, b'unable to open display')},
    )
    kwargs = dict(fake)
    launcher, sink = kwargs.pop('launcher'), kwargs.pop('sink')
    kwargs.pop('clock')
    kwargs.pop('steady')
    kwargs.pop('sleep')
    with pytest.raises(runner.ObservationFailure,
                       match='window_helper helper failed'):
        asyncio.run(runner.bind_gui_window(
            launcher=launcher,
            environment={'GZ_PARTITION': 'mecanum_b2_test'},
            partition='mecanum_b2_test', deadline=1.0,
            steady=fake['steady'], sleep=fake['sleep'], sink=sink, **kwargs,
        ))
    passes = [facts for event, facts in sink.records
              if event == 'gui_window_discovery_pass']
    assert passes[-1]['outcome'] == 'WINDOW_PROPERTY_HELPER_FAILURE'


@pytest.mark.parametrize('fail_persist', [False, True])
def test_r007_a01_run_uses_persisted_revalidation_sequence(
        tmp_path, fail_persist):
    """The actual binder feeds the persisted revalidation event to request."""
    args, deps, _, _, root, _, state = make_runner_inputs(
        tmp_path, production_supervisor=True,
    )
    fake = _window_discovery_fakes(
        [_window_line('0x22')], [{'0x22': _gazebo_properties()}],
    )

    async def production_binder(**kwargs):
        kwargs['launcher'] = fake['launcher']
        for name in ('process_identity_reader', 'parent_reader',
                     'executable_reader', 'argv_reader'):
            kwargs[name] = fake[name]
        kwargs['partition_reader'] = lambda _pid: kwargs['partition']
        return await runner.bind_gui_window(**kwargs)

    deps['bind_gui_window'] = production_binder
    deps['revalidate_gui_window'] = production_binder
    if fail_persist:
        class FailingSink(runner.ObservationEvidenceSink):
            def record(self, event, facts):
                if event == 'gui_window_capture_binding_verified':
                    raise OSError('injected revalidation persistence failure')
                return super().record(event, facts)

        deps['sink_factory'] = FailingSink
    verdict = asyncio.run(runner._run(args, dependencies=deps))
    if fail_persist:
        assert verdict == 'FAIL'
        assert 'request' not in state
        assert not list(root.glob('review_mailbox/requests/*.json'))
        return
    assert verdict == 'PASS'
    records = [json.loads(line) for line in
               (root / 'observation.jsonl').read_text().splitlines()]
    event = next(r for r in records
                 if r['event'] == 'gui_window_capture_binding_verified')
    assert (state['request']['window_process_identity']['evidence_sequence']
            == event['sequence'])


@pytest.mark.parametrize('role', ['window_helper', 'capture_helper',
                                  'publisher'])
def test_r007_a02_non_xprop_badwindow_is_failure(role):
    """The X11 exception is limited to the xprop discovery operation."""
    fake = _window_discovery_fakes(
        [''], [{'0x51': (b'', 1, b'X Error of failed request: BadWindow')}],
    )
    fake['launcher'].pass_index = 0
    command = (('/usr/bin/other', '-id', '0x51') if role == 'window_helper'
               else ('/usr/bin/xprop', '-id', '0x51', '_NET_WM_PID',
                     'WM_CLASS', '_NET_WM_NAME', 'WM_NAME'))
    with pytest.raises(runner.ObservationFailure, match='BadWindow'):
        asyncio.run(runner._owned_helper(
            fake['launcher'], command, {}, role=role,
            deadline=1.0, steady=fake['steady'], sink=None,
            window_id='0x51',
        ))


def test_r007_a02_repeated_badwindow_expires_same_deadline():
    """Stale XIDs are reconsidered without refreshing the deadline."""
    fake = _window_discovery_fakes(
        [_window_line('0x51')],
        [{'0x51': (b'', 1, b'X Error of failed request: BadWindow')}],
    )
    kwargs = dict(fake)
    launcher, sink = kwargs.pop('launcher'), kwargs.pop('sink')
    kwargs.pop('clock')
    kwargs.pop('steady')
    kwargs.pop('sleep')
    with pytest.raises(runner.ReviewInvalidated, match='deadline expired'):
        asyncio.run(runner.bind_gui_window(
            launcher=launcher, environment={}, partition='mecanum_b2_test',
            deadline=0.25, steady=fake['steady'], sleep=fake['sleep'],
            sink=sink, **kwargs,
        ))
    assert fake['clock'][0] == pytest.approx(0.25)


def test_r007_a02_stdout_badwindow_does_not_hide_xprop_failure():
    """Only stderr X11 diagnostics can identify a disappeared XID."""
    fake = _window_discovery_fakes(
        [_window_line('0x51')],
        [{'0x51': (b'BadWindow in title', 1, b'cannot open display')}],
    )
    kwargs = dict(fake)
    launcher, sink = kwargs.pop('launcher'), kwargs.pop('sink')
    kwargs.pop('clock')
    kwargs.pop('steady')
    kwargs.pop('sleep')
    with pytest.raises(runner.ObservationFailure, match='cannot open display'):
        asyncio.run(runner.bind_gui_window(
            launcher=launcher, environment={}, partition='mecanum_b2_test',
            deadline=1.0, steady=fake['steady'], sleep=fake['sleep'],
            sink=sink, **kwargs,
        ))


@pytest.mark.parametrize('failed_event', [
    'owned_helper_exit', 'gui_window_discovery_pass',
])
def test_r007_a03_latches_helper_failure_before_sink_error(failed_event):
    """A failed diagnostic write cannot replace a detected helper failure."""
    fake = _window_discovery_fakes(
        [_window_line('0x51')],
        [{'0x51': (b'', 1, b'cannot open display')}],
    )
    latch = runner.FirstFailureLatch(monotonic_ns=lambda: 123456)
    writes = []
    failed = [False]

    class FailingSink:
        def record(self, event, facts):
            if not failed[0] and event == failed_event and (
                    event != 'owned_helper_exit'
                    or facts.get('result') == 'HELPER_FAILED'):
                failed[0] = True
                raise OSError('injected sink failure')
            writes.append(event)

    sink = runner.FirstFailureEvidenceSink(FailingSink(), latch)
    kwargs = dict(fake)
    launcher = kwargs.pop('launcher')
    kwargs.pop('sink')
    kwargs.pop('clock')
    kwargs.pop('steady')
    kwargs.pop('sleep')
    with pytest.raises((runner.ObservationFailure, OSError)):
        asyncio.run(runner.bind_gui_window(
            launcher=launcher, environment={}, partition='mecanum_b2_test',
            deadline=1.0, steady=fake['steady'], sleep=fake['sleep'],
            sink=sink, **kwargs,
        ))
    assert 'cannot open display' in latch.primary_failure['reason']
    assert latch.primary_failure['source'] == 'window_helper'
    assert latch.primary_failure['phase'] == 'window_discovery'
    assert latch.primary_failure['detection_monotonic_ns'] == 123456
    assert any(item['event'] == failed_event for item in latch.cleanup_errors)
    sink.record('sink_recovered', {})
    assert 'sink_recovered' in writes


@pytest.mark.parametrize('delayed', [False, True])
def test_r007_b01_classified_badwindow_is_accepted_by_real_monitor(
        monkeypatch, delayed):
    """A gated xprop stale-window result is not an unexpected exit."""
    fake = _window_discovery_fakes(
        [''], [{'0x51': (b'', 1, b'X Error of failed request: BadWindow')}],
    )
    launcher = fake['launcher']
    launcher.pass_index = 0
    launcher.waiters = {}
    launcher.cleanup_dispatches = {}
    launcher.observed_exits = {}
    launcher.reported_exit_ids = set()
    original = launcher.start_gated
    release = asyncio.Event()
    pending_seen = asyncio.Event()
    classify = runner._helper_exit_classification

    def observe_classification(*args):
        outcome = classify(*args)
        if outcome == 'pending':
            pending_seen.set()
        return outcome

    monkeypatch.setattr(runner, '_helper_exit_classification',
                        observe_classification)

    async def start(*args, **kwargs):
        process = await original(*args, **kwargs)
        record = launcher.records[-1]
        record.identity = {'pid': process.pid, 'process_group_id': process.pid,
                           'session_id': process.pid, 'start_ticks': 1}
        record.gate.update({'role': 'window_helper',
                            'planned_command': list(args[0]),
                            'verified_identity': dict(record.identity)})
        if delayed:
            communicate = process.communicate

            async def blocked_communicate():
                await release.wait()
                return await communicate()

            process.communicate = blocked_communicate
        launcher.waiters[id(process)] = asyncio.create_task(process.wait())
        return process

    launcher.start_gated = start
    stop = asyncio.Event()

    class Sink:
        def record(self, event, facts):
            if event == 'owned_process_exit':
                stop.set()

    async def run():
        command = ('/usr/bin/xprop', '-id', '0x51', '_NET_WM_PID',
                   'WM_CLASS', '_NET_WM_NAME', 'WM_NAME')
        helper = asyncio.create_task(runner._owned_helper(
            launcher, command, {}, deadline=time.monotonic() + 2,
            sink=Sink(), window_id='0x51', return_metadata=True,
        ))
        monitor = asyncio.create_task(runner._monitor_owned_processes(
            launcher=launcher, supervisor=SimpleNamespace(owned=[]),
            sink=Sink(), stop_event=stop, deadline=time.monotonic() + 2,
            steady=time.monotonic,
        ))
        if delayed:
            await asyncio.wait_for(pending_seen.wait(), 1)
            assert not monitor.done()
            release.set()
        await helper
        await monitor

    asyncio.run(run())


@pytest.mark.parametrize('case', [
    'missing', 'expired', 'owner_cancelled', 'identity_unknown', 'other_role',
])
def test_r007_b01_monitor_rejects_unverified_exit(case):
    """Pending ownership and unrelated nonzero exits remain fail closed."""
    async def run():
        pid = 201
        identity = {'pid': pid, 'process_group_id': pid,
                    'session_id': pid, 'start_ticks': 1}
        command = ('/usr/bin/xprop', '-id', '0x51', '_NET_WM_PID',
                   'WM_CLASS', '_NET_WM_NAME', 'WM_NAME')
        process = SimpleNamespace(pid=pid, returncode=1)
        gate = {'role': 'window_helper', 'planned_command': list(command),
                'verified_identity': dict(identity), 'nonce': 'nonce',
                'binding_sha256': 'f' * 64}
        owner = asyncio.get_running_loop().create_future()
        if case == 'owner_cancelled':
            owner.cancel()
        record = SimpleNamespace(
            name='capture_helper' if case == 'other_role' else 'window_helper',
            pid=pid, process=process, command=command, gate=gate,
            gate_released=True,
            identity=None if case == 'identity_unknown' else identity,
        )
        if case != 'missing':
            record.helper_classification = {
                'state': 'pending', 'owner': owner, 'window_id': '0x51',
                'deadline': 0 if case == 'expired' else time.monotonic() + 2,
            }
        waiter = asyncio.get_running_loop().create_future()
        waiter.set_result(1)
        launcher = SimpleNamespace(
            records=[record], waiters={id(process): waiter},
            cleanup_dispatches={}, observed_exits={}, reported_exit_ids=set(),
        )
        with pytest.raises(runner.ObservationFailure, match='unexpectedly'):
            await runner._monitor_owned_processes(
                launcher=launcher, supervisor=SimpleNamespace(owned=[]),
                sink=SimpleNamespace(record=lambda *_args: None),
                stop_event=asyncio.Event(), deadline=time.monotonic() + 2,
                steady=time.monotonic,
            )

    asyncio.run(run())


def test_r007_b01_discovery_and_monitor_accept_stale_then_valid():
    """Production discovery and monitor agree on a stale xprop exit."""
    fake = _window_discovery_fakes(
        [_window_line('0x51'), _window_line('0x52')],
        [{'0x51': (b'', 1, b'X Error of failed request: BadWindow')},
         {'0x52': _gazebo_properties()}],
    )
    launcher = fake['launcher']
    launcher.waiters = {}
    launcher.cleanup_dispatches = {}
    launcher.observed_exits = {}
    launcher.reported_exit_ids = set()
    original = launcher.start_gated
    observed = asyncio.Event()
    stop = asyncio.Event()
    events = []

    async def start(*args, **kwargs):
        process = await original(*args, **kwargs)
        launcher.waiters[id(process)] = asyncio.create_task(process.wait())
        return process

    launcher.start_gated = start

    class Sink:
        def record(self, event, facts):
            events.append((event, facts))
            if (event == 'owned_process_exit'
                    and facts.get('exit_status') == 1):
                observed.set()

    async def run():
        monitor = asyncio.create_task(runner._monitor_owned_processes(
            launcher=launcher, supervisor=SimpleNamespace(owned=[]),
            sink=Sink(), stop_event=stop, deadline=2.0, steady=fake['steady'],
        ))
        try:
            result = await runner.bind_gui_window(
                launcher=launcher, environment={}, partition='mecanum_b2_test',
                deadline=1.0, steady=fake['steady'], sleep=fake['sleep'],
                sink=Sink(),
                process_identity_reader=fake['process_identity_reader'],
                parent_reader=fake['parent_reader'],
                executable_reader=fake['executable_reader'],
                argv_reader=fake['argv_reader'],
                partition_reader=fake['partition_reader'],
            )
            await asyncio.wait_for(observed.wait(), 1)
            assert result['window_id'] == '0x52'
        finally:
            stop.set()
            await monitor
        exit_fact = next(f for e, f in events if e == 'owned_process_exit'
                         and f.get('exit_status') == 1)
        assert exit_fact['helper_outcome'] == 'accepted'
        assert exit_fact['requested_cleanup_exit'] is False

    asyncio.run(run())


@pytest.mark.parametrize('classification', [
    'accepted', 'missing', 'identity_mismatch', 'other_command', 'pending',
])
def test_r007_b01_final_sweep_classifies_unreported_helper_exit(
        tmp_path, classification):
    """The production final sweep accepts only a fully classified exit."""
    args, deps, _, _, root, _, state = make_runner_inputs(
        tmp_path, production_supervisor=True,
    )
    capture = deps['capture_window_bounded']

    async def capture_with_launcher(*args, **kwargs):
        state['launcher_for_sweep'] = kwargs['launcher']
        return await capture(*args, **kwargs)

    deps['capture_window_bounded'] = capture_with_launcher

    class InjectExitSink(runner.ObservationEvidenceSink):
        def record(self, event, facts):
            sequence = super().record(event, facts)
            if event == 'observation_result':
                launcher = state['launcher_for_sweep']
                pid = 920001
                identity = {'pid': pid, 'process_group_id': pid,
                            'session_id': pid, 'start_ticks': 1}
                command = ('/usr/bin/xprop', '-id', '0x51', '_NET_WM_PID',
                           'WM_CLASS', '_NET_WM_NAME', 'WM_NAME')
                process = SimpleNamespace(pid=pid, returncode=1)
                gate = {'role': 'window_helper', 'planned_command':
                        list(command), 'verified_identity': dict(identity),
                        'nonce': 'test-nonce', 'binding_sha256': 'f' * 64}
                record = SimpleNamespace(
                    name='window_helper', pid=pid, process=process,
                    identity=identity, identity_error=None, command=command,
                    gate=gate, gate_released=True,
                )
                if classification != 'missing':
                    classification_state = {
                        'state': 'accepted_badwindow', 'identity': identity,
                        'exit_status': 1, 'binding_sha256': 'f' * 64,
                        'nonce': 'test-nonce', 'window_id': '0x51',
                    }
                    if classification == 'identity_mismatch':
                        classification_state['identity'] = {
                            **identity, 'start_ticks': 2,
                        }
                    elif classification == 'other_command':
                        gate['planned_command'] = ['/usr/bin/other', '0x51']
                    elif classification == 'pending':
                        classification_state.update({
                            'state': 'pending',
                            'owner': (
                                asyncio.get_running_loop().create_future()
                            ),
                            'deadline': time.monotonic() + 2,
                        })
                    record.helper_classification = classification_state
                waiter = asyncio.get_running_loop().create_future()
                waiter.set_result(1)
                launcher.records.append(record)
                launcher.identities[id(process)] = identity
                launcher.waiters[id(process)] = waiter
            return sequence

    deps['sink_factory'] = InjectExitSink
    verdict = asyncio.run(runner._run(args, dependencies=deps))
    assert verdict == ('PASS' if classification == 'accepted' else 'FAIL')
    records = [json.loads(line) for line in
               (root / 'observation.jsonl').read_text().splitlines()]
    event = next(r['facts'] for r in records
                 if r['event'] == 'owned_process_exit_during_cleanup'
                 and r['facts']['process'] == 'window_helper')
    assert event['exit_status'] == 1
    expected_outcome = {
        'accepted': 'accepted', 'pending': 'pending',
    }.get(classification, 'unexpected')
    assert event['helper_outcome'] == expected_outcome
    assert event['dispatch_observed_before_exit'] is False


def test_r007_b02_deadline_precedes_mismatch_even_if_sink_fails():
    """Keep both detected errors when a partial pass ends at deadline."""
    fake = _window_discovery_fakes(
        [_window_line('0x71') + _window_line('0x72')],
        [{'0x71': _gazebo_properties(), '0x72': _gazebo_properties()}],
    )
    launcher = fake['launcher']
    original = launcher.start_gated

    async def finish_during_first_property(*args, **kwargs):
        result = await original(*args, **kwargs)
        if args[0][0].endswith('xprop'):
            communicate = result.communicate

            async def complete_at_deadline():
                output = await communicate()
                fake['clock'][0] = 1.0
                return output

            result.communicate = complete_at_deadline
        return result

    launcher.start_gated = finish_during_first_property
    latch = runner.FirstFailureLatch(monotonic_ns=lambda: 123456)

    class Sink:
        def record(self, event, facts):
            if event == 'gui_window_discovery_pass':
                raise OSError('diagnostic sink failed')

    sink = runner.FirstFailureEvidenceSink(Sink(), latch)
    kwargs = {key: fake[key] for key in (
        'process_identity_reader', 'parent_reader', 'executable_reader',
        'argv_reader', 'partition_reader',
    )}
    expected = {'window_id': '0x99'}
    with pytest.raises((runner.ObservationFailure, OSError)):
        asyncio.run(runner.bind_gui_window(
            launcher=launcher, environment={}, partition='mecanum_b2_test',
            deadline=1.0, steady=fake['steady'], sleep=fake['sleep'],
            sink=sink, expected_window=expected, **kwargs,
        ))
    assert 'deadline expired' in latch.primary_failure['reason']
    assert any('binding changed' in item['reason']
               for item in latch.secondary_failures)
    assert latch.cleanup_errors


def test_window_discovery_sink_failure_fails_closed():
    """A diagnostics sink failure cannot turn a missing window into success."""
    fake = _window_discovery_fakes([''], [{}])

    class BrokenSink:
        def record(self, event, facts):
            if event == 'gui_window_discovery_pass':
                raise OSError('injected discovery journal failure')
    kwargs = dict(fake)
    launcher = kwargs.pop('launcher')
    kwargs.pop('sink')
    kwargs.pop('clock')
    kwargs.pop('steady')
    kwargs.pop('sleep')
    with pytest.raises(OSError, match='journal failure'):
        asyncio.run(runner.bind_gui_window(
            launcher=launcher,
            environment={'GZ_PARTITION': 'mecanum_b2_test'},
            partition='mecanum_b2_test', deadline=1.0,
            steady=fake['steady'], sleep=fake['sleep'], sink=BrokenSink(),
            **kwargs,
        ))


def test_window_discovery_fails_if_owned_gui_identity_changes_mid_pass():
    """A new GUI PID identity fails closed before inspecting a client."""
    fake = _window_discovery_fakes([_window_line('0x61')],
                                   [{'0x61': _gazebo_properties()}])
    calls = [0]
    base = fake['process_identity_reader']

    def changed(pid):
        calls[0] += 1
        result = dict(base(pid))
        if pid == 101 and calls[0] >= 2:
            result['start_ticks'] += 1
        return result
    kwargs = dict(fake)
    launcher, sink = kwargs.pop('launcher'), kwargs.pop('sink')
    kwargs.pop('clock')
    kwargs.pop('steady')
    kwargs.pop('sleep')
    kwargs['process_identity_reader'] = changed
    with pytest.raises(runner.ObservationFailure,
                       match='owned GUI identity changed'):
        asyncio.run(runner.bind_gui_window(
            launcher=launcher,
            environment={'GZ_PARTITION': 'mecanum_b2_test'},
            partition='mecanum_b2_test', deadline=1.0,
            steady=fake['steady'], sleep=fake['sleep'], sink=sink, **kwargs,
        ))


def test_window_binding_revalidation_rejects_changed_window_before_capture():
    """The selected XID/PID must match a fresh bounded discovery pass."""
    fake = _window_discovery_fakes(
        [_window_line('0x72')], [{'0x72': _gazebo_properties()}],
    )
    expected = {
        'window_id': '0x71', 'pid': 102, 'pgid': 101,
        'process_start_ticks': 9, 'gz_partition': 'mecanum_b2_test',
        'executable': '/usr/bin/gz', 'argv': ['/usr/bin/gz', 'sim', '-g'],
    }
    kwargs = dict(fake)
    launcher, sink = kwargs.pop('launcher'), kwargs.pop('sink')
    kwargs.pop('clock')
    kwargs.pop('steady')
    kwargs.pop('sleep')
    with pytest.raises(runner.ObservationFailure,
                       match='binding changed before capture'):
        asyncio.run(runner.bind_gui_window(
            launcher=launcher,
            environment={'GZ_PARTITION': 'mecanum_b2_test'},
            partition='mecanum_b2_test', deadline=1.0,
            steady=fake['steady'], sleep=fake['sleep'], sink=sink,
            expected_window=expected, **kwargs,
        ))


def test_window_capture_uses_injected_qt_api_and_writes_one_window_png(
        tmp_path):
    """Test helper for RUN007 offline behavior."""
    target = tmp_path / 'screenshots'
    target.mkdir(mode=448)
    pixels = bytes((1, 2, 3, 255, 4, 5, 6, 255))

    class Bits:

        def setsize(self, size):
            """Test helper for RUN007 offline behavior."""
            assert size == len(pixels)

        def __bytes__(self):
            return pixels

    class Image:
        Format_RGBA8888 = 7

        def isNull(self):
            """Test helper for RUN007 offline behavior."""
            return False

        def width(self):
            """Test helper for RUN007 offline behavior."""
            return 2

        def height(self):
            """Test helper for RUN007 offline behavior."""
            return 1

        def save(self, buffer, fmt):
            """Test helper for RUN007 offline behavior."""
            buffer.array.extend(b'PNG-test-fixture')
            return fmt == 'PNG'

        def convertToFormat(self, _fmt):
            """Test helper for RUN007 offline behavior."""
            return self

        def bits(self):
            """Test helper for RUN007 offline behavior."""
            return Bits()

        def byteCount(self):
            """Test helper for RUN007 offline behavior."""
            return len(pixels)

        @classmethod
        def fromData(cls, _data, _fmt):
            """Test helper for RUN007 offline behavior."""
            return cls()

    class Pixmap:

        def isNull(self):
            """Test helper for RUN007 offline behavior."""
            return False

        def toImage(self):
            """Test helper for RUN007 offline behavior."""
            return Image()

    class Screen:

        def grabWindow(self, window_id):
            """Test helper for RUN007 offline behavior."""
            assert window_id == 18
            return Pixmap()

    class App:

        @staticmethod
        def instance():
            """Test helper for RUN007 offline behavior."""
            return App()

        def primaryScreen(self):
            """Test helper for RUN007 offline behavior."""
            return Screen()

    class QByteArray(bytearray):
        pass

    class Buffer:

        def __init__(self, array):
            """Test helper for RUN007 offline behavior."""
            self.array = array

        def close(self):
            """Test helper for RUN007 offline behavior."""
            pass

    def buffer_open(_self, _mode):
        return True

    setattr(Buffer, 'open', buffer_open)

    def api():
        return App, Image, Buffer, QByteArray, SimpleNamespace(WriteOnly=1)

    path = target / 'capture.png'
    result = runner.capture_x11_window('0x12', path, qt_api_factory=api)
    assert result['width'] == 2 and result['height'] == 1
    assert result['sha256'] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert path.stat().st_mode & 511 == 384


def test_window_capture_rejects_uniform_blank_frame(tmp_path):
    """Test helper for RUN007 offline behavior."""
    target = tmp_path / 'screenshots'
    target.mkdir(mode=448)
    pixels = b'\x00\x00\x00\xff' * 4

    class Bits:

        def setsize(self, _size):
            """Test helper for RUN007 offline behavior."""
            pass

        def __bytes__(self):
            return pixels

    class Image:
        Format_RGBA8888 = 1

        def isNull(self):
            """Test helper for RUN007 offline behavior."""
            return False

        def width(self):
            """Test helper for RUN007 offline behavior."""
            return 2

        def height(self):
            """Test helper for RUN007 offline behavior."""
            return 2

        def save(self, buffer, _fmt):
            """Test helper for RUN007 offline behavior."""
            buffer.array.extend(b'png')
            return True

        def convertToFormat(self, _fmt):
            """Test helper for RUN007 offline behavior."""
            return self

        def bits(self):
            """Test helper for RUN007 offline behavior."""
            return Bits()

        def byteCount(self):
            """Test helper for RUN007 offline behavior."""
            return len(pixels)

        @classmethod
        def fromData(cls, _data, _fmt):
            """Test helper for RUN007 offline behavior."""
            return cls()

    class Pixmap:

        def isNull(self):
            """Test helper for RUN007 offline behavior."""
            return False

        def toImage(self):
            """Test helper for RUN007 offline behavior."""
            return Image()

    class Screen:

        def grabWindow(self, _window):
            """Test helper for RUN007 offline behavior."""
            return Pixmap()

    class App:

        @staticmethod
        def instance():
            """Test helper for RUN007 offline behavior."""
            return App()

        def primaryScreen(self):
            """Test helper for RUN007 offline behavior."""
            return Screen()

    class Array(bytearray):
        pass

    class Buffer:

        def __init__(self, array):
            """Test helper for RUN007 offline behavior."""
            self.array = array

        def close(self):
            """Test helper for RUN007 offline behavior."""
            pass

    def buffer_open(_self, _mode):
        return True

    setattr(Buffer, 'open', buffer_open)

    with pytest.raises(runner.ObservationFailure, match='uniformly blank'):
        runner.capture_x11_window(
            '0x12', None,
            qt_api_factory=lambda: (
                App, Image, Buffer, Array,
                SimpleNamespace(WriteOnly=1)))


@pytest.mark.parametrize('fault,match', [
    ('no_clock', 'clock readiness timed out'),
    ('inhibit', 'paused and inhibited'),
    ('clock_advance', 'clock advanced'),
    ('heartbeat', 'heartbeat'),
    ('foreign_node', 'unexpected ROS graph')])
def test_observation_health_fails_closed_for_clock_status_and_graph(fault,
                                                                    match):
    """Test helper for RUN007 offline behavior."""
    from collections import deque
    now = [0.0]
    session = str(uuid.uuid4())
    config = 'c' * 64

    class Observer:

        def __init__(self):
            """Test helper for RUN007 offline behavior."""
            self.events = deque()
            self.sequence = 0

        def spin_once(self, _timeout):
            """Test helper for RUN007 offline behavior."""
            self.sequence += 1
            received = now[0]
            if fault != 'no_clock':
                clock = (2,
                         0) if (fault == 'clock_advance'
                                and self.sequence > 2) else (1, 0)
                self.events.append(('clock', SimpleNamespace(sec=clock[0],
                                                             nanosec=clock[1]),
                                    received, int(received * 1000000000.0)))
            if fault != 'heartbeat' or self.sequence == 1:
                self.events.append(('backend',
                                    SimpleNamespace(
                                        session_id=session,
                                        config_hash=config,
                                        backend_instance_id='backend',
                                        header=SimpleNamespace(
                                            frame_id='b2_training_arena'),
                                        paused=fault != 'inhibit',
                                        actuator_inhibited=fault != 'inhibit',
                                        fault_flags=0,
                                        applied_receipt_valid=False,
                                        status_sequence=self.sequence),
                                    received,
                                    int(received * 1000000000.0)))
            now[0] += 0.2

        def node_inventory(self):
            """Test helper for RUN007 offline behavior."""
            nodes = list(runner.EXPECTED_ROS_NODES)
            return nodes + [('foreign_node',
                             '/')] if fault == 'foreign_node' else nodes
    plan = SimpleNamespace(session_id=session, config_hash=config)
    review = SimpleNamespace(is_set=lambda: False)
    with pytest.raises(runner.ObservationFailure, match=match):
        asyncio.run(runner.evaluate_observation(plan=plan,
                                                observer=Observer(),
                                                duration_s=60,
                                                steady=lambda: now[0],
                                                ack_event=review, deadline=4,
                                                sink=None,
                                                readiness_complete_event=(
                                                    SimpleNamespace(
                                                        is_set=lambda: True)),
                                                clock_ready_timeout_s=0.4))


def _capture_qt_api(pixels, png_bytes=b'PNG-offline-fixture'):
    class Bits:
        def setsize(self, _size):
            return None

        def __bytes__(self):
            return pixels

    class Image:
        Format_RGBA8888 = 7

        def isNull(self):
            return False

        def width(self):
            return len(pixels) // 4

        def height(self):
            return 1

        def save(self, buffer, _fmt):
            buffer.array.extend(png_bytes)
            return True

        def convertToFormat(self, _fmt):
            return self

        def bits(self):
            return Bits()

        def byteCount(self):
            return len(pixels)

        @classmethod
        def fromData(cls, _data, _fmt):
            return cls()

    class Pixmap:
        def isNull(self):
            return False

        def toImage(self):
            return Image()

    class Screen:
        def grabWindow(self, _window_id):
            return Pixmap()

    class App:
        @staticmethod
        def instance():
            return App()

        def primaryScreen(self):
            return Screen()

    class Buffer:
        def __init__(self, array):
            self.array = array

        def open_buffer(self, _mode):
            return True

        def close(self):
            return None

    setattr(Buffer, 'open', Buffer.open_buffer)

    return lambda: (App, Image, Buffer, bytearray,
                    SimpleNamespace(WriteOnly=1))


def test_capture_without_destination_returns_validated_bytes():
    """Capture production PNG validation without forcing a destination."""
    png = b'PNG-offline-fixture'
    result = runner.capture_x11_window(
        '0x12', None,
        qt_api_factory=_capture_qt_api(
            b'\x01\x02\x03\xff\x04\x05\x06\xff', png),
    )
    assert result['path'] is None
    assert result['png_bytes'] == png
    assert result['sha256'] == hashlib.sha256(png).hexdigest()
    assert result['width'] == 2 and result['height'] == 1


def test_window_binding_skips_tree_metadata_and_binds_owned_child():
    """Bind the unique nested client window through owned process lineage."""
    tree = ('xwininfo: Window id: 0x01 (the root window)\n'
            '  Root window id: 0x01 (the root window)\n'
            '  Parent window id: 0x00 (none)\n'
            '     2 children:\n'
            '     0x10 "WM frame": ("wm", "Xfwm4") 900x700+0+0\n'
            '        1 child:\n'
            '        0x11 "Gazebo": ("gz sim", "Gazebo") 800x600+1+1\n')
    properties = {
        '0x10': ('_NET_WM_PID(CARDINAL) = 900\n'
                 'WM_CLASS(STRING) = "wm", "Xfwm4"\n'),
        '0x11': ('_NET_WM_PID(CARDINAL) = 102\n'
                 'WM_CLASS(STRING) = "gz sim", "Gazebo"\n'),
    }
    gui_identity = {
        'pid': 101, 'process_group_id': 101, 'session_id': 101,
        'start_ticks': 7,
    }
    child_identity = {
        'pid': 102, 'process_group_id': 101, 'session_id': 101,
        'start_ticks': 9,
    }

    class Process:
        def __init__(self, pid, output):
            self.pid = pid
            self.output = output.encode()

        async def communicate(self):
            return self.output, b''

        async def wait(self):
            return 0

    class Launcher:
        def __init__(self):
            self.records = [SimpleNamespace(
                name='gui', pid=101, process=object(),
                identity=gui_identity,
                command=('/usr/bin/gz', 'sim', '-g'))]
            self.waiters = {}

        async def start_gated(self, command, _environment, *, role,
                              deadline, steady):
            if command[0] == '/usr/bin/xwininfo':
                output = tree
            else:
                output = properties[command[2]]
            process = Process(200 + len(self.records), output)
            self.records.append(SimpleNamespace(
                name=role, pid=process.pid, process=process,
                identity={'pid': process.pid}, command=tuple(command),
                wrapper_command=('fake-gate-wrapper',),
                gate={'nonce': 'fake-nonce', 'binding_sha256': 'f' * 64},
                gate_released=True,
            ))
            return process

    identities = {101: gui_identity, 102: child_identity}
    result = asyncio.run(runner.bind_gui_window(
        launcher=Launcher(), environment={'GZ_PARTITION': 'part-run'},
        partition='part-run', deadline=10, steady=lambda: 0,
        process_identity_reader=lambda pid: identities[pid],
        parent_reader=lambda pid: {102: 101, 101: 1}[pid],
        executable_reader=lambda _path: '/opt/gz/bin/gz',
        argv_reader=lambda _pid: ['/opt/gz/bin/gz', 'sim', '-g'],
        partition_reader=lambda _pid: 'part-run',
    ))
    assert result['window_id'] == '0x11'
    assert result['pid'] == 102 and result['pgid'] == 101
    assert result['argv'] == ['/opt/gz/bin/gz', 'sim', '-g']


def test_capture_helper_is_async_owned_and_health_can_run_while_pending():
    """Keep capture off the monitor loop and retain its owned handle."""
    png = b'\x89PNG\r\n\x1a\n' + b'\x00\x00\x00\rIHDR'
    png += (2).to_bytes(4, 'big') + (1).to_bytes(4, 'big') + b'payload'
    started = asyncio.Event()
    release = asyncio.Event()
    alive = {'value': True}

    class Process:
        pid = 700
        returncode = None

        async def communicate(self):
            started.set()
            await release.wait()
            self.returncode = 0
            alive['value'] = False
            return png, b''

        async def wait(self):
            return self.returncode

    process = Process()
    identity = {
        'pid': 700, 'process_group_id': 700, 'session_id': 700,
        'start_ticks': 44,
    }

    class Launcher:
        def __init__(self):
            self.records = []
            self.waiters = {}
            self.identities = {}

        async def start_gated(self, command, _environment, *, role,
                              deadline, steady):
            record = SimpleNamespace(
                name=role, pid=700, process=process,
                identity=identity, command=tuple(command),
                wrapper_command=('fake-gate-wrapper',),
                gate={'nonce': 'fake-nonce', 'binding_sha256': 'f' * 64},
                gate_released=True, identity_error=None)
            self.records.append(record)
            self.identities[id(process)] = identity
            return process

        def group_alive(self, _process):
            return alive['value']

        async def stop_group(self, _process, _sig):
            alive['value'] = False
            process.returncode = -1

    launcher = Launcher()
    clock = [0.0]
    health = []

    async def monitor_health():
        await started.wait()
        health.append('checked')
        release.set()

    async def scenario():
        capture = asyncio.create_task(runner.capture_x11_window_bounded(
            '0x12', launcher=launcher, environment={}, deadline=5,
            steady=lambda: clock[0]))
        monitor = asyncio.create_task(monitor_health())
        result = await capture
        await monitor
        assert health == ['checked']
        assert result['png_bytes'] == png
        assert result['sha256'] == hashlib.sha256(png).hexdigest()

    asyncio.run(scenario())
    assert launcher.records[0].identity == identity


def test_runner_cancels_capture_and_cleans_owned_helper_on_health_failure(
        tmp_path):
    """Health failure cancels capture and joins all injected runner tasks."""
    args, dependencies, _events, processes, _root, observer, state = \
        make_runner_inputs(tmp_path)
    state['capture_hang'] = True

    async def fail_after_capture_starts(**_kwargs):
        await state['capture_started'].wait()
        raise runner.ObservationFailure('injected inhibit health failure')

    dependencies['evaluate_observation'] = fail_after_capture_starts

    async def run_and_check_tasks():
        verdict = await runner._run(args, dependencies=dependencies)
        current = asyncio.current_task()
        pending = [task for task in asyncio.all_tasks()
                   if task is not current and not task.done()]
        return verdict, pending

    verdict, pending = asyncio.run(run_and_check_tasks())
    assert verdict == 'FAIL'
    assert state['capture_cancelled']
    assert all(process.returncode is not None for _cmd, process in processes)
    assert pending == []
    assert observer.closed == 1


def test_dependency_preflight_runs_before_acquisition_and_launcher(tmp_path):
    """Stop before capacity/process effects on dependency mismatch."""
    args, dependencies, _events, processes, root, _observer, _state = \
        make_runner_inputs(tmp_path)
    acquired = []
    dependencies['acquire'] = lambda *_args: acquired.append(True)

    def missing_module(_name):
        raise ImportError('injected pinned-module failure')

    dependencies['module_importer'] = missing_module
    with pytest.raises(runner.ObservationFailure,
                       match='host dependency verification failed'):
        asyncio.run(runner._run(args, dependencies=dependencies))
    assert acquired == []
    assert processes == []
    assert not root.exists()


def test_publisher_identity_read_failure_retains_handle_and_reports_residue():
    """The Popen handle exists before a live identity read can fail."""
    owned = []

    def popen(*args, **kwargs):
        process = subprocess.Popen(*args, **kwargs)
        owned.append(process)
        return process

    def read_identity(_pid):
        assert len(owned) == 1
        raise OSError('injected proc read failure')
    with pytest.raises(runner.ObservationFailure,
                       match='identity unverified'):
        runner.publish_review_result_bounded(
            '/tmp/request.json', verdict='PASS', reason='reviewed',
            request_deadline=time.monotonic() + 8,
            popen=popen, identity_reader=read_identity,
            helper_command_factory=lambda _role, _planned: _python_target(
                'pass'
            ),
        )
    assert len(owned) == 1
    owned[0].wait(timeout=2)
    assert owned[0].returncode != 0


def test_publisher_communication_error_finalizes_verified_worker():
    """Communication failure signals only the verified wrapper group."""
    signals = []
    processes = []

    class Proxy:
        def __init__(self, *args, **kwargs):
            self.process = subprocess.Popen(*args, **kwargs)
            processes.append(self.process)
            self.pid = self.process.pid

        def poll(self):
            return self.process.poll()

        def wait(self, timeout):
            return self.process.wait(timeout=timeout)

        def communicate(self, timeout):
            raise OSError('injected communicate failure')

    def signal_group(pgid, sig):
        signals.append((pgid, sig))
        os.killpg(pgid, sig)
    with pytest.raises(runner.ObservationFailure, match='communicate failure'):
        runner.publish_review_result_bounded(
            '/tmp/request.json', verdict='PASS', reason='reviewed',
            request_deadline=time.monotonic() + 8, popen=Proxy,
            signal_group=signal_group,
            helper_command_factory=lambda _role, _planned: _python_target(
                'import time; time.sleep(30)'
            ),
        )
    assert signals and signals[0][1] == signal.SIGTERM
    assert processes[0].wait(timeout=2) != 0


def test_publisher_identity_change_never_signals_unverified_group():
    """A changed process-start identity refuses cleanup signaling."""
    signals = []
    identities = []
    processes = []

    def reader(pid):
        identity = runner.process_start_identity(pid)
        identities.append(identity)
        if len(identities) > 1:
            return {**identity, 'start_ticks': identity['start_ticks'] + 1}
        return identity

    def popen(*args, **kwargs):
        process = subprocess.Popen(*args, **kwargs)
        processes.append(process)
        return process

    def fail_after_release(_record):
        raise RuntimeError('trigger finalizer')
    with pytest.raises(runner.ObservationFailure,
                       match='residue unknown.*identity changed'):
        runner.publish_review_result_bounded(
            '/tmp/request.json', verdict='PASS', reason='reviewed',
            request_deadline=time.monotonic() + 8, popen=popen,
            identity_reader=reader, on_started=fail_after_release,
            signal_group=lambda pgid, sig: signals.append((pgid, sig)),
            helper_command_factory=lambda _role, _planned: _python_target(
                'import time; time.sleep(30)'
            ),
        )
    assert signals == []
    assert processes
    assert runner.process_start_identity(processes[0].pid) == identities[0]
    os.killpg(processes[0].pid, signal.SIGTERM)
    processes[0].wait(timeout=2)


def test_publisher_started_callback_failure_finalizes_owned_handle():
    """The callback is before release and failure cleans the owned group."""
    signals = []
    started = []

    def signal_group(pgid, sig):
        signals.append((pgid, sig))
        os.killpg(pgid, sig)

    def fail_evidence(record):
        started.append(record)
        raise RuntimeError('evidence callback failed')

    with pytest.raises(runner.ObservationFailure, match='evidence callback'):
        runner.publish_review_result_bounded(
            '/tmp/request.json', verdict='PASS', reason='reviewed',
            request_deadline=time.monotonic() + 8,
            signal_group=signal_group,
            on_started=fail_evidence,
            helper_command_factory=lambda _role, _planned: _python_target(
                'import time; time.sleep(30)'
            ),
        )
    assert signals and signals[0][1] == signal.SIGTERM
    assert started[0]['identity']['pid'] == started[0]['process'].pid


def test_publisher_wait_failure_records_unknown_residue():
    """A wait error remains residue unknown after dispatch is attempted."""
    signals = []
    processes = []

    class Proxy:
        def __init__(self, *args, **kwargs):
            self.process = subprocess.Popen(*args, **kwargs)
            processes.append(self.process)
            self.pid = self.process.pid

        def poll(self):
            return self.process.poll()

        def communicate(self, timeout):
            raise OSError('injected communicate error')

        def wait(self, timeout):
            raise OSError('injected wait error')

    def signal_group(pgid, sig):
        signals.append((pgid, sig))
        os.killpg(pgid, sig)
    with pytest.raises(runner.ObservationFailure,
                       match='residue unknown.*publisher wait failed'):
        runner.publish_review_result_bounded(
            '/tmp/request.json', verdict='PASS', reason='reviewed',
            request_deadline=time.monotonic() + 8, popen=Proxy,
            signal_group=signal_group,
            helper_command_factory=lambda _role, _planned: _python_target(
                'import time; time.sleep(30)'
            ),
        )
    assert signals and signals[0][1] == signal.SIGTERM
    assert processes[0].wait(timeout=2) != 0


def test_server_template_is_bound_to_run007_and_effective_world():
    """Pin the full effective server argv under the RUN007 evidence root."""
    template = bundle_packet()['commands_argv']['exact_templates']['server']
    expected = (
        '/home/hazan/mecanum_runtime_evidence/B22_GUI_OBSERVATION_RUN007/'
        'runtime_assets/b2_training_arena.B2_SOAK_V1.<session_uuid>'
        '.runtime.sdf'
    )
    assert template[-1] == expected
    assert 'B22_GUI_OBSERVATION_RUN001' not in template[-1]
    session = str(uuid.uuid4())
    world = Path(expected.replace('<session_uuid>', session))
    plan = SimpleNamespace(
        gui_requested=True,
        commands=(
            tuple(template[:-1]) + (str(world),),
            tuple(bundle_packet()['commands_argv']['exact_templates']['gui']),
        ),
        bridge_command=tuple(bundle_packet()['commands_argv'][
            'exact_templates']['parameter_bridge']),
        world_file=world,
        session_id=session,
    )
    runner._validate_plan_commands(plan, bundle_packet(), effective=True)
    run001_world = Path(str(world).replace('RUN007', 'RUN001'))
    plan.world_file = run001_world
    plan.commands = (tuple(template[:-1]) + (str(run001_world),),
                     plan.commands[1])
    with pytest.raises(runner.ObservationFailure,
                       match='canonical RUN007 asset'):
        runner._validate_plan_commands(plan, bundle_packet(), effective=True)


def _native_helper_launcher(on_start=None, delegate_transform=None):
    """Use the production gate with a harmless real Python child process."""

    class Delegate:
        async def start(self, command, environment):
            command = tuple(command)
            if delegate_transform is not None:
                command = tuple(delegate_transform(command))
            return await asyncio.create_subprocess_exec(
                *command, stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=dict(environment), start_new_session=True,
            )

        async def stop_group(self, process, sig):
            os.killpg(process.pid, sig)

        def group_alive(self, process):
            return process.returncode is None

    return runner.TrackedProcessLauncher(Delegate(), on_start=on_start)


def _python_target(code):
    return (sys.executable, '-c', code)


class _PublisherFakeControl:
    def settimeout(self, timeout):
        self.last_timeout = timeout

    def close(self):
        pass


class _PublisherFakeListener(_PublisherFakeControl):
    def bind(self, _path):
        pass

    def listen(self, _backlog):
        pass

    def accept(self):
        return _PublisherFakeControl(), None


class _PublisherFakeProcess:
    pid = 440017

    def __init__(self, *, now=None, communicate_error=None):
        self.returncode = None
        self.now = now
        self.communicate_error = communicate_error
        self.communicate_timeout = None
        self.wait_calls = []

    def poll(self):
        return self.returncode

    def communicate(self, timeout):
        self.communicate_timeout = timeout
        if self.communicate_error is not None:
            raise self.communicate_error
        if self.now is not None:
            self.now[0] = 5.01
        self.returncode = 0
        return b'ok', b''

    def wait(self, timeout):
        self.wait_calls.append(timeout)
        if self.now is not None and self.returncode is None:
            self.now[0] += timeout
        if self.returncode is None:
            raise subprocess.TimeoutExpired('fake-publisher', timeout)
        return self.returncode


def _patch_publisher_operation_fakes(
        monkeypatch, *, now, process, received=None, sent=None):
    listener = _PublisherFakeListener()
    monkeypatch.setattr(
        runner.socket, 'socket', lambda *_args, **_kwargs: listener,
    )
    monkeypatch.setattr(
        runner, '_socket_recv_frame',
        lambda *_args, **_kwargs: next(received),
    )
    monkeypatch.setattr(
        runner, '_socket_send_frame',
        lambda _sock, payload, **_kwargs: sent.append(payload),
    )

    def identity_reader(pid):
        return {
            'pid': pid, 'process_group_id': pid, 'session_id': pid,
            'start_ticks': 91,
        }

    def popen(*_args, **_kwargs):
        return process
    monkeypatch.setattr(runner.subprocess, 'Popen', popen)
    return listener, identity_reader, popen


def _publisher_frames():
    return iter((
        {'schema_id': runner.GATED_HELPER_SCHEMA,
         'event': 'READY_FOR_RELEASE', 'pid': _PublisherFakeProcess.pid,
         'nonce': 'filled-by-test', 'binding_sha256': 'filled-by-test',
         'deadline_monotonic_ns': 5_000_000_000},
        {'schema_id': runner.GATED_HELPER_SCHEMA,
         'event': 'RELEASE_ACCEPTED', 'nonce': 'filled-by-test',
         'binding_sha256': 'filled-by-test'},
        EOFError('target exec closed control channel'),
    ))


def test_publisher_operation_uses_one_budget_after_handshake(monkeypatch):
    """Handshake time is deducted from communicate's remaining budget."""
    now = [0.0]
    process = _PublisherFakeProcess()
    sent = []
    received = _publisher_frames()
    _listener, identity_reader, popen = _patch_publisher_operation_fakes(
        monkeypatch, now=now, process=process, received=received, sent=sent,
    )
    holder = {}

    def callback(record):
        holder['record'] = record
        now[0] = 2.0

    def receive(_sock, **_kwargs):
        frame = next(received)
        if isinstance(frame, BaseException):
            raise frame
        if frame['event'] == 'READY_FOR_RELEASE':
            frame['pid'] = process.pid
            frame['nonce'] = holder['record']['nonce']
            frame['binding_sha256'] = holder['record']['binding_sha256']
            frame['deadline_monotonic_ns'] = (
                holder['record']['operation_deadline_monotonic_ns']
            )
            assert frame == {
                'schema_id': runner.GATED_HELPER_SCHEMA,
                'event': 'READY_FOR_RELEASE', 'pid': process.pid,
                'nonce': holder['record']['nonce'],
                'binding_sha256': holder['record']['binding_sha256'],
                'deadline_monotonic_ns': (
                    holder['record']['operation_deadline_monotonic_ns']
                ),
            }
        if frame['event'] == 'RELEASE_ACCEPTED':
            frame['nonce'] = sent[0]['nonce']
            frame['binding_sha256'] = sent[0]['binding_sha256']
        return frame

    monkeypatch.setattr(runner, '_socket_recv_frame', receive)
    result = runner.publish_review_result_bounded(
        '/tmp/request.json', verdict='PASS', reason='seen',
        request_deadline=20.0, steady=lambda: now[0],
        on_started=callback, identity_reader=identity_reader, popen=popen,
    )
    assert result['exit_status'] == 0
    assert process.communicate_timeout == pytest.approx(3.0)
    assert [item['event'] for item in sent] == ['RELEASE', 'EXEC_COMMIT']


def test_publisher_operation_expiry_after_handshake_blocks_exec_commit(
        monkeypatch):
    """An expired operation deadline cannot release target execution."""
    now = [0.0]
    process = _PublisherFakeProcess()
    sent = []
    received = _publisher_frames()
    signals = []
    _listener, identity_reader, popen = _patch_publisher_operation_fakes(
        monkeypatch, now=now, process=process, received=received, sent=sent,
    )

    def callback(record):
        now[0] = 5.0

    def signal_group(pgid, sig):
        signals.append((pgid, sig))
        process.returncode = -sig

    with pytest.raises(runner.ObservationFailure, match='deadline'):
        runner.publish_review_result_bounded(
            '/tmp/request.json', verdict='PASS', reason='seen',
            request_deadline=20.0, steady=lambda: now[0],
            on_started=callback, signal_group=signal_group,
            identity_reader=identity_reader, popen=popen,
        )
    assert not sent
    assert signals == [(process.pid, signal.SIGTERM)]


def test_publisher_communicate_completion_after_deadline_fails(monkeypatch):
    """A late exit cannot become a successful publisher result."""
    now = [0.0]
    process = _PublisherFakeProcess(now=now)
    sent = []
    received = _publisher_frames()
    _listener, identity_reader, popen = _patch_publisher_operation_fakes(
        monkeypatch, now=now, process=process, received=received, sent=sent,
    )
    holder = {}

    def receive(_sock, **_kwargs):
        frame = next(received)
        if isinstance(frame, BaseException):
            raise frame
        if frame['event'] == 'READY_FOR_RELEASE':
            frame['pid'] = process.pid
            frame['nonce'] = holder['record']['nonce']
            frame['binding_sha256'] = holder['record']['binding_sha256']
            frame['deadline_monotonic_ns'] = (
                holder['record']['operation_deadline_monotonic_ns']
            )
        if frame['event'] == 'RELEASE_ACCEPTED':
            frame['nonce'] = sent[0]['nonce']
            frame['binding_sha256'] = sent[0]['binding_sha256']
        return frame

    monkeypatch.setattr(runner, '_socket_recv_frame', receive)
    with pytest.raises(runner.ObservationFailure, match='deadline'):
        runner.publish_review_result_bounded(
            '/tmp/request.json', verdict='PASS', reason='seen',
            request_deadline=20.0, steady=lambda: now[0],
            on_started=lambda record: holder.update(record=record),
            identity_reader=identity_reader, popen=popen,
        )
    assert process.returncode == 0
    assert [item['event'] for item in sent] == ['RELEASE', 'EXEC_COMMIT']


def test_framed_partial_read_recomputes_remaining_deadline():
    """A partial frame cannot restart the socket timeout per recv."""
    now = [0.0]
    wire = (4).to_bytes(4, 'big') + b'{"x":1}'

    class PartialSocket:
        def __init__(self):
            self.timeouts = []
            self.calls = 0

        def settimeout(self, value):
            self.timeouts.append(value)

        def recv(self, _size):
            self.calls += 1
            if self.calls == 1:
                now[0] = 4.95
                return wire[:1]
            now[0] = 5.0
            return wire[1:2]

    sock = PartialSocket()
    with pytest.raises(TimeoutError):
        runner._socket_recv_frame(sock, deadline=5.0, steady=lambda: now[0])
    assert sock.calls == 2
    assert sock.timeouts[0] == pytest.approx(5.0)
    assert sock.timeouts[1] == pytest.approx(0.05)


def test_publisher_operation_timeout_cleans_verified_identity_bounded(
        monkeypatch):
    """Timeout uses bounded verified signaling and reports unknown residue."""
    now = [0.0]
    process = _PublisherFakeProcess(
        now=now,
        communicate_error=subprocess.TimeoutExpired('publisher', 2.0),
    )
    sent = []
    received = _publisher_frames()
    signals = []
    _listener, identity_reader, popen = _patch_publisher_operation_fakes(
        monkeypatch, now=now, process=process, received=received, sent=sent,
    )
    holder = {}

    def receive(_sock, **_kwargs):
        frame = next(received)
        if isinstance(frame, BaseException):
            raise frame
        if frame['event'] == 'READY_FOR_RELEASE':
            frame['pid'] = process.pid
            frame['nonce'] = holder['record']['nonce']
            frame['binding_sha256'] = holder['record']['binding_sha256']
            frame['deadline_monotonic_ns'] = (
                holder['record']['operation_deadline_monotonic_ns']
            )
        if frame['event'] == 'RELEASE_ACCEPTED':
            frame['nonce'] = sent[0]['nonce']
            frame['binding_sha256'] = sent[0]['binding_sha256']
        return frame

    monkeypatch.setattr(runner, '_socket_recv_frame', receive)

    def signal_group(pgid, sig):
        signals.append((pgid, sig))

    with pytest.raises(runner.ObservationFailure, match='residue unknown'):
        runner.publish_review_result_bounded(
            '/tmp/request.json', verdict='PASS', reason='seen',
            request_deadline=20.0, steady=lambda: now[0],
            on_started=lambda record: holder.update(record=record),
            signal_group=signal_group,
            identity_reader=identity_reader, popen=popen,
        )
    assert signals == [
        (process.pid, signal.SIGTERM), (process.pid, signal.SIGKILL),
    ]
    assert process.wait_calls == [1.0, 1.0]
    assert now[0] == 2.0


def test_publisher_cleanup_escalates_to_sigkill_for_sigterm_resistant_native(
        tmp_path):
    """A harmless TERM-resistant Python target is killed and joined."""
    root = tmp_path / 'native-evidence'
    root.mkdir()
    request_path, request_bytes, request, _image = request_fixture(
        root, steady_ns=time.monotonic_ns(),
    )
    callback = runner.publisher_pre_release_evidence_callback(
        request_path, request_bytes, request, evidence_root=root,
    )
    started = []
    signals = []
    process = None

    def on_started(record):
        started.append(record)
        callback(record)

    def signal_group(pgid, sig):
        signals.append((pgid, sig))
        os.killpg(pgid, sig)

    target = _python_target(
        'import signal, time; signal.signal(signal.SIGTERM, signal.SIG_IGN); '
        'print("term-ignored", flush=True); time.sleep(30)'
    )
    try:
        with pytest.raises(runner.ObservationFailure,
                           match='TimeoutExpired'):
            runner.publish_review_result_bounded(
                request_path, verdict='PASS', reason='offline timeout test',
                request_deadline=time.monotonic() + 7.5,
                on_started=on_started, signal_group=signal_group,
                helper_command_factory=lambda _role, _planned: target,
            )
        assert len(started) == 1
        process = started[0]['process']
        assert signals == [
            (process.pid, signal.SIGTERM), (process.pid, signal.SIGKILL),
        ]
        assert process.returncode == -signal.SIGKILL
        artifact = Path(started[0]['evidence_artifact_path'])
        assert artifact.is_file()
        evidence = json.loads(artifact.read_text())
        assert evidence['process_identity'] == started[0]['identity']
        assert evidence['gate_nonce'] == started[0]['nonce']
        assert started[0]['evidence_before_release'] is True
        process.communicate(timeout=1)
    finally:
        if process is None and started:
            process = started[0]['process']
        if process is not None and process.poll() is None:
            original = started[0]['identity']
            current = runner.process_start_identity(process.pid)
            if current == original:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=2)
                process.communicate(timeout=1)


def test_publisher_cleanup_rechecks_identity_before_sigkill():
    """A reused identity is never signaled during escalation."""
    now = [0.0]
    process = _PublisherFakeProcess(now=now)
    baseline = {
        'pid': process.pid, 'process_group_id': process.pid,
        'session_id': process.pid, 'start_ticks': 91,
    }
    calls = []
    signals = []

    def identity_reader(pid):
        calls.append(pid)
        if len(calls) == 1:
            return baseline
        return {**baseline, 'start_ticks': 92}

    residue = runner._finalize_publisher_process(
        process, baseline, deadline=2.0, steady=lambda: now[0],
        identity_reader=identity_reader,
        signal_group=lambda pgid, sig: signals.append((pgid, sig)),
    )
    assert signals == [(process.pid, signal.SIGTERM)]
    assert now[0] == 1.0
    assert residue == (
        f'residue unknown: publisher identity changed pid={process.pid}'
    )
    assert process.returncode is None


def test_publisher_cleanup_clips_and_latches_short_review_budget(monkeypatch):
    """A short review remainder is not refreshed or reported as clean."""
    now = [0.0]
    process = _PublisherFakeProcess(now=now)
    sent = []
    received = _publisher_frames()
    _listener, identity_reader, popen = _patch_publisher_operation_fakes(
        monkeypatch, now=now, process=process, received=received, sent=sent,
    )
    records = []

    def callback(record):
        records.append(record)
        now[0] = 7.2

    def signal_group(pgid, sig):
        sent.append({'signal_pid': pgid, 'signal': sig})

    with pytest.raises(runner.ObservationFailure,
                       match='deadline.*residue unknown'):
        runner.publish_review_result_bounded(
            '/tmp/request.json', verdict='PASS', reason='short budget',
            request_deadline=7.5, steady=lambda: now[0],
            on_started=callback, signal_group=signal_group,
            identity_reader=identity_reader, popen=popen,
        )
    record = records[0]
    deadline = record['cleanup_deadline_monotonic_s']
    assert deadline == 7.5
    assert sent == [
        {'signal_pid': process.pid, 'signal': signal.SIGTERM},
        {'signal_pid': process.pid, 'signal': signal.SIGKILL},
    ]
    assert process.wait_calls == [pytest.approx(0.3)]
    assert now[0] == 7.5
    assert runner._publisher_cleanup_deadline(
        record, 20.0, lambda: now[0],
    ) == deadline
    residue = runner._finalize_publisher_process(
        process, record['identity'], deadline=deadline, steady=lambda: now[0],
        identity_reader=identity_reader,
        signal_group=lambda pgid, sig: sent.append(
            {'signal_pid': pgid, 'signal': sig}
        ),
    )
    assert residue == (
        f'residue unknown: publisher still alive pid={process.pid}'
    )
    assert len(sent) == 2


def test_default_publish_cli_writes_ownership_evidence_before_target(
        tmp_path, monkeypatch, capsys):
    """The CLI's default callback publishes binding before target release."""
    root = tmp_path / 'evidence'
    root.mkdir()
    request_path, _request_bytes, request, _image = request_fixture(
        root, steady_ns=time.monotonic_ns(),
    )
    monkeypatch.setattr(runner, 'EVIDENCE_ROOT', root)
    artifact = (
        root / 'review_mailbox' / 'results'
        / f"{request['review_request_id']}.publisher-ownership.json"
    )
    marker = tmp_path / 'publisher-target-ran'
    target = (
        'import json; from pathlib import Path; '
        f'artifact=Path({str(artifact)!r}); '
        'record=json.loads(artifact.read_text()); '
        'assert record["run_id"] == "B22_GUI_OBSERVATION_RUN007"; '
        f'Path({str(marker)!r}).write_text(record["gate_nonce"])'
    )
    bounded = runner.publish_review_result_bounded

    def default_cli_bounded(*args, **kwargs):
        assert callable(kwargs.get('on_started'))
        kwargs['helper_command_factory'] = (
            lambda _role, _planned: _python_target(target)
        )
        return bounded(*args, **kwargs)

    monkeypatch.setattr(runner, 'publish_review_result_bounded',
                        default_cli_bounded)
    runner.main([
        '--publish-review-result', str(request_path), '--verdict', 'PASS',
        '--reason', 'fake-only CLI binding check',
        '--viewer-ref-state', 'TOOL_NO_STABLE_REFERENCE',
    ])
    result = json.loads(capsys.readouterr().out)
    ownership = json.loads(artifact.read_text())
    assert marker.read_text() == ownership['gate_nonce']
    assert result['evidence_before_release'] is True
    assert result['evidence_artifact_path'] == str(artifact)
    assert result['evidence_artifact_sha256'] == hashlib.sha256(
        artifact.read_bytes()
    ).hexdigest()
    assert ownership['session_id'] == request['session_id']
    assert ownership['packet_sha256'] == request['packet_sha256']
    assert ownership['process_identity']['pid'] == result['worker_pid']


def test_default_publish_cli_evidence_failure_blocks_target_and_cleans(
        tmp_path, monkeypatch, capsys):
    """Default CLI evidence failure prevents release and cleans its helper."""
    root = tmp_path / 'evidence'
    root.mkdir()
    request_path, _request_bytes, request, _image = request_fixture(
        root, steady_ns=time.monotonic_ns(),
    )
    monkeypatch.setattr(runner, 'EVIDENCE_ROOT', root)
    artifact = (
        root / 'review_mailbox' / 'results'
        / f"{request['review_request_id']}.publisher-ownership.json"
    )
    marker = tmp_path / 'publisher-target-must-not-run'
    target = f'from pathlib import Path; Path({str(marker)!r}).touch()'
    real_atomic_publish = runner.atomic_publish

    def fail_ownership_write(path, data):
        if str(path).endswith('.publisher-ownership.json'):
            raise OSError('injected ownership evidence write failure')
        return real_atomic_publish(path, data)

    monkeypatch.setattr(runner, 'atomic_publish', fail_ownership_write)
    bounded = runner.publish_review_result_bounded
    captured = []

    def default_cli_bounded(*args, **kwargs):
        callback = kwargs['on_started']
        kwargs['on_started'] = lambda record: (
            captured.append(record), callback(record)
        )[-1]
        kwargs['helper_command_factory'] = (
            lambda _role, _planned: _python_target(target)
        )
        return bounded(*args, **kwargs)

    monkeypatch.setattr(runner, 'publish_review_result_bounded',
                        default_cli_bounded)
    with pytest.raises(SystemExit, match='injected ownership evidence write'):
        runner.main([
            '--publish-review-result', str(request_path), '--verdict', 'PASS',
            '--reason', 'fake-only evidence failure check',
            '--viewer-ref-state', 'TOOL_NO_STABLE_REFERENCE',
        ])
    assert captured and captured[0]['process'].returncode is not None
    assert not marker.exists()
    assert not artifact.exists()
    assert 'evidence' in capsys.readouterr().err.lower() or captured


def test_gated_helper_records_identity_before_immediate_target_exec(tmp_path):
    """A zero-duration target cannot race away before ownership is stored."""
    marker = tmp_path / 'executed'
    observations = []

    def on_start(record, identity):
        observations.append((record.pid, identity, marker.exists()))

    launcher = _native_helper_launcher(on_start=on_start)
    command = _python_target(
        'from pathlib import Path; import sys; '
        f'Path({str(marker)!r}).write_text("ran"); '
        'sys.stdout.write("fast-out"); sys.stderr.write("fast-err")'
    )

    async def run():
        process = await launcher.start_gated(
            command, os.environ.copy(), role='window_helper',
            deadline=time.monotonic() + 5,
        )
        stdout, stderr = await process.communicate()
        return process, stdout, stderr
    process, stdout, stderr = asyncio.run(run())
    assert process.returncode == 0
    assert stdout == b'fast-out'
    assert stderr == b'fast-err'
    assert marker.read_text() == 'ran'
    assert len(observations) == 1
    assert observations[0][0] == process.pid
    assert observations[0][1]['pid'] == process.pid
    assert observations[0][2] is False
    record = next(item for item in launcher.records if item.process is process)
    assert record.gate_released is True
    assert record.command == command
    assert record.wrapper_command != command


def test_gated_window_capture_and_publisher_use_default_owned_gate(tmp_path):
    """All short helper entry paths retain the real two-phase gate."""
    events = []

    def on_start(record, identity):
        events.append((record.name, record.pid, identity, record.gate))

    launcher = _native_helper_launcher(on_start=on_start)
    environment = os.environ.copy()
    deadline = time.monotonic() + 8
    png = (b'\x89PNG\r\n\x1a\n' + b'\x00\x00\x00\rIHDR'
           + (2).to_bytes(4, 'big') + (1).to_bytes(4, 'big') + b'fixture')

    async def run_entries():
        window_output = await runner._owned_helper(
            launcher, _python_target('print("window-result", end="")'),
            environment, deadline=deadline, sink=None,
        )
        capture_result = await runner.capture_x11_window_bounded(
            '0x1', launcher=launcher, environment=environment,
            deadline=deadline,
            helper_command_factory=lambda _role, _planned: _python_target(
                'import sys; sys.stdout.buffer.write(bytes.fromhex('
                + repr(png.hex()) + '))'
            ),
        )
        return window_output, capture_result
    window_output, capture = asyncio.run(run_entries())
    assert window_output == 'window-result'
    assert capture['png_bytes'] == png

    publish_result = runner.publish_review_result_bounded(
        tmp_path / 'unused-request.json', verdict='PASS', reason='fake pixels',
        request_deadline=time.monotonic() + 8,
        on_started=lambda record: events.append((
            'publisher', record['process'].pid,
            record['identity'], record['wrapper_command'],
        )),
        helper_command_factory=lambda _role, _planned: _python_target(
            'print("publisher-result", end="")'
        ),
    )
    assert publish_result['exit_status'] == 0
    assert publish_result['stdout'] == 'publisher-result'
    assert (publish_result['planned_command']
            != publish_result['wrapper_command'])
    assert {event[0] for event in events} >= {
        'window_helper', 'capture_helper', 'publisher',
    }
    assert all(event[2]['pid'] == event[1] for event in events)


def test_gated_evidence_failure_closes_before_target_release(tmp_path):
    """The pre-release evidence callback is fail-closed and handle-owned."""
    marker = tmp_path / 'must-not-execute'
    launcher = _native_helper_launcher(
        on_start=lambda _record, _identity: (_ for _ in ()).throw(
            RuntimeError('injected evidence failure')
        ),
    )
    command = _python_target(
        f'from pathlib import Path; Path({str(marker)!r}).touch()'
    )

    async def run():
        with pytest.raises(RuntimeError, match='injected evidence failure'):
            await launcher.start_gated(
                command, os.environ.copy(), role='capture_helper',
                deadline=time.monotonic() + 5,
            )
        assert len(launcher.records) == 1
        process = launcher.records[0].process
        await asyncio.wait_for(process.wait(), timeout=3)
        assert process.returncode != 0
    asyncio.run(run())
    assert not marker.exists()


def test_gated_helper_nonzero_target_preserves_stdio_and_fails():
    """After release, target exit status and independent streams are kept."""
    launcher = _native_helper_launcher()

    async def run():
        process = await launcher.start_gated(
            _python_target(
                'import sys; print("stdout-fact"); '
                'print("stderr-fact", file=sys.stderr); sys.exit(7)'
            ),
            os.environ.copy(), role='window_helper',
            deadline=time.monotonic() + 5,
        )
        stdout, stderr = await process.communicate()
        return process, stdout, stderr
    process, stdout, stderr = asyncio.run(run())
    assert process.returncode == 7
    assert stdout == b'stdout-fact\n'
    assert stderr == b'stderr-fact\n'
    launcher = _native_helper_launcher()

    async def fail_contract():
        with pytest.raises(runner.ObservationFailure,
                           match='stderr-contract'):
            await runner._owned_helper(
                launcher,
                _python_target(
                    'import sys; print("stderr-contract", '
                    'file=sys.stderr); sys.exit(9)'
                ),
                os.environ.copy(), deadline=time.monotonic() + 5,
                sink=None,
            )
    asyncio.run(fail_contract())


@pytest.mark.parametrize('payload,expected,truncated', [
    (b'', '', False),
    (b'bad\xff\x1b', 'bad\ufffd\\x1b', False),
    (b'x' * 513, 'x' * 512, True),
])
def test_owned_helper_bounded_stderr(payload, expected, truncated):
    """Nonzero helpers retain bounded, safe stderr and their identity."""
    launcher = _native_helper_launcher()

    async def run():
        with pytest.raises(runner.ObservationFailure) as caught:
            await runner._owned_helper(
                launcher,
                _python_target(
                    f'import sys; sys.stdout.write("stdout-only"); '
                    f'sys.stderr.buffer.write({payload!r}); sys.exit(9)'
                ),
                os.environ.copy(), deadline=time.monotonic() + 5,
                sink=None, role='window_helper',
            )
        return str(caught.value)

    message = asyncio.run(run())
    assert 'window_helper' in message and 'exit status 9' in message
    assert expected in message
    assert ('[truncated]' in message) is truncated
    assert 'stdout-only' not in message
    assert '\x1b' not in message


def test_gated_identity_mismatch_keeps_handle_and_never_executes(tmp_path):
    """Identity mismatch leaves the wrapper owned but never releases target."""
    marker = tmp_path / 'identity-mismatch-target-ran'

    def mismatch(_pid):
        return {'pid': 1, 'process_group_id': 1,
                'session_id': 1, 'start_ticks': 1}
    launcher = _native_helper_launcher()
    launcher.identity_reader = mismatch
    command = _python_target(
        f'from pathlib import Path; Path({str(marker)!r}).touch()'
    )

    async def run():
        with pytest.raises(runner.ObservationFailure,
                           match='owned session leader'):
            await launcher.start_gated(
                command, os.environ.copy(), role='publisher',
                deadline=time.monotonic() + 5,
            )
        assert len(launcher.records) == 1
        record = launcher.records[0]
        assert record.process is not None and record.identity is None
        await asyncio.wait_for(record.process.wait(), timeout=3)
        assert record.process.returncode != 0
    asyncio.run(run())
    assert not marker.exists()


def test_gated_cancellation_before_release_retains_and_joins_wrapper(tmp_path):
    """Cancellation closes the gate; no target executes and handle is kept."""
    marker = tmp_path / 'cancelled-before-release'
    callback_seen = asyncio.Event()
    loop_holder = []

    def on_start(_record, _identity):
        loop_holder[0].call_soon(callback_seen.set)
    launcher = _native_helper_launcher(on_start=on_start)
    command = _python_target(
        f'from pathlib import Path; Path({str(marker)!r}).touch()'
    )

    async def run():
        loop_holder.append(asyncio.get_running_loop())
        task = asyncio.create_task(launcher.start_gated(
            command, os.environ.copy(), role='capture_helper',
            deadline=time.monotonic() + 5,
        ))
        await asyncio.wait_for(callback_seen.wait(), timeout=2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert len(launcher.records) == 1
        process = launcher.records[0].process
        await asyncio.wait_for(process.wait(), timeout=3)
        assert process.returncode != 0
    asyncio.run(run())
    assert not marker.exists()


def test_parent_disconnect_after_release_before_exec_commit_fails_closed(
        tmp_path):
    """RELEASE alone cannot authorize target exec if parent disappears."""
    marker = tmp_path / 'parent-disconnect-target-ran'
    gate_dir = tmp_path / 'manual-gate'
    gate_dir.mkdir(mode=0o700)
    socket_path = str(gate_dir / 'control.sock')
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    listener.bind(socket_path)
    listener.listen(1)
    deadline_ns = time.monotonic_ns() + 5_000_000_000
    nonce = uuid.uuid4().hex
    command = _python_target(
        f'from pathlib import Path; Path({str(marker)!r}).touch()'
    )
    wrapper, _binding, binding_hash = runner._gated_wrapper_argv(
        'window_helper', command, socket_path, nonce, deadline_ns,
    )
    process = subprocess.Popen(
        wrapper, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, start_new_session=True,
    )
    try:
        control, _ = listener.accept()
        control.settimeout(3)
        hello = runner._socket_recv_frame(control)
        assert hello == {
            'schema_id': runner.GATED_HELPER_SCHEMA,
            'event': 'READY_FOR_RELEASE', 'pid': process.pid,
            'nonce': nonce, 'binding_sha256': binding_hash,
            'deadline_monotonic_ns': deadline_ns,
        }
        runner._socket_send_frame(control, {
            'schema_id': runner.GATED_HELPER_SCHEMA, 'event': 'RELEASE',
            'nonce': nonce, 'binding_sha256': binding_hash,
            'deadline_monotonic_ns': deadline_ns,
        })
        assert runner._socket_recv_frame(control) == {
            'schema_id': runner.GATED_HELPER_SCHEMA,
            'event': 'RELEASE_ACCEPTED', 'nonce': nonce,
            'binding_sha256': binding_hash,
        }
        # Simulate parent loss before the second, final authorization frame.
        control.close()
        stdout, stderr = process.communicate(timeout=3)
        assert process.returncode == 125
        assert not marker.exists()
        assert stdout == b''
        assert stderr == b''
    finally:
        listener.close()
        if process.poll() is None:
            process.kill()
            process.wait(timeout=2)
        if os.path.exists(socket_path):
            os.unlink(socket_path)
        gate_dir.rmdir()


def test_gated_target_can_be_stopped_after_release_by_verified_identity(
        tmp_path):
    """Post-release cancellation path retains then joins the exact helper."""
    marker = tmp_path / 'released-target'
    launcher = _native_helper_launcher()
    command = _python_target(
        f'from pathlib import Path; import time; '
        f'Path({str(marker)!r}).touch(); '
        'print("TARGET_READY", flush=True); time.sleep(30)'
    )

    async def run():
        process = await launcher.start_gated(
            command, os.environ.copy(), role='capture_helper',
            deadline=time.monotonic() + 5,
        )
        record = next(item for item in launcher.records
                      if item.process is process)
        assert record.gate_released is True
        assert await asyncio.wait_for(
            process.stdout.readline(), timeout=2,
        ) == b'TARGET_READY\n'
        identity = launcher.identity_reader(process.pid)
        assert identity == record.identity
        os.killpg(record.identity['process_group_id'], signal.SIGTERM)
        await asyncio.wait_for(process.wait(), timeout=3)
        await process.communicate()
        assert process.returncode != 0
    asyncio.run(run())
    assert marker.exists()
