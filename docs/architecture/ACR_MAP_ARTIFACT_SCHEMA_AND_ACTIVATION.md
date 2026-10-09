# ACR: Canonical Static-Map Artifact Schema and Activation

**ACR ID:** `ACR_MAP_ARTIFACT_SCHEMA_AND_ACTIVATION`
**Status:** `CANDIDATE_ONLY_PENDING_FOCUSED_INDEPENDENT_AUDIT_AND_SEPARATE_USER_INTEGRATION_AUTHORIZATION`
**Work package:** `WP-05-UNIFIED-MAP-ARTIFACT-SCHEMA-CHANGE-CONTROL`
**Integration base:** `f9987be4429349ef9110c45cf97a89728a5e4229`
**Candidate branch:** `wp-05-unified-map-artifact-schema-change-control-f9987be`

## 1. Decision and scope

This candidate records `USER_DECISION: APPROVED_FOR_WP05_UNIFIED_MAP_ARTIFACT_SCHEMA_CHANGE_CONTROL`. It is documentation-only and is not active until this exact candidate passes focused independent audit, receives separate Project Owner/User authorization for integration, and is fast-forwarded to `integration/implementation` with the remote ref verified.

It defines a canonical static-map artifact schema without changing Architecture §48's map-content hash boundary. It selects no map source, `map_id`, world, frame, transform, scenario, runtime profile, or map instance. It does not approve a concrete artifact or authorize code, ROS/runtime, HIL, hardware, motor operation, `deploy_sim`, or `deploy_real`. WP-05 remains open.

## 2. Canonical identity and directory rules

The canonical root remains `artifacts/maps/<map_id>/`. `map_id` must match `^[a-z][a-z0-9_]{0,63}$`, be unique repository-wide under `artifacts/maps/` using case-insensitive comparison, and equal the directory name exactly. Invalid IDs and exact/case-fold collisions are rejected; validation never renames an ID or directory.

An approved map is immutable and is not renamed. A meaningful content or provenance change creates a new immutable artifact identity and directory; the prior bundle and its history remain. The new identity must not overwrite the approved artifact or reuse its directory identity. No concrete ID is assigned here.

## 3. `metadata.yaml` — `mecanum_map_metadata/v1`

### 3.1 Encoding and parser

`metadata.yaml` is UTF-8 without BOM and contains exactly one YAML 1.2 document using a restricted data-only subset. Reject malformed YAML, duplicate mapping keys, aliases, tags, multiple documents, non-finite numbers, and unknown fields. Schema validation is strict; missing required fields or unknown states fail closed.

### 3.2 Required logical fields

The v1 object contains these required groups. Instance values must come from evidence; the schema supplies no concrete identities, provenance, approver identities, or measurements.

- `schema`: exactly `mecanum_map_metadata/v1` (version is carried by this identifier).
- `map_id`: validated by §2 and equal to the containing directory name.
- `artifact_identity`: non-empty immutable identity unique to the artifact instance.
- `classification`: exactly `static_occupancy_map`.
- `source_provenance`: one or more records with source reference and evidence reference; include a raw source SHA-256 only when computed from those bytes. User attestation is labeled as such and is not inferred validation evidence.
- `custody_approval`: `map_custodian`, `approver`, `approval_status`, and an immutable `approval_evidence` reference. Actor records identify role and principal. Default MapCustodian and approver are Project Owner/User. A delegate is valid only with immutable delegation evidence. Project Owner/User may self-approve while holding both roles.
- `world_frame`: relationship state and evidence reference, defaulting to `NOT_DECLARED`.
- `runtime_compatibility`: state and evidence reference, defaulting to `NOT_VALIDATED`.
- `history`: immutable identity and supersession references; the first identity has no predecessor.

`approval_status` is authoritative in `metadata.yaml`; the manifest carries no independent effective status. Allowed lifecycle values are exactly `draft`, `pending_review`, `approved`, `rejected`, and `superseded`. Only `approved` can be effective for navigation, and approval requires an immutable approval-evidence reference. Missing/malformed/unknown status, missing evidence, or inconsistent identity leaves the artifact non-effective; there is no implicit approval.

An approved bundle is never overwritten. A meaningful change produces a new artifact identity and directory. Supersession is represented by immutable history/evidence linked from the successor; the previous bundle and its approval evidence are retained unchanged. Consumers fail closed for an identity identified as superseded.

## 4. `map_manifest.json` — `mecanum_map_manifest/v1`

### 4.1 Full manifest structure

The full manifest has exactly these top-level fields; unknown fields are rejected:

```json
{
  "schema": "mecanum_map_manifest/v1",
  "map_id": "<same as containing directory>",
  "artifact_identity": "<immutable instance identity>",
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

Angle-bracket strings and zero sizes are schema placeholders, not artifact values. `map_id` must match metadata and the directory; `artifact_identity` must match metadata. The mandatory metadata descriptor is outside the map-content digest and has role `metadata`, exact relative path `metadata.yaml`, non-negative integer byte size, and lowercase 64-hex raw SHA-256 checked against the actual file.

### 4.2 Locked map-content digest

`map_content_hash` is SHA-256 of RFC 8785 JCS output for the exact §48 projection, encoded UTF-8 without BOM and without trailing newline. The projection contains only:

- `schema: mecanum_map_hash/v1`;
- exactly two ordered `files` entries: `map_yaml` with `name: map.yaml`, then `occupancy_image` with `name: map.pgm`;
- exactly `role`, `name`, `size_bytes`, and `sha256` in each entry, with byte size and raw-file SHA-256 verified against file bytes.

No metadata descriptor, pose graph, result field, full-manifest serialization, or resulting `map_content_hash` is included. The hash is never calculated from the full manifest. Key `name` follows the §48 example and the User-approved clarification; file boundary and order are unchanged.

### 4.3 Full-manifest serialization and validation

Serialize the complete `map_manifest.json` using RFC 8785 JCS, UTF-8 without BOM, with no trailing newline. This determines full-manifest bytes but does not change the projection used for `map_content_hash`. The manifest contains no digest or signature of its own bytes. No detached checksum/signature is required here; a future need requires separate change control and must be recorded externally.

Reject absolute paths, `..`, backslashes, symlinks, duplicate paths, paths outside the map directory, duplicate/missing/unknown roles, and paths other than the two projection names and `metadata.yaml`. Reject malformed JSON, invalid UTF-8, BOM, duplicate object keys, trailing data, non-finite numbers, unknown fields, and hash/size mismatch. `size_bytes` is a non-negative integer, not a boolean or fractional number. Every SHA-256 is exactly 64 lowercase hexadecimal characters and must match the corresponding raw bytes. Validate metadata under §3.

## 5. World/frame and runtime compatibility

World/frame relationship defaults to `NOT_DECLARED`. Allowed states are exactly `NOT_DECLARED`, `DECLARED_UNVERIFIED`, `EVIDENCE_RECORDED`, `VALIDATED`, and `REJECTED`. `VALIDATED` requires immutable evidence identifying compared identities/frames, method, tolerance or uncertainty, and approver. Filenames, directories, user-supplied provenance, map YAML values, and content hashes alone do not establish metric alignment or equivalence.

Runtime compatibility defaults to `NOT_VALIDATED` and fails closed. A map hash or source provenance does not establish compatibility with a world, frame tree, Map Server, localization profile, or runtime. A `VALIDATED` or `REJECTED` state requires separate immutable evidence and an approver. No world, frame, profile, or runtime verification is selected or authorized here.

## 6. Optional pose graph

The first canonical static-map artifact omits pose-graph files. Later inclusion requires its own schema, versioned manifest, audit, and work package. Pose-graph files and their manifest always remain outside `map_content_hash`, consistent with §48's separate pose-graph manifest/hash boundary.

## 7. Activation and governance

This ACR becomes active only after focused independent audit passes, the Project Owner/User separately authorizes this exact candidate, and the exact commit is fast-forwarded to `integration/implementation` with the remote ref verified. Schema activation does not approve any individual map instance; a concrete map requires separately evidenced preparation, validation, and approval under the activated schema.

The RFC 8785 map-hash clarification is already active at the base integration commit `f9987be4429349ef9110c45cf97a89728a5e4229`; this ACR preserves it. Registry reconciliation in this candidate corrects the earlier candidate-pending wording for that integrated RFC clarification while keeping this map schema candidate-only. No PEP revision, WP status/dependency, WP-04 Gate A state, code authorization, runtime approval, HIL, hardware, or deployment state changes.

## 8. Prior audited semantics provenance

This refreshed candidate carries forward the schema semantics from prior candidate `wp-05-unified-map-artifact-schema-change-control-988a74b@617ef28b92b6a17bc4ba00d1b0edd7ccfcdd7b12`, parent `988a74b529fdb4bcf77f341db5c6d115e8511a9b`. The Project Owner/User supplied audit verdict `READINESS_FOR_USER_DECISION_TO_INTEGRATE: PASS` for that exact candidate. It is stale on the current integration base and is used only as audited semantic provenance, not as an integration candidate. This refreshed candidate requires its own focused re-audit and separate exact-commit integration authorization.
