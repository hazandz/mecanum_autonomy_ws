from pathlib import Path
import yaml


ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = ROOT.parents[2]


def test_static_target_tf_edges_have_the_declared_single_owners():
    amcl = yaml.safe_load((ROOT / "config/localization/amcl_omni.yaml").read_text())["amcl"]["ros__parameters"]
    ekf = yaml.safe_load((ROOT / "config/state_estimation/ekf_sim.yaml").read_text())["ekf_filter_node"]["ros__parameters"]
    bringup = yaml.safe_load((ROOT / "config/navigation_v1_static_bringup.template.yaml").read_text())
    assert amcl["global_frame_id"] == "map" and amcl["odom_frame_id"] == "odom" and amcl["tf_broadcast"] is True
    assert ekf["world_frame"] == "odom" and ekf["odom_frame"] == "odom" and ekf["base_link_frame"] == "base_link" and ekf["publish_tf"] is True
    assert bringup["robot_description"]["owner"] == "robot_state_publisher"
    assert bringup["robot_description"]["tf_edge"] == "base_link -> lidar_frame"
    assert bringup["localization"]["owner"] == "AMCL" and bringup["localization"]["tf_edge"] == "map -> odom"
    assert bringup["ekf"]["owner"] == "robot_localization" and bringup["ekf"]["tf_edge"] == "odom -> base_link"
