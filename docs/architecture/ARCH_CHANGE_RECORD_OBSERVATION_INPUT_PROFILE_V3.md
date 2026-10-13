# Architecture Change Record: ObservationInputProfileV3

**Record ID:** `ACR-OBSERVATION-INPUT-PROFILE-V3`
**Record revision:** `7` (L2 typed-boundary amendment candidate; not active before separate activation)
**Status:** `REVISION_3_ACTIVE_TECHNICAL_AUTHORITY; REVISION_7_L2_REVIEW_CANDIDATE_AT_SOURCE_BASE`
**Work package:** `WP04-OBSERVATION-INPUT-CONTRACT-V3-ARCHITECTURE-CLOSURE`
**Activation integration:** `origin/integration/implementation@8c3de26521d7028a933f0a3ebe780fcb372f7a3a`
**Activated ACR revision 3:** `wp-04-gate-b-config-hash-root-correction-c1187de@8c3de26521d7028a933f0a3ebe780fcb372f7a3a`
**Architecture authority:** `docs/MECANUM_NAV_DRL_Architecture.docx`, SHA-256 `432eeac363a595cfcf7e81c4b66054fb674dba140a2ef3cffecd617ab8136204`, release date 2026-09-16.

Revision 5 records the status-reconciliation event already integrated at `3fc3e2e583550b47195720f0de2fda8fbbd7490f`. It does not change the technical semantics, hash policy, exhaustive root set, profile schema, pins, measurements, or authorization boundary of active revision 3. At integration `8c3de26521d7028a933f0a3ebe780fcb372f7a3a`, revision 3 was activated after an exact-candidate audit PASS and separate exact-commit User authorization (both `USER_SUPPLIED_EVIDENCE`), followed by the fast-forward and remote-ref verification (Git-verifiable facts). No audit-report hash is asserted. Commit `3fc3e2e…` is present on the integration line and records that event; its former pre-integration pending wording is historical. The separate review candidate `4a938773cfd8f36cc81934951f4fa02dae99cb05` was reported as audited PASS by the User but was not integrated after a preflight found wording that would remain stale after fast-forward; this audit statement is `USER_SUPPLIED_EVIDENCE`, with no report hash asserted. This record does not amend or supersede the frozen Architecture DOCX and does not grant implementation/runtime authorization.

The activated specification is Observation V3 Specification revision 5 at `docs/OBSERVATION_V3_SPECIFICATION.md`, full-document SHA-256 `4092ee19d48a760b329ff49b9a79e39ab8389ff232aabd5dd06db83f8d83e5a2`, as of integration `8c3de26521d7028a933f0a3ebe780fcb372f7a3a`. Revision 1 was the historical boundary-source selection before activation; revisions 1–4 remain preserved provenance and are not deleted or rewritten.

Revision 3 superseded revision 2 only to correct F-01 by explicitly enumerating
the exhaustive Architecture §4 hash-input root set in §4. It does not change
the approved global hash policy, profile shape, pending pins/measurements,
active-source selection, or any authorization/status boundary.

## 1. Reason for change

Architecture §4 defines the `ResolvedConfig` root and includes `observation: ObservationConfig`; §20 defines the observation layout and says its schema hash covers ordering, LiDAR rules, limits, goal cap, control period, issued-command definition, and normalization. It does not define a static descriptor slot for the Gate-B input contracts. ACR8 §8 requires a canonical `ObservationInputContractV3` source and compiler/composition validation with no unresolved resolved-config values. This activated amendment adds the missing static descriptor at `ResolvedConfig.observation.input_profile` without adding a root member or changing the 81D policy observation.

## 2. Activated Architecture amendment (technical content from revision 3)

The Architecture `ResolvedConfig` root-member set remains unchanged. In the existing `ObservationConfig`, add exactly one required nested member:

```text
input_profile: ObservationInputProfileV3
```

No root `gate_b` member is introduced. `ResolvedGateBRecordV3`, if used internally by a compiler or implementation, is not a root canonical member and cannot replace the Architecture `ResolvedConfig` envelope. Its approved content must be represented by `observation.input_profile` and other existing Architecture-owned domains; no second or Gate-B-only config hash is defined.

The activated nested schema is:

```text
ObservationInputProfileV3(
  *,
  schema_id: str,                         # exact literal "observation-input-profile-v3"
  schema_revision: int,                   # exact built-in int; value 1 for this schema
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

Every listed member is required, keyword-only, exact built-in type, frozen/immutable, and has no default or coercion. Strings are non-empty and compared exactly. `schema_revision` is a positive exact integer. `contract_sha256` and `source_file_sha256` are lowercase 64-hex SHA-256 strings; `commit_sha` is a full lowercase 40-hex Git commit SHA. `source_path` is an exact repository-relative tracked path. A source reference is valid only when the path's bytes at the pinned commit have the stated file SHA. Branches, tags, abbreviations, mutable URLs, aliases, and lookup/fallback resolution are forbidden. Contract digest and source-file digest identify different byte sets and must not be conflated.

These are schema definitions, not selected values for a runnable profile. At this base, the canonical authorities do not provide exact contract IDs/digests for every LiDAR, LocalReference, measured-twist, frame, and lifecycle/reset/barrier contract. Such values remain unresolved until separately selected from an approved immutable source. A profile instance missing any required pin or evidence is not a resolved value. No source value is inferred from OIC rev.6 or any other draft/provenance-only file.

This member is a static configuration descriptor. It contains no ROS/generated message, sensor sample, receipt payload or instance, timestamp, sequence, lifecycle counter/identity, barrier occurrence, freshness result, or other runtime state. Those are runtime facts and are outside the resolved config and its hash.

## 3. Versioning, compatibility, and migration

The activated schema assigns `schema_id="observation-input-profile-v3"` and `schema_revision=1`. Because a required nested member changes the serialized resolved-config schema, the amendment selects the next compatible resolved-config schema version `3.1` (from Architecture's `3.0`); the root member names and ownership remain unchanged. A missing `observation.input_profile`, an unknown member, an invalid version, or a legacy config without this required member is rejected; no implicit migration, default, alias, or partial resolved config is allowed.

Before implementation, the controlled schema and compiler/config input family must be updated under their own exact authorization. Existing V3 config inputs, profiles, compiler output, validation, config-hash vectors, model/checkpoint/run-manifest bindings, and downstream consumers require compatibility analysis and regeneration/revalidation under the new schema. This record makes no claim that such migration has occurred. Historical configurations and hashes are not silently reinterpreted.

## 4. Global configuration hash

`ObservationInputProfileV3` is included in the single global `ResolvedConfig.config_hash`; there is no Gate-B-only digest. The Owner-approved global rule is SHA-256 over RFC 8785 JCS canonical UTF-8 bytes of the fully resolved, validated, static Architecture `ResolvedConfig`, with no BOM and no trailing newline. The exact and exhaustive root-member set of the hash-input projection is:

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

Each listed root must occur exactly once in the object being hashed. This list is exhaustive, not illustrative: no root may be omitted, added, renamed, replaced, or projected separately. `observation.input_profile` is nested within `observation`, not a separate root. The only excluded field is the output `config_hash` itself, which is computed from the listed projection and then stored in the resolved object; no other projection/root exclusion is allowed. The resulting stored `ResolvedConfig` therefore contains the listed roots plus that output field, in accordance with Architecture §4.

The projection is fully resolved and validated before canonicalization. Duplicate JSON keys are rejected before projection creation; parsers must not silently retain one duplicate value. SHA-256 is computed over RFC 8785 JCS UTF-8 bytes, without BOM or trailing newline. Non-finite numbers and runtime-only facts—including timestamps, sensor samples, receipt instances/payloads/sequences, lifecycle identity/counters, barrier occurrences/results, freshness results, and raw ROS objects—are invalid resolved-config inputs and cause rejection; they are not silently filtered. No Gate-B-only hash or subrecord hash substitutes for the global hash.

The compiler rejects the entire config if any required root domain or profile member is missing, unknown, defaulted, coerced, aliased, unresolved, unsupported by exact authority, or lacks required evidence. It emits neither a partial `ResolvedConfig` nor a partial hash. A required `PENDING_OWNER_DECISION` pin or `PENDING_MEASUREMENT` value makes the dependent profile and entire config ineligible for resolution; no sample value is substituted. The Architecture §4 schema/version impact and migration from the previously specified resolved-config schema were recorded in the change-control activated by revision 3; this status record does not claim that implementation migration or its acceptance evidence is complete. No existing config/hash is silently reinterpreted.

Acceptance evidence required before a later implementation candidate is considered includes: (1) a field-by-field projection manifest proving the exact exhaustive root set above and each root's nested fields are covered exactly once, with only the output `config_hash` omitted; (2) RFC 8785 JCS golden vectors pinning canonical UTF-8 bytes and SHA-256 results, including object-key ordering and array-order behavior; (3) rejection vectors for duplicate keys, non-finite values, self-reference, forbidden runtime facts, missing/unknown fields, and unresolved required pins/measurements; and (4) schema-version/migration analysis demonstrating that prior resolved configs and hashes are not silently reinterpreted. These are required future evidence, not evidence produced by this governance candidate.

## 5. Boundaries and status

The adapter remains responsible for verifying ROS message type, QoS, frame, freshness, provenance and lifecycle/barrier facts before producing typed ingress data. The pure core receives only immutable typed snapshots/profile values and does not import ROS, access I/O, read a clock, or inspect repositories. This record does not change receipt v2, QoS6, ACR8, the Gate A schema, or WP-05.

Revision 3 is active change-control at the stated integration, without editing the Architecture DOCX. Revisions 4 and 5 are status/provenance successors only; revision 4's candidate status describes its historical review state before the later reconciliation recorded by revision 5. Neither activation nor these status records constitute code authorization, Gate B acceptance, runtime evidence, HIL/hardware authority, or deployment approval.

```text
WP-04: BLOCKED_BY_CONTRACT
GATE_A_STRUCTURAL_PRIMITIVES: PASSED
GATE_B: NOT_STARTED
CODE_AUTHORIZATION: NOT_GRANTED
RUNTIME_APPROVED: NOT_APPROVED
WP-05: OPEN
```

## 6. Revision 6 — source-parent review snapshot and post-integration target-governance state

This section records the Owner decisions supplied for work package
`WP04-GATE-B-TARGET-CONTRACT-CLOSURE-DECISION` at integration base
`701bb0cc5ca17b71e083d3ce4fdebd2bf46fbcee`. At that source-parent snapshot,
revision 6 was a proposed successor awaiting independent audit PASS, separate User
authorization for its exact commit, fast-forward, and remote-ref verification;
ACR revision 3 and Observation V3 Specification revision 5 remained the active
technical authority. After those conditions are satisfied for the exact
successor and its remote ref is verified, revision 6 is an integration-resident
target-governance record only; it is not active technical semantics and does
not supersede ACR revision 3 or Specification revision 5. This correction
records the two temporal states without inferring audit or authorization from
Git ancestry. No source pin or runtime evidence is inferred from ancestry.

The target decisions refine how an eventual profile is to be interpreted; they
do not populate a profile or select immutable source references:

1. **LiDAR target frame:** the canonical target/TF child is exactly
   `lidar_frame`. The names `RPLiDAR_A1M8_1`, `base_scan`, and namespaced
   variants are not aliases. The profile must pin the actual sensor/frame
   contract and any explicitly authorized transform relationship. No claim is
   made that a runtime `LaserScan.header.frame_id` has been observed or that it
   equals `lidar_frame`.
2. **LocalReference:** Gate B consumes the navigation/global-path reference
   expressed in `base_link`, consistent with Architecture §45. The simulation
   implementation `observations/goal_features.py` is provenance/reference only;
   it is not selected as the Gate B canonical source.
3. **Measured twist:** the semantic source is one fused-odometry publisher
   owned by the EKF, consistent with Architecture §§11 and 41. No operational
   node/config/source pin is selected by this record. The Architecture-defined
   topic contract is not evidence that a concrete runtime publisher/config has
   been immutably pinned or validated.
4. **TF ownership:** the selected localization provider owns `map -> odom`;
   the EKF owns `odom -> base_link`; and the robot description, published by
   `robot_state_publisher`, owns `base_link -> lidar_frame`. The exact profile
   source and physical transform/extrinsic remain unselected/unmeasured.
5. **Lifecycle/reset/action barrier:** preserve the active ACR3/Specification
   lifecycle and fail-closed rules, including epoch/generation compatibility
   and receipt eligibility strictly after the applicable barriers. No new
   immutable lifecycle/reset/barrier policy source is selected here. Runtime
   lifecycle values and barrier occurrences remain runtime facts, not static
   profile/config-hash values.

Receipt v2 and QoS6 remain established canonical pins and are not reclassified
as pending. The existing pins are receipt interface
`mecanum.final-issued-receipt/v2`, schema revision 2, at
`ros2_ws/src/mecanum_nav_rl_interfaces/msg/FinalIssuedCommandReceipt.msg`
(SHA-256 `0c6446674bf17373ec646519043f506a9a7a15f95d5fdd10829b0cedb956500a`),
dependency-closure manifest v1 (SHA-256
`0872fa8c10179f69c2e9e9546392ac734a4f4e94ade176a8be431f06905ecf73`), and
QoS6 transport ID `mecanum.final-issued-receipt-topic-qos/v2` with manifest
SHA-256 `338bea1b7350d3b82146c7e728516ec7947471ee68db0f8871ddb72071b79620`
and full-document SHA-256
`4200cd2fbdc81a19400f168dd3526eb7871ac2251049fc7c4f5d5c2fddfd2022`.
These remain pins only; this candidate performs no ROSIDL or runtime check.

The following six profile reference groups remain without a selected immutable
source contract and therefore remain `PENDING_OWNER_SOURCE_SELECTION`: LiDAR
snapshot; navigation/global-path LocalReference; measured-twist snapshot;
frame/geometry source; lifecycle/reset/action-barrier policy; and the concrete
profile source. Existing source files, including the approved V3 input family,
are not canonical profile references solely because they exist. In particular,
`ros2_ws/src/mecanum_nav_rl/config/v3/frames.yaml` does not by itself provide
the required selected contract identity/digest and immutable profile reference.

Physical LiDAR geometry/extrinsic and all applicable timing, freshness, skew,
timeout, buffer, sensor, or measured-twist values that authority requires but
which are not yet measured remain `PENDING_MEASUREMENT`. No ID, digest, source
SHA, topic alias, default, package version, measurement, or profile value is
created by this candidate. The active global configuration-hash policy remains
unchanged: a required unresolved pin/evidence/measurement rejects the entire
resolved config, with no partial profile or hash; runtime facts are invalid
resolved-config inputs and are rejected rather than silently filtered.

The source and measurement gaps above prevent a resolved
`ObservationInputProfileV3` and keep Gate B `NOT_STARTED`. This candidate does
not pass Gate B, close WP-04, change WP-05, grant `CODE_AUTHORIZATION`, or grant
runtime/HIL/hardware/deployment approval.

## 7. Revision 7 — L2 Observation Input Contract V3 typed-boundary amendment

### 7.1 Lifecycle and authority boundary

At exact source base `5497b7e1938242422594f8150b06a32fe221ee70`, this revision-7 amendment and its companion contract, semantic manifest, decision, Registry, PEP, and Ledger updates are review-candidate snapshots. They do not alter active authority. If this exact candidate receives independent audit PASS, separate exact-commit User authorization, fast-forward, and remote-ref verification, it becomes an integration-resident L2 target-governance record. Integration alone does not activate these technical semantics: ACR revision 3 and Observation V3 Specification revision 5 remain active technical authority until a separate activation/change-control explicitly supersedes them. This document does not assert audit or authorization from Git ancestry.

### 7.2 Owner-approved abstract contracts

The Owner-approved L2 decision records five abstract contract identities, each at revision `v3`:

| Contract ID | Scope |
|---|---|
| `mecanum.observation.lidar-snapshot/v3` | Raw angular LiDAR snapshot before sectorization; canonical target `lidar_frame`; exactly 72 finite sector outputs. |
| `mecanum.observation.local-reference/v3` | Navigation/global-path LocalReference in `base_link`; exact features `distance`, `sin_bearing`, `cos_bearing`. |
| `mecanum.observation.measured-twist/v3` | Base-frame measured twist `[vx, vy, wz]`; target semantic owner is one EKF fused-odometry publisher. |
| `mecanum.observation.frame-tf-binding/v3` | Target TF ownership and separately evidenced runtime transform binding. |
| `mecanum.observation.lifecycle-barrier/v3` | Exact lifecycle/config identity and receipt admission after action/reset barriers and before cutoff. |

The canonical semantic manifest is `docs/architecture/OBSERVATION_INPUT_CONTRACT_V3_SEMANTIC_MANIFEST.json`; its semantic-manifest SHA-256 is `175a1af789b6641cfe455daeee8fedac80aaf80ad8c00792ba0a287c41acc0bb`. That digest covers the complete canonical manifest bytes. It is distinct from the source-file SHA-256 of the manifest and from the source-file SHA-256 of `docs/OBSERVATION_INPUT_CONTRACT_V3.md`; no source-file hash is embedded in, or substituted for, the semantic digest. No per-contract digest is invented.

The companion contract document's source-file SHA-256 at this candidate content is `d44d33843c32d1f0d5c747522f3add09bfde21fcb0884e21da93a52476cb4dfc`. This is a source-byte digest, not a semantic-manifest digest or a Git commit pin. The canonical manifest file's source-byte SHA-256 is `175a1af789b6641cfe455daeee8fedac80aaf80ad8c00792ba0a287c41acc0bb`; it equals its semantic-manifest digest here because the file bytes are exactly the canonical JCS payload, but the identifiers name distinct evidence roles.

The abstract typed boundary, shared identity, requiredness, ownership, invariants, runtime evidence boundary, and fail-closed behavior are specified in the companion contract document. All four observation inputs and the final-issued receipt ingress context must match exactly on `episode_generation`, `reset_epoch`, `runtime_generation`, and the global `config_hash`. Receipt v2 remains unchanged and has no `config_hash` field; the companion contract does not add one or define a message wrapper. Any external ingress binding is future separately authorized implementation work. A missing, mismatched, stale, aliased, defaulted, coerced, partially matching, or unverifiable required input is rejected and produces no observation vector.

This amendment records target ownership, not evidence of runtime ownership: localization owns `map -> odom`, EKF owns `odom -> base_link`, and robot description/`robot_state_publisher` owns `base_link -> lidar_frame`. `SafetyLifecycle` remains sole owner of action/reset barriers. Receipt v2 and QoS6 established pins remain unchanged.

### 7.3 Compatibility and unresolved evidence

This is an abstract L2 contract record only. It does not select a ROS interface/message type, topic, publisher node/config, package version, source file, concrete profile source, contract-source pin, geometry, timeout, default, alias, measurement, or runtime fact. LiDAR range/timing/extrinsic, cadence/latency/freshness/skew/timeout/buffer, LocalReference provider and transform, measured-twist topic/type/covariance/validity/freshness/provenance, TF alignment/publisher uniqueness, lifecycle policy source, receipt-after-barrier timeout, and all other applicable measurement evidence remain pending. The six profile-reference groups remain without concrete immutable source selection. No `ObservationInputProfileV3` instance is resolved.

The active global Architecture `ResolvedConfig` 16-root hash policy, RFC 8785 JCS semantics, nested `observation.input_profile` location, and full-config fail-closed rule are unchanged. There is no root `gate_b`, Gate-B-only hash, or partial profile/hash. Runtime timestamps, sensor samples, receipt instances/payloads/sequences, lifecycle values, barrier occurrences, freshness results, raw ROS objects, and runtime observations are invalid static-config/hash inputs. Missing or unverifiable required pins/evidence or required `PENDING_MEASUREMENT` values reject the entire resolved config.

After a future separate activation/change-control, migration and acceptance work must assess existing configs, compiler/core/adapter boundaries, source bindings, rejection behavior, preservation of the 81D observation, and simulator/runtime separation. This candidate does not claim that migration, code, tests, ROSIDL, adapter/QoS integration, runtime, HIL, hardware, or deployment evidence exists. Gate B remains `NOT_STARTED`; WP-04 remains `BLOCKED_BY_CONTRACT`; no code or runtime authorization is granted.
