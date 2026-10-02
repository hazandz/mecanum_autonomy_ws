"""Core-only previous-issued-command feature extraction."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from numbers import Real

from mecanum_nav_rl.config.models import ActionConfig, ObservationConfig


_COMMAND_COMPONENT_NAMES = ("vx", "vy", "wz")


def _require_finite_real(field_name: str, value: object) -> float:
    """Return a finite real value while rejecting booleans and invalid values."""

    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"{field_name} must be a real number")
    numeric_value = float(value)
    if not isfinite(numeric_value):
        raise ValueError(f"{field_name} must be finite")
    return numeric_value


def _require_action_bounds(action_config: ActionConfig) -> tuple[float, float]:
    """Return finite ordered normalized-action bounds from ActionConfig."""

    if not isinstance(action_config, ActionConfig):
        raise TypeError("action_config must be an ActionConfig")
    normalized_low = _require_finite_real(
        "ActionConfig.normalized_low", action_config.normalized_low
    )
    normalized_high = _require_finite_real(
        "ActionConfig.normalized_high", action_config.normalized_high
    )
    if normalized_low >= normalized_high:
        raise ValueError("ActionConfig normalized_low must be less than normalized_high")
    return normalized_low, normalized_high


@dataclass(frozen=True, slots=True)
class PreviousNormalizedCommand:
    """Normalized command actually issued at the prior environment boundary.

    This represents the command accepted and issued at the prior environment
    step boundary.  It is not measured odometry, a ROS Twist, or an actuator
    acknowledgement.
    """

    vx: float
    vy: float
    wz: float

    def __post_init__(self) -> None:
        """Copy finite normalized command components into an immutable value."""

        for field_name in _COMMAND_COMPONENT_NAMES:
            object.__setattr__(
                self,
                field_name,
                _require_finite_real(field_name, getattr(self, field_name)),
            )

    @classmethod
    def episode_initial(cls, action_config: ActionConfig) -> "PreviousNormalizedCommand":
        """Create the explicit all-zero previous command for a new episode."""

        normalized_low, normalized_high = _require_action_bounds(action_config)
        if action_config.dimension != len(_COMMAND_COMPONENT_NAMES):
            raise ValueError("ActionConfig dimension must be exactly three")
        if not normalized_low <= 0.0 <= normalized_high:
            raise ValueError(
                "ActionConfig bounds must include zero for the episode initial command"
            )
        return cls(vx=0.0, vy=0.0, wz=0.0)


@dataclass(frozen=True, slots=True)
class PreviousCommandFeatureResult:
    """Immutable copied features in the fixed vx, vy, wz policy order."""

    features: tuple[float, float, float]

    def __post_init__(self) -> None:
        """Validate the immutable fixed-width feature tuple."""

        if len(self.features) != len(_COMMAND_COMPONENT_NAMES):
            raise ValueError("previous-command features have an invalid component count")
        copied_features = tuple(
            _require_finite_real(f"features[{index}]", value)
            for index, value in enumerate(self.features)
        )
        object.__setattr__(self, "features", copied_features)


class PreviousCommandFeatureExtractor:
    """Validate and copy the prior issued normalized command into features."""

    def __init__(
        self,
        observation_config: ObservationConfig,
        action_config: ActionConfig,
    ) -> None:
        """Bind the observation component count and action bounds."""

        if not isinstance(observation_config, ObservationConfig):
            raise TypeError("observation_config must be an ObservationConfig")
        normalized_low, normalized_high = _require_action_bounds(action_config)
        if (
            observation_config.previous_command_feature_count
            != len(_COMMAND_COMPONENT_NAMES)
        ):
            raise ValueError(
                "ObservationConfig previous_command_feature_count must be exactly three"
            )
        if action_config.dimension != len(_COMMAND_COMPONENT_NAMES):
            raise ValueError("ActionConfig dimension must be exactly three")
        if (
            observation_config.previous_command_feature_count
            != action_config.dimension
        ):
            raise ValueError(
                "ObservationConfig previous_command_feature_count must match "
                "ActionConfig dimension"
            )

        self._observation_config = observation_config
        self._normalized_low = normalized_low
        self._normalized_high = normalized_high

    def extract(
        self,
        previous_command: PreviousNormalizedCommand,
    ) -> PreviousCommandFeatureResult:
        """Return the validated command unchanged in vx, vy, wz order."""

        if not isinstance(previous_command, PreviousNormalizedCommand):
            raise TypeError("previous_command must be a PreviousNormalizedCommand")

        features = tuple(
            getattr(previous_command, field_name)
            for field_name in _COMMAND_COMPONENT_NAMES
        )
        for field_name, value in zip(_COMMAND_COMPONENT_NAMES, features, strict=True):
            if value < self._normalized_low or value > self._normalized_high:
                raise ValueError(
                    f"{field_name} must be within ActionConfig normalized bounds"
                )
        if len(features) != self._observation_config.previous_command_feature_count:
            raise RuntimeError(
                "generated feature count does not match ObservationConfig"
            )
        return PreviousCommandFeatureResult(features=features)
