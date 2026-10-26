"""Thông tin tính liên tục của các báo cáo TELEMETRY được chấp nhận."""
from dataclasses import dataclass


@dataclass(frozen=True)
class TelemetryHealth:
    active: bool
    fresh: bool
    fault_bits: int
    estop_active: bool


def telemetry_health(active: bool, fresh: bool, report) -> TelemetryHealth:
    if not active or not fresh or report is None:
        return TelemetryHealth(False, False, 0, False)
    return TelemetryHealth(report.packet.mcu_fault_bits == 0 and report.packet.estop_aux_active == 0,
                           True, report.packet.mcu_fault_bits,
                           report.packet.estop_aux_active == 1)
