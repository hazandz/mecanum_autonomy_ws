from unittest.mock import Mock

from mecanum_base_bridge.command_semantics import CommandSemantics
from mecanum_base_bridge.protocol_constants import MAX_WIRE_FRAME_LENGTH
from mecanum_base_bridge.uart_rx_diagnostic import UartRxDiagnostic
from mecanum_base_bridge.uart_rx_state import UartRxState


def hx(value: str) -> bytes:
    return bytes.fromhex(value)


V1_COMMAND = hx(
    '02 01 0b 01 14 40 30 20 10 44 33 22 11 01 03 a0 3f '
    '01 01 02 bf 01 05 40 3f 30 6e 00'
)
V2_CONFIG_REQUEST = hx(
    '02 01 0b 03 28 04 03 02 01 44 33 22 11 22 01 02 03 '
    '04 05 06 07 08 09 0a 0b 0c 0d 0e 0f 10 11 12 13 14 '
    '15 16 17 18 19 1a 1b 1c 1d 1e 1f 7b e7 00'
)
V6_TELEMETRY = hx(
    '02 01 1a 02 41 0d 0c 0b 0a 08 07 06 05 04 03 02 01 '
    '44 33 22 11 07 06 05 04 03 02 01 05 15 cd 5b 07 01 '
    '01 01 0e d6 ff ff ff ff ff ff ff ea 16 b0 4c 02 01 01 '
    '0f 16 e9 4f b3 fd ff ff ff 40 30 20 10 02 08 01 04 01 '
    'dd 12 00'
)
INVALID_FRAMES = (
    ('cobs_drop_count', hx('02 00')),
    ('crc_drop_count', hx(
        '02 01 0b 01 14 40 30 20 10 44 33 22 11 01 03 a0 3f '
        '01 01 02 bf 01 05 40 3f 31 6e 00')),
    ('payload_length_drop_count', hx(
        '02 01 0b 01 13 40 30 20 10 44 33 22 11 01 03 a0 3f '
        '01 01 02 bf 01 05 40 3f b0 67 00')),
    ('protocol_version_drop_count', hx(
        '02 02 0b 01 14 40 30 20 10 44 33 22 11 01 03 a0 3f '
        '01 01 02 bf 01 05 40 3f 35 37 00')),
    ('message_type_drop_count', hx(
        '02 01 0b 7f 14 40 30 20 10 44 33 22 11 01 03 a0 3f '
        '01 01 02 bf 01 05 40 3f d3 4e 00')),
)


def assert_v6_metadata(diagnostic: UartRxDiagnostic) -> None:
    snapshot = diagnostic.snapshot
    assert snapshot.state == UartRxState.WAITING_FOR_VALID_TELEMETRY
    assert snapshot.valid_telemetry_count == 1
    assert snapshot.telemetry_sequence == 0x0A0B0C0D
    assert snapshot.mcu_boot_id == 0x0102030405060708
    assert snapshot.reset_epoch == 0x11223344
    assert snapshot.mcu_monotonic_time_us == 0x0001020304050607


def test_v6_telemetry_whole_frame_updates_only_telemetry_diagnostic() -> None:
    diagnostic = UartRxDiagnostic()

    returned = diagnostic.feed_bytes(V6_TELEMETRY)

    assert returned == diagnostic.snapshot
    assert diagnostic.snapshot.total_bytes == len(V6_TELEMETRY)
    assert diagnostic.snapshot.complete_frame_count == 1
    assert_v6_metadata(diagnostic)


def test_v6_telemetry_handles_arbitrary_chunks_and_separate_delimiter() -> None:
    diagnostic = UartRxDiagnostic()

    diagnostic.feed_bytes(V6_TELEMETRY[:7])
    diagnostic.feed_bytes(V6_TELEMETRY[7:-1])
    assert diagnostic.snapshot.complete_frame_count == 0
    diagnostic.feed_bytes(V6_TELEMETRY[-1:])

    assert_v6_metadata(diagnostic)


def test_multiple_complete_frames_in_one_chunk_are_processed() -> None:
    diagnostic = UartRxDiagnostic()

    diagnostic.feed_bytes(V6_TELEMETRY + V6_TELEMETRY)

    assert diagnostic.snapshot.complete_frame_count == 2
    assert diagnostic.snapshot.valid_telemetry_count == 2
    assert diagnostic.snapshot.telemetry_sequence == 0x0A0B0C0D


def test_i1_to_i5_drop_then_v6_is_still_accepted() -> None:
    diagnostic = UartRxDiagnostic()

    diagnostic.feed_bytes(b''.join(frame for _counter, frame in INVALID_FRAMES) + V6_TELEMETRY)

    snapshot = diagnostic.snapshot
    assert snapshot.complete_frame_count == 6
    for counter_name, _frame in INVALID_FRAMES:
        assert getattr(snapshot, counter_name) == 1
    assert_v6_metadata(diagnostic)


def test_valid_command_and_config_are_diagnostic_drops_without_semantic_gate(monkeypatch) -> None:
    semantic_handler_spy = Mock(wraps=CommandSemantics.handle_command)
    monkeypatch.setattr(CommandSemantics, 'handle_command', semantic_handler_spy)
    diagnostic = UartRxDiagnostic()

    diagnostic.feed_bytes(V1_COMMAND + V2_CONFIG_REQUEST)

    snapshot = diagnostic.snapshot
    assert semantic_handler_spy.call_count == 0
    assert snapshot.complete_frame_count == 2
    assert snapshot.command_frame_drop_count == 1
    assert snapshot.config_frame_drop_count == 1
    assert snapshot.valid_telemetry_count == 0


def test_oversize_accumulator_drops_until_delimiter_then_recovers_with_v6() -> None:
    diagnostic = UartRxDiagnostic()

    diagnostic.feed_bytes(b'\x01' * MAX_WIRE_FRAME_LENGTH)
    assert diagnostic.snapshot.state == UartRxState.TRANSPORT_FAULT
    assert diagnostic.snapshot.oversize_drop_count == 1
    assert diagnostic.snapshot.complete_frame_count == 0

    diagnostic.feed_bytes(b'\x99\x00')
    assert diagnostic.snapshot.complete_frame_count == 0
    diagnostic.feed_bytes(V6_TELEMETRY)

    assert_v6_metadata(diagnostic)


def test_rx_diagnostic_exposes_no_tx_or_motor_control_api() -> None:
    prohibited_api_names = {
        'open', 'close', 'send', 'transmit', 'write', 'command', 'enable_motor',
    }
    assert prohibited_api_names.isdisjoint(vars(UartRxDiagnostic))
