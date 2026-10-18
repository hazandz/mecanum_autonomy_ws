# WP06-6F TF/EKF runtime state-estimation ingress — L2 decision

## Classification and authority

- Work item: `WP06-6F_TF_EKF_RUNTIME_STATE_ESTIMATION_INGRESS_WITH_CLOCK`.
- Classification: `L2_PROFILE_SPECIFIC_TF_EKF_RUNTIME_STATE_ESTIMATION_INGRESS`.
- Exact base: `8b73bcb0b026fe337c023f6a30205dbe89d31eb5`.
- Architecture authority: `docs/MECANUM_NAV_DRL_Architecture.docx`, SHA-256 `432eeac363a595cfcf7e81c4b66054fb674dba140a2ef3cffecd617ab8136204`.
- Evidence ceiling: `IMPLEMENTED_OFFLINE_TF_EKF_CLOCK_SOURCE_AND_GUARD_ONLY`.

This is a review candidate with source, governance, offline-test, and build evidence only. It creates no runtime evidence, runtime authorization, resolved profile, `ResolvedConfigV3`, `config_hash`, endpoint pin, Gate B transition, or runtime approval. `runtime_eligible: false`; `RUNTIME_APPROVED: NOT_APPROVED`; `GATE_B: NOT_STARTED`.

## Selected topology

The future runtime starts the existing WP06-6C bootstrap separately and once. That bootstrap remains the owner of the only `robot_state_publisher`, with `use_sim_time=true`, and the static `base_link -> lidar_frame` edge from the robot Xacro. The WP06-6F composite launch does not start another bootstrap or robot-state publisher. It includes only the existing WP06-6C wheel/IMU ingress, one dedicated clock bridge, and one `robot_localization/ekf_node`.

The dedicated clock bridge has one `GZ_TO_ROS` mapping: Gazebo `/clock` (`gz.msgs.Clock`) to ROS `/clock` (`rosgraph_msgs/msg/Clock`). It is independent of the legacy `gazebo.launch.py`; that launch remains unselected and is not installed or invoked by this candidate. No GZ-to-ROS bridge is added for `/odom`, `/ground_truth/odom`, `/tf`, `/tf_static`, `/cmd_vel`, or `/map`.

The fixed partition is `wp06_scan_probe_run_002`, matching the existing bootstrap. Composite launch rejects a different or empty partition and rejects `use_sim_time` other than `true`.

## EKF and TF contract

The existing EKF settings are retained, with explicit `reset_on_time_jump: true` and `use_control: false`. Inputs are `/wheel/odometry_raw` and `/imu/data`; ROS `/clock` is the simulation-time source. Wheel fusion remains linear velocity X/Y only. IMU fusion remains yaw and yaw angular velocity only. No absolute Gazebo pose, `/odom`, or `/ground_truth/odom` is fused. No new covariance tuning is introduced.

The EKF is the sole intended dynamic TF authority for `odom -> base_link` and publishes `/odometry/filtered` as `nav_msgs/msg/Odometry`, with frames `odom` and `base_link`. The existing bootstrap RSP remains the sole intended static TF owner for `base_link -> lidar_frame`, with the Xacro transform translation `[-0.031765, 0, 0.140]` and identity rotation. `map -> odom` is outside this candidate and is not created.

## Future runtime guard and evidence requirements

Run 001 is a separate capacity-one guard seeded `PENDING_EXACT_INTEGRATION_AND_USER_AUTHORIZATION`. The candidate does not acquire or consume it. A future supervisor must verify exact origin, review/integration topology and ancestry, clean worktree, Architecture/decision/source pins, host capability, required imports, package availability, partition/command context, absent run directory, and stale-process absence before atomic guard acquisition.

After separate exact-commit Owner authorization, the future runner may start the bootstrap once, require literal `Entity creation successful.` and 20 seconds of continued liveness, then start the composite once. It must observe ROS `/clock`, wheel/IMU/filtered odometry, node topology and TF through a ROS API observer. The observer must record per-transform parent, child, timestamp and publisher GID; require at least five strictly increasing `odom -> base_link` samples from one GID; require exactly one `base_link -> lidar_frame` static transform matching the Xacro; and reject `map -> odom`. Global `/tf` publisher count is not evidence of edge ownership. Raw transcripts and process-group teardown evidence must be retained. Teardown stops the composite before bootstrap and verifies no live or zombie group members. Any failure after acquisition consumes the guard and ends the attempt without retry.

## Historical and status boundaries

WP06-6C Run 003 remains independently audited only for bounded wheel/IMU ingress, effective simulation time and teardown. That result does not establish EKF, TF ownership, global ROS graph, Nav2, AMCL, Map Server or full navigation-profile compatibility. Historical WP06-6C/6D/6E sources and runtime artifacts remain unchanged.

No runtime was executed for this candidate. A future runtime requires independent audit and separate Owner authorization for the exact review commit. This decision does not grant that authorization or establish runtime compatibility.
