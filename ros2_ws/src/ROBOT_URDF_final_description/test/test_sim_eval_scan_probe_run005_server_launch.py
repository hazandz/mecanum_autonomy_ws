"""Offline source boundary checks for the Run 005 server-only launch."""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
LAUNCH = ROOT / "ros2_ws/src/ROBOT_URDF_final_description/launch/sim_eval_scan_probe_run005_server.launch.py"

def test_run005_launch_is_server_only_and_partition_pinned():
    source = LAUNCH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    constants = {node.targets[0].id: ast.literal_eval(node.value) for node in tree.body
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)}
    assert constants["GZ_PARTITION"] == "wp06_scan_probe_run_005"
    assert source.count("SetEnvironmentVariable(name=\"GZ_PARTITION\"") == 1
    assert source.count("gz_sim.launch.py") == 1
    assert source.count("package=\"robot_state_publisher\"") == 1
    assert '"use_sim_time": True' in source
    assert '"gz_args": f"-r -s -v 4 {world_path}"' in source
    assert '"sim_eval_scan_probe.world.sdf"' in source
    assert "IncludeLaunchDescription(" in source
    forbidden = ("ros_gz_sim create", "executable=\"create\"", "ros_gz_bridge", "parameter_bridge",
        "/scan", "probe_scan_endpoint", "static_transform_publisher", "tf2_ros", "gui:=", "-g ",
        "http://", "https://", "tugbot_depot.sdf")
    assert not any(token in source.lower() for token in forbidden)
    assert "spawn" not in source.lower()
