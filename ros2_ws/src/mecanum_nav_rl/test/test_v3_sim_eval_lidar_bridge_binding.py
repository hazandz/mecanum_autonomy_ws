"""Offline checks for the WP04/WP08 typed static scan-binding seam."""

import ast
from copy import deepcopy
from pathlib import Path
import math
import sys
from types import ModuleType

import pytest
import yaml

# The observations package initializer eagerly imports unrelated Pydantic-backed
# modules. Install a test-only package namespace so this isolated pure seam can
# import only its three standard-library-based modules without loading those
# unrelated package exports.
PACKAGE_ROOT = Path(__file__).resolve().parents[1]
OBSERVATIONS_PACKAGE = PACKAGE_ROOT / "mecanum_nav_rl/observations"
if "mecanum_nav_rl.observations" not in sys.modules:
    observations_namespace = ModuleType("mecanum_nav_rl.observations")
    observations_namespace.__path__ = [str(OBSERVATIONS_PACKAGE)]
    sys.modules["mecanum_nav_rl.observations"] = observations_namespace

from mecanum_nav_rl.observations.v3_ingress_binding_types import IngressMessageBinding
from mecanum_nav_rl.observations.v3_sim_eval_lidar_bridge_binding import (
    adapt_sim_eval_lidar_from_static_bridge_claim,
    build_sim_eval_lidar_binding_from_static_bridge_claim,
)
from mecanum_nav_rl.observations.v3_snapshot_types import (
    ActiveLifecycleConfigContext,
    LidarSnapshot,
)


REPO_ROOT = PACKAGE_ROOT.parents[2]
WP08_YAML = (
    REPO_ROOT
    / "ros2_ws/src/mecanum_nav_bringup/config/bridge/sim_eval_lidar_scan_bridge.static.yaml"
)
MODULE_PATH = (
    PACKAGE_ROOT
    / "mecanum_nav_rl/observations/v3_sim_eval_lidar_bridge_binding.py"
)


class FakeHeader:
    def __init__(self, frame_id="lidar_frame"):
        self.frame_id = frame_id


class FakeScan:
    def __init__(self, frame_id="lidar_frame"):
        self.header = FakeHeader(frame_id)


def _wp08_claim():
    return yaml.safe_load(WP08_YAML.read_text(encoding="utf-8"))


def _context():
    return ActiveLifecycleConfigContext(
        contract_id="test-active-context/v1",
        episode_generation=17,
        reset_epoch=23,
        runtime_generation=41,
        config_hash="a" * 64,
    )


def _mutate(claim, section, field, value):
    result = deepcopy(claim)
    result[section][field] = value
    return result


def test_wp08_yaml_to_binding_to_existing_adapter_yields_typed_snapshot():
    claim = _wp08_claim()
    context = _context()
    converter_calls = []

    def converter(message):
        converter_calls.append(message)
        return tuple(float(index) for index in range(72))

    binding = build_sim_eval_lidar_binding_from_static_bridge_claim(
        claim, expected_message_class=FakeScan, converter=converter
    )
    assert type(binding) is IngressMessageBinding
    assert binding.expected_topic == "/scan"
    assert binding.expected_type == "sensor_msgs/msg/LaserScan"
    assert binding.expected_frame_id == "lidar_frame"
    assert binding.expected_child_frame_id is None
    assert converter_calls == []  # Binding creation must not call the converter.

    message = FakeScan()
    snapshot = adapt_sim_eval_lidar_from_static_bridge_claim(
        message,
        claim,
        expected_message_class=FakeScan,
        converter=converter,
        context=context,
    )
    assert type(snapshot) is LidarSnapshot
    assert len(snapshot.sectors) == 72
    assert all(type(value) is float and math.isfinite(value) for value in snapshot.sectors)
    assert snapshot.topic_claim == "/scan"
    assert snapshot.type_claim == "sensor_msgs/msg/LaserScan"
    assert snapshot.frame_id == "lidar_frame"
    assert (
        snapshot.episode_generation,
        snapshot.reset_epoch,
        snapshot.runtime_generation,
        snapshot.config_hash,
    ) == (
        context.episode_generation,
        context.reset_epoch,
        context.runtime_generation,
        context.config_hash,
    )
    assert converter_calls == [message]


@pytest.mark.parametrize(
    ("section", "field", "value"),
    [
        ("ros_output", "topic", "/other_scan"),
        ("ros_output", "ros_message_type", "sensor_msgs/msg/Imu"),
        ("ros_output", "required_header_frame_id", "base_link"),
        ("ros_output", "publishes_tf", True),
        ("tf_contract", "base_to_lidar_owner", "static_transform_publisher"),
        ("tf_contract", "required_static_edge", "base_link -> base_scan"),
        ("tf_contract", "bridge_publishes_tf", True),
        (
            "transport_binding",
            "gz_transport_endpoint",
            "/world/default/model/robot/link/lidar_frame/sensor/scan/scan",
        ),
        (
            "transport_binding",
            "bridge_implementation",
            "ros_gz_bridge parameter_bridge",
        ),
        ("transport_binding", "observed_scan_timing", 6.0),
    ],
)
def test_public_boundary_mismatches_fail_closed(section, field, value):
    claim = _mutate(_wp08_claim(), section, field, value)
    assert build_sim_eval_lidar_binding_from_static_bridge_claim(
        claim, expected_message_class=FakeScan, converter=lambda _message: ()
    ) is None


def test_runtime_eligible_true_fails_closed():
    claim = _wp08_claim()
    claim["runtime_eligible"] = True
    assert build_sim_eval_lidar_binding_from_static_bridge_claim(
        claim, expected_message_class=FakeScan, converter=lambda _message: ()
    ) is None


@pytest.mark.parametrize(
    ("expected_message_class", "converter"),
    [
        (FakeScan(), lambda _message: ()),
        (FakeScan, None),
        (FakeScan, object()),
    ],
)
def test_wrong_injected_class_or_converter_fails_closed(expected_message_class, converter):
    assert build_sim_eval_lidar_binding_from_static_bridge_claim(
        _wp08_claim(),
        expected_message_class=expected_message_class,
        converter=converter,
    ) is None


def test_adapter_rejections_and_bad_context_fail_closed():
    claim = _wp08_claim()
    converter = lambda _message: tuple(0.5 for _ in range(72))
    assert adapt_sim_eval_lidar_from_static_bridge_claim(
        FakeScan("base_scan"),
        claim,
        expected_message_class=FakeScan,
        converter=converter,
        context=_context(),
    ) is None
    assert adapt_sim_eval_lidar_from_static_bridge_claim(
        FakeScan(),
        claim,
        expected_message_class=str,
        converter=converter,
        context=_context(),
    ) is None
    assert adapt_sim_eval_lidar_from_static_bridge_claim(
        FakeScan(),
        claim,
        expected_message_class=FakeScan,
        converter=lambda _message: tuple(0.5 for _ in range(71)),
        context=_context(),
    ) is None
    assert adapt_sim_eval_lidar_from_static_bridge_claim(
        FakeScan(),
        claim,
        expected_message_class=FakeScan,
        converter=lambda _message: tuple(float("inf") for _ in range(72)),
        context=_context(),
    ) is None
    assert adapt_sim_eval_lidar_from_static_bridge_claim(
        FakeScan(),
        claim,
        expected_message_class=FakeScan,
        converter=converter,
        context=object(),
    ) is None


def test_sensor_provenance_is_not_relocked_by_candidate_c():
    claim = _wp08_claim()
    claim["gazebo_sensor"]["sensor_name"] = "unexamined-provenance-field"
    assert build_sim_eval_lidar_binding_from_static_bridge_claim(
        claim, expected_message_class=FakeScan, converter=lambda _message: ()
    ) is not None


def test_module_and_test_have_no_runtime_imports_or_graph_execution_symbols():
    forbidden_imports = {
        "rclpy", "launch", "launch_ros", "tf2_ros", "sensor_msgs", "nav_msgs",
        "ros_gz_bridge", "ros_gz_sim", "gz", "gazebo", "mecanum_nav_bringup",
    }
    forbidden_symbols = {
        "Node", "Publisher", "Subscriber", "Timer", "TransformBroadcaster",
        "LaunchDescription", "subprocess", "Popen", "socket", "create_publisher",
        "create_subscription", "create_timer", "send", "urlopen",
    }
    for path in (MODULE_PATH, Path(__file__)):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = {alias.name.split(".", 1)[0] for alias in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = {node.module.split(".", 1)[0]}
            else:
                names = set()
            assert names.isdisjoint(forbidden_imports)
            if isinstance(node, ast.Name):
                assert node.id not in forbidden_symbols
            if isinstance(node, ast.Attribute):
                assert node.attr not in forbidden_symbols
