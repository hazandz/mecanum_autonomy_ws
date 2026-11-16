# MANUAL_SLAM: khởi động bằng hai terminal

Hướng dẫn này mô tả luồng source/launch dành riêng cho MANUAL_SLAM bench. Nó
không phải xác nhận chạy thực tế hoặc thay thế công tắc nguồn tổng. Không tự
đặt các tọa độ cảm biến: dùng các giá trị lắp đặt đã được Owner xác nhận.

## Chuẩn bị workspace trên Pi

Build và cài các package ROS trong workspace theo quy trình triển khai hiện có.
Mỗi terminal mới cần source cùng môi trường:

```bash
source /opt/ros/jazzy/setup.bash
cd <workspace>/ros2_ws
source install/setup.bash
```

Không giả định đường dẫn workspace, thiết bị serial hoặc LiDAR trên laptop và
Pi giống nhau. Lệnh dưới đây yêu cầu cung cấp manifest bench, UART, YAML driver,
LiDAR port, EKF YAML và đầy đủ transform `base_link` tới `lidar_frame`/`imu_link`.

## Terminal 1: hardware MANUAL_SLAM

```bash
ros2 launch mecanum_nav_bringup manual_slam.launch.py \
  serial_device:=<UART_STM32> \
  hardware_manifest:=<MANIFEST_SLAM_BENCH> \
  ekf_params_file:=<EKF_YAML> \
  lidar_parameter_file:=<YDLIDAR_X3_YAML> \
  lidar_port:=<YDLIDAR_PORT> \
  lidar_x:=<MEASURED_VALUE> lidar_y:=<MEASURED_VALUE> lidar_z:=<MEASURED_VALUE> \
  lidar_roll:=<MEASURED_VALUE> lidar_pitch:=<MEASURED_VALUE> lidar_yaw:=<MEASURED_VALUE> \
  imu_x:=<MEASURED_VALUE> imu_y:=<MEASURED_VALUE> imu_z:=<MEASURED_VALUE> \
  imu_roll:=<MEASURED_VALUE> imu_pitch:=<MEASURED_VALUE> imu_yaw:=<MEASURED_VALUE>
```

Launch dùng joy autorepeat để mapper timeout có thể quan sát im lặng tay cầm;
LiDAR wrapper gọi driver X3 với YAML được truyền; BNO055 wrapper mặc định
`i2c_bus=1`, `i2c_addr=41`, `frame_id=imu_link`, 50 Hz và
`use_sim_time=false`. Nếu cấu hình Pi của Owner cần giá trị bus/address khác,
truyền argument tương ứng trong launch phần cứng. Không dùng giá trị transform
mẫu thay cho phép đo.

Giữ terminal 1 mở. Theo quan sát Pi do Owner cung cấp, BNO055 node `bno055`
phát IMU tại `/bno055/imu`; wrapper không remap topic này. Terminal 2 cần nhận
`/scan`, `/bno055/imu`, `/joy`,
`/mcu/heartbeat` và trạng thái `/mecanum/safety_lifecycle_state` từ tuyến này.

## Terminal 2: SLAM Toolbox và readiness gates

```bash
source /opt/ros/jazzy/setup.bash
cd <workspace>/ros2_ws
source install/setup.bash
ros2 launch mecanum_nav_bringup manual_slam_mapping.launch.py
```

Launch chạy `async_slam_toolbox_node` với cấu hình mapping async được cài trong
`mecanum_nav_bringup/config/manual_slam/mapper_params_online_async.yaml`. Nó
đợi SLAM Toolbox và `/safety_lifecycle` active, `/scan`, topic IMU và heartbeat còn
mới/healthy, cùng một mẫu `/joy` mới và trung tính. Sau đó launch gọi safety
rearm, xác nhận `motion_permitted`, kiểm tra lại Joy trung tính, gọi
`/manual_slam/enable` và đợi một mẫu Joy mới, còn hạn, vẫn trung tính để xác
nhận mapper đã thoát trạng thái chờ neutral. Không tạo Joy giả và không gửi
lệnh chuyển động. Chỉ chuyển động cần được người điều khiển gạt có chủ ý mới
tạo lệnh.

Mỗi service có timeout mặc định 10 giây, dependency có timeout 30 giây và toàn
bộ khởi động có timeout 120 giây. Có thể điều chỉnh qua launch arguments
`service_timeout_s`, `dependency_timeout_s`, `startup_timeout_s`,
`slam_params_file`, `imu_topic`, `slam_state_check_period_s`, `joy_max_age_s` và
`heartbeat_max_age_s`. `imu_topic` mặc định `/bno055/imu`; topic sai hoặc không
có dữ liệu sẽ timeout và thông báo tên topic đang chờ. Deadzone Joy cố định
0.12 bán kính để khớp mapper hiện tại.
Thông báo `waiting for ...` nêu dependency đang chờ; hết hạn hoặc service từ
chối sẽ đóng launch terminal 2 và không báo sẵn sàng.
Sau khi enable, coordinator tiếp tục theo dõi freshness của scan/IMU/Joy,
heartbeat, safety motion permission và lifecycle `/slam_toolbox` (kiểm tra định kỳ
0.5 giây). SLAM không còn ở `active` hoặc mất một dependency sẽ yêu cầu
software disarm rồi đóng launch terminal 2 với lý do cụ thể.

## Dừng

Nhấn `Ctrl-C` ở terminal 2. Orchestrator gọi `/manual_slam/disarm` best-effort
trước khi thoát; lỗi khi bridge/service đã dừng sẽ được in ra. Sau đó dừng
terminal 1 theo quy trình bench. Software disarm không thay thế công tắc nguồn
tổng và công tắc đó chưa được xác minh ngắt cả hai driver. E-stop auxiliary
vẫn được telemetry báo `UNKNOWN` theo cấu hình bench.

Đây chỉ là hướng dẫn khởi động offline. Không xác nhận UART/session trên Pi,
độc quyền publisher graph, watchdog thực, chuyển động, E-stop vật lý hoặc chất
lượng bản đồ.
