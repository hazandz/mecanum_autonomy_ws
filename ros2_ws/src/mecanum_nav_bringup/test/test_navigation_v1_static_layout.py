import ast
from pathlib import Path
import re
import xml.etree.ElementTree as ET


PACKAGE_ROOT = Path(__file__).resolve().parents[1]


def test_package_layout_contains_only_owned_static_sources():
    required = (
        "package.xml",
        "setup.py",
        "setup.cfg",
        "resource/mecanum_nav_bringup",
        "mecanum_nav_bringup/__init__.py",
        "mecanum_nav_bringup/navigation_v1_static_contract.py",
        "config/navigation_v1_source_lock.template.yaml",
        "config/navigation_v1_static_bringup.template.yaml",
        "launch/navigation_v1_static_bringup.launch.py",
        "test/test_navigation_v1_static_contract.py",
        "test/test_navigation_v1_static_layout.py",
    )
    assert all((PACKAGE_ROOT / relative).is_file() for relative in required)
    package = ET.parse(PACKAGE_ROOT / "package.xml").getroot()
    assert package.findtext("name") == "mecanum_nav_bringup"
    assert package.findtext("version")
    assert package.findtext("export/build_type") == "ament_python"


def test_static_templates_have_no_numeric_runtime_defaults_or_legacy_fallback():
    for name in (
        "navigation_v1_source_lock.template.yaml",
        "navigation_v1_static_bringup.template.yaml",
    ):
        text = (PACKAGE_ROOT / "config" / name).read_text(encoding="utf-8")
        assert not re.search(r":\s*-?\d+(?:\.\d+)?\s*(?:#.*)?$", text, re.MULTILINE)
        assert "ros2_ws/src/ROBOT_URDF_final_description" not in text
        assert "base_scan" not in text
        assert "RPLiDAR_A1M8_1" not in text


def test_pure_validator_and_guarded_launch_have_no_ros_runtime_imports():
    forbidden_roots = {
        "rclpy",
        "tf2_ros",
        "launch_ros",
        "nav2_bringup",
        "nav2_amcl",
        "nav2_map_server",
        "robot_localization",
        "robot_state_publisher",
        "sensor_msgs",
        "nav_msgs",
        "geometry_msgs",
        "gazebo",
        "rosbag",
    }
    for relative in (
        "mecanum_nav_bringup/navigation_v1_static_contract.py",
        "launch/navigation_v1_static_bringup.launch.py",
    ):
        source = (PACKAGE_ROOT / relative).read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name.split(".", 1)[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module.split(".", 1)[0]]
            else:
                continue
            assert forbidden_roots.isdisjoint(names)


def test_launch_guard_checks_pending_templates_before_any_launch_import():
    source = (PACKAGE_ROOT / "launch/navigation_v1_static_bringup.launch.py").read_text()
    pending_check = source.index("reject_pending_markers(*texts)")
    final_guard = source.index("Navigation V1 runtime graph creation is outside")
    assert pending_check < final_guard
    assert "LaunchDescription" not in source
