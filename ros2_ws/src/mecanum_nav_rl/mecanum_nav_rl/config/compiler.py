"""Compile layered YAML configuration into one validated configuration."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from pathlib import Path

from mecanum_nav_rl.config.loader import load_yaml_mapping
from mecanum_nav_rl.config.models import (
    ResolvedConfig,
    RuntimeProfile,
)


def _format_key_path(key_path: tuple[str, ...]) -> str:
    """Format a nested configuration key path for an error message."""

    return ".".join(key_path) if key_path else "<root>"


def _validate_expected_profile(
    expected_profile: RuntimeProfile,
) -> None:
    """Ensure the caller explicitly supplies a RuntimeProfile value."""

    if not isinstance(expected_profile, RuntimeProfile):
        raise TypeError(
            "expected_profile must be a RuntimeProfile value"
        )


def deep_merge(
    base: Mapping[str, object],
    override: Mapping[str, object],
    *,
    key_path: tuple[str, ...] = (),
) -> dict[str, object]:
    """
    Merge one override mapping onto one base mapping.

    Rules:
    - Nested mappings are merged recursively.
    - Scalars and lists from override replace base values.
    - A mapping cannot replace a scalar/list, or vice versa.
    - Neither input mapping is modified.
    """

    merged: dict[str, object] = deepcopy(dict(base))

    for key, override_value in override.items():
        current_path = key_path + (key,)

        if key not in merged:
            merged[key] = deepcopy(override_value)
            continue

        base_value = merged[key]
        base_is_mapping = isinstance(base_value, Mapping)
        override_is_mapping = isinstance(override_value, Mapping)

        if base_is_mapping and override_is_mapping:
            merged[key] = deep_merge(
                base_value,
                override_value,
                key_path=current_path,
            )
            continue

        if base_is_mapping != override_is_mapping:
            location = _format_key_path(current_path)
            raise ValueError(
                "configuration layer type conflict at "
                f"'{location}': a mapping cannot replace a non-mapping "
                "value, and a non-mapping value cannot replace a mapping"
            )

        merged[key] = deepcopy(override_value)

    return merged


def compile_config_layers(
    *layers: Mapping[str, object],
    expected_profile: RuntimeProfile,
) -> ResolvedConfig:
    """
    Merge raw configuration layers and validate the final result.

    Earlier layers have lower priority than later layers. The compiled
    runtime profile must match expected_profile exactly.
    """

    _validate_expected_profile(expected_profile)

    if not layers:
        raise ValueError(
            "at least one configuration layer is required"
        )

    merged_data: dict[str, object] = {}

    for index, layer in enumerate(layers):
        if not isinstance(layer, Mapping):
            raise TypeError(
                f"configuration layer {index} must be a mapping"
            )

        if not all(isinstance(key, str) for key in layer):
            raise ValueError(
                f"configuration layer {index} must use string keys"
            )

        merged_data = deep_merge(merged_data, layer)

    config = ResolvedConfig.model_validate(merged_data)

    if config.runtime.profile != expected_profile:
        raise ValueError(
            "compiled configuration profile does not match the "
            f"expected profile: expected '{expected_profile.value}', "
            f"received '{config.runtime.profile.value}'"
        )

    return config


def compile_config(
    base_path: str | Path,
    profile_path: str | Path,
    *,
    expected_profile: RuntimeProfile,
) -> ResolvedConfig:
    """
    Load, merge, and validate a base YAML file with one profile YAML file.

    Priority order:
        base_path < profile_path

    The caller must explicitly state which runtime profile is expected.
    This prevents a mismatched or malicious profile YAML file from silently
    changing the requested runtime mode.
    """

    _validate_expected_profile(expected_profile)

    base_data = load_yaml_mapping(base_path)
    profile_data = load_yaml_mapping(profile_path)

    return compile_config_layers(
        base_data,
        profile_data,
        expected_profile=expected_profile,
    )