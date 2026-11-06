#!/usr/bin/env python3
"""Capture raw, timestamped evidence for one bounded transient user service.
This program records observations and operation status only; it never grades containment.
"""
import base64
import datetime as dt
import hashlib
import json
import os
import pathlib
import pwd
import secrets
import shutil
import subprocess
import sys
import tempfile
import time

PYTHON_PIN = "/home/hazan/step07_runtime_python312_pydantic_2_10_6/bin/python"
HELPER_SHA256 = "c860f69898d19d569cb116f01cd24772546bfd0465954a1f6b081315101fe881"
HELPER_BYTES = b'''"""Inert helper: parent creates one new-session child, then blocks its event loop."""
import argparse
import asyncio
import json
import os
import pathlib
import signal
import subprocess
import sys
import time

def identity(nonce):
    p = pathlib.Path('/proc/self')
    stat = (p/'stat').read_text()
    tail = stat[stat.rfind(')')+2:].split()
    uid = next(x for x in (p/'status').read_text().splitlines() if x.startswith('Uid:')).split()[1]
    return {'pid':os.getpid(),'uid':int(uid),'start_ticks':int(tail[19]),
            'pgid':os.getpgid(0),'sid':os.getsid(0),
            'cgroup':(p/'cgroup').read_text().strip(),'nonce':nonce}

def put(path, value):
    tmp=path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(value,sort_keys=True)+'\\n')
    os.replace(tmp,path)

def alarm_exit(_sig,_frame): os._exit(124)

def child(out, nonce):
    signal.signal(signal.SIGTERM,signal.SIG_IGN); signal.signal(signal.SIGALRM,alarm_exit); signal.alarm(20)
    put(out/'child.json',identity(nonce)); time.sleep(30)

async def parent(out, nonce):
    signal.signal(signal.SIGTERM,signal.SIG_IGN); signal.signal(signal.SIGALRM,alarm_exit); signal.alarm(20)
    proc=subprocess.Popen([sys.executable,__file__,'--child',str(out),nonce],
        start_new_session=True,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,close_fds=True)
    limit=time.monotonic()+2
    while not (out/'child.json').exists() and time.monotonic()<limit: await asyncio.sleep(.02)
    if not (out/'child.json').exists(): os._exit(125)
    put(out/'parent.json',identity(nonce))
    put(out/'parent_blocked.json',{'nonce':nonce,'pid':os.getpid(),'child_pid':proc.pid,
        'phase':'event_loop_blocked','monotonic_ns':time.monotonic_ns()})
    time.sleep(30)  # Deliberately blocks the active event-loop thread.

if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('--child',action='store_true'); ap.add_argument('out'); ap.add_argument('nonce')
    a=ap.parse_args(); d=pathlib.Path(a.out)
    child(d,a.nonce) if a.child else asyncio.run(parent(d,a.nonce))
'''

WINDOW_NS = 12_000_000_000
CLEANUP_NS = 3_000_000_000
SAMPLE_OFFSETS_NS = (50_000_000, 500_000_000, 1_500_000_000, 3_000_000_000,
                     3_800_000_000, 4_200_000_000, 5_500_000_000,
                     7_500_000_000, 9_500_000_000, 11_400_000_000)
SHOW_PROPERTIES = ("InvocationID", "ControlGroup", "MainPID", "ActiveState", "SubState",
                   "Result", "ExecMainPID", "ExecMainCode", "ExecMainStatus", "Type", "Restart",
                   "RuntimeMaxUSec", "RuntimeRandomizedExtraUSec", "TimeoutStartUSec",
                   "TimeoutStopUSec", "KillMode", "KillSignal", "SendSIGKILL", "FinalKillSignal")


def stamp():
    return {"utc": dt.datetime.now(dt.timezone.utc).isoformat(),
            "monotonic_ns": time.monotonic_ns()}


def b64(value):
    return base64.b64encode(value).decode("ascii")


def decoded(value):
    return value.decode("utf-8", errors="replace")


def parse_properties(text):
    result = {}
    for line in text.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            result[key] = value
    return result


def stat_fields(raw):
    text = decoded(raw)
    tail = text[text.rfind(")") + 2:].split()
    return {"state": tail[0], "pgid": int(tail[2]), "sid": int(tail[3]),
            "start_ticks": int(tail[19])}


def cgroup_v2_path(raw):
    matches = [line[3:] for line in decoded(raw).splitlines() if line.startswith("0::")]
    return matches[0] if len(matches) == 1 else None


class Capture:
    def __init__(self):
        self.root = pathlib.Path(tempfile.mkdtemp(prefix="b22-containment-raw-", dir="/tmp"))
        self.nonce = secrets.token_hex(16)
        self.unit = f"b22-containment-raw-{self.nonce}.service"
        self.helper = self.root / "helper.py"
        self.helper_out = self.root / "helper-state"
        self.helper_out.mkdir()
        self.helper.write_bytes(HELPER_BYTES)
        self.helper_sha256 = hashlib.sha256(HELPER_BYTES).hexdigest()
        self.python = pathlib.Path(PYTHON_PIN)
        self.command = [str(self.python), str(self.helper), str(self.helper_out), self.nonce]
        self.commands_path = self.root / "commands.jsonl"
        self.snapshots_path = self.root / "snapshots.jsonl"
        self.events_path = self.root / "events.jsonl"
        self.errors = []
        self.snapshots = 0
        self.preflight_ok = False
        self.launch_record = None
        self.primary_start_ns = None
        self.primary_deadline_ns = None
        self.pinned_unit = None
        self.pinned_main = None
        self.last_properties = {}
        self.cleanup_attempt = {"attempted": False, "action": "none"}
        self.controller_error = None
        self.cleanup_error = None
        self.summary_error = None
        self.command_records_error = None
        self.primary_samples = {}
        self.cleanup_end_limit_ns = None

    def append(self, path, item):
        with path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(item, sort_keys=True, ensure_ascii=True) + "\n")
            stream.flush()

    def command_run(self, argv, timeout_s, bucket="collection"):
        started = stamp()
        record = {"argv": list(argv), "bucket": bucket, "cwd": os.getcwd(), "started": started}
        if timeout_s <= 0:
            record.update({"returncode": None, "not_started": True,
                           "reason": "deadline_exhausted_before_command_start"})
            record["finished"] = stamp()
            record["elapsed_ns"] = record["finished"]["monotonic_ns"] - started["monotonic_ns"]
            self.errors.append({"kind": "command_not_started", "bucket": bucket,
                                "argv": list(argv), "reason": record["reason"]})
            self.append(self.commands_path, record)
            return record
        try:
            p = subprocess.run(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, timeout=timeout_s, check=False)
            record.update({"returncode": p.returncode, "stdout_b64": b64(p.stdout),
                           "stderr_b64": b64(p.stderr), "stdout_text": decoded(p.stdout),
                           "stderr_text": decoded(p.stderr)})
        except subprocess.TimeoutExpired as exc:
            out = exc.stdout or b""; err = exc.stderr or b""
            if isinstance(out, str): out = out.encode()
            if isinstance(err, str): err = err.encode()
            record.update({"returncode": None, "timeout": True, "stdout_b64": b64(out),
                           "stderr_b64": b64(err), "stdout_text": decoded(out),
                           "stderr_text": decoded(err)})
            self.errors.append({"kind": "command_timeout", "bucket": bucket, "argv": list(argv)})
        except OSError as exc:
            record.update({"returncode": None, "error": f"{type(exc).__name__}:{exc}"})
            self.errors.append({"kind": "command_error", "bucket": bucket, "argv": list(argv),
                                "error": record["error"]})
        record["finished"] = stamp()
        record["elapsed_ns"] = record["finished"]["monotonic_ns"] - started["monotonic_ns"]
        self.append(self.commands_path, record)
        return record

    def read_raw(self, path):
        started = stamp()
        record = {"path": str(path), "started": started}
        try:
            raw = pathlib.Path(path).read_bytes()
            record.update({"read": True, "size": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
                           "bytes_b64": b64(raw), "text": decoded(raw)})
        except OSError as exc:
            record.update({"read": False, "error": f"{type(exc).__name__}:{exc}"})
        record["finished"] = stamp()
        return record

    def read_proc(self, pid):
        started = stamp()
        record = {"pid": pid, "started": started, "files": {}}
        base = pathlib.Path("/proc") / str(pid)
        for name in ("stat", "status", "cmdline", "cgroup"):
            record["files"][name] = self.read_raw(base / name)
        try:
            failed = [name for name, item in record["files"].items() if not item.get("read")]
            if failed:
                raise OSError("required_proc_bytes_unavailable:" + ",".join(failed))
            raw_stat = base64.b64decode(record["files"]["stat"]["bytes_b64"], validate=True)
            raw_status = base64.b64decode(record["files"]["status"]["bytes_b64"], validate=True)
            raw_cmdline = base64.b64decode(record["files"]["cmdline"]["bytes_b64"], validate=True)
            raw_cgroup = base64.b64decode(record["files"]["cgroup"]["bytes_b64"], validate=True)
            identity = stat_fields(raw_stat)
            uid_line = next(line for line in decoded(raw_status).splitlines() if line.startswith("Uid:"))
            identity["uid"] = int(uid_line.split()[1])
            identity["pid"] = int(pid)
            identity["cgroup"] = cgroup_v2_path(raw_cgroup)
            identity["argv"] = [decoded(part) for part in raw_cmdline.split(b"\0") if part]
            record["identity_source_sha256"] = {
                name: record["files"][name]["sha256"]
                for name in ("stat", "status", "cmdline", "cgroup")}
            record["parsed_identity"] = identity
        except (OSError, ValueError, StopIteration, IndexError, TypeError) as exc:
            record["parse_error"] = f"{type(exc).__name__}:{exc}"
        record["finished"] = stamp()
        return record

    def scan_cgroup(self, cgroup_path, deadline_ns):
        started = stamp()
        result = {"pinned_path": cgroup_path, "started": started, "directories": [], "errors": []}
        if (not isinstance(cgroup_path, str) or not cgroup_path.startswith("/")
                or cgroup_path == "/"):
            result["errors"].append("missing_or_invalid_control_group_path")
            result["finished"] = stamp()
            return result
        parts = pathlib.PurePosixPath(cgroup_path).parts
        if ".." in parts:
            result["errors"].append("control_group_path_contains_parent_component")
            result["finished"] = stamp()
            return result
        root = pathlib.Path("/sys/fs/cgroup").joinpath(*[p for p in parts if p != "/"])
        count = 0
        def walk_error(exc):
            result["errors"].append(f"walk:{type(exc).__name__}:{exc}")
        try:
            for directory, subdirs, files in os.walk(root, onerror=walk_error):
                if time.monotonic_ns() >= deadline_ns:
                    result["errors"].append("scan_deadline_reached")
                    break
                count += 1
                subdirs.sort()
                d = pathlib.Path(directory)
                item = {"directory": str(d)}
                procfile = d / "cgroup.procs"
                try:
                    raw = procfile.read_bytes()
                    item.update({"cgroup_procs_read": True, "size": len(raw),
                                 "sha256": hashlib.sha256(raw).hexdigest(),
                                 "bytes_b64": b64(raw), "text": decoded(raw)})
                except OSError as exc:
                    item.update({"cgroup_procs_read": False,
                                 "error": f"{type(exc).__name__}:{exc}"})
                    result["errors"].append(f"{procfile}:{type(exc).__name__}:{exc}")
                result["directories"].append(item)
                if count >= 128 and subdirs:
                    result["errors"].append("scan_directory_limit_128_reached")
                    break
        except OSError as exc:
            result["errors"].append(f"scan:{type(exc).__name__}:{exc}")
        result["finished"] = stamp()
        return result

    def preflight(self):
        facts = {"started": stamp(), "uid": os.getuid(), "gid": os.getgid(),
                 "username": pwd.getpwuid(os.getuid()).pw_name,
                 "python_executable": sys.executable, "python_version": sys.version,
                 "helper_sha256": self.helper_sha256, "output_root": str(self.root),
                 "unit_name": self.unit, "nonce": self.nonce}
        checks = []
        checks.append({"name": "owner_identity", "ok": os.getuid() == 1000 and facts["username"] == "hazan"})
        checks.append({"name": "pinned_python", "ok": pathlib.Path(sys.executable).resolve() == self.python.resolve()
                       and sys.version_info[:3] == (3, 12, 3)})
        checks.append({"name": "helper_sha256", "ok": self.helper_sha256 == HELPER_SHA256})
        systemd = self.command_run(["systemctl", "--version"], 2.0, "preflight")
        version_line = systemd.get("stdout_text", "").splitlines()[:1]
        version_words = version_line[0].split() if version_line else []
        systemd_major = version_words[1].split(".")[0] if len(version_words) > 1 else None
        checks.append({"name": "systemd_major_255", "ok": bool(version_line)
                       and version_words[0] == "systemd" and systemd_major == "255"})
        manager = self.command_run(["systemctl", "--user", "is-system-running"], 2.0, "preflight")
        checks.append({"name": "user_manager_running", "ok": manager.get("returncode") == 0
                       and manager.get("stdout_text", "").strip() == "running"})
        cgroup_raw = self.read_raw("/proc/self/cgroup")
        mount_raw = self.read_raw("/proc/self/mountinfo")
        controllers = self.read_raw("/sys/fs/cgroup/cgroup.controllers")
        has_v2 = "0::" in cgroup_raw.get("text", "") and " - cgroup2 " in mount_raw.get("text", "")
        checks.append({"name": "cgroup_v2_metadata", "ok": has_v2 and controllers.get("read") is True})
        collision = self.command_run(["systemctl", "--user", "show", self.unit,
                                      "--property=LoadState", "--value"], 1.0,
                                     "preflight_unit_collision")
        load_state = collision.get("stdout_text", "").strip()
        checks.append({"name": "unique_unit_not_loaded", "ok": load_state == "not-found"})
        facts.update({"checks": checks, "systemd_version_command": systemd,
                      "user_manager_command": manager, "cgroup_self": cgroup_raw,
                      "cgroup_mountinfo": mount_raw, "cgroup_controllers": controllers,
                      "unit_collision_query": collision, "finished": stamp()})
        self.append(self.events_path, {"kind": "preflight", **facts})
        self.preflight_ok = all(check["ok"] for check in checks)
        return facts

    def observe_binding(self, props, main_proc):
        invocation = props.get("InvocationID")
        cg = props.get("ControlGroup")
        mainpid_text = props.get("MainPID")
        if self.pinned_unit is not None:
            expected = self.pinned_unit
            mismatches = {}
            if invocation and invocation != expected["invocation_id"]:
                mismatches["InvocationID"] = {"pinned": expected["invocation_id"], "observed": invocation}
            if cg and cg != expected["control_group"]:
                mismatches["ControlGroup"] = {"pinned": expected["control_group"], "observed": cg}
            try:
                observed_mainpid = int(mainpid_text) if mainpid_text else None
            except ValueError:
                observed_mainpid = None
            if observed_mainpid is not None and observed_mainpid != expected["main_pid"]:
                mismatches["MainPID"] = {"pinned": expected["main_pid"], "observed": observed_mainpid}
            if mismatches:
                event = {"kind": "pinned_unit_binding_mismatch", "mismatches": mismatches,
                         "raw_properties": dict(props), "observed_at": stamp()}
                self.append(self.events_path, event)
                return {"bound": False, "reason": "pinned_unit_binding_mismatch", "event": event}
        if not (invocation and cg and cg != "/" and mainpid_text and main_proc):
            return {"bound": False, "reason": "required_unit_or_MainPID_identity_missing"}
        try:
            mainpid = int(mainpid_text)
            identity = main_proc.get("parsed_identity", {})
        except (TypeError, ValueError):
            return {"bound": False, "reason": "MainPID_or_identity_malformed"}
        required = ("pid", "uid", "start_ticks", "pgid", "sid", "cgroup", "argv")
        if any(key not in identity or identity[key] is None for key in required):
            return {"bound": False, "reason": "MainPID_identity_incomplete"}
        if (identity.get("pid") != mainpid or identity.get("argv") != self.command
                or identity.get("uid") != 1000 or identity.get("cgroup") != cg):
            return {"bound": False, "reason": "MainPID_identity_does_not_match_unit_command"}
        candidate = {"invocation_id": invocation, "control_group": cg,
                     "main_pid": mainpid, "main_identity": identity,
                     "observed_at": stamp()}
        if self.pinned_unit is None:
            self.pinned_unit = candidate
            self.pinned_main = candidate
            self.append(self.events_path, {"kind": "first_command_bound_unit_observation",
                                           "binding": candidate})
            return {"bound": True, "binding": candidate}
        return {"bound": True, "binding": self.pinned_unit}

    def snapshot(self, label, end_ns, primary_deadline_ns,
                 primary_sample_offset_ns=None):
        begin = stamp()
        index = self.snapshots
        item = {"index": index, "label": label, "started": begin}
        remaining = (end_ns - time.monotonic_ns()) / 1e9
        if remaining <= 0:
            item["systemctl_show"] = {"not_started": True,
                                      "reason": "deadline_exhausted_before_snapshot"}
            item["finished"] = stamp()
            item["within_primary_window"] = item["finished"]["monotonic_ns"] <= primary_deadline_ns
            item["collection_end_limit_ns"] = end_ns
            item["primary_deadline_ns"] = primary_deadline_ns
            self.append(self.snapshots_path, item)
            self.snapshots += 1
            if primary_sample_offset_ns is not None:
                self.primary_samples[str(primary_sample_offset_ns)] = {
                    "status": "missed", "reason": "deadline_exhausted_before_snapshot",
                    "finished": item["finished"]}
            return item
        timeout = min(0.6, remaining)
        show_argv = ["systemctl", "--user", "show", self.unit, "--no-pager"]
        show_argv += [f"--property={key}" for key in SHOW_PROPERTIES]
        show = self.command_run(show_argv, timeout, "snapshot")
        item["systemctl_show"] = show
        props = parse_properties(show.get("stdout_text", ""))
        item["properties_parsed_for_indexing_only"] = props
        self.last_properties = props
        main_proc = None
        try:
            mainpid = int(props.get("MainPID", "0"))
        except ValueError:
            mainpid = 0
        if mainpid:
            main_proc = self.read_proc(mainpid)
            item["main_proc"] = main_proc
        binding_result = self.observe_binding(props, main_proc)
        item["binding_observation"] = binding_result
        metadata = {}
        helper_pids = {}
        for name, role in (("parent.json", "parent"), ("child.json", "child"),
                           ("parent_blocked.json", "blocked_marker")):
            record = self.read_raw(self.helper_out / name)
            if record.get("read"):
                try:
                    parsed = json.loads(record["text"])
                    record["parsed_for_pid_lookup_only"] = parsed
                    if role in ("parent", "child") and isinstance(parsed.get("pid"), int):
                        helper_pids[role] = parsed["pid"]
                except (ValueError, TypeError) as exc:
                    record["parse_error"] = f"{type(exc).__name__}:{exc}"
            metadata[name] = record
        item["helper_metadata_raw"] = metadata
        item["helper_proc"] = {role: self.read_proc(pid) for role, pid in helper_pids.items()}
        if self.pinned_unit is not None:
            observed_cg = self.pinned_unit["control_group"]
            item["cgroup_scan"] = self.scan_cgroup(observed_cg, end_ns)
            item["cgroup_scan_binding"] = {
                "InvocationID": self.pinned_unit["invocation_id"],
                "ControlGroup": observed_cg,
            }
        else:
            item["cgroup_scan"] = {
                "not_started": True,
                "reason": "unit_ownership_binding_not_established",
                "pinned_path": None,
            }
        item["primary_deadline_ns"] = primary_deadline_ns
        item["finished"] = stamp()
        item["within_primary_window"] = item["finished"]["monotonic_ns"] <= primary_deadline_ns
        item["collection_end_limit_ns"] = end_ns
        if primary_sample_offset_ns is not None:
            if item.get("systemctl_show", {}).get("not_started"):
                status = "missed"
            else:
                status = ("collected_within_primary_window" if item["within_primary_window"]
                          else "collected_outside_primary_window")
            self.primary_samples[str(primary_sample_offset_ns)] = {
                "status": status, "snapshot_index": index,
                "started": begin, "finished": item["finished"],
            }
        self.append(self.snapshots_path, item)
        self.snapshots += 1
        return item

    def journal(self, deadline_ns):
        remaining = (deadline_ns - time.monotonic_ns()) / 1e9
        if remaining <= 0:
            record = {"kind": "journal", "skipped": "cleanup_budget_exhausted", "at": stamp()}
        else:
            record = {"kind": "journal", "command": self.command_run(
                ["journalctl", "--user-unit", self.unit, "--no-pager", "-o", "short-monotonic", "-n", "200"],
                min(0.4, remaining), "journal")}
        self.append(self.events_path, record)
        return record

    def guarded_cleanup(self, cleanup_deadline_ns):
        if self.cleanup_end_limit_ns is not None:
            cleanup_deadline_ns = min(cleanup_deadline_ns, self.cleanup_end_limit_ns)
        self.cleanup_attempt = {"attempted": False, "action": "none", "started": stamp()}
        if time.monotonic_ns() >= cleanup_deadline_ns:
            self.cleanup_attempt.update({"skipped": "cleanup_budget_exhausted", "finished": stamp()})
            self.append(self.events_path, {"kind": "cleanup", **self.cleanup_attempt})
            return
        if self.pinned_unit is None or self.pinned_main is None:
            reason = ("unit_ownership_not_pinned" if self.pinned_unit is None
                      else "MainPID_identity_not_pinned")
            self.cleanup_attempt.update({"skipped": reason, "finished": stamp()})
            self.append(self.events_path, {"kind": "cleanup", **self.cleanup_attempt})
            return
        remaining = (cleanup_deadline_ns - time.monotonic_ns()) / 1e9
        fresh = self.command_run(["systemctl", "--user", "show", self.unit, "--no-pager",
                                  "--property=InvocationID", "--property=ControlGroup",
                                  "--property=MainPID", "--property=ActiveState"],
                                 min(0.6, remaining), "cleanup_recheck")
        fresh_props = parse_properties(fresh.get("stdout_text", ""))
        self.cleanup_attempt["recheck"] = fresh
        self.cleanup_attempt["recheck_parsed_for_identity_only"] = fresh_props
        expected = self.pinned_unit
        if fresh.get("returncode") != 0:
            self.cleanup_attempt.update({"skipped": "unit_recheck_command_incomplete", "finished": stamp()})
            self.append(self.events_path, {"kind": "cleanup", **self.cleanup_attempt})
            return
        if fresh_props.get("InvocationID") != expected["invocation_id"]:
            self.cleanup_attempt.update({"skipped": "InvocationID_not_same_as_pinned", "finished": stamp()})
            self.append(self.events_path, {"kind": "cleanup", **self.cleanup_attempt})
            return
        if fresh_props.get("ControlGroup") != expected["control_group"]:
            self.cleanup_attempt.update({"skipped": "ControlGroup_not_same_as_pinned", "finished": stamp()})
            self.append(self.events_path, {"kind": "cleanup", **self.cleanup_attempt})
            return
        if fresh_props.get("ActiveState") in ("failed", "inactive"):
            self.cleanup_attempt.update({"skipped": "unit_already_terminal", "finished": stamp()})
            self.append(self.events_path, {"kind": "cleanup", **self.cleanup_attempt})
            return
        if fresh_props.get("MainPID") != str(expected["main_pid"]):
            self.cleanup_attempt.update({"skipped": "MainPID_not_same_as_pinned", "finished": stamp()})
            self.append(self.events_path, {"kind": "cleanup", **self.cleanup_attempt})
            return
        fresh_proc = self.read_proc(expected["main_pid"])
        self.cleanup_attempt["main_proc_recheck"] = fresh_proc
        current = fresh_proc.get("parsed_identity", {})
        pinned = expected["main_identity"]
        identity_keys = ("pid", "uid", "start_ticks", "pgid", "sid", "cgroup", "argv")
        if any(current.get(key) != pinned.get(key) for key in identity_keys) or current.get("argv") != self.command:
            self.cleanup_attempt.update({"skipped": "MainPID_identity_or_argv_not_same_as_pinned", "finished": stamp()})
            self.append(self.events_path, {"kind": "cleanup", **self.cleanup_attempt})
            return
        remaining = (cleanup_deadline_ns - time.monotonic_ns()) / 1e9
        if remaining <= 0:
            self.cleanup_attempt.update({"skipped": "cleanup_budget_exhausted_before_stop", "finished": stamp()})
            self.append(self.events_path, {"kind": "cleanup", **self.cleanup_attempt})
            return
        self.cleanup_attempt["attempted"] = True
        self.cleanup_attempt["action"] = "systemctl_user_stop_exact_pinned_unit"
        self.cleanup_attempt["stop_command"] = self.command_run(
            ["systemctl", "--user", "stop", self.unit], min(1.0, remaining), "cleanup_stop")
        self.cleanup_attempt["finished"] = stamp()
        stop = self.cleanup_attempt["stop_command"]
        if stop.get("returncode") != 0 or stop.get("timeout") or stop.get("error"):
            self.cleanup_error = {"kind": "cleanup_stop_failed", "command": stop}
        self.append(self.events_path, {"kind": "cleanup", **self.cleanup_attempt})

    def run(self):
        preflight = self.preflight()
        if not self.preflight_ok:
            return self.finish("CAPTURE_INCOMPLETE", "preflight_not_satisfied", 2, preflight)
        self.helper_out.mkdir(exist_ok=True)
        self.primary_start_ns = time.monotonic_ns()
        self.primary_deadline_ns = self.primary_start_ns + WINDOW_NS
        self.cleanup_end_limit_ns = self.primary_deadline_ns + CLEANUP_NS
        self.primary_samples = {
            str(offset): {"status": "pending", "offset_ns": offset}
            for offset in SAMPLE_OFFSETS_NS
        }
        self.append(self.events_path, {"kind": "primary_window_start", "stamp": stamp(),
                                      "deadline_ns": self.primary_deadline_ns})
        property_args = [f"--property={k}={v}" for k, v in {
            "Type": "exec", "Restart": "no", "RuntimeMaxSec": "4s",
            "RuntimeRandomizedExtraSec": "0", "TimeoutStartSec": "3s",
            "TimeoutStopSec": "1s", "KillMode": "control-group",
            "KillSignal": "SIGTERM", "SendSIGKILL": "yes", "FinalKillSignal": "SIGKILL"}.items()]
        launch_argv = ["systemd-run", "--user", "--no-block", f"--unit={self.unit}",
                       *property_args, "--", *self.command]
        try:
            remaining = (self.primary_deadline_ns - time.monotonic_ns()) / 1e9
            self.launch_record = self.command_run(launch_argv, min(3.0, remaining), "launch")
            self.append(self.events_path, {"kind": "launch_outcome_raw", "accepted_by_systemd_run":
                                          self.launch_record.get("returncode") == 0,
                                          "helper_execution_inferred": False,
                                          "command_record": self.launch_record})
            for index, offset in enumerate(SAMPLE_OFFSETS_NS):
                due = self.primary_start_ns + offset
                remaining = (self.primary_deadline_ns - time.monotonic_ns()) / 1e9
                if remaining <= 0:
                    self._mark_pending_samples_missed("primary_deadline_elapsed_before_sample")
                    break
                sleep_s = (due - time.monotonic_ns()) / 1e9
                if sleep_s > 0:
                    time.sleep(min(sleep_s, remaining))
                if time.monotonic_ns() >= self.primary_deadline_ns:
                    self.primary_samples[str(offset)] = {
                        "status": "missed", "reason": "deadline_elapsed_before_snapshot",
                        "at": stamp(),
                    }
                    self._mark_pending_samples_missed("primary_deadline_elapsed_before_sample")
                    break
                self.snapshot(f"scheduled_{index + 1}_at_{offset}_ns", self.primary_deadline_ns,
                              self.primary_deadline_ns, primary_sample_offset_ns=offset)
            self._mark_pending_samples_missed("primary_window_ended_before_sample")
            while True:
                remaining = (self.primary_deadline_ns - time.monotonic_ns()) / 1e9
                if remaining <= 0:
                    break
                time.sleep(min(0.05, remaining))
            self.append(self.events_path, {"kind": "primary_window_end", "stamp": stamp(),
                                          "deadline_ns": self.primary_deadline_ns})
        except BaseException as exc:
            self.controller_error = {"type": type(exc).__name__, "message": str(exc),
                                     "at": stamp()}
            self.errors.append({"kind": "controller_error", **self.controller_error})
            self._mark_pending_samples_missed("controller_exception_after_launch_request")
        finally:
            # One fixed cleanup end-limit is established before launch and never extended.
            cleanup_deadline = self.cleanup_end_limit_ns
            try:
                self.guarded_cleanup(cleanup_deadline)
            except BaseException as exc:
                self.cleanup_error = {"type": type(exc).__name__, "message": str(exc),
                                      "at": stamp()}
                self.errors.append({"kind": "cleanup_error", **self.cleanup_error})
            if time.monotonic_ns() < cleanup_deadline:
                try:
                    evidence_deadline = min(cleanup_deadline, self.primary_deadline_ns + 1_000_000_000)
                    if time.monotonic_ns() < evidence_deadline:
                        self.snapshot("post_primary_window", evidence_deadline, self.primary_deadline_ns)
                except BaseException as exc:
                    self.errors.append({"kind": "post_window_snapshot_error",
                                        "type": type(exc).__name__, "message": str(exc), "at": stamp()})
            try:
                self.journal(cleanup_deadline)
            except BaseException as exc:
                self.errors.append({"kind": "journal_collection_error",
                                    "type": type(exc).__name__, "message": str(exc), "at": stamp()})
        try:
            command_records = self._command_records()
        except BaseException as exc:
            self.command_records_error = {"type": type(exc).__name__, "message": str(exc),
                                          "at": stamp()}
            self.errors.append({"kind": "command_records_error", **self.command_records_error})
            command_records = None
        failed_commands = [] if command_records is None else [
            row for row in command_records
            if row.get("returncode") not in (0, None)
            and not (row.get("bucket") == "preflight_unit_collision"
                     and row.get("stdout_text", "").strip() == "not-found")]
        timed_out = [] if command_records is None else [row for row in command_records if row.get("timeout")]
        primary_complete = all(
            self.primary_samples.get(str(offset), {}).get("status") == "collected_within_primary_window"
            for offset in SAMPLE_OFFSETS_NS)
        launch_accepted = bool(self.launch_record and self.launch_record.get("returncode") == 0)
        complete = (self.preflight_ok and primary_complete and launch_accepted
                    and command_records is not None and not failed_commands and not timed_out
                    and self.controller_error is None and self.cleanup_error is None
                    and self.command_records_error is None and not self.errors)
        note = ("all_primary_samples_and_capture_operations_recorded_without_errors"
                if complete else "one_or_more_primary_samples_or_capture_operations_incomplete")
        extra = {"planned_primary_samples": len(SAMPLE_OFFSETS_NS),
                 "primary_sample_status": self.primary_samples,
                 "primary_samples_complete_in_window": primary_complete,
                 "snapshot_count_including_post_window": self.snapshots,
                 "launch_returncode": None if self.launch_record is None else self.launch_record.get("returncode"),
                 "launch_accepted_by_systemd_run": launch_accepted,
                 "helper_execution_inferred": False,
                 "failed_command_count": len(failed_commands),
                 "timed_out_command_count": len(timed_out),
                 "command_records_error": self.command_records_error,
                 "controller_error": self.controller_error,
                 "cleanup_error": self.cleanup_error,
                 "pinned_unit_identity": self.pinned_unit,
                 "cleanup_operation": self.cleanup_attempt}
        try:
            return self.finish("CAPTURE_COMPLETE" if complete else "CAPTURE_INCOMPLETE", note,
                               0 if complete else 3, preflight, extra=extra)
        except BaseException as exc:
            self.summary_error = {"type": type(exc).__name__, "message": str(exc), "at": stamp()}
            print(json.dumps({"collector_status": "CAPTURE_INCOMPLETE",
                              "controller_error": self.controller_error,
                              "cleanup_error": self.cleanup_error,
                              "summary_error": self.summary_error}, sort_keys=True), file=sys.stderr)
            return 5

    def _mark_pending_samples_missed(self, reason):
        for key, sample in self.primary_samples.items():
            if sample.get("status") == "pending":
                sample.update({"status": "missed", "reason": reason, "at": stamp()})

    def _command_records(self):
        rows = []
        for line_number, line in enumerate(self.commands_path.read_text(encoding="utf-8").splitlines(), 1):
            try:
                rows.append(json.loads(line))
            except (TypeError, ValueError) as exc:
                raise ValueError(f"invalid_command_record_line_{line_number}:{exc}") from exc
        return rows

    def finish(self, state, note, exit_code, preflight, extra=None):
        summary = {"collector_status": state, "collector_note": note,
                   "containment_verdict": None, "preflight": preflight,
                   "output_root": str(self.root), "unit": self.unit, "nonce": self.nonce,
                   "helper_sha256": self.helper_sha256,
                   "helper_file_sha256": hashlib.sha256(self.helper.read_bytes()).hexdigest(),
                   "primary_window_start_ns": self.primary_start_ns,
                   "primary_deadline_ns": self.primary_deadline_ns,
                   "snapshot_count": self.snapshots, "errors": self.errors,
                   "primary_sample_status": self.primary_samples,
                   "controller_error": self.controller_error,
                   "cleanup_error": self.cleanup_error,
                   "command_records_error": self.command_records_error,
                   "launch_record": self.launch_record, "finished": stamp()}
        if extra: summary.update(extra)
        (self.root / "summary.json").write_text(json.dumps(summary, sort_keys=True, indent=2) + "\n")
        print(json.dumps({"collector_status": state, "output_root": str(self.root),
                          "summary": str(self.root / "summary.json"), "exit_code": exit_code}, sort_keys=True))
        return exit_code


def main():
    capture = Capture()
    try:
        return capture.run()
    except BaseException as exc:
        capture.controller_error = {"type": type(exc).__name__, "message": str(exc), "at": stamp()}
        try:
            return capture.finish("CAPTURE_INCOMPLETE", "uncaught_collector_exception",
                                  4, {"exception": capture.controller_error})
        except BaseException as summary_exc:
            capture.summary_error = {"type": type(summary_exc).__name__,
                                     "message": str(summary_exc), "at": stamp()}
            print(json.dumps({"collector_status": "CAPTURE_INCOMPLETE",
                              "output_root": str(capture.root),
                              "controller_error": capture.controller_error,
                              "cleanup_error": capture.cleanup_error,
                              "summary_error": capture.summary_error}, sort_keys=True),
                  file=sys.stderr)
            return 5

if __name__ == "__main__":
    raise SystemExit(main())
