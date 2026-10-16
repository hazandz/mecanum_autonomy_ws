import math
import unittest

from mecanum_base_bridge.sim_eval_imu_normalizer import (
    ANGULAR_VELOCITY_COVARIANCE_DIAGONAL,
    IMU_FRAME_ID,
    LINEAR_ACCELERATION_COVARIANCE_DIAGONAL,
    ORIENTATION_COVARIANCE_DIAGONAL,
    ImuNormalizer,
)


def test_valid_imu_is_passed_without_changing_frame_stamp_or_values():
    normalizer = ImuNormalizer()
    accepted = normalizer.process(100, "base_link", (0.0, 0.0, 0.0, 1.0), (0.1, 0.2, 0.3), (1.0, 2.0, 3.0))
    assert accepted.stamp_ns == 100
    assert accepted.frame_id == IMU_FRAME_ID
    assert accepted.orientation_xyzw == (0.0, 0.0, 0.0, 1.0)
    assert accepted.angular_velocity_xyz == (0.1, 0.2, 0.3)
    assert accepted.linear_acceleration_xyz == (1.0, 2.0, 3.0)


def test_wrong_frame_invalid_quaternion_and_nonfinite_values_are_dropped():
    normalizer = ImuNormalizer()
    assert normalizer.process(100, "imu_link", (0, 0, 0, 1), (0, 0, 0), (0, 0, 0)) is None
    assert normalizer.process(100, "base_link", (0, 0, 0, 2), (0, 0, 0), (0, 0, 0)) is None
    assert normalizer.process(100, "base_link", (0, 0, math.nan, 1), (0, 0, 0), (0, 0, 0)) is None
    assert normalizer.process(100, "base_link", (0, 0, 0, 1), (0, math.inf, 0), (0, 0, 0)) is None
    assert normalizer.process(100, "base_link", (0, 0, 0, 1), (0, 0, 0), (0, 0, -math.inf)) is None


def test_duplicate_and_rollback_stamps_are_dropped_and_reset_order_guard():
    normalizer = ImuNormalizer()
    assert normalizer.process(100, "base_link", (0, 0, 0, 1), (0, 0, 0), (0, 0, 0))
    assert normalizer.process(100, "base_link", (0, 0, 0, 1), (0, 0, 0), (0, 0, 0)) is None
    assert normalizer.process(99, "base_link", (0, 0, 0, 1), (0, 0, 0), (0, 0, 0)) is None
    assert normalizer.process(101, "base_link", (0, 0, 0, 1), (0, 0, 0), (0, 0, 0))


def test_required_node_covariance_diagonals_are_exact():
    from mecanum_base_bridge.sim_eval_imu_normalizer import (
        ANGULAR_VELOCITY_COVARIANCE,
        LINEAR_ACCELERATION_COVARIANCE,
        ORIENTATION_COVARIANCE,
    )

    assert len(ORIENTATION_COVARIANCE) == 9
    assert tuple(ORIENTATION_COVARIANCE[i * 3 + i] for i in range(3)) == ORIENTATION_COVARIANCE_DIAGONAL
    assert tuple(ANGULAR_VELOCITY_COVARIANCE[i * 3 + i] for i in range(3)) == ANGULAR_VELOCITY_COVARIANCE_DIAGONAL
    assert tuple(LINEAR_ACCELERATION_COVARIANCE[i * 3 + i] for i in range(3)) == LINEAR_ACCELERATION_COVARIANCE_DIAGONAL


class ColconImuNormalizerTests(unittest.TestCase):
    """Expose pure IMU checks to ament_python's unittest runner."""

    def test_valid_passthrough(self):
        test_valid_imu_is_passed_without_changing_frame_stamp_or_values()

    def test_invalid_input_drop(self):
        test_wrong_frame_invalid_quaternion_and_nonfinite_values_are_dropped()

    def test_timestamp_order(self):
        test_duplicate_and_rollback_stamps_are_dropped_and_reset_order_guard()

    def test_covariance(self):
        test_required_node_covariance_diagonals_are_exact()
