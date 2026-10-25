# ACR — Step 7 research-grade runtime acceptance simplification (L2)

**Decision ID:** `STEP07_RESEARCH_GRADE_RUNTIME_ACCEPTANCE_SIMPLIFICATION_L2`
**Owner authorization:** `OWNER_APPROVED_STEP07_RESEARCH_GRADE_SIMPLIFICATION_L2_OFFLINE_IMPLEMENTATION`
**Authority:** Architecture SHA-256 `432eeac363a595cfcf7e81c4b66054fb674dba140a2ef3cffecd617ab8136204`
**Scope:** Step 7, `sim_eval` / `NAV2_BASELINE` research-grade integrated runtime acceptance.

## Decision

Replace the active Run005 forensic acceptance model with one runner, one in-process ROS observer, one rosbag recorder, a pure A1–A10 evaluator, local bounded synchronization, and six direct evidence heads. This decision retains the frozen Architecture invariants for TF authority, Ground Truth isolation, Observation V3, command ownership, Safety, map identity, and global resolved-config hashing.

The owner-approved SIM_BASELINE values and A1–A10 semantics are recorded here and in the versioned `navigation.step07_acceptance` policy. That policy is part of the existing complete `ResolvedConfigV3` and its existing global `config_hash`; no independent digest is introduced.

## Integrated runtime acceptance A1–A10

An attempt passes only when every condition below passes. A condition not evaluated because an upstream stage failed is `FAIL` with `NOT_EVALUATED_DUE_TO_<stage>`.

| ID | Required evidence |
|---|---|
| A1 Simulator | Canonical Depot v6/Tugbot v1 world, entity, map and spawn selection; simulator starts without a blocking startup failure or duplicate instance. |
| A2 Clock and sensors | Positive advancing `/clock`; fresh valid `/scan`, `/wheel/odometry_raw`, and `/imu/data`, including type, frame, required values and receive/message age. |
| A3 EKF odometry | Multiple advancing `/odometry/filtered` samples in `odom` / `base_link`; finite valid pose, twist and covariance; sole source is EKF, not Ground Truth or legacy Gazebo odometry. |
| A4 TF | Exact-time usable `map→odom→base_link→lidar_frame`; observed edge owners are AMCL, EKF and `robot_state_publisher`, with no duplicate owner or frame alias. |
| A5 Localization | Map Server and AMCL Active; canonical map selected; initial pose applied; `/amcl_pose` in `map`, finite pose/quaternion/covariance, covariance diagonals `0..0.25`, age ≤2 s, translation jump ≤`0.50 m + 0.35 m/s × Δt`, yaw jump ≤`0.50 rad + 1.0 rad/s × Δt`. This is a health check, not absolute-accuracy proof. SIM AMCL uses `update_min_d=0.0`, `update_min_a=0.0`. |
| A6 Nav2 | Required Nav2 nodes Active; one observer `ComputePathToPose` request succeeds; one valid `NavigateToPose` goal is accepted and processed. |
| A7 Observation | At least five distinct, fresh, synchronized valid `float32[81]` observations in V3 order and normalization. Five is a minimum; the report keeps the first five. |
| A8 Command/Safety/receipt | One causal nonzero NAV2 candidate traverses Safety decision, accepted `CommandEnvelope`, sole `FinalTwistPublisher` `/cmd_vel`, and a matching actual `FinalIssuedCommandReceipt`. |
| A9 Navigation outcome | Goal `(−4,0)` in `map`, position-only; accepted terminal SUCCEEDED; position error ≤0.15 m, planar speed ≤0.03 m/s, `|wz|≤0.05 rad/s`; healthy localization and fresh pose/twist remain valid continuously for ≥1.0 s ROS time. Mission deadline 240 s steady. |
| A10 Shutdown | Mission canceled if active; safe stop through existing Safety path and actual zero receipt before teardown; composite before bootstrap; recorder finalized; owned groups reaped and no live/zombie/orphan process remains; observer executor stopped. Functional failure does not itself fail cleanup. |

SIM freshness limits are scan 500 ms, wheel ingress 200 ms, IMU ingress 200 ms, filtered odometry 250 ms, lifecycle 500 ms and receipt 500 ms; any stricter current Safety/config limit remains effective. Pair skew is ≤50 ms. Exact-odometry-time TF lookup is bounded by 200 ms steady time; local-reference age is ≤250 ms. Buffers hold at most 64 inputs. LiDAR uses 72 normalized angular-sector minima; the remaining blocks are `[clip(distance_m/5,0,1), sin(bearing), cos(bearing)]`, measured `[vx,vy,wz]` normalized by `[0.25,0.20,0.80]`, and the actual prior final-issued command normalized by the same scales.

The mission uses the `nav2_controller::StoppedGoalChecker` contract: XY tolerance 0.15 m, yaw tolerance π, stopped linear 0.03 m/s, stopped angular 0.05 rad/s, `stateful=false`; the final-yaw rotate critic is not an acceptance condition. Campaign deadline is 480 s steady, with up to 20 s reserved for shutdown. All waits are bounded by that deadline.

## Runtime adapter and direct evidence model

The runner owns bootstrap, composite and rosbag process groups. One observer runs in the runner process and supplies typed facts to the pure evaluator. The recorder stores only the explicit approved topic set, including hidden action topics, with simulation time and configured QoS overrides. `identity.json`, `resolved_config.json`, `runtime.log`, `capture/`, `acceptance.json`, and `metrics.json` are the only six evidence heads. JSON writes are finite and atomic; duplicate JSON keys are rejected on input. No source-file pins, sidecars, per-sample hashes, native lifecycle retention, or manifest hierarchy is part of active acceptance.

Runtime authorization is separate and must explicitly bind the exact integrated candidate commit, global `config_hash`, run ID and exclusive output target. Sim-only E-stop release/rearm requires the separate explicit authorization bit; the runner never defaults it true. This ACR grants no runtime or integration permission.

## Retired from active acceptance

Retire the 53-member source-pin inventory and refresh/closure phases; `mecanum.step07-run005-temporal-coherence/v1`; native lifecycle reservation and ACK/RELEASE; retained-record and cross-process monotonic protocols; per-sample GID proof; sealed sidecars and terminal/collection handshakes; failure settlement; nested validators; manifest/hash hierarchies; historical replay and availability prerequisites; tracked source-guard mutation; detached runtime checkout; and the C++ forensic observer dependency. Historical source, guards, runtime records, and outcomes remain preserved and are not rewritten.

`RUN005_FORENSIC_CAMPAIGN = RETIRED_AS_ACTIVE_ACCEPTANCE_MODEL`
`HISTORICAL_RECORDS = PRESERVED`
`INVOCATION_021_ROOT_CAUSE = ROOT_CAUSE_UNRESOLVED`

## Evidence boundary

This ACR authorizes only the bounded offline implementation scope specified by the owner. It does not authorize runtime execution, campaign invocation, Gate B, HIL, hardware, integration, or deployment. Until separate runtime authorization and review, the status remains `IMPLEMENTED_OFFLINE_ONLY`, `RUNTIME_AUTHORIZATION = NOT_GRANTED`, `GATE_B = NOT_STARTED`, and `REAL_READY = NOT_CLAIMED`.

## Candidate evidence snapshot

Follow-up candidate branch `step07-research-runtime-simplification`, parent `5916e267f1a0687fe75a76ff9890a849c1ea284c`, retains original implementation base `fdc0e299515bda2286832aabec635948629517b5`. Fresh external build of the five authorized packages completed. On the refreshed overlay, RL plus bringup offline selection reported 978 passed and one ROS-graph-capable lifecycle node deselected: `test_safety_lifecycle_transition.py::test_lifecycle_managed_publisher_follows_standard_transitions`, which calls `rclpy.init()`. The pure-module import test passed separately in isolation because its process-global `sys.modules` assertion is contaminated by package-wide adapter collection. Active Step-7 tools reported 29 passed. The changed lidar/TF test reported 7 passed. Base bridge reported 121 passed and interface tests 8 passed. Full robot-description selection reported 28 passed and three unrelated failures: copyright/flake8 lint findings in the existing directory and an existing probe-world system-list assertion; the changed lidar test passed independently. The selected suite did not create a ROS graph. This snapshot is offline source/build/test evidence only and does not certify runtime behavior.

### F1–F7 follow-up implementation disposition

Follow-up to audit commit `5916e267f1a0687fe75a76ff9890a849c1ea284c`, on the same candidate and without a new ACR: F1 lifecycle heartbeat freshness is separated from pinned barrier events and executor exceptions are returned to runner cleanup; F2 authorization now requires the explicit sim-only E-stop release bit, hidden action topics are requested from rosbag, and startup rearms once only after upstream readiness; F3 local-reference path transformation applies exact `base_link <- map` rotation then translation; F4 admission checks ROS and steady freshness, message validity and observed TF edge publisher ownership, with mission readiness rechecked; F5 command evidence matches candidate, Safety decision, envelope, actual `/cmd_vel`, receipt identity and payload and retains one completed episode; F6 shared cleanup inspects owned process groups and finalizes A10 after shutdown; F7 omitted non-target policy remains omitted in serialization/hash round-trip, explicit null and a declared hash mismatch fail, and failures/unmeasured metrics are reported honestly.

Disposition evidence and actual offline test/build totals are recorded by the current candidate delivery and append-only progress entry. These fixes remain `IMPLEMENTED_OFFLINE_ONLY`; no runtime was invoked and no runtime behavior is claimed.
