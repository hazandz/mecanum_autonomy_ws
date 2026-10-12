# Canonical Source Registry — Mecanum Nav2 DRL

## Registry role

This registry identifies operational source selection. It does not override MECANUM_NAV_DRL_Architecture.docx, approved ACRs or explicit user decisions.

## Canonical QoS6 / ACR8 bundle

The Project Owner/User-approved QoS revision 6 / ACR revision 8 bundle was
integrated at `origin/integration/implementation@2e7a2980cb75f0567182ea694c04328d7d8643e0`.
The Registry entries below record its active document/interface/manifest pins.
The change records contract identity and pins only; it does not close WP-03 or
WP-04, change dependencies, or authorize code/runtime. Historical QoS5/ACR7
approval and v1 pins remain preserved.

## WP-03 authorized dispositions and closure activation

The decision record is `docs/governance/decisions/WP-03_CONTRACT_CLOSURE_DECISIONS.md`.
Its disposition source is packet branch `wp-03-decision-packet-baseline-2e7a2980`,
commit `473d1cc6265dc14230fa47a89546b14a9de2a6eb`, packet SHA-256
`3559f21a07520f10ac1dceb0c2e6f888597a0215a63a5b8b91fce10d340e583c`. The
seven-path reconciliation at `wp-03-decision-contract-reconciliation-2e7a2980`
commit `b234c2fe5831c1a0ea3c2b1805a5715773d6d2a6` passed `INDEPENDENT_FOCUSED_STATIC_AUDIT_WP03_DECISION_CONTRACT_RECONCILIATION_B234C2FE.md`
(SHA-256 `7db8347459af8762da1b74afd99c765a9121e43c2453363049c3f00c0256110f`). PEP-001 rev.0.4.0 controls activation: WP-03 is
`BLOCKED_BY_CONTRACT` until the exact reviewed final candidate is fast-forwarded
to `integration/implementation` and the remote ref is verified; after activation
its status is `CLOSED`. The transition closes only WP-03 contract dispositions;
it does not assert runtime or physical evidence or authorize implementation.

## WP-04 Gate A structural-schema activation reconciliation — active source selection

The exact structural schema `docs/OBSERVATION_GATE_A_STRUCTURAL_SCHEMA.md`
(full-document SHA-256
`43537b8f0edafbe809e6f70bda86808f87b12f146ed45509c4bfbacd26956ad3`) was
introduced in the exact-schema candidate ancestry and its receipt-selector
attribution was corrected by
`wp-04-gate-a-receipt-selector-attribution-correction@f9987be4429349ef9110c45cf97a89728a5e4229`.
Its focused re-audit report
`INDEPENDENT_FOCUSED_STATIC_REAUDIT_WP04_F01_RECEIPT_SELECTOR_ATTRIBUTION_F9987BE4.md`
(SHA-256
`6902ebce5ec874a5922e06c2623cba7edb09083f493d7aa8242ecc715c1f60c5`)
reported PASS. The Project Owner/User explicitly authorized integration of
that exact candidate. Its commit is an ancestor of the current integration
base `401593a4268af572ef4690177539360b1c15410a`, and the schema bytes at that
base match the pinned full-document hash. These audit, authorization,
ancestry, and byte-identity facts establish the schema's active Registry
source-selection status as of that base.

The schema file's embedded candidate-status wording and its SHA remain
unchanged as pre-integration document history. This Registry reconciliation
supersedes that wording only as to activation/source-selection status; it does
not alter schema semantics, close WP-04, pass Gate A, or grant implementation
or runtime authorization. The separate error-carrier decision record and
refreshed implementation-authorization packet in the current review bundle
remain candidate-only until this exact bundle passes independent audit,
receives separate explicit user authorization for its final commit, and is
fast-forwarded with the remote ref verified.

## Registry entries

| Source/path | Classification | Permitted use |
|---|---|---|
| docs/MECANUM_NAV_DRL_Architecture.docx | ARCHITECTURE_AUTHORITY | Highest architecture authority |
| docs/RECEIPT_TOPIC_QOS_CONTRACT.md | CANONICAL_APPROVED_DESIGN_CONTRACT | Receipt Topic QoS Contract revision 6; full-document SHA-256 `4200cd2fbdc81a19400f168dd3526eb7871ac2251049fc7c4f5d5c2fddfd2022`; transport identity `mecanum.final-issued-receipt-topic-qos/v2` / `338bea1b7350d3b82146c7e728516ec7947471ee68db0f8871ddb72071b79620`; QoS policy values and transport behavior unchanged; design-contract scope only, no code/runtime authorization |
| docs/ACR_V3_OBSERVATION_BOUNDARY_CLOSURE.md | CANONICAL_APPROVED_ACR | ACR revision 8; full-document SHA-256 `03fef021f6b9731f811f83a5e53aae1c430bdc2ea76815a8ada416f1a5bf772c`; approved Gate A/Gate B scope carried forward; no WP-03 closure or dependency/status changes |
| docs/governance/decisions/QOS_REVISION_6_ACR_REVISION_8_BUNDLE_APPROVAL.md | CANONICAL_GOVERNANCE_APPROVAL_RECORD | Project Owner/User approval dated 2026-10-08; approval-record SHA-256 `4d740559f850f179387db802df845748068f75a21266fd1edb52402b2c72c529`; exact QoS6/ACR8, interface v2, dependency-closure and transport-v2 pins recorded; governs canonical document/status activation only after exact candidate integration; no code/runtime authorization or WP status/dependency change |
| docs/OBSERVATION_GATE_A_STRUCTURAL_SCHEMA.md | CANONICAL_APPROVED_GATE_A_STRUCTURAL_SCHEMA | Full-document SHA-256 `43537b8f0edafbe809e6f70bda86808f87b12f146ed45509c4bfbacd26956ad3`; audited correction `wp-04-gate-a-receipt-selector-attribution-correction@f9987be4429349ef9110c45cf97a89728a5e4229`, user-authorized and integrated by the stated base; structural contract source only, no Gate A pass or code/runtime authorization |
| docs/OBSERVATION_V3_SPECIFICATION.md | CANONICAL_INTEGRATED_GATE_B_GOVERNANCE_SPECIFICATION | Revision 3; integrated governance amendment source commit `d87b5a17ca0e9430d0b163aacf5b9cfcc4458d14`, present at current integration base `410d9cb70518b64d3c76c2ef99b11b69d1da6701`; Architecture DOCX remains higher authority. Revision 2 is superseded historical review provenance. No Gate B pass, implementation, or runtime authority |
| docs/governance/decisions/WP-04_GATE_B_CONSOLIDATED_DECISION.md | CANONICAL_GOVERNANCE_BOUNDARY_DECISION | Integrated boundary decision at base; full-document SHA-256 `49c96beb9c317a930a2af33c94e172f3c8b5beb9e797378820e77b60dc959992`; revision-2 correction is superseded historical review provenance, not the current candidate or active decision |
| docs/governance/decisions/QOS_REVISION_5_ACR_REVISION_7_BUNDLE_APPROVAL.md | HISTORICAL_GOVERNANCE_APPROVAL_RECORD | Prior user-approved bundle dated 2026-10-06; historical QoS5/ACR7 and receipt-interface/transport v1 pins retained; not current source selection after this candidate is integrated |
| AGENTS.md | EXECUTION_GOVERNANCE | Codex work rules; not architecture authority |
| docs/MECANUM_NAV_DRL_Project_Tree.txt | PROJECT_STRUCTURE_AUTHORITY | Expected project layout; not architecture override |
| ros2_ws/src/mecanum_nav_rl/config/v3/** | APPROVED_FOR_CORE | Only permitted config-input family for new canonical/offline implementation; effective composition remains caller-owned and contract-bound |
| ros2_ws/src/mecanum_nav_rl/config/base.yaml and config/profiles/** outside V3 | PRE_V3_NONCANONICAL | Historical/reference only unless explicit decision changes status |
| ros2_ws/src/mecanum_nav_rl/** pure core | IMPLEMENTED_CORE_PENDING_P0_REMEDIATION | Reuse only through approved work packages |
| ros2_ws/src/mecanum_nav_rl_interfaces/msg/** | CANONICAL_INTERFACE_CONTRACT | Typed interface source; changes require contract review |
| ros2_ws/src/mecanum_nav_rl_interfaces/msg/FinalIssuedCommandReceipt.msg | CANONICAL_INTERFACE_CONTRACT | Receipt interface v2; SHA-256 `0c6446674bf17373ec646519043f506a9a7a15f95d5fdd10829b0cedb956500a`; typed contract source only, not ROSIDL build or implementation authorization |
| docs/RECEIPT_INTERFACE_DEPENDENCY_CLOSURE_MANIFEST.json | CANONICAL_INTERFACE_DEPENDENCY_CLOSURE_MANIFEST | Closure version 1; SHA-256 `0872fa8c10179f69c2e9e9546392ac734a4f4e94ade176a8be431f06905ecf73`; pins transitive message-definition provenance |
| docs/RECEIPT_TOPIC_QOS_TRANSPORT_MANIFEST.json | CANONICAL_TRANSPORT_MANIFEST | Transport ID `mecanum.final-issued-receipt-topic-qos/v2`; SHA-256 `338bea1b7350d3b82146c7e728516ec7947471ee68db0f8871ddb72071b79620`; byte-identical to QoS revision 6 §4 manifest |
| ros2_ws/src/mecanum_base_bridge/** | CODEC_CORE_ONLY | Codec/diagnostic evidence only; not serial/ROS/odometry runtime |
| firmware_STM32/** | FIRMWARE_SOURCE_PENDING_OFFLINE_AND_HIL_EVIDENCE | Firmware implementation work only under contract/hardware approval |
| ros2_ws/src/ROBOT_URDF_final_description/urdf/**, meshes/**, models/** | ROBOT_GEOMETRY_SIMULATION_SOURCE | Geometry/simulation source; not proof of official runtime control profile |
| ros2_ws/src/ROBOT_URDF_final_description/ROBOT_URDF_final_description/mecanum_env.py | LEGACY_NONCANONICAL | Excluded from official runtime/architecture evidence |
| ros2_ws/src/ROBOT_URDF_final_description/ROBOT_URDF_final_description/train_ai.py | UNCLASSIFIED_LEGACY_DEPENDENT | Not allowed as canonical training/runtime entrypoint pending explicit decision |
| artifacts/maps/<map_id> | CANONICAL_MAP_ARTIFACT_PRESENT_DRAFT_NOT_APPROVED | `artifacts/maps/warehouse_map2/` is integration-resident as a draft artifact. It is not approved, navigation-ready, or selected for navigation/localization. Do not use ROS-package map copies as canonical |
| artifacts/scenarios/<scenario_id>/scenario.json | APPROVED_SCENARIO_CONVENTION_NO_ARTIFACT_SELECTED | Authorized disposition selects immutable `scenario.json` serialized as `RFC8785_JCS_UTF8` under this root; Project Owner/User is ScenarioCustodian unless delegated. No scenario ID/values/artifact selected. `GT_ODOM_2D` is evaluator-only; raw GT is excluded from policy/observation core. WP-03 closure activation is governed by PEP-001 rev.0.4.0 |
| docs/governance/decisions/WP-03_CONTRACT_CLOSURE_DECISIONS.md | WP03_AUTHORIZED_DISPOSITION_AND_CLOSURE_RECORD | Project Owner/User-authorized D2, D3, map, scenario, hardware and routing dispositions; WP-03 closure activation follows PEP-001 rev.0.4.0 and requires the exact reviewed final candidate on integration/implementation |
| artifacts/hardware/<hardware_profile_id>/hardware_manifest.yaml | CANONICAL_LOCATION_PRESENT_VALIDITY_PENDING | Hardware source location exists; records Project Owner/User as Hardware Measurement Owner and Technical Approver unless a delegate is named; values/approval require separate evidence |
| artifacts/simulation/** historical reports/tools | HISTORICAL_OFFLINE_EVIDENCE | Audit/provenance only; never automatic runtime approval |
| docs/*DRAFT*, approval packet draft and legacy report | DRAFT_OR_HISTORICAL_EVIDENCE | Read for context; not implementation authority without approval |
| .venv/**, build/**, install/**, log/**, __pycache__/** | GENERATED_NONCANONICAL | Must not be introduced into future integration commits |

## Required source-selection rules

- A new work package must state which registry entries it reads and writes.
- If a source is DRAFT, HISTORICAL, LEGACY, NONCANONICAL, PENDING or MISSING, Codex must not treat it as runtime-ready or silently promote it.
- Missing canonical locations must be created only through an approved work package with provenance/hash rules; never by copying arbitrary legacy files.
- Changes to this registry require an explicit governance prompt and must include architecture/ACR impact analysis.

## WP-04 Gate B boundary activation and superseded revision-2 historical review provenance

The boundary-closure bundle from
`wp-04-gate-b-boundary-closure-decision-50476170@68174e714cbe8aab61880113496cd7ccd7f97f5d`
established the controlled Gate B boundary and selected specification
revision 1 at that historical integration point. Revision 3 was later
integrated as the current governance specification. This does not pass Gate B,
satisfy all six ACR8 Gate B implementation conditions, change WP
status/dependencies, or grant implementation/runtime authorization.

The earlier exact-data-contract review candidate
`wp-04-gate-b-exact-data-contract-change-control-68174e@687469f4aa2f166566e31aa91c1b1d90648c3812`
is superseded review provenance only. It was not integrated and is not active
source selection. Its five delivery hashes are retained in the PEP-001
replacement change-control record for traceability; they do not identify
current canonical artifacts.

Observation V3 Specification revision 2 is superseded historical review
provenance, not current content or active source selection.
Its exact source is
`wp-04-gate-b-exact-data-contract-completion-refresh-1e14644@e89aeda5ca78859bfeedac4e7b94bcd6c7dcc7f0`,
path `docs/OBSERVATION_V3_SPECIFICATION.md`, SHA-256
`ed06bc5bd145e0eb9376df71ff42ee60069906d987c78531ba8b9e688746b1bc`.
At historical base `68174e714cbe8aab61880113496cd7ccd7f97f5d`, revision 1 was
the active boundary source selection. Revision 3 from source commit
`d87b5a17ca0e9430d0b163aacf5b9cfcc4458d14` is present in integration ancestry
at current base `410d9cb70518b64d3c76c2ef99b11b69d1da6701` as the integrated
governance amendment described below. It does not modify the Architecture DOCX,
pass Gate B, or authorize implementation/runtime.

The correction source candidate
`wp-04-gate-b-exact-data-contract-completion-correction-68174e@73a1f73c39eb742e79f53f50d5b5d73b41be0822`,
parent `68174e714cbe8aab61880113496cd7ccd7f97f5d`, is source/provenance only.
It is not this candidate, was not integrated, and is not being amended or
repushed. The historical replacement branch
`wp-04-gate-b-exact-data-contract-completion-refresh-1e14644`, based on
`1e14644a7d778a0c5ad32512430d775fd0e8ecd3`, proposed the following five-path
documentation/governance bundle. These hashes are historical delivery
provenance and do not identify current artifacts. That review was superseded.
The revision-3 integrated governance amendment is tracked separately below.
Candidate-only wording in historical snapshots describes their state before
integration and is not the current source-selection status:

| Superseded revision-2 historical artifact | Path | Historical delivery SHA-256 |
|---|---|---|
| Observation V3 Specification revision 2 (replacement) | `docs/OBSERVATION_V3_SPECIFICATION.md` | `ed06bc5bd145e0eb9376df71ff42ee60069906d987c78531ba8b9e688746b1bc` |
| Consolidated decision correction | `docs/governance/decisions/WP-04_GATE_B_CONSOLIDATED_DECISION.md` | `9a683c12939c4f092341f8632507f8bc0ec45280ecd5e9a4b56a04a6f9828048` |
| Canonical Source Registry | `docs/governance/CANONICAL_SOURCE_REGISTRY.md` | Candidate-only; exact bytes identified by the reviewed branch tip |
| PEP-001 revision 0.8.0 | `docs/governance/PROJECT_EXECUTION_PLAN.md` | Candidate-only; exact bytes identified by the reviewed branch tip |
| Project Progress Ledger | `docs/governance/PROJECT_PROGRESS_LEDGER.md` | One append-only refresh entry; exact bytes identified by the reviewed branch tip |

That superseded revision-2 proposal carried forward the flat binding, strict types/ranges/value
semantics, selected lifecycle tuple and fail-closed mappings, adapter/core
boundary, raw-ROS prohibition, and `PENDING_MEASUREMENT` rule. It does not
claim that `ResolvedGateBRecordV3` has a selected exact member set, exact
resolved observation-input profile shape, or resolved non-pending values.
Observation Input Contract V3 revision 6 remains `REVISED_DRAFT`
provenance-only and cannot supply field/default/schema authority.
`ResolvedConfigV3.gate_b` is a required compiler-owned slot, not an
authorization of an unselected record shape.

Two independent blockers remain and must be resolved together in one
consolidated Owner decision before any code-authorization candidate may be
considered:

- `DECISION_DEFERRED_PENDING_EXACT_NON_CIRCULAR_CONFIG_HASH_PROJECTION`
- `DECISION_DEFERRED_PENDING_EXACT_RESOLVED_OBSERVATION_INPUT_PROFILE_SHAPE`

Neither the source correction nor the replacement candidate is active source
selection. The replacement does not satisfy the six ACR8 Gate B conditions,
pass Gate B, change WP status/dependencies, or grant implementation/runtime
authorization. WP-05's draft artifact and map-status state at the integration
base are preserved without edits by this candidate.

- New canonical/offline implementation that consumes configuration must use the V3 config family through an approved V3 composition/loader surface; it must not directly select the V1 loader, `config/base.yaml` or pre-V3 `config/profiles/**`.
- `APPROVED_FOR_CORE` for the V3 config family is not approval of any runtime profile, PPO training, Gazebo execution, HIL, deploy_sim or deploy_real.
- This decision does not resolve caller-owned composition, token/provenance, NavigationContractV3, localization/state contract, map provenance or hardware approval; those remain blocked until their own approved contracts.
- Existing legacy code may remain for historical/reference purposes but must not become a canonical entrypoint by import, wrapper or indirect delegation.


## WP-05 canonical artifact-foundation decision — active on integration

**Activation state:** foundation candidate `wp-05-canonical-artifact-foundation-integration-34dbb9d@d89f5187c792932e6e77f7ff8db5045f9cce70ed`, based on `34dbb9d17bb5863880838b0c49acac81b8b6dc48`, received a focused independent audit PASS, was authorized by the Project Owner/User, and was fast-forwarded to `integration/implementation`; the remote ref was verified at the exact candidate commit. These foundation references are active on the integration line. The previous candidate `wp-05-canonical-artifact-foundation-integration@28e84ea2758ef8a2f252b3da3e94114bb2705003` also passed the audit categories recorded in `docs/governance/decisions/WP-05_CANONICAL_ARTIFACT_FOUNDATION_APPROVAL.md`, but is stale after the integration base advanced and is not the integrated candidate. Approved packet source: `wp-05-artifact-foundation-decision-packet-56815516` at `72e47bd1c0a80188abc96f8575d5b345e3767e4d`, SHA-256 `b6a3cc428b82d92c437c9b0809f50268d3f409f82d7715c4494c3d27f07bf8d5`.

- **Map foundation (historical activation state):** at foundation activation, preserve `artifacts/maps/<map_id>/`; no map ID or instance had then been selected. The later `warehouse_map2` draft integration is recorded below. `map_content_hash` follows Architecture §48 and pins only `map.yaml` and `map.pgm` by role, relative name, byte size, and raw-file SHA-256 in the `mecanum_map_hash/v1` canonical JSON manifest. The manifest result field is excluded from its own digest input; `metadata.yaml` and optional `slam_pose_graph.posegraph` are outside the content-hash boundary.
- **Scenario foundation:** preserve `artifacts/scenarios/<scenario_id>/scenario.json`; `RFC8785_JCS_UTF8` is the serialization convention only. `GT_ODOM_2D` is evaluator/oracle-only; raw Ground Truth is excluded from PPO, policy input, and the observation core. No scenario ID or concrete value is selected.
- **Hardware foundation:** preserve `artifacts/hardware/<hardware_profile_id>/hardware_manifest.yaml` and the distinct approval record. `TBD_MEASURED`/null remain unavailable and fail-closed; `approval_status: DRAFT`; `motor_enable_allowed: false`. No measurement, hash approval, or hardware approval is recorded.

No world/frame equivalence, goal, start, bounds, zones, seed, randomization value, map/scenario instance, or physical measurement is selected. This foundation activation does not change PEP-001, WP status/dependencies, code authorization, runtime approval, or hardware approval.

## WP-05 map hash serialization RFC 8785 decision — active on integration

**Activation state:** the RFC 8785 clarification was integrated by `wp-05-map-hash-serialization-rfc8785-change-control-c37a5bff@988a74b529fdb4bcf77f341db5c6d115e8511a9b`, based on `c37a5bff9dd6cc32fc503cdd796b31720a58a616`; it remains active at current integration base `410d9cb70518b64d3c76c2ef99b11b69d1da6701`. Earlier candidate-pending wording in its decision record describes the pre-integration state and is superseded as to activation state here. This reconciliation does not activate a map schema or any concrete instance.

The active hash projection remains schema `mecanum_map_hash/v1` and exactly two ordered entries: `map_yaml`/`map.yaml`, then `occupancy_image`/`map.pgm`, each with role, `name`, `size_bytes`, and raw-file SHA-256. Hash only RFC 8785 JCS bytes encoded UTF-8 without BOM or trailing newline. `metadata.yaml`, optional pose graph, full-manifest result fields, and resulting `map_content_hash` are outside the digest. This rule is independently active at the current integration base and is unchanged by later WP-05 status reconciliation.

## WP-05 canonical static-map metadata schema — active on integration

**Activation state:** the exact metadata-schema candidate `wp-05-unified-map-metadata-schema-change-control-793514f@d33b93d3c6389872450f1a001e3073c61f355824`, parent `793514f8ff3c20c13bfe84bf0529295de4d4d0b4`, is `ACTIVE_ON_INTEGRATION` effective from exact commit `d33b93d3c6389872450f1a001e3073c61f355824`. The focused audit verdict and exact-commit User authorization are `USER_SUPPLIED_EVIDENCE`; no audit-report hash is asserted. Git-verifiable history confirms the commit ancestry and integration-ref activation event. Candidate-only wording in that integrated snapshot records the historical pre-activation state and is corrected by this status record.

The prior candidate `wp-05-unified-map-metadata-schema-change-control-7f9ed36@3892edf37ab5388fd38d3cf4a41d28ae2401782e` is stale provenance only; no audit or authorization is inferred for other commits. The nine metadata decision groups and Option A remain USER_SUPPLIED_DECISION. Unresolved provenance/external evidence route, actor/principal details, approval and delegation evidence schema, world/frame/runtime evidence, decimal grammar, and supersession event/index details remain PENDING_OWNER_DECISION or PROPOSAL_ONLY. The `warehouse_map2` draft artifact is present as recorded below; no map is approved or navigation-ready, and none is selected as the canonical navigation/localization map. Supersession event/index proposal is not active and must not be applied.

The RFC 8785 map-hash rule remains independently active. Only map.yaml and map.pgm are in map_content_hash; metadata, full manifest, result fields, optional pose graph, and resulting hash remain outside the payload. This status correction changes no schema semantics, WP status/dependency, or authorization.

Historical status-correction provenance: `wp-05-map-metadata-schema-activation-status-correction-d33b93d@e4add07d10eb4a616569d0f9a83f97493851ef04`, parent `d33b93d3c6389872450f1a001e3073c61f355824`. Historical refresh provenance: `wp-05-map-metadata-schema-activation-status-refresh-572da88`, based on `572da885d31d98929a1f8b8af4420012f1786fd6`; that base is not the current integration baseline or current WP-05 candidate. Candidate `wp-05-world-frame-evidence-registry-reconciliation-e89aeda5@0f42f1c9da00725c36500ff4ec1d2f75a0c8709a` is a remote review candidate with User-supplied verdict `CORRECTION_REQUIRED`, not integrated. The current replacement branch `wp-05-world-frame-evidence-governance-correction-0b2fcd1` is based on `0b2fcd1d010bc30f54d7621e6192dd76339df6b2` and is pending consolidated independent audit, separate exact-commit User authorization, fast-forward, and remote-ref verification. None of these historical review states suspends or alters the map metadata schema active since d33b93d.

## WP-05 `warehouse_map2` integrated draft and world-frame evidence record

Historical artifact provenance: at `68174e714cbe8aab61880113496cd7ccd7f97f5d`, no canonical map instance was selected or present. The draft candidate was later integrated at `1e14644a7d778a0c5ad32512430d775fd0e8ecd3`; at current integration base `410d9cb70518b64d3c76c2ef99b11b69d1da6701`, `artifacts/maps/warehouse_map2/` is present with map_id `warehouse_map2`, artifact_identity `4a8a23d0-7e27-4a50-8201-dd1abf1a3db4`, and map_content_hash `2bd9ff0a40eaeb61c2359aab4bb213da623ab56746debe591edd4a54c2229f90`. Its approval_status remains `draft`, world_frame remains `NOT_DECLARED`, and runtime_compatibility remains `NOT_VALIDATED`; it is not approved, navigation-ready, or selected for navigation/localization. Candidate `ca0432366da500ed549f71f96b51434b706772ef` remains local/unpushed source provenance only. Candidate `0f42f1c9da00725c36500ff4ec1d2f75a0c8709a` was pushed to its remote review branch and received the User-supplied audit verdict `CORRECTION_REQUIRED`; it was not integrated and activated neither its evidence record nor a metadata transition. Evidence-schema/record source commit `410d9cb70518b64d3c76c2ef99b11b69d1da6701` is integration-resident Git history. That fact does not itself prove an independent audit or User approval, nor does it activate a metadata declaration. The historical `572da885d31d98929a1f8b8af4420012f1786fd6` refresh is provenance only, not the current integration base or current WP-05 candidate. The RFC 8785 map-hash rule and metadata schema remain independently active. No source-world equivalence, transform, metric alignment, runtime compatibility, map approval, or navigation readiness is recorded. WP-05 remains OPEN; CODE_AUTHORIZATION: NOT_GRANTED; RUNTIME_APPROVED: NOT_APPROVED.

## WP-04 Gate A exact structural schema decision — historical pre-activation record

**Historical candidate state:** At the time of the original review, the Project Owner/User's exact schema selection was recorded in the candidate document `docs/OBSERVATION_GATE_A_STRUCTURAL_SCHEMA.md` (full-document SHA-256 `48f7a01a8713cb148c6fef2c1dc5add391dc29a05679e15a23c2b2b9ac817a9f`) and decision record `docs/governance/decisions/WP-04_GATE_A_EXACT_SCHEMA_DECISION.md` (full-document SHA-256 `e5b1ee20539be1e2a50df93bbd791a58045ae8d1f3a091b3322fd05a21704f5a`) on candidate branch `wp-04-gate-a-exact-schema-reconciliation-988a74b`, based on `988a74b529fdb4bcf77f341db5c6d115e8511a9b`. Its source decision packet was `wp-04-gate-a-exact-schema-decision-packet-c37a5bff@fc7833d0a491190c88f93d8fdd59da2feb263169`, SHA-256 `e69f0a06b6189a6558d7ee46f6c2c0f645abd6df62c618c39761b2733731042c`. The `PENDING_...` state and activation rule in that candidate record describe the pre-activation point in time and are retained here as historical provenance, not current status.

**Current activation status:** The exact schema source-selection activation is recorded in the preceding Registry reconciliation section and the active Registry row. The focused audit, explicit user authorization, exact integration ancestry, and byte-identity evidence stated there satisfy the former activation conditions as of integration base `3b357afdec00d7fb769c9d4978372772a91bc307`. The prior candidate-only disposition is superseded only as to schema source-selection/activation status. This does not change schema content or semantics, pass Gate A, close WP-04, change WP status/dependencies, or grant code/runtime authorization.

## WP-04 ObservationInputProfileV3 integrated governance amendment

At historical base `e89aeda5ca78859bfeedac4e7b94bcd6c7dcc7f0`, the active source selection was Observation V3 Specification revision 1, SHA-256 `feffb86e335d64a3a3fe0f3a1ce0866f868c8ed56ffa4412db14128c80b284ec`; it did not define `ObservationConfig.input_profile`. Revision 2 is superseded historical review provenance, pinned as `wp-04-gate-b-exact-data-contract-completion-refresh-1e14644@e89aeda5ca78859bfeedac4e7b94bcd6c7dcc7f0`, path `docs/OBSERVATION_V3_SPECIFICATION.md`, revision-2 full-document SHA-256 `ed06bc5bd145e0eb9376df71ff42ee60069906d987c78531ba8b9e688746b1bc`; it is not current content or active source selection. Revision 3 from source branch `wp-04-observation-input-profile-architecture-amendment-e89aeda5` at commit `d87b5a17ca0e9430d0b163aacf5b9cfcc4458d14`, together with its traceability corrections, is present in integration ancestry at `410d9cb70518b64d3c76c2ef99b11b69d1da6701` as the current integrated governance amendment. The Architecture DOCX is unchanged and retains precedence.

| Integrated governance artifact | Path | Status at this Registry base |
|---|---|---|
| Architecture Change Record | `docs/architecture/ARCH_CHANGE_RECORD_OBSERVATION_INPUT_PROFILE_V3.md` | Integrated governance amendment; subordinate to and does not modify the Architecture DOCX |
| Observation V3 Specification revision 3 | `docs/OBSERVATION_V3_SPECIFICATION.md` | Integrated governance specification; revision 2 is superseded historical provenance |
| Gate B consolidated decision amendment | `docs/governance/decisions/WP-04_GATE_B_CONSOLIDATED_DECISION.md` | Integrated governance decision; Gate B remains `NOT_STARTED` |
| PEP-001 revision 0.9.0 | `docs/governance/PROJECT_EXECUTION_PLAN.md` | Integration-resident plan record; no WP status/dependency transition |
| Progress Ledger entry | `docs/governance/PROJECT_PROGRESS_LEDGER.md` | Append-only integration history |

The integrated amendment keeps the Architecture root envelope unchanged, adds no root `gate_b`, and places static Gate-B references under `observation.input_profile`. `ResolvedGateBRecordV3` is only an internal compiler/type abstraction. The global resolved-config hash boundary is recorded; no Gate-B-only hash is added. Concrete contract IDs/digests and source pins not established by canonical authority remain unresolved; no profile instance is claimed resolved. OIC rev.6 remains provenance-only. These Git facts do not establish an independent audit or User approval beyond separately identified evidence, pass Gate B, alter the Architecture DOCX, or authorize implementation/runtime.

This entry changes no active source selection, WP status/dependency, or authorization. Gate B remains `NOT_STARTED`; WP-04 remains `BLOCKED_BY_CONTRACT`; Gate A remains `PASSED`; code/runtime authority remains not granted/approved; WP-05 remains `OPEN`.
