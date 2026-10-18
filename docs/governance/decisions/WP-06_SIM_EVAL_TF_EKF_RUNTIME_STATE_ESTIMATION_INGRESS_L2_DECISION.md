# WP06-6F TF/EKF runtime state-estimation ingress — L2 decision

## Classification and authority

- Work item: `WP06-6F_TF_EKF_RUNTIME_STATE_ESTIMATION_INGRESS_WITH_CLOCK`.
- Classification: `L2_PROFILE_SPECIFIC_TF_EKF_RUNTIME_STATE_ESTIMATION_INGRESS`.
- Exact integration base: `8b73bcb0b026fe337c023f6a30205dbe89d31eb5`.
- Architecture authority: `docs/MECANUM_NAV_DRL_Architecture.docx`, SHA-256 `432eeac363a595cfcf7e81c4b66054fb674dba140a2ef3cffecd617ab8136204`.
- Current evidence ceiling: `IMPLEMENTED_OFFLINE_JSON_COLLECTION_CORRECTION_RUN003_GUARD_PENDING`.

This candidate contains source, governance, offline-test and build evidence only. It creates no new runtime evidence or authorization, resolved profile, `ResolvedConfigV3`, `config_hash`, endpoint pin, Gate B transition or runtime approval. `runtime_eligible: false`; runtime evidence status is `NOT_CREATED`; `RUNTIME_APPROVED: NOT_APPROVED`; `GATE_B: NOT_STARTED`.

## Locked topology and contracts

The existing WP06-6C bootstrap is started separately and owns the sole `robot_state_publisher`, with `use_sim_time=true` and static `base_link -> lidar_frame`. The WP06-6F composite starts only the existing wheel/IMU ingress, a dedicated `/clock` bridge, and one `robot_localization/ekf_node`; it starts neither bootstrap nor a second RSP. The only new bridge mapping is Gazebo `/clock` (`gz.msgs.Clock`) to ROS `/clock` (`rosgraph_msgs/msg/Clock`), direction `GZ_TO_ROS`. There is no bridge route for `/odom`, `/ground_truth/odom`, `/tf`, `/tf_static`, `/cmd_vel`, or `/map`, and no legacy `gazebo.launch.py` route.

The EKF uses simulation time, `reset_on_time_jump: true`, `publish_tf: true`, `two_d_mode: true`, `world_frame: odom`, and only `/wheel/odometry_raw` plus `/imu/data`; wheel fusion remains linear velocity X/Y and IMU fusion remains yaw/yaw-rate. The EKF is the intended sole dynamic `odom -> base_link` owner. The bootstrap RSP is the intended sole static `base_link -> lidar_frame` owner, with the locked Xacro transform. `map -> odom` is outside this candidate. These ownership statements are design contracts, not runtime findings.

## Historical Run 001

Run 001 is an immutable observer API failure: the target Jazzy `rclpy` does not support `create_subscription(..., with_info=True)`. This does not establish a TF/EKF failure. Its historical artifacts were not changed and the run was not retried. The C++ `rclcpp::MessageInfo` observer and Python offline JSON validator are the corrective implementation.

## Run 002 — consumed historical observer execution failure

Run 002 was executed exactly once at review commit `8939b7d8d0268eb595f906bcc97581d6dc62b581`. Its external capacity-one guard is `CONSUMED` with `acquisition_count=1`. The run failed during observer execution when nested JSON collection arrays led to `json.exception.type_error.304` while accessing the TF row. This is an observer execution failure only; Run 002 does not establish failure of TF, EKF, clock, or `robot_state_publisher`. Run 002 is immutable and was not retried. Its external evidence and consumed guard remain unchanged.

## Current observer and source pins

The C++ observer initializes its JSON collections as actual empty arrays and validates row shape before GID access. Its dynamic `/tf` subscription uses `KEEP_LAST(100)`, `BEST_EFFORT`, `VOLATILE`; `/tf_static` uses `KEEP_LAST(1)`, `RELIABLE`, `TRANSIENT_LOCAL`. Static transform ownership requires a unique `/tf_static` MessageInfo GID mapping to the root-namespace `robot_state_publisher` endpoint of type `tf2_msgs/msg/TFMessage`; no node-name fallback is allowed. Python validates observer JSON offline only.

- Current C++ observer, `ros2_ws/src/wp06_6f_tf_ekf_runtime_observer/src/wp06_6f_tf_ekf_runtime_observer.cpp`: SHA-256 `70c74e56988ce750aa9c808e929d68df06a04f7a6d8bfeb175c74e40c2b014b7`.
- Current Python validator, `ros2_ws/src/mecanum_nav_bringup/mecanum_nav_bringup/sim_eval_tf_ekf_runtime_observer.py`: SHA-256 `163e02eb8db27a8e9f355c6f343d30a6291b37289f2bdc3e486bab85922d7c9e`.

## Run 003 — sole pending authorization guard

Run 003 is the only pending WP06-6F guard. It is seeded `PENDING_EXACT_INTEGRATION_AND_USER_AUTHORIZATION`, capacity `1`, `acquisition_count=0`, `runtime_authorization=NOT_GRANTED`. It has not been consumed. No new runtime authorization is granted by this decision.

The canonical Run 003 guard manifest and evidence JSON bind the current source pins and this decision. The decision SHA is reconciled in both records; the manifest SHA is reconciled in the Run 003 guard.

## Current status

Evidence ceiling remains `IMPLEMENTED_OFFLINE_JSON_COLLECTION_CORRECTION_RUN003_GUARD_PENDING`. Run 002 remains a consumed historical observer execution failure; Run 003 remains pending and is the sole pending guard. No runtime was run by this governance reconciliation. `RUNTIME_APPROVED: NOT_APPROVED`; `GATE_B: NOT_STARTED`.
