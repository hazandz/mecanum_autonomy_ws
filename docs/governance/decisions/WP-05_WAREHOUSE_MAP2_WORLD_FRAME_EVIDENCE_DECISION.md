# WP-05 `warehouse_map2` World-Frame Declaration Evidence Decision

**State:** candidate-only; pending consolidated independent audit, separate User authorization for the exact candidate, fast-forward, and remote-ref verification.

## Purpose and provenance

This candidate defines a narrow immutable evidence-record shape for a future `world_frame: DECLARED_UNVERIFIED` metadata reference and supplies one record for the selected `warehouse_map2` subject. It does not modify the map metadata or manifest. The Project Owner/User decisions below are `USER_SUPPLIED_DECISION`; the source-world Git pin identifies SDF bytes only.

- Integration base: `e89aeda5ca78859bfeedac4e7b94bcd6c7dcc7f0`
- Map subject: `warehouse_map2`, artifact identity `4a8a23d0-7e27-4a50-8201-dd1abf1a3db4`
- Map content hash: `2bd9ff0a40eaeb61c2359aab4bb213da623ab56746debe591edd4a54c2229f90`
- Evidence record path: `docs/governance/evidence/WP-05_WAREHOUSE_MAP2_WORLD_FRAME_DECLARATION.json`
- Evidence record SHA-256: `4002e9cd93363f488eb92149d51ca60598922ac11bf252720b8b01a245407294` (candidate bytes; not an integrated Git reference)
- Source world: `ros2_ws/src/ROBOT_URDF_final_description/launch/tugbot_depot.sdf`
- Source-world Git pin: repository `https://github.com/hazandz/mecanum_autonomy_ws.git`, commit `e89aeda5ca78859bfeedac4e7b94bcd6c7dcc7f0`, SHA-256 `a4b6253340baa866d89640d62a94d04fbea51425e9af1deca591422a0a36d91d`

The replacement candidate is branch `wp-05-world-frame-evidence-registry-reconciliation-e89aeda5`, based on `e89aeda5ca78859bfeedac4e7b94bcd6c7dcc7f0`. Its content source is the local, unpushed review candidate `wp-05-world-frame-evidence-schema-record-e89aeda5@ca0432366da500ed549f71f96b51434b706772ef`, whose sole parent is the same base. That source candidate was not integrated and is not treated as authority or as having passed audit. The replacement reconciles Registry wording and preserves the evidence record and decision semantics; this candidate itself remains pending independent local audit.

The prior review candidate `37cf785c1a567baf14e511f7f8ce869cca785a5b` is superseded review provenance and is not integrated. Its metadata changes are not carried into this candidate.

## Record schema and sufficiency

The candidate ACR defines `mecanum_map_world_frame_declaration_evidence/v1` as an exact RFC 8785 JCS/UTF-8/no-BOM/no-final-newline JSON object with six groups: `schema`, `subject`, `declaration`, `source_world`, `decision_provenance`, and `limitations`. Exact fields, types, constants, Git pin validation, rejection rules, and immutability requirements are in ACR §3.4.1. The record identifies the exact map subject and decision. `decision_provenance` explicitly labels the map-to-world/SLAM association `USER_SUPPLIED_DECISION` and scopes the Git pin to source-world bytes only.

The source-world file does not prove that the map was created from it. That association is User-supplied. The record makes no `map == world`, identity-transform, metric-alignment, or measured/validated `world → map` claim. Its limitation flags are all false for equivalence, transform, runtime validation, and map approval.

This record is sufficient only for `DECLARED_UNVERIFIED`; it is not evidence for `EVIDENCE_RECORDED` or `VALIDATED`. The future metadata `evidence_ref` must pin this exact record by an immutable Git reference after the evidence-record candidate is integrated. No metadata state transition occurs in this work package.

## Artifact and authorization boundaries

At the integration base, `artifacts/maps/warehouse_map2/metadata.yaml` remains `world_frame.state: NOT_DECLARED`, `approval_status: draft`, and `runtime_compatibility.state: NOT_VALIDATED`. This candidate changes none of those bytes, the map files, manifest, or `map_content_hash`. The record does not approve the map, assert runtime compatibility, or authorize navigation.

The evidence schema and record become integration-resident authority only after this exact candidate passes independent audit, receives separate User authorization, is fast-forwarded, and the remote integration ref is verified. A later, separate phase may update metadata to reference this integrated record.

No scenario, code, runtime, HIL, hardware, motor-enable, `deploy_sim`, or `deploy_real` authority is granted. WP-05 remains OPEN; WP-04 remains `BLOCKED_BY_CONTRACT`; Gate A structural primitives remain PASSED; Gate B remains NOT_STARTED.
