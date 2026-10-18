"""Offline finalization-order regression tests for WP06-6F Run007."""
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


guard = _load("wp06_6f_run007_guard_test", TOOLS / "wp06_6f_tf_ekf_run007_runtime_guard.py")
sys.modules["wp06_6f_tf_ekf_run007_runtime_guard"] = guard
runner = _load("wp06_6f_run007_runner_test", TOOLS / "run_wp06_6f_tf_ekf_run007_session.py")

RUNTIME_KEYS = (
    "bootstrap_readiness", "bootstrap_stability_20_seconds", "composite_live_through_evidence",
    "composite_stability_5_seconds", "clock_minimum_five_nonzero_strictly_increasing",
    "wheel_info_one_publisher_and_type", "imu_info_one_publisher_and_type",
    "filtered_info_one_publisher_and_type", "wheel_sample_contract", "imu_sample_contract",
    "filtered_odometry_minimum_five_contract_and_monotonicity",
    "dynamic_odom_to_base_link_minimum_five_strictly_increasing_single_gid_owned_by_ekf",
    "dynamic_tf_subscription_qos_contract", "static_base_link_to_lidar_frame_exact",
    "static_tf_edge_publisher_gid_mappable", "static_tf_edge_publisher_gid_unique_mapped",
    "static_tf_owner_is_robot_state_publisher", "static_tf_subscription_qos_contract",
    "map_to_odom_absent_during_full_window", "observer_errors_absent", "ekf_use_sim_time_true",
    "ingress_use_sim_time_true", "ekf_inputs_and_outputs_bounded", "ekf_set_pose_admin_endpoint",
    "ekf_set_pose_zero_publishers_no_payload", "ingress_outputs_bounded",
    "ingress_bridge_outputs_bounded", "clock_bridge_outputs_only_clock",
    "forbidden_topics_and_processes_absent", "runtime_session_completed_without_exception",
)


def _record(runtime=None, teardown=None):
    return {
        "pre_teardown_runtime_acceptance": dict(runtime or {key: True for key in RUNTIME_KEYS}),
        "teardown_acceptance": dict(teardown or {
            "process_group_teardown_clean": True,
            "teardown_order_and_count_correct": True,
        }),
    }


def test_all_runtime_and_teardown_acceptance_true_passes_only_after_finalization():
    record = _record()
    final = runner._finalize_acceptance(record)
    assert set(final) == set(RUNTIME_KEYS) | {"process_group_teardown_clean", "teardown_order_and_count_correct"}
    assert all(value is True for value in final.values())
    assert record["terminal_outcome"] == "WP06_6F_RUNTIME_RUN007_PASS_PENDING_INDEPENDENT_EVIDENCE_AUDIT"
    assert "failure" not in record
    assert record["teardown_pass"] is True


def test_dirty_teardown_fails_with_teardown_literal_after_runtime_pass():
    record = _record(teardown={
        "process_group_teardown_clean": False,
        "teardown_order_and_count_correct": True,
    })
    final = runner._finalize_acceptance(record)
    assert all(record["pre_teardown_runtime_acceptance"].values())
    assert final["process_group_teardown_clean"] is False
    assert record["terminal_outcome"] == "WP06_6F_RUNTIME_RUN007_FAIL_NO_RETRY_GUARD_CONSUMED"
    assert record["failure"] == "PROCESS_GROUP_TEARDOWN_FAILED"


def test_runtime_failure_with_clean_teardown_has_runtime_literal():
    runtime = {key: True for key in RUNTIME_KEYS}
    runtime["wheel_sample_contract"] = False
    record = _record(runtime=runtime)
    final = runner._finalize_acceptance(record)
    assert final["process_group_teardown_clean"] is True
    assert record["terminal_outcome"] == "WP06_6F_RUNTIME_RUN007_FAIL_NO_RETRY_GUARD_CONSUMED"
    assert record["failure"] == "RUNTIME_ACCEPTANCE_FAILED:wheel_sample_contract"


def test_final_record_cannot_have_all_true_acceptance_and_fail_outcome():
    good = _record()
    good["acceptance"] = runner._finalize_acceptance(good)
    assert all(good["acceptance"].values())
    assert good["terminal_outcome"].endswith("PASS_PENDING_INDEPENDENT_EVIDENCE_AUDIT")
    bad = _record()
    bad["teardown_acceptance"]["teardown_order_and_count_correct"] = False
    bad["acceptance"] = runner._finalize_acceptance(bad)
    assert not all(bad["acceptance"].values())
    assert bad["terminal_outcome"].endswith("FAIL_NO_RETRY_GUARD_CONSUMED")


def test_offline_run006_record_proves_historical_finalization_order_bug_only():
    path = Path("/home/hazan/wp06_runtime_evidence/WP06_6F_TF_EKF_RUNTIME_INGRESS_RUN_006/run_record.json")
    if not path.is_file():
        pytest.skip("External read-only Run006 record is unavailable")
    raw = path.read_bytes()
    record = json.loads(raw.decode("utf-8"))
    assert record["run_id"] == "WP06_6F_TF_EKF_RUNTIME_INGRESS_RUN_006"
    assert record["terminal_outcome"] == "WP06_6F_RUNTIME_RUN006_FAIL_NO_RETRY_GUARD_CONSUMED"
    assert record["failure"] == "GuardError:RUNTIME_ACCEPTANCE_FAILED"
    assert record["teardown_pass"] is True
    assert record["acceptance"]["process_group_teardown_clean"] is True
    assert record["acceptance"]["teardown_order_and_count_correct"] is True
    assert all(value is True for value in record["acceptance"].values())
    # Historical terminal outcome and evidence are observations only; Run007 is a new implementation.
    source = (TOOLS / "run_wp06_6f_tf_ekf_run006_session.py").read_text(encoding="utf-8")
    assert source.index('raise GuardError("RUNTIME_ACCEPTANCE_FAILED")') < source.index("    finally:")
    assert record["terminal_outcome"].endswith("FAIL_NO_RETRY_GUARD_CONSUMED")


def test_run001_to_run006_guard_manifest_session_sources_are_parent_identical():
    parent = "b502e3e08ffcbe63ffeebad762a13fe419fdcb92"
    changed = set(subprocess.run(["git", "diff", "--name-only", parent], cwd=ROOT, check=True,
                                 capture_output=True, text=True).stdout.splitlines())
    tracked = subprocess.run(["git", "ls-tree", "-r", "--name-only", parent], cwd=ROOT, check=True,
                            capture_output=True, text=True).stdout.splitlines()
    import re
    protected_name = re.compile(r"(?:RUN_00[1-6]|run00[1-6])")
    protected = [p for p in tracked if protected_name.search(p)
                 and ("approval_guards/" in p or "GUARD_MANIFEST" in p or "_session.py" in p or "_runtime_guard.py" in p)]
    assert protected
    for relative in protected:
        assert relative not in changed, relative
        expected = subprocess.run(["git", "show", f"{parent}:{relative}"], cwd=ROOT, check=True,
                                  capture_output=True).stdout
        assert (ROOT / relative).read_bytes() == expected, relative


def test_run007_guard_is_pending_capacity_one_and_run_specific():
    path = ROOT / guard.GUARD_PATH
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["run_id"] == guard.RUN_ID == "WP06_6F_TF_EKF_RUNTIME_INGRESS_RUN_007"
    assert data["state"] == guard.PENDING == "PENDING_EXACT_INTEGRATION_AND_USER_AUTHORIZATION"
    assert data["capacity"] == 1 and data["acquisition_count"] == 0
    assert data["runtime_authorization"] == "NOT_GRANTED"


def test_runner_decides_terminal_outcome_only_in_post_teardown_finalizer():
    import ast
    source = (TOOLS / "run_wp06_6f_tf_ekf_run007_session.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    run_fn = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "run_session")
    finalizer_calls = [node.lineno for node in ast.walk(run_fn)
                       if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                       and node.func.id == "_finalize_acceptance"]
    terminal_assignments = [node.lineno for node in ast.walk(run_fn)
                            if isinstance(node, (ast.Assign, ast.AnnAssign))
                            and "terminal_outcome" in ast.unparse(node)]
    assert len(finalizer_calls) == 1
    assert len(terminal_assignments) == 0
    run_source = ast.get_source_segment(source, run_fn)
    assert run_source.index('record["teardown"] = teardown') < run_source.index('record["acceptance"] = _finalize_acceptance(record)')
    assert 'raise GuardError("RUNTIME_ACCEPTANCE_FAILED")' not in run_source


def test_run007_manifest_guard_and_evidence_are_coherent_and_phase_complete():
    import hashlib
    manifest_path = ROOT / guard.MANIFEST_PATH
    evidence_path = ROOT / guard.EVIDENCE_PATH
    guard_path = ROOT / guard.GUARD_PATH
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    seed = json.loads(guard_path.read_text(encoding="utf-8"))
    assert manifest["run_id"] == evidence["run_id"] == seed["run_id"] == guard.RUN_ID
    assert manifest["acceptance_to_collector_matrix"] == evidence["acceptance_to_collector_matrix"]
    phases = {row["acceptance_id"]: row["phase"] for row in manifest["acceptance_to_collector_matrix"]}
    assert phases["process_group_teardown"] == "teardown_acceptance"
    assert phases["process_group_teardown_order"] == "teardown_acceptance"
    assert phases["runtime_session_completed_without_exception"] == "pre_teardown_runtime_acceptance"
    assert all(value == "pre_teardown_runtime_acceptance" for key, value in phases.items()
               if key not in {"process_group_teardown", "process_group_teardown_order"})
    assert seed["state"] == guard.PENDING and seed["capacity"] == 1
    assert seed["acquisition_count"] == 0 and seed["runtime_authorization"] == "NOT_GRANTED"
    assert hashlib.sha256(manifest_path.read_bytes()).hexdigest() == seed["guard_manifest_sha256"]
    assert hashlib.sha256(evidence_path.read_bytes()).hexdigest() == manifest["evidence_sha256"]
    assert manifest["decision_sha256"] == seed["decision_sha256"]
    matrix_ids = {row["acceptance_id"] for row in manifest["acceptance_to_collector_matrix"]}
    assert matrix_ids == guard_required_ids()
    pins = manifest["source_pins"]
    assert pins == evidence["source_pins"]
    for relative, expected in pins.items():
        assert len(expected) == 64
        assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == expected, relative


def guard_required_ids():
    return {
        "bootstrap_readiness", "bootstrap_stability_20_seconds", "composite_liveness", "composite_stability_5_seconds",
        "clock_five_monotonic_samples", "wheel_input", "imu_input", "ingress_use_sim_time",
        "filtered_odometry_five_monotonic_samples", "ekf_use_sim_time", "ekf_topology",
        "dynamic_tf_edge_gid", "dynamic_tf_subscription_qos", "static_tf_edge_qos",
        "static_tf_owner_gid_mappable", "static_tf_owner_gid_unique", "static_tf_owner_gid",
        "static_tf_subscription_qos", "map_to_odom_absent", "forbidden_bridge_and_process_boundary",
        "process_group_teardown", "process_group_teardown_order", "observer_error_absent",
        "ekf_set_pose_admin_endpoint", "ekf_set_pose_zero_publishers_no_payload",
        "runtime_session_completed_without_exception",
    }
