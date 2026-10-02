"""Canonical SHA-256 identity for post-resolution architecture v3 config."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
import hashlib
import json

from mecanum_nav_rl.config.v3_models import ResolvedConfigV3


V3_CONFIG_HASH_ALGORITHM = "sha256"
V3_CONFIG_HASH_SCHEMA = "mecanum_nav_rl.resolved_config.v3"


def canonical_v3_hash_payload(unhashed_mapping: Mapping[str, object]) -> dict[str, object]:
    """Build a canonical hash payload before, and explicitly without, config_hash."""

    if not isinstance(unhashed_mapping, Mapping):
        raise TypeError("unhashed v3 config must be a mapping")
    payload = deepcopy(dict(unhashed_mapping))
    provenance = payload.get("provenance")
    if not isinstance(provenance, Mapping):
        raise ValueError("unhashed v3 config requires provenance mapping")
    if "config_hash" in provenance:
        raise ValueError("caller must not provide provenance.config_hash")
    return {
        "config_hash_schema": V3_CONFIG_HASH_SCHEMA,
        "resolved_config_without_config_hash": payload,
    }


def canonical_v3_config_json(unhashed_mapping: Mapping[str, object]) -> str:
    """Serialize exactly the non-self-referential v3 hash payload."""

    try:
        return json.dumps(
            canonical_v3_hash_payload(unhashed_mapping),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )
    except (TypeError, ValueError) as error:
        raise ValueError("v3 config hash payload is not canonical JSON") from error


def config_v3_sha256(unhashed_mapping: Mapping[str, object]) -> str:
    """Return SHA-256 of canonical post-layer, pre-config-hash v3 data."""

    return hashlib.sha256(canonical_v3_config_json(unhashed_mapping).encode("utf-8")).hexdigest()


def hash_payload_from_resolved_v3(config: ResolvedConfigV3) -> dict[str, object]:
    """Recreate the non-self-referential payload from a final resolved config."""

    if not isinstance(config, ResolvedConfigV3):
        raise TypeError("config must be ResolvedConfigV3")
    raw = config.model_dump(mode="json")
    provenance = raw["provenance"]
    assert isinstance(provenance, dict)
    del provenance["config_hash"]
    return canonical_v3_hash_payload(raw)
