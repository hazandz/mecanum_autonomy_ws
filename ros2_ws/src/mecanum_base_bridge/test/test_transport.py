"""Offline contract tests for the bounded Pi--STM32 serial byte transport."""

import importlib

import pytest
import serial

from mecanum_base_bridge import transport
from mecanum_base_bridge.protocol_constants import MAX_WIRE_FRAME_LENGTH


class FakeClock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class FakeSerial:
    def __init__(self, **settings):
        self.__dict__.update(settings)
        self.is_open = True
        self.read_results = []
        self.read_calls = []
        self.writes = []
        self.write_result = None
        self.write_error = None
        self.close_error = None
        self.close_calls = 0

    def read(self, size):
        self.read_calls.append(size)
        result = self.read_results.pop(0) if self.read_results else b''
        if isinstance(result, BaseException):
            raise result
        return result

    def write(self, data):
        self.writes.append(data)
        if self.write_error is not None:
            raise self.write_error
        return len(data) if self.write_result is None else self.write_result

    def close(self):
        self.close_calls += 1
        self.is_open = False
        if self.close_error is not None:
            raise self.close_error


class FakeFactory:
    def __init__(self, *results):
        self.results = list(results)
        self.calls = []

    def __call__(self, **settings):
        self.calls.append(settings)
        result = self.results.pop(0) if self.results else FakeSerial(**settings)
        if isinstance(result, BaseException):
            raise result
        for name, value in settings.items():
            if not hasattr(result, name):
                setattr(result, name, value)
        return result


def make_transport(*factory_results):
    clock = FakeClock()
    factory = FakeFactory(*factory_results)
    subject = transport.SerialTransport(
        '/dev/fake-uart', serial_factory=factory, monotonic=clock
    )
    return subject, factory, clock


def test_import_and_constructor_do_not_open_and_port_is_required(monkeypatch):
    calls = []
    monkeypatch.setattr(serial, 'Serial', lambda **kwargs: calls.append(kwargs))
    importlib.reload(transport)
    with pytest.raises(TypeError):
        transport.SerialTransport()
    with pytest.raises(ValueError):
        transport.SerialTransport('  ')
    subject = transport.SerialTransport('/dev/fake-uart')
    assert subject.is_open is False
    assert calls == []
    importlib.reload(transport)


def test_open_uses_exact_uart_settings_and_does_not_send_protocol_bytes():
    handle = FakeSerial()
    subject, factory, _ = make_transport(handle)
    assert subject.open() is True
    assert factory.calls == [{
        'port': '/dev/fake-uart',
        'baudrate': 115200,
        'bytesize': serial.EIGHTBITS,
        'parity': serial.PARITY_NONE,
        'stopbits': serial.STOPBITS_ONE,
        'xonxoff': False,
        'rtscts': False,
        'dsrdtr': False,
        'timeout': 0,
        'write_timeout': 0.020,
        'exclusive': True,
    }]
    assert subject.is_open is True
    assert handle.writes == []


def test_open_error_is_reported_and_backed_off_without_retry_loop():
    failure = serial.SerialException('open failed')
    subject, factory, clock = make_transport(failure)
    with pytest.raises(serial.SerialException) as raised:
        subject.open()
    assert raised.value is failure
    assert len(factory.calls) == 1
    assert subject.open() is False
    assert len(factory.calls) == 1
    clock.advance(1.0)
    assert subject.open() is True
    assert len(factory.calls) == 2


def test_backend_that_does_not_apply_exclusive_setting_fails_closed():
    settings = {
        'port': '/dev/fake-uart', 'baudrate': 115200,
        'bytesize': serial.EIGHTBITS, 'parity': serial.PARITY_NONE,
        'stopbits': serial.STOPBITS_ONE, 'xonxoff': False, 'rtscts': False,
        'dsrdtr': False, 'timeout': 0, 'write_timeout': 0.020,
        'exclusive': True,
    }
    handle = FakeSerial(**settings)
    handle.exclusive = False
    subject, _, _ = make_transport(handle)
    with pytest.raises(serial.SerialException, match='exclusive'):
        subject.open()
    assert handle.is_open is False
    assert subject.is_open is False


def test_read_returns_raw_chunks_empty_bytes_and_enforces_bound():
    handle = FakeSerial()
    handle.read_results = [b'\x01\x00\xff', b'', b'next']
    subject, _, _ = make_transport(handle)
    subject.open()
    assert subject.read() == b'\x01\x00\xff'
    assert subject.read(max_bytes=512) == b''
    assert subject.read(4) == b'next'
    assert handle.read_calls == [256, 512, 4]
    for invalid in (-1, 513):
        with pytest.raises(ValueError):
            subject.read(invalid)
    with pytest.raises(TypeError):
        subject.read(True)
    assert handle.read_calls == [256, 512, 4]


def test_write_preserves_exact_bytes_including_zero_and_has_wire_bound():
    handle = FakeSerial()
    subject, _, _ = make_transport(handle)
    subject.open()
    frame = b'\x11\x00\x22\x00'
    subject.write(frame)
    assert handle.writes == [frame]
    subject.write(bytes(MAX_WIRE_FRAME_LENGTH))
    assert handle.writes[-1] == bytes(MAX_WIRE_FRAME_LENGTH)
    with pytest.raises(ValueError):
        subject.write(bytes(MAX_WIRE_FRAME_LENGTH + 1))
    with pytest.raises(TypeError):
        subject.write(bytearray(b'abc'))


@pytest.mark.parametrize('write_error', [
    None,
    serial.SerialTimeoutException('write timed out'),
])
def test_short_write_and_write_timeout_close_handle_and_do_not_replay(write_error):
    handle = FakeSerial()
    subject, _, clock = make_transport(handle)
    subject.open()
    if write_error is None:
        handle.write_result = 1
        with pytest.raises(serial.SerialException, match='short serial write'):
            subject.write(b'frame')
    else:
        handle.write_error = write_error
        with pytest.raises(serial.SerialTimeoutException) as raised:
            subject.write(b'frame')
        assert raised.value is write_error
    assert handle.close_calls == 1
    assert subject.is_open is False
    clock.advance(1.0)
    assert subject.open() is True
    assert len(handle.writes) == 1


def test_read_error_preserves_original_when_cleanup_also_fails():
    failure = OSError('read failed')
    old_handle = FakeSerial()
    old_handle.read_results = [failure]
    old_handle.close_error = RuntimeError('cleanup failed')
    new_handle = FakeSerial()
    subject, factory, clock = make_transport(old_handle, new_handle)
    subject.open()
    with pytest.raises(OSError) as raised:
        subject.read()
    assert raised.value is failure
    assert subject.is_open is False
    assert old_handle.close_calls == 1
    clock.advance(1.0)
    assert subject.open() is True
    assert subject.read() == b''
    assert len(factory.calls) == 2
    assert new_handle.read_calls == [256]


def test_close_is_idempotent_and_enforces_reconnect_delay_with_new_handle():
    first = FakeSerial()
    second = FakeSerial()
    subject, factory, clock = make_transport(first, second)
    assert subject.open() is True
    subject.close()
    subject.close()
    assert first.close_calls == 1
    assert subject.open() is False
    assert len(factory.calls) == 1
    clock.advance(0.999)
    assert subject.open() is False
    assert len(factory.calls) == 1
    clock.advance(0.001)
    assert subject.open() is True
    assert len(factory.calls) == 2
    assert subject.is_open is True
    assert first.writes == [] and second.writes == []


def test_reopen_failure_after_backoff_has_one_attempt_and_no_old_bytes():
    first = FakeSerial()
    first.read_results = [serial.SerialException('disconnect')]
    failure = serial.SerialException('reopen failed')
    subject, factory, clock = make_transport(first, failure)
    subject.open()
    with pytest.raises(serial.SerialException, match='disconnect'):
        subject.read()
    clock.advance(1.0)
    with pytest.raises(serial.SerialException) as raised:
        subject.open()
    assert raised.value is failure
    assert len(factory.calls) == 2
    assert subject.open() is False
    assert len(factory.calls) == 2
    assert first.writes == []


def test_closed_transport_rejects_io_without_opening_or_replay():
    subject, factory, _ = make_transport()
    with pytest.raises(serial.SerialException, match='not open'):
        subject.read()
    with pytest.raises(serial.SerialException, match='not open'):
        subject.write(b'caller bytes')
    assert factory.calls == []
