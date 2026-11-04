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
    # Deprecated ambiguous event kind: never use it as receive or ready.
    RECEIVE_OR_READY = 'receive_or_ready'
    STATUS_RECEIVED = 'status_received'
    STATUS_READY = 'status_ready'
    TAKE = 'take'
    CALLBACK_ENTRY = 'callback_entry'
    STATUS_VALIDATION = 'status_validation'
    HEARTBEAT_CHECK = 'heartbeat_check'


class Cause(str, Enum):
    NO_PUBLISH_ATTEMPT = 'no_publish_attempt_observed'
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
    status_accepted: Optional[bool] = None


@dataclass(frozen=True)
class PublishCoverage:
    """Verified, loss-free publisher coverage and clear in-flight boundary."""

    binding: Binding
    start_ns: int
    end_ns: int
    clock_domain: str
    provenance: str
    source_verified: bool
    complete: bool
    in_flight_clear_at_start: bool


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


def _definitely_precedes(first: DiagnosticEvent, second: DiagnosticEvent) -> bool:
    """Return true only when the timestamp intervals establish causal order."""

    return (
        first.timestamp_ns + first.uncertainty_ns
        <= second.timestamp_ns - second.uncertainty_ns
    )


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
            or not isinstance(event.clock_domain, str)
            or not event.clock_domain
            or not isinstance(event.provenance, str)
            or not event.provenance
            or not isinstance(event.source_verified, bool)
        ):
            return _unknown('event timestamp, identity, or provenance is incomplete')
        if event.kind is EventKind.STATUS_VALIDATION:
            if not isinstance(event.status_accepted, bool):
                return _unknown('status-validation outcome is missing')
        elif event.status_accepted is not None:
            return _unknown('status outcome is attached to the wrong event kind')

    checks = [event for event in events if event.kind is EventKind.HEARTBEAT_CHECK]
    if len(checks) != 1:
        return _unknown('heartbeat check is missing or duplicated')
    check = checks[0]
    domain = check.clock_domain
    if not check.source_verified:
        return _unknown('heartbeat-check source is not verified')

    baseline_seq = check.status_sequence
    baseline_callbacks = [
        event for event in events
        if event.kind is EventKind.CALLBACK_ENTRY
        and event.status_sequence == baseline_seq
    ]
    baseline_validations = [
        event for event in events
        if event.kind is EventKind.STATUS_VALIDATION
        and event.status_sequence == baseline_seq
    ]
    if len(baseline_callbacks) != 1 or len(baseline_validations) != 1:
        return _unknown('baseline callback or validation is missing/ambiguous')
    last = baseline_callbacks[0]
    baseline_validation = baseline_validations[0]
    if (
        not last.source_verified
        or not baseline_validation.source_verified
        or last.clock_domain != domain
        or baseline_validation.clock_domain != domain
        or baseline_validation.status_accepted is not True
    ):
        return _unknown('baseline status was not verifiably accepted')

    check_earliest = check.timestamp_ns - check.uncertainty_ns
    check_latest = check.timestamp_ns + check.uncertainty_ns
    last_earliest = last.timestamp_ns - last.uncertainty_ns
    last_latest = last.timestamp_ns + last.uncertainty_ns
    if baseline_validation.timestamp_ns + baseline_validation.uncertainty_ns > check_earliest:
        return _unknown('baseline acceptance is not established before heartbeat check')
    if baseline_validation.timestamp_ns + baseline_validation.uncertainty_ns < last_earliest:
        return _unknown('baseline validation predates its callback sample')
    if not _definitely_precedes(last, baseline_validation):
        return _unknown('baseline callback/validation order is not established')

    minimum_gap = check_earliest - last_latest
    maximum_gap = check_latest - last_earliest
    if minimum_gap > threshold_ns:
        expired: Optional[bool] = True
    elif maximum_gap <= threshold_ns:
        expired = False
    else:
        return _unknown('heartbeat boundary overlaps timestamp uncertainty')
    if not expired:
        return Diagnosis(Cause.UNKNOWN, True, 'heartbeat threshold is not exceeded', False)

    earliest_deadline_ns = last_earliest + threshold_ns
    latest_deadline_ns = last_latest + threshold_ns

    sequences = sorted({
        event.status_sequence for event in events
        if event.status_sequence > baseline_seq
    })
    indexed: dict[tuple[EventKind, int], list[DiagnosticEvent]] = {}
    for event in events:
        if event.status_sequence > baseline_seq:
            indexed.setdefault((event.kind, event.status_sequence), []).append(event)
    if any(len(items) > 1 for items in indexed.values()):
        return _unknown('duplicate event identity makes sample correlation ambiguous', True)

    resolved_rejections: set[int] = set()
    # Resolve every sample that could affect the check before considering a
    # later sequence. A rejection is usable only if callback -> validation and
    # validation -> check are established by non-overlapping time intervals.
    for sequence in sequences:
        callbacks = indexed.get((EventKind.CALLBACK_ENTRY, sequence), [])
        validations = indexed.get((EventKind.STATUS_VALIDATION, sequence), [])
        receives = indexed.get((EventKind.STATUS_RECEIVED, sequence), [])
        readies = indexed.get((EventKind.STATUS_READY, sequence), [])
        takes = indexed.get((EventKind.TAKE, sequence), [])
        ambiguous_times = indexed.get((EventKind.RECEIVE_OR_READY, sequence), [])
        publish_events = [
            event for kind in (EventKind.PUBLISH_BEGIN, EventKind.PUBLISH_RETURN)
            for event in indexed.get((kind, sequence), [])
        ]
        if ambiguous_times:
            return _unknown(
                f'seq={sequence} uses ambiguous receive_or_ready timestamp semantics',
                True,
            )
        if validations and not callbacks:
            return _unknown(f'seq={sequence} validation has no matching callback', True)
        for callback_event in callbacks:
            if callback_event.clock_domain != domain or not callback_event.source_verified:
                return _unknown('callback clock/provenance is unverified', True)
            callback_earliest = callback_event.timestamp_ns - callback_event.uncertainty_ns
            callback_latest = callback_event.timestamp_ns + callback_event.uncertainty_ns
            if callback_earliest <= check_latest:
                if callback_latest > check_earliest:
                    return _unknown(
                        f'seq={sequence} callback/check order overlaps timestamp uncertainty',
                        True,
                    )
                if len(validations) != 1:
                    return _unknown(
                        f'seq={sequence} pre-check callback has no unique validation outcome',
                        True,
                    )
                validation = validations[0]
                if (
                    validation.clock_domain != domain
                    or not validation.source_verified
                    or validation.timestamp_ns + validation.uncertainty_ns > check_earliest
                ):
                    return _unknown(
                        f'seq={sequence} pre-check validation is not resolved before check',
                        True,
                    )
                if not _definitely_precedes(callback_event, validation):
                    return _unknown(
                        f'seq={sequence} callback/validation order overlaps uncertainty',
                        True,
                    )
                if validation.status_accepted:
                    return _unknown(
                        f'seq={sequence} accepted status conflicts with check baseline',
                        True,
                    )
                resolved_rejections.add(sequence)

        precheck_times = receives + readies + takes
        has_precheck_time = any(
            item.timestamp_ns - item.uncertainty_ns <= check_latest
            for item in precheck_times
        )
        if (
            has_precheck_time
            and validations
            and validations[0].status_accepted is False
            and sequence not in resolved_rejections
        ):
            return _unknown(
                f'seq={sequence} rejection was not established by heartbeat check',
                True,
            )

        publish_may_precede_check = any(
            event.timestamp_ns - event.uncertainty_ns <= check_latest
            for event in publish_events
        )
        if (
            publish_may_precede_check
            and not callbacks
            and not precheck_times
            and not validations
        ):
            return _unknown(
                f'seq={sequence} publish sample is unresolved at heartbeat check',
                True,
            )

    for sequence in sequences:
        sample = {
            kind: indexed.get((kind, sequence), [])
            for kind in EventKind
        }
        relevant = [event for items in sample.values() for event in items]
        if any(event.clock_domain != domain for event in relevant):
            return _unknown('correlated sample uses a different clock domain', True)
        if any(not event.source_verified for event in relevant):
            return _unknown('correlated sample provenance is unverified', True)

        callback_items = sample[EventKind.CALLBACK_ENTRY]
        validation_items = sample[EventKind.STATUS_VALIDATION]
        receive_items = sample[EventKind.STATUS_RECEIVED]
        ready_items = sample[EventKind.STATUS_READY]
        take_items = sample[EventKind.TAKE]
        ambiguous_items = sample[EventKind.RECEIVE_OR_READY]
        if ambiguous_items:
            return _unknown(
                f'seq={sequence} receive_or_ready is not a typed timing source',
                True,
            )
        if not callback_items:
            if receive_items or ready_items or take_items:
                return _unknown(
                    f'seq={sequence} sample timing exists without callback entry',
                    True,
                )
            continue
        callback_event = callback_items[0]
        callback_earliest = callback_event.timestamp_ns - callback_event.uncertainty_ns
        if callback_earliest <= check_latest:
            if sequence in resolved_rejections:
                continue
            return _unknown(
                f'seq={sequence} callback outcome was not resolved at heartbeat check',
                True,
            )
        if len(validation_items) != 1:
            if any(
                item.timestamp_ns - item.uncertainty_ns <= check_latest
                for item in receive_items + ready_items + take_items
            ):
                return _unknown(
                    f'seq={sequence} pre-check receive/ready lacks validation', True,
                )
            return _unknown(
                f'seq={sequence} post-check callback has no unique validation outcome',
                True,
            )
        validation = validation_items[0]
        if validation.status_accepted is False:
            if sequence in resolved_rejections:
                continue
            if any(
                item.timestamp_ns - item.uncertainty_ns <= check_latest
                for item in receive_items + ready_items + take_items
            ):
                return _unknown(
                    f'seq={sequence} rejection was not established by heartbeat check',
                    True,
                )
            continue
        if not _definitely_precedes(callback_event, validation):
            return _unknown(
                f'seq={sequence} callback/validation order is not established', True,
            )
        if not receive_items and not ready_items:
            return _unknown(f'seq={sequence} lacks typed receive/ready timestamp', True)
        timing_events = receive_items + ready_items
        if any(item.metadata_supported is not True for item in timing_events):
            return _unknown(
                f'seq={sequence} typed receive/ready metadata is not verified', True,
            )
        begin_items = sample[EventKind.PUBLISH_BEGIN]
        return_items = sample[EventKind.PUBLISH_RETURN]
        for timing_event in timing_events:
            if begin_items and not _definitely_precedes(begin_items[0], timing_event):
                return _unknown(
                    f'seq={sequence} publish begin does not precede typed timing event',
                    True,
                )
        if begin_items and return_items and not _definitely_precedes(
            begin_items[0], return_items[0],
        ):
            return _unknown(
                f'seq={sequence} publish begin/return order is not established', True,
            )
        if receive_items and ready_items and not _definitely_precedes(
            receive_items[0], ready_items[0],
        ):
            return _unknown(
                f'seq={sequence} middleware receive/ready order is not established',
                True,
            )
        if ready_items and not _definitely_precedes(ready_items[0], callback_event):
            return _unknown(
                f'seq={sequence} ready does not definitely precede callback', True,
            )
        if receive_items and not _definitely_precedes(receive_items[0], callback_event):
            return _unknown(
                f'seq={sequence} receive does not definitely precede callback', True,
            )

        ready_on_time = bool(ready_items) and _definitely_before_or_at(
            ready_items[0], earliest_deadline_ns,
        )
        receive_late = bool(receive_items) and _definitely_after(
            receive_items[0], latest_deadline_ns,
        )
        callback_late = _definitely_after(callback_event, latest_deadline_ns)
        if ready_on_time and callback_late:
            return Diagnosis(
                Cause.CALLBACK_SERVICE_DELAYED, True,
                'verified ready is before the earliest deadline; callback starts after the latest deadline',
                True, (last, ready_items[0], callback_event, validation, check),
            )
        if receive_late and callback_late:
            begin = sample[EventKind.PUBLISH_BEGIN]
            returned = sample[EventKind.PUBLISH_RETURN]
            if len(begin) != 1 or len(returned) != 1:
                return _unknown(
                    'late receive lacks a complete publish-call pair', True,
                )
            begin_before = _definitely_before_or_at(
                begin[0], earliest_deadline_ns,
            )
            return_before = _definitely_before_or_at(
                returned[0], earliest_deadline_ns,
            )
            if not begin_before or not return_before:
                return _unknown(
                    'publish call is not proven complete before earliest deadline',
                    True,
                )
            if (
                begin[0].timestamp_ns + begin[0].uncertainty_ns
                > returned[0].timestamp_ns - returned[0].uncertainty_ns
            ):
                return _unknown('publish begin/return order is not verified', True)
            return Diagnosis(
                Cause.RECEIVE_PATH_DELAYED, True,
                'verified publish call completed before earliest deadline; receive/ready follows latest deadline',
                True, (
                    last, begin[0], returned[0], receive_items[0],
                    callback_event, validation, check,
                ),
            )
        return _unknown('sample timing is not definitely on either side of deadline', True)

    if publisher_coverage is not None:
        coverage = publisher_coverage
        if (
            coverage.binding != expected
            or not isinstance(coverage.source_verified, bool)
            or not coverage.source_verified
            or not isinstance(coverage.complete, bool)
            or not coverage.complete
            or not isinstance(coverage.in_flight_clear_at_start, bool)
            or not coverage.in_flight_clear_at_start
            or not isinstance(coverage.provenance, str)
            or not coverage.provenance
            or not isinstance(coverage.clock_domain, str)
            or not coverage.clock_domain
            or coverage.clock_domain != domain
            or not _valid_nonnegative_int(coverage.start_ns)
            or not _valid_nonnegative_int(coverage.end_ns)
        ):
            return _unknown('publisher coverage or in-flight boundary is incomplete', True)
        if (
            coverage.start_ns > last_earliest
            or coverage.end_ns < check_latest
        ):
            return _unknown(
                'publisher coverage does not span earliest baseline sample to latest check',
                True,
            )
        window_sample_events = [
            event for event in events
            if event.status_sequence != baseline_seq
            and event.timestamp_ns + event.uncertainty_ns >= coverage.start_ns
            and event.timestamp_ns - event.uncertainty_ns <= coverage.end_ns
        ]
        publish_events_in_window = [
            event for event in events
            if event.kind in (EventKind.PUBLISH_BEGIN, EventKind.PUBLISH_RETURN)
            and event.timestamp_ns + event.uncertainty_ns >= coverage.start_ns
            and event.timestamp_ns - event.uncertainty_ns <= coverage.end_ns
        ]
        if window_sample_events or publish_events_in_window:
            return _unknown(
                'sample or publish evidence conflicts with absence conclusion', True,
            )
        return Diagnosis(
            Cause.NO_PUBLISH_ATTEMPT, True,
            'complete publisher instrumentation observed no publish_begin in the full window; this does not establish backend death',
            True, (last, baseline_validation, check),
        )

    return _unknown('available events cannot distinguish publish, receive, and callback delay', True)
