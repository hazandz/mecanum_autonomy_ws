import ast
from pathlib import Path
import xml.etree.ElementTree as ET


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
LAUNCH_SOURCE = PACKAGE_ROOT / "launch/sim_eval_scan_probe_bootstrap.launch.py"


def _call_name(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _keyword_value(call, name):
    for keyword in call.keywords:
        if keyword.arg == name:
            return keyword.value
    return None


def test_bootstrap_has_one_gazebo_include_one_rsp_and_one_create():
    source = LAUNCH_SOURCE.read_text(encoding="utf-8")
    tree = ast.parse(source)
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
    includes = [node for node in calls if _call_name(node.func) == "IncludeLaunchDescription"]
    resource_path_actions = [
        node for node in calls if _call_name(node.func) == "SetEnvironmentVariable"
    ]
    nodes = [node for node in calls if _call_name(node.func) == "Node"]
    assert len(includes) == 1
    assert len(resource_path_actions) == 1
    assert len(nodes) == 2
    assert "gz_sim.launch.py" in source
    assert 'name="GZ_SIM_RESOURCE_PATH"' in source
    assert "package_share_parent" in source

    rsp_nodes = [
        node
        for node in nodes
        if ast.literal_eval(_keyword_value(node, "package")) == "robot_state_publisher"
        and ast.literal_eval(_keyword_value(node, "executable"))
        == "robot_state_publisher"
    ]
    create_nodes = [
        node
        for node in nodes
        if ast.literal_eval(_keyword_value(node, "package")) == "ros_gz_sim"
        and ast.literal_eval(_keyword_value(node, "executable")) == "create"
    ]
    assert len(rsp_nodes) == 1
    assert len(create_nodes) == 1
    assert "ROBOT_URDF_final.xacro" in source
    assert '"use_sim_time": False' in source
    assert '"-topic"' in source and '"/robot_description"' in source
    assert '"-name"' in source and '"ROBOT_URDF_final"' in source
    assert '"-allow_renaming"' in source and '"false"' in source


def test_bootstrap_is_bridge_free_and_has_no_other_runtime_stack():
    source = LAUNCH_SOURCE.read_text(encoding="utf-8").lower()
    for forbidden in (
        "ros_gz_bridge",
        "parameter_bridge",
        "/scan",
        "static_transform_publisher",
        "tf2_ros",
        "nav2",
        "amcl",
        "ekf",
        "map_server",
        "/cmd_vel",
        "endpoint_selection",
    ):
        assert forbidden not in source


def test_package_declares_only_bootstrap_launch_runtime_dependencies():
    package = ET.parse(PACKAGE_ROOT / "package.xml").getroot()
    dependencies = {
        element.text
        for element in package.findall("exec_depend")
        if element.text
    }
    assert {"launch", "launch_ros", "ros_gz_sim"} <= dependencies


def test_launch_install_glob_in_setup_covers_new_source_without_setup_edit():
    setup_source = (PACKAGE_ROOT / "setup.py").read_text(encoding="utf-8")
    assert "glob('launch/*')" in setup_source
