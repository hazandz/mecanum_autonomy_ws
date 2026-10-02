#!/usr/bin/env python3
"""Fail-closed static contract checks for the rendered ECS diagnostic route."""
from __future__ import annotations

import argparse
import ast
import os
import re
import stat
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "launch" / "native_sdf_ecs_contact_diagnostic_world_template.sdf.in"
LAUNCH = ROOT / "launch" / "native_sdf_ecs_contact_diagnostic_rendered.launch.py"
TOKENS = (
    "RECEIPT_TOPIC", "RUN_ID", "WORLD_NAME", "MODEL_NAME", "LINK_NAME", "SENSOR_NAME",
    "PLUGIN_SOURCE_SHA256", "PLUGIN_BINARY_SHA256", "COLLECTOR_SOURCE_SHA256",
    "COLLECTOR_BINARY_SHA256", "BASE_WORLD_TEMPLATE_SHA256", "NATIVE_MODEL_SHA256",
    "SYSTEM_WAIT_TIMEOUT_SIM_TIME_NS", "SYSTEM_DELIVERY_WAIT_TIMEOUT_STEADY_NS",
    "COLLECTOR_RECEIPT_WAIT_TIMEOUT_STEADY_NS", "COLLECTOR_PERSIST_TIMEOUT_STEADY_NS",
    "PLUGIN_ALIAS",
)
REQUIRED_KEYS = tuple(f"{{{{S3D3_{key}}}}}" for key in TOKENS)
FORBIDDEN = ("robot_state_publisher", "robot_description", "ros_gz_bridge", "parameter_bridge",
             "/cmd_vel", "teleop", "nav2", "ppo", "gym", "touchplugin", "static_transform",
             "world_control", "set_entity_pose", "delete_entity")


def require(value: bool, reason: str) -> None:
    if not value:
        raise ValueError(reason)


def name(call: ast.Call) -> str | None:
    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return None


def constants(tree: ast.AST) -> list[str]:
    return [node.value.lower() for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)]


def check_world(path: Path = TEMPLATE) -> None:
    data = path.read_text(encoding="utf-8")
    require("${" not in data and "$(" not in data, "environment or shell substitution is prohibited")
    for token in REQUIRED_KEYS:
        require(data.count(token) == 1, f"token cardinality wrong: {token}")
    require("{{S3D3_".encode().decode() in data, "template has no tokens")
    unknown = re.findall(r"\{\{S3D3_[A-Z0-9_]+\}\}", data)
    require(set(unknown) == set(REQUIRED_KEYS), "unknown template token")
    root = ET.fromstring(data)
    require(root.tag == "sdf" and root.attrib.get("version") == "1.11", "wrong SDF root")
    worlds = root.findall("world")
    require(len(worlds) == 1 and worlds[0].attrib.get("name") == "world_demo", "wrong world identity")
    world = worlds[0]
    require(not world.findall("model") and not world.findall("include"), "world may not include or spawn a robot")
    plugins = world.findall("plugin")
    require(len(plugins) == 3, "expected only Physics, Contact, and one diagnostic System")
    contract = {(p.attrib.get("filename"), p.attrib.get("name")): p for p in plugins}
    require(len(contract) == 3, "duplicate System plugin is prohibited")
    require(("gz-sim-physics-system", "gz::sim::systems::Physics") in contract, "physics System missing")
    require(("gz-sim-contact-system", "gz::sim::systems::Contact") in contract, "exactly one Contact System required")
    require(("gz-sim-sensors-system", "gz::sim::systems::Sensors") not in contract,
            "Sensors System is prohibited: Contact owns ContactSensor lifecycle")
    require(not any(p.attrib.get("filename") == "gz-sim-sensors-system" or
                    p.attrib.get("name") == "gz::sim::systems::Sensors" for p in plugins),
            "Sensors System / render-engine configuration is outside this route")
    diagnostic = contract.get(("S3D3EcsContactSensorDiagnosticSystem", "{{S3D3_PLUGIN_ALIAS}}"))
    require(diagnostic is not None, "exactly one world-scope diagnostic System required")
    children = list(diagnostic)
    require(len(children) == len(REQUIRED_KEYS) - 1, "missing or duplicate immutable plugin configuration")
    seen = {child.tag: child.text for child in children}
    expected = {token.removeprefix("{{S3D3_").removesuffix("}}").lower(): token
                for token in REQUIRED_KEYS if token != "{{S3D3_PLUGIN_ALIAS}}"}
    require(seen == expected, "plugin config key/token contract mismatch")
    lowered = data.lower()
    require(not any(value in lowered for value in FORBIDDEN), "forbidden runtime/control literal in template")
    require(re.search(r"<(?:pause|step)>", lowered) is None, "world-control element in template")


def check_launch(path: Path = LAUNCH) -> None:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, str(path))
    words = constants(tree)
    require(not any(any(token in word for word in words) for token in FORBIDDEN), "forbidden literal in launch")
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
    names = [name(call) for call in calls]
    forbidden = {"Node", "TimerAction", "ExecuteProcess", "OpaqueFunction", "GroupAction", "Popen", "run", "system"}
    require(not any(value in forbidden for value in names), "forbidden process/action constructor")
    function = next((node for node in tree.body if isinstance(node, ast.FunctionDef)
                     and node.name == "generate_launch_description"), None)
    require(function is not None, "missing launch function")
    return_calls = [node.value for node in function.body if isinstance(node, ast.Return)]
    require(len(return_calls) == 1 and isinstance(return_calls[0], ast.Call) and name(return_calls[0]) == "LaunchDescription", "wrong launch return")
    values = return_calls[0].args[0]
    require(isinstance(values, ast.List), "launch actions must be a literal list")
    action_names = [elt.id for elt in values.elts if isinstance(elt, ast.Name)]
    require(action_names == ["require_rendered_world", "set_resource_path", "set_plugin_path", "gazebo"], "wrong dedicated launch graph")
    require(source.count('DeclareLaunchArgument(') == 1 and '"rendered_world"' in source, "one required rendered-world argument")
    require("default_value" not in source, "rendered-world argument may not have a fallback")
    require(source.count("SetEnvironmentVariable(") == 2, "must set only resource and plugin paths")
    require("GZ_SIM_RESOURCE_PATH" in source and "GZ_SIM_SYSTEM_PLUGIN_PATH" in source, "required Gazebo paths missing")
    require("get_package_prefix(\"s3_d3_ecs_contact_diagnostic\")" in source, "plugin prefix must be package-installed")
    require("gz_sim.launch.py" in source and "rendered_world" in source, "official include / exact rendered world missing")


def write_rendered_fixture(path: Path) -> None:
    data = TEMPLATE.read_text(encoding="utf-8")
    values = {
        "RECEIPT_TOPIC": "/s3_d3/diagnostic/receipt", "RUN_ID": "run_fixture", "WORLD_NAME": "world_demo",
        "MODEL_NAME": "ROBOT_URDF_final", "LINK_NAME": "base_link", "SENSOR_NAME": "s3_d3_base_contact_sensor",
        "PLUGIN_SOURCE_SHA256": "a" * 64, "PLUGIN_BINARY_SHA256": "b" * 64,
        "COLLECTOR_SOURCE_SHA256": "c" * 64, "COLLECTOR_BINARY_SHA256": "d" * 64,
        "BASE_WORLD_TEMPLATE_SHA256": "e" * 64, "NATIVE_MODEL_SHA256": "f" * 64,
        "SYSTEM_WAIT_TIMEOUT_SIM_TIME_NS": "1", "SYSTEM_DELIVERY_WAIT_TIMEOUT_STEADY_NS": "2",
        "COLLECTOR_RECEIPT_WAIT_TIMEOUT_STEADY_NS": "3", "COLLECTOR_PERSIST_TIMEOUT_STEADY_NS": "4",
        "PLUGIN_ALIAS": "s3_d3::ecs_contact::ContactSensorDiagnosticSystem",
    }
    for key, value in values.items():
        data = data.replace("{{S3D3_" + key + "}}", value)
    ET.fromstring(data)
    path.write_text(data, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--negative-fixtures", action="store_true")
    parser.add_argument("--write-rendered-fixture", type=Path)
    args = parser.parse_args()
    check_world(); check_launch()
    if args.negative_fixtures:
        original = TEMPLATE.read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as temporary:
            probe = Path(temporary) / "world.sdf.in"
            for bad in (original.replace("{{S3D3_RUN_ID}}", "", 1),
                        original.replace("{{S3D3_RUN_ID}}", "{{S3D3_UNKNOWN}}", 1),
                        original.replace("gz-sim-contact-system", "duplicate", 1),
                        original.replace("</world>", "<plugin filename=\"gz-sim-sensors-system\" name=\"gz::sim::systems::Sensors\"><render_engine>ogre2</render_engine></plugin></world>", 1),
                        original.replace("</world>", "<model name=\"ROBOT_URDF_final\"/></world>", 1)):
                probe.write_text(bad, encoding="utf-8")
                try:
                    check_world(probe)
                except ValueError:
                    continue
                raise AssertionError("negative world fixture unexpectedly passed")
    if args.write_rendered_fixture:
        write_rendered_fixture(args.write_rendered_fixture)
    print("native ECS diagnostic integration static contract: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
