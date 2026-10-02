"""Fail-closed core-only YAML and mapping input for architecture v3 config."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml
from yaml.constructor import ConstructorError
from yaml.nodes import MappingNode


class V3UniqueKeySafeLoader(yaml.SafeLoader):
    """Safe YAML loader which rejects duplicate keys at every mapping level."""


def _construct_unique_mapping(
    loader: V3UniqueKeySafeLoader,
    node: MappingNode,
    deep: bool = False,
) -> dict[Any, Any]:
    if not isinstance(node, MappingNode):
        raise ConstructorError(None, None, "expected a mapping", node.start_mark)
    loader.flatten_mapping(node)
    result: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        try:
            duplicate = key in result
        except TypeError as error:
            raise ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                "found an unhashable mapping key",
                key_node.start_mark,
            ) from error
        if duplicate:
            raise ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                f"found duplicate key: {key!r}",
                key_node.start_mark,
            )
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


V3UniqueKeySafeLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_unique_mapping
)


def _validate_mapping(value: object, *, location: str = "<root>") -> None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if not isinstance(key, str):
                raise ValueError(f"v3 config key at {location} must be a string")
            _validate_mapping(nested, location=f"{location}.{key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _validate_mapping(nested, location=f"{location}[{index}]")


def load_v3_mapping(value: Mapping[str, object]) -> dict[str, object]:
    """Validate and copy one in-memory config layer without mutation or I/O."""

    if not isinstance(value, Mapping):
        raise TypeError("v3 config layer must be a mapping")
    _validate_mapping(value)
    return deepcopy(dict(value))


def load_v3_yaml_mapping(config_path: str | Path) -> dict[str, object]:
    """Read one explicit UTF-8 YAML layer; no discovery, defaults, or env I/O."""

    path = Path(config_path)
    if not path.is_file():
        raise FileNotFoundError(f"v3 configuration file does not exist: {path}")
    if path.suffix.lower() not in {".yaml", ".yml"}:
        raise ValueError("v3 configuration file must use .yaml or .yml")
    try:
        with path.open("r", encoding="utf-8") as handle:
            loaded = yaml.load(handle, Loader=V3UniqueKeySafeLoader)
    except UnicodeDecodeError as error:
        raise ValueError(f"v3 configuration must be valid UTF-8: {path}") from error
    except yaml.YAMLError as error:
        raise ValueError(f"invalid v3 YAML configuration {path}: {error}") from error
    if not isinstance(loaded, Mapping):
        raise ValueError("v3 configuration root must be a mapping")
    return load_v3_mapping(loaded)
