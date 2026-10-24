import copy
import hashlib
import json
from pathlib import Path

import pytest

from step07_gate_b_evidence_validator import (
    QOS_PROFILE_SOURCE_PATHS, canonical_navigation_evidence_chain,
    build_navigation_evidence_chain, semantic_canonical_bytes,
    navigation_evidence_chain_failure,
    load_json, validate_gate_b_document, validate_observer,
    validate_run_directory, validate_run_record, validate_vector_samples,
)


def test_observer_json_duplicate_bom_nonstandard_and_bad_utf8_fail_closed(tmp_path):
    path = tmp_path / "x.json"
    for raw, literal in ((b'{"a":1,"a":2}', "DUPLICATE"), (b"\xef\xbb\xbf{}", "BOM"),
                         (b'{"x":NaN}', "NONSTANDARD"), (b"\xff", "JSON_PARSE")):
        path.write_bytes(raw)
        with pytest.raises(ValueError, match=literal):
            load_json(path)


def test_terminal_record_requires_run005_identity_acceptance_and_verified_final_teardown():
    passed = {"schema_version": "1.0", "run_id": "STEP07_NAV2_BASELINE_RUN_005",
              "call_counts": {"bootstrap": 1, "composite": 1},
              "action_server_readiness": {"status": "PASS", "attempted": True, "ready": True},
              "process_groups": {
                  "bootstrap": {"pid": 1001, "pgid": 1001,
                      "initial_snapshot": {"live_member_pids": [1001], "zombie_member_pids": []},
                      "readiness": {"ready": True, "entity_creation_literal": True}},
                  "composite": {"pid": 1002, "pgid": 1002,
                      "initial_snapshot": {"live_member_pids": [1002], "zombie_member_pids": []},
                      "readiness": {"ready": True},
                      "command": ["ros2", "launch", "mecanum_nav_bringup", "sim_eval_nav2_baseline_system.launch.py", "start_bootstrap:=false"]}},
              "acceptance": {"runtime": True, "bootstrap_composite_process_groups_distinct": True,
                             "bootstrap_readiness": True, "composite_readiness": True,
                             "process_group_teardown_clean": True,
                             "teardown_order_and_count_correct": True},
              "teardown": {"completed": True, "clean": True, "ordered": True,
                           "order_correct": True, "verified": True, "graceful": True,
                           "escalation_history": []},
              "failure_reason_literals": [],
              "terminal_outcome": "STEP07_NAV2_BASELINE_RUN005_PASS_PENDING_INDEPENDENT_EVIDENCE_AUDIT"}
    assert validate_run_record(passed)["pass"]
    bad_groups = copy.deepcopy(passed)
    bad_groups["process_groups"]["composite"]["pgid"] = 1001
    with pytest.raises(ValueError, match="PROCESS_GROUP_ACCEPTANCE_RAW_MISMATCH"):
        validate_run_record(bad_groups)
    inconsistent = copy.deepcopy(passed)
    inconsistent["terminal_outcome"] = "STEP07_NAV2_BASELINE_RUN005_FAIL_NO_RETRY_GUARD_CONSUMED"
    with pytest.raises(ValueError, match="TERMINAL_OUTCOME"):
        validate_run_record(inconsistent)


def _run005_record():
    return {"schema_version": "1.0", "run_id": "STEP07_NAV2_BASELINE_RUN_005",
            "call_counts": {"bootstrap": 1, "composite": 1},
            "action_server_readiness": {"status": "PASS", "attempted": True, "ready": True},
            "process_groups": {
                "bootstrap": {"pid": 1001, "pgid": 1001,
                    "initial_snapshot": {"live_member_pids": [1001], "zombie_member_pids": []},
                    "readiness": {"ready": True, "entity_creation_literal": True}},
                "composite": {"pid": 1002, "pgid": 1002,
                    "initial_snapshot": {"live_member_pids": [1002], "zombie_member_pids": []},
                    "readiness": {"ready": True},
                    "command": ["ros2", "launch", "mecanum_nav_bringup", "sim_eval_nav2_baseline_system.launch.py", "start_bootstrap:=false"]}},
            "acceptance": {"runtime": True, "bootstrap_composite_process_groups_distinct": True,
                           "bootstrap_readiness": True, "composite_readiness": True,
                           "process_group_teardown_clean": True,
                           "teardown_order_and_count_correct": True},
            "teardown": {"completed": True, "clean": True, "ordered": True,
                         "order_correct": True, "verified": True, "graceful": True,
                         "escalation_history": []},
            "failure_reason_literals": [],
            "terminal_outcome": "STEP07_NAV2_BASELINE_RUN005_PASS_PENDING_INDEPENDENT_EVIDENCE_AUDIT"}


def test_run001_identity_and_stale_run001_terminal_outcomes_are_rejected():
    record = _run005_record()
    record["run_id"] = "STEP07_NAV2_BASELINE_RUN_001"
    with pytest.raises(ValueError, match="RUN_RECORD_IDENTITY_INVALID"):
        validate_run_record(record)

    for stale in (
        "STEP07_NAV2_BASELINE_RUN001_PASS_PENDING_INDEPENDENT_EVIDENCE_AUDIT",
        "STEP07_NAV2_BASELINE_RUN001_FAIL_NO_RETRY_GUARD_CONSUMED",
    ):
        record = _run005_record()
        record["terminal_outcome"] = stale
        with pytest.raises(ValueError, match="TERMINAL_OUTCOME_ACCEPTANCE_RAW_MISMATCH|TERMINAL_OUTCOME_ACCEPTANCE_INCONSISTENCY"):
            validate_run_record(record)


def test_valid_run005_fail_record_is_accepted_as_a_fail_verdict():
    record = _run005_record()
    record["acceptance"]["runtime"] = False
    record["failure_reason_literals"] = ["SIMULATED_FAILURE"]
    record["terminal_outcome"] = "STEP07_NAV2_BASELINE_RUN005_FAIL_NO_RETRY_GUARD_CONSUMED"
    assert validate_run_record(record) == {
        "pass": False,
        "terminal_outcome": "STEP07_NAV2_BASELINE_RUN005_FAIL_NO_RETRY_GUARD_CONSUMED",
    }


def test_versioned_process_group_schema_requires_all_roles_and_child_group_proof():
    record = _run005_record()
    record["process_group_schema_version"] = "2.0"
    member_defaults = {"launcher_pid": None, "child_pid": None, "ownership_relation": "NOT_STARTED",
        "command": [], "returncode": None, "exit_code": None, "qos_observation": None,
        "qos_verdict": None, "shutdown_request": None, "terminal_state": "NOT_STARTED",
        "log_path": None, "final_snapshot": None, "ownership_verified": False,
        "ownership_errors": []}
    for name in ("bootstrap", "composite"):
        member = record["process_groups"][name]
        member.update({key: value for key, value in member_defaults.items() if key not in member})
        member["name"] = name
        member["launcher_pid"] = member["pid"]
        member["ownership_relation"] = "LAUNCHER_IS_PROCESS_GROUP_LEADER"
        member["ownership_verified"] = True
    assert record["process_groups"]["composite"]["command"] == [
        "ros2", "launch", "mecanum_nav_bringup",
        "sim_eval_nav2_baseline_system.launch.py", "start_bootstrap:=false"]
    for name in ("cpp_observer", "gate_b_observer"):
        record["process_groups"][name] = {**member_defaults, "name": name, "pid": None,
            "pgid": None, "readiness": None, "initial_snapshot": None}
    assert validate_run_record(record)["pass"] is True

    missing = copy.deepcopy(record)
    del missing["process_groups"]["cpp_observer"]
    with pytest.raises(ValueError, match="PROCESS_GROUP_SCHEMA_KEYS_INVALID"):
        validate_run_record(missing)

    unproven_child = copy.deepcopy(record)
    cpp = unproven_child["process_groups"]["cpp_observer"]
    cpp.update(pid=2001, launcher_pid=2001, pgid=2001, ownership_verified=True,
               child_pid=3001, ownership_relation="LAUNCHER_IS_PROCESS_GROUP_LEADER")
    with pytest.raises(ValueError, match="PROCESS_GROUP_CHILD_RELATION_INVALID:cpp_observer"):
        validate_run_record(unproven_child)


@pytest.mark.parametrize("mutation", [
    lambda record: record["teardown"].update(verified=False),
    lambda record: record["teardown"].update(graceful=False),
    lambda record: record["teardown"].pop("graceful"),
    lambda record: record["teardown"].update(escalation_history=[{"signal": "SIGTERM"}]),
    lambda record: record["failure_reason_literals"].append("SIGTERM"),
])
def test_claimed_run005_pass_with_unverified_teardown_or_failure_literal_is_rejected(mutation):
    record = _run005_record()
    mutation(record)
    with pytest.raises(ValueError, match="TERMINAL_OUTCOME_ACCEPTANCE_INCONSISTENCY"):
        validate_run_record(record)


def test_gate_b_vector_validation_requires_five_finite_monotonic_81_float32_samples():
    samples = [{"stamp_ns": i, "dimension": 81, "dtype": "float32", "values": [0.0] * 81} for i in range(1, 6)]
    assert validate_vector_samples(samples)
    samples[-1]["values"][0] = float("inf")
    assert not validate_vector_samples(samples)


def observer_doc():
    clock = [{"sec": 1, "nanosec": i} for i in range(1, 6)]
    odom = [{"frame_id": "odom", "child_frame_id": "base_link", "stamp_sec": 1,
             "stamp_nanosec": i, "pose_finite": True, "twist_finite": True,
             "pose_covariance_finite": True, "twist_covariance_finite": True,
             "pose_covariance_count": 36, "twist_covariance_count": 36} for i in range(1, 6)]
    tf = [{"parent": "odom", "child": "base_link", "stamp_sec": 1,
           "stamp_nanosec": i, "publisher_gid": "01"} for i in range(1, 6)]
    return {
        "schema_version": "1.0", "config_hash": "a" * 64,
        "clock": clock, "scan": [{"frame_id": "lidar_frame", "ranges_valid": True, "range_count": 1}],
        "wheel_odometry_raw": [{"frame_id": "odom", "child_frame_id": "base_link", "twist_finite": True}],
        "imu_data": [{"frame_id": "base_link", "quaternion_finite": True, "quaternion_norm": 1.0}],
        "filtered_odometry": odom, "tf": tf,
        "tf_static": [{"parent": "base_link", "child": "lidar_frame", "translation": [-0.031765, 0.0, 0.14], "rotation": [0.0, 0.0, 0.0, 1.0], "publisher_gid": "02"}],
        "lifecycle": [{"episode_generation": 1, "reset_epoch": 2, "runtime_generation": 3,
                        "primary_state": 2, "barrier_state": 1, "motion_permitted": True}],
        "receipt": [{"episode_generation": 1, "reset_epoch": 2, "runtime_generation": 3}],
        "safety_state": [], "qos_history_depth_observability": [
            {"topic": "/mecanum/safety_lifecycle_state", "node_name": name,
             "endpoint_type": direction, "history_depth_status": "OBSERVED_MATCH"}
            for name, direction in (("safety_lifecycle", "PUBLISHER"),
                ("safety_supervisor", "SUBSCRIPTION"), ("final_twist_publisher", "SUBSCRIPTION"),
                ("step07_nav2_baseline_runtime_observer", "SUBSCRIPTION"),
                ("step07_gate_b_observer", "SUBSCRIPTION"))] + [
            {"topic": "/mecanum/final_issued_command", "node_name": "final_twist_publisher",
             "endpoint_type": "PUBLISHER", "history_depth_status": "OBSERVED_MATCH"}],
        "gate_b_vectors": [], "map_to_odom": [{"parent": "map", "child": "odom", "stamp_sec": 1, "stamp_nanosec": 1, "publisher_gid": "04"}],
        "map_to_odom_gids": ["04"], "world_to_map": [],
        "dynamic_tf_gids": ["01"], "static_tf_gids": ["02"],
        "qos": {"/tf": {"history": "KEEP_LAST", "depth": 100, "reliability": "BEST_EFFORT", "durability": "VOLATILE"},
                "/tf_static": {"history": "KEEP_LAST", "depth": 1, "reliability": "RELIABLE", "durability": "TRANSIENT_LOCAL"},
                "/mecanum/safety_lifecycle_state": {"history": "KEEP_LAST", "depth": 10, "reliability": "RELIABLE", "durability": "VOLATILE"},
                "/mecanum/final_issued_command": {"history": "KEEP_LAST", "depth": 1, "reliability": "RELIABLE", "durability": "TRANSIENT_LOCAL"}},
        "graph": {"/tf": {"publishers": [
                      {"gid": "01", "node_name": "ekf_filter_node", "node_namespace": "/", "topic_type": "tf2_msgs/msg/TFMessage"},
                      {"gid": "04", "node_name": "amcl", "node_namespace": "/", "topic_type": "tf2_msgs/msg/TFMessage"}]},
                  "/tf_static": {"publishers": [{"gid": "02", "node_name": "robot_state_publisher", "node_namespace": "/", "topic_type": "tf2_msgs/msg/TFMessage"}]},
                  "/scan": {"publishers": [{"node_name": "sim_eval_scan_bridge", "node_namespace": "/", "topic_type": "sensor_msgs/msg/LaserScan"}]},
                  "/wheel/odometry_raw": {"publishers": [{"node_name": "sim_eval_wheel_imu_ingress", "node_namespace": "/", "topic_type": "nav_msgs/msg/Odometry"}]},
                  "/imu/data": {"publishers": [{"node_name": "sim_eval_wheel_imu_ingress", "node_namespace": "/", "topic_type": "sensor_msgs/msg/Imu"}]},
                  "/odometry/filtered": {"publishers": [{"node_name": "ekf_filter_node", "node_namespace": "/", "topic_type": "nav_msgs/msg/Odometry"}]},
                  "/map": {"publishers": [{"node_name": "map_server", "node_namespace": "/", "topic_type": "nav_msgs/msg/OccupancyGrid"}]},
                  "/mecanum/safety_lifecycle_state": {
                      "publishers": [{"node_name": "safety_lifecycle", "node_namespace": "/", "topic_type": "mecanum_nav_rl_interfaces/msg/SafetyLifecycleState", "endpoint_type": "PUBLISHER", "reliability": 1, "durability": 2, "history": 1, "depth": 10}],
                      "subscribers": [{"node_name": name, "node_namespace": "/", "topic_type": "mecanum_nav_rl_interfaces/msg/SafetyLifecycleState", "endpoint_type": "SUBSCRIPTION", "reliability": 1, "durability": 2, "history": 1, "depth": 10} for name in ("safety_supervisor", "final_twist_publisher", "step07_nav2_baseline_runtime_observer", "step07_gate_b_observer")]},
                  "/mecanum/safety/lifecycle_state": {"publishers": [], "subscribers": []},
                  "/mecanum/final_issued_command": {"publishers": [{"node_name": "final_twist_publisher", "node_namespace": "/", "topic_type": "mecanum_nav_rl_interfaces/msg/FinalIssuedCommandReceipt", "endpoint_type": "PUBLISHER", "reliability": 1, "durability": 1, "history": 1, "depth": 1}]},
                  "/cmd_vel": {"publishers": [{"gid": "03", "node_name": "final_twist_publisher", "node_namespace": "/", "topic_type": "geometry_msgs/msg/Twist"}],
                                "subscribers": [{"node_name": "sim_eval_cmd_vel_bridge"}]}},
        "cmd_vel_ownership": {"publisher_endpoints": [{"gid": "03", "node_name": "final_twist_publisher", "node_namespace": "/", "topic_type": "geometry_msgs/msg/Twist"}]},
        "forbidden_boundary": {"/odom": {"publishers": [], "subscribers": []}, "/ground_truth/odom": {"publishers": [], "subscribers": []}},
        "acceptance": {"clock_multisample": True, "filtered_odometry_multisample": True,
            "tf_qos_contract": True,
            "dynamic_tf_single_gid_and_ekf_owner": True, "static_transform_and_rsp_owner": True,
            "map_to_odom_single_amcl_owner": True, "world_to_map_absent": True, "forbidden_boundary_clear": True,
            "scan_publisher_owner": True, "wheel_publisher_owner": True, "imu_publisher_owner": True,
            "filtered_odometry_publisher_owner": True, "map_server_publisher_owner": True,
            "lifecycle_endpoint_qos_contract": True, "receipt_qos_contract": True,
            "obsolete_lifecycle_topic_absent": True, "receipt_publisher_owner": True,
            "cmd_vel_single_final_publisher": True, "cmd_vel_bridge_subscriber_only": True,
            "scan_valid_frame": True, "wheel_ingress_valid": True,
            "imu_ingress_valid": True, "lifecycle_ready_observed": True,
            "final_receipt_observed": True, "lifecycle_receipt_identity": True},
        "qos_verdict": {"lifecycle_endpoint_qos_contract": "PASS", "receipt_qos_contract": "PASS"},
        "errors": [],
    }


def _pinned_qos_evidence():
    return {"schema_version": "1.0", "runtime_checkout_head": "c" * 40,
            "runtime_checkout_origin": "https://github.com/hazandz/mecanum_autonomy_ws.git",
            "source_pins": {path: {"sha256": "a" * 64, "size_bytes": 10}
                            for path in QOS_PROFILE_SOURCE_PATHS},
            "installed_python_source_byte_equality": {
                path: True for path in QOS_PROFILE_SOURCE_PATHS if path.endswith(".py")},
            "installed_observer_binary": {"sha256": "b" * 64, "size_bytes": 100,
                "source_sha256": "a" * 64, "source_size_bytes": 10}}


def _mark_qos_unknown(document):
    life = document["graph"]["/mecanum/safety_lifecycle_state"]
    for row in life["publishers"] + life["subscribers"]:
        row["history"], row["depth"] = 3, 0
    rec = document["graph"]["/mecanum/final_issued_command"]["publishers"][0]
    rec["history"], rec["depth"] = 3, 0
    document["qos_history_depth_observability"] = [
        {"topic": "/mecanum/safety_lifecycle_state", "node_name": row["node_name"],
         "endpoint_type": row["endpoint_type"], "history_depth_status": "UNOBSERVABLE"}
        for row in life["publishers"] + life["subscribers"]]
    document["qos_history_depth_observability"].append(
        {"topic": "/mecanum/final_issued_command", "node_name": "final_twist_publisher",
         "endpoint_type": "PUBLISHER", "history_depth_status": "UNOBSERVABLE"})
    document["acceptance"]["lifecycle_endpoint_qos_contract"] = False
    document["acceptance"]["receipt_qos_contract"] = False
    document["qos_verdict"] = {"lifecycle_endpoint_qos_contract": "UNOBSERVABLE",
                               "receipt_qos_contract": "UNOBSERVABLE"}
    document["errors"] = []


def _duplicate_rejecting_json(path):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"duplicate key: {key}")
            result[key] = value
        return result

    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=pairs)


def test_governance_acceptance_matrices_match_observer_lifecycle_receipt_contracts():
    root = Path(__file__).resolve().parents[4]
    matrix_paths = (
        root / "docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN001_L2_EVIDENCE.json",
        root / "docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN001_GUARD_MANIFEST.json",
    )
    canonical_ids = {
        "lifecycle_endpoint_qos_contract",
        "receipt_qos_contract",
        "obsolete_lifecycle_topic_absent",
    }
    observer_ids = {
        "lifecycle_endpoint_qos_contract",
        "receipt_qos_contract",
        "obsolete_lifecycle_topic_absent",
        "receipt_publisher_owner",
        "lifecycle_ready_observed",
        "lifecycle_receipt_identity",
        "final_receipt_observed",
    }
    cxx = (root / "ros2_ws/src/step07_nav2_baseline_runtime_observer/src/step07_nav2_baseline_runtime_observer.cpp").read_text(encoding="utf-8")

    for path in matrix_paths:
        document = _duplicate_rejecting_json(path)
        rows = document["acceptance_to_collector_matrix"]
        ids = [row["acceptance_id"] for row in rows]
        assert observer_ids <= set(ids)
        for acceptance_id in canonical_ids:
            assert ids.count(acceptance_id) == 1
            row = next(row for row in rows if row["acceptance_id"] == acceptance_id)
            assert row["failure_reason_literal"] == f"ACCEPTANCE_FAILED:{acceptance_id}"
            assert {"collector", "raw_artifact_path", "parser_or_validator", "pass_condition", "offline_test_name"} <= set(row)
        assert "lifecycle_state_publisher_owner" not in ids

    # C++ builds raw failure literals by the shared acceptance-id convention.
    assert '"ACCEPTANCE_FAILED:" + name' in cxx
    for acceptance_id in canonical_ids:
        assert acceptance_id in cxx


@pytest.mark.parametrize(
    ("acceptance_id", "mutate", "early_literal"),
    [
        ("lifecycle_endpoint_qos_contract",
         lambda doc: doc["graph"]["/mecanum/safety_lifecycle_state"]["publishers"][0].update(depth=9), None),
        ("receipt_qos_contract",
         lambda doc: doc["graph"]["/mecanum/final_issued_command"]["publishers"][0].update(depth=2), None),
        ("obsolete_lifecycle_topic_absent",
         lambda doc: doc["graph"]["/mecanum/safety/lifecycle_state"]["subscribers"].append({"node_name": "unexpected"}),
         "LIFECYCLE_TOPIC_OBSOLETE_OR_IN_USE"),
    ],
)
def test_lifecycle_receipt_acceptance_mismatches_fail_closed(acceptance_id, mutate, early_literal):
    document = observer_doc()
    mutate(document)
    if early_literal:
        # The parser rejects an observed obsolete endpoint before acceptance-map comparison.
        with pytest.raises(ValueError, match=early_literal):
            validate_observer(document, config_hash="a" * 64)
        return
    with pytest.raises(ValueError, match="OBSERVER_ACCEPTANCE_RAW_MISMATCH|QOS_OBSERVABILITY_EVIDENCE_RAW_MISMATCH"):
        validate_observer(document, config_hash="a" * 64)


def test_cpp_observer_parser_recomputes_qos_gid_static_owner_and_boundary():
    doc = observer_doc()
    result = validate_observer(doc, config_hash="a" * 64)
    assert all(result["acceptance"].values())
    for mutation in (
        lambda value: value["qos"]["/tf"].update(reliability="RELIABLE"),
        lambda value: value["qos"]["/tf_static"].update(durability="VOLATILE"),
        lambda value: value["graph"]["/tf"]["publishers"][0].update(node_name="other"),
        lambda value: value["graph"]["/tf"]["publishers"][1].update(node_name="other"),
        lambda value: value["graph"]["/tf_static"]["publishers"][0].update(node_name="other"),
        lambda value: value["graph"]["/mecanum/safety_lifecycle_state"]["publishers"][0].update(node_name="other"),
        lambda value: value["graph"]["/mecanum/safety_lifecycle_state"]["publishers"][0].update(topic_type="wrong/type"),
        lambda value: value["graph"]["/mecanum/safety_lifecycle_state"]["publishers"][0].update(durability=1),
        lambda value: value["graph"]["/mecanum/safety_lifecycle_state"]["publishers"][0].update(reliability=2),
        lambda value: value["graph"]["/mecanum/safety_lifecycle_state"]["publishers"][0].update(history=2),
        lambda value: value["graph"]["/mecanum/safety_lifecycle_state"]["publishers"][0].update(depth=1),
        lambda value: value["graph"]["/mecanum/safety_lifecycle_state"]["subscribers"][0].update(durability=1),
        lambda value: value["graph"]["/mecanum/safety_lifecycle_state"]["subscribers"][0].update(reliability=2),
        lambda value: value["graph"]["/mecanum/safety_lifecycle_state"]["subscribers"][0].update(history=2),
        lambda value: value["graph"]["/mecanum/safety_lifecycle_state"]["subscribers"][0].update(depth=1),
        lambda value: value["graph"]["/mecanum/safety_lifecycle_state"]["publishers"].append(copy.deepcopy(value["graph"]["/mecanum/safety_lifecycle_state"]["publishers"][0])),
        lambda value: value["qos"]["/mecanum/safety_lifecycle_state"].update(durability="TRANSIENT_LOCAL"),
        lambda value: value["qos"]["/mecanum/final_issued_command"].update(depth=10),
        lambda value: value["graph"]["/mecanum/final_issued_command"]["publishers"][0].update(durability=2),
        lambda value: value["graph"]["/mecanum/safety/lifecycle_state"]["publishers"].append({"node_name": "safety_lifecycle"}),
        lambda value: value["map_to_odom"].append({"parent": "map", "child": "odom"}),
        lambda value: value["world_to_map"].append({"parent": "world", "child": "map", "publisher_gid": "05"}),
        lambda value: value["forbidden_boundary"]["/odom"]["publishers"].append({"node_name": "bridge"}),
        lambda value: value["receipt"][0].update(runtime_generation=99),
    ):
        changed = copy.deepcopy(doc)
        mutation(changed)
        with pytest.raises(ValueError):
            validate_observer(changed, config_hash="a" * 64)


def test_qos_unknown_fallback_requires_exact_pinned_source_and_installed_implementation():
    doc = observer_doc()
    _mark_qos_unknown(doc)
    unresolved = validate_observer(doc, config_hash="a" * 64)
    assert unresolved["qos_history_depth_resolution"] == "UNOBSERVABLE_NO_VALID_PIN"
    assert unresolved["acceptance"]["lifecycle_endpoint_qos_contract"] is False
    resolved = validate_observer(doc, config_hash="a" * 64,
        qos_implementation_pin_evidence=_pinned_qos_evidence(), review_commit="c" * 40)
    assert resolved["qos_history_depth_resolution"] == "PINNED_IMPLEMENTATION"
    assert resolved["acceptance"]["lifecycle_endpoint_qos_contract"] is True
    assert resolved["acceptance"]["receipt_qos_contract"] is True
    for mutate in (
        lambda pin: pin["source_pins"].pop(next(iter(QOS_PROFILE_SOURCE_PATHS))),
        lambda pin: pin["installed_python_source_byte_equality"].update({
            next(path for path in QOS_PROFILE_SOURCE_PATHS if path.endswith(".py")): False}),
        lambda pin: pin.update(runtime_checkout_head="d" * 40),
        lambda pin: pin.update(installed_observer_binary={"sha256": "invalid", "size_bytes": 1}),
    ):
        pin = copy.deepcopy(_pinned_qos_evidence())
        mutate(pin)
        result = validate_observer(doc, config_hash="a" * 64,
            qos_implementation_pin_evidence=pin, review_commit="c" * 40)
        assert result["acceptance"]["lifecycle_endpoint_qos_contract"] is False


def test_valid_source_install_proof_never_upgrades_observed_qos_mismatch():
    doc = observer_doc()
    _mark_qos_unknown(doc)
    lifecycle = doc["graph"]["/mecanum/safety_lifecycle_state"]
    lifecycle["subscribers"][0]["reliability"] = 2
    row = next(row for row in doc["qos_history_depth_observability"]
               if row["topic"] == "/mecanum/safety_lifecycle_state"
               and row["node_name"] == lifecycle["subscribers"][0]["node_name"])
    row["history_depth_status"] = "MISMATCH"
    doc["qos_verdict"]["lifecycle_endpoint_qos_contract"] = "FAIL"
    doc["errors"] = ["ACCEPTANCE_FAILED:lifecycle_endpoint_qos_contract"]
    resolved = validate_observer(doc, config_hash="a" * 64,
        qos_implementation_pin_evidence=_pinned_qos_evidence(), review_commit="c" * 40)
    assert resolved["acceptance"]["lifecycle_endpoint_qos_contract"] is False
    assert resolved["qos_history_depth_resolution"] == "PINNED_IMPLEMENTATION"


def test_missing_gate_b_endpoint_is_not_resolved_by_valid_source_install_proof():
    doc = observer_doc()
    _mark_qos_unknown(doc)
    lifecycle = doc["graph"]["/mecanum/safety_lifecycle_state"]
    lifecycle["subscribers"] = [row for row in lifecycle["subscribers"]
                                  if row["node_name"] != "step07_gate_b_observer"]
    doc["qos_history_depth_observability"] = [row for row in doc["qos_history_depth_observability"]
        if row["node_name"] != "step07_gate_b_observer"]
    doc["qos_verdict"]["lifecycle_endpoint_qos_contract"] = "FAIL"
    doc["errors"] = ["ACCEPTANCE_FAILED:lifecycle_endpoint_qos_contract"]
    result = validate_observer(doc, config_hash="a" * 64,
        qos_implementation_pin_evidence=_pinned_qos_evidence(), review_commit="c" * 40)
    assert result["acceptance"]["lifecycle_endpoint_qos_contract"] is False
    assert result["qos_history_depth_resolution"] == "PINNED_IMPLEMENTATION"


def test_navigation_evidence_chain_requires_every_existing_stream_and_is_canonical():
    observer = observer_doc()
    gate = _gate_b_doc()
    start, end = gate["samples"][0]["stamp_ns"], gate["samples"][-1]["stamp_ns"]
    observer["safety_state"] = [{"stamp_sec": 0, "stamp_nanosec": i,
        "raw_command": {"vx": 0.1, "vy": 0.0, "wz": 0.0},
        "intervention_reasons": ["LIMITER_PRIMED"], "command_valid": True,
        "motion_permitted": True, "scan_fresh": True, "odom_fresh": True,
        "tf_valid": True, "localization_valid": True} for i in range(start, end + 1)]
    observer["receipt"] = [{"stamp_sec": 0, "stamp_nanosec": i, "source": 2, "sequence": i,
        "episode_generation": 1, "reset_epoch": 2, "runtime_generation": 3,
        "vx": 0.1, "vy": 0.0, "wz": 0.0} for i in range(start, end + 1)]
    observer["filtered_odometry"] = [{"frame_id": "odom", "child_frame_id": "base_link",
        "stamp_sec": 0, "stamp_nanosec": i, "pose": [0.0] * 7, "twist": [0.0] * 6,
        "pose_finite": True, "twist_finite": True} for i in range(start, end + 1)]
    chain_a, bytes_a = canonical_navigation_evidence_chain(observer, gate)
    chain_b, bytes_b = canonical_navigation_evidence_chain(observer, gate)
    assert chain_a == chain_b and bytes_a == bytes_b
    assert json.loads(bytes_a) == chain_a
    for field in ("safety_state", "receipt", "filtered_odometry"):
        changed = copy.deepcopy(observer)
        changed[field] = []
        with pytest.raises(ValueError, match="NAVIGATION_EVIDENCE_CHAIN_MISSING"):
            canonical_navigation_evidence_chain(changed, gate)
    changed = copy.deepcopy(observer)
    changed["safety_state"][0].pop("raw_command")
    with pytest.raises(ValueError, match="candidate_or_safety_reason"):
        canonical_navigation_evidence_chain(changed, gate)


def test_navigation_evidence_chain_rejects_uncorrelated_receipt_and_has_structured_failure():
    observer = observer_doc()
    gate = _gate_b_doc()
    observer["safety_state"] = [{"stamp_sec": 0, "stamp_nanosec": i,
        "raw_command": {"vx": 0.0, "vy": 0.0, "wz": 0.0},
        "intervention_reasons": [], "command_valid": True, "motion_permitted": True}
        for i in range(1, 6)]
    observer["receipt"] = [{"stamp_sec": 0, "stamp_nanosec": i, "sequence": i,
        "episode_generation": 1, "reset_epoch": 2, "runtime_generation": 3,
        "vx": 0.0, "vy": 0.0, "wz": 0.0} for i in range(1, 6)]
    observer["filtered_odometry"] = [{"frame_id": "odom", "child_frame_id": "base_link",
        "stamp_sec": 0, "stamp_nanosec": i, "pose": [0.0] * 7, "twist": [0.0] * 6,
        "pose_finite": True, "twist_finite": True} for i in range(1, 6)]
    observer["receipt"][0]["sequence"] = 99
    with pytest.raises(ValueError, match="correlated_final_receipt"):
        canonical_navigation_evidence_chain(observer, gate)
    failure = navigation_evidence_chain_failure(observer, gate,
        "NAVIGATION_EVIDENCE_CHAIN_MISSING:correlated_final_receipt")
    assert failure["state"] == "FAILURE"
    assert failure["failure_literal"] == "NAVIGATION_EVIDENCE_CHAIN_MISSING:correlated_final_receipt"
    assert failure["links"]["final_receipt"]["state"] == "CORRELATION_FAILURE"
    assert failure["window"]["sample_count"] == 5


def test_gate_b_document_requires_successful_nav2_actions_and_exact_vectors():
    samples = [{"stamp_ns": i, "dimension": 81, "dtype": "float32", "values": [0.0] * 81} for i in range(1, 6)]
    doc = {"schema_version": "1.0", "config_hash": "b" * 64,
           "source_contract": "LIDAR72_LOCAL_REFERENCE3_FILTERED_TWIST3_FINAL_RECEIPT3",
           "sample_count": 5, "samples": samples,
           "compute_path_to_pose": {"requested_once": True, "success": True, "frame_id": "map", "transcript": {"path_frame_id": "map"}},
           "navigate_to_pose": {"requested_once": True, "accepted": True, "succeeded": True}, "errors": [],
           "acceptance": {"five_immutable_observation81": True, "compute_path_success_map_frame": True,
                          "navigate_to_pose_requested_once": True, "navigate_to_pose_succeeded": True,
                          "no_command_or_policy_publisher": True, "errors_absent": True}}
    assert all(validate_gate_b_document(doc, config_hash="b" * 64)["acceptance"].values())
    doc["samples"].pop()
    with pytest.raises(ValueError, match="VECTOR"):
        validate_gate_b_document(doc, config_hash="b" * 64)


def test_lifecycle_endpoint_contract_rejects_qos_conflation_and_obsolete_topic():
    document = observer_doc()
    document["qos"]["/mecanum/safety_lifecycle_state"] = dict(document["qos"]["/mecanum/final_issued_command"])
    with pytest.raises(ValueError):
        validate_observer(document, config_hash="a" * 64)
    document = observer_doc()
    document["graph"]["/mecanum/safety/lifecycle_state"]["subscribers"].append({"node_name": "safety_lifecycle"})
    with pytest.raises(ValueError, match="LIFECYCLE_TOPIC_OBSOLETE_OR_IN_USE"):
        validate_observer(document, config_hash="a" * 64)


def _gate_b_doc(config_hash="a" * 64):
    samples = [{"stamp_ns": i, "dimension": 81, "dtype": "float32", "values": [0.0] * 81,
                "correlation": {"episode_generation": 1, "reset_epoch": 2, "runtime_generation": 3,
                    "lifecycle_sequence": i, "receipt_sequence": i, "scan_stamp_ns": i,
                    "odometry_stamp_ns": i, "receipt_stamp_ns": i}}
               for i in range(1, 6)]
    return {"schema_version": "1.0", "config_hash": config_hash,
            "source_contract": "LIDAR72_LOCAL_REFERENCE3_FILTERED_TWIST3_FINAL_RECEIPT3",
            "sample_count": len(samples), "samples": samples,
            "compute_path_to_pose": {"requested_once": True, "success": True, "frame_id": "map",
                                      "transcript": {"path_frame_id": "map"}},
            "navigate_to_pose": {"requested_once": True, "accepted": True, "succeeded": True},
            "errors": [],
            "acceptance": {"five_immutable_observation81": True,
                           "compute_path_success_map_frame": True,
                           "navigate_to_pose_requested_once": True,
                           "navigate_to_pose_succeeded": True,
                           "no_command_or_policy_publisher": True, "errors_absent": True}}


def _write_canonical_json(path, value):
    path.write_bytes(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                separators=(",", ":"), allow_nan=False).encode("utf-8"))


def test_validate_run_directory_accepts_complete_canonical_run005_bundle(tmp_path):
    run_dir = tmp_path / "run005"
    run_dir.mkdir()
    config_hash = "a" * 64
    record = _run005_record()
    record["config_hash"] = config_hash
    record["acceptance"].update({"observer_acceptance": True, "gate_b_vectors": True})
    record["teardown"].update({"completed": True, "clean": True,
                               "ordered": True, "order_correct": True, "verified": True,
                               "graceful": True, "escalation_history": []})
    observer = observer_doc()
    gate = _gate_b_doc(config_hash)
    for row in observer["filtered_odometry"]:
        row.update(stamp_sec=0, pose=[0.0] * 7, twist=[0.0] * 6)
    observer["safety_state"] = [{"stamp_sec": 0, "stamp_nanosec": i,
        "raw_command": {"vx": 0.0, "vy": 0.0, "wz": 0.0},
        "intervention_reasons": [], "command_valid": True, "motion_permitted": True}
        for i in range(1, 6)]
    observer["receipt"] = [{"stamp_sec": 0, "stamp_nanosec": i, "sequence": i,
        "episode_generation": 1, "reset_epoch": 2, "runtime_generation": 3,
        "vx": 0.0, "vy": 0.0, "wz": 0.0}
        for i in range(1, 6)]
    observer["navigation_evidence_chain"], canonical = canonical_navigation_evidence_chain(observer, gate)
    observer["navigation_evidence_chain_canonical"] = canonical.decode("utf-8")
    observer["navigation_evidence_chain_sha256"] = __import__("hashlib").sha256(canonical).hexdigest()
    artifact_values = {
        "run_record.json": record,
        "runtime_observer.json": observer,
        "gate_b_vectors.json": gate,
    }
    artifact_rows = []
    for name, value in artifact_values.items():
        target = run_dir / name
        _write_canonical_json(target, value)
        raw = target.read_bytes()
        artifact_rows.append({"path": name,
                              "sha256": __import__("hashlib").sha256(raw).hexdigest(),
                              "size_bytes": len(raw)})
    _write_canonical_json(run_dir / "artifact_manifest.json",
                          {"schema_version": "1.0", "run_id": record["run_id"],
                           "artifact_count": len(artifact_rows),
                           "artifacts": artifact_rows})
    checksum_rows = sorted((item["sha256"], item["path"]) for item in artifact_rows)
    (run_dir / "SHA256SUMS.txt").write_text(
        "".join(f"{digest}  {path}\n" for digest, path in checksum_rows), encoding="utf-8")

    result = validate_run_directory(run_dir)
    assert result["verdict"] == {
        "pass": True,
        "terminal_outcome": "STEP07_NAV2_BASELINE_RUN005_PASS_PENDING_INDEPENDENT_EVIDENCE_AUDIT",
    }
    assert len(result["artifact_hashes"]) == 3


def _fresh_pre_vector_chain():
    observer=observer_doc();gate=_gate_b_doc()
    observer['safety_state']=[];observer['receipt']=[];observer['filtered_odometry']=[]
    for i,sample in enumerate(gate['samples'],1):
        stamp=10_000_000_000+(i-1)*10_000_000;measurement=stamp-20_000_000
        sample['stamp_ns']=stamp
        sample['correlation'].update(scan_stamp_ns=measurement,odometry_stamp_ns=measurement,
            receipt_stamp_ns=measurement,receipt_sequence=i)
        sec,ns=divmod(measurement,1_000_000_000)
        observer['receipt'].append({'stamp_sec':sec,'stamp_nanosec':ns,'sequence':i,
            'episode_generation':1,'reset_epoch':2,'runtime_generation':3,'vx':0.,'vy':0.,'wz':0.})
        observer['filtered_odometry'].append({'stamp_sec':sec,'stamp_nanosec':ns,
            'pose':[0.]*7,'twist':[0.]*6,'pose_finite':True,'twist_finite':True})
        sec,ns=divmod(stamp,1_000_000_000)
        observer['safety_state'].append({'stamp_sec':sec,'stamp_nanosec':ns,'raw_command':{'vx':0.,'vy':0.,'wz':0.},
            'intervention_reasons':[],'command_valid':True,'motion_permitted':True})
    return observer,gate


def test_exact_fresh_records_before_first_vector_are_kept_without_widening_window():
    observer,gate=_fresh_pre_vector_chain()
    chain=build_navigation_evidence_chain(observer,gate)
    assert chain['window']['start_stamp_ns']==10_000_000_000
    first=chain['links']['final_receipt'][0]
    assert first['stamp_sec']*1_000_000_000+first['stamp_nanosec']==9_980_000_000
    unrelated=copy.deepcopy(first);unrelated.update(stamp_sec=9,stamp_nanosec=0,sequence=999)
    observer['receipt'].append(unrelated)
    assert build_navigation_evidence_chain(observer,gate)==chain


@pytest.mark.parametrize('fault',['stale_receipt','stale_odometry','future','wrong_sequence','wrong_generation','missing_receipt','missing_odometry'])
def test_pre_vector_correlation_rejects_stale_future_wrong_identity_or_missing_exact_record(fault):
    observer,gate=_fresh_pre_vector_chain();correlation=gate['samples'][0]['correlation']
    if fault in ('stale_receipt','stale_odometry','future'):
        key='odometry_stamp_ns' if fault=='stale_odometry' else 'receipt_stamp_ns'
        age=250_000_001 if fault=='stale_odometry' else 500_000_001 if fault=='stale_receipt' else -1
        stamp=gate['samples'][0]['stamp_ns']-age;correlation[key]=stamp
        row=observer['filtered_odometry' if fault=='stale_odometry' else 'receipt'][0]
        row['stamp_sec'],row['stamp_nanosec']=divmod(stamp,1_000_000_000)
    elif fault=='wrong_sequence':observer['receipt'][0]['sequence']=999
    elif fault=='wrong_generation':observer['receipt'][0]['runtime_generation']=99
    else:observer['receipt' if fault=='missing_receipt' else 'filtered_odometry'].pop(0)
    with pytest.raises(ValueError,match='FRESHNESS_INVALID|correlated_final_receipt|correlated_odometry'):
        build_navigation_evidence_chain(observer,gate)


def test_terminal_handshake_verifies_collection_and_peer_hash_and_exact_byte_size():
    from step07_gate_b_evidence_validator import validate_gate_b_terminal
    collection=_gate_b_doc();collection.update(handshake_protocol='2.0',invocation_id='fixture',
        protocol_phase='COLLECTION_COMPLETE_AWAITING_PEER')
    raw=semantic_canonical_bytes(collection)
    peer=semantic_canonical_bytes({'schema_version':'1.0','invocation_id':'fixture',
        'config_hash':'a'*64,'snapshot_complete':True})
    terminal={'schema_version':'1.0','collector':'step07_gate_b_observer','protocol_phase':'TERMINAL',
        'config_hash':'a'*64,'invocation_id':'fixture','status':'PASS','errors':[],'peer_verified':True,
        'collection_artifact':{'path':'gate_b_vectors.json','sha256':hashlib.sha256(raw).hexdigest(),'size_bytes':len(raw)},
        'peer_artifact':{'path':'runtime_observer.json','sha256':hashlib.sha256(peer).hexdigest(),'size_bytes':len(peer)}}
    kwargs=dict(collection_raw=raw,peer_raw=peer,config_hash='a'*64,invocation_id='fixture')
    assert validate_gate_b_terminal(terminal,**kwargs)['terminal_pass']
    for field in ('size_bytes','sha256'):
        bad=copy.deepcopy(terminal);bad['collection_artifact'][field]=0
        with pytest.raises(ValueError,match='HASH_OR_SIZE_MISMATCH'):validate_gate_b_terminal(bad,**kwargs)


@pytest.mark.parametrize('literal',['GATE_B_PEER_EVIDENCE_TIMEOUT','GATE_B_PEER_CONFIG_HASH_MISMATCH'])
def test_peer_failure_after_vector_write_round_trips_as_failure_not_collection_pass(tmp_path,literal):
    record=_run005_record();record.update(config_hash='a'*64,invocation_id='fixture',collector_handshake_protocol='2.0')
    record['acceptance'].update(observer_acceptance=False,gate_b_vectors=False)
    record['failure_reason_literals']=[literal];record['terminal_outcome']='STEP07_NAV2_BASELINE_RUN005_FAIL_NO_RETRY_GUARD_CONSUMED'
    state={'protocol':'2.0','status':'FAIL','events':['GATE_B_COLLECTION_VERIFIED'],'failure_literal':literal}
    record['collector_handshake']=state
    gate=_gate_b_doc();gate.update(handshake_protocol='2.0',invocation_id='fixture',protocol_phase='COLLECTION_COMPLETE_AWAITING_PEER')
    collection=semantic_canonical_bytes(gate)
    terminal={'schema_version':'1.0','collector':'step07_gate_b_observer','protocol_phase':'TERMINAL',
        'config_hash':'a'*64,'invocation_id':'fixture','status':'FAIL','errors':[literal],'peer_verified':False,
        'collection_artifact':{'path':'gate_b_vectors.json','sha256':hashlib.sha256(collection).hexdigest(),'size_bytes':len(collection)},'peer_artifact':None}
    artifacts={'run_record.json':record,'gate_b_vectors.json':gate,'runtime_observer.json':{'config_hash':'a'*64},
        'gate_b_terminal.json':terminal,'collector_handshake.failure.json':{'schema_version':'1.0','invocation_id':'fixture','config_hash':'a'*64,**state}}
    rows=[]
    for name,doc in artifacts.items():
        p=tmp_path/name;_write_canonical_json(p,doc);raw=p.read_bytes();rows.append({'path':name,'sha256':hashlib.sha256(raw).hexdigest(),'size_bytes':len(raw)})
    _write_canonical_json(tmp_path/'artifact_manifest.json',{'schema_version':'1.0','run_id':record['run_id'],
        'artifact_count':len(rows),'artifacts':rows})
    (tmp_path/'SHA256SUMS.txt').write_text(''.join(f"{row['sha256']}  {row['path']}\n" for row in rows))
    result=validate_run_directory(tmp_path)
    assert not result['verdict']['pass'] and not result['gate_b_terminal']['terminal_pass']
    assert all(gate['acceptance'].values()) # Collection local xanh không được nâng terminal.


PROTOCOL2_EVENTS = ["GATE_B_COLLECTION_VERIFIED", "CPP_FINALIZE_REQUESTED",
                    "CPP_SNAPSHOT_COMPLETE", "GATE_B_TERMINAL_VERIFIED"]


def _seal_bundle(root, filenames=None):
    filenames = filenames or sorted(path.name for path in root.glob("*.json")
                                    if path.name != "artifact_manifest.json")
    record = json.loads((root / "run_record.json").read_text(encoding="utf-8"))
    rows = []
    for name in filenames:
        raw = (root / name).read_bytes()
        rows.append({"path": name, "sha256": hashlib.sha256(raw).hexdigest(), "size_bytes": len(raw)})
    _write_canonical_json(root / "artifact_manifest.json", {"schema_version": "1.0",
        "run_id": record["run_id"], "artifact_count": len(rows), "artifacts": rows})
    (root / "SHA256SUMS.txt").write_text(
        "".join(f"{row['sha256']}  {row['path']}\n" for row in rows), encoding="utf-8")


def _protocol2_pass_bundle(root):
    root.mkdir(parents=True, exist_ok=True)
    config_hash, invocation_id = "a" * 64, "INVOCATION_PROTOCOL2_FIXTURE"
    record = _run005_record()
    record.update(config_hash=config_hash, invocation_id=invocation_id,
        collector_handshake_protocol="2.0", collector_handshake={
            "protocol": "2.0", "status": "COMPLETE", "events": PROTOCOL2_EVENTS.copy()})
    record["acceptance"].update(observer_acceptance=True, gate_b_vectors=True)
    observer = observer_doc()
    observer.update(invocation_id=invocation_id, snapshot_complete=True)
    gate = _gate_b_doc(config_hash)
    gate.update(handshake_protocol="2.0", protocol_phase="COLLECTION_COMPLETE_AWAITING_PEER",
                invocation_id=invocation_id)
    for row in observer["filtered_odometry"]:
        row.update(stamp_sec=0, pose=[0.0] * 7, twist=[0.0] * 6)
    observer["safety_state"] = [{"stamp_sec": 0, "stamp_nanosec": i,
        "raw_command": {"vx": 0.0, "vy": 0.0, "wz": 0.0},
        "intervention_reasons": [], "command_valid": True, "motion_permitted": True}
        for i in range(1, 6)]
    observer["receipt"] = [{"stamp_sec": 0, "stamp_nanosec": i, "sequence": i,
        "episode_generation": 1, "reset_epoch": 2, "runtime_generation": 3,
        "vx": 0.0, "vy": 0.0, "wz": 0.0} for i in range(1, 6)]
    observer["navigation_evidence_chain"], chain_raw = canonical_navigation_evidence_chain(observer, gate)
    observer["navigation_evidence_chain_canonical"] = chain_raw.decode("utf-8")
    observer["navigation_evidence_chain_sha256"] = hashlib.sha256(chain_raw).hexdigest()

    def identity(raw, name):
        return {"path": name, "sha256": hashlib.sha256(raw).hexdigest(), "size_bytes": len(raw)}

    collection_raw = semantic_canonical_bytes(gate)
    peer_raw = semantic_canonical_bytes(observer)
    terminal = {"schema_version": "1.0", "collector": "step07_gate_b_observer",
        "protocol_phase": "TERMINAL", "config_hash": config_hash, "invocation_id": invocation_id,
        "status": "PASS", "errors": [], "peer_verified": True,
        "collection_artifact": identity(collection_raw, "gate_b_vectors.json"),
        "peer_artifact": identity(peer_raw, "runtime_observer.json")}
    chain_raw = semantic_canonical_bytes(observer["navigation_evidence_chain"])
    chain_doc = {"schema_version": "1.0", "chain": observer["navigation_evidence_chain"],
        "canonical": chain_raw.decode("utf-8"), "sha256": hashlib.sha256(chain_raw).hexdigest()}
    for name, document in (("run_record.json", record), ("runtime_observer.json", observer),
                           ("gate_b_vectors.json", gate), ("gate_b_terminal.json", terminal),
                           ("navigation_evidence_chain.json", chain_doc)):
        _write_canonical_json(root / name, document)
    _seal_bundle(root)
    return root


def _refresh_protocol2_terminal_binding(root):
    path = root / "gate_b_terminal.json"
    terminal = json.loads(path.read_text(encoding="utf-8"))
    for key, filename in (("collection_artifact", "gate_b_vectors.json"),
                          ("peer_artifact", "runtime_observer.json")):
        artifact = root / filename
        if terminal.get(key) is not None and artifact.is_file():
            raw = artifact.read_bytes()
            terminal[key] = {"path": filename, "sha256": hashlib.sha256(raw).hexdigest(),
                             "size_bytes": len(raw)}
    _write_canonical_json(path, terminal)
    _seal_bundle(root)


def test_protocol2_pass_fixture_is_accepted_by_validate_run_directory(tmp_path):
    result = validate_run_directory(_protocol2_pass_bundle(tmp_path / "pass"))
    assert result["verdict"]["pass"] is True
    assert result["gate_b_terminal"]["terminal_pass"] is True
    assert set(result["artifact_hashes"]) == {"run_record.json", "runtime_observer.json",
        "gate_b_vectors.json", "gate_b_terminal.json", "navigation_evidence_chain.json"}


def test_protocol2_pass_rejects_resealed_contradictory_handshake_failure(tmp_path):
    root = _protocol2_pass_bundle(tmp_path / "pass_with_failure")
    _write_canonical_json(root / "collector_handshake.failure.json", {
        "schema_version": "1.0", "protocol": "2.0",
        "invocation_id": "INVOCATION_PROTOCOL2_FIXTURE", "config_hash": "a" * 64,
        "status": "FAIL", "events": PROTOCOL2_EVENTS[:-1],
        "failure_literal": "CONTRADICTORY_FAILURE"})
    _seal_bundle(root)
    with pytest.raises(ValueError, match="COLLECTOR_HANDSHAKE_FAILURE_RECORD_MISMATCH"):
        validate_run_directory(root)


@pytest.mark.parametrize("mutation", [
    "collection_missing_protocol", "collection_old_protocol", "collection_unknown_protocol",
    "run_record_protocol_mismatch", "terminal_fail", "terminal_wrong_config",
    "terminal_wrong_invocation", "terminal_wrong_hash", "terminal_wrong_size",
    "handshake_missing_status", "handshake_fail_status", "event_missing", "event_duplicate",
    "event_wrong_order", "six_vectors", "omit_run_record_seal", "omit_observer_seal",
    "omit_collection_seal", "omit_terminal_seal", "omit_chain_seal", "missing_terminal",
    "missing_chain", "missing_run_record", "artifact_changed_after_manifest",
])
def test_protocol2_pass_mutations_fail_through_validate_run_directory(tmp_path, mutation):
    root = _protocol2_pass_bundle(tmp_path / mutation)
    record_path, gate_path, terminal_path = (root / name for name in (
        "run_record.json", "gate_b_vectors.json", "gate_b_terminal.json"))
    record = json.loads(record_path.read_text(encoding="utf-8"))
    gate = json.loads(gate_path.read_text(encoding="utf-8"))
    terminal = json.loads(terminal_path.read_text(encoding="utf-8"))
    if mutation == "collection_missing_protocol":
        gate.pop("handshake_protocol")
    elif mutation == "collection_old_protocol":
        gate["handshake_protocol"] = "1.0"
    elif mutation == "collection_unknown_protocol":
        gate["handshake_protocol"] = "9.0"
    elif mutation == "run_record_protocol_mismatch":
        record["collector_handshake_protocol"] = "1.0"
    elif mutation == "terminal_fail":
        terminal["status"] = "FAIL"
    elif mutation == "terminal_wrong_config":
        terminal["config_hash"] = "b" * 64
    elif mutation == "terminal_wrong_invocation":
        terminal["invocation_id"] = "OTHER"
    elif mutation == "terminal_wrong_hash":
        terminal["collection_artifact"]["sha256"] = "0" * 64
    elif mutation == "terminal_wrong_size":
        terminal["collection_artifact"]["size_bytes"] += 1
    elif mutation == "handshake_missing_status":
        record["collector_handshake"].pop("status")
    elif mutation == "handshake_fail_status":
        record["collector_handshake"]["status"] = "FAIL"
        record["collector_handshake"]["failure_literal"] = "FIXTURE_FAILURE"
    elif mutation == "event_missing":
        record["collector_handshake"]["events"].pop()
    elif mutation == "event_duplicate":
        record["collector_handshake"]["events"][1] = record["collector_handshake"]["events"][0]
    elif mutation == "event_wrong_order":
        record["collector_handshake"]["events"][:2] = reversed(record["collector_handshake"]["events"][:2])
    elif mutation == "six_vectors":
        gate["samples"].append(copy.deepcopy(gate["samples"][-1]))
        gate["samples"][-1]["stamp_ns"] = 6
        gate["sample_count"] = 6
    elif mutation.startswith("omit_"):
        filename = {"omit_run_record_seal": "run_record.json", "omit_observer_seal": "runtime_observer.json",
            "omit_collection_seal": "gate_b_vectors.json", "omit_terminal_seal": "gate_b_terminal.json",
            "omit_chain_seal": "navigation_evidence_chain.json"}[mutation]
        rows = json.loads((root / "artifact_manifest.json").read_text())["artifacts"]
        rows = [row for row in rows if row["path"] != filename]
        record = json.loads(record_path.read_text())
        _write_canonical_json(root / "artifact_manifest.json", {"schema_version": "1.0",
            "run_id": record["run_id"], "artifact_count": len(rows), "artifacts": rows})
        (root / "SHA256SUMS.txt").write_text(
            "".join(f"{row['sha256']}  {row['path']}\n" for row in rows), encoding="utf-8")
        with pytest.raises(ValueError, match="RUN_RECORD_NOT_SEALED|VERDICT_ARTIFACT_COVERAGE_INCOMPLETE|VERDICT_ARTIFACT_NOT_SEALED"):
            validate_run_directory(root)
        return
    elif mutation in ("missing_terminal", "missing_chain", "missing_run_record"):
        filename = {"missing_terminal": "gate_b_terminal.json", "missing_chain": "navigation_evidence_chain.json",
                    "missing_run_record": "run_record.json"}[mutation]
        (root / filename).unlink()
        if mutation != "missing_run_record":
            _seal_bundle(root)
        with pytest.raises((ValueError, FileNotFoundError)):
            validate_run_directory(root)
        return
    elif mutation == "artifact_changed_after_manifest":
        gate_path.write_bytes(gate_path.read_bytes() + b" ")
        with pytest.raises(ValueError, match="ARTIFACT_INTEGRITY_MISMATCH:gate_b_vectors.json"):
            validate_run_directory(root)
        return
    _write_canonical_json(record_path, record)
    _write_canonical_json(gate_path, gate)
    _write_canonical_json(terminal_path, terminal)
    if mutation == "six_vectors":
        _refresh_protocol2_terminal_binding(root)
    else:
        _seal_bundle(root)
    with pytest.raises(ValueError):
        validate_run_directory(root)


def test_protocol2_pre_gate_failure_requires_only_sealed_run_record(tmp_path):
    root = tmp_path / "pre_gate"
    root.mkdir()
    record = _run005_record()
    record.update(config_hash="a" * 64, invocation_id="PRE_GATE", collector_handshake_protocol="2.0")
    record["acceptance"].update(observer_acceptance=False, gate_b_vectors=False)
    record["failure_reason_literals"] = ["CPP_INITIAL_READY_FAILED"]
    record["terminal_outcome"] = "STEP07_NAV2_BASELINE_RUN005_FAIL_NO_RETRY_GUARD_CONSUMED"
    _write_canonical_json(root / "run_record.json", record)
    _seal_bundle(root, ["run_record.json"])
    result = validate_run_directory(root)
    assert result["verdict"]["pass"] is False
    assert result["gate_b"]["state"] == "NOT_STARTED"


def test_protocol2_pre_gate_producer_not_started_artifact_is_a_sealed_failure(tmp_path, monkeypatch):
    from run_step07_nav2_baseline_run005 import settle_collectors_before_teardown

    root = tmp_path / "pre_gate_settlement"
    root.mkdir()
    config_hash, blocker, literal = "a" * 64, "CPP_INITIAL_READY_FAILED", "RUNNER_SETTLEMENT_FIXTURE"
    record = _run005_record()
    record.update(config_hash=config_hash, invocation_id="PRE_GATE_SETTLEMENT",
        collector_handshake_protocol="2.0", collector_stage="CPP_OBSERVER_STARTING",
        collector_settlement={"failure_literal": literal, "blocking_reason": blocker,
                              "stage": "CPP_OBSERVER_STARTING"})
    record["acceptance"].update(observer_acceptance=False, gate_b_vectors=False)
    record["failure_reason_literals"] = [blocker]
    record["terminal_outcome"] = "STEP07_NAV2_BASELINE_RUN005_FAIL_NO_RETRY_GUARD_CONSUMED"
    gate_path, observer_path = root / "gate_b_vectors.json", root / "runtime_observer.json"
    outcomes = settle_collectors_before_teardown(gate=None, cpp=None, gate_member=None,
        cpp_member=None, gate_path=gate_path, observer_path=observer_path,
        config_hash=config_hash, failure_literal=literal, blocking_reason=blocker)
    record["collector_outcomes"] = outcomes
    _write_canonical_json(root / "run_record.json", record)
    _seal_bundle(root)
    result = validate_run_directory(root)
    assert result["verdict"]["pass"] is False
    assert result["gate_b"]["state"] == "NOT_STARTED"
    assert result["gate_b"]["blocking_reason"] == blocker


def test_runner_failure_chain_sidecar_is_sealed_and_validate_run_directory_returns_fail(tmp_path):
    from run_step07_nav2_baseline_run005 import (
        settle_collectors_before_teardown, settle_navigation_chain_failure)

    root = tmp_path / "pre_gate_failure_chain"
    root.mkdir()
    config_hash, invocation_id = "a" * 64, "FAILURE_CHAIN_FIXTURE"
    literal, blocker, stage = "RUNNER_COLLECTOR_SETTLEMENT:RuntimeError:CPP_NOT_READY", "CPP_NOT_READY", "CPP_OBSERVER_STARTING"
    record = _run005_record()
    record.update(config_hash=config_hash, invocation_id=invocation_id,
        collector_handshake_protocol="2.0", collector_stage=stage,
        collector_settlement={"failure_literal": literal, "blocking_reason": blocker, "stage": stage})
    record["acceptance"].update(observer_acceptance=False, gate_b_vectors=False)
    record["failure_reason_literals"] = [blocker]
    record["terminal_outcome"] = "STEP07_NAV2_BASELINE_RUN005_FAIL_NO_RETRY_GUARD_CONSUMED"
    gate_path, observer_path = root / "gate_b_vectors.json", root / "runtime_observer.json"
    outcomes = settle_collectors_before_teardown(gate=None, cpp=None,
        gate_member=None, cpp_member=None, gate_path=gate_path, observer_path=observer_path,
        config_hash=config_hash, failure_literal=literal, blocking_reason=blocker)
    record["collector_outcomes"] = outcomes
    settle_navigation_chain_failure(root, record, gate_path=gate_path, observer_path=observer_path,
        failure_literal=literal, blocking_reason=blocker, stage=stage)
    _write_canonical_json(root / "run_record.json", record)
    _seal_bundle(root)

    result = validate_run_directory(root)

    assert result["verdict"]["pass"] is False
    assert result["gate_b"]["state"] == "NOT_STARTED"
    assert result["gate_b"]["blocking_reason"] == blocker
    assert result["navigation_evidence_chain"]["state"] == "FAILURE"
    assert result["navigation_evidence_chain"]["chain"]["window"]["sample_count"] == 0


@pytest.mark.parametrize("mutation", ["wrong_invocation", "wrong_config", "wrong_events", "wrong_literal"])
def test_protocol2_handshake_failure_sidecar_must_match_run_record(tmp_path, mutation):
    root = tmp_path / mutation
    root.mkdir()
    config_hash, invocation_id = "a" * 64, "EARLY_HANDSHAKE_FAILURE"
    state = {"protocol": "2.0", "status": "FAIL", "events": [],
             "failure_literal": "GATE_B_COLLECTION_TIMEOUT"}
    record = _run005_record()
    record.update(config_hash=config_hash, invocation_id=invocation_id,
        collector_handshake_protocol="2.0", collector_handshake=copy.deepcopy(state))
    record["acceptance"].update(observer_acceptance=False, gate_b_vectors=False)
    record["failure_reason_literals"] = [state["failure_literal"]]
    record["terminal_outcome"] = "STEP07_NAV2_BASELINE_RUN005_FAIL_NO_RETRY_GUARD_CONSUMED"
    failure = {"schema_version": "1.0", "invocation_id": invocation_id,
               "config_hash": config_hash, **state}
    if mutation == "wrong_invocation":
        failure["invocation_id"] = "OTHER"
    elif mutation == "wrong_config":
        failure["config_hash"] = "b" * 64
    elif mutation == "wrong_events":
        failure["events"] = ["CPP_FINALIZE_REQUESTED"]
    else:
        failure["failure_literal"] = "OTHER_FAILURE"
    _write_canonical_json(root / "run_record.json", record)
    _write_canonical_json(root / "collector_handshake.failure.json", failure)
    _seal_bundle(root)
    with pytest.raises(ValueError, match="COLLECTOR_HANDSHAKE_FAILURE_IDENTITY_INVALID|COLLECTOR_HANDSHAKE_FAILURE_RECORD_MISMATCH"):
        validate_run_directory(root)


def test_protocol2_gate_started_without_collection_accepts_only_runner_stage_failure(tmp_path, monkeypatch):
    from run_step07_nav2_baseline_run005 import settle_collectors_before_teardown

    class ExitedProcess:
        returncode = 2
        def poll(self):
            return self.returncode

    root = tmp_path / "gate_started_no_collection"
    root.mkdir()
    config_hash, blocker, literal = "a" * 64, "GATE_B_COLLECTION_TIMEOUT", "RUNNER_GATE_SETTLEMENT"
    monkeypatch.setattr("run_step07_nav2_baseline_run005._safe_stop_owned_process",
        lambda proc, member, timeout: {"exit_code": 2, "leader_returncode": 2,
            "terminal_state": "EXITED", "clean": True, "verified": True,
            "graceful": True, "signal_sent": False, "errors": []})
    record = _run005_record()
    record.update(config_hash=config_hash, invocation_id="GATE_STARTED_NO_COLLECTION",
        collector_handshake_protocol="2.0", collector_stage="GATE_B_COLLECTION",
        collector_settlement={
            "failure_literal": literal, "blocking_reason": blocker, "stage": "GATE_B_COLLECTION"})
    record["call_counts"]["gate_b_observer"] = 1
    record["process_groups"]["gate_b_observer"] = {"pid": 4040, "pgid": 4040}
    record["acceptance"].update(observer_acceptance=False, gate_b_vectors=False)
    record["failure_reason_literals"] = [blocker]
    record["terminal_outcome"] = "STEP07_NAV2_BASELINE_RUN005_FAIL_NO_RETRY_GUARD_CONSUMED"
    gate_path, observer_path = root / "gate_b_vectors.json", root / "runtime_observer.json"
    outcomes = settle_collectors_before_teardown(gate=ExitedProcess(), cpp=None,
        gate_member={"name": "gate_b_observer", "pgid": 4040}, cpp_member=None,
        gate_path=gate_path, observer_path=observer_path, config_hash=config_hash,
        failure_literal=literal, blocking_reason=blocker)
    record["collector_outcomes"] = outcomes
    _write_canonical_json(root / "run_record.json", record)
    _seal_bundle(root)
    result = validate_run_directory(root)
    assert result["verdict"]["pass"] is False
    assert result["gate_b"]["state"] == "FAILED"
    assert result["gate_b"]["blocking_reason"] == blocker


def test_protocol2_handshake_failure_accepts_sealed_partial_bundle(tmp_path):
    root = tmp_path / "partial"
    root.mkdir()
    config_hash, invocation_id = "a" * 64, "PARTIAL_HANDSHAKE"
    state = {"protocol": "2.0", "status": "FAIL", "events": ["GATE_B_COLLECTION_VERIFIED"],
             "failure_literal": "CPP_FINALIZE_REQUEST_FAILED"}
    record = _run005_record()
    record.update(config_hash=config_hash, invocation_id=invocation_id,
        collector_handshake_protocol="2.0", collector_handshake=state)
    record["acceptance"].update(observer_acceptance=False, gate_b_vectors=False)
    record["failure_reason_literals"] = [state["failure_literal"]]
    record["terminal_outcome"] = "STEP07_NAV2_BASELINE_RUN005_FAIL_NO_RETRY_GUARD_CONSUMED"
    gate = _gate_b_doc(config_hash)
    gate.update(handshake_protocol="2.0", protocol_phase="COLLECTION_COMPLETE_AWAITING_PEER",
                invocation_id=invocation_id)
    collection_raw = semantic_canonical_bytes(gate)
    terminal = {"schema_version": "1.0", "collector": "step07_gate_b_observer",
        "protocol_phase": "TERMINAL", "config_hash": config_hash, "invocation_id": invocation_id,
        "status": "FAIL", "errors": [state["failure_literal"]], "peer_verified": False,
        "collection_artifact": {"path": "gate_b_vectors.json",
            "sha256": hashlib.sha256(collection_raw).hexdigest(), "size_bytes": len(collection_raw)},
        "peer_artifact": None}
    failure = {"schema_version": "1.0", "protocol": "2.0", "config_hash": config_hash,
               "invocation_id": invocation_id, **state}
    for name, document in (("run_record.json", record), ("gate_b_vectors.json", gate),
                           ("gate_b_terminal.json", terminal),
                           ("collector_handshake.failure.json", failure)):
        _write_canonical_json(root / name, document)
    _seal_bundle(root)
    result = validate_run_directory(root)
    assert result["verdict"]["pass"] is False
    assert result["gate_b_terminal"]["terminal_pass"] is False


def test_protocol2_post_handshake_failure_is_validated_as_terminal_failure(tmp_path):
    root = _protocol2_pass_bundle(tmp_path / "post_handshake")
    record_path, gate_path, observer_path = (root / name for name in (
        "run_record.json", "gate_b_vectors.json", "runtime_observer.json"))
    record = json.loads(record_path.read_text(encoding="utf-8"))
    gate = json.loads(gate_path.read_text(encoding="utf-8"))
    observer = json.loads(observer_path.read_text(encoding="utf-8"))
    record["acceptance"]["gate_b_vectors"] = False
    record["failure_reason_literals"] = ["NAVIGATE_TO_POSE_FAILED"]
    record["terminal_outcome"] = "STEP07_NAV2_BASELINE_RUN005_FAIL_NO_RETRY_GUARD_CONSUMED"
    gate["navigate_to_pose"]["succeeded"] = False
    gate["errors"] = ["NAVIGATE_TO_POSE_FAILED"]
    gate["acceptance"]["navigate_to_pose_succeeded"] = False
    gate["acceptance"]["errors_absent"] = False
    observer["navigation_evidence_chain"], chain_raw = canonical_navigation_evidence_chain(observer, gate)
    observer["navigation_evidence_chain_canonical"] = chain_raw.decode("utf-8")
    observer["navigation_evidence_chain_sha256"] = hashlib.sha256(chain_raw).hexdigest()
    chain_doc = {"schema_version": "1.0", "chain": observer["navigation_evidence_chain"],
        "canonical": chain_raw.decode("utf-8"), "sha256": hashlib.sha256(chain_raw).hexdigest()}
    terminal = json.loads((root / "gate_b_terminal.json").read_text(encoding="utf-8"))
    terminal["status"] = "FAIL"
    terminal["errors"] = gate["errors"]
    _write_canonical_json(record_path, record)
    _write_canonical_json(gate_path, gate)
    _write_canonical_json(observer_path, observer)
    _write_canonical_json(root / "navigation_evidence_chain.json", chain_doc)
    _write_canonical_json(root / "gate_b_terminal.json", terminal)
    _refresh_protocol2_terminal_binding(root)
    result = validate_run_directory(root)
    assert result["verdict"]["pass"] is False
    assert result["gate_b_terminal"]["terminal_pass"] is False
    assert result["gate_b"]["acceptance"]["navigate_to_pose_succeeded"] is False


@pytest.mark.parametrize("mutation", ["manifest_count", "manifest_identity", "artifact_path_escape"])
def test_manifest_identity_count_and_path_contract_are_enforced(tmp_path, mutation):
    root = _protocol2_pass_bundle(tmp_path / mutation)
    manifest_path = root / "artifact_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if mutation == "manifest_count":
        manifest["artifact_count"] += 1
    elif mutation == "manifest_identity":
        manifest["run_id"] = "OTHER_RUN"
    else:
        manifest["artifacts"][0]["path"] = "../outside.json"
    _write_canonical_json(manifest_path, manifest)
    with pytest.raises(ValueError, match="ARTIFACT_MANIFEST_IDENTITY_INVALID|ARTIFACT_MANIFEST_ENTRIES_INVALID|ARTIFACT_MANIFEST_PATH_INVALID"):
        validate_run_directory(root)


def test_evidence_root_and_verdict_artifact_symlinks_are_rejected(tmp_path):
    root = _protocol2_pass_bundle(tmp_path / "sealed")
    linked_root = tmp_path / "root-link"
    linked_root.symlink_to(root, target_is_directory=True)
    with pytest.raises(ValueError, match="EVIDENCE_ROOT_NOT_REAL_DIRECTORY"):
        validate_run_directory(linked_root)
    target = tmp_path / "observer-copy.json"
    target.write_bytes((root / "runtime_observer.json").read_bytes())
    (root / "runtime_observer.json").unlink()
    (root / "runtime_observer.json").symlink_to(target)
    with pytest.raises(ValueError, match="ARTIFACT_SYMLINK_FORBIDDEN:runtime_observer.json"):
        validate_run_directory(root)


def test_protocol2_marker_in_failure_document_cannot_fall_back_to_legacy(tmp_path):
    root = _protocol2_pass_bundle(tmp_path / "legacy_downgrade")
    record = json.loads((root / "run_record.json").read_text())
    gate = json.loads((root / "gate_b_vectors.json").read_text())
    record.pop("collector_handshake_protocol")
    record.pop("collector_handshake")
    gate.pop("handshake_protocol")
    gate.pop("protocol_phase")
    _write_canonical_json(root / "run_record.json", record)
    _write_canonical_json(root / "gate_b_vectors.json", gate)
    _write_canonical_json(root / "collector_handshake.failure.json", {
        "schema_version": "1.0", "protocol": "2.0", "status": "FAIL"})
    _seal_bundle(root)
    with pytest.raises(ValueError, match="COLLECTOR_PROTOCOL_MISMATCH"):
        validate_run_directory(root)
