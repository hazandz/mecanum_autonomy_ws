import json
import hashlib
from pathlib import Path
import subprocess

import pytest

from step07_runtime_guard import (
    AUTH_SCOPE, INTEGRATION_BASE, PARTITION, RUN_ID, acquire_guard,
    load_guard, validate_owner_authorization, validate_seed, validate_source_pins,
)

ROOT = Path(__file__).resolve().parents[4]
GUARD = ROOT / "artifacts/simulation/step07_nav2_baseline_campaign/approval_guards/STEP07_NAV2_BASELINE_RUN_001.json"
RUN001_REVIEW_SHA = "5a44cd9910e9b6d6058d8d2d9252a86f7cf9dcd8"
REVIEW = "a" * 40
AUTH = {"authorization": "OWNER_APPROVED_EXACT_RUN", "scope": AUTH_SCOPE,
        "run_id": RUN_ID, "review_commit": REVIEW, "integration_base": INTEGRATION_BASE}


def seed():
    return {"schema_version": "1.0", "run_id": RUN_ID,
            "state": "PENDING_EXACT_INTEGRATION_AND_USER_AUTHORIZATION",
            "capacity": 1, "acquisition_count": 0, "runtime_authorization": "NOT_GRANTED",
            "integration_base": INTEGRATION_BASE,
            "architecture_sha256": "432eeac363a595cfcf7e81c4b66054fb674dba140a2ef3cffecd617ab8136204",
            "partition": PARTITION}


def _git_blob(root: Path, commit: str, relative: str) -> bytes:
    """Read a pinned historical blob; never fall back to checkout bytes."""
    result = subprocess.run(
        ["git", "show", f"{commit}:{relative}"], cwd=root,
        check=True, capture_output=True,
    )
    return result.stdout


def _validate_run001_historical_source_pins(root: Path, guard: dict) -> None:
    pins = guard.get("source_pins")
    if type(pins) is not dict or not pins:
        raise ValueError("HISTORICAL_SOURCE_PINS_MISSING")
    for relative, expected in pins.items():
        if (type(relative) is not str or type(expected) is not dict
                or set(expected) != {"sha256", "size_bytes"}):
            raise ValueError("HISTORICAL_SOURCE_PIN_ROW_INVALID")
        path = Path(relative)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("HISTORICAL_SOURCE_PIN_PATH_INVALID")
        raw = _git_blob(root, RUN001_REVIEW_SHA, relative)
        if (hashlib.sha256(raw).hexdigest() != expected["sha256"]
                or len(raw) != expected["size_bytes"]):
            raise ValueError(f"HISTORICAL_SOURCE_PIN_MISMATCH:{relative}")


def test_committed_guard_is_capacity_one_pending_seed():
    document = load_guard(GUARD)
    validate_seed(document, run_id=RUN_ID, review_commit=REVIEW, integration_base=INTEGRATION_BASE,
                  architecture_sha256=document["architecture_sha256"], partition=PARTITION)
    assert document["state"] == "PENDING_EXACT_INTEGRATION_AND_USER_AUTHORIZATION"
    assert document["capacity"] == 1 and document["acquisition_count"] == 0
    assert document["runtime_authorization"] == "NOT_GRANTED"
    _validate_run001_historical_source_pins(ROOT, document)
    assert GUARD.read_bytes() == _git_blob(
        ROOT, RUN001_REVIEW_SHA,
        "artifacts/simulation/step07_nav2_baseline_campaign/approval_guards/STEP07_NAV2_BASELINE_RUN_001.json",
    )


def test_run001_historical_pins_ignore_current_run002_contract_bytes():
    document = load_guard(GUARD)
    contract = "ros2_ws/src/mecanum_nav_bringup/test/test_sim_eval_tf_ekf_runtime_contract.py"
    current = (ROOT / contract).read_bytes()
    historical = _git_blob(ROOT, RUN001_REVIEW_SHA, contract)
    assert current != historical
    _validate_run001_historical_source_pins(ROOT, document)


def test_run001_historical_blob_mismatch_fails_closed():
    document = load_guard(GUARD)
    relative = "ros2_ws/src/mecanum_nav_bringup/test/test_sim_eval_tf_ekf_runtime_contract.py"
    document["source_pins"][relative]["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="HISTORICAL_SOURCE_PIN_MISMATCH"):
        _validate_run001_historical_source_pins(ROOT, document)


@pytest.mark.parametrize("commit,path", [
    ("0" * 40, "ros2_ws/src/mecanum_nav_bringup/test/test_sim_eval_tf_ekf_runtime_contract.py"),
    (RUN001_REVIEW_SHA, "missing/historical/path"),
])
def test_run001_missing_historical_commit_or_path_fails_closed(commit, path, monkeypatch):
    document = load_guard(GUARD)
    document["source_pins"] = {path: {"sha256": "0" * 64, "size_bytes": 0}}
    monkeypatch.setattr("test_step07_runtime_guard.RUN001_REVIEW_SHA", commit)
    with pytest.raises(subprocess.CalledProcessError):
        _validate_run001_historical_source_pins(ROOT, document)


def test_run002_generic_source_pin_validation_uses_current_worktree_bytes(tmp_path):
    from step07_run002_runtime_guard import validate_source_pins as validate_current

    source = tmp_path / "current.txt"
    source.write_bytes(b"run002-current")
    pin = {"current.txt": {"sha256": hashlib.sha256(b"run002-current").hexdigest(),
                           "size_bytes": len(b"run002-current")}}
    validate_current(tmp_path, pin)
    source.write_bytes(b"changed")
    with pytest.raises(ValueError, match="SOURCE_PIN_MISMATCH"):
        validate_current(tmp_path, pin)


@pytest.mark.parametrize("field,value", [
    ("authorization", ""), ("scope", "wrong"), ("run_id", "wrong"),
    ("review_commit", "b" * 40), ("integration_base", "c" * 40),
])
def test_bad_authorization_fails_before_guard_or_evidence_mutation(tmp_path, field, value):
    guard_path = tmp_path / "guard.json"
    seed_bytes = json.dumps(seed(), sort_keys=True, separators=(",", ":")).encode()
    guard_path.write_bytes(seed_bytes)
    evidence = tmp_path / "run001"
    bad = dict(AUTH); bad[field] = value
    with pytest.raises(ValueError):
        validate_owner_authorization(**bad, expected_run_id=RUN_ID,
            expected_review_commit=REVIEW, expected_integration_base=INTEGRATION_BASE)
    assert guard_path.read_bytes() == seed_bytes
    assert not evidence.exists()
    assert not guard_path.with_suffix(".json.lock").exists()


def test_valid_authorization_consumes_only_when_acquire_is_explicit(tmp_path):
    guard_path = tmp_path / "guard.json"
    guard = seed()
    guard_path.write_bytes(json.dumps(guard, sort_keys=True, separators=(",", ":")).encode())
    metadata = validate_owner_authorization(**AUTH, expected_run_id=RUN_ID,
        expected_review_commit=REVIEW, expected_integration_base=INTEGRATION_BASE)
    assert guard_path.read_bytes() == json.dumps(guard, sort_keys=True, separators=(",", ":")).encode()
    consumed = acquire_guard(guard_path, guard, metadata, review_commit=REVIEW, integration_base=INTEGRATION_BASE)
    assert consumed["state"] == "CONSUMED"
    assert consumed["acquisition_count"] == 1
    assert consumed["runtime_authorization"] == "GRANTED_FOR_THIS_EXACT_RUN_ONLY"
    for key, value in metadata.items():
        assert consumed[key] == value
    assert guard_path.with_suffix(".json.lock").exists()
