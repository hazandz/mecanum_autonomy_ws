"""Thông tin tính liên tục của các báo cáo TELEMETRY được chấp nhận."""
from dataclasses import dataclass

from .bridge_session import ALLOWED_MCU_FAULTS


@dataclass(frozen=True)
class TelemetryHealth:
    active: bool
    fresh: bool
    fault_bits: int
    estop_active: bool


def telemetry_health(active: bool, fresh: bool, report) -> TelemetryHealth:
    packet = None if report is None else report.packet
    trusted = bool(fresh and packet is not None
                   and type(packet.mcu_fault_bits) is int
                   and packet.mcu_fault_bits & ~ALLOWED_MCU_FAULTS == 0
                   and type(packet.estop_aux_active) is int
                   and packet.estop_aux_active in (0, 1))
    if not trusted:
        return TelemetryHealth(False, False, 0, False)
    faults = packet.mcu_fault_bits
    estop = packet.estop_aux_active == 1
    healthy = bool(active and faults == 0 and not estop)
    return TelemetryHealth(healthy, True, faults, estop)
