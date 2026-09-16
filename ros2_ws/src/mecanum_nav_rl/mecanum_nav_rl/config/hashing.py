"""Create stable identifiers for validated runtime configuration."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from mecanum_nav_rl.config.models import ResolvedConfig


CONFIG_HASH_ALGORITHM = "sha256"
CONFIG_HASH_VERSION = "v1"
DEFAULT_SHORT_CONFIG_ID_LENGTH = 12
FULL_SHA256_HEX_LENGTH = 64


def _require_resolved_config(config: ResolvedConfig) -> None:
    """Reject data that has not passed ResolvedConfig validation."""

    if not isinstance(config, ResolvedConfig):
        raise TypeError(
            "config must be a validated ResolvedConfig instance"
        )


def canonical_config_json(config: ResolvedConfig) -> str:
    """Serialize a validated configuration into stable canonical JSON."""

    _require_resolved_config(config)

    hash_payload = {
        "config_hash_version": CONFIG_HASH_VERSION,
        "config": config.model_dump(mode="json"),
    }

    try:
        return json.dumps(
            hash_payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )
    except (TypeError, ValueError) as error:
        raise ValueError(
            "validated configuration cannot be converted to canonical JSON"
        ) from error


def config_sha256(config: ResolvedConfig) -> str:
    """
    Return the full 64-character SHA-256 hash of one configuration.

    Store this full value in checkpoint metadata and reports.
    """

    canonical_json = canonical_config_json(config)
    payload = canonical_json.encode("utf-8")

    return hashlib.sha256(payload).hexdigest()


def short_config_id(
    config: ResolvedConfig,
    length: int = DEFAULT_SHORT_CONFIG_ID_LENGTH,
) -> str:
    """
    Return a short prefix of the full configuration hash.

    Use this only for readable artifact names. The full hash remains the
    official configuration identifier.
    """

    if isinstance(length, bool) or not isinstance(length, int):
        raise TypeError("length must be an integer")

    if not 1 <= length <= FULL_SHA256_HEX_LENGTH:
        raise ValueError(
            "length must be between 1 and "
            f"{FULL_SHA256_HEX_LENGTH}"
        )

    return config_sha256(config)[:length]