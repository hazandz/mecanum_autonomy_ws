"""Pure command acceptance model for golden-vector semantic tests."""

from dataclasses import dataclass
import math
from typing import Optional

from .uart_v1_codec import CommandPacket


@dataclass(frozen=True)
class CommandDecision:
    accepted: bool
    watchdog_refresh_requested: bool
    config_status_response: None
    reason: str


class CommandSemantics:
    """Minimal configured-epoch sequence gate with no transport side effects."""

    def __init__(self, configured_reset_epoch: int,
                 last_accepted_command_sequence: Optional[int] = None):
        self.configured_reset_epoch = configured_reset_epoch
        self.last_accepted_command_sequence = last_accepted_command_sequence
        self.last_watchdog_refresh_requested = False
        self.last_config_status_response = None

    def handle_command(self, command: CommandPacket) -> CommandDecision:
        """Accept only finite matching-epoch commands with strict sequence."""
        self.last_watchdog_refresh_requested = False
        self.last_config_status_response = None
        if not all(math.isfinite(value) for value in
                   (command.vx_mps, command.vy_mps, command.wz_radps)):
            return CommandDecision(False, False, None, 'non_finite_command')
        if command.reset_epoch != self.configured_reset_epoch:
            return CommandDecision(False, False, None, 'wrong_reset_epoch')
        if (self.last_accepted_command_sequence is not None and
                command.command_sequence <= self.last_accepted_command_sequence):
            return CommandDecision(False, False, None, 'duplicate_or_backward_sequence')
        self.last_accepted_command_sequence = command.command_sequence
        self.last_watchdog_refresh_requested = True
        return CommandDecision(True, True, None, 'accepted')
