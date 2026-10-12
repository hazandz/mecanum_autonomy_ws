# ACR: Canonical Static-Map Artifact Schema and Activation

**ACR ID:** ACR_MAP_ARTIFACT_SCHEMA_AND_ACTIVATION
**Status:** ACTIVE_ON_INTEGRATION; this candidate's narrow clarifications remain pending integration
**Work package:** WP-05-WAREHOUSE-MAP2-CANONICAL-DRAFT-ARTIFACT
**Integration base:** 68174e714cbe8aab61880113496cd7ccd7f97f5d
**Candidate branch:** wp-05-warehouse-map2-canonical-draft-68174e

## 1. Decision, provenance, and scope

This candidate records the nine metadata decision groups as USER_SUPPLIED_DECISION, as stated by the Project Owner/User for this work package. It records Option A for supersession: approved metadata, artifact bytes, and approval evidence remain immutable; supersession is recorded in an append-only event/index. Conversation-supplied audit or User-authorization claims remain USER_SUPPLIED; no audit-report hash is asserted.

Source decision packet: branch wp-05-map-metadata-source-traceability-correction-4b21343, commit 361966ececc3c0fde088bffe5ec2987af8f16014, path docs/WP-05_MAP_METADATA_SCHEMA_CLOSURE_DECISION_PACKET_DRAFT.md, SHA-256 9bd7c06683299d36b11ffebb0db372f67e24257ab9a2ebb0cc193ee18bb35bd4. This provenance does not activate this schema.

Source content provenance: prior candidate `wp-05-unified-map-metadata-schema-change-control-7f9ed36@3892edf37ab5388fd38d3cf4a41d28ae2401782e` (parent `7f9ed36a10b5f4ab68eb437833f04d4842eff986`), now stale on this base. Its content is carried forward only; no audit or authorization is transferred. Exact source-file digests are recorded in the decision record.

The candidate-only wording in the integrated source commit described the pre-activation state. USER_SUPPLIED_EVIDENCE: the Project Owner/User supplied a focused consolidated audit verdict of READINESS_FOR_USER_DECISION_TO_INTEGRATE: PASS and authorized the fast-forward of this exact commit. Git-verifiable evidence confirms commit d33b93d3c6389872450f1a001e3073c61f355824, with sole parent 793514f8ff3c20c13bfe84bf0529295de4d4d0b4, is present at the verified remote integration ref. Accordingly, this schema is ACTIVE_ON_INTEGRATION effective from d33b93d3c6389872450f1a001e3073c61f355824. No audit-report hash is asserted. This activation selects no map source, map_id, actor identity, world/frame equivalence, runtime-compatibility evidence, or map instance, and does not authorize code, ROS/runtime, HIL, hardware, motor operation, deploy_sim, or deploy_real. WP-05 remains open.

Historical refresh provenance: `wp-05-map-metadata-schema-activation-status-refresh-572da88` was based on `572da885d31d98929a1f8b8af4420012f1786fd6`; that base is historical and is neither the current integration baseline nor the current WP-05 candidate. Integration later advanced through WP-04 commits `d87b5a17ca0e9430d0b163aacf5b9cfcc4458d14` and `0b2fcd1d010bc30f54d7621e6192dd76339df6b2`. Review candidate `wp-05-world-frame-evidence-registry-reconciliation-e89aeda5@0f42f1c9da00725c36500ff4ec1d2f75a0c8709a`, parent `e89aeda5ca78859bfeedac4e7b94bcd6c7dcc7f0`, was pushed to its remote review branch; its `CORRECTION_REQUIRED` audit verdict is USER_SUPPLIED_EVIDENCE. It was not integrated. Current replacement candidate: `wp-05-world-frame-evidence-governance-correction-0b2fcd1`, based on `0b2fcd1d010bc30f54d7621e6192dd76339df6b2`, pending its own consolidated independent audit, separate exact-commit User authorization, fast-forward, and remote-ref verification. Metadata-schema activation from d33b93d remains unchanged.

The schema integrated at `d33b93d3c6389872450f1a001e3073c61f355824` remains active. This candidate proposes only the following Owner-approved, narrowly scoped clarifications for the `warehouse_map2` draft: `provenance_kind` v1 is exactly `git_source`; principal text uses `github:<lowercase-login>`; and the selected source YAML may receive only the exact `image` reference rewrite recorded in the decision record. These additions are candidate-only until this exact candidate passes independent audit, receives separate User authorization for integration, is fast-forwarded, and the remote integration ref is verified.

## 2. Identity and immutability

The canonical root remains artifacts/maps/<map_id>/. map_id must match ^[a-z][a-z0-9_]{0,63}$, equal the containing directory name exactly, and be unique case-insensitively under artifacts/maps/. Collision is rejected; validators do not rename IDs.

artifact_identity is a UUID string unique across map artifacts; v1 has no artifact_version field. The proposed accepted spelling is canonical lowercase UUID text with a valid RFC 9562 version and variant. A meaningful content or provenance change creates a new identity and directory. Approved artifact bytes and approval evidence are never overwritten.

## 3. metadata.yaml — mecanum_map_metadata/v1

### 3.1 Parser

metadata.yaml is UTF-8 without BOM and exactly one YAML 1.2 document. The data model is mappings with string keys, sequences, strings, and explicit null only at the nullable paths below. Boolean and floating-point scalars are forbidden. No metadata field in v1 accepts an integer. Reject malformed UTF-8/YAML, duplicate keys, aliases/anchors, tags, merge keys, multiple documents, directives, unknown fields, unknown enum values, and implicit scalar coercion. Mapping-key order has no meaning; sequence order is retained. Metadata has no canonical serialization rule and remains outside map_content_hash.

The accepted prior parser recommendation requires fixed ASCII schema keys, double-quoted string values with restricted JSON-compatible escapes, NFC Unicode, no control characters, and no plain, single-quoted, literal, or folded string scalars. The only null token is null; alternate null spellings and empty scalars are rejected. Integer lexical form, if encountered, is 0 or -?[1-9][0-9]*, but all integer leaves are rejected in metadata v1.

Missing and null are distinct. Required non-null keys cannot be omitted or null. Explicit null is allowed only for: direct-holder actor delegation_evidence; approver and approval_evidence in draft or pending_review; world_frame.evidence_ref in NOT_DECLARED; runtime_compatibility.evidence_ref in NOT_VALIDATED; and history.predecessor_ref for the first identity. raw_sha256 is omitted until computed and is never null. All other keys are required and non-null unless a state rule says otherwise.

### 3.2 Exact top-level fields

The top-level mapping has exactly these required keys:

- schema: string exactly mecanum_map_metadata/v1.
- map_id: string validated by §2 and equal to the directory name.
- artifact_identity: canonical lowercase UUID string, unique across map artifacts.
- classification: string exactly static_occupancy_map.
- source_provenance: sequence of at least one record.
- custody_approval: mapping in §3.5.
- world_frame: mapping in §3.6.
- runtime_compatibility: mapping in §3.7.
- history: mapping in §3.8.

Unknown keys at every level are rejected.

### 3.3 Source provenance

Each source_provenance record has exactly source_ref, evidence_ref, provenance_kind, and conditionally raw_sha256.

source_ref is a mapping with exactly kind, repository, commit, path. For a Git source, kind is git_file; repository is a canonical repository URI; commit is the full Git object ID, never a branch or tag; path is repository-relative and rejects absolute paths, .., backslash, empty components, and symlinks. evidence_ref is the same Git locator plus sha256, exactly 64 lowercase hex; validation resolves commit/path and recomputes SHA-256 over referenced bytes. External evidence references are not accepted by the Git-only v1 evidence validator.

The candidate clarification sets the complete `provenance_kind` v1 enum to exactly `git_source`. It denotes a source file pinned by an immutable Git commit/path and verified SHA-256. `USER_ATTESTED` and `EXTERNAL_SOURCE` are not accepted in v1. Git provenance does not mean User attestation, approval, world/frame validation, or runtime compatibility. This clarification is candidate-only pending the activation conditions in §5.

raw_sha256 is optional, lowercase 64-hex SHA-256 of source raw bytes. Omit before computation; if present, recompute from exact source bytes and require a match. source_provenance order is primary source first, then supporting or derived records in declared order. Duplicate source_ref locators are rejected.

### 3.4 Immutable references and evidence

A Git evidence reference has exactly kind=git_file, repository:string, commit:full commit object ID, path:repository-relative string, sha256:lowercase 64-hex. Immutability is checked by resolving the exact commit/path and recomputing the digest. Branch/tag-only references are invalid. A Git pin or USER_ATTESTED label does not prove an approval, world/frame validation, or runtime compatibility.

Referenced approval, delegation, world/frame, and runtime evidence must identify its subject and decision in immutable bytes. Exact evidence-document schemas, timestamp format, principal-authentication method, and external evidence policy are PENDING_OWNER_DECISION.

### 3.4.1 `DECLARED_UNVERIFIED` source-world declaration evidence — candidate addition

This replacement candidate proposes adding the following narrow record shape. It is not effective until this exact candidate is audited, separately authorized, integrated, and its remote ref verified.

For a map whose `world_frame.state` is `DECLARED_UNVERIFIED`, the `metadata.yaml` `world_frame.evidence_ref` SHALL be an immutable Git reference to a `mecanum_map_world_frame_declaration_evidence/v1` JSON record. The record MUST be UTF-8 without BOM, serialized as RFC 8785 JCS bytes with no trailing newline, and MUST NOT contain a self-digest or signature. Reject malformed JSON, duplicate object keys, non-finite values, unknown or missing keys, wrong types, invalid UTF-8/BOM, and any byte sequence that is not exactly the RFC 8785 serialization of the parsed value.

The top-level object has exactly these required keys: `schema`, `subject`, `declaration`, `source_world`, `decision_provenance`, `limitations`. `schema` is exactly the string `mecanum_map_world_frame_declaration_evidence/v1`.

- `subject` is an object with exactly `map_id`, `artifact_identity`, `map_content_hash`, all strings. They MUST exactly match the referenced map artifact's directory/map ID, top-level immutable UUID identity, and `map_content_hash`. The hash is 64 lowercase hexadecimal characters.
- `declaration` is an object with exactly `world_frame_state`, `map_frame`, `assertion_kind`, `transform_claim`, all strings. Their exact values are respectively `DECLARED_UNVERIFIED`, `map`, `USER_SUPPLIED_SLAM_SOURCE_WORLD`, and `NONE`.
- `source_world` is an object with exactly `kind`, `repository`, `commit`, `path`, `sha256`. `kind` is `git_file`; `repository` is the canonical repository URI; `commit` is the full Git commit object ID; `path` is a repository-relative path without absolute form, `..`, backslash, empty components, or symlink traversal; `sha256` is 64 lowercase hexadecimal characters. Resolve the exact commit/path and recompute the digest over the source bytes. This source-world locator is distinct from the metadata `evidence_ref`, which pins the declaration record itself.
- `decision_provenance` is an object with exactly `association` and `git_pin_scope`, both strings with exact values `USER_SUPPLIED_DECISION` and `SOURCE_WORLD_BYTES_ONLY`. This explicitly means the association between the map and source world is User-supplied; the Git pin identifies source-world bytes only and does not independently prove the association.
- `limitations` is an object with exactly `map_world_equivalence_claimed`, `transform_claimed`, `runtime_validation_claimed`, and `map_approval_claimed`, all JSON booleans and all exactly `false`.

This record shape is sufficient only to identify the subject and the User-supplied declaration decision for `DECLARED_UNVERIFIED`. It does not satisfy `EVIDENCE_RECORDED` or `VALIDATED`; it contains no world/map equivalence evidence, transform, measurement, runtime validation, or map approval. Its Git pin is immutable and verified under §3.4. The record itself MUST remain byte-immutable after integration.

### 3.5 Custody and approval

custody_approval has exactly map_custodian, approver, approval_status, approval_evidence. Actor mappings have exactly role, principal, delegation_evidence. role is MAP_CUSTODIAN or MAP_APPROVER. principal is a non-empty, stable identifier, not a display name. The candidate clarification restricts principal text to `github:<lowercase-login>`; this is candidate-only pending the activation conditions in §5. Direct role holders use delegation_evidence:null; delegates require a Git-pinned immutable delegation reference. No actor is assigned by the schema.

map_custodian is required in every state. approver is null in draft/pending_review and an actor mapping in approved/rejected. The Project Owner/User may hold both roles.

The accepted five-value lifecycle vocabulary is preserved as dispositions. Stored approval_status is draft, pending_review, approved, or rejected and is authoritative for the approval decision of that immutable metadata record; superseded is derived only from the append-only event/index and is never written by mutating an approved record. approval_evidence is null in draft/pending_review and a Git-pinned reference in approved/rejected; its evidence must identify the matching artifact identity and decision. Exact approval/rejection record schema, timestamp, subject digests, and principal authentication are PENDING_OWNER_DECISION.

No lifecycle transition graph is defined in v1. This does not allow implicit approval: missing, malformed, mismatched, or unverifiable evidence fails closed. Only a valid approved record satisfies the schema approval predicate. Approved bundles are immutable.

Under Option A, superseded is not written by mutating an approved artifact’s approval_status. Supersession is an effective/current disposition from the append-only event/index in §3.9, distinct from the artifact’s own approval decision.

### 3.6 World/frame

world_frame has exactly state and evidence_ref. state is NOT_DECLARED, DECLARED_UNVERIFIED, EVIDENCE_RECORDED, VALIDATED, or REJECTED; default NOT_DECLARED. evidence_ref is null only for NOT_DECLARED and is a Git-pinned immutable reference for every other state.

VALIDATED evidence identifies map/world identities and frames, method, tolerance or uncertainty, and approver. Decimal quantities are quoted decimal strings with explicit units, not YAML floats. Exact nested evidence keys, units, decimal grammar/precision, and approval record schema are PENDING_OWNER_DECISION. Filename, provenance, hash, or User assertion alone does not establish equivalence.

### 3.7 Runtime compatibility

runtime_compatibility has exactly state and evidence_ref. state is NOT_VALIDATED, EVIDENCE_RECORDED, VALIDATED, or REJECTED; default NOT_VALIDATED. evidence_ref is null only for NOT_VALIDATED and otherwise a Git-pinned immutable reference. VALIDATED/REJECTED evidence identifies the map, compatibility subject, result, and approver. Exact evidence keys and principal authentication are PENDING_OWNER_DECISION. Compatibility evidence grants no runtime, navigation, or deployment authority.

### 3.8 History

history has exactly predecessor_ref. artifact_identity appears only at the top level. predecessor_ref is null for the first identity; otherwise it is a canonical lowercase UUID resolving to an existing map artifact identity. Changed content creates a new identity. Existing metadata is not edited to add a successor link. Whether a supersession relation may cross map_id is PENDING_OWNER_DECISION.

### 3.9 Supersession — Option A

USER_SUPPLIED_DECISION: approved metadata/artifact bytes and approval evidence remain immutable. metadata is authoritative for the artifact’s own approval decision. An append-only event/index is the sole authority for predecessor/successor relations and effective/current disposition; it does not rewrite or override the approval decision.

The following implementation design is PROPOSAL_ONLY, not selected authority:

- Store one immutable event per relation under artifacts/maps/_supersession/events/<event_identity>.json; derive an index by enumerating and validating the complete event set at a pinned repository commit. Do not put mutable effective status in metadata.yaml.
- Proposed event schema is mecanum_map_supersession_event/v1, with exactly schema, event_identity, predecessor, successor, decision_actor, decision_evidence_ref. Each identity reference has map_id and artifact_identity. No digest/signature is self-embedded; verify bytes by Git commit/path and recomputed SHA-256.
- Accept an event only after both bundles validate, the predecessor has a valid approved decision, and the successor has valid approval_status:approved. Reject self-links, missing/mismatched identities, invalid actor/delegation/evidence, duplicate events, more than one successor per predecessor, forks, and cycles.
- Consumer proposal: validate metadata approval first. A map is approval-eligible only when approval_status:approved and its evidence validates. Then validate the complete event set. A valid event to an approved successor makes the predecessor effective disposition SUPERSEDED; absent a valid outgoing event, disposition is APPROVED_CURRENT. Missing/corrupt event set, duplicate successor, fork, cycle, or unresolved link affecting the queried identity fails closed; it is not treated as current. An unrelated invalid event’s fail-closed scope remains PENDING_OWNER_DECISION.
- Supersession is not approval and grants no runtime authority. A successor is not effective without its own valid approval.

Event location and serialization, proof that the set is complete and append-only, identity-reference digests, supersession approver/delegation/evidence contents, separate User approval requirement, acceptance timing, cross-map_id relation, and precise consumer fail-closed scope are PENDING_OWNER_DECISION. Until resolved and audited, supersession is not fully normative and no implementation may apply this proposal as active policy.

### 3.10 Pending decision register

PENDING_OWNER_DECISION items are: principal authentication; approval/rejection/delegation/world-frame/runtime evidence document schemas; timestamp and subject-digest requirements; tolerance/uncertainty keys, units, decimal grammar and precision; supersession event/index location, schema/serialization, append-only proof, approver/evidence, acceptance timing and fail-closed scope; and whether supersession may cross map_id. The candidate's `git_source` enum and principal spelling clarification are not active until the §5 conditions are met.

## 4. map_manifest.json and hash boundary

The existing manifest schema is mecanum_map_manifest/v1. It has exactly these top-level fields; unknown fields are rejected:

```json
{
  "schema": "mecanum_map_manifest/v1",
  "map_id": "<same as containing directory>",
  "artifact_identity": "<same immutable identity as metadata>",
  "map_hash_manifest": {
    "schema": "mecanum_map_hash/v1",
    "files": [
      {"role": "map_yaml", "name": "map.yaml", "size_bytes": 0, "sha256": "<64 lowercase hex>"},
      {"role": "occupancy_image", "name": "map.pgm", "size_bytes": 0, "sha256": "<64 lowercase hex>"}
    ]
  },
  "map_content_hash": "<64 lowercase hex>",
  "metadata": {
    "role": "metadata",
    "relative_path": "metadata.yaml",
    "size_bytes": 0,
    "sha256": "<64 lowercase hex>"
  }
}
```

Angle-bracket values and zero sizes are schema placeholders, not artifact values. map_id and artifact_identity must match the directory and metadata. The metadata descriptor is mandatory and outside the map-content digest; its role is metadata, its exact relative path is metadata.yaml, size_bytes is a non-negative integer, and sha256 is the lowercase SHA-256 of metadata.yaml bytes.

The complete map_manifest.json serialization uses RFC 8785 JCS, UTF-8 without BOM and no trailing newline. This rule determines full-manifest bytes only; map_content_hash is never calculated over the full manifest. The manifest embeds no digest or signature of its own bytes.

For this candidate only, the Owner-approved canonicalization of the selected source YAML permits exactly one textual field change: `image: warehouse_map2.pgm` becomes `image: map.pgm`. The source YAML SHA-256, resulting canonical YAML SHA-256, changed field/value, and proof that replacing the new value with the source value reconstructs the source bytes exactly are recorded in the decision record. No other YAML bytes may change. This candidate-only clarification does not authorize general YAML rewriting and is not active before the §5 conditions are met.

Architecture §48 and the active RFC 8785 clarification govern map_content_hash: SHA-256 of RFC 8785 JCS UTF-8 bytes for the exact mecanum_map_hash/v1 projection containing only map.yaml and map.pgm, in §48 order: map_yaml/map.yaml, then occupancy_image/map.pgm. Each entry has exactly role, name, size_bytes, and raw-file sha256, all verified against source bytes. metadata.yaml, optional pose graph, manifest result fields, and resulting map_content_hash are outside the payload. Raw-file SHA-256 values are distinct from map_content_hash.

Reject absolute paths, .., backslashes, symlinks, duplicate paths, paths outside the map directory, duplicate/missing/unknown roles, and paths beyond map.yaml, map.pgm, and metadata.yaml. Reject malformed JSON, invalid UTF-8/BOM, duplicate object keys, trailing data, non-finite numbers, unknown fields, and hash/size mismatch. size_bytes is a non-negative integer, not a boolean or fractional value. Every SHA-256 is exactly 64 lowercase hexadecimal characters and must match raw bytes. The metadata descriptor and metadata.yaml are validated under this ACR. No pose graph is included in the first canonical static-map artifact; a later pose graph needs its own schema, manifest, audit, and work package and remains outside map_content_hash.

## 5. Activation and governance

The candidate-only status wording in the integrated d33b93d source commit is retained as historical pre-activation state. Audit verdict and authorization are USER_SUPPLIED_EVIDENCE; fast-forward and remote-ref verification are Git-verifiable facts. The metadata schema remains ACTIVE_ON_INTEGRATION effective from d33b93d, independently of selection or approval of any concrete map. Status-correction source candidate `wp-05-map-metadata-schema-activation-status-correction-d33b93d@e4add07d10eb4a616569d0f9a83f97493851ef04` is historical provenance. Review candidate `wp-05-world-frame-evidence-registry-reconciliation-e89aeda5@0f42f1c9da00725c36500ff4ec1d2f75a0c8709a` (parent `e89aeda5ca78859bfeedac4e7b94bcd6c7dcc7f0`) was pushed to review and received the User-supplied `CORRECTION_REQUIRED` verdict; it was not integrated. The `572da885d31d98929a1f8b8af4420012f1786fd6` refresh base is historical, not current. This replacement is based on `0b2fcd1d010bc30f54d7621e6192dd76339df6b2` and awaits its own audit and separate exact-commit authorization.

RFC 8785 map-hash clarification remains active independently, and the already-integrated metadata schema remains active. The narrow declaration-evidence schema/record proposed by this replacement becomes integration-resident only after this exact candidate passes consolidated independent audit, receives separate User authorization, is fast-forwarded, and the remote integration ref is verified. The PEP snapshot wording correction is descriptive only; no WP-04 file, WP status/dependency, code authorization, runtime approval, HIL, hardware, motor-enable, or deployment state changes. The map remains a draft; the evidence record does not change metadata state or authorize navigation.
