"""Offline behavior tests for diagnostic status observation only."""
from pathlib import Path
from types import SimpleNamespace

from mecanum_nav_bringup.local_training_heartbeat_trace_observer import (
    EVENT_CALLBACK_ENTRY, EVENT_HEARTBEAT_CHECK, EVENT_STATUS_BASELINE,
    EVENT_STATUS_VALIDATION,
    LocalTrainingHeartbeatTraceObserver, clock_context,
    measure_clock_domain_certificate,
)


class FakeTraceApi:
    """Store native writer calls while providing deterministic fake time."""

    def __init__(self, times):
        """Initialize clock samples and captured writer operations."""
        self.times = iter(times)
        self.records = []
        self.closed = []

    def hbtrace_clock_monotonic_ns(self):
        """Return the next injected monotonic timestamp."""
        return next(self.times)

    def hbtrace_open_path(self, *args):
        """Record the file binding passed to the C API."""
        self.open_args = args
        return 17

    def hbtrace_append(self, writer, kind, timestamp, sequence, payload, size):
        """Append one diagnostic record to the in-memory fixture."""
        data = bytes(payload[:size]) if size else b''
        self.records.append((writer, kind, timestamp, sequence, data))
        return 1

    def hbtrace_close(self, writer):
        """Record closure of the fake native writer."""
        self.closed.append(writer)


def _readiness_status(backend=42):
    return {
        'world_id': 'b2_training_arena', 'session_id': 'session-1',
        'config_hash': 'a' * 64, 'backend_instance_id': backend,
        'status_sequence': 1, 'fault_flags': 0,
        'actuator_inhibited': True,
    }


def _observer(api, *, ready=True):
    """Construct an observer without importing or starting ROS."""
    plan = SimpleNamespace(
        session_id='session-1', config_hash='a' * 64,
        environment={'ROS_DOMAIN_ID': '83'},
    )
    observer = LocalTrainingHeartbeatTraceObserver(
        plan=plan,
        trace_file={
            'path': '/private/observer.hbtrace', 'device': 1, 'inode': 2,
        },
        collection_id='session-1', clock_provenance='c' * 64,
        library_path=Path('/private/libwriter.so'),
        api_loader=lambda _path: api,
    )
    observer._api = api
    if ready:
        assert observer.bind_readiness_backend(_readiness_status())
    return observer


def _status(*, backend=42, sequence=1, session='session-1', config='a' * 64,
            world='b2_training_arena', paused=True, inhibited=True,
            faults=0, receipt=False):
    """Build one producer-shaped fake status message."""
    return SimpleNamespace(
        session_id=session, config_hash=config, backend_instance_id=backend,
        status_sequence=sequence,
        header=SimpleNamespace(frame_id=world), paused=paused,
        actuator_inhibited=inhibited, fault_flags=faults,
        applied_receipt_valid=receipt,
    )


def test_status_callback_records_binding_validation_without_runtime_control():
    """Record callback and health validation without changing control."""
    api = FakeTraceApi([100, 101, 102])
    observer = _observer(api)
    observer._on_status(_status())
    assert api.open_args[6] == 42
    assert [record[4] for record in api.records[1:]] == [
        bytes((EVENT_CALLBACK_ENTRY, 0)),
        bytes((EVENT_STATUS_VALIDATION, 1)),
        bytes((10, 1)),
    ]
    assert api.records[0][2] <= api.records[1][2]
    assert observer._last_accepted_sequence == 1
    assert observer.snapshot()['errors'] == ()


def test_heartbeat_diagnostic_uses_strictly_greater_than_one_second():
    """Keep the diagnostic threshold strict and supervisor-independent."""
    api = FakeTraceApi([100, 101, 1_000_000_100, 1_000_000_101])
    observer = _observer(api)
    observer._on_status(_status())
    observer._check_heartbeat()
    assert not any(record[4][0] == EVENT_HEARTBEAT_CHECK
                   for record in api.records if record[4])
    observer._check_heartbeat()
    checks = [record for record in api.records
              if record[4] and record[4][0] == EVENT_HEARTBEAT_CHECK]
    assert len(checks) == 1
    assert checks[0][4] == bytes((EVENT_HEARTBEAT_CHECK, 1))


def test_session_identity_change_is_reported_and_not_recorded_as_same_sample():
    """Reject a backend instance change inside the bound session."""
    api = FakeTraceApi([100, 101, 102, 200])
    observer = _observer(api)
    observer._on_status(_status())
    count = len(api.records)
    observer._on_status(_status(backend=43, sequence=2))
    assert len(api.records) == count
    assert 'readiness_backend_instance_mismatch' in (
        observer.snapshot()['errors']
    )


def test_invalid_health_is_recorded_as_diagnostic_validation_failure():
    """Retain unhealthy status as a diagnostic validation failure."""
    api = FakeTraceApi([100, 101, 102])
    observer = _observer(api)
    observer._on_status(_status(faults=1))
    assert api.records[-2][4] == bytes((EVENT_STATUS_VALIDATION, 0))
    assert api.records[-1][4] == bytes((EVENT_STATUS_BASELINE, 0))
    assert observer._last_accepted_ns is None


def test_status_before_readiness_cannot_open_writer_or_set_baseline():
    """Only a callback after accepted readiness may initialize the trace."""
    api = FakeTraceApi([100, 101, 102])
    observer = _observer(api, ready=False)
    observer._on_status(_status(sequence=1))
    assert api.records == []
    assert observer._last_accepted_sequence is None

    assert observer.bind_readiness_backend(_readiness_status())
    observer._on_status(_status(sequence=2))
    assert api.open_args[6] == 42
    assert observer._last_accepted_sequence == 2


def test_readiness_instance_is_checked_before_writer_open_and_update():
    """Do not bind a callback to a different ready backend instance."""
    api = FakeTraceApi([100, 101, 102])
    observer = _observer(api, ready=False)
    assert observer.bind_readiness_backend(_readiness_status(backend=43))
    observer._on_status(_status(backend=42, sequence=1))
    assert api.records == []
    assert observer._last_accepted_sequence is None
    assert 'readiness_backend_instance_mismatch' in (
        observer.snapshot()['errors']
    )


def test_health_validation_and_baseline_use_are_separate_trace_events():
    """A healthy duplicate remains valid health but is not a baseline."""
    api = FakeTraceApi([100, 101, 102, 200, 201, 202])
    observer = _observer(api)
    observer._on_status(_status(sequence=9))
    observer._on_status(_status(sequence=9))
    events = [record[4] for record in api.records if record[4]]
    health = [item for item in events if item[0] == EVENT_STATUS_VALIDATION]
    baseline = [item for item in events if item[0] == 10]
    assert health == [bytes((EVENT_STATUS_VALIDATION, 1))] * 2
    assert baseline == [bytes((10, 1)), bytes((10, 0))]


def test_python_clock_context_matches_shared_linux_provenance_shape():
    """Expose clock provenance without treating resolution as uncertainty."""
    context = clock_context()
    assert context['clock'] == 'CLOCK_MONOTONIC'
    assert len(context['provenance']) == 64
    assert context['clock_resolution_ns'] > 0


def test_duplicate_and_out_of_order_sequences_do_not_refresh_heartbeat():
    """Only an accepted, strictly advancing sequence moves the baseline."""
    api = FakeTraceApi([
        100, 101, 102, 200, 201, 202, 300, 301, 302,
    ])
    observer = _observer(api)
    observer._on_status(_status(sequence=5))
    baseline_ns = observer._last_accepted_ns
    baseline_sequence = observer._last_accepted_sequence

    observer._on_status(_status(sequence=5))
    assert observer._last_accepted_ns == baseline_ns
    assert observer._last_accepted_sequence == baseline_sequence
    assert bytes((9, 1)) in [record[4] for record in api.records]
    assert api.records[-1][4] == bytes((10, 0))

    observer._on_status(_status(sequence=4))
    assert observer._last_accepted_ns == baseline_ns
    assert observer._last_accepted_sequence == baseline_sequence
    assert bytes((9, 2)) in [record[4] for record in api.records]
    assert api.records[-1][4] == bytes((10, 0))

    observer._on_status(_status(sequence=6))
    assert observer._last_accepted_ns == 300
    assert observer._last_accepted_sequence == 6


def test_duplicate_at_exact_threshold_does_not_renew_the_baseline():
    """A duplicate at 1 s leaves the old baseline to expire strictly later."""
    api = FakeTraceApi([
        100, 101, 1_000_000_100, 1_000_000_101,
        1_000_000_101, 1_000_000_102,
    ])
    observer = _observer(api)
    observer._on_status(_status(sequence=10))
    observer._on_status(_status(sequence=10))
    assert observer._last_accepted_ns == 100
    assert not any(record[4] == bytes((EVENT_HEARTBEAT_CHECK, 1))
                   for record in api.records)
    observer._check_heartbeat()
    assert api.records[-1][4] == bytes((EVENT_HEARTBEAT_CHECK, 1))


def test_observer_requires_plan_ros_domain_and_reports_thread_readiness():
    """A missing launch domain cannot silently use the process default."""
    from unittest.mock import patch

    api = FakeTraceApi([])
    observer = _observer(api)
    observer.plan = SimpleNamespace(
        session_id='session-1', config_hash='a' * 64, environment={},
    )
    started_threads = []

    class ThreadSentinel:
        def __init__(self, **_kwargs):
            started_threads.append(self)

        def start(self):
            pass

    with patch(
        'mecanum_nav_bringup.local_training_heartbeat_trace_observer.'
        'threading.Thread', ThreadSentinel,
    ):
        assert observer.start() is False
    assert started_threads == []
    state = observer.snapshot()
    assert state['ready'] is False
    assert any('ROS_DOMAIN_ID' in error for error in state['errors'])


def test_joined_is_false_while_observer_thread_is_alive():
    """A live thread is never reported joined by its own finally block."""
    import threading

    observer = _observer(FakeTraceApi([]))
    gate = threading.Event()
    thread = threading.Thread(target=gate.wait)
    observer._thread = thread
    thread.start()
    try:
        assert observer.snapshot()['joined'] is False
    finally:
        gate.set()
        thread.join(1)


def test_nonresponsive_observer_stop_is_bounded_and_reports_residue():
    """A live, nonresponsive thread is not joined or treated as closed."""
    import asyncio
    import threading

    observer = _observer(FakeTraceApi([]))
    gate = threading.Event()
    thread = threading.Thread(target=gate.wait)
    observer._thread = thread
    thread.start()
    try:
        assert asyncio.run(observer.stop_async(timeout_s=0)) is False
        snapshot = observer.snapshot()
        assert snapshot['thread_alive'] is True
        assert snapshot['joined'] is False
        assert snapshot['writer_closed'] is False
        assert 'observer_thread_residue_unknown' in snapshot['errors']
    finally:
        gate.set()
        thread.join(1)


def test_observer_finalizer_does_not_claim_join_while_thread_is_live():
    """Thread cleanup cannot set the owner's join result from inside itself."""
    import sys
    from types import ModuleType
    from unittest.mock import patch

    class FakeContext:
        def init(self, **_kwargs):
            pass

        def ok(self):
            return False

        def shutdown(self):
            pass

    class FakeNode:
        def __init__(self, *_args, **_kwargs):
            pass

        def create_subscription(self, *_args, **_kwargs):
            return object()

        def create_timer(self, *_args, **_kwargs):
            return object()

        def destroy_node(self):
            pass

    class FakeExecutor:
        def __init__(self, **_kwargs):
            pass

        def add_node(self, _node):
            pass

        def shutdown(self, **_kwargs):
            pass

    class LiveThreadIdentity:
        def is_alive(self):
            return True

    modules = {
        'rclpy': ModuleType('rclpy'),
        'rclpy.context': ModuleType('rclpy.context'),
        'rclpy.executors': ModuleType('rclpy.executors'),
        'rclpy.node': ModuleType('rclpy.node'),
        'mecanum_nav_rl_interfaces': ModuleType('mecanum_nav_rl_interfaces'),
        'mecanum_nav_rl_interfaces.msg': ModuleType(
            'mecanum_nav_rl_interfaces.msg',
        ),
    }
    modules['rclpy.context'].Context = FakeContext
    modules['rclpy.executors'].SingleThreadedExecutor = FakeExecutor
    modules['rclpy.node'].Node = FakeNode
    modules['mecanum_nav_rl_interfaces.msg'].SimulationContactState = object
    observer = _observer(FakeTraceApi([]))
    observer._ros_domain_id = 83
    observer._thread = LiveThreadIdentity()
    with patch.dict(sys.modules, modules):
        observer._thread_main()
    state = observer.snapshot()
    assert observer._thread.is_alive() is True
    assert state['joined'] is False


def test_observer_initializes_fake_context_with_plan_domain_and_joins():
    """Use only middleware fakes to verify launch-domain binding and join."""
    import sys
    import threading
    from types import ModuleType
    from unittest.mock import patch

    released = threading.Event()
    initialized = {}

    class FakeContext:
        def __init__(self):
            self.running = True

        def init(self, **kwargs):
            initialized.update(kwargs)

        def ok(self):
            return self.running

        def shutdown(self):
            self.running = False
            released.set()

    class FakeNode:
        def __init__(self, *_args, **_kwargs):
            pass

        def create_subscription(self, *_args, **_kwargs):
            return object()

        def create_timer(self, *_args, **_kwargs):
            return object()

        def destroy_node(self):
            pass

    class FakeExecutor:
        def __init__(self, **_kwargs):
            pass

        def add_node(self, _node):
            pass

        def spin_once(self, **_kwargs):
            released.wait(1)

        def shutdown(self, **_kwargs):
            released.set()

    modules = {
        'rclpy': ModuleType('rclpy'),
        'rclpy.context': ModuleType('rclpy.context'),
        'rclpy.executors': ModuleType('rclpy.executors'),
        'rclpy.node': ModuleType('rclpy.node'),
        'mecanum_nav_rl_interfaces': ModuleType('mecanum_nav_rl_interfaces'),
        'mecanum_nav_rl_interfaces.msg': ModuleType(
            'mecanum_nav_rl_interfaces.msg',
        ),
    }
    modules['rclpy.context'].Context = FakeContext
    modules['rclpy.executors'].SingleThreadedExecutor = FakeExecutor
    modules['rclpy.node'].Node = FakeNode
    modules['mecanum_nav_rl_interfaces.msg'].SimulationContactState = object
    observer = _observer(FakeTraceApi([]))
    with patch.dict(sys.modules, modules):
        assert observer.start() is True
        assert initialized == {'args': None, 'domain_id': 83}
        assert observer.snapshot()['ready'] is True
        assert observer.stop(timeout_s=1) is True
    assert observer.snapshot()['joined'] is True
    assert observer.snapshot()['thread_alive'] is False


def test_native_clock_domain_check_does_not_claim_an_error_bound(tmp_path):
    """Retain observed bracket width without calling it a bound."""
    binary = tmp_path / 'writer.so'
    binary.write_bytes(b'fake writer bytes')
    python_values = iter([90, 110] * 3)

    class NativeClockApi:
        @staticmethod
        def hbtrace_clock_monotonic_ns():
            return 100

    certificate = measure_clock_domain_certificate(
        binary, sample_count=3, api_loader=lambda _path: NativeClockApi(),
        python_clock_ns=lambda: next(python_values),
    )
    assert certificate['observed_max_bracket_width_ns'] == 20
    assert 'error_bound_ns' not in certificate
    assert certificate['binary_sha256']
    assert len(certificate['samples']) == 3


def test_native_clock_outside_bracket_does_not_produce_domain_check(tmp_path):
    """A native timestamp outside its Python bracket fails the clock check."""
    binary = tmp_path / 'writer.so'
    binary.write_bytes(b'fake writer bytes')

    class NativeClockApi:
        @staticmethod
        def hbtrace_clock_monotonic_ns():
            return 200

    values = iter([90, 110] * 3)
    try:
        measure_clock_domain_certificate(
            binary, sample_count=3,
            api_loader=lambda _path: NativeClockApi(),
            python_clock_ns=lambda: next(values),
        )
    except ValueError as error:
        assert 'outside Python bracket' in str(error)
    else:
        raise AssertionError('invalid native clock bracket was accepted')
