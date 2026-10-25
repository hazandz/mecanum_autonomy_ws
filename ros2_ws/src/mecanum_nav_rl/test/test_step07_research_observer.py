"""Offline boundary and production method checks for the in-process adapter."""

import sys
import threading
import ast
from collections import deque
import math
from types import SimpleNamespace

from mecanum_nav_rl.observations import step07_research_observer as observer_module
from mecanum_nav_rl.observations.step07_research_acceptance import Context


def test_observer_import_does_not_import_or_initialize_ros_graph():
    assert "ros2cli" not in sys.modules
    assert hasattr(observer_module, "Step07ResearchObserver")
    tree = ast.parse(open(observer_module.__file__, encoding="utf-8").read())
    top_level_ros_imports = [node for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom))
        and ((isinstance(node, ast.Import) and any(alias.name.startswith("rclpy") for alias in node.names))
             or (isinstance(node, ast.ImportFrom) and (node.module or "").startswith("rclpy")))]
    assert top_level_ros_imports == []


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


def _lifecycle_message(*, sec, barrier_sec, sequence=4, generation=3, epoch=2,
                       runtime=5, primary=2, barrier=2, permitted=False):
    return SimpleNamespace(
        header=SimpleNamespace(stamp=SimpleNamespace(sec=sec, nanosec=0), frame_id="base_link"),
        barrier_stamp=SimpleNamespace(sec=barrier_sec, nanosec=0),
        sequence=sequence, episode_generation=generation, reset_epoch=epoch,
        runtime_generation=runtime, primary_state=primary, barrier_state=barrier,
        motion_permitted=permitted, reason="test",
    )


def _bare_observer():
    instance = object.__new__(observer_module.Step07ResearchObserver)
    instance._lock = threading.RLock()
    instance._config_hash = "c" * 64
    instance._steady_ns = lambda: 9_000_000_000
    instance.context = None
    instance.lifecycle = None
    instance.barrier_stamp_ns = 0
    instance.barrier_event_stamp_ns = 0
    instance.barrier_sequence = 0
    instance.action_events = []
    return instance


def test_lifecycle_callback_heartbeat_refreshes_freshness_without_new_barrier_event():
    observer = _bare_observer()
    first = _lifecycle_message(sec=10, barrier_sec=9)
    observer._lifecycle_cb(first)
    assert observer.lifecycle.value["sequence"] == 4
    assert observer.barrier_sequence == 1
    event_stamp = observer.barrier_event_stamp_ns
    for sec in (11, 12, 13):
        observer._lifecycle_cb(_lifecycle_message(sec=sec, barrier_sec=sec-1))
        assert observer.lifecycle.stamp_ns == sec * 1_000_000_000
        assert observer.barrier_event_stamp_ns == event_stamp
        assert observer.barrier_sequence == 1


def test_lifecycle_callback_tracks_rearm_generation_and_nonready_fault_events():
    observer = _bare_observer()
    observer._lifecycle_cb(_lifecycle_message(sec=10, barrier_sec=9))
    observer._lifecycle_cb(_lifecycle_message(sec=11, barrier_sec=11, sequence=5,
                                               runtime=6, barrier=1, permitted=True))
    assert observer.barrier_sequence == 2
    assert observer.lifecycle.context.runtime_generation == 6
    assert observer.lifecycle.value["barrier_state"] == 1
    observer._lifecycle_cb(_lifecycle_message(sec=12, barrier_sec=12, sequence=6,
                                               barrier=2, permitted=False))
    assert observer.barrier_sequence == 3
    observer._lifecycle_cb(_lifecycle_message(sec=13, barrier_sec=13, sequence=7,
                                               barrier=3, permitted=False))
    assert observer.barrier_sequence == 4


def _valid_odom_message():
    vector3 = lambda: SimpleNamespace(x=0.0, y=0.0, z=0.0)
    pose = SimpleNamespace(position=vector3(), orientation=SimpleNamespace(x=0.0, y=0.0, z=0.0, w=1.0))
    twist = SimpleNamespace(linear=vector3(), angular=vector3())
    return SimpleNamespace(header=SimpleNamespace(frame_id="odom"), child_frame_id="base_link",
        pose=SimpleNamespace(pose=pose, covariance=[0.0]*36),
        twist=SimpleNamespace(twist=twist, covariance=[0.0]*36))


def test_production_odometry_admission_rejects_wrong_frame_nonfinite_and_invalid_covariance():
    valid = _valid_odom_message()
    assert observer_module.Step07ResearchObserver._valid_odom(valid)
    wrong_frame = _valid_odom_message(); wrong_frame.child_frame_id = "base_footprint"
    assert not observer_module.Step07ResearchObserver._valid_odom(wrong_frame)
    invalid_value = _valid_odom_message(); invalid_value.twist.twist.linear.y = math.nan
    assert not observer_module.Step07ResearchObserver._valid_odom(invalid_value)
    invalid_covariance = _valid_odom_message(); invalid_covariance.pose.covariance[0] = -1.0
    assert not observer_module.Step07ResearchObserver._valid_odom(invalid_covariance)


def test_amcl_callback_does_not_admit_nonfinite_pose_or_invalid_quaternion():
    observer = object.__new__(observer_module.Step07ResearchObserver)
    observer._lock = threading.RLock()
    observer._steady_ns = lambda: 100
    observer.localization = deque(maxlen=64)
    message = SimpleNamespace(header=SimpleNamespace(frame_id="map",
        stamp=SimpleNamespace(sec=1, nanosec=0)), pose=SimpleNamespace(
        pose=SimpleNamespace(position=SimpleNamespace(x=0.0, y=0.0, z=0.0),
            orientation=SimpleNamespace(x=0.0, y=0.0, z=0.0, w=1.0)),
        covariance=[0.0]*36))
    observer._amcl(message)
    assert len(observer.localization) == 1
    message.pose.pose.orientation.w = 0.0
    observer._amcl(message)
    assert len(observer.localization) == 1
    message.pose.pose.position.x = math.inf
    observer._amcl(message)
    assert len(observer.localization) == 1
