"""Offline synthetic tests for the future WP06-6F Run002 supervisor."""
import importlib.util
import json
from pathlib import Path
import sys
from unittest.mock import Mock

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


guard = _load("wp06_6f_guard_test", TOOLS / "wp06_6f_tf_ekf_runtime_guard.py")
sys.modules["wp06_6f_tf_ekf_runtime_guard"] = guard
runner = _load("wp06_6f_runner_test", TOOLS / "run_wp06_6f_tf_ekf_session.py")


def test_run002_guard_atomic_capacity_one_acquire_and_rejects_second_acquire(tmp_path):
    path = tmp_path / "guard.json"
    path.write_bytes(json.dumps({"run_id": guard.RUN_ID, "gz_partition": guard.PARTITION,
        "state": guard.PENDING, "capacity": 1, "acquisition_count": 0,
        "runtime_authorization": "NOT_GRANTED"}, sort_keys=True, separators=(",", ":")).encode())
    acquired = guard.acquire_guard(path, "a" * 40, "b" * 40)
    assert guard.RUN_ID.endswith("RUN_002")
    assert acquired["state"] == guard.CONSUMED and acquired["acquisition_count"] == 1
    with pytest.raises(guard.GuardError, match="GUARD_CAPACITY_CONSUMED"):
        guard.acquire_guard(path, "a" * 40, "b" * 40)


def test_bootstrap_readiness_and_stability_fail_closed():
    assert runner._bootstrap_readiness_and_stability(True, True) == {"bootstrap_readiness": True, "bootstrap_stability_20_seconds": True}
    assert not runner._bootstrap_readiness_and_stability(False, True)["bootstrap_readiness"]
    assert not runner._bootstrap_readiness_and_stability(True, False)["bootstrap_stability_20_seconds"]


def test_wheel_imu_and_node_info_contracts_remain_fail_closed():
    wheel = {"header": {"frame_id": "odom", "stamp": {"sec": 1, "nanosec": 0}}, "child_frame_id": "base_link",
             "twist": {"twist": {"linear": {"x": 0.1, "y": 0.0, "z": 0.0}}}}
    imu = {"header": {"frame_id": "base_link", "stamp": {"sec": 1, "nanosec": 0}},
           "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0}}
    assert runner._wheel_imu_sample_contract(wheel, imu, True, True) == {"wheel_sample_contract": True, "imu_sample_contract": True}
    sample = "/ekf_filter_node\n  Subscribers:\n    /clock: rosgraph_msgs/msg/Clock\n  Publishers:\n    /odometry/filtered: nav_msgs/msg/Odometry\n    /parameter_events: x\n"
    assert runner._data_topics(sample, "Publishers") == {"/odometry/filtered"}


def test_teardown_uses_exact_single_predicate_and_detects_aggregate_mismatch():
    clean = [{"name": n, "leader_returncode": 0, "live_member_pids": [], "zombie_member_pids": [], "outcome": "STOPPED"}
             for n in ("composite", "bootstrap")]
    assert runner._teardown_is_clean(clean)
    assert runner._teardown_order_and_count_correct(clean)
    assert runner._teardown_verdict(clean, True) is True
    assert runner._teardown_verdict(clean, False) == "INTERNAL_EVIDENCE_INCONSISTENCY"
    assert not runner._teardown_is_clean([{**clean[0], "leader_returncode": 130}, clean[1]])
    assert not runner._teardown_is_clean([{**clean[0], "live_member_pids": [22]}, clean[1]])
    assert runner._teardown_is_clean(list(reversed(clean)))
    assert not runner._teardown_order_and_count_correct(list(reversed(clean)))


def test_synthetic_host_preflight_failure_leaves_guard_unacquired_and_run_dir_absent(tmp_path, monkeypatch):
    root = tmp_path / "repo"; root.mkdir()
    run_dir = tmp_path / "run"
    monkeypatch.setattr(runner, "verify_runtime_preconditions", lambda *args: {"guard": {"state": guard.PENDING}, "source_pins": {}})
    monkeypatch.setattr(runner, "_host_preflight", lambda root: (_ for _ in ()).throw(guard.GuardError("GETIFADDRS_UNAVAILABLE")))
    acquire = Mock(side_effect=AssertionError("must remain pending"))
    monkeypatch.setattr(runner, "acquire_guard", acquire)
    with pytest.raises(guard.GuardError, match="GETIFADDRS_UNAVAILABLE"):
        runner.run_session(root, tmp_path / "guard.json", run_dir, guard.RUN_ID, guard.PARTITION, "a" * 40, "b" * 40)
    acquire.assert_not_called(); assert not run_dir.exists()


def test_runner_has_single_cpp_observer_invocation_and_no_python_runtime_subscriber():
    source = (TOOLS / "run_wp06_6f_tf_ekf_session.py").read_text(encoding="utf-8")
    assert source.count("_run_cpp_observer(") == 2
    assert "collect_and_write" not in source and "RUNTIME_ACCEPTANCE_MATRIX" not in source
    assert "gazebo.launch.py" not in source
    observer = (ROOT / "ros2_ws/src/mecanum_nav_bringup/mecanum_nav_bringup/sim_eval_tf_ekf_runtime_observer.py").read_text(encoding="utf-8")
    assert "create_subscription" not in observer and "with_info=" not in observer


def test_acceptance_matrix_has_collector_artifact_parser_and_offline_test():
    manifest_path = ROOT / "docs/governance/evidence/WP-06_6F_TF_EKF_RUNTIME_INGRESS_RUN_002_GUARD_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    matrix = manifest["acceptance_to_collector_matrix"]
    required = {"bootstrap_readiness", "bootstrap_stability_20_seconds", "composite_liveness", "composite_stability_5_seconds",
                "clock_five_monotonic_samples", "wheel_input", "imu_input", "ingress_use_sim_time",
                "filtered_odometry_five_monotonic_samples", "ekf_use_sim_time", "ekf_topology", "dynamic_tf_edge_gid",
                "static_tf_edge_qos", "map_to_odom_absent", "forbidden_bridge_and_process_boundary", "process_group_teardown",
                "process_group_teardown_order", "observer_error_absent"}
    assert required <= {item["acceptance_id"] for item in matrix}
    assert all(all(item.get(k) for k in ("collector", "raw_artifact_path", "parser_or_validator", "pass_condition", "failure_reason_literal", "offline_test_name")) for item in matrix)
    assert any("runtime_observer.json" in item["raw_artifact_path"] for item in matrix)


def test_yaml_echo_parser_uses_multi_document_and_requires_single_mapping():
    assert runner._parse_single_yaml_mapping(b"---\na: 1\n---\n") == {"a": 1}
    with pytest.raises(ValueError, match="EXPECTED_EXACTLY_ONE_YAML_MAPPING"):
        runner._parse_single_yaml_mapping(b"---\na: 1\n---\nb: 2\n")


def test_forbidden_process_boundary():
    assert runner._forbidden_process_present({"commands": [{"command": "ros2 run nav2_controller controller_server"}]})
    assert not runner._forbidden_process_present({"commands": [{"command": "ros2 launch mecanum_nav_bringup sim_eval_tf_ekf_state_estimation.launch.py"}]})
