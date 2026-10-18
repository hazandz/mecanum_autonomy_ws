"""Fail-closed future runtime preflight and capacity-one guard acquisition."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path


RUN_ID = "WP06_6F_TF_EKF_RUNTIME_INGRESS_RUN_007"
PARTITION = "wp06_scan_probe_run_002"
PENDING = "PENDING_EXACT_INTEGRATION_AND_USER_AUTHORIZATION"
CONSUMED = "CONSUMED"
ARCHITECTURE_PATH = "docs/MECANUM_NAV_DRL_Architecture.docx"
ARCHITECTURE_SHA256 = "432eeac363a595cfcf7e81c4b66054fb674dba140a2ef3cffecd617ab8136204"
DECISION_PATH = "docs/governance/decisions/WP-06_SIM_EVAL_TF_EKF_RUNTIME_STATE_ESTIMATION_INGRESS_L2_DECISION.md"
MANIFEST_PATH = "docs/governance/evidence/WP-06_6F_TF_EKF_RUNTIME_INGRESS_RUN_007_GUARD_MANIFEST.json"
EVIDENCE_PATH = "docs/governance/evidence/WP-06_SIM_EVAL_TF_EKF_RUNTIME_STATE_ESTIMATION_INGRESS_L2_EVIDENCE.json"
GUARD_PATH = "artifacts/simulation/sim_eval_scan_endpoint_probe_evidence/approval_guards/WP06_6F_TF_EKF_RUNTIME_INGRESS_RUN_007.json"


class GuardError(RuntimeError):
    """A failed authority/precondition or consumed capacity-one guard."""


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _git(root, *args):
    completed = subprocess.run(
        ["git", "-C", str(root), *args],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if completed.returncode:
        raise GuardError(f"GIT_CHECK_FAILED:{args[0]}:{completed.stderr.strip()}")
    return completed.stdout.strip()


def _reject_duplicate_json_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise GuardError(f"DUPLICATE_JSON_KEY:{key}")
        result[key] = value
    return result


def _load_json(path):
    raw = Path(path).read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raise GuardError(f"JSON_BOM:{path}")
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_reject_duplicate_json_keys)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GuardError(f"JSON_INVALID:{path}:{exc}") from exc
    canonical = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    if raw != canonical:
        raise GuardError(f"JSON_NOT_CANONICAL:{path}")
    return value


def verify_runtime_preconditions(
    repository_root,
    guard_path,
    run_directory,
    expected_review_commit,
    expected_integration_base,
):
    """Check exact authority, clean review checkout, pins, and unused run path."""
    root = Path(repository_root).resolve()
    guard_file = Path(guard_path).resolve()
    run_dir = Path(run_directory).resolve()
    if root == run_dir or root in run_dir.parents:
        raise GuardError("RUN_DIRECTORY_MUST_BE_OUTSIDE_REPOSITORY")
    if _git(root, "remote", "get-url", "origin") != "https://github.com/hazandz/mecanum_autonomy_ws.git":
        raise GuardError("ORIGIN_MISMATCH")
    if _git(root, "rev-parse", "HEAD") != expected_review_commit:
        raise GuardError("REVIEW_HEAD_MISMATCH")
    if _git(root, "rev-parse", "origin/integration/implementation") != expected_integration_base:
        raise GuardError("INTEGRATION_BASE_MISMATCH")
    _git(root, "merge-base", "--is-ancestor", expected_integration_base, expected_review_commit)
    if _git(root, "status", "--porcelain"):
        raise GuardError("WORKTREE_DIRTY")
    guard = _load_json(guard_file)
    if guard_file != (root / GUARD_PATH).resolve() or guard.get("guard_path") != GUARD_PATH:
        raise GuardError("GUARD_PATH_MISMATCH")
    if guard.get("run_id") != RUN_ID or guard.get("gz_partition") != PARTITION:
        raise GuardError("GUARD_CONTEXT_MISMATCH")
    if guard.get("state") != PENDING or guard.get("capacity") != 1:
        raise GuardError("GUARD_NOT_PENDING_CAPACITY_ONE")
    if guard.get("acquisition_count") != 0 or guard.get("runtime_authorization") != "NOT_GRANTED":
        raise GuardError("GUARD_SEED_ALREADY_MUTATED")
    if guard.get("expected_integration_base") != expected_integration_base:
        raise GuardError("GUARD_BASE_MISMATCH")
    if guard.get("expected_review_commit") not in (None, expected_review_commit):
        raise GuardError("GUARD_REVIEW_MISMATCH")
    manifest_path = root / MANIFEST_PATH
    if _sha256(manifest_path) != guard.get("guard_manifest_sha256"):
        raise GuardError("GUARD_MANIFEST_SHA_MISMATCH")
    decision_path = root / DECISION_PATH
    if _sha256(decision_path) != guard.get("decision_sha256"):
        raise GuardError("DECISION_SHA_MISMATCH")
    architecture = root / ARCHITECTURE_PATH
    if _sha256(architecture) != ARCHITECTURE_SHA256:
        raise GuardError("ARCHITECTURE_SHA_MISMATCH")
    manifest = _load_json(manifest_path)
    if manifest.get("base_commit") != expected_integration_base:
        raise GuardError("MANIFEST_BASE_MISMATCH")
    if manifest.get("decision_sha256") != guard.get("decision_sha256"):
        raise GuardError("MANIFEST_DECISION_MISMATCH")
    if manifest.get("run_id") != RUN_ID or manifest.get("gz_partition") != PARTITION:
        raise GuardError("MANIFEST_CONTEXT_MISMATCH")
    if manifest.get("guard_path") != guard.get("guard_path"):
        raise GuardError("MANIFEST_GUARD_PATH_MISMATCH")
    guard_seed = manifest.get("guard_seed", {})
    if guard_seed != {"path": GUARD_PATH, "state": PENDING, "capacity": 1, "consumed": False}:
        raise GuardError("MANIFEST_GUARD_SEED_MISMATCH")
    expected_commands = {
        "bootstrap": ["ros2", "launch", "ROBOT_URDF_final_description", "sim_eval_scan_probe_bootstrap.launch.py"],
        "composite": ["ros2", "launch", "mecanum_nav_bringup", "sim_eval_tf_ekf_state_estimation.launch.py",
                      f"gz_partition:={PARTITION}", "use_sim_time:=true"],
        "observer": ["ros2", "run", "wp06_6f_tf_ekf_runtime_observer", "wp06_6f_tf_ekf_runtime_observer"],
        "set_pose_info": ["ros2", "topic", "info", "--verbose", "/set_pose"],
        "set_pose_echo": ["ros2", "topic", "echo", "/set_pose", "geometry_msgs/msg/PoseWithCovarianceStamped", "--once"],
    }
    if manifest.get("command_contract") != expected_commands:
        raise GuardError("MANIFEST_COMMAND_CONTRACT_MISMATCH")
    evidence_path = root / EVIDENCE_PATH
    if manifest.get("evidence_path") != EVIDENCE_PATH or _sha256(evidence_path) != manifest.get("evidence_sha256"):
        raise GuardError("EVIDENCE_SHA_MISMATCH")
    evidence = _load_json(evidence_path)
    if evidence.get("run_id") != RUN_ID or evidence.get("gz_partition") != PARTITION:
        raise GuardError("EVIDENCE_CONTEXT_MISMATCH")
    if evidence.get("runtime_eligible") is not False or evidence.get("runtime_evidence_status") != "NOT_CREATED":
        raise GuardError("EVIDENCE_CEILING_MISMATCH")
    if evidence.get("source_pins") != manifest.get("source_pins"):
        raise GuardError("EVIDENCE_SOURCE_PINS_MISMATCH")
    matrix = manifest.get("acceptance_to_collector_matrix")
    if not isinstance(matrix, list) or matrix != evidence.get("acceptance_to_collector_matrix"):
        raise GuardError("ACCEPTANCE_MATRIX_MISMATCH")
    required_acceptances = {
        "bootstrap_readiness", "bootstrap_stability_20_seconds", "composite_liveness", "composite_stability_5_seconds",
        "clock_five_monotonic_samples", "wheel_input", "imu_input", "ingress_use_sim_time",
        "filtered_odometry_five_monotonic_samples", "ekf_use_sim_time", "ekf_topology",
        "dynamic_tf_edge_gid", "dynamic_tf_subscription_qos", "static_tf_edge_qos",
        "static_tf_owner_gid_mappable", "static_tf_owner_gid_unique", "static_tf_owner_gid",
        "static_tf_subscription_qos", "map_to_odom_absent",
        "forbidden_bridge_and_process_boundary", "process_group_teardown", "process_group_teardown_order", "observer_error_absent",
        "ekf_set_pose_admin_endpoint", "ekf_set_pose_zero_publishers_no_payload",
        "runtime_session_completed_without_exception",
    }
    matrix_by_id = {row.get("acceptance_id"): row for row in matrix if isinstance(row, dict)}
    if set(matrix_by_id) != required_acceptances:
        raise GuardError("ACCEPTANCE_MATRIX_COVERAGE_MISMATCH")
    required_fields = ("collector", "raw_artifact_path", "parser_or_validator", "pass_condition", "failure_reason_literal", "offline_test_name")
    if any(not all(row.get(field) for field in required_fields) for row in matrix_by_id.values()):
        raise GuardError("ACCEPTANCE_MATRIX_ROW_INCOMPLETE")
    source_pins = manifest.get("source_pins")
    if not isinstance(source_pins, dict) or not source_pins:
        raise GuardError("MANIFEST_SOURCE_PINS_INVALID")
    for relative, expected in source_pins.items():
        if not isinstance(expected, str) or len(expected) != 64 or any(char not in "0123456789abcdef" for char in expected):
            raise GuardError(f"SOURCE_PIN_SHA_INVALID:{relative}")
        path = root / relative
        if not path.is_file() or _sha256(path) != expected:
            raise GuardError(f"SOURCE_PIN_MISMATCH:{relative}")
    if run_dir.exists():
        raise GuardError("RUN_DIRECTORY_ALREADY_EXISTS")
    return {"guard": guard, "manifest": manifest, "source_pins": source_pins}


def acquire_guard(guard_path, expected_review_commit, expected_integration_base):
    """Atomically consume a pending capacity-one guard once, after all preflight."""
    path = Path(guard_path).resolve()
    lock_path = path.with_suffix(path.suffix + ".lock")
    lock_fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        guard = _load_json(path)
        if guard.get("state") != PENDING or guard.get("capacity") != 1:
            raise GuardError("GUARD_CAPACITY_CONSUMED")
        if guard.get("run_id") != RUN_ID or guard.get("gz_partition") != PARTITION:
            raise GuardError("GUARD_CONTEXT_MISMATCH")
        updated = dict(guard)
        updated["state"] = CONSUMED
        updated["acquired_review_commit"] = expected_review_commit
        updated["acquired_integration_base"] = expected_integration_base
        updated["acquisition_count"] = 1
        canonical = json.dumps(updated, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(canonical)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp_name, path)
            directory_fd = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)
        return updated
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        os.close(lock_fd)
