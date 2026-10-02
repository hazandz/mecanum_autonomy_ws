# S3 Training Task, Reset And Collision Design Packet

Status: **DRAFT — PENDING_USER_APPROVAL**

## Purpose, authority, and scope

This packet turns the source evidence from audit S3.2.1A into explicit choices
required before a future training-task runtime is designed. It is a decision
packet only. It does not define a scenario artifact, create a `TrainingTaskOracle`,
instrument Gazebo contacts, reset an entity, or alter a ROS graph.

Authority and evidence consulted:

- [MECANUM_NAV_DRL_Architecture.docx](MECANUM_NAV_DRL_Architecture.docx),
  schema `3.0`, SHA-256
  `f0fb1ebede5f4fa18604610c04bb13587d456173b4fd942dba77e44d49777860`.
- [ACR S1: Simulated Odometry And Ground Truth Isolation](ACR_S1_Simulated_Odometry_And_Ground_Truth_Isolation.md).
- [S3 Episode, Reward And Termination Design](S3_Episode_Reward_Termination_Design_DRAFT.md).
- [S3 Termination Inputs And Limits Decision Packet](S3_Termination_Inputs_And_Limits_Decision_Packet_DRAFT.md).
- [S3 Transition Provenance Decision Packet](S3_Transition_Provenance_Decision_Packet_DRAFT.md).
- [Passive Stream Timing Evidence Report](../artifacts/simulation/passive_stream_timing/Passive_Stream_Timing_Evidence_Report.md).

The architecture and ACR S1 permit hidden Gazebo ground truth for task-oracle,
reset-validation, reward, terminal, and evaluator purposes. They prohibit raw
ground truth, a ground-truth message, or an object reachable from ground truth
from entering policy observation or policy runtime. This packet does not weaken
that boundary.

## 1. Evidence and implementation classification

| Item | Evidence or current owner | Status | Boundary / gap |
| --- | --- | --- | --- |
| `TrainingTaskOracle` | ACR S1 permits the responsibility; no corresponding runtime component exists | `NOT_IMPLEMENTED` | Permission to read hidden GT is not an implementation or an approval for policy access. |
| `/ground_truth/odom` | Legacy Gazebo `OdometryPublisher`; passive report observed `nav_msgs/msg/Odometry`, metadata `world` to `base_link`, publisher `/ros_gz_bridge` | `CANDIDATE_FOR_FUTURE_DECISION` | It is a candidate hidden source only. Metadata is not a TF-authority claim. |
| `/odom` | Legacy `MecanumDrive` path | `OBSERVED` | ACR S1 excludes it as canonical policy odometry. |
| Task scenario artifact | No canonical artifact currently exists | `NOT_IMPLEMENTED` | Legacy waypoints/maps are prototype inputs and cannot define the new contract. |
| Start pose | Launch startup creates `ROBOT_URDF_final` at a fixed pose; legacy code has sampled starts | `OBSERVED` | Startup pose and prototype sampler are not episode start-pose ownership. |
| Goal | `LocalGoal2D` is core input only; no official task producer/config exists | `NOT_IMPLEMENTED` | Goal coordinates, goal-settle rule, and frame remain decisions. |
| Valid area | World collision geometry exists | `OBSERVED` | Geometry alone is not a policy-safe valid-area contract. |
| Forbidden zone | No approved task-boundary source exists | `NOT_IMPLEMENTED` | Do not derive zones from SDF visual or collision bounds. |
| `GOAL_REACHED` fact | Architecture defines precedence; no oracle producer exists | `APPROVED_FOR_CORE` | Precedence may be implemented only after a user-approved fact/source contract. |
| `OUT_OF_BOUNDS` fact | Architecture defines precedence; no boundary/oracle producer exists | `APPROVED_FOR_CORE` | Same restriction: no runtime fact or boundary semantics yet. |
| Collision instrumentation | Robot/world collision geometry is present | `OBSERVED` | Geometry is not an event source, sensor, bridge, or filtering contract. |
| `ContactLatch` | Architecture defines expected latch semantics; core has test-only candidate/token checks | `APPROVED_FOR_CORE` | Runtime producer, event timing, action-interval proof, and latch owner are absent. |
| Reset transaction | Gazebo `UserCommands`; legacy prototype calls `SetEntityPose` and `ControlWorld` | `CANDIDATE_FOR_FUTURE_DECISION` | These are capabilities, not an atomic episode-reset contract. |
| LiDAR frame reconciliation | Profile/source use `RPLiDAR_A1M8_1`; passive runtime evidence reports `ROBOT_URDF_final/RPLiDAR_A1M8_1/rplidar` | `REQUIRED_DECISION` | Runtime observation adapter must fail closed pending an approved canonical frame/reconciliation. |
| TF authority | Passive evidence observed `odom` to `base_link` and wheel edges only | `REQUIRED_DECISION` | GT odometry metadata does not prove a `world` to `odom` TF edge or its owner. |
| D6 episode limit | S3 decision packet has no selected mode or numeric limit | `REQUIRED_DECISION` | Step/time mode, values, source, and discontinuity handling remain open. |
| STUCK | No detector/fact/window exists | `NOT_IMPLEMENTED` | Progress source, window domain, thresholds, and reset semantics remain decisions. |

`GOAL_REACHED`, `OUT_OF_BOUNDS`, and `ContactLatch` are classified
`APPROVED_FOR_CORE` only where authoritative precedence or core-only semantics
already exist. No row above grants runtime approval.

## 2. Proposed scenario-artifact ownership

### 2.1 Proposed artifact boundary

**PROPOSED_FOR_RUNTIME — requires user approval.** A scenario is a versioned,
immutable artifact outside `ROBOT_URDF_final_description`, for example under a
future artifact namespace rather than inside the robot-description package. Its
identity must include a scenario ID, schema version, canonical serialization
hash, and referenced world identity/version. A package must consume an approved
artifact; it must not copy mutable start/goal constants from legacy code.

The proposed content is deliberately structural; all coordinates, dimensions,
and thresholds are `REQUIRED_DECISION`:

| Required artifact field | Purpose | Validation and fail-closed rule |
| --- | --- | --- |
| `scenario_id`, schema version, canonical hash | Stable scenario identity | Missing/unknown schema or hash mismatch rejects reset/task facts. |
| World identity/version/hash | Bind scenario to one world/collision-description revision | A changed or unverified world rejects the scenario; visual similarity is insufficient. |
| Robot/entity identity | Bind reset and collision filtering to the intended model | Must exactly identify the spawned entity; mismatch rejects the transaction. |
| Frame contract | State the frame for starts, goals, valid area, forbidden zones, and oracle facts | Every derived fact must match the approved frame; no implicit TF conversion. |
| Start-pose set | Approved candidate poses and orientations | Every member must be finite and pass the approved validation rules. Values are `REQUIRED_DECISION`. |
| Goal set | Approved goal positions and any task metadata | No default coordinate or legacy waypoint fallback. Goal semantics are `REQUIRED_DECISION`. |
| Valid area | Explicit task-valid geometry/representation | Must be unambiguous and versioned; SDF collision/visual extents are not substitutes. |
| Forbidden zones | Explicit excluded regions and semantics | Must be evaluated in the scenario frame with no inferred margins. |

### 2.2 Lifecycle binding

At reset, the runtime owner must bind the selected immutable scenario identity
to the new `EpisodeLifecycleIdentity` (`episode_generation`, `reset_epoch`,
`runtime_generation`) and the episode identifier. A step fact additionally
binds the active `TransitionIdentity`. Scenario ID/version/hash must accompany
oracle and reset-validation facts so a fact from another scenario cannot join a
transition. The runtime owner for this binding is `NOT_IMPLEMENTED`.

## 3. Proposed hidden-ground-truth `TrainingTaskOracle` contract

### 3.1 Ownership and permitted output

**PROPOSED_FOR_RUNTIME — requires user approval.** `TrainingTaskOracle` is an
internal task/runtime component. It may read hidden `/ground_truth/odom` only
after runtime source, frame, scenario, freshness, and lifecycle contracts are
approved. The observed source is a candidate; it is not an oracle today.

The oracle may emit only immutable, derived task facts. A reset fact carries an
`EpisodeLifecycleIdentity`; a step fact carries the same identity plus the
active `TransitionIdentity`.

| Permitted derived fact | Required provenance | Prohibited representation |
| --- | --- | --- |
| Finite non-negative distance to the selected goal | Scenario ID/version/hash; scenario frame; source simulation timestamp; lifecycle identity; transition identity for a step | Raw odometry message, raw world/model pose, or a reference reachable from either. |
| Goal-reached candidate | The above distance plus user-approved goal semantics, same lifecycle/transition | A policy feature or policy-readable oracle object. |
| Out-of-bounds candidate | User-approved valid-area/forbidden-zone evaluation, same scenario/frame/lifecycle/transition | Inferred SDF bounding box or visual geometry classification. |
| Reset oracle baseline | Distance and simulation timestamp aligned with exact observation0 and active lifecycle | A wall/steady-time substitute or guessed baseline. |

The oracle must reject a mismatch of lifecycle, transition token, scenario
hash, entity identity, frame, source timestamp/provenance, or freshness policy.
It must not use GT `world` to `base_link` metadata as evidence of TF authority.

### 3.2 Isolation matrix

| Data | Allowed destination | Forbidden destination |
| --- | --- | --- |
| Hidden `/ground_truth/odom` and raw Gazebo/model state | `TrainingTaskOracle`, reset validation, reward/termination/evaluator oracle work, and the ACR S1 sensor-side emulator boundary | `SnapshotSynchronizer`, `ObservationAssembler`, `ObservationEncoder`, PPO/policy runtime, or a policy-reachable buffer. |
| Immutable derived oracle facts | Reward/termination core after lifecycle/token validation; reset transaction validation | Policy observation vector or action decoder. |
| Policy-safe noisy odometry snapshot | Policy observation pipeline | Oracle truth source. |

## 4. Proposed reset transaction contract

`SetEntityPose` alone is insufficient: it does not itself prove velocity
clearance, contact/latch state, sensor provenance, lifecycle isolation, or a
valid observation0. The following is **PROPOSED_FOR_RUNTIME** and requires
approval plus runtime evidence:

1. Begin a strictly newer reset generation and create the new lifecycle
   identity; inhibit any command/transition associated with the prior identity.
2. Select and validate a scenario artifact, start pose, and goal before touching
   simulator state.
3. Request a simulator pose-and-velocity reset for the approved entity and
   scenario. The exact capability and receipt semantics are `REQUIRED_DECISION`.
4. Clear prior lifecycle-scoped ContactLatch state, command-receipt/history,
   reward baseline, emulator state, and sensor/synchronizer buffers.
5. Establish new action and reset barriers from an approved runtime owner.
6. Wait only for post-barrier data: required source receipts, policy-safe
   exact scan–odometry input, and hidden oracle evidence remain separately
   validated in their own boundaries.
7. Validate scenario identity, entity pose and velocity receipt, no stale
   contact, exact scan–odometry pair, and a finite/non-negative oracle baseline
   aligned with observation0.
8. Commit observation0 only when every fact is valid. Commit the previous
   issued-command zero and reward baseline atomically with the lifecycle state.
9. On any failure, return `RESET_ABORT`, preserve safe inhibit, enter `FAULT`,
   and create no Gym transition. A later reset must not reuse old facts.

Capabilities requiring proof before runtime implementation include: whether
the deployed Gazebo world exposes a supported pose/velocity reset operation;
whether that operation returns an observable receipt; how velocities and
physics transient state are cleared; whether a reset changes or preserves
simulation time; and how post-reset contact/sensor callbacks are tied to the
new lifecycle identity. Existing `UserCommands`, prototype `SetEntityPose`, and
prototype `ControlWorld` do not answer these questions.

## 5. Collision instrumentation and `ContactLatch` requirements

No plugin, topic, collision-name mapping, or bridge is selected by this packet.
The current geometry is necessary for physics but insufficient as a collision
source.

Future instrumentation must provide all of the following before it can supply
a termination or reward fact:

- A timestamped event source and a versioned manifest of scoped robot and world
  collision names derived from the expanded robot/world descriptions.
- Approved robot-versus-world filtering; wheel/ground exclusions must be
  explicit and tested, never inferred from a string convention.
- A lifecycle-aware event boundary that rejects old epoch/generation events.
- Evidence that a candidate event belongs to the active action interval and
  `TransitionIdentity`; a token alone does not prove timing.
- An immutable `ContactLatch` candidate snapshot. Reward/termination only read
  it during transition construction.
- Consume-once only at successful atomic transition commit. `STEP_ABORT` does
  not consume it; reset/restart clears lifecycle-scoped staged and pending
  state so an old pulse cannot reach a new episode.

The architecture-defined core-only `ContactCandidateSnapshot` and token guards
remain useful tests of joins/atomicity, but are not a runtime ContactLatch.

## 6. LiDAR-frame and TF blockers

### 6.1 LiDAR reconciliation

| Observation | Source | Required reconciliation | Fail-closed behavior before approval |
| --- | --- | --- | --- |
| Runtime scan `frame_id` is `ROBOT_URDF_final/RPLiDAR_A1M8_1/rplidar` | Passive timing evidence | Choose canonical frame value and owner/update path across profile, robot description, static transform, and runtime adapter | Reject the scan for official observation/runtime validation; do not silently rename it. |
| Profile/Gazebo configuration says `RPLiDAR_A1M8_1` | `sim_train.yaml` and legacy Gazebo description | Determine whether this is an intended link frame, an incorrect configured value, or a bridge/static-TF naming issue | Do not infer equivalence solely from suffix or topology. |

### 6.2 TF questions

The evidence observed `odom` to `base_link` and wheel transforms. GT odometry
contains `world` to `base_link` metadata, which is not a TF transform and does
not establish `world` to `odom`.

The following remain `REQUIRED_DECISION`/runtime evidence:

- Owner of `odom` to `base_link` for every future profile, consistent with the
  authoritative EKF ownership rule for integration/deployment.
- Whether a `world` to `odom` relation is needed by each task/reset/oracle
  consumer, and whether it is a TF edge, an oracle-only coordinate conversion,
  or unnecessary.
- The exact source, static/dynamic nature, and authority for every required
  transform. No authority is inferred from odometry metadata.

## 7. Decision registry

| ID | User decision required | Current status | Evidence/approval required |
| --- | --- | --- | --- |
| T1 | Scenario artifact schema, location, canonical serialization/version/hash | `REQUIRED_DECISION` | Artifact review and validation/fail-closed rules. |
| T2 | Start poses, goals, valid area, forbidden zones, scenario/world identity and frame | `REQUIRED_DECISION` | Versioned scenario artifact; no legacy coordinate adoption. |
| T3 | `TrainingTaskOracle` derived-fact contract and owner | `REQUIRED_DECISION` | GT isolation, frame/entity/scenario/lifecycle/token alignment rules. |
| T4 | Reset transaction semantics and owner | `REQUIRED_DECISION` | Supported simulator capability, receipt/velocity/contact/buffer/barrier validation evidence. |
| T5 | Collision source, instrumentation, scoped-name manifest, filtering, and ContactLatch owner | `REQUIRED_DECISION` | Controlled pulse/sustained-contact/reset/replay/action-interval tests. |
| T6 | Canonical LiDAR frame and reconciliation owner | `REQUIRED_DECISION` | Source/runtime frame evidence and graph/frame validation. |
| T7 | TF authority and whether `world` to `odom` is required for each consumer | `REQUIRED_DECISION` | Profile-specific TF graph/authority evidence. |
| T8 | D6 limit mode and numeric limits | `REQUIRED_DECISION` | Step/simulation-time contract, config validation, discontinuity evidence. |
| T9 | STUCK source, window domain, thresholds, precedence interaction, reset behavior | `REQUIRED_DECISION` | Task/oracle and motion evidence; no heuristic is selected here. |

## 8. Exit criteria and handoff

### `READY_FOR_S3.2.2_CORE_ONLY`

All of the following must be user-approved before a core-only task-fact or
termination-input contract begins:

- T1–T3: scenario identity and the immutable oracle-fact/provenance contract;
- T2 frame semantics for goals, boundaries, and derived facts;
- the lifecycle/`TransitionIdentity` join rules and missing-fact fail-closed
  behavior; and
- the required source facts for whichever core evaluator scope is proposed.

Core-only work still must not create a ROS/Gazebo producer or invent numeric
D6/STUCK values.

### `READY_FOR_S3.2.2_RUNTIME`

Runtime work additionally requires:

- An approved and validated scenario artifact with actual values;
- an approved GT/oracle ingress boundary that preserves policy isolation;
- T4 reset capability, receipt, barrier, contact/buffer/history clear, and
  post-reset validation evidence;
- T5 collision instrumentation and lifecycle/action-interval evidence;
- T6 LiDAR reconciliation and T7 profile-specific TF authority evidence;
- approved D6 and STUCK contracts where the runtime/evaluator needs them; and
- safety/fault behavior approved for failed reset, source loss, stale facts,
  and `STEP_ABORT`/`RESET_ABORT`.

Until then, the narrow next phase is a design-only S3.2.2 packet or a
user-approved sub-packet for T1–T3. It must not create a runtime oracle, reset
adapter, ContactLatch, Gymnasium environment, command publisher, or simulator
control operation.
