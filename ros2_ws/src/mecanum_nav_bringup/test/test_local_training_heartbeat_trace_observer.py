"""Offline behavior tests for diagnostic status observation only."""
from pathlib import Path
from types import SimpleNamespace

from mecanum_nav_bringup.local_training_heartbeat_trace_observer import (
    EVENT_CALLBACK_ENTRY, EVENT_HEARTBEAT_CHECK, EVENT_STATUS_VALIDATION,
    LocalTrainingHeartbeatTraceObserver, clock_context,
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


def _observer(api):
    """Construct an observer without importing or starting ROS."""
    plan = SimpleNamespace(
        session_id='session-1', config_hash='a' * 64,
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
    assert 'backend_instance_changed_within_session' in (
        observer.snapshot()['errors']
    )


def test_invalid_health_is_recorded_as_diagnostic_validation_failure():
    """Retain unhealthy status as a diagnostic validation failure."""
    api = FakeTraceApi([100, 101, 102])
    observer = _observer(api)
    observer._on_status(_status(faults=1))
    assert api.records[-1][4] == bytes((EVENT_STATUS_VALIDATION, 0))
    assert observer._last_accepted_ns is None


def test_python_clock_context_matches_shared_linux_provenance_shape():
    """Expose clock provenance without treating resolution as uncertainty."""
    context = clock_context()
    assert context['clock'] == 'CLOCK_MONOTONIC'
    assert len(context['provenance']) == 64
    assert context['clock_resolution_ns'] > 0
