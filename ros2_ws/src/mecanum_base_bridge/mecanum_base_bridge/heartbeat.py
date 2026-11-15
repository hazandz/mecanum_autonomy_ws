"""Ánh xạ trạng thái UART đã xác thực sang Heartbeat hiện có."""
from dataclasses import dataclass

SOURCE_MCU = 2
ALLOWED_MCU_FAULTS = 1 | 2 | 256 | 512 | 1024 | 2048 | 4096
ESTOP_AUX_UNKNOWN = 0
ESTOP_AUX_INACTIVE = 1
ESTOP_AUX_ACTIVE = 2


@dataclass(frozen=True)
class HeartbeatState:
    source: int
    sequence: int
    reset_epoch: int
    healthy: bool
    fault_bits: int
    detail: str
    estop_aux_state: int


def make_heartbeat(sequence: int, reset_epoch: int, session_active: bool,
                   telemetry_fresh: bool, report, transport_healthy: bool,
                   estop_aux_monitored: bool = True) -> HeartbeatState:
    trusted = bool(telemetry_fresh and report is not None
                   and type(report.packet.mcu_fault_bits) is int
                   and report.packet.mcu_fault_bits & ~ALLOWED_MCU_FAULTS == 0
                   and type(report.packet.estop_aux_active) is int
                   and report.packet.estop_aux_active in (0, 1, 2))
    faults = report.packet.mcu_fault_bits if trusted else 0
    if not trusted:
        estop_state = ESTOP_AUX_UNKNOWN
    else:
        # UART v1 values: 0=INACTIVE, 1=ACTIVE, 2=UNKNOWN.
        estop_state = {
            0: ESTOP_AUX_INACTIVE,
            1: ESTOP_AUX_ACTIVE,
            2: ESTOP_AUX_UNKNOWN,
        }[report.packet.estop_aux_active]
    estop = estop_state == ESTOP_AUX_ACTIVE
    unknown = estop_state == ESTOP_AUX_UNKNOWN
    # MANUAL_SLAM bench has no auxiliary E-stop circuit installed. Keep the
    # reported UNKNOWN value truthful, but do not make that absent input alone
    # mark this explicitly selected mode unhealthy. ACTIVE always remains fatal.
    healthy = bool(session_active and trusted and transport_healthy and faults == 0
                   and not estop and (not estop_aux_monitored or not unknown))
    if not trusted:
        detail = ("Pi observed UART/session loss; E-stop auxiliary UNKNOWN"
                  if unknown else "Pi observed UART/session loss")
    else:
        detail = ("E-stop auxiliary UNKNOWN" if unknown and estop_aux_monitored
                  else "MCU telemetry fresh; E-stop auxiliary not monitored for MANUAL_SLAM bench"
                  if unknown else "MCU telemetry fresh")
    return HeartbeatState(SOURCE_MCU, sequence & 0xFFFFFFFF, reset_epoch,
                          healthy, faults, detail, estop_state)
