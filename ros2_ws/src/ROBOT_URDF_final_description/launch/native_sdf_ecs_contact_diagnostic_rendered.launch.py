"""Load one caller-rendered native ECS diagnostic world, with no robot spawn.

``rendered_world`` has no default: a future approved supervisor must pass the
exact non-symlink rendered file.  This launch neither creates a robot nor
creates a ROS endpoint; it only configures official Gazebo search paths and
includes ``ros_gz_sim/gz_sim.launch.py``.
"""

import os
from os.path import join

from ament_index_python.packages import get_package_prefix, get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, SetEnvironmentVariable
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration


def generate_launch_description():
    pkg_ros_gz_sim = get_package_share_directory("ros_gz_sim")
    pkg_robot = get_package_share_directory("ROBOT_URDF_final_description")
    pkg_diagnostic_prefix = get_package_prefix("s3_d3_ecs_contact_diagnostic")
    rendered_world = LaunchConfiguration("rendered_world")

    inherited_resource_path = os.environ.get("GZ_SIM_RESOURCE_PATH", "")
    resource_path = os.path.dirname(pkg_robot)
    if inherited_resource_path:
        resource_path = os.pathsep.join([resource_path, inherited_resource_path])
    inherited_plugin_path = os.environ.get("GZ_SIM_SYSTEM_PLUGIN_PATH", "")
    diagnostic_plugin_path = join(pkg_diagnostic_prefix, "lib")
    plugin_path = diagnostic_plugin_path
    if inherited_plugin_path:
        plugin_path = os.pathsep.join([diagnostic_plugin_path, inherited_plugin_path])

    require_rendered_world = DeclareLaunchArgument(
        "rendered_world", description="Exact caller-rendered S3.D3 diagnostic world path"
    )
    set_resource_path = SetEnvironmentVariable(name="GZ_SIM_RESOURCE_PATH", value=resource_path)
    set_plugin_path = SetEnvironmentVariable(name="GZ_SIM_SYSTEM_PLUGIN_PATH", value=plugin_path)
    gazebo = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(join(pkg_ros_gz_sim, "launch", "gz_sim.launch.py")),
        launch_arguments={"gz_args": ["-r -v 4 ", rendered_world]}.items(),
    )
    return LaunchDescription([require_rendered_world, set_resource_path, set_plugin_path, gazebo])
