from copy import deepcopy
import ast
import importlib
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest
import yaml

from mecanum_nav_bringup import sim_eval_scan_endpoint_probe as probe


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = PACKAGE_ROOT.parents[2]
CONFIG_PATH = PACKAGE_ROOT / "config/bridge/sim_eval_scan_endpoint_probe.static.yaml"
EXPECTED_TYPE = "gz.msgs.LaserScan"


class UniqueSafeLoader(yaml.SafeLoader):
    pass


def _construct_unique_mapping(loader, node, deep=False):
    loader.flatten_mapping(node)
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in result:
            raise ValueError(f"duplicate YAML key: {key}")
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


UniqueSafeLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_unique_mapping)


class FakeRunner:
    def __init__(self, discovery, topic_info=None, error=None):
        self.discovery = discovery
        self.topic_info = topic_info or {}
        self.error = error
        self.calls = []

    def __call__(self, arguments, **kwargs):
        self.calls.append((arguments, kwargs))
        if self.error is not None:
            raise self.error
        if arguments == ["gz", "topic", "-l"]:
            return self.discovery
        if arguments[:3] == ["gz", "topic", "-i"]:
            return self.topic_info[arguments[-1]]
        raise AssertionError(f"unexpected command vector: {arguments!r}")


def completed(stdout="", returncode=0):
    return SimpleNamespace(stdout=stdout, stderr="", returncode=returncode)


def run_probe(topics, infos=None, **kwargs):
    runner = FakeRunner(completed("\n".join(topics)), infos, **kwargs)
    return probe.probe_endpoint(probe.STATIC_DESCRIPTOR, runner), runner


def test_yaml_is_exact_static_descriptor_and_validator_accepts_it():
    raw = CONFIG_PATH.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf")
    descriptor = yaml.load(raw.decode("utf-8"), Loader=UniqueSafeLoader)
    assert descriptor == probe.STATIC_DESCRIPTOR
    assert probe.validate_probe_configuration(descriptor) is None
    assert descriptor["runtime_eligible"] is False


@pytest.mark.parametrize(
    "path,value",
    [
        (("schema",), "wrong/v1"),
        (("profile",), "other"),
        (("sensor_provenance", "expected_gz_message_type"), "gz.msgs.Other"),
        (("expected_future_ros_boundary", "direction"), "ROS_TO_GZ"),
        (("command_contract", "default_timeout_seconds"), 6.0),
        (("command_contract", "maximum_discovered_topics"), 513),
        (("prohibitions", "no_endpoint_pin"), False),
        (("prohibitions", "forbidden_ros_components"), ["publisher"]),
    ],
)
def test_validator_rejects_contract_mutations(path, value):
    descriptor = deepcopy(probe.STATIC_DESCRIPTOR)
    target = descriptor
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(probe.InvalidProbeConfiguration):
        probe.validate_probe_configuration(descriptor)


def test_validator_rejects_missing_and_extra_keys():
    missing = deepcopy(probe.STATIC_DESCRIPTOR)
    del missing["sensor_provenance"]["declared_relative_topic"]
    extra = deepcopy(probe.STATIC_DESCRIPTOR)
    extra["runtime_endpoint"] = "/world/default/scan"
    for descriptor in (missing, extra):
        with pytest.raises(probe.InvalidProbeConfiguration):
            probe.validate_probe_configuration(descriptor)


def test_probe_rejects_invalid_configuration_without_invoking_runner():
    calls = []
    descriptor = deepcopy(probe.STATIC_DESCRIPTOR)
    descriptor["runtime_eligible"] = True
    result = probe.probe_endpoint(descriptor, command_runner=lambda *a, **k: calls.append((a, k)))
    assert result.outcome == "INVALID_PROBE_CONFIGURATION"
    assert calls == []


def test_exactly_one_inspected_type_is_observed_without_endpoint_inference():
    topic = "/world/room/model/robot/link/lidar_frame/sensor/YDLIDAR_X3_PRO/scan"
    result, runner = run_probe([topic], {topic: completed("Publishers [1]:\n  1: gz.msgs.LaserScan\n")})
    assert result.outcome == "EXACTLY_ONE_MATCH"
    assert result.observed_endpoints == (topic,)
    assert result.as_dict() == {
        "endpoint_status": "OBSERVED_NOT_PINNED",
        "observed_endpoints": [topic],
        "outcome": "EXACTLY_ONE_MATCH",
    }
    assert runner.calls[0][0] == ["gz", "topic", "-l"]
    assert runner.calls[1][0] == ["gz", "topic", "-i", "-t", topic]
    assert all(call[1]["shell"] is False and call[1]["timeout"] == 5.0 for call in runner.calls)


def test_no_topics_returns_no_match():
    result, runner = run_probe([])
    assert result.outcome == "NO_MATCH"
    assert runner.calls == [(["gz", "topic", "-l"], runner.calls[0][1])]


def test_multiple_exact_types_are_ambiguous():
    topics = ["/sim/a", "/unrelated/name"]
    infos = {topic: completed("Type: gz.msgs.LaserScan\n") for topic in topics}
    result, _ = run_probe(topics, infos)
    assert result.outcome == "AMBIGUOUS_MATCHES"
    assert result.observed_endpoints == tuple(topics)


def test_other_type_is_not_selected_and_relative_sensor_topic_is_not_inferred():
    topic = "/scan"
    result, _ = run_probe([topic], {topic: completed("Type: gz.msgs.Image\n")})
    assert result.outcome == "NO_MATCH"
    assert probe._valid_absolute_topic("scan") is False


def test_unrecognized_topic_info_fails_closed():
    topic = "/topic"
    result, _ = run_probe([topic], {topic: completed("Publisher details unavailable\n")})
    assert result.outcome == "UNRECOGNIZED_TOPIC_INFO"


@pytest.mark.parametrize(
    "error,outcome",
    [
        (FileNotFoundError(), "GZ_COMMAND_NOT_FOUND"),
        (subprocess.TimeoutExpired(["gz"], 5.0), "GZ_COMMAND_TIMEOUT"),
        (OSError("failed"), "GZ_COMMAND_FAILED"),
    ],
)
def test_command_errors_are_fail_closed(error, outcome):
    result = probe.probe_endpoint(command_runner=FakeRunner(completed(), error=error))
    assert result.outcome == outcome


def test_nonzero_exit_is_command_failure():
    result = probe.probe_endpoint(command_runner=FakeRunner(completed(returncode=1)))
    assert result.outcome == "GZ_COMMAND_FAILED"


@pytest.mark.parametrize("topic", ["relative/topic", "/bad//topic", "/bad/../topic", "/bad topic"])
def test_malformed_or_nonabsolute_discovered_topic_is_rejected(topic):
    result, runner = run_probe([topic])
    assert result.outcome == "UNRECOGNIZED_TOPIC_INFO"
    assert len(runner.calls) == 1


def test_discovery_limit_accepts_512_and_rejects_513_without_inspection():
    topics = [f"/topic_{index}" for index in range(513)]
    too_many, runner = run_probe(topics)
    assert too_many.outcome == "TOO_MANY_TOPICS"
    assert len(runner.calls) == 1

    exactly_limit = topics[:512]
    infos = {topic: completed("Type: gz.msgs.Image\n") for topic in exactly_limit}
    result, runner = run_probe(exactly_limit, infos)
    assert result.outcome == "NO_MATCH"
    assert len(runner.calls) == 513


def test_import_is_inert_and_module_has_no_forbidden_runtime_boundary():
    calls = []
    original = probe.subprocess.run
    probe.subprocess.run = lambda *args, **kwargs: calls.append((args, kwargs))
    try:
        importlib.reload(probe)
    finally:
        probe.subprocess.run = original
    assert calls == []

    module_path = PACKAGE_ROOT / "mecanum_nav_bringup/sim_eval_scan_endpoint_probe.py"
    test_path = Path(__file__)
    for path in (module_path, test_path):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imported = set()
        attributes = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.add(node.module or "")
            elif isinstance(node, ast.Attribute):
                attributes.add(node.attr)
            forbidden = {"rclpy", "ros2", "launch_ros", "tf2_ros", "ros_gz_bridge", "gazebo", "gz"}
            assert not any(item.split(".")[0] in forbidden for item in imported)
            assert not attributes.intersection({"Popen", "socket", "create_publisher", "create_subscription"})
            assert not any(
                isinstance(node, ast.keyword)
                and node.arg == "shell"
                and isinstance(node.value, ast.Constant)
                and node.value.value is True
                for node in ast.walk(tree)
            )
        if path == module_path:
            command_vectors = [
                [node.value for node in item.elts]
                for item in ast.walk(tree)
                if isinstance(item, ast.List)
                and all(isinstance(node, ast.Constant) for node in item.elts)
            ]
            assert ["gz", "topic", "-e"] not in command_vectors
            assert not any(
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "subprocess"
                and node.func.attr == "run"
                for node in ast.walk(tree)
            )  # _run invokes the injected runner; import remains inert.


def test_legacy_bridge_is_clock_only_and_existing_static_sensor_boundary_is_unchanged():
    legacy = (REPOSITORY_ROOT / "ros2_ws/src/ROBOT_URDF_final_description/config/ros_gz_bridge_gazebo.yaml").read_text(encoding="utf-8")
    assert "gz.msgs.Clock" in legacy
    assert "LaserScan" not in legacy

    static_contract = (PACKAGE_ROOT / "config/bridge/sim_eval_lidar_scan_bridge.static.yaml").read_text(encoding="utf-8")
    assert "gz_transport_endpoint: PENDING_GZ_LIDAR_TRANSPORT_ENDPOINT_PIN" in static_contract
    assert "bridge_implementation: PENDING_PROFILE_SPECIFIC_ROS_GZ_BRIDGE_SOURCE_PIN" in static_contract
    assert "relative_sensor_topic_is_not_full_transport_endpoint" in static_contract

    gazebo = (REPOSITORY_ROOT / "ros2_ws/src/ROBOT_URDF_final_description/urdf/ROBOT_URDF_final.gazebo").read_text(encoding="utf-8")
    assert '<gazebo reference="lidar_frame">' in gazebo
    assert '<sensor name="YDLIDAR_X3_PRO" type="gpu_lidar">' in gazebo
    assert "<topic>scan</topic>" in gazebo


def test_setup_registers_only_owned_yaml_and_probe_console_script():
    setup = (PACKAGE_ROOT / "setup.py").read_text(encoding="utf-8")
    assert '"config/bridge/sim_eval_scan_endpoint_probe.static.yaml"' in setup
    assert "sim_eval_scan_endpoint_probe = mecanum_nav_bringup.sim_eval_scan_endpoint_probe:main" in setup


def test_cli_json_is_canonical_and_unique_match_is_the_only_zero_exit(monkeypatch, capsys):
    topic = "/observed/topic"
    calls = iter([completed(topic), completed("Type: gz.msgs.LaserScan\n")])
    monkeypatch.setattr(probe.subprocess, "run", lambda *args, **kwargs: next(calls))
    assert probe.main([]) == 0
    output = capsys.readouterr().out
    assert output.endswith("\n")
    encoded = output[:-1].encode("utf-8")
    decoded = json.loads(encoded.decode("utf-8"))
    assert decoded == {
        "endpoint_status": "OBSERVED_NOT_PINNED",
        "observed_endpoints": [topic],
        "outcome": "EXACTLY_ONE_MATCH",
    }
    assert output[:-1] == json.dumps(decoded, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    monkeypatch.setattr(probe.subprocess, "run", lambda *args, **kwargs: completed(""))
    assert probe.main([]) != 0
    capsys.readouterr()
