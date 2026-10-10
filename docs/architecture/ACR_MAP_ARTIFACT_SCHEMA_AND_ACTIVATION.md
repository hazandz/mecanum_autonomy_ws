# ACR: Canonical Static-Map Artifact Schema and Activation

**ACR ID:** ACR_MAP_ARTIFACT_SCHEMA_AND_ACTIVATION
**Status:** CANDIDATE_ONLY_PENDING_FOCUSED_INDEPENDENT_AUDIT_AND_SEPARATE_USER_INTEGRATION_AUTHORIZATION
**Work package:** WP-05-UNIFIED-MAP-METADATA-SCHEMA-CHANGE-CONTROL
**Integration base:** 7f9ed36a10b5f4ab68eb437833f04d4842eff986
**Candidate branch:** wp-05-unified-map-metadata-schema-change-control-7f9ed36

## 1. Decision, provenance, and scope

This candidate records the nine metadata decision groups as USER_SUPPLIED_DECISION, as stated by the Project Owner/User for this work package. It records Option A for supersession: approved metadata, artifact bytes, and approval evidence remain immutable; supersession is recorded in an append-only event/index. Conversation-supplied audit or User-authorization claims remain USER_SUPPLIED; no audit-report hash is asserted.

Source decision packet: branch wp-05-map-metadata-source-traceability-correction-4b21343, commit 361966ececc3c0fde088bffe5ec2987af8f16014, path docs/WP-05_MAP_METADATA_SCHEMA_CLOSURE_DECISION_PACKET_DRAFT.md, SHA-256 9bd7c06683299d36b11ffebb0db372f67e24257ab9a2ebb0cc193ee18bb35bd4. This provenance does not activate this schema.

This documentation candidate is inactive until this exact candidate passes focused independent audit, receives separate Project Owner/User authorization for integration, is fast-forwarded to integration/implementation, and the remote ref is verified. It selects no map source, map_id, actor identity, world/frame equivalence, runtime-compatibility evidence, or map instance. It does not authorize code, ROS/runtime, HIL, hardware, motor operation, deploy_sim, or deploy_real. WP-05 remains open.

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

provenance_kind includes USER_ATTESTED, which means an explicit User assertion and never means validation or approval. The exact complete provenance_kind enum remains PENDING_OWNER_DECISION because the accepted prior recommendation included EXTERNAL_SOURCE while also selecting Git-only immutable evidence references. This candidate does not silently reconcile those choices.

raw_sha256 is optional, lowercase 64-hex SHA-256 of source raw bytes. Omit before computation; if present, recompute from exact source bytes and require a match. source_provenance order is primary source first, then supporting or derived records in declared order. Duplicate source_ref locators are rejected.

### 3.4 Immutable references and evidence

A Git evidence reference has exactly kind=git_file, repository:string, commit:full commit object ID, path:repository-relative string, sha256:lowercase 64-hex. Immutability is checked by resolving the exact commit/path and recomputing the digest. Branch/tag-only references are invalid. A Git pin or USER_ATTESTED label does not prove an approval, world/frame validation, or runtime compatibility.

Referenced approval, delegation, world/frame, and runtime evidence must identify its subject and decision in immutable bytes. Exact evidence-document schemas, timestamp format, principal-authentication method, and external evidence policy are PENDING_OWNER_DECISION.

### 3.5 Custody and approval

custody_approval has exactly map_custodian, approver, approval_status, approval_evidence. Actor mappings have exactly role, principal, delegation_evidence. role is MAP_CUSTODIAN or MAP_APPROVER. principal is a non-empty, stable, issuer-qualified identifier, not a display name; namespace grammar/registry is PENDING_OWNER_DECISION. Direct role holders use delegation_evidence:null; delegates require a Git-pinned immutable delegation reference. No concrete actor is assigned.

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

PENDING_OWNER_DECISION items are: complete provenance_kind enum/external source form; principal namespace and authentication; approval/rejection/delegation/world-frame/runtime evidence document schemas; timestamp and subject-digest requirements; tolerance/uncertainty keys, units, decimal grammar and precision; supersession event/index location, schema/serialization, append-only proof, approver/evidence, acceptance timing and fail-closed scope; and whether supersession may cross map_id. This candidate records accepted decisions but does not claim these details are resolved.

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

Architecture §48 and the active RFC 8785 clarification govern map_content_hash: SHA-256 of RFC 8785 JCS UTF-8 bytes for the exact mecanum_map_hash/v1 projection containing only map.yaml and map.pgm, in §48 order: map_yaml/map.yaml, then occupancy_image/map.pgm. Each entry has exactly role, name, size_bytes, and raw-file sha256, all verified against source bytes. metadata.yaml, optional pose graph, manifest result fields, and resulting map_content_hash are outside the payload. Raw-file SHA-256 values are distinct from map_content_hash.

Reject absolute paths, .., backslashes, symlinks, duplicate paths, paths outside the map directory, duplicate/missing/unknown roles, and paths beyond map.yaml, map.pgm, and metadata.yaml. Reject malformed JSON, invalid UTF-8/BOM, duplicate object keys, trailing data, non-finite numbers, unknown fields, and hash/size mismatch. size_bytes is a non-negative integer, not a boolean or fractional value. Every SHA-256 is exactly 64 lowercase hexadecimal characters and must match raw bytes. The metadata descriptor and metadata.yaml are validated under this ACR. No pose graph is included in the first canonical static-map artifact; a later pose graph needs its own schema, manifest, audit, and work package and remains outside map_content_hash.

## 5. Activation and governance

This exact candidate remains candidate-only until focused independent audit passes, the Project Owner/User separately authorizes this exact commit, it is fast-forwarded to integration/implementation, and the remote ref is verified. Schema activation is separate from approval of a concrete map instance.

RFC 8785 map-hash clarification remains active independently. No PEP, WP-04 file, WP status/dependency, code authorization, runtime approval, HIL, hardware, motor-enable, or deployment state changes. No map artifact is created.
