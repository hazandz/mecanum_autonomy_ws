# WP06-6F Run006 topology-checker corrective candidate

## Authority and scope

- Work item: `WP06-6F_TF_EKF_RUNTIME_STATE_ESTIMATION_INGRESS_WITH_CLOCK`.
- Classification: `L2_PROFILE_SPECIFIC_TF_EKF_RUNTIME_STATE_ESTIMATION_INGRESS`.
- Corrective base / sole parent: `ca2e9798a49be6c9b3429ef0fd161410539ca12a`.
- Integration base: `8b73bcb0b026fe337c023f6a30205dbe89d31eb5`.
- Architecture SHA-256: `432eeac363a595cfcf7e81c4b66054fb674dba140a2ef3cffecd617ab8136204`.
- Evidence ceiling: `IMPLEMENTED_OFFLINE_RUN005_TOPOLOGY_FALSE_NEGATIVE_CORRECTION_RUN006_GUARD_PENDING`.

This candidate creates a separate Run006 guard and offline session runner. It corrects only the exact-section topology checker. Each `ros2 node info` transcript is parsed by its `Subscribers` and `Publishers` sections. `/parameter_events` is allowed in either section; `/rosout` is allowed only under `Publishers`. These ROS-standard endpoints are removed before exact comparison of the EKF business endpoints. Any other endpoint, including either standard endpoint in the wrong direction, remains fail-closed. Topic matching is exact: `/odometry/filtered` is not `/odom`.

The EKF business subscribers remain exactly `/clock`, `/imu/data`, `/wheel/odometry_raw`, and administrative `/set_pose`; publishers remain exactly `/odometry/filtered`, `/tf`, and `/diagnostics`. The separate `/set_pose` evidence remains mandatory: type `geometry_msgs/msg/PoseWithCovarianceStamped`, one EKF subscription, zero publishers, and timed-out echo with empty stdout. Any observed `/set_pose` publisher fails.

## Run005 immutable disposition

Run005 executed once and remains historical with terminal outcome `WP06_6F_RUNTIME_RUN005_FAIL_NO_RETRY_GUARD_CONSUMED`. Its raw runtime evidence showed the clock, wheel, IMU, EKF, dynamic/static TF, QoS, `/set_pose`, forbidden-topic boundary, and teardown criteria passing. The checker rejected the EKF topology because it compared ROS-standard `/parameter_events` and `/rosout` together with business endpoints. This is a checker false negative, not a TF, EKF, clock, sensor, robot-state-publisher, or runtime topology failure. Run005 guard, lock, record, manifest, transcripts, and external evidence remain immutable and are not retried.

Run001 through Run004 remain immutable historical runs with their previously recorded failures and consumed authorization states. No historical terminal outcome is rewritten.

## Locked runtime topology retained

The bootstrap retains the sole `robot_state_publisher` and owns static `base_link -> lidar_frame`. The composite remains limited to the existing WP06-6C wheel/IMU ingress, the dedicated GZ-to-ROS `/clock` bridge, and one `robot_localization/ekf_node`. No bridge route is added for `/odom`, `/ground_truth/odom`, `/tf`, `/tf_static`, `/cmd_vel`, or `/map`; no second EKF, Nav2, AMCL, SLAM, Map Server, command publisher, or custom TF broadcaster is added.

The EKF remains configured with simulation time, `reset_on_time_jump: true`, `publish_tf: true`, `two_d_mode: true`, and `world_frame: odom`. It fuses only wheel linear velocity X/Y and IMU yaw/yaw-rate, with no new covariance tuning. EKF remains the intended sole dynamic `odom -> base_link` owner; bootstrap RSP remains the intended sole static `base_link -> lidar_frame` owner. These are source/design constraints, not new runtime findings from this corrective candidate.

## Run006 bounded state

Run006 has a new capacity-one guard seeded `PENDING_EXACT_INTEGRATION_AND_USER_AUTHORIZATION`, capacity `1`, acquisition count `0`, and `runtime_authorization=NOT_GRANTED`. It is not authorized or executed by this candidate. `runtime_eligible: false`; runtime evidence status is `NOT_CREATED`; `RUNTIME_APPROVED: NOT_APPROVED`; `GATE_B: NOT_STARTED`.

No launch, bridge mapping, EKF configuration, TF ownership, sensor semantics, or C++ observer behavior changes. This is offline checker, governance, and test evidence only.
