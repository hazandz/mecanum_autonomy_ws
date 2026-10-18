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


## Corrective observer continuation — multi-sample evidence closure

The prior runner used one `ros2 topic echo --once` sample for `/clock` and `/odometry/filtered`; that cannot establish five samples, strict timestamp increase, per-edge TF publisher-GID ownership, or late-subscriber receipt of transient-local static TF. The corrective source adds one ROS API observer invocation after the composite is live. It records canonical raw observations and structured validation in `transcripts/runtime_observer.json`; it subscribes to `/clock`, `/odometry/filtered`, `/tf` with message-info GIDs, and `/tf_static` using KEEP_LAST depth 1, RELIABLE, TRANSIENT_LOCAL QoS. Missing publisher GID fails closed. No runtime was run and the Run 001 guard remains pending, capacity 1, unconsumed.

### Runtime acceptance-to-collector matrix

| acceptance_id | collector | raw_artifact_path | parser_or_validator | pass_condition | failure_reason_literal | offline_test_name |
|---|---|---|---|---|---|---|
| bootstrap_readiness | session_runner | logs/bootstrap.log | literal-byte readiness matcher | contains exact Entity creation successful. line before 90s timeout | BOOTSTRAP_READINESS_FAILED | test_bootstrap_readiness_and_stability_fail_closed |
| bootstrap_stability_20_seconds | session_runner | run_record.json:acceptance.bootstrap_stability_20_seconds | monotonic clock + Popen.poll | bootstrap remains alive for 20 seconds after readiness | BOOTSTRAP_DIED_DURING_STABILIZATION | test_bootstrap_readiness_and_stability_fail_closed |
| composite_liveness | session_runner | run_record.json:acceptance.composite_live_through_evidence | Popen.poll at observation boundaries | composite remains alive through observer and transcript collection | COMPOSITE_EXITED_DURING_EVIDENCE | test_composite_liveness_and_teardown_acceptance_fail_closed |
| clock_five_monotonic_samples | rclpy runtime observer subscription /clock | transcripts/runtime_observer.json#/topics/~1clock/samples | evaluate_observations | at least 5 nonzero clock samples with strictly increasing unique (sec,nanosec) | CLOCK_TIMEOUT_MINIMUM_FIVE_SAMPLES | test_clock_requires_five_nonzero_strict_timestamps |
| wheel_input | session runner ROS topic info and one sample | transcripts/wheel_info.*.bin;transcripts/wheel_echo.*.bin | _verify_topic_info + safe_load_all input validator | nav_msgs/msg/Odometry, one data publisher, odom->base_link and finite twist | WHEEL_INPUT_TYPE_PUBLISHER_OR_SAMPLE_CONTRACT_FAILED | test_wheel_and_imu_input_acceptance_is_fail_closed |
| imu_input | session runner ROS topic info and one sample | transcripts/imu_info.*.bin;transcripts/imu_echo.*.bin | _verify_topic_info + safe_load_all input validator | sensor_msgs/msg/Imu, one data publisher, base_link, finite payload and normalized quaternion | IMU_INPUT_TYPE_PUBLISHER_OR_SAMPLE_CONTRACT_FAILED | test_wheel_and_imu_input_acceptance_is_fail_closed |
| ingress_use_sim_time | session runner ros2 param get transcript | transcripts/ingress_use_sim_time.stdout.bin | exact true suffix validator | effective ingress use_sim_time is true | INGRESS_USE_SIM_TIME_FALSE_OR_UNAVAILABLE | test_runtime_acceptance_matrix_covers_all_required_criteria |
| filtered_odometry_five_monotonic_samples | rclpy runtime observer subscription /odometry/filtered | transcripts/runtime_observer.json#/topics/~1odometry~1filtered/samples | evaluate_observations | one typed data publisher plus at least 5 valid odom->base_link payloads with monotonic timestamps and finite pose/twist/36-value covariance | FILTERED_ODOMETRY_TIMEOUT_MINIMUM_FIVE_SAMPLES | test_filtered_odometry_requires_five_valid_monotonic_samples |
| ekf_use_sim_time | session runner ros2 param get transcript | transcripts/ekf_use_sim_time.stdout.bin | exact true suffix validator | effective EKF use_sim_time is true | EKF_USE_SIM_TIME_FALSE_OR_UNAVAILABLE | test_runtime_acceptance_matrix_covers_all_required_criteria |
| ekf_topology | session runner ros2 node info transcript | transcripts/ekf_node_info.stdout.bin | node section topic parser | only wheel, IMU, clock subscriptions and filtered odometry plus /tf publications | EKF_NODE_TOPOLOGY_OUT_OF_CONTRACT | test_node_info_topic_parser_is_edge_and_section_specific |
| dynamic_tf_edge_gid | rclpy MessageInfo observer /tf | transcripts/runtime_observer.json#/topics/~1tf/transforms | evaluate_observations | at least 5 strictly increasing odom->base_link transforms from exactly one publisher GID | TF_DYNAMIC_EDGE_TIMEOUT_MINIMUM_FIVE_EDGES | test_dynamic_tf_requires_five_samples_and_one_gid |
| static_tf_edge_qos | rclpy transient-local MessageInfo observer /tf_static | transcripts/runtime_observer.json#/topics/~1tf_static | evaluate_observations + STATIC_QOS_CONTRACT | one unique base_link->lidar_frame transform with specified Xacro transform and KEEP_LAST(1)/RELIABLE/TRANSIENT_LOCAL QoS | TF_STATIC_EDGE_MISSING_OR_TRANSFORM_MISMATCH | test_static_tf_requires_transient_local_qos_and_exact_transform |
| map_to_odom_absent | rclpy observers /tf and /tf_static for full window | transcripts/runtime_observer.json#/acceptance/map_to_odom_absent_during_observation_window | evaluate_observations | no map->odom edge throughout completed observation window | MAP_TO_ODOM_EDGE_OBSERVED | test_map_to_odom_and_observation_timeouts_fail_closed |
| forbidden_bridge_and_process_boundary | session runner node-info transcripts and composite process-group snapshot | transcripts/*node_info*;run_record.json:process_group_commands | node section topic parser + command marker matcher | no forbidden bridge/topic route or Nav2/AMCL/SLAM/Map Server/command publisher process in candidate process group | FORBIDDEN_BRIDGE_TOPIC_OR_PROCESS_OBSERVED | test_forbidden_runtime_boundary_is_fail_closed |
| process_group_teardown | session runner process-group reaper | run_record.json:teardown | final /proc live/zombie snapshots | composite group stopped before bootstrap group, no live or zombie members | PROCESS_GROUP_TEARDOWN_FAILED | test_composite_liveness_and_teardown_acceptance_fail_closed |
