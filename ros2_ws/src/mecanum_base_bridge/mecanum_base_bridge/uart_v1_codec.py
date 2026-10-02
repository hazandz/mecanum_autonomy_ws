"""Pure byte codec for the Pi--STM32 UART v1 contract."""

from dataclasses import dataclass
import struct
from typing import Union

from .cobs_codec import CobsDecodeError, cobs_decode, cobs_encode
from .crc16_ccitt_false import crc16_ccitt_false
from .protocol_constants import (
    COMMAND_PAYLOAD_LENGTH, CONFIG_REQUEST_PAYLOAD_LENGTH,
    CONFIG_STATUS_PAYLOAD_LENGTH, CRC_LENGTH, HEADER_LENGTH,
    MAX_RAW_FRAME_LENGTH, MAX_WIRE_FRAME_LENGTH, MESSAGE_COMMAND,
    MESSAGE_CONFIG, MESSAGE_TELEMETRY, PROTOCOL_VERSION,
    TELEMETRY_PAYLOAD_LENGTH, VALID_MESSAGE_TYPES, WIRE_DELIMITER,
)


class UartV1CodecError(ValueError):
    """Base class for rejected UART v1 codec frames."""


class WireFrameError(UartV1CodecError):
    """The frame is not bounded and delimiter-terminated."""


class FrameTooLargeError(UartV1CodecError):
    """The frame exceeds the contract's bounded storage."""


class CrcMismatchError(UartV1CodecError):
    """The received CRC is invalid."""


class ProtocolVersionError(UartV1CodecError):
    """The protocol version is unsupported."""


class MessageTypeError(UartV1CodecError):
    """The message type is unsupported."""


class PayloadLengthError(UartV1CodecError):
    """The payload length violates the contract."""


@dataclass(frozen=True)
class CommandPacket:
    command_sequence: int
    reset_epoch: int
    vx_mps: float
    vy_mps: float
    wz_radps: float


@dataclass(frozen=True)
class ConfigRequestPacket:
    config_sequence: int
    reset_epoch: int
    hardware_config_hash: bytes


@dataclass(frozen=True)
class ConfigStatusPacket:
    config_sequence: int
    reset_epoch: int
    hardware_config_hash: bytes
    mcu_boot_id: int
    config_status: int
    reject_reason: int


@dataclass(frozen=True)
class TelemetryPacket:
    telemetry_sequence: int
    mcu_boot_id: int
    reset_epoch: int
    mcu_monotonic_time_us: int
    ticks_fl: int
    ticks_fr: int
    ticks_rl: int
    ticks_rr: int
    last_accepted_command_sequence: int
    mcu_fault_bits: int
    estop_aux_active: int


@dataclass(frozen=True)
class DecodedFrame:
    protocol_version: int
    message_type: int
    payload: bytes
    crc16: int
    raw_frame: bytes


TypedPacket = Union[CommandPacket, ConfigRequestPacket, ConfigStatusPacket, TelemetryPacket]


def _validate_uint(value: int, bits: int, field_name: str) -> None:
    if not isinstance(value, int) or not 0 <= value < (1 << bits):
        raise ValueError(f'{field_name} must fit uint{bits}')


def _validate_hash(value: bytes) -> None:
    if not isinstance(value, bytes) or len(value) != 32:
        raise ValueError('hardware_config_hash must contain exactly 32 bytes')


def _expected_payload_length(message_type: int, payload_length: int) -> int:
    if message_type == MESSAGE_COMMAND:
        return COMMAND_PAYLOAD_LENGTH
    if message_type == MESSAGE_TELEMETRY:
        return TELEMETRY_PAYLOAD_LENGTH
    if message_type == MESSAGE_CONFIG:
        if payload_length in (CONFIG_REQUEST_PAYLOAD_LENGTH, CONFIG_STATUS_PAYLOAD_LENGTH):
            return payload_length
        raise PayloadLengthError('CONFIG payload must be 40 or 50 bytes')
    raise MessageTypeError(f'unsupported message type: {message_type:#04x}')


def _validate_payload_length(message_type: int, payload: bytes) -> None:
    if message_type not in VALID_MESSAGE_TYPES:
        raise MessageTypeError(f'unsupported message type: {message_type:#04x}')
    if len(payload) != _expected_payload_length(message_type, len(payload)):
        raise PayloadLengthError('payload length violates message contract')


def serialize_command(packet: CommandPacket) -> bytes:
    _validate_uint(packet.command_sequence, 32, 'command_sequence')
    _validate_uint(packet.reset_epoch, 32, 'reset_epoch')
    return struct.pack('<IIfff', packet.command_sequence, packet.reset_epoch,
                       packet.vx_mps, packet.vy_mps, packet.wz_radps)


def parse_command(payload: bytes) -> CommandPacket:
    _validate_payload_length(MESSAGE_COMMAND, payload)
    return CommandPacket(*struct.unpack('<IIfff', payload))


def serialize_config_request(packet: ConfigRequestPacket) -> bytes:
    _validate_uint(packet.config_sequence, 32, 'config_sequence')
    _validate_uint(packet.reset_epoch, 32, 'reset_epoch')
    _validate_hash(packet.hardware_config_hash)
    return struct.pack('<II32s', packet.config_sequence, packet.reset_epoch,
                       packet.hardware_config_hash)


def parse_config_request(payload: bytes) -> ConfigRequestPacket:
    if len(payload) != CONFIG_REQUEST_PAYLOAD_LENGTH:
        raise PayloadLengthError('CONFIG_REQUEST payload must be 40 bytes')
    return ConfigRequestPacket(*struct.unpack('<II32s', payload))


def serialize_config_status(packet: ConfigStatusPacket) -> bytes:
    _validate_uint(packet.config_sequence, 32, 'config_sequence')
    _validate_uint(packet.reset_epoch, 32, 'reset_epoch')
    _validate_hash(packet.hardware_config_hash)
    _validate_uint(packet.mcu_boot_id, 64, 'mcu_boot_id')
    _validate_uint(packet.config_status, 8, 'config_status')
    _validate_uint(packet.reject_reason, 8, 'reject_reason')
    return struct.pack('<II32sQBB', packet.config_sequence, packet.reset_epoch,
                       packet.hardware_config_hash, packet.mcu_boot_id,
                       packet.config_status, packet.reject_reason)


def parse_config_status(payload: bytes) -> ConfigStatusPacket:
    if len(payload) != CONFIG_STATUS_PAYLOAD_LENGTH:
        raise PayloadLengthError('CONFIG_STATUS payload must be 50 bytes')
    return ConfigStatusPacket(*struct.unpack('<II32sQBB', payload))


def serialize_telemetry(packet: TelemetryPacket) -> bytes:
    _validate_uint(packet.telemetry_sequence, 32, 'telemetry_sequence')
    _validate_uint(packet.mcu_boot_id, 64, 'mcu_boot_id')
    _validate_uint(packet.reset_epoch, 32, 'reset_epoch')
    _validate_uint(packet.mcu_monotonic_time_us, 64, 'mcu_monotonic_time_us')
    _validate_uint(packet.last_accepted_command_sequence, 32, 'last_accepted_command_sequence')
    _validate_uint(packet.mcu_fault_bits, 32, 'mcu_fault_bits')
    _validate_uint(packet.estop_aux_active, 8, 'estop_aux_active')
    return struct.pack(
        '<IQIQqqqqIIB', packet.telemetry_sequence, packet.mcu_boot_id,
        packet.reset_epoch, packet.mcu_monotonic_time_us, packet.ticks_fl,
        packet.ticks_fr, packet.ticks_rl, packet.ticks_rr,
        packet.last_accepted_command_sequence, packet.mcu_fault_bits,
        packet.estop_aux_active,
    )


def parse_telemetry(payload: bytes) -> TelemetryPacket:
    _validate_payload_length(MESSAGE_TELEMETRY, payload)
    return TelemetryPacket(*struct.unpack('<IQIQqqqqIIB', payload))


def build_raw_frame(message_type: int, payload: bytes) -> bytes:
    _validate_payload_length(message_type, payload)
    header = struct.pack('<HBB', PROTOCOL_VERSION, message_type, len(payload))
    body = header + payload
    raw = body + struct.pack('<H', crc16_ccitt_false(body))
    if len(raw) > MAX_RAW_FRAME_LENGTH:
        raise FrameTooLargeError('raw frame exceeds 96-byte contract storage')
    return raw


def build_wire_frame(message_type: int, payload: bytes) -> bytes:
    wire = cobs_encode(build_raw_frame(message_type, payload)) + bytes((WIRE_DELIMITER,))
    if len(wire) > MAX_WIRE_FRAME_LENGTH:
        raise FrameTooLargeError('wire frame exceeds 98-byte contract receive buffer')
    return wire


def decode_frame(wire_frame: bytes) -> DecodedFrame:
    """Decode and strictly validate a complete wire frame."""
    if len(wire_frame) > MAX_WIRE_FRAME_LENGTH:
        raise FrameTooLargeError('wire frame exceeds 98-byte contract receive buffer')
    if len(wire_frame) < 2 or wire_frame[-1] != WIRE_DELIMITER:
        raise WireFrameError('wire frame must end in one 0x00 delimiter')
    try:
        raw = cobs_decode(wire_frame[:-1])
    except CobsDecodeError:
        raise
    if len(raw) > MAX_RAW_FRAME_LENGTH:
        raise FrameTooLargeError('decoded raw frame exceeds 96-byte contract storage')
    if len(raw) < HEADER_LENGTH + CRC_LENGTH:
        raise PayloadLengthError('raw frame is shorter than header plus CRC')

    protocol_version, message_type, payload_length = struct.unpack('<HBB', raw[:HEADER_LENGTH])
    if protocol_version != PROTOCOL_VERSION:
        raise ProtocolVersionError(f'unsupported protocol version: {protocol_version:#06x}')
    if message_type not in VALID_MESSAGE_TYPES:
        raise MessageTypeError(f'unsupported message type: {message_type:#04x}')
    expected_length = _expected_payload_length(message_type, payload_length)
    if payload_length != expected_length:
        raise PayloadLengthError('declared payload length violates message contract')
    if len(raw) != HEADER_LENGTH + payload_length + CRC_LENGTH:
        raise PayloadLengthError('raw frame length does not match header payload length')

    received_crc = struct.unpack('<H', raw[-CRC_LENGTH:])[0]
    calculated_crc = crc16_ccitt_false(raw[:-CRC_LENGTH])
    if received_crc != calculated_crc:
        raise CrcMismatchError(
            f'CRC mismatch: received {received_crc:#06x}, calculated {calculated_crc:#06x}'
        )
    return DecodedFrame(protocol_version, message_type, raw[HEADER_LENGTH:-CRC_LENGTH],
                        received_crc, raw)


def serialize_packet(packet: TypedPacket) -> tuple[int, bytes]:
    if isinstance(packet, CommandPacket):
        return MESSAGE_COMMAND, serialize_command(packet)
    if isinstance(packet, ConfigRequestPacket):
        return MESSAGE_CONFIG, serialize_config_request(packet)
    if isinstance(packet, ConfigStatusPacket):
        return MESSAGE_CONFIG, serialize_config_status(packet)
    if isinstance(packet, TelemetryPacket):
        return MESSAGE_TELEMETRY, serialize_telemetry(packet)
    raise TypeError(f'unsupported packet type: {type(packet)!r}')


def parse_typed_packet(frame: DecodedFrame) -> TypedPacket:
    if frame.message_type == MESSAGE_COMMAND:
        return parse_command(frame.payload)
    if frame.message_type == MESSAGE_TELEMETRY:
        return parse_telemetry(frame.payload)
    if len(frame.payload) == CONFIG_REQUEST_PAYLOAD_LENGTH:
        return parse_config_request(frame.payload)
    if len(frame.payload) == CONFIG_STATUS_PAYLOAD_LENGTH:
        return parse_config_status(frame.payload)
    raise PayloadLengthError('validated CONFIG frame has an impossible payload length')
