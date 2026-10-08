# S3 Simulation Scenario Artifact Contract

**Status:** `DRAFT — APPROVED CONVENTION DISPOSITION; VALUES AND RUNTIME NOT APPROVED; WP-03 CLOSURE ACTIVATION PER PEP-001 REV.0.4.0`

## 1. Purpose and authority

This document proposes an immutable scenario-artifact contract outside the
robot-description package. A future approved artifact is the only permitted
source from which `TrainingTaskOracle` may derive goal-distance and bounds
facts. This document creates neither an artifact nor a runtime loader.

Authority and constraints:

- [MECANUM_NAV_DRL_Architecture.docx](MECANUM_NAV_DRL_Architecture.docx),
  schema `3.0`, SHA-256
  `f0fb1ebede5f4fa18604610c04bb13587d456173b4fd942dba77e44d49777860`;
- [S3 GT Odom 2D Coordinate Relation Decision Packet](S3_GT_2D_Coordinate_Relation_Decision_Packet_DRAFT.md), where Option A permits `GT_ODOM_2D` only for core-only oracle-interface design;
- [S3 Training Task Oracle Core Design](S3_Training_Task_Oracle_Core_Design_DRAFT.md);
- [S3 World Geometry And Entity Inventory](S3_World_Geometry_And_Entity_Inventory_DRAFT.md);
- [S3 Training Task Reset And Collision Design Packet](S3_Training_Task_Reset_And_Collision_Design_Packet_DRAFT.md); and
- [S3 Termination Inputs And Limits Decision Packet](S3_Termination_Inputs_And_Limits_Decision_Packet_DRAFT.md).

The Project Owner/User-authorized convention recorded in the WP-03 decision record is
`artifacts/scenarios/<scenario_id>/scenario.json`, outside
`ROBOT_URDF_final_description`, serialized as `RFC8785_JCS_UTF8`. The convention
is an authorized disposition recorded in the governing decision record.
No scenario artifact, scenario ID, or concrete value is created or selected by
this decision.

### Approved disposition provenance

Source decision packet: `WP-03_USER_DECISION_RESOLUTION_PROPOSAL.md`; branch `wp-03-decision-packet-baseline-2e7a2980`; commit `473d1cc6265dc14230fa47a89546b14a9de2a6eb`; SHA-256 `3559f21a07520f10ac1dceb0c2e6f888597a0215a63a5b8b91fce10d340e583c`.
Independent focused audit: `INDEPENDENT_FOCUSED_STATIC_AUDIT_WP03_DECISION_CONTRACT_RECONCILIATION_B234C2FE.md`; SHA-256 `7db8347459af8762da1b74afd99c765a9121e43c2453363049c3f00c0256110f`; `READINESS_FOR_CANONICAL_INTEGRATION: PASS`.

The Project Owner/User is the `ScenarioCustodian` and scenario approver unless a
delegate and approval authority are named in the immutable scenario record.

## 2. Artifact ownership and immutable identity

A future scenario artifact is owned by the simulation/task layer, not the
robot-description package, policy, bridge, or firmware. The Project Owner/User
is the `ScenarioCustodian` and scenario approver unless a delegate and approval
authority are named in the immutable scenario record. Its complete immutable
identity must be attached to every future `TrainingTaskFactSnapshot`.

| Identity member | Proposed requirement | Fail-closed meaning |
| --- | --- | --- |
| `scenario_id` | Non-empty, explicitly user-approved identity. | Missing/unknown ID makes the scenario unavailable. |
| `scenario_version` | Explicit version of the selected scenario values and schema compatibility. | No implicit “latest” or legacy version lookup. |
| `scenario_content_sha256` | SHA-256 of a specified canonical artifact serialization. | Hash absent/mismatch rejects the artifact and all derived facts. |
| `gazebo_world_name` | Exact Gazebo/SDF world identity selected for the scenario. | Different/missing name rejects the artifact; it is not a coordinate frame. |
| `world_file_sha256` | SHA-256 of the exact world file revision. | Changed/unverified file rejects the artifact. |
| `coordinate_reference_id` | Exactly `GT_ODOM_2D` for this proposed 2D oracle contract. | Missing/different reference rejects the artifact; no conversion is inferred. |
| Schema/provenance identifier | Versioned identifier for this contract and the record of its approval. | Unknown schema/provenance is not parsed permissively. |

The artifact identity is separate from two source strings:

| Value | Domain | What it is not |
| --- | --- | --- |
| `GT_ODOM_2D` | Evaluator/ground-truth-only 2D coordinate-reference identity. | Not a ROS topic, TF edge, Gazebo world name, policy frame, or policy/observation-core input. |
| `world` | Runtime-observed `/ground_truth/odom.header.frame_id` metadata. | Not equivalent to `world_demo`, a selected scenario frame, or TF authority. |
| `world_demo` | Static Gazebo/SDF world identity used by the inspected launch/service path. | Not proven equal to `world` and not automatically a ROS coordinate frame. |

No artifact may claim that these three values are equal or provide an implicit
SDF/model-local-to-`GT_ODOM_2D` conversion.

`GT_ODOM_2D` is only the evaluator/ground-truth coordinate reference. Raw
Ground Truth must not enter PPO, policy input, `ObservationAssembler`,
`ObservationEncoder`, or the observation core. This disposition creates no
scenario values or coordinate conversion.

## 3. Proposed schema without concrete values

The following is a contract shape only. Every literal numeric value, region,
name, or optional feature remains unselected until a concrete artifact receives
separate user approval and a hash.

### 3.1 Common validation rules

Every geometric field must be finite, expressed in SI units, and bound to the
artifact's `coordinate_reference_id`, scenario identity/version/hash, and
world identity/hash. Booleans are not numbers. NaN, infinities, omitted units,
unknown shape kinds, duplicate IDs, empty identifiers, ambiguous boundary
semantics, and unversioned provenance are invalid.

The contract is strictly 2D: it has no `z`, z offset, height, pose-origin
conversion, or inferred footprint clearance field.

### 3.2 Proposed members

| Member | Proposed fields | Required validation and provenance | Current value state |
| --- | --- | --- | --- |
| Goal | `goal_id`, `x_m`, `y_m`, `goal_radius_m` or explicitly named tolerance, and `goal_reached_rule` | Finite 2D values, positive radius/tolerance where applicable, SI units, exact scenario/frame identity, rule/version provenance. | `REQUIRED_DECISION` |
| Valid training area | `area_id`, `shape_type`, shape parameters, and `boundary_inclusion_rule` | Explicit supported shape/type only; finite geometry; non-empty interior; unambiguous inside/on-boundary semantics; exact scenario/frame identity. | `REQUIRED_DECISION` |
| Forbidden zone | `zone_id`, `shape_type`, shape parameters, and `boundary_rule` | Globally unique ID; finite 2D geometry; explicit treatment of boundary contact; exact scenario/frame identity. | `REQUIRED_DECISION` |
| Optional start-pose catalog | `start_id`, `x_m`, `y_m`, `yaw_rad`, plus catalog/version provenance | Finite 2D/yaw values; explicit deterministic selection/sampling rule; no default start pose. | `OPTIONAL — REQUIRED_DECISION` |
| Randomization extension | Versioned extension identity and fields only if separately selected | Must not alter scenario identity/hash silently; per-episode sampled values need their own seed/provenance contract. | `DEFERRED` |

`goal_reached_rule`, valid-area shape kinds, forbidden-zone shape kinds, and
boundary inclusion semantics are intentionally named but not selected here.
They may not be populated from a legacy waypoint, visual map, world-size
guess, collision geometry, or obstacle inference.

## 4. Oracle use and fail-closed behavior

An oracle may derive a goal-distance fact or bounds candidate only after it
receives a fully validated artifact identity and the immutable, same-lifecycle
`GT_ODOM_2D` input described by the core design. It must return
`SCENARIO_UNAVAILABLE` with no fact when any required artifact member is
missing, malformed, unknown, mismatched, or unapproved.

| Invalid condition | Required result |
| --- | --- |
| Missing scenario ID/version/hash, world identity/hash, or coordinate reference | `SCENARIO_UNAVAILABLE`; no derived fact. |
| Hash/schema/provenance mismatch | `SCENARIO_UNAVAILABLE`; no fallback to an older or “latest” artifact. |
| Goal/bounds/start data absent or invalid | `SCENARIO_UNAVAILABLE`; do not use a default, legacy value, or SDF-derived value. |
| Frame/coordinate relation absent or mismatched | `SCENARIO_UNAVAILABLE`; do not convert from `world_demo`, SDF-local, or visual coordinates. |
| Artifact cannot join active lifecycle/transition | Explicit lifecycle/provenance mismatch; no fact and no cached prior fact. |

The artifact cannot establish collision, a contact event, a reset receipt,
settled state, TF authority, or a Gazebo pose-application receipt.

## 5. Lifecycle and policy-isolation rules

Every future `TrainingTaskFactSnapshot` must carry the complete scenario
identity/version/hash along with its lifecycle identity. A step fact must also
carry the active `TransitionIdentity`; an observation0 reset baseline follows
the core-design rule for exact observation0 provenance and does not fabricate a
step token.

An artifact is immutable for an episode and may not change during a transition.
Replacing an artifact can become effective only at a newer episode/generation
under a policy that is still `REQUIRED_DECISION`. It must invalidate all prior
scenario-derived facts; no cache, goal, bounds, or start data can cross an
episode/reset/runtime generation boundary.

Neither scenario internals nor raw GT may be visible to PPO, policy input,
`ObservationAssembler`, `ObservationEncoder`, a policy ROS topic, or a
deployed-robot process. The artifact supplies oracle-only semantics; it does
not add any feature to the 81-element policy observation contract.

## 6. User decision registry before a concrete artifact

| Decision | What the user must approve | Evidence required before concrete values |
| --- | --- | --- |
| First scenario identity | Scenario name/ID and version for the first training case. | Immutable artifact naming/serialization proposal and selected world revision. |
| Goal | Goal coordinates, radius/tolerance, and goal-reached rule. | Evidence that values are meaningful in `GT_ODOM_2D`; no legacy/SDF inference. |
| Valid area | 2D shape, numeric boundary, and inclusion rule. | Coordinate/frame provenance and scenario/world validation evidence. |
| Forbidden zones | Zone IDs, geometry, and boundary semantics. | Same coordinate provenance; no visual/collision geometry shortcut. |
| Start catalog | Whether starts are fixed or catalogued, plus coordinates/yaw and selection semantics. | Approved source and episode-seed/lifecycle design. |
| Randomization fields | Include in the artifact now or defer to a later versioned extension. | Seed, reproducibility, and scenario-hash impact design. |
| Artifact-change policy | When and how a new artifact may take effect between episodes/generations. | Lifecycle invalidation and replay evidence plan. |
| Coordinate suitability | Evidence that each selected coordinate is valid for `GT_ODOM_2D`. | User-reviewed measurement/provenance evidence; not a bare `world` string. |

## 7. Explicit non-claims

This contract does not approve or implement:

- reset, settle, entity-control, or runtime ingress behavior;
- `ContactLatch`, collision policy, STUCK, D6, reward, or termination;
- Gymnasium/SB3 integration, a ROS node/topic, or a policy path;
- a `TrainingTaskOracle` source file or a `READY` oracle fact; or
- a conversion of the geometry inventory, SDF, visual map, or obstacle layout
  into a task policy.

It also does not approve any hardware, firmware, STM32, Pi, UART, motor, or
launch/configuration change.

## 8. Exit criterion

The artifact convention and custodian role are approved dispositions;
concrete scenario identity/values and an immutable artifact with verified hash
remain unselected. Only after that artifact is separately approved and the
WP-03 closure transition is active under PEP-001 rev.0.4.0 may a later increment
design a core-only `TrainingTaskOracle` using test-only facts. Gazebo
runtime, reset, collision, reward/termination, Gym/SB3, and policy integration
remain separately blocked.
