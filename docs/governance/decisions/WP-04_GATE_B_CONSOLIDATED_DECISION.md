# WP-04 Gate B Consolidated Decision and Exact-Data-Contract Correction

**Status:** `ACR_REVISION_3_ACTIVATED_AT_INTEGRATION_8C3DE; GATE_B_NOT_STARTED; THIS_STATUS_RECONCILIATION_IS_CANDIDATE_ONLY`
**Work package:** `WP04-ACR-REV3-ACTIVATION-STATUS-RECONCILIATION`
**Activation integration:** `8c3de26521d7028a933f0a3ebe780fcb372f7a3a`; ACR revision 3 exact SHA `38cb74c0b09cd9c3ecbbac30c6520e0d01f7711adb788414a0a46489e844d9f8`; activated Specification revision 5 exact SHA `4092ee19d48a760b329ff49b9a79e39ab8389ff232aabd5dd06db83f8d83e5a2`
**Decision basis:** `WP04_GATE_B_CONSOLIDATED_OWNER_DECISION_PROPOSAL_572DA885`, supplied by the User; not represented as a Git-pinned authority or hashed audit report.

The Project Owner/User approved both the global configuration-hash policy and nested observation-input profile policy as written on 2026-10-12 (`APPROVE_BOTH_AS_WRITTEN`). The decision was recorded before activation. The exact-candidate audit PASS and separate exact-commit User authorization for `8c3de26521d7028a933f0a3ebe780fcb372f7a3a` are `USER_SUPPLIED_EVIDENCE`; no report hash is asserted. The fast-forward and remote-ref verification are Git-verifiable facts. Source review candidate `wp-04-gate-b-exact-data-contract-change-control-68174e@687469f4aa2f166566e31aa91c1b1d90648c3812` remains superseded review provenance only; it was not integrated or made active authority. The Architecture DOCX remains highest authority.

At the historical pre-activation integration base `c1187de97c550b9968d88aa6043ed716df981b54`, revision 1 was the active Gate B boundary-source selection, selected at `68174e714cbe8aab61880113496cd7ccd7f97f5d`, SHA-256 `feffb86e335d64a3a3fe0f3a1ce0866f868c8ed56ffa4412db14128c80b284ec`. Revisions 1–4 remain preserved provenance. At current activation integration `8c3de26521d7028a933f0a3ebe780fcb372f7a3a`, ACR revision 3 activated Specification revision 5 (SHA-256 `4092ee19d48a760b329ff49b9a79e39ab8389ff232aabd5dd06db83f8d83e5a2`). Historical revisions are not rewritten.

## 1. Owner decisions recorded

1. Create a controlled `Observation V3 Specification` revision 1.
2. Preserve the receipt v2 message byte-for-byte. Bind receipt/config compatibility through an immutable wrapper/config record outside the message; do not add `config_hash` to the message.
3. Preserve the Gate A structural container. Add a resolved Gate B record owned and constructed by the `ResolvedConfigV3` compiler.
4. The ROS adapter validates ROS message type, QoS, frame, freshness, and provenance. The pure core receives typed data only.
5. Unmeasured timing/profile values are `PENDING_MEASUREMENT`. A compiler must reject them in a real resolved profile.
6. A receipt is eligible only when its lifecycle tuple matches and its stamp is strictly after both action and reset barriers. Mismatch, stale input, or timeout fails closed.
7. Use the exact existing ACR8 status vocabulary/mapping recorded in §2. Malformed or unverifiable source/provenance for which no authorized mapping exists is `AUTHORITY_CHANGE_REQUIRED`; do not create a new status.
8. Prepare governance only. Any later work is split into pure-core, ROSIDL, adapter/QoS, and runtime/HIL evidence phases.

Observation V3 Specification revision 2 and its `ReceiptIngressBindingV3` proposal are historical pinned review provenance only: source branch `wp-04-gate-b-exact-data-contract-completion-refresh-1e14644`, commit `e89aeda5ca78859bfeedac4e7b94bcd6c7dcc7f0`, path `docs/OBSERVATION_V3_SPECIFICATION.md`, revision-2 full-document SHA-256 `ed06bc5bd145e0eb9376df71ff42ee60069906d987c78531ba8b9e688746b1bc`. They are superseded and are not the current content at that path. Specification revision 3 and its proposed profile shape were present in integration ancestry from source commit `d87b5a17ca0e9430d0b163aacf5b9cfcc4458d14`; at that historical stage the ACR remained candidate-only. ACR revision 3 was later activated at `8c3de26521d7028a933f0a3ebe780fcb372f7a3a` as recorded above. The Architecture DOCX remains highest authority. Lifecycle tuple and barrier checks remain runtime ingress semantics; the static profile contains only contract references and immutable source provenance. `ResolvedGateBRecordV3`, if used, is only an internal compiler/type abstraction and does not add a root member. Observation Input Contract V3 revision 6 remains `REVISED_DRAFT` provenance-only and cannot be used as field/default/schema authority. This record does not pass Gate B, close WP-04, or authorize implementation/runtime.

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

## 3. Superseded exact-data-contract revision-2 historical provenance

Observation V3 Specification revision 2 and its `ReceiptIngressBindingV3`
proposal are historical pinned review provenance only:
`wp-04-gate-b-exact-data-contract-completion-refresh-1e14644@e89aeda5ca78859bfeedac4e7b94bcd6c7dcc7f0`,
path `docs/OBSERVATION_V3_SPECIFICATION.md`, full-document SHA-256
`ed06bc5bd145e0eb9376df71ff42ee60069906d987c78531ba8b9e688746b1bc`.
Revision 2 is superseded; it is not the current content at that path and is
not active source selection or authority. At source baseline
`e89aeda5ca78859bfeedac4e7b94bcd6c7dcc7f0`, revision 1 remained active.
Revision 3 from source commit
`d87b5a17ca0e9430d0b163aacf5b9cfcc4458d14` is present in integration ancestry
at base `410d9cb70518b64d3c76c2ef99b11b69d1da6701` as candidate/provenance.
At the pre-activation base, the companion ACR was candidate-only and controlled
activation. That historical status is superseded by the verified activation
event recorded in the current activation section below. The `ObservationInputProfileV3` shape described at
§3.1 is unchanged; this historical note does not alter its semantics.

The following decisions remain relevant to the Gate-B boundary. The first two bullets record the historical revision-2 proposal only; they do not describe the current Specification path or add members to `ObservationInputProfileV3`:

- Historical revision-2 proposal only: flat `ReceiptIngressBindingV3`, with
  its member set and semantics pinned by the revision-2 source reference above.
- Historical revision-2 proposal only: that binding carried
  `observation_spec_revision` and did not duplicate
  `ResolvedConfigV3.provenance.config_hash`. The revision-3 candidate proposes
  the static descriptor in `ObservationInputProfileV3` §3.1 and the companion
  ACR; its proposed shape is not overwritten by this history note.
- Lifecycle is the atomic exact tuple
  `(episode_generation, reset_epoch, runtime_generation)`, mapped to
  `ObservationCutoffV3.epoch == reset_epoch` and
  `ObservationCutoffV3.generation == runtime_generation`; active
  `lifecycle_identity` comes from `SafetyLifecycle` context and is verified by
  the adapter against the configured ingress binding.
- Existing ACR8 mappings, fail-closed behavior, pure-core/adapter boundary,
  raw-ROS prohibition, and `PENDING_MEASUREMENT` rule are unchanged. No numeric
  timing/profile value is selected.

The following blocker labels describe the earlier unresolved Owner questions. The Owner decision of 2026-10-12 resolves both questions as `APPROVE_BOTH_AS_WRITTEN`; ACR revision 3 activation is recorded at integration `8c3de26521d7028a933f0a3ebe780fcb372f7a3a`. Concrete contract IDs/digests and source pins not selected by active authority, and measurement-dependent values, remain unresolved and make any profile instance ineligible for resolution.

1. `DECISION_DEFERRED_PENDING_EXACT_NON_CIRCULAR_CONFIG_HASH_PROJECTION` — Owner decision recorded and ACR revision 3 activated: global `ResolvedConfig.config_hash` is SHA-256 over RFC 8785 JCS canonical UTF-8 bytes of the complete, resolved, validated static Architecture `ResolvedConfig`; no BOM or trailing newline; omit only output `config_hash`. Runtime-only data, duplicate keys and non-finite numbers are rejected, not silently filtered.
2. `DECISION_DEFERRED_PENDING_EXACT_RESOLVED_OBSERVATION_INPUT_PROFILE_SHAPE` — Owner decision recorded and ACR revision 3 activated: required nested `ObservationConfig.input_profile: ObservationInputProfileV3`, no root `gate_b`; static profile pins are included in the global hash. Exact member set and strict semantics are recorded in the activated companion ACR. Concrete contract pins/evidence and required measurements remain pending. OIC revision 6 remains provenance-only and cannot supply field/default/schema authority.

The former `ResolvedConfigV3.gate_b` required-slot wording was candidate-only historical provenance and is superseded; no root `gate_b` is added. The activated schema places Gate-B static bindings under `ResolvedConfig.observation.input_profile`. `ResolvedGateBRecordV3`, if used, is only an internal compiler/type abstraction and must serialize into that nested representation. The full Architecture root envelope and global `config_hash` remain controlling. This governance status does not resolve required reference values/evidence or authorize code.

## 4. Controlled evidence layers

The evidence sequence is cumulative and separate:

1. **Pure Python:** immutable resolved record/binding, compiler ownership, exact pins, typed ingress seam, deterministic barrier/order/status tests, 81D layout/provenance tests, and import-purity checks.
2. **ROSIDL generation:** only after a separately scoped authorization; verify the already-pinned receipt v2 bytes and dependency closure generate/install without changing the message. This candidate does not perform generation.
3. **Adapter/QoS integration:** separately authorized integration tests for exact interface/config pins, QoS compatibility/events, source/frame/provenance, receive/freshness, ordering and fail-closed propagation.
4. **Runtime/HIL:** later and separately approved evidence; no runtime, HIL, hardware, or deployment authorization is granted here.

Passing an earlier layer is not evidence for a later one. Gate B remains `NOT_STARTED` until the required contract gates, implementation review, and evidence are satisfied and a separate governance transition is authorized.

## 5. Historical pre-activation candidate/provenance snapshot at c1187de

At historical base `c1187de97c550b9968d88aa6043ed716df981b54`, the path contained Observation V3 Specification revision 3 and ACR revision 1 as integration-resident candidate/provenance. Source candidate `wp-04-gate-b-global-config-owner-decision-c1187de@e79a8f6fd6be7b50dbbfe28819a34116ecaec3ab` recorded Specification revision 4 and ACR revision 2. The correction candidate recorded Specification revision 5 and ACR revision 3. Their then-candidate-only status was superseded at integration `8c3de26521d7028a933f0a3ebe780fcb372f7a3a` after exact-candidate audit PASS and separate exact-commit User authorization (`USER_SUPPLIED_EVIDENCE`, no report hash asserted), fast-forward, and remote-ref verification. Git ancestry alone is not treated as audit or authorization evidence. No Architecture DOCX bytes were changed; this activation does not authorize implementation/runtime or satisfy Gate B.

No changes are made to ACR8, QoS6, the receipt v2 `.msg`, ROSIDL package metadata, Gate A schema, error-carrier decision, code, or tests. WP-05 map metadata schema and its status remain unchanged.

Historical status at integration base `c1187de97c550b9968d88aa6043ed716df981b54`, before the activation event:

```text
WP-04: BLOCKED_BY_CONTRACT
GATE_A_STRUCTURAL_PRIMITIVES: PASSED
GATE_B: NOT_STARTED
GATE_B_BOUNDARY_CLOSURE: ACTIVE_ON_INTEGRATION
OWNER_DECISIONS: APPROVE_BOTH_AS_WRITTEN
OBSERVATION_INPUT_PROFILE_SCHEMA: OWNER_DECIDED_CANDIDATE_PENDING_ACR_ACTIVATION
GLOBAL_CONFIG_HASH_POLICY: OWNER_DECIDED_CANDIDATE_PENDING_ACR_ACTIVATION
GLOBAL_CONFIG_HASH_IMPLEMENTATION: NOT_IMPLEMENTED
CONCRETE_PROFILE_REFERENCE_PINS: PENDING_ACTIVE_AUTHORITY_AND_EVIDENCE
CODE_AUTHORIZATION: NOT_GRANTED
RUNTIME_APPROVED: NOT_APPROVED
WP-05: OPEN
```

## Current ACR revision-3 activation status and remaining blockers

At integration `8c3de26521d7028a933f0a3ebe780fcb372f7a3a`, ACR revision 3 (SHA-256 `38cb74c0b09cd9c3ecbbac30c6520e0d01f7711adb788414a0a46489e844d9f8`) activated Observation V3 Specification revision 5 (SHA-256 `4092ee19d48a760b329ff49b9a79e39ab8389ff232aabd5dd06db83f8d83e5a2`). Exact-candidate audit PASS and separate exact-commit User authorization are `USER_SUPPLIED_EVIDENCE`; no audit-report hash is asserted. The fast-forward from `c1187de97c550b9968d88aa6043ed716df981b54` and post-fast-forward remote-ref verification are Git-verifiable facts. This reconciliation records that event and does not infer it from ancestry alone.

The inherited candidate-only/activation-pending wording in the historical sections describes states before the relevant integration events; it is historical provenance, not current status. Commit `3fc3e2e583550b47195720f0de2fda8fbbd7490f` is integrated and records the ACR revision-3/Specification revision-5 activation status consistently in the governance set. The separate review candidate `4a938773cfd8f36cc81934951f4fa02dae99cb05` was reported by the User as audit-PASS evidence but was not integrated after a delivery preflight found status wording that would become stale after integration. That audit verdict is `USER_SUPPLIED_EVIDENCE`; no report hash is asserted. This correction records the already-integrated event and makes no technical change to the active ACR/specification.

Concrete required contract/source pins and evidence remain pending; measurements remain `PENDING_MEASUREMENT`. Activation does not create a profile instance, resolve those items, satisfy all ACR8 implementation conditions, or pass Gate B.

WP-05 boundary is unchanged: `warehouse_map2` remains `approval_status: draft`, `world_frame: NOT_DECLARED`, and `runtime_compatibility: NOT_VALIDATED`. User-supplied attribution that the map was SLAM-generated from `tugbot_depot.sdf` remains provenance only; it is not evidence of map/world equality, a transform, metric alignment, runtime validation, or map approval.

```text
WP-04: BLOCKED_BY_CONTRACT
GATE_A_STRUCTURAL_PRIMITIVES: PASSED
GATE_B: NOT_STARTED
WP-05: OPEN
CODE_AUTHORIZATION: NOT_GRANTED
RUNTIME_APPROVED: NOT_APPROVED
```

## 6. Activated ObservationConfig input-profile schema and remaining blockers

The Owner-approved and activated change-control records `ResolvedConfig.observation.input_profile: ObservationInputProfileV3` as required and nested under the existing Architecture root member `observation`. No root `gate_b` member is added. The active member set and reference types are in Specification revision 5 and companion ACR revision 3. Concrete reference values not supported by active canonical source pins remain unresolved; OIC rev.6 remains provenance-only.

The approved change-control decision records a static profile descriptor covered by the global resolved-config hash. The global payload is the full resolved and validated static config serialized as RFC 8785 JCS UTF-8, with no BOM or trailing newline; only output `config_hash` is omitted. Runtime lifecycle facts, timestamps, freshness observations, receipt instances/payloads, ROS objects, and sensor samples are invalid config inputs and cause rejection, not additional silently filtered exclusions. Missing, unknown, defaulted, coerced, unresolved or evidence-deficient required data rejects the whole config with no partial hash.

The integrated status-reconciliation commit `3fc3e2e583550b47195720f0de2fda8fbbd7490f` does not modify or supersede the Architecture DOCX. ACR revision 3 and Specification revision 5 remain active technical authority from integration `8c3de26521d7028a933f0a3ebe780fcb372f7a3a`; status/provenance successors do not replace their technical semantics. Concrete resolved observation-profile pins/evidence and required measurements remain Gate B blockers. This record does not grant `CODE_AUTHORIZATION`, pass Gate B, close WP-04, or grant runtime/HIL/hardware/deployment authority.

## 7. F-01 exhaustive global hash-root correction — historical candidate provenance

The source review candidate `e79a8f6fd6be7b50dbbfe28819a34116ecaec3ab` was
reported by the User's focused audit to lack an explicit exhaustive root list in
ACR §4 and Specification §5.1. This is user-supplied audit evidence; no audit
report hash is asserted. The correction candidate's ACR revision 3 and
Specification revision 5 enumerate the exact global hash-input roots from
Architecture §4: `schema_version`, `runtime_profile`, `navigation_mode`,
`project`, `topics`, `frames`, `state_estimation`, `localization`,
`navigation`, `observation`, `action`, `reward`, `training`, `evaluation`,
`safety`, and `acceptance`. The list is exhaustive; each appears exactly once;
no root can be omitted, added, renamed, replaced, or separately projected.
`observation.input_profile` is nested within `observation`. Only the output
`config_hash` is excluded; duplicate keys, non-finite values, and runtime-only
facts are rejected rather than filtered. At the historical pre-activation
base `c1187de97c550b9968d88aa6043ed716df981b54`, these correction bytes were
review provenance; the correction was later integrated at `8c3de…` as ACR
revision 3 and Specification revision 5. This history changes no Owner
decision or profile semantics.

Candidate file pins: `docs/architecture/ARCH_CHANGE_RECORD_OBSERVATION_INPUT_PROFILE_V3.md`
revision 3, SHA-256
`38cb74c0b09cd9c3ecbbac30c6520e0d01f7711adb788414a0a46489e844d9f8`; and
`docs/OBSERVATION_V3_SPECIFICATION.md` revision 5, SHA-256
`4092ee19d48a760b329ff49b9a79e39ab8389ff232aabd5dd06db83f8d83e5a2`. These
pins identify the technical bytes activated at `8c3de…`; the historical
pre-activation candidate wording is not current status.
