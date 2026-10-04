# ACR V3 Observation Boundary Closure

**Revision:** `6`
**Status:** `APPROVED_BY_USER — BUNDLED_ARCHITECTURE_DECISION`
**Runtime status:** `RUNTIME_NOT_APPROVED`
**Change class:** observation semantics, typed cross-process protocol, and resolved-config schema extension

**Bundled approval:** user approval on `2026-10-03` (Asia/Saigon), together
with `RECEIPT_TOPIC_QOS_CONTRACT` revision `4`.  This approval authorizes
follow-on configuration and interface design only. It does not authorize
implementation, ROS runtime, build, test, training, HIL, hardware, merge, or
push.

## 1. Decision requested

This ACR closes the gaps that prevent the V3 observation specification from becoming implementation authority:

1. reset semantics for previous issued command in `observation0`;
2. transport of final-issued command evidence from the safety process to the policy/observation process;
3. resolved V3 configuration ownership for observation input policies; and
4. precise LiDAR range and `LocalReference` feature semantics.

It does not alter the 81-element layout or `/cmd_vel` ownership. It introduces a public receipt protocol, therefore an approved ACR is required.

## 2. Authority and facts

| Authority fact | Consequence |
| --- | --- |
| Observation is fixed `float32[81]`: 72 LiDAR, goal distance/sin/cos, measured twist, previous issued command. | No feature is added, removed, or reordered. |
| `LaserGeometrySnapshot` includes `T_base_lidar`; profile TF/extrinsic is locked and X3 extrinsic is measured. | V3 binds and validates the transform; it has no default. |
| Scan/odometry use ROS-time barriers and pairwise sync; `LocalReference` is checked against odometry; steady receive time is local. | Receipt history cannot use sensor-skew or a foreign steady clock. |
| Safety is an independent process; `FinalTwistPublisher` is the sole `/cmd_vel` publisher. | A local Python receipt cannot reach policy observation. |
| Existing shared DDS interfaces are `Heartbeat`, `SafetyState`, `NavigationState`, and `CommandEnvelope`. | `SafetyState` cannot substitute for a receipt: it lacks ordering, full provenance, schema binding and per-issue identity. |
| Resolved V3 config contains no tokens and its hash covers resolved semantics. | `TBD_MEASURED` and other tokens are pre-resolution only. |

`ACR_S2_Snapshot_Synchronization_Temporal_Contract` remains pending and owns numerical sensor timing and buffer decisions. This record chooses no timing number and does not override S2.

## 3. Decision A — reset closure for `observation0`

### Proposed decision

The canonical previous issued command for `observation0` is a **new-epoch, post-reset-barrier SAFE_STOP zero receipt**. It is final-issued evidence, not a core-created default and not the pre-reset zero from the prior epoch.

### Required event order

1. `ResetManager` sets `reset_in_progress=true` and inhibits normal sources.
2. `FinalTwistPublisher` emits the architecture-required pre-reset zero.
3. Reset increments `reset_epoch`, clears command/history state, and completes simulator/task mutation.
4. It sets the ROS-time reset barrier and starts collecting new-epoch sensors.
5. `CommandArbiter`, under `SafetySupervisor` authority, selects one `SOURCE_SAFE_STOP` zero envelope in the new epoch with ROS stamp strictly greater than the reset barrier. `FinalTwistPublisher` publishes the resulting final zero `Twist` and emits the corresponding receipt.
6. The observation layer waits for valid scan/odometry and `LocalReference`, selects that receipt, and encodes `observation0`.
7. Only after successful encoding may reset release control.

If step 5 or 6 fails, reset remains inhibited and returns failure. No synthetic zero, old receipt, or fabricated observation is permitted.

### Why approval is required

The frozen architecture clears previous-issued history before `observation0` but does not define the new-epoch value at positions `[78..80]`. Selecting the post-barrier zero closes that ambiguity and changes trained-observation semantics. This decision is `ACR_REQUIRED`.

## 4. Decision B — final-issued receipt bridge

### Selected boundary

Add one typed DDS message and one read-only topic:

```text
FinalTwistPublisher
  -- /mecanum/final_issued_command (FinalIssuedCommandReceipt.msg) -->
V3 observation ingress
```

`FinalTwistPublisher` is the only publisher. V3 observation ingress is a subscriber only. This topic never commands an actuator, does not replace `/cmd_vel`, and cannot bypass `SafetySupervisor`.

Private shared-memory objects and co-locating policy with safety are rejected: they make the process/lifecycle boundary implicit and are not reviewable as a cross-process contract.

### Message schema to approve

Only ROS-time fields cross processes. Safety keeps its local steady timestamps for TTL/watchdog work; they are not exported as comparable timestamps.

```text
# FinalIssuedCommandReceipt.msg
# header.stamp: ROS time of local /cmd_vel issue
# header.frame_id: base_link

std_msgs/Header header                # required; stamp and frame above
uint8 source                         # CommandEnvelope source constants
uint64 sequence                       # source-envelope sequence
uint32 reset_epoch
uint32 runtime_generation
uint64 source_instance_id

uint64 final_publisher_instance_id    # changes whenever FinalTwistPublisher restarts
uint64 final_publish_sequence         # starts at 1 and is monotonic per publisher instance
uint8 DECISION_UNKNOWN=0
uint8 DECISION_PASS_THROUGH=1
uint8 DECISION_LIMITED=2
uint8 DECISION_SAFE_STOP=3
uint8 DECISION_ESTOP=4
uint8 decision_code
uint8 PUBLICATION_ISSUED=1
uint8 publication_result               # receipt exists only after ISSUED

string receipt_contract_id              # mecanum.final-issued-receipt/v1
string receipt_contract_sha256          # canonical receipt-contract hash
string observation_schema_id           # obs-v3-l72-g3-t3-c3-f32
string resolved_config_hash             # canonical V3 SHA-256
geometry_msgs/Twist final_command      # physical base_link [vx, vy, wz]
```

`final_publisher_instance_id` identifies the `FinalTwistPublisher` process
instance and must change when it restarts.  `final_publish_sequence` starts at
`1` for that instance, strictly increases for every emitted receipt, and does
not reset at `reset_epoch`.  Ingress compares it only within
`(runtime_generation, final_publisher_instance_id)`; it never substitutes the
originating `CommandEnvelope.sequence`.

`final_command` is a planar physical `base_link` command: `linear.x`,
`linear.y`, and `angular.z` are finite `vx`, `vy`, and `wz`; `linear.z`,
`angular.x`, and `angular.y` are exactly zero.  `CommandArbiter`, under
`SafetySupervisor` authority, owns `source_instance_id` and `sequence` for the
new-epoch `SOURCE_SAFE_STOP` zero envelope. `FinalTwistPublisher` only issues
the final Twist and the corresponding receipt; it never fabricates an envelope.

No `receipt_id`, actuator acknowledgement, QoS-delivery claim, source string,
safety-process steady timestamp, or detailed reason-bits field belongs in this
message. Detailed intervention reasons remain in `SafetyState` and diagnostics;
V3 needs only `decision_code` and final-command provenance. Missing receipt,
wrong enum/mode, non-monotonic final sequence, duplicate sequence, or
contract/schema/config-hash/lifecycle mismatch yields non-ready observation.

The new topic requires one explicit `TopicQosContractV3` record and the exact
approved Receipt Topic QoS Contract pair:
`mecanum.final-issued-receipt-topic-qos/v1` /
`a3bc1a965fc6885825ab961289fa4028862aa7af4b3f3156bc40542f7ee08f62`.
It defines `RELIABLE + TRANSIENT_LOCAL + KEEP_LAST(1)`, delivery ordering,
coalesced-gap handling, and action-bound receipt readiness. It intentionally
does **not** use an infinite liveliness lease to claim dead-writer detection.
S2 can constrain sensor timing only and cannot choose this topic's QoS.

### Version, hash, and compatibility

Adding `FinalIssuedCommandReceipt.msg` is an additive public-interface change. It requires `mecanum_nav_rl_interfaces` to move from `2.4.0` to `2.5.0`, an interface changelog entry, and interface-contract tests.

`receipt_contract_id` is exactly `mecanum.final-issued-receipt/v1`.
`receipt_contract_sha256` is exactly
`90348664c4563997b93de7f10e278b10d4053fcb96909b6bb85c1319db76c40e`.
It is the SHA-256 of the canonical UTF-8 JSON manifest below, with no
whitespace or trailing newline. It excludes profile values and runtime
timestamps. A V3 observation subscriber accepts only this exact ID/hash pair;
no field-dropping, aliasing, conversion, or compatibility fallback is
permitted.

```json
{"compatibility":"EXACT_ID_AND_SHA256_NO_ALIAS_OR_FIELD_DROPPING","constants":{"decision_code":{"DECISION_ESTOP":4,"DECISION_LIMITED":2,"DECISION_PASS_THROUGH":1,"DECISION_SAFE_STOP":3,"DECISION_UNKNOWN":0},"publication_result":{"PUBLICATION_ISSUED":1},"source":{"SOURCE_NAV2":2,"SOURCE_POLICY":1,"SOURCE_SAFE_STOP":4,"SOURCE_TELEOP":3,"SOURCE_UNKNOWN":0}},"contract_id":"mecanum.final-issued-receipt/v1","field_order":[{"constraints":{"frame_id":"base_link","stamp":"ROS_TIME_OF_LOCAL_CMD_VEL_ISSUE"},"name":"header","type":"std_msgs/Header"},{"name":"source","type":"uint8"},{"name":"sequence","type":"uint64"},{"name":"reset_epoch","type":"uint32"},{"name":"runtime_generation","type":"uint32"},{"name":"source_instance_id","type":"uint64"},{"name":"final_publisher_instance_id","type":"uint64"},{"name":"final_publish_sequence","type":"uint64"},{"name":"decision_code","type":"uint8"},{"name":"publication_result","type":"uint8"},{"name":"receipt_contract_id","type":"string"},{"name":"receipt_contract_sha256","type":"string"},{"name":"observation_schema_id","type":"string"},{"name":"resolved_config_hash","type":"string"},{"constraints":{"finite":["linear.x","linear.y","angular.z"],"frame":"base_link","must_equal_zero":["linear.z","angular.x","angular.y"],"physical_components":["vx","vy","wz"]},"name":"final_command","type":"geometry_msgs/Twist"}],"ownership":{"final_publisher":"FinalTwistPublisher","safe_stop_envelope":"CommandArbiter_under_SafetySupervisor"},"publication_semantics":"LOCAL_CMD_VEL_ISSUE_ONLY_NOT_DDS_DELIVERY_OR_ACTUATOR_ACK","selection_rule":{"barrier":"EXTERNAL_RECEIPT_TOPIC_QOS_PREDICATE","candidate":"HEADER_STAMP_LE_CUT_OFF","group":"RUNTIME_GENERATION_AND_FINAL_PUBLISHER_INSTANCE","winner":"GREATEST_FINAL_PUBLISH_SEQUENCE"},"sequence_rule":{"final_publish_sequence":"STARTS_AT_1_STRICTLY_INCREASES_PER_FINAL_PUBLISHER_INSTANCE_NEVER_RESETS_AT_RESET_EPOCH","final_publisher_instance_id":"CHANGES_ON_FINAL_TWIST_PUBLISHER_PROCESS_RESTART","source_instance_id_and_sequence":"ORIGINATING_COMMAND_ENVELOPE_ONLY"},"source_acceptance":{"accepted":[1,2,3,4],"rejected":[0]},"version":1}
```

### Selection rule

At `cut_off_ros_ns`, history admits only transport-admitted compatible receipts
with `header.stamp <= cut_off_ros_ns`, then selects the greatest
`final_publish_sequence` within the active
`(runtime_generation, final_publisher_instance_id)`. Action/reset-barrier
timestamps are created and owned only by the safety lifecycle. The Receipt
Topic QoS Contract receives those timestamps as inputs and owns only the
predicate that a receipt is after the supplied barrier, plus coalesced-gap
classification. No sensor-skew test or cross-process steady-clock comparison is
used. A later SAFE_STOP zero wins naturally.

## 5. Decision C — resolved V3 observation-input contract

### Config-model change

Add one profile-owned, fully resolved field to `ResolvedConfigV3`:

```text
observation_input: ObservationInputContractV3
```

The existing `observation` section remains the base-owned frozen vector schema (81 dimensions, dtype and component order). `observation_input` owns physical and temporal input semantics that differ by runtime profile.

| Subcontract | Required resolved fields | Owner and provenance rule |
| --- | --- | --- |
| `LidarInputContractV3` | header frame, `T_base_lidar`, extrinsic identity, FOV/angular window, 72 bin boundaries, endpoint convention, range minimum/maximum, invalid/no-return policy IDs, range-value semantic | runtime-profile-owned; `deploy_real` needs approved measured registry/provenance |
| `GoalInputContractV3` | `goal_distance_scale_m`, local-reference source/derivation policy | runtime-profile-owned and bound into config hash |
| `ObservationTimingPolicyV3` | scan/odometry sync tolerance, individual receive-age limits, reference-to-odometry skew limit, `receipt_after_barrier_timeout_ns`, and response `NON_READY` | runtime-profile-owned; sensor values remain blocked by S2/evidence, while receipt timeout requires separate receipt-specific evidence and is not supplied by S2 |
| `ReceiptBridgeReferenceV3` | exact receipt-interface ID/SHA-256 and exact receipt-topic-QoS ID/SHA-256 | profile-owned reference; it must point to one command-safety-owned receipt contract and one QoS contract without restating their rules |

`CommandSafetyContractV3` must gain `final_issued_receipt_contract_id`,
`final_issued_receipt_contract_sha256`,
`final_issued_receipt_topic_qos_contract_id`, and
`final_issued_receipt_topic_qos_contract_sha256`. That command-safety-owned
contract declares the receipt schema/version, topic-contract pair,
publisher/subscriber ownership, and sequence rule. `observation_input` may only
reference it; it must not duplicate or redefine the safety or QoS contracts.

Composable-layer ownership must be amended so runtime-profile owns `observation_input`, alongside runtime-specific limits. It must not implicitly merge into base-owned `observation`.

Raw assets may contain typed tokens such as `TBD_MEASURED`; the compiler must reject them before constructing `ResolvedConfigV3`. `sim_train` can resolve only approved simulation-baseline values. `deploy_real` requires concrete approved measured values and registry provenance.

## 6. Decision D — geometric and goal semantics

### LiDAR sectors

Each of the 72 LiDAR values is the **sanitized sensor-ray range**, normalized by profile sensor `range_max`. Its angular sector is determined by transforming the ray endpoint with configured `T_base_lidar` and taking its bearing in `base_link`.

The value is deliberately not reinterpreted as base-radial distance. This preserves profile `range_max` normalization while mapping a rotated or offset LiDAR to the correct base-frame sector. The semantic is part of `LidarInputContractV3` and the resolved config hash.

### Local reference

`LocalReference` remains a stamped, lifecycle-bound point in `base_link`. V3 core derives distance and bearing from that point, then emits `clip(distance_m / goal_distance_scale_m, 0, 1)`, `sin(bearing_rad)`, and `cos(bearing_rad)`. Adapter-provided distance/bearing are diagnostics only; they never supply policy features.

## 7. Approval scope and exclusions

This ACR and its separate Receipt Topic QoS Contract form one approval bundle;
neither may be approved alone. After that bundle is approved, it approves
together:

- new-epoch SAFE_STOP zero receipt for `observation0`;
- the public receipt message/topic and ownership boundary;
- the `observation_input` resolved-config extension and fragment ownership;
- sensor-ray range with base-link endpoint bearing; and
- core-derived goal distance/bearing from the base-link point.

This ACR approves the semantic QoS profile only: `RELIABLE + TRANSIENT_LOCAL +
KEEP_LAST(1)` with disabled deadline, lifespan, and liveliness lease. It does
not approve any finite timeout/lease value, LiDAR mounting transform, X3 driver,
serial setting, range/cadence, hardware measurement, ROS node, build, test,
runtime, training, HIL, or hardware action.

## 8. Gates after approval

Before a V3 core implementation packet may be issued:

1. record this approved ACR in architecture/governance and update the V3 observation specification;
2. approve the bundled Receipt Topic QoS Contract with its canonical ID/hash,
   delivery/coalescing/action-bound readiness behavior, and
   `TopicQosContractV3` record; this is separate from S2;
3. design `ObservationInputContractV3` model, canonical source, compiler and composition validation with no unresolved values in resolved config;
4. add receipt message/topic, version/hash compatibility checks and its canonical topic/QoS record;
5. define pure-Python ingress seams for typed snapshots and receipt data; and
6. obtain an independent audit that 81D layout and process/safety isolation remain preserved.

Only then may a later work package implement the connected pure-Python V3 assembler/encoder/history path. Runtime integration is a separate gate.

## 9. Final status

`ACR_V3_OBSERVATION_BOUNDARY_CLOSURE: APPROVED_FOR_FOLLOW_ON_DESIGN_ONLY`
`RECEIPT_TOPIC_QOS_CONTRACT: APPROVED_IN_SAME_BUNDLE`
`V3_OBSERVATION_BOUNDARY: NOT_IMPLEMENTATION_AUTHORITY_YET`
`RUNTIME_NOT_APPROVED`

## 10. Status-only erratum (2026-10-04)

The semantics of ACR S2 revision 2, Observation Input Contract V3 revision 6,
and V3 Observation Boundary Specification revision 7 are approved for
follow-on design only. Profile-specific numerical sensor timing, buffer, and
freshness values and their evidence remain unresolved. This erratum changes
status/traceability only; it does not change receipt protocol semantics or the
approval of this ACR revision 6 and Receipt Topic QoS Contract revision 4.
No implementation or runtime authorization is granted.
