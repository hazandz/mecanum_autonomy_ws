# S3 Controlled Coordinate And Reset Measurement Plan

Status: **APPROVED_FOR_ONE_CONTROLLED_SIMULATION_MEASUREMENT — EXECUTION_NOT_YET_STARTED**

## Purpose, scope, and authority

This document plans a future controlled Gazebo-only measurement. Its purpose is
to collect evidence for two unresolved questions:

1. Whether coordinates accepted by the source-identified pose-control service
   have a reproducible numerical relation to the observed
   `/ground_truth/odom.header.frame_id=world` pose metadata.
2. Whether existing pose-control and world-control capabilities can supply any
   evidence needed for a later reset transaction.

The measurement is not a runtime-reset approval, a scenario decision, a task
oracle, a Gymnasium environment, collision instrumentation, reward, or
termination implementation. `/ground_truth/odom` remains hidden evidence only;
it must not enter policy observation or policy runtime.

Authority and evidence:

- [MECANUM_NAV_DRL_Architecture.docx](MECANUM_NAV_DRL_Architecture.docx),
  schema `3.0`, SHA-256
  `f0fb1ebede5f4fa18604610c04bb13587d456173b4fd942dba77e44d49777860`.
- [ACR S1: Simulated Odometry And Ground Truth Isolation](ACR_S1_Simulated_Odometry_And_Ground_Truth_Isolation.md).
- [S3 Training Task, Reset And Collision Design Packet](S3_Training_Task_Reset_And_Collision_Design_Packet_DRAFT.md).
- [S3 World Geometry And Entity Inventory](S3_World_Geometry_And_Entity_Inventory_DRAFT.md).
- [Passive Stream Timing Evidence Report](../artifacts/simulation/passive_stream_timing/Passive_Stream_Timing_Evidence_Report.md).

Terminology is intentionally separated:

- `world_demo` is the observed Gazebo/SDF world identity/name.
- `world` is the observed GT odometry metadata frame ID.
- Neither name establishes a TF edge, TF authority, or an automatic numerical
  mapping from SDF/model-local coordinates to a ROS/scenario coordinate frame.

## 1. Scope of the future experiment

The future experiment runs only in the existing Gazebo simulation and may do
only the following:

- Launch the existing Gazebo launch file without editing it.
- Call the source-identified pose-control service for entity
  `ROBOT_URDF_final`, after verifying the service exists in that run.
- Subscribe and record `/clock`, `/ground_truth/odom`, `/odom`, `/scan`, and
  `/tf`; inspect graph metadata before and after each run.
- Record the service response, ROS/simulation timestamps, and local steady
  receive timestamps as separate clock domains.
- Save evidence outside production packages and terminate Gazebo with `SIGINT`.

The future experiment must not publish `/cmd_vel`, create a command publisher,
teleoperate, run Nav2/PPO/Gymnasium, spawn/delete an entity, edit source/config,
or interact with Pi, UART, STM32, motors, or other hardware. A pre-run frozen
`/cmd_vel` publisher allowlist is mandatory; any collector-created publisher or
unexpected graph change invalidates the run.

### Declared mutation boundary

| Boundary | Allowed or forbidden operation | Required record |
| --- | --- | --- |
| Permitted mutation | Exactly one declared pose-control request per approved probe `P0`, `P1`, or `P2`, targeting only `ROBOT_URDF_final` | Lossless request, response, symbolic probe ID, entity target, call order, and barrier metadata. |
| Forbidden mutations | World reset, pause, step, spawn, delete, world-control operation, undeclared pose request, and command publication | Any detection invalidates the run. |

### Approved probe inputs

User approval is limited to one Gazebo simulation-only controlled measurement,
targeting only `ROBOT_URDF_final`, with exactly these three pose requests in the
fixed order `P0 → P1 → P2`.

| Probe | x | y | z | yaw (rad) |
| --- | ---: | ---: | ---: | ---: |
| P0 | -4.0 | -3.0 | 0.1 | 0.0 |
| P1 | -4.0 | 0.0 | 0.1 | 1.57079632679 |
| P2 | -2.0 | -3.0 | 0.1 | -1.57079632679 |

No additional pose request is approved. This approval does not establish a
scenario/start/goal, reset contract, or runtime approval; all coordinate mapping,
Fuel geometry, robot-footprint, and collision-safety caveats remain in force.

## 2. Hypotheses and non-claims

| Hypothesis | Future method | Evidence to retain | Explicit non-claim |
| --- | --- | --- | --- |
| Startup pose has a measurable relation to GT pose metadata | Capture post-warm-up `/ground_truth/odom` after the source-declared startup spawn | Startup request/source pose, GT pose/timestamp, graph metadata, receive times | Does not select `world` as scenario frame or establish TF authority. |
| Pose service coordinates map consistently to GT pose metadata | Compare service requests for non-collinear symbolic probes `P0`, `P1`, `P2` with post-barrier GT samples | Request/response record; exact GT samples; relation/residual analysis; source/clock provenance | Does not assume identity mapping, SDF-to-ROS conversion, or a scenario boundary. |
| GT velocity becomes observable after a pose operation | Record GT twist and post-barrier samples while settlement is observed | GT twist/timestamp trace and selected observation window metadata | No velocity-zero threshold or reset-validation threshold is approved here. |
| Simulation time behavior after each pose operation is observable | Compare `/clock` and GT timestamps before/after each probe | Lossless `/clock` and GT trace; monotonicity/duplicate/regression analysis | Does not define whether a future reset must reset simulation time. |
| Pre-operation callbacks can be distinguished from post-barrier evidence | Record barriers and classify arrivals for GT odom, odom, scan, TF | Per-stream timestamps, steady receive times, message order/index, graph snapshots | Does not approve barrier freshness, timeout, queue, or overflow policy. |
| A successful service response has limited meaning | Record response alongside observed post-operation state | Service result and post-barrier evidence | Service success alone is **not** a reset receipt and cannot prove an atomic reset transaction. |

All settling, relation, and velocity observations are
`PROPOSED_FROM_MEASUREMENT_PENDING_USER_APPROVAL`; no timeout, tolerance,
velocity epsilon, settle threshold, or coordinate is chosen by this plan.

## 3. Proposed probe protocol

### 3.1 Run preparation

1. Record launch identity, world-file hash, collector identity, and the
   `world_demo` versus `world` terminology boundary in the run manifest.
2. Take a complete pre-run graph snapshot, including publisher names,
   namespaces when available, types, and counts for the five observed streams
   and `/cmd_vel`.
3. Freeze the observed pre-run `/cmd_vel` publisher allowlist. The collector
   must declare and verify that it created no `/cmd_vel` publisher and invoked
   no command/control action outside the approved pose probe.
4. Launch only the existing simulation, warm up, and record a startup baseline
   without sending a pose request.

### 3.2 Symbolic probes

Use exactly the three approved non-collinear probes `P0`, `P1`, and `P2` from
[Approved probe inputs](#approved-probe-inputs), and issue them only in the fixed
order `P0 → P1 → P2`. No additional numerical pose, yaw value, time budget, or
tolerance is approved by this plan.

For each probe:

1. Record a barrier snapshot before the service call: latest stream metadata,
   `/clock`, GT odom metadata, and local `monotonic_ns` receive time.
2. Send one pose-control request for entity `ROBOT_URDF_final` using the
   selected symbolic probe.
3. Record the complete request and service response without treating a success
   response as a reset receipt.
4. Wait for and losslessly record post-barrier `/ground_truth/odom`, `/odom`,
   `/scan`, and `/tf` evidence. Preserve ROS/simulation timestamps separately
   from steady receive timestamps; never subtract across the two domains.
5. Classify candidate settlement only as `OBSERVED`: pose relation, velocity,
   stream continuity, and callback ordering remain measured facts, not approved
   thresholds.
6. Record all graph changes and invalidate the probe if collector command
   publication, unexpected `/cmd_vel` publisher, missing metadata, or a
   simulator-control action outside the declared pose probe is detected.

### 3.3 Failure and shutdown path

If service availability, graph metadata, required stream capture, source
identity, or collector safety assertions fail, stop recording, mark the probe
invalid with the precise reason, and do not infer a coordinate relation.
Terminate only the Gazebo process started by the measurement with `SIGINT`.
No retry count, timeout, settle criterion, or recovery sequence is selected.

## 4. Artifact contract for the future measurement

The future measurement may create evidence only under:

```text
artifacts/simulation/controlled_coordinate_reset_measurement/
```

| Artifact | Required content | Purpose |
| --- | --- | --- |
| Run manifest | Tool/collector version, launch/world identity and hash, entity identity, frozen `/cmd_vel` allowlist, declared safety scope | Binds the evidence to one source revision and proves scope. |
| Launch and collector logs | Process lifecycle, stderr/stdout, `SIGINT` shutdown record | Diagnoses failed or partial capture. |
| Pre/post graph snapshots | Publisher names/namespaces/types/counts for observed streams and `/cmd_vel` | Detects graph mutation and validates the frozen allowlist. |
| Service request/response record | Symbolic probe ID; user-approved numerical request fields at execution; entity target; call order; response; barrier metadata and clock-domain metadata | Preserves lossless pose-operation evidence without elevating service success to a reset receipt. |
| Lossless topic trace | `/clock`, GT odom, odom, scan, TF payload metadata; ROS/sim stamps, steady receive time, message index | Supports relation, ordering, and continuity analysis without fabricating freshness. |
| Per-probe summary | Barrier, accepted/rejected request, post-barrier candidates, observed relation/velocity/clock notes, invalidation reason | Separates raw evidence from interpretation. |
| Aggregate report | Cross-probe relation results, anomalies, limitations, proposed options labelled pending approval | Supports a later user decision, not automatic approval. |
| Safety-scope statement | Explicit declaration of no `/cmd_vel` publish or command publisher; no teleop, Nav2, PPO/Gymnasium, reset/pause/step world, spawn/delete, world-control operation, undeclared pose request, or hardware operation; only manifest-declared pose-control requests are permitted | Documents the declared mutation boundary and every exception to it. |

## 5. Acceptance evidence and non-claims

The resulting evidence may support a user decision about a future scenario
coordinate frame, confirm or reject a proposed numerical conversion candidate,
and characterize the capability/limitation of the pose service and a later
reset receipt/barrier design.

It cannot, by itself, prove any of the following:

- An atomic reset of pose, velocity, physics, contact latch, command receipt,
  history, emulator, or sensor buffer.
- A collision event source, collision filtering, or `ContactLatch` runtime.
- A valid area, forbidden zone, goal contract, or task-oracle runtime.
- TF authority or existence of `world_demo` to `world` or `world` to `odom`.
- A Gymnasium environment, reward/termination semantics, or any real-robot
  safety property.

## 6. Decision registry after measurement

| Decision | Possible evidence from this plan | Status after measurement until user approval |
| --- | --- | --- |
| Use `world` as scenario coordinate frame or select another frame | Measured relation between pose-service coordinates and GT metadata | `REQUIRED_DECISION` |
| SDF/model-local to scenario-frame mapping/provenance | Measured conversion candidate and residuals across symbolic probes | `REQUIRED_DECISION` |
| Pose-service receipt semantics | Response plus observed post-barrier behavior | `REQUIRED_DECISION` |
| Post-reset barrier policy | Message-order, timestamp, and callback continuity evidence | `REQUIRED_DECISION` |
| Reset validation criteria | Observed pose/twist/clock behavior and stated limitations | `REQUIRED_DECISION` |
| Need for a capability beyond `SetEntityPose` | Evidence of what the pose operation did not clear or prove | `REQUIRED_DECISION` |

No outcome of this measurement can self-approve a scenario, reset transaction,
or runtime component. Follow-on work must return to a decision packet before
implementation.
