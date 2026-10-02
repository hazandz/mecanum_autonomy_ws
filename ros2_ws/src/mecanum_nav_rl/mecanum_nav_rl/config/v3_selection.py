"""Explicit caller-owned V3 asset selection without filesystem access."""

from __future__ import annotations

from typing import Annotated, ClassVar

from pydantic import StringConstraints, field_validator, model_validator

from mecanum_nav_rl.config.v3_models import ConfigModelV3, RuntimeSelectionV3


OpaqueV3AssetPath = Annotated[
    str, StringConstraints(strict=True, min_length=1)
]


class ExplicitV3AssetSelection(ConfigModelV3):
    """Immutable caller input naming the selected V3 asset paths.

    Values remain opaque strings. This type validates neither filesystem
    availability nor YAML contents and deliberately does not infer path meaning.
    """

    runtime_selection: RuntimeSelectionV3
    base_path: OpaqueV3AssetPath
    frames_path: OpaqueV3AssetPath
    topics_catalog_path: OpaqueV3AssetPath
    qos_catalog_path: OpaqueV3AssetPath
    state_localization_path: OpaqueV3AssetPath
    system_contracts_path: OpaqueV3AssetPath
    acceptance_path: OpaqueV3AssetPath
    measurements_catalog_path: OpaqueV3AssetPath
    ppo_path: OpaqueV3AssetPath
    profile_path: OpaqueV3AssetPath
    mode_path: OpaqueV3AssetPath

    _PATH_FIELD_NAMES: ClassVar[tuple[str, ...]] = (
        "base_path",
        "frames_path",
        "topics_catalog_path",
        "qos_catalog_path",
        "state_localization_path",
        "system_contracts_path",
        "acceptance_path",
        "measurements_catalog_path",
        "ppo_path",
        "profile_path",
        "mode_path",
    )

    @field_validator(*_PATH_FIELD_NAMES)
    @classmethod
    def validate_opaque_path(cls, value: str) -> str:
        """Reject unsafe empty path tokens while preserving their exact spelling."""

        if not value.strip():
            raise ValueError("asset path must not be empty or whitespace-only")
        if "\x00" in value:
            raise ValueError("asset path must not contain a NUL byte")
        return value

    @model_validator(mode="after")
    def validate_unique_paths(self) -> "ExplicitV3AssetSelection":
        """Require each caller-provided asset path to name a distinct input."""

        paths = tuple(getattr(self, name) for name in self._PATH_FIELD_NAMES)
        if len(set(paths)) != len(paths):
            raise ValueError("asset paths must be unique across selection fields")
        return self
