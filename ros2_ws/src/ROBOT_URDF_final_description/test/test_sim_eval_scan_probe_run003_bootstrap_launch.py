"""Static Run 003 bootstrap contract tests; do not launch ROS or Gazebo."""

import ast
from pathlib import Path
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[4]
LAUNCH = ROOT / "ros2_ws/src/ROBOT_URDF_final_description/launch/sim_eval_scan_probe_run003_bootstrap.launch.py"
WORLD = ROOT / "ros2_ws/src/ROBOT_URDF_final_description/launch/sim_eval_scan_probe.world.sdf"


def _constant(tree, name):
    found = [n for n in ast.walk(tree) if isinstance(n, ast.Assign) and any(
        isinstance(target, ast.Name) and target.id == name for target in n.targets
    )]
    assert len(found) == 1
    return ast.literal_eval(found[0].value)


def test_run003_launch_pins_partition_and_world_without_runtime_extras():
    source = LAUNCH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    assert _constant(tree, "GZ_PARTITION") == "wp06_scan_probe_run_003"
    assert _constant(tree, "WORLD_NAME") == "wp06_scan_probe_world"
    assert source.count("gz_sim.launch.py") == 1
    assert source.count("package=\"robot_state_publisher\"") == 1
    assert source.count("executable=\"create\"") == 1
    assert source.count("package=\"ros_gz_sim\"") == 1
    assert '"gz_args": f"-r -s -v 4 {world_path}"' in source
    assert '"use_sim_time": True' in source
    assert '"-world", WORLD_NAME' in source
    assert '"-topic", "/robot_description"' in source
    assert '"-name", ENTITY_NAME' in source
    assert '"-allow_renaming", "false"' in source
    assert '"-x", "0.0", "-y", "0.0", "-z", "0.1", "-Y", "0.0"' in source
    set_partition_at = source.index('SetEnvironmentVariable(name="GZ_PARTITION"')
    gazebo_at = source.index("gazebo_server = IncludeLaunchDescription")
    assert set_partition_at < gazebo_at
    lowered = source.lower()
    for forbidden in (
        "ros_gz_bridge", "parameter_bridge", "/scan", "tf2_ros",
        "static_transform_publisher", "nav2", "amcl", "ekf", "map_server",
        "timeraction", "sleep(", "tugbot_depot.sdf", "gui:=",
    ):
        assert forbidden not in lowered


def test_world_is_the_existing_local_fuel_free_probe_world():
    raw = WORLD.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf")
    sdf = ET.fromstring(raw.decode("utf-8"))
    worlds = sdf.findall("world")
    assert len(worlds) == 1 and worlds[0].attrib["name"] == "wp06_scan_probe_world"
    text = raw.decode("utf-8").lower()
    for forbidden in ("<include", "<uri", "fuel.gazebosim.org", "http://", "https://"):
        assert forbidden not in text
