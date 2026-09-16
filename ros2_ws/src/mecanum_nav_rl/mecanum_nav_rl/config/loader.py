"""Load and validate YAML configuration files."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml
from yaml.constructor import ConstructorError
from yaml.nodes import MappingNode

from mecanum_nav_rl.config.models import ResolvedConfig


class UniqueKeySafeLoader(yaml.SafeLoader):
    """
    Safe YAML loader that rejects duplicate mapping keys.

    This class keeps the safety behavior of yaml.SafeLoader while adding
    duplicate-key detection for every YAML mapping.
    """


def _construct_unique_mapping(
    loader: UniqueKeySafeLoader,
    node: MappingNode,
    deep: bool = False,
) -> dict[Any, Any]:
    """Construct one YAML mapping and reject duplicate keys."""

    if not isinstance(node, MappingNode):
        raise ConstructorError(
            None,
            None,
            "expected a YAML mapping node",
            node.start_mark,
        )

    loader.flatten_mapping(node)

    mapping: dict[Any, Any] = {}

    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)

        try:
            key_already_exists = key in mapping
        except TypeError as error:
            raise ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                "found an unhashable mapping key",
                key_node.start_mark,
            ) from error

        if key_already_exists:
            raise ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                f"found duplicate key: {key!r}",
                key_node.start_mark,
            )

        value = loader.construct_object(value_node, deep=deep)
        mapping[key] = value

    return mapping


UniqueKeySafeLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


def _format_key_path(key_path: tuple[str, ...]) -> str:
    """Format a nested YAML key path for an error message."""

    return ".".join(key_path) if key_path else "<root>"


def _validate_mapping_keys(
    value: object,
    *,
    key_path: tuple[str, ...] = (),
) -> None:
    """
    Recursively ensure every YAML mapping uses string keys.

    Lists are traversed because they may contain mappings too.
    """

    if isinstance(value, Mapping):
        for key, nested_value in value.items():
            location = _format_key_path(key_path)

            if not isinstance(key, str):
                raise ValueError(
                    "all YAML mapping keys must be strings; "
                    f"found {key!r} inside '{location}'"
                )

            _validate_mapping_keys(
                nested_value,
                key_path=key_path + (key,),
            )

    elif isinstance(value, list):
        for index, item in enumerate(value):
            _validate_mapping_keys(
                item,
                key_path=key_path + (f"[{index}]",),
            )


def _validate_yaml_path(config_path: str | Path) -> Path:
    """Validate a YAML file path before attempting to read it."""

    path = Path(config_path).expanduser()

    if not path.exists():
        raise FileNotFoundError(
            f"configuration file does not exist: {path}"
        )

    if not path.is_file():
        raise IsADirectoryError(
            f"configuration path is not a file: {path}"
        )

    if path.suffix.lower() not in {".yaml", ".yml"}:
        raise ValueError(
            "configuration file must use the '.yaml' or '.yml' extension: "
            f"{path}"
        )

    return path


def load_yaml_mapping(config_path: str | Path) -> dict[str, object]:
    """
    Read one YAML file as a raw key-value mapping.

    This function does not require the YAML file to contain a complete
    ResolvedConfig. It can read base files, profile overlays, and future
    experiment configuration files.

    Raises:
        FileNotFoundError:
            If the requested path does not exist.

        IsADirectoryError:
            If the requested path is a directory.

        ValueError:
            If the extension, text encoding, YAML syntax, duplicate keys,
            mapping keys, file contents, or root structure are invalid.
    """

    path = _validate_yaml_path(config_path)

    try:
        with path.open(mode="r", encoding="utf-8") as file_handle:
            raw_data = yaml.load(
                file_handle,
                Loader=UniqueKeySafeLoader,
            )
    except UnicodeDecodeError as error:
        raise ValueError(
            f"configuration file must be valid UTF-8: {path}"
        ) from error
    except yaml.YAMLError as error:
        raise ValueError(
            f"invalid YAML configuration file '{path}': {error}"
        ) from error
    except OSError as error:
        raise OSError(
            f"could not read configuration file: {path}"
        ) from error

    if raw_data is None:
        raise ValueError(
            f"configuration file is empty: {path}"
        )

    if not isinstance(raw_data, dict):
        raise ValueError(
            "configuration root must be a key-value mapping: "
            f"{path}"
        )

    _validate_mapping_keys(raw_data)

    return raw_data


def load_config(config_path: str | Path) -> ResolvedConfig:
    """
    Load and validate one complete YAML configuration file.

    Unlike load_yaml_mapping(), this function requires all fields needed
    to construct ResolvedConfig.
    """

    raw_data = load_yaml_mapping(config_path)

    return ResolvedConfig.model_validate(raw_data)