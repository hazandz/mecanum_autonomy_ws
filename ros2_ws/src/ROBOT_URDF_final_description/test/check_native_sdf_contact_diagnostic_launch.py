#!/usr/bin/env python3
"""Fail-closed AST validation for the native-SDF world-only diagnostic launch."""

from __future__ import annotations

import argparse
import ast
import hashlib
import os
import stat
import sys
from pathlib import Path


PACKAGE_NAME = "ROBOT_URDF_final_description"
WORLD_FILENAME = "tugbot_depot.sdf"
RESOURCE_VARIABLE = "GZ_SIM_RESOURCE_PATH"
LAUNCH_FILENAME = "native_sdf_contact_diagnostic.launch.py"
PACKAGE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LAUNCH = PACKAGE_ROOT / "launch" / LAUNCH_FILENAME

FORBIDDEN_LITERALS = (
    "robot_state_publisher",
    "robot_description",
    "ros_gz_bridge",
    "parameter_bridge",
    "static_transform_publisher",
    "/cmd_vel",
    "teleop",
    "nav2",
    "ppo",
    "gym",
    "collector",
    "control",
    "service",
    "action",
    "world_control",
    "set_entity_pose",
    "TimerAction",
    "respawn",
    "retry",
    "tugbot_depot.sdf".replace(".sdf", "_source.sdf"),
)
FORBIDDEN_CONSTRUCTORS = {
    "Node",
    "TimerAction",
    "ExecuteProcess",
    "OpaqueFunction",
    "GroupAction",
    "EmitEvent",
    "RegisterEventHandler",
    "OnProcessExit",
    "OnProcessStart",
}
ALLOWED_CONSTRUCTORS = {
    "LaunchDescription",
    "SetEnvironmentVariable",
    "IncludeLaunchDescription",
    "PythonLaunchDescriptionSource",
}


class ValidationError(ValueError):
    """The static native-world launch contract was not met."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def call_name(call: ast.Call) -> str | None:
    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return None


def keyword(call: ast.Call, name: str) -> ast.AST | None:
    return next((item.value for item in call.keywords if item.arg == name), None)


def constant(node: ast.AST | None) -> object | None:
    return node.value if isinstance(node, ast.Constant) else None


def function(tree: ast.Module) -> ast.FunctionDef:
    matches = [node for node in tree.body if isinstance(node, ast.FunctionDef)
               and node.name == "generate_launch_description"]
    require(len(matches) == 1, "expected exactly one generate_launch_description")
    return matches[0]


def assignment(func: ast.FunctionDef, name: str) -> ast.AST:
    matches = [node.value for node in func.body if isinstance(node, ast.Assign)
               for target in node.targets if isinstance(target, ast.Name)
               and target.id == name]
    require(len(matches) == 1, f"expected one assignment to {name}, found {len(matches)}")
    return matches[0]


def require_call(value: ast.AST, name: str, label: str) -> ast.Call:
    require(isinstance(value, ast.Call) and call_name(value) == name,
            f"{label} must be {name}(...)" )
    return value


def text_constants(tree: ast.AST) -> list[str]:
    return [node.value.lower() for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)]


def validate_source(source: str, filename: str = str(DEFAULT_LAUNCH)) -> None:
    tree = ast.parse(source, filename=filename)
    constants = text_constants(tree)
    # Package `ros_gz_sim` and the word `create` legitimately occur in the
    # official include and explanatory docstring. Process creation is instead
    # rejected structurally below through constructor and Node checks.
    prohibited = [literal for literal in FORBIDDEN_LITERALS
                  if any(literal.lower() in value for value in constants)]
    require(not prohibited, f"forbidden literal(s): {prohibited}")

    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
    names = [call_name(call) for call in calls]
    prohibited_calls = [name for name in names if name in FORBIDDEN_CONSTRUCTORS]
    require(not prohibited_calls, f"forbidden launch constructor(s): {prohibited_calls}")
    unknown_action_calls = [name for name in names if name and name.endswith("Action")
                            and name not in ALLOWED_CONSTRUCTORS]
    require(not unknown_action_calls, f"unexpected launch action(s): {unknown_action_calls}")
    require("Popen" not in names and "run" not in names and "system" not in names,
            "subprocess or shell API is prohibited")

    func = function(tree)
    imports = [node for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom))]
    import_text = ast.unparse(ast.Module(body=imports, type_ignores=[]))
    for forbidden in ("launch_ros", "xacro", "subprocess", "shlex"):
        require(forbidden not in import_text, f"forbidden import: {forbidden}")

    package_share_calls = [call for call in calls if call_name(call) == "get_package_share_directory"]
    package_values = [constant(call.args[0]) for call in package_share_calls if call.args]
    require(package_values.count("ros_gz_sim") == 1,
            "must resolve ros_gz_sim package share exactly once")
    require(package_values.count(PACKAGE_NAME) == 1,
            "must resolve robot package share exactly once")

    world_value = ast.unparse(assignment(func, "world_file_path"))
    require("pkg_robot" in world_value and repr("launch") in world_value
            and repr(WORLD_FILENAME) in world_value,
            "world must be the installed package launch/tugbot_depot.sdf")

    parent_value = ast.unparse(assignment(func, "package_share_parent"))
    require(parent_value == "os.path.dirname(pkg_robot)",
            "resource root must be the portable parent of package share")
    inherited_value = ast.unparse(assignment(func, "inherited_resource_path"))
    require("os.environ.get('GZ_SIM_RESOURCE_PATH', '')" == inherited_value
            or 'os.environ.get("GZ_SIM_RESOURCE_PATH", "")' == inherited_value,
            "must preserve inherited GZ_SIM_RESOURCE_PATH")

    resource_value = ast.unparse(assignment(func, "resource_path"))
    require(resource_value == "package_share_parent",
            "resource path must begin with package-share parent")
    if_nodes = [node for node in func.body if isinstance(node, ast.If)]
    require(len(if_nodes) == 1, "expected exactly one inherited-resource conditional")
    if_text = ast.unparse(if_nodes[0])
    require("inherited_resource_path" in if_text and "os.pathsep.join" in if_text
            and "package_share_parent" in if_text,
            "inherited resource path must append portably")
    require("/home/" not in ast.unparse(func), "source-tree or absolute home path is prohibited")

    resource_call = require_call(assignment(func, "set_resource_path"),
                                 "SetEnvironmentVariable", "set_resource_path")
    require(constant(keyword(resource_call, "name")) == RESOURCE_VARIABLE,
            "wrong resource variable")
    require(isinstance(keyword(resource_call, "value"), ast.Name)
            and keyword(resource_call, "value").id == "resource_path",
            "resource value must be the portable resource_path")

    gazebo = require_call(assignment(func, "gazebo"), "IncludeLaunchDescription", "gazebo")
    include_text = ast.unparse(gazebo)
    require("PythonLaunchDescriptionSource" in include_text
            and repr("gz_sim.launch.py") in include_text
            and "pkg_ros_gz_sim" in include_text,
            "must include only official ros_gz_sim/gz_sim.launch.py")
    require("gz_args" in include_text and "world_file_path" in include_text,
            "Gazebo include must receive locked world gz_args")

    returns = [node for node in func.body if isinstance(node, ast.Return)]
    require(len(returns) == 1, "expected exactly one return")
    returned = require_call(returns[0].value, "LaunchDescription", "return")
    require(len(returned.args) == 1 and isinstance(returned.args[0], ast.List),
            "LaunchDescription requires one literal action list")
    action_names = [item.id if isinstance(item, ast.Name) else None
                    for item in returned.args[0].elts]
    require(action_names == ["set_resource_path", "gazebo"],
            "launch graph must be exactly set_resource_path -> gazebo")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_install_parity(source: Path, installed: Path) -> str:
    try:
        source_mode = source.lstat().st_mode
        installed_mode = installed.lstat().st_mode
    except FileNotFoundError as exc:
        raise ValidationError(f"missing launch file: {exc.filename}") from exc
    require(stat.S_ISREG(source_mode), "source launch must be a regular file")
    if stat.S_ISLNK(installed_mode):
        resolved = installed.resolve(strict=True)
        require(resolved == source.resolve(strict=True),
                "installed launch symlink must resolve to the source launch")
    else:
        require(stat.S_ISREG(installed_mode), "installed launch must be regular or source symlink")
    require(sha256(source) == sha256(installed), "source/install launch SHA-256 mismatch")
    validate_source(installed.read_text(encoding="utf-8"), str(installed))
    return sha256(source)


def expect_rejected(label: str, source: str) -> None:
    try:
        validate_source(source, f"<fixture:{label}>")
    except (ValidationError, SyntaxError):
        return
    raise AssertionError(f"negative fixture unexpectedly passed: {label}")


def run_negative_fixtures(source: str) -> None:
    fixtures = {
        "extra_node": source + "\nextra = Node(package='x', executable='y')\n",
        "create_node": source + "\nextra = Node(package='ros_gz_sim', executable='create')\n",
        "timer_action": source + "\nextra = TimerAction(period=1.0, actions=[])\n",
        "execute_process": source + "\nextra = ExecuteProcess(cmd=['x'])\n",
        "opaque_function": source + "\nextra = OpaqueFunction(function=lambda: [])\n",
        "bridge_literal": source + "\nbridge = 'ros_gz_bridge'\n",
        "source_path": source.replace('package_share_parent = os.path.dirname(pkg_robot)',
                                      "package_share_parent = '/home/hazan/mecanum_autonomy_ws/ros2_ws/src'"),
        "wrong_world": source.replace('"tugbot_depot.sdf"', '"wrong.sdf"'),
        "extra_action": source.replace('LaunchDescription([set_resource_path, gazebo])',
                                       'LaunchDescription([set_resource_path, gazebo, set_resource_path])'),
        "wrong_order": source.replace('LaunchDescription([set_resource_path, gazebo])',
                                       'LaunchDescription([gazebo, set_resource_path])'),
    }
    for label, fixture in fixtures.items():
        expect_rejected(label, fixture)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--launch", type=Path, default=DEFAULT_LAUNCH)
    parser.add_argument("--installed-launch", type=Path)
    parser.add_argument("--negative-fixtures", action="store_true")
    args = parser.parse_args()
    source = args.launch.read_text(encoding="utf-8")
    validate_source(source, str(args.launch))
    if args.installed_launch is not None:
        print(f"launch_sha256={validate_install_parity(args.launch, args.installed_launch)}")
    if args.negative_fixtures:
        run_negative_fixtures(source)
        print("native-sdf-contact-diagnostic-launch-negative-fixtures=PASS (10)")
    print("native-sdf-contact-diagnostic-launch=PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, SyntaxError, ValidationError) as exc:
        print(f"native-sdf-contact-diagnostic-launch=FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
