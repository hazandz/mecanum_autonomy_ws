import copy
import json
from pathlib import Path

import pytest

from step07_gate_b_evidence_validator import (
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
              "teardown": {"completed": True, "clean": True, "order_correct": True, "verified": True},
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
            "teardown": {"completed": True, "clean": True, "order_correct": True, "verified": True},
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


@pytest.mark.parametrize("mutation", [
    lambda record: record["teardown"].update(verified=False),
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
        "errors": [],
    }


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
    with pytest.raises(ValueError, match="OBSERVER_ACCEPTANCE_RAW_MISMATCH"):
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
    samples = [{"stamp_ns": i, "dimension": 81, "dtype": "float32", "values": [0.0] * 81}
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
                               "order_correct": True, "verified": True})
    observer = observer_doc()
    gate = _gate_b_doc(config_hash)
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
