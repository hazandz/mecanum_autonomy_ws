"""Offline boundary checks for the Step-6 sim_eval baseline source."""
from pathlib import Path
import xml.etree.ElementTree as ET

import yaml

ROOT = Path(__file__).resolve().parents[4]


def test_command_bridge_is_ros_to_gazebo_only() -> None:
    path = ROOT / "ros2_ws/src/mecanum_nav_bringup/config/bridge/sim_eval_cmd_vel.runtime.yaml"
    mappings = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert mappings == [{
        "ros_topic_name": "/cmd_vel", "gz_topic_name": "/cmd_vel",
        "ros_type_name": "geometry_msgs/msg/Twist", "gz_type_name": "gz.msgs.Twist",
        "direction": "ROS_TO_GZ",
    }]


def test_required_package_dependencies_and_lifecycle_config_parse() -> None:
    for package in (
        "ros2_ws/src/mecanum_nav_bringup/package.xml",
        "ros2_ws/src/mecanum_nav_rl/package.xml",
        "ros2_ws/src/mecanum_nav_rl_interfaces/package.xml",
    ):
        ET.fromstring((ROOT / package).read_bytes())
    deps = [node.text for node in ET.parse(ROOT / "ros2_ws/src/mecanum_nav_rl/package.xml").getroot().findall("exec_depend")]
    assert deps.count("lifecycle_msgs") == 1
    assert deps.count("std_srvs") == 1
    lifecycle = yaml.safe_load((ROOT / "ros2_ws/src/mecanum_nav_bringup/config/lifecycle/sim_eval_nav2_baseline.runtime.yaml").read_text())
    assert lifecycle["barrier_owner"] == "SafetyLifecycle"
    assert lifecycle["motion_requires"] == ["READY", "fresh_barrier"]
    safety = yaml.safe_load((ROOT / "ros2_ws/src/mecanum_nav_rl/config/safety/sim_eval_nav2_baseline_safety.yaml").read_text())
    assert safety["estop_boundary"] == {
        "scope": "SIM_EVAL_ONLY_NOT_HARDWARE_ESTOP",
        "default_active": True,
        "release_requires_launch_authorization": True,
    }


def test_no_forbidden_ingress_is_added_by_new_configs_or_launch() -> None:
    launch = (ROOT / "ros2_ws/src/mecanum_nav_bringup/launch/sim_eval_nav2_baseline_system.launch.py").read_text()
    config = (ROOT / "ros2_ws/src/mecanum_nav_bringup/config/navigation/sim_eval_nav2_baseline.runtime.yaml").read_text()
    for forbidden in ("/ground_truth/odom", "gz_topic_name: /odom", "gz_topic_name: /tf", "/tf_static"):
        assert forbidden not in launch
        assert forbidden not in config


def test_nav2_and_safety_command_ownership_is_explicit() -> None:
    root = ROOT / "ros2_ws/src"
    launch = (root / "mecanum_nav_bringup/launch/sim_eval_nav2_baseline_system.launch.py").read_text()
    publisher = (root / "mecanum_nav_rl/mecanum_nav_rl/runtime_safety/final_twist_publisher_node.py").read_text()
    supervisor = (root / "mecanum_nav_rl/mecanum_nav_rl/runtime_safety/safety_supervisor_node.py").read_text()
    assert '"/mecanum/nav2_candidate_cmd"' in launch
    assert launch.count('("cmd_vel", "/mecanum/nav2_candidate_cmd")') == 2
    assert '"/mecanum/safety_accepted_cmd"' in supervisor
    assert publisher.count('self.create_publisher(Twist, "/cmd_vel"') == 1
    assert 'create_publisher(Twist, "/cmd_vel"' not in supervisor
    assert "direction: ROS_TO_GZ" in (root / "mecanum_nav_bringup/config/bridge/sim_eval_cmd_vel.runtime.yaml").read_text()
    assert 'publisher_owner: mecanum_base_bridge' in (root / "mecanum_nav_rl/config/v3/topics.yaml").read_text().split("- name: /imu/data", 1)[1].split("- name:", 1)[0]


def test_each_navigation_node_uses_filtered_odometry_and_direct_observer_dependencies():
    navigation = yaml.safe_load((ROOT / "ros2_ws/src/mecanum_nav_bringup/config/navigation/sim_eval_nav2_baseline.runtime.yaml").read_text())
    for node in ("controller_server", "bt_navigator"):
        assert navigation[node]["ros__parameters"]["odom_topic"] == "/odometry/filtered"
    dependencies = [item.text for item in ET.parse(ROOT / "ros2_ws/src/mecanum_nav_rl/package.xml").getroot().findall("exec_depend")]
    for package in ("action_msgs", "nav2_msgs", "tf2_geometry_msgs"):
        assert dependencies.count(package) == 1
    safety = yaml.safe_load((ROOT / "ros2_ws/src/mecanum_nav_rl/config/safety/sim_eval_nav2_baseline_safety.yaml").read_text())
    assert safety["scan_validity"]["positive_infinity"] == "VALID_NO_RETURN_WITH_VALID_RANGE_METADATA"
