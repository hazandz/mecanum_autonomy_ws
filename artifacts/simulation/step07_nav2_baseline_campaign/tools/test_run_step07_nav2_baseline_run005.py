import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess

import pytest
import xml.etree.ElementTree as ET

RUNNER_PATH = Path(__file__).with_name("run_step07_nav2_baseline_run005.py")
ROOT = Path(__file__).resolve().parents[4]
SPEC = importlib.util.spec_from_file_location("step07_run005_runner_test", RUNNER_PATH)
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


def test_installed_file_closure_rejects_any_artifact_package_without_prefix():
    package = "ROBOT_URDF_final_description"
    prefixes = {name: f"/overlay/{name}" for name in runner.REQUIRED_PACKAGE_PREFIXES
                if name != package}
    with pytest.raises(RuntimeError, match="INSTALLED_FILE_PACKAGE_PREFIX_MISSING:ROBOT_URDF_final_description"):
        runner.validate_installed_file_package_closure(runner.INSTALLED_FILE_ARTIFACTS, prefixes)


def test_host_preflight_collects_complete_prefix_closure_before_installed_byte_checks(
    tmp_path, monkeypatch
):
    import socket
    from types import SimpleNamespace

    assert set(runner.REQUIRED_PACKAGE_PREFIXES) == {
        "ros_gz_sim", "ros_gz_bridge", "mecanum_base_bridge",
        "mecanum_nav_bringup", "ROBOT_URDF_final_description",
        "robot_localization", "step07_nav2_baseline_runtime_observer",
        "mecanum_nav_rl",
    }

    worktree = tmp_path / "source"
    worktree.mkdir()
    run_directory = tmp_path / "evidence"
    map_root = tmp_path / "map"
    map_root.mkdir()
    config = worktree / "test_resolved.json"
    config.write_text(json.dumps({"provenance": {
        "config_hash": "5b3bb2be3bc4d8ff5f9f1524b5ecd52f735c63622e3dd6ddd3e67aa9e6ce1071"
    }}))
    monkeypatch.setattr(runner, "CONFIG_REL", "test_resolved.json")
    architecture = worktree / "docs/MECANUM_NAV_DRL_Architecture.docx"
    architecture.parent.mkdir(parents=True)
    architecture.write_bytes(b"architecture fixture")
    source_module = (worktree / "ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/observations/"
                     "step07_gate_b_observer_node.py")
    source_module.parent.mkdir(parents=True)
    source_module.write_bytes(b"observer fixture")

    prefix_root = tmp_path / "prefixes"
    prefixes = {}
    for package in runner.REQUIRED_PACKAGE_PREFIXES:
        prefix = prefix_root / package
        prefix.mkdir(parents=True)
        prefixes[package] = prefix
    module = (prefixes["mecanum_nav_rl"] / "lib/python3.12/site-packages/mecanum_nav_rl/"
              "observations/step07_gate_b_observer_node.py")
    module.parent.mkdir(parents=True)
    module.write_bytes(source_module.read_bytes())
    observer = (prefixes["step07_nav2_baseline_runtime_observer"] / "lib/"
                "step07_nav2_baseline_runtime_observer/step07_nav2_baseline_runtime_observer")
    observer.parent.mkdir(parents=True)
    observer.write_bytes(b"observer executable fixture")
    gate_script = prefixes["mecanum_nav_rl"] / "lib/mecanum_nav_rl/step07_gate_b_observer"
    gate_script.parent.mkdir(parents=True)
    gate_script.write_bytes(b"gate script fixture")

    for package, install_relative, source_relative in runner.INSTALLED_FILE_ARTIFACTS:
        source = worktree / source_relative
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(("source:" + source_relative).encode())
        installed = prefixes[package] / "share" / package / install_relative
        installed.parent.mkdir(parents=True, exist_ok=True)
        installed.write_bytes(source.read_bytes())

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for executable in ("ros2", "gz"):
        (bin_dir / executable).write_bytes(b"fixture")
    env = {"PATH": str(bin_dir)}
    prefix_requests = []
    equality_started = []

    def fake_run(args, **_kwargs):
        if args[:3] == ["ros2", "pkg", "prefix"]:
            package = args[3]
            prefix_requests.append(package)
            return SimpleNamespace(stdout=str(prefixes[package]))
        return SimpleNamespace(stdout="ROSIDL_IMPORT_PASS")

    original_read_bytes = Path.read_bytes

    def tracked_read_bytes(path):
        if path.parts[-1:] == ("sim_eval_nav2_baseline_system.launch.py",) and "share" in path.parts:
            equality_started.append(str(path))
        return original_read_bytes(path)

    monkeypatch.setattr(runner, "_run", fake_run)
    monkeypatch.setattr(runner, "validate_map_root", lambda _root: map_root)
    monkeypatch.setattr(runner, "validate_fuel_cache", lambda *_args: {"cache": "valid"})
    monkeypatch.setattr(runner, "validate_source_pins", lambda *_args: None)
    monkeypatch.setattr(runner, "sha256", lambda _path: runner.ARCHITECTURE_SHA256)
    monkeypatch.setattr(runner, "validate_runtime_python_environment",
                        lambda _python, _env, _prefix: {"observer_module_path": str(module)})
    monkeypatch.setattr(runner.os, "access", lambda *_args: True)
    monkeypatch.setattr(socket, "if_nameindex", lambda: [])
    monkeypatch.setattr(Path, "read_bytes", tracked_read_bytes)
    monkeypatch.setattr(runner, "stale_partition_processes", lambda _partition: [])

    result = runner.host_preflight(
        env, worktree, run_directory, runner.PARTITION, map_root, tmp_path / "fuel", {},
        Path(runner.RUNTIME_PYTHON_PATH),
    )

    assert tuple(prefix_requests) == runner.REQUIRED_PACKAGE_PREFIXES
    assert "ROBOT_URDF_final_description" in result["package_prefixes"]
    assert result["installed_source_byte_equality"] == {
        relative_source: True for _package, _relative_install, relative_source
        in runner.INSTALLED_FILE_ARTIFACTS
    }
    assert equality_started, "the full host preflight simulation must reach installed byte checks"


def test_host_preflight_missing_robot_description_prefix_fails_before_installed_checks(
    tmp_path, monkeypatch
):
    import socket
    from types import SimpleNamespace

    worktree = tmp_path / "source"
    worktree.mkdir()
    run_directory = tmp_path / "evidence"
    map_root = tmp_path / "map"
    map_root.mkdir()
    (worktree / "test_resolved.json").write_text(
        json.dumps({"provenance": {
            "config_hash": "5b3bb2be3bc4d8ff5f9f1524b5ecd52f735c63622e3dd6ddd3e67aa9e6ce1071"
        }}))
    monkeypatch.setattr(runner, "CONFIG_REL", "test_resolved.json")
    architecture = worktree / "docs/MECANUM_NAV_DRL_Architecture.docx"
    architecture.parent.mkdir(parents=True)
    architecture.write_bytes(b"architecture fixture")
    prefix_root = tmp_path / "prefixes"
    prefixes = {}
    for package in runner.REQUIRED_PACKAGE_PREFIXES:
        if package == "ROBOT_URDF_final_description":
            continue
        prefix = prefix_root / package
        prefix.mkdir(parents=True)
        prefixes[package] = prefix
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for executable in ("ros2", "gz"):
        (bin_dir / executable).write_bytes(b"fixture")
    requests = []
    equality_started = []

    def fake_run(args, **_kwargs):
        if args[:3] == ["ros2", "pkg", "prefix"]:
            package = args[3]
            requests.append(package)
            value = prefixes.get(package)
            return SimpleNamespace(stdout="" if value is None else str(value))
        raise AssertionError(f"unexpected command before installed checks: {args}")

    monkeypatch.setattr(runner, "_run", fake_run)
    monkeypatch.setattr(runner, "validate_map_root", lambda _root: map_root)
    monkeypatch.setattr(runner, "validate_fuel_cache", lambda *_args: {"cache": "valid"})
    monkeypatch.setattr(runner, "validate_source_pins", lambda *_args: None)
    monkeypatch.setattr(runner, "sha256", lambda _path: runner.ARCHITECTURE_SHA256)
    monkeypatch.setattr(runner.os, "access", lambda *_args: True)
    monkeypatch.setattr(socket, "if_nameindex", lambda: [])
    monkeypatch.setattr(runner, "validate_runtime_python_environment",
                        lambda *_args: pytest.fail("runtime Python checks must follow complete prefix closure"))
    monkeypatch.setattr(runner, "stale_partition_processes", lambda _partition: [])

    with pytest.raises(RuntimeError, match="PACKAGE_PREFIX_EMPTY:ROBOT_URDF_final_description"):
        runner.host_preflight(
            {"PATH": str(bin_dir)}, worktree, run_directory, runner.PARTITION,
            map_root, tmp_path / "fuel", {}, Path(runner.RUNTIME_PYTHON_PATH),
        )
    assert requests == list(runner.REQUIRED_PACKAGE_PREFIXES[:5])
    assert equality_started == []


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
        guard_path, lock, guard, {}, "a" * 40, runner.INTEGRATION_BASE, Path(runner.RUNTIME_PYTHON_PATH), record,
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
        runner.INTEGRATION_BASE, Path(runner.RUNTIME_PYTHON_PATH), {"call_counts": {"runner": 1}},
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


@pytest.mark.parametrize("facts,expected", [
    ({"python_major": 3, "python_minor": 12, "errors": ["PYDANTIC_IMPORT:ModuleNotFoundError"]}, "PYDANTIC_IMPORT_FAILED"),
    ({"python_major": 3, "python_minor": 12, "pydantic_version": "1.10.12", "errors": []}, "PYDANTIC_VERSION_MISMATCH"),
    ({"python_major": 3, "python_minor": 11, "pydantic_version": "2.10.6", "errors": []}, "PYTHON_VERSION_MISMATCH"),
    ({"python_major": 3, "python_minor": 12, "pydantic_version": "2.10.6", "errors": ["RCLPY_IMPORT:ModuleNotFoundError"]}, "RCLPY_IMPORT_FAILED"),
    ({"python_major": 3, "python_minor": 12, "pydantic_version": "2.10.6", "errors": ["OBSERVER_IMPORT:ImportError"]}, "GATE_B_OBSERVER_IMPORT_FAILED"),
])
def test_runtime_python_environment_invalid_preacquire_fails_closed(tmp_path, monkeypatch, facts, expected):
    import os
    import json as json_module
    runtime_python = Path(runner.RUNTIME_PYTHON_PATH)
    original_is_file = Path.is_file
    monkeypatch.setattr(Path, "is_file", lambda self: True if self == runtime_python else original_is_file(self))
    monkeypatch.setattr(os, "access", lambda *_: True)
    monkeypatch.setattr(runner, "_run", lambda *_a, **_k: type("R", (), {
        "returncode": 0, "stdout": json_module.dumps(facts), "stderr": ""})())
    overlay = tmp_path / "overlay"
    overlay.mkdir()
    with pytest.raises(RuntimeError, match=f"RUNTIME_PYTHON_ENVIRONMENT_INVALID:{expected}"):
        runner.validate_runtime_python_environment(runtime_python, {}, overlay)


def test_wrong_runtime_interpreter_path_fails_closed_without_bare_python_fallback(tmp_path):
    with pytest.raises(RuntimeError, match="RUNTIME_PYTHON_ENVIRONMENT_INVALID:INTERPRETER_PATH_MISMATCH"):
        runner.validate_runtime_python_environment(Path("/usr/bin/python3"), {}, tmp_path)
    source = RUNNER_PATH.read_text(encoding="utf-8")
    assert 'gate_command = [str(args.runtime_python), "-m", "mecanum_nav_rl.observations.step07_gate_b_observer_node"' in source
    assert 'subprocess.Popen(["python3", "-m", "mecanum_nav_rl.observations.step07_gate_b_observer_node"' not in source
    assert "prepare_step07_runtime_python_environment.py" not in source
    assert "pip install" not in source


def test_runtime_python_correct_overlay_passes_and_returns_fingerprint(tmp_path, monkeypatch):
    import os
    import json as json_module
    runtime_python = Path(runner.RUNTIME_PYTHON_PATH)
    overlay = tmp_path / "overlay"
    overlay.mkdir()
    module = overlay / "lib/python3.12/site-packages/mecanum_nav_rl/observations/step07_gate_b_observer_node.py"
    module.parent.mkdir(parents=True)
    module.write_text("# installed observer")
    facts = {"python_major": 3, "python_minor": 12, "python_version": "3.12.3",
             "pydantic_version": "2.10.6", "errors": [], "observer_module_path": str(module)}
    original_is_file = Path.is_file
    monkeypatch.setattr(Path, "is_file", lambda self: True if self == runtime_python else original_is_file(self))
    monkeypatch.setattr(os, "access", lambda *_: True)
    seen = []
    def fake_run(command, **_kwargs):
        seen.append(command)
        return type("R", (), {"returncode": 0, "stdout": json_module.dumps(facts), "stderr": ""})()
    monkeypatch.setattr(runner, "_run", fake_run)
    result = runner.validate_runtime_python_environment(runtime_python, {}, overlay)
    assert seen == [[str(runtime_python), "-c", runner.RUNTIME_PYTHON_PROBE]]
    assert result["pydantic_version"] == "2.10.6"
    assert Path(result["observer_module_path"]).is_relative_to(overlay.resolve())


def test_runtime_python_environment_failure_is_recorded_preacquire_without_guard_use(tmp_path, monkeypatch):
    runtime_worktree = tmp_path / "runtime"
    runtime_worktree.mkdir()
    run_directory = tmp_path / "evidence"
    guard_path = runtime_worktree / "guard.json"
    lock = guard_path.with_suffix(".json.lock")
    guard = {"state": runner.PENDING, "capacity": 1, "acquisition_count": 0,
             "runtime_authorization": "NOT_GRANTED"}
    guard_raw = json.dumps(guard, sort_keys=True, separators=(",", ":")).encode()
    guard_path.write_bytes(guard_raw)
    monkeypatch.setattr(runner, "prepare_ros_environment", lambda *_: {"PATH": "/usr/bin"})
    def host(*_args):
        raise RuntimeError("RUNTIME_PYTHON_ENVIRONMENT_INVALID:PYDANTIC_VERSION_MISMATCH")
    monkeypatch.setattr(runner, "host_preflight", host)
    monkeypatch.setattr(runner, "acquire_guard", lambda *_a, **_k: pytest.fail("must not acquire"))
    record = {"run_id": runner.RUN_ID, "review_commit": "a"*40,
              "integration_base": runner.INTEGRATION_BASE, "partition": runner.PARTITION,
              "guard_state_before": runner.PENDING}
    *_, failure = runner.preacquire_preflight(
        runtime_worktree, {}, run_directory, runner.PARTITION, tmp_path/"map", tmp_path/"fuel",
        {}, guard_path, lock, guard, {}, "a"*40, runner.INTEGRATION_BASE,
        Path(runner.RUNTIME_PYTHON_PATH), record)
    assert failure["exception_message"] == "RUNTIME_PYTHON_ENVIRONMENT_INVALID:PYDANTIC_VERSION_MISMATCH"
    assert failure["failure_reason_literals"] == ["RUNTIME_PYTHON_ENVIRONMENT_INVALID:PYDANTIC_VERSION_MISMATCH"]
    assert guard_path.read_bytes() == guard_raw and not lock.exists()
    assert failure["call_counts"] == {"runner": 1, "bootstrap": 0, "composite": 0,
                                       "cpp_observer": 0, "gate_b_observer": 0}


def test_rclpy_import_failure_after_ros_overlay_source_is_preacquire_and_not_guarded(tmp_path, monkeypatch):
    import os

    runtime_worktree = tmp_path / "runtime"
    runtime_worktree.mkdir()
    run_directory = tmp_path / "evidence"
    guard_path = runtime_worktree / "guard.json"
    lock = guard_path.with_suffix(".json.lock")
    guard = {"state": runner.PENDING, "capacity": 1, "acquisition_count": 0,
             "runtime_authorization": "NOT_GRANTED"}
    guard_raw = json.dumps(guard, sort_keys=True, separators=(",", ":")).encode()
    guard_path.write_bytes(guard_raw)
    phases = []

    def sourced_ros_environment(*_args):
        phases.append("ros_and_overlay_sourced")
        return {"AMENT_PREFIX_PATH": "/external/install", "PATH": "/opt/ros/jazzy/bin"}

    overlay = tmp_path / "overlay"
    overlay.mkdir()
    runtime_python = Path(runner.RUNTIME_PYTHON_PATH)
    original_is_file = Path.is_file
    monkeypatch.setattr(Path, "is_file", lambda self: True if self == runtime_python else original_is_file(self))
    monkeypatch.setattr(os, "access", lambda *_args: True)
    facts = {"python_major": 3, "python_minor": 12, "pydantic_version": "2.10.6",
             "errors": ["RCLPY_IMPORT:ModuleNotFoundError"], "observer_module_path": str(overlay / "observer.py")}
    monkeypatch.setattr(runner, "_run", lambda *_args, **_kwargs: type("R", (), {
        "returncode": 0, "stdout": json.dumps(facts), "stderr": ""})())

    def sourced_host_preflight(env, _worktree, _run_directory, _partition, _map, _fuel, _pins, runtime_python):
        assert "AMENT_PREFIX_PATH" in env
        phases.append("runtime_interpreter_probe_after_source")
        return runner.validate_runtime_python_environment(runtime_python, env, overlay)

    monkeypatch.setattr(runner, "prepare_ros_environment", sourced_ros_environment)
    monkeypatch.setattr(runner, "host_preflight", sourced_host_preflight)
    monkeypatch.setattr(runner, "acquire_guard", lambda *_a, **_k: pytest.fail("must not acquire"))
    record = {"run_id": runner.RUN_ID, "review_commit": "a" * 40,
              "integration_base": runner.INTEGRATION_BASE, "partition": runner.PARTITION,
              "guard_state_before": runner.PENDING}
    *_, failure = runner.preacquire_preflight(
        runtime_worktree, {}, run_directory, runner.PARTITION, tmp_path / "map", tmp_path / "fuel",
        {}, guard_path, lock, guard, {}, "a" * 40, runner.INTEGRATION_BASE,
        runtime_python, record)
    assert phases == ["ros_and_overlay_sourced", "runtime_interpreter_probe_after_source"]
    assert failure["exception_message"] == "RUNTIME_PYTHON_ENVIRONMENT_INVALID:RCLPY_IMPORT_FAILED"
    assert failure["failure_reason_literals"] == ["RUNTIME_PYTHON_ENVIRONMENT_INVALID:RCLPY_IMPORT_FAILED"]
    assert guard_path.read_bytes() == guard_raw and not lock.exists()
    assert failure["guard_acquired"] is False and failure["runtime_execution"] is False


def test_runtime_python_wrong_overlay_fails_with_required_literal(tmp_path, monkeypatch):
    import os
    import json as json_module
    runtime_python = Path(runner.RUNTIME_PYTHON_PATH)
    overlay = tmp_path / "overlay"; overlay.mkdir()
    outside = tmp_path / "outside.py"; outside.write_text("# not installed")
    facts = {"python_major": 3, "python_minor": 12, "pydantic_version": "2.10.6",
             "errors": [], "observer_module_path": str(outside)}
    original_is_file = Path.is_file
    monkeypatch.setattr(Path, "is_file", lambda self: True if self == runtime_python else original_is_file(self))
    monkeypatch.setattr(os, "access", lambda *_: True)
    monkeypatch.setattr(runner, "_run", lambda *_a, **_k: type("R", (), {
        "returncode": 0, "stdout": json_module.dumps(facts), "stderr": ""})())
    with pytest.raises(RuntimeError, match="RUNTIME_PYTHON_ENVIRONMENT_INVALID:GATE_B_OBSERVER_OUTSIDE_INSTALL_OVERLAY"):
        runner.validate_runtime_python_environment(runtime_python, {}, overlay)


def test_missing_runtime_python_executable_fails_closed_before_probe(tmp_path, monkeypatch):
    import os
    runtime_python = Path(runner.RUNTIME_PYTHON_PATH)
    original_is_file = Path.is_file
    monkeypatch.setattr(Path, "is_file", lambda self: False if self == runtime_python else original_is_file(self))
    monkeypatch.setattr(os, "access", lambda *_: False)
    monkeypatch.setattr(runner, "_run", lambda *_a, **_k: pytest.fail("must not probe missing interpreter"))
    with pytest.raises(RuntimeError, match="RUNTIME_PYTHON_ENVIRONMENT_INVALID:INTERPRETER_MISSING_OR_NOT_EXECUTABLE"):
        runner.validate_runtime_python_environment(runtime_python, {}, tmp_path)
