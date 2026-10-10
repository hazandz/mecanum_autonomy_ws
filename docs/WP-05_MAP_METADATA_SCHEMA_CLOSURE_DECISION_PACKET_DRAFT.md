# WP-05 Map Metadata Schema Closure Decision Packet Draft

**Status:** `DRAFT / PENDING_PROJECT_OWNER_USER_DECISIONS_AND_FOCUSED_AUDIT`
**Work package:** `WP-05-MAP-SCHEMA-ACTIVATION-AND-METADATA-CLOSURE-PACKET`
**Exact integration base:** `integration/implementation@401593a4268af572ef4690177539360b1c15410a`
**Prior/source packet branch (before F-01 correction):** `wp-05-map-metadata-schema-closure-packet-401593a`

## Purpose

This packet asks the Project Owner/User to close two governance gaps before any canonical map instance is prepared: how the map-artifact schema's activation is recorded after commit `401593a…` reached integration, and the exact normative structure and validation rules for `metadata.yaml`. It proposes choices for review; none of the proposals below changes current authority.

This packet creates no map artifact, selects no map source or `map_id`, approves no map instance, and establishes no world/frame equivalence or runtime compatibility. It does not authorize navigation, scenario work, code, runtime, HIL, hardware, or WP-05 closure.

Evidence labels used below:

- **SOURCE_FACT:** read from a specified repository object or verified remote ref.
- **USER_SUPPLIED:** stated by the Project Owner/User in conversation; no corresponding immutable repository record was found.
- **PROPOSED_FOR_USER_DECISION:** a recommendation only; not current schema authority.

## 1. Separate decisions and current state

### 1.1 Map-hash rule — active and separate

**SOURCE_FACT:** Architecture §48 at the base specifies SHA-256 over RFC 8785 JCS bytes encoded as UTF-8 without BOM or trailing newline. The projection is schema `mecanum_map_hash/v1` with exactly two ordered entries: `map_yaml` / `map.yaml`, then `occupancy_image` / `map.pgm`; each entry carries role, name, byte size, and raw-file SHA-256. `metadata.yaml`, pose graph, manifest result fields, and resulting `map_content_hash` are excluded.

**SOURCE_FACT:** The Registry identifies the RFC 8785 clarification as active on integration. Its integration commit is `988a74b529fdb4bcf77f341db5c6d115e8511a9b`; it remains present at this packet's exact base. This packet does not reopen or alter that rule.

### 1.2 Map-artifact schema — integration event versus recorded activation state

**SOURCE_FACT:** Remote `integration/implementation` was verified at `401593a4268af572ef4690177539360b1c15410a`. That commit contains the four-path map-schema change-control candidate. At this base:

- The ACR status line remains `CANDIDATE_ONLY_PENDING_FOCUSED_INDEPENDENT_AUDIT_AND_SEPARATE_USER_INTEGRATION_AUTHORIZATION`.
- The decision record remains `CANDIDATE_PENDING_FOCUSED_INDEPENDENT_AUDIT_AND_SEPARATE_USER_INTEGRATION_AUTHORIZATION`.
- The Registry calls the schema a refreshed candidate only and says references activate after focused re-audit, separate authorization of the exact commit, fast-forward, and remote-ref verification.

Those documents do not themselves record a completed activation correction. The exact commit's presence on the integration ref is a verifiable Git event; it does not, by itself, prove audit or User authorization.

**SOURCE_FACT:** The predecessor decision packet is available at branch `wp-05-map-artifact-schema-decision-packet-988a74b` @ `ceb97be46b2e8d031e7712624b3de5898597cb38`, parent `988a74b529fdb4bcf77f341db5c6d115e8511a9b`, path `docs/architecture/proposals/wp-05-canonical-artifact-foundation/WP-05_MAP_ARTIFACT_SCHEMA_DECISION_PACKET_DRAFT.md`, SHA-256 `0a5dac94ac31e961cb18abd9cfe38eef284e3969d05d230b6b0c9bba9de28831`. Its source branch/ref and file bytes were directly verified. It is historical decision-packet provenance, not current authority.

**USER_SUPPLIED:** The conversation includes a focused-audit verdict `READINESS_FOR_USER_DECISION_TO_INTEGRATE: PASS` for exact commit `401593a4268af572ef4690177539360b1c15410a`, and an explicit User authorization to fast-forward that commit. The remote fast-forward and resulting ref were independently verified. The named audit report `INDEPENDENT_FOCUSED_STATIC_REAUDIT_WP05_UNIFIED_MAP_ARTIFACT_SCHEMA_401593A4.md` was not found in the tracked tree of either the candidate commit or integration base. Its contents and file hash therefore are not independently verified from the repository in this packet.

**PROPOSED_FOR_USER_DECISION:** Reconcile the static candidate/pending labels through a separate append-only governance correction. Preserve the original text as historical state; record the audit verdict and its evidence source, the exact User authorization, the verified fast-forward, and remote ref. Only that correction should state whether the schema is active. If the User does not accept the conversation-supplied audit/authorization as sufficient provenance, keep the schema non-operative and identify the additional immutable evidence or authorization required. Do not infer activation solely from the Git ref.

### 1.3 Map instance — not approved or created

No canonical map instance is approved or created by this packet. It makes no source, `map_id`, world/frame, scenario, or runtime-profile decision. Map-hash authority and map-schema activation are distinct from the later preparation, validation, and approval of a particular map.

## 2. `metadata.yaml` field-closure matrix

The integration-resident, candidate-only ACR proposal names required logical fields and several validation rules, but it does not define a complete field-level YAML schema for all nested records. The map-schema content in that ACR becomes normative only after a separate status correction has been independently audited, authorized for integration by the User, and the remote integration ref has been verified. Because the proposal also requires strict rejection of unknown fields, implementations cannot safely invent different nested structures and each claim conformance. Every completion rule suggested in this section is **PROPOSED_FOR_USER_DECISION**, not current schema authority.

| ACR field/path | What the pending ACR proposal specifies | Exact structure/validation still open |
|---|---|---|
| `schema` | Required string value `mecanum_map_metadata/v1`; version is carried by this identifier. | Whether any other version field exists is not specified. Proposed: exact non-empty scalar string, no separate `version` key in v1. |
| `map_id` | Required; grammar `^[a-z][a-z0-9_]{0,63}$`; equals directory name; unique case-insensitively under `artifacts/maps/`. | Scalar YAML string is implied by the grammar but not explicitly typed. Proposed: require a string and reject coercion. |
| `artifact_identity` | Required non-empty immutable identity unique to the instance; must match manifest. | Type, grammar, generation, uniqueness scope, and relation to artifact version are open. The ACR does not define an `artifact_version` key, while the decision record refers to artifact/version identity. |
| `classification` | Required exact value `static_occupancy_map`. | Proposed: scalar string enum with no other v1 values. |
| `source_provenance[]` | At least one record; each has a source reference and evidence reference. Include raw-source SHA-256 only when computed from those bytes. User attestation must be labeled and cannot be treated as validation. | Exact key paths, reference format, record identity, source/hash pairing, attestation vocabulary, date policy, and whether multiple records have a canonical order are open. |
| `custody_approval` | Required group with `map_custodian`, `approver`, `approval_status`, and immutable `approval_evidence` reference. Actors identify role and principal. Project Owner/User is the default custodian and approver; a delegate requires immutable delegation evidence; self-approval is permitted. | Actor key names/types, principal identifier format, whether both actors must be present in every lifecycle state, and exact delegation-reference shape are open. The packet does not name a principal or assert a map approval. |
| `custody_approval.approval_status` | Allowed values: `draft`, `pending_review`, `approved`, `rejected`, `superseded`. Only `approved` can be effective for navigation. | Transition graph, evidence required for each state, and whether `draft`/`pending_review` may have null approval evidence are open. |
| `custody_approval.approval_evidence` | ACR calls for an immutable evidence reference; approval requires such evidence. Missing evidence leaves the artifact non-effective. | Whether the field is required/non-null before approval, exact URI/object shape, accepted evidence locations, and how immutability is verified are open. No map-instance approval evidence is supplied by this packet. |
| `world_frame` | Required relationship state and evidence reference; default state `NOT_DECLARED`. Allowed states: `NOT_DECLARED`, `DECLARED_UNVERIFIED`, `EVIDENCE_RECORDED`, `VALIDATED`, `REJECTED`. `VALIDATED` requires immutable evidence naming compared identities/frames, method, tolerance or uncertainty, and approver. | Exact YAML keys, nested evidence schema, which non-validated states permit null evidence, and whether rejection requires an approver/reference are open. |
| `runtime_compatibility` | Required state and evidence reference; default state `NOT_VALIDATED`. `VALIDATED` or `REJECTED` requires separate immutable evidence and an approver. | ACR does not enumerate the allowed runtime states or exact keys, nor say when a null evidence reference is valid. Proposed vocabulary requires User decision. |
| `history` | Required immutable identity and supersession references; first identity has no predecessor. Meaningful changes create a new identity; old approved bundles/history remain immutable. | Exact key paths, representation of “no predecessor”, successor versus predecessor links, relationship to `artifact_identity`, and evidence needed for supersession are open. |

### 2.1 Cross-cutting serialization and parser questions

**SOURCE_FACT:** ACR requires UTF-8 without BOM, exactly one YAML 1.2 document, a restricted data-only subset, and rejection of malformed YAML, duplicate mapping keys, aliases, tags, multiple documents, non-finite numbers, and unknown fields.

**PROPOSED_FOR_USER_DECISION:** Define the restricted subset precisely: permitted scalar types, whether booleans/null are accepted, number syntax, quoting/escape behavior, Unicode normalization policy, duplicate-key detection before object construction, and whether YAML merge keys are rejected with aliases. State whether ordering is semantically irrelevant in YAML and whether a canonical serialization is required for metadata bytes. Metadata remains outside `map_content_hash` regardless.

### 2.2 Evidence-reference proposal

**PROPOSED_FOR_USER_DECISION:** Use one typed immutable reference object, for example:

```yaml
repository: https://github.com/<owner>/<repository>.git
commit: <full immutable commit SHA>
path: <repository-relative path>
sha256: <lowercase 64-hex SHA-256 of referenced bytes>
```

Validation would resolve the exact commit, read the exact path at that commit, recompute the SHA-256, and reject mutable branch/tag-only references. For evidence outside Git, User must decide an immutable URI plus digest and retrieval policy. This reference format is a proposal; it is not currently authorized.

### 2.3 Lifecycle and navigation proposal

**PROPOSED_FOR_USER_DECISION:** Permit all five lifecycle states to be stored as immutable repository records, but allow navigation use only for `approved`, after identity, file hashes, manifest, and approval evidence validate. `draft`, `pending_review`, `rejected`, and `superseded` remain non-effective. Unknown/missing state or malformed evidence fails closed. Retain rejected and superseded records rather than deleting them.

| State | May be stored? | Navigation-effective? | Evidence question for User |
|---|---:|---:|---|
| `draft` | Yes, proposal | No | May approval evidence be null? Is source/creation evidence still required? |
| `pending_review` | Yes | No | Must a review-request record be pinned? Is that different from approval evidence? |
| `approved` | Yes | Only after all validation passes | Require immutable approval record with principal, role, decision, artifact identity/hash, and date? |
| `rejected` | Yes, historical | No | Require immutable rejection reason/decision reference? |
| `superseded` | Yes, historical | No | Require immutable reference to successor and supersession decision? |

The ACR does not say whether `approval_evidence` is non-null in every state. Its required-group wording suggests a reference is required, while fail-closed wording permits an artifact to remain non-effective when evidence is absent. The User must resolve whether draft/pending artifacts may encode `approval_evidence: null`; this packet does not decide that point.

### 2.4 Exact nested-key proposal for User review

The following names illustrate one deterministic v1 shape. They are **PROPOSED_FOR_USER_DECISION** and must not be treated as accepted schema:

```yaml
schema: mecanum_map_metadata/v1
map_id: <string>
artifact_identity: <opaque immutable string>
classification: static_occupancy_map
source_provenance:
  - source_ref: <immutable source reference>
    evidence_ref: <immutable evidence reference>
    raw_sha256: <optional lowercase 64-hex digest>
    provenance_kind: <proposed enum including USER_ATTESTED>
custody_approval:
  map_custodian:
    role: MapCustodian
    principal: <stable principal identifier>
    delegation_evidence: <reference or null>
  approver:
    role: MapApprover
    principal: <stable principal identifier>
    delegation_evidence: <reference or null>
  approval_status: <one allowed lifecycle value>
  approval_evidence: <reference or null, nullability pending User decision>
world_frame:
  state: NOT_DECLARED
  evidence_ref: <reference or null>
runtime_compatibility:
  state: NOT_VALIDATED
  evidence_ref: <reference or null>
history:
  artifact_identity: <same immutable identity>
  predecessor_ref: <reference or null for first instance>
  supersession_ref: <reference or null>
```

Before accepting such a shape, decide whether `principal` is a stable ID, a human-readable name, or both; how default Project Owner/User roles are represented without asserting a specific person's identity; whether delegated actors need separate principal and delegation fields; and whether nulls differ from omitted keys. Exact object shape, requiredness, and null semantics must be normative if unknown fields are rejected.

## 3. Activation and change control

| Claim | Evidence class | What is directly established |
|---|---|---|
| Remote integration equals `401593a…` | SOURCE_FACT | `git ls-remote` returned the exact required integration ref. |
| Exact candidate is on integration | SOURCE_FACT | The remote ref points to exact commit `401593a…`; this proves Git state only. |
| Candidate audit passed | USER_SUPPLIED | Verdict and report name were supplied in conversation; report file/hash was not found in the candidate or integration tracked tree. |
| Exact commit was separately User-authorized | USER_SUPPLIED | The prior explicit User decision authorized fast-forward of `401593a…`; the message is conversation evidence, not a repository-pinned approval file. |
| ACR/decision/Registry activation is recorded | SOURCE_FACT | No: each still has candidate/pending wording at this base. |
| Schema is active | Not established by these document states | Do not infer solely from integration presence; reconcile the static status records through change control. |

**PROPOSED_FOR_USER_DECISION — activation options:**

1. **Record the already completed activation conditions:** accept the conversation-supplied audit verdict and exact User authorization as evidence; create a later append-only status correction that pins the exact commit, audit provenance, authorization provenance, and verified remote ref; update current ACR/decision/Registry state without deleting historical wording; append to Ledger. This does not approve a map instance.
2. **Require repository-pinned audit evidence first:** keep schema non-operative until the audit report or an immutable audit record is available and independently traceable; then use a separate audited status-correction candidate. Do not repeat the fast-forward of `401593a…`.
3. **Defer activation determination:** leave existing candidate/pending wording in force and perform no canonical map preparation until the User supplies a further decision and evidence route.

The User should confirm which evidence sources are acceptable and whether option 1 is authorized. The packet makes no activation transition and does not authorize any status change.

## 4. Consolidated decisions requested

The User can decide or defer the following independently where safe:

1. **Activation record:** accept conversation-supplied audit/authorization evidence for exact `401593a…`, require a repository-pinned audit record, or defer; choose the append-only correction path and fields.
2. **Identity/version:** define `artifact_identity` type/grammar/generation and uniqueness scope; decide if `artifact_version` is a separate field or if the ACR's single identity key is sufficient.
3. **Source provenance:** approve exact record keys, reference format, hash pairing, attestation vocabulary, ordering, and whether date/actor are required.
4. **Custody and approval:** define actor object keys/types/principal representation, role inheritance, delegation evidence, self-approval record, authoritative status location, and immutable evidence-reference format.
5. **Lifecycle evidence:** decide nullability and evidence rules for `draft`, `pending_review`, `approved`, `rejected`, and `superseded`; approve the transition graph and evidence needed for rejection/supersession.
6. **World/frame:** confirm the five ACR states; define exact keys, evidence schema, null rules, and approver evidence. `NOT_DECLARED` can safely defer any equivalence claim if encoded unambiguously.
7. **Runtime compatibility:** define allowed states and evidence shape. `NOT_VALIDATED` can safely defer runtime claims if encoded unambiguously; it never implies navigation readiness.
8. **History:** define predecessor/successor keys, null representation for first identity, supersession link semantics, and retention/immutability checks.
9. **Parser profile:** define restricted YAML 1.2 subset, null/boolean/numeric types, duplicate-key detection, and whether metadata needs canonical serialization. Preserve the already-active map-hash boundary.

**Decisions already recorded:** the map-hash RFC 8785 rule and two-file hash boundary; the schema proposal's high-level lifecycle vocabulary, default world/frame and runtime states, role defaults, and fail-closed intent. These high-level decisions do not supply all nested metadata keys or evidence formats.

**Audit and integration:** candidate `401593a…` is integrated at the verified remote ref. The audit PASS and exact User authorization are present in conversation history; the audit report itself was not directly available in the tracked trees inspected for this packet. ACR, decision record, and Registry at the base still state candidate/pending. The User must decide how to record that discrepancy; this packet does not resolve it.

**Safe deferrals:** world/frame equivalence, runtime compatibility, pose graph, scenario, goals, zones, randomization, and navigation use can remain unclaimed. A draft instance is not safely creatable until its exact metadata key/type/null/evidence rules are normative and the schema activation state is reconciled.

## 5. Scope and status boundary

This packet changes no canonical authority and does not create any `artifacts/maps/**` file. It does not select a source, `map_id`, world/frame relationship, scenario, runtime profile, or concrete artifact. It computes no new map hash. It makes no WP status/dependency transition and grants no code, runtime, HIL, hardware, motor-enable, `deploy_sim`, or `deploy_real` authority.

WP-05 remains `OPEN`; `CODE_AUTHORIZATION: NOT_GRANTED`; `RUNTIME_APPROVED: NOT_APPROVED`.
