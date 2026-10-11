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

For the refreshed status-correction review, `wp-05-map-metadata-schema-activation-status-correction-d33b93d@e4add07d10eb4a616569d0f9a83f97493851ef04` is source/provenance only (sole parent `d33b93d3c6389872450f1a001e3073c61f355824`), not the current candidate or base. The refresh candidate is based on `572da885d31d98929a1f8b8af4420012f1786fd6`; it carries forward the historical activation facts for d33b93d and awaits its own focused audit and separate exact-commit User authorization. Audit and authorization claims are USER_SUPPLIED_EVIDENCE; Git refs verify ancestry and integration history only. No audit-report hash is asserted.

No map artifact or source is selected. No scenario, measurement, code, runtime, ROS, HIL, hardware, motor-enable, deploy_sim, or deploy_real authority is created. No WP status/dependency changes; WP-05 remains open and WP-04 is unchanged. CODE_AUTHORIZATION: NOT_GRANTED. RUNTIME_APPROVED: NOT_APPROVED.

## 5. `warehouse_map2` draft artifact and narrow schema clarifications — candidate only

The statement in §4 that no map source or instance was selected records the state at the integrated schema base before this subsequent User decision. For preparation of this review candidate, the Project Owner/User supplied the following decisions (`USER_SUPPLIED_DECISION`): use map ID `warehouse_map2` and the tracked source pair `ros2_ws/src/ROBOT_URDF_final_description/maps/warehouse_map2.yaml` and `ros2_ws/src/ROBOT_URDF_final_description/maps/warehouse_map2.pgm`; use MapCustodian principal `github:hazandz`; allow only `provenance_kind: git_source`; rewrite only the source YAML `image` reference from `warehouse_map2.pgm` to canonical `map.pgm`; generate one lowercase UUIDv4; include no pose graph; set `world_frame.state: NOT_DECLARED`, `runtime_compatibility.state: NOT_VALIDATED`, and `approval_status: draft`; do not claim SLAM provenance or use `tugbot_depot.sdf` as provenance. This user decision selects a review candidate only and does not approve the map.

At base `68174e714cbe8aab61880113496cd7ccd7f97f5d`, the exact source YAML SHA-256 is `28e5fdca66783b462946f13c51e6a46bbb2a1f38f0e80714a05569c7ab0ab0c1`; the exact source PGM SHA-256 is `32f8a3eb626ebddecc15843748de0db8c6f7adc1b45a5edc1b1b1886407aef55`. The source YAML image field was changed once from `warehouse_map2.pgm` to `map.pgm`; replacing that value back reconstructs the source bytes exactly. Source YAML digest: `28e5fdca66783b462946f13c51e6a46bbb2a1f38f0e80714a05569c7ab0ab0c1`. Resulting canonical `map.yaml` digest: `5073762401784f67e856b5018656ad869ecc26e723f85e5979054eadc7876a68`. The PGM is byte-identical to its pinned source.

Candidate artifact identity: `4a8a23d0-7e27-4a50-8201-dd1abf1a3db4`. The candidate YAML transformation changed only the bytes `image: warehouse_map2.pgm` to `image: map.pgm`; the source YAML was 136 bytes, the canonical YAML is 125 bytes, and inverse replacement reconstructs the full source byte sequence. Source YAML SHA-256 is `28e5fdca66783b462946f13c51e6a46bbb2a1f38f0e80714a05569c7ab0ab0c1`; canonical `map.yaml` SHA-256 is `5073762401784f67e856b5018656ad869ecc26e723f85e5979054eadc7876a68`. Source and candidate `map.pgm` are each 184839 bytes with SHA-256 `32f8a3eb626ebddecc15843748de0db8c6f7adc1b45a5edc1b1b1886407aef55`.

| Candidate file/evidence | Bytes | SHA-256 |
|---|---:|---|
| `map.yaml` | 125 | `5073762401784f67e856b5018656ad869ecc26e723f85e5979054eadc7876a68` |
| `map.pgm` | 184839 | `32f8a3eb626ebddecc15843748de0db8c6f7adc1b45a5edc1b1b1886407aef55` |
| `metadata.yaml` | 1914 | `44a3adf3a50d1e002c0fda0703dc605a6df2777928f922eab548dd939455bf5b` |
| RFC 8785 projection bytes for `map_content_hash` | — | `2bd9ff0a40eaeb61c2359aab4bb213da623ab56746debe591edd4a54c2229f90` |
| `map_content_hash` | — | `2bd9ff0a40eaeb61c2359aab4bb213da623ab56746debe591edd4a54c2229f90` |
| JCS-serialized `map_manifest.json` | 698 | `94795a8f2f92399b5ce8620b18ab8c5bfbc0af67bd7020ce3110ed1fc15c5df8` |

The projection uses the §48 order `map_yaml`, then `occupancy_image`; the same isolated `rfc8785==0.1.4` toolchain produced identical UTF-8 bytes on repeat, without BOM or trailing newline. Metadata and the complete manifest are excluded from `map_content_hash`; the manifest carries only the metadata descriptor and result hash outside its nested projection. This candidate-only record and its files do not make the instance active or approved. The clarification additions to the ACR and the instance selection remain pending this exact candidate's independent audit, separate User authorization for its exact commit, fast-forward, and remote-ref verification. Option A supersession event/index remains `PROPOSAL_ONLY` and is not applied. WP-05 remains OPEN; no code or runtime authority is granted.
