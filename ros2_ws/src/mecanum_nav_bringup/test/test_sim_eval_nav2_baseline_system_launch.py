"""Static-only import and ownership checks for the consolidated launch."""
from pathlib import Path
import xml.etree.ElementTree as ET

from launch import LaunchDescription

ROOT = Path(__file__).resolve().parents[4]


def test_composite_launch_imports_without_starting_processes(monkeypatch, tmp_path) -> None:
    import importlib.util

    monkeypatch.setenv("ROS_HOME", str(tmp_path / "ros_home"))
    monkeypatch.setenv("ROS_LOG_DIR", str(tmp_path / "ros_log"))

    path = ROOT / "ros2_ws/src/mecanum_nav_bringup/launch/sim_eval_nav2_baseline_system.launch.py"
    spec = importlib.util.spec_from_file_location("sim_eval_nav2_baseline_system", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    description = module.generate_launch_description()
    assert isinstance(description, LaunchDescription)
    # OpaqueFunction is left unevaluated, so no process is launched by this test.
    assert len(description.entities) == 9


def test_system_launch_has_exact_command_route_and_safety_executables() -> None:
    source = (ROOT / "ros2_ws/src/mecanum_nav_bringup/launch/sim_eval_nav2_baseline_system.launch.py").read_text()
    assert '("cmd_vel", "/mecanum/nav2_candidate_cmd")' in source
    assert 'executable="safety_lifecycle"' in source
    assert 'executable="safety_supervisor"' in source
    assert 'executable="final_twist_publisher"' in source
    assert "sim_eval_tf_ekf_state_estimation.launch.py" in source
    assert "sim_eval_lidar_scan_bridge.runtime.yaml" in source
    assert "sim_eval_cmd_vel.runtime.yaml" in source
    assert "gazebo.launch.py" not in source
    assert "ground_truth" not in source
    assert '"/odom"' not in source
    assert '"/tf"' not in source
    assert "Path.cwd()" not in source
    assert "canonical_map_root" in source
    assert 'DeclareLaunchArgument("sim_estop_release_authorized", default_value="false")' in source
    assert source.index("bootstrap_module.validate_fuel_cache(") < source.index("bootstrap_actions = _bootstrap_include(")
    assert '"fuel_cache_root": fuel_cache_root' in source
    assert '"canonical_map_root"' in source
    assert 'DeclareLaunchArgument("start_bootstrap", default_value="true")' in source
    assert '_literal_bool(start_bootstrap, "start_bootstrap")' in source
    # The same map/Fuel validation occurs before the conditional include in both modes.
    assert source.index("checked_map_yaml(") < source.index("bootstrap_module.validate_fuel_cache(")
    assert source.index("bootstrap_module.validate_fuel_cache(") < source.index("bootstrap_actions = _bootstrap_include(")
    import importlib.util
    import pytest
    path = ROOT / "ros2_ws/src/mecanum_nav_bringup/launch/sim_eval_nav2_baseline_system.launch.py"
    spec = importlib.util.spec_from_file_location("sim_eval_estop_literal_test", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module._literal_bool("true", "sim_estop_release_authorized") is True
    assert module._literal_bool("false", "sim_estop_release_authorized") is False
    for invalid in ("True", "FALSE", "1", "yes", ""):
        with pytest.raises(RuntimeError, match="INVALID_LITERAL_BOOLEAN"):
            module._literal_bool(invalid, "sim_estop_release_authorized")


def test_bootstrap_include_defaults_to_once_and_can_be_separated_without_launching():
    import importlib.util
    import pytest
    from launch.actions import IncludeLaunchDescription

    path = ROOT / "ros2_ws/src/mecanum_nav_bringup/launch/sim_eval_nav2_baseline_system.launch.py"
    spec = importlib.util.spec_from_file_location("sim_eval_bootstrap_split_test", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    pose = {"initial_pose_map_x": "0.0", "initial_pose_map_y": "0.0", "initial_pose_map_yaw": "0.0"}
    default_actions = module._bootstrap_include("true", "/installed/bootstrap.launch.py", "partition-x", "/home/test/.gz/fuel", pose)
    separated_actions = module._bootstrap_include("false", "/installed/bootstrap.launch.py", "partition-x", "/home/test/.gz/fuel", pose)
    assert len(default_actions) == 1 and isinstance(default_actions[0], IncludeLaunchDescription)
    assert separated_actions == []
    with pytest.raises(RuntimeError, match="INVALID_LITERAL_BOOLEAN:start_bootstrap"):
        module._bootstrap_include("True", "/installed/bootstrap.launch.py", "partition-x", "/home/test/.gz/fuel", pose)


def test_map_root_is_absolute_and_all_canonical_files_are_pinned() -> None:
    import importlib.util
    import pytest
    path = ROOT / "ros2_ws/src/mecanum_nav_bringup/launch/sim_eval_nav2_baseline_system.launch.py"
    spec = importlib.util.spec_from_file_location("sim_eval_map_preflight_test", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with pytest.raises(RuntimeError, match="SIM_EVAL_CANONICAL_MAP_ROOT_MUST_BE_ABSOLUTE"):
        module.checked_map_yaml("relative/map")
    with pytest.raises(RuntimeError, match="SIM_EVAL_CANONICAL_MAP_ROOT_MISSING"):
        module.checked_map_yaml(str(ROOT / "missing-map-root"))
    expected = module.checked_map_yaml(str(ROOT / "artifacts/maps/warehouse_map2"))
    assert expected == str(ROOT / "artifacts/maps/warehouse_map2/map.yaml")


def test_map_localization_and_tf_ownership_are_declared_once() -> None:
    navigation = (ROOT / "ros2_ws/src/mecanum_nav_bringup/config/navigation/sim_eval_nav2_baseline.runtime.yaml").read_text()
    assert "topic_name: /map" in navigation
    assert "yaml_filename: artifacts/maps/warehouse_map2/map.yaml" in navigation
    assert "global_frame: map" in navigation
    assert "odom_topic: /odometry/filtered" in navigation
    ekf = (ROOT / "ros2_ws/src/mecanum_nav_bringup/config/state_estimation/ekf_sim.yaml").read_text()
    assert "world_frame: odom" in ekf
    assert "base_link_frame: base_link" in ekf
    amcl = (ROOT / "ros2_ws/src/mecanum_nav_bringup/config/localization/amcl_omni.yaml").read_text()
    assert "global_frame_id: map" in amcl
    assert "odom_frame_id: odom" in amcl
    assert "base_frame_id: base_link" in amcl
    xacro = (ROOT / "ros2_ws/src/ROBOT_URDF_final_description/urdf/ROBOT_URDF_final.xacro").read_text()
    assert "lidar_frame" in xacro


def test_state_estimation_child_forwards_the_exact_caller_partition_without_runtime(
    monkeypatch,
):
    import importlib.util
    import pytest
    from launch import LaunchContext
    from launch.utilities import perform_substitutions
    from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, SetEnvironmentVariable

    relative = "ros2_ws/src/mecanum_nav_bringup/launch/sim_eval_tf_ekf_state_estimation.launch.py"
    path = ROOT / relative
    spec = importlib.util.spec_from_file_location("state_estimation_partition_contract", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    description = module.generate_launch_description()
    partition_argument = next(
        action for action in description.entities
        if isinstance(action, DeclareLaunchArgument) and action.name == "gz_partition"
    )
    assert partition_argument.default_value is None
    source = path.read_text(encoding="utf-8")
    assert "EXPECTED_PARTITION" not in source
    assert "wp06_scan_probe_run_002" not in source
    assert "partition !=" not in source
    assert "use_sim_time != \"true\"" in source

    monkeypatch.setattr(module, "get_package_share_directory", lambda _package: "/share/mecanum_base_bridge")
    context = LaunchContext()
    supplied = "caller_partition_opaque_123"
    context.launch_configurations.update({"gz_partition": supplied, "use_sim_time": "true"})
    actions = module._create_runtime_actions(context)
    env_action = next(action for action in actions if isinstance(action, SetEnvironmentVariable))
    include = next(action for action in actions if isinstance(action, IncludeLaunchDescription))
    assert perform_substitutions(context, env_action.name) == "GZ_PARTITION"
    assert perform_substitutions(context, env_action.value) == supplied
    assert dict(include.launch_arguments)["gz_partition"] == supplied

    for invalid in ("", "   ", "\t\n"):
        bad_context = LaunchContext()
        bad_context.launch_configurations.update({"gz_partition": invalid, "use_sim_time": "true"})
        with pytest.raises(RuntimeError, match="SIM_EVAL_GZ_PARTITION_REQUIRED"):
            module._create_runtime_actions(bad_context)
    with pytest.raises(RuntimeError, match="SIM_EVAL_GZ_PARTITION_REQUIRED"):
        module._create_runtime_actions(LaunchContext())
    invalid_clock = LaunchContext()
    invalid_clock.launch_configurations.update({"gz_partition": supplied, "use_sim_time": "false"})
    with pytest.raises(RuntimeError, match="WP06-6F requires use_sim_time=true"):
        module._create_runtime_actions(invalid_clock)


def test_nav2_runtime_dependencies_cover_required_nodes_and_plugin_providers():
    package = ET.parse(ROOT / "ros2_ws/src/mecanum_nav_bringup/package.xml").getroot()
    exec_dependencies = [node.text for node in package.findall("exec_depend")]
    assert len(exec_dependencies) == len(set(exec_dependencies))
    required = {
        "nav2_map_server", "nav2_amcl", "nav2_planner", "nav2_controller",
        "nav2_behaviors", "nav2_bt_navigator", "nav2_lifecycle_manager",
        "nav2_costmap_2d", "nav2_navfn_planner", "nav2_dwb_controller",
        "nav2_behavior_tree",
    }
    assert required <= set(exec_dependencies)
    launch = (ROOT / "ros2_ws/src/mecanum_nav_bringup/launch/sim_eval_nav2_baseline_system.launch.py").read_text()
    nav = (ROOT / "ros2_ws/src/mecanum_nav_bringup/config/navigation/sim_eval_nav2_baseline.runtime.yaml").read_text()
    for package, executable in (
        ("nav2_map_server", "map_server"), ("nav2_amcl", "amcl"),
        ("nav2_planner", "planner_server"), ("nav2_controller", "controller_server"),
        ("nav2_behaviors", "behavior_server"), ("nav2_bt_navigator", "bt_navigator"),
        ("nav2_lifecycle_manager", "lifecycle_manager"),
    ):
        assert f'package="{package}"' in launch
        assert f'executable="{executable}"' in launch
    for plugin in ("nav2_navfn_planner::NavfnPlanner", "dwb_core::DWBLocalPlanner",
                   "nav2_costmap_2d::StaticLayer", "nav2_costmap_2d::ObstacleLayer",
                   "nav2_costmap_2d::InflationLayer"):
        assert plugin in nav or plugin in launch
