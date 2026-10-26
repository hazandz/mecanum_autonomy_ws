import math
from types import SimpleNamespace

import pytest

from mecanum_base_bridge.wheel_odometry import WheelOdometry


def packet(seq, ticks, boot=1, epoch=0, time_us=None):
    return SimpleNamespace(telemetry_sequence=seq, ticks_fl=ticks[0], ticks_fr=ticks[1],
        ticks_rl=ticks[2], ticks_rr=ticks[3], mcu_boot_id=boot, reset_epoch=epoch,
        mcu_monotonic_time_us=time_us if time_us is not None else seq * 100_000)


def odom():
    return WheelOdometry(.097, .216, .190, 937.2, (1, 1, 1, 1))


def test_forward_lateral_yaw_and_mixed_kinematics():
    scale = math.pi * .097 / 937.2
    forward = odom(); assert forward.update(packet(1, (0, 0, 0, 0)), 1_000_000_000) is None
    f = forward.update(packet(2, (100, 100, 100, 100)), 1_100_000_000)
    assert f.x == pytest.approx(100 * scale) and f.y == pytest.approx(0)
    lateral = odom(); lateral.update(packet(1, (0, 0, 0, 0)), 1_000_000_000)
    l = lateral.update(packet(2, (-100, 100, 100, -100)), 1_100_000_000)
    assert l.y == pytest.approx(100 * scale) and l.x == pytest.approx(0)
    yaw = odom(); yaw.update(packet(1, (0, 0, 0, 0)), 1_000_000_000)
    w = yaw.update(packet(2, (-100, 100, -100, 100)), 1_100_000_000)
    assert w.yaw == pytest.approx(100 * scale / .203)
    mixed = odom(); mixed.update(packet(1, (0, 0, 0, 0)), 1_000_000_000)
    m = mixed.update(packet(2, (0, 100, 100, 0)), 1_100_000_000)
    assert math.isfinite(m.x) and math.isfinite(m.y) and math.isfinite(m.yaw)
    assert all(math.isfinite(x) for x in m.pose_covariance + m.twist_covariance)
    assert m.pose_covariance[0] > 0 and m.twist_covariance[0] > 0


def test_signs_are_required_and_applied_once():
    with pytest.raises(ValueError, match='Dấu encoder'):
        WheelOdometry(.097, .216, .190, 937.2, (1, 1, None, 1))
    model = WheelOdometry(.097, .216, .190, 937.2, (-1, 1, 1, -1))
    model.update(packet(1, (0, 0, 0, 0)), 1_000_000_000)
    result = model.update(packet(2, (100, 100, 100, 100)), 1_100_000_000)
    assert result.y == pytest.approx(100 * math.pi * .097 / 937.2)


def test_discontinuity_baseline_and_coalesced_ros_stamps():
    model = odom()
    assert model.update(packet(10, (0, 0, 0, 0)), 1_000_000_000) is None
    assert model.update(packet(11, (100, 100, 100, 100)), 1_000_000_000) is not None
    assert model.update(packet(14, (200, 200, 200, 200)), 1_100_000_000) is None
    assert model.update(packet(15, (300, 300, 300, 300), boot=2), 1_200_000_000) is None
    assert model.update(packet(16, (400, 400, 400, 400), boot=2), 1_300_000_000) is not None
    assert model.update(packet(17, (500, 500, 500, 500), boot=2), 1_250_000_000) is None


def test_continuity_reset_and_invalid_stamp_do_not_bridge_gap():
    model = odom()
    model.update(packet(1, (0, 0, 0, 0)), 1_000_000_000)
    assert model.update(packet(2, (20, 20, 20, 20)), 1_100_000_000,
                        continuity_reset=True) is None
    assert model.update(packet(3, (40, 40, 40, 40)), 0) is None
    assert model.update(packet(4, (50, 50, 50, 50)), 1_200_000_000) is None


def test_large_int64_adjacent_difference_is_computed_before_float():
    model = odom()
    model.update(packet(1, (-(1 << 63) + 1,) * 4, time_us=1000), 1_000_000_000)
    result = model.update(packet(2, ((1 << 63) - 1,) * 4, time_us=1_001_000),
                          1_001_000_000)
    assert result is not None and math.isfinite(result.x)
