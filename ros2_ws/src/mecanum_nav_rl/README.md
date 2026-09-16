# mecanum_nav_rl

Package ROS 2 Python chính của dự án điều hướng robot Mecanum bằng Deep Reinforcement Learning.

Package này sẽ chứa các phần:

- Cấu hình runtime theo các profile simulation và deployment.
- Tích hợp ROS 2, Gazebo Harmonic, LiDAR, odometry và TF.
- Gymnasium environment phục vụ huấn luyện PPO.
- Observation 81 chiều và action Mecanum `[vx, vy, wz]`.
- Reward, termination, training và evaluation độc lập.
- SafetySupervisor, command arbitration và final command publisher.

## Trạng thái hiện tại

Khung package Python đã được tạo:

- `package.xml`
- `setup.py`
- `setup.cfg`
- `resource/mecanum_nav_rl`
- `mecanum_nav_rl/__init__.py`

Chưa có node, launch file, Gymnasium environment hoặc PPO training.

## Yêu cầu môi trường

- Ubuntu 24.04
- ROS 2 Jazzy
- Gazebo Harmonic
- Package `mecanum_nav_rl_interfaces` đã được build thành công

## Build package

Tại thư mục ROS 2 workspace:

```bash
cd ~/mecanum_autonomy_ws/ros2_ws
source /opt/ros/jazzy/setup.bash
source install/setup.bash
colcon build --packages-select mecanum_nav_rl --symlink-install
source install/setup.bash
