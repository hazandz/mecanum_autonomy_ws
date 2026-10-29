from dataclasses import replace
import pytest
from mecanum_nav_rl.core.issued_command_cutoff import CutoffStatus, IssuedCommandReceiptView, PolicyActionIssuance, ReceiptSource, ReceiptStreamBinding, select_final_issued_at_cutoff
from mecanum_nav_rl.core.lifecycle_types import EpisodeLifecycleIdentity
IDENTITY = EpisodeLifecycleIdentity(1, 2, 3)
BINDING = ReceiptStreamBinding(90, 'session-1', 'a' * 64, IDENTITY)
ISSUANCE = PolicyActionIssuance(7, 11, IDENTITY, 1, 'transition-1')
SCALES = (0.25, 0.2, 0.8)

def receipt(seq, stamp, source, source_seq, xyz=(0.0, 0.0, 0.0), **kw):
    return IssuedCommandReceiptView(stamp, 90, seq, source, 7, source_seq, 1,
        'transition-1', IDENTITY, 'session-1', 'a' * 64, xyz, **kw)

def select(items, cutoff=20, now=40):
    return select_final_issued_at_cutoff(tuple(items), binding=BINDING,
        issuance=ISSUANCE, cutoff_ros_ns=cutoff, evaluation_ros_now_ns=now, physical_scales=SCALES)

def valid_stream():
    return (receipt(1, 10, ReceiptSource.POLICY, 11, (0.1, -0.1, 0.4)),
        receipt(2, 20, ReceiptSource.SAFE_STOP, 2, (0.0, 0.0, 0.0)), receipt(3,
        30, ReceiptSource.POLICY, 12, (0.2, 0.1, 0.1)))

def test_selects_latest_sequence_at_cutoff_even_when_callbacks_reorder():
    result = select(tuple(reversed(valid_stream())))
    assert result.status is CutoffStatus.READY
    assert result.receipt.final_publish_sequence == 2
    assert result.normalized_command == (0.0, 0.0, 0.0)

def test_same_stamp_uses_highest_publish_sequence_and_adjacent_receipt():
    items = (receipt(1, 20, ReceiptSource.POLICY, 11, (0.1, 0, 0)), receipt(2,
        20, ReceiptSource.SAFE_STOP, 2, (0, 0,
        0)), receipt(3, 21, ReceiptSource.POLICY, 12))
    result = select(items, cutoff=20, now=21)
    assert result.status is CutoffStatus.READY
    assert result.receipt.final_publish_sequence == 2

def test_missing_or_gapped_trailing_receipt_is_pending():
    assert select(valid_stream()[:1]).status is CutoffStatus.PENDING
    assert select((valid_stream()[0],
        valid_stream()[2])).status is CutoffStatus.PENDING

def test_policy_then_stop_and_stop_then_policy_choose_actual_last_payload():
    stop = receipt(2, 20, ReceiptSource.SAFE_STOP, 9, (0, 0, 0))
    later = receipt(3, 21, ReceiptSource.POLICY, 12, (0.05, 0.02, -0.4))
    trailing = receipt(4, 22, ReceiptSource.SAFE_STOP, 10, (0, 0, 0))
    assert select((valid_stream()[0], stop, later,
        trailing)).receipt.source is ReceiptSource.SAFE_STOP
    assert select((valid_stream()[0], stop, later, trailing), cutoff=21,
        now=22).normalized_command == pytest.approx((0.2, 0.1, -0.5))

def test_stop_after_cutoff_only_proves_boundary_and_does_not_rewrite_past_snapshot():
    policy = receipt(1, 10, ReceiptSource.POLICY, 11, (0.1, -0.1, 0.4))
    stop = receipt(2, 20, ReceiptSource.SAFE_STOP, 99, (0, 0, 0))
    result = select((policy, stop), cutoff=10, now=20)
    assert result.status is CutoffStatus.READY
    assert result.receipt == policy
    assert result.normalized_command == pytest.approx((0.4, -0.5, 0.5))

def test_wrong_context_rollback_conflicting_duplicate_and_invalid_latest_reject():
    base = valid_stream()
    assert select((base[0], replace(base[1], final_publisher_instance_id=91),
        base[2])).status is CutoffStatus.REJECTED
    assert select((base[0], replace(base[1], publish_stamp_ns=5),
        base[2])).status is CutoffStatus.REJECTED
    assert select((base[0], base[1], replace(base[1], final_command=(1.0, 0.0,
        0.0)), base[2])).status is CutoffStatus.REJECTED
    assert select((base[0], replace(base[1], admission_valid=False),
        base[2])).status is CutoffStatus.REJECTED
    assert select((base[0], replace(base[1], session_id='other-session'),
        base[2])).status is CutoffStatus.REJECTED
    assert select((base[0], replace(base[1], ingress_config_hash='b' * 64),
        base[2])).status is CutoffStatus.REJECTED

def test_future_stamp_wrong_lifecycle_and_absent_issuance_reject():
    base = valid_stream()
    assert select((base[0], base[1], replace(base[2], publish_stamp_ns=50)),
        now=40).status is CutoffStatus.REJECTED
    assert select((base[0], replace(base[1],
        lifecycle=EpisodeLifecycleIdentity(2, 3,
        4)), base[2])).status is CutoffStatus.REJECTED
    assert select((base[1], base[2])).status is CutoffStatus.REJECTED
    wrong_source = (receipt(1, 10, ReceiptSource.NAV2, 11), base[1], base[2])
    assert select(wrong_source).status is CutoffStatus.REJECTED
    issued_after_cutoff = (receipt(1, 21, ReceiptSource.POLICY, 11), receipt(2,
        30, ReceiptSource.SAFE_STOP, 2))
    assert select(issued_after_cutoff, cutoff=20,
        now=30).status is CutoffStatus.REJECTED

def test_publisher_restart_and_sequence_timestamp_rollback_reject():
    base = valid_stream()
    assert select((base[0], replace(base[1], final_publisher_instance_id=91),
        base[2])).status is CutoffStatus.REJECTED
    assert select((base[0], replace(base[1], final_publish_sequence=3,
        publish_stamp_ns=15), base[2])).status is CutoffStatus.REJECTED

def test_command_outside_axis_envelope_rejects_without_clamp():
    bad = receipt(2, 20, ReceiptSource.SAFE_STOP, 2, (0.251, 0, 0))
    assert select((valid_stream()[0], bad,
        valid_stream()[2])).status is CutoffStatus.REJECTED
