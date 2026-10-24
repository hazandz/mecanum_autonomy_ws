#!/usr/bin/env python3
"""Single-use owner-authorized Step-7 NAV2_BASELINE Run005 campaign supervisor.

This file is source/offline machinery only. It never runs as part of build or
test. A future exact-run Owner prompt must supply the authorization fields.
"""
from __future__ import annotations

import argparse
import errno
import fcntl
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import socket
import signal
import stat
import struct
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


def stale_partition_processes(partition: str, proc_root: Path = Path("/proc")) -> list[str]:
    """Return non-ancestry PIDs whose exact environment owns this partition."""
    own_ancestry = {os.getpid()}
    parent = os.getppid()
    while parent > 1:
        own_ancestry.add(parent)
        try:
            stat = (proc_root / str(parent) / "stat").read_text(encoding="ascii")
            # The comm field is parenthesized and may contain spaces. Fields
            # after its closing delimiter start with state, then ppid.
            close = stat.rfind(")")
            fields_after_comm = stat[close + 1 :].split()
            parent = int(fields_after_comm[1])
        except (OSError, ValueError, IndexError):
            break

    expected = b"GZ_PARTITION=" + partition.encode("utf-8")
    matches = []
    try:
        processes = list(proc_root.iterdir())
    except OSError:
        return matches
    for proc in processes:
        if not proc.name.isdigit():
            continue
        pid = int(proc.name)
        if pid in own_ancestry:
            continue
        try:
            environment = (proc / "environ").read_bytes()
        except OSError:
            # Unrelated processes can disappear or restrict proc access while
            # the scan is in progress; inaccessible metadata is not a match.
            continue
        if expected in environment.split(b"\0"):
            matches.append(pid)
    return [str(pid) for pid in sorted(matches)]


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
                   runtime_python: Path, record: dict | None = None) -> dict:
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
    qos_python_paths = {
        "ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/runtime_safety/safety_lifecycle_node.py": "mecanum_nav_rl.runtime_safety.safety_lifecycle_node",
        "ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/runtime_safety/final_twist_publisher_node.py": "mecanum_nav_rl.runtime_safety.final_twist_publisher_node",
    }
    qos_python_equality = {}
    for relative, module in qos_python_paths.items():
        source_path = worktree / relative
        installed_path = Path(_run([str(runtime_python), "-c",
            f"import {module} as m; print(m.__file__)"] , env=env).stdout.strip()).resolve(strict=True)
        same = source_path.read_bytes() == installed_path.read_bytes()
        qos_python_equality[relative] = same
        if not same:
            raise RuntimeError(f"QOS_PROFILE_INSTALLED_SOURCE_MISMATCH:{relative}")
    qos_pin_paths = {
        "ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/runtime_safety/safety_lifecycle_node.py",
        "ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/runtime_safety/final_twist_publisher_node.py",
        "ros2_ws/src/step07_nav2_baseline_runtime_observer/src/step07_nav2_baseline_runtime_observer.cpp",
    }
    if not qos_pin_paths.issubset(source_pins):
        raise RuntimeError("QOS_PROFILE_IMPLEMENTATION_SOURCE_PIN_MISSING")
    runtime_head = _run(["git", "rev-parse", "HEAD"], cwd=worktree).stdout.strip()
    runtime_origin = _run(["git", "remote", "get-url", "origin"], cwd=worktree).stdout.strip()
    if (record is not None and runtime_head != record.get("review_commit")) or runtime_origin != EXPECTED_ORIGIN:
        raise RuntimeError("QOS_PROFILE_IMPLEMENTATION_RUNTIME_IDENTITY_INVALID")
    qos_implementation_pin_evidence = {
        "schema_version": "1.0", "runtime_checkout_head": runtime_head,
        "runtime_checkout_origin": runtime_origin,
        "source_pins": {path: source_pins[path] for path in sorted(qos_pin_paths)},
        "installed_python_source_byte_equality": qos_python_equality,
        "installed_observer_binary": {"sha256": sha256(observer),
                                       "size_bytes": observer.stat().st_size,
                                       "source_sha256": source_pins["ros2_ws/src/step07_nav2_baseline_runtime_observer/src/step07_nav2_baseline_runtime_observer.cpp"]["sha256"],
                                       "source_size_bytes": source_pins["ros2_ws/src/step07_nav2_baseline_runtime_observer/src/step07_nav2_baseline_runtime_observer.cpp"]["size_bytes"]},
    }
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
    if record is None:
        transport_facts = validate_gz_transport_host_capability(env, partition)
    else:
        transport_facts = validate_gz_transport_host_capability(env, partition, record=record)
    ros_discovery_facts = validate_ros_discovery_host_capability(env)
    return {"canonical_map_yaml": str(map_path / "map.yaml"), "fuel_cache": fuel,
            "package_prefixes": prefixes, "observer_executable": str(observer),
            "nav2_executables": nav2_executables,
            "gate_b_observer_console_script": str(gate_script),
            "runtime_python": str(runtime_python), "runtime_python_fingerprint": runtime_facts,
            "installed_source_byte_equality": equality, "rosidl_import": "PASS",
            "qos_implementation_pin_evidence": qos_implementation_pin_evidence,
            "stale_processes": stale, "gz_transport_host_capability": transport_facts,
            "ros_discovery_host_capability": ros_discovery_facts}


def validate_gz_transport_host_capability(
    env: dict[str, str], partition: str, *, socket_factory=None,
    interface_address_lookup=None, command_runner=None, timeout: float = 15,
    proc_route_path: Path = Path("/proc/net/route"),
    sysfs_root: Path = Path("/sys"), record: dict | None = None,
) -> dict:
    """Resolve a physical default-route IPv4 without invoking external route tools."""
    command_runner = command_runner or _run
    facts: dict = {"partition": partition, "status": "PENDING"}

    def unavailable(reason: str, error: BaseException | None = None):
        facts.update({"partition": partition, "status": "FAIL", "failure_reason": reason})
        if record is not None:
            record["gz_transport_host_capability"] = facts
        failure = RuntimeError(f"GZ_TRANSPORT_HOST_CAPABILITY_UNAVAILABLE:{reason}")
        if error is not None:
            raise failure from error
        raise failure

    try:
        route_text = Path(proc_route_path).read_text(encoding="ascii")
    except (OSError, UnicodeError) as error:
        unavailable("PROC_NET_ROUTE_UNREADABLE", error)
    routes = []
    lines = route_text.splitlines()
    if not lines or lines[0].split()[:2] != ["Iface", "Destination"]:
        unavailable("PROC_NET_ROUTE_MALFORMED")
    for line in lines[1:]:
        fields = line.split()
        if not fields:
            continue
        if len(fields) < 11:
            unavailable("PROC_NET_ROUTE_MALFORMED")
        interface, destination, gateway, flags, _refcnt, _use, metric, mask = fields[:8]
        if (not interface or interface in {".", ".."}
                or not all(char.isalnum() or char in "_.:-" for char in interface)):
            unavailable("PROC_NET_ROUTE_MALFORMED")
        try:
            dest_ip = ipaddress.IPv4Address(struct.pack("<I", int(destination, 16)))
            mask_ip = ipaddress.IPv4Address(struct.pack("<I", int(mask, 16)))
            int(gateway, 16)
            route_flags = int(flags, 16)
            metric_value = int(metric, 10)
            if metric_value < 0:
                raise ValueError("negative metric")
        except (ValueError, struct.error) as error:
            unavailable("PROC_NET_ROUTE_MALFORMED", error)
        if dest_ip == ipaddress.IPv4Address("0.0.0.0") and mask_ip == ipaddress.IPv4Address("0.0.0.0"):
            if route_flags & 0x1 == 0:
                unavailable("DEFAULT_ROUTE_NOT_UP")
            routes.append((metric_value, interface))
    if not routes:
        unavailable("DEFAULT_ROUTE_MISSING")
    best_metric = min(metric for metric, _interface in routes)
    selected = [(metric, interface) for metric, interface in routes if metric == best_metric]
    if len(selected) != 1:
        unavailable("DEFAULT_ROUTE_AMBIGUOUS")
    _metric, interface = selected[0]

    root = Path(sysfs_root)
    net_entry = root / "class" / "net" / interface
    try:
        net_real = net_entry.resolve(strict=True)
        devices_root = (root / "devices").resolve(strict=True)
        net_real.relative_to(devices_root)
        flags = int((net_entry / "flags").read_text(encoding="ascii").strip(), 0)
        operstate = (net_entry / "operstate").read_text(encoding="ascii").strip().lower()
        device_target = (net_real / "device").resolve(strict=True)
        device_target.relative_to(devices_root)
    except (OSError, UnicodeError, ValueError) as error:
        unavailable("ROUTE_INTERFACE_SYSFS_INVALID", error)
    try:
        device_target.relative_to((devices_root / "virtual").resolve(strict=True))
    except ValueError:
        pass
    except OSError as error:
        unavailable("ROUTE_INTERFACE_SYSFS_INVALID", error)
    else:
        unavailable("ROUTE_INTERFACE_NOT_PHYSICAL")
    if flags & 0x1 == 0 or operstate != "up":
        unavailable("ROUTE_INTERFACE_DOWN")

    udp_factory = socket_factory or socket.socket
    address_lookup = interface_address_lookup or _interface_ipv4_addresses
    udp_socket = None
    try:
        udp_socket = udp_factory(socket.AF_INET, socket.SOCK_DGRAM)
        udp_socket.connect(("192.0.2.1", 9))
        source_text = udp_socket.getsockname()[0]
        selected_ip = ipaddress.IPv4Address(source_text)
        if not _is_usable_local_ipv4(selected_ip):
            unavailable("DEFAULT_ROUTE_SOURCE_INVALID")
        interface_addresses = {ipaddress.IPv4Address(value) for value in address_lookup(udp_socket, interface)}
        if selected_ip not in interface_addresses:
            unavailable("DEFAULT_ROUTE_SOURCE_NOT_ON_INTERFACE")
    except RuntimeError:
        raise
    except (OSError, ValueError, TypeError) as error:
        unavailable("UDP_SOURCE_RESOLUTION_FAILED", error)
    finally:
        if udp_socket is not None:
            try:
                udp_socket.close()
            except OSError:
                unavailable("UDP_SOCKET_CLOSE_FAILED")

    facts.update({"interface": interface, "ipv4": str(selected_ip), "partition": partition,
             "route_source": "PROC_NET_ROUTE_AND_UDP_CONNECT",
             "probe": {"command": "gz topic -t <unique> -m gz.msgs.StringMsg -p <probe>",
                       "status": "PENDING"}, "status": "PENDING"})
    if record is not None:
        record["gz_transport_host_capability"] = facts
    probe_env = dict(env)
    probe_env["GZ_PARTITION"] = partition
    probe_env["GZ_IP"] = str(selected_ip)
    topic = f"/step07/host_transport_probe/{uuid.uuid4().hex}"
    command = ["gz", "topic", "-t", topic, "-m", "gz.msgs.StringMsg",
               "-p", "data: 'step07_transport_probe'"]
    try:
        result = command_runner(command, env=probe_env, check=False, timeout=timeout)
    except subprocess.TimeoutExpired as error:
        facts["probe"] = {"status": "FAIL", "reason": "GZ_TOPIC_PUBLISH_TIMEOUT"}
        unavailable("GZ_TOPIC_PUBLISH_TIMEOUT", error)
    except PermissionError as error:
        facts["probe"] = {"status": "FAIL", "reason": "GZ_TOPIC_PUBLISH_PERMISSION_DENIED"}
        unavailable("GZ_TOPIC_PUBLISH_PERMISSION_DENIED", error)
    except OSError as error:
        facts["probe"] = {"status": "FAIL", "reason": "GZ_TOPIC_PUBLISH_OS_ERROR"}
        unavailable("GZ_TOPIC_PUBLISH_OS_ERROR", error)
    output = ((getattr(result, "stdout", "") or "") + "\n" +
              (getattr(result, "stderr", "") or ""))
    markers = ("getifaddrs:", "error creating socket:", "operation not permitted",
               "network is unreachable", "failed to create", "transport error")
    found = sorted(marker for marker in markers if marker in output.lower())
    facts["probe"] = {"status": "PASS" if getattr(result, "returncode", 1) == 0 and not found else "FAIL",
                       "returncode": getattr(result, "returncode", None),
                       "output_bytes": len(output.encode("utf-8", errors="replace")),
                       "output_sha256": hashlib.sha256(output.encode("utf-8", errors="replace")).hexdigest(),
                       "recognized_error_markers": found}
    if getattr(result, "returncode", 1) != 0:
        unavailable("GZ_TOPIC_PUBLISH_EXIT_NONZERO")
    if found:
        unavailable("GZ_TOPIC_PUBLISH_TRANSPORT_ERROR")
    env["GZ_PARTITION"] = partition
    env["GZ_IP"] = str(selected_ip)
    return facts


def _is_usable_local_ipv4(address: ipaddress.IPv4Address) -> bool:
    reserved_networks = (
        ipaddress.IPv4Network("0.0.0.0/8"),
        ipaddress.IPv4Network("192.0.0.0/24"),
        ipaddress.IPv4Network("192.0.2.0/24"),
        ipaddress.IPv4Network("198.18.0.0/15"),
        ipaddress.IPv4Network("198.51.100.0/24"),
        ipaddress.IPv4Network("203.0.113.0/24"),
        ipaddress.IPv4Network("240.0.0.0/4"),
    )
    return not (address.is_loopback or address.is_link_local or address.is_multicast
                or address.is_unspecified or address.is_reserved
                or any(address in network for network in reserved_networks))


def _interface_ipv4_addresses(sock, interface: str) -> tuple[str, ...]:
    """Read the interface's primary IPv4 address through Linux SIOCGIFADDR."""
    request = struct.pack("256s", interface.encode("ascii")[:15])
    response = fcntl.ioctl(sock.fileno(), 0x8915, request)  # SIOCGIFADDR
    return (socket.inet_ntoa(response[20:24]),)


ROS_DISCOVERY_ERROR_MARKERS = (
    "getifaddrs:", "error creating socket:", "operation not permitted",
    "permission denied", "failed to create participant", "failed to initialize",
    "network is unreachable", "cannot assign requested address",
)


def validate_ros_discovery_host_capability(
    env: dict[str, str], *, command_runner=None, timeout: float = 10,
) -> dict:
    """Probe ROS 2 discovery in the sourced overlay without starting a daemon."""
    command_runner = command_runner or _run
    support_command = ["ros2", "topic", "list", "--no-daemon", "--spin-time", "3", "--help"]
    probe_command = ["ros2", "topic", "list", "--no-daemon", "--spin-time", "3"]
    try:
        support = command_runner(support_command, env=env, check=False, timeout=timeout)
    except subprocess.TimeoutExpired as error:
        raise RuntimeError("ROS_DISCOVERY_HOST_CAPABILITY_UNAVAILABLE:CLI_SUPPORT_TIMEOUT") from error
    except (PermissionError, OSError) as error:
        raise RuntimeError("ROS_DISCOVERY_HOST_CAPABILITY_UNAVAILABLE:CLI_SUPPORT_ERROR") from error
    support_output = (getattr(support, "stdout", "") or "") + "\n" + (getattr(support, "stderr", "") or "")
    if getattr(support, "returncode", 1) != 0 or "--no-daemon" not in support_output or "--spin-time" not in support_output:
        raise RuntimeError("ROS_DISCOVERY_HOST_CAPABILITY_UNAVAILABLE:CLI_OPTIONS_UNSUPPORTED")
    try:
        result = command_runner(probe_command, env=env, check=False, timeout=timeout)
    except subprocess.TimeoutExpired as error:
        raise RuntimeError("ROS_DISCOVERY_HOST_CAPABILITY_UNAVAILABLE:PROBE_TIMEOUT") from error
    except PermissionError as error:
        raise RuntimeError("ROS_DISCOVERY_HOST_CAPABILITY_UNAVAILABLE:SOCKET_PERMISSION_DENIED") from error
    except OSError as error:
        raise RuntimeError("ROS_DISCOVERY_HOST_CAPABILITY_UNAVAILABLE:PROBE_OS_ERROR") from error
    output = (getattr(result, "stdout", "") or "") + "\n" + (getattr(result, "stderr", "") or "")
    lowered = output.lower()
    if any(marker in lowered for marker in ROS_DISCOVERY_ERROR_MARKERS):
        raise RuntimeError("ROS_DISCOVERY_HOST_CAPABILITY_UNAVAILABLE:NETWORK_ERROR_OUTPUT")
    if getattr(result, "returncode", 1) != 0:
        raise RuntimeError("ROS_DISCOVERY_HOST_CAPABILITY_UNAVAILABLE:PROBE_EXIT_NONZERO")
    return {"cli_options": "PASS", "probe": "PASS", "empty_graph_valid": True,
            "command": probe_command, "output_line_count": len((getattr(result, "stdout", "") or "").splitlines())}


class RunnerInterruptedBySignal(RuntimeError):
    """A catchable runner interruption that still enters campaign teardown."""


class SigtermHandler:
    """Track SIGTERM across guard acquisition, campaign, and finalization."""
    def __init__(self):
        self.interrupted = False
        self.guard_acquired = False
        self.campaign_active = False
        self.finalizing = False
        self.exception_raised = False
        self.handler_restored = False
        self.terminal_committed = False
        self.registration_depth = 0

    def __call__(self, signum, _frame):
        if signum != signal.SIGTERM:
            return
        if self.terminal_committed:
            return
        self.interrupted = True
        if self.registration_depth:
            return
        if not self.guard_acquired:
            self._raise_once()
        elif self.campaign_active and not self.finalizing:
            self._raise_once()

    def _raise_once(self):
        if not self.exception_raised:
            self.exception_raised = True
            raise RunnerInterruptedBySignal("RUNNER_INTERRUPTED_BY_SIGNAL:SIGTERM")

    def mark_guard_acquired(self):
        self.guard_acquired = True

    def begin_campaign(self):
        self.campaign_active = True
        if self.interrupted:
            self._raise_once()

    def begin_finalization(self):
        self.finalizing = True

    def restore(self, previous_handler):
        if not self.handler_restored:
            signal.signal(signal.SIGTERM, previous_handler)
            self.handler_restored = True

def acquire_guard_with_sigterm_handoff(runtime_guard: Path, guard: dict,
                                       authorization: dict, review_commit: str,
                                       integration_base: str,
                                       sigterm_handler: SigtermHandler | None = None,
                                       mask_signals=None):
    """Block SIGTERM only while guard mutation is handed to the campaign."""
    if sigterm_handler is None:
        return acquire_guard(runtime_guard, guard, authorization,
                             review_commit=review_commit,
                             integration_base=integration_base)
    if not hasattr(signal, "pthread_sigmask"):
        raise RuntimeError("SIGTERM_GUARD_HANDOFF_MASK_UNAVAILABLE")
    mask = mask_signals or signal.pthread_sigmask
    previous_mask = mask(signal.SIG_BLOCK, {signal.SIGTERM})
    try:
        consumed = acquire_guard(runtime_guard, guard, authorization,
                                 review_commit=review_commit,
                                 integration_base=integration_base)
        sigterm_handler.mark_guard_acquired()
        return consumed
    finally:
        mask(signal.SIG_SETMASK, previous_mask)


def _atomic_write(path: Path, document: dict):
    payload = json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.", delete=False) as handle:
            tmp = Path(handle.name)
            handle.write(payload); handle.flush(); os.fsync(handle.fileno())
        os.replace(tmp, path)
        tmp = None
    finally:
        if tmp is not None:
            try:
                tmp.unlink()
            except OSError:
                pass


def write_metadata_evidence_manifest(evidence_path: Path, evidence: dict,
                                      manifest_path: Path, manifest: dict) -> dict:
    """Pin chính exact UTF-8 bytes cuối, bao gồm nội dung đa byte."""
    _atomic_write(evidence_path, evidence)
    raw = evidence_path.read_bytes()
    identity = {"sha256": hashlib.sha256(raw).hexdigest(), "size_bytes": len(raw)}
    manifest.update(evidence_sha256=identity["sha256"], evidence_size_bytes=identity["size_bytes"])
    _atomic_write(manifest_path, manifest)
    return identity


def write_navigation_chain(run_directory: Path, chain: dict) -> None:
    raw = json.dumps(chain, ensure_ascii=False, sort_keys=True,
                     separators=(",", ":"), allow_nan=False).encode("utf-8")
    _atomic_write(run_directory / "navigation_evidence_chain.json", {
        "schema_version": "1.0", "chain": chain, "canonical": raw.decode("utf-8"),
        "sha256": hashlib.sha256(raw).hexdigest()})


def complete_collector_handshake(*, gate, cpp, cpp_member, gate_path: Path,
                                 observer_path: Path, config_hash: str, invocation_id: str,
                                 record: dict, collection_timeout=1800, finalize_timeout=60):
    """Collection -> C++ finalize khi Gate-B sống -> terminal peer -> exit."""
    from step07_gate_b_evidence_validator import validate_gate_b_collection, validate_gate_b_terminal, load_json
    state = {"protocol": "2.0", "events": [], "status": "PENDING"}
    record["collector_handshake"] = state
    try:
        deadline = time.monotonic() + collection_timeout
        while not gate_path.is_file():
            if cpp.poll() is not None:
                raise RuntimeError("CPP_OBSERVER_EXITED_BEFORE_RUNNER_SHUTDOWN")
            if gate.poll() is not None:
                raise RuntimeError("GATE_B_EXITED_BEFORE_COLLECTION_ARTIFACT")
            if time.monotonic() >= deadline:
                raise RuntimeError("GATE_B_COLLECTION_ARTIFACT_TIMEOUT")
            time.sleep(0.05)
        collection = load_canonical_json(gate_path)
        validate_gate_b_collection(collection, config_hash=config_hash, invocation_id=invocation_id)
        state["events"].append("GATE_B_COLLECTION_VERIFIED")
        if gate.poll() is not None:
            raise RuntimeError("GATE_B_EXITED_BEFORE_CPP_SNAPSHOT")
        if cpp.poll() is not None:
            raise RuntimeError("CPP_OBSERVER_EXITED_BEFORE_RUNNER_SHUTDOWN")
        if not _owned_group_verified(cpp, cpp_member):
            raise RuntimeError("CPP_OBSERVER_PROCESS_GROUP_NOT_OWNED")
        if cpp_member.get("finalize_request_issued") is True:
            raise RuntimeError("CPP_FINALIZE_REQUEST_ALREADY_ISSUED")
        previous = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGTERM})
        try:
            if os.getpgid(cpp.pid) != cpp_member["pgid"]:
                raise RuntimeError("CPP_OBSERVER_PROCESS_GROUP_NOT_OWNED")
            cpp_member.update(finalize_request_issued=True, shutdown_requested_by_runner=True,
                shutdown_signal="SIGINT", shutdown_request={"requested": True, "by": "runner",
                "reason": "GATE_B_COLLECTION_VERIFIED", "signal": "SIGINT"})
            os.killpg(cpp_member["pgid"], signal.SIGINT)
        finally:
            signal.pthread_sigmask(signal.SIG_SETMASK, previous)
        state["events"].append("CPP_FINALIZE_REQUESTED")
        cpp.wait(timeout=finalize_timeout)
        if cpp.returncode != 0:
            raise RuntimeError(f"CPP_OBSERVER_FAILED:{cpp.returncode}")
        if not observer_path.is_file():
            raise RuntimeError("CPP_OBSERVER_ARTIFACT_MISSING")
        peer = load_json(observer_path)[0]
        if (peer.get("schema_version") != "1.0" or peer.get("config_hash") != config_hash
                or peer.get("invocation_id") != invocation_id or peer.get("snapshot_complete") is not True
                or type(peer.get("graph")) is not dict or type(peer.get("qos_verdict")) is not dict):
            raise RuntimeError("CPP_OBSERVER_FINAL_ARTIFACT_INVALID")
        state["events"].append("CPP_SNAPSHOT_COMPLETE")
        gate.wait(timeout=finalize_timeout + 5)
        terminal_path = gate_path.with_name("gate_b_terminal.json")
        if not terminal_path.is_file():
            raise RuntimeError("GATE_B_TERMINAL_EVIDENCE_MISSING")
        terminal = load_canonical_json(terminal_path)
        verdict = validate_gate_b_terminal(terminal, collection_raw=gate_path.read_bytes(),
            peer_raw=observer_path.read_bytes(), config_hash=config_hash, invocation_id=invocation_id)
        state["events"].append("GATE_B_TERMINAL_VERIFIED")
        if gate.returncode != 0 or not verdict["terminal_pass"]:
            raise RuntimeError("GATE_B_TERMINAL_FAILED:" + ";".join(verdict["errors"]))
        state["status"] = "COMPLETE"
        return terminal
    except BaseException as error:
        state.update(status="FAIL", failure_literal=f"{type(error).__name__}:{_safe_error_message(error)}")
        _atomic_write(gate_path.with_name("collector_handshake.failure.json"), {
            "schema_version": "1.0", "invocation_id": invocation_id,
            "config_hash": config_hash, **state})
        raise


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


def _process_group_members(pgid: int, *, proc_root: Path = Path("/proc")) -> dict:
    live, zombies, errors = [], [], []
    try:
        entries = list(proc_root.iterdir())
    except OSError as error:
        return {"live_member_pids": [], "zombie_member_pids": [],
                "verified": False, "inspection_errors": [f"PROC_ENUMERATION:{type(error).__name__}"]}
    for proc in entries:
        if not proc.name.isdigit():
            continue
        try:
            stat_text = (proc / "stat").read_text()
            closing = stat_text.rfind(")")
            if closing < 0:
                raise ValueError("stat command delimiter missing")
            stat_fields = stat_text[closing + 1:].split()
            if int(stat_fields[2]) == pgid:
                (zombies if stat_fields[0] == "Z" else live).append(int(proc.name))
        except (ValueError, IndexError) as error:
            errors.append(f"{proc.name}:PROC_STAT_INVALID:{type(error).__name__}")
        except OSError as error:
            errors.append(f"{proc.name}:PROC_STAT_UNREADABLE:{type(error).__name__}")
    return {"live_member_pids": sorted(live), "zombie_member_pids": sorted(zombies),
            "verified": not errors, "inspection_errors": sorted(errors)}


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


PROCESS_GROUP_NAMES = ("bootstrap", "composite", "cpp_observer", "gate_b_observer")


def _empty_process_group_member(name: str) -> dict:
    """Return the complete, stable evidence shape before any child is spawned."""
    return {"name": name, "pid": None, "launcher_pid": None, "child_pid": None,
            "pgid": None, "ownership_relation": "NOT_STARTED", "command": [],
            "returncode": None, "exit_code": None, "readiness": None,
            "qos_observation": None, "qos_verdict": None,
            "shutdown_request": None, "terminal_state": "NOT_STARTED",
            "clean": False, "verified": False, "graceful": False, "ordered": False,
            "shutdown_requested_by_runner": False, "shutdown_signal": None,
            "log_path": None, "initial_snapshot": None, "final_snapshot": None,
            "ownership_verified": False, "ownership_errors": []}


def _initialize_process_group_schema(record: dict) -> dict:
    """Install all fixed process-group entries before guard acquisition."""
    groups = {name: _empty_process_group_member(name) for name in PROCESS_GROUP_NAMES}
    record["process_groups"] = groups
    return groups


def _record_spawned_process_group(record: dict, name: str, member: dict) -> dict:
    groups = record.get("process_groups")
    if type(groups) is not dict or tuple(groups) != PROCESS_GROUP_NAMES:
        raise RuntimeError("PROCESS_GROUP_SCHEMA_INVALID")
    if name not in groups or member.get("name") != name:
        raise RuntimeError(f"PROCESS_GROUP_SCHEMA_MEMBER_INVALID:{name}")
    groups[name].update(member)
    return groups[name]


def _record_collector_readiness(member: dict, readiness: dict) -> None:
    member["readiness"] = readiness
    child_pid = readiness.get("pid") if type(readiness) is dict else None
    if type(child_pid) is int and child_pid > 1:
        member["child_pid"] = child_pid
        member["ownership_relation"] = (
            "LAUNCHER_IS_COLLECTOR" if child_pid == member.get("launcher_pid")
            else "CHILD_IN_LAUNCHER_PROCESS_GROUP")
    if type(readiness) is dict and readiness.get("ready") is True:
        member["terminal_state"] = "READY_AWAITING_RUNNER_SHUTDOWN"


def _spawn_owned_process(command: list[str], *, name: str, cwd: Path, env: dict[str, str],
                         log_path: Path, processes: list[dict],
                         ownership_ledger: dict | None = None,
                         sigterm_handler: SigtermHandler | None = None) -> tuple[subprocess.Popen, dict]:
    """Đăng ký handle trước PGID/snapshot; SIGTERM chỉ latch trong registration."""
    ledger = ownership_ledger if ownership_ledger is not None else {}
    if name in ledger:
        raise RuntimeError(f"PROCESS_ALREADY_REGISTERED:{name}")
    if sigterm_handler is not None:
        sigterm_handler.registration_depth += 1
    try:
        with open(log_path, "wb") as log:
            proc = subprocess.Popen(command, cwd=cwd, env=env, stdout=log,
                                    stderr=subprocess.STDOUT, start_new_session=True)
            member = {"name": name, "pid": proc.pid, "launcher_pid": proc.pid,
                      "child_pid": None, "pgid": None,
                      "ownership_relation": "LAUNCHER_IS_PROCESS_GROUP_LEADER",
                      "command": list(command), "returncode": None, "exit_code": None,
                      "readiness": None, "qos_observation": None, "qos_verdict": None,
                      "shutdown_request": None, "terminal_state": "STARTING",
                      "clean": False, "verified": False, "graceful": False,
                      "ordered": False, "shutdown_requested_by_runner": False,
                      "shutdown_signal": None,
                      "log_path": str(log_path),
                      "initial_snapshot": None, "final_snapshot": None,
                      "ownership_verified": False, "ownership_errors": []}
            ledger[name] = {"process": proc, "member": member}
            processes.append(member)
        try:
            member["pgid"] = os.getpgid(proc.pid)
            member["initial_snapshot"] = _process_group_members(member["pgid"])
            snapshot = member["initial_snapshot"]
            member["ownership_verified"] = (
                member["pgid"] == proc.pid and proc.pid > 1
                and snapshot.get("verified") is True
                and proc.pid in snapshot.get("live_member_pids", []))
            if not member["ownership_verified"]:
                raise RuntimeError(f"PROCESS_OWNERSHIP_UNVERIFIED:{name}")
        except BaseException as error:
            member["ownership_errors"].append(f"PROCESS_REGISTRATION_FAILED:{type(error).__name__}:{error}")
            raise
    finally:
        if sigterm_handler is not None:
            sigterm_handler.registration_depth -= 1
    if sigterm_handler is not None and sigterm_handler.interrupted:
        sigterm_handler._raise_once()
    return proc, member


def _owned_group_verified(proc, member) -> bool:
    return (proc is not None and isinstance(member, dict)
            and type(member.get("pid")) is int and member["pid"] > 1
            and member["pid"] == proc.pid == member.get("pgid")
            and (member.get("ownership_verified") is True
                 or (member.get("initial_snapshot") or {}).get("verified") is True
                 and proc.pid in (member.get("initial_snapshot") or {}).get("live_member_pids", [])))


def _stop_unverified_child(proc, member, timeout):
    """Không killpg khi ownership chưa rõ; chỉ thử dừng child đã giữ handle."""
    errors = ["PROCESS_OWNERSHIP_UNVERIFIED"]
    errors.extend(member.get("ownership_errors", []) if isinstance(member, dict) else [])
    try:
        proc.send_signal(signal.SIGINT)
    except BaseException as error:
        errors.append(f"CHILD_SIGNAL_FAILED:{type(error).__name__}:{error}")
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        errors.append("CHILD_WAIT_TIMEOUT")
        try:
            proc.kill()
            proc.wait(timeout=timeout)
        except BaseException as error:
            errors.append(f"CHILD_STOP_FAILED:{type(error).__name__}:{error}")
    except BaseException as error:
        errors.append(f"CHILD_WAIT_FAILED:{type(error).__name__}:{error}")
    snapshot = {"live_member_pids": [], "zombie_member_pids": [], "verified": False,
                "inspection_errors": ["PROCESS_OWNERSHIP_UNVERIFIED"]}
    if isinstance(member, dict):
        member["final_snapshot"] = snapshot
        member["returncode"] = getattr(proc, "returncode", None)
        member.update({"exit_code": member["returncode"], "clean": False,
                       "verified": False, "graceful": False, "ordered": False,
                       "terminal_state": "TEARDOWN_UNVERIFIED"})
    return {"signal": "SIGINT", "signal_sent": False, "child_stop_attempted": True,
            "leader_returncode": getattr(proc, "returncode", None),
            "exit_code": getattr(proc, "returncode", None), **snapshot,
            "errors": errors, "clean": False, "graceful": False,
            "verified": False, "ordered": False,
            "shutdown_requested_by_runner": (isinstance(member, dict) and
                member.get("shutdown_requested_by_runner") is True),
            "shutdown_signal": None,
            "terminal_state": "TEARDOWN_UNVERIFIED", "escalation_history": []}


def _safe_error_message(error: BaseException) -> str:
    try:
        message = str(error)
    except BaseException:
        message = "ERROR_MESSAGE_UNAVAILABLE"
    return message if isinstance(message, str) and message else type(error).__name__


def _safe_failure_text(value, fallback: str) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    if type(value) is dict:
        try:
            return json.dumps(value, ensure_ascii=False, sort_keys=True,
                              separators=(",", ":"), allow_nan=False)
        except (TypeError, ValueError):
            return fallback
    return fallback


def record_campaign_failure(record: dict, phase: str, error: BaseException) -> dict:
    """Persist nullable-prone exception details as structured data and a safe literal."""
    message = _safe_error_message(error)
    literal = f"{type(error).__name__}:{message}"
    details = {"phase": _safe_failure_text(phase, "CAMPAIGN"),
               "exception_type": type(error).__name__, "message": message,
               "literal": literal}
    record["failure_details"] = details
    record["pre_teardown_failure"] = literal
    return details


def validate_started_process_group(proc: subprocess.Popen, member: dict) -> None:
    if (proc.poll() is not None or member.get("pid") != member.get("pgid")
            or member.get("initial_snapshot", {}).get("verified") is not True
            or member.get("pid") not in member.get("initial_snapshot", {}).get("live_member_pids", [])):
        raise RuntimeError(f"CAMPAIGN_PROCESS_GROUP_STALE_OR_INVALID:{member.get('name', 'unknown')}")


def _stop_owned_process(proc: subprocess.Popen | None, member: dict | None, timeout: float) -> dict:
    request = member.get("shutdown_request") if type(member) is dict else None
    shutdown_requested = (type(member) is dict and
        (member.get("shutdown_requested_by_runner") is True or
         (type(request) is dict and request.get("requested") is True and request.get("by") == "runner")))
    if type(member) is dict:
        member["shutdown_requested_by_runner"] = shutdown_requested
    result = {"signal": "SIGINT", "signal_sent": False, "leader_returncode": None,
              "exit_code": None, "live_member_pids": [], "zombie_member_pids": [],
              "verified": False, "errors": [], "clean": False, "graceful": False,
              "ordered": False, "shutdown_requested_by_runner": shutdown_requested,
              "shutdown_signal": None,
              "terminal_state": "TEARDOWN_UNVERIFIED", "escalation_history": []}
    if proc is not None and not _owned_group_verified(proc, member):
        return _stop_unverified_child(proc, member, timeout)
    if proc is None or type(member) is not dict or type(member.get("pgid")) is not int or member["pgid"] <= 1:
        result["errors"] = ["PROCESS_GROUP_MISSING"]
        return result
    try:
        leader_exited = proc.poll() is not None
        if not leader_exited and os.getpgid(proc.pid) != member["pgid"]:
            return _stop_unverified_child(proc, member, timeout)
    except BaseException as error:
        member.setdefault("ownership_errors", []).append(f"PROCESS_GROUP_RECHECK_FAILED:{type(error).__name__}:{error}")
        return _stop_unverified_child(proc, member, timeout)
    signal_sent = False
    errors = []
    try:
        if not leader_exited and member.get("finalize_request_issued") is not True:
            os.killpg(member["pgid"], signal.SIGINT)
            signal_sent = True
    except ProcessLookupError:
        errors.append("KILLPG_PROCESS_NOT_FOUND")
    except BaseException as error:
        errors.append(f"KILLPG_FAILED:{type(error).__name__}:{error}")
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        errors.append("PROCESS_WAIT_TIMEOUT")
    except BaseException as error:
        errors.append(f"PROCESS_WAIT_FAILED:{type(error).__name__}:{error}")
    try:
        snapshot = _process_group_members(member["pgid"])
    except BaseException as error:
        snapshot = {"live_member_pids": [], "zombie_member_pids": [], "verified": False,
                    "inspection_errors": [f"PROC_SNAPSHOT_FAILED:{type(error).__name__}:{error}"]}
    if leader_exited and (snapshot.get("live_member_pids") or snapshot.get("zombie_member_pids")):
        member.setdefault("ownership_errors", []).append("GROUP_OWNER_EXITED_WITH_REMAINING_MEMBERS")
        return _stop_unverified_child(proc, member, timeout)
    if not snapshot.get("verified"):
        errors.extend(snapshot.get("inspection_errors", ["PROC_SNAPSHOT_UNVERIFIED"]))
    try:
        returncode = proc.returncode
    except BaseException as error:
        returncode = None
        errors.append(f"PROCESS_RETURN_CODE_UNAVAILABLE:{type(error).__name__}")
    clean = ((signal_sent or leader_exited or member.get("finalize_request_issued") is True) and not errors and returncode == 0
             and not snapshot["live_member_pids"] and not snapshot["zombie_member_pids"])
    verified = snapshot.get("verified") is True
    graceful = clean and not result["escalation_history"]
    terminal_state = ("RUNNER_SHUTDOWN_COMPLETE" if clean else "RUNNER_SHUTDOWN_FAILED") \
        if shutdown_requested else ("EXITED" if returncode == 0 else "FAILED")
    member.update({"returncode": returncode, "exit_code": returncode,
                   "final_snapshot": snapshot, "clean": clean, "verified": verified,
                   "graceful": graceful, "ordered": False,
                   "shutdown_requested_by_runner": shutdown_requested,
                   "shutdown_signal": "SIGINT" if signal_sent else member.get("shutdown_signal"),
                   "terminal_state": terminal_state})
    result.update(snapshot)
    result.update({"signal_sent": signal_sent, "leader_returncode": returncode,
                   "exit_code": returncode, "verified": verified, "errors": errors,
                   "clean": clean, "graceful": graceful,
                   "shutdown_signal": "SIGINT" if signal_sent else None,
                   "terminal_state": terminal_state})
    return result


def _safe_stop_owned_process(proc, member, timeout: float) -> dict:
    try:
        return _stop_owned_process(proc, member, timeout)
    except BaseException as error:
        literal = f"TEARDOWN_EXCEPTION:{type(error).__name__}:{_safe_error_message(error)}"
        snapshot = {"live_member_pids": [], "zombie_member_pids": [], "verified": False,
                    "inspection_errors": [literal]}
        if isinstance(member, dict):
            member["final_snapshot"] = snapshot
            try:
                member["returncode"] = proc.returncode if proc is not None else None
            except BaseException:
                member["returncode"] = None
            member.update({"exit_code": member["returncode"], "clean": False,
                           "verified": False, "graceful": False, "ordered": False,
                           "terminal_state": "TEARDOWN_FAILED"})
        return {"signal": "SIGINT", "signal_sent": False,
                "leader_returncode": member.get("returncode") if isinstance(member, dict) else None,
                "exit_code": member.get("returncode") if isinstance(member, dict) else None,
                **snapshot, "errors": [literal], "clean": False, "verified": False,
                "graceful": False, "ordered": False,
                "shutdown_requested_by_runner": (isinstance(member, dict) and
                    member.get("shutdown_requested_by_runner") is True),
                "shutdown_signal": None,
                "terminal_state": "TEARDOWN_FAILED", "escalation_history": []}


def _stop_collector(proc, member, timeout: float = 20) -> dict:
    if proc is None and member is None:
        return {"signal": "SIGINT", "signal_sent": False, "leader_returncode": None,
                "exit_code": None, "live_member_pids": [], "zombie_member_pids": [], "verified": True,
                "inspection_errors": [], "errors": [], "clean": True, "graceful": True,
                "ordered": False, "shutdown_requested_by_runner": False,
                "shutdown_signal": None,
                "terminal_state": "NOT_STARTED", "escalation_history": [], "started": False}
    return _safe_stop_owned_process(proc, member, timeout)


def _launcher_log_escalations(member: dict) -> list[dict]:
    """Return launcher log escalation lines following its SIGINT shutdown marker."""
    raw_path = member.get("log_path")
    if not isinstance(raw_path, str) or not raw_path:
        return []
    try:
        lines = Path(raw_path).read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    shutdown_start = next((index for index, line in enumerate(lines)
        if "sigint" in line.lower() and any(marker in line.lower()
            for marker in ("ctrl-c", "receiving", "received", "interrupted"))), None)
    if shutdown_start is None:
        return []
    escalations = []
    for index, line in enumerate(lines[shutdown_start + 1:], start=shutdown_start + 2):
        match = re.search(r"escalat(?:ing|ed|e)\s+to\s+['\"]?(SIGTERM|SIGKILL)\b", line, re.IGNORECASE)
        if match is not None:
            signal_name = match.group(1).upper()
            escalations.append({"source": "launcher_log", "line": index,
                                "signal": signal_name, "detail": line.strip()})
    return escalations


def teardown_campaign_processes(*, composite_proc, composite_member, bootstrap_proc,
                                bootstrap_member, collector_procs, collector_members,
                                bootstrap_calls: int, composite_calls: int) -> dict:
    """Best-effort ordered shutdown; every unverified operation makes teardown fail."""
    teardown = {"completed": False, "clean": False, "ordered": False,
                "order_correct": False, "verified": False, "graceful": False,
                "shutdown_requested_by_runner": False, "exit_code": None,
                "terminal_state": "TEARDOWN_NOT_STARTED",
                "escalation_history": [], "errors": []}
    teardown["composite"] = _safe_stop_owned_process(composite_proc, composite_member, 30)
    teardown["bootstrap"] = _safe_stop_owned_process(bootstrap_proc, bootstrap_member, 30)
    teardown["order"] = ["composite", "bootstrap"]
    for name in ("gate_b_observer", "cpp_observer"):
        teardown.setdefault("collectors", {})[name] = _stop_collector(
            collector_procs.get(name), collector_members.get(name))
    members = {member.get("name"): member for member in (collector_members or {}).values()
               if isinstance(member, dict)}
    members.update({"composite": composite_member, "bootstrap": bootstrap_member})
    snapshots = {}
    for name, member in members.items():
        try:
            snapshot = member.get("final_snapshot") or _process_group_members(member["pgid"])
        except BaseException as error:
            snapshot = {"live_member_pids": [], "zombie_member_pids": [], "verified": False,
                        "inspection_errors": [f"FINAL_SNAPSHOT_FAILED:{type(error).__name__}:{error}"]}
        snapshots[name] = snapshot
    teardown["process_group_snapshots"] = snapshots
    all_live = sorted({pid for snapshot in snapshots.values() for pid in snapshot.get("live_member_pids", [])})
    all_zombie = sorted({pid for snapshot in snapshots.values() for pid in snapshot.get("zombie_member_pids", [])})
    verified = all(snapshot.get("verified") is True for snapshot in snapshots.values())
    verified = verified and all(
        item.get("verified") is True
        for item in (teardown["composite"], teardown["bootstrap"], *teardown["collectors"].values())
    )
    teardown.update({"live_member_pids": all_live, "zombie_member_pids": all_zombie,
                     "verified": verified})
    teardown["errors"] = [error for item in (teardown["composite"], teardown["bootstrap"],
        *teardown["collectors"].values()) for error in item.get("errors", [])]
    teardown["clean"] = (verified and not teardown["errors"] and not all_live and not all_zombie
                          and teardown["composite"].get("clean") is True
                          and teardown["bootstrap"].get("clean") is True
                          and all(item.get("clean") is True for item in teardown["collectors"].values()))
    teardown["order_correct"] = (
        teardown["order"] == ["composite", "bootstrap"]
        and teardown["composite"].get("signal_sent") is True
        and teardown["bootstrap"].get("signal_sent") is True
        and bootstrap_calls == 1 and composite_calls == 1
        and isinstance(bootstrap_member, dict) and isinstance(composite_member, dict)
        and bootstrap_member.get("pgid") != composite_member.get("pgid")
        and not teardown["composite"].get("live_member_pids")
        and not teardown["composite"].get("zombie_member_pids")
        and not teardown["bootstrap"].get("live_member_pids")
        and not teardown["bootstrap"].get("zombie_member_pids")
    )
    teardown["ordered"] = teardown["order_correct"]
    process_results = (teardown["composite"], teardown["bootstrap"],
                       *teardown["collectors"].values())
    process_members = {"composite": composite_member, "bootstrap": bootstrap_member}
    process_members.update({name: member for name, member in (collector_members or {}).items()})
    for name, result in (("composite", teardown["composite"]),
                         ("bootstrap", teardown["bootstrap"]),
                         *[(name, teardown["collectors"][name])
                           for name in ("gate_b_observer", "cpp_observer")]):
        member = process_members.get(name)
        launcher_escalations = _launcher_log_escalations(member) if isinstance(member, dict) else []
        if launcher_escalations:
            result["escalation_history"] = [*result.get("escalation_history", []),
                                             *launcher_escalations]
        if result.get("escalation_history"):
            result["graceful"] = False
    teardown["escalation_history"] = [
        {"process": name, **entry}
        for name, result in (("composite", teardown["composite"]),
                             ("bootstrap", teardown["bootstrap"]),
                             *[(name, teardown["collectors"][name])
                               for name in ("gate_b_observer", "cpp_observer")])
        for entry in result.get("escalation_history", [])
    ]
    teardown["graceful"] = (all(item.get("graceful") is True for item in process_results)
                             and teardown["escalation_history"] == [])
    teardown["completed"] = True
    teardown["shutdown_requested_by_runner"] = any(
        item.get("shutdown_requested_by_runner") is True for item in process_results)
    teardown["terminal_state"] = "TEARDOWN_COMPLETE" if teardown["verified"] else "TEARDOWN_UNVERIFIED"
    for name, result in (("composite", teardown["composite"]),
                         ("bootstrap", teardown["bootstrap"]),
                         *[(name, teardown["collectors"][name])
                           for name in ("gate_b_observer", "cpp_observer")]):
        member = process_members.get(name)
        if isinstance(member, dict):
            member.update({"clean": result.get("clean") is True,
                           "verified": result.get("verified") is True,
                           "graceful": result.get("graceful") is True,
                           "ordered": teardown["ordered"] is True,
                           "shutdown_requested_by_runner": result.get(
                               "shutdown_requested_by_runner") is True,
                           "exit_code": result.get("exit_code", result.get("leader_returncode")),
                           "terminal_state": result.get("terminal_state", "TEARDOWN_UNVERIFIED")})
    return teardown


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
    sums_path = run_directory / "SHA256SUMS.txt"
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="",
                                         dir=run_directory, prefix=".SHA256SUMS.", delete=False) as handle:
            tmp = Path(handle.name)
            handle.write(sums); handle.flush(); os.fsync(handle.fileno())
        os.replace(tmp, sums_path)
        tmp = None
    finally:
        if tmp is not None:
            try:
                tmp.unlink()
            except OSError:
                pass


PREACQUIRE_TERMINAL = "STEP07_NAV2_BASELINE_RUN005_PREACQUIRE_PREFLIGHT_FAILED_NO_GUARD_CONSUMED"


def _write_preacquire_failure_evidence(run_directory: Path, record: dict,
                                       error: BaseException, *, guard_lock: Path) -> dict:
    """Persist auditable pre-acquire failure without implying runtime teardown."""
    if run_directory.exists():
        raise RuntimeError("EVIDENCE_DIRECTORY_ALREADY_EXISTS")
    if guard_lock.exists():
        raise RuntimeError("PREACQUIRE_FAILURE_GUARD_LOCK_PRESENT")
    failure_literal = (str(error) if str(error).startswith((
                           "RUNTIME_PYTHON_ENVIRONMENT_INVALID:",
                           "GZ_TRANSPORT_HOST_CAPABILITY_UNAVAILABLE:",
                           "ROS_DISCOVERY_HOST_CAPABILITY_UNAVAILABLE:"))
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


def recover_guard_handoff_failure(*, runtime_guard, guard_lock, guard, authorization,
                                  review_commit, integration_base, error, run_directory,
                                  record, sigterm_handler=None, env=None, preflight=None):
    """Chỉ strict runtime readback được quyền phân loại guard sau exception."""
    readback_error = None
    try:
        current = load_guard(runtime_guard)
    except (OSError, ValueError) as read_error:
        current = None
        readback_error = f"{type(read_error).__name__}:{read_error}"
    consumed = (isinstance(current, dict) and current.get("state") == "CONSUMED"
                and current.get("capacity") == 1 and current.get("acquisition_count") == 1
                and current.get("runtime_authorization") == "GRANTED_FOR_THIS_EXACT_RUN_ONLY"
                and current.get("acquired_review_commit") == review_commit
                and current.get("acquired_integration_base") == integration_base
                and all(current.get(key) == value for key, value in authorization.items()))
    if consumed:
        if sigterm_handler is not None:
            sigterm_handler.mark_guard_acquired()
        return env, preflight, current, error
    if current == guard and current is not None and current.get("state") == PENDING and not guard_lock.exists():
        failure = _write_preacquire_failure_evidence(
            run_directory, record, error, guard_lock=guard_lock)
        return None, None, None, failure
    # Không biết chắc guard còn pending: giữ lock và không tuyên bố chưa consume.
    if run_directory.exists():
        raise RuntimeError("GUARD_STATE_UNVERIFIED_EVIDENCE_ALREADY_EXISTS") from error
    literal = "GUARD_ACQUISITION_STATE_UNVERIFIED"
    record.update({"guard_acquired": None, "guard_state_after": "UNVERIFIED",
                   "guard_acquisition_count": None, "runtime_execution": False,
                   "teardown_applicable": False, "guard_lock_exists": guard_lock.exists(),
                   "guard_readback_error": readback_error,
                   "exception_type": type(error).__name__, "exception_message": str(error),
                   "failure_reason_literals": [literal],
                   "terminal_outcome": "STEP07_NAV2_BASELINE_RUN005_FAIL_GUARD_ACQUISITION_STATE_UNVERIFIED_NO_RETRY"})
    _atomic_write(run_directory / "preflight_failure.json", record)
    _atomic_write(run_directory / "run_record.json", record)
    _write_artifact_manifest(run_directory)
    return None, None, None, record


def preacquire_preflight(worktree: Path, dirs: dict[str, Path], run_directory: Path,
                         partition: str, map_root: Path, fuel_root: Path,
                         source_pins: dict, runtime_guard: Path, guard_lock: Path,
                         guard: dict, authorization: dict, review_commit: str,
                         integration_base: str, runtime_python: Path, record: dict,
                         sigterm_handler: SigtermHandler | None = None,
                         mask_signals=None):
    """Build, host-check and acquire; on failure, save evidence without teardown."""
    try:
        env = prepare_ros_environment(worktree, dirs)
        preflight = host_preflight(env, worktree, run_directory, partition,
                                   map_root, fuel_root, source_pins, runtime_python, record)
        if guard_lock.exists():
            raise RuntimeError("GUARD_LOCK_ALREADY_EXISTS")
        consumed = acquire_guard_with_sigterm_handoff(
            runtime_guard, guard, authorization, review_commit, integration_base,
            sigterm_handler=sigterm_handler, mask_signals=mask_signals)
        return env, preflight, consumed, None
    except BaseException as error:
        return recover_guard_handoff_failure(
            runtime_guard=runtime_guard, guard_lock=guard_lock, guard=guard,
            authorization=authorization, review_commit=review_commit,
            integration_base=integration_base, error=error, run_directory=run_directory,
            record=record, sigterm_handler=sigterm_handler,
            env=locals().get("env"), preflight=locals().get("preflight"))


def finalise_after_teardown(record: dict, runtime_acceptance: dict, teardown: dict) -> dict:
    """The only terminal verdict function; invoke only after all teardown ends."""
    if type(runtime_acceptance) is not dict or not runtime_acceptance or any(type(value) is not bool for value in runtime_acceptance.values()):
        raise ValueError("RUNTIME_ACCEPTANCE_MATRIX_INVALID")
    if teardown.get("completed") is not True:
        raise ValueError("TEARDOWN_NOT_COMPLETED_BEFORE_FINALIZATION")
    record["teardown"] = dict(teardown)
    teardown_ok = (teardown.get("clean") is True and teardown.get("ordered") is True
                   and teardown.get("verified") is True and teardown.get("graceful") is True
                   and teardown.get("escalation_history") == [])
    record["acceptance"] = {**runtime_acceptance,
        "process_group_teardown_clean": teardown.get("clean") is True,
        "teardown_order_and_count_correct": teardown.get("ordered") is True,
        "process_group_teardown_graceful": teardown.get("graceful") is True}
    failures = [f"RUNTIME_ACCEPTANCE_FAILED:{key}" for key, value in runtime_acceptance.items() if not value]
    action_readiness = record.get("action_server_readiness")
    if ("gate_b_vectors" in runtime_acceptance and
            (type(action_readiness) is not dict or action_readiness.get("status") != "PASS"
             or action_readiness.get("attempted") is not True or action_readiness.get("ready") is not True)):
        failures.append("ACTION_SERVER_READINESS_NOT_PROVEN")
    pre_teardown_failure = record.get("pre_teardown_failure")
    if pre_teardown_failure:
        literal = str(pre_teardown_failure)
        if "RUNNER_INTERRUPTED_BY_SIGNAL:SIGTERM" in literal:
            failures.append("RUNNER_INTERRUPTED_BY_SIGNAL:SIGTERM")
        else:
            failures.append(f"PRE_TEARDOWN_FAILURE:{literal}")
    if not teardown.get("clean"):
        failures.append("PROCESS_GROUP_TEARDOWN_FAILED")
    if not teardown.get("order_correct"):
        failures.append("TEARDOWN_ORDER_OR_COUNT_FAILED")
    if teardown.get("verified") is not True:
        failures.append("PROCESS_GROUP_TEARDOWN_UNVERIFIED")
    if teardown.get("ordered") is not True:
        failures.append("PROCESS_GROUP_TEARDOWN_ORDER_UNVERIFIED")
    if teardown.get("graceful") is not True:
        failures.append("PROCESS_GROUP_TEARDOWN_NOT_GRACEFUL")
    if teardown.get("escalation_history") != []:
        failures.append("PROCESS_GROUP_TEARDOWN_ESCALATED")
    failures = list(dict.fromkeys(failures))
    passed = all(record["acceptance"].values()) and not failures
    record["failure_reason_literals"] = failures
    record["terminal_outcome"] = ("STEP07_NAV2_BASELINE_RUN005_PASS_PENDING_INDEPENDENT_EVIDENCE_AUDIT"
                                  if passed else "STEP07_NAV2_BASELINE_RUN005_FAIL_NO_RETRY_GUARD_CONSUMED")
    record["finalized_after_teardown"] = True
    return record


def mark_collector_failures(teardown: dict, outcomes: dict) -> dict:
    failed = {name: row for name, row in outcomes.items()
              if type(row) is dict and row.get("terminal_state") not in ("NOT_STARTED", "READY_AWAITING_ARTIFACTS")
              and row.get("exit_code") is not None and row.get("exit_code") != 0}
    if failed:
        literals = [f"COLLECTOR_FAILED:{name}:{row.get('exit_code')}"
                    for name, row in sorted(failed.items())]
        teardown["collector_failures"] = literals
        teardown["errors"] = list(dict.fromkeys([*teardown.get("errors", []), *literals]))
        teardown["clean"] = False
        teardown["graceful"] = False
    return teardown


def terminal_exit_code(record: dict) -> int:
    """Map the persisted terminal verdict to the runner's process status."""
    return 0 if record.get("terminal_outcome", "").endswith(
        "PASS_PENDING_INDEPENDENT_EVIDENCE_AUDIT") else 2


def persist_terminal_evidence(record: dict, runtime_acceptance: dict, teardown: dict,
                              run_directory: Path, sigterm_handler: SigtermHandler) -> dict:
    """Finalize, resyncing a FAIL bundle if SIGTERM arrives before return."""
    sigterm_handler.begin_finalization()
    try:
        if sigterm_handler.interrupted:
            record["pre_teardown_failure"] = "RUNNER_INTERRUPTED_BY_SIGNAL:SIGTERM"
        result = finalise_after_teardown(record, runtime_acceptance, teardown)
        _atomic_write(run_directory / "run_record.json", result)
        _write_artifact_manifest(run_directory)
        # The handler does not raise during finalization. If it observed a
        # signal while the record, manifest, or checksums were being written,
        # replace any provisional PASS and synchronize the complete bundle.
        if (sigterm_handler.interrupted and
                record.get("pre_teardown_failure") != "RUNNER_INTERRUPTED_BY_SIGNAL:SIGTERM"):
            record["pre_teardown_failure"] = "RUNNER_INTERRUPTED_BY_SIGNAL:SIGTERM"
            result = finalise_after_teardown(record, runtime_acceptance, teardown)
            _atomic_write(run_directory / "run_record.json", result)
            _write_artifact_manifest(run_directory)
        return result
    except BaseException as error:
        if sigterm_handler.interrupted:
            failure_literal = "RUNNER_INTERRUPTED_BY_SIGNAL:SIGTERM"
        else:
            failure_literal = f"FINAL_EVIDENCE_FINALIZATION_FAILED:{type(error).__name__}:{error}"
        record["finalization_failure"] = failure_literal
        failures = list(record.get("failure_reason_literals", []))
        if failure_literal not in failures:
            failures.append(failure_literal)
        record["failure_reason_literals"] = failures
        record["terminal_outcome"] = "STEP07_NAV2_BASELINE_RUN005_FAIL_NO_RETRY_GUARD_CONSUMED"
        record["finalized_after_teardown"] = True
        # The acceptance matrix may be all true; the explicit failure still wins.
        _atomic_write(run_directory / "run_record.json", record)
        _write_artifact_manifest(run_directory)
        return record


def finalize_campaign_after_acquisition(*, record, runtime_acceptance, composite_proc,
                                        composite_member, bootstrap_proc, bootstrap_member,
                                        collector_procs, collector_members, bootstrap_calls,
                                        composite_calls, cpp_calls, gate_b_calls, run_directory,
                                        sigterm_handler, previous_sigterm_handler,
                                        ownership_ledger=None):
    """Run best-effort teardown and terminal persistence under a restored handler."""
    teardown = {"completed": True, "clean": False, "ordered": False,
                "order_correct": False, "verified": False, "graceful": False,
                "shutdown_requested_by_runner": False, "exit_code": None,
                "terminal_state": "TEARDOWN_NOT_VERIFIED",
                "escalation_history": [], "errors": ["TEARDOWN_NOT_VERIFIED"]}
    result = None
    try:
        sigterm_handler.begin_finalization()
        if ownership_ledger is not None:
            def owned(name):
                row = ownership_ledger.get(name, {})
                return row.get("process"), row.get("member")
            composite_proc, composite_member = owned("composite")
            bootstrap_proc, bootstrap_member = owned("bootstrap")
            collector_procs = {name: owned(name)[0] for name in ("gate_b_observer", "cpp_observer")}
            collector_members = {name: owned(name)[1] for name in collector_procs if owned(name)[1] is not None}
            bootstrap_calls = int("bootstrap" in ownership_ledger)
            composite_calls = int("composite" in ownership_ledger)
            cpp_calls = int("cpp_observer" in ownership_ledger)
            gate_b_calls = int("gate_b_observer" in ownership_ledger)
            groups = record.get("process_groups")
            if type(groups) is dict:
                for name, row in ownership_ledger.items():
                    if name in groups and type(row) is dict and type(row.get("member")) is dict:
                        groups[name].update(row["member"])
            record["runtime_execution"] = bool(ownership_ledger)
        try:
            teardown = teardown_campaign_processes(
                composite_proc=composite_proc, composite_member=composite_member,
                bootstrap_proc=bootstrap_proc, bootstrap_member=bootstrap_member,
                collector_procs=collector_procs, collector_members=collector_members,
                bootstrap_calls=bootstrap_calls, composite_calls=composite_calls)
            mark_collector_failures(teardown, record.get("collector_outcomes", {}))
        except BaseException as error:
            teardown = {"completed": True, "clean": False, "ordered": False,
                        "order_correct": False, "verified": False, "graceful": False,
                        "shutdown_requested_by_runner": False, "exit_code": None,
                        "terminal_state": "TEARDOWN_FAILED",
                        "escalation_history": [],
                        "errors": [f"TEARDOWN_UNEXPECTED_FAILURE:{type(error).__name__}:{_safe_error_message(error)}"]}
            record.setdefault("pre_teardown_failure",
                f"TEARDOWN_UNEXPECTED_FAILURE:{type(error).__name__}:{_safe_error_message(error)}")
        record["call_counts"].update({"bootstrap": bootstrap_calls, "composite": composite_calls,
                                      "cpp_observer": cpp_calls, "gate_b_observer": gate_b_calls})
        if sigterm_handler.interrupted:
            record.setdefault("pre_teardown_failure", "RUNNER_INTERRUPTED_BY_SIGNAL:SIGTERM")
        result = persist_terminal_evidence(record, runtime_acceptance, teardown,
                                           run_directory, sigterm_handler)
    except BaseException as error:
        if sigterm_handler.interrupted:
            reason = "RUNNER_INTERRUPTED_BY_SIGNAL:SIGTERM"
        else:
            reason = f"FINALIZATION_PATH_FAILED:{type(error).__name__}:{error}"
        record.setdefault("pre_teardown_failure", reason)
        teardown.update({"completed": True, "clean": False, "ordered": False,
                         "order_correct": False, "verified": False, "graceful": False,
                         "shutdown_requested_by_runner": False, "exit_code": None,
                         "terminal_state": "FINALIZATION_PATH_FAILED",
                         "escalation_history": [], "finalization_path_error": reason})
        record["call_counts"].update({"bootstrap": bootstrap_calls, "composite": composite_calls,
                                      "cpp_observer": cpp_calls, "gate_b_observer": gate_b_calls})
        if sigterm_handler.interrupted:
            record["pre_teardown_failure"] = "RUNNER_INTERRUPTED_BY_SIGNAL:SIGTERM"
        result = persist_terminal_evidence(record, runtime_acceptance, teardown,
                                           run_directory, sigterm_handler)
    finally:
        sigterm_handler.restore(previous_sigterm_handler)
        # Keep the custom handler installed through the final write and until
        # the restoration boundary. If it observed SIGTERM just before the
        # handler swap, synchronize a FAIL bundle after restoration.
        if result is not None and sigterm_handler.interrupted and result.get(
                "terminal_outcome", "").endswith("PASS_PENDING_INDEPENDENT_EVIDENCE_AUDIT"):
            record["pre_teardown_failure"] = "RUNNER_INTERRUPTED_BY_SIGNAL:SIGTERM"
            result = persist_terminal_evidence(record, runtime_acceptance, teardown,
                                               run_directory, sigterm_handler)
        sigterm_handler.terminal_committed = True
    return result


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
    runtime_guard = args.runtime_worktree / args.guard_path.relative_to(source)
    guard_lock = runtime_guard.with_suffix(runtime_guard.suffix + ".lock")
    observer_path = args.run_directory / "runtime_observer.json"
    gate_vectors_path = args.run_directory / "gate_b_vectors.json"
    record = {"schema_version": "1.0", "process_group_schema_version": "2.0",
              "run_id": RUN_ID, "review_commit": head,
              "invocation_id": args.run_directory.name, "collector_handshake_protocol": "2.0",
              "integration_base": args.expected_integration_base, "partition": PARTITION,
              "guard_path": str(args.guard_path), "guard_capacity": guard["capacity"],
              "guard_acquisition_count": guard["acquisition_count"],
              "source_guard": {"path": str(args.guard_path), "state_before": guard.get("state"),
                               "state_after": guard.get("state")},
              "runtime_guard": {"path": str(runtime_guard), "lock_path": str(guard_lock),
                                "state_before": "NOT_ACQUIRED", "state_after": "NOT_ACQUIRED"},
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
    _initialize_process_group_schema(record)
    processes = []
    ownership_ledger = {}
    runtime_acceptance = {"guard_acquired_once": True, "canonical_map_and_fuel_preflight": True,
                          "runtime_graph_and_goal": False, "observer_acceptance": False,
                          "gate_b_vectors": False,
                          "bootstrap_composite_process_groups_distinct": False,
                          "bootstrap_readiness": False, "composite_readiness": False,
                          "all_collectors_ready_before_goal": False}
    collector_members = {}
    record["collector_stage"] = "PRE_BOOTSTRAP"
    record["action_server_readiness"] = {
        "status": "NOT_ATTEMPTED_DUE_TO_COMPOSITE_READINESS",
        "attempted": False, "ready": "NOT_ATTEMPTED"}
    teardown = {"completed": False, "clean": False, "ordered": False,
                "order_correct": False, "verified": False, "graceful": False,
                "escalation_history": []}
    sigterm_handler = SigtermHandler()
    previous_sigterm_handler = signal.getsignal(signal.SIGTERM)
    signal.signal(signal.SIGTERM, sigterm_handler)
    try:
        env, preflight, consumed, preacquire_failure = preacquire_preflight(
            args.runtime_worktree, dirs, args.run_directory, args.gz_partition,
            args.canonical_map_root, args.fuel_cache_root, guard["source_pins"],
            runtime_guard, guard_lock, guard, authorization, head,
            args.expected_integration_base, args.runtime_python, record,
            sigterm_handler=sigterm_handler)
    except BaseException as error:
        try:
            env, preflight, consumed, preacquire_failure = recover_guard_handoff_failure(
                runtime_guard=runtime_guard, guard_lock=guard_lock, guard=guard,
                authorization=authorization, review_commit=head,
                integration_base=args.expected_integration_base, error=error,
                run_directory=args.run_directory, record=record,
                sigterm_handler=sigterm_handler)
        except BaseException:
            sigterm_handler.restore(previous_sigterm_handler)
            raise
    if preacquire_failure is not None:
        if consumed is None:
            sigterm_handler.restore(previous_sigterm_handler)
            return 2
    if consumed is None:
        sigterm_handler.restore(previous_sigterm_handler)
        return 2
    try:
        record["preflight"] = preflight
        record["guard_state_after_acquire"] = consumed["state"]
        record["guard_state_after"] = consumed["state"]
        record["source_guard"]["state_after"] = guard.get("state")
        record["runtime_guard"].update({"state_before": PENDING,
                                         "state_after": consumed["state"],
                                         "acquisition_count": consumed["acquisition_count"],
                                         "lock_present": guard_lock.exists()})
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
        sigterm_handler.begin_campaign()
        if preacquire_failure is not None:
            raise preacquire_failure
        args.run_directory.mkdir(parents=True, exist_ok=False)
        (args.run_directory / "authorization_state.txt").write_text(
            f"run_id={RUN_ID}\nscope={AUTH_SCOPE}\nreview_commit={head}\nintegration_base={args.expected_integration_base}\nauthorization_sha256={hashlib.sha256(authorization['owner_authorization'].encode()).hexdigest()}\n", encoding="utf-8")
        logdir = args.run_directory / "logs"; logdir.mkdir()
        bootstrap_command, composite_command = campaign_launch_commands(
            preflight, partition=PARTITION, fuel_root=args.fuel_cache_root,
            repository_root=args.runtime_worktree)
        bootstrap_proc, bootstrap_member = _spawn_owned_process(
            bootstrap_command, name="bootstrap", cwd=args.runtime_worktree, env=env,
            log_path=logdir / "bootstrap.log", processes=processes,
            ownership_ledger=ownership_ledger, sigterm_handler=sigterm_handler)
        bootstrap_calls = 1
        record["call_counts"]["bootstrap"] = bootstrap_calls
        _record_spawned_process_group(record, "bootstrap", bootstrap_member)
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
            log_path=logdir / "composite.log", processes=processes,
            ownership_ledger=ownership_ledger, sigterm_handler=sigterm_handler)
        composite_calls = 1
        record["call_counts"]["composite"] = composite_calls
        _record_spawned_process_group(record, "composite", composite_member)
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
        record["collector_stage"] = "COMPOSITE_READY"
        record["action_server_readiness"] = not_attempted_action_server("CPP_OBSERVER_NOT_READY")
        response = _run(["ros2", "service", "call", "/mecanum/safety/rearm", "std_srvs/srv/Trigger", "{}"],
                        cwd=args.runtime_worktree, env=env, timeout=30)
        record["rearm_service_transcript"] = response.stdout
        if "success=true" not in response.stdout.replace(" ", "").lower():
            raise RuntimeError("SAFETY_LIFECYCLE_REARM_NOT_CONFIRMED")
        observer_path = args.run_directory / "runtime_observer.json"
        cpp_ready_path = args.run_directory / "runtime_observer.ready.json"
        gate_ready_path = args.run_directory / "gate_b_observer.ready.json"
        goal_trigger_path = args.run_directory / "gate_b_goal.trigger.json"
        cpp_command = ["ros2", "run", "step07_nav2_baseline_runtime_observer",
                       "step07_nav2_baseline_runtime_observer", "--ros-args",
                       "-p", f"output_path:={observer_path}", "-p", f"ready_path:={cpp_ready_path}",
                       "-p", f"config_hash:={record['config_hash']}",
                       "-p", f"invocation_id:={record['invocation_id']}",
                       "-p", "duration_sec:=1800", "-p", "runner_controlled_shutdown:=true"]
        record["collector_stage"] = "CPP_OBSERVER_STARTING"
        cpp, cpp_member = _spawn_owned_process(
            cpp_command, name="cpp_observer", cwd=args.runtime_worktree, env=env,
            log_path=logdir / "cpp_observer.log", processes=processes,
            ownership_ledger=ownership_ledger, sigterm_handler=sigterm_handler)
        collector_members["cpp_observer"] = cpp_member
        cpp_group = _record_spawned_process_group(record, "cpp_observer", cpp_member)
        cpp_calls = 1; record["call_counts"]["cpp_observer"] = 1
        cpp_required_subscriptions = ["/clock", "/scan", "/wheel/odometry_raw", "/imu/data",
            "/odometry/filtered", "/tf", "/tf_static", "/mecanum/safety_lifecycle_state",
            "/mecanum/final_issued_command", "/mecanum/safety_state"]
        cpp_readiness = wait_collector_ready(
            cpp_ready_path, cpp, collector="step07_nav2_baseline_runtime_observer",
            config_hash=record["config_hash"], required_subscriptions=cpp_required_subscriptions,
            process_group=cpp_member)
        _record_collector_readiness(cpp_group, cpp_readiness)
        record["collector_stage"] = "CPP_OBSERVER_READY"
        record_gate_b_readiness_transition(record, "cpp_initial_ready", "PASS")
        record["action_server_readiness"] = not_attempted_action_server("CPP_OBSERVER_READY_HANDSHAKE_COMPLETED")
        action_server = wait_navigate_to_pose_action_server(env)
        record["action_server_readiness"] = action_server
        runtime_acceptance["navigate_to_pose_action_server_ready"] = action_server["ready"] is True
        gate_blocker = gate_b_start_blocking_reason(cpp_group.get("readiness"), action_server)
        record_gate_b_readiness_transition(record, "action_server_ready",
            "PASS" if gate_blocker is None else "FAIL", gate_blocker)
        if gate_blocker is not None:
            raise RuntimeError(gate_blocker)
        record["collector_stage"] = "CPP_PRE_GATE_B_RECHECK"
        if cpp.poll() is not None:
            record["cpp_observer_terminal_state"] = "CPP_OBSERVER_READY_BUT_TERMINATED"
            cpp_blocker = "CPP_OBSERVER_READY_BUT_TERMINATED_BEFORE_GATE_B"
            record_gate_b_readiness_transition(record, "cpp_pre_gate_b_recheck", "FAIL", cpp_blocker)
            raise RuntimeError(cpp_blocker)
        record_gate_b_readiness_transition(record, "cpp_pre_gate_b_recheck", "PASS")
        record["collector_stage"] = "ACTION_SERVER_READY"
        gate_command = [str(args.runtime_python), "-m", "mecanum_nav_rl.observations.step07_gate_b_observer_node",
                              "--output", str(args.run_directory / "gate_b_vectors.json"),
                              "--config-hash", record["config_hash"], "--peer-evidence-path", str(observer_path),
                              "--invocation-id", record["invocation_id"],
                              "--terminal-output", str(args.run_directory / "gate_b_terminal.json"),
                              "--ready-path", str(gate_ready_path), "--start-path", str(goal_trigger_path),
                              "--goal-x", "-4.0", "--goal-y", "0.0", "--goal-yaw", "0.0"]
        record["collector_stage"] = "GATE_B_OBSERVER_STARTING"
        gate, gate_member = _spawn_owned_process(
            gate_command, name="gate_b_observer", cwd=args.runtime_worktree, env=env,
            log_path=logdir / "gate_b_observer.log", processes=processes,
            ownership_ledger=ownership_ledger, sigterm_handler=sigterm_handler)
        gate_b_calls = 1; record["call_counts"]["gate_b_observer"] = 1
        record_gate_b_readiness_transition(record, "gate_b_start", "PASS")
        collector_members["gate_b_observer"] = gate_member
        gate_group = _record_spawned_process_group(record, "gate_b_observer", gate_member)
        gate_required_subscriptions = ["/scan", "/odometry/filtered", "/mecanum/safety_lifecycle_state",
                                       "/mecanum/final_issued_command"]
        record["collector_stage"] = "GATE_B_OBSERVER_STARTING_READINESS"
        gate_readiness = wait_collector_ready(
            gate_ready_path, gate, collector="step07_gate_b_observer",
            config_hash=record["config_hash"], required_subscriptions=gate_required_subscriptions,
            process_group=gate_member)
        _record_collector_readiness(gate_group, gate_readiness)
        record["collector_stage"] = "GATE_B_OBSERVER_READY"
        record["process_groups"]["gate_b_observer"]["readiness"]["navigate_to_pose_action_server"] = action_server
        chain_ready_path = args.run_directory / "navigation_evidence_chain_collector.ready.json"
        chain_required_subscriptions = ["/mecanum/safety_state", "/mecanum/final_issued_command",
                                        "/odometry/filtered"]
        chain_ready = {"schema_version": "1.0", "collector": "navigation_evidence_chain_collector",
            "state": "READY", "config_hash": record["config_hash"], "pid": os.getpid(),
            "process_alive": True,
            "ros_context_valid": record["process_groups"]["cpp_observer"]["readiness"]["ros_context_valid"],
            "context_owner": "step07_nav2_baseline_runtime_observer",
            "subscriptions_created": chain_required_subscriptions,
            "source_observer_ready_artifact": cpp_ready_path.name}
        _atomic_write(chain_ready_path, chain_ready)
        chain_ready_readback = load_canonical_json(chain_ready_path)
        record["collector_outcomes"] = {"navigation_evidence_chain_collector": {
            "exit_code": None, "terminal_state": "READY_AWAITING_ARTIFACTS",
            "artifact_written": chain_ready_readback.get("state") == "READY",
            "readiness_artifact": chain_ready_path.name}}
        if cpp.poll() is not None:
            record["cpp_observer_terminal_state"] = "CPP_OBSERVER_READY_BUT_TERMINATED"
            raise RuntimeError("CPP_OBSERVER_READY_BUT_TERMINATED")
        all_ready = (record["process_groups"]["cpp_observer"]["readiness"].get("ready") is True
                     and record["process_groups"]["gate_b_observer"]["readiness"].get("ready") is True
                     and chain_ready_readback.get("state") == "READY"
                     and chain_ready_readback.get("config_hash") == record["config_hash"]
                     and chain_ready_readback.get("pid") == os.getpid()
                     and chain_ready_readback.get("process_alive") is True
                     and chain_ready_readback.get("ros_context_valid") is True
                     and chain_ready_readback.get("subscriptions_created") == chain_required_subscriptions
                     and action_server["ready"] is True
                     and cpp.poll() is None and gate.poll() is None)
        if not all_ready:
            raise RuntimeError("GATE_B_COLLECTOR_READINESS_HANDSHAKE_FAILED")
        record["collector_stage"] = "ALL_COLLECTORS_READY"
        runtime_acceptance["all_collectors_ready_before_goal"] = True
        record["collector_stage"] = "GOAL_TRIGGERED"
        _atomic_write(goal_trigger_path, {"schema_version": "1.0", "state": "TRIGGER_GOAL",
            "config_hash": record["config_hash"], "collector_ready": True,
            "ready_collectors": ["step07_nav2_baseline_runtime_observer", "step07_gate_b_observer",
                                 "navigation_evidence_chain_collector"],
            "navigate_to_pose_action_server_ready": True})
        gate_vectors_path = args.run_directory / "gate_b_vectors.json"
        complete_collector_handshake(gate=gate, cpp=cpp, cpp_member=cpp_member,
            gate_path=gate_vectors_path, observer_path=observer_path,
            config_hash=record["config_hash"], invocation_id=record["invocation_id"], record=record)
        cpp_member["exit_code"] = cpp.returncode
        cpp_member["terminal_state"] = "RUNNER_SHUTDOWN_COMPLETE" if cpp.returncode == 0 else "RUNNER_SHUTDOWN_FAILED"
        record["collector_outcomes"] = {
            "gate_b_observer": {"exit_code": gate.returncode,
                "terminal_state": "EXITED" if gate.returncode == 0 else "FAILED",
                "artifact_written": gate_vectors_path.is_file()},
            "cpp_observer": {"exit_code": cpp.returncode,
                "terminal_state": "EXITED" if cpp.returncode == 0 else "FAILED",
                "artifact_written": observer_path.is_file()},
            "navigation_evidence_chain_collector": {"exit_code": None,
                "terminal_state": "READY_AWAITING_ARTIFACTS",
                "artifact_written": chain_ready_path.is_file(),
                "readiness_artifact": chain_ready_path.name},
        }
        gate_member["exit_code"] = gate.returncode
        gate_member["terminal_state"] = "TERMINAL_ARTIFACT_EXITED" if gate.returncode == 0 else "TERMINAL_ARTIFACT_FAILED"
        if gate.returncode != 0 or cpp.returncode != 0:
            from step07_gate_b_evidence_validator import navigation_evidence_chain_failure, load_json
            gate_doc = load_json(gate_vectors_path)[0] if gate_vectors_path.is_file() else {}
            cpp_doc = load_json(observer_path)[0] if observer_path.is_file() else {
                "observer_lifecycle": {"state": "ARTIFACT_MISSING_AFTER_COLLECTOR_EXIT"}}
            failure_literal = (f"GATE_B_OBSERVER_FAILED:{gate.returncode}" if gate.returncode != 0
                               else f"CPP_OBSERVER_FAILED:{cpp.returncode}")
            failure = navigation_evidence_chain_failure(cpp_doc, gate_doc, failure_literal)
            failure_bytes = json.dumps(failure, ensure_ascii=False, sort_keys=True,
                separators=(",", ":"), allow_nan=False).encode("utf-8")
            record["collector_failure"] = {"failure_literal": failure_literal,
                "exit_code": gate.returncode if gate.returncode != 0 else cpp.returncode,
                "lifecycle_state": failure["observer_lifecycle_state"],
                "partial_artifacts": [name for name, exists in (
                    ("gate_b_vectors.json", gate_vectors_path.is_file()),
                    ("runtime_observer.json", observer_path.is_file())) if exists],
                "evidence_chain_failure": failure,
                "evidence_chain_failure_sha256": hashlib.sha256(failure_bytes).hexdigest()}
            record["collector_outcomes"]["navigation_evidence_chain_collector"] = {
                "exit_code": 2, "terminal_state": "FAILED_UPSTREAM_COLLECTOR",
                "artifact_written": True, "failure_literal": failure_literal}
            write_navigation_chain(args.run_directory, failure)
            raise RuntimeError(failure_literal)
        if cpp.returncode != 0:
            raise RuntimeError(f"CPP_OBSERVER_FAILED:{cpp.returncode}")
        from step07_gate_b_evidence_validator import (canonical_navigation_evidence_chain,
            navigation_evidence_chain_failure,
            load_json, validate_gate_b_document, validate_observer)
        cpp_document, _ = load_json(observer_path)
        gate_document, _ = load_json(args.run_directory / "gate_b_vectors.json")
        raw_qos = cpp_document.get("qos_verdict", {})
        cpp_member["qos_observation"] = cpp_document.get("qos_history_depth_observability")
        cpp_member["qos_verdict"] = raw_qos
        qos_values = (raw_qos.get("lifecycle_endpoint_qos_contract"),
                      raw_qos.get("receipt_qos_contract"))
        if "FAIL" in qos_values:
            record["cpp_observer_terminal_state"] = "CPP_OBSERVER_FINAL_RAW_QOS_FAILURE"
        observer_validation = validate_observer(cpp_document, config_hash=record["config_hash"],
            qos_implementation_pin_evidence=preflight["qos_implementation_pin_evidence"],
            review_commit=head)
        resolution = observer_validation.get("qos_history_depth_resolution")
        if "FAIL" not in qos_values and resolution == "UNOBSERVABLE_NO_VALID_PIN":
            record["cpp_observer_terminal_state"] = "CPP_OBSERVER_FINAL_QOS_PROOF_FAILURE"
        elif "FAIL" not in qos_values and resolution == "PINNED_IMPLEMENTATION":
            record["cpp_observer_terminal_state"] = "CPP_OBSERVER_FINAL_QOS_UNOBSERVABLE_WITH_VALID_PROOF"
        elif "FAIL" not in qos_values:
            record["cpp_observer_terminal_state"] = "CPP_OBSERVER_FINAL_QOS_OBSERVED"
        cpp_member["terminal_state"] = record["cpp_observer_terminal_state"]
        try:
            chain, canonical_chain = canonical_navigation_evidence_chain(cpp_document, gate_document)
            write_navigation_chain(args.run_directory, chain)
        except ValueError as error:
            failure_chain = navigation_evidence_chain_failure(cpp_document, gate_document, str(error))
            canonical_failure = json.dumps(failure_chain, ensure_ascii=False, sort_keys=True,
                separators=(",", ":"), allow_nan=False).encode("utf-8")
            write_navigation_chain(args.run_directory, failure_chain)
            record["collector_outcomes"]["navigation_evidence_chain_collector"] = {
                "exit_code": 2, "terminal_state": "FAILED_INCOMPLETE_EVIDENCE_CHAIN",
                "artifact_written": True, "failure_literal": str(error),
                "failure_artifact": "navigation_evidence_chain.json"}
            raise RuntimeError(f"NAVIGATION_EVIDENCE_CHAIN_INCOMPLETE:{error}") from error
        record["collector_outcomes"]["navigation_evidence_chain_collector"] = {
            "exit_code": 0, "terminal_state": "COMPLETE",
            "artifact_written": True, "artifact": "navigation_evidence_chain.json"}
        gate_validation = validate_gate_b_document(gate_document, config_hash=record["config_hash"],
            terminal=load_canonical_json(args.run_directory / "gate_b_terminal.json"),
            collection_raw=gate_vectors_path.read_bytes(), peer_raw=observer_path.read_bytes(),
            invocation_id=record["invocation_id"])
        runtime_acceptance["observer_acceptance"] = bool(observer_validation.get("acceptance")) and all(observer_validation["acceptance"].values())
        runtime_acceptance["gate_b_vectors"] = bool(gate_validation.get("acceptance")) and all(gate_validation["acceptance"].values())
        runtime_acceptance["runtime_graph_and_goal"] = runtime_acceptance["gate_b_vectors"]
        if not runtime_acceptance["observer_acceptance"] or not runtime_acceptance["gate_b_vectors"]:
            raise RuntimeError("RAW_OBSERVER_ACCEPTANCE_FAILED")
        record["goal_result"] = gate_document["navigate_to_pose"]
    except BaseException as error:
        failure_details = record_campaign_failure(
            record, record.get("collector_stage", "CAMPAIGN"), error)
        error_message = failure_details["message"]
        error_text = failure_details["literal"]
        try:
            events = record.get("gate_b_readiness_state_machine", [])
            next_stage = (GATE_B_READINESS_STAGES[len(events)]
                          if type(events) is list and len(events) < len(GATE_B_READINESS_STAGES)
                          else None)
            expected_failure_stage = {
                "CPP_OBSERVER_STARTING": "cpp_initial_ready",
                "CPP_OBSERVER_READY": "action_server_ready",
                "CPP_PRE_GATE_B_RECHECK": "cpp_pre_gate_b_recheck",
            }.get(record.get("collector_stage"))
            if (next_stage == expected_failure_stage
                    and (not events or events[-1].get("status") == "PASS")):
                record_gate_b_readiness_transition(record, next_stage, "FAIL", error_text)
        except BaseException as transition_error:
            record["gate_b_readiness_state_machine_failure"] = (
                f"{type(transition_error).__name__}:{_safe_error_message(transition_error)}")
        groups = record.get("process_groups")
        if type(groups) is dict and record.get("collector_stage") in (
                "CPP_OBSERVER_STARTING", "GATE_B_OBSERVER_STARTING",
                "GATE_B_OBSERVER_STARTING_READINESS"):
            group_name = ("cpp_observer" if record["collector_stage"] == "CPP_OBSERVER_STARTING"
                          else "gate_b_observer")
            member_record = groups.get(group_name)
            if type(member_record) is dict and member_record.get("readiness") is None:
                member_record["readiness"] = {"ready": False, "failure": str(error)}
                member_record["terminal_state"] = "NOT_READY"
        if "CPP_READY_BUT_TERMINATED" in error_text:
            record["cpp_observer_terminal_state"] = "CPP_OBSERVER_READY_BUT_TERMINATED"
        elif ("CPP_NOT_READY" in error_text or "CPP_READINESS" in error_text
              or record.get("collector_stage") == "CPP_OBSERVER_STARTING"):
            record["cpp_observer_terminal_state"] = "CPP_OBSERVER_NOT_READY"
        process_groups = record.get("process_groups")
        cpp_group_state = (process_groups.get("cpp_observer")
                           if type(process_groups) is dict else None)
        cpp_readiness_state = (cpp_group_state.get("readiness")
                               if type(cpp_group_state) is dict else None)
        if (cpp is not None and type(cpp_readiness_state) is dict
                and cpp_readiness_state.get("ready") is True and cpp.poll() is not None):
            record["cpp_observer_terminal_state"] = "CPP_OBSERVER_READY_BUT_TERMINATED"
        action_readiness_state = record.get("action_server_readiness")
        if type(action_readiness_state) is not dict:
            action_readiness_state = {}
            record["action_server_readiness"] = action_readiness_state
        if action_readiness_state.get("attempted") is not True:
            record["action_server_readiness"] = not_attempted_action_server(error_text)
        if gate is not None or cpp is not None:
            settlement_literal = f"RUNNER_COLLECTOR_SETTLEMENT:{type(error).__name__}:{error_message}"
            action_readiness_state = record.get("action_server_readiness")
            action_readiness_state = (action_readiness_state
                if type(action_readiness_state) is dict else {})
            if record.get("gate_b_start_blocking_reason"):
                settlement_blocking_reason = record["gate_b_start_blocking_reason"]
            elif action_readiness_state.get("status") == "FAIL":
                settlement_blocking_reason = _safe_failure_text(
                    action_readiness_state.get("failure_literal"), error_text)
            else:
                settlement_blocking_reason = error_text or record.get("collector_stage") or "COLLECTOR_PREREQUISITE_FAILED"
            # Bind a runner-authored stage artifact to the run record even when
            # collector teardown itself completes without an error.
            record["collector_settlement"] = {
                "failure_literal": settlement_literal,
                "blocking_reason": settlement_blocking_reason,
                "stage": record.get("collector_stage", "UNRECORDED"),
            }
            try:
                record["collector_outcomes"] = settle_collectors_before_teardown(
                    gate=gate, cpp=cpp, gate_member=collector_members.get("gate_b_observer"),
                    cpp_member=collector_members.get("cpp_observer"), gate_path=gate_vectors_path,
                    observer_path=observer_path, config_hash=record["config_hash"],
                    failure_literal=settlement_literal,
                    blocking_reason=settlement_blocking_reason)
                chain_ready_path = args.run_directory / "navigation_evidence_chain_collector.ready.json"
                if chain_ready_path.is_file() and record["collector_outcomes"].get(
                        "navigation_evidence_chain_collector", {}).get("terminal_state") != "COMPLETE":
                    record["collector_outcomes"]["navigation_evidence_chain_collector"] = {
                        "exit_code": 2, "terminal_state": "FAILED_RUNNER_POSTPROCESSING",
                        "artifact_written": observer_path.is_file(), "failure_literal": settlement_literal}
                if gate is None:
                    from step07_gate_b_evidence_validator import navigation_evidence_chain_failure, load_json
                    cpp_doc = load_json(observer_path)[0] if observer_path.is_file() else {
                        "observer_lifecycle": {"state": "ARTIFACT_MISSING_AFTER_COLLECTOR_EXIT"}}
                    gate_doc = load_json(gate_vectors_path)[0] if gate_vectors_path.is_file() else {
                        "stage_failure": {"status": "NOT_STARTED", "blocking_reason": settlement_literal}}
                    blocking_reason = (gate_doc.get("stage_failure", {}).get("blocking_reason")
                        if type(gate_doc.get("stage_failure")) is dict else None) or record.get("collector_stage", "UNRECORDED")
                    chain_failure = navigation_evidence_chain_failure(
                        cpp_doc, gate_doc, f"EVIDENCE_WINDOW_NOT_FORMED:{blocking_reason}")
                    chain_bytes = json.dumps(chain_failure, ensure_ascii=False, sort_keys=True,
                        separators=(",", ":"), allow_nan=False).encode("utf-8")
                    record["navigation_evidence_chain_failure"] = chain_failure
                    record["navigation_evidence_chain_failure_sha256"] = hashlib.sha256(chain_bytes).hexdigest()
                    write_navigation_chain(args.run_directory, chain_failure)
                    record.setdefault("collector_outcomes", {})["navigation_evidence_chain_collector"] = {
                        "process_exit_status": "NOT_STARTED", "terminal_state": "NOT_STARTED",
                        "artifact_written": observer_path.is_file(),
                        "failure_literal": chain_failure["failure_literal"],
                        "stage": record.get("collector_stage", "UNRECORDED")}
                failed = {name: row for name, row in record["collector_outcomes"].items()
                          if type(row) is dict and row.get("exit_code") not in (0, None)}
                if failed or not all(row.get("artifact_written") is True
                                     for row in record["collector_outcomes"].values()):
                    record["collector_failure"] = {"failure_literal": settlement_literal,
                        "exit_codes": {name: row["exit_code"] for name, row in record["collector_outcomes"].items()
                                       if type(row) is dict and "exit_code" in row},
                        "process_exit_statuses": {name: row.get("process_exit_status", "UNKNOWN")
                                       for name, row in record["collector_outcomes"].items()
                                       if type(row) is dict},
                        "lifecycle_state": {"state": "SEE_PARTIAL_COLLECTOR_ARTIFACTS"},
                        "partial_artifacts": [path.name for path in (gate_vectors_path, observer_path) if path.is_file()]}
            except BaseException as settlement_error:
                record["collector_settlement_failure"] = (
                    f"{type(settlement_error).__name__}:{settlement_error}")
        record["traceback"] = traceback.format_exc()
    finally:
        if runtime_acceptance:
            finalize_campaign_after_acquisition(
                record=record, runtime_acceptance=runtime_acceptance,
                composite_proc=composite_proc, composite_member=composite_member,
                bootstrap_proc=bootstrap_proc, bootstrap_member=bootstrap_member,
                collector_procs={"gate_b_observer": gate, "cpp_observer": cpp},
                collector_members=collector_members, bootstrap_calls=bootstrap_calls,
                composite_calls=composite_calls, cpp_calls=cpp_calls,
                gate_b_calls=gate_b_calls, run_directory=args.run_directory,
                sigterm_handler=sigterm_handler,
                previous_sigterm_handler=previous_sigterm_handler,
                ownership_ledger=ownership_ledger)
        # Keep every guard, lock, log and evidence artifact after acquisition.
    return terminal_exit_code(record)


ROS_ACTIVE_STATE_ID = 3
COMPOSITE_LIFECYCLE_NODES = (
    "/map_server", "/amcl", "/planner_server", "/controller_server",
    "/behavior_server", "/bt_navigator", "/safety_lifecycle",
)


def composite_readiness_command():
    # Chỉ runner runtime gọi probe này sau source ROS/overlay, trước rearm.
    script = r'''import time
import rclpy
from rclpy.parameter import Parameter
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import LaserScan
from nav_msgs.msg import Odometry
from tf2_ros import Buffer, TransformListener
rclpy.init()
node = rclpy.create_node("step07_pre_rearm_readiness", parameter_overrides=[Parameter("use_sim_time", value=True)])
buffer = Buffer(node=node)
listener = TransformListener(buffer, node)
latest = {}
node.create_subscription(LaserScan, "/scan", lambda msg: latest.update(scan=msg), qos_profile_sensor_data)
node.create_subscription(Odometry, "/odometry/filtered", lambda msg: latest.update(odom=msg), qos_profile_sensor_data)
deadline = time.monotonic() + 8.0
ready = False
try:
    while time.monotonic() < deadline:
        rclpy.spin_once(node, timeout_sec=0.1)
        now = node.get_clock().now().nanoseconds
        fresh = now > 0 and all(key in latest and 0 <= now - (latest[key].header.stamp.sec * 1000000000 + latest[key].header.stamp.nanosec) <= limit for key, limit in (("scan", 500000000), ("odom", 250000000)))
        if fresh and buffer.can_transform("map", "odom", rclpy.time.Time()) and buffer.can_transform("odom", "base_link", rclpy.time.Time()):
            ready = True
            break
finally:
    node.destroy_node()
    rclpy.shutdown()
print("COMPOSITE_DATA_READY" if ready else "COMPOSITE_DATA_NOT_READY")
raise SystemExit(0 if ready else 2)
'''
    return [RUNTIME_PYTHON_PATH, "-c", script]


def active_lifecycle_states(env):
    import re
    states = {}
    for name in COMPOSITE_LIFECYCLE_NODES:
        result = _run(["ros2", "lifecycle", "get", name], env=env, check=False, timeout=10)
        if result.returncode != 0 or re.fullmatch(r"\s*active\s+\[3\]\s*", result.stdout) is None:
            return None
        states[name] = ROS_ACTIVE_STATE_ID
    return states


def _ready_pid_belongs_to_owned_group(pid: int, process: subprocess.Popen,
                                      member: dict | None) -> bool:
    """Accept a ros2-run child PID only when it remains in its owned PGID."""
    if type(pid) is not int or pid <= 0 or process.poll() is not None or type(member) is not dict:
        return False
    pgid = member.get("pgid")
    if type(pgid) is not int or pgid <= 0:
        return False
    try:
        return os.getpgid(pid) == pgid and _owned_group_verified(process, member)
    except (ProcessLookupError, PermissionError, OSError):
        return False


def wait_collector_ready(path: Path, process: subprocess.Popen, *, collector: str,
                        config_hash: str, required_subscriptions, timeout: float = 120,
                        process_group: dict | None = None) -> dict:
    deadline = time.monotonic() + timeout
    saw_ready = False
    while time.monotonic() < deadline:
        try:
            ready = load_canonical_json(path)
        except (OSError, ValueError):
            if process.poll() is not None:
                raise RuntimeError(f"{collector.upper()}_NOT_READY:PROCESS_EXITED:{process.returncode}")
            time.sleep(0.05)
            continue
        if ready.get("state") == "READY":
            saw_ready = True
            if process.poll() is not None or ready.get("process_alive") is not True:
                raise RuntimeError(f"{collector.upper()}_READY_BUT_TERMINATED:{process.returncode}")
        if (ready.get("state") == "READY" and ready.get("collector") == collector
                and ready.get("config_hash") == config_hash
                and _ready_pid_belongs_to_owned_group(ready.get("pid"), process, process_group)
                and ready.get("process_alive") is True
                and ready.get("ros_context_valid") is True
                and ready.get("subscriptions_created") == required_subscriptions):
            return {"ready": True, "artifact": path.name, "pid": ready["pid"],
                    "launcher_pid": process.pid,
                    "pgid": process_group.get("pgid") if type(process_group) is dict else None,
                    "ownership_relation": ("LAUNCHER_IS_COLLECTOR" if ready["pid"] == process.pid
                        else "CHILD_IN_LAUNCHER_PROCESS_GROUP"),
                    "subscriptions_created": list(required_subscriptions),
                    "ros_context_valid": True}
        if ready.get("state") == "NOT_READY" and ready.get("failure_literal"):
            raise RuntimeError(f"{collector.upper()}_NOT_READY:{ready['failure_literal']}")
        if ready.get("state") not in ("READY", "NOT_READY"):
            raise RuntimeError(f"{collector.upper()}_NOT_READY:{ready.get('failure_literal', 'UNKNOWN')}")
        if process.poll() is not None:
            label = "READY_BUT_TERMINATED" if saw_ready else "NOT_READY"
            raise RuntimeError(f"{collector.upper()}_{label}:PROCESS_EXITED:{process.returncode}")
        time.sleep(0.05)
    label = "READY_BUT_TERMINATED" if saw_ready and process.poll() is not None else "NOT_READY"
    raise RuntimeError(f"{collector.upper()}_{label}:READINESS_DEADLINE")


def navigate_to_pose_action_server_ready(env: dict[str, str]) -> dict:
    result = _run(["ros2", "action", "info", "/navigate_to_pose"], env=env,
                  check=False, timeout=15)
    # _run() redirects stderr to STDOUT. CompletedProcess.stderr is therefore
    # normally None; stdout is the one merged transcript and the only source
    # used for the readiness decision.
    transcript = result.stdout
    output_valid = isinstance(transcript, str)
    server_count = None
    if output_valid:
        try:
            transcript.encode("utf-8", errors="strict")
            if "\x00" in transcript:
                output_valid = False
            else:
                server_lines = [line for line in transcript.splitlines()
                                if re.search(r"\bAction\s+servers\s*:", line, re.IGNORECASE)]
                if len(server_lines) != 1:
                    output_valid = False
                else:
                    match = re.fullmatch(r"\s*Action\s+servers\s*:\s*(\d+)\s*",
                                         server_lines[0], re.IGNORECASE)
                    if match is None:
                        output_valid = False
                    else:
                        try:
                            server_count = int(match.group(1))
                        except ValueError:
                            output_valid = False
        except UnicodeEncodeError:
            output_valid = False
    returncode = getattr(result, "returncode", None)
    ready = (output_valid and type(returncode) is int and returncode == 0
             and server_count == 1)
    failure_literal = ("NAVIGATE_TO_POSE_ACTION_SERVER_PROBE_OUTPUT_INVALID"
                       if not output_valid else
                       None if ready else "NAVIGATE_TO_POSE_ACTION_SERVER_NOT_READY")
    return {"ready": ready, "server_count": server_count,
            "transcript": transcript if output_valid else "",
            "failure_literal": failure_literal}


def wait_navigate_to_pose_action_server(env: dict[str, str], *, timeout: float = 120) -> dict:
    deadline = time.monotonic() + timeout
    last = {"ready": False, "server_count": None, "transcript": ""}
    attempts = 0
    while time.monotonic() < deadline:
        attempts += 1
        try:
            last = navigate_to_pose_action_server_ready(env)
        except (OSError, subprocess.SubprocessError) as error:
            last = {"ready": False, "server_count": None,
                    "transcript": f"{type(error).__name__}:{error}"}
        if last["ready"]:
            return {"status": "PASS", "attempted": True, "attempt_count": attempts, **last}
        time.sleep(0.5)
    return {"status": "FAIL", "attempted": attempts > 0, "attempt_count": attempts,
            "failure_literal": (last.get("failure_literal") or
                "NAVIGATE_TO_POSE_ACTION_SERVER_NOT_READY"), **last}


def gate_b_start_blocking_reason(cpp_readiness, action_server) -> str | None:
    """Require proven C++ readiness and a successful action-server probe before Gate-B."""
    if type(cpp_readiness) is not dict or cpp_readiness.get("ready") is not True:
        return "CPP_OBSERVER_READINESS_NOT_PROVEN"
    if (type(action_server) is dict and action_server.get("status") == "PASS"
            and action_server.get("attempted") is True and action_server.get("ready") is True):
        return None
    if type(action_server) is dict:
        return _safe_failure_text(action_server.get("failure_literal"),
            _safe_failure_text(action_server.get("blocking_reason"),
                               "ACTION_SERVER_READINESS_NOT_PROVEN"))
    return "ACTION_SERVER_READINESS_NOT_PROVEN"


GATE_B_READINESS_STAGES = (
    "cpp_initial_ready", "action_server_ready", "cpp_pre_gate_b_recheck", "gate_b_start")


def record_gate_b_readiness_transition(record: dict, stage: str, status: str,
                                       reason: str | None = None) -> dict:
    """Append the next fail-closed Gate-B prerequisite transition."""
    events = record.setdefault("gate_b_readiness_state_machine", [])
    if type(events) is not list or len(events) >= len(GATE_B_READINESS_STAGES):
        raise RuntimeError("GATE_B_READINESS_STATE_MACHINE_INVALID")
    expected = GATE_B_READINESS_STAGES[len(events)]
    if stage != expected:
        raise RuntimeError(f"GATE_B_READINESS_TRANSITION_OUT_OF_ORDER:{expected}:{stage}")
    if events and events[-1].get("status") != "PASS":
        raise RuntimeError(f"GATE_B_READINESS_PREREQUISITE_FAILED:{events[-1].get('stage')}")
    if status not in ("PASS", "FAIL"):
        raise RuntimeError("GATE_B_READINESS_STATUS_INVALID")
    event = {"stage": stage, "status": status}
    if status == "FAIL":
        event["blocking_reason"] = _safe_failure_text(reason, f"{stage.upper()}_NOT_PROVEN")
        record["gate_b_start_blocking_reason"] = event["blocking_reason"]
    events.append(event)
    return event


def not_attempted_action_server(blocking_reason: str) -> dict:
    blocking_reason = _safe_failure_text(blocking_reason, "ACTION_SERVER_READINESS_NOT_PROVEN")
    reason = re.sub(r"[^A-Z0-9_]+", "_", blocking_reason.upper()).strip("_")
    return {"status": f"NOT_ATTEMPTED_DUE_TO_{reason or 'UNKNOWN'}",
            "attempted": False, "ready": "NOT_ATTEMPTED",
            "blocking_reason": blocking_reason}


def settle_collectors_before_teardown(*, gate, cpp, gate_member, cpp_member,
                                     gate_path: Path, observer_path: Path,
                                     config_hash: str, failure_literal: str,
                                     blocking_reason: str | None = None) -> dict:
    """Stop owned collectors first and preserve explicit partial evidence."""
    failure_literal = _safe_failure_text(failure_literal, "COLLECTOR_SETTLEMENT_FAILED")
    blocker = _safe_failure_text(blocking_reason, failure_literal)
    outcomes = {}
    for name, process, member, path in (("gate_b_observer", gate, gate_member, gate_path),
                                        ("cpp_observer", cpp, cpp_member, observer_path)):
        started = process is not None or isinstance(member, dict)
        requested = False
        if process is not None:
            try:
                requested = process.poll() is None
            except BaseException:
                requested = False
        if isinstance(member, dict):
            requested = requested or member.get("shutdown_requested_by_runner") is True
            member["shutdown_requested_by_runner"] = requested
            if not member.get("finalize_request_issued"):
                member["shutdown_signal"] = "SIGINT" if requested else None
                member["shutdown_request"] = {"requested": requested, "by": "runner",
                    "reason": blocker, "signal": "SIGINT"}
        stop_result = _stop_collector(process, member) if started else _stop_collector(None, None)
        exit_code = stop_result.get("exit_code", stop_result.get("leader_returncode"))
        status = ("NOT_STARTED" if not started else
                  "EXITED" if exit_code == 0 else
                  "FAILED" if exit_code is not None else "UNKNOWN")
        outcomes[name] = {"exit_code": exit_code,
            "process_exit_status": status,
            "terminal_state": stop_result.get("terminal_state", "TEARDOWN_UNVERIFIED"),
            "artifact_written": path.is_file(),
            "clean": stop_result.get("clean") is True,
            "verified": stop_result.get("verified") is True,
            "graceful": stop_result.get("graceful") is True,
            "ordered": False, "shutdown_requested_by_runner": requested,
            "shutdown_signal": "SIGINT" if stop_result.get("signal_sent") is True else None,
            "teardown_errors": list(stop_result.get("errors", []))}
    if not gate_path.exists():
        not_started = gate is None
        _atomic_write(gate_path, {"schema_version": "1.0", "config_hash": config_hash,
            "source_contract": "LIDAR72_LOCAL_REFERENCE3_FILTERED_TWIST3_FINAL_RECEIPT3",
            "sample_count": 0, "samples": [], "errors": [failure_literal],
            "collector_terminal_state": "NOT_STARTED" if not_started else "FAILURE_ARTIFACT_WRITTEN_BY_RUNNER",
            "stage_failure": {"status": "NOT_STARTED" if not_started else "FAILED",
                "blocking_reason": blocker, "gate_b_observer_started": not not_started},
            "collector_failure": {"literal": failure_literal,
                "process_exit_status": "NOT_STARTED" if not_started else outcomes["gate_b_observer"].get("process_exit_status", "UNKNOWN"),
                "lifecycle_state": {"state": "NOT_STARTED" if not_started else "FAIL_CLOSED",
                    "reason": blocker}, "partial_artifact": "gate_b_vectors.json",
                "valid_sample_count": 0}})
    if not observer_path.exists():
        _atomic_write(observer_path, {"schema_version": "1.0", "config_hash": config_hash,
            "errors": [failure_literal], "observer_lifecycle": {"state": "FAIL_CLOSED",
                "failure_literal": failure_literal, "ros_context_valid": "UNVERIFIED",
                "partial_artifact": "runtime_observer.json"}})
    for name, path in (("gate_b_observer", gate_path), ("cpp_observer", observer_path)):
        outcomes[name]["artifact_written"] = path.is_file()
    return outcomes


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
            active = active_lifecycle_states(env)
            if active is None:
                time.sleep(2)
                continue
            data = _run(composite_readiness_command(), env=env, check=False, timeout=15)
            (logdir / "pre_rearm_readiness.txt").write_text(data.stdout, encoding="utf-8")
            if data.returncode != 0 or data.stdout.strip() != "COMPOSITE_DATA_READY":
                time.sleep(2)
                continue
            return {"ready": True, "ros_lifecycle_states": active,
                    "data_readiness": "COMPOSITE_DATA_READY",
                    "topics": sorted(required), "nodes": sorted(required_nodes),
                    "services": sorted(required_services),
                    "topic_transcript": transcripts["topics"].name,
                    "node_transcript": transcripts["nodes"].name,
                    "service_transcript": transcripts["services"].name}
        time.sleep(2)
    raise RuntimeError("COMPOSITE_READINESS_TIMEOUT")


if __name__ == "__main__":
    raise SystemExit(main())
