"""One-shot Run 005 source. Import is inert; runtime use needs exact authorization."""

from datetime import datetime, timezone
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time

try:
    from . import scan_endpoint_probe_run005_runtime_guard as guard
except ImportError:
    import scan_endpoint_probe_run005_runtime_guard as guard

ORIGIN = "https://github.com/hazandz/mecanum_autonomy_ws.git"
INTEGRATION_BASE = "83f13d67ab212fec03b18cd2ed830349b7013ab3"
RUN_ID = "WP06_6D_SIM_EVAL_SCAN_ENDPOINT_PROBE_RUN_005"
PARTITION = "wp06_scan_probe_run_005"
WORLD_NAME = "wp06_scan_probe_world"
CREATE_SERVICE = "/world/wp06_scan_probe_world/create"
DECISION_PATH = guard.DECISION_PATH
MANIFEST_PATH = guard.MANIFEST_PATH
EVIDENCE_PATH = "docs/governance/evidence/WP-06_SCAN_PROBE_PERSISTENT_TRANSPORT_DISCOVERY_FIX_L2_EVIDENCE.json"
GUARD_PATH = guard.GUARD_PATH
GUARD_MODULE_PATH = "artifacts/simulation/sim_eval_scan_endpoint_probe_evidence/tools/scan_endpoint_probe_run005_runtime_guard.py"
RUNNER_PATH = "artifacts/simulation/sim_eval_scan_endpoint_probe_evidence/tools/run_scan_endpoint_probe_run005_session.py"
RUN_DIRECTORY = "artifacts/simulation/sim_eval_scan_endpoint_probe_evidence/runs/" + RUN_ID
ARCHITECTURE_PATH = "docs/MECANUM_NAV_DRL_Architecture.docx"
ARCHITECTURE_SHA256 = "432eeac363a595cfcf7e81c4b66054fb674dba140a2ef3cffecd617ab8136204"
WORLD_PATH = "ros2_ws/src/ROBOT_URDF_final_description/launch/sim_eval_scan_probe.world.sdf"
GAZEBO_SOURCE_PATH = "ros2_ws/src/ROBOT_URDF_final_description/urdf/ROBOT_URDF_final.gazebo"
DESCRIPTOR_PATH = "ros2_ws/src/mecanum_nav_bringup/config/bridge/sim_eval_scan_endpoint_probe.static.yaml"
PROBE_PATH = "ros2_ws/src/mecanum_nav_bringup/mecanum_nav_bringup/sim_eval_scan_endpoint_probe.py"
SERVER_LAUNCH_PATH = "ros2_ws/src/ROBOT_URDF_final_description/launch/sim_eval_scan_probe_run005_server.launch.py"
SERVICE_TIMEOUT_S = 30.0
SERVICE_POLL_S = 0.25
MAX_SERVICE_ATTEMPTS = 121
MAX_SERVICES_PER_SNAPSHOT = 4096
MAX_SERVICE_SNAPSHOT_BYTES = 1_048_576
CREATE_TIMEOUT_S = 30.0
PROBE_TIMEOUT_S = 90.0
STABILIZATION_S = 20.0
SIGNAL_WAIT_S = 10.0
CREATE_SUCCESS = b"Entity creation successful."
CREATE_ARGV = ["ros2", "run", "ros_gz_sim", "create", "-world", WORLD_NAME,
               "-topic", "/robot_description", "-name", "ROBOT_URDF_final",
               "-allow_renaming", "false", "-x", "0.0", "-y", "0.0", "-z", "0.1", "-Y", "0.0"]
PROBE_ARGV = ["python3", "-m", "mecanum_nav_bringup.sim_eval_scan_endpoint_probe",
              "--transcript-directory", "{run_directory}/transcripts"]

class SessionError(RuntimeError):
    pass

class TeardownError(SessionError):
    pass

class TransportBindingUnavailable(SessionError):
    pass

def canonical_json_bytes(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")

def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise SessionError(f"duplicate JSON key: {key}")
        result[key] = value
    return result

def _sha(raw):
    return hashlib.sha256(raw).hexdigest()

def _git(root, args, git_runner):
    result = git_runner(["git", "-C", str(root), *args], shell=False, capture_output=True, text=False, check=False)
    if result.returncode:
        raise SessionError("git preflight failed: " + " ".join(args))
    return result.stdout.decode("utf-8", "strict").strip()

def _git_blob(root, revision, path, git_runner):
    result = git_runner(["git", "-C", str(root), "show", f"{revision}:{path}"], shell=False,
                        capture_output=True, text=False, check=False)
    if result.returncode:
        raise SessionError(f"integrated blob missing: {path}")
    return result.stdout

def _canonical_file(path):
    raw = Path(path).read_bytes()
    if raw.startswith(b"\xef\xbb\xbf") or raw.endswith(b"\n"):
        raise SessionError(f"BOM/final newline forbidden: {path}")
    value = json.loads(raw.decode("utf-8", "strict"), object_pairs_hook=_unique)
    if canonical_json_bytes(value) != raw:
        raise SessionError(f"noncanonical JSON: {path}")
    return value, raw

def _load_transport_binding():
    # Delayed, explicit import. run_session calls this before creating/acquiring guard.
    from gz.transport import Node, NodeOptions
    return Node, NodeOptions

def _expected_context(manifest, manifest_sha):
    return {"run_id": RUN_ID, "gz_partition": PARTITION, "capacity": 1,
            "guard_path": GUARD_PATH, "authority_packet": manifest["authority_packet"],
            "manifest_path": MANIFEST_PATH, "manifest_sha256": manifest_sha,
            "source_pins": manifest["source_pins"], "commands": manifest["commands"],
            "timeouts": manifest["timeouts"], "transport_discovery": manifest["transport_discovery"],
            "review_runtime_topology": manifest["review_runtime_topology"],
            "runtime_authorization_required": True}

def preflight(root, guard_path, run_dir, run_id, partition, expected_review_commit,
              expected_integration_base, *, git_runner=subprocess.run):
    root = Path(root).resolve(); guard_path = Path(guard_path).resolve(); run_dir = Path(run_dir).resolve()
    if re.fullmatch(r"[0-9a-f]{40}", expected_review_commit or "") is None:
        raise SessionError("expected review commit must be exact 40 lowercase hex")
    if re.fullmatch(r"[0-9a-f]{40}", expected_integration_base or "") is None:
        raise SessionError("expected integration base must be exact 40 lowercase hex")
    if expected_integration_base != INTEGRATION_BASE:
        raise SessionError("expected integration base does not match the Run 005 source base")
    if run_id != RUN_ID or partition != PARTITION:
        raise SessionError("run identity/partition mismatch")
    if guard_path != (root / GUARD_PATH).resolve() or run_dir != (root / RUN_DIRECTORY).resolve():
        raise SessionError("guard or run directory path mismatch")
    if run_dir.exists():
        raise SessionError("run directory already exists")
    if _git(root, ["remote", "get-url", "origin"], git_runner) != ORIGIN:
        raise SessionError("origin mismatch")
    if _git(root, ["rev-parse", "HEAD"], git_runner) != expected_review_commit:
        raise SessionError("HEAD does not equal expected review commit")
    if _git(root, ["rev-parse", "origin/integration/implementation"], git_runner) != expected_integration_base:
        raise SessionError("integration ref does not equal expected integration base")
    # git merge-base --is-ancestor emits no stdout; _git raises on nonzero.
    _git(root, ["merge-base", "--is-ancestor", expected_integration_base,
                expected_review_commit], git_runner)
    if _git(root, ["status", "--porcelain"], git_runner):
        raise SessionError("worktree is dirty")
    arch = (root / ARCHITECTURE_PATH).read_bytes()
    if _sha(arch) != ARCHITECTURE_SHA256 or _git_blob(root, expected_review_commit, ARCHITECTURE_PATH, git_runner) != arch:
        raise SessionError("Architecture authority mismatch")
    manifest, manifest_raw = _canonical_file(root / MANIFEST_PATH)
    if set(manifest) != {"schema", "classification", "evidence_level", "run_id", "gz_partition", "authority_packet", "evidence_packet", "source_pins", "guard_contract", "commands", "timeouts", "transport_discovery", "teardown_policy", "probe_contract", "review_runtime_topology"}:
        raise SessionError("manifest keys mismatch")
    if (manifest["schema"] != "mecanum_scan_endpoint_probe_run005_guard_manifest/v1"
        or manifest["classification"] != "L2_SIM_EVAL_SCAN_PROBE_PERSISTENT_TRANSPORT_DISCOVERY_FIX"
        or manifest["evidence_level"] != "IMPLEMENTED_OFFLINE_GUARD_AND_SESSION_SOURCE_ONLY"
        or manifest["run_id"] != RUN_ID or manifest["gz_partition"] != PARTITION):
        raise SessionError("manifest identity mismatch")
    authority = manifest["authority_packet"]
    if authority != {"path": DECISION_PATH, "sha256": manifest["source_pins"].get(DECISION_PATH)}:
        raise SessionError("authority packet mismatch")
    evidence, evidence_raw = _canonical_file(root / EVIDENCE_PATH)
    if manifest["evidence_packet"] != {"path": EVIDENCE_PATH, "sha256": _sha(evidence_raw)}:
        raise SessionError("evidence packet SHA/path mismatch")
    if evidence.get("source_pins") != manifest["source_pins"]:
        raise SessionError("evidence source pins differ")
    review_bound_paths = (
        (ARCHITECTURE_PATH, arch), (MANIFEST_PATH, manifest_raw),
        (EVIDENCE_PATH, evidence_raw), (DECISION_PATH, (root / DECISION_PATH).read_bytes()),
        (GUARD_PATH, guard_path.read_bytes()), (GUARD_MODULE_PATH, (root / GUARD_MODULE_PATH).read_bytes()),
        (RUNNER_PATH, (root / RUNNER_PATH).read_bytes()),
    )
    for p, raw in review_bound_paths:
        if _git_blob(root, expected_review_commit, p, git_runner) != raw:
            raise SessionError(f"local bytes differ from expected review commit: {p}")
    if _sha((root / DECISION_PATH).read_bytes()) != authority["sha256"]:
        raise SessionError("decision SHA mismatch")
    pins = manifest["source_pins"]
    expected_paths = {WORLD_PATH, GAZEBO_SOURCE_PATH, DESCRIPTOR_PATH, PROBE_PATH, SERVER_LAUNCH_PATH, DECISION_PATH}
    if type(pins) is not dict or set(pins) != expected_paths:
        raise SessionError("source pin path set mismatch")
    for p, expected in pins.items():
        raw = (root / p).read_bytes()
        if _sha(raw) != expected or _git_blob(root, expected_review_commit, p, git_runner) != raw:
            raise SessionError(f"source pin mismatch: {p}")
    expected_commands = {"bootstrap": ["ros2", "launch", "ROBOT_URDF_final_description", "sim_eval_scan_probe_run005_server.launch.py"],
        "create": CREATE_ARGV, "probe": PROBE_ARGV, "transport": ["gz.transport.Node.service_list"]}
    if manifest["commands"] != expected_commands:
        raise SessionError("command contract mismatch")
    if manifest["guard_contract"] != {"path": GUARD_PATH, "schema": guard.SCHEMA, "capacity": 1, "seed_state": guard.PENDING}:
        raise SessionError("guard contract mismatch")
    if manifest["transport_discovery"] != {"import": "from gz.transport import Node, NodeOptions", "partition": PARTITION,
        "node_count": 1, "method": "service_list", "exact_service": CREATE_SERVICE,
        "timeout_seconds": 30.0, "poll_interval_seconds": 0.25,
        "maximum_attempts": MAX_SERVICE_ATTEMPTS, "maximum_services_per_snapshot": MAX_SERVICES_PER_SNAPSHOT,
        "maximum_snapshot_bytes": MAX_SERVICE_SNAPSHOT_BYTES, "import_before_guard_acquire": True}:
        raise SessionError("transport discovery contract mismatch")
    if manifest["timeouts"] != {"service_readiness_total_seconds": 30.0, "service_poll_interval_seconds": 0.25,
        "create_seconds": 30.0, "stabilization_seconds": 20.0, "probe_seconds": 90.0, "teardown_signal_wait_seconds": 10.0}:
        raise SessionError("timeout contract mismatch")
    if manifest["teardown_policy"] != {"signals": ["SIGINT", "SIGTERM", "SIGKILL"], "wait_seconds_each": 10,
        "direct_child_reap_required": True, "linux_proc_group_snapshot_required": True,
        "zombies_are_not_live_members": True, "create_always_accounted_in_finally": True}:
        raise SessionError("teardown policy mismatch")
    if manifest["probe_contract"] != {"expected_gz_type": "gz.msgs.LaserScan", "publisher_only": True,
        "pass_status": "OBSERVED_NOT_PINNED", "maximum_transcript_bytes_per_stream": 1048576}:
        raise SessionError("probe contract mismatch")
    if manifest["review_runtime_topology"] != {
        "head_must_equal": "expected_review_commit",
        "integration_ref_must_equal": "expected_integration_base",
        "exact_integration_base": INTEGRATION_BASE,
        "integration_base_must_be_ancestor_of_review": True,
        "source_blobs_from": "expected_review_commit",
        "review_commit_argument": "--expected-review-commit",
        "integration_base_argument": "--expected-integration-base",
    }:
        raise SessionError("review/integration topology contract mismatch")
    manifest_sha = _sha(manifest_raw)
    guard_record, guard_raw = _canonical_file(guard_path)
    if _git_blob(root, expected_review_commit, GUARD_PATH, git_runner) != guard_raw:
        raise SessionError("guard differs from expected review commit seed")
    context = _expected_context(manifest, manifest_sha)
    guard.validate_guard(guard_record, context)
    return {"root": root, "run_dir": run_dir, "guard_path": guard_path, "manifest": manifest,
            "manifest_sha256": manifest_sha, "guard_context": context, "guard_state_before": guard_record["state"],
            "review_commit": expected_review_commit, "integration_base": expected_integration_base}

def _service_snapshot(node):
    services = node.service_list()
    if isinstance(services, tuple) and len(services) == 2:
        services = services[0]
    if services is None or isinstance(services, (str, bytes)):
        raise SessionError("service_list returned malformed value")
    result = sorted(str(item) for item in services)
    return result

def _wait_for_create_service(node, server, run_dir, *, clock=time.monotonic, sleeper=time.sleep):
    start = clock(); attempts = []
    for index in range(1, MAX_SERVICE_ATTEMPTS + 1):
        if server.poll() is not None:
            return False, attempts, "SERVER_EXITED"
        try:
            services = _service_snapshot(node)
            exact = CREATE_SERVICE in services
            raw = canonical_json_bytes(services)
            elapsed = clock() - start
            if elapsed > SERVICE_TIMEOUT_S:
                attempts.append({"index": index, "timestamp_monotonic_s": clock(), "service_count": len(services),
                    "exact_service_present": exact, "snapshot_sha256": _sha(raw), "snapshot_size_bytes": len(raw),
                    "snapshot_saved": False, "limit_exceeded": "SERVICE_READINESS_TIMEOUT"})
                return False, attempts, "SERVICE_READINESS_TIMEOUT"
            too_many_records = len(services) > MAX_SERVICES_PER_SNAPSHOT
            too_many_bytes = len(raw) > MAX_SERVICE_SNAPSHOT_BYTES
            if too_many_records or too_many_bytes:
                attempts.append({"index": index, "timestamp_monotonic_s": clock(), "service_count": len(services),
                    "exact_service_present": exact, "snapshot_sha256": _sha(raw), "snapshot_size_bytes": len(raw),
                    "snapshot_saved": False, "limit_exceeded": "SERVICE_LIST_LIMIT_EXCEEDED" if too_many_records else "SERVICE_SNAPSHOT_LIMIT_EXCEEDED"})
                return False, attempts, "SERVICE_LIST_LIMIT_EXCEEDED" if too_many_records else "SERVICE_SNAPSHOT_LIMIT_EXCEEDED"
            snapshot = run_dir / "service_snapshots" / f"service-{index:03d}.json"
            snapshot.parent.mkdir(parents=True, exist_ok=True)
            snapshot.write_bytes(raw)
            attempts.append({"index": index, "timestamp_monotonic_s": clock(), "service_count": len(services),
                "exact_service_present": exact, "snapshot_path": snapshot.relative_to(run_dir).as_posix(),
                "snapshot_sha256": _sha(raw), "snapshot_size_bytes": len(raw)})
            if exact:
                return True, attempts, "READY"
        except Exception as exc:
            attempts.append({"index": index, "timestamp_monotonic_s": clock(), "service_count": None,
                "exact_service_present": False, "error": f"{type(exc).__name__}: {exc}"})
        remaining = SERVICE_TIMEOUT_S - (clock() - start)
        if remaining <= 0:
            break
        sleeper(min(SERVICE_POLL_S, remaining))
    return False, attempts, "SERVICE_READINESS_TIMEOUT"

def parse_proc_stat(raw):
    close = raw.rfind(b")")
    if close < 0: raise TeardownError("malformed /proc stat")
    fields = raw[close + 1:].strip().split()
    if len(fields) < 3: raise TeardownError("short /proc stat")
    return fields[0].decode("ascii", "strict"), int(fields[2])

def snapshot_group(pgid, proc_root=Path("/proc")):
    live, zombie = [], []
    try: entries = list(Path(proc_root).iterdir())
    except OSError as exc: raise TeardownError("/proc unavailable") from exc
    for entry in entries:
        if not entry.name.isdecimal(): continue
        try: raw = (entry / "stat").read_bytes()
        except FileNotFoundError: continue
        except OSError as exc: raise TeardownError(f"cannot read /proc/{entry.name}/stat") from exc
        state, group = parse_proc_stat(raw)
        if group == pgid: (zombie if state in {"Z", "X"} else live).append(int(entry.name))
    return {"live_member_pids": sorted(live), "zombie_member_pids": sorted(zombie)}

def teardown(process, pgid, *, owned_pgid, signal_group=os.killpg, proc_root=Path("/proc"), sleeper=time.sleep,
             clock=time.monotonic, wait_exception=subprocess.TimeoutExpired):
    timeline = []
    if process is None: return {"outcome": "NOT_STARTED", "leader_returncode": None, "signal_timeline": [], "final_snapshot": {"live_member_pids": [], "zombie_member_pids": []}}
    if type(pgid) is not int or pgid != owned_pgid or owned_pgid != process.pid:
        try: process.wait(timeout=SIGNAL_WAIT_S)
        except wait_exception: pass
        return {"outcome": "UNEXPECTED_PGID_NO_SIGNAL", "leader_returncode": process.poll(), "signal_timeline": [], "final_snapshot": {"observability": "NOT_CHECKED"}}
    for name in ("SIGINT", "SIGTERM", "SIGKILL"):
        row = {"signal": name, "pgid": pgid, "sent": False}
        try: signal_group(pgid, getattr(signal, name)); row["sent"] = True
        except ProcessLookupError: row["process_lookup_error"] = True
        except OSError as exc: row["error"] = f"{type(exc).__name__}: {exc}"
        until = clock() + SIGNAL_WAIT_S
        while clock() < until:
            rc = process.poll()
            try: snap = snapshot_group(pgid, proc_root)
            except TeardownError as exc: snap = {"live_member_pids": [], "zombie_member_pids": [], "observability": "UNAVAILABLE", "error": str(exc)}
            if rc is not None and snap.get("observability") != "UNAVAILABLE" and not snap["live_member_pids"]:
                try: process.wait(timeout=0)
                except wait_exception: pass
                row["snapshot"] = snap; row["leader_returncode"] = process.poll(); timeline.append(row)
                return {"outcome": "STOPPED", "leader_returncode": process.poll(), "signal_timeline": timeline, "final_snapshot": snap}
            sleeper(0.1)
        row["snapshot"] = snap; row["leader_returncode"] = process.poll(); timeline.append(row)
    try: process.wait(timeout=SIGNAL_WAIT_S)
    except wait_exception: pass
    try: final = snapshot_group(pgid, proc_root); final["observability"] = "AVAILABLE"
    except TeardownError as exc: final = {"live_member_pids": [], "zombie_member_pids": [], "observability": "UNAVAILABLE", "error": str(exc)}
    if final["observability"] == "UNAVAILABLE": outcome = "TEARDOWN_OBSERVABILITY_UNAVAILABLE"
    elif process.poll() is None or final["live_member_pids"]: outcome = "LIVE_PROCESS_GROUP_AFTER_SIGKILL"
    else: outcome = "STOPPED"
    return {"outcome": outcome, "leader_returncode": process.poll(), "signal_timeline": timeline, "final_snapshot": final}

def _transcript(run_dir, name, raw):
    path = run_dir / "transcripts" / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(raw)
    return {"path": path.relative_to(run_dir).as_posix(), "sha256": _sha(raw), "size_bytes": len(raw)}

def _utc(): return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

def run_session(root, guard_path, run_dir, run_id, partition, expected_review_commit,
                expected_integration_base, *, git_runner=subprocess.run,
                import_binding=_load_transport_binding, popen=subprocess.Popen, command_runner=subprocess.run,
                pgid_getter=os.getpgid, signal_group=os.killpg, proc_root=Path("/proc"), clock=time.monotonic,
                sleeper=time.sleep):
    checked = preflight(root, guard_path, run_dir, run_id, partition,
                        expected_review_commit, expected_integration_base, git_runner=git_runner)
    # Binding failure must occur before directory creation or guard acquisition.
    try:
        Node, NodeOptions = import_binding()
    except (ImportError, ModuleNotFoundError) as exc:
        raise TransportBindingUnavailable("GZ_TRANSPORT_PYTHON_BINDING_UNAVAILABLE") from exc
    checked["run_dir"].mkdir(parents=True, exist_ok=False)
    try: guard.consume_guard(checked["guard_path"], checked["guard_context"])
    except Exception:
        checked["run_dir"].rmdir(); raise
    record = {"schema": "mecanum_scan_endpoint_probe_run005_record/v1", "run_id": RUN_ID,
        "review_commit": expected_review_commit, "integration_base": expected_integration_base,
        "guard_state_before": checked["guard_state_before"],
        "guard_state_after_acquire": guard.CONSUMED, "authority_packet": checked["manifest"]["authority_packet"],
        "source_pins": checked["manifest"]["source_pins"], "started_utc": _utc(),
        "service_readiness": {"ready": False, "attempts": []}, "create": None, "probe": None,
        "processes": {}, "teardown": {}, "terminal_outcome": "SESSION_ERROR"}
    env = os.environ.copy(); env["GZ_PARTITION"] = PARTITION
    root = checked["root"]; run_dir = checked["run_dir"]
    server = create = None; server_pgid = create_pgid = None; server_owned = create_owned = False
    create_torn_down = False
    try:
        options = NodeOptions(); options.partition = PARTITION
        node = Node(options)
        server_log = (run_dir / "bootstrap.log").open("wb")
        server = popen(["ros2", "launch", "ROBOT_URDF_final_description", "sim_eval_scan_probe_run005_server.launch.py"],
            cwd=str(root), env=env, shell=False, start_new_session=True, stdout=server_log, stderr=subprocess.STDOUT)
        server_pgid = pgid_getter(server.pid); server_owned = server_pgid == server.pid
        record["processes"]["server"] = {"pid": server.pid, "pgid": server_pgid, "pgid_verified": server_owned}
        if not server_owned: raise SessionError("unexpected server process group")
        ready, attempts, reason = _wait_for_create_service(node, server, run_dir, clock=clock, sleeper=sleeper)
        record["service_readiness"] = {"ready": ready, "reason": reason, "attempts": attempts}
        if not ready: record["terminal_outcome"] = reason; raise SessionError(reason)
        create_log = (run_dir / "create.log").open("wb")
        try:
            create = popen(CREATE_ARGV, cwd=str(root), env=env, shell=False, start_new_session=True,
                           stdout=create_log, stderr=subprocess.STDOUT)
            create_pgid = pgid_getter(create.pid); create_owned = create_pgid == create.pid
            record["processes"]["create"] = {"pid": create.pid, "pgid": create_pgid, "pgid_verified": create_owned}
            if not create_owned: raise SessionError("unexpected create process group")
            try: rc = create.wait(timeout=CREATE_TIMEOUT_S); timed_out = False
            except subprocess.TimeoutExpired: rc = None; timed_out = True
            create_log.flush(); raw = (run_dir / "create.log").read_bytes()
            record["create"] = {"exit_code": rc, "timeout": timed_out, "readiness": rc == 0 and CREATE_SUCCESS in raw,
                "transcript": _transcript(run_dir, "create.stdout.bin", raw)}
            if timed_out or rc != 0 or CREATE_SUCCESS not in raw:
                record["terminal_outcome"] = "CREATE_NOT_READY"; raise SessionError("create exit/token contract failed")
        finally:
            if create is not None and not create_torn_down:
                record["teardown"]["create"] = teardown(create, create_pgid, owned_pgid=create.pid if create_owned else None,
                    signal_group=signal_group, proc_root=proc_root, sleeper=sleeper, clock=clock)
                create_torn_down = True
        sleeper(STABILIZATION_S)
        argv = ["python3", "-m", "mecanum_nav_bringup.sim_eval_scan_endpoint_probe",
                "--transcript-directory", str(run_dir / "transcripts")]
        try:
            probe = command_runner(argv, cwd=str(root), env=env, shell=False, capture_output=True, text=False,
                timeout=PROBE_TIMEOUT_S, check=False)
            out = probe.stdout if isinstance(probe.stdout, bytes) else str(probe.stdout or "").encode()
            err = probe.stderr if isinstance(probe.stderr, bytes) else str(probe.stderr or "").encode()
            rc, timed_out = probe.returncode, False
        except subprocess.TimeoutExpired as exc:
            out = exc.stdout if isinstance(exc.stdout, bytes) else b""; err = exc.stderr if isinstance(exc.stderr, bytes) else b""
            rc, timed_out = None, True
        result = None
        try: result = json.loads(out.decode("utf-8", "strict"), object_pairs_hook=_unique)
        except (UnicodeDecodeError, json.JSONDecodeError, SessionError): pass
        record["probe"] = {"exit_code": rc, "timeout": timed_out, "stdout": _transcript(run_dir, "probe.stdout.bin", out),
            "stderr": _transcript(run_dir, "probe.stderr.bin", err), "probe_result": result}
        if rc == 0 and not timed_out and type(result) is dict and result.get("outcome") == "EXACTLY_ONE_MATCH":
            record["terminal_outcome"] = "GZ_LASERSCAN_ENDPOINT_OBSERVED_NOT_PINNED"
        else: record["terminal_outcome"] = "PROBE_NOT_EXACTLY_ONE_MATCH"
    except Exception as exc:
        record["session_error"] = f"{type(exc).__name__}: {exc}"
    finally:
        if create is not None and not create_torn_down:
            record["teardown"]["create"] = teardown(create, create_pgid, owned_pgid=create.pid if create_owned else None,
                signal_group=signal_group, proc_root=proc_root, sleeper=sleeper, clock=clock)
            create_torn_down = True
        if server is not None:
            record["teardown"]["server"] = teardown(server, server_pgid, owned_pgid=server.pid if server_owned else None,
                signal_group=signal_group, proc_root=proc_root, sleeper=sleeper, clock=clock)
        bootstrap_path = run_dir / "bootstrap.log"
        if bootstrap_path.exists():
            bootstrap_raw = bootstrap_path.read_bytes()
            record["bootstrap_log"] = {"path": "bootstrap.log", "sha256": _sha(bootstrap_raw),
                                        "size_bytes": len(bootstrap_raw)}
        record["finished_utc"] = _utc()
        (run_dir / "run_record.json").write_bytes(canonical_json_bytes(record))
    return record

def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("repository-root", "guard-path", "run-directory", "run-id", "gz-partition",
                 "expected-review-commit", "expected-integration-base"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args(argv)
    try:
        record = run_session(args.repository_root, args.guard_path, args.run_directory, args.run_id,
            args.gz_partition, args.expected_review_commit, args.expected_integration_base)
    except TransportBindingUnavailable as exc:
        print(json.dumps({"outcome": "GZ_TRANSPORT_PYTHON_BINDING_UNAVAILABLE", "error": str(exc)}, sort_keys=True, separators=(",", ":")))
        return 2
    except Exception as exc:
        print(json.dumps({"outcome": "PREFLIGHT_FAILED_GUARD_PENDING", "error": str(exc)}, sort_keys=True, separators=(",", ":")))
        return 2
    print(json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0 if record["terminal_outcome"] == "GZ_LASERSCAN_ENDPOINT_OBSERVED_NOT_PINNED" else 1

if __name__ == "__main__":
    raise SystemExit(main())
