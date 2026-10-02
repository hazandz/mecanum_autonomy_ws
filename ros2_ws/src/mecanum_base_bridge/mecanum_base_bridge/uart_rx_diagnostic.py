"""Phase B RX-only byte accumulator and UART v1 telemetry diagnostic.

This module has no serial-port, ROS, transmit, command-session, odometry, or
motor-control behavior. A future byte source may pass chunks to feed_bytes().
"""

from dataclasses import replace

from .cobs_codec import CobsDecodeError
from .protocol_constants import MAX_WIRE_FRAME_LENGTH, WIRE_DELIMITER
from .uart_rx_state import UartRxDiagnosticSnapshot, UartRxState
from .uart_v1_codec import (
    CommandPacket,
    CrcMismatchError,
    FrameTooLargeError,
    MessageTypeError,
    PayloadLengthError,
    ProtocolVersionError,
    TelemetryPacket,
    WireFrameError,
    decode_frame,
    parse_typed_packet,
)


class UartRxDiagnostic:
    """Safely decode only complete delimiter-terminated UART v1 frames."""

    def __init__(self) -> None:
        self._accumulator = bytearray()
        self._discard_until_delimiter = False
        self._snapshot = UartRxDiagnosticSnapshot()

    @property
    def snapshot(self) -> UartRxDiagnosticSnapshot:
        """Return the immutable current diagnostic snapshot."""
        return self._snapshot

    def feed_bytes(self, chunk: bytes) -> UartRxDiagnosticSnapshot:
        """Consume arbitrary received bytes without raising for frame failures.

        The accumulator holds COBS bytes excluding the delimiter. If it reaches
        the 98-byte delimiter-inclusive wire limit, this module drops all bytes
        through the next delimiter so no fragment can be partially parsed.
        """
        if not isinstance(chunk, bytes):
            raise TypeError('RX diagnostic accepts bytes chunks only')

        if chunk and self._snapshot.state == UartRxState.DISCONNECTED:
            self._snapshot = replace(
                self._snapshot, state=UartRxState.WAITING_FOR_VALID_TELEMETRY
            )
        self._snapshot = replace(
            self._snapshot, total_bytes=self._snapshot.total_bytes + len(chunk)
        )

        for value in chunk:
            if self._discard_until_delimiter:
                if value == WIRE_DELIMITER:
                    self._discard_until_delimiter = False
                continue

            if value == WIRE_DELIMITER:
                self._handle_delimiter()
                continue

            # The delimiter itself requires one of the 98 wire-buffer bytes.
            if len(self._accumulator) >= MAX_WIRE_FRAME_LENGTH - 1:
                self._accumulator.clear()
                self._discard_until_delimiter = True
                self._snapshot = replace(
                    self._snapshot,
                    state=UartRxState.TRANSPORT_FAULT,
                    oversize_drop_count=self._snapshot.oversize_drop_count + 1,
                )
                continue

            self._accumulator.append(value)

        return self._snapshot

    def _handle_delimiter(self) -> None:
        if not self._accumulator:
            return

        wire_frame = bytes(self._accumulator) + bytes((WIRE_DELIMITER,))
        self._accumulator.clear()
        self._snapshot = replace(
            self._snapshot,
            complete_frame_count=self._snapshot.complete_frame_count + 1,
        )

        try:
            packet = parse_typed_packet(decode_frame(wire_frame))
        except CobsDecodeError:
            self._increment_drop('cobs_drop_count')
            return
        except CrcMismatchError:
            self._increment_drop('crc_drop_count')
            return
        except ProtocolVersionError:
            self._increment_drop('protocol_version_drop_count')
            return
        except MessageTypeError:
            self._increment_drop('message_type_drop_count')
            return
        except (PayloadLengthError, WireFrameError):
            self._increment_drop('payload_length_drop_count')
            return
        except FrameTooLargeError:
            self._increment_drop('oversize_drop_count')
            return

        if isinstance(packet, TelemetryPacket):
            self._snapshot = replace(
                self._snapshot,
                state=UartRxState.WAITING_FOR_VALID_TELEMETRY,
                valid_telemetry_count=self._snapshot.valid_telemetry_count + 1,
                telemetry_sequence=packet.telemetry_sequence,
                mcu_boot_id=packet.mcu_boot_id,
                reset_epoch=packet.reset_epoch,
                mcu_monotonic_time_us=packet.mcu_monotonic_time_us,
            )
        elif isinstance(packet, CommandPacket):
            self._increment_drop('command_frame_drop_count')
        else:
            self._increment_drop('config_frame_drop_count')

    def _increment_drop(self, field_name: str) -> None:
        self._snapshot = replace(
            self._snapshot,
            **{field_name: getattr(self._snapshot, field_name) + 1},
        )
