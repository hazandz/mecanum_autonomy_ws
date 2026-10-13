from dataclasses import replace
from pathlib import Path
import sys
from types import ModuleType

import pytest

# Load only the new pure-core namespace. The existing observations package
# initializer imports unrelated configuration dependencies.
_PACKAGE_DIR = Path(__file__).parents[1] / "mecanum_nav_rl"
for _name, _path in (("mecanum_nav_rl", _PACKAGE_DIR),
                     ("mecanum_nav_rl.observations", _PACKAGE_DIR / "observations")):
    if _name not in sys.modules:
        _module = ModuleType(_name)
        _module.__path__ = [str(_path)]
        sys.modules[_name] = _module

from mecanum_nav_rl.observations.v3_snapshot_types import (
    LIDAR_CONTRACT_ID,
    FRAME_TF_CONTRACT_ID,
    LIFECYCLE_BARRIER_CONTRACT_ID,
    LOCAL_REFERENCE_CONTRACT_ID,
    MEASURED_TWIST_CONTRACT_ID,
    ActiveLifecycleConfigContext,
    FinalIssuedReceiptContext,
    LidarSnapshot,
    LocalReferenceSnapshot,
    MeasuredTwistSnapshot,
)
from mecanum_nav_rl.observations.v3_snapshot_validation import (
    FixtureBindingClaims,
    validate_observation_inputs,
)


CONFIG_HASH = "a" * 64


def matching_inputs():
    context = ActiveLifecycleConfigContext(
        LIFECYCLE_BARRIER_CONTRACT_ID, 4, 2, 9, CONFIG_HASH)
    common = (4, 2, 9, CONFIG_HASH)
    return {
        "context": context,
        "lidar": LidarSnapshot(LIDAR_CONTRACT_ID, FRAME_TF_CONTRACT_ID, *common,
                                "lidar_frame", (0.5,) * 72),
        "local_reference": LocalReferenceSnapshot(
            LOCAL_REFERENCE_CONTRACT_ID, FRAME_TF_CONTRACT_ID, *common,
            "base_link", (0.25, 0.0, 1.0)),
        "measured_twist": MeasuredTwistSnapshot(
            MEASURED_TWIST_CONTRACT_ID, FRAME_TF_CONTRACT_ID, *common,
            "base_link", (0.1, 0.0, 0.0)),
        "receipt": FinalIssuedReceiptContext(
            LIFECYCLE_BARRIER_CONTRACT_ID, FRAME_TF_CONTRACT_ID, *common,
            "base_link", (0.0, 0.0, 0.0)),
    }


def validate(values):
    return validate_observation_inputs(**values)


def test_matching_immutable_snapshots_validate():
    assert validate(matching_inputs()) is not None


@pytest.mark.parametrize("name", ["lidar", "local_reference", "measured_twist", "receipt"])
def test_missing_snapshot_is_not_ready(name):
    values = matching_inputs()
    values[name] = None
    assert validate(values) is None


@pytest.mark.parametrize("name", ["lidar", "local_reference", "measured_twist", "receipt"])
def test_wrong_contract_identity_is_rejected(name):
    values = matching_inputs()
    values[name] = replace(values[name], contract_id="unapproved/v0")
    assert validate(values) is None


@pytest.mark.parametrize("field", ["episode_generation", "reset_epoch", "runtime_generation", "config_hash"])
def test_each_identity_mismatch_is_rejected(field):
    values = matching_inputs()
    value = values["measured_twist"]
    replacement = "b" * 64 if field == "config_hash" else getattr(value, field) + 1
    values["measured_twist"] = replace(value, **{field: replacement})
    assert validate(values) is None


@pytest.mark.parametrize(("name", "frame"), [
    ("lidar", "RPLiDAR_A1M8_1"),
    ("lidar", "base_scan"),
    ("local_reference", "map"),
    ("measured_twist", "odom"),
    ("receipt", "odom"),
])
def test_wrong_or_legacy_frame_is_rejected(name, frame):
    values = matching_inputs()
    values[name] = replace(values[name], frame_id=frame)
    assert validate(values) is None


def test_wrong_frame_contract_identity_is_rejected():
    values = matching_inputs()
    values["lidar"] = replace(values["lidar"], frame_contract_id="other-frame-contract/v1")
    assert validate(values) is None


@pytest.mark.parametrize(("name", "field", "bad_value"), [
    ("lidar", "sectors", (0.5,) * 71),
    ("local_reference", "features", (0.25, 1.0)),
    ("measured_twist", "components", (0.1, 0.0, float("nan"))),
    ("receipt", "final_command", (0.0, 0.0, float("inf"))),
])
def test_missing_wrong_shape_or_nonfinite_values_cannot_validate(name, field, bad_value):
    values = matching_inputs()
    with pytest.raises((TypeError, ValueError)):
        replace(values[name], **{field: bad_value})


def test_untyped_input_and_wrong_context_contract_are_rejected():
    values = matching_inputs()
    values["lidar"] = object()
    assert validate(values) is None
    values = matching_inputs()
    values["context"] = replace(values["context"], contract_id="other/v3")
    assert validate(values) is None


def test_unverifiable_or_mismatching_fixture_claims_are_rejected():
    values = matching_inputs()
    values["lidar"] = replace(values["lidar"], topic_claim="/scan")
    assert validate(values) is None
    values["fixture_claims"] = FixtureBindingClaims(lidar_topic="/other")
    assert validate(values) is None


def test_exact_injected_fixture_claims_are_checked_without_becoming_defaults():
    values = matching_inputs()
    values["lidar"] = replace(
        values["lidar"], topic_claim="/scan", type_claim="sensor_msgs/msg/LaserScan")
    values["fixture_claims"] = FixtureBindingClaims(
        lidar_topic="/scan", lidar_type="sensor_msgs/msg/LaserScan")
    assert validate(values) is not None


def test_constructors_reject_coercion_and_invalid_hash():
    with pytest.raises(TypeError):
        ActiveLifecycleConfigContext(LIFECYCLE_BARRIER_CONTRACT_ID, True, 2, 9, CONFIG_HASH)
    with pytest.raises(ValueError):
        ActiveLifecycleConfigContext(LIFECYCLE_BARRIER_CONTRACT_ID, 4, 2, 9, "not-a-hash")
