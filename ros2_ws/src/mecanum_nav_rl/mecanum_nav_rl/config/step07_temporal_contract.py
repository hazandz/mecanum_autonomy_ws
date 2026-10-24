"""Run005 temporal semantic-contract loader and fail-closed binding check."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

CONTRACT_ID = "mecanum.step07-run005-temporal-coherence/v1"
CONTRACT_SHA256 = "57aa6b871fd3bcdc4ae6eb2b6f7a0dcb66b07b927516b7b0969d5e47e5c36e59"
CONTRACT_RESOURCE = "v3/contracts/step07_run005_temporal_coherence.v1.json"


def _pairs(rows: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in rows:
        if key in result:
            raise ValueError("RUN005_TEMPORAL_CONTRACT_DUPLICATE_KEY")
        result[key] = value
    return result


def _reject_constant(_: str) -> None:
    raise ValueError("RUN005_TEMPORAL_CONTRACT_NONFINITE")


def resolve_run005_semantic_resource() -> Path:
    """Return the exact source/share resource path used by the loader."""
    source_root = Path(__file__).resolve().parents[2]
    source_resource = source_root / "config" / "v3" / "contracts" / Path(CONTRACT_RESOURCE).name
    if source_resource.is_file():
        return source_resource.resolve(strict=True)
    try:
        from ament_index_python.packages import get_package_share_directory
        return (Path(get_package_share_directory("mecanum_nav_rl")) /
                "config" / "v3" / "contracts" / Path(CONTRACT_RESOURCE).name).resolve(strict=True)
    except (ImportError, OSError) as error:
        raise ValueError("RUN005_TEMPORAL_CONTRACT_RESOURCE_UNAVAILABLE") from error


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def load_run005_semantic_payload() -> dict[str, Any]:
    raw = resolve_run005_semantic_resource().read_bytes()
    if raw.startswith(b"\xef\xbb\xbf") or raw.endswith(b"\n"):
        raise ValueError("RUN005_TEMPORAL_CONTRACT_SERIALIZATION_INVALID")
    document = json.loads(raw.decode("utf-8", errors="strict"),
                          object_pairs_hook=_pairs, parse_constant=_reject_constant)
    if type(document) is not dict or canonical_bytes(document) != raw:
        raise ValueError("RUN005_TEMPORAL_CONTRACT_NOT_CANONICAL")
    actual = hashlib.sha256(raw).hexdigest()
    if actual != CONTRACT_SHA256:
        raise ValueError("RUN005_TEMPORAL_CONTRACT_DIGEST_MISMATCH")
    return document


def validate_run005_temporal_binding(binding: object, *, runtime_profile: str,
                                     navigation_mode: str) -> None:
    if type(binding) is not dict or set(binding) != {"contract_id", "contract_sha256"}:
        raise ValueError("RUN005_TEMPORAL_CONTRACT_BINDING_SCHEMA_INVALID")
    if (binding.get("contract_id") != CONTRACT_ID
            or binding.get("contract_sha256") != CONTRACT_SHA256):
        raise ValueError("RUN005_TEMPORAL_CONTRACT_BINDING_MISMATCH")
    if runtime_profile != "sim_eval" or navigation_mode != "NAV2_BASELINE":
        raise ValueError("RUN005_TEMPORAL_CONTRACT_SCOPE_MISMATCH")
    load_run005_semantic_payload()
