"""Offline structural checks for static Navigation V1 localization templates."""

import ast
from pathlib import Path

import yaml


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_PATHS = {
    "amcl": PACKAGE_ROOT / "config/localization/navigation_v1_amcl_omni.static.template.yaml",
    "ekf": PACKAGE_ROOT / "config/state_estimation/navigation_v1_ekf.static.template.yaml",
    "lifecycle": PACKAGE_ROOT / "config/lifecycle/navigation_v1_localization_lifecycle.static.template.yaml",
}
BOUNDARY_STATUS = {
    "MAP_ARTIFACT": "DRAFT_ON_INTEGRATION_NOT_APPROVED",
    "WORLD_FRAME": "NOT_DECLARED",
    "RUNTIME_COMPATIBILITY": "NOT_VALIDATED",
    "RUNTIME_APPROVED": "NOT_APPROVED",
    "YDLIDAR_X3_PRO_RUNTIME_SOURCE_PIN": "PENDING",
    "ROS_GAZEBO_SCAN_BRIDGE_SOURCE_PIN": "PENDING",
    "SCAN_RUNTIME_PROFILE": "PENDING",
}
STARTUP_ORDER = (
    "robot_description",
    "drivers_bridge",
    "EKF",
    "Map_Server",
    "AMCL",
    "healthy_LocalizationMonitor",
    "Planner_global_costmap",
    "Safety",
    "selected_controller_or_manager",
    "mission_acceptance",
)
FORBIDDEN_KEYS = {
    "map_id",
    "map_content_hash",
    "map_path",
    "artifact_path",
    "config_hash",
    "namespace",
    "remap",
    "remaps",
    "timeout",
    "covariance",
    "frequency",
    "autostart",
    "launch_arguments",
}


def _load_templates():
    assert all(path.is_file() for path in TEMPLATE_PATHS.values())
    return {
        name: yaml.safe_load(path.read_text(encoding="utf-8"))
        for name, path in TEMPLATE_PATHS.items()
    }


def _walk_keys(value):
    if isinstance(value, dict):
        for key, child in value.items():
            yield key
            yield from _walk_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_keys(child)


def test_three_templates_exist_parse_and_are_static_non_executable():
    templates = _load_templates()
    assert set(templates) == {"amcl", "ekf", "lifecycle"}
    for template in templates.values():
        assert template["classification"] == "STATIC_TEMPLATE_ONLY"
        assert template["runtime_eligible"] is False
        assert template["runtime_graph_creation"] == "FORBIDDEN"
        assert template["boundary_status"] == BOUNDARY_STATUS


def test_amcl_template_contains_only_selected_target_invariants():
    amcl = _load_templates()["amcl"]
    assert amcl["provider"] == "AMCL"
    assert amcl["mode"] == "NAV2_BASELINE"
    assert amcl["tf_edge"] == "map -> odom"
    assert amcl["tf_edge_owner"] == "AMCL"
    assert amcl["robot_model_type"] == "nav2_amcl::OmniMotionModel"
    assert amcl["scan"] == {
        "topic": "/scan",
        "type": "sensor_msgs/msg/LaserScan",
        "header_frame_id": "lidar_frame",
        "alias_policy": "FORBIDDEN",
    }


def test_ekf_template_contains_target_edge_inputs_and_output_contract():
    ekf = _load_templates()["ekf"]
    assert ekf["provider"] == "robot_localization"
    assert ekf["tf_edge"] == "odom -> base_link"
    assert ekf["tf_edge_owner"] == "robot_localization"
    assert ekf["required_inputs"] == ["/wheel/odometry_raw", "/imu/data"]
    assert ekf["target_output"] == {
        "topic": "/odometry/filtered",
        "type": "nav_msgs/msg/Odometry",
        "header_frame_id": "odom",
        "child_frame_id": "base_link",
    }


def test_lifecycle_policy_has_exact_health_gated_startup_order_and_inhibition():
    lifecycle = _load_templates()["lifecycle"]
    assert lifecycle["health_gated"] is True
    assert tuple(lifecycle["startup_order"]) == STARTUP_ORDER
    assert lifecycle["fail_closed"] == {
        "upstream_component_not_healthy": "NAVIGATION_BASELINE_TRANSITION_FORBIDDEN",
        "source_pin_missing_or_unverified": "NAVIGATION_BASELINE_TRANSITION_FORBIDDEN",
        "activation": "FORBIDDEN",
        "command_or_motion_enable": "FORBIDDEN",
    }


def test_templates_have_no_unselected_runtime_values_or_resolved_profile_claims():
    templates = _load_templates()
    for template in templates.values():
        assert FORBIDDEN_KEYS.isdisjoint(set(_walk_keys(template)))
        assert template["runtime_eligible"] is False
        assert template["classification"] == "STATIC_TEMPLATE_ONLY"
        assert "config_hash" not in template
        assert "resolved_profile" not in template
        assert "map_approval" not in template
        assert template["runtime_graph_creation"] == "FORBIDDEN"


def test_static_validator_and_policy_templates_import_no_ros_runtime():
    source_paths = [
        PACKAGE_ROOT / "mecanum_nav_bringup/navigation_v1_static_contract.py",
        Path(__file__),
    ]
    forbidden_roots = {
        "rclpy",
        "launch",
        "launch_ros",
        "nav2_bringup",
        "nav2_amcl",
        "robot_localization",
        "gazebo",
    }
    for path in source_paths:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots = {alias.name.split(".", 1)[0] for alias in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module:
                roots = {node.module.split(".", 1)[0]}
            else:
                continue
            assert forbidden_roots.isdisjoint(roots)


def test_templates_do_not_claim_executable_or_gazebo_scan_is_ros_scan():
    texts = [path.read_text(encoding="utf-8") for path in TEMPLATE_PATHS.values()]
    combined = "\n".join(texts)
    assert "executable_profile" not in combined
    assert "resolved_profile" not in combined
    assert "Gazebo transport scan is ROS /scan" not in combined
    assert "ResolvedConfig" not in combined
