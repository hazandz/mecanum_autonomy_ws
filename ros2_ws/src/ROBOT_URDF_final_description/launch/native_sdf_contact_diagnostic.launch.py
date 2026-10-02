"""World-only native-SDF diagnostic launch.

This launch receives no robot description and emits only a resource-path setup
environment setup followed by the official Gazebo Sim world include.  A future approved
supervisor, not this launch, owns the sole native-SDF ``create -file`` child.
"""

import os
from os.path import join

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, SetEnvironmentVariable
from launch.launch_description_sources import PythonLaunchDescriptionSource


def generate_launch_description():
    pkg_ros_gz_sim = get_package_share_directory("ros_gz_sim")
    pkg_robot = get_package_share_directory("ROBOT_URDF_final_description")
    world_file_path = join(pkg_robot, "launch", "tugbot_depot.sdf")

    package_share_parent = os.path.dirname(pkg_robot)
    inherited_resource_path = os.environ.get("GZ_SIM_RESOURCE_PATH", "")
    resource_path = package_share_parent
    if inherited_resource_path:
        resource_path = os.pathsep.join(
            [package_share_parent, inherited_resource_path]
        )
    set_resource_path = SetEnvironmentVariable(
        name="GZ_SIM_RESOURCE_PATH", value=resource_path
    )

    gazebo = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            join(pkg_ros_gz_sim, "launch", "gz_sim.launch.py")
        ),
        launch_arguments={"gz_args": f"-r -v 4 {world_file_path}"}.items(),
    )

    return LaunchDescription([set_resource_path, gazebo])
