# Observation V3 Specification

**Revision:** `3` (integration-resident candidate/provenance pending ACR activation conditions; revision 2 remains superseded historical review provenance)
**Status:** `INTEGRATION_RESIDENT_CANDIDATE_PENDING_ACR_ACTIVATION_CONDITIONS`
**Work package:** `WP-04-OBSERVATION-INPUT-PROFILE-ARCHITECTURE-AMENDMENT`
**Source commit (Git ancestry fact only):** `d87b5a17ca0e9430d0b163aacf5b9cfcc4458d14`; present in integration ancestry at `410d9cb70518b64d3c76c2ef99b11b69d1da6701`; ACR activation conditions remain pending
**Runtime status:** `RUNTIME_NOT_APPROVED`

This revision is an integration-resident candidate/provenance record for the proposed nested `ObservationConfig.input_profile` described in `docs/architecture/ARCH_CHANGE_RECORD_OBSERVATION_INPUT_PROFILE_V3.md`. Git history places source commit `d87b5a17ca0e9430d0b163aacf5b9cfcc4458d14` in the integration ancestry at the stated base, but that fact does not satisfy the ACR activation conditions or prove focused audit/User authorization. The ACR remains `CANDIDATE_ONLY_PENDING_FOCUSED_INDEPENDENT_AUDIT_AND_CANONICAL_INTEGRATION`; the Architecture DOCX remains the highest authority. This candidate does not pass Gate B, close WP-04, implement an adapter, or authorize code or runtime.

## 1. Authority and exact pins

The governing architecture remains `docs/MECANUM_NAV_DRL_Architecture.docx`. Current approved Gate A/Gate B contract authority is ACR revision 8 and Receipt Topic QoS Contract revision 6, as selected by the Canonical Source Registry and the integrated bundled approval record. Their source files retain historical pre-integration `DRAFT` wording; that wording is superseded only for document authority/status by the approval record and Registry, not for technical content.

| Artifact | Exact identity | Canonical path | SHA-256 |
|---|---|---|---|
| ACR | revision 8 | `docs/ACR_V3_OBSERVATION_BOUNDARY_CLOSURE.md` | `03fef021f6b9731f811f83a5e53aae1c430bdc2ea76815a8ada416f1a5bf772c` |
| Receipt Topic QoS Contract | revision 6; `mecanum.final-issued-receipt-topic-qos/v2` | `docs/RECEIPT_TOPIC_QOS_CONTRACT.md` | Full document `4200cd2fbdc81a19400f168dd3526eb7871ac2251049fc7c4f5d5c2fddfd2022`; transport manifest `338bea1b7350d3b82146c7e728516ec7947471ee68db0f8871ddb72071b79620` |
| Receipt interface | `mecanum.final-issued-receipt/v2`, schema revision 2 | `ros2_ws/src/mecanum_nav_rl_interfaces/msg/FinalIssuedCommandReceipt.msg` | `0c6446674bf17373ec646519043f506a9a7a15f95d5fdd10829b0cedb956500a` |
| Dependency closure | version 1 | `docs/RECEIPT_INTERFACE_DEPENDENCY_CLOSURE_MANIFEST.json` | `0872fa8c10179f69c2e9e9546392ac734a4f4e94ade176a8be431f06905ecf73` |
| Bundle approval record | QoS6/ACR8 approval | `docs/governance/decisions/QOS_REVISION_6_ACR_REVISION_8_BUNDLE_APPROVAL.md` | `4d740559f850f179387db802df845748068f75a21266fd1edb52402b2c72c529` |
| Gate A structural schema | active source selection, Gate A scope only | `docs/OBSERVATION_GATE_A_STRUCTURAL_SCHEMA.md` | `43537b8f0edafbe809e6f70bda86808f87b12f146ed45509c4bfbacd26956ad3` |
| Gate A error-carrier decision | accepted Gate A carrier only | `docs/governance/decisions/WP-04_GATE_A_ERROR_CARRIER_DECISION.md` | `72a2c94df548cb00557b1777e10d11b96b386329894edaf34e1d81c07ed4e94d` |

The receipt schema SHA, dependency-closure SHA, transport-manifest SHA, and full-document SHA values identify distinct byte sets and are not interchangeable. No `config_hash` is added to the receipt message. S2 revision 2, Observation Input Contract revision 6, and V3 Observation Boundary Specification revision 7 are provenance-only; none is promoted or used to add active fields.

## 2. Observation layout and ownership boundary

The policy observation remains exactly 81 `float32` values in the frozen order:

1. 72 LiDAR sectors;
2. 3 LocalReference features;
3. 3 measured-twist features `[vx, vy, wz]`;
4. 3 previous-final-issued-command features `[vx, vy, wz]`.

The 81D layout, feature ownership, frame/normalization rules, Ground Truth exclusion, and distinction among raw action, decoded candidate, and final-issued command are unchanged from Architecture and the approved contracts. This specification does not select numeric profile parameters. Ground Truth is excluded from policy input and its provenance path.

The pure-Python core accepts typed, already-validated values. A ROS adapter is responsible for middleware-facing message typing, QoS compatibility, frame validation, receive/freshness checks, source/provenance checks, and conversion into the typed ingress boundary. The core does not import ROS, inspect repositories/files, read clocks, perform I/O, or fabricate fallback values. No ROS adapter behavior is implemented or claimed by this document.

## 3. Gate B resolved record and receipt binding

The approved receipt v2 bytes remain unchanged. The `ResolvedConfig` root remains exactly the Architecture root envelope: no root `gate_b` member is added. The proposed location for Gate-B static binding is the versioned nested member `observation.input_profile: ObservationInputProfileV3`; it is not active while the ACR activation conditions remain pending. `ResolvedGateBRecordV3`, if used internally by a future compiler, is only an internal type abstraction; it is not a canonical root member and would serialize into the proposed `observation.input_profile` representation only if the ACR amendment is activated.

`ObservationInputProfileV3` contains only the static contract references listed
in §3.1 and immutable Git source provenance. The receipt v2 ID/SHA and QoS6
transport ID/manifest SHA remain the existing approved authority pins; they may
be referenced by the corresponding contract references and are not fields in
the receipt message. Exact contract IDs/digests and source pins for other
required contracts remain unresolved wherever active authority has not selected
them. No concrete profile instance is asserted here.

The earlier Gate-B review proposal's `profile_id`, `lifecycle_identity`, and
`expected_*generation` values are not members of this static descriptor. The
active lifecycle tuple, lifecycle identity, barriers, timestamps, sequence
values, freshness results, and receipt instances are runtime ingress facts and
must remain outside `ObservationInputProfileV3` and the global config hash.

Observation Input Contract V3 revision 6 remains provenance-only and is not field/default/schema authority. This specification does not create or alter receipt fields, QoS policy, or ACR8 statuses.

### 3.1 `ObservationInputProfileV3` static schema

The candidate proposes a required nested member with schema identity `observation-input-profile-v3`, revision `1`, and the proposed member set below. If activated, it would be a static immutable descriptor, not runtime state.

```text
ObservationInputProfileV3(
  *,
  schema_id: str,
  schema_revision: int,
  lidar_snapshot_contract: ObservationContractReferenceV3,
  local_reference_snapshot_contract: ObservationContractReferenceV3,
  measured_twist_snapshot_contract: ObservationContractReferenceV3,
  final_issued_receipt_contract: ObservationContractReferenceV3,
  frame_contract: ObservationContractReferenceV3,
  topic_qos_contract: ObservationContractReferenceV3,
  lifecycle_reset_barrier_policy: ObservationContractReferenceV3,
  profile_source: ImmutableGitSourceReferenceV3,
)

ObservationContractReferenceV3(
  *,
  contract_id: str,
  contract_sha256: str,
  source: ImmutableGitSourceReferenceV3,
)

ImmutableGitSourceReferenceV3(
  *,
  commit_sha: str,
  source_path: str,
  source_file_sha256: str,
)
```

All fields are required, keyword-only, exact built-in types, frozen/immutable, with no defaults or coercion. `schema_id` is exactly `observation-input-profile-v3`; `schema_revision` is exact `int` value `1`. Identifiers and paths are non-empty exact strings. Contract/file hashes are lowercase 64-hex; Git commit is a full lowercase 40-hex SHA. A Git source reference is verified against the exact tracked path bytes at that commit. No branch/tag, mutable URL, alias, lookup, or fallback is allowed. Contract identity SHA and source-file SHA are distinct pins.

The required contract IDs, semantic contract digests and profile source for a concrete instance are not populated unless selected by active authority. At this integration base, some snapshot/policy contracts lack their own canonical IDs/digests. Those values remain unresolved; the type definition does not invent them or make a profile instance valid. A profile missing any pin/evidence is not resolved and must be rejected as part of the whole config.

This descriptor contains no ROS message, sensor sample, receipt payload/instance, timestamp, sequence, lifecycle identity/counter, barrier occurrence, freshness result, or runtime state. The adapter validates runtime facts before creating typed ingress data; those facts remain outside static config and its hash.

### Lifecycle tuple

Receipt eligibility requires exact compatibility with the active lifecycle and strict temporal ordering. The receipt must be strictly after both the action and reset barriers, and at or before the observation cutoff. A receipt before/equal to either barrier, after cutoff, or associated with a mismatching or invalidated lifecycle is not eligible.

The selected lifecycle tuple is `(episode_generation, reset_epoch, runtime_generation)` with atomic exact comparison. `ObservationCutoffV3.epoch == reset_epoch`; `ObservationCutoffV3.generation == runtime_generation`. `episode_generation` participates in the exact tuple comparison. `lifecycle_identity` is the exact string from active `SafetyLifecycle` context; the adapter verifies it against the configured ingress binding and does not infer it from a receipt. No partial match, reuse, alias, or fallback is allowed. Missing, ambiguous, or mismatching correspondence fails closed using the decision record's existing mapping; an ambiguous/unverifiable identity with no authorized mapping is `AUTHORITY_CHANGE_REQUIRED`.

### Fail-closed state behavior

- Only a compatible, admitted receipt strictly after both barriers and not later than cutoff may satisfy the receipt input.
- A duplicate or non-monotonic sequence is rejected; a coalesced gap is classified only after an earlier accepted receipt from the same publisher instance, and is not by itself a missing latest-state receipt.
- Pre-barrier, stale, future, mismatched, missing, or invalidated inputs cannot be repaired using PPO action, decoder output, `SafetyState`, cached data, or synthetic zero.
- After reset, `observation0` requires the compatible new-epoch `SOURCE_SAFE_STOP` zero receipt with `CommandArbiter` provenance, admitted after the reset barrier.
- An action-bound timeout returns non-ready/no vector; no 81D vector is constructed.
- No state transition creates or advances barriers in this spec. `SafetyLifecycle` owns action/reset barriers; the assigned runtime adapter produces caller facts under its separate authority.

## 4. Pending measured/profile values

Unmeasured timing, receipt-after-barrier timeout, skew, buffer limits, sensor freshness, measured-twist validity/covariance/provenance, LiDAR timing, and X3 extrinsic/range/frame facts remain `PENDING_MEASUREMENT`. They must not be replaced by sample constants or values from provenance drafts. A compiler must reject these values in a real resolved profile until the applicable measured/approved evidence exists and is pinned. This specification does not assert any measurement, runtime profile, or successful resolution.

## 5. Gate B and implementation boundary

ACR8 requires all six Gate B conditions before a connected/profile-resolving implementation packet may be issued: (1) record approved ACR and update the controlled V3 specification; (2) bind approved QoS identity/manifest, delivery/coalescing/action-bound readiness and `TopicQosContractV3`; (3) define `ObservationInputContractV3` canonical source and compiler/composition validation with no unresolved resolved-config values; (4) add/register receipt message/topic and version/hash checks plus canonical QoS record; (5) define pure-Python typed-snapshot/receipt ingress seams; and (6) independently audit preservation of the 81D layout and process/safety isolation.

This integration-resident candidate does not itself satisfy all six ACR8 Gate B implementation conditions, install/generate the ROSIDL interface, select concrete profile evidence, implement adapters, produce a resolved profile, or pass Gate B. Required contract IDs/digests and source pins not selected by canonical authority remain unresolved; measurement-dependent values remain `PENDING_MEASUREMENT`, and a future compiler must reject the entire resolved config whenever a required pin/evidence/value is unresolved. The candidate proposes that global `ResolvedConfig.config_hash` cover the entire resolved config, including this descriptor, using RFC 8785 JCS UTF-8 bytes and excluding the output hash and prohibited runtime facts; this amendment is not effective until the ACR activation conditions are met. No Gate-B-only hash exists. Any later code work requires a separate exact-scope packet, focused audit, and explicit `CODE_AUTHORIZATION`. ROSIDL, adapter/QoS integration, runtime, HIL, hardware, `deploy_sim`, and `deploy_real` remain outside this governance amendment.

```text
WP-04: BLOCKED_BY_CONTRACT
GATE_A_STRUCTURAL_PRIMITIVES: PASSED
GATE_B: NOT_STARTED
GATE_B_BOUNDARY_CLOSURE: ACTIVE_ON_INTEGRATION
GLOBAL_CONFIG_HASH_PROPOSAL: INTEGRATION_RESIDENT_CANDIDATE_PENDING_ACR_ACTIVATION_CONDITIONS
GLOBAL_CONFIG_HASH_IMPLEMENTATION: PENDING_EXACT_NON_CIRCULAR_RESOLUTION
OBSERVATION_INPUT_PROFILE_SCHEMA: INTEGRATION_RESIDENT_CANDIDATE_PENDING_ACR_ACTIVATION_CONDITIONS
CONCRETE_PROFILE_REFERENCE_PINS: PENDING_ACTIVE_AUTHORITY_AND_EVIDENCE
CODE_AUTHORIZATION: NOT_GRANTED
RUNTIME_APPROVED: NOT_APPROVED
WP-05: OPEN
```
