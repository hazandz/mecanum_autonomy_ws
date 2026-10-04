# ACR S2 — Snapshot Synchronization Temporal Contract

**Revision:** `2`\
**Status:** `DRAFT — PENDING_INDEPENDENT_ARCHITECTURE_REVIEW_AND_USER_APPROVAL`\
**Runtime status:** `RUNTIME_NOT_APPROVED`\
**Scope:** canonical V3 temporal admission and selection for LiDAR, motion
snapshot and local reference before a pure V3 assembler creates an 81-element
observation. This is not an implementation work package.

## 1. Purpose

The Architecture requires a synchronized, post-barrier sensor snapshot but does
not set numerical tolerance, freshness or buffer values. This ACR defines the
semantics and evidence gate without inventing any number:

```text
validated LiDAR + compatible motion snapshot + compatible LocalReference
        -- S2 temporal admission/selection -->
typed coherent input set or NON_READY
        -- V3 assembler --> immutable float32[81]
```

S2 governs features `[0..77]` only: LiDAR `[0..71]`, LocalReference `[72..74]`,
and measured twist `[75..77]`. Final-issued receipt `[78..80]` is excluded:
its QoS, gap rules and receipt wait are already owned by the approved receipt
contracts.

## 2. Authority and boundary

| Classification | Authority / fact | Consequence |
| --- | --- | --- |
| `ARCHITECTURE_FACT` | Buffered scan and odometry require matching epoch/generation, stamps strictly after action/reset barriers, bounded skew, local steady receive age, and valid contracts. | No stale, pre-barrier or mismatched input can form a vector. |
| `ARCHITECTURE_FACT` | ROS time is for sensor alignment; local steady time is for receive age and waits. They are never subtracted. | Every rule below names its clock domain. |
| `ARCHITECTURE_FACT` | Buffers are bounded/ordered, reset-cleared, counted for duplicate/out-of-order/stale/sync miss; clock rollback invalidates buffers and advances generation. | S2 must specify bounded-buffer and failure semantics. |
| `ARCHITECTURE_FACT` | `sim_train` uses noisy `SimulatedOdometryEmulator` snapshots without public odometry/TF; local goal derives from approved episode-goal intent plus that snapshot. | `sim_train` is an internal variant, never an EKF or Ground Truth fallback. |
| `CARRIED_FORWARD_DESIGN_DECISION` | ObservationInputContractV3 rev.5 assigns `SafetyLifecycle` as sole action/reset-barrier owner. | S2 consumes barriers and never creates, translates or replaces one; formal approval of that decision remains a prerequisite for implementation. |
| `APPROVED_DECISION` | Receipt QoS/gap/timeout are separate. | S2 must not redefine them. |

S2 does not select YDLIDAR X3 values, serial settings, QoS, TF transforms,
control period, receipt timeout, a node, simulation setting or runtime behavior.
It authorizes no code, test, build, ROS, Gazebo, PPO, HIL, hardware, merge or
push.

## 3. Contract and configuration binding

Proposed reference:

```text
contract_id: mecanum.snapshot-synchronization-temporal/v1
contract_sha256: 1be31c1915fedd86f269cee5214d794da0899a0d69dbb0ba5392e619813d4a8f
```

`ObservationTimingPolicyV3.sensor_sync_contract` must carry this exact pair.
Resolved timing/buffer policy is profile-owned, inside `config_hash`, and has no
`TBD_*` token. Raw ROS messages need no config hash; ingress binds each typed
snapshot to the active resolved session.

### 3.1 Shared observation cut-off

`ObservationCutoffV3` is an immutable, transaction-scoped internal value:

```text
transaction_id: opaque identity unique within (reset_epoch, runtime_generation)
creation_owner: RobotRuntimeAdapter.wait_transition_snapshot(after=receipt)
reset_epoch: active epoch
runtime_generation: active generation
schema_id: active V3 schema
config_hash: active resolved-config hash
cut_off_ros_ns: active profile ROS time
action_barrier_ros_ns: immutable value supplied by SafetyLifecycle
reset_barrier_ros_ns: immutable value supplied by SafetyLifecycle
invariant: cut_off_ros_ns > action_barrier_ros_ns
           and cut_off_ros_ns > reset_barrier_ros_ns
```

The canonical **transition snapshot transaction owner** is
`RobotRuntimeAdapter`, specifically one invocation of
`RobotRuntimeAdapter.wait_transition_snapshot(after=receipt)`. That invocation
creates exactly one object, owns `transaction_id` and supplies the cut-off;
`SafetyLifecycle` remains the sole owner of the two barrier values inside it.
The adapter may gather inputs through other boundaries, but it may not delegate
or duplicate this ownership. `V3ObservationIngress`/S2 and receipt history
must consume the *same* object, matching every listed field. Neither is allowed
to create, infer, round, or replace a cut-off. `ObservationCutoffV3` is not a
ROS message, config value, or public receipt field.

### 3.2 Proposed timing-model amendment

Existing field meanings are fixed:

```text
sensor_sync_tolerance_ns          maximum |scan_stamp - motion_stamp|
scan_max_receive_age_ns           local ingress steady age of scan
odom_max_receive_age_ns           same for EKF odometry or emulator motion
reference_max_receive_age_ns      same for LocalReference
max_reference_snapshot_skew_ns    maximum |reference_stamp - selected_motion_stamp|
```

S2 proposes these fields, because Architecture requires bounded buffers and a
configured future-stamp rule:

```text
future_stamp_tolerance_ns: StrictNonNegativeInt
max_scan_buffer_items: StrictPositiveInt
max_motion_buffer_items: StrictPositiveInt
max_reference_buffer_items: StrictPositiveInt
ordered_insert_policy: "STAMP_ASCENDING_STABLE_ARRIVAL_TIEBREAK_V1"
overflow_policy: "EVICT_OLDEST_AND_MARK_NON_READY_V1"
selection_policy: "GLOBAL_LATEST_COHERENT_TRIPLE_AT_OR_BEFORE_CUTOFF_V1"
freshness_clock_policy: "LOCAL_INGRESS_STEADY_RECEIVE_AGE_V1"
barrier_clock_policy: "SAFETY_LIFECYCLE_PROFILE_ROS_TIME_V1"
```

This is a proposed config-model amendment, not code. Independent audit must
review its placement in `ObservationTimingPolicyV3`.

## 4. Clock, lifecycle and buffer ownership

| Concern | Sole owner | Rule |
| --- | --- | --- |
| `runtime_generation` on clock rollback/simulator restart | `ClockEpochTracker` / lifecycle | Advance generation; invalidate all S2 buffers before admitting a new candidate. |
| reset epoch and action/reset barriers | `SafetyLifecycle` | Supply immutable profile-ROS-time barriers; S2 does not create or translate them. |
| steady receive timestamp | Each local ingress boundary | Capture locally on receive/creation; compare only with that same boundary's steady `now`. |
| buffer order, eviction and selection | S2 ingress/synchronizer | Hold only active-lifecycle typed snapshots under the resolved buffer policy. |
| 81D vector | V3 pure assembler | Accept an S2-ready input set only; otherwise emit no vector. |

All candidate stamps and barriers are in active profile ROS time with matching
unit, `reset_epoch` and `runtime_generation`. In `sim_train` with
`use_sim_time=true`, emulator/local-goal stamps use that same profile ROS clock,
not a second simulation barrier. No cross-process steady timestamp is compared.

Reset or generation change atomically clears scan, motion and reference buffers.
New values must be strictly after the new barrier; an old numerical timestamp
never becomes valid again merely because it recurs in a new generation.

## 5. Admission and ordered buffering

Before insertion, every snapshot is already immutable and has passed its own
frame/unit/source/finite checks. S2 admits it only if it has:

1. exact active `reset_epoch` and `runtime_generation` metadata;
2. a finite profile-ROS stamp strictly after both applicable barriers;
3. compatible resolved source identity and snapshot contract;
4. a local ingress steady receive stamp for a same-boundary age check; and
5. no raw Ground Truth payload, synthetic public odometry/TF, PPO action,
   decoder result or V1 observation object.

At `assemble_at(ObservationCutoffV3)`, S2 first verifies transaction identity,
the canonical creation owner, epoch, generation, schema/config hash and barrier
values. If `cut_off_ros_ns` is not strictly later than **both** barriers, it
returns `CUTOFF_BARRIER_ORDER_NON_READY` before inspecting a buffer. It then selects only
`stamp_ros_ns <= cut_off_ros_ns` from that same object. A sample later than the
cut-off can remain ordered for a later transaction, but never repairs the
current observation. A sample more than `future_stamp_tolerance_ns` ahead of
that cut-off is rejected with `FUTURE_STAMP_CONTRACT_ERROR`.

Ingress assigns a local immutable arrival identity when an upstream message has
no portable sequence. It is only for ordering/duplicate diagnostics, not a new
ROS protocol or source-provenance replacement.

Buffers are ordered by `(stamp_ros_ns, stable_arrival_identity)`. Valid
out-of-order input may be inserted in order and is counted. A valid
out-of-order arrival or an exact duplicate is a diagnostic only: it does not by
itself make the transaction non-ready. An ordering status becomes non-ready
only when the selected candidate cannot be deterministically ordered, or when
one claimed source identity/sequence denotes conflicting immutable content.

## 6. Coherent-set selection

S2 builds and ranks a **global coherent triple**, never a scan-motion pair
followed by an optional reference lookup. A triple is eligible only when all
three entries are active-lifecycle, post-barrier, at/before the shared cut-off,
within their individual receive-age limits, and satisfy both:

```text
abs(scan_stamp_ros_ns - motion_stamp_ros_ns) <= sensor_sync_tolerance_ns
abs(reference_stamp_ros_ns - motion_stamp_ros_ns)
  <= max_reference_snapshot_skew_ns
```

For every eligible triple, define
`coherence_ros_ns = min(scan_stamp_ros_ns, motion_stamp_ros_ns,
reference_stamp_ros_ns)`. S2 chooses exactly one by this descending/ascending
lexicographic ranking:

1. greatest `coherence_ros_ns`;
2. smallest `max(scan_motion_skew_ns, reference_motion_skew_ns)`;
3. greatest `motion_stamp_ros_ns`, then `scan_stamp_ros_ns`, then
   `reference_stamp_ros_ns`; and
4. lexicographically smallest tuple of stable arrival identities.

Thus an older complete triple wins over a newer scan-motion pair that has no
compatible reference. The final arrival-identity rule makes selection
deterministic without treating valid out-of-order arrival as failure.

### 6.1 `sim_eval`, `deploy_sim` and `deploy_real`

The triple is `(LaserGeometrySnapshot, EkfMeasuredTwistSnapshot,
NavigationLocalReference)`. The selected EKF motion is the only measured-twist
source. Wheel command, final command and perfect simulated velocity are
forbidden substitutes.

### 6.2 `sim_train`

The triple is `(LaserGeometrySnapshot, SimulatedOdometryEmulator motion
snapshot, SimTrainLocalReferenceSnapshot)`. The local-reference snapshot must
derive from approved episode-goal intent and the **exact selected emulator
snapshot identity**: compatible contract, source identity and source sequence.
The selected noisy emulator snapshot is the sole measured-twist source.

The exact-snapshot identity is a `PROPOSED_DECISION`. It prevents a delayed
goal and measured twist from representing different noisy states, without
exposing Ground Truth or creating public odometry/TF. Receive-age checks remain
local to the boundary that captured them.

## 7. Fail-closed results

| Condition | Required result |
| --- | --- |
| no active scan/motion/reference | `INPUT_MISSING_NON_READY` |
| epoch/generation/source-contract mismatch | `LIFECYCLE_OR_CONTRACT_MISMATCH_NON_READY` |
| pre-barrier input | `BARRIER_NOT_PASSED_NON_READY` |
| cut-off at or before either SafetyLifecycle barrier | `CUTOFF_BARRIER_ORDER_NON_READY` |
| future-dated beyond tolerance | `FUTURE_STAMP_CONTRACT_ERROR` |
| receive age exceeded | `INPUT_STALE_NON_READY` |
| no coherent scan-motion pair | `SENSOR_SYNC_MISS_NON_READY` |
| reference mismatches selected motion | `REFERENCE_SYNC_MISS_NON_READY` |
| selected candidate cannot be deterministically ordered, or one claimed source identity/sequence has conflicting immutable content | `ORDERING_CONTRACT_AMBIGUITY_NON_READY` |
| overflow can have removed a viable match | `BUFFER_OVERFLOW_NON_READY` |
| generation change / clock rollback | `GENERATION_INVALIDATED_NON_READY` |

On overflow, evict the oldest ordered entry, increment the counter and mark the
affected transaction non-ready until a new coherent set exists. Every non-ready
result has no partial vector: no zero-fill, interpolation, stale reuse,
nearest-neighbour outside tolerance, V1 fallback or safety decision.

## 8. Separate semantic and numerical approval gates

### 8.1 Semantic ACR approval

Semantic approval requires only one synchronized architecture-review packet:

1. independent audit against Architecture and the approved receipt bundle;
2. user approval of this ACR's semantic rules: shared cut-off/global triple,
   canonical `RobotRuntimeAdapter` transaction ownership, clock/lifecycle
   ownership, exact emulator identity, buffer/failure policy and config-model
   shape; and
3. synchronized `ObservationInputContractV3` rev.6 and V3 Observation Boundary
   Specification rev.7 carrying this exact S2 ID/hash and cut-off invariant.

No YDLIDAR measurement, numerical timing value or profile evidence is a
precondition for this semantic decision.

### 8.2 Profile resolved-config approval

A particular profile may resolve S2 fields only when an evidence record for
that same profile/source identity contains:

| Value family | Required evidence |
| --- | --- |
| scan-motion tolerance | paired profile-ROS stamp trace, cadence/jitter and accepted bound |
| scan/motion/reference receive ages | local-ingress steady receive-time trace and accepted delay/jitter bound |
| reference-motion skew | reference and selected-motion stamp trace and accepted bound |
| future tolerance | clock/source timing evidence and declared skew treatment |
| buffer capacities | source rate, processing/pause/recovery delay and overflow analysis |

`sim_train`, `sim_eval` and `deploy_sim` may use approved `SIM_BASELINE`
evidence for their own profile only. `deploy_real` requires its own
`MEASURED_REGISTRY` evidence: no simulation cadence, transform or freshness
limit may be copied to YDLIDAR X3. Each record is ID/SHA-256 bound into
`config_hash`; unresolved `TBD_MEASURED` is invalid in `ResolvedConfigV3`.

### 8.3 Follow-on implementation readiness and runtime approval

Semantic approval does not authorize code. It permits only a separate
architecture readiness review for a non-resolving pure-Python contract/core
work package. That review must not resolve a profile or claim timing evidence.
Profile-specific implementation that resolves or executes a profile remains
gated by section 8.2.

Resolved configuration evidence is still not runtime evidence. Runtime, HIL and
YDLIDAR X3 deployment remain separate approval gates.

## 9. Required pure-Python acceptance seam

This draft authorizes no execution. A later pure-Python seam must prove:

1. post-barrier selection accepts only in-tolerance inputs at/before cut-off;
2. age uses same-boundary steady evidence, never cross-process subtraction;
3. reset, generation change and clock rollback clear buffers and reject old data;
4. `sim_train` local goal requires the exact selected emulator snapshot;
5. Ground Truth, synthetic public odometry/TF and PPO-derived goal/twist reject;
   and
6. overflow, duplicate, ordering, future-stamp and sync miss never create a
   partial vector or V1 fallback.

## 10. Canonical manifest and approval gate

The following canonical UTF-8 JSON has no whitespace or trailing newline. Its
SHA-256 is `1be31c1915fedd86f269cee5214d794da0899a0d69dbb0ba5392e619813d4a8f`.

```json
{"barrier_owner":"SafetyLifecycle","clock_rules":{"alignment":"PROFILE_ROS_TIME_SAME_EPOCH","freshness":"LOCAL_INGRESS_STEADY_TIME_ONLY","no_cross_process_steady_comparison":true},"contract_id":"mecanum.snapshot-synchronization-temporal/v1","cutoff":{"eligibility":"STRICTLY_AFTER_ACTION_AND_RESET_BARRIERS","identity":"ROBOT_RUNTIME_ADAPTER_WAIT_TRANSITION_SNAPSHOT_SUPPLIED_SHARED_WITH_S2_AND_RECEIPT_HISTORY","scope":"RESET_EPOCH_RUNTIME_GENERATION"},"future_stamp_policy":"REJECT_IF_GREATER_THAN_CUT_OFF_PLUS_CONFIGURED_TOLERANCE","input_groups":{"navigation":"SCAN_EKF_ODOM_LOCAL_REFERENCE","sim_train":"SCAN_EMULATOR_SNAPSHOT_INTERNAL_LOCAL_REFERENCE"},"lifecycle":{"generation_epoch":"EXACT_MATCH","reset":"CLEAR_BUFFERS_AND_REQUIRE_POST_BARRIER_INPUTS"},"ordering":{"valid_out_of_order":"DIAGNOSTIC_ONLY","non_ready":"ONLY_SELECTED_AMBIGUITY_OR_CONFLICTING_CLAIMED_IDENTITY"},"receipt_exclusions":["receipt_qos","receipt_gap","receipt_timeout"],"selection":"GLOBAL_LATEST_COHERENT_TRIPLE_AT_OR_BEFORE_CUTOFF","status":"NON_READY_NO_VECTOR","version":1}
```

Semantic approval requires **only** the three items in section 8.1, in one
review packet. Section 8.2 evidence is a separate prerequisite before an
individual profile can resolve numerical values; `deploy_real` further requires
its own `MEASURED_REGISTRY` record. It does not condition semantic approval.

This ACR does **not** approve implementation. After semantic approval, a
separate architecture review may decide whether a non-resolving pure-Python V3
contract/core work package is ready. Resolving or executing any profile still
requires its section 8.2 evidence.

`ACR_S2_SNAPSHOT_SYNCHRONIZATION_TEMPORAL_CONTRACT: DRAFT`\
`S2_SENSOR_TIMING: VALUES_UNRESOLVED`\
`V3_OBSERVATION_IMPLEMENTATION: NOT_AUTHORIZED`\
`RUNTIME_NOT_APPROVED`
