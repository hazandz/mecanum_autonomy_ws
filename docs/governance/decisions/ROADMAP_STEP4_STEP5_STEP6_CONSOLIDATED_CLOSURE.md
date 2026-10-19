# Roadmap Steps 4–6 consolidated closure — L2 candidate

## Classification and authority

Classification: `L2_SOURCE_CONFIG_INTERFACE_GOVERNANCE_CONSOLIDATED_CLOSURE`. This candidate records the Owner decisions supplied for the selected `sim_eval` / `NAV2_BASELINE` path and implements source, configuration, interface, static-launch, and offline-test closure only. The frozen Architecture remains highest authority (SHA-256 `432eeac363a595cfcf7e81c4b66054fb674dba140a2ef3cffecd617ab8136204`). It does not itself establish runtime acceptance.

The roadmap numbering is: (1) decision bundle; (2) WP05 static bringup; (3) ingress candidates; (4) artifact bundle; (5) static profile closure; (6) WP06 bringup, safety, runtime implementation/integration; (7) integrated runtime campaign, evidence, independent audit, and Owner approval. These roadmap items are not delivery-workflow stages. The historical Step-7 Gate B survey is preparatory inventory; project Step 7 remains `NOT_STARTED`. PEP work package WP-07 is distinct and unchanged.

## Closed source/config decisions

- Step 4 map root is `artifacts/maps/warehouse_map2/`, identity `warehouse_map2`, artifact UUID `4a8a23d0-7e27-4a50-8201-dd1abf1a3db4`, content hash `2bd9ff0a40eaeb61c2359aab4bb213da623ab56746debe591edd4a54c2229f90`. The selected map is not the Gazebo world. `tugbot_depot.sdf` is user-attested map-creation-world provenance; `sim_eval_scan_probe.world.sdf` is diagnostic only; `warehouse_world.sdf` is reference only. The selected world is `tugbot_depot.sdf`, world name `world_demo`. Its Fuel URI must resolve from an existing local cache at the future runtime campaign preflight; no network fetch, fallback asset, geometry substitution, or world geometry change is permitted.
- Map/world runtime compatibility remains `NOT_VALIDATED`; world-frame state remains `DECLARED_UNVERIFIED`; no `world -> map` is published. AMCL Omni owns `map -> odom`, EKF owns `odom -> base_link`, and `robot_state_publisher` owns `base_link -> lidar_frame`.
- Step 5 profile is `sim_eval`, mode `NAV2_BASELINE`, `use_sim_time=true`. The source provides the selected V3 profile/mode and a full resolved JSON with 16 Architecture roots, nested `observation.input_profile`, no unresolved token, and JCS SHA-256 config hash. Source/test reproducibility is offline evidence only. `/scan` is LaserScan in `lidar_frame`; Map Server owns `/map`; AMCL Omni owns `map -> odom`; EKF owns `odom -> base_link`; RSP owns `base_link -> lidar_frame`. No canonical Gazebo bridge is introduced for `/odom`, `/ground_truth/odom`, or Gazebo `/tf`. Measured twist source is `/odometry/filtered` only, finite with 36 covariance entries, freshness contract 250 ms; no odometry/Ground Truth substitute. LocalReference is the successful Nav2 `ComputePathToPose` result as `nav_msgs/msg/Path` in `map`, transformed to `base_link` only with valid TF; it is not PPO ingress here. LiDAR contract is finite `/scan`, age at most 500 ms; obstacle range 0.10–3.0 m and raytrace range 3.5 m.
- Step 6 source defines receipt v2 as a generated/installed interface; only stale status comments in `FinalIssuedCommandReceipt.msg` change. Its fields, constants, order, bounded-string capacity, identity and QoS contract are unchanged. `SafetyLifecycle` owns lifecycle identity and the episode/reset barrier; motion requires a fresh READY barrier. `SafetySupervisor` selects/limits the remapped Nav2 candidate and fails safe for invalid/stale/non-ready inputs. `FinalTwistPublisher` is the sole ROS `/cmd_vel` publisher and publishes the final command before its receipt. Nav2 controller output is remapped to `/mecanum/nav2_candidate_cmd`; the `/cmd_vel` ROS-to-Gazebo bridge is subscriber-only on the ROS side. No PPO implementation or safety substitution is added.
- Numeric safety limits and freshness values in the selected sim profile are the Owner-supplied simulation contract; this does not validate them on hardware. Hardware geometry, E-stop, MCU watchdog, TB6612 thermal/current, power integrity, braking, and latency are deferred to WP12 and do not block this sim-eval source closure.

## Candidate evidence and limits

The companion evidence JSON inventories exact candidate source byte hashes and the map/world asset pins. The Step-4 manifest separately pins map/world bytes. This candidate does not rewrite WP06 historical guards, manifests, transcripts, records, external evidence, or outcomes. WP06-6F Run007 remains bounded to the independently audited ingress/clock/EKF/TF scope; it does not establish Nav2, map, full graph, SafetyLifecycle, or PPO runtime behavior. Absence of `map -> odom` in that WP06 run was outside its selected profile and is not a runtime failure. PPO only produces a normalized action under its future contract; it is not a safety layer. Only `FinalTwistPublisher` may publish `/cmd_vel`.

Evidence ceiling: `STATIC_SOURCE_OFFLINE_BUILD_TEST_READY_FOR_STEP7_RUNTIME_CAMPAIGN`. No runtime, Nav2-live, AMCL-convergence, full-TF-runtime, Gate B, PPO-training, HIL, or hardware validation is claimed. Current statuses are exactly: `STEP4_ARTIFACT_BUNDLE_DECISION = CLOSED_FOR_SIM_EVAL`; `STEP5_STATIC_PROFILE_CLOSURE = IMPLEMENTED_OFFLINE_ONLY`; `STEP6_SOURCE_AND_OFFLINE_INTEGRATION_CLOSURE = IMPLEMENTED_OFFLINE_ONLY`; `STEP7 = NOT_STARTED`; `RUNTIME_APPROVED = NOT_APPROVED`; `GATE_B = NOT_STARTED`.

## Remaining roadmap Step-7 prerequisites

1. Preflight that the approved local cache resolves the world Fuel asset without network access or fallback.
2. A separate Owner-approved capacity-one runtime authorization for the exact integrated source and run.
3. Explicit runtime initial-pose input (`initial_pose_map_x`, `initial_pose_map_y`, `initial_pose_map_yaw`) and partition.
4. Full composite runtime campaign evidence across map/world alignment, localization, lifecycle barriers, command routing, and teardown.
5. Independent evidence audit of the exact runtime artifacts.
6. Separate Owner decision after audit.

Terminal candidate disposition: `ROADMAP_STEP4_STEP5_STEP6_CONSOLIDATED_CLOSURE_CANDIDATE_PENDING_INDEPENDENT_AUDIT`.
