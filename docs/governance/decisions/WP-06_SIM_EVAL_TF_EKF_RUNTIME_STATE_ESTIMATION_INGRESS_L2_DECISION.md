# WP06-6F TF/EKF runtime state-estimation ingress — L2 decision

## Classification and authority

- Work item: `WP06-6F_TF_EKF_RUNTIME_STATE_ESTIMATION_INGRESS_WITH_CLOCK`.
- Classification: `L2_PROFILE_SPECIFIC_TF_EKF_RUNTIME_STATE_ESTIMATION_INGRESS`.
- Exact base: `8b73bcb0b026fe337c023f6a30205dbe89d31eb5`.
- Architecture authority: `docs/MECANUM_NAV_DRL_Architecture.docx`, SHA-256 `432eeac363a595cfcf7e81c4b66054fb674dba140a2ef3cffecd617ab8136204`.
- Evidence ceiling: `IMPLEMENTED_OFFLINE_CPP_GID_OBSERVER_AND_PENDING_RUN002_GUARD_ONLY`.

This is source, governance, offline-test and build work only. It creates no runtime evidence or authorization, resolved profile, `ResolvedConfigV3`, `config_hash`, endpoint pin, Gate B transition or runtime approval. `runtime_eligible: false`; `RUNTIME_APPROVED: NOT_APPROVED`; `GATE_B: NOT_STARTED`.

## Selected topology and locked contracts

The future runtime starts the existing WP06-6C bootstrap separately and once. That bootstrap remains the owner of the only `robot_state_publisher`, with `use_sim_time=true`, and the static `base_link -> lidar_frame` edge from the robot Xacro. The WP06-6F composite launch starts only existing WP06-6C wheel/IMU ingress, one dedicated `/clock` bridge, and one `robot_localization/ekf_node`; it does not start bootstrap or another robot-state publisher.

The clock bridge has one `GZ_TO_ROS` mapping: Gazebo `/clock` (`gz.msgs.Clock`) to ROS `/clock` (`rosgraph_msgs/msg/Clock`). It is independent of legacy `gazebo.launch.py`. No bridge is defined for `/odom`, `/ground_truth/odom`, `/tf`, `/tf_static`, `/cmd_vel`, or `/map`.

The EKF retains `use_sim_time: true`, `reset_on_time_jump: true`, `publish_tf: true`, `two_d_mode: true`, `world_frame: odom`, and inputs `/wheel/odometry_raw` and `/imu/data`. Wheel fusion remains linear velocity X/Y only; IMU fusion remains yaw and yaw angular velocity only. No absolute Gazebo pose or new covariance tuning is introduced. The EKF is the intended sole dynamic owner of `odom -> base_link`; the bootstrap RSP retains sole static ownership of `base_link -> lidar_frame` using translation `[-0.031765, 0, 0.140]` and identity rotation. `map -> odom` is outside scope.

## Run 001 historical disposition and observer correction

Run 001 is an immutable historical failure caused by the observer API mismatch: Python `rclpy` in the target Jazzy environment does not accept `create_subscription(..., with_info=True)`. This is an observer execution failure; it is not evidence of a TF or EKF runtime failure. No Run 001 guard, lock, record, manifest, raw evidence or artifact is changed, and Run 001 is not retried.

The replacement observer is a dedicated `ament_cmake` C++ executable using `rclcpp::MessageInfo` and underlying RMW publisher GID. It snapshots `/tf` graph endpoints and accepts dynamic edge ownership only when the exact GID maps uniquely to the configured EKF endpoint. An unmappable GID fails closed as `TF_EDGE_PUBLISHER_GID_UNMAPPABLE`; no node-name fallback or global `/tf` publisher count is used. It records canonical schema-versioned JSON atomically, including multi-sample `/clock`, filtered odometry, edge-specific TF, static TF with RELIABLE/TRANSIENT_LOCAL QoS, endpoint mappings, map-to-odom observation, per-condition verdicts, and literal reasons. Python is now only an offline canonical-JSON parser/validator; no Python `with_info=` use remains under `ros2_ws/src`.

Teardown accounting has one predicate: `leader_returncode == 0 AND live_member_pids == [] AND zombie_member_pids == [] AND outcome == STOPPED`. Any recorded aggregate inconsistent with that predicate is `INTERNAL_EVIDENCE_INCONSISTENCY`.

## Run 002 guard and future runtime boundary

Run 002 has a separate capacity-one guard seeded `PENDING_EXACT_INTEGRATION_AND_USER_AUTHORIZATION`, capacity `1`, acquisition count `0`, and `runtime_authorization: NOT_GRANTED`. It has not been acquired or authorized. The future runner must complete static identity/source-pin and host-capability/import checks before acquiring that guard, call bootstrap and composite at most once, invoke the C++ observer exactly once, save its JSON output via the observer's atomic write, and tear down composite before bootstrap. Any post-acquisition failure consumes the guard and ends without retry. No runtime was executed as part of this corrective candidate.

## Evidence ceiling

`IMPLEMENTED_OFFLINE_CPP_GID_OBSERVER_AND_PENDING_RUN002_GUARD_ONLY`. The Run 002 runtime remains unauthorized and unexecuted; independent audit and a separate exact-run Owner authorization are required before any runtime.

## Corrective continuation — dynamic TF subscriber QoS

The dynamic `/tf` observer subscription uses explicit `KEEP_LAST(100)`, `BEST_EFFORT`, `VOLATILE` QoS to match the standard dynamic TF publisher contract. `/tf_static` remains `KEEP_LAST(1)`, `RELIABLE`, `TRANSIENT_LOCAL`. Observer schema v2 records both actual subscription profiles, and the offline validator rejects either mismatch. Dynamic TF edge ownership remains based on the edge publisher GID mapped uniquely to the EKF graph endpoint; acceptance is unchanged.

Current source pins:
- `ros2_ws/src/wp06_6f_tf_ekf_runtime_observer/src/wp06_6f_tf_ekf_runtime_observer.cpp` — `3e2e3227d4933a2cf0863b31810556c01116fb9598bb8ba850c1beb974f0b635`
- `ros2_ws/src/mecanum_nav_bringup/mecanum_nav_bringup/sim_eval_tf_ekf_runtime_observer.py` — `cee7ac20fab7e6a86d066e9e76b12113399a19c1c8cceba60d265247b1ba4bf3`

This is an offline source/test/build correction only. Run 001 remains the immutable observer API mismatch failure and is not a TF/EKF failure. Run 002 remains unauthorized and pending with capacity 1 and acquisition count 0. No runtime authorization, runtime evidence, integration, or Gate B transition is created.
