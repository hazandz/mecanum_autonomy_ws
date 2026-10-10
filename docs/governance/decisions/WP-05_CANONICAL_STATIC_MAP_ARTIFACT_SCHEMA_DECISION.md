# WP-05 Canonical Static-Map Artifact Schema — Decision Record

**Record state:** CANDIDATE_PENDING_FOCUSED_INDEPENDENT_AUDIT_AND_SEPARATE_USER_INTEGRATION_AUTHORIZATION
**Work package:** WP-05-UNIFIED-MAP-METADATA-SCHEMA-CHANGE-CONTROL
**Integration base:** 7f9ed36a10b5f4ab68eb437833f04d4842eff986
**Candidate branch:** wp-05-unified-map-metadata-schema-change-control-7f9ed36

## 1. User-supplied decisions and provenance

The Project Owner/User states that the nine metadata recommendation groups from the prior consolidated analysis are approved for this candidate. This record labels them USER_SUPPLIED_DECISION; it does not claim that the conversation or its audit statements are Git-pinned evidence. The User also explicitly selected Option A: approved metadata/artifact bytes and approval evidence remain immutable, and supersession uses an append-only event/index.

Source decision packet: wp-05-map-metadata-source-traceability-correction-4b21343@361966ececc3c0fde088bffe5ec2987af8f16014; path docs/WP-05_MAP_METADATA_SCHEMA_CLOSURE_DECISION_PACKET_DRAFT.md; SHA-256 9bd7c06683299d36b11ffebb0db372f67e24257ab9a2ebb0cc193ee18bb35bd4. Audit verdicts or User approval are not inferred from Git refs. No audit-report hash or unsupported provenance is asserted.

## 2. Recorded metadata decisions

The candidate ACR records the accepted decisions for identity/version, source provenance, custody/approval actors, lifecycle/evidence principles, world/frame states, runtime compatibility states, predecessor history, and restricted YAML parsing. These decisions do not select any map source, map_id, actor identity, world/frame equivalence, runtime evidence, or artifact instance.

The active Architecture §48/RFC 8785 map-hash boundary is unchanged: only map.yaml and map.pgm enter map_content_hash; metadata, manifest result fields, pose graph, and hash result remain outside it. The RFC 8785 rule remains active independently of this candidate.

## 3. Supersession decision and pending details

USER_SUPPLIED_DECISION: Option A. The old approved metadata/artifact and approval evidence are immutable. Metadata is authoritative for that artifact’s approval decision. An append-only supersession event/index is the sole authority for predecessor/successor relations and effective/current disposition; it does not rewrite approval_status.

The ACR includes a deterministic PROPOSAL_ONLY event/index design and labels unresolved location/schema, completeness and append-only proof, approver/delegation/evidence, acceptance timing, cross-map_id rules, and consumer fail-closed scope as PENDING_OWNER_DECISION. It does not present those unresolved choices as approved or claim supersession is fully normative. The stored approval decision and derived effective disposition are distinct authority domains.

## 4. Candidate and activation boundary

This four-path documentation candidate is not active until this exact candidate passes focused independent audit, receives separate Project Owner/User authorization for integration, is fast-forwarded to integration/implementation, and the remote ref is verified. Schema activation remains separate from approval of an individual map instance.

No map artifact or source is selected. No scenario, measurement, code, runtime, ROS, HIL, hardware, motor-enable, deploy_sim, or deploy_real authority is created. No WP status/dependency changes; WP-05 remains open and WP-04 is unchanged. CODE_AUTHORIZATION: NOT_GRANTED. RUNTIME_APPROVED: NOT_APPROVED.
