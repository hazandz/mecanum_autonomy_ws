"""Offline tests for the one-shot CONFIG-only bench harness."""

from __future__ import annotations

from pathlib import Path

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
           output_path=None):
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
        sleeper=clock.sleep,
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
    no_status = invoke(tmp_path, FakeTransport())
    assert no_status["error"]["code"] == "config_status_timeout"
    status_only = invoke(tmp_path, FakeTransport(post_tx=[status_frame()]))
    assert status_only["error"]["code"] == "telemetry_timeout"


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
