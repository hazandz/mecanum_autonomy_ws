from collections import deque

import pytest

from mecanum_base_bridge.bridge_session import (
    BridgeSession, LifecycleIdentity, SessionState,
)
from mecanum_base_bridge.protocol_constants import MESSAGE_CONFIG, MESSAGE_TELEMETRY
from mecanum_base_bridge.uart_v1_codec import (
    CommandPacket, ConfigStatusPacket, TelemetryPacket, build_wire_frame,
    decode_frame, parse_command, parse_config_status, serialize_config_status,
    serialize_telemetry,
)
from mecanum_base_bridge.command_semantics import CommandSemantics


class Clock:
    def __init__(self): self.value = 0.0
    def __call__(self): return self.value


class FakeTransport:
    def __init__(self):
        self.is_open = False
        self.open_calls = 0
        self.close_calls = 0
        self.writes = []
        self.rx = deque()
        self.fail_read = False
        self.fail_write = False
        self.open_result = True
    def open(self):
        self.open_calls += 1
        if not self.open_result: return False
        self.is_open = True
        return True
    def close(self): self.close_calls += 1; self.is_open = False
    def read(self, max_bytes=256):
        if self.fail_read: raise OSError('fake disconnect')
        out = bytearray()
        while self.rx and len(out) < max_bytes: out.append(self.rx.popleft())
        return bytes(out)
    def write(self, data):
        if self.fail_write: raise OSError('fake short write/timeout')
        if not self.is_open: raise OSError('closed')
        self.writes.append(bytes(data))
        return len(data)
    def inject(self, data): self.rx.extend(data)


HASH = bytes(range(32))
INITIAL = LifecycleIdentity(0, 0, False)
RESET = LifecycleIdentity(0, 1, True)  # epoch 0 vẫn là identity Owner hợp lệ


def new_session():
    clock, transport = Clock(), FakeTransport()
    session = BridgeSession(transport, HASH, clock)
    assert session.start()
    assert session.take_owner_reset_request()
    session.observe_lifecycle_snapshot(INITIAL)
    assert session.confirm_owner_reset(RESET)
    assert session.state == SessionState.CONFIGURING
    assert len(transport.writes) == 1
    config = decode_frame(transport.writes[0])
    assert config.message_type == MESSAGE_CONFIG
    return clock, transport, session


def status_for(sequence=1, epoch=0, boot=9, state=1, reason=0):
    return build_wire_frame(MESSAGE_CONFIG, serialize_config_status(
        ConfigStatusPacket(sequence, epoch, HASH, boot, state, reason)))


def telemetry(sequence, boot=9, epoch=0, tick=100, ack=0, faults=0):
    return build_wire_frame(MESSAGE_TELEMETRY, serialize_telemetry(
        TelemetryPacket(sequence, boot, epoch, tick, 0, 0, 0, 0, ack, faults, 0)))


def activate(clock, transport, session):
    transport.inject(telemetry(1))  # A1: bỏ qua telemetry trước CONFIG_STATUS được chấp nhận
    clock.value = 0.001
    session.io_once()
    assert session.state == SessionState.CONFIGURING
    transport.inject(status_for())
    clock.value = 0.002
    session.io_once()
    assert session.state == SessionState.CONFIGURING  # chỉ status chưa đủ kích hoạt
    transport.inject(telemetry(1, tick=100))
    clock.value = 0.003
    session.io_once()
    assert session.state == SessionState.ACTIVE


def test_a1_status_gates_activation_and_requires_fresh_post_activation_command():
    clock, transport, session = new_session()
    activate(clock, transport, session)
    assert session.state == SessionState.ACTIVE
    assert not session.receive_cmd_vel(0.0, 0.0, 0.0, received_at=0.003)
    assert len(transport.writes) == 1
    assert session.receive_cmd_vel(0.0, 0.25, 0.0, received_at=0.004)
    clock.value = 0.004
    session.io_once()
    command = parse_command(decode_frame(transport.writes[-1]).payload)
    assert command.command_sequence == 1 and command.reset_epoch == 0
    assert command.vy_mps == pytest.approx(0.25)


@pytest.mark.parametrize(('age', 'sent'), [(0.099, True), (0.100, False), (0.101, False)])
def test_command_freshness_boundary_never_synthesizes_zero(age, sent):
    clock, transport, session = new_session()
    activate(clock, transport, session)
    cmd_at = 0.004
    assert session.receive_cmd_vel(0.1, -0.2, 0.3, received_at=cmd_at)
    clock.value = cmd_at + age
    before = len(transport.writes)
    session.io_once()
    assert (len(transport.writes) == before + 1) is sent
    if not sent:
        assert len(transport.writes) == 1


def test_command_rate_no_burst_zero_is_real_and_sequence_exhaustion_stops():
    clock, transport, session = new_session()
    activate(clock, transport, session)
    assert session.receive_cmd_vel(0.0, 0.0, 0.0, received_at=0.004)
    clock.value = 0.004
    session.io_once()
    session.io_once()
    assert len(transport.writes) == 2
    clock.value = 0.024
    session.io_once()
    assert len(transport.writes) == 3
    seqs = [parse_command(decode_frame(w).payload).command_sequence for w in transport.writes[1:]]
    assert seqs == [1, 2]
    session._command_sequence = 0x100000000
    clock.value = 0.044
    session.io_once()
    assert session.state == SessionState.DISCONNECTED
    assert len(transport.writes) == 3


def test_invalid_latest_twist_clears_command_cache_immediately():
    clock, transport, session = new_session()
    activate(clock, transport, session)
    assert session.receive_cmd_vel(0.2, 0.1, 0.0, received_at=0.004)
    assert not session.receive_cmd_vel(float('nan'), 0.0, 0.0, received_at=0.005)
    clock.value = 0.010
    session.io_once()
    assert len(transport.writes) == 1


def test_config_attempts_are_bounded_correlated_and_old_status_ignored():
    clock, transport, session = new_session()
    first = decode_frame(transport.writes[-1])
    clock.value = 0.500
    session.io_once()
    second = decode_frame(transport.writes[-1])
    assert second.payload != first.payload
    old = status_for(sequence=1)
    transport.inject(old)
    clock.value = 0.501
    session.io_once()
    assert session.state == SessionState.CONFIGURING
    clock.value = 1.000
    session.io_once()
    assert len(transport.writes) == 3
    clock.value = 1.500
    session.io_once()
    assert session.state == SessionState.DISCONNECTED
    assert len(transport.writes) == 3


def test_rejected_config_does_not_retry_storm_and_reports_reason():
    clock, transport, session = new_session()
    transport.inject(status_for(state=2, reason=1))
    clock.value = 0.01
    session.io_once()
    assert session.state == SessionState.CONFIGURING
    assert session.config_reject_reason == 1
    clock.value = 5.0
    session.io_once()
    assert len(transport.writes) == 1


def test_telemetry_validation_ack_progression_timeout_and_owner_reset_boundary():
    clock, transport, session = new_session()
    activate(clock, transport, session)
    assert session.take_accepted_telemetry().packet.telemetry_sequence == 1
    assert session.receive_cmd_vel(0.1, 0.0, 0.0, received_at=0.004)
    clock.value = 0.004
    session.io_once()
    transport.inject(telemetry(2, tick=101, ack=1))
    clock.value = 0.01
    session.io_once()
    assert session.take_accepted_telemetry().packet.last_accepted_command_sequence == 1
    clock.value = 0.024
    session.io_once()  # COMMAND thứ hai, sequence 2
    transport.inject(telemetry(3, tick=102, ack=3))  # ACK vượt sequence đã gửi cao nhất
    clock.value = 0.025
    session.io_once()
    assert session.state == SessionState.DISCONNECTED


@pytest.mark.parametrize('packet', [
    telemetry(1, boot=10, tick=100),
    telemetry(1, epoch=1, tick=100),
])
def test_first_telemetry_boot_or_epoch_mismatch_invalidates_after_status(packet):
    clock, transport, session = new_session()
    transport.inject(status_for())
    clock.value = 0.001
    session.io_once()
    transport.inject(packet)
    clock.value = 0.002
    session.io_once()
    assert session.state == SessionState.DISCONNECTED
    assert session.continuity_reset


def test_valid_telemetry_timeout_and_mcu_watchdog_fault_are_session_recovery():
    clock, transport, session = new_session()
    activate(clock, transport, session)
    clock.value = 0.203
    session.io_once()
    assert session.state == SessionState.DISCONNECTED

    clock, transport, session = new_session()
    activate(clock, transport, session)
    transport.inject(telemetry(2, tick=101, faults=256))
    clock.value = 0.010
    session.io_once()
    accepted = session.take_accepted_telemetry()
    assert accepted.packet.mcu_fault_bits == 256
    assert session.mcu_fault_bits == 256
    assert not session.transport_healthy
    assert session.state == SessionState.DISCONNECTED


def test_telemetry_sequence_and_mcu_time_must_progress_strictly():
    clock, transport, session = new_session()
    activate(clock, transport, session)
    transport.inject(telemetry(2, tick=100))
    clock.value = 0.010
    session.io_once()
    assert session.state == SessionState.DISCONNECTED


def test_disconnect_reconnect_waits_one_second_new_epoch_and_never_resumes_cache():
    clock, transport, session = new_session()
    activate(clock, transport, session)
    assert session.receive_cmd_vel(1.0, 2.0, 3.0, received_at=0.004)
    transport.fail_read = True
    clock.value = 0.01
    session.io_once()
    assert session.state == SessionState.DISCONNECTED and not session.transport_healthy
    assert session.take_owner_reset_request()
    transport.fail_read = False
    clock.value = 1.009
    session.io_once()
    assert transport.open_calls == 1
    clock.value = 1.010
    session.io_once()
    assert transport.open_calls == 2 and session.state == SessionState.PORT_OPEN
    assert session.take_owner_reset_request()
    assert not session.receive_cmd_vel(1.0, 2.0, 3.0, received_at=1.011)
    assert len(transport.writes) == 1


def test_command_write_failure_closes_then_waits_and_requires_new_owner_identity():
    clock, transport, session = new_session()
    activate(clock, transport, session)
    assert session.receive_cmd_vel(1.0, 0.0, 0.0, received_at=0.004)
    transport.fail_write = True
    clock.value = 0.004
    session.io_once()
    assert session.state == SessionState.DISCONNECTED
    assert not session.transport_healthy
    transport.fail_write = False
    clock.value = 1.003
    session.io_once()
    assert session.state == SessionState.DISCONNECTED
    clock.value = 1.004
    session.io_once()
    assert session.state == SessionState.PORT_OPEN
    assert len(transport.writes) == 1
    assert not session.receive_cmd_vel(1.0, 0.0, 0.0, received_at=1.005)
    assert session.confirm_owner_reset(LifecycleIdentity(0, 2, True))
    assert len(transport.writes) == 2  # chỉ có CONFIG mới, không phát lại command cũ


def test_failed_open_uses_one_second_interval_without_looping():
    clock, transport = Clock(), FakeTransport()
    transport.open_result = False
    session = BridgeSession(transport, HASH, clock)
    assert not session.start() and transport.open_calls == 1
    clock.value = 0.999
    assert not session.start() and transport.open_calls == 1
    clock.value = 1.0
    transport.open_result = True
    assert session.start() and transport.open_calls == 2


def test_rearm_generation_only_clears_latest_command_and_fault_domains_are_separate():
    clock, transport, session = new_session()
    activate(clock, transport, session)
    assert session.receive_cmd_vel(1.0, 2.0, 3.0, received_at=0.004)
    session.request_rearm_generation()
    clock.value = 0.01
    session.io_once()
    assert len(transport.writes) == 1
    assert session.mcu_fault_bits == 0
    assert session.transport_healthy


def test_command_semantics_rejects_zero_without_refresh_or_history_change():
    semantics = CommandSemantics(configured_reset_epoch=0)
    before = semantics.last_accepted_command_sequence
    decision = semantics.handle_command(CommandPacket(0, 0, 0.0, 0.0, 0.0))
    assert not decision.accepted and not decision.watchdog_refresh_requested
    assert decision.reason == 'zero_sequence'
    assert semantics.last_accepted_command_sequence == before
