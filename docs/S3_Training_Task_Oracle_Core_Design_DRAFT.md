# S3 Training Task Oracle Core Design

**Status:** `DRAFT — CORE-ONLY DESIGN, RUNTIME NOT APPROVED`

## 1. Purpose, authority, and scope

This document defines a proposed pure-core contract for a future
simulation-internal `TrainingTaskOracle`. It follows the user's narrow Option A
selection in [S3 GT Odom 2D Coordinate Relation Decision Packet](S3_GT_2D_Coordinate_Relation_Decision_Packet_DRAFT.md): `GT_ODOM_2D` may be used only
as a hidden 2D coordinate reference when designing the oracle interface.

The authoritative architecture is
[MECANUM_NAV_DRL_Architecture.docx](MECANUM_NAV_DRL_Architecture.docx), schema
`3.0`, SHA-256
`f0fb1ebede5f4fa18604610c04bb13587d456173b4fd942dba77e44d49777860`.
It permits hidden ground truth for `TrainingTaskOracle`, reset validation,
reward/success/termination, and evaluation, while forbidding it from
`SnapshotSynchronizer`, `ObservationAssembler`, `ObservationEncoder`, PPO, and
policy runtime. This design also preserves the constraints in:

- [S3 Training Task Reset And Collision Design Packet](S3_Training_Task_Reset_And_Collision_Design_Packet_DRAFT.md);
- [S3 Episode Reward And Termination Design](S3_Episode_Reward_Termination_Design_DRAFT.md); and
- [S3 Termination Inputs And Limits Decision Packet](S3_Termination_Inputs_And_Limits_Decision_Packet_DRAFT.md).

This is not a source-code plan authorization. It neither creates an oracle nor
authorizes a Gazebo ingress, scenario artifact, reset operation, collision
source, reward evaluator, termination evaluator, Gymnasium environment, ROS
node, topic, or hardware operation.

## 2. Ownership and data boundary

`TrainingTaskOracle` is a simulation-internal owner of immutable **derived
task facts**. A later core implementation may live in the owned
`mecanum_nav_rl` task/core boundary, but no file or runtime producer is created
by this document.

| Boundary | Proposed contract |
| --- | --- |
| Hidden input identity | `GT_ODOM_2D`: finite `x_m`, `y_m`, and `yaw_rad` from hidden `/ground_truth/odom`; observed runtime metadata is `header.frame_id="world"`. |
| Required identity | `EpisodeLifecycleIdentity` carries episode generation, reset epoch, and runtime generation. A step request also carries the active `TransitionIdentity`. |
| Required provenance | Source simulation timestamp, the observed GT frame metadata, lifecycle identity, and the caller-supplied join context. Reset baseline requests also carry exact observation0 provenance; step requests carry the same active transition token as the candidate commit. |
| Output | Immutable derived facts only: a finite non-negative goal-distance fact when an approved goal exists, and a future bounds candidate only when an approved scenario boundary exists. |
| Prohibited output | Raw `/ground_truth/odom`, a Gazebo/model pose, a ROS message, or any reference/object reachable from raw GT. |
| Prohibited consumers | `ObservationAssembler`, `ObservationEncoder`, PPO/policy input, policy ROS topics, Pi/STM32 transport, and deployed-robot code. |

`world` is observed GT message metadata. It is not asserted to equal the
Gazebo world identity `world_demo`, is not a selected scenario frame, and is
not TF-authority evidence.

## 3. Proposed immutable core API

The names below are a design-level API; they are not current source types and
must not be treated as runtime producers.

### 3.1 Input snapshot

`GTODOM2DInputSnapshot` would be immutable and contain only:

| Field | Validation and purpose |
| --- | --- |
| `x_m`, `y_m`, `yaw_rad` | Real, finite numeric values. No z field, offset, pose-origin inference, or implicit conversion. |
| `source_timestamp_ns` | Exact non-negative integer timestamp retained in its stated simulation/ROS domain; no conversion to steady time. |
| `observed_frame_id` | Explicit metadata string. For this selected reference, caller evidence must identify the observed `world` metadata; this is not a frame-conversion authority. |
| `lifecycle_identity` | Immutable `EpisodeLifecycleIdentity`; every field must exactly match the active lifecycle. |
| `join_context` | A mode-specific immutable context described below; it contains no raw GT object. |

There are two mutually exclusive join modes:

| Request mode | Required join | Why it differs |
| --- | --- | --- |
| Reset baseline | Active lifecycle plus exact observation0 provenance. No `TransitionIdentity` is fabricated before the first step. | The reset baseline is committed with observation0, before a step token exists. |
| Step fact | Active lifecycle plus the exact active `TransitionIdentity` for the candidate step. | Goal/bounds facts for a step must join the same transaction as command receipt, contact candidate, and exact observation. |

The core must reject a request containing both modes, neither mode, a foreign
lifecycle, a stale or future episode/reset/runtime generation, a transition
token for another step, a different token for the same step, an inexact
observation0 provenance, or an invalid timestamp/value.

### 3.2 Derived result

`TrainingTaskOracleResult` would be immutable and expose an explicit status,
the applicable lifecycle identity, an optional transition identity, and
`fact: TrainingTaskFactSnapshot | None`.

`TrainingTaskFactSnapshot`, when status is ready, would contain only derived
values and their join evidence:

| Derived member | Availability rule |
| --- | --- |
| `goal_distance_m` | Present only when a user-approved, finite goal in an approved scenario/frame contract is available; value is finite and non-negative. |
| `bounds_candidate` | Present only when an approved valid-area/forbidden-zone contract exists. It is a candidate fact, not a terminal decision. |
| `source_timestamp_ns`, lifecycle/transition identity | Retained only to prove the same permitted input point; no pose is retained. |
| Scenario identity/version/hash and frame evidence | Required before a goal/bounds fact can be ready; currently unavailable. |

The fact object has no x/y/yaw fields, raw-GT reference, ROS message, Gazebo
object, policy feature, or mutable callback state.

### 3.3 Status and fail-closed rules

The proposed status vocabulary is intentionally explicit:

| Status | Required behavior |
| --- | --- |
| `READY` | Return a new immutable derived fact only after all applicable identity, join, scenario, frame, and numeric checks pass. |
| `INVALID_INPUT` | Reject malformed, missing, boolean-as-number, non-finite, or invalid timestamp/frame input; return no fact. |
| `LIFECYCLE_MISMATCH` | Reject wrong, stale, or future episode generation, reset epoch, or runtime generation; return no fact. |
| `TRANSITION_MISMATCH` | Reject absent/wrong/replayed transition token for a step fact; return no fact. |
| `PROVENANCE_MISMATCH` | Reject a reset fact not joined to exact observation0 or a step fact not joined to the active transition; return no fact. |
| `SCENARIO_UNAVAILABLE` | Return no goal/bounds fact when approved scenario identity, goal, bounds, or frame semantics are absent. |
| `FACT_UNAVAILABLE` | Return no fact when a required input cannot be supplied; never use the previous fact, older GT, a legacy waypoint, or an inferred SDF bound. |

The oracle core is stateless with respect to previously returned facts, or
otherwise must clear every cache on a strictly newer reset lifecycle. A reset
must never permit a fact from the prior episode/reset/runtime generation to
join observation0 or a later step.

## 4. Pending scenario and runtime prerequisites

The user selection of `GT_ODOM_2D` does not resolve the following blockers:

| Blocker | State | Consequence for this design |
| --- | --- | --- |
| Scenario identity/version/hash | `REQUIRED_DECISION` | No ready fact may be emitted without it. |
| Goal definition and goal-reached semantics | `REQUIRED_DECISION` | No goal-distance or goal-reached result is production-ready. |
| Valid area and forbidden zones | `REQUIRED_DECISION` | No bounds candidate may be emitted. Static SDF geometry remains reference only. |
| Scenario coordinate frame and relation to source geometry | `REQUIRED_DECISION` plus runtime evidence | No implicit `world_demo`, SDF-local, or `world` conversion is allowed. |
| Runtime ingress from `/ground_truth/odom` | `NOT_IMPLEMENTED` | This design does not subscribe, parse ROS messages, or select a freshness policy. |
| Reset receipt and settle validation | `NOT_IMPLEMENTED` | `SetEntityPose success` and post-response candidates are not reset receipts. |
| Collision/ContactLatch | `NOT_IMPLEMENTED` | No contact fact is supplied or inferred here. |
| STUCK, D6, reward, termination evaluator | `REQUIRED_DECISION` / `NOT_IMPLEMENTED` | The oracle returns no terminal decision and performs no reward calculation. |
| Gymnasium/SB3 integration | `NOT_IMPLEMENTED` | No environment transition, action, or policy API is created. |

## 5. Ground-truth isolation requirements

The future production core oracle must remain a pure module. It may accept
only the immutable hidden snapshot described here and return derived facts to
the task/reward/termination boundary after join validation. It must not import
or call ROS, Gazebo, TF, Gymnasium, Stable-Baselines3, `ObservationAssembler`,
`ObservationEncoder`, or any policy module.

No code path may route raw GT, `GT_ODOM_2D`, or a reference reachable from
either into policy observation. The policy-safe odometry path remains the
internal simulated-odometry measurement output already designated by ACR S1;
it is separate from this oracle boundary.

## 6. Required test matrix for a later core increment

| Test | Required evidence |
| --- | --- |
| Valid reset baseline fact | Same active lifecycle, valid exact observation0 provenance, finite non-negative derived distance, and no transition token fabricated. |
| Valid step fact | Same active lifecycle and exact `TransitionIdentity`; returned derived fact contains no raw GT pose/reference. |
| Lifecycle mismatch | Wrong/stale/future episode generation, reset epoch, or runtime generation returns `LIFECYCLE_MISMATCH` and no fact. |
| Transition mismatch | Missing, wrong-step, different-same-step, stale, future, or replayed token returns `TRANSITION_MISMATCH` and no fact. |
| Reset isolation | A new reset makes all prior fact/cache state unusable; observation0 and later steps cannot reuse it. |
| Numeric and timestamp rejection | NaN, infinities, bools, malformed frame metadata, and invalid/ambiguous timestamps fail closed. |
| Missing input | Missing scenario/goal/bounds or invalid provenance returns an explicit non-ready status; no fallback to legacy data, old fact, or SDF inference. |
| Object/reference isolation | Mutating a caller-owned input after creation cannot alter the returned fact; result contains no raw GT object/reference. |
| Policy isolation scan | Production oracle source has no ROS, Gazebo, Gymnasium, SB3, policy-observation, or raw-GT-to-policy import/route. |

## 7. Exit condition

This document makes a later **core-only** `TrainingTaskOracle` implementation
designable, subject to a separate implementation authorization and test-only
facts. It does not make any runtime implementation ready.

Gazebo ingress, concrete scenario data, reset/collision ownership, reward and
termination evaluators, Gym/SB3 integration, and all hardware paths remain
blocked pending their listed decisions and evidence.
