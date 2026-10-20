#!/usr/bin/env python3
"""Single-use owner-authorized Step-7 NAV2_BASELINE Run005 campaign supervisor.

This file is source/offline machinery only. It never runs as part of build or
test. A future exact-run Owner prompt must supply the authorization fields.
"""
from __future__ import annotations

import argparse
import errno
import hashlib
import json
import os
from pathlib import Path
import signal
import stat
import subprocess
import sys
import tempfile
import time
import traceback
import uuid

from step07_run005_runtime_guard import (
    ARCHITECTURE_SHA256, AUTH_SCOPE, INTEGRATION_BASE, PARTITION, PENDING, RUN_ID,
    RUNTIME_PYTHON_PATH, acquire_guard, load_guard, validate_owner_authorization,
    validate_seed, validate_source_pins,
)

MAP_ROOT_REL = "artifacts/maps/warehouse_map2"
MAP_HASHES = {
    "map.yaml": "5073762401784f67e856b5018656ad869ecc26e723f85e5979054eadc7876a68",
    "map.pgm": "32f8a3eb626ebddecc15843748de0db8c6f7adc1b45a5edc1b1b1886407aef55",
    "metadata.yaml": "45450a2d62b38560200d11fef6ece8505eef5a3e3d73e27f7b091de022e793c1",
    "map_manifest.json": "7e0a380b0d8df32f9a4fc30dd0dbbe9ed08aafdcd5efb3764bccd844b98c1cb1",
}
WORLD_REL = "ros2_ws/src/ROBOT_URDF_final_description/launch/tugbot_depot.sdf"
WORLD_SHA256 = "a4b6253340baa866d89640d62a94d04fbea51425e9af1deca591422a0a36d91d"
CONFIG_REL = "ros2_ws/src/mecanum_nav_rl/config/v3/resolved/sim_eval_nav2_baseline.resolved.json"
CONFIG_SHA256 = "3841d1a1c2e9e1a4883431f05d7d5ff13e0b687569e5734f0b4f91aa69294b84"
PYDANTIC_VERSION = "2.10.6"
EXPECTED_ORIGIN = "https://github.com/hazandz/mecanum_autonomy_ws.git"

RUNTIME_PYTHON_PROBE = r'''import importlib, json, platform, sys
facts = {"python_version": platform.python_version(), "python_major": sys.version_info.major,
         "python_minor": sys.version_info.minor, "errors": []}
try:
    import pydantic
    facts["pydantic_version"] = pydantic.__version__
except Exception as exc:
    facts["errors"].append("PYDANTIC_IMPORT:" + type(exc).__name__)
try:
    import rclpy
    facts["rclpy_module"] = rclpy.__file__
except Exception as exc:
    facts["errors"].append("RCLPY_IMPORT:" + type(exc).__name__)
try:
    module = importlib.import_module("mecanum_nav_rl.observations.step07_gate_b_observer_node")
    facts["observer_module_path"] = module.__file__
except Exception as exc:
    facts["errors"].append("OBSERVER_IMPORT:" + type(exc).__name__)
print(json.dumps(facts, sort_keys=True, separators=(",", ":")))
'''


def validate_runtime_python_environment(runtime_python: Path, env: dict[str, str],
                                         overlay_prefix: Path) -> dict:
    """Validate the exact Owner-selected Python without a bare-python fallback."""
    invalid = "RUNTIME_PYTHON_ENVIRONMENT_INVALID:"
    if not runtime_python.is_absolute() or str(runtime_python) != RUNTIME_PYTHON_PATH:
        raise RuntimeError(invalid + "INTERPRETER_PATH_MISMATCH")
    if not runtime_python.is_file() or not os.access(runtime_python, os.X_OK):
        raise RuntimeError(invalid + "INTERPRETER_MISSING_OR_NOT_EXECUTABLE")
    try:
        probe = _run([str(runtime_python), "-c", RUNTIME_PYTHON_PROBE], env=env, check=False)
    except OSError as error:
        raise RuntimeError(invalid + "INTERPRETER_EXECUTION_FAILED") from error
    try:
        facts = json.loads(probe.stdout)
    except (json.JSONDecodeError, TypeError) as error:
        raise RuntimeError(invalid + "INTERPRETER_PROBE_INVALID") from error
    if probe.returncode != 0:
        raise RuntimeError(invalid + "INTERPRETER_PROBE_FAILED")
    if (facts.get("python_major"), facts.get("python_minor")) != (3, 12):
        raise RuntimeError(invalid + "PYTHON_VERSION_MISMATCH")
    errors = facts.get("errors", [])
    if any(item.startswith("PYDANTIC_IMPORT:") for item in errors):
        raise RuntimeError(invalid + "PYDANTIC_IMPORT_FAILED")
    if facts.get("pydantic_version") != PYDANTIC_VERSION:
        raise RuntimeError(invalid + "PYDANTIC_VERSION_MISMATCH")
    if any(item.startswith("RCLPY_IMPORT:") for item in errors):
        raise RuntimeError(invalid + "RCLPY_IMPORT_FAILED")
    if any(item.startswith("OBSERVER_IMPORT:") for item in errors):
        raise RuntimeError(invalid + "GATE_B_OBSERVER_IMPORT_FAILED")
    try:
        module_path = Path(facts.get("observer_module_path", "")).resolve(strict=True)
        prefix = overlay_prefix.resolve(strict=True)
        module_path.relative_to(prefix)
    except (OSError, RuntimeError, ValueError) as error:
        raise RuntimeError(invalid + "GATE_B_OBSERVER_OUTSIDE_INSTALL_OVERLAY") from error
    facts["observer_module_path"] = str(module_path)
    facts["install_overlay_prefix"] = str(prefix)
    return facts


def validate_runtime_output_targets(runtime_worktree: Path, run_directory: Path) -> None:
    """Prove both new output targets have distinct, writable real parents."""
    targets = (
        ("runtime_worktree", Path(runtime_worktree)),
        ("run_directory", Path(run_directory)),
    )
    normalized: dict[str, Path] = {}
    for label, target in targets:
        if not target.is_absolute():
            raise RuntimeError(f"RUNTIME_OUTPUT_PARENT_INVALID:{label}")
        target = Path(os.path.abspath(target))
        normalized[label] = target
        try:
            target.lstat()
        except FileNotFoundError:
            pass
        except OSError as error:
            if error.errno in (errno.EACCES, errno.EPERM, errno.EROFS):
                raise RuntimeError(f"RUNTIME_OUTPUT_PARENT_NOT_WRITABLE:{label}") from error
            raise RuntimeError(f"RUNTIME_OUTPUT_PARENT_INVALID:{label}") from error
        else:
            raise RuntimeError(f"RUNTIME_OUTPUT_PARENT_INVALID:{label}")

        parent = target.parent
        try:
            parent_info = parent.lstat()
        except OSError as error:
            if error.errno in (errno.EACCES, errno.EPERM, errno.EROFS):
                raise RuntimeError(f"RUNTIME_OUTPUT_PARENT_NOT_WRITABLE:{label}") from error
            raise RuntimeError(f"RUNTIME_OUTPUT_PARENT_INVALID:{label}") from error
        if parent.is_symlink() or not stat.S_ISDIR(parent_info.st_mode):
            raise RuntimeError(f"RUNTIME_OUTPUT_PARENT_INVALID:{label}")

    runtime_target = normalized["runtime_worktree"]
    evidence_target = normalized["run_directory"]
    if (runtime_target == evidence_target
            or runtime_target in evidence_target.parents
            or evidence_target in runtime_target.parents):
        raise RuntimeError("RUNTIME_OUTPUT_PARENT_INVALID:runtime_worktree")

    for label, _target in targets:
        parent = normalized[label].parent
        sentinel = parent / f".step07-output-probe-{os.getpid()}-{uuid.uuid4().hex}"
        descriptor = None
        created = False
        try:
            descriptor = os.open(
                sentinel, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600
            )
            created = True
            marker = b"step07-output-parent-writable\n"
            offset = 0
            while offset < len(marker):
                count = os.write(descriptor, marker[offset:])
                if count <= 0:
                    raise OSError(errno.EIO, "output-parent probe write made no progress")
                offset += count
            os.fsync(descriptor)
            os.close(descriptor)
            descriptor = None
            os.unlink(sentinel)
            created = False
        except OSError as error:
            if descriptor is not None:
                try:
                    os.close(descriptor)
                except OSError:
                    pass
            if created:
                try:
                    os.unlink(sentinel)
                except OSError:
                    pass
            raise RuntimeError(f"RUNTIME_OUTPUT_PARENT_NOT_WRITABLE:{label}") from error


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run(args, *, cwd=None, env=None, timeout=30, check=True, capture=True):
    result = subprocess.run(args, cwd=cwd, env=env, timeout=timeout, check=False,
                            text=True, stdout=subprocess.PIPE if capture else None,
                            stderr=subprocess.STDOUT if capture else None)
    if check and result.returncode != 0:
        raise RuntimeError(f"COMMAND_FAILED:{args[0]}:{result.returncode}:{result.stdout or ''}")
    return result


def create_isolated_runtime_checkout(source: Path, destination: Path,
                                     expected_head: str) -> Path:
    """Copy the exact local source commit into a repository with private Git metadata.

    The source is read-only input.  In particular, this must not use linked
    worktree operations, because those write administrative state into the
    source repository's common Git directory.
    """
    source = Path(source).resolve(strict=True)
    destination = Path(destination)
    if not destination.is_absolute():
        raise RuntimeError("RUNTIME_CHECKOUT_PATH_NOT_ABSOLUTE")
    if destination.resolve(strict=False) == source or source in destination.resolve(strict=False).parents:
        raise RuntimeError("RUNTIME_CHECKOUT_PATH_INSIDE_SOURCE_REPOSITORY")
    if destination.exists() or destination.is_symlink():
        raise RuntimeError("RUNTIME_CHECKOUT_PATH_ALREADY_EXISTS")
    if not destination.parent.is_dir():
        raise RuntimeError("RUNTIME_CHECKOUT_PARENT_MISSING")
    if len(expected_head) != 40 or any(c not in "0123456789abcdef" for c in expected_head):
        raise RuntimeError("RUNTIME_CHECKOUT_EXPECTED_COMMIT_INVALID")

    source_origin = _run(["git", "remote", "get-url", "origin"], cwd=source).stdout.strip()
    source_head = _run(["git", "rev-parse", "HEAD"], cwd=source).stdout.strip()
    source_status = _run(["git", "status", "--porcelain", "--untracked-files=all"], cwd=source).stdout
    if source_origin != EXPECTED_ORIGIN or source_head != expected_head or source_status.strip():
        raise RuntimeError("SOURCE_REPOSITORY_IDENTITY_CHANGED_DURING_RUNTIME_CHECKOUT_CREATION")

    _run([
        "git", "clone", "--no-hardlinks", "--no-checkout", "--origin", "origin",
        "--", str(source), str(destination),
    ], cwd=source)
    _run(["git", "checkout", "--detach", expected_head], cwd=destination)
    _run(["git", "remote", "set-url", "origin", source_origin], cwd=destination)

    git_metadata = destination / ".git"
    if not git_metadata.is_dir() or git_metadata.is_symlink():
        raise RuntimeError("RUNTIME_CHECKOUT_GIT_METADATA_NOT_PRIVATE")
    common_dir = Path(_run(["git", "rev-parse", "--git-common-dir"], cwd=destination).stdout.strip())
    if not common_dir.is_absolute():
        common_dir = (destination / common_dir).resolve(strict=True)
    if common_dir != git_metadata.resolve(strict=True):
        raise RuntimeError("RUNTIME_CHECKOUT_GIT_METADATA_NOT_PRIVATE")
    alternates = git_metadata / "objects" / "info" / "alternates"
    if alternates.exists() and alternates.read_text(encoding="utf-8").strip():
        raise RuntimeError("RUNTIME_CHECKOUT_USES_SHARED_OBJECT_ALTERNATES")

    runtime_head = _run(["git", "rev-parse", "HEAD"], cwd=destination).stdout.strip()
    runtime_status = _run(
        ["git", "status", "--porcelain", "--untracked-files=all"], cwd=destination
    ).stdout.strip()
    runtime_origin = _run(["git", "remote", "get-url", "origin"], cwd=destination).stdout.strip()
    symbolic_head = _run(["git", "symbolic-ref", "-q", "HEAD"], cwd=destination, check=False)
    if runtime_head != expected_head or runtime_status or runtime_origin != EXPECTED_ORIGIN or symbolic_head.returncode == 0:
        raise RuntimeError("RUNTIME_CHECKOUT_NOT_EXACT_CLEAN_DETACHED")

    if (_run(["git", "rev-parse", "HEAD"], cwd=source).stdout.strip() != source_head
            or _run(["git", "status", "--porcelain", "--untracked-files=all"], cwd=source).stdout != source_status
            or _run(["git", "remote", "get-url", "origin"], cwd=source).stdout.strip() != source_origin):
        raise RuntimeError("SOURCE_REPOSITORY_CHANGED_DURING_RUNTIME_CHECKOUT_CREATION")
    return destination


def validate_map_root(root: Path) -> Path:
    if not root.is_absolute() or not root.is_dir():
        raise RuntimeError("CANONICAL_MAP_ROOT_INVALID")
    root = root.resolve(strict=True)
    for name, digest in MAP_HASHES.items():
        path = root / name
        if not path.is_file() or sha256(path) != digest:
            raise RuntimeError(f"CANONICAL_MAP_HASH_MISMATCH:{name}")
    return root


BASE_REQUIRED_PACKAGE_PREFIXES = (
    "ros_gz_sim",
    "ros_gz_bridge",
    "mecanum_base_bridge",
    "mecanum_nav_bringup",
    "ROBOT_URDF_final_description",
    "robot_localization",
    "step07_nav2_baseline_runtime_observer",
    "mecanum_nav_rl",
)

NAV2_NODE_EXECUTABLES = (
    ("nav2_map_server", "map_server"),
    ("nav2_amcl", "amcl"),
    ("nav2_planner", "planner_server"),
    ("nav2_controller", "controller_server"),
    ("nav2_behaviors", "behavior_server"),
    ("nav2_bt_navigator", "bt_navigator"),
    ("nav2_lifecycle_manager", "lifecycle_manager"),
)
NAV2_PLUGIN_PROVIDER_PACKAGES = (
    "nav2_costmap_2d",
    "nav2_navfn_planner",
    "nav2_dwb_controller",
    "nav2_behavior_tree",
)
NAV2_RUNTIME_PACKAGES = tuple(dict.fromkeys(
    tuple(package for package, _executable in NAV2_NODE_EXECUTABLES)
    + NAV2_PLUGIN_PROVIDER_PACKAGES
))
REQUIRED_PACKAGE_PREFIXES = tuple(dict.fromkeys(
    BASE_REQUIRED_PACKAGE_PREFIXES + NAV2_RUNTIME_PACKAGES
))

INSTALLED_FILE_ARTIFACTS = (
    ("mecanum_nav_bringup", "launch/sim_eval_nav2_baseline_system.launch.py", "ros2_ws/src/mecanum_nav_bringup/launch/sim_eval_nav2_baseline_system.launch.py"),
    ("ROBOT_URDF_final_description", "launch/sim_eval_nav2_baseline_bootstrap.launch.py", "ros2_ws/src/ROBOT_URDF_final_description/launch/sim_eval_nav2_baseline_bootstrap.launch.py"),
    ("ROBOT_URDF_final_description", "launch/tugbot_depot.sdf", WORLD_REL),
    ("mecanum_nav_bringup", "config/navigation/sim_eval_nav2_baseline.runtime.yaml", "ros2_ws/src/mecanum_nav_bringup/config/navigation/sim_eval_nav2_baseline.runtime.yaml"),
    ("mecanum_nav_bringup", "config/bridge/sim_eval_cmd_vel.runtime.yaml", "ros2_ws/src/mecanum_nav_bringup/config/bridge/sim_eval_cmd_vel.runtime.yaml"),
    ("mecanum_nav_bringup", "config/lifecycle/sim_eval_nav2_baseline.runtime.yaml", "ros2_ws/src/mecanum_nav_bringup/config/lifecycle/sim_eval_nav2_baseline.runtime.yaml"),
    ("mecanum_nav_bringup", "launch/sim_eval_tf_ekf_state_estimation.launch.py", "ros2_ws/src/mecanum_nav_bringup/launch/sim_eval_tf_ekf_state_estimation.launch.py"),
    ("mecanum_nav_bringup", "config/bridge/sim_eval_lidar_scan_bridge.runtime.yaml", "ros2_ws/src/mecanum_nav_bringup/config/bridge/sim_eval_lidar_scan_bridge.runtime.yaml"),
    ("mecanum_nav_bringup", "config/localization/amcl_omni.yaml", "ros2_ws/src/mecanum_nav_bringup/config/localization/amcl_omni.yaml"),
    ("mecanum_nav_bringup", "config/bridge/sim_eval_clock.runtime.yaml", "ros2_ws/src/mecanum_nav_bringup/config/bridge/sim_eval_clock.runtime.yaml"),
    ("mecanum_nav_bringup", "config/state_estimation/ekf_sim.yaml", "ros2_ws/src/mecanum_nav_bringup/config/state_estimation/ekf_sim.yaml"),
    ("mecanum_base_bridge", "launch/sim_eval_wheel_imu_ingress.launch.py", "ros2_ws/src/mecanum_base_bridge/launch/sim_eval_wheel_imu_ingress.launch.py"),
    ("mecanum_base_bridge", "config/bridge/sim_eval_wheel_imu_ingress.runtime.yaml", "ros2_ws/src/mecanum_base_bridge/config/bridge/sim_eval_wheel_imu_ingress.runtime.yaml"),
    ("mecanum_nav_rl", "config/safety/sim_eval_nav2_baseline_safety.yaml", "ros2_ws/src/mecanum_nav_rl/config/safety/sim_eval_nav2_baseline_safety.yaml"),
    ("mecanum_nav_rl", "config/v3/resolved/sim_eval_nav2_baseline.resolved.json", CONFIG_REL),
)


def collect_package_prefixes(env: dict[str, str]) -> dict[str, str]:
    """Resolve package prefixes and report stable Nav2 closure failures."""
    prefixes = {}
    nav2_packages = set(NAV2_RUNTIME_PACKAGES)
    for package in REQUIRED_PACKAGE_PREFIXES:
        result = _run(["ros2", "pkg", "prefix", package], env=env,
                      check=package not in nav2_packages)
        prefix = result.stdout.strip()
        if package in nav2_packages and (getattr(result, "returncode", 0) != 0 or not prefix):
            raise RuntimeError(f"NAV2_PACKAGE_PREFIX_MISSING:{package}")
        if not prefix:
            raise RuntimeError(f"PACKAGE_PREFIX_EMPTY:{package}")
        prefixes[package] = prefix
    return prefixes


def validate_nav2_executables(prefixes: dict[str, str]) -> dict[str, str]:
    """Require installed Nav2 nodes before the capacity-one guard is acquired."""
    executables = {}
    for package, executable in NAV2_NODE_EXECUTABLES:
        path = Path(prefixes[package]) / "lib" / package / executable
        if not path.is_file() or not os.access(path, os.X_OK):
            raise RuntimeError(f"NAV2_EXECUTABLE_MISSING:{package}/{executable}")
        executables[f"{package}/{executable}"] = str(path)
    return executables


def validate_installed_file_package_closure(installed_files, prefixes: dict[str, str]) -> None:
    """Fail before byte comparisons if any artifact package lacks a collected prefix."""
    required = {package for package, _relative_install, _relative_source in installed_files}
    missing = sorted(required - set(prefixes))
    if missing:
        raise RuntimeError(f"INSTALLED_FILE_PACKAGE_PREFIX_MISSING:{missing[0]}")


FUEL_URI_MAPPING = {
    "https://fuel.gazebosim.org/1.0/OpenRobotics/models/Depot":
        ("openrobotics", "depot", "OpenRobotics", "Depot"),
    "https://fuel.gazebosim.org/1.0/MovAi/models/Tugbot":
        ("movai", "tugbot", "MovAi", "Tugbot"),
}


def validate_fuel_cache_layout(uris: list[str], cache_root: Path,
                               expected_root: Path) -> dict:
    import re
    if (not cache_root.is_absolute() or cache_root != expected_root
            or cache_root.is_symlink()):
        raise RuntimeError("FUEL_CACHE_ROOT_NOT_CANONICAL")
    root = expected_root.resolve(strict=True)
    if root != expected_root:
        raise RuntimeError("FUEL_CACHE_ROOT_NOT_CANONICAL")
    if len(uris) != 2 or set(uris) != set(FUEL_URI_MAPPING):
        raise RuntimeError("FUEL_URI_SET_MISMATCH")
    resolved = {}
    for uri, (owner, model, original_owner, original_model) in FUEL_URI_MAPPING.items():
        parent = root / "fuel.gazebosim.org" / owner / "models" / model
        uppercase_parent = root / "fuel.gazebosim.org" / original_owner / "models" / original_model
        if os.path.lexists(uppercase_parent):
            raise RuntimeError(f"FUEL_MODEL_PARENT_CASE_MISMATCH:{owner}/{model}")
        if not parent.exists() or not parent.is_dir():
            raise RuntimeError(f"FUEL_MODEL_PARENT_INVALID:{original_owner}/{original_model}")
        if not parent.resolve(strict=True).is_relative_to(root):
            raise RuntimeError("FUEL_CACHE_PATH_ESCAPES_ROOT")
        versions = []
        for child in parent.iterdir():
            if re.fullmatch(r"[0-9]+", child.name) and int(child.name) > 0 and child.is_dir():
                real = child.resolve(strict=True)
                if not real.is_relative_to(root):
                    raise RuntimeError("FUEL_CACHE_PATH_ESCAPES_ROOT")
                # Fuel's canonical model layout places these files directly in
                # the exact version directory; avoid ambiguous recursive search.
                config = real / "model.config"
                model_file = real / "model.sdf"
                if config.is_symlink() and not config.resolve(strict=True).is_relative_to(root):
                    raise RuntimeError("FUEL_CACHE_PATH_ESCAPES_ROOT")
                if model_file.is_symlink() and not model_file.resolve(strict=True).is_relative_to(root):
                    raise RuntimeError("FUEL_CACHE_PATH_ESCAPES_ROOT")
                if (config.is_file() and model_file.is_file()
                        and config.resolve(strict=True).is_relative_to(root)
                        and model_file.resolve(strict=True).is_relative_to(root)):
                    versions.append(real)
        if len(versions) != 1:
            raise RuntimeError("SIM_EVAL_FUEL_CACHE_VERSION_AMBIGUOUS_OR_MISSING")
        resolved[uri] = str(versions[0])
    return resolved


def validate_fuel_cache(world_path: Path, cache_root: Path) -> dict:
    import xml.etree.ElementTree as ET
    expected_root = Path.home() / ".gz" / "fuel"
    if not cache_root.is_absolute() or cache_root != expected_root:
        raise RuntimeError("FUEL_CACHE_ROOT_NOT_CANONICAL")
    if sha256(world_path) != WORLD_SHA256:
        raise RuntimeError("CANONICAL_WORLD_HASH_MISMATCH")
    sdf = ET.parse(world_path).getroot()
    uris = [node.text.strip() for node in sdf.iter("uri") if node.text and "fuel.gazebosim.org" in node.text]
    return validate_fuel_cache_layout(uris, cache_root, expected_root)


def stale_partition_processes(partition: str) -> list[str]:
    own_ancestry = {os.getpid()}
    parent = os.getppid()
    while parent > 1:
        own_ancestry.add(parent)
        try:
            parent = int(Path(f"/proc/{parent}/stat").read_text().split()[3])
        except (OSError, ValueError, IndexError):
            break
    matches = []
    for proc in Path("/proc").iterdir():
        if not proc.name.isdigit() or int(proc.name) in own_ancestry:
            continue
        try:
            command = (proc / "cmdline").read_bytes().replace(b"\0", b" ").decode("utf-8", "replace").strip()
        except OSError:
            continue
        if partition in command:
            matches.append(f"{proc.name}:{command}")
    return matches


def prepare_ros_environment(worktree: Path, dirs: dict[str, Path]) -> dict[str, str]:
    """Build and source Jazzy/overlay in one Bash process, returning its env."""
    script = r'''set -e -o pipefail
set +u
source /opt/ros/jazzy/setup.bash
colcon --log-base "$LOG_BASE" build --base-paths "$REPOSITORY/ros2_ws/src" --build-base "$BUILD_BASE" --install-base "$INSTALL_BASE" --packages-select step07_nav2_baseline_runtime_observer mecanum_nav_rl mecanum_nav_rl_interfaces mecanum_nav_bringup mecanum_base_bridge ROBOT_URDF_final_description
source "$INSTALL_BASE/setup.bash"
set -u
printf '\0ENV\0'
env -0
'''
    env = dict(os.environ)
    env.update({"REPOSITORY": str(worktree), "BUILD_BASE": str(dirs["build"]),
                "INSTALL_BASE": str(dirs["install"]), "LOG_BASE": str(dirs["log"]),
                "ROS_HOME": str(dirs["ros_home"]), "ROS_LOG_DIR": str(dirs["ros_log"])})
    result = _run(["bash", "-c", script], cwd=worktree, env=env, timeout=3600)
    marker = b"\0ENV\0"
    raw = result.stdout.encode()
    packed = raw[raw.index(marker) + len(marker):]
    sourced = {}
    for item in packed.split(b"\0"):
        if b"=" in item:
            key, value = item.split(b"=", 1)
            sourced[key.decode()] = value.decode(errors="surrogateescape")
    if not sourced.get("AMENT_PREFIX_PATH"):
        raise RuntimeError("ROS_OVERLAY_SOURCE_FAILED")
    return sourced


def host_preflight(env: dict[str, str], worktree: Path, run_directory: Path,
                   partition: str, map_root: Path, fuel_root: Path, source_pins: dict,
                   runtime_python: Path) -> dict:
    if run_directory.exists():
        raise RuntimeError("EVIDENCE_DIRECTORY_ALREADY_EXISTS")
    map_path = validate_map_root(map_root)
    fuel = validate_fuel_cache(worktree / WORLD_REL, fuel_root)
    validate_source_pins(worktree, source_pins)
    architecture = worktree / "docs/MECANUM_NAV_DRL_Architecture.docx"
    if sha256(architecture) != ARCHITECTURE_SHA256:
        raise RuntimeError("ARCHITECTURE_AUTHORITY_HASH_MISMATCH")
    config_doc = json.loads((worktree / CONFIG_REL).read_text(encoding="utf-8"))
    if config_doc.get("provenance", {}).get("config_hash") != "5b3bb2be3bc4d8ff5f9f1524b5ecd52f735c63622e3dd6ddd3e67aa9e6ce1071":
        raise RuntimeError("RESOLVED_CONFIG_HASH_MISMATCH")
    if not os.access("/dev/shm", os.W_OK):
        raise RuntimeError("DEV_SHM_NOT_WRITABLE")
    for program in ("ros2", "gz"):
        if not any((Path(part) / program).is_file() for part in env.get("PATH", "").split(os.pathsep)):
            raise RuntimeError(f"REQUIRED_EXECUTABLE_MISSING:{program}")
    prefixes = collect_package_prefixes(env)
    nav2_executables = validate_nav2_executables(prefixes)
    installed_files = INSTALLED_FILE_ARTIFACTS
    validate_installed_file_package_closure(installed_files, prefixes)
    observer = Path(prefixes["step07_nav2_baseline_runtime_observer"]) / "lib" / "step07_nav2_baseline_runtime_observer" / "step07_nav2_baseline_runtime_observer"
    if not observer.is_file() or not os.access(observer, os.X_OK):
        raise RuntimeError("CPP_OBSERVER_EXECUTABLE_NOT_INSTALLED")
    runtime_facts = validate_runtime_python_environment(
        runtime_python, env, Path(prefixes["mecanum_nav_rl"]))
    module_path = runtime_facts["observer_module_path"]
    installed_module = Path(module_path).resolve(strict=True)
    source_module = worktree / "ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/observations/step07_gate_b_observer_node.py"
    if installed_module.read_bytes() != source_module.read_bytes():
        raise RuntimeError("GATE_B_OBSERVER_INSTALLED_SOURCE_MISMATCH")
    gate_script = Path(prefixes["mecanum_nav_rl"]) / "lib" / "mecanum_nav_rl" / "step07_gate_b_observer"
    if not gate_script.is_file() or not os.access(gate_script, os.X_OK):
        raise RuntimeError("GATE_B_OBSERVER_CONSOLE_SCRIPT_NOT_INSTALLED")
    equality = {}
    for package, relative_install, relative_source in installed_files:
        installed = Path(prefixes[package]) / "share" / package / relative_install
        source_path = worktree / relative_source
        same = installed.is_file() and installed.read_bytes() == source_path.read_bytes()
        equality[relative_source] = same
        if not same:
            raise RuntimeError(f"INSTALLED_SOURCE_BYTES_MISMATCH:{relative_source}")
    _run([str(runtime_python), "-c", "from mecanum_nav_rl_interfaces.msg import FinalIssuedCommandReceipt, SafetyLifecycleState; print('ROSIDL_IMPORT_PASS')"], env=env)
    stale = stale_partition_processes(partition)
    if stale:
        raise RuntimeError("STALE_PARTITION_PROCESS_FOUND")
    return {"canonical_map_yaml": str(map_path / "map.yaml"), "fuel_cache": fuel,
            "package_prefixes": prefixes, "observer_executable": str(observer),
            "nav2_executables": nav2_executables,
            "gate_b_observer_console_script": str(gate_script),
            "runtime_python": str(runtime_python), "runtime_python_fingerprint": runtime_facts,
            "installed_source_byte_equality": equality, "rosidl_import": "PASS",
            "stale_processes": stale}


def _atomic_write(path: Path, document: dict):
    payload = json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.", delete=False) as handle:
        tmp = Path(handle.name); handle.write(payload); handle.flush(); os.fsync(handle.fileno())
    os.replace(tmp, path)


def load_canonical_json(path: Path) -> dict:
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raise ValueError("JSON_BOM_FORBIDDEN")
    if raw.endswith(b"\n"):
        raise ValueError("JSON_FINAL_NEWLINE_FORBIDDEN")
    document = json.loads(
        raw.decode("utf-8"),
        object_pairs_hook=lambda pairs: _unique_json_pairs(pairs),
        parse_constant=lambda value: (_ for _ in ()).throw(ValueError(f"JSON_NONFINITE_FORBIDDEN:{value}")),
    )
    if type(document) is not dict:
        raise ValueError("JSON_ROOT_NOT_OBJECT")
    canonical = json.dumps(document, ensure_ascii=False, sort_keys=True,
                           separators=(",", ":"), allow_nan=False).encode("utf-8")
    if raw != canonical:
        raise ValueError("JSON_NOT_CANONICAL")
    return document


def _unique_json_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"JSON_DUPLICATE_KEY:{key}")
        result[key] = value
    return result


def _process_group_members(pgid: int) -> dict:
    live, zombies = [], []
    for proc in Path("/proc").iterdir():
        if not proc.name.isdigit():
            continue
        try:
            stat = (proc / "stat").read_text().split()
            if int(stat[4]) == pgid:
                (zombies if stat[2] == "Z" else live).append(int(proc.name))
        except (OSError, ValueError, IndexError):
            continue
    return {"live_member_pids": sorted(live), "zombie_member_pids": sorted(zombies)}


def campaign_launch_commands(preflight: dict, *, partition: str, fuel_root: Path,
                             repository_root: Path) -> tuple[list[str], list[str]]:
    map_root = Path(preflight["canonical_map_yaml"]).parent
    fuel_root = fuel_root.resolve(strict=True)
    pose = ["initial_pose_map_x:=0.0", "initial_pose_map_y:=0.0", "initial_pose_map_yaw:=0.0"]
    bootstrap = ["ros2", "launch", "ROBOT_URDF_final_description",
                 "sim_eval_nav2_baseline_bootstrap.launch.py", f"gz_partition:={partition}",
                 f"fuel_cache_root:={fuel_root}", *pose]
    composite = ["ros2", "launch", "mecanum_nav_bringup",
                 "sim_eval_nav2_baseline_system.launch.py", "start_bootstrap:=false",
                 f"gz_partition:={partition}", f"canonical_map_root:={map_root}",
                 f"fuel_cache_root:={fuel_root}", *pose, "sim_estop_release_authorized:=true"]
    return bootstrap, composite


def validate_distinct_process_groups(bootstrap: dict | None, composite: dict | None) -> None:
    if type(bootstrap) is not dict or type(composite) is not dict:
        raise RuntimeError("CAMPAIGN_PROCESS_GROUP_MISSING")
    for member in (bootstrap, composite):
        pid, pgid = member.get("pid"), member.get("pgid")
        snapshot = member.get("initial_snapshot")
        if type(pid) is not int or pid <= 1 or type(pgid) is not int or pgid <= 1:
            raise RuntimeError("CAMPAIGN_PROCESS_GROUP_MISSING")
        if pid != pgid or type(snapshot) is not dict or pid not in snapshot.get("live_member_pids", []):
            raise RuntimeError("CAMPAIGN_PROCESS_GROUP_STALE_OR_INVALID")
    if bootstrap["pgid"] == composite["pgid"]:
        raise RuntimeError("CAMPAIGN_PROCESS_GROUPS_NOT_DISTINCT")


def _spawn_owned_process(command: list[str], *, name: str, cwd: Path, env: dict[str, str],
                         log_path: Path, processes: list[dict]) -> tuple[subprocess.Popen, dict]:
    with open(log_path, "wb") as log:
        proc = subprocess.Popen(command, cwd=cwd, env=env, stdout=log,
                                stderr=subprocess.STDOUT, start_new_session=True)
    try:
        pgid = os.getpgid(proc.pid)
    except ProcessLookupError:
        pgid = -1
    member = {"name": name, "pid": proc.pid, "pgid": pgid, "command": list(command),
              "returncode": None, "readiness": None, "initial_snapshot": _process_group_members(pgid) if pgid > 1 else {"live_member_pids": [], "zombie_member_pids": []},
              "final_snapshot": None}
    processes.append(member)
    return proc, member


def validate_started_process_group(proc: subprocess.Popen, member: dict) -> None:
    if (proc.poll() is not None or member.get("pid") != member.get("pgid")
            or member.get("pid") not in member.get("initial_snapshot", {}).get("live_member_pids", [])):
        raise RuntimeError(f"CAMPAIGN_PROCESS_GROUP_STALE_OR_INVALID:{member.get('name', 'unknown')}")


def _stop_owned_process(proc: subprocess.Popen | None, member: dict | None, timeout: float) -> dict:
    if proc is None or type(member) is not dict or type(member.get("pgid")) is not int or member["pgid"] <= 1:
        return {"signal": "SIGINT", "signal_sent": False, "leader_returncode": None,
                "live_member_pids": [], "zombie_member_pids": [], "clean": False}
    signal_sent = False
    try:
        os.killpg(member["pgid"], signal.SIGINT)
        signal_sent = True
    except ProcessLookupError:
        pass
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        pass
    snapshot = _process_group_members(member["pgid"])
    member["returncode"] = proc.returncode
    member["final_snapshot"] = snapshot
    clean = signal_sent and proc.returncode == 0 and not snapshot["live_member_pids"] and not snapshot["zombie_member_pids"]
    return {"signal": "SIGINT", "signal_sent": signal_sent, "leader_returncode": proc.returncode,
            **snapshot, "clean": clean}


def _wait_bootstrap_ready(env: dict[str, str], logdir: Path, process: subprocess.Popen) -> dict:
    deadline = time.monotonic() + 300
    required_topics = {"/clock", "/tf_static"}
    required_nodes = {"/robot_state_publisher"}
    topic_path, node_path = logdir / "bootstrap_topic_list.txt", logdir / "bootstrap_node_list.txt"
    log_path = logdir / "bootstrap.log"
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("BOOTSTRAP_EXITED_BEFORE_READINESS")
        topics = _run(["ros2", "topic", "list"], env=env, check=False, timeout=15)
        nodes = _run(["ros2", "node", "list"], env=env, check=False, timeout=15)
        topic_path.write_text(topics.stdout, encoding="utf-8")
        node_path.write_text(nodes.stdout, encoding="utf-8")
        bootstrap_log = log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else ""
        topic_names = set(topics.stdout.splitlines())
        node_names = {line.strip() if line.strip().startswith("/") else "/" + line.strip() for line in nodes.stdout.splitlines()}
        entity_ready = "Entity creation successful." in bootstrap_log
        if (topics.returncode == 0 and nodes.returncode == 0 and entity_ready
                and required_topics.issubset(topic_names) and required_nodes.issubset(node_names)):
            return {"ready": True, "entity_creation_literal": True, "topics": sorted(required_topics),
                    "nodes": sorted(required_nodes), "topic_transcript": topic_path.name,
                    "node_transcript": node_path.name}
        time.sleep(2)
    raise RuntimeError("BOOTSTRAP_READINESS_TIMEOUT")


def _write_artifact_manifest(run_directory: Path) -> None:
    entries = []
    for path in sorted(run_directory.rglob("*")):
        if not path.is_file() or path.name in {"artifact_manifest.json", "SHA256SUMS.txt"}:
            continue
        raw = path.read_bytes()
        entries.append({"path": path.relative_to(run_directory).as_posix(),
                        "sha256": hashlib.sha256(raw).hexdigest(), "size_bytes": len(raw)})
    manifest = {"schema_version": "1.0", "run_id": RUN_ID,
                "artifact_count": len(entries), "artifacts": entries}
    _atomic_write(run_directory / "artifact_manifest.json", manifest)
    sums = "".join(f"{item['sha256']}  {item['path']}\n" for item in entries)
    (run_directory / "SHA256SUMS.txt").write_text(sums, encoding="utf-8")


PREACQUIRE_TERMINAL = "STEP07_NAV2_BASELINE_RUN005_PREACQUIRE_PREFLIGHT_FAILED_NO_GUARD_CONSUMED"


def _write_preacquire_failure_evidence(run_directory: Path, record: dict,
                                       error: BaseException, *, guard_lock: Path) -> dict:
    """Persist auditable pre-acquire failure without implying runtime teardown."""
    if run_directory.exists():
        raise RuntimeError("EVIDENCE_DIRECTORY_ALREADY_EXISTS")
    if guard_lock.exists():
        raise RuntimeError("PREACQUIRE_FAILURE_GUARD_LOCK_PRESENT")
    failure_literal = (str(error) if str(error).startswith("RUNTIME_PYTHON_ENVIRONMENT_INVALID:")
                       else f"PREACQUIRE_FAILURE:{type(error).__name__}:{error}")
    failure = {
        "schema_version": "1.0", "run_id": RUN_ID,
        "review_commit": record.get("review_commit"),
        "integration_base": record.get("integration_base"),
        "partition": record.get("partition"),
        "guard_path": record.get("guard_path"),
        "guard_capacity": 1, "guard_acquisition_count": 0,
        "architecture_sha256": ARCHITECTURE_SHA256,
        "runner_invoked": True, "runtime_execution": False,
        "guard_acquired": False, "guard_state_before": PENDING,
        "guard_state_after": PENDING, "authorization_acquisition_count": 0,
        "failure_literal": failure_literal,
        "exception_type": type(error).__name__, "exception_message": str(error),
        "traceback": traceback.format_exc(), "teardown_applicable": False,
        "call_counts": {"runner": 1, "bootstrap": 0, "composite": 0,
                         "cpp_observer": 0, "gate_b_observer": 0},
        "terminal_outcome": PREACQUIRE_TERMINAL,
    }
    record.update({
        "runner_invoked": True, "runtime_execution": False,
        "guard_acquired": False, "guard_state_before": PENDING,
        "guard_state_after": PENDING, "authorization_acquisition_count": 0,
        "guard_capacity": 1, "guard_acquisition_count": 0,
        "preacquire_failure_literal": failure_literal,
        "exception_type": type(error).__name__, "exception_message": str(error),
        "traceback": failure["traceback"], "teardown_applicable": False,
        "call_counts": dict(failure["call_counts"]), "acceptance": {},
        "failure_reason_literals": [failure_literal],
        "terminal_outcome": PREACQUIRE_TERMINAL,
        "finalized_after_teardown": False,
    })
    run_directory.mkdir(parents=True, exist_ok=False)
    _atomic_write(run_directory / "preflight_failure.json", failure)
    _atomic_write(run_directory / "run_record.json", record)
    payload_entries = []
    for name in ("preflight_failure.json", "run_record.json"):
        raw = (run_directory / name).read_bytes()
        payload_entries.append({"path": name, "sha256": hashlib.sha256(raw).hexdigest(),
                                "size_bytes": len(raw)})
    manifest = {"schema_version": "1.0", "run_id": RUN_ID,
                "artifact_count": len(payload_entries), "artifacts": payload_entries}
    _atomic_write(run_directory / "artifact_manifest.json", manifest)
    sums_entries = list(payload_entries)
    manifest_raw = (run_directory / "artifact_manifest.json").read_bytes()
    sums_entries.append({"path": "artifact_manifest.json",
                         "sha256": hashlib.sha256(manifest_raw).hexdigest(),
                         "size_bytes": len(manifest_raw)})
    sums = "".join(f"{item['sha256']}  {item['path']}\n" for item in sorted(sums_entries, key=lambda item: item["path"]))
    (run_directory / "SHA256SUMS.txt").write_text(sums, encoding="utf-8")
    for name in ("preflight_failure.json", "run_record.json", "artifact_manifest.json"):
        load_canonical_json(run_directory / name)
    return record


def preacquire_preflight(worktree: Path, dirs: dict[str, Path], run_directory: Path,
                         partition: str, map_root: Path, fuel_root: Path,
                         source_pins: dict, runtime_guard: Path, guard_lock: Path,
                         guard: dict, authorization: dict, review_commit: str,
                         integration_base: str, runtime_python: Path, record: dict):
    """Build, host-check and acquire; on failure, save evidence without teardown."""
    try:
        env = prepare_ros_environment(worktree, dirs)
        preflight = host_preflight(env, worktree, run_directory, partition,
                                   map_root, fuel_root, source_pins, runtime_python)
        if guard_lock.exists():
            raise RuntimeError("GUARD_LOCK_ALREADY_EXISTS")
        consumed = acquire_guard(runtime_guard, guard, authorization,
                                 review_commit=review_commit,
                                 integration_base=integration_base)
        return env, preflight, consumed, None
    except BaseException as error:
        failure = _write_preacquire_failure_evidence(
            run_directory, record, error, guard_lock=guard_lock)
        return None, None, None, failure


def finalise_after_teardown(record: dict, runtime_acceptance: dict, teardown: dict) -> dict:
    """The only terminal verdict function; invoke only after all teardown ends."""
    if type(runtime_acceptance) is not dict or not runtime_acceptance or any(type(value) is not bool for value in runtime_acceptance.values()):
        raise ValueError("RUNTIME_ACCEPTANCE_MATRIX_INVALID")
    if teardown.get("completed") is not True:
        raise ValueError("TEARDOWN_NOT_COMPLETED_BEFORE_FINALIZATION")
    record["teardown"] = dict(teardown)
    teardown_ok = teardown.get("clean") is True and teardown.get("order_correct") is True
    record["acceptance"] = {**runtime_acceptance,
        "process_group_teardown_clean": teardown.get("clean") is True,
        "teardown_order_and_count_correct": teardown.get("order_correct") is True}
    passed = all(record["acceptance"].values())
    failures = [f"RUNTIME_ACCEPTANCE_FAILED:{key}" for key, value in runtime_acceptance.items() if not value]
    if not teardown.get("clean"):
        failures.append("PROCESS_GROUP_TEARDOWN_FAILED")
    if not teardown.get("order_correct"):
        failures.append("TEARDOWN_ORDER_OR_COUNT_FAILED")
    record["failure_reason_literals"] = failures
    record["terminal_outcome"] = ("STEP07_NAV2_BASELINE_RUN005_PASS_PENDING_INDEPENDENT_EVIDENCE_AUDIT"
                                  if passed else "STEP07_NAV2_BASELINE_RUN005_FAIL_NO_RETRY_GUARD_CONSUMED")
    record["finalized_after_teardown"] = True
    if passed != all(record["acceptance"].values()) or (passed and failures):
        raise ValueError("FINAL_RECORD_INTERNAL_INCONSISTENCY")
    return record


def _parse():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--runtime-worktree", type=Path, required=True)
    parser.add_argument("--run-directory", type=Path, required=True)
    parser.add_argument("--guard-path", type=Path, required=True)
    parser.add_argument("--expected-review-commit", required=True)
    parser.add_argument("--expected-integration-base", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--gz-partition", required=True)
    parser.add_argument("--canonical-map-root", type=Path, required=True)
    parser.add_argument("--fuel-cache-root", type=Path, required=True)
    parser.add_argument("--runtime-python", type=Path, required=True)
    parser.add_argument("--owner-authorization", required=True)
    parser.add_argument("--owner-authorization-scope", required=True)
    parser.add_argument("--owner-authorization-run-id", required=True)
    parser.add_argument("--owner-authorization-review-commit", required=True)
    parser.add_argument("--owner-authorization-integration-base", required=True)
    return parser.parse_args()


def main():
    args = _parse()
    source = args.repository_root.resolve(strict=True)
    try:
        args.guard_path.relative_to(source)
    except ValueError as error:
        raise SystemExit("GUARD_PATH_OUTSIDE_REPOSITORY") from error
    if args.expected_integration_base != INTEGRATION_BASE:
        raise SystemExit("INTEGRATION_BASE_MISMATCH")
    origin = _run(["git", "remote", "get-url", "origin"], cwd=source).stdout.strip()
    head = _run(["git", "rev-parse", "HEAD"], cwd=source).stdout.strip()
    if origin != EXPECTED_ORIGIN or head != args.expected_review_commit:
        raise SystemExit("SOURCE_REPOSITORY_IDENTITY_MISMATCH")
    if _run(["git", "status", "--porcelain"], cwd=source).stdout.strip():
        raise SystemExit("SOURCE_REPOSITORY_NOT_CLEAN")
    _run(["git", "cat-file", "-e", f"{INTEGRATION_BASE}^{{commit}}"], cwd=source)
    _run(["git", "merge-base", "--is-ancestor", INTEGRATION_BASE, head], cwd=source)
    guard = load_guard(args.guard_path)
    validate_seed(guard, run_id=args.run_id, review_commit=head,
                  integration_base=args.expected_integration_base,
                  architecture_sha256=ARCHITECTURE_SHA256, partition=args.gz_partition)
    authorization = validate_owner_authorization(
        authorization=args.owner_authorization, scope=args.owner_authorization_scope,
        run_id=args.owner_authorization_run_id, review_commit=args.owner_authorization_review_commit,
        integration_base=args.owner_authorization_integration_base, expected_run_id=args.run_id,
        expected_review_commit=head, expected_integration_base=args.expected_integration_base)
    try:
        validate_runtime_output_targets(args.runtime_worktree, args.run_directory)
    except RuntimeError as error:
        raise SystemExit(str(error)) from None
    dirs_root = Path(tempfile.mkdtemp(prefix="step07_nav2_run005_"))
    dirs = {name: dirs_root / name for name in ("build", "install", "log", "ros_home", "ros_log")}
    for path in dirs.values(): path.mkdir(parents=True, exist_ok=True)
    create_isolated_runtime_checkout(source, args.runtime_worktree, head)
    bootstrap_proc = composite_proc = cpp = gate = None
    bootstrap_member = composite_member = None
    bootstrap_calls = composite_calls = cpp_calls = gate_b_calls = 0
    record = {"schema_version": "1.0", "run_id": RUN_ID, "review_commit": head,
              "integration_base": args.expected_integration_base, "partition": PARTITION,
              "guard_path": str(args.guard_path), "guard_capacity": guard["capacity"],
              "guard_acquisition_count": guard["acquisition_count"],
              "run004_historical_disposition": {
                  "terminal_outcome": "STEP07_NAV2_BASELINE_RUN004_PREACQUIRE_PREFLIGHT_FAILED_NO_GUARD_CONSUMED",
                  "root_cause": "PACKAGE_PREFIX_CLOSURE_MISSING_ROBOT_URDF_FINAL_DESCRIPTION",
                  "retry_permitted": False,
              },
              **authorization, "config_hash": "5b3bb2be3bc4d8ff5f9f1524b5ecd52f735c63622e3dd6ddd3e67aa9e6ce1071",
              "map_root": str(args.canonical_map_root), "world_sha256": WORLD_SHA256,
              "runtime_python": str(args.runtime_python),
              "call_counts": {"runner": 1, "bootstrap": 0, "composite": 0, "cpp_observer": 0, "gate_b_observer": 0},
              "acceptance": {}, "failure_reason_literals": [], "guard_state_before": guard.get("state"),
              "guard_state_after": guard.get("state"), "guard_acquired": False,
              "runner_invoked": True, "runtime_execution": False,
              "teardown_applicable": False}
    processes = []
    runtime_acceptance = {}
    teardown = {"completed": False, "clean": False, "order_correct": False}
    runtime_guard = args.runtime_worktree / args.guard_path.relative_to(source)
    guard_lock = runtime_guard.with_suffix(runtime_guard.suffix + ".lock")
    env, preflight, consumed, preacquire_failure = preacquire_preflight(
        args.runtime_worktree, dirs, args.run_directory, args.gz_partition,
        args.canonical_map_root, args.fuel_cache_root, guard["source_pins"],
        runtime_guard, guard_lock, guard, authorization, head,
        args.expected_integration_base, args.runtime_python, record)
    if preacquire_failure is not None:
        return 2
    record["preflight"] = preflight
    record["guard_state_after_acquire"] = consumed["state"]
    record["guard_state_after"] = consumed["state"]
    record["guard_acquired"] = True
    record["guard_acquisition_count"] = consumed["acquisition_count"]
    record["authorization_acquisition_count"] = consumed["acquisition_count"]
    record["runtime_execution"] = True
    record["teardown_applicable"] = True
    runtime_acceptance.update({"guard_acquired_once": True, "canonical_map_and_fuel_preflight": True,
                               "runtime_graph_and_goal": False, "observer_acceptance": False,
                               "gate_b_vectors": False,
                               "bootstrap_composite_process_groups_distinct": False,
                               "bootstrap_readiness": False, "composite_readiness": False})
    args.run_directory.mkdir(parents=True, exist_ok=False)
    (args.run_directory / "authorization_state.txt").write_text(
        f"run_id={RUN_ID}\nscope={AUTH_SCOPE}\nreview_commit={head}\nintegration_base={args.expected_integration_base}\nauthorization_sha256={hashlib.sha256(authorization['owner_authorization'].encode()).hexdigest()}\n", encoding="utf-8")
    logdir = args.run_directory / "logs"; logdir.mkdir()
    bootstrap_command, composite_command = campaign_launch_commands(
        preflight, partition=PARTITION, fuel_root=args.fuel_cache_root,
        repository_root=args.runtime_worktree)
    record["process_groups"] = {}
    try:
        bootstrap_proc, bootstrap_member = _spawn_owned_process(
            bootstrap_command, name="bootstrap", cwd=args.runtime_worktree, env=env,
            log_path=logdir / "bootstrap.log", processes=processes)
        bootstrap_calls = 1
        record["call_counts"]["bootstrap"] = bootstrap_calls
        record["process_groups"]["bootstrap"] = bootstrap_member
        validate_started_process_group(bootstrap_proc, bootstrap_member)
        try:
            bootstrap_member["readiness"] = _wait_bootstrap_ready(env, logdir, bootstrap_proc)
        except BaseException as error:
            bootstrap_member["readiness"] = {"ready": False, "failure": f"{type(error).__name__}:{error}"}
            raise
        validate_started_process_group(bootstrap_proc, bootstrap_member)
        runtime_acceptance["bootstrap_readiness"] = True
        composite_proc, composite_member = _spawn_owned_process(
            composite_command, name="composite", cwd=args.runtime_worktree, env=env,
            log_path=logdir / "composite.log", processes=processes)
        composite_calls = 1
        record["call_counts"]["composite"] = composite_calls
        record["process_groups"]["composite"] = composite_member
        validate_started_process_group(composite_proc, composite_member)
        validate_started_process_group(bootstrap_proc, bootstrap_member)
        validate_distinct_process_groups(bootstrap_member, composite_member)
        runtime_acceptance["bootstrap_composite_process_groups_distinct"] = True
        try:
            composite_member["readiness"] = _wait_ready(env, logdir, composite_proc)
        except BaseException as error:
            composite_member["readiness"] = {"ready": False, "failure": f"{type(error).__name__}:{error}"}
            raise
        runtime_acceptance["composite_readiness"] = True
        response = _run(["ros2", "service", "call", "/mecanum/safety/rearm", "std_srvs/srv/Trigger", "{}"],
                        cwd=args.runtime_worktree, env=env, timeout=30)
        record["rearm_service_transcript"] = response.stdout
        if "success=true" not in response.stdout.replace(" ", "").lower():
            raise RuntimeError("SAFETY_LIFECYCLE_REARM_NOT_CONFIRMED")
        observer_path = args.run_directory / "runtime_observer.json"
        cpp_log = open(logdir / "cpp_observer.log", "wb")
        cpp = subprocess.Popen(["ros2", "run", "step07_nav2_baseline_runtime_observer",
                               "step07_nav2_baseline_runtime_observer", "--ros-args",
                               "-p", f"output_path:={observer_path}", "-p", f"config_hash:={record['config_hash']}",
                               "-p", "duration_sec:=1800"], cwd=args.runtime_worktree, env=env,
                              stdout=cpp_log, stderr=subprocess.STDOUT, start_new_session=True)
        cpp_member = {"name": "cpp_observer", "pid": cpp.pid, "pgid": os.getpgid(cpp.pid),
                      "command": ["ros2", "run", "step07_nav2_baseline_runtime_observer"],
                      "returncode": None, "readiness": {"started": True}, "final_snapshot": None}
        processes.append(cpp_member)
        cpp_calls = 1; record["call_counts"]["cpp_observer"] = 1
        gate_log = open(logdir / "gate_b_observer.log", "wb")
        gate_command = [str(args.runtime_python), "-m", "mecanum_nav_rl.observations.step07_gate_b_observer_node",
                              "--output", str(args.run_directory / "gate_b_vectors.json"),
                              "--config-hash", record["config_hash"], "--goal-x", "-4.0", "--goal-y", "0.0", "--goal-yaw", "0.0"]
        gate = subprocess.Popen(gate_command,
                             cwd=args.runtime_worktree, env=env, stdout=gate_log, stderr=subprocess.STDOUT,
                             start_new_session=True)
        gate_b_calls = 1; record["call_counts"]["gate_b_observer"] = 1
        gate_member = {"name": "gate_b_observer", "pid": gate.pid, "pgid": os.getpgid(gate.pid),
                       "command": gate_command,
                       "returncode": None, "readiness": {"started": True}, "final_snapshot": None}
        processes.append(gate_member)
        gate.wait(timeout=1800)
        if gate.returncode != 0:
            raise RuntimeError(f"GATE_B_OBSERVER_FAILED:{gate.returncode}")
        cpp.wait(timeout=1850)
        if cpp.returncode != 0:
            raise RuntimeError(f"CPP_OBSERVER_FAILED:{cpp.returncode}")
        from step07_gate_b_evidence_validator import load_json, validate_gate_b_document, validate_observer
        cpp_document, _ = load_json(observer_path)
        gate_document, _ = load_json(args.run_directory / "gate_b_vectors.json")
        validate_observer(cpp_document, config_hash=record["config_hash"])
        validate_gate_b_document(gate_document, config_hash=record["config_hash"])
        runtime_acceptance["observer_acceptance"] = bool(cpp_document.get("acceptance")) and all(cpp_document["acceptance"].values())
        runtime_acceptance["gate_b_vectors"] = bool(gate_document.get("acceptance")) and all(gate_document["acceptance"].values())
        runtime_acceptance["runtime_graph_and_goal"] = runtime_acceptance["gate_b_vectors"]
        if not runtime_acceptance["observer_acceptance"] or not runtime_acceptance["gate_b_vectors"]:
            raise RuntimeError("RAW_OBSERVER_ACCEPTANCE_FAILED")
        record["goal_result"] = gate_document["navigate_to_pose"]
    except BaseException as error:
        record["pre_teardown_failure"] = f"{type(error).__name__}:{error}"
        record["traceback"] = traceback.format_exc()
    finally:
        collector_members = {member["name"]: member for member in processes
                             if member["name"] in {"gate_b_observer", "cpp_observer"}}
        composite_teardown = _stop_owned_process(composite_proc, composite_member, timeout=30)
        teardown["composite"] = composite_teardown
        bootstrap_teardown = _stop_owned_process(bootstrap_proc, bootstrap_member, timeout=30)
        teardown["bootstrap"] = bootstrap_teardown
        teardown["order"] = ["composite", "bootstrap"]
        for name, proc in (("gate_b_observer", gate), ("cpp_observer", cpp)):
            if proc is not None and proc.poll() is None:
                try:
                    os.killpg(os.getpgid(proc.pid), signal.SIGINT)
                    proc.wait(timeout=20)
                except (ProcessLookupError, subprocess.TimeoutExpired):
                    teardown["clean"] = False
            if proc is not None:
                teardown.setdefault("collector_returncodes", {})[name] = proc.returncode
                member = collector_members.get(name)
                if member is not None:
                    member["returncode"] = proc.returncode
                    member["final_snapshot"] = _process_group_members(member["pgid"])
        teardown["clean"] = (composite_teardown["clean"] and bootstrap_teardown["clean"]
                              and all(value == 0 for value in teardown.get("collector_returncodes", {}).values()))
        teardown["order_correct"] = (teardown["order"] == ["composite", "bootstrap"]
                                     and composite_teardown["signal_sent"]
                                     and bootstrap_teardown["signal_sent"]
                                     and bootstrap_calls == 1
                                     and composite_calls == 1
                                     and bootstrap_member is not None
                                     and composite_member is not None
                                     and bootstrap_member.get("pid") != composite_member.get("pid")
                                     and bootstrap_member.get("pgid") != composite_member.get("pgid")
                                     and not composite_teardown["live_member_pids"]
                                     and not composite_teardown["zombie_member_pids"]
                                     and not bootstrap_teardown["live_member_pids"]
                                     and not bootstrap_teardown["zombie_member_pids"])
        group_snapshots = {member["name"]: member.get("final_snapshot") or _process_group_members(member["pgid"])
                           for member in processes}
        teardown["process_group_snapshots"] = group_snapshots
        all_live = sorted({pid for snapshot in group_snapshots.values() for pid in snapshot["live_member_pids"]})
        all_zombie = sorted({pid for snapshot in group_snapshots.values() for pid in snapshot["zombie_member_pids"]})
        teardown["live_member_pids"] = all_live
        teardown["zombie_member_pids"] = all_zombie
        teardown["clean"] = teardown["clean"] and not all_live and not all_zombie
        teardown["completed"] = True
        record["call_counts"].update({"bootstrap": bootstrap_calls, "composite": composite_calls,
                                        "cpp_observer": cpp_calls, "gate_b_observer": gate_b_calls})
        if runtime_acceptance:
            result = finalise_after_teardown(record, runtime_acceptance, teardown)
            _atomic_write(args.run_directory / "run_record.json", result)
            _write_artifact_manifest(args.run_directory)
        # Keep every guard, lock, log and evidence artifact after acquisition.
    return 0 if record.get("terminal_outcome", "").endswith("PASS_PENDING_INDEPENDENT_EVIDENCE_AUDIT") else 2


def _wait_ready(env, logdir, process):
    deadline = time.monotonic() + 300
    required = {"/clock", "/scan", "/odometry/filtered", "/tf", "/tf_static"}
    required_nodes = {"/robot_state_publisher", "/ekf_filter_node", "/map_server", "/amcl",
                      "/planner_server", "/controller_server", "/behavior_server",
                      "/bt_navigator", "/safety_lifecycle", "/safety_supervisor", "/final_twist_publisher"}
    required_services = {"/mecanum/safety/rearm", "/mecanum/safety/request_reset"}
    transcripts = {"topics": logdir / "topic_list.txt", "nodes": logdir / "node_list.txt",
                   "services": logdir / "service_list.txt"}
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("COMPOSITE_EXITED_BEFORE_READINESS")
        topic_result = _run(["ros2", "topic", "list"], env=env, check=False, timeout=15)
        node_result = _run(["ros2", "node", "list"], env=env, check=False, timeout=15)
        service_result = _run(["ros2", "service", "list"], env=env, check=False, timeout=15)
        transcripts["topics"].write_text(topic_result.stdout, encoding="utf-8")
        transcripts["nodes"].write_text(node_result.stdout, encoding="utf-8")
        transcripts["services"].write_text(service_result.stdout, encoding="utf-8")
        topics = set(topic_result.stdout.splitlines())
        nodes = {line.strip() if line.strip().startswith("/") else "/" + line.strip() for line in node_result.stdout.splitlines()}
        services = set(service_result.stdout.splitlines())
        if (topic_result.returncode == 0 and node_result.returncode == 0 and service_result.returncode == 0
                and required.issubset(topics) and required_nodes.issubset(nodes)
                and required_services.issubset(services)):
            return {"ready": True, "topics": sorted(required), "nodes": sorted(required_nodes),
                    "services": sorted(required_services),
                    "topic_transcript": transcripts["topics"].name,
                    "node_transcript": transcripts["nodes"].name,
                    "service_transcript": transcripts["services"].name}
        time.sleep(2)
    raise RuntimeError("COMPOSITE_READINESS_TIMEOUT")


if __name__ == "__main__":
    raise SystemExit(main())
