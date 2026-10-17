"""Offline synthetic-repository tests for Run 003 guard/session ownership."""

import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
from types import SimpleNamespace

import pytest


TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parents[3]
sys.path.insert(0, str(TOOLS))
import run_scan_endpoint_probe_run003_session as session  # noqa: E402
import scan_endpoint_probe_run003_runtime_guard as guard  # noqa: E402


class FakeGit:
    def __init__(self, root, blobs, *, head=None, integration=None):
        self.root = Path(root)
        self.blobs = blobs
        self.head = head or "a" * 40
        self.integration = integration or self.head

    def __call__(self, argv, **kwargs):
        assert kwargs["shell"] is False
        command = argv[3:]
        if command == ["remote", "get-url", "origin"]:
            out = b"https://github.com/hazandz/mecanum_autonomy_ws.git"
        elif command == ["rev-parse", "HEAD"]:
            out = self.head.encode()
        elif command == ["rev-parse", "origin/integration/implementation"]:
            out = self.integration.encode()
        elif command == ["status", "--porcelain"]:
            out = b""
        elif len(command) == 2 and command[0] == "show":
            _revision, path = command[1].split(":", 1)
            if path not in self.blobs:
                return subprocess.CompletedProcess(argv, 1, b"", b"missing")
            out = self.blobs[path]
        else:
            return subprocess.CompletedProcess(argv, 1, b"", b"unexpected git call")
        return subprocess.CompletedProcess(argv, 0, out, b"")


class FakeProcess:
    def __init__(self, pid=42424):
        import io
        self.pid = pid
        self.stdout = io.BytesIO(b"[create] Entity creation successful.\n")
        self.alive = True
        self.last_signal = None
        self.wait_calls = []

    def poll(self):
        return None if self.alive else 0

    def wait(self, timeout=None):
        self.wait_calls.append(timeout)
        if self.last_signal == signal.SIGKILL:
            self.alive = False
            return 0
        raise subprocess.TimeoutExpired("fake-bootstrap", timeout)


def _synthetic_repository(tmp_path):
    manifest_path = REPO / session.MANIFEST_PATH
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    files = {
        session.DECISION_PATH,
        session.MANIFEST_PATH,
        session.GUARD_RELATIVE_PATH,
        *manifest["source_pins"].keys(),
    }
    root = tmp_path / "repo"
    root.mkdir()
    blobs = {}
    for rel in files:
        raw = (REPO / rel).read_bytes()
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        blobs[rel] = raw
    commit = "a" * 40
    git = FakeGit(root, blobs, head=commit, integration=commit)
    return root, blobs, git, manifest, commit


def _args(root, tmp_path, commit):
    guard_path = root / session.GUARD_RELATIVE_PATH
    run_dir = root / "artifacts/simulation/sim_eval_scan_endpoint_probe_evidence/runs" / session.RUN_ID
    return (root, guard_path, run_dir, session.RUN_ID, session.PARTITION, commit)


def test_preflight_failure_does_not_consume_guard_or_create_run(tmp_path):
    root, blobs, git, _, commit = _synthetic_repository(tmp_path)
    args = list(_args(root, tmp_path, commit))
    args[3] = "WP06_OTHER_RUN"
    called = []
    with pytest.raises(session.SessionPreflightError):
        session.execute_session(*args, git_runner=git, process_factory=lambda *a, **k: called.append(True))
    assert called == []
    guard_record = json.loads(Path(args[1]).read_text(encoding="utf-8"))
    assert guard_record["state"] == guard.PENDING
    assert not Path(args[2]).exists()


@pytest.mark.parametrize("tamper", ["head", "integration", "decision", "manifest", "command", "partition", "source", "guard_path"])
def test_context_mismatch_fails_before_consumption(tmp_path, tamper):
    root, blobs, git, manifest, commit = _synthetic_repository(tmp_path)
    args = list(_args(root, tmp_path, commit))
    if tamper == "head":
        git.head = "b" * 40
    elif tamper == "integration":
        git.integration = "c" * 40
    elif tamper in {"decision", "manifest", "command", "partition"}:
        rel = session.MANIFEST_PATH if tamper in {"manifest", "command", "partition"} else session.DECISION_PATH
        target = root / rel
        raw = target.read_bytes()
        if tamper == "decision":
            target.write_bytes(raw + b"x")
        else:
            obj = json.loads(raw)
            if tamper == "command":
                obj["commands"]["probe"] = "python3 -m wrong"
            elif tamper == "partition":
                obj["gz_partition"] = "wrong_partition"
            else:
                obj["schema"] = "wrong/v0"
            target.write_text(json.dumps(obj, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    elif tamper == "source":
        source = next(
            path for path in manifest["source_pins"]
            if path != session.GUARD_RELATIVE_PATH
        )
        (root / source).write_bytes(b"changed local source")
    elif tamper == "guard_path":
        args[1] = root / "somewhere_else.json"
    called = []
    with pytest.raises(session.SessionPreflightError):
        session.execute_session(*args, git_runner=git, process_factory=lambda *a, **k: called.append(True))
    assert called == []
    original_guard = root / session.GUARD_RELATIVE_PATH
    assert json.loads(original_guard.read_text(encoding="utf-8"))["state"] == guard.PENDING
    assert not Path(args[2]).exists()


def _run_with_fakes(tmp_path, *, ready=True, probe_error=None):
    root, blobs, git, manifest, commit = _synthetic_repository(tmp_path)
    args = _args(root, tmp_path, commit)
    process = FakeProcess()
    process_kwargs = []

    def process_factory(argv, **kwargs):
        process_kwargs.append((argv, kwargs))
        assert kwargs["shell"] is False
        assert kwargs["start_new_session"] is True
        return process

    probe_calls = []

    def probe_runner(argv, **kwargs):
        probe_calls.append((argv, kwargs))
        if probe_error:
            raise probe_error
        assert kwargs["shell"] is False
        transcript_dir = Path(argv[-1])
        stdout_raw = b"fake gz topic -l output"
        stderr_raw = b""
        stdout_path = transcript_dir / "command-0001.stdout.bin"
        stderr_path = transcript_dir / "command-0001.stderr.bin"
        stdout_path.write_bytes(stdout_raw)
        stderr_path.write_bytes(stderr_raw)
        observation = {
            "argv": ["gz", "topic", "-l"],
            "returncode": 0,
            "timeout": False,
            "transcript_path": "transcripts/command-0001",
            "stdout_path": "transcripts/command-0001.stdout.bin",
            "stdout_sha256": hashlib.sha256(stdout_raw).hexdigest(),
            "stdout_size_bytes": len(stdout_raw),
            "stderr_path": "transcripts/command-0001.stderr.bin",
            "stderr_sha256": hashlib.sha256(stderr_raw).hexdigest(),
            "stderr_size_bytes": 0,
        }
        result = {"outcome": "NO_PUBLISHER_MATCH", "observed_endpoints": [], "command_observations": [observation]}
        return subprocess.CompletedProcess(argv, 1, json.dumps(result).encode(), b"")

    signal_calls = []

    def signal_group(pgid, sig):
        signal_calls.append((pgid, sig))
        assert pgid == process.pid
        process.last_signal = sig

    def readiness_waiter(proc, event, timeout, **kwargs):
        assert timeout == 90
        if ready:
            event.set()
        return ready

    record, code = session.execute_session(
        *args,
        git_runner=git,
        process_factory=process_factory,
        probe_runner=probe_runner,
        signal_group=signal_group,
        group_exists=lambda _pgid: process.last_signal != signal.SIGKILL,
        sleeper=lambda _: None,
        readiness_waiter=readiness_waiter,
    )
    return root, args, process, process_kwargs, probe_calls, signal_calls, record, code


def test_exact_integration_fixture_consumes_once_probe_after_ready_and_tears_own_group(tmp_path):
    root, args, process, factory_calls, probe_calls, signals, record, code = _run_with_fakes(tmp_path)
    assert code == 1  # The fixture result is deliberately a non-pass observation.
    assert len(factory_calls) == 1
    assert factory_calls[0][1]["start_new_session"] is True
    assert record["bootstrap_pid"] == record["bootstrap_pgid"] == process.pid
    assert record["bootstrap_readiness"] is True
    assert len(probe_calls) == 1
    assert probe_calls[0][0][:3] == ["python3", "-m", "mecanum_nav_bringup.sim_eval_scan_endpoint_probe"]
    assert signals == [(process.pid, signal.SIGINT), (process.pid, signal.SIGTERM), (process.pid, signal.SIGKILL)]
    after = json.loads((root / session.GUARD_RELATIVE_PATH).read_text(encoding="utf-8"))
    assert after["state"] == guard.CONSUMED
    saved = json.loads((args[2] / "run_record.json").read_text(encoding="utf-8"))
    assert saved["probe_result"]["outcome"] == "NO_PUBLISHER_MATCH"
    assert saved["transcript_hashes"][0]["sha256"] == hashlib.sha256(b"fake gz topic -l output").hexdigest()
    assert saved["signal_timeline"] == record["signal_timeline"]


def test_not_ready_tears_down_created_group_and_never_calls_probe(tmp_path):
    root, args, process, factory_calls, probe_calls, signals, record, code = _run_with_fakes(tmp_path, ready=False)
    assert code == 1
    assert len(factory_calls) == 1
    assert probe_calls == []
    assert record["bootstrap_readiness"] is False
    assert [sig for _, sig in signals] == [signal.SIGINT, signal.SIGTERM, signal.SIGKILL]
    assert json.loads((root / session.GUARD_RELATIVE_PATH).read_text(encoding="utf-8"))["state"] == guard.CONSUMED


def test_timeout_after_consumption_keeps_guard_consumed_and_second_attempt_is_blocked(tmp_path):
    root, args, process, _, probe_calls, _, record, code = _run_with_fakes(
        tmp_path,
        probe_error=subprocess.TimeoutExpired(["python3", "-m", "probe"], 90),
    )
    assert code == 1 and len(probe_calls) == 1
    assert record["probe_timeout"] is True
    assert json.loads((root / session.GUARD_RELATIVE_PATH).read_text(encoding="utf-8"))["state"] == guard.CONSUMED
    next_args = (*args[:2], root / "artifacts/simulation/sim_eval_scan_endpoint_probe_evidence/runs/second_run", *args[3:])
    called = []
    with pytest.raises(session.SessionPreflightError):
        session.execute_session(*next_args, git_runner=FakeGit(root, {}), process_factory=lambda *a, **k: called.append(1))
    assert called == []


def test_teardown_escalates_owned_group_even_if_launch_leader_already_exited():
    process = FakeProcess()
    process.alive = False
    signals = []

    def signal_group(pgid, sig):
        signals.append((pgid, sig))
        process.last_signal = sig

    timeline, outcome = session._teardown_process_group(
        process,
        signal_group,
        group_exists=lambda _pgid: process.last_signal != signal.SIGKILL,
        sleeper=lambda _seconds: None,
    )
    assert outcome == "STOPPED"
    assert [sig for _, sig in signals] == [signal.SIGINT, signal.SIGTERM, signal.SIGKILL]
    assert all(pgid == process.pid for pgid, _ in signals)
    assert [item["signal"] for item in timeline] == ["SIGINT", "SIGTERM", "SIGKILL"]


def test_guard_json_is_canonical_pending_seed_and_consume_is_atomic_in_temp_copy(tmp_path):
    seed_path = REPO / session.GUARD_RELATIVE_PATH
    raw = seed_path.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf") and not raw.endswith(b"\n")
    seed = guard.load_json_bytes(raw)
    assert guard.canonical_json_bytes(seed) == raw
    assert seed["state"] == guard.PENDING and seed["capacity"] == 1
    temp = tmp_path / "guard.json"
    temp.write_bytes(raw)
    digest = guard.consume_guard(temp, seed["context"])
    assert len(digest) == 64
    assert json.loads(temp.read_text(encoding="utf-8"))["state"] == guard.CONSUMED
    with pytest.raises(guard.GuardError):
        guard.consume_guard(temp, seed["context"])
