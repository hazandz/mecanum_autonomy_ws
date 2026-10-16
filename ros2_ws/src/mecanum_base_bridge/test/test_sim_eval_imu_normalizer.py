from types import SimpleNamespace

import pytest

from mecanum_base_bridge.sim_eval_imu_normalizer import (
    IMU_ANGULAR_VELOCITY_COVARIANCE_DIAGONAL,
    IMU_LINEAR_ACCELERATION_COVARIANCE_DIAGONAL,
    IMU_ORIENTATION_COVARIANCE_DIAGONAL,
    SimEvalImuNormalizer,
)


def imu(t=1.0, frame="base_link", q=(0.0, 0.0, 0.0, 1.0), angular=(1.0, 2.0, 3.0), accel=(4.0, 5.0, 6.0)):
    sec = int(t)
    ns = int(round((t - sec) * 1_000_000_000))
    return SimpleNamespace(
        header=SimpleNamespace(frame_id=frame, stamp=SimpleNamespace(sec=sec, nanosec=ns)),
        orientation=SimpleNamespace(x=q[0], y=q[1], z=q[2], w=q[3]),
        angular_velocity=SimpleNamespace(x=angular[0], y=angular[1], z=angular[2]),
        linear_acceleration=SimpleNamespace(x=accel[0], y=accel[1], z=accel[2]),
    )


def test_accepts_valid_imu_preserves_stamp_values_and_sets_explicit_covariance():
    normalizer = SimEvalImuNormalizer()
    source = imu(3.25)
    result = normalizer.process(source)
    assert (result.stamp_sec, result.stamp_nanosec) == (3, 250_000_000)
    assert result.orientation_xyzw == (0.0, 0.0, 0.0, 1.0)
    assert result.angular_velocity_xyz == (1.0, 2.0, 3.0)
    assert result.linear_acceleration_xyz == (4.0, 5.0, 6.0)
    assert result.header_frame_id == "base_link"
    assert result.publishes_tf is False
    assert tuple(result.orientation_covariance[::4]) == IMU_ORIENTATION_COVARIANCE_DIAGONAL
    assert tuple(result.angular_velocity_covariance[::4]) == IMU_ANGULAR_VELOCITY_COVARIANCE_DIAGONAL
    assert tuple(result.linear_acceleration_covariance[::4]) == IMU_LINEAR_ACCELERATION_COVARIANCE_DIAGONAL


@pytest.mark.parametrize(
    "sample",
    [
        imu(frame="imu_link"),
        imu(q=(0.0, 0.0, 0.0, 0.5)),
        imu(q=(float("nan"), 0.0, 0.0, 1.0)),
        imu(angular=(0.0, float("inf"), 0.0)),
        imu(accel=(0.0, 0.0, float("nan"))),
        SimpleNamespace(
            header=SimpleNamespace(frame_id="base_link", stamp=SimpleNamespace(sec=2_147_483_648, nanosec=0)),
            orientation=SimpleNamespace(x=0.0, y=0.0, z=0.0, w=1.0),
            angular_velocity=SimpleNamespace(x=0.0, y=0.0, z=0.0),
            linear_acceleration=SimpleNamespace(x=0.0, y=0.0, z=0.0),
        ),
    ],
)
def test_drops_wrong_frame_quaternion_or_nonfinite(sample):
    assert SimEvalImuNormalizer().process(sample) is None


def test_duplicate_or_rollback_stamp_is_dropped_without_republishing_old_sample():
    normalizer = SimEvalImuNormalizer()
    assert normalizer.process(imu(2.0)) is not None
    assert normalizer.process(imu(2.0)) is None
    assert normalizer.process(imu(1.9)) is None
    assert normalizer.process(imu(2.1)) is not None
