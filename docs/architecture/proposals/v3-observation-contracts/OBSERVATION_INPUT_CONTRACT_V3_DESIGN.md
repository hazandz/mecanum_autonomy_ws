# Observation Input Contract V3 Design

**Revision:** `6`
**Status:** `APPROVED_FOR_FOLLOW_ON_DESIGN_ONLY — SEMANTIC INPUT-BOUNDARY DESIGN`
**Runtime status:** `RUNTIME_NOT_APPROVED`
**Scope:** resolved V3 configuration shape and pure-core input contract for the
canonical 81-element observation. This is not an implementation work package.

## 1. Purpose

The approved receipt bundle closes only the safety-to-observation boundary for
features `[78..80]`. This design closes the missing *configuration boundary* so
one immutable `ResolvedConfigV3` can bind all four observation inputs without
falling back to V1 or inventing runtime values:

```text
Lidar input [0..71]
Local reference [72..74]
Measured twist [75..77]
Final-issued receipt [78..80]
        -> ObservationInputContractV3
        -> V3ObservationAssembler
        -> immutable float32[81] or typed NON_READY
```

The contract receives only resolved profile data and exact references to
approved cross-process contracts. It emits no ROS message, TF, command, or
vector. A future pure-Python assembler consumes it after the compiler has made
an immutable `ResolvedConfigV3`.

## 2. Authority and boundaries

| Authority / fact | Consequence for this design |
| --- | --- |
| Architecture §20 fixes the 81D order and `angular_sector_min` reduction. | This design cannot add, remove, reorder, or repurpose features. |
| Architecture §45 defines lifecycle-bound `LocalReference` in `base_link` and its skew check against odometry. | Goal core derives features from the point; it does not accept policy-ready distance/bearing as an authority. |
| Architecture requires measured body twist and separates it from the published command. | Twist source is the configured state-estimation boundary, never PPO, command, wheel-command estimate, or Ground Truth. |
| Architecture §41.1 fixes `sim_train` as an internal `SimulatedOdometryEmulator` noisy pose/twist-snapshot path, with neither a public odometry topic nor a new TF authority. | `sim_train` must use a typed internal-snapshot variant. It must not be represented as an EKF topic or a synthetic ROS/TF endpoint. |
| Architecture §41.1 separates `sim_eval`/`deploy_sim` from `sim_train`: they use the simulated wheel-odometry equivalent through EKF. | The EKF-topic variant is required for `sim_eval`, `deploy_sim`, and `deploy_real`; it is forbidden for `sim_train`. |
| Architecture §41.1 also requires `sim_train` to form its local goal from the noisy internal emulator output; raw Ground Truth remains only an input of the emulator and task-oracle boundaries. | `sim_train` requires a distinct internal `LocalReference` producer, typed snapshot and time/lifecycle contract. It must not be modelled as the localisation-adapter/TF path used by the other profiles. |
| Approved ACR revision 6 plus Receipt Topic QoS Contract revision 4. | Receipt interface/QoS ID-hash pairs are fixed references, not duplicated policy definitions. |
| A0.3 compiler and A0.5 composition ADR. | New field is profile-owned, enters the normal resolved-config hash, and may contain no token in `ResolvedConfigV3`. |
| ACR S2 semantics are approved for follow-on design only. | This design defines timing-field ownership, but profile-specific numeric sensor timing, buffer, and freshness values/evidence remain unresolved. |

`mecanum_env.py`, `train_ai.py`, V1 observation types, simulator Ground Truth,
and current V1 assembler code are explicitly non-authoritative for this design.

## 3. Decision A — resolved-config ownership

Add exactly one immutable top-level field to `ResolvedConfigV3`:

```text
observation_input: ObservationInputContractV3
```

It is supplied only by the explicit runtime-profile fragment in the A0.5
composition contract. The existing base-owned `observation` field remains the
frozen 81D shape. `observation_input` carries profile-dependent physical and
temporal input semantics, including the explicit distinction between
`sim_train` internal snapshots and integration/deployment topic inputs.

The compiler's existing non-self-referential `provenance.config_hash` must cover
the fully resolved `observation_input` payload automatically. The raw profile
may use typed tokens before resolution, but `compile_v3_config()` must reject
them before `ResolvedConfigV3` construction. No default, V1 conversion, or
simulation-to-real inheritance is permitted.

## 4. Proposed strict model surface

The following is the required target model shape. Names are design-level API
contracts, not code created by this document.

`StrictPositiveInt` and `StrictNonNegativeInt` below are new strict integer
aliases: they reject `bool`, floats, and non-integers, then enforce `> 0` or
`>= 0` respectively.

```text
ContractReferenceV3
  contract_id: IdentifierV3
  contract_sha256: Sha256V3

InputProvenanceV3
  source_class: "SIM_BASELINE" | "MEASURED_REGISTRY" | "APPROVED_CONTRACT"
  source_id: IdentifierV3
  source_sha256: Sha256V3

TopicQosSelectorV3
  name: IdentifierV3
  message_type: IdentifierV3
  publisher_owner: IdentifierV3
  subscriber_owner: IdentifierV3
  qos_profile_id: IdentifierV3
  frame_contract_id: IdentifierV3
  freshness_policy_id: IdentifierV3

Transform2DV3
  parent_frame: IdentifierV3
  child_frame: IdentifierV3
  translation_x_m: StrictFiniteFloatV3
  translation_y_m: StrictFiniteFloatV3
  yaw_rad: StrictFiniteFloatV3
  contract: ContractReferenceV3
  provenance: InputProvenanceV3

LidarInputContractV3
  source_topic: TopicQosSelectorV3
  sensor_model_id: IdentifierV3
  header_frame: IdentifierV3
  T_base_lidar: Transform2DV3
  raw_geometry_contract: ContractReferenceV3
  sector_boundaries_rad: tuple[StrictFiniteFloatV3, ...]  # exactly 73
  sector_interval_policy: "LEFT_CLOSED_RIGHT_OPEN_FINAL_CLOSED"
  sector_reduction: "angular_sector_min"
  range_unit: "m"
  range_min_m: StrictPositiveFiniteFloatV3
  range_max_m: StrictPositiveFiniteFloatV3
  range_sanitization_contract: ContractReferenceV3
  source_provenance: InputProvenanceV3

GoalInputContractV3
  # Discriminated union on source_kind; exactly one variant is present.

SimTrainInternalGoalInputV3
  source_kind: "SIM_TRAIN_INTERNAL_LOCAL_REFERENCE"
  reference_builder_owner: Literal["SimTrainLocalReferenceBuilder"]
  episode_goal_contract: ContractReferenceV3
  emulator_snapshot_contract: ContractReferenceV3
  point_semantics_frame: IdentifierV3
  point_unit: "m"
  reference_stamp_policy: "PROFILE_ROS_TIME_FROM_EMULATOR_SNAPSHOT"
  barrier_clock_policy: "SAFETY_LIFECYCLE_PROFILE_ROS_TIME"
  lifecycle_policy: "ACTIVE_EMULATOR_SNAPSHOT_LIFECYCLE"
  goal_distance_scale_m: StrictPositiveFiniteFloatV3
  validity_contract: ContractReferenceV3
  source_provenance: InputProvenanceV3  # SIM_BASELINE only

NavigationLocalReferenceGoalInputV3
  source_kind: "NAVIGATION_LOCAL_REFERENCE"
  local_reference_contract: ContractReferenceV3
  localization_provider: IdentifierV3
  point_frame: IdentifierV3
  point_unit: "m"
  goal_distance_scale_m: StrictPositiveFiniteFloatV3
  source_provenance: InputProvenanceV3

GoalInputContractV3 =
  SimTrainInternalGoalInputV3 | NavigationLocalReferenceGoalInputV3

MeasuredTwistInputContractV3
  # Discriminated union on source_kind; exactly one variant is present.

SimTrainInternalMeasuredTwistInputV3
  source_kind: "SIM_TRAIN_INTERNAL_SNAPSHOT"
  snapshot_owner: Literal["SimulatedOdometryEmulator"]
  snapshot_contract: ContractReferenceV3
  stamp_policy: "PROFILE_ROS_TIME_FROM_EMULATOR_SNAPSHOT"
  barrier_clock_policy: "SAFETY_LIFECYCLE_PROFILE_ROS_TIME"
  body_semantics_frame: IdentifierV3
  component_order: tuple["vx", "vy", "wz"]
  linear_unit: "m_per_s"
  angular_unit: "rad_per_s"
  validity_contract: ContractReferenceV3
  normalization_policy: "MOTION_LIMITS_PER_AXIS"
  out_of_range_policy: "REJECT_NON_READY_NO_CLIP"
  source_provenance: InputProvenanceV3  # SIM_BASELINE only

EkfTopicMeasuredTwistInputV3
  source_kind: "EKF_ODOMETRY_TOPIC"
  source_topic: TopicQosSelectorV3
  state_estimation_owner: Literal["robot_localization_EKF"]
  body_frame: IdentifierV3
  component_order: tuple["vx", "vy", "wz"]
  stamp_policy: "ODOMETRY_HEADER_STAMP"
  linear_unit: "m_per_s"
  angular_unit: "rad_per_s"
  validity_contract: ContractReferenceV3
  normalization_policy: "MOTION_LIMITS_PER_AXIS"
  out_of_range_policy: "REJECT_NON_READY_NO_CLIP"
  source_provenance: InputProvenanceV3

MeasuredTwistInputContractV3 =
  SimTrainInternalMeasuredTwistInputV3 | EkfTopicMeasuredTwistInputV3

ObservationTimingPolicyV3
  sensor_sync_contract: ContractReferenceV3  # exact S2 ID/SHA-256
  sensor_sync_tolerance_ns: StrictNonNegativeInt
  scan_max_receive_age_ns: StrictPositiveInt
  odom_max_receive_age_ns: StrictPositiveInt
  reference_max_receive_age_ns: StrictPositiveInt
  max_reference_snapshot_skew_ns: StrictNonNegativeInt
  future_stamp_tolerance_ns: StrictNonNegativeInt
  max_scan_buffer_items: StrictPositiveInt
  max_motion_buffer_items: StrictPositiveInt
  max_reference_buffer_items: StrictPositiveInt
  ordered_insert_policy: "STAMP_ASCENDING_STABLE_ARRIVAL_TIEBREAK_V1"
  overflow_policy: "EVICT_OLDEST_AND_MARK_NON_READY_V1"
  selection_policy: "GLOBAL_LATEST_COHERENT_TRIPLE_AT_OR_BEFORE_CUTOFF_V1"
  freshness_clock_policy: "LOCAL_INGRESS_STEADY_RECEIVE_AGE_V1"
  barrier_clock_policy: "SAFETY_LIFECYCLE_PROFILE_ROS_TIME_V1"
  receipt_after_barrier_timeout_ns: StrictPositiveInt

ReceiptBridgeReferenceV3
  receipt_interface: ContractReferenceV3
  receipt_topic_qos: ContractReferenceV3

ObservationCutoffV3  # transaction-scoped input; not a config or ROS message
  transaction_id: IdentifierV3
  creation_owner: Literal["RobotRuntimeAdapter.wait_transition_snapshot(after=receipt)"]
  reset_epoch: StrictNonNegativeInt
  runtime_generation: StrictNonNegativeInt
  schema_id: IdentifierV3
  config_hash: Sha256V3
  cut_off_ros_ns: StrictNonNegativeInt
  action_barrier_ros_ns: StrictNonNegativeInt  # supplied by SafetyLifecycle
  reset_barrier_ros_ns: StrictNonNegativeInt   # supplied by SafetyLifecycle
  invariant: cut_off_ros_ns > action_barrier_ros_ns
             and cut_off_ros_ns > reset_barrier_ros_ns

CommandSafetyContractV3 extension (safety-owned, outside observation_input)
  final_issued_receipt_contract_id: IdentifierV3
  final_issued_receipt_contract_sha256: Sha256V3
  final_issued_receipt_topic_qos_contract_id: IdentifierV3
  final_issued_receipt_topic_qos_contract_sha256: Sha256V3
  final_issued_receipt_topic: TopicQosSelectorV3

ObservationInputContractV3
  lidar: LidarInputContractV3
  goal: GoalInputContractV3
  measured_twist: MeasuredTwistInputContractV3
  timing: ObservationTimingPolicyV3
  receipt_bridge: ReceiptBridgeReferenceV3
```

`TopicQosSelectorV3` is an explicit full selector, not topic-name inference.
The compiler must require exactly one match of all seven fields against a
`TopicQosContractV3` tuple in `topics_qos`; zero or multiple matches fail
closed. This applies to LiDAR, the EKF-topic measured-twist variant, and the
safety-owned final-issued receipt topic. The internal `sim_train` twist variant
has no topic selector because architecture forbids a public odometry topic and
new TF authority there. A future generic topic identity field may replace this
selector only through an approved config-schema revision.

`Transform2DV3` is the architecture's resolved `T_base_lidar`: it maps a
planar point in the LiDAR frame into `base_link` using translation `(x, y)` and
yaw. Its contract SHA-256 binds the exact transform values and convention. The
model validates finite shape; the measured-registry or simulation-baseline
authority validates/calibrates the physical transform.
The assembler uses this resolved transform, never an inferred transform from a
ROS frame name.

## 5. Required invariants and feature rules

### 5.1 Cross-contract validation

Before a config is accepted, the compiler/validator must verify all of the
following without reading ROS:

1. `lidar.header_frame == frames_tf.lidar_frame`;
   `T_base_lidar.parent_frame == frames_tf.base_frame`; and
   `T_base_lidar.child_frame == frames_tf.lidar_frame`.
2. `NavigationLocalReferenceGoalInputV3.point_frame`, the EKF-topic twist
   `body_frame`, the internal-goal `point_semantics_frame`, the internal-twist
   `body_semantics_frame`, and the receipt header-frame contract are exactly
   `frames_tf.base_frame` (`base_link` semantics). The two internal `sim_train`
   declarations are coordinate semantics, not claims that a public TF edge
   exists.
3. Goal source-kind compatibility is exact:
   - `sim_train` requires `SIM_TRAIN_INTERNAL_LOCAL_REFERENCE`,
     `reference_builder_owner == SimTrainLocalReferenceBuilder`,
     `SIM_BASELINE` provenance, and an `emulator_snapshot_contract` equal to
     the internal measured-twist snapshot contract. The builder may receive
     only an approved episode-goal intent and the emulator's noisy typed
     snapshot; it may not accept a raw Ground Truth pose, world/model object,
     TF transform, or raw Ground Truth buffer.
   - `sim_eval`, `deploy_sim`, and `deploy_real` require
     `NAVIGATION_LOCAL_REFERENCE`, whose `localization_provider` equals
     `localization.provider` and whose local-reference contract ID equals
     `navigation.local_reference_contract_id`.
4. Runtime-profile/measured-twist-source-kind compatibility is exact:
   - `sim_train` requires `SIM_TRAIN_INTERNAL_SNAPSHOT`,
     `snapshot_owner == SimulatedOdometryEmulator`, and `SIM_BASELINE`
     provenance, `stamp_policy == PROFILE_ROS_TIME_FROM_EMULATOR_SNAPSHOT`,
     and `barrier_clock_policy == SAFETY_LIFECYCLE_PROFILE_ROS_TIME`. It has
     no odometry-topic selector, EKF-owner field, public TF requirement, or
     independent barrier/time-domain field.
   - `sim_eval`, `deploy_sim`, and `deploy_real` require
     `EKF_ODOMETRY_TOPIC`, whose owner equals `state_estimation.ekf_owner` and
     whose validity contract is compatible with
     `state_estimation.covariance_contract_id`.
5. The LiDAR selector and any EKF-topic twist selector each match exactly one
   resolved `topics_qos` record. A selector may not bind to a Ground Truth
   publisher or an unapproved frame.
6. `command_safety.final_issued_receipt_topic` matches exactly one resolved
   `topics_qos` record and is exactly the approved receipt endpoint:
   `/mecanum/final_issued_command`,
   `mecanum_nav_rl_interfaces/msg/FinalIssuedCommandReceipt`,
   `FinalTwistPublisher`, `V3ObservationIngress`,
   `Q_FINAL_ISSUED_RECEIPT_V1`, `BASE_LINK_PLANAR_TWIST_V1`, and
   `ACTION_BOUND_RECEIPT_V1`. Zero or multiple matching records fail closed.
   This selector is command-safety-owned; `ReceiptBridgeReferenceV3` does not
   duplicate it.
7. `receipt_bridge.receipt_interface` and
   `receipt_bridge.receipt_topic_qos` exactly equal their corresponding
   `command_safety` ID/hash fields, and are respectively
   `mecanum.final-issued-receipt/v1` /
   `90348664c4563997b93de7f10e278b10d4053fcb96909b6bb85c1319db76c40e`;
   and
   `mecanum.final-issued-receipt-topic-qos/v1` /
   `a3bc1a965fc6885825ab961289fa4028862aa7af4b3f3156bc40542f7ee08f62`.
8. Physical LiDAR profile/extrinsic/range inputs and measured-twist inputs are
   `MEASURED_REGISTRY` for `deploy_real`. `SIM_BASELINE` is permitted for
   `sim_train`, `sim_eval`, and `deploy_sim`; `deploy_sim` binds the selected
   simulation LiDAR profile rather than inheriting a real-robot measurement.
   `APPROVED_CONTRACT` is reserved for non-physical policy references such as
   LocalReference, receipt, and timing contracts; it may not disguise an
   unmeasured physical value.
9. A `sim_train` internal local-reference snapshot must carry its profile
   ROS-time reference stamp from the noisy emulator snapshot, source snapshot
   sequence, active `reset_epoch`, active `runtime_generation`, source
   identity, validity and episode-goal-contract identity. Its point is already
   in `base_link` semantics; the core derives distance/bearing and receives
   neither a global robot pose nor raw Ground Truth. The internal goal and
   twist variants must both declare
   `barrier_clock_policy == SAFETY_LIFECYCLE_PROFILE_ROS_TIME`. Therefore,
   `SafetyLifecycle` is the sole creator and owner of action/reset barriers in
   **every** profile, including `sim_train`; `SimulatedOdometryEmulator` and
   `SimTrainLocalReferenceBuilder` only consume the supplied barrier values.
   When `use_sim_time=true`, their snapshot stamps are the profile ROS clock
   in the same nanosecond unit and epoch as those barriers. They must not
   create, advance, translate, or compare against a second simulation-time
   barrier.
10. LiDAR bounds must satisfy `0 < range_min_m < range_max_m`. Equality is
   rejected because it would make range sanitization and normalization
   degenerate.
11. No unresolved token, non-finite scalar, invalid sector count/boundary order,
   non-positive range/scale/age/timeout, or extra field reaches
   `ResolvedConfigV3`.
12. `timing.sensor_sync_contract` is exactly
    `mecanum.snapshot-synchronization-temporal/v1` /
    `1be31c1915fedd86f269cee5214d794da0899a0d69dbb0ba5392e619813d4a8f`. Every assembly transaction receives one immutable
    `ObservationCutoffV3` from
    `RobotRuntimeAdapter.wait_transition_snapshot(after=receipt)`; S2 and
    receipt history consume the same transaction ID, lifecycle, schema/config
    identity, barriers and `cut_off_ros_ns`. Neither path may derive a second
    cut-off.
13. `ObservationCutoffV3.creation_owner` is exactly
    `RobotRuntimeAdapter.wait_transition_snapshot(after=receipt)`, and its
    `cut_off_ros_ns` is strictly greater than both SafetyLifecycle barrier
    timestamps. An owner mismatch is
    `LIFECYCLE_OR_CONTRACT_MISMATCH_NON_READY`; an ordering mismatch is
    `CUTOFF_BARRIER_ORDER_NON_READY`. Neither may infer or repair a cut-off.

`raw_geometry_contract` binds the profile's permitted FOV, angle direction,
angle-origin convention, and angle-increment/beam-geometry validation rule.
`range_sanitization_contract` binds the invalid/no-return treatment in section
5.2. Both are exact ID-hash references so their semantics cannot drift while
the 81D schema label remains unchanged.

### 5.2 LiDAR `[0..71]`

The existing architecture rule is fixed: sanitize a raw sensor-domain range,
map its endpoint through `T_base_lidar` to a `base_link` sector, reduce multiple
rays with `angular_sector_min`, then divide the retained sensor-ray range by
`range_max_m`.

| Raw ray | Required treatment |
| --- | --- |
| finite inside profile range | clamp to `[range_min_m, range_max_m]`, then take sector minimum |
| `+Inf` or above `range_max_m` | use `range_max_m`; increment no-return diagnostic ratio |
| `NaN`, `-Inf`, zero, or negative | use `range_max_m`; increment invalid diagnostic ratio |
| finite below `range_min_m` | use `range_min_m`; increment invalid diagnostic ratio |

Missing sector coverage, invalid angle geometry, wrong frame/extrinsic identity,
or no ready scan produces `NON_READY`. Diagnostics do not consume another
observation feature.

### 5.3 Goal `[72..74]`

For `sim_eval`, `deploy_sim`, and `deploy_real`, ingress supplies the
lifecycle-bound navigation `LocalReference` point in `base_link`. For
`sim_train`, `SimTrainLocalReferenceBuilder` supplies an internal typed point
in the same body-coordinate semantics from an approved episode-goal intent and
the noisy `SimulatedOdometryEmulator` snapshot. It has no ROS topic, public TF
edge, localisation-adapter dependency, or raw Ground Truth payload.

Both variants must carry the active lifecycle and a reference timestamp in the
active profile ROS-time domain as the selected sensor snapshot. In `sim_train`,
this is the same SafetyLifecycle-owned barrier clock carried by the emulator
snapshot, not an internal lifecycle clock.
The pure core derives the values itself:

```text
[ clip(hypot(x_m, y_m) / goal_distance_scale_m, 0, 1),
  sin(atan2(y_m, x_m)),
  cos(atan2(y_m, x_m)) ]
```

Adapter/builder-provided distance/bearing are diagnostics only. The core rejects
a wrong frame semantics, wrong source-kind/provider, Ground Truth source or
payload, lifecycle mismatch, expired external reference, missing internal
snapshot provenance, or reference-to-selected-snapshot skew violation.

### 5.4 Measured twist `[75..77]`

For `sim_eval`, `deploy_sim`, and `deploy_real`, the only policy values are
physical body twist `[vx, vy, wz]` from the selected EKF/state-estimation
boundary. For `sim_train`, they come only from the noisy typed internal snapshot
owned by `SimulatedOdometryEmulator`; raw simulator Ground Truth remains hidden
from policy observation. Each value divides by the corresponding resolved
`MotionLimitTargetPolicyV3` maximum. It is not a desired command and cannot be
derived from a wheel command, PPO action, decoder result, final command, or
perfect simulator state.

`REJECT_NON_READY_NO_CLIP` is an approved semantic decision for follow-on
design only: non-finite values, values invalid under the applicable approved
validity contract, or absolute values above their corresponding per-axis
motion limit produce `NON_READY`; they are not clipped. This does not approve
runtime behavior. The validity contract and profile record must still define
the applicable estimator validity/fault/covariance criteria and provide the
required provenance and profile evidence. Covariance/fault thresholds and
profile-specific evidence remain unresolved here; this document does not
invent a number or acceptance threshold.

### 5.5 Receipt `[78..80]`

Only an ingress-projected receipt admitted by the approved receipt interface
and QoS contracts may provide physical `[vx, vy, wz]`. Normalize each component
with the same per-axis motion limits as measured twist. The ingress owns the
action/reset barrier predicate, coalesced-gap classification, late-join rule,
and receipt timeout; pure core responds to a non-ready ingress status by
producing no vector.

## 6. Timing and typed failure ownership

| Concern | Owner | Required response |
| --- | --- | --- |
| scan/motion/reference triple selection, buffer capacity, overflow, future-stamp handling and skew | S2 contract `mecanum.snapshot-synchronization-temporal/v1` / `1be31c1915fedd86f269cee5214d794da0899a0d69dbb0ba5392e619813d4a8f` | One globally ranked coherent triple at/before a shared transaction cut-off; S2 semantics approved for follow-on design only; profile-specific numeric timing/evidence remains pending and no numeric value is chosen here. |
| external scan/odom/reference receive ages and reference-to-odometry skew | `ObservationTimingPolicyV3` using approved profile values | Non-ready; no cached input fallback. |
| `sim_train` internal local-reference and measured-twist timestamp/provenance | `SimulatedOdometryEmulator` / `SimTrainLocalReferenceBuilder` produce snapshots; `SafetyLifecycle` supplies barriers; `ObservationTimingPolicyV3` validates | Require active lifecycle, compatible emulator snapshot contract/sequence, and timestamps strictly after the supplied barrier in the same profile ROS-time unit and epoch. The internal producers consume barriers; they do not create, advance, translate, or replace them. No invented ROS message or cross-process steady timestamp. |
| action/reset barrier timestamps | `SafetyLifecycle` | Sole owner for every profile. It supplies immutable profile-ROS-time barriers to ingress; no other layer creates, advances, translates, or substitutes them. |
| observation transaction cut-off | `RobotRuntimeAdapter.wait_transition_snapshot(after=receipt)` | Create exactly one immutable `ObservationCutoffV3`; S2 and receipt history consume it unchanged. It owns no barrier, and its cut-off is strictly after both supplied SafetyLifecycle barriers. |
| receipt-after-barrier timeout | `ObservationTimingPolicyV3`, supported by receipt-specific evidence | Ingress reports `RECEIPT_AFTER_BARRIER_TIMEOUT`; core emits no vector. |
| source/frame/unit/hash/lifecycle mismatch | ingress and pure core invariant checks | Typed non-ready; no alias, conversion, or V1 fallback. |

The future pure-core status surface must distinguish at least sensor-pair
pending/skew/stale, reference invalid/stale/skew, twist invalid/out-of-range,
receipt non-ready, lifecycle mismatch, config-contract mismatch, and ready. A
non-ready result contains no partially built 81D array.

## 7. Required changes after this design is approved

No change is authorized by this document today. A later scoped implementation
proposal must include all of the following as one reviewable config/core slice:

1. strict immutable Pydantic models above and the `ResolvedConfigV3` field;
2. compiler/hash/validator changes that enforce section 5.1, including the
   `deploy_sim` `SIM_BASELINE` allowance and profile/source-kind union;
3. explicit canonical profile-fragment source and composition ownership;
4. exact `topics_qos` records for scan, EKF-topic measured twist, and the
   safety-owned receipt topic; the `sim_train` internal snapshot has no
   invented ROS topic record;
5. pure-Python snapshot/ingress and assembler test seams, including the
   internal local-reference builder boundary, lifecycle/timestamp provenance
   and raw-Ground-Truth rejection; and
6. no V1 delegation, runtime adapter, ROS execution, build, test execution,
   training, HIL, hardware, merge, or push unless a later packet explicitly
   authorizes it.

## 8. Approval and readiness gate

This document has two distinct readiness gates:

### 8.1 Non-resolving primitive readiness review

A separate readiness review may assess the non-resolving pure-Python
primitives constrained by PEP-001 revision `0.2.0`: structural models and
their validation only. Unresolved profile timing values, measured-twist
profile evidence, or profile composition do not by themselves block that
separate review. Such primitives must not resolve a profile, treat fixtures
as provenance or evidence, or create an observation vector. This wording is
not implementation authorization; a separate exact implementation packet
and its approval remain required.

### 8.2 Profile-resolving and integrated implementation gate

Profile-resolving or integrated implementation is not ready until all of the
following are resolved and approved for the applicable profile:

- the complete profile-resolved contract and composition;
- S2 timing, buffer, and freshness values with required profile evidence;
- measured-twist validity, fault/covariance criteria, provenance, and profile
  evidence;
- canonical source records for LiDAR, external and internal LocalReference,
  measured twist, and their profile provenance; and
- concrete profile values, including X3 extrinsic/range/frame evidence for
  `deploy_real`.

These profile and evidence gates are not reduced by §8.1. No
`deploy_real` measurement, artifact, HIL, Gate 3/4, or runtime approval is
implied.

## 9. Corrective revision ledger

Revision 2 closes the earlier independent-audit findings without changing the frozen
81D feature layout, the approved receipt interface/hash, or receipt QoS
semantics:

1. adds an explicit internal `sim_train` measured-twist variant;
2. permits `SIM_BASELINE` for every simulation-backed profile, including
   `deploy_sim`;
3. makes the receipt topic a direct, unique command-safety-owned
   `topics_qos` binding; and
4. rejects degenerate LiDAR range bounds.

It remains a follow-on-design document only and is not implementation authority.

Revision 3 closes the remaining profile-completeness gap by adding a typed
internal `sim_train` local-reference boundary. It does not alter the 81D goal
features, public receipt protocol, TF tree, or any QoS contract. It must be
reviewed for Ground Truth isolation and timestamp/lifecycle correctness before
approval.

Revision 4 closes the barrier-clock ownership ambiguity without changing the
81D layout, public receipt/QoS contracts, TF tree, or runtime behavior:

1. `SafetyLifecycle` is explicitly the sole action/reset-barrier owner in
   every profile, including `sim_train`;
2. the internal emulator and local-goal builder are barrier consumers only;
3. their stamps are bound to profile ROS time (the same nanosecond unit and
   epoch as the supplied barrier; with `use_sim_time=true`, the profile ROS
   clock), not to a second simulation-time barrier; and
4. conversion, independent barrier creation, advancement, and substitution
   fail closed.

Revision 6 closes the final S2 review findings without choosing numerical
timing values or changing the 81D/public receipt contracts:

1. binds the exact S2 contract ID/SHA-256 into `ObservationTimingPolicyV3`;
2. adds required bounded-buffer, future-stamp and deterministic global-triple
   selection policy fields;
3. defines one transaction-scoped `ObservationCutoffV3`, shared unchanged by
   S2 and receipt history; and
4. maps cut-off creation to the canonical
   `RobotRuntimeAdapter.wait_transition_snapshot(after=receipt)` call and
   rejects a cut-off that is not strictly after both barriers; and
5. keeps measurement evidence as a later per-profile resolved-config gate.

`OBSERVATION_INPUT_CONTRACT_V3: APPROVED_FOR_FOLLOW_ON_DESIGN_ONLY`
`OBSERVATION_PROFILE_TIMING: VALUES_UNRESOLVED`
`V3_OBSERVATION_ASSEMBLER: NOT_AUTHORIZED`
`RUNTIME_NOT_APPROVED`
