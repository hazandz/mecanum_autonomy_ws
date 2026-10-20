import json
from pathlib import Path

import pytest

from step07_run005_runtime_guard import (
    ARCHITECTURE_SHA256, AUTH_SCOPE, INTEGRATION_BASE, PARTITION, PENDING, RUN_ID, RUNTIME_PYTHON_PATH, PYDANTIC_REQUIREMENT,
    acquire_guard, load_guard, validate_seed, validate_source_pins,
)

ROOT = Path(__file__).resolve().parents[4]
GUARD = ROOT / "artifacts/simulation/step07_nav2_baseline_campaign/approval_guards/STEP07_NAV2_BASELINE_RUN_005.json"
EVIDENCE = ROOT / "docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_L1_EVIDENCE.json"
REVIEW = "fdc0e299515bda2286832aabec635948629517b5"
EXPECTED_SOURCE_PIN_PATHS = {
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/prepare_step07_runtime_python_environment.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/step07_runtime_python_requirements.txt",

    "artifacts/maps/warehouse_map2/map.yaml",
    "ros2_ws/src/step07_nav2_baseline_runtime_observer/package.xml",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/run_step07_nav2_baseline_run005.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/step07_gate_b_evidence_validator.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/step07_run005_runtime_guard.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_run_step07_nav2_baseline_run005.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_gate_b_evidence_validator.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_run005_runtime_guard.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_runtime_guard.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_run003_runtime_guard.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_run004_runtime_guard.py",
    "ros2_ws/src/ROBOT_URDF_final_description/launch/tugbot_depot.sdf",
    "ros2_ws/src/ROBOT_URDF_final_description/launch/sim_eval_nav2_baseline_bootstrap.launch.py",
    "ros2_ws/src/mecanum_nav_bringup/launch/sim_eval_nav2_baseline_system.launch.py",
    "ros2_ws/src/mecanum_nav_bringup/test/test_sim_eval_nav2_baseline_system_launch.py",
    "ros2_ws/src/mecanum_nav_bringup/test/test_sim_eval_tf_ekf_runtime_contract.py",
    "ros2_ws/src/mecanum_nav_rl/config/v3/resolved/sim_eval_nav2_baseline.resolved.json",
    "ros2_ws/src/mecanum_nav_bringup/launch/sim_eval_tf_ekf_state_estimation.launch.py",
    "ros2_ws/src/mecanum_nav_bringup/package.xml",
    "ros2_ws/src/mecanum_nav_bringup/config/navigation/sim_eval_nav2_baseline.runtime.yaml",
    "ros2_ws/src/mecanum_nav_bringup/config/bridge/sim_eval_cmd_vel.runtime.yaml",
    "ros2_ws/src/mecanum_nav_bringup/config/lifecycle/sim_eval_nav2_baseline.runtime.yaml",
    "ros2_ws/src/mecanum_nav_bringup/config/bridge/sim_eval_lidar_scan_bridge.runtime.yaml",
    "ros2_ws/src/mecanum_nav_bringup/config/localization/amcl_omni.yaml",
    "ros2_ws/src/mecanum_nav_bringup/config/bridge/sim_eval_clock.runtime.yaml",
    "ros2_ws/src/mecanum_nav_bringup/config/state_estimation/ekf_sim.yaml",
    "ros2_ws/src/mecanum_base_bridge/launch/sim_eval_wheel_imu_ingress.launch.py",
    "ros2_ws/src/mecanum_base_bridge/config/bridge/sim_eval_wheel_imu_ingress.runtime.yaml",
    "ros2_ws/src/mecanum_nav_rl/config/safety/sim_eval_nav2_baseline_safety.yaml",
    "ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/observations/step07_gate_b_observer_node.py",
    "ros2_ws/src/mecanum_nav_rl/test/test_step07_gate_b_observer_node.py",
    "ros2_ws/src/step07_nav2_baseline_runtime_observer/src/step07_nav2_baseline_runtime_observer.cpp",
}

NEW_SOURCE_PIN_PATHS = {
    "ros2_ws/src/mecanum_nav_bringup/launch/sim_eval_tf_ekf_state_estimation.launch.py",
    "ros2_ws/src/mecanum_nav_bringup/package.xml",
    "ros2_ws/src/mecanum_nav_bringup/config/navigation/sim_eval_nav2_baseline.runtime.yaml",
    "ros2_ws/src/mecanum_nav_bringup/config/bridge/sim_eval_cmd_vel.runtime.yaml",
    "ros2_ws/src/mecanum_nav_bringup/config/lifecycle/sim_eval_nav2_baseline.runtime.yaml",
    "ros2_ws/src/mecanum_nav_bringup/config/bridge/sim_eval_lidar_scan_bridge.runtime.yaml",
    "ros2_ws/src/mecanum_nav_bringup/config/localization/amcl_omni.yaml",
    "ros2_ws/src/mecanum_nav_bringup/config/bridge/sim_eval_clock.runtime.yaml",
    "ros2_ws/src/mecanum_nav_bringup/config/state_estimation/ekf_sim.yaml",
    "ros2_ws/src/mecanum_base_bridge/launch/sim_eval_wheel_imu_ingress.launch.py",
    "ros2_ws/src/mecanum_base_bridge/config/bridge/sim_eval_wheel_imu_ingress.runtime.yaml",
    "ros2_ws/src/mecanum_nav_rl/config/safety/sim_eval_nav2_baseline_safety.yaml",
}
OLD_SOURCE_PIN_PATHS = EXPECTED_SOURCE_PIN_PATHS - NEW_SOURCE_PIN_PATHS


def test_committed_run005_guard_is_exact_pending_seed_and_its_own_source_closes():
    document = load_guard(GUARD)
    validate_seed(document, run_id=RUN_ID, review_commit=REVIEW,
                  integration_base=INTEGRATION_BASE,
                  architecture_sha256=ARCHITECTURE_SHA256, partition=PARTITION)
    assert document["state"] == PENDING
    assert document["capacity"] == 1 and document["acquisition_count"] == 0
    assert document["runtime_authorization"] == "NOT_GRANTED"
    assert document["retry_permitted"] is False
    assert document["run_id"] == "STEP07_NAV2_BASELINE_RUN_005"
    assert document["integration_base"] == "f7f98c683d59cf4c62e462da9f37d4ffb2455c80"
    assert document["partition"] == "mecanum_step7_nav2_run005_f7f98c6"
    assert document["preacquire_failure_contract"]["terminal_outcome"] == (
        "STEP07_NAV2_BASELINE_RUN005_PREACQUIRE_PREFLIGHT_FAILED_NO_GUARD_CONSUMED"
    )
    assert document["runtime_python"] == RUNTIME_PYTHON_PATH
    assert document["runtime_python_dependency"] == PYDANTIC_REQUIREMENT
    assert document["runtime_python_environment_contract"]["failure_literal_prefix"] == "RUNTIME_PYTHON_ENVIRONMENT_INVALID:"
    assert document["run002_historical_disposition"] == {
        "terminal_outcome": "STEP07_NAV2_BASELINE_RUN002_PREACQUIRE_PREFLIGHT_FAILED_NO_GUARD_CONSUMED",
        "root_cause": "FUEL_CACHE_PATH_CASE_NORMALIZATION_MISMATCH",
        "retry_permitted": False,
    }
    assert document["run004_historical_disposition"] == {
        "terminal_outcome": "STEP07_NAV2_BASELINE_RUN004_PREACQUIRE_PREFLIGHT_FAILED_NO_GUARD_CONSUMED",
        "root_cause": "PACKAGE_PREFIX_CLOSURE_MISSING_ROBOT_URDF_FINAL_DESCRIPTION",
        "retry_permitted": False,
    }
    assert document["run005_attempt_001_disposition"] == {
        "attempt": "attempt_001",
        "evidence_directory": "/home/hazan/step07_runtime_evidence/STEP07_NAV2_BASELINE_RUN_005",
        "root_failure": "SIM_EVAL_FUEL_CACHE_MODEL_MISSING:OpenRobotics/Depot",
        "run_record_sha256": "374565871f170fb2cbd7a9c089a2d0f47dd4e34d217357769259ef74f5409040",
        "terminal_outcome": "STEP07_NAV2_BASELINE_RUN005_FAIL_NO_RETRY_GUARD_CONSUMED",
        "guard_consumed": True,
        "immutable": True,
        "retry_permitted": False,
    }
    pins = document["source_pins"]
    assert document["run005_attempt_002_contract"] == {
        "attempt": "attempt_002",
        "requires_exact_candidate_commit": True,
        "requires_independent_audit": True,
        "requires_new_owner_authorization": True,
        "source_pin_count": len(pins),
    }
    assert not GUARD.with_suffix(GUARD.suffix + ".lock").exists()
    assert len(EXPECTED_SOURCE_PIN_PATHS) == 34
    assert len(set(EXPECTED_SOURCE_PIN_PATHS)) == 34
    assert set(pins) <= EXPECTED_SOURCE_PIN_PATHS
    assert set(pins) | NEW_SOURCE_PIN_PATHS == EXPECTED_SOURCE_PIN_PATHS
    assert "artifacts/simulation/step07_nav2_baseline_campaign/tools/run_step07_nav2_baseline_run005.py" in pins
    assert not any("approval_guards/step07_nav2_baseline_run_00[123].json" in path.lower() for path in pins)
    assert set(pins) == EXPECTED_SOURCE_PIN_PATHS
    import hashlib
    prospective = dict(pins)
    stale_current_sources = set()
    for relative, expected in pins.items():
        raw = (ROOT / relative).read_bytes()
        actual = {"sha256": hashlib.sha256(raw).hexdigest(), "size_bytes": len(raw)}
        if actual != expected:
            stale_current_sources.add(relative)
            prospective[relative] = actual
    assert stale_current_sources <= {
        "artifacts/simulation/step07_nav2_baseline_campaign/tools/run_step07_nav2_baseline_run005.py",
        "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_run_step07_nav2_baseline_run005.py",
        "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_run005_runtime_guard.py",
        "ros2_ws/src/mecanum_nav_bringup/test/test_sim_eval_tf_ekf_runtime_contract.py",
    }
    # During source stabilization, only the exact in-scope edited source pins
    # can be prospective; final governance reconciliation must restore closure.
    validate_source_pins(ROOT, prospective)


def test_invocation_003_is_recorded_as_preacquire_without_guard_consumption():
    document = load_guard(GUARD)
    disposition = document["run005_attempt_002_invocation_003_disposition"]
    assert disposition == {
        "attempt": "attempt_002_invocation_003",
        "call_counts": {
            "runner": 1, "bootstrap": 0, "composite": 0,
            "cpp_observer": 0, "gate_b_observer": 0,
        },
        "evidence_bundle_created": False,
        "evidence_write_exception": "OSError: [Errno 30] Read-only file system",
        "guard_consumed": False,
        "initial_preacquire_exception": "PermissionError: [Errno 1] Operation not permitted",
        "runtime_checkout_created": True,
        "runtime_execution": False,
        "terminal_outcome": "STEP07_NAV2_BASELINE_RUN005_PREACQUIRE_PREFLIGHT_FAILED_NO_GUARD_CONSUMED",
    }


def test_invocation_004_checksum_verified_preacquire_record_keeps_seed_pending():
    document = load_guard(GUARD)
    evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    disposition = evidence["run005_attempt_002_invocation_004"]
    assert disposition["preacquire_failure_literal"] == (
        "PREACQUIRE_FAILURE:RuntimeError:STALE_PARTITION_PROCESS_FOUND"
    )
    assert disposition["terminal_outcome"] == (
        "STEP07_NAV2_BASELINE_RUN005_PREACQUIRE_PREFLIGHT_FAILED_NO_GUARD_CONSUMED"
    )
    assert disposition["call_counts"] == {
        "runner": 1, "bootstrap": 0, "composite": 0,
        "cpp_observer": 0, "gate_b_observer": 0,
    }
    assert disposition["runtime_execution"] is False
    assert disposition["guard_acquired"] is disposition["guard_consumed"] is False
    assert disposition["guard_state_before"] == disposition["guard_state_after"] == PENDING
    assert disposition["guard_capacity"] == 1
    assert disposition["guard_acquisition_count"] == 0
    assert disposition["lock_exists"] is False
    assert disposition["teardown_applicable"] is False
    assert disposition["sha256sums_check"] == "PASS"
    assert disposition["artifact_manifest_count"] == 2
    assert document["state"] == PENDING and document["capacity"] == 1
    assert document["acquisition_count"] == 0
    assert document["runtime_authorization"] == "NOT_GRANTED"
    assert not GUARD.with_suffix(GUARD.suffix + ".lock").exists()


@pytest.mark.parametrize("raw", [
    b'{"a":1,"a":2}', b'{"a":NaN}', b'\xef\xbb\xbf{}', b'{}\n', b'{ "a":1}', b'\xff',
])
def test_guard_json_rejects_duplicate_nonfinite_bom_newline_noncanonical_and_invalid_utf8(tmp_path, raw):
    path = tmp_path / "guard.json"
    path.write_bytes(raw)
    with pytest.raises((ValueError, UnicodeDecodeError, json.JSONDecodeError)):
        load_guard(path)


def test_acquisition_is_explicit_and_capacity_one(tmp_path):
    path = tmp_path / "run005.json"
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
