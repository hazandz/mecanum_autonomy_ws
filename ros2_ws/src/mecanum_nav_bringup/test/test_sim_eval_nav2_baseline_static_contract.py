"""Offline boundary checks for the Step-6 sim_eval baseline source."""
import json
import math
import xml.etree.ElementTree as ET
from pathlib import Path

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


def test_research_goal_checker_and_amcl_health_baseline_parse():
    nav = yaml.safe_load((ROOT / "ros2_ws/src/mecanum_nav_bringup/config/navigation/sim_eval_nav2_baseline.runtime.yaml").read_text())
    checker = nav["controller_server"]["ros__parameters"]["goal_checker"]
    assert checker == {"plugin": "nav2_controller::StoppedGoalChecker",
        "xy_goal_tolerance": 0.15, "yaw_goal_tolerance": 3.141592653589793,
        "trans_stopped_velocity": 0.03, "rot_stopped_velocity": 0.05,
        "stateful": False}
    assert "RotateToGoal" not in nav["controller_server"]["ros__parameters"]["FollowPath"]["critics"]
    amcl = yaml.safe_load((ROOT / "ros2_ws/src/mecanum_nav_bringup/config/localization/amcl_omni.yaml").read_text())["amcl"]["ros__parameters"]
    assert amcl["update_min_d"] == amcl["update_min_a"] == 0.0
    assert amcl["set_initial_pose"] is True


def test_sim_eval_dwb_translation_bound_matches_approved_axis_envelope():
    """Keep DWB's planar bound equal to the approved component envelope."""
    navigation_path = (
        ROOT / 'ros2_ws/src/mecanum_nav_bringup/config/navigation/'
        'sim_eval_nav2_baseline.runtime.yaml'
    )
    navigation = yaml.safe_load(navigation_path.read_text(encoding='utf-8'))
    follow_path = navigation['controller_server']['ros__parameters'][
        'FollowPath'
    ]
    safety_path = (
        ROOT / 'ros2_ws/src/mecanum_nav_rl/config/safety/'
        'sim_eval_nav2_baseline_safety.yaml'
    )
    safety = yaml.safe_load(safety_path.read_text(encoding='utf-8'))
    resolved_path = (
        ROOT / 'ros2_ws/src/mecanum_nav_rl/config/v3/resolved/'
        'sim_eval_nav2_baseline.resolved.json'
    )
    resolved = json.loads(resolved_path.read_text(encoding='utf-8'))

    max_speed_xy = follow_path['max_speed_xy']
    assert isinstance(max_speed_xy, (int, float))
    assert not isinstance(max_speed_xy, bool)
    assert math.isfinite(max_speed_xy) and max_speed_xy > 0.0

    max_vx = resolved['motion_limits']['max_vx_mps']
    max_vy = resolved['motion_limits']['max_vy_mps']
    assert follow_path['max_vel_x'] == max_vx
    assert max_vx == safety['limits']['velocity'][0]
    assert follow_path['max_vel_y'] == max_vy
    assert max_vy == safety['limits']['velocity'][1]
    assert follow_path['min_vel_x'] == -max_vx
    assert follow_path['min_vel_y'] == -max_vy
    assert math.isclose(
        max_speed_xy,
        math.hypot(max_vx, max_vy),
        rel_tol=0.0,
        abs_tol=1e-15,
    )


def _nav2_1_3_12_speed_is_valid(
    vx: float,
    vy: float,
    wz: float,
    max_speed_xy: float,
    min_speed_xy: float = 0.0,
    min_speed_theta: float = 0.0,
) -> bool:
    """Offline reproduction of the tagged Nav2 1.3.12 predicate."""
    float_epsilon = 1.1920928955078125e-7
    velocity_squared = vx * vx + vy * vy
    if (
        max_speed_xy >= 0.0
        and velocity_squared > max_speed_xy * max_speed_xy + float_epsilon
    ):
        return False
    if (
        min_speed_xy >= 0.0
        and velocity_squared + float_epsilon < min_speed_xy * min_speed_xy
        and min_speed_theta >= 0.0
        and abs(wz) + float_epsilon < min_speed_theta
    ):
        return False
    if velocity_squared == 0.0 and wz == 0.0:
        return False
    return True


def test_nav2_speed_predicate_default_zero_and_approved_bound():
    """Test kinematic admissibility, not collision or critic ranking."""
    bound = 0.32015621187164245
    assert not _nav2_1_3_12_speed_is_valid(0.1, 0.0, 0.0, 0.0)

    for vx, vy in (
        (0.1, 0.0),
        (-0.1, 0.0),
        (0.0, 0.1),
        (0.0, -0.1),
        (0.25, 0.20),
        (0.25, -0.20),
        (-0.25, 0.20),
        (-0.25, -0.20),
    ):
        assert _nav2_1_3_12_speed_is_valid(vx, vy, 0.0, bound)

    assert not _nav2_1_3_12_speed_is_valid(0.26, 0.20, 0.0, bound)
    assert _nav2_1_3_12_speed_is_valid(0.0, 0.0, 0.1, bound)
