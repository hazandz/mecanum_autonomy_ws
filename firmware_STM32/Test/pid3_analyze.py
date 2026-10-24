#!/usr/bin/env python3
"""Screen a PID-3A loaded ALL_FORWARD run exported from the g_pid3 RAM log."""
from __future__ import annotations

import argparse
import csv
import math
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

WHEELS = ("fl", "fr", "rl", "rr")
LABELS = {"fl": "FL", "fr": "FR", "rl": "RL", "rr": "RR"}
RUN_STATE = 2
COMPLETE_STATE = 4
PWM_LIMIT = 400.0
SATURATION_LIMIT_MS = 250.0
MIN_SAMPLES = 100
REQUIRED = {
    "timestamp_ms", "state", "target_cps", "dt_ms", "sync_spread_cps",
    "sync_warning", "log_overflow", "final_state", "last_error",
    "fault_wheel_mask", "completed_count",
}
for wheel in WHEELS:
    REQUIRED.update({
        f"{wheel}_measured_cps", f"{wheel}_error_cps",
        f"{wheel}_u_ff_permille", f"{wheel}_u_i_permille",
        f"{wheel}_u_output_permille", f"{wheel}_encoder_delta",
        f"total_delta_{wheel}",
    })


class CsvError(ValueError):
    pass


@dataclass(frozen=True)
class Row:
    timestamp: int
    state: int
    target: float
    dt_ms: int
    measured: dict[str, float]
    error: dict[str, float]
    ff: dict[str, float]
    ui: dict[str, float]
    pwm: dict[str, float]
    delta: dict[str, int]
    total: dict[str, int]
    spread: float
    warning: int
    overflow: int
    final_state: int
    last_error: int
    fault_mask: int
    completed_count: int


def finite(raw: str | None, name: str, line: int) -> float:
    try:
        value = float(raw)
    except (TypeError, ValueError) as exc:
        raise CsvError(f"line {line}: invalid {name}: {raw!r}") from exc
    if not math.isfinite(value):
        raise CsvError(f"line {line}: non-finite {name}")
    return value


def integer(raw: str | None, name: str, line: int) -> int:
    value = finite(raw, name, line)
    if not value.is_integer():
        raise CsvError(f"line {line}: {name} must be an integer")
    return int(value)


def parse_csv(lines: Iterable[str]) -> list[Row]:
    reader = csv.DictReader(lines)
    if reader.fieldnames is None:
        raise CsvError("CSV is empty or has no header")
    missing = REQUIRED - set(reader.fieldnames)
    if missing:
        raise CsvError("missing columns: " + ", ".join(sorted(missing)))
    rows: list[Row] = []
    for line, raw in enumerate(reader, start=2):
        timestamp = integer(raw.get("timestamp_ms"), "timestamp_ms", line)
        if timestamp < 0 or timestamp > 0xFFFFFFFF:
            raise CsvError(f"line {line}: timestamp_ms outside uint32 range")
        state = integer(raw.get("state"), "state", line)
        target = finite(raw.get("target_cps"), "target_cps", line)
        dt_ms = integer(raw.get("dt_ms"), "dt_ms", line)
        spread = finite(raw.get("sync_spread_cps"), "sync_spread_cps", line)
        warning = integer(raw.get("sync_warning"), "sync_warning", line)
        overflow = integer(raw.get("log_overflow"), "log_overflow", line)
        final_state = integer(raw.get("final_state"), "final_state", line)
        last_error = integer(raw.get("last_error"), "last_error", line)
        fault_mask = integer(raw.get("fault_wheel_mask"), "fault_wheel_mask", line)
        completed_count = integer(raw.get("completed_count"), "completed_count", line)
        if dt_ms <= 0 or spread < 0.0:
            raise CsvError(f"line {line}: dt_ms must be positive and spread nonnegative")
        if warning not in (0, 1) or overflow not in (0, 1):
            raise CsvError(f"line {line}: status flags must be 0 or 1")
        measured: dict[str, float] = {}
        error: dict[str, float] = {}
        ff: dict[str, float] = {}
        ui: dict[str, float] = {}
        pwm: dict[str, float] = {}
        delta: dict[str, int] = {}
        total: dict[str, int] = {}
        for wheel in WHEELS:
            measured[wheel] = finite(raw.get(f"{wheel}_measured_cps"), f"{wheel}_measured_cps", line)
            error[wheel] = finite(raw.get(f"{wheel}_error_cps"), f"{wheel}_error_cps", line)
            ff[wheel] = finite(raw.get(f"{wheel}_u_ff_permille"), f"{wheel}_u_ff_permille", line)
            ui[wheel] = finite(raw.get(f"{wheel}_u_i_permille"), f"{wheel}_u_i_permille", line)
            pwm[wheel] = finite(raw.get(f"{wheel}_u_output_permille"), f"{wheel}_u_output_permille", line)
            delta[wheel] = integer(raw.get(f"{wheel}_encoder_delta"), f"{wheel}_encoder_delta", line)
            total[wheel] = integer(raw.get(f"total_delta_{wheel}"), f"total_delta_{wheel}", line)
            if pwm[wheel] < 0.0 or pwm[wheel] > PWM_LIMIT:
                raise CsvError(f"line {line}: {wheel} PWM outside 0..400 permille")
        if final_state not in range(7) or state not in range(7):
            raise CsvError(f"line {line}: invalid runtime state")
        if fault_mask < 0 or fault_mask > 0x0F or completed_count < 0:
            raise CsvError(f"line {line}: invalid fault mask or completed_count")
        rows.append(Row(timestamp, state, target, dt_ms, measured, error, ff, ui,
                        pwm, delta, total, spread, warning, overflow, final_state,
                        last_error, fault_mask, completed_count))
    if not rows:
        raise CsvError("CSV contains no samples")
    return rows


def percentile95(values: list[float]) -> float:
    ordered = sorted(values)
    return ordered[max(0, math.ceil(0.95 * len(ordered)) - 1)]


def analyze(rows: list[Row]) -> tuple[str, bool]:
    failures: list[str] = []
    run_rows = [row for row in rows if row.state == RUN_STATE]
    if len(run_rows) < MIN_SAMPLES:
        failures.append(f"insufficient run samples ({len(run_rows)}; need {MIN_SAMPLES})")
    if any(row.state != RUN_STATE for row in rows):
        failures.append("CSV contains non-RUN sample rows")
    if any(row.final_state != COMPLETE_STATE for row in rows):
        failures.append("final_state is not COMPLETE (4)")
    if any(row.last_error != 0 for row in rows):
        failures.append("last_error is nonzero")
    if any(row.fault_mask != 0 for row in rows):
        failures.append("fault_wheel_mask is nonzero")
    if any(row.overflow for row in rows):
        failures.append("log_overflow is set")
    if any(row.completed_count < 1 for row in rows):
        failures.append("completed_count is zero")
    targets = [row.target for row in run_rows]
    if not targets or any(abs(target - 500.0) > 0.01 for target in targets):
        failures.append("RUN target must remain +500 cps")

    times = [row.timestamp for row in run_rows]
    intervals = [((b - a) & 0xFFFFFFFF) for a, b in zip(times, times[1:])
                 if ((b - a) & 0xFFFFFFFF) > 0]
    sample_period = statistics.median(intervals) if intervals else 40.0
    duration_ms = (((times[-1] - times[0]) & 0xFFFFFFFF) + sample_period) if times else 0.0
    spreads = [row.spread for row in run_rows]
    sync_mean = statistics.fmean(spreads) if spreads else float("nan")
    sync_p95 = percentile95(spreads) if spreads else float("nan")
    sync_max = max(spreads) if spreads else float("nan")
    sync_limit = 100.0  # PID-3A fixed target: max(10% of 500, 100 cps).
    if not spreads or sync_p95 > sync_limit:
        failures.append(f"sync p95 exceeds {sync_limit:.0f} cps")

    lines = [f"Duration: {duration_ms / 1000.0:.3f} s",
             f"Sample count: {len(run_rows)} (expected about 125)",
             f"Sample interval estimate: {sample_period:.1f} ms", "",
             "Per-wheel steady-state metrics (last 30% of RUN samples):"]
    totals: dict[str, int] = {}
    for wheel in WHEELS:
        tail_start = max(0, int(len(run_rows) * 0.70))
        tail = run_rows[tail_start:]
        tail_speeds = [row.measured[wheel] for row in tail]
        mean_speed = statistics.fmean(tail_speeds) if tail_speeds else float("nan")
        mean_error = 500.0 - mean_speed if tail_speeds else float("nan")
        error_pct = abs(mean_error) * 100.0 / 500.0 if tail_speeds else float("nan")
        stddev = statistics.pstdev(tail_speeds) if len(tail_speeds) > 1 else 0.0
        mean_ff = statistics.fmean(row.ff[wheel] for row in tail) if tail else float("nan")
        mean_i = statistics.fmean(row.ui[wheel] for row in tail) if tail else float("nan")
        mean_pwm = statistics.fmean(row.pwm[wheel] for row in tail) if tail else float("nan")
        saturation_ms = sum(sample_period for row in run_rows if row.pwm[wheel] >= 399.5)
        total = rows[-1].total[wheel]
        totals[wheel] = total
        if not tail or abs(mean_error) > 50.0:
            failures.append(f"{LABELS[wheel]} steady error exceeds 50 cps")
        if saturation_ms > SATURATION_LIMIT_MS:
            failures.append(f"{LABELS[wheel]} saturation exceeds {SATURATION_LIMIT_MS:.0f} ms")
        lines.append(
            f"{LABELS[wheel]}: mean={mean_speed:.1f} cps, error={mean_error:.1f} cps "
            f"({error_pct:.2f}%), stddev={stddev:.1f}, FF={mean_ff:.1f}, "
            f"I={mean_i:.1f}, PWM={mean_pwm:.1f}, saturation={saturation_ms:.0f} ms, "
            f"total_counts={total}"
        )
    lines.extend(["", f"Synchronization: mean={sync_mean:.1f}, p95={sync_p95:.1f}, "
                  f"max={sync_max:.1f} cps (p95 limit {sync_limit:.0f})"])
    total_values = list(totals.values())
    if total_values:
        min_total, max_total = min(total_values), max(total_values)
        mean_total = statistics.fmean(total_values)
        spread_counts = max_total - min_total
        spread_pct = (spread_counts * 100.0 / mean_total) if mean_total else 0.0
        lines.extend(["Total-count comparison (diagnostic only):",
                      f"min={min_total}, max={max_total}, mean={mean_total:.1f}, "
                      f"spread={spread_counts} counts ({spread_pct:.2f}%)"])
    lines.extend(["", "MANUAL CHASSIS OBSERVATION: not present in firmware CSV.",
                  "Record forward distance, lateral drift, and heading error separately.",
                  "", "Screening: " + ("FAIL" if failures else "PASS")])
    if failures:
        lines.append("Reasons:")
        lines.extend(f"- {reason}" for reason in dict.fromkeys(failures))
    return "\n".join(lines), not failures


def _fixture(*, fault: int = 0, overflow: int = 0, pwm: int = 150,
             counts: int = 2500, spread: int = 20,
             varied: bool = False, failing_wheel: str | None = None) -> list[Row]:
    rows = []
    for idx in range(125):
        measured = {}
        for wheel in WHEELS:
            offset = ((idx % 3) - 1) * 50 if varied else 0
            if wheel == failing_wheel:
                offset -= 100
            measured[wheel] = float(500 + offset)
        rows.append(Row(
            timestamp=idx * 40, state=RUN_STATE, target=500.0, dt_ms=20,
            measured=measured, error={w: 500.0 - measured[w] for w in WHEELS},
            ff={w: 150.0 for w in WHEELS}, ui={w: 0.0 for w in WHEELS},
            pwm={w: float(pwm) for w in WHEELS}, delta={w: 20 for w in WHEELS},
            total={w: counts for w in WHEELS}, spread=float(spread), warning=0,
            overflow=overflow, final_state=COMPLETE_STATE, last_error=0,
            fault_mask=fault, completed_count=1))
    return rows


def self_test() -> None:
    def require(condition: bool, message: str) -> None:
        if not condition:
            raise AssertionError(message)

    _, passed = analyze(_fixture())
    require(passed, "perfect four-wheel tracking should pass")
    _, passed = analyze(_fixture(failing_wheel="rl"))
    require(not passed, "one-wheel steady-error violation should fail")
    _, passed = analyze(_fixture(spread=150))
    require(not passed, "excessive synchronization spread should fail")
    _, passed = analyze(_fixture(fault=0x04))
    require(not passed, "fault metadata should fail")
    _, passed = analyze(_fixture(overflow=1))
    require(not passed, "log overflow should fail")
    _, passed = analyze(_fixture(pwm=400))
    require(not passed, "prolonged saturation should fail")
    _, passed = analyze(_fixture(varied=True))
    require(passed, "quantization-like 450/500/550 cps must not false-fail")
    header = ",".join(sorted(REQUIRED)) + "\n"
    try:
        parse_csv([header, "bad\n"])
    except CsvError:
        pass
    else:
        raise AssertionError("invalid CSV should be rejected")
    report, _ = analyze(_fixture(counts=1234))
    require("total_counts=1234" in report and "spread=0 counts" in report,
            "cumulative encoder totals should be reported")
    print("PID-3 analyzer self-test: PASS (9 checks)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", nargs="?", type=Path, help="CSV exported from g_pid3_log")
    parser.add_argument("--self-test", action="store_true", help="run synthetic analyzer checks")
    args = parser.parse_args()
    if args.self_test:
        try:
            self_test()
        except AssertionError as exc:
            print(f"PID-3 analyzer self-test: FAIL: {exc}", file=sys.stderr)
            return 1
        return 0
    if args.csv is None:
        parser.error("provide a CSV path or --self-test")
    try:
        with args.csv.open("r", newline="", encoding="utf-8") as stream:
            rows = parse_csv(stream)
        report_text, passed = analyze(rows)
    except (OSError, CsvError, csv.Error) as exc:
        print(f"CSV ERROR: {exc}", file=sys.stderr)
        return 2
    print(report_text)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
