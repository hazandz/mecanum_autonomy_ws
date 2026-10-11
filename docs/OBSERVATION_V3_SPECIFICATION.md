# Observation V3 Specification

**Revision:** `2`
**Status:** `CANDIDATE_ONLY_PENDING_FOCUSED_INDEPENDENT_AUDIT_AND_CANONICAL_INTEGRATION`
**Work package:** `WP-04-GATE-B-EXACT-DATA-CONTRACT-CHANGE-CONTROL`
**Candidate base:** `origin/integration/implementation@68174e714cbe8aab61880113496cd7ccd7f97f5d`
**Runtime status:** `RUNTIME_NOT_APPROVED`

This revision records the Project Owner/User's exact Gate B data-contract decisions supplied for this work package. It is a candidate only until this exact five-path change-control candidate passes independent audit, receives separate User authorization for its exact final commit, is fast-forwarded to `integration/implementation`, and the remote ref is verified. It does not authorize implementation, pass Gate B, close WP-04, or authorize runtime.

## 1. Change provenance and authority

The decision source is the audited decision packet `wp-04-gate-b-exact-data-contract-decision-68174e@0ce46d8751dd3f82fbbfc8b50b0f776e525d924b`, path `docs/WP-04_GATE_B_EXACT_DATA_CONTRACT_DECISION_PACKET_DRAFT.md`, SHA-256 `262a6ac47129172a6cc9ab49ffacb0891cdfcf35fd94bd34185aff9b0a284c42`. The Owner decisions in this change-control are supplied in the current User work-package instruction; the packet is provenance, not independent authority and not a substitute for this exact decision.

The governing architecture remains `docs/MECANUM_NAV_DRL_Architecture.docx`. Current approved Gate A/Gate B contract authority remains ACR revision 8 and Receipt Topic QoS Contract revision 6, as selected by the Registry and the integrated QoS6/ACR8 approval record. Receipt, dependency-closure, transport-manifest, and full-document hashes identify distinct byte sets and are not interchangeable.

| Artifact | Exact identity | Canonical path | SHA-256 |
|---|---|---|---|
| ACR | revision 8 | `docs/ACR_V3_OBSERVATION_BOUNDARY_CLOSURE.md` | `03fef021f6b9731f811f83a5e53aae1c430bdc2ea76815a8ada416f1a5bf772c` |
| Receipt Topic QoS Contract | revision 6; `mecanum.final-issued-receipt-topic-qos/v2` | `docs/RECEIPT_TOPIC_QOS_CONTRACT.md` | Full document `4200cd2fbdc81a19400f168dd3526eb7871ac2251049fc7c4f5d5c2fddfd2022`; transport manifest `338bea1b7350d3b82146c7e728516ec7947471ee68db0f8871ddb72071b79620` |
| Receipt interface | `mecanum.final-issued-receipt/v2`, schema revision 2 | `ros2_ws/src/mecanum_nav_rl_interfaces/msg/FinalIssuedCommandReceipt.msg` | `0c6446674bf17373ec646519043f506a9a7a15f95d5fdd10829b0cedb956500a` |
| Dependency closure | version 1 | `docs/RECEIPT_INTERFACE_DEPENDENCY_CLOSURE_MANIFEST.json` | `0872fa8c10179f69c2e9e9546392ac734a4f4e94ade176a8be431f06905ecf73` |
| QoS6/ACR8 approval | bundled approval record | `docs/governance/decisions/QOS_REVISION_6_ACR_REVISION_8_BUNDLE_APPROVAL.md` | `4d740559f850f179387db802df845748068f75a21266fd1edb52402b2c72c529` |
| Gate A structural schema | Gate A only | `docs/OBSERVATION_GATE_A_STRUCTURAL_SCHEMA.md` | `43537b8f0edafbe809e6f70bda86808f87b12f146ed45509c4bfbacd26956ad3` |
| Gate A error-carrier decision | Gate A only | `docs/governance/decisions/WP-04_GATE_A_ERROR_CARRIER_DECISION.md` | `72a2c94df548cb00557b1777e10d11b96b386329894edaf34e1d81c07ed4e94d` |

The integrated boundary-closure candidate is active on the integration line at the base. This revision extends its exact data contract; it does not alter ACR8, QoS6, receipt v2 bytes, the Gate A schema, or the Gate A error-carrier decision. S2 revision 2, Observation Input Contract revision 6, and V3 Observation Boundary Specification revision 7 remain provenance-only and do not supply fields or defaults.

## 2. Observation layout and ownership boundary

The observation remains exactly 81 `float32` values in the frozen order: 72 LiDAR sectors; 3 LocalReference features; 3 measured-twist features `[vx, vy, wz]`; and 3 previous-final-issued-command features `[vx, vy, wz]`. Feature ownership, frame/normalization rules, Ground Truth exclusion, and the distinction among raw action, decoded candidate, and final-issued command remain governed by Architecture and the approved contracts. This revision selects no numeric profile parameter.

The pure-Python core receives immutable typed snapshots and the binding defined below. It does not import or receive raw ROS/generated objects, access middleware, perform I/O, read a clock, inspect files or repositories, resolve hashes, normalize frames, or fabricate fallback data. The adapter is the only layer permitted to receive raw ROS/generated objects.

## 3. `ReceiptIngressBindingV3`

The binding is a flat, immutable, keyword-only value outside `FinalIssuedCommandReceipt.msg`. All listed members are required; there are no defaults, aliases, fallback, lookup, normalization, or coercion.

```text
ReceiptIngressBindingV3(
  *,
  receipt_interface_id: str,
  receipt_interface_sha256: str,
  dependency_closure_manifest_sha256: str,
  qos_contract_id: str,
  transport_manifest_sha256: str,
  observation_spec_revision: int,
  profile_id: str,
  lifecycle_identity: str,
  expected_episode_generation: int,
  expected_reset_epoch: int,
  expected_runtime_generation: int,
)
```

The binding uses exact built-in `str` and exact built-in `int`; subclasses and numeric coercion are rejected, and `bool` is not accepted as an integer. Values are compared exactly. Hash members must match lowercase 64-hex syntax and equal the applicable exact pinned/compiler-produced value. `observation_spec_revision >= 1`. `expected_episode_generation` is in `0..2^64-1`; `expected_reset_epoch` and `expected_runtime_generation` are each in `0..2^32-1`, matching their receipt interface widths.

The selected receipt and QoS identities are `mecanum.final-issued-receipt/v2` and `mecanum.final-issued-receipt-topic-qos/v2`, with the hashes pinned in §1. The observation specification binding contains only `observation_spec_revision`; its full-document SHA is pinned externally in the Registry/decision record. A later specification revision requires an authority update; there is no runtime alias or automatic lookup. `resolved_config_hash` is not duplicated in this binding; its sole canonical location is `ResolvedConfigV3.provenance.config_hash` as defined in §7.

`profile_id` is a required exact string identifying the selected approved profile in the compiler-owned resolved configuration; no profile value is selected by this document. `lifecycle_identity` is an exact string from the active `SafetyLifecycle` context. The adapter verifies it against the configured ingress binding; it is not derived from a receipt field.

The value representation is frozen and slotted, with field-wise equality and hash, default representation, and no serialization/export API. The binding is outside the ROS message; the receipt v2 message remains byte-identical.

## 4. Lifecycle correspondence and receipt eligibility

The receipt lifecycle tuple is `(episode_generation, reset_epoch, runtime_generation)`. Compatibility is an atomic exact equality against `(expected_episode_generation, expected_reset_epoch, expected_runtime_generation)` in the binding. Partial match, reuse, alias, or fallback is not allowed. `ObservationCutoffV3.epoch` equals `reset_epoch`; `ObservationCutoffV3.generation` equals `runtime_generation`. `lifecycle_identity` equals the exact identity from the active `SafetyLifecycle` context after the adapter verifies that context against the configured ingress binding; it is not inferred from the receipt.

A receipt is eligible only if that tuple and active identity are compatible, the receipt is strictly after both action and reset barriers, and its stamp is at or before the observation cutoff. A receipt at/before either barrier, after cutoff, or associated with a mismatching or invalidated lifecycle is rejected. The tuple is evaluated atomically; no partial match or episode-value reuse is permitted.

The adapter validates message/interface pins, publisher/source provenance, QoS compatibility/events, frame and planar-twist contract, timestamp domain, freshness, lifecycle tuple, sequence ordering, and barrier/cutoff eligibility before constructing typed core inputs. Core receives no raw message or ROS-generated value.

## 5. Fail-closed status mapping

Use only existing ACR8 vocabulary; do not add a status. The following dispositions preserve the current ACR8/QoS6 boundary:

| Condition | Existing status/disposition |
|---|---|
| Required receipt missing through the resolved action-bound timeout | `INPUT_MISSING_NON_READY`; no vector or fallback |
| Contract/config/lifecycle/QoS/frame ID or SHA mismatch, including tuple mismatch | `LIFECYCLE_OR_CONTRACT_MISMATCH_NON_READY`; reject |
| Invalidated generation | `GENERATION_INVALIDATED_NON_READY`; reject prior-generation data |
| Receipt at/before action or reset barrier | `BARRIER_NOT_PASSED_NON_READY`; reject |
| Cutoff not strictly after both barriers | `CUTOFF_BARRIER_ORDER_NON_READY`; reject cutoff |
| Receipt later than observation cutoff | `FUTURE_STAMP_CONTRACT_ERROR`; reject without clock reinterpretation |
| Stale receipt under the applicable approved profile rule | `INPUT_STALE_NON_READY`; reject |
| Sensor synchronization miss | `SENSOR_SYNC_MISS_NON_READY`; reject synchronized input |
| Reference synchronization miss | `REFERENCE_SYNC_MISS_NON_READY`; reject synchronized input |
| Buffer overflow | `BUFFER_OVERFLOW_NON_READY`; fail closed |
| Ordering ambiguity, duplicate, or non-monotonic sequence | `ORDERING_CONTRACT_AMBIGUITY_NON_READY`; reject |
| Ambiguous/unverifiable lifecycle identity correspondence or malformed/unverifiable source/provenance with no authorized mapping | `AUTHORITY_CHANGE_REQUIRED`; stop, no new status |
| Coalesced sequence gap after a prior accepted receipt from the same publisher instance | QoS6 `COALESCED_GAP`; diagnostic gap and accept the newer otherwise-compatible latest state |

The transport rule for a late joiner's first retained sample remains `ACCEPTED`; coalesced-gap handling does not replace QoS6 ordering or publisher-instance requirements. No failure may be repaired with PPO action, cached data, `SafetyState`, or synthetic zero.

## 6. Adapter, core, and timing records

`ReceiptIngressBindingV3` contains immutable contract/configuration references and lifecycle pins only. Timing/profile inputs are held separately in the resolved observation-input/timing record. The ROS adapter validates raw message type, interface ID/hash, QoS ID/transport manifest and compatibility events, frame, source/enum and publisher provenance, lifecycle, timestamp domain, freshness, ordering, and barriers. It passes an immutable typed snapshot and the binding to the pure core. No raw ROS object crosses the seam.

The adapter owns ROS time and middleware checks. Core consumes typed, already-validated facts and does not read a clock. QoS6 continues to define action-bound readiness, strict post-barrier receipt ordering, cutoff eligibility, depth-1 coalescing and duplicate/non-monotonic rejection. There is no global receipt-age timeout. The action-bound timeout is owned by the resolved input contract/profile.

All unmeasured sensor freshness, skew, buffer capacity, receipt-after-barrier timeout, measured-twist validity/covariance/provenance, LiDAR timing, and X3 extrinsic/range/frame values remain `PENDING_MEASUREMENT`. A real-profile resolution is rejected while any required measurement is pending. No numeric measurement or profile value is invented here.

## 7. Resolved configuration and `config_hash`

The selected boundary is a nested compiler-owned record:

```text
ResolvedConfigV3(
  ...,
  provenance: ResolvedConfigProvenanceV3,
  gate_b: ResolvedGateBRecordV3,
)
```

`ResolvedConfigV3.gate_b` is required, complete, immutable, and constructed only by the `ResolvedConfigV3` compiler. The resolved Gate B record contains the selected `ReceiptIngressBindingV3`, exact `ObservationInputContractV3`, selected profile identity, and fully resolved non-pending values. There is no caller construction, partial record, default, alias, coercion, lookup, normalization, or unresolved token.

The sole canonical `config_hash` source is `ResolvedConfigV3.provenance.config_hash`; its value is an exact lowercase 64-hex SHA-256 string. It is not duplicated in `ReceiptIngressBindingV3` or added to the receipt message. **The exact non-circular hash projection remains unresolved:** covered fields/bytes and self-reference exclusions have not been canonically selected or audited. The decision is therefore `DECISION_DEFERRED_PENDING_EXACT_NON_CIRCULAR_PROJECTION`. No code authorization or claim that the binding is fully implementable may issue until a separate governance decision pins and audits the exact projection, covered fields, and exclusions.

No unresolved token/default/alias/coercion is allowed in a real resolved Gate B profile. Required timing/profile values that remain `PENDING_MEASUREMENT` cause the compiler to reject real-profile resolution. Fixtures are not measurements or runtime evidence.

## 8. Candidate state and authorization boundary

This revision records the selected exact public data contract except for the explicitly deferred config-hash projection. That projection is the sole remaining contract change-control blocker before a Gate B code-authorization candidate can be considered. Separate focused audit, exact-scope implementation packet, and explicit User code authorization remain required; this candidate grants none of them.

```text
WP-04: BLOCKED_BY_CONTRACT
GATE_A_STRUCTURAL_PRIMITIVES: PASSED
GATE_B: NOT_STARTED
GATE_B_BOUNDARY_CLOSURE: ACTIVE_ON_INTEGRATION
CONFIG_HASH_PROJECTION: DECISION_DEFERRED_PENDING_EXACT_NON_CIRCULAR_PROJECTION
CODE_AUTHORIZATION: NOT_GRANTED
RUNTIME_APPROVED: NOT_APPROVED
WP-05: OPEN
```
