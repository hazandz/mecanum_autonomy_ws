import hashlib
import importlib.util
import inspect
import json
import errno
import os
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
RUN005_ATTEMPT_001_SHA = "71ca32471f8e042a0048d319ca39cb9deff0c6f4"
RUN005_ATTEMPT_002_OUTPUT_BASE = "99d5c29c1c302260a8971e19e46f93d778a52f86"
RUN005_GUARD_REL = "artifacts/simulation/step07_nav2_baseline_campaign/approval_guards/STEP07_NAV2_BASELINE_RUN_005.json"


def _fake_proc_process(proc_root, pid, *, environ=None, cmdline=None, ppid=1):
    process = proc_root / str(pid)
    process.mkdir(parents=True, exist_ok=True)
    (process / "stat").write_text(f"{pid} (fake process {pid}) S {ppid} 0 0\n", encoding="ascii")
    if environ is not None:
        (process / "environ").write_bytes(environ)
    if cmdline is not None:
        (process / "cmdline").write_bytes(cmdline)
    return process


def _git_blob(root: Path, commit: str, relative: str) -> bytes:
    return subprocess.run(
        ["git", "show", f"{commit}:{relative}"], cwd=root,
        check=True, capture_output=True,
    ).stdout


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


def _git_metadata_snapshot(git_dir: Path):
    snapshot = {}
    for path in sorted(git_dir.rglob("*")):
        relative = path.relative_to(git_dir).as_posix()
        info = path.lstat()
        snapshot[relative] = (info.st_mode & 0o777, info.st_size, info.st_mtime_ns,
                              path.read_bytes() if path.is_file() and not path.is_symlink() else None,
                              os.readlink(path) if path.is_symlink() else None)
    return snapshot


def test_runtime_checkout_is_private_local_clone_and_leaves_read_only_source_metadata_unchanged(tmp_path, monkeypatch):
    source = tmp_path / "source"
    destination = tmp_path / "runtime-copy"
    source.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=source, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=source, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=source, check=True)
    (source / "payload.txt").write_text("fixture\n", encoding="utf-8")
    subprocess.run(["git", "add", "payload.txt"], cwd=source, check=True)
    subprocess.run(["git", "commit", "-m", "fixture"], cwd=source, check=True, capture_output=True)
    subprocess.run(["git", "remote", "add", "origin", runner.EXPECTED_ORIGIN], cwd=source, check=True)
    expected_head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=source, check=True, capture_output=True, text=True
    ).stdout.strip()
    git_dir = source / ".git"
    original_modes = {path: path.stat().st_mode & 0o777 for path in [git_dir, *git_dir.rglob("*")]}
    for path in sorted(original_modes, key=lambda item: len(item.parts), reverse=True):
        path.chmod(0o555 if path.is_dir() else 0o444)
    source_snapshot = _git_metadata_snapshot(git_dir)

    commands = []
    original_run = runner._run

    def recording_run(args, **kwargs):
        commands.append(list(args))
        return original_run(args, **kwargs)

    monkeypatch.setattr(runner, "_run", recording_run)
    try:
        result = runner.create_isolated_runtime_checkout(source, destination, expected_head)
        assert result == destination
        assert destination.joinpath(".git").is_dir()
        assert not destination.joinpath(".git").is_symlink()
        common_dir = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"], cwd=destination,
            check=True, capture_output=True, text=True,
        ).stdout.strip()
        common_path = Path(common_dir)
        if not common_path.is_absolute():
            common_path = destination / common_path
        assert common_path.resolve() == (destination / ".git").resolve()
        assert not (destination / ".git/objects/info/alternates").exists()
        assert subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=destination, check=True,
            capture_output=True, text=True,
        ).stdout.strip() == expected_head
        assert subprocess.run(
            ["git", "symbolic-ref", "-q", "HEAD"], cwd=destination,
            capture_output=True, text=True,
        ).returncode != 0
        assert subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=all"], cwd=destination,
            check=True, capture_output=True, text=True,
        ).stdout == ""
        assert subprocess.run(
            ["git", "remote", "get-url", "origin"], cwd=destination,
            check=True, capture_output=True, text=True,
        ).stdout.strip() == runner.EXPECTED_ORIGIN
        assert subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=source, check=True,
            capture_output=True, text=True,
        ).stdout.strip() == expected_head
        assert subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=all"], cwd=source,
            check=True, capture_output=True, text=True,
        ).stdout == ""
        assert _git_metadata_snapshot(git_dir) == source_snapshot
        rendered = [" ".join(command) for command in commands]
        assert any(command[:3] == ["git", "clone", "--no-hardlinks"]
                   and "--no-checkout" in command for command in commands)
        assert any(command[:3] == ["git", "checkout", "--detach"] for command in commands)
        assert any(command[:4] == ["git", "remote", "set-url", "origin"] for command in commands)
        assert not any("worktree" in command for command in rendered)
        assert not any(command[:2] in (["git", "fetch"], ["git", "pull"]) for command in commands)
    finally:
        for path, mode in original_modes.items():
            path.chmod(mode)


def test_installed_file_closure_rejects_any_artifact_package_without_prefix():
    package = "ROBOT_URDF_final_description"
    prefixes = {name: f"/overlay/{name}" for name in runner.REQUIRED_PACKAGE_PREFIXES
                if name != package}
    with pytest.raises(RuntimeError, match="INSTALLED_FILE_PACKAGE_PREFIX_MISSING:ROBOT_URDF_final_description"):
        runner.validate_installed_file_package_closure(runner.INSTALLED_FILE_ARTIFACTS, prefixes)


def test_installed_runtime_artifact_closure_is_the_exact_fifteen_source_set():
    expected = {
        "ros2_ws/src/mecanum_nav_bringup/launch/sim_eval_nav2_baseline_system.launch.py",
        "ros2_ws/src/ROBOT_URDF_final_description/launch/sim_eval_nav2_baseline_bootstrap.launch.py",
        "ros2_ws/src/ROBOT_URDF_final_description/launch/tugbot_depot.sdf",
        "ros2_ws/src/mecanum_nav_bringup/config/navigation/sim_eval_nav2_baseline.runtime.yaml",
        "ros2_ws/src/mecanum_nav_bringup/config/bridge/sim_eval_cmd_vel.runtime.yaml",
        "ros2_ws/src/mecanum_nav_bringup/config/lifecycle/sim_eval_nav2_baseline.runtime.yaml",
        "ros2_ws/src/mecanum_nav_bringup/launch/sim_eval_tf_ekf_state_estimation.launch.py",
        "ros2_ws/src/mecanum_nav_bringup/config/bridge/sim_eval_lidar_scan_bridge.runtime.yaml",
        "ros2_ws/src/mecanum_nav_bringup/config/localization/amcl_omni.yaml",
        "ros2_ws/src/mecanum_nav_bringup/config/bridge/sim_eval_clock.runtime.yaml",
        "ros2_ws/src/mecanum_nav_bringup/config/state_estimation/ekf_sim.yaml",
        "ros2_ws/src/mecanum_base_bridge/launch/sim_eval_wheel_imu_ingress.launch.py",
        "ros2_ws/src/mecanum_base_bridge/config/bridge/sim_eval_wheel_imu_ingress.runtime.yaml",
        "ros2_ws/src/mecanum_nav_rl/config/safety/sim_eval_nav2_baseline_safety.yaml",
        "ros2_ws/src/mecanum_nav_rl/config/v3/resolved/sim_eval_nav2_baseline.resolved.json",
    }
    assert len(runner.INSTALLED_FILE_ARTIFACTS) == 15
    assert {relative for _package, _installed, relative in runner.INSTALLED_FILE_ARTIFACTS} == expected


def test_host_preflight_collects_complete_prefix_closure_before_installed_byte_checks(
    tmp_path, monkeypatch
):
    from types import SimpleNamespace

    assert set(runner.REQUIRED_PACKAGE_PREFIXES) == {
        "ros_gz_sim", "ros_gz_bridge", "mecanum_base_bridge",
        "mecanum_nav_bringup", "ROBOT_URDF_final_description",
        "robot_localization", "step07_nav2_baseline_runtime_observer",
        "mecanum_nav_rl", *runner.NAV2_RUNTIME_PACKAGES,
    }
    assert len(runner.INSTALLED_FILE_ARTIFACTS) == 15

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
    for package, executable in runner.NAV2_NODE_EXECUTABLES:
        installed_executable = prefixes[package] / "lib" / package / executable
        installed_executable.parent.mkdir(parents=True, exist_ok=True)
        installed_executable.write_bytes(b"executable fixture")

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
            return SimpleNamespace(stdout=str(prefixes[package]), returncode=0)
        return SimpleNamespace(stdout="ROSIDL_IMPORT_PASS", returncode=0)

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
    monkeypatch.setattr(runner, "validate_gz_transport_host_capability",
                        lambda *_args: {"gz_topic_list": "PASS"})
    monkeypatch.setattr(runner, "validate_ros_discovery_host_capability",
                        lambda *_args: {"probe": "PASS", "empty_graph_valid": True})
    monkeypatch.setattr(Path, "read_bytes", tracked_read_bytes)
    monkeypatch.setattr(runner, "stale_partition_processes", lambda _partition: [])

    result = runner.host_preflight(
        env, worktree, run_directory, runner.PARTITION, map_root, tmp_path / "fuel", {},
        Path(runner.RUNTIME_PYTHON_PATH),
    )

    assert tuple(prefix_requests) == runner.REQUIRED_PACKAGE_PREFIXES
    assert "ROBOT_URDF_final_description" in result["package_prefixes"]
    assert set(result["nav2_executables"]) == {
        f"{package}/{executable}" for package, executable in runner.NAV2_NODE_EXECUTABLES
    }
    assert result["installed_source_byte_equality"] == {
        relative_source: True for _package, _relative_install, relative_source
        in runner.INSTALLED_FILE_ARTIFACTS
    }
    assert equality_started, "the full host preflight simulation must reach installed byte checks"


@pytest.mark.parametrize("package", runner.NAV2_RUNTIME_PACKAGES)
def test_missing_nav2_package_prefix_has_stable_preacquire_failure(package, monkeypatch):
    from types import SimpleNamespace

    def fake_run(args, **_kwargs):
        requested = args[3]
        if requested == package:
            return SimpleNamespace(stdout="", returncode=1)
        return SimpleNamespace(stdout=f"/overlay/{requested}", returncode=0)

    monkeypatch.setattr(runner, "_run", fake_run)
    with pytest.raises(RuntimeError, match=f"NAV2_PACKAGE_PREFIX_MISSING:{package}"):
        runner.collect_package_prefixes({"PATH": "/opt/ros/jazzy/bin"})


@pytest.mark.parametrize("package,executable", runner.NAV2_NODE_EXECUTABLES)
def test_missing_nav2_executable_has_stable_preacquire_failure(package, executable, tmp_path):
    prefixes = {name: str(tmp_path / name) for name in runner.REQUIRED_PACKAGE_PREFIXES}
    for name in runner.REQUIRED_PACKAGE_PREFIXES:
        Path(prefixes[name]).mkdir()
    for other_package, other_executable in runner.NAV2_NODE_EXECUTABLES:
        path = Path(prefixes[other_package]) / "lib" / other_package / other_executable
        if (other_package, other_executable) == (package, executable):
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"fixture")
        path.chmod(0o755)
    with pytest.raises(RuntimeError, match=f"NAV2_EXECUTABLE_MISSING:{package}/{executable}"):
        runner.validate_nav2_executables(prefixes)


def test_nav2_prefix_and_executable_checks_precede_all_installed_byte_comparisons():
    source = RUNNER_PATH.read_text(encoding="utf-8")
    body = source[source.index("def host_preflight("):source.index("def _atomic_write(")]
    assert body.index("collect_package_prefixes(env)") < body.index("validate_nav2_executables(prefixes)")
    assert body.index("validate_nav2_executables(prefixes)") < body.index("for package, relative_install, relative_source in installed_files")


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


def test_runtime_output_target_probe_passes_and_cleans_sentinels(tmp_path):
    runtime_parent = tmp_path / "runtime-parent"
    evidence_parent = tmp_path / "evidence-parent"
    runtime_parent.mkdir()
    evidence_parent.mkdir()
    runner.validate_runtime_output_targets(
        runtime_parent / "runtime", evidence_parent / "evidence"
    )
    assert list(runtime_parent.iterdir()) == []
    assert list(evidence_parent.iterdir()) == []


@pytest.mark.parametrize("case", [
    "relative", "missing_parent", "symlink_parent", "existing_target", "symlink_target",
])
def test_runtime_output_targets_reject_invalid_paths(tmp_path, case):
    runtime_parent = tmp_path / "runtime-parent"
    evidence_parent = tmp_path / "evidence-parent"
    runtime_parent.mkdir()
    evidence_parent.mkdir()
    runtime_target = runtime_parent / "runtime"
    evidence_target = evidence_parent / "evidence"
    expected = "RUNTIME_OUTPUT_PARENT_INVALID:runtime_worktree"
    if case == "relative":
        runtime_target = Path("relative-runtime")
    elif case == "missing_parent":
        runtime_target = tmp_path / "missing-parent" / "runtime"
    elif case == "symlink_parent":
        link_parent = tmp_path / "runtime-link"
        link_parent.symlink_to(runtime_parent, target_is_directory=True)
        runtime_target = link_parent / "runtime"
    elif case == "existing_target":
        runtime_target.mkdir()
    elif case == "symlink_target":
        runtime_target.symlink_to(evidence_parent, target_is_directory=True)
    with pytest.raises(RuntimeError, match=expected):
        runner.validate_runtime_output_targets(runtime_target, evidence_target)


@pytest.mark.parametrize("relation", ["same", "nested_runtime", "nested_evidence"])
def test_runtime_output_targets_reject_colliding_or_nested_targets(tmp_path, relation):
    parent = tmp_path / "parent"
    parent.mkdir()
    runtime_target = parent / "runtime"
    evidence_target = parent / "evidence"
    if relation == "same":
        evidence_target = runtime_target
    elif relation == "nested_runtime":
        evidence_target = runtime_target / "evidence"
        runtime_target.parent.mkdir(exist_ok=True)
    else:
        runtime_target = evidence_target / "runtime"
    invalid_label = "run_directory" if relation == "nested_runtime" else "runtime_worktree"
    with pytest.raises(RuntimeError, match=f"RUNTIME_OUTPUT_PARENT_INVALID:{invalid_label}"):
        runner.validate_runtime_output_targets(runtime_target, evidence_target)


@pytest.mark.parametrize("failure_errno", [errno.EPERM, errno.EROFS])
def test_read_only_evidence_parent_fails_with_stable_literal_before_clone_or_guard_mutation(
    tmp_path, monkeypatch, failure_errno
):
    runtime_parent = tmp_path / "runtime-parent"
    evidence_parent = tmp_path / "evidence-parent"
    runtime_parent.mkdir()
    evidence_parent.mkdir()
    runtime_target = runtime_parent / "runtime"
    evidence_target = evidence_parent / "evidence"
    guard_path = ROOT / RUN005_GUARD_REL
    original_guard = guard_path.read_bytes()
    lock_path = guard_path.with_suffix(guard_path.suffix + ".lock")
    assert not lock_path.exists()

    args = type("Args", (), {
        "repository_root": ROOT,
        "runtime_worktree": runtime_target,
        "run_directory": evidence_target,
        "guard_path": guard_path,
            "expected_review_commit": subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
                capture_output=True, text=True).stdout.strip(),
        "expected_integration_base": runner.INTEGRATION_BASE,
        "run_id": runner.RUN_ID,
        "gz_partition": runner.PARTITION,
        "owner_authorization": "test-authorization",
        "owner_authorization_scope": runner.AUTH_SCOPE,
        "owner_authorization_run_id": runner.RUN_ID,
            "owner_authorization_review_commit": subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
                capture_output=True, text=True).stdout.strip(),
        "owner_authorization_integration_base": runner.INTEGRATION_BASE,
    })()
    monkeypatch.setattr(runner, "_parse", lambda: args)
    original_runner_run = runner._run

    def clean_status_run(command, **kwargs):
        if command[:3] == ["git", "status", "--porcelain"]:
            return type("Result", (), {"stdout": "", "returncode": 0})()
        return original_runner_run(command, **kwargs)

    monkeypatch.setattr(runner, "_run", clean_status_run)
    monkeypatch.setattr(runner, "validate_seed", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(runner, "validate_owner_authorization", lambda **_kwargs: {})
    clone_calls = []
    monkeypatch.setattr(
        runner, "create_isolated_runtime_checkout",
        lambda *a, **k: clone_calls.append((a, k)),
    )
    monkeypatch.setattr(
        runner.tempfile, "mkdtemp",
        lambda **_kwargs: pytest.fail("external build dirs must not be created before output validation"),
    )
    original_open = runner.os.open

    def denied_evidence_open(path, flags, mode=0o777):
        if Path(path).parent == evidence_parent:
            raise PermissionError(failure_errno, "simulated read-only output parent")
        return original_open(path, flags, mode)

    monkeypatch.setattr(runner.os, "open", denied_evidence_open)
    with pytest.raises(SystemExit) as raised:
        runner.main()
    assert str(raised.value) == "RUNTIME_OUTPUT_PARENT_NOT_WRITABLE:run_directory"
    assert clone_calls == []
    assert not runtime_target.exists()
    assert not evidence_target.exists()
    assert guard_path.read_bytes() == original_guard
    assert not lock_path.exists()
    assert not list(runtime_parent.iterdir())
    assert not list(evidence_parent.iterdir())


def test_gz_transport_capability_pass_uses_exact_partition_and_fake_probes():
    from types import SimpleNamespace

    class FakeSocket:
        def __init__(self):
            self.bound = None
            self.closed = False

        def bind(self, address):
            self.bound = address

        def close(self):
            self.closed = True

    udp = FakeSocket()
    commands = []

    def fake_command(command, **kwargs):
        commands.append((command, kwargs))
        return SimpleNamespace(returncode=0, stdout="/clock\n", stderr="")

    facts = runner.validate_gz_transport_host_capability(
        {"PATH": "/fake/bin", "GZ_PARTITION": "wrong"}, runner.PARTITION,
        interface_enumerator=lambda: [(2, "lo")],
        socket_factory=lambda *_args: udp, command_runner=fake_command,
    )
    assert facts["gz_topic_list"] == "PASS"
    assert udp.bound == ("127.0.0.1", 0) and udp.closed
    assert commands[0][0] == ["gz", "topic", "-l"]
    assert commands[0][1]["env"]["GZ_PARTITION"] == runner.PARTITION


def test_gz_transport_capability_fails_if_udp_socket_close_fails():
    class CloseFailureSocket:
        def bind(self, _address):
            pass

        def close(self):
            raise PermissionError("close denied")

    with pytest.raises(RuntimeError, match=(
        "^GZ_TRANSPORT_HOST_CAPABILITY_UNAVAILABLE:UDP_LOOPBACK_PERMISSION_DENIED$"
    )):
        runner.validate_gz_transport_host_capability(
            {}, runner.PARTITION, interface_enumerator=lambda: [(1, "lo")],
            socket_factory=lambda *_args: CloseFailureSocket(),
            command_runner=lambda *_a, **_k: pytest.fail("gz probe follows successful UDP close"),
        )


@pytest.mark.parametrize(("interfaces", "socket_error", "command_error", "returncode", "output", "reason"), [
    (PermissionError(), None, None, 0, "", "INTERFACE_ENUMERATION_PERMISSION_DENIED"),
    (OSError(), None, None, 0, "", "INTERFACE_ENUMERATION_OS_ERROR"),
    ([], None, None, 0, "", "INTERFACE_ENUMERATION_EMPTY_OR_MALFORMED"),
    ([(0, "lo")], None, None, 0, "", "INTERFACE_ENUMERATION_EMPTY_OR_MALFORMED"),
    ([(1, "")], None, None, 0, "", "INTERFACE_ENUMERATION_EMPTY_OR_MALFORMED"),
    ([(1, "lo", "extra")], None, None, 0, "", "INTERFACE_ENUMERATION_INVALID"),
    ([(1, "lo")], PermissionError(), None, 0, "", "UDP_LOOPBACK_PERMISSION_DENIED"),
    ([(1, "lo")], OSError(), None, 0, "", "UDP_LOOPBACK_OS_ERROR"),
    ([(1, "lo")], None, subprocess.TimeoutExpired("gz topic -l", 1), 0, "", "GZ_TOPIC_TIMEOUT"),
    ([(1, "lo")], None, PermissionError(), 0, "", "GZ_TOPIC_PERMISSION_DENIED"),
    ([(1, "lo")], None, OSError(), 0, "", "GZ_TOPIC_OS_ERROR"),
    ([(1, "lo")], None, None, 1, "", "GZ_TOPIC_EXIT_NONZERO"),
    ([(1, "lo")], None, None, 0, "getifaddrs: Operation not permitted", "GZ_TOPIC_TRANSPORT_ERROR_OUTPUT"),
    ([(1, "lo")], None, None, 0, "Error creating socket: Operation not permitted", "GZ_TOPIC_TRANSPORT_ERROR_OUTPUT"),
])
def test_gz_transport_capability_fails_closed_with_stable_literal(
    interfaces, socket_error, command_error, returncode, output, reason,
):
    from types import SimpleNamespace

    def enumerate_interfaces():
        if isinstance(interfaces, BaseException):
            raise interfaces
        return interfaces

    class FakeSocket:
        def bind(self, _address):
            if socket_error:
                raise socket_error

        def close(self):
            pass

    def command(_command, **_kwargs):
        if command_error:
            raise command_error
        return SimpleNamespace(returncode=returncode, stdout=output, stderr="")

    with pytest.raises(RuntimeError, match=f"^GZ_TRANSPORT_HOST_CAPABILITY_UNAVAILABLE:{reason}$"):
        runner.validate_gz_transport_host_capability(
            {}, runner.PARTITION, interface_enumerator=enumerate_interfaces,
            socket_factory=lambda *_args: FakeSocket(), command_runner=command,
        )


def test_ros_discovery_capability_accepts_empty_graph_and_uses_no_daemon_probe():
    from types import SimpleNamespace

    commands = []

    def fake_command(command, **kwargs):
        commands.append((list(command), kwargs))
        if command[-1] == "--help":
            return SimpleNamespace(returncode=0, stdout="--no-daemon --spin-time", stderr="")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    env = {"AMENT_PREFIX_PATH": "/sourced/overlay", "ROS_DISTRO": "jazzy"}
    result = runner.validate_ros_discovery_host_capability(env, command_runner=fake_command)
    assert result["empty_graph_valid"] is True
    assert commands[0][0] == ["ros2", "topic", "list", "--no-daemon", "--spin-time", "3", "--help"]
    assert commands[1][0] == ["ros2", "topic", "list", "--no-daemon", "--spin-time", "3"]
    assert all(call[1]["env"] is env and call[1]["timeout"] <= 10 for call in commands)


@pytest.mark.parametrize(("mode", "reason"), [
    ("support_nonzero", "CLI_OPTIONS_UNSUPPORTED"),
    ("probe_timeout", "PROBE_TIMEOUT"),
    ("probe_permission", "SOCKET_PERMISSION_DENIED"),
    ("probe_oserror", "PROBE_OS_ERROR"),
    ("probe_nonzero", "PROBE_EXIT_NONZERO"),
    ("probe_network_output", "NETWORK_ERROR_OUTPUT"),
])
def test_ros_discovery_capability_fails_closed_with_stable_literal(mode, reason):
    from types import SimpleNamespace

    def fake_command(command, **_kwargs):
        if command[-1] == "--help":
            if mode == "support_nonzero":
                return SimpleNamespace(returncode=1, stdout="", stderr="unsupported option")
            return SimpleNamespace(returncode=0, stdout="--no-daemon --spin-time", stderr="")
        if mode == "probe_timeout":
            raise subprocess.TimeoutExpired(command, 1)
        if mode == "probe_permission":
            raise PermissionError("socket denied")
        if mode == "probe_oserror":
            raise OSError("probe failed")
        if mode == "probe_nonzero":
            return SimpleNamespace(returncode=2, stdout="", stderr="failed")
        return SimpleNamespace(returncode=0, stdout="", stderr="getifaddrs: denied")

    with pytest.raises(RuntimeError, match=f"^ROS_DISCOVERY_HOST_CAPABILITY_UNAVAILABLE:{reason}$"):
        runner.validate_ros_discovery_host_capability(
            {"AMENT_PREFIX_PATH": "/sourced/overlay"}, command_runner=fake_command)


@pytest.mark.parametrize(("acceptance", "record_extra", "teardown", "expected"), [
    ({"all": True}, {"pre_teardown_failure": "RunnerInterruptedBySignal:RUNNER_INTERRUPTED_BY_SIGNAL:SIGTERM"},
     {"completed": True, "clean": True, "order_correct": True, "verified": True},
     "STEP07_NAV2_BASELINE_RUN005_FAIL_NO_RETRY_GUARD_CONSUMED"),
    ({"all": True}, {"pre_teardown_failure": "RuntimeError:campaign failed"},
     {"completed": True, "clean": True, "order_correct": True, "verified": True},
     "STEP07_NAV2_BASELINE_RUN005_FAIL_NO_RETRY_GUARD_CONSUMED"),
    ({"all": True}, {},
     {"completed": True, "clean": True, "order_correct": True, "verified": True},
     "STEP07_NAV2_BASELINE_RUN005_PASS_PENDING_INDEPENDENT_EVIDENCE_AUDIT"),
    ({"all": True}, {},
     {"completed": True, "clean": False, "order_correct": True, "verified": False},
     "STEP07_NAV2_BASELINE_RUN005_FAIL_NO_RETRY_GUARD_CONSUMED"),
])
def test_terminal_verdict_and_real_artifacts_include_all_failure_conditions(
    tmp_path, acceptance, record_extra, teardown, expected,
):
    run_directory = tmp_path / "evidence"
    run_directory.mkdir()
    record = {"schema_version": "1.0", "run_id": runner.RUN_ID,
              "call_counts": {"runner": 1, "bootstrap": 1, "composite": 1,
                              "cpp_observer": 0, "gate_b_observer": 0}, **record_extra}
    handler = runner.SigtermHandler()
    result = runner.persist_terminal_evidence(record, acceptance, teardown, run_directory, handler)
    assert result["terminal_outcome"] == expected
    stored = runner.load_canonical_json(run_directory / "run_record.json")
    assert stored["terminal_outcome"] == expected
    manifest = runner.load_canonical_json(run_directory / "artifact_manifest.json")
    listed = {item["path"]: item for item in manifest["artifacts"]}
    raw = (run_directory / "run_record.json").read_bytes()
    assert listed["run_record.json"]["sha256"] == hashlib.sha256(raw).hexdigest()
    assert listed["run_record.json"]["size_bytes"] == len(raw)
    assert (run_directory / "SHA256SUMS.txt").is_file()


def test_sigterm_during_finalization_rewrites_durable_fail_record(tmp_path, monkeypatch):
    run_directory = tmp_path / "evidence"
    run_directory.mkdir()
    handler = runner.SigtermHandler()
    original_write = runner._atomic_write
    first = True

    def interrupt_first_write(path, document):
        nonlocal first
        if first and path.name == "run_record.json":
            first = False
            handler(runner.signal.SIGTERM, None)
        original_write(path, document)

    monkeypatch.setattr(runner, "_atomic_write", interrupt_first_write)
    result = runner.persist_terminal_evidence(
        {"call_counts": {"runner": 1}}, {"all": True},
        {"completed": True, "clean": True, "order_correct": True, "verified": True},
        run_directory, handler)
    assert result["terminal_outcome"] == "STEP07_NAV2_BASELINE_RUN005_FAIL_NO_RETRY_GUARD_CONSUMED"
    assert "RUNNER_INTERRUPTED_BY_SIGNAL:SIGTERM" in result["failure_reason_literals"]
    assert runner.load_canonical_json(run_directory / "run_record.json")["terminal_outcome"].endswith(
        "FAIL_NO_RETRY_GUARD_CONSUMED")
    assert (run_directory / "artifact_manifest.json").is_file()
    assert (run_directory / "SHA256SUMS.txt").is_file()


def test_process_group_kill_wait_and_proc_errors_cannot_report_clean(tmp_path, monkeypatch):
    class FakeProcess:
        pid = 212
        returncode = None

        def wait(self, timeout):
            raise subprocess.TimeoutExpired("fake", timeout)

    member = {"name": "composite", "pid": 212, "pgid": 212}
    monkeypatch.setattr(runner.os, "killpg", lambda *_args: (_ for _ in ()).throw(PermissionError("denied")))
    monkeypatch.setattr(runner, "_process_group_members", lambda *_args, **_kwargs: (
        (_ for _ in ()).throw(OSError("proc unreadable"))))
    result = runner._stop_owned_process(FakeProcess(), member, timeout=0.01)
    assert result["clean"] is False and result["verified"] is False
    assert any(item.startswith("KILLPG_FAILED:PermissionError") for item in result["errors"])
    assert "PROCESS_WAIT_TIMEOUT" in result["errors"]
    assert any(item.startswith("PROC_SNAPSHOT_FAILED:OSError") for item in result["errors"])
    run_directory = tmp_path / "evidence"
    run_directory.mkdir()
    verdict = runner.persist_terminal_evidence(
        {"call_counts": {"runner": 1, "bootstrap": 1, "composite": 1}}, {"all": True},
        {"completed": True, "clean": False, "order_correct": True, "verified": False,
         "errors": result["errors"]}, run_directory, runner.SigtermHandler())
    assert verdict["terminal_outcome"].endswith("FAIL_NO_RETRY_GUARD_CONSUMED")
    assert runner.load_canonical_json(run_directory / "run_record.json")["terminal_outcome"].endswith(
        "FAIL_NO_RETRY_GUARD_CONSUMED")
    assert (run_directory / "artifact_manifest.json").is_file()
    assert (run_directory / "SHA256SUMS.txt").is_file()


def test_sigterm_during_teardown_still_stops_both_groups_and_persists_failure(tmp_path, monkeypatch):
    handler = runner.SigtermHandler()
    class FakeProcess:
        def __init__(self, pid):
            self.pid = pid
            self.returncode = None

        def poll(self):
            return None

        def wait(self, timeout):
            self.returncode = 0
            return 0

    kill_order = []
    def injected_killpg(pgid, _sig):
        kill_order.append(pgid)
        if len(kill_order) == 1:
            handler(runner.signal.SIGTERM, None)

    monkeypatch.setattr(runner.os, "killpg", injected_killpg)
    monkeypatch.setattr(runner, "_process_group_members", lambda _pgid: {
        "live_member_pids": [], "zombie_member_pids": [], "verified": True,
        "inspection_errors": []})
    composite = {"name": "composite", "pid": 31, "pgid": 31}
    bootstrap = {"name": "bootstrap", "pid": 32, "pgid": 32}
    run_directory = tmp_path / "evidence"
    run_directory.mkdir()
    record = {"call_counts": {"runner": 1}}
    previous = runner.signal.getsignal(runner.signal.SIGTERM)
    result = runner.finalize_campaign_after_acquisition(
        record=record, runtime_acceptance={"all": True},
        composite_proc=FakeProcess(31), composite_member=composite,
        bootstrap_proc=FakeProcess(32), bootstrap_member=bootstrap,
        collector_procs={}, collector_members={}, bootstrap_calls=1,
        composite_calls=1, cpp_calls=0, gate_b_calls=0, run_directory=run_directory,
        sigterm_handler=handler, previous_sigterm_handler=previous)
    assert kill_order == [31, 32]
    assert result["terminal_outcome"].endswith("FAIL_NO_RETRY_GUARD_CONSUMED")
    assert "RUNNER_INTERRUPTED_BY_SIGNAL:SIGTERM" in result["failure_reason_literals"]
    assert runner.load_canonical_json(run_directory / "run_record.json")["terminal_outcome"].endswith(
        "FAIL_NO_RETRY_GUARD_CONSUMED")


def test_ros_discovery_failure_writes_preacquire_bundle_without_acquiring_guard(tmp_path, monkeypatch):
    runtime_worktree = tmp_path / "runtime"
    runtime_worktree.mkdir()
    evidence = tmp_path / "evidence"
    guard_path = tmp_path / "guard.json"
    guard = {"state": runner.PENDING, "capacity": 1, "acquisition_count": 0,
             "runtime_authorization": "NOT_GRANTED"}
    raw_guard = json.dumps(guard, sort_keys=True, separators=(",", ":")).encode()
    guard_path.write_bytes(raw_guard)
    lock = guard_path.with_suffix(".json.lock")
    calls = []
    monkeypatch.setattr(runner, "prepare_ros_environment", lambda *_: {"AMENT_PREFIX_PATH": "/overlay"})

    def host(_env, *_args):
        calls.append("gazebo_probe")
        calls.append("ros_probe")
        runner.validate_ros_discovery_host_capability(
            {"AMENT_PREFIX_PATH": "/overlay"}, command_runner=lambda *_a, **_k: (
                (_ for _ in ()).throw(PermissionError("socket denied"))))

    monkeypatch.setattr(runner, "host_preflight", host)
    monkeypatch.setattr(runner, "acquire_guard", lambda *_a, **_k: pytest.fail("must remain pre-acquire"))
    record = {"run_id": runner.RUN_ID, "review_commit": "a" * 40,
              "integration_base": runner.INTEGRATION_BASE, "partition": runner.PARTITION,
              "guard_state_before": runner.PENDING}
    result = runner.preacquire_preflight(
        runtime_worktree, {}, evidence, runner.PARTITION, tmp_path / "map", tmp_path / "fuel",
        {}, guard_path, lock, guard, {}, "a" * 40, runner.INTEGRATION_BASE,
        Path(runner.RUNTIME_PYTHON_PATH), record)
    assert calls == ["gazebo_probe", "ros_probe"]
    assert result[3]["preacquire_failure_literal"] == (
        "ROS_DISCOVERY_HOST_CAPABILITY_UNAVAILABLE:CLI_SUPPORT_ERROR")
    assert guard_path.read_bytes() == raw_guard and not lock.exists()
    assert runner.load_canonical_json(evidence / "run_record.json")["guard_acquired"] is False
    assert (evidence / "preflight_failure.json").is_file()


def test_preacquire_transport_failure_writes_evidence_without_guard_or_process(
    tmp_path, monkeypatch,
):
    runtime_worktree = tmp_path / "runtime"
    runtime_worktree.mkdir()
    evidence = tmp_path / "evidence"
    guard_path = runtime_worktree / "guard.json"
    guard = {"state": runner.PENDING, "capacity": 1, "acquisition_count": 0,
             "runtime_authorization": "NOT_GRANTED"}
    raw_guard = json.dumps(guard, sort_keys=True, separators=(",", ":")).encode()
    guard_path.write_bytes(raw_guard)
    lock = guard_path.with_suffix(".json.lock")
    calls = []

    monkeypatch.setattr(runner, "prepare_ros_environment", lambda *_: {"PATH": ""})
    def host(*_args):
        calls.append("host")
        runner.validate_gz_transport_host_capability(
            {}, runner.PARTITION, interface_enumerator=lambda: (_ for _ in ()).throw(PermissionError()),
            socket_factory=lambda *_: pytest.fail("UDP probe must follow interfaces"),
            command_runner=lambda *_a, **_k: pytest.fail("gz probe must follow UDP"),
        )
    monkeypatch.setattr(runner, "host_preflight", host)
    monkeypatch.setattr(runner, "acquire_guard", lambda *_a, **_k: pytest.fail("guard must remain pending"))
    record = {"run_id": runner.RUN_ID, "partition": runner.PARTITION,
              "guard_state_before": runner.PENDING}
    result = runner.preacquire_preflight(
        runtime_worktree, {}, evidence, runner.PARTITION, tmp_path / "map", tmp_path / "fuel",
        {}, guard_path, lock, guard, {}, "a" * 40, runner.INTEGRATION_BASE,
        Path(runner.RUNTIME_PYTHON_PATH), record,
    )
    assert calls == ["host"] and result[3]["failure_reason_literals"] == [
        "GZ_TRANSPORT_HOST_CAPABILITY_UNAVAILABLE:INTERFACE_ENUMERATION_PERMISSION_DENIED"]
    assert record["guard_state_after"] == runner.PENDING
    assert record["call_counts"] == {"runner": 1, "bootstrap": 0, "composite": 0,
                                      "cpp_observer": 0, "gate_b_observer": 0}
    assert guard_path.read_bytes() == raw_guard and not lock.exists()
    assert (evidence / "run_record.json").is_file()
    assert (evidence / "preflight_failure.json").is_file()


def test_sigterm_handler_raises_stable_exception_and_runtime_path_finalizes_after_teardown():
    source = RUNNER_PATH.read_text(encoding="utf-8")
    main_body = source[source.index("def main():"):]
    assert main_body.index("preacquire_preflight(") < main_body.index(
        "signal.signal(signal.SIGTERM, sigterm_handler)") < main_body.index("args.run_directory.mkdir")
    assert source.index("sigterm_handler.begin_finalization()") < source.index(
        "finalise_after_teardown(record, runtime_acceptance, teardown)")
    finalizer = source[source.index("def finalize_campaign_after_acquisition("):]
    assert "finally:\n        signal.signal(signal.SIGTERM, previous_sigterm_handler)" in finalizer
    handler = runner.SigtermHandler()
    with pytest.raises(runner.RunnerInterruptedBySignal,
                       match="^RUNNER_INTERRUPTED_BY_SIGNAL:SIGTERM$"):
        handler(runner.signal.SIGTERM, None)
    handler(runner.signal.SIGTERM, None)  # second signal cannot interrupt evidence finalization
    handler = runner.SigtermHandler()
    handler.begin_finalization()
    with pytest.raises(runner.RunnerInterruptedBySignal,
                       match="^RUNNER_INTERRUPTED_BY_SIGNAL:SIGTERM$"):
        handler(runner.signal.SIGTERM, None)
    handler(runner.signal.SIGTERM, None)
    assert handler.interrupted is True
    record = {"pre_teardown_failure": "RunnerInterruptedBySignal:RUNNER_INTERRUPTED_BY_SIGNAL:SIGTERM"}
    finalized = runner.finalise_after_teardown(
        record, {"runtime_acceptance": False},
        {"completed": True, "clean": True, "order_correct": True},
    )
    assert finalized["terminal_outcome"] == "STEP07_NAV2_BASELINE_RUN005_FAIL_NO_RETRY_GUARD_CONSUMED"
    assert finalized["finalized_after_teardown"] is True
    assert "RUNNER_INTERRUPTED_BY_SIGNAL:SIGTERM" in finalized["failure_reason_literals"]


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
        {"completed": True, "clean": True, "order_correct": True, "verified": True},
    )
    assert result["terminal_outcome"].endswith("PASS_PENDING_INDEPENDENT_EVIDENCE_AUDIT")
    assert all(result["acceptance"].values())
    source = RUNNER_PATH.read_text()
    assert source.index("preacquire_preflight(") < source.index("_spawn_owned_process(", source.index("def main():"))


def test_best_effort_teardown_attempts_composite_before_bootstrap(tmp_path, monkeypatch):
    order = []
    composite = {"name": "composite", "pid": 31, "pgid": 31}
    bootstrap = {"name": "bootstrap", "pid": 32, "pgid": 32}

    def fake_stop(_proc, member, _timeout):
        order.append(member["name"])
        member["final_snapshot"] = {"live_member_pids": [], "zombie_member_pids": [],
                                     "verified": True, "inspection_errors": []}
        return {"signal_sent": True, "clean": True, "verified": True,
                "live_member_pids": [], "zombie_member_pids": [], "errors": []}

    monkeypatch.setattr(runner, "_stop_owned_process", fake_stop)
    teardown = runner.teardown_campaign_processes(
        composite_proc=object(), composite_member=composite,
        bootstrap_proc=object(), bootstrap_member=bootstrap,
        collector_procs={}, collector_members={}, bootstrap_calls=1, composite_calls=1)
    assert order == ["composite", "bootstrap"]
    assert teardown["completed"] and teardown["verified"] and teardown["clean"]
    assert teardown["order_correct"]


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


def test_stale_partition_scan_uses_only_exact_nul_delimited_environment_entries(tmp_path, monkeypatch):
    proc_root = tmp_path / "proc"
    proc_root.mkdir()
    monkeypatch.setattr(runner.os, "getpid", lambda: 999)
    monkeypatch.setattr(runner.os, "getppid", lambda: 1)
    partition = runner.PARTITION
    _fake_proc_process(proc_root, 10, cmdline=f"wrapper {partition}".encode())
    _fake_proc_process(proc_root, 11, environ=f"GZ_PARTITION={partition}\0OTHER=x\0".encode())
    _fake_proc_process(proc_root, 12, environ=f"GZ_PARTITION={partition}-extra\0".encode())
    _fake_proc_process(proc_root, 13, environ=f"XGZ_PARTITION={partition}\0".encode())
    _fake_proc_process(proc_root, 14, environ=f"OTHER=GZ_PARTITION={partition}\0".encode())
    _fake_proc_process(proc_root, 15, environ=b"GZ_PARTITION=another_partition\0")
    _fake_proc_process(proc_root, 16, environ=f"PATH=/bin\0GZ_PARTITION={partition}\0LANG=C\0".encode())

    assert runner.stale_partition_processes(partition, proc_root=proc_root) == ["11", "16"]
    source = inspect.getsource(runner.stale_partition_processes)
    assert "cmdline" not in source
    assert '.split(b"\\0")' in source


def test_stale_partition_scan_excludes_process_ancestry_and_sorts_numeric_pids(tmp_path, monkeypatch):
    proc_root = tmp_path / "proc"
    proc_root.mkdir()
    monkeypatch.setattr(runner.os, "getpid", lambda: 900)
    monkeypatch.setattr(runner.os, "getppid", lambda: 500)
    exact = f"GZ_PARTITION={runner.PARTITION}\0".encode()
    _fake_proc_process(proc_root, 900, environ=exact)
    _fake_proc_process(proc_root, 500, environ=exact, ppid=1)
    _fake_proc_process(proc_root, 10, environ=exact)
    _fake_proc_process(proc_root, 2, environ=exact)

    assert runner.stale_partition_processes(runner.PARTITION, proc_root=proc_root) == ["2", "10"]


def test_stale_partition_scan_ignores_disappeared_or_inaccessible_environ(tmp_path, monkeypatch):
    proc_root = tmp_path / "proc"
    proc_root.mkdir()
    monkeypatch.setattr(runner.os, "getpid", lambda: 999)
    monkeypatch.setattr(runner.os, "getppid", lambda: 1)
    for pid in (3, 4, 5):
        _fake_proc_process(proc_root, pid, environ=b"GZ_PARTITION=other\0")
    original_read_bytes = Path.read_bytes

    def selective_read_bytes(path):
        if path.name == "environ" and path.parent.name == "3":
            raise PermissionError("proc environ denied")
        if path.name == "environ" and path.parent.name == "4":
            raise FileNotFoundError("process disappeared")
        if path.name == "environ" and path.parent.name == "5":
            raise OSError("proc read failed")
        return original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", selective_read_bytes)
    assert runner.stale_partition_processes(runner.PARTITION, proc_root=proc_root) == []


def test_exact_stale_environment_match_fails_preacquire_without_guard_or_lock(tmp_path, monkeypatch):
    proc_root = tmp_path / "proc"
    proc_root.mkdir()
    monkeypatch.setattr(runner.os, "getpid", lambda: 999)
    monkeypatch.setattr(runner.os, "getppid", lambda: 1)
    _fake_proc_process(
        proc_root, 123,
        environ=f"GZ_PARTITION={runner.PARTITION}\0".encode(),
        cmdline=b"unrelated-command\0",
    )
    runtime_worktree = tmp_path / "runtime-worktree"
    runtime_worktree.mkdir()
    run_directory = tmp_path / "evidence"
    guard_path = tmp_path / "guard.json"
    guard = {"run_id": runner.RUN_ID, "state": runner.PENDING, "capacity": 1,
             "acquisition_count": 0, "runtime_authorization": "NOT_GRANTED"}
    guard_raw = json.dumps(guard, sort_keys=True, separators=(",", ":")).encode()
    guard_path.write_bytes(guard_raw)
    lock = guard_path.with_suffix(".json.lock")

    monkeypatch.setattr(runner, "prepare_ros_environment", lambda *_: {"ROS_DISTRO": "jazzy"})

    def host_preflight(_env, _worktree, _run_directory, partition, *_args):
        if runner.stale_partition_processes(partition, proc_root=proc_root):
            raise RuntimeError("STALE_PARTITION_PROCESS_FOUND")
        return {"stale_processes": []}

    def acquire(*_args, **_kwargs):
        raise AssertionError("exact stale match must stop before guard acquisition")

    monkeypatch.setattr(runner, "host_preflight", host_preflight)
    monkeypatch.setattr(runner, "acquire_guard", acquire)
    record = {"schema_version": "1.0", "run_id": runner.RUN_ID,
              "review_commit": "a" * 40, "integration_base": runner.INTEGRATION_BASE,
              "partition": runner.PARTITION, "guard_state_before": runner.PENDING}
    result = runner.preacquire_preflight(
        runtime_worktree, {"build": tmp_path / "build"}, run_directory,
        runner.PARTITION, tmp_path / "map", tmp_path / "fuel", {}, guard_path,
        lock, guard, {}, "a" * 40, runner.INTEGRATION_BASE,
        Path(runner.RUNTIME_PYTHON_PATH), record,
    )

    assert result[:3] == (None, None, None)
    assert result[3]["preacquire_failure_literal"] == "PREACQUIRE_FAILURE:RuntimeError:STALE_PARTITION_PROCESS_FOUND"
    assert result[3]["guard_acquired"] is False
    assert result[3]["call_counts"] == {"runner": 1, "bootstrap": 0, "composite": 0,
                                         "cpp_observer": 0, "gate_b_observer": 0}
    assert guard_path.read_bytes() == guard_raw
    assert not lock.exists()


def test_bootstrap_and_run005_host_preflight_share_lowercase_fuel_binding(tmp_path, monkeypatch):
    monkeypatch.setenv("ROS_HOME", str(tmp_path / "ros_home"))
    monkeypatch.setenv("ROS_LOG_DIR", str(tmp_path / "ros_log"))
    bootstrap_path = ROOT / "ros2_ws/src/ROBOT_URDF_final_description/launch/sim_eval_nav2_baseline_bootstrap.launch.py"
    spec = importlib.util.spec_from_file_location("run005_bootstrap_fuel_contract", bootstrap_path)
    assert spec and spec.loader
    bootstrap = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bootstrap)

    sdf = tmp_path / "world.sdf"
    sdf.write_text(
        "<sdf><world name='w'>"
        f"<include><uri>{DEPOT_URI}</uri></include>"
        f"<include><uri>{TUGBOT_URI}</uri></include>"
        "</world></sdf>", encoding="utf-8",
    )
    lower = _valid_fuel_cache(tmp_path / "fuel-lower")
    launch_paths = bootstrap.validate_fuel_layout(sdf, lower)
    host_paths = runner.validate_fuel_cache_layout(FUEL_URIS, lower, lower)
    assert {uri: Path(path).resolve() for uri, path in launch_paths.items()} == {
        uri: Path(path).resolve() for uri, path in host_paths.items()
    }
    for uri, expected_suffix in (
        (DEPOT_URI, "openrobotics/models/depot/1"),
        (TUGBOT_URI, "movai/models/tugbot/1"),
    ):
        assert launch_paths[uri].as_posix().endswith(expected_suffix)

    upper = tmp_path / "fuel-uppercase"
    for owner, model in (("OpenRobotics", "Depot"), ("MovAi", "Tugbot")):
        version = upper / "fuel.gazebosim.org" / owner / "models" / model / "1"
        version.mkdir(parents=True)
        (version / "model.config").write_text("<model/>", encoding="utf-8")
        (version / "model.sdf").write_text("<sdf/>", encoding="utf-8")
    with pytest.raises(RuntimeError):
        bootstrap.validate_fuel_layout(sdf, upper)
    with pytest.raises(RuntimeError):
        runner.validate_fuel_cache_layout(FUEL_URIS, upper, upper)


def test_run005_attempt001_historical_pins_are_git_blob_only_and_match_exact_bytes():
    historical_guard = json.loads(_git_blob(ROOT, RUN005_ATTEMPT_001_SHA, RUN005_GUARD_REL))
    pins = historical_guard["source_pins"]
    assert pins
    for relative, expected in pins.items():
        blob = _git_blob(ROOT, RUN005_ATTEMPT_001_SHA, relative)
        assert hashlib.sha256(blob).hexdigest() == expected["sha256"], relative
        assert len(blob) == expected["size_bytes"], relative


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
