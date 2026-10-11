# WP-04 Gate B Consolidated Decision and Exact-Data-Contract Correction

**Status:** `CANDIDATE_ONLY_PENDING_FOCUSED_INDEPENDENT_AUDIT_AND_CANONICAL_INTEGRATION`
**Work package:** `WP-04-OBSERVATION-INPUT-PROFILE-ARCHITECTURE-AMENDMENT`
**Integration base:** `origin/integration/implementation@e89aeda5ca78859bfeedac4e7b94bcd6c7dcc7f0`
**Candidate branch:** `wp-04-observation-input-profile-architecture-amendment-e89aeda5`
**Decision basis:** `WP04_GATE_B_CONSOLIDATED_OWNER_DECISION_PROPOSAL_572DA885`, supplied by the User; not represented as a Git-pinned authority or hashed audit report.

This record carries forward the eight Owner decisions supplied in the earlier work-package context and corrects the resolved-record scope. The cited proposal name is provenance supplied by the User only; this record does not assert that the proposal is present in Git, nor invent a report hash. Source review candidate `wp-04-gate-b-exact-data-contract-change-control-68174e@687469f4aa2f166566e31aa91c1b1d90648c3812` is superseded review provenance only; it was not integrated and is not active authority. This replacement remains candidate governance content until this exact candidate is audited, separately authorized for integration, fast-forwarded, and remotely verified.

## 1. Owner decisions recorded

1. Create a controlled `Observation V3 Specification` revision 1.
2. Preserve the receipt v2 message byte-for-byte. Bind receipt/config compatibility through an immutable wrapper/config record outside the message; do not add `config_hash` to the message.
3. Preserve the Gate A structural container. Add a resolved Gate B record owned and constructed by the `ResolvedConfigV3` compiler.
4. The ROS adapter validates ROS message type, QoS, frame, freshness, and provenance. The pure core receives typed data only.
5. Unmeasured timing/profile values are `PENDING_MEASUREMENT`. A compiler must reject them in a real resolved profile.
6. A receipt is eligible only when its lifecycle tuple matches and its stamp is strictly after both action and reset barriers. Mismatch, stale input, or timeout fails closed.
7. Use the exact existing ACR8 status vocabulary/mapping recorded in §2. Malformed or unverifiable source/provenance for which no authorized mapping exists is `AUTHORITY_CHANGE_REQUIRED`; do not create a new status.
8. Prepare governance only. Any later work is split into pure-core, ROSIDL, adapter/QoS, and runtime/HIL evidence phases.

The prior review-candidate `ReceiptIngressBindingV3` shape and any proposal to store lifecycle values in a resolved static record are superseded provenance, not active authority. Lifecycle tuple and barrier checks remain runtime ingress semantics; the proposed `ObservationInputProfileV3` contains only static contract references and immutable source provenance. `ResolvedGateBRecordV3`, if used, is an internal compiler/type abstraction only and does not add a root member. Observation Input Contract V3 revision 6 remains `REVISED_DRAFT` provenance-only and cannot be used as field/default/schema authority. This Architecture-amendment candidate defines no runtime implementation and is inactive until its exact amendment is audited, separately authorized, integrated, and remotely verified.

## 2. Gate B failure/status matrix

The status identifiers below are existing ACR8 vocabulary. QoS6 transport classifications remain transport-layer evidence and are not promoted into new ACR statuses. The mappings describe fail-closed outcomes for a future implementation; they do not claim the behavior exists now.

| Condition | Transport/validation event | Existing ACR8 status | Required disposition |
|---|---|---|---|
| Receipt absent through the resolved action-bound timeout | `RECEIPT_AFTER_BARRIER_TIMEOUT` | `INPUT_MISSING_NON_READY` | No vector; no fallback |
| Receipt stale under approved profile freshness rule | `INPUT_STALE_NON_READY` | `INPUT_STALE_NON_READY` | Reject input; no vector |
| Receipt timestamp later than observation cutoff / future relative to cutoff | Future-stamp validation | `FUTURE_STAMP_CONTRACT_ERROR` | Reject; no reinterpretation |
| Sensor snapshot synchronization miss | Sensor sync validation | `SENSOR_SYNC_MISS_NON_READY` | Reject synchronized input |
| Reference snapshot synchronization miss | Reference sync validation | `REFERENCE_SYNC_MISS_NON_READY` | Reject synchronized input |
| Buffer overflow | Buffer admission | `BUFFER_OVERFLOW_NON_READY` | Fail closed; no dropping policy unless separately specified |
| Ordering cannot be established | Ordering validation | `ORDERING_CONTRACT_AMBIGUITY_NON_READY` | Reject ambiguous ordering |
| Receipt at/before an action or reset barrier | Barrier predicate | `BARRIER_NOT_PASSED_NON_READY` | Receipt cannot satisfy the barrier |
| Cutoff is not strictly after both action/reset barriers | Structural cutoff predicate | `CUTOFF_BARRIER_ORDER_NON_READY` | Reject cutoff |
| Interface ID/SHA mismatch | Exact pin validation | `LIFECYCLE_OR_CONTRACT_MISMATCH_NON_READY` | Reject; no alias/fallback |
| QoS ID/manifest mismatch or incompatible QoS | Binding/transport validation | `LIFECYCLE_OR_CONTRACT_MISMATCH_NON_READY` | Reject incompatible delivery |
| Resolved config hash mismatch | Wrapper/config binding | `LIFECYCLE_OR_CONTRACT_MISMATCH_NON_READY` | Reject config/receipt pairing |
| Lifecycle tuple mismatch | Lifecycle compatibility | `LIFECYCLE_OR_CONTRACT_MISMATCH_NON_READY` | Reject; compare the selected lifecycle tuple atomically and exactly |
| Frame mismatch | Adapter frame validation | `LIFECYCLE_OR_CONTRACT_MISMATCH_NON_READY` | Reject; no frame adaptation |
| Generation invalidated | Lifecycle invalidation | `GENERATION_INVALIDATED_NON_READY` | Reject prior-generation data |
| Duplicate sequence | QoS6 ordering classification `DUPLICATE` | `ORDERING_CONTRACT_AMBIGUITY_NON_READY` | Reject delivery |
| Non-monotonic sequence | QoS6 ordering classification `NON_MONOTONIC` | `ORDERING_CONTRACT_AMBIGUITY_NON_READY` | Reject and report protocol fault |
| Coalesced gap after a prior accepted receipt from same publisher | QoS6 `COALESCED_GAP` | No failure status by itself | Record diagnostic gap and accept newer otherwise-compatible latest state |
| Malformed or unverifiable source/provenance with no authorized mapping | Validation cannot establish a trusted contract fact | **`AUTHORITY_CHANGE_REQUIRED`** | Stop; no new status and no inferred fallback |

QoS6 specifies that `COALESCED_GAP` is accepted only when a prior receipt from the same publisher instance has been admitted; a late joiner's first retained sample is `ACCEPTED`. ACR8 status mapping does not override that transport rule. Any future mapping not explicitly present in this table or approved authority must be treated as `AUTHORITY_CHANGE_REQUIRED`, not improvised.

## 3. Superseded exact-data-contract replacement review provenance

The replacement specification is revision 2, candidate-only, at
`docs/OBSERVATION_V3_SPECIFICATION.md`. Its full-document SHA-256 is recorded
in the candidate Registry and PEP; the hash is not embedded in the
specification itself. The prior review candidate used the same proposed
revision number but was never integrated. Its artifacts and delivery hashes
are retained only as superseded review provenance; they are not current source
selection or authority.

The following prior Owner decisions remain part of the Gate-B contract boundary; their candidate-only source history does not itself activate a schema:

- Flat `ReceiptIngressBindingV3`, with the required member set shown in §3 of
  the specification; keyword-only, required, exact built-in `str`/`int`, no
  coercion, no defaults, and the selected ranges/value semantics.
- The binding carries `observation_spec_revision`; the full-document
  specification SHA is pinned externally. It does not duplicate
  `ResolvedConfigV3.provenance.config_hash`.
- Lifecycle is the atomic exact tuple
  `(episode_generation, reset_epoch, runtime_generation)`, mapped to
  `ObservationCutoffV3.epoch == reset_epoch` and
  `ObservationCutoffV3.generation == runtime_generation`; active
  `lifecycle_identity` comes from `SafetyLifecycle` context and is verified by
  the adapter against the configured ingress binding.
- Existing ACR8 mappings, fail-closed behavior, pure-core/adapter boundary,
  raw-ROS prohibition, and `PENDING_MEASUREMENT` rule are unchanged. No numeric
  timing/profile value is selected.

The following blocker labels describe the superseded revision-2 review candidate's state at that time; they are retained as historical provenance, not current active authority. This candidate proposes resolutions for those two concerns: the full-global hash rule is stated in §6, and the static input-profile schema is stated in §6 and the companion Architecture Change Record. Those proposals remain inactive pending focused audit, separate exact-commit User authorization, integration, and remote-ref verification. Concrete contract IDs/digests and source pins not selected by active authority, and measurement-dependent values, remain unresolved and make any profile instance ineligible for resolution.

1. Historical label: `DECISION_DEFERRED_PENDING_EXACT_NON_CIRCULAR_CONFIG_HASH_PROJECTION` — this amendment candidate proposes RFC 8785 JCS UTF-8 hashing over the full resolved Architecture config, excluding the output `config_hash` and prohibited runtime facts; it is not active before amendment integration.
2. Historical label: `DECISION_DEFERRED_PENDING_EXACT_RESOLVED_OBSERVATION_INPUT_PROFILE_SHAPE` — this amendment candidate proposes the exact static `ObservationInputProfileV3` shape in §6/ACR; it does not select concrete profile pins unsupported by active authority. OIC revision 6 remains provenance-only and cannot supply field/default/schema authority.

The former `ResolvedConfigV3.gate_b` required-slot wording was candidate-only and is superseded by this proposal; no root `gate_b` is added. Gate-B static bindings belong under `ResolvedConfig.observation.input_profile`. `ResolvedGateBRecordV3`, if used, is only an internal compiler/type abstraction and must serialize into that approved nested representation. The full Architecture root envelope and global `config_hash` remain controlling. No code authorization may rely on this candidate schema before the amendment is effective and required reference values/evidence are selected.

## 4. Controlled evidence layers

The evidence sequence is cumulative and separate:

1. **Pure Python:** immutable resolved record/binding, compiler ownership, exact pins, typed ingress seam, deterministic barrier/order/status tests, 81D layout/provenance tests, and import-purity checks.
2. **ROSIDL generation:** only after a separately scoped authorization; verify the already-pinned receipt v2 bytes and dependency closure generate/install without changing the message. This candidate does not perform generation.
3. **Adapter/QoS integration:** separately authorized integration tests for exact interface/config pins, QoS compatibility/events, source/frame/provenance, receive/freshness, ordering and fail-closed propagation.
4. **Runtime/HIL:** later and separately approved evidence; no runtime, HIL, hardware, or deployment authorization is granted here.

Passing an earlier layer is not evidence for a later one. Gate B remains `NOT_STARTED` until the required contract gates, implementation review, and evidence are satisfied and a separate governance transition is authorized.

## 5. Candidate authority and status boundary

The accompanying Specification revision 3, Architecture Change Record, this decision record, Registry entry, PEP entry, and Ledger entry are candidate-only. If integrated after audit and separate exact-commit User authorization, they record the proposed architecture amendment; they do not themselves authorize implementation or runtime.

No changes are made to ACR8, QoS6, the receipt v2 `.msg`, ROSIDL package metadata, Gate A schema, error-carrier decision, code, or tests. WP-05 map metadata schema and its status remain unchanged.

```text
WP-04: BLOCKED_BY_CONTRACT
GATE_A_STRUCTURAL_PRIMITIVES: PASSED
GATE_B: NOT_STARTED
GATE_B_BOUNDARY_CLOSURE: ACTIVE_ON_INTEGRATION
OBSERVATION_INPUT_PROFILE: CANDIDATE_PENDING_ARCHITECTURE_AMENDMENT_INTEGRATION
CONCRETE_PROFILE_REFERENCE_PINS: PENDING_ACTIVE_AUTHORITY_AND_EVIDENCE
CODE_AUTHORIZATION: NOT_GRANTED
RUNTIME_APPROVED: NOT_APPROVED
WP-05: OPEN
```

## 6. ObservationConfig input-profile amendment candidate

The proposed schema is `ResolvedConfig.observation.input_profile: ObservationInputProfileV3`, required and nested under the existing Architecture root member `observation`. No root `gate_b` member exists or is proposed. The exact candidate member set and reference types are in Specification revision 3 and the companion Architecture Change Record. Concrete reference values not supported by active canonical source pins remain unresolved; OIC rev.6 remains provenance-only.

The profile descriptor is static and participates in the global resolved-config hash. RFC 8785 JCS UTF-8 bytes cover the fully resolved config; the output `config_hash` and prohibited runtime facts are excluded. Missing, unknown, defaulted, coerced, unresolved, or evidence-deficient required data rejects the entire config without partial hash. Runtime lifecycle facts, timestamps, freshness observations, receipt instances/payloads, ROS objects, and sensor samples are outside the config/hash.

This amendment candidate is not active Architecture authority until audit, separate exact-commit User authorization, fast-forward, and remote-ref verification. It grants no `CODE_AUTHORIZATION`, does not pass Gate B or close WP-04, and grants no runtime/HIL/hardware/deployment authority.
