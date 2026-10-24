#!/usr/bin/env python3
"""Analyze PID-0 STM32 CSV captures using only the Python standard library."""
import argparse
import csv
import io
import math
import statistics
import sys
from collections import defaultdict

WHEELS = ("FL", "FR", "RL", "RR")
REQUIRED = {
    "timestamp_ms", "state", "selected_wheel", "direction", "duty_permille",
    "fl_delta", "fr_delta", "rl_delta", "rr_delta",
    "fl_counts_per_sec", "fr_counts_per_sec", "rl_counts_per_sec", "rr_counts_per_sec",
}
SPEED_COLUMN = {"FL": "fl_counts_per_sec", "FR": "fr_counts_per_sec",
                "RL": "rl_counts_per_sec", "RR": "rr_counts_per_sec"}


def parse_rows(stream):
    reader = csv.DictReader(stream)
    if reader.fieldnames is None:
        raise ValueError("CSV is empty or has no header")
    missing = REQUIRED.difference(reader.fieldnames)
    if missing:
        raise ValueError("missing CSV columns: " + ", ".join(sorted(missing)))
    rows = []
    for line_number, raw in enumerate(reader, start=2):
        try:
            wheel = raw["selected_wheel"].strip().upper()
            direction = raw["direction"].strip().upper()
            if wheel not in WHEELS or direction not in ("FORWARD", "REVERSE"):
                raise ValueError("invalid wheel or direction")
            row = {
                "timestamp_ms": int(raw["timestamp_ms"]) & 0xFFFFFFFF,
                "state": int(raw["state"]),
                "selected_wheel": wheel,
                "direction": direction,
                "duty_permille": int(raw["duty_permille"]),
            }
            for name in SPEED_COLUMN.values():
                value = float(raw[name])
                if not math.isfinite(value):
                    raise ValueError("non-finite speed")
                row[name] = value
            rows.append(row)
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"invalid CSV row {line_number}: {exc}") from exc
    return rows


def fit_line(points):
    """Least-squares y=a+b*x for (x,y) pairs; returns a,b,R^2."""
    if len(points) < 2:
        return None
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    xbar, ybar = statistics.mean(xs), statistics.mean(ys)
    denom = sum((x - xbar) ** 2 for x in xs)
    if denom <= 0.0:
        return None
    slope = sum((x - xbar) * (y - ybar) for x, y in points) / denom
    intercept = ybar - slope * xbar
    residual = sum((y - (intercept + slope * x)) ** 2 for x, y in points)
    total = sum((y - ybar) ** 2 for y in ys)
    r_squared = 1.0 if total == 0.0 and residual == 0.0 else (
        0.0 if total == 0.0 else 1.0 - residual / total)
    return intercept, slope, r_squared


def steady_points(rows):
    """One robust steady-state estimate per wheel/direction/duty from MEASURE rows."""
    groups = defaultdict(list)
    for row in rows:
        # PID-0 state 3 is MEASURE; accept named state in hand-edited captures too.
        if row["state"] not in (3,):
            continue
        wheel = row["selected_wheel"]
        signed = row[SPEED_COLUMN[wheel]]
        groups[(wheel, row["direction"], row["duty_permille"])].append(abs(signed))
    estimates = {}
    for key, values in groups.items():
        tail = values[len(values) // 2:] or values
        estimates[key] = (statistics.mean(tail), statistics.pstdev(tail), len(values))
    return estimates


def estimate_tau(rows, wheel, direction, duty, steady):
    """Estimate step time to 63.2% of measured steady speed from first powered sample."""
    seq = [r for r in rows if r["selected_wheel"] == wheel and
           r["direction"] == direction and r["duty_permille"] == duty and
           r["state"] in (2, 3)]
    if len(seq) < 3 or steady <= 0.0:
        return None
    start = seq[0]["timestamp_ms"]
    threshold = 0.6321205588 * steady
    for row in seq:
        speed = abs(row[SPEED_COLUMN[wheel]])
        if speed >= threshold:
            dt = (row["timestamp_ms"] - start) & 0xFFFFFFFF
            return dt / 1000.0
    return None


def analyze(rows, out):
    estimates = steady_points(rows)
    tau_values, seed_values = [], []
    for wheel in WHEELS:
        for direction in ("FORWARD", "REVERSE"):
            print(f"\n{wheel} {direction}", file=out)
            items = sorted((duty, val) for (w, dr, duty), val in estimates.items()
                           if w == wheel and dr == direction)
            if not items:
                print("  no MEASURE samples", file=out)
                continue
            moving = [(duty, mean, sd, n) for duty, (mean, sd, n) in items if mean > 0.0]
            first = min((x[0] for x in moving), default=None)
            print("  first duty with measurable movement: " +
                  ("none observed" if first is None else f"{first} permille"), file=out)
            print("  duty_permille,steady_counts_per_sec,population_stddev,n", file=out)
            for duty, mean, sd, n in items:
                print(f"  {duty},{mean:.6f},{sd:.6f},{n}", file=out)
            fit = fit_line([(mean, duty) for duty, mean, _sd, _n in moving])
            if fit is None:
                print("  feedforward fit: insufficient distinct moving points", file=out)
                continue
            u0, kv, r2 = fit
            print(f"  duty_permille = u0 + kv * abs(counts_per_second)", file=out)
            print(f"  u0={u0:.6f} permille, kv={kv:.9f} permille/(count/s), R^2={r2:.6f}", file=out)
            # Highest moving duty is used for a coarse first-order step estimate.
            duty, (mean, _sd, _n) = max(
                ((d, e) for (w, dr, d), e in estimates.items()
                 if w == wheel and dr == direction and e[0] > 0.0),
                default=(None, (0.0, 0.0, 0)))
            if duty is not None:
                tau = estimate_tau(rows, wheel, direction, duty, mean)
                if tau is not None and tau > 0.0:
                    gain = mean / float(duty)  # counts/s per permille
                    # Conservative IMC-style starting point: lambda=2*tau, delay assumed zero.
                    kp = 1.0 / (3.0 * gain)
                    ki = kp / (2.0 * tau)
                    tau_values.append(tau)
                    seed_values.append((wheel, direction, kp, ki, tau))
                    print(f"  step estimate: steady gain={gain:.9f} counts/s/permille, tau={tau:.6f} s", file=out)
                else:
                    print("  step estimate: insufficient response samples to estimate tau", file=out)
    print("\nCONSERVATIVE_PI_SEED", file=out)
    print("Initial suggestion only; not validated gains. PI output units are permille and error units are counts/s.", file=out)
    if not seed_values:
        print("unavailable: no usable step response and moving steady-state data", file=out)
    else:
        for wheel, direction, kp, ki, tau in seed_values:
            print(f"{wheel} {direction}: Kp={kp:.9g}, Ki={ki:.9g}, tau={tau:.6g} s", file=out)


def self_test():
    buf = io.StringIO()
    buf.write("timestamp_ms,state,selected_wheel,direction,duty_permille,fl_delta,fr_delta,rl_delta,rr_delta,fl_counts_per_sec,fr_counts_per_sec,rl_counts_per_sec,rr_counts_per_sec\n")
    # Deadzone at 100; moving steady points satisfy duty = 100 + 2*speed.
    for duty, speed in ((100, 0.0), (150, 25.0), (200, 50.0)):
        for _ in range(4):
            buf.write(f"0,3,FL,FORWARD,{duty},0,0,0,0,{speed},0,0,0\n")
    # A synthetic first-order 300 permille response with tau ~= 100 ms.
    for t in range(0, 501, 20):
        speed = 100.0 * (1.0 - math.exp(-t / 100.0))
        state = 2 if t < 100 else 3
        buf.write(f"{t},{state},FR,FORWARD,300,0,0,0,0,0,{speed},0,0\n")
    rows = parse_rows(io.StringIO(buf.getvalue()))
    assert len(rows) == 38
    estimates = steady_points(rows)
    assert estimates[("FL", "FORWARD", 100)][0] == 0.0
    assert estimates[("FL", "FORWARD", 150)][0] == 25.0
    moving = [(mean, duty) for (wheel, direction, duty), (mean, _sd, _n) in estimates.items()
              if wheel == "FL" and direction == "FORWARD" and mean > 0]
    fit = fit_line(moving)
    assert fit and abs(fit[0] - 100.0) < 1e-9 and abs(fit[1] - 2.0) < 1e-9
    assert min(d for (w, dr, d), (m, _sd, _n) in estimates.items()
               if w == "FL" and dr == "FORWARD" and m > 0) == 150
    tau = estimate_tau(rows, "FR", "FORWARD", 300, 100.0)
    assert tau is not None and abs(tau - 0.1) <= 0.02
    # Parser must reject an incomplete schema.
    try:
        parse_rows(io.StringIO("timestamp_ms,state\n0,3\n"))
    except ValueError:
        pass
    else:
        raise AssertionError("incomplete CSV was accepted")
    print("PID-0 analyzer self-test: PASS")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_file", nargs="?", help="PID-0 CSV dump")
    parser.add_argument("--self-test", action="store_true", help="run synthetic offline checks")
    args = parser.parse_args(argv)
    if args.self_test:
        self_test()
        return 0
    if not args.csv_file:
        parser.error("provide a CSV file or --self-test")
    try:
        with open(args.csv_file, newline="", encoding="utf-8") as stream:
            rows = parse_rows(stream)
        analyze(rows, sys.stdout)
    except (OSError, ValueError) as exc:
        print(f"pid0_analyze: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
