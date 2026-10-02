"""Dedicated bootstrap-only launch for the S3 D3 typed Scene diagnostic.

This launch supplies the initial robot description only. The supervisor owns the
one approved bootstrap create child; this launch contains no bridge, command,
control, observer, or create path.
"""

import os
from os.path import join

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, SetEnvironmentVariable
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node
import xacro


def generate_launch_description():
    pkg_ros_gz_sim = get_package_share_directory('ros_gz_sim')
    pkg_robot = get_package_share_directory('ROBOT_URDF_final_description')
    robot_description_file = join(pkg_robot, 'urdf', 'ROBOT_URDF_final.xacro')
    world_file_path = join(pkg_robot, 'launch', 'tugbot_depot.sdf')

    robot_description_config = xacro.process_file(robot_description_file)
    robot_description = {'robot_description': robot_description_config.toxml()}

    current_resource_path = os.environ.get('GZ_SIM_RESOURCE_PATH', '')
    resource_paths = [os.path.dirname(pkg_robot)]
    if current_resource_path:
        resource_paths.append(current_resource_path)
    set_resource_path = SetEnvironmentVariable(
        name='GZ_SIM_RESOURCE_PATH', value=':'.join(resource_paths)
    )

    description_provider = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        name='typed_scene_bootstrap_description_provider',
        output='screen',
        parameters=[robot_description],
    )

    gazebo = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(join(pkg_ros_gz_sim, 'launch', 'gz_sim.launch.py')),
        launch_arguments={'gz_args': f'-r -v 4 {world_file_path}'}.items(),
    )



    return LaunchDescription([
        set_resource_path,
        gazebo,
        description_provider,
    ])
