"""Core-only, fail-closed decoding from a PPO action into VelocityCommand.

``PreviousNormalizedCommand`` is the PPO action received validly at the prior
environment step. It is observation history only: it is not the future runtime
safety layer's final issued physical command or actuator acknowledgement.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import Enum
from math import isfinite
from numbers import Real

from mecanum_nav_rl.config.models import ActionConfig, MotionLimitsConfig, ResolvedConfig
from mecanum_nav_rl.core.types import VelocityCommand


_COMPONENT_NAMES = ("vx", "vy", "wz")
_NORMALIZED_LOW = -1.0
_NORMALIZED_HIGH = 1.0


def _require_finite_real(field_name: str, value: object) -> float:
    """Return one finite real value and reject booleans or non-numeric input."""

    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"{field_name} must be a real number")
    numeric_value = float(value)
    if not isfinite(numeric_value):
        raise ValueError(f"{field_name} must be finite")
    return numeric_value


@dataclass(frozen=True, slots=True)
class NormalizedPpoAction:
    """One validated normalized PPO action in fixed ``vx, vy, wz`` order."""

    vx: float
    vy: float
    wz: float

    def __post_init__(self) -> None:
        """Copy only finite values inside the closed normalized action domain."""

        for field_name in _COMPONENT_NAMES:
            value = _require_finite_real(field_name, getattr(self, field_name))
            if value < _NORMALIZED_LOW or value > _NORMALIZED_HIGH:
                raise ValueError(f"{field_name} must be in the closed interval [-1, 1]")
            object.__setattr__(self, field_name, value)


class PpoActionDecodeStatus(str, Enum):
    """Explicit result of parsing and scaling one PPO action candidate."""

    READY = "ready"
    INVALID_INPUT = "invalid_input"
    INVALID_DIMENSION = "invalid_dimension"
    OUT_OF_BOUNDS = "out_of_bounds"
    INVALID_CONFIGURATION = "invalid_configuration"


@dataclass(frozen=True, slots=True)
class PpoActionDecodeResult:
    """A physical command only when decoding completed without substitution."""

    status: PpoActionDecodeStatus
    normalized_action: NormalizedPpoAction | None
    command: VelocityCommand | None

    def __post_init__(self) -> None:
        """Prevent results that silently carry a fallback command."""

        if not isinstance(self.status, PpoActionDecodeStatus):
            raise TypeError("status must be a PpoActionDecodeStatus")
        if self.status is PpoActionDecodeStatus.READY:
            if not isinstance(self.normalized_action, NormalizedPpoAction):
                raise ValueError("a ready result requires a normalized action")
            if not isinstance(self.command, VelocityCommand):
                raise ValueError("a ready result requires a physical VelocityCommand")
        elif self.normalized_action is not None or self.command is not None:
            raise ValueError("a non-ready result must not carry action or command data")

    @property
    def ready(self) -> bool:
        """Return whether the result carries a physical command to a later layer."""

        return self.status is PpoActionDecodeStatus.READY


class PpoActionDecoder:
    """Decode exactly three normalized PPO components using MotionLimitsConfig."""

    def __init__(self, config: ResolvedConfig) -> None:
        """Retain only validated scaling data or fail closed at every decode call."""

        if not isinstance(config, ResolvedConfig):
            raise TypeError("config must be a ResolvedConfig")
        self._configuration_error = self._validate_configuration(config)
        self._motion_limits = config.motion_limits if self._configuration_error is None else None

    def decode(self, raw_action: object) -> PpoActionDecodeResult:
        """Parse, validate, and scale raw PPO values without clamp or fallback."""

        if self._configuration_error is not None:
            return PpoActionDecodeResult(
                PpoActionDecodeStatus.INVALID_CONFIGURATION, None, None
            )

        parsed = self._parse_raw_action(raw_action)
        if isinstance(parsed, PpoActionDecodeStatus):
            return PpoActionDecodeResult(parsed, None, None)

        try:
            normalized_action = NormalizedPpoAction(*parsed)
        except ValueError:
            return PpoActionDecodeResult(PpoActionDecodeStatus.OUT_OF_BOUNDS, None, None)
        except TypeError:
            return PpoActionDecodeResult(PpoActionDecodeStatus.INVALID_INPUT, None, None)

        assert self._motion_limits is not None
        command = VelocityCommand(
            vx=normalized_action.vx * self._motion_limits.max_vx_mps,
            vy=normalized_action.vy * self._motion_limits.max_vy_mps,
            wz=normalized_action.wz * self._motion_limits.max_wz_radps,
        )
        return PpoActionDecodeResult(PpoActionDecodeStatus.READY, normalized_action, command)

    @staticmethod
    def _parse_raw_action(
        raw_action: object,
    ) -> tuple[float, float, float] | PpoActionDecodeStatus:
        """Accept exactly three finite reals while consuming at most four items."""

        if isinstance(raw_action, (str, bytes, bytearray, Mapping)) or not isinstance(
            raw_action, Iterable
        ):
            return PpoActionDecodeStatus.INVALID_INPUT
        try:
            iterator = iter(raw_action)
        except TypeError:
            return PpoActionDecodeStatus.INVALID_INPUT

        values: list[object] = []
        try:
            for _ in _COMPONENT_NAMES:
                values.append(next(iterator))
        except StopIteration:
            return PpoActionDecodeStatus.INVALID_DIMENSION
        except Exception:
            return PpoActionDecodeStatus.INVALID_INPUT

        try:
            next(iterator)
        except StopIteration:
            pass
        except Exception:
            return PpoActionDecodeStatus.INVALID_INPUT
        else:
            return PpoActionDecodeStatus.INVALID_DIMENSION

        try:
            vx, vy, wz = (
                _require_finite_real(field_name, value)
                for field_name, value in zip(_COMPONENT_NAMES, values, strict=True)
            )
        except (TypeError, ValueError):
            return PpoActionDecodeStatus.INVALID_INPUT
        return vx, vy, wz

    @staticmethod
    def _validate_configuration(config: ResolvedConfig) -> str | None:
        """Return an error marker for bypassed model validation; do not scale then."""

        action = config.action
        limits = config.motion_limits
        if not isinstance(action, ActionConfig) or not isinstance(limits, MotionLimitsConfig):
            return "action or motion limits type is invalid"
        if action.dimension != len(_COMPONENT_NAMES):
            return "action dimension must be exactly three"
        try:
            normalized_low = _require_finite_real("normalized_low", action.normalized_low)
            normalized_high = _require_finite_real("normalized_high", action.normalized_high)
            limit_values = (
                _require_finite_real("max_vx_mps", limits.max_vx_mps),
                _require_finite_real("max_vy_mps", limits.max_vy_mps),
                _require_finite_real("max_wz_radps", limits.max_wz_radps),
            )
        except (TypeError, ValueError):
            return "configuration values must be finite real numbers"
        if normalized_low != _NORMALIZED_LOW or normalized_high != _NORMALIZED_HIGH:
            return "normalized bounds must be exactly [-1, 1]"
        if any(value <= 0.0 for value in limit_values):
            return "motion limits must be positive"
        return None
