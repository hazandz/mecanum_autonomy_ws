from dataclasses import fields
import numpy as np
import pytest
from mecanum_nav_rl.core.lifecycle_types import EpisodeLifecycleIdentity
from mecanum_nav_rl.observations.local_training_reference import LocalTrainingGoal, NoisyOdometryContext, build_local_training_reference
from mecanum_nav_rl.simulation.simulated_odometry import SimulatedOdometryMeasurement, SimulatedOdometrySnapshot, SimulatedOdometryStatus

def context(x=0.0, y=0.0, yaw=0.0, stamp=100, seq=4,
    status=SimulatedOdometryStatus.VALID):
    measurement = SimulatedOdometryMeasurement(x, y, yaw, 0.1, -0.2,
        0.3) if status is SimulatedOdometryStatus.VALID else None
    snapshot = SimulatedOdometrySnapshot(stamp, status, seq, measurement)
    return NoisyOdometryContext(snapshot, EpisodeLifecycleIdentity(1, 2, 3),
        'scenario-frame', 'scenario-A', 10)

def ref(goal, odom, scan_stamp=100, scan_seq=4, ros_now=100, steady_now=10):
    return build_local_training_reference(goal, odom,
        evaluation_ros_now_ns=ros_now, evaluation_steady_now_ns=steady_now, scan_timestamp_ns=scan_stamp, scan_sequence=scan_seq)

def goal(x, y):
    return LocalTrainingGoal(x, y, 'scenario-frame', 'scenario-A')

@pytest.mark.parametrize('g,odom,expected', [((2, 0), (0, 0, 0), (0.2, 0, 1)),
    ((-2, 0), (0, 0, 0), (0.2, 0, -1)), ((0, 2), (0, 0, 0), (0.2, 1, 0)), ((2,
    0), (0, 0, np.pi / 2), (0.2, -1, 0))])

def test_body_frame_forward_reverse_lateral_and_yaw(g, odom, expected):
    result = ref(goal(*g), context(*odom))
    assert result.ready
    np.testing.assert_allclose(result.features, expected, atol=1e-06)

def test_zero_distance_scale_cap_dtype_order_and_exact_identity():
    zero = ref(goal(0, 0), context())
    assert zero.features == (np.float32(0), np.float32(0), np.float32(1))
    ten = ref(goal(10, 0), context())
    over = ref(goal(100, 0), context())
    assert ten.features[0] == over.features[0] == np.float32(1)
    assert all((type(x) is np.float32 for x in ten.features))
    assert zero.timestamp_ns == 100 and zero.sequence == 4
    assert zero.lifecycle == EpisodeLifecycleIdentity(1, 2, 3)
    assert zero.scenario_identity == 'scenario-A' and zero.frame_id == 'base_link'

@pytest.mark.parametrize('status', [SimulatedOdometryStatus.DELAYED,
    SimulatedOdometryStatus.DROPPED])

def test_delayed_and_dropped_inputs_reject(status):
    assert not ref(goal(1, 0), context(status=status)).ready

def test_stale_future_skew_and_sequence_mismatch_reject():
    assert not ref(goal(1, 0), context(stamp=100), ros_now=400000101).ready
    assert not ref(goal(1, 0), context(stamp=101), ros_now=100).ready
    assert not ref(goal(1, 0), context(), scan_stamp=99).ready
    assert not ref(goal(1, 0), context(), scan_seq=5).ready
    assert not ref(goal(1, 0), context(), steady_now=300000011).ready

def test_scenario_frame_and_identity_are_exact_and_no_ground_truth_field_exists():
    assert not ref(LocalTrainingGoal(1, 0, 'alias', 'scenario-A'),
        context()).ready
    assert not ref(LocalTrainingGoal(1, 0, 'scenario-frame', 'scenario-B'),
        context()).ready
    names = {field.name for field in fields(NoisyOdometryContext)}
    assert not any(('ground_truth' in name or name in {'gt',
        'oracle_pose'} for name in names))
