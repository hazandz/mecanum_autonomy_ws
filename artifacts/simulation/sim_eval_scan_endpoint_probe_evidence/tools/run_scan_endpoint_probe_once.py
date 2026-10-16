"""Future-only supervisor for one capacity-guarded scan endpoint probe."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Callable, Mapping

from scan_endpoint_probe_runtime_guard import (
    AUTHORITY_PACKET,
    COMMAND_LITERAL,
    GUARD_CONTEXT,
    GZ_PARTITION,
    RUN_ID,
    SOURCE_PINS,
    GuardError,
    consume_pending_guard,
    sha256_file,
    verify_authority_packet,
)


MANIFEST_PATH = "docs/governance/evidence/WP-06_SIM_EVAL_SCAN_ENDPOINT_PROBE_RUNTIME_GUARD_MANIFEST.json"
GUARD_PATH = "artifacts/simulation/sim_eval_scan_endpoint_probe_evidence/approval_guards/WP06_6D_SIM_EVAL_SCAN_ENDPOINT_PROBE_RUN_001.json"
GUARD_SOURCE_PATH = "artifacts/simulation/sim_eval_scan_endpoint_probe_evidence/tools/scan_endpoint_probe_runtime_guard.py"
SUPERVISOR_SOURCE_PATH = "artifacts/simulation/sim_eval_scan_endpoint_probe_evidence/tools/run_scan_endpoint_probe_once.py"
HEX40 = re.compile(r"^[0-9a-f]{40}$")
PROBE_TIMEOUT_SECONDS = 75


class SupervisorPreflightError(RuntimeError):
    """A condition failed before capacity-one consumption."""


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise SupervisorPreflightError(f"duplicate manifest key: {key}")
        result[key] = value
    return result


def _load_canonical_json(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf") or raw.endswith(b"\n"):
        raise SupervisorPreflightError("manifest must be UTF-8 without BOM/final newline")
    try:
        parsed = json.loads(raw.decode("utf-8"), object_pairs_hook=_reject_duplicate_keys)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise SupervisorPreflightError("manifest is invalid JSON") from error
    encoded = json.dumps(parsed, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    if type(parsed) is not dict or encoded != raw:
        raise SupervisorPreflightError("manifest is not canonical JSON")
    return parsed


def _git_output(repository_root: Path, args: list[str], runner: Callable[..., Any]) -> bytes:
    completed = runner(
        ["git", "-C", str(repository_root), *args],
        shell=False,
        capture_output=True,
        timeout=10,
        check=False,
    )
    if getattr(completed, "returncode", 1) != 0 or not isinstance(getattr(completed, "stdout", None), (bytes, str)):
        raise SupervisorPreflightError("git preflight command failed")
    stdout = completed.stdout
    return stdout if isinstance(stdout, bytes) else stdout.encode("utf-8")


def _git_text(repository_root: Path, args: list[str], runner: Callable[..., Any]) -> str:
    return _git_output(repository_root, args, runner).decode("utf-8").strip()


def expected_command(repository_root: Path) -> list[str]:
    return [
        "env",
        f"GZ_PARTITION={GZ_PARTITION}",
        f"PYTHONPATH={repository_root}/ros2_ws/src/mecanum_nav_bringup",
        "python3",
        "-m",
        "mecanum_nav_bringup.sim_eval_scan_endpoint_probe",
    ]


def _verify_source_pins(repository_root: Path) -> None:
    for source in SOURCE_PINS.values():
        path = repository_root / source["path"]
        if not path.is_file() or sha256_file(path) != source["sha256"]:
            raise SupervisorPreflightError(f"source pin mismatch: {source['path']}")


def _verify_integrated_candidate(repository_root: Path, expected_commit: str, git_runner: Callable[..., Any]) -> None:
    if not HEX40.fullmatch(expected_commit):
        raise SupervisorPreflightError("expected integration commit must be 40 lowercase hex characters")
    if _git_text(repository_root, ["rev-parse", "HEAD"], git_runner) != expected_commit:
        raise SupervisorPreflightError("repository HEAD is not the exact expected integration commit")
    if _git_text(repository_root, ["rev-parse", "origin/integration/implementation"], git_runner) != expected_commit:
        raise SupervisorPreflightError("integration ref is not the exact expected integration commit")

    packet_bytes = _git_output(repository_root, ["show", f"{expected_commit}:{AUTHORITY_PACKET['path']}"], git_runner)
    if hashlib.sha256(packet_bytes).hexdigest() != AUTHORITY_PACKET["sha256"]:
        raise SupervisorPreflightError("integrated authority packet byte SHA-256 mismatch")

    manifest_bytes = _git_output(repository_root, ["show", f"{expected_commit}:{MANIFEST_PATH}"], git_runner)
    manifest = _load_canonical_json_bytes(manifest_bytes)
    if manifest.get("authority_packet") != AUTHORITY_PACKET:
        raise SupervisorPreflightError("integrated manifest authority packet mismatch")
    candidate_hashes = manifest.get("candidate_source_sha256")
    expected_paths = {GUARD_PATH, GUARD_SOURCE_PATH, SUPERVISOR_SOURCE_PATH}
    if type(candidate_hashes) is not dict or set(candidate_hashes) != expected_paths:
        raise SupervisorPreflightError("integrated manifest source hash set mismatch")
    for path, expected_hash in candidate_hashes.items():
        blob = _git_output(repository_root, ["show", f"{expected_commit}:{path}"], git_runner)
        if type(expected_hash) is not str or hashlib.sha256(blob).hexdigest() != expected_hash:
            raise SupervisorPreflightError(f"integrated candidate blob mismatch: {path}")
        local_path = repository_root / path
        if not local_path.is_file() or sha256_file(local_path) != expected_hash:
            raise SupervisorPreflightError(f"local candidate source mismatch: {path}")


def _load_canonical_json_bytes(raw: bytes) -> dict[str, Any]:
    if raw.startswith(b"\xef\xbb\xbf") or raw.endswith(b"\n"):
        raise SupervisorPreflightError("integrated manifest encoding mismatch")
    try:
        parsed = json.loads(raw.decode("utf-8"), object_pairs_hook=_reject_duplicate_keys)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise SupervisorPreflightError("integrated manifest JSON mismatch") from error
    if type(parsed) is not dict or json.dumps(parsed, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8") != raw:
        raise SupervisorPreflightError("integrated manifest is not canonical")
    return parsed


def _write_run_record(run_directory: Path, record: Mapping[str, Any]) -> None:
    run_directory.mkdir(parents=True, exist_ok=False)
    (run_directory / "probe_run_record.json").write_bytes(
        json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )


def run_once(
    repository_root: Path,
    guard_path: Path,
    run_directory: Path,
    expected_integration_commit: str,
    *,
    git_runner: Callable[..., Any] = subprocess.run,
    probe_runner: Callable[..., Any] = subprocess.run,
) -> int:
    """Run exactly once only after all exact-integration preconditions pass."""
    repository_root = repository_root.resolve()
    guard_path = guard_path.resolve()
    if guard_path != (repository_root / GUARD_PATH).resolve() or GUARD_CONTEXT["run_id"] != RUN_ID:
        raise SupervisorPreflightError("guard path/run ID differs from exact authorization context")
    if run_directory.exists():
        raise SupervisorPreflightError("run directory already exists")
    verify_authority_packet(repository_root, AUTHORITY_PACKET)
    _verify_source_pins(repository_root)
    _verify_integrated_candidate(repository_root, expected_integration_commit, git_runner)
    if COMMAND_LITERAL != "env GZ_PARTITION=wp06_scan_probe_run_001 PYTHONPATH={repo_root}/ros2_ws/src/mecanum_nav_bringup python3 -m mecanum_nav_bringup.sim_eval_scan_endpoint_probe":
        raise SupervisorPreflightError("command literal mismatch")

    consume_pending_guard(guard_path, GUARD_CONTEXT)
    command = expected_command(repository_root)
    record: dict[str, Any] = {
        "authority_packet": AUTHORITY_PACKET,
        "command": command,
        "expected_integration_commit": expected_integration_commit,
        "guard_state_after_acquire": "CONSUMED",
        "launcher_timeout_seconds": PROBE_TIMEOUT_SECONDS,
        "source_pins": SOURCE_PINS,
    }
    try:
        completed = probe_runner(
            command,
            shell=False,
            capture_output=True,
            text=True,
            timeout=PROBE_TIMEOUT_SECONDS,
            cwd=repository_root,
            check=False,
        )
        record.update({"exit_code": completed.returncode, "stderr": completed.stderr, "stdout": completed.stdout})
        try:
            record["probe_result"] = json.loads(completed.stdout)
        except (TypeError, json.JSONDecodeError):
            record["probe_result"] = None
        _write_run_record(run_directory, record)
        return 0 if record["exit_code"] == 0 and record["probe_result"] and record["probe_result"].get("outcome") == "EXACTLY_ONE_MATCH" else 1
    except subprocess.TimeoutExpired as error:
        record.update({"outcome": "WRAPPER_TIMEOUT", "timeout_cleanup": "launcher-managed escalation; not SIGINT-only", "stdout": error.stdout, "stderr": error.stderr})
        _write_run_record(run_directory, record)
        return 1
    except BaseException as error:
        record.update({"outcome": "SUPERVISOR_INTERRUPTION_OR_ERROR", "error_type": type(error).__name__})
        _write_run_record(run_directory, record)
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", required=True)
    parser.add_argument("--guard-path", required=True)
    parser.add_argument("--run-directory", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--expected-integration-commit", required=True)
    args = parser.parse_args(argv)
    if args.run_id != RUN_ID:
        raise SupervisorPreflightError("run ID differs from exact authorization context")
    return run_once(Path(args.repository_root), Path(args.guard_path), Path(args.run_directory), args.expected_integration_commit)


if __name__ == "__main__":
    raise SystemExit(main())
