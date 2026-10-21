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


def _acquired_campaign_handler():
    handler = runner.SigtermHandler()
    handler.mark_guard_acquired()
    handler.begin_campaign()
    return handler


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


def _fake_route_sysfs(tmp_path, interface="enp2s0", *, physical=True):
    from types import SimpleNamespace

    sysfs = tmp_path / "sys"
    (sysfs / "devices/virtual/net").mkdir(parents=True)
    net = sysfs / "class/net" / interface
    net.mkdir(parents=True)
    if physical:
        device = sysfs / "devices/pci0000/0000:00:00.0"
        device.mkdir(parents=True)
        (net / "device").symlink_to(device)

    def command(argv, **_kwargs):
        if argv[:7] == ["ip", "-j", "-4", "route", "show", "table", "main"]:
            return SimpleNamespace(returncode=0, stdout=json.dumps([
                {"dst": "default", "dev": interface, "metric": 100,
                 "prefsrc": "192.168.50.23", "gateway": "192.168.50.1"}]), stderr="")
        if argv[:4] == ["ip", "-j", "-d", "link"]:
            return SimpleNamespace(returncode=0, stdout=json.dumps([
                {"ifname": interface, "flags": ["BROADCAST", "UP"], "operstate": "UP"}]), stderr="")
        if argv[:4] == ["ip", "-j", "-4", "addr"]:
            return SimpleNamespace(returncode=0, stdout=json.dumps([
                {"ifname": interface, "addr_info": [
                    {"family": "inet", "local": "192.168.50.23", "prefixlen": 24}]}]), stderr="")
        if argv[0:2] == ["gz", "topic"]:
            return SimpleNamespace(returncode=0, stdout="published one message", stderr="")
        raise AssertionError(f"unexpected command: {argv}")
    return sysfs, command


def test_gz_transport_capability_selects_local_default_route_and_sets_shared_environment(tmp_path):
    sysfs, base_command = _fake_route_sysfs(tmp_path)
    commands = []
    def command(argv, **kwargs):
        commands.append((list(argv), kwargs))
        return base_command(argv, **kwargs)

    env = {"PATH": "/fake/bin", "GZ_PARTITION": "wrong"}
    record = {}
    facts = runner.validate_gz_transport_host_capability(
        env, runner.PARTITION, command_runner=command, sysfs_root=sysfs, record=record)
    assert facts["interface"] == "enp2s0" and facts["ipv4"] == "192.168.50.23"
    assert facts["probe"]["status"] == "PASS"
    assert env["GZ_IP"] == "192.168.50.23" and env["GZ_PARTITION"] == runner.PARTITION
    probe_command, probe_kwargs = commands[-1]
    assert probe_command[:2] == ["gz", "topic"] and "-p" in probe_command
    assert probe_kwargs["env"]["GZ_IP"] == "192.168.50.23"
    assert probe_kwargs["env"]["GZ_PARTITION"] == runner.PARTITION
    assert record["gz_transport_host_capability"]["probe"]["output_sha256"]
    assert "published one message" not in json.dumps(record)


def test_every_campaign_component_spawn_inherits_the_verified_partition_and_gz_ip(tmp_path, monkeypatch):
    captured = []
    class Child:
        pid = 501
    def popen(_command, *, env, **_kwargs):
        captured.append(dict(env))
        return Child()
    monkeypatch.setattr(runner.subprocess, "Popen", popen)
    monkeypatch.setattr(runner.os, "getpgid", lambda pid: pid)
    monkeypatch.setattr(runner, "_process_group_members", lambda pgid: {
        "live_member_pids": [pgid], "zombie_member_pids": [], "verified": True,
        "inspection_errors": []})
    env = {"GZ_IP": "192.168.50.23", "GZ_PARTITION": runner.PARTITION}
    ledger = {}
    for name in ("bootstrap", "composite", "cpp_observer", "gate_b_observer"):
        runner._spawn_owned_process(["fake", name], name=name, cwd=tmp_path, env=env,
            log_path=tmp_path / f"{name}.log", processes=[], ownership_ledger=ledger)
    assert len(captured) == 4
    assert all(row["GZ_IP"] == "192.168.50.23" and row["GZ_PARTITION"] == runner.PARTITION
               for row in captured)


@pytest.mark.parametrize(("mutation", "reason"), [
    ("missing_route", "DEFAULT_ROUTE_MISSING"),
    ("docker_interface", "ROUTE_INTERFACE_NOT_PHYSICAL"),
    ("loopback_source", "DEFAULT_ROUTE_SOURCE_NOT_LOCAL"),
    ("link_local_source", "DEFAULT_ROUTE_SOURCE_NOT_LOCAL"),
    ("interface_down", "ROUTE_INTERFACE_DOWN"),
    ("source_not_on_route_interface", "DEFAULT_ROUTE_SOURCE_NOT_LOCAL"),
    ("address_interface_mismatch", "ROUTE_INTERFACE_ADDRESS_INVALID"),
])
def test_gz_default_route_selection_fails_closed(tmp_path, mutation, reason):
    sysfs, base_command = _fake_route_sysfs(tmp_path, interface="docker0",
                                            physical=mutation != "docker_interface")
    def command(argv, **kwargs):
        result = base_command(argv, **kwargs)
        if mutation == "missing_route" and argv[3:5] == ["route", "show"]:
            from types import SimpleNamespace
            return SimpleNamespace(returncode=0, stdout="[]", stderr="")
        if mutation in {"loopback_source", "link_local_source"} and argv[0:4] == ["ip", "-j", "-4", "route"]:
            from types import SimpleNamespace
            source = "127.0.0.1" if mutation == "loopback_source" else "169.254.1.2"
            return SimpleNamespace(returncode=0, stdout=json.dumps([{"dst":"default","dev":"docker0","metric":100,"prefsrc":source}]), stderr="")
        if mutation == "interface_down" and argv[0:4] == ["ip", "-j", "-d", "link"]:
            from types import SimpleNamespace
            return SimpleNamespace(returncode=0, stdout=json.dumps([{"ifname":"docker0","flags":[],"operstate":"DOWN"}]), stderr="")
        if mutation == "source_not_on_route_interface" and argv[0:4] == ["ip", "-j", "-4", "addr"]:
            from types import SimpleNamespace
            return SimpleNamespace(returncode=0, stdout=json.dumps([{"ifname":"docker0","addr_info":[{"family":"inet","local":"192.168.50.99"}]}]), stderr="")
        if mutation == "address_interface_mismatch" and argv[0:4] == ["ip", "-j", "-4", "addr"]:
            from types import SimpleNamespace
            return SimpleNamespace(returncode=0, stdout=json.dumps([{"ifname":"other0","addr_info":[{"family":"inet","local":"192.168.50.23"}]}]), stderr="")
        return result
    with pytest.raises(RuntimeError, match=f"^GZ_TRANSPORT_HOST_CAPABILITY_UNAVAILABLE:{reason}$"):
        runner.validate_gz_transport_host_capability({}, runner.PARTITION,
                                                      command_runner=command, sysfs_root=sysfs)


@pytest.mark.parametrize(("mode", "reason"), [
    ("timeout", "GZ_TOPIC_PUBLISH_TIMEOUT"),
    ("nonzero", "GZ_TOPIC_PUBLISH_EXIT_NONZERO"),
    ("unreachable", "GZ_TOPIC_PUBLISH_TRANSPORT_ERROR"),
])
def test_gz_publish_probe_fails_closed_and_records_sanitized_result(tmp_path, mode, reason):
    from types import SimpleNamespace
    sysfs, base_command = _fake_route_sysfs(tmp_path)
    def command(argv, **kwargs):
        if argv[:2] == ["gz", "topic"]:
            if mode == "timeout":
                raise subprocess.TimeoutExpired(argv, 1)
            return SimpleNamespace(returncode=2 if mode == "nonzero" else 0,
                                   stdout="", stderr="Network is unreachable" if mode == "unreachable" else "failed")
        return base_command(argv, **kwargs)
    record = {}
    with pytest.raises(RuntimeError, match=f"^GZ_TRANSPORT_HOST_CAPABILITY_UNAVAILABLE:{reason}$"):
        runner.validate_gz_transport_host_capability({}, runner.PARTITION,
                                                      command_runner=command, sysfs_root=sysfs, record=record)
    facts = record["gz_transport_host_capability"]
    assert facts["interface"] == "enp2s0" and facts["ipv4"] == "192.168.50.23"
    assert facts["status"] == "FAIL"


def test_preacquire_gz_probe_failure_persists_sanitized_route_and_probe_facts(tmp_path, monkeypatch):
    from types import SimpleNamespace
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    evidence = tmp_path / "evidence"
    sysfs, base_command = _fake_route_sysfs(tmp_path)
    def command(argv, **kwargs):
        if argv[:2] == ["gz", "topic"]:
            return SimpleNamespace(returncode=0, stdout="", stderr="Network is unreachable")
        return base_command(argv, **kwargs)
    monkeypatch.setattr(runner, "prepare_ros_environment", lambda *_args: {"PATH": "/fake"})
    monkeypatch.setattr(runner, "host_preflight", lambda env, worktree, run_directory, partition,
                        map_root, fuel_root, pins, runtime_python, record: _preflight_transport_probe(
                            env, partition, record, command, sysfs))
    guard_path = runtime / "guard.json"
    guard = {"state": runner.PENDING, "capacity": 1, "acquisition_count": 0,
             "runtime_authorization": "NOT_GRANTED"}
    runner._atomic_write(guard_path, guard)
    lock = guard_path.with_suffix(".json.lock")
    record = {"run_id": runner.RUN_ID, "partition": runner.PARTITION,
              "guard_state_before": runner.PENDING,
              "call_counts": {"runner": 1, "bootstrap": 0, "composite": 0,
                              "cpp_observer": 0, "gate_b_observer": 0}}
    result = runner.preacquire_preflight(runtime, {}, evidence, runner.PARTITION,
        tmp_path / "map", tmp_path / "fuel", {}, guard_path, lock, guard, {}, "a" * 40,
        runner.INTEGRATION_BASE, Path(runner.RUNTIME_PYTHON_PATH), record)
    assert result[2] is None and lock.exists() is False
    stored = runner.load_canonical_json(evidence / "run_record.json")
    capability = stored["gz_transport_host_capability"]
    assert capability["interface"] == "enp2s0" and capability["ipv4"] == "192.168.50.23"
    assert capability["partition"] == runner.PARTITION and capability["probe"]["status"] == "FAIL"
    assert "Network is unreachable" not in json.dumps(stored)
    assert (evidence / "preflight_failure.json").is_file()


def _preflight_transport_probe(env, partition, record, command, sysfs):
    return runner.validate_gz_transport_host_capability(
        env, partition, command_runner=command, sysfs_root=sysfs, record=record)


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
     {"completed": True, "clean": True, "ordered": True, "order_correct": True,
      "verified": True, "graceful": True, "escalation_history": []},
     "STEP07_NAV2_BASELINE_RUN005_FAIL_NO_RETRY_GUARD_CONSUMED"),
    ({"all": True}, {"pre_teardown_failure": "RuntimeError:campaign failed"},
     {"completed": True, "clean": True, "ordered": True, "order_correct": True,
      "verified": True, "graceful": True, "escalation_history": []},
     "STEP07_NAV2_BASELINE_RUN005_FAIL_NO_RETRY_GUARD_CONSUMED"),
    ({"all": True}, {},
     {"completed": True, "clean": True, "ordered": True, "order_correct": True,
      "verified": True, "graceful": True, "escalation_history": []},
     "STEP07_NAV2_BASELINE_RUN005_PASS_PENDING_INDEPENDENT_EVIDENCE_AUDIT"),
    ({"all": True}, {},
     {"completed": True, "clean": True, "ordered": True, "order_correct": True,
      "verified": True, "graceful": False, "escalation_history": [{"signal": "SIGTERM"}]},
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
    handler = _acquired_campaign_handler()
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
        {"completed": True, "clean": True, "ordered": True, "order_correct": True,
         "verified": True, "graceful": True, "escalation_history": []},
        run_directory, handler)
    assert result["terminal_outcome"] == "STEP07_NAV2_BASELINE_RUN005_FAIL_NO_RETRY_GUARD_CONSUMED"
    assert "RUNNER_INTERRUPTED_BY_SIGNAL:SIGTERM" in result["failure_reason_literals"]
    assert runner.load_canonical_json(run_directory / "run_record.json")["terminal_outcome"].endswith(
        "FAIL_NO_RETRY_GUARD_CONSUMED")
    assert (run_directory / "artifact_manifest.json").is_file()
    assert (run_directory / "SHA256SUMS.txt").is_file()


def test_process_group_kill_wait_and_proc_errors_cannot_report_clean(tmp_path, monkeypatch):
    monkeypatch.setattr(runner.os, "getpgid", lambda pid: pid)
    class FakeProcess:
        pid = 212
        returncode = None

        def poll(self): return None
        def wait(self, timeout):
            raise subprocess.TimeoutExpired("fake", timeout)

    member = {"name": "composite", "pid": 212, "pgid": 212, "ownership_verified": True}
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
        {"completed": True, "clean": False, "ordered": True, "order_correct": True,
         "verified": False, "graceful": False, "escalation_history": [{"signal": "SIGTERM"}],
         "errors": result["errors"]}, run_directory, runner.SigtermHandler())
    assert verdict["terminal_outcome"].endswith("FAIL_NO_RETRY_GUARD_CONSUMED")
    assert runner.load_canonical_json(run_directory / "run_record.json")["terminal_outcome"].endswith(
        "FAIL_NO_RETRY_GUARD_CONSUMED")
    assert (run_directory / "artifact_manifest.json").is_file()
    assert (run_directory / "SHA256SUMS.txt").is_file()


def test_sigterm_during_teardown_still_stops_both_groups_and_persists_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(runner.os, "getpgid", lambda pid: pid)
    handler = _acquired_campaign_handler()
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
    composite = {"name": "composite", "pid": 31, "pgid": 31, "ownership_verified": True}
    bootstrap = {"name": "bootstrap", "pid": 32, "pgid": 32, "ownership_verified": True}
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
            {}, runner.PARTITION,
            command_runner=lambda *_a, **_k: (_ for _ in ()).throw(PermissionError("route denied")),
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
        "GZ_TRANSPORT_HOST_CAPABILITY_UNAVAILABLE:DEFAULT_ROUTE_COMMAND_FAILED"]
    assert record["guard_state_after"] == runner.PENDING
    assert record["call_counts"] == {"runner": 1, "bootstrap": 0, "composite": 0,
                                      "cpp_observer": 0, "gate_b_observer": 0}
    assert guard_path.read_bytes() == raw_guard and not lock.exists()
    assert (evidence / "run_record.json").is_file()
    assert (evidence / "preflight_failure.json").is_file()


def test_sigterm_before_guard_acquisition_writes_preacquire_failure_without_consuming(tmp_path, monkeypatch):
    runtime_worktree = tmp_path / "runtime"
    runtime_worktree.mkdir()
    run_directory = tmp_path / "evidence"
    guard_path = runtime_worktree / "guard.json"
    guard = {"state": runner.PENDING, "capacity": 1, "acquisition_count": 0,
             "runtime_authorization": "NOT_GRANTED"}
    guard_bytes = json.dumps(guard, sort_keys=True, separators=(",", ":")).encode()
    guard_path.write_bytes(guard_bytes)
    lock = guard_path.with_suffix(".json.lock")
    launches = []
    handler = runner.SigtermHandler()
    monkeypatch.setattr(runner, "prepare_ros_environment", lambda *_: {"PATH": "/fake"})
    monkeypatch.setattr(runner, "host_preflight", lambda *_args: {})
    monkeypatch.setattr(runner, "acquire_guard", lambda *_a, **_k: pytest.fail("must not acquire"))

    def interrupt_before_acquire(*_args, **_kwargs):
        launches.append("acquire-handoff")
        handler(runner.signal.SIGTERM, None)

    monkeypatch.setattr(runner, "acquire_guard_with_sigterm_handoff", interrupt_before_acquire)
    record = {"run_id": runner.RUN_ID, "partition": runner.PARTITION,
              "guard_state_before": runner.PENDING,
              "call_counts": {"runner": 1, "bootstrap": 0, "composite": 0,
                              "cpp_observer": 0, "gate_b_observer": 0}}
    result = runner.preacquire_preflight(
        runtime_worktree, {}, run_directory, runner.PARTITION, tmp_path / "map", tmp_path / "fuel",
        {}, guard_path, lock, guard, {}, "a" * 40, runner.INTEGRATION_BASE,
        Path(runner.RUNTIME_PYTHON_PATH), record, sigterm_handler=handler)
    assert launches == ["acquire-handoff"]
    assert result[2] is None
    assert result[3]["preacquire_failure_literal"] == (
        "PREACQUIRE_FAILURE:RunnerInterruptedBySignal:RUNNER_INTERRUPTED_BY_SIGNAL:SIGTERM")
    assert guard_path.read_bytes() == guard_bytes and not lock.exists()
    stored = runner.load_canonical_json(run_directory / "run_record.json")
    assert stored["guard_acquired"] is False and stored["guard_state_after"] == runner.PENDING
    assert stored["terminal_outcome"] == "STEP07_NAV2_BASELINE_RUN005_PREACQUIRE_PREFLIGHT_FAILED_NO_GUARD_CONSUMED"
    assert runner.terminal_exit_code(stored) == 2
    assert (run_directory / "artifact_manifest.json").is_file()
    assert (run_directory / "SHA256SUMS.txt").is_file()


def test_sigterm_after_guard_mutation_is_buffered_through_handoff_and_finalized_fail(tmp_path, monkeypatch):
    runtime_worktree = tmp_path / "runtime"
    runtime_worktree.mkdir()
    run_directory = tmp_path / "evidence"
    guard_path = runtime_worktree / "guard.json"
    lock = guard_path.with_suffix(".json.lock")
    guard = {"state": runner.PENDING, "capacity": 1, "acquisition_count": 0,
             "runtime_authorization": "NOT_GRANTED"}
    guard_path.write_text(json.dumps(guard))
    handler = runner.SigtermHandler()
    monkeypatch.setattr(runner, "prepare_ros_environment", lambda *_: {"PATH": "/fake"})
    monkeypatch.setattr(runner, "host_preflight", lambda *_args: {"ready": True})

    def acquire(*_args, **_kwargs):
        consumed = {**guard, "state": "CONSUMED", "acquisition_count": 1}
        guard_path.write_text(json.dumps(consumed))
        lock.write_text("capacity-one")
        return consumed

    monkeypatch.setattr(runner, "acquire_guard", acquire)
    mask_events = []

    def masked_signal(how, mask):
        mask_events.append(how)
        if how == runner.signal.SIG_SETMASK:
            handler(runner.signal.SIGTERM, None)
        return set()

    record = {"run_id": runner.RUN_ID, "partition": runner.PARTITION,
              "guard_state_before": runner.PENDING,
              "call_counts": {"runner": 1, "bootstrap": 0, "composite": 0,
                              "cpp_observer": 0, "gate_b_observer": 0}}
    env, preflight, consumed, failure = runner.preacquire_preflight(
        runtime_worktree, {}, run_directory, runner.PARTITION, tmp_path / "map", tmp_path / "fuel",
        {}, guard_path, lock, guard, {}, "a" * 40, runner.INTEGRATION_BASE,
        Path(runner.RUNTIME_PYTHON_PATH), record, sigterm_handler=handler,
        mask_signals=masked_signal)
    assert consumed["state"] == "CONSUMED" and consumed["acquisition_count"] == 1
    assert failure is None and handler.guard_acquired and handler.interrupted
    assert mask_events == [runner.signal.SIG_BLOCK, runner.signal.SIG_SETMASK]
    with pytest.raises(runner.RunnerInterruptedBySignal, match="RUNNER_INTERRUPTED_BY_SIGNAL:SIGTERM"):
        handler.begin_campaign()
    record.update({"guard_acquired": True, "guard_state_after": "CONSUMED",
                   "guard_acquisition_count": 1, "call_counts": record["call_counts"]})
    result = runner.finalize_campaign_after_acquisition(
        record=record, runtime_acceptance={"all": True}, composite_proc=None,
        composite_member=None, bootstrap_proc=None, bootstrap_member=None,
        collector_procs={}, collector_members={}, bootstrap_calls=0,
        composite_calls=0, cpp_calls=0, gate_b_calls=0, run_directory=run_directory,
        sigterm_handler=handler, previous_sigterm_handler=runner.signal.getsignal(runner.signal.SIGTERM))
    assert result["terminal_outcome"].endswith("FAIL_NO_RETRY_GUARD_CONSUMED")
    assert runner.terminal_exit_code(result) == 2
    assert "RUNNER_INTERRUPTED_BY_SIGNAL:SIGTERM" in result["failure_reason_literals"]
    assert json.loads(guard_path.read_text())["state"] == "CONSUMED" and lock.exists()
    assert runner.load_canonical_json(run_directory / "run_record.json")["guard_acquired"] is True
    assert (run_directory / "artifact_manifest.json").is_file()
    assert (run_directory / "SHA256SUMS.txt").is_file()


def test_sigterm_after_checksums_before_handler_restore_rewrites_bundle_fail(tmp_path, monkeypatch):
    run_directory = tmp_path / "evidence"
    run_directory.mkdir()
    handler = runner.SigtermHandler()
    handler.mark_guard_acquired()
    handler.begin_campaign()
    original_manifest = runner._write_artifact_manifest
    delivered = False

    def write_then_interrupt(directory):
        nonlocal delivered
        original_manifest(directory)
        if not delivered:
            delivered = True
            handler(runner.signal.SIGTERM, None)

    monkeypatch.setattr(runner, "_write_artifact_manifest", write_then_interrupt)
    previous = runner.signal.getsignal(runner.signal.SIGTERM)
    result = runner.finalize_campaign_after_acquisition(
        record={"call_counts": {"runner": 1}}, runtime_acceptance={"all": True},
        composite_proc=None, composite_member=None, bootstrap_proc=None, bootstrap_member=None,
        collector_procs={}, collector_members={}, bootstrap_calls=1, composite_calls=1,
        cpp_calls=0, gate_b_calls=0, run_directory=run_directory,
        sigterm_handler=handler, previous_sigterm_handler=previous)
    assert delivered and result["terminal_outcome"].endswith("FAIL_NO_RETRY_GUARD_CONSUMED")
    assert "RUNNER_INTERRUPTED_BY_SIGNAL:SIGTERM" in result["failure_reason_literals"]
    record_bytes = (run_directory / "run_record.json").read_bytes()
    manifest = runner.load_canonical_json(run_directory / "artifact_manifest.json")
    item = next(x for x in manifest["artifacts"] if x["path"] == "run_record.json")
    assert item["sha256"] == hashlib.sha256(record_bytes).hexdigest()
    assert item["size_bytes"] == len(record_bytes)
    assert runner.signal.getsignal(runner.signal.SIGTERM) == previous
    assert (run_directory / "SHA256SUMS.txt").is_file()


def test_sigterm_at_terminal_commit_boundary_fails_before_handler_restore(tmp_path, monkeypatch):
    run_directory = tmp_path / "evidence"
    run_directory.mkdir()
    handler = _acquired_campaign_handler()
    original_restore = handler.restore
    delivered = False

    def interrupt_before_restore(previous_handler):
        nonlocal delivered
        if not delivered:
            delivered = True
            handler(runner.signal.SIGTERM, None)
        return original_restore(previous_handler)

    monkeypatch.setattr(handler, "restore", interrupt_before_restore)
    previous = runner.signal.getsignal(runner.signal.SIGTERM)
    result = runner.finalize_campaign_after_acquisition(
        record={"call_counts": {"runner": 1}}, runtime_acceptance={"all": True},
        composite_proc=None, composite_member=None, bootstrap_proc=None, bootstrap_member=None,
        collector_procs={}, collector_members={}, bootstrap_calls=0, composite_calls=0,
        cpp_calls=0, gate_b_calls=0, run_directory=run_directory,
        sigterm_handler=handler, previous_sigterm_handler=previous)
    assert delivered and runner.terminal_exit_code(result) == 2
    assert result["terminal_outcome"].endswith("FAIL_NO_RETRY_GUARD_CONSUMED")
    persisted = runner.load_canonical_json(run_directory / "run_record.json")
    assert persisted["terminal_outcome"] == result["terminal_outcome"]
    manifest = runner.load_canonical_json(run_directory / "artifact_manifest.json")
    artifact = next(item for item in manifest["artifacts"] if item["path"] == "run_record.json")
    raw = (run_directory / "run_record.json").read_bytes()
    assert artifact["sha256"] == hashlib.sha256(raw).hexdigest()
    assert artifact["size_bytes"] == len(raw)
    assert runner.signal.getsignal(runner.signal.SIGTERM) == previous


def test_sigterm_after_terminal_commit_does_not_rewrite_completed_campaign(tmp_path, monkeypatch):
    monkeypatch.setattr(runner.os, "getpgid", lambda pid: pid)
    run_directory = tmp_path / "evidence"
    run_directory.mkdir()
    handler = _acquired_campaign_handler()
    class FakeProcess:
        def __init__(self, pid): self.pid, self.returncode = pid, None
        def poll(self): return None
        def wait(self, timeout): self.returncode = 0; return 0
    monkeypatch.setattr(runner.os, "killpg", lambda *_args: None)
    monkeypatch.setattr(runner, "_process_group_members", lambda _pgid: {
        "live_member_pids": [], "zombie_member_pids": [], "verified": True,
        "inspection_errors": []})
    previous = runner.signal.getsignal(runner.signal.SIGTERM)
    result = runner.finalize_campaign_after_acquisition(
        record={"call_counts": {"runner": 1}}, runtime_acceptance={"all": True},
        composite_proc=FakeProcess(11), composite_member={"name":"composite","pid":11,"pgid":11,"ownership_verified":True},
        bootstrap_proc=FakeProcess(12), bootstrap_member={"name":"bootstrap","pid":12,"pgid":12,"ownership_verified":True},
        collector_procs={}, collector_members={}, bootstrap_calls=1, composite_calls=1,
        cpp_calls=0, gate_b_calls=0, run_directory=run_directory,
        sigterm_handler=handler, previous_sigterm_handler=previous)
    assert runner.terminal_exit_code(result) == 0
    raw = (run_directory / "run_record.json").read_bytes()
    handler(runner.signal.SIGTERM, None)
    assert handler.interrupted is False
    assert (run_directory / "run_record.json").read_bytes() == raw


def test_normal_completion_restores_handler_and_keeps_pass_bundle(tmp_path, monkeypatch):
    monkeypatch.setattr(runner.os, "getpgid", lambda pid: pid)
    run_directory = tmp_path / "evidence"
    run_directory.mkdir()
    handler = _acquired_campaign_handler()
    class FakeProcess:
        def __init__(self, pid): self.pid, self.returncode = pid, None
        def poll(self): return None
        def wait(self, timeout): self.returncode = 0; return 0
    kill_order = []
    monkeypatch.setattr(runner.os, "killpg", lambda pgid, _sig: kill_order.append(pgid))
    monkeypatch.setattr(runner, "_process_group_members", lambda _pgid: {
        "live_member_pids": [], "zombie_member_pids": [], "verified": True,
        "inspection_errors": []})
    previous = runner.signal.getsignal(runner.signal.SIGTERM)
    result = runner.finalize_campaign_after_acquisition(
        record={"call_counts": {"runner": 1}}, runtime_acceptance={"all": True},
        composite_proc=FakeProcess(11), composite_member={"name":"composite","pid":11,"pgid":11,"ownership_verified":True},
        bootstrap_proc=FakeProcess(12), bootstrap_member={"name":"bootstrap","pid":12,"pgid":12,"ownership_verified":True},
        collector_procs={}, collector_members={}, bootstrap_calls=1, composite_calls=1,
        cpp_calls=0, gate_b_calls=0, run_directory=run_directory,
        sigterm_handler=handler, previous_sigterm_handler=previous)
    assert result["terminal_outcome"].endswith("PASS_PENDING_INDEPENDENT_EVIDENCE_AUDIT")
    assert runner.terminal_exit_code(result) == 0
    before = (run_directory / "run_record.json").read_bytes()
    assert runner.signal.getsignal(runner.signal.SIGTERM) == previous
    assert kill_order == [11, 12]
    assert not handler.interrupted
    assert (run_directory / "artifact_manifest.json").is_file()
    assert (run_directory / "SHA256SUMS.txt").is_file()
    assert (run_directory / "run_record.json").read_bytes() == before


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
        {"completed": True, "clean": True, "ordered": True, "order_correct": True,
         "verified": True, "graceful": True, "escalation_history": []},
    )
    assert result["terminal_outcome"].endswith("PASS_PENDING_INDEPENDENT_EVIDENCE_AUDIT")
    assert all(result["acceptance"].values())
    source = RUNNER_PATH.read_text()
    assert source.index("preacquire_preflight(") < source.index("_spawn_owned_process(", source.index("def main():"))


def test_best_effort_teardown_attempts_composite_before_bootstrap(tmp_path, monkeypatch):
    order = []
    composite = {"name": "composite", "pid": 31, "pgid": 31, "ownership_verified": True}
    bootstrap = {"name": "bootstrap", "pid": 32, "pgid": 32, "ownership_verified": True}

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

    def sourced_host_preflight(env, _worktree, _run_directory, _partition, _map, _fuel, _pins, runtime_python, _record=None):
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


def _assert_real_bundle(directory):
    for line in (directory / "SHA256SUMS.txt").read_text().splitlines():
        expected, relative = line.split("  ", 1)
        assert hashlib.sha256((directory / relative).read_bytes()).hexdigest() == expected
    manifest = runner.load_canonical_json(directory / "artifact_manifest.json")
    for row in manifest["artifacts"]:
        raw = (directory / row["path"]).read_bytes()
        assert row["sha256"] == hashlib.sha256(raw).hexdigest()
        assert row["size_bytes"] == len(raw)


@pytest.mark.parametrize("fault", ["after_replace", "unmask"])
def test_consumed_guard_readback_overrides_handoff_exception_and_saves_terminal_fail(tmp_path, monkeypatch, fault):
    import step07_run005_runtime_guard as guard_module
    worktree = tmp_path / "runtime"; worktree.mkdir()
    guard_path = worktree / "guard.json"; lock = guard_path.with_suffix(".json.lock")
    seed = {"run_id": runner.RUN_ID, "state": runner.PENDING, "capacity": 1,
            "acquisition_count": 0, "runtime_authorization": "NOT_GRANTED"}
    guard_path.write_bytes(json.dumps(seed, sort_keys=True, separators=(",", ":")).encode())
    auth = {"owner_authorization": "TEST_EXACT_AUTH", "owner_authorization_scope": runner.AUTH_SCOPE,
            "owner_authorization_run_id": runner.RUN_ID, "owner_authorization_review_commit": "a" * 40,
            "owner_authorization_integration_base": runner.INTEGRATION_BASE}
    handler = runner.SigtermHandler()
    monkeypatch.setattr(runner, "prepare_ros_environment", lambda *_: {})
    monkeypatch.setattr(runner, "host_preflight", lambda *_: {})
    original_replace = guard_module.os.replace
    def replace(source, target):
        original_replace(source, target)
        if Path(target) == guard_path and fault == "after_replace":
            raise OSError("AFTER_REPLACE")
    monkeypatch.setattr(guard_module.os, "replace", replace)
    def masks(how, _mask):
        if fault == "unmask" and how == runner.signal.SIG_SETMASK:
            raise OSError("UNMASK_FAILED")
        return set()
    directory = tmp_path / "evidence"
    record = {"call_counts": {"runner": 1}, "guard_state_before": runner.PENDING}
    _, _, consumed, failure = runner.preacquire_preflight(
        worktree, {}, directory, runner.PARTITION, tmp_path / "map", tmp_path / "fuel", {},
        guard_path, lock, seed, auth, "a" * 40, runner.INTEGRATION_BASE,
        Path(runner.RUNTIME_PYTHON_PATH), record, sigterm_handler=handler, mask_signals=masks)
    assert consumed == runner.load_guard(guard_path)
    assert consumed["state"] == "CONSUMED" and handler.guard_acquired
    assert lock.exists() and not directory.exists()
    with pytest.raises(FileExistsError):
        runner.acquire_guard(guard_path, seed, auth, review_commit="a" * 40,
                             integration_base=runner.INTEGRATION_BASE)
    record.update({"guard_acquired": True, "guard_state_after": consumed["state"],
                   "guard_acquisition_count": consumed["acquisition_count"],
                   "pre_teardown_failure": str(failure)})
    result = runner.finalize_campaign_after_acquisition(
        record=record, runtime_acceptance={"all": True}, composite_proc=None,
        composite_member=None, bootstrap_proc=None, bootstrap_member=None,
        collector_procs={}, collector_members={}, bootstrap_calls=0, composite_calls=0,
        cpp_calls=0, gate_b_calls=0, run_directory=directory,
        sigterm_handler=handler, previous_sigterm_handler=runner.signal.getsignal(runner.signal.SIGTERM),
        ownership_ledger={})
    assert runner.terminal_exit_code(result) == 2
    assert result["guard_acquired"] and result["guard_acquisition_count"] == 1
    assert result["terminal_outcome"].endswith("FAIL_NO_RETRY_GUARD_CONSUMED")
    assert result["runtime_execution"] is False and lock.exists()
    _assert_real_bundle(directory)


def test_unreadable_runtime_guard_never_falls_back_to_source_pending_seed(tmp_path, monkeypatch):
    guard = tmp_path / "runtime_guard.json"; guard.write_bytes(b'not-json')
    lock = guard.with_suffix(".json.lock"); lock.write_bytes(b'held')
    directory = tmp_path / "evidence"
    record = {"call_counts": {"runner": 1}}
    result = runner.recover_guard_handoff_failure(
        runtime_guard=guard, guard_lock=lock, guard={"state": runner.PENDING}, authorization={},
        review_commit="a" * 40, integration_base=runner.INTEGRATION_BASE,
        error=OSError("HANDOFF"), run_directory=directory, record=record)
    assert result[2] is None and record["guard_acquired"] is None
    assert record["guard_state_after"] == "UNVERIFIED"
    assert "NO_GUARD_CONSUMED" not in record["terminal_outcome"]
    assert lock.exists() and guard.read_bytes() == b'not-json'
    _assert_real_bundle(directory)


@pytest.mark.parametrize("name", ["bootstrap", "composite", "cpp_observer", "gate_b_observer"])
@pytest.mark.parametrize("stage", ["popen_return", "getpgid", "snapshot", "registration", "caller_handoff"])
def test_sigterm_at_spawn_boundaries_retains_every_child_for_ledger_teardown(tmp_path, monkeypatch, name, stage):
    _exercise_owned_spawn_boundary(tmp_path, monkeypatch, name, stage, "SIGTERM")


@pytest.mark.parametrize("stage", ["getpgid", "snapshot", "registration"])
def test_oserror_after_popen_stops_known_child_without_unverified_killpg(tmp_path, monkeypatch, stage):
    _exercise_owned_spawn_boundary(tmp_path, monkeypatch, "composite", stage, "OSError")


def _exercise_owned_spawn_boundary(tmp_path, monkeypatch, target, stage, fault):
    consumed_guard = tmp_path / "consumed_guard.json"
    guard_bytes = b'{"acquisition_count":1,"capacity":1,"state":"CONSUMED"}'
    consumed_guard.write_bytes(guard_bytes)
    consumed_lock = consumed_guard.with_suffix(".json.lock"); consumed_lock.write_bytes(b"held")
    handler = _acquired_campaign_handler()
    ledger = {}; children = {}; signals = []; child_signals = []; delivered = False
    current = None
    def inject(where):
        nonlocal delivered
        if not delivered and current == target and stage == where:
            delivered = True
            if fault == "SIGTERM": handler(runner.signal.SIGTERM, None)
            else: raise OSError("INJECTED_AFTER_POPEN")
    class Child:
        def __init__(self, pid): self.pid, self.returncode = pid, None
        def poll(self): return self.returncode
        def wait(self, timeout): self.returncode = 0; return 0
        def send_signal(self, sig): child_signals.append(self.pid)
        def kill(self): self.returncode = -9
    def popen(*_args, **_kwargs):
        child = Child(101 + len(children)); children[child.pid] = child
        inject("popen_return")
        return child
    def getpgid(pid): inject("getpgid"); return pid
    def snapshot(pgid):
        inject("snapshot")
        return {"live_member_pids": [pgid] if children[pgid].returncode is None else [],
                "zombie_member_pids": [], "verified": True, "inspection_errors": []}
    class Members(list):
        def append(self, item): super().append(item); inject("registration")
    members = Members()
    monkeypatch.setattr(runner.subprocess, "Popen", popen)
    monkeypatch.setattr(runner.os, "getpgid", getpgid)
    monkeypatch.setattr(runner, "_process_group_members", snapshot)
    def killpg(pgid, _sig):
        assert any(row["member"].get("ownership_verified") and row["member"]["pgid"] == pgid
                   for row in ledger.values())
        signals.append(pgid)
    monkeypatch.setattr(runner.os, "killpg", killpg)
    error = None
    for current in ("bootstrap", "composite", "cpp_observer", "gate_b_observer"):
        try:
            result = runner._spawn_owned_process(
                ["fake", current], name=current, cwd=tmp_path, env={},
                log_path=tmp_path / (current + ".log"), processes=members,
                ownership_ledger=ledger, sigterm_handler=handler)
            inject("caller_handoff")
        except (runner.RunnerInterruptedBySignal, OSError) as caught:
            error = caught
            break
    assert delivered and error is not None
    assert len(ledger) == len(children)
    assert all(row["process"] in children.values() for row in ledger.values())
    record = {"call_counts": {"runner": 1}, "pre_teardown_failure": str(error), "guard_acquired": True}
    directory = tmp_path / "evidence"
    previous = runner.signal.getsignal(runner.signal.SIGTERM)
    result = runner.finalize_campaign_after_acquisition(
        record=record, runtime_acceptance={"all": True}, composite_proc=None,
        composite_member=None, bootstrap_proc=None, bootstrap_member=None,
        collector_procs={}, collector_members={}, bootstrap_calls=0, composite_calls=0,
        cpp_calls=0, gate_b_calls=0, run_directory=directory, sigterm_handler=handler,
        previous_sigterm_handler=previous, ownership_ledger=ledger)
    assert runner.terminal_exit_code(result) == 2
    assert result["terminal_outcome"].endswith("FAIL_NO_RETRY_GUARD_CONSUMED")
    assert all(child.returncode is not None for child in children.values())
    if "composite" in ledger:
        comp = ledger["composite"]["member"]["pid"]; boot = ledger["bootstrap"]["member"]["pid"]
        if comp in signals and boot in signals: assert signals.index(comp) < signals.index(boot)
    if fault == "OSError":
        pid = ledger[target]["member"]["pid"]
        assert pid in child_signals and pid not in signals
        assert result["teardown"]["verified"] is False
    assert result["call_counts"]["bootstrap"] == int("bootstrap" in ledger)
    assert result["call_counts"]["composite"] == int("composite" in ledger)
    assert result["call_counts"]["cpp_observer"] == int("cpp_observer" in ledger)
    assert result["call_counts"]["gate_b_observer"] == int("gate_b_observer" in ledger)
    assert runner.signal.getsignal(runner.signal.SIGTERM) == previous
    assert consumed_guard.read_bytes() == guard_bytes and consumed_lock.read_bytes() == b"held"
    _assert_real_bundle(directory)


def test_all_four_components_use_the_same_owned_spawn_and_finalizer_ledger():
    import inspect
    body = inspect.getsource(runner.main)
    assert body.count("_spawn_owned_process(") == 4
    assert "subprocess.Popen" not in body
    assert body.count("ownership_ledger=ownership_ledger") == 5


def test_verified_ledger_all_acceptance_true_has_clean_ordered_pass_bundle(tmp_path, monkeypatch):
    ledger = {}; processes = []; children = {}; order = []
    handler = _acquired_campaign_handler()
    class Child:
        def __init__(self, pid): self.pid, self.returncode = pid, None
        def poll(self): return self.returncode
        def wait(self, timeout): self.returncode = 0; return 0
    def popen(*_args, **_kwargs):
        child = Child(301 + len(children)); children[child.pid] = child; return child
    monkeypatch.setattr(runner.subprocess, "Popen", popen)
    monkeypatch.setattr(runner.os, "getpgid", lambda pid: pid)
    monkeypatch.setattr(runner.os, "killpg", lambda pgid, _sig: order.append(pgid))
    monkeypatch.setattr(runner, "_process_group_members", lambda pgid: {
        "live_member_pids": [pgid] if children[pgid].returncode is None else [],
        "zombie_member_pids": [], "verified": True, "inspection_errors": []})
    for name in ("bootstrap", "composite", "cpp_observer", "gate_b_observer"):
        proc, _ = runner._spawn_owned_process(["fake"], name=name, cwd=tmp_path, env={},
            log_path=tmp_path / (name + ".log"), processes=processes,
            ownership_ledger=ledger, sigterm_handler=handler)
        if name.endswith("observer"): proc.wait(timeout=1)
    directory = tmp_path / "evidence"
    result = runner.finalize_campaign_after_acquisition(
        record={"call_counts": {"runner": 1}, "guard_acquired": True},
        runtime_acceptance={"all": True}, composite_proc=None, composite_member=None,
        bootstrap_proc=None, bootstrap_member=None, collector_procs={}, collector_members={},
        bootstrap_calls=0, composite_calls=0, cpp_calls=0, gate_b_calls=0,
        run_directory=directory, sigterm_handler=handler,
        previous_sigterm_handler=runner.signal.getsignal(runner.signal.SIGTERM), ownership_ledger=ledger)
    assert result["terminal_outcome"].endswith("PASS_PENDING_INDEPENDENT_EVIDENCE_AUDIT")
    assert runner.terminal_exit_code(result) == 0 and result["failure_reason_literals"] == []
    assert all(result["teardown"][key] for key in
               ("completed", "clean", "ordered", "order_correct", "verified", "graceful"))
    assert result["teardown"]["escalation_history"] == []
    assert order == [302, 301]
    assert result["call_counts"] == {"runner":1,"bootstrap":1,"composite":1,"cpp_observer":1,"gate_b_observer":1}
    _assert_real_bundle(directory)


def test_changed_group_never_receives_killpg_and_known_child_is_stopped(tmp_path, monkeypatch):
    calls = []
    class Child:
        pid = 901
        returncode = None
        def poll(self): return None
        def send_signal(self, _sig): calls.append("child")
        def wait(self, timeout): self.returncode = 0
    monkeypatch.setattr(runner.os, "getpgid", lambda _pid: 999)
    monkeypatch.setattr(runner.os, "killpg", lambda *_: pytest.fail("group not owned"))
    member={"pid":901,"pgid":901,"ownership_verified":True}
    result=runner._stop_owned_process(Child(), member, 1)
    assert calls == ["child"]
    assert result["verified"] is result["clean"] is False


def test_pre_replacement_failure_releases_only_pending_guard_lock_and_saves_preacquire_bundle(tmp_path, monkeypatch):
    import step07_run005_runtime_guard as guard_module
    worktree = tmp_path / "runtime"; worktree.mkdir()
    guard = worktree / "guard.json"; lock = guard.with_suffix(".json.lock")
    seed = {"state": runner.PENDING, "capacity": 1, "acquisition_count": 0,
            "runtime_authorization": "NOT_GRANTED"}
    raw = json.dumps(seed, sort_keys=True, separators=(",", ":")).encode(); guard.write_bytes(raw)
    replace = guard_module.os.replace
    def fail_before_guard_replace(source, target):
        if Path(target) == guard: raise OSError("BEFORE_REPLACE")
        replace(source, target)
    monkeypatch.setattr(guard_module.os, "replace", fail_before_guard_replace)
    monkeypatch.setattr(runner, "prepare_ros_environment", lambda *_: {})
    monkeypatch.setattr(runner, "host_preflight", lambda *_: {})
    directory = tmp_path / "evidence"
    _, _, consumed, failure = runner.preacquire_preflight(
        worktree, {}, directory, runner.PARTITION, tmp_path / "map", tmp_path / "fuel", {},
        guard, lock, seed, {}, "a" * 40, runner.INTEGRATION_BASE,
        Path(runner.RUNTIME_PYTHON_PATH), {"call_counts": {"runner": 1}})
    assert consumed is None and failure["guard_acquired"] is False
    assert failure["guard_state_after"] == runner.PENDING and failure["guard_acquisition_count"] == 0
    assert guard.read_bytes() == raw and not lock.exists()
    assert failure["runtime_execution"] is False
    assert failure["call_counts"] == {"runner":1,"bootstrap":0,"composite":0,"cpp_observer":0,"gate_b_observer":0}
    _assert_real_bundle(directory)


@pytest.mark.parametrize("fault", ["after_replace", "unmask"])
def test_simulated_main_never_returns_without_consumed_terminal_bundle_after_handoff_error(tmp_path, monkeypatch, fault):
    from types import SimpleNamespace
    source = tmp_path / "source"; source.mkdir()
    seed_path = source / "guard.json"; seed_path.write_bytes((ROOT / RUN005_GUARD_REL).read_bytes())
    source_bytes = seed_path.read_bytes()
    runtime = tmp_path / "runtime"; evidence = tmp_path / "evidence"
    args = SimpleNamespace(repository_root=source, guard_path=seed_path,
        expected_review_commit="a" * 40, expected_integration_base=runner.INTEGRATION_BASE,
        run_id=runner.RUN_ID, gz_partition=runner.PARTITION,
        owner_authorization="TEST_ONLY_EXACT_AUTH", owner_authorization_scope=runner.AUTH_SCOPE,
        owner_authorization_run_id=runner.RUN_ID, owner_authorization_review_commit="a" * 40,
        owner_authorization_integration_base=runner.INTEGRATION_BASE,
        runtime_worktree=runtime, run_directory=evidence, canonical_map_root=source / "map",
        fuel_cache_root=tmp_path / "fuel", runtime_python=Path(runner.RUNTIME_PYTHON_PATH))
    monkeypatch.setattr(runner, "_parse", lambda: args)
    def git_read(command, **_kwargs):
        assert command[0] == "git"
        if command[1:4] == ["remote", "get-url", "origin"]: text = runner.EXPECTED_ORIGIN
        elif command[1:3] == ["rev-parse", "HEAD"]: text = "a" * 40
        else: text = ""
        return SimpleNamespace(stdout=text, returncode=0)
    monkeypatch.setattr(runner, "_run", git_read)
    def private_clone(*_args):
        runtime.mkdir(); (runtime / "guard.json").write_bytes(source_bytes)
    monkeypatch.setattr(runner, "create_isolated_runtime_checkout", private_clone)
    monkeypatch.setattr(runner, "prepare_ros_environment", lambda *_: {})
    monkeypatch.setattr(runner, "host_preflight", lambda *_: {})
    monkeypatch.setattr(runner, "_spawn_owned_process", lambda *_a, **_k: pytest.fail("no component may spawn"))
    original_replace = runner.os.replace
    def replace(source_file, target):
        original_replace(source_file, target)
        if fault == "after_replace" and Path(target) == runtime / "guard.json": raise OSError("AFTER_REPLACE")
    monkeypatch.setattr(runner.os, "replace", replace)
    def masks(how, _mask):
        if fault == "unmask" and how == runner.signal.SIG_SETMASK: raise OSError("UNMASK_FAILED")
        return set()
    monkeypatch.setattr(runner.signal, "pthread_sigmask", masks)
    previous = runner.signal.getsignal(runner.signal.SIGTERM)
    assert runner.main() == 2
    assert runner.signal.getsignal(runner.signal.SIGTERM) == previous
    consumed = runner.load_guard(runtime / "guard.json")
    assert consumed["state"] == "CONSUMED" and consumed["acquisition_count"] == 1
    assert (runtime / "guard.json.lock").exists() and seed_path.read_bytes() == source_bytes
    record = runner.load_canonical_json(evidence / "run_record.json")
    assert record["guard_acquired"] is True and record["guard_acquisition_count"] == 1
    assert record["terminal_outcome"].endswith("FAIL_NO_RETRY_GUARD_CONSUMED")
    assert record["runtime_execution"] is False and record["call_counts"] == {
        "runner":1,"bootstrap":0,"composite":0,"cpp_observer":0,"gate_b_observer":0}
    assert record["teardown"]["completed"] is True
    _assert_real_bundle(evidence)


def test_pre_rearm_requires_ros_active_three_for_all_managed_nodes(monkeypatch):
    from types import SimpleNamespace
    calls = []
    def run(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=0, stdout="active [3]\n")
    monkeypatch.setattr(runner, "_run", run)
    states = runner.active_lifecycle_states({})
    assert states == {node: 3 for node in runner.COMPOSITE_LIFECYCLE_NODES}
    assert len(calls) == 7
    for invalid in ("active [2]", "inactive [2]", "active [3]\nerror", ""):
        monkeypatch.setattr(runner, "_run", lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout=invalid))
        assert runner.active_lifecycle_states({}) is None


def test_composite_readiness_checks_actual_data_before_exact_single_rearm(monkeypatch, tmp_path):
    from types import SimpleNamespace
    topics = ["/clock", "/scan", "/odometry/filtered", "/tf", "/tf_static"]
    nodes = ["/robot_state_publisher", "/ekf_filter_node", *runner.COMPOSITE_LIFECYCLE_NODES,
             "/safety_supervisor", "/final_twist_publisher"]
    services = ["/mecanum/safety/rearm", "/mecanum/safety/request_reset"]
    calls=[]
    def run(command, **kwargs):
        calls.append(command)
        if command[1:3] == ["topic", "list"]: output="\n".join(topics)
        elif command[1:3] == ["node", "list"]: output="\n".join(nodes)
        elif command[1:3] == ["service", "list"]: output="\n".join(services)
        elif command[1:3] == ["lifecycle", "get"]: output="active [3]"
        else:
            assert command[0] == runner.RUNTIME_PYTHON_PATH
            output="COMPOSITE_DATA_READY"
        return SimpleNamespace(returncode=0, stdout=output)
    monkeypatch.setattr(runner,"_run",run)
    result=runner._wait_ready({},tmp_path,SimpleNamespace(poll=lambda: None))
    assert result["ready"] and result["data_readiness"] == "COMPOSITE_DATA_READY"
    assert not any(command[1:3] == ["service", "call"] for command in calls)
    source=RUNNER_PATH.read_text()
    assert source.index('composite_member["readiness"] = _wait_ready') < source.index('"/mecanum/safety/rearm", "std_srvs/srv/Trigger"')
    assert source.count('"/mecanum/safety/rearm", "std_srvs/srv/Trigger"') == 1
    assert 'duration_sec:=30' in source and 'duration_sec:=1800' not in source
    assert '"--peer-evidence-path", str(observer_path)' in source
