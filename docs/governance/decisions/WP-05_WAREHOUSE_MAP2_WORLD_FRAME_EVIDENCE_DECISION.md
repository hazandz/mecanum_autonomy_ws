# WP-05 `warehouse_map2` World-Frame Declaration Evidence Decision

**State:** replacement candidate only; pending consolidated independent audit, separate User authorization for this exact candidate, fast-forward, and remote-ref verification.

## Purpose and provenance

This candidate proposes a narrow immutable evidence-record shape for a future `world_frame: DECLARED_UNVERIFIED` metadata reference and carries one record for the existing `warehouse_map2` draft subject. It does not modify map metadata or manifest. Project Owner/User decisions are `USER_SUPPLIED_DECISION`; the source-world Git pin identifies SDF bytes only.

- Current integration base and sole candidate parent: `0b2fcd1d010bc30f54d7621e6192dd76339df6b2`
- Current replacement branch: `wp-05-world-frame-evidence-governance-correction-0b2fcd1`
- Source review candidate: `wp-05-world-frame-evidence-registry-reconciliation-e89aeda5@0f42f1c9da00725c36500ff4ec1d2f75a0c8709a`, parent `e89aeda5ca78859bfeedac4e7b94bcd6c7dcc7f0`; pushed to the remote review branch, not integrated
- Source-candidate audit: `CORRECTION_REQUIRED` (`USER_SUPPLIED_EVIDENCE`); no audit-report hash is asserted
- Earlier source-only candidate: `wp-05-world-frame-evidence-schema-record-e89aeda5@ca0432366da500ed549f71f96b51434b706772ef`, local/unpushed provenance only, not authority and not an audit PASS
- Superseded review candidate: `37cf785c1a567baf14e511f7f8ce869cca785a5b`; not integrated, and its metadata changes are not carried forward
- Map subject: `warehouse_map2`, artifact identity `4a8a23d0-7e27-4a50-8201-dd1abf1a3db4`
- Map content hash: `2bd9ff0a40eaeb61c2359aab4bb213da623ab56746debe591edd4a54c2229f90`
- Evidence record path: `docs/governance/evidence/WP-05_WAREHOUSE_MAP2_WORLD_FRAME_DECLARATION.json`
- Evidence record SHA-256: `4002e9cd93363f488eb92149d51ca60598922ac11bf252720b8b01a245407294` (source-candidate bytes; not yet integrated)
- Source world: `ros2_ws/src/ROBOT_URDF_final_description/launch/tugbot_depot.sdf`
- Source-world Git pin: repository `https://github.com/hazandz/mecanum_autonomy_ws.git`, commit `e89aeda5ca78859bfeedac4e7b94bcd6c7dcc7f0`, SHA-256 `a4b6253340baa866d89640d62a94d04fbea51425e9af1deca591422a0a36d91d`
- Historical refresh base `572da885d31d98929a1f8b8af4420012f1786fd6` is provenance only, not the current integration base or current WP-05 candidate.

This replacement is based directly on `0b2fcd1d010bc30f54d7621e6192dd76339df6b2`. It ports relevant declaration-evidence content without cherry-picking, merging, or rebasing the source candidate. The source candidate's audit finding is User-provided evidence, not a Git-verifiable report.

## Record schema and sufficiency

The candidate ACR addition defines `mecanum_map_world_frame_declaration_evidence/v1` as an exact RFC 8785 JCS/UTF-8/no-BOM/no-final-newline JSON object with six groups: `schema`, `subject`, `declaration`, `source_world`, `decision_provenance`, and `limitations`. Exact keys, types, constants, Git-pin validation, rejection rules, and immutability requirements are specified in candidate ACR §3.4.1. The record identifies the exact map subject and declaration decision. `decision_provenance` labels the association `USER_SUPPLIED_DECISION`; the Git pin scope is `SOURCE_WORLD_BYTES_ONLY` and does not independently prove that association.

The source-world file does not prove that the map was created from it. That association is User-supplied. The record makes no `map == world`, identity-transform, metric-alignment, or measured/validated `world → map` claim. Limitation flags for equivalence, transform, runtime validation, and map approval remain false.

This record is sufficient only to identify the subject and User-supplied declaration decision for `DECLARED_UNVERIFIED`. It is not evidence for `EVIDENCE_RECORDED` or `VALIDATED`. The future metadata `evidence_ref` can pin this exact record only after the record candidate is integrated. No metadata state transition occurs in this work package.

## Governance findings and correction scope

The audit findings supplied by the User are addressed as follows:

1. PEP-001's static snapshot is corrected to state that a `warehouse_map2` draft artifact is present while no approved/navigation-ready map is selected.
2. The prior Ledger wording is preserved as history; this candidate appends the later successful review-branch push event and the `CORRECTION_REQUIRED` verdict as User-supplied audit evidence. Candidate `0f42f1c…` remains unintegrated and did not activate the evidence record or metadata transition.
3. Candidate `0f42f1c…` is identified as the prior remote review candidate with `CORRECTION_REQUIRED`; this replacement awaits its own independent audit and separate exact-candidate authorization/integration.
4. The `572da885…` refresh is identified as historical provenance, not the current integration base or current WP-05 candidate.

## Artifact and authorization boundaries

At current integration base `0b2fcd1d010bc30f54d7621e6192dd76339df6b2`, `artifacts/maps/warehouse_map2/metadata.yaml` remains `world_frame.state: NOT_DECLARED`, `approval_status: draft`, and `runtime_compatibility.state: NOT_VALIDATED`. This candidate leaves all four map artifact files and `map_content_hash` unchanged. The declaration evidence record does not approve the map, assert runtime compatibility, establish navigation readiness, or authorize navigation.

The evidence schema and record proposed here become integration-resident only after audit of this exact replacement, separate User authorization, fast-forward, and remote-ref verification. A later separate phase may update metadata to reference the integrated record.

No scenario, code, runtime, HIL, hardware, motor-enable, `deploy_sim`, or `deploy_real` authority is granted. WP-05 remains OPEN; WP-04 remains `BLOCKED_BY_CONTRACT`; Gate A structural primitives remain PASSED; Gate B remains NOT_STARTED.
