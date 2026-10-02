import pytest

from mecanum_base_bridge.protocol_constants import MESSAGE_COMMAND, MESSAGE_CONFIG, MESSAGE_TELEMETRY
from mecanum_base_bridge.uart_v1_codec import (
    CommandPacket, ConfigRequestPacket, ConfigStatusPacket, TelemetryPacket,
    build_raw_frame, build_wire_frame, decode_frame, parse_typed_packet,
    serialize_packet,
)


def hx(value: str) -> bytes:
    return bytes.fromhex(value)


# Literal bytes transcribed from Pi_STM32_UART_v1_Golden_Vectors.md, not codec output.
VALID_VECTORS = (
    pytest.param('V1 COMMAND', MESSAGE_COMMAND,
        hx('40 30 20 10 44 33 22 11 00 00 a0 3f 00 00 00 bf 00 00 40 3f'),
        hx('01 00 01 14 40 30 20 10 44 33 22 11 00 00 a0 3f 00 00 00 bf 00 00 40 3f 30 6e'),
        hx('02 01 0b 01 14 40 30 20 10 44 33 22 11 01 03 a0 3f 01 01 02 bf 01 05 40 3f 30 6e 00'),
        CommandPacket(0x10203040, 0x11223344, 1.25, -0.5, 0.75), id='v1_command'),
    pytest.param('V2 CONFIG_REQUEST', MESSAGE_CONFIG,
        hx('04 03 02 01 44 33 22 11 00 01 02 03 04 05 06 07 08 09 0a 0b 0c 0d 0e 0f 10 11 12 13 14 15 16 17 18 19 1a 1b 1c 1d 1e 1f'),
        hx('01 00 03 28 04 03 02 01 44 33 22 11 00 01 02 03 04 05 06 07 08 09 0a 0b 0c 0d 0e 0f 10 11 12 13 14 15 16 17 18 19 1a 1b 1c 1d 1e 1f 7b e7'),
        hx('02 01 0b 03 28 04 03 02 01 44 33 22 11 22 01 02 03 04 05 06 07 08 09 0a 0b 0c 0d 0e 0f 10 11 12 13 14 15 16 17 18 19 1a 1b 1c 1d 1e 1f 7b e7 00'),
        ConfigRequestPacket(0x01020304, 0x11223344, bytes(range(32))), id='v2_config_request'),
    pytest.param('V3 CONFIG_STATUS_ACCEPTED', MESSAGE_CONFIG,
        hx('04 03 02 01 44 33 22 11 00 01 02 03 04 05 06 07 08 09 0a 0b 0c 0d 0e 0f 10 11 12 13 14 15 16 17 18 19 1a 1b 1c 1d 1e 1f 08 07 06 05 04 03 02 01 01 00'),
        hx('01 00 03 32 04 03 02 01 44 33 22 11 00 01 02 03 04 05 06 07 08 09 0a 0b 0c 0d 0e 0f 10 11 12 13 14 15 16 17 18 19 1a 1b 1c 1d 1e 1f 08 07 06 05 04 03 02 01 01 00 a7 93'),
        hx('02 01 0b 03 32 04 03 02 01 44 33 22 11 29 01 02 03 04 05 06 07 08 09 0a 0b 0c 0d 0e 0f 10 11 12 13 14 15 16 17 18 19 1a 1b 1c 1d 1e 1f 08 07 06 05 04 03 02 01 01 03 a7 93 00'),
        ConfigStatusPacket(0x01020304, 0x11223344, bytes(range(32)), 0x0102030405060708, 0x01, 0x00), id='v3_config_status_accepted'),
    pytest.param('V4 CONFIG_STATUS_HASH_MISMATCH', MESSAGE_CONFIG,
        hx('05 03 02 01 44 33 22 11 00 01 02 03 04 05 06 07 08 09 0a 0b 0c 0d 0e 0f 10 11 12 13 14 15 16 17 18 19 1a 1b 1c 1d 1e 1f 08 07 06 05 04 03 02 01 02 01'),
        hx('01 00 03 32 05 03 02 01 44 33 22 11 00 01 02 03 04 05 06 07 08 09 0a 0b 0c 0d 0e 0f 10 11 12 13 14 15 16 17 18 19 1a 1b 1c 1d 1e 1f 08 07 06 05 04 03 02 01 02 01 a3 c4'),
        hx('02 01 0b 03 32 05 03 02 01 44 33 22 11 2c 01 02 03 04 05 06 07 08 09 0a 0b 0c 0d 0e 0f 10 11 12 13 14 15 16 17 18 19 1a 1b 1c 1d 1e 1f 08 07 06 05 04 03 02 01 02 01 a3 c4 00'),
        ConfigStatusPacket(0x01020305, 0x11223344, bytes(range(32)), 0x0102030405060708, 0x02, 0x01), id='v4_config_status_hash_mismatch'),
    pytest.param('V5 CONFIG_STATUS_LOCAL_CONFIG_INVALID', MESSAGE_CONFIG,
        hx('06 03 02 01 44 33 22 11 00 01 02 03 04 05 06 07 08 09 0a 0b 0c 0d 0e 0f 10 11 12 13 14 15 16 17 18 19 1a 1b 1c 1d 1e 1f 08 07 06 05 04 03 02 01 02 02'),
        hx('01 00 03 32 06 03 02 01 44 33 22 11 00 01 02 03 04 05 06 07 08 09 0a 0b 0c 0d 0e 0f 10 11 12 13 14 15 16 17 18 19 1a 1b 1c 1d 1e 1f 08 07 06 05 04 03 02 01 02 02 5a c2'),
        hx('02 01 0b 03 32 06 03 02 01 44 33 22 11 2c 01 02 03 04 05 06 07 08 09 0a 0b 0c 0d 0e 0f 10 11 12 13 14 15 16 17 18 19 1a 1b 1c 1d 1e 1f 08 07 06 05 04 03 02 01 02 02 5a c2 00'),
        ConfigStatusPacket(0x01020306, 0x11223344, bytes(range(32)), 0x0102030405060708, 0x02, 0x02), id='v5_config_status_local_config_invalid'),
    pytest.param('V6 TELEMETRY', MESSAGE_TELEMETRY,
        hx('0d 0c 0b 0a 08 07 06 05 04 03 02 01 44 33 22 11 07 06 05 04 03 02 01 00 15 cd 5b 07 00 00 00 00 d6 ff ff ff ff ff ff ff ea 16 b0 4c 02 00 00 00 16 e9 4f b3 fd ff ff ff 40 30 20 10 02 08 00 00 01'),
        hx('01 00 02 41 0d 0c 0b 0a 08 07 06 05 04 03 02 01 44 33 22 11 07 06 05 04 03 02 01 00 15 cd 5b 07 00 00 00 00 d6 ff ff ff ff ff ff ff ea 16 b0 4c 02 00 00 00 16 e9 4f b3 fd ff ff ff 40 30 20 10 02 08 00 00 01 dd 12'),
        hx('02 01 1a 02 41 0d 0c 0b 0a 08 07 06 05 04 03 02 01 44 33 22 11 07 06 05 04 03 02 01 05 15 cd 5b 07 01 01 01 0e d6 ff ff ff ff ff ff ff ea 16 b0 4c 02 01 01 0f 16 e9 4f b3 fd ff ff ff 40 30 20 10 02 08 01 04 01 dd 12 00'),
        TelemetryPacket(0x0A0B0C0D, 0x0102030405060708, 0x11223344, 0x0001020304050607, 123456789, -42, 9876543210, -9876543210, 0x10203040, 2050, 0x01), id='v6_telemetry'),
)


@pytest.mark.parametrize('name,message_type,payload,raw,wire,expected_packet', VALID_VECTORS)
def test_golden_vector_encode_and_decode(name, message_type, payload, raw, wire, expected_packet) -> None:
    del name
    assert build_raw_frame(message_type, payload) == raw
    assert build_wire_frame(message_type, payload) == wire
    decoded = decode_frame(wire)
    assert decoded.raw_frame == raw
    assert decoded.payload == payload
    assert parse_typed_packet(decoded) == expected_packet


@pytest.mark.parametrize('name,message_type,payload,raw,wire,expected_packet', VALID_VECTORS)
def test_dataclass_serialization_matches_golden_vector_bytes(
    name, message_type, payload, raw, wire, expected_packet
) -> None:
    """Exercise each packet dataclass, not only literal payload input."""
    del name
    serialized_message_type, serialized_payload = serialize_packet(expected_packet)
    assert serialized_message_type == message_type
    assert serialized_payload == payload
    assert build_raw_frame(serialized_message_type, serialized_payload) == raw
    assert build_wire_frame(serialized_message_type, serialized_payload) == wire
