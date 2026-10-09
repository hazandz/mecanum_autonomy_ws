# WP-04 Gate A — exact structural schema decision packet

**Status:** DRAFT_FOR_PROJECT_OWNER_USER_DECISION_AND_FOCUSED_INDEPENDENT_AUDIT
**Work package:** WP-04-POLICY-CORE-P0
**Base:** origin/integration/implementation at c37a5bff9dd6cc32fc503cdd796b31720a58a616
**Source packet 1:** branch wp-04-gate-a-structural-authority-resolution-c37a5bff, commit def2f1cee05119ea1b8877824c9f95884621fbe6, SHA-256 5d95f9cc3890b16e3bed1094e36fede3d0d0da375b37b5ac4b3cde56779d835e.
**Source packet 2:** branch wp-04-gate-a-structural-decision-resolution-c37a5bff, commit 3b3f2de7870ce7c935ca1f12a98b1c3c416a8649, SHA-256 2a4579622802ed000cf8e0553f3c5d414dc4eec14659b547f8edfd95303b776b.

## 1. Purpose and decision state

This packet turns the recorded high-level user choices into concrete schema options for a Project Owner/User decision. It is not a contract amendment, implementation packet approval, CODE_AUTHORIZATION, Gate A pass, WP-04 closure, or runtime approval.

Previously recorded directions:

1. ObservationCutoffV3: Option B, minimum facts grounded in currently approved authority; do not import extra S2/OIC draft fields.
2. ObservationInputContractV3: Option A, immutable reference-only container; no nested OIC models.
3. Strict immutable models, keyword-only construction, no coercion or implicit defaults; missing, unknown and wrong-typed inputs fail closed.
4. Preserve ACR8 canonical status names and fail-closed semantics; no fallback or weakened non-ready result.
5. QoS6/ACR8/Registry are current authority; S2 rev.2, OIC rev.6 and V3 Boundary Specification rev.7 remain provenance-only.

Those decisions do not select exact field spelling, Python time representation, integer bounds, reference member set, equality/hash/serialization behavior, or a complete error mapping. Those choices are presented below. Nothing labeled candidate is adopted unless the Owner/User selects it and the choice is recorded through governance.

## 2. Authority and provenance

### Current authority at the exact baseline

| Authority | Exact path and identity | Relevance |
|---|---|---|
| Architecture | docs/MECANUM_NAV_DRL_Architecture.docx; SHA-256 f0fb1ebede5f4fa18604610c04bb13587d456173b4fd942dba77e44d49777860 | Highest authority; does not specify these Python schemas. |
| PEP-001 rev.0.5.0 | docs/governance/PROJECT_EXECUTION_PLAN.md; SHA-256 ffcf5cbbbd25d174ff2ed97dd7fe4297ccefe5eaaf0f95d00b69aba1a820807b | Allows immutable cutoff type/validation, immutable structural input models and exact S2/final-issued-receipt ID/SHA structural references. Controls sequence, not schema detail or code authorization. |
| ACR8 | docs/ACR_V3_OBSERVATION_BOUNDARY_CLOSURE.md; SHA-256 03fef021f6b9731f811f83a5e53aae1c430bdc2ea76815a8ada416f1a5bf772c | Current approved Gate A/B ACR. Cutoff strictly after both barriers; same lifecycle identity, epoch, generation and profile ROS-time domain; SafetyLifecycle owns barriers; RobotRuntimeAdapter.wait_transition_snapshot(after=receipt) operationally creates cutoff; typed fail-closed semantics; config_hash if carried is opaque caller-supplied provenance. |
| QoS6 | docs/RECEIPT_TOPIC_QOS_CONTRACT.md; full-document SHA-256 4200cd2fbdc81a19400f168dd3526eb7871ac2251049fc7c4f5d5c2fddfd2022; transport ID mecanum.final-issued-receipt-topic-qos/v2; manifest SHA-256 338bea1b7350d3b82146c7e728516ec7947471ee68db0f8871ddb72071b79620 | Canonical transport contract/manifest identity; does not prescribe Python model API. |
| Bundle approval | docs/governance/decisions/QOS_REVISION_6_ACR_REVISION_8_BUNDLE_APPROVAL.md; SHA-256 4d740559f850f179387db802df845748068f75a21266fd1edb52402b2c72c529 | Approval provenance; no code authority. |
| Canonical Source Registry | docs/governance/CANONICAL_SOURCE_REGISTRY.md; SHA-256 75d63ea7500f1a0c442100bb3d9dd9291ed27358e6061e5ac1fcc25ac0afe879 | Selects ACR8/QoS6 and receipt v2 schema, dependency closure and transport manifest. |

### Provenance-only inputs

PEP pins but does not approve, canonicalize, promote or treat these as independently satisfying a gate. They do not grant implementation authorization.

| Source | Provenance and exact hashes |
|---|---|
| S2 rev.2 | origin/docs-v3-observation-contract-import@d3ca85536e35b38f7f3dffcf1dfd1bc16983aae9; docs/architecture/proposals/v3-observation-contracts/ACR_S2_SNAPSHOT_SYNCHRONIZATION_TEMPORAL_CONTRACT.md; full-document SHA-256 e1468d0373922a1806e14da91e7cc0336bcc7d70c4cd3ec4fc749078d86b70ab; embedded ID mecanum.snapshot-synchronization-temporal/v1 and contract/manifest SHA-256 1be31c1915fedd86f269cee5214d794da0899a0d69dbb0ba5392e619813d4a8f; DRAFT. |
| OIC rev.6 | Same branch/commit; docs/architecture/proposals/v3-observation-contracts/OBSERVATION_INPUT_CONTRACT_V3_DESIGN.md; full-document SHA-256 200703949d6b326a30ee8e2f75cd2cd14054576e6772ddc6ae3ff670e48eb76c; REVISED_DRAFT. |
| V3 Boundary Specification rev.7 | Same branch/commit; docs/architecture/proposals/v3-observation-contracts/V3_OBSERVATION_BOUNDARY_SPECIFICATION.md; full-document SHA-256 47ba6c432cc53798e9f8a97f3c0a97aae586d24bef98113716a4493e57ad4eeb; supporting provenance. |

The S2 embedded contract/manifest hash differs from its full-document hash. Draft field names/types below are identified as provenance only, not adopted defaults.

## 3. ObservationCutoffV3 exact field decision

### 3.1 Semantic facts required by approved authority

The value must permit structural validation of: a cutoff and both action/reset barriers; a common lifecycle identity, epoch/reset epoch, generation/runtime generation and profile ROS-time domain; and strict ordering with cutoff later than each barrier. SafetyLifecycle remains sole barrier owner. RobotRuntimeAdapter.wait_transition_snapshot(after=receipt) remains sole operational cutoff creator. Core only receives/validates facts; it cannot read a clock, create/advance barriers, create a cutoff, convert time or synthesize identity.

### 3.2 Concrete schema candidate, offered for decision only

    ObservationCutoffV3(
        *,
        lifecycle_identity: LifecycleIdentity,
        epoch: EpochValue,
        generation: GenerationValue,
        time_domain: ProfileRosTimeDomain,
        cutoff_time: RosTimeValue,
        action_barrier_time: RosTimeValue,
        reset_barrier_time: RosTimeValue,
    )

| Required field | Meaning | Candidate Python type/range | Authority and decision |
|---|---|---|---|
| lifecycle_identity | Identity shared by cutoff and both barriers | Candidate: non-empty str; exact comparison, no normalization | ACR requires sameness, not field/type/encoding. Choose this, another representation, or PENDING_USER_DECISION. |
| epoch | Active epoch associated with time facts | Candidate: exact built-in int, bool rejected, minimum 0, no upper bound | ACR requires matching epoch/reset epoch; no type or maximum is approved. Decide if epoch/reset_epoch are one fact or distinct. |
| generation | Active generation associated with time facts | Candidate: exact built-in int, bool rejected, minimum 0, no upper bound | ACR requires matching generation/runtime generation; no Python representation or bound is approved. |
| time_domain | Common active profile ROS-time domain identity | Candidate: non-empty opaque str; exact comparison | ACR requires common domain but does not define ID or encoding. No profile resolution or clock access. |
| cutoff_time | Caller-supplied transition cutoff | Candidate: RosTimeValue; required | ACR specifies ownership/order, not Python timestamp representation or unit. |
| action_barrier_time | Immutable action barrier supplied by SafetyLifecycle | Candidate: RosTimeValue; required | Owner/order are approved; representation is not. |
| reset_barrier_time | Immutable reset barrier supplied by SafetyLifecycle | Candidate: RosTimeValue; required | Owner/order are approved; representation is not. |

Nested candidate:

    RosTimeValue(*, domain: ProfileRosTimeDomain, value: TimeTicks)
    ProfileRosTimeDomain = non-empty opaque str
    TimeTicks = exact built-in int, bool rejected, minimum 0, no upper bound

The nested form repeats domain identity in each time value. Alternative: one top-level time_domain plus three scalar timestamps. The unit/resolution of TimeTicks is PENDING_USER_DECISION. “Nanoseconds” occurs in S2/OIC draft names only and is not adopted here.

### 3.3 Field-set options

- **Option A — Flat facts:** the seven required facts above; choose shared top-level domain plus scalar timestamps, or nested RosTimeValue values.
- **Option B — Nested values:** same facts grouped into immutable lifecycle identity and shared-domain time values. Exact types/member names remain for decision.
- **Option C — Caller context:** cutoff value carries the three times only; separate immutable context supplies identity/epoch/generation/domain. The exact context and proof that validation still establishes ACR8 matching must be approved.

Do not include transaction_id, creation_owner text, schema_id or config_hash solely because a draft proposes them. If any is requested, cite current approved authority or mark PENDING_USER_DECISION. If config_hash is carried, it remains opaque caller-supplied provenance and is never computed, verified, resolved, defaulted, bound or made a config field.

### 3.4 Fixed ordering

    cutoff_time > action_barrier_time
    cutoff_time > reset_barrier_time
    lifecycle_identity, epoch, generation and profile ROS-time domain match

Equality fails closed. No tolerance, clock conversion, receipt wait or runtime clock access is included. Whether the barriers must be ordered relative to each other is not specified by the cited approved rule and remains PENDING_USER_DECISION.

## 4. Reference-only ObservationInputContractV3

### 4.1 Exact reference value candidate

    ContractReferenceV3(*, contract_id: str, contract_sha256: str)

Both fields required. Candidate matching is exact string equality to a selected ID/SHA pair: no case folding, aliases, fallback, substitution, normalization, hashing or filesystem lookup. Whether additional generic ID/hex syntax validation is required is PENDING_USER_DECISION. Artifact path is provenance metadata, not automatically a model field.

### 4.2 Member-set options

PEP requires exact S2 and final-issued-receipt ID/SHA structural references. S2 is still provenance-only, so its member—if selected—must be labeled as a provenance reference, not authority.

**Option A — PEP-minimum structural member set**

    ObservationInputContractV3(
        *,
        s2_provenance_reference: ContractReferenceV3,
        receipt_interface_reference: ContractReferenceV3,
    )

**Option B — additionally carry canonical QoS transport pin**

    ObservationInputContractV3(
        *,
        s2_provenance_reference: ContractReferenceV3,
        receipt_interface_reference: ContractReferenceV3,
        receipt_qos_transport_reference: ContractReferenceV3,
    )

**Option C — governance references**

Decide whether ACR8, QoS6, approval-record or Registry IDs/hashes belong as structural members, rather than as authority/provenance outside this value. Current PEP/contracts do not state that governance-document hashes must be runtime-independent model members; inclusion is PENDING_USER_DECISION.

### 4.3 Exact reference inventory

| Candidate reference member | ID and hash pair | Canonical/provenance path and document hash | Important distinction |
|---|---|---|---|
| s2_provenance_reference | mecanum.snapshot-synchronization-temporal/v1; embedded contract/manifest SHA-256 1be31c1915fedd86f269cee5214d794da0899a0d69dbb0ba5392e619813d4a8f | PEP provenance path docs/architecture/proposals/v3-observation-contracts/ACR_S2_SNAPSHOT_SYNCHRONIZATION_TEMPORAL_CONTRACT.md at origin/docs-v3-observation-contract-import@d3ca85536e35b38f7f3dffcf1dfd1bc16983aae9; full-document SHA-256 e1468d0373922a1806e14da91e7cc0336bcc7d70c4cd3ec4fc749078d86b70ab | Provenance only, not canonical authority. Embedded hash and document hash differ. |
| receipt_interface_reference | mecanum.final-issued-receipt/v2; schema SHA-256 0c6446674bf17373ec646519043f506a9a7a15f95d5fdd10829b0cedb956500a | Canonical path ros2_ws/src/mecanum_nav_rl_interfaces/msg/FinalIssuedCommandReceipt.msg | Hash identifies schema only. No ROS/ROSIDL generation or runtime integration. |
| receipt_qos_transport_reference | mecanum.final-issued-receipt-topic-qos/v2; transport-manifest SHA-256 338bea1b7350d3b82146c7e728516ec7947471ee68db0f8871ddb72071b79620 | Canonical manifest docs/RECEIPT_TOPIC_QOS_TRANSPORT_MANIFEST.json; governing QoS document docs/RECEIPT_TOPIC_QOS_CONTRACT.md, full-document SHA-256 4200cd2fbdc81a19400f168dd3526eb7871ac2251049fc7c4f5d5c2fddfd2022 | Manifest hash is not full QoS document or receipt-schema hash. Member inclusion is a decision. |
| governance documents | ACR8 SHA-256 03fef021f6b9731f811f83a5e53aae1c430bdc2ea76815a8ada416f1a5bf772c; QoS6 SHA-256 4200cd2fbdc81a19400f168dd3526eb7871ac2251049fc7c4f5d5c2fddfd2022; approval SHA-256 4d740559f850f179387db802df845748068f75a21266fd1edb52402b2c72c529; Registry SHA-256 75d63ea7500f1a0c442100bb3d9dd9291ed27358e6061e5ac1fcc25ac0afe879 | Canonical paths listed in §2 | Authority inputs, not automatically model members; inclusion is PENDING_USER_DECISION. |

ACR8 §5.2 retains proposal-era wording for receipt v2 pins, while current Registry/approval select receipt v2 as canonical. This packet preserves both and flags the wording for focused audit; it does not amend or silently reinterpret them.

## 5. API and value semantics

Already selected at policy level: strict immutable models, keyword-only constructors, no coercion or implicit defaults; missing, unknown and wrong-typed input fails closed.

Candidate declaration style, not adopted:

    @dataclass(frozen=True, slots=True, kw_only=True)
    class ObservationCutoffV3: ...

    @dataclass(frozen=True, slots=True, kw_only=True)
    class ContractReferenceV3: ...

    @dataclass(frozen=True, slots=True, kw_only=True)
    class ObservationInputContractV3: ...

Still PENDING_USER_DECISION:

| Concern | Options | Effect |
|---|---|---|
| Representation | Frozen/slotted keyword-only dataclass; frozen keyword-only dataclass without slots; custom immutable class | Exact signature, introspection and subclass rules. |
| Equality | Field-wise value equality; identity-only equality | Comparison semantics and tests. |
| Hash | Generated hash for immutable members; explicitly unhashable | Nested fields must be immutable/hashable if value hashing is selected. No content hash is calculated. |
| repr | Default field repr; compact/redacted repr | Decide whether opaque IDs/hashes are shown in repr. |
| Serialization | No supported serialization API; separately specified structural export | No config/YAML/ROS serialization is implied. |
| Subclasses | Reject subclasses; accept compatible immutable subclasses | Authority does not select. Decide exact-type versus isinstance policy. |
| bool-as-int and numeric subclasses | Reject bool and non-exact integer types; or accept selected integral subclasses while still rejecting bool | Exact boundary behavior remains to choose; no coercion. |

No config loader, profile resolver, ROS message, adapter or runtime API is proposed.

## 6. Structural validation/error matrix

Carrier options: typed validation result/status, or typed exception carrying an existing canonical status where semantics match. Choose one API; no new canonical status may be invented. If ACR8 has no semantically matching status, the mapping is PENDING_USER_DECISION.

| Structural failure | Approved relation | Existing status candidate | Required disposition |
|---|---|---|---|
| Cutoff equals or precedes action barrier | ACR8 explicitly requires strictly later | CUTOFF_BARRIER_ORDER_NON_READY | Authority-backed mapping; choose result or exception carrier. |
| Cutoff equals or precedes reset barrier | Same approved strict-order rule | CUTOFF_BARRIER_ORDER_NON_READY | Authority-backed mapping; choose carrier. |
| Lifecycle identity, epoch, generation or time-domain mismatch | ACR8 requires these facts to match | LIFECYCLE_OR_CONTRACT_MISMATCH_NON_READY | Candidate mapping; confirm all such structural mismatches share it. |
| Missing required field/reference | Fail-closed policy selected; ACR8 uses INPUT_MISSING_NON_READY for missing input, not specifically constructor omission | INPUT_MISSING_NON_READY only if equivalence is approved; otherwise PENDING_USER_DECISION | Do not silently equate malformed structure with runtime input absence. |
| Unknown field | Strict rejection selected; no dedicated ACR8 status | PENDING_USER_DECISION | Choose typed carrier/disposition; do not add status. |
| Wrong type, including bool-as-int | Strict rejection selected; no dedicated ACR8 status | PENDING_USER_DECISION | Choose status mapping or typed construction error. |
| Below/above range | Bounds not selected; no direct ACR8 status | PENDING_USER_DECISION | Decide bounds first, then mapping. Do not infer uint width. |
| Malformed ID/SHA syntax | Generic syntax rules not selected | PENDING_USER_DECISION | Decide syntax validation; exact pair comparison remains mandatory. |
| ID paired with wrong SHA, or SHA with wrong ID | Exact contract mismatch must fail closed | LIFECYCLE_OR_CONTRACT_MISMATCH_NON_READY is a candidate | Confirm applicability; no alias/fallback. |
| Time domain not comparable | ACR requires same profile domain but does not define representation | PENDING_USER_DECISION | Resolve representation; no clock conversion/external lookup. |
| Missing/malformed config_hash, if selected as a field | ACR says opaque provenance if carried; does not require Gate A field | PENDING_USER_DECISION | Decide field presence first; never compute or verify against config. |
| Missing/duplicate transaction identity, if selected | Approved sources specify one operational cutoff creation, not ID schema/uniqueness API | PENDING_USER_DECISION | No S2 draft uniqueness rule without separate decision. |
| Future-input, freshness, sync, buffer or generation-invalidation condition | Connected S2/runtime behavior, outside structural Gate A | ACR8 has corresponding statuses | Not implemented or tested by Gate A. |

Preserve the full ACR8 vocabulary unchanged: INPUT_MISSING_NON_READY; LIFECYCLE_OR_CONTRACT_MISMATCH_NON_READY; BARRIER_NOT_PASSED_NON_READY; CUTOFF_BARRIER_ORDER_NON_READY; FUTURE_STAMP_CONTRACT_ERROR; INPUT_STALE_NON_READY; SENSOR_SYNC_MISS_NON_READY; REFERENCE_SYNC_MISS_NON_READY; ORDERING_CONTRACT_AMBIGUITY_NON_READY; BUFFER_OVERFLOW_NON_READY; GENERATION_INVALIDATED_NON_READY. Listing a status does not authorize the connected behavior it names.

## 7. Decisions the Owner/User still needs to make

1. Select cutoff field-set option A, B or C in §3.3.
2. For each selected field: exact name; direct/nested representation; Python type; requiredness; bounds; bool/subclass policy; and timestamp unit/resolution.
3. Decide whether lifecycle identity and profile ROS-time domain are explicit fields, and their exact opaque representations.
4. Decide whether transaction identity, creation-owner text, schema ID or config_hash are absent or carried; any inclusion must be grounded in current approved authority or separately approved.
5. Select ObservationInputContract member option A/B or a written alternative, including whether governance document hashes are outside the value or additional members.
6. Select exact member names/nesting for ContractReferenceV3, and exact pair-only versus additional syntax validation.
7. Select representation style, nested immutability, equality, hashability, repr and serialization policy.
8. Select typed-result versus typed-exception API and complete status mapping. For no matching ACR8 status, explicitly decide a typed fail-closed disposition without creating a canonical status.
9. Decide whether action/reset barriers must be ordered relative to each other; the cited ACR rule only orders cutoff after each one.

Unselected items remain PENDING_USER_DECISION. They may not be inferred from S2/OIC/V3 Spec drafts or existing code conventions.

## 8. Scope and status

This packet is limited to a structural Gate A schema decision. It does not authorize config/compiler/profile work; ROS/ROSIDL/QoS/TF/DDS; adapters; runtime clocks; freshness/synchronization; receipt bridge/history; S2 synchronizer/buffers; assembler/encoder or 81D construction; V1 observation/decoder/snapshot use; Ground Truth; HIL; hardware; deploy_sim; or deploy_real. WP-05 is untouched.

    SCHEMA_PACKET: DRAFT_FOR_FOCUSED_INDEPENDENT_AUDIT
    USER_DECISIONS: HIGH_LEVEL_DIRECTIONS_RECORDED; EXACT_SCHEMA_PENDING
    WP-04: BLOCKED_BY_CONTRACT
    GATE_A: NOT_PASSED
    CODE_AUTHORIZATION: NOT_GRANTED
    RUNTIME_APPROVED: NOT_APPROVED

This candidate does not amend PEP-001, Registry, Ledger, QoS6, ACR8 or any canonical contract. It does not declare Gate A passed, WP-04 closed, or implementation authorized.
