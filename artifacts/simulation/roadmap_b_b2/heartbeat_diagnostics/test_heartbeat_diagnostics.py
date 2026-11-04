"""Deterministic, offline tests for heartbeat diagnostic correlation."""

import hashlib
import re
import unittest
from pathlib import Path

from heartbeat_diagnostics import (
    HEARTBEAT_THRESHOLD_NS,
    Binding,
    BoundedEventBuffer,
    CallMeasurement,
    Cause,
    DiagnosticEvent,
    EventKind,
    PublishCoverage,
    analyze,
    heartbeat_expired_reference,
    measure_once,
)


SESSION = 'session-test'
BACKEND_ID = 41
CONFIG_HASH = 'cfg-hash'
WORLD = 'b2_training_arena'
DOMAIN = 'host-monotonic-test'
PROVENANCE = 'synthetic-fixture-v1'
EXPECTED = Binding(SESSION, BACKEND_ID, CONFIG_HASH, WORLD)
BASE_NS = 10_000_000_000
CHECK_NS = BASE_NS + HEARTBEAT_THRESHOLD_NS + 1


def event(
    kind,
    sequence,
    timestamp,
    *,
    session=SESSION,
    backend=BACKEND_ID,
    config=CONFIG_HASH,
    world=WORLD,
    domain=DOMAIN,
    provenance=PROVENANCE,
    verified=True,
    uncertainty=0,
    metadata_supported=None,
    middleware_sequence=None,
    status_accepted=None,
    take_succeeded=None,
):
    fields = dict(
        kind=kind,
        session_id=session,
        backend_instance_id=backend,
        status_sequence=sequence,
        config_hash=config,
        world=world,
        timestamp_ns=timestamp,
        clock_domain=domain,
        provenance=provenance,
        source_verified=verified,
        uncertainty_ns=uncertainty,
        metadata_supported=metadata_supported,
        middleware_sequence=middleware_sequence,
    )
    if 'status_accepted' in DiagnosticEvent.__dataclass_fields__:
        fields['status_accepted'] = status_accepted
    if 'take_succeeded' in DiagnosticEvent.__dataclass_fields__:
        fields['take_succeeded'] = take_succeeded
    return DiagnosticEvent(**fields)


def validation_event(sequence, timestamp, accepted):
    validation_kind = getattr(EventKind, 'STATUS_VALIDATION', None)
    if validation_kind is None:
        return None
    return event(
        validation_kind, sequence, timestamp,
        status_accepted=accepted,
    )


def ready_event(sequence, timestamp, **kwargs):
    kind = getattr(EventKind, 'STATUS_READY', EventKind.RECEIVE_OR_READY)
    return event(kind, sequence, timestamp, metadata_supported=True, **kwargs)


def received_event(sequence, timestamp, **kwargs):
    kind = getattr(EventKind, 'STATUS_RECEIVED', EventKind.RECEIVE_OR_READY)
    return event(kind, sequence, timestamp, metadata_supported=True, **kwargs)


def baseline_events(check_ns=CHECK_NS):
    items = [
        event(EventKind.CALLBACK_ENTRY, 3, BASE_NS),
        event(EventKind.HEARTBEAT_CHECK, 3, check_ns),
    ]
    validation = validation_event(3, BASE_NS + 1, True)
    if validation is not None:
        items.insert(1, validation)
    return items


def buffer_with(*events, capacity=256):
    result = BoundedEventBuffer(capacity)
    for item in events:
        result.append(item)
    return result


class HeartbeatDiagnosisTests(unittest.TestCase):
    def test_publish_absence_with_late_coverage_start_is_unknown(self):
        coverage = PublishCoverage(
            binding=EXPECTED,
            start_ns=BASE_NS + 999_000_000,
            end_ns=CHECK_NS,
            clock_domain=DOMAIN,
            provenance='late-starting-backend-ring-v1',
            source_verified=True,
            complete=True,
            in_flight_clear_at_start=True,
        )
        diagnosis = analyze(
            buffer_with(*baseline_events()), expected=EXPECTED,
            publisher_coverage=coverage,
        )
        self.assertEqual(diagnosis.cause, Cause.UNKNOWN)

    def test_publish_evidence_inside_full_coverage_prevents_absence_cause(self):
        coverage = PublishCoverage(
            binding=EXPECTED,
            start_ns=BASE_NS,
            end_ns=CHECK_NS,
            clock_domain=DOMAIN,
            provenance='complete-backend-ring-v1',
            source_verified=True,
            complete=True,
            in_flight_clear_at_start=True,
        )
        diagnosis = analyze(
            buffer_with(
                *baseline_events(),
                event(EventKind.PUBLISH_BEGIN, 3, BASE_NS + 500_000_000),
            ),
            expected=EXPECTED,
            publisher_coverage=coverage,
        )
        self.assertEqual(diagnosis.cause, Cause.UNKNOWN)
        self.assertIn('conflicts with absence', diagnosis.reason)

    def test_ready_inside_uncertain_deadline_is_unknown(self):
        check_ns = BASE_NS + 1_020_000_000
        items = [
            event(EventKind.CALLBACK_ENTRY, 3, BASE_NS,
                  uncertainty=10_000_000),
            event(EventKind.STATUS_VALIDATION, 3, BASE_NS + 11_000_000,
                  status_accepted=True),
            event(EventKind.HEARTBEAT_CHECK, 3, check_ns),
            event(EventKind.PUBLISH_BEGIN, 4, BASE_NS + 900_000_000),
            event(EventKind.PUBLISH_RETURN, 4, BASE_NS + 910_000_000),
            ready_event(4, BASE_NS + 995_000_000),
            event(EventKind.CALLBACK_ENTRY, 4, check_ns + 1),
            event(EventKind.STATUS_VALIDATION, 4, check_ns + 2,
                  status_accepted=True),
        ]
        diagnosis = analyze(buffer_with(*items), expected=EXPECTED)
        self.assertTrue(diagnosis.heartbeat_expired)
        self.assertEqual(diagnosis.cause, Cause.UNKNOWN)

    def test_later_sequence_does_not_skip_unclassified_earlier_callback(self):
        items = baseline_events() + [
            event(EventKind.CALLBACK_ENTRY, 4, BASE_NS + 900_000_000),
            event(EventKind.PUBLISH_BEGIN, 5, BASE_NS + 800_000_000),
            event(EventKind.PUBLISH_RETURN, 5, BASE_NS + 810_000_000),
            received_event(5, CHECK_NS + 100),
            event(EventKind.CALLBACK_ENTRY, 5, CHECK_NS + 110),
            event(EventKind.STATUS_VALIDATION, 5, CHECK_NS + 120,
                  status_accepted=True),
        ]
        diagnosis = analyze(buffer_with(*items), expected=EXPECTED)
        self.assertEqual(diagnosis.cause, Cause.UNKNOWN)

    def test_ready_before_publish_begin_is_not_callback_delay(self):
        items = baseline_events(BASE_NS + 1_010_000_000) + [
            ready_event(4, BASE_NS + 900_000_000),
            event(EventKind.PUBLISH_BEGIN, 4, BASE_NS + 1_020_000_000),
            event(EventKind.PUBLISH_RETURN, 4, BASE_NS + 1_021_000_000),
            event(EventKind.CALLBACK_ENTRY, 4, BASE_NS + 1_030_000_000),
        ]
        validation = validation_event(4, BASE_NS + 1_031_000_000, True)
        if validation is not None:
            items.append(validation)
        diagnosis = analyze(buffer_with(*items), expected=EXPECTED)
        self.assertEqual(diagnosis.cause, Cause.UNKNOWN)

    def test_causal_order_uncertainty_overlap_is_unknown(self):
        items = baseline_events() + [
            event(EventKind.PUBLISH_BEGIN, 4, BASE_NS + 800_000_000,
                  uncertainty=5_000_000),
            ready_event(4, BASE_NS + 803_000_000,
                        uncertainty=5_000_000),
            event(EventKind.PUBLISH_RETURN, 4, BASE_NS + 810_000_000),
            event(EventKind.CALLBACK_ENTRY, 4, CHECK_NS + 100),
        ]
        validation = validation_event(4, CHECK_NS + 200, True)
        if validation is not None:
            items.append(validation)
        diagnosis = analyze(buffer_with(*items), expected=EXPECTED)
        self.assertEqual(diagnosis.cause, Cause.UNKNOWN)
        self.assertIn('publish begin', diagnosis.reason)

    def test_unresolved_precheck_publish_sample_blocks_later_sequence_cause(self):
        items = baseline_events(BASE_NS + 1_010_000_000) + [
            event(EventKind.PUBLISH_BEGIN, 4, BASE_NS + 800_000_000),
            event(EventKind.PUBLISH_RETURN, 4, BASE_NS + 810_000_000),
            event(EventKind.PUBLISH_BEGIN, 5, BASE_NS + 900_000_000),
            event(EventKind.PUBLISH_RETURN, 5, BASE_NS + 910_000_000),
            ready_event(5, BASE_NS + 950_000_000),
            event(EventKind.CALLBACK_ENTRY, 5, BASE_NS + 1_020_000_000),
        ]
        validation = validation_event(5, BASE_NS + 1_030_000_000, True)
        if validation is not None:
            items.append(validation)
        diagnosis = analyze(buffer_with(*items), expected=EXPECTED)
        self.assertEqual(diagnosis.cause, Cause.UNKNOWN)
        self.assertIn('seq=4', diagnosis.reason)

    def test_rejection_after_check_cannot_resolve_prior_ready_sample(self):
        check_ns = BASE_NS + 1_010_000_000
        items = baseline_events(check_ns) + [
            event(EventKind.PUBLISH_BEGIN, 4, BASE_NS + 800_000_000),
            event(EventKind.PUBLISH_RETURN, 4, BASE_NS + 810_000_000),
            ready_event(4, BASE_NS + 900_000_000),
            event(EventKind.CALLBACK_ENTRY, 4, BASE_NS + 1_020_000_000),
            event(EventKind.PUBLISH_BEGIN, 5, BASE_NS + 850_000_000),
            event(EventKind.PUBLISH_RETURN, 5, BASE_NS + 860_000_000),
            ready_event(5, BASE_NS + 950_000_000),
            event(EventKind.CALLBACK_ENTRY, 5, BASE_NS + 1_030_000_000),
        ]
        items.extend((
            validation_event(4, BASE_NS + 1_021_000_000, False),
            validation_event(5, BASE_NS + 1_031_000_000, True),
        ))
        diagnosis = analyze(
            buffer_with(*(item for item in items if item is not None)),
            expected=EXPECTED,
        )
        self.assertEqual(diagnosis.cause, Cause.UNKNOWN)
        self.assertIn('seq=4', diagnosis.reason)

    def test_rejection_overlapping_callback_uncertainty_does_not_resolve_sample(self):
        check_ns = BASE_NS + 1_010_000_000
        items = baseline_events(check_ns) + [
            event(EventKind.PUBLISH_BEGIN, 4, BASE_NS + 700_000_000),
            event(EventKind.PUBLISH_RETURN, 4, BASE_NS + 710_000_000),
            ready_event(4, BASE_NS + 800_000_000),
            event(EventKind.CALLBACK_ENTRY, 4, BASE_NS + 800_000_000,
                  uncertainty=100_000_000),
            event(EventKind.PUBLISH_BEGIN, 5, BASE_NS + 850_000_000),
            event(EventKind.PUBLISH_RETURN, 5, BASE_NS + 860_000_000),
            ready_event(5, BASE_NS + 950_000_000),
            event(EventKind.CALLBACK_ENTRY, 5, BASE_NS + 1_030_000_000),
        ]
        items.extend((
            validation_event(4, BASE_NS + 850_000_000, False),
            validation_event(5, BASE_NS + 1_031_000_000, True),
        ))
        diagnosis = analyze(
            buffer_with(*(item for item in items if item is not None)),
            expected=EXPECTED,
        )
        self.assertEqual(diagnosis.cause, Cause.UNKNOWN)
        self.assertIn('seq=4', diagnosis.reason)

    def test_precheck_publish_cannot_be_skipped_after_late_rejection(self):
        check_ns = BASE_NS + 1_010_000_000
        items = baseline_events(check_ns) + [
            event(EventKind.PUBLISH_BEGIN, 4, BASE_NS + 800_000_000),
            event(EventKind.PUBLISH_RETURN, 4, BASE_NS + 801_000_000),
            received_event(4, BASE_NS + 1_020_000_000),
            event(EventKind.CALLBACK_ENTRY, 4, BASE_NS + 1_021_000_000),
            event(EventKind.PUBLISH_BEGIN, 5, BASE_NS + 850_000_000),
            event(EventKind.PUBLISH_RETURN, 5, BASE_NS + 851_000_000),
            ready_event(5, BASE_NS + 950_000_000),
            event(EventKind.CALLBACK_ENTRY, 5, BASE_NS + 1_030_000_000),
        ]
        items.extend((
            validation_event(4, BASE_NS + 1_022_000_000, False),
            validation_event(5, BASE_NS + 1_031_000_000, True),
        ))
        diagnosis = analyze(
            buffer_with(*(item for item in items if item is not None)),
            expected=EXPECTED,
        )
        self.assertEqual(diagnosis.cause, Cause.UNKNOWN)
        self.assertIn('seq=4', diagnosis.reason)

    def test_take_after_callback_prevents_timeline_classification(self):
        items = baseline_events() + [
            event(EventKind.PUBLISH_BEGIN, 4, BASE_NS + 700_000_000),
            event(EventKind.PUBLISH_RETURN, 4, BASE_NS + 701_000_000),
            ready_event(4, BASE_NS + 900_000_000),
            event(EventKind.CALLBACK_ENTRY, 4, BASE_NS + 1_030_000_000),
            event(EventKind.TAKE, 4, BASE_NS + 1_040_000_000,
                  take_succeeded=True),
        ]
        validation = validation_event(4, BASE_NS + 1_050_000_000, True)
        if validation is not None:
            items.append(validation)
        diagnosis = analyze(buffer_with(*items), expected=EXPECTED)
        self.assertEqual(diagnosis.cause, Cause.UNKNOWN)

    def test_take_before_callback_preserves_verified_ready_classification(self):
        items = baseline_events() + [
            event(EventKind.PUBLISH_BEGIN, 4, BASE_NS + 700_000_000),
            event(EventKind.PUBLISH_RETURN, 4, BASE_NS + 701_000_000),
            ready_event(4, BASE_NS + 900_000_000),
            event(EventKind.TAKE, 4, BASE_NS + 1_020_000_000,
                  take_succeeded=True),
            event(EventKind.CALLBACK_ENTRY, 4, BASE_NS + 1_030_000_000),
        ]
        validation = validation_event(4, BASE_NS + 1_050_000_000, True)
        if validation is not None:
            items.append(validation)
        diagnosis = analyze(buffer_with(*items), expected=EXPECTED)
        self.assertEqual(diagnosis.cause, Cause.CALLBACK_SERVICE_DELAYED)

    def test_take_outcome_is_required_and_take_clock_must_match(self):
        items = baseline_events() + [
            event(EventKind.PUBLISH_BEGIN, 4, BASE_NS + 700_000_000),
            event(EventKind.PUBLISH_RETURN, 4, BASE_NS + 701_000_000),
            ready_event(4, BASE_NS + 900_000_000),
            event(EventKind.TAKE, 4, BASE_NS + 1_020_000_000,
                  take_succeeded=True, domain='other-monotonic'),
            event(EventKind.CALLBACK_ENTRY, 4, BASE_NS + 1_030_000_000),
            validation_event(4, BASE_NS + 1_050_000_000, True),
        ]
        diagnosis = analyze(
            buffer_with(*(item for item in items if item is not None)),
            expected=EXPECTED,
        )
        self.assertEqual(diagnosis.cause, Cause.UNKNOWN)
        self.assertIn('clock domain', diagnosis.reason)

    def test_take_without_outcome_is_unknown(self):
        items = baseline_events() + [
            event(EventKind.TAKE, 4, BASE_NS + 900_000_000),
            event(EventKind.CALLBACK_ENTRY, 4, BASE_NS + 1_030_000_000),
            validation_event(4, BASE_NS + 1_050_000_000, True),
        ]
        diagnosis = analyze(
            buffer_with(*(item for item in items if item is not None)),
            expected=EXPECTED,
        )
        self.assertEqual(diagnosis.cause, Cause.UNKNOWN)
        self.assertIn('take outcome', diagnosis.reason)

    def test_take_before_receive_cannot_support_receive_delay(self):
        check_ns = BASE_NS + 1_010_000_000
        items = baseline_events(check_ns) + [
            event(EventKind.PUBLISH_BEGIN, 4, BASE_NS + 800_000_000),
            event(EventKind.PUBLISH_RETURN, 4, BASE_NS + 801_000_000),
            event(EventKind.TAKE, 4, BASE_NS + 990_000_000,
                  take_succeeded=True),
            received_event(4, BASE_NS + 1_020_000_000),
            event(EventKind.CALLBACK_ENTRY, 4, BASE_NS + 1_030_000_000),
            validation_event(4, BASE_NS + 1_031_000_000, True),
        ]
        diagnosis = analyze(
            buffer_with(*(item for item in items if item is not None)),
            expected=EXPECTED,
        )
        self.assertEqual(diagnosis.cause, Cause.UNKNOWN)
        self.assertIn('receive/take order', diagnosis.reason)

    def test_receive_then_take_then_callback_can_classify_receive_delay(self):
        check_ns = BASE_NS + 1_010_000_000
        items = baseline_events(check_ns) + [
            event(EventKind.PUBLISH_BEGIN, 4, BASE_NS + 800_000_000),
            event(EventKind.PUBLISH_RETURN, 4, BASE_NS + 801_000_000),
            received_event(4, BASE_NS + 1_020_000_000),
            event(EventKind.TAKE, 4, BASE_NS + 1_025_000_000,
                  take_succeeded=True),
            event(EventKind.CALLBACK_ENTRY, 4, BASE_NS + 1_030_000_000),
            validation_event(4, BASE_NS + 1_031_000_000, True),
        ]
        diagnosis = analyze(
            buffer_with(*(item for item in items if item is not None)),
            expected=EXPECTED,
        )
        self.assertEqual(diagnosis.cause, Cause.RECEIVE_PATH_DELAYED)

    def test_rejected_sample_with_take_after_callback_blocks_later_sequence(self):
        check_ns = BASE_NS + 1_010_000_000
        items = baseline_events(check_ns) + [
            event(EventKind.CALLBACK_ENTRY, 4, BASE_NS + 900_000_000),
            event(EventKind.TAKE, 4, BASE_NS + 910_000_000,
                  take_succeeded=True),
            validation_event(4, BASE_NS + 920_000_000, False),
            event(EventKind.PUBLISH_BEGIN, 5, BASE_NS + 850_000_000),
            event(EventKind.PUBLISH_RETURN, 5, BASE_NS + 851_000_000),
            ready_event(5, BASE_NS + 950_000_000),
            event(EventKind.CALLBACK_ENTRY, 5, BASE_NS + 1_030_000_000),
            validation_event(5, BASE_NS + 1_031_000_000, True),
        ]
        diagnosis = analyze(
            buffer_with(*(item for item in items if item is not None)),
            expected=EXPECTED,
        )
        self.assertEqual(diagnosis.cause, Cause.UNKNOWN)
        self.assertIn('seq=4', diagnosis.reason)

    def test_ordered_take_before_rejected_callback_allows_later_sequence(self):
        check_ns = BASE_NS + 1_010_000_000
        items = baseline_events(check_ns) + [
            event(EventKind.TAKE, 4, BASE_NS + 890_000_000,
                  take_succeeded=True),
            event(EventKind.CALLBACK_ENTRY, 4, BASE_NS + 900_000_000),
            validation_event(4, BASE_NS + 920_000_000, False),
            event(EventKind.PUBLISH_BEGIN, 5, BASE_NS + 850_000_000),
            event(EventKind.PUBLISH_RETURN, 5, BASE_NS + 851_000_000),
            ready_event(5, BASE_NS + 950_000_000),
            event(EventKind.CALLBACK_ENTRY, 5, BASE_NS + 1_030_000_000),
            validation_event(5, BASE_NS + 1_031_000_000, True),
        ]
        diagnosis = analyze(
            buffer_with(*(item for item in items if item is not None)),
            expected=EXPECTED,
        )
        self.assertEqual(diagnosis.cause, Cause.CALLBACK_SERVICE_DELAYED)

    def test_baseline_take_after_callback_cannot_support_heartbeat_check(self):
        items = baseline_events() + [
            event(EventKind.TAKE, 3, BASE_NS + 10, take_succeeded=True),
            event(EventKind.PUBLISH_BEGIN, 4, BASE_NS + 800_000_000),
            event(EventKind.PUBLISH_RETURN, 4, BASE_NS + 801_000_000),
            ready_event(4, BASE_NS + 950_000_000),
            event(EventKind.CALLBACK_ENTRY, 4, BASE_NS + 1_030_000_000),
            validation_event(4, BASE_NS + 1_031_000_000, True),
        ]
        diagnosis = analyze(
            buffer_with(*(item for item in items if item is not None)),
            expected=EXPECTED,
        )
        self.assertEqual(diagnosis.cause, Cause.UNKNOWN)

    def test_take_callback_uncertainty_overlap_is_unknown(self):
        check_ns = BASE_NS + 1_010_000_000
        items = baseline_events(check_ns) + [
            event(EventKind.PUBLISH_BEGIN, 4, BASE_NS + 800_000_000),
            event(EventKind.PUBLISH_RETURN, 4, BASE_NS + 801_000_000),
            ready_event(4, BASE_NS + 900_000_000),
            event(EventKind.TAKE, 4, BASE_NS + 1_020_000_000,
                  uncertainty=30_000_000, take_succeeded=True),
            event(EventKind.CALLBACK_ENTRY, 4, BASE_NS + 1_040_000_000,
                  uncertainty=10_000_000),
            validation_event(4, BASE_NS + 1_080_000_000, True),
        ]
        diagnosis = analyze(
            buffer_with(*(item for item in items if item is not None)),
            expected=EXPECTED,
        )
        self.assertEqual(diagnosis.cause, Cause.UNKNOWN)
        self.assertIn('take/callback order', diagnosis.reason)

    def test_failed_take_is_not_successful_sample_evidence(self):
        items = baseline_events() + [
            event(EventKind.TAKE, 4, BASE_NS + 900_000_000,
                  take_succeeded=False),
            event(EventKind.CALLBACK_ENTRY, 4, BASE_NS + 1_030_000_000),
            validation_event(4, BASE_NS + 1_031_000_000, True),
        ]
        diagnosis = analyze(
            buffer_with(*(item for item in items if item is not None)),
            expected=EXPECTED,
        )
        self.assertEqual(diagnosis.cause, Cause.UNKNOWN)
        self.assertIn('lacks typed receive/ready', diagnosis.reason)

    def test_receive_timestamp_without_verified_ready_is_not_callback_delay(self):
        items = baseline_events() + [
            event(EventKind.PUBLISH_BEGIN, 4, BASE_NS + 700_000_000),
            event(EventKind.PUBLISH_RETURN, 4, BASE_NS + 710_000_000),
            received_event(4, BASE_NS + 900_000_000),
            event(EventKind.CALLBACK_ENTRY, 4, CHECK_NS + 100),
        ]
        validation = validation_event(4, CHECK_NS + 200, True)
        if validation is not None:
            items.append(validation)
        diagnosis = analyze(buffer_with(*items), expected=EXPECTED)
        self.assertEqual(diagnosis.cause, Cause.UNKNOWN)

    def test_ambiguous_legacy_receive_or_ready_is_not_treated_as_ready(self):
        items = baseline_events() + [
            event(EventKind.PUBLISH_BEGIN, 4, BASE_NS + 700_000_000),
            event(EventKind.PUBLISH_RETURN, 4, BASE_NS + 710_000_000),
            event(EventKind.RECEIVE_OR_READY, 4, BASE_NS + 900_000_000,
                  metadata_supported=True),
            event(EventKind.CALLBACK_ENTRY, 4, CHECK_NS + 100),
        ]
        validation = validation_event(4, CHECK_NS + 200, True)
        if validation is not None:
            items.append(validation)
        diagnosis = analyze(buffer_with(*items), expected=EXPECTED)
        self.assertEqual(diagnosis.cause, Cause.UNKNOWN)

    def test_ready_timestamp_does_not_prove_receive_path_delay(self):
        items = baseline_events() + [
            event(EventKind.PUBLISH_BEGIN, 4, BASE_NS + 800_000_000),
            event(EventKind.PUBLISH_RETURN, 4, BASE_NS + 810_000_000),
            ready_event(4, CHECK_NS + 100),
            event(EventKind.CALLBACK_ENTRY, 4, CHECK_NS + 110),
        ]
        validation = validation_event(4, CHECK_NS + 120, True)
        if validation is not None:
            items.append(validation)
        diagnosis = analyze(buffer_with(*items), expected=EXPECTED)
        self.assertEqual(diagnosis.cause, Cause.UNKNOWN)

    def test_explicitly_rejected_earlier_sample_allows_supported_later_sample(self):
        items = baseline_events() + [
            event(EventKind.PUBLISH_BEGIN, 4, BASE_NS + 850_000_000),
            event(EventKind.PUBLISH_RETURN, 4, BASE_NS + 860_000_000),
            event(EventKind.CALLBACK_ENTRY, 4, BASE_NS + 900_000_000),
            event(EventKind.PUBLISH_BEGIN, 5, BASE_NS + 800_000_000),
            event(EventKind.PUBLISH_RETURN, 5, BASE_NS + 810_000_000),
            received_event(5, CHECK_NS + 100),
            event(EventKind.CALLBACK_ENTRY, 5, CHECK_NS + 110),
        ]
        items.extend((
            validation_event(4, BASE_NS + 901_000_000, False),
            validation_event(5, CHECK_NS + 120, True),
        ))
        items = [item for item in items if item is not None]
        diagnosis = analyze(buffer_with(*items), expected=EXPECTED)
        self.assertEqual(diagnosis.cause, Cause.RECEIVE_PATH_DELAYED)

    def test_backend_stop_requires_complete_publisher_coverage(self):
        baseline = baseline_events()
        coverage = PublishCoverage(
            binding=EXPECTED,
            start_ns=BASE_NS,
            end_ns=CHECK_NS,
            clock_domain=DOMAIN,
            provenance='complete-backend-ring-v1',
            source_verified=True,
            complete=True,
            in_flight_clear_at_start=True,
        )
        diagnosis = analyze(
            buffer_with(*baseline), expected=EXPECTED,
            publisher_coverage=coverage,
        )
        self.assertEqual(diagnosis.cause, Cause.NO_PUBLISH_ATTEMPT)
        self.assertTrue(diagnosis.evidence_complete)
        self.assertTrue(diagnosis.heartbeat_expired)

        no_coverage = analyze(buffer_with(*baseline), expected=EXPECTED)
        self.assertEqual(no_coverage.cause, Cause.UNKNOWN)
        self.assertFalse(no_coverage.evidence_complete)

        incomplete = PublishCoverage(
            binding=EXPECTED,
            start_ns=BASE_NS,
            end_ns=CHECK_NS,
            clock_domain=DOMAIN,
            provenance='partial-backend-ring-v1',
            source_verified=True,
            complete=False,
            in_flight_clear_at_start=True,
        )
        self.assertEqual(
            analyze(buffer_with(*baseline), expected=EXPECTED,
                    publisher_coverage=incomplete).cause,
            Cause.UNKNOWN,
        )

        uncleared_boundary = PublishCoverage(
            binding=EXPECTED,
            start_ns=BASE_NS,
            end_ns=CHECK_NS,
            clock_domain=DOMAIN,
            provenance='boundary-in-flight-state-unknown-v1',
            source_verified=True,
            complete=True,
            in_flight_clear_at_start=False,
        )
        self.assertEqual(
            analyze(buffer_with(*baseline), expected=EXPECTED,
                    publisher_coverage=uncleared_boundary).cause,
            Cause.UNKNOWN,
        )

    def test_publish_on_time_and_receive_after_deadline_is_receive_delay(self):
        late_ns = CHECK_NS + 100
        items = baseline_events() + [
            event(EventKind.PUBLISH_BEGIN, 4, BASE_NS + 800_000_000),
            event(EventKind.PUBLISH_RETURN, 4, BASE_NS + 810_000_000),
            received_event(4, late_ns),
            event(EventKind.CALLBACK_ENTRY, 4, late_ns + 10),
            event(EventKind.STATUS_VALIDATION, 4, late_ns + 20,
                  status_accepted=True),
        ]
        diagnosis = analyze(buffer_with(*items), expected=EXPECTED)
        self.assertEqual(diagnosis.cause, Cause.RECEIVE_PATH_DELAYED)
        self.assertEqual(
            [item.kind for item in diagnosis.supporting_events],
            [
                EventKind.CALLBACK_ENTRY,
                EventKind.PUBLISH_BEGIN,
                EventKind.PUBLISH_RETURN,
                EventKind.STATUS_RECEIVED,
                EventKind.CALLBACK_ENTRY,
                EventKind.STATUS_VALIDATION,
                EventKind.HEARTBEAT_CHECK,
            ],
        )

    def test_ready_before_deadline_and_callback_after_is_callback_delay(self):
        items = baseline_events() + [
            event(EventKind.PUBLISH_BEGIN, 4, BASE_NS + 700_000_000),
            event(EventKind.PUBLISH_RETURN, 4, BASE_NS + 710_000_000),
            ready_event(4, BASE_NS + 900_000_000),
            event(EventKind.CALLBACK_ENTRY, 4, CHECK_NS + 100),
            event(EventKind.STATUS_VALIDATION, 4, CHECK_NS + 200,
                  status_accepted=True),
        ]
        diagnosis = analyze(buffer_with(*items), expected=EXPECTED)
        self.assertEqual(diagnosis.cause, Cause.CALLBACK_SERVICE_DELAYED)
        self.assertTrue(diagnosis.evidence_complete)

    def test_publish_return_may_follow_ready_without_invalidating_callback_delay(self):
        items = baseline_events() + [
            event(EventKind.PUBLISH_BEGIN, 4, BASE_NS + 700_000_000),
            ready_event(4, BASE_NS + 900_000_000),
            event(EventKind.PUBLISH_RETURN, 4, BASE_NS + 950_000_000),
            event(EventKind.CALLBACK_ENTRY, 4, CHECK_NS + 100),
        ]
        validation = validation_event(4, CHECK_NS + 200, True)
        if validation is not None:
            items.append(validation)
        diagnosis = analyze(buffer_with(*items), expected=EXPECTED)
        self.assertEqual(diagnosis.cause, Cause.CALLBACK_SERVICE_DELAYED)

    def test_publish_plus_callback_without_receive_is_unknown(self):
        items = baseline_events() + [
            event(EventKind.PUBLISH_BEGIN, 4, BASE_NS + 800_000_000),
            event(EventKind.PUBLISH_RETURN, 4, BASE_NS + 810_000_000),
            event(EventKind.CALLBACK_ENTRY, 4, CHECK_NS + 100),
        ]
        diagnosis = analyze(buffer_with(*items), expected=EXPECTED)
        self.assertEqual(diagnosis.cause, Cause.UNKNOWN)

    def test_take_alone_does_not_prove_receive_time(self):
        items = baseline_events() + [
            event(EventKind.TAKE, 4, BASE_NS + 900_000_000),
        ]
        diagnosis = analyze(buffer_with(*items), expected=EXPECTED)
        self.assertEqual(diagnosis.cause, Cause.UNKNOWN)

    def test_wrong_clock_domain_is_unknown(self):
        items = baseline_events() + [
            event(EventKind.PUBLISH_BEGIN, 4, BASE_NS + 700_000_000),
            event(EventKind.PUBLISH_RETURN, 4, BASE_NS + 710_000_000),
            event(
                EventKind.STATUS_RECEIVED, 4, CHECK_NS + 100,
                domain='unix-epoch', metadata_supported=True,
            ),
            event(EventKind.CALLBACK_ENTRY, 4, CHECK_NS + 200),
        ]
        self.assertEqual(
            analyze(buffer_with(*items), expected=EXPECTED).cause,
            Cause.UNKNOWN,
        )

    def test_binding_mismatch_duplicate_identity_and_unsupported_metadata(self):
        mismatch_fixtures = (
            {'session': 'other-session'},
            {'backend': BACKEND_ID + 1},
            {'config': 'other-config'},
            {'world': 'other-world'},
        )
        for override in mismatch_fixtures:
            with self.subTest(override=override):
                mismatch = baseline_events() + [
                    event(EventKind.PUBLISH_BEGIN, 4, BASE_NS, **override),
                ]
                self.assertEqual(
                    analyze(buffer_with(*mismatch), expected=EXPECTED).cause,
                    Cause.UNKNOWN,
                )

        duplicate = baseline_events() + [
            event(EventKind.STATUS_RECEIVED, 4, CHECK_NS + 1,
                  metadata_supported=True),
            event(EventKind.STATUS_RECEIVED, 4, CHECK_NS + 2,
                  metadata_supported=True),
        ]
        self.assertEqual(
            analyze(buffer_with(*duplicate), expected=EXPECTED).cause,
            Cause.UNKNOWN,
        )

        unsupported = baseline_events() + [
            event(EventKind.STATUS_READY, 4, CHECK_NS + 10,
                  metadata_supported=False),
            event(EventKind.CALLBACK_ENTRY, 4, CHECK_NS + 20),
            event(EventKind.STATUS_VALIDATION, 4, CHECK_NS + 30,
                  status_accepted=True),
        ]
        diagnosis = analyze(buffer_with(*unsupported), expected=EXPECTED)
        self.assertEqual(diagnosis.cause, Cause.UNKNOWN)
        self.assertIn('metadata is not verified', diagnosis.reason)

    def test_uncertainty_straddling_deadline_is_unknown(self):
        items = [
            event(EventKind.CALLBACK_ENTRY, 3, BASE_NS, uncertainty=2),
            event(EventKind.STATUS_VALIDATION, 3, BASE_NS + 10,
                  status_accepted=True),
            event(EventKind.HEARTBEAT_CHECK, 3, CHECK_NS, uncertainty=2),
        ]
        diagnosis = analyze(buffer_with(*items), expected=EXPECTED)
        self.assertEqual(diagnosis.cause, Cause.UNKNOWN)
        self.assertIn('uncertainty', diagnosis.reason)

    def test_buffer_overflow_invalidates_diagnosis(self):
        buffer = buffer_with(*baseline_events(), capacity=1)
        diagnosis = analyze(buffer, expected=EXPECTED)
        self.assertEqual(diagnosis.cause, Cause.UNKNOWN)
        self.assertIn('dropped_count=2', diagnosis.reason)

    def test_sink_measurement_success_and_slow_operation(self):
        ticks = iter((100, 125))
        measurement = CallMeasurement()
        calls = []

        def operation():
            calls.append('called')
            return 'record-sequence-7'

        result = measure_once(
            operation,
            monotonic_ns=lambda: next(ticks),
            measurement=measurement,
        )
        self.assertEqual(result, 'record-sequence-7')
        self.assertEqual(calls, ['called'])
        self.assertEqual(measurement.duration_ns, 25)

        ticks = iter((1_000, 1_000 + 1_200_000_000))
        slow = CallMeasurement()
        self.assertEqual(
            measure_once(lambda: 9, monotonic_ns=lambda: next(ticks),
                         measurement=slow),
            9,
        )
        self.assertEqual(slow.duration_ns, 1_200_000_000)

    def test_sink_measurement_preserves_original_exception_and_single_call(self):
        original = OSError('synthetic sink failure')
        calls = []
        measurement = CallMeasurement()
        ticks = iter((5, 17))

        def operation():
            calls.append(1)
            raise original

        with self.assertRaises(OSError) as caught:
            measure_once(
                operation,
                monotonic_ns=lambda: next(ticks),
                measurement=measurement,
            )
        self.assertIs(caught.exception, original)
        self.assertEqual(calls, [1])
        self.assertEqual(measurement.duration_ns, 12)

    def test_heartbeat_boundary_matches_strict_run008_comparison(self):
        repo_root = Path(__file__).resolve().parents[4]
        runner = (
            repo_root
            / 'artifacts/simulation/roadmap_b_b2/gui_observation_run008/tools'
            / 'observation_runner.py'
        )
        source = runner.read_bytes()
        self.assertEqual(
            hashlib.sha256(source).hexdigest(),
            'f57e22d700ae507d7e37d790b0754aac2191bcfc2cd9931de6c7402531c26ca4',
        )
        source_text = source.decode('utf-8')
        self.assertRegex(source_text, r'HEARTBEAT_GAP_S\s*=\s*1\.0')
        self.assertRegex(
            source_text,
            r'now\s*-\s*last_heartbeat\s*>\s*HEARTBEAT_GAP_S',
        )
        self.assertFalse(heartbeat_expired_reference(0, HEARTBEAT_THRESHOLD_NS))
        self.assertTrue(
            heartbeat_expired_reference(0, HEARTBEAT_THRESHOLD_NS + 1)
        )


if __name__ == '__main__':
    unittest.main()
