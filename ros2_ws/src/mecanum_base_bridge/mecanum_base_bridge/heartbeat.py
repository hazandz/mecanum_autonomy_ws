"""Ánh xạ trạng thái UART đã xác thực sang Heartbeat hiện có."""
from dataclasses import dataclass

SOURCE_MCU = 2
ALLOWED_MCU_FAULTS = 1 | 2 | 256 | 512 | 1024 | 2048 | 4096


@dataclass(frozen=True)
class HeartbeatState:
    source: int
    sequence: int
    reset_epoch: int
    healthy: bool
    fault_bits: int
    detail: str


def make_heartbeat(sequence: int, reset_epoch: int, session_active: bool,
                   telemetry_fresh: bool, report, transport_healthy: bool) -> HeartbeatState:
    trusted = bool(telemetry_fresh and report is not None
                   and type(report.packet.mcu_fault_bits) is int
                   and report.packet.mcu_fault_bits & ~ALLOWED_MCU_FAULTS == 0
                   and report.packet.estop_aux_active in (0, 1))
    faults = report.packet.mcu_fault_bits if trusted else 0
    estop = bool(trusted and report.packet.estop_aux_active == 1)
    healthy = bool(session_active and trusted and transport_healthy and faults == 0 and not estop)
    detail = "MCU telemetry fresh" if trusted else "Pi observed UART/session loss"
    return HeartbeatState(SOURCE_MCU, sequence & 0xFFFFFFFF, reset_epoch,
                          healthy, faults, detail)
