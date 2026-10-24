#!/usr/bin/env python3
"""Offline summary and acceptance checks for PID-1A RAM-log CSV exports."""
import argparse
import csv
import math
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

REQUIRED = {
    "timestamp_ms", "state", "selected_wheel", "direction", "target_cps",
    "measured_cps", "error_cps", "u_ff_permille", "u_p_permille",
    "u_i_permille", "u_output_permille", "encoder_delta", "dt_ms",
    "log_overflow", "final_state",
}
WHEEL_NAMES = {"0": "FL", "1": "FR", "2": "RL", "3": "RR",
               "FL": "FL", "FR": "FR", "RL": "RL", "RR": "RR"}
DIRECTIONS = {"1": ("FORWARD", 1.0), "2": ("REVERSE", -1.0),
              "FORWARD": ("FORWARD", 1.0), "REVERSE": ("REVERSE", -1.0)}
EXPECTED = [500, 1000, 1400, 1000, 500]


class CsvError(ValueError):
    pass


@dataclass
class Row:
    timestamp_ms: int
    state: str
    wheel: str
    direction: str
    sign: float
    target: float
    measured: float
    error: float
    pwm: float
    ff: float
    up: float
    ui: float
    delta: int
    dt_ms: int
    overflow: int
    final_state: int


def _number(raw: str, name: str, line: int) -> float:
    try:
        value = float(raw)
    except (ValueError, TypeError) as exc:
        raise CsvError(f"line {line}: invalid {name}: {raw!r}") from exc
    if not math.isfinite(value):
        raise CsvError(f"line {line}: non-finite {name}")
    return value


def parse_csv(source: Iterable[str]) -> list[Row]:
    reader = csv.DictReader(source)
    if reader.fieldnames is None:
        raise CsvError("CSV is empty or has no header")
    missing = REQUIRED - set(reader.fieldnames)
    if missing:
        raise CsvError("missing columns: " + ", ".join(sorted(missing)))
    rows = []
    for line, raw in enumerate(reader, start=2):
        wheel_key = (raw.get("selected_wheel") or "").strip().upper()
        direction_key = (raw.get("direction") or "").strip().upper()
        if wheel_key not in WHEEL_NAMES:
            raise CsvError(f"line {line}: invalid selected_wheel {wheel_key!r}")
        if direction_key not in DIRECTIONS:
            raise CsvError(f"line {line}: invalid direction {direction_key!r}")
        state = (raw.get("state") or "").strip().upper()
        try:
            timestamp = int(_number(raw["timestamp_ms"], "timestamp_ms", line))
            dt = int(_number(raw["dt_ms"], "dt_ms", line))
            delta = int(_number(raw["encoder_delta"], "encoder_delta", line))
            overflow = int(_number(raw["log_overflow"], "log_overflow", line))
            final_state = int(_number(raw["final_state"], "final_state", line))
        except (OverflowError, ValueError) as exc:
            if isinstance(exc, CsvError):
                raise
            raise CsvError(f"line {line}: invalid integer field") from exc
        if dt <= 0 or overflow not in (0, 1):
            raise CsvError(f"line {line}: dt_ms must be positive and log_overflow 0/1")
        sign = DIRECTIONS[direction_key][1]
        if final_state not in (0, 1, 2, 3, 4, 5):
            raise CsvError(f"line {line}: invalid final_state {final_state}")
        rows.append(Row(timestamp, state, WHEEL_NAMES[wheel_key],
                        DIRECTIONS[direction_key][0], sign,
                        _number(raw["target_cps"], "target_cps", line),
                        _number(raw["measured_cps"], "measured_cps", line),
                        _number(raw["error_cps"], "error_cps", line),
                        _number(raw["u_output_permille"], "u_output_permille", line),
                        _number(raw["u_ff_permille"], "u_ff_permille", line),
                        _number(raw["u_p_permille"], "u_p_permille", line),
                        _number(raw["u_i_permille"], "u_i_permille", line),
                        delta, dt, overflow, final_state))
    if not rows:
        raise CsvError("CSV contains no samples")
    return rows


def segments(rows: list[Row]) -> list[list[Row]]:
    result: list[list[Row]] = []
    key = None
    for row in rows:
        if row.state not in ("2", "RUN_PROFILE") or abs(row.target) < 0.5:
            key = None
            continue
        current = (row.wheel, row.direction, round(abs(row.target)))
        if current != key:
            result.append([])
            key = current
        result[-1].append(row)
    return result


def analyze(rows: list[Row]) -> tuple[list[dict], list[str]]:
    faults = [r for r in rows if r.state in ("5", "FAULT")]
    overflow = any(r.overflow for r in rows)
    final_states = {r.final_state for r in rows}
    groups = segments(rows)
    report = []
    reasons = []
    metadata = {(g[0].wheel, g[0].direction) for g in groups if g}
    if len(metadata) != 1:
        reasons.append("data must contain exactly one wheel and one direction")
    targets = [round(abs(g[0].target)) for g in groups if g]
    if targets != EXPECTED:
        reasons.append(f"expected five plateaus {EXPECTED}; found {targets}")
    if faults or 5 in final_states:
        reasons.append("FAULT state present")
    if final_states != {3}:
        reasons.append("final_state must be COMPLETE (3)")
    if overflow:
        reasons.append("log_overflow is set")
    for index, group in enumerate(groups):
        target = round(abs(group[0].target))
        signed_speeds = [r.sign * r.measured for r in group]
        tail = signed_speeds[max(0, int(len(group) * 0.70)):]
        count = len(group)
        mean = statistics.fmean(tail) if tail else float("nan")
        stddev = statistics.pstdev(tail) if len(tail) > 1 else 0.0
        error = target - mean if math.isfinite(mean) else float("inf")
        maximum = max(signed_speeds) if signed_speeds else float("nan")
        minimum = min(signed_speeds) if signed_speeds else float("nan")

        previous_target = 0 if index == 0 else round(abs(groups[index - 1][0].target))

        if target >= previous_target:
            transition = "STEP_UP"
            transient_peak = maximum
            transient_pct = max(
                0.0,
                (maximum - target) * 100.0 / target
            )
        else:
            transition = "STEP_DOWN"
            transient_peak = minimum
            transient_pct = max(
                0.0,
                (target - minimum) * 100.0 / target
            )
        tail_rows = group[max(0, int(count * 0.70)):]
        means = {name: statistics.fmean(getattr(r, attr) for r in tail_rows) if tail_rows else float("nan")
                 for name, attr in (("pwm", "pwm"), ("u_ff", "ff"), ("u_p", "up"), ("u_i", "ui"))}
        allowed = max(0.05 * target, 50.0)
        saturated = [r for r in group if r.pwm >= 399.5]
        saturation_ms = sum(r.dt_ms for r in saturated)

        # Encoder speed is quantized. At 20 ms, one encoder count
        # corresponds to about 50 counts/s. Do not classify normal
        # +/-1-count toggling around the target as sustained oscillation.
        median_dt_ms = statistics.median(r.dt_ms for r in group)
        cps_per_count = 1000.0 / median_dt_ms

        errors = [target - v for v in tail]
        crossings = sum(
            1
            for a, b in zip(errors, errors[1:])
            if (a < 0 <= b) or (a >= 0 > b)
        )

        oscillation_stddev_limit = max(
            0.05 * target,
            1.5 * cps_per_count,
        )

        oscillation = (
            len(tail) >= 10
            and crossings >= 4
            and stddev > oscillation_stddev_limit
        )
        ok = count >= 50 and len(tail) >= 10
        local_reasons = []
        if not ok: local_reasons.append("insufficient samples (need >=50 per plateau)")
        if abs(error) > allowed: local_reasons.append("steady-state error exceeds limit")
        transient_abs = abs(transient_peak - target)
        transient_abs_limit = max(
            0.15 * target,
            2.0 * cps_per_count,
        )

        if transient_abs > transient_abs_limit:
            if transition == "STEP_UP":
                local_reasons.append(
                    "step-up overshoot exceeds quantization-aware limit"
                )
            else:
                local_reasons.append(
                    "step-down undershoot exceeds quantization-aware limit"
                )
        if oscillation: local_reasons.append("obvious sustained oscillation heuristic triggered")
        if saturation_ms > 250: local_reasons.append("output saturation exceeds 250 ms")
        report.append({"target": target, "mean": mean, "error": error,
                       "error_pct": abs(error) * 100.0 / target,
                       "maximum": maximum,
                       "minimum": minimum,
                       "transition": transition,
                       "transient_peak": transient_peak,
                       "transient_pct": transient_pct,
                       "stddev": stddev, "count": count, "means": means,
                       "pass": not local_reasons, "reasons": local_reasons})
    if not report:
        reasons.append("no nonzero RUN_PROFILE plateaus found")
    return report, reasons


def format_report(rows: list[Row]) -> tuple[str, bool]:
    plateaus, global_reasons = analyze(rows)
    wheel = plateaus and rows[0].wheel or "unknown"
    direction = plateaus and rows[0].direction or "unknown"
    lines = [f"PID-1A analysis: {wheel} {direction}",
             "target_cps | transition | mean_cps | steady_error_cps | steady_error_pct | transient_peak_cps | transient_pct | mean_pwm | mean_ff | mean_up | mean_ui | pop_stddev | n | result"]
    for p in plateaus:
        m = p["means"]
        lines.append(f"{p['target']:>10} | {p['transition']:>10} | {p['mean']:>8.1f} | {p['error']:>16.1f} | {p['error_pct']:>16.2f} | {p['transient_peak']:>18.1f} | {p['transient_pct']:>13.2f} | {m['pwm']:>8.1f} | {m['u_ff']:>7.1f} | {m['u_p']:>6.1f} | {m['u_i']:>6.1f} | {p['stddev']:>10.1f} | {p['count']:>3} | {'PASS' if p['pass'] else 'FAIL'}")
        for reason in p["reasons"]:
            lines.append("  - " + reason)
    passed = bool(plateaus) and not global_reasons and all(p["pass"] for p in plateaus)
    lines.append("Overall: " + ("PASS" if passed else "FAIL"))
    for reason in global_reasons:
        lines.append("  - " + reason)
    lines.append("Note: acceptance is an offline initial screening heuristic, not hardware safety or final gain validation.")
    return "\n".join(lines), passed


def _fixture() -> str:
    fields = ["timestamp_ms", "state", "selected_wheel", "direction", "target_cps", "measured_cps", "error_cps", "u_ff_permille", "u_p_permille", "u_i_permille", "u_output_permille", "encoder_delta", "dt_ms", "log_overflow", "final_state"]
    out = [",".join(fields)]
    now = 0
    for target in EXPECTED:
        for i in range(60):
            now += 20
            out.append(f"{now},2,0,1,{target},{target},{0},150,0,0,150,10,20,0,3")
    return "\n".join(out) + "\n"


def self_test() -> None:
    import io
    perfect = parse_csv(io.StringIO(_fixture()))
    text, passed = format_report(perfect)
    assert passed and "Overall: PASS" in text, text
    plateau_report, _ = analyze(perfect)
    assert [p["transition"] for p in plateau_report] == [
        "STEP_UP", "STEP_UP", "STEP_UP", "STEP_DOWN", "STEP_DOWN"
    ]
    quantized_lines = _fixture().splitlines()
    for row_index in range(1, 61):
        columns = quantized_lines[row_index].split(",")
        target = int(columns[4])
        measured = target + (50 if row_index % 2 else -50)
        columns[5] = str(measured)
        columns[6] = str(target - measured)
        quantized_lines[row_index] = ",".join(columns)
    _, passed = format_report(parse_csv(io.StringIO("\n".join(quantized_lines) + "\n")))
    assert passed, "quantization-like +/-1-count tracking must not false-fail"
    bad_error = _fixture().replace(",500,500,0,150,", ",500,300,200,150,")
    _, passed = format_report(parse_csv(io.StringIO(bad_error)))
    assert not passed, "steady error violation must fail"
    bad_overshoot = _fixture().replace(",500,500,0,150,", ",500,700,-200,150,", 1)
    _, passed = format_report(parse_csv(io.StringIO(bad_overshoot)))
    assert not passed, "overshoot violation must fail"
    for invalid in ("", "timestamp_ms,state\n1,2\n", _fixture().replace(",150,0,0,150,10,20,0", ",NaN,0,0,150,10,20,0", 1)):
        try:
            parse_csv(io.StringIO(invalid))
        except CsvError:
            pass
        else:
            raise AssertionError("missing/invalid CSV must be rejected")
    print("PID-1 analyzer self-test: PASS")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", nargs="?", type=Path, help="PID-1 RAM CSV export")
    parser.add_argument("--self-test", action="store_true", help="run synthetic offline tests")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0
    if args.csv is None:
        parser.error("provide a CSV path or --self-test")
    try:
        with args.csv.open("r", newline="", encoding="utf-8") as stream:
            rows = parse_csv(stream)
    except (OSError, CsvError) as exc:
        print(f"CSV ERROR: {exc}", file=sys.stderr)
        return 2
    text, passed = format_report(rows)
    print(text)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
