# WP06-6F TF/EKF runtime state-estimation ingress — Run005 corrective decision

## Authority and bounded status

- Work item: `WP06-6F_TF_EKF_RUNTIME_STATE_ESTIMATION_INGRESS_WITH_CLOCK`.
- Classification: `L2_PROFILE_SPECIFIC_TF_EKF_RUNTIME_STATE_ESTIMATION_INGRESS`.
- Corrective base / sole parent: `8b21a9832c18bc8a91af5169a78ac621038def46`.
- Integration base: `8b73bcb0b026fe337c023f6a30205dbe89d31eb5`.
- Architecture SHA-256: `432eeac363a595cfcf7e81c4b66054fb674dba140a2ef3cffecd617ab8136204`.
- Current evidence ceiling: `IMPLEMENTED_OFFLINE_RUN004_CHECKER_CONTRACT_CORRECTION_RUN005_GUARD_PENDING`.

This candidate creates a new Run005 runner and capacity-one guard. It corrects the node-topology checker contract without changing runtime topology, bridge mappings, EKF YAML, TF ownership, sensor semantics, or the C++ observer. EKF data-plane subscriptions are exactly `/clock`, `/imu/data`, and `/wheel/odometry_raw`; the one allowed administrative subscription is `/set_pose`. Run005 separately captures `/set_pose` topic info and a bounded single-message echo attempt. It requires type `geometry_msgs/msg/PoseWithCovarianceStamped`, exactly one EKF subscription, zero publishers, and no payload. Any observed publisher fails with `EKF_SET_POSE_EXTERNAL_PUBLISHER_OBSERVED`.

Node topic policy is parsed by section and compared as exact topic-name sets. `/odometry/filtered` is not equal to `/odom`; exact `/odom`, `/ground_truth/odom`, `/cmd_vel`, `/map`, `/tf_static`, any unauthorized `/set_pose` endpoint, or any additional node topic outside its allowlist fails closed. This source-only candidate does not alter the WP06-6F launch or runtime topology.

`runtime_eligible: false`; runtime evidence status is `NOT_CREATED`; `RUNTIME_APPROVED: NOT_APPROVED`; `GATE_B: NOT_STARTED`. Run005 is pending only; it has not been authorized or executed.

## Locked topology retained

The bootstrap retains the sole `robot_state_publisher` and owns static `base_link -> lidar_frame`. The composite retains only the existing WP06-6C wheel/IMU ingress, the dedicated GZ-to-ROS `/clock` bridge, and one `robot_localization/ekf_node`. No bridge route is added for `/odom`, `/ground_truth/odom`, `/tf`, `/tf_static`, `/cmd_vel`, or `/map`; no second EKF, Nav2, AMCL, SLAM, Map Server, command publisher, or custom TF broadcaster is added.

The EKF remains configured with simulation time, `reset_on_time_jump: true`, `publish_tf: true`, `two_d_mode: true`, and `world_frame: odom`. It fuses only wheel linear velocity X/Y and IMU yaw/yaw-rate, with no new covariance tuning. EKF remains the intended sole dynamic `odom -> base_link` owner; bootstrap RSP remains the intended sole static `base_link -> lidar_frame` owner. These are source/design constraints, not findings from Run005.

## Immutable runtime history

- Run001 is an immutable historical observer API failure: Jazzy `rclpy` did not support the attempted `with_info=True` API. It does not establish a TF/EKF failure and was not retried.
- Run002 is an immutable historical C++ observer nested-array execution failure (`json.exception.type_error.304`); its guard was consumed once. It does not establish a TF/EKF/clock/RSP failure and was not retried.
- Run003 is an immutable historical cross-language JSON byte-comparison failure: valid C++ JSON was rejected by Python reserialization. It does not establish a TF/EKF/clock/robot failure; its guard was consumed once and its raw evidence was not changed or retried.
- Run004 was executed once at review commit `8b21a9832c18bc8a91af5169a78ac621038def46` and ended `WP06_6F_RUNTIME_RUN004_FAIL_NO_RETRY_GUARD_CONSUMED`. Its raw evidence shows the EKF subscribes to the expected inputs plus standard administrative `/set_pose`. The checker rejected that subscriber and falsely detected `/odom` by substring matching `/odometry/filtered`. Run004 therefore records checker-contract failures, not a TF/EKF/clock/robot failure. Its guard was consumed once; no Run004 guard, runner, manifest, record, or raw artifact is modified by this candidate, and Run004 is not retried.

## Run005 guard and evidence ceiling

Run005 guard seed is `PENDING_EXACT_INTEGRATION_AND_USER_AUTHORIZATION`, capacity `1`, acquisition count `0`, `runtime_authorization=NOT_GRANTED`. It remains pending and unconsumed; this candidate grants no runtime authorization.

The Run005 acceptance matrix names a collector, raw transcript path, exact parser/validator, pass condition, failure literal, and offline test for node topology and `/set_pose` publisher/payload checks. Evidence is limited to source, governance, and offline test/build checks. Runtime evidence remains `NOT_CREATED`; `RUNTIME_APPROVED: NOT_APPROVED`; `GATE_B: NOT_STARTED`.
