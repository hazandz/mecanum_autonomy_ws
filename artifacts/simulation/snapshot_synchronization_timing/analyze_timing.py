#!/usr/bin/env python3
"""Offline, read-only timing analysis for /scan and /odom evidence traces."""

from __future__ import annotations

import argparse
import bisect
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any


ANALYSIS_MARGIN_NS = 1_000_000


def quantile(values: list[int], probability: float) -> int | None:
    """Return a deterministic nearest-rank quantile without float samples."""

    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(probability * len(ordered)) - 1)]


def integer_stats(values: list[int]) -> dict[str, int | None]:
    """Return compact statistics for values in one already-defined time domain."""

    if not values:
        return {"count": 0, "min": None, "p50": None, "p95": None, "p99": None, "max": None}
    return {
        "count": len(values),
        "min": min(values),
        "p50": int(median(values)),
        "p95": quantile(values, 0.95),
        "p99": quantile(values, 0.99),
        "max": max(values),
    }


def stream_summary(records: list[dict[str, int]]) -> dict[str, Any]:
    """Describe one trace stream while keeping ROS and steady times separate."""

    stamps = [record["stamp_ns"] for record in records]
    receives = [record["receive_steady_ns"] for record in records]
    stamp_deltas = [right - left for left, right in zip(stamps, stamps[1:])]
    receive_deltas = [right - left for left, right in zip(receives, receives[1:])]
    duration_ns = receives[-1] - receives[0] if len(receives) > 1 else 0
    return {
        "message_count": len(records),
        "duplicate_stamp_count": sum(delta == 0 for delta in stamp_deltas),
        "stamp_regression_count": sum(delta < 0 for delta in stamp_deltas),
        "receive_regression_count": sum(delta < 0 for delta in receive_deltas),
        "ros_stamp_interval_ns": integer_stats([delta for delta in stamp_deltas if delta > 0]),
        "steady_receive_interarrival_ns": integer_stats([delta for delta in receive_deltas if delta > 0]),
        "observed_rate_hz": (len(records) - 1) * 1_000_000_000 / duration_ns if duration_ns > 0 else None,
    }


def nearest_pairs(
    scan_records: list[dict[str, int]], odom_records: list[dict[str, int]]
) -> list[dict[str, int]]:
    """Pair each scan with its deterministic nearest odom *by ROS stamp*.

    The signed wait is deliberately calculated only from two steady-clock values.
    It is evidence for buffered waiting, not a subtraction across time domains.
    """

    ordered_odom = sorted(odom_records, key=lambda record: (record["stamp_ns"], record["message_index"]))
    odom_stamps = [record["stamp_ns"] for record in ordered_odom]
    pairs: list[dict[str, int]] = []
    for scan in scan_records:
        position = bisect.bisect_left(odom_stamps, scan["stamp_ns"])
        candidate_indices = [index for index in (position - 1, position) if 0 <= index < len(ordered_odom)]
        if not candidate_indices:
            continue
        odom = min(
            (ordered_odom[index] for index in candidate_indices),
            key=lambda record: (abs(scan["stamp_ns"] - record["stamp_ns"]), record["stamp_ns"], record["message_index"]),
        )
        pairs.append(
            {
                "scan_message_index": scan["message_index"],
                "scan_stamp_ns": scan["stamp_ns"],
                "odom_message_index": odom["message_index"],
                "odom_stamp_ns": odom["stamp_ns"],
                "absolute_stamp_skew_ns": abs(scan["stamp_ns"] - odom["stamp_ns"]),
                "scan_receive_steady_ns": scan["receive_steady_ns"],
                "odom_receive_steady_ns": odom["receive_steady_ns"],
                "signed_receive_wait_ns": odom["receive_steady_ns"] - scan["receive_steady_ns"],
            }
        )
    return pairs


def tolerance_options(skews: list[int]) -> list[dict[str, Any]]:
    """Compare analysis-only pairing choices; this function does not approve one."""

    if not skews:
        return []
    p99 = quantile(skews, 0.99)
    assert p99 is not None
    options = [
        ("exact_only", 0, "No temporal mismatch accepted; vulnerable to any timestamp phase offset."),
        (
            "p99_plus_analysis_margin",
            p99 + ANALYSIS_MARGIN_NS,
            f"p99 nearest skew plus {ANALYSIS_MARGIN_NS} ns analysis margin; must be remeasured under load.",
        ),
        ("max_observed", max(skews), "Accepts every nearest-by-stamp pair in this trace; largest temporal mismatch is retained."),
    ]
    return [
        {
            "status": "PROPOSED_FROM_MEASUREMENT_PENDING_USER_APPROVAL",
            "option": name,
            "tolerance_ns": threshold,
            "accepted_pair_count": sum(skew <= threshold for skew in skews),
            "dropped_pair_count": sum(skew > threshold for skew in skews),
            "risk": risk,
        }
        for name, threshold, risk in options
    ]


def analyze_capture(input_dir: Path) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, int]]]:
    """Analyze a finished trace and persist per-pair evidence beside it."""

    records = [
        json.loads(line)
        for line in (input_dir / "trace.jsonl").read_text(encoding="utf-8").splitlines()
        if line
    ]
    metadata = json.loads((input_dir / "capture_metadata.json").read_text(encoding="utf-8"))
    streams = {stream: [record for record in records if record["stream"] == stream] for stream in ("scan", "odom")}
    pairs = nearest_pairs(streams["scan"], streams["odom"])
    skews = [pair["absolute_stamp_skew_ns"] for pair in pairs]
    waits = [pair["signed_receive_wait_ns"] for pair in pairs]
    nonzero_outliers = [pair for pair in pairs if pair["absolute_stamp_skew_ns"] > 0]
    summary: dict[str, Any] = {
        "analysis_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "streams": {stream: stream_summary(items) for stream, items in streams.items()},
        "nearest_by_stamp_candidate_count": len(pairs),
        "scan_without_any_odom_candidate_count": len(streams["scan"]) - len(pairs),
        "scan_to_nearest_odom_skew_ns": integer_stats(skews),
        "exact_stamp_match_count": sum(skew == 0 for skew in skews),
        "nonzero_stamp_skew_count": len(nonzero_outliers),
        "candidate_arrived_before_or_with_scan_count": sum(wait <= 0 for wait in waits),
        "candidate_arrived_after_scan_count": sum(wait > 0 for wait in waits),
        "signed_receive_wait_ns": integer_stats(waits),
        "positive_receive_wait_ns": integer_stats([wait for wait in waits if wait > 0]),
        "nonzero_stamp_skew_outliers": nonzero_outliers,
        "tolerance_options": tolerance_options(skews),
    }
    scan_rate = summary["streams"]["scan"]["observed_rate_hz"]
    odom_rate = summary["streams"]["odom"]["observed_rate_hz"]
    summary["rate_ratio_odom_to_scan"] = odom_rate / scan_rate if scan_rate else None
    (input_dir / "scan_odom_pairs.jsonl").write_text(
        "".join(json.dumps(pair, sort_keys=True) + "\n" for pair in pairs), encoding="utf-8"
    )
    (input_dir / "timing_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (input_dir / "Timing_Evidence_Report.md").write_text(render_capture_report(metadata, summary), encoding="utf-8")
    return metadata, summary, pairs


def stats_row(name: str, values: dict[str, int | None]) -> str:
    return "| {0} | {1} | {2} | {3} | {4} | {5} | {6} |".format(
        name, values["count"], values["min"], values["p50"], values["p95"], values["p99"], values["max"]
    )


def render_capture_report(metadata: dict[str, Any], summary: dict[str, Any]) -> str:
    """Render the single-run evidence with pairability facts, not a false claim."""

    streams = summary["streams"]
    outliers = summary["nonzero_stamp_skew_outliers"]
    lines = [
        "# Snapshot Synchronization Timing Evidence",
        "",
        f"Execution timestamp UTC: {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Scope",
        "",
        "- Collector subscriptions only: `/scan` and `/odom`; no publisher, `/cmd_vel`, reset, or service-control operation.",
        "- Header (ROS/simulation) stamps and steady receive times remain separate time domains.",
        f"- Capture duration steady ns: {metadata['duration_steady_ns']}; scans: {metadata['counts']['scan']}; odometry: {metadata['counts']['odom']}.",
        "",
        "## Stream and pair statistics (nanoseconds)",
        "",
        "| Metric | Count | Min | P50 | P95 | P99 | Max |",
        "| --- | --- | --- | --- | --- | --- | --- |",
        stats_row("scan ROS stamp interval", streams["scan"]["ros_stamp_interval_ns"]),
        stats_row("scan steady receive inter-arrival", streams["scan"]["steady_receive_interarrival_ns"]),
        stats_row("odom ROS stamp interval", streams["odom"]["ros_stamp_interval_ns"]),
        stats_row("odom steady receive inter-arrival", streams["odom"]["steady_receive_interarrival_ns"]),
        stats_row("nearest-by-stamp absolute skew", summary["scan_to_nearest_odom_skew_ns"]),
        stats_row("signed steady receive wait", summary["signed_receive_wait_ns"]),
        stats_row("positive steady receive wait", summary["positive_receive_wait_ns"]),
        "",
        "## Pairability evidence",
        "",
        f"- Nearest-by-stamp candidates: {summary['nearest_by_stamp_candidate_count']}; scans with no odom record available at all: {summary['scan_without_any_odom_candidate_count']}.",
        "- The latter is trace availability only, **not** evidence that a scan is pairable under a future tolerance.",
        f"- Exact stamp matches: {summary['exact_stamp_match_count']}; nonzero-skew pairs: {summary['nonzero_stamp_skew_count']}.",
        f"- Candidate received before/with scan: {summary['candidate_arrived_before_or_with_scan_count']}; after scan (buffer wait needed): {summary['candidate_arrived_after_scan_count']}.",
        "",
        "## Tolerance options — not approved",
        "",
        "| Status | Option | Tolerance ns | Accepted pairs | Dropped pairs | Temporal-mismatch risk |",
        "| --- | --- | --- | --- | --- |",
    ]
    lines.extend(
        "| {status} | {option} | {tolerance_ns} | {accepted_pair_count} | {dropped_pair_count} | {risk} |".format(**option)
        for option in summary["tolerance_options"]
    )
    lines.extend(["", "## Full nonzero-skew outliers", ""])
    if outliers:
        lines.extend([
            "| Scan stamp ns | Odom stamp ns | Absolute skew ns | Scan receive steady ns | Odom receive steady ns | Signed receive wait ns |",
            "| --- | --- | --- | --- | --- | --- |",
        ])
        lines.extend(
            "| {scan_stamp_ns} | {odom_stamp_ns} | {absolute_stamp_skew_ns} | {scan_receive_steady_ns} | {odom_receive_steady_ns} | {signed_receive_wait_ns} |".format(**pair)
            for pair in outliers
        )
    else:
        lines.append("No nonzero nearest-by-stamp skew occurred in this capture.")
    lines.extend([
        "",
        "## Limitations",
        "",
        "- Idle Gazebo only; no reset, delay/dropout, CPU contention, or command-motion evidence.",
        "- This report does not select a synchronizer tolerance, receive-age budget, or buffer capacity.",
        "- It is not deploy-real or hardware evidence and does not approve S.2.2A.",
    ])
    return "\n".join(lines) + "\n"


def render_multi_run_report(parent: Path, run_rows: list[dict[str, Any]], all_pairs: list[dict[str, int]]) -> str:
    """Render the required five-run comparison without selecting a contract value."""

    skews = [pair["absolute_stamp_skew_ns"] for pair in all_pairs]
    positive_waits = [pair["signed_receive_wait_ns"] for pair in all_pairs if pair["signed_receive_wait_ns"] > 0]
    outliers = [pair for pair in all_pairs if pair["absolute_stamp_skew_ns"] > 0]
    sixty_ms = [pair for pair in outliers if pair["absolute_stamp_skew_ns"] == 60_000_000]
    runs_with_sixty_ms = len({pair["run"] for pair in sixty_ms})
    total_pair_count = len(all_pairs)
    sixty_ms_rate = 0.0 if total_pair_count == 0 else 100.0 * len(sixty_ms) / total_pair_count
    nonzero_rate = 0.0 if total_pair_count == 0 else 100.0 * len(outliers) / total_pair_count
    occurrence = "not observed" if not sixty_ms else f"{len(sixty_ms)} pair(s) across {runs_with_sixty_ms} of {len(run_rows)} runs"
    conclusion = (
        "No 60 ms outlier was observed in the five-run set; the earlier single-run event remains unconfirmed."
        if not sixty_ms
        else ("The 60 ms outlier recurs across multiple runs." if runs_with_sixty_ms > 1 else "The 60 ms outlier occurred in one run only and is rare in this set.")
    )
    lines = [
        "# Timing Evidence Report — Multi-Run",
        "",
        f"Execution timestamp UTC: {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Scope",
        "",
        f"- {len(run_rows)} independent idle-Gazebo captures. Collector subscribed only to `/scan` and `/odom`.",
        "- No `/cmd_vel`, reset, teleop, entity/service control, UART, or hardware operation was issued.",
        "- All numeric options below are `PROPOSED_FROM_MEASUREMENT_PENDING_USER_APPROVAL`.",
        "",
        "## Per-run summary",
        "",
        "| Run | Duration ns | Scan | Odom | Odom/scan rate | Exact pairs | Nonzero skew | Skew p95 ns | Skew p99 ns | Skew max ns | Positive wait p99 ns |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    lines.extend(
        "| {run} | {duration_ns} | {scan_count} | {odom_count} | {rate_ratio} | {exact} | {nonzero} | {skew_p95} | {skew_p99} | {skew_max} | {wait_p99} |".format(**row)
        for row in run_rows
    )
    lines.extend([
        "",
        "## Aggregate pairing evidence",
        "",
        f"- Aggregate nearest-by-stamp skew: `{json.dumps(integer_stats(skews), sort_keys=True)}`.",
        f"- Aggregate positive receive wait: `{json.dumps(integer_stats(positive_waits), sort_keys=True)}`.",
        f"- Nonzero-skew occurrence: {len(outliers)}/{total_pair_count} ({nonzero_rate:.4f}%).",
        f"- 60 ms skew occurrence: {occurrence} ({sixty_ms_rate:.4f}% of nearest-by-stamp pairs).",
        f"- Interpretation: {conclusion}",
        "- Exact-only pairing accepts only exact stamp pairs; any nonzero skew is dropped, so exact-only is not robust whenever nonzero skew occurs.",
        "",
        "## Aggregate tolerance options — not approved",
        "",
        "| Status | Option | Tolerance ns | Accepted pairs | Dropped pairs | Temporal-mismatch risk |",
        "| --- | --- | --- | --- | --- |",
    ])
    lines.extend(
        "| {status} | {option} | {tolerance_ns} | {accepted_pair_count} | {dropped_pair_count} | {risk} |".format(**option)
        for option in tolerance_options(skews)
    )
    lines.extend([
        "",
        "## Aggregate nonzero-skew outliers",
        "",
        "| Run | Scan stamp ns | Odom stamp ns | Absolute skew ns | Signed receive wait ns |",
        "| --- | --- | --- | --- | --- |",
    ])
    if outliers:
        lines.extend(
            "| {run} | {scan_stamp_ns} | {odom_stamp_ns} | {absolute_stamp_skew_ns} | {signed_receive_wait_ns} |".format(**pair)
            for pair in outliers
        )
    else:
        lines.append("| — | — | — | 0 | — |")
    lines.extend([
        "",
        "## Evidence still required before approval",
        "",
        "- Repeat under reset, simulator delay/dropout, CPU contention, and command-motion scenarios.",
        "- Decide receive-age budgets and buffer capacities separately; this report does not approve them.",
        "- Gazebo timing is not deploy-real or hardware evidence.",
    ])
    return "\n".join(lines) + "\n"


def analyze_multi_run(parent: Path) -> None:
    """Summarize run_* captures without overwriting any historical capture."""

    run_dirs = sorted(
        path
        for path in parent.glob("run_*")
        if path.is_dir() and (path / "trace.jsonl").is_file() and (path / "capture_metadata.json").is_file()
    )
    if len(run_dirs) < 5:
        raise ValueError(f"need at least five run_* captures, found {len(run_dirs)}")
    run_rows: list[dict[str, Any]] = []
    all_pairs: list[dict[str, int]] = []
    for run_dir in run_dirs:
        metadata, summary, pairs = analyze_capture(run_dir)
        for pair in pairs:
            pair["run"] = run_dir.name
        skew = summary["scan_to_nearest_odom_skew_ns"]
        positive_wait = summary["positive_receive_wait_ns"]
        run_rows.append({
            "run": run_dir.name,
            "duration_ns": metadata["duration_steady_ns"],
            "scan_count": metadata["counts"]["scan"],
            "odom_count": metadata["counts"]["odom"],
            "rate_ratio": summary["rate_ratio_odom_to_scan"],
            "exact": summary["exact_stamp_match_count"],
            "nonzero": summary["nonzero_stamp_skew_count"],
            "skew_p95": skew["p95"], "skew_p99": skew["p99"], "skew_max": skew["max"], "wait_p99": positive_wait["p99"],
        })
        all_pairs.extend(pairs)
    (parent / "Timing_Evidence_Report_MultiRun.md").write_text(
        render_multi_run_report(parent, run_rows, all_pairs), encoding="utf-8"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    selector = parser.add_mutually_exclusive_group(required=True)
    selector.add_argument("--input-dir", type=Path)
    selector.add_argument("--multi-run-parent", type=Path)
    arguments = parser.parse_args()
    if arguments.input_dir:
        _, summary, _ = analyze_capture(arguments.input_dir)
        print(json.dumps(summary, indent=2))
    else:
        analyze_multi_run(arguments.multi_run_parent)
        print(arguments.multi_run_parent / "Timing_Evidence_Report_MultiRun.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
