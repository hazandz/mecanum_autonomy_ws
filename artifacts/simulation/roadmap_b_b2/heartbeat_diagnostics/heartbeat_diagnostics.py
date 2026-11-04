"""Offline, bounded correlation of supplied heartbeat diagnostic events.

This module does not collect ROS data, write evidence, or issue runtime verdicts.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from enum import Enum
from threading import Lock
from typing import Callable, Optional, TypeVar


HEARTBEAT_THRESHOLD_NS = 1_000_000_000
DEFAULT_EVENT_CAPACITY = 256
T = TypeVar('T')


class EventKind(str, Enum):
    PUBLISH_BEGIN = 'publish_begin'
    PUBLISH_RETURN = 'publish_return'
    RECEIVE_OR_READY = 'receive_or_ready'
    TAKE = 'take'
    CALLBACK_ENTRY = 'callback_entry'
    HEARTBEAT_CHECK = 'heartbeat_check'


class Cause(str, Enum):
    BACKEND_STOPPED = 'backend_stopped'
    RECEIVE_PATH_DELAYED = 'receive_path_delayed'
    CALLBACK_SERVICE_DELAYED = 'callback_service_delayed'
    UNKNOWN = 'unknown'


@dataclass(frozen=True)
class Binding:
    session_id: str
    backend_instance_id: int
    config_hash: str
    world: str


@dataclass(frozen=True)
class DiagnosticEvent:
    """One externally supplied timestamp with explicit provenance."""

    kind: EventKind
    session_id: str
    backend_instance_id: int
    status_sequence: int
    config_hash: str
    world: str
    timestamp_ns: int
    clock_domain: str
    provenance: str
    source_verified: bool
    uncertainty_ns: int = 0
    metadata_supported: Optional[bool] = None
    middleware_sequence: Optional[int] = None


@dataclass(frozen=True)
class PublishCoverage:
    """Claim that publisher instrumentation covered one interval completely."""

    binding: Binding
    start_ns: int
    end_ns: int
    clock_domain: str
    provenance: str
    source_verified: bool
    complete: bool


@dataclass(frozen=True)
class Diagnosis:
    """Diagnostic classification only; never a runtime acceptance verdict."""

    cause: Cause
    evidence_complete: bool
    reason: str
    heartbeat_expired: Optional[bool]
    supporting_events: tuple[DiagnosticEvent, ...] = ()


class BoundedEventBuffer:
    """Fixed-capacity FIFO; overflow is visible and invalidates diagnosis."""

    def __init__(self, capacity: int = DEFAULT_EVENT_CAPACITY) -> None:
        if isinstance(capacity, bool) or not isinstance(capacity, int) or capacity <= 0:
            raise ValueError('capacity must be a positive integer')
        self._events: deque[DiagnosticEvent] = deque(maxlen=capacity)
        self._capacity = capacity
        self._dropped_count = 0
        self._lock = Lock()

    def append(self, event: DiagnosticEvent) -> None:
        if not isinstance(event, DiagnosticEvent):
            raise TypeError('event must be DiagnosticEvent')
        with self._lock:
            if len(self._events) == self._capacity:
                self._dropped_count += 1
            self._events.append(event)

    def snapshot(self) -> tuple[tuple[DiagnosticEvent, ...], int]:
        with self._lock:
            return tuple(self._events), self._dropped_count


def heartbeat_expired_reference(
    last_receive_ns: int,
    check_ns: int,
    threshold_ns: int = HEARTBEAT_THRESHOLD_NS,
) -> bool:
    """Mirror the RUN008 strict `gap > 1 s` comparison for offline fixtures."""

    values = (last_receive_ns, check_ns, threshold_ns)
    if any(isinstance(value, bool) or not isinstance(value, int) for value in values):
        raise TypeError('heartbeat timestamps and threshold must be integers')
    if last_receive_ns < 0 or check_ns < 0 or threshold_ns < 0:
        raise ValueError('heartbeat timestamps and threshold must be non-negative')
    return check_ns - last_receive_ns > threshold_ns


@dataclass
class CallMeasurement:
    start_ns: Optional[int] = None
    end_ns: Optional[int] = None
    duration_ns: Optional[int] = None
    measurement_error: Optional[str] = None


def measure_once(
    operation: Callable[[], T],
    *,
    monotonic_ns: Callable[[], int],
    measurement: CallMeasurement,
) -> T:
    """Measure one call without changing its result or masking its exception.

    Clock failures make the measurement incomplete, but do not prevent the
    operation from running and do not replace an operation exception.
    """

    measurement.start_ns = None
    measurement.end_ns = None
    measurement.duration_ns = None
    measurement.measurement_error = None
    try:
        start = monotonic_ns()
        if isinstance(start, bool) or not isinstance(start, int) or start < 0:
            raise ValueError('clock returned an invalid start timestamp')
        measurement.start_ns = start
    except BaseException as error:  # diagnostic failure must not skip operation
        measurement.measurement_error = f'start_clock:{type(error).__name__}'

    try:
        return operation()
    finally:
        try:
            end = monotonic_ns()
            if isinstance(end, bool) or not isinstance(end, int) or end < 0:
                raise ValueError('clock returned an invalid end timestamp')
            measurement.end_ns = end
            if measurement.start_ns is None:
                measurement.measurement_error = measurement.measurement_error or 'start_missing'
            elif end < measurement.start_ns:
                measurement.measurement_error = 'clock_went_backwards'
            else:
                measurement.duration_ns = end - measurement.start_ns
        except BaseException as error:  # preserve return/exception from operation
            measurement.measurement_error = measurement.measurement_error or (
                f'end_clock:{type(error).__name__}'
            )


def _valid_nonnegative_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _unknown(reason: str, heartbeat_expired: Optional[bool] = None) -> Diagnosis:
    return Diagnosis(Cause.UNKNOWN, False, reason, heartbeat_expired)


def _definitely_before_or_at(event: DiagnosticEvent, deadline_ns: int) -> bool:
    return event.timestamp_ns + event.uncertainty_ns <= deadline_ns


def _definitely_after(event: DiagnosticEvent, deadline_ns: int) -> bool:
    return event.timestamp_ns - event.uncertainty_ns > deadline_ns


def analyze(
    buffer: BoundedEventBuffer,
    *,
    expected: Binding,
    publisher_coverage: Optional[PublishCoverage] = None,
    threshold_ns: int = HEARTBEAT_THRESHOLD_NS,
) -> Diagnosis:
    """Correlate one heartbeat window using identity, sequence and clock domain.

    Events are never joined by arrival order or timestamp proximity. A positive
    cause requires verified provenance and an unambiguous sample identity.
    """

    events, dropped = buffer.snapshot()
    if dropped:
        return _unknown(f'event buffer overflowed; dropped_count={dropped}')
    if not isinstance(expected, Binding):
        return _unknown('expected binding has invalid type')
    if (
        not isinstance(expected.session_id, str)
        or not expected.session_id
        or not isinstance(expected.config_hash, str)
        or not expected.config_hash
        or not isinstance(expected.world, str)
        or not expected.world
        or not _valid_nonnegative_int(expected.backend_instance_id)
        or expected.backend_instance_id == 0
    ):
        return _unknown('expected binding is incomplete')
    if not _valid_nonnegative_int(threshold_ns):
        return _unknown('heartbeat threshold is invalid')
    if not events:
        return _unknown('no diagnostic events supplied')

    for event in events:
        if not isinstance(event, DiagnosticEvent):
            return _unknown('malformed diagnostic event')
        if not isinstance(event.kind, EventKind):
            return _unknown('event kind is unsupported')
        if (
            event.session_id != expected.session_id
            or not isinstance(event.backend_instance_id, int)
            or isinstance(event.backend_instance_id, bool)
            or event.backend_instance_id <= 0
            or event.backend_instance_id != expected.backend_instance_id
            or event.config_hash != expected.config_hash
            or event.world != expected.world
        ):
            return _unknown('event binding mismatch')
        if (
            not _valid_nonnegative_int(event.status_sequence)
            or event.status_sequence == 0
            or not _valid_nonnegative_int(event.timestamp_ns)
            or not _valid_nonnegative_int(event.uncertainty_ns)
            or not event.clock_domain
            or not event.provenance
            or not isinstance(event.source_verified, bool)
        ):
            return _unknown('event timestamp, identity, or provenance is incomplete')

    checks = [event for event in events if event.kind is EventKind.HEARTBEAT_CHECK]
    if len(checks) != 1:
        return _unknown('heartbeat check is missing or duplicated')
    check = checks[0]
    domain = check.clock_domain
    if not check.source_verified:
        return _unknown('heartbeat-check source is not verified')

    baseline_seq = check.status_sequence
    baseline = [
        event for event in events
        if event.kind is EventKind.CALLBACK_ENTRY
        and event.status_sequence == baseline_seq
    ]
    if len(baseline) != 1:
        return _unknown('baseline callback is missing or ambiguous')
    last = baseline[0]
    if not last.source_verified or last.clock_domain != domain:
        return _unknown('baseline callback clock/provenance is unverified')

    minimum_gap = (
        check.timestamp_ns - check.uncertainty_ns
        - (last.timestamp_ns + last.uncertainty_ns)
    )
    maximum_gap = (
        check.timestamp_ns + check.uncertainty_ns
        - (last.timestamp_ns - last.uncertainty_ns)
    )
    if minimum_gap > threshold_ns:
        expired: Optional[bool] = True
    elif maximum_gap <= threshold_ns:
        expired = False
    else:
        return _unknown('heartbeat boundary overlaps timestamp uncertainty')
    if not expired:
        return Diagnosis(Cause.UNKNOWN, True, 'heartbeat threshold is not exceeded', False)

    deadline_ns = last.timestamp_ns + threshold_ns
    next_sequences = sorted({
        event.status_sequence for event in events
        if event.status_sequence > baseline_seq
    })
    indexed: dict[tuple[EventKind, int], list[DiagnosticEvent]] = {}
    for event in events:
        if event.status_sequence > baseline_seq:
            indexed.setdefault((event.kind, event.status_sequence), []).append(event)
    if any(len(items) > 1 for items in indexed.values()):
        return _unknown('duplicate event identity makes sample correlation ambiguous', True)

    for sequence in next_sequences:
        sample = {
            kind: indexed.get((kind, sequence), [])
            for kind in EventKind
        }
        relevant = [event for items in sample.values() for event in items]
        if any(event.clock_domain != domain for event in relevant):
            return _unknown('correlated sample uses a different clock domain', True)
        if any(not event.source_verified for event in relevant):
            return _unknown('correlated sample provenance is unverified', True)

        receive = sample[EventKind.RECEIVE_OR_READY]
        callback = sample[EventKind.CALLBACK_ENTRY]
        if receive:
            event = receive[0]
            if event.metadata_supported is not True:
                return _unknown('receive/ready metadata is not verified as supported', True)
            if callback:
                callback_event = callback[0]
                if (
                    _definitely_before_or_at(event, deadline_ns)
                    and _definitely_after(callback_event, deadline_ns)
                ):
                    return Diagnosis(
                        Cause.CALLBACK_SERVICE_DELAYED, True,
                        'verified receive/ready precedes deadline; callback entry follows it',
                        True, (last, event, callback_event, check),
                    )
                if (
                    _definitely_after(event, deadline_ns)
                    and _definitely_after(callback_event, deadline_ns)
                ):
                    begin = sample[EventKind.PUBLISH_BEGIN]
                    returned = sample[EventKind.PUBLISH_RETURN]
                    if len(begin) == 1 and len(returned) == 1:
                        if (
                            begin[0].timestamp_ns + begin[0].uncertainty_ns
                            > returned[0].timestamp_ns - returned[0].uncertainty_ns
                        ):
                            return _unknown(
                                'publish begin/return order is not verified', True,
                            )
                        if (
                            callback_event.timestamp_ns
                            + callback_event.uncertainty_ns
                            < event.timestamp_ns - event.uncertainty_ns
                        ):
                            return _unknown(
                                'callback timestamp precedes receive/ready timestamp',
                                True,
                            )
                        if (
                            _definitely_before_or_at(begin[0], deadline_ns)
                            and _definitely_before_or_at(returned[0], deadline_ns)
                        ):
                            return Diagnosis(
                                Cause.RECEIVE_PATH_DELAYED, True,
                                'verified publish completed before deadline; receive/ready follows it',
                                True, (last, begin[0], returned[0], event, callback_event, check),
                            )
                    return _unknown(
                        'late receive has no timely, complete publish-call evidence', True,
                    )
                return _unknown('sample timing overlaps the heartbeat deadline', True)
            return _unknown('receive/ready exists without callback entry', True)

    if publisher_coverage is not None:
        coverage = publisher_coverage
        if (
            coverage.binding != expected
            or not isinstance(coverage.source_verified, bool)
            or not coverage.source_verified
            or not isinstance(coverage.complete, bool)
            or not coverage.complete
            or not isinstance(coverage.provenance, str)
            or not coverage.provenance
            or not isinstance(coverage.clock_domain, str)
            or not coverage.clock_domain
            or coverage.clock_domain != domain
            or not _valid_nonnegative_int(coverage.start_ns)
            or not _valid_nonnegative_int(coverage.end_ns)
        ):
            return _unknown('publisher coverage is incomplete or mismatched', True)
        latest_deadline_ns = (
            last.timestamp_ns + last.uncertainty_ns + threshold_ns
        )
        latest_check_ns = check.timestamp_ns + check.uncertainty_ns
        if (
            coverage.start_ns > latest_deadline_ns
            or coverage.end_ns < latest_check_ns
        ):
            return _unknown('publisher coverage does not span the heartbeat window', True)
        publish_attempts = [
            event for event in events
            if event.kind is EventKind.PUBLISH_BEGIN
            and event.status_sequence > baseline_seq
            and event.clock_domain == domain
            and event.source_verified
        ]
        if not publish_attempts:
            return Diagnosis(
                Cause.BACKEND_STOPPED, True,
                'complete verified publisher coverage shows no later publish attempt',
                True, (last, check),
            )
        if any(_definitely_after(event, deadline_ns) for event in publish_attempts):
            return _unknown('publisher attempted the next status after the deadline', True)

    return _unknown('available events cannot distinguish publish, receive, and callback delay', True)
