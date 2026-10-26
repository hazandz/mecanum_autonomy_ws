from collections import deque
import importlib.util
import pathlib
import sys

import pytest

from mecanum_base_bridge.bridge_session import (
    BridgeSession, LifecycleIdentity, SessionState,
)
from mecanum_base_bridge.protocol_constants import (
    CONFIG_REJECTED, MESSAGE_CONFIG, MESSAGE_TELEMETRY, REJECT_HASH_MISMATCH,
)
from mecanum_base_bridge.uart_v1_codec import (
    CommandPacket, ConfigStatusPacket, TelemetryPacket,
    build_wire_frame, decode_frame, parse_command, parse_config_request,
    serialize_config_status, serialize_telemetry,
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
INITIAL = LifecycleIdentity(0, 0, False, sequence=1, fresh=True)
RESET = LifecycleIdentity(1, 0, False, sequence=2, fresh=True)


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


def status_for(sequence=1, epoch=1, boot=9, state=1, reason=0):
    return build_wire_frame(MESSAGE_CONFIG, serialize_config_status(
        ConfigStatusPacket(sequence, epoch, HASH, boot, state, reason)))


def telemetry(sequence, boot=9, epoch=1, tick=100, ack=0, faults=0, estop=0):
    return build_wire_frame(MESSAGE_TELEMETRY, serialize_telemetry(
        TelemetryPacket(sequence, boot, epoch, tick, 0, 0, 0, 0, ack, faults, estop)))


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
    session.observe_lifecycle_snapshot(LifecycleIdentity(1, 1, True, sequence=3, fresh=True))


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
    assert command.command_sequence == 1 and command.reset_epoch == 1
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
    telemetry(1, epoch=2, tick=100),
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
    session.observe_lifecycle_snapshot(LifecycleIdentity(2, 0, False, sequence=4, fresh=True))
    clock.value = 1.009
    session.io_once()
    assert transport.open_calls == 1
    clock.value = 1.010
    session.io_once()
    assert transport.open_calls == 2 and session.state == SessionState.CONFIGURING
    assert not session.take_owner_reset_request()
    assert not session.receive_cmd_vel(1.0, 2.0, 3.0, received_at=1.011)
    assert len(transport.writes) == 2


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
    assert session.confirm_owner_reset(LifecycleIdentity(2, 0, False, sequence=4, fresh=True))
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


def test_rearm_with_same_owner_epoch_cannot_confirm_pending_reset():
    clock, transport = Clock(), FakeTransport()
    session = BridgeSession(transport, HASH, clock)
    assert session.start()
    baseline = LifecycleIdentity(7, 4, False, sequence=5, fresh=True)
    session.observe_lifecycle_snapshot(baseline)
    rearm_only = LifecycleIdentity(7, 5, True, sequence=6, fresh=True)
    assert not session.confirm_owner_reset(rearm_only)
    assert session._await_owner_reset
    assert session.state == SessionState.PORT_OPEN
    assert session.transport_healthy
    assert transport.writes == []


def _safety_lifecycle_core():
    repository = pathlib.Path(__file__).resolve().parents[4]
    source = repository / 'ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/runtime_safety/safety_contract.py'
    spec = importlib.util.spec_from_file_location('u4_test_safety_contract', source)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.SafetyLifecycleCore


def _identity_from_core(snapshot, fresh=True):
    return LifecycleIdentity(snapshot.reset_epoch, snapshot.runtime_generation,
                             snapshot.motion_permitted, snapshot.sequence, fresh)


def test_real_safety_lifecycle_core_reset_epoch_configures_while_non_ready():
    Core = _safety_lifecycle_core()
    core = Core()
    core.configure(1)
    baseline = core.activate(2)
    assert baseline.reset_epoch == 0 and not baseline.motion_permitted
    clock, transport = Clock(), FakeTransport()
    session = BridgeSession(transport, HASH, clock)
    assert session.start()
    session.observe_lifecycle_snapshot(_identity_from_core(baseline))

    reset = core.begin_reset(3)
    assert reset.reset_epoch == 1 and not reset.motion_permitted
    assert session.confirm_owner_reset(_identity_from_core(reset))
    request = parse_config_request(decode_frame(transport.writes[-1]).payload)
    assert request.reset_epoch == 1
    assert session.state == SessionState.CONFIGURING

    transport.inject(telemetry(1, epoch=1, tick=100))
    clock.value = 0.001
    session.io_once()
    assert session.state == SessionState.CONFIGURING
    transport.inject(status_for(sequence=request.config_sequence, epoch=1))
    clock.value = 0.002
    session.io_once()
    assert session.state == SessionState.CONFIGURING
    transport.inject(telemetry(1, epoch=1, tick=100))
    clock.value = 0.003
    session.io_once()
    assert session.state == SessionState.ACTIVE
    assert not session.receive_cmd_vel(0.1, 0.0, 0.0, received_at=0.004)

    ready = core.rearm(4)
    session.observe_lifecycle_snapshot(_identity_from_core(ready))
    assert session.receive_cmd_vel(0.1, 0.0, 0.0, received_at=0.004)
    clock.value = 0.004
    session.io_once()
    command = parse_command(decode_frame(transport.writes[-1]).payload)
    assert command.command_sequence == 1 and command.reset_epoch == 1


def test_epoch_zero_is_valid_when_owner_epoch_changed_from_nonzero_baseline():
    clock, transport = Clock(), FakeTransport()
    session = BridgeSession(transport, HASH, clock)
    assert session.start()
    session.observe_lifecycle_snapshot(LifecycleIdentity(9, 3, False, 10, True))
    assert session.confirm_owner_reset(LifecycleIdentity(0, 0, False, 11, True))
    request = parse_config_request(decode_frame(transport.writes[-1]).payload)
    assert request.reset_epoch == 0


@pytest.mark.parametrize('identity', [
    LifecycleIdentity(True, 0, False, 2, True),
    LifecycleIdentity(1.0, 0, False, 2, True),
    LifecycleIdentity(1, False, False, 2, True),
    LifecycleIdentity(1, 0.0, False, 2, True),
    LifecycleIdentity(1, 0, 1, 2, True),
    LifecycleIdentity(1, 0, False, True, True),
    LifecycleIdentity(1, 0, False, 2.0, True),
    LifecycleIdentity(1, 0, False, 2, 1),
])
def test_owner_identity_requires_exact_uint_types_boolean_fields_and_freshness(identity):
    clock, transport = Clock(), FakeTransport()
    session = BridgeSession(transport, HASH, clock)
    assert session.start()
    with pytest.raises(ValueError):
        session.observe_lifecycle_snapshot(identity)


def test_stale_or_out_of_order_owner_snapshot_cannot_confirm_reset():
    clock, transport = Clock(), FakeTransport()
    session = BridgeSession(transport, HASH, clock)
    assert session.start()
    session.observe_lifecycle_snapshot(LifecycleIdentity(0, 0, False, 5, True))
    assert not session.confirm_owner_reset(LifecycleIdentity(1, 0, False, 6, False))
    assert not session.confirm_owner_reset(LifecycleIdentity(1, 0, False, 4, True))
    assert transport.writes == []


def test_confirm_outside_pending_owner_reset_cannot_bypass_config_handshake():
    clock, transport, session = new_session()
    writes_before = len(transport.writes)
    assert not session.confirm_owner_reset(LifecycleIdentity(2, 0, False, 3, True))
    assert len(transport.writes) == writes_before
    assert session.state == SessionState.CONFIGURING


def test_owner_epoch_change_during_active_invalidates_before_new_command_epoch():
    clock, transport, session = new_session()
    activate(clock, transport, session)
    assert session.receive_cmd_vel(0.5, 0.2, 0.1, received_at=0.004)
    session.observe_lifecycle_snapshot(LifecycleIdentity(2, 0, False, 4, True))
    assert session.state == SessionState.CONFIGURING
    request = parse_config_request(decode_frame(transport.writes[-1]).payload)
    assert request.reset_epoch == 2
    assert not session.receive_cmd_vel(0.5, 0.2, 0.1, received_at=0.005)
    assert len(transport.writes) == 2
    transport.inject(status_for(sequence=request.config_sequence, epoch=2))
    clock.value = 0.006
    session.io_once()
    transport.inject(telemetry(1, epoch=2, tick=101))
    clock.value = 0.007
    session.io_once()
    assert session.state == SessionState.ACTIVE
    assert not session.receive_cmd_vel(0.5, 0.2, 0.1, received_at=0.007)
    session.observe_lifecycle_snapshot(LifecycleIdentity(2, 1, True, 5, True))
    assert session.receive_cmd_vel(0.5, 0.2, 0.1, received_at=0.008)


def test_owner_epoch_received_during_backoff_is_kept_and_config_counter_never_reuses():
    clock, transport, session = new_session()
    first_request = parse_config_request(decode_frame(transport.writes[-1]).payload)
    activate(clock, transport, session)
    transport.fail_read = True
    clock.value = 0.010
    session.io_once()
    assert session.state == SessionState.DISCONNECTED
    assert session.take_owner_reset_request()
    transport.fail_read = False
    session.observe_lifecycle_snapshot(LifecycleIdentity(2, 0, False, 4, True))
    assert not session.take_owner_reset_request()
    clock.value = 1.010
    session.io_once()
    assert session.state == SessionState.CONFIGURING
    second_request = parse_config_request(decode_frame(transport.writes[-1]).payload)
    assert second_request.config_sequence == first_request.config_sequence + 1
    assert second_request.reset_epoch == 2
    assert not session.take_owner_reset_request()


def test_accepted_status_at_490ms_stops_config_retry_and_allows_telemetry_deadline():
    clock, transport, session = new_session()
    transport.inject(status_for(sequence=1))
    clock.value = 0.490
    session.io_once()
    assert len(transport.writes) == 1
    transport.inject(status_for(sequence=1))
    clock.value = 0.500
    session.io_once()
    assert len(transport.writes) == 1
    transport.inject(telemetry(1, tick=100))
    clock.value = 0.689
    session.io_once()
    assert session.state == SessionState.ACTIVE


def test_first_telemetry_at_200ms_deadline_is_rejected():
    clock, transport, session = new_session()
    transport.inject(status_for(sequence=1))
    clock.value = 0.490
    session.io_once()
    transport.inject(telemetry(1, tick=100))
    clock.value = 0.690
    session.io_once()
    assert session.state == SessionState.DISCONNECTED
    assert session.take_accepted_telemetry() is None
    assert session.continuity_reset


def test_duplicate_accepted_status_does_not_extend_first_telemetry_deadline():
    clock, transport, session = new_session()
    transport.inject(status_for(sequence=1))
    clock.value = 0.490
    session.io_once()
    transport.inject(status_for(sequence=1))
    clock.value = 0.600
    session.io_once()
    assert session.state == SessionState.CONFIGURING
    assert len(transport.writes) == 1
    clock.value = 0.690
    session.io_once()
    assert session.state == SessionState.DISCONNECTED


def test_rejected_status_terminates_activation_for_that_handshake():
    clock, transport, session = new_session()
    transport.inject(status_for(sequence=1))
    clock.value = 0.050
    session.io_once()
    transport.inject(status_for(sequence=1, state=CONFIG_REJECTED, reason=REJECT_HASH_MISMATCH))
    clock.value = 0.060
    session.io_once()
    transport.inject(telemetry(1, tick=100))
    clock.value = 0.061
    session.io_once()
    assert session.state == SessionState.CONFIGURING
    assert session.take_accepted_telemetry() is None
    assert len(transport.writes) == 1


ALLOWED_FAULTS = (1, 2, 256, 512, 1024, 2048, 4096, 1 | 2 | 256 | 512 | 1024 | 2048 | 4096)


@pytest.mark.parametrize('faults', ALLOWED_FAULTS)
def test_each_contract_mcu_fault_bit_is_validated_and_preserved_as_report(faults):
    clock, transport, session = new_session()
    transport.inject(status_for(sequence=1))
    clock.value = 0.001
    session.io_once()
    transport.inject(telemetry(1, tick=100, faults=faults))
    clock.value = 0.002
    session.io_once()
    report = session.take_accepted_telemetry()
    assert report is not None and report.packet.mcu_fault_bits == faults
    assert session.mcu_fault_bits == faults
    if faults & (1 | 256):
        assert session.state == SessionState.DISCONNECTED
        assert not session.transport_healthy
    else:
        assert session.state == SessionState.ACTIVE


@pytest.mark.parametrize('faults', [4, 8, 16, 32, 64, 128, 8192, 0x80000000])
def test_policy_imu_and_reserved_mcu_fault_bits_are_never_reported(faults):
    clock, transport, session = new_session()
    transport.inject(status_for(sequence=1))
    clock.value = 0.001
    session.io_once()
    transport.inject(telemetry(1, tick=100, faults=faults))
    clock.value = 0.002
    session.io_once()
    assert session.take_accepted_telemetry() is None
    assert session.state == SessionState.DISCONNECTED


@pytest.mark.parametrize('packet', [
    telemetry(1, tick=100, ack=1),
    telemetry(1, tick=100, estop=2),
])
def test_first_telemetry_rejected_before_activation_when_ack_or_estop_invalid(packet):
    clock, transport, session = new_session()
    transport.inject(status_for(sequence=1))
    clock.value = 0.001
    session.io_once()
    transport.inject(packet)
    clock.value = 0.002
    session.io_once()
    assert session.state == SessionState.DISCONNECTED
    assert session.take_accepted_telemetry() is None


def test_valid_timeout_fault_report_is_emitted_only_after_all_fields_validate():
    clock, transport, session = new_session()
    transport.inject(status_for(sequence=1))
    clock.value = 0.001
    session.io_once()
    transport.inject(telemetry(1, tick=100, faults=256, ack=1))
    clock.value = 0.002
    session.io_once()
    assert session.take_accepted_telemetry() is None

    clock, transport, session = new_session()
    transport.inject(status_for(sequence=1))
    clock.value = 0.001
    session.io_once()
    transport.inject(telemetry(1, tick=100, faults=256, ack=0))
    clock.value = 0.002
    session.io_once()
    report = session.take_accepted_telemetry()
    assert report is not None and report.packet.mcu_fault_bits == 256
    assert session.state == SessionState.DISCONNECTED


def test_invalid_active_telemetry_never_reaches_consumer():
    clock, transport, session = new_session()
    activate(clock, transport, session)
    session.take_accepted_telemetry()
    assert session.receive_cmd_vel(0.1, 0.0, 0.0, received_at=0.004)
    clock.value = 0.004
    session.io_once()
    transport.inject(telemetry(2, tick=101, ack=2, faults=256))
    clock.value = 0.010
    session.io_once()
    assert session.take_accepted_telemetry() is None
    assert session.state == SessionState.DISCONNECTED


def test_bad_crc_clears_pending_report_latches_continuity_and_keeps_high_water():
    clock, transport, session = new_session()
    activate(clock, transport, session)
    assert session.continuity_reset
    transport.inject(telemetry(2, tick=101))
    clock.value = 0.010
    session.io_once()
    assert session.take_accepted_telemetry().packet.telemetry_sequence == 2
    bad = bytearray(telemetry(3, tick=102))
    bad[4] ^= 1
    transport.inject(bytes(bad))
    clock.value = 0.020
    session.io_once()
    assert session.take_accepted_telemetry() is None
    assert session.continuity_reset
    transport.inject(telemetry(2, tick=103))
    clock.value = 0.030
    session.io_once()
    assert session.state == SessionState.DISCONNECTED
    assert session.take_accepted_telemetry() is None


def test_malformed_frame_does_not_refresh_valid_telemetry_deadline():
    clock, transport, session = new_session()
    activate(clock, transport, session)
    session.take_accepted_telemetry()
    bad = bytearray(telemetry(2, tick=101))
    bad[4] ^= 1
    transport.inject(bytes(bad))
    clock.value = 0.100
    session.io_once()
    assert session.state == SessionState.ACTIVE
    assert session.continuity_reset
    clock.value = 0.203
    session.io_once()
    assert session.state == SessionState.DISCONNECTED


def test_oversize_frame_latches_continuity_and_pending_old_telemetry_is_cleared_on_invalidate():
    clock, transport, session = new_session()
    activate(clock, transport, session)
    assert session.take_accepted_telemetry() is not None
    from mecanum_base_bridge.protocol_constants import MAX_WIRE_FRAME_LENGTH
    transport.inject(b'\x01' * (MAX_WIRE_FRAME_LENGTH + 1) + b'\x00')
    clock.value = 0.010
    session.io_once()
    assert session.continuity_reset
    assert session.take_accepted_telemetry() is None

    transport.fail_read = True
    clock.value = 0.020
    session.io_once()
    assert session.take_accepted_telemetry() is None
