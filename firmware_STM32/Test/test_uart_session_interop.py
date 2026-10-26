#!/usr/bin/env python3
"""Transcript ngoại tuyến giữa Pi engine và C runtime native; telemetry là dữ liệu tổng hợp."""

from collections import deque
import importlib.util
import os
from pathlib import Path
import selectors
import subprocess
import sys
import time

from mecanum_base_bridge.bridge_session import BridgeSession, LifecycleIdentity, SessionState
from mecanum_base_bridge.hardware_config import load_manifest, manifest_digest
from mecanum_base_bridge.protocol_constants import MESSAGE_CONFIG, MESSAGE_TELEMETRY
from mecanum_base_bridge.uart_v1_codec import (
    TelemetryPacket, build_wire_frame, decode_frame, serialize_telemetry,
)


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / 'artifacts/hardware/mecanum_f411_tb6612_ga25_370_rev_a/hardware_manifest.yaml'
SAFETY_LIFECYCLE_SOURCE = ROOT / 'ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/runtime_safety/safety_contract.py'


def _lifecycle_core():
    spec = importlib.util.spec_from_file_location('u4_interop_safety_contract', SAFETY_LIFECYCLE_SOURCE)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.SafetyLifecycleCore


def _owner_identity(snapshot):
    return LifecycleIdentity(snapshot.reset_epoch, snapshot.runtime_generation,
                             snapshot.motion_permitted, snapshot.sequence, True)


class Clock:
    def __init__(self): self.value = 0.0
    def __call__(self): return self.value


class FakeTransport:
    def __init__(self): self.is_open = False; self.rx = deque(); self.writes = []
    def open(self): self.is_open = True; return True
    def close(self): self.is_open = False
    def read(self, max_bytes=256):
        result = bytearray()
        while self.rx and len(result) < max_bytes: result.append(self.rx.popleft())
        return bytes(result)
    def write(self, frame): self.writes.append(bytes(frame)); return len(frame)
    def inject(self, data): self.rx.extend(data)


def _read_line(process, timeout=2.0):
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ)
    deadline = time.monotonic() + timeout
    data = bytearray()
    try:
        while time.monotonic() < deadline:
            if selector.select(deadline - time.monotonic()):
                block = os.read(process.stdout.fileno(), 4096)
                if not block:
                    raise AssertionError(f'C peer closed stdout: {process.poll()}')
                data.extend(block)
                if b'\n' in data:
                    line, _, _ = data.partition(b'\n')
                    return line.decode('ascii')
        raise AssertionError('native C peer exceeded bounded 2 s response timeout')
    finally:
        selector.close()


def _send(process, tick, frame):
    process.stdin.write(f'{tick} {frame.hex()}\n'.encode('ascii'))
    process.stdin.flush()
    line = _read_line(process)
    assert line.startswith('RESULT '), line
    fields = dict(part.split('=', 1) for part in line.split()[1:])
    return fields


def test_python_session_and_actual_c_runtime_interoperate():
    peer = os.environ.get('WP07_U4_INTEROP_PEER')
    assert peer and Path(peer).is_file(), 'CTest/acceptance must provide the native C peer executable'
    digest = manifest_digest(load_manifest(MANIFEST))
    child_env = os.environ.copy()
    asan = child_env.get('ASAN_OPTIONS', '')
    if 'detect_leaks=' not in asan:
        asan = f'{asan}:detect_leaks=0' if asan else 'detect_leaks=0'
    child_env['ASAN_OPTIONS'] = asan
    proc = subprocess.Popen([peer, '--interop', digest.hex(), '123'],
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, bufsize=0, env=child_env)
    try:
        assert _read_line(proc) == 'READY'
        clock, transport = Clock(), FakeTransport()
        pi = BridgeSession(transport, digest, clock)
        core = _lifecycle_core()()
        core.configure(1)
        baseline = core.activate(2)
        assert pi.start()
        pi.observe_lifecycle_snapshot(_owner_identity(baseline))
        reset = core.begin_reset(3)
        assert not reset.motion_permitted and reset.reset_epoch == 1
        assert pi.confirm_owner_reset(_owner_identity(reset))
        config_wire = transport.writes[-1]
        assert decode_frame(config_wire).message_type == MESSAGE_CONFIG
        result = _send(proc, 100, config_wire)
        assert result['configured'] == '1' and result['telemetry'] == '1'
        status_wire = bytes.fromhex(result['tx'])
        assert decode_frame(status_wire).message_type == MESSAGE_CONFIG
        # Bỏ telemetry đến trước status; CONFIG_STATUS đơn lẻ cũng chưa kích hoạt.
        transport.inject(build_wire_frame(MESSAGE_TELEMETRY, serialize_telemetry(
            TelemetryPacket(1, int(result['boot']), int(result['epoch']), 100,
                            0, 0, 0, 0, 0, 0, 0))))
        clock.value = 0.001
        pi.io_once()
        assert pi.state == SessionState.CONFIGURING
        transport.inject(status_wire)
        clock.value = 0.002
        pi.io_once()
        assert pi.state == SessionState.CONFIGURING  # CONFIG_STATUS đơn lẻ chưa đủ

        # Telemetry tổng hợp chỉ dùng test, dựa trên snapshot fixture của C peer.
        # U4 chưa có telemetry producer trong firmware.
        transport.inject(build_wire_frame(MESSAGE_TELEMETRY, serialize_telemetry(
            TelemetryPacket(1, int(result['boot']), int(result['epoch']), 101,
                            0, 0, 0, 0, 0, 0, 0))))
        clock.value = 0.003
        pi.io_once()
        assert pi.state == SessionState.ACTIVE
        assert not pi.receive_cmd_vel(0.2, -0.1, 0.3, received_at=0.003)
        ready = core.rearm(4)
        pi.observe_lifecycle_snapshot(_owner_identity(ready))
        clock.value = 0.004
        assert pi.receive_cmd_vel(0.2, -0.1, 0.3, received_at=clock.value)
        pi.io_once()
        command_wire = transport.writes[-1]
        result = _send(proc, 103, command_wire)
        assert result['accepted'] == '1' and result['configured'] == '1'
        assert result['faults'] == '0'

        # Gửi lặp là fixture âm tường minh, không phải hành vi retry của Pi.
        duplicate = _send(proc, 104, command_wire)
        assert duplicate['accepted'] == '1'
        assert int(duplicate['faults']) & 512
        assert duplicate['tx'] == '-'
        proc.stdin.close()
        return_code = proc.wait(timeout=2.0)
        error_text = proc.stderr.read().decode('utf-8', errors='replace')
        assert return_code == 0, error_text
    finally:
        if proc.poll() is None:
            proc.kill(); proc.wait(timeout=1.0)
