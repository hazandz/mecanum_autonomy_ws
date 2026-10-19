import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess

import pytest
import xml.etree.ElementTree as ET

RUNNER_PATH = Path(__file__).with_name("run_step07_nav2_baseline_run003.py")
ROOT = Path(__file__).resolve().parents[4]
SPEC = importlib.util.spec_from_file_location("step07_run003_runner_test", RUNNER_PATH)
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)

DEPOT_URI = "https://fuel.gazebosim.org/1.0/OpenRobotics/models/Depot"
TUGBOT_URI = "https://fuel.gazebosim.org/1.0/MovAi/models/Tugbot"
FUEL_URIS = [DEPOT_URI, TUGBOT_URI]


def _valid_fuel_cache(root):
    for owner, model in (("openrobotics", "depot"), ("movai", "tugbot")):
        version = root / "fuel.gazebosim.org" / owner / "models" / model / "1"
        version.mkdir(parents=True)
        (version / "model.config").write_text("<model><name>x</name></model>")
        (version / "model.sdf").write_text("<sdf version='1.9'/>")
    return root


def _validate_layout(root):
    return runner.validate_fuel_cache_layout(FUEL_URIS, root, root)


def _strict_load(path):
    return runner.load_canonical_json(path)


@pytest.mark.parametrize("failure_site", ["prepare", "host"])
def test_preacquire_build_or_host_failure_writes_complete_audit_without_guard_or_runtime(
    tmp_path, monkeypatch, failure_site
):
    runtime_worktree = tmp_path / "runtime-worktree"
    runtime_worktree.mkdir()
    run_directory = tmp_path / "evidence"
    guard = {"run_id": runner.RUN_ID, "state": runner.PENDING,
             "capacity": 1, "acquisition_count": 0,
             "runtime_authorization": "NOT_GRANTED"}
    guard_path = runtime_worktree / "guard.json"
    guard_raw = json.dumps(guard, sort_keys=True, separators=(",", ":")).encode()
    guard_path.write_bytes(guard_raw)
    lock = guard_path.with_suffix(".json.lock")
    calls = {"prepare": 0, "host": 0, "acquire": 0}

    def prepare(_worktree, _dirs):
        calls["prepare"] += 1
        assert runtime_worktree.is_dir()
        assert not run_directory.exists(), "evidence is created only after auditable preflight phase starts"
        if failure_site == "prepare":
            raise RuntimeError("SIMULATED_PREPARE_FAILURE")
        return {"ROS_DISTRO": "jazzy"}

    def host(*_args):
        calls["host"] += 1
        assert not run_directory.exists()
        raise OSError("SIMULATED_HOST_PREFLIGHT_FAILURE")

    def acquire(*_args, **_kwargs):
        calls["acquire"] += 1
        raise AssertionError("guard acquisition must not be reached")

    monkeypatch.setattr(runner, "prepare_ros_environment", prepare)
    monkeypatch.setattr(runner, "host_preflight", host)
    monkeypatch.setattr(runner, "acquire_guard", acquire)
    record = {"schema_version": "1.0", "run_id": runner.RUN_ID,
              "review_commit": "a" * 40,
              "integration_base": runner.INTEGRATION_BASE,
              "partition": runner.PARTITION,
              "guard_state_before": runner.PENDING}
    env, preflight, consumed, failure = runner.preacquire_preflight(
        runtime_worktree, {"build": tmp_path / "build"}, run_directory,
        runner.PARTITION, tmp_path / "map", tmp_path / "fuel", {},
        guard_path, lock, guard, {}, "a" * 40, runner.INTEGRATION_BASE, record,
    )

    assert env is preflight is consumed is None
    assert failure["terminal_outcome"] == runner.PREACQUIRE_TERMINAL
    assert failure["runner_invoked"] is True
    assert failure["preacquire_failure_literal"].startswith(
        f"PREACQUIRE_FAILURE:{'RuntimeError' if failure_site == 'prepare' else 'OSError'}:SIMULATED_"
    )
    assert failure["exception_type"] == ("RuntimeError" if failure_site == "prepare" else "OSError")
    assert failure["exception_message"] == ("SIMULATED_PREPARE_FAILURE" if failure_site == "prepare"
                                              else "SIMULATED_HOST_PREFLIGHT_FAILURE")
    assert failure["traceback"] and failure["teardown_applicable"] is False
    assert failure["runtime_execution"] is False and failure["guard_acquired"] is False
    assert failure["guard_state_before"] == failure["guard_state_after"] == runner.PENDING
    assert failure["authorization_acquisition_count"] == 0
    assert failure["guard_capacity"] == 1 and failure["guard_acquisition_count"] == 0
    assert failure["call_counts"] == {"runner": 1, "bootstrap": 0, "composite": 0,
                                       "cpp_observer": 0, "gate_b_observer": 0}
    assert calls["acquire"] == 0
    assert calls["host"] == (0 if failure_site == "prepare" else 1)
    assert guard_path.read_bytes() == guard_raw
    assert not lock.exists()
    assert {path.name for path in run_directory.iterdir()} == {
        "run_record.json", "preflight_failure.json", "artifact_manifest.json", "SHA256SUMS.txt"
    }
    run_record = _strict_load(run_directory / "run_record.json")
    failure_doc = _strict_load(run_directory / "preflight_failure.json")
    manifest = _strict_load(run_directory / "artifact_manifest.json")
    assert run_record["preacquire_failure_literal"] == failure_doc["failure_literal"]
    assert run_record["guard_capacity"] == failure_doc["guard_capacity"] == 1
    assert run_record["guard_acquisition_count"] == failure_doc["guard_acquisition_count"] == 0
    assert run_record["terminal_outcome"] == failure_doc["terminal_outcome"] == runner.PREACQUIRE_TERMINAL
    assert {entry["path"] for entry in manifest["artifacts"]} == {"run_record.json", "preflight_failure.json"}
    for entry in manifest["artifacts"]:
        raw = (run_directory / entry["path"]).read_bytes()
        assert entry["sha256"] == hashlib.sha256(raw).hexdigest()
        assert entry["size_bytes"] == len(raw)
    sums = {}
    for line in (run_directory / "SHA256SUMS.txt").read_text().splitlines():
        digest, path = line.split("  ", 1)
        sums[path] = digest
    for name in ("run_record.json", "preflight_failure.json", "artifact_manifest.json"):
        assert sums[name] == hashlib.sha256((run_directory / name).read_bytes()).hexdigest()


@pytest.mark.parametrize("raw", [
    b'{"x":1,"x":2}', b'{"x":Infinity}', b'\xef\xbb\xbf{}', b'{}\n', b'not-json',
])
def test_canonical_json_loader_rejects_duplicate_nonfinite_bom_final_newline_and_invalid_json(tmp_path, raw):
    path = tmp_path / "document.json"
    path.write_bytes(raw)
    with pytest.raises((ValueError, json.JSONDecodeError)):
        _strict_load(path)


def test_success_path_acquires_guard_before_any_campaign_process_and_finalizes_after_teardown(tmp_path, monkeypatch):
    runtime_worktree = tmp_path / "runtime"
    runtime_worktree.mkdir()
    evidence = tmp_path / "evidence"
    guard_path = runtime_worktree / "guard.json"
    guard = {"state": runner.PENDING, "acquisition_count": 0}
    calls = []

    monkeypatch.setattr(runner, "prepare_ros_environment", lambda *_: calls.append("build") or {"PATH": ""})
    monkeypatch.setattr(runner, "host_preflight", lambda *_: calls.append("host") or {"ready": True})

    def acquire(*_args, **_kwargs):
        calls.append("acquire")
        return {"state": "CONSUMED", "acquisition_count": 1}

    monkeypatch.setattr(runner, "acquire_guard", acquire)
    env, preflight, consumed, failure = runner.preacquire_preflight(
        runtime_worktree, {}, evidence, runner.PARTITION, tmp_path / "map", tmp_path / "fuel",
        {}, guard_path, guard_path.with_suffix(".json.lock"), guard, {}, "a" * 40,
        runner.INTEGRATION_BASE, {"call_counts": {"runner": 1}},
    )
    assert calls == ["build", "host", "acquire"]
    assert env["PATH"] == "" and preflight == {"ready": True}
    assert consumed == {"state": "CONSUMED", "acquisition_count": 1}
    assert failure is None and not evidence.exists()

    bootstrap = {"pid": 31, "pgid": 31, "initial_snapshot": {"live_member_pids": [31]}}
    composite = {"pid": 32, "pgid": 32, "initial_snapshot": {"live_member_pids": [32]}}
    runner.validate_distinct_process_groups(bootstrap, composite)
    result = runner.finalise_after_teardown(
        {}, {"guard_acquired_once": True, "runtime_acceptance": True},
        {"completed": True, "clean": True, "order_correct": True},
    )
    assert result["terminal_outcome"].endswith("PASS_PENDING_INDEPENDENT_EVIDENCE_AUDIT")
    assert all(result["acceptance"].values())
    source = RUNNER_PATH.read_text()
    assert source.index("preacquire_preflight(") < source.index("_spawn_owned_process(", source.index("def main():"))
    assert source.index("composite_teardown = _stop_owned_process") < source.index("bootstrap_teardown = _stop_owned_process")


def test_process_groups_and_final_record_fail_closed():
    with pytest.raises(RuntimeError, match="CAMPAIGN_PROCESS_GROUP_MISSING"):
        runner.validate_distinct_process_groups(None, {})
    bootstrap = {"pid": 31, "pgid": 31, "initial_snapshot": {"live_member_pids": [31]}}
    same = {"pid": 31, "pgid": 31, "initial_snapshot": {"live_member_pids": [31]}}
    with pytest.raises(RuntimeError, match="CAMPAIGN_PROCESS_GROUPS_NOT_DISTINCT"):
        runner.validate_distinct_process_groups(bootstrap, same)
    with pytest.raises(ValueError, match="TEARDOWN_NOT_COMPLETED_BEFORE_FINALIZATION"):
        runner.finalise_after_teardown({}, {"all": True}, {"completed": False})


def test_fuel_cache_accepts_exact_lowercase_owner_model_layout(tmp_path):
    root = _valid_fuel_cache(tmp_path / "fuel")
    resolved = _validate_layout(root)
    assert set(resolved) == set(FUEL_URIS)
    assert resolved[DEPOT_URI].endswith("openrobotics/models/depot/1")
    assert resolved[TUGBOT_URI].endswith("movai/models/tugbot/1")


def test_canonical_sdf_preserves_exact_case_sensitive_fuel_uris():
    sdf = ET.parse(ROOT / runner.WORLD_REL).getroot()
    uris = [node.text.strip() for node in sdf.iter("uri")
            if node.text and "fuel.gazebosim.org" in node.text]
    assert len(uris) == 2 and set(uris) == set(FUEL_URIS)
    assert runner.FUEL_URI_MAPPING[DEPOT_URI][:2] == ("openrobotics", "depot")
    assert runner.FUEL_URI_MAPPING[TUGBOT_URI][:2] == ("movai", "tugbot")


def test_fuel_cache_rejects_uppercase_owner_model_paths(tmp_path):
    root = tmp_path / "fuel"
    for owner, model in (("OpenRobotics", "Depot"), ("MovAi", "Tugbot")):
        version = root / "fuel.gazebosim.org" / owner / "models" / model / "1"
        version.mkdir(parents=True)
        (version / "model.config").write_text("<model/>")
        (version / "model.sdf").write_text("<sdf/>")
    with pytest.raises(RuntimeError, match="FUEL_MODEL_PARENT_CASE_MISMATCH|FUEL_MODEL_PARENT_INVALID"):
        _validate_layout(root)


@pytest.mark.parametrize("mutation,expected", [
    ("missing", "FUEL_MODEL_PARENT_INVALID"),
    ("ambiguous", "SIM_EVAL_FUEL_CACHE_VERSION_AMBIGUOUS_OR_MISSING"),
    ("missing_config", "SIM_EVAL_FUEL_CACHE_VERSION_AMBIGUOUS_OR_MISSING"),
    ("missing_sdf", "SIM_EVAL_FUEL_CACHE_VERSION_AMBIGUOUS_OR_MISSING"),
    ("symlink_escape", "FUEL_CACHE_PATH_ESCAPES_ROOT"),
])
def test_fuel_cache_invalid_layout_fails_closed(tmp_path, mutation, expected):
    root = _valid_fuel_cache(tmp_path / "fuel")
    depot = root / "fuel.gazebosim.org/openrobotics/models/depot"
    if mutation == "missing":
        import shutil
        shutil.rmtree(depot)
    elif mutation == "ambiguous":
        version = depot / "2"; version.mkdir()
        (version / "model.config").write_text("<model/>")
        (version / "model.sdf").write_text("<sdf/>")
    elif mutation == "missing_config":
        (depot / "1/model.config").unlink()
    elif mutation == "missing_sdf":
        (depot / "1/model.sdf").unlink()
    elif mutation == "symlink_escape":
        outside = tmp_path / "outside.sdf"; outside.write_text("<sdf/>")
        (depot / "1/model.sdf").unlink()
        (depot / "1/model.sdf").symlink_to(outside)
    with pytest.raises(RuntimeError, match=expected):
        _validate_layout(root)


def test_fuel_cache_rejects_custom_root_and_non_exact_uri_set(tmp_path):
    root = _valid_fuel_cache(tmp_path / "fuel")
    with pytest.raises(RuntimeError, match="FUEL_CACHE_ROOT_NOT_CANONICAL"):
        runner.validate_fuel_cache_layout(FUEL_URIS, root, tmp_path / "other")
    with pytest.raises(RuntimeError, match="FUEL_URI_SET_MISMATCH"):
        runner.validate_fuel_cache_layout([DEPOT_URI, DEPOT_URI], root, root)


def test_fuel_validation_has_no_ambiguous_recursive_lookup_or_download_path():
    source = RUNNER_PATH.read_text(encoding="utf-8")
    fuel_function = source[source.index("def validate_fuel_cache_layout"):source.index("def stale_partition_processes")]
    assert ".rglob(" not in fuel_function
    assert "gz fuel download" not in source
    assert "OpenRobotics/models/Depot" in source and "MovAi/models/Tugbot" in source
