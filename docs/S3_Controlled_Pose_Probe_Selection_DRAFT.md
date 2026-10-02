# S3 Controlled Pose Probe Selection

**Status:** `USER_APPROVED_FOR_CONTROLLED_SIMULATION_MEASUREMENT — EXECUTION_NOT_YET_STARTED`

## Mục đích và giới hạn

Tài liệu này chuẩn bị các giá trị số để người dùng chọn ba probe `P0`, `P1`,
và `P2` cho phép đo controlled-coordinate sau này. Các giá trị chỉ là payload
đề xuất cho một yêu cầu pose-control đã được phê duyệt riêng; chúng không phải
start pose, goal, scenario boundary, reset contract, hay runtime approval.

Người dùng đã duyệt giới hạn cho phép đo Gazebo simulation-only: entity duy nhất là
`ROBOT_URDF_final`, và chỉ đúng ba pose request theo thứ tự `P0 → P1 → P2` của
Bộ A được phép ở phase đo sau. Approval này không suy diễn scenario/start/goal,
reset contract, runtime approval, hoặc bất kỳ quyền điều khiển nào khác.

Không có yêu cầu pose, Gazebo launch, service call, command publication, hoặc
thao tác phần cứng nào được thực hiện khi cập nhật tài liệu này.

## Phân biệt identity và coordinate frame

- `world_demo` là SDF/Gazebo world name trong
  [`tugbot_depot.sdf`](../ros2_ws/src/ROBOT_URDF_final_description/launch/tugbot_depot.sdf),
  không mặc định là ROS coordinate frame.
- `world` là `header.frame_id` đã quan sát trên ground-truth odometry; nó chỉ là
  runtime metadata quan sát được, không chứng minh Gazebo world name, TF edge,
  hoặc TF authority.
- Tọa độ dưới đây là proposed service-request coordinates để kiểm tra mapping.
  Việc chúng có cùng hệ số/trục với các số trong SDF là giả thuyết cần đo, không
  phải kết luận từ static source.
- Không suy diễn TF authority, atomic reset, collision policy, ContactLatch,
  hoặc TrainingTaskOracle từ selection này.

## Cơ sở static collision screening

World được launch là
[`tugbot_depot.sdf`](../ros2_ws/src/ROBOT_URDF_final_description/launch/tugbot_depot.sdf)
với SDF world name `world_demo`; launch spawn entity `ROBOT_URDF_final` ban đầu
tại `(0, 0, 0.1)` và yaw `0`. Collision model `depot_collision` có parent pose
`(7.19009, 1.09982, 0)` và các collision primitive được khai báo local theo
model đó.

Các số dưới đây chỉ được dùng để sàng lọc rằng một probe *không nằm trong các
primitive được khai báo tường minh*, với giả định số học tạm thời rằng request
pose dùng cùng convention với SDF. Đây là `GEOMETRY_REFERENCE_ONLY`, không phải
tọa độ ROS `world`, scenario coordinate frame, hay bằng chứng clearance runtime.

| Nhóm geometry/collision tĩnh | Bằng chứng source | Rủi ro đối với probe | Giới hạn static inspection |
| --- | --- | --- | --- |
| Boundary walls `wall1`–`wall4` | `depot_collision` trong `tugbot_depot.sdf` | Probe gần biên có thể xuyên/chạm tường | Pose request domain chưa được chứng minh là SDF/model-local domain |
| Boxes `boxes1`–`boxes11`, pallet movers, stairs, pillars | Cùng `depot_collision` | Pose có thể nằm trong obstacle tường minh | Extent robot, contact response, và vertical clearance chưa được runtime-verified |
| Shelf cylinders `shelfs1`–`shelfs18` | Cùng `depot_collision` | Các cylinder nhỏ có thể gây collision không dễ thấy khi chỉ nhìn tọa độ điểm | Không có manifest runtime cho scoped collision names |
| Fuel include `Depot` | `<include>` Fuel trong SDF | Có thể thêm geometry không có expansion local trong repository | Geometry/scoped names sau Fuel expansion là `NOT_ESTABLISHED_RUNTIME` |
| Fuel model `tugbot` | `<include>` Fuel trong SDF | Có thể thêm robot/model collision geometry | Không có static expansion hoặc runtime entity inventory chứng minh đầy đủ |
| Robot base và wheel collision links | `ROBOT_URDF_final.gazebo`/robot description | Robot footprint có thể chạm geometry dù origin probe không nằm trong primitive | Không có pose-service clearance test; wheel–ground/contact filtering chưa được chọn |

Vì scoped name, Fuel expansion, pose-service coordinate mapping, và robot footprint
chưa được đo, “không nằm trong known primitive” **không** có nghĩa là pose an toàn.
Measurement phase phải dừng ngay nếu quan sát collision hoặc behaviour bất thường.

## Bộ A — `USER_APPROVED_FOR_CONTROLLED_SIMULATION_MEASUREMENT`

Các điểm A được đặt về phía `x` âm, cách các obstacle primitive tường minh ở
vùng depot nội bộ; chúng tạo tam giác không thẳng hàng. `z = 0.1` được mượn từ
startup spawn pose source, chỉ là reference chứ không chứng minh clearance.

| Probe | x | y | z | yaw (rad) | Lý do chọn | Confidence và giới hạn |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| P0 | -4.0 | -3.0 | 0.1 | 0.0 | Điểm tham chiếu phía tây-nam, cách boundary/obstacle primitive tường minh trong sàng lọc số học | Conditional-low: không nằm trong declared primitive theo screening; Fuel, footprint, và coordinate mapping chưa biết |
| P1 | -4.0 | 0.0 | 0.1 | 1.57079632679 | Dịch `+y` từ P0 và thay yaw để kiểm tra trục/yaw mapping | Conditional-low: cùng giới hạn như P0 |
| P2 | -2.0 | -3.0 | 0.1 | -1.57079632679 | Dịch `+x` từ P0 để tạo tam giác và kiểm tra trục khác | Conditional-low: cùng giới hạn như P0 |

| Khoảng cách tương đối | Giá trị |
| --- | ---: |
| P0–P1 | 3.000 m |
| P0–P2 | 2.000 m |
| P1–P2 | sqrt(13) ≈ 3.606 m |

Ba điểm không thẳng hàng vì vector `P0→P1 = (0, 3)` và `P0→P2 = (2, 0)` không
đồng phương.

## Bộ B — `NOT_SELECTED`

Các điểm B nằm ở vùng tây-bắc khác với Bộ A, vẫn tránh các primitive collision
tường minh theo screening số học. Bộ này dùng cùng khoảng cách tam giác nhưng
khác vùng để giúp phát hiện mapping bị lệch theo vị trí.

| Probe | x | y | z | yaw (rad) | Lý do chọn | Confidence và giới hạn |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| P0 | -5.0 | 2.0 | 0.1 | 0.0 | Reference phía tây-bắc, không trùng vùng Bộ A | Conditional-low: chỉ qua declared-primitive screening; không có clearance/runtime confirmation |
| P1 | -5.0 | 5.0 | 0.1 | 1.57079632679 | Dịch `+y` để kiểm tra consistency theo một trục | Conditional-low: cùng giới hạn như P0 |
| P2 | -3.0 | 2.0 | 0.1 | -1.57079632679 | Dịch `+x` để tạo tam giác không thẳng hàng | Conditional-low: cùng giới hạn như P0 |

| Khoảng cách tương đối | Giá trị |
| --- | ---: |
| P0–P1 | 3.000 m |
| P0–P2 | 2.000 m |
| P1–P2 | sqrt(13) ≈ 3.606 m |

Ba điểm không thẳng hàng vì vector `P0→P1 = (0, 3)` và `P0→P2 = (2, 0)` không
đồng phương.

## Lựa chọn của người dùng

Người dùng đã chọn Bộ A cho một controlled measurement Gazebo simulation-only.
Approval chỉ bao gồm `ROBOT_URDF_final` và chính xác ba request theo thứ tự
`P0 → P1 → P2`; không mở rộng thành scenario/start/goal/reset contract hoặc
runtime approval.

| Lựa chọn | Trạng thái | Điều kiện trước phase đo |
| --- | --- | --- |
| [x] Bộ A | `USER_APPROVED_FOR_CONTROLLED_SIMULATION_MEASUREMENT` | Chỉ P0 → P1 → P2 với các giá trị số đã ghi; entity duy nhất `ROBOT_URDF_final` |
| [ ] Bộ B | `NOT_SELECTED` | Không được thực thi trong controlled measurement đã duyệt này |
| [ ] Tự nhập P0/P1/P2 | `NOT_SELECTED` | Cần một user approval mới trước mọi thay thế tọa độ |

## Pre-run checklist cho phase controlled measurement sau này

- [ ] Target entity duy nhất là `ROBOT_URDF_final`.
- [ ] Chỉ có đúng ba pose request P0/P1/P2 đã được người dùng phê duyệt.
- [ ] Capture metadata/stream trước và sau từng request.
- [ ] Không có `/cmd_vel`, teleop, Nav2, PPO/Gymnasium.
- [ ] Không reset, pause, step world, spawn, delete, hay world-control operation.
- [ ] Không có undeclared pose request hoặc command publication.
- [ ] Stop ngay nếu robot xuất hiện collision hoặc behaviour bất thường.
- [ ] Lossless artifact ghi symbolic probe ID, numerical request fields, target,
  call order, response, và barrier metadata.

## Explicit non-claims

Selection này không xác lập scenario coordinate frame, valid area, forbidden
zone, task goal, collision filter, ContactLatch, reset receipt, TF ownership,
hay TrainingTaskOracle runtime. Các quyết định đó vẫn theo các draft S3 và cần
evidence/runtime approval riêng.
