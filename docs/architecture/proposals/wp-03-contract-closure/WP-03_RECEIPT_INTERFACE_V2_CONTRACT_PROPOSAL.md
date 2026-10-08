# WP-03 — Receipt Interface v2 Contract Proposal

**Status:** `DRAFT_FOR_INDEPENDENT_AUDIT_AND_USER_DECISION`
**Baseline:** `integration/implementation@9a4c0d233e8237f01a04880fe99e8a3114528f4`
**Proposed interface ID:** `mecanum.final-issued-receipt/v2`
**Proposed schema revision:** `2`
**Schema artifact:** `docs/architecture/proposals/wp-03-contract-closure/WP-03_RECEIPT_INTERFACE_V2_DRAFT.msg`
**Schema SHA-256:** `0c6446674bf17373ec646519043f506a9a7a15f95d5fdd10829b0cedb956500a`

This proposal defines a candidate public receipt schema for review. It is not a ROSIDL implementation, canonical contract, or authorization to implement or run the interface. The schema file is kept in the proposal area as requested.

## 1. Identity and disposition of the v1 pin

QoS revision 5 and ACR revision 7 pin `mecanum.final-issued-receipt/v1` to SHA-256 `90348664c4563997b93de7f10e278b10d4053fcb96909b6bb85c1319db76c40e`. The user-provided completed provenance search found no matching artifact. This proposal does not assign the v1 ID or hash to the v2 schema and does not claim schema compatibility with v1.

The proposed v2 ID identifies the candidate schema bytes above. If approved, the old v1 pin must be expressly dispositioned in both companion contracts; it must not be silently repointed. A hash-only replacement is appropriate only if the exact same interface identity and schema definition are recovered and verified. A changed public schema requires an explicitly approved version/identity disposition. The present proposal chooses a new `/v2` identity for audit; it does not canonically supersede v1.

## 2. Schema fields

The `.msg` draft contains only fields supported by the approved D2 decisions, QoS revision 5 §4, and `CommandEnvelope.msg`, plus the wire choices explicitly approved for this proposal by the Project Owner/User.

| Field(s) | Proposed meaning and constraints | Basis |
|---|---|---|
| `header` | `std_msgs/Header`; `frame_id` is exactly `base_link`. Its stamp is evaluated in the ROS-time domain under QoS §6 action/reset barrier rules. | QoS §§2, 6; D2 profile boundary |
| `episode_generation`, `reset_epoch`, `runtime_generation` | Flattened `EpisodeLifecycleIdentity`; types are respectively `uint64`, `uint32`, `uint32`. | User-approved wire decisions; `CommandEnvelope` fixes the latter two widths |
| `step_index`, `transition_id` | Flattened transition identity; `step_index` is `uint64`; `transition_id` is a bounded 36-character ASCII UUID string. Together with lifecycle fields these bind the active transition. | User-approved wire decisions; approved D2 direct binding |
| `source` | `uint8` and constants mirror `CommandEnvelope`: UNKNOWN=0, POLICY=1, NAV2=2, TELEOP=3, SAFE_STOP=4. UNKNOWN is non-ready; accepted sources remain POLICY, NAV2, TELEOP, SAFE_STOP. | QoS §4; `CommandEnvelope.msg`; D2 |
| `sequence`, `reset_epoch`, `runtime_generation`, `source_instance_id` | Preserve the corresponding `CommandEnvelope` field names, widths, constants, and semantics. Types are `uint64`, `uint32`, `uint32`, `uint64`. | QoS §4; `CommandEnvelope.msg` |
| `final_publisher_instance_id` | `uint64`; identifies one `FinalTwistPublisher` process instance and changes when that process restarts. | QoS §4; D2 |
| `final_publish_sequence` | `uint64`; starts at 1 for each publisher instance, strictly increases for each emitted receipt, and does not reset at `reset_epoch`. | QoS §4; D2 |
| `final_command` | `geometry_msgs/Twist`; finite planar physical `base_link` command: `linear.x=vx`, `linear.y=vy`, `angular.z=wz`; `linear.z`, `angular.x`, `angular.y` are exactly zero. | QoS §4; D2 |

The schema intentionally adds no normalized-command, `config_hash`, profile, handoff-status, or transport-manifest field. D2 permits normalized values only when an exact conversion contract supplies their semantics and provenance; no such values are selected here. The interface ID and schema hash are pinned by companion records, not self-embedded in the message.

## 3. Identity validation

`transition_id` must be exactly 36 ASCII characters in lowercase canonical UUID textual form, with hyphens at positions 9, 14, 19, and 24 and hexadecimal characters elsewhere (`[0-9a-f]`). The bounded ROS string enforces the maximum length; contract validation enforces exact length, ASCII, lowercase, hyphen positions, and hexadecimal syntax. This proposal does not impose UUID version or variant restrictions.

The flattened lifecycle fields and transition fields represent the direct `EpisodeLifecycleIdentity` and `TransitionIdentity` binding selected by D2. There is no nested message and no separate `ScenarioSessionBinding`; the scenario/session linkage remains indirect through `EpisodeLifecycle`.

## 4. Ownership and lifecycle

`SafetySupervisor` remains the sole owner of arbitration, validation, limiting, smoothing, and final-command selection. `FinalTwistPublisher` owns receipt creation after the selected command crosses the applicable successful final boundary. The receipt records the selected result; it does not select or modify the command.

For simulation, creation follows successful completion of the approved local publish-issuance boundary; merely starting a publish call is insufficient. The receipt does not prove DDS delivery, Gazebo application, actuator acknowledgement, or robot movement. `deploy_real` remains unavailable: a separate approved ROS-to-transport handoff boundary and success condition must first be defined in its own contract. This v2 proposal does not add transport behavior or a deploy profile binding.

Receipt identity is distinct from transition identity. `(final_publisher_instance_id, final_publish_sequence)` identifies the publisher receipt stream; it cannot replace the lifecycle/transition binding. A receipt is not an actuator acknowledgement.

## 5. Validation and failure semantics

The receiver validates the schema/contract identity, frame, finite planar command, source, lifecycle identity, transition identity, and the separate receipt sequence according to QoS §4–6 and the approved D2 decisions. UNKNOWN source, invalid or mismatched identity, duplicate/replay, non-monotonic sequence, stale/future transition, lifecycle mismatch, source mismatch, and failed final boundary are not admitted as a ready receipt and follow the existing fail-closed contract behavior. The publisher emits no ready receipt when its boundary fails.

This proposal adds no new failure status, recovery path, timeout, reset behavior, or inference. Existing action/reset barrier and lifecycle rules remain controlled by QoS and D2. A later validation failure after issue does not imply rollback; D2's `STEP_ABORT`/`FAULT` semantics remain in force.

## 6. Provenance and scope

The schema SHA identifies the exact `.msg` proposal bytes only. It is not the transport manifest hash. QoS transport ID `mecanum.final-issued-receipt-topic-qos/v1`, manifest SHA-256 `a3bc1a965fc6885825ab961289fa4028862aa7af4b3f3156bc40542f7ee08f62`, QoS policies, delivery/coalescing semantics, and action/reset readiness behavior remain unchanged in these proposals.

The QoS revision 5 / ACR revision 7 bundle remains the canonical authority at the stated baseline until a new bundle is independently audited, explicitly user-approved, and canonically integrated under governance. This proposal changes no canonical file and does not close WP-03 or authorize code, ROS, runtime, HIL, hardware, or `deploy_real`.

## 7. Pending review

The auditor and Project Owner/User must review the proposed field layout, UUID validation rule, v2 identity, v1 disposition, and companion pin changes. Until that review and governance process complete, the candidate schema and all amendment wording remain non-canonical proposals.

```text
WP-02: CLOSED
WP-03: BLOCKED_BY_CONTRACT
WP-04: BLOCKED_BY_CONTRACT
CODE_AUTHORIZATION: NOT_GRANTED
RUNTIME_APPROVED: NOT_APPROVED
```
