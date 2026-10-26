from types import SimpleNamespace

import pytest

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


class _Clock:
    def __init__(self): self.value = 0.0
    def __call__(self): return self.value


class _Transport:
    def __init__(self): self.is_open = False; self.rx = bytearray(); self.writes = []
    def open(self): self.is_open = True; return True
    def close(self): self.is_open = False
    def read(self, max_bytes=256):
        value = bytes(self.rx[:max_bytes]); del self.rx[:max_bytes]; return value
    def write(self, frame): self.writes.append(bytes(frame)); return len(frame)
    def inject(self, frame): self.rx.extend(frame)


def _fault_report_from_real_session_path(bits):
    from mecanum_base_bridge.bridge_session import BridgeSession, LifecycleIdentity, SessionState
    from mecanum_base_bridge.protocol_constants import MESSAGE_CONFIG, MESSAGE_TELEMETRY
    from mecanum_base_bridge.uart_v1_codec import (
        ConfigStatusPacket, TelemetryPacket, build_wire_frame,
        serialize_config_status, serialize_telemetry,
    )
    clock, transport, digest = _Clock(), _Transport(), bytes(range(32))
    session = BridgeSession(transport, digest, clock)
    assert session.start()
    session.observe_lifecycle_snapshot(LifecycleIdentity(0, 0, False, 1, True))
    assert session.confirm_owner_reset(LifecycleIdentity(1, 0, False, 2, True))
    status = ConfigStatusPacket(1, 1, digest, 44, 1, 0)
    transport.inject(build_wire_frame(MESSAGE_CONFIG, serialize_config_status(status)))
    clock.value = 0.001
    session.io_once()
    assert session.state == SessionState.CONFIGURING
    packet = TelemetryPacket(1, 44, 1, 1000, 1, 1, 1, 1, 0, bits, 0)
    transport.inject(build_wire_frame(MESSAGE_TELEMETRY, serialize_telemetry(packet)))
    clock.value = 0.002
    session.io_once()
    assert session.state == SessionState.DISCONNECTED
    accepted = session.take_accepted_telemetry()
    assert accepted is not None and accepted.packet.mcu_fault_bits == bits
    return clock, session, accepted


class _HeartbeatPublisher:
    def __init__(self): self.messages = []
    def publish(self, message): self.messages.append(message)


def _heartbeat_adapter(clock, session, accepted, owner_epoch):
    from builtin_interfaces.msg import Time
    return SimpleNamespace(
        _steady_clock=clock,
        _session=session,
        _latest_report=accepted,
        _owner_message=SimpleNamespace(reset_epoch=owner_epoch),
        _heartbeat_sequence=17,
        _heartbeat_pub=_HeartbeatPublisher(),
        get_clock=lambda: SimpleNamespace(now=lambda: SimpleNamespace(
            to_msg=lambda: Time(sec=1, nanosec=0))),
    )


@pytest.mark.parametrize("fault", [1, 256])
def test_node_heartbeat_preserves_fresh_mcu_fault_after_session_invalidation(fault):
    from mecanum_base_bridge.bridge_node import UartBridgeNode
    clock, session, accepted = _fault_report_from_real_session_path(fault)
    adapter = _heartbeat_adapter(clock, session, accepted, owner_epoch=1)
    UartBridgeNode._heartbeat_tick(adapter)
    message = adapter._heartbeat_pub.messages[-1]
    assert not message.healthy
    assert message.fault_bits == fault
    assert message.reset_epoch == accepted.packet.reset_epoch == 1


def test_node_heartbeat_drops_stale_mcu_report_after_invalidation():
    from mecanum_base_bridge.bridge_node import UartBridgeNode
    clock, session, accepted = _fault_report_from_real_session_path(256)
    clock.value = accepted.pi_receive_time + 0.200
    adapter = _heartbeat_adapter(clock, session, accepted, owner_epoch=1)
    UartBridgeNode._heartbeat_tick(adapter)
    message = adapter._heartbeat_pub.messages[-1]
    assert not message.healthy and message.fault_bits == 0


def test_node_heartbeat_does_not_relabel_old_epoch_after_owner_change_and_reconnect():
    from mecanum_base_bridge.bridge_node import UartBridgeNode
    from mecanum_base_bridge.bridge_session import LifecycleIdentity
    clock, session, accepted = _fault_report_from_real_session_path(1)
    assert session.observe_lifecycle_snapshot(LifecycleIdentity(2, 0, False, 3, True))
    clock.value += session.RECONNECT_INTERVAL
    assert session.start()
    adapter = _heartbeat_adapter(clock, session, accepted, owner_epoch=2)
    UartBridgeNode._heartbeat_tick(adapter)
    message = adapter._heartbeat_pub.messages[-1]
    assert not message.healthy and message.fault_bits == 0
    assert message.reset_epoch == 2
