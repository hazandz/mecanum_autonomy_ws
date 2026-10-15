from pathlib import Path

import yaml


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
EKF_CONFIG = PACKAGE_ROOT / "config/state_estimation/ekf_sim.yaml"
EXPECTED_ODOM_CONFIG = [
    False, False, False, False, False, False, True, True, False, False, False, False, False, False, False
]
EXPECTED_IMU_CONFIG = [
    False, False, False, False, False, True, False, False, False, False, False, True, False, False, False
]


def test_sim_eval_ekf_declares_sim_time_and_exact_fifteen_state_vectors():
    document = yaml.safe_load(EKF_CONFIG.read_text(encoding="utf-8"))
    params = document["ekf_filter_node"]["ros__parameters"]

    assert params["use_sim_time"] is True
    assert params["frequency"] == 30.0
    assert params["sensor_timeout"] == 0.20
    assert params["two_d_mode"] is True
    assert params["publish_tf"] is True
    assert params["publish_acceleration"] is False
    assert params["world_frame"] == "odom"
    assert params["map_frame"] == "map"
    assert params["odom_frame"] == "odom"
    assert params["base_link_frame"] == "base_link"
    assert params["odom0"] == "/wheel/odometry_raw"
    assert params["imu0"] == "/imu/data"

    odom_config = params["odom0_config"]
    imu_config = params["imu0_config"]
    assert len(odom_config) == 15
    assert len(imu_config) == 15
    assert all(type(value) is bool for value in odom_config)
    assert all(type(value) is bool for value in imu_config)
    assert odom_config == EXPECTED_ODOM_CONFIG
    assert imu_config == EXPECTED_IMU_CONFIG

    assert params["odom0_differential"] is False
    assert params["odom0_relative"] is False
    assert params["imu0_differential"] is False
    assert params["imu0_relative"] is False
    assert params["odom0_queue_size"] == 10
    assert params["imu0_queue_size"] == 20
    assert params["odom0"] not in {"/odom", "/ground_truth/odom"}
    assert params["imu0"] not in {"/odom", "/ground_truth/odom"}
    assert not any("ground_truth" in key for key in params)
