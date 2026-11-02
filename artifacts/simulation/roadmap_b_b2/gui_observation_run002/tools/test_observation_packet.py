"""RUN002 guard, mailbox, observer, and orchestration regressions."""
from __future__ import annotations

import asyncio
import hashlib
import importlib
import json
import signal
import sys
import uuid
from dataclasses import make_dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest
HERE = Path(__file__).resolve().parent
BUNDLE = HERE.parent
PACKET = BUNDLE / 'packet.json'
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
guard = importlib.import_module('observation_guard')
runner = importlib.import_module('observation_runner')
sink = importlib.import_module('observation_sink')


def bundle_packet():
    """Test helper for RUN002 offline behavior."""
    return json.loads(PACKET.read_text(encoding='utf-8'))


def tools_hashes():
    """Test helper for RUN002 offline behavior."""
    return guard.tool_hashes(runner.TOOL_PATHS)


def test_actual_bundle_packet_validates_complete_run002_schema():
    """Test helper for RUN002 offline behavior."""
    packet = bundle_packet()
    bindings = guard.packet_bindings(packet, tools_hashes())
    assert packet['run_id'] == guard.RUN_ID
    assert packet['runtime_authorization'] == 'NOT_GRANTED'
    assert (
        packet['repository']['remote_status_at_executor']
        == 'REMOTE_UNVERIFIED_AT_EXECUTOR'
    )
    assert len(bindings['file_sha256']) == 47
    assert bindings['production_source_pin'] == guard.PRODUCTION_SOURCE_PIN
    assert packet['timing']['review_checkpoint_s'] == 60
    assert packet['acceptance']['owner_visual_review'] == 'NOT_PERFORMED'


def test_packet_missing_field_rejects_before_any_acquisition(tmp_path):
    """Test helper for RUN002 offline behavior."""
    packet = bundle_packet()
    del packet['composition']
    with pytest.raises(guard.GuardError, match='canonical schema'):
        guard.packet_bindings(packet, tools_hashes())
    assert list(tmp_path.iterdir()) == []


def test_packet_wrong_source_pin_or_alternate_schema_rejects():
    """Test helper for RUN002 offline behavior."""
    packet = bundle_packet()
    packet['repository']['production_source_pin'] = '0' * 40
    with pytest.raises(guard.GuardError, match='repository pins'):
        guard.packet_bindings(packet, tools_hashes())
    packet = bundle_packet()
    packet['production_source_pin'] = guard.PRODUCTION_SOURCE_PIN
    with pytest.raises(guard.GuardError, match='canonical schema'):
        guard.packet_bindings(packet, tools_hashes())


def test_packet_rejects_changed_tool_hash_and_input_pin():
    """Test helper for RUN002 offline behavior."""
    packet = bundle_packet()
    wrong = dict(tools_hashes())
    wrong['observation_runner.py'] = '0' * 64
    with pytest.raises(guard.GuardError, match='tool hashes'):
        guard.packet_bindings(packet, wrong)
    packet = bundle_packet()
    packet['inputs']['config_hash'] = '0' * 64
    with pytest.raises(guard.GuardError, match='input pins'):
        guard.packet_bindings(packet, tools_hashes())


def test_packet_coordinator_id_contract_is_typed_uint64_policy():
    """Test helper for RUN002 offline behavior."""
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
    """Test helper for RUN002 offline behavior."""
    for raw in (b'{"x":1,"x":2}', b'{"x":NaN}', b'{} {}'):
        with pytest.raises(guard.GuardError):
            guard.strict_json_loads(raw)


def test_gui_parser_is_strict_and_run002_rejects_false_before_side_effect():
    """Test helper for RUN002 offline behavior."""
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
    """Test helper for RUN002 offline behavior."""
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
    """Test helper for RUN002 offline behavior."""
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
    """Test helper for RUN002 offline behavior."""
    path = tmp_path / 'acquisition.json'
    outcomes = []
    import concurrent.futures

    def acquire(index):
        """Test helper for RUN002 offline behavior."""
        try:
            guard.acquire_once(path, {'run_id': 'RUN002_TEST',
                                      'contender': index})
            return 'won'
        except guard.GuardError:
            return 'lost'
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        outcomes.extend(pool.map(acquire, (1, 2)))
    assert sorted(outcomes) == ['lost', 'won']
    before = path.read_bytes()
    with pytest.raises(guard.GuardError, match='already exists'):
        guard.acquire_once(path, {'run_id': 'RUN002_TEST', 'contender': 3})
    assert path.read_bytes() == before


def test_partial_acquisition_is_never_repaired_or_reused(tmp_path):
    """Test helper for RUN002 offline behavior."""
    path = tmp_path / 'acquisition.json'
    path.write_bytes(b'{partial')
    with pytest.raises(guard.GuardError, match='already exists'):
        guard.acquire_once(path, {'run_id': 'RUN002_TEST'})
    assert path.read_bytes() == b'{partial'


def request_fixture(root, *, packet_hash='a' * 64, session_id=None):
    """Test helper for RUN002 offline behavior."""
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
    now_ns = 1000000000
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
    """Test helper for RUN002 offline behavior."""
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
    """Test helper for RUN002 offline behavior."""
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
    """Test helper for RUN002 offline behavior."""
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
    """Test helper for RUN002 offline behavior."""
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
    """Test helper for RUN002 offline behavior."""
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
    """Test helper for RUN002 offline behavior."""
    request_path, _, request, _ = request_fixture(tmp_path)
    Path(request['screenshot_path']).write_bytes(b'changed bytes')
    with pytest.raises(runner.ObservationFailure, match='hash changed'):
        runner.publish_review_result_worker(request_path, verdict='PASS',
                                            reason='scene visible',
                                            root=tmp_path)


def test_atomic_publication_no_overwrite_and_symlink_component(tmp_path):
    """Test helper for RUN002 offline behavior."""
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
    """Test helper for RUN002 offline behavior."""
    _, request_bytes, request, _ = request_fixture(tmp_path)
    clock = [0.0]

    async def tick(delay):
        """Test helper for RUN002 offline behavior."""
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
    """Test helper for RUN002 offline behavior."""
    _, request_bytes, request, _ = request_fixture(tmp_path)
    stop = SimpleNamespace(is_set=lambda: True)
    with pytest.raises(runner.ReviewInvalidated, match='invalidated'):
        asyncio.run(runner.await_codex_review(
            request_path=Path(request['result_path']),
            request_bytes=request_bytes, request=request, deadline=10,
            steady=lambda: 0, sink=None, stop_event=stop,
        ))


def test_bounded_publisher_requires_budget_and_uses_injected_process():
    """Test helper for RUN002 offline behavior."""
    calls = []

    class FakePopen:
        pid = 321
        returncode = 0

        def __init__(self, *args, **kwargs):
            """Test helper for RUN002 offline behavior."""
            calls.append((args, kwargs))

        def communicate(self, timeout):
            """Test helper for RUN002 offline behavior."""
            assert timeout <= 5
            return (b'ok', b'')

        def poll(self):
            """Test helper for RUN002 offline behavior."""
            return self.returncode
    identity = {'pid': 321, 'process_group_id': 321, 'session_id': 321,
                'start_ticks': 4}
    with pytest.raises(runner.ReviewInvalidated, match='7 seconds'):
        runner.publish_review_result_bounded(
            '/tmp/request.json', verdict='PASS', reason='visible',
            request_deadline=6, steady=lambda: 0, popen=FakePopen,
            identity_reader=lambda _pid: identity,
        )
    assert calls == []
    result = runner.publish_review_result_bounded(
        '/tmp/request.json', verdict='PASS', reason='visible',
        request_deadline=7, steady=lambda: 0, popen=FakePopen,
        identity_reader=lambda _pid: identity,
    )
    assert result['exit_status'] == 0
    assert len(calls) == 1


def test_publisher_timeout_escalates_only_injected_owned_group(monkeypatch):
    """Test helper for RUN002 offline behavior."""
    signals = []

    class FakePopen:
        pid = 456
        returncode = None

        def __init__(self, *args, **kwargs):
            """Test helper for RUN002 offline behavior."""
            pass

        def communicate(self, timeout):
            """Test helper for RUN002 offline behavior."""
            raise runner.subprocess.TimeoutExpired('writer', timeout)

        def wait(self, timeout):
            """Test helper for RUN002 offline behavior."""
            if signals and signals[-1] == signal.SIGKILL:
                self.returncode = -signal.SIGKILL
            return self.returncode

        def poll(self):
            """Test helper for RUN002 offline behavior."""
            return self.returncode
    monkeypatch.setattr(runner.os, 'killpg', lambda pgid,
                        sig: signals.append(sig))
    identity = {'pid': 456, 'process_group_id': 456, 'session_id': 456,
                'start_ticks': 88}
    with pytest.raises(runner.ObservationFailure, match='timed out'):
        runner.publish_review_result_bounded(
            '/tmp/request.json', verdict='PASS', reason='visible',
            request_deadline=7, steady=lambda: 0, popen=FakePopen,
            identity_reader=lambda _pid: identity,
        )
    assert signals == [signal.SIGTERM, signal.SIGKILL]


def test_publisher_identity_uncertainty_does_not_signal(monkeypatch):
    """Test helper for RUN002 offline behavior."""
    signals = []

    class FakePopen:
        pid = 457
        returncode = 0

        def __init__(self, *args, **kwargs):
            """Test helper for RUN002 offline behavior."""
            pass

        def communicate(self, timeout):
            """Test helper for RUN002 offline behavior."""
            return (b'', b'')

        def poll(self):
            """Test helper for RUN002 offline behavior."""
            return 0
    monkeypatch.setattr(runner.os, 'killpg',
                        lambda *args: signals.append(args))
    with pytest.raises(runner.ObservationFailure, match='ownership'):
        runner.publish_review_result_bounded('/tmp/request.json',
                                             verdict='PASS',
                                             reason='visible',
                                             request_deadline=7,
                                             steady=lambda: 0,
                                             popen=FakePopen,
                                             identity_reader=lambda _pid: {
                                                 'pid': 1})
    assert signals == []


def test_observer_uses_its_own_context_executor_and_private_spin():
    """Test helper for RUN002 offline behavior."""
    calls = []

    class Context:

        def __init__(self):
            """Test helper for RUN002 offline behavior."""
            calls.append(('context', self))

    class Executor:

        def __init__(self, *, context):
            """Test helper for RUN002 offline behavior."""
            self.context = context
            calls.append(('executor', context))

        def add_node(self, node):
            """Test helper for RUN002 offline behavior."""
            calls.append(('add', node.context))
            return True

        def spin_once(self, timeout_sec):
            """Test helper for RUN002 offline behavior."""
            calls.append(('spin', timeout_sec))

        def remove_node(self, node):
            """Test helper for RUN002 offline behavior."""
            calls.append(('remove', node.context))

        def shutdown(self, timeout_sec):
            """Test helper for RUN002 offline behavior."""
            calls.append(('executor_shutdown', timeout_sec))
            return True

    class Node:

        def __init__(self, name, *, context):
            """Test helper for RUN002 offline behavior."""
            self.context = context
            calls.append(('node', name, context))

        def create_subscription(self, *args):
            """Test helper for RUN002 offline behavior."""
            calls.append(('subscription', args[1], args[3]))
            return object()

        def destroy_node(self):
            """Test helper for RUN002 offline behavior."""
            calls.append(('destroy_node', self.context))

        def get_node_names_and_namespaces(self):
            """Test helper for RUN002 offline behavior."""
            return []

    class Rclpy:

        def init(self, *, context, domain_id):
            """Test helper for RUN002 offline behavior."""
            calls.append(('init', context, domain_id))

        def ok(self, *, context):
            """Test helper for RUN002 offline behavior."""
            return True

        def shutdown(self, *, context):
            """Test helper for RUN002 offline behavior."""
            calls.append(('context_shutdown', context))

        def spin_once(self, *_args, **_kwargs):
            """Test helper for RUN002 offline behavior."""
            raise AssertionError('global spin forbidden')

    class QoS:

        def __init__(self, **kwargs):
            """Test helper for RUN002 offline behavior."""
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
    """Test helper for RUN002 offline behavior."""
    calls = []

    class Context:

        def __init__(self):
            """Test helper for RUN002 offline behavior."""
            calls.append('context')

    class Executor:

        def __init__(self, *, context):
            """Test helper for RUN002 offline behavior."""
            self.context = context
            calls.append('executor')

        def add_node(self, node):
            """Test helper for RUN002 offline behavior."""
            return True

        def remove_node(self, node):
            """Test helper for RUN002 offline behavior."""
            calls.append('remove')

        def shutdown(self, timeout_sec):
            """Test helper for RUN002 offline behavior."""
            calls.append('executor_shutdown')
            raise RuntimeError('injected')

    class Node:

        def __init__(self, name, *, context):
            """Test helper for RUN002 offline behavior."""
            self.context = context
            calls.append('node')

        def create_subscription(self, *args):
            """Test helper for RUN002 offline behavior."""
            return object()

        def destroy_node(self):
            """Test helper for RUN002 offline behavior."""
            calls.append('destroy_node')

    class Rclpy:

        def init(self, *, context, domain_id):
            """Test helper for RUN002 offline behavior."""
            calls.append('init')

        def ok(self, *, context):
            """Test helper for RUN002 offline behavior."""
            return True

        def shutdown(self, *, context):
            """Test helper for RUN002 offline behavior."""
            calls.append('context_shutdown')

    class QoS:

        def __init__(self, **kwargs):
            """Test helper for RUN002 offline behavior."""
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
    """Test helper for RUN002 offline behavior."""

    class FakeObserver:

        def __init__(self):
            """Test helper for RUN002 offline behavior."""
            self.events = deque()
            self.samples = 0

        def spin_once(self, _timeout):
            """Test helper for RUN002 offline behavior."""
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
            """Test helper for RUN002 offline behavior."""
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


def test_review_result_write_failure_cannot_be_passed_by_waiter(tmp_path):
    """Test helper for RUN002 offline behavior."""
    _, request_bytes, request, _ = request_fixture(tmp_path)

    def fail_read(_path, **_kwargs):
        """Test helper for RUN002 offline behavior."""
        raise OSError('evidence read failed')
    with pytest.raises(OSError):
        asyncio.run(runner.await_codex_review(
            request_path=Path(request['result_path']),
            request_bytes=request_bytes, request=request, deadline=1,
            steady=lambda: 0, sink=None, read_file=fail_read))


def test_production_cli_has_no_root_or_owner_input_override():
    """Test helper for RUN002 offline behavior."""
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
    """Test helper for RUN002 offline behavior."""
    source = Path(runner.__file__).read_text(encoding='utf-8')
    for forbidden in ('OWNER_ACK_SCENE', 'OWNER_ABORT_GUI',
                      'create_publisher(', 'create_client(', 'world_control',
                      'set_pose', 'rearm'):
        assert forbidden not in source


def test_review_deadline_is_absolute_and_duplicate_read_does_not_refresh(
        tmp_path):
    """Test helper for RUN002 offline behavior."""
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
        """Test helper for RUN002 offline behavior."""
        accepted = await runner.await_codex_review(
            request_path=Path(request['result_path']),
            request_bytes=request_bytes, request=request, deadline=10,
            steady=lambda: 0, sink=None,
            monotonic_ns=lambda: request['request_created_steady_ns'] + 1)
        seen.append(accepted)
    asyncio.run(observe())
    assert request['review_deadline_steady_ns'] == initial_deadline
    assert len(seen) == 1


def make_runner_inputs(tmp_path, *, startup_failure=False):
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
    }
    png = (b'\x89PNG\r\n\x1a\n' + b'\x00\x00\x00\rIHDR'
           + (2).to_bytes(4, 'big') + (1).to_bytes(4, 'big') + b'fixture')

    class FakeProcess:

        def __init__(self, pid, command):
            """Test helper for RUN002 offline behavior."""
            self.pid = pid
            self.command = tuple(command)
            self.returncode = None
            self.event = asyncio.Event()

        async def wait(self):
            """Test helper for RUN002 offline behavior."""
            await self.event.wait()
            return self.returncode

        async def communicate(self):
            """Test helper for RUN002 offline behavior."""
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
            """Test helper for RUN002 offline behavior."""
            self.returncode = status
            self.event.set()

    class FakeLauncher:

        async def start(self, command, environment):
            """Test helper for RUN002 offline behavior."""
            counter[0] += 1
            proc = FakeProcess(counter[0], command)
            processes.append((tuple(command), proc))
            events.append(('spawn', runner._process_label(command)))
            return proc

    class FakeReadiness:

        def bind_environment(self, environment):
            """Test helper for RUN002 offline behavior."""
            events.append(('bind_env', dict(environment)))

        async def server_scene(self, plan, process, timeout_s):
            """Test helper for RUN002 offline behavior."""
            events.append(('scene_ready', timeout_s))

        async def gui_process_started(self, plan, process, timeout_s):
            """Test helper for RUN002 offline behavior."""
            events.append(('gui_ready', timeout_s))

    class FakeSupervisor:

        def __init__(self, *, plan, launcher, readiness, evidence_sink):
            """Test helper for RUN002 offline behavior."""
            self.plan = plan
            self.launcher = launcher
            self.readiness = readiness
            self.owned = []

        async def start(self):
            """Test helper for RUN002 offline behavior."""
            if startup_failure:
                process = await self.launcher.start(self.plan.commands[0],
                                                    self.plan.environment)
                self.owned.append(SimpleNamespace(name='server',
                                                  process=process,
                                                  output_tasks=[]))
                raise RuntimeError('injected partial startup')
            roles = {}
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
            """Test helper for RUN002 offline behavior."""
            events.append(('cleanup',))
            for _command, process in processes:
                process.finish()

    class FakeObserver:

        def __init__(self):
            """Test helper for RUN002 offline behavior."""
            self.closed = 0

        def start(self):
            """Test helper for RUN002 offline behavior."""
            events.append(('observer_start',))

        def close(self, **_kwargs):
            """Test helper for RUN002 offline behavior."""
            self.closed += 1
            events.append(('observer_close',))
    observer = FakeObserver()
    template = packet['commands_argv']['exact_templates']
    holder = {}

    def build_plan(gui, temp_dir):
        """Test helper for RUN002 offline behavior."""
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
                ('world_file', Path),
                ('commands', tuple),
                ('bridge_command', tuple),
                ('environment', dict),
            ],
        )
        plan = FakePlan(
            True, session, 17, packet['inputs']['config_hash'],
            packet['inputs']['manifest_sha256'], world,
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
        """Test helper for RUN002 offline behavior."""
        await ack_event.wait()
        return {'backend_identity': ['session', 'config', 'backend', 'world'],
                'last_status_sequence': 3, 'backend_status_samples': 3,
                'clock_samples': 3, 'clock_stamp': [0, 0],
                'observed_seconds': 60}

    async def bind_window(**_kwargs):
        """Test helper for RUN002 offline behavior."""
        return {'evidence_sequence': 9, 'window_id': '0x123', 'pid': 900010,
                'pgid': 900010, 'process_start_ticks': 31,
                'gz_partition': holder['plan'].environment['GZ_PARTITION'],
                'executable': '/usr/bin/gz', 'argv': ['/usr/bin/gz', 'sim'],
                'gui_process_identity': {'pid': 900010}}

    async def review_waiter(*, request, request_bytes, **_kwargs):
        """Test helper for RUN002 offline behavior."""
        state['request'] = request
        result = runner._review_result_bytes(
            request_bytes, request, verdict='PASS',
            reason='fake visual review in test only')
        runner.atomic_publish(Path(request['result_path']), result)
        return {'verdict': 'PASS', 'reason': 'test fake review only',
                'viewer_ref_state': 'TOOL_NO_STABLE_REFERENCE'}

    def identity_reader(pid):
        return {
            'pid': pid,
            'process_group_id': pid,
            'session_id': pid,
            'start_ticks': 1,
        }
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
                    'readiness': FakeReadiness(),
                    'supervisor_factory': FakeSupervisor,
                    'observer_factory': lambda: observer,
                    'evaluate_observation': evaluate,
                    'bind_gui_window': bind_window,
                    'await_review': review_waiter,
                    'cleanup_escalation_grace': (0, 0, 0)}
    dependencies.update(_host_dependency_fakes(packet))
    return (SimpleNamespace(gui=True, approved_commit=commit), dependencies,
            events, processes, root, observer, state)


def _host_dependency_fakes(packet):
    """Inject pinned host metadata without importing Qt or middleware."""
    fingerprints = packet['installation']['dependency_fingerprints']
    qt = fingerprints['qt']
    desktop = fingerprints['desktop_tools']
    python = fingerprints['python']
    modules = {
        'PyQt5': SimpleNamespace(__file__=qt['PyQt5_origin']),
        'PyQt5.QtCore': SimpleNamespace(
            __file__=qt['QtCore_origin'],
            PYQT_VERSION_STR=qt['PyQt5_version'],
            qVersion=lambda: qt['Qt_version'],
        ),
        'PyQt5.QtGui': SimpleNamespace(__file__=qt['QtGui_origin']),
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
    """Test helper for RUN002 offline behavior."""
    args, deps, events, processes, root, observer, state = \
        make_runner_inputs(tmp_path)
    verdict = asyncio.run(runner._run(args, dependencies=deps))
    assert verdict == 'PASS'
    assert [runner._process_label(command)
            for command, _proc in processes] == [
        'robot_state_publisher', 'parameter_bridge', 'server', 'gui',
        'capture_helper',
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
    """Test helper for RUN002 offline behavior."""
    args, deps, events, processes, root, observer, _state = \
        make_runner_inputs(tmp_path, startup_failure=True)
    verdict = asyncio.run(runner._run(args, dependencies=deps))
    assert verdict == 'FAIL'
    assert len(processes) == 2
    assert ('cleanup',) in events
    assert observer.closed == 1
    result = json.loads((root / 'final_result.json').read_text())
    assert result['status'] == 'FAIL'


def test_codex_result_and_owner_review_labels_are_distinct_in_source():
    """Test helper for RUN002 offline behavior."""
    source = Path(runner.__file__).read_text(encoding='utf-8')
    assert 'automated_observation_verdict' in source
    assert 'owner_visual_review' in source
    assert 'OWNER_ACK_SCENE' not in source and 'OWNER_ABORT_GUI' not in source
    assert 'create_publisher(' not in source and 'create_client(' not in source


def test_window_binding_matches_unique_owned_process_and_partition():
    """Test helper for RUN002 offline behavior."""

    class FakeProcess:

        def __init__(self, pid, stdout):
            """Test helper for RUN002 offline behavior."""
            self.pid = pid
            self.stdout = stdout

        async def communicate(self):
            """Test helper for RUN002 offline behavior."""
            return (self.stdout, b'')

        async def wait(self):
            """Test helper for RUN002 offline behavior."""
            return 0

    class FakeLauncher:

        def __init__(self, tree, props):
            """Test helper for RUN002 offline behavior."""
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

        async def start(self, command, _environment):
            """Test helper for RUN002 offline behavior."""
            output = (self.tree if command[0] == '/usr/bin/xwininfo'
                      else self.props)
            process = FakeProcess(
                202 if command[0].endswith('xwininfo') else 203, output)
            self.records.append(SimpleNamespace(name='window_helper',
                                                pid=process.pid,
                                                process=process,
                                                identity={'pid': process.pid},
                                                command=tuple(command)))
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
    'partition,tree,expected_error',
    [('foreign', b'  0x000010 "Gazebo"\n', 'partition differs'),
     ('mecanum_b2_test', b'  0x000010 "Gazebo"\n'
      b'    0x000011 "Gazebo child"\n', 'exactly one')],
    ids=[
        'foreign-  0x000010 "Gazebo"\n',
        'mecanum_b2_test-  0x000010 "Gazebo"\n  '
        '0x000011 "Gazebo"\n',
    ],
)
def test_window_binding_rejects_partition_mismatch_or_ambiguity(
        partition, tree, expected_error):
    """Test helper for RUN002 offline behavior."""

    class FakeProcess:

        def __init__(self, pid, output):
            """Test helper for RUN002 offline behavior."""
            self.pid = pid
            self.output = output

        async def communicate(self):
            """Test helper for RUN002 offline behavior."""
            return (self.output, b'')

        async def wait(self):
            """Test helper for RUN002 offline behavior."""
            return 0

    class FakeLauncher:

        def __init__(self):
            """Test helper for RUN002 offline behavior."""
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

        async def start(self, command, _env):
            """Test helper for RUN002 offline behavior."""
            out = (tree if command[0].endswith('xwininfo') else
                   b'_NET_WM_PID(CARDINAL) = 101\n'
                   b'WM_CLASS(STRING) = "gz", "Gazebo"\n')
            proc = FakeProcess(202, out)
            self.records.append(SimpleNamespace(name='window_helper', pid=202,
                                                process=proc,
                                                identity={'pid': 202},
                                                command=tuple(command)))
            return proc
    identity = {'pid': 101, 'process_group_id': 101, 'session_id': 101,
                'start_ticks': 7}
    with pytest.raises(runner.ObservationFailure, match=expected_error):
        asyncio.run(runner.bind_gui_window(launcher=FakeLauncher(),
                                           environment={},
                                           partition='mecanum_b2_test',
                                           deadline=10, steady=lambda: 0,
                                           process_identity_reader=(
                                               lambda _pid: identity),
                                           executable_reader=(
                                               lambda _path: '/usr/bin/gz'),
                                           argv_reader=(
                                               lambda _pid: ['/usr/bin/gz',
                                                             'sim', '-g']),
                                           partition_reader=(
                                               lambda _pid: partition)))


def test_window_capture_uses_injected_qt_api_and_writes_one_window_png(
        tmp_path):
    """Test helper for RUN002 offline behavior."""
    target = tmp_path / 'screenshots'
    target.mkdir(mode=448)
    pixels = bytes((1, 2, 3, 255, 4, 5, 6, 255))

    class Bits:

        def setsize(self, size):
            """Test helper for RUN002 offline behavior."""
            assert size == len(pixels)

        def __bytes__(self):
            return pixels

    class Image:
        Format_RGBA8888 = 7

        def isNull(self):
            """Test helper for RUN002 offline behavior."""
            return False

        def width(self):
            """Test helper for RUN002 offline behavior."""
            return 2

        def height(self):
            """Test helper for RUN002 offline behavior."""
            return 1

        def save(self, buffer, fmt):
            """Test helper for RUN002 offline behavior."""
            buffer.array.extend(b'PNG-test-fixture')
            return fmt == 'PNG'

        def convertToFormat(self, _fmt):
            """Test helper for RUN002 offline behavior."""
            return self

        def bits(self):
            """Test helper for RUN002 offline behavior."""
            return Bits()

        def byteCount(self):
            """Test helper for RUN002 offline behavior."""
            return len(pixels)

        @classmethod
        def fromData(cls, _data, _fmt):
            """Test helper for RUN002 offline behavior."""
            return cls()

    class Pixmap:

        def isNull(self):
            """Test helper for RUN002 offline behavior."""
            return False

        def toImage(self):
            """Test helper for RUN002 offline behavior."""
            return Image()

    class Screen:

        def grabWindow(self, window_id):
            """Test helper for RUN002 offline behavior."""
            assert window_id == 18
            return Pixmap()

    class App:

        @staticmethod
        def instance():
            """Test helper for RUN002 offline behavior."""
            return App()

        def primaryScreen(self):
            """Test helper for RUN002 offline behavior."""
            return Screen()

    class QByteArray(bytearray):
        pass

    class Buffer:

        def __init__(self, array):
            """Test helper for RUN002 offline behavior."""
            self.array = array

        def close(self):
            """Test helper for RUN002 offline behavior."""
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
    """Test helper for RUN002 offline behavior."""
    target = tmp_path / 'screenshots'
    target.mkdir(mode=448)
    pixels = b'\x00\x00\x00\xff' * 4

    class Bits:

        def setsize(self, _size):
            """Test helper for RUN002 offline behavior."""
            pass

        def __bytes__(self):
            return pixels

    class Image:
        Format_RGBA8888 = 1

        def isNull(self):
            """Test helper for RUN002 offline behavior."""
            return False

        def width(self):
            """Test helper for RUN002 offline behavior."""
            return 2

        def height(self):
            """Test helper for RUN002 offline behavior."""
            return 2

        def save(self, buffer, _fmt):
            """Test helper for RUN002 offline behavior."""
            buffer.array.extend(b'png')
            return True

        def convertToFormat(self, _fmt):
            """Test helper for RUN002 offline behavior."""
            return self

        def bits(self):
            """Test helper for RUN002 offline behavior."""
            return Bits()

        def byteCount(self):
            """Test helper for RUN002 offline behavior."""
            return len(pixels)

        @classmethod
        def fromData(cls, _data, _fmt):
            """Test helper for RUN002 offline behavior."""
            return cls()

    class Pixmap:

        def isNull(self):
            """Test helper for RUN002 offline behavior."""
            return False

        def toImage(self):
            """Test helper for RUN002 offline behavior."""
            return Image()

    class Screen:

        def grabWindow(self, _window):
            """Test helper for RUN002 offline behavior."""
            return Pixmap()

    class App:

        @staticmethod
        def instance():
            """Test helper for RUN002 offline behavior."""
            return App()

        def primaryScreen(self):
            """Test helper for RUN002 offline behavior."""
            return Screen()

    class Array(bytearray):
        pass

    class Buffer:

        def __init__(self, array):
            """Test helper for RUN002 offline behavior."""
            self.array = array

        def close(self):
            """Test helper for RUN002 offline behavior."""
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
    """Test helper for RUN002 offline behavior."""
    from collections import deque
    now = [0.0]
    session = str(uuid.uuid4())
    config = 'c' * 64

    class Observer:

        def __init__(self):
            """Test helper for RUN002 offline behavior."""
            self.events = deque()
            self.sequence = 0

        def spin_once(self, _timeout):
            """Test helper for RUN002 offline behavior."""
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
            """Test helper for RUN002 offline behavior."""
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

        async def start(self, command, _environment):
            if command[0] == '/usr/bin/xwininfo':
                output = tree
            else:
                output = properties[command[2]]
            process = Process(200 + len(self.records), output)
            self.records.append(SimpleNamespace(
                name='window_helper', pid=process.pid, process=process,
                identity={'pid': process.pid}, command=tuple(command)))
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

        async def start(self, command, _environment):
            record = SimpleNamespace(
                name='capture_helper', pid=700, process=process,
                identity=identity, command=tuple(command),
                identity_error=None)
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
    """Popen ownership exists before identity reading and is never guessed."""
    owned = []

    class Process:
        pid = 801
        returncode = None

        def __init__(self, *_args, **_kwargs):
            owned.append(self.pid)

        def poll(self):
            return self.returncode

        def wait(self, timeout):
            return self.returncode

    def read_identity(_pid):
        assert owned == [801]
        raise OSError('injected proc read failure')

    with pytest.raises(runner.ObservationFailure,
                       match='residue unknown'):
        runner.publish_review_result_bounded(
            '/tmp/request.json', verdict='PASS', reason='reviewed',
            request_deadline=10, steady=lambda: 0,
            popen=Process, identity_reader=read_identity,
        )
    assert owned == [801]


def test_publisher_communication_error_finalizes_verified_worker():
    """A writer error escalates only the process group it owns."""
    signals = []

    class Process:
        pid = 802
        returncode = None

        def __init__(self, *_args, **_kwargs):
            self.started = True

        def poll(self):
            return self.returncode

        def communicate(self, timeout):
            raise OSError('injected communicate failure')

        def wait(self, timeout):
            if signals and signals[-1] == signal.SIGKILL:
                self.returncode = -signal.SIGKILL
            return self.returncode

    identity = {
        'pid': 802, 'process_group_id': 802,
        'session_id': 802, 'start_ticks': 54,
    }
    with pytest.raises(runner.ObservationFailure, match='communicate failure'):
        runner.publish_review_result_bounded(
            '/tmp/request.json', verdict='PASS', reason='reviewed',
            request_deadline=10, steady=lambda: 0, popen=Process,
            identity_reader=lambda _pid: identity,
            signal_group=lambda pgid, sig: signals.append((pgid, sig)),
        )
    assert signals == [(802, signal.SIGTERM), (802, signal.SIGKILL)]


def test_publisher_identity_change_never_signals_unverified_group():
    """A changed start identity leaves residue unknown without signaling."""
    signals = []

    class Process:
        pid = 803
        returncode = None

        def __init__(self, *_args, **_kwargs):
            pass

        def poll(self):
            return self.returncode

        def communicate(self, timeout):
            raise OSError('injected writer error')

        def wait(self, timeout):
            return self.returncode

    identities = iter((
        {'pid': 803, 'process_group_id': 803,
         'session_id': 803, 'start_ticks': 55},
        {'pid': 803, 'process_group_id': 803,
         'session_id': 803, 'start_ticks': 56},
    ))
    with pytest.raises(runner.ObservationFailure,
                       match='residue unknown.*identity changed'):
        runner.publish_review_result_bounded(
            '/tmp/request.json', verdict='PASS', reason='reviewed',
            request_deadline=10, steady=lambda: 0, popen=Process,
            identity_reader=lambda _pid: next(identities),
            signal_group=lambda pgid, sig: signals.append((pgid, sig)),
        )
    assert signals == []


def test_publisher_started_callback_failure_finalizes_owned_handle():
    """A failed evidence callback still cleans the verified writer group."""
    signals = []

    class Process:
        pid = 804
        returncode = None

        def __init__(self, *_args, **_kwargs):
            pass

        def poll(self):
            return self.returncode

        def wait(self, timeout):
            if signals:
                self.returncode = -signals[-1][1]
            return self.returncode

    identity = {
        'pid': 804, 'process_group_id': 804,
        'session_id': 804, 'start_ticks': 57,
    }

    def fail_evidence(_process):
        raise RuntimeError('evidence callback failed')

    with pytest.raises(runner.ObservationFailure, match='evidence callback'):
        runner.publish_review_result_bounded(
            '/tmp/request.json', verdict='PASS', reason='reviewed',
            request_deadline=10, steady=lambda: 0, popen=Process,
            identity_reader=lambda _pid: identity,
            signal_group=lambda pgid, sig: signals.append((pgid, sig)),
            on_started=fail_evidence,
        )
    assert signals == [(804, signal.SIGTERM)]


def test_publisher_wait_failure_records_unknown_residue():
    """A wait error remains a failure and does not claim cleanup success."""
    signals = []

    class Process:
        pid = 805
        returncode = None

        def __init__(self, *_args, **_kwargs):
            pass

        def poll(self):
            return self.returncode

        def communicate(self, timeout):
            raise OSError('injected communicate error')

        def wait(self, timeout):
            raise OSError('injected wait error')

    identity = {
        'pid': 805, 'process_group_id': 805,
        'session_id': 805, 'start_ticks': 58,
    }
    with pytest.raises(runner.ObservationFailure,
                       match='residue unknown.*publisher wait failed'):
        runner.publish_review_result_bounded(
            '/tmp/request.json', verdict='PASS', reason='reviewed',
            request_deadline=10, steady=lambda: 0, popen=Process,
            identity_reader=lambda _pid: identity,
            signal_group=lambda pgid, sig: signals.append((pgid, sig)),
        )
    assert signals == [(805, signal.SIGTERM)]


def test_server_template_is_bound_to_run002_and_effective_world():
    """Pin the full effective server argv under the RUN002 evidence root."""
    template = bundle_packet()['commands_argv']['exact_templates']['server']
    expected = (
        '/home/hazan/mecanum_runtime_evidence/B22_GUI_OBSERVATION_RUN002/'
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
    run001_world = Path(str(world).replace('RUN002', 'RUN001'))
    plan.world_file = run001_world
    plan.commands = (tuple(template[:-1]) + (str(run001_world),),
                     plan.commands[1])
    with pytest.raises(runner.ObservationFailure,
                       match='canonical RUN002 asset'):
        runner._validate_plan_commands(plan, bundle_packet(), effective=True)
