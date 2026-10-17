"""Atomic capacity-one guard for the separately authorized Run 005 session."""

from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import tempfile

SCHEMA = "mecanum_scan_endpoint_probe_run005_guard/v1"
PENDING = "PENDING_EXACT_INTEGRATION_AND_USER_AUTHORIZATION"
CONSUMED = "CONSUMED"
RUN_ID = "WP06_6D_SIM_EVAL_SCAN_ENDPOINT_PROBE_RUN_005"
PARTITION = "wp06_scan_probe_run_005"
GUARD_PATH = "artifacts/simulation/sim_eval_scan_endpoint_probe_evidence/approval_guards/WP06_6D_SIM_EVAL_SCAN_ENDPOINT_PROBE_RUN_005.json"
MANIFEST_PATH = "docs/governance/evidence/WP-06_SCAN_PROBE_RUN_005_RUNTIME_GUARD_MANIFEST.json"
DECISION_PATH = "docs/governance/decisions/WP-06_SCAN_PROBE_PERSISTENT_TRANSPORT_DISCOVERY_FIX_L2_DECISION.md"

class GuardError(ValueError):
    """Invalid, mismatched, or already consumed capacity-one guard."""

def canonical_json_bytes(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")

def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise GuardError(f"duplicate JSON key: {key}")
        result[key] = value
    return result

def load_guard_bytes(raw):
    if raw.startswith(b"\xef\xbb\xbf") or raw.endswith(b"\n"):
        raise GuardError("guard BOM/final newline forbidden")
    try:
        value = json.loads(raw.decode("utf-8", "strict"), object_pairs_hook=_unique)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GuardError("invalid guard JSON") from exc
    if canonical_json_bytes(value) != raw:
        raise GuardError("guard is not canonical compact JSON")
    return value

def validate_guard(record, expected_context):
    if type(record) is not dict or set(record) != {"schema", "capacity", "state", "context"}:
        raise GuardError("guard key set mismatch")
    if record["schema"] != SCHEMA or type(record["capacity"]) is not int or record["capacity"] != 1:
        raise GuardError("guard schema/capacity mismatch")
    if record["state"] != PENDING:
        raise GuardError("guard already consumed; retries prohibited")
    if record["context"] != expected_context:
        raise GuardError("guard context mismatch")
    return record

@contextmanager
def _lock(path):
    fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)

def _atomic_write(path, data):
    fd, temp = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
        dfd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(dfd)
        finally:
            os.close(dfd)
    finally:
        try:
            os.unlink(temp)
        except FileNotFoundError:
            pass

def consume_guard(path, expected_context):
    path = Path(path)
    with _lock(path.with_suffix(path.suffix + ".lock")):
        record = load_guard_bytes(path.read_bytes())
        validate_guard(record, expected_context)
        record["state"] = CONSUMED
        raw = canonical_json_bytes(record)
        _atomic_write(path, raw)
        return hashlib.sha256(raw).hexdigest()
