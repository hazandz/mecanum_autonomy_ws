"""Offline synthetic-repository tests for the future one-shot 6F runner."""

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


def test_guard_atomic_capacity_one_acquire_and_rejects_second_acquire(tmp_path):
    path = tmp_path / "guard.json"
    path.write_bytes(json.dumps({
        "run_id": guard.RUN_ID,
        "gz_partition": guard.PARTITION,
        "state": guard.PENDING,
        "capacity": 1,
    }, sort_keys=True, separators=(",", ":")).encode())
    acquired = guard.acquire_guard(path, "a" * 40, "b" * 40)
    assert acquired["state"] == guard.CONSUMED
    assert acquired["capacity"] == 1
    assert acquired["acquisition_count"] == 1
    with pytest.raises(guard.GuardError, match="GUARD_CAPACITY_CONSUMED"):
        guard.acquire_guard(path, "a" * 40, "b" * 40)


def test_bootstrap_readiness_and_stability_fail_closed():
    assert runner._bootstrap_readiness_and_stability(True, True) == {
        "bootstrap_readiness": True, "bootstrap_stability_20_seconds": True
    }
    assert runner._bootstrap_readiness_and_stability(False, True)["bootstrap_readiness"] is False
    assert runner._bootstrap_readiness_and_stability(True, False)["bootstrap_stability_20_seconds"] is False


def test_wheel_and_imu_input_acceptance_is_fail_closed():
    wheel = {"header": {"frame_id": "odom", "stamp": {"sec": 1, "nanosec": 0}},
             "child_frame_id": "base_link", "twist": {"twist": {"linear": {"x": 0.1, "y": 0.0, "z": 0.0}}}}
    imu = {"header": {"frame_id": "base_link", "stamp": {"sec": 1, "nanosec": 0}},
           "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},
           "angular_velocity": {"x": 0.0, "y": 0.0, "z": 0.0},
           "linear_acceleration": {"x": 0.0, "y": 0.0, "z": 0.0}}
    assert runner._wheel_imu_sample_contract(wheel, imu, True, True) == {
        "wheel_sample_contract": True, "imu_sample_contract": True
    }
    assert runner._wheel_imu_sample_contract(wheel, imu, False, True)["wheel_sample_contract"] is False
    bad_imu = {**imu, "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 0.5}}
    assert runner._wheel_imu_sample_contract(wheel, bad_imu, True, True)["imu_sample_contract"] is False


def test_composite_liveness_and_teardown_acceptance_fail_closed():
    assert runner._composite_liveness(True, True)
    assert not runner._composite_liveness(False, True)
    clean = [
        {"name": "composite", "outcome": "STOPPED", "final_snapshot": {"live_members": [], "zombie_members": []}},
        {"name": "bootstrap", "outcome": "STOPPED", "final_snapshot": {"live_members": [], "zombie_members": []}},
    ]
    assert runner._teardown_is_clean(clean)
    assert not runner._teardown_is_clean(list(reversed(clean)))
    assert not runner._teardown_is_clean(clean[:1])
    assert not runner._teardown_is_clean([{**clean[0], "final_snapshot": {"live_members": [{"pid": 1}], "zombie_members": []}}, clean[1]])


def test_runtime_host_preflight_failure_happens_before_guard_or_run_dir(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    root.mkdir()
    run_dir = tmp_path / "future-run"
    monkeypatch.setattr(runner, "verify_runtime_preconditions", lambda *args: {"source_pins": {}})
    monkeypatch.setattr(runner, "_host_preflight", lambda root: (_ for _ in ()).throw(guard.GuardError("GETIFADDRS_UNAVAILABLE")))
    acquire = Mock(side_effect=AssertionError("guard must remain pending"))
    monkeypatch.setattr(runner, "acquire_guard", acquire)
    with pytest.raises(guard.GuardError, match="GETIFADDRS_UNAVAILABLE"):
        runner.run_session(root, tmp_path / "guard.json", run_dir, guard.RUN_ID, guard.PARTITION, "a" * 40, "b" * 40)
    acquire.assert_not_called()
    assert not run_dir.exists()


def test_source_preflight_and_import_checks_precede_guard_acquisition():
    import ast

    tree = ast.parse((TOOLS / "run_wp06_6f_tf_ekf_session.py").read_text(encoding="utf-8"))
    run_session = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "run_session")
    source = (TOOLS / "run_wp06_6f_tf_ekf_session.py").read_text(encoding="utf-8")
    positions = [source.index(name + "(", source.index("def run_session")) for name in (
        "verify_runtime_preconditions", "_host_preflight", "_stale_processes", "acquire_guard"
    )]
    assert positions == sorted(positions)
    assert "importlib" in (TOOLS / "run_wp06_6f_tf_ekf_session.py").read_text(encoding="utf-8")


def test_tf_observer_contract_requires_unique_dynamic_gid_and_static_xacro_transform():
    import importlib.util
    observer_path = ROOT / "ros2_ws/src/mecanum_nav_bringup/mecanum_nav_bringup/sim_eval_tf_ekf_runtime_observer.py"
    module = _load("wp06_6f_observer_runtime_test", observer_path)
    test_path = ROOT / "ros2_ws/src/mecanum_nav_bringup/test/test_sim_eval_tf_ekf_runtime_observer.py"
    test_module = _load("wp06_6f_observer_fixtures", test_path)
    observations, qos = test_module._observation()
    result = module.evaluate_observations(observations, qos)["acceptance"]
    assert result["dynamic_odom_to_base_link_minimum_five_strictly_increasing_single_gid"] is True
    assert result["static_base_link_to_lidar_frame_qos_and_transform_exact"] is True
    observations["/tf"]["transforms"].append({**observations["/tf"]["transforms"][0], "publisher_gid": "second-gid", "stamp_ns": 15})
    assert module.evaluate_observations(observations, qos)["acceptance"]["dynamic_odom_to_base_link_minimum_five_strictly_increasing_single_gid"] is False


def test_node_info_topic_parser_is_edge_and_section_specific():
    sample = """/ekf_filter_node
  Subscribers:
    /clock: rosgraph_msgs/msg/Clock
    /imu/data: sensor_msgs/msg/Imu
  Publishers:
    /odometry/filtered: nav_msgs/msg/Odometry
    /parameter_events: rcl_interfaces/msg/ParameterEvent
"""
    assert runner._node_section_topics(sample, "Subscribers") == {"/clock", "/imu/data"}
    assert runner._data_topics(sample, "Publishers") == {"/odometry/filtered"}


def test_forbidden_runtime_boundary_is_fail_closed():
    assert runner._forbidden_process_present({"commands": [{"command": "ros2 run nav2_controller controller_server"}]})
    assert not runner._forbidden_process_present({"commands": [{"command": "ros2 launch mecanum_nav_bringup sim_eval_tf_ekf_state_estimation.launch.py"}]})


def test_yaml_parser_uses_multi_document_load_and_requires_one_mapping():
    assert runner._parse_single_yaml_mapping(b"---\nheader:\n  frame_id: odom\n---\n") == {"header": {"frame_id": "odom"}}
    with pytest.raises(ValueError, match="EXPECTED_EXACTLY_ONE_YAML_MAPPING"):
        runner._parse_single_yaml_mapping(b"---\na: 1\n---\nb: 2\n")


def test_supervisor_has_no_legacy_launch_or_forbidden_bridge_route():
    source = (TOOLS / "run_wp06_6f_tf_ekf_session.py").read_text(encoding="utf-8")
    assert "sim_eval_scan_probe_bootstrap.launch.py" in source
    assert "sim_eval_tf_ekf_state_estimation.launch.py" in source
    assert "gazebo.launch.py" not in source
    assert "parameter_bridge" not in source
    assert "os.killpg" in source
    assert "start_new_session=True" in source
    assert "collect_and_write(observer_path, timeout_seconds=30.0)" in source
    assert source.count("collect_and_write(observer_path") == 1
    assert '"clock_echo"' not in source
    assert '"filtered_echo"' not in source


def test_runner_manifest_matrix_and_synthetic_preflight_failure_are_fail_closed(tmp_path, monkeypatch):
    observer_path = ROOT / "ros2_ws/src/mecanum_nav_bringup/mecanum_nav_bringup/sim_eval_tf_ekf_runtime_observer.py"
    module = _load("wp06_6f_observer_matrix_test", observer_path)
    required = {
        "bootstrap_readiness", "bootstrap_stability_20_seconds", "composite_liveness",
        "clock_five_monotonic_samples", "wheel_input", "imu_input",
        "filtered_odometry_five_monotonic_samples", "dynamic_tf_edge_gid", "static_tf_edge_qos",
        "map_to_odom_absent", "forbidden_bridge_and_process_boundary", "process_group_teardown",
    }
    matrix = {row["acceptance_id"]: row for row in module.RUNTIME_ACCEPTANCE_MATRIX}
    assert required <= matrix.keys()
    assert all(matrix[name]["raw_artifact_path"] and matrix[name]["offline_test_name"] for name in required)
    assert "runtime_observer.json" in str(matrix["clock_five_monotonic_samples"]["raw_artifact_path"])

    root = tmp_path / "repo"
    root.mkdir()
    run_dir = tmp_path / "unused-run-dir-for-synthetic-test"
    acquire = Mock(side_effect=AssertionError("guard must remain pending on preflight failure"))
    monkeypatch.setattr(runner, "verify_runtime_preconditions", lambda *args: {"source_pins": {}})
    monkeypatch.setattr(runner, "acquire_guard", acquire)
    monkeypatch.setattr(runner.importlib, "import_module", lambda name: type("M", (), {"RUNTIME_ACCEPTANCE_MATRIX": module.RUNTIME_ACCEPTANCE_MATRIX})())
    monkeypatch.setattr(runner, "_stale_processes", lambda: None)
    monkeypatch.setattr(runner, "_host_preflight", lambda root: (_ for _ in ()).throw(guard.GuardError("GETIFADDRS_UNAVAILABLE")))
    with pytest.raises(guard.GuardError, match="GETIFADDRS_UNAVAILABLE"):
        runner.run_session(root, tmp_path / "guard.json", run_dir, guard.RUN_ID, guard.PARTITION, "a" * 40, "b" * 40)
    acquire.assert_not_called()
    assert not run_dir.exists()
