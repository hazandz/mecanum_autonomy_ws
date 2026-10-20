"""Static partition and topology contract checks; no launch process is created."""

import ast
import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[4]
SOURCE = ROOT / "ros2_ws/src/mecanum_nav_bringup/launch/sim_eval_tf_ekf_state_estimation.launch.py"
SPEC = importlib.util.spec_from_file_location("sim_eval_tf_ekf_state_estimation", SOURCE)
LAUNCH_MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(LAUNCH_MODULE)


def test_composite_launch_only_composes_ingress_clock_and_one_ekf():
    text = SOURCE.read_text(encoding="utf-8")
    tree = ast.parse(text)
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
    nodes = [call for call in calls if isinstance(call.func, ast.Name) and call.func.id == "Node"]
    includes = [call for call in calls if isinstance(call.func, ast.Name) and call.func.id == "IncludeLaunchDescription"]
    assert len(nodes) == 2
    assert len(includes) == 1
    node_packages = []
    node_executables = []
    for node in nodes:
        keywords = {item.arg: item.value for item in node.keywords}
        node_packages.append(ast.literal_eval(keywords["package"]))
        node_executables.append(ast.literal_eval(keywords["executable"]))
    assert sorted(zip(node_packages, node_executables)) == sorted([
        ("ros_gz_bridge", "parameter_bridge"),
        ("robot_localization", "ekf_node"),
    ])
    assert "mecanum_base_bridge" in text
    assert "sim_eval_wheel_imu_ingress.launch.py" in text
    assert "EXPECTED_PARTITION" not in text
    assert "wp06_scan_probe_run_002" not in text
    assert 'DeclareLaunchArgument("use_sim_time", default_value="true")' in text
    assert 'DeclareLaunchArgument("gz_partition")' in text
    assert "SetEnvironmentVariable(\"GZ_PARTITION\", partition)" in text
    assert "raise RuntimeError(\"SIM_EVAL_GZ_PARTITION_REQUIRED\")" in text
    for forbidden in (
        "robot_state_publisher", "gazebo.launch.py", "bootstrap.launch.py", "nav2", "amcl",
        "slam", "map_server", "static_transform_publisher", "cmd_vel", "tf2_ros",
    ):
        assert forbidden not in text.lower()


def test_partition_validation_rejects_missing_and_blank_values():
    for value in (None, "", "   ", "\t\n"):
        with pytest.raises(RuntimeError, match="SIM_EVAL_GZ_PARTITION_REQUIRED"):
            LAUNCH_MODULE._require_partition(value)


def test_arbitrary_caller_partition_is_preserved_for_environment_and_ingress():
    supplied = "campaign_partition_owned_by_caller"
    assert LAUNCH_MODULE._require_partition(supplied) == supplied

    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
    env_calls = [
        call for call in calls
        if isinstance(call.func, ast.Name) and call.func.id == "SetEnvironmentVariable"
    ]
    assert len(env_calls) == 1
    assert ast.literal_eval(env_calls[0].args[0]) == "GZ_PARTITION"
    assert isinstance(env_calls[0].args[1], ast.Name)
    assert env_calls[0].args[1].id == "partition"

    ingress_arguments = [
        item
        for call in calls
        if isinstance(call.func, ast.Name) and call.func.id == "IncludeLaunchDescription"
        for keyword in call.keywords
        if keyword.arg == "launch_arguments"
        for item in ast.walk(keyword.value)
        if isinstance(item, ast.Dict)
    ]
    assert len(ingress_arguments) == 1
    forwarded = {
        key.value: value
        for key, value in zip(ingress_arguments[0].keys, ingress_arguments[0].values)
    }
    assert isinstance(forwarded["gz_partition"], ast.Name)
    assert forwarded["gz_partition"].id == "partition"
    assert isinstance(forwarded["use_sim_time"], ast.Constant)
    assert forwarded["use_sim_time"].value == "true"


def test_launch_uses_installed_configs_and_forces_sim_time_for_both_nodes():
    text = SOURCE.read_text(encoding="utf-8")
    assert '"sim_eval_clock.runtime.yaml"' in text
    assert '"ekf_sim.yaml"' in text
    assert '"use_sim_time": True' in text
    assert '"use_sim_time": "true"' in text
