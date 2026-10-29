"""Kiểm tra chọn receipt lệnh cuối tại observation cutoff."""
from dataclasses import replace

from mecanum_nav_rl.core.issued_command_cutoff import (
    CutoffStatus,
    IssuedCommandReceiptView,
    PolicyActionIssuance,
    ReceiptSource,
    ReceiptStreamBinding,
    select_final_issued_at_cutoff,
    select_reset_zero_at_cutoff,
)
from mecanum_nav_rl.core.lifecycle_types import EpisodeLifecycleIdentity

import pytest

IDENTITY = EpisodeLifecycleIdentity(1, 2, 3)
BINDING = ReceiptStreamBinding(
    90, 'session-1', 'a' * 64, IDENTITY, 'base_link'
)
ISSUANCE = PolicyActionIssuance(7, 11, IDENTITY, 1, 'transition-1')
SCALES = (0.25, 0.2, 0.8)


def receipt(seq, stamp, source, source_seq, xyz=(0.0, 0.0, 0.0), **kw):
    """Tạo receipt view đã copy cho một test stream."""
    return IssuedCommandReceiptView(
        stamp,
        90,
        seq,
        source,
        7,
        source_seq,
        1,
        'transition-1',
        IDENTITY,
        'session-1',
        'a' * 64,
        xyz,
        stamp,
        'base_link',
        True,
        **kw,
    )


def select(items, cutoff=20, now=40):
    """Chạy selector với thời điểm đánh giá được truyền tường minh."""
    return select_final_issued_at_cutoff(
        tuple(items),
        binding=BINDING,
        issuance=ISSUANCE,
        cutoff_ros_ns=cutoff,
        evaluation_ros_now_ns=now,
        evaluation_steady_now_ns=now,
        reset_barrier_ros_ns=0,
        action_barrier_ros_ns=0,
        physical_scales=SCALES,
    )


def valid_stream():
    """Trả về stream ba publication hợp lệ quanh cutoff mặc định."""
    return (
        receipt(1, 10, ReceiptSource.POLICY, 11, (0.1, -0.1, 0.4)),
        receipt(2, 20, ReceiptSource.SAFE_STOP, 2, (0.0, 0.0, 0.0)),
        receipt(3, 30, ReceiptSource.POLICY, 12, (0.2, 0.1, 0.1)),
    )


def test_selects_latest_sequence_at_cutoff_even_when_callbacks_reorder():
    """Dùng publication sequence khi callback đến sai thứ tự."""
    result = select(tuple(reversed(valid_stream())))
    assert result.status is CutoffStatus.READY
    assert result.receipt.final_publish_sequence == 2
    assert result.normalized_command == (0.0, 0.0, 0.0)


def test_same_stamp_uses_highest_publish_sequence_and_adjacent_receipt():
    """Sắp thứ tự stamp bằng final publication sequence."""
    items = (
        receipt(1, 20, ReceiptSource.POLICY, 11, (0.1, 0, 0)),
        receipt(2, 20, ReceiptSource.SAFE_STOP, 2, (0, 0, 0)),
        receipt(3, 21, ReceiptSource.POLICY, 12),
    )
    result = select(items, cutoff=20, now=21)
    assert result.status is CutoffStatus.READY
    assert result.receipt.final_publish_sequence == 2


def test_missing_or_gapped_trailing_receipt_is_pending():
    """Trả pending khi thiếu receipt biên liền kề."""
    assert select(valid_stream()[:1]).status is CutoffStatus.PENDING
    assert select(
        (valid_stream()[0], valid_stream()[2])
    ).status is CutoffStatus.PENDING


def test_policy_then_stop_and_stop_then_policy_choose_actual_last_payload():
    """Chọn payload được phát cuối cùng tại từng cutoff."""
    stop = receipt(2, 20, ReceiptSource.SAFE_STOP, 9, (0, 0, 0))
    later = receipt(3, 21, ReceiptSource.POLICY, 12, (0.05, 0.02, -0.4))
    trailing = receipt(4, 22, ReceiptSource.SAFE_STOP, 10, (0, 0, 0))
    assert select(
        (valid_stream()[0], stop, later, trailing)
    ).receipt.source is ReceiptSource.SAFE_STOP
    assert select(
        (valid_stream()[0], stop, later, trailing), cutoff=21, now=22
    ).normalized_command == pytest.approx((0.2, 0.1, -0.5))


def test_stop_after_cutoff_preserves_snapshot():
    """Không đưa stop sau cutoff vào snapshot đã chọn."""
    policy = receipt(1, 10, ReceiptSource.POLICY, 11, (0.1, -0.1, 0.4))
    stop = receipt(2, 20, ReceiptSource.SAFE_STOP, 99, (0, 0, 0))
    result = select((policy, stop), cutoff=10, now=20)
    assert result.status is CutoffStatus.READY
    assert result.receipt == policy
    assert result.normalized_command == pytest.approx((0.4, -0.5, 0.5))


def test_invalid_context_and_receipt_order_reject():
    """Từ chối receipt mới nhất không hợp lệ thay vì fallback."""
    base = valid_stream()
    assert select(
        (base[0], replace(base[1], final_publisher_instance_id=91), base[2])
    ).status is CutoffStatus.REJECTED
    assert select(
        (base[0], replace(base[1], publish_stamp_ns=5), base[2])
    ).status is CutoffStatus.REJECTED
    assert select(
        (
            base[0],
            base[1],
            replace(base[1], final_command=(1.0, 0.0, 0.0)),
            base[2],
        )
    ).status is CutoffStatus.REJECTED
    assert select(
        (base[0], replace(base[1], admission_valid=False), base[2])
    ).status is CutoffStatus.REJECTED
    assert select(
        (base[0], replace(base[1], session_id='other-session'), base[2])
    ).status is CutoffStatus.REJECTED
    assert select(
        (base[0], replace(base[1], ingress_config_hash='b' * 64), base[2])
    ).status is CutoffStatus.REJECTED


def test_future_stamp_wrong_lifecycle_and_absent_issuance_reject():
    """Từ chối stamp tương lai, lifecycle sai và issuance còn thiếu."""
    base = valid_stream()
    assert select(
        (base[0], base[1], replace(base[2], publish_stamp_ns=50)),
        now=40,
    ).status is CutoffStatus.REJECTED
    assert select(
        (
            base[0],
            replace(base[1], lifecycle=EpisodeLifecycleIdentity(2, 3, 4)),
            base[2],
        )
    ).status is CutoffStatus.REJECTED
    assert select((base[1], base[2])).status is CutoffStatus.REJECTED
    wrong_source = (receipt(1, 10, ReceiptSource.NAV2, 11), base[1], base[2])
    assert select(wrong_source).status is CutoffStatus.REJECTED
    issued_after_cutoff = (
        receipt(1, 21, ReceiptSource.POLICY, 11),
        receipt(2, 30, ReceiptSource.SAFE_STOP, 2),
    )
    assert select(
        issued_after_cutoff, cutoff=20, now=30
    ).status is CutoffStatus.REJECTED


def test_publisher_restart_and_sequence_timestamp_rollback_reject():
    """Từ chối publisher restart và sequence/stamp rollback."""
    base = valid_stream()
    assert select(
        (base[0], replace(base[1], final_publisher_instance_id=91), base[2])
    ).status is CutoffStatus.REJECTED
    assert select(
        (
            base[0],
            replace(base[1], final_publish_sequence=3, publish_stamp_ns=15),
            base[2],
        )
    ).status is CutoffStatus.REJECTED


def test_command_outside_axis_envelope_rejects_without_clamp():
    """Từ chối payload ngoài envelope vật lý, không clamp."""
    bad = receipt(2, 20, ReceiptSource.SAFE_STOP, 2, (0.251, 0, 0))
    assert select(
        (valid_stream()[0], bad, valid_stream()[2])
    ).status is CutoffStatus.REJECTED


def test_receipt_admission_checks_context_age_and_payload():
    """Kiểm tra frame, receive age, barrier, source và payload dừng."""
    base = valid_stream()
    assert select(
        (base[0], replace(base[1], frame_id='map'), base[2])
    ).status is CutoffStatus.REJECTED
    assert select(
        (base[0], replace(base[1], received_steady_ns=0), base[2]),
        now=600000001,
    ).status is CutoffStatus.REJECTED
    assert select(
        (base[0], replace(base[1], source=ReceiptSource.NAV2), base[2])
    ).status is CutoffStatus.REJECTED
    assert select(
        (
            base[0],
            replace(base[1], final_command=(0.1, 0.0, 0.0)),
            base[2],
        )
    ).status is CutoffStatus.REJECTED
    assert select(base, cutoff=20, now=40).status is CutoffStatus.READY
    assert select(base, cutoff=20, now=40).cutoff_ros_ns == 20


def select_zero(
    items, cutoff=20, now=40, steady_now=None, barrier=0, binding=BINDING
):
    """Chạy selector reset-zero với thời điểm đánh giá tường minh."""
    return select_reset_zero_at_cutoff(
        tuple(items),
        binding=binding,
        cutoff_ros_ns=cutoff,
        evaluation_ros_now_ns=now,
        evaluation_steady_now_ns=now if steady_now is None else steady_now,
        reset_barrier_ros_ns=barrier,
        physical_scales=SCALES,
    )


def test_reset_zero_uses_real_stop_without_policy_issuance():
    """Nhận receipt dừng thực tế mà không cần POLICY issuance."""
    zero = receipt(1, 10, ReceiptSource.SAFE_STOP, 3)
    next_receipt = receipt(2, 21, ReceiptSource.SAFE_STOP, 4)
    selected = select_zero((next_receipt, zero))
    assert selected.status is CutoffStatus.READY
    assert (
        selected.receipt == zero
        and selected.normalized_command == (0, 0, 0)
    )


def test_reset_zero_nonzero_replacement_and_after_cutoff_do_not_rewrite():
    """Từ chối zero bị thay thế, giữ nguyên snapshot trước cutoff."""
    zero = receipt(1, 10, ReceiptSource.SAFE_STOP, 3)
    nonzero = receipt(2, 20, ReceiptSource.POLICY, 11, (0.1, 0, 0))
    assert select_zero(
        (zero, nonzero), cutoff=20
    ).status is CutoffStatus.REJECTED
    later = receipt(2, 21, ReceiptSource.SAFE_STOP, 4)
    selected = select_zero((zero, later), cutoff=20)
    assert selected.status is CutoffStatus.READY and selected.receipt == zero


def test_reset_zero_equal_stamp_uses_sequence_and_requires_adjacent_boundary():
    """Dùng sequence để phân xử stamp bằng nhau và yêu cầu receipt kề."""
    first = receipt(1, 20, ReceiptSource.SAFE_STOP, 3)
    second = receipt(2, 20, ReceiptSource.POLICY, 11, (0.1, 0, 0))
    third = receipt(3, 21, ReceiptSource.SAFE_STOP, 4)
    assert select_zero(
        (third, second, first), cutoff=20
    ).status is CutoffStatus.REJECTED
    assert select_zero((first,)).status is CutoffStatus.PENDING


def test_reset_zero_rejects_stale_barrier_and_stream_identity():
    """Từ chối barrier cũ và receipt thuộc session khác."""
    zero = receipt(1, 10, ReceiptSource.SAFE_STOP, 3)
    next_receipt = receipt(2, 21, ReceiptSource.SAFE_STOP, 4)
    assert select_zero(
        (zero, next_receipt), barrier=10
    ).status is CutoffStatus.REJECTED
    wrong_session = replace(zero, session_id='other')
    assert select_zero(
        (wrong_session, next_receipt)
    ).status is CutoffStatus.REJECTED


def test_reset_zero_rejects_ages_future_and_wrong_binding():
    """Reject reset receipts that fail dual-clock or stream admission."""
    zero = receipt(1, 10, ReceiptSource.SAFE_STOP, 3)
    next_receipt = receipt(
        2, 21, ReceiptSource.POLICY, 11, (0.1, 0.0, 0.0)
    )
    ros_stale = select_zero(
        (zero, next_receipt), now=500000011, steady_now=40
    )
    assert ros_stale.status is CutoffStatus.REJECTED
    receive_stale = replace(zero, received_steady_ns=0)
    steady_result = select_zero(
        (receive_stale, next_receipt), now=40, steady_now=500000001
    )
    assert steady_result.status is CutoffStatus.REJECTED
    future = replace(next_receipt, publish_stamp_ns=41)
    assert select_zero((zero, future), now=40).status is CutoffStatus.REJECTED
    wrong_config = replace(BINDING, config_hash='b' * 64)
    assert select_zero(
        (zero, next_receipt), binding=wrong_config
    ).status is CutoffStatus.REJECTED
    wrong_publisher = replace(zero, final_publisher_instance_id=91)
    assert select_zero(
        (wrong_publisher, next_receipt)
    ).status is CutoffStatus.REJECTED
    wrong_lifecycle = replace(
        next_receipt, lifecycle=EpisodeLifecycleIdentity(2, 3, 4)
    )
    assert select_zero(
        (zero, wrong_lifecycle)
    ).status is CutoffStatus.REJECTED
    with pytest.raises(ValueError):
        replace(zero, received_steady_ns=-1)


def test_reset_zero_rejects_duplicate_rollback_and_latest_policy():
    """Reject conflicting sequence reuse, rollback and nonzero latest."""
    zero = receipt(1, 10, ReceiptSource.SAFE_STOP, 3)
    next_receipt = receipt(
        2, 21, ReceiptSource.POLICY, 11, (0.1, 0.0, 0.0)
    )
    assert select_zero((zero, zero, next_receipt)).status is CutoffStatus.READY
    changed_duplicate = replace(zero, final_command=(0.1, 0.0, 0.0))
    assert select_zero(
        (zero, changed_duplicate, next_receipt)
    ).status is CutoffStatus.REJECTED
    rollback = replace(next_receipt, publish_stamp_ns=9)
    later = receipt(3, 22, ReceiptSource.SAFE_STOP, 4)
    assert select_zero(
        (zero, rollback, later)
    ).status is CutoffStatus.REJECTED
    latest_policy = receipt(
        2, 20, ReceiptSource.POLICY, 11, (0.1, 0.0, 0.0)
    )
    later_stop = receipt(3, 21, ReceiptSource.SAFE_STOP, 4)
    assert select_zero(
        (zero, latest_policy, later_stop), cutoff=20
    ).status is CutoffStatus.REJECTED
    nonzero_stop = receipt(
        1, 10, ReceiptSource.SAFE_STOP, 3, (0.1, 0.0, 0.0)
    )
    assert select_zero(
        (nonzero_stop, next_receipt)
    ).status is CutoffStatus.REJECTED
