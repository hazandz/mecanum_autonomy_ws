# Project Execution Plan — Mecanum Nav2 DRL

## Metadata

| Field | Value |
|---|---|
| Plan ID | `PEP-001` |
| Revision | `0.10.13` WP04/WP05 runtime measurement evidence schema F-01 correction review snapshot |
| Architecture status | `ARCHITECTURE_FROZEN`, `IMPLEMENTATION_READY`, `NOT_YET_REAL_ROBOT_VALIDATED` |
| Immutable baseline | `baseline/architecture-frozen-20261002` at `86beff623dba3683f643c851a4a1374c635178b3` |
| Integration line | `integration/implementation` |
| Initial integration commit | `99de9d1839b0d5b1a2da95fc0958b49bac2483a0` |
| Activation rule | The copy on `integration/implementation` is the canonical plan. Work-branch copies are review material. Architecture amendments additionally require focused audit, separate exact-commit User authorization, fast-forward, and remote-ref verification. |
| Runtime status | `RUNTIME_NOT_APPROVED` |

## Authority and scope

- `docs/MECANUM_NAV_DRL_Architecture.docx` remains the highest architecture authority.
- This plan controls implementation sequencing, dependency, Git delivery and progress reporting only.
- This plan cannot change frozen TF, Ground Truth, hybrid Nav2/PPO, holonomic `vy`, safety, artifact or deploy-real contracts.
- Any architecture change requires an approved ACR or explicit user decision; it must not be hidden as a plan update.

## Current static audit snapshot

| Area | Status | Evidence boundary |
|---|---|---|
| V3 config, pure core, observation/action/lifecycle/scenario/oracle | `IMPLEMENTED_CORE` with known P0 semantic gaps | Static source only |
| ROS interfaces | `IMPLEMENTED_CORE` | Message source/static contract only |
| Pi–STM32 bridge | `IMPLEMENTED_CORE` for codec/diagnostic only; `PROPOSED_FOR_RUNTIME` for serial/ROS/odometry | No transport/HIL evidence |
| STM32 firmware | Source and pure modules exist; runtime/HIL remains `PROPOSED_FOR_RUNTIME` | No build/HIL/hardware claim |
| `mecanum_nav_bringup` | Missing | Not implemented |
| SafetySupervisor / FinalTwistPublisher | Contract only | Not implemented runtime |
| Gymnasium, PPO trainer, evaluator | Missing canonical implementation | Not implemented |
| Canonical maps at `artifacts/maps/<map_id>` | Draft artifact present; not approved | `artifacts/maps/warehouse_map2/` is integrated as `approval_status: draft`; no approved/navigation-ready canonical map is selected. This is artifact-presence evidence only, not runtime or navigation evidence |
| Gazebo legacy control profile | Historical/static source only | Not official frozen runtime profile |
| Real robot | `RUNTIME_NOT_APPROVED` | No Gate 3/4, HIL or real-robot evidence |

## Mandatory Git workflow

```text
immutable baseline
→ integration/implementation
→ one work-package branch
→ Codex report + PLAN_UPDATE_PROPOSAL
→ architecture audit
→ explicit user approval
→ separate integration work package
```

- Work package branches begin from an exact integration SHA.
- Codex never pushes directly to main, baseline or probe branches.
- Each push is limited to the branch and scope explicitly authorized by its prompt.
- A failed push is PUSH_FAILED_NO_RETRY.
- A branch/commit/push is only IMPLEMENTED_OFFLINE_ONLY unless higher evidence exists.
## Ordered work packages

| Order | ID | Scope | Depends on | Initial status |
|---|---|---|---|---|
| 00H | WP-00H-EXECUTION-GOVERNANCE | Integration line, plan, ledger, canonical source registry | WP-00G | PENDING_INTEGRATION_APPROVAL |
| 01 | WP-01-REPOSITORY-HYGIENE | Remove generated/cache files from future integration index only; preserve local files/history | 00H and user-approved exact path whitelist | BLOCKED_BY_GOVERNANCE |
| 02 | WP-02-CANONICAL-SOURCE-SELECTION | V3 selection, legacy boundary, source registry enforcement | 00H | BLOCKED_BY_GOVERNANCE |
| 03 | WP-03-OPEN-CONTRACT-CLOSURE | Final-issued receipt, collision/contact, map/scenario/hardware intake decisions | 02 and required user decisions | BLOCKED_BY_CONTRACT |
| 04 | WP-04-POLICY-CORE-P0 | V3 policy-observation core. First constrained deliverable: non-integrated immutable V3 contract primitives — ObservationCutoffV3 core type/validation and ObservationInputContractV3 structural models. Any LiDAR/LocalReference normalization, final-issued receipt integration, V3 assembler/encoder, compiler/profile closure or runtime bridge requires a separate independently approved implementation packet. | WP-03; user-approved V3 scope closure; canonical semantic-bundle record in this PEP for S2 rev.2, Observation Input Contract rev.6, ACR rev.8 and QoS6/ACR8 approval provenance; separate exact implementation packet | BLOCKED_BY_CONTRACT |
| 05 | WP-05-CANONICAL-ARTIFACT-FOUNDATION | Map, scenario and hardware provenance/hash foundation | 03 | BLOCKED_BY_CONTRACT |
| 06 | WP-06-BRINGUP-SAFETY-OFFLINE | mecanum_nav_bringup, command adapters, safety and final publisher offline implementation | 03, 04, 05 | BLOCKED_BY_DEPENDENCY |
| 07 | WP-07-BRIDGE-FIRMWARE-OFFLINE | Serial/telemetry/odometry contract and firmware integration offline | 03, 05 | BLOCKED_BY_DEPENDENCY |
| 08 | WP-08-SIMULATION-PROFILE-MIGRATION | Static ROS–Gazebo command/TF/GT profile migration | 06, 07 where applicable | BLOCKED_BY_DEPENDENCY |
| 09 | WP-09-TASK-REWARD-TERMINATION | Task, reward, termination, collision/contact and randomization contract implementation | 03, 05, 08 | BLOCKED_BY_DEPENDENCY |
| 10 | WP-10-GYM-PPO-EVALUATOR | Gym wrapper, PPO trainer, checkpoint/evaluator and Nav2-vs-hybrid evaluation | 04, 06, 08, 09 | BLOCKED_BY_DEPENDENCY |
| 11 | WP-11-APPROVED-SIM-RUNTIME | Capacity-one simulation runtime packets and approved runs | Offline review + explicit runtime approval | RUNTIME_NOT_APPROVED |
| 12 | WP-12-HIL-GATE-3-4 | Hardware measurements, HIL, staged real tests and Gate 3/4 | 06, 07, 11 + user approval | RUNTIME_NOT_APPROVED |

### WP-04 constrained first deliverable — V3 immutable contract primitives

This is a narrowed deliverable inside `WP-04-POLICY-CORE-P0`, not `WP-05A`,
not a new sub-package, and not code authorization.

It permits only:

- immutable `ObservationCutoffV3` core type with structural fail-closed
  validation;
- immutable structural `ObservationInputContractV3` model shapes;
- exact S2 and final-issued receipt ID/SHA structural references.

Ownership remains:

- `SafetyLifecycle`: sole owner of action/reset barriers;
- `RobotRuntimeAdapter.wait_transition_snapshot(after=receipt)`: sole
  operational creator of one observation cutoff per transition;
- V3 core primitive module: type shape/validation only.

Explicit prohibitions:

- no `ResolvedConfigV3`, raw V3 config, loader, compiler, composition,
  config hash, YAML, profile or resolved-profile changes;
- no ROS/ROSIDL, QoS, TF, DDS, sensor adapter, `/cmd_vel`, or runtime code;
- no S2 buffer/synchronizer, LiDAR sectorizer, assembler, encoder or 81D
  vector construction;
- no receipt interface/bridge/history or safety/final-publisher runtime work;
- no V1 observation, decoder, history or snapshot reuse, wrapper, fallback
  or deletion.

Fixtures in any later implementation packet are in-memory structural fixtures,
never profile values, provenance evidence, measurement or runtime evidence.

WP-04 remains `BLOCKED_BY_CONTRACT`. Its Gate A semantic provenance pins are
recorded in the PEP-001 rev.0.5.0 semantic-bundle reconciliation below. Only
after that PEP revision is canonically integrated may the exact Gate A
implementation packet be prepared and submitted for independent audit. This
does not authorize source changes or implementation; the exact packet still
requires separate user approval and code authorization.


## Non-negotiable implementation rules
- Do not rewrite the project wholesale.
- Do not use mecanum_env.py as architecture/runtime evidence.
- Do not use train_ai.py as a canonical entrypoint until its legacy status is explicitly decided.
- Do not create Gymnasium/PPO training before WP-04 and WP-09.
- Do not treat test/build/static evidence as Gazebo, HIL or real-robot evidence.
- Do not enable deploy_real before required measurement, HIL, Gate 4 and explicit approval.
## Plan change control
A plan update must state:
1. Plan ID and old/new revision.
2. Exact status transition.
3. Work package, branch, base SHA and commit SHA.
4. Dependency/evidence impact.
5. Whether Architecture/ACR impact exists.
6. Ledger entry to append.
7. User approval required before integration.
If an item is blocked, update it to BLOCKED_* with a concrete reason; do not silently reorder or skip it.


## WP-02 closure status transition — PEP-001 rev.0.3.0

This change-control record applies the explicit user-authorized WP-02 status
transition. Per the Metadata `Activation rule`, the transition becomes the
active governance status only when this PEP revision is present on
`integration/implementation`; on this work branch it remains pending
integration. The `Initial status` values in `Ordered work packages` remain
historical and are not rewritten.

| Change-control field | Recorded value |
|---|---|
| Plan ID; old/new revision | `PEP-001`; `0.2.0` -> `0.3.0` |
| Work package | `WP-02-CANONICAL-CLOSURE-INTEGRATION` |
| Work branch | `wp-02-close-and-integrate-3f4a114` |
| Integration base SHA | `3f4a1147d97143995d3cd9c56097a0fb414a40ca` |
| Source candidate branch | `wp-02-pep-closure-transition-candidate-3f4a114` |
| Source candidate commit SHA | `6e962f3a14e60a017dd525a5fda9eed4f77cbe2a` |
| Decision date and authority | `2026-10-07`; explicit user decision in chat, approver role `Project Owner/User` |
| Exact status transition | `WP-02: BLOCKED_BY_GOVERNANCE -> CLOSED` |
| WP-02 current status on activation | `CLOSED`, effective when PEP-001 rev.0.3.0 is canonically integrated |
| Evidence and scope basis | Ledger entry `WP-02I-INTEGRATE-CANONICAL-SOURCE-SELECTION`, candidate commit `eed009d926e721ed37f27f675bbbe27e04cc14fe`, evidence `IMPLEMENTED_OFFLINE_ONLY`; scope coverage is V3 selection, legacy boundary, and source-registry enforcement at governance/source-selection level, not automated runtime enforcement. The closure disposition proposal and its audit are identified in the integration evidence package. |
| Additional evidence condition | No runtime, HIL, hardware, or physical-measurement evidence is required for WP-02 unless a controlling WP-02 authority explicitly requires it; none was identified in the reviewed scope. |
| Dependency/status impact | WP-03 remains `BLOCKED_BY_CONTRACT` and retains its dependency on WP-02 plus required user decisions. WP-04 remains `BLOCKED_BY_CONTRACT`; its WP-03, V3-scope, semantic-bundle, and separate implementation-packet dependencies are unchanged. No WP-03 readiness conclusion is made here. |
| Architecture/ACR impact | None; this is a PEP/governance status-control change only. |
| Ledger entry | `WP-02-CLOSE-CANONICAL-SOURCE-SELECTION`, appended in the same governance integration. |
| Integration commit SHA | Identified by the canonical Git history and evidence export; it is not embedded in the content of the commit that contains it. |
| Authorization boundary | The WP-02 status transition does not authorize WP-03/WP-04 implementation, code, runtime, HIL, hardware, or deployment. Runtime remains `RUNTIME_NOT_APPROVED`. |

The `Ordered work packages` table retains its historical `Initial status`
column and values: WP-02 `BLOCKED_BY_GOVERNANCE`, WP-03
`BLOCKED_BY_CONTRACT`, and WP-04 `BLOCKED_BY_CONTRACT`. The current WP-02
status is recorded separately above; WP-03/WP-04 status and dependencies are
unchanged.


## WP-03 contract-closure status transition — PEP-001 rev.0.4.0

This change-control record proposes the Project Owner/User-authorized
`WP-03: BLOCKED_BY_CONTRACT -> CLOSED` transition. Under the Metadata
`Activation rule`, it becomes the active governance status only when the exact
reviewed final candidate is fast-forwarded to `integration/implementation` and
the remote ref is verified. On this work branch the transition remains
pending. The `Initial status` column and its historical WP-03 value are not
rewritten.

| Change-control field | Recorded value |
|---|---|
| Plan ID; old/new revision | `PEP-001`; `0.3.0` -> `0.4.0` |
| Work package | `WP-03-CLOSURE-AND-SINGLE-INTEGRATION-CANDIDATE` |
| Work branch | `wp-03-close-and-integrate-once-2e7a2980` |
| Integration base SHA | `2e7a2980cb75f0567182ea694c04328d7d8643e0` |
| Audited disposition source branch/commit | `wp-03-decision-contract-reconciliation-2e7a2980` / `b234c2fe5831c1a0ea3c2b1805a5715773d6d2a6` |
| Audit report | `INDEPENDENT_FOCUSED_STATIC_AUDIT_WP03_DECISION_CONTRACT_RECONCILIATION_B234C2FE.md`; SHA-256 `7db8347459af8762da1b74afd99c765a9121e43c2453363049c3f00c0256110f`; `READINESS_FOR_CANONICAL_INTEGRATION: PASS` |
| Decision authority/date | Project Owner/User authorized the dispositions and preparation of this transition candidate; `2026-10-08` |
| Exact status transition | `WP-03: BLOCKED_BY_CONTRACT -> CLOSED` |
| WP-03 current status on activation | `CLOSED`, effective only when this exact reviewed final candidate is fast-forwarded to integration and the remote ref is verified |
| Closure basis | The WP-03 scope in `Ordered work packages`—final-issued receipt, collision/contact, and map/scenario/hardware intake decisions—has authorized dispositions recorded in the seven reviewed records and this decision record. The required user decisions are recorded; no concrete map/scenario values or hardware measurements are invented. |
| Closure/evidence boundary | Closure records the contract decisions and routes later obligations to their PEP work packages: canonical map/scenario/hardware artifact provenance to WP-05; offline safety/final-publisher and task/contact implementation to WP-06/WP-09 under their existing dependencies; approved simulation runtime evidence to WP-11; and physical measurements/HIL to WP-12. It does not claim those evidence items exist or make them prerequisites for this contract-status transition. |
| Dependency/status impact | WP-02 remains `CLOSED`. WP-04 remains `BLOCKED_BY_CONTRACT`; its dependency on WP-03 and all other dependencies/statuses remain unchanged. Closing WP-03 does not satisfy WP-04's other gates or authorize downstream work. WP-05 and later package ordering/dependencies remain unchanged. |
| Architecture/ACR impact | None; this is governance status/change-control only. The audited D2/D3/map/scenario/hardware dispositions are unchanged. |
| Ledger entry | `WP-03-CLOSE-OPEN-CONTRACTS`, appended below under the same candidate change control. |
| Candidate content commit SHA | Identified by the exact candidate tip in Git history; not embedded in the commit containing this content. The audited source commit is recorded above. |
| Integration commit SHA | Identified by canonical Git history/evidence after fast-forward; not embedded in the commit containing this content. |
| Authorization boundary | `CODE_AUTHORIZATION: NOT_GRANTED`. No ROS/ROSIDL, build, test, runtime, HIL, hardware operation, `deploy_real`, or deployment authorization; runtime remains `RUNTIME_NOT_APPROVED`. |

The `Ordered work packages` table retains its historical `Initial status`
values: WP-02 `BLOCKED_BY_GOVERNANCE`, WP-03 `BLOCKED_BY_CONTRACT`, and WP-04
`BLOCKED_BY_CONTRACT`. WP-03's active status is recorded separately by this
change-control section after activation; WP-04 status and dependency are not
changed.


## WP-04 Gate A semantic-bundle reconciliation — PEP-001 rev.0.5.0

This change-control record reconciles the Gate A semantic-bundle references
with the approved source/status authority at the exact integration base. It
does not rewrite any historical `Initial status` value or WP-02/WP-03
transition record. At base `56815516d9a9d000a7b6e41e5290e96bbed7286b`,
WP-03 is `CLOSED` under its previously integrated transition; WP-04 remains
`BLOCKED_BY_CONTRACT`.

### Gate A semantic-provenance pins and current authority

The following exact immutable source bytes pin semantic-design provenance for
Gate A. Full-document hashes are distinguished from an embedded
contract/manifest hash. These provenance pins do not make each pinned source a
canonical or independently approved architecture authority.

| Artifact | Revision / identity | Source repository branch and immutable commit | Source path | Full-document SHA-256 / contract pin |
|---|---|---|---|---|
| S2 Snapshot Synchronization Temporal Contract | Revision `2`; contract ID `mecanum.snapshot-synchronization-temporal/v1`; canonical contract/manifest SHA-256 `1be31c1915fedd86f269cee5214d794da0899a0d69dbb0ba5392e619813d4a8f` | `origin/docs-v3-observation-contract-import` @ `d3ca85536e35b38f7f3dffcf1dfd1bc16983aae9` | `docs/architecture/proposals/v3-observation-contracts/ACR_S2_SNAPSHOT_SYNCHRONIZATION_TEMPORAL_CONTRACT.md` | Full document `e1468d0373922a1806e14da91e7cc0336bcc7d70c4cd3ec4fc749078d86b70ab`; contract/manifest pin as stated |
| Observation Input Contract V3 Design | Revision `6` | `origin/docs-v3-observation-contract-import` @ `d3ca85536e35b38f7f3dffcf1dfd1bc16983aae9` | `docs/architecture/proposals/v3-observation-contracts/OBSERVATION_INPUT_CONTRACT_V3_DESIGN.md` | Full document `200703949d6b326a30ee8e2f75cd2cd14054576e6772ddc6ae3ff670e48eb76c` |
| ACR V3 Observation Boundary Closure | Revision `8`; current approved Gate A/Gate B ACR authority | `origin/integration/implementation` @ `56815516d9a9d000a7b6e41e5290e96bbed7286b` | `docs/ACR_V3_OBSERVATION_BOUNDARY_CLOSURE.md` | Full document `03fef021f6b9731f811f83a5e53aae1c430bdc2ea76815a8ada416f1a5bf772c` |
| QoS6 / ACR8 bundled approval provenance | Approval dated `2026-10-08`; current source/status authority | `origin/integration/implementation` @ `56815516d9a9d000a7b6e41e5290e96bbed7286b` | `docs/governance/decisions/QOS_REVISION_6_ACR_REVISION_8_BUNDLE_APPROVAL.md` | Full document `4d740559f850f179387db802df845748068f75a21266fd1edb52402b2c72c529` |
| QoS Topic Contract | Revision `6`; transport ID `mecanum.final-issued-receipt-topic-qos/v2`; transport-manifest SHA-256 `338bea1b7350d3b82146c7e728516ec7947471ee68db0f8871ddb72071b79620` | `origin/integration/implementation` @ `56815516d9a9d000a7b6e41e5290e96bbed7286b` | `docs/RECEIPT_TOPIC_QOS_CONTRACT.md` | Full document `4200cd2fbdc81a19400f168dd3526eb7871ac2251049fc7c4f5d5c2fddfd2022`; transport manifest pin as stated |

The S2 value `1be31c...` is its embedded canonical contract/manifest SHA,
not the full-document SHA; the latter is `e1468d...` above. The full-document
hashes of the OIC, ACR, approval record and QoS document identify their exact
bytes and are not interchangeable with contract or transport-manifest hashes.

S2 revision 2 at the pinned source is labeled
`DRAFT — PENDING_INDEPENDENT_ARCHITECTURE_REVIEW_AND_USER_APPROVAL`; Observation
Input Contract V3 revision 6 is labeled
`REVISED_DRAFT — PENDING_INDEPENDENT_ARCHITECTURE_REVIEW_AND_USER_APPROVAL`.
They are immutable semantic-design provenance only. This PEP pins their exact
provenance bytes; it does not approve, canonicalize, promote either draft, or
treat either one independently as satisfying an architecture or approval gate.
Neither source grants implementation authorization.

The V3 Observation Boundary Specification revision 7 is retained as
supporting semantic-design provenance, not silently omitted: its source is
`origin/docs-v3-observation-contract-import` @
`d3ca85536e35b38f7f3dffcf1dfd1bc16983aae9`, path
`docs/architecture/proposals/v3-observation-contracts/V3_OBSERVATION_BOUNDARY_SPECIFICATION.md`,
full-document SHA-256
`47ba6c432cc53798e9f8a97f3c0a97aae586d24bef98113716a4493e57ad4eeb`.
For Gate A sequencing and approved Gate A/Gate B scope, it is not a separate
active authority component: the Registry selects ACR revision 8 as the
`CANONICAL_APPROVED_ACR`, and ACR8 §4 carries forward the approved Gate A/Gate B
scope. Accordingly ACR8 at the exact path/hash above is the current ACR
authority for that scope. This statement does not claim that the standalone
specification is globally superseded for every design subject or alter its
technical content.

The QoS6/ACR8 sources remain the current source/status authority under the
Canonical Source Registry and their approval record. `DRAFT` wording in the
immutable QoS6/ACR8 source bytes records the pre-integration history; the
approval record supersedes those labels only for document authority/status
after the exact bundle was canonically integrated. The Registry-selected ACR8
is the current approved ACR authority only for the active Gate A/Gate B scope
it carries forward. PEP-001 rev.0.5.0 controls WP sequencing and Gate A
provenance pins; it does not change the approved QoS/ACR semantics or elevate
the S2/OIC source drafts.

### Gate A effect and boundary

This reconciliation records the semantic bundle for Gate A. It permits only
preparation and independent audit of an exact Gate A implementation packet,
and only after PEP-001 rev.0.5.0 is canonically integrated. It does not change
WP-04's status or dependency, does not make WP-04 implementation-eligible,
does not authorize source edits or code, and grants no runtime approval. The
exact packet must still receive its own independent audit and explicit user
approval; code authorization must be separately granted for that exact packet.

WP-03 is `CLOSED` at the stated integration base under the earlier integrated
WP-03 transition. This reconciliation records no new WP-03 transition. WP-04
remains `BLOCKED_BY_CONTRACT`, retains its dependency on WP-03, and all other
WP statuses/dependencies remain unchanged.

### Change control

| Change-control field | Recorded value |
|---|---|
| Plan ID; old/new revision | `PEP-001`; `0.4.0` -> `0.5.0` |
| Work package | `WP-04-GATE-A-SEMANTIC-BUNDLE-PEP-RECONCILIATION` |
| Work branch | `wp-04-gate-a-semantic-bundle-pep-reconciliation` |
| Integration base / source commit | `56815516d9a9d000a7b6e41e5290e96bbed7286b` |
| Audit authority | `WP04_GATE_A_AUTHORITY_READINESS_AUDIT_56815516.md`; SHA-256 `8328f9560f09e0b03d0210830bc8d3cda03ed8023730554935b4a81694493eb8`; verdict `WP04_GATE_A_CONTRACT_RECONCILIATION_REQUIRED` |
| Candidate content commit | Resolved by Git history from the exact reviewed branch tip; not embedded in this file to avoid a self-referential commit SHA |
| Dependency/evidence impact | No dependency or status transition. WP-03 is already `CLOSED` at the integration base; WP-04 remains `BLOCKED_BY_CONTRACT`. Gate A semantic source identities and hashes are now explicit; only exact packet preparation/audit may follow canonical integration of this PEP revision. |
| Architecture/ACR impact | None. ACR8 is referenced as the current approved contract authority; no Architecture or ACR semantics are amended. |
| Ledger entry | None in this candidate: no status transition is made; the Progress Ledger remains append-only. |
| Approval before canonical integration | Explicit user approval is required after independent audit and before this PEP revision is canonically integrated. |
| Activation / authorization boundary | This branch is a pending PEP proposal under the Metadata Activation rule. Canonical integration activates the governance reconciliation only; it does not grant code authorization, runtime approval, HIL, hardware or `deploy_real` authorization. |

```text
WP-02: CLOSED
WP-03: CLOSED
WP-04: BLOCKED_BY_CONTRACT
CODE_AUTHORIZATION: NOT_GRANTED
RUNTIME_APPROVED: NOT_APPROVED
```

### WP-04 Gate A structural-primitives status transition — PEP-001 rev.0.6.0

This section records the proposed transition for the Gate A structural
primitives only. It is pending on this review candidate and becomes effective
only after this exact candidate passes focused independent audit, the Project
Owner/User separately authorizes integration of its exact commit, that commit
is fast-forwarded to `integration/implementation`, and the remote integration
ref is verified at that commit.

| Change-control field | Recorded value |
|---|---|
| Plan ID; old/new revision | `PEP-001`; `0.5.0` -> `0.6.0` |
| Work package | `WP-04-GATE-A-STATUS-TRANSITION-CANDIDATE` |
| Work branch | `wp-04-gate-a-status-transition-d33b93d` |
| Integration base | `d33b93d3c6389872450f1a001e3073c61f355824` |
| Prior candidate provenance | `wp-04-gate-a-status-transition-793514f@481047c055cf7f7bdfb9e91cd6443cf0022518e3`; stale-base content provenance only, not modified, rebased, or delivered by this work package |
| Proposed transition | `GATE_A: NOT_PASSED` -> `PASSED`, limited to Gate A structural-primitives acceptance, and pending the activation conditions above |
| Candidate content commit | Resolved from the final reviewed branch tip; not embedded here to avoid a self-referential commit SHA |
| Dependency/evidence impact | WP-03 is `CLOSED` at the base and its recorded dependency is satisfied for this constrained Gate A structural scope. No dependency changes. WP-04 remains `BLOCKED_BY_CONTRACT`. |
| Architecture/contract impact | None. No change to Architecture, ACR8, QoS6, the canonical structural schema, error-carrier decision, or technical semantics. The intervening integration delta from `793514f…` to `d33b93d…` is limited to four WP-05 governance documents and does not change the Gate A authority/evidence pins. |
| Ledger entry | One new append-only candidate entry records the pending transition; no historical Ledger entry is changed and no active/canonical transition is recorded. |
| Approval before canonical integration | Focused independent audit and separate explicit Project Owner/User authorization for this exact final commit are required before integration. |

#### Pinned implementation evidence

The evidence scope is limited to the structural-primitives implementation and
its focused pure-Python tests, integrated at commit
`793514f8ff3c20c13bfe84bf0529295de4d4d0b4` and unchanged by the intervening
WP-05 governance integration:

| Evidence | Exact reference | SHA-256 / result |
|---|---|---|
| Structural primitive module | `ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/core/v3_observation_contracts.py` | `2d2013b3d584b1e42e71dcce85417e1402c4667dba41d95c820dd4499f7e7b3` |
| Focused test file | `ros2_ws/src/mecanum_nav_rl/test/test_v3_observation_contract_primitives.py` | `8eacfca6e70bd987df9b4e00c769b9fe154e3c6632e2cb6245249f77b2fdd853` |
| Focused test result | `PYTHONPATH=ros2_ws/src/mecanum_nav_rl PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider ros2_ws/src/mecanum_nav_rl/test/test_v3_observation_contract_primitives.py` | `69 passed in 0.21s`; directly reviewed evidence supplied for the prior integration review |
| Audit and decision provenance | Focused audit verdict and current User decision | Supplied by the User in the work-package context; no audit-report SHA-256 is asserted because no report hash is pinned here |

The proposed `PASSED` transition is limited to the Gate A structural-primitives
acceptance scope represented by those exact source and test bytes. It excludes
Gate B, connected behavior, the 81D observation vector, ROS adapters, runtime,
HIL, hardware, and deployment. It does not close WP-04 or grant any new code,
ROS, runtime, HIL, hardware, `deploy_sim`, or `deploy_real` authorization. No
code authorization beyond the prior exact two-path grant is created here.

Until this exact candidate passes focused audit, receives separate User
integration authorization, is fast-forwarded, and has its remote ref verified,
the recorded candidate state is:

```text
WP-04: BLOCKED_BY_CONTRACT
GATE_A_STRUCTURAL_PRIMITIVES: PASSED_PENDING_FOCUSED_AUDIT_AND_CANONICAL_INTEGRATION
GATE_B: NOT_STARTED
RUNTIME_APPROVED: NOT_APPROVED
WP-05: OPEN
```

#### Source-amendment provenance correction (evidence only)

This correction adds immutable traceability for the source Architecture
amendment. It does not change the proposed schema or technical semantics and
does not represent approval, activation, authorization, or Gate B pass.

| Provenance field | Pinned value |
|---|---|
| Work package | `WP-04-OBSERVATION-INPUT-PROFILE-ARCHITECTURE-AMENDMENT` |
| Source review branch | `wp-04-observation-input-profile-architecture-amendment-e89aeda5` |
| Original amendment commit | `d87b5a17ca0e9430d0b163aacf5b9cfcc4458d14` |
| Direct parent/base | `e89aeda5ca78859bfeedac4e7b94bcd6c7dcc7f0` |
| Evidence record | `docs/governance/evidence/WP-04_OBSERVATION_INPUT_PROFILE_ARCHITECTURE_AMENDMENT_PROVENANCE.json`; SHA-256 `eba5f233a2488d11b5161f6b87abd4994d749763f36eb768d4577f445e326069` |
| Record purpose | Provenance/evidence only; not approval, activation, authorization, or Gate B pass |
| Correction successor | `wp-04-observation-input-profile-architecture-amendment-correction-e89aeda5`; correction commit identity is resolved from Git history and is not embedded in its own evidence record |
| Candidate state | Pending focused audit, separate User authorization for exact correction tip, fast-forward, and remote-ref verification |

### Historical WP-04 ObservationInputProfileV3 candidate/provenance snapshot — PEP-001 rev.0.9.0 source content

At the historical integration point recorded by this rev.0.9.0 source content, commit `d87b5a17ca0e9430d0b163aacf5b9cfcc4458d14` and revision-3 downstream materials were present in ancestry as Git facts. At that point the controlling ACR remained `CANDIDATE_ONLY_PENDING_FOCUSED_INDEPENDENT_AUDIT_AND_CANONICAL_INTEGRATION`. Ancestry alone did not prove that the exact candidate passed focused audit or received separate exact-commit User authorization. The later activation at `8c3de26521d7028a933f0a3ebe780fcb372f7a3a` is recorded in the current rev.0.10.2 section below. This PEP historical content is retained as provenance.

| Change-control field | Recorded value |
|---|---|
| Plan ID; source revision | `PEP-001`; `0.9.0` candidate source content |
| Work package | `WP-04-OBSERVATION-INPUT-PROFILE-ARCHITECTURE-AMENDMENT` and status reconciliation |
| Source integration base | `e89aeda5ca78859bfeedac4e7b94bcd6c7dcc7f0`; source commit `d87b5a17ca0e9430d0b163aacf5b9cfcc4458d14` is in ancestry at `410d9cb70518b64d3c76c2ef99b11b69d1da6701` |
| ACR authority/status | `docs/architecture/ARCH_CHANGE_RECORD_OBSERVATION_INPUT_PROFILE_V3.md`; candidate-only pending its stated focused-audit, exact User-authorization, canonical-integration, and remote-ref conditions |
| Downstream proposal | `ObservationConfig.input_profile: ObservationInputProfileV3`; no root `gate_b`; proposed shape does not become effective by Git ancestry |
| Candidate hash/compiler proposal | Global `ResolvedConfig.config_hash` over the resolved config; exact non-circular implementation projection remains unresolved and is a Gate B blocker |
| Static/runtime boundary | Proposed static descriptor uses contract and immutable-source references only; runtime ingress facts remain separate. No adapter, ROSIDL or runtime implementation is claimed |
| Concrete pins | Required exact contract IDs/digests and source pins remain unresolved; no profile instance is claimed resolved |
| Status/dependency impact | No transition: WP-04 remains `BLOCKED_BY_CONTRACT`; Gate A structural primitives `PASSED`; Gate B `NOT_STARTED`; WP-05 `OPEN` |
| Authorization boundary | `CODE_AUTHORIZATION: NOT_GRANTED`; `RUNTIME_APPROVED: NOT_APPROVED`; no ROS/ROSIDL, runtime, HIL, hardware, `deploy_sim`, or `deploy_real` authority |

```text
WP-04: BLOCKED_BY_CONTRACT
GATE_A_STRUCTURAL_PRIMITIVES: PASSED
GATE_B: NOT_STARTED
GATE_B_BOUNDARY_CLOSURE: ACTIVE_ON_INTEGRATION
OBSERVATION_INPUT_PROFILE_SCHEMA: INTEGRATION_RESIDENT_CANDIDATE_PENDING_ACR_ACTIVATION_CONDITIONS
GLOBAL_CONFIG_HASH_PROJECTION: PROPOSAL_PENDING_ACR_ACTIVATION_AND_EXACT_NON_CIRCULAR_RESOLUTION
CONCRETE_PROFILE_REFERENCE_PINS: PENDING_ACTIVE_AUTHORITY_AND_EVIDENCE
CODE_AUTHORIZATION: NOT_GRANTED
RUNTIME_APPROVED: NOT_APPROVED
WP-05: OPEN
```

### WP-04 Gate B exact-data-contract completion refresh — PEP-001 rev.0.8.0 historical pre-integration snapshot

This section records the candidate and pending state at its historical
revision-0.8.0 refresh point. Its labels are retained as history. The later
revision-0.9.0 source content above records an integration-resident candidate
and provenance fact, while amendment activation remains controlled by the ACR
and its conditions. Neither that ancestry fact nor this PEP candidate activates
the amendment. Gate B and implementation authorization remain unchanged.

This replacement governance candidate carries forward the correction from
`wp-04-gate-b-exact-data-contract-completion-correction-68174e@73a1f73c39eb742e79f53f50d5b5d73b41be0822`
without modifying or repushing that source branch. The prior review candidate
`wp-04-gate-b-exact-data-contract-change-control-68174e@687469f4aa2f166566e31aa91c1b1d90648c3812`
is superseded review provenance only; it was never integrated and is not
active authority. The source correction is also source/provenance only, not
the replacement candidate or active source selection. This replacement is
candidate-only until its exact final commit passes consolidated independent
audit, receives separate explicit User authorization, is fast-forwarded to
`integration/implementation`, and has its remote ref verified.

| Change-control field | Recorded value |
|---|---|
| Plan ID; old/new revision | `PEP-001`; `0.7.0` -> `0.8.0` |
| Work package | `WP-04-GATE-B-EXACT-DATA-CONTRACT-COMPLETION-REFRESH` |
| Replacement branch | `wp-04-gate-b-exact-data-contract-completion-refresh-1e14644` |
| Integration base | `1e14644a7d778a0c5ad32512430d775fd0e8ecd3` |
| Superseded review provenance | `wp-04-gate-b-exact-data-contract-change-control-68174e@687469f4aa2f166566e31aa91c1b1d90648c3812`; candidate-only, not integrated or active |
| Correction source provenance | `wp-04-gate-b-exact-data-contract-completion-correction-68174e@73a1f73c39eb742e79f53f50d5b5d73b41be0822`, parent `68174e714cbe8aab61880113496cd7ccd7f97f5d`; source-only, unchanged, not integrated as this candidate |
| Source correction artifact hashes | Specification `06157a2d5c980d90677e37de7e120c97c98111a8a18a92897746738a691de2a2`; decision `9a2979c15dfc5ce0649ab45e30adeb840862c98065a33eafc6ac41418f673f29`; Registry `538a0f85559f061295bea824a31bf4fdaf64d44afaeab57f7a220ff70a96b51e`; PEP `ac1ab8f437154857381108e51b992f7203533dcc68f95b38c37c86a9c9ea7a70`; Ledger `6fa6fa7a55b20b57c34068fbbe6af06936db1d68e8f5e24f100e1a6a2783db3b` |
| Replacement artifacts | `docs/OBSERVATION_V3_SPECIFICATION.md` revision 2, SHA-256 `ed06bc5bd145e0eb9376df71ff42ee60069906d987c78531ba8b9e688746b1bc`; `docs/governance/decisions/WP-04_GATE_B_CONSOLIDATED_DECISION.md`, SHA-256 `9a683c12939c4f092341f8632507f8bc0ec45280ecd5e9a4b56a04a6f9828048`; both candidate-only. Registry, PEP and Ledger exact bytes are identified by the reviewed branch tip to avoid self-reference. |
| Deferred blockers | `DECISION_DEFERRED_PENDING_EXACT_NON_CIRCULAR_CONFIG_HASH_PROJECTION` and `DECISION_DEFERRED_PENDING_EXACT_RESOLVED_OBSERVATION_INPUT_PROFILE_SHAPE`; independent, to be resolved together in one consolidated resolved-config Owner decision before any code-authorization candidate is considered |
| Candidate state | Replacement documentation only; `GATE_B: NOT_STARTED`; boundary closure remains active on the integration base; no resolved-record shape is active |
| Dependency/status impact | No transition or dependency change. WP-04 remains `BLOCKED_BY_CONTRACT`; Gate A structural primitives remain `PASSED`; Gate B remains `NOT_STARTED`; WP-05 remains `OPEN` |
| Architecture/contract impact | Carries forward the flat binding, strict types/ranges/value semantics, selected lifecycle tuple and ACR8 mappings, adapter/core boundary, raw-ROS prohibition, and `PENDING_MEASUREMENT`. Does not select `ResolvedGateBRecordV3` member/type/value semantics or use OIC rev.6 as field/default/schema authority. WP-05 draft map artifact/status at base are untouched. |
| Ledger entry | One append-only refresh entry; all Ledger bytes at base are preserved byte-for-byte |
| Activation/authorization boundary | Candidate-only pending audit, separate exact-commit User authorization, fast-forward and remote-ref verification. No `CODE_AUTHORIZATION`, runtime, HIL, hardware, `deploy_sim`, or `deploy_real` authority |

This candidate does not claim that `ResolvedGateBRecordV3` has an exact
member set, exact input-profile shape, or resolved non-pending values. OIC
revision 6 remains `REVISED_DRAFT` provenance-only and cannot define
fields/defaults/schema. `ResolvedConfigV3.gate_b` is a required
compiler-owned slot only; it does not establish the slot's value shape. The
two deferred blockers must be resolved together before any code-authorization
candidate is considered. No Gate B pass, WP-04 closure, or runtime evidence is
recorded.

```text
WP-04: BLOCKED_BY_CONTRACT
GATE_A_STRUCTURAL_PRIMITIVES: PASSED
GATE_B: NOT_STARTED
GATE_B_BOUNDARY_CLOSURE: ACTIVE_ON_INTEGRATION
CONFIG_HASH_PROJECTION: DECISION_DEFERRED_PENDING_EXACT_NON_CIRCULAR_CONFIG_HASH_PROJECTION
RESOLVED_INPUT_PROFILE_SHAPE: DECISION_DEFERRED_PENDING_EXACT_RESOLVED_OBSERVATION_INPUT_PROFILE_SHAPE
CODE_AUTHORIZATION: NOT_GRANTED
RUNTIME_APPROVED: NOT_APPROVED
WP-05: OPEN
```

### Historical WP-04 Gate B boundary-closure review snapshot — PEP-001 rev.0.7.0

The candidate-pending wording in this historical rev.0.7.0 section records
the pre-integration state. The boundary-closure bundle was later integrated
at `68174e714cbe8aab61880113496cd7ccd7f97f5d`; at this base, revision 1 is
active only as the controlled Gate B boundary/specification selection, as
recorded in the Canonical Source Registry. This activation does not select a
`ResolvedGateBRecordV3` shape, pass Gate B, or authorize implementation.

This section records a documentation-only candidate based on the User-supplied
decision basis `WP04_GATE_B_CONSOLIDATED_OWNER_DECISION_PROPOSAL_572DA885`.
That proposal is provenance supplied in the work-package context, not a
Git-pinned authority; no report hash is asserted. The candidate-pending state
in the historical table below describes its pre-integration state only. At the
then-current integration base `410d9cb70518b64d3c76c2ef99b11b69d1da6701`, revision 1
remained the active Gate B boundary-source selection. Its exact immutable source
is `wp-04-gate-b-boundary-closure-decision-50476170@68174e714cbe8aab61880113496cd7ccd7f97f5d`,
path `docs/OBSERVATION_V3_SPECIFICATION.md`, full-document SHA-256
`feffb86e335d64a3a3fe0f3a1ce0866f868c8ed56ffa4412db14128c80b284ec`. Revision
2 is superseded historical review provenance. Revision 3 and its companion
Architecture amendment were candidate-only at that historical base; their
presence in integration ancestry did not replace revision 1 or activate the
amendment. This selection was only the
existing Gate B boundary source; it does not pass Gate B, resolve its blockers,
or authorize implementation/runtime.

| Change-control field | Recorded value |
|---|---|
| Plan ID; old/new revision | `PEP-001`; `0.6.0` -> `0.7.0` |
| Work package | `WP-04-GATE-B-CONSOLIDATED-BOUNDARY-CLOSURE` |
| Work branch | `wp-04-gate-b-boundary-closure-decision-50476170` |
| Integration base | `50476170bb545483905308e5887990ab6220c566` |
| Decision provenance | User-supplied `WP04_GATE_B_CONSOLIDATED_OWNER_DECISION_PROPOSAL_572DA885`; not represented as Git-pinned authority; audit/report hash not asserted |
| Historical pre-integration candidate artifacts | `docs/OBSERVATION_V3_SPECIFICATION.md` revision 1 and `docs/governance/decisions/WP-04_GATE_B_CONSOLIDATED_DECISION.md`; candidate-pending status below records their state before integration |
| Candidate content commit | Resolved from the final reviewed branch tip; not embedded here to avoid self-reference |
| Candidate state | `GATE_B_BOUNDARY_CLOSURE: PENDING_FOCUSED_AUDIT_AND_CANONICAL_INTEGRATION`; `GATE_B: NOT_STARTED` |
| Dependency/status impact | No WP status or dependency transition. WP-04 remains `BLOCKED_BY_CONTRACT`; Gate A structural primitives remain `PASSED`; WP-05 remains `OPEN`. |
| Architecture/contract impact | Records boundary decisions without changing Architecture, ACR8, QoS6, receipt v2 bytes, Gate A schema, or Gate A error-carrier decision. Exact receipt/lifecycle comparison member mapping and selected public wrapper field/type details remain pending as stated in the specification; no implementation may infer them. |
| Ledger entry | One append-only candidate entry at the end of the Ledger; no historical entry is modified and no active Gate B status is recorded. |
| Authorization boundary | No `CODE_AUTHORIZATION`, ROS/ROSIDL generation, adapter, runtime, HIL, hardware, `deploy_sim`, or `deploy_real` authority. Runtime remains `RUNTIME_NOT_APPROVED`. |

The candidate records the eight User-supplied boundary decisions, pins the
approved QoS6/ACR8 bundle, and specifies fail-closed outcomes using the
existing ACR8 vocabulary. It does not claim that ACR8's six Gate B conditions
are satisfied, does not start Gate B, and does not close WP-04. Any exact
implementation allowlist requires later contract closure, independent review,
and a separate explicit implementation authorization.

```text
WP-04: BLOCKED_BY_CONTRACT
GATE_A_STRUCTURAL_PRIMITIVES: PASSED
GATE_B: NOT_STARTED
CODE_AUTHORIZATION: NOT_GRANTED
RUNTIME_APPROVED: NOT_APPROVED
WP-05: OPEN
```

### Historical WP04-GATE-B-CONFIG-HASH-EXHAUSTIVE-ROOT-CORRECTION — PEP-001 rev.0.10.1 pre-activation snapshot

At historical base `c1187de97c550b9968d88aa6043ed716df981b54`, Observation V3
Specification revision 1 was the active Gate B boundary-source selection
at its pinned immutable bytes. The revision-3 file at the current path and its
companion Architecture Change Record were candidate-only. Source candidate
`wp-04-gate-b-global-config-owner-decision-c1187de@e79a8f6fd6be7b50dbbfe28819a34116ecaec3ab`
records ACR revision 2 / Specification revision 4. Correction review branch
`wp-04-gate-b-config-hash-root-correction-c1187de` has that source commit as
its direct parent. This correction candidate records ACR revision 3 (SHA-256
`38cb74c0b09cd9c3ecbbac30c6520e0d01f7711adb788414a0a46489e844d9f8`) and
Specification revision 5 (SHA-256
`4092ee19d48a760b329ff49b9a79e39ab8389ff232aabd5dd06db83f8d83e5a2`). These
were review-candidate records at that historical base; Git ancestry did not activate the amendment.
The Project Owner/User approved both policies as written on 2026-10-12
(`APPROVE_BOTH_AS_WRITTEN`):

1. `ResolvedConfig.config_hash` is SHA-256 of RFC 8785 JCS canonical UTF-8
   bytes for the complete resolved and validated static Architecture
   `ResolvedConfig`; there is no BOM or trailing newline; only the output
   `config_hash` is omitted from the payload. No Gate-B-only or subrecord hash
   substitutes for the global hash.
2. The required static Gate-B profile is nested at
   `ObservationConfig.input_profile: ObservationInputProfileV3`; no root
   `gate_b` member is added. The profile is covered by the global hash.

These were Owner decisions recorded for change-control at the historical base. Runtime-only facts, raw ROS/receipt data and samples
are invalid config inputs and cause rejection rather than being silently
filtered. Missing/unknown/defaulted/coerced/unresolved values, unavailable
required pins/evidence, duplicate keys, non-finite numbers, or required
`PENDING_MEASUREMENT` / `PENDING_OWNER_DECISION` data reject the whole resolved
configuration; no partial config/hash is emitted. Concrete profile pins and
required measurements remain unresolved. OIC revision 6 remains
provenance-only.

| Change-control field | Recorded value |
|---|---|
| Work package / base | `WP04-GATE-B-CONFIG-HASH-EXHAUSTIVE-ROOT-CORRECTION`; integration base `c1187de97c550b9968d88aa6043ed716df981b54`; direct parent `e79a8f6fd6be7b50dbbfe28819a34116ecaec3ab` |
| Architecture authority | `docs/MECANUM_NAV_DRL_Architecture.docx`, SHA-256 `432eeac363a595cfcf7e81c4b66054fb674dba140a2ef3cffecd617ab8136204`; unchanged and highest authority until ACR activation |
| Active boundary source | Observation V3 Specification revision 1 at `wp-04-gate-b-boundary-closure-decision-50476170@68174e714cbe8aab61880113496cd7ccd7f97f5d`, SHA-256 `feffb86e335d64a3a3fe0f3a1ce0866f868c8ed56ffa4412db14128c80b284ec` |
| Candidate documents | Source review candidate `e79a8f6fd6be7b50dbbfe28819a34116ecaec3ab` (direct parent/integration base `c1187de97c550b9968d88aa6043ed716df981b54`); correction candidate ACR revision 3 (`38cb74c0b09cd9c3ecbbac30c6520e0d01f7711adb788414a0a46489e844d9f8`) and Observation V3 Specification revision 5 (`4092ee19d48a760b329ff49b9a79e39ab8389ff232aabd5dd06db83f8d83e5a2`), with this PEP revision, Gate-B decision, Registry and one append-only Ledger entry |
| F-01 evidence | User-supplied focused independent audit finding that ACR §4 and Specification §5.1 lacked an explicit exhaustive global-hash root list; no audit-report hash is asserted |
| Projection roots | Exhaustive Architecture §4 root set is listed in ACR revision 3 §4 and Specification revision 5 §5.1; only output `config_hash` is omitted, and forbidden runtime values are rejected rather than filtered |
| Candidate state | Pending focused independent audit, separate exact-commit User authorization, fast-forward and remote-ref verification; no ACR activation or active profile schema is claimed |
| Status/dependency | No transition: WP-04 `BLOCKED_BY_CONTRACT`; Gate A structural primitives `PASSED`; Gate B `NOT_STARTED`; WP-05 `OPEN` |
| Authorization | `CODE_AUTHORIZATION: NOT_GRANTED`; `RUNTIME_APPROVED: NOT_APPROVED`; no ROS/ROSIDL, adapter, HIL, hardware, `deploy_sim` or `deploy_real` authority |

### Historical PEP-001 rev.0.10.2 snapshot — status before integration 3fc3e2e

At integration base `8c3de26521d7028a933f0a3ebe780fcb372f7a3a`, ACR revision 3 (SHA-256 `38cb74c0b09cd9c3ecbbac30c6520e0d01f7711adb788414a0a46489e844d9f8`) activated Observation V3 Specification revision 5 (SHA-256 `4092ee19d48a760b329ff49b9a79e39ab8389ff232aabd5dd06db83f8d83e5a2`). Exact-candidate audit PASS and separate exact-commit User authorization are `USER_SUPPLIED_EVIDENCE`; no report hash is asserted. The fast-forward from `c1187de97c550b9968d88aa6043ed716df981b54` and remote-ref verification are Git-verifiable facts. This PEP revision records status/provenance only; it does not modify technical semantics or itself establish a further activation event.

Concrete contract/source pins and required evidence remain pending; measurements remain `PENDING_MEASUREMENT`. ACR activation creates no profile instance and does not satisfy Gate B. Historical PEP rev.0.10.1 text records the pre-activation state at `c1187de`; it is not current status.

| Field | Current disposition |
|---|---|
| Active specification | Observation V3 Specification rev.5, exact SHA above; rev.1 was the historical pre-activation source selection and revs.1–4 remain provenance |
| WP/status | WP-04 `BLOCKED_BY_CONTRACT`; Gate A structural primitives `PASSED`; Gate B `NOT_STARTED`; WP-05 `OPEN` |
| WP-05 map boundary | `warehouse_map2` remains `approval_status: draft`, `world_frame: NOT_DECLARED`, `runtime_compatibility: NOT_VALIDATED`; User-supplied SLAM-source attribution is provenance only, not map/world equivalence, transform, alignment, runtime validation, or map approval |
| Authorization | `CODE_AUTHORIZATION: NOT_GRANTED`; `RUNTIME_APPROVED: NOT_APPROVED`; no ROS, HIL, hardware, or deployment authority |

At that snapshot, the status-reconciliation content was review material. The event it described has since been recorded as integrated commit `3fc3e2e583550b47195720f0de2fda8fbbd7490f`; no map artifact/evidence or WP-05 state changed.

### WP04-ACR3-STATUS-RECONCILIATION — PEP-001 rev.0.10.3

This revision reconciles the already-integrated status event at exact base `3fc3e2e583550b47195720f0de2fda8fbbd7490f`. Git verifies that commit is on `integration/implementation`. The exact ACR revision-3 audit PASS and separate exact-commit User authorization are `USER_SUPPLIED_EVIDENCE`; no audit-report hash is asserted. ACR revision 3 and Observation V3 Specification revision 5 remain the active technical authority from `8c3de26521d7028a933f0a3ebe780fcb372f7a3a`. The review candidate `4a938773cfd8f36cc81934951f4fa02dae99cb05` was reported by the User as audit PASS evidence but was not integrated after preflight found stale post-integration wording; no technical authority is inferred from that unintegrated review commit.

Earlier PEP sections that say a status/activation event was candidate-only or awaiting integration are snapshots at their explicitly stated earlier base/commit, not the current state of the event at `3fc3e2e…`.

Concrete required contract/source pins and evidence remain `PENDING_OWNER_DECISION`; measurements remain `PENDING_MEASUREMENT`. ACR activation creates no resolved profile and does not satisfy Gate B. WP-04 remains `BLOCKED_BY_CONTRACT`; Gate A structural primitives remain `PASSED`; Gate B remains `NOT_STARTED`; WP-05 remains `OPEN`. `warehouse_map2` remains `approval_status: draft`, `world_frame: NOT_DECLARED`, `runtime_compatibility: NOT_VALIDATED`. User-supplied SLAM-source attribution remains provenance only, not evidence of map/world equality, a transform, metric alignment, runtime validation, or map approval. `CODE_AUTHORIZATION: NOT_GRANTED`; `RUNTIME_APPROVED: NOT_APPROVED`; no code, ROS, HIL, hardware, or deployment authority is granted.

### WP04-OBSERVATION-INPUT-CONTRACT-V3-ARCHITECTURE-CLOSURE — PEP-001 rev.0.10.4 candidate snapshot

At exact source base `5497b7e1938242422594f8150b06a32fe221ee70`, this plan update routes the Owner-approved L2 abstract typed-boundary candidate through independent audit and separate exact-commit User authorization. After fast-forward and remote-ref verification, its records are integration-resident L2 target-governance only; technical activation remains a separate change-control. ACR revision 3 and Observation V3 Specification revision 5 remain active technical authority until that activation. This PEP candidate does not itself activate technical semantics or infer audit/authorization from ancestry.

The candidate defines five abstract revision-v3 contract identities in `docs/OBSERVATION_INPUT_CONTRACT_V3.md`, with canonical semantic manifest SHA-256 `175a1af789b6641cfe455daeee8fedac80aaf80ad8c00792ba0a287c41acc0bb`. It does not select concrete source/profile pins or measurement values and does not alter the active global 16-root `ResolvedConfig.config_hash`, nested `observation.input_profile`, receipt v2, or QoS6.

**Critical path:** L2 contract candidate audit/authorization/integration → separate activation/change-control → L1 immutable source selection and profile-manifest closure → exact code-authorization packet → pure-core/compiler implementation and offline acceptance → separately authorized ROS adapter/QoS integration → runtime evidence → later HIL/hardware gates. This ordering is planning only and grants no authority.

No profile instance is resolved. Six concrete profile-reference groups remain unselected; applicable LiDAR geometry/range/extrinsic, timing, freshness, skew, timeout/buffer, twist validity/covariance/provenance, TF alignment, and runtime publisher evidence remain pending or `PENDING_MEASUREMENT`. WP-04 remains `BLOCKED_BY_CONTRACT`; Gate A structural primitives remain `PASSED`; Gate B remains `NOT_STARTED`; WP-05 remains `OPEN`; `CODE_AUTHORIZATION: NOT_GRANTED`; `RUNTIME_APPROVED: NOT_APPROVED`.

Candidate lifecycle: before integration, this exact work is a review-candidate snapshot pending independent audit, separate exact-commit User authorization, fast-forward, and remote-ref verification. After those conditions, it is an integration-resident L2 target-governance record only; the technical semantics still await separate activation/change-control.

### WP04-OIC-V3-TECHNICAL-ACTIVATION — PEP-001 rev.0.10.5 source-base snapshot

At exact source base `23a7e21e320395091de4dd1b1700845355dc4391`, this plan update and ACR revision 8 / Specification revision 10 are an activation review candidate. OIC V3 source-file SHA-256 is `d44d33843c32d1f0d5c747522f3add09bfde21fcb0884e21da93a52476cb4dfc`; its semantic-manifest SHA-256 is `175a1af789b6641cfe455daeee8fedac80aaf80ad8c00792ba0a287c41acc0bb`. These are distinct digest roles. The manifest and OIC document bytes are unchanged by this activation candidate.

After independent audit PASS for this exact activation candidate, separate exact-commit User authorization, fast-forward, and remote-ref verification, OIC V3 and its manifest have status `ACTIVE_TECHNICAL_AUTHORITY_FOR_ABSTRACT_OIC_V3_CONTRACT_SEMANTICS_ONLY`. The frozen Architecture and ACR revision-3 / Specification revision-5 base authority are then extended by OIC V3 for the typed observation-input boundary; the base revisions are not the sole authority for that boundary. This candidate does not claim those conditions already occurred and does not infer them from ancestry.

Activation is limited to abstract contract semantics. It does not select concrete source pins, profile instances, runtime topics/publishers, package versions, or measurements. Six profile-reference groups and applicable evidence remain unresolved; required measurements remain `PENDING_MEASUREMENT`. The next prerequisite is L1 canonical source-pin/profile-manifest closure, not code. The global 16-root `ResolvedConfig.config_hash`, nested `observation.input_profile`, receipt v2, QoS6, and existing fail-closed semantics are unchanged.

**Critical path after activation:** L1 canonical source-pin and profile-manifest closure → exact code-authorization packet → separately authorized pure-core/compiler implementation and offline acceptance → separately authorized ROS adapter/QoS integration → runtime evidence → later HIL/hardware gates. This ordering is planning only and grants no authority.

WP-04 remains `BLOCKED_BY_CONTRACT`; Gate A structural primitives remain `PASSED`; Gate B remains `NOT_STARTED`; WP-05 remains `OPEN`; `CODE_AUTHORIZATION: NOT_GRANTED`; `RUNTIME_APPROVED: NOT_APPROVED`. No profile is resolved and no code, ROS/ROSIDL, runtime, HIL, hardware, or deployment authority is granted.

### WP04-OIC-V3-RUNTIME-BINDING-ARCHITECTURE-DECISION — PEP-001 rev.0.10.6 source-base snapshot

At exact source/integration base `7e72998c7bc8f9fb0a042672a9444879cd9baedd`, this is a seven-path documentation candidate. The target public bindings are recorded in `docs/OBSERVATION_RUNTIME_BINDING_V3.md` (source SHA-256 `ce2c979788658b45facbabdc3f7063f8663bf71380ab839531afcf7e204173b1`) and its semantic manifest (SHA-256 `e800f7169304624d81334c26a638c27c9cbaa11a6df0ba5531b1718ee914f76f`). The manifest digest is not the contract document's source-file digest.

At the source base, OIC v3 remains active abstract contract authority and this L2 binding candidate is not yet active. After exact-candidate independent audit PASS, separate exact User authorization, fast-forward, and remote-ref verification, it becomes active L2 runtime-binding technical authority for target endpoints/ownership only; no separate activation candidate is required. The active OIC semantic-manifest/source fingerprints and established receipt v2/QoS6 pins remain unchanged.

No executable source/package/launch pin, concrete profile, geometry, extrinsic, range, covariance, timeout, cadence, latency, freshness, skew, or runtime evidence is selected. Such pins remain `PENDING_IMPLEMENTATION_SOURCE_PIN`; required measurements remain `PENDING_MEASUREMENT`. Missing/unverifiable prerequisites fail closed: no profile resolution, no global `config_hash`, and no Gate B bring-up.

**Critical path:** activate this exact L2 target-binding candidate only after its audit/authorization/integration conditions → L1 immutable implementation-source/profile pin closure and required measurements → separately reviewed exact code-authorization packet → separately authorized pure-core/compiler implementation and offline evidence → separately authorized ROS adapter/QoS and runtime evidence → later HIL/hardware gates. This candidate itself grants no code or runtime authority.

WP-04 remains `BLOCKED_BY_CONTRACT`; Gate A remains `PASSED`; Gate B remains `NOT_STARTED`; WP-05 remains `OPEN`; `CODE_AUTHORIZATION: NOT_GRANTED`; `RUNTIME_APPROVED: NOT_APPROVED`.

### WP04-OIC-V3-BOUNDED-FAIL-CLOSED-IMPLEMENTATION-AUTHORIZATION — PEP-001 rev.0.10.8 status correction

At exact source-base/review snapshot `5e5075b5860034527350629c686c2d26651fbfeb`, OIC V3 and the L2 runtime-binding authority are integration-resident. Before integration of the exact correction candidate, the current status is `CODE_AUTHORIZATION: NOT_GRANTED` and `RUNTIME_APPROVED: NOT_APPROVED`. This four-path governance record carries a conditional, bounded decision: only after independent audit PASS for the exact correction candidate, separate exact-commit User authorization, fast-forward, and remote-ref verification does the post-integration status become `CODE_AUTHORIZATION: GRANTED_BOUNDED_FAIL_CLOSED_INTERNAL_SEAMS_ONLY` while `RUNTIME_APPROVED: NOT_APPROVED` remains unchanged.

`BOUNDED_FAIL_CLOSED_IMPLEMENTATION_AUTHORIZATION` is the name of the Owner-approved scope; `GRANTED_BOUNDED_FAIL_CLOSED_INTERNAL_SEAMS_ONLY` is its canonical status token after all four conditions. Review push or Git ancestry alone does not grant authorization. The token applies only to the internal code seams listed in `docs/governance/decisions/WP-04_OIC_V3_BOUNDED_IMPLEMENTATION_AUTHORIZATION.md` and does not expand their scope.

The permitted future code candidate is limited to typed snapshot/context structures, strict fail-closed validation, a pure-core assembler/synchronizer over already-validated typed values, and dependency-injected internal boundaries for LiDAR, LocalReference, measured twist, and receipt/lifecycle context. It is not ROS ingress and does not include ROS endpoints, public interfaces, launch/runtime config, TF runtime, Nav2/localization/EKF setup, profile/config resolution, or runtime execution. Missing/mismatched inputs yield no vector; no partial vector/hash, default, alias, coercion, zero-fill, or legacy/simulation fallback is permitted. Code review and test/offline acceptance evidence remain required.

Source/package/version pins, concrete profile inputs, and applicable measurements/evidence remain unresolved or `PENDING_MEASUREMENT`; they are prerequisites for later profile resolution and bring-up, not values this authorization supplies. The active global 16-root `ResolvedConfig.config_hash`, OIC/runtime-binding semantics, receipt v2, and QoS6 remain unchanged. The next permitted work after this governance candidate is integrated is a separately scoped bounded code candidate, not Gate B bring-up. ROS adapter/QoS integration, runtime, HIL, hardware, and deployment remain outside this authorization and require their own evidence/approval.

Candidate lifecycle: at source base `5e5075b…`, this exact correction is review material pending independent audit PASS, separate exact-commit User authorization, fast-forward, and remote-ref verification. After all four conditions, it is an integrated bounded code-authorization governance record only, and the canonical post-integration code status is `GRANTED_BOUNDED_FAIL_CLOSED_INTERNAL_SEAMS_ONLY`; `RUNTIME_APPROVED: NOT_APPROVED` remains. Integration does not assert that code has been written, pins/measurements resolved, the profile or global hash emitted, tests accepted, Gate B started/passed, or WP-04 closed. Current source-base statuses remain WP-04 `BLOCKED_BY_CONTRACT`; Gate A structural primitives `PASSED`; Gate B `NOT_STARTED`; WP-05 `OPEN`; `CODE_AUTHORIZATION: NOT_GRANTED`; `RUNTIME_APPROVED: NOT_APPROVED`.


### WP05-NAVIGATION-V1-RUNTIME-BINDING-REFRESH — PEP-001 rev.0.10.9 review snapshot

At exact integration base `16e4d81296f5db0fb322349bfe673cb5bd2c1534`, the refreshed WP-05 L2 target-binding candidate is being prepared on `wp05-navigation-v1-runtime-binding-refresh-16e4d812`. Source-content provenance is prior review commit `4ff6b96783c940e7f4c523ed553d3ad75f8a5a55` on `wp05-navigation-v1-runtime-binding-architecture-5249a11` (parent `5249a11e69408abf845e8568258989a70edefb35`) only; it is not current base/parent and is not considered integrated or audited here. Candidate-only/pending-audit status is tied to this refreshed source-base snapshot. The exact candidate becomes `ACTIVE_L2_NAVIGATION_V1_RUNTIME_BINDING_TECHNICAL_AUTHORITY_FOR_TARGET_BINDINGS_ONLY` only after independent audit PASS, separate explicit User authorization for its exact commit, fast-forward, and remote integration-ref verification; no separate activation candidate is required.

This L2 decision records target bindings only. `warehouse_map2` remains draft/not approved/not navigation-ready; `WORLD_FRAME: NOT_DECLARED`; `RUNTIME_COMPATIBILITY: NOT_VALIDATED`; no profile is resolved, no global `config_hash` exists, and Navigation V1 bring-up is not authorized. Required implementation source/package/version pins and measurements remain pending and fail closed. WP-05 remains `OPEN`; Gate B remains `NOT_STARTED`.

Current WP-04 status at this base is `BLOCKED_BY_CONTRACT`, Gate A `PASSED`, Gate B `NOT_STARTED`. `CODE_AUTHORIZATION: GRANTED_BOUNDED_FAIL_CLOSED_INTERNAL_SEAMS_ONLY` remains limited to typed internal structures, fail-closed validators, pure-core assembler/synchronizer seams, and dependency-injected internal boundaries. It does not authorize public ROS/runtime interfaces, Navigation configuration or bring-up, profile resolution, runtime, HIL, hardware, or deployment. `RUNTIME_APPROVED: NOT_APPROVED`. This WP-05 candidate does not broaden that authorization.

### WP04-OIC-V3-NONEXECUTING-OBSERVATION-INGRESS-SOURCE-AUTHORIZATION — PEP-001 rev.0.10.10

At exact source-base/review snapshot `346138368a5a3599779f36d629c6fc0e0233338a`, this four-path L1 governance candidate records a conditional extension of the existing bounded internal-seam code authorization. The current source-base status remains `CODE_AUTHORIZATION: GRANTED_BOUNDED_FAIL_CLOSED_INTERNAL_SEAMS_ONLY`; `RUNTIME_APPROVED: NOT_APPROVED`. Only after independent audit PASS for the exact candidate, separate exact-commit User authorization, fast-forward, and remote-ref verification does the status extend to `GRANTED_BOUNDED_FAIL_CLOSED_INTERNAL_SEAMS_AND_NONEXECUTING_OBSERVATION_INGRESS_ADAPTER_SOURCES_ONLY`. Review push and Git ancestry alone do not grant it.

The decision is bounded by the Architecture SHA-256 `432eeac363a595cfcf7e81c4b66054fb674dba140a2ef3cffecd617ab8136204`; OIC source SHA-256 `d44d33843c32d1f0d5c747522f3add09bfde21fcb0884e21da93a52476cb4dfc` and semantic-manifest SHA-256 `175a1af789b6641cfe455daeee8fedac80aaf80ad8c00792ba0a287c41acc0bb`; WP-04 runtime-binding semantic-manifest SHA-256 `e800f7169304624d81334c26a638c27c9cbaa11a6df0ba5531b1718ee914f76f`; WP-05 Navigation V1 runtime-binding ACR SHA-256 `3e74cdcb6136f60a6ad2822a853f2ae9926cf971059f3c2470c874802d6fae0d` and semantic-manifest SHA-256 `33855c9c95f9c0594ddd8805514658e4f5cb8255a219938a7913438470edbf31`; integrated pure-core source candidate `16e4d81296f5db0fb322349bfe673cb5bd2c1534`; and established receipt v2/QoS6 pins, all unchanged.

After the four conditions, source-level work may create nonexecuting observation-ingress adapter sources and related static/unit tests only under `ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/observations/` and `ros2_ws/src/mecanum_nav_rl/test/`; exact files still require a later code/source-closure candidate. `mecanum_nav_rl` remains the package owner. Typed ROS message objects may be accepted as inputs, but no node, executor, subscription, publisher, timer, service/action client, TF lookup/broadcast, launch, or runtime graph is allowed. The bounded targets and fail-closed rules are recorded in the companion decision; this governance candidate creates no source or test file.

**Critical path:** this L1 source authorization audit/decision/integration → exact path/source closure and separately scoped offline adapter implementation → code review and static/unit evidence → separately authorized runtime integration and evidence → later Gate B acceptance and HIL/hardware gates. This plan does not authorize or claim those downstream steps.

No resolved profile or global `config_hash` is produced; no package/version pin, measurement, map approval, or runtime evidence is added. No Gate B start/pass or WP-04 closure is claimed. WP-04 remains `BLOCKED_BY_CONTRACT`; Gate A structural primitives `PASSED`; Gate B `NOT_STARTED`; WP-05 `OPEN`; `RUNTIME_APPROVED: NOT_APPROVED`. Before integration, the source-base code token remains the internal-seams-only token; after all four exact-candidate conditions it is the extended nonexecuting-source token above.


### WP05-NAVIGATION-V1-DEPENDENCY-LOCK-AND-STATIC-BRINGUP-SOURCE-AUTHORIZATION — PEP-001 rev.0.10.11 review snapshot

At exact integration base `2a537a9cfa9f9c5b0bec1f9c629fec8e2f98a225`, this five-path L1 governance candidate defines the future Navigation V1 dependency-lock schema and the bounded future source layout/ownership of `mecanum_nav_bringup`. It creates no package, source, launch, runtime YAML, package/version lock, resolved profile, profile hash, map approval, or runtime evidence. Candidate-only status applies to this exact source-base review snapshot and remains pending independent audit, separate explicit User authorization for the exact commit, fast-forward, and remote-ref verification.

The current authorization before this candidate's integration is `CODE_AUTHORIZATION: GRANTED_BOUNDED_FAIL_CLOSED_INTERNAL_SEAMS_AND_NONEXECUTING_OBSERVATION_INGRESS_ADAPTER_SOURCES_ONLY`; `RUNTIME_APPROVED: NOT_APPROVED`. After all exact-candidate conditions, the conditional authorization is `CODE_AUTHORIZATION: GRANTED_BOUNDED_FAIL_CLOSED_INTERNAL_SEAMS_NONEXECUTING_OBSERVATION_INGRESS_AND_STATIC_NAVIGATION_V1_BRINGUP_SOURCES_ONLY`; `RUNTIME_APPROVED: NOT_APPROVED`. The extension permits static bringup source and static acceptance tests only in the decision's exact layout. It does not permit running launch/ROS/Nav2/AMCL/EKF/Gazebo, creating a runtime graph, resolving a profile/hash, approving a map, or HIL/hardware/deployment.

Dependency roots are fixed by the schema. Concrete external package locks remain `PENDING_EXTERNAL_PACKAGE_LOCK`; workspace package/config/launch sources remain `PENDING_IMPLEMENTATION_SOURCE_PIN`. The static test list is an expectation for a later authorized code candidate, not test evidence from this candidate. Missing required lock/pin/measurement/evidence fails closed with no resolved profile, global `config_hash`, or Navigation bring-up.

`mecanum_nav_bringup` is absent at the source base. WP-05 remains `OPEN`; `warehouse_map2` remains draft, not approved or navigation-ready; `WORLD_FRAME: NOT_DECLARED`; `RUNTIME_COMPATIBILITY: NOT_VALIDATED`. WP-04 remains `BLOCKED_BY_CONTRACT`; Gate A `PASSED`; Gate B `NOT_STARTED`.

### WP04-WP05 runtime measurement plan and evidence schema — PEP-001 rev.0.10.12 source-base snapshot

At exact integration/source base `cc0018560b20a52fa6d3c9cf26abbe0ef4c6227a`, the L1 measurement-governance decision and packet schema are review-candidate snapshots. They do not constitute runtime evidence or runtime-binding authority. Only after independent audit PASS for the exact candidate, separate exact-commit User authorization, fast-forward, and remote-ref verification may they be described as `INTEGRATED_L1_RUNTIME_MEASUREMENT_GOVERNANCE_PLAN_ONLY`.

Planning route only: integrate the measurement plan/schema → obtain a separate L1 authorization for any passive collector → establish required immutable source/package pins and measurements → gather exploratory evidence where useful → obtain separately authorized acceptance-grade collection and gate-specific review. This plan does not authorize a harness, set thresholds, resolve a profile or global `config_hash`, approve a map, change WP status, or grant runtime authority. If a future harness changes TF ownership, lifecycle, safety, public interface, or `config_hash` semantics, stop for L2 change-control. WP-04 remains `BLOCKED_BY_CONTRACT`; Gate A `PASSED`; Gate B `NOT_STARTED`; WP-05 `OPEN`; `warehouse_map2` remains draft/not approved; `WORLD_FRAME: NOT_DECLARED`; `RUNTIME_COMPATIBILITY: NOT_VALIDATED`; the current code-authorization token is unchanged; `RUNTIME_APPROVED: NOT_APPROVED`.

### WP04-WP05 measurement evidence schema F-01 correction — PEP-001 rev.0.10.13 review snapshot

The source-parent review candidate is `5b8ac68f51814f9520e1e72a28da5ad35fcfacea` at integration base `cc0018560b20a52fa6d3c9cf26abbe0ef4c6227a`. `F-01` is `USER_SUPPLIED_INDEPENDENT_AUDIT_EVIDENCE`; no report hash is claimed. The correction places `minItems: 1` on the acceptance-conditional `metrics_inventory` array; schema ID/revision remain unchanged. This is a review snapshot, not active L2 authority. After audit PASS for the exact correction, separate exact User authorization, fast-forward, and remote-ref verification only, the records are `INTEGRATED_L1_RUNTIME_MEASUREMENT_GOVERNANCE_PLAN_ONLY`. No plan, ownership, pin, threshold, harness, measurement, profile, `config_hash`, status, or authorization changes; `RUNTIME_APPROVED: NOT_APPROVED` remains.

### WP05-NAVIGATION-V1-DEPENDENCY-LOCK-PROVENANCE-ENVELOPE-L2-AMENDMENT-CORRECTED — review snapshot

At exact source base `f23af59d7a9458175928c2647532339ff933158b`, the dependency-lock schema revision 2 amendment and validator/test correction are review material. The typed `artifact_baseline_provenance` envelope is required and closed to unknown fields. The existing 14 logical roots remain unchanged; `launch_ros` remains outside that set. No concrete lock instance, static profile source, package pin, runtime behavior, map approval, profile resolution, or `config_hash` is created.

The amendment becomes active authority only for dependency-lock provenance schema semantics after independent audit PASS for the exact candidate, separate exact-commit User authorization, fast-forward, and remote-ref verification. Structural validation is offline and does not inspect or prove external artifact existence. WP-05 remains `OPEN`; map approval and runtime status are unchanged; `RUNTIME_APPROVED: NOT_APPROVED`. WP-04 remains unchanged and Gate B remains `NOT_STARTED`.

### WP05-CONCRETE-14-ROOT-EXTERNAL-DEPENDENCY-LOCK-RECORD — review snapshot

At exact source base `ab5c62f866985b72cbaff370fae38cdd6192dbcc`, the six-path L1 candidate adds a schema-v2 JSON record for exactly the 14 logical external dependency roots, plus its decision, Registry/PEP routing, focused static test, and append-only Ledger entry. Package `.deb` hashes and the closure manifest were checked against the external baseline; the record's `source_commit` `f23af59d7a9458175928c2647532339ff933158b` is collection provenance, not this candidate's integration base. The external locator is evidence location only.

The record intentionally has no workspace-source locks. It must not be used as a complete runtime-validator input: the ten required workspace roles are still missing, and the validator rejects the empty lock list. This review candidate does not create a static profile source, workspace-source pins, profile resolution, `config_hash`, map approval, or runtime evidence. After audit PASS for the exact candidate, separate exact-commit User authorization, fast-forward, and remote-ref verification, it may be described only as an integrated external dependency-lock record. WP-05 remains `OPEN`; map remains draft/not approved; `WORLD_FRAME: NOT_DECLARED`; `RUNTIME_COMPATIBILITY: NOT_VALIDATED`; `RUNTIME_APPROVED: NOT_APPROVED`; WP-04 remains `BLOCKED_BY_CONTRACT`; Gate B remains `NOT_STARTED`.
### WP04-WP05 shared LiDAR frame and TF/RSP ownership — review snapshot

At exact source base `de71ae4d4ecb86724b1a02bdccad6f70315de7bc`, the shared L2 candidate records the User-supplied decision that literal `lidar_frame` is the public frame identity and `robot_state_publisher` is sole target owner of `base_link → lidar_frame`. Before exact-candidate independent audit PASS, separate User authorization, fast-forward, and remote-ref verification, it remains review-only. Those conditions would activate only `ACTIVE_L2_SHARED_TF_RSP_GOVERNANCE_FOR_FRAME_ID_AND_OWNERSHIP_ONLY`; they do not provide runtime authorization, runtime evidence, source pin, or geometry verification.

Next WP-04/WP-05 dependency: design a separate canonical RSP description source, select the extrinsic using appropriate measurement evidence, then close its exact source pin. The legacy `RPLiDAR_A1M8_1` fixed-joint transform remains `PENDING_MEASUREMENT_AND_CANONICAL_SOURCE_SELECTION`; do not reuse its geometry as canonical. Until the canonical source pin, verified extrinsic evidence, literal scan frame, and sole-owner conditions are satisfied, fail closed: no Navigation V1/Observation V3 profile resolution, global `config_hash`, Nav2 baseline, Observation V3 runtime vector, or Gate B start/pass. No implementation or runtime activity is authorized here.

WP-04 remains `BLOCKED_BY_CONTRACT`; Gate A `PASSED`; Gate B `NOT_STARTED`; WP-05 `OPEN`; map remains draft/not approved; `WORLD_FRAME: NOT_DECLARED`; `RUNTIME_COMPATIBILITY: NOT_VALIDATED`; `RUNTIME_APPROVED: NOT_APPROVED`.
### WP-04/WP-05 canonical RSP description source creation — conditional L1 authorization review snapshot

At exact base `fa862f26eed6cfa30a553ccf6f1befcad532a1f9`, this candidate records conditional authorization for a later canonical robot-description source within the integrated L2 `base_link → lidar_frame` semantics. It is review-only pending independent audit PASS for this exact candidate, separate User authorization, fast-forward, and remote-ref verification. If integrated after those conditions, it permits only the four future source paths in the decision, and only after an Owner-approved extrinsic evidence packet exists. It creates no source, source pin, geometry verification, profile, `config_hash`, runtime evidence, or runtime authorization.

Required next-step order after integration: (1) collect and obtain explicit Owner acceptance of the complete extrinsic evidence packet; (2) create a source candidate in the exact four allowed paths; (3) independently audit and separately authorize/integrate that source candidate; (4) close its exact source pin; (5) perform runtime TF measurement only under separate runtime authorization. Missing packet fields or acceptance means no source edits and fail-closed behavior. Legacy `RPLiDAR_A1M8_1` geometry is not reusable as canonical extrinsic.

No status changes: WP-04 remains `BLOCKED_BY_CONTRACT`; Gate A `PASSED`; Gate B `NOT_STARTED`; WP-05 `OPEN`; map remains draft/not approved; `WORLD_FRAME: NOT_DECLARED`; `RUNTIME_COMPATIBILITY: NOT_VALIDATED`; `RUNTIME_APPROVED: NOT_APPROVED`.


## WP-04 YDLIDAR X3 Pro static simulation scan authorization — review snapshot

After the existing canonical RSP source-pin closure, the next eligible step is review of this bounded L1 authorization candidate, followed (only after its independent audit PASS, separate exact-commit User authorization, fast-forward, and remote-ref verification) by a separate static-source candidate limited to the Gazebo description and its focused static contract test. That future candidate may use the pinned vendor row and stated static 6.0 Hz / 500-sample derivation. It must not create a ROS bridge or runtime graph. Keep driver/bridge/profile pins and cadence, latency/freshness, no-return, and hardware-as-built measurements pending.


## WP00 — post-integration static status reconciliation at `9f2762d875024df927aa581580e746bc35436e80`

This reconciliation records the current Git integration state: WP-04 `e9695d21fb2d9c76fe7e35f0081f648bc401fe51` is the direct parent of WP-05 `9f2762d875024df927aa581580e746bc35436e80`. WP-04 is `INTEGRATED_L1_STATIC_SIMULATION_SCAN_SOURCE_CREATION_AUTHORIZATION_ONLY`, bounded to authorizing a future static Gazebo LiDAR source candidate in exactly the Gazebo description and its focused static contract-test paths. It does not provide a runtime source pin, ROS bridge, profile, runtime evidence, or runtime authorization.

WP-05 is `INTEGRATED_STATIC_TEMPLATE_SOURCES_ONLY` and consists of the AMCL, EKF, localization-lifecycle static templates, their static-source test, and package-data registration in `setup.py`. It is not a workspace-source-role pin, runtime source pin, resolved-profile input, map approval, runtime evidence, runtime authorization, resolved profile, or `config_hash`. No independent WP-05 pre-integration audit is asserted here; the record is a post-integration static reconciliation only. Git ancestry establishes ordering and content presence, not audit, runtime evidence, or authorization.

Prospective next-step order: (1) this L1 post-integration reconciliation; (2) a WP-04 static Gazebo LiDAR source candidate limited to its authorized two paths; (3) WP-05 source-role/profile closure preparation; (4) each subsequent candidate starts from the then-exact integration tip and follows its own review/integration process. These are planned steps, not completed work. The older historical snapshot's “canonical RSP source design” next-step wording is superseded for current routing because the canonical RSP source and source-provenance closure are already integrated.

No technical or authorization transition is recorded. Status remains `WP-04: BLOCKED_BY_CONTRACT`; `GATE_A_STRUCTURAL_PRIMITIVES: PASSED`; `GATE_B: NOT_STARTED`; `WP-05: OPEN`; `MAP_ARTIFACT: DRAFT_ON_INTEGRATION_NOT_APPROVED`; `WORLD_FRAME: NOT_DECLARED`; `RUNTIME_COMPATIBILITY: NOT_VALIDATED`; `RUNTIME_APPROVED: NOT_APPROVED`; `YDLIDAR_X3_PRO_RUNTIME_SOURCE_PIN: PENDING`; `ROS_GAZEBO_SCAN_BRIDGE_SOURCE_PIN: PENDING`; `SCAN_RUNTIME_PROFILE: PENDING`.

### WP05-NAVIGATION-V1-WORKSPACE-SOURCE-ROLE-INVENTORY — routing only

At exact source-base snapshot `c59d9ea65010ff80eb0202bfaa5220c5f18f25ac`, the source-role inventory and decision packet are L1 governance review candidates. They classify evidence references and route the ten outstanding workspace roles; all remain `PENDING_IMPLEMENTATION_SOURCE_PIN` and `NOT_SELECTED`. This is not source selection and does not populate `workspace_source_locks` or alter the external dependency lock. Only after independent audit PASS for the exact candidate, separate exact-commit User authorization, fast-forward, and remote-ref verification may the records be described as an integrated inventory governance record. This PEP routing note does not change critical path, WP status, authorization, map state, profile/config-hash boundary, or runtime evidence. Missing required source/evidence remains fail-closed; no resolved Navigation V1 profile, global `config_hash`, Nav2 baseline bring-up, or runtime authorization follows from this inventory.


### WP05 warehouse_map2 sim_eval static approval evidence — Candidate 4A routing

Candidate 4A is an approval-evidence decision for the exact `warehouse_map2` artifact selection under `SIM_EVAL_NAV2_BASELINE_STATIC_MAP_ARTIFACT_SELECTION`. It does not update artifact metadata, activate map approval, or select/resolve a runtime profile. The record is review-only until independent audit PASS, separate exact-candidate User authorization, fast-forward integration, and remote-ref verification. Candidate 4B depends on the exact integrated commit of Candidate 4A and may separately update metadata from `draft` to `approved`; any world-frame metadata change remains a separate explicit action referencing the existing declaration evidence. No Map Server load, runtime authority, profile resolution, `config_hash`, or WP-05 closure follows from Candidate 4A.


### WP05 sim_eval + NAV2_BASELINE static profile input closure — Step 5A routing

Candidate `wp05-sim-eval-static-profile-closure-2864a21` records only static profile inputs at exact base `2864a215782cc1901aa259a49d885fa0c132cf7a`. It is review-only pending exact-candidate audit, separate User authorization, fast-forward integration, and remote-ref verification. After those conditions, the result is a static input closure, not a resolved runtime profile. `warehouse_map2` is approved only for the static selection scope; `WORLD_FRAME: DECLARED_UNVERIFIED`; runtime compatibility remains `NOT_VALIDATED`. No workspace source-role locks are created, and the ten runtime roles are not inferred to be pinned. WP08 remains a static bridge boundary; neither a `ros_gz_bridge` implementation nor endpoint is selected, and Gazebo transport is not inferred to be ROS `/scan`. Existing launch files remain fail-closed. WP06 and runtime assembly remain prerequisites before a separately authorized campaign. No `ResolvedConfigV3`, `config_hash`, Map Server load, launch graph, runtime evidence/authorization, or WP-05 closure is claimed. WP-04/WP-05 and Gate A/Gate B statuses remain unchanged.


### WP06 receipt v2 ROSIDL generation — atomic L2 decision, review routing

This atomic candidate combines the bounded L2 disposition of historical receipt-source annotations with the additive ROSIDL build-interface declaration for the existing receipt v2 message. The decision and evidence record remain review candidates on exact base `c8b178a2f1feee115a3a01553afaec616cabf737` until independent audit PASS, separate User authorization for the exact commit, fast-forward integration, and remote-ref verification.

Only after those conditions, record `WP06_RECEIPT_V2_ROSIDL_GENERATION: IMPLEMENTED_OFFLINE_BUILD_INTERFACE_ONLY`. `DRAFT` remains a historical annotation and never downgrades the established canonical receipt; “Not installed in a ROSIDL package” is superseded only for ROSIDL build generation. Receipt schema bytes/ID/revision, QoS6, and dependency closure remain unchanged. Runtime producers/consumers, node, publisher/subscriber, topic, runtime QoS/evidence, `ResolvedConfigV3`, `config_hash`, Gate B, and runtime authorization remain outside scope; `RUNTIME_APPROVED: NOT_APPROVED`.


### WP05 warehouse_map2 static approval metadata activation — candidate routing

This review candidate proposes to activate only the existing approval evidence for the exact `warehouse_map2` subject and reference the existing world declaration evidence. If this candidate passes audit, receives separate User authorization, is fast-forward integrated, and its remote ref is verified, metadata will be `approval_status: approved` only for `SIM_EVAL_NAV2_BASELINE_STATIC_MAP_ARTIFACT_SELECTION` and `world_frame.state: DECLARED_UNVERIFIED`; runtime compatibility remains `NOT_VALIDATED`. This makes the map eligible as a static profile input for Step 5, not a resolved profile or navigation-ready artifact. Earlier draft/`NOT_DECLARED` statements remain historical snapshots and are superseded only as current metadata wording. Future Map Server binding is limited to `artifacts/maps/warehouse_map2/map.yaml`. No Map Server load, AMCL/TF/runtime evidence, map/world equivalence, runtime authority, profile resolution, `ResolvedConfigV3`, `config_hash`, or WP-05 closure follows. WP-04/WP-05 and Gate A/Gate B statuses remain unchanged.


### WP06 command safety core — jerk-envelope corrected candidate routing

Candidate `wp06-command-safety-core-jerk-envelope-fix-d0b1234` is independently based on exact base `d0b1234f1c23961c5dd7c04a35c9ec39d6077629` and does not reuse either rejected candidate `a3c9f7074f96a2d5632bb1cddd3ecffb18e1c58a` or `89f064af2af1afbc86cf9e10eb43c974709ae1e0`. It retains F-01/F-02/F-03 and corrects F-04 using the per-axis intersection of acceleration, jerk centered on previous acceleration, and hard-velocity-derived acceleration intervals. Empty intersections fail to `FAULT` + zero and clear command identity; there is no post-limit velocity clipping.

This remains a pure offline decision core and offline test candidate. Only after independent audit PASS for the exact commit, separate User authorization for that exact commit, integration, and remote-ref verification may the status be recorded as `WP06_COMMAND_SAFETY_CORE: IMPLEMENTED_OFFLINE_ONLY`. No runtime SafetySupervisor, ROS node/graph, `FinalTwistPublisher`, `/cmd_vel` publisher, receipt runtime, collision/TTC, physical E-stop integration, profile, `ResolvedConfigV3`, `config_hash`, runtime evidence, Gate B transition, or runtime authorization is created. Motion limits remain injected and unpinned; `RUNTIME_APPROVED: NOT_APPROVED` and WP-04/WP-05/Gate A/Gate B statuses remain unchanged.

### WP06 sim_eval wheel/IMU ingress — ROSIDL sequence correction routing

The replacement candidate is constructed directly from exact integration base `43c94789f628b4211189fc391326e0b119cbb6d3`, without using either rejected candidate (`38d52b19b8cacecbe49961f77df47eaacfd8c3c4` or `3f40b6dcf34e07f9f9df33889df2c9379163d3fd`). It preserves the invalid-wheel-interval barrier (F-01) and the effective sim-time guard before endpoint creation (F-02), and corrects F-03 by accepting ROSIDL `array('d')` through the indexed `Sequence` protocol while rejecting generators and strings. Earlier list-only fixtures did not establish actual ROSIDL sequence compatibility.

This is source plus offline test/build evidence only; `runtime_eligible: false`. WP06-6E remains sole owner of bridge implementation. The branch is review-only. Only after exact-candidate independent audit PASS, separate User authorization, integration, and remote-ref verification may a later status record say `WP06_SIM_EVAL_WHEEL_IMU_RUNTIME_INGRESS: IMPLEMENTED_OFFLINE_ONLY`. No ROS/Gazebo runtime, bridge, TF publisher, `/cmd_vel`, runtime evidence/authorization, Gate B transition, or WP-04/WP-05/Gate A/Gate B status change is claimed. `RUNTIME_APPROVED: NOT_APPROVED`.


### WP06 sim_eval wheel/IMU ingress — corrective review commit (F-04)

Corrective commit parent `4ccb0491408c8b8bfbf0c34f5cb33329ec9979c6` addresses F-04 `ROLLBACK_TIMESTAMP_PRECEDENCE` on the existing review candidate branch; this is not a new candidate from integration. A valid backward timestamp is extracted and handled before wheel payload access and immediately resets pose/baseline, even when the payload is malformed. F-01/F-02/F-03 are retained. Final review HEAD remains offline evidence only, `runtime_eligible: false`; WP06-6E remains sole bridge owner. No runtime evidence or authorization is implied, `RUNTIME_APPROVED: NOT_APPROVED`, and WP-04/WP-05/Gate A/Gate B remain unchanged.


### WP05 static profile current Gazebo source-pin reconciliation — review routing

The exact-base check at `4f491edca1d46dee259d57350ad520a0334e4049` found a pre-existing provenance drift: current Gazebo source SHA `1e97b6ea340adc9aecaf320cc432007c6bb37f5922cdc0366dbee50a9a26ff0e` versus Step 5A current-descriptor SHA `a97b092f7343d04679ed1417539e47d217b20d18afc3364a27cf14110d9dece8`. This candidate changes only `source_commit` and the `gazebo_lidar_source` SHA in the profile YAML, Python descriptor and manifest. Historical inventory is retained unchanged. Following exact-candidate audit PASS, separate User authorization, integration and remote-ref verification, the static input closure is self-consistent again; it remains non-runtime and unresolved. No endpoint/bridge/runtime pin, profile resolution, `ResolvedConfigV3`, `config_hash`, runtime evidence, or runtime authorization follows. WP-05 stays `OPEN`, WP-04 `BLOCKED_BY_CONTRACT`, Gate A `PASSED`, Gate B `NOT_STARTED`, and `RUNTIME_APPROVED: NOT_APPROVED`.


### WP06 sim_eval Scan endpoint probe — review routing

The exact-base candidate `wp06-sim-eval-scan-endpoint-probe-46be7a2` (`46be7a2bde222475fbaaaac8a6749211edfd2ba0`) prepares an offline-tested topic discovery source only. The declared relative sensor topic `scan` is not treated as the full Gazebo endpoint. The source is not executed; it creates no endpoint pin or bridge implementation. A future run requires an explicit capacity-one `APPROVED_RUNTIME` packet, exact command, pass/fail and stop conditions, and User approval. The observation must receive a separate Owner decision before WP06-6E, which remains the sole canonical ROS–Gazebo bridge owner. No ROS `/scan` publisher, TF, runtime evidence/authorization, profile resolution or Gate B transition follows. Existing WP-04/WP-05/Gate A/Gate B and `RUNTIME_APPROVED: NOT_APPROVED` statuses remain unchanged.
### WP06 sim_eval Scan endpoint probe runtime bootstrap and capacity-one guard — review candidate

This independently constructed L2 candidate at exact base `bfc1ef3cfe4ba98beefbe7f18607b97a41e52d15` implements offline-only bootstrap and guard source. The bridge-free bootstrap sets the exact partition `wp06_scan_probe_run_001` before Gazebo include, starts one RSP for static robot description ownership, includes one Gazebo simulation and creates one exact-name entity. The capacity-one seed remains `PENDING_EXACT_INTEGRATION_AND_USER_AUTHORIZATION`.

The future supervisor cannot consume this guard from a review checkout. It requires the caller's exact 40-character integrated commit, matching `HEAD` and `origin/integration/implementation`, the authority packet byte SHA, integrated guard/supervisor seed blobs, source pins, exact command and partition, and a new run directory. This candidate neither executes the probe nor establishes a runtime result. After independent audit, exact integration, remote-ref verification, and separate exact-commit User authorization, it may be described only as `RUNTIME_GUARD_IMPLEMENTED_AWAITING_EXACT_USER_AUTHORIZATION`. Any observed endpoint remains `OBSERVED_NOT_PINNED` and needs Owner decision before WP06-6E. Existing WP-04/WP-05, Gate A/Gate B and `RUNTIME_APPROVED: NOT_APPROVED` statuses remain unchanged.


## WP06 sim_eval scan endpoint probe — deterministic bootstrap remediation L2 review candidate

At exact base `be5f63e7a01be0bca0b838e1ae5265bbb7145be8`, this review candidate adds a local Fuel-free probe world and deterministic server-only bootstrap for Run 002. The world contains only the requested Gazebo systems and inline ground plane; it does not replace `tugbot_depot.sdf` and makes no navigation-fidelity or Nav2-readiness claim. The launch unconditionally sets `GZ_PARTITION=wp06_scan_probe_run_002`, explicitly targets `wp06_scan_probe_world`, and has no fixed-delay readiness substitute.

Run 001 remains byte-identical and pending at the source base. Conditional on integration of this exact candidate, its old source/partition context becomes `NOT_CONSUMED_AND_INVALIDATED_BY_EXACT_INTEGRATION_MISMATCH`. Run 002 is future-only, capacity one and `PENDING_EXACT_INTEGRATION_AND_USER_AUTHORIZATION`; this review candidate does not authorize runtime. A future run requires exact integrated commit, clean worktree, pending guard, and the exact create log `Entity creation successful.` before a compatible supervisor can be called once. A consumed guard cannot be retried.

No endpoint pin, ROS `/scan`, bridge, TF evidence, runtime evidence/authorization, resolved profile, `ResolvedConfigV3`, `config_hash` or Gate B transition is created. WP06-6E remains sole owner of the canonical ROS–Gazebo bridge. WP-04 `BLOCKED_BY_CONTRACT`, WP-05 `OPEN`, Gate A `PASSED`, Gate B `NOT_STARTED`, and `RUNTIME_APPROVED: NOT_APPROVED` remain unchanged.

### Corrective review commit — Run 002 completion

The existing review candidate receives one corrective commit from parent `97aeecdff640187ac0b3ad152a22befe442a1a2f`. Run 002's independent guard/supervisor pair is implemented offline and remains pending, not runtime-authorized. Exact integration/source checks and a clean checkout precede guard consumption; future bootstrap readiness requires the literal `Entity creation successful.`. Run 001 files remain byte-identical with the parent. The probe world gravity placement is corrected to direct world scope. No runtime was executed and no endpoint, bridge, ROS `/scan`, TF evidence, runtime evidence/approval, `ResolvedConfigV3`, `config_hash` or Gate B transition is created. `RUNTIME_APPROVED: NOT_APPROVED` and existing WP/Gate statuses do not change.
