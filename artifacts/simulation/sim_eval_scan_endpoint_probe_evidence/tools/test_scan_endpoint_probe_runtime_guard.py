from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[4]
TOOLS = ROOT / "artifacts/simulation/sim_eval_scan_endpoint_probe_evidence/tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import scan_endpoint_probe_runtime_guard as guard
import run_scan_endpoint_probe_once as supervisor


def _write(root: Path, relative: str, content: bytes) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def _synthetic_repository(tmp_path: Path) -> Path:
    root = tmp_path / "repository"
    paths = [
        guard.AUTHORITY_PACKET["path"],
        supervisor.MANIFEST_PATH,
        supervisor.GUARD_PATH,
        supervisor.GUARD_SOURCE_PATH,
        supervisor.SUPERVISOR_SOURCE_PATH,
        *(entry["path"] for entry in guard.SOURCE_PINS.values()),
    ]
    for relative in paths:
        source = ROOT / relative
        _write(root, relative, source.read_bytes())
    return root


class _ExactGit:
    def __init__(self, root: Path, commit: str, *, head: str | None = None, integration: str | None = None, missing: str | None = None):
        self.root = root
        self.commit = commit
        self.head = head or commit
        self.integration = integration or commit
        self.missing = missing

    def __call__(self, command, **kwargs):
        args = command[3:]
        if args == ["rev-parse", "HEAD"]:
            return SimpleNamespace(returncode=0, stdout=self.head.encode())
        if args == ["rev-parse", "origin/integration/implementation"]:
            return SimpleNamespace(returncode=0, stdout=self.integration.encode())
        if args[0] == "show":
            _, reference = args
            commit, relative = reference.split(":", 1)
            if commit != self.commit or relative == self.missing:
                return SimpleNamespace(returncode=1, stdout=b"")
            return SimpleNamespace(returncode=0, stdout=(self.root / relative).read_bytes())
        raise AssertionError(command)


def _success_probe(command, **kwargs):
    assert kwargs["shell"] is False
    assert command[0] == "env"
    return SimpleNamespace(returncode=0, stdout='{"outcome":"EXACTLY_ONE_MATCH"}', stderr="")


def test_guard_seed_is_pending_canonical_and_refuses_second_acquire(tmp_path):
    record = guard.read_canonical_record(ROOT / supervisor.GUARD_PATH)
    assert record["state"] == guard.PENDING
    copied = tmp_path / "guard.json"
    copied.write_bytes((ROOT / supervisor.GUARD_PATH).read_bytes())
    guard.consume_pending_guard(copied, guard.GUARD_CONTEXT)
    assert guard.read_canonical_record(copied)["state"] == guard.CONSUMED
    with pytest.raises(guard.GuardError):
        guard.consume_pending_guard(copied, guard.GUARD_CONTEXT)


def test_guard_and_manifest_reject_duplicate_keys_and_require_canonical_utf8_bytes(tmp_path):
    guard_path = tmp_path / "guard.json"
    guard_path.write_bytes(b'{"a":1,"a":2}')
    with pytest.raises(guard.GuardError):
        guard.read_canonical_record(guard_path)
    for relative in (supervisor.GUARD_PATH, supervisor.MANIFEST_PATH):
        raw = (ROOT / relative).read_bytes()
        assert not raw.startswith(b"\xef\xbb\xbf")
        assert not raw.endswith(b"\n")
        decoded = json.loads(raw)
        assert json.dumps(decoded, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8") == raw


@pytest.mark.parametrize("field", ["authority_packet", "command_literal", "gz_partition", "run_id", "source_pins"])
def test_guard_rejects_every_context_mismatch(tmp_path, field):
    copied = tmp_path / "guard.json"
    copied.write_bytes((ROOT / supervisor.GUARD_PATH).read_bytes())
    changed = json.loads(json.dumps(guard.GUARD_CONTEXT))
    changed[field] = "mismatch"
    with pytest.raises(guard.GuardError):
        guard.consume_pending_guard(copied, changed)
    assert guard.read_canonical_record(copied)["state"] == guard.PENDING


def test_f02_authority_packet_byte_change_blocks_before_guard_consumption(tmp_path):
    root = _synthetic_repository(tmp_path)
    packet = root / guard.AUTHORITY_PACKET["path"]
    packet.write_bytes(packet.read_bytes() + b"x")
    expected = "a" * 40
    with pytest.raises(guard.GuardError):
        supervisor.run_once(root, root / supervisor.GUARD_PATH, root / "run", expected, git_runner=_ExactGit(root, expected), probe_runner=_success_probe)
    assert guard.read_canonical_record(root / supervisor.GUARD_PATH)["state"] == guard.PENDING
    assert not (root / "run").exists()


@pytest.mark.parametrize("mode", ["review_head", "integration_ref", "missing_integrated_candidate"])
def test_f03_nonintegrated_or_review_context_blocks_before_acquire(tmp_path, mode):
    root = _synthetic_repository(tmp_path)
    expected = "a" * 40
    kwargs = {"head": expected, "integration": expected}
    if mode == "review_head":
        kwargs["head"] = "b" * 40
    elif mode == "integration_ref":
        kwargs["integration"] = "b" * 40
    else:
        kwargs["missing"] = supervisor.GUARD_SOURCE_PATH
    with pytest.raises(supervisor.SupervisorPreflightError):
        supervisor.run_once(root, root / supervisor.GUARD_PATH, root / "run", expected, git_runner=_ExactGit(root, expected, **kwargs), probe_runner=_success_probe)
    assert guard.read_canonical_record(root / supervisor.GUARD_PATH)["state"] == guard.PENDING
    assert not (root / "run").exists()


def test_exact_integration_fixture_consumes_atomically_before_fake_probe(tmp_path):
    root = _synthetic_repository(tmp_path)
    expected = "a" * 40
    result = supervisor.run_once(root, root / supervisor.GUARD_PATH, root / "run", expected, git_runner=_ExactGit(root, expected), probe_runner=_success_probe)
    assert result == 0
    assert guard.read_canonical_record(root / supervisor.GUARD_PATH)["state"] == guard.CONSUMED
    assert json.loads((root / "run/probe_run_record.json").read_text(encoding="utf-8"))["guard_state_after_acquire"] == guard.CONSUMED


@pytest.mark.parametrize("failure", ["timeout", "interruption"])
def test_timeout_and_interruption_fixtures_leave_guard_consumed(tmp_path, failure):
    root = _synthetic_repository(tmp_path)
    expected = "a" * 40
    if failure == "timeout":
        def fake_probe(*args, **kwargs):
            raise subprocess.TimeoutExpired(args[0], kwargs["timeout"])
        assert supervisor.run_once(root, root / supervisor.GUARD_PATH, root / "run", expected, git_runner=_ExactGit(root, expected), probe_runner=fake_probe) == 1
    else:
        def fake_probe(*args, **kwargs):
            raise KeyboardInterrupt()
        with pytest.raises(KeyboardInterrupt):
            supervisor.run_once(root, root / supervisor.GUARD_PATH, root / "run", expected, git_runner=_ExactGit(root, expected), probe_runner=fake_probe)
    assert guard.read_canonical_record(root / supervisor.GUARD_PATH)["state"] == guard.CONSUMED


def test_static_scope_never_imports_or_reuses_contact_guard_or_runtime_processes():
    combined = (ROOT / supervisor.GUARD_SOURCE_PATH).read_text(encoding="utf-8") + (ROOT / supervisor.SUPERVISOR_SOURCE_PATH).read_text(encoding="utf-8")
    for forbidden in ("contact_producer_evidence", "Popen", "shell=True", "ros2 ", "gz topic -e", "ros_gz_bridge", "rclpy"):
        assert forbidden not in combined
    assert "subprocess.run" in (ROOT / supervisor.SUPERVISOR_SOURCE_PATH).read_text(encoding="utf-8")
