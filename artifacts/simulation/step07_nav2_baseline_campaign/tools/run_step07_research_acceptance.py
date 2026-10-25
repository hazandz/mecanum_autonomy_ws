#!/usr/bin/env python3
"""Single-process owner for simplified Step 7 integrated runtime acceptance.

This module is import-safe offline. Its runtime path is deliberately gated by
an Owner authorization bound to exact commit, global config hash, run ID, and
exclusive output target. It never imports the retired Run005 runner/guard.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import importlib.util
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import uuid
from typing import Any, Callable, Iterable, Mapping


DECISION_ID = "STEP07_RESEARCH_GRADE_RUNTIME_ACCEPTANCE_SIMPLIFICATION_L2"
REPOSITORY_URL = "https://github.com/hazandz/mecanum_autonomy_ws.git"
PROFILE = "sim_eval"
MODE = "NAV2_BASELINE"
WORLD_NAME = "world_demo"
ENTITY_NAME = "ROBOT_URDF_final"
FUEL_EXPECTED = {"OpenRobotics/Depot": "v6", "MovAi/Tugbot": "v1"}
EVIDENCE_HEADS = ("identity.json", "resolved_config.json", "runtime.log",
                  "capture", "acceptance.json", "metrics.json")
CAPTURE_TOPICS = (
    "/clock", "/scan", "/wheel/odometry_raw", "/imu/data", "/odometry/filtered",
    "/tf", "/tf_static", "/map", "/amcl_pose", "/initialpose",
    "/mecanum/safety_lifecycle_state", "/mecanum/safety_state",
    "/mecanum/nav2_candidate_cmd", "/mecanum/safety_accepted_cmd", "/cmd_vel",
    "/mecanum/final_issued_command", "/navigate_to_pose/_action/status",
    "/navigate_to_pose/_action/feedback",
)


class AcceptanceFailure(RuntimeError):
    def __init__(self, stage: str, component: str, reason: str) -> None:
        super().__init__(reason)
        self.stage, self.component, self.reason = stage, component, reason


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_json(path: Path) -> Any:
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raise ValueError("UTF-8 BOM is not allowed")
    return json.loads(raw.decode("utf-8"), object_pairs_hook=_reject_duplicate_keys,
                      parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)))


def atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    """Finite, UTF-8 JSON replacement using a same-directory temporary file."""
    encoded = json.dumps(payload, ensure_ascii=False, allow_nan=False,
                         sort_keys=False, separators=(",", ":")) + "\n"
    temp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    with temp.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, path)


def read_git_identity(repository: Path) -> tuple[str, bool, str]:
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repository,
                             check=True, capture_output=True, text=True).stdout.strip()
    origin = subprocess.run(["git", "remote", "get-url", "origin"], cwd=repository,
                            check=True, capture_output=True, text=True).stdout.strip()
    status = subprocess.run(["git", "status", "--porcelain=v1", "--untracked-files=all"],
                            cwd=repository, check=True, capture_output=True, text=True).stdout
    if origin != REPOSITORY_URL:
        raise AcceptanceFailure("PREFLIGHT", "identity", "ORIGIN_URL_MISMATCH")
    return commit, not status.strip(), origin


def verify_runtime_authorization(path: Path, *, commit: str, config_hash: str,
                                 run_id: str, output_target: Path) -> dict[str, Any]:
    auth = load_json(path)
    expected = {"exact_git_commit": commit, "config_hash": config_hash,
                "run_id": run_id, "output_target": str(output_target.resolve())}
    if not isinstance(auth, dict) or any(auth.get(k) != v for k, v in expected.items()):
        raise AcceptanceFailure("PREFLIGHT", "authorization", "OWNER_AUTHORIZATION_BINDING_MISMATCH")
    if auth.get("owner_authorized") is not True:
        raise AcceptanceFailure("PREFLIGHT", "authorization", "OWNER_RUNTIME_AUTHORIZATION_REQUIRED")
    if auth.get("sim_estop_release_authorized") is not True:
        raise AcceptanceFailure("PREFLIGHT", "authorization", "SIM_ESTOP_RELEASE_AUTHORIZATION_REQUIRED")
    return auth


def dependency_versions() -> dict[str, str]:
    """Record installed versions only; no network or source-file hashing."""
    release = {}
    try:
        for line in Path("/etc/os-release").read_text(encoding="utf-8").splitlines():
            key, sep, value = line.partition("=")
            if sep:
                release[key] = value.strip().strip('"')
    except OSError:
        pass
    versions: dict[str, str] = {
        "os": release.get("PRETTY_NAME", "UNKNOWN"),
        "kernel": os.uname().release,
        "python": sys.version.split()[0],
        "ros_distro": os.environ.get("ROS_DISTRO", "UNKNOWN"),
        "rmw_implementation": os.environ.get("RMW_IMPLEMENTATION", "DEFAULT"),
    }
    for name in ("pydantic", "rclpy", "nav2_msgs", "rosbag2_py"):
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = "NOT_INSTALLED"
        try:
            spec = importlib.util.find_spec(name)
            versions[f"{name}_origin"] = str(spec.origin) if spec else "NOT_IMPORTABLE"
        except (ImportError, AttributeError, ValueError):
            versions[f"{name}_origin"] = "NOT_IMPORTABLE"
    for package in ("gz-sim8", "libsdformat14", "ros-jazzy-nav2-bringup",
                    "ros-jazzy-rclpy", "ros-jazzy-rmw-fastrtps-cpp",
                    "ros-jazzy-rosbag2"):
        result = subprocess.run(["dpkg-query", "-W", "-f=${Version}", package],
                                capture_output=True, text=True, check=False)
        versions[package] = result.stdout.strip() if result.returncode == 0 else "NOT_INSTALLED"
    return versions


def _finite_tree(value: Any) -> bool:
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, Mapping):
        return all(_finite_tree(v) for v in value.values())
    if isinstance(value, (list, tuple)):
        return all(_finite_tree(v) for v in value)
    return True


def validate_resolved_config(document: Mapping[str, Any], *, expected_hash: str | None = None) -> str:
    """Use the existing compiler/hash model and require target policy binding."""
    if not _finite_tree(document):
        raise ValueError("resolved config contains a non-finite value")
    from mecanum_nav_rl.config.v3_compiler import compile_resolved_document_v3
    unhashed = json.loads(json.dumps(document))
    declared = unhashed.get("provenance", {}).pop("config_hash", None)
    if expected_hash is not None and declared != expected_hash:
        raise ValueError("resolved config hash differs from expected identity")
    compiled = compile_resolved_document_v3(unhashed)
    if compiled.runtime.runtime_profile.value != PROFILE or compiled.runtime.navigation_mode.value != MODE:
        raise ValueError("resolved config is not sim_eval/NAV2_BASELINE")
    if declared != compiled.provenance.config_hash:
        raise ValueError("declared config_hash does not match compiled global config_hash")
    if compiled.navigation.step07_acceptance is None:
        raise ValueError("resolved config lacks Step07 global-hash acceptance policy")
    return compiled.provenance.config_hash


def verify_canonical_map(map_root: Path, map_identity: Mapping[str, Any]) -> dict[str, Any]:
    """Verify Architecture §48 map.yaml/map.pgm projection and external identity."""
    import hashlib
    root = map_root.resolve(strict=True)
    if root.name != str(map_identity["map_id"]):
        raise ValueError("canonical map directory does not match map_id")
    manifest_path = root / "map_manifest.json"
    manifest = load_json(manifest_path)
    if manifest.get("map_id") != map_identity["map_id"]:
        raise ValueError("map manifest map_id mismatch")
    if hashlib.sha256(manifest_path.read_bytes()).hexdigest() != map_identity["canonical_manifest_sha256"]:
        raise ValueError("canonical map manifest SHA-256 mismatch")
    entries = manifest.get("map_hash_manifest", {}).get("files")
    expected_roles = (("map_yaml", "map.yaml"), ("occupancy_image", "map.pgm"))
    actual = []
    for entry, (role, name) in zip(entries or (), expected_roles, strict=True):
        path = root / name
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if (entry.get("role"), entry.get("name"), entry.get("sha256"), entry.get("size_bytes")) != (
                role, name, digest, len(raw)):
            raise ValueError(f"map artifact member mismatch: {name}")
        actual.append({"role": role, "name": name, "size_bytes": len(raw), "sha256": digest})
    projection = {"schema": "mecanum_map_hash/v1", "files": actual}
    content_hash = hashlib.sha256(json.dumps(projection, ensure_ascii=False,
        sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    if content_hash != manifest.get("map_content_hash"):
        raise ValueError("Architecture §48 map_content_hash mismatch")
    return {"map_id": manifest["map_id"], "artifact_identity": manifest["artifact_identity"],
            "map_content_hash": content_hash,
            "canonical_manifest_sha256": map_identity["canonical_manifest_sha256"]}


@dataclass
class OwnedProcess:
    name: str
    process: subprocess.Popen[bytes]
    started_steady: float
    log_stream: Any
    pgid: int
    stopped: bool = False


@dataclass
class ProcessOwner:
    processes: list[OwnedProcess] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def start(self, name: str, command: Iterable[str], *, env: Mapping[str, str],
              runtime_log: Any, cwd: Path) -> OwnedProcess:
        process = subprocess.Popen(tuple(command), cwd=cwd, env=dict(env),
                                   stdin=subprocess.DEVNULL, stdout=runtime_log,
                                   stderr=subprocess.STDOUT, start_new_session=True)
        owned = OwnedProcess(name, process, time.monotonic(), runtime_log, process.pid)
        self.processes.append(owned)
        return owned

    @staticmethod
    def _group_members(pgid: int) -> tuple[tuple[int, str], ...] | None:
        """Inspect only the owned process group through procfs; None means unknown."""
        proc = Path("/proc")
        if not proc.is_dir():
            return None
        members = []
        try:
            for entry in proc.iterdir():
                if not entry.name.isdigit():
                    continue
                raw = (entry / "stat").read_text(encoding="ascii")
                fields = raw[raw.rfind(")")+2:].split()
                state, group = fields[0], int(fields[2])
                if group == pgid:
                    members.append((int(entry.name), state))
        except (OSError, ValueError, IndexError):
            return None
        return tuple(members)

    @staticmethod
    def _signal_owned_group(owned: OwnedProcess, sig: int) -> None:
        members = ProcessOwner._group_members(owned.pgid)
        if members is None:
            raise RuntimeError(f"cannot verify owned process group: {owned.name}")
        if not members:
            return
        try:
            if owned.pgid != owned.process.pid:
                raise RuntimeError(f"owned process group identity is invalid: {owned.name}")
            os.killpg(owned.pgid, sig)
        except ProcessLookupError:
            return

    def stop_one(self, owned: OwnedProcess, *, grace_s: float = 5.0) -> dict[str, Any]:
        if owned.stopped:
            return {"name": owned.name, "returncode": owned.process.poll(), "stopped": True}
        result: dict[str, Any] = {"name": owned.name, "returncode": owned.process.poll(),
                                  "stopped": False}
        try:
            self._signal_owned_group(owned, signal.SIGINT)
        except RuntimeError as error:
            result["group_inspection_error"] = str(error)
            return result
        deadline = time.monotonic() + grace_s
        while time.monotonic() < deadline:
            members = self._group_members(owned.pgid)
            if members == ():
                if owned.process.poll() is None:
                    try:
                        result["returncode"] = owned.process.wait(timeout=max(0.01, deadline-time.monotonic()))
                    except subprocess.TimeoutExpired:
                        pass
                owned.stopped = owned.process.poll() is not None
                result.update({"returncode": owned.process.poll(), "stopped": owned.stopped,
                               "group_members": []})
                if not owned.stopped:
                    result["sigint_timeout"] = True
                return result
            if members is None:
                result["group_inspection_error"] = "OWNED_PROCESS_GROUP_STATUS_UNKNOWN"
                return result
            time.sleep(0.02)
        result.update({"sigint_timeout": True, "stopped": False,
                       "group_members": list(self._group_members(owned.pgid) or ())})
        return result

    def stop_all(self, order: Iterable[str] | None = None, *, grace_s: float = 2.0,
                 capture_finalized: Callable[[], bool] = lambda: False) -> list[dict[str, Any]]:
        lookup = {p.name: p for p in self.processes}
        names = tuple(order or reversed([p.name for p in self.processes]))
        results = [self.stop_one(lookup[name], grace_s=grace_s)
                   for name in names if name in lookup]
        pending = {item["name"]: item for item in results if item.get("sigint_timeout")}
        if pending and capture_finalized():
            for name, item in pending.items():
                owned = lookup[name]
                self._signal_owned_group(owned, signal.SIGTERM)
                try:
                    item["returncode"] = owned.process.wait(timeout=2.0)
                except subprocess.TimeoutExpired:
                    item["returncode"] = owned.process.poll()
                members = self._group_members(owned.pgid)
                item["group_members"] = list(members or ())
                item["stopped"] = members == () and owned.process.poll() is not None
                item["sigterm_escalated_after_finalize"] = True
                self.warnings.append(f"{name}: launcher-managed SIGTERM after capture finalize")
                owned.stopped = item["stopped"]
                if not item["stopped"]:
                    self._signal_owned_group(owned, signal.SIGKILL)
                    item["sigkill_required"] = True
                    members = self._group_members(owned.pgid)
                    item["group_members"] = list(members or ())
                    item["stopped"] = members == () and owned.process.poll() is not None
                    owned.stopped = item["stopped"]
        elif pending:
            # Containment targets only the exact process groups this runner
            # created. Missing finalized capture makes A10 fail independently.
            for name, item in pending.items():
                owned = lookup[name]
                self._signal_owned_group(owned, signal.SIGKILL)
                item["sigkill_required"] = True
                members = self._group_members(owned.pgid)
                item["group_members"] = list(members or ())
                item["returncode"] = owned.process.poll()
                item["stopped"] = members == () and item["returncode"] is not None
                owned.stopped = item["stopped"]
        return results


@dataclass
class CampaignState:
    stage: str = "PREFLIGHT"
    facts: dict[str, Any] = field(default_factory=dict)
    primary_failure: dict[str, Any] | None = None
    warnings: list[str] = field(default_factory=list)
    valid_observations: list[dict[str, Any]] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    cleanup: dict[str, Any] = field(default_factory=dict)

    def fail(self, component: str, reason: str, *, logs: list[str] | None = None) -> None:
        if self.primary_failure is None:
            self.primary_failure = {"stage": self.stage, "primary_failure": reason,
                                    "component": component, "short_reason": reason,
                                    "relevant_logs": list(logs or ()),
                                    "bag_time_window": None, "root_cause": "ROOT_CAUSE_UNRESOLVED"}


class ResearchAcceptanceRunner:
    """Orchestrates one authorized runtime invocation and independent cleanup."""

    def __init__(self, *, repository: Path, output_target: Path,
                 authorization_path: Path, partition: str,
                 fuel_cache_root: Path, map_root: Path,
                 now_steady: Callable[[], float] = time.monotonic,
                 process_owner: ProcessOwner | None = None) -> None:
        self.repository = repository.resolve(strict=True)
        self.output_target = output_target.resolve(strict=False)
        self.authorization_path = authorization_path.resolve(strict=True)
        self.partition = partition
        self.fuel_cache_root = fuel_cache_root.resolve(strict=True)
        self.map_root = map_root.resolve(strict=True)
        self.now_steady = now_steady
        self.process_owner = process_owner or ProcessOwner()
        self.state = CampaignState()
        self.started_steady = now_steady()
        self.run_id = self.output_target.name
        self.commit = ""
        self.config_hash = ""
        self.config: dict[str, Any] = {}
        self.map_identity_actual: dict[str, Any] = {}
        self.output: Path | None = None
        self.log_stream: Any = None
        self.observer: Any = None
        self.executor: Any = None
        self.executor_thread: Any = None
        self.rclpy: Any = None
        self.navigation_goal_handle: Any = None
        self.path_snapshot: Any = None
        self.used_pairs: set[tuple[int, int]] = set()
        self.last_progress_arc: float | None = None
        self.action_accept_ns = 0
        self.goal_barrier_sequence = 0
        self.goal_barrier_stamp_ns = 0
        self.authorization: dict[str, Any] = {}
        self.rearm_requested = False
        self.mission_deadline_steady = 0.0
        self.shutdown_results: list[dict[str, Any]] = []
        self.shutdown_completed = False

    def preflight(self) -> None:
        self.state.stage = "PREFLIGHT"
        self.commit, clean, origin = read_git_identity(self.repository)
        if not clean:
            raise AcceptanceFailure("PREFLIGHT", "identity", "SOURCE_WORKTREE_NOT_CLEAN")
        config_path = self.repository / "ros2_ws/src/mecanum_nav_rl/config/v3/resolved/sim_eval_nav2_baseline.resolved.json"
        self.config = load_json(config_path)
        self.config_hash = validate_resolved_config(self.config)
        if not self.partition.strip():
            raise AcceptanceFailure("PREFLIGHT", "partition", "GZ_PARTITION_REQUIRED")
        self.authorization = verify_runtime_authorization(self.authorization_path, commit=self.commit,
                                    config_hash=self.config_hash, run_id=self.run_id,
                                    output_target=self.output_target)
        if self.output_target.exists():
            raise AcceptanceFailure("PREFLIGHT", "output", "OUTPUT_TARGET_ALREADY_EXISTS")
        self.map_identity_actual = verify_canonical_map(self.map_root, self.config["map_identity"])
        # mkdir is the capacity-one claim. The identity is the first artifact,
        # before any runtime child can be started.
        self.output_target.mkdir(parents=False, exist_ok=False)
        self.output = self.output_target
        capture = self.output / "capture"
        capture.mkdir()
        self.log_stream = (self.output / "runtime.log").open("x", encoding="utf-8")
        started = datetime.now(timezone.utc).isoformat()
        identity = {
            "run_id": self.run_id, "decision_id": DECISION_ID,
            "exact_git_commit": self.commit, "repository_url": origin,
            "source_clean": True, "runtime_profile": PROFILE,
            "navigation_mode": MODE, "use_sim_time": True,
            "config_hash": self.config_hash, "dependency_versions": dependency_versions(),
            "map_identity": self.map_identity_actual,
            "world": {"name": WORLD_NAME, "entity": ENTITY_NAME,
                      "fuel_models": FUEL_EXPECTED},
            "domain_id": os.environ.get("ROS_DOMAIN_ID", "DEFAULT"),
            "gz_partition": self.partition,
            "runtime_authorization_reference": str(self.authorization_path),
            "start_time_utc": started,
        }
        atomic_json(self.output / "identity.json", identity)
        atomic_json(self.output / "resolved_config.json", self.config)
        self.log("runner", "identity recorded; runtime children not yet started")

    def log(self, component: str, message: str) -> None:
        if self.log_stream:
            timestamp = datetime.now(timezone.utc).isoformat()
            self.log_stream.write(f"{timestamp} [{component}] {message}\n")
            self.log_stream.flush()

    def deadline_remaining(self) -> float:
        return max(0.0, 480.0 - (self.now_steady() - self.started_steady))

    def _launch(self, package: str, filename: str, args: Mapping[str, str]) -> list[str]:
        return ["ros2", "launch", package, filename,
                *(f"{key}:={value}" for key, value in args.items())]

    def start_runtime_children(self) -> None:
        if self.output is None:
            raise RuntimeError("preflight must create the output target first")
        if self.authorization.get("sim_estop_release_authorized") is not True:
            raise AcceptanceFailure("PREFLIGHT", "authorization", "SIM_ESTOP_RELEASE_AUTHORIZATION_REQUIRED")
        env = dict(os.environ)
        env["GZ_PARTITION"] = self.partition
        env["ROS_DOMAIN_ID"] = env.get("ROS_DOMAIN_ID", "0")
        common = {"initial_pose_map_x": "0", "initial_pose_map_y": "0",
                  "initial_pose_map_yaw": "0"}
        self.process_owner.start("bootstrap", self._launch(
            "ROBOT_URDF_final_description", "sim_eval_nav2_baseline_bootstrap.launch.py",
            {"gz_partition": self.partition, "fuel_cache_root": str(self.fuel_cache_root), **common}),
            env=env, runtime_log=self.log_stream, cwd=self.repository)
        self.process_owner.start("composite", self._launch(
            "mecanum_nav_bringup", "sim_eval_nav2_baseline_system.launch.py",
            {"gz_partition": self.partition, "start_bootstrap": "false",
             "canonical_map_root": str(self.map_root), "fuel_cache_root": str(self.fuel_cache_root),
             "sim_estop_release_authorized": "true", **common}),
            env=env, runtime_log=self.log_stream, cwd=self.repository)
        qos = self.repository / "ros2_ws/src/mecanum_nav_bringup/config/recording/step07_research_qos.yaml"
        bag_command = ["ros2", "bag", "record", "--storage", "sqlite3", "--use-sim-time",
                       "--include-hidden-topics",
                       "--output", str(self.output / "capture" / "step07"),
                       "--qos-profile-overrides-path", str(qos), *CAPTURE_TOPICS]
        self.process_owner.start("recorder", bag_command, env=env,
                                 runtime_log=self.log_stream, cwd=self.repository)

    def start_observer(self) -> None:
        """Create exactly one in-process observer and spin callbacks concurrently."""
        import rclpy
        from rclpy.executors import MultiThreadedExecutor
        from mecanum_nav_rl.observations.step07_research_observer import Step07ResearchObserver
        self.rclpy = rclpy
        if not rclpy.ok():
            rclpy.init(args=None)
        self.observer = Step07ResearchObserver(config_hash=self.config_hash)
        self.executor = MultiThreadedExecutor(num_threads=4)
        self.executor.add_node(self.observer.node)
        import threading
        self.executor_thread = threading.Thread(target=self._spin_executor,
            name="step07-observer-executor", daemon=False)
        self.executor_thread.start()

    def _spin_executor(self) -> None:
        try:
            self.executor.spin()
        except BaseException as error:
            self.observer.executor_error = error

    def _remaining(self, deadline: float) -> float:
        return max(0.0, deadline - self.now_steady())

    def _wait_future(self, future: Any, deadline: float, *, stage: str, component: str) -> Any:
        self._raise_executor_error(stage)
        while not future.done():
            self._raise_executor_error(stage)
            if self._remaining(deadline) <= 0:
                raise AcceptanceFailure(stage, component, "STEADY_DEADLINE_EXPIRED")
            time.sleep(min(0.01, self._remaining(deadline)))
        error = future.exception()
        if error is not None:
            raise AcceptanceFailure(stage, component, f"CALLBACK_EXCEPTION:{type(error).__name__}:{error}")
        return future.result()

    def _wait_for(self, predicate: Callable[[], bool], deadline: float, *,
                  stage: str, component: str, reason: str) -> None:
        while True:
            self._raise_executor_error(stage)
            if predicate():
                return
            if self._remaining(deadline) <= 0:
                raise AcceptanceFailure(stage, component, reason)
            time.sleep(min(0.02, self._remaining(deadline)))

    def _raise_executor_error(self, stage: str | None = None) -> None:
        error = getattr(self.observer, "executor_error", None) if self.observer is not None else None
        if error is not None:
            raise AcceptanceFailure(stage or self.state.stage, "observer_executor",
                                    f"EXECUTOR_EXCEPTION:{type(error).__name__}:{error}")

    def _graph_ready_for_recording(self) -> bool:
        ready, missing = self.observer.recording_ready(CAPTURE_TOPICS)
        if not ready:
            self.log("recorder", f"waiting for recorder subscriptions; missing={','.join(missing[:4])}")
        return ready

    def _topic_samples_ready(self) -> bool:
        observer = self.observer
        if observer.clock_rollback:
            raise AcceptanceFailure("A2_CLOCK_AND_SENSORS", "clock", "SIM_CLOCK_ROLLBACK")
        now_steady = time.monotonic_ns()
        if observer.clock_ns <= 0 or observer.clock_advance_count < 2 or observer.lifecycle is None:
            return False
        life = observer.lifecycle
        ros_age = observer.clock_ns - life.stamp_ns
        if life.value["barrier_state"] == 3:
            raise AcceptanceFailure("STARTUP", "safety_lifecycle", "SAFETY_LIFECYCLE_FAULT")
        if (life.value["primary_state"] != 2
                or life.value["barrier_state"] not in (1, 2)
                or now_steady-life.received_steady_ns > 500_000_000
                or not 0 <= ros_age <= 500_000_000):
            return False
        graph = observer.graph_snapshot()
        incompatible = self._known_qos_mismatches(graph)
        if incompatible:
            raise AcceptanceFailure("A2_CLOCK_AND_SENSORS", "qos",
                                    f"KNOWN_QOS_INCOMPATIBILITY:{','.join(incompatible)}")
        lifecycle_publishers = graph["topics"].get(
            "/mecanum/safety_lifecycle_state", {}).get("publishers", ())
        if len(lifecycle_publishers) != 1 or lifecycle_publishers[0][0] != "safety_lifecycle":
            raise AcceptanceFailure("STARTUP", "safety_lifecycle_owner",
                                    "LIFECYCLE_PUBLISHER_OWNER_MISMATCH")
        if not observer.scans or not observer.wheel or not observer.imu or not observer.odometry:
            return False
        scan = observer.scans[-1].value
        wheel = observer.wheel[-1].value
        imu = observer.imu[-1].value
        odom = observer.odometry[-1].value
        if (observer.scans[-1].frame_id != "lidar_frame" or not scan.ranges
                or wheel.header.frame_id != "odom" or wheel.child_frame_id != "base_link"
                or imu.header.frame_id != "base_link" or odom.header.frame_id != "odom"
                or odom.child_frame_id != "base_link"):
            raise AcceptanceFailure("A2_CLOCK_AND_SENSORS", "sensor_frames", "SENSOR_TYPE_OR_FRAME_INVALID")
        from mecanum_nav_rl.observations.step07_research_acceptance import lidar_sectors
        try:
            lidar_sectors(scan.ranges, angle_min=scan.angle_min,
                angle_increment=scan.angle_increment, range_min=scan.range_min,
                range_max=scan.range_max, frame_id=scan.header.frame_id)
        except (TypeError, ValueError) as error:
            raise AcceptanceFailure("A2_CLOCK_AND_SENSORS", "scan", f"SCAN_INVALID:{error}") from error
        facts = (observer.scans[-1], observer.wheel[-1], observer.imu[-1], observer.odometry[-1])
        limits = (500_000_000, 200_000_000, 200_000_000, 250_000_000)
        return all(0 <= now_steady-f.received_steady_ns <= limit
                   and 0 <= observer.clock_ns-f.stamp_ns <= limit
                   for f, limit in zip(facts, limits))

    def _goal_pose(self) -> Any:
        from geometry_msgs.msg import PoseStamped
        goal = PoseStamped()
        goal.header.frame_id = "map"
        goal.header.stamp = self.observer.node.get_clock().now().to_msg()
        goal.pose.position.x = -4.0
        goal.pose.position.y = 0.0
        goal.pose.orientation.w = 1.0
        return goal

    def _check_launch_processes(self) -> None:
        for child in self.process_owner.processes:
            code = child.process.poll()
            if code is not None:
                raise AcceptanceFailure(self.state.stage, child.name,
                    f"OWNED_LAUNCH_EXITED:{code}")

    def _a1_asset_check(self) -> dict[str, Any]:
        import xml.etree.ElementTree as ET
        world = self.repository / "ros2_ws/src/ROBOT_URDF_final_description/launch/tugbot_depot.sdf"
        if not world.is_file():
            raise AcceptanceFailure("A1_SIMULATOR", "world", "CANONICAL_WORLD_MISSING")
        uris = {e.text.strip() for e in ET.parse(world).getroot().iter("uri") if e.text and "/models/" in e.text}
        expected = {"https://fuel.gazebosim.org/1.0/OpenRobotics/models/Depot",
                    "https://fuel.gazebosim.org/1.0/MovAi/models/Tugbot"}
        if uris != expected:
            raise AcceptanceFailure("A1_SIMULATOR", "world", "CANONICAL_FUEL_URI_SET_MISMATCH")
        fuel_root = self.fuel_cache_root.resolve(strict=True)
        if fuel_root != (Path.home() / ".gz/fuel").resolve(strict=False):
            raise AcceptanceFailure("A1_SIMULATOR", "fuel_cache", "FUEL_CACHE_ROOT_NOT_CANONICAL")
        resolved_fuel = {}
        for identity, version in FUEL_EXPECTED.items():
            owner, model = identity.split("/", 1)
            model_root = fuel_root / "fuel.gazebosim.org" / owner.lower() / "models" / model.lower()
            version_root = model_root / version.removeprefix("v")
            if not version_root.is_dir() or not (version_root / "model.config").is_file() \
                    or not (version_root / "model.sdf").is_file():
                raise AcceptanceFailure("A1_SIMULATOR", "fuel_cache", f"EXPECTED_FUEL_ASSET_MISSING:{identity}:{version}")
            resolved_fuel[identity] = {"version": version, "path": str(version_root)}
        map_identity = verify_canonical_map(self.map_root, self.config["map_identity"])
        return {"pass": True, "reason": "CANONICAL_WORLD_ASSET_SELECTION",
                "measured": {"world": str(world), "world_name": WORLD_NAME,
                             "entity_name": ENTITY_NAME, "fuel_models": resolved_fuel,
                             "map_identity": map_identity}}

    def _wait_ready(self) -> None:
        self.state.stage = "STARTUP"
        a1_assets = self._a1_asset_check()
        start = self.now_steady()
        deadline = min(start + 150.0, self.started_steady + 460.0)
        self._wait_for(lambda: self._topic_samples_ready(), deadline, stage="A2_CLOCK_AND_SENSORS",
                       component="observer", reason="CLOCK_SENSOR_OR_LIFECYCLE_READINESS_TIMEOUT")
        self._check_launch_processes()
        self.state.facts["A1"] = {**a1_assets,
            "reason": "CANONICAL_SIMULATOR_STARTED_AND_ASSETS_VERIFIED",
            "measured": {**a1_assets.get("measured", {}),
                         "clock_ns": self.observer.clock_ns,
                         "clock_advances": self.observer.clock_advance_count}}
        self.state.facts["A2"] = {"pass": True, "reason": "CLOCK_AND_REQUIRED_SENSORS_FRESH",
            "measured": {"clock_ns": self.observer.clock_ns,
                         "clock_advances": self.observer.clock_advance_count,
                         "scan_age_ms": (time.monotonic_ns()-self.observer.scans[-1].received_steady_ns)//1_000_000,
                         "wheel_age_ms": (time.monotonic_ns()-self.observer.wheel[-1].received_steady_ns)//1_000_000,
                         "imu_age_ms": (time.monotonic_ns()-self.observer.imu[-1].received_steady_ns)//1_000_000}}
        odoms = tuple(self.observer.odometry)
        advancing = len(odoms) >= 2 and odoms[-1].stamp_ns > odoms[-2].stamp_ns
        valid = advancing and all(
            x.value.header.frame_id == "odom" and x.value.child_frame_id == "base_link"
            and all(math.isfinite(v) for v in (x.value.pose.pose.position.x,
                x.value.pose.pose.position.y, x.value.twist.twist.linear.x,
                x.value.twist.twist.linear.y, x.value.twist.twist.angular.z,
                *x.value.pose.covariance, *x.value.twist.covariance)) for x in odoms[-2:])
        if not valid:
            raise AcceptanceFailure("A3_EKF_ODOMETRY", "filtered_odometry", "FILTERED_ODOMETRY_INVALID")
        graph = self.observer.graph_snapshot()
        odom_publishers = graph["topics"].get("/odometry/filtered", {}).get("publishers", ())
        if len(odom_publishers) != 1 or "ekf" not in odom_publishers[0][0].lower():
            raise AcceptanceFailure("A3_EKF_ODOMETRY", "graph", "EKF_ODOMETRY_OWNER_MISMATCH")
        self.state.facts["A3"] = {"pass": True, "reason": "EKF_FILTERED_ODOMETRY_ADVANCING",
            "measured": {"samples": len(odoms), "frame_id": "odom", "child_frame_id": "base_link"}}

        nodes = graph["nodes"]
        required = {"map_server", "amcl", "planner_server", "controller_server",
                    "behavior_server", "bt_navigator"}
        if not required.issubset(nodes):
            raise AcceptanceFailure("A6_NAV2", "ros_graph", "REQUIRED_NAV2_NODES_MISSING")
        self._wait_for(lambda: self.observer.wait_for_actions(timeout_sec=0.1), deadline,
            stage="A6_NAV2", component="action_servers", reason="NAV2_ACTION_SERVER_UNAVAILABLE")
        lifecycle_futures = self.observer.query_lifecycle_states()
        lifecycle_active = {}
        for name, future in lifecycle_futures.items():
            response = self._wait_future(future, deadline, stage="A6_NAV2", component=f"{name}_lifecycle")
            lifecycle_active[name] = int(response.current_state.id) == 3
        if not all(lifecycle_active.values()):
            raise AcceptanceFailure("A6_NAV2", "lifecycle", "REQUIRED_NAV2_NODE_NOT_ACTIVE")
        self.state.facts["A6"] = {"pass": True, "reason": "NAV2_NODES_AND_ACTION_SERVERS_READY",
                                  "measured": {"nodes": sorted(required)}}
        self.state.stage = "A5_LOCALIZATION"
        localization_ok, localization_reason = self._localization_ok()
        if not localization_ok:
            self._wait_for(lambda: self._localization_ok()[0], deadline, stage="A5_LOCALIZATION",
                           component="amcl", reason=localization_reason or "LOCALIZATION_NOT_HEALTHY")
        self.state.facts["A5"] = {"pass": True, "reason": "AMCL_LOCALIZATION_HEALTH_VALID",
            "measured": {"samples": len(self.observer.localization), "map_id": self.config["map_identity"]["map_id"]}}
        # Required TF edges are checked at the same fresh filtered-odometry stamps.
        self.state.stage = "A4_TF"
        self._wait_for(lambda: self._tf_chain_usable(self.observer.odometry[-1].stamp_ns), deadline,
            stage="A4_TF", component="tf2", reason="REQUIRED_TF_CHAIN_UNAVAILABLE_AT_SENSOR_STAMP")
        owner_map = self._observed_tf_owners()
        self.state.facts["A4"] = {"pass": True, "reason": "TF_CHAIN_AVAILABLE_AT_SENSOR_TIMESTAMP",
            "measured": {"edges": ["map->odom", "odom->base_link", "base_link->lidar_frame"],
                         "owners": owner_map}}
        self._startup_rearm(deadline)

    def _startup_rearm(self, deadline: float) -> None:
        if self.authorization.get("sim_estop_release_authorized") is not True:
            raise AcceptanceFailure("STARTUP", "authorization", "SIM_ESTOP_RELEASE_AUTHORIZATION_REQUIRED")
        if self.rearm_requested:
            raise AcceptanceFailure("STARTUP", "safety_lifecycle", "STARTUP_REARM_ALREADY_REQUESTED")
        self.rearm_requested = True
        rearm_future = self.observer.request_rearm()
        rearm_response = self._wait_future(rearm_future, deadline, stage="STARTUP_REARM",
                                           component="safety_rearm")
        if not rearm_response.success:
            raise AcceptanceFailure("STARTUP_REARM", "safety_rearm", "SAFETY_REARM_REFUSED")
        self._wait_for(lambda: self._lifecycle_ready(), deadline, stage="STARTUP_REARM",
            component="safety_lifecycle", reason="SAFETY_READY_AFTER_REARM_TIMEOUT")

    def _lifecycle_ready(self) -> bool:
        life = self.observer.lifecycle
        if life is None:
            return False
        now_steady = time.monotonic_ns()
        return (life.context == self.observer.context and life.value["primary_state"] == 2
            and life.value["barrier_state"] == 1 and life.value["motion_permitted"]
            and 0 <= now_steady-life.received_steady_ns <= 500_000_000
            and 0 <= self.observer.clock_ns-life.stamp_ns <= 500_000_000)

    def _localization_ok(self) -> tuple[bool, str | None]:
        from mecanum_nav_rl.observations.step07_research_acceptance import localization_health
        now_ros = self.observer.clock_ns
        if now_ros <= 0:
            return False, "CLOCK_NOT_POSITIVE"
        return localization_health(tuple(self.observer.localization), now_ros_ns=now_ros,
            max_age_ns=2_000_000_000, now_steady_ns=time.monotonic_ns(), max_covariance=0.25)

    def _tf_chain_usable(self, stamp_ns: int) -> bool:
        try:
            for target, source in (("map", "odom"), ("odom", "base_link"),
                                   ("base_link", "lidar_frame")):
                self.observer.lookup_transform(target, source, stamp_ns)
            return True
        except Exception:
            return False

    def _observed_tf_owners(self) -> dict[str, str]:
        expected = {("map", "odom"): "amcl",
                    ("odom", "base_link"): "ekf_filter_node",
                    ("base_link", "lidar_frame"): "robot_state_publisher"}
        observed: dict[str, str] = {}
        for edge, owner in expected.items():
            owners = self.observer.tf_edge_owners.get(edge, set())
            normalized = {str(name).strip("/").lower() for name in owners}
            if normalized != {owner}:
                raise AcceptanceFailure("A4_TF", "tf_publishers",
                    f"TF_EDGE_OWNER_MISMATCH:{edge[0]}->{edge[1]}:{sorted(normalized)}")
            observed[f"{edge[0]}->{edge[1]}"] = next(iter(owners))
        return observed

    def _send_one_plan(self) -> None:
        from mecanum_nav_rl.observations.step07_research_acceptance import PathSnapshot
        self.state.stage = "A6_NAV2_PLAN"
        if not self.observer.wait_for_actions(timeout_sec=min(1.0, self.deadline_remaining())):
            raise AcceptanceFailure("A6_NAV2", "action_servers", "NAV2_ACTION_SERVER_UNAVAILABLE")
        goal = self._goal_pose()
        sent_ns = self.observer.node.get_clock().now().nanoseconds
        future = self.observer.send_compute_path(goal, request_stamp=goal.header.stamp)
        response = self._wait_future(future, self.started_steady+460.0,
                                     stage="A6_NAV2", component="compute_path_send")
        if not response.accepted:
            raise AcceptanceFailure("A6_NAV2", "compute_path", "COMPUTE_PATH_REQUEST_REJECTED")
        path_result = self._wait_future(response.get_result_async(), self.started_steady+460.0,
                                        stage="A6_NAV2", component="compute_path_result")
        if path_result.status != 4:
            raise AcceptanceFailure("A6_NAV2", "compute_path", "COMPUTE_PATH_RESULT_NOT_SUCCEEDED")
        path = path_result.result.path
        if not path.poses or path.header.frame_id != "map":
            raise AcceptanceFailure("A6_NAV2", "compute_path", "PATH_EMPTY_OR_FRAME_INVALID")
        poses = tuple((float(p.pose.position.x), float(p.pose.position.y)) for p in path.poses)
        if not all(math.isfinite(x) and math.isfinite(y) for x, y in poses):
            raise AcceptanceFailure("A6_NAV2", "compute_path", "PATH_NONFINITE")
        req_id = str(uuid.uuid4())
        life = self.observer.lifecycle
        if life is None or life.context != self.observer.context:
            raise AcceptanceFailure("A6_NAV2", "context", "LIFECYCLE_CONTEXT_INVALID")
        self.path_snapshot = PathSnapshot(poses_xy=poses, request_id=req_id,
            goal_xy=(-4.0, 0.0), context=life.context,
            map_id=self.map_identity_actual["map_id"],
            map_content_hash=self.map_identity_actual["map_content_hash"],
            received_steady_ns=time.monotonic_ns(),
            expires_steady_ns=int((self.started_steady+460.0)*1_000_000_000))
        self.state.facts["A6"] = {"pass": True, "reason": "COMPUTE_PATH_SUCCEEDED_AND_NAV_GOAL_ACCEPTED_PENDING",
                                   "measured": {"path_pose_count": len(poses), "request_id": req_id}}

    def _lookup_local_reference(self, odom_stamp_ns: int, odom_receive_ns: int,
                                cutoff_ns: int, deadline: float) -> tuple[tuple[float, float, float], float, int] | None:
        from mecanum_nav_rl.observations.step07_research_acceptance import (
            PathSnapshot, project_lookahead, transform_map_path_to_base,
        )
        from rclpy.time import Time
        pending_deadline = min(self.now_steady()+0.200, deadline)
        tf = None
        tf_error: str | None = None
        query = Time(nanoseconds=odom_stamp_ns, clock_type=self.rclpy.clock.ClockType.ROS_TIME)
        while tf is None and self.now_steady() < pending_deadline:
            try:
                tf = self.observer.tf_buffer.lookup_transform("base_link", "map", query,
                    timeout=self.observer._Duration(seconds=0.0))
            except Exception:
                tf_error = "exact-time lookup unavailable"
                time.sleep(0.005)
        if (tf is None or self.observer.clock_ns < cutoff_ns or self.observer.clock_rollback
                or self._remaining(deadline) <= 0 or self.observer.context != self.path_snapshot.context
                or self.observer.lifecycle is None):
            self.log("tf", f"local reference unavailable: stamp={odom_stamp_ns} cutoff={cutoff_ns} error={tf_error}")
            return None
        now_steady = time.monotonic_ns()
        lifecycle = self.observer.lifecycle
        if (not 0 <= now_steady-odom_receive_ns <= 250_000_000
                or not 0 <= now_steady-lifecycle.received_steady_ns <= 500_000_000
                or not 0 <= self.observer.clock_ns-lifecycle.stamp_ns <= 500_000_000
                or lifecycle.context != self.path_snapshot.context
                or lifecycle.value["primary_state"] != 2
                or lifecycle.value["barrier_state"] != 1
                or not lifecycle.value["motion_permitted"]):
            self.log("tf", "local reference rejected: stale odometry/lifecycle or invalid context")
            return None
        tr = tf.transform.translation
        q = tf.transform.rotation
        poses_base = transform_map_path_to_base(self.path_snapshot.poses_xy,
            translation=(tr.x, tr.y, tr.z), rotation_xyzw=(q.x, q.y, q.z, q.w))
        path = PathSnapshot(poses_base, self.path_snapshot.request_id, self.path_snapshot.goal_xy,
            self.path_snapshot.map_id, self.path_snapshot.map_content_hash,
            self.path_snapshot.context, self.path_snapshot.received_steady_ns,
            min(self.path_snapshot.expires_steady_ns, int(deadline*1_000_000_000)))
        try:
            progress, distance_feature, bearing = project_lookahead(path, robot_xy=(0.0,0.0),
                previous_arc_m=self.last_progress_arc, now_steady_ns=time.monotonic_ns())
        except ValueError as error:
            self.log("observation", f"local reference unavailable: {error}")
            return None
        committed_steady = time.monotonic_ns()
        if (committed_steady-odom_receive_ns > 250_000_000
                or self._remaining(deadline) <= 0 or self.observer.context != self.path_snapshot.context
                or self.observer.barrier_sequence != self.goal_barrier_sequence
                or self.observer.clock_rollback):
            self.log("tf", "local reference expired before commit")
            return None
        return ((distance_feature, math.sin(bearing), math.cos(bearing)),
                progress, committed_steady)

    def _mission_lifecycle_valid(self, context: Any, now_steady_ns: int) -> bool:
        life = self.observer.lifecycle
        if life is None or life.context != context or self.observer.context != context:
            return False
        return (life.value["primary_state"] == 2 and life.value["barrier_state"] == 1
            and life.value["motion_permitted"]
            and 0 <= now_steady_ns-life.received_steady_ns <= 500_000_000
            and 0 <= self.observer.clock_ns-life.stamp_ns <= 500_000_000)

    def _assert_live_mission_health(self, context: Any, stage: str) -> None:
        observer = self.observer
        if observer.clock_rollback or observer.clock_ns <= 0:
            raise AcceptanceFailure(stage, "clock", "SIM_CLOCK_INVALID_OR_ROLLED_BACK")
        now_ros, now_steady = observer.clock_ns, time.monotonic_ns()
        if not self._mission_lifecycle_valid(context, now_steady):
            raise AcceptanceFailure(stage, "safety_lifecycle", "LIFECYCLE_NOT_READY_OR_STALE")
        required = ((observer.scans, 500_000_000, "scan"),
                    (observer.wheel, 200_000_000, "wheel_odometry"),
                    (observer.imu, 200_000_000, "imu"),
                    (observer.odometry, 250_000_000, "filtered_odometry"))
        for stream, limit, name in required:
            if not stream:
                raise AcceptanceFailure(stage, name, f"{name.upper()}_MISSING")
            fact = stream[-1]
            if (fact.context != context or not 0 <= now_steady-fact.received_steady_ns <= limit
                    or not 0 <= now_ros-fact.stamp_ns <= limit):
                raise AcceptanceFailure(stage, name, f"{name.upper()}_STALE_OR_WRONG_CONTEXT")

    def _collect_one_observation(self, deadline: float) -> bool:
        from mecanum_nav_rl.observations.step07_research_acceptance import (
            make_observation, select_actual_receipt, select_scan_odom_pair,
        )
        observer = self.observer
        self._assert_live_mission_health(self.path_snapshot.context, "A7_OBSERVATION")
        cutoff = observer.node.get_clock().now().nanoseconds
        if cutoff <= 0 or observer.context != self.path_snapshot.context:
            raise AcceptanceFailure("A7_OBSERVATION", "context_or_clock", "INVALID_OBSERVATION_CONTEXT")
        if (observer.barrier_sequence != self.goal_barrier_sequence
                or observer.barrier_stamp_ns != self.goal_barrier_stamp_ns):
            raise AcceptanceFailure("A7_OBSERVATION", "lifecycle", "LIFECYCLE_BARRIER_CHANGED_DURING_MISSION")
        barrier_ns = max(self.action_accept_ns, self.goal_barrier_stamp_ns)
        now_steady = time.monotonic_ns()
        pair = select_scan_odom_pair(tuple(observer.scans), tuple(observer.odometry),
            cutoff_ns=cutoff, now_steady_ns=now_steady, scan_freshness_ns=500_000_000,
            odom_freshness_ns=250_000_000, sync_tolerance_ns=50_000_000,
            scan_barrier_ns=barrier_ns, odom_barrier_ns=barrier_ns,
            context=self.path_snapshot.context, used_pairs=self.used_pairs, now_ros_ns=cutoff)
        if pair is None:
            return False
        scan_fact, odom_fact = pair
        receipt = select_actual_receipt(tuple(observer.receipts), cutoff_ns=cutoff,
            now_steady_ns=time.monotonic_ns(), freshness_ns=500_000_000,
            after_barrier_ns=barrier_ns, context=self.path_snapshot.context, now_ros_ns=cutoff)
        if receipt is None:
            return False
        pinned_context = self.path_snapshot.context
        if (observer.context != pinned_context or observer.barrier_sequence != self.goal_barrier_sequence
                or observer.barrier_stamp_ns != self.goal_barrier_stamp_ns):
            raise AcceptanceFailure("A7_OBSERVATION", "lifecycle", "LIFECYCLE_CONTEXT_CHANGED_DURING_MISSION")
        if not self._mission_lifecycle_valid(pinned_context, time.monotonic_ns()):
            raise AcceptanceFailure("A7_OBSERVATION", "safety_lifecycle", "LIFECYCLE_NOT_READY_OR_STALE")
        pre_tf_now_steady = time.monotonic_ns()
        if (scan_fact.frame_id != "lidar_frame" or odom_fact.frame_id != "base_link"
                or odom_fact.value.header.frame_id != "odom"
                or odom_fact.value.child_frame_id != "base_link"
                or scan_fact.context != pinned_context or odom_fact.context != pinned_context
                or receipt.context != pinned_context
                or not 0 <= cutoff-scan_fact.stamp_ns <= 500_000_000
                or not 0 <= cutoff-odom_fact.stamp_ns <= 250_000_000
                or not 0 <= cutoff-receipt.stamp_ns <= 500_000_000
                or not 0 <= pre_tf_now_steady-scan_fact.received_steady_ns <= 500_000_000
                or not 0 <= pre_tf_now_steady-odom_fact.received_steady_ns <= 250_000_000
                or not 0 <= pre_tf_now_steady-receipt.received_steady_ns <= 500_000_000
                or self._remaining(deadline) <= 0):
            return False
        try:
            lidar_sectors(scan_fact.value.ranges, angle_min=scan_fact.value.angle_min,
                angle_increment=scan_fact.value.angle_increment, range_min=scan_fact.value.range_min,
                range_max=scan_fact.value.range_max, frame_id=scan_fact.frame_id)
        except (TypeError, ValueError) as error:
            self.state.facts["rejected_observations"] = self.state.facts.get("rejected_observations", 0)+1
            reasons = self.state.facts.setdefault("rejection_reasons", {})
            reasons[str(error)] = reasons.get(str(error), 0)+1
            return False
        reference_result = self._lookup_local_reference(odom_fact.stamp_ns, odom_fact.received_steady_ns,
                                                        cutoff, deadline)
        if reference_result is None:
            if (observer.context != pinned_context
                    or observer.barrier_sequence != self.goal_barrier_sequence
                    or observer.barrier_stamp_ns != self.goal_barrier_stamp_ns
                    or observer.clock_rollback):
                raise AcceptanceFailure("A7_OBSERVATION", "lifecycle",
                                        "LIFECYCLE_OR_CLOCK_CONTEXT_CHANGED_DURING_TF_LOOKUP")
            return False
        reference, progress, reference_receive_ns = reference_result
        now_steady = time.monotonic_ns()
        self._assert_live_mission_health(pinned_context, "A7_OBSERVATION")
        if (observer.context != pinned_context or observer.barrier_sequence != self.goal_barrier_sequence
                or observer.barrier_stamp_ns != self.goal_barrier_stamp_ns):
            raise AcceptanceFailure("A7_OBSERVATION", "lifecycle",
                                    "LIFECYCLE_BARRIER_CHANGED_DURING_TF_LOOKUP")
        if (observer.context != pinned_context or observer.barrier_sequence != self.goal_barrier_sequence
                or observer.barrier_stamp_ns != self.goal_barrier_stamp_ns or observer.clock_rollback
                or not 0 <= now_steady-scan_fact.received_steady_ns <= 500_000_000
                or not 0 <= now_steady-odom_fact.received_steady_ns <= 250_000_000
                or not 0 <= now_steady-receipt.received_steady_ns <= 500_000_000
                or not 0 <= observer.clock_ns-scan_fact.stamp_ns <= 500_000_000
                or not 0 <= observer.clock_ns-odom_fact.stamp_ns <= 250_000_000
                or not 0 <= observer.clock_ns-receipt.stamp_ns <= 500_000_000
                or not self._mission_lifecycle_valid(pinned_context, now_steady)
                or self._remaining(deadline) <= 0):
            return False
        scan = scan_fact.value
        odom = odom_fact.value
        try:
            vector = make_observation(scan.ranges, scan_angle_min=scan.angle_min,
                scan_angle_increment=scan.angle_increment, scan_range_min=scan.range_min,
                scan_range_max=scan.range_max, scan_frame=scan.header.frame_id,
                reference_features=reference,
                measured_twist=(odom.twist.twist.linear.x, odom.twist.twist.linear.y,
                                odom.twist.twist.angular.z),
                previous_final_command=receipt.value["command"],
                twist_scales=(0.25,0.20,0.80), context=pinned_context)
        except ValueError as error:
            self.state.facts["rejected_observations"] = self.state.facts.get("rejected_observations", 0)+1
            reasons = self.state.facts.setdefault("rejection_reasons", {})
            reasons[str(error)] = reasons.get(str(error), 0)+1
            return False
        record = {"vector": vector.tolist(), "dtype": "float32", "shape": [81],
                  "scan_stamp_ns": scan_fact.stamp_ns, "odom_stamp_ns": odom_fact.stamp_ns,
                  "reference_stamp_ns": odom_fact.stamp_ns,
                  "snapshot_cutoff_ros_ns": cutoff, "tf_query_stamp_ros_ns": odom_fact.stamp_ns,
                  "scan_receive_steady_ns": scan_fact.received_steady_ns,
                  "odom_receive_steady_ns": odom_fact.received_steady_ns,
                  "reference_receive_steady_ns": reference_receive_ns,
                  "receipt_stamp_ns": receipt.stamp_ns,
                  "receipt_receive_steady_ns": receipt.received_steady_ns,
                  "receipt_sequence": receipt.value["final_publish_sequence"],
                  "context": {"episode_generation": receipt.context.episode_generation,
                      "reset_epoch": receipt.context.reset_epoch,
                      "runtime_generation": receipt.context.runtime_generation},
                  "barrier_sequence": observer.barrier_sequence,
                  "config_hash": self.config_hash}
        self.state.valid_observations.append(record)
        self.last_progress_arc = progress
        return True

    @staticmethod
    def _known_qos_mismatches(graph: Mapping[str, Any]) -> tuple[str, ...]:
        """Reject known reliability/durability incompatibility; unknown is undecided."""
        from mecanum_nav_rl.observations.step07_research_acceptance import qos_endpoints_compatible

        required = {"/scan", "/wheel/odometry_raw", "/imu/data", "/odometry/filtered",
                    "/tf", "/tf_static", "/mecanum/safety_lifecycle_state",
                    "/mecanum/safety_state", "/mecanum/nav2_candidate_cmd",
                    "/mecanum/safety_accepted_cmd", "/cmd_vel",
                    "/mecanum/final_issued_command"}
        incompatible: list[str] = []
        for topic in sorted(required):
            facts = graph.get("topics", {}).get(topic, {})
            for publisher in facts.get("publishers", ()):
                for subscription in facts.get("subscriptions", ()):
                    if len(publisher) < 6 or len(subscription) < 6:
                        continue
                    if not qos_endpoints_compatible(publisher[3], publisher[4],
                                                    subscription[3], subscription[4]):
                        incompatible.append(topic)
                        break
                if topic in incompatible:
                    break
        return tuple(incompatible)

    def _mission(self) -> None:
        self._send_one_plan()
        goal = self._goal_pose()
        sent_steady = self.now_steady()
        result_deadline = min(sent_steady+240.0, self.started_steady+460.0)
        self.mission_deadline_steady = result_deadline
        nav_future = self.observer.send_navigation(goal)
        response = self._wait_future(nav_future, result_deadline, stage="A9_NAVIGATION_OUTCOME",
                                     component="navigate_to_pose_send")
        if not response.accepted:
            raise AcceptanceFailure("A9_NAVIGATION_OUTCOME", "navigate_to_pose", "NAVIGATE_GOAL_REJECTED")
        self.navigation_goal_handle = response
        self.action_accept_ns = self.observer.node.get_clock().now().nanoseconds
        self.goal_barrier_sequence = self.observer.barrier_sequence
        self.goal_barrier_stamp_ns = self.observer.barrier_stamp_ns
        self.log("navigate", f"accepted goal_uuid={bytes(response.goal_id.uuid).hex()}")
        from dataclasses import replace
        self.path_snapshot = replace(self.path_snapshot,
            expires_steady_ns=int(result_deadline*1_000_000_000))
        self.state.facts["A6"] = {"pass": True, "reason": "PATH_SUCCEEDED_AND_NAVIGATE_GOAL_ACCEPTED",
            "measured": {"path_pose_count": len(self.path_snapshot.poses_xy),
                         "goal_uuid": bytes(response.goal_id.uuid).hex()}}
        result_future = response.get_result_async()
        self.state.stage = "A7_OBSERVATION"
        overall_sample_deadline = min(self.started_steady+460.0, sent_steady+240.0)
        action_result = None
        while self._remaining(overall_sample_deadline) > 0:
            self._raise_executor_error("A7_OBSERVATION")
            if len(self.state.valid_observations) < 5:
                self._collect_one_observation(overall_sample_deadline)
            self._command_chain_fact()
            if result_future.done():
                action_result = result_future.result()
                break
            self._check_launch_processes()
            time.sleep(0.01)
        if action_result is None:
            self.state.facts["A9"] = {"pass": False, "reason": "NAVIGATION_DEADLINE_OR_NO_RESULT"}
            self.state.stage = "A9_NAVIGATION_OUTCOME"
            self.state.fail("navigate_to_pose", "NAVIGATION_DEADLINE_OR_NO_RESULT")
        else:
            self.log("navigate", f"result status={action_result.status}")
            self.state.facts["A9"] = self._navigation_outcome(action_result)
        if len(self.state.valid_observations) < 5:
            sample_deadline = min(self.started_steady+460.0, self.now_steady()+20.0)
            while len(self.state.valid_observations) < 5 and self._remaining(sample_deadline) > 0:
                self._collect_one_observation(sample_deadline)
                time.sleep(0.01)
        self.state.facts["A7"] = {"pass": len(self.state.valid_observations) >= 5,
            "reason": "FIVE_VALID_OBSERVATIONS" if len(self.state.valid_observations) >= 5 else "VALID_OBSERVATION_COUNT_BELOW_FIVE",
            "measured": {"valid_count": len(self.state.valid_observations)}}
        self.state.valid_observations = self.state.valid_observations[:5]
        self.state.facts["A8"] = self._command_chain_fact()

    def _navigation_outcome(self, action_result: Any) -> dict[str, Any]:
        status = int(action_result.status)
        if status != 4:
            return {"pass": False, "reason": f"NAVIGATION_ACTION_TERMINAL_STATUS_{status}",
                    "measured": {"status": status}}
        result = action_result.result
        pose = self.observer.localization[-1] if self.observer.localization else None
        odom = self.observer.odometry[-1].value if self.observer.odometry else None
        health, reason = self._localization_ok()
        if pose is None or odom is None:
            return {"pass": False, "reason": "NAVIGATION_RESULT_MISSING_POSE_OR_ODOMETRY"}
        x, y, _ = pose["pose"]
        linear = math.hypot(odom.twist.twist.linear.x, odom.twist.twist.linear.y)
        angular = abs(odom.twist.twist.angular.z)
        settled = self._wait_for_settle(min(self.now_steady()+20.0,
            self.mission_deadline_steady, self.started_steady+460.0))
        pose = self.observer.localization[-1] if self.observer.localization else pose
        odom = self.observer.odometry[-1].value if self.observer.odometry else odom
        health, reason = self._localization_ok()
        x, y, _ = pose["pose"]
        linear = math.hypot(odom.twist.twist.linear.x, odom.twist.twist.linear.y)
        angular = abs(odom.twist.twist.angular.z)
        passed = (status == 4 and math.hypot(x+4.0,y) <= 0.15 and linear <= 0.03
                  and angular <= 0.05 and health and settled)
        reason_value = "NAVIGATION_SUCCEEDED_SETTLED" if passed else (
            reason or "NAVIGATION_TERMINAL_OR_SETTLE_CRITERION_FAILED")
        self.state.metrics.update({"navigation_result_status": status,
            "final_position_error_m": math.hypot(x+4.0,y), "final_linear_speed_mps": linear,
            "final_angular_speed_radps": angular})
        return {"pass": passed, "reason": reason_value,
                "measured": {"status": status, "position_error_m": math.hypot(x+4.0,y),
                    "linear_speed_mps": linear, "angular_speed_radps": angular,
                    "localization_health": health, "settled": settled}}

    def _wait_for_settle(self, deadline: float) -> bool:
        """Observe advancing fresh AMCL/filtered-odom facts for one ROS second."""
        start_ros_ns = None
        last_pair = None
        while self._remaining(deadline) > 0 and self.observer.clock_ns > 0:
            if self.observer.clock_rollback:
                return False
            if not self.observer.localization or not self.observer.odometry:
                time.sleep(0.02); continue
            loc = self.observer.localization[-1]
            odom_fact = self.observer.odometry[-1]
            odom = odom_fact.value
            now_ros = self.observer.clock_ns
            now_steady = time.monotonic_ns()
            healthy, _ = self._localization_ok()
            pose = loc["pose"]
            linear = math.hypot(odom.twist.twist.linear.x, odom.twist.twist.linear.y)
            angular = abs(odom.twist.twist.angular.z)
            ok = (healthy and math.hypot(pose[0]+4.0, pose[1]) <= 0.15
                  and linear <= 0.03 and angular <= 0.05
                  and now_steady-loc["received_steady_ns"] <= 2_000_000_000
                  and now_steady-odom_fact.received_steady_ns <= 250_000_000)
            pair = (loc["stamp_ns"], odom_fact.stamp_ns)
            if not ok:
                start_ros_ns = None
            elif pair != last_pair:
                if start_ros_ns is None:
                    start_ros_ns = now_ros
                elif now_ros-start_ros_ns >= 1_000_000_000:
                    return True
                last_pair = pair
            time.sleep(0.02)
        return False

    def _command_chain_fact(self) -> dict[str, Any]:
        retained = self.state.facts.get("command_chain_episode")
        if isinstance(retained, Mapping):
            return dict(retained)
        graph = self.observer.graph_snapshot()
        publishers = graph["topics"].get("/cmd_vel", {}).get("publishers", ())
        candidates = tuple(self.observer.nav2_candidates)
        envelopes = tuple(self.observer.accepted_envelopes)
        receipts = tuple(self.observer.receipts)
        commands = tuple(self.observer.cmd_vel_commands)
        safety_states = tuple(self.observer.safety_states)
        nonzero = lambda c: all(math.isfinite(float(v)) for v in c) and any(abs(float(v)) > 1e-6 for v in c)
        sole = (len(publishers) == 1
                and publishers[0][0].lower() == "final_twist_publisher")
        context = self.path_snapshot.context if self.path_snapshot is not None else None
        for receipt in reversed(receipts):
            rv = receipt.value
            if (receipt.context != context or rv.get("source") != 2
                    or not nonzero(rv.get("command", ()))
                    or type(rv.get("final_publish_sequence")) is not int
                    or rv["final_publish_sequence"] <= 0
                    or type(rv.get("publisher_instance")) is not int
                    or rv["publisher_instance"] <= 0):
                continue
            for envelope in reversed(envelopes):
                ev = envelope.value
                if (envelope.context != receipt.context or ev.get("source") != rv.get("source")
                        or ev.get("sequence") != rv.get("sequence")
                        or ev.get("source_instance_id") != rv.get("source_instance_id")
                        or tuple(ev.get("command", ())) != tuple(rv["command"])
                        or not (0 < envelope.stamp_ns <= receipt.stamp_ns)):
                    continue
                matching_safety = [s for s in safety_states
                    if s.context == receipt.context
                    and s.value.get("active_command_source") == 2
                    and s.value.get("command_valid") is True
                    and s.value.get("motion_permitted") is True
                    and tuple(s.value.get("final_command", ())) == tuple(ev["command"])
                    and 0 < s.stamp_ns <= receipt.stamp_ns
                    and abs(s.stamp_ns-envelope.stamp_ns) <= 500_000_000]
                matching_cmd = [c for c in commands
                    if c.context == receipt.context
                    and tuple(c.value) == tuple(rv["command"])
                    and abs(c.received_steady_ns-receipt.received_steady_ns) <= 250_000_000]
                matching_candidate = [c for c in candidates
                    if c.context == receipt.context and nonzero(c.value)
                    and 0 <= envelope.received_steady_ns-c.received_steady_ns <= 500_000_000]
                if matching_safety and matching_cmd and matching_candidate and sole:
                    episode = {"pass": True, "reason": "NAV2_SAFETY_FINAL_RECEIPT_CHAIN",
                        "measured": {"cmd_vel_publishers": [p[0] for p in publishers],
                            "candidate_command": list(matching_candidate[-1].value),
                            "safety_decision_command": list(matching_safety[-1].value["final_command"]),
                            "accepted_envelope_command": list(ev["command"]),
                            "actual_cmd_vel": list(matching_cmd[-1].value),
                            "receipt_command": list(rv["command"]),
                            "sequence": rv["sequence"],
                            "source_instance_id": rv["source_instance_id"],
                            "final_publish_sequence": rv["final_publish_sequence"],
                            "receipt_stamp_ns": receipt.stamp_ns}}
                    self.state.facts["command_chain_episode"] = episode
                    return episode
        return {"pass": False, "reason": "COMMAND_CHAIN_NOT_CORRELATED",
            "measured": {"cmd_vel_publishers": [p[0] for p in publishers],
                "nonzero_nav2_candidate": any(x.context == context and nonzero(x.value) for x in candidates),
                "actual_cmd_vel_observed": bool(commands),
                "matched_envelope_receipt": False}}

    def _safe_stop(self) -> bool:
        if self.observer is None:
            return False
        try:
            if self.navigation_goal_handle is not None:
                result_future = self.navigation_goal_handle.get_result_async()
                if not result_future.done():
                    cancel_future = self.navigation_goal_handle.cancel_goal_async()
                    self._wait_future(cancel_future, self.now_steady()+2.0,
                        stage="A10_SHUTDOWN", component="navigate_cancel")
                    self.log("navigate", "cancel requested during shutdown")
            request_ros_ns = self.observer.node.get_clock().now().nanoseconds
            future = self.observer.request_safe_stop()
            response = self._wait_future(future, self.now_steady()+2.0,
                stage="A10_SHUTDOWN", component="safety_reset")
            if not response.success:
                return False
            deadline = self.now_steady()+2.0
            while self.now_steady() < deadline:
                for receipt in reversed(self.observer.receipts):
                    if (receipt.context == self.observer.context and receipt.stamp_ns > request_ros_ns
                            and all(x == 0.0 for x in receipt.value["command"])):
                        self.state.facts["safe_stop_verified"] = True
                        return True
                time.sleep(0.01)
        except Exception as error:
            self.log("shutdown", f"safe-stop verification failed: {error}")
        return False

    def execute(self) -> dict[str, Any]:
        """Run one authorized campaign. This function is not called in offline delivery."""
        report: dict[str, Any] | None = None
        try:
            self.start_observer()
            self.start_runtime_children()
            self._wait_for(self._graph_ready_for_recording, min(self.started_steady+60.0,
                self.started_steady+460.0), stage="RECORDER", component="ros_graph",
                reason="RECORDER_SUBSCRIPTIONS_NOT_READY")
            self._wait_ready()
            self._mission()
        except AcceptanceFailure as error:
            self.state.stage = error.stage
            self.state.fail(error.component, error.reason)
            self.log(error.component, error.reason)
        except Exception as error:
            self.state.fail("runner", f"{type(error).__name__}:{error}")
            self.log("runner", f"unhandled failure {type(error).__name__}: {error}")
        finally:
            for index in range(1, 10):
                key = f"A{index}"
                if key not in self.state.facts:
                    self.state.facts[key] = {"pass": False,
                        "reason": f"NOT_EVALUATED_DUE_TO_{self.state.stage}"}
            self.state.stage = "A10_SHUTDOWN"
            self.shutdown()
            try:
                report = self.evaluate_and_write()
            except Exception as error:
                self.state.fail("report", f"REPORT_FINALIZATION_FAILED:{type(error).__name__}:{error}")
                self.state.facts["A10"] = {"pass": False, "reason": "REPORT_FINALIZATION_FAILED",
                    "measured": {**self.state.cleanup, "report_error": f"{type(error).__name__}:{error}"}}
                self.log("report", f"finalization failed: {type(error).__name__}: {error}")
                try:
                    report = self.evaluate_and_write()
                except Exception as retry_error:
                    self.log("report", f"failure report could not be written: {retry_error}")
                    report = {"overall": "FAIL", "acceptance": {},
                              "primary_failure": self.state.primary_failure}
            if self.output:
                try:
                    identity = load_json(self.output / "identity.json")
                    identity["end_time_utc"] = datetime.now(timezone.utc).isoformat()
                    atomic_json(self.output / "identity.json", identity)
                except Exception as error:
                    self.log("identity", f"end time write failed: {error}")
            self.close()
        return report or {"overall": "FAIL", "acceptance": {}}

    def _capture_finalized(self) -> bool:
        if not self.output:
            return False
        capture = self.output / "capture" / "step07"
        metadata = capture / "metadata.yaml"
        databases = tuple(capture.glob("*.db3"))
        return metadata.is_file() and bool(databases) and all(p.process.poll() is not None
            for p in self.process_owner.processes if p.name == "recorder")

    def evaluate_and_write(self) -> dict[str, Any]:
        from mecanum_nav_rl.observations.step07_research_acceptance import evaluate_a1_a10
        self.state.stage = "FINALIZE"
        failed = next(((key, value) for key, value in self.state.facts.items()
                       if key in {f"A{i}" for i in range(1, 11)}
                       and isinstance(value, Mapping) and value.get("pass") is False), None)
        if failed is not None and self.state.primary_failure is None:
            key, fact = failed
            self.state.stage = f"{key}_ACCEPTANCE"
            self.state.fail(key.lower(), str(fact.get("reason", "ACCEPTANCE_CONDITION_FAILED")))
        report = evaluate_a1_a10({**self.state.facts,
                                  "primary_failure": self.state.primary_failure,
                                  "warnings": self.state.warnings,
                                  "valid_observations": self.state.valid_observations[:5]})
        report["timestamp_utc"] = datetime.now(timezone.utc).isoformat()
        report["bag_time_window"] = self.state.metrics.get("bag_time_window")
        report["log_references"] = ["runtime.log"]
        metrics = dict(self.state.metrics)
        metrics.update({"valid_observations": len(self.state.valid_observations),
                        "rejected_observations": self.state.facts.get("rejected_observations", 0),
                        "rejection_reasons": self.state.facts.get("rejection_reasons", {}),
                        "safety_interventions": self.state.facts.get("safety_interventions")})
        if self.output:
            atomic_json(self.output / "acceptance.json", report)
            atomic_json(self.output / "metrics.json", metrics)
        return report

    def shutdown(self) -> dict[str, Any]:
        """Cleanup verdict is separate from the functional A1-A9 outcome."""
        if self.shutdown_completed:
            return self.state.cleanup
        self.state.stage = "SHUTDOWN"
        safe_stop = self._safe_stop()
        try:
            processes = self.process_owner.stop_all(("composite", "bootstrap", "recorder"),
                grace_s=2.0, capture_finalized=self._capture_finalized)
        except Exception as error:
            processes = [{"name": "process_cleanup", "stopped": False,
                          "error": f"{type(error).__name__}:{error}"}]
        capture_finalized = self._capture_finalized()
        executor_stopped = self._stop_executor()
        owned_members = {p.name: self.process_owner._group_members(p.pgid)
                         for p in self.process_owner.processes}
        orphans = {name: list(members or ()) for name, members in owned_members.items()
                   if members is None or members}
        self.state.facts["capture_finalized"] = capture_finalized
        self.state.cleanup = {"completed": all(x.get("stopped") for x in processes)
                                  and not orphans and executor_stopped,
                              "processes": processes,
                              "warnings": list(self.process_owner.warnings),
                              "safe_stop_verified": safe_stop,
                              "capture_finalized": capture_finalized,
                              "executor_stopped": executor_stopped,
                              "owned_orphans": orphans}
        a10 = self.state.cleanup["completed"] and self.state.cleanup["safe_stop_verified"] \
            and self.state.cleanup["capture_finalized"] and not self.state.cleanup["owned_orphans"] \
            and not any(x.get("sigkill_required") for x in processes)
        self.state.facts["A10"] = {"pass": bool(a10), "reason": "CLEANUP_VERIFIED" if a10 else "SHUTDOWN_CONTRACT_NOT_MET",
                                    "measured": self.state.cleanup}
        self.shutdown_completed = True
        return self.state.cleanup

    def _stop_executor(self) -> bool:
        if self.observer is None:
            if self.rclpy is not None:
                try:
                    if self.rclpy.ok():
                        self.rclpy.shutdown()
                except Exception as error:
                    self.state.cleanup.setdefault("errors", []).append(
                        f"rclpy_shutdown:{type(error).__name__}:{error}")
                    return False
            return self.executor_thread is None
        errors = []
        if self.executor is not None:
            try:
                self.executor.remove_node(self.observer.node)
            except Exception as error:
                errors.append(f"remove_node:{type(error).__name__}:{error}")
            try:
                self.executor.shutdown(timeout_sec=2.0)
            except Exception as error:
                errors.append(f"executor_shutdown:{type(error).__name__}:{error}")
        if self.rclpy is not None:
            try:
                if self.rclpy.ok():
                    self.rclpy.shutdown()
            except Exception as error:
                errors.append(f"rclpy_shutdown:{type(error).__name__}:{error}")
        if self.executor_thread is not None:
            try:
                self.executor_thread.join(timeout=2.0)
            except Exception as error:
                errors.append(f"executor_join:{type(error).__name__}:{error}")
        stopped = self.executor_thread is None or not self.executor_thread.is_alive()
        try:
            self.observer.destroy()
        except Exception as error:
            errors.append(f"observer_destroy:{type(error).__name__}:{error}")
        if errors:
            self.state.cleanup.setdefault("errors", []).extend(errors)
        return stopped and not errors

    def close(self) -> None:
        if self.log_stream:
            self.log_stream.flush()
            os.fsync(self.log_stream.fileno())
            self.log_stream.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--output-target", type=Path, required=True)
    parser.add_argument("--owner-authorization", type=Path, required=True)
    parser.add_argument("--gz-partition", required=True)
    parser.add_argument("--fuel-cache-root", type=Path, required=True)
    parser.add_argument("--canonical-map-root", type=Path, required=True)
    args = parser.parse_args(argv)
    runner = None
    try:
        runner = ResearchAcceptanceRunner(repository=args.repository,
            output_target=args.output_target, authorization_path=args.owner_authorization,
            partition=args.gz_partition, fuel_cache_root=args.fuel_cache_root,
            map_root=args.canonical_map_root)
        runner.preflight()
        report = runner.execute()
        return 0 if report["overall"] == "PASS" else 1
    except Exception as error:
        if runner is not None:
            runner.state.fail("runner", str(error))
            try:
                if runner.output:
                    runner.state.facts.update({f"A{i}": {"pass": False,
                        "reason": f"NOT_EVALUATED_DUE_TO_{runner.state.stage}"} for i in range(1, 10)})
                    runner.shutdown()
                    runner.evaluate_and_write()
            except Exception:
                pass
            finally:
                runner.close()
        print(f"STEP07_RESEARCH_ACCEPTANCE_FAIL: {type(error).__name__}: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
