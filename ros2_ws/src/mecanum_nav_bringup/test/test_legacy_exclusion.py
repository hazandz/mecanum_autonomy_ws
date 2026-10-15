import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN = (
    "RPLiDAR_A1M8_1", "base_scan", "rplidar_link", "warehouse_map2",
    "slam_toolbox", "PreferForwardCritic", "velocity_smoother",
    "collision_monitor", "SafetySupervisor", "FinalTwistPublisher",
    "config_hash", "ResolvedConfigV3",
)
RUNTIME_IMPORTS = {
    "rclpy", "launch", "launch_ros", "tf2_ros", "nav2_bringup", "nav2_amcl",
    "nav2_map_server", "robot_localization", "gazebo", "sensor_msgs", "nav_msgs",
}


def test_new_configs_and_guards_exclude_legacy_and_runtime_activation():
    source_paths = [
        ROOT / "config/state_estimation/ekf_sim.yaml",
        ROOT / "config/localization/amcl_omni.yaml",
        ROOT / "config/navigation/nav2_baseline.yaml",
        ROOT / "config/lifecycle/navigation_v1_startup.yaml",
        ROOT / "config/remaps/navigation_v1.yaml",
        ROOT / "launch/navigation_v1.launch.py",
        ROOT / "launch/navigation_v1_lifecycle.launch.py",
    ]
    for path in source_paths:
        text = path.read_text(encoding="utf-8")
        for forbidden in FORBIDDEN:
            assert forbidden not in text
    for path in source_paths[-2:]:
        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text)
        assert "generate_launch_description" in {node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
        assert "RuntimeError" in text and "runtime graph creation" in text
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module.split(".", 1)[0])
        assert imports.isdisjoint(RUNTIME_IMPORTS)
        assert "Node(" not in text and "LifecycleNode" not in text and "LaunchDescription" not in text
        assert text.index("MAP_YAML_FILENAME ==") < text.index("raise RuntimeError")


def test_tests_and_helpers_do_not_import_ros_runtime():
    test_paths = sorted((ROOT / "test").glob("test_*.py"))
    new_names = {
        "test_package_layout.py", "test_dependency_lock_schema.py", "test_map_artifact_reference.py",
        "test_tf_owner_contract.py", "test_navigation_v1_static_config.py", "test_remap_namespace_schema.py",
        "test_lifecycle_startup_contract.py", "test_legacy_exclusion.py",
    }
    for path in test_paths:
        if path.name not in new_names:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module.split(".", 1)[0])
        assert imports.isdisjoint(RUNTIME_IMPORTS)
