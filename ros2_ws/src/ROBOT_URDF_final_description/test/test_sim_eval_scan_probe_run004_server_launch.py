"""Offline source checks for the Run 004 server-only launch."""

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
LAUNCH = ROOT / "ros2_ws/src/ROBOT_URDF_final_description/launch/sim_eval_scan_probe_run004_server.launch.py"
WORLD = ROOT / "ros2_ws/src/ROBOT_URDF_final_description/launch/sim_eval_scan_probe.world.sdf"


def test_run004_launch_is_partition_pinned_server_only_and_does_not_spawn():
    source = LAUNCH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    constants = {
        node.targets[0].id: ast.literal_eval(node.value)
        for node in tree.body
        if isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
    }
    assert constants["GZ_PARTITION"] == "wp06_scan_probe_run_004"
    assert source.count("SetEnvironmentVariable(name=\"GZ_PARTITION\"") == 1
    assert source.count("gz_sim.launch.py") == 1
    assert source.count("package=\"robot_state_publisher\"") == 1
    assert source.count("IncludeLaunchDescription(") == 1
    assert '"use_sim_time": True' in source
    assert '"gz_args": f"-r -s -v 4 {world_path}"' in source
    assert '"sim_eval_scan_probe.world.sdf"' in source
    assert "executable=\"create\"" not in source
    assert "ros_gz_sim\",\n        executable=\"create\"" not in source
    lowered = source.lower()
    for forbidden in (
        "ros_gz_sim create", "parameter_bridge", "ros_gz_bridge", "/scan",
        "static_transform_publisher", "tf2_ros", "timeraction", "sleep(",
        "tugbot_depot.sdf", "gui:=", "http://", "https://",
    ):
        assert forbidden not in lowered


def test_run004_launch_uses_the_existing_local_probe_world():
    assert WORLD.is_file()
    text = WORLD.read_text(encoding="utf-8").lower()
    for forbidden in ("<include", "<uri", "fuel.gazebosim.org", "http://", "https://"):
        assert forbidden not in text
