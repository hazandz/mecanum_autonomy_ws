"""Offline synthetic tests for the WP06-6F Run005 topology checker."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[4]
TOOLS = ROOT / "artifacts/simulation/sim_eval_scan_endpoint_probe_evidence/tools"
sys.path.insert(0, str(TOOLS))


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


guard = _load("wp06_6f_run005_guard_test", TOOLS / "wp06_6f_tf_ekf_run005_runtime_guard.py")
sys.modules["wp06_6f_tf_ekf_run005_runtime_guard"] = guard
runner = _load("wp06_6f_run005_runner_test", TOOLS / "run_wp06_6f_tf_ekf_run005_session.py")


def _node(subscribers=(), publishers=()):
    lines = ["/node"]
    lines += ["  Subscribers:"] + [f"    {topic}: std_msgs/msg/String" for topic in subscribers]
    lines += ["  Publishers:"] + [f"    {topic}: std_msgs/msg/String" for topic in publishers]
    lines += ["  Service Servers:"]
    return "\n".join(lines)


def _valid_node_infos():
    return {
        "ekf": _node(
            ("/clock", "/imu/data", "/wheel/odometry_raw", "/set_pose"),
            ("/odometry/filtered", "/tf", "/diagnostics", "/parameter_events", "/rosout"),
        ),
        "ingress": _node(
            ("/clock", "/sim_eval/imu_raw", "/sim_eval/wheel_joint_states"),
            ("/wheel/odometry_raw", "/imu/data", "/parameter_events", "/rosout"),
        ),
        "ingress_bridge": _node((), ("/sim_eval/wheel_joint_states", "/sim_eval/imu_raw", "/parameter_events", "/rosout")),
        "clock_bridge": _node(("/clock",), ("/clock", "/parameter_events", "/rosout")),
    }


def test_run005_guard_is_pending_capacity_one():
    p = ROOT / "artifacts/simulation/sim_eval_scan_endpoint_probe_evidence/approval_guards/WP06_6F_TF_EKF_RUNTIME_INGRESS_RUN_005.json"
    g = json.loads(p.read_text(encoding="utf-8"))
    assert g["run_id"] == guard.RUN_ID == "WP06_6F_TF_EKF_RUNTIME_INGRESS_RUN_005"
    assert g["state"] == guard.PENDING == "PENDING_EXACT_INTEGRATION_AND_USER_AUTHORIZATION"
    assert g["capacity"] == 1 and g["acquisition_count"] == 0
    assert g["runtime_authorization"] == "NOT_GRANTED"


def test_exact_topic_names_do_not_confuse_filtered_odometry_with_odom():
    infos = _valid_node_infos()
    assert "/odometry/filtered" in runner._node_section_topics(infos["ekf"], "Publishers")
    assert "/odom" not in runner._node_section_topics(infos["ekf"], "Publishers")
    assert runner._topic_policy_violations(infos) == []
    infos["ekf"] = _node(
        ("/clock", "/imu/data", "/wheel/odometry_raw", "/set_pose"),
        ("/odometry/filtered", "/odom", "/tf", "/diagnostics", "/parameter_events", "/rosout"),
    )
    assert any("/odom" in row.get("topics", []) for row in runner._topic_policy_violations(infos))


@pytest.mark.parametrize("topic", ["/ground_truth/odom", "/cmd_vel", "/map", "/tf_static"])
def test_forbidden_exact_topics_are_rejected(topic):
    infos = _valid_node_infos()
    infos["ingress"] = _node(
        ("/clock", "/sim_eval/imu_raw", "/sim_eval/wheel_joint_states", topic),
        ("/wheel/odometry_raw", "/imu/data", "/parameter_events", "/rosout"),
    )
    violations = runner._topic_policy_violations(infos)
    assert any(topic in row.get("topics", []) for row in violations)


def test_set_pose_is_accepted_only_as_ekf_subscriber():
    assert runner._topic_policy_violations(_valid_node_infos()) == []
    infos = _valid_node_infos()
    infos["ingress"] = _node(
        ("/clock", "/sim_eval/imu_raw", "/sim_eval/wheel_joint_states", "/set_pose"),
        ("/wheel/odometry_raw", "/imu/data", "/parameter_events", "/rosout"),
    )
    assert any(row["reason"] == "SET_POSE_OUTSIDE_EKF_SUBSCRIBER" for row in runner._topic_policy_violations(infos))


def test_set_pose_publisher_is_rejected_with_specific_failure_literal():
    infos = _valid_node_infos()
    infos["ekf"] = _node(
        ("/clock", "/imu/data", "/wheel/odometry_raw", "/set_pose"),
        ("/odometry/filtered", "/tf", "/diagnostics", "/set_pose", "/parameter_events", "/rosout"),
    )
    violations = runner._topic_policy_violations(infos)
    assert any(row["reason"] == "EKF_SET_POSE_EXTERNAL_PUBLISHER_OBSERVED" for row in violations)
    info = "Type: geometry_msgs/msg/PoseWithCovarianceStamped\nPublisher count: 1\nSubscription count: 1\nNode name: ekf_filter_node\nEndpoint type: SUBSCRIPTION\n"
    assert runner._set_pose_failure_reason(info, b"", 124, {"/set_pose"}) == "EKF_SET_POSE_EXTERNAL_PUBLISHER_OBSERVED"


def test_arbitrary_auxiliary_topic_outside_allowlist_is_rejected():
    infos = _valid_node_infos()
    infos["ekf"] = _node(
        ("/clock", "/imu/data", "/wheel/odometry_raw", "/set_pose", "/debug_state"),
        ("/odometry/filtered", "/tf", "/diagnostics", "/parameter_events", "/rosout"),
    )
    violations = runner._topic_policy_violations(infos)
    assert any(row["reason"] == "EKF_SUBSCRIBER_SET_OUT_OF_CONTRACT" for row in violations)


def test_set_pose_endpoint_requires_exact_type_ekf_subscription_zero_publishers_and_no_payload():
    info = """Type: geometry_msgs/msg/PoseWithCovarianceStamped
Publisher count: 0
Subscription count: 1

Node name: ekf_filter_node
Node namespace: /
Topic type: geometry_msgs/msg/PoseWithCovarianceStamped
Endpoint type: SUBSCRIPTION
"""
    good = runner._set_pose_endpoint_contract(info, b"", 124, {"/set_pose"})
    assert good == {"type_exact": True, "publisher_count_zero": True, "ekf_is_subscriber": True, "no_payload": True}
    bad_publisher = info.replace("Publisher count: 0", "Publisher count: 1")
    assert not runner._set_pose_endpoint_contract(bad_publisher, b"", 124, {"/set_pose"})["publisher_count_zero"]
    assert not runner._set_pose_endpoint_contract(info, b"payload", 0, {"/set_pose"})["no_payload"]
    assert not runner._set_pose_endpoint_contract(info.replace("geometry_msgs/msg/PoseWithCovarianceStamped", "std_msgs/msg/String"), b"", 124, {"/set_pose"})["type_exact"]
    assert not runner._set_pose_endpoint_contract(info, b"", 124, set())["ekf_is_subscriber"]


def test_run004_checker_and_repository_history_are_byte_identical_to_parent():
    paths = (
        "artifacts/simulation/sim_eval_scan_endpoint_probe_evidence/approval_guards/WP06_6F_TF_EKF_RUNTIME_INGRESS_RUN_004.json",
        "artifacts/simulation/sim_eval_scan_endpoint_probe_evidence/tools/run_wp06_6f_tf_ekf_run004_session.py",
        "artifacts/simulation/sim_eval_scan_endpoint_probe_evidence/tools/test_wp06_6f_tf_ekf_run004_session.py",
        "artifacts/simulation/sim_eval_scan_endpoint_probe_evidence/tools/wp06_6f_tf_ekf_run004_runtime_guard.py",
        "docs/governance/evidence/WP-06_6F_TF_EKF_RUNTIME_INGRESS_RUN_004_GUARD_MANIFEST.json",
    )
    parent = "8b21a9832c18bc8a91af5169a78ac621038def46"
    for relative in paths:
        expected = subprocess.run(["git", "show", f"{parent}:{relative}"], cwd=ROOT, check=True, capture_output=True).stdout
        assert (ROOT / relative).read_bytes() == expected, relative


def test_runner_test_and_manifest_contract_are_run005_specific():
    assert runner.RUN_ID == "WP06_6F_TF_EKF_RUNTIME_INGRESS_RUN_005"
    source = (TOOLS / "run_wp06_6f_tf_ekf_run005_session.py").read_text(encoding="utf-8")
    assert "run004" not in source.lower()
    manifest = json.loads((ROOT / "docs/governance/evidence/WP-06_6F_TF_EKF_RUNTIME_INGRESS_RUN_005_GUARD_MANIFEST.json").read_text(encoding="utf-8"))
    ids = {row["acceptance_id"] for row in manifest["acceptance_to_collector_matrix"]}
    assert {"ekf_set_pose_admin_endpoint", "ekf_set_pose_zero_publishers_no_payload"} <= ids
    for row in manifest["acceptance_to_collector_matrix"]:
        assert all(row.get(key) for key in ("collector", "raw_artifact_path", "parser_or_validator", "pass_condition", "failure_reason_literal", "offline_test_name"))
