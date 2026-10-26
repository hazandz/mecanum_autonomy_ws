"""Session UART thuần Python; identity lifecycle luôn do SafetyLifecycle sở hữu."""

from dataclasses import dataclass
from enum import Enum
import math
import struct
import time
from typing import Callable, Optional

from .protocol_constants import (
    CONFIG_ACCEPTED, CONFIG_REJECTED, MESSAGE_CONFIG, MESSAGE_TELEMETRY,
    MAX_WIRE_FRAME_LENGTH, MESSAGE_COMMAND, REJECT_NONE,
    REJECT_HASH_MISMATCH, REJECT_LOCAL_CONFIG_INVALID,
)
from .uart_v1_codec import (
    CommandPacket, ConfigRequestPacket, ConfigStatusPacket, TelemetryPacket,
    build_wire_frame, decode_frame, parse_config_status, parse_telemetry,
    serialize_command, serialize_config_request,
)

FAULT_TRANSPORT = 1
FAULT_ESTOP_ACTIVE = 2
FAULT_MCU_COMMAND_TIMEOUT = 256
FAULT_MCU_COMMAND_INVALID = 512
FAULT_MCU_CONTROL_LOOP = 1024
FAULT_MOTOR_DRIVER = 2048
FAULT_ENCODER = 4096
ALLOWED_MCU_FAULTS = (
    FAULT_TRANSPORT | FAULT_ESTOP_ACTIVE | FAULT_MCU_COMMAND_TIMEOUT |
    FAULT_MCU_COMMAND_INVALID | FAULT_MCU_CONTROL_LOOP |
    FAULT_MOTOR_DRIVER | FAULT_ENCODER
)


class SessionState(str, Enum):
    DISCONNECTED = 'DISCONNECTED'
    PORT_OPEN = 'PORT_OPEN'
    CONFIGURING = 'CONFIGURING'
    ACTIVE = 'ACTIVE'


@dataclass(frozen=True)
class LifecycleIdentity:
    """Ảnh chụp owner; ``fresh`` do adapter xác định, độc lập ``ready``."""

    reset_epoch: int
    runtime_generation: int
    ready: bool
    sequence: int = 0
    fresh: bool = False


@dataclass(frozen=True)
class AcceptedTelemetry:
    packet: TelemetryPacket
    pi_receive_time: float


class BridgeSession:
    """Một owner IO, bộ đệm hữu hạn và state CONFIG/COMMAND ngoại tuyến."""

    CONFIG_TIMEOUT = 0.500
    TELEMETRY_TIMEOUT = 0.200
    RECONNECT_INTERVAL = 1.0
    COMMAND_PERIOD = 0.020
    COMMAND_FRESHNESS = 0.100

    def __init__(self, transport, hardware_config_hash: bytes,
                 monotonic: Callable[[], float] = time.monotonic):
        if not isinstance(hardware_config_hash, bytes) or len(hardware_config_hash) != 32:
            raise ValueError('hardware_config_hash must be 32 bytes')
        self._transport = transport
        self._hash = hardware_config_hash
        self._clock = monotonic
        self.state = SessionState.DISCONNECTED
        self._frames = bytearray()
        self._discard = False
        self._baseline_identity: Optional[LifecycleIdentity] = None
        self._confirmed_identity: Optional[LifecycleIdentity] = None
        self._identity: Optional[LifecycleIdentity] = None
        self._identity_fresh = False
        self._last_owner_sequence = -1
        self._await_owner_reset = True
        self._reset_reference_epoch: Optional[int] = None
        self._owner_reset_pending = False
        self._owner_reset_request_queued = False
        self._config_sequence = 0
        self._config_attempts = 0
        self._config_sent_at = 0.0
        self._accepted_status: Optional[ConfigStatusPacket] = None
        self._first_telemetry_deadline: Optional[float] = None
        self._telemetry_deadline = 0.0
        self._active_at = 0.0
        self._latest_cmd: Optional[tuple[float, float, float, float]] = None
        self._next_command_at = 0.0
        self._command_sequence = 1
        self._highest_command_sent = 0
        self._last_acknowledged_command = 0
        self._telemetry_sequence: Optional[int] = None
        self._mcu_time: Optional[int] = None
        self._accepted_telemetry: Optional[AcceptedTelemetry] = None
        self._continuity_reset = True
        self._reconnect_at = 0.0
        self._config_rejected = False
        self.config_reject_reason: Optional[int] = None
        self.mcu_fault_bits = 0
        self.transport_healthy = False

    def _request_owner_reset(self) -> None:
        if not self._await_owner_reset:
            self._await_owner_reset = True
            reference = self._confirmed_identity or self._identity or self._baseline_identity
            self._reset_reference_epoch = None if reference is None else reference.reset_epoch
            self._owner_reset_request_queued = False
        if not self._owner_reset_request_queued:
            self._owner_reset_pending = True
            self._owner_reset_request_queued = True

    def take_owner_reset_request(self) -> bool:
        """Lấy một yêu cầu reset đã gộp để SafetyLifecycle xử lý."""
        pending = self._owner_reset_pending
        self._owner_reset_pending = False
        return pending

    def observe_lifecycle_snapshot(self, identity: LifecycleIdentity) -> bool:
        """Nhận snapshot mới; epoch khác được coi là reset do owner cấp."""
        self._validate_identity(identity)
        if not identity.fresh:
            self._identity_fresh = False
            self._latest_cmd = None
            return False
        if identity.sequence < self._last_owner_sequence:
            self._identity_fresh = False
            self._latest_cmd = None
            return False
        if identity.sequence == self._last_owner_sequence and self._identity is not None:
            if identity != self._identity:
                self._identity_fresh = False
                self._latest_cmd = None
                return False
            self._identity_fresh = True
            return True
        if self._baseline_identity is None:
            self._baseline_identity = identity
            self._identity = identity
            self._identity_fresh = True
            self._last_owner_sequence = identity.sequence
            if self._reset_reference_epoch is None:
                self._reset_reference_epoch = identity.reset_epoch
            return True

        previous = self._identity or self._baseline_identity
        self._last_owner_sequence = identity.sequence
        self._identity = identity
        self._identity_fresh = True
        if identity.runtime_generation != previous.runtime_generation or not identity.ready:
            self._latest_cmd = None

        if identity.reset_epoch != previous.reset_epoch:
            if self._await_owner_reset:
                if identity.reset_epoch != self._reset_reference_epoch:
                    self._adopt_owner_epoch(identity, self._clock())
                return True
            self._require_owner_reset_request(reference_epoch=previous.reset_epoch)
            self._adopt_owner_epoch(identity, self._clock())
            return True

        if self._await_owner_reset:
            return False
        return True

    def confirm_owner_reset(self, identity: LifecycleIdentity) -> bool:
        """Chỉ xác nhận reset đang chờ khi owner cấp epoch khác baseline."""
        self._validate_identity(identity)
        if not self._await_owner_reset or not identity.fresh:
            return False
        if identity.sequence <= self._last_owner_sequence:
            return False
        reference = self._reset_reference_epoch
        if reference is None and self._baseline_identity is not None:
            reference = self._baseline_identity.reset_epoch
        if reference is None or identity.reset_epoch == reference:
            return False
        self._last_owner_sequence = identity.sequence
        self._adopt_owner_epoch(identity, self._clock())
        return True

    @staticmethod
    def _validate_identity(identity: LifecycleIdentity) -> None:
        if not isinstance(identity, LifecycleIdentity):
            raise ValueError('caller lifecycle identity is invalid')
        if (type(identity.reset_epoch) is not int or not 0 <= identity.reset_epoch <= 0xFFFFFFFF
                or type(identity.runtime_generation) is not int
                or not 0 <= identity.runtime_generation <= 0xFFFFFFFF
                or type(identity.sequence) is not int or not 0 <= identity.sequence <= 0xFFFFFFFFFFFFFFFF
                or type(identity.ready) is not bool or type(identity.fresh) is not bool):
            raise ValueError('caller lifecycle identity is invalid')

    def _require_owner_reset_request(self, reference_epoch: Optional[int] = None) -> None:
        if not self._await_owner_reset:
            self._await_owner_reset = True
            reference = self._confirmed_identity or self._identity or self._baseline_identity
            self._reset_reference_epoch = (
                reference_epoch if reference_epoch is not None else
                (None if reference is None else reference.reset_epoch)
            )
            self._owner_reset_request_queued = False
        elif self._reset_reference_epoch is None and reference_epoch is not None:
            self._reset_reference_epoch = reference_epoch
        self._request_owner_reset()

    def _adopt_owner_epoch(self, identity: LifecycleIdentity, now: float) -> None:
        """Xóa session cũ rồi CONFIG bằng epoch mới, kể cả khi NON_READY."""
        self._clear_session_data(clear_owner=False)
        self._identity = identity
        self._identity_fresh = True
        self._confirmed_identity = identity
        self._await_owner_reset = False
        self._reset_reference_epoch = identity.reset_epoch
        self._owner_reset_pending = False
        self._owner_reset_request_queued = False
        self.config_reject_reason = None
        self.transport_healthy = bool(getattr(self._transport, 'is_open', False))
        if self.transport_healthy:
            self.state = SessionState.PORT_OPEN
            self._begin_handshake(now)

    def start(self) -> bool:
        """Mở transport; reopen dùng owner reset đã xác nhận trong backoff."""
        now = self._clock()
        if self.state != SessionState.DISCONNECTED or now < self._reconnect_at:
            return False
        if self._await_owner_reset:
            self._request_owner_reset()
        try:
            opened = self._transport.open()
        except Exception:
            self.transport_healthy = False
            self._reconnect_at = now + self.RECONNECT_INTERVAL
            return False
        if opened is False:
            self.transport_healthy = False
            self._reconnect_at = now + self.RECONNECT_INTERVAL
            return False
        self.state = SessionState.PORT_OPEN
        self.transport_healthy = True
        self._clear_session_data(clear_owner=False)
        if (not self._await_owner_reset and self._confirmed_identity is not None
                and self._identity_fresh):
            self._begin_handshake(now)
        return True

    def receive_cmd_vel(self, vx: float, vy: float, wz: float,
                        received_at: Optional[float] = None) -> bool:
        now = self._clock() if received_at is None else received_at
        identity = self._identity
        if (self.state != SessionState.ACTIVE or identity is None or not self._identity_fresh
                or not identity.ready or now <= self._active_at):
            return False
        try:
            values = (float(vx), float(vy), float(wz))
        except (TypeError, ValueError, OverflowError):
            self._latest_cmd = None
            return False
        if not all(math.isfinite(value) for value in values):
            self._latest_cmd = None
            return False
        try:
            struct.pack('<fff', *values)
        except (OverflowError, struct.error):
            self._latest_cmd = None
            return False
        self._latest_cmd = (values[0], values[1], values[2], now)
        return True

    def request_rearm_generation(self) -> None:
        """Generation đổi chỉ xóa lệnh mới nhất; reset do owner sở hữu."""
        self._latest_cmd = None

    def take_accepted_telemetry(self) -> Optional[AcceptedTelemetry]:
        result = self._accepted_telemetry
        self._accepted_telemetry = None
        return result

    @property
    def continuity_reset(self) -> bool:
        value = self._continuity_reset
        self._continuity_reset = False
        return value

    def io_once(self, now: Optional[float] = None) -> None:
        """Đọc hữu hạn, cập nhật timer và phát tối đa một COMMAND."""
        current = self._clock() if now is None else now
        if self.state == SessionState.DISCONNECTED:
            if current >= self._reconnect_at:
                self.start()
            return
        if not getattr(self._transport, 'is_open', True):
            self._invalidate(current, transport_failure=True)
            return
        try:
            chunk = self._transport.read(max_bytes=256)
            if not isinstance(chunk, bytes) or len(chunk) > 256:
                raise OSError('transport returned an invalid bounded read chunk')
            if chunk:
                self._consume(chunk, current)
            if self.state == SessionState.CONFIGURING:
                if self._config_rejected:
                    return
                if self._accepted_status is not None:
                    if (self._first_telemetry_deadline is not None
                            and current >= self._first_telemetry_deadline):
                        self._invalidate(current, transport_failure=False)
                        return
                elif current - self._config_sent_at >= self.CONFIG_TIMEOUT:
                    if self._config_attempts >= 3:
                        self._invalidate(current, transport_failure=False)
                        return
                    self._send_config(current)
            if self.state == SessionState.ACTIVE:
                if current >= self._telemetry_deadline:
                    self._invalidate(current, transport_failure=False)
                    return
                self._send_command_if_due(current)
        except Exception:
            self._invalidate(current, transport_failure=True)
            return

    def _consume(self, chunk: bytes, now: float) -> None:
        for byte in chunk:
            if byte == 0:
                if not self._discard and self._frames:
                    self._handle_frame(bytes(self._frames) + b'\x00', now)
                self._frames.clear()
                self._discard = False
            elif not self._discard:
                if len(self._frames) >= MAX_WIRE_FRAME_LENGTH - 1:
                    self._frames.clear()
                    self._discard = True
                    self._mark_continuity_gap()
                else:
                    self._frames.append(byte)

    def _handle_frame(self, wire: bytes, now: float) -> None:
        try:
            decoded = decode_frame(wire)
            if decoded.message_type == MESSAGE_CONFIG:
                self._handle_status(parse_config_status(decoded.payload), now)
            elif decoded.message_type == MESSAGE_TELEMETRY:
                self._handle_telemetry(parse_telemetry(decoded.payload), now)
            else:
                self._mark_continuity_gap()
        except (ValueError, struct.error):
            self._mark_continuity_gap()

    def _begin_handshake(self, now: float) -> None:
        if (self._await_owner_reset or self._identity is None or not self._identity_fresh
                or self._confirmed_identity is None):
            return
        if self._config_sequence >= 0xFFFFFFFF:
            self._invalidate(now, transport_failure=False)
            return
        self._accepted_status = None
        self._first_telemetry_deadline = None
        self._config_attempts = 0
        self._config_rejected = False
        self.config_reject_reason = None
        self.state = SessionState.CONFIGURING
        self._command_sequence = 1
        self._highest_command_sent = 0
        self._last_acknowledged_command = 0
        self._send_config(now)

    def _send_config(self, now: float) -> None:
        if (self._identity is None or not self._identity_fresh or self._await_owner_reset
                or self._config_attempts >= 3 or self._config_sequence >= 0xFFFFFFFF):
            return
        self._config_sequence += 1
        packet = ConfigRequestPacket(self._config_sequence, self._identity.reset_epoch, self._hash)
        self._transport.write(build_wire_frame(MESSAGE_CONFIG, serialize_config_request(packet)))
        self._config_attempts += 1
        self._config_sent_at = now

    def _handle_status(self, status: ConfigStatusPacket, now: float) -> None:
        identity = self._identity
        if (self.state != SessionState.CONFIGURING or identity is None or self._await_owner_reset
                or self._config_rejected):
            return
        if (status.config_sequence != self._config_sequence
                or status.reset_epoch != identity.reset_epoch
                or status.hardware_config_hash != self._hash
                or status.mcu_boot_id == 0):
            return
        if status.config_status == CONFIG_REJECTED:
            if status.reject_reason not in (REJECT_HASH_MISMATCH, REJECT_LOCAL_CONFIG_INVALID):
                return
            self._config_rejected = True
            self._accepted_status = None
            self._first_telemetry_deadline = None
            self.config_reject_reason = status.reject_reason
            self._latest_cmd = None
            return
        if status.config_status != CONFIG_ACCEPTED or status.reject_reason != REJECT_NONE:
            return
        if self._accepted_status is None:
            self._accepted_status = status
            self._first_telemetry_deadline = now + self.TELEMETRY_TIMEOUT

    def _telemetry_valid(self, packet: TelemetryPacket, first: bool) -> bool:
        status = self._accepted_status
        identity = self._identity
        if (status is None or identity is None or packet.mcu_boot_id != status.mcu_boot_id
                or packet.reset_epoch != status.reset_epoch or packet.reset_epoch != identity.reset_epoch):
            return False
        if type(packet.mcu_fault_bits) is not int or packet.mcu_fault_bits & ~ALLOWED_MCU_FAULTS:
            return False
        if type(packet.estop_aux_active) is not int or packet.estop_aux_active not in (0, 1):
            return False
        if (type(packet.last_accepted_command_sequence) is not int
                or packet.last_accepted_command_sequence > self._highest_command_sent
                or packet.last_accepted_command_sequence < self._last_acknowledged_command):
            return False
        if first and packet.last_accepted_command_sequence != 0:
            return False
        if type(packet.telemetry_sequence) is not int or not 0 <= packet.telemetry_sequence <= 0xFFFFFFFF:
            return False
        if type(packet.mcu_monotonic_time_us) is not int or not 0 <= packet.mcu_monotonic_time_us <= 0xFFFFFFFFFFFFFFFF:
            return False
        if self._telemetry_sequence is not None and packet.telemetry_sequence <= self._telemetry_sequence:
            return False
        if self._mcu_time is not None and packet.mcu_monotonic_time_us <= self._mcu_time:
            return False
        return True

    def _handle_telemetry(self, packet: TelemetryPacket, now: float) -> None:
        first = self.state == SessionState.CONFIGURING
        if first:
            if self._config_rejected or self._accepted_status is None:
                return
            if (self._first_telemetry_deadline is None
                    or now >= self._first_telemetry_deadline):
                self._invalidate(now, transport_failure=False)
                return
        elif self.state != SessionState.ACTIVE:
            return
        if not self._telemetry_valid(packet, first):
            self._invalidate(now, transport_failure=False)
            return

        self._telemetry_sequence = packet.telemetry_sequence
        self._mcu_time = packet.mcu_monotonic_time_us
        self._last_acknowledged_command = packet.last_accepted_command_sequence
        self._telemetry_deadline = now + self.TELEMETRY_TIMEOUT
        self.mcu_fault_bits = packet.mcu_fault_bits
        report = AcceptedTelemetry(packet, now)
        if first:
            self.state = SessionState.ACTIVE
            self._active_at = now
            self._first_telemetry_deadline = None
        self._accepted_telemetry = report
        if packet.mcu_fault_bits & (FAULT_TRANSPORT | FAULT_MCU_COMMAND_TIMEOUT):
            self._invalidate(now, transport_failure=False)
            self.mcu_fault_bits = packet.mcu_fault_bits
            self._accepted_telemetry = report

    def _send_command_if_due(self, now: float) -> None:
        identity = self._identity
        latest = self._latest_cmd
        if (identity is None or not self._identity_fresh or not identity.ready
                or latest is None or now < self._next_command_at):
            return
        vx, vy, wz, received = latest
        if received <= self._active_at or now < received or now - received >= self.COMMAND_FRESHNESS:
            self._latest_cmd = None
            return
        if self._command_sequence > 0xFFFFFFFF:
            self._invalidate(now, transport_failure=False)
            return
        payload = serialize_command(CommandPacket(self._command_sequence, identity.reset_epoch,
                                                  vx, vy, wz))
        self._transport.write(build_wire_frame(MESSAGE_COMMAND, payload))
        self._highest_command_sent = self._command_sequence
        self._command_sequence += 1
        self._next_command_at = now + self.COMMAND_PERIOD

    def _mark_continuity_gap(self) -> None:
        self._continuity_reset = True
        self._accepted_telemetry = None

    def _clear_session_data(self, clear_owner: bool) -> None:
        self._frames.clear()
        self._discard = False
        self._accepted_status = None
        self._first_telemetry_deadline = None
        self._latest_cmd = None
        self._telemetry_sequence = None
        self._mcu_time = None
        self._accepted_telemetry = None
        self._highest_command_sent = 0
        self._last_acknowledged_command = 0
        self._command_sequence = 1
        self._config_attempts = 0
        self._config_rejected = False
        self.config_reject_reason = None
        self._continuity_reset = True
        self.mcu_fault_bits = 0
        if clear_owner:
            self._confirmed_identity = None
            self._identity = None
            self._identity_fresh = False
            self._await_owner_reset = True

    def _invalidate(self, now: float, transport_failure: bool) -> None:
        self._latest_cmd = None
        self._clear_session_data(clear_owner=False)
        self._continuity_reset = True
        self._require_owner_reset_request()
        self.transport_healthy = False
        try:
            self._transport.close()
        except Exception:
            pass
        self.state = SessionState.DISCONNECTED
        self._reconnect_at = now + self.RECONNECT_INTERVAL
