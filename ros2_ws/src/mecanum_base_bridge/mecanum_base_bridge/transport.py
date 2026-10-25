"""Bounded, offline-testable serial byte transport for Pi--STM32 UART v1.

This layer owns one pyserial handle. It deliberately does not frame, parse,
buffer, retry, or interpret protocol/session state.
"""

from __future__ import annotations

import time
from typing import Callable, Optional

import serial

from .protocol_constants import MAX_WIRE_FRAME_LENGTH


_READ_LIMIT = 512
_RECONNECT_DELAY_SECONDS = 1.0
_WRITE_TIMEOUT_SECONDS = 0.020


class SerialTransport:
    """A single-owner serial port with bounded reads and writes.

    ``open`` returns ``False`` when reconnect backoff has not elapsed and
    ``True`` when a handle is open. A failed open raises the original backend
    exception. Only an explicit later call to ``open`` can reconnect.
    """

    def __init__(
        self,
        port: str,
        *,
        serial_factory: Optional[Callable[..., object]] = None,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        if not isinstance(port, str) or not port.strip():
            raise ValueError('port must be a non-empty string')
        self.port = port
        self._serial_factory = serial_factory or serial.Serial
        self._monotonic = monotonic
        self._handle = None
        self._retry_after = None

    @property
    def is_open(self) -> bool:
        """Whether the current serial handle reports itself open."""
        return self._handle is not None and bool(self._handle.is_open)

    def open(self) -> bool:
        """Open once, unless closed/error backoff is still active."""
        if self.is_open:
            return True
        now = self._monotonic()
        if self._retry_after is not None and now < self._retry_after:
            return False

        settings = {
            'port': self.port,
            'baudrate': 115200,
            'bytesize': serial.EIGHTBITS,
            'parity': serial.PARITY_NONE,
            'stopbits': serial.STOPBITS_ONE,
            'xonxoff': False,
            'rtscts': False,
            'dsrdtr': False,
            'timeout': 0,
            'write_timeout': _WRITE_TIMEOUT_SECONDS,
            'exclusive': True,
        }
        handle = None
        try:
            handle = self._serial_factory(**settings)
            for name, expected in settings.items():
                actual = getattr(handle, name)
                if actual != expected:
                    raise serial.SerialException(
                        f'serial backend did not apply {name}={expected!r}'
                    )
            if not handle.is_open:
                raise serial.SerialException('serial backend returned a closed port')
        except Exception:
            self._retry_after = self._monotonic() + _RECONNECT_DELAY_SECONDS
            self._close_quietly(handle)
            raise

        self._handle = handle
        self._retry_after = None
        return True

    def close(self) -> None:
        """Close the current handle; repeated calls are safe."""
        handle = self._handle
        self._handle = None
        if handle is None:
            return
        self._retry_after = self._monotonic() + _RECONNECT_DELAY_SECONDS
        handle.close()

    def read(self, max_bytes: int = 256) -> bytes:
        """Read one bounded chunk, returning raw bytes (or ``b''``)."""
        if isinstance(max_bytes, bool) or not isinstance(max_bytes, int):
            raise TypeError('max_bytes must be an integer')
        if not 0 <= max_bytes <= _READ_LIMIT:
            raise ValueError('max_bytes must be between 0 and 512')
        handle = self._require_open_handle()
        try:
            data = handle.read(max_bytes)
        except (serial.SerialException, OSError):
            self._invalidate_after_io_error(handle)
            raise
        if not isinstance(data, bytes):
            raise TypeError('serial backend read must return bytes')
        return data

    def write(self, frame: bytes) -> None:
        """Write exactly one caller-supplied bounded frame."""
        if not isinstance(frame, bytes):
            raise TypeError('frame must be bytes')
        if len(frame) > MAX_WIRE_FRAME_LENGTH:
            raise ValueError(
                f'frame exceeds MAX_WIRE_FRAME_LENGTH ({MAX_WIRE_FRAME_LENGTH})'
            )
        handle = self._require_open_handle()
        try:
            written = handle.write(frame)
            if written != len(frame):
                raise serial.SerialException(
                    f'short serial write: wrote {written!r} of {len(frame)} bytes'
                )
        except (serial.SerialException, OSError):
            self._invalidate_after_io_error(handle)
            raise

    def _require_open_handle(self):
        handle = self._handle
        if handle is None or not handle.is_open:
            raise serial.SerialException('serial port is not open')
        return handle

    def _invalidate_after_io_error(self, handle) -> None:
        if self._handle is handle:
            self._handle = None
        self._retry_after = self._monotonic() + _RECONNECT_DELAY_SECONDS
        self._close_quietly(handle)

    @staticmethod
    def _close_quietly(handle) -> None:
        if handle is None:
            return
        try:
            handle.close()
        except Exception:
            # Preserve the open/read/write exception that caused cleanup.
            pass
