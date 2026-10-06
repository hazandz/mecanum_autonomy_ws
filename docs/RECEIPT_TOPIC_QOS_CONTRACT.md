# Receipt Topic QoS Contract

**Revision:** `5` (proposal draft)
**Status:** `DRAFT_FOR_INDEPENDENT_AUDIT_AND_USER_APPROVAL`
**Authority role:** proposed revision; not current authority
**Current authority:** Receipt Topic QoS Contract revision `4` remains current until a revision 5 bundle is approved and canonically integrated.
**Runtime status:** `RUNTIME_NOT_APPROVED`

The following approval and erratum records are reproduced from revision 4 as historical context only; they do not approve this revision 5 draft.

**Bundled approval:** user approval on `2026-10-03` (Asia/Saigon), together
with `ACR_V3_OBSERVATION_BOUNDARY_CLOSURE` revision `6`. This approval
authorizes follow-on configuration and interface design only. It does not
authorize implementation, ROS runtime, build, test, training, HIL, hardware,
merge, or push.

**Erratum R4-E1 (2026-10-03):** Section 10's stale reference to ACR revision
`5` is corrected to revision `6`. This is a traceability-only correction: the
canonical JSON manifest, public protocol, QoS settings, contract ID and SHA-256
remain unchanged.

## 1. Purpose and boundary

This contract defines one public DDS boundary that carries evidence of the
latest command *actually issued by* `FinalTwistPublisher` after safety
arbitration:

```text
FinalTwistPublisher
  -- /mecanum/final_issued_command --> V3ObservationIngress
```

The topic is a read-only **latest-final-command state receipt**, not an
actuator command channel, an actuator acknowledgement, a safety-state
replacement, or an unbounded audit-event log.  It exists so the V3 observation
features `[78..80]` can represent the most recent final-issued physical
`[vx, vy, wz]`, rather than a PPO action or decoder candidate.

This contract owns DDS transport semantics and ingress gap classification.  It
does **not** select a sensor timing value, an X3 parameter, a ROS node
implementation, or a runtime approval.

## 2. Exact public endpoint

| Item | Proposed canonical value | Rule |
| --- | --- | --- |
| Topic | `/mecanum/final_issued_command` | One topic only; no topic alias or fallback. |
| Message type | `mecanum_nav_rl_interfaces/msg/FinalIssuedCommandReceipt` | A new versioned public interface, not `SafetyState`. |
| Publisher | `FinalTwistPublisher` | The sole logical publisher; it remains the sole `/cmd_vel` publisher. |
| Subscriber | `V3ObservationIngress` | Read-only ingress for the V3 observation boundary; it never publishes a command. |
| Frame | `base_link` | Every accepted receipt has exactly this `header.frame_id`; no frame aliasing. |
| Topic QoS ID | `Q_FINAL_ISSUED_RECEIPT_V1` | The ID below is part of the resolved topic/QoS record. |
| Contract ID | `mecanum.final-issued-receipt-topic-qos/v1` | Its canonical manifest is versioned and hashed before implementation. |

The future resolved V3 configuration must contain one direct
`TopicQosContractV3` record with these endpoint values.  The record is not
created by this design draft.

## 3. Proposed QoS profile

| QoS policy | Required value | Why this value is required |
| --- | --- | --- |
| Reliability | `RELIABLE` | A final-command receipt is safety/observation evidence; best-effort loss must not be silently treated as a command state. |
| Durability | `TRANSIENT_LOCAL` | A restarting observation subscriber receives the latest publisher-retained receipt, then validates its lifecycle, contract, and barriers. It never treats replay alone as evidence for a later action. |
| History | `KEEP_LAST` | The observation needs the latest final-issued state, not a complete command-event log. |
| Depth | `1` | Only the most recent state is retained. Earlier receipts may be coalesced and that coalescing is explicitly detectable below. |
| Deadline | disabled / infinite | An unchanged final command may legitimately produce no new receipt; a generic DDS deadline would incorrectly label that state stale. |
| Lifespan | disabled / infinite | DDS must not discard a retained receipt merely because it is old; lifecycle and action/reset barriers decide eligibility. |
| Liveliness | `AUTOMATIC`, lease disabled / infinite | This contract does not use liveliness to detect a dead writer. It is neither evidence that a command is fresh nor a receipt-readiness signal. |

`TRANSIENT_LOCAL + KEEP_LAST(1)` is deliberate.  A late-joining observation
process can recover the last state, while `reset_epoch`, `runtime_generation`,
contract hashes, and the action/reset barriers prevent an old retained receipt
from satisfying a new action or a new reset.  `VOLATILE` is rejected because it
could indefinitely block a recovered observer when the final command has not
changed.

No finite liveliness lease is selected.  A dead final-publisher process is
therefore not detected through DDS liveliness in this version of the contract.
The fail-closed path is the action/reset receipt wait in section 6 plus explicit
lifecycle transitions.  Adding a finite lease later requires a new QoS-contract
version, a profile-owned value with evidence/provenance, and architecture
review; it cannot be inferred by an implementation.

## 4. Receipt publication and message preconditions

The publisher emits one receipt immediately after it locally issues the final
`/cmd_vel` `Twist`.  `PUBLICATION_ISSUED` means only that this local issue was
performed.  It does not claim DDS delivery, actuator acknowledgement, wheel
motion, or achieved velocity.

Before this QoS contract can be approved, the receipt-interface contract must
lock all of the following:

1. `source`, `sequence`, `reset_epoch`, `runtime_generation`, and
   `source_instance_id` exactly mirror `CommandEnvelope` widths and source
   constants.  An accepted source is one of `POLICY`, `NAV2`, `TELEOP`, or
   `SAFE_STOP`; `UNKNOWN` is non-ready.
2. `final_command` is planar physical `base_link` velocity:
   `linear.x = vx`, `linear.y = vy`, `angular.z = wz`; all three are finite;
   `linear.z`, `angular.x`, and `angular.y` are exactly zero.  The command must
   be the final safety-arbitrated command for the envelope, not a candidate.
3. Add `uint64 final_publisher_instance_id` to
   `FinalIssuedCommandReceipt`.  It identifies one `FinalTwistPublisher`
   process instance and changes whenever that process restarts.  The existing
   `source_instance_id` belongs to the originating command source and cannot
   safely serve this purpose.
4. `final_publish_sequence` is `uint64`, starts at `1` for each
   `final_publisher_instance_id`, and strictly increases for every receipt
   emitted by that publisher instance.  It does not reset at `reset_epoch`.
5. `CommandArbiter`, under `SafetySupervisor` authority, owns
   `source_instance_id` and `sequence` for a new-epoch `SOURCE_SAFE_STOP` zero
   envelope.  `FinalTwistPublisher` publishes its final `Twist` and receipt; it
   does not fabricate an envelope.

Items 3–5 are protocol corrections required before the ACR message schema is
implementation authority.  They do not add actuator semantics.

## 5. Transport ordering, coalescing, and ingress status

The ingress tracks accepted delivery order independently for each
`(runtime_generation, final_publisher_instance_id)` pair.  It must never
compare a final-publisher sequence with `CommandEnvelope.sequence`: the two
counters have different owners and purposes.

| Condition at ingress | Classification | Effect on receipt state |
| --- | --- | --- |
| First compatible receipt for an active publisher instance | `ACCEPTED` | Store as the latest eligible receipt. |
| `final_publish_sequence = previous + 1` | `ACCEPTED` | Replace latest eligible receipt. |
| `final_publish_sequence > previous + 1`, after ingress has accepted a prior receipt from the same publisher instance | `COALESCED_GAP` | Record diagnostic gap, then accept the newer receipt. With depth 1, this is expected coalescing, not evidence that the latest final command is unknown. |
| Same sequence again | `DUPLICATE` | Reject the delivery; keep the previously accepted receipt only if it remains otherwise eligible. |
| Lower sequence for same publisher instance | `NON_MONOTONIC` | Reject the delivery and report transport/protocol fault. |
| Middleware reports an incompatible-QoS or message-loss condition, where the selected DDS implementation exposes that event | `TRANSPORT_UNHEALTHY` | Reject the affected delivery. A later fully compatible receipt may restore admissibility. This rule does not claim dead-writer detection. |
| ID/hash, schema, config, frame, source, planar-twist, epoch, or generation mismatch | `CONTRACT_OR_LIFECYCLE_MISMATCH` | Reject; no adaptation, inference, or fallback. |

A `COALESCED_GAP` is intentionally not a policy-observation failure by itself.
It is detectable only after ingress has previously admitted a receipt from the
same publisher instance. A late joiner receiving its first retained receipt
classifies it as `ACCEPTED`; it cannot infer whether older receipts were
coalesced. The latest receipt still describes the final command state. In contrast,
duplicates, backward order, and transport failures that are actually reported cannot be repaired
by using a PPO action, `SafetyState`, a cached decoder result, or a synthetic
zero.

The subscriber records its own local steady receive time only for diagnostics.
It never subtracts that value from a steady timestamp created in the safety
process, because those clock domains are not a shared cross-process contract.

## 6. Action/reset freshness rule

There is deliberately **no global receipt-age timeout**.  A final command can
remain valid while unchanged; the safety watchdog is responsible for issuing a
later safe-stop command when that command should cease to be valid.

Instead, receipt readiness is action-bound:

`SafetyLifecycle` creates and owns the ROS-time action and reset barrier
timestamps. This contract does not create, advance, or reinterpret them; it
defines only the predicate that an admitted receipt has a timestamp strictly
after the externally supplied barrier.

1. At a normal action barrier, the observation transaction waits for a
   compatible receipt with `header.stamp > action_barrier_ros_ns` and
   `header.stamp <= observation_cut_off_ros_ns`.
2. At reset, it waits for the ACR-selected new-epoch post-reset-barrier
   `SOURCE_SAFE_STOP` zero receipt before encoding `observation0`.
3. A durable replay may initialize history for the active lifecycle, but can
   never satisfy either barrier unless its ROS timestamp is strictly after that
   barrier.
4. If no qualifying receipt arrives within the profile-owned
   `receipt_after_barrier_timeout_ns`, ingress reports
   `RECEIPT_AFTER_BARRIER_TIMEOUT`; V3 core returns `NON_READY` and must not
   construct an 81D vector.

The timeout is not a DDS deadline and this contract intentionally assigns it
no numeric value.  It belongs to the approved, resolved
`ObservationInputContractV3` and requires its own timing evidence.

## 7. Single ownership of each rule

| Contract/layer | Sole responsibility | Must not own |
| --- | --- | --- |
| This Receipt Topic QoS Contract | Topic identity, QoS profile, publisher/subscriber transport ownership, delivery ordering, `COALESCED_GAP`, transport-health classification, and the receipt-after-supplied-barrier predicate. | Creating/owning barrier timestamps, sensor synchronization, or the policy's vector-production response. |
| Receipt interface/bridge contract | Message fields, ID/hash/version compatibility, physical command semantics, source provenance, and cut-off selection among already admitted receipts. | DDS QoS or observation timeout numbers. |
| `ObservationInputContractV3` | `receipt_after_barrier_timeout_ns` and the response to an ingress status: `NON_READY`, no vector. | QoS policies, gap detection, or receipt schema duplication. |
| Safety lifecycle and `CommandArbiter` | Action/reset barriers and construction of SAFE_STOP envelopes. | Subscriber delivery status and core observation fallback. |
| S2 snapshot temporal contract | Scan/odometry/reference synchronization only. | Receipt-topic QoS, receipt gaps, or receipt wait timeout. |

ACR revision 6 has removed duplicate `receipt gap/status policy` ownership from
both `ObservationTimingPolicyV3` and `ReceiptBridgeReferenceV3`. They reference
this contract by exact ID/hash and do not restate its transport rules.

## 8. Configuration and compatibility bindings

Before implementation, the approved config composition must bind these exact
references into the resolved configuration and its hash:

```text
TopicQosContractV3(
  name="/mecanum/final_issued_command",
  message_type="mecanum_nav_rl_interfaces/msg/FinalIssuedCommandReceipt",
  publisher_owner="FinalTwistPublisher",
  subscriber_owner="V3ObservationIngress",
  qos_profile_id="Q_FINAL_ISSUED_RECEIPT_V1",
  frame_contract_id="BASE_LINK_PLANAR_TWIST_V1",
  freshness_policy_id="ACTION_BOUND_RECEIPT_V1",
)
```

`CommandSafetyContractV3` must reference the receipt-interface contract and
this QoS contract by exact ID and SHA-256.  `ReceiptBridgeReferenceV3` may
reference those same exact values.  A subscriber rejects a message or config
whose interface ID/hash, topic-QoS ID/hash, observation schema ID, or resolved
config hash differs from the active resolved contract.

The exact receipt-interface pair required by this topic is
`mecanum.final-issued-receipt/v1` /
`90348664c4563997b93de7f10e278b10d4053fcb96909b6bb85c1319db76c40e`.

The canonical UTF-8 JSON manifest for this draft has no whitespace or trailing
newline:

```json
{"contract_id":"mecanum.final-issued-receipt-topic-qos/v1","frame_contract_id":"BASE_LINK_PLANAR_TWIST_V1","freshness_policy_id":"ACTION_BOUND_RECEIPT_V1","owners":{"publisher":"FinalTwistPublisher","subscriber":"V3ObservationIngress"},"qos":{"deadline":"INFINITE","depth":1,"durability":"TRANSIENT_LOCAL","history":"KEEP_LAST","lifespan":"INFINITE","liveliness":"AUTOMATIC","liveliness_lease":"INFINITE","reliability":"RELIABLE"},"receipt_interface":{"contract_id":"mecanum.final-issued-receipt/v1","sha256":"90348664c4563997b93de7f10e278b10d4053fcb96909b6bb85c1319db76c40e"},"status_policy":{"barrier_timestamp_owner":"SafetyLifecycle","coalesced_gap":"ACCEPT_NEWER","coalesced_gap_detection":"ONLY_AFTER_PRIOR_RECEIPT_SAME_INSTANCE","dead_writer_detection":"NOT_USED","duplicate":"REJECT","message_loss":"REJECT_UNTIL_COMPATIBLE_RECEIPT","nonmonotonic":"REJECT","qos_incompatible":"REJECT_UNTIL_COMPATIBLE_RECEIPT"},"topic":"/mecanum/final_issued_command","type":"mecanum_nav_rl_interfaces/msg/FinalIssuedCommandReceipt","version":1}
```

Its exact SHA-256 is
`a3bc1a965fc6885825ab961289fa4028862aa7af4b3f3156bc40542f7ee08f62`.
The ID/hash pair is frozen at approval time.  No runtime process may compute a
replacement, drop a field, or use a compatibility alias.

## 9. Required design-time acceptance cases

No test or runtime operation is authorized by this draft.  A future pure-Python
ingress test seam must nevertheless prove at least:

1. a post-action compatible receipt becomes eligible and normalizes only the
   final physical `[vx, vy, wz]` at observation positions `[78..80]`;
2. `COALESCED_GAP` is emitted only after an earlier accepted receipt from the
   same publisher instance; a late joiner's first retained receipt is
   `ACCEPTED`; a duplicate or non-monotonic sequence is rejected;
3. a durable pre-barrier receipt cannot satisfy a new action or reset;
4. missing receipt until the configured action-bound timeout produces
   `NON_READY`, never a decoder/PPO/`SafetyState` fallback;
5. source, enum width, planar-twist, frame, publisher-instance, contract hash,
   schema hash, config hash, epoch, and generation mismatches fail closed; and
6. a new-epoch SAFE_STOP zero has `CommandArbiter` provenance and is selected
   for `observation0` only after the reset barrier.

## 10. Approval gates and final status

**DRAFT — proposed QoS Contract revision 5.** This section is not effective unless this complete revision 5 draft and ACR revision 7 are independently audited, explicitly approved together, and canonically integrated under the repository workflow. Until then, revision 4 remains current authority and its §10 remains unchanged.

This proposed revision 5 preserves the historical approval event recorded above for revision 4 (approval on `2026-10-03` with ACR revision `6`) and the historical R4-E1 traceability correction. Neither historical record is rewritten or backdated. Any future approval of this revision 5 bundle must be recorded as a separate event on its actual date.

The transport contract identity remains `mecanum.final-issued-receipt-topic-qos/v1`, with canonical transport-manifest SHA-256 `a3bc1a965fc6885825ab961289fa4028862aa7af4b3f3156bc40542f7ee08f62`, only on the condition that the canonical manifest remains byte-identical to revision 4 and its hash recomputes to that value. The `/v1` suffix identifies the transport contract/manifest version; it is distinct from this document's revision number. This revision 5 draft changes approval-scope wording only and makes no transport or public-protocol change.

### 10.1 Proposed bundled approval

If approved, the bundle comprises:

1. this Receipt Topic QoS Contract document revision `5`, identified by its exact document revision and document SHA-256 recorded externally in the companion approval/change-control record;
2. `ACR_V3_OBSERVATION_BOUNDARY_CLOSURE` revision `7`;
3. the R4-E2 traceability disposition in this draft's §10.2, which updates the current operative companion reference to ACR revision 7; and
4. the R4-A1 approval-scope amendment incorporated into this draft's §10.3, not a sidecar with independent or separate authority.

The approval record must distinguish the SHA-256 of this revision 5 document from the canonical transport-manifest SHA-256. The document hash is computed over the finalized document bytes and is recorded externally in the bundled approval record and companion proposal references; it is not embedded in this document, so no self-referential hash is created. The transport-manifest hash continues to identify only the canonical transport manifest.

R4-E2 is not applied retroactively to historical revision 4. Its proposed effect is represented here by the operative ACR revision 7 reference in this draft. R4-A1 is merged into this proposed revision 5 §10.3; it has no separate normative authority outside this draft and approval bundle. Neither amendment is effective before approval and canonical integration.

### 10.2 Proposed companion reference (R4-E2 disposition)

For this proposed revision 5 only, the current operative companion reference is `ACR_V3_OBSERVATION_BOUNDARY_CLOSURE` revision `7`. This replaces the operative revision 6 reference prospectively within the draft. The historical revision 4 approval event and its R4-E1 record remain unchanged; R4-E2 is not applied to or used to rewrite revision 4.

### 10.3 Proposed approval scope (R4-A1 disposition)

This subsection is the proposed substantive approval-scope amendment formerly identified as R4-A1. It is incorporated into QoS Contract revision 5 and is not an erratum or a separately authoritative sidecar.

This document may become design authority only after the applicable bundle and evidence below are approved together:

1. this Receipt Topic QoS Contract revision 5, including its exact document SHA-256 recorded in the companion approval record and unchanged transport contract ID/manifest hash;
2. ACR revision 7; and
3. for Gate B, the resulting public-interface version/hash and resolved-config binding.

#### Gate A — primitive-only

For a constrained primitive-only packet, the proposed §10(3) requirement is satisfied by recording the exact approved contract ID/SHA references and structural-validation scope. Gate A does not create or bind `ResolvedConfigV3`, create a config hash, or implement a public interface or topic. It therefore does not require a resulting public-interface version/hash or resolved-config binding as a Gate A artifact or precondition.

Gate A remains subject to the PEP-001 WP-04 → WP-03 dependency, the safety/lifecycle/temporal and Ground Truth isolation constraints, canonical semantic-bundle requirements, and all separately applicable governance gates. This proposed scope does not close WP-03, alter the dependency, or grant implementation authorization.

#### Gate B — connected/profile-resolving

Before connected or profile-resolving implementation, the approved resulting public-interface version/hash and resolved-config binding remain required, together with all other applicable ACR §8 gates and profile-specific evidence. This includes the applicable canonical ACR/specification record; bundled QoS approval and topic/QoS record; `ObservationInputContractV3` canonical source/compiler/composition validation with no unresolved values; receipt message/topic and compatibility checks; typed pure-Python ingress seams; and independent evidence that the 81D layout and process/safety isolation remain preserved.

This amendment does not select or waive profile timing, buffer, freshness, measured-twist validity/covariance/provenance, or YDLIDAR X3 extrinsic/range/frame evidence.

This proposed revision changes no transport QoS policy, topic, message fields, public protocol, endpoint, owner, gap/stale behavior, safety boundary, or canonical transport manifest. It does not waive lifecycle, temporal, safety, or Ground Truth isolation requirements; alter WP-04's dependency on WP-03; close WP-03; or authorize code, build, tests, runtime, hardware, or HIL.

### 10.4 Draft status

```text
QOS_REVISION_5: DRAFT_PENDING_INDEPENDENT_AUDIT_AND_USER_APPROVAL
QOS_REVISION_4: CURRENT_AUTHORITY_UNTIL_REVISION_5_BUNDLE_APPROVED_AND_CANONICALLY_INTEGRATED
R4_E2: PROPOSED_IN_REVISION_5_ONLY; NOT_APPLIED_TO_HISTORICAL_REVISION_4
R4_A1: INCORPORATED_IN_DRAFT_REVISION_5_SECTION_10_3; NO_SEPARATE_AUTHORITY
WP-03: BLOCKED_BY_CONTRACT
WP-04: BLOCKED_BY_CONTRACT
CODE_AUTHORIZATION: NOT_GRANTED
RUNTIME_NOT_APPROVED
```

This document remains a proposal. It does not modify canonical revision 4, ACR revision 6, PEP-001, the progress ledger, source code, interfaces, configuration, or runtime authority.
