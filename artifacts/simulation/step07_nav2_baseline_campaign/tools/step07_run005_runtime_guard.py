"""Capacity-one guard primitives for Step-7 NAV2_BASELINE Run005."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import tempfile

RUN_ID = "STEP07_NAV2_BASELINE_RUN_005"
PENDING = "PENDING_EXACT_INTEGRATION_AND_USER_AUTHORIZATION"
AUTH_SCOPE = "STEP07_NAV2_BASELINE_RUN005_ONE_OFFICIAL_CAMPAIGN_INVOCATION_CAPACITY_ONE_NO_RETRY"
ARCHITECTURE_SHA256 = "432eeac363a595cfcf7e81c4b66054fb674dba140a2ef3cffecd617ab8136204"
INTEGRATION_BASE = "f7f98c683d59cf4c62e462da9f37d4ffb2455c80"
PARTITION = "mecanum_step7_nav2_run005_f7f98c6"
RUNTIME_PYTHON_PATH = "/home/hazan/step07_runtime_python312_pydantic_2_10_6/bin/python"
PYDANTIC_REQUIREMENT = "pydantic==2.10.6"
RUN005_CONFIG_HASH = "4fac960ff2298cefd1b261db314bfa8e802855f8cb6290b762594658982b7925"
TEMPORAL_CONTRACT_ID = "mecanum.step07-run005-temporal-coherence/v1"
TEMPORAL_CONTRACT_SHA256 = "57aa6b871fd3bcdc4ae6eb2b6f7a0dcb66b07b927516b7b0969d5e47e5c36e59"
FUEL_URI_PATH_BINDINGS = {
    "https://fuel.gazebosim.org/1.0/OpenRobotics/models/Depot":
        "fuel.gazebosim.org/openrobotics/models/depot/<positive-integer-version>",
    "https://fuel.gazebosim.org/1.0/MovAi/models/Tugbot":
        "fuel.gazebosim.org/movai/models/tugbot/<positive-integer-version>",
}


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"DUPLICATE_JSON_KEY:{key}")
        result[key] = value
    return result


def load_guard(path: str | Path) -> dict:
    raw = Path(path).read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raise ValueError("GUARD_JSON_BOM")
    if raw.endswith(b"\n"):
        raise ValueError("GUARD_JSON_FINAL_NEWLINE")
    value = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique,
                       parse_constant=lambda value: (_ for _ in ()).throw(ValueError(f"INVALID_JSON_CONSTANT:{value}")))
    if type(value) is not dict:
        raise ValueError("GUARD_ROOT_NOT_OBJECT")
    canonical = json.dumps(value, ensure_ascii=False, sort_keys=True,
                           separators=(",", ":"), allow_nan=False).encode("utf-8")
    if raw != canonical:
        raise ValueError("GUARD_JSON_NOT_CANONICAL")
    return value


def validate_seed(guard: dict, *, run_id: str, review_commit: str,
                  integration_base: str, architecture_sha256: str,
                  partition: str) -> None:
    expected = {
        "run_id": RUN_ID, "state": PENDING, "capacity": 1,
        "acquisition_count": 0, "runtime_authorization": "NOT_GRANTED",
        "integration_base": INTEGRATION_BASE,
        "architecture_sha256": ARCHITECTURE_SHA256, "partition": PARTITION,
    }
    if (run_id != RUN_ID or integration_base != INTEGRATION_BASE
            or architecture_sha256 != ARCHITECTURE_SHA256 or partition != PARTITION):
        raise ValueError("GUARD_AUTHORITY_ARGUMENT_MISMATCH")
    for key, value in expected.items():
        if guard.get(key) != value:
            raise ValueError(f"GUARD_SEED_MISMATCH:{key}")
    bindings = {
        "expected_review_commit": None,
        "runtime_profile": "sim_eval", "navigation_mode": "NAV2_BASELINE",
        "use_sim_time": True, "runtime_eligible": False,
        "runtime_evidence_status": "NOT_CREATED", "GATE_B": "NOT_STARTED",
        "RUNTIME_APPROVED": "NOT_APPROVED", "retry_permitted": False,
        "config_hash": RUN005_CONFIG_HASH,
        "temporal_coherence_contract": {
            "contract_id": TEMPORAL_CONTRACT_ID,
            "contract_sha256": TEMPORAL_CONTRACT_SHA256,
        },
        "map_root": "artifacts/maps/warehouse_map2", "map_id": "warehouse_map2",
        "map_artifact_identity": "4a8a23d0-7e27-4a50-8201-dd1abf1a3db4",
        "map_content_hash": "2bd9ff0a40eaeb61c2359aab4bb213da623ab56746debe591edd4a54c2229f90",
        "map_sha256": {"map.yaml": "5073762401784f67e856b5018656ad869ecc26e723f85e5979054eadc7876a68",
                       "map.pgm": "32f8a3eb626ebddecc15843748de0db8c6f7adc1b45a5edc1b1b1886407aef55",
                       "metadata.yaml": "45450a2d62b38560200d11fef6ece8505eef5a3e3d73e27f7b091de022e793c1",
                       "map_manifest.json": "7e0a380b0d8df32f9a4fc30dd0dbbe9ed08aafdcd5efb3764bccd844b98c1cb1"},
        "world_path": "ros2_ws/src/ROBOT_URDF_final_description/launch/tugbot_depot.sdf",
        "world_sha256": "a4b6253340baa866d89640d62a94d04fbea51425e9af1deca591422a0a36d91d",
        "world_name": "world_demo", "initial_pose_map": {"x": 0.0, "y": 0.0, "yaw": 0.0},
        "goal_pose_map": {"x": -4.0, "y": 0.0, "yaw": 0.0},
        "world_map_numeric_equality": "PROHIBITED", "world_to_map_transform": "PROHIBITED",
        "tf_owners": {"map_to_odom": "amcl", "odom_to_base_link": "ekf_filter_node",
                      "base_link_to_lidar_frame": "robot_state_publisher"},
        "owner_authorization_scope": AUTH_SCOPE,
        "runtime_python": RUNTIME_PYTHON_PATH,
        "runtime_python_dependency": PYDANTIC_REQUIREMENT,
        "fuel_cache_path_case_policy": "LOWERCASE_OWNER_AND_MODEL_EXACT_PATH_NO_RGLOB_NO_DOWNLOAD",
        "fuel_uri_path_bindings": FUEL_URI_PATH_BINDINGS,
        "run002_historical_disposition": {
            "terminal_outcome": "STEP07_NAV2_BASELINE_RUN002_PREACQUIRE_PREFLIGHT_FAILED_NO_GUARD_CONSUMED",
            "root_cause": "FUEL_CACHE_PATH_CASE_NORMALIZATION_MISMATCH",
            "retry_permitted": False,
        },
        "run004_historical_disposition": {
            "terminal_outcome": "STEP07_NAV2_BASELINE_RUN004_PREACQUIRE_PREFLIGHT_FAILED_NO_GUARD_CONSUMED",
            "root_cause": "PACKAGE_PREFIX_CLOSURE_MISSING_ROBOT_URDF_FINAL_DESCRIPTION",
            "retry_permitted": False,
        },
    }
    for key, value in bindings.items():
        if guard.get(key) != value:
            raise ValueError(f"GUARD_BINDING_MISMATCH:{key}")
    if not isinstance(guard.get("source_pins"), dict) or not guard["source_pins"]:
        raise ValueError("GUARD_SOURCE_PINS_MISSING")
    if (not isinstance(review_commit, str) or len(review_commit) != 40
            or any(char not in "0123456789abcdef" for char in review_commit)):
        raise ValueError("REVIEW_COMMIT_INVALID")


def validate_owner_authorization(*, authorization: str, scope: str,
                                 run_id: str, review_commit: str,
                                 integration_base: str, expected_run_id: str,
                                 expected_review_commit: str,
                                 expected_integration_base: str) -> dict:
    fields = (authorization, scope, run_id, review_commit, integration_base)
    if any(type(value) is not str or not value.strip() for value in fields):
        raise ValueError("OWNER_AUTHORIZATION_FIELD_MISSING")
    if scope != AUTH_SCOPE:
        raise ValueError("OWNER_AUTHORIZATION_SCOPE_MISMATCH")
    if run_id != expected_run_id or run_id != RUN_ID:
        raise ValueError("OWNER_AUTHORIZATION_RUN_ID_MISMATCH")
    if review_commit != expected_review_commit:
        raise ValueError("OWNER_AUTHORIZATION_REVIEW_COMMIT_MISMATCH")
    if integration_base != expected_integration_base or integration_base != INTEGRATION_BASE:
        raise ValueError("OWNER_AUTHORIZATION_INTEGRATION_BASE_MISMATCH")
    return {
        "owner_authorization": authorization,
        "owner_authorization_scope": scope,
        "owner_authorization_run_id": run_id,
        "owner_authorization_review_commit": review_commit,
        "owner_authorization_integration_base": integration_base,
    }


def acquire_guard(path: str | Path, guard: dict, authorization: dict,
                  *, review_commit: str, integration_base: str) -> dict:
    """Atomically consume only after every preflight and exact authorization."""
    path = Path(path)
    lock = path.with_suffix(path.suffix + ".lock")
    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(fd)
    try:
        current = load_guard(path)
        if current != guard or current.get("state") != PENDING or current.get("acquisition_count") != 0:
            raise ValueError("GUARD_CHANGED_OR_ALREADY_CONSUMED")
        consumed = dict(current)
        consumed.update({
            "state": "CONSUMED", "acquisition_count": 1,
            "runtime_authorization": "GRANTED_FOR_THIS_EXACT_RUN_ONLY",
            "acquired_review_commit": review_commit,
            "acquired_integration_base": integration_base,
            **authorization,
        })
        payload = json.dumps(consumed, ensure_ascii=False, sort_keys=True,
                             separators=(",", ":"), allow_nan=False).encode("utf-8")
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.", delete=False) as tmp:
            tmp.write(payload)
            tmp.flush()
            os.fsync(tmp.fileno())
            temp_path = Path(tmp.name)
        os.replace(temp_path, path)
        return consumed
    except BaseException:
        # Chỉ trả lại capacity khi strict readback chứng minh chưa consume.
        try:
            readback = load_guard(path)
            pending = (readback == guard and readback.get("state") == PENDING
                       and readback.get("acquisition_count") == 0)
        except (OSError, ValueError):
            pending = False
        if pending:
            try:
                lock.unlink()
            except OSError:
                pass
        raise


def sha256(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate_source_pins(root: str | Path, pins: dict) -> None:
    root = Path(root).resolve(strict=True)
    for relative, expected in pins.items():
        if type(relative) is not str or type(expected) is not dict or set(expected) != {"sha256", "size_bytes"}:
            raise ValueError("SOURCE_PIN_ROW_INVALID")
        path = Path(relative)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("SOURCE_PIN_PATH_INVALID")
        raw = (root / path).read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected["sha256"] or len(raw) != expected["size_bytes"]:
            raise ValueError(f"SOURCE_PIN_MISMATCH:{relative}")
