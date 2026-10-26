from types import SimpleNamespace

from mecanum_base_bridge.heartbeat import ALLOWED_MCU_FAULTS, SOURCE_MCU, make_heartbeat
from mecanum_base_bridge.telemetry_state import telemetry_health


def report(bits=0, estop=0):
    return SimpleNamespace(packet=SimpleNamespace(mcu_fault_bits=bits, estop_aux_active=estop))


def test_valid_fault_bits_are_preserved_as_mcu_measurements():
    for bit in (1, 2, 256, 512, 1024, 2048, 4096, ALLOWED_MCU_FAULTS):
        state = make_heartbeat(3, 0, True, True, report(bit, int(bit == 2)), True)
        assert state.source == SOURCE_MCU and state.fault_bits == bit
        assert not state.healthy


def test_pi_loss_and_stale_report_do_not_fabricate_mcu_faults():
    for active, fresh, transport in ((False, False, False), (True, False, True), (True, True, False)):
        state = make_heartbeat(2, 9, active, fresh, report(1), transport)
        assert not state.healthy
    lost = make_heartbeat(2, 9, False, False, report(4096), False)
    assert lost.fault_bits == 0 and "Pi observed" in lost.detail


def test_reserved_fault_and_invalid_estop_are_rejected():
    invalid = make_heartbeat(1, 0, True, True, report(8192), True)
    estop = make_heartbeat(1, 0, True, True, report(0, 2), True)
    assert not invalid.healthy and invalid.fault_bits == 0
    assert not estop.healthy and estop.fault_bits == 0
    assert not telemetry_health(True, True, report(256)).active
    assert not telemetry_health(True, False, report(0)).fresh
