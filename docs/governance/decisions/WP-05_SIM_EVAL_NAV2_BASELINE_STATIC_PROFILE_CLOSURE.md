# WP-05 sim_eval + NAV2_BASELINE static profile input closure — Step 5A

## Classification and candidate lifecycle

- Classification: `L1_STATIC_PROFILE_INPUT_CLOSURE_ONLY`.
- Exact base: `2864a215782cc1901aa259a49d885fa0c132cf7a`.
- Đây là Step 5A: đóng tập static profile inputs cho `sim_eval + NAV2_BASELINE`.
- Candidate này là review-only trước independent audit và integration; nội dung không tạo runtime profile.

## Static inputs recorded

Descriptor tĩnh và evidence manifest ghi nhận chính xác subject map đã được duyệt, năm file cấu hình Navigation, tám hợp đồng nguồn gốc ingress/bridge/TF tĩnh, cùng tham chiếu bất biến tới external dependency lock và static-policy manifest. `warehouse_map2` chỉ được duyệt cho `SIM_EVAL_NAV2_BASELINE_STATIC_MAP_ARTIFACT_SELECTION`; world frame là `DECLARED_UNVERIFIED` và runtime compatibility vẫn `NOT_VALIDATED`.

Bản đồ đủ điều kiện làm đầu vào tĩnh cho công việc Step 5 tiếp theo, nhưng record này không phân giải profile. Nó không tạo `ResolvedConfigV3`, `config_hash` hoặc `workspace_source_locks`. Không suy diễn rằng các tham chiếu file tĩnh đã pin mười workspace-source roles runtime.

## Runtime and authority boundary

WP08 chỉ ghi nhận ranh giới bridge tĩnh. Candidate này không chọn implementation `ros_gz_bridge` hoặc transport endpoint, và không suy diễn Gazebo transport `scan` là ROS `/scan`. Candidate không tạo bridge, endpoint pin, runtime source pin, runtime evidence hoặc runtime authorization.

`navigation_v1.launch.py` và `navigation_v1_lifecycle.launch.py` tiếp tục fail-closed; marker map chưa phân giải của chúng không đổi. WP06 vẫn là điều kiện tiên quyết cho command/safety path. Cần runtime assembly cùng evidence được ủy quyền riêng trước mọi campaign. Không khẳng định có Map Server runtime binding/load, launch graph, AMCL/EKF runtime hoặc xác thực runtime compatibility.

After independent audit PASS for the exact candidate, separate User authorization, fast-forward integration, and remote-ref verification, this record is an integrated static profile-input closure only. It does not change WP-04/WP-05 or Gate A/Gate B status. Status remains WP-04 `BLOCKED_BY_CONTRACT`, Gate A `PASSED`, Gate B `NOT_STARTED`, WP-05 `OPEN`, `WORLD_FRAME: DECLARED_UNVERIFIED`, `RUNTIME_COMPATIBILITY: NOT_VALIDATED`, and `RUNTIME_APPROVED: NOT_APPROVED`.
