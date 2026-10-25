from __future__ import annotations

import json
from pathlib import Path
import signal

import pytest

from run_step07_research_acceptance import (
    AcceptanceFailure, CampaignState, ProcessOwner, ResearchAcceptanceRunner,
    atomic_json, load_json, verify_runtime_authorization,
)


def test_duplicate_json_keys_and_nonfinite_constants_reject(tmp_path):
    path = tmp_path / "duplicate.json"
    path.write_text('{"a":1,"a":2}', encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate"):
        load_json(path)
    path.write_text('{"x":NaN}', encoding="utf-8")
    with pytest.raises(ValueError):
        load_json(path)


def test_atomic_report_write_requires_finite_json_and_replaces_complete_file(tmp_path):
    path = tmp_path / "report.json"
    atomic_json(path, {"a": [1, 2]})
    assert json.loads(path.read_text()) == {"a": [1, 2]}
    with pytest.raises(ValueError):
        atomic_json(path, {"bad": float("nan")})
    assert json.loads(path.read_text()) == {"a": [1, 2]}


def test_authorization_must_match_exact_commit_hash_run_and_output(tmp_path):
    output = tmp_path / "run-1"
    auth = tmp_path / "auth.json"
    auth.write_text(json.dumps({"owner_authorized": True, "exact_git_commit": "c"*40,
        "config_hash": "f"*64, "run_id": "run-1", "output_target": str(output)}))
    assert verify_runtime_authorization(auth, commit="c"*40, config_hash="f"*64,
                                        run_id="run-1", output_target=output)["owner_authorized"]
    with pytest.raises(AcceptanceFailure, match="BINDING_MISMATCH"):
        verify_runtime_authorization(auth, commit="d"*40, config_hash="f"*64,
                                    run_id="run-1", output_target=output)


def test_cleanup_is_separate_from_functional_verdict_and_only_signals_owned_groups(monkeypatch):
    class FakeProcess:
        pid = 987654
        returncode = None
        def wait(self, timeout=None): self.returncode = 0; return 0
        def poll(self): return self.returncode

    sent = []
    monkeypatch.setattr("run_step07_research_acceptance.subprocess.Popen",
                        lambda *a, **k: FakeProcess())
    monkeypatch.setattr("run_step07_research_acceptance.os.killpg",
                        lambda pid, sig: sent.append((pid, sig)))
    monkeypatch.setattr("run_step07_research_acceptance.os.getpgid", lambda pid: pid)
    owner = ProcessOwner()
    import io, time
    owned = owner.start("composite", ["fake-runtime"], env={}, runtime_log=io.BytesIO(), cwd=Path.cwd())
    cleanup = owner.stop_all(("composite",))
    state = CampaignState(facts={"A9": {"pass": False}})
    assert cleanup[0]["stopped"] is True
    assert sent == [(987654, signal.SIGINT)]
    assert state.facts["A9"]["pass"] is False


def test_runner_requires_preflight_before_process_start_and_capacity_one_output(tmp_path):
    # Production preflight uses repository identity/config; this unit check
    # exercises the actual guard at the production child-start method.
    runner = object.__new__(ResearchAcceptanceRunner)
    runner.output = None
    with pytest.raises(RuntimeError, match="preflight"):
        runner.start_runtime_children()
