#!/usr/bin/env python3
"""Offline structural validation for the typed-Scene bootstrap description launch."""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path('/home/hazan/mecanum_autonomy_ws')
LAUNCH = ROOT / 'ros2_ws/src/ROBOT_URDF_final_description/launch/typed_scene_observer.launch.py'
FORBIDDEN_RUNTIME_LITERALS = (
    'ros_gz_bridge', 'parameter_bridge', '/cmd_vel', 'static_transform_publisher',
    'teleop', 'nav2', 'ppo', 'gym', 'training', 'controlworld', 'setentitypose',
    'raw-contact', 'contact/raw',
)
ALLOWED_LAUNCH_CONSTRUCTORS = {
    'LaunchDescription', 'SetEnvironmentVariable', 'IncludeLaunchDescription',
    'Node', 'PythonLaunchDescriptionSource',
}
FORBIDDEN_LAUNCH_CONSTRUCTORS = {
    'OpaqueFunction', 'GroupAction', 'ExecuteProcess', 'EmitEvent',
    'RegisterEventHandler', 'OnProcessExit', 'OnProcessStart', 'TimerAction',
}


def call_name(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return None


def keyword(call: ast.Call, name: str) -> ast.AST | None:
    return next((item.value for item in call.keywords if item.arg == name), None)


def constant(node: ast.AST | None):
    return node.value if isinstance(node, ast.Constant) else None


def assign_value(tree: ast.AST, name: str) -> ast.AST:
    matches = [node.value for node in ast.walk(tree) if isinstance(node, ast.Assign)
               for target in node.targets if isinstance(target, ast.Name) and target.id == name]
    assert len(matches) == 1, f'expected one assignment to {name}, found {len(matches)}'
    return matches[0]


def validate_source(source: str) -> None:
    tree = ast.parse(source, filename=str(LAUNCH))
    constants = [node.value.lower() for node in ast.walk(tree)
                 if isinstance(node, ast.Constant) and isinstance(node.value, str)]
    forbidden = [literal for literal in FORBIDDEN_RUNTIME_LITERALS
                 if any(literal in value for value in constants)]
    assert not forbidden, f'forbidden runtime literal(s): {forbidden}'
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
    names = [call_name(call) for call in calls]
    forbidden_calls = [name for name in names if name in FORBIDDEN_LAUNCH_CONSTRUCTORS
                       or (name and name.endswith('Action') and name not in ALLOWED_LAUNCH_CONSTRUCTORS)]
    assert not forbidden_calls, f'forbidden launch action(s): {forbidden_calls}'
    assert 'system' not in names and 'Popen' not in names and 'run' not in names, 'shell/subprocess API is prohibited'
    assert not any(name in source for name in ('retry', 'respawn')), 'retry or respawn path is prohibited'

    nodes = [call for call in calls if call_name(call) == 'Node']
    assert len(nodes) == 1, f'expected exactly one Node action, found {len(nodes)}'
    provider = nodes[0]
    assert constant(keyword(provider, 'package')) == 'robot_state_publisher'
    assert constant(keyword(provider, 'executable')) == 'robot_state_publisher'
    assert keyword(provider, 'arguments') is None
    assert keyword(provider, 'remappings') is None
    assert keyword(provider, 'namespace') is None
    parameters = keyword(provider, 'parameters')
    assert isinstance(parameters, ast.List) and len(parameters.elts) == 1
    assert isinstance(parameters.elts[0], ast.Name) and parameters.elts[0].id == 'robot_description'
    assert not [call for call in calls if call_name(call) == 'TimerAction'], 'TimerAction must be absent'
    assert not [call for call in calls if constant(keyword(call, 'package')) == 'ros_gz_sim' and constant(keyword(call, 'executable')) == 'create'], 'launch-owned create must be absent'

    includes = [call for call in calls if call_name(call) == 'IncludeLaunchDescription']
    assert len(includes) == 1
    include_text = ast.unparse(includes[0])
    assert "'gz_sim.launch.py'" in include_text or '"gz_sim.launch.py"' in include_text
    assert 'world_file_path' in include_text and 'gz_args' in include_text
    world = ast.unparse(assign_value(tree, 'world_file_path'))
    assert "'launch'" in world and "'tugbot_depot.sdf'" in world
    resources = [call for call in calls if call_name(call) == 'SetEnvironmentVariable']
    assert len(resources) == 1 and constant(keyword(resources[0], 'name')) == 'GZ_SIM_RESOURCE_PATH'

    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'generate_launch_description']
    assert len(functions) == 1
    returns = [node for node in ast.walk(functions[0]) if isinstance(node, ast.Return)]
    assert len(returns) == 1 and isinstance(returns[0].value, ast.Call) and call_name(returns[0].value) == 'LaunchDescription'
    result_actions = returns[0].value.args[0] if returns[0].value.args else None
    assert isinstance(result_actions, ast.List)
    assert [item.id if isinstance(item, ast.Name) else None for item in result_actions.elts] == ['set_resource_path', 'gazebo', 'description_provider']
    assert len(result_actions.elts) == 3


def expect_rejected(label: str, source: str) -> None:
    try:
        validate_source(source)
    except (AssertionError, SyntaxError):
        return
    raise AssertionError(f'negative fixture unexpectedly accepted: {label}')


def offline_self_test() -> None:
    source = LAUNCH.read_text(encoding='utf-8')
    validate_source(source)
    fixtures = {
        'extra_node': source + "\nextra = Node(package='x', executable='y')\n",
        'launch_owned_create': source + "\nextra = Node(package='ros_gz_sim', executable='create')\n",
        'timer_action': source + "\nextra = TimerAction(period=3.0, actions=[])\n",
        'opaque_function': source + "\nextra = OpaqueFunction()\n",
        'execute_process': source + "\nextra = ExecuteProcess()\n",
        'unknown_action': source + "\nextra = GroupAction()\n",
        'wrong_return_list': source.replace('description_provider,\n    ])', 'description_provider,\n        gazebo,\n    ])'),
    }
    for label, fixture in fixtures.items():
        expect_rejected(label, fixture)
    print(f'typed-scene-diagnostic-launch-self-test: PASS ({len(fixtures)} negative fixtures)')


def main() -> int:
    validate_source(LAUNCH.read_text(encoding='utf-8'))
    print('typed-scene-diagnostic-launch-static-check: PASS')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
