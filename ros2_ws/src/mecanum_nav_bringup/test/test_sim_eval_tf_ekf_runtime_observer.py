"""Offline synthetic tests for multisample clock/odometry/TF evidence."""

import importlib.util
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[4]
OBSERVER_PATH = ROOT / "ros2_ws/src/mecanum_nav_bringup/mecanum_nav_bringup/sim_eval_tf_ekf_runtime_observer.py"
SPEC = importlib.util.spec_from_file_location("wp06_6f_observer_test", OBSERVER_PATH)
observer = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = observer
SPEC.loader.exec_module(observer)


def _clock_samples(times=(10, 11, 12, 13, 14)):
    return [{"stamp": {"sec": value, "nanosec": 0}, "stamp_ns": value * 1_000_000_000} for value in times]


def _odom_sample(stamp, frame="odom", covariance=None):
    cov = [0.0] * 36 if covariance is None else covariance
    message = {
        "header": {"frame_id": frame, "stamp": {"sec": stamp, "nanosec": 0}},
        "child_frame_id": "base_link",
        "pose": {"pose": {"position": {"x": 0.0, "y": 0.0, "z": 0.0}, "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0}}, "covariance": list(cov)},
        "twist": {"twist": {"linear": {"x": 0.0, "y": 0.0, "z": 0.0}, "angular": {"x": 0.0, "y": 0.0, "z": 0.0}}, "covariance": [0.0] * 36},
    }
    return {"stamp_ns": stamp * 1_000_000_000, "message": message}


def _dynamic_tf(stamps=(10, 11, 12, 13, 14), gids=None):
    gids = gids or ["ekf-gid"] * len(stamps)
    return [{"parent": "odom", "child": "base_link", "stamp_ns": stamp * 1_000_000_000,
             "publisher_gid": gid, "translation": [0.0, 0.0, 0.0], "rotation_xyzw": [0.0, 0.0, 0.0, 1.0]}
            for stamp, gid in zip(stamps, gids)]


def _static_tf(translation=None, rotation=None):
    return [{"parent": "base_link", "child": "lidar_frame", "stamp_ns": 0, "publisher_gid": "rsp-gid",
             "translation": translation or [-0.031765, 0.0, 0.140],
             "rotation_xyzw": rotation or [0.0, 0.0, 0.0, 1.0]}]


def _observation(clock=None, filtered=None, dynamic=None, static=None, qos=None, window=True):
    return {
        "/clock": {"samples": _clock_samples() if clock is None else clock},
        "/odometry/filtered": {"samples": [_odom_sample(n) for n in range(10, 15)] if filtered is None else filtered},
        "/tf": {"transforms": _dynamic_tf() if dynamic is None else dynamic, "window_complete": window},
        "/tf_static": {"transforms": _static_tf() if static is None else static, "window_complete": window},
    }, observer.STATIC_QOS_CONTRACT if qos is None else qos


def test_clock_requires_five_nonzero_strict_timestamps():
    observations, qos = _observation()
    assert observer.evaluate_observations(observations, qos)["acceptance"]["clock_minimum_five_nonzero_strictly_increasing"] is True
    for values in ((10, 11, 11, 13, 14), (10, 12, 11, 13, 14), (0, 11, 12, 13, 14), (10, 11, 12, 13)):
        observations, qos = _observation(clock=_clock_samples(values))
        result = observer.evaluate_observations(observations, qos)
        assert result["acceptance"]["clock_minimum_five_nonzero_strictly_increasing"] is False
        assert "/clock" in result["failure_reason_literals"]


def test_filtered_odometry_requires_five_valid_monotonic_samples():
    observations, qos = _observation()
    assert observer.evaluate_observations(observations, qos)["acceptance"]["filtered_odometry_minimum_five_contract_and_monotonicity"] is True
    cases = [
        [_odom_sample(n, frame="map") for n in range(10, 15)],
        [_odom_sample(n, covariance=[0.0] * 35 + ["NaN"]) for n in range(10, 15)],
        [_odom_sample(n) for n in (10, 11, 11, 13, 14)],
        [_odom_sample(n) for n in range(10, 14)],
    ]
    for samples in cases:
        observations, qos = _observation(filtered=samples)
        result = observer.evaluate_observations(observations, qos)
        assert result["acceptance"]["filtered_odometry_minimum_five_contract_and_monotonicity"] is False
        assert "/odometry/filtered" in result["failure_reason_literals"]


def test_dynamic_tf_requires_five_samples_and_one_gid():
    observations, qos = _observation()
    assert observer.evaluate_observations(observations, qos)["acceptance"]["dynamic_odom_to_base_link_minimum_five_strictly_increasing_single_gid"] is True
    for records in (_dynamic_tf(gids=["a", "a", "b", "a", "a"]), _dynamic_tf(stamps=(10, 11, 11, 13, 14)), _dynamic_tf(stamps=(10, 11, 12, 13))):
        observations, qos = _observation(dynamic=records)
        result = observer.evaluate_observations(observations, qos)
        assert result["acceptance"]["dynamic_odom_to_base_link_minimum_five_strictly_increasing_single_gid"] is False
        assert "/tf:odom->base_link" in result["failure_reason_literals"]


def test_static_tf_requires_transient_local_qos_and_exact_transform():
    observations, qos = _observation()
    assert observer.evaluate_observations(observations, qos)["acceptance"]["static_base_link_to_lidar_frame_qos_and_transform_exact"] is True
    wrong_qos = dict(qos, durability="VOLATILE")
    wrong_translation = _static_tf(translation=[0.0, 0.0, 0.0])
    wrong_rotation = _static_tf(rotation=[0.0, 0.0, 1.0, 0.0])
    for records, profile in ((_static_tf(), wrong_qos), (wrong_translation, qos), (wrong_rotation, qos), ([], qos)):
        observations, _ = _observation(static=records)
        result = observer.evaluate_observations(observations, profile)
        assert result["acceptance"]["static_base_link_to_lidar_frame_qos_and_transform_exact"] is False
        assert "/tf_static:base_link->lidar_frame" in result["failure_reason_literals"]


def test_map_to_odom_and_observation_timeouts_fail_closed():
    observations, qos = _observation()
    observations["/tf"]["transforms"].append({"parent": "map", "child": "odom", "stamp_ns": 15, "publisher_gid": "amcl"})
    result = observer.evaluate_observations(observations, qos)
    assert result["acceptance"]["map_to_odom_absent_during_observation_window"] is False
    assert result["failure_reason_literals"]["map->odom"] == "MAP_TO_ODOM_EDGE_OBSERVED"

    observations, qos = _observation(window=False)
    result = observer.evaluate_observations(observations, qos)
    assert result["acceptance"]["map_to_odom_absent_during_observation_window"] is False
    assert result["failure_reason_literals"]["map->odom"] == "TF_OBSERVATION_WINDOW_INCOMPLETE"

    observations, qos = _observation(clock=[] , filtered=[], dynamic=[], static=[])
    observations["/clock"]["timeout_reason"] = "CLOCK_TIMEOUT_NO_SAMPLE"
    observations["/odometry/filtered"]["timeout_reason"] = "FILTERED_ODOMETRY_TIMEOUT_MINIMUM_FIVE_SAMPLES"
    observations["/tf"]["timeout_reason"] = "TF_DYNAMIC_ODOM_BASE_LINK_TIMEOUT_MINIMUM_FIVE_EDGES"
    observations["/tf_static"]["timeout_reason"] = "TF_STATIC_BASE_LINK_LIDAR_FRAME_TIMEOUT"
    result = observer.evaluate_observations(observations, qos)
    assert result["failure_reason_literals"] == {
        "/clock": "CLOCK_TIMEOUT_NO_SAMPLE",
        "/odometry/filtered": "FILTERED_ODOMETRY_TIMEOUT_MINIMUM_FIVE_SAMPLES",
        "/tf:odom->base_link": "TF_DYNAMIC_ODOM_BASE_LINK_TIMEOUT_MINIMUM_FIVE_EDGES",
        "/tf_static:base_link->lidar_frame": "TF_STATIC_BASE_LINK_LIDAR_FRAME_TIMEOUT",
    }


def test_observer_errors_fail_closed():
    observations, qos = _observation()
    result = observer.evaluate_observations(observations, qos, ["/tf_MESSAGE_INFO_OR_PARSE_FAILED"])
    assert result["acceptance"]["observer_errors_absent"] is False
    assert result["failure_reason_literals"]["observer_errors_absent"] == "RUNTIME_OBSERVER_CALLBACK_OR_API_ERROR"


def test_runtime_acceptance_matrix_covers_all_required_criteria():
    required = {
        "bootstrap_readiness", "bootstrap_stability_20_seconds", "composite_liveness",
        "clock_five_monotonic_samples", "wheel_input", "imu_input", "filtered_odometry_five_monotonic_samples",
        "dynamic_tf_edge_gid", "static_tf_edge_qos", "map_to_odom_absent",
        "forbidden_bridge_and_process_boundary", "process_group_teardown",
    }
    matrix = observer.RUNTIME_ACCEPTANCE_MATRIX
    assert {item["acceptance_id"] for item in matrix} >= required
    for item in matrix:
        assert all(item.get(key) for key in ("collector", "raw_artifact_path", "parser_or_validator", "pass_condition", "failure_reason_literal", "offline_test_name"))
