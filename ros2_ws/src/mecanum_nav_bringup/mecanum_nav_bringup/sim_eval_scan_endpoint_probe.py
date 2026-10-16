"""Offline-tested source for future, separately authorized Gazebo topic discovery.

Importing this module is inert. The command-line entry point is not permission
to run it; execution requires a separate capacity-one APPROVED_RUNTIME packet.
"""

from collections.abc import Mapping
import json
import re
import subprocess


SCHEMA = "mecanum_sim_eval_scan_endpoint_probe/v1"
PROFILE = "sim_eval"
CLASSIFICATION = "PROBE_SOURCE_ONLY"
RUNTIME_ELIGIBLE = False
SENSOR_PROVENANCE = {
    "source_file": "ros2_ws/src/ROBOT_URDF_final_description/urdf/ROBOT_URDF_final.gazebo",
    "reference_link": "lidar_frame",
    "sensor_name": "YDLIDAR_X3_PRO",
    "sensor_type": "gpu_lidar",
    "declared_relative_topic": "scan",
    "expected_gz_message_type": "gz.msgs.LaserScan",
}
FUTURE_ROS_BOUNDARY = {
    "topic": "/scan",
    "message_type": "sensor_msgs/msg/LaserScan",
    "direction": "GZ_TO_ROS",
}
COMMAND_CONTRACT = {
    "executable": "gz",
    "discovery_arguments": ["topic", "-l"],
    "inspect_prefix": ["topic", "-i", "-t"],
    "timeout_seconds": 5.0,
    "maximum_topics": 512,
    "selection_rule": "EXACTLY_ONE_EXPECTED_GZ_MESSAGE_TYPE",
}
PROHIBITIONS = {
    "no_ros2": True,
    "no_ros_gz_bridge": True,
    "no_gz_topic_echo": True,
    "no_bridge_launch": True,
    "no_endpoint_pin": True,
    "no_bridge_config_mutation": True,
    "no_ros_publisher_or_subscriber": True,
    "no_tf": True,
    "no_map_server_amcl_ekf_or_nav2": True,
}
STATIC_DESCRIPTOR = {
    "schema": SCHEMA,
    "profile": PROFILE,
    "classification": CLASSIFICATION,
    "runtime_eligible": RUNTIME_ELIGIBLE,
    "sensor_provenance": SENSOR_PROVENANCE,
    "future_ros_boundary": FUTURE_ROS_BOUNDARY,
    "command_contract": COMMAND_CONTRACT,
    "prohibitions": PROHIBITIONS,
}

OUTCOMES = frozenset(
    {
        "EXACTLY_ONE_MATCH",
        "NO_MATCH",
        "AMBIGUOUS_MATCHES",
        "GZ_COMMAND_NOT_FOUND",
        "GZ_COMMAND_TIMEOUT",
        "GZ_COMMAND_FAILED",
        "UNRECOGNIZED_TOPIC_INFO",
        "TOO_MANY_TOPICS",
        "INVALID_PROBE_CONFIGURATION",
    }
)
_ABSOLUTE_TOPIC = re.compile(r"^/(?:[A-Za-z0-9_][A-Za-z0-9_.-]*)(?:/[A-Za-z0-9_][A-Za-z0-9_.-]*)*$")
_TYPE_LINE = re.compile(r"^\s*Type:\s*(\S+)\s*$", re.MULTILINE)
_EXPECTED_TYPE_TOKEN = re.compile(r"(?<![A-Za-z0-9_.])gz\.msgs\.LaserScan(?![A-Za-z0-9_.])")


class ProbeConfigurationError(ValueError):
    """Raised only by the exact static descriptor validator."""


def _validate_exact(actual, expected, path="descriptor"):
    if isinstance(expected, Mapping):
        if not isinstance(actual, Mapping) or set(actual) != set(expected):
            raise ProbeConfigurationError(f"{path}: missing or unexpected keys")
        for key, value in expected.items():
            _validate_exact(actual[key], value, f"{path}.{key}")
        return
    if isinstance(expected, list):
        if type(actual) is not list or len(actual) != len(expected):
            raise ProbeConfigurationError(f"{path}: list differs from contract")
        for index, (item, wanted) in enumerate(zip(actual, expected)):
            _validate_exact(item, wanted, f"{path}[{index}]")
        return
    if type(actual) is not type(expected) or actual != expected:
        raise ProbeConfigurationError(f"{path}: value differs from contract")


def validate_probe_descriptor(descriptor):
    """Return True only for the exact static probe descriptor."""
    _validate_exact(descriptor, STATIC_DESCRIPTOR)
    return True


def _result(outcome, observed_topics=(), detail=None):
    result = {"outcome": outcome}
    if outcome in {"EXACTLY_ONE_MATCH", "AMBIGUOUS_MATCHES"}:
        result["observed_endpoints"] = [
            {
                "message_type": SENSOR_PROVENANCE["expected_gz_message_type"],
                "status": "OBSERVED_NOT_PINNED",
                "topic": topic,
            }
            for topic in observed_topics
        ]
    else:
        result["observed_endpoints"] = []
    if detail is not None:
        result["detail"] = detail
    return result


def _run_command(command, command_runner):
    try:
        completed = command_runner(
            command,
            shell=False,
            capture_output=True,
            text=True,
            timeout=COMMAND_CONTRACT["timeout_seconds"],
            check=False,
        )
    except FileNotFoundError:
        return None, "GZ_COMMAND_NOT_FOUND"
    except subprocess.TimeoutExpired:
        return None, "GZ_COMMAND_TIMEOUT"
    except OSError:
        return None, "GZ_COMMAND_FAILED"
    if getattr(completed, "returncode", None) != 0:
        return None, "GZ_COMMAND_FAILED"
    stdout = getattr(completed, "stdout", None)
    if not isinstance(stdout, str):
        return None, "GZ_COMMAND_FAILED"
    return stdout, None


def _valid_absolute_topic(topic):
    return isinstance(topic, str) and _ABSOLUTE_TOPIC.fullmatch(topic) is not None


def _extract_type_token(topic_info):
    matches = _TYPE_LINE.findall(topic_info)
    if len(matches) != 1:
        return None
    token = matches[0]
    if _EXPECTED_TYPE_TOKEN.fullmatch(token):
        return token
    # A syntactically present, non-LaserScan type is a recognized non-match.
    if re.fullmatch(r"[A-Za-z][A-Za-z0-9_.]*", token):
        return token
    return None


def probe_scan_endpoint(descriptor=STATIC_DESCRIPTOR, command_runner=subprocess.run):
    """Discover exact Gazebo LaserScan type matches without pinning endpoints.

    This function performs subprocess calls when explicitly invoked. It must
    only be invoked by a separately approved runtime packet in the future.
    """
    try:
        validate_probe_descriptor(descriptor)
    except (ProbeConfigurationError, TypeError, AttributeError):
        return _result("INVALID_PROBE_CONFIGURATION")

    executable = COMMAND_CONTRACT["executable"]
    discovery = [executable, *COMMAND_CONTRACT["discovery_arguments"]]
    listing, error = _run_command(discovery, command_runner)
    if error:
        return _result(error)

    topics = [line.strip() for line in listing.splitlines() if line.strip()]
    if len(topics) > COMMAND_CONTRACT["maximum_topics"]:
        return _result("TOO_MANY_TOPICS")
    if any(not _valid_absolute_topic(topic) for topic in topics):
        return _result("UNRECOGNIZED_TOPIC_INFO", detail="discovery returned a malformed topic")

    matches = []
    for topic in topics:
        inspect = [executable, *COMMAND_CONTRACT["inspect_prefix"], topic]
        topic_info, error = _run_command(inspect, command_runner)
        if error:
            return _result(error)
        type_token = _extract_type_token(topic_info)
        if type_token is None:
            return _result("UNRECOGNIZED_TOPIC_INFO")
        if type_token == SENSOR_PROVENANCE["expected_gz_message_type"]:
            matches.append(topic)

    if not matches:
        return _result("NO_MATCH")
    if len(matches) > 1:
        return _result("AMBIGUOUS_MATCHES", matches)
    return _result("EXACTLY_ONE_MATCH", matches)


def canonical_json(result):
    """Serialize a probe result as compact, sorted UTF-8-compatible JSON."""
    return json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def main():
    result = probe_scan_endpoint()
    print(canonical_json(result))
    return 0 if result["outcome"] == "EXACTLY_ONE_MATCH" else 1


if __name__ == "__main__":
    raise SystemExit(main())
