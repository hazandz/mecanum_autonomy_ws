"""Offline-testable source for a future, separately approved Gazebo topic probe.

Importing this module is inert. The command runner is invoked only by the
explicit CLI entry point or by a caller invoking ``probe_endpoint``.
"""

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
import json
import re
import subprocess
import sys


STATIC_DESCRIPTOR = {
    "schema": "mecanum_sim_eval_scan_endpoint_probe/v1",
    "profile": "sim_eval",
    "classification": "PROBE_SOURCE_ONLY",
    "runtime_eligible": False,
    "sensor_provenance": {
        "source_file": "ros2_ws/src/ROBOT_URDF_final_description/urdf/ROBOT_URDF_final.gazebo",
        "reference_link": "lidar_frame",
        "sensor_name": "YDLIDAR_X3_PRO",
        "sensor_type": "gpu_lidar",
        "declared_relative_topic": "scan",
        "expected_gz_message_type": "gz.msgs.LaserScan",
    },
    "expected_future_ros_boundary": {
        "topic": "/scan",
        "ros_message_type": "sensor_msgs/msg/LaserScan",
        "direction": "GZ_TO_ROS",
    },
    "command_contract": {
        "executable": "gz",
        "discovery_arguments": ["topic", "-l"],
        "inspect_arguments_prefix": ["topic", "-i", "-t"],
        "default_timeout_seconds": 5.0,
        "maximum_discovered_topics": 512,
        "selection_rule": "EXACTLY_ONE_EXPECTED_GZ_MESSAGE_TYPE",
        "outcomes": [
            "EXACTLY_ONE_MATCH",
            "NO_MATCH",
            "AMBIGUOUS_MATCHES",
            "GZ_COMMAND_NOT_FOUND",
            "GZ_COMMAND_TIMEOUT",
            "GZ_COMMAND_FAILED",
            "UNRECOGNIZED_TOPIC_INFO",
            "TOO_MANY_TOPICS",
            "INVALID_PROBE_CONFIGURATION",
        ],
    },
    "prohibitions": {
        "forbidden_commands": ["ros2", "ros_gz_bridge", "gz topic -e", "bridge_launch"],
        "forbidden_ros_components": ["ROS publisher", "ROS subscriber", "TF", "Map Server", "AMCL", "EKF", "Nav2"],
        "no_endpoint_pin": True,
        "no_bridge_config_mutation": True,
        "no_ros_publisher_subscriber_tf_or_navigation_nodes": True,
    },
}
_EXPECTED_DESCRIPTOR = deepcopy(STATIC_DESCRIPTOR)


@dataclass(frozen=True)
class ProbeResult:
    outcome: str
    observed_endpoints: tuple = ()

    def as_dict(self):
        return {
            "endpoint_status": "OBSERVED_NOT_PINNED",
            "observed_endpoints": list(self.observed_endpoints),
            "outcome": self.outcome,
        }


class InvalidProbeConfiguration(ValueError):
    """Raised by the validator for a descriptor outside the exact contract."""


def _validate_exact(actual, expected, path="descriptor"):
    if isinstance(expected, Mapping):
        if not isinstance(actual, Mapping) or set(actual) != set(expected):
            raise InvalidProbeConfiguration(f"{path} has missing or unexpected fields")
        for key, expected_value in expected.items():
            _validate_exact(actual[key], expected_value, f"{path}.{key}")
        return
    if isinstance(expected, list):
        if type(actual) is not list or len(actual) != len(expected):
            raise InvalidProbeConfiguration(f"{path} does not match the static contract")
        for index, (actual_value, expected_value) in enumerate(zip(actual, expected)):
            _validate_exact(actual_value, expected_value, f"{path}[{index}]")
        return
    if type(actual) is not type(expected) or actual != expected:
        raise InvalidProbeConfiguration(f"{path} does not match the static contract")


def validate_probe_configuration(configuration):
    """Accept only the exact static probe descriptor; performs no I/O."""
    _validate_exact(configuration, _EXPECTED_DESCRIPTOR)
    return None


_GZ_TYPE_TOKEN = re.compile(r"(?<![A-Za-z0-9_.])gz\.msgs\.[A-Za-z0-9_]+(?![A-Za-z0-9_.])")


def _valid_absolute_topic(topic):
    if not isinstance(topic, str) or not topic.startswith("/") or topic.startswith("//"):
        return False
    if any(character.isspace() for character in topic) or topic.endswith("/"):
        return False
    segments = topic[1:].split("/")
    return all(segment not in ("", ".", "..") for segment in segments)


def _run(runner, arguments, timeout):
    return runner(
        arguments,
        capture_output=True,
        text=True,
        timeout=timeout,
        shell=False,
        check=False,
    )


def probe_endpoint(configuration=STATIC_DESCRIPTOR, command_runner=None):
    """Observe topics typed as LaserScan without pinning or inferring an endpoint."""
    try:
        validate_probe_configuration(configuration)
    except (InvalidProbeConfiguration, TypeError, AttributeError):
        return ProbeResult("INVALID_PROBE_CONFIGURATION")

    runner = subprocess.run if command_runner is None else command_runner
    contract = configuration["command_contract"]
    timeout = contract["default_timeout_seconds"]
    executable = contract["executable"]

    try:
        discovery = _run(runner, [executable, *contract["discovery_arguments"]], timeout)
    except FileNotFoundError:
        return ProbeResult("GZ_COMMAND_NOT_FOUND")
    except subprocess.TimeoutExpired:
        return ProbeResult("GZ_COMMAND_TIMEOUT")
    except (OSError, subprocess.SubprocessError):
        return ProbeResult("GZ_COMMAND_FAILED")
    if type(getattr(discovery, "returncode", None)) is not int or not isinstance(getattr(discovery, "stdout", None), str):
        return ProbeResult("GZ_COMMAND_FAILED")
    if discovery.returncode != 0:
        return ProbeResult("GZ_COMMAND_FAILED")

    topics = [line.strip() for line in discovery.stdout.splitlines() if line.strip()]
    maximum = contract["maximum_discovered_topics"]
    if len(topics) > maximum:
        return ProbeResult("TOO_MANY_TOPICS")
    if any(not _valid_absolute_topic(topic) for topic in topics) or len(set(topics)) != len(topics):
        return ProbeResult("UNRECOGNIZED_TOPIC_INFO")

    expected_type = configuration["sensor_provenance"]["expected_gz_message_type"]
    matches = []
    inspect_prefix = [executable, *contract["inspect_arguments_prefix"]]
    for topic in topics:
        try:
            info = _run(runner, [*inspect_prefix, topic], timeout)
        except FileNotFoundError:
            return ProbeResult("GZ_COMMAND_NOT_FOUND")
        except subprocess.TimeoutExpired:
            return ProbeResult("GZ_COMMAND_TIMEOUT")
        except (OSError, subprocess.SubprocessError):
            return ProbeResult("GZ_COMMAND_FAILED")
        if type(getattr(info, "returncode", None)) is not int or not isinstance(getattr(info, "stdout", None), str):
            return ProbeResult("GZ_COMMAND_FAILED")
        if info.returncode != 0:
            return ProbeResult("GZ_COMMAND_FAILED")
        types = _GZ_TYPE_TOKEN.findall(info.stdout)
        if not types:
            return ProbeResult("UNRECOGNIZED_TOPIC_INFO")
        if expected_type in types:
            matches.append(topic)

    if len(matches) == 1:
        return ProbeResult("EXACTLY_ONE_MATCH", tuple(matches))
    if len(matches) > 1:
        return ProbeResult("AMBIGUOUS_MATCHES", tuple(matches))
    return ProbeResult("NO_MATCH")


def main(argv=None):
    """Emit one canonical JSON observation; only a unique match exits zero."""
    if argv not in (None, []):
        result = ProbeResult("INVALID_PROBE_CONFIGURATION")
    else:
        result = probe_endpoint()
    sys.stdout.write(json.dumps(result.as_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
    return 0 if result.outcome == "EXACTLY_ONE_MATCH" else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
