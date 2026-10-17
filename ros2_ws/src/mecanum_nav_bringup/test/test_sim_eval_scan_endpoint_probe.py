"""Offline tests for the import-inert, non-pinning endpoint observation tool."""

import ast
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
from unittest.mock import patch

import pytest
import yaml

from mecanum_nav_bringup import sim_eval_scan_endpoint_probe as probe
from mecanum_nav_bringup.sim_eval_static_profile_contract import STATIC_PROFILE_DESCRIPTOR


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PACKAGE_ROOT.parents[2]
YAML_PATH = PACKAGE_ROOT / "config/bridge/sim_eval_scan_endpoint_probe.static.yaml"
EXPECTED_DESCRIPTOR = {
    "schema": "mecanum_sim_eval_scan_endpoint_probe/v2",
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
    "future_ros_boundary": {
        "topic": "/scan",
        "message_type": "sensor_msgs/msg/LaserScan",
        "direction": "GZ_TO_ROS",
    },
    "command_contract": {
        "executable": "gz",
        "discovery_arguments": ["topic", "-l"],
        "inspect_prefix": ["topic", "-i", "-t"],
        "timeout_seconds": 5.0,
        "maximum_topics": 512,
        "maximum_candidate_topics": 16,
        "maximum_transcript_bytes_per_stream": 1048576,
        "selection_rule": "EXACT_LEAF_SCAN_THEN_PUBLISHER_TYPE",
    },
    "prohibitions": {
        "no_ros2": True,
        "no_ros_gz_bridge": True,
        "no_gz_topic_echo": True,
        "no_bridge_launch": True,
        "no_endpoint_pin": True,
        "no_bridge_config_mutation": True,
        "no_ros_publisher_or_subscriber": True,
        "no_tf": True,
        "no_map_server_amcl_ekf_or_nav2": True,
    },
}


class UniqueKeyLoader(yaml.SafeLoader):
    pass


def _unique_yaml_mapping(loader, node, deep=False):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in result:
            raise ValueError(f"duplicate YAML key: {key}")
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


UniqueKeyLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _unique_yaml_mapping)


def _sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class FakeRunner:
    def __init__(self, topics, info_by_topic=None, *, discovery_returncode=0, inspect_returncode=0):
        self.topics = topics
        self.info_by_topic = info_by_topic or {}
        self.discovery_returncode = discovery_returncode
        self.inspect_returncode = inspect_returncode
        self.calls = []

    def __call__(self, argv, **kwargs):
        self.calls.append((argv, kwargs))
        assert kwargs == {
            "shell": False, "capture_output": True, "text": False,
            "timeout": 5.0, "check": False,
        }
        if argv == ["gz", "topic", "-l"]:
            return subprocess.CompletedProcess(
                argv, self.discovery_returncode,
                "\n".join(self.topics).encode(), b"discovery-stderr",
            )
        assert argv[:4] == ["gz", "topic", "-i", "-t"]
        return subprocess.CompletedProcess(
            argv, self.inspect_returncode, self.info_by_topic.get(argv[4], b""), b"inspect-stderr",
        )


def _make_transcript_dir(tmp_path):
    directory = tmp_path / "transcripts"
    directory.mkdir(exist_ok=True)
    return directory


def _result_for(tmp_path, topics, info_by_topic=None, **runner_options):
    runner = FakeRunner(topics, info_by_topic, **runner_options)
    result = probe.probe_scan_endpoint(command_runner=runner, transcript_directory=_make_transcript_dir(tmp_path))
    return result, runner


def test_yaml_and_python_descriptor_are_exact():
    raw = YAML_PATH.read_bytes()
    assert raw.decode("utf-8").encode("utf-8") == raw
    assert not raw.startswith(b"\xef\xbb\xbf")
    descriptor = yaml.load(raw.decode("utf-8"), Loader=UniqueKeyLoader)
    assert descriptor == EXPECTED_DESCRIPTOR == probe.STATIC_DESCRIPTOR
    assert probe.validate_probe_descriptor(descriptor) is True


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d.update(schema="other/v2"),
        lambda d: d.update(profile="other"),
        lambda d: d["sensor_provenance"].update(expected_gz_message_type="gz.msgs.Other"),
        lambda d: d["future_ros_boundary"].update(direction="ROS_TO_GZ"),
        lambda d: d["command_contract"].update(maximum_candidate_topics=17),
        lambda d: d["command_contract"].update(maximum_transcript_bytes_per_stream=0),
        lambda d: d["prohibitions"].update(no_ros_gz_bridge=False),
    ],
)
def test_validator_rejects_descriptor_mutations(mutate):
    candidate = copy.deepcopy(EXPECTED_DESCRIPTOR)
    mutate(candidate)
    with pytest.raises(probe.ProbeConfigurationError):
        probe.validate_probe_descriptor(candidate)


def test_harmonic_unbracketed_publisher_exact_type_passes(tmp_path):
    topic = "/robot/scan"
    info = (
        b"Publishers [Address, Message Type]:\n"
        b"tcp://127.0.0.1:1234, gz.msgs.LaserScan\n"
        b"Subscribers [Address, Message Type]:\n"
        b"tcp://127.0.0.1:2345, gz.msgs.PointCloudPacked\n"
    )
    result, runner = _result_for(tmp_path, ["/clock", topic], {topic: info})
    assert result["outcome"] == "EXACTLY_ONE_MATCH"
    assert result["observed_endpoints"] == [
        {"message_type": "gz.msgs.LaserScan", "status": "OBSERVED_NOT_PINNED", "topic": topic}
    ]
    assert [call[0] for call in runner.calls] == [
        ["gz", "topic", "-l"], ["gz", "topic", "-i", "-t", topic]
    ]
    assert all(call[1]["shell"] is False for call in runner.calls)


def test_run005_observed_111_byte_harmonic_transcript_replays_as_exact_match(tmp_path):
    topic = "/scan"
    raw_info = (
        b"Publishers [Address, Message Type]:\n"
        b"  tcp://127.0.0.1:44619, gz.msgs.LaserScan\n"
        b"No subscribers on topic [/scan]\n"
    )
    assert len(raw_info) == 111
    result, _ = _result_for(tmp_path, [topic], {topic: raw_info})
    assert result["outcome"] == "EXACTLY_ONE_MATCH"
    assert result["observed_endpoints"] == [
        {
            "message_type": "gz.msgs.LaserScan",
            "status": "OBSERVED_NOT_PINNED",
            "topic": "/scan",
        }
    ]
    assert (tmp_path / "transcripts/command-0002.stdout.bin").read_bytes() == raw_info


def test_non_scan_publisher_has_distinct_fail_closed_outcome(tmp_path):
    topic = "/robot/scan"
    result, _ = _result_for(tmp_path, [topic], {
        topic: b"Publishers [Address, Message Type]:\ntcp://127.0.0.1:1234, gz.msgs.PointCloudPacked\n"
    })
    assert result["outcome"] == "NO_EXPECTED_PUBLISHER_TYPE"
    assert result["observed_endpoints"] == []


def test_multiple_publishers_for_one_candidate_fail_closed(tmp_path):
    topic = "/scan"
    info = (
        b"Publishers [Address, Message Type]:\n"
        b"tcp://127.0.0.1:1234, gz.msgs.LaserScan\n"
        b"tcp://127.0.0.1:2345, gz.msgs.LaserScan\n"
    )
    result, _ = _result_for(tmp_path, [topic], {topic: info})
    assert result["outcome"] == "AMBIGUOUS_PUBLISHERS"
    assert result["observed_endpoints"] == []


def test_subscriber_only_and_mixed_sections_count_publishers_only(tmp_path):
    topic = "/robot/scan"
    subscriber_only = (
        b"Subscribers [Address, Message Type]:\n"
        b"tcp://127.0.0.1:2345, gz.msgs.LaserScan\n"
    )
    result, _ = _result_for(tmp_path, [topic], {topic: subscriber_only})
    assert result["outcome"] == "NO_PUBLISHER_MATCH"
    assert result["observed_endpoints"] == []

    mixed = (
        b"Publishers [Address, Message Type]:\n"
        b"tcp://127.0.0.1:1234, gz.msgs.PointCloudPacked\n"
        b"Subscribers [Address, Message Type]:\n"
        b"tcp://127.0.0.1:2345, gz.msgs.LaserScan\n"
    )
    result, _ = _result_for(tmp_path, [topic], {topic: mixed})
    assert result["outcome"] == "NO_EXPECTED_PUBLISHER_TYPE"
    assert result["observed_endpoints"] == []


def test_bracketed_address_and_malformed_publisher_are_rejected(tmp_path):
    topic = "/robot/scan"
    bracketed = b"Publishers [Address, Message Type]:\n<tcp://127.0.0.1:1234>, gz.msgs.LaserScan\n"
    result, _ = _result_for(tmp_path, [topic], {topic: bracketed})
    assert result["outcome"] == "TOPIC_INFO_UNRECOGNIZED"
    assert result["observed_endpoints"] == []
    malformed = b"Publishers [Address, Message Type]:\ntcp://, gz.msgs.LaserScan\n"
    result, _ = _result_for(tmp_path, [topic], {topic: malformed})
    assert result["outcome"] == "TOPIC_INFO_UNRECOGNIZED"
    result, _ = _result_for(tmp_path, [topic], {topic: b"Type: gz.msgs.LaserScan\n"})
    assert result["outcome"] == "TOPIC_INFO_UNRECOGNIZED"


def test_zero_one_and_multiple_scan_publisher_matches(tmp_path):
    a, b = "/a/scan", "/b/scan"
    info = lambda _topic: b"Publishers [Address, Message Type]:\ntcp://127.0.0.1:1234, gz.msgs.LaserScan\n"
    result, _ = _result_for(tmp_path, ["/clock", "/not_scan"], {})
    assert result["outcome"] == "NO_CANDIDATE_TOPIC"
    result, _ = _result_for(tmp_path, [a, b], {a: info(a), b: info(b)})
    assert result["outcome"] == "AMBIGUOUS_PUBLISHER_MATCHES"
    assert [item["topic"] for item in result["observed_endpoints"]] == [a, b]


def test_malformed_listing_or_candidate_info_fails_closed(tmp_path):
    result, _ = _result_for(tmp_path, ["relative/scan"], {})
    assert result["outcome"] == "TOPIC_INFO_UNRECOGNIZED"
    result, _ = _result_for(tmp_path, ["/robot/scan"], {"/robot/scan": b"unexpected data gz.msgs.LaserScan\n"})
    assert result["outcome"] == "TOPIC_INFO_UNRECOGNIZED"
    result, _ = _result_for(tmp_path, ["/robot/scan"], {
        "/robot/scan": b"Publishers [Address, Message Type]:\nmalformed publisher\n"
    })
    assert result["outcome"] == "TOPIC_INFO_UNRECOGNIZED"


def test_discovery_candidate_and_transcript_limits_fail_closed(tmp_path):
    result, runner = _result_for(tmp_path, [f"/x/{i}/scan" for i in range(17)])
    assert result["outcome"] == "TOO_MANY_CANDIDATE_TOPICS"
    assert len(runner.calls) == 1

    huge = b"x" * (probe.COMMAND_CONTRACT["maximum_transcript_bytes_per_stream"] + 1)
    runner = lambda argv, **kwargs: subprocess.CompletedProcess(argv, 0, huge, b"")
    result = probe.probe_scan_endpoint(command_runner=runner, transcript_directory=_make_transcript_dir(tmp_path))
    assert result["outcome"] == "TRANSCRIPT_LIMIT_EXCEEDED"
    obs = result["command_observations"][0]
    raw_path = _make_transcript_dir(tmp_path) / Path(obs["stdout_path"]).name
    assert obs["stdout_size_bytes"] == len(huge)
    assert obs["stdout_sha256"] == hashlib.sha256(huge).hexdigest()
    assert obs["transcript_limit_exceeded"] is True
    assert raw_path.read_bytes() == huge


def test_transcript_hash_size_and_relative_path_are_exact(tmp_path):
    topic = "/robot/scan"
    raw_out = b"Publishers [Address, Message Type]:\ntcp://127.0.0.1:1234, gz.msgs.LaserScan\n"
    result, _ = _result_for(tmp_path, [topic], {topic: raw_out})
    observations = result["command_observations"]
    assert len(observations) == 2
    for index, observation in enumerate(observations, 1):
        assert observation["argv"] == (["gz", "topic", "-l"] if index == 1 else ["gz", "topic", "-i", "-t", topic])
        assert observation["timeout"] is False
        assert observation["transcript_path"] == f"transcripts/command-{index:04d}"
        stdout = (tmp_path / observation["stdout_path"]).read_bytes()
        stderr = (tmp_path / observation["stderr_path"]).read_bytes()
        assert hashlib.sha256(stdout).hexdigest() == observation["stdout_sha256"]
        assert len(stdout) == observation["stdout_size_bytes"]
        assert hashlib.sha256(stderr).hexdigest() == observation["stderr_sha256"]
        assert len(stderr) == observation["stderr_size_bytes"]


def test_command_failures_timeout_and_invalid_descriptor(tmp_path):
    def missing(argv, **kwargs):
        raise FileNotFoundError("gz missing")

    result = probe.probe_scan_endpoint(command_runner=missing, transcript_directory=_make_transcript_dir(tmp_path))
    assert result["outcome"] == "GZ_COMMAND_NOT_FOUND"

    def timeout(argv, **kwargs):
        raise subprocess.TimeoutExpired(argv, kwargs["timeout"], output=b"partial", stderr=b"err")

    result = probe.probe_scan_endpoint(command_runner=timeout, transcript_directory=_make_transcript_dir(tmp_path))
    assert result["outcome"] == "GZ_COMMAND_TIMEOUT"
    assert result["command_observations"][0]["timeout"] is True

    failed = FakeRunner([], discovery_returncode=2)
    result = probe.probe_scan_endpoint(command_runner=failed, transcript_directory=_make_transcript_dir(tmp_path))
    assert result["outcome"] == "GZ_COMMAND_FAILED"

    invalid = copy.deepcopy(EXPECTED_DESCRIPTOR)
    invalid["runtime_eligible"] = True
    no_call = FakeRunner([])
    result = probe.probe_scan_endpoint(invalid, command_runner=no_call, transcript_directory=_make_transcript_dir(tmp_path))
    assert result["outcome"] == "INVALID_PROBE_CONFIGURATION"
    assert no_call.calls == []


def test_import_is_inert_and_source_has_no_runtime_bridge_or_shell_escape_hatch():
    module_path = PACKAGE_ROOT / "mecanum_nav_bringup/sim_eval_scan_endpoint_probe.py"
    spec = importlib.util.spec_from_file_location("_probe_import_inert_check", module_path)
    isolated = importlib.util.module_from_spec(spec)
    with patch.object(subprocess, "run") as run:
        spec.loader.exec_module(isolated)
        run.assert_not_called()
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    forbidden_imports = {"rclpy", "launch", "launch_ros", "tf2_ros", "ros_gz_bridge", "ros_gz_sim", "gz", "gazebo", "sensor_msgs", "nav_msgs", "ros2", "socket"}
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add((node.module or "").split(".")[0])
        if isinstance(node, ast.Name):
            assert node.id != "Popen"
    assert imported.isdisjoint(forbidden_imports)
    source = module_path.read_text(encoding="utf-8")
    assert "gz topic -e" not in source
    assert "ros2 topic" not in source
    assert "shell=True" not in source
    assert source.count("subprocess.run") == 1


def test_clock_bridge_and_wp05_static_profile_provenance_remain_consistent():
    clock_path = REPO_ROOT / "ros2_ws/src/ROBOT_URDF_final_description/config/ros_gz_bridge_gazebo.yaml"
    clock = yaml.safe_load(clock_path.read_text(encoding="utf-8"))
    assert clock == [{
        "ros_topic_name": "/clock", "gz_topic_name": "/clock",
        "ros_type_name": "rosgraph_msgs/msg/Clock", "gz_type_name": "gz.msgs.Clock",
        "direction": "GZ_TO_ROS",
    }]
    assert _sha256(PACKAGE_ROOT / "config/bridge/sim_eval_lidar_scan_bridge.static.yaml") == "60a012fd2fd8f743658cdfb4fc3e910d728b17b2bea5d7dece3316bd4f12ff7e"

    gazebo_source_path = "ros2_ws/src/ROBOT_URDF_final_description/urdf/ROBOT_URDF_final.gazebo"
    gazebo_source = REPO_ROOT / gazebo_source_path
    source_sha256 = _sha256(gazebo_source)
    expected = {
        "role": "gazebo_lidar_source",
        "path": gazebo_source_path,
        "classification": "GAZEBO_TRANSPORT_PROVENANCE_ONLY",
        "sha256": source_sha256,
    }

    profile = yaml.safe_load(
        (PACKAGE_ROOT / "config/profiles/sim_eval_nav2_baseline.static.yaml").read_text(encoding="utf-8")
    )
    profile_entries = [
        item for item in profile["static_ingress_contracts"]
        if item.get("role") == "gazebo_lidar_source"
    ]
    assert profile_entries == [expected]

    manifest_path = REPO_ROOT / "docs/governance/evidence/WP-05_SIM_EVAL_NAV2_BASELINE_STATIC_PROFILE_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest_entries = [
        item for item in manifest["static_ingress_contracts"]
        if item.get("role") == "gazebo_lidar_source"
    ]
    assert manifest_entries == [expected]

    python_entries = [
        item for item in STATIC_PROFILE_DESCRIPTOR["static_ingress_contracts"]
        if item.get("role") == "gazebo_lidar_source"
    ]
    assert python_entries == [expected]
