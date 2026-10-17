"""Offline-only tests for the independent Run 002 guard/supervisor pair."""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[4]
TOOLS = ROOT / "artifacts/simulation/sim_eval_scan_endpoint_probe_evidence/tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
import scan_endpoint_probe_run002_runtime_guard as guard
import run_scan_endpoint_probe_run002_once as supervisor

RUN001_FILES = (
    "artifacts/simulation/sim_eval_scan_endpoint_probe_evidence/approval_guards/WP06_6D_SIM_EVAL_SCAN_ENDPOINT_PROBE_RUN_001.json",
    "artifacts/simulation/sim_eval_scan_endpoint_probe_evidence/tools/scan_endpoint_probe_runtime_guard.py",
    "artifacts/simulation/sim_eval_scan_endpoint_probe_evidence/tools/run_scan_endpoint_probe_once.py",
    "docs/governance/evidence/WP-06_SIM_EVAL_SCAN_ENDPOINT_PROBE_RUNTIME_GUARD_MANIFEST.json",
)
RUN001_MANIFEST = RUN001_FILES[-1]


def _write(root: Path, rel: str, content: bytes) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def _synthetic_repository(tmp_path: Path) -> Path:
    root = tmp_path / "synthetic-repo"
    paths = {
        guard.AUTHORITY_PACKET["path"],
        supervisor.MANIFEST_PATH,
        guard.GUARD_PATH,
        supervisor.GUARD_SOURCE_PATH,
        supervisor.SUPERVISOR_SOURCE_PATH,
        *(pin["path"] for pin in guard.SOURCE_PINS.values()),
    }
    for rel in paths:
        _write(root, rel, (ROOT / rel).read_bytes())
    return root


class ExactIntegratedGit:
    """Synthetic Git command runner; it never starts Git or a runtime process."""

    def __init__(self, root: Path, commit: str, *, head: str | None = None, integration: str | None = None):
        self.root = root
        self.commit = commit
        self.head = head if head is not None else commit
        self.integration = integration if integration is not None else commit
        self.missing_or_altered: dict[str, bytes] = {}

    def __call__(self, command, **kwargs):
        assert kwargs.get("shell") is False
        args = command[3:]
        if args == ["remote", "get-url", "origin"]:
            return SimpleNamespace(returncode=0, stdout=b"https://github.com/hazandz/mecanum_autonomy_ws.git\n")
        if args == ["rev-parse", "HEAD"]:
            return SimpleNamespace(returncode=0, stdout=(self.head + "\n").encode())
        if args == ["rev-parse", "origin/integration/implementation"]:
            return SimpleNamespace(returncode=0, stdout=(self.integration + "\n").encode())
        if args == ["status", "--short"]:
            return SimpleNamespace(returncode=0, stdout=b"")
        if len(args) == 2 and args[0] == "show":
            commit, rel = args[1].split(":", 1)
            if commit != self.commit:
                return SimpleNamespace(returncode=1, stdout=b"")
            if rel in self.missing_or_altered:
                return SimpleNamespace(returncode=0, stdout=self.missing_or_altered[rel])
            path = self.root / rel
            return SimpleNamespace(returncode=0, stdout=path.read_bytes() if path.is_file() else b"")
        raise AssertionError(f"unexpected synthetic git command: {command!r}")


def _fake_probe(command, **kwargs):
    assert kwargs.get("shell") is False
    assert command == supervisor._expected_command(kwargs["cwd"])
    return SimpleNamespace(returncode=0, stdout='{"outcome":"EXACTLY_ONE_MATCH"}', stderr="")


def _call(root, git, probe=_fake_probe, **overrides):
    expected = overrides.pop("expected", "a" * 40)
    return supervisor.run_once(
        root,
        Path(overrides.pop("guard", root / guard.GUARD_PATH)),
        Path(overrides.pop("run_directory", root / "artifacts/simulation/sim_eval_scan_endpoint_probe_evidence/runs" / guard.RUN_ID)),
        overrides.pop("run_id", guard.RUN_ID),
        overrides.pop("partition", guard.GZ_PARTITION),
        expected,
        git_runner=git,
        probe_runner=probe,
    )


def test_world_gravity_is_corrected_at_world_scope_and_run001_is_untouched():
    world = Path("ros2_ws/src/ROBOT_URDF_final_description/launch/sim_eval_scan_probe.world.sdf")
    import xml.etree.ElementTree as ET
    root = ET.fromstring((ROOT / world).read_bytes())
    selected = root.find("world")
    assert selected is not None and selected.findtext("gravity") == "0 0 -9.8"
    assert selected.find("physics/gravity") is None
    for rel in RUN001_FILES:
        base_bytes = subprocess.run(["git", "-C", str(ROOT), "show", f"97aeecdff640187ac0b3ad152a22befe442a1a2f:{rel}"], capture_output=True, check=True).stdout
        assert (ROOT / rel).read_bytes() == base_bytes


def test_run002_seed_and_manifest_are_canonical_pending_non_authorization():
    evidence_path = "docs/governance/evidence/WP-06_SIM_EVAL_SCAN_ENDPOINT_PROBE_DETERMINISTIC_BOOTSTRAP_REMEDIATION_L2_EVIDENCE.json"
    for rel in (guard.GUARD_PATH, supervisor.MANIFEST_PATH, RUN001_MANIFEST, evidence_path):
        raw = (ROOT / rel).read_bytes()
        assert not raw.startswith(b"\xef\xbb\xbf") and not raw.endswith(b"\n")
        parsed = json.loads(raw.decode("utf-8"), object_pairs_hook=guard._pairs_no_duplicates)
        assert guard.canonical_json_bytes(parsed) == raw
    seed = guard.read_canonical_record(ROOT / guard.GUARD_PATH)
    assert seed == {"capacity": 1, "context": guard.GUARD_CONTEXT, "state": guard.PENDING, "version": 1}
    manifest = json.loads((ROOT / supervisor.MANIFEST_PATH).read_text(encoding="utf-8"))
    assert manifest == supervisor._expected_manifest(ROOT)
    assert manifest["runtime_authorized"] is False
    assert manifest["run_id"] == "WP06_6D_SIM_EVAL_SCAN_ENDPOINT_PROBE_RUN_002"


def test_guard_consumes_exact_run002_once_and_rejects_run001_path(tmp_path):
    root = tmp_path / "guard-repo"
    seed_path = root / guard.GUARD_PATH
    _write(root, guard.GUARD_PATH, (ROOT / guard.GUARD_PATH).read_bytes())
    _write(root, guard.AUTHORITY_PACKET["path"], (ROOT / guard.AUTHORITY_PACKET["path"]).read_bytes())
    consumed = guard.consume_run002_guard(root, seed_path)
    assert consumed["state"] == guard.CONSUMED
    with pytest.raises(guard.GuardError):
        guard.consume_run002_guard(root, seed_path)
    run001 = root / RUN001_FILES[0]
    _write(root, RUN001_FILES[0], b"{}")
    with pytest.raises(guard.GuardError):
        guard.consume_run002_guard(root, run001)


def test_guard_rejects_authority_path_or_context_mismatch_without_consumption(tmp_path):
    root = tmp_path / "context-repo"
    seed_path = root / guard.GUARD_PATH
    _write(root, guard.GUARD_PATH, (ROOT / guard.GUARD_PATH).read_bytes())
    _write(root, guard.AUTHORITY_PACKET["path"], (ROOT / guard.AUTHORITY_PACKET["path"]).read_bytes())
    wrong = json.loads(json.dumps(guard.GUARD_CONTEXT))
    wrong["authority_packet"]["path"] = "docs/wrong.md"
    with pytest.raises(guard.GuardError):
        guard.consume_run002_guard(root, seed_path, wrong)
    assert guard.read_canonical_record(seed_path)["state"] == guard.PENDING
    duplicate = root / "duplicate.json"
    duplicate.write_bytes(b'{"capacity":1,"capacity":1}')
    with pytest.raises(guard.GuardError):
        guard.read_canonical_record(duplicate)


def test_exact_synthetic_integration_consumes_only_run002(tmp_path):
    root = _synthetic_repository(tmp_path)
    git = ExactIntegratedGit(root, "a" * 40)
    assert _call(root, git) == 0  # exact probe observation is not an authorization claim
    assert guard.read_canonical_record(root / guard.GUARD_PATH)["state"] == guard.CONSUMED
    run_record = json.loads((root / "artifacts/simulation/sim_eval_scan_endpoint_probe_evidence/runs" / guard.RUN_ID / "probe_run_record.json").read_bytes())
    assert run_record["guard_state_after_acquire"] == guard.CONSUMED
    assert run_record["probe_result"] == {"outcome": "EXACTLY_ONE_MATCH"}
    with pytest.raises(supervisor.SupervisorPreflightError):
        _call(root, git)


@pytest.mark.parametrize("mode", ["head", "integration", "authority", "manifest", "source_pin"])
def test_all_preflight_mismatches_fail_before_consumption(tmp_path, mode):
    root = _synthetic_repository(tmp_path)
    expected = "a" * 40
    git = ExactIntegratedGit(root, expected)
    if mode == "head":
        git.head = "b" * 40
    elif mode == "integration":
        git.integration = "b" * 40
    elif mode == "authority":
        rel = guard.AUTHORITY_PACKET["path"]
        altered = (root / rel).read_bytes() + b"x"
        _write(root, rel, altered)
        git.missing_or_altered[rel] = altered
    elif mode == "manifest":
        rel = supervisor.MANIFEST_PATH
        data = json.loads((root / rel).read_bytes())
        data["command_literal"] = "wrong-command"
        altered = guard.canonical_json_bytes(data)
        _write(root, rel, altered)
        git.missing_or_altered[rel] = altered
    elif mode == "source_pin":
        rel = next(iter(guard.SOURCE_PINS.values()))["path"]
        altered = (root / rel).read_bytes() + b"x"
        _write(root, rel, altered)
        git.missing_or_altered[rel] = altered
    with pytest.raises(supervisor.SupervisorPreflightError):
        _call(root, git, expected=expected)
    assert guard.read_canonical_record(root / guard.GUARD_PATH)["state"] == guard.PENDING
    assert not (root / "artifacts/simulation/sim_eval_scan_endpoint_probe_evidence/runs" / guard.RUN_ID).exists()


@pytest.mark.parametrize("field,value", [
    ("run_id", "WP06_6D_SIM_EVAL_SCAN_ENDPOINT_PROBE_RUN_001"),
    ("partition", "wrong_partition"),
    ("guard", Path("/tmp/run001.json")),
])
def test_wrong_run_identity_partition_or_guard_fails_before_acquire(tmp_path, field, value):
    root = _synthetic_repository(tmp_path)
    options = {field: value}
    with pytest.raises(supervisor.SupervisorPreflightError):
        _call(root, ExactIntegratedGit(root, "a" * 40), **options)
    assert guard.read_canonical_record(root / guard.GUARD_PATH)["state"] == guard.PENDING


def test_wrong_expected_commit_and_existing_run_directory_fail_closed(tmp_path):
    root = _synthetic_repository(tmp_path)
    with pytest.raises(supervisor.SupervisorPreflightError):
        _call(root, ExactIntegratedGit(root, "a" * 40), expected="not-a-commit")
    run_dir = root / "artifacts/simulation/sim_eval_scan_endpoint_probe_evidence/runs" / guard.RUN_ID
    run_dir.mkdir(parents=True)
    with pytest.raises(supervisor.SupervisorPreflightError):
        _call(root, ExactIntegratedGit(root, "a" * 40))
    assert guard.read_canonical_record(root / guard.GUARD_PATH)["state"] == guard.PENDING


@pytest.mark.parametrize("failure", ["timeout", "interruption", "error"])
def test_post_consumption_timeout_or_error_never_restores_capacity(tmp_path, failure):
    root = _synthetic_repository(tmp_path)
    def fail(*args, **kwargs):
        if failure == "timeout":
            raise subprocess.TimeoutExpired(args[0], kwargs["timeout"])
        if failure == "interruption":
            raise KeyboardInterrupt()
        raise RuntimeError("synthetic post-consumption failure")
    if failure == "interruption":
        with pytest.raises(KeyboardInterrupt):
            _call(root, ExactIntegratedGit(root, "a" * 40), probe=fail)
    elif failure == "error":
        with pytest.raises(RuntimeError):
            _call(root, ExactIntegratedGit(root, "a" * 40), probe=fail)
    else:
        assert _call(root, ExactIntegratedGit(root, "a" * 40), probe=fail) == 1
    assert guard.read_canonical_record(root / guard.GUARD_PATH)["state"] == guard.CONSUMED


def test_source_boundary_is_offline_only_and_does_not_reuse_run001_or_contact_guard():
    for rel in ("artifacts/simulation/sim_eval_scan_endpoint_probe_evidence/tools/scan_endpoint_probe_run002_runtime_guard.py", supervisor.SUPERVISOR_SOURCE_PATH):
        text = (ROOT / rel).read_text(encoding="utf-8")
        tree = ast.parse(text)
        imports = {alias.name for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom)) for alias in node.names}
        assert not any(name == "rclpy" or name.startswith("rclpy.") or name == "ros_gz_bridge" for name in imports)
        assert "contact_producer_evidence" not in text
        assert "scan_endpoint_probe_runtime_guard" not in text
        assert "scan_endpoint_probe_once" not in text
        assert "shell=True" not in text and "subprocess.Popen" not in text
    supervisor_text = Path(ROOT / supervisor.SUPERVISOR_SOURCE_PATH).read_text(encoding="utf-8")
    assert "subprocess.run" in supervisor_text
    assert 'shell=False' in supervisor_text
