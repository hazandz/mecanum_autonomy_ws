"""Offline tests for the one-shot CONFIG-only bench harness."""

from __future__ import annotations

from pathlib import Path
import subprocess

import pytest

from mecanum_base_bridge import uart_config_only_bench as bench
from mecanum_base_bridge.protocol_constants import (
    CONFIG_ACCEPTED,
    ESTOP_AUX_UNKNOWN,
    MESSAGE_CONFIG,
    MESSAGE_TELEMETRY,
    REJECT_NONE,
)
from mecanum_base_bridge.uart_v1_codec import (
    ConfigStatusPacket,
    TelemetryPacket,
    build_wire_frame,
    cobs_encode,
    decode_frame,
    parse_config_request,
    serialize_config_status,
    serialize_telemetry,
)


ROOT = Path(__file__).resolve().parents[4]
MANIFEST = ROOT / "artifacts/hardware/mecanum_f411_tb6612_ga25_370_rev_a/hardware_manifest.yaml"


class FakeClock:
    def __init__(self):
        self.now = 10.0

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


class FakeTransport:
    def __init__(self, post_tx=(), pre_tx=(), read_error=None, write_error=None):
        self.post_tx = list(post_tx)
        self.pre_tx = list(pre_tx)
        self.read_error = read_error
        self.write_error = write_error
        self.open_calls = 0
        self.close_calls = 0
        self.writes = []

    def open(self):
        self.open_calls += 1
        return True

    def read(self, max_bytes=256):
        assert max_bytes == 256
        if self.writes:
            if self.read_error is not None:
                error, self.read_error = self.read_error, None
                raise error
            return self.post_tx.pop(0) if self.post_tx else b""
        return self.pre_tx.pop(0) if self.pre_tx else b""

    def write(self, frame):
        self.writes.append(frame)
        if self.write_error is not None:
            raise self.write_error

    def close(self):
        self.close_calls += 1


class ScheduledTransport(FakeTransport):
    """Fake nonblocking RX whose clock advances to the next scheduled packet."""

    def __init__(self, clock, events=(), *, write_delay=0.0):
        super().__init__()
        self.clock = clock
        self.events = list(events)
        self.config_sent_at = None
        self.write_delay = write_delay

    def write(self, frame):
        super().write(frame)
        self.config_sent_at = self.clock.now
        self.clock.now += self.write_delay

    def read(self, max_bytes=256):
        assert max_bytes == 256
        if not self.writes or not self.events:
            return b""
        offset, data = self.events[0]
        if self.clock.now >= self.config_sent_at + offset:
            self.events.pop(0)
            return data
        return b""


def status_frame(*, sequence=7, epoch=19, digest=None, boot=23, status=CONFIG_ACCEPTED, reject=REJECT_NONE):
    if digest is None:
        digest = bench.manifest_digest(bench.load_manifest(MANIFEST))
    return build_wire_frame(
        MESSAGE_CONFIG,
        serialize_config_status(ConfigStatusPacket(sequence, epoch, digest, boot, status, reject)),
    )


def telemetry_frame(*, sequence=0, boot=23, epoch=19, time_us=1000, ticks=(0, 0, 0, 0), ack=0, faults=0,
                    estop=ESTOP_AUX_UNKNOWN):
    packet = TelemetryPacket(sequence, boot, epoch, time_us, *ticks, ack, faults, estop)
    return build_wire_frame(MESSAGE_TELEMETRY, serialize_telemetry(packet))


def invoke(tmp_path, transport, *, clock=None, a1_window=0.01, duration=0.02, epoch=19, sequence=7,
           output_path=None, sleeper=None):
    clock = clock or FakeClock()
    if output_path is None:
        output_path = tmp_path / "evidence.json"
    return bench.run_bench(
        transport=transport,
        serial_device="/dev/fake-uart",
        manifest_path=MANIFEST,
        reset_epoch=epoch,
        config_sequence=sequence,
        duration=duration,
        a1_window=a1_window,
        output_path=output_path,
        confirm_a1_precondition=True,
        source_fingerprint={"git_commit": "test-double"},
        repository_root=ROOT,
        clock=clock,
        sleeper=sleeper or clock.sleep,
    )


def test_waits_through_a1_then_sends_one_config_and_accepts_unknown_telemetry(tmp_path):
    transport = FakeTransport(post_tx=[status_frame(), telemetry_frame()])
    clock = FakeClock()
    evidence = invoke(tmp_path, transport, clock=clock)

    assert evidence["result"] == "observed"
    assert evidence["a1_observation"] == "no_complete_frame_observed_during_finite_window"
    assert clock.now >= 10.01
    assert transport.open_calls == 1
    assert transport.close_calls == 1
    assert len(transport.writes) == 1
    decoded = decode_frame(transport.writes[0])
    assert decoded.message_type == MESSAGE_CONFIG
    assert len(decoded.payload) == 40
    request = parse_config_request(decoded.payload)
    assert (request.config_sequence, request.reset_epoch) == (7, 19)
    assert evidence["tx_counts"] == {
        "write_attempts": 1, "write_successes": 1, "config_request_attempts": 1,
        "config_request": 1, "command": 0,
    }
    assert evidence["counter_observations"][0]["estop_aux_active"] == ESTOP_AUX_UNKNOWN
    assert evidence["counter_observations"][0]["delta_ticks"] is None


@pytest.mark.parametrize("status_kwargs, code", [
    ({"sequence": 8}, "config_sequence_mismatch"),
    ({"epoch": 20}, "config_epoch_mismatch"),
    ({"digest": b"x" * 32}, "config_hash_mismatch"),
    ({"status": 0, "reject": 1}, "config_rejected"),
    ({"boot": 0}, "invalid_boot_id"),
])
def test_rejects_mismatched_or_rejected_config_status(tmp_path, status_kwargs, code):
    transport = FakeTransport(post_tx=[status_frame(**status_kwargs)])
    evidence = invoke(tmp_path, transport)
    assert evidence["result"] == "failed"
    assert evidence["error"]["code"] == code
    assert len(transport.writes) == 1
    assert evidence["tx_counts"]["command"] == 0


def test_status_timeout_and_telemetry_timeout_are_distinct(tmp_path):
    no_status = invoke(tmp_path, FakeTransport(), duration=0.6)
    assert no_status["error"]["code"] == "config_status_timeout"
    status_only = invoke(tmp_path, FakeTransport(post_tx=[status_frame()]))
    assert status_only["error"]["code"] == "telemetry_initial_timeout"


def test_rejects_preconfig_telemetry_and_incomplete_a1_frame(tmp_path):
    early = invoke(tmp_path, FakeTransport(pre_tx=[telemetry_frame()]))
    assert early["error"]["code"] == "preconfig_telemetry_received"
    assert early["tx_counts"]["config_request"] == 0

    incomplete = invoke(tmp_path, FakeTransport(pre_tx=[b"\x01\x02"]))
    assert incomplete["error"]["code"] == "incomplete_preconfig_frame"
    assert incomplete["tx_counts"]["config_request"] == 0

    empty_frame = invoke(tmp_path, FakeTransport(pre_tx=[b"\x00"]))
    assert empty_frame["error"]["code"] == "framing_error"
    assert empty_frame["tx_counts"]["config_request"] == 0


@pytest.mark.parametrize("telemetry_kwargs, code", [
    ({"boot": 24}, "telemetry_boot_id_mismatch"),
    ({"epoch": 20}, "telemetry_epoch_mismatch"),
    ({"estop": 0}, "estop_aux_not_unknown"),
    ({"ack": 1}, "unexpected_command_ack"),
    ({"faults": 1}, "mcu_fault_reported"),
    ({"faults": 1 << 31}, "reserved_fault_bits"),
])
def test_rejects_invalid_telemetry_identity_or_diagnostics(tmp_path, telemetry_kwargs, code):
    transport = FakeTransport(post_tx=[status_frame(), telemetry_frame(**telemetry_kwargs)])
    evidence = invoke(tmp_path, transport)
    assert evidence["error"]["code"] == code
    assert evidence["tx_counts"]["command"] == 0


@pytest.mark.parametrize("second, code", [
    (telemetry_frame(sequence=0, time_us=2000, ticks=(1, 0, 0, 0)), "telemetry_sequence_not_increasing"),
    (telemetry_frame(sequence=2, time_us=1000, ticks=(1, 0, 0, 0)), "telemetry_time_not_increasing"),
])
def test_rejects_duplicate_or_backward_telemetry_progress(tmp_path, second, code):
    transport = FakeTransport(post_tx=[status_frame(), telemetry_frame(), second])
    evidence = invoke(tmp_path, transport)
    assert evidence["error"]["code"] == code


def test_reports_raw_tick_delta_only_within_same_boot_and_epoch(tmp_path):
    transport = FakeTransport(post_tx=[
        status_frame(),
        telemetry_frame(sequence=4, time_us=1000, ticks=(10, 20, 30, 40)),
        telemetry_frame(sequence=5, time_us=2000, ticks=(12, 19, 35, 40)),
    ])
    evidence = invoke(tmp_path, transport, duration=0.03)
    assert evidence["result"] == "observed"
    assert evidence["counter_observations"][1]["delta_ticks"] == {"FL": 2, "FR": -1, "RL": 5, "RR": 0}


def test_allows_forward_sequence_gap_but_reports_raw_counter_delta(tmp_path):
    transport = FakeTransport(post_tx=[
        status_frame(),
        telemetry_frame(sequence=4, time_us=1000),
        telemetry_frame(sequence=6, time_us=2000, ticks=(2, 0, 0, 0)),
    ])
    evidence = invoke(tmp_path, transport, duration=0.03)
    assert evidence["result"] == "observed"
    assert evidence["counter_observations"][1]["delta_ticks"]["FL"] == 2


def test_crc_error_is_reported_and_never_retried(tmp_path):
    valid = bytearray(status_frame())
    valid[2] ^= 1
    transport = FakeTransport(post_tx=[bytes(valid)])
    evidence = invoke(tmp_path, transport)
    assert evidence["error"]["code"] in {"crc_error", "cobs_error", "wire_frame_error"}
    assert transport.open_calls == 1
    assert len(transport.writes) == 1
    assert evidence["tx_counts"]["command"] == 0


def test_cleanup_closes_on_transport_exception_and_interrupt_without_reopen(tmp_path):
    failed = FakeTransport(read_error=OSError("read failed"))
    evidence = invoke(tmp_path, failed)
    assert evidence["error"]["code"] == "OSError"
    assert failed.close_calls == 1
    assert failed.open_calls == 1
    assert len(failed.writes) == 1

    interrupted = FakeTransport(read_error=KeyboardInterrupt())
    evidence = invoke(tmp_path, interrupted)
    assert evidence["result"] == "interrupted"
    assert interrupted.close_calls == 1
    assert interrupted.open_calls == 1
    assert len(interrupted.writes) == 1

    write_timeout = FakeTransport(write_error=TimeoutError("bounded write timeout"))
    evidence = invoke(tmp_path, write_timeout)
    assert evidence["error"]["code"] == "TimeoutError"
    assert evidence["tx_counts"]["write_attempts"] == 1
    assert evidence["tx_counts"]["config_request_attempts"] == 1
    assert evidence["tx_counts"]["write_successes"] == 0
    assert evidence["tx_counts"]["config_request"] == 0
    assert evidence["tx_counts"]["command"] == 0
    assert write_timeout.close_calls == 1
    assert len(write_timeout.writes) == 1


def test_rejects_evidence_path_inside_repository_before_open(tmp_path):
    transport = FakeTransport()
    evidence = invoke(tmp_path, transport, output_path=ROOT / "should-not-exist.json")
    assert evidence["error"]["code"] == "ValueError"
    assert transport.open_calls == 0
    assert transport.writes == []
    assert transport.close_calls == 1


def test_refuses_to_overwrite_existing_evidence_before_open(tmp_path):
    output = tmp_path / "already-recorded.json"
    original = b'{"existing":"evidence"}\n'
    output.write_bytes(original)
    transport = FakeTransport()
    evidence = invoke(tmp_path, transport, output_path=output)
    assert evidence["error"]["code"] == "FileExistsError"
    assert transport.open_calls == 0
    assert transport.writes == []
    assert output.read_bytes() == original


def test_f2_repository_root_uses_git_for_linked_worktree_with_bounded_timeout(tmp_path, monkeypatch):
    # Build a real linked worktree fixture so this test behaves the same when
    # the suite itself is run from either a clone or a linked worktree.
    clone = tmp_path / "fixture-clone"
    relative_module = Path("ros2_ws/src/mecanum_base_bridge/mecanum_base_bridge/uart_config_only_bench.py")
    module_in_clone = clone / relative_module
    module_in_clone.parent.mkdir(parents=True)
    module_in_clone.write_bytes(Path(bench.__file__).read_bytes())
    subprocess.run(["git", "init", "-q", str(clone)], check=True)
    subprocess.run(["git", "-C", str(clone), "add", str(relative_module)], check=True)
    subprocess.run([
        "git", "-C", str(clone), "-c", "user.name=Fixture", "-c",
        "user.email=fixture@example.invalid", "commit", "-qm", "fixture base",
    ], check=True)
    linked = tmp_path / "fixture-linked-worktree"
    subprocess.run([
        "git", "-C", str(clone), "worktree", "add", "-qb", "fixture-linked", str(linked), "HEAD",
    ], check=True)
    module_in_linked = linked / relative_module
    assert (linked / ".git").is_file()
    monkeypatch.setattr(bench, "__file__", str(module_in_linked))
    real_run = subprocess.run
    timeouts = []

    def checked_run(*args, **kwargs):
        timeouts.append(kwargs.get("timeout"))
        return real_run(*args, **kwargs)

    monkeypatch.setattr(bench.subprocess, "run", checked_run)
    assert bench._repository_root() == linked.resolve()
    assert timeouts and all(value is not None and value <= 3.0 for value in timeouts)


def _run_scheduled(tmp_path, events, *, duration, write_delay=0.0, wake_overshoot=0.0):
    clock = FakeClock()
    transport = ScheduledTransport(clock, events, write_delay=write_delay)

    def scheduled_sleep(seconds):
        target = clock.now + seconds
        if transport.writes and transport.events:
            next_event = transport.config_sent_at + transport.events[0][0]
            if clock.now <= next_event <= target:
                clock.now = next_event
                return
        capture_end = transport.config_sent_at + write_delay + duration if transport.config_sent_at is not None else None
        if (wake_overshoot and capture_end is not None and clock.now < capture_end <= target):
            clock.now = capture_end + wake_overshoot
            return
        clock.now = target

    evidence = invoke(tmp_path, transport, clock=clock, duration=duration, sleeper=scheduled_sleep)
    return evidence, transport, clock


def test_f1_config_status_deadline_reproductions_fail_in_config_phase(tmp_path):
    late_status = status_frame()
    late_telemetry = telemetry_frame()
    evidence, transport, _ = _run_scheduled(
        tmp_path, [(0.800, late_status), (0.810, late_telemetry)], duration=1.0
    )
    assert evidence["error"]["code"] == "config_status_timeout"
    assert evidence["error"]["phase"] == "status_and_telemetry_rx"
    assert transport.open_calls == 1 and len(transport.writes) == 1


def test_f1a_config_deadline_starts_before_a_slow_write(tmp_path):
    events = [
        (0.510, status_frame()),
        (0.515, telemetry_frame(sequence=0, time_us=1000)),
        (0.665, telemetry_frame(sequence=1, time_us=2000)),
        (0.815, telemetry_frame(sequence=2, time_us=3000)),
        (0.965, telemetry_frame(sequence=3, time_us=4000)),
    ]
    evidence, transport, _ = _run_scheduled(tmp_path, events, duration=1.0, write_delay=0.019)
    assert evidence["error"]["code"] == "config_status_timeout"
    assert evidence["rx_counts"]["telemetry"] == 0
    assert len(transport.writes) == 1


@pytest.mark.parametrize("duration, expected", [
    (0.195, "observed"),
    (0.210, "telemetry_freshness_timeout"),
    (0.215, "telemetry_freshness_timeout"),
])
def test_f1b_capture_cutoff_controls_final_freshness(duration, expected, tmp_path):
    evidence, transport, _ = _run_scheduled(
        tmp_path,
        [(0.0, status_frame()), (0.010, telemetry_frame())],
        duration=duration,
        wake_overshoot=0.015,
    )
    actual = "observed" if evidence["result"] == "observed" else evidence["error"]["code"]
    assert actual == expected
    assert transport.open_calls == 1 and len(transport.writes) == 1


@pytest.mark.parametrize("offset, expected", [
    (0.499, "accepted"),
    (0.500, "config_status_timeout"),
    (0.501, "config_status_timeout"),
])
def test_f1_config_status_deadline_before_at_and_after(tmp_path, offset, expected):
    events = [(offset, status_frame())]
    if expected == "accepted":
        events.extend([
            (0.550, telemetry_frame(sequence=1, time_us=1000)),
            (0.700, telemetry_frame(sequence=2, time_us=2000)),
            (0.850, telemetry_frame(sequence=3, time_us=3000)),
        ])
    evidence, _, _ = _run_scheduled(tmp_path, events, duration=1.0)
    actual = "accepted" if evidence["result"] == "observed" else evidence["error"]["code"]
    assert actual == expected


def test_f1_initial_telemetry_deadline_reproductions_and_boundaries(tmp_path):
    late, _, _ = _run_scheduled(
        tmp_path, [(0.0, status_frame()), (0.300, telemetry_frame())], duration=0.5
    )
    assert late["error"]["code"] == "telemetry_initial_timeout"

    for offset, expected in ((0.199, "observed"), (0.200, "telemetry_initial_timeout"),
                             (0.201, "telemetry_initial_timeout")):
        evidence, _, _ = _run_scheduled(
            tmp_path, [(0.0, status_frame()), (offset, telemetry_frame())], duration=0.210
        )
        actual = "observed" if evidence["result"] == "observed" else evidence["error"]["code"]
        assert actual == expected


def test_f1_telemetry_freshness_and_late_packet_cannot_recover_session(tmp_path):
    sparse, _, _ = _run_scheduled(
        tmp_path, [(0.0, status_frame()), (0.010, telemetry_frame())], duration=1.0
    )
    assert sparse["error"]["code"] == "telemetry_freshness_timeout"

    late_recovery, _, _ = _run_scheduled(
        tmp_path,
        [(0.0, status_frame()), (0.010, telemetry_frame()), (0.300, telemetry_frame(sequence=1, time_us=2000))],
        duration=0.5,
    )
    assert late_recovery["error"]["code"] == "telemetry_freshness_timeout"


@pytest.mark.parametrize("gap, expected", [
    (0.199, "observed"),
    (0.200, "telemetry_freshness_timeout"),
    (0.201, "telemetry_freshness_timeout"),
])
def test_f1_subsequent_telemetry_deadline_boundaries(tmp_path, gap, expected):
    evidence, _, _ = _run_scheduled(
        tmp_path,
        [(0.0, status_frame()), (0.010, telemetry_frame()),
         (0.010 + gap, telemetry_frame(sequence=1, time_us=2000))],
        duration=0.250,
    )
    actual = "observed" if evidence["result"] == "observed" else evidence["error"]["code"]
    assert actual == expected


def test_f1_valid_stream_persists_past_each_telemetry_timeout_with_raw_deltas(tmp_path):
    events = [(0.0, status_frame())]
    for index, offset in enumerate((0.010, 0.180, 0.350, 0.520, 0.690), start=0):
        events.append((offset, telemetry_frame(
            sequence=index, time_us=(index + 1) * 100_000,
            ticks=(index, 2 * index, -index, 0),
        )))
    evidence, _, _ = _run_scheduled(tmp_path, events, duration=0.800)
    assert evidence["result"] == "observed"
    assert len(evidence["counter_observations"]) == 5
    assert evidence["counter_observations"][-1]["delta_ticks"] == {
        "FL": 1, "FR": 2, "RL": -1, "RR": 0,
    }


def test_f3_partial_frame_at_capture_end_is_recorded_without_failure(tmp_path):
    first = telemetry_frame(sequence=0, time_us=1000)
    second = telemetry_frame(sequence=1, time_us=2000, ticks=(1, 2, 3, 4))
    third = telemetry_frame(sequence=2, time_us=3000)
    prefix = third[:12]
    suffix = third[12:]
    evidence, _, _ = _run_scheduled(
        tmp_path,
        [(0.0, status_frame()), (0.005, first), (0.025, second), (0.045, prefix), (0.051, suffix)],
        duration=0.050,
    )
    assert evidence["result"] == "observed"
    assert evidence["rx_counts"]["telemetry"] == 2
    assert evidence["rx_counts"]["trailing_partial_bytes"] == 12


def test_f3_complete_bad_frame_fails_and_partial_bytes_do_not_refresh_freshness(tmp_path):
    decoded = decode_frame(telemetry_frame(sequence=1, time_us=2000))
    raw = bytearray(decoded.raw_frame)
    raw[-1] ^= 0x01
    damaged = cobs_encode(bytes(raw)) + b"\x00"
    malformed, _, _ = _run_scheduled(
        tmp_path, [(0.0, status_frame()), (0.005, telemetry_frame()), (0.045, bytes(damaged))], duration=0.2
    )
    assert malformed["error"]["code"] == "crc_error"

    partial, _, _ = _run_scheduled(
        tmp_path, [(0.0, status_frame()), (0.005, telemetry_frame()), (0.150, b"\x01" * 12)], duration=0.4
    )
    assert partial["error"]["code"] == "telemetry_freshness_timeout"
    assert partial["rx_counts"]["trailing_partial_bytes"] == 12


@pytest.mark.parametrize("relative_output", [
    Path("audit-must-reject.json"),
    Path("artifacts/audit-must-reject.json"),
    Path("ros2_ws/audit-must-reject.json"),
])
def test_f2_main_rejects_output_anywhere_in_git_root_before_open(tmp_path, monkeypatch, relative_output):
    fake_root = tmp_path / "fake-repo"
    (fake_root / "artifacts").mkdir(parents=True)
    (fake_root / "ros2_ws/src/mecanum_base_bridge/mecanum_base_bridge").mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(fake_root)], check=True)
    fake_module_path = (fake_root / "ros2_ws/src/mecanum_base_bridge/mecanum_base_bridge/"
                        "uart_config_only_bench.py")
    fake_module_path.write_bytes(Path(bench.__file__).read_bytes())
    monkeypatch.setattr(bench, "__file__", str(fake_module_path))
    monkeypatch.setattr(bench, "_git_source_fingerprint", lambda root: {"git_commit": "test"}, raising=False)
    transports = []

    def transport_factory(device):
        transport = FakeTransport()
        transports.append(transport)
        return transport

    monkeypatch.setattr(bench, "SerialTransport", transport_factory)
    output = fake_root / relative_output
    args = [
        "--serial-device", "/dev/fake", "--hardware-manifest", str(MANIFEST),
        "--reset-epoch", "19", "--config-sequence", "7", "--a1-window", "0.001",
        "--duration", "0.001", "--output", str(output),
        "--confirm-firmware-just-booted-no-config",
    ]
    try:
        bench.main(args)
    except SystemExit:
        pass
    assert transports and transports[0].open_calls == 0
    assert transports[0].writes == []
    assert not output.exists()


def test_f2_main_rejects_symlink_output_resolving_inside_git_root(tmp_path, monkeypatch):
    fake_root = tmp_path / "fake-repo"
    (fake_root / "artifacts").mkdir(parents=True)
    (fake_root / "ros2_ws/src/mecanum_base_bridge/mecanum_base_bridge").mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(fake_root)], check=True)
    fake_module_path = (fake_root / "ros2_ws/src/mecanum_base_bridge/mecanum_base_bridge/"
                        "uart_config_only_bench.py")
    fake_module_path.write_bytes(Path(bench.__file__).read_bytes())
    monkeypatch.setattr(bench, "__file__", str(fake_module_path))
    monkeypatch.setattr(bench, "_git_source_fingerprint", lambda root: {"git_commit": "test"}, raising=False)
    link = tmp_path / "repo-alias"
    link.symlink_to(fake_root, target_is_directory=True)
    transports = []
    monkeypatch.setattr(bench, "SerialTransport", lambda device: transports.append(FakeTransport()) or transports[-1])
    output = link / "artifacts/symlink-must-reject.json"
    args = [
        "--serial-device", "/dev/fake", "--hardware-manifest", str(MANIFEST),
        "--reset-epoch", "19", "--config-sequence", "7", "--a1-window", "0.001",
        "--duration", "0.001", "--output", str(output),
        "--confirm-firmware-just-booted-no-config",
    ]
    try:
        bench.main(args)
    except SystemExit:
        pass
    assert transports and transports[0].open_calls == 0
    assert transports[0].writes == []
    assert not (fake_root / "artifacts/symlink-must-reject.json").exists()
