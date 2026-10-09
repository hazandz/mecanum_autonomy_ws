# WP-04 Gate A — structural decision resolution proposal

**Status:** DRAFT_FOR_FOCUSED_INDEPENDENT_AUDIT
**Decision provenance:** Project Owner/User choices supplied for WORK_PACKAGE_ID WP-04-GATE-A-STRUCTURAL-DECISION-RESOLUTION. This proposal records those choices for audit; it is not a code-authorization decision.
**Work package:** WP-04-POLICY-CORE-P0
**Candidate base:** origin/integration/implementation at c37a5bff9dd6cc32fc503cdd796b31720a58a616
**Source packet:** wp-04-gate-a-structural-authority-resolution-c37a5bff at def2f1cee05119ea1b8877824c9f95884621fbe6; docs/WP-04_GATE_A_STRUCTURAL_AUTHORITY_DECISION_PACKET_DRAFT.md; SHA-256 5d95f9cc3890b16e3bed1094e36fede3d0d0da375b37b5ac4b3cde56779d835e. The source packet was supplied as audited; this proposal does not replace or extend that audit.

## 1. Decision recorded

The Project Owner/User has selected the following structural directions for possible Gate A work:

1. **ObservationCutoffV3 field-set direction — Option B.** Use only the minimum facts required by currently applicable approved authority. Do not import extra fields or semantics from S2/OIC draft provenance.
2. **ObservationInputContractV3 shape — Option A.** Use an immutable reference-only container. Do not include nested OIC models in Gate A.
3. **Validation/type policy.** Models are strict and immutable; constructors are keyword-only; no coercion or implicit defaults. Missing fields, unknown fields and wrong types fail closed.
4. **Error policy.** Preserve the canonical ACR8 status vocabulary and fail-closed/non-ready semantics. Do not add fallback or weaken a failure condition.
5. **Exact references.** Use the canonical QoS6/ACR8/Registry references selected at the baseline. S2 rev.2, OIC rev.6 and V3 Boundary Specification rev.7 remain provenance only and are not promoted to authority.
6. **Authorization boundary.** No CODE_AUTHORIZATION, runtime, ROS, HIL, hardware or deployment authorization is granted.

These are recorded user decisions about direction and boundaries. They do not supply every Python field name/type, reference-container member spelling, constructor signature detail, or error-to-status mapping. Those unresolved details remain explicitly PENDING below and must not be guessed or coded. This proposal itself is pending focused independent audit and does not activate a new contract or PEP rule.

## 2. Authority and provenance

### Current canonical authority at the exact base

- Architecture: docs/MECANUM_NAV_DRL_Architecture.docx, SHA-256 f0fb1ebede5f4fa18604610c04bb13587d456173b4fd942dba77e44d49777860.
- PEP-001 rev.0.5.0: docs/governance/PROJECT_EXECUTION_PLAN.md, SHA-256 ffcf5cbbbd25d174ff2ed97dd7fe4297ccefe5eaaf0f95d00b69aba1a820807b. It controls sequencing and allows preparation of the constrained primitive packet; it does not grant source-edit authority.
- ACR revision 8: docs/ACR_V3_OBSERVATION_BOUNDARY_CLOSURE.md, SHA-256 03fef021f6b9731f811f83a5e53aae1c430bdc2ea76815a8ada416f1a5bf772c. The Registry selects this as the active approved ACR for Gate A/Gate B scope.
- QoS revision 6: docs/RECEIPT_TOPIC_QOS_CONTRACT.md, SHA-256 4200cd2fbdc81a19400f168dd3526eb7871ac2251049fc7c4f5d5c2fddfd2022; transport ID mecanum.final-issued-receipt-topic-qos/v2; manifest SHA-256 338bea1b7350d3b82146c7e728516ec7947471ee68db0f8871ddb72071b79620.
- QoS6/ACR8 approval record: docs/governance/decisions/QOS_REVISION_6_ACR_REVISION_8_BUNDLE_APPROVAL.md, SHA-256 4d740559f850f179387db802df845748068f75a21266fd1edb52402b2c72c529.
- Canonical Source Registry: docs/governance/CANONICAL_SOURCE_REGISTRY.md, SHA-256 75d63ea7500f1a0c442100bb3d9dd9291ed27358e6061e5ac1fcc25ac0afe879.
- Gate A PEP change-control record: docs/governance/decisions/WP-04_GATE_A_SEMANTIC_BUNDLE_PEP_CHANGE_CONTROL.md, SHA-256 4876a0ad5afbe355ce5f410b9e5dbb2ef669455deedf2e2b2c9ca864c7425bb2.

### Provenance-only inputs

PEP pins, but does not approve, canonicalize, promote or treat as independently gate-satisfying:

- S2 rev.2 at origin/docs-v3-observation-contract-import@d3ca85536e35b38f7f3dffcf1dfd1bc16983aae9, docs/architecture/proposals/v3-observation-contracts/ACR_S2_SNAPSHOT_SYNCHRONIZATION_TEMPORAL_CONTRACT.md, full-document SHA-256 e1468d0373922a1806e14da91e7cc0336bcc7d70c4cd3ec4fc749078d86b70ab; embedded contract ID mecanum.snapshot-synchronization-temporal/v1 and contract/manifest SHA-256 1be31c1915fedd86f269cee5214d794da0899a0d69dbb0ba5392e619813d4a8f. Its source label is DRAFT.
- OIC rev.6 at the same branch/commit, docs/architecture/proposals/v3-observation-contracts/OBSERVATION_INPUT_CONTRACT_V3_DESIGN.md, full-document SHA-256 200703949d6b326a30ee8e2f75cd2cd14054576e6772ddc6ae3ff670e48eb76c. Its source label is REVISED_DRAFT.
- V3 Boundary Specification rev.7 at the same branch/commit, docs/architecture/proposals/v3-observation-contracts/V3_OBSERVATION_BOUNDARY_SPECIFICATION.md, full-document SHA-256 47ba6c432cc53798e9f8a97f3c0a97aae586d24bef98113716a4493e57ad4eeb. It is supporting design provenance and does not replace ACR8.

The chosen minimal-field direction is based on approved ACR8/PEP invariants, not on adopting those draft schemas. A field that happens to appear in a pinned draft does not become approved because its bytes are pinned.

## 3. Resolved structural direction and remaining PENDING details

### 3.1 ObservationCutoffV3

**Resolved direction:** Option B. A later Gate A implementation may represent only the minimum caller-supplied facts needed to validate ACR8’s approved invariants: cutoff; both action/reset barriers; matching lifecycle identity, epoch/reset epoch, generation/runtime generation; and the common active profile ROS-time domain. The primitive must not create, revise, infer, round, translate or replace operational facts. SafetyLifecycle remains sole owner of the two barriers, and RobotRuntimeAdapter.wait_transition_snapshot(after=receipt) remains the sole operational creator of one cutoff per transition.

**Still PENDING; do not infer or code yet:**

- Exact field names, which facts are direct fields versus nested immutable values, and the minimality rule if caller context supplies identity/domain outside the value.
- Python type and range for every identifier, epoch/generation and time value; bool/subclass treatment and whether integer coercion is rejected.
- How lifecycle identity and profile ROS-time domain are represented and compared.
- Whether config_hash is included as a carried opaque provenance value at all. If present, it is caller-supplied only; the primitive must not create, calculate, verify, resolve, default, bind, or turn it into a configuration field.
- Whether schema identity is part of this minimal cutoff value. The 81D observation schema is not implied by Gate A.
- Whether transaction identity or creation-owner text is represented as data. The direction excludes importing those fields solely because S2/OIC drafts propose them; any requirement must be grounded in current approved authority.
- Exact value-object implementation/API details not dictated by the accepted policy, including public class/module API, validation entry point, equality/hash/repr/serialization behavior.

The S2/OIC draft proposal transaction_id, creation_owner, schema_id and its exact proposed field list remain provenance only. Option B does not silently adopt them.

### 3.2 ObservationInputContractV3

**Resolved direction:** Option A. Gate A’s container is immutable and reference-only. It has no nested lidar, goal, measured-twist, timing, profile, topic-selector, transform, provenance-union or receipt-bridge model.

**Still PENDING; do not infer or code yet:**

- Exact member names and nesting for the reference-only container.
- Which exact references are carried as structural values versus documented pins/constants. PEP requires exact S2 and final-issued-receipt ID/SHA structural references; the canonical Registry/approval also select QoS6/ACR8 and receipt v2 interface/transport artifacts. The focused audit/decision record must settle the exact reference set without promoting S2/OIC drafts.
- Exact Python ID/SHA value types, allowed syntax/casing, validation API, and how a mismatched ID/hash pair fails.
- Whether references are caller-supplied immutable values, constants, or a combination; no defaults, aliases, substitutions or fallback are permitted.
- Whether an empty reference-only container can exist before exact required members are supplied. Under the approved user policy, missing/unknown/wrongly typed values fail closed; no implicit default may make a partial value valid.
- Equality, hashing and serialization behavior beyond the strict immutable requirement.

No OIC rev.6 nested model or field is adopted by this decision.

### 3.3 Shared strictness and error policy

**Resolved direction:** immutable strict models, keyword-only constructors, no coercion, no implicit defaults. Missing fields, unknown fields and wrong types fail closed. Validation may not weaken a canonical non-ready condition or fall back to another value/path.

**Still PENDING:** the exact API surface and mapping from each structural invalidity to a typed failure carrying the ACR8 canonical status vocabulary. ACR8’s relevant names include LIFECYCLE_OR_CONTRACT_MISMATCH_NON_READY and CUTOFF_BARRIER_ORDER_NON_READY; its full canonical vocabulary also includes INPUT_MISSING_NON_READY, BARRIER_NOT_PASSED_NON_READY, FUTURE_STAMP_CONTRACT_ERROR, INPUT_STALE_NON_READY, SENSOR_SYNC_MISS_NON_READY, REFERENCE_SYNC_MISS_NON_READY, ORDERING_CONTRACT_AMBIGUITY_NON_READY, BUFFER_OVERFLOW_NON_READY and GENERATION_INVALIDATED_NON_READY. This list preserves names; it does not mean Gate A implements synchronization, freshness, future-stamp, buffer or runtime behavior.

The exact mapping for missing field, unknown field, wrong type, invalid range, malformed ID/SHA, pair mismatch, lifecycle mismatch, time-domain mismatch, and barrier ordering remains PENDING. Do not add a new canonical status, conflate programmer-invalid construction with runtime non-readiness, or choose exception versus result carrier without the exact reviewed implementation packet/decision. Whatever carrier is later selected must preserve fail-closed semantics and canonical status spellings where applicable.

## 4. Exact reference inventory for focused audit

The decision directs use of canonical QoS6/ACR8/Registry references at this baseline. The following inventory distinguishes source identity from authority and requires the focused audit to verify the exact structural member set:

| Reference | Exact identity/path | Status for this packet |
|---|---|---|
| ACR authority | ACR8; docs/ACR_V3_OBSERVATION_BOUNDARY_CLOSURE.md; SHA-256 03fef021f6b9731f811f83a5e53aae1c430bdc2ea76815a8ada416f1a5bf772c | Current approved Gate A/Gate B ACR authority. |
| QoS authority | QoS6; docs/RECEIPT_TOPIC_QOS_CONTRACT.md; SHA-256 4200cd2fbdc81a19400f168dd3526eb7871ac2251049fc7c4f5d5c2fddfd2022; transport ID mecanum.final-issued-receipt-topic-qos/v2; manifest SHA-256 338bea1b7350d3b82146c7e728516ec7947471ee68db0f8871ddb72071b79620; manifest path docs/RECEIPT_TOPIC_QOS_TRANSPORT_MANIFEST.json | Canonical approved contract/manifest identity; no runtime transport implementation in Gate A. |
| Receipt interface | mecanum.final-issued-receipt/v2; ros2_ws/src/mecanum_nav_rl_interfaces/msg/FinalIssuedCommandReceipt.msg; schema SHA-256 0c6446674bf17373ec646519043f506a9a7a15f95d5fdd10829b0cedb956500a | Canonical Registry-selected interface source; Gate A may only carry a structural reference if confirmed by focused audit. |
| S2 semantic provenance pin | mecanum.snapshot-synchronization-temporal/v1; embedded contract/manifest SHA-256 1be31c1915fedd86f269cee5214d794da0899a0d69dbb0ba5392e619813d4a8f; full source path/hash in §2 | PEP provenance pin only, not promoted authority. Whether/how this pin is a structural reference member must be confirmed against PEP wording and audit. |
| OIC and V3 Spec | Exact provenance paths/hashes in §2 | Provenance-only; neither provides Gate A members or validation rules. |

This inventory does not create a new contract, change a hash, amend ACR8/QoS6, or settle the noted proposal-era wording in ACR8 §5.2. If focused audit identifies a genuine unresolved authority conflict rather than a representational question, implementation remains stopped pending separate governance resolution.

## 5. Scope and acceptance boundary

This proposal records decisions for the existing primitive-only Gate A scope. It does not add or authorize configuration/compiler/profile work, ROS/ROSIDL/QoS/TF/DDS integration, adapters, synchronizer/buffers, receipt bridge/history, assembler/encoder, 81D vector construction, V1 observation/decoder/snapshot use, Ground Truth, HIL, hardware, deploy_sim or deploy_real.

Before a later exact CODE_AUTHORIZATION candidate can be considered, its packet must resolve every PENDING item in §§3–4 into an exact field/type/signature/error matrix; identify exact file allowlist, base and hashes; provide acceptance tests for immutability, required/unknown/wrong-type failure, no coercion/default, exact reference pairs, lifecycle/epoch/generation/time-domain matching, and cutoff strictly after both barriers; prove no draft was promoted to authority; and pass focused independent audit. Those criteria describe future evidence only. This candidate does not run such checks or tests and does not authorize their implementation.

## 6. Status and authority limits

    USER_STRUCTURAL_DIRECTION: RECORDED_FOR_FOCUSED_AUDIT
    DECISION_RESOLUTION: DRAFT_PENDING_FOCUSED_INDEPENDENT_AUDIT
    PENDING_EXACT_FIELD_AND_ERROR_MATRIX: TRUE
    S2_REVISION_2: PROVENANCE_ONLY
    OIC_REVISION_6: PROVENANCE_ONLY
    V3_BOUNDARY_SPECIFICATION_REVISION_7: SUPPORTING_PROVENANCE_ONLY
    WP-03: CLOSED (unchanged at baseline)
    WP-04: BLOCKED_BY_CONTRACT
    GATE_A: NOT_PASSED
    CODE_AUTHORIZATION: NOT_GRANTED
    RUNTIME_APPROVED: NOT_APPROVED

This is a documentation candidate for focused audit only. It does not amend PEP-001, Registry, Ledger, ACR8, QoS6 or any contract; it changes no WP status/dependency and grants no implementation or runtime permission.
