import json
from pathlib import Path
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = ROOT.parents[2]
LOCK_PATH = REPOSITORY / "docs/governance/evidence/WP-05_NAVIGATION_V1_EXTERNAL_14_ROOT_DEPENDENCY_LOCK.json"
EXPECTED = [
    "nav2_bringup", "nav2_amcl", "nav2_map_server", "nav2_lifecycle_manager",
    "nav2_planner", "nav2_controller", "nav2_bt_navigator", "nav2_costmap_2d",
    "robot_localization", "tf2_ros", "robot_state_publisher", "sensor_msgs",
    "nav_msgs", "geometry_msgs",
]


def test_package_dependencies_match_the_fourteen_locked_logical_roots():
    lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    assert lock["direct_dependency_roots"] == EXPECTED
    entries = lock["external_package_locks"]
    assert [entry["ros_package_name"] for entry in entries] == EXPECTED
    package = ET.parse(ROOT / "package.xml").getroot()
    assert [node.text for node in package.findall("exec_depend")] == EXPECTED
    assert "launch_ros" not in lock["direct_dependency_roots"]
    assert "launch_ros" not in [node.text for node in package.findall("exec_depend")]
