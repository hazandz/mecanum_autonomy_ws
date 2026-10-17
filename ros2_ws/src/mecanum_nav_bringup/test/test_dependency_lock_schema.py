import json
from pathlib import Path
import xml.etree.ElementTree as ET

import yaml


ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = ROOT.parents[2]
LOCK_PATH = REPOSITORY / "docs/governance/evidence/WP-05_NAVIGATION_V1_EXTERNAL_14_ROOT_DEPENDENCY_LOCK.json"
SOURCE_LOCK_TEMPLATE = ROOT / "config/navigation_v1_source_lock.template.yaml"
COMMON_NAVIGATION_V1_ROOTS = [
    "nav2_bringup", "nav2_amcl", "nav2_map_server", "nav2_lifecycle_manager",
    "nav2_planner", "nav2_controller", "nav2_bt_navigator", "nav2_costmap_2d",
    "robot_localization", "tf2_ros", "robot_state_publisher", "sensor_msgs",
    "nav_msgs", "geometry_msgs",
]
PROFILE_SPECIFIC_RUNTIME_EXEC_DEPENDS = ["ros_gz_bridge", "launch", "launch_ros"]
PROFILE_SPECIFIC_NOT_COMMON_LOCK = PROFILE_SPECIFIC_RUNTIME_EXEC_DEPENDS


def test_wp05_lock_contains_only_the_fourteen_common_navigation_v1_roots():
    lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    assert lock["direct_dependency_roots"] == COMMON_NAVIGATION_V1_ROOTS
    entries = lock["external_package_locks"]
    assert [entry["ros_package_name"] for entry in entries] == COMMON_NAVIGATION_V1_ROOTS
    assert not set(PROFILE_SPECIFIC_NOT_COMMON_LOCK).intersection(
        lock["direct_dependency_roots"]
    )
    assert not set(PROFILE_SPECIFIC_NOT_COMMON_LOCK).intersection(
        entry["ros_package_name"] for entry in entries
    )

    template = yaml.safe_load(SOURCE_LOCK_TEMPLATE.read_text(encoding="utf-8"))
    assert template["required_direct_dependency_roots"] == COMMON_NAVIGATION_V1_ROOTS
    assert not set(PROFILE_SPECIFIC_NOT_COMMON_LOCK).intersection(
        template["required_direct_dependency_roots"]
    )


def test_package_exec_dependencies_are_common_roots_then_profile_specific_runtime_roots():
    package = ET.parse(ROOT / "package.xml").getroot()
    exec_dependencies = [node.text for node in package.findall("exec_depend")]
    assert exec_dependencies == (
        COMMON_NAVIGATION_V1_ROOTS + PROFILE_SPECIFIC_RUNTIME_EXEC_DEPENDS
    )
    assert exec_dependencies[-3:] == PROFILE_SPECIFIC_NOT_COMMON_LOCK
