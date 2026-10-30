"""Pure exact timestamp and dual-clock port checks."""
from mecanum_nav_rl.simulation.local_training_io import (
    ExactTimestampPairer,
    NoisyOdometrySample,
    ScanSample,
    pair_exact,
    validate_dual_clock_freshness,
)

import pytest


def _scan(stamp=1_000_000_000):
    return ScanSample(stamp, 'lidar_frame', (1.0, 2.0))


def _odom(stamp=1_000_000_000, status='VALID', values=(0.1, 0.2, 0.3)):
    return NoisyOdometrySample(stamp, 1, status, 'base_link', values)


def test_exact_pair_requires_same_stamp_and_preserves_original_stamp():
    """Only identical timestamps form a pair, with their source stamp."""
    pair = pair_exact(_scan(), _odom())
    assert pair.stamp_ns == 1_000_000_000
    with pytest.raises(ValueError, match='mismatch'):
        pair_exact(_scan(), _odom(1_000_000_001))


def test_delayed_dropped_and_invalid_frame_have_no_fallback():
    """Non-ready or wrong-frame data has no substitute measurement."""
    with pytest.raises(ValueError, match='no current measurement'):
        pair_exact(_scan(), _odom(status='DELAYED', values=None))
    with pytest.raises(ValueError, match='frame'):
        pair_exact(
            _scan(),
            NoisyOdometrySample(
                1_000_000_000, 1, 'VALID', 'odom', (0, 0, 0),
            ),
        )


def test_pair_buffers_are_bounded_and_never_nearest_match():
    """Pair buffers stay bounded and do not use nearest timestamps."""
    pairer = ExactTimestampPairer(capacity=2)
    pairer.push(1, 'a')
    pairer.push(3, 'c')
    assert pairer.pop(2) is None
    with pytest.raises(OverflowError):
        pairer.push(4, 'd')


def test_ros_and_steady_age_each_enforce_their_own_budget():
    """ROS and steady age budgets reject independently."""
    validate_dual_clock_freshness(
        source_ros_ns=10, now_ros_ns=20, receive_steady_ns=100,
        now_steady_ns=110, max_age_ns=10,
    )
    with pytest.raises(ValueError, match='ROS or local steady'):
        validate_dual_clock_freshness(
            source_ros_ns=10, now_ros_ns=21, receive_steady_ns=100,
            now_steady_ns=110, max_age_ns=10,
        )
    with pytest.raises(ValueError, match='ROS or local steady'):
        validate_dual_clock_freshness(
            source_ros_ns=10, now_ros_ns=20, receive_steady_ns=100,
            now_steady_ns=111, max_age_ns=10,
        )
    with pytest.raises(ValueError, match='future'):
        validate_dual_clock_freshness(
            source_ros_ns=21, now_ros_ns=20, receive_steady_ns=100,
            now_steady_ns=110, max_age_ns=10,
        )
    with pytest.raises(ValueError, match='future'):
        validate_dual_clock_freshness(
            source_ros_ns=10, now_ros_ns=20, receive_steady_ns=111,
            now_steady_ns=110, max_age_ns=10,
        )
