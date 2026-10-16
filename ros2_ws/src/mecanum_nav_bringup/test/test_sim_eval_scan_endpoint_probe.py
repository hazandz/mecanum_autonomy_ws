"""Offline contract tests; no Gazebo/ROS command is executed."""

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


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PACKAGE_ROOT.parents[2]
YAML_PATH = PACKAGE_ROOT / "config/bridge/sim_eval_scan_endpoint_probe.static.yaml"
EXPECTED_DESCRIPTOR = {
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
        "selection_rule": "EXACTLY_ONE_EXPECTED_GZ_MESSAGE_TYPE",
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


UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _unique_yaml_mapping
)


def _sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class FakeRunner:
    def __init__(self, topics, type_by_topic=None, *, discovery_returncode=0, inspect_returncode=0):
        self.topics = topics
        self.type_by_topic = type_by_topic or {}
        self.discovery_returncode = discovery_returncode
        self.inspect_returncode = inspect_returncode
        self.calls = []

    def __call__(self, command, **kwargs):
        self.calls.append((command, kwargs))
        assert kwargs["shell"] is False
        assert kwargs["capture_output"] is True
        assert kwargs["text"] is True
        assert kwargs["timeout"] == 5.0
        assert kwargs["check"] is False
        if command == ["gz", "topic", "-l"]:
            return subprocess.CompletedProcess(command, self.discovery_returncode, "\n".join(self.topics), "")
        assert command[:4] == ["gz", "topic", "-i", "-t"]
        topic = command[4]
        token = self.type_by_topic.get(topic)
        output = f"Publishers: 1\nType: {token}\n" if token is not None else "No type details\n"
        return subprocess.CompletedProcess(command, self.inspect_returncode, output, "")


def _result_for(topics, type_by_topic=None):
    runner = FakeRunner(topics, type_by_topic)
    result = probe.probe_scan_endpoint(command_runner=runner)
    return result, runner


def test_yaml_and_python_descriptor_are_exact_and_registered():
    raw = YAML_PATH.read_bytes()
    assert raw.decode("utf-8").encode("utf-8") == raw
    assert not raw.startswith(b"\xef\xbb\xbf")
    descriptor = yaml.load(raw.decode("utf-8"), Loader=UniqueKeyLoader)
    assert descriptor == EXPECTED_DESCRIPTOR == probe.STATIC_DESCRIPTOR
    assert probe.validate_probe_descriptor(descriptor) is True
    setup = (PACKAGE_ROOT / "setup.py").read_text(encoding="utf-8")
    assert '"config/bridge/sim_eval_scan_endpoint_probe.static.yaml"' in setup
    assert "sim_eval_scan_endpoint_probe = mecanum_nav_bringup.sim_eval_scan_endpoint_probe:main" in setup


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d.update(schema="other/v1"),
        lambda d: d.update(profile="other"),
        lambda d: d["sensor_provenance"].update(expected_gz_message_type="gz.msgs.Other"),
        lambda d: d["future_ros_boundary"].update(direction="ROS_TO_GZ"),
        lambda d: d["command_contract"].update(timeout_seconds=10.0),
        lambda d: d["command_contract"].update(maximum_topics=513),
        lambda d: d["prohibitions"].update(no_ros_gz_bridge=False),
    ],
)
def test_validator_rejects_descriptor_mutations(mutate):
    candidate = copy.deepcopy(EXPECTED_DESCRIPTOR)
    mutate(candidate)
    with pytest.raises(probe.ProbeConfigurationError):
        probe.validate_probe_descriptor(candidate)


def test_one_exact_type_match_is_observed_but_not_pinned():
    topic = "/world/warehouse/model/robot/sensor/laser/link/lidar_frame/scan"
    result, runner = _result_for([topic], {topic: "gz.msgs.LaserScan"})
    assert result == {
        "outcome": "EXACTLY_ONE_MATCH",
        "observed_endpoints": [
            {"message_type": "gz.msgs.LaserScan", "status": "OBSERVED_NOT_PINNED", "topic": topic}
        ],
    }
    assert [call[0] for call in runner.calls] == [
        ["gz", "topic", "-l"], ["gz", "topic", "-i", "-t", topic]
    ]
    encoded = probe.canonical_json(result)
    assert encoded == json.dumps(result, sort_keys=True, separators=(",", ":"))
    assert result["observed_endpoints"][0]["status"] == "OBSERVED_NOT_PINNED"
    assert "endpoint_pin" not in encoded


def test_zero_match_and_no_topic_name_inference():
    result, _ = _result_for(["/scan"], {"/scan": "gz.msgs.PointCloudPacked"})
    assert result["outcome"] == "NO_MATCH"
    assert result["observed_endpoints"] == []

    unrelated = "/world/x/sensor/renamed/output"
    result, _ = _result_for([unrelated], {unrelated: "gz.msgs.LaserScan"})
    assert result["outcome"] == "EXACTLY_ONE_MATCH"
    assert result["observed_endpoints"][0]["topic"] == unrelated


def test_ambiguous_matches_inspect_every_discovered_topic():
    topics = ["/a/laser", "/b/other", "/c/scan"]
    result, runner = _result_for(topics, {topic: "gz.msgs.LaserScan" for topic in topics})
    assert result["outcome"] == "AMBIGUOUS_MATCHES"
    assert [item["topic"] for item in result["observed_endpoints"]] == topics
    assert len(runner.calls) == 1 + len(topics)


def test_unknown_info_malformed_topic_failure_and_timeout_fail_closed():
    result, _ = _result_for(["/topic"], {})
    assert result["outcome"] == "UNRECOGNIZED_TOPIC_INFO"
    malformed, _ = _result_for(["relative/topic"], {})
    assert malformed["outcome"] == "UNRECOGNIZED_TOPIC_INFO"

    failed_runner = FakeRunner([], discovery_returncode=2)
    assert probe.probe_scan_endpoint(command_runner=failed_runner)["outcome"] == "GZ_COMMAND_FAILED"

    def missing(command, **kwargs):
        raise FileNotFoundError("gz not found")

    assert probe.probe_scan_endpoint(command_runner=missing)["outcome"] == "GZ_COMMAND_NOT_FOUND"

    def timeout(command, **kwargs):
        raise subprocess.TimeoutExpired(command, kwargs["timeout"])

    assert probe.probe_scan_endpoint(command_runner=timeout)["outcome"] == "GZ_COMMAND_TIMEOUT"


def test_topic_limit_and_invalid_configuration_do_not_inspect_or_execute():
    runner = FakeRunner([f"/topic_{i}" for i in range(513)])
    assert probe.probe_scan_endpoint(command_runner=runner)["outcome"] == "TOO_MANY_TOPICS"
    assert len(runner.calls) == 1

    invalid = copy.deepcopy(EXPECTED_DESCRIPTOR)
    invalid["runtime_eligible"] = True
    runner = FakeRunner([])
    result = probe.probe_scan_endpoint(invalid, command_runner=runner)
    assert result["outcome"] == "INVALID_PROBE_CONFIGURATION"
    assert runner.calls == []


def test_import_is_inert_and_source_has_no_runtime_or_shell_escape_hatch():
    module_path = PACKAGE_ROOT / "mecanum_nav_bringup/sim_eval_scan_endpoint_probe.py"
    spec = importlib.util.spec_from_file_location("_probe_import_inert_check", module_path)
    isolated = importlib.util.module_from_spec(spec)
    with patch.object(subprocess, "run") as run:
        spec.loader.exec_module(isolated)
        run.assert_not_called()

    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    forbidden_imports = {
        "rclpy", "launch", "launch_ros", "tf2_ros", "ros_gz_bridge", "ros_gz_sim",
        "gz", "gazebo", "sensor_msgs", "nav_msgs", "ros2",
    }
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
    assert "shell=True" not in source
    assert "socket" not in imported


def test_clock_bridge_and_reconciled_wp05_sources_are_unchanged():
    clock_path = REPO_ROOT / "ros2_ws/src/ROBOT_URDF_final_description/config/ros_gz_bridge_gazebo.yaml"
    clock = yaml.safe_load(clock_path.read_text(encoding="utf-8"))
    assert clock == [
        {
            "ros_topic_name": "/clock",
            "gz_topic_name": "/clock",
            "ros_type_name": "rosgraph_msgs/msg/Clock",
            "gz_type_name": "gz.msgs.Clock",
            "direction": "GZ_TO_ROS",
        }
    ]
    assert _sha256(REPO_ROOT / "ros2_ws/src/ROBOT_URDF_final_description/urdf/ROBOT_URDF_final.gazebo") == "1e97b6ea340adc9aecaf320cc432007c6bb37f5922cdc0366dbee50a9a26ff0e"
    assert _sha256(REPO_ROOT / "ros2_ws/src/mecanum_nav_bringup/config/bridge/sim_eval_lidar_scan_bridge.static.yaml") == "60a012fd2fd8f743658cdfb4fc3e910d728b17b2bea5d7dece3316bd4f12ff7e"
    assert _sha256(REPO_ROOT / "ros2_ws/src/mecanum_nav_bringup/config/profiles/sim_eval_nav2_baseline.static.yaml") == "55da76d604e8c4464ccf32d6475d62f2b928c2aabeee9c1ffcb6aaf26dd4eb0b"
    assert _sha256(REPO_ROOT / "ros2_ws/src/mecanum_nav_bringup/mecanum_nav_bringup/sim_eval_static_profile_contract.py") == "d557c1a1d1ff7b7a7131145f680c6e537dc2fa5ade5cd6b40fcfc17c2d34e039"
    assert _sha256(REPO_ROOT / "docs/governance/evidence/WP-05_SIM_EVAL_NAV2_BASELINE_STATIC_PROFILE_MANIFEST.json") == "1a9c0504cdb4c18aa4620174f52d9cdf53a6203b8b189452db50bb3c8cfe2a90"
