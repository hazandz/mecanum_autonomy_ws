import os
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare

def generate_launch_description():
    pkg_name = 'ROBOT_URDF_final_description'

    # ============================================================
    # 1. KHAI BÁO CÁC BIẾN MÔI TRƯỜNG
    # ============================================================
    use_sim_time = LaunchConfiguration('use_sim_time')
    map_yaml_file = LaunchConfiguration('map')
    params_file = LaunchConfiguration('params_file')

    declare_use_sim_time_cmd = DeclareLaunchArgument(
        'use_sim_time',
        default_value='true',
        description='Sử dụng thời gian mô phỏng Gazebo'
    )

    declare_map_yaml_cmd = DeclareLaunchArgument(
        'map',
        default_value=PathJoinSubstitution(
            [FindPackageShare(pkg_name), 'maps', 'warehouse_map2.yaml']
        ),
        description='Đường dẫn tuyệt đối đến file bản đồ'
    )

    declare_params_file_cmd = DeclareLaunchArgument(
        'params_file',
        default_value=PathJoinSubstitution(
            [FindPackageShare(pkg_name), 'config', 'nav2_params.yaml']
        ),
        description='Đường dẫn tuyệt đối đến file cấu hình của Nav2'
    )

    # ============================================================
    # 2. KHỐI NAV2 BRINGUP (ĐIỀU HƯỚNG CỐT LÕI TÁCH RỜI)
    # ============================================================
    nav2_bringup_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution(
                [FindPackageShare('nav2_bringup'), 'launch', 'bringup_launch.py']
            )
        ),
        launch_arguments={
            'map': map_yaml_file,
            'use_sim_time': use_sim_time,
            'params_file': params_file,
            'autostart': 'true'
        }.items()
    )

    return LaunchDescription([
        declare_use_sim_time_cmd,
        declare_map_yaml_cmd,
        declare_params_file_cmd,
        nav2_bringup_launch
    ])