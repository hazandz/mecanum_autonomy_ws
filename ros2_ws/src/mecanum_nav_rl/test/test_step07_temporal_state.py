from copy import deepcopy

import pytest

from mecanum_nav_rl.observations.step07_temporal_state import (
    AttemptContext,
    Run005TemporalAttempt,
)


CTX = AttemptContext("goal:intent-1", "a" * 64, "warehouse_map2", "b" * 64, 1, 2, 3, 4)


def attempt():
    return Run005TemporalAttempt(steady_deadline_ns=1000, max_odom_age_ns=250)


def test_zero_clock_does_not_pin_or_send_and_steady_deadline_still_expires():
    state = attempt()
    assert state.consume_trigger(valid=True, ros_ns=0, steady_ns=10, context=CTX) == "WAIT_VALID_ROS_CLOCK"
    assert state.t_a_ns is None and not state.planner_sent
    assert state.consume_trigger(valid=True, ros_ns=10, steady_ns=1000, context=CTX) == "CAMPAIGN_STEADY_DEADLINE_EXPIRED"


def test_fixed_ta_late_tf_sends_planner_once_with_send_time_stamp():
    state = attempt()
    assert state.consume_trigger(valid=True, ros_ns=100, steady_ns=10, context=CTX) == "PINNED"
    assert state.poll_prerequisite_tf(available=False, ros_ns=200, steady_ns=20, context=CTX) == "TF_QUERY_PENDING"
    assert state.t_a_ns == 100
    assert state.poll_prerequisite_tf(available=True, ros_ns=300, steady_ns=30, context=CTX) == "SEND_PLANNER_ONCE"
    state.mark_planner_sent("compute-uuid", 300)
    assert state.planner_send_ns == 300
    assert state.poll_prerequisite_tf(available=True, ros_ns=400, steady_ns=40, context=CTX) == "PLANNER_ALREADY_SENT"


def test_context_change_before_planner_is_terminal():
    state = attempt()
    state.consume_trigger(valid=True, ros_ns=100, steady_ns=10, context=CTX)
    changed = AttemptContext("goal:intent-1", "a" * 64, "warehouse_map2", "b" * 64, 1, 2, 3, 5)
    assert state.poll_prerequisite_tf(available=True, ros_ns=101, steady_ns=11, context=changed) == "ATTEMPT_CONTEXT_CHANGED_BEFORE_PLANNER"
    assert not state.planner_sent


def test_matched_successful_path_only_and_immutable_copy_identity():
    state = attempt()
    state.consume_trigger(valid=True, ros_ns=100, steady_ns=10, context=CTX)
    state.mark_planner_sent("req-1", 101)
    poses = ({"x": 1}, {"x": 2})
    with pytest.raises(ValueError, match="PATH_RESULT_IDENTITY"):
        state.admit_path(request_uuid="old", result_status="SUCCEEDED", frame_id="map", poses=poses,
                         receipt_steady_ns=20, campaign_deadline_ns=900, context=CTX)
    path = state.admit_path(request_uuid="req-1", result_status="SUCCEEDED", frame_id="map", poses=poses,
                            receipt_steady_ns=20, campaign_deadline_ns=900, context=CTX)
    assert path.path_sequence == 1 and path.expiry_steady_ns == 900 and path.poses is not poses


def test_single_pending_snapshot_rejects_second_capture_without_replacement():
    state = attempt()
    state.consume_trigger(valid=True, ros_ns=100, steady_ns=10, context=CTX)
    payload = {"receipt": [1, 2], "odom": 7}
    pending = state.acquire_snapshot(t_vector_ns=200, t_tf_ns=150, steady_ns=20,
        measurement_identity=(1, 2, 3), context=CTX, input_stamps_ns=(150, 170),
        correlation_records=("odom:150", "receipt:170"), payload=payload,
        input_age_limits_ns=(250, 500))
    before = deepcopy(pending)
    with pytest.raises(ValueError, match="PENDING_SNAPSHOT_EXISTS"):
        state.acquire_snapshot(t_vector_ns=210, t_tf_ns=180, steady_ns=21,
            measurement_identity=(4, 5, 6), context=CTX, input_stamps_ns=(180,),
            correlation_records=("odom:180",), payload={"latest": True})
    assert state.pending == before


def test_rollback_clears_pending_and_clock_increase_cannot_resurrect():
    state = attempt()
    state.consume_trigger(valid=True, ros_ns=100, steady_ns=10, context=CTX)
    state.acquire_snapshot(t_vector_ns=200, t_tf_ns=150, steady_ns=20,
        measurement_identity=(1,), context=CTX, input_stamps_ns=(150,),
        correlation_records=("odom:150",), payload=b"p")
    assert state.observe_time(99, 30) is False
    assert state.pending is None and state.terminal_failure == "ROS_CLOCK_ROLLBACK"
    assert state.observe_time(201, 31) is False
    assert state.t_a_ns == 100 and state.pending is None


def _pending(state, *, identity=(1,), t_vector=200, t_tf=150, stamps=(150,), limits=None):
    state.consume_trigger(valid=True, ros_ns=100, steady_ns=10, context=CTX)
    return state.acquire_snapshot(t_vector_ns=t_vector, t_tf_ns=t_tf, steady_ns=20,
        measurement_identity=identity, context=CTX, input_stamps_ns=stamps,
        correlation_records=("exact",), payload={"immutable": True},
        input_age_limits_ns=limits or tuple(250 for _ in stamps))


def test_future_input_and_wrong_tf_odom_stamp_rejected():
    state = attempt()
    state.consume_trigger(valid=True, ros_ns=100, steady_ns=10, context=CTX)
    with pytest.raises(ValueError, match="CUTOFF"):
        state.acquire_snapshot(t_vector_ns=200, t_tf_ns=150, steady_ns=21,
            measurement_identity=(2,), context=CTX, input_stamps_ns=(150, 201),
            correlation_records=("future",), payload={})
    with pytest.raises(ValueError, match="TF_ODOMETRY"):
        state.acquire_snapshot(t_vector_ns=200, t_tf_ns=149, steady_ns=21,
            measurement_identity=(2,), context=CTX, input_stamps_ns=(150,),
            correlation_records=("wrong",), payload={})


def test_commit_rechecks_freshness_deadline_and_context():
    state = attempt(); _pending(state, limits=(1000,))
    with pytest.raises(ValueError, match="STALE_AT_COMMIT"):
        state.commit_snapshot(ros_ns=401, steady_ns=30, context=CTX, lookup_succeeded=True)
    state = attempt(); _pending(state)
    with pytest.raises(ValueError, match="DEADLINE"):
        state.commit_snapshot(ros_ns=201, steady_ns=1000, context=CTX, lookup_succeeded=True)
    state = attempt(); _pending(state)
    changed = AttemptContext("goal:intent-1", "a" * 64, "warehouse_map2", "b" * 64, 1, 2, 3, 5)
    with pytest.raises(ValueError, match="CONTEXT_CHANGED"):
        state.commit_snapshot(ros_ns=201, steady_ns=30, context=changed, lookup_succeeded=True)


def test_lookup_exception_preserves_cause_and_never_commits():
    state = attempt(); _pending(state)
    with pytest.raises(ValueError, match="TF_LOOKUP_EXCEPTION:ExtrapolationException"):
        state.commit_snapshot(ros_ns=201, steady_ns=30, context=CTX,
                              lookup_succeeded=True, lookup_exception="ExtrapolationException")
    assert state.pending is not None


def test_same_measurement_cannot_become_new_under_new_cutoff():
    state = attempt(); _pending(state, identity=("scan1", "odom1", "receipt1", "life1"))
    state.commit_snapshot(ros_ns=201, steady_ns=30, context=CTX, lookup_succeeded=True)
    with pytest.raises(ValueError, match="MEASUREMENT_IDENTITY_DUPLICATE"):
        state.acquire_snapshot(t_vector_ns=202, t_tf_ns=151, steady_ns=31,
            measurement_identity=("scan1", "odom1", "receipt1", "life1"), context=CTX,
            input_stamps_ns=(151,), correlation_records=("same",), payload={})
