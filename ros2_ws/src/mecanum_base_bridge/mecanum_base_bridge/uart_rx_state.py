"""State and immutable diagnostic snapshot for the Phase B RX-only logic."""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class UartRxState(str, Enum):
    """Logical byte-ingestion states; this is not a serial-port lifecycle."""

    DISCONNECTED = 'DISCONNECTED'
    WAITING_FOR_VALID_TELEMETRY = 'WAITING_FOR_VALID_TELEMETRY'
    TRANSPORT_FAULT = 'TRANSPORT_FAULT'


@dataclass(frozen=True)
class UartRxDiagnosticSnapshot:
    """Read-only counters and metadata from successfully decoded TELEMETRY."""

    state: UartRxState = UartRxState.DISCONNECTED
    total_bytes: int = 0
    complete_frame_count: int = 0
    valid_telemetry_count: int = 0
    cobs_drop_count: int = 0
    crc_drop_count: int = 0
    protocol_version_drop_count: int = 0
    message_type_drop_count: int = 0
    payload_length_drop_count: int = 0
    oversize_drop_count: int = 0
    command_frame_drop_count: int = 0
    config_frame_drop_count: int = 0
    telemetry_sequence: Optional[int] = None
    mcu_boot_id: Optional[int] = None
    reset_epoch: Optional[int] = None
    mcu_monotonic_time_us: Optional[int] = None
