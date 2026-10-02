#!/usr/bin/env python3
"""Offline-only post-response provenance analysis for one approved replacement run."""

import argparse
import json
import math
from pathlib import Path


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def yaw_from_quaternion(z, w):
    return math.atan2(2.0 * w * z, 1.0 - 2.0 * z * z)


def pose_tuple(record):
    pose = record["payload"]["pose"]["pose"]
    position = pose["position"]
    orientation = pose["orientation"]
    return (position["x"], position["y"], position["z"], yaw_from_quaternion(orientation["z"], orientation["w"]))


def candidate_records(trace, item):
    end = item["post_probe_barrier"]["captured_steady_ns"]
    dispatch = item["ros_request_dispatched_steady_ns"]
    return [
        record for record in trace
        if record.get("stream") == "/ground_truth/odom"
        and dispatch < record["received_steady_ns"] <= end
    ]


def candidate_summary(records, post_response_barrier_steady_ns):
    classified = []
    previous_pose = None
    for record in records:
        labels = []
        if record["received_steady_ns"] > post_response_barrier_steady_ns:
            labels.append("POST_RESPONSE_CANDIDATE")
        else:
            labels.append("PRE_RESPONSE_CANDIDATE")
        current_pose = pose_tuple(record)
        if previous_pose is not None and current_pose != previous_pose:
            labels.append("OBSERVED_POSE_CHANGE")
        previous_pose = current_pose
        classified.append({
            "ros_stamp_ns": record.get("ros_stamp_ns"),
            "received_steady_ns": record["received_steady_ns"],
            "labels": labels,
            "pose": {"x": current_pose[0], "y": current_pose[1], "z": current_pose[2], "yaw_rad": current_pose[3]},
            "twist": record["payload"]["twist"]["twist"],
        })
    if not any("POST_RESPONSE_CANDIDATE" in item["labels"] for item in classified):
        classified.append({"labels": ["NO_POST_RESPONSE_GT"]})
    return classified


def first_with_label(classified, label):
    return next((item for item in classified if label in item["labels"]), None)


def display_candidate(item):
    if item is None or "pose" not in item:
        return "NONE"
    pose = item["pose"]
    return "stamp={} steady={} pose={:.9f}/{:.9f}/{:.9f}/{:.11f}".format(
        item["ros_stamp_ns"], item["received_steady_ns"], pose["x"], pose["y"], pose["z"], pose["yaw_rad"]
    )


def main():
    parser = argparse.ArgumentParser(description="Offline replacement-run provenance analyzer")
    parser.add_argument("--run-dir", required=True)
    args = parser.parse_args()
    run_dir = Path(args.run_dir)
    metadata = load_json(run_dir / "capture_metadata.json")
    requests = load_json(run_dir / "request_response_records.json")
    trace = load_jsonl(run_dir / "stream_trace.jsonl")
    rows = []
    missing_timestamp_provenance = []
    for item in requests:
        required = (
            "pre_call_steady_ns",
            "ros_request_dispatched_steady_ns",
            "ros_response_received_steady_ns",
            "post_response_barrier_steady_ns",
        )
        if any(item.get(field) is None for field in required):
            missing_timestamp_provenance.append(item["probe_id"])
            classifications = [{"labels": ["NO_POST_RESPONSE_GT"]}]
        else:
            classifications = candidate_summary(candidate_records(trace, item), item["post_response_barrier_steady_ns"])
        pre_count = sum("PRE_RESPONSE_CANDIDATE" in entry["labels"] for entry in classifications)
        post_count = sum("POST_RESPONSE_CANDIDATE" in entry["labels"] for entry in classifications)
        pose_change_count = sum("OBSERVED_POSE_CHANGE" in entry["labels"] for entry in classifications)
        row = {
            "probe_id": item["probe_id"],
            "service_success": None if item.get("response") is None else bool(item["response"].get("success")),
            "timestamps": {field: item.get(field) for field in required},
            "pre_response_candidate_count": pre_count,
            "post_response_candidate_count": post_count,
            "observed_pose_change_count": pose_change_count,
            "no_post_response_gt": post_count == 0,
            "first_post_response_candidate": first_with_label(classifications, "POST_RESPONSE_CANDIDATE"),
            "first_observed_pose_change": first_with_label(classifications, "OBSERVED_POSE_CHANGE"),
            "candidate_classifications": classifications,
        }
        rows.append(row)
        summary_path = run_dir / (item["probe_id"] + "_summary.json")
        summary_path.write_text(json.dumps({"request_record": item, "post_response_provenance": row}, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    overall = {
        "run_id": metadata["run_id"],
        "run_status": metadata["run_status"],
        "timestamp_provenance_complete": not missing_timestamp_provenance,
        "missing_timestamp_provenance_probes": missing_timestamp_provenance,
        "rows": rows,
        "non_claim": "POST_RESPONSE_CANDIDATE is a local receive-order classification, not a Gazebo application receipt, reset receipt, settle threshold, or coordinate-mapping proof.",
    }
    (run_dir / "analysis_summary.json").write_text(json.dumps(overall, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")

    lines = [
        "# Controlled Coordinate Reset Measurement Evidence Report",
        "",
        "## Run status",
        "",
        "- Run: `" + metadata["run_id"] + "`",
        "- Status: `" + metadata["run_status"] + "`",
        "- Sent probes: `" + " → ".join(metadata["sent_probe_order"]) + "`",
        "- Entity: `ROBOT_URDF_final`",
        "- Pose service: `" + metadata["pose_service"] + "` (`" + metadata["pose_service_type"] + "`)",
        "- Timestamp provenance complete: `" + str(not missing_timestamp_provenance) + "`",
        "",
        "## Post-response provenance classification",
        "",
        "| Probe | Response success | PRE_RESPONSE_CANDIDATE | POST_RESPONSE_CANDIDATE | OBSERVED_POSE_CHANGE | NO_POST_RESPONSE_GT | First post-response candidate |",
        "| --- | --- | ---: | ---: | ---: | --- | --- |",
    ]
    for row in rows:
        lines.append("| {} | {} | {} | {} | {} | {} | {} |".format(
            row["probe_id"], row["service_success"], row["pre_response_candidate_count"],
            row["post_response_candidate_count"], row["observed_pose_change_count"],
            row["no_post_response_gt"], display_candidate(row["first_post_response_candidate"])))
    lines.extend([
        "",
        "## Provenance meaning and limitations",
        "",
        "- `PRE_RESPONSE_CANDIDATE` is received after local dispatch but not strictly after the post-response barrier.",
        "- `POST_RESPONSE_CANDIDATE` is received strictly after the local post-response barrier; it is the only candidate class used in this report's request–GT relation.",
        "- `OBSERVED_POSE_CHANGE` is a descriptive trace change, not a settle threshold or receipt.",
        "- `NO_POST_RESPONSE_GT` means no retained GT row passed the local post-response test; it must not be replaced with an older or pre-response sample.",
        "- The request z remains `0.1` and observed GT z may remain `0.0`. This is reported only as an observation, not a mapping adjustment.",
        "- No conclusion is made about Gazebo pose application receipt, atomic reset, scenario frame, TF authority, collision, task oracle, Gym, reward, termination, runtime deployment, firmware, or hardware.",
    ])
    (run_dir.parent / "Controlled_Coordinate_Reset_Measurement_Evidence_Report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"run_id": metadata["run_id"], "status": metadata["run_status"], "timestamp_provenance_complete": not missing_timestamp_provenance}))


if __name__ == "__main__":
    main()
