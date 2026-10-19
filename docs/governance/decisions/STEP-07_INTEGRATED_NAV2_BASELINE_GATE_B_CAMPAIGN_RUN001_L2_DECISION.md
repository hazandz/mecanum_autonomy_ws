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

## Lifecycle endpoint/QoS contract correction — offline candidate

The canonical `SafetyLifecycleState` topic is `/mecanum/safety_lifecycle_state`, type `mecanum_nav_rl_interfaces/msg/SafetyLifecycleState`, published by the unique `safety_lifecycle` endpoint offering RELIABLE + VOLATILE + KEEP_LAST(10). The C++ runtime observer and Gate-B observer use distinct dedicated subscriptions with that QoS. The validator recomputes owner and QoS acceptance from raw graph endpoint snapshots and rejects any endpoint on obsolete `/mecanum/safety/lifecycle_state`. Receipt remains `/mecanum/final_issued_command`, owned by `final_twist_publisher`, RELIABLE + TRANSIENT_LOCAL + KEEP_LAST(1); the observer validates its offered and requested QoS separately.

The guard/evidence/manifest source-pin set remains exactly 16 entries. Seven changed pinned source/test files have these refreshed SHA-256 and byte sizes:

| Path | SHA-256 | Size (bytes) |
|---|---|---:|
| `artifacts/simulation/step07_nav2_baseline_campaign/tools/step07_gate_b_evidence_validator.py` | `210694c3b9c270e20d4650ca7bb8362ee703c62a0a22bfe6e4f21a8cab970190` | 23255 |
| `artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_gate_b_evidence_validator.py` | `448d2302755c0fc3ce270109bca7266d877db4743050da2f9216c3aa2d97aab3` | 13715 |
| `ros2_ws/src/step07_nav2_baseline_runtime_observer/src/step07_nav2_baseline_runtime_observer.cpp` | `d713d8c67145bfdaf55d4f55c0ab5fcb4b2114013a1aa9d69cff3c27fd925519` | 29652 |
| `ros2_ws/src/step07_nav2_baseline_runtime_observer/test/test_step07_nav2_baseline_runtime_observer.cpp` | `5f2f16d1a06b17cdf5831747c89c76e7c1cdc7743ee7505c685be15e3f8708af` | 7981 |
| `ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/observations/step07_gate_b_observer_node.py` | `32f1c754bfe65268317d2a2cebe34982285a0273a071fb9fb2f25649df4dc4f4` | 21067 |
| `ros2_ws/src/mecanum_nav_rl/test/test_step07_gate_b_observer_node.py` | `4f0f661f507846dd0623877a5a6b93a56e9029f93d1f7f988c745896ab06ae70` | 4580 |
| `ros2_ws/src/mecanum_nav_bringup/test/test_sim_eval_tf_ekf_runtime_contract.py` | `8f03f5feef72d81eb86600f2dfcabffe18765fd4db57c1484bd67ec5250dd6db` | 27451 |

The guard seed remains PENDING, capacity one, acquisition count zero, and `runtime_authorization=NOT_GRANTED`. Runtime, Gate-B transition, integration, and runtime approval are not claimed.

### Historical provisional verification disposition — superseded by contract-test closure

This paragraph records the earlier provisional verification before the Owner-authorized contract-test path was added to scope. At that point the bringup suite had two failures in `test_sim_eval_tf_ekf_runtime_contract.py`; the following contract-test closure records the superseding verification for the amended 14-path candidate. The earlier failure report is historical and is not the current candidate disposition.


### Contract-test scope closure — offline verification

The previously recorded two bringup-test failures were a provisional verification result from before the Owner-authorized contract-test scope amendment. The amended contract test now separately preserves the exact 23-path root campaign diff (`f7f98c683d59cf4c62e462da9f37d4ffb2455c80` to `6fbddb3db1a38908ed470f549a1c8182e022a37f`) and enforces the exact 14-path corrective diff. It checks the canonical lifecycle topic and distinct lifecycle/receipt QoS. The existing 16-entry source-pin set includes this path; its refreshed pin is SHA-256 `8f03f5feef72d81eb86600f2dfcabffe18765fd4db57c1484bd67ec5250dd6db` and size 27451 bytes.

Verification on the current candidate: six-package external colcon build PASS; focused Step-7 suite 49 passed; `mecanum_nav_rl/test` 707 passed; `mecanum_nav_bringup/test` 239 passed; observer and ROSIDL colcon tests 25 passed with zero failures; installed ROSIDL imports, observer executable, Gate-B observer import, and installed-source byte equality PASS. Root 23-path scope, corrective 14-path scope, historical WP06 preservation, source pins, canonical JSON, Ledger prefix, and diff checks PASS. Offline-only; no runner/runtime execution, guard acquisition, Gate-B transition, integration, or runtime approval.

### Run001 acceptance-matrix closure — offline corrective

The current governance matrices mirror the acceptance map emitted by the C++ observer and recomputed by `validate_observer`. The lifecycle endpoint owner/type/subscriber/QoS condition is represented once as `lifecycle_endpoint_qos_contract`; receipt endpoint QoS and absence of `/mecanum/safety/lifecycle_state` are separate rows. The retired `lifecycle_state_publisher_owner` row is not a current acceptance. Raw observer failure literals follow `ACCEPTANCE_FAILED:<acceptance_id>`; the validator may reject an observed obsolete endpoint earlier as `LIFECYCLE_TOPIC_OBSOLETE_OR_IN_USE`. This is documentation/test closure only; Run001 remains pending, no evidence directory is created, and no runtime or Gate-B result is claimed.

### Acceptance-matrix scope-chain closure — offline candidate

This continuation preserves three distinct diffs: the root campaign `f7f98c683d59cf4c62e462da9f37d4ffb2455c80` to `6fbddb3db1a38908ed470f549a1c8182e022a37f` is 23 paths; the lifecycle-QoS correction from `6fbddb3db1a38908ed470f549a1c8182e022a37f` to `5fa2e89f84d683723eba8eb989cfef59059ae603` is 14 paths; the current acceptance-matrix correction is scoped to the exact nine paths based on `5fa2e89f84d683723eba8eb989cfef59059ae603`. The chain test uses dirty-worktree status before commit and `HEAD^..HEAD` after commit, and rejects untracked repository artifacts. No runtime or Gate-B outcome is claimed.
