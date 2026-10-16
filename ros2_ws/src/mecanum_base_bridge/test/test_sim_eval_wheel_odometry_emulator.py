import math
import unittest

import pytest

from mecanum_base_bridge.sim_eval_wheel_odometry_emulator import (
    JOINT_NAMES,
    MAX_SOURCE_GAP_S,
    POSE_COVARIANCE_DIAGONAL,
    TRACK_M,
    WHEELBASE_M,
    WHEEL_RADIUS_M,
    TWIST_COVARIANCE_DIAGONAL,
    WheelOdometryEmulator,
)


NAMES = [JOINT_NAMES[key] for key in ("FL", "FR", "RL", "RR")]
BASE = 1_000_000_000


def _sample_for_rates(rates, stamp=BASE + 20_000_000, names=NAMES):
    by_name = dict(zip(NAMES, rates))
    return WheelOdometryEmulator(), [by_name[name] for name in names], names, stamp


def _run(rates, names=NAMES):
    core = WheelOdometryEmulator()
    assert core.process(names, [0.0] * len(names), BASE) is None
    return core.process(names, rates, BASE + 20_000_000)


def test_forward_lateral_yaw_and_combined_mecanum_kinematics():
    forward = _run([1 / WHEEL_RADIUS_M] * 4)
    assert forward.linear_x == pytest.approx(1.0)
    assert forward.linear_y == pytest.approx(0.0)
    assert forward.angular_z == pytest.approx(0.0)

    lateral = _run([-1 / WHEEL_RADIUS_M, 1 / WHEEL_RADIUS_M, 1 / WHEEL_RADIUS_M, -1 / WHEEL_RADIUS_M])
    assert lateral.linear_x == pytest.approx(0.0)
    assert lateral.linear_y == pytest.approx(1.0)
    assert lateral.angular_z == pytest.approx(0.0)

    wheel_rate = (WHEELBASE_M + TRACK_M) / WHEEL_RADIUS_M
    yaw = _run([-wheel_rate, wheel_rate, -wheel_rate, wheel_rate])
    assert yaw.linear_x == pytest.approx(0.0)
    assert yaw.linear_y == pytest.approx(0.0)
    assert yaw.angular_z == pytest.approx(1.0)

    combined_rates = [1 / WHEEL_RADIUS_M - wheel_rate,
                      1 / WHEEL_RADIUS_M + wheel_rate,
                      1 / WHEEL_RADIUS_M - wheel_rate,
                      1 / WHEEL_RADIUS_M + wheel_rate]
    combined = _run(combined_rates)
    assert (combined.linear_x, combined.linear_y, combined.angular_z) == pytest.approx((1.0, 0.0, 1.0))


def test_joint_names_are_used_independent_of_array_order():
    ordered = _run([1 / WHEEL_RADIUS_M] * 4)
    reordered_names = [NAMES[2], NAMES[0], NAMES[3], NAMES[1]]
    reordered = _run([1 / WHEEL_RADIUS_M] * 4, reordered_names)
    assert reordered.linear_x == pytest.approx(ordered.linear_x)
    assert reordered.linear_y == pytest.approx(ordered.linear_y)


@pytest.mark.parametrize("names", [NAMES[:3], [*NAMES, NAMES[0]]])
def test_missing_or_duplicate_required_joint_is_rejected(names):
    core = WheelOdometryEmulator()
    assert core.process(NAMES, [0.0] * 4, BASE) is None
    assert core.process(names, [0.0] * len(names), BASE + 20_000_000) is None


def test_non_finite_velocity_is_rejected():
    core = WheelOdometryEmulator()
    core.process(NAMES, [0.0] * 4, BASE)
    assert core.process(NAMES, [0.0, 0.0, math.inf, 0.0], BASE + 20_000_000) is None


@pytest.mark.parametrize("bad_stamp", [BASE, BASE - 1])
def test_duplicate_or_out_of_order_stamp_drops_and_resets_integrator(bad_stamp):
    core = WheelOdometryEmulator()
    core.process(NAMES, [0.0] * 4, BASE)
    assert core.process(NAMES, [1.0] * 4, BASE + 20_000_000)
    assert core.process(NAMES, [1.0] * 4, bad_stamp) is None
    assert core.pose == (0.0, 0.0, 0.0)
    assert core.process(NAMES, [1.0] * 4, BASE + 40_000_000) is None
    assert core.process(NAMES, [1.0] * 4, BASE + 60_000_000) is not None


def test_source_gap_over_limit_drops_and_resets_integrator():
    core = WheelOdometryEmulator()
    core.process(NAMES, [0.0] * 4, BASE)
    core.process(NAMES, [1.0] * 4, BASE + 20_000_000)
    assert core.process(NAMES, [1.0] * 4, BASE + 20_000_000 + int(MAX_SOURCE_GAP_S * 1e9) + 1) is None
    assert core.pose == (0.0, 0.0, 0.0)


def test_covariances_are_finite_diagonal_and_core_does_not_create_tf():
    sample = _run([1 / WHEEL_RADIUS_M] * 4)
    assert len(sample.pose_covariance) == len(sample.twist_covariance) == 36
    assert all(math.isfinite(value) for value in sample.pose_covariance + sample.twist_covariance)
    assert tuple(sample.pose_covariance[index * 6 + index] for index in range(6)) == POSE_COVARIANCE_DIAGONAL
    assert tuple(sample.twist_covariance[index * 6 + index] for index in range(6)) == TWIST_COVARIANCE_DIAGONAL
    assert not hasattr(sample, "tf")


class ColconWheelOdometryTests(unittest.TestCase):
    """Expose wheel-core checks to ament_python's unittest runner."""

    def test_kinematics(self):
        test_forward_lateral_yaw_and_combined_mecanum_kinematics()

    def test_joint_reordering(self):
        test_joint_names_are_used_independent_of_array_order()

    def test_missing_and_duplicate_names(self):
        for names in (NAMES[:3], [*NAMES, NAMES[0]]):
            test_missing_or_duplicate_required_joint_is_rejected(names)

    def test_nonfinite_velocity(self):
        test_non_finite_velocity_is_rejected()

    def test_timestamp_barriers(self):
        for stamp in (BASE, BASE - 1):
            test_duplicate_or_out_of_order_stamp_drops_and_resets_integrator(stamp)
        test_source_gap_over_limit_drops_and_resets_integrator()

    def test_covariance_and_tf_boundary(self):
        test_covariances_are_finite_diagonal_and_core_does_not_create_tf()
