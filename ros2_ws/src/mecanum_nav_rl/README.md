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
- Python dependencies trong `~/mecanum_autonomy_ws/requirements-lock.txt`

## Python environment tái lập được

Tạo `.venv` một lần ở workspace root, cài dependency đã khóa, rồi luôn dùng
interpreter của `.venv` để chạy colcon. `colcon` hệ thống có thể dùng Python
system khác với `.venv`; vì vậy không dùng `PYTHONPATH` thủ công và gọi
`python -m colcon` sau khi activate môi trường.

```bash
cd ~/mecanum_autonomy_ws
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
python -m pip install --requirement requirements-lock.txt
source /opt/ros/jazzy/setup.bash
cd ros2_ws
```

## Build package

Từ terminal đã chuẩn bị theo phần trên:

```bash
python -m colcon build --packages-select mecanum_nav_rl --symlink-install
source install/setup.bash
python -m colcon test --packages-select mecanum_nav_rl
python -m colcon test-result --verbose
```
