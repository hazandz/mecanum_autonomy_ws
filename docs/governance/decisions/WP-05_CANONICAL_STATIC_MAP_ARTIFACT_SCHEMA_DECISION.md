# WP-05 Canonical Static-Map Artifact Schema — Decision Record

**Record state:** ACTIVE_ON_INTEGRATION_EFFECTIVE_FROM_d33b93d3c6389872450f1a001e3073c61f355824
**Work package:** WP-05-UNIFIED-MAP-METADATA-SCHEMA-CHANGE-CONTROL
**Integration base:** 793514f8ff3c20c13bfe84bf0529295de4d4d0b4
**Candidate branch:** wp-05-unified-map-metadata-schema-change-control-793514f

## 1. User-supplied decisions and provenance

The Project Owner/User states that the nine metadata recommendation groups from the prior consolidated analysis are approved for this candidate. This record labels them USER_SUPPLIED_DECISION; it does not claim that the conversation or its audit statements are Git-pinned evidence. The User also explicitly selected Option A: approved metadata/artifact bytes and approval evidence remain immutable, and supersession uses an append-only event/index.

Source decision packet: wp-05-map-metadata-source-traceability-correction-4b21343@361966ececc3c0fde088bffe5ec2987af8f16014; path docs/WP-05_MAP_METADATA_SCHEMA_CLOSURE_DECISION_PACKET_DRAFT.md; SHA-256 9bd7c06683299d36b11ffebb0db372f67e24257ab9a2ebb0cc193ee18bb35bd4. Audit verdicts or User approval are not inferred from Git refs. No audit-report hash or unsupported provenance is asserted.

**Prior/source candidate provenance (stale; content source only):** `wp-05-unified-map-metadata-schema-change-control-7f9ed36@3892edf37ab5388fd38d3cf4a41d28ae2401782e`; parent `7f9ed36a10b5f4ab68eb437833f04d4842eff986`. The source candidate is not the current integration tip and is not treated as an integration candidate. This refresh has its own audit and separate exact-commit User authorization requirements; no prior audit or authorization is inferred.

Source file SHA-256 values: ACR `d14fd11ffa5725746d4ae4d783ae0e321d3991c2ae952c4cdcc8dd89f1da7eec`; decision record `c07a218ce5f712a56701ec92bcba902ed5d6d78579aea0f5bbff3e12c6f55f29`; Registry `f3649bb0e7fd652f1fb7c3689731247c69be4d522754a350eb84dd6d4b428aec`; Ledger `a6e57d7805e4c8993bb3d0d0b9fac7338cbabc0f63988e693dcf7211935aaf9e`. These digests identify the source candidate files, not the refreshed files.

## 2. Recorded metadata decisions

The candidate ACR records the accepted decisions for identity/version, source provenance, custody/approval actors, lifecycle/evidence principles, world/frame states, runtime compatibility states, predecessor history, and restricted YAML parsing. These decisions do not select any map source, map_id, actor identity, world/frame equivalence, runtime evidence, or artifact instance.

The active Architecture §48/RFC 8785 map-hash boundary is unchanged: only map.yaml and map.pgm enter map_content_hash; metadata, manifest result fields, pose graph, and hash result remain outside it. The RFC 8785 rule remains active independently of this candidate.

## 3. Supersession decision and pending details

USER_SUPPLIED_DECISION: Option A. The old approved metadata/artifact and approval evidence are immutable. Metadata is authoritative for that artifact’s approval decision. An append-only supersession event/index is the sole authority for predecessor/successor relations and effective/current disposition; it does not rewrite approval_status.

The ACR includes a deterministic PROPOSAL_ONLY event/index design and labels unresolved location/schema, completeness and append-only proof, approver/delegation/evidence, acceptance timing, cross-map_id rules, and consumer fail-closed scope as PENDING_OWNER_DECISION. It does not present those unresolved choices as approved or claim supersession is fully normative. The stored approval decision and derived effective disposition are distinct authority domains.

## 4. Candidate and activation boundary

The candidate-only wording in this record describes the pre-activation state when the exact candidate was under review. USER_SUPPLIED_EVIDENCE: the Project Owner/User supplied READINESS_FOR_USER_DECISION_TO_INTEGRATE: PASS and authorized integration of exact commit d33b93d3c6389872450f1a001e3073c61f355824. Git history confirms its sole parent is 793514f8ff3c20c13bfe84bf0529295de4d4d0b4, and the remote integration ref was verified at d33b93d3c6389872450f1a001e3073c61f355824. Therefore the map metadata schema status is ACTIVE_ON_INTEGRATION effective from d33b93d3c6389872450f1a001e3073c61f355824. No audit-report hash is asserted. Schema activation remains separate from approval of an individual map instance. This status correction changes no schema semantics; the correction candidate itself remains subject to its own focused audit and separate exact-commit User authorization before integration.

No map artifact or source is selected. No scenario, measurement, code, runtime, ROS, HIL, hardware, motor-enable, deploy_sim, or deploy_real authority is created. No WP status/dependency changes; WP-05 remains open and WP-04 is unchanged. CODE_AUTHORIZATION: NOT_GRANTED. RUNTIME_APPROVED: NOT_APPROVED.
