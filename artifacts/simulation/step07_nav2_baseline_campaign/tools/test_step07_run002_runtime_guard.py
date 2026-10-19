import json
import hashlib
from pathlib import Path
import subprocess

import pytest

from step07_run002_runtime_guard import (
    ARCHITECTURE_SHA256, AUTH_SCOPE, INTEGRATION_BASE, PARTITION, PENDING, RUN_ID,
    acquire_guard, load_guard, validate_seed, validate_source_pins,
)

ROOT = Path(__file__).resolve().parents[4]
GUARD = ROOT / "artifacts/simulation/step07_nav2_baseline_campaign/approval_guards/STEP07_NAV2_BASELINE_RUN_002.json"
RUN002_REVIEW_SHA = "6d730bd54d7f99429ee4832a3f6f96beffae020f"
REVIEW = "a" * 40


def _git_blob(root: Path, commit: str, relative: str) -> bytes:
    """Return exact historical Git bytes; failures never fall back to checkout."""
    return subprocess.run(
        ["git", "show", f"{commit}:{relative}"],
        cwd=root,
        check=True,
        capture_output=True,
    ).stdout


def _validate_run002_historical_source_pins(root: Path, guard: dict) -> None:
    pins = guard.get("source_pins")
    if type(pins) is not dict or not pins:
        raise ValueError("HISTORICAL_RUN002_SOURCE_PINS_MISSING")
    for relative, expected in pins.items():
        if (type(relative) is not str or type(expected) is not dict
                or set(expected) != {"sha256", "size_bytes"}
                or type(expected.get("sha256")) is not str
                or type(expected.get("size_bytes")) is not int):
            raise ValueError("HISTORICAL_RUN002_SOURCE_PIN_ROW_INVALID")
        path = Path(relative)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("HISTORICAL_RUN002_SOURCE_PIN_PATH_INVALID")
        raw = _git_blob(root, RUN002_REVIEW_SHA, relative)
        if (hashlib.sha256(raw).hexdigest() != expected["sha256"]
                or len(raw) != expected["size_bytes"]):
            raise ValueError(f"HISTORICAL_RUN002_SOURCE_PIN_MISMATCH:{relative}")


def test_committed_run002_guard_is_exact_pending_seed_and_its_historical_source_closes():
    document = load_guard(GUARD)
    validate_seed(document, run_id=RUN_ID, review_commit=REVIEW,
                  integration_base=INTEGRATION_BASE,
                  architecture_sha256=ARCHITECTURE_SHA256, partition=PARTITION)
    assert document["state"] == PENDING
    assert document["capacity"] == 1 and document["acquisition_count"] == 0
    assert document["runtime_authorization"] == "NOT_GRANTED"
    assert document["retry_permitted"] is False
    assert not GUARD.with_suffix(GUARD.suffix + ".lock").exists()
    pins = document["source_pins"]
    assert len(pins) == len(set(pins))
    assert "artifacts/simulation/step07_nav2_baseline_campaign/tools/run_step07_nav2_baseline_run002.py" in pins
    assert not any("run001" in path.lower() for path in pins)
    _validate_run002_historical_source_pins(ROOT, document)
    guard_relative = "artifacts/simulation/step07_nav2_baseline_campaign/approval_guards/STEP07_NAV2_BASELINE_RUN_002.json"
    assert GUARD.read_bytes() == _git_blob(ROOT, RUN002_REVIEW_SHA, guard_relative)


def test_run002_historical_pins_ignore_the_run003_contract_test_worktree_change():
    document = load_guard(GUARD)
    relative = "ros2_ws/src/mecanum_nav_bringup/test/test_sim_eval_tf_ekf_runtime_contract.py"
    assert relative in document["source_pins"]
    current = (ROOT / relative).read_bytes()
    historical = _git_blob(ROOT, RUN002_REVIEW_SHA, relative)
    assert current != historical
    _validate_run002_historical_source_pins(ROOT, document)


def test_run002_historical_source_pin_hash_mismatch_fails_closed():
    document = load_guard(GUARD)
    relative = next(iter(document["source_pins"]))
    altered = json.loads(json.dumps(document))
    altered["source_pins"][relative]["sha256"] = "0" * 64
    with pytest.raises(ValueError, match=f"HISTORICAL_RUN002_SOURCE_PIN_MISMATCH:{relative}"):
        _validate_run002_historical_source_pins(ROOT, altered)


@pytest.mark.parametrize("commit,relative", [
    ("0" * 40, "artifacts/maps/warehouse_map2/map.yaml"),
    (RUN002_REVIEW_SHA, "missing/historical/path"),
])
def test_run002_historical_missing_commit_or_blob_fails_closed(commit, relative, monkeypatch):
    document = load_guard(GUARD)
    document["source_pins"] = {relative: {"sha256": "0" * 64, "size_bytes": 0}}
    monkeypatch.setattr("test_step07_run002_runtime_guard.RUN002_REVIEW_SHA", commit)
    with pytest.raises(subprocess.CalledProcessError):
        _validate_run002_historical_source_pins(ROOT, document)


@pytest.mark.parametrize("relative", ["/absolute/path", "../escape", "nested/../../escape"])
def test_run002_historical_source_pin_path_is_rejected(relative):
    document = {"source_pins": {relative: {"sha256": "0" * 64, "size_bytes": 0}}}
    with pytest.raises(ValueError, match="HISTORICAL_RUN002_SOURCE_PIN_PATH_INVALID"):
        _validate_run002_historical_source_pins(ROOT, document)


def test_run002_current_candidate_pin_validation_still_reads_worktree_bytes(tmp_path):
    source = tmp_path / "current.txt"
    source.write_bytes(b"run003-current")
    pin = {"current.txt": {"sha256": hashlib.sha256(b"run003-current").hexdigest(),
                            "size_bytes": len(b"run003-current")}}
    validate_source_pins(tmp_path, pin)
    source.write_bytes(b"changed")
    with pytest.raises(ValueError, match="SOURCE_PIN_MISMATCH"):
        validate_source_pins(tmp_path, pin)


@pytest.mark.parametrize("raw", [
    b'{"a":1,"a":2}', b'{"a":NaN}', b'\xef\xbb\xbf{}', b'{}\n', b'{ "a":1}', b'\xff',
])
def test_guard_json_rejects_duplicate_nonfinite_bom_newline_noncanonical_and_invalid_utf8(tmp_path, raw):
    path = tmp_path / "guard.json"
    path.write_bytes(raw)
    with pytest.raises((ValueError, UnicodeDecodeError, json.JSONDecodeError)):
        load_guard(path)


def test_acquisition_is_explicit_and_capacity_one(tmp_path):
    path = tmp_path / "run002.json"
    document = {"run_id": RUN_ID, "state": PENDING, "capacity": 1,
                "acquisition_count": 0, "runtime_authorization": "NOT_GRANTED",
                "integration_base": INTEGRATION_BASE,
                "architecture_sha256": ARCHITECTURE_SHA256, "partition": PARTITION,
                "source_pins": {"placeholder": {"sha256": "0" * 64, "size_bytes": 0}}}
    path.write_bytes(json.dumps(document, sort_keys=True, separators=(",", ":")).encode())
    consumed = acquire_guard(path, document, {"owner_authorization": "exact"},
                             review_commit=REVIEW, integration_base=INTEGRATION_BASE)
    assert consumed["state"] == "CONSUMED"
    assert consumed["acquisition_count"] == 1
    assert consumed["runtime_authorization"] == "GRANTED_FOR_THIS_EXACT_RUN_ONLY"
    assert path.with_suffix(".json.lock").exists()
