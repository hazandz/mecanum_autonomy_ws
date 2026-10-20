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
RUN002_REVIEW_SHA = "6d730bd54d7f99429ee4832a3f6f96beffae020f"
RUN003_REVIEW_SHA = "fdc0e299515bda2286832aabec635948629517b5"
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


def _strict_git_json(root: Path, commit: str, relative: str) -> dict:
    raw = _git_blob(root, commit, relative)
    value = json.loads(raw.decode("utf-8"), object_pairs_hook=lambda pairs: _no_duplicate_pairs(pairs))
    if raw != json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"):
        raise ValueError("HISTORICAL_GUARD_NOT_CANONICAL")
    return value


def _no_duplicate_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"DUPLICATE_JSON_KEY:{key}")
        result[key] = value
    return result


def _validate_historical_pins_at_commit(root: Path, guard: dict, commit: str) -> None:
    pins = guard.get("source_pins")
    if type(pins) is not dict or not pins:
        raise ValueError("HISTORICAL_SOURCE_PINS_MISSING")
    for relative, expected in pins.items():
        if type(expected) is not dict or set(expected) != {"sha256", "size_bytes"}:
            raise ValueError("HISTORICAL_SOURCE_PIN_ROW_INVALID")
        raw = _git_blob(root, commit, relative)
        if hashlib.sha256(raw).hexdigest() != expected["sha256"] or len(raw) != expected["size_bytes"]:
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


def test_run002_historical_guard_and_source_pins_use_its_exact_git_commit():
    guard_path = "artifacts/simulation/step07_nav2_baseline_campaign/approval_guards/STEP07_NAV2_BASELINE_RUN_002.json"
    historical_guard = _strict_git_json(ROOT, RUN002_REVIEW_SHA, guard_path)
    assert historical_guard["run_id"] == "STEP07_NAV2_BASELINE_RUN_002"
    _validate_historical_pins_at_commit(ROOT, historical_guard, RUN002_REVIEW_SHA)


def test_run002_historical_pins_ignore_current_run003_worktree_bytes():
    guard_path = "artifacts/simulation/step07_nav2_baseline_campaign/approval_guards/STEP07_NAV2_BASELINE_RUN_002.json"
    historical_guard = _strict_git_json(ROOT, RUN002_REVIEW_SHA, guard_path)
    relative = "ros2_ws/src/mecanum_nav_bringup/test/test_sim_eval_tf_ekf_runtime_contract.py"
    current = (ROOT / relative).read_bytes()
    historical = _git_blob(ROOT, RUN002_REVIEW_SHA, relative)
    assert current != historical
    _validate_historical_pins_at_commit(ROOT, historical_guard, RUN002_REVIEW_SHA)


def test_run002_historical_pin_mismatch_or_missing_blob_fails_closed():
    guard_path = "artifacts/simulation/step07_nav2_baseline_campaign/approval_guards/STEP07_NAV2_BASELINE_RUN_002.json"
    historical_guard = _strict_git_json(ROOT, RUN002_REVIEW_SHA, guard_path)
    relative = next(iter(historical_guard["source_pins"]))
    mutated = json.loads(json.dumps(historical_guard))
    mutated["source_pins"][relative]["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="HISTORICAL_SOURCE_PIN_MISMATCH"):
        _validate_historical_pins_at_commit(ROOT, mutated, RUN002_REVIEW_SHA)
    with pytest.raises(subprocess.CalledProcessError):
        _git_blob(ROOT, "0" * 40, relative)
    with pytest.raises(subprocess.CalledProcessError):
        _git_blob(ROOT, RUN002_REVIEW_SHA, "missing/historical/path")


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


def test_run003_historical_guard_and_source_pins_use_exact_git_blobs():
    guard_path = "artifacts/simulation/step07_nav2_baseline_campaign/approval_guards/STEP07_NAV2_BASELINE_RUN_003.json"
    historical_guard = _strict_git_json(ROOT, RUN003_REVIEW_SHA, guard_path)
    assert historical_guard["run_id"] == "STEP07_NAV2_BASELINE_RUN_003"
    _validate_historical_pins_at_commit(ROOT, historical_guard, RUN003_REVIEW_SHA)
    assert (ROOT / guard_path).read_bytes() == _git_blob(ROOT, RUN003_REVIEW_SHA, guard_path)


def test_run003_current_candidate_does_not_change_historical_pins():
    guard_path = "artifacts/simulation/step07_nav2_baseline_campaign/approval_guards/STEP07_NAV2_BASELINE_RUN_003.json"
    historical_guard = _strict_git_json(ROOT, RUN003_REVIEW_SHA, guard_path)
    relative = "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_runtime_guard.py"
    current = (ROOT / relative).read_bytes()
    historical = _git_blob(ROOT, RUN003_REVIEW_SHA, relative)
    assert current != historical
    _validate_historical_pins_at_commit(ROOT, historical_guard, RUN003_REVIEW_SHA)


def test_run003_historical_pin_mismatch_or_missing_blob_fails_closed():
    guard_path = "artifacts/simulation/step07_nav2_baseline_campaign/approval_guards/STEP07_NAV2_BASELINE_RUN_003.json"
    historical_guard = _strict_git_json(ROOT, RUN003_REVIEW_SHA, guard_path)
    relative = next(iter(historical_guard["source_pins"]))
    mutated = json.loads(json.dumps(historical_guard))
    mutated["source_pins"][relative]["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="HISTORICAL_SOURCE_PIN_MISMATCH"):
        _validate_historical_pins_at_commit(ROOT, mutated, RUN003_REVIEW_SHA)
    with pytest.raises(subprocess.CalledProcessError):
        _git_blob(ROOT, "0" * 40, relative)
    with pytest.raises(subprocess.CalledProcessError):
        _git_blob(ROOT, RUN003_REVIEW_SHA, "missing/historical/path")


def test_run005_parent_pin_inventory_uses_immutable_git_blobs_after_guard_source_changes():
    commit = "53b7790c23c7d4969612259a8ee06be0353babd2"
    relative_guard = "artifacts/simulation/step07_nav2_baseline_campaign/approval_guards/STEP07_NAV2_BASELINE_RUN_005.json"
    historical = _strict_git_json(ROOT, commit, relative_guard)
    changed = "artifacts/simulation/step07_nav2_baseline_campaign/tools/step07_run005_runtime_guard.py"
    assert (ROOT / changed).read_bytes() != _git_blob(ROOT, commit, changed)
    _validate_historical_pins_at_commit(ROOT, historical, commit)
    invalid = json.loads(json.dumps(historical))
    invalid["source_pins"][changed]["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="HISTORICAL_SOURCE_PIN_MISMATCH"):
        _validate_historical_pins_at_commit(ROOT, invalid, commit)
