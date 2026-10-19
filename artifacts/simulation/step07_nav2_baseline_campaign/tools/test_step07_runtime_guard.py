import json
from pathlib import Path

import pytest

from step07_runtime_guard import (
    AUTH_SCOPE, INTEGRATION_BASE, PARTITION, RUN_ID, acquire_guard,
    load_guard, validate_owner_authorization, validate_seed, validate_source_pins,
)

ROOT = Path(__file__).resolve().parents[4]
GUARD = ROOT / "artifacts/simulation/step07_nav2_baseline_campaign/approval_guards/STEP07_NAV2_BASELINE_RUN_001.json"
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


def test_committed_guard_is_capacity_one_pending_seed():
    document = load_guard(GUARD)
    validate_seed(document, run_id=RUN_ID, review_commit=REVIEW, integration_base=INTEGRATION_BASE,
                  architecture_sha256=document["architecture_sha256"], partition=PARTITION)
    assert document["state"] == "PENDING_EXACT_INTEGRATION_AND_USER_AUTHORIZATION"
    assert document["capacity"] == 1 and document["acquisition_count"] == 0
    assert document["runtime_authorization"] == "NOT_GRANTED"
    validate_source_pins(ROOT, document["source_pins"])


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
