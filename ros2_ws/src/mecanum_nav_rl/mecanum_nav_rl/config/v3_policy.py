"""Pure architecture v3 profile/mode and unresolved-token policies.

This module validates values supplied by a caller. It does not resolve tokens,
read configuration, touch the environment, or perform runtime I/O.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from mecanum_nav_rl.config.v3_models import (
    ConfigTokenV3,
    NavigationModeV3,
    RuntimeProfileV3,
    TokenizedConfigInputV3,
    validate_profile_mode_v3,
)


class ResolutionStageV3(str, Enum):
    """Stage at which an unresolved tokenized input is considered."""

    CONFIG_INPUT = "CONFIG_INPUT"
    BUILD_OUTPUT = "BUILD_OUTPUT"
    DEPLOY_OUTPUT = "DEPLOY_OUTPUT"


@dataclass(frozen=True)
class TokenPolicyContextV3:
    """Explicit target context used to reject invalid unresolved tokens."""

    runtime_profile: RuntimeProfileV3
    final_evaluation: bool
    gate4: bool
    stage: ResolutionStageV3

    def __post_init__(self) -> None:
        if not isinstance(self.runtime_profile, RuntimeProfileV3):
            raise TypeError("runtime_profile must be RuntimeProfileV3")
        if type(self.final_evaluation) is not bool:
            raise TypeError("final_evaluation must be bool")
        if type(self.gate4) is not bool:
            raise TypeError("gate4 must be bool")
        if not isinstance(self.stage, ResolutionStageV3):
            raise TypeError("stage must be ResolutionStageV3")


def validate_tokenized_input_v3(
    tokenized_input: TokenizedConfigInputV3,
    context: TokenPolicyContextV3,
) -> None:
    """Apply token restrictions without resolving a token or picking defaults."""

    if not isinstance(tokenized_input, TokenizedConfigInputV3):
        raise TypeError("tokenized_input must be TokenizedConfigInputV3")
    if not isinstance(context, TokenPolicyContextV3):
        raise TypeError("context must be TokenPolicyContextV3")

    token = tokenized_input.token
    profile = context.runtime_profile
    if token is ConfigTokenV3.SIM_BASELINE and profile not in {
        RuntimeProfileV3.SIM_TRAIN,
        RuntimeProfileV3.SIM_EVAL,
    }:
        raise ValueError("SIM_BASELINE is valid only for sim_train or sim_eval")
    if token is ConfigTokenV3.TBD_MEASURED and (
        profile is RuntimeProfileV3.DEPLOY_REAL or context.gate4
    ):
        raise ValueError("TBD_MEASURED is forbidden for deploy_real or Gate 4")
    if token is ConfigTokenV3.TBD_PROJECT_ACCEPTANCE and context.final_evaluation:
        raise ValueError("TBD_PROJECT_ACCEPTANCE is forbidden for final evaluation")
    if token is ConfigTokenV3.REQUIRED_BUILD_INPUT and context.stage in {
        ResolutionStageV3.BUILD_OUTPUT,
        ResolutionStageV3.DEPLOY_OUTPUT,
    }:
        raise ValueError("REQUIRED_BUILD_INPUT must resolve before build/deploy")
