"""CONFIG-only UART bench for bounded, non-motor Pi--STM32 observation.

This module sends at most one CONFIG_REQUEST. It contains no COMMAND encoder,
ROS node, lifecycle gate, odometry, reconnect loop, or motor operation.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import subprocess
import time
from typing import Callable

from .hardware_config import communication_config_valid, load_manifest, manifest_digest
from .protocol_constants import (
    CONFIG_ACCEPTED,
    ESTOP_AUX_UNKNOWN,
    MAX_WIRE_FRAME_LENGTH,
    MESSAGE_CONFIG,
    MESSAGE_TELEMETRY,
    REJECT_NONE,
    WIRE_DELIMITER,
)
from .transport import SerialTransport
from .uart_v1_codec import (
    CobsDecodeError,
    ConfigRequestPacket,
    ConfigStatusPacket,
    CrcMismatchError,
    FrameTooLargeError,
    MessageTypeError,
    PayloadLengthError,
    ProtocolVersionError,
    TelemetryPacket,
    WireFrameError,
    build_wire_frame,
    decode_frame,
    parse_config_request,
    parse_config_status,
    parse_telemetry,
    serialize_config_request,
)


MAX_OBSERVATION_SECONDS = 300.0
MAX_A1_WINDOW_SECONDS = 30.0
CONFIG_STATUS_TIMEOUT_SECONDS = 0.500
TELEMETRY_TIMEOUT_SECONDS = 0.200
MAX_WIRE_ACCUMULATOR = MAX_WIRE_FRAME_LENGTH - 1
ALLOWED_MCU_FAULTS = 1 | 2 | 256 | 512 | 1024 | 2048 | 4096
INT64_MIN = -(1 << 63)
INT64_MAX = (1 << 63) - 1


class BenchFailure(RuntimeError):
    """A specific fail-closed bench result, suitable for evidence output."""

    def __init__(self, code: str, detail: str):
        super().__init__(detail)
        self.code = code


class WireFrameAccumulator:
    """Split nonblocking byte chunks into bounded delimiter-terminated frames."""

    def __init__(self) -> None:
        self._frame = bytearray()

    @property
    def pending_bytes(self) -> int:
        return len(self._frame)

    def feed(self, chunk: bytes) -> list[bytes]:
        if not isinstance(chunk, bytes):
            raise TypeError("serial read must return bytes")
        completed: list[bytes] = []
        for byte in chunk:
            if byte == WIRE_DELIMITER:
                if not self._frame:
                    raise WireFrameError("empty UART frame delimiter")
                completed.append(bytes(self._frame) + bytes((WIRE_DELIMITER,)))
                self._frame.clear()
                continue
            if len(self._frame) >= MAX_WIRE_ACCUMULATOR:
                self._frame.clear()
                raise FrameTooLargeError("UART frame exceeded the 98-byte wire limit")
            self._frame.append(byte)
        return completed


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _validate_parameters(
    serial_device: str,
    manifest_path: Path,
    reset_epoch: int,
    config_sequence: int,
    duration: float,
    a1_window: float,
    output_path: Path,
    repository_root: Path,
    confirm_a1_precondition: bool,
) -> tuple[dict, bytes, str]:
    if not isinstance(serial_device, str) or not serial_device.strip():
        raise ValueError("serial device must be explicitly supplied")
    for name, value in (("reset_epoch", reset_epoch), ("config_sequence", config_sequence)):
        if type(value) is not int or not 0 <= value <= 0xFFFFFFFF:
            raise ValueError(f"{name} must fit uint32")
    if config_sequence == 0:
        raise ValueError("config_sequence must be in 1..0xFFFFFFFF")
    if not math.isfinite(duration) or not 0 < duration <= MAX_OBSERVATION_SECONDS:
        raise ValueError(f"duration must be finite and in (0, {MAX_OBSERVATION_SECONDS}]")
    if not math.isfinite(a1_window) or not 0 < a1_window <= MAX_A1_WINDOW_SECONDS:
        raise ValueError(f"a1_window must be finite and in (0, {MAX_A1_WINDOW_SECONDS}]")
    if not confirm_a1_precondition:
        raise ValueError("A1 requires explicit confirmation that firmware just booted without prior CONFIG")
    resolved_output = output_path.expanduser().resolve()
    root = repository_root.resolve()
    if resolved_output == root or root in resolved_output.parents:
        raise ValueError("evidence output must be outside the repository")
    if resolved_output.exists():
        raise FileExistsError(f"refusing to overwrite evidence output: {resolved_output}")
    if not resolved_output.parent.is_dir():
        raise FileNotFoundError(f"evidence output directory must already exist: {resolved_output.parent}")

    manifest = load_manifest(manifest_path)
    if not communication_config_valid(manifest):
        raise ValueError("hardware manifest is not a valid UART v1 communication profile")
    digest = manifest_digest(manifest)
    manifest_bytes = manifest_path.read_bytes()
    manifest_sha256 = hashlib.sha256(manifest_bytes).hexdigest()
    return manifest, digest, manifest_sha256


def _decode_packet(wire: bytes):
    try:
        frame = decode_frame(wire)
    except CobsDecodeError as exc:
        raise BenchFailure("cobs_error", str(exc)) from exc
    except CrcMismatchError as exc:
        raise BenchFailure("crc_error", str(exc)) from exc
    except ProtocolVersionError as exc:
        raise BenchFailure("protocol_version_error", str(exc)) from exc
    except MessageTypeError as exc:
        raise BenchFailure("message_type_error", str(exc)) from exc
    except PayloadLengthError as exc:
        raise BenchFailure("payload_length_error", str(exc)) from exc
    except FrameTooLargeError as exc:
        raise BenchFailure("frame_too_large", str(exc)) from exc
    except WireFrameError as exc:
        raise BenchFailure("wire_frame_error", str(exc)) from exc
    if frame.message_type == MESSAGE_CONFIG:
        if len(frame.payload) == 50:
            return frame, parse_config_status(frame.payload)
        raise BenchFailure("unexpected_config_frame", "received CONFIG_REQUEST from STM32")
    if frame.message_type == MESSAGE_TELEMETRY:
        try:
            return frame, parse_telemetry(frame.payload)
        except ValueError as exc:
            raise BenchFailure("telemetry_field_error", str(exc)) from exc
    raise BenchFailure("unexpected_message_type", f"received message type 0x{frame.message_type:02x}")


def _feed_frames(accumulator: WireFrameAccumulator, chunk: bytes) -> list[bytes]:
    try:
        return accumulator.feed(chunk)
    except (FrameTooLargeError, WireFrameError) as exc:
        raise BenchFailure("framing_error", str(exc)) from exc


def _guard_config_tx(frame_bytes: bytes, expected: ConfigRequestPacket) -> None:
    """Final fail-closed TX guard; this is the only permitted write payload."""
    frame = decode_frame(frame_bytes)
    if frame.message_type != MESSAGE_CONFIG or len(frame.payload) != 40:
        raise BenchFailure("tx_guard_rejected", "outbound frame is not a 40-byte CONFIG_REQUEST")
    try:
        decoded = parse_config_request(frame.payload)
    except (ValueError, WireFrameError) as exc:
        raise BenchFailure("tx_guard_rejected", f"CONFIG_REQUEST decode failed: {exc}") from exc
    if decoded != expected:
        raise BenchFailure("tx_guard_rejected", "outbound CONFIG_REQUEST differs from invocation parameters")


def _validate_status(
    status: ConfigStatusPacket,
    expected: ConfigRequestPacket,
) -> None:
    if status.config_sequence != expected.config_sequence:
        raise BenchFailure("config_sequence_mismatch", "CONFIG_STATUS sequence did not echo request")
    if status.reset_epoch != expected.reset_epoch:
        raise BenchFailure("config_epoch_mismatch", "CONFIG_STATUS epoch did not echo request")
    if status.hardware_config_hash != expected.hardware_config_hash:
        raise BenchFailure("config_hash_mismatch", "CONFIG_STATUS hash did not echo manifest digest")
    if status.mcu_boot_id == 0:
        raise BenchFailure("invalid_boot_id", "CONFIG_STATUS boot_id must be nonzero")
    if status.config_status != CONFIG_ACCEPTED or status.reject_reason != REJECT_NONE:
        raise BenchFailure(
            "config_rejected",
            f"CONFIG_STATUS rejected: status={status.config_status}, reject_reason={status.reject_reason}",
        )


def _check_session_deadline(
    now: float,
    *,
    config_status_accepted: bool,
    telemetry_count: int,
    config_status_deadline: float,
    first_telemetry_deadline: float | None,
    telemetry_deadline: float | None,
) -> None:
    """Expire the active protocol phase before accepting any newly-read bytes."""
    if not config_status_accepted:
        if now >= config_status_deadline:
            raise BenchFailure("config_status_timeout", "CONFIG_STATUS deadline expired")
        return
    if telemetry_count == 0:
        if first_telemetry_deadline is None or now >= first_telemetry_deadline:
            raise BenchFailure("telemetry_initial_timeout", "first TELEMETRY deadline expired")
        return
    if telemetry_deadline is None or now >= telemetry_deadline:
        raise BenchFailure("telemetry_freshness_timeout", "TELEMETRY freshness deadline expired")


def _telemetry_observation(
    packet: TelemetryPacket,
    *,
    expected: ConfigRequestPacket,
    boot_id: int,
    previous: TelemetryPacket | None,
) -> dict:
    if packet.mcu_boot_id != boot_id:
        raise BenchFailure("telemetry_boot_id_mismatch", "TELEMETRY boot_id differs from accepted CONFIG_STATUS")
    if packet.reset_epoch != expected.reset_epoch:
        raise BenchFailure("telemetry_epoch_mismatch", "TELEMETRY epoch differs from CONFIG_REQUEST")
    if packet.estop_aux_active != ESTOP_AUX_UNKNOWN:
        raise BenchFailure(
            "estop_aux_not_unknown",
            f"expected E-stop auxiliary UNKNOWN=2, received {packet.estop_aux_active}",
        )
    if packet.last_accepted_command_sequence != 0:
        raise BenchFailure(
            "unexpected_command_ack",
            f"expected command acknowledgement 0, received {packet.last_accepted_command_sequence}",
        )
    if packet.mcu_fault_bits & ~ALLOWED_MCU_FAULTS:
        raise BenchFailure("reserved_fault_bits", f"reserved MCU fault bits 0x{packet.mcu_fault_bits:08x}")
    if packet.mcu_fault_bits != 0:
        raise BenchFailure("mcu_fault_reported", f"MCU fault bits 0x{packet.mcu_fault_bits:08x}")

    delta = None
    if previous is not None:
        if packet.mcu_boot_id != previous.mcu_boot_id or packet.reset_epoch != previous.reset_epoch:
            raise BenchFailure("counter_baseline_boundary", "refusing counter delta across boot_id or epoch")
        if packet.telemetry_sequence <= previous.telemetry_sequence:
            raise BenchFailure("telemetry_sequence_not_increasing", "TELEMETRY sequence did not increase")
        if packet.mcu_monotonic_time_us <= previous.mcu_monotonic_time_us:
            raise BenchFailure("telemetry_time_not_increasing", "MCU monotonic time did not increase")
        current_ticks = (packet.ticks_fl, packet.ticks_fr, packet.ticks_rl, packet.ticks_rr)
        previous_ticks = (previous.ticks_fl, previous.ticks_fr, previous.ticks_rl, previous.ticks_rr)
        delta_values = tuple(current - old for current, old in zip(current_ticks, previous_ticks))
        if any(value < INT64_MIN or value > INT64_MAX for value in delta_values):
            raise BenchFailure("counter_delta_out_of_range", "signed int64 counter delta overflow")
        delta = dict(zip(("FL", "FR", "RL", "RR"), delta_values))
    elif not 0 <= packet.telemetry_sequence <= 0xFFFFFFFF:
        raise BenchFailure("telemetry_sequence_invalid", "first telemetry sequence is outside uint32")

    return {
        "observed_at_utc": _utc_now(),
        "telemetry_sequence": packet.telemetry_sequence,
        "mcu_monotonic_time_us": packet.mcu_monotonic_time_us,
        "mcu_boot_id": packet.mcu_boot_id,
        "reset_epoch": packet.reset_epoch,
        "last_accepted_command_sequence": packet.last_accepted_command_sequence,
        "mcu_fault_bits": packet.mcu_fault_bits,
        "estop_aux_active": packet.estop_aux_active,
        "cumulative_ticks": {
            "FL": packet.ticks_fl,
            "FR": packet.ticks_fr,
            "RL": packet.ticks_rl,
            "RR": packet.ticks_rr,
        },
        "delta_ticks": delta,
    }


def run_bench(
    *,
    transport,
    serial_device: str,
    manifest_path: Path,
    reset_epoch: int,
    config_sequence: int,
    duration: float,
    a1_window: float,
    output_path: Path,
    confirm_a1_precondition: bool,
    source_fingerprint: dict,
    repository_root: Path,
    clock: Callable[[], float] = time.monotonic,
    sleeper: Callable[[float], None] = time.sleep,
) -> dict:
    """Run one bounded bench invocation and always close its transport."""
    started_at = _utc_now()
    evidence = {
        "schema_version": "wp07_u6_config_only_bench/v1",
        "result": "failed",
        "source_fingerprint": source_fingerprint,
        "invocation": {
            "serial_device": serial_device,
            "hardware_manifest": str(manifest_path),
            "reset_epoch": reset_epoch,
            "config_sequence": config_sequence,
            "a1_window_seconds": a1_window,
            "duration_seconds": duration,
            "a1_precondition_owner_confirmed": bool(confirm_a1_precondition),
        },
        "started_at_utc": started_at,
        "finished_at_utc": None,
        "manifest_sha256": None,
        "hardware_config_hash": None,
        "a1_observation": "not_started",
        "tx_counts": {
            "write_attempts": 0,
            "write_successes": 0,
            "config_request_attempts": 0,
            "config_request": 0,
            "command": 0,
        },
        "rx_counts": {
            "bytes": 0, "complete_frames": 0, "valid_frames": 0, "telemetry": 0,
            "trailing_partial_bytes": 0,
        },
        "config_status": None,
        "boot_id": None,
        "epoch": None,
        "counter_observations": [],
        "error": None,
        "termination_reason": None,
        "limitations": [
            "No wheel signs are inferred; raw cumulative counters only.",
            "A1 is interpretable only if the owner-confirmed just-booted/no-prior-CONFIG precondition is true.",
            "No COMMAND, ROS, motor, or odometry operation is performed.",
        ],
    }
    accumulator = WireFrameAccumulator()
    current_phase = "preflight"
    expected: ConfigRequestPacket | None = None
    accepted_boot_id: int | None = None
    previous_telemetry: TelemetryPacket | None = None
    config_status_accepted = False
    capture_deadline: float | None = None
    config_status_deadline: float | None = None
    first_telemetry_deadline: float | None = None
    telemetry_deadline: float | None = None

    try:
        manifest, digest, manifest_sha256 = _validate_parameters(
            serial_device,
            manifest_path,
            reset_epoch,
            config_sequence,
            duration,
            a1_window,
            output_path,
            repository_root,
            confirm_a1_precondition,
        )
        evidence["manifest_sha256"] = manifest_sha256
        evidence["hardware_config_hash"] = digest.hex()
        expected = ConfigRequestPacket(config_sequence, reset_epoch, digest)
        if not transport.open():
            raise BenchFailure("serial_open_backoff", "transport did not open on its single open attempt")

        current_phase = "a1_preconfig_observation"
        a1_deadline = clock() + a1_window
        while clock() < a1_deadline:
            chunk = transport.read(256)
            if chunk:
                evidence["rx_counts"]["bytes"] += len(chunk)
                for wire in _feed_frames(accumulator, chunk):
                    evidence["rx_counts"]["complete_frames"] += 1
                    _, packet = _decode_packet(wire)
                    evidence["rx_counts"]["valid_frames"] += 1
                    if isinstance(packet, TelemetryPacket):
                        raise BenchFailure(
                            "preconfig_telemetry_received",
                            "TELEMETRY arrived before this invocation sent CONFIG_REQUEST",
                        )
                    raise BenchFailure("unexpected_preconfig_frame", "unexpected valid UART frame before CONFIG")
            else:
                sleeper(min(0.005, max(0.0, a1_deadline - clock())))
        if accumulator.pending_bytes:
            raise BenchFailure(
                "incomplete_preconfig_frame",
                f"received {accumulator.pending_bytes} unterminated byte(s) during A1 window",
            )
        evidence["a1_observation"] = "no_complete_frame_observed_during_finite_window"

        current_phase = "config_request_tx"
        request_payload = serialize_config_request(expected)
        config_frame = build_wire_frame(MESSAGE_CONFIG, request_payload)
        _guard_config_tx(config_frame, expected)
        evidence["tx_counts"]["write_attempts"] += 1
        evidence["tx_counts"]["config_request_attempts"] += 1
        transport.write(config_frame)
        evidence["tx_counts"]["write_successes"] += 1
        evidence["tx_counts"]["config_request"] += 1
        sent_at = clock()
        capture_deadline = sent_at + duration
        config_status_deadline = sent_at + CONFIG_STATUS_TIMEOUT_SECONDS
        current_phase = "status_and_telemetry_rx"

        while True:
            now = clock()
            _check_session_deadline(
                now,
                config_status_accepted=config_status_accepted,
                telemetry_count=evidence["rx_counts"]["telemetry"],
                config_status_deadline=config_status_deadline,
                first_telemetry_deadline=first_telemetry_deadline,
                telemetry_deadline=telemetry_deadline,
            )
            if now >= capture_deadline:
                break

            chunk = transport.read(256)
            rx_at = clock()
            if chunk:
                evidence["rx_counts"]["bytes"] += len(chunk)
            _check_session_deadline(
                rx_at,
                config_status_accepted=config_status_accepted,
                telemetry_count=evidence["rx_counts"]["telemetry"],
                config_status_deadline=config_status_deadline,
                first_telemetry_deadline=first_telemetry_deadline,
                telemetry_deadline=telemetry_deadline,
            )
            if rx_at >= capture_deadline:
                break

            if chunk:
                for wire in _feed_frames(accumulator, chunk):
                    evidence["rx_counts"]["complete_frames"] += 1
                    evidence["rx_counts"]["trailing_partial_bytes"] = accumulator.pending_bytes
                    _check_session_deadline(
                        clock(),
                        config_status_accepted=config_status_accepted,
                        telemetry_count=evidence["rx_counts"]["telemetry"],
                        config_status_deadline=config_status_deadline,
                        first_telemetry_deadline=first_telemetry_deadline,
                        telemetry_deadline=telemetry_deadline,
                    )
                    _, packet = _decode_packet(wire)
                    evidence["rx_counts"]["valid_frames"] += 1
                    if isinstance(packet, ConfigStatusPacket):
                        if config_status_accepted:
                            raise BenchFailure("duplicate_config_status", "received more than one CONFIG_STATUS")
                        _validate_status(packet, expected)
                        config_status_accepted = True
                        accepted_boot_id = packet.mcu_boot_id
                        first_telemetry_deadline = rx_at + TELEMETRY_TIMEOUT_SECONDS
                        evidence["config_status"] = {
                            "config_sequence": packet.config_sequence,
                            "reset_epoch": packet.reset_epoch,
                            "hardware_config_hash": packet.hardware_config_hash.hex(),
                            "config_status": packet.config_status,
                            "reject_reason": packet.reject_reason,
                        }
                        evidence["boot_id"] = accepted_boot_id
                        evidence["epoch"] = packet.reset_epoch
                    elif isinstance(packet, TelemetryPacket):
                        if not config_status_accepted or accepted_boot_id is None:
                            raise BenchFailure(
                                "telemetry_before_accepted_status",
                                "TELEMETRY arrived before matching CONFIG_STATUS ACCEPTED",
                            )
                        observation = _telemetry_observation(
                            packet,
                            expected=expected,
                            boot_id=accepted_boot_id,
                            previous=previous_telemetry,
                        )
                        evidence["counter_observations"].append(observation)
                        evidence["rx_counts"]["telemetry"] += 1
                        previous_telemetry = packet
                        telemetry_deadline = rx_at + TELEMETRY_TIMEOUT_SECONDS
                    else:  # pragma: no cover - _decode_packet returns only the two accepted types.
                        raise BenchFailure("unexpected_frame", "unexpected packet type")
                evidence["rx_counts"]["trailing_partial_bytes"] = accumulator.pending_bytes
            else:
                phase_deadline = config_status_deadline
                if config_status_accepted:
                    phase_deadline = first_telemetry_deadline if evidence["rx_counts"]["telemetry"] == 0 else telemetry_deadline
                wake_at = min(capture_deadline, phase_deadline)
                remaining = max(0.0, wake_at - clock())
                if remaining:
                    sleeper(min(0.005, remaining))

        evidence["rx_counts"]["trailing_partial_bytes"] = accumulator.pending_bytes
        _check_session_deadline(
            clock(),
            config_status_accepted=config_status_accepted,
            telemetry_count=evidence["rx_counts"]["telemetry"],
            config_status_deadline=config_status_deadline,
            first_telemetry_deadline=first_telemetry_deadline,
            telemetry_deadline=telemetry_deadline,
        )
        if not config_status_accepted:
            raise BenchFailure("config_status_timeout", "no matching CONFIG_STATUS before capture ended")
        if evidence["rx_counts"]["telemetry"] == 0:
            raise BenchFailure("telemetry_initial_timeout", "no valid TELEMETRY before capture ended")
        evidence["result"] = "observed"
        evidence["termination_reason"] = "finite_observation_window_elapsed"
    except KeyboardInterrupt:
        evidence["result"] = "interrupted"
        evidence["error"] = {"code": "keyboard_interrupt", "detail": "operator interrupted bounded observation"}
        evidence["termination_reason"] = "interrupted"
    except Exception as exc:
        code = exc.code if isinstance(exc, BenchFailure) else type(exc).__name__
        evidence["error"] = {"code": code, "detail": str(exc), "phase": current_phase}
        evidence["termination_reason"] = code
    finally:
        evidence["rx_counts"]["trailing_partial_bytes"] = accumulator.pending_bytes
        try:
            transport.close()
        except Exception as exc:
            evidence["result"] = "failed"
            cleanup = {"code": "transport_close_error", "detail": str(exc), "phase": "cleanup"}
            if evidence["error"] is None:
                evidence["error"] = cleanup
            else:
                evidence["cleanup_error"] = cleanup
            evidence["termination_reason"] = "transport_close_error"
        evidence["tx_counts"]["command"] = 0
        evidence["finished_at_utc"] = _utc_now()
    return evidence


def _repository_root() -> Path:
    module_path = Path(__file__).resolve()
    result = subprocess.run(
        ["git", "-C", str(module_path.parent), "rev-parse", "--show-toplevel"],
        check=True,
        capture_output=True,
        text=True,
        timeout=3.0,
    )
    root = Path(result.stdout.strip()).resolve()
    if not root.is_dir():
        raise RuntimeError("Git repository root is not a directory")
    return root


def _git_source_fingerprint(repository_root: Path) -> dict:
    result = subprocess.run(
        ["git", "-C", str(repository_root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
        timeout=3.0,
    )
    commit = result.stdout.strip()
    script_path = Path(__file__).resolve()
    return {
        "git_commit": commit,
        "harness_path": str(script_path),
        "harness_sha256": hashlib.sha256(script_path.read_bytes()).hexdigest(),
    }


def _positive_finite_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed) or parsed <= 0:
        raise argparse.ArgumentTypeError("must be a finite number greater than zero")
    return parsed


def _uint32(value: str) -> int:
    try:
        parsed = int(value, 0)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer (decimal or 0x-prefixed)") from exc
    if not 0 <= parsed <= 0xFFFFFFFF:
        raise argparse.ArgumentTypeError("must fit uint32")
    return parsed


def write_evidence(path: Path, evidence: dict, repository_root: Path) -> Path:
    resolved = path.expanduser().resolve()
    root = repository_root.resolve()
    if resolved == root or root in resolved.parents:
        raise ValueError("evidence output must be outside the repository")
    resolved.parent.mkdir(parents=False, exist_ok=True)
    with resolved.open("x", encoding="utf-8") as stream:
        json.dump(evidence, stream, indent=2, sort_keys=True, ensure_ascii=False)
        stream.write("\n")
        stream.flush()
    return resolved


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="One-shot CONFIG-only UART bench; never sends COMMAND")
    parser.add_argument("--serial-device", required=True, help="explicit serial device path; no default is selected")
    parser.add_argument("--hardware-manifest", required=True, type=Path)
    parser.add_argument("--reset-epoch", required=True, type=_uint32)
    parser.add_argument("--config-sequence", required=True, type=_uint32)
    parser.add_argument("--a1-window", required=True, type=_positive_finite_float,
                        help="finite pre-CONFIG observation window in seconds")
    parser.add_argument("--duration", required=True, type=_positive_finite_float,
                        help="finite status/telemetry observation window in seconds")
    parser.add_argument("--output", required=True, type=Path,
                        help="new evidence JSON path outside the repository")
    parser.add_argument("--confirm-firmware-just-booted-no-config", action="store_true",
                        help="owner confirmation required to interpret A1 pre-CONFIG observation")
    args = parser.parse_args(argv)

    if args.config_sequence == 0:
        parser.error("--config-sequence must be in 1..0xFFFFFFFF")
    if args.a1_window > MAX_A1_WINDOW_SECONDS:
        parser.error(f"--a1-window must not exceed {MAX_A1_WINDOW_SECONDS} seconds")
    if args.duration > MAX_OBSERVATION_SECONDS:
        parser.error(f"--duration must not exceed {MAX_OBSERVATION_SECONDS} seconds")
    try:
        repository_root = _repository_root()
        source_fingerprint = _git_source_fingerprint(repository_root)
        transport = SerialTransport(args.serial_device)
        evidence = run_bench(
            transport=transport,
            serial_device=args.serial_device,
            manifest_path=args.hardware_manifest.expanduser().resolve(),
            reset_epoch=args.reset_epoch,
            config_sequence=args.config_sequence,
            duration=args.duration,
            a1_window=args.a1_window,
            output_path=args.output.expanduser().resolve(),
            confirm_a1_precondition=args.confirm_firmware_just_booted_no_config,
            source_fingerprint=source_fingerprint,
            repository_root=repository_root,
        )
        output_path = write_evidence(args.output, evidence, repository_root)
    except Exception as exc:
        parser.error(str(exc))
    print(f"result={evidence['result']} termination_reason={evidence['termination_reason']}")
    print(f"config_request_tx={evidence['tx_counts']['config_request']} command_tx={evidence['tx_counts']['command']}")
    print(f"telemetry_rx={evidence['rx_counts']['telemetry']} evidence={output_path}")
    return 0 if evidence["result"] == "observed" else 1


if __name__ == "__main__":  # pragma: no cover - exercised as a module by the owner.
    raise SystemExit(main())
