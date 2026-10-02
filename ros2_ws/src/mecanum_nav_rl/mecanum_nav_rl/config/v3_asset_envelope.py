"""Explicit raw V3 asset envelope without loading or composition behavior."""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import field_validator, model_validator

from mecanum_nav_rl.config.v3_models import ConfigModelV3


class CanonicalV3AssetEnvelope(ConfigModelV3):
    """One raw asset split explicitly into structural and catalog regions."""

    fragment: Mapping[str, object]
    catalog: Mapping[str, object]

    @field_validator("fragment", "catalog", mode="before")
    @classmethod
    def validate_raw_region_keys(cls, value: object) -> object:
        """Reject non-string keys before Pydantic can coerce mapping keys."""

        if not isinstance(value, Mapping):
            return value
        for key in value:
            if not isinstance(key, str):
                raise ValueError("asset envelope region keys must be strings")
            if not key:
                raise ValueError("asset envelope region keys must not be empty")
            if "\x00" in key:
                raise ValueError("asset envelope region keys must not contain a NUL byte")
        return value

    @model_validator(mode="after")
    def validate_regions(self) -> "CanonicalV3AssetEnvelope":
        """Keep a non-empty envelope and one top-level semantic owner per key."""

        if not self.fragment and not self.catalog:
            raise ValueError("asset envelope must contain fragment or catalog content")
        duplicate_keys = set(self.fragment) & set(self.catalog)
        if duplicate_keys:
            raise ValueError(
                "asset envelope top-level semantic keys must not appear in both "
                "fragment and catalog"
            )
        return self
