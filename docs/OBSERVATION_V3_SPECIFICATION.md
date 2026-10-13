# Observation V3 Specification

**Revision:** `9` (L2 typed-boundary review snapshot at source base; separate activation required)
**Status:** `REVISION_5_ACTIVE_TECHNICAL_SPECIFICATION; REVISION_9_L2_REVIEW_SNAPSHOT_AT_SOURCE_BASE_NOT_ACTIVE`
**Work package:** `WP04-OBSERVATION-INPUT-CONTRACT-V3-ARCHITECTURE-CLOSURE`
**Activation integration:** `origin/integration/implementation@8c3de26521d7028a933f0a3ebe780fcb372f7a3a`; activated revision-5 bytes SHA-256 `4092ee19d48a760b329ff49b9a79e39ab8389ff232aabd5dd06db83f8d83e5a2`
**Runtime status:** `RUNTIME_NOT_APPROVED`

Revision 7 records that status-reconciliation commit `3fc3e2e583550b47195720f0de2fda8fbbd7490f` is integrated. The exact Specification revision 5 bytes (SHA-256 `4092ee19d48a760b329ff49b9a79e39ab8389ff232aabd5dd06db83f8d83e5a2`) remain the technical specification activated by ACR revision 3 at integration `8c3de26521d7028a933f0a3ebe780fcb372f7a3a`. The exact-candidate audit PASS and separate User authorization for that activation are `USER_SUPPLIED_EVIDENCE`; fast-forward and remote-ref verification are Git-verifiable facts. No audit-report hash is asserted. Revision 7 changes status/provenance wording only and does not change technical contract semantics, pass Gate B, close WP-04, implement an adapter, or authorize code/runtime. The prior revision-6 wording that described its review state as pending is historical pre-integration wording; revision 6 was not integrated.

## Historical source selection before ACR revision-3 activation

Before ACR revision-3 activation at integration `8c3de26521d7028a933f0a3ebe780fcb372f7a3a`, revision 1 was the selected Gate B boundary source, pinned by `wp-04-gate-b-boundary-closure-decision-50476170@68174e714cbe8aab61880113496cd7ccd7f97f5d`, SHA-256 `feffb86e335d64a3a3fe0f3a1ce0866f868c8ed56ffa4412db14128c80b284ec`. Revisions 1–4 remain historical provenance; revision 5 is the exact specification activated by ACR revision 3. This history selects no additional concrete profile pin, does not pass Gate B, and grants no implementation or runtime authority.

## 1. Authority and exact pins

The governing architecture remains `docs/MECANUM_NAV_DRL_Architecture.docx`. The active Observation V3 technical authority is ACR revision 3 and Observation V3 Specification revision 5, activated at the integration identified above. Receipt Topic QoS Contract revision 6 remains its separately approved receipt/QoS authority. Revision 8 in this document is a target-governance record only; it does not become active technical semantics or supersede revision 5 when integrated.

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

The approved receipt v2 bytes remain unchanged. The `ResolvedConfig` root remains exactly the Architecture root envelope: no root `gate_b` member is added. The active location for Gate-B static binding is the versioned nested member `observation.input_profile: ObservationInputProfileV3`. `ResolvedGateBRecordV3`, if used internally by a future compiler, is only an internal type abstraction; it is not a canonical root member and serializes only into the approved nested representation.

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

The activated amendment records the Owner-approved required nested member with schema identity `observation-input-profile-v3`, revision `1`, and the exact member set below. The member is a static immutable descriptor, not runtime state. Activation does not resolve missing concrete pins or measurements.

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

The required contract IDs, semantic contract digests and profile source for a concrete instance are not populated unless selected by active authority. At this integration base, some snapshot/policy contracts lack their own canonical IDs/digests. Those values remain `PENDING_OWNER_DECISION`; the type definition does not invent them or make a profile instance valid. A profile missing any pin/evidence is not resolved and must be rejected as part of the whole config.

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

This status/provenance record does not satisfy all six ACR8 Gate B implementation conditions, install/generate the ROSIDL interface, select concrete profile evidence, implement adapters, produce a resolved profile, or pass Gate B. Required contract IDs/digests and source pins not selected by canonical authority remain `PENDING_OWNER_DECISION`; measurement-dependent values remain `PENDING_MEASUREMENT`. A future compiler must reject the entire resolved config and emit no partial hash whenever a required pin/evidence/value is unresolved. ACR revision 3 activation does not establish concrete profile pins. Any later code work requires a separate exact-scope packet, focused audit, and explicit `CODE_AUTHORIZATION`. ROSIDL, adapter/QoS integration, runtime, HIL, hardware, `deploy_sim`, and `deploy_real` remain outside this governance status reconciliation.

### 5.1 Global `ResolvedConfig.config_hash` decision

The Owner-approved global hash is SHA-256 of RFC 8785 JCS canonical UTF-8
bytes for the complete resolved and validated static Architecture
`ResolvedConfig`, with no BOM and no trailing newline. Exactly the output
`config_hash` field is omitted from the serialized payload to avoid
self-reference. The exact and exhaustive root-member set of the hash-input
projection is:

```text
schema_version
runtime_profile
navigation_mode
project
topics
frames
state_estimation
localization
navigation
observation
action
reward
training
evaluation
safety
acceptance
```

Each listed root must occur exactly once in the object being hashed. This list
is exhaustive, not illustrative: no root may be omitted, added, renamed,
replaced, or projected separately. `observation.input_profile` is nested
inside `observation`, not a separate root. The only excluded field is the
output `config_hash` itself, computed from the listed projection and then
stored in the resolved object. The stored `ResolvedConfig` therefore contains
the listed roots plus that output field, consistent with Architecture §4.

The projection is fully resolved and validated before canonicalization.
Duplicate JSON keys are rejected before projection creation; a parser must not
silently retain one duplicate value. SHA-256 is computed over RFC 8785 JCS
UTF-8 bytes, without BOM or trailing newline. Non-finite numbers and runtime-only
facts—including timestamps, sensor samples, raw ROS/receipt objects and
payloads, sequence values, lifecycle identity/counters, barrier occurrences
or results, and freshness results—are invalid resolved-config inputs and cause
rejection; they are not silently filtered. No Gate-B-only hash or subrecord
hash is defined. RFC 8785 is recorded as a change-controlled refinement of
Architecture §4, not inferred from the map-manifest hash rule in §48.

Missing/unknown/defaulted/coerced/aliased/unresolved required fields, missing
authority/evidence pins, or required `PENDING_OWNER_DECISION` /
`PENDING_MEASUREMENT` values reject the entire resolved config. The compiler
does not emit a partial config or hash. This is active specification/change-
control content under ACR revision 3, not implementation evidence.

```text
WP-04: BLOCKED_BY_CONTRACT
GATE_A_STRUCTURAL_PRIMITIVES: PASSED
GATE_B: NOT_STARTED
GATE_B_BOUNDARY_CLOSURE: ACTIVE_ON_INTEGRATION
OWNER_DECISIONS: APPROVE_BOTH_AS_WRITTEN
GLOBAL_CONFIG_HASH_POLICY: ACTIVE_UNDER_ACR_REVISION_3_AT_INTEGRATION_8C3DE
GLOBAL_CONFIG_HASH_IMPLEMENTATION: NOT_IMPLEMENTED
OBSERVATION_INPUT_PROFILE_SCHEMA: ACTIVE_UNDER_ACR_REVISION_3_AT_INTEGRATION_8C3DE
CONCRETE_PROFILE_REFERENCE_PINS: PENDING_ACTIVE_AUTHORITY_AND_EVIDENCE
CODE_AUTHORIZATION: NOT_GRANTED
RUNTIME_APPROVED: NOT_APPROVED
WP-05: OPEN
```

## 6. Revision 8 — source-parent review snapshot and post-integration target-governance state

This section records the Owner target-contract decisions supplied for
`WP04-GATE-B-TARGET-CONTRACT-CLOSURE-DECISION` at source-parent base
`701bb0cc5ca17b71e083d3ce4fdebd2bf46fbcee`. At that snapshot, this successor
was awaiting independent audit PASS, separate User authorization for its exact
commit, fast-forward, and remote-ref verification; ACR revision 3 and
Specification revision 5 remained active technical authority. After those
conditions are satisfied for the exact successor and its remote ref is
verified, revision 8 is an integration-resident target-governance record only.
It is not active technical semantics and does not supersede Specification
revision 5. This section does not instantiate or resolve
`ObservationInputProfileV3`.

The required static profile member set and strict value semantics remain exactly
those in active §3.1 and ACR revision 3. These target decisions do not add
profile fields, change the exhaustive 16-root global hash projection, alter
RFC 8785 JCS behavior, add a Gate-B-only hash, or permit runtime facts in static
configuration. The entire resolved config continues to fail closed without a
partial profile/hash when a required pin/evidence/value is unresolved; runtime
facts are invalid config inputs, not values to silently filter.

### 6.1 Owner-selected target contract semantics

- **LiDAR frame target:** the canonical target/TF child is exactly
  `lidar_frame`. `RPLiDAR_A1M8_1`, `base_scan`, and namespaced variants are not
  aliases. The concrete sensor source, its exact input frame, and any explicit
  transform relationship require an immutable selected frame/source contract.
  No runtime `LaserScan.header.frame_id` is asserted by this document.
- **LocalReference:** Gate B's LocalReference is the navigation/global-path
  reference expressed in `base_link`, consistent with Architecture §45. The
  simulation-only `observations/goal_features.py` is provenance/reference, not
  the Gate B canonical source.
- **Measured twist:** the target source is a single fused-odometry publisher
  owned by the EKF, consistent with Architecture §§11 and 41. The operational
  publisher/config/source has not been immutably selected. No new topic alias or
  runtime publisher claim is made.
- **TF ownership:** the selected localization provider owns `map -> odom`; the
  EKF owns `odom -> base_link`; robot description/`robot_state_publisher` owns
  `base_link -> lidar_frame`. This does not select a profile-specific source or
  establish physical geometry. LiDAR geometry/extrinsic remains
  `PENDING_MEASUREMENT`.
- **Lifecycle/reset/action barrier:** the active lifecycle tuple, epoch/
  generation compatibility, receipt-after-barrier ordering, and fail-closed
  rules remain controlling. No immutable lifecycle/reset/action-barrier policy
  source is selected here; observed lifecycle values and barrier occurrences
  remain runtime facts.

Receipt v2 and QoS6 canonical pins remain established as listed in §1 and are
not pending. Their established IDs, revisions, bytes, dependency closure, and
transport manifest are unchanged; this candidate does not claim ROSIDL
generation or runtime QoS compatibility evidence.

### 6.2 Source-selection and evidence boundary

The six groups without a selected immutable profile-reference source remain
`PENDING_OWNER_SOURCE_SELECTION`: LiDAR snapshot; navigation/global-path
LocalReference; measured-twist snapshot; frame/geometry source;
lifecycle/reset/action-barrier policy; and concrete profile source. The
existence of a source file or its inclusion in the V3 input family does not
make it a canonical profile pin. OIC revision 6, review candidates, and drafts
remain provenance-only and cannot supply fields, defaults, IDs, or digests.

All applicable but unmeasured LiDAR geometry/extrinsic and timing, freshness,
skew, timeout, buffer, sensor, and measured-twist values remain
`PENDING_MEASUREMENT`. No source SHA, contract ID/digest, topic/config pin,
default, alias, package version, or measurement is invented here. Once a
required source is selected by authority, its exact identity/revision, immutable
commit/path, source-file digest, and distinct semantic contract digest must be
verified; a missing or unverifiable required reference continues to reject
the whole resolved configuration with no partial hash.

At the source-parent snapshot, this specification revision was a review
candidate. After the exact successor is audited, separately authorized,
fast-forwarded, and its remote ref verified, revision 8 is an integration-resident
target-governance record only; it does not become active technical semantics.
It records no resolved profile, no Gate B start/pass, no WP-04 closure, and no
code/runtime/HIL/hardware/deployment authorization. WP-05 and its
artifact/status are unchanged.

## 7. Revision 9 — proposed L2 Observation Input Contract V3 boundary

This section and companion `docs/OBSERVATION_INPUT_CONTRACT_V3.md` / semantic manifest are a review-candidate snapshot at exact source base `5497b7e1938242422594f8150b06a32fe221ee70`. After audit PASS, separate exact-commit User authorization, fast-forward, and remote-ref verification, these records are integration-resident L2 target-governance records only. They do not activate new technical semantics. ACR revision 3 and Specification revision 5 remain active technical authority until a separate activation/change-control explicitly supersedes them. This lifecycle wording does not infer audit or authorization from ancestry.

The semantic-manifest SHA-256 is `175a1af789b6641cfe455daeee8fedac80aaf80ad8c00792ba0a287c41acc0bb`; it hashes the complete RFC 8785 JCS semantic manifest, not the companion contract document's source-file bytes. The companion document source-file SHA-256 at this candidate content is `d05fa5365d25116e061f39f58e3c159eb31cae31d417fb366ef172383c74aa65`. The manifest source-file digest has the same value as its semantic digest because its exact file bytes are the canonical JCS payload; these remain distinct evidence roles. The five revision-`v3` contract identities are:

- `mecanum.observation.lidar-snapshot/v3`
- `mecanum.observation.local-reference/v3`
- `mecanum.observation.measured-twist/v3`
- `mecanum.observation.frame-tf-binding/v3`
- `mecanum.observation.lifecycle-barrier/v3`

The companion contract defines the abstract typed boundary and fail-closed semantics. All runtime snapshots and the final-issued receipt ingress context require exact atomic match on `episode_generation`, `reset_epoch`, `runtime_generation`, and the global `config_hash`. Receipt v2 is unchanged and has no `config_hash` message field; no receipt field or ROS interface is added here. The contract does not select concrete source files, ROS types/topics/publishers, package versions, profile pins, geometry, timing values, or measurements. `lidar_frame` is the exact target with no inferred alias; LiDAR is raw angular input before sectorization and yields 72 finite sectors. LocalReference is the navigation/global-path value in `base_link` with `distance`, `sin_bearing`, `cos_bearing`; measured twist is `[vx, vy, wz]` with EKF as target owner; TF ownership and SafetyLifecycle barrier ownership are as recorded in the companion contract. These are target semantics, not runtime evidence.

The six concrete profile-reference groups and applicable measurement/evidence remain unresolved. No `ObservationInputProfileV3` instance is resolved. Required missing or unverifiable pin/evidence or a required `PENDING_MEASUREMENT` continues to reject the entire resolved configuration without partial profile/hash. The active Architecture 16-root global `ResolvedConfig.config_hash` policy, RFC 8785 behavior, nested `observation.input_profile`, and no-root-`gate_b` boundary are unchanged. Runtime facts remain invalid static config/hash inputs and are rejected, not filtered.

These target contracts require later migration and acceptance evidence before implementation is considered. This candidate does not implement core, compiler, adapter, ROSIDL, tests, runtime, HIL, hardware, or deployment. Gate B remains `NOT_STARTED`; WP-04 remains `BLOCKED_BY_CONTRACT`; WP-05 remains `OPEN`; no code/runtime authorization is granted.
