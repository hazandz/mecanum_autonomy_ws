# Architecture Change Record: ObservationInputProfileV3

**Record ID:** `ACR-OBSERVATION-INPUT-PROFILE-V3`
**Record revision:** `4` (activation/status reconciliation successor; status/provenance only)
**Status:** `REVISION_3_ACTIVATED_AT_INTEGRATION_8C3DE; REVISION_4_STATUS_RECONCILIATION_CANDIDATE_ONLY`
**Work package:** `WP04-ACR-REV3-ACTIVATION-STATUS-RECONCILIATION`
**Activation integration:** `origin/integration/implementation@8c3de26521d7028a933f0a3ebe780fcb372f7a3a`
**Activated ACR revision 3:** `wp-04-gate-b-config-hash-root-correction-c1187de@8c3de26521d7028a933f0a3ebe780fcb372f7a3a`
**Architecture authority:** `docs/MECANUM_NAV_DRL_Architecture.docx`, SHA-256 `432eeac363a595cfcf7e81c4b66054fb674dba140a2ef3cffecd617ab8136204`, release date 2026-09-16.

Revision 4 records activation/status history only; it does not change the technical semantics, hash policy, exhaustive root set, profile schema, pins, measurements, or authorization boundary of revision 3. At integration `8c3de26521d7028a933f0a3ebe780fcb372f7a3a`, revision 3 was activated after an exact-candidate audit PASS and separate exact-commit User authorization (both `USER_SUPPLIED_EVIDENCE`), followed by the fast-forward and remote-ref verification (Git-verifiable facts). No audit-report hash is asserted. This record does not amend or supersede the frozen Architecture DOCX and does not grant implementation/runtime authorization. This successor is a status/provenance candidate; its own integration is not required to repeat or re-activate revision 3.

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

The compiler rejects the entire config if any required root domain or profile member is missing, unknown, defaulted, coerced, aliased, unresolved, unsupported by exact authority, or lacks required evidence. It emits neither a partial `ResolvedConfig` nor a partial hash. A required `PENDING_OWNER_DECISION` pin or `PENDING_MEASUREMENT` value makes the dependent profile and entire config ineligible for resolution; no sample value is substituted. The Architecture §4 schema/version impact and migration from the currently specified resolved-config schema are part of this candidate change-control and require audit/activation; no existing config/hash is silently reinterpreted.

Acceptance evidence required before a later implementation candidate is considered includes: (1) a field-by-field projection manifest proving the exact exhaustive root set above and each root's nested fields are covered exactly once, with only the output `config_hash` omitted; (2) RFC 8785 JCS golden vectors pinning canonical UTF-8 bytes and SHA-256 results, including object-key ordering and array-order behavior; (3) rejection vectors for duplicate keys, non-finite values, self-reference, forbidden runtime facts, missing/unknown fields, and unresolved required pins/measurements; and (4) schema-version/migration analysis demonstrating that prior resolved configs and hashes are not silently reinterpreted. These are required future evidence, not evidence produced by this governance candidate.

## 5. Boundaries and status

The adapter remains responsible for verifying ROS message type, QoS, frame, freshness, provenance and lifecycle/barrier facts before producing typed ingress data. The pure core receives only immutable typed snapshots/profile values and does not import ROS, access I/O, read a clock, or inspect repositories. This record does not change receipt v2, QoS6, ACR8, the Gate A schema, or WP-05.

Revision 3 is activated change-control at the stated integration, without editing the Architecture DOCX. This revision-4 status reconciliation remains a candidate governance successor and is not a new technical amendment. Neither activation nor this record constitutes code authorization, Gate B acceptance, runtime evidence, HIL/hardware authority, or deployment approval.

```text
WP-04: BLOCKED_BY_CONTRACT
GATE_A_STRUCTURAL_PRIMITIVES: PASSED
GATE_B: NOT_STARTED
CODE_AUTHORIZATION: NOT_GRANTED
RUNTIME_APPROVED: NOT_APPROVED
WP-05: OPEN
```
