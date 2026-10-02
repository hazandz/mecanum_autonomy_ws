# S3 First Scenario Candidate Review

**Status:** `DRAFT — USER SELECTION REQUIRED; NOT A SCENARIO ARTIFACT OR APPROVAL`

## 1. Scope and audited world source

This is a read-only review to help the user choose values for one first
simulation scenario candidate. It is not a scenario artifact, a coordinate
conversion, a collision policy, or approval for a controlled run.

| Item | Read-only source evidence | Status |
| --- | --- | --- |
| Launch entry | [gazebo.launch.py](../ros2_ws/src/ROBOT_URDF_final_description/launch/gazebo.launch.py) passes `tugbot_depot.sdf` to `ros_gz_sim`. | `OBSERVED_STATIC_SOURCE` |
| Local launched world SDF | [tugbot_depot.sdf](../ros2_ws/src/ROBOT_URDF_final_description/launch/tugbot_depot.sdf) | `OBSERVED_STATIC_SOURCE` |
| World SDF SHA-256 | `a5e9c9b1e9b8ad11e0399855f06de687f04c702258b8b74ce563523d78ed55fe` | `OBSERVED_STATIC_SOURCE` |
| Gazebo world identity | SDF `<world name="world_demo">` | `OBSERVED_STATIC_SOURCE`; not a selected coordinate frame |
| Spawned robot entity | Launch requests `ROBOT_URDF_final` at static startup pose `(0, 0, 0.1, yaw 0)`. | `OBSERVED_STATIC_SOURCE`; not a scenario start approval |
| Hidden GT metadata | Replacement evidence observed `/ground_truth/odom.header.frame_id="world"`. | `OBSERVED_RUNTIME_METADATA`; not equal to `world_demo` and not TF authority |

The exact world revision above is a candidate reference for user selection; it
does not by itself create `gazebo_world_name`/hash fields in a scenario
artifact.

## 2. Static model and geometry references

All poses in this table are source-declared SDF/model-local references. They
are not asserted to be coordinates in `GT_ODOM_2D`, are not collision policy,
and must not be converted into valid bounds or free-space claims.

| Static item | Source-declared reference | Read-only limitation |
| --- | --- | --- |
| `ground_plane` | Local static model at pose `0 0 0 0 0 0`; plane collision. | Floor existence does not establish a task area or wheel/contact policy. |
| Depot include | Fuel URI `OpenRobotics/models/Depot`, source pose `7.19009 1.09982 0 0 0 0`. | Expanded identity/geometry/scoped collisions are `UNKNOWN` without resolved Fuel content/runtime evidence. |
| `depot_collision` | Static local model at `7.19009 1.09982 0 0 0 0`; declares walls, boxes, pillars, pallet movers, stairs, and shelves in its own local geometry. | `GEOMETRY_REFERENCE_ONLY`; no task-boundary or collision conclusion. |
| `tugbot` include | Fuel URI `MovAi/models/Tugbot`, source pose `2.75268 1.0014 0.132279 0 0 0`, explicit include name `tugbot`. | Expanded mesh/collision geometry and runtime scope are `UNKNOWN`. |
| `ROBOT_URDF_final` | Launch-spawned entity; robot description supplies base/wheel/sensor collision geometry. | Robot footprint, collision filtering, and runtime scoped names remain unapproved. |

The SDF explicitly names `wall1`–`wall4`, `boxes1`–`boxes11`, `pilar1`–`pilar4`,
`pallet_mover1`–`pallet_mover2`, `stairs`, and `shelfs1`–`shelfs18` under
`depot_collision/collision_link`. These are inventory references only. Remote
Fuel dependencies and any geometry not expanded in local source remain
`UNKNOWN`, not guessed.

## 3. Probe evidence available to candidates

The retained replacement run observed these request-to-GT numerical
correspondences after the local post-response barrier:

| Probe | Request hypothesis x/y/yaw | First post-response GT x/y/yaw | Permitted conclusion |
| --- | --- | --- | --- |
| P0 | `(-4, -3, 0)` | `(-4, -3, 0)` | Narrow numeric correspondence only. |
| P1 | `(-4, 0, π/2)` | `(-4, 0, π/2)` | Narrow numeric correspondence only. |
| P2 | `(-2, -3, -π/2)` | `(-2, -3, -π/2)` | Narrow numeric correspondence only. |

Each coordinate below is labeled:

**`CANDIDATE_ONLY — NOT_APPROVED — REQUIRES_CONTROLLED_SUITABILITY_EVIDENCE`**

This label means no claim of free space, collision-free path, reset-ready pose,
valid bounds, `GT_ODOM_2D`/SDF coordinate equivalence, or `world_demo = world`.

## 4. Candidate scenario v1 hypotheses

These are incomplete hypotheses, deliberately limited to one fixed-start and
one goal. None contains an approved radius, numeric valid-area boundary, or
scenario identity/hash.

| Temporary candidate ID | Fixed-start hypothesis | Goal hypothesis | Valid-area shape hypothesis | Forbidden-zone choice | P0/P1/P2 relation | Why measure next | Still `UNVERIFIED` |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A `P0_TO_P1` | P0 `(-4, -3, yaw 0)` — `CANDIDATE_ONLY — NOT_APPROVED — REQUIRES_CONTROLLED_SUITABILITY_EVIDENCE`. | P1 `(-4, 0)` — `CANDIDATE_ONLY — NOT_APPROVED — REQUIRES_CONTROLLED_SUITABILITY_EVIDENCE`. | Axis-aligned rectangle hypothesis enclosing the two selected 2D points; all numeric extents and inclusion semantics unset. | `none for v1` is a user choice, not selected. | Reuses observed probes P0 and P1 only. | Tests a simple one-axis start/goal relation without inheriting a task path. | Goal radius/rule, rectangle bounds, frame relation, sensor suitability, reset behavior, collision/path clearance, start validity. |
| B `P0_TO_P2` | P0 `(-4, -3, yaw 0)` — `CANDIDATE_ONLY — NOT_APPROVED — REQUIRES_CONTROLLED_SUITABILITY_EVIDENCE`. | P2 `(-2, -3)` — `CANDIDATE_ONLY — NOT_APPROVED — REQUIRES_CONTROLLED_SUITABILITY_EVIDENCE`. | Axis-aligned rectangle hypothesis enclosing the two selected 2D points; all numeric extents and inclusion semantics unset. | `none for v1` is a user choice, not selected. | Reuses observed probes P0 and P2 only. | Provides an independent lateral/longitudinal numerical relation from candidate A. | Goal radius/rule, rectangle bounds, frame relation, sensor suitability, reset behavior, collision/path clearance, start validity. |
| C `P1_TO_P2` | P1 `(-4, 0, yaw π/2)` — `CANDIDATE_ONLY — NOT_APPROVED — REQUIRES_CONTROLLED_SUITABILITY_EVIDENCE`. | P2 `(-2, -3)` — `CANDIDATE_ONLY — NOT_APPROVED — REQUIRES_CONTROLLED_SUITABILITY_EVIDENCE`. | Simple convex 2D region hypothesis; shape type, parameters, and inclusion semantics unset. | `unresolved`; user must decide whether v1 has no zones or explicitly defined zones. | Reuses observed probes P1 and P2 only. | Exercises a non-axis-aligned start/goal relation without claiming the joining path is usable. | Goal radius/rule, region geometry, frame relation, sensor suitability, reset behavior, collision/path clearance, start validity, zone semantics. |

No temporary ID is a selected `scenario_id`, and no candidate can be converted
to a scenario artifact until the user supplies/approves all missing values and
evidence.

## 5. User selection table

| User choice | Required confirmation | Current state |
| --- | --- | --- |
| Candidate | Choose A, B, C, or select none. | `REQUIRED_USER_SELECTION` |
| Start | Confirm or adjust the candidate x/y/yaw; identify it as a fixed start or catalog member. | `REQUIRED_USER_SELECTION` |
| Goal | Confirm or adjust x/y, radius/tolerance, and goal-reached semantics. | `REQUIRED_USER_SELECTION` |
| Valid area | Confirm or adjust shape, every numeric boundary, and inclusion rule. | `REQUIRED_USER_SELECTION` |
| Forbidden zones | Select `none for v1` explicitly, or require defined zone geometry/semantics. | `REQUIRED_USER_SELECTION` |
| Randomization | Confirm v1 has no randomization. | `REQUIRED_USER_SELECTION` |
| Artifact lifecycle | Select artifact-change behavior between episodes/generations. | `REQUIRED_USER_SELECTION` |

The user may also decline all candidates and provide different values. Doing so
does not weaken the required controlled suitability evidence.

## 6. Handoff boundary

Only after the user selects a candidate with concrete values may the next phase
create an approval packet for **one controlled scenario-suitability run**. That
packet must declare exact pose requests, preserve post-response provenance,
and observe `/scan`, `/ground_truth/odom`, `/clock`, and graph metadata under
the existing no-command boundary.

It must not create a scenario artifact/hash or `TrainingTaskOracle` source,
and it cannot claim reset/collision/termination readiness from suitability
evidence alone.

## 7. Explicit non-claims

This review does not approve a candidate, goal, bounds, start, forbidden zone,
randomization, Gazebo runtime, reset, collision/ContactLatch, STUCK, D6,
reward, termination, Gymnasium/SB3, or hardware. It does not place Ground
Truth in PPO observation/policy, and it does not derive a task policy from SDF,
visual, or static geometry references.
