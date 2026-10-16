"""Future one-shot supervisor; importing this module never starts a process."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

from scan_endpoint_probe_runtime_guard import (
    CapacityOneGuard,
    EXPECTED_AUTHORIZATION,
    EXPECTED_PACKET_SHA256,
    GuardRejected,
    canonical_json_bytes,
)


COMMAND_TEMPLATE = EXPECTED_AUTHORIZATION["command_template"]
MAX_RUNTIME_SECONDS = EXPECTED_AUTHORIZATION["max_runtime_seconds"]
RUNS_RELATIVE_PATH = Path(
    "artifacts/simulation/sim_eval_scan_endpoint_probe_evidence/runs"
)
GUARD_RELATIVE_PATH = Path(
    "artifacts/simulation/sim_eval_scan_endpoint_probe_evidence/approval_guards/"
    "WP06_6D_SIM_EVAL_SCAN_ENDPOINT_PROBE_RUN_001.json"
)


class SupervisorPreflightError(RuntimeError):
    """Raised before guard consumption if immutable source/context checks fail."""


def _utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace(
        "+00:00", "Z"
    )


def _sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _verify_source_pins(repository_root):
    verified = {}
    for role, pin in EXPECTED_AUTHORIZATION["source_pins"].items():
        source = repository_root / pin["path"]
        try:
            actual = _sha256(source)
        except OSError as exc:
            raise SupervisorPreflightError(f"missing source pin: {role}") from exc
        if actual != pin["sha256"]:
            raise SupervisorPreflightError(f"source hash mismatch: {role}")
        verified[role] = {"path": pin["path"], "sha256": actual}
    return verified


def _actual_command(repository_root):
    replacement = str(repository_root / "ros2_ws/src/mecanum_nav_bringup")
    return [
        item.replace("{repo_root}/ros2_ws/src/mecanum_nav_bringup", replacement)
        for item in COMMAND_TEMPLATE
    ]


def _decode_output(value):
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value if isinstance(value, str) else str(value)


def _atomic_write(path, payload):
    data = payload if isinstance(payload, bytes) else canonical_json_bytes(payload)
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "wb") as target:
            target.write(data)
            target.flush()
            os.fsync(target.fileno())
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _classify_probe_output(stdout, returncode):
    if returncode != 0:
        return "PROBE_COMMAND_FAILED", None
    try:
        parsed = json.loads(stdout)
    except (json.JSONDecodeError, TypeError):
        return "INVALID_PROBE_RESULT", None
    if not isinstance(parsed, dict):
        return "INVALID_PROBE_RESULT", None
    if parsed.get("outcome") != "EXACTLY_ONE_MATCH":
        return "PROBE_FAIL", parsed
    endpoints = parsed.get("observed_endpoints")
    if (
        not isinstance(endpoints, list)
        or len(endpoints) != 1
        or endpoints[0].get("message_type") != "gz.msgs.LaserScan"
        or endpoints[0].get("status") != "OBSERVED_NOT_PINNED"
        or not isinstance(endpoints[0].get("topic"), str)
        or not endpoints[0]["topic"].startswith("/")
    ):
        return "INVALID_PROBE_RESULT", parsed
    return "EXACTLY_ONE_MATCH", parsed


def run_scan_endpoint_probe_once(
    repository_root,
    guard_path,
    run_id,
    *,
    command_runner=subprocess.run,
    utc_clock=_utc_now,
):
    """Run one bounded probe only after exact source pins and guard checks.

    The caller is responsible for a separate APPROVED_RUNTIME authorization
    tied to the exact integrated candidate. No call is made during import.
    """
    repository_root = Path(repository_root).resolve(strict=True)
    expected_guard_path = (repository_root / GUARD_RELATIVE_PATH).resolve()
    supplied_guard_path = Path(guard_path)
    if not supplied_guard_path.is_absolute():
        supplied_guard_path = repository_root / supplied_guard_path
    supplied_guard_path = supplied_guard_path.resolve()
    if supplied_guard_path != expected_guard_path:
        raise SupervisorPreflightError("guard path does not match the pinned run packet")
    if run_id != EXPECTED_AUTHORIZATION["run_id"]:
        raise SupervisorPreflightError("run ID differs from the exact guard packet")

    verified_pins = _verify_source_pins(repository_root)
    command = _actual_command(repository_root)
    expected_partition = EXPECTED_AUTHORIZATION["gz_partition"]
    if command[1] != f"GZ_PARTITION={expected_partition}":
        raise SupervisorPreflightError("command partition differs from guard context")

    run_directory = repository_root / RUNS_RELATIVE_PATH / run_id
    if run_directory.exists():
        raise SupervisorPreflightError("run directory already exists; retry is forbidden")
    run_directory.parent.mkdir(parents=True, exist_ok=True)
    run_directory.mkdir(exist_ok=False)

    guard = CapacityOneGuard(supplied_guard_path)
    try:
        acquired_run_id = guard.acquire(
            packet_sha256=EXPECTED_PACKET_SHA256,
            run_id=run_id,
            guard_context=EXPECTED_AUTHORIZATION,
            source_pins=EXPECTED_AUTHORIZATION["source_pins"],
            command_literal=COMMAND_TEMPLATE,
            partition=expected_partition,
        )
    except BaseException:
        # Only remove the fresh empty directory created by this call. A prior
        # run directory is rejected above and is never touched.
        try:
            run_directory.rmdir()
        except OSError:
            pass
        raise

    started_at = None
    stdout = ""
    stderr = ""
    exit_code = None
    outcome = "SUPERVISOR_FAILURE"
    probe_result = None
    result_record = None
    try:
        started_at = utc_clock()
        try:
            completed = command_runner(
                command,
                shell=False,
                capture_output=True,
                text=True,
                timeout=MAX_RUNTIME_SECONDS,
                check=False,
                cwd=str(repository_root),
            )
            stdout = _decode_output(getattr(completed, "stdout", ""))
            stderr = _decode_output(getattr(completed, "stderr", ""))
            exit_code = getattr(completed, "returncode", None)
            outcome, probe_result = _classify_probe_output(stdout, exit_code)
        except subprocess.TimeoutExpired as exc:
            stdout = _decode_output(exc.stdout)
            stderr = _decode_output(exc.stderr)
            outcome = "WRAPPER_TIMEOUT"
        except KeyboardInterrupt:
            outcome = "INTERRUPTED"
            stderr = "Interrupted while the one-shot probe process was supervised."
            exit_code = 130
        except OSError as exc:
            outcome = "PROBE_LAUNCH_FAILED"
            stderr = f"{type(exc).__name__}: {exc}"
            exit_code = 127
        except Exception as exc:
            outcome = "SUPERVISOR_ERROR"
            stderr = f"{type(exc).__name__}: {exc}"
            exit_code = 1

        result_record = {
            "classification": "OBSERVED_NOT_PINNED",
            "command": command,
            "finished_at_utc": utc_clock(),
            "outcome": outcome,
            "probe_result": probe_result,
            "run_id": run_id,
            "source_pins": verified_pins,
            "started_at_utc": started_at,
            "stderr": stderr,
            "stdout": stdout,
            "timeout_cleanup": "launcher-managed escalation; not SIGINT-only",
            "wrapper_exit_code": exit_code,
        }
        return result_record
    finally:
        if result_record is None:
            result_record = {
                "classification": "OBSERVED_NOT_PINNED",
                "command": command,
                "finished_at_utc": utc_clock(),
                "outcome": outcome,
                "probe_result": probe_result,
                "run_id": run_id,
                "source_pins": verified_pins,
                "started_at_utc": started_at,
                "stderr": stderr,
                "stdout": stdout,
                "timeout_cleanup": "launcher-managed escalation; not SIGINT-only",
                "wrapper_exit_code": exit_code,
            }
        try:
            _atomic_write(run_directory / "result.json", result_record)
            _atomic_write(run_directory / "stdout.txt", stdout.encode("utf-8"))
            _atomic_write(run_directory / "stderr.txt", stderr.encode("utf-8"))
        finally:
            guard.finalize(run_id=acquired_run_id, outcome=outcome)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", required=True)
    parser.add_argument("--guard-path", required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args(argv)
    try:
        result = run_scan_endpoint_probe_once(
            args.repository_root,
            args.guard_path,
            args.run_id,
        )
    except (GuardRejected, SupervisorPreflightError, OSError) as exc:
        print(json.dumps({"outcome": "PREFLIGHT_FAILED", "detail": str(exc)}, sort_keys=True, separators=(",", ":")))
        return 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0 if result["outcome"] == "EXACTLY_ONE_MATCH" else 1


if __name__ == "__main__":
    raise SystemExit(main())
