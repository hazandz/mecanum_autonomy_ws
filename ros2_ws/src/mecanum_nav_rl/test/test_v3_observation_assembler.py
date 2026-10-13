import ast
from pathlib import Path
from dataclasses import replace
import sys
from types import ModuleType

import numpy as np

# Load only the new pure-core namespace. The existing observations package
# initializer imports unrelated configuration dependencies.
_PACKAGE_DIR = Path(__file__).parents[1] / "mecanum_nav_rl"
for _name, _path in (("mecanum_nav_rl", _PACKAGE_DIR),
                     ("mecanum_nav_rl.observations", _PACKAGE_DIR / "observations")):
    if _name not in sys.modules:
        _module = ModuleType(_name)
        _module.__path__ = [str(_path)]
        sys.modules[_name] = _module

from mecanum_nav_rl.observations.v3_observation_assembler import assemble_observation
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
from mecanum_nav_rl.observations.v3_snapshot_validation import validate_observation_inputs


def matching_inputs():
    context = ActiveLifecycleConfigContext(LIFECYCLE_BARRIER_CONTRACT_ID, 4, 2, 9, "a" * 64)
    common = (4, 2, 9, "a" * 64)
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


def test_valid_matching_inputs_produce_one_read_only_81d_float32_vector():
    validated = validate_observation_inputs(**matching_inputs())
    result = assemble_observation(validated)
    assert result.ready is True
    assert result.vector.shape == (81,)
    assert result.vector.dtype == np.dtype(np.float32)
    assert not result.vector.flags.writeable


def test_invalid_inputs_and_mismatches_produce_no_vector():
    values = matching_inputs()
    values["receipt"] = replace(values["receipt"], config_hash="b" * 64)
    invalid = validate_observation_inputs(**values)
    result = assemble_observation(invalid)
    assert result.ready is False
    assert result.vector is None


def test_nonvalidated_or_missing_token_produces_no_vector():
    for value in (None, object()):
        result = assemble_observation(value)
        assert result.ready is False
        assert result.vector is None


def test_float32_overflow_fails_without_partial_vector():
    values = matching_inputs()
    values["lidar"] = replace(values["lidar"], sectors=(1.0e100,) * 72)
    validated = validate_observation_inputs(**values)
    result = assemble_observation(validated)
    assert result.ready is False
    assert result.vector is None


def test_pure_core_modules_have_no_forbidden_runtime_imports():
    package = Path(__file__).parents[1] / "mecanum_nav_rl" / "observations"
    modules = [package / name for name in (
        "v3_snapshot_types.py", "v3_snapshot_validation.py",
        "v3_observation_assembler.py", "v3_internal_boundaries.py")]
    forbidden = {"rclpy", "tf2_ros", "gazebo", "nav2_msgs", "sensor_msgs",
                 "nav_msgs", "geometry_msgs", "ros_gz"}
    for module in modules:
        tree = ast.parse(module.read_text(encoding="utf-8"))
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module.split(".")[0])
        assert forbidden.isdisjoint(imports), module.name


def test_active_context_requires_lifecycle_contract_identity():
    wrong = ActiveLifecycleConfigContext("other/v3", 4, 2, 9, "a" * 64)
    values = matching_inputs()
    values["context"] = wrong
    assert validate_observation_inputs(**values) is None
