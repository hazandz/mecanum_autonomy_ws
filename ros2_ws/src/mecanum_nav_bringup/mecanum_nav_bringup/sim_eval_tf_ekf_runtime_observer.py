"""Multi-sample ROS clock, odometry, and edge-specific TF evidence collector."""

from __future__ import annotations

import json
import math
from pathlib import Path
import time
from datetime import datetime, timezone


OBSERVER_SCHEMA = "wp06_6f_runtime_observer/v1"
STATIC_QOS_CONTRACT = {
    "history": "KEEP_LAST",
    "depth": 1,
    "reliability": "RELIABLE",
    "durability": "TRANSIENT_LOCAL",
}
EXPECTED_STATIC_TRANSLATION = [-0.031765, 0.0, 0.140]
EXPECTED_STATIC_ROTATION_XYZW = [0.0, 0.0, 0.0, 1.0]
RUNTIME_ACCEPTANCE_MATRIX = [
    {"acceptance_id": "bootstrap_readiness", "record_key": "bootstrap_readiness", "collector": "session_runner", "raw_artifact_path": "logs/bootstrap.log", "parser_or_validator": "literal-byte readiness matcher", "pass_condition": "contains exact Entity creation successful. line before 90s timeout", "failure_reason_literal": "BOOTSTRAP_READINESS_FAILED", "offline_test_name": "test_bootstrap_readiness_and_stability_fail_closed"},
    {"acceptance_id": "bootstrap_stability_20_seconds", "record_key": "bootstrap_stability_20_seconds", "collector": "session_runner", "raw_artifact_path": "run_record.json:acceptance.bootstrap_stability_20_seconds", "parser_or_validator": "monotonic clock + Popen.poll", "pass_condition": "bootstrap remains alive for 20 seconds after readiness", "failure_reason_literal": "BOOTSTRAP_DIED_DURING_STABILIZATION", "offline_test_name": "test_bootstrap_readiness_and_stability_fail_closed"},
    {"acceptance_id": "composite_liveness", "record_key": "composite_live_through_evidence", "collector": "session_runner", "raw_artifact_path": "run_record.json:acceptance.composite_live_through_evidence", "parser_or_validator": "Popen.poll at observation boundaries", "pass_condition": "composite remains alive through observer and transcript collection", "failure_reason_literal": "COMPOSITE_EXITED_DURING_EVIDENCE", "offline_test_name": "test_composite_liveness_and_teardown_acceptance_fail_closed"},
    {"acceptance_id": "clock_five_monotonic_samples", "record_key": "clock_minimum_five_nonzero_strictly_increasing", "collector": "rclpy runtime observer subscription /clock", "raw_artifact_path": "transcripts/runtime_observer.json#/topics/~1clock/samples", "parser_or_validator": "evaluate_observations", "pass_condition": "at least 5 nonzero clock samples with strictly increasing unique (sec,nanosec)", "failure_reason_literal": "CLOCK_TIMEOUT_MINIMUM_FIVE_SAMPLES", "offline_test_name": "test_clock_requires_five_nonzero_strict_timestamps"},
    {"acceptance_id": "wheel_input", "record_key": "wheel_sample_contract", "collector": "session runner ROS topic info and one sample", "raw_artifact_path": "transcripts/wheel_info.*.bin;transcripts/wheel_echo.*.bin", "parser_or_validator": "_verify_topic_info + safe_load_all input validator", "pass_condition": "nav_msgs/msg/Odometry, one data publisher, odom->base_link and finite twist", "failure_reason_literal": "WHEEL_INPUT_TYPE_PUBLISHER_OR_SAMPLE_CONTRACT_FAILED", "offline_test_name": "test_wheel_and_imu_input_acceptance_is_fail_closed"},
    {"acceptance_id": "imu_input", "record_key": "imu_sample_contract", "collector": "session runner ROS topic info and one sample", "raw_artifact_path": "transcripts/imu_info.*.bin;transcripts/imu_echo.*.bin", "parser_or_validator": "_verify_topic_info + safe_load_all input validator", "pass_condition": "sensor_msgs/msg/Imu, one data publisher, base_link, finite payload and normalized quaternion", "failure_reason_literal": "IMU_INPUT_TYPE_PUBLISHER_OR_SAMPLE_CONTRACT_FAILED", "offline_test_name": "test_wheel_and_imu_input_acceptance_is_fail_closed"},
    {"acceptance_id": "ingress_use_sim_time", "record_key": "ingress_use_sim_time_true", "collector": "session runner ros2 param get transcript", "raw_artifact_path": "transcripts/ingress_use_sim_time.stdout.bin", "parser_or_validator": "exact true suffix validator", "pass_condition": "effective ingress use_sim_time is true", "failure_reason_literal": "INGRESS_USE_SIM_TIME_FALSE_OR_UNAVAILABLE", "offline_test_name": "test_runtime_acceptance_matrix_covers_all_required_criteria"},
    {"acceptance_id": "filtered_odometry_five_monotonic_samples", "record_key": "filtered_odometry_minimum_five_contract_and_monotonicity", "collector": "rclpy runtime observer subscription /odometry/filtered", "raw_artifact_path": "transcripts/runtime_observer.json#/topics/~1odometry~1filtered/samples", "parser_or_validator": "evaluate_observations", "pass_condition": "one typed data publisher plus at least 5 valid odom->base_link payloads with monotonic timestamps and finite pose/twist/36-value covariance", "failure_reason_literal": "FILTERED_ODOMETRY_TIMEOUT_MINIMUM_FIVE_SAMPLES", "offline_test_name": "test_filtered_odometry_requires_five_valid_monotonic_samples"},
    {"acceptance_id": "ekf_use_sim_time", "record_key": "ekf_use_sim_time_true", "collector": "session runner ros2 param get transcript", "raw_artifact_path": "transcripts/ekf_use_sim_time.stdout.bin", "parser_or_validator": "exact true suffix validator", "pass_condition": "effective EKF use_sim_time is true", "failure_reason_literal": "EKF_USE_SIM_TIME_FALSE_OR_UNAVAILABLE", "offline_test_name": "test_runtime_acceptance_matrix_covers_all_required_criteria"},
    {"acceptance_id": "ekf_topology", "record_key": "ekf_inputs_and_outputs_bounded", "collector": "session runner ros2 node info transcript", "raw_artifact_path": "transcripts/ekf_node_info.stdout.bin", "parser_or_validator": "node section topic parser", "pass_condition": "only wheel, IMU, clock subscriptions and filtered odometry plus /tf publications", "failure_reason_literal": "EKF_NODE_TOPOLOGY_OUT_OF_CONTRACT", "offline_test_name": "test_node_info_topic_parser_is_edge_and_section_specific"},
    {"acceptance_id": "dynamic_tf_edge_gid", "record_key": "dynamic_odom_to_base_link_minimum_five_strictly_increasing_single_gid", "collector": "rclpy MessageInfo observer /tf", "raw_artifact_path": "transcripts/runtime_observer.json#/topics/~1tf/transforms", "parser_or_validator": "evaluate_observations", "pass_condition": "at least 5 strictly increasing odom->base_link transforms from exactly one publisher GID", "failure_reason_literal": "TF_DYNAMIC_EDGE_TIMEOUT_MINIMUM_FIVE_EDGES", "offline_test_name": "test_dynamic_tf_requires_five_samples_and_one_gid"},
    {"acceptance_id": "static_tf_edge_qos", "record_key": "static_base_link_to_lidar_frame_qos_and_transform_exact", "collector": "rclpy transient-local MessageInfo observer /tf_static", "raw_artifact_path": "transcripts/runtime_observer.json#/topics/~1tf_static", "parser_or_validator": "evaluate_observations + STATIC_QOS_CONTRACT", "pass_condition": "one unique base_link->lidar_frame transform with specified Xacro transform and KEEP_LAST(1)/RELIABLE/TRANSIENT_LOCAL QoS", "failure_reason_literal": "TF_STATIC_EDGE_MISSING_OR_TRANSFORM_MISMATCH", "offline_test_name": "test_static_tf_requires_transient_local_qos_and_exact_transform"},
    {"acceptance_id": "map_to_odom_absent", "record_key": "map_to_odom_absent_during_observation_window", "collector": "rclpy observers /tf and /tf_static for full window", "raw_artifact_path": "transcripts/runtime_observer.json#/acceptance/map_to_odom_absent_during_observation_window", "parser_or_validator": "evaluate_observations", "pass_condition": "no map->odom edge throughout completed observation window", "failure_reason_literal": "MAP_TO_ODOM_EDGE_OBSERVED", "offline_test_name": "test_map_to_odom_and_observation_timeouts_fail_closed"},
    {"acceptance_id": "observer_errors_absent", "record_key": "observer_errors_absent", "collector": "rclpy observer callbacks and executor", "raw_artifact_path": "transcripts/runtime_observer.json#/observer_errors", "parser_or_validator": "evaluate_observations", "pass_condition": "all required subscriptions, message-info GIDs, serialization and executor callbacks completed without errors", "failure_reason_literal": "RUNTIME_OBSERVER_CALLBACK_OR_API_ERROR", "offline_test_name": "test_observer_errors_fail_closed"},
    {"acceptance_id": "forbidden_bridge_and_process_boundary", "record_key": "forbidden_topics_and_processes_absent", "collector": "session runner node-info transcripts and composite process-group snapshot", "raw_artifact_path": "transcripts/*node_info*;run_record.json:process_group_commands", "parser_or_validator": "node section topic parser + command marker matcher", "pass_condition": "no forbidden bridge/topic route or Nav2/AMCL/SLAM/Map Server/command publisher process in candidate process group", "failure_reason_literal": "FORBIDDEN_BRIDGE_TOPIC_OR_PROCESS_OBSERVED", "offline_test_name": "test_forbidden_runtime_boundary_is_fail_closed"},
    {"acceptance_id": "process_group_teardown", "record_key": "teardown_process_groups_clean", "collector": "session runner process-group reaper", "raw_artifact_path": "run_record.json:teardown", "parser_or_validator": "final /proc live/zombie snapshots", "pass_condition": "composite group stopped before bootstrap group, no live or zombie members", "failure_reason_literal": "PROCESS_GROUP_TEARDOWN_FAILED", "offline_test_name": "test_composite_liveness_and_teardown_acceptance_fail_closed"},
]


def _now():
    return datetime.now(timezone.utc).isoformat()


def _json_value(value):
    """Serialize ROS messages without emitting non-standard JSON NaN tokens."""
    if isinstance(value, float):
        if math.isfinite(value):
            return value
        if math.isnan(value):
            return "NaN"
        return "Infinity" if value > 0 else "-Infinity"
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    fields = getattr(value, "get_fields_and_field_types", None)
    if callable(fields):
        return {name: _json_value(getattr(value, name)) for name in fields()}
    return str(value)


def _stamp_ns(stamp):
    return int(stamp.sec) * 1_000_000_000 + int(stamp.nanosec)


def _strictly_increasing(values):
    return bool(values) and all(left < right for left, right in zip(values, values[1:]))


def _finite(value):
    if isinstance(value, bool) or value is None:
        return False
    if isinstance(value, (int, float)):
        return math.isfinite(float(value))
    if isinstance(value, list):
        return all(_finite(item) for item in value)
    if isinstance(value, dict):
        return bool(value) and all(_finite(item) for item in value.values())
    return False


def _valid_nonzero_stamp(stamp):
    return type(stamp.get("sec")) is int and type(stamp.get("nanosec")) is int and (
        stamp["sec"] > 0 or stamp["nanosec"] > 0
    ) and stamp["sec"] >= 0 and 0 <= stamp["nanosec"] < 1_000_000_000


def evaluate_observations(observations, qos=STATIC_QOS_CONTRACT, observer_errors=()):
    """Pure offline validator for the observer's canonical structured payload."""
    clock = observations.get("/clock", {})
    clock_samples = clock.get("samples", [])
    clock_times = [sample.get("stamp_ns", 0) for sample in clock_samples]
    clock_pass = (
        len(clock_samples) >= 5
        and all(_valid_nonzero_stamp(sample.get("stamp", {})) for sample in clock_samples)
        and len(set(clock_times)) == len(clock_times)
        and _strictly_increasing(clock_times)
    )

    filtered = observations.get("/odometry/filtered", {})
    filtered_samples = filtered.get("samples", [])
    filtered_times = [sample.get("stamp_ns", 0) for sample in filtered_samples]
    filtered_pass = len(filtered_samples) >= 5 and _strictly_increasing(filtered_times)
    filtered_reasons = []
    if len(filtered_samples) < 5:
        filtered_reasons.append("FILTERED_ODOMETRY_TIMEOUT_MIN_SAMPLES")
    for sample in filtered_samples:
        msg = sample.get("message", {})
        if msg.get("header", {}).get("frame_id") != "odom" or msg.get("child_frame_id") != "base_link":
            filtered_pass = False
            filtered_reasons.append("FILTERED_ODOMETRY_FRAME_MISMATCH")
            break
        stamp = msg.get("header", {}).get("stamp", {})
        if not _valid_nonzero_stamp(stamp):
            filtered_pass = False
            filtered_reasons.append("FILTERED_ODOMETRY_INVALID_STAMP")
            break
        pose = msg.get("pose", {})
        twist = msg.get("twist", {})
        if not _finite(pose) or not _finite(twist):
            filtered_pass = False
            filtered_reasons.append("FILTERED_ODOMETRY_NONFINITE_POSE_OR_TWIST")
            break
        if len(pose.get("covariance", [])) != 36 or len(twist.get("covariance", [])) != 36 or not _finite(pose.get("covariance", [])) or not _finite(twist.get("covariance", [])):
            filtered_pass = False
            filtered_reasons.append("FILTERED_ODOMETRY_INVALID_COVARIANCE")
            break
    if len(filtered_times) >= 2 and not _strictly_increasing(filtered_times):
        filtered_pass = False
        filtered_reasons.append("FILTERED_ODOMETRY_TIMESTAMP_NOT_STRICTLY_INCREASING")

    tf_obs = observations.get("/tf", {})
    dynamic = [row for row in tf_obs.get("transforms", []) if row.get("parent") == "odom" and row.get("child") == "base_link"]
    dynamic_times = [row.get("stamp_ns", 0) for row in dynamic]
    dynamic_gids = {row.get("publisher_gid") for row in dynamic}
    dynamic_pass = (
        len(dynamic) >= 5
        and all(type(stamp) is int and stamp > 0 for stamp in dynamic_times)
        and _strictly_increasing(dynamic_times)
        and len(dynamic_gids) == 1
        and None not in dynamic_gids
        and all(_finite(row.get("translation")) and _finite(row.get("rotation_xyzw")) for row in dynamic)
    )

    static_obs = observations.get("/tf_static", {})
    static = [row for row in static_obs.get("transforms", []) if row.get("parent") == "base_link" and row.get("child") == "lidar_frame"]
    signatures = {
        (row.get("publisher_gid"), tuple(row.get("translation", [])), tuple(row.get("rotation_xyzw", [])))
        for row in static
    }
    static_qos_pass = qos == STATIC_QOS_CONTRACT
    static_pass = len(signatures) == 1 and bool(static) and static_qos_pass
    if static_pass:
        row = static[0]
        static_pass = (
            len(row.get("translation", [])) == 3
            and len(row.get("rotation_xyzw", [])) == 4
            and all(abs(a - b) <= 1e-9 for a, b in zip(row["translation"], EXPECTED_STATIC_TRANSLATION))
            and all(abs(a - b) <= 1e-9 for a, b in zip(row["rotation_xyzw"], EXPECTED_STATIC_ROTATION_XYZW))
            and _finite(row.get("translation"))
            and _finite(row.get("rotation_xyzw"))
        )

    map_to_odom = [row for section in (tf_obs, static_obs) for row in section.get("transforms", []) if row.get("parent") == "map" and row.get("child") == "odom"]
    result = {
        "clock_minimum_five_nonzero_strictly_increasing": clock_pass,
        "filtered_odometry_minimum_five_contract_and_monotonicity": filtered_pass,
        "dynamic_odom_to_base_link_minimum_five_strictly_increasing_single_gid": dynamic_pass,
        "static_base_link_to_lidar_frame_qos_and_transform_exact": static_pass,
        "map_to_odom_absent_during_observation_window": not map_to_odom,
        "observer_errors_absent": not observer_errors,
    }
    reasons = {}
    if not clock_pass:
        stamps = [sample.get("stamp", {}) for sample in clock_samples]
        if len(clock_samples) < 5:
            reason = "CLOCK_TIMEOUT_MINIMUM_FIVE_SAMPLES"
        elif not all(_valid_nonzero_stamp(stamp) for stamp in stamps):
            reason = "CLOCK_TIMESTAMP_ZERO_OR_INVALID"
        else:
            reason = "CLOCK_TIMESTAMP_NOT_STRICTLY_INCREASING"
        reasons["/clock"] = clock.get("timeout_reason") or reason
    if not filtered_pass:
        reasons["/odometry/filtered"] = filtered.get("timeout_reason") or (filtered_reasons[0] if filtered_reasons else "FILTERED_ODOMETRY_CONTRACT_FAILED")
    if not dynamic_pass:
        if len(dynamic_gids) > 1:
            reason = "TF_DYNAMIC_EDGE_GID_CARDINALITY_NOT_ONE"
        elif len(dynamic) >= 2 and not _strictly_increasing(dynamic_times):
            reason = "TF_DYNAMIC_EDGE_TIMESTAMP_NOT_STRICTLY_INCREASING"
        else:
            reason = "TF_DYNAMIC_EDGE_TIMEOUT_MINIMUM_FIVE_EDGES"
        reasons["/tf:odom->base_link"] = tf_obs.get("timeout_reason") or reason
    if not static_pass:
        reasons["/tf_static:base_link->lidar_frame"] = static_obs.get("timeout_reason") or (
            "TF_STATIC_QOS_CONTRACT_MISMATCH" if not static_qos_pass else "TF_STATIC_EDGE_MISSING_OR_TRANSFORM_MISMATCH"
        )
    if map_to_odom:
        reasons["map->odom"] = "MAP_TO_ODOM_EDGE_OBSERVED"
    elif tf_obs.get("window_complete") is not True:
        result["map_to_odom_absent_during_observation_window"] = False
        reasons["map->odom"] = "TF_OBSERVATION_WINDOW_INCOMPLETE"
    if observer_errors:
        reasons["observer_errors_absent"] = "RUNTIME_OBSERVER_CALLBACK_OR_API_ERROR"
    return {"acceptance": result, "failure_reason_literals": reasons}


def collect_and_write(output_path, timeout_seconds=30.0):
    """Collect a full observation window once and write canonical JSON, fail-closed."""
    output_path = Path(output_path)
    started = _now()
    observations = {
        "/clock": {"type": "rosgraph_msgs/msg/Clock", "samples": [], "timeout_reason": None},
        "/odometry/filtered": {"type": "nav_msgs/msg/Odometry", "samples": [], "parse_errors": [], "timeout_reason": None},
        "/tf": {"type": "tf2_msgs/msg/TFMessage", "transforms": [], "timeout_reason": None},
        "/tf_static": {"type": "tf2_msgs/msg/TFMessage", "transforms": [], "timeout_reason": None},
    }
    errors = []
    qos_used = dict(STATIC_QOS_CONTRACT)
    runtime = {}
    rclpy_module = None
    node = None
    executor = None
    initialized_here = False
    try:
        import rclpy as rclpy_module
        from rclpy.executors import SingleThreadedExecutor
        from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
        from nav_msgs.msg import Odometry
        from rosgraph_msgs.msg import Clock
        from tf2_msgs.msg import TFMessage

        if not rclpy_module.ok():
            rclpy_module.init(args=None)
            initialized_here = True
        runtime["rclpy_initialized_here"] = initialized_here
        node = rclpy_module.create_node("wp06_6f_multisample_runtime_observer")
        executor = SingleThreadedExecutor()
        executor.add_node(node)

        def clock_cb(message):
            stamp = message.clock
            value = {"sec": int(stamp.sec), "nanosec": int(stamp.nanosec)}
            observations["/clock"]["samples"].append({"stamp": value, "stamp_ns": _stamp_ns(stamp)})

        def odom_cb(message):
            try:
                payload = _json_value(message)
                stamp = message.header.stamp
                observations["/odometry/filtered"]["samples"].append({"stamp": {"sec": int(stamp.sec), "nanosec": int(stamp.nanosec)}, "stamp_ns": _stamp_ns(stamp), "message": payload})
            except Exception as exc:
                observations["/odometry/filtered"]["parse_errors"].append(f"ODOMETRY_SAMPLE_SERIALIZATION_ERROR:{type(exc).__name__}:{exc}")

        def tf_cb(topic):
            def callback(message, info):
                try:
                    raw_gid = bytes(info.publisher_gid)
                    gid = raw_gid.hex()
                    if not raw_gid or not any(raw_gid):
                        raise ValueError("PUBLISHER_GID_UNAVAILABLE")
                    for transform in message.transforms:
                        row = {
                            "parent": transform.header.frame_id,
                            "child": transform.child_frame_id,
                            "stamp_ns": _stamp_ns(transform.header.stamp),
                            "stamp": {"sec": int(transform.header.stamp.sec), "nanosec": int(transform.header.stamp.nanosec)},
                            "publisher_gid": gid,
                            "translation": [float(transform.transform.translation.x), float(transform.transform.translation.y), float(transform.transform.translation.z)],
                            "rotation_xyzw": [float(transform.transform.rotation.x), float(transform.transform.rotation.y), float(transform.transform.rotation.z), float(transform.transform.rotation.w)],
                        }
                        if (topic == "/tf" and (row["parent"], row["child"]) in {("odom", "base_link"), ("map", "odom")}) or (topic == "/tf_static" and (row["parent"], row["child"]) in {("base_link", "lidar_frame"), ("map", "odom")}):
                            observations[topic]["transforms"].append(row)
                except Exception as exc:
                    errors.append(f"{topic}_MESSAGE_INFO_OR_PARSE_FAILED:{type(exc).__name__}:{exc}")
            return callback

        node.create_subscription(Clock, "/clock", clock_cb, QoSProfile(depth=100))
        node.create_subscription(Odometry, "/odometry/filtered", odom_cb, QoSProfile(depth=100))
        node.create_subscription(TFMessage, "/tf", tf_cb("/tf"), QoSProfile(depth=100), with_info=True)
        static_qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
        )
        node.create_subscription(TFMessage, "/tf_static", tf_cb("/tf_static"), static_qos, with_info=True)

        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            executor.spin_once(timeout_sec=min(0.1, max(0.0, deadline - time.monotonic())))
        observations["/tf"]["window_complete"] = True
        observations["/tf_static"]["window_complete"] = True
        runtime["observed_window_seconds"] = timeout_seconds
    except Exception as exc:
        errors.append(f"OBSERVER_INITIALIZATION_OR_SPIN_FAILED:{type(exc).__name__}:{exc}")
        observations["/tf"]["timeout_reason"] = "TF_OBSERVER_RUNTIME_API_UNAVAILABLE"
        observations["/tf_static"]["timeout_reason"] = "TF_OBSERVER_RUNTIME_API_UNAVAILABLE"
        for topic in ("/clock", "/odometry/filtered"):
            observations[topic]["timeout_reason"] = f"{topic.upper().replace('/', '').replace('_', '-')}_OBSERVER_RUNTIME_API_UNAVAILABLE"
        observations["/tf"]["window_complete"] = False
        observations["/tf_static"]["window_complete"] = False
    finally:
        if executor is not None:
            try:
                if node is not None:
                    executor.remove_node(node)
                executor.shutdown(timeout_sec=2.0)
            except Exception as exc:
                errors.append(f"OBSERVER_EXECUTOR_CLEANUP_FAILED:{type(exc).__name__}:{exc}")
        if node is not None:
            try:
                node.destroy_node()
            except Exception as exc:
                errors.append(f"OBSERVER_NODE_CLEANUP_FAILED:{type(exc).__name__}:{exc}")
        if initialized_here and rclpy_module is not None:
            try:
                rclpy_module.shutdown()
            except Exception as exc:
                errors.append(f"OBSERVER_RCLPY_CLEANUP_FAILED:{type(exc).__name__}:{exc}")

    if not observations["/clock"]["samples"]:
        observations["/clock"]["timeout_reason"] = observations["/clock"]["timeout_reason"] or "CLOCK_TIMEOUT_NO_SAMPLE"
    elif len(observations["/clock"]["samples"]) < 5:
        observations["/clock"]["timeout_reason"] = "CLOCK_TIMEOUT_MINIMUM_FIVE_SAMPLES"
    if len(observations["/odometry/filtered"]["samples"]) < 5:
        observations["/odometry/filtered"]["timeout_reason"] = "FILTERED_ODOMETRY_TIMEOUT_MINIMUM_FIVE_SAMPLES"
    if len([r for r in observations["/tf"]["transforms"] if r["parent"] == "odom" and r["child"] == "base_link"]) < 5:
        observations["/tf"]["timeout_reason"] = "TF_DYNAMIC_ODOM_BASE_LINK_TIMEOUT_MINIMUM_FIVE_EDGES"
    if not any(r["parent"] == "base_link" and r["child"] == "lidar_frame" for r in observations["/tf_static"]["transforms"]):
        observations["/tf_static"]["timeout_reason"] = "TF_STATIC_BASE_LINK_LIDAR_FRAME_TIMEOUT"

    evaluated = evaluate_observations(observations, qos_used, errors)
    document = {
        "schema": OBSERVER_SCHEMA,
        "started_at": started,
        "finished_at": _now(),
        "timeout_seconds": timeout_seconds,
        "topics": observations,
        "qos_used": {"/tf_static": qos_used},
        "runtime": runtime,
        "observer_errors": errors,
        **evaluated,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8"))
    return document
