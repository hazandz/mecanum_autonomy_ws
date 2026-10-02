"""Legacy V1 configuration plus lazily exposed architecture-target V3 APIs.

Importing this package must not make V1 core code depend on the optional V3
validation implementation.  V3 names resolve explicitly on demand; no
ambiguous legacy ``ResolvedConfig`` alias is introduced.
"""

from __future__ import annotations

from importlib import import_module


_V3_EXPORT_MODULES = {
    "CanonicalFragmentKindV3": "v3_composition",
    "CanonicalFragmentV3": "v3_composition",
    "compose_canonical_v3_fragments": "v3_composition",
    "CanonicalV3AssetEnvelope": "v3_asset_envelope",
    "ExplicitV3AssetSelection": "v3_selection",
    "AcceptanceContractV3": "v3_models",
    "ActionContractV3": "v3_models",
    "ApprovalProvenanceV3": "v3_compiler",
    "ApprovedExperimentOverrideV3": "v3_compiler",
    "ApprovedMeasuredRegistryV3": "v3_compiler",
    "ConfigProvenanceV3": "v3_models",
    "ConfigTokenV3": "v3_models",
    "EvaluationContractV3": "v3_models",
    "FrameTfContractV3": "v3_models",
    "MapIdentityV3": "v3_models",
    "MotionLimitTargetPolicyV3": "v3_models",
    "NavigationContractV3": "v3_models",
    "NavigationModeV3": "v3_models",
    "ObservationContractV3": "v3_models",
    "ProjectIdentityV3": "v3_models",
    "ResolutionStageV3": "v3_policy",
    "ResolvedConfigV3": "v3_models",
    "RuntimeProfileV3": "v3_models",
    "RuntimeSelectionV3": "v3_models",
    "TokenizedConfigInputV3": "v3_models",
    "TokenPolicyContextV3": "v3_policy",
    "TopicQosContractV3": "v3_models",
    "V3_CONFIG_HASH_ALGORITHM": "v3_hashing",
    "V3_CONFIG_HASH_SCHEMA": "v3_hashing",
    "canonical_v3_config_json": "v3_hashing",
    "canonical_v3_hash_payload": "v3_hashing",
    "compile_v3_config": "v3_compiler",
    "config_v3_sha256": "v3_hashing",
    "deep_merge_v3": "v3_compiler",
    "hash_payload_from_resolved_v3": "v3_hashing",
    "load_v3_mapping": "v3_loader",
    "load_v3_yaml_mapping": "v3_loader",
    "validate_profile_mode_v3": "v3_policy",
    "validate_resolved_config_v3": "v3_validators",
    "validate_tokenized_input_v3": "v3_policy",
}

__all__ = tuple(sorted(_V3_EXPORT_MODULES))


def __getattr__(name: str) -> object:
    """Load a V3 API only when a caller explicitly requests it."""

    module_name = _V3_EXPORT_MODULES.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = import_module(f"{__name__}.{module_name}")
    value = getattr(module, name)
    globals()[name] = value
    return value
