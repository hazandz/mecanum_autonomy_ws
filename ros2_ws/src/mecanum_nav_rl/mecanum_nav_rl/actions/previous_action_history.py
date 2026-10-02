"""Episode-scoped, core-only history of validated PPO normalized actions.

This history stores the most recent *valid PPO normalized action* for the
current episode.  It is not a published physical command, a motor command, or
the final command of a future runtime safety layer.  A non-ready decode result
never creates a new action in this history.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from mecanum_nav_rl.actions.ppo_decoder import (
    NormalizedPpoAction,
    PpoActionDecodeResult,
    PpoActionDecodeStatus,
)
from mecanum_nav_rl.config.models import ActionConfig
from mecanum_nav_rl.observations.previous_command import PreviousNormalizedCommand


class PreviousActionHistoryStatus(str, Enum):
    """Explicit state-transition outcome for one episode-history operation."""

    RESET = "reset"
    UPDATED = "updated"
    DECODE_NOT_READY = "decode_not_ready"
    STALE_GENERATION = "stale_generation"
    FUTURE_GENERATION = "future_generation"
    UNINITIALIZED = "uninitialized"


@dataclass(frozen=True, slots=True)
class PreviousActionHistoryState:
    """Immutable current normalized-action history for one explicit generation."""

    episode_generation: int
    previous_command: PreviousNormalizedCommand

    def __post_init__(self) -> None:
        """Reject ambiguous or invalid episode-generation identifiers."""

        if isinstance(self.episode_generation, bool) or not isinstance(self.episode_generation, int):
            raise TypeError("episode_generation must be an integer")
        if self.episode_generation < 0:
            raise ValueError("episode_generation must be non-negative")
        if not isinstance(self.previous_command, PreviousNormalizedCommand):
            raise TypeError("previous_command must be a PreviousNormalizedCommand")


@dataclass(frozen=True, slots=True)
class PreviousActionHistoryResult:
    """Immutable result that distinguishes state retention from a new action."""

    status: PreviousActionHistoryStatus
    state: PreviousActionHistoryState | None
    accepted_action: PreviousNormalizedCommand | None

    def __post_init__(self) -> None:
        """Prevent non-ready results from being mistaken for a new action."""

        if not isinstance(self.status, PreviousActionHistoryStatus):
            raise TypeError("status must be a PreviousActionHistoryStatus")
        if self.state is not None and not isinstance(self.state, PreviousActionHistoryState):
            raise TypeError("state must be a PreviousActionHistoryState or None")
        if self.accepted_action is not None and not isinstance(
            self.accepted_action, PreviousNormalizedCommand
        ):
            raise TypeError("accepted_action must be a PreviousNormalizedCommand or None")

        if self.status is PreviousActionHistoryStatus.UPDATED:
            if self.state is None or self.accepted_action is None:
                raise ValueError("an updated result requires state and accepted_action")
            if self.state.previous_command != self.accepted_action:
                raise ValueError("updated state must contain accepted_action")
        elif self.accepted_action is not None:
            raise ValueError("only an updated result may carry accepted_action")

    @property
    def updated(self) -> bool:
        """Return whether this operation accepted a new PPO action."""

        return self.status is PreviousActionHistoryStatus.UPDATED


class PreviousActionHistory:
    """Own one episode's previous PPO action after decoder validation only."""

    def __init__(self, action_config: ActionConfig) -> None:
        """Bind the explicit zero initial command without accepting raw PPO input."""

        if not isinstance(action_config, ActionConfig):
            raise TypeError("action_config must be an ActionConfig")
        self._initial_command = PreviousNormalizedCommand.episode_initial(action_config)
        self._state: PreviousActionHistoryState | None = None

    @property
    def state(self) -> PreviousActionHistoryState | None:
        """Return the immutable current state, or None before an explicit reset."""

        return self._state

    def reset(self, episode_generation: int) -> PreviousActionHistoryResult:
        """Start a strictly newer episode with explicit zero previous action."""

        generation = self._require_generation(episode_generation)
        if self._state is not None and generation <= self._state.episode_generation:
            return PreviousActionHistoryResult(
                PreviousActionHistoryStatus.STALE_GENERATION,
                self._state,
                None,
            )

        self._state = PreviousActionHistoryState(generation, self._initial_command)
        return PreviousActionHistoryResult(PreviousActionHistoryStatus.RESET, self._state, None)

    def update(
        self,
        episode_generation: int,
        decode_result: PpoActionDecodeResult,
    ) -> PreviousActionHistoryResult:
        """Copy only a READY decoder action into the matching active generation."""

        generation = self._require_generation(episode_generation)
        if not isinstance(decode_result, PpoActionDecodeResult):
            raise TypeError("decode_result must be a PpoActionDecodeResult")
        if self._state is None:
            return PreviousActionHistoryResult(
                PreviousActionHistoryStatus.UNINITIALIZED,
                None,
                None,
            )
        if generation < self._state.episode_generation:
            return PreviousActionHistoryResult(
                PreviousActionHistoryStatus.STALE_GENERATION,
                self._state,
                None,
            )
        if generation > self._state.episode_generation:
            return PreviousActionHistoryResult(
                PreviousActionHistoryStatus.FUTURE_GENERATION,
                self._state,
                None,
            )
        if decode_result.status is not PpoActionDecodeStatus.READY:
            return PreviousActionHistoryResult(
                PreviousActionHistoryStatus.DECODE_NOT_READY,
                self._state,
                None,
            )

        normalized_action = decode_result.normalized_action
        if not isinstance(normalized_action, NormalizedPpoAction):
            raise RuntimeError("a ready decode result must contain NormalizedPpoAction")
        previous_command = PreviousNormalizedCommand(
            vx=normalized_action.vx,
            vy=normalized_action.vy,
            wz=normalized_action.wz,
        )
        self._state = PreviousActionHistoryState(generation, previous_command)
        return PreviousActionHistoryResult(
            PreviousActionHistoryStatus.UPDATED,
            self._state,
            previous_command,
        )

    @staticmethod
    def _require_generation(value: object) -> int:
        """Validate a caller-provided reset token without numeric coercion."""

        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError("episode_generation must be an integer")
        if value < 0:
            raise ValueError("episode_generation must be non-negative")
        return value
