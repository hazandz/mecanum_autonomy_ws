#!/usr/bin/env python3
"""Analyze PID-2A four-wheel simultaneous speed-lab CSV exports."""
import argparse
import csv
import math
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

WHEELS = ("fl", "fr", "rl", "rr")
WHEEL_LABELS = {"fl": "FL", "fr": "FR", "rl": "RL", "rr": "RR"}
EXPECTED = [500, 1000, 1400, 1000, 500]
MODE = {"1": ("ALL_FORWARD", 1.0), "2": ("ALL_REVERSE", -1.0),
        "ALL_FORWARD": ("ALL_FORWARD", 1.0), "ALL_REVERSE": ("ALL_REVERSE", -1.0)}
REQUIRED = {
    "timestamp_ms", "state", "mode", "target_cps", "dt_ms",
    "sync_spread_cps", "sync_warning", "log_overflow", "final_state",
}
for wheel in WHEELS:
    REQUIRED.update({
        f"{wheel}_measured_cps", f"{wheel}_error_cps",
        f"{wheel}_u_ff_permille", f"{wheel}_u_i_permille",
        f"{wheel}_u_output_permille", f"{wheel}_encoder_delta",
    })


class CsvError(ValueError):
    pass


@dataclass
class Row:
    timestamp_ms: int
    state: str
    mode: str
    sign: float
    target: float
    dt_ms: int
    measured: dict[str, float]
    error: dict[str, float]
    ff: dict[str, float]
    ui: dict[str, float]
    output: dict[str, float]
    delta: dict[str, int]
    spread: float
    sync_warning: int
    overflow: int
    final_state: int


def number(value: str, field: str, line: int) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise CsvError(f"line {line}: invalid {field}: {value!r}") from exc
    if not math.isfinite(result):
        raise CsvError(f"line {line}: non-finite {field}")
    return result


def parse_csv(stream: Iterable[str]) -> list[Row]:
    reader = csv.DictReader(stream)
    if reader.fieldnames is None:
        raise CsvError("CSV is empty or has no header")
    missing = REQUIRED - set(reader.fieldnames)
    if missing:
        raise CsvError("missing columns: " + ", ".join(sorted(missing)))
    rows = []
    for line, raw in enumerate(reader, start=2):
        mode_key = (raw.get("mode") or "").strip().upper()
        if mode_key not in MODE:
            raise CsvError(f"line {line}: invalid mode {mode_key!r}")
        state = (raw.get("state") or "").strip().upper()
        try:
            timestamp = int(number(raw["timestamp_ms"], "timestamp_ms", line))
            dt_ms = int(number(raw["dt_ms"], "dt_ms", line))
            sync_warning = int(number(raw["sync_warning"], "sync_warning", line))
            overflow = int(number(raw["log_overflow"], "log_overflow", line))
            final_state = int(number(raw["final_state"], "final_state", line))
        except (OverflowError, ValueError) as exc:
            if isinstance(exc, CsvError):
                raise
            raise CsvError(f"line {line}: invalid integer field") from exc
        if dt_ms <= 0 or sync_warning not in (0, 1) or overflow not in (0, 1):
            raise CsvError(f"line {line}: invalid dt_ms or status flag")
        if final_state not in (0, 1, 2, 3, 4, 5):
            raise CsvError(f"line {line}: invalid final_state")
        measured, error, ff, ui, output, delta = {}, {}, {}, {}, {}, {}
        for wheel in WHEELS:
            measured[wheel] = number(raw[f"{wheel}_measured_cps"], f"{wheel}_measured_cps", line)
            error[wheel] = number(raw[f"{wheel}_error_cps"], f"{wheel}_error_cps", line)
            ff[wheel] = number(raw[f"{wheel}_u_ff_permille"], f"{wheel}_u_ff_permille", line)
            ui[wheel] = number(raw[f"{wheel}_u_i_permille"], f"{wheel}_u_i_permille", line)
            output[wheel] = number(raw[f"{wheel}_u_output_permille"], f"{wheel}_u_output_permille", line)
            delta[wheel] = int(number(raw[f"{wheel}_encoder_delta"], f"{wheel}_encoder_delta", line))
        target_cps = number(raw["target_cps"], "target_cps", line)
        if abs(target_cps) >= 0.5 and target_cps * MODE[mode_key][1] < 0.0:
            raise CsvError(f"line {line}: target sign conflicts with mode")
        sync_spread = number(raw["sync_spread_cps"], "sync_spread_cps", line)
        if sync_spread < 0.0:
            raise CsvError(f"line {line}: sync_spread_cps must be nonnegative")
        rows.append(Row(timestamp, state, MODE[mode_key][0], MODE[mode_key][1],
                        target_cps, dt_ms,
                        measured, error, ff, ui, output, delta,
                        sync_spread, sync_warning, overflow, final_state))
    if not rows:
        raise CsvError("CSV contains no samples")
    return rows


def plateau_groups(rows: list[Row]) -> list[list[Row]]:
    groups: list[list[Row]] = []
    previous = None
    for row in rows:
        if row.state not in ("2", "RUN_PROFILE") or abs(row.target) < 0.5:
            previous = None
            continue
        key = (row.mode, round(abs(row.target)))
        if key != previous:
            groups.append([])
            previous = key
        groups[-1].append(row)
    return groups


def _mean_tail(values: list[float]) -> tuple[float, float]:
    tail = values[max(0, int(len(values) * 0.70)):]
    if not tail:
        return float("nan"), 0.0
    return statistics.fmean(tail), statistics.pstdev(tail) if len(tail) > 1 else 0.0


def analyze(rows: list[Row]) -> tuple[list[dict], list[str]]:
    groups = plateau_groups(rows)
    global_errors = []
    results = []
    modes = {row.mode for row in rows}
    targets = [round(abs(group[0].target)) for group in groups if group]
    if len(modes) != 1:
        global_errors.append("CSV must contain exactly one runtime mode")
    if targets != EXPECTED:
        global_errors.append(f"expected plateaus {EXPECTED}; found {targets}")
    if any(row.state in ("5", "FAULT") or row.final_state == 5 for row in rows):
        global_errors.append("FAULT state present")
    if any(row.overflow for row in rows):
        global_errors.append("log_overflow is set")
    if {row.final_state for row in rows} != {3}:
        global_errors.append("final_state must be COMPLETE (3)")

    previous_target = 0
    for group in groups:
        target = round(abs(group[0].target))
        transition = "STEP_UP" if target >= previous_target else "STEP_DOWN"
        speeds = {wheel: [row.sign * row.measured[wheel] for row in group] for wheel in WHEELS}
        dt_quant = statistics.median(row.dt_ms for row in group)
        cps_per_count = 1000.0 / dt_quant
        sample_period = statistics.median(
            [b.timestamp_ms - a.timestamp_ms for a, b in zip(group, group[1:])]
        ) if len(group) > 1 else float(dt_quant * 2)
        wheel_metrics = {}
        wheel_failed = False
        for wheel in WHEELS:
            values = speeds[wheel]
            mean, stddev = _mean_tail(values)
            error = target - mean
            max_speed = max(values)
            min_speed = min(values)
            if transition == "STEP_UP":
                transient = max(0.0, max_speed - target)
                transient_name = "overshoot"
            else:
                transient = max(0.0, target - min_speed)
                transient_name = "undershoot"
            transient_pct = transient * 100.0 / target
            tail_start = max(0, int(len(group) * 0.70))
            tail_rows = group[tail_start:]
            mean_ff = statistics.fmean(row.ff[wheel] for row in tail_rows)
            mean_ui = statistics.fmean(row.ui[wheel] for row in tail_rows)
            mean_pwm = statistics.fmean(row.output[wheel] for row in tail_rows)
            sat_ms = sum(sample_period for row in group if row.output[wheel] >= 399.5)
            tail_errors = [target - value for value in values[tail_start:]]
            crossings = sum(1 for a, b in zip(tail_errors, tail_errors[1:])
                            if (a < 0 <= b) or (a >= 0 > b))
            oscillation_limit = max(0.05 * target, 1.5 * cps_per_count)
            oscillation = (len(tail_errors) >= 10 and crossings >= 4 and
                           stddev > oscillation_limit)
            allowed_error = max(0.05 * target, 50.0)
            allowed_transient = max(0.15 * target, 2.0 * cps_per_count)
            reasons = []
            if len(group) < 30 or len(tail_rows) < 8:
                reasons.append("insufficient samples")
            if abs(error) > allowed_error:
                reasons.append("steady-state error exceeds limit")
            if transient > allowed_transient:
                reasons.append(f"quantization-aware {transient_name} exceeds limit")
            if oscillation:
                reasons.append("sustained oscillation heuristic triggered")
            if sat_ms > 250.0:
                reasons.append("output saturation exceeds 250 ms")
            if reasons:
                wheel_failed = True
            wheel_metrics[wheel] = {
                "mean": mean, "error": error, "error_pct": abs(error) * 100.0 / target,
                "stddev": stddev, "mean_ff": mean_ff, "mean_ui": mean_ui,
                "mean_pwm": mean_pwm, "transient_name": transient_name,
                "transient": transient, "transient_pct": transient_pct,
                "saturation_ms": sat_ms, "pass": not reasons, "reasons": reasons,
            }
        spreads = [row.spread for row in group]
        sync_mean = statistics.fmean(spreads)
        sync_p95 = sorted(spreads)[min(len(spreads) - 1, math.ceil(0.95 * len(spreads)) - 1)]
        sync_max = max(spreads)
        sync_limit = max(0.10 * target, 100.0)
        sync_pass = sync_p95 <= sync_limit
        if not sync_pass:
            wheel_failed = True
        results.append({"target": target, "transition": transition,
                        "wheel_metrics": wheel_metrics, "sync_mean": sync_mean,
                        "sync_p95": sync_p95, "sync_max": sync_max,
                        "sync_limit": sync_limit, "sync_pass": sync_pass,
                        "pass": not wheel_failed})
        previous_target = target
    if not results:
        global_errors.append("no nonzero RUN_PROFILE plateaus found")
    return results, global_errors


def pid1_baseline(path: Path) -> dict[tuple[str, str, int], float]:
    """Read optional PID-1 CSV and derive mean positive I per wheel/direction/target."""
    grouped: dict[tuple[str, str, int], list[float]] = {}
    with path.open("r", newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        required = {"selected_wheel", "direction", "target_cps", "state", "u_i_permille"}
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise CsvError("PID-1 baseline CSV needs selected_wheel,direction,target_cps,state,u_i_permille")
        for line, row in enumerate(reader, start=2):
            state = (row["state"] or "").strip().upper()
            if state not in ("2", "RUN_PROFILE"):
                continue
            wheel = (row["selected_wheel"] or "").strip().upper()
            direction = (row["direction"] or "").strip().upper()
            wheel_alias = {"0": "FL", "1": "FR", "2": "RL", "3": "RR"}
            wheel = wheel_alias.get(wheel, wheel)
            direction_alias = {"1": "ALL_FORWARD", "2": "ALL_REVERSE",
                               "FORWARD": "ALL_FORWARD", "REVERSE": "ALL_REVERSE"}
            direction = direction_alias.get(direction, direction)
            if wheel not in WHEEL_LABELS.values() or direction not in ("ALL_FORWARD", "ALL_REVERSE"):
                raise CsvError(f"PID-1 baseline line {line}: invalid wheel/direction")
            target = round(abs(number(row["target_cps"], "target_cps", line)))
            ui = number(row["u_i_permille"], "u_i_permille", line)
            grouped.setdefault((wheel, direction, target), []).append(ui)
    return {key: statistics.fmean(values) for key, values in grouped.items()}


SHARED_LOADING_MIN_I_INCREASE = 10.0


def report(rows: list[Row], baseline: dict | None = None) -> tuple[str, bool]:
    plateaus, global_errors = analyze(rows)
    mode = next(iter({row.mode for row in rows}), "UNKNOWN")
    lines = [f"PID-2A analysis: {mode}",
             "Each wheel row reports mean/steady metrics from the last 30% of that plateau; transient spans the full plateau.",
             "plateau transition wheel mean_cps steady_error_cps error_pct pop_stddev mean_ff mean_I mean_PWM transient saturation_ms result"]
    for plateau in plateaus:
        lines.append(f"{plateau['target']} cps {plateau['transition']} sync_mean={plateau['sync_mean']:.1f} sync_p95={plateau['sync_p95']:.1f} sync_max={plateau['sync_max']:.1f} cps (limit p95 {plateau['sync_limit']:.1f}): {'PASS' if plateau['sync_pass'] else 'FAIL'}")
        for wheel in WHEELS:
            metric = plateau["wheel_metrics"][wheel]
            lines.append(f"{wheel.upper():>2} {metric['mean']:>9.1f} {metric['error']:>16.1f} {metric['error_pct']:>9.2f}% {metric['stddev']:>10.1f} {metric['mean_ff']:>7.1f} {metric['mean_ui']:>7.1f} {metric['mean_pwm']:>8.1f} {metric['transient_name']}={metric['transient']:.1f} ({metric['transient_pct']:.2f}%) {metric['saturation_ms']:.0f} {'PASS' if metric['pass'] else 'FAIL'}")
            for reason in metric["reasons"]:
                lines.append(f"    - {reason}")
        if baseline is not None:
            direction = "ALL_FORWARD" if mode == "ALL_FORWARD" else "ALL_REVERSE"
            target = plateau["target"]
            compared = []
            for wheel in WHEELS:
                key = (WHEEL_LABELS[wheel], direction, target)
                if key in baseline:
                    current = plateau["wheel_metrics"][wheel]["mean_ui"]
                    base = baseline[key]
                    if current > max(0.0, base) + SHARED_LOADING_MIN_I_INCREASE:
                        compared.append(wheel)
            if len(compared) == 4:
                lines.append("Possible shared-supply loading indication: all four mean positive integrals exceed their PID-1 baselines by more than the configured threshold. This is not a voltage-sag measurement.")
    passed = bool(plateaus) and not global_errors and all(p["pass"] for p in plateaus)
    lines.append("Overall: " + ("PASS" if passed else "FAIL"))
    for reason in global_errors:
        lines.append("  - " + reason)
    lines.append("Note: offline screening only; this does not establish hardware safety or runtime acceptance.")
    return "\n".join(lines), passed


def _fixture() -> str:
    fields = ["timestamp_ms", "state", "mode", "target_cps", "dt_ms"]
    for wheel in WHEELS:
        fields.extend([f"{wheel}_measured_cps", f"{wheel}_error_cps",
                       f"{wheel}_u_ff_permille", f"{wheel}_u_i_permille",
                       f"{wheel}_u_output_permille", f"{wheel}_encoder_delta"])
    fields.extend(["sync_spread_cps", "sync_warning", "log_overflow", "final_state"])
    output = [",".join(fields)]
    timestamp = 0
    for target in EXPECTED:
        for _ in range(38):
            timestamp += 40
            values = [str(timestamp), "2", "1", str(target), "20"]
            for _wheel in WHEELS:
                values.extend([str(target), "0", "150", "0", "150", "10"])
            values.extend(["0", "0", "0", "3"])
            output.append(",".join(values))
    return "\n".join(output) + "\n"


def self_test() -> None:
    import io
    perfect_text = _fixture()
    perfect = parse_csv(io.StringIO(perfect_text))
    summary, passed = report(perfect)
    assert passed and "Overall: PASS" in summary, summary
    plateaus, _ = analyze(perfect)
    assert [p["transition"] for p in plateaus] == [
        "STEP_UP", "STEP_UP", "STEP_UP", "STEP_DOWN", "STEP_DOWN"
    ]

    # One wheel's steady-state error must fail even when the other three track.
    lines = perfect_text.splitlines()
    for index in range(1, 39):
        fields = lines[index].split(",")
        fields[5] = "0"  # FL measured speed; columns 5/6 are FL speed/error.
        fields[6] = fields[3]
        lines[index] = ",".join(fields)
    _, passed = report(parse_csv(io.StringIO("\n".join(lines) + "\n")))
    assert not passed, "one-wheel error must fail"

    # Restore and create a p95 synchronization violation on the first plateau.
    lines = perfect_text.splitlines()
    for index in range(1, 39):
        fields = lines[index].split(",")
        fields[5] = "700"
        fields[6] = str(int(fields[3]) - 700)
        fields[-4] = "200"  # sync spread before final status fields
        lines[index] = ",".join(fields)
    _, passed = report(parse_csv(io.StringIO("\n".join(lines) + "\n")))
    assert not passed, "excessive synchronization spread must fail"

    for column, value in ((-1, "5"), (-2, "1")):
        lines = perfect_text.splitlines()
        fields = lines[1].split(",")
        fields[column] = value
        lines[1] = ",".join(fields)
        _, passed = report(parse_csv(io.StringIO("\n".join(lines) + "\n")))
        assert not passed, "FAULT/overflow metadata must fail"

    # STEP_UP/STEP_DOWN chatter of +/- one 20 ms encoder count (50 cps) is allowed.
    lines = perfect_text.splitlines()
    for index in range(1, 39):
        fields = lines[index].split(",")
        target = int(fields[3])
        measured = target + (50 if index % 2 else -50)
        for wheel_index in range(4):
            base = 5 + wheel_index * 6
            fields[base] = str(measured)
            fields[base + 1] = str(target - measured)
        fields[-4] = "0"
        lines[index] = ",".join(fields)
    _, passed = report(parse_csv(io.StringIO("\n".join(lines) + "\n")))
    assert passed, "quantization-like +/-1-count behavior must not false-fail"

    for invalid in ("", "timestamp_ms,state\n1,2\n",
                    perfect_text.replace(",150,0,150,10,", ",NaN,0,150,10,", 1)):
        try:
            parse_csv(io.StringIO(invalid))
        except CsvError:
            pass
        else:
            raise AssertionError("invalid CSV must be rejected")
    print("PID-2 analyzer self-test: PASS")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", nargs="?", type=Path, help="PID-2 RAM CSV export")
    parser.add_argument("--pid1-baseline", type=Path,
                        help="optional PID-1 CSV for shared-loading comparison")
    parser.add_argument("--self-test", action="store_true", help="run offline synthetic checks")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0
    if args.csv is None:
        parser.error("provide a CSV path or --self-test")
    try:
        with args.csv.open("r", newline="", encoding="utf-8") as stream:
            rows = parse_csv(stream)
        baseline = pid1_baseline(args.pid1_baseline) if args.pid1_baseline else None
    except (OSError, CsvError) as exc:
        print(f"CSV ERROR: {exc}", file=sys.stderr)
        return 2
    text, passed = report(rows, baseline)
    print(text)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
