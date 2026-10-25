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
    with pytest.raises(RuntimeError, match="SIM_EVAL_REQUIRES_USE_SIM_TIME_TRUE"):
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


def _composite_module():
    import importlib.util
    path = ROOT / "ros2_ws/src/mecanum_nav_bringup/launch/sim_eval_nav2_baseline_system.launch.py"
    spec = importlib.util.spec_from_file_location("composite_lifecycle_contract", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_lifecycle_topology_real_launch_events_configure_then_activate_only():
    from launch import LaunchContext
    from launch.actions import RegisterEventHandler
    from launch.events.process import ProcessStarted
    from launch_ros.actions import LifecycleNode
    from launch_ros.events.lifecycle import StateTransition
    from lifecycle_msgs.msg import Transition, TransitionEvent
    m = _composite_module()
    configure, activate, node = m.safety_lifecycle_actions()
    assert isinstance(node, LifecycleNode)
    assert isinstance(configure, RegisterEventHandler) and isinstance(activate, RegisterEventHandler)
    assert configure.event_handler.handle_once and activate.event_handler.handle_once
    context = LaunchContext()
    configure.execute(context); activate.execute(context)
    start = ProcessStarted(action=node, name="safety_lifecycle", cmd=[], cwd=None, env={}, pid=12345)
    assert configure.event_handler.matches(start)
    events = configure.event_handler.handle(start, context)
    assert [action.event.transition_id for action in events] == [Transition.TRANSITION_CONFIGURE]
    msg = TransitionEvent(); msg.start_state.label="configuring"; msg.goal_state.label="inactive"
    inactive = StateTransition(action=node, msg=msg)
    assert activate.event_handler.matches(inactive)
    assert [action.event.transition_id for action in activate.event_handler.handle(inactive, context)] == [Transition.TRANSITION_ACTIVATE]
    msg.goal_state.label="active"
    assert not activate.event_handler.matches(StateTransition(action=node, msg=msg))
    policy = ROOT / "ros2_ws/src/mecanum_nav_bringup/config/lifecycle/sim_eval_nav2_baseline.runtime.yaml"
    params = m.lifecycle_manager_parameters(policy)
    assert params["node_names"] == ["map_server", "amcl", "planner_server", "controller_server", "behavior_server", "bt_navigator"]
    assert params["autostart"] is True and params["bond_timeout"] > 0
    assert "safety_lifecycle" not in params["node_names"]


def test_actual_node_parameter_files_parse_with_jazzy_c_parser_without_ros_graph(monkeypatch, tmp_path):
    import ctypes as C
    import yaml
    from launch import LaunchContext
    from launch_ros.actions import Node
    from launch_ros.utilities import evaluate_parameters
    m = _composite_module()
    description = tmp_path / "description"; (description / "launch").mkdir(parents=True)
    (description / "launch/sim_eval_nav2_baseline_bootstrap.launch.py").write_text("def validate_fuel_cache(*args): pass\n")
    shares = {"ROBOT_URDF_final_description": description,
              "mecanum_nav_bringup": ROOT / "ros2_ws/src/mecanum_nav_bringup",
              "mecanum_nav_rl": ROOT / "ros2_ws/src/mecanum_nav_rl"}
    monkeypatch.setattr(m, "get_package_share_directory", lambda name: str(shares[name]))
    context = LaunchContext()
    context.launch_configurations.update({"gz_partition":"fixture_partition", "start_bootstrap":"false",
        "canonical_map_root":str(ROOT / "artifacts/maps/warehouse_map2"), "fuel_cache_root":"/unused",
        "sim_estop_release_authorized":"false", "initial_pose_map_x":"0.0",
        "initial_pose_map_y":"0.0", "initial_pose_map_yaw":"0.0"})
    actions = m._actions(context)
    import importlib.util
    child_path = shares["mecanum_nav_bringup"] / "launch/sim_eval_tf_ekf_state_estimation.launch.py"
    spec = importlib.util.spec_from_file_location("composite_child_parameter_parser", child_path)
    child = importlib.util.module_from_spec(spec); spec.loader.exec_module(child)
    monkeypatch.setattr(child, "get_package_share_directory", lambda _: str(ROOT / "ros2_ws/src/mecanum_base_bridge"))
    monkeypatch.setattr(child, "EKF_CONFIG", str(shares["mecanum_nav_bringup"] / "config/state_estimation/ekf_sim.yaml"))
    monkeypatch.setattr(child, "CLOCK_CONFIG", str(shares["mecanum_nav_bringup"] / "config/bridge/sim_eval_clock.runtime.yaml"))
    context.launch_configurations["use_sim_time"] = "true"
    actions += child._create_runtime_actions(context)
    class Allocator(C.Structure):
        _fields_ = [(name, C.c_void_p) for name in ("allocate", "deallocate", "reallocate", "zero_allocate", "state")]
    rc = C.CDLL("librcutils.so"); rc.rcutils_get_default_allocator.restype=Allocator
    parser = C.CDLL("librcl_yaml_param_parser.so")
    parser.rcl_yaml_node_struct_init.argtypes=[Allocator]; parser.rcl_yaml_node_struct_init.restype=C.c_void_p
    parser.rcl_parse_yaml_file.argtypes=[C.c_char_p,C.c_void_p]; parser.rcl_parse_yaml_file.restype=C.c_bool
    parser.rcl_yaml_node_struct_fini.argtypes=[C.c_void_p]
    checked = set()
    for index, action in enumerate(actions):
        if not isinstance(action, Node): continue
        values = evaluate_parameters(context, action._Node__parameters)
        for subindex, value in enumerate(values):
            if isinstance(value, dict):
                target=tmp_path / f"params-{index}-{subindex}.yaml"
                target.write_text(yaml.safe_dump({"/**":{"ros__parameters":value}}))
            else:
                target=Path(value); checked.add(target)
            handle=parser.rcl_yaml_node_struct_init(rc.rcutils_get_default_allocator())
            assert handle
            try: assert parser.rcl_parse_yaml_file(str(target).encode(),handle), str(target)
            finally: parser.rcl_yaml_node_struct_fini(handle)
    assert checked == {
        shares["mecanum_nav_bringup"] / "config/localization/amcl_omni.yaml",
        shares["mecanum_nav_bringup"] / "config/navigation/sim_eval_nav2_baseline.runtime.yaml",
        shares["mecanum_nav_bringup"] / "config/state_estimation/ekf_sim.yaml",
    }
    assert shares["mecanum_nav_bringup"] / "config/lifecycle/sim_eval_nav2_baseline.runtime.yaml" not in checked


def test_amcl_initial_pose_launch_parameters_are_always_floats(monkeypatch):
    from launch import LaunchContext
    from launch_ros.actions import Node
    from launch_ros.utilities import evaluate_parameters

    module = _composite_module()
    description = Path('/tmp/step07-launch-description')
    shares = {
        'ROBOT_URDF_final_description': description,
        'mecanum_nav_bringup': ROOT / 'ros2_ws/src/mecanum_nav_bringup',
        'mecanum_nav_rl': ROOT / 'ros2_ws/src/mecanum_nav_rl',
    }
    monkeypatch.setattr(module, 'get_package_share_directory', lambda name: str(shares[name]))

    # Replace only the Fuel preflight module lookup; keep production _actions,
    # LaunchContext, LaunchConfiguration and launch_ros parameter evaluation.
    class BootstrapModule:
        @staticmethod
        def validate_fuel_cache(*_args):
            return None

    class Loader:
        @staticmethod
        def exec_module(_module):
            return None

    class BootstrapSpec:
        loader = Loader()

    monkeypatch.setattr(module.importlib.util, 'spec_from_file_location',
                        lambda *_args: BootstrapSpec())
    monkeypatch.setattr(module.importlib.util, 'module_from_spec',
                        lambda _spec: BootstrapModule())

    cases = (
        ('0', '0.0', '-1.25'),
        ('0.375', '-2', '1.5707963'),
    )
    for pose in cases:
        context = LaunchContext()
        context.launch_configurations.update({
            'gz_partition': 'offline_launch_test',
            'start_bootstrap': 'false',
            'canonical_map_root': str(ROOT / 'artifacts/maps/warehouse_map2'),
            'fuel_cache_root': '/unused/offline-test',
            'sim_estop_release_authorized': 'false',
            'initial_pose_map_x': pose[0],
            'initial_pose_map_y': pose[1],
            'initial_pose_map_yaw': pose[2],
        })
        actions = module._actions(context)
        amcl = next(action for action in actions
                    if isinstance(action, Node)
                    and action.node_package == 'nav2_amcl'
                    and action.node_executable == 'amcl')
        evaluated = evaluate_parameters(context, amcl._Node__parameters)
        values = next(item for item in evaluated if isinstance(item, dict))
        keys = ('initial_pose.x', 'initial_pose.y', 'initial_pose.yaw')
        for key, raw in zip(keys, pose):
            assert type(values[key]) is float
            assert values[key] == float(raw)
