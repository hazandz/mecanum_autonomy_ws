"""Offline tests for the caller-owned V3 asset-selection contract."""

from __future__ import annotations

import ast
import inspect

import pytest
from pydantic import ValidationError

from mecanum_nav_rl.config import ExplicitV3AssetSelection as PackageSelection
from mecanum_nav_rl.config.v3_models import (
    NavigationModeV3,
    ResolvedConfigV3,
    RuntimeProfileV3,
    RuntimeSelectionV3,
)
from mecanum_nav_rl.config.v3_selection import ExplicitV3AssetSelection


def _runtime(
    profile: RuntimeProfileV3 = RuntimeProfileV3.SIM_TRAIN,
    mode: NavigationModeV3 = NavigationModeV3.LOCAL_TRAINING,
) -> RuntimeSelectionV3:
    return RuntimeSelectionV3(
        runtime_profile=profile,
        navigation_mode=mode,
        use_sim_time=profile is not RuntimeProfileV3.DEPLOY_REAL,
    )


def _payload() -> dict[str, object]:
    return {
        "runtime_selection": _runtime(),
        "base_path": "opaque-base",
        "frames_path": "opaque-frames",
        "topics_catalog_path": "opaque-topics",
        "qos_catalog_path": "opaque-qos",
        "state_localization_path": "opaque-state-localization",
        "system_contracts_path": "opaque-system-contracts",
        "acceptance_path": "opaque-acceptance",
        "measurements_catalog_path": "opaque-measurements",
        "ppo_path": "opaque-ppo",
        "profile_path": "opaque-profile",
        "mode_path": "opaque-mode",
    }


def test_valid_selection_is_immutable_and_preserves_opaque_paths() -> None:
    payload = _payload()
    payload["base_path"] = " ./caller-owned/base path.yaml "
    selection = ExplicitV3AssetSelection.model_validate(payload)
    assert selection.base_path == " ./caller-owned/base path.yaml "
    assert selection.state_localization_path == "opaque-state-localization"
    assert selection.system_contracts_path == "opaque-system-contracts"
    assert selection.runtime_selection == _runtime()
    with pytest.raises(ValidationError):
        selection.base_path = "different"  # type: ignore[misc]


def test_valid_d03_pair_is_accepted_through_nested_runtime_selection() -> None:
    payload = _payload()
    payload["runtime_selection"] = _runtime(
        RuntimeProfileV3.DEPLOY_SIM, NavigationModeV3.HYBRID_AI_LOCAL
    )
    selection = ExplicitV3AssetSelection.model_validate(payload)
    assert selection.runtime_selection.navigation_mode is NavigationModeV3.HYBRID_AI_LOCAL


def test_invalid_d03_pair_is_rejected_by_nested_runtime_selection() -> None:
    payload = _payload()
    payload["runtime_selection"] = {
        "runtime_profile": RuntimeProfileV3.SIM_TRAIN,
        "navigation_mode": NavigationModeV3.NAV2_BASELINE,
        "use_sim_time": True,
    }
    with pytest.raises(ValidationError, match="not permitted"):
        ExplicitV3AssetSelection.model_validate(payload)


@pytest.mark.parametrize("invalid", ("", " \t", "opaque\x00path"))
@pytest.mark.parametrize(
    "field_name",
    ExplicitV3AssetSelection._PATH_FIELD_NAMES,
)
def test_empty_whitespace_and_nul_paths_are_rejected(
    field_name: str, invalid: str
) -> None:
    payload = _payload()
    payload[field_name] = invalid
    with pytest.raises(ValidationError):
        ExplicitV3AssetSelection.model_validate(payload)


def test_duplicate_paths_are_rejected() -> None:
    payload = _payload()
    payload["frames_path"] = payload["base_path"]
    with pytest.raises(ValidationError, match="must be unique"):
        ExplicitV3AssetSelection.model_validate(payload)


@pytest.mark.parametrize(
    "field_name", ("state_localization_path", "system_contracts_path")
)
def test_future_source_paths_are_required(field_name: str) -> None:
    payload = _payload()
    del payload[field_name]
    with pytest.raises(ValidationError):
        ExplicitV3AssetSelection.model_validate(payload)


@pytest.mark.parametrize(
    "field_name", ("state_localization_path", "system_contracts_path")
)
def test_future_source_paths_reject_duplicates(field_name: str) -> None:
    payload = _payload()
    payload[field_name] = payload["base_path"]
    with pytest.raises(ValidationError, match="must be unique"):
        ExplicitV3AssetSelection.model_validate(payload)


def test_distinct_arbitrary_path_names_are_accepted_without_filename_inference() -> None:
    payload = _payload()
    payload["profile_path"] = "caller-chosen-alpha"
    payload["mode_path"] = "caller-chosen-beta"
    payload["state_localization_path"] = "caller-chosen-gamma"
    payload["system_contracts_path"] = "caller-chosen-delta"
    selection = ExplicitV3AssetSelection.model_validate(payload)
    assert selection.profile_path == "caller-chosen-alpha"
    assert selection.mode_path == "caller-chosen-beta"
    assert selection.state_localization_path == "caller-chosen-gamma"
    assert selection.system_contracts_path == "caller-chosen-delta"


def test_selection_module_has_no_loader_composition_hash_filesystem_or_runtime_imports() -> None:
    module = __import__("mecanum_nav_rl.config.v3_selection", fromlist=["*"])
    tree = ast.parse(inspect.getsource(module))
    forbidden_import_roots = {
        "pathlib", "os", "yaml", "rclpy", "gazebo", "gz", "ignition",
        "gymnasium", "stable_baselines3",
    }
    forbidden_modules = {
        "mecanum_nav_rl.config.v3_loader",
        "mecanum_nav_rl.config.v3_composition",
        "mecanum_nav_rl.config.v3_compiler",
        "mecanum_nav_rl.config.v3_hashing",
    }
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.add(node.module)
    assert not {
        name.split(".", 1)[0] for name in imported
    } & forbidden_import_roots
    assert not imported & forbidden_modules

    forbidden_attributes = {
        "glob", "rglob", "iterdir", "exists", "is_file", "resolve", "scandir",
        "load", "safe_load", "compose", "compile", "hash",
    }
    assert not {
        node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
    } & forbidden_attributes


def test_public_package_import_is_module_owned_and_not_resolved_config() -> None:
    assert PackageSelection is ExplicitV3AssetSelection
    selection = ExplicitV3AssetSelection.model_validate(_payload())
    assert not isinstance(selection, ResolvedConfigV3)
    assert type(selection) is ExplicitV3AssetSelection
