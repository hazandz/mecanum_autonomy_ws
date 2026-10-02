"""Pure structural composition for caller-supplied canonical V3 fragments."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType

from mecanum_nav_rl.config.v3_loader import load_v3_mapping
from mecanum_nav_rl.config.v3_models import ResolvedConfigV3


class CanonicalFragmentKindV3(str, Enum):
    """The seven approved structural fragment positions."""

    BASE = "BASE"
    FRAMES = "FRAMES"
    TOPICS_QOS = "TOPICS_QOS"
    STATE_LOCALIZATION = "STATE_LOCALIZATION"
    SYSTEM_CONTRACTS = "SYSTEM_CONTRACTS"
    RUNTIME_PROFILE = "RUNTIME_PROFILE"
    NAVIGATION_MODE = "NAVIGATION_MODE"


@dataclass(frozen=True)
class CanonicalFragmentV3:
    """One explicit in-memory structural fragment supplied by the caller."""

    kind: CanonicalFragmentKindV3
    values: Mapping[str, object]

    def __post_init__(self) -> None:
        if not isinstance(self.kind, CanonicalFragmentKindV3):
            raise TypeError("fragment kind must be CanonicalFragmentKindV3")
        if not isinstance(self.values, Mapping):
            raise TypeError("fragment values must be a mapping")


_MODEL_OWNED_TOP_LEVEL_FIELDS = frozenset(ResolvedConfigV3.model_fields)


def _owned_fields(*field_names: str) -> frozenset[str]:
    unknown = set(field_names) - _MODEL_OWNED_TOP_LEVEL_FIELDS
    if unknown:
        raise RuntimeError("fragment ownership names must be model-owned")
    return frozenset(field_names)


_FRAGMENT_OWNERSHIP_V3: Mapping[CanonicalFragmentKindV3, frozenset[str]] = (
    MappingProxyType(
        {
            CanonicalFragmentKindV3.BASE: _owned_fields(
                "schema_version",
                "project",
                "provenance",
                "observation",
                "action",
                "map_identity",
            ),
            CanonicalFragmentKindV3.FRAMES: _owned_fields("frames_tf"),
            CanonicalFragmentKindV3.TOPICS_QOS: _owned_fields("topics_qos"),
            CanonicalFragmentKindV3.STATE_LOCALIZATION: _owned_fields(
                "state_estimation", "localization"
            ),
            CanonicalFragmentKindV3.SYSTEM_CONTRACTS: _owned_fields(
                "command_safety",
                "reward",
                "training",
                "evaluation",
                "acceptance",
            ),
            CanonicalFragmentKindV3.RUNTIME_PROFILE: _owned_fields(
                "runtime", "motion_limits"
            ),
            CanonicalFragmentKindV3.NAVIGATION_MODE: _owned_fields(
                "runtime", "navigation"
            ),
        }
    )
)


def _canonical_path(parent: str, key: str) -> str:
    return key if not parent else f"{parent}.{key}"


def _merge_disjoint_v3(
    lower_priority: Mapping[str, object],
    higher_priority: Mapping[str, object],
    *,
    parent_path: str = "",
) -> dict[str, object]:
    merged = deepcopy(dict(lower_priority))
    for key, incoming in higher_priority.items():
        path = _canonical_path(parent_path, key)
        if key not in merged:
            merged[key] = deepcopy(incoming)
            continue
        existing = merged[key]
        existing_mapping = isinstance(existing, Mapping)
        incoming_mapping = isinstance(incoming, Mapping)
        if existing_mapping and incoming_mapping:
            merged[key] = _merge_disjoint_v3(
                existing, incoming, parent_path=path
            )
            continue
        if existing_mapping != incoming_mapping:
            raise ValueError(f"mapping/scalar collision at canonical field {path}")
        raise ValueError(f"duplicate canonical leaf field {path}")
    return merged


def _validated_fragment(
    fragment: CanonicalFragmentV3,
    expected_kind: CanonicalFragmentKindV3,
) -> dict[str, object]:
    if not isinstance(fragment, CanonicalFragmentV3):
        raise TypeError("canonical fragment must be CanonicalFragmentV3")
    if fragment.kind is not expected_kind:
        raise ValueError(
            f"expected fragment kind {expected_kind.value}, got {fragment.kind.value}"
        )
    values = load_v3_mapping(fragment.values)
    if not values:
        raise ValueError(f"canonical fragment {expected_kind.value} must not be empty")
    owned = _FRAGMENT_OWNERSHIP_V3[expected_kind]
    for field_name in values:
        if field_name not in _MODEL_OWNED_TOP_LEVEL_FIELDS:
            raise ValueError(f"unknown canonical top-level field {field_name}")
        if field_name not in owned:
            raise ValueError(
                f"canonical top-level field {field_name} is not owned by "
                f"fragment {expected_kind.value}"
            )
    return values


def compose_canonical_v3_fragments(
    base: CanonicalFragmentV3,
    frames: CanonicalFragmentV3,
    topics_qos: CanonicalFragmentV3,
    state_localization: CanonicalFragmentV3,
    system_contracts: CanonicalFragmentV3,
    runtime_profile: CanonicalFragmentV3,
    navigation_mode: CanonicalFragmentV3,
) -> dict[str, object]:
    """Compose the seven explicit fragments without resolution or model construction."""

    ordered = (
        (base, CanonicalFragmentKindV3.BASE),
        (frames, CanonicalFragmentKindV3.FRAMES),
        (topics_qos, CanonicalFragmentKindV3.TOPICS_QOS),
        (state_localization, CanonicalFragmentKindV3.STATE_LOCALIZATION),
        (system_contracts, CanonicalFragmentKindV3.SYSTEM_CONTRACTS),
        (runtime_profile, CanonicalFragmentKindV3.RUNTIME_PROFILE),
        (navigation_mode, CanonicalFragmentKindV3.NAVIGATION_MODE),
    )
    composed: dict[str, object] = {}
    for fragment, expected_kind in ordered:
        composed = _merge_disjoint_v3(
            composed, _validated_fragment(fragment, expected_kind)
        )
    return deepcopy(composed)
