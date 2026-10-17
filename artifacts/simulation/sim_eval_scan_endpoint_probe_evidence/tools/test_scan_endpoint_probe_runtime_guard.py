from __future__ import annotations

import importlib.util
import hashlib
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


RUN001_PATH = "artifacts/simulation/sim_eval_scan_endpoint_probe_evidence/approval_guards/WP06_6D_SIM_EVAL_SCAN_ENDPOINT_PROBE_RUN_001.json"
RUN002_PATH = "artifacts/simulation/sim_eval_scan_endpoint_probe_evidence/approval_guards/WP06_6D_SIM_EVAL_SCAN_ENDPOINT_PROBE_RUN_002.json"
RUN002_AUTHORITY = {
    "path": "docs/governance/decisions/WP-06_SIM_EVAL_SCAN_ENDPOINT_PROBE_DETERMINISTIC_BOOTSTRAP_REMEDIATION_L2_DECISION.md",
    "sha256": "580773194d810da301474632038db15f1a1720aafa040450bcf2974677e34f1d",
}


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


def test_run001_guard_is_unchanged_from_exact_base():
    base = "be5f63e7a01be0bca0b838e1ae5265bbb7145be8"
    expected = subprocess.run(
        ["git", "-C", str(ROOT), "show", f"{base}:{RUN001_PATH}"],
        capture_output=True,
        check=True,
    ).stdout
    assert (ROOT / RUN001_PATH).read_bytes() == expected


def test_run002_seed_is_canonical_pending_capacity_one_and_not_authorization():
    path = ROOT / RUN002_PATH
    raw = path.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf")
    assert not raw.endswith(b"\n")
    record = guard.read_canonical_record(path)
    assert set(record) == {"capacity", "context", "state", "version"}
    assert record["capacity"] == 1 and type(record["capacity"]) is int
    assert record["version"] == 1 and type(record["version"]) is int
    assert record["state"] == "PENDING_EXACT_INTEGRATION_AND_USER_AUTHORIZATION"
    context = record["context"]
    assert context["run_id"] == "WP06_6D_SIM_EVAL_SCAN_ENDPOINT_PROBE_RUN_002"
    assert context["gz_partition"] == "wp06_scan_probe_run_002"
    assert context["world_name"] == "wp06_scan_probe_world"
    assert context["candidate_runtime_authorization"] is False
    assert context["owner_only_runtime_authorization_required_after_integration"] is True
    assert context["expected_integration_commit_status"] == "MUST_BE_SUPPLIED_AS_EXACT_40_HEX_AFTER_INTEGRATION_AND_OWNER_AUTHORIZATION"
    assert context["mismatch_policy"] == "FAIL_CLOSED"
    assert context["retry_after_consumption"] is False
    assert context["bootstrap_readiness_evidence"] == "ros_gz_sim create must log exact line: Entity creation successful."
    assert context["authority_packet"] == RUN002_AUTHORITY
    assert context["expected_gz_type"] == "gz.msgs.LaserScan"
    assert context["future_ros_boundary"] == "GZ_TO_ROS /scan sensor_msgs/msg/LaserScan"
    assert context["command_literal"] == (
        "env GZ_PARTITION=wp06_scan_probe_run_002 "
        "PYTHONPATH={repo_root}/ros2_ws/src/mecanum_nav_bringup "
        "python3 -m mecanum_nav_bringup.sim_eval_scan_endpoint_probe"
    )
    source_pins = context["source_pins"]
    assert set(source_pins) == {
        "bootstrap_launch", "gazebo_source", "probe_descriptor", "probe_module", "probe_world"
    }
    for source in source_pins.values():
        assert hashlib.sha256((ROOT / source["path"]).read_bytes()).hexdigest() == source["sha256"]
    assert not (ROOT / "artifacts/simulation/sim_eval_scan_endpoint_probe_evidence/runs/WP06_6D_SIM_EVAL_SCAN_ENDPOINT_PROBE_RUN_002").exists()
