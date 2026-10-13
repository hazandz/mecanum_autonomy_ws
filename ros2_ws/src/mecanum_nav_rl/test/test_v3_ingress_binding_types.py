import ast
import sys
from pathlib import Path
from types import ModuleType

import pytest


_PACKAGE_DIR = Path(__file__).parents[1] / "mecanum_nav_rl"
for _name, _path in (("mecanum_nav_rl", _PACKAGE_DIR),
                     ("mecanum_nav_rl.observations", _PACKAGE_DIR / "observations")):
    if _name not in sys.modules:
        _module = ModuleType(_name)
        _module.__path__ = [str(_path)]
        sys.modules[_name] = _module

from mecanum_nav_rl.observations.v3_ingress_binding_types import IngressMessageBinding


class FakeMessage:
    pass


def test_binding_is_frozen_and_keeps_injected_class_callback_and_metadata():
    callback = lambda message: message
    binding = IngressMessageBinding(
        FakeMessage, "/scan", "sensor_msgs/msg/LaserScan", "lidar_frame", callback, None)
    assert binding.expected_message_class is FakeMessage
    assert binding.expected_topic == "/scan"
    assert binding.expected_type == "sensor_msgs/msg/LaserScan"
    assert binding.expected_frame_id == "lidar_frame"
    assert binding.converter is callback
    with pytest.raises((AttributeError, TypeError)):
        binding.expected_topic = "/other"


@pytest.mark.parametrize("kwargs", [
    {"expected_message_class": object(), "expected_topic": None,
     "expected_type": "x/y", "expected_frame_id": "map",
     "converter": None, "expected_child_frame_id": None},
    {"expected_message_class": FakeMessage, "expected_topic": 1,
     "expected_type": "x/y", "expected_frame_id": "map",
     "converter": None, "expected_child_frame_id": None},
    {"expected_message_class": FakeMessage, "expected_topic": None,
     "expected_type": "x/y", "expected_frame_id": "map",
     "converter": object(), "expected_child_frame_id": None},
])
def test_binding_rejects_wrong_types_without_coercion(kwargs):
    with pytest.raises(TypeError):
        IngressMessageBinding(**kwargs)


def test_production_adapters_do_not_import_ros_runtime_packages():
    source_dir = _PACKAGE_DIR / "observations"
    modules = (
        "v3_ingress_binding_types.py",
        "v3_lidar_ingress_adapter.py",
        "v3_local_reference_ingress_adapter.py",
        "v3_measured_twist_ingress_adapter.py",
    )
    forbidden = {
        "rclpy", "tf2_ros", "launch", "launch_ros", "sensor_msgs", "nav_msgs",
        "geometry_msgs", "rosbag", "gazebo", "ros_gz",
    }
    for filename in modules:
        tree = ast.parse((source_dir / filename).read_text(encoding="utf-8"))
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module.split(".", 1)[0])
        assert not forbidden.intersection(imports), (filename, imports)
