"""Offline parser and fail-closed validator for the WP06-6F C++ observer JSON."""

from __future__ import annotations

import json
import math
from pathlib import Path
import re


OBSERVER_SCHEMA = "wp06_6f_cpp_runtime_observer/v3"
EXPECTED_EKF_NODE_NAME = "ekf_filter_node"
EXPECTED_STATIC_TF_NODE_NAME = "robot_state_publisher"
EXPECTED_DYNAMIC_TF_QOS = {
    "history": "KEEP_LAST",
    "depth": 100,
    "reliability": "BEST_EFFORT",
    "durability": "VOLATILE",
}
EXPECTED_STATIC_TF_QOS = {
    "history": "KEEP_LAST",
    "depth": 1,
    "reliability": "RELIABLE",
    "durability": "TRANSIENT_LOCAL",
}
EXPECTED_TRANSLATION = (-0.031765, 0.0, 0.140)
EXPECTED_ROTATION = (0.0, 0.0, 0.0, 1.0)
EXPECTED_ACCEPTANCE_KEYS = {
    "clock_minimum_five_nonzero_strictly_increasing",
    "dynamic_odom_to_base_link_minimum_five_strictly_increasing_single_gid_owned_by_ekf",
    "dynamic_tf_subscription_qos_contract",
    "filtered_odometry_minimum_five_contract_and_monotonicity",
    "map_to_odom_absent_during_full_window",
    "observer_errors_absent",
    "static_base_link_to_lidar_frame_exact",
    "static_tf_edge_publisher_gid_mappable",
    "static_tf_edge_publisher_gid_unique_mapped",
    "static_tf_owner_is_robot_state_publisher",
    "static_tf_subscription_qos_contract",
}
_GID_PATTERN = re.compile(r"^[0-9a-f]+$")


class ObserverDocumentError(ValueError):
    """Malformed or internally inconsistent C++ observer document."""


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ObserverDocumentError(f"DUPLICATE_JSON_KEY:{key}")
        result[key] = value
    return result


def _reject_constant(value):
    raise ObserverDocumentError(f"NONSTANDARD_JSON_CONSTANT:{value}")


def load_observer_json(path: str | Path) -> dict:
    """Read strict UTF-8 JSON and validate its meaning independent of byte formatting."""
    raw = Path(path).read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raise ObserverDocumentError("OBSERVER_JSON_BOM")
    try:
        document = json.loads(
            raw.decode("utf-8"), object_pairs_hook=_unique_pairs, parse_constant=_reject_constant
        )
    except UnicodeDecodeError as exc:
        raise ObserverDocumentError("OBSERVER_JSON_NOT_UTF8") from exc
    except json.JSONDecodeError as exc:
        raise ObserverDocumentError(f"OBSERVER_JSON_INVALID:{exc}") from exc
    if not isinstance(document, dict):
        raise ObserverDocumentError("OBSERVER_DOCUMENT_NOT_OBJECT")
    validate_observer_document(document)
    return document


def _stamp_ns(value: dict) -> int | None:
    if not isinstance(value, dict):
        return None
    sec, nanosec = value.get("sec"), value.get("nanosec")
    if type(sec) is not int or type(nanosec) is not int or sec < 0 or not 0 <= nanosec < 1_000_000_000:
        return None
    result = sec * 1_000_000_000 + nanosec
    return result if result > 0 else None


def _finite_tree(value) -> bool:
    if isinstance(value, bool) or value is None:
        return False
    if isinstance(value, (int, float)):
        return math.isfinite(float(value))
    if isinstance(value, list):
        return all(_finite_tree(item) for item in value)
    if isinstance(value, dict):
        return bool(value) and all(_finite_tree(item) for item in value.values())
    return False


def _strictly_increasing(values) -> bool:
    return len(values) >= 2 and all(left < right for left, right in zip(values, values[1:]))


def _require_object(value, literal: str) -> dict:
    if not isinstance(value, dict):
        raise ObserverDocumentError(literal)
    return value


def _require_object_rows(value, path: str) -> list[dict]:
    if not isinstance(value, list):
        raise ObserverDocumentError(f"OBSERVER_COLLECTION_NOT_ARRAY:{path}")
    for index, row in enumerate(value):
        if not isinstance(row, dict):
            raise ObserverDocumentError(f"OBSERVER_COLLECTION_ROW_NOT_OBJECT:{path}:{index}")
    return value


def _expected_clock(document):
    topic = document["topics"]["/clock"]
    samples = topic.get("samples", [])
    values = [_stamp_ns(item.get("stamp")) for item in samples]
    return len(samples) >= 5 and all(value is not None for value in values) and _strictly_increasing(values)


def _expected_filtered(document):
    samples = document["topics"]["/odometry/filtered"].get("samples", [])
    values = []
    for item in samples:
        message = item.get("message", {})
        stamp = _stamp_ns(message.get("header", {}).get("stamp"))
        if stamp is None or not item.get("valid"):
            return False
        if message.get("header", {}).get("frame_id") != "odom" or message.get("child_frame_id") != "base_link":
            return False
        pose = message.get("pose", {})
        twist = message.get("twist", {})
        if len(pose.get("covariance", [])) != 36 or len(twist.get("covariance", [])) != 36:
            return False
        if not _finite_tree(pose) or not _finite_tree(twist):
            return False
        values.append(stamp)
    return len(samples) >= 5 and _strictly_increasing(values)


def _endpoint_mapping(document):
    transforms = [
        row for row in document["topics"]["/tf"].get("transforms", [])
        if row.get("parent") == "odom" and row.get("child") == "base_link"
    ]
    gids = {row.get("publisher_gid") for row in transforms}
    if len(gids) != 1 or None in gids:
        return False, False
    gid = next(iter(gids))
    if not isinstance(gid, str) or not gid or len(gid) % 2 or _GID_PATTERN.fullmatch(gid) is None:
        return False, False
    endpoints = document.get("graph_endpoint_snapshot", {}).get("/tf", [])
    matches = [item for item in endpoints if item.get("gid") == gid]
    unique = len(matches) == 1
    expected_owner = (
        unique and matches[0].get("node_name") == document.get("expected_ekf_node_name")
        and matches[0].get("node_namespace") == "/"
        and matches[0].get("topic_type") == "tf2_msgs/msg/TFMessage"
    )
    mappings = [item for item in document.get("endpoint_mapping", []) if item.get("gid") == gid]
    mapping_agrees = (
        len(mappings) == 1 and mappings[0].get("unique") is True and
        mappings[0].get("match_count") == 1 and mappings[0].get("expected_owner") is expected_owner
    )
    return unique and mapping_agrees, expected_owner and mapping_agrees


def _expected_dynamic_tf(document):
    topic = document["topics"]["/tf"]
    transforms = [
        row for row in topic.get("transforms", [])
        if row.get("parent") == "odom" and row.get("child") == "base_link"
    ]
    values = [row.get("stamp_ns") for row in transforms]
    basic = (
        len(transforms) >= 5 and all(type(value) is int and value > 0 for value in values) and
        _strictly_increasing(values) and all(row.get("valid") is True for row in transforms)
    )
    unique_gid, expected_owner = _endpoint_mapping(document)
    return basic and len({row.get("publisher_gid") for row in transforms}) == 1 and unique_gid and expected_owner


def _static_transform_pass(document):
    transforms = [
        row for row in document["topics"]["/tf_static"].get("transforms", [])
        if row.get("parent") == "base_link" and row.get("child") == "lidar_frame"
    ]
    if len(transforms) != 1:
        return False
    row = transforms[0]
    translation, rotation = row.get("translation"), row.get("rotation_xyzw")
    return (
        row.get("valid") is True and isinstance(translation, list) and len(translation) == 3 and
        isinstance(rotation, list) and len(rotation) == 4 and _finite_tree(translation) and _finite_tree(rotation) and
        all(abs(float(a) - b) <= 1e-9 for a, b in zip(translation, EXPECTED_TRANSLATION)) and
        all(abs(float(a) - b) <= 1e-9 for a, b in zip(rotation, EXPECTED_ROTATION))
    )


def _static_gid_mapping(document):
    transforms = [
        row for row in document["topics"]["/tf_static"].get("transforms", [])
        if row.get("parent") == "base_link" and row.get("child") == "lidar_frame"
    ]
    snapshots = document.get("graph_endpoint_snapshot", {})
    endpoints = snapshots.get("/tf_static", []) if isinstance(snapshots, dict) else []
    mappings = document.get("static_endpoint_mapping", [])
    if len(transforms) != 1:
        return False, False, False, "TF_STATIC_EDGE_MISSING_OR_TRANSFORM_MISMATCH"
    gid = transforms[0].get("publisher_gid")
    if not isinstance(gid, str) or not gid or len(gid) % 2 or _GID_PATTERN.fullmatch(gid) is None:
        return False, False, False, "TF_STATIC_EDGE_PUBLISHER_GID_UNMAPPABLE"
    matches = [item for item in endpoints if isinstance(item, dict) and item.get("gid") == gid]
    mapping_rows = [item for item in mappings if isinstance(item, dict) and item.get("gid") == gid]
    if not matches:
        return False, False, False, "TF_STATIC_EDGE_PUBLISHER_GID_UNMAPPABLE"
    if len(matches) != 1 or len(mapping_rows) != 1 or mapping_rows[0].get("unique") is not True or mapping_rows[0].get("match_count") != 1:
        return True, False, False, "TF_STATIC_EDGE_PUBLISHER_GID_NOT_UNIQUE"
    endpoint = matches[0]
    owner = (
        endpoint.get("node_name") == EXPECTED_STATIC_TF_NODE_NAME and
        endpoint.get("node_namespace") == "/" and
        endpoint.get("topic_type") == "tf2_msgs/msg/TFMessage"
    )
    expected_endpoint = {key: endpoint.get(key) for key in ("node_name", "node_namespace", "topic_type")}
    if mapping_rows[0].get("mapped_endpoint") != expected_endpoint or mapping_rows[0].get("expected_owner") is not owner:
        return False, False, False, "TF_STATIC_EDGE_PUBLISHER_GID_UNMAPPABLE"
    if not owner:
        return True, True, False, "TF_STATIC_EDGE_PUBLISHER_NOT_ROBOT_STATE_PUBLISHER"
    return True, True, True, ""


def validate_observer_document(document: dict) -> dict:
    """Recompute acceptance from raw normalized observations and graph endpoint data."""
    if not isinstance(document, dict) or document.get("schema") != OBSERVER_SCHEMA:
        raise ObserverDocumentError("OBSERVER_SCHEMA_MISMATCH")
    topics = document.get("topics")
    required_topics = {"/clock", "/odometry/filtered", "/tf", "/tf_static"}
    if not isinstance(topics, dict) or not required_topics.issubset(topics):
        raise ObserverDocumentError("OBSERVER_REQUIRED_TOPICS_MISSING")
    expected_types = {
        "/clock": "rosgraph_msgs/msg/Clock",
        "/odometry/filtered": "nav_msgs/msg/Odometry",
        "/tf": "tf2_msgs/msg/TFMessage",
        "/tf_static": "tf2_msgs/msg/TFMessage",
    }
    for topic, message_type in expected_types.items():
        if not isinstance(topics[topic], dict):
            raise ObserverDocumentError(f"OBSERVER_TOPIC_DOCUMENT_NOT_OBJECT:{topic}")
        if topics[topic].get("type") != message_type:
            raise ObserverDocumentError(f"OBSERVER_TYPE_MISMATCH:{topic}")
    for topic, key in (
        ("/clock", "samples"),
        ("/odometry/filtered", "samples"),
        ("/tf", "transforms"),
        ("/tf_static", "transforms"),
    ):
        _require_object_rows(topics[topic].get(key), f"{topic}/{key}")
    _require_object_rows(document.get("observed_forbidden_edges"), "observed_forbidden_edges")
    graph_snapshot = document.get("graph_endpoint_snapshot")
    if (not isinstance(graph_snapshot, dict) or set(graph_snapshot) != {"/tf", "/tf_static"} or
        any(not isinstance(rows, list) for rows in graph_snapshot.values()) or
        not isinstance(document.get("endpoint_mapping"), list) or
        not isinstance(document.get("static_endpoint_mapping"), list)):
        raise ObserverDocumentError("OBSERVER_GRAPH_MAPPING_MISSING")
    for topic, rows in graph_snapshot.items():
        _require_object_rows(rows, f"graph_endpoint_snapshot/{topic}")
    _require_object_rows(document.get("endpoint_mapping"), "endpoint_mapping")
    _require_object_rows(document.get("static_endpoint_mapping"), "static_endpoint_mapping")
    for row in document["endpoint_mapping"] + document["static_endpoint_mapping"]:
        if row.get("mapped_endpoint") is not None and not isinstance(row.get("mapped_endpoint"), dict):
            raise ObserverDocumentError("OBSERVER_ENDPOINT_MAPPING_ROW_INVALID")
    if document.get("expected_ekf_node_name") != EXPECTED_EKF_NODE_NAME:
        raise ObserverDocumentError("OBSERVER_EKF_NODE_IDENTITY_MISMATCH")
    if document.get("expected_static_tf_node_name") != EXPECTED_STATIC_TF_NODE_NAME:
        raise ObserverDocumentError("OBSERVER_STATIC_TF_NODE_IDENTITY_MISMATCH")
    qos_used = document.get("qos_used")
    if not isinstance(qos_used, dict) or qos_used.get("/tf") != EXPECTED_DYNAMIC_TF_QOS:
        raise ObserverDocumentError("OBSERVER_QOS_CONTRACT_MISMATCH:/tf")
    if qos_used.get("/tf_static") != EXPECTED_STATIC_TF_QOS:
        raise ObserverDocumentError("OBSERVER_QOS_CONTRACT_MISMATCH:/tf_static")

    dynamic_rows = topics["/tf"].get("transforms", [])
    static_rows = topics["/tf_static"].get("transforms", [])
    forbidden_edges = document.get("observed_forbidden_edges", [])
    map_edge_seen = any(row.get("parent") == "map" and row.get("child") == "odom" for row in forbidden_edges)
    errors_absent = document.get("observer_errors") == []
    static_gid_mappable, static_gid_unique, static_owner, static_gid_reason = _static_gid_mapping(document)
    static_transform = _static_transform_pass(document)
    static_qos = qos_used["/tf_static"] == EXPECTED_STATIC_TF_QOS
    expected = {
        "clock_minimum_five_nonzero_strictly_increasing": _expected_clock(document),
        "dynamic_odom_to_base_link_minimum_five_strictly_increasing_single_gid_owned_by_ekf": _expected_dynamic_tf(document),
        "dynamic_tf_subscription_qos_contract": qos_used["/tf"] == EXPECTED_DYNAMIC_TF_QOS,
        "filtered_odometry_minimum_five_contract_and_monotonicity": _expected_filtered(document),
        "map_to_odom_absent_during_full_window": not map_edge_seen and document.get("window_complete") is True,
        "observer_errors_absent": errors_absent,
        "static_base_link_to_lidar_frame_exact": static_transform,
        "static_tf_edge_publisher_gid_mappable": static_gid_mappable,
        "static_tf_edge_publisher_gid_unique_mapped": static_gid_unique,
        "static_tf_owner_is_robot_state_publisher": static_owner,
        "static_tf_subscription_qos_contract": static_qos,
    }
    if document.get("acceptance") != expected:
        raise ObserverDocumentError("OBSERVER_ACCEPTANCE_DOES_NOT_MATCH_RAW_DATA")
    reasons = document.get("failure_reason_literals")
    if not isinstance(reasons, dict):
        raise ObserverDocumentError("OBSERVER_FAILURE_REASONS_MISSING")
    reason_keys = {
        "clock_minimum_five_nonzero_strictly_increasing": "/clock",
        "filtered_odometry_minimum_five_contract_and_monotonicity": "/odometry/filtered",
        "dynamic_odom_to_base_link_minimum_five_strictly_increasing_single_gid_owned_by_ekf": "/tf:odom->base_link",
        "static_base_link_to_lidar_frame_exact": "/tf_static:base_link->lidar_frame",
        "static_tf_edge_publisher_gid_mappable": "/tf_static:base_link->lidar_frame",
        "static_tf_edge_publisher_gid_unique_mapped": "/tf_static:base_link->lidar_frame",
        "static_tf_owner_is_robot_state_publisher": "/tf_static:base_link->lidar_frame",
        "static_tf_subscription_qos_contract": "/tf_static:qos",
        "map_to_odom_absent_during_full_window": "map->odom",
        "observer_errors_absent": "observer_errors",
    }
    for acceptance_key, reason_key in reason_keys.items():
        if not expected[acceptance_key] and not isinstance(reasons.get(reason_key), str):
            raise ObserverDocumentError(f"OBSERVER_FAILURE_REASON_MISSING:{reason_key}")
    if not static_transform and static_gid_reason == "TF_STATIC_EDGE_MISSING_OR_TRANSFORM_MISMATCH":
        pass
    elif (not static_gid_mappable or (static_gid_mappable and not static_gid_unique) or
          (static_gid_unique and not static_owner)) and reasons.get("/tf_static:base_link->lidar_frame") != static_gid_reason:
        raise ObserverDocumentError("OBSERVER_STATIC_GID_FAILURE_REASON_MISMATCH")
    if not static_transform and reasons.get("/tf_static:base_link->lidar_frame") != "TF_STATIC_EDGE_MISSING_OR_TRANSFORM_MISMATCH":
        raise ObserverDocumentError("OBSERVER_STATIC_TRANSFORM_FAILURE_REASON_MISMATCH")
    if static_gid_unique and not static_owner and reasons.get("/tf_static:base_link->lidar_frame") != "TF_STATIC_EDGE_PUBLISHER_NOT_ROBOT_STATE_PUBLISHER":
        raise ObserverDocumentError("OBSERVER_STATIC_OWNER_FAILURE_REASON_MISMATCH")
    if not static_qos and reasons.get("/tf_static:qos") != "TF_STATIC_QOS_CONTRACT_MISMATCH":
        raise ObserverDocumentError("OBSERVER_STATIC_QOS_FAILURE_REASON_MISMATCH")
    all_pass = all(expected.values())
    expected_outcome = "PASS" if all_pass else "FAIL_NO_RETRY"
    if reasons.get("/tf:odom->base_link") == "TF_EDGE_PUBLISHER_GID_UNMAPPABLE":
        expected_outcome = "TF_EDGE_PUBLISHER_GID_UNMAPPABLE"
    if document.get("terminal_outcome") != expected_outcome:
        raise ObserverDocumentError("OBSERVER_TERMINAL_OUTCOME_MISMATCH")
    return {"acceptance": expected, "all_pass": all_pass, "failure_reason_literals": reasons}
