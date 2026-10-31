"""Launch the local training supervisor and trusted data adapters."""
from pathlib import Path

from ament_index_python.packages import get_package_share_directory

from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    ExecuteProcess,
    OpaqueFunction,
)
from launch.substitutions import LaunchConfiguration

from launch_ros.actions import Node


def _start(context):
    from mecanum_nav_bringup.local_training_launch_contract import (
        parse_gui_argument,
    )

    gui = LaunchConfiguration('gui').perform(context)
    parse_gui_argument(gui)
    config = LaunchConfiguration('resolved_config').perform(context)
    if not config.startswith('/'):
        raise ValueError('resolved_config must be an absolute path')

    description_share = Path(
        get_package_share_directory('ROBOT_URDF_final_description'),
    ).resolve(strict=True)
    bringup_share = Path(
        get_package_share_directory('mecanum_nav_bringup'),
    ).resolve(strict=True)
    robot_description = (
        description_share / 'urdf/mecanum_b2_static.urdf'
    ).read_text(encoding='utf-8')
    bridge_config = bringup_share / 'config/bridge/local_training.runtime.yaml'
    if not bridge_config.is_file():
        raise FileNotFoundError(
            'installed local-training bridge config missing'
        )

    return [
        Node(
            package='robot_state_publisher',
            executable='robot_state_publisher',
            name='robot_state_publisher',
            output='screen',
            parameters=[{
                'robot_description': robot_description,
                'use_sim_time': True,
            }],
        ),
        Node(
            package='ros_gz_bridge',
            executable='parameter_bridge',
            name='local_training_bridge',
            output='screen',
            parameters=[{'config_file': str(bridge_config)}],
        ),
        ExecuteProcess(
            cmd=[
                'local_training_supervisor', '--gui', gui,
                '--resolved-config', config,
            ],
            output='screen',
            name='local_training_process_supervisor',
        ),
    ]


def generate_launch_description():
    """Declare the GUI and verified configuration launch arguments."""
    return LaunchDescription([
        DeclareLaunchArgument('gui', default_value='false'),
        DeclareLaunchArgument(
            'resolved_config',
            description='Absolute path to verified B2 resolved config',
        ),
        OpaqueFunction(function=_start),
    ])
