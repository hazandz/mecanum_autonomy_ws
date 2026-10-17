"""Offline-tested, import-inert Gazebo scan endpoint observation probe.

This module does not make an endpoint pin or implement a ROS bridge. Calling
the CLI is reserved for a future, separately authorized capacity-one session.
"""

from collections.abc import Mapping
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path


SCHEMA = "mecanum_sim_eval_scan_endpoint_probe/v2"
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
    "maximum_candidate_topics": 16,
    "maximum_transcript_bytes_per_stream": 1048576,
    "selection_rule": "EXACT_LEAF_SCAN_THEN_PUBLISHER_TYPE",
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
        "NO_CANDIDATE_TOPIC",
        "NO_PUBLISHER_MATCH",
        "AMBIGUOUS_PUBLISHER_MATCHES",
        "TOPIC_INFO_UNRECOGNIZED",
        "GZ_COMMAND_NOT_FOUND",
        "GZ_COMMAND_TIMEOUT",
        "GZ_COMMAND_FAILED",
        "TOO_MANY_CANDIDATE_TOPICS",
        "TRANSCRIPT_LIMIT_EXCEEDED",
        "INVALID_PROBE_CONFIGURATION",
    }
)

_ABSOLUTE_TOPIC = re.compile(
    r"^/(?:[A-Za-z0-9_][A-Za-z0-9_.-]*)(?:/[A-Za-z0-9_][A-Za-z0-9_.-]*)*$"
)
_TYPE_TOKEN = re.compile(r"^[A-Za-z][A-Za-z0-9_.]*$")
_LEGACY_TYPE = re.compile(r"^\s*Type:\s*([A-Za-z][A-Za-z0-9_.]*)\s*$")
_PUBLISHERS_HEADER = re.compile(
    r"^\s*Publishers\s+\[Address,\s*Message Type\]:\s*$"
)
_SUBSCRIBERS_HEADER = re.compile(
    r"^\s*Subscribers\s+\[Address,\s*Message Type\]:\s*$"
)
_ENDPOINT_LINE = re.compile(r"^\s*<([^<>]+)>\s*,\s*([A-Za-z][A-Za-z0-9_.]*)\s*$")


class ProbeConfigurationError(ValueError):
    """Raised only when a descriptor is not the exact static contract."""


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
    """Accept only the exact versioned static descriptor."""
    _validate_exact(descriptor, STATIC_DESCRIPTOR)
    return True


def _valid_absolute_topic(topic):
    return isinstance(topic, str) and _ABSOLUTE_TOPIC.fullmatch(topic) is not None


def _parse_topic_listing(raw):
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        return None
    topics = [line.strip() for line in text.splitlines() if line.strip()]
    if any(not _valid_absolute_topic(topic) for topic in topics):
        return None
    return topics


def _parse_topic_info(raw):
    """Return (recognized, publisher message types) for two exact grammars."""
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        return False, ()
    lines = text.splitlines()
    legacy = []
    for line in lines:
        match = _LEGACY_TYPE.fullmatch(line)
        if match:
            legacy.append(match.group(1))
    publisher_headers = [i for i, line in enumerate(lines) if _PUBLISHERS_HEADER.fullmatch(line)]
    subscriber_headers = [i for i, line in enumerate(lines) if _SUBSCRIBERS_HEADER.fullmatch(line)]
    if len(legacy) > 1 or len(publisher_headers) > 1 or len(subscriber_headers) > 1:
        return False, ()
    if legacy and publisher_headers:
        return False, ()
    if legacy:
        return True, tuple(legacy)
    if not publisher_headers and not subscriber_headers:
        return False, ()

    publisher_types = []
    if publisher_headers:
        start = publisher_headers[0] + 1
        later_headers = [i for i in range(start, len(lines)) if re.fullmatch(r"\s*[A-Za-z][A-Za-z ]*\s+\[.*\]:\s*", lines[i])]
        end = min(later_headers) if later_headers else len(lines)
        for line in lines[start:end]:
            if not line.strip():
                continue
            entry = _ENDPOINT_LINE.fullmatch(line)
            if not entry or not entry.group(1).strip() or not _TYPE_TOKEN.fullmatch(entry.group(2)):
                return False, ()
            publisher_types.append(entry.group(2))
    # A subscribers-only section is recognized but never contributes matches.
    if subscriber_headers and not publisher_headers:
        start = subscriber_headers[0] + 1
        for line in lines[start:]:
            if not line.strip():
                continue
            if re.fullmatch(r"\s*[A-Za-z][A-Za-z ]*\s+\[.*\]:\s*", line):
                break
            if not _ENDPOINT_LINE.fullmatch(line):
                return False, ()
    return True, tuple(publisher_types)


def _as_raw_bytes(value):
    if value is None:
        return b""
    if isinstance(value, bytes):
        return value
    if isinstance(value, str):
        return value.encode("utf-8")
    return None


def _write_transcript(transcript_directory, command_index, stdout, stderr):
    directory = Path(transcript_directory)
    stdout_path = directory / f"command-{command_index:04d}.stdout.bin"
    stderr_path = directory / f"command-{command_index:04d}.stderr.bin"
    stdout_path.write_bytes(stdout)
    stderr_path.write_bytes(stderr)
    relative_base = Path("transcripts") / f"command-{command_index:04d}"
    return {
        "transcript_path": relative_base.as_posix(),
        "stdout_path": (relative_base.parent / f"{relative_base.name}.stdout.bin").as_posix(),
        "stdout_sha256": hashlib.sha256(stdout).hexdigest(),
        "stdout_size_bytes": len(stdout),
        "stderr_path": (relative_base.parent / f"{relative_base.name}.stderr.bin").as_posix(),
        "stderr_sha256": hashlib.sha256(stderr).hexdigest(),
        "stderr_size_bytes": len(stderr),
    }


def _run_command(argv, command_runner, transcript_directory, command_index):
    timeout = COMMAND_CONTRACT["timeout_seconds"]
    try:
        completed = command_runner(
            argv,
            shell=False,
            capture_output=True,
            text=False,
            timeout=timeout,
            check=False,
        )
        stdout = _as_raw_bytes(getattr(completed, "stdout", None))
        stderr = _as_raw_bytes(getattr(completed, "stderr", None))
        if stdout is None or stderr is None:
            stdout, stderr = b"", b""
            outcome = "GZ_COMMAND_FAILED"
            returncode = getattr(completed, "returncode", None)
        else:
            returncode = getattr(completed, "returncode", None)
            outcome = None if returncode == 0 else "GZ_COMMAND_FAILED"
    except FileNotFoundError:
        stdout, stderr, returncode, outcome = b"", b"", None, "GZ_COMMAND_NOT_FOUND"
    except subprocess.TimeoutExpired as exc:
        stdout = _as_raw_bytes(exc.stdout) or b""
        stderr = _as_raw_bytes(exc.stderr) or b""
        returncode, outcome = None, "GZ_COMMAND_TIMEOUT"
    except OSError:
        stdout, stderr, returncode, outcome = b"", b"", None, "GZ_COMMAND_FAILED"

    files = _write_transcript(transcript_directory, command_index, stdout, stderr)
    observation = {
        "argv": list(argv),
        "returncode": returncode,
        "timeout": outcome == "GZ_COMMAND_TIMEOUT",
        "stdout_sha256": files["stdout_sha256"],
        "stdout_size_bytes": files["stdout_size_bytes"],
        "stderr_sha256": files["stderr_sha256"],
        "stderr_size_bytes": files["stderr_size_bytes"],
        "transcript_path": files["transcript_path"],
        "stdout_path": files["stdout_path"],
        "stderr_path": files["stderr_path"],
    }
    over_limit = (
        len(stdout) > COMMAND_CONTRACT["maximum_transcript_bytes_per_stream"]
        or len(stderr) > COMMAND_CONTRACT["maximum_transcript_bytes_per_stream"]
    )
    if over_limit:
        observation["transcript_limit_bytes_per_stream"] = COMMAND_CONTRACT[
            "maximum_transcript_bytes_per_stream"
        ]
        observation["transcript_limit_exceeded"] = True
        if outcome is None:
            outcome = "TRANSCRIPT_LIMIT_EXCEEDED"
    return stdout, stderr, outcome, observation


def _result(outcome, observations=(), matched_topics=(), detail=None):
    result = {
        "outcome": outcome,
        "observed_endpoints": [
            {
                "message_type": SENSOR_PROVENANCE["expected_gz_message_type"],
                "status": "OBSERVED_NOT_PINNED",
                "topic": topic,
            }
            for topic in matched_topics
        ],
        "command_observations": list(observations),
    }
    if detail is not None:
        result["detail"] = detail
    return result


def probe_scan_endpoint(
    descriptor=STATIC_DESCRIPTOR,
    command_runner=subprocess.run,
    transcript_directory=None,
):
    """List topics, then inspect only absolute topics whose leaf is ``scan``."""
    try:
        validate_probe_descriptor(descriptor)
        if transcript_directory is None or not Path(transcript_directory).is_dir():
            return _result("INVALID_PROBE_CONFIGURATION")
    except (ProbeConfigurationError, TypeError, AttributeError, OSError):
        return _result("INVALID_PROBE_CONFIGURATION")

    executable = COMMAND_CONTRACT["executable"]
    observations = []
    command_index = 1
    listing_argv = [executable, *COMMAND_CONTRACT["discovery_arguments"]]
    listing_raw, _, error, observation = _run_command(
        listing_argv, command_runner, transcript_directory, command_index
    )
    observations.append(observation)
    if error:
        return _result(error, observations)
    listing = _parse_topic_listing(listing_raw)
    if listing is None:
        return _result("TOPIC_INFO_UNRECOGNIZED", observations, detail="malformed topic listing")
    if len(listing) > COMMAND_CONTRACT["maximum_topics"]:
        return _result("TOO_MANY_CANDIDATE_TOPICS", observations)
    candidates = [topic for topic in listing if topic.rsplit("/", 1)[-1] == "scan"]
    if not candidates:
        return _result("NO_CANDIDATE_TOPIC", observations)
    if len(candidates) > COMMAND_CONTRACT["maximum_candidate_topics"]:
        return _result("TOO_MANY_CANDIDATE_TOPICS", observations)

    matches = []
    for topic in candidates:
        command_index += 1
        argv = [executable, *COMMAND_CONTRACT["inspect_prefix"], topic]
        info, _, error, observation = _run_command(
            argv, command_runner, transcript_directory, command_index
        )
        observations.append(observation)
        if error:
            return _result(error, observations)
        recognized, publisher_types = _parse_topic_info(info)
        if not recognized:
            return _result("TOPIC_INFO_UNRECOGNIZED", observations, detail=f"malformed info for {topic}")
        if SENSOR_PROVENANCE["expected_gz_message_type"] in publisher_types:
            matches.append(topic)
    if not matches:
        return _result("NO_PUBLISHER_MATCH", observations)
    if len(matches) > 1:
        return _result("AMBIGUOUS_PUBLISHER_MATCHES", observations, matches)
    return _result("EXACTLY_ONE_MATCH", observations, matches)


def canonical_json(value):
    """Serialize compact, sorted JSON suitable for UTF-8 stdout."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--transcript-directory", required=True)
    args = parser.parse_args(argv)
    result = probe_scan_endpoint(transcript_directory=args.transcript_directory)
    print(canonical_json(result))
    return 0 if result["outcome"] == "EXACTLY_ONE_MATCH" else 1


if __name__ == "__main__":
    raise SystemExit(main())
