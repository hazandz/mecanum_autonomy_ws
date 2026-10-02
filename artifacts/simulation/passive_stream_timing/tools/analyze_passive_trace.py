#!/usr/bin/env python3
"""Offline-only analyzer for S3 passive JSON and JSONL evidence."""

import argparse
import bisect
import json
import math
from pathlib import Path

STREAMS = ["/clock", "/ground_truth/odom", "/odom", "/scan", "/tf"]


def percentile(values, fraction):
    if not values:
        return None
    values = sorted(values)
    index = (len(values) - 1) * fraction
    lower = math.floor(index)
    upper = math.ceil(index)
    if lower == upper:
        return values[lower]
    return values[lower] + (values[upper] - values[lower]) * (index - lower)


def summary(values):
    if not values:
        return {"count": 0, "min": None, "p50": None, "p95": None, "p99": None, "max": None}
    return {
        "count": len(values), "min": min(values), "p50": percentile(values, 0.5),
        "p95": percentile(values, 0.95), "p99": percentile(values, 0.99), "max": max(values),
    }


def load_json(path):
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def load_jsonl(path):
    records = []
    with path.open(encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            if line.strip():
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise ValueError(str(path) + ":" + str(number) + " is not an object")
                records.append(value)
    return records


def tf_messages(records):
    first = {}
    for record in records:
        first.setdefault(record.get("message_index"), record)
    return [first[key] for key in sorted(first)]


def by_stream_statistics(records):
    grouped = {stream: [] for stream in STREAMS}
    for record in records:
        if record.get("stream") in grouped:
            grouped[record["stream"]].append(record)
    output = {}
    for stream, values in grouped.items():
        messages = tf_messages(values) if stream == "/tf" else values
        stamps = [int(value["ros_stamp_ns"]) for value in messages if "ros_stamp_ns" in value]
        receives = [int(value["received_steady_ns"]) for value in messages]
        stamp_deltas = [right - left for left, right in zip(stamps, stamps[1:])]
        receive_deltas = [right - left for left, right in zip(receives, receives[1:])]
        span = receives[-1] - receives[0] if len(receives) > 1 else 0
        output[stream] = {
            "record_count": len(values),
            "message_count": len(messages),
            "stamp_duplicate_count": sum(delta == 0 for delta in stamp_deltas),
            "stamp_regression_count": sum(delta < 0 for delta in stamp_deltas),
            "ros_stamp_interval_ns": summary(stamp_deltas),
            "steady_interarrival_ns": summary(receive_deltas),
            "observed_rate_hz": ((len(receives) - 1) * 1_000_000_000 / span) if span > 0 else None,
            "frame_ids": sorted({str(value.get("frame_id")) for value in values if value.get("frame_id")}),
            "child_frame_ids": sorted({str(value.get("child_frame_id")) for value in values if value.get("child_frame_id")}),
        }
    return output, grouped


def nearest_pairs(left, right, name):
    right_values = sorted([(int(value["ros_stamp_ns"]), value) for value in right if "ros_stamp_ns" in value])
    right_stamps = [value[0] for value in right_values]
    pairs = []
    for item in left:
        if "ros_stamp_ns" not in item or not right_stamps:
            continue
        left_stamp = int(item["ros_stamp_ns"])
        position = bisect.bisect_left(right_stamps, left_stamp)
        choices = [index for index in (position - 1, position) if 0 <= index < len(right_stamps)]
        selected = min(choices, key=lambda index: abs(right_stamps[index] - left_stamp))
        right_stamp, right_item = right_values[selected]
        pairs.append({
            "pair": name,
            "left_stamp_ns": left_stamp,
            "right_stamp_ns": right_stamp,
            "absolute_skew_ns": abs(right_stamp - left_stamp),
            "left_index": item.get("index"),
            "right_index": right_item.get("index"),
        })
    return pairs


def pair_result(pairs):
    values = [item["absolute_skew_ns"] for item in pairs]
    return {
        "pair_count": len(pairs),
        "exact_match_count": sum(value == 0 for value in values),
        "nonzero_skew_count": sum(value != 0 for value in values),
        "absolute_skew_ns": summary(values),
        "nonzero_outliers": [item for item in pairs if item["absolute_skew_ns"] != 0],
    }


def analyze_run(run_dir):
    metadata = load_json(run_dir / "capture_metadata.json")
    records = load_jsonl(run_dir / "stream_trace.jsonl")
    streams, grouped = by_stream_statistics(records)
    pairs = {
        "ground_truth_odom_to_odom": nearest_pairs(grouped["/ground_truth/odom"], grouped["/odom"], "ground_truth_odom_to_odom"),
        "scan_to_odom": nearest_pairs(grouped["/scan"], grouped["/odom"], "scan_to_odom"),
        "scan_to_ground_truth_odom": nearest_pairs(grouped["/scan"], grouped["/ground_truth/odom"], "scan_to_ground_truth_odom"),
    }
    output = {
        "run_id": metadata["run_id"],
        "run_status": metadata["run_status"],
        "invalid_reasons": metadata["invalid_reasons"],
        "capture_record_counts": metadata["capture_record_counts"],
        "cmd_vel_allowlist_changed": metadata["cmd_vel_allowlist_changed"],
        "pre_capture_cmd_vel_publishers": metadata["frozen_cmd_vel_allowlist"],
        "post_run_cmd_vel_publishers": metadata["post_run_graph_snapshot"]["/cmd_vel"]["publishers"],
        "pre_capture_graph_snapshot": metadata["pre_capture_graph_snapshot"],
        "streams": streams,
        "pairs": {name: pair_result(value) for name, value in pairs.items()},
        "tf_relations": sorted({(value.get("frame_id", ""), value.get("child_frame_id", "")) for value in grouped["/tf"]}),
    }
    (run_dir / "summary.json").write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output


def table(rows):
    if not rows:
        return "_None_"
    fields = list(rows[0])
    lines = ["| " + " | ".join(fields) + " |", "| " + " | ".join("---" for _ in fields) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(str(row[field]).replace("|", "\\|") for field in fields) + " |")
    return "\n".join(lines)


def report(root, runs):
    valid = [run for run in runs if run["run_status"] == "VALID"]
    outliers = []
    for run in valid:
        for pair in run["pairs"].values():
            outliers.extend([{"run_id": run["run_id"], **value} for value in pair["nonzero_outliers"]])
    candidate = bool(valid) and all(
        "world" in run["streams"]["/ground_truth/odom"]["frame_ids"]
        and "base_link" in run["streams"]["/ground_truth/odom"]["child_frame_ids"]
        for run in valid
    )
    lines = ["# Passive Stream Timing Evidence Report", "", "Status labels: OBSERVED, CANDIDATE_FOR_FUTURE_DECISION, PROPOSED_FROM_MEASUREMENT, NOT_ESTABLISHED.", "", "## Run validity — OBSERVED", ""]
    lines.extend([table([{
        "run_id": run["run_id"], "status": run["run_status"],
        "invalid_reasons": "; ".join(run["invalid_reasons"]) or "-",
        "cmd_vel_change": run["cmd_vel_allowlist_changed"],
    } for run in runs]), "", "Only VALID runs below contribute to aggregate timing evidence.", ""])
    graph_rows = []
    for run in valid:
        for topic in STREAMS:
            entry = run["pre_capture_graph_snapshot"][topic]
            graph_rows.append({
                "run_id": run["run_id"],
                "topic": topic,
                "observed_types": ",".join(entry["observed_types"]) or "-",
                "publisher_count": entry["publisher_count"],
                "publishers": ",".join(item["publisher_name"] for item in entry["publishers"]) or "-",
            })
    lines.extend(["## Graph metadata — OBSERVED", "", table(graph_rows), "", "## Stream statistics — OBSERVED", ""])
    for stream in STREAMS:
        rows = []
        for run in valid:
            data = run["streams"][stream]
            rows.append({
                "run_id": run["run_id"], "records": data["record_count"], "messages": data["message_count"],
                "rate_hz": data["observed_rate_hz"], "duplicates": data["stamp_duplicate_count"],
                "regressions": data["stamp_regression_count"], "steady_p99_ns": data["steady_interarrival_ns"]["p99"],
                "steady_max_ns": data["steady_interarrival_ns"]["max"], "frames": ",".join(data["frame_ids"]) or "-",
                "children": ",".join(data["child_frame_ids"]) or "-",
            })
        lines.extend(["### " + stream, "", table(rows), ""])
    lines.extend(["## Timestamp pairing — OBSERVED", ""])
    for name in ("ground_truth_odom_to_odom", "scan_to_odom", "scan_to_ground_truth_odom"):
        rows = []
        for run in valid:
            data = run["pairs"][name]
            rows.append({
                "run_id": run["run_id"], "pairs": data["pair_count"], "exact": data["exact_match_count"],
                "nonzero": data["nonzero_skew_count"], "p99_skew_ns": data["absolute_skew_ns"]["p99"],
                "max_skew_ns": data["absolute_skew_ns"]["max"],
            })
        lines.extend(["### " + name, "", table(rows), ""])
    lines.extend(["## Nonzero timestamp-skew outliers — OBSERVED", "", table(outliers), "", "## TF relations — OBSERVED", ""])
    relations = sorted({relation for run in valid for relation in run["tf_relations"]})
    lines.append(table([{"parent_frame": item[0] or "-", "child_frame": item[1] or "-"} for item in relations]))
    lines.extend(["", "## Ground-truth stream assessment", ""])
    if candidate:
        lines.append("CANDIDATE_FOR_FUTURE_DECISION: valid runs observed /ground_truth/odom with world to base_link frame metadata. This is not a TrainingTaskOracle and does not authorize GT for policy observation.")
    else:
        lines.append("NOT_ESTABLISHED: no sufficient valid-run world to base_link ground-truth stream evidence.")
    lines.extend(["", "## Limitations — NOT_ESTABLISHED", "", "This idle passive evidence does not establish ContactLatch/collision, task goal or bounds, STUCK policy, D6 limit, reward, termination, Gym behavior, actuator behavior, or hardware behavior.", "A permitted pre-existing ros_gz_bridge publisher does not prove no external command was sent. The evidence only records graph changes and that the collector declares no command publish or control-service operation."])
    (root / "Passive_Stream_Timing_Evidence_Report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Offline S3 passive artifact analyzer")
    parser.add_argument("--root", required=True)
    args = parser.parse_args()
    root = Path(args.root)
    run_dirs = sorted(path for path in root.glob("run-*") if path.is_dir())
    if len(run_dirs) != 6:
        raise ValueError("expected exactly six run directories, found " + str(len(run_dirs)))
    runs = [analyze_run(path) for path in run_dirs]
    report(root, runs)
    print(json.dumps({"runs": len(runs), "valid": sum(run["run_status"] == "VALID" for run in runs)}))


if __name__ == "__main__":
    main()
