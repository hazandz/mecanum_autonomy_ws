import os
from os.path import join

from ament_index_python.packages import get_package_share_directory

from launch import LaunchDescription
from launch.actions import (
    IncludeLaunchDescription,
    TimerAction,
    SetEnvironmentVariable
)
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node

import xacro


def generate_launch_description():

    # ============================================================
    # 1. PACKAGE PATHS
    # ============================================================

    pkg_ros_gz_sim = get_package_share_directory('ros_gz_sim')
    pkg_robot = get_package_share_directory('ROBOT_URDF_final_description')
    pkg_share_parent = os.path.dirname(pkg_robot)

    # ============================================================
    # 2. FILE PATHS
    # ============================================================

    robot_description_file = os.path.join(
        pkg_robot, 'urdf', 'ROBOT_URDF_final.xacro'
    )
    world_file_path = os.path.join(
        pkg_robot, 'launch', 'tugbot_depot.sdf'
    )

    # ============================================================
    # 3. PROCESS XACRO -> URDF
    # ============================================================

    robot_description_config = xacro.process_file(robot_description_file)
    robot_description = {'robot_description': robot_description_config.toxml()}

    # ============================================================
    # 4. GAZEBO RESOURCE PATH
    # ============================================================

    current_gz_resource_path = os.environ.get('GZ_SIM_RESOURCE_PATH', '')
    resource_paths = [pkg_share_parent]

    if current_gz_resource_path:
        resource_paths.append(current_gz_resource_path)

    set_gz_resource_path = SetEnvironmentVariable(
        name='GZ_SIM_RESOURCE_PATH',
        value=':'.join(resource_paths)
    )

    # ============================================================
    # 5. ROBOT STATE PUBLISHER
    # ============================================================

    robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        name='robot_state_publisher',
        output='screen',
        parameters=[
            robot_description,
            {'use_sim_time': True}
        ]
    )

    # ============================================================
    # 6. GAZEBO HARMONIC
    # ============================================================

    gazebo = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            join(pkg_ros_gz_sim, 'launch', 'gz_sim.launch.py')
        ),
        launch_arguments={
            'gz_args': f'-r -v 4 {world_file_path}'
        }.items()
    )

    # ============================================================
    # 7. SPAWN ROBOT
    # ============================================================

    spawn_robot = TimerAction(
        period=3.0,
        actions=[
            Node(
                package='ros_gz_sim',
                executable='create',
                arguments=[
                    '-topic', '/robot_description',
                    '-name', 'ROBOT_URDF_final',
                    '-allow_renaming', 'false',
                    '-x', '0.0',
                    '-y', '0.0',
                    '-z', '0.1',
                    '-Y', '0.0'
                ],
                output='screen'
            )
        ]
    )

    # ============================================================
    # 8. ROS 2 <-> GAZEBO BRIDGE (ĐÃ FIX CÚ PHÁP & THÊM JOINT STATES)
    # ============================================================

    ros_gz_bridge = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        arguments=[
            # Lệnh điều khiển xe
            '/cmd_vel@geometry_msgs/msg/Twist@gz.msgs.Twist',
            # Tọa độ Odom
            '/odom@nav_msgs/msg/Odometry@gz.msgs.Odometry',
            # Dữ liệu Laser RPLidar
           # Lidar chỉ được phép đẩy data 1 chiều từ Gazebo -> ROS 2 bằng dấu '['
            '/scan@sensor_msgs/msg/LaserScan[gz.msgs.LaserScan',
            # Dữ liệu Ảnh Camera RealSense
            '/camera/image_raw@sensor_msgs/msg/Image@gz.msgs.Image',
            # Khung tọa độ TF (ĐÃ THÊM DẤU PHẨY CHUẨN)
            '/tf@tf2_msgs/msg/TFMessage@gz.msgs.Pose_V',
            # Đồng bộ thời gian mô phỏng
            '/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock',
            # Trạng thái các khớp bánh xe
            '/joint_states@sensor_msgs/msg/JointState[gz.msgs.Model'
        ],
        parameters=[
            {'use_sim_time': True}
        ],
        output='screen'
    )

# ============================================================
    # 8.5. STATIC TF BRIDGE CHO LIDAR
    # ============================================================
   # SỬA LẠI TÊN FRAME ID BÊN PHÍA GAZEBO CHO ĐÚNG VỚI LINK ĐÃ ĐƯỢC BẢO TOÀN
    static_tf_pub = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        arguments=[
            '0', '0', '0', '0', '0', '0',
            'RPLiDAR_A1M8_1',
            'ROBOT_URDF_final/RPLiDAR_A1M8_1/rplidar' # <-- Sửa chữ base_link thành RPLiDAR_A1M8_1
        ],
        output='screen'
    )
    # ============================================================
    # 9. LAUNCH DESCRIPTION
    # ============================================================

    return LaunchDescription([
        set_gz_resource_path,
        gazebo,
        spawn_robot,
        ros_gz_bridge,
        robot_state_publisher,
        static_tf_pub
    ])