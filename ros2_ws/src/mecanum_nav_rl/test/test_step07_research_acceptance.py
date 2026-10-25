from __future__ import annotations

import math

import numpy as np
import pytest

from mecanum_nav_rl.observations.step07_research_acceptance import (
    BoundedFacts, Context, PathSnapshot, StampedFact, evaluate_a1_a10,
    ClockRollbackGuard, lidar_sectors, localization_health, make_observation,
    mission_settled, normalized_twist, project_lookahead,
    select_actual_receipt, select_scan_odom_pair,
)


CTX = Context(7, 2, 4, "a" * 64)


def fact(stamp, value=None, *, receive=1_000_000_000, frame="base_link", identity=()):
    return StampedFact(stamp, receive, frame, value, CTX, identity)


def test_observation_is_float32_81_ordered_and_read_only_including_vy_and_receipt():
    ranges = [2.0] * 360
    vector = make_observation(ranges, scan_angle_min=-math.pi,
        scan_angle_increment=2*math.pi/360, scan_range_min=0.1, scan_range_max=10.0,
        scan_frame="lidar_frame", reference_features=(0.4, 0.6, 0.8),
        measured_twist=(0.1, -0.1, 0.4), previous_final_command=(0.2, -0.2, 0.8),
        twist_scales=(0.25, 0.20, 0.80), context=CTX)
    assert vector.shape == (81,) and vector.dtype == np.float32 and not vector.flags.writeable
    assert tuple(vector[72:75]) == pytest.approx((0.4, 0.6, 0.8))
    assert tuple(vector[75:78]) == pytest.approx((0.4, -0.5, 0.5))
    assert tuple(vector[78:81]) == pytest.approx((0.8, -1.0, 1.0))


@pytest.mark.parametrize("bad", [float("nan"), -float("inf")])
def test_lidar_rejects_required_invalid_ranges(bad):
    ranges = [1.0] * 360
    ranges[0] = bad
    with pytest.raises(ValueError, match="invalid required range"):
        lidar_sectors(ranges, angle_min=-math.pi, angle_increment=2*math.pi/360,
                      range_min=0.1, range_max=10.0, frame_id="lidar_frame")


def test_lidar_accepts_positive_infinity_no_return_with_valid_metadata():
    ranges = [2.0] * 360
    ranges[0] = float("inf")
    result = lidar_sectors(ranges, angle_min=-math.pi, angle_increment=2*math.pi/360,
                           range_min=0.1, range_max=10.0, frame_id="lidar_frame")
    assert len(result) == 72 and all(0 <= x <= 1 for x in result)


def test_lidar_maps_out_of_range_positive_returns_to_no_return():
    ranges = [2.0] * 360
    ranges[0] = 11.0
    result = lidar_sectors(ranges, angle_min=-math.pi, angle_increment=2*math.pi/360,
                           range_min=0.1, range_max=10.0, frame_id="lidar_frame")
    assert len(result) == 72 and all(0 <= x <= 1 for x in result)


def test_lidar_rejects_silent_frame_alias_and_missing_sector():
    with pytest.raises(ValueError, match="frame/geometry"):
        lidar_sectors([1.0] * 360, angle_min=-math.pi, angle_increment=0.01,
                      range_min=0.1, range_max=10.0, frame_id="scan")
    with pytest.raises(ValueError, match="at least one valid beam"):
        lidar_sectors([1.0] * 72, angle_min=0, angle_increment=0.01,
                      range_min=0.1, range_max=10.0, frame_id="lidar_frame")


def test_twist_rejects_outside_envelope_without_clipping():
    assert normalized_twist(0.25, 0.2, 0.8, scales=(0.25, 0.2, 0.8)) == (1.0, 1.0, 1.0)
    with pytest.raises(ValueError, match="outside validity"):
        normalized_twist(0.25001, 0.0, 0.0, scales=(0.25, 0.2, 0.8))


def test_pair_selection_requires_new_after_barriers_cutoff_freshness_context_and_skew():
    scans = [fact(1_000_000_000), fact(1_100_000_000), fact(2_000_000_000)]
    odoms = [fact(1_040_000_000), fact(1_200_000_000), fact(1_300_000_000)]
    used = set()
    pair = select_scan_odom_pair(scans, odoms, cutoff_ns=1_500_000_000,
        now_steady_ns=1_200_000_000, scan_freshness_ns=500_000_000,
        odom_freshness_ns=250_000_000, sync_tolerance_ns=50_000_000,
        scan_barrier_ns=1_000_000_000, odom_barrier_ns=1_000_000_000,
        context=CTX, used_pairs=used)
    assert pair is None  # every eligible scan is at/before the strict barrier
    scans.append(fact(1_250_000_000, receive=1_200_000_000))
    pair = select_scan_odom_pair(scans, odoms, cutoff_ns=1_500_000_000,
        now_steady_ns=1_200_000_000, scan_freshness_ns=500_000_000,
        odom_freshness_ns=250_000_000, sync_tolerance_ns=50_000_000,
        scan_barrier_ns=1_000_000_000, odom_barrier_ns=1_000_000_000,
        context=CTX, used_pairs=used)
    assert pair and pair[0].stamp_ns == 1_250_000_000
    repeated_scan_pair = select_scan_odom_pair(scans, odoms, cutoff_ns=1_500_000_000,
        now_steady_ns=1_200_000_000, scan_freshness_ns=500_000_000,
        odom_freshness_ns=250_000_000, sync_tolerance_ns=50_000_000,
        scan_barrier_ns=1_000_000_000, odom_barrier_ns=1_000_000_000,
        context=CTX, used_pairs=used)
    assert repeated_scan_pair is not None
    assert (repeated_scan_pair[0].stamp_ns, repeated_scan_pair[1].stamp_ns) != (
        pair[0].stamp_ns, pair[1].stamp_ns)


def test_pair_rejects_stale_future_context_and_skew():
    other = Context(8, 2, 4, "a" * 64)
    scans = [fact(1_100_000_000), fact(1_200_000_000, receive=100_000_000),
             StampedFact(1_300_000_000, 1_000_000_000, "lidar_frame", None, other)]
    odoms = [fact(1_200_000_000)]
    assert select_scan_odom_pair(scans, odoms, cutoff_ns=1_150_000_000,
        now_steady_ns=1_000_000_000, scan_freshness_ns=10_000_000,
        odom_freshness_ns=10_000_000, sync_tolerance_ns=1,
        scan_barrier_ns=0, odom_barrier_ns=0, context=CTX, used_pairs=set()) is None


def test_bounded_facts_orders_deduplicates_and_evicts():
    stream = BoundedFacts(2)
    assert stream.insert(fact(3, identity=(3,)))
    assert stream.insert(fact(1, identity=(1,)))
    assert not stream.insert(fact(1, identity=(1,)))
    assert stream.insert(fact(2, identity=(2,)))
    assert [item.stamp_ns for item in stream._facts] == [2, 3]


def test_clock_rollback_clears_inputs_and_permanently_fails_attempt():
    stream = BoundedFacts(4)
    stream.insert(fact(10, identity=(10,)))
    guard = ClockRollbackGuard((stream.clear,))
    assert guard.observe(20)
    assert guard.observe(19) is False
    assert guard.failed and stream._facts == []
    assert guard.observe(30) is False
    assert ClockRollbackGuard().observe(0) is False


def test_actual_receipt_requires_real_identity_source_barrier_cutoff_and_freshness():
    receipt = fact(120, {"command": (0.1, -0.1, 0.2), "sequence": 8, "source": 2},
                   receive=100, identity=(8,))
    assert select_actual_receipt([receipt], cutoff_ns=121, now_steady_ns=130,
        freshness_ns=40, after_barrier_ns=110, context=CTX) == receipt
    assert select_actual_receipt([receipt], cutoff_ns=119, now_steady_ns=130,
        freshness_ns=40, after_barrier_ns=110, context=CTX) is None
    assert select_actual_receipt([receipt], cutoff_ns=121, now_steady_ns=130,
        freshness_ns=40, after_barrier_ns=120, context=CTX) is None
    assert select_actual_receipt([fact(120, {"command": (0.,0.,0.), "sequence": 0, "source": 2})],
        cutoff_ns=121, now_steady_ns=130, freshness_ns=40, after_barrier_ns=110,
        context=CTX) is None


def test_lookahead_is_arc_length_projected_and_immutable():
    path = PathSnapshot(((0.0, 0.0), (1.0, 0.0), (2.0, 0.0)), "r1", (2, 0),
                        "map-a", "b"*64, CTX, 0, 10_000_000_000)
    progress, distance, bearing = project_lookahead(path, robot_xy=(0.2, 0.1),
        previous_arc_m=None, now_steady_ns=2)
    assert progress == pytest.approx(0.2)
    assert distance == pytest.approx(math.hypot(0.5, 0.1)/5.0)
    assert bearing == pytest.approx(math.atan2(-0.1, 0.5))
    with pytest.raises(ValueError, match="deviated"):
        project_lookahead(path, robot_xy=(0.2, 1.0), previous_arc_m=None, now_steady_ns=2)
    with pytest.raises(ValueError, match="expired"):
        project_lookahead(path, robot_xy=(0.2, 0), previous_arc_m=None, now_steady_ns=10_000_000_001)


def test_lookahead_window_prevents_unbounded_branch_jump():
    path = PathSnapshot(((0.,0.),(1.,0.),(1.,1.),(2.,1.)), "r", (2.,1.),
                        "map", "b"*64, CTX, 0, 100)
    with pytest.raises(ValueError, match="bounded search"):
        project_lookahead(path, robot_xy=(2.,1.), previous_arc_m=0.1, now_steady_ns=1,
                          forward_window_m=0.2)


def test_localization_health_checks_covariance_freshness_and_jumps():
    good = {"stamp_ns": 1_000_000_000, "received_steady_ns": 1_000_000_000,
            "frame_id": "map", "pose": (0.,0.,0.), "covariance": (0.2,0.2,0.2)}
    assert localization_health([good], now_ros_ns=1_100_000_000,
                                max_age_ns=2_000_000_000, now_steady_ns=1_100_000_000) == (True, None)
    bad = {**good, "stamp_ns": 1_500_000_000, "pose": (1.,0.,0.)}
    assert localization_health([good, bad], now_ros_ns=1_600_000_000,
        max_age_ns=2_000_000_000, now_steady_ns=1_100_000_000)[1] == "LOCALIZATION_TRANSLATION_JUMP"
    assert localization_health([{**good, "covariance": (0.26,0.1,0.1)}], now_ros_ns=1_100_000_000,
        max_age_ns=2_000_000_000, now_steady_ns=1_100_000_000)[1] == "LOCALIZATION_VALUE_OR_COVARIANCE_INVALID"


def test_mission_settle_requires_continuous_ros_time_and_fresh_health():
    samples = [{"stamp_ns": 1_000_000_000, "settle_start_ros_ns": 1_000_000_000,
        "position_xy": (-4.01, 0), "twist": (0.01, 0.01, 0.01),
        "localization_valid": True, "fresh": True},
        {"stamp_ns": 2_000_000_000, "settle_start_ros_ns": 1_000_000_000,
        "position_xy": (-4.01, 0), "twist": (0.01, 0.01, 0.01),
        "localization_valid": True, "fresh": True}]
    assert mission_settled(samples, now_ros_ns=2_000_000_000)
    assert not mission_settled(samples, now_ros_ns=1_999_999_999)
    assert not mission_settled([samples[0], {**samples[1], "fresh": False}], now_ros_ns=2_000_000_000)
    assert not mission_settled([samples[0], {**samples[1], "twist": (0.0, 0.04, 0.0)}], now_ros_ns=2_000_000_000)


def test_a1_a10_fail_closed_and_keep_functional_vs_cleanup_facts_separate():
    report = evaluate_a1_a10({"A1": {"pass": True}, "A9": {"pass": False, "reason": "NO_RESULT"},
                              "A10": {"pass": True, "measured": {"completed": True}}})
    assert report["overall"] == "FAIL"
    assert report["acceptance"]["A2"]["reason"] == "NOT_EVALUATED_DUE_TO_MISSING_FACT"
    assert report["acceptance"]["A9"]["status"] == "FAIL"
    assert report["acceptance"]["A10"]["status"] == "PASS"


def test_a1_a10_success_requires_all_conditions_and_reports_only_first_five_vectors():
    facts = {f"A{index}": {"pass": True, "reason": f"CHECK_{index}_PASS"}
             for index in range(1, 11)}
    vectors = [{"vector": [float(index)] * 81} for index in range(7)]
    report = evaluate_a1_a10({**facts, "valid_observations": vectors})
    assert report["overall"] == "PASS"
    assert all(report["acceptance"][f"A{index}"]["status"] == "PASS"
               for index in range(1, 11))
    assert report["valid_observations"] == vectors[:5]
    changed = dict(facts)
    changed["A8"] = {"pass": False, "reason": "COMMAND_CHAIN_MISSING"}
    assert evaluate_a1_a10({**changed, "valid_observations": vectors})["overall"] == "FAIL"
