# WP-05 `warehouse_map2` sim_eval static approval evidence decision

## Classification and source-base snapshot

- Change class: `L2_MAP_APPROVAL_EVIDENCE_SCHEMA_AND_STATIC_SELECTION_DECISION`.
- Exact source-base snapshot: `7fe8b24758636dcac540b33a73bf5e3b7febbe6b`.
- Current Architecture authority: `docs/MECANUM_NAV_DRL_Architecture.docx`, SHA-256 `432eeac363a595cfcf7e81c4b66054fb674dba140a2ef3cffecd617ab8136204`.
- Candidate state before the required audit and integration conditions: review candidate only.

## Exact map subject and owner decision

The Owner-selected static map artifact for target `sim_eval + NAV2_BASELINE` is exactly `warehouse_map2` at `artifacts/maps/warehouse_map2/`:

| Field | Exact value |
|---|---|
| `map_id` | `warehouse_map2` |
| `artifact_identity` | `4a8a23d0-7e27-4a50-8201-dd1abf1a3db4` |
| `map_content_hash` | `2bd9ff0a40eaeb61c2359aab4bb213da623ab56746debe591edd4a54c2229f90` |
| `map.yaml` SHA-256 | `5073762401784f67e856b5018656ad869ecc26e723f85e5979054eadc7876a68` |
| `map.pgm` SHA-256 | `32f8a3eb626ebddecc15843748de0db8c6f7adc1b45a5edc1b1b1886407aef55` |

The exact-subject approval-evidence schema and values in `docs/governance/evidence/WP-05_WAREHOUSE_MAP2_SIM_EVAL_STATIC_APPROVAL.json` record the Owner's decision. Approval scope is only `SIM_EVAL_NAV2_BASELINE_STATIC_MAP_ARTIFACT_SELECTION`. A future Map Server may bind only to `artifacts/maps/warehouse_map2/map.yaml`; a ROS-package map copy is not selected.

This evidence record does not alter map bytes, identity, or `map_content_hash`. At this source base, map metadata remains `approval_status: "draft"`, `world_frame.state: "NOT_DECLARED"`, and `runtime_compatibility.state: "NOT_VALIDATED"`.

## Candidate lifecycle and boundary

Candidate 4A becomes active only after independent audit PASS for the exact candidate, separate User authorization for that exact candidate, fast-forward integration, and remote-ref verification. After activation, only the approval-evidence record becomes integration-resident immutable evidence; map metadata remains `draft`.

Candidate 4B may reference this evidence from its exact integrated base and separately change metadata from `draft` to `approved`. Candidate 4B may also, but is not required to, set `world_frame.state` to `DECLARED_UNVERIFIED` by referencing the existing `docs/governance/evidence/WP-05_WAREHOUSE_MAP2_WORLD_FRAME_DECLARATION.json`. Candidate 4A does neither.

This decision does not claim that the map is navigation-ready, a profile is resolved, Map Server has loaded the map, AMCL is active, map and world are equivalent, TF is valid, or runtime compatibility has been established. It grants no runtime authority, provides no map-loading evidence, does not resolve a profile, emit `config_hash`, or close WP-05.

No self-hash, commit self-pin, timestamp, signature, map image bytes, or runtime result is part of the evidence JSON.
