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
    records = []
    for stamp in range(10, 15):
        records.append({"topic": "/tf", "parent": "odom", "child": "base_link", "stamp_ns": stamp,
                        "publisher_gid": "ekf-gid", "translation": [0.0, 0.0, 0.0], "rotation_xyzw": [0.0, 0.0, 0.0, 1.0]})
    records.append({"topic": "/tf_static", "parent": "base_link", "child": "lidar_frame", "stamp_ns": 0,
                    "publisher_gid": "rsp-gid", "translation": [-0.031765, 0.0, 0.140], "rotation_xyzw": [0.0, 0.0, 0.0, 1.0]})
    result = runner._tf_acceptance(records)
    assert result["dynamic_edge_samples"] == 5
    assert result["dynamic_timestamps_strictly_increasing"] is True
    assert result["dynamic_unique_gid"] is True
    assert result["static_edge_exactly_one_with_xacro_transform"] is True
    assert result["map_to_odom_absent"] is True
    records.append({**records[0], "publisher_gid": "second-gid"})
    assert runner._tf_acceptance(records)["dynamic_unique_gid"] is False


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
