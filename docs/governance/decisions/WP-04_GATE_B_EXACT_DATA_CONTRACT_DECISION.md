# WP-04 Gate B Exact Data-Contract Decision

**Status:** `CANDIDATE_ONLY_PENDING_FOCUSED_INDEPENDENT_AUDIT_AND_CANONICAL_INTEGRATION`
**Work package:** `WP-04-GATE-B-EXACT-DATA-CONTRACT-CHANGE-CONTROL`
**Integration base:** `origin/integration/implementation@68174e714cbe8aab61880113496cd7ccd7f97f5d`
**Decision date:** `2026-10-11`
**Runtime status:** `RUNTIME_NOT_APPROVED`

This record captures the Project Owner/User decisions supplied for the exact Gate B data contract. It is candidate governance only; it does not itself activate the revised specification, authorize code, start Gate B, pass Gate B, or change WP status. Activation requires focused independent audit of the exact candidate, separate explicit User authorization for its exact final commit, a fast-forward to `integration/implementation`, and remote-ref verification.

## 1. Decision provenance and authority

The decision packet provenance is:

| Field | Value |
|---|---|
| Branch | `wp-04-gate-b-exact-data-contract-decision-68174e` |
| Commit | `0ce46d8751dd3f82fbbfc8b50b0f776e525d924b` |
| Parent/base | `68174e714cbe8aab61880113496cd7ccd7f97f5d` |
| Path | `docs/WP-04_GATE_B_EXACT_DATA_CONTRACT_DECISION_PACKET_DRAFT.md` |
| SHA-256 | `262a6ac47129172a6cc9ab49ffacb0891cdfcf35fd94bd34185aff9b0a284c42` |

The packet is provenance and a record of options, not the source of approval. The operative choices in this candidate are the User decisions stated in the current work-package authorization. Current approved design authority remains Architecture, QoS6, ACR8, the receipt v2 interface and their exact selected pins in the Canonical Source Registry and bundled approval record. This decision does not edit those sources.

## 2. Decisions recorded

### A. `ReceiptIngressBindingV3`

The selected representation is a flat record with the field set below, all required, keyword-only, and without defaults:

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

The selected fields use exact built-in `str`/`int`; subclasses, coercion, and `bool` as an integer are rejected. Values are compared exactly. Hash strings use lowercase 64-hex syntax and must equal the exact active pin or compiler-produced value. `observation_spec_revision >= 1`; episode generation is `0..2^64-1`; reset epoch and runtime generation are each `0..2^32-1`.

The flat shape is selected from Option A of the source packet, subject to the two explicit pin/config decisions below: `observation_spec_sha256` is excluded because only the specification revision is carried in the binding; `resolved_config_hash` is excluded because the sole canonical hash source is `ResolvedConfigV3.provenance.config_hash`. The remaining Option A binding members are required and retained.

The value semantics are frozen and slotted, field-wise equality/hash, default `repr`, and no serialization/export API. The binding remains outside the receipt message.

### B. Observation specification pin

The binding carries only `observation_spec_revision`. The full-document SHA is pinned externally by the Registry and this decision record; no self-hash is embedded in the specification or binding. A new specification revision requires an explicit authority update; there is no alias or automatic lookup.

### C. Lifecycle correspondence

Receipt eligibility compares the atomic exact tuple:

```text
receipt:  (episode_generation, reset_epoch, runtime_generation)
binding:  (expected_episode_generation, expected_reset_epoch, expected_runtime_generation)
```

`ObservationCutoffV3.epoch == reset_epoch` and `ObservationCutoffV3.generation == runtime_generation`. `episode_generation` participates in the comparison. Partial match, reuse, alias, and fallback are not allowed. `lifecycle_identity` is an exact string from the active `SafetyLifecycle` context; the adapter verifies it against the configured ingress binding and does not infer it from the receipt.

### D. Failure behavior

Use only existing ACR8 status vocabulary:

| Condition | Status/disposition |
|---|---|
| Missing required receipt | `INPUT_MISSING_NON_READY` |
| Contract/config/QoS/frame/lifecycle mismatch | `LIFECYCLE_OR_CONTRACT_MISMATCH_NON_READY` |
| Invalidated generation | `GENERATION_INVALIDATED_NON_READY` |
| Receipt at/before action or reset barrier | `BARRIER_NOT_PASSED_NON_READY` |
| Invalid cutoff/barrier order | `CUTOFF_BARRIER_ORDER_NON_READY` |
| Receipt later than cutoff | `FUTURE_STAMP_CONTRACT_ERROR` |
| Stale input under the approved profile rule | `INPUT_STALE_NON_READY` |
| Sensor/reference synchronization miss | `SENSOR_SYNC_MISS_NON_READY` / `REFERENCE_SYNC_MISS_NON_READY` |
| Buffer overflow | `BUFFER_OVERFLOW_NON_READY` |
| Duplicate, non-monotonic, or otherwise ambiguous ordering | `ORDERING_CONTRACT_AMBIGUITY_NON_READY` |
| Ambiguous/unverifiable identity correspondence or malformed/unverifiable source/provenance without an authorized mapping | `AUTHORITY_CHANGE_REQUIRED` |
| Valid QoS6 coalesced gap after a prior accepted receipt from the same publisher instance | `COALESCED_GAP` diagnostic; accept the newer otherwise-compatible latest state |

No status is created or weakened. Failures are fail-closed; no vector or fallback is produced where the ACR8 disposition requires rejection.

### E. Adapter/core boundary and timing ownership

The adapter is the only layer that receives raw ROS/generated objects. It validates message/interface pins, QoS and compatibility events, frame/planar-twist semantics, source/publisher provenance, lifecycle, timestamp domain, freshness, ordering, and barriers before passing data inward. The pure core receives only an immutable typed snapshot and the binding; it does not import ROS, perform I/O, read a clock, or inspect a repository.

The binding record contains contract/configuration references and lifecycle pins only. Timing/profile inputs remain in a separate resolved timing/profile record. The adapter owns middleware and ROS-time checks; the core consumes typed validated facts. No raw ROS object is permitted in pure core.

### F. Resolved configuration and compiler ownership

The selected composition is:

```text
ResolvedConfigV3.gate_b: ResolvedGateBRecordV3
```

The `ResolvedConfigV3` compiler is the sole constructor. The nested record contains the selected binding, exact `ObservationInputContractV3`, profile identity, and fully resolved non-pending values. No default, alias, coercion, unresolved token, caller construction, or partial record is permitted. Real-profile resolution is rejected while any required timing/profile value remains `PENDING_MEASUREMENT`.

### G. `config_hash` projection blocker

The sole canonical source is `ResolvedConfigV3.provenance.config_hash`, whose value is an exact lowercase 64-hex SHA-256 string. The hash is not duplicated in the binding or added to the receipt interface. The exact bytes/fields covered by the canonical hash projection and its self-reference exclusions are not decided here. This item remains exactly:

```text
DECISION_DEFERRED_PENDING_EXACT_NON_CIRCULAR_PROJECTION
```

No code authorization and no claim that the binding is fully implementable may issue until a separate governance decision defines the exact projection, covered fields, canonicalization, and self-reference exclusions, and that decision is audited. This is the sole remaining Gate B data-contract change-control blocker before a code-authorization candidate may be considered. Pending measurements remain a separate profile/runtime eligibility condition, not a numeric value selected by this record.

## 3. Authority pins

| Artifact | Identity/path | SHA-256 |
|---|---|---|
| Observation V3 Specification | revision 2 candidate; `docs/OBSERVATION_V3_SPECIFICATION.md` | `3a90e7bfddbe52be0011a77c8f1d2c24190222770174486414ddd2ca6d450cb3` (external pin; not embedded in itself) |
| Receipt | `mecanum.final-issued-receipt/v2`; `ros2_ws/src/mecanum_nav_rl_interfaces/msg/FinalIssuedCommandReceipt.msg` | `0c6446674bf17373ec646519043f506a9a7a15f95d5fdd10829b0cedb956500a` |
| QoS6 transport | `mecanum.final-issued-receipt-topic-qos/v2`; `docs/RECEIPT_TOPIC_QOS_CONTRACT.md` | Manifest `338bea1b7350d3b82146c7e728516ec7947471ee68db0f8871ddb72071b79620`; full document `4200cd2fbdc81a19400f168dd3526eb7871ac2251049fc7c4f5d5c2fddfd2022` |
| Dependency closure | `docs/RECEIPT_INTERFACE_DEPENDENCY_CLOSURE_MANIFEST.json` | `0872fa8c10179f69c2e9e9546392ac734a4f4e94ade176a8be431f06905ecf73` |
| ACR8 | `docs/ACR_V3_OBSERVATION_BOUNDARY_CLOSURE.md` | `03fef021f6b9731f811f83a5e53aae1c430bdc2ea76815a8ada416f1a5bf772c` |
| QoS6/ACR8 approval | `docs/governance/decisions/QOS_REVISION_6_ACR_REVISION_8_BUNDLE_APPROVAL.md` | `4d740559f850f179387db802df845748068f75a21266fd1edb52402b2c72c529` |
| Gate A structural schema | `docs/OBSERVATION_GATE_A_STRUCTURAL_SCHEMA.md` | `43537b8f0edafbe809e6f70bda86808f87b12f146ed45509c4bfbacd26956ad3` |
| Gate A error-carrier decision | `docs/governance/decisions/WP-04_GATE_A_ERROR_CARRIER_DECISION.md` | `72a2c94df548cb00557b1777e10d11b96b386329894edaf34e1d81c07ed4e94d` |

## 4. Status and authorization boundary

This five-path bundle is candidate-only until audit, separate exact-commit User integration authorization, fast-forward, and remote verification. It records no status transition and grants no code, ROS/ROSIDL, adapter, runtime, HIL, hardware, `deploy_sim`, or `deploy_real` authority. It does not change WP-05 or its status.

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
