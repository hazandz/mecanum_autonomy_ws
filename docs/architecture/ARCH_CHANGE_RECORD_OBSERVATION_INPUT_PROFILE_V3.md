# Architecture Change Record: ObservationInputProfileV3

**Record ID:** `ACR-OBSERVATION-INPUT-PROFILE-V3`
**Record revision:** `3` (F-01 exhaustive-root correction; candidate; Owner decisions recorded, activation pending)
**Status:** `CANDIDATE_ONLY_PENDING_FOCUSED_INDEPENDENT_AUDIT_AND_SEPARATE_EXACT_COMMIT_USER_AUTHORIZATION_AND_CANONICAL_INTEGRATION`
**Work package:** `WP04-GATE-B-CONFIG-HASH-EXHAUSTIVE-ROOT-CORRECTION`
**Base:** `origin/integration/implementation@c1187de97c550b9968d88aa6043ed716df981b54`
**Correction source/direct parent:** `wp-04-gate-b-global-config-owner-decision-c1187de@e79a8f6fd6be7b50dbbfe28819a34116ecaec3ab`
**Correction review branch:** `wp-04-gate-b-config-hash-root-correction-c1187de` (candidate only)
**Architecture authority:** `docs/MECANUM_NAV_DRL_Architecture.docx`, SHA-256 `432eeac363a595cfcf7e81c4b66054fb674dba140a2ef3cffecd617ab8136204`, release date 2026-09-16.

The Project Owner/User approved both the global configuration-hash policy and the nested observation-input profile policy as written on 2026-10-12 (`APPROVE_BOTH_AS_WRITTEN`). This records that decision; it does not activate this amendment or grant implementation/runtime authorization. The amendment does not edit or supersede the frozen Architecture. It becomes effective only after this exact candidate passes focused independent audit, receives separate explicit Project Owner/User authorization for its exact commit, is fast-forwarded to `integration/implementation`, and the remote ref is verified. Until then the existing Architecture and active source selections remain controlling. Presence of any source commit in integration ancestry alone does not prove audit, exact-commit authorization, or activation.

The active Gate B boundary-source selection remains Observation V3 Specification revision 1, pinned at `wp-04-gate-b-boundary-closure-decision-50476170@68174e714cbe8aab61880113496cd7ccd7f97f5d`, path `docs/OBSERVATION_V3_SPECIFICATION.md`, SHA-256 `feffb86e335d64a3a3fe0f3a1ce0866f868c8ed56ffa4412db14128c80b284ec`, until the amendment activation conditions above are met. The current path's later revision bytes and this ACR remain candidate-only.

Revision 3 supersedes revision 2 only to correct F-01 by explicitly enumerating
the exhaustive Architecture §4 hash-input root set in §4. It does not change
the approved global hash policy, profile shape, pending pins/measurements,
active-source selection, or any authorization/status boundary.

## 1. Reason for change

Architecture §4 defines the `ResolvedConfig` root and includes `observation: ObservationConfig`; §20 defines the observation layout and says its schema hash covers ordering, LiDAR rules, limits, goal cap, control period, issued-command definition, and normalization. It does not define a static descriptor slot for the Gate-B input contracts. ACR8 §8 requires a canonical `ObservationInputContractV3` source and compiler/composition validation with no unresolved resolved-config values. This amendment proposes the missing static descriptor at `ResolvedConfig.observation.input_profile` without adding a root member or changing the 81D policy observation.

## 2. Proposed Architecture amendment

The Architecture `ResolvedConfig` root-member set remains unchanged. In the existing `ObservationConfig`, add exactly one required nested member:

```text
input_profile: ObservationInputProfileV3
```

No root `gate_b` member is introduced. `ResolvedGateBRecordV3`, if used internally by a compiler or implementation, is not a root canonical member and cannot replace the Architecture `ResolvedConfig` envelope. Its approved content must be represented by `observation.input_profile` and other existing Architecture-owned domains; no second or Gate-B-only config hash is defined.

The candidate nested schema is:

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

This candidate assigns `schema_id="observation-input-profile-v3"` and `schema_revision=1`. Because a required nested member changes the serialized resolved-config schema, the candidate proposes the next compatible resolved-config schema version `3.1` (from Architecture's `3.0`); the root member names and ownership remain unchanged. A missing `observation.input_profile`, an unknown member, an invalid version, or a legacy config without this required member is rejected; no implicit migration, default, alias, or partial resolved config is allowed.

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

The compiler rejects the entire config if any required root domain or profile member is missing, unknown, defaulted, coerced, aliased, unresolved, unsupported by exact authority, or lacks required evidence. It emits neither a partial `ResolvedConfig` nor a partial hash. A required `PENDING_OWNER_DECISION` pin or `PENDING_MEASUREMENT` value makes the dependent profile and entire config ineligible for resolution; no sample value is substituted. The Architecture §4 schema/version impact and migration from the currently specified resolved-config schema are part of this candidate change-control and require audit/activation; no existing config/hash is silently reinterpreted.

Acceptance evidence required before a later implementation candidate is considered includes: (1) a field-by-field projection manifest proving the exact exhaustive root set above and each root's nested fields are covered exactly once, with only the output `config_hash` omitted; (2) RFC 8785 JCS golden vectors pinning canonical UTF-8 bytes and SHA-256 results, including object-key ordering and array-order behavior; (3) rejection vectors for duplicate keys, non-finite values, self-reference, forbidden runtime facts, missing/unknown fields, and unresolved required pins/measurements; and (4) schema-version/migration analysis demonstrating that prior resolved configs and hashes are not silently reinterpreted. These are required future evidence, not evidence produced by this governance candidate.

## 5. Boundaries and status

The adapter remains responsible for verifying ROS message type, QoS, frame, freshness, provenance and lifecycle/barrier facts before producing typed ingress data. The pure core receives only immutable typed snapshots/profile values and does not import ROS, access I/O, read a clock, or inspect repositories. This record does not change receipt v2, QoS6, ACR8, the Gate A schema, or WP-05.

This is an architecture-change candidate, not effective Architecture authority, code authorization, Gate B acceptance, runtime evidence, HIL/hardware authority, or deployment approval.

```text
WP-04: BLOCKED_BY_CONTRACT
GATE_A_STRUCTURAL_PRIMITIVES: PASSED
GATE_B: NOT_STARTED
CODE_AUTHORIZATION: NOT_GRANTED
RUNTIME_APPROVED: NOT_APPROVED
WP-05: OPEN
```
