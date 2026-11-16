"""Terminal 2: start async SLAM and gate MANUAL_SLAM rearm/enable."""
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument, LogInfo, RegisterEventHandler, Shutdown,
)
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch.event_handlers import OnProcessExit
from launch_ros.actions import LifecycleNode, Node
from launch_ros.substitutions import FindPackageShare

from mecanum_nav_bringup.manual_slam_orchestration import DEFAULT_IMU_TOPIC


def generate_launch_description():
    slam_config = LaunchConfiguration("slam_params_file")
    orchestrator = Node(
        package="mecanum_nav_bringup", executable="manual_slam_orchestrator",
        name="manual_slam_orchestrator", output="screen",
        parameters=[{
            "use_sim_time": False,
            "startup_timeout_s": LaunchConfiguration("startup_timeout_s"),
            "dependency_timeout_s": LaunchConfiguration("dependency_timeout_s"),
            "service_timeout_s": LaunchConfiguration("service_timeout_s"),
            "slam_state_check_period_s": LaunchConfiguration("slam_state_check_period_s"),
            "imu_topic": LaunchConfiguration("imu_topic"),
            "joy_max_age_s": LaunchConfiguration("joy_max_age_s"),
            "heartbeat_max_age_s": LaunchConfiguration("heartbeat_max_age_s"),
        }],
    )
    slam_toolbox = LifecycleNode(
        package="slam_toolbox", executable="async_slam_toolbox_node",
        name="slam_toolbox", namespace="/", output="screen",
        parameters=[slam_config, {"use_sim_time": False}],
    )
    return LaunchDescription([
        DeclareLaunchArgument(
            "slam_params_file",
            default_value=PathJoinSubstitution([
                FindPackageShare("mecanum_nav_bringup"), "config", "manual_slam",
                "mapper_params_online_async.yaml",
            ]),
            description="Async SLAM Toolbox mapping parameters for MANUAL_SLAM",
        ),
        DeclareLaunchArgument("startup_timeout_s", default_value="120.0"),
        DeclareLaunchArgument("dependency_timeout_s", default_value="30.0"),
        DeclareLaunchArgument("service_timeout_s", default_value="10.0"),
        DeclareLaunchArgument("slam_state_check_period_s", default_value="0.5"),
        DeclareLaunchArgument("imu_topic", default_value=DEFAULT_IMU_TOPIC),
        DeclareLaunchArgument("joy_max_age_s", default_value="0.25"),
        DeclareLaunchArgument("heartbeat_max_age_s", default_value="0.6"),
        RegisterEventHandler(OnProcessExit(
            target_action=orchestrator,
            on_exit=[
                LogInfo(msg=(
                    "manual_slam_orchestrator exited; stopping the terminal-2 SLAM launch")),
                Shutdown(reason=(
                    "MANUAL_SLAM orchestration ended; mapping launch is not ready")),
            ],
        )),
        RegisterEventHandler(OnProcessExit(
            target_action=slam_toolbox,
            on_exit=[
                LogInfo(msg="SLAM Toolbox exited; stopping terminal-2 mapping launch"),
                Shutdown(reason="SLAM Toolbox exited; mapping launch is not ready"),
            ],
        )),
        slam_toolbox,
        orchestrator,
    ])
