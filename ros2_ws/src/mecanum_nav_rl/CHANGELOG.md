# Changelog

Mọi thay đổi có ảnh hưởng đến cách package `mecanum_nav_rl`
giao tiếp, build, chạy hoặc đánh giá sẽ được ghi tại đây.

Các thay đổi nhỏ chỉ nằm bên trong một file và không ảnh hưởng
đến package khác không bắt buộc phải ghi.

## [Unreleased]

Các module runtime, cấu hình, Gymnasium environment, training,
evaluation và safety chưa được triển khai.

## [0.1.0] - 2026-09-04

### Added

- Tạo khung package ROS 2 Python `mecanum_nav_rl`.
- Khai báo build bằng `ament_python`.
- Khai báo dependency ROS 2 và dependency với
  `mecanum_nav_rl_interfaces`.
- Tạo resource marker để ROS 2 tìm package.
- Tạo Python package `mecanum_nav_rl`.
- Tạo tài liệu hướng dẫn build ban đầu.

### Notes

- Package chưa có node chạy bằng `ros2 run`.
- Package chưa có launch file.
- Package chưa có Gymnasium environment hoặc PPO training.
- Hai custom message `Heartbeat` và `SafetyState` thuộc package
  `mecanum_nav_rl_interfaces`.
