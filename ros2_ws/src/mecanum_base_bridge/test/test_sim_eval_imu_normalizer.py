from types import SimpleNamespace as NS

from mecanum_base_bridge.sim_eval_imu_normalizer import SimEvalImuNormalizer


def imu(stamp_ns, frame="base_link", q=(0.0, 0.0, 0.0, 1.0), w=(0.1, 0.2, 0.3), a=(1.0, 2.0, 3.0)):
    sec, nanosec = divmod(stamp_ns, 1_000_000_000)
    return NS(header=NS(stamp=NS(sec=sec, nanosec=nanosec), frame_id=frame),
              orientation=NS(x=q[0], y=q[1], z=q[2], w=q[3]),
              angular_velocity=NS(x=w[0], y=w[1], z=w[2]),
              linear_acceleration=NS(x=a[0], y=a[1], z=a[2]))


def test_valid_imu_keeps_stamp_values_and_sets_exact_covariance():
    core = SimEvalImuNormalizer()
    sample = core.process(imu(1_000_000_001))
    assert sample.stamp_ns == 1_000_000_001
    assert sample.frame_id == "base_link"
    assert sample.orientation_xyzw == (0.0, 0.0, 0.0, 1.0)
    assert sample.angular_velocity_xyz == (0.1, 0.2, 0.3)
    assert sample.linear_acceleration_xyz == (1.0, 2.0, 3.0)
    assert sample.publishes_tf is False
    assert tuple(sample.orientation_covariance[i * 3 + i] for i in range(3)) == (1_000_000.0, 1_000_000.0, 0.007615435)
    assert tuple(sample.angular_velocity_covariance[i * 3 + i] for i in range(3)) == (1_000_000.0, 1_000_000.0, 0.01)
    assert tuple(sample.linear_acceleration_covariance[i * 3 + i] for i in range(3)) == (1_000_000.0,) * 3


def test_wrong_frame_invalid_quaternion_and_nonfinite_are_dropped():
    core = SimEvalImuNormalizer()
    assert core.process(imu(1_000_000_000, frame="imu_link")) is None
    assert core.process(imu(1_000_000_000, q=(0.0, 0.0, 0.0, 0.5))) is None
    assert core.process(imu(1_000_000_000, w=(float("nan"), 0.0, 0.0))) is None
    assert core.process(imu(1_000_000_000, a=(0.0, float("inf"), 0.0))) is None
    assert core.process(imu(1_000_000_000, q=(True, 0.0, 0.0, 1.0))) is None


def test_duplicate_or_rollback_stamp_is_dropped_without_rewinding_accepted_stamp():
    core = SimEvalImuNormalizer()
    assert core.process(imu(1_000_000_000)) is not None
    assert core.process(imu(1_000_000_000)) is None
    assert core.process(imu(1_100_000_000)) is not None
    assert core.process(imu(1_050_000_000)) is None
    assert core.process(imu(1_200_000_000)) is not None
