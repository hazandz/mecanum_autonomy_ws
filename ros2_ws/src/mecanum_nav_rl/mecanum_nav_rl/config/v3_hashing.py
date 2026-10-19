"""Canonical SHA-256 identity for post-resolution architecture v3 config."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from typing import Any

from mecanum_nav_rl.config.v3_models import ResolvedConfigV3


V3_CONFIG_HASH_ALGORITHM = "sha256"
V3_CONFIG_HASH_SCHEMA = "mecanum_nav_rl.resolved_config.v3"


def _jcs_number(value: int | float) -> str:
    """Serialize an IEEE-754 number using RFC 8785 ECMAScript formatting."""
    if isinstance(value, bool):
        raise TypeError("boolean is not a JSON number")
    if isinstance(value, int):
        if abs(value) > 9007199254740991:
            raise ValueError("integer is outside the JCS interoperable range")
        return str(value)
    if not math.isfinite(value):
        raise ValueError("JCS does not permit non-finite numbers")
    if value == 0.0:
        return "0"
    negative = value < 0
    raw = repr(abs(value)).lower()
    if "e" in raw:
        mantissa, exponent_text = raw.split("e", 1)
        exponent = int(exponent_text)
    else:
        mantissa, exponent = raw, 0
    whole, _, fraction = mantissa.partition(".")
    digits = whole + fraction
    decimal_position = len(whole) + exponent
    while len(digits) > 1 and digits.startswith("0"):
        digits = digits[1:]
        decimal_position -= 1
    while len(digits) > 1 and digits.endswith("0"):
        digits = digits[:-1]
    if 0 < decimal_position <= 21:
        if decimal_position >= len(digits):
            result = digits + ("0" * (decimal_position - len(digits)))
        else:
            result = digits[:decimal_position] + "." + digits[decimal_position:]
    elif -6 < decimal_position <= 0:
        result = "0." + ("0" * (-decimal_position)) + digits
    else:
        exponent = decimal_position - 1
        result = digits[0]
        if len(digits) > 1:
            result += "." + digits[1:]
        result += "e" + ("+" if exponent >= 0 else "") + str(exponent)
    return ("-" if negative else "") + result


def _jcs(value: Any) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, (int, float)):
        return _jcs_number(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise TypeError("JCS object keys must be strings")
        keys = sorted(value, key=lambda key: key.encode("utf-16-be"))
        return "{" + ",".join(_jcs(key) + ":" + _jcs(value[key]) for key in keys) + "}"
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return "[" + ",".join(_jcs(item) for item in value) + "]"
    raise TypeError(f"unsupported JCS value: {type(value).__name__}")


def canonical_v3_hash_payload(unhashed_mapping: Mapping[str, object]) -> dict[str, object]:
    """Return the complete resolved document, omitting only config_hash."""

    if not isinstance(unhashed_mapping, Mapping):
        raise TypeError("unhashed v3 config must be a mapping")
    payload = deepcopy(dict(unhashed_mapping))
    provenance = payload.get("provenance")
    if not isinstance(provenance, dict):
        raise ValueError("unhashed v3 config requires provenance mapping")
    provenance.pop("config_hash", None)
    return payload


def canonical_v3_config_json(unhashed_mapping: Mapping[str, object]) -> str:
    """Serialize exactly the non-self-referential v3 hash payload."""

    return _jcs(canonical_v3_hash_payload(unhashed_mapping))


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
