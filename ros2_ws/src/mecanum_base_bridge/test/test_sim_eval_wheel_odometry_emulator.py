from dataclasses import replace
from types import SimpleNamespace

import pytest

from mecanum_base_bridge.sim_eval_wheel_odometry_emulator import (
    JOINT_NAMES,
    TRACK_M,
    WHEELBASE_M,
    MAX_SOURCE_GAP_S,
    SimEvalWheelOdometryEmulator,
    WHEEL_RADIUS_M,
)


JOINTS = list(JOINT_NAMES.values())


def message(t, velocity=(1.0, 1.0, 1.0, 1.0), names=None):
    sec = int(t)
    nanosec = int(round((t - sec) * 1_000_000_000))
    return SimpleNamespace(
        header=SimpleNamespace(stamp=SimpleNamespace(sec=sec, nanosec=nanosec)),
        name=list(JOINTS if names is None else names),
        velocity=list(velocity),
    )


def primed():
    emulator = SimEvalWheelOdometryEmulator()
    assert emulator.process(message(1.0, (0.0, 0.0, 0.0, 0.0))) is None
    sample = emulator.process(message(1.1))
    assert sample is not None
    return emulator, sample


@pytest.mark.parametrize(
    "bad",
    [
        lambda: message(1.2, names=JOINTS[:-1]),
        lambda: message(1.2, names=[*JOINTS[:3], JOINTS[0]]),
        lambda: message(1.2, velocity=(1.0, 2.0, 3.0)),
        lambda: message(1.2, velocity=(1.0, float("nan"), 1.0, 1.0)),
        lambda: message(1.2, velocity=(1.0, float("inf"), 1.0, 1.0)),
        lambda: message(1.2, velocity=(1.0, True, 1.0, 1.0)),
        lambda: SimpleNamespace(header=message(1.2).header, name=iter(JOINTS), velocity=[1.0] * 4),
    ],
    ids=["missing-joint", "duplicate-joint", "length-mismatch", "nan", "inf", "bool-is-not-rate", "names-not-list-or-tuple"],
)
def test_malformed_forward_sample_breaks_interval_keeps_pose_and_requires_new_baseline(bad):
    emulator, accepted = primed()
    trusted = emulator.trusted_pose
    assert bad() and emulator.process(bad()) is None
    assert emulator.trusted_pose == trusted
    assert emulator._last_stamp_ns is None
    assert emulator.process(message(1.3, (2.0, 2.0, 2.0, 2.0))) is None
    recovered = emulator.process(message(1.4, (2.0, 2.0, 2.0, 2.0)))
    assert recovered is not None
    assert recovered.x > accepted.x
    assert recovered.x - accepted.x == pytest.approx(2.0 * WHEEL_RADIUS_M * 0.1)
    assert recovered.header_frame_id == "odom"
    assert recovered.child_frame_id == "base_link"
    assert recovered.publishes_tf is False


@pytest.mark.parametrize("bad_time", [1.1, 1.31])
def test_duplicate_or_long_gap_keeps_pose_and_clears_interval(bad_time):
    emulator, _ = primed()
    trusted = emulator.trusted_pose
    assert emulator.process(message(bad_time)) is None
    assert emulator.trusted_pose == trusted
    assert emulator._last_stamp_ns is None
    assert emulator.process(message(2.0)) is None
    assert emulator.process(message(2.1)) is not None


def test_valid_interval_after_bad_sample_does_not_integrate_since_pre_error_stamp():
    emulator, accepted = primed()
    saved = emulator.trusted_pose
    malformed = message(1.2)
    malformed.velocity[0] = float("nan")
    assert emulator.process(malformed) is None
    assert emulator.process(message(1.25)) is None
    sample = emulator.process(message(1.35))
    assert sample is not None
    assert sample.x - saved[0] == pytest.approx(WHEEL_RADIUS_M * 0.1)
    assert sample.x - accepted.x == pytest.approx(WHEEL_RADIUS_M * 0.1)


def test_timestamp_rollback_resets_pose_and_requires_new_baseline():
    emulator, _ = primed()
    assert emulator.trusted_pose[0] > 0.0
    assert emulator.process(message(0.9)) is None
    assert emulator.trusted_pose == (0.0, 0.0, 0.0)
    assert emulator._last_stamp_ns is None
    assert emulator.process(message(1.0)) is None
    assert emulator.process(message(1.1)) is not None


def test_invalid_stamp_and_nonfinite_kinematics_never_mutate_trusted_pose():
    emulator, _ = primed()
    trusted = emulator.trusted_pose
    invalid_stamp = message(1.2)
    invalid_stamp.header.stamp.nanosec = 1_000_000_000
    assert emulator.process(invalid_stamp) is None
    assert emulator.trusted_pose == trusted
    assert emulator.process(message(1.3, (0.0, 0.0, 0.0, 0.0))) is None
    huge = message(1.4, (1e308, 1e308, 1e308, 1e308))
    assert emulator.process(huge) is None
    assert emulator.trusted_pose == trusted
    assert emulator._last_stamp_ns is None


def test_correct_mecanum_components_reorder_and_covariance_without_tf():
    emulator = SimEvalWheelOdometryEmulator()
    reordered = [JOINTS[2], JOINTS[0], JOINTS[3], JOINTS[1]]
    # Equal wheel rates are a pure forward fixture; index order is irrelevant.
    assert emulator.process(message(1.0, (1.0,) * 4, reordered)) is None
    sample = emulator.process(message(1.1, (1.0,) * 4, reordered))
    assert sample.linear_x == pytest.approx(WHEEL_RADIUS_M)
    assert sample.linear_y == pytest.approx(0.0)
    assert sample.angular_z == pytest.approx(0.0)
    assert len(sample.pose_covariance) == len(sample.twist_covariance) == 36
    assert tuple(sample.pose_covariance[index * 6 + index] for index in range(6)) == (
        0.0025, 0.0025, 1000000.0, 1000000.0, 1000000.0, 0.007615435
    )
    assert tuple(sample.twist_covariance[index * 6 + index] for index in range(6)) == (
        0.01, 0.01, 1000000.0, 1000000.0, 1000000.0, 0.04
    )
    assert sample.publishes_tf is False


@pytest.mark.parametrize(
    "body_twist",
    [(0.2, 0.0, 0.0), (0.0, 0.15, 0.0), (0.0, 0.0, 0.4), (0.2, -0.1, 0.3)],
    ids=["forward", "lateral", "yaw", "combined"],
)
def test_mecanum_kinematics_match_forward_lateral_yaw_and_combined_twist(body_twist):
    vx, vy, wz = body_twist
    radius = WHEEL_RADIUS_M
    lever = WHEELBASE_M + TRACK_M
    wheel_rates = (
        (vx - vy - lever * wz) / radius,
        (vx + vy + lever * wz) / radius,
        (vx + vy - lever * wz) / radius,
        (vx - vy + lever * wz) / radius,
    )
    emulator = SimEvalWheelOdometryEmulator()
    assert emulator.process(message(1.0, wheel_rates)) is None
    output = emulator.process(message(1.1, wheel_rates))
    assert output.linear_x == pytest.approx(vx)
    assert output.linear_y == pytest.approx(vy)
    assert output.angular_z == pytest.approx(wz)
