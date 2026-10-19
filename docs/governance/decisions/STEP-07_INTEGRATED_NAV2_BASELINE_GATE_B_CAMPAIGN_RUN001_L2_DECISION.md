# STEP07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN001 — L2 decision

## Classification and authority

Classification: `L2_RUNTIME_INTEGRATION_GATE_B_SAFETY_EVIDENCE_CAMPAIGN`.
This candidate is based on integration commit
`f7f98c683d59cf4c62e462da9f37d4ffb2455c80` and the Architecture authority
`docs/MECANUM_NAV_DRL_Architecture.docx` SHA-256
`432eeac363a595cfcf7e81c4b66054fb674dba140a2ef3cffecd617ab8136204`.
Owner decisions in the approved campaign prompt are copied as fixed inputs;
this decision does not select or reinterpret them.

## Fixed campaign inputs

- Profile/mode: `sim_eval` / `NAV2_BASELINE`; simulation time is enabled.
- Canonical map root: `artifacts/maps/warehouse_map2/`; map identity,
  content hash and the four file hashes are pinned in the guard and evidence.
- World: `ros2_ws/src/ROBOT_URDF_final_description/launch/tugbot_depot.sdf`.
  Fuel access is local-only under `$HOME/.gz/fuel`; each Owner-pinned URI must
  have exactly one positive integer version directory with `model.config` and
  `model.sdf`. No network fetch, fallback, or geometry substitution is part
  of this candidate.
- Partition: `mecanum_step7_nav2_run001_f7f98c6`.
- Initial map pose `(0,0,0)`; goal map pose `(-4,0,0)`. Map and Gazebo world
  are distinct; no `world -> map` transform is asserted.
- TF ownership: AMCL `map -> odom`; EKF `odom -> base_link`;
  `robot_state_publisher` `base_link -> lidar_frame`.
- The Gate-B vector is exactly 81 finite `float32` values in the established
  order: LiDAR 72, LocalReference 3, measured twist 3, final receipt 3.
- No Ground Truth, `/odom`, or `/ground_truth/odom` policy ingress. No PPO
  training, action decoding, or PPO command publisher.
- `SafetyLifecycle` rearm is requested once only after preconditions pass.
  `sim_estop_release_authorized=true` is supplied only by a future exact-run
  authorization. `FinalTwistPublisher` remains the sole ROS `/cmd_vel` publisher.

## Candidate machinery and guard

The candidate adds a capacity-one Run001 seed, an authorization-bound guard
module, a one-shot runner, a post-run evidence validator, a C++ runtime
collector using `rclcpp::MessageInfo`, and an installed Python Gate-B observer
that delegates conversion and assembly to the existing pure V3 adapters and
assembler. The Python observer requests `ComputePathToPose` once and then
`NavigateToPose` once, accepts no retry, and publishes no topic or command.
The C++ observer snapshots the `/tf` and `/tf_static` graph endpoints and fails
closed when edge GIDs do not map uniquely to the required owner endpoints.

The guard seed remains `PENDING_EXACT_INTEGRATION_AND_USER_AUTHORIZATION`,
capacity `1`, acquisition count `0`, and `runtime_authorization=NOT_GRANTED`.
It can be consumed only by a future official runner call after all source,
host, build, installed-artifact, map/Fuel and exact-run authorization checks.
Any post-acquisition failure is terminal; there is no retry path. This
candidate itself supplies no runtime authorization and invokes no runner.

## Evidence boundary and status

Evidence ceiling: `IMPLEMENTED_SOURCE_AND_OFFLINE_TEST_CAMPAIGN_MACHINERY_ONLY`.
Only source, static checks, unit tests and an offline build can be attributed to
this candidate after verification. It does not assert that Gazebo, ROS graph,
Nav2, AMCL, localization, TF, safety behavior, goal completion, or Gate B has
passed at runtime. Step 7 remains the only place to assess complete runtime
acceptance after a separately authorized capacity-one campaign and independent
evidence audit.

`STEP 4 = CLOSED_FOR_SIM_EVAL`; `STEP 5 = IMPLEMENTED_OFFLINE_ONLY`;
`STEP 6 = IMPLEMENTED_OFFLINE_ONLY`; `STEP 7 = NOT_STARTED`;
`GATE_B = NOT_STARTED`; `RUNTIME_APPROVED = NOT_APPROVED`.

## Offline verification record

This review snapshot records offline verification only: six selected colcon packages built successfully; `mecanum_nav_rl/test` passed 705 tests; `mecanum_nav_bringup/test` passed 237 tests; the C++ runtime observer and ROSIDL interfaces colcon tests passed 11 tests each; 36 focused campaign tests passed. Installed ROSIDL imports, observer executable, Gate-B console script, parser import and checked source-byte comparisons passed. The test interpreter used Pydantic 2.10.6. No runtime, Gate B transition or runtime approval is claimed. The evidence ceiling remains `IMPLEMENTED_SOURCE_AND_OFFLINE_TEST_CAMPAIGN_MACHINERY_ONLY`.

## Separated bootstrap/composite process-group correction

The authorized topology correction adds the required `start_bootstrap` literal boolean (default `true`). The default standalone composite includes bootstrap exactly once; `false` excludes bootstrap while still validating the canonical map identity and local Fuel cache. The official runner starts bootstrap once in its own process group, waits for its existing fail-closed readiness predicate, then starts the composite once with `start_bootstrap:=false` in a distinct process group. It records separate PIDs, PGIDs, commands, readiness results, return codes and final snapshots. Teardown sends SIGINT to and verifies the composite group before doing so for bootstrap; both groups must have no live or zombie members.

Offline verification for this amended 23-path candidate: six-package external colcon build PASS; `mecanum_nav_rl/test` 705 passed; `mecanum_nav_bringup/test` 238 passed; observer and interface colcon tests 11 each passed; focused campaign/launch/contract tests 45 passed. Installed launch/source byte equality, Gate-B observer import and console script, C++ observer executable, and ROSIDL imports passed. The evidence and guard manifest are `ec4c059ff3a0fa39df0b887426ae0517efda9b9820ecab6a2bad6a34135a973c` and `11343554c3d0dec9b82ee7ef90a976e67828913fbfc991962988ba81f40830fb` respectively. Source pins cover 16 implementation/tool/test files. No campaign runner or runtime process was executed; Run001 guard remains pending, Gate B remains `NOT_STARTED`, and `RUNTIME_APPROVED` remains `NOT_APPROVED`.
