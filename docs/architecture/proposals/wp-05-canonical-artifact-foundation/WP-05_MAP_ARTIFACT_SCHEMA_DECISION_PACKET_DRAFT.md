# WP-05 Canonical Static-Map Artifact Schema — Decision Packet (Draft)

**Status:** `DRAFT / PENDING_PROJECT_OWNER_USER_DECISIONS`
**Work package:** `WP-05-MAP-ARTIFACT-SCHEMA-DECISION-PACKET`
**Exact integration base:** `integration/implementation@988a74b529fdb4bcf77f341db5c6d115e8511a9b`
**Candidate branch:** `wp-05-map-artifact-schema-decision-packet-988a74b`

**Purpose:** collect unresolved schema and lifecycle decisions for a later unified change-control of the canonical static-map artifact. This packet is for decision and focused audit only. It is not a schema, ACR, approval, map selection, or artifact instance.

## 1. Authority and scope boundary

The controlling source remains `docs/MECANUM_NAV_DRL_Architecture.docx` at this exact base. Sections 43, 45, 48, and 50 establish the relevant behavior. PEP-001 rev.0.5.0 sequences WP-05 but does not replace Architecture. The active WP-05 foundation approval and map-hash RFC 8785 decision are recorded in the governance sources at the same base.

Already established and not reopened here:

- Canonical map root: `artifacts/maps/<map_id>/`.
- Architecture §48 names `map.yaml`, `map.pgm`, `map_manifest.json`, and `metadata.yaml` in the map root; pose-graph files are optional and use a separate manifest/hash.
- `map_content_hash` covers the RFC 8785 JCS projection for exactly `map.yaml` and `map.pgm`, UTF-8 without BOM or trailing newline. Entry order is `map_yaml`, then `occupancy_image`; each entry identifies role, relative name, byte size, and raw-file SHA-256. Metadata, optional pose graph, manifest result fields, and the resulting `map_content_hash` are outside that digest input.
- §48 says mapping creates draft artifacts and hashes after save; navigation requires `approval_status=approved`. §43 says a new map remains draft until saved, hashed, checked, and approved. §45 carries `map_id` and `map_content_hash` with path identity. §50 requires an approved map/hash and one localization provider for navigation checks.
- The RFC 8785 map-hash decision is active on integration at this base. Registry and decision-record text still describes that RFC clarification as candidate-pending; a later unified change-control must reconcile those stale descriptions without implying that a map schema or map instance is already approved.

This packet does not select a map source or `map_id`. It does not select `warehouse_map2`, assert world/frame equivalence, or define a runtime profile. No scenario, goal, start, bounds, zones, seed, randomization value, pose graph, measurement, hardware evidence, code, ROS/runtime, HIL, or deployment authorization is created.

## 2. Decisions requested

Every recommendation below is a proposal only. No option becomes effective through this packet. The Project Owner/User should confirm, replace, or defer each choice before the later change-control is drafted.

### 2.1 `map_id` syntax, identity, and lifecycle

**Decision:** choose identifier grammar, case behavior, uniqueness scope, directory matching, and rename/collision policy.

| Option | Proposed rule | Effect |
|---|---|---|
| A — portable lowercase slug (**recommended**) | ASCII lowercase letters, digits, underscore; begin with a letter; no spaces, path separators, dots, or case variants. Unique among entries directly under `artifacts/maps/`, compared case-insensitively. ID must exactly equal its directory name. | Portable validation and avoids filesystem case collisions; restricts naming flexibility. |
| B — lowercase DNS-style slug | ASCII lowercase letters, digits, and hyphens; begin/end with a letter or digit; same uniqueness and directory-match rules as A. | Familiar URL-like IDs; disallows underscores. |
| C — defer grammar | Retain only the existing root convention until a later schema decision. | No new identifier validation; artifact creation remains blocked on the later rule. |

User must decide whether uniqueness is repository-wide under `artifacts/maps/` or scoped to a registry namespace; whether IDs are immutable after publication; whether any collision is rejected without repair; and whether a rename or materially changed approved map requires a new ID, new artifact version, or both. **Recommended default:** reject collisions; never silently rename or mutate an approved instance; publish changed content as a new immutable identity and retain the prior instance as history.

### 2.2 `metadata.yaml` schema, custody, approval, and history

**Decision:** define schema/version, required fields, parser rules, authority roles, status vocabulary, and immutable-history behavior.

**Schema options:**

- **A — versioned strict schema (`mecanum_map_metadata/v1`, recommended):** require schema/version, `map_id`, artifact identity/version, static-map classification, source provenance, custody/approval provenance, and explicit world/frame declaration state. Any hash reference is informational and remains outside the hash projection. Reject unknown fields unless a later schema version permits them.
- **B — minimal metadata:** require schema/version, `map_id`, custody/approval provenance, and declaration states; keep detailed provenance in a separate immutable decision record.
- **C — defer:** define no metadata schema and create no map instance until a later decision resolves the fields.

**Parser/encoding choices:** decide UTF-8/BOM policy, YAML version/subset, and whether duplicate mapping keys, aliases/tags, non-finite numbers, unknown fields, and multiple documents fail validation. **Recommended default:** UTF-8 without BOM, one YAML 1.2 document, restricted data-only subset, reject duplicate keys and unsupported constructs, and strict schema validation. This is a metadata parsing rule, not a map-content hash rule.

**Required-field candidates for confirmation:** schema and version; `map_id`; immutable artifact/version identity; static-map type; source provenance/evidence references; source byte hashes when actually available; attestation/actor/date only when supported by recorded evidence; `MapCustodian`; approver and any named delegate plus delegation provenance; `approval_status`; world/frame relationship state and evidence reference defaulting to `NOT_DECLARED`; history/supersession reference. These are candidate fields, not selected schema.

The active Registry records Project Owner/User as MapCustodian/approver unless a delegate is named in the immutable map record. User must confirm whether custody and approval are distinct roles, self-approval is allowed, delegation evidence required, and whether approver must differ from creator.

**Approval/effective-state options:**

- **A — minimal:** `draft` and `approved`, preserving §48's exact `approved` value for navigation; absent, malformed, or unknown status fails closed.
- **B — explicit lifecycle (recommended):** `draft`, `pending_review`, `approved`, `rejected`, and `superseded`; only `approved` is effective for navigation, and transitions require immutable decision evidence.
- **C — defer extra states:** retain only the §48 distinction between draft and `approved`; define rejection/revocation/supersession later.

User must choose the single authoritative location for `approval_status` (`metadata.yaml`, `map_manifest.json`, or a separate immutable approval record). **Recommended default:** metadata/approval record is authoritative; do not duplicate an independently editable effective status in the manifest. Navigation fails closed unless the authoritative status is exactly `approved` and identity/hash checks pass.

For history, choose append-only approval/supersession records, version history inside metadata, or a separate governance decision record. **Recommended default:** approved instances are immutable; decisions are recorded in append-only, hash-pinned records and historical approval evidence is never rewritten.

**Fail-closed rule:** missing required fields, unknown schema/status, invalid provenance, missing approver/delegation evidence, mismatched ID, or insufficient validation evidence leaves the instance non-effective and unusable for navigation. User should confirm the unavailable-state label; proposal: remain `draft` with validation errors, never implicit approval.

### 2.3 `map_manifest.json` schema and validation

**Decision:** define the full-manifest schema separately from the already-authorized content-hash projection.

**Proposed full-manifest shape (for decision only):** versioned top-level manifest with manifest schema/version, `map_id`, immutable artifact/version identity, the exact §48 `map_hash_manifest` projection, resulting `map_content_hash`, and a `metadata.yaml` descriptor (`relative_path`, `size_bytes`, raw SHA-256). Any approval state must reference the single authoritative location chosen in §2.2. The manifest must not contain a digest of its own complete bytes. User must confirm or replace all proposed names and fields.

**Projection-key clarification:** §48 prose says “relative name,” while its inline example uses JSON key `name`. Confirm the exact serialized key spelling in the locked two-entry projection. **Recommended default:** use `name` as shown in the §48 example, constrained to `map.yaml` and `map.pgm`; preserve the two roles, order, and two-file boundary. A different key spelling changes the JCS bytes and content hash even if file membership is unchanged, so the later change-control must state the exact projection and a test vector.

For metadata's descriptor, decide whether its key is `metadata` or a role-bearing member of a `files` list, and whether the role is fixed. **Recommended default:** one mandatory descriptor with unique role `metadata`, exact relative path `metadata.yaml`, non-negative integer `size_bytes`, and lowercase 64-character raw SHA-256. It remains outside `map_content_hash`.

**Validation policy choices:**

- Paths: normalized relative POSIX paths only; reject absolute paths, `..`, empty components, backslashes, symlinks, and paths outside the map directory (**recommended**).
- Sizes: non-negative integral byte counts compared to actual bytes; reject booleans, fractions, overflow, and mismatches.
- Digests: lowercase 64-hex SHA-256, recomputed from raw file bytes; reject malformed or mismatched values.
- Roles/entries: exactly one `map_yaml` and one `occupancy_image`, in that order, in the hash projection; reject duplicate/missing/unknown roles and duplicate paths.
- JSON: decide policy for malformed JSON, invalid UTF-8, BOM, duplicate object keys, trailing data, and non-finite numbers; **recommended default:** reject all. Decide whether unknown fields are rejected or allowed only under a recognized schema version; **recommended default:** strict rejection.

**Full-manifest serialization is separate from `map_content_hash`:**

| Option | Full `map_manifest.json` bytes | Effect |
|---|---|---|
| A — RFC 8785 JCS UTF-8, no BOM/newline (**recommended**) | Serialize the complete manifest deterministically, including result fields and metadata descriptor. Extract the exact §48 projection before computing `map_content_hash`; never hash the complete manifest to produce that result field. | Reproducible full-manifest bytes while retaining the existing two-file digest boundary. This is an explicit map-manifest decision, not an extension of the scenario convention. |
| B — fully specified pretty JSON | Fix indentation, key order, line endings, encoding, final newline, and escaping in a separate profile. | Human-readable, but requires more serialization rules and cross-implementation checks. |
| C — semantic JSON only | Validate parsed fields/file hashes without requiring identical full-manifest bytes; claim no canonical full-manifest byte hash. | Fewer byte-format commitments, but no byte-for-byte manifest reproducibility. |

User must decide whether a detached full-manifest checksum/signature is needed. **Recommended default:** none inside the manifest; if later needed, record it externally so there is no self-reference. Confirm result-field name/encoding for `map_content_hash`; its input remains exactly the RFC 8785 projection already selected in §48.

### 2.4 World/frame declaration and runtime compatibility

**Decision:** choose declaration fields, allowed states, and evidence threshold without selecting any world, frame, transform, or runtime profile.

- **Default declaration:** `NOT_DECLARED` unless separate evidence establishes the relationship. Filename, directory, SLAM provenance statement, `map.yaml` frame/resolution/origin, or visual similarity is not evidence of metric alignment or world/frame equivalence.
- **Proposed states:** `NOT_DECLARED`, `DECLARED_UNVERIFIED`, `EVIDENCE_RECORDED`, `VALIDATED`, and `REJECTED`. User should confirm this vocabulary and whether `VALIDATED` requires named approver plus separate transform/measurement/validation evidence.
- **Evidence rule:** only a separate immutable, traceable evidence record can support equivalence. It should identify what was compared, method, frames/identities, uncertainty/tolerance, and approver only when actually evidenced. No inference from source names or provenance wording.
- **Runtime compatibility:** a separate fail-closed gate. A valid `map.yaml`/`map.pgm` or matching hash alone does not establish compatibility with a world, frame tree, Map Server, localization profile, or runtime. User should choose required compatibility evidence and owner/gate. **Recommended default:** `NOT_VALIDATED` until a separately authorized verification packet supplies evidence. This packet authorizes no verification run.

### 2.5 Optional pose graph

**Recommendation:** omit pose-graph files from the first canonical static-map artifact. This avoids implying SLAM continuation capability and keeps the first instance's scope limited.

If later included, require a separate schema and versioned `pose_graph_manifest.json` contract covering paths, sizes, raw hashes, provenance, validation, and lifecycle. Pose graph remains outside `map_content_hash`; §48 assigns it a separate manifest/hash. User should confirm omission as the initial default and require a separate work package/audit for inclusion.

### 2.6 Unified change-control and activation

After User decisions and focused audit of this packet, the later unified schema change-control is limited to:

1. `docs/architecture/ACR_MAP_ARTIFACT_SCHEMA_AND_ACTIVATION.md`
2. `docs/governance/decisions/WP-05_CANONICAL_STATIC_MAP_ARTIFACT_SCHEMA_DECISION.md`
3. `docs/governance/CANONICAL_SOURCE_REGISTRY.md`
4. `docs/governance/PROJECT_PROGRESS_LEDGER.md`

The later change-control must preserve the current §48 hash boundary and RFC 8785 rule. Do not edit Architecture DOCX or PEP unless a separately approved change actually changes that boundary. Reconcile Registry and decision-record language that still calls the already-integrated RFC 8785 clarification candidate-pending; keep the Ledger append-only and add a correction/reconciliation entry rather than rewriting history. Record exact decisions and an activation condition tied to focused audit, separate exact-candidate User authorization, fast-forward, and remote verification.

Schema activation is distinct from approval of an individual map instance: schema activation defines how future instances are described and validated; it does not select, create, validate, or approve a map. User should confirm this path allowlist and whether the ACR is the only authority vehicle needed while the §48 hash boundary remains unchanged.

## 3. Consolidated User decision checklist

Before unified change-control, User decisions remain pending for:

1. `map_id` grammar, case and uniqueness scope, directory match, immutability, collision, and rename policy.
2. Metadata schema/version and required fields; YAML encoding/parser strictness; provenance/custody evidence; MapCustodian/approver/delegate relationship; status vocabulary and authoritative status location; history/supersession policy; fail-closed label.
3. Full manifest schema/version and result fields; exact projection key spelling (`name` or a confirmed alternative); metadata descriptor; path/size/hash/role/unknown-field/JSON duplicate-key validation; full-manifest serialization; detached checksum/signature policy.
4. World/frame declaration field and vocabulary, evidence bar and approver; runtime-compatibility evidence and gate owner.
5. Pose-graph omission from the first artifact and separate schema/work-package requirement if later included.
6. Exact four-path unified change-control scope and audit/authorization/activation conditions.

**No decisions are made by this packet.** It does not choose `warehouse_map2`, any map source or ID, a world/frame relationship, runtime compatibility, or an artifact schema as current authority. It creates no `artifacts/maps/**` content and changes no WP status, dependency, or authorization. WP-05 remains open; `CODE_AUTHORIZATION: NOT_GRANTED`; `RUNTIME_APPROVED: NOT_APPROVED`.
