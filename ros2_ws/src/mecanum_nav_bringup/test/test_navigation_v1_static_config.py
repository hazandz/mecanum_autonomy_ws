from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_ODOM_CONFIG = [
    False, False, False, False, False, False, True, True, False, False, False, False, False, False, False
]
EXPECTED_IMU_CONFIG = [
    False, False, False, False, False, True, False, False, False, False, False, True, False, False, False
]


def test_ekf_consumes_only_raw_wheel_odometry_and_imu_with_exact_sim_contract():
    config = yaml.safe_load(
        (ROOT / "config/state_estimation/ekf_sim.yaml").read_text(encoding="utf-8")
    )["ekf_filter_node"]["ros__parameters"]
    assert config["use_sim_time"] is True
    assert config["frequency"] == 30.0
    assert config["sensor_timeout"] == 0.20
    assert config["two_d_mode"] is True
    assert config["publish_tf"] is True
    assert config["publish_acceleration"] is False
    assert config["map_frame"] == "map"
    assert config["odom_frame"] == "odom"
    assert config["base_link_frame"] == "base_link"
    assert config["world_frame"] == "odom"
    assert config["odom0"] == "/wheel/odometry_raw"
    assert config["imu0"] == "/imu/data"

    odom0_config = config["odom0_config"]
    imu0_config = config["imu0_config"]
    assert len(odom0_config) == 15
    assert len(imu0_config) == 15
    assert all(type(value) is bool for value in odom0_config)
    assert all(type(value) is bool for value in imu0_config)
    assert odom0_config == EXPECTED_ODOM_CONFIG
    assert imu0_config == EXPECTED_IMU_CONFIG

    assert config["odom0_differential"] is False
    assert config["odom0_relative"] is False
    assert config["imu0_differential"] is False
    assert config["imu0_relative"] is False
    assert config["odom0_queue_size"] == 10
    assert config["imu0_queue_size"] == 20
    assert config["odom0"] not in {"/odom", "/ground_truth/odom"}
    assert config["imu0"] not in {"/odom", "/ground_truth/odom"}
    configured_inputs = {value for key, value in config.items() if key in {"odom0", "imu0"}}
    assert configured_inputs == {"/wheel/odometry_raw", "/imu/data"}
    assert not any("ground_truth" in key for key in config)


def test_amcl_uses_omni_model_and_canonical_scan_binding():
    path = ROOT / "config/localization/amcl_omni.yaml"
    config = yaml.safe_load(path.read_text(encoding="utf-8"))["amcl"]["ros__parameters"]
    text = path.read_text(encoding="utf-8")
    assert config["use_sim_time"] is True
    assert config["global_frame_id"] == "map"
    assert config["odom_frame_id"] == "odom"
    assert config["base_frame_id"] == "base_link"
    assert config["robot_model_type"] == "nav2_amcl::OmniMotionModel"
    assert config["scan_topic"] == "/scan"
    assert config["map_topic"] == "/map"
    assert config["laser_min_range"] == -1.0 and config["laser_max_range"] == -1.0
    assert "header_frame_id: lidar_frame" in text
    assert "base_scan" not in text and "RPLiDAR_A1M8_1" not in text
    assert "initial_pose" not in config


def test_nav2_baseline_static_values_and_simulation_time():
    config = yaml.safe_load(
        (ROOT / "config/navigation/nav2_baseline.yaml").read_text(encoding="utf-8")
    )
    assert all(
        node["ros__parameters"]["use_sim_time"] is True
        for node in (
            config["map_server"], config["planner_server"],
            config["controller_server"], config["bt_navigator"],
        )
    )
    planner = config["planner_server"]["ros__parameters"]["GridBased"]
    assert planner == {
        "plugin": "nav2_navfn_planner::NavfnPlanner",
        "allow_unknown": False,
        "tolerance": 0.20,
    }
    controller = config["controller_server"]["ros__parameters"]["FollowPath"]
    assert controller["plugin"] == "dwb_core::DWBLocalPlanner"
    assert controller["min_vel_y"] < 0 < controller["max_vel_y"]
    assert controller["vy_samples"] > 1
    assert controller["critics"] == [
        "RotateToGoal", "Oscillation", "BaseObstacle", "GoalAlign",
        "PathAlign", "PathDist", "GoalDist",
    ]
    assert "PreferForwardCritic" not in str(controller)
    assert controller["decel_lim_x"] == -controller["acc_lim_x"]
    assert controller["decel_lim_y"] == -controller["acc_lim_y"]
    assert controller["decel_lim_theta"] == -controller["acc_lim_theta"]
    assert config["bt_navigator"]["ros__parameters"]["odom_topic"] == "/odometry/filtered"
    for costmap_name, wrapper in (
        ("global_costmap", "global_costmap"),
        ("local_costmap", "local_costmap"),
    ):
        params = config[costmap_name][wrapper]["ros__parameters"]
        assert params["use_sim_time"] is True
        assert params["footprint"] == "[[0.20, 0.14], [0.20, -0.14], [-0.20, -0.14], [-0.20, 0.14]]"
        assert params["obstacle_layer"]["scan"]["topic"] == "/scan"
        assert params["obstacle_layer"]["scan"]["data_type"] == "LaserScan"
        assert params["obstacle_layer"]["scan"]["obstacle_min_range"] == 0.10
        assert params["obstacle_layer"]["scan"]["obstacle_max_range"] == 3.0
        assert params["obstacle_layer"]["scan"]["raytrace_max_range"] == 3.5
        assert params["inflation_layer"]["inflation_radius"] == 0.30
        assert params["inflation_layer"]["cost_scaling_factor"] == 3.0
