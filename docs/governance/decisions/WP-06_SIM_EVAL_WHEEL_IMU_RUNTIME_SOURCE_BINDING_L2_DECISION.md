# WP-06 sim_eval wheel and IMU runtime ingress — L2 decision

## Decision identity

- Classification: `L2_SIM_EVAL_WHEEL_IMU_RUNTIME_SOURCE_BINDING_AND_INGRESS_IMPLEMENTATION`.
- Exact source base: `43c94789f628b4211189fc391326e0b119cbb6d3`.
- Architecture: `docs/MECANUM_NAV_DRL_Architecture.docx`, SHA-256 `432eeac363a595cfcf7e81c4b66054fb674dba140a2ef3cffecd617ab8136204`.
- Evidence level: `IMPLEMENTATION_SOURCE_AND_OFFLINE_BUILD_UNIT_TEST_ONLY`.
- The design is based on the Owner/Architect packet supplied for this work package. It is not inferred from Git ancestry.

## Approved implementation boundary

This candidate adds one simulation-only ingress path in `mecanum_base_bridge`: wheel velocities from the staged Gazebo `JointState` source are converted to `/wheel/odometry_raw`, and validated IMU data is copied to `/imu/data`. The wheel emulator uses the specified four-wheel order, geometry, signs and kinematic equations, integrates planar pose in SE(2), requires strictly increasing source stamps and a positive interval no larger than 0.20 s, and rejects incomplete, duplicate, malformed or non-finite data. It does not read joint position, model/world pose, `/odom` or `/ground_truth/odom`.

The IMU sensor is attached to `base_link` with identity pose and emits the specified Gazebo endpoint. The pure normalizer accepts only `base_link` samples with finite values, strictly increasing ROS stamps and a quaternion norm in `[0.999, 1.001]`; it does not repair a frame, quaternion, stamp or stale sample. The ROS node exposes exactly two staging subscriptions and two canonical publishers. It publishes no TF.

The existing `tugbot_depot.sdf` at the source base already contains exactly one world-level `gz-sim-imu-system` plugin. Its bytes are preserved; no duplicate plugin is added. The existing historical static ingress contract v1 is also byte-preserved. A separate versioned source-binding descriptor records the new sim_eval bindings and keeps `runtime_eligible: false` and runtime evidence `NOT_CREATED`.

## Ownership and prohibited inference

- `robot_localization` remains the sole owner of `odom → base_link`; this package's wheel odometry output does not publish TF.
- `/odom` and `/ground_truth/odom` are prohibited as EKF inputs. The encoder emulator derives motion only from the staged wheel `JointState` values.
- The IMU source is attached to `base_link`; this source change alone is not runtime frame evidence.
- Candidate 6E is the sole owner of the ROS–Gazebo bridge implementation. This candidate adds no bridge configuration or bridge launch.
- Staging input QoS is BEST_EFFORT/VOLATILE/KEEP_LAST(10); canonical output QoS is RELIABLE/VOLATILE/KEEP_LAST(10). The node uses simulation time by default and compares sensor stamps, not wall-clock time.

## Non-goals and status

This candidate does not modify Step 5A static profile closure or the static ingress v1 snapshot. It does not authorize Gate B, profile resolution, `ResolvedConfigV3`, `config_hash`, map/runtime compatibility, TF runtime evidence or `deploy_real`. It does not establish bridge implementation, runtime evidence, runtime authorization, HIL or hardware evidence. No runtime node is launched by the candidate checks. `runtime_eligible: false` remains in the source-binding descriptor, `RUNTIME_APPROVED: NOT_APPROVED`, and WP-04/WP-05/Gate A/Gate B statuses remain unchanged.

The source includes an installable ROS executable but no execution evidence. The review candidate lifecycle and its exact source/test/build evidence are recorded separately in the candidate's evidence JSON and append-only Ledger entry. A later run requires its own explicit runtime authorization and packet.
