"""Offline Run 004 runner, guard, readiness, and process-accounting tests."""

import ast
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
from types import SimpleNamespace

import pytest

from scan_endpoint_probe_run004_runtime_guard import (
    CONSUMED,
    EXPECTED_CONTEXT,
    GuardError,
    PENDING,
    canonical_json_bytes,
    consume_guard,
    load_json_bytes,
)
import run_scan_endpoint_probe_run004_session as runner


ROOT = Path(__file__).resolve().parents[4]
BASE = "db464f741e24a81b3f9587f827fc145c533d8d6c"


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate key: {key}")
        result[key] = value
    return result


def _manifest_and_evidence(root=ROOT):
    manifest = json.loads((root / runner.MANIFEST_PATH).read_text(encoding="utf-8"))
    evidence = json.loads((root / runner.EVIDENCE_PATH).read_text(encoding="utf-8"))
    return manifest, evidence


def _git_fixture(root, *, head="a" * 40, integration=None, dirty=""):
    integration = head if integration is None else integration

    def fake(args, **kwargs):
        argv = list(args)
        if argv[-3:] == ["remote", "get-url", "origin"]:
            return SimpleNamespace(returncode=0, stdout=runner.ORIGIN.encode())
        if argv[-2:] == ["rev-parse", "HEAD"]:
            return SimpleNamespace(returncode=0, stdout=head.encode())
        if argv[-2:] == ["rev-parse", "origin/integration/implementation"]:
            return SimpleNamespace(returncode=0, stdout=integration.encode())
        if argv[-2:] == ["status", "--porcelain"]:
            return SimpleNamespace(returncode=0, stdout=dirty.encode())
        if len(argv) >= 3 and argv[-2] == "show":
            revision_path = argv[-1]
            commit, relative = revision_path.split(":", 1)
            if commit != head:
                return SimpleNamespace(returncode=1, stdout=b"")
            path = root / relative
            if not path.is_file():
                return SimpleNamespace(returncode=1, stdout=b"")
            return SimpleNamespace(returncode=0, stdout=path.read_bytes())
        raise AssertionError(f"unexpected git invocation: {argv}")

    return fake


def _copy_synthetic_repo(tmp_path):
    root = tmp_path / "repo"
    manifest, _ = _manifest_and_evidence()
    required = {
        runner.ARCHITECTURE_PATH,
        runner.DECISION_PATH,
        runner.EVIDENCE_PATH,
        runner.MANIFEST_PATH,
        runner.GUARD_PATH,
        *manifest["source_pins"].keys(),
    }
    for relative in required:
        source = ROOT / relative
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    return root


def _pending_guard(root):
    value = json.loads((root / runner.GUARD_PATH).read_text(encoding="utf-8"))
    assert value["state"] == PENDING
    return value


class FakeProcess:
    def __init__(self, pid, *, returncode=None, output=b"", output_stream=None):
        self.pid = pid
        self.returncode = returncode
        if output_stream is not None and output:
            output_stream.write(output)
            output_stream.flush()

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        if self.returncode is None:
            raise subprocess.TimeoutExpired("fake", timeout)
        return self.returncode


class FakeClock:
    def __init__(self):
        self.value = 0.0

    def __call__(self):
        return self.value

    def sleep(self, duration):
        self.value += duration


def _recorded_probe_result():
    return {
        "outcome": "EXACTLY_ONE_MATCH",
        "observed_endpoints": [{
            "message_type": "gz.msgs.LaserScan",
            "status": "OBSERVED_NOT_PINNED",
            "topic": "/world/wp06_scan_probe_world/model/robot/link/lidar/sensor/scan",
        }],
    }


def test_run004_guard_seed_is_canonical_pending_and_atomic_capacity_one(tmp_path):
    root = _copy_synthetic_repo(tmp_path)
    path = root / runner.GUARD_PATH
    record = load_json_bytes(path.read_bytes())
    assert record["state"] == PENDING
    assert record["capacity"] == 1
    assert record["context"] == EXPECTED_CONTEXT
    consume_guard(path, EXPECTED_CONTEXT)
    assert load_json_bytes(path.read_bytes())["state"] == CONSUMED
    with pytest.raises(GuardError):
        consume_guard(path, EXPECTED_CONTEXT)


@pytest.mark.parametrize("mismatch", ["head", "integration", "dirty", "run_id", "partition", "guard_path"])
def test_preflight_rejects_mismatch_before_guard_consumption(tmp_path, mismatch):
    root = _copy_synthetic_repo(tmp_path)
    expected = "a" * 40
    values = {"head": expected, "integration": expected, "dirty": ""}
    if mismatch == "head":
        values["head"] = "b" * 40
    elif mismatch == "integration":
        values["integration"] = "b" * 40
    elif mismatch == "dirty":
        values["dirty"] = " M source.py\n"
    wrong_guard = root / runner.GUARD_PATH
    if mismatch == "guard_path":
        wrong_guard = root / "wrong.json"
    with pytest.raises(runner.SessionError):
        runner.preflight(
            root, wrong_guard, root / runner.RUN_DIRECTORY,
            runner.RUN_ID if mismatch != "run_id" else "WP06_6D_SIM_EVAL_SCAN_ENDPOINT_PROBE_RUN_003",
            runner.PARTITION if mismatch != "partition" else "wp06_scan_probe_run_003",
            expected, git_runner=_git_fixture(root, **values),
        )
    assert _pending_guard(root)["state"] == PENDING
    assert not (root / runner.RUN_DIRECTORY).exists()


def test_preflight_rejects_modified_pin_or_packet_before_guard_acquire(tmp_path):
    root = _copy_synthetic_repo(tmp_path)
    source = root / runner.WORLD_PATH
    source.write_bytes(source.read_bytes() + b"\n")
    with pytest.raises(runner.SessionError, match="source pin mismatch"):
        runner.preflight(root, root / runner.GUARD_PATH, root / runner.RUN_DIRECTORY,
                         runner.RUN_ID, runner.PARTITION, "a" * 40,
                         git_runner=_git_fixture(root))
    assert _pending_guard(root)["state"] == PENDING
    assert not (root / runner.RUN_DIRECTORY).exists()


@pytest.mark.parametrize("relative_path", [runner.DECISION_PATH, runner.MANIFEST_PATH])
def test_preflight_rejects_modified_authority_or_manifest_before_guard_acquire(tmp_path, relative_path):
    root = _copy_synthetic_repo(tmp_path)
    target = root / relative_path
    target.write_bytes(target.read_bytes() + b" ")
    with pytest.raises(runner.SessionError):
        runner.preflight(root, root / runner.GUARD_PATH, root / runner.RUN_DIRECTORY,
                         runner.RUN_ID, runner.PARTITION, "a" * 40,
                         git_runner=_git_fixture(root))
    assert _pending_guard(root)["state"] == PENDING
    assert not (root / runner.RUN_DIRECTORY).exists()


def test_guard_manifest_and_evidence_pin_the_same_sources():
    manifest, evidence = _manifest_and_evidence()
    guard = json.loads((ROOT / runner.GUARD_PATH).read_text(encoding="utf-8"))
    assert evidence["source_pins"] == manifest["source_pins"] == guard["context"]["source_pins"]
    for relative, digest in manifest["source_pins"].items():
        assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == digest
    assert guard["state"] == PENDING


def test_service_readiness_accepts_only_exact_world_create_service():
    assert runner._service_is_ready(b"/world/wp06_scan_probe_world/create\n")
    assert not runner._service_is_ready(b"/world/wp06_scan_probe_world/create_extra\n")
    assert not runner._service_is_ready(b"prefix /world/wp06_scan_probe_world/create suffix\n")


@pytest.mark.parametrize("returncode,output,expected", [
    (0, b"Entity creation successful.", True),
    (0, b"Entity creation successful!", False),
    (2, b"Entity creation successful.", False),
])
def test_create_readiness_requires_zero_exit_and_exact_success_bytes(tmp_path, returncode, output, expected):
    raw = tmp_path / "create.log"
    raw.write_bytes(output)
    assert (returncode == 0 and runner.CREATE_SUCCESS in raw.read_bytes()) is expected


def test_readiness_source_has_no_buffered_pipe_readiness_path():
    source = (ROOT / "artifacts/simulation/sim_eval_scan_endpoint_probe_evidence/tools/run_scan_endpoint_probe_run004_session.py").read_text(encoding="utf-8")
    assert ".stdout.read(65536)" not in source
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "Popen":
            assert not any(isinstance(keyword.value, ast.Attribute) and keyword.value.attr == "PIPE"
                           for keyword in node.keywords)
    assert "stdout=log_stream" in source and "stderr=subprocess.STDOUT" in source


def test_service_gate_prevents_create_until_service_is_ready(tmp_path):
    root = _copy_synthetic_repo(tmp_path)
    fake_git = _git_fixture(root)
    processes = []
    calls = []
    server_ref = {}

    def fake_popen(argv, **kwargs):
        calls.append(("popen", list(argv)))
        pid = 41000 + len(processes)
        if argv == runner.BOOTSTRAP_ARGV:
            process = FakeProcess(pid, returncode=None, output_stream=kwargs["stdout"])
            server_ref["process"] = process
        elif argv == runner.CREATE_ARGV:
            assert calls[-2][0] == "service"
            process = FakeProcess(pid, returncode=0, output=runner.CREATE_SUCCESS, output_stream=kwargs["stdout"])
        else:
            raise AssertionError(argv)
        processes.append(process)
        return process

    service_count = 0
    def fake_run(argv, **kwargs):
        nonlocal service_count
        calls.append(("service" if argv == runner.SERVICE_ARGV else "probe", list(argv)))
        if argv == runner.SERVICE_ARGV:
            service_count += 1
            output = b"/world/wp06_scan_probe_world/control\n"
            if service_count > 1:
                output += b"/world/wp06_scan_probe_world/create\n"
            return SimpleNamespace(returncode=0, stdout=output, stderr=b"")
        return SimpleNamespace(returncode=0, stdout=json.dumps(_recorded_probe_result()).encode(), stderr=b"")

    def send_signal(pgid, sig):
        assert pgid == server_ref["process"].pid
        server_ref["process"].returncode = 0

    clock = FakeClock()
    proc_root = tmp_path / "empty-proc"
    proc_root.mkdir()
    record = runner.run_session(
        root, root / runner.GUARD_PATH, root / runner.RUN_DIRECTORY,
        runner.RUN_ID, runner.PARTITION, "a" * 40,
        git_runner=fake_git, command_runner=fake_run, popen_factory=fake_popen,
        pgid_getter=lambda pid: pid, signal_group=send_signal, proc_root=proc_root,
        clock=clock, sleeper=clock.sleep,
    )
    assert record["server"]["readiness"] is True
    assert record["create"]["readiness"] is True
    assert record["probe"]["probe_result"]["outcome"] == "EXACTLY_ONE_MATCH"
    assert record["terminal_outcome"] == "GZ_LASERSCAN_ENDPOINT_OBSERVED_NOT_PINNED"
    assert [kind for kind, _ in calls].count("probe") == 1
    assert record["teardown"]["server"]["outcome"] == "STOPPED"
    assert json.loads((root / runner.GUARD_PATH).read_text())["state"] == CONSUMED


@pytest.mark.parametrize("service_output,create_rc,create_output,expected", [
    (b"/world/wp06_scan_probe_world/control\n", 0, runner.CREATE_SUCCESS, "SERVER_NOT_READY"),
    (b"/world/wp06_scan_probe_world/create\n", 3, runner.CREATE_SUCCESS, "CREATE_NOT_READY"),
    (b"/world/wp06_scan_probe_world/create\n", 0, b"created", "CREATE_NOT_READY"),
])
def test_no_probe_on_service_or_create_failure(tmp_path, service_output, create_rc, create_output, expected):
    root = _copy_synthetic_repo(tmp_path)
    processes = []
    server_ref = {}
    probe_calls = []

    def fake_popen(argv, **kwargs):
        pid = 42000 + len(processes)
        if argv == runner.BOOTSTRAP_ARGV:
            p = FakeProcess(pid, returncode=None, output_stream=kwargs["stdout"])
            server_ref["p"] = p
        else:
            p = FakeProcess(pid, returncode=create_rc, output=create_output, output_stream=kwargs["stdout"])
        processes.append(p)
        return p

    def fake_run(argv, **kwargs):
        if argv == runner.SERVICE_ARGV:
            return SimpleNamespace(returncode=0, stdout=service_output, stderr=b"")
        probe_calls.append(argv)
        return SimpleNamespace(returncode=0, stdout=b"{}", stderr=b"")

    clock = FakeClock()
    def send_signal(pgid, sig):
        server_ref["p"].returncode = 0

    proc_root = tmp_path / "empty-proc"
    proc_root.mkdir()
    record = runner.run_session(
        root, root / runner.GUARD_PATH, root / runner.RUN_DIRECTORY,
        runner.RUN_ID, runner.PARTITION, "a" * 40,
        git_runner=_git_fixture(root), command_runner=fake_run, popen_factory=fake_popen,
        pgid_getter=lambda pid: pid, signal_group=send_signal, proc_root=proc_root,
        clock=clock, sleeper=clock.sleep,
    )
    assert record["terminal_outcome"] == expected
    assert probe_calls == []
    assert json.loads((root / runner.GUARD_PATH).read_text())["state"] == CONSUMED


def test_proc_stat_uses_final_closing_parenthesis_and_zombies_are_separate(tmp_path):
    proc = tmp_path / "proc"
    proc.mkdir()
    (proc / "100").mkdir()
    (proc / "101").mkdir()
    (proc / "100/stat").write_bytes(b"100 (name ) with ) chars) S 1 100 0 0")
    (proc / "101/stat").write_bytes(b"101 (zombie) Z 1 100 0 0")
    snapshot = runner.snapshot_process_group(100, proc_root=proc)
    assert snapshot == {"live_member_pids": [100], "zombie_member_pids": [101]}


def test_teardown_reaped_leader_and_no_live_members_passes(tmp_path):
    proc = FakeProcess(50001, returncode=0)
    proc_root = tmp_path / "proc"
    proc_root.mkdir()
    result = runner.teardown_process_group(
        proc, 50001, owned_pgid=50001, proc_root=proc_root, signal_group=lambda *_: pytest.fail("signal unexpected")
    )
    assert result["outcome"] == "ALREADY_EXITED"
    assert result["leader_returncode"] == 0


def test_teardown_zombie_only_is_not_reported_as_live(tmp_path):
    proc_root = tmp_path / "proc"
    proc_root.mkdir()
    (proc_root / "50002").mkdir()
    (proc_root / "50002/stat").write_bytes(b"50002 (zombie) Z 1 50002 0 0")
    process = FakeProcess(50002, returncode=0)
    result = runner.teardown_process_group(
        process, 50002, owned_pgid=50002, proc_root=proc_root, signal_group=lambda *_: pytest.fail("signal unexpected")
    )
    assert result["outcome"] == "ALREADY_EXITED"
    assert result["final_snapshot"]["live_member_pids"] == []
    assert result["final_snapshot"]["zombie_member_pids"] == [50002]


def test_teardown_live_member_after_sigkill_is_reported_with_pid(tmp_path):
    proc_root = tmp_path / "proc"
    proc_root.mkdir()
    (proc_root / "51000").mkdir()
    (proc_root / "51001").mkdir()
    (proc_root / "51000/stat").write_bytes(b"51000 (leader) S 1 51000 0 0")
    (proc_root / "51001/stat").write_bytes(b"51001 (child) S 1 51000 0 0")
    process = FakeProcess(51000, returncode=None)
    signals = []
    clock = FakeClock()
    result = runner.teardown_process_group(
        process, 51000, owned_pgid=51000, proc_root=proc_root,
        signal_group=lambda pgid, sig: signals.append((pgid, sig)),
        sleeper=clock.sleep, clock=clock,
    )
    assert [sig for _, sig in signals] == [getattr(__import__("signal"), n) for n in runner.TEARDOWN_SIGNALS]
    assert all(pgid == 51000 for pgid, _ in signals)
    assert result["outcome"] == "LIVE_PROCESS_GROUP_AFTER_SIGKILL"
    assert result["final_snapshot"]["live_member_pids"] == [51000, 51001]


def test_unexpected_pgid_is_never_signaled(tmp_path):
    process = FakeProcess(52001, returncode=None)
    signals = []
    result = runner.teardown_process_group(
        process, 52002, owned_pgid=52001, signal_group=lambda *args: signals.append(args),
        proc_root=tmp_path / "empty-proc",
    )
    assert result["outcome"] == "UNEXPECTED_PGID_NO_SIGNAL"
    assert signals == []


def test_run002_and_run003_history_not_added_to_candidate_diff():
    changed = subprocess.run(["git", "-C", str(ROOT), "diff", "--name-only", BASE],
                             check=True, capture_output=True, text=True).stdout.splitlines()
    for path in changed:
        assert "/RUN_002" not in path and "/RUN_003" not in path
    assert "sim_eval_scan_probe.world.sdf" not in changed
    assert "ROBOT_URDF_final.gazebo" not in changed
