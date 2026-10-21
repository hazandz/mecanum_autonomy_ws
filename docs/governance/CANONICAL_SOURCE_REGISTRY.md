# Canonical Source Registry — Mecanum Nav2 DRL

## Registry role

This registry identifies operational source selection. It does not override MECANUM_NAV_DRL_Architecture.docx, approved ACRs or explicit user decisions.

## WP04 OIC V3 technical activation — source-base snapshot and target authority

The original L2 contract-candidate state is a historical snapshot at exact source base `5497b7e1938242422594f8150b06a32fe221ee70`: ACR revision 3 and Observation V3 Specification revision 5 were then the active base technical authority, while ACR revision 7 / Specification revision 9 and the new abstract contract and manifest were review-candidate records. The current technical-activation candidate is based on exact integration tip `23a7e21e320395091de4dd1b1700845355dc4391`; at that base ACR 3 / Specification 5 remain the active base authority and OIC V3 remains inactive pending this separate activation change-control.

After independent audit PASS for the exact activation candidate, separate exact-commit User authorization, fast-forward, and remote-ref verification, OIC V3 and its semantic manifest have status `ACTIVE_TECHNICAL_AUTHORITY_FOR_ABSTRACT_OIC_V3_CONTRACT_SEMANTICS_ONLY`. The active technical authority is then the frozen Architecture plus the ACR revision-3 / Specification revision-5 base authority as extended by the activated OIC V3 abstract typed-boundary semantics; revisions 3/5 are not the sole authority for that boundary. The contract source-file SHA-256 is `d44d33843c32d1f0d5c747522f3add09bfde21fcb0884e21da93a52476cb4dfc`; the semantic-manifest SHA-256 is `175a1af789b6641cfe455daeee8fedac80aaf80ad8c00792ba0a287c41acc0bb`. These identify distinct evidence roles. No concrete source file, runtime topic/publisher, ROS message type, profile reference, measurement, or profile instance is selected. Receipt v2/QoS6 and the active 16-root global config-hash policy remain unchanged.

The preceding pre-integration candidate-only wording describes only its explicitly identified source-base snapshot, not the post-activation state. This activation candidate does not claim audit, authorization, or activation from ancestry. After activation, six profile-reference groups and all required pins/evidence/measurements remain unresolved; no profile is resolved and Gate B does not start/pass. WP-04 remains `BLOCKED_BY_CONTRACT`; WP-05 remains `OPEN`; `CODE_AUTHORIZATION: NOT_GRANTED`; `RUNTIME_APPROVED: NOT_APPROVED`. The next prerequisite is L1 canonical source-pin/profile-manifest closure, not code.

## WP-04 Gate B target-contract closure — source-parent snapshot and post-integration target state

At exact integration base `701bb0cc5ca17b71e083d3ce4fdebd2bf46fbcee`, active
technical authority remains ACR revision 3 (SHA-256
`38cb74c0b09cd9c3ecbbac30c6520e0d01f7711adb788414a0a46489e844d9f8`) and
Observation V3 Specification revision 5 (SHA-256
`4092ee19d48a760b329ff49b9a79e39ab8389ff232aabd5dd06db83f8d83e5a2`), both
activated at `8c3de26521d7028a933f0a3ebe780fcb372f7a3a`. The target-contract
closure source candidate records Owner decisions for the exact target frame,
LocalReference meaning, measured-twist source semantics, TF ownership, and
lifecycle/barrier boundary. At the source-parent snapshot, its ACR record
revision 6, Specification revision 8, and decision record were review
candidates awaiting exact-candidate audit PASS, separate User authorization,
and integration/remote-ref verification.
After those conditions and remote-ref verification for the exact successor,
these are integration-resident target-governance records only; they do not
supersede the active technical authority, ACR revision 3 and Specification
revision 5.

Receipt v2 and QoS6 remain established canonical pins under the integrated
bundle and Registry; they are not pending. The exact receipt interface,
dependency-closure, QoS transport-manifest and full-document hashes are
recorded above in the Registry's canonical entries. This source candidate changes no
receipt/QoS bytes and claims no ROSIDL or runtime evidence.

Six profile-reference groups remain `PENDING_OWNER_SOURCE_SELECTION`: LiDAR
snapshot, navigation/global-path LocalReference, measured-twist snapshot,
frame/geometry source, lifecycle/reset/action-barrier policy, and concrete
profile source. Physical geometry/extrinsic and applicable required sensor or
timing values remain `PENDING_MEASUREMENT`. No profile instance is resolved;
under active ACR3, a missing required pin/evidence/measurement rejects the
whole resolved config with no partial hash. The candidate does not start/pass
Gate B, change WP status/dependencies, or grant code/runtime authorization.

## WP04-GATE-B-SOURCE-DISPOSITION-CLOSURE — source-parent snapshot and post-integration target state

At integration/source base `8b2f6d5c05ae8db8ce62285bd84afc401fb0d00c`, the decision record
`docs/governance/decisions/WP-04_GATE_B_SOURCE_DISPOSITION_CLOSURE.md` is a
source-parent snapshot, not active technical semantics. Its source-file
SHA-256 inventory pins bytes at that immutable base solely for provenance and
permitted evidence classification. It does not select a canonical runtime
source or resolve any profile reference.

The Owner-specified disposition is: `observations/lidar.py` is only a pure
72-sector algorithm source; `goal_features.py`, `measured_twist.py`, and
`simulated_odometry.py` are simulation/provenance only; `synchronizer.py`,
`previous_command.py`, `lifecycle_types.py`, and `episode_lifecycle.py` are
structural primitives/non-canonical policy sources; `config/v3/frames.yaml`
and `config/v3/topics.yaml` are Architecture-intent inputs only. The exact
paths, source base and file digests are recorded in the decision record. None
is canonical runtime-contract authority.

Final-issued receipt v2, its dependency-closure pin, and QoS6 transport pins
remain established under the existing Registry and integrated approval; they
are not reclassified as pending. Six profile-reference groups remain
unresolved: LiDAR snapshot, LocalReference, measured twist, frame/TF,
lifecycle/reset/action-barrier, and concrete profile source. Required
measurement items remain `PENDING_MEASUREMENT`. Active ACR3/Specification rev.5
remain unchanged. If later source selection requires new contract semantics or
a public/runtime interface, an L2 Architecture Change Record is required
before implementation. Missing required pins/evidence/measurements still
reject the whole resolved config without a partial hash.

At source parent `513ef03cc3c8b6d2e4f2053308d8f10b4e24f56d`, the decision and
Registry wording represented the pre-integration review state. This exact
correction candidate, before its integration, is pending independent audit,
separate User authorization for its exact commit, fast-forward, and
remote-ref verification. After those conditions are satisfied, the decision,
Registry entry, and Ledger correction are an integrated source-disposition
governance record only. They do not activate technical semantics, make any
source a canonical runtime contract, resolve a profile, start/pass Gate B, or
grant code/runtime authorization. ACR revision 3 and Observation V3
Specification revision 5 remain the active technical authority; receipt v2 and
QoS6 remain established; the six profile-reference groups remain unresolved.
WP-04, Gate A, Gate B, WP-05, and authorization statuses are unchanged.

### Historical source-selection candidate snapshot at integration base 13bfa066

The following source-selection candidate record describes only its historical
review state at integration base
`13bfa06658e5d65cc16f97fbc3ff3ec4a72e1bf6`; it is not the current candidate
for this work package and does not activate a source.

At integration base 13bfa06658e5d65cc16f97fbc3ff3ec4a72e1bf6, ACR revision 3
and Observation V3 Specification revision 5 remain the active technical
authority for profile schema and semantics. The source-selection decision
record docs/governance/decisions/WP-04_GATE_B_CANONICAL_INPUT_SOURCE_SELECTION.md
records the Project Owner/User rule that only sources explicitly established by
current Registry/approval authority may be selected. This successor is
candidate-only and does not activate a new source.

The prior candidate d385ea98986f0d68d6f288da2efa5db3fcf66085 was based on
29080644f3020f7ecd208dc45433c7d36ecc5e2e; it was not integrated and did not
receive a content-audit verdict. It is cited only as wording provenance for
this successor, which is based directly on 13bfa06658e5d65cc16f97fbc3ff3ec4a72e1bf6.

Receipt v2 and QoS6 pins remain established by the active Registry/approval at
the integrated bundle commit 2e7a2980cb75f0567182ea694c04328d7d8643e0:
receipt identity mecanum.final-issued-receipt/v2, revision 2, canonical
.msg path ros2_ws/src/mecanum_nav_rl_interfaces/msg/FinalIssuedCommandReceipt.msg,
SHA-256 0c6446674bf17373ec646519043f506a9a7a15f95d5fdd10829b0cedb956500a;
dependency-closure v1 path
docs/RECEIPT_INTERFACE_DEPENDENCY_CLOSURE_MANIFEST.json, SHA-256
0872fa8c10179f69c2e9e9546392ac734a4f4e94ade176a8be431f06905ecf73. QoS
identity is mecanum.final-issued-receipt-topic-qos/v2; transport manifest
path docs/RECEIPT_TOPIC_QOS_TRANSPORT_MANIFEST.json, SHA-256
338bea1b7350d3b82146c7e728516ec7947471ee68db0f8871ddb72071b79620; QoS6
full-document SHA-256 is separately
4200cd2fbdc81a19400f168dd3526eb7871ac2251049fc7c4f5d5c2fddfd2022.

No unique active contract ID/digest and immutable source pin is selected for
LiDAR snapshot, LocalReference, measured-twist, frame, or lifecycle/reset/
action-barrier profile references; these remain PENDING_OWNER_DECISION, then
require exact Git byte/provenance verification after an approved source is
selected. The concrete profile-source reference is likewise
PENDING_OWNER_DECISION. OIC revision 6 and other drafts/review candidates are
provenance-only. Required measurements and implementation/ROS adapter/runtime/
HIL evidence remain separately pending as applicable. Missing required
pin/evidence keeps the profile unresolved; active ACR3 requires whole-config
rejection without a partial hash.

This inventory does not change ACR3/Specification rev.5 semantics, active
receipt/QoS pins, global config_hash, the exhaustive 16-root projection,
nested ObservationConfig.input_profile, status/dependencies, or authorization.
The preceding pending-review language is a snapshot at integration base
`701bb0cc5ca17b71e083d3ce4fdebd2bf46fbcee`, not an indefinite post-integration
status. At the source-parent snapshot, this correction successor itself
remained pending its own focused audit, separate User authorization for its
exact commit, fast-forward, and remote-ref verification. ACR revision 6 / Specification revision 8 are target
governance, not active technical semantics; ACR revision 3 / Specification
revision 5 remain active technical authority. No profile is resolved and Gate B
remains `NOT_STARTED`.

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
or runtime authorization. At the time of that earlier review, the separate
error-carrier decision record and refreshed implementation-authorization
packet in that bundle were review candidates under the stated audit,
authorization, and integration conditions. This is historical bundle status,
not the current status of the ACR revision-3 activation recorded below.

## Registry entries

| Source/path | Classification | Permitted use |
|---|---|---|
| docs/MECANUM_NAV_DRL_Architecture.docx | ARCHITECTURE_AUTHORITY | Highest architecture authority |
| docs/RECEIPT_TOPIC_QOS_CONTRACT.md | CANONICAL_APPROVED_DESIGN_CONTRACT | Receipt Topic QoS Contract revision 6; full-document SHA-256 `4200cd2fbdc81a19400f168dd3526eb7871ac2251049fc7c4f5d5c2fddfd2022`; transport identity `mecanum.final-issued-receipt-topic-qos/v2` / `338bea1b7350d3b82146c7e728516ec7947471ee68db0f8871ddb72071b79620`; QoS policy values and transport behavior unchanged; design-contract scope only, no code/runtime authorization |
| docs/ACR_V3_OBSERVATION_BOUNDARY_CLOSURE.md | CANONICAL_APPROVED_ACR | ACR revision 8; full-document SHA-256 `03fef021f6b9731f811f83a5e53aae1c430bdc2ea76815a8ada416f1a5bf772c`; approved Gate A/Gate B scope carried forward; no WP-03 closure or dependency/status changes |
| docs/governance/decisions/QOS_REVISION_6_ACR_REVISION_8_BUNDLE_APPROVAL.md | CANONICAL_GOVERNANCE_APPROVAL_RECORD | Project Owner/User approval dated 2026-10-08; approval-record SHA-256 `4d740559f850f179387db802df845748068f75a21266fd1edb52402b2c72c529`; exact QoS6/ACR8, interface v2, dependency-closure and transport-v2 pins recorded; governs canonical document/status activation only after exact candidate integration; no code/runtime authorization or WP status/dependency change |
| docs/OBSERVATION_GATE_A_STRUCTURAL_SCHEMA.md | CANONICAL_APPROVED_GATE_A_STRUCTURAL_SCHEMA | Full-document SHA-256 `43537b8f0edafbe809e6f70bda86808f87b12f146ed45509c4bfbacd26956ad3`; audited correction `wp-04-gate-a-receipt-selector-attribution-correction@f9987be4429349ef9110c45cf97a89728a5e4229`, user-authorized and integrated by the stated base; structural contract source only, no Gate A pass or code/runtime authorization |
| docs/OBSERVATION_V3_SPECIFICATION.md | ACTIVE_BASE_SPECIFICATION_REV5; REVISION_7_STATUS_PROVENANCE_SUCCESSOR; REVISION_10_ACTIVATION_CANDIDATE | At source base `23a7e21…`, revision 5 is the active base technical specification; after all four activation conditions, its base authority is extended by abstract OIC V3 semantics only. Revision 10 does not replace its unchanged semantics. Revision 1 was historical source selection; revisions 1–4 remain provenance. Concrete pins/measurements remain pending; no Gate B pass or implementation/runtime authority |
| docs/architecture/ARCH_CHANGE_RECORD_OBSERVATION_INPUT_PROFILE_V3.md | ACTIVE_BASE_CHANGE_CONTROL_REV3; REVISION_5_STATUS_PROVENANCE_SUCCESSOR; REVISION_8_ACTIVATION_CANDIDATE | At source base `23a7e21…`, revision 3 is the active base change-control; after all four activation conditions, the frozen Architecture and revision-3 base are extended by abstract OIC V3 contract semantics only. Revision 8 does not change its own or the OIC contract semantics beyond the stated activation. No concrete source pins or measurements are established |
| docs/governance/decisions/WP-04_GATE_B_CONSOLIDATED_DECISION.md | ACTIVE_GATE_B_DECISION_WITH_INTEGRATED_ACR3_STATUS_HISTORY | Records ACR3 activation and the later status-reconciliation integration at `3fc3e2e583550b47195720f0de2fda8fbbd7490f`; required profile pins/evidence and measurements remain pending; Gate B remains NOT_STARTED and no code/runtime authorization is granted |
| docs/governance/decisions/QOS_REVISION_5_ACR_REVISION_7_BUNDLE_APPROVAL.md | HISTORICAL_GOVERNANCE_APPROVAL_RECORD | Prior user-approved bundle dated 2026-10-06; historical QoS5/ACR7 and receipt-interface/transport v1 pins retained; not current source selection after this candidate is integrated |
| AGENTS.md | EXECUTION_GOVERNANCE | Codex work rules; not architecture authority |
| docs/MECANUM_NAV_DRL_Project_Tree.txt | PROJECT_STRUCTURE_AUTHORITY | Expected project layout; not architecture override |
| ros2_ws/src/mecanum_nav_rl/config/v3/** | APPROVED_FOR_CORE | Permitted config-input family within approved core scope; for Navigation V1 source selection these are contract/intention inputs only, not an executable resolved profile or selected runtime source |
| ros2_ws/src/mecanum_nav_rl/config/base.yaml and config/profiles/** outside V3 | PRE_V3_NONCANONICAL | Historical/reference only unless explicit decision changes status |
| ros2_ws/src/mecanum_nav_rl/** pure core | IMPLEMENTED_CORE_PENDING_P0_REMEDIATION | Reuse only through approved work packages |
| ros2_ws/src/mecanum_nav_rl_interfaces/msg/** | CANONICAL_INTERFACE_CONTRACT | Typed interface source; changes require contract review |
| ros2_ws/src/mecanum_nav_rl_interfaces/msg/FinalIssuedCommandReceipt.msg | CANONICAL_INTERFACE_CONTRACT | Receipt interface v2; SHA-256 `0c6446674bf17373ec646519043f506a9a7a15f95d5fdd10829b0cedb956500a`; typed contract source only, not ROSIDL build or implementation authorization |
| docs/RECEIPT_INTERFACE_DEPENDENCY_CLOSURE_MANIFEST.json | CANONICAL_INTERFACE_DEPENDENCY_CLOSURE_MANIFEST | Closure version 1; SHA-256 `0872fa8c10179f69c2e9e9546392ac734a4f4e94ade176a8be431f06905ecf73`; pins transitive message-definition provenance |
| docs/RECEIPT_TOPIC_QOS_TRANSPORT_MANIFEST.json | CANONICAL_TRANSPORT_MANIFEST | Transport ID `mecanum.final-issued-receipt-topic-qos/v2`; SHA-256 `338bea1b7350d3b82146c7e728516ec7947471ee68db0f8871ddb72071b79620`; byte-identical to QoS revision 6 §4 manifest |
| ros2_ws/src/mecanum_base_bridge/** | CODEC_CORE_ONLY | Codec/diagnostic evidence only; not serial/ROS/odometry runtime |
| firmware_STM32/** | FIRMWARE_SOURCE_PENDING_OFFLINE_AND_HIL_EVIDENCE | Firmware implementation work only under contract/hardware approval |
| ros2_ws/src/ROBOT_URDF_final_description/urdf/**, meshes/**, models/** | ROBOT_GEOMETRY_SIMULATION_SOURCE | Geometry/simulation source; not proof of official runtime control profile |
| `ros2_ws/src/ROBOT_URDF_final_description/config/nav2_params.yaml`, `launch/nav2_bringup.launch.py`, `config/mapper_params_online_async.yaml`, `launch/slam.launch.py`, `config/ros_gz_bridge_gazebo.yaml`, `launch/gazebo.launch.py` | REFERENCE_ONLY_LEGACY for Navigation V1 | Static legacy reference only; not canonical executable profile sources, pins, runtime graph, or implicit remap/frame-alias authority |
| `docs/OBSERVATION_INPUT_CONTRACT_V3.md` | OIC_V3_ACTIVATION_CANDIDATE_AT_23A7E21; TARGET_ACTIVE_ABSTRACT_CONTRACT_AUTHORITY_AFTER_FOUR_CONDITIONS | Source-file SHA-256 `d44d33843c32d1f0d5c747522f3add09bfde21fcb0884e21da93a52476cb4dfc`; after exact-candidate audit PASS, separate User authorization, fast-forward, and remote-ref verification, active technical authority for abstract OIC V3 contract semantics only; no concrete profile/source or runtime implementation is selected |
| `docs/architecture/OBSERVATION_INPUT_CONTRACT_V3_SEMANTIC_MANIFEST.json` | OIC_V3_SEMANTIC_MANIFEST_ACTIVATION_CANDIDATE_AT_23A7E21; TARGET_ACTIVE_SEMANTIC_AUTHORITY_AFTER_FOUR_CONDITIONS | Semantic-manifest SHA-256 `175a1af789b6641cfe455daeee8fedac80aaf80ad8c00792ba0a287c41acc0bb`; digest is distinct from OIC source-file SHA; after the four conditions it is the canonical semantic payload for abstract OIC V3 only; no concrete pins or measurements |
| `docs/governance/decisions/WP-04_OBSERVATION_INPUT_CONTRACT_V3_ARCHITECTURE_DECISION.md` | OIC_V3_ACTIVATION_CANDIDATE_AT_23A7E21 | Records five abstract revision-v3 contracts and the conditional activation boundary; after the four conditions these semantics are active only at the abstract typed-boundary level; no profile resolution, Gate B start/pass, or code/runtime authorization |
| `ros2_ws/src/ROBOT_URDF_final_description/urdf/ROBOT_URDF_final.xacro`, `launch/tugbot_depot.sdf` | GEOMETRY_OR_PROVENANCE_EVIDENCE_ONLY for Navigation V1 | Static geometry/source bytes only; do not establish selected profile, actual scan header, runtime TF, map/world equivalence, transform, metric alignment, or compatibility |
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
revision 1 at that historical integration point. Its exact selected source
bytes are path `docs/OBSERVATION_V3_SPECIFICATION.md`, full-document SHA-256
`feffb86e335d64a3a3fe0f3a1ce0866f868c8ed56ffa4412db14128c80b284ec` at commit
`68174e714cbe8aab61880113496cd7ccd7f97f5d`. This revision-1 boundary-source
selection was controlling at that historical integration point, before ACR revision-3 activation at `8c3de26521d7028a933f0a3ebe780fcb372f7a3a`.
Source commit revision 3
`d87b5a17ca0e9430d0b163aacf5b9cfcc4458d14` is present in integration ancestry,
and the ACR still marked the amendment candidate-only pending its activation
conditions at that historical point. This does not pass Gate B, satisfy all six ACR8 Gate B
implementation conditions, change WP status/dependencies, or grant
implementation/runtime authorization.

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
at base `410d9cb70518b64d3c76c2ef99b11b69d1da6701` as candidate/provenance.
The ACR activation conditions remain unsatisfied in the available authority;
ancestry alone does not make revision 3 effective or active source selection.
It does not modify the Architecture DOCX, pass Gate B, or authorize
implementation/runtime.

The correction source candidate
`wp-04-gate-b-exact-data-contract-completion-correction-68174e@73a1f73c39eb742e79f53f50d5b5d73b41be0822`,
parent `68174e714cbe8aab61880113496cd7ccd7f97f5d`, is source/provenance only.
It is not this candidate, was not integrated, and is not being amended or
repushed. The historical replacement branch
`wp-04-gate-b-exact-data-contract-completion-refresh-1e14644`, based on
`1e14644a7d778a0c5ad32512430d775fd0e8ecd3`, proposed the following five-path
documentation/governance bundle. These hashes are historical delivery
provenance and do not identify current artifacts. That review was superseded.
The revision-3 integration-resident candidate/provenance is tracked separately
below. Candidate-only wording in historical snapshots is consistent with the
controlling ACR status and its pending activation conditions:

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

## WP-05 Navigation V1 source selection — review candidate only

The target/profile-resolution workflow decision at `docs/governance/decisions/WP-05_NAVIGATION_PROFILE_RESOLUTION_DECISION.md` was integrated at commit `13bfa06658e5d65cc16f97fbc3ff3ec4a72e1bf6`. It records the User-supplied Map Server + AMCL Omni target and a source inventory, but it did not select executable profile sources, resolve a profile, create a profile hash, approve a map, or authorize bring-up. Its earlier review-only wording is historical status at its source base.

The new source-selection decision record at `docs/governance/decisions/WP-05_NAVIGATION_V1_CANONICAL_SOURCE_SELECTION.md` is introduced by this review candidate from exact base `71f5db2b2bd1a04a1a3a087fed2ae6547f156fb1`. It records the Owner decision that no executable Navigation V1 profile is currently canonical. The V3 `frames.yaml`, `topics.yaml`, and `modes/nav2_baseline.yaml` are contract/intention inputs only, not an executable profile. Legacy Nav2/AMCL/launch/SLAM/Gazebo files are `REFERENCE_ONLY_LEGACY`; robot description/Xacro/SDF are geometry/provenance evidence only. None is selected by path, filename, repetition, or package location.

`warehouse_map2` exists in integration as draft with identity `4a8a23d0-7e27-4a50-8201-dd1abf1a3db4` and map hash `2bd9ff0a40eaeb61c2359aab4bb213da623ab56746debe591edd4a54c2229f90`; it remains not approved and not navigation-ready; runtime compatibility remains NOT_VALIDATED. A future profile may bind this exact artifact subject but that binding does not approve it.

Map Server config, AMCL parameters, EKF config, launch ownership, scan header frame, `base_link → lidar` geometry, TF ownership realization, explicit remaps/namespaces, lifecycle/startup implementation, and package/version pins remain `PENDING_OWNER_SOURCE_SELECTION` / `PENDING_PIN` as applicable. No implicit scan-frame alias is permitted. Missing/conflicting required inputs fail closed: no resolved profile, no profile `config_hash`, and no Navigation V1 bring-up. Runtime evidence, map approval, and world-frame validation remain independent work packages.

This exact source-selection candidate remains review-only until independent audit, separate explicit User authorization for its exact commit, fast-forward, and remote-ref verification. It makes no PEP, status, dependency, code, runtime, map-approval, or navigation-readiness change.

## WP-04 Gate A exact structural schema decision — historical pre-activation record

**Historical candidate state:** At the time of the original review, the Project Owner/User's exact schema selection was recorded in the candidate document `docs/OBSERVATION_GATE_A_STRUCTURAL_SCHEMA.md` (full-document SHA-256 `48f7a01a8713cb148c6fef2c1dc5add391dc29a05679e15a23c2b2b9ac817a9f`) and decision record `docs/governance/decisions/WP-04_GATE_A_EXACT_SCHEMA_DECISION.md` (full-document SHA-256 `e5b1ee20539be1e2a50df93bbd791a58045ae8d1f3a091b3322fd05a21704f5a`) on candidate branch `wp-04-gate-a-exact-schema-reconciliation-988a74b`, based on `988a74b529fdb4bcf77f341db5c6d115e8511a9b`. Its source decision packet was `wp-04-gate-a-exact-schema-decision-packet-c37a5bff@fc7833d0a491190c88f93d8fdd59da2feb263169`, SHA-256 `e69f0a06b6189a6558d7ee46f6c2c0f645abd6df62c618c39761b2733731042c`. The `PENDING_...` state and activation rule in that candidate record describe the pre-activation point in time and are retained here as historical provenance, not current status.

**Current activation status:** The exact schema source-selection activation is recorded in the preceding Registry reconciliation section and the active Registry row. The focused audit, explicit user authorization, exact integration ancestry, and byte-identity evidence stated there satisfy the former activation conditions as of integration base `3b357afdec00d7fb769c9d4978372772a91bc307`. The prior candidate-only disposition is superseded only as to schema source-selection/activation status. This does not change schema content or semantics, pass Gate A, close WP-04, change WP status/dependencies, or grant code/runtime authorization.

## Historical WP-04 ObservationInputProfileV3 pre-activation candidate status at 410d9cb

At historical base `410d9cb70518b64d3c76c2ef99b11b69d1da6701`, the then-current selected source was Observation V3 Specification revision 1; revision 2 was superseded historical review provenance. Revision 3 and source commit `d87b5a17ca0e9430d0b163aacf5b9cfcc4458d14` were present in integration ancestry. This is a Git-verifiable history fact only. At that time the companion ACR stated `CANDIDATE_ONLY_PENDING_FOCUSED_INDEPENDENT_AUDIT_AND_CANONICAL_INTEGRATION`. The later activation is recorded in the current section below. Ancestry alone does not prove focused audit or exact User authorization. The Architecture DOCX retains precedence.

| Integration-resident candidate/provenance | Path | Status under the controlling ACR |
|---|---|---|
| Architecture Change Record | `docs/architecture/ARCH_CHANGE_RECORD_OBSERVATION_INPUT_PROFILE_V3.md` | At historical base `410d9cb…`, candidate-only; current activation is recorded below |
| Observation V3 Specification revision 3 | `docs/OBSERVATION_V3_SPECIFICATION.md` | At historical base `410d9cb…`, integration-resident candidate/provenance; later superseded by activated revision 5 |
| Gate B consolidated decision amendment | `docs/governance/decisions/WP-04_GATE_B_CONSOLIDATED_DECISION.md` | Downstream candidate/provenance record; cannot override or activate the ACR |
| PEP-001 revision 0.9.0 source content | `docs/governance/PROJECT_EXECUTION_PLAN.md` | Candidate/provenance in the source branch; does not activate the ACR or change WP status/dependency |
| Progress Ledger entry | `docs/governance/PROJECT_PROGRESS_LEDGER.md` | Append-only candidate history; does not establish audit/authorization or activation |

The amendment candidate kept the Architecture root envelope unchanged, added no root `gate_b`, and recorded the Owner-approved static member under `observation.input_profile`. `ResolvedGateBRecordV3` is only an internal compiler/type abstraction, not a root member or alternate hash. The Owner-approved global hash policy is RFC 8785 JCS UTF-8 SHA-256 over the complete resolved static Architecture config; only output `config_hash` is omitted. Runtime-only data is invalid input and must be rejected, not silently removed. At the historical pre-activation base `c1187de97c550b9968d88aa6043ed716df981b54`, this was candidate-only. Concrete contract IDs/digests/source pins and required measurements remain unresolved. OIC rev.6 remains provenance-only. These decisions do not pass Gate B or authorize implementation/runtime.

This historical entry records the pre-activation state only; current activation status is recorded below. It changes no technical semantics, WP status/dependency, or authorization.

### Historical WP04-GATE-B global hash-root candidate at pre-activation base c1187de

Source review candidate `wp-04-gate-b-global-config-owner-decision-c1187de@e79a8f6fd6be7b50dbbfe28819a34116ecaec3ab` has sole parent
`c1187de97c550b9968d88aa6043ed716df981b54`. Its user-supplied F-01 finding
identified that ACR §4 and Specification §5.1 did not enumerate the complete
Architecture §4 root set explicitly; no audit-report hash is asserted. The
correction proposes ACR revision 3 (SHA-256
`38cb74c0b09cd9c3ecbbac30c6520e0d01f7711adb788414a0a46489e844d9f8`) and
Specification revision 5 (SHA-256
`4092ee19d48a760b329ff49b9a79e39ab8389ff232aabd5dd06db83f8d83e5a2`). Both
were candidate-only pending focused independent audit, separate explicit
User authorization for the exact final commit, fast-forward, and remote-ref
verification at that time. Observation V3 Specification revision 1 was then the active
Gate-B boundary-source selection. This correction changes no Owner decision,
profile semantics, concrete pin, measurement, status, dependency, or
authorization; Gate B remained `NOT_STARTED` and the ACR was not active at base `c1187de`.
The historical correction review branch was
`wp-04-gate-b-config-hash-root-correction-c1187de`, with direct parent
`e79a8f6fd6be7b50dbbfe28819a34116ecaec3ab`; the cumulative integration base is
`c1187de97c550b9968d88aa6043ed716df981b54`.

## ACR revision-3 activation event at integration 8c3de26 — historical event; current status through 3fc3e2e

At exact integration `8c3de26521d7028a933f0a3ebe780fcb372f7a3a`, ACR revision 3 was activated for the ObservationInputProfileV3 Architecture change-control. The exact-candidate audit PASS and separate exact-commit User authorization are `USER_SUPPLIED_EVIDENCE`; no audit-report hash is asserted. The fast-forward from `c1187de97c550b9968d88aa6043ed716df981b54` and remote-ref verification are Git-verifiable facts. ACR revision 3 SHA-256 is `38cb74c0b09cd9c3ecbbac30c6520e0d01f7711adb788414a0a46489e844d9f8`; the activated Observation V3 Specification revision 5 SHA-256 is `4092ee19d48a760b329ff49b9a79e39ab8389ff232aabd5dd06db83f8d83e5a2`. Revision 1 is historical pre-activation source selection; revisions 1–4 remain provenance.

The status-reconciliation commit `3fc3e2e583550b47195720f0de2fda8fbbd7490f` is integrated. Its pre-integration pending language is historical, not the present status. The later review candidate `4a938773cfd8f36cc81934951f4fa02dae99cb05` was reported by the User as audit PASS evidence but was not integrated after preflight identified wording that would be stale after fast-forward; this is `USER_SUPPLIED_EVIDENCE`, with no audit-report hash asserted. Neither status reconciliation changes technical semantics or resolves concrete contract/source pins or measurements. Gate B remains `NOT_STARTED`; WP-04 remains `BLOCKED_BY_CONTRACT`; Gate A is `PASSED`; WP-05 is `OPEN`; code/runtime authorization is not granted.

## WP-04 OIC V3 static reference manifest — source-base snapshot and target status

At exact source base `2186cd061ee126611f7afaacbbd9e8e2319ecc91`, the new static reference manifest is a review candidate pending independent audit, separate exact-commit User authorization, fast-forward, and remote-ref verification. After those conditions for the exact candidate, it is an integrated L1 static-reference governance record only; it is not a resolved `ObservationInputProfileV3`, runtime evidence, or a change to active technical semantics.

OIC V3 remains the active abstract typed-boundary authority: `docs/OBSERVATION_INPUT_CONTRACT_V3.md`, source-file SHA-256 `d44d33843c32d1f0d5c747522f3add09bfde21fcb0884e21da93a52476cb4dfc`; canonical semantic manifest `docs/architecture/OBSERVATION_INPUT_CONTRACT_V3_SEMANTIC_MANIFEST.json`, semantic-manifest SHA-256 `175a1af789b6641cfe455daeee8fedac80aaf80ad8c00792ba0a287c41acc0bb`. Receipt v2 and QoS6 remain established under `docs/governance/decisions/QOS_REVISION_6_ACR_REVISION_8_BUNDLE_APPROVAL.md` (SHA-256 `4d740559f850f179387db802df845748068f75a21266fd1edb52402b2c72c529`): receipt interface `mecanum.final-issued-receipt/v2`, schema revision 2, source SHA-256 `0c6446674bf17373ec646519043f506a9a7a15f95d5fdd10829b0cedb956500a`, dependency closure v1 SHA-256 `0872fa8c10179f69c2e9e9546392ac734a4f4e94ade176a8be431f06905ecf73`; QoS ID `mecanum.final-issued-receipt-topic-qos/v2`, revision 6, transport-manifest v2 SHA-256 `338bea1b7350d3b82146c7e728516ec7947471ee68db0f8871ddb72071b79620`, full QoS document SHA-256 `4200cd2fbdc81a19400f168dd3526eb7871ac2251049fc7c4f5d5c2fddfd2022`. These digests name distinct byte sets.

The candidate manifest at `docs/governance/evidence/WP-04_OBSERVATION_INPUT_PROFILE_V3_STATIC_REFERENCE_MANIFEST.json` records exactly seven reference groups: the five active OIC V3 identities (`mecanum.observation.lidar-snapshot/v3`, `mecanum.observation.local-reference/v3`, `mecanum.observation.measured-twist/v3`, `mecanum.observation.frame-tf-binding/v3`, `mecanum.observation.lifecycle-barrier/v3`) paired with OIC source and semantic pins, plus the established receipt-v2 and QoS6 pins. Concrete runtime source/profile bindings and required measurements/evidence remain unresolved as identified in the manifest; `PENDING_MEASUREMENT` is not replaced. Missing required pins/evidence fail closed: no resolved profile, global config hash, or Navigation/Gate B bring-up. No `config_hash` is computed or claimed by this record.

## WP04-OIC-V3 runtime target-binding authority — source-base snapshot and target lifecycle

At exact source base `7e72998c7bc8f9fb0a042672a9444879cd9baedd`, this candidate’s `ACR-OBSERVATION-RUNTIME-BINDING-V3` record revision `1`, together with its companion runtime-binding contract, semantic manifest, and decision, is a review-candidate snapshot. At that base, `docs/architecture/ARCH_CHANGE_RECORD_OBSERVATION_INPUT_PROFILE_V3.md` is Record revision `8`; `docs/OBSERVATION_V3_SPECIFICATION.md` revision `9` is Specification provenance only and is not an ACR revision. The new runtime-binding ACR is the separately named `ACR-OBSERVATION-RUNTIME-BINDING-V3`, Record revision `1`. Active abstract OIC V3 semantics continue to be governed by the integrated ACR/Specification/OIC authority. The L2 candidate records target interfaces/ownership only: LiDAR `sensor_msgs/msg/LaserScan` `/scan` in exact `lidar_frame` (`LidarIngressAdapterV3`); successful `ComputePathToPose` result with `nav_msgs/msg/Path` in `map` transformed to `base_link` LocalReference (`Nav2PlanReferenceAdapterV3`); measured twist `nav_msgs/msg/Odometry` `/odometry/filtered` with `odom`/`base_link` frames from one target `robot_localization` EKF; TF sole-owner targets localization `map -> odom`, EKF `odom -> base_link`, and `robot_state_publisher` `base_link -> lidar_frame`; and `SafetyLifecycle` sole ownership of lifecycle tuple/action-reset barriers with unchanged receipt v2/QoS6 and internal ingress context. This correction changes no five target runtime bindings, pins, pending measurements, fail-closed behavior, active authority, or authorization. The exact candidate still requires independent audit, separate exact User authorization, fast-forward, and remote-ref verification before it can be integrated.

The contract document `docs/OBSERVATION_RUNTIME_BINDING_V3.md` has source-file SHA-256 `ce2c979788658b45facbabdc3f7063f8663bf71380ab839531afcf7e204173b1`; `docs/architecture/OBSERVATION_RUNTIME_BINDING_V3_SEMANTIC_MANIFEST.json` has semantic-manifest SHA-256 `e800f7169304624d81334c26a638c27c9cbaa11a6df0ba5531b1718ee914f76f`. These identify distinct evidence roles. The dependency OIC document remains SHA-256 `d44d33843c32d1f0d5c747522f3add09bfde21fcb0884e21da93a52476cb4dfc` and its semantic manifest remains `175a1af789b6641cfe455daeee8fedac80aaf80ad8c00792ba0a287c41acc0bb`; the integrated static-reference manifest remains `639a83454fe9a1e1bf49f98334ba81aa5a78944644d99dfbe599082f4b5918d6`. Receipt v2/QoS6 pins remain established and unchanged.

After independent audit PASS, separate exact-commit User authorization, fast-forward, and remote-ref verification for the exact candidate, the L2 runtime-binding record becomes active technical authority for target bindings only; no separate activation candidate is required. The source-base candidate status is historical after those conditions. This record selects no implementation source/package/launch/EKF configuration, concrete profile, geometry/extrinsic, range, covariance, timeout, cadence, latency, or runtime evidence. Required implementation pins remain `PENDING_IMPLEMENTATION_SOURCE_PIN`, and required measurements remain `PENDING_MEASUREMENT`; failure to establish required pins/evidence fails closed without profile resolution, global `config_hash`, or Gate B bring-up. This candidate does not start/pass Gate B, close WP-04, or grant code/runtime authorization. WP-04 remains `BLOCKED_BY_CONTRACT`; Gate A `PASSED`; Gate B `NOT_STARTED`; WP-05 `OPEN`; `CODE_AUTHORIZATION: NOT_GRANTED`; `RUNTIME_APPROVED: NOT_APPROVED`.

## WP04 OIC V3 bounded fail-closed implementation authorization — status lifecycle and bounded scope

At exact source-base/review snapshot `5e5075b5860034527350629c686c2d26651fbfeb`, OIC V3 abstract typed-boundary semantics and the L2 runtime-binding target authority are integration-resident. Before integration of the exact correction candidate, the current status is `CODE_AUTHORIZATION: NOT_GRANTED` and `RUNTIME_APPROVED: NOT_APPROVED`. This record carries the Owner's conditional decision to grant only `BOUNDED_FAIL_CLOSED_IMPLEMENTATION_AUTHORIZATION` after independent audit PASS for the exact correction candidate, separate exact-commit User authorization, fast-forward, and remote-ref verification.

Only after all four conditions are satisfied for that exact correction candidate, the post-integration status is `CODE_AUTHORIZATION: GRANTED_BOUNDED_FAIL_CLOSED_INTERNAL_SEAMS_ONLY` and `RUNTIME_APPROVED: NOT_APPROVED`. `BOUNDED_FAIL_CLOSED_IMPLEMENTATION_AUTHORIZATION` names the approved scope; `GRANTED_BOUNDED_FAIL_CLOSED_INTERNAL_SEAMS_ONLY` is the canonical status token for that conditional authorization. Review push or Git ancestry alone does not grant it. Integration records bounded governance authorization only and does not mean implementation exists or is accepted.

The bounded future code candidate may implement only internal typed snapshot/context structures; fail-closed validation of exact contract identity, lifecycle tuple, `config_hash`, and fixture-injected topic/type/frame claims; a pure-core assembler/synchronizer that accepts only validated typed inputs and returns no vector on missing/mismatch/invalid input; and dependency-injected internal boundaries for LiDAR, LocalReference, measured twist, and receipt/lifecycle context. These boundaries are not ROS runtime ingress. No ROS endpoints, launch/runtime configuration, TF runtime, public ROS interface, runtime stack, profile instance, `ResolvedConfig`, global hash, or partial artifact is authorized.

Required source/package/version pins, measurements, and evidence remain pending. No default, alias, legacy/simulation fallback, fabricated value, clipping, zero-fill, partial vector, or partial hash may satisfy a missing prerequisite. `SafetyLifecycle` and `V3ObservationIngress` remain target implementation owners, not runtime evidence. Code review and test/offline acceptance evidence remain required and are not replaced by the bounded authorization. WP-04 remains `BLOCKED_BY_CONTRACT`; Gate A is `PASSED`; Gate B is `NOT_STARTED`; WP-05 is `OPEN`; runtime/HIL/hardware/deployment authority remains ungranted.

The post-integration token covers only typed snapshot/context structures, fail-closed validators, pure-core assembler/synchronizer seams, and dependency-injected internal adapter boundaries. It does not authorize ROS runtime graph/endpoints, launch/runtime YAML, TF runtime, Nav2/AMCL/EKF setup, `ResolvedConfig`, profile/global `config_hash`, inferred source/package/version pins, public ROS/ROSIDL changes, runtime/HIL/hardware/deploy, Gate B start/pass, or WP-05/map changes.


## WP-05 Navigation V1 L2 runtime-binding refresh — review snapshot at `16e4d81296f5db0fb322349bfe673cb5bd2c1534`

The current review candidate is being prepared directly from exact integration base `16e4d81296f5db0fb322349bfe673cb5bd2c1534` on branch `wp05-navigation-v1-runtime-binding-refresh-16e4d812`. Prior commit `4ff6b96783c940e7f4c523ed553d3ad75f8a5a55` (parent `5249a11e69408abf845e8568258989a70edefb35`) is source-content/provenance only: it is not this candidate's parent, not the current integration baseline, and is not treated as integrated or audited by this refresh. Candidate-only/pending-audit wording in the companion ACR, contract, and decision applies to this refreshed review snapshot. Only after independent audit PASS for the exact successor commit, separate exact-commit User authorization, fast-forward, and remote-ref verification do the target bindings become `ACTIVE_L2_NAVIGATION_V1_RUNTIME_BINDING_TECHNICAL_AUTHORITY_FOR_TARGET_BINDINGS_ONLY`; no separate activation candidate is required.

The five target groups remain limited to: canonical map-artifact-root binding; AMCL Omni as the `NAV2_BASELINE` localization target (`map → odom`) with SLAM Toolbox MAPPING-only; EKF target ownership of `odom → base_link`; `/scan` LaserScan with exact `lidar_frame` and robot-description target ownership of `base_link → lidar_frame`; and Architecture health-gated lifecycle/startup. `warehouse_map2` remains draft, not approved, not selected for navigation/localization, and not navigation-ready. `WORLD_FRAME: NOT_DECLARED`; `RUNTIME_COMPATIBILITY: NOT_VALIDATED`; no map-world equivalence, transform, alignment, or runtime validation is asserted.

Implementation source/package/version pins and measurements listed in the companion records remain pending. Missing or conflicting required information fails closed: no resolved profile, global `config_hash`, or Navigation V1 bring-up. The current integration's WP-04 code authorization remains exactly `GRANTED_BOUNDED_FAIL_CLOSED_INTERNAL_SEAMS_ONLY`, limited to internal fail-closed seams; this WP-05 candidate grants no broader code authority, runtime approval, map approval, or status/dependency transition.

## WP-04 OIC V3 nonexecuting observation-ingress source authorization — review snapshot at `346138368a5a3599779f36d629c6fc0e0233338a`

At this exact source-base/review snapshot, the bounded authorization already integrated for internal fail-closed seams remains `GRANTED_BOUNDED_FAIL_CLOSED_INTERNAL_SEAMS_ONLY`; `RUNTIME_APPROVED: NOT_APPROVED`. The four-path L1 candidate in `docs/governance/decisions/WP-04_OIC_V3_NONEXECUTING_OBSERVATION_INGRESS_SOURCE_AUTHORIZATION.md` records a conditional, source-level extension only. No audit, User authorization, or activation is inferred from Git ancestry or review push.

After independent audit PASS for that exact candidate, separate exact-commit User authorization, fast-forward, and remote-ref verification, the current authorization token is `GRANTED_BOUNDED_FAIL_CLOSED_INTERNAL_SEAMS_AND_NONEXECUTING_OBSERVATION_INGRESS_ADAPTER_SOURCES_ONLY`; `RUNTIME_APPROVED: NOT_APPROVED`. It permits only later, separately pinned source creation within `ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/observations/` and `ros2_ws/src/mecanum_nav_rl/test/`, under the decision's nonexecuting adapter boundary. This record itself creates no code or tests.

The recorded target input claims are `/scan` `sensor_msgs/msg/LaserScan` with exact `lidar_frame`; prevalidated/transformed Nav2 global-path LocalReference; `/odometry/filtered` `nav_msgs/msg/Odometry`; and already-valid typed receipt/lifecycle context. No alias, ROS graph, TF operation, source/package/version pin, profile, measurement, global `config_hash`, map approval, or runtime evidence is introduced. Missing or mismatched input remains fail-closed with no typed snapshot and no 81D vector. OIC v3, runtime-binding, receipt v2, QoS6, and WP-05 authorities/pins are not modified.

The current record lifecycle is: source-base snapshot before integration; integrated L1 bounded implementation-source authorization only after all four conditions above. It is not runtime approval, implementation completion, or runtime evidence. WP-04 remains `BLOCKED_BY_CONTRACT`; Gate A `PASSED`; Gate B `NOT_STARTED`; WP-05 `OPEN`.

## WP04-OIC-V3 implementation-source pin closure — review snapshot at `8675047aa61835621f6d1e31aff567b75c87094c`

`docs/governance/evidence/WP-04_OIC_V3_IMPLEMENTATION_SOURCE_PIN_MANIFEST.json` and `docs/governance/decisions/WP-04_OIC_V3_IMPLEMENTATION_SOURCE_PIN_CLOSURE.md` inventory 15 exact workspace implementation files at this source base. Every entry is classified `PINNED_IMPLEMENTATION_SOURCE_ONLY` and `NOT_A_RUNTIME_SOURCE_PIN`; it records immutable path/byte provenance only. The eight `mecanum_nav_rl` pure-core/nonexecuting-ingress sources and seven `mecanum_nav_bringup` scaffold/template/validator/launch sources are not runtime evidence. The latter are not external package or ROS-distribution locks.

The manifest records authority fingerprints for Architecture, OIC V3, WP-04 runtime-binding/static-reference authorities and bounded authorization, and WP-05 Navigation V1 runtime-binding/static-bringup authorization. The routing does not alter those authorities. `PENDING_EXTERNAL_PACKAGE_LOCK`, `PENDING_RUNTIME_SOURCE_PIN`, and `PENDING_MEASUREMENT` remain distinct pending classes and fail closed. No resolved profile, global `config_hash`, Gate B bring-up, map approval, runtime evidence, or runtime authorization follows from these implementation pins.

At this exact base the records are review-candidate snapshots. Only after independent audit PASS for the exact candidate, separate exact-commit User authorization, fast-forward, and remote-ref verification are they integrated L1 implementation-source-pin governance records. This does not change active L2 semantics, target TF ownership, status, or authorization. AMCL remains target owner of `map → odom`; EKF of `odom → base_link`; RSP of `base_link → lidar_frame`. `warehouse_map2` remains draft; `WORLD_FRAME: NOT_DECLARED`; `RUNTIME_COMPATIBILITY: NOT_VALIDATED`.

## WP04-WP05 runtime measurement plan and evidence schema — review snapshot at `cc0018560b20a52fa6d3c9cf26abbe0ef4c6227a`

At this exact source-base snapshot, `docs/governance/decisions/WP-04_WP-05_RUNTIME_MEASUREMENT_PLAN_AND_EVIDENCE_SCHEMA.md` and its companion JSON Schema are review-candidate governance records, not active runtime-binding technical authority. They define only measurement planning, ownership, fail-closed evidence admission, exploratory-versus-acceptance distinction, and packet shape. The schema is not a populated packet and provides no measurement result, runtime evidence, acceptance conclusion, map approval, Gate B pass, or authorization.

After independent audit PASS for the exact candidate, separate exact-commit User authorization, fast-forward, and remote-ref verification, these records may be described only as `INTEGRATED_L1_RUNTIME_MEASUREMENT_GOVERNANCE_PLAN_ONLY`. Review push or Git ancestry alone does not activate them. No passive measurement harness is authorized; it requires a separate L1 authorization. No numerical threshold, source/package/version lock instance, profile, `config_hash`, measurement value, or runtime authorization is introduced. Required source/package pins and measurements remain pending. Status remains WP-04 `BLOCKED_BY_CONTRACT`, Gate B `NOT_STARTED`, WP-05 `OPEN`, map draft/not approved, `WORLD_FRAME: NOT_DECLARED`, `RUNTIME_COMPATIBILITY: NOT_VALIDATED`, and `RUNTIME_APPROVED: NOT_APPROVED`.

Dependency fingerprints recorded by this candidate are Architecture SHA-256 `432eeac363a595cfcf7e81c4b66054fb674dba140a2ef3cffecd617ab8136204`; OIC source SHA-256 `d44d33843c32d1f0d5c747522f3add09bfde21fcb0884e21da93a52476cb4dfc`; OIC semantic-manifest SHA-256 `175a1af789b6641cfe455daeee8fedac80aaf80ad8c00792ba0a287c41acc0bb`; WP-04 runtime-binding manifest SHA-256 `e800f7169304624d81334c26a638c27c9cbaa11a6df0ba5531b1718ee914f76f`; WP-05 Navigation V1 runtime-binding ACR SHA-256 `3e74cdcb6136f60a6ad2822a853f2ae9926cf971059f3c2470c874802d6fae0d`; WP-05 runtime-binding manifest SHA-256 `33855c9c95f9c0594ddd8805514658e4f5cb8255a219938a7913438470edbf31`; and `warehouse_map2` map-content hash `2bd9ff0a40eaeb61c2359aab4bb213da623ab56746debe591edd4a54c2229f90`. These are dependency fingerprints, not newly selected pins or acceptance evidence.


## WP-05 Navigation V1 dependency-lock schema and static bringup source authorization — review snapshot at `2a537a9cfa9f9c5b0bec1f9c629fec8e2f98a225`

Decision candidate: `docs/governance/decisions/WP-05_NAVIGATION_V1_DEPENDENCY_LOCK_AND_STATIC_BRINGUP_SOURCE_AUTHORIZATION.md`; schema: `docs/governance/evidence/WP-05_NAVIGATION_V1_DEPENDENCY_LOCK_SCHEMA.json`. This five-path candidate is based on exact integration snapshot `2a537a9cfa9f9c5b0bec1f9c629fec8e2f98a225` and is pending independent audit, separate exact-commit User authorization, fast-forward, and remote-ref verification. The schema defines direct dependency roots and required future lock fields only; it contains no installed package/version, `.deb` digest, workspace source pin, resolved profile, or runtime evidence.

The proposed future owner of Navigation V1 bringup sources is `mecanum_nav_bringup`; no such package exists at this base. The enumerated source layout is a bounded future allowlist, not present content. `mecanum_nav_rl` retains DRL/pure-core/observation-adapter ownership; `mecanum_base_bridge` retains Pi–STM32 transport/raw wheel-odometry ownership and emits no TF; `ROBOT_URDF_final_description` retains geometry and future robot-description ownership of `base_link → lidar_frame`; map bytes remain only at `artifacts/maps/<map_id>/`.

Current authorization at the base remains `CODE_AUTHORIZATION: GRANTED_BOUNDED_FAIL_CLOSED_INTERNAL_SEAMS_AND_NONEXECUTING_OBSERVATION_INGRESS_ADAPTER_SOURCES_ONLY`; `RUNTIME_APPROVED: NOT_APPROVED`. Only after the exact candidate lifecycle conditions above would it extend to `GRANTED_BOUNDED_FAIL_CLOSED_INTERNAL_SEAMS_NONEXECUTING_OBSERVATION_INGRESS_AND_STATIC_NAVIGATION_V1_BRINGUP_SOURCES_ONLY`. That is static-source/static-test authorization only; it does not permit launch/ROS/Nav2/AMCL/EKF/Gazebo execution, profile resolution, map approval, runtime/HIL/hardware/deployment, or WP status changes.

Outstanding records remain `PENDING_EXTERNAL_PACKAGE_LOCK` or `PENDING_IMPLEMENTATION_SOURCE_PIN`. Any missing required lock/source/measurement/evidence fails closed: no resolved profile, profile `config_hash`, bring-up, map approval, or runtime authorization. WP-05 remains `OPEN`; `warehouse_map2` remains draft, not approved or navigation-ready; `WORLD_FRAME: NOT_DECLARED`, and `RUNTIME_COMPATIBILITY: NOT_VALIDATED`; WP-04 remains `BLOCKED_BY_CONTRACT`, Gate A `PASSED`, Gate B `NOT_STARTED`.

## WP04-WP05 measurement evidence schema F-01 correction — review snapshot

The source-parent candidate is `5b8ac68f51814f9520e1e72a28da5ad35fcfacea`, based directly on integration `cc0018560b20a52fa6d3c9cf26abbe0ef4c6227a`; it remains a review candidate and was not integrated. Finding `F-01` is `USER_SUPPLIED_INDEPENDENT_AUDIT_EVIDENCE`; no audit-report hash is recorded. The correction moves the acceptance-only `minItems: 1` constraint to the `metrics_inventory` array level. Schema ID and revision `1` are unchanged. No existing registry entry pinned the schema bytes, so this correction introduces no dependency pin.

This correction is the current review snapshot. Only after independent audit PASS for this exact correction, separate exact-commit User authorization, fast-forward, and remote-ref verification may the decision/schema/Registry/PEP records be described as `INTEGRATED_L1_RUNTIME_MEASUREMENT_GOVERNANCE_PLAN_ONLY`. This is not active L2 technical authority, runtime evidence, map approval, runtime authorization, or Gate B pass. All prior plan boundaries and pending source/package pins and measurements remain unchanged; no harness or measurement result is created.

## Architecture authority provenance reconciliation — review snapshot at `457926439220756f5dc18ed62c9d1143715668fc`

The current Git-verifiable Architecture authority at this source-base snapshot is `docs/MECANUM_NAV_DRL_Architecture.docx`, SHA-256 `432eeac363a595cfcf7e81c4b66054fb674dba140a2ef3cffecd617ab8136204`. Historical provenance `docs/MECANUM_NAV_DRL_Architecture.docx@86beff623dba3683f643c851a4a1374c635178b3`, SHA-256 `f0fb1ebede5f4fa18604610c04bb13587d456173b4fd942dba77e44d49777860`, is historical provenance only and is not a current authority claim. The Git-verifiable transition is recorded at `988a74b529fdb4bcf77f341db5c6d115e8511a9b`; the verified semantic delta is limited to §48 RFC 8785 JCS UTF-8 serialization for `map_content_hash`.

The 26 listed A0/S3 legacy/draft documents are classified `HISTORICAL_PROVENANCE_ONLY` and `NOT_A_CURRENT_ARCHITECTURE_AUTHORITY_CLAIM`. Their reconciliation changes only provenance/status wording. It does not activate their technical content or change Architecture semantics, map bytes/hash, WP-04/WP-05 semantics, source pins, package locks, profiles, config hash, or authorization. This is a review candidate; independent audit PASS, separate exact-commit User authorization, fast-forward, and remote-ref verification remain pending. No WP-04/WP-05 status or dependency transition is recorded.

## WP05 Navigation V1 dependency-lock provenance envelope — source-base review snapshot

At exact source base `f23af59d7a9458175928c2647532339ff933158b`, the new dependency-lock provenance ACR, schema revision 2, semantic manifest, validator update, tests, and decision record are review-candidate material. The amendment adds a required closed typed `artifact_baseline_provenance` envelope only. The 14 logical roots and existing package-pin semantics remain unchanged; `launch_ros` is not a logical root. No concrete lock instance or profile source is created, and structural validation does not prove that an external artifact exists.

Only after independent audit PASS for the exact candidate, separate explicit User authorization for that exact commit, fast-forward, and remote-ref verification may this be described as integrated active authority for dependency-lock provenance schema semantics only. No Navigation runtime semantics, map approval, profile resolution, `config_hash`, runtime authorization, or WP-04 status changes. WP-05 remains `OPEN`; `RUNTIME_APPROVED: NOT_APPROVED`.

## WP05 external 14-root dependency-lock record — review snapshot at `ab5c62f866985b72cbaff370fae38cdd6192dbcc`

`docs/governance/evidence/WP-05_NAVIGATION_V1_EXTERNAL_14_ROOT_DEPENDENCY_LOCK.json` is an L1 review candidate containing the 14 exact external package pins allowed by active dependency-lock schema v2 and its typed artifact-baseline provenance envelope. The external artifact bytes were checked at the Owner-provided baseline locator; the lock records the baseline collection provenance commit `f23af59d7a9458175928c2647532339ff933158b`, distinct from this candidate's integration base. `workspace_source_locks` is empty, and the record is not a complete input to the runtime validator; the required workspace-source roles remain unpinned.

This record is candidate-only at this exact source-base snapshot pending independent audit, separate explicit User authorization for the exact candidate, fast-forward, and remote-ref verification. It does not create a resolved profile, profile `config_hash`, workspace-source pin, map approval, runtime evidence, or runtime authorization. `warehouse_map2` remains draft/not approved; `WORLD_FRAME: NOT_DECLARED`; `RUNTIME_COMPATIBILITY: NOT_VALIDATED`; WP-05 remains `OPEN`; WP-04 and Gate B are unchanged.

## WP05 Navigation V1 static policy source provenance — review candidate

At source commit `c1d37b3d7ec349c0942790063d57887e5d201484`, three static policy files are pinned by exact path and SHA-256 in `docs/governance/evidence/WP-05_NAVIGATION_V1_STATIC_POLICY_SOURCE_PIN_MANIFEST.json`. This establishes `PINNED_STATIC_POLICY_SOURCE_ONLY` provenance. The policy contents intentionally remain pending and `STATIC_TEMPLATE_ONLY`; no role is resolved by the provenance pin. All ten workspace-source roles remain `PENDING_IMPLEMENTATION_SOURCE_PIN`, including `nav2_lifecycle_bringup`, `remap_namespace_policy`, and `lifecycle_startup_policy`.

The new manifest and decision are review-candidate records at this source-base snapshot. They do not populate `workspace_source_locks`, authorize Nav2 activation or lifecycle transitions, create a runtime graph, resolve a profile, approve a map, or provide runtime evidence/authorization. WP-05 status and all map/world/runtime boundaries remain unchanged.
## WP-04/WP-05 shared LiDAR frame and TF/RSP ownership — review candidate

At exact source base `de71ae4d4ecb86724b1a02bdccad6f70315de7bc`, the decision `docs/governance/decisions/WP-04_WP-05_SHARED_LIDAR_FRAME_TF_RSP_OWNERSHIP_DECISION.md`, shared contract, ACR, and semantic manifest are review-only records derived from `USER_SUPPLIED_ARCHITECT_OWNER_DECISION`. The specified Architecture Git blob at this base has SHA-256 `432eeac363a595cfcf7e81c4b66054fb674dba140a2ef3cffecd617ab8136204`.

The new L2 governance record selects literal `lidar_frame` as the public LiDAR frame for Navigation V1 `/scan` and Observation V3, and `robot_state_publisher` as sole target owner of the direct fixed edge `base_link → lidar_frame`. `RPLiDAR_A1M8_1` remains `LEGACY_GEOMETRY_PROVENANCE_ONLY`; it is not an alias, canonical frame, runtime target, or source pin. Legacy fixed-joint geometry remains `PENDING_MEASUREMENT_AND_CANONICAL_SOURCE_SELECTION`. This record is distinct from legacy geometry provenance and does not select or verify an extrinsic.

The record becomes `ACTIVE_L2_SHARED_TF_RSP_GOVERNANCE_FOR_FRAME_ID_AND_OWNERSHIP_ONLY` only after independent audit PASS for the exact candidate, separate exact-commit User authorization, fast-forward, and remote-ref verification. It provides no source pin, geometry verification, runtime evidence, or runtime authorization. Missing canonical RSP source pin or verified extrinsic evidence, a nonliteral scan frame, alias/bridge/static-transform workaround, or owner conflict fails closed as specified in the decision. WP-04/WP-05 statuses and Gate B are unchanged.
## WP-04/WP-05 canonical RSP description source creation authorization — review snapshot

At exact source base `fa862f26eed6cfa30a553ccf6f1befcad532a1f9`, `docs/governance/decisions/WP-04_WP-05_CANONICAL_RSP_DESCRIPTION_SOURCE_CREATION_AUTHORIZATION.md` and its manifest are a review-only L1 conditional source-creation authorization, based on `USER_SUPPLIED_ARCHITECT_OWNER_DECISION`. It is bounded by the integrated L2 shared-frame decision: literal `lidar_frame` and `robot_state_publisher` sole target ownership of direct edge `base_link → lidar_frame`.

The four future allowed paths are the Xacro, Gazebo description, dedicated `navigation_v1_robot_state_publisher.launch.py`, and focused TF contract test under `ros2_ws/src/ROBOT_URDF_final_description/`. No source pin for that future canonical source exists yet. `RPLiDAR_A1M8_1` and legacy `xyz/rpy` remain `LEGACY_GEOMETRY_PROVENANCE_ONLY` and `PENDING_MEASUREMENT_AND_CANONICAL_SOURCE_SELECTION`; they are not canonical geometry evidence. Creation is conditional on a complete extrinsic evidence packet with explicit Owner acceptance.

Only after independent audit PASS for this exact candidate, separate exact-commit User authorization, fast-forward, and remote-ref verification does this record become `INTEGRATED_L1_CANONICAL_RSP_DESCRIPTION_SOURCE_CREATION_AUTHORIZATION_ONLY`. That status grants no source pin, geometry verification, runtime evidence, profile resolution, `config_hash`, Gate B authorization, or runtime authorization. WP-04/WP-05 statuses remain unchanged and `RUNTIME_APPROVED: NOT_APPROVED`.

## WP04-WP05 canonical RSP source pin provenance closure — review snapshot at `d4ae75e34a62730da0576f51c1a49dd67b9d8d3b`

`docs/governance/evidence/WP-04_WP-05_CANONICAL_RSP_SOURCE_PIN_MANIFEST.json` records exactly four already-integrated source files at the exact source commit: canonical robot-description Xacro, Gazebo LiDAR-absence guard, dedicated RSP launch, and static LiDAR TF contract test. Each is `PINNED_CANONICAL_DESCRIPTION_SOURCE_ONLY`, scoped to WP-04 Observation V3 / WP-05 Navigation V1 source provenance, and explicitly `NOT_A_RUNTIME_SOURCE_PIN`. `ROBOT_URDF_final_description` is the package owner.

The provenance pin does not create a runtime source pin for the LiDAR driver, `/scan`, AMCL, EKF, map, or runtime package. The source's CAD nominal extrinsic is linked to Owner packet fingerprint `40fe44cb3647376b3b1f793761091e101051d7e141e4687e67e2f03632e430de`; hardware-as-built verification remains pending. `robot_state_publisher` remains the sole target owner of direct edge `base_link → lidar_frame`, with literal public frame `lidar_frame`. The current Gazebo source contains no active LiDAR sensor/profile; `RPLiDAR_A1M8_1` is not canonical and is neither an alias nor a bridge.

This is a review-candidate provenance closure at this exact source-base snapshot. It grants no runtime authorization, map approval, profile resolution, global `config_hash`, Gate B start/pass, or runtime evidence. WP-04/WP-05 statuses and `RUNTIME_APPROVED: NOT_APPROVED` remain unchanged.


## WP-04 YDLIDAR X3 Pro static simulation scan source-creation authorization — review snapshot at `53d56e1787487fd90c6d92e8f4f51a3eca23773f`

The manifest and decision are `L1_STATIC_SOURCE_CREATION_AUTHORIZATION_ONLY` review-candidate records. They pin vendor documentation to YDLidar-SDK commit `42a82ed10d2304094c111fc63dee8e4a229b79b7`, path `doc/Dataset.md`, SHA-256 `ec5e27ab30b1e4d13a4b25bc4770a106d05f54ba5b191f21374af11a6d2b4897`, and authorize only a later static-source candidate editing the Gazebo description and focused static contract test. Vendor facts and the derived 6.0 Hz / 500-sample simulation nominal are not runtime evidence.

The future source must retain `lidar_frame` and `robot_state_publisher` sole ownership of `base_link → lidar_frame`; `RPLiDAR_A1M8_1` remains legacy provenance only. Gazebo transport `scan` is not ROS `/scan` or `sensor_msgs/msg/LaserScan`. All listed runtime source pins and measurements remain pending. The candidate does not create source, bridge, profile, `config_hash`, runtime evidence, map approval, Gate B transition, or runtime authorization.


## WP00 post-integration status reconciliation — base `9f2762d875024df927aa581580e746bc35436e80`

At this integration snapshot, `origin/integration/implementation` is `9f2762d875024df927aa581580e746bc35436e80`. WP-04 commit `e9695d21fb2d9c76fe7e35f0081f648bc401fe51` is the direct parent of WP-05 integration commit `9f2762d875024df927aa581580e746bc35436e80`. The WP-04 record is `INTEGRATED_L1_STATIC_SIMULATION_SCAN_SOURCE_CREATION_AUTHORIZATION_ONLY`: it conditionally permits only a later static Gazebo LiDAR source candidate under `ros2_ws/src/ROBOT_URDF_final_description/urdf/ROBOT_URDF_final.gazebo` and its focused contract test at `ros2_ws/src/ROBOT_URDF_final_description/test/test_navigation_v1_lidar_frame_tf_contract.py`. It is not a runtime source pin, ROS bridge, runtime profile, runtime evidence, or runtime authorization.

WP-05 at `9f2762d875024df927aa581580e746bc35436e80` integrates exactly these five static-source paths:

- `ros2_ws/src/mecanum_nav_bringup/config/localization/navigation_v1_amcl_omni.static.template.yaml`
- `ros2_ws/src/mecanum_nav_bringup/config/state_estimation/navigation_v1_ekf.static.template.yaml`
- `ros2_ws/src/mecanum_nav_bringup/config/lifecycle/navigation_v1_localization_lifecycle.static.template.yaml`
- `ros2_ws/src/mecanum_nav_bringup/test/test_navigation_v1_static_localization_lifecycle_sources.py`
- `ros2_ws/src/mecanum_nav_bringup/setup.py`

Its disposition is `INTEGRATED_STATIC_TEMPLATE_SOURCES_ONLY`. These templates are not `WORKSPACE_SOURCE_ROLE_PIN`, `RUNTIME_SOURCE_PIN`, `RESOLVED_PROFILE_INPUT`, `MAP_APPROVAL`, `RUNTIME_EVIDENCE`, or `RUNTIME_AUTHORIZATION`; they do not resolve a profile or create `config_hash`. This post-integration static reconciliation does not assert a WP-05 independent pre-integration audit or infer audit, runtime evidence, or authorization from ancestry.

The next-step route is: L1 post-integration reconciliation → a WP-04 static Gazebo LiDAR source candidate within its authorized two-path allowlist → WP-05 source-role/profile closure preparation → each later candidate based on and integrated from the exact current integration tip. This route is prospective; those later steps are not asserted as completed. Earlier review snapshots remain historical snapshots. This reconciliation supersedes only their stale present-tense next-step wording that canonical RSP description source creation was still the next action; the integrated canonical RSP source and its provenance closure are already present at this base.

Current status remains: `WP-04: BLOCKED_BY_CONTRACT`; `GATE_A_STRUCTURAL_PRIMITIVES: PASSED`; `GATE_B: NOT_STARTED`; `WP-05: OPEN`; `MAP_ARTIFACT: DRAFT_ON_INTEGRATION_NOT_APPROVED`; `WORLD_FRAME: NOT_DECLARED`; `RUNTIME_COMPATIBILITY: NOT_VALIDATED`; `RUNTIME_APPROVED: NOT_APPROVED`; `YDLIDAR_X3_PRO_RUNTIME_SOURCE_PIN: PENDING`; `ROS_GAZEBO_SCAN_BRIDGE_SOURCE_PIN: PENDING`; `SCAN_RUNTIME_PROFILE: PENDING`.

## WP-05 Navigation V1 workspace source-role inventory — review snapshot at `c59d9ea65010ff80eb0202bfaa5220c5f18f25ac`

Decision packet: `docs/governance/decisions/WP-05_NAVIGATION_V1_WORKSPACE_SOURCE_ROLE_INVENTORY_AND_DECISION_PACKET.md`; evidence inventory: `docs/governance/evidence/WP-05_NAVIGATION_V1_WORKSPACE_SOURCE_ROLE_INVENTORY.json`. This five-path L1 governance candidate routes evidence for the ten required workspace source roles. Each role remains `PENDING_IMPLEMENTATION_SOURCE_PIN`, `NOT_SELECTED`, and not eligible as a runtime input. The listed files are evidence references only; static templates/policies/guards remain static evidence, robot-description files remain description provenance, and Gazebo transport remains `GAZEBO_TRANSPORT_SOURCE_ONLY_NOT_ROS_SCAN_ADAPTER`—not ROS `/scan` evidence.

At this exact source-base snapshot these records are review candidates. Only after independent audit PASS for the exact candidate, separate User authorization for that exact commit, fast-forward, and remote-ref verification may they be described as an integrated inventory governance record. Review push or ancestry alone does not change that lifecycle. No source selection, `workspace_source_locks` entry, external lock change, code-authorization extension, resolved profile, global `config_hash`, map approval, runtime evidence, Gate B transition, or runtime authorization is created. Missing source pins/evidence continues to fail closed; WP-04 remains `BLOCKED_BY_CONTRACT`, Gate A `PASSED`, Gate B `NOT_STARTED`, WP-05 `OPEN`, map draft/not approved, `WORLD_FRAME: NOT_DECLARED`, `RUNTIME_COMPATIBILITY: NOT_VALIDATED`, and `RUNTIME_APPROVED: NOT_APPROVED`.


## WP05 warehouse_map2 sim_eval static approval evidence — review candidate

At exact source base `7fe8b24758636dcac540b33a73bf5e3b7febbe6b`, Candidate 4A records the Owner-selected static artifact `warehouse_map2` for `sim_eval + NAV2_BASELINE`, under the sole scope `SIM_EVAL_NAV2_BASELINE_STATIC_MAP_ARTIFACT_SELECTION`. The evidence JSON is `docs/governance/evidence/WP-05_WAREHOUSE_MAP2_SIM_EVAL_STATIC_APPROVAL.json`; it pins the exact map subject and file fingerprints. The future Map Server binding is limited to `artifacts/maps/warehouse_map2/map.yaml`; no ROS-package copy is selected.

This is an approval-evidence decision candidate only. It has not activated map metadata, which remains `draft`; it has not resolved or selected a runtime profile. It makes no navigation-readiness, Map Server load, AMCL, TF, map/world equivalence, world-frame validation, or runtime-compatibility claim. Candidate 4B depends on the exact integrated commit of Candidate 4A and is a separate metadata-change candidate. No runtime authority, profile resolution, `config_hash`, or WP-05 closure is created.


## WP05 warehouse_map2 static approval metadata activation — review candidate

At exact base `a8eed8712ad7e20ae4d9e7665a4d07dacbde9047`, metadata is `draft`, `WORLD_FRAME: NOT_DECLARED`, and runtime compatibility is `NOT_VALIDATED`. This candidate proposes to pin the integrated static approval evidence and existing world-frame declaration evidence in the exact map metadata. Before integration, the proposed activation is review-only.

After independent audit PASS, separate exact-candidate User authorization, fast-forward integration, and remote-ref verification, current metadata will be `approval_status: approved` solely for `SIM_EVAL_NAV2_BASELINE_STATIC_MAP_ARTIFACT_SELECTION`, with `world_frame.state: DECLARED_UNVERIFIED` and `runtime_compatibility.state: NOT_VALIDATED`. It is then eligible as a static profile input for Step 5, not a resolved profile or navigation-ready artifact. A future Map Server may bind only to `artifacts/maps/warehouse_map2/map.yaml`.

Earlier Registry/PEP/Ledger statements describing `warehouse_map2` as draft or world frame `NOT_DECLARED` are historical source-base snapshots; after activation this entry supersedes them only for current metadata status. No map/world equivalence, transform, metric alignment, Map Server load, AMCL, TF, runtime validation, runtime authority, `ResolvedConfigV3`, `config_hash`, or WP-05 closure is claimed. WP-04/WP-05 and Gate A/Gate B statuses remain unchanged.


## WP05 sim_eval + NAV2_BASELINE static profile input closure — Step 5A review candidate

Candidate `wp05-sim-eval-static-profile-closure-2864a21` is based on `2864a215782cc1901aa259a49d885fa0c132cf7a`. It records a closed static input descriptor for `sim_eval + NAV2_BASELINE`, including source-path/hash provenance and the already approved `warehouse_map2` static-selection subject. Before audit/integration it remains a review candidate. After exact-candidate audit PASS, separate User authorization, fast-forward integration, and remote-ref verification, its disposition is `STATIC_PROFILE_INPUT_CLOSURE_ONLY`; it is not a resolved runtime profile.

Map status for current integration after that transition is approved only for `SIM_EVAL_NAV2_BASELINE_STATIC_MAP_ARTIFACT_SELECTION`; `WORLD_FRAME: DECLARED_UNVERIFIED`; `RUNTIME_COMPATIBILITY: NOT_VALIDATED`. Earlier draft/`NOT_DECLARED` entries remain historical snapshots. No `workspace_source_locks`, `ResolvedConfigV3`, `config_hash`, runtime source pin, bridge/endpoint pin, Map Server load, launch graph, runtime evidence, or runtime authorization is created. WP-04 remains `BLOCKED_BY_CONTRACT`; Gate A `PASSED`; Gate B `NOT_STARTED`; WP-05 `OPEN`; `RUNTIME_APPROVED: NOT_APPROVED`.


## WP06 receipt v2 ROSIDL enablement — atomic L2 review candidate

At exact source base `c8b178a2f1feee115a3a01553afaec616cabf737`, receipt v2 is already the established canonical interface contract, but its source carries historical `DRAFT` and “Not installed in a ROSIDL package” annotations. The atomic L2 decision `docs/governance/decisions/WP-06_RECEIPT_V2_ROSIDL_ENABLEMENT_ATOMIC_L2_DECISION.md` and evidence record `docs/governance/evidence/WP-06_RECEIPT_V2_ROSIDL_ENABLEMENT_ATOMIC_L2_EVIDENCE.json` resolve those annotations narrowly for ROSIDL generation status and authorize this candidate's build/interface declaration.

Before independent audit, separate exact-commit User authorization, integration, and remote-ref verification, this remains a review candidate. After all four conditions apply to this exact candidate, the status is `WP06_RECEIPT_V2_ROSIDL_GENERATION: IMPLEMENTED_OFFLINE_BUILD_INTERFACE_ONLY`. This supersedes `Not installed in a ROSIDL package` only for build generation. Receipt ID `mecanum.final-issued-receipt/v2`, schema revision 2, `.msg` source bytes/SHA-256 `0c6446674bf17373ec646519043f506a9a7a15f95d5fdd10829b0cedb956500a`, dependency closure, and QoS6 remain unchanged. The historical `DRAFT` annotation does not downgrade the canonical receipt contract.

No receipt runtime producer/consumer, ROS node, publisher/subscriber, `/mecanum/final_issued_command` topic, runtime QoS, receipt runtime evidence, `ResolvedConfigV3`, `config_hash`, Gate B transition, or runtime authorization is created. `RUNTIME_APPROVED: NOT_APPROVED`; WP-04/WP-05 and Gate A/Gate B statuses remain unchanged. ROSIDL build-interface generation alone is not runtime implementation.


## WP06 command safety core — jerk-envelope corrected atomic L2 review candidate

At exact integration base `d0b1234f1c23961c5dd7c04a35c9ec39d6077629`, this independently created candidate retains the exact-width F-01, latched emergency/no-auto-resume F-02, and reset/epoch/generation/source/handover barrier F-03 corrections. It corrects F-04 by intersecting, per axis, the hard-velocity-derived acceleration interval, acceleration interval, and jerk interval centered on previous acceleration. An empty intersection yields `FAULT`, zero, and command-cache invalidation. No post-limit velocity clipping is used.

The candidate is `L2_COMMAND_SAFETY_CORE_JERK_ENVELOPE_CORRECTED_PURE_LOGIC_IMPLEMENTATION` and remains review-only. Only after independent audit PASS for this exact candidate, separate exact-commit User authorization, integration, and remote-ref verification may the status be recorded as `WP06_COMMAND_SAFETY_CORE: IMPLEMENTED_OFFLINE_ONLY`. Evidence is limited to pure-core source and offline unit tests. No runtime SafetySupervisor, ROS graph, `FinalTwistPublisher`, `/cmd_vel` publication, receipt runtime, collision/TTC or physical E-stop integration, profile, `ResolvedConfigV3`, `config_hash`, runtime evidence, or runtime authorization is created. `RUNTIME_APPROVED: NOT_APPROVED`; WP-04/WP-05 and Gate A/Gate B remain unchanged.

## WP06 sim_eval wheel/IMU ingress — ROSIDL sequence-corrected replacement review candidate

At exact base `43c94789f628b4211189fc391326e0b119cbb6d3`, this fresh candidate records the bounded simulation-only ingress source and corrects the wheel emulator's ROSIDL numeric-sequence acceptance. Rejected candidate commits `38d52b19b8cacecbe49961f77df47eaacfd8c3c4` and `3f40b6dcf34e07f9f9df33889df2c9379163d3fd` are historical references only and are not candidate ancestors or source inputs. F-01 invalid-interval barriers and F-02 forced/effective `use_sim_time=true` are retained; F-03 accepts indexed `collections.abc.Sequence` values including `array.array('d')` without coercing generators.

The node is constrained to the two staging subscriptions and two canonical outputs in the L2 decision. It does not publish TF. `/odom` and `/ground_truth/odom` are prohibited inputs. `runtime_eligible: false`; WP06-6E remains the sole ROS–Gazebo bridge owner. Evidence is source plus offline test/build only. The candidate is review-only pending independent audit and separate exact-commit User authorization. No runtime evidence, runtime authorization, profile resolution, `ResolvedConfigV3`, `config_hash`, Gate B transition, or changes to WP-04/WP-05/Gate A/Gate B are asserted. `RUNTIME_APPROVED: NOT_APPROVED`.


### WP06 sim_eval wheel/IMU ingress — corrective review commit (F-04)

The corrective commit is applied to the existing review candidate, not created as a new candidate from integration. Integration base remains `43c94789f628b4211189fc391326e0b119cbb6d3`; direct parent is `4ccb0491408c8b8bfbf0c34f5cb33329ec9979c6`. F-04 `ROLLBACK_TIMESTAMP_PRECEDENCE` requires a valid backward timestamp to reset pose and baseline before payload validation, including when the accompanying wheel rates are NaN or required joints are missing/duplicated. F-01/F-02/F-03 remain unchanged. Evidence is offline only, `runtime_eligible: false`; WP06-6E remains sole bridge owner. `RUNTIME_APPROVED: NOT_APPROVED`; WP-04/WP-05/Gate A/Gate B are unchanged.


## WP05 sim_eval + NAV2_BASELINE current Gazebo source-pin reconciliation — review candidate

At exact base `4f491edca1d46dee259d57350ad520a0334e4049`, the current Gazebo LiDAR source bytes have SHA-256 `1e97b6ea340adc9aecaf320cc432007c6bb37f5922cdc0366dbee50a9a26ff0e`, while the current Step 5A YAML, Python descriptor and manifest retained prior source-base provenance and the old Gazebo hash `a97b092f7343d04679ed1417539e47d217b20d18afc3364a27cf14110d9dece8`. This candidate reconciles only those two values in the three current descriptors. The source remains classified `GAZEBO_TRANSPORT_PROVENANCE_ONLY`; its content and all LiDAR, map, TF, bridge and runtime semantics remain unchanged. The historical workspace source-role inventory is preserved with its old hash as a source-base snapshot.

Before independent audit and separate exact-candidate User authorization/integration, this is review-only. After those conditions, Step 5A is self-consistent only as `STATIC_PROFILE_INPUT_CLOSURE_ONLY`, not a resolved runtime profile. No endpoint pin, bridge, runtime source pin, `ResolvedConfigV3`, `config_hash`, runtime evidence or runtime authorization is created. Current status remains WP-05 `OPEN`, WP-04 `BLOCKED_BY_CONTRACT`, Gate A `PASSED`, Gate B `NOT_STARTED`, and `RUNTIME_APPROVED: NOT_APPROVED`.


## WP06 sim_eval Scan endpoint probe — L2 review candidate

Candidate `wp06-sim-eval-scan-endpoint-probe-46be7a2` is based on `46be7a2bde222475fbaaaac8a6749211edfd2ba0` and adds a static descriptor plus an import-inert, fake-runner-tested source for a future bounded Gazebo topic probe. `<topic>scan</topic>` is only a relative sensor topic, not a full Gazebo Transport endpoint. This candidate does not execute the probe or pin an endpoint; any future observation is `OBSERVED_NOT_PINNED` and requires a separate Owner decision before WP06-6E.

A future execution requires a separate capacity-one `APPROVED_RUNTIME` packet with exact command, pass/fail criteria, stop conditions and explicit User approval. WP06-6E remains sole owner of canonical ROS–Gazebo bridge implementation. No bridge, ROS `/scan` publisher, TF, runtime evidence, profile resolution or runtime authorization is created. WP-04 `BLOCKED_BY_CONTRACT`, WP-05 `OPEN`, Gate A `PASSED`, Gate B `NOT_STARTED`, and `RUNTIME_APPROVED: NOT_APPROVED` remain unchanged. Evidence ceiling: `IMPLEMENTED_OFFLINE_BUILD_AND_TEST_ONLY`; review only pending independent audit.
## WP06 sim_eval Scan endpoint probe runtime bootstrap and capacity-one guard — review candidate

At exact integration base `bfc1ef3cfe4ba98beefbe7f18607b97a41e52d15`, this independently constructed L2 review candidate binds the bootstrap source and a capacity-one guard to the authority packet `docs/governance/decisions/WP-06_SIM_EVAL_SCAN_ENDPOINT_PROBE_RUNTIME_BOOTSTRAP_AND_GUARD.md`, SHA-256 `d053fb4e6623cd753d63d4e1c646c476124579946671d389a16aba333d1b69e6`. The initial guard state is `PENDING_EXACT_INTEGRATION_AND_USER_AUTHORIZATION`; it is not an authorization to run.

After independent audit, exact integration, remote-ref verification, and a separate User prompt carrying the exact 40-character integration commit, the status may be recorded only as `RUNTIME_GUARD_IMPLEMENTED_AWAITING_EXACT_USER_AUTHORIZATION`. The one-shot supervisor then verifies authority-packet bytes, source pins, exact HEAD/integration ref, integrated candidate blobs, command, partition, run ID, and absent run directory before atomically consuming the guard. WP06-6E remains the sole canonical ROS–Gazebo bridge owner. No endpoint pin, bridge, ROS `/scan`, TF, runtime evidence, profile resolution, `ResolvedConfigV3`, `config_hash`, Gate B transition, or runtime authorization is created. `WP-04: BLOCKED_BY_CONTRACT`; `WP-05: OPEN`; Gate A: `PASSED`; Gate B: `NOT_STARTED`; `RUNTIME_APPROVED: NOT_APPROVED`.


## WP06 sim_eval scan endpoint probe — deterministic bootstrap remediation L2 review candidate

At exact base `be5f63e7a01be0bca0b838e1ae5265bbb7145be8`, this review candidate adds a local Fuel-free probe world and deterministic server-only bootstrap for Run 002. The world contains only the requested Gazebo systems and inline ground plane; it does not replace `tugbot_depot.sdf` and makes no navigation-fidelity or Nav2-readiness claim. The launch unconditionally sets `GZ_PARTITION=wp06_scan_probe_run_002`, explicitly targets `wp06_scan_probe_world`, and has no fixed-delay readiness substitute.

Run 001 remains byte-identical and pending at the source base. Conditional on integration of this exact candidate, its old source/partition context becomes `NOT_CONSUMED_AND_INVALIDATED_BY_EXACT_INTEGRATION_MISMATCH`. Run 002 is future-only, capacity one and `PENDING_EXACT_INTEGRATION_AND_USER_AUTHORIZATION`; this review candidate does not authorize runtime. A future run requires exact integrated commit, clean worktree, pending guard, and the exact create log `Entity creation successful.` before a compatible supervisor can be called once. A consumed guard cannot be retried.

No endpoint pin, ROS `/scan`, bridge, TF evidence, runtime evidence/authorization, resolved profile, `ResolvedConfigV3`, `config_hash` or Gate B transition is created. WP06-6E remains sole owner of the canonical ROS–Gazebo bridge. WP-04 `BLOCKED_BY_CONTRACT`, WP-05 `OPEN`, Gate A `PASSED`, Gate B `NOT_STARTED`, and `RUNTIME_APPROVED: NOT_APPROVED` remain unchanged.

### Corrective review commit — Run 002 guard/supervisor and world gravity

The corrective commit is on the same review branch, parented by `97aeecdff640187ac0b3ad152a22befe442a1a2f`. Run 002 now has a separate pending-only guard, one-shot supervisor and canonical manifest bound to the corrected decision SHA and exact source pins. The Run 001 guard, tools and manifest are byte-identical to the parent. World gravity is a direct child of the probe world, not physics. Evidence remains offline source/tests/build only; the Run 002 guard is not consumed or runtime-authorized. `RUNTIME_APPROVED: NOT_APPROVED`; WP-04/WP-05, Gate A/Gate B unchanged.


## WP06 Run 003 scan-probe observation and teardown remediation — review candidate

The candidate `wp06-scan-probe-observation-teardown-b15e0fd` starts at exact integration base `b15e0fd6e83f840822b8ba11f68dbdf31de0978e`. It revises the offline probe to select only exact `/.../scan` leaf candidates and recognize only the canonical unbracketed Gazebo Harmonic publisher entry inside the `Publishers` section. Legacy `Type:` lines and subscriber-only types do not match. Raw stdout/stderr is retained under a future run directory with exact transcript hashes and byte counts; candidate count (16) and per-stream transcript hard limit (1,048,576 bytes) are explicit and overflow fails closed.

Run 003 has a separate server-only bridge-free bootstrap and a pending capacity-one session guard. The runner verifies exact integrated refs, clean worktree, authority decision, manifest, guard, command and source blobs before consumption; it waits for the exact create-success log, invokes the probe once, and tears down only its own process group using the fixed escalation policy. The guard is `PENDING_EXACT_INTEGRATION_AND_USER_AUTHORIZATION`; no runtime run is authorized or executed by this candidate. Run 002 remains outside scope and is untouched.

A future `EXACTLY_ONE_MATCH` remains `OBSERVED_NOT_PINNED` and requires a separate Owner decision before WP06-6E, the sole canonical ROS–Gazebo bridge owner. No endpoint pin, ROS `/scan`, bridge, TF evidence, runtime profile/resolution, `ResolvedConfigV3`, `config_hash`, Gate B transition, runtime evidence/authorization, or `RUNTIME_APPROVED` status is established. WP-04 `BLOCKED_BY_CONTRACT`; WP-05 `OPEN`; Gate A `PASSED`; Gate B `NOT_STARTED`; `RUNTIME_APPROVED: NOT_APPROVED`.


### Run 003 corrective review — Harmonic publisher grammar

The corrective commit on `wp06-scan-probe-observation-teardown-b15e0fd` narrows scan inspection to the structured `Publishers` section and canonical unbracketed `<scheme>://<address>, <message-type>` entries. Only exact `gz.msgs.LaserScan` publisher entries produce an observed candidate; subscriber-only data does not. The previous candidate `e9ccee03123c3ec2baf82a66ce5a60bcbf1f9dfb` was not integrated and was not runtime-authorized. Run 003 remains pending; another capacity-one authorization is required after audit and integration of the exact corrected commit. Evidence remains offline source/tests/build only; no endpoint pin, bridge, ROS `/scan`, TF or runtime evidence.


## WP06 scan-probe Run 004 readiness and teardown remediation — review candidate

The review candidate `wp06-scan-probe-readiness-teardown-run004-db464f7` is based on `db464f741e24a81b3f9587f827fc145c533d8d6c`. It introduces a distinct Run 004 pending guard, a server-only launch, service-gated robot creation, and a session runner with direct-file transcripts and Linux `/proc` process-group accounting. Run 002 and Run 003 historical paths remain outside the candidate diff and are not changed or reinterpreted.

The Run 004 guard remains `PENDING_EXACT_INTEGRATION_AND_USER_AUTHORIZATION`; candidate evidence is `IMPLEMENTED_OFFLINE_GUARD_AND_SESSION_SOURCE_ONLY`. Runtime use requires independent audit, exact candidate integration/ref verification, a clean integrated worktree, and separate Owner authorization for the exact integrated commit. A future result can be no stronger than `GZ_LASERSCAN_ENDPOINT_OBSERVED_NOT_PINNED`. No endpoint pin, ROS `/scan`, bridge, TF evidence, runtime authorization, `ResolvedConfigV3`, `config_hash`, Gate B transition, or runtime approval is established. WP-04 `BLOCKED_BY_CONTRACT`, WP-05 `OPEN`, Gate A `PASSED`, Gate B `NOT_STARTED`, and `RUNTIME_APPROVED: NOT_APPROVED` remain unchanged.


## WP06 scan-probe Run 005 persistent transport discovery — parser corrective review candidate

The existing Run 005 review line retains its exact review/integration topology,
Transport 13 pre-acquire check, one-node service discovery, world, LiDAR,
create command, and teardown behavior. The source parser now recognizes the
Gazebo Harmonic publisher record followed by the exact `No subscribers on
topic [/scan]` footer. It accepts one publisher of exact type
`gz.msgs.LaserScan`; missing, malformed, wrong-type, subscriber-only, or
ambiguous publisher information fails closed.

Run 005 runtime was invoked once on parent
`20814c9009cee588f6b330ee227f69d886949593`. The historical record remains
`PROBE_NOT_EXACTLY_ONE_MATCH`, and the runtime-host authorization is consumed.
Independent review of the preserved 111-byte inspection transcript confirmed
one Gazebo `gz.msgs.LaserScan` publisher; offline replay of those bytes yields
`GZ_LASERSCAN_ENDPOINT_OBSERVED_NOT_PINNED`. The historical run record is
unchanged. Although the Git guard file remains a pending source seed, it is
not authorization to rerun Run 005; no retry is allowed.

This parser correction is source plus offline-test evidence only; it did not
run ROS, Gazebo, `gz`, launch, probe, or the session runner. It creates no ROS
`/scan`, bridge, TF evidence, endpoint pin, runtime approval, `ResolvedConfigV3`,
`config_hash`, or Gate B transition. WP-04 `BLOCKED_BY_CONTRACT`, WP-05 `OPEN`,
Gate A `PASSED`, Gate B `NOT_STARTED`, and `RUNTIME_APPROVED: NOT_APPROVED`
remain unchanged.


## WP06 sim_eval ROS–Gazebo scan bridge — review candidate

At exact integration base `abcdffb4d1683c6b337b7c8a8916d0c9317d111e`, this candidate adds one profile-specific `GZ_TO_ROS` mapping from Gazebo `/scan` (`gz.msgs.LaserScan`) to ROS `/scan` (`sensor_msgs/msg/LaserScan`) using `ros_gz_bridge/parameter_bridge` and an installed YAML `config_file`. The launch defaults to `GZ_PARTITION=sim_eval`, requires `use_sim_time: true`, and starts only the bridge node. The prior static bridge contract remains unchanged provenance evidence.

Status: bridge source and this frame correction are source/offline-test/build evidence only; runtime compatibility remains `NOT_VALIDATED` and `RUNTIME_APPROVED: NOT_APPROVED`. Historical Run 001 passed ROS `/scan` existence/type, one data publisher, non-empty ranges, and clean teardown; `/parameter_events` and `/rosout` are standard ROS node endpoints. Its sole audited failure was the sensor-source `LaserScan.header.frame_id` mismatch (`ROBOT_URDF_final/base_link/YDLIDAR_X3_PRO` instead of `lidar_frame`). Runtime Run 002 remains the historical `WP06_6E_RUNTIME_FRAME_CONTRACT_FAIL_NO_RETRY`; its record is unchanged and no runtime retry is performed. This correction retains `<frame_id>lidar_frame</frame_id>` and adds `<gz_frame_id>lidar_frame</gz_frame_id>` as direct children of the existing Gazebo sensor, with the current `gazebo_lidar_source` pin reconciled to `9ff2dd9578b069cc492c9ff05e7f7f0d952c8bad0c5ecd9710ccea63d9fb1bbd` in profile YAML, Python descriptor, and WP-05 manifest. The bridge does not rewrite headers. A new capacity-one runtime requires independent audit and separate Owner authorization on the exact corrective commit. No endpoint-address pin, new runtime evidence, TF, odometry, command bridge, profile resolution, `ResolvedConfigV3`, `config_hash`, Gate B transition, or runtime approval is created. WP-04 remains `BLOCKED_BY_CONTRACT`; WP-05 `OPEN`; Gate A `PASSED`; Gate B `NOT_STARTED`.


### WP06-6E dependency lock scope correction — review candidate

The WP-05 external dependency lock and Navigation V1 source-lock template remain byte-identical to the base and continue to contain exactly the 14 common Navigation V1 roots. The package adds `ros_gz_bridge`, `launch`, and `launch_ros` as profile-specific `exec_depend` entries for the `sim_eval` bridge, after those 14 common roots. The corrected dependency-lock test checks the two scopes separately and rejects adding the profile-specific dependencies to the WP-05 common lock.

These declarations are source-level only. Runtime compatibility remains `NOT_VALIDATED`; no ROS `/scan` evidence, endpoint-address pin, TF/odom/command bridge, runtime authorization, or Gate B transition is created. `RUNTIME_APPROVED: NOT_APPROVED`.


## WP06-6E Run 003 runtime evidence disposition — L1 candidate

At integrated source commit `8bd998d6c118239d70f1d4a7b73e145795e8f921`, independent review of the externally stored Run 003 raw evidence passed for the scan-bridge boundary only. Raw hashes were recalculated and ROS transcripts independently parsed: `/scan` is `sensor_msgs/msg/LaserScan`, has one data publisher, bridge-node publishers are exactly `/scan`, `/parameter_events`, and `/rosout`, no forbidden odometry/command/TF/map publisher was observed, `header.frame_id` is `lidar_frame`, and `ranges` contains 129 values. Bootstrap and bridge teardown had no live/zombie members. The disposition manifest records hashes and external provenance; no raw runtime file is copied or modified.

The immutable Run 003 `run_record.json` still says `WP06_6E_RUNTIME_DUAL_FRAME_CONTRACT_FAIL_NO_RETRY`: its parser mishandled multi-document YAML and node-info indentation. The embedded self-hash is not trusted; independently recomputed raw transcript hashes and the read-only reconciliation addendum support the bounded audit. Run 003 was not replayed. Run 001 and Run 002 remain historical failures. Current WP06-6E status is `WP06_6E_SCAN_BRIDGE_RUNTIME_OBSERVED_AND_AUDITED_PASS`, limited to scan-bridge runtime scope, not whole navigation profile compatibility. `RUNTIME_APPROVED: NOT_APPROVED`; `GATE_B: NOT_STARTED`. No endpoint pin, profile resolution, `ResolvedConfigV3`, `config_hash`, or TF evidence is created.


## WP06-6C sim_eval wheel/IMU runtime ingress activation — L2 review candidate

At exact base `bd749560e50e11963873c33a51f806e420c38392`, this candidate implements offline-only two-waypoint GZ-to-ROS staging source: `/joint_states` (`gz.msgs.Model`) to `/sim_eval/wheel_joint_states` (`sensor_msgs/msg/JointState`) and `/sim_eval/imu/raw` (`gz.msgs.IMU`) to `/sim_eval/imu_raw` (`sensor_msgs/msg/Imu`), followed by the existing wheel/IMU ingress node publishing the existing canonical wheel-derived `/wheel/odometry_raw` and normalized `/imu/data`. The dedicated launch starts only `ros_gz_bridge/parameter_bridge` and the ingress node, sets the `sim_eval` partition, and requires `use_sim_time=true`. The IMU source sensor has `frame_id` and `gz_frame_id` set to `base_link` as direct children.

The current Gazebo-source SHA changes from `9ff2dd9578b069cc492c9ff05e7f7f0d952c8bad0c5ecd9710ccea63d9fb1bbd` to `7bbaa475578600d8e18e437fa83720483b90b4af2bf4212151257152429576a2`; only current WP-05 static-profile provenance records are reconciled. WP-05 external dependency lock, historical inventory, and static-policy manifest are unchanged. WP06-6E Run 003 disposition/raw evidence stay historical and unchanged at the former source hash; its audit remains bounded to the scan-bridge scope.

Status: `IMPLEMENTED_OFFLINE_BRIDGE_AND_INGRESS_SOURCE_ONLY`; `runtime_eligible: false`; runtime evidence `NOT_CREATED`. No `/odom`, `/ground_truth/odom`, `/tf`, `/tf_static`, EKF, Nav2, AMCL, Map Server, or command publisher is added/launched by this candidate. WP-04 `BLOCKED_BY_CONTRACT`, WP-05 `OPEN`, `RUNTIME_APPROVED: NOT_APPROVED`, and `GATE_B: NOT_STARTED` remain unchanged. No runtime authorization or navigation-ready assertion is made.

### WP06-6C Run 001 IMU observability correction — existing review branch

Read-only recalculation of the external Run 001 artifact set found all 35 files and SHA256SUMS entries consistent with `artifact_manifest.json`. The immutable run remains `WP06_6C_RUNTIME_FAIL_NO_RETRY`: the ROS staging `/sim_eval/imu_raw` payload was not captured and the `/imu/data` echo timed out with empty stdout/stderr. Topic info shows publisher/subscriber endpoints but is not payload proof. Therefore A (Gazebo source emission), B (bridge transfer), and C (normalizer rejection) are all `NOT_PROVEN`; finding: `RUN001_RAW_IMU_STAGING_SAMPLE_NOT_CAPTURED_ROOT_CAUSE_NOT_PROVABLE`.

The correction is observability-only: one structured first-accept record and first record per normalizer rejection gate, plus an offline YAML multi-document transcript parser using `yaml.safe_load_all`. It changes no sensor, bridge, IMU acceptance semantics, wheel behavior, or public ROS topic. A future runtime packet must also capture a Gazebo-side `/sim_eval/imu/raw` payload to distinguish A from B, as well as ROS staging payload, verbose staging topic info, canonical `/imu/data`, and gate diagnostics. Current evidence is source/offline tests only; `runtime_eligible: false`; corrective runtime evidence not created; `RUNTIME_APPROVED: NOT_APPROVED`; Gate B `NOT_STARTED`.


### WP06-6C Run 002 world IMU-system correction — existing review branch

The proven Run 002 finding is `GAZEBO_IMU_SYSTEM_PLUGIN_ABSENT`: no Gazebo
publisher was observed on `/sim_eval/imu/raw`, while wheel and scan paths
operated; the local probe world had `gz-sim-sensors-system` but lacked
`gz-sim-imu-system`. The corrective source adds exactly one world-level
`gz-sim-imu-system` plugin and an offline XML regression test for exactly one
world-level Sensors and IMU system. This does not establish runtime sensor,
bridge, or normalizer success. Run 002 remains immutable and is not replayed.
Evidence remains offline source/test/build only; `runtime_eligible: false`,
runtime evidence not created, and `RUNTIME_APPROVED: NOT_APPROVED`.

## WP06-6C Run 003 runtime evidence disposition — current bounded status

Canonical runtime evidence disposition: `docs/governance/evidence/WP-06_6C_WHEEL_IMU_RUNTIME_INGRESS_RUN_003_MANIFEST.json`. Independent audit passed for the exact review source commit `9c945a4d52058e3f3cb3b8285e5cb017582fd8af`, limited to Gazebo IMU → ROS staging → normalizer → `/imu/data`, wheel ingress, effective `use_sim_time`, and teardown. Run 001 and Run 002 remain immutable historical failures. The disposition does not assert whole-graph, EKF, Nav2, AMCL, Map Server, global TF, or navigation-profile validation. `RUNTIME_APPROVED: NOT_APPROVED`; `GATE_B: NOT_STARTED`; no new runtime authorization is issued. Integration is eligible only pending final independent audit of the exact L1 disposition commit and Owner decision.


## WP06-6F Run006 topology false-negative correction — current bounded status

Run005 is immutable historical outcome `WP06_6F_RUNTIME_RUN005_FAIL_NO_RETRY_GUARD_CONSUMED`. Its raw node-info transcripts include ROS-standard `/parameter_events` and `/rosout`; the checker included those endpoints in the EKF business endpoint equality check and produced a false negative. Other Run005 acceptance findings passed; this checker failure does not indicate TF/EKF/clock/robot failure. Run001–Run005 artifacts are immutable and are not retried.

Run006 introduces a separate offline runner and capacity-one guard. It parses `Publishers` and `Subscribers` sections and removes only direction-allowed ROS-standard endpoints before exact business-topic equality: `/parameter_events` in either section and `/rosout` only in `Publishers`. Wrong-direction standard endpoints and all other extra endpoints fail closed. `/set_pose` remains restricted to the EKF subscriber and must have exact type, zero publishers, and no payload.

Run006 guard seed is `PENDING_EXACT_INTEGRATION_AND_USER_AUTHORIZATION`, capacity 1, acquisition count 0, `runtime_authorization=NOT_GRANTED`. Evidence ceiling: `IMPLEMENTED_OFFLINE_RUN005_TOPOLOGY_FALSE_NEGATIVE_CORRECTION_RUN006_GUARD_PENDING`; `runtime_eligible: false`; runtime evidence `NOT_CREATED`; `RUNTIME_APPROVED: NOT_APPROVED`; `GATE_B: NOT_STARTED`.


### WP06-6F Run007 current candidate

Canonical Run007 guard manifest: `docs/governance/evidence/WP-06_6F_TF_EKF_RUNTIME_INGRESS_RUN_007_GUARD_MANIFEST.json`. Run007 có runner, guard và guard seed riêng. Run006 là historical runner finalization failure (mọi acceptance được ghi true sau teardown nhưng terminal failure đã bị quyết định trước teardown); không phải TF/EKF/clock/robot failure và không retry. Run007 chỉ là offline source/test/build candidate, guard pending capacity one, runtime chưa được authorize hoặc thực thi. Evidence ceiling: `IMPLEMENTED_OFFLINE_RUN006_FINALIZATION_ORDER_CORRECTION_RUN007_GUARD_PENDING`.

#### WP06-6F Run007 Owner authorization binding corrective

Canonical Run007 manifest/evidence/decision pin the exact scope literal `WP06_6F_RUN007_ONE_OFFICIAL_RUNNER_INVOCATION_CAPACITY_ONE_NO_RETRY`. The future official runner requires five non-empty Owner authorization arguments and exact binding to Run007, expected review commit and integration base before any guard acquisition. Guard acquisition is the only operation that records `GRANTED_FOR_THIS_EXACT_RUN_ONLY`, owner metadata and acquired refs; the committed seed remains pending with capacity 1 and acquisition count 0. The run record v2 preserves all five values, acquisition count and before/after guard states. Offline evidence only; no authorization was supplied to or consumed by this candidate; `RUNTIME_APPROVED: NOT_APPROVED`; `GATE_B: NOT_STARTED`.


### WP06-6F Run007 — audited runtime evidence disposition

Canonical L1 disposition manifest: `docs/governance/evidence/WP-06_6F_TF_EKF_RUNTIME_INGRESS_RUN_007_MANIFEST.json`. The read-only audit records `WP06_6F_RUN007_INDEPENDENT_EVIDENCE_AUDIT_PASS` for runtime source commit `93468611748e3966cd6fa7fa280e840651d2c895`, integration base `8b73bcb0b026fe337c023f6a30205dbe89d31eb5`, and external evidence directory `/home/hazan/wp06_runtime_evidence/WP06_6F_TF_EKF_RUNTIME_INGRESS_RUN_007`. Scope is only the WP06-6F ingress/clock/EKF/TF evidence and teardown captured in that run. Run001–Run006 remain immutable historical. This supersedes only the previous current Run007 pending-audit status. It does not validate Nav2, AMCL, Map Server, the whole ROS graph, Gate B, or navigation readiness. `RUNTIME_APPROVED: NOT_APPROVED`; `GATE_B: NOT_STARTED`; the Run007 guard remains consumed and no runtime authorization is issued.


## Step-7 Gate B authority/input closure survey — provenance record

The review candidate `step-07-gate-b-authority-input-closure-5471e88` is based on exact integration source base `5471e8860050326215bb83761629e9969def16ea`. Its survey decision and evidence record are `docs/governance/decisions/STEP-07_GATE_B_SAFETY_LIFECYCLE_PPO_AUTHORITY_INPUT_CLOSURE_SURVEY.md` and `docs/governance/evidence/STEP-07_GATE_B_SAFETY_LIFECYCLE_PPO_AUTHORITY_INPUT_CLOSURE_SURVEY.json`. They record source-base provenance and closure findings only. This Registry entry does not reclassify or promote any authority/source, resolve a concrete input/profile, select a map or mode, close Gate B, change WP-04/WP-07 status, or grant implementation/runtime authorization. Existing Registry classifications remain unchanged; the Registry remains the operational source selector, with historical/draft wording interpreted in its source-base context.


## Roadmap Steps 4–6 consolidated closure candidate — current source snapshot

At review base `d44ba711395a50d3ba8b9f91e6f64d1eca8ca5a1`, the initial L2 candidate recorded the supplied sim_eval/NAV2_BASELINE Owner decisions. Its original decision/evidence hashes (`775a0e22…` / `45352361…`) identify that prior snapshot only. The unchanged comment-only `FinalIssuedCommandReceipt.msg` hash remains `bc8bfd11960079271b78ddfe2b3c3dbf0204959d6dcef44fa8565b6a6384fa0c`; the older `0c644667…` value above remains a historical pin for its earlier byte set. The Step-4 manifest remains `43584fd2d4d17e7a90d10a78c073227639823ba71e0d2c68b72a5652c7055cf6`. Current corrective evidence and source pins are recorded in the following entry.

Candidate-only status: Step 4 `CLOSED_FOR_SIM_EVAL`; Step 5 `IMPLEMENTED_OFFLINE_ONLY`; Step 6 `IMPLEMENTED_OFFLINE_ONLY`; roadmap Step 7 `NOT_STARTED`; `RUNTIME_APPROVED: NOT_APPROVED`; `GATE_B: NOT_STARTED`. This record is provenance/status only and does not alter the classification or semantics of existing authorities. No runtime, Nav2 live, AMCL convergence, complete TF graph, PPO training, HIL, or hardware validation is claimed.

## Roadmap Steps 4–6 corrective L2 source assembly and safety closure

The corrective candidate is based on parent `d8db18aa3a5819b42d130221904281cec3360cae`; its exact source/config/test pins are in the current `source_pins` array of `docs/governance/evidence/ROADMAP_STEP4_STEP5_STEP6_CONSOLIDATED_CLOSURE.json`. It binds the selected map root and hashes at launch, checks the exact Owner-bound Fuel cache layout before Gazebo launch actions, removes constructor lifecycle auto-transitions, provides explicit reset/rearm services, drives the safety core from immutable YAML policy values, defaults the sim-only E-stop boundary active, and binds canonical `/imu/data` and `/wheel/odometry_raw` ownership to `mecanum_base_bridge`. The package has source/build/offline-test evidence only; no runtime graph, Nav2-live, HIL, hardware, PPO, Gate B, or runtime approval claim is made. Historical WP06 Run001–Run007 files remain immutable. Existing statuses remain Step 4 `CLOSED_FOR_SIM_EVAL`, Step 5/6 `IMPLEMENTED_OFFLINE_ONLY`, Step 7 `NOT_STARTED`, `RUNTIME_APPROVED: NOT_APPROVED`, and `GATE_B: NOT_STARTED`.

Corrective decision SHA-256: `0e1a84b8c2a8147db8ce57522aa55648241df110920830b29e28145273e988d5`; current corrective evidence SHA-256: `f757d8e9b035c23e27f01d44afa37082f4e62a061324ace6b0cf5fa91e349ff3`. Offline evidence records five-package build PASS, `mecanum_nav_rl/test` 701 PASS, `mecanum_nav_bringup/test` 234 PASS, ROSIDL colcon test 11 PASS, installed source/config byte equality, ROSIDL imports, and all three safety executables. Evidence ceiling remains `STATIC_SOURCE_OFFLINE_BUILD_TEST_READY_FOR_STEP7_RUNTIME_CAMPAIGN`; Gate B and runtime approval are unchanged.


#### Safety lifecycle managed-entity and receipt corrective L2

Current corrective parent is `04a2ba5332ea56feb24dc3cf393114d8158bcb62`. Decision SHA-256: `0e1a84b8c2a8147db8ce57522aa55648241df110920830b29e28145273e988d5`; evidence JSON SHA-256: `f757d8e9b035c23e27f01d44afa37082f4e62a061324ace6b0cf5fa91e349ff3`. The exact 14-path corrective records standard ROS lifecycle callback delegation, `CommandEnvelope.episode_generation`, identity matching before NAV2 publication, and one receipt after each successful final command publication; command publish failure yields no receipt. Historical WP06 artifacts remain byte-preserved. Evidence ceiling remains `STATIC_SOURCE_OFFLINE_BUILD_TEST_READY_FOR_STEP7_RUNTIME_CAMPAIGN`; no runtime, Gate B, Step 7 PASS, or `RUNTIME_APPROVED` is asserted.

### Roadmap Steps 4–6 corrective metadata reconciliation — L1

The current underlying L2 corrective is exact commit `dbc00940f9f70a4ee3a846ceb6fde1964c35ff19`, parent `04a2ba5332ea56feb24dc3cf393114d8158bcb62`: exactly 14 changed paths and 46 source pins, verified as raw Git blobs with matching SHA-256 and byte size. Its offline test results are 701 `mecanum_nav_rl` tests, 234 `mecanum_nav_bringup` tests, and 11 interface `colcon test` cases. Corrective scope includes managed lifecycle publisher callback delegation, `CommandEnvelope.episode_generation`, SafetySupervisor lifecycle identity propagation, NAV2 identity checks in FinalTwistPublisher, and receipt-after-successful-final-publish behavior with regression coverage.

The L1 reconciliation candidate changes exactly five governance paths; this is distinct from the underlying 14-path L2 packet. Decision: `docs/governance/decisions/ROADMAP_STEP4_STEP5_STEP6_CONSOLIDATED_CLOSURE.md`, SHA-256 `0d5927d672b1d7c8083c50638f9b77ec8b9eac94f17a3b27bb460aa3ae167920`. Evidence: `docs/governance/evidence/ROADMAP_STEP4_STEP5_STEP6_CONSOLIDATED_CLOSURE.json`, SHA-256 `16a513a01e2ba71aaac99d6c4cee71ca36c22ce6cec811d1a0e92a60d78c6e39`. These supersede stale current metadata on parent, scope, pin count and test totals; earlier Ledger records remain historical. Evidence ceiling and status remain unchanged; no runtime, Gate B or `RUNTIME_APPROVED` claim is made.


## Step-7 integrated NAV2_BASELINE Gate-B campaign Run001 — review candidate

Candidate `STEP07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN001` is based on `f7f98c683d59cf4c62e462da9f37d4ffb2455c80`. Its source/offline machinery, exact source pins, guard seed and acceptance-to-collector matrix are recorded in `docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN001_L2_EVIDENCE.json` and the guard manifest beside it. This entry records provenance only and does not change existing authority classifications or statuses.

The Run001 guard seed is capacity one and remains `PENDING_EXACT_INTEGRATION_AND_USER_AUTHORIZATION`, `acquisition_count=0`, `runtime_authorization=NOT_GRANTED`. No owner authorization was supplied or consumed, and this candidate did not call its runner. Evidence ceiling is `IMPLEMENTED_SOURCE_AND_OFFLINE_TEST_CAMPAIGN_MACHINERY_ONLY`; runtime evidence is `NOT_CREATED`; `GATE_B: NOT_STARTED`; `RUNTIME_APPROVED: NOT_APPROVED`. Run001–Run007 WP06 historical evidence remains immutable.

Offline verification for this Run001 review candidate: six-package colcon build PASS; 705 `mecanum_nav_rl/test` tests and 237 `mecanum_nav_bringup/test` tests PASS; C++ observer and interface colcon tests 11 each PASS; 36 focused campaign tests PASS. Installed closure checks passed. This is source/build/offline-test evidence only; runtime evidence remains `NOT_CREATED`.

### Step-7 Run001 separated bootstrap/composite topology correction

The current review candidate remains based on `f7f98c683d59cf4c62e462da9f37d4ffb2455c80` and adds exactly two approved paths to the earlier 21-path scope: the canonical composite launch and its static launch test. The composite defaults `start_bootstrap=true` and validates map/Fuel in both modes; `false` supports the runner's distinct bootstrap/composite process groups. Runner evidence records independent invocation counts, PIDs/PGIDs, commands, readiness, return codes and snapshots, with composite-first then bootstrap SIGINT teardown.

Decision SHA-256 `f03d04e1c6ccca2229773d4e417a68c3c280d778a2a01835b920cca1b3f172b2`; evidence SHA-256 `ec4c059ff3a0fa39df0b887426ae0517efda9b9820ecab6a2bad6a34135a973c`; guard manifest SHA-256 `11343554c3d0dec9b82ee7ef90a976e67828913fbfc991962988ba81f40830fb`. The guard is still pending/capacity-one/not authorized. Offline-only result: six-package build, 705 `mecanum_nav_rl` tests, 238 `mecanum_nav_bringup` tests, 22 C++ observer/interface tests, and 45 focused tests passed. No runtime, Gate B transition or runtime approval is claimed.

## Step-7 Run001 lifecycle endpoint/QoS source correction

The current corrective review snapshot pins the canonical lifecycle endpoint `/mecanum/safety_lifecycle_state` (SafetyLifecycleState, unique `safety_lifecycle` publisher, RELIABLE + VOLATILE + KEEP_LAST(10)); both campaign observers request dedicated matching subscription QoS. The evidence validator checks raw graph publisher/subscriber endpoint records and rejects use of `/mecanum/safety/lifecycle_state`. Final receipt QoS remains separately RELIABLE + TRANSIENT_LOCAL + KEEP_LAST(1). The unchanged 16-entry pin set is authoritative in the Run001 guard, evidence, and manifest. No status/classification or runtime authority changes. Refreshed source/test pin deltas:

| Path | SHA-256 | Size (bytes) |
|---|---|---:|
| `artifacts/simulation/step07_nav2_baseline_campaign/tools/step07_gate_b_evidence_validator.py` | `210694c3b9c270e20d4650ca7bb8362ee703c62a0a22bfe6e4f21a8cab970190` | 23255 |
| `artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_gate_b_evidence_validator.py` | `448d2302755c0fc3ce270109bca7266d877db4743050da2f9216c3aa2d97aab3` | 13715 |
| `ros2_ws/src/step07_nav2_baseline_runtime_observer/src/step07_nav2_baseline_runtime_observer.cpp` | `d713d8c67145bfdaf55d4f55c0ab5fcb4b2114013a1aa9d69cff3c27fd925519` | 29652 |
| `ros2_ws/src/step07_nav2_baseline_runtime_observer/test/test_step07_nav2_baseline_runtime_observer.cpp` | `5f2f16d1a06b17cdf5831747c89c76e7c1cdc7743ee7505c685be15e3f8708af` | 7981 |
| `ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/observations/step07_gate_b_observer_node.py` | `32f1c754bfe65268317d2a2cebe34982285a0273a071fb9fb2f25649df4dc4f4` | 21067 |
| `ros2_ws/src/mecanum_nav_rl/test/test_step07_gate_b_observer_node.py` | `4f0f661f507846dd0623877a5a6b93a56e9029f93d1f7f988c745896ab06ae70` | 4580 |

### Historical provisional verification disposition — superseded by contract-test closure

This paragraph records the earlier provisional verification before the Owner-authorized contract-test path was added to scope. At that point the bringup suite had two failures in `test_sim_eval_tf_ekf_runtime_contract.py`; the following contract-test closure records the superseding verification for the amended 14-path candidate. The earlier failure report is historical and is not the current candidate disposition.


### Step-7 Run001 lifecycle-QoS test-contract closure — review candidate

The existing source-pin set remains exactly 16 unique paths; the corrective test path `ros2_ws/src/mecanum_nav_bringup/test/test_sim_eval_tf_ekf_runtime_contract.py` was already present and its entry is refreshed to SHA-256 `8f03f5feef72d81eb86600f2dfcabffe18765fd4db57c1484bd67ec5250dd6db` with size 27451 bytes. The contract test now distinguishes the immutable 23-path root campaign scope from the exact 14-path lifecycle-QoS corrective scope. Offline validation: six-package build PASS; focused tests 49 passed; `mecanum_nav_rl/test` 707 passed; `mecanum_nav_bringup/test` 239 passed; observer/interface colcon tests 25 passed. Historical WP06 evidence remains protected. No runtime was executed; Run001 guard remains pending/unconsumed, Gate B `NOT_STARTED`, and `RUNTIME_APPROVED: NOT_APPROVED`.

### Step-7 Run001 acceptance matrix closure

The Run001 L2 evidence and guard manifest now list the seven lifecycle/receipt-related observer acceptance IDs emitted by `validate_observer`. They contain one each of `lifecycle_endpoint_qos_contract`, `receipt_qos_contract`, and `obsolete_lifecycle_topic_absent`, omit retired `lifecycle_state_publisher_owner`, and use the C++ raw-literal convention `ACCEPTANCE_FAILED:<acceptance_id>`. The validator's earlier `LIFECYCLE_TOPIC_OBSOLETE_OR_IN_USE` rejection is recorded as parser behavior only. Runtime authorization and Gate-B status are unchanged.

### Run001 acceptance-matrix scope-chain closure

The immutable scope chain remains 23 root campaign paths (`f7f98c6..6fbddb3`), 14 lifecycle-QoS corrective paths (`6fbddb3..5fa2e89`), and the exact nine-path acceptance-matrix corrective (`5fa2e89..candidate`). The contract test supports dirty and committed review states and rejects untracked artifacts. Its existing one-of-16 source pin is refreshed in the guard, evidence and manifest; pin cardinality remains 16 unique paths.


### STEP07_NAV2_BASELINE_RUN_002 — pre-acquire failure evidence candidate

Run002 uses independent guard, runner, tests, and source-pin inventory recorded in `docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN002_L2_EVIDENCE.json` (16 Run002 source pins). The seed is PENDING, capacity one, acquisition count zero, and runtime authorization NOT_GRANTED. Run001 remains immutable with its historical pre-acquire failure disposition; no Run001 pin inventory is reused as Run002 provenance. No runtime evidence or Gate B transition is claimed.


Run002 source-pin inventory (16 unique pins; path SHA-256 and byte size are mirrored exactly in the Run002 seed guard, L2 evidence, and guard manifest):

| Path | SHA-256 | Size (bytes) |
|---|---|---:|
| `artifacts/simulation/step07_nav2_baseline_campaign/tools/step07_run002_runtime_guard.py` | `5057f2a1474b14e64de32fd2f1d2d1a30078fbdf7fa956d6628a60a146fa49ff` | 8199 |
| `artifacts/simulation/step07_nav2_baseline_campaign/tools/run_step07_nav2_baseline_run002.py` | `69f71af7ebb1ebc55fd10aa783218ad2d3914784d33a7c7e180c82bba044f1b3` | 45236 |
| `artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_run002_runtime_guard.py` | `cab62fa394887f83304916fb41e1fed784c77d1e9dd8d5f3a987c17d42281338` | 2668 |
| `artifacts/simulation/step07_nav2_baseline_campaign/tools/test_run_step07_nav2_baseline_run002.py` | `58a4f7f0e91d1a1528ce3ea53bfa8b0410f8aef57a06d2e9c2e866c355663467` | 8550 |
| `artifacts/simulation/step07_nav2_baseline_campaign/tools/step07_gate_b_evidence_validator.py` | `210694c3b9c270e20d4650ca7bb8362ee703c62a0a22bfe6e4f21a8cab970190` | 23255 |
| `artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_gate_b_evidence_validator.py` | `f5b2f0a96aac0bbc429a5ab41a19f558006d05f19c54b9a5d5ec8c7f429ec795` | 17061 |
| `ros2_ws/src/step07_nav2_baseline_runtime_observer/src/step07_nav2_baseline_runtime_observer.cpp` | `d713d8c67145bfdaf55d4f55c0ab5fcb4b2114013a1aa9d69cff3c27fd925519` | 29652 |
| `ros2_ws/src/step07_nav2_baseline_runtime_observer/test/test_step07_nav2_baseline_runtime_observer.cpp` | `5f2f16d1a06b17cdf5831747c89c76e7c1cdc7743ee7505c685be15e3f8708af` | 7981 |
| `ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/observations/step07_gate_b_observer_node.py` | `32f1c754bfe65268317d2a2cebe34982285a0273a071fb9fb2f25649df4dc4f4` | 21067 |
| `ros2_ws/src/mecanum_nav_rl/test/test_step07_gate_b_observer_node.py` | `4f0f661f507846dd0623877a5a6b93a56e9029f93d1f7f988c745896ab06ae70` | 4580 |
| `ros2_ws/src/mecanum_nav_bringup/launch/sim_eval_nav2_baseline_system.launch.py` | `283010f115b1608f8a73613f45e4da674f54ec93c2b91584d86b9514030fb013` | 8870 |
| `ros2_ws/src/mecanum_nav_bringup/test/test_sim_eval_nav2_baseline_system_launch.py` | `2bc2901a9fad989149ac663b42ac9ac55e926483056431e09b4b073f38770d14` | 6391 |
| `ros2_ws/src/mecanum_nav_bringup/test/test_sim_eval_tf_ekf_runtime_contract.py` | `d44339ff4edd064f3c28dc98c2e19eed0b72f1c8588bcd44198b0337c7fc21d5` | 30381 |
| `ros2_ws/src/ROBOT_URDF_final_description/launch/tugbot_depot.sdf` | `a4b6253340baa866d89640d62a94d04fbea51425e9af1deca591422a0a36d91d` | 12364 |
| `ros2_ws/src/mecanum_nav_rl/config/v3/resolved/sim_eval_nav2_baseline.resolved.json` | `3841d1a1c2e9e1a4883431f05d7d5ff13e0b687569e5734f0b4f91aa69294b84` | 5326 |
| `artifacts/maps/warehouse_map2/map.yaml` | `5073762401784f67e856b5018656ad869ecc26e723f85e5979054eadc7876a68` | 125 |


### Run002 historical-pin reference policy and scope-chain correction

The Run001 pending guard’s 16 historical source pins are checked from Git blobs at `5a44cd9910e9b6d6058d8d2d9252a86f7cf9dcd8`, including exact byte length; absent objects or mismatches fail closed without checkout fallback. Run002 pins remain a distinct 16-entry inventory over current worktree bytes. Its corrective scope is exactly 13 paths and the contract preserves the 23 → 14 → 9 → 13 path chain. Run001 guard/runtime semantics and historical outcomes are unchanged.

### STEP07_NAV2_BASELINE_RUN_003 — Fuel path normalization candidate

Run003 tạo candidate offline cho mapping Fuel cache lowercase. Run002 historical outcome vẫn là `STEP07_NAV2_BASELINE_RUN002_PREACQUIRE_PREFLIGHT_FAILED_NO_GUARD_CONSUMED`, root cause `FUEL_CACHE_PATH_CASE_NORMALIZATION_MISMATCH`; pre-acquire evidence mechanism đã được chứng minh trong record Run002 và không có retry. Run003 seed PENDING/capacity-one/acquisition 0/NOT_GRANTED. Host Depot asset chưa được xác minh hoặc provision trong candidate.

Run003 evidence: `docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN003_L2_EVIDENCE.json` (SHA-256 `2f26ff124310e55568605f8e8d9958fa19c673955e257bcd41bc35fe0bc762f6`); guard manifest SHA-256 `121b0f1b02dce97811397168286a55bddc99160b61062fb09b8e93fdde57fa65`; decision SHA-256 `04ef84ed664fcdde8d0d9e6eb902632e1a001e8687f3caa077a33dfccadf3d29`. Direct scope: exactly 14 paths from exact base `6d730bd54d7f99429ee4832a3f6f96beffae020f`, comprising the original 13 Run003 paths plus the Owner-authorized historical Run002 guard-test reconciliation path. That additional test reads Run002 Git blobs at its pinned commit and is not added to the 16-entry Run003 runtime source-pin inventory.

Run003 source inventory (16 unique current-worktree SHA-256 and byte-size pins, mirrored in Run003 seed/evidence/manifest):

| Path | SHA-256 | Size (bytes) |
|---|---|---:|
| `artifacts/maps/warehouse_map2/map.yaml` | `5073762401784f67e856b5018656ad869ecc26e723f85e5979054eadc7876a68` | 125 |
| `artifacts/simulation/step07_nav2_baseline_campaign/tools/run_step07_nav2_baseline_run003.py` | `e8801e6329411d5d80baadb7f73172bc91612965c3c53628d52c5e572b62a9c7` | 46288 |
| `artifacts/simulation/step07_nav2_baseline_campaign/tools/step07_gate_b_evidence_validator.py` | `210694c3b9c270e20d4650ca7bb8362ee703c62a0a22bfe6e4f21a8cab970190` | 23255 |
| `artifacts/simulation/step07_nav2_baseline_campaign/tools/step07_run003_runtime_guard.py` | `8e30f9671ca67e25a332afe0b5fd3c7c78fa37a67035106dcf1a54b533bafb6b` | 8942 |
| `artifacts/simulation/step07_nav2_baseline_campaign/tools/test_run_step07_nav2_baseline_run003.py` | `12d0886bd2823aad00a75f9766c522294dc6c24cc341b9adba804da9295384b6` | 12757 |
| `artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_gate_b_evidence_validator.py` | `f5b2f0a96aac0bbc429a5ab41a19f558006d05f19c54b9a5d5ec8c7f429ec795` | 17061 |
| `artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_run003_runtime_guard.py` | `a7b907a87b3b3bee3c75263261aeee5c06f70c92289b1b82c28c544cc64ecba7` | 4826 |
| `artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_runtime_guard.py` | `3a672e0516d975c83998df691e9a01099a2f8dbfcdd5bcac37b8a07891020a26` | 9920 |
| `ros2_ws/src/ROBOT_URDF_final_description/launch/tugbot_depot.sdf` | `a4b6253340baa866d89640d62a94d04fbea51425e9af1deca591422a0a36d91d` | 12364 |
| `ros2_ws/src/mecanum_nav_bringup/launch/sim_eval_nav2_baseline_system.launch.py` | `283010f115b1608f8a73613f45e4da674f54ec93c2b91584d86b9514030fb013` | 8870 |
| `ros2_ws/src/mecanum_nav_bringup/test/test_sim_eval_nav2_baseline_system_launch.py` | `2bc2901a9fad989149ac663b42ac9ac55e926483056431e09b4b073f38770d14` | 6391 |
| `ros2_ws/src/mecanum_nav_bringup/test/test_sim_eval_tf_ekf_runtime_contract.py` | `d16c487554495e73dbbdd8f7df857b383897db6a804c85aef9a1572c2486203d` | 32084 |
| `ros2_ws/src/mecanum_nav_rl/config/v3/resolved/sim_eval_nav2_baseline.resolved.json` | `3841d1a1c2e9e1a4883431f05d7d5ff13e0b687569e5734f0b4f91aa69294b84` | 5326 |
| `ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/observations/step07_gate_b_observer_node.py` | `32f1c754bfe65268317d2a2cebe34982285a0273a071fb9fb2f25649df4dc4f4` | 21067 |
| `ros2_ws/src/mecanum_nav_rl/test/test_step07_gate_b_observer_node.py` | `4f0f661f507846dd0623877a5a6b93a56e9029f93d1f7f988c745896ab06ae70` | 4580 |
| `ros2_ws/src/step07_nav2_baseline_runtime_observer/src/step07_nav2_baseline_runtime_observer.cpp` | `d713d8c67145bfdaf55d4f55c0ab5fcb4b2114013a1aa9d69cff3c27fd925519` | 29652 |

No runtime evidence, Gate B transition, or `RUNTIME_APPROVED` is claimed. Run001/Run002 and WP06 historical artifacts are unchanged.

## Step-7 Run004 host provisioning environment decoupling — corrective candidate

Run004 L1 corrective base `cbf59ff938d8b96ec650859d9367bc6cb840f0c6`; original Run004 candidate remains the exact 17-path diff from `fdc0e299515bda2286832aabec635948629517b5`. This corrective is exactly 11 paths, with a four-path source/test Phase A. It removes the provisioning helper's pre-source `rclpy` dependency: the helper checks only outside-repository Python 3.12/Pydantic 2.10.6/executable/fingerprint closure and defers `rclpy` to the official runner after ROS/overlay sourcing. Runner `rclpy`, Gate-B observer and installed-overlay checks remain fail-closed. Run004 has 20 current-worktree SHA-256/size pins; Run001–Run003 use exact historical Git blobs with no fallback. Guard remains pending, capacity 1, acquisition 0, NOT_GRANTED. Evidence SHA-256 `e3b9eaab981f7bcb44192fcc1d61af53c79878f79103037a3857adc4389ff8ff`; manifest SHA-256 `1369bac8fd60586a8e2231ff9f458cdc2820cfa599c32ab6e35df98533a0c376`; decision SHA-256 `f4dd7b7c4b24eceeae85bb08812ea32ac9c3029b681f127816349176c6997b0a`. No runtime evidence, Gate B transition or `RUNTIME_APPROVED` is claimed.


### STEP07 Run005 installed package-prefix closure — L1 review candidate

Run004 is the immutable pre-acquire failure `STEP07_NAV2_BASELINE_RUN004_PREACQUIRE_PREFLIGHT_FAILED_NO_GUARD_CONSUMED`; the sole root cause is `PACKAGE_PREFIX_CLOSURE_MISSING_ROBOT_URDF_FINAL_DESCRIPTION`. No Run004 retry or historical reinterpretation is made. Run005 adds the missing `ROBOT_URDF_final_description` package prefix and verifies that every package used in installed-file equality checks belongs to the exact collected prefix set before those byte comparisons. The exact package closure is ros_gz_sim, ros_gz_bridge, mecanum_base_bridge, mecanum_nav_bringup, ROBOT_URDF_final_description, robot_localization, step07_nav2_baseline_runtime_observer, and mecanum_nav_rl.

Run005 exact base `b7105ccb651da6d0dcb916d7544481f7beacaae1`; exact 13-path scope. The 21 unique Run005 runtime source pins below use current candidate bytes with SHA-256 and byte size; this count is independent of delivery scope. Run001–Run004 historical source pins are read from exact historical Git blobs and fail closed on missing/mismatched bytes, with no worktree fallback. Historical scope chain remains 23 → 14 → 9 → 13 → 14 → 17 → 11; current Run005 scope is 13.

| Path | SHA-256 | Size (bytes) |
|---|---|---:|
| `artifacts/maps/warehouse_map2/map.yaml` | `5073762401784f67e856b5018656ad869ecc26e723f85e5979054eadc7876a68` | 125 |
| `artifacts/simulation/step07_nav2_baseline_campaign/tools/prepare_step07_runtime_python_environment.py` | `01f09ddf82d61f239bbee9e002868f9c3d027526b02ddfe1e0c0e0b31fb7b79e` | 5330 |
| `artifacts/simulation/step07_nav2_baseline_campaign/tools/run_step07_nav2_baseline_run005.py` | `c5f6d39870b58571ad97fb11d5e9ad526c0d94093f8b27588de46454128bdc2a` | 50866 |
| `artifacts/simulation/step07_nav2_baseline_campaign/tools/step07_gate_b_evidence_validator.py` | `210694c3b9c270e20d4650ca7bb8362ee703c62a0a22bfe6e4f21a8cab970190` | 23255 |
| `artifacts/simulation/step07_nav2_baseline_campaign/tools/step07_run005_runtime_guard.py` | `ab838d7fc952d5b625391fc59f1d38682915e53aefa0232315672a17e7a3a71f` | 9468 |
| `artifacts/simulation/step07_nav2_baseline_campaign/tools/step07_runtime_python_requirements.txt` | `6560f131b6d82cef455b70cd8952a814dd3811dec73108d69b3d9206c95c9573` | 17 |
| `artifacts/simulation/step07_nav2_baseline_campaign/tools/test_run_step07_nav2_baseline_run005.py` | `0077a45ced974364d3fbbcdab5d07d63f7bea538be968c00212c1eaf0da1d03f` | 30969 |
| `artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_gate_b_evidence_validator.py` | `f5b2f0a96aac0bbc429a5ab41a19f558006d05f19c54b9a5d5ec8c7f429ec795` | 17061 |
| `artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_run003_runtime_guard.py` | `d36d809d9174ec17d9e3df9771176c42d4c351aee890ae13668828194763af82` | 7036 |
| `artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_run004_runtime_guard.py` | `0f938eedd91eecae4b91a1fbf3b3b1749c0f498a4f1f1eee889ea378ef0d853f` | 7785 |
| `artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_run005_runtime_guard.py` | `d12af8790a0e64726e1a9d5afa06e9ee0a90873e1074dcb272e997f5187438a8` | 5980 |
| `artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_runtime_guard.py` | `c93c4f2d1f87c05e31ad13306b37f20f2f906b14898aa9bbf89a22aab97b99e2` | 11918 |
| `ros2_ws/src/ROBOT_URDF_final_description/launch/tugbot_depot.sdf` | `a4b6253340baa866d89640d62a94d04fbea51425e9af1deca591422a0a36d91d` | 12364 |
| `ros2_ws/src/mecanum_nav_bringup/launch/sim_eval_nav2_baseline_system.launch.py` | `283010f115b1608f8a73613f45e4da674f54ec93c2b91584d86b9514030fb013` | 8870 |
| `ros2_ws/src/mecanum_nav_bringup/test/test_sim_eval_nav2_baseline_system_launch.py` | `2bc2901a9fad989149ac663b42ac9ac55e926483056431e09b4b073f38770d14` | 6391 |
| `ros2_ws/src/mecanum_nav_bringup/test/test_sim_eval_tf_ekf_runtime_contract.py` | `3c10881a239e7ceea8a3c99851d3c32a48235cfce93fbee522f9c154e5c7c10b` | 40343 |
| `ros2_ws/src/mecanum_nav_rl/config/v3/resolved/sim_eval_nav2_baseline.resolved.json` | `3841d1a1c2e9e1a4883431f05d7d5ff13e0b687569e5734f0b4f91aa69294b84` | 5326 |
| `ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/observations/step07_gate_b_observer_node.py` | `32f1c754bfe65268317d2a2cebe34982285a0273a071fb9fb2f25649df4dc4f4` | 21067 |
| `ros2_ws/src/mecanum_nav_rl/test/test_step07_gate_b_observer_node.py` | `4f0f661f507846dd0623877a5a6b93a56e9029f93d1f7f988c745896ab06ae70` | 4580 |
| `ros2_ws/src/step07_nav2_baseline_runtime_observer/package.xml` | `ec322d9068526ba43b878e7ebb249d0587fb9189f49fcb8999e38eea2b68791b` | 733 |
| `ros2_ws/src/step07_nav2_baseline_runtime_observer/src/step07_nav2_baseline_runtime_observer.cpp` | `d713d8c67145bfdaf55d4f55c0ab5fcb4b2114013a1aa9d69cff3c27fd925519` | 29652 |

Decision SHA-256 `3fe0df3816bcbfd4569ae9279b2e6be3ecf8f6041bc07295e1a14455a3ded51c`; evidence SHA-256 `fdc65d78e947fd302acc5e4885d4f2aefefc14d98e98632c8e2d8cbdbf05b777`; guard-manifest SHA-256 `c8abea65d820b6b850e6853e7f52bd1566ff99f1c60647126f30ac871f1d4986`; Run005 guard SHA-256 `4343fa9b5ec7b3fe0c6e1be60628cc2d77fffa16603dc04a04147d28508ba2a1`. Run005 remains pending, capacity one, acquisition zero, `runtime_authorization=NOT_GRANTED`; Gate B `NOT_STARTED`, `RUNTIME_APPROVED=NOT_APPROVED`, runtime evidence not created. No runtime or integration is claimed.


### STEP07 Run005 package-prefix closure final pin/scope reconciliation

This entry supersedes the prior Run005 candidate-only pin and evidence hash references above. The corrected final-scope contract test pin is `ros2_ws/src/mecanum_nav_bringup/test/test_sim_eval_tf_ekf_runtime_contract.py` SHA-256 `50e826ba266c8177ec73c450c0a8a3ea77ae33184d98b0c534c4f08f1d6f409b`, size `40187`. Run005 retains exactly 21 unique current-worktree source pins and an exact 13-path delivery scope. Phase A passed with focused scope/historical tests 46, Step-7 tools 182, bringup 239, RL 707, six-package build PASS, observer/ROSIDL tests PASS, installed source-byte equality 6/6, and parsing/pin/history checks PASS. Historical Run001–Run004 pins use exact Git blobs; Run004 remains its immutable package-prefix pre-acquire failure and was not retried.

Decision SHA-256 `6b9cb13114504f3c2b33e7187c6d32b227f79e2a101c6f57f89a99a21038f72c`; evidence SHA-256 `5a7c70bb5c9a21300d23ab0d2318223fcb1909ff6326b0b6540aba4863baedae`; guard manifest SHA-256 `b51c528653b9b6b58118f020e05c6d2148ae419fc8acb89563cd268dc2542986`; guard SHA-256 `14820301519f35bef273627ca0cd95372413389284df6c824a5f2d37ed3dcf5e`. Run005 guard remains pending/unconsumed; no runtime or integration is claimed.


### STEP07 Run005 attempt_002 Fuel path case-normalization correction

Run005 attempt_001 is the immutable consumed failure `STEP07_NAV2_BASELINE_RUN005_FAIL_NO_RETRY_GUARD_CONSUMED`, root `SIM_EVAL_FUEL_CACHE_MODEL_MISSING:OpenRobotics/Depot` followed by `BOOTSTRAP_EXITED_BEFORE_READINESS`; run-record SHA-256 `374565871f170fb2cbd7a9c089a2d0f47dd4e34d217357769259ef74f5409040`. It was not retried. Attempt_002 retains the Run005 ID and maps the unchanged case-sensitive SDF URIs to lowercase Fuel filesystem parents `openrobotics/depot` and `movai/tugbot`; uppercase parents reject. No cache download or mutation is part of this candidate.

Attempt_002 source-scope base `71ca32471f8e042a0048d319ca39cb9deff0c6f4`; cumulative exact path set is 13 paths, including the isolated-checkout runner correction. Its runtime source-pin inventory is 22 unique current-worktree entries, including the bootstrap launch and Run005 runner pins. Attempt_001 historical pins are read from exact Git blobs at `71ca32471f8e042a0048d319ca39cb9deff0c6f4`, checked by SHA-256/size, and never fall back to worktree bytes. Historical scopes remain 23 → 14 → 9 → 13 → 14 → 17 → 11; attempt_001 is 13 paths and attempt_002 is 13 paths.

Offline results: isolated-checkout runner tests 36 passed; focused bootstrap/scope tests 29 passed; Step-7 tools 185 passed; bringup 239 passed; RL 707 passed; six-package external build passed; observer/ROSIDL tests 25 passed; installed bootstrap launch byte equality and static parsing/pin/scope/history checks passed. No runtime was run.

| Current Run005 attempt_002 source path | SHA-256 | Size (bytes) |
|---|---|---:|
| `artifacts/maps/warehouse_map2/map.yaml` | `5073762401784f67e856b5018656ad869ecc26e723f85e5979054eadc7876a68` | 125 |
| `artifacts/simulation/step07_nav2_baseline_campaign/tools/prepare_step07_runtime_python_environment.py` | `01f09ddf82d61f239bbee9e002868f9c3d027526b02ddfe1e0c0e0b31fb7b79e` | 5330 |
| `artifacts/simulation/step07_nav2_baseline_campaign/tools/run_step07_nav2_baseline_run005.py` | `1738b0e8f03d369cbc8da53a9ce59fd8fe502880b8c296daa870b51ae7c2f57f` | 54367 |
| `artifacts/simulation/step07_nav2_baseline_campaign/tools/step07_gate_b_evidence_validator.py` | `210694c3b9c270e20d4650ca7bb8362ee703c62a0a22bfe6e4f21a8cab970190` | 23255 |
| `artifacts/simulation/step07_nav2_baseline_campaign/tools/step07_run005_runtime_guard.py` | `ab838d7fc952d5b625391fc59f1d38682915e53aefa0232315672a17e7a3a71f` | 9468 |
| `artifacts/simulation/step07_nav2_baseline_campaign/tools/step07_runtime_python_requirements.txt` | `6560f131b6d82cef455b70cd8952a814dd3811dec73108d69b3d9206c95c9573` | 17 |
| `artifacts/simulation/step07_nav2_baseline_campaign/tools/test_run_step07_nav2_baseline_run005.py` | `68bc2e194fa7d38e9ebd2fe5f70f02e40a1b92ce7c213fdd658e01c047b7ed20` | 38428 |
| `artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_gate_b_evidence_validator.py` | `f5b2f0a96aac0bbc429a5ab41a19f558006d05f19c54b9a5d5ec8c7f429ec795` | 17061 |
| `artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_run003_runtime_guard.py` | `d36d809d9174ec17d9e3df9771176c42d4c351aee890ae13668828194763af82` | 7036 |
| `artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_run004_runtime_guard.py` | `0f938eedd91eecae4b91a1fbf3b3b1749c0f498a4f1f1eee889ea378ef0d853f` | 7785 |
| `artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_run005_runtime_guard.py` | `2fb5fd07d368f0ab69855b8b0aac944292c562484a2a1ce54283f72089e96eea` | 6936 |
| `artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_runtime_guard.py` | `c93c4f2d1f87c05e31ad13306b37f20f2f906b14898aa9bbf89a22aab97b99e2` | 11918 |
| `ros2_ws/src/ROBOT_URDF_final_description/launch/sim_eval_nav2_baseline_bootstrap.launch.py` | `4067d6efe3782d7687e237603803d8a1b3ebc3fda4927f8233a50951ae856456` | 7054 |
| `ros2_ws/src/ROBOT_URDF_final_description/launch/tugbot_depot.sdf` | `a4b6253340baa866d89640d62a94d04fbea51425e9af1deca591422a0a36d91d` | 12364 |
| `ros2_ws/src/mecanum_nav_bringup/launch/sim_eval_nav2_baseline_system.launch.py` | `283010f115b1608f8a73613f45e4da674f54ec93c2b91584d86b9514030fb013` | 8870 |
| `ros2_ws/src/mecanum_nav_bringup/test/test_sim_eval_nav2_baseline_system_launch.py` | `2bc2901a9fad989149ac663b42ac9ac55e926483056431e09b4b073f38770d14` | 6391 |
| `ros2_ws/src/mecanum_nav_bringup/test/test_sim_eval_tf_ekf_runtime_contract.py` | `a1693c2bf968ef45bd845bbd4d82b62448059b048c0bda3f30615652fbb52039` | 41194 |
| `ros2_ws/src/mecanum_nav_rl/config/v3/resolved/sim_eval_nav2_baseline.resolved.json` | `3841d1a1c2e9e1a4883431f05d7d5ff13e0b687569e5734f0b4f91aa69294b84` | 5326 |
| `ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/observations/step07_gate_b_observer_node.py` | `32f1c754bfe65268317d2a2cebe34982285a0273a071fb9fb2f25649df4dc4f4` | 21067 |
| `ros2_ws/src/mecanum_nav_rl/test/test_step07_gate_b_observer_node.py` | `4f0f661f507846dd0623877a5a6b93a56e9029f93d1f7f988c745896ab06ae70` | 4580 |
| `ros2_ws/src/step07_nav2_baseline_runtime_observer/package.xml` | `ec322d9068526ba43b878e7ebb249d0587fb9189f49fcb8999e38eea2b68791b` | 733 |
| `ros2_ws/src/step07_nav2_baseline_runtime_observer/src/step07_nav2_baseline_runtime_observer.cpp` | `d713d8c67145bfdaf55d4f55c0ab5fcb4b2114013a1aa9d69cff3c27fd925519` | 29652 |

Decision SHA-256 `ba12bd8e4d24a17e3455622770cf0449dc2724216b93411ee8444fa4ae7d58db`; evidence SHA-256 `79ebedc1c3831760be2b8c5bc2c588588cd237e377d1ba0ff6ff759ff2ee1ed2`; guard-manifest SHA-256 `b95b01b7f98490ae9e157e471790d1d36cb835c8330f91c1ddfc2b1de09b4caa`; guard SHA-256 `ad5feb501244511edbe2fe9aded8e53d984453182aff0b3d14939e8a46dff181`. Run005 remains pending, capacity one, acquisition zero, `runtime_authorization=NOT_GRANTED`; Gate B `NOT_STARTED`; `RUNTIME_APPROVED=NOT_APPROVED`. Evidence ceiling: `SOURCE_OFFLINE_TEST_CANDIDATE_ONLY_NO_RUNTIME_EVIDENCE`.

### STEP07 Run005 attempt_002 isolated runtime checkout correction

At corrective base `72d04391a9d6d83e3e18589212d566f17dc220d1`, the runner replaces linked worktree creation with a local `git clone --no-hardlinks --no-checkout`; it detaches at the exact source HEAD, uses private destination Git metadata, retains the official origin, verifies a clean destination, and confirms source metadata is unchanged. The cumulative attempt_002 path set is exactly 13; 22 source pins remain a separate inventory. The refreshed runner, runner-test, and contract-test hashes are in the active Run005 source-pin table above. No runtime is claimed; the attempt_002 guard remains pending/unconsumed.

Record hashes for this correction: decision `ddff30ade74efaf4d8d8e202de4decdb5594766589097a29a2d6780e7f088180`; evidence `6f4ad54ecfd3b51a17c3a1251ef1322a63b4a9222fca1c47220dfa0bcdb8a24b`; manifest `22e1d9b6bc9d013a831b0ffbb06bddce8a18b05c1ab6092fac88a42a61761818`; guard `4be7b4bd00324ba023c11a2717cdfcc91f8d9418ace98b47de40e2f181cc178f`.


### STEP07 Run005 attempt_002 partition and Nav2 pre-acquire corrective

This entry supersedes only the active attempt_002 scope/pin summary. The original attempt_002 corrective remains its historical exact 13-path diff from `71ca32471f8e042a0048d319ca39cb9deff0c6f4` to `87af41f45d721969f2767d36291252e3b14e3dcb`. The current direct corrective diff from `87af41f45d721969f2767d36291252e3b14e3dcb` is exactly 16 paths. The latest scope test checks both exact path sets.

The child EKF/clock launch accepts only a non-empty supplied partition, forwards it unchanged to ingress and `GZ_PARTITION`, and does not route on the historical WP06 literal. The runner verifies seven Nav2 node package/executable pairs, four plugin-provider package prefixes, and source/installed equality for 15 runtime artifacts before guard acquisition. The four new Nav2 dependencies are profile-specific and are not added to the WP05 14-root lock/template.

There are exactly 34 unique current Run005 source pins (22 existing + 12 new); this inventory is independent of the 16-path delivery scope. Historical Run001–Run005 pins use exact Git blobs and fail closed without worktree fallback. Run005 attempt_002 invocation_002 is immutable: `COMPOSITE_EXITED_BEFORE_READINESS` caused by `LEGACY_WP06_PARTITION_LOCK`; no retry. Attempt_001 and all Run001–Run004 evidence remain immutable.

| Path | SHA-256 | Size (bytes) |
|---|---|---:|
| `artifacts/maps/warehouse_map2/map.yaml` | `5073762401784f67e856b5018656ad869ecc26e723f85e5979054eadc7876a68` | 125 |
| `artifacts/simulation/step07_nav2_baseline_campaign/tools/prepare_step07_runtime_python_environment.py` | `01f09ddf82d61f239bbee9e002868f9c3d027526b02ddfe1e0c0e0b31fb7b79e` | 5330 |
| `artifacts/simulation/step07_nav2_baseline_campaign/tools/run_step07_nav2_baseline_run005.py` | `8d518ec71e9aa1e4707ea48574a7b373b15287973bdb9a4219d57bece74a88cd` | 57583 |
| `artifacts/simulation/step07_nav2_baseline_campaign/tools/step07_gate_b_evidence_validator.py` | `210694c3b9c270e20d4650ca7bb8362ee703c62a0a22bfe6e4f21a8cab970190` | 23255 |
| `artifacts/simulation/step07_nav2_baseline_campaign/tools/step07_run005_runtime_guard.py` | `ab838d7fc952d5b625391fc59f1d38682915e53aefa0232315672a17e7a3a71f` | 9468 |
| `artifacts/simulation/step07_nav2_baseline_campaign/tools/step07_runtime_python_requirements.txt` | `6560f131b6d82cef455b70cd8952a814dd3811dec73108d69b3d9206c95c9573` | 17 |
| `artifacts/simulation/step07_nav2_baseline_campaign/tools/test_run_step07_nav2_baseline_run005.py` | `98430e85ec3afd0c4845a7df57bfd6cdeeb9040f6685a5d95f5fcc31062ed3e8` | 42555 |
| `artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_gate_b_evidence_validator.py` | `f5b2f0a96aac0bbc429a5ab41a19f558006d05f19c54b9a5d5ec8c7f429ec795` | 17061 |
| `artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_run003_runtime_guard.py` | `d36d809d9174ec17d9e3df9771176c42d4c351aee890ae13668828194763af82` | 7036 |
| `artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_run004_runtime_guard.py` | `0f938eedd91eecae4b91a1fbf3b3b1749c0f498a4f1f1eee889ea378ef0d853f` | 7785 |
| `artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_run005_runtime_guard.py` | `d1db51ef78a218fbe929aae28b7c43220b2f8cd3b613ec5c3d1c173437200b11` | 9778 |
| `artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_runtime_guard.py` | `c93c4f2d1f87c05e31ad13306b37f20f2f906b14898aa9bbf89a22aab97b99e2` | 11918 |
| `ros2_ws/src/ROBOT_URDF_final_description/launch/sim_eval_nav2_baseline_bootstrap.launch.py` | `4067d6efe3782d7687e237603803d8a1b3ebc3fda4927f8233a50951ae856456` | 7054 |
| `ros2_ws/src/ROBOT_URDF_final_description/launch/tugbot_depot.sdf` | `a4b6253340baa866d89640d62a94d04fbea51425e9af1deca591422a0a36d91d` | 12364 |
| `ros2_ws/src/mecanum_base_bridge/config/bridge/sim_eval_wheel_imu_ingress.runtime.yaml` | `2dafb19da5daeeb91c451ae57055caa389a0353900525fb9a5861e1c670c6547` | 506 |
| `ros2_ws/src/mecanum_base_bridge/launch/sim_eval_wheel_imu_ingress.launch.py` | `1612ce773eb0b7cb05e4d081eee441418dea32314c3685adcdcd96dd569069b8` | 1795 |
| `ros2_ws/src/mecanum_nav_bringup/config/bridge/sim_eval_clock.runtime.yaml` | `89220ef78125348776575b1a14fa1727c9cb098d9c46d84a74e27e5e8715f0b1` | 143 |
| `ros2_ws/src/mecanum_nav_bringup/config/bridge/sim_eval_cmd_vel.runtime.yaml` | `6577ad07506be16666fc11095cfab07e75b6fb2b3fb72d697e634c97417b373f` | 147 |
| `ros2_ws/src/mecanum_nav_bringup/config/bridge/sim_eval_lidar_scan_bridge.runtime.yaml` | `fbfcf29e197ea94622b5e86858ffef6b5fee05a5d9bcf6ab58bf110d9c5561c2` | 214 |
| `ros2_ws/src/mecanum_nav_bringup/config/lifecycle/sim_eval_nav2_baseline.runtime.yaml` | `cf1c942f76f4e432c1716e82f759a1d17012866714e8a958d59585585694102f` | 352 |
| `ros2_ws/src/mecanum_nav_bringup/config/localization/amcl_omni.yaml` | `c6e58320aa1b35f4c74ca7442bf00357266ad51428522ca93d4565c1d6617e60` | 891 |
| `ros2_ws/src/mecanum_nav_bringup/config/navigation/sim_eval_nav2_baseline.runtime.yaml` | `ee0ea126c3bf08386b9b4d408ef0b9775398f1d821c1cc5a1f6f3f08efb81167` | 2971 |
| `ros2_ws/src/mecanum_nav_bringup/config/state_estimation/ekf_sim.yaml` | `6aaacd93181eb3cbfc1bd25067ebdc441bad40998ccb486fea1c51f3ffe8a755` | 776 |
| `ros2_ws/src/mecanum_nav_bringup/launch/sim_eval_nav2_baseline_system.launch.py` | `283010f115b1608f8a73613f45e4da674f54ec93c2b91584d86b9514030fb013` | 8870 |
| `ros2_ws/src/mecanum_nav_bringup/launch/sim_eval_tf_ekf_state_estimation.launch.py` | `1bf0098b9534257cb57b7f69e47179f2a61b0340745a8f68be7c24254d32a061` | 2753 |
| `ros2_ws/src/mecanum_nav_bringup/package.xml` | `0e82b208575f11a46d12f1053f6721092f5e4f69af0da77abda28cd40ccc33fd` | 1737 |
| `ros2_ws/src/mecanum_nav_bringup/test/test_sim_eval_nav2_baseline_system_launch.py` | `d64c265a07b5c3e4f525177004b894ed82a6765f0e2536154658f6b2fb524c52` | 10672 |
| `ros2_ws/src/mecanum_nav_bringup/test/test_sim_eval_tf_ekf_runtime_contract.py` | `12e6598c0021f1cc5063315d8feb7e82f96e83bf046d334bede9cc2a124626ff` | 43898 |
| `ros2_ws/src/mecanum_nav_rl/config/safety/sim_eval_nav2_baseline_safety.yaml` | `d9120562549f3a14b6b7673afe247696c0233d2f9d1be1399eac37ec6ff423bd` | 943 |
| `ros2_ws/src/mecanum_nav_rl/config/v3/resolved/sim_eval_nav2_baseline.resolved.json` | `3841d1a1c2e9e1a4883431f05d7d5ff13e0b687569e5734f0b4f91aa69294b84` | 5326 |
| `ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/observations/step07_gate_b_observer_node.py` | `32f1c754bfe65268317d2a2cebe34982285a0273a071fb9fb2f25649df4dc4f4` | 21067 |
| `ros2_ws/src/mecanum_nav_rl/test/test_step07_gate_b_observer_node.py` | `4f0f661f507846dd0623877a5a6b93a56e9029f93d1f7f988c745896ab06ae70` | 4580 |
| `ros2_ws/src/step07_nav2_baseline_runtime_observer/package.xml` | `ec322d9068526ba43b878e7ebb249d0587fb9189f49fcb8999e38eea2b68791b` | 733 |
| `ros2_ws/src/step07_nav2_baseline_runtime_observer/src/step07_nav2_baseline_runtime_observer.cpp` | `d713d8c67145bfdaf55d4f55c0ab5fcb4b2114013a1aa9d69cff3c27fd925519` | 29652 |

Verification: focused tests 89; Step-7 tools 205; bringup 244; RL 707; six-package external build PASS; observer 13 C++ tests and ROSIDL 8 tests PASS; installed artifact equality 15/15; 34/34 pins and exact scope/history PASS. No runtime was executed in this corrective. Run005 guard remains pending, capacity 1, acquisition 0, `runtime_authorization=NOT_GRANTED`; Gate B `NOT_STARTED`; `RUNTIME_APPROVED=NOT_APPROVED`.

Current hashes: decision `8e6437172e324cf0407a612209ab2759ca02634b95a003f4b685ede2bd58e90a`; guard `1c8468d3df731719522e64d8b21370ce33543ff07f9c1835aa920bd5c8f0b520`; evidence `265807e5cc1da274dd0f08ffcdede4791838d6e334904c1dbfbf2b6d3341fe51`; manifest `424104bafd0e164720499e6e5204a7de4d7916c87ac1d596db92ae6093c0bc87`.

### STEP07 Run005 attempt_002 output-parent preflight corrective — current source pins

The current direct corrective scope is exactly 11 paths from `c408ccd2a2f7b11787f725a24e818ffa038e3d36`. It removes the non-authoritative network-interface probe and requires a create/write/fsync/close/unlink output-parent probe before the private runtime clone, build, host preflight, evidence, guard acquisition, or process launch. Invocation_003 remains an immutable pre-acquire failure with no evidence bundle and no guard consumption; its initial `PermissionError: [Errno 1] Operation not permitted` and subsequent evidence-write `OSError: [Errno 30] Read-only file system` are recorded without implying runtime execution.

Run005 keeps exactly 34 unique runtime source pins. The following existing entries were refreshed from current candidate bytes; the remaining 30 entries are unchanged.

| Existing pinned source/test path | SHA-256 | Size (bytes) |
|---|---|---:|
| `artifacts/simulation/step07_nav2_baseline_campaign/tools/run_step07_nav2_baseline_run005.py` | `6a2943049203a6a6768c040715a55cbae501af0ed8d2f71af18edcd8e5f6d8cc` | 60768 |
| `artifacts/simulation/step07_nav2_baseline_campaign/tools/test_run_step07_nav2_baseline_run005.py` | `b30211ebce9b635c28c3a22c5eede940e370b8d926d79b9ba98ed37b806c6086` | 48457 |
| `artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_run005_runtime_guard.py` | `3b0a8b7ca8f9f1c11d8eeff1b067b9c25356a26d048bc9084380a121d6d03281` | 10630 |
| `ros2_ws/src/mecanum_nav_bringup/test/test_sim_eval_tf_ekf_runtime_contract.py` | `3a4dfb51fa5f0d160fca04adf8a4d1819dde5d613598ea5b7f899b5b09b8eb47` | 45389 |

Guard SHA-256 `db5cfd94b9623c1497ba103444e931064c04cf76e7ebe455ba8a7f29a313752e`; evidence SHA-256 `39b220725d48f19f7b140da97868bc9c31ba5321c21dfa5c1be14572ca050813`; manifest SHA-256 `66bb591039054556824e0c032d552247d5319e8b5ec240bddea7960bf99bd17d`; Decision SHA-256 `3d42d895ee8bc3a583e3b2f2dd08caa751afa0a12b23914ce2e1af5ccc7ba735`. The guard remains pending/capacity-one/acquisition-zero/NOT_GRANTED; no runtime or Gate-B claim is made.


### STEP07 Run005 attempt_002 exact GZ_PARTITION process identity corrective

The current exact direct scope is 11 paths from `da82b2e5d65eedd80f42000283dccc42a5f6ed66`. Stale partition detection now accepts only an exact NUL-delimited `GZ_PARTITION=<partition>` entry from a non-ancestry process environment; command-line matching is removed. Invocation_004 is preserved as a checksum-verified pre-acquire failure, with no guard consumption or lock and no campaign process invocation.

Run005 keeps 34 unique current source pins. These three existing entries were refreshed; no pin was added:

| Existing source/test path | SHA-256 | Size (bytes) |
|---|---|---:|
| `artifacts/simulation/step07_nav2_baseline_campaign/tools/run_step07_nav2_baseline_run005.py` | `5c463f20dc2daa63b48a25ba205e4248967bc6fe1a80001dc2328b736b84c5cf` | 61495 |
| `artifacts/simulation/step07_nav2_baseline_campaign/tools/test_run_step07_nav2_baseline_run005.py` | `5dffb67426258b7b88d77208d460358d00b7f64cb6ea01dd0d0bddfc05dc95ff` | 54257 |
| `ros2_ws/src/mecanum_nav_bringup/test/test_sim_eval_tf_ekf_runtime_contract.py` | `719116c137289e79306869c951a7ac9fdd5c75749fd082ca7c97d7958673097d` | 47458 |

Current record hashes: decision `b1aa4f60806bec6fdc5ceab9b72b9da44f38f872a703a1083bfe97dee8fdf5f5`, guard `01c77c369129f963791d176091e803a5596f9ebd91e1de4033c5bb3bc684bdbc`, evidence `98cb7844f4af480f2e14dd4def6806c484b15175dc35a3591471cef066347e34`, manifest `d53650a6273f9ccf4ab0696bd3b4d6f9c8c91f60f6cf518a0b372550c9b50952`. Guard state remains pending/capacity-one/acquisition-zero/NOT_GRANTED. No runtime or Gate-B claim is made.


## Run005 attempt_002 exact GZ_PARTITION process-identity corrective — final pin reconciliation

The exact current corrective scope is 11 paths from `da82b2e5d65eedd80f42000283dccc42a5f6ed66`; source-pin count remains 34 unique entries and is independent of changed-path count. The existing 34 pins were checked against current bytes; two entries required refresh after test stabilization. Historical attempt_001 through invocation_004 records remain immutable. Invocation_004 was a checksum-verified pre-acquire failure with the guard pending and unconsumed.

| Current existing pin | SHA-256 | Size (bytes) |
|---|---|---:|
| `artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_run005_runtime_guard.py` | `b5532869ebbf6f3cbdf7c657c89dd291d005671ae1d41c76e25224b2b9bc370d` | 12201 |
| `ros2_ws/src/mecanum_nav_bringup/test/test_sim_eval_tf_ekf_runtime_contract.py` | `e88f0fc6be4a8c9bd22e7f855fc160c656b530870529d753ae788f8b55206982` | 47558 |

Current decision SHA-256 `ab30bbbf37f4961e70c4369e3c370590438d12f16031cb9d0fc5850653694311`; guard `e71580a8c3ffb0feb7740f8aa194ad2206ce18f9e60cfc9fb4b5ad1c600da36a`; evidence `fe28092b4589cf85b270fdc6e8696197687626aa32ca33f85e3360f36db462e6`; manifest `a012aae26afbc5af4c025f7d70d3ef6a562b34c4659c361cccdf86622f9c5f93`. Verification is source/offline only; Gate B remains `NOT_STARTED`, `RUNTIME_APPROVED=NOT_APPROVED`.

### STEP-7 Run005 attempt_002 host transport and terminal evidence corrective — current reconciliation

Exact base `99d5c29c1c302260a8971e19e46f93d778a52f86`; exact 11-path current direct scope is checked as a set. Run005 retains 34 unique current-worktree runtime pins; changed-path count and source-pin count are independent. Host transport preflight validates `socket.if_nameindex()`, a UDP loopback bind/close, and `gz topic -l` with the exact campaign partition before guard acquisition. Failures are pre-acquire and produce evidence with the guard pending. SIGTERM is routed through teardown and finalization; SIGKILL cannot be caught or guaranteed to produce a final record.

Invocation_005 is immutable. Persisted `run_record.json` SHA-256 `5ffa675f8ec846d09a6c7e70ebaa3689eb7566f03398db565c4bd53874b360da` exists and reports `BOOTSTRAP_READINESS_TIMEOUT`, bootstrap 1, composite/observers 0, consumed runtime guard, and teardown completed but not clean. Its bootstrap log contains Gazebo `getifaddrs` and UDP socket permission errors. The record's existence means the claim that external termination prevented the final record is not supported by the persisted artifact. No historical evidence was changed.

Guard/evidence/manifest current hashes: guard `1b11297c2a8ff391c4bcf556ca6c11a935b85b8d0f489441d8d467faf367cf5c`, evidence `a0dee26a56d10a896939588f4f0b3b1b287fbf293edf313cd69c9e3ba276beee`, manifest `84cd34016d1c2784df0ad4a911507dae02b3f067bb9fe9758e5d4db45b6abc7f`.

| Current Run005 source pin | SHA-256 | Size (bytes) |
|---|---|---:|
| `artifacts/maps/warehouse_map2/map.yaml` | `5073762401784f67e856b5018656ad869ecc26e723f85e5979054eadc7876a68` | 125 |
| `artifacts/simulation/step07_nav2_baseline_campaign/tools/prepare_step07_runtime_python_environment.py` | `01f09ddf82d61f239bbee9e002868f9c3d027526b02ddfe1e0c0e0b31fb7b79e` | 5330 |
| `artifacts/simulation/step07_nav2_baseline_campaign/tools/run_step07_nav2_baseline_run005.py` | `8aae15ff5b1b752efa80fd3839a7f5e815adc172e249b7bbd5f4b436112c75d8` | 85522 |
| `artifacts/simulation/step07_nav2_baseline_campaign/tools/step07_gate_b_evidence_validator.py` | `210694c3b9c270e20d4650ca7bb8362ee703c62a0a22bfe6e4f21a8cab970190` | 23255 |
| `artifacts/simulation/step07_nav2_baseline_campaign/tools/step07_run005_runtime_guard.py` | `325889d73bfcb4eb5b33a8373a6fc22b73fa5571893adb7626e6d8caed963dce` | 9843 |
| `artifacts/simulation/step07_nav2_baseline_campaign/tools/step07_runtime_python_requirements.txt` | `6560f131b6d82cef455b70cd8952a814dd3811dec73108d69b3d9206c95c9573` | 17 |
| `artifacts/simulation/step07_nav2_baseline_campaign/tools/test_run_step07_nav2_baseline_run005.py` | `bcbe8793d51c258e5a8bbc8aa37ba1fa7d2ce2b27753a5bf39f32d47121d5fa3` | 85822 |
| `artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_gate_b_evidence_validator.py` | `f5b2f0a96aac0bbc429a5ab41a19f558006d05f19c54b9a5d5ec8c7f429ec795` | 17061 |
| `artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_run003_runtime_guard.py` | `d36d809d9174ec17d9e3df9771176c42d4c351aee890ae13668828194763af82` | 7036 |
| `artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_run004_runtime_guard.py` | `0f938eedd91eecae4b91a1fbf3b3b1749c0f498a4f1f1eee889ea378ef0d853f` | 7785 |
| `artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_run005_runtime_guard.py` | `30813145c8921b0a3e4995a9072e5fecb7343230bd51c2c81acc61f23e6750a9` | 14390 |
| `artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_runtime_guard.py` | `120f24891f6c39eb5af814393c879e479f4736cadd14a2bb35821a6a546ce28b` | 12752 |
| `ros2_ws/src/ROBOT_URDF_final_description/launch/sim_eval_nav2_baseline_bootstrap.launch.py` | `4067d6efe3782d7687e237603803d8a1b3ebc3fda4927f8233a50951ae856456` | 7054 |
| `ros2_ws/src/ROBOT_URDF_final_description/launch/tugbot_depot.sdf` | `a4b6253340baa866d89640d62a94d04fbea51425e9af1deca591422a0a36d91d` | 12364 |
| `ros2_ws/src/mecanum_base_bridge/config/bridge/sim_eval_wheel_imu_ingress.runtime.yaml` | `2dafb19da5daeeb91c451ae57055caa389a0353900525fb9a5861e1c670c6547` | 506 |
| `ros2_ws/src/mecanum_base_bridge/launch/sim_eval_wheel_imu_ingress.launch.py` | `1612ce773eb0b7cb05e4d081eee441418dea32314c3685adcdcd96dd569069b8` | 1795 |
| `ros2_ws/src/mecanum_nav_bringup/config/bridge/sim_eval_clock.runtime.yaml` | `89220ef78125348776575b1a14fa1727c9cb098d9c46d84a74e27e5e8715f0b1` | 143 |
| `ros2_ws/src/mecanum_nav_bringup/config/bridge/sim_eval_cmd_vel.runtime.yaml` | `6577ad07506be16666fc11095cfab07e75b6fb2b3fb72d697e634c97417b373f` | 147 |
| `ros2_ws/src/mecanum_nav_bringup/config/bridge/sim_eval_lidar_scan_bridge.runtime.yaml` | `fbfcf29e197ea94622b5e86858ffef6b5fee05a5d9bcf6ab58bf110d9c5561c2` | 214 |
| `ros2_ws/src/mecanum_nav_bringup/config/lifecycle/sim_eval_nav2_baseline.runtime.yaml` | `cf1c942f76f4e432c1716e82f759a1d17012866714e8a958d59585585694102f` | 352 |
| `ros2_ws/src/mecanum_nav_bringup/config/localization/amcl_omni.yaml` | `c6e58320aa1b35f4c74ca7442bf00357266ad51428522ca93d4565c1d6617e60` | 891 |
| `ros2_ws/src/mecanum_nav_bringup/config/navigation/sim_eval_nav2_baseline.runtime.yaml` | `ee0ea126c3bf08386b9b4d408ef0b9775398f1d821c1cc5a1f6f3f08efb81167` | 2971 |
| `ros2_ws/src/mecanum_nav_bringup/config/state_estimation/ekf_sim.yaml` | `6aaacd93181eb3cbfc1bd25067ebdc441bad40998ccb486fea1c51f3ffe8a755` | 776 |
| `ros2_ws/src/mecanum_nav_bringup/launch/sim_eval_nav2_baseline_system.launch.py` | `283010f115b1608f8a73613f45e4da674f54ec93c2b91584d86b9514030fb013` | 8870 |
| `ros2_ws/src/mecanum_nav_bringup/launch/sim_eval_tf_ekf_state_estimation.launch.py` | `1bf0098b9534257cb57b7f69e47179f2a61b0340745a8f68be7c24254d32a061` | 2753 |
| `ros2_ws/src/mecanum_nav_bringup/package.xml` | `0e82b208575f11a46d12f1053f6721092f5e4f69af0da77abda28cd40ccc33fd` | 1737 |
| `ros2_ws/src/mecanum_nav_bringup/test/test_sim_eval_nav2_baseline_system_launch.py` | `d64c265a07b5c3e4f525177004b894ed82a6765f0e2536154658f6b2fb524c52` | 10672 |
| `ros2_ws/src/mecanum_nav_bringup/test/test_sim_eval_tf_ekf_runtime_contract.py` | `b8ccb7d0ca3018ab2c620bf4f7a75d0ee3727007c65f83255f0e99886a64f92e` | 51569 |
| `ros2_ws/src/mecanum_nav_rl/config/safety/sim_eval_nav2_baseline_safety.yaml` | `d9120562549f3a14b6b7673afe247696c0233d2f9d1be1399eac37ec6ff423bd` | 943 |
| `ros2_ws/src/mecanum_nav_rl/config/v3/resolved/sim_eval_nav2_baseline.resolved.json` | `3841d1a1c2e9e1a4883431f05d7d5ff13e0b687569e5734f0b4f91aa69294b84` | 5326 |
| `ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/observations/step07_gate_b_observer_node.py` | `32f1c754bfe65268317d2a2cebe34982285a0273a071fb9fb2f25649df4dc4f4` | 21067 |
| `ros2_ws/src/mecanum_nav_rl/test/test_step07_gate_b_observer_node.py` | `4f0f661f507846dd0623877a5a6b93a56e9029f93d1f7f988c745896ab06ae70` | 4580 |
| `ros2_ws/src/step07_nav2_baseline_runtime_observer/package.xml` | `ec322d9068526ba43b878e7ebb249d0587fb9189f49fcb8999e38eea2b68791b` | 733 |
| `ros2_ws/src/step07_nav2_baseline_runtime_observer/src/step07_nav2_baseline_runtime_observer.cpp` | `d713d8c67145bfdaf55d4f55c0ab5fcb4b2114013a1aa9d69cff3c27fd925519` | 29652 |


### STEP-7 Run005 attempt_002 terminal verdict and ROS discovery preflight corrective — current reconciliation

Exact base `87ee34b1a945ecc12b525fe9f4711a368c0bdbc3`; exact current direct scope: 11 paths. The runner checks ROS CLI support and performs bounded `ros2 topic list --no-daemon --spin-time 3` after ROS and overlay sourcing, before guard acquisition. An empty graph is permitted for this capability probe; permission/socket errors, timeout, nonzero exit, or network-error output fail closed with pre-acquire evidence. The exact-partition `gz topic -l` check remains. Terminal PASS requires all acceptance values true, no failure literals, and completed, ordered, clean, verified teardown. SIGTERM is a failure routed through best-effort composite-before-bootstrap teardown and record finalization. Unverified teardown is never clean. SIGKILL, power loss, or an unwritable filesystem cannot guarantee a durable record.

Invocation_005 remains immutable. Its persisted run record exists and reports `RuntimeError:BOOTSTRAP_READINESS_TIMEOUT` after guard acquisition; bootstrap ran once, composite and observers did not, and teardown completed but was not clean/order-correct. The bootstrap log records Gazebo interface/socket permission errors. The saved record does not support a claim that external termination prevented finalization.

Phase A offline checks passed: focused Run005 runner/guard 116; focused scope 2; Step-7 tools 257; bringup 244; nav_rl 707; six-package external build; observer 13 and ROSIDL 25 cases; installed-source equality 15/15; source pins 34/34; parsing, history, scope and diff checks. No runtime was run. Guard remains pending/capacity 1/acquisition 0/NOT_GRANTED; Gate B `NOT_STARTED`; `RUNTIME_APPROVED=NOT_APPROVED`. Evidence ceiling: `SOURCE_OFFLINE_TEST_CANDIDATE_ONLY_NO_RUNTIME_EVIDENCE`.

Governance artifact hashes: decision `17a72941d1e32a42692615f81abb69c9613a5be0d5de18a406f9d55312943215`, guard `2dc8a9bf9d4fab3593bd9c85a563cc3ad6122565cbf1bb25215fddd833b72470`, evidence `14c9d7ec0abc4d5062ad11f545c401d233b08f523b7dca46ef5b050c478a5d0b`, manifest `f97ade36ac0b0a5be1c614d742abab340c7ecb80d4705072f6679600eb1ffd93`.

### STEP-7 Run005 attempt_002 SIGTERM/guard handoff corrective — current reconciliation

This L1 correction is based on `bee34dd2d689fe585ae12000058b2f2903196659` and keeps Run005 attempt_002, the 34-pin current source inventory, and the existing pending capacity-one guard. The exact current corrective path set is independently checked as 11 paths; the source-pin inventory remains exactly 34 unique paths.

The SIGTERM handler is installed before pre-acquire checks. A pre-acquisition SIGTERM writes pre-acquire failure evidence without claiming guard consumption. SIGTERM is blocked only during guard mutation/handoff; the acquired state is marked before unblocking so a pending signal is classified as consumed FAIL. During teardown/finalization the handler records interruption without raising; terminal verdict is FAIL for any pre-teardown failure, SIGTERM, false acceptance, or incomplete/unclean/unverified teardown. A SIGTERM delivered before handler restoration causes record/manifest/checksum resynchronization to FAIL where writable. The previous handler is restored once. SIGKILL, power loss, or an unwritable evidence filesystem cannot guarantee durable evidence.

Phase A passed: focused runner/guard 122, focused scope-chain 2, Step-7 tools 263, bringup 244, nav_rl 707; six-package external build; observer 13 and ROSIDL 8 tests; installed-source equality 15/15; py_compile; 34/34 pins; canonical JSON/YAML/XML, history, exact scope and diff checks. No runner/runtime was executed. Run005 remains pending/unconsumed, Gate B `NOT_STARTED`, `RUNTIME_APPROVED=NOT_APPROVED`. Evidence ceiling: `SOURCE_OFFLINE_TEST_CANDIDATE_ONLY_NO_RUNTIME_EVIDENCE`.

Current refreshes (SHA-256, bytes):
| `artifacts/simulation/step07_nav2_baseline_campaign/tools/run_step07_nav2_baseline_run005.py` | `4f9e56c939a5dfa362672ae63d61395c6b263ccd049ff23098a0bae693f8a117` | 90789 |
| `artifacts/simulation/step07_nav2_baseline_campaign/tools/test_run_step07_nav2_baseline_run005.py` | `add635ab907ea8b0b927c2dd2eea4d9ab05527d1630db6b1e6de24132fd98ce3` | 104828 |
| `artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_run005_runtime_guard.py` | `d1432e3453bbf8145537bc41265fcfc7bce562a10ebfe6568b21c1ad2cd448be` | 17078 |
| `ros2_ws/src/mecanum_nav_bringup/test/test_sim_eval_tf_ekf_runtime_contract.py` | `376bc411bb5983be062279e8c7f5696f1af448d4fea5d48b31048ec69eb5727a` | 52485 |

Current guard SHA-256 `c7c2caaff6d1d81fbc3300cedb226de2daec3f6f35f0db13a6d2a91a57fe7b89`, evidence SHA-256 `1ab3eb1247841ab0eb707c0b18d315a84aa36d6d9f3b49eb59fbc81192feb79d`, and manifest SHA-256 `4e9deab757bdadbb28399b94f65e068aeb730f7dccee863bc41675dc9e4148a3`.


### Run005 attempt_002 — reconciliation guard/process ownership hiện hành

Corrective L1 trên base `53b7790c23c7d4969612259a8ee06be0353babd2`, vẫn Run005 attempt_002. Direct scope là exact 13 path; runtime source-pin inventory giữ 34 path duy nhất. Guard mutation exception chỉ được xóa lock khi strict runtime readback xác nhận đúng seed PENDING chưa acquire. Sau replacement hoặc unmask failure, strict readback CONSUMED đúng commit/authorization/count=1 đi vào post-acquire FAIL và terminal evidence. Readback không xác định giữ lock, ghi UNVERIFIED và không fallback sang source checkout.

Cả bốn component dùng cùng owned-spawn helper: SIGTERM được latch trong registration; child handle được ghi ledger trước PGID/snapshot. Teardown lấy ledger kể cả khi caller chưa nhận assignment. Chỉ signal process group đã xác minh; nếu không xác minh được, thử dừng chính child đã biết và ghi FAIL/unverified. Thứ tự composite trước bootstrap, acceptance, partition, QoS và capacity-one không đổi.

Phase A PASS: focused runner 142, guard 15, historical guard 19; full Step-7 tools 299, bringup 244, RL 707; build sáu package ngoài worktree; observer 13 và ROSIDL 8; py_compile sáu file; installed/source equality 15/15; source pins 34/34 sau reconciliation, JSON/YAML/XML và history/scope/diff checks. Không official runtime invocation trong corrective này.

Giữ lịch sử invocation_001–005, consumed guards/locks/evidence/runtime worktrees bất biến. Source seed còn PENDING, capacity 1, acquisition 0, runtime_authorization=NOT_GRANTED, không lock. Gate B NOT_STARTED; RUNTIME_APPROVED=NOT_APPROVED. Giới hạn: SIGKILL, mất điện hoặc filesystem không ghi được vẫn có thể ngăn terminal evidence. Evidence ceiling: SOURCE_OFFLINE_TEST_ONLY_PENDING_INDEPENDENT_AUDIT. Bước tiếp theo: independent audit exact corrective commit; runtime cần authorization riêng.

| Source pin đã refresh | SHA-256 | Byte size |
|---|---|---:|
| `artifacts/simulation/step07_nav2_baseline_campaign/tools/run_step07_nav2_baseline_run005.py` | `4f9e56c939a5dfa362672ae63d61395c6b263ccd049ff23098a0bae693f8a117` | 90789 |
| `artifacts/simulation/step07_nav2_baseline_campaign/tools/step07_run005_runtime_guard.py` | `325889d73bfcb4eb5b33a8373a6fc22b73fa5571893adb7626e6d8caed963dce` | 9843 |
| `artifacts/simulation/step07_nav2_baseline_campaign/tools/test_run_step07_nav2_baseline_run005.py` | `add635ab907ea8b0b927c2dd2eea4d9ab05527d1630db6b1e6de24132fd98ce3` | 104828 |
| `artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_run005_runtime_guard.py` | `d1432e3453bbf8145537bc41265fcfc7bce562a10ebfe6568b21c1ad2cd448be` | 17078 |
| `artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_runtime_guard.py` | `120f24891f6c39eb5af814393c879e479f4736cadd14a2bb35821a6a546ce28b` | 12752 |
| `ros2_ws/src/mecanum_nav_bringup/test/test_sim_eval_tf_ekf_runtime_contract.py` | `376bc411bb5983be062279e8c7f5696f1af448d4fea5d48b31048ec69eb5727a` | 52485 |

Guard SHA-256 `47ba096c850081ff073cb54c66381a128a3ea2eca812ed650ddae939045548fa`; evidence `8e87e4fd9b5cf7fa08b3529a3448cd36418ad077432d27ed855edee6b5f9082e`; manifest `f0403ddb4d140937635972a8156c6eadcf677bd454d1cd0917fad8c3f539b759`.


### Run005 attempt_002 — corrective L2 composite/Gate-B

Base `bb5fc04fe8e309c52e468f766893ef60625e6821`; exact direct scope 23 path, union pins 37/37. Owner phê duyệt L2 cho lifecycle orchestration, clock/binding/TF, observer lifetime và scan validity; filename decision L1 giữ nguyên. SOURCE_OFFLINE_TEST_ONLY_PENDING_INDEPENDENT_AUDIT. Focused 46, tools 301, bringup 248, RL 715 PASS; sáu-package external build, observer 13, ROSIDL 8, installed/source 19/19 PASS. Guard seed PENDING/capacity 1/acquisition 0/NOT_GRANTED; Gate B NOT_STARTED; RUNTIME_APPROVED NOT_APPROVED. Không official runner/runtime/integration; lịch sử và guard/ownership tại base bất biến. Next action: independent audit exact corrective commit; runtime cần authorization riêng.

Decision: `docs/governance/decisions/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_L1_DECISION.md`; SHA-256 `e245967f9c5b324c4d67dae70ca046bc3b8d80252197411c3021ebca3856ed36`.

- `artifacts/simulation/step07_nav2_baseline_campaign/approval_guards/STEP07_NAV2_BASELINE_RUN_005.json`: `2442328059cfea2143ea3660ad578bf8a69a535493459f7aec510a725c12e6aa`.
- `docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_L1_EVIDENCE.json`: `1d206e32f5604ff425d30b3dbd8b2a377593a602d9e163e18a47065ce8995afe`.
- `docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_GUARD_MANIFEST.json`: `3c7ab3855df8fac785c21de85d1e3e522fffbb87aaf090b63a64fb81737f0b36`.


### Run005 attempt_002 — evidence-validator identity/verdict corrective (2026-10-21)

Base `c8e34ead42c9c3fa6d79bf73dc221a9cc599d42a`; direct corrective scope exact 10 paths. This is an offline validator-contract correction only. The validator now binds to Run005 identity/outcomes and rejects pass claims with missing teardown verification or non-empty failure literals. Current Run005 inventory remains 37 unique source pins; three existing entries refreshed, no membership change.

Refreshed entries:
- `artifacts/simulation/step07_nav2_baseline_campaign/tools/step07_gate_b_evidence_validator.py`: SHA-256 `42e24bfaa56f11eb93afdf1e51887342b00e199ab276927ac027eff68ab2fa43`, 23649 bytes.
- `artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_gate_b_evidence_validator.py`: SHA-256 `10908be06fe118c7d0eafd49b1a0f16adec0f298e1c921f5bbe325b5c33e3308`, 23016 bytes.
- `ros2_ws/src/mecanum_nav_bringup/test/test_sim_eval_tf_ekf_runtime_contract.py`: SHA-256 `9342e542ba6d500a47680730869a1d8f6367f0f39d362192b9ad2a10374c048c`, 59703 bytes.

Offline result: 37/37 source pins, full Step-7 tools 306, bringup 249, RL 715, external six-package build PASS, observer 13 and ROSIDL 8 PASS, installed runtime-artifact equality 15/15 PASS. No runtime invocation.


### Run005 attempt_002 — GZ_IP transport binding / graceful teardown corrective L2

Base/sole parent `f72ac2112e0d1545a72b6a9a12764664d508aaa8`; exact direct scope 13 paths. Source pins remain 37 unique entries, membership unchanged; existing hashes/sizes are refreshed from current bytes. Gazebo Transport selects and validates a local IPv4 assigned to the selected IPv4 default-route interface, passes it as `GZ_IP` with the exact campaign `GZ_PARTITION`, and performs one bounded transport publish probe before guard acquisition. Runtime PASS requires teardown completed, clean, ordered, verified and graceful with no escalation history.

Invocation_007 is immutable historical runtime failure: bootstrap READY; composite readiness timeout after multicast `Network is unreachable`; final snapshot was clean but `lifecycle_manager` required escalation, so teardown was not graceful. It is not a PASS. No historical runtime artifact was modified and no runtime was run for this corrective.

### Run005 attempt_002 — pure-Python default-route resolver corrective

Active base `e921b04e9ef8dc933a76966cf101613fab0f8062`; exact current direct diff: 11 paths. The current runtime source-pin inventory retains the same 37 unique entries. Active route resolution no longer depends on executable `ip`: it parses `/proc/net/route`, checks UP/physical interface facts in sysfs, selects a UDP-connect source, and verifies interface ownership via `SIOCGIFADDR`. It retains exact campaign GZ_IP/GZ_PARTITION inheritance and the pre-acquire bounded publish probe.

Invocation_009 remains an immutable no-guard-consumed preflight failure: `GZ_TRANSPORT_HOST_CAPABILITY_UNAVAILABLE:DEFAULT_ROUTE_EXIT_NONZERO`. The recorded result does not identify whether the external command failed due to syntax, permissions, or version. No historical runtime evidence was changed.

Current source pin refreshes (SHA-256, byte size):
| `artifacts/simulation/step07_nav2_baseline_campaign/tools/run_step07_nav2_baseline_run005.py` | `5eb0a1c12b2673a42d6db0f286d17e2fd3320a92fb7a25cd76f4d02f529f8c30` | 101060 |
| `artifacts/simulation/step07_nav2_baseline_campaign/tools/test_run_step07_nav2_baseline_run005.py` | `bb1e73a47de3b726346a75512fb392a5718144b338ba07c1d4db7ef3f65f34eb` | 116357 |
| `artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_run005_runtime_guard.py` | `723941c02064eead9839e6aba296be6bcf304ca1afc1d843e7d9b101d7ae0981` | 18086 |
| `ros2_ws/src/mecanum_nav_bringup/test/test_sim_eval_tf_ekf_runtime_contract.py` | `7b9fbd5af7d79caeadaea293c30db71a386d98fe27292574fbc0276372d3d676` | 65816 |

Current guard/evidence/manifest SHA-256: `6539bda341ace90f2c595572063b8c95ba41ea92017c6c803847722adf5097e5` / `e563268b209f8c96adbd25aa426cf2f15004a1d9ff799871320aaab5f5bd7789` / `5c147a1d58feaa1d3dd5571a6dbb4e7d377019284c4fc805b1587c645f9588e6`.
