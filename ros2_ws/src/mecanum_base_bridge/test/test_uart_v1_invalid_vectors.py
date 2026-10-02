import math
from unittest.mock import Mock

import pytest

from mecanum_base_bridge.cobs_codec import CobsDecodeError
from mecanum_base_bridge.command_semantics import CommandSemantics
from mecanum_base_bridge.uart_v1_codec import (
    CrcMismatchError,
    FrameTooLargeError,
    MessageTypeError,
    PayloadLengthError,
    ProtocolVersionError,
    decode_frame,
    parse_command,
)


def hx(value: str) -> bytes:
    return bytes.fromhex(value)


BASELINE_SEQUENCE = 0x10203040
CONFIGURED_EPOCH = 0x11223344


def assert_no_command_side_effects(session: CommandSemantics) -> None:
    assert session.last_accepted_command_sequence == BASELINE_SEQUENCE
    assert session.last_watchdog_refresh_requested is False
    assert session.last_config_status_response is None


def run_command_pipeline(wire: bytes, session: CommandSemantics):
    """Test-only pipeline: complete wire bytes through semantic decision."""
    command = parse_command(decode_frame(wire).payload)
    return command, session.handle_command(command)


@pytest.mark.parametrize(
    'name,wire,error_type',
    (
        pytest.param(
            'I1 CRC wrong',
            hx('02 01 0b 01 14 40 30 20 10 44 33 22 11 01 03 a0 3f 01 01 02 bf 01 05 40 3f 31 6e 00'),
            CrcMismatchError,
            id='i1_crc_wrong',
        ),
        pytest.param('I2 malformed COBS', hx('02 00'), CobsDecodeError, id='i2_malformed_cobs'),
        pytest.param(
            'I3 payload length mismatch',
            hx('02 01 0b 01 13 40 30 20 10 44 33 22 11 01 03 a0 3f 01 01 02 bf 01 05 40 3f b0 67 00'),
            PayloadLengthError,
            id='i3_payload_length_mismatch',
        ),
        pytest.param(
            'I4 unsupported protocol version',
            hx('02 02 0b 01 14 40 30 20 10 44 33 22 11 01 03 a0 3f 01 01 02 bf 01 05 40 3f 35 37 00'),
            ProtocolVersionError,
            id='i4_unsupported_protocol_version',
        ),
        pytest.param(
            'I5 unknown message type',
            hx('02 01 0b 7f 14 40 30 20 10 44 33 22 11 01 03 a0 3f 01 01 02 bf 01 05 40 3f d3 4e 00'),
            MessageTypeError,
            id='i5_unknown_message_type',
        ),
    ),
)
def test_invalid_codec_vectors_drop_without_semantic_side_effects(
    name, wire, error_type, monkeypatch
) -> None:
    del name
    session = CommandSemantics(CONFIGURED_EPOCH, BASELINE_SEQUENCE)
    semantic_handler_spy = Mock(wraps=session.handle_command)
    monkeypatch.setattr(session, 'handle_command', semantic_handler_spy)

    with pytest.raises(error_type):
        run_command_pipeline(wire, session)

    semantic_handler_spy.assert_not_called()
    assert_no_command_side_effects(session)


@pytest.mark.parametrize(
    'name,wire,expected_reason',
    (
        pytest.param(
            'I6 COMMAND NaN',
            hx('02 01 0b 01 14 41 30 20 10 44 33 22 11 01 03 c0 7f 01 01 02 bf 01 05 40 3f 4d 4f 00'),
            'non_finite_command',
            id='i6_command_nan',
        ),
        pytest.param(
            'I7 duplicate sequence',
            hx('02 01 0b 01 14 40 30 20 10 44 33 22 11 01 03 a0 3f 01 01 02 bf 01 05 40 3f 30 6e 00'),
            'duplicate_or_backward_sequence',
            id='i7_duplicate_sequence',
        ),
        pytest.param(
            'I8 backward sequence',
            hx('02 01 0b 01 14 3f 30 20 10 44 33 22 11 01 03 a0 3f 01 01 02 bf 01 05 40 3f 08 5b 00'),
            'duplicate_or_backward_sequence',
            id='i8_backward_sequence',
        ),
        pytest.param(
            'I9 wrong reset epoch',
            hx('02 01 0b 01 14 41 30 20 10 45 33 22 11 01 03 a0 3f 01 01 02 bf 01 05 40 3f a7 f3 00'),
            'wrong_reset_epoch',
            id='i9_wrong_reset_epoch',
        ),
    ),
)
def test_invalid_command_semantics_have_no_acceptance_side_effects(
    name, wire, expected_reason
) -> None:
    del name
    session = CommandSemantics(CONFIGURED_EPOCH, BASELINE_SEQUENCE)
    command, decision = run_command_pipeline(wire, session)
    assert decision.accepted is False
    assert decision.watchdog_refresh_requested is False
    assert decision.config_status_response is None
    assert decision.reason == expected_reason
    assert_no_command_side_effects(session)
    if expected_reason == 'non_finite_command':
        assert math.isnan(command.vx_mps)


def test_valid_command_pipeline_accepts_v1_and_refreshes_only_test_signal() -> None:
    wire = hx(
        '02 01 0b 01 14 40 30 20 10 44 33 22 11 01 03 a0 3f '
        '01 01 02 bf 01 05 40 3f 30 6e 00'
    )
    session = CommandSemantics(CONFIGURED_EPOCH, 0x1020303F)

    command, decision = run_command_pipeline(wire, session)

    assert command.command_sequence == 0x10203040
    assert decision.accepted is True
    assert decision.watchdog_refresh_requested is True
    assert decision.config_status_response is None
    assert session.last_accepted_command_sequence == 0x10203040


def test_wire_frame_over_98_bytes_is_rejected_safely() -> None:
    oversized_wire = (b'\x01' * 98) + b'\x00'
    with pytest.raises(FrameTooLargeError):
        decode_frame(oversized_wire)


def test_decoded_raw_frame_over_96_bytes_is_rejected_safely(monkeypatch) -> None:
    """Exercise the post-COBS raw-storage guard independently of wire storage.

    A naturally encoded raw frame longer than 96 bytes is also longer than the
    98-byte wire limit, so the wire guard rejects it first. This test injects a
    decoded 97-byte raw result to verify the required second fail-closed guard.
    """
    import mecanum_base_bridge.uart_v1_codec as codec

    monkeypatch.setattr(codec, 'cobs_decode', lambda _encoded: b'\x01' * 97)
    with pytest.raises(FrameTooLargeError):
        codec.decode_frame(b'\x01\x00')
