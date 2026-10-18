"""Offline synthetic tests for the WP06-6F Run006 topology checker."""
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


guard = _load("wp06_6f_run006_guard_test", TOOLS / "wp06_6f_tf_ekf_run006_runtime_guard.py")
sys.modules["wp06_6f_tf_ekf_run006_runtime_guard"] = guard
runner = _load("wp06_6f_run006_runner_test", TOOLS / "run_wp06_6f_tf_ekf_run006_session.py")


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


def test_run006_guard_is_pending_capacity_one():
    p = ROOT / "artifacts/simulation/sim_eval_scan_endpoint_probe_evidence/approval_guards/WP06_6F_TF_EKF_RUNTIME_INGRESS_RUN_006.json"
    g = json.loads(p.read_text(encoding="utf-8"))
    assert g["run_id"] == guard.RUN_ID == "WP06_6F_TF_EKF_RUNTIME_INGRESS_RUN_006"
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
    infos = _valid_node_infos()
    infos["ingress"] = _node(
        ("/clock", "/sim_eval/imu_raw", "/sim_eval/wheel_joint_states"),
        ("/wheel/odometry_raw", "/imu/data", "/set_pose", "/parameter_events", "/rosout"),
    )
    assert any(row["reason"] == "EKF_SET_POSE_EXTERNAL_PUBLISHER_OBSERVED" for row in runner._topic_policy_violations(infos))
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


def test_runner_test_and_manifest_contract_are_run006_specific():
    assert runner.RUN_ID == "WP06_6F_TF_EKF_RUNTIME_INGRESS_RUN_006"
    source = (TOOLS / "run_wp06_6f_tf_ekf_run006_session.py").read_text(encoding="utf-8")
    assert "run004" not in source.lower()
    manifest = json.loads((ROOT / "docs/governance/evidence/WP-06_6F_TF_EKF_RUNTIME_INGRESS_RUN_006_GUARD_MANIFEST.json").read_text(encoding="utf-8"))
    ids = {row["acceptance_id"] for row in manifest["acceptance_to_collector_matrix"]}
    assert {"ekf_set_pose_admin_endpoint", "ekf_set_pose_zero_publishers_no_payload"} <= ids
    for row in manifest["acceptance_to_collector_matrix"]:
        assert all(row.get(key) for key in ("collector", "raw_artifact_path", "parser_or_validator", "pass_condition", "failure_reason_literal", "offline_test_name"))


RUN005_RAW_NODE_INFO_BASE64 = {
    'ekf_node_info': 'L2VrZl9maWx0ZXJfbm9kZQogIFN1YnNjcmliZXJzOgogICAgL2Nsb2NrOiByb3NncmFwaF9tc2dzL21zZy9DbG9jawogICAgL2ltdS9kYXRhOiBzZW5zb3JfbXNncy9tc2cvSW11CiAgICAvcGFyYW1ldGVyX2V2ZW50czogcmNsX2ludGVyZmFjZXMvbXNnL1BhcmFtZXRlckV2ZW50CiAgICAvc2V0X3Bvc2U6IGdlb21ldHJ5X21zZ3MvbXNnL1Bvc2VXaXRoQ292YXJpYW5jZVN0YW1wZWQKICAgIC93aGVlbC9vZG9tZXRyeV9yYXc6IG5hdl9tc2dzL21zZy9PZG9tZXRyeQogIFB1Ymxpc2hlcnM6CiAgICAvZGlhZ25vc3RpY3M6IGRpYWdub3N0aWNfbXNncy9tc2cvRGlhZ25vc3RpY0FycmF5CiAgICAvb2RvbWV0cnkvZmlsdGVyZWQ6IG5hdl9tc2dzL21zZy9PZG9tZXRyeQogICAgL3BhcmFtZXRlcl9ldmVudHM6IHJjbF9pbnRlcmZhY2VzL21zZy9QYXJhbWV0ZXJFdmVudAogICAgL3Jvc291dDogcmNsX2ludGVyZmFjZXMvbXNnL0xvZwogICAgL3RmOiB0ZjJfbXNncy9tc2cvVEZNZXNzYWdlCiAgU2VydmljZSBTZXJ2ZXJzOgogICAgL2VrZl9maWx0ZXJfbm9kZS9kZXNjcmliZV9wYXJhbWV0ZXJzOiByY2xfaW50ZXJmYWNlcy9zcnYvRGVzY3JpYmVQYXJhbWV0ZXJzCiAgICAvZWtmX2ZpbHRlcl9ub2RlL2dldF9wYXJhbWV0ZXJfdHlwZXM6IHJjbF9pbnRlcmZhY2VzL3Nydi9HZXRQYXJhbWV0ZXJUeXBlcwogICAgL2VrZl9maWx0ZXJfbm9kZS9nZXRfcGFyYW1ldGVyczogcmNsX2ludGVyZmFjZXMvc3J2L0dldFBhcmFtZXRlcnMKICAgIC9la2ZfZmlsdGVyX25vZGUvZ2V0X3R5cGVfZGVzY3JpcHRpb246IHR5cGVfZGVzY3JpcHRpb25faW50ZXJmYWNlcy9zcnYvR2V0VHlwZURlc2NyaXB0aW9uCiAgICAvZWtmX2ZpbHRlcl9ub2RlL2xpc3RfcGFyYW1ldGVyczogcmNsX2ludGVyZmFjZXMvc3J2L0xpc3RQYXJhbWV0ZXJzCiAgICAvZWtmX2ZpbHRlcl9ub2RlL3NldF9wYXJhbWV0ZXJzOiByY2xfaW50ZXJmYWNlcy9zcnYvU2V0UGFyYW1ldGVycwogICAgL2VrZl9maWx0ZXJfbm9kZS9zZXRfcGFyYW1ldGVyc19hdG9taWNhbGx5OiByY2xfaW50ZXJmYWNlcy9zcnYvU2V0UGFyYW1ldGVyc0F0b21pY2FsbHkKICAgIC9lbmFibGU6IHN0ZF9zcnZzL3Nydi9FbXB0eQogICAgL3Jlc2V0OiBzdGRfc3J2cy9zcnYvRW1wdHkKICAgIC9zZXRfcG9zZTogcm9ib3RfbG9jYWxpemF0aW9uL3Nydi9TZXRQb3NlCiAgICAvdG9nZ2xlOiByb2JvdF9sb2NhbGl6YXRpb24vc3J2L1RvZ2dsZUZpbHRlclByb2Nlc3NpbmcKICBTZXJ2aWNlIENsaWVudHM6CgogIEFjdGlvbiBTZXJ2ZXJzOgoKICBBY3Rpb24gQ2xpZW50czoKCg==',
    'ingress_node_info': 'L3NpbV9ldmFsX3doZWVsX2ltdV9pbmdyZXNzCiAgU3Vic2NyaWJlcnM6CiAgICAvY2xvY2s6IHJvc2dyYXBoX21zZ3MvbXNnL0Nsb2NrCiAgICAvc2ltX2V2YWwvaW11X3Jhdzogc2Vuc29yX21zZ3MvbXNnL0ltdQogICAgL3NpbV9ldmFsL3doZWVsX2pvaW50X3N0YXRlczogc2Vuc29yX21zZ3MvbXNnL0pvaW50U3RhdGUKICBQdWJsaXNoZXJzOgogICAgL2ltdS9kYXRhOiBzZW5zb3JfbXNncy9tc2cvSW11CiAgICAvcGFyYW1ldGVyX2V2ZW50czogcmNsX2ludGVyZmFjZXMvbXNnL1BhcmFtZXRlckV2ZW50CiAgICAvcm9zb3V0OiByY2xfaW50ZXJmYWNlcy9tc2cvTG9nCiAgICAvd2hlZWwvb2RvbWV0cnlfcmF3OiBuYXZfbXNncy9tc2cvT2RvbWV0cnkKICBTZXJ2aWNlIFNlcnZlcnM6CiAgICAvc2ltX2V2YWxfd2hlZWxfaW11X2luZ3Jlc3MvZGVzY3JpYmVfcGFyYW1ldGVyczogcmNsX2ludGVyZmFjZXMvc3J2L0Rlc2NyaWJlUGFyYW1ldGVycwogICAgL3NpbV9ldmFsX3doZWVsX2ltdV9pbmdyZXNzL2dldF9wYXJhbWV0ZXJfdHlwZXM6IHJjbF9pbnRlcmZhY2VzL3Nydi9HZXRQYXJhbWV0ZXJUeXBlcwogICAgL3NpbV9ldmFsX3doZWVsX2ltdV9pbmdyZXNzL2dldF9wYXJhbWV0ZXJzOiByY2xfaW50ZXJmYWNlcy9zcnYvR2V0UGFyYW1ldGVycwogICAgL3NpbV9ldmFsX3doZWVsX2ltdV9pbmdyZXNzL2dldF90eXBlX2Rlc2NyaXB0aW9uOiB0eXBlX2Rlc2NyaXB0aW9uX2ludGVyZmFjZXMvc3J2L0dldFR5cGVEZXNjcmlwdGlvbgogICAgL3NpbV9ldmFsX3doZWVsX2ltdV9pbmdyZXNzL2xpc3RfcGFyYW1ldGVyczogcmNsX2ludGVyZmFjZXMvc3J2L0xpc3RQYXJhbWV0ZXJzCiAgICAvc2ltX2V2YWxfd2hlZWxfaW11X2luZ3Jlc3Mvc2V0X3BhcmFtZXRlcnM6IHJjbF9pbnRlcmZhY2VzL3Nydi9TZXRQYXJhbWV0ZXJzCiAgICAvc2ltX2V2YWxfd2hlZWxfaW11X2luZ3Jlc3Mvc2V0X3BhcmFtZXRlcnNfYXRvbWljYWxseTogcmNsX2ludGVyZmFjZXMvc3J2L1NldFBhcmFtZXRlcnNBdG9taWNhbGx5CiAgU2VydmljZSBDbGllbnRzOgoKICBBY3Rpb24gU2VydmVyczoKCiAgQWN0aW9uIENsaWVudHM6Cgo=',
    'ingress_bridge_node_info': 'L3NpbV9ldmFsX3doZWVsX2ltdV9pbmdyZXNzX2JyaWRnZQogIFN1YnNjcmliZXJzOgogICAgL3BhcmFtZXRlcl9ldmVudHM6IHJjbF9pbnRlcmZhY2VzL21zZy9QYXJhbWV0ZXJFdmVudAogIFB1Ymxpc2hlcnM6CiAgICAvcGFyYW1ldGVyX2V2ZW50czogcmNsX2ludGVyZmFjZXMvbXNnL1BhcmFtZXRlckV2ZW50CiAgICAvcm9zb3V0OiByY2xfaW50ZXJmYWNlcy9tc2cvTG9nCiAgICAvc2ltX2V2YWwvaW11X3Jhdzogc2Vuc29yX21zZ3MvbXNnL0ltdQogICAgL3NpbV9ldmFsL3doZWVsX2pvaW50X3N0YXRlczogc2Vuc29yX21zZ3MvbXNnL0pvaW50U3RhdGUKICBTZXJ2aWNlIFNlcnZlcnM6CiAgICAvc2ltX2V2YWxfd2hlZWxfaW11X2luZ3Jlc3NfYnJpZGdlL2Rlc2NyaWJlX3BhcmFtZXRlcnM6IHJjbF9pbnRlcmZhY2VzL3Nydi9EZXNjcmliZVBhcmFtZXRlcnMKICAgIC9zaW1fZXZhbF93aGVlbF9pbXVfaW5ncmVzc19icmlkZ2UvZ2V0X3BhcmFtZXRlcl90eXBlczogcmNsX2ludGVyZmFjZXMvc3J2L0dldFBhcmFtZXRlclR5cGVzCiAgICAvc2ltX2V2YWxfd2hlZWxfaW11X2luZ3Jlc3NfYnJpZGdlL2dldF9wYXJhbWV0ZXJzOiByY2xfaW50ZXJmYWNlcy9zcnYvR2V0UGFyYW1ldGVycwogICAgL3NpbV9ldmFsX3doZWVsX2ltdV9pbmdyZXNzX2JyaWRnZS9nZXRfdHlwZV9kZXNjcmlwdGlvbjogdHlwZV9kZXNjcmlwdGlvbl9pbnRlcmZhY2VzL3Nydi9HZXRUeXBlRGVzY3JpcHRpb24KICAgIC9zaW1fZXZhbF93aGVlbF9pbXVfaW5ncmVzc19icmlkZ2UvbGlzdF9wYXJhbWV0ZXJzOiByY2xfaW50ZXJmYWNlcy9zcnYvTGlzdFBhcmFtZXRlcnMKICAgIC9zaW1fZXZhbF93aGVlbF9pbXVfaW5ncmVzc19icmlkZ2Uvc2V0X3BhcmFtZXRlcnM6IHJjbF9pbnRlcmZhY2VzL3Nydi9TZXRQYXJhbWV0ZXJzCiAgICAvc2ltX2V2YWxfd2hlZWxfaW11X2luZ3Jlc3NfYnJpZGdlL3NldF9wYXJhbWV0ZXJzX2F0b21pY2FsbHk6IHJjbF9pbnRlcmZhY2VzL3Nydi9TZXRQYXJhbWV0ZXJzQXRvbWljYWxseQogIFNlcnZpY2UgQ2xpZW50czoKCiAgQWN0aW9uIFNlcnZlcnM6CgogIEFjdGlvbiBDbGllbnRzOgoK',
    'clock_bridge_node_info': 'L3NpbV9ldmFsX2Nsb2NrX2JyaWRnZQogIFN1YnNjcmliZXJzOgogICAgL2Nsb2NrOiByb3NncmFwaF9tc2dzL21zZy9DbG9jawogICAgL3BhcmFtZXRlcl9ldmVudHM6IHJjbF9pbnRlcmZhY2VzL21zZy9QYXJhbWV0ZXJFdmVudAogIFB1Ymxpc2hlcnM6CiAgICAvY2xvY2s6IHJvc2dyYXBoX21zZ3MvbXNnL0Nsb2NrCiAgICAvcGFyYW1ldGVyX2V2ZW50czogcmNsX2ludGVyZmFjZXMvbXNnL1BhcmFtZXRlckV2ZW50CiAgICAvcm9zb3V0OiByY2xfaW50ZXJmYWNlcy9tc2cvTG9nCiAgU2VydmljZSBTZXJ2ZXJzOgogICAgL3NpbV9ldmFsX2Nsb2NrX2JyaWRnZS9kZXNjcmliZV9wYXJhbWV0ZXJzOiByY2xfaW50ZXJmYWNlcy9zcnYvRGVzY3JpYmVQYXJhbWV0ZXJzCiAgICAvc2ltX2V2YWxfY2xvY2tfYnJpZGdlL2dldF9wYXJhbWV0ZXJfdHlwZXM6IHJjbF9pbnRlcmZhY2VzL3Nydi9HZXRQYXJhbWV0ZXJUeXBlcwogICAgL3NpbV9ldmFsX2Nsb2NrX2JyaWRnZS9nZXRfcGFyYW1ldGVyczogcmNsX2ludGVyZmFjZXMvc3J2L0dldFBhcmFtZXRlcnMKICAgIC9zaW1fZXZhbF9jbG9ja19icmlkZ2UvZ2V0X3R5cGVfZGVzY3JpcHRpb246IHR5cGVfZGVzY3JpcHRpb25faW50ZXJmYWNlcy9zcnYvR2V0VHlwZURlc2NyaXB0aW9uCiAgICAvc2ltX2V2YWxfY2xvY2tfYnJpZGdlL2xpc3RfcGFyYW1ldGVyczogcmNsX2ludGVyZmFjZXMvc3J2L0xpc3RQYXJhbWV0ZXJzCiAgICAvc2ltX2V2YWxfY2xvY2tfYnJpZGdlL3NldF9wYXJhbWV0ZXJzOiByY2xfaW50ZXJmYWNlcy9zcnYvU2V0UGFyYW1ldGVycwogICAgL3NpbV9ldmFsX2Nsb2NrX2JyaWRnZS9zZXRfcGFyYW1ldGVyc19hdG9taWNhbGx5OiByY2xfaW50ZXJmYWNlcy9zcnYvU2V0UGFyYW1ldGVyc0F0b21pY2FsbHkKICBTZXJ2aWNlIENsaWVudHM6CgogIEFjdGlvbiBTZXJ2ZXJzOgoKICBBY3Rpb24gQ2xpZW50czoKCg==',
}

def test_run005_raw_node_info_transcripts_pass_run006_topology_policy():
    import hashlib

    expected_hashes = {
        "ekf_node_info": "ab69440fd60b08625acdb1d539ae067ea6e8916042ca4a19178a0782380ec996",
        "ingress_node_info": "3bcd91b5ccaa04071b82b205197e779efb56f289198a96bd5d71b6891fdeeb69",
        "ingress_bridge_node_info": "e2f828c1363e4f3ed942cedc1dcc92a5cfd98ee52c90e7892d145a058d4c62aa",
        "clock_bridge_node_info": "46037052d34d3905974d461e446e06c9537cbeb59824e9ab787f7ca085e50123",
    }
    import base64
    raw_transcripts = {name: base64.b64decode(value) for name, value in RUN005_RAW_NODE_INFO_BASE64.items()}
    for name, raw in raw_transcripts.items():
        assert hashlib.sha256(raw).hexdigest() == expected_hashes[name]
    infos = {
        "ekf": raw_transcripts["ekf_node_info"].decode("utf-8"),
        "ingress": raw_transcripts["ingress_node_info"].decode("utf-8"),
        "ingress_bridge": raw_transcripts["ingress_bridge_node_info"].decode("utf-8"),
        "clock_bridge": raw_transcripts["clock_bridge_node_info"].decode("utf-8"),
    }
    outputs = {
        "wheel_info": b"Type: nav_msgs/msg/Odometry\nPublisher count: 1\n",
        "imu_info": b"Type: sensor_msgs/msg/Imu\nPublisher count: 1\n",
        "filtered_info": b"Type: nav_msgs/msg/Odometry\nPublisher count: 1\n",
        "wheel_echo": b"header:\n  stamp: {sec: 1, nanosec: 1}\n  frame_id: odom\nchild_frame_id: base_link\ntwist: {twist: {linear: {x: 0.1, y: 0.0, z: 0.0}}}\n",
        "imu_echo": b"header:\n  stamp: {sec: 1, nanosec: 2}\n  frame_id: base_link\norientation: {x: 0.0, y: 0.0, z: 0.0, w: 1.0}\n",
        "ekf_use_sim_time": b"Boolean value is: True\n",
        "ingress_use_sim_time": b"Boolean value is: True\n",
        "ekf_node_info": infos["ekf"].encode(),
        "ingress_node_info": infos["ingress"].encode(),
        "ingress_bridge_node_info": infos["ingress_bridge"].encode(),
        "clock_bridge_node_info": infos["clock_bridge"].encode(),
        "set_pose_info": b"Type: geometry_msgs/msg/PoseWithCovarianceStamped\nPublisher count: 0\nSubscription count: 1\nNode name: ekf_filter_node\nEndpoint type: SUBSCRIPTION\n",
        "set_pose_echo": b"",
        "set_pose_echo_exit_code": b"124",
    }
    observer = {"acceptance": {"filtered_odometry_minimum_five_contract_and_monotonicity": True}}
    result = runner._evaluate_acceptance(outputs, observer, {})
    assert result["ekf_inputs_and_outputs_bounded"] is True
    assert result["forbidden_topics_and_processes_absent"] is True


def test_ros_standard_endpoints_are_direction_allowlisted_only():
    infos = _valid_node_infos()
    assert runner._topic_policy_violations(infos) == []
    infos["ekf"] = _node(
        ("/clock", "/imu/data", "/wheel/odometry_raw", "/set_pose", "/rosout"),
        ("/odometry/filtered", "/tf", "/diagnostics", "/parameter_events"),
    )
    violations = runner._topic_policy_violations(infos)
    assert any(row["reason"] == "ROS_STANDARD_ENDPOINT_WRONG_DIRECTION" and row["topics"] == ["/rosout"] for row in violations)
