"""One-shot Run 002 supervisor, inert on import; never authorizes general runtime."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
from typing import Callable

import scan_endpoint_probe_run002_runtime_guard as guard

MANIFEST_PATH = "docs/governance/evidence/WP-06_SIM_EVAL_SCAN_ENDPOINT_PROBE_RUN_002_RUNTIME_GUARD_MANIFEST.json"
GUARD_SOURCE_PATH = "artifacts/simulation/sim_eval_scan_endpoint_probe_evidence/tools/scan_endpoint_probe_run002_runtime_guard.py"
SUPERVISOR_SOURCE_PATH = "artifacts/simulation/sim_eval_scan_endpoint_probe_evidence/tools/run_scan_endpoint_probe_run002_once.py"
HEX40 = re.compile(r"^[0-9a-f]{40}$")
TIMEOUT_SECONDS = 75
COMMAND_LITERAL = guard.COMMAND_LITERAL


class SupervisorPreflightError(RuntimeError):
    """Raised before guard consumption whenever any authorization input differs."""


def _canonical_json(raw: bytes) -> dict:
    if raw.startswith(b"\xef\xbb\xbf") or raw.endswith(b"\n"):
        raise SupervisorPreflightError("JSON must be UTF-8 without BOM/final newline")
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise SupervisorPreflightError("duplicate JSON key")
            result[key] = value
        return result
    try:
        data = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SupervisorPreflightError("invalid JSON") from exc
    if type(data) is not dict or guard.canonical_json_bytes(data) != raw:
        raise SupervisorPreflightError("JSON is not compact canonical JSON")
    return data


def _git(root: Path, args: list[str], runner: Callable) -> bytes:
    result = runner(["git", "-C", str(root), *args], shell=False, capture_output=True, timeout=10, check=False)
    if getattr(result, "returncode", 1) != 0 or not isinstance(getattr(result, "stdout", None), (bytes, str)):
        raise SupervisorPreflightError(f"git command failed: {args!r}")
    output = result.stdout
    return output if isinstance(output, bytes) else output.encode("utf-8")


def _text(root: Path, args: list[str], runner: Callable) -> str:
    return _git(root, args, runner).decode("utf-8").strip()


def _expected_manifest(root: Path) -> dict:
    return {
        "authority_packet": guard.AUTHORITY_PACKET,
        "capacity": 1,
        "command_literal": COMMAND_LITERAL,
        "evidence_level": "IMPLEMENTED_OFFLINE_GUARD_AND_BOOTSTRAP_SOURCE_ONLY",
        "expected_gz_type": "gz.msgs.LaserScan",
        "future_ros_boundary": "GZ_TO_ROS /scan sensor_msgs/msg/LaserScan",
        "gz_partition": guard.GZ_PARTITION,
        "guard_path": guard.GUARD_PATH,
        "run_id": guard.RUN_ID,
        "schema": "mecanum_wp06_scan_probe_run002_runtime_guard_manifest/v1",
        "source_pins": guard.SOURCE_PINS,
        "state": guard.PENDING,
        "runtime_authorized": False,
    }


def _verify_local_and_integrated(root: Path, commit: str, runner: Callable) -> dict:
    if not HEX40.fullmatch(commit):
        raise SupervisorPreflightError("expected integration must be exactly 40 lowercase hex characters")
    if _text(root, ["remote", "get-url", "origin"], runner) != "https://github.com/hazandz/mecanum_autonomy_ws.git":
        raise SupervisorPreflightError("origin URL mismatch")
    if _text(root, ["rev-parse", "HEAD"], runner) != commit:
        raise SupervisorPreflightError("HEAD is not the expected integrated commit")
    if _text(root, ["rev-parse", "origin/integration/implementation"], runner) != commit:
        raise SupervisorPreflightError("integration ref is not the expected commit")
    if _text(root, ["status", "--short"], runner):
        raise SupervisorPreflightError("worktree is not clean")

    def integrated(path: str) -> bytes:
        return _git(root, ["show", f"{commit}:{path}"], runner)

    authority = integrated(guard.AUTHORITY_PACKET["path"])
    if hashlib.sha256(authority).hexdigest() != guard.AUTHORITY_PACKET["sha256"]:
        raise SupervisorPreflightError("integrated authority decision hash mismatch")
    local_authority = root / guard.AUTHORITY_PACKET["path"]
    if not local_authority.is_file() or local_authority.read_bytes() != authority:
        raise SupervisorPreflightError("local authority decision differs from integrated blob")

    manifest_bytes = integrated(MANIFEST_PATH)
    manifest = _canonical_json(manifest_bytes)
    if manifest != _expected_manifest(root):
        raise SupervisorPreflightError("Run 002 manifest/context mismatch")
    local_manifest = root / MANIFEST_PATH
    if not local_manifest.is_file() or local_manifest.read_bytes() != manifest_bytes:
        raise SupervisorPreflightError("local manifest differs from integrated blob")

    guard_seed_bytes = integrated(guard.GUARD_PATH)
    seed = guard.read_canonical_record_bytes(guard_seed_bytes)
    if seed != {"capacity": 1, "context": guard.GUARD_CONTEXT, "state": guard.PENDING, "version": 1}:
        raise SupervisorPreflightError("integrated Run 002 seed/context is not exact pending state")
    local_seed = root / guard.GUARD_PATH
    if not local_seed.is_file() or local_seed.read_bytes() != guard_seed_bytes:
        raise SupervisorPreflightError("local Run 002 seed differs from integrated blob")

    for source_path in (GUARD_SOURCE_PATH, SUPERVISOR_SOURCE_PATH):
        blob = integrated(source_path)
        local = root / source_path
        if not local.is_file() or local.read_bytes() != blob:
            raise SupervisorPreflightError(f"local Run 002 tool differs from integrated blob: {source_path}")
    for pin in guard.SOURCE_PINS.values():
        blob = integrated(pin["path"])
        expected_hash = hashlib.sha256(blob).hexdigest()
        local = root / pin["path"]
        if expected_hash != pin["sha256"] or not local.is_file() or local.read_bytes() != blob:
            raise SupervisorPreflightError(f"integrated/local source pin mismatch: {pin['path']}")
    return manifest


def _expected_command(root: Path) -> list[str]:
    return [
        "env", f"GZ_PARTITION={guard.GZ_PARTITION}",
        f"PYTHONPATH={root}/ros2_ws/src/mecanum_nav_bringup",
        "python3", "-m", "mecanum_nav_bringup.sim_eval_scan_endpoint_probe",
    ]


def run_once(
    repository_root: Path,
    guard_path: Path,
    run_directory: Path,
    run_id: str,
    partition: str,
    expected_integration_commit: str,
    *, git_runner: Callable = subprocess.run,
    probe_runner: Callable = subprocess.run,
) -> int:
    root = repository_root.resolve()
    target_guard = guard_path.resolve()
    if run_id != guard.RUN_ID or partition != guard.GZ_PARTITION:
        raise SupervisorPreflightError("Run 002 ID or partition mismatch")
    if target_guard != (root / guard.GUARD_PATH).resolve():
        raise SupervisorPreflightError("Run 001 or noncanonical guard path is forbidden")
    expected_command_literal = (
        "env GZ_PARTITION=wp06_scan_probe_run_002 "
        "PYTHONPATH={repo_root}/ros2_ws/src/mecanum_nav_bringup "
        "python3 -m mecanum_nav_bringup.sim_eval_scan_endpoint_probe"
    )
    if COMMAND_LITERAL != expected_command_literal or guard.GUARD_CONTEXT["command_literal"] != expected_command_literal:
        raise SupervisorPreflightError("exact command literal mismatch")
    target_run = run_directory.resolve()
    expected_run = (root / "artifacts/simulation/sim_eval_scan_endpoint_probe_evidence/runs" / guard.RUN_ID).resolve()
    if target_run != expected_run or target_run.exists():
        raise SupervisorPreflightError("run directory must be the exact absent Run 002 directory")

    manifest = _verify_local_and_integrated(root, expected_integration_commit, git_runner)
    if manifest["guard_path"] != guard.GUARD_PATH or manifest["command_literal"] != expected_command_literal:
        raise SupervisorPreflightError("manifest guard/command mismatch")
    guard.verify_authority_packet(root)

    # All checks are complete. Capacity is consumed exactly once immediately before subprocess.
    guard.consume_run002_guard(root, target_guard, guard.GUARD_CONTEXT)
    command = _expected_command(root)
    run_directory.mkdir(parents=True, exist_ok=False)
    record = {
        "authority_packet": guard.AUTHORITY_PACKET,
        "command_literal": expected_command_literal,
        "expected_integration_commit": expected_integration_commit,
        "guard_state_after_acquire": guard.CONSUMED,
        "launcher_timeout_seconds": TIMEOUT_SECONDS,
        "timeout_cleanup": "launcher-managed escalation; not SIGINT-only",
        "source_pins": guard.SOURCE_PINS,
    }
    try:
        result = probe_runner(command, shell=False, capture_output=True, text=True, timeout=TIMEOUT_SECONDS, cwd=root, check=False)
        record.update({"exit_code": result.returncode, "stdout": result.stdout, "stderr": result.stderr})
        try:
            record["probe_result"] = json.loads(result.stdout)
        except (TypeError, json.JSONDecodeError):
            record["probe_result"] = None
        (run_directory / "probe_run_record.json").write_bytes(guard.canonical_json_bytes(record))
        probe = record["probe_result"]
        return 0 if result.returncode == 0 and type(probe) is dict and probe.get("outcome") == "EXACTLY_ONE_MATCH" else 1
    except subprocess.TimeoutExpired as exc:
        record.update({"outcome": "WRAPPER_TIMEOUT", "stdout": exc.stdout, "stderr": exc.stderr})
        (run_directory / "probe_run_record.json").write_bytes(guard.canonical_json_bytes(record))
        return 1
    except BaseException as exc:
        record.update({"outcome": "SUPERVISOR_ERROR_OR_INTERRUPTION", "error_type": type(exc).__name__})
        (run_directory / "probe_run_record.json").write_bytes(guard.canonical_json_bytes(record))
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", required=True)
    parser.add_argument("--guard-path", required=True)
    parser.add_argument("--run-directory", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--gz-partition", required=True)
    parser.add_argument("--expected-integration-commit", required=True)
    args = parser.parse_args(argv)
    return run_once(Path(args.repository_root), Path(args.guard_path), Path(args.run_directory), args.run_id, args.gz_partition, args.expected_integration_commit)


if __name__ == "__main__":
    raise SystemExit(main())
