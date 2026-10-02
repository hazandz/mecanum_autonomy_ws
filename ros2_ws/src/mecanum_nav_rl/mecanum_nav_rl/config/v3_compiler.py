"""Five-layer, fail-closed compiler for architecture-target v3 config."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass

from mecanum_nav_rl.config.v3_hashing import config_v3_sha256
from mecanum_nav_rl.config.v3_loader import load_v3_mapping
from mecanum_nav_rl.config.v3_models import (
    ConfigTokenV3,
    ResolvedConfigV3,
    RuntimeProfileV3,
    TokenizedConfigInputV3,
)
from mecanum_nav_rl.config.v3_policy import (
    ResolutionStageV3,
    TokenPolicyContextV3,
    validate_profile_mode_v3,
    validate_tokenized_input_v3,
)
from mecanum_nav_rl.config.v3_validators import validate_resolved_config_v3


@dataclass(frozen=True)
class ApprovalProvenanceV3:
    """Explicit approval identity required for a privileged input layer."""

    approval_id: str
    approval_sha256: str

    def __post_init__(self) -> None:
        if not isinstance(self.approval_id, str) or not self.approval_id.strip():
            raise ValueError("approval_id must be a non-empty string")
        if (
            not isinstance(self.approval_sha256, str)
            or len(self.approval_sha256) != 64
            or any(character not in "0123456789abcdef" for character in self.approval_sha256)
        ):
            raise ValueError("approval_sha256 must be lowercase SHA-256")


@dataclass(frozen=True)
class ApprovedExperimentOverrideV3:
    """Experiment override plus the approval provenance required to use it."""

    values: Mapping[str, object]
    approval: ApprovalProvenanceV3

    def __post_init__(self) -> None:
        load_v3_mapping(self.values)
        if not isinstance(self.approval, ApprovalProvenanceV3):
            raise TypeError("experiment override requires ApprovalProvenanceV3")


@dataclass(frozen=True)
class ApprovedMeasuredRegistryV3:
    """Measured-registry layer and the registry plus approval provenance."""

    values: Mapping[str, object]
    registry_id: str
    registry_sha256: str
    approval: ApprovalProvenanceV3

    def __post_init__(self) -> None:
        load_v3_mapping(self.values)
        if not isinstance(self.registry_id, str) or not self.registry_id.strip():
            raise ValueError("registry_id must be a non-empty string")
        if (
            not isinstance(self.registry_sha256, str)
            or len(self.registry_sha256) != 64
            or any(character not in "0123456789abcdef" for character in self.registry_sha256)
        ):
            raise ValueError("registry_sha256 must be lowercase SHA-256")
        if not isinstance(self.approval, ApprovalProvenanceV3):
            raise TypeError("measured registry requires ApprovalProvenanceV3")


def deep_merge_v3(
    lower_priority: Mapping[str, object], higher_priority: Mapping[str, object]
) -> dict[str, object]:
    """Recursively merge mappings without mutating either source layer."""

    lower = load_v3_mapping(lower_priority)
    higher = load_v3_mapping(higher_priority)
    merged: dict[str, object] = deepcopy(lower)
    for key, override in higher.items():
        if key not in merged:
            merged[key] = deepcopy(override)
            continue
        existing = merged[key]
        existing_mapping = isinstance(existing, Mapping)
        override_mapping = isinstance(override, Mapping)
        if existing_mapping != override_mapping:
            raise ValueError(
                f"v3 layer type conflict at {key}: mapping/non-mapping replacement"
            )
        if existing_mapping:
            assert isinstance(existing, Mapping)
            assert isinstance(override, Mapping)
            merged[key] = deep_merge_v3(existing, override)
        else:
            merged[key] = deepcopy(override)
    return merged


def _require_layer(name: str, layer: Mapping[str, object]) -> dict[str, object]:
    try:
        return load_v3_mapping(layer)
    except (TypeError, ValueError) as error:
        raise ValueError(f"invalid {name} layer: {error}") from error


def _require_runtime_context(
    merged: Mapping[str, object],
    *,
    output_stage: ResolutionStageV3,
    gate4: bool,
) -> TokenPolicyContextV3:
    runtime = merged.get("runtime")
    evaluation = merged.get("evaluation")
    if not isinstance(runtime, Mapping) or not isinstance(evaluation, Mapping):
        raise ValueError("merged v3 config requires runtime and evaluation mappings")
    try:
        profile = RuntimeProfileV3(runtime["runtime_profile"])
        mode = runtime["navigation_mode"]
        use_sim_time = runtime["use_sim_time"]
        final_evaluation = evaluation["final_evaluation"]
    except KeyError as error:
        raise ValueError(f"merged v3 config is missing {error.args[0]}") from error
    if type(use_sim_time) is not bool or type(final_evaluation) is not bool:
        raise ValueError("runtime/use_sim_time and evaluation/final_evaluation must be bool")
    from mecanum_nav_rl.config.v3_models import NavigationModeV3

    try:
        navigation_mode = NavigationModeV3(mode)
    except ValueError as error:
        raise ValueError("navigation_mode is invalid") from error
    validate_profile_mode_v3(profile, navigation_mode)
    expected_sim_time = profile is not RuntimeProfileV3.DEPLOY_REAL
    if use_sim_time != expected_sim_time:
        raise ValueError("runtime profile has invalid use_sim_time")
    return TokenPolicyContextV3(profile, final_evaluation, gate4, output_stage)


def _validate_motion_limit_source_class(
    merged: Mapping[str, object],
    *,
    runtime_profile: RuntimeProfileV3,
    measured_registry: ApprovedMeasuredRegistryV3 | None,
) -> None:
    """Bind final motion source class to the profile and its registry receipt."""

    motion = merged.get("motion_limits")
    if not isinstance(motion, Mapping):
        raise ValueError("merged v3 config requires motion_limits mapping")
    source_class = motion.get("source_class")
    if source_class == "SIM_BASELINE":
        if runtime_profile not in {
            RuntimeProfileV3.SIM_TRAIN,
            RuntimeProfileV3.SIM_EVAL,
        }:
            raise ValueError(
                "SIM_BASELINE motion limits are valid only for sim_train or sim_eval"
            )
        return
    if source_class != "MEASURED_REGISTRY":
        raise ValueError("motion_limits.source_class is not an approved V3 source")
    if measured_registry is None:
        raise ValueError(
            "MEASURED_REGISTRY motion limits require an approved measured registry layer"
        )
    registry_motion = measured_registry.values.get("motion_limits")
    if not isinstance(registry_motion, Mapping):
        raise ValueError(
            "approved measured registry must provide motion_limits provenance"
        )
    if registry_motion.get("source_class") != "MEASURED_REGISTRY":
        raise ValueError(
            "approved measured registry must declare MEASURED_REGISTRY motion limits"
        )
    if registry_motion.get("source_id") != measured_registry.registry_id:
        raise ValueError("measured registry motion source_id must match registry_id")
    if motion.get("source_id") != measured_registry.registry_id:
        raise ValueError("final measured motion source_id must match registry_id")


def _walk_tokens(value: object) -> tuple[TokenizedConfigInputV3, ...]:
    found: list[TokenizedConfigInputV3] = []
    if isinstance(value, Mapping):
        keys = {key for key in value if isinstance(key, str)}
        if {"field_path", "token", "reference_id"}.issubset(keys):
            found.append(TokenizedConfigInputV3.model_validate(value))
        for nested in value.values():
            found.extend(_walk_tokens(nested))
    elif isinstance(value, list):
        for nested in value:
            found.extend(_walk_tokens(nested))
    return tuple(found)


def _assert_no_caller_config_hash(merged: Mapping[str, object]) -> None:
    provenance = merged.get("provenance")
    if not isinstance(provenance, Mapping):
        raise ValueError("merged v3 config requires provenance mapping")
    if "config_hash" in provenance:
        raise ValueError("caller must not supply provenance.config_hash")


def compile_v3_config(
    *,
    base_layer: Mapping[str, object],
    runtime_profile_layer: Mapping[str, object],
    navigation_mode_layer: Mapping[str, object],
    experiment_override_layer: ApprovedExperimentOverrideV3 | None,
    measured_hardware_registry_layer: ApprovedMeasuredRegistryV3 | None,
    output_stage: ResolutionStageV3,
    gate4: bool,
) -> ResolvedConfigV3:
    """Compile the architecture's five layers into immutable V3 config.

    The three ordinary layers are mandatory. Privileged override/registry
    layers are optional only when absent; if supplied they must use their
    explicit approved wrapper type. No input may provide the final hash.
    """

    if not isinstance(output_stage, ResolutionStageV3):
        raise TypeError("output_stage must be ResolutionStageV3")
    if type(gate4) is not bool:
        raise TypeError("gate4 must be bool")
    merged = deep_merge_v3(
        _require_layer("base", base_layer),
        _require_layer("runtime-profile", runtime_profile_layer),
    )
    merged = deep_merge_v3(merged, _require_layer("navigation-mode", navigation_mode_layer))
    if experiment_override_layer is not None:
        if not isinstance(experiment_override_layer, ApprovedExperimentOverrideV3):
            raise TypeError("experiment override requires approved provenance wrapper")
        merged = deep_merge_v3(merged, experiment_override_layer.values)
    if measured_hardware_registry_layer is not None:
        if not isinstance(measured_hardware_registry_layer, ApprovedMeasuredRegistryV3):
            raise TypeError("measured registry requires approved provenance wrapper")
        merged = deep_merge_v3(merged, measured_hardware_registry_layer.values)
    _assert_no_caller_config_hash(merged)
    context = _require_runtime_context(
        merged, output_stage=output_stage, gate4=gate4
    )
    tokens = _walk_tokens(merged)
    for tokenized in tokens:
        validate_tokenized_input_v3(tokenized, context)
    if tokens:
        raise ValueError("unresolved tokenized input cannot enter ResolvedConfigV3")
    _validate_motion_limit_source_class(
        merged,
        runtime_profile=context.runtime_profile,
        measured_registry=measured_hardware_registry_layer,
    )
    config_hash = config_v3_sha256(merged)
    final_payload = deepcopy(merged)
    provenance = final_payload["provenance"]
    assert isinstance(provenance, dict)
    provenance["config_hash"] = config_hash
    config = ResolvedConfigV3.model_validate(final_payload)
    validate_resolved_config_v3(config)
    return config
