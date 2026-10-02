"""Offline tests for the explicit raw V3 asset-envelope boundary."""

from __future__ import annotations

import ast
import inspect

import pytest
from pydantic import ValidationError

from mecanum_nav_rl.config import CanonicalV3AssetEnvelope as PackageEnvelope
from mecanum_nav_rl.config.v3_asset_envelope import CanonicalV3AssetEnvelope
from mecanum_nav_rl.config.v3_models import ResolvedConfigV3


def test_fragment_only_envelope_is_valid() -> None:
    envelope = CanonicalV3AssetEnvelope(fragment={"runtime": {}}, catalog={})
    assert envelope.fragment == {"runtime": {}}
    assert envelope.catalog == {}


def test_catalog_only_envelope_is_valid() -> None:
    envelope = CanonicalV3AssetEnvelope(fragment={}, catalog={"metadata": {}})
    assert envelope.fragment == {}
    assert envelope.catalog == {"metadata": {}}


def test_disjoint_fragment_and_catalog_regions_are_valid() -> None:
    envelope = CanonicalV3AssetEnvelope(
        fragment={"frames_tf": {"map": "map"}},
        catalog={"asset_notes": {"pre_resolution": True}},
    )
    assert set(envelope.fragment) == {"frames_tf"}
    assert set(envelope.catalog) == {"asset_notes"}


def test_both_regions_empty_are_rejected() -> None:
    with pytest.raises(ValidationError, match="fragment or catalog"):
        CanonicalV3AssetEnvelope(fragment={}, catalog={})


def test_extra_root_key_is_rejected() -> None:
    with pytest.raises(ValidationError):
        CanonicalV3AssetEnvelope.model_validate(
            {"fragment": {"base": {}}, "catalog": {}, "extra": {}}
        )


@pytest.mark.parametrize("field_name", ("fragment", "catalog"))
@pytest.mark.parametrize("invalid", ([], "not-a-mapping", 1))
def test_non_mapping_region_is_rejected(field_name: str, invalid: object) -> None:
    payload: dict[str, object] = {"fragment": {"base": {}}, "catalog": {}}
    payload[field_name] = invalid
    with pytest.raises(ValidationError):
        CanonicalV3AssetEnvelope.model_validate(payload)


@pytest.mark.parametrize("invalid_key", (1, True))
@pytest.mark.parametrize("field_name", ("fragment", "catalog"))
def test_non_string_region_key_is_rejected_before_pydantic_coercion(
    field_name: str, invalid_key: object
) -> None:
    payload: dict[str, object] = {"fragment": {"base": {}}, "catalog": {}}
    payload[field_name] = {invalid_key: {}}
    if field_name == "fragment":
        payload["catalog"] = {"metadata": {}}
    with pytest.raises(ValidationError, match="keys must be strings"):
        CanonicalV3AssetEnvelope.model_validate(payload)


@pytest.mark.parametrize("invalid_key", ("", "key\x00with-nul"))
@pytest.mark.parametrize("field_name", ("fragment", "catalog"))
def test_empty_or_nul_region_key_is_rejected(
    field_name: str, invalid_key: str
) -> None:
    payload: dict[str, object] = {"fragment": {"base": {}}, "catalog": {}}
    payload[field_name] = {invalid_key: {}}
    if field_name == "fragment":
        payload["catalog"] = {"metadata": {}}
    with pytest.raises(ValidationError):
        CanonicalV3AssetEnvelope.model_validate(payload)


def test_duplicate_top_level_semantic_key_is_rejected() -> None:
    with pytest.raises(ValidationError, match="must not appear in both"):
        CanonicalV3AssetEnvelope(
            fragment={"runtime": {}}, catalog={"runtime": {"metadata": True}}
        )


def test_envelope_object_is_immutable_at_the_v3_public_boundary() -> None:
    envelope = CanonicalV3AssetEnvelope(fragment={"base": {}}, catalog={})
    with pytest.raises(ValidationError):
        envelope.fragment = {}  # type: ignore[misc]


def test_package_export_is_module_owned_not_resolved_and_not_selection() -> None:
    assert PackageEnvelope is CanonicalV3AssetEnvelope
    envelope = CanonicalV3AssetEnvelope(fragment={"base": {}}, catalog={})
    assert not isinstance(envelope, ResolvedConfigV3)
    assert type(envelope) is CanonicalV3AssetEnvelope


def test_envelope_module_has_no_loader_composition_hash_filesystem_or_runtime_imports() -> None:
    module = __import__("mecanum_nav_rl.config.v3_asset_envelope", fromlist=["*"])
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
        "mecanum_nav_rl.config.v3_selection",
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
