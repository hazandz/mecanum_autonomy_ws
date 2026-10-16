# WP-06 sim_eval wheel/IMU runtime-source binding — independent replacement candidate

## Decision identity and lifecycle

- Work package: `WP06_SIM_EVAL_WHEEL_IMU_RUNTIME_INGRESS_BARRIER_AND_CLOCK_CORRECTED`
- Classification: `L2_SIM_EVAL_WHEEL_IMU_INGRESS_SOURCE_AND_BARRIER_CLOCK_CORRECTION`
- Exact integration/source base: `43c94789f628b4211189fc391326e0b119cbb6d3`
- Review branch: `wp06-sim-eval-wheel-imu-ingress-barrier-clock-fix-43c9478`
- Architecture SHA-256: `432eeac363a595cfcf7e81c4b66054fb674dba140a2ef3cffecd617ab8136204`
- Evidence level: `IMPLEMENTED_OFFLINE_BUILD_AND_TEST_ONLY` (chỉ áp dụng khi các check offline trong báo cáo candidate đạt).
- Candidate `38d52b19b8cacecbe49961f77df47eaacfd8c3c4` là historical rejected candidate; replacement này được dựng trực tiếp từ base nêu trên, không kế thừa code hoặc commit của candidate đó.
- Trạng thái của tài liệu này là review candidate. Nó không tự kích hoạt runtime authority hoặc thay đổi status WP-04/WP-05/Gate A/Gate B.

## Bounded source ownership

Candidate 6C sở hữu đúng model-level static IMU source, pure-Python wheel odometry emulator, pure-Python IMU normalizer, source-binding config, ROS ingress source, offline tests và governance evidence trong allowlist. Candidate không sở hữu ROS–Gazebo bridge; WP06-6E vẫn là owner duy nhất của bridge implementation.

Wheel path: Gazebo `/joint_states` (`gz.msgs.Model`) → bridge tương lai thuộc WP06-6E → `/sim_eval/wheel_joint_states` (`sensor_msgs/msg/JointState`) → ingress này → `/wheel/odometry_raw` (`nav_msgs/msg/Odometry`) → EKF.

IMU path: Gazebo `/sim_eval/imu/raw` (`gz.msgs.IMU`) → bridge tương lai thuộc WP06-6E → `/sim_eval/imu_raw` (`sensor_msgs/msg/Imu`) → ingress này → `/imu/data` (`sensor_msgs/msg/Imu`) → EKF.

Wheel emulator chỉ sử dụng bốn wheel angular velocities trong staging `JointState`; không dùng position, Gazebo model/world pose, `/odom` hoặc `/ground_truth/odom`. Output wheel odometry có frame `odom`/`base_link` và không phát TF. IMU source khai báo gắn vào `base_link`; điều này chưa phải runtime frame evidence.

## Corrections

### F-01 — invalid wheel input interval barrier

Mọi cấu trúc, joint, velocity, stamp, duplicate, gap hoặc kết quả tính toán không hợp lệ làm mất `_last_stamp_ns`, giữ nguyên pose tin cậy và không phát sample. Sample hợp lệ tiếp theo chỉ lập baseline; chỉ sample hợp lệ sau baseline mới được tích phân. Stamp lùi reset pose về gốc và yêu cầu baseline mới. Pose dự kiến được tính trong local variables và chỉ commit sau khi mọi trường output hữu hạn. Không tích phân xuyên qua khoảng dữ liệu không đáng tin và không tạo TF.

### F-02 — effective simulation clock before endpoints

Ngay sau `super().__init__()` node đặt atomically `use_sim_time=true`, kiểm tra `result.successful`, rồi kiểm tra giá trị effective là `True`. Mọi lỗi ném `RuntimeError` trước khi tạo bất kỳ publisher/subscriber nào. Không dùng `has_parameter`/`declare_parameter` như fallback để bảo đảm clock contract.

## Runtime and authority boundary

Source binding giữ `runtime_eligible: false`; bridge implementation status là `PENDING_WP06_6E`; runtime evidence status là `NOT_CREATED`. Không tạo bridge, TF publisher, `/cmd_vel` publisher, `/odom`/`/ground_truth/odom` input, ROS graph evidence, runtime execution, Nav2/EKF/Map Server runtime, resolved profile, `ResolvedConfigV3`, `config_hash`, Gate B transition, deployment authority hoặc runtime authorization. Runtime compatibility chưa được xác minh; `RUNTIME_APPROVED: NOT_APPROVED`.

Candidate không đổi static ingress contract v1, static profile Step 5A, EKF YAML, SDF, LiDAR source, map, WP-04/WP-05, Gate A hoặc Gate B. Kết quả source/XML/YAML/parser/pytest/py_compile/colcon nếu có chỉ là bằng chứng ngoại tuyến, không phải runtime evidence. Trong lần kiểm tra candidate, pytest trực tiếp chạy toàn package và `colcon build` đạt; `colcon test` log ghi `Ran 1 test`, trong khi `colcon test-result --verbose` báo `0 tests`. Vì hai kết quả colcon không nhất quán, không tính `colcon test` là bằng chứng test thành công.
