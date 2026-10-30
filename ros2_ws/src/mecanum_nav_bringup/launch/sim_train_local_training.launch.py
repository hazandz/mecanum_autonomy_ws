"""Launch the B2 server supervisor with an optional GUI process."""
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument, ExecuteProcess, OpaqueFunction,
)
from launch.substitutions import LaunchConfiguration


def _start(context):
    from mecanum_nav_bringup.local_training_launch_contract import (
        parse_gui_argument,
    )

    gui = LaunchConfiguration('gui').perform(context)
    parse_gui_argument(gui)
    config = LaunchConfiguration('resolved_config').perform(context)
    if not config.startswith('/'):
        raise ValueError('resolved_config must be an absolute path')
    return [
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
