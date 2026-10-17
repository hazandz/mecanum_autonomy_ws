import ast
from pathlib import Path
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[4]
LAUNCH = ROOT / "ros2_ws/src/ROBOT_URDF_final_description/launch/sim_eval_scan_probe_bootstrap.launch.py"
WORLD = ROOT / "ros2_ws/src/ROBOT_URDF_final_description/launch/sim_eval_scan_probe.world.sdf"
PACKAGE = ROOT / "ros2_ws/src/ROBOT_URDF_final_description/package.xml"
RUN002_PARTITION = "wp06_scan_probe_run_002"
WORLD_NAME = "wp06_scan_probe_world"


def _constant_assignment(tree, name):
    assignments = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == name for target in node.targets)
    ]
    assert len(assignments) == 1
    return ast.literal_eval(assignments[0].value)


def test_local_probe_world_is_fuel_free_and_has_only_required_systems():
    raw = WORLD.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf")
    root = ET.fromstring(raw.decode("utf-8"))
    assert root.tag == "sdf"
    worlds = root.findall("world")
    assert len(worlds) == 1
    world = worlds[0]
    assert world.attrib == {"name": WORLD_NAME}
    assert world.find("physics") is not None
    plugins = world.findall("plugin")
    assert [plugin.attrib["name"] for plugin in plugins] == [
        "gz::sim::systems::Physics",
        "gz::sim::systems::UserCommands",
        "gz::sim::systems::SceneBroadcaster",
        "gz::sim::systems::Sensors",
    ]
    assert [plugin.attrib["filename"] for plugin in plugins] == [
        "gz-sim-physics-system",
        "gz-sim-user-commands-system",
        "gz-sim-scene-broadcaster-system",
        "gz-sim-sensors-system",
    ]
    assert plugins[-1].findtext("render_engine") == "ogre2"
    models = world.findall("model")
    assert len(models) == 1
    assert models[0].attrib == {"name": "ground_plane"}
    assert models[0].findtext("static") == "true"
    assert models[0].find(".//geometry/plane") is not None
    assert world.find("include") is None
    assert world.find(".//uri") is None
    lowered = raw.decode("utf-8").lower()
    for forbidden in ("fuel.gazebosim.org", "http://", "https://", "<include", "<uri"):
        assert forbidden not in lowered


def test_bootstrap_pins_run002_partition_before_server_only_gazebo_include():
    source = LAUNCH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    assert _constant_assignment(tree, "GZ_PARTITION") == RUN002_PARTITION
    assert _constant_assignment(tree, "WORLD_NAME") == WORLD_NAME
    partition_calls = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "SetEnvironmentVariable"
        and any(keyword.arg == "name" and ast.literal_eval(keyword.value) == "GZ_PARTITION" for keyword in node.keywords)
        and any(keyword.arg == "value" and isinstance(keyword.value, ast.Name) and keyword.value.id == "GZ_PARTITION" for keyword in node.keywords)
    ]
    assert len(partition_calls) == 1
    assert source.index("set_partition = SetEnvironmentVariable") < source.index("gazebo = IncludeLaunchDescription")
    assert '"gz_args": f"-r -s -v 4 {world_sdf}"' in source
    assert '"sim_eval_scan_probe.world.sdf"' in source
    assert "tugbot_depot.sdf" not in source
    assert '"-world", WORLD_NAME' in source
    assert '"-topic", "/robot_description"' in source
    assert '"-name", ENTITY_NAME' in source
    assert '"-allow_renaming", "false"' in source
    assert all(f'"{value}"' in source for value in ("-x", "0.0", "-y", "-z", "0.1", "-Y"))
    assert '"use_sim_time": True' in source
    assert source.count("gz_sim.launch.py") == 1
    assert source.count('package="robot_state_publisher"') == 1
    assert source.count('package="ros_gz_sim"') == 1
    assert source.count('executable="create"') == 1
    for forbidden in (
        "ros_gz_bridge", "parameter_bridge", "/scan", "static_transform_publisher",
        "tf2_ros", "nav2", "amcl", "ekf", "map_server", "TimerAction",
        "sleep(", "-g", "gui:=", "tugbot_depot.sdf",
    ):
        assert forbidden not in source.lower()


def test_bootstrap_assets_are_installed_by_existing_launch_glob_and_dependencies_remain():
    setup_source = (ROOT / "ros2_ws/src/ROBOT_URDF_final_description/setup.py").read_text(encoding="utf-8")
    assert "glob('launch/*')" in setup_source
    dependencies = {element.text for element in ET.parse(PACKAGE).getroot().findall("exec_depend")}
    assert {"ament_index_python", "launch", "launch_ros", "ros_gz_sim"} <= dependencies
