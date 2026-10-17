"""One-shot, capacity-one Run 004 session source; never run during candidate creation."""

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time

try:
    from . import scan_endpoint_probe_run004_runtime_guard as guard_module
except ImportError:  # Direct script invocation in a future authorized session.
    import scan_endpoint_probe_run004_runtime_guard as guard_module


SCHEMA = "mecanum_scan_endpoint_probe_run004_session_manifest/v1"
RECORD_SCHEMA = "mecanum_scan_endpoint_probe_run004_record/v1"
RUN_ID = "WP06_6D_SIM_EVAL_SCAN_ENDPOINT_PROBE_RUN_004"
PARTITION = "wp06_scan_probe_run_004"
ORIGIN = "https://github.com/hazandz/mecanum_autonomy_ws.git"
ARCHITECTURE_PATH = "docs/MECANUM_NAV_DRL_Architecture.docx"
ARCHITECTURE_SHA256 = "432eeac363a595cfcf7e81c4b66054fb674dba140a2ef3cffecd617ab8136204"
DECISION_PATH = "docs/governance/decisions/WP-06_SCAN_PROBE_READINESS_AND_TEARDOWN_ACCOUNTING_REMEDIATION_L2_DECISION.md"
EVIDENCE_PATH = "docs/governance/evidence/WP-06_SCAN_PROBE_READINESS_AND_TEARDOWN_ACCOUNTING_REMEDIATION_L2_EVIDENCE.json"
MANIFEST_PATH = "docs/governance/evidence/WP-06_SCAN_PROBE_RUN_004_RUNTIME_GUARD_MANIFEST.json"
GUARD_PATH = "artifacts/simulation/sim_eval_scan_endpoint_probe_evidence/approval_guards/WP06_6D_SIM_EVAL_SCAN_ENDPOINT_PROBE_RUN_004.json"
RUN_DIRECTORY = "artifacts/simulation/sim_eval_scan_endpoint_probe_evidence/runs/" + RUN_ID
WORLD_PATH = "ros2_ws/src/ROBOT_URDF_final_description/launch/sim_eval_scan_probe.world.sdf"
GAZEBO_SOURCE_PATH = "ros2_ws/src/ROBOT_URDF_final_description/urdf/ROBOT_URDF_final.gazebo"
DESCRIPTOR_PATH = "ros2_ws/src/mecanum_nav_bringup/config/bridge/sim_eval_scan_endpoint_probe.static.yaml"
PROBE_PATH = "ros2_ws/src/mecanum_nav_bringup/mecanum_nav_bringup/sim_eval_scan_endpoint_probe.py"
SERVER_LAUNCH_PATH = "ros2_ws/src/ROBOT_URDF_final_description/launch/sim_eval_scan_probe_run004_server.launch.py"
SERVICE_ARGV = ["gz", "service", "--list"]
BOOTSTRAP_ARGV = ["ros2", "launch", "ROBOT_URDF_final_description", "sim_eval_scan_probe_run004_server.launch.py"]
CREATE_ARGV = [
    "ros2", "run", "ros_gz_sim", "create", "-world", "wp06_scan_probe_world",
    "-topic", "/robot_description", "-name", "ROBOT_URDF_final",
    "-allow_renaming", "false", "-x", "0.0", "-y", "0.0", "-z", "0.1", "-Y", "0.0",
]
PROBE_ARGV_PREFIX = ["python3", "-m", "mecanum_nav_bringup.sim_eval_scan_endpoint_probe"]
PROBE_ARGV_TEMPLATE = PROBE_ARGV_PREFIX + ["--transcript-directory", "{run_directory}/transcripts"]
CREATE_SUCCESS = b"Entity creation successful."
CREATE_SERVICE = b"/world/wp06_scan_probe_world/create"
TIMEOUTS = {
    "service_readiness_total_seconds": 30,
    "service_poll_interval_seconds": 0.5,
    "service_command_seconds": 2,
    "create_seconds": 30,
    "stabilization_seconds": 20,
    "probe_seconds": 90,
    "teardown_signal_wait_seconds": 10,
}
TEARDOWN_SIGNALS = ("SIGINT", "SIGTERM", "SIGKILL")


class SessionError(RuntimeError):
    """Fail-closed Run 004 preflight or session error."""


class TeardownObservabilityError(SessionError):
    """Linux /proc could not provide an auditable process-group snapshot."""


def canonical_json_bytes(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise SessionError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_canonical_json(path):
    raw = Path(path).read_bytes()
    if raw.startswith(b"\xef\xbb\xbf") or raw.endswith(b"\n"):
        raise SessionError(f"BOM or final newline forbidden: {path}")
    try:
        value = json.loads(raw.decode("utf-8", errors="strict"), object_pairs_hook=_unique_object)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SessionError(f"invalid UTF-8 JSON: {path}") from exc
    if canonical_json_bytes(value) != raw:
        raise SessionError(f"noncanonical JSON: {path}")
    return value, raw


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def _git_bytes(root, revision_path, git_runner):
    completed = git_runner(
        ["git", "-C", str(root), "show", revision_path],
        shell=False, capture_output=True, text=False, check=False,
    )
    if completed.returncode != 0:
        raise SessionError(f"git show failed: {revision_path}")
    return completed.stdout


def _git_text(root, args, git_runner):
    completed = git_runner(
        ["git", "-C", str(root), *args],
        shell=False, capture_output=True, text=False, check=False,
    )
    if completed.returncode != 0:
        raise SessionError(f"git command failed: {' '.join(args)}")
    return completed.stdout.decode("utf-8", errors="strict").strip()


def _validate_manifest(manifest):
    keys = {
        "schema", "classification", "evidence_level", "run_id", "gz_partition",
        "authority_packet", "evidence_packet", "source_pins", "guard_contract",
        "commands", "timeouts", "teardown_policy", "probe_contract",
    }
    if type(manifest) is not dict or set(manifest) != keys:
        raise SessionError("manifest key set mismatch")
    if manifest["schema"] != SCHEMA or manifest["run_id"] != RUN_ID or manifest["gz_partition"] != PARTITION:
        raise SessionError("manifest identity mismatch")
    if manifest["classification"] != "L2_RUNTIME_OBSERVABILITY_AND_PROCESS_OWNERSHIP_REMEDIATION":
        raise SessionError("manifest classification mismatch")
    if manifest["evidence_level"] != "IMPLEMENTED_OFFLINE_GUARD_AND_SESSION_SOURCE_ONLY":
        raise SessionError("manifest evidence level mismatch")
    authority = manifest["authority_packet"]
    if type(authority) is not dict or set(authority) != {"path", "sha256"} or authority["path"] != DECISION_PATH:
        raise SessionError("decision authority descriptor mismatch")
    if type(authority["sha256"]) is not str or re.fullmatch(r"[0-9a-f]{64}", authority["sha256"]) is None:
        raise SessionError("decision authority digest malformed")
    evidence = manifest["evidence_packet"]
    if type(evidence) is not dict or set(evidence) != {"path", "sha256"} or evidence["path"] != EVIDENCE_PATH:
        raise SessionError("evidence descriptor mismatch")
    if type(evidence["sha256"]) is not str or re.fullmatch(r"[0-9a-f]{64}", evidence["sha256"]) is None:
        raise SessionError("evidence digest malformed")
    required_pins = {WORLD_PATH, GAZEBO_SOURCE_PATH, DESCRIPTOR_PATH, PROBE_PATH, SERVER_LAUNCH_PATH, DECISION_PATH}
    pins = manifest["source_pins"]
    if type(pins) is not dict or set(pins) != required_pins:
        raise SessionError("source pin path set mismatch")
    if any(type(value) is not str or re.fullmatch(r"[0-9a-f]{64}", value) is None for value in pins.values()):
        raise SessionError("source pin digest malformed")
    if pins[DECISION_PATH] != authority["sha256"]:
        raise SessionError("decision pin and authority packet differ")
    if manifest["guard_contract"] != {
        "path": GUARD_PATH,
        "schema": "mecanum_scan_endpoint_probe_run004_guard/v1",
        "capacity": 1,
        "seed_state": "PENDING_EXACT_INTEGRATION_AND_USER_AUTHORIZATION",
    }:
        raise SessionError("guard contract mismatch")
    if manifest["commands"] != {
        "service": SERVICE_ARGV,
        "bootstrap": BOOTSTRAP_ARGV,
        "create": CREATE_ARGV,
        "probe": PROBE_ARGV_TEMPLATE,
    }:
        raise SessionError("command literal mismatch")
    if manifest["timeouts"] != TIMEOUTS:
        raise SessionError("timeout contract mismatch")
    if manifest["teardown_policy"] != {
        "signals": list(TEARDOWN_SIGNALS),
        "wait_seconds_each": 10,
        "direct_child_reap_required": True,
        "linux_proc_group_snapshot_required": True,
        "zombies_are_not_live_members": True,
    }:
        raise SessionError("teardown contract mismatch")
    if manifest["probe_contract"] != {
        "candidate_leaf": "scan",
        "expected_gz_type": "gz.msgs.LaserScan",
        "publisher_only": True,
        "pass_status": "OBSERVED_NOT_PINNED",
        "maximum_transcript_bytes_per_stream": 1048576,
    }:
        raise SessionError("probe contract mismatch")
    return manifest


def _expected_guard_context(manifest, manifest_sha):
    return {
        "run_id": RUN_ID,
        "gz_partition": PARTITION,
        "capacity": 1,
        "guard_path": GUARD_PATH,
        "authority_packet": manifest["authority_packet"],
        "manifest_path": MANIFEST_PATH,
        "manifest_sha256": manifest_sha,
        "source_pins": manifest["source_pins"],
        "commands": manifest["commands"],
        "timeouts": manifest["timeouts"],
        "teardown_policy": manifest["teardown_policy"],
        "runtime_authorization_required": True,
    }


def preflight(repository_root, guard_path, run_directory, run_id, gz_partition, expected_integration_commit,
              *, git_runner=subprocess.run):
    """Validate all integrated bytes and exact context before guard acquisition."""
    root = Path(repository_root).resolve()
    guard_file = Path(guard_path).resolve()
    run_dir = Path(run_directory).resolve()
    if re.fullmatch(r"[0-9a-f]{40}", expected_integration_commit or "") is None:
        raise SessionError("expected integration commit must be exact 40-character lowercase hex")
    if run_id != RUN_ID or gz_partition != PARTITION:
        raise SessionError("run ID or partition mismatch")
    if guard_file != (root / GUARD_PATH).resolve():
        raise SessionError("guard path mismatch")
    if run_dir != (root / RUN_DIRECTORY).resolve():
        raise SessionError("run directory mismatch")
    if run_dir.exists():
        raise SessionError("run directory already exists")
    if _git_text(root, ["remote", "get-url", "origin"], git_runner) != ORIGIN:
        raise SessionError("origin mismatch")
    if _git_text(root, ["rev-parse", "HEAD"], git_runner) != expected_integration_commit:
        raise SessionError("HEAD mismatch")
    if _git_text(root, ["rev-parse", "origin/integration/implementation"], git_runner) != expected_integration_commit:
        raise SessionError("integration ref mismatch")
    if _git_text(root, ["status", "--porcelain"], git_runner):
        raise SessionError("worktree is not clean")

    architecture = (root / ARCHITECTURE_PATH).read_bytes()
    if sha256(architecture) != ARCHITECTURE_SHA256:
        raise SessionError("Architecture authority SHA mismatch")
    if _git_bytes(root, f"{expected_integration_commit}:{ARCHITECTURE_PATH}", git_runner) != architecture:
        raise SessionError("Architecture authority differs from integrated commit")
    manifest_path = root / MANIFEST_PATH
    manifest, manifest_raw = load_canonical_json(manifest_path)
    _validate_manifest(manifest)
    if _git_bytes(root, f"{expected_integration_commit}:{MANIFEST_PATH}", git_runner) != manifest_raw:
        raise SessionError("local manifest differs from integrated commit")
    manifest_sha = sha256(manifest_raw)

    decision_raw = (root / DECISION_PATH).read_bytes()
    evidence_raw = (root / EVIDENCE_PATH).read_bytes()
    if sha256(decision_raw) != manifest["authority_packet"]["sha256"]:
        raise SessionError("authority decision SHA mismatch")
    if sha256(evidence_raw) != manifest["evidence_packet"]["sha256"]:
        raise SessionError("evidence packet SHA mismatch")
    evidence, checked_evidence_raw = load_canonical_json(root / EVIDENCE_PATH)
    if checked_evidence_raw != evidence_raw or evidence.get("source_pins") != manifest["source_pins"]:
        raise SessionError("evidence and manifest source pins differ")
    if _git_bytes(root, f"{expected_integration_commit}:{DECISION_PATH}", git_runner) != decision_raw:
        raise SessionError("decision differs from integrated commit")
    if _git_bytes(root, f"{expected_integration_commit}:{EVIDENCE_PATH}", git_runner) != evidence_raw:
        raise SessionError("evidence differs from integrated commit")

    for relative_path, expected_hash in manifest["source_pins"].items():
        local_bytes = (root / relative_path).read_bytes()
        if sha256(local_bytes) != expected_hash:
            raise SessionError(f"source pin mismatch: {relative_path}")
        if _git_bytes(root, f"{expected_integration_commit}:{relative_path}", git_runner) != local_bytes:
            raise SessionError(f"local source differs from integrated blob: {relative_path}")

    guard_bytes = guard_file.read_bytes()
    integrated_guard = _git_bytes(root, f"{expected_integration_commit}:{GUARD_PATH}", git_runner)
    if guard_bytes != integrated_guard:
        raise SessionError("guard differs from integrated seed")
    guard_record = guard_module.load_json_bytes(guard_bytes)
    if guard_bytes.endswith(b"\n") or guard_module.canonical_json_bytes(guard_record) != guard_bytes:
        raise SessionError("guard is not canonical compact JSON")
    guard_context = _expected_guard_context(manifest, manifest_sha)
    if guard_context != guard_module.EXPECTED_CONTEXT:
        raise SessionError("guard tool context differs from integrated manifest")
    guard_module.validate_pending_record(guard_record, guard_context)
    return {
        "root": root,
        "guard_path": guard_file,
        "run_directory": run_dir,
        "integration_commit": expected_integration_commit,
        "manifest": manifest,
        "manifest_sha256": manifest_sha,
        "evidence_sha256": sha256(evidence_raw),
        "guard_state_before": guard_record["state"],
        "guard_context": guard_context,
    }


def parse_proc_stat(raw):
    """Parse Linux /proc/<pid>/stat using the final ')' before state/pgrp."""
    close = raw.rfind(b")")
    if close < 0:
        raise TeardownObservabilityError("malformed /proc stat: comm terminator missing")
    fields = raw[close + 1:].strip().split()
    if len(fields) < 3:
        raise TeardownObservabilityError("malformed /proc stat: state/pgrp missing")
    state = fields[0].decode("ascii", errors="strict")
    try:
        pgrp = int(fields[2])
    except ValueError as exc:
        raise TeardownObservabilityError("malformed /proc stat: pgrp invalid") from exc
    return state, pgrp


def snapshot_process_group(pgid, *, proc_root=Path("/proc")):
    """Snapshot live/zombie members for an exact PGID, or fail closed."""
    live, zombies = [], []
    try:
        entries = list(Path(proc_root).iterdir())
    except OSError as exc:
        raise TeardownObservabilityError("cannot enumerate /proc") from exc
    for entry in entries:
        if not entry.name.isdecimal():
            continue
        try:
            raw = (entry / "stat").read_bytes()
        except FileNotFoundError:  # Process exited during the snapshot.
            continue
        except OSError as exc:
            raise TeardownObservabilityError(f"cannot read /proc/{entry.name}/stat") from exc
        state, member_group = parse_proc_stat(raw)
        if member_group != pgid:
            continue
        pid = int(entry.name)
        (zombies if state in {"Z", "X"} else live).append(pid)
    return {"live_member_pids": sorted(live), "zombie_member_pids": sorted(zombies)}


def _proc_snapshot_for_record(pgid, proc_root):
    try:
        snapshot = snapshot_process_group(pgid, proc_root=proc_root)
        snapshot["observability"] = "AVAILABLE"
        return snapshot
    except TeardownObservabilityError as exc:
        return {"live_member_pids": [], "zombie_member_pids": [], "observability": "UNAVAILABLE", "error": str(exc)}


def teardown_process_group(process, pgid, *, owned_pgid, signal_group=os.killpg,
                           proc_root=Path("/proc"), sleeper=time.sleep,
                           clock=time.monotonic, wait_timeout_exception=subprocess.TimeoutExpired):
    """Reap the direct child and account exact-group live and zombie members."""
    timeline = []
    if process is None:
        return {"outcome": "NOT_STARTED", "leader_returncode": None, "signal_timeline": timeline,
                "final_snapshot": {"live_member_pids": [], "zombie_member_pids": [], "observability": "AVAILABLE"}}
    if type(pgid) is not int or pgid != owned_pgid or owned_pgid != getattr(process, "pid", None):
        return {"outcome": "UNEXPECTED_PGID_NO_SIGNAL", "leader_returncode": process.poll(),
                "signal_timeline": timeline,
                "final_snapshot": {"live_member_pids": [], "zombie_member_pids": [], "observability": "NOT_CHECKED"}}

    initial = _proc_snapshot_for_record(pgid, proc_root)
    leader_rc = process.poll()
    if initial["observability"] == "AVAILABLE" and not initial["live_member_pids"] and leader_rc is not None:
        try:
            process.wait(timeout=0)
        except wait_timeout_exception:
            pass
        return {"outcome": "ALREADY_EXITED", "leader_returncode": process.poll(),
                "signal_timeline": timeline, "final_snapshot": initial}

    for label in TEARDOWN_SIGNALS:
        entry = {"signal": label, "pgid": pgid, "sent": False}
        try:
            signal_group(pgid, getattr(signal, label))
            entry["sent"] = True
        except ProcessLookupError:
            entry["process_lookup_error"] = True
        except OSError as exc:
            entry["error"] = f"{type(exc).__name__}: {exc}"
        deadline = clock() + TIMEOUTS["teardown_signal_wait_seconds"]
        while clock() < deadline:
            leader_rc = process.poll()
            snapshot = _proc_snapshot_for_record(pgid, proc_root)
            if snapshot["observability"] == "AVAILABLE" and leader_rc is not None and not snapshot["live_member_pids"]:
                try:
                    process.wait(timeout=0)
                except wait_timeout_exception:
                    pass
                entry["exited_or_no_live_members"] = True
                entry["snapshot"] = snapshot
                timeline.append(entry)
                return {"outcome": "STOPPED", "leader_returncode": process.poll(),
                        "signal_timeline": timeline, "final_snapshot": snapshot}
            sleeper(0.1)
        entry["leader_returncode_after_wait"] = process.poll()
        entry["snapshot"] = _proc_snapshot_for_record(pgid, proc_root)
        timeline.append(entry)
        if entry["snapshot"]["observability"] == "UNAVAILABLE":
            continue

    # SIGKILL stage has elapsed. Explicitly wait/reap the direct child as required.
    try:
        process.wait(timeout=TIMEOUTS["teardown_signal_wait_seconds"])
    except wait_timeout_exception:
        pass
    final = _proc_snapshot_for_record(pgid, proc_root)
    leader_rc = process.poll()
    if final["observability"] == "UNAVAILABLE":
        outcome = "TEARDOWN_OBSERVABILITY_UNAVAILABLE"
    elif leader_rc is None or final["live_member_pids"]:
        outcome = "LIVE_PROCESS_GROUP_AFTER_SIGKILL"
    else:
        outcome = "STOPPED"
    return {"outcome": outcome, "leader_returncode": leader_rc,
            "signal_timeline": timeline, "final_snapshot": final}


def _write_bytes(path, raw):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_bytes(raw)
    return {"path": Path(path).relative_to(Path(path).parents[1]).as_posix(),
            "sha256": sha256(raw), "size_bytes": len(raw)}


def _transcript_record(run_dir, name, raw):
    path = run_dir / "transcripts" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return {"path": path.relative_to(run_dir).as_posix(), "sha256": sha256(raw), "size_bytes": len(raw)}


def _service_is_ready(raw):
    try:
        expected = CREATE_SERVICE.decode("ascii")
        return any(line.strip() == expected for line in raw.decode("utf-8", errors="strict").splitlines())
    except UnicodeDecodeError:
        return False


def _wait_for_service(server, env, run_dir, *, command_runner, clock, sleeper):
    deadline = clock() + TIMEOUTS["service_readiness_total_seconds"]
    attempts = []
    while clock() < deadline:
        if server.poll() is not None:
            return False, attempts
        argv = list(SERVICE_ARGV)
        try:
            completed = command_runner(argv, shell=False, capture_output=True, text=False,
                                       timeout=TIMEOUTS["service_command_seconds"], check=False,
                                       cwd=str(run_dir.parents[4]), env=env)
            stdout = completed.stdout if isinstance(completed.stdout, bytes) else str(completed.stdout or "").encode()
            stderr = completed.stderr if isinstance(completed.stderr, bytes) else str(completed.stderr or "").encode()
            returncode, timed_out = completed.returncode, False
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout if isinstance(exc.stdout, bytes) else b""
            stderr = exc.stderr if isinstance(exc.stderr, bytes) else b""
            returncode, timed_out = None, True
        except (FileNotFoundError, OSError) as exc:
            stdout, stderr = b"", str(exc).encode("utf-8", errors="replace")
            returncode, timed_out = None, False
        index = len(attempts) + 1
        stdout_file = _transcript_record(run_dir, f"service-{index:03d}.stdout.bin", stdout)
        stderr_file = _transcript_record(run_dir, f"service-{index:03d}.stderr.bin", stderr)
        ready = returncode == 0 and _service_is_ready(stdout)
        attempts.append({"argv": argv, "returncode": returncode, "timeout": timed_out,
                         "stdout": stdout_file, "stderr": stderr_file, "create_service_present": ready})
        if ready:
            return True, attempts
        remaining = deadline - clock()
        if remaining > 0:
            sleeper(min(TIMEOUTS["service_poll_interval_seconds"], remaining))
    return False, attempts


def _start_process(argv, *, cwd, env, stdout, stderr, popen_factory, pgid_getter):
    process = popen_factory(argv, cwd=str(cwd), env=env, shell=False, start_new_session=True,
                            stdout=stdout, stderr=stderr)
    try:
        pgid = pgid_getter(process.pid)
    except OSError:
        return process, None, False
    return process, pgid, pgid == process.pid


def _create_record_base(preflight_result, guard_state_after, started):
    manifest = preflight_result["manifest"]
    return {
        "schema": RECORD_SCHEMA,
        "run_id": RUN_ID,
        "integration_commit": preflight_result["integration_commit"],
        "authority_packet": manifest["authority_packet"],
        "manifest_sha256": preflight_result["manifest_sha256"],
        "source_pins": manifest["source_pins"],
        "guard_state_before": preflight_result["guard_state_before"],
        "guard_state_after_acquire": guard_state_after,
        "started_utc": started,
        "server": {"pid": None, "pgid": None, "readiness": False, "service_attempts": []},
        "create": {"pid": None, "pgid": None, "exit_code": None, "readiness": False},
        "probe": None,
        "teardown": {"server": None, "create": None},
        "terminal_outcome": "SESSION_ERROR",
    }


def _utc_now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _run_probe(run_dir, root, env, *, command_runner):
    argv = PROBE_ARGV_PREFIX + ["--transcript-directory", str(run_dir / "transcripts")]
    try:
        completed = command_runner(argv, shell=False, capture_output=True, text=False,
                                   timeout=TIMEOUTS["probe_seconds"], check=False,
                                   cwd=str(root), env=env)
        stdout = completed.stdout if isinstance(completed.stdout, bytes) else str(completed.stdout or "").encode()
        stderr = completed.stderr if isinstance(completed.stderr, bytes) else str(completed.stderr or "").encode()
        result = {"exit_code": completed.returncode, "timeout": False}
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, bytes) else b""
        stderr = exc.stderr if isinstance(exc.stderr, bytes) else b""
        result = {"exit_code": None, "timeout": True}
    result["stdout"] = _transcript_record(run_dir, "probe.stdout.bin", stdout)
    result["stderr"] = _transcript_record(run_dir, "probe.stderr.bin", stderr)
    try:
        result["probe_result"] = json.loads(stdout.decode("utf-8", errors="strict"), object_pairs_hook=_unique_object)
    except (UnicodeDecodeError, json.JSONDecodeError, SessionError):
        result["probe_result"] = None
    return result


def run_session(repository_root, guard_path, run_directory, run_id, gz_partition, expected_integration_commit,
                *, git_runner=subprocess.run, command_runner=subprocess.run, popen_factory=subprocess.Popen,
                pgid_getter=os.getpgid, signal_group=os.killpg, proc_root=Path("/proc"),
                clock=time.monotonic, sleeper=time.sleep):
    """Preflight, consume once, service-gated spawn, one probe, and accounted teardown."""
    checked = preflight(repository_root, guard_path, run_directory, run_id, gz_partition,
                        expected_integration_commit, git_runner=git_runner)
    run_dir = checked["run_directory"]
    # Verify the future record location can be created before spending capacity.
    run_dir.mkdir(parents=True, exist_ok=False)
    try:
        guard_module.consume_guard(checked["guard_path"], checked["guard_context"])
    except Exception:
        # Only remove the empty directory created by this invocation.
        run_dir.rmdir()
        raise
    # The capacity-one token is consumed immediately before starting the session.
    record = _create_record_base(checked, guard_module.CONSUMED, _utc_now())
    root = checked["root"]
    env = os.environ.copy()
    env["GZ_PARTITION"] = PARTITION
    pythonpath = str(root / "ros2_ws/src/mecanum_nav_bringup")
    if env.get("PYTHONPATH"):
        env["PYTHONPATH"] = pythonpath + os.pathsep + env["PYTHONPATH"]
    else:
        env["PYTHONPATH"] = pythonpath

    server = create = None
    server_pgid = create_pgid = None
    server_owned = create_owned = False
    bootstrap_log = run_dir / "bootstrap.log"
    try:
        with bootstrap_log.open("wb") as log_stream:
            server, server_pgid, server_owned = _start_process(
                BOOTSTRAP_ARGV, cwd=root, env=env, stdout=log_stream, stderr=subprocess.STDOUT,
                popen_factory=popen_factory, pgid_getter=pgid_getter)
            record["server"].update({"pid": server.pid, "pgid": server_pgid,
                                     "pgid_verified": server_owned,
                                     "bootstrap_log": {"path": "bootstrap.log"}})
            if not server_owned:
                record["terminal_outcome"] = "UNEXPECTED_SERVER_PGID"
                raise SessionError("server process group was not the newly created session")
            service_ready, attempts = _wait_for_service(
                server, env, run_dir, command_runner=command_runner, clock=clock, sleeper=sleeper)
            record["server"]["service_attempts"] = attempts
            record["server"]["readiness"] = service_ready
            if not service_ready:
                record["terminal_outcome"] = "SERVER_NOT_READY"
                raise SessionError("exact create service was not observed before server readiness timeout/death")

            create_log = run_dir / "create.log"
            with create_log.open("wb") as create_stream:
                create, create_pgid, create_owned = _start_process(
                    CREATE_ARGV, cwd=root, env=env, stdout=create_stream, stderr=subprocess.STDOUT,
                    popen_factory=popen_factory, pgid_getter=pgid_getter)
                record["create"].update({"pid": create.pid, "pgid": create_pgid,
                                         "pgid_verified": create_owned,
                                         "transcript": {"path": "create.log"}})
                if not create_owned:
                    record["terminal_outcome"] = "UNEXPECTED_CREATE_PGID"
                    raise SessionError("create process group was not the newly created session")
                try:
                    create_rc = create.wait(timeout=TIMEOUTS["create_seconds"])
                except subprocess.TimeoutExpired:
                    record["create"]["timeout"] = True
                    record["create"]["teardown"] = teardown_process_group(
                create, create_pgid, owned_pgid=create.pid, signal_group=signal_group,
                proc_root=proc_root, sleeper=sleeper, clock=clock)
                    record["teardown"]["create"] = record["create"]["teardown"]
                    record["terminal_outcome"] = "CREATE_TIMEOUT"
                    raise SessionError("robot create timed out")
                create_stream.flush()
                create_raw = create_log.read_bytes()
                record["create"].update({"exit_code": create_rc, "timeout": False,
                                         "transcript_sha256": sha256(create_raw),
                                         "transcript_size_bytes": len(create_raw)})
                create_ready = create_rc == 0 and CREATE_SUCCESS in create_raw
                record["create"]["readiness"] = create_ready
                if not create_ready:
                    record["terminal_outcome"] = "CREATE_NOT_READY"
                    raise SessionError("create must exit zero and emit exact success bytes")
                record["teardown"]["create"] = teardown_process_group(
                    create, create_pgid, owned_pgid=create.pid, signal_group=signal_group,
                    proc_root=proc_root, sleeper=sleeper, clock=clock)

        sleeper(TIMEOUTS["stabilization_seconds"])
        record["probe"] = _run_probe(run_dir, root, env, command_runner=command_runner)
        probe_result = record["probe"].get("probe_result")
        if (record["probe"]["exit_code"] == 0 and not record["probe"]["timeout"]
                and type(probe_result) is dict and probe_result.get("outcome") == "EXACTLY_ONE_MATCH"):
            record["terminal_outcome"] = "GZ_LASERSCAN_ENDPOINT_OBSERVED_NOT_PINNED"
        elif record["probe"]["timeout"]:
            record["terminal_outcome"] = "PROBE_TIMEOUT"
        else:
            record["terminal_outcome"] = "PROBE_NOT_EXACTLY_ONE_MATCH"
    except Exception as exc:
        record["session_error"] = f"{type(exc).__name__}: {exc}"
    finally:
        if server is not None and server_owned:
            record["teardown"]["server"] = teardown_process_group(
                server, server_pgid, owned_pgid=server.pid, signal_group=signal_group,
                proc_root=proc_root, sleeper=sleeper, clock=clock)
        elif server is not None:
            record["teardown"]["server"] = {
                "outcome": "UNEXPECTED_PGID_NO_SIGNAL", "leader_returncode": server.poll(),
                "signal_timeline": [], "final_snapshot": {"live_member_pids": [], "zombie_member_pids": [], "observability": "NOT_CHECKED"},
            }
        if record["terminal_outcome"] == "GZ_LASERSCAN_ENDPOINT_OBSERVED_NOT_PINNED":
            if any(not value or value.get("outcome") not in {"STOPPED", "ALREADY_EXITED"}
                   for value in record["teardown"].values() if value is not None):
                record["terminal_outcome"] = "TEARDOWN_FAILED_AFTER_OBSERVATION"
        record["finished_utc"] = _utc_now()
        bootstrap_raw = bootstrap_log.read_bytes() if bootstrap_log.exists() else b""
        record["server"]["bootstrap_log"].update({"sha256": sha256(bootstrap_raw), "size_bytes": len(bootstrap_raw)})
        record_path = run_dir / "run_record.json"
        record_path.write_bytes(canonical_json_bytes(record))
    return record


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", required=True)
    parser.add_argument("--guard-path", required=True)
    parser.add_argument("--run-directory", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--gz-partition", required=True)
    parser.add_argument("--expected-integration-commit", required=True)
    args = parser.parse_args(argv)
    try:
        record = run_session(args.repository_root, args.guard_path, args.run_directory, args.run_id,
                             args.gz_partition, args.expected_integration_commit)
    except Exception as exc:
        print(json.dumps({"outcome": "PREFLIGHT_FAILED_GUARD_PENDING", "error": str(exc)},
                         ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        return 2
    print(json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0 if record["terminal_outcome"] == "GZ_LASERSCAN_ENDPOINT_OBSERVED_NOT_PINNED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
