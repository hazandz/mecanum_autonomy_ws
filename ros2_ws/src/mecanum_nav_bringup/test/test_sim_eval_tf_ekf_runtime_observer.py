"""Synthetic offline contract tests for the C++ rclcpp MessageInfo observer JSON."""

import importlib.util
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[4]
OBSERVER_PATH = ROOT / "ros2_ws/src/mecanum_nav_bringup/mecanum_nav_bringup/sim_eval_tf_ekf_runtime_observer.py"
SPEC = importlib.util.spec_from_file_location("wp06_6f_offline_observer", OBSERVER_PATH)
observer = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = observer
SPEC.loader.exec_module(observer)


def _message(stamp):
    v = {"x": 0.0, "y": 0.0, "z": 0.0}
    return {"header": {"frame_id": "odom", "stamp": {"sec": stamp, "nanosec": 0}},
            "child_frame_id": "base_link",
            "pose": {"covariance": [0.0] * 36, "pose": {"position": v, "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0}}},
            "twist": {"covariance": [0.0] * 36, "twist": {"linear": v, "angular": v}}}


def _doc():
    times = list(range(1, 6))
    gid = "001122aabbcc"
    endpoints = [{"gid": gid, "node_name": "ekf_filter_node", "node_namespace": "/", "topic_type": "tf2_msgs/msg/TFMessage"}]
    static_gid = "ffeedd"
    static_endpoint = {"gid": static_gid, "node_name": "robot_state_publisher", "node_namespace": "/", "topic_type": "tf2_msgs/msg/TFMessage"}
    return {"schema": observer.OBSERVER_SCHEMA, "expected_ekf_node_name": "ekf_filter_node", "window_complete": True,
            "terminal_outcome": "PASS",
            "observer_errors": [], "graph_endpoint_snapshot": {"/tf": endpoints, "/tf_static": [static_endpoint]},
            "expected_static_tf_node_name": "robot_state_publisher",
            "observed_forbidden_edges": [],
            "endpoint_mapping": [{"gid": gid, "match_count": 1, "unique": True, "expected_owner": True,
                                  "mapped_endpoint": {"node_name": "ekf_filter_node", "node_namespace": "/", "topic_type": "tf2_msgs/msg/TFMessage"}}],
            "static_endpoint_mapping": [{"gid": static_gid, "match_count": 1, "unique": True, "expected_owner": True,
                                          "mapped_endpoint": {"node_name": "robot_state_publisher", "node_namespace": "/", "topic_type": "tf2_msgs/msg/TFMessage"}}],
            "qos_used": {
                "/tf": dict(observer.EXPECTED_DYNAMIC_TF_QOS),
                "/tf_static": dict(observer.EXPECTED_STATIC_TF_QOS),
            },
            "topics": {
                "/clock": {"type": "rosgraph_msgs/msg/Clock", "samples": [{"stamp": {"sec": n, "nanosec": 0}, "stamp_ns": n * 10**9, "valid": True} for n in times]},
                "/odometry/filtered": {"type": "nav_msgs/msg/Odometry", "samples": [{"message": _message(n), "stamp_ns": n * 10**9, "valid": True} for n in times]},
                "/tf": {"type": "tf2_msgs/msg/TFMessage", "window_complete": True, "transforms": [{"parent": "odom", "child": "base_link", "stamp_ns": n * 10**9, "publisher_gid": gid, "translation": [0.0, 0.0, 0.0], "rotation_xyzw": [0.0, 0.0, 0.0, 1.0], "valid": True} for n in times]},
                "/tf_static": {"type": "tf2_msgs/msg/TFMessage", "window_complete": True, "transforms": [{"parent": "base_link", "child": "lidar_frame", "stamp_ns": 0, "publisher_gid": static_gid, "translation": list(observer.EXPECTED_TRANSLATION), "rotation_xyzw": list(observer.EXPECTED_ROTATION), "valid": True}]}} ,
            "acceptance": {key: True for key in observer.EXPECTED_ACCEPTANCE_KEYS}, "failure_reason_literals": {}}


def _validate(document):
    return observer.validate_observer_document(document)["acceptance"]


def test_clock_five_increasing_pass_and_zero_duplicate_decreasing_fail():
    doc = _doc()
    assert _validate(doc)["clock_minimum_five_nonzero_strictly_increasing"]
    for values in ([0, 2, 3, 4, 5], [1, 2, 2, 4, 5], [1, 3, 2, 4, 5]):
        bad = _doc()
        bad["topics"]["/clock"]["samples"] = [{"stamp": {"sec": n, "nanosec": 0}, "valid": True} for n in values]
        with pytest.raises(observer.ObserverDocumentError, match="ACCEPTANCE_DOES_NOT_MATCH"):
            _validate(bad)


def test_filtered_odometry_rejects_bad_frame_covariance_or_time():
    assert _validate(_doc())["filtered_odometry_minimum_five_contract_and_monotonicity"]
    for mutate in (
        lambda d: d["topics"]["/odometry/filtered"]["samples"][0]["message"]["header"].update(frame_id="map"),
        lambda d: d["topics"]["/odometry/filtered"]["samples"][0]["message"]["pose"]["covariance"].__setitem__(0, float("nan")),
        lambda d: d["topics"]["/odometry/filtered"]["samples"][1]["message"]["header"].update(stamp={"sec": 1, "nanosec": 0}),
    ):
        bad = _doc(); mutate(bad)
        with pytest.raises(observer.ObserverDocumentError): _validate(bad)


def test_dynamic_tf_requires_five_edges_one_gid_and_exact_endpoint_owner():
    assert _validate(_doc())["dynamic_odom_to_base_link_minimum_five_strictly_increasing_single_gid_owned_by_ekf"]
    bad = _doc(); bad["topics"]["/tf"]["transforms"][0]["publisher_gid"] = "other"
    bad["endpoint_mapping"].append({"gid": "other", "match_count": 1, "unique": True, "expected_owner": True})
    bad["graph_endpoint_snapshot"]["/tf"].append({"gid": "other", "node_name": "ekf_filter_node"})
    with pytest.raises(observer.ObserverDocumentError): _validate(bad)
    bad = _doc(); bad["graph_endpoint_snapshot"] = []
    with pytest.raises(observer.ObserverDocumentError): _validate(bad)


def test_static_tf_requires_transform_qos_and_exact_rsp_gid_owner():
    result = _validate(_doc())
    assert result["static_base_link_to_lidar_frame_exact"]
    assert result["static_tf_edge_publisher_gid_unique_mapped"]
    assert result["static_tf_owner_is_robot_state_publisher"]
    assert result["static_tf_subscription_qos_contract"]
    for mutate in (
        lambda d: d["qos_used"]["/tf_static"].update(durability="VOLATILE"),
        lambda d: d["topics"]["/tf_static"]["transforms"][0].update(translation=[0, 0, 0]),
        lambda d: d["topics"]["/tf_static"]["transforms"].clear(),
        lambda d: d["topics"]["/tf_static"]["transforms"].append(dict(d["topics"]["/tf_static"]["transforms"][0])),
        lambda d: d["graph_endpoint_snapshot"]["/tf_static"][0].update(node_name="other_node"),
        lambda d: d["graph_endpoint_snapshot"]["/tf_static"].clear(),
        lambda d: d["static_endpoint_mapping"][0].update(unique=False, match_count=2),
    ):
        bad = _doc(); mutate(bad)
        with pytest.raises(observer.ObserverDocumentError): _validate(bad)


def test_static_owner_failures_have_exact_fail_closed_literals():
    cases = (
        ("TF_STATIC_EDGE_PUBLISHER_GID_UNMAPPABLE", False, False, False, lambda d: (d["graph_endpoint_snapshot"]["/tf_static"].clear(), d["static_endpoint_mapping"].clear())),
        ("TF_STATIC_EDGE_PUBLISHER_GID_NOT_UNIQUE", True, False, False, lambda d: (d["graph_endpoint_snapshot"]["/tf_static"].append(dict(d["graph_endpoint_snapshot"]["/tf_static"][0])), d["static_endpoint_mapping"][0].update(unique=False, match_count=2))),
        ("TF_STATIC_EDGE_PUBLISHER_NOT_ROBOT_STATE_PUBLISHER", True, True, False, lambda d: (d["graph_endpoint_snapshot"]["/tf_static"][0].update(node_name="other_node"), d["static_endpoint_mapping"][0].update(expected_owner=False, mapped_endpoint={"node_name": "other_node", "node_namespace": "/", "topic_type": "tf2_msgs/msg/TFMessage"}))),
    )
    for literal, mappable, unique, owner, mutate in cases:
        bad = _doc(); mutate(bad)
        bad["acceptance"]["static_tf_edge_publisher_gid_mappable"] = mappable
        bad["acceptance"]["static_tf_edge_publisher_gid_unique_mapped"] = unique
        bad["acceptance"]["static_tf_owner_is_robot_state_publisher"] = owner
        bad["failure_reason_literals"]["/tf_static:base_link->lidar_frame"] = literal
        bad["terminal_outcome"] = "FAIL_NO_RETRY"
        result = observer.validate_observer_document(bad)
        assert result["failure_reason_literals"]["/tf_static:base_link->lidar_frame"] == literal
        assert not result["all_pass"]


def test_schema_v2_and_missing_static_ownership_are_rejected():
    old = _doc(); old["schema"] = "wp06_6f_cpp_runtime_observer/v2"
    with pytest.raises(observer.ObserverDocumentError, match="OBSERVER_SCHEMA_MISMATCH"):
        _validate(old)
    missing = _doc(); missing.pop("static_endpoint_mapping")
    with pytest.raises(observer.ObserverDocumentError, match="OBSERVER_GRAPH_MAPPING_MISSING"):
        _validate(missing)


def test_dynamic_tf_qos_is_best_effort_volatile_and_static_qos_is_reliable_transient_local():
    assert _validate(_doc())["dynamic_tf_subscription_qos_contract"]
    for mutate in (
        lambda d: d["qos_used"]["/tf"].update(reliability="RELIABLE"),
        lambda d: d["qos_used"]["/tf"].update(durability="TRANSIENT_LOCAL"),
        lambda d: d["qos_used"]["/tf_static"].update(reliability="BEST_EFFORT"),
        lambda d: d["qos_used"]["/tf_static"].update(durability="VOLATILE"),
        lambda d: d["qos_used"]["/tf"].update(depth=99),
    ):
        bad = _doc()
        mutate(bad)
        with pytest.raises(observer.ObserverDocumentError, match="OBSERVER_QOS_CONTRACT_MISMATCH"):
            _validate(bad)


def test_json_reader_rejects_reliable_or_transient_local_dynamic_tf_qos(tmp_path):
    for field, value in (("reliability", "RELIABLE"), ("durability", "TRANSIENT_LOCAL")):
        document = _doc()
        document["qos_used"]["/tf"][field] = value
        path = tmp_path / f"invalid-{field}.json"
        path.write_bytes(json.dumps(document, sort_keys=True, separators=(",", ":")).encode("utf-8"))
        with pytest.raises(observer.ObserverDocumentError, match="OBSERVER_QOS_CONTRACT_MISMATCH:/tf"):
            observer.load_observer_json(path)


def test_map_to_odom_and_incomplete_window_fail():
    bad = _doc(); bad["observed_forbidden_edges"].append({"parent": "map", "child": "odom", "topic": "/tf"})
    with pytest.raises(observer.ObserverDocumentError): _validate(bad)
    bad = _doc(); bad["window_complete"] = False
    with pytest.raises(observer.ObserverDocumentError): _validate(bad)


def test_per_topic_timeout_reason_literals_are_required_for_failed_observations():
    cases = [
        ("/clock", "clock_minimum_five_nonzero_strictly_increasing", lambda d: d["topics"]["/clock"].update(samples=[]), "CLOCK_TIMEOUT_MINIMUM_FIVE_SAMPLES"),
        ("/odometry/filtered", "filtered_odometry_minimum_five_contract_and_monotonicity", lambda d: d["topics"]["/odometry/filtered"].update(samples=[]), "FILTERED_ODOMETRY_TIMEOUT_MINIMUM_FIVE_SAMPLES"),
        ("/tf:odom->base_link", "dynamic_odom_to_base_link_minimum_five_strictly_increasing_single_gid_owned_by_ekf", lambda d: d["topics"]["/tf"].update(transforms=[]), "TF_DYNAMIC_TIMEOUT_MINIMUM_FIVE_EDGES_OR_GIDS"),
        ("/tf_static:base_link->lidar_frame", "static_base_link_to_lidar_frame_exact", lambda d: d["topics"]["/tf_static"].update(transforms=[]), "TF_STATIC_EDGE_MISSING_OR_TRANSFORM_MISMATCH"),
    ]
    for reason_key, acceptance_key, mutate, reason in cases:
        bad = _doc(); mutate(bad)
        bad["acceptance"][acceptance_key] = False
        if acceptance_key == "static_base_link_to_lidar_frame_exact":
            bad["acceptance"]["static_tf_edge_publisher_gid_mappable"] = False
            bad["acceptance"]["static_tf_edge_publisher_gid_unique_mapped"] = False
            bad["acceptance"]["static_tf_owner_is_robot_state_publisher"] = False
        bad["failure_reason_literals"][reason_key] = reason
        bad["terminal_outcome"] = "FAIL_NO_RETRY"
        result = observer.validate_observer_document(bad)
        assert not result["acceptance"][acceptance_key]
        assert result["failure_reason_literals"][reason_key] == reason


def test_json_reader_rejects_duplicate_keys_and_noncanonical_bytes(tmp_path):
    path = tmp_path / "observer.json"
    path.write_bytes(b'{"a":1,"a":2}')
    with pytest.raises(observer.ObserverDocumentError, match="DUPLICATE_JSON_KEY"):
        observer.load_observer_json(path)
    path.write_bytes(json.dumps(_doc(), sort_keys=True, separators=(",", ":")).encode())
    assert observer.load_observer_json(path)["schema"] == observer.OBSERVER_SCHEMA


def test_observer_errors_are_a_structured_fail_closed_condition():
    bad = _doc()
    bad["observer_errors"] = ["TF_EDGE_PUBLISHER_GID_UNMAPPABLE"]
    bad["acceptance"]["observer_errors_absent"] = False
    bad["failure_reason_literals"]["observer_errors"] = "RUNTIME_OBSERVER_CALLBACK_OR_API_ERROR"
    bad["terminal_outcome"] = "FAIL_NO_RETRY"
    result = observer.validate_observer_document(bad)
    assert not result["acceptance"]["observer_errors_absent"]


def test_runner_invokes_cpp_observer_once_and_never_uses_python_collector_matrix():
    runner = (ROOT / "artifacts/simulation/sim_eval_scan_endpoint_probe_evidence/tools/run_wp06_6f_tf_ekf_session.py").read_text()
    assert runner.count("_run_cpp_observer(") == 2  # definition plus one call site
    assert "collect_and_write" not in runner
    assert "RUNTIME_ACCEPTANCE_MATRIX" not in runner
    py_sources = list((ROOT / "ros2_ws/src").rglob("*.py"))
    forbidden = "with_" + "info="
    assert all(forbidden not in path.read_text(encoding="utf-8") for path in py_sources)
