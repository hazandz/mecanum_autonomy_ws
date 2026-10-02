# S3 GT Odom 2D Coordinate Relation Decision Packet

**Status:** `DRAFT — OPTION A USER_APPROVED_FOR_CORE_ONLY_INTERFACE_DESIGN; RUNTIME NOT APPROVED`

## 1. Purpose, scope, and authority

This packet asks the user to make one narrow simulation-only decision: whether
the explicitly named hidden coordinate reference `GT_ODOM_2D` may be used by a
future internal `TrainingTaskOracle`. It does not create that oracle, a Gazebo
adapter, a reset adapter, a ROS topic, or a policy input.

The authoritative architecture is
[MECANUM_NAV_DRL_Architecture.docx](MECANUM_NAV_DRL_Architecture.docx), schema
`3.0`, SHA-256
`f0fb1ebede5f4fa18604610c04bb13587d456173b4fd942dba77e44d49777860`.
Its ground-truth isolation contract permits hidden ground truth for the
simulation task oracle, while prohibiting it from policy observation. This
packet also relies on:

- [S3 Post-Response Provenance Replacement-Run Packet](S3_Post_Response_Provenance_Replacement_Run_Packet_DRAFT.md);
- the retained [controlled-measurement evidence report](../artifacts/simulation/controlled_coordinate_reset_measurement/Controlled_Coordinate_Reset_Measurement_Evidence_Report.md);
- [S3 Controlled Coordinate Evidence Review](S3_Controlled_Coordinate_Evidence_Review_DRAFT.md);
- [S3 World Geometry And Entity Inventory](S3_World_Geometry_And_Entity_Inventory_DRAFT.md); and
- [S3 Training Task, Reset And Collision Design Packet](S3_Training_Task_Reset_And_Collision_Design_Packet_DRAFT.md).

The evidence authority for the request-to-GT relation in this packet is the
completed replacement run
`run-replacement-post-response-20260924T191000Z-03`, not the earlier
pre-response-only run.

## 2. Observed replacement-run evidence

The replacement run is recorded as `VALID`; it targeted only
`ROBOT_URDF_final`, used the temporary one-service bridge, and sent exactly
`P0 → P1 → P2`. Each retained `SetEntityPose` response was `success=true`.
For each probe, the table records the first GT odometry sample classified
`POST_RESPONSE_CANDIDATE` in the retained report.

| Probe | Approved request x/y/yaw | First post-response GT x/y/yaw | Classification and boundary |
| --- | --- | --- | --- |
| P0 | `(-4, -3, 0)` | `(-4, -3, 0)` | `POST_RESPONSE_CANDIDATE`: the GT row was received strictly after the local post-response barrier. |
| P1 | `(-4, 0, π/2)` | `(-4, 0, π/2)` | `POST_RESPONSE_CANDIDATE`: the GT row was received strictly after the local post-response barrier. |
| P2 | `(-2, -3, -π/2)` | `(-2, -3, -π/2)` | `POST_RESPONSE_CANDIDATE`: the GT row was received strictly after the local post-response barrier. |

The source report retains the corresponding raw numerical fields, including
the separate ROS/simulation stamps and steady receive times. The relation in
this table is an observed 2D numerical correspondence; it is not an automatic
coordinate mapping decision.

## 3. Proposed narrow decision

### Proposed identity and source

**USER_APPROVED_FOR_CORE_ONLY_INTERFACE_DESIGN:** define `GT_ODOM_2D` as the
named hidden simulation coordinate reference formed from `x`, `y`, and
`yaw` in
`/ground_truth/odom`. The evidence report observed
`header.frame_id="world"` at runtime. The bare string `world` is therefore
the observed GT message frame metadata for this proposal; it is not the Gazebo
world identity `world_demo`, and this packet asserts no equality or transform
between them.

`GT_ODOM_2D` is a derived internal identity, not a new ROS message, public ROS
topic, TF edge, or policy-visible data object.

### Permitted and forbidden uses if selected

| Boundary | Proposed rule |
| --- | --- |
| Permitted owner | A future internal simulation `TrainingTaskOracle` only. |
| Permitted derived uses | Goal-distance, user-selected 2D bounds evaluation, and future termination facts after their own lifecycle/provenance contracts are approved. |
| Forbidden policy paths | No raw GT or `GT_ODOM_2D` in PPO observation, policy input, `ObservationAssembler`, `ObservationEncoder`, a policy ROS topic, or any policy-reachable buffer/object. |
| Forbidden deployment paths | No use on the deployed robot, in Pi/STM32 transport, or as a substitute for measured real odometry. |

This user approval does not approve a runtime `TrainingTaskOracle`; it only
permits its core-only interface design in a separate phase.

## 4. Fail-closed treatment of z

The three requests used `z=0.1`, whereas the retained first post-response GT
rows report `z=0.0`. This packet does not create a z offset, conversion rule,
or pose-origin interpretation. `z` is deliberately outside `GT_ODOM_2D`; the
task geometry considered here is only 2D `x/y/yaw`.

Any future 3D task, footprint-height, or full reset contract remains blocked
until a separately approved source/provenance design explains this difference.
No implementation may silently use the observed z discrepancy to alter a
request or an oracle fact.

## 5. Explicit non-claims

This packet does **not** demonstrate or approve any of the following:

- a time at which Gazebo absolutely applied a pose request;
- atomic reset, settled state, a reset receipt, or a reset lifecycle contract;
- TF authority, a `world_demo → world` edge, or conversion from SDF/model-local coordinates;
- `ContactLatch`, collision semantics, STUCK, D6 episode limits, reward, or a Gym runtime;
- a `TrainingTaskOracle` runtime implementation; or
- hardware, firmware, Pi, STM32, UART, motor, or deployment behavior.

`POST_RESPONSE_CANDIDATE` proves only local receive ordering after the client
validated `success=true`. It is not a Gazebo application receipt and must not
be promoted into one by later code or documentation.

## 6. User decision

| Option | User selection | Consequence |
| --- | --- | --- |
| A | **USER_SELECTED_FOR_CORE_ONLY_INTERFACE_DESIGN**: `GT_ODOM_2D` is the hidden 2D coordinate reference for the simulation-only `TrainingTaskOracle` design. | Permits this core-only design only; it does not permit Gazebo runtime, reset, collision, or policy GT access. |
| B | **NOT_SELECTED**. | No additional authority is implied by the non-selection of Option B. |

The user selected Option A after the replacement run established a consistent
post-response candidate relation for all three non-collinear approved probes.
The narrow scope and explicit non-claims still preserve every unresolved
coordinate-frame, reset, and runtime question.

## 7. Exit criterion and deferred work

With Option A selected, the next permitted increment may design a core-only
`TrainingTaskOracle` interface that consumes a hidden `GT_ODOM_2D` input and
emits immutable derived task facts. It must retain ground-truth isolation and
must not implement Gazebo runtime, reset, collision, or policy integration.

The following remain `REQUIRED_DECISION` or `NOT_IMPLEMENTED`: scenario frame,
goal and bounds artifact, reset semantics, collision/contact source, D6/STUCK,
TF authority, runtime source freshness, and all reward/termination runtime
work.
