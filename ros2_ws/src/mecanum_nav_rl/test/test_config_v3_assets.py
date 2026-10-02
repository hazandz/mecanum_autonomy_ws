"""Offline contract tests for the parallel V3 configuration asset skeleton."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import pytest

from mecanum_nav_rl.config.v3_compiler import compile_v3_config
from mecanum_nav_rl.config.v3_loader import load_v3_yaml_mapping
from mecanum_nav_rl.config.v3_models import (
    NavigationModeV3,
    RuntimeProfileV3,
    _VALID_NAVIGATION_MODES_BY_PROFILE_V3,
)
from mecanum_nav_rl.config.v3_policy import (
    ResolutionStageV3,
    validate_profile_mode_v3,
)


_PACKAGE_ROOT = Path(__file__).resolve().parents[1]
_V3_ROOT = _PACKAGE_ROOT / "config" / "v3"
_REQUIRED_ASSETS = (
    "base.yaml",
    "profiles/sim_train.yaml",
    "profiles/sim_eval.yaml",
    "profiles/deploy_sim.yaml",
    "profiles/deploy_real.yaml",
    "modes/local_training.yaml",
    "modes/mapping.yaml",
    "modes/nav2_baseline.yaml",
    "modes/hybrid_ai_local.yaml",
    "topics.yaml",
    "qos.yaml",
    "frames.yaml",
    "acceptance.yaml",
    "measurements.yaml",
    "algorithms/ppo.yaml",
)
_TOKEN_LITERALS = {
    "FIXED_ARCH",
    "SIM_BASELINE",
    "TBD_MEASURED",
    "TBD_PROJECT_ACCEPTANCE",
    "REQUIRED_BUILD_INPUT",
}


def _asset(relative_path: str) -> Path:
    return _V3_ROOT / relative_path


def _walk_values(value: object) -> tuple[object, ...]:
    values: list[object] = [value]
    if isinstance(value, Mapping):
        for nested in value.values():
            values.extend(_walk_values(nested))
    elif isinstance(value, list):
        for nested in value:
            values.extend(_walk_values(nested))
    return tuple(values)


def _walk_tokens(value: object) -> tuple[Mapping[str, object], ...]:
    found: list[Mapping[str, object]] = []
    if isinstance(value, Mapping):
        if {"field_path", "token", "reference_id"}.issubset(value):
            found.append(value)
        for nested in value.values():
            found.extend(_walk_tokens(nested))
    elif isinstance(value, list):
        for nested in value:
            found.extend(_walk_tokens(nested))
    return tuple(found)


def test_all_required_v3_assets_exist_and_parse_fail_closed() -> None:
    assert {path.relative_to(_V3_ROOT).as_posix() for path in _V3_ROOT.rglob("*.yaml")} == set(_REQUIRED_ASSETS)
    for relative_path in _REQUIRED_ASSETS:
        assert _asset(relative_path).is_file()
        assert isinstance(load_v3_yaml_mapping(_asset(relative_path)), dict)


def test_assets_only_use_the_closed_token_taxonomy_and_no_placeholder_words() -> None:
    forbidden_placeholders = {"TBD", "TODO", "null", "default", "unknown"}
    for relative_path in _REQUIRED_ASSETS:
        payload = load_v3_yaml_mapping(_asset(relative_path))
        for token in _walk_tokens(payload):
            assert set(token) == {"field_path", "token", "reference_id"}
            assert token["token"] in _TOKEN_LITERALS
        strings = {value for value in _walk_values(payload) if isinstance(value, str)}
        assert not strings & forbidden_placeholders


def test_profile_assets_encode_the_exact_d03_time_and_mode_matrix() -> None:
    assert set(_VALID_NAVIGATION_MODES_BY_PROFILE_V3) == set(RuntimeProfileV3)
    for profile, expected_modes in _VALID_NAVIGATION_MODES_BY_PROFILE_V3.items():
        payload = load_v3_yaml_mapping(_asset(f"profiles/{profile.value}.yaml"))
        runtime = payload["runtime"]
        assert isinstance(runtime, Mapping)
        assert runtime["runtime_profile"] == profile.value
        assert runtime["use_sim_time"] is (
            profile is not RuntimeProfileV3.DEPLOY_REAL
        )
        asset_mode_names = tuple(runtime["allowed_navigation_modes"])
        asset_modes = frozenset(
            NavigationModeV3(mode_name) for mode_name in asset_mode_names
        )
        assert len(asset_mode_names) == len(asset_modes)
        assert asset_modes == expected_modes
        for mode in asset_modes:
            validate_profile_mode_v3(profile, mode)
    with pytest.raises(ValueError, match="not permitted"):
        validate_profile_mode_v3(
            RuntimeProfileV3.SIM_TRAIN, NavigationModeV3.NAV2_BASELINE
        )


def test_mode_assets_only_encode_allowed_d03_mode_literals() -> None:
    expected = {
        "local_training.yaml": "LOCAL_TRAINING",
        "mapping.yaml": "MAPPING",
        "nav2_baseline.yaml": "NAV2_BASELINE",
        "hybrid_ai_local.yaml": "HYBRID_AI_LOCAL",
    }
    for filename, mode_name in expected.items():
        payload = load_v3_yaml_mapping(_asset(f"modes/{filename}"))
        runtime = payload["runtime"]
        assert isinstance(runtime, Mapping)
        assert runtime["navigation_mode"] == mode_name
        assert mode_name in {item.value for item in NavigationModeV3}


def test_deploy_real_remains_tokenized_and_cannot_compile_as_resolved_config() -> None:
    deploy_real = load_v3_yaml_mapping(_asset("profiles/deploy_real.yaml"))
    tokens = _walk_tokens(deploy_real)
    assert {token["token"] for token in tokens} >= {
        "TBD_MEASURED",
        "REQUIRED_BUILD_INPUT",
    }
    assert not any(
        isinstance(value, (int, float)) and not isinstance(value, bool)
        for value in _walk_values(deploy_real.get("motion_limits"))
    )
    with pytest.raises(ValueError):
        compile_v3_config(
            base_layer=load_v3_yaml_mapping(_asset("base.yaml")),
            runtime_profile_layer=deploy_real,
            navigation_mode_layer=load_v3_yaml_mapping(
                _asset("modes/nav2_baseline.yaml")
            ),
            experiment_override_layer=None,
            measured_hardware_registry_layer=None,
            output_stage=ResolutionStageV3.CONFIG_INPUT,
            gate4=False,
        )


def test_v3_assets_never_claim_runtime_or_real_robot_approval() -> None:
    prohibited_claims = (
        "runtime ready",
        "measured valid",
        "gate 4 pass",
        "hil pass",
        "real robot validated",
    )
    for relative_path in _REQUIRED_ASSETS:
        text = _asset(relative_path).read_text(encoding="utf-8").lower()
        assert not any(claim in text for claim in prohibited_claims)


def test_v1_assets_remain_present_and_separate() -> None:
    legacy_base = _PACKAGE_ROOT / "config" / "base.yaml"
    legacy_profile = _PACKAGE_ROOT / "config" / "profiles" / "sim_train.yaml"
    assert legacy_base.is_file()
    assert legacy_profile.is_file()
    assert "schema_version: \"1.0\"" in legacy_base.read_text(encoding="utf-8")


def test_after_build_every_v3_asset_is_installed_with_identical_content() -> None:
    install_root = _PACKAGE_ROOT.parents[1] / "install" / "mecanum_nav_rl" / "share" / "mecanum_nav_rl" / "config" / "v3"
    for relative_path in _REQUIRED_ASSETS:
        source = _asset(relative_path)
        installed = install_root / relative_path
        assert installed.is_file(), installed
        assert installed.read_bytes() == source.read_bytes()
