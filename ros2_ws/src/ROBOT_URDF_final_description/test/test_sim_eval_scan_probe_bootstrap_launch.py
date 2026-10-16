import ast
from pathlib import Path
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[4]
LAUNCH = ROOT / "ros2_ws/src/ROBOT_URDF_final_description/launch/sim_eval_scan_probe_bootstrap.launch.py"
PACKAGE = ROOT / "ros2_ws/src/ROBOT_URDF_final_description/package.xml"


def test_bootstrap_ast_pins_partition_before_gazebo_include_and_stays_bridge_free():
    source = LAUNCH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
    partition_calls = [
        node for node in calls
        if isinstance(node.func, ast.Name)
        and node.func.id == "SetEnvironmentVariable"
        and any(keyword.arg == "name" and isinstance(keyword.value, ast.Constant) and keyword.value.value == "GZ_PARTITION" for keyword in node.keywords)
        and any(keyword.arg == "value" and isinstance(keyword.value, ast.Name) and keyword.value.id == "GZ_PARTITION" for keyword in node.keywords)
    ]
    assert len(partition_calls) == 1
    assert source.index("set_partition = SetEnvironmentVariable") < source.index("gazebo = IncludeLaunchDescription")
    assert source.count("gz_sim.launch.py") == 1
    assert source.count('package="robot_state_publisher"') == 1
    assert source.count('package="ros_gz_sim"') == 1
    assert 'executable="create"' in source
    assert '"-name", ENTITY_NAME' in source
    assert '"-allow_renaming", "false"' in source
    for forbidden in ("ros_gz_bridge", "parameter_bridge", "/scan", "static_transform_publisher", "tf2_ros", "nav2", "amcl", "ekf", "map_server"):
        assert forbidden not in source.lower()


def test_bootstrap_is_installed_by_existing_launch_glob_and_dependencies_are_declared():
    setup_source = (ROOT / "ros2_ws/src/ROBOT_URDF_final_description/setup.py").read_text(encoding="utf-8")
    assert "glob('launch/*')" in setup_source
    dependencies = {element.text for element in ET.parse(PACKAGE).getroot().findall("exec_depend")}
    assert {"ament_index_python", "launch", "launch_ros", "ros_gz_sim"} <= dependencies
