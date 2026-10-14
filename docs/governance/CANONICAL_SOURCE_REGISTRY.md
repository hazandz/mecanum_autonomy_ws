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

## WP04-WP05 runtime measurement plan and evidence schema — review snapshot at `cc0018560b20a52fa6d3c9cf26abbe0ef4c6227a`

At this exact source-base snapshot, `docs/governance/decisions/WP-04_WP-05_RUNTIME_MEASUREMENT_PLAN_AND_EVIDENCE_SCHEMA.md` and its companion JSON Schema are review-candidate governance records, not active runtime-binding technical authority. They define only measurement planning, ownership, fail-closed evidence admission, exploratory-versus-acceptance distinction, and packet shape. The schema is not a populated packet and provides no measurement result, runtime evidence, acceptance conclusion, map approval, Gate B pass, or authorization.

After independent audit PASS for the exact candidate, separate exact-commit User authorization, fast-forward, and remote-ref verification, these records may be described only as `INTEGRATED_L1_RUNTIME_MEASUREMENT_GOVERNANCE_PLAN_ONLY`. Review push or Git ancestry alone does not activate them. No passive measurement harness is authorized; it requires a separate L1 authorization. No numerical threshold, source/package/version lock instance, profile, `config_hash`, measurement value, or runtime authorization is introduced. Required source/package pins and measurements remain pending. Status remains WP-04 `BLOCKED_BY_CONTRACT`, Gate B `NOT_STARTED`, WP-05 `OPEN`, map draft/not approved, `WORLD_FRAME: NOT_DECLARED`, `RUNTIME_COMPATIBILITY: NOT_VALIDATED`, and `RUNTIME_APPROVED: NOT_APPROVED`.

Dependency fingerprints recorded by this candidate are Architecture SHA-256 `432eeac363a595cfcf7e81c4b66054fb674dba140a2ef3cffecd617ab8136204`; OIC source SHA-256 `d44d33843c32d1f0d5c747522f3add09bfde21fcb0884e21da93a52476cb4dfc`; OIC semantic-manifest SHA-256 `175a1af789b6641cfe455daeee8fedac80aaf80ad8c00792ba0a287c41acc0bb`; WP-04 runtime-binding manifest SHA-256 `e800f7169304624d81334c26a638c27c9cbaa11a6df0ba5531b1718ee914f76f`; WP-05 Navigation V1 runtime-binding ACR SHA-256 `3e74cdcb6136f60a6ad2822a853f2ae9926cf971059f3c2470c874802d6fae0d`; WP-05 runtime-binding manifest SHA-256 `33855c9c95f9c0594ddd8805514658e4f5cb8255a219938a7913438470edbf31`; and `warehouse_map2` map-content hash `2bd9ff0a40eaeb61c2359aab4bb213da623ab56746debe591edd4a54c2229f90`. These are dependency fingerprints, not newly selected pins or acceptance evidence.


## WP-05 Navigation V1 dependency-lock schema and static bringup source authorization — review snapshot at `2a537a9cfa9f9c5b0bec1f9c629fec8e2f98a225`

Decision candidate: `docs/governance/decisions/WP-05_NAVIGATION_V1_DEPENDENCY_LOCK_AND_STATIC_BRINGUP_SOURCE_AUTHORIZATION.md`; schema: `docs/governance/evidence/WP-05_NAVIGATION_V1_DEPENDENCY_LOCK_SCHEMA.json`. This five-path candidate is based on exact integration snapshot `2a537a9cfa9f9c5b0bec1f9c629fec8e2f98a225` and is pending independent audit, separate exact-commit User authorization, fast-forward, and remote-ref verification. The schema defines direct dependency roots and required future lock fields only; it contains no installed package/version, `.deb` digest, workspace source pin, resolved profile, or runtime evidence.

The proposed future owner of Navigation V1 bringup sources is `mecanum_nav_bringup`; no such package exists at this base. The enumerated source layout is a bounded future allowlist, not present content. `mecanum_nav_rl` retains DRL/pure-core/observation-adapter ownership; `mecanum_base_bridge` retains Pi–STM32 transport/raw wheel-odometry ownership and emits no TF; `ROBOT_URDF_final_description` retains geometry and future robot-description ownership of `base_link → lidar_frame`; map bytes remain only at `artifacts/maps/<map_id>/`.

Current authorization at the base remains `CODE_AUTHORIZATION: GRANTED_BOUNDED_FAIL_CLOSED_INTERNAL_SEAMS_AND_NONEXECUTING_OBSERVATION_INGRESS_ADAPTER_SOURCES_ONLY`; `RUNTIME_APPROVED: NOT_APPROVED`. Only after the exact candidate lifecycle conditions above would it extend to `GRANTED_BOUNDED_FAIL_CLOSED_INTERNAL_SEAMS_NONEXECUTING_OBSERVATION_INGRESS_AND_STATIC_NAVIGATION_V1_BRINGUP_SOURCES_ONLY`. That is static-source/static-test authorization only; it does not permit launch/ROS/Nav2/AMCL/EKF/Gazebo execution, profile resolution, map approval, runtime/HIL/hardware/deployment, or WP status changes.

Outstanding records remain `PENDING_EXTERNAL_PACKAGE_LOCK` or `PENDING_IMPLEMENTATION_SOURCE_PIN`. Any missing required lock/source/measurement/evidence fails closed: no resolved profile, profile `config_hash`, bring-up, map approval, or runtime authorization. WP-05 remains `OPEN`; `warehouse_map2` remains draft, not approved or navigation-ready; `WORLD_FRAME: NOT_DECLARED`, and `RUNTIME_COMPATIBILITY: NOT_VALIDATED`; WP-04 remains `BLOCKED_BY_CONTRACT`, Gate A `PASSED`, Gate B `NOT_STARTED`.
