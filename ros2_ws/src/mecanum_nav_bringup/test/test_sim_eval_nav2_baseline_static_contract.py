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
    lifecycle = yaml.safe_load((ROOT / "ros2_ws/src/mecanum_nav_bringup/config/lifecycle/sim_eval_nav2_baseline.runtime.yaml").read_text())
    assert lifecycle["barrier_owner"] == "SafetyLifecycle"
    assert lifecycle["motion_requires"] == ["READY", "fresh_barrier"]


def test_no_forbidden_ingress_is_added_by_new_configs_or_launch() -> None:
    launch = (ROOT / "ros2_ws/src/mecanum_nav_bringup/launch/sim_eval_nav2_baseline_system.launch.py").read_text()
    config = (ROOT / "ros2_ws/src/mecanum_nav_bringup/config/navigation/sim_eval_nav2_baseline.runtime.yaml").read_text()
    for forbidden in ("/ground_truth/odom", "gz_topic_name: /odom", "gz_topic_name: /tf", "/tf_static"):
        assert forbidden not in launch
        assert forbidden not in config
