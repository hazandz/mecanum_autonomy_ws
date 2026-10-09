# WP-05 Canonical Static-Map Artifact Schema — Decision Record

**Record state:** `CANDIDATE_PENDING_FOCUSED_INDEPENDENT_AUDIT_AND_SEPARATE_USER_INTEGRATION_AUTHORIZATION`
**Work package:** `WP-05-UNIFIED-MAP-ARTIFACT-SCHEMA-CHANGE-CONTROL`
**Integration base:** `988a74b529fdb4bcf77f341db5c6d115e8511a9b`
**Candidate branch:** `wp-05-unified-map-artifact-schema-change-control-988a74b`

## 1. User decision

The Project Owner/User explicitly supplied:

`USER_DECISION: APPROVED_FOR_WP05_UNIFIED_MAP_ARTIFACT_SCHEMA_CHANGE_CONTROL`

This decision authorizes preparation of one unified documentation-only candidate with the exact four-path scope below. It approves the listed schema semantics for candidate preparation; it does not approve a map instance, select a map source, ID, world, frame, or scenario, authorize runtime/code, or close WP-05.

## 2. Candidate decision content

The proposed schema and activation contract is `docs/architecture/ACR_MAP_ARTIFACT_SCHEMA_AND_ACTIVATION.md`. It records the User-approved rules for:

- `map_id` grammar `^[a-z][a-z0-9_]{0,63}$`, repository-wide case-insensitive uniqueness under `artifacts/maps/`, exact directory-name match, collision rejection, approved-artifact immutability, and new identity/history for meaningful changes;
- strict UTF-8-no-BOM, single-document YAML 1.2 data-only `mecanum_map_metadata/v1`, custody/approval provenance, lifecycle states, immutable evidence, world/frame declarations, runtime-compatibility state, and fail-closed behavior;
- strict `mecanum_map_manifest/v1`, full-manifest RFC 8785 JCS serialization, exact §48 `mecanum_map_hash/v1` projection, metadata descriptor validation, and no self-reference or self-embedded signature/digest;
- default `NOT_DECLARED` world/frame relationship and `NOT_VALIDATED` runtime compatibility, each requiring separate immutable evidence before validation;
- omission of pose graph from the first canonical static-map artifact and separate schema/manifest/work-package/audit if later included;
- activation only after focused audit, separate exact-candidate user authorization, fast-forward, and remote-ref verification.

The content-hash boundary remains exactly `map.yaml` and `map.pgm` in §48 order and roles, under the RFC 8785 rule active at the integration base. Metadata descriptor, optional pose graph, full-manifest result fields, and resulting `map_content_hash` remain outside the digest input.

## 3. RFC 8785 activation reconciliation

The map-hash RFC 8785 clarification was integrated at `integration/implementation@988a74b529fdb4bcf77f341db5c6d115e8511a9b`. The earlier RFC decision record contains candidate-only wording from before that integration. This candidate reconciles the current Registry activation state and records the now-active RFC rule; it does not change the historical record's bytes or imply that this map-artifact schema or any map instance is active.

## 4. Exact scope and activation boundary

Only these paths belong to this unified candidate:

1. `docs/architecture/ACR_MAP_ARTIFACT_SCHEMA_AND_ACTIVATION.md`
2. `docs/governance/decisions/WP-05_CANONICAL_STATIC_MAP_ARTIFACT_SCHEMA_DECISION.md`
3. `docs/governance/CANONICAL_SOURCE_REGISTRY.md`
4. `docs/governance/PROJECT_PROGRESS_LEDGER.md`

The ACR and this record are candidate-only until this exact candidate passes focused independent audit, receives separate Project Owner/User authorization for integration, and is fast-forwarded with the remote integration ref verified. Schema activation is separate from selection, creation, validation, or approval of an individual map instance.

No `artifacts/maps/**` content is created. No `warehouse_map2`, map source, map ID, world/frame, scenario, goal/start/bounds/zones, seed/randomization value, pose graph, measurement, code, ROS/runtime, HIL, hardware, motor-enable, or deployment is selected or authorized. WP-05 remains open; WP-04 status/dependency is unchanged; `CODE_AUTHORIZATION: NOT_GRANTED`; `RUNTIME_APPROVED: NOT_APPROVED`.
