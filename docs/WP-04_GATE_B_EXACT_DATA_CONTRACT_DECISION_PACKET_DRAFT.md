# WP-04 Gate B Exact Data-Contract Decision Packet

**Status:** `DRAFT_FOR_OWNER_DECISION_AND_FOCUSED_AUDIT`
**Work package:** `WP-04-GATE-B-EXACT-DATA-CONTRACT-DECISION-PACKET`
**Integration baseline:** `origin/integration/implementation@68174e714cbe8aab61880113496cd7ccd7f97f5d`
**Review branch:** `wp-04-gate-b-exact-data-contract-decision-68174e`
**Decision basis:** active Gate B boundary-closure bundle at the baseline and its explicitly recorded pending exact data-contract items.

This packet presents choices for Project Owner/User decision. **No option below is approved by this packet.** It is not a contract amendment, implementation authorization, Gate B pass, or runtime approval. The Owner-supplied proposal name referenced by the boundary-closure record is not treated as a Git-pinned authority; no report hash is asserted.

## 1. Current authority and exact pins

The integrated Gate B boundary-closure bundle makes `docs/OBSERVATION_V3_SPECIFICATION.md` revision 1 the controlled specification source for this decision scope. The source selection is active at this integration baseline. The exact public shape of `ReceiptIngressBindingV3`, the resolved Gate B record, and receipt-to-cutoff lifecycle correspondence are still `PENDING_OWNER_DECISION`. Earlier PEP/Registry wording that describes the bundle as candidate/pending is retained pre-activation wording; this packet does not edit those governance files.

The controlling pins remain:

| Artifact | Identity | Path | SHA-256 |
|---|---|---|---|
| Receipt interface | `mecanum.final-issued-receipt/v2`, schema rev.2 | `ros2_ws/src/mecanum_nav_rl_interfaces/msg/FinalIssuedCommandReceipt.msg` | `0c6446674bf17373ec646519043f506a9a7a15f95d5fdd10829b0cedb956500a` |
| Receipt QoS contract | `mecanum.final-issued-receipt-topic-qos/v2`, QoS rev.6 | `docs/RECEIPT_TOPIC_QOS_CONTRACT.md` | Transport manifest `338bea1b7350d3b82146c7e728516ec7947471ee68db0f8871ddb72071b79620`; full document `4200cd2fbdc81a19400f168dd3526eb7871ac2251049fc7c4f5d5c2fddfd2022` |
| Dependency closure | closure v1 | `docs/RECEIPT_INTERFACE_DEPENDENCY_CLOSURE_MANIFEST.json` | `0872fa8c10179f69c2e9e9546392ac734a4f4e94ade176a8be431f06905ecf73` |
| Observation V3 Specification | rev.1 | `docs/OBSERVATION_V3_SPECIFICATION.md` | `feffb86e335d64a3a3fe0f3a1ce0866f868c8ed56ffa4412db14128c80b284ec` |
| Gate A structural schema | Gate A only | `docs/OBSERVATION_GATE_A_STRUCTURAL_SCHEMA.md` | `43537b8f0edafbe809e6f70bda86808f87b12f146ed45509c4bfbacd26956ad3` |
| Gate A error-carrier decision | Gate A only | `docs/governance/decisions/WP-04_GATE_A_ERROR_CARRIER_DECISION.md` | `72a2c94df548cb00557b1777e10d11b96b386329894edaf34e1d81c07ed4e94d` |

The receipt schema, dependency-closure manifest, transport manifest, and full-document hashes identify distinct byte sets. The receipt v2 message remains byte-identical; `config_hash` must not be added to it. S2 rev.2, OIC rev.6, and V3 Spec rev.7 remain provenance-only and cannot supply defaults or extra fields.

## 2. Decision A — `ReceiptIngressBindingV3`

The active boundary decision requires an immutable wrapper/config record outside the ROS message. It does not yet select its exact public member set. The following two shapes are choices for the Owner, not approved APIs.

### Option A — Flat binding record (`PROPOSAL_ONLY`)

```text
ReceiptIngressBindingV3(
  *,
  receipt_interface_id: str,
  receipt_interface_sha256: str,
  dependency_closure_manifest_sha256: str,
  qos_contract_id: str,
  transport_manifest_sha256: str,
  observation_spec_revision: int,
  observation_spec_sha256: str,
  resolved_config_hash: str,
  profile_id: str,
  lifecycle_identity: str,
  expected_episode_generation: int,
  expected_reset_epoch: int,
  expected_runtime_generation: int,
)
```

Every member is required; no default. Candidate exact-type policy: built-in `str` for identifiers/hashes and built-in `int` for revisions/generation values, with `bool` rejected for integer members. Pinned identities/hashes compare byte-for-byte. Numeric generation values are non-negative. Hash fields must equal their active pinned values or the exact compiler-produced config hash, not be normalized or resolved by lookup. The receipt supplies the first three lifecycle values except `lifecycle_identity`; that identity would be obtained from the trusted active lifecycle context, not fabricated from a ROS field.

**Tradeoff:** explicit flat fields make pin review straightforward, but duplicate values already represented by the resolved configuration and make lifecycle correspondence more visible and less compact.

### Option B — Nested exact-reference records (`PROPOSAL_ONLY`)

```text
ReceiptIngressBindingV3(
  *,
  receipt_interface_reference: ContractReferenceV3,
  dependency_closure_manifest_sha256: str,
  qos_reference: ContractReferenceV3,
  observation_spec_revision: int,
  observation_spec_sha256: str,
  resolved_config_hash: str,
  profile_id: str,
  lifecycle_binding: LifecycleBindingV3,
)
```

`ContractReferenceV3` is the existing Gate A type. `LifecycleBindingV3` would require its own exact approved field set and is not defined by Gate A. Each nested object is required; no defaults. `LifecycleBindingV3` exact types/comparison remain a separate choice in §3.

**Tradeoff:** nesting reuses the existing reference value type and separates lifecycle fields, but introduces a new public nested type and a larger equality/API surface.

### Questions for this record

1. Select flat Option A or nested Option B, or specify an exact alternative shape.
2. Confirm the requiredness and type policy above, or give exact replacements. In particular, decide whether all strings use exact built-in `str`, whether numeric values use exact built-in `int`, and whether hash syntax is validated or only equality to pinned/compiler-produced values is checked.
3. Decide whether the record contains an observation-spec hash before the final full-document hash is known. If not, specify the non-circular version/provenance reference and how a later spec revision changes the pin.
4. Decide the exact ownership and provenance source of `profile_id`; it may not be chosen from an unapproved profile or draft.

## 3. Decision B — Lifecycle correspondence and receipt eligibility

The receipt v2 message contains `episode_generation` (`uint64`), `reset_epoch` (`uint32`), and `runtime_generation` (`uint32`). Gate A `ObservationCutoffV3` contains `lifecycle_identity: str`, `epoch: int`, and `generation: int`. Receipt v2 has no `lifecycle_identity` field. The Owner must select how those facts correspond; no string conversion, alias, inference, or draft-derived mapping is permitted.

### Tuple choices (`PROPOSAL_FOR_USER_DECISION`)

| Choice | Exact comparison proposal | Consequence |
|---|---|---|
| **A — Compare episode plus reset/runtime generations** | Exact expected tuple `(expected_episode_generation, expected_reset_epoch, expected_runtime_generation)` in the compiler-owned binding equals receipt `(episode_generation, reset_epoch, runtime_generation)`; `ObservationCutoffV3.epoch == expected_reset_epoch`, `generation == expected_runtime_generation`; `lifecycle_identity` is an exact separate active-context identity, not derived from the message. | Stronger episode separation. Owner must define the trusted source and equality rule for the context identity because the receipt cannot prove it directly. |
| **B — Compare reset/runtime generations only** | Exact tuple `(expected_reset_epoch, expected_runtime_generation)` equals receipt `(reset_epoch, runtime_generation)`; cutoff `epoch`/`generation` equal those same expected values. `episode_generation` is not part of readiness comparison. `lifecycle_identity` remains separate active-context identity. | Simpler mapping, but receipt data from a different episode could be indistinguishable if reset/runtime generations are reused. This risk needs explicit Owner acceptance. |
| **C — Require additional message identity** | Add or change an interface member to carry the needed lifecycle identity/tuple. | Not available under the current decision to preserve receipt v2 bytes. Requires `AUTHORITY_CHANGE_REQUIRED`, new interface approval/hash, and separate change-control; do not implement under this packet. |

**Recommendation — `PROPOSAL_ONLY`:** choose A, include `episode_generation` in exact equality, map `epoch` to `reset_epoch` and `generation` to `runtime_generation`, and keep `lifecycle_identity` as separately sourced active-context identity. Before implementation, the Owner must still identify the authority that supplies that context identity and define how it is bound to the receipt publisher/source instance; this packet does not invent that association.

### Comparison and fail-closed choices

- **Exact comparison:** Option 1 is exact integer equality for selected tuple members plus exact string equality for active-context `lifecycle_identity`; Option 2 is equality of a compiler-issued opaque lifecycle token. Option 2 requires a token field/source contract and is not present in receipt v2; any such token must remain external to the message or require `AUTHORITY_CHANGE_REQUIRED`.
- **Requiredness:** selected tuple and lifecycle context are required, not optional. Missing components cannot be treated as wildcard or “not applicable.”
- **Missing tuple:** proposal is `INPUT_MISSING_NON_READY`, no vector. Owner must confirm this is the intended ACR8 mapping.
- **Ambiguous/unverifiable correspondence:** `AUTHORITY_CHANGE_REQUIRED`; stop before implementation, do not invent a status.
- **Tuple mismatch:** `LIFECYCLE_OR_CONTRACT_MISMATCH_NON_READY`; reject receipt, no fallback.
- **Invalidated generation:** `GENERATION_INVALIDATED_NON_READY`; reject prior-generation receipt.
- **Pre-barrier receipt:** `BARRIER_NOT_PASSED_NON_READY`; receipt must be strictly after both action and reset barriers.
- **Cutoff/barrier order invalid:** `CUTOFF_BARRIER_ORDER_NON_READY`; cutoff must be strictly later than each barrier.
- **Future stamp beyond cutoff:** `FUTURE_STAMP_CONTRACT_ERROR`; reject, no clock-domain reinterpretation.

The Owner must select whether a tuple is atomic (all fields compared together) and whether any transition permits reuse of an episode value. Recommendation is atomic exact equality with no partial match, reuse alias, or fallback (`PROPOSAL_ONLY`).

## 4. Decision C — Adapter/core data boundary

### Adapter checks before core ingress

The ROS adapter is the only layer that may receive the raw ROS message. Before constructing typed core inputs it must validate the selected exact receipt-interface ID/schema hash, message type/version, QoS contract ID/transport manifest, compatibility events, frame contract and planar-twist semantics, source/enum validity, publisher/source provenance, config hash binding, lifecycle tuple, timestamp domain, receipt ordering, and configured freshness/action-barrier eligibility.

The pure-Python core receives typed immutable values only. A raw ROS message, ROS-generated object, node, clock, file/repository handle, or middleware entity must never cross into or be imported by the core. The core must not perform I/O, read clocks, resolve paths/hashes, normalize frame names, or fabricate missing data. The Owner must choose whether adapter validation is represented as a validated typed receipt plus `ReceiptIngressBindingV3`, or as a typed ingress result carrying a status; the exact API remains open.

### Timing/freshness inputs

QoS6 defines action-bound readiness, strictly-after-barrier receipt timing, cutoff eligibility, detectable depth-1 coalescing, duplicate/non-monotonic rejection, and no global receipt-age timeout. The action-bound timeout belongs to the resolved input contract/profile and has no numeric value in the authority. Sensor freshness, skew, buffer capacities, receipt-after-barrier timeout and sensor/profile validity data remain `PENDING_MEASUREMENT` until evidence is approved.

Choices for the Owner:

1. Keep `ReceiptIngressBindingV3` limited to immutable contract/config/lifecycle pins and place timing inputs in a separate resolved observation-input record; or combine references and timing in one binding record. `PROPOSAL_ONLY` recommendation: keep them separate to preserve QoS6 ownership boundaries.
2. Confirm the adapter alone checks receipt/action/reset/cutoff stamps and the core consumes the resulting typed eligibility fact; or require the core to receive and evaluate typed timestamps. If the latter, define the exact clock-domain and error-carrier API without moving ROS/clock access into the core.
3. Select how a configured timeout is represented while unmeasured. Recommendation: keep it unavailable, reject real-profile compilation, and do not instantiate a real profile until measured/approved. No numeric value is proposed here.

## 5. Decision D — Compiler and resolved-record boundary

The active boundary decision requires a Gate B record owned and constructed solely by the `ResolvedConfigV3` compiler. Its exact public shape is unselected.

| Option | Candidate shape | Tradeoff |
|---|---|---|
| **A — Nested required record** | `ResolvedConfigV3` contains one required `gate_b: ResolvedGateBRecordV3`; compiler is the sole constructor. The record contains the chosen `ReceiptIngressBindingV3`, exact `ObservationInputContractV3`, selected profile identity, and fully resolved non-pending values. | Strong boundary and explicit ownership, but introduces named public record and exact field/API decisions. |
| **B — Extend existing resolved configuration directly** | Add required Gate B fields directly to `ResolvedConfigV3`, still compiler-created and validated as a single whole. | Fewer types, but broadens the existing public config model and risks mixing Gate B ingress data with unrelated config domains. |

Both options require keyword-only construction, all required fields, no implicit defaults, aliases, lookup, normalization, coercion, unresolved token, caller construction, or partial resolved record. The compiler must fail closed if any required binding or applicable measured profile value is absent. No implementation is authorized by these proposals.

### `config_hash` location choices

1. **Option A (`PROPOSAL_ONLY`):** one canonical source at `ResolvedConfigV3.provenance.config_hash`; `ReceiptIngressBindingV3` references/duplicates the exact value and compiler validation requires equality. This is explicit but duplicates a value.
2. **Option B (`PROPOSAL_ONLY`):** keep `config_hash` only in `ResolvedConfigV3.provenance`; the compiler-owned Gate B record is inseparably contained in that resolved config and is bound by that one hash, with no duplicate field. This avoids two copies but needs precise definition of what bytes/fields the hash covers.

Recommendation (`PROPOSAL_ONLY`): Option B, if the current canonical config-hash algorithm can demonstrably cover the Gate B binding without circularity. Otherwise, return to the Owner with the exact non-circular hash projection before implementation; never self-hash or silently exclude fields.

### Unresolved values and real profiles

No unresolved token/default/alias/coercion is permitted in a real resolved Gate B profile. Timing/profile values that still require measurement remain `PENDING_MEASUREMENT`; the compiler rejects the real-profile resolution while any such required value is pending. In-memory test fixtures cannot be presented as measurement, profile evidence, or runtime readiness.

## 6. Questions for Project Owner/User

Every answer is a decision for a later record; this packet records none as approved.

| Decision | Options to choose | Recommendation (`PROPOSAL_ONLY`) | Authority impact | Owner response requested |
|---|---|---|---|---|
| Binding member shape | §2 Option A flat / Option B nested / exact alternative | A for explicit pins, unless nested `ContractReferenceV3` reuse is preferred | Defines new public contract; must be pinned in approved spec before implementation | Select one and specify exact member list |
| Exact types and validation | Exact built-in `str`/`int` strict / approved strict model types / exact alternative | Exact built-ins, no coercion; equality against pins, not lookup | New type/validation contract | Confirm types, ranges, hash syntax rule, requiredness |
| Immutability/value behavior | frozen+slots+keyword-only / other exact immutable model; field equality/hash; repr; serialization none or exact API | frozen+slots+keyword-only; field-wise equality/hash; default repr; no serialization/export API | Defines observable public data API | Select representation and equality/hash/repr/serialization rules |
| Spec self-pin | revision-only / external final-document SHA / another non-circular reference | revision-only inside record; full SHA externally pinned after final bytes | Avoids self-reference; may require Registry/approval-record update | Select exact non-circular pin method |
| Lifecycle tuple | §3 Option A include episode / Option B omit episode / formal interface change | A, with separate trusted lifecycle identity source | Changes receipt eligibility semantics; interface change requires authority change | Select tuple members, mapping, source and equality rule |
| Missing/ambiguous lifecycle data | Missing → `INPUT_MISSING_NON_READY`; ambiguous → `AUTHORITY_CHANGE_REQUIRED`; exact alternative | Fail closed as shown | Existing ACR8 status usage; no new status | Confirm mapping and atomicity/no-reuse rule |
| Adapter/core seam | Adapter validates and passes typed eligibility / core validates typed timestamps / exact alternative | Adapter owns ROS/frame/QoS/freshness; core consumes typed facts | Sets package ownership and test boundary | Select seam and exact typed output/error carrier |
| Binding vs timing records | Separate reference/config binding and timing input / one combined record | Separate records | Preserves QoS6 responsibility boundaries | Select exact ownership/record composition |
| Config hash | Duplicate into binding and equality-check / only `ResolvedConfigV3.provenance.config_hash` / exact alternative | Single provenance source if hash coverage is proven | May require config hash projection/change-control | Select location and exact covered bytes/fields |
| Profile/timing requirements | Reject real resolution while pending / other measured evidence process | Reject until measured/approved | No numeric profile value is selected; measurement remains separate evidence | Confirm evidence owner/source and when a profile is eligible |
| Raw ROS object policy | Prohibit in pure core / exact alternative | Prohibit | Preserves pure-core/adapter boundary | Confirm absolute boundary and adapter-to-core value shape |

## 7. Acceptance criteria for a later exact-contract implementation packet

Before implementation authorization is considered, a consolidated decision record must resolve every row above and a controlled authority update must pin the exact final data model. A later exact-scope packet should require:

- static checks that every public member, exact type, requiredness, and constructor rule matches the approved spec;
- pure-Python tests for all required/missing/unknown/wrong-type/bool-as-int cases, exact pin/hash/config mismatches, tuple equality/missing/ambiguous/mismatch/invalidated behavior, barrier/cutoff ordering, and fail-closed status propagation;
- compiler tests proving it is the only construction path, binds `ResolvedConfigV3` and config hash without circularity, and rejects unresolved tokens/defaults/profile values;
- equality/hash/immutability tests only to the extent expressly selected by the Owner;
- import-purity tests proving no raw ROS type or ROS/runtime import, I/O, clock, repository lookup, or message construction in pure core;
- an adapter contract test plan for ROS type, QoS, frame, freshness, source/provenance, ordering, and exact pin validation, without running ROS in a documentation-only work package;
- test vectors for the fixed 81D layout and proof that no Ground Truth or raw ROS message enters core;
- independent audit of exact allowlist, authority pins, no fallback/alias, status matrix, and Gate B boundary.

ROSIDL generation, adapter/QoS integration, runtime and HIL remain separate authorization/evidence stages. These criteria do not authorize or claim any of them.

```text
WP-04: BLOCKED_BY_CONTRACT
GATE_A_STRUCTURAL_PRIMITIVES: PASSED
GATE_B: NOT_STARTED
GATE_B_BOUNDARY_CLOSURE: ACTIVE_ON_INTEGRATION
CODE_AUTHORIZATION: NOT_GRANTED
RUNTIME_APPROVED: NOT_APPROVED
WP-05: OPEN
```
