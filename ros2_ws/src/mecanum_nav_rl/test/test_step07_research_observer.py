"""Offline boundary and production method checks for the in-process adapter."""

import sys

from mecanum_nav_rl.observations import step07_research_observer as observer_module
from mecanum_nav_rl.observations.step07_research_acceptance import Context


def test_observer_import_does_not_import_or_initialize_ros_graph():
    assert "rclpy" not in sys.modules
    assert "ros2cli" not in sys.modules
    assert hasattr(observer_module, "Step07ResearchObserver")


def test_observer_has_no_collector_process_or_file_ipc_protocol():
    source = open(observer_module.__file__, encoding="utf-8").read()
    assert "subprocess" not in source
    assert "ros2cli" not in source
    assert "ACK/RELEASE" not in source
    assert "lookup_transform(\"base_link\", \"map\", stamp" in source
    assert "ClockType.ROS_TIME" in source


def test_observer_admission_context_is_static_config_plus_real_lifecycle_identity():
    context = Context(5, 2, 3, "f" * 64)
    assert context == Context(5, 2, 3, "f" * 64)
    assert context != Context(5, 2, 4, "f" * 64)
