from pathlib import Path
import yaml


ROOT = Path(__file__).resolve().parents[1]


def test_remaps_are_exact_static_intent_without_aliases():
    config = yaml.safe_load((ROOT / "config/remaps/navigation_v1.yaml").read_text(encoding="utf-8"))
    assert config["schema"] == "mecanum_navigation_v1_static_remaps/v1"
    assert config["profile"] == "sim_eval" and config["mode"] == "NAV2_BASELINE"
    assert config["namespace"] == "/"
    assert config["remaps"] == {
        "scan": "/scan",
        "map": "/map",
        "odom": "/odometry/filtered",
        "amcl_pose": "/amcl_pose",
        "nav2_command_output": "/cmd_vel_nav2_raw",
        "tf": "/tf",
        "tf_static": "/tf_static",
    }
    text = (ROOT / "config/remaps/navigation_v1.yaml").read_text(encoding="utf-8")
    for forbidden in ("lidar_frame", "base_scan", "rplidar_link", "RPLiDAR_A1M8_1", "/cmd_vel\n"):
        assert forbidden not in text
