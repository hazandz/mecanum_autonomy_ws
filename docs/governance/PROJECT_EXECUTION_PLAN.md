# Project Execution Plan — Mecanum Nav2 DRL

## Metadata

| Field | Value |
|---|---|
| Plan ID | `PEP-001` |
| Revision | `0.10.16` Run005 attempt_002 QoS source-freeze review snapshot |
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


### WP06 scan-probe observability and teardown remediation — Run 003 routing

Candidate `wp06-scan-probe-observation-teardown-b15e0fd` is based on exact integration base `b15e0fd6e83f840822b8ba11f68dbdf31de0978e`. It updates the offline probe parser to inspect only absolute topics with exact leaf `scan`, recognize the legacy type line and Harmonic publisher-section grammar, exclude subscriber-only matches, and write raw command transcripts with hashes/sizes under a future run directory. Transcript streams are capped at 1,048,576 bytes and candidate topics at 16; overflow fails closed.

The independent Run 003 bootstrap and session runner use a pending capacity-one guard, exact integrated source/authority checks, readiness only on `Entity creation successful.`, one probe invocation, and process-group teardown with fixed SIGINT/SIGTERM/SIGKILL escalation. This is source plus offline tests/build only; the guard remains `PENDING_EXACT_INTEGRATION_AND_USER_AUTHORIZATION`. Run 002 is outside scope and untouched. A future exact observation is `OBSERVED_NOT_PINNED`; no bridge, ROS `/scan`, TF, runtime evidence/authorization, profile resolution, `ResolvedConfigV3`, `config_hash`, Gate B transition, or runtime approval is created. WP-04 remains `BLOCKED_BY_CONTRACT`; WP-05 `OPEN`; Gate A `PASSED`; Gate B `NOT_STARTED`; `RUNTIME_APPROVED: NOT_APPROVED`.


### Run 003 corrective candidate — publisher grammar F-01

The corrective review commit updates the probe parser to accept only the unbracketed Harmonic address/type entry inside the publisher section. It rejects bracketed and malformed publisher entries, does not count subscriber-only `gz.msgs.LaserScan`, and returns a distinct fail-closed outcome for a valid non-scan publisher type. The prior review tip was not integrated and has no runtime authorization. Run 003 requires audit PASS, exact integration and a new capacity-one authorization. This is offline source/test/build evidence only; no runtime execution or endpoint pin.


## WP06 6D scan probe Run 004 — readiness and teardown remediation (review candidate)

At exact base `db464f741e24a81b3f9587f827fc145c533d8d6c`, this candidate prepares source and offline checks for Run 004. The server-only launch sets `GZ_PARTITION=wp06_scan_probe_run_004`, uses the existing local probe world, starts `robot_state_publisher`, and does not spawn. The future runner gates spawn on the exact Gazebo create service, then requires create exit code zero plus the exact `Entity creation successful.` transcript bytes before probing once. Bootstrap and create output are written directly to files; readiness is not parsed from buffered bootstrap pipes. Teardown reaps the direct child and records exact process-group live/zombie members from `/proc`.

Run 002 and Run 003 remain immutable historical evidence and are untouched. The Run 004 capacity-one guard is pending and unconsumed. This review candidate did not run ROS/Gazebo/`gz`, launch, probe, or supervisor and creates no runtime evidence. Any future runtime requires independent audit, exact candidate integration and remote-ref verification, then separate Owner authorization for the exact integrated commit. Even a future exact probe match is only `GZ_LASERSCAN_ENDPOINT_OBSERVED_NOT_PINNED`; it does not establish ROS `/scan`, a bridge, TF, runtime compatibility, `ResolvedConfigV3`, `config_hash`, Gate B, or runtime approval. WP-04 remains `BLOCKED_BY_CONTRACT`, WP-05 `OPEN`, Gate A `PASSED`, Gate B `NOT_STARTED`, and `RUNTIME_APPROVED: NOT_APPROVED`.


## WP06 6D scan probe Run 005 — Harmonic topic-info parser correction (review candidate)

The existing Run 005 review candidate receives a parser-only correction for
the observed Gazebo Harmonic topic-info output. The parser accepts one exact
`gz.msgs.LaserScan` publisher record and the `No subscribers on topic [/scan]`
footer, and fails closed for missing, malformed, wrong-type, subscriber-only,
or ambiguous publishers. The recorded raw 111-byte transcript is replayed
offline; the corrected result is `GZ_LASERSCAN_ENDPOINT_OBSERVED_NOT_PINNED`.

Run 005 itself was already invoked once on parent
`20814c9009cee588f6b330ee227f69d886949593`. Its immutable historical terminal
outcome remains `PROBE_NOT_EXACTLY_ONE_MATCH`; the host runtime authorization
was consumed. The source guard's pending state is only its Git seed and does
not permit rerunning Run 005. No runtime retry is performed or authorized.

This correction is parser source and offline-test evidence only. The run record
is not edited; no ROS `/scan`, bridge, TF, endpoint pin, profile resolution,
`ResolvedConfigV3`, `config_hash`, Gate B transition, or runtime approval is
created. WP-04 `BLOCKED_BY_CONTRACT`, WP-05 `OPEN`, Gate A `PASSED`, Gate B
`NOT_STARTED`, and `RUNTIME_APPROVED: NOT_APPROVED` remain unchanged.


## WP06 profile-specific ROS–Gazebo scan bridge — review candidate

The review candidate based on `abcdffb4d1683c6b337b7c8a8916d0c9317d111e` implements one `GZ_TO_ROS` `/scan` mapping (`gz.msgs.LaserScan` → `sensor_msgs/msg/LaserScan`) through `ros_gz_bridge/parameter_bridge`. Its YAML and launch are installed by the bringup package; launch defaults `GZ_PARTITION` to `sim_eval` and enforces `use_sim_time: true`.

Evidence ceiling for this correction is source, offline tests and build only. Historical Runtime Run 001 passed ROS `/scan` existence/type, one data publisher, non-empty ranges, and clean teardown; `/parameter_events` and `/rosout` are standard ROS node endpoints. Its sole audited failure was source-owned `LaserScan.header.frame_id` (`ROBOT_URDF_final/base_link/YDLIDAR_X3_PRO` instead of `lidar_frame`). Runtime Run 002 remains `WP06_6E_RUNTIME_FRAME_CONTRACT_FAIL_NO_RETRY`; both historical records remain unchanged and no retry is performed. This correction retains `<frame_id>lidar_frame</frame_id>` and adds `<gz_frame_id>lidar_frame</gz_frame_id>` to the same Gazebo sensor. The exact new Gazebo source SHA-256 `9ff2dd9578b069cc492c9ff05e7f7f0d952c8bad0c5ecd9710ccea63d9fb1bbd` is reconciled only in the current static-profile YAML, Python descriptor and WP-05 static-profile manifest; historical inventory and WP-05 lock are unchanged. The bridge does not rewrite headers. A new capacity-one runtime requires independent audit and separate Owner authorization for the exact corrective commit. Runtime compatibility remains `NOT_VALIDATED`; no endpoint pin, new runtime evidence, profile resolution, `ResolvedConfigV3`/`config_hash`, Gate B transition, or runtime approval is created. WP-04/WP-05/Gate A/Gate B and `RUNTIME_APPROVED: NOT_APPROVED` remain unchanged.


### WP06-6E dependency-lock scope correction

The external WP-05 lock remains exactly the 14 common Navigation V1 roots. The `sim_eval` bridge's `ros_gz_bridge`, `launch`, and `launch_ros` entries are profile-specific runtime dependencies and remain outside both WP-05 lock files. The package declares all 17 exec dependencies in the required order, while the offline dependency-lock test validates common and profile-specific lists independently. No lock expansion, runtime validation, or runtime approval occurs.


## WP06-6E Run 003 runtime evidence disposition — L1 candidate

The integrated source is `8bd998d6c118239d70f1d4a7b73e145795e8f921`. Independent read-only audit of external Run 003 raw evidence passed for the scan-bridge scope: ROS `/scan` type `sensor_msgs/msg/LaserScan`, one data publisher, bridge-node publishers `/scan`, `/parameter_events`, `/rosout`, no forbidden odometry/command/TF/map publishers, `header.frame_id=lidar_frame`, 129 non-empty ranges, and clean teardown with no live/zombie process members. The original run record remains immutable with historical terminal `WP06_6E_RUNTIME_DUAL_FRAME_CONTRACT_FAIL_NO_RETRY`; its YAML multi-document and node-info indentation parsing defects explain the mismatch. Raw files were independently hashed and parsed; the reconciliation addendum does not replace them, and Run 003 was not replayed. Run 001/002 remain historical failures.

Current WP06-6E status: `WP06_6E_SCAN_BRIDGE_RUNTIME_OBSERVED_AND_AUDITED_PASS`, restricted to scan-bridge runtime scope. This is not whole navigation profile validation. `RUNTIME_APPROVED: NOT_APPROVED`; `GATE_B: NOT_STARTED`. No endpoint pin, TF evidence, profile resolution, `ResolvedConfigV3`, `config_hash`, runtime approval, or Gate B transition is created.


## WP06-6C sim_eval wheel/IMU runtime ingress activation — L2 review candidate

This candidate at exact base `bd749560e50e11963873c33a51f806e420c38392` adds the GZ-to-ROS staging mappings for wheel `gz.msgs.Model` on `/joint_states` and IMU `gz.msgs.IMU` on `/sim_eval/imu/raw`, feeding only `/sim_eval/wheel_joint_states` and `/sim_eval/imu_raw` into the existing ingress node. That node retains its existing derived `/wheel/odometry_raw` and normalized `/imu/data` outputs. The dedicated launch starts only the bridge and ingress nodes; it enforces `GZ_PARTITION` from `gz_partition` and effective `use_sim_time=true`. The IMU sensor's direct `frame_id` and `gz_frame_id` are both `base_link`; existing geometry, timing, covariance and core behavior are retained.

The Gazebo source SHA changes from `9ff2dd9578b069cc492c9ff05e7f7f0d952c8bad0c5ecd9710ccea63d9fb1bbd` to `7bbaa475578600d8e18e437fa83720483b90b4af2bf4212151257152429576a2`. Only current WP-05 static-profile YAML/contract/manifest provenance is reconciled. WP05 lock, historical inventory and static-policy manifest are unchanged. WP06-6E Run 003 remains historical, immutable evidence from its prior source hash; its scan-bridge-only audited status is not altered or contradicted.

Evidence status is `IMPLEMENTED_OFFLINE_BRIDGE_AND_INGRESS_SOURCE_ONLY`; `runtime_eligible: false`; `runtime_evidence_status: NOT_CREATED`. No Gazebo odometry or Ground Truth input is bridged, and no TF, EKF, Nav2, AMCL, Map Server, or command publisher is started. This candidate does not validate runtime compatibility, EKF, TF, or navigation. WP-04/WP-05 and approval states remain unchanged: `BLOCKED_BY_CONTRACT`, `OPEN`, `RUNTIME_APPROVED: NOT_APPROVED`, `GATE_B: NOT_STARTED`.

### WP06-6C Run 001 IMU observability correction — current review routing

Run 001 remains the immutable historical failure `WP06_6C_RUNTIME_FAIL_NO_RETRY`. Recalculated raw artifact hashes agree with its manifest, but no `/sim_eval/imu_raw` payload was captured and the `/imu/data` echo transcript is empty after timeout. Endpoint counts do not establish payload delivery. The source, bridge, and normalizer branches A/B/C are therefore not provable from Run 001.

This existing-branch correction adds bounded structured first-accept/first-rejection diagnostics for the existing normalizer gates and an offline multi-document YAML transcript parser; wheel and sensor/bridge semantics stay unchanged. Before any future capacity-one runtime, evidence must include a Gazebo-side `/sim_eval/imu/raw` sample, ROS staging `/sim_eval/imu_raw` payload plus verbose topic info, canonical `/imu/data`, and structured rejection details for stamp, frame, finite values, quaternion norm, and monotonic timestamp. Use `yaml.safe_load_all`; publisher counts alone are insufficient. The correction is source/offline-test evidence only, `runtime_eligible: false`; Run 001 is not replayed and no runtime authorization is issued. `RUNTIME_APPROVED: NOT_APPROVED`; Gate B remains `NOT_STARTED`.


### WP06-6C Run 002 world IMU-system corrective source activation

Run 002 raw evidence identifies `GAZEBO_IMU_SYSTEM_PLUGIN_ABSENT`: the world
had the Sensors system but no IMU system, and no Gazebo publisher was
observed on `/sim_eval/imu/raw`; scan and wheel paths remained operational.
The corrective source adds exactly one direct world-level
`gz-sim-imu-system` plugin and an offline XML regression test that rejects
absence or renaming. Run 002 remains an immutable historical failure and is
not retried. This candidate provides offline source/test/build evidence only;
`runtime_eligible: false`, runtime evidence `NOT_CREATED`, and
`RUNTIME_APPROVED: NOT_APPROVED`. It makes no runtime-pass claim for the sensor,
bridge, or normalizer.

## WP06-6C Run 003 runtime evidence disposition — bounded ingress status

WP06-6C implementation and runtime evidence are complete only within the wheel/IMU ingress scope. Independent audit passed the external Run 003 evidence for Gazebo IMU → ROS staging → normalizer → `/imu/data`, wheel ingress, effective `use_sim_time`, and teardown; see the canonical disposition manifest `docs/governance/evidence/WP-06_6C_WHEEL_IMU_RUNTIME_INGRESS_RUN_003_MANIFEST.json`. Run 001 and Run 002 remain immutable historical failures. This is not whole ROS graph, global TF, EKF, Nav2, AMCL, Map Server, or navigation-profile validation. `RUNTIME_APPROVED: NOT_APPROVED`; `GATE_B: NOT_STARTED`; no new runtime authorization is issued. Integration is eligible only after final independent audit of the exact L1 disposition commit and Owner decision.


## WP06-6F Run006 topology false-negative correction — bounded candidate status

Run005 remains immutable with terminal outcome `WP06_6F_RUNTIME_RUN005_FAIL_NO_RETRY_GUARD_CONSUMED`. Raw node-info transcripts show ROS-standard `/parameter_events` and `/rosout`; the checker mistakenly included these in exact EKF business endpoint comparisons. Other Run005 runtime criteria passed, so this is a checker false negative, not a TF/EKF/clock/robot failure. No historical run is retried.

Run006 uses section-aware exact topic parsing. It allows `/parameter_events` in both endpoint directions and `/rosout` only as a publisher, then checks exact EKF business endpoints. All other extra or wrong-direction endpoints fail closed. The `/set_pose` subscriber, zero-publisher, and empty timed echo checks remain.

Run006 guard is pending, capacity one, acquisition count zero, `runtime_authorization=NOT_GRANTED`; no authorization or runtime execution is included. Evidence ceiling: `IMPLEMENTED_OFFLINE_RUN005_TOPOLOGY_FALSE_NEGATIVE_CORRECTION_RUN006_GUARD_PENDING`; `runtime_eligible: false`; runtime evidence `NOT_CREATED`; `RUNTIME_APPROVED: NOT_APPROVED`; `GATE_B: NOT_STARTED`.


### WP06-6F Run007 — finalization-order corrective candidate

Run006 được giữ nguyên là historical runner finalization failure: raw record cho thấy runtime acceptance và teardown đều true, trong khi terminal failure được ghi trước khi teardown criteria được tính. Đây không phải bằng chứng lỗi TF/EKF/clock/robot. Run007 tách runtime acceptance, teardown acceptance và final acceptance; terminal outcome chỉ được chốt sau teardown. Guard Run007 riêng còn pending, capacity one, chưa acquire; chưa có runtime authorization. Evidence ceiling: `IMPLEMENTED_OFFLINE_RUN006_FINALIZATION_ORDER_CORRECTION_RUN007_GUARD_PENDING`; runtime eligible false, runtime evidence chưa tạo, `RUNTIME_APPROVED: NOT_APPROVED`, `GATE_B: NOT_STARTED`.

#### WP06-6F Run007 exact Owner authorization binding corrective

Candidate corrective offline-only trên parent `a1348313dab704964e67572fd18dcdcecf1f66d7` bổ sung năm tham số bắt buộc cho official runner. Trước acquire, authorization phải không rỗng và khớp chính xác Run007 ID, expected review SHA, integration base, cùng scope literal `WP06_6F_RUN007_ONE_OFFICIAL_RUNNER_INVOCATION_CAPACITY_ONE_NO_RETRY`. Guard ghi Owner authorization metadata, exact refs, acquisition count và `GRANTED_FOR_THIS_EXACT_RUN_ONLY` chỉ tại acquisition sau preflight; run record v2 lưu đủ metadata và guard state trước/sau. Sai/thiếu authorization fail-closed trước lock/evidence directory. Candidate không acquire guard và không chạy runtime. Seed còn pending/capacity-one; evidence ceiling `IMPLEMENTED_OFFLINE_RUN007_OWNER_AUTHORIZATION_BINDING_GUARD_PENDING`; runtime evidence chưa tạo; `RUNTIME_APPROVED: NOT_APPROVED`; `GATE_B: NOT_STARTED`.


### WP06-6F Run007 — bounded evidence audit disposition

The exact Run007 evidence for source commit `93468611748e3966cd6fa7fa280e840651d2c895` was independently audited PASS and is recorded by `docs/governance/evidence/WP-06_6F_TF_EKF_RUNTIME_INGRESS_RUN_007_MANIFEST.json`. This records only WP06-6F wheel/IMU ingress, `/clock`, EKF filtered odometry, specified TF edges/ownership/QoS, `/set_pose` boundary, and clean teardown. Run001–Run006 remain immutable historical. This does not mark the broader WP06, navigation profile, Nav2, AMCL, Map Server, whole ROS graph, Gate B, or runtime approval complete. `RUNTIME_APPROVED: NOT_APPROVED`; `GATE_B: NOT_STARTED`. This review-branch disposition remains subject to independent audit and a separate Owner integration decision.


## Step-7 Gate B authority/input closure survey — review snapshot

This is the Step-7 roadmap survey step, not PEP work package `WP-07-BRIDGE-FIRMWARE-OFFLINE`. The PEP WP-07 row and all ordered work-package statuses/dependencies remain unchanged (`WP-07` remains `BLOCKED_BY_DEPENDENCY`).

At exact integration base `5471e8860050326215bb83761629e9969def16ea`, candidate branch `step-07-gate-b-authority-input-closure-5471e88` records an L2 governance/evidence-only survey in `docs/governance/decisions/STEP-07_GATE_B_SAFETY_LIFECYCLE_PPO_AUTHORITY_INPUT_CLOSURE_SURVEY.md` and `docs/governance/evidence/STEP-07_GATE_B_SAFETY_LIFECYCLE_PPO_AUTHORITY_INPUT_CLOSURE_SURVEY.json`. The survey finds no concrete Gate B profile closed: the six input groups remain partial or unresolved pending Owner selections, immutable source pins, and applicable measurements. It records the `.msg` status-comment versus CMake generator contradiction without deciding or changing either side. WP06-6F Run007 remains bounded to its independently audited ingress/clock/EKF/TF evidence; it does not validate Nav2, map selection, `map -> odom`, whole-graph state, SafetyLifecycle, or PPO.

Candidate survey state: `STEP07_L2_AUTHORITY_INPUT_CLOSURE_SURVEY_CANDIDATE_PENDING_INDEPENDENT_AUDIT`. This is not a status transition or implementation authorization. `GATE_B: NOT_STARTED`; `RUNTIME_APPROVED: NOT_APPROVED`; WP-04 and WP-07 status/dependencies are unchanged. Terminal decision for this survey is `STEP07_L2_SURVEY_PASS_IMPLEMENTATION_NOT_AUTHORIZED`.


## Roadmap Steps 4–6 consolidated closure candidate (review-only)

At the explicitly supplied review base `d44ba711395a50d3ba8b9f91e6f64d1eca8ca5a1`, a candidate records Step 4 artifact bundle closure for sim_eval, Step 5 static profile closure, and Step 6 source/offline integration closure. This note is candidate evidence, not a WP status/dependency transition. PEP revision remains 0.10.14. Roadmap Step 7 remains `NOT_STARTED`; PEP work package WP-07 remains governed by its existing row. `RUNTIME_APPROVED: NOT_APPROVED`; `GATE_B: NOT_STARTED`. Evidence ceiling: `STATIC_SOURCE_OFFLINE_BUILD_TEST_READY_FOR_STEP7_RUNTIME_CAMPAIGN`.

### Roadmap Steps 4–6 corrective source assembly and safety closure

At review parent `d8db18aa3a5819b42d130221904281cec3360cae`, the corrective candidate updates only the authorized existing L2 allowlist. It adds deterministic absolute canonical-map input validation, Owner-bound local Fuel-cache structure preflight, explicit lifecycle reset/rearm barriers, fail-closed sim-only E-stop release, YAML-driven immutable safety limits/freshness, and correct V3 source ownership for `/imu/data` and `/wheel/odometry_raw`. This is candidate source/build/unit-test evidence and does not transition any PEP work-package status. Step 4/5/6/7, Gate B, runtime approval, WP-04 and WP-07 statuses remain as already recorded above; no runtime was executed.

Offline verification record for this review candidate: five-package colcon build PASS; `mecanum_nav_rl/test` 701 passed; `mecanum_nav_bringup/test` 234 passed; `mecanum_nav_rl_interfaces` colcon test 11 passed; ROSIDL imports, three installed safety executables, and eight installed launch/config source-byte comparisons PASS. Test interpreter is `/tmp/roadmap-step4-pydantic.ymkohe/venv/bin/python` with Pydantic `2.10.6`; build/install/log root is `/tmp/roadmap-step4-corrective.FNdGkG`, outside the worktree. Current evidence JSON SHA-256: `f757d8e9b035c23e27f01d44afa37082f4e62a061324ace6b0cf5fa91e349ff3`. This does not change the evidence ceiling or authorize runtime.


#### Roadmap Steps 4–6 safety lifecycle and receipt corrective (review candidate)

At parent `04a2ba5332ea56feb24dc3cf393114d8158bcb62`, the offline corrective is limited to the exact 14-path allowlist. It delegates managed lifecycle publisher transitions to the standard lifecycle parent callbacks; adds `episode_generation` to `CommandEnvelope`; binds NAV2 final publication to matching episode/reset/runtime identity; and records exactly one receipt after successful `/cmd_vel` publication, including zero safe-stop, with no receipt after command publish failure. Decision SHA-256 `0e1a84b8c2a8147db8ce57522aa55648241df110920830b29e28145273e988d5`; current evidence SHA-256 `f757d8e9b035c23e27f01d44afa37082f4e62a061324ace6b0cf5fa91e349ff3`. Five-package colcon build PASS; `mecanum_nav_rl/test` 701 passed; `mecanum_nav_bringup/test` 234 passed; interface colcon test 11 passed. This is offline source/build/test evidence only. Step 4–6 statuses remain as previously recorded; Step 7 remains `NOT_STARTED`; `GATE_B: NOT_STARTED`; `RUNTIME_APPROVED: NOT_APPROVED`.

### Roadmap Steps 4–6 corrective metadata reconciliation — 2026-10-19

The exact underlying L2 corrective is `dbc00940f9f70a4ee3a846ceb6fde1964c35ff19` (sole parent `04a2ba5332ea56feb24dc3cf393114d8158bcb62`), with 14 changed paths and 46 source pins verified against its Git blobs. Its recorded offline results are 701 `mecanum_nav_rl` pytest cases, 234 `mecanum_nav_bringup` pytest cases, and 11 interface `colcon test` cases. The current L1 reconciliation is a distinct five-governance-path change; it does not alter source/test/runtime semantics or historical evidence.

Reconciliation decision SHA-256: `0d5927d672b1d7c8083c50638f9b77ec8b9eac94f17a3b27bb460aa3ae167920`; evidence JSON SHA-256: `16a513a01e2ba71aaac99d6c4cee71ca36c22ce6cec811d1a0e92a60d78c6e39`; Registry SHA-256: `f4b4edd2b882b7b573502b3b0a86198c29556dc8ca11656f29a8813707c5f076`. This entry supersedes stale current metadata about the underlying packet’s parent, path scope, source-pin count, and test totals. Step 4 remains `CLOSED_FOR_SIM_EVAL`; Step 5 and Step 6 remain `IMPLEMENTED_OFFLINE_ONLY`; Step 7 remains `NOT_STARTED`; `GATE_B: NOT_STARTED`; `RUNTIME_APPROVED: NOT_APPROVED`; the evidence ceiling is unchanged.


### Roadmap Step 7 integrated NAV2_BASELINE campaign Run001 — review candidate

This L2 candidate adds only source/offline campaign machinery at exact base `f7f98c683d59cf4c62e462da9f37d4ffb2455c80`. The campaign input bundle is `sim_eval` + `NAV2_BASELINE` with Owner-pinned map/world/Fuel/poses/goal and ownership described in the candidate decision/evidence. A capacity-one guard remains pending; exact-run Owner authorization, runtime execution, independent evidence audit, and Owner approval are still future prerequisites.

This review snapshot does not transition plan statuses: Step 4 `CLOSED_FOR_SIM_EVAL`; Step 5 and Step 6 `IMPLEMENTED_OFFLINE_ONLY`; Step 7 `NOT_STARTED`; `GATE_B: NOT_STARTED`; `RUNTIME_APPROVED: NOT_APPROVED`. Evidence ceiling is `IMPLEMENTED_SOURCE_AND_OFFLINE_TEST_CAMPAIGN_MACHINERY_ONLY`; runtime evidence is not created. PEP work-package identifiers/statuses remain unchanged.

Run001 campaign review evidence records six-package colcon build PASS, 705 `mecanum_nav_rl/test` tests, 237 `mecanum_nav_bringup/test` tests, 11 observer tests, 11 interface tests, and 36 focused tests PASS. These results do not transition Step 7, Gate B, or runtime approval.

#### Roadmap Step-7 Run001 campaign topology candidate

The review candidate remains source/offline-test machinery only. Composite launch has an exact `start_bootstrap` literal argument defaulting to `true`; separated mode disables inclusion while retaining map and Fuel preflight. The one-shot runner creates independent bootstrap and composite process groups, waits for bootstrap readiness before composite startup, and verifies composite-first then bootstrap teardown. Decision/evidence/manifest hashes are recorded in the Registry's current candidate entry. Offline checks passed as recorded in the campaign evidence; this does not start the campaign, consume the guard, transition Gate B, or change any PEP work-package status.

#### Step-7 Run001 lifecycle endpoint/QoS correction — review-only

This candidate aligns both observers and the raw graph validator with the existing SafetyLifecycle publisher endpoint and QoS. Seven changed source/test SHA-256 and byte-size pairs are recorded in the Run001 evidence and manifest; the amended contract-test path pin is documented in the following closure entry. The source-pin set remains 16. Run001 guard remains pending/capacity-one/not consumed; Step 7 remains `NOT_STARTED`, `GATE_B: NOT_STARTED`, and `RUNTIME_APPROVED: NOT_APPROVED`. This is offline candidate scope only and changes no runtime authorization or project status.

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

The amended test contract preserves the root campaign's exact 23-path diff and validates the corrective's exact 14 paths, including a dirty-worktree and post-commit scope path. Existing source pins remain 16 unique entries; `ros2_ws/src/mecanum_nav_bringup/test/test_sim_eval_tf_ekf_runtime_contract.py` remains the same pinned path with refreshed SHA-256 `8f03f5feef72d81eb86600f2dfcabffe18765fd4db57c1484bd67ec5250dd6db` and size 27451 bytes. Current offline verification: six-package external build PASS; focused Step-7 tests 49 passed; `mecanum_nav_rl/test` 707 passed; `mecanum_nav_bringup/test` 239 passed; observer and ROSIDL tests 25 passed; installed closure PASS. Run001 remains pending/unconsumed; no runtime or Gate-B status transition is made.

### Step-7 Run001 acceptance-matrix closure

The acceptance matrix in both Run001 governance records is aligned with raw observer acceptance IDs for lifecycle endpoint/QoS, receipt QoS, obsolete lifecycle topic absence, receipt publisher owner, READY lifecycle observation, receipt identity, and final receipt observation. No source/runtime contract or status transition is implied; Run001 guard remains pending and unconsumed.

### Run001 acceptance-matrix scope-chain closure

The current corrective preserves root 23-path and lifecycle-QoS 14-path historical diffs and validates the current nine-path scope separately. This is offline test/governance closure only; Run001 guard remains pending/unconsumed, and no Gate-B or runtime status transition is made.


### Step-7 Run002 pre-acquire evidence correction — review candidate

The Run002 source/offline candidate adds pre-acquire failure evidence persistence after source/guard identity and detached runtime worktree validation. It records the exact exception and traceback, zero runtime-process calls, unchanged pending guard, and a terminal no-consumption outcome. Run001 remains historical and immutable. No runtime execution, Gate B transition, or `RUNTIME_APPROVED` is claimed; Run002 authorization remains NOT_GRANTED.


Run002 source provenance: exactly 16 unique path/SHA-256/size pins are recorded consistently in the Run002 guard seed, evidence, guard manifest, and Registry. This is an offline source-closure record only; it does not authorize or claim runtime.


### STEP07 Run002 historical source-pin reference-aware correction

The Run002 candidate remains based on `5a44cd9910e9b6d6058d8d2d9252a86f7cf9dcd8`. Its direct corrective scope is exactly 13 paths. The scope-chain test preserves the Run001 root campaign (23 paths), lifecycle/QoS correction (14), acceptance-matrix correction (9), and current Run002 correction (13). Run001 guard pins are verified by SHA-256 and size against `git show 5a44cd9910e9b6d6058d8d2d9252a86f7cf9dcd8:<path>` with no fallback; Run002 pins continue to verify current worktree bytes and remain 16 unique entries. Run002 remains pending/unconsumed; no runtime execution or Gate B transition is asserted.


### Step-7 Run003 Fuel cache path-normalization candidate

The review-only Run003 candidate, based on `6d730bd54d7f99429ee4832a3f6f96beffae020f`, has an exact 14-path current scope: the original 13 Run003 paths plus the Owner-authorized Run002 historical guard-test correction. The added test validates Run002 pins from Git blobs at `6d730bd54d7f99429ee4832a3f6f96beffae020f`, with exact SHA-256/size and no checkout fallback; it does not alter Run002 behavior or become a Run003 source pin. Run003 retains exactly 16 unique runtime source pins; the already-pinned contract-test entry now matches SHA-256 `d16c487554495e73dbbdd8f7df857b383897db6a804c85aef9a1572c2486203d` and size 32084 bytes. It uses exact lowercase Fuel owner/model cache paths while retaining the SDF's case-sensitive URIs, and disallows ambiguous recursive lookup, custom roots, escaping symlinks, and downloads. Run002 remains the immutable pre-acquire failure `STEP07_NAV2_BASELINE_RUN002_PREACQUIRE_PREFLIGHT_FAILED_NO_GUARD_CONSUMED` with root cause `FUEL_CACHE_PATH_CASE_NORMALIZATION_MISMATCH`; its evidence mechanism worked and it was not retried. Depot host asset availability remains an unverified runtime precondition. Run003 guard remains pending, capacity one, acquisition zero, and `runtime_authorization=NOT_GRANTED`. No project status changes: Step 7 and Gate B remain `NOT_STARTED`; `RUNTIME_APPROVED: NOT_APPROVED`.

### Step-7 Run004 host provisioning environment decoupling — corrective candidate

Run004 corrective base `cbf59ff938d8b96ec650859d9367bc6cb840f0c6`, exact 11-path delivery scope (four source/test paths in Phase A); the original 17-path Run004 candidate remains historical. The host helper validates Python 3.12, exact Pydantic 2.10.6 and fingerprint, and defers `rclpy` to the sourced runner preflight. Historical Run001–Run003 pins remain Git-blob verified; Run004 has 20 current-worktree pins. Decision SHA-256 `f4dd7b7c4b24eceeae85bb08812ea32ac9c3029b681f127816349176c6997b0a`, evidence SHA-256 `e3b9eaab981f7bcb44192fcc1d61af53c79878f79103037a3857adc4389ff8ff`, manifest SHA-256 `1369bac8fd60586a8e2231ff9f458cdc2820cfa599c32ab6e35df98533a0c376`. Run004 guard remains pending/unconsumed; no runtime evidence; Gate B `NOT_STARTED`; `RUNTIME_APPROVED=NOT_APPROVED`.


### Step-7 Run005 installed package-prefix closure — review candidate

At exact base `b7105ccb651da6d0dcb916d7544481f7beacaae1`, the Run005 L1 correction addresses only the historical Run004 pre-acquire root cause `PACKAGE_PREFIX_CLOSURE_MISSING_ROBOT_URDF_FINAL_DESCRIPTION`. The Run005 runner collects the exact eight package prefixes and verifies installed-file comparison package membership before comparing installed bytes. Run004 remains an immutable, non-retried pre-acquire failure; its prior disposition is not broadened.

The Run005 candidate has an exact 13-path scope and 21 current-worktree source pins. Historical Run001–Run004 pins are validated from exact Git blobs at their respective historical commits; Run005 pins use current candidate bytes. Offline checks recorded for this candidate: Step-7 tools 182 passed; bringup 239 passed; RL 707 passed; six-package external build PASS; observer/ROSIDL tests 13/8 passed; installed closure, static parsing, source-pin and scope checks PASS. These checks do not authorize or claim runtime. Run005 remains pending with capacity one, acquisition zero, and `runtime_authorization=NOT_GRANTED`; Step 7/Gate B remain `NOT_STARTED`, `RUNTIME_APPROVED=NOT_APPROVED`. No PEP work-package status or dependency is changed.

Decision SHA-256 `3fe0df3816bcbfd4569ae9279b2e6be3ecf8f6041bc07295e1a14455a3ded51c`; evidence SHA-256 `fdc65d78e947fd302acc5e4885d4f2aefefc14d98e98632c8e2d8cbdbf05b777`; guard manifest SHA-256 `c8abea65d820b6b850e6853e7f52bd1566ff99f1c60647126f30ac871f1d4986`; Registry SHA-256 `4feffc633d5f16d9a35ced9a81b06b9d4fa5837d4789e9dd8ba0e3c2d562a793`.


### Step-7 Run005 package-prefix closure final pin/scope reconciliation

This current Run005 reconciliation supersedes its earlier candidate metadata references without changing PEP work-package status or dependencies. The dirty/clean final contract test requires the exact 13-path `RUN005_PATHS`; worktree dirtiness no longer selects a different invariant. The existing contract-test source pin is SHA-256 `50e826ba266c8177ec73c450c0a8a3ea77ae33184d98b0c534c4f08f1d6f409b`, size `40187`; 21 unique current source pins remain independent of the 13-path delivery scope. Phase A passed: Step-7 tools 182, bringup 239, RL 707, focused scope/historical 46, six-package build, observer/ROSIDL and installed-byte closure. No runtime or Gate-B result is claimed. Run004 remains immutable and not retried.

Decision SHA-256 `6b9cb13114504f3c2b33e7187c6d32b227f79e2a101c6f57f89a99a21038f72c`; evidence SHA-256 `5a7c70bb5c9a21300d23ab0d2318223fcb1909ff6326b0b6540aba4863baedae`; manifest SHA-256 `b51c528653b9b6b58118f020e05c6d2148ae419fc8acb89563cd268dc2542986`; Registry SHA-256 `84c006da0f6fdf523e06027f1d863d0b0cedca7c698cd1b3e2fe69578a2d6b91`.


### Step-7 Run005 attempt_002 Fuel cache case-normalization corrective

Run005 attempt_001 remains the immutable consumed failure `STEP07_NAV2_BASELINE_RUN005_FAIL_NO_RETRY_GUARD_CONSUMED`, root `SIM_EVAL_FUEL_CACHE_MODEL_MISSING:OpenRobotics/Depot` then `BOOTSTRAP_EXITED_BEFORE_READINESS`; it was not retried. Attempt_002 fixes only the bootstrap filesystem case mismatch: original SDF URI casing is preserved and local cache lookup uses lowercase `openrobotics/depot` and `movai/tugbot`, rejecting uppercase parents. No download or runtime is included.

The current attempt_002 exact path set is 12 paths (`RUN005_ATTEMPT_002_PATHS`) in both dirty and committed states. Attempt_001 remains the exact 13-path historical diff. The separate attempt_002 runtime source-pin inventory has 22 unique paths and validates current candidate bytes; attempt_001 pins are checked from Git blobs at `71ca32471f8e042a0048d319ca39cb9deff0c6f4` by SHA-256/size without worktree fallback.

Offline verification: focused 72; Step-7 tools 184; bringup 239; RL 707; six-package external build PASS; observer/ROSIDL 25 PASS; Python compilation, installed launch equality, canonical JSON and duplicate-key checks, YAML/XML parsing, source pins, historical preservation, exact scope and diff checks PASS. No runtime executed. Attempt_002 guard remains pending, capacity 1, acquisition 0, `runtime_authorization=NOT_GRANTED`; Gate B `NOT_STARTED`; `RUNTIME_APPROVED=NOT_APPROVED`. Evidence ceiling: `SOURCE_OFFLINE_TEST_CANDIDATE_ONLY_NO_RUNTIME_EVIDENCE`.

Current decision/evidence/manifest/guard SHA-256: `ba12bd8e4d24a17e3455622770cf0449dc2724216b93411ee8444fa4ae7d58db` / `79ebedc1c3831760be2b8c5bc2c588588cd237e377d1ba0ff6ff759ff2ee1ed2` / `b95b01b7f98490ae9e157e471790d1d36cb835c8330f91c1ddfc2b1de09b4caa` / `ad5feb501244511edbe2fe9aded8e53d984453182aff0b3d14939e8a46dff181`. Registry SHA-256: `d6b0ba9b3492f17006a887e7316db117806ceea1936fe317e14194947ca7903f`. No PEP work-package status or dependency is changed.


### STEP-7 Run005 attempt_002 isolated runtime checkout corrective

Corrective base `72d04391a9d6d83e3e18589212d566f17dc220d1`. The runner creates a private local clone from the exact source checkout with `--no-hardlinks`, checks out the exact review HEAD detached, verifies clean status and official origin, and confirms that source repository ref/status/origin remain unchanged. Linked worktree metadata writes are removed from the runner path. The cumulative attempt_002 exact path set is 13; the runtime source-pin inventory remains 22 unique paths. Offline validation is recorded in the current Run005 evidence; there is no runtime claim or PEP status transition. Independent audit of the exact corrective commit, followed by the separately authorized steps, remains outstanding.

Current Run005 attempt_002 corrective hashes: decision `ddff30ade74efaf4d8d8e202de4decdb5594766589097a29a2d6780e7f088180`; evidence `6f4ad54ecfd3b51a17c3a1251ef1322a63b4a9222fca1c47220dfa0bcdb8a24b`; manifest `22e1d9b6bc9d013a831b0ffbb06bddce8a18b05c1ab6092fac88a42a61761818`; guard `4be7b4bd00324ba023c11a2717cdfcc91f8d9418ace98b47de40e2f181cc178f`; Registry `1b685ed46e820c48971ccced80be39644b2632c499c442d31bfd06cd3438c76a`.


### Step-7 Run005 attempt_002 partition and Nav2 pre-acquire closure corrective

At corrective base `87af41f45d721969f2767d36291252e3b14e3dcb`, this L1 packet preserves the original attempt_002 13-path historical scope and adds a separate exact 16-path direct corrective scope. The scope contract uses exact sets in both dirty Phase A and final committed states.

The state-estimation child launch now requires a caller-supplied non-empty partition, exports and forwards it exactly, and does not hard-code the WP06 partition. Four Nav2 Step-7 providers are declared once as profile-specific runtime dependencies; the WP05 14-root lock/template is unchanged. Before guard acquisition, the runner validates seven Nav2 node package prefixes/executables, four plugin-provider prefixes, and installed/source byte equality for 15 runtime artifacts.

Run005 attempt_002 invocation_002 remains immutable with terminal `STEP07_NAV2_BASELINE_RUN005_FAIL_NO_RETRY_GUARD_CONSUMED`, root `LEGACY_WP06_PARTITION_LOCK`, and was not retried. No runtime was executed in this corrective. The seed remains pending, capacity one, acquisition zero, `runtime_authorization=NOT_GRANTED`; Gate B is `NOT_STARTED`, `RUNTIME_APPROVED=NOT_APPROVED`.

Phase A PASS: focused 89; Step-7 tools 205; bringup 244; RL 707; six-package external build; observer 13 C++ and ROSIDL 8 tests; installed artifacts 15/15; current source pins 34/34; exact historical/current scope and parsing checks. Current evidence ceiling remains `SOURCE_OFFLINE_TEST_CANDIDATE_ONLY_NO_RUNTIME_EVIDENCE`.

Record references: Run005 decision `8e6437172e324cf0407a612209ab2759ca02634b95a003f4b685ede2bd58e90a`, Registry `c75d979c58b555c9dfed76667f96f7bcc5151033b779c9f96d43066f983a4831`, guard `1c8468d3df731719522e64d8b21370ce33543ff07f9c1835aa920bd5c8f0b520`, evidence `265807e5cc1da274dd0f08ffcdede4791838d6e334904c1dbfbf2b6d3341fe51`, manifest `424104bafd0e164720499e6e5204a7de4d7916c87ac1d596db92ae6093c0bc87`. No PEP status or dependency transition is made.

### Step-7 Run005 attempt_002 output-parent preflight reliability corrective

This current corrective has exact direct scope 11 paths from `c408ccd2a2f7b11787f725a24e818ffa038e3d36`; it does not alter Run005's profile, map/world, TF, safety, Nav2 behavior, Gate-B acceptance, or command ownership. The runner removes the unused `socket.if_nameindex()` probe and validates real writable output parents with an exclusive create/write/fsync/close/unlink probe before clone/build/host checks/evidence/guard/processes. Stable output-parent failures do not attempt evidence writes.

Invocation_003 is recorded accurately as a pre-acquire failure: initial `PermissionError: [Errno 1] Operation not permitted`, then evidence persistence failed with `OSError: [Errno 30] Read-only file system`; no evidence bundle, guard consumption, lock, or campaign process resulted. No retry occurred. The source guard remains pending, capacity 1, acquisition 0, `runtime_authorization=NOT_GRANTED`; Gate B remains `NOT_STARTED`, `RUNTIME_APPROVED=NOT_APPROVED`.

Run005 source pins remain 34 unique current-worktree entries, separate from the 11 changed paths. Four existing pin entries were refreshed; no new pin was added. Offline verification recorded: Step-7 tools 218 passed, bringup 244, RL 707, six-package external build PASS, observer/ROSIDL tests PASS, installed artifacts 15/15, and pins 34/34. Evidence ceiling: `SOURCE_OFFLINE_TEST_CANDIDATE_ONLY_NO_RUNTIME_EVIDENCE`.

Decision SHA-256 `3d42d895ee8bc3a583e3b2f2dd08caa751afa0a12b23914ce2e1af5ccc7ba735`; Registry SHA-256 `ece7c9142e77dff08fbd84aa4f1e2c0534aa4de432233dbb16516093a22484df`; guard `db5cfd94b9623c1497ba103444e931064c04cf76e7ebe455ba8a7f29a313752e`; evidence `39b220725d48f19f7b140da97868bc9c31ba5321c21dfa5c1be14572ca050813`; manifest `66bb591039054556824e0c032d552247d5319e8b5ec240bddea7960bf99bd17d`.


### Step-7 Run005 attempt_002 exact partition-process identity corrective

This L1 corrective has an exact 11-path direct scope from `da82b2e5d65eedd80f42000283dccc42a5f6ed66`. Invocation_004 is an immutable pre-acquire failure: `STALE_PARTITION_PROCESS_FOUND`, runner invoked once, no bootstrap/composite/observer calls, no guard consumption, no lock, and verified evidence checksums. The stale scan matches only an exact NUL-delimited `GZ_PARTITION` environment entry for non-ancestry processes; inaccessible/disappeared process environments are ignored.

Offline verification passed: 72 focused runner tests; 222 Step-7 tool tests; bringup 244; nav_rl 707; six-package external build; observer CTest 1/1 and ROSIDL CTest 3/3; installed/source equality 15/15; and 34/34 current source pins. Guard remains pending, capacity one, acquisition zero, `runtime_authorization=NOT_GRANTED`; Gate B `NOT_STARTED`; `RUNTIME_APPROVED=NOT_APPROVED`. Evidence ceiling is `SOURCE_OFFLINE_TEST_CANDIDATE_ONLY_NO_RUNTIME_EVIDENCE`.

Record hashes: decision `{decision_sha}`, Registry `{registry_sha}`, guard `{guard_sha}`, evidence `{evidence_sha}`, manifest `{manifest_sha}`.


## Run005 attempt_002 exact partition-process identity corrective — final verification

This update supersedes only the current attempt_002 stale-process scanner verification metadata; no PEP work-package status or dependency changes. Exact direct scope from `da82b2e5d65eedd80f42000283dccc42a5f6ed66` is 11 paths. The scanner matches only exact NUL-delimited `GZ_PARTITION=<partition>` entries for non-ancestry processes; process disappearance/inaccessible environment is ignored, and numeric PID diagnostics are deterministic.

Final offline checks: focused runner/guard 82; Step-7 tools 223; bringup 244; nav_rl 707; six-package external build PASS; observer CTest 1/1 with 13 cases; ROSIDL 25 cases; installed-source equality 15/15; py_compile 4 modified files; current source pins 34/34. Guard remains PENDING/capacity 1/acquisition 0/NOT_GRANTED, no lock. Invocation_004 remains immutable with verified evidence and no guard consumption. No runtime claim, Gate B transition, or authorization.

Current record references: decision `ab30bbbf37f4961e70c4369e3c370590438d12f16031cb9d0fc5850653694311`; Registry `cd615016ac39364067ef8474f7d1343882cc102c775b398a201a6122c2af80ff`; guard `e71580a8c3ffb0feb7740f8aa194ad2206ce18f9e60cfc9fb4b5ad1c600da36a`; evidence `fe28092b4589cf85b270fdc6e8696197687626aa32ca33f85e3360f36db462e6`; manifest `a012aae26afbc5af4c025f7d70d3ef6a562b34c4659c361cccdf86622f9c5f93`.

### Run005 attempt_002 host transport and durable terminal evidence corrective

The current L1 corrective is based on `99d5c29c1c302260a8971e19e46f93d778a52f86` with exact 11-path scope and 34 unique existing Run005 runtime pins. Host transport is checked before acquisition through interface enumeration, UDP loopback bind/close, and `gz topic -l` under the campaign partition. SIGTERM after acquisition enters teardown and terminal artifact finalization; SIGKILL remains uncapturable. Invocation_005 evidence is preserved and records bootstrap readiness timeout after Gazebo transport errors; its run record exists, so the prior assertion that external termination prevented that record is not supported by the stored artifact. This source/offline candidate does not authorize a runtime invocation.


### Run005 attempt_002 terminal verdict and ROS discovery corrective (offline candidate)

Current base: `87ee34b1a945ecc12b525fe9f4711a368c0bdbc3`; exact direct scope: 11 paths. Before acquisition, the runner checks ROS CLI support and bounded discovery capability in the sourced ROS/overlay environment. Empty graph is permitted; capability errors fail closed with pre-acquire evidence. Terminal PASS requires all acceptance values true, no failure literals, and completed, ordered, clean, verified teardown. SIGTERM produces failure and best-effort composite-before-bootstrap teardown/finalization; unverifiable teardown fails. SIGKILL, power loss, and unwritable filesystems can prevent durable finalization. Phase A results are recorded in the Run005 L1 evidence. This offline candidate does not authorize runtime or transition Gate B.


### Step-7 Run005 attempt_002 SIGTERM/guard handoff corrective

This L1 corrective is based on `bee34dd2d689fe585ae12000058b2f2903196659`. It closes the SIGTERM boundary around guard acquisition and terminal evidence finalization without changing acceptance, Gazebo/ROS host probes, teardown order, guard capacity, or process ownership. The handler is active before acquisition; SIGTERM is masked only for the guard mutation/handoff and pending delivery is classified after marking the guard acquired. During finalization, SIGTERM is latched without throwing and causes terminal FAIL resynchronization before handler restoration when evidence storage remains writable. SIGKILL, power loss, and filesystem write failure remain durability limits.

Phase A is source-frozen after PASS: Step-7 tools 263; bringup 244; RL 707; six-package external build; observer 13 / ROSIDL 8 tests; installed source equality 15/15; 34/34 source pins; exact scope/history and parsing checks. No runtime or official runner was invoked. Run005 attempt_002 guard remains pending, capacity one, acquisition zero, `runtime_authorization=NOT_GRANTED`; Gate B `NOT_STARTED`; `RUNTIME_APPROVED=NOT_APPROVED`. The exact current corrective scope is 11 paths, independent of 34 source pins.


### Run005 attempt_002 — guard mutation/process ownership corrective

Corrective L1 trên base `53b7790c23c7d4969612259a8ee06be0353babd2`, vẫn Run005 attempt_002. Direct scope là exact 13 path; runtime source-pin inventory giữ 34 path duy nhất. Guard mutation exception chỉ được xóa lock khi strict runtime readback xác nhận đúng seed PENDING chưa acquire. Sau replacement hoặc unmask failure, strict readback CONSUMED đúng commit/authorization/count=1 đi vào post-acquire FAIL và terminal evidence. Readback không xác định giữ lock, ghi UNVERIFIED và không fallback sang source checkout.

Cả bốn component dùng cùng owned-spawn helper: SIGTERM được latch trong registration; child handle được ghi ledger trước PGID/snapshot. Teardown lấy ledger kể cả khi caller chưa nhận assignment. Chỉ signal process group đã xác minh; nếu không xác minh được, thử dừng chính child đã biết và ghi FAIL/unverified. Thứ tự composite trước bootstrap, acceptance, partition, QoS và capacity-one không đổi.

Phase A PASS: focused runner 142, guard 15, historical guard 19; full Step-7 tools 299, bringup 244, RL 707; build sáu package ngoài worktree; observer 13 và ROSIDL 8; py_compile sáu file; installed/source equality 15/15; source pins 34/34 sau reconciliation, JSON/YAML/XML và history/scope/diff checks. Không official runtime invocation trong corrective này.

Giữ lịch sử invocation_001–005, consumed guards/locks/evidence/runtime worktrees bất biến. Source seed còn PENDING, capacity 1, acquisition 0, runtime_authorization=NOT_GRANTED, không lock. Gate B NOT_STARTED; RUNTIME_APPROVED=NOT_APPROVED. Giới hạn: SIGKILL, mất điện hoặc filesystem không ghi được vẫn có thể ngăn terminal evidence. Evidence ceiling: SOURCE_OFFLINE_TEST_ONLY_PENDING_INDEPENDENT_AUDIT. Bước tiếp theo: independent audit exact corrective commit; runtime cần authorization riêng.


### Run005 attempt_002 — corrective L2 composite/Gate-B

Base `bb5fc04fe8e309c52e468f766893ef60625e6821`; exact direct scope 23 path, union pins 37/37. Owner phê duyệt L2 cho lifecycle orchestration, clock/binding/TF, observer lifetime và scan validity; filename decision L1 giữ nguyên. SOURCE_OFFLINE_TEST_ONLY_PENDING_INDEPENDENT_AUDIT. Focused 46, tools 301, bringup 248, RL 715 PASS; sáu-package external build, observer 13, ROSIDL 8, installed/source 19/19 PASS. Guard seed PENDING/capacity 1/acquisition 0/NOT_GRANTED; Gate B NOT_STARTED; RUNTIME_APPROVED NOT_APPROVED. Không official runner/runtime/integration; lịch sử và guard/ownership tại base bất biến. Next action: independent audit exact corrective commit; runtime cần authorization riêng.

Decision: `docs/governance/decisions/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_L1_DECISION.md`; SHA-256 `e245967f9c5b324c4d67dae70ca046bc3b8d80252197411c3021ebca3856ed36`.

- `artifacts/simulation/step07_nav2_baseline_campaign/approval_guards/STEP07_NAV2_BASELINE_RUN_005.json`: `2442328059cfea2143ea3660ad578bf8a69a535493459f7aec510a725c12e6aa`.
- `docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_L1_EVIDENCE.json`: `1d206e32f5604ff425d30b3dbd8b2a377593a602d9e163e18a47065ce8995afe`.
- `docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_GUARD_MANIFEST.json`: `3c7ab3855df8fac785c21de85d1e3e522fffbb87aaf090b63a64fb81737f0b36`.


### Active corrective — Run005 evidence-validator identity closure

Base `c8e34ead42c9c3fa6d79bf73dc221a9cc599d42a`, branch `step07-integrated-nav2-gateb-campaign-f7f98c6`; exact delivery set is the 10-path allowlist in the Run005 evidence and manifest. Scope is limited to validator run identity and verdict consistency. The source-pin inventory remains 37 unique entries; three existing hashes/sizes are refreshed. Historical Git-blob checks and the earlier 23-path L2 scope remain preserved.

Offline verification: validator 15 tests; focused scope 9 tests; Step-7 tools 306; bringup 249; RL 715 with external install base; six-package external build; observer 13 and ROSIDL 8; `py_compile`; installed/source equality 15/15. No runtime was executed. Evidence ceiling is `SOURCE_OFFLINE_TEST_ONLY_PENDING_INDEPENDENT_AUDIT`. Next action: independent audit of the exact corrective commit; runtime requires separate Owner authorization.


### Active corrective — Run005 attempt_002 GZ_IP transport / graceful teardown L2

Base `f72ac2112e0d1545a72b6a9a12764664d508aaa8`, existing review branch; exact current direct set is 13 authorized paths. Source inventory remains 37 unique pins. Pre-acquire transport qualification derives and validates one local IPv4 from structured default-route/interface/address data, sets `GZ_IP` only in the verified campaign environment, and runs a bounded one-shot `gz topic` publish probe. PASS also requires graceful teardown; clean final state after escalation is FAIL. Invocation_007 remains immutable runtime failure (bootstrap ready, composite readiness timeout on multicast `Network is unreachable`, lifecycle_manager escalation). No runner/runtime/integration was executed by this offline corrective. Independent audit is next; a future runtime requires separate authorization.

### Run005 attempt_002 — default-route resolver corrective (offline only)

Active corrective trên base `e921b04e9ef8dc933a76966cf101613fab0f8062`, exact direct scope 11 paths. Loại bỏ external `ip -j` route dependency; pure-Python resolver dùng `/proc/net/route`, sysfs physical/UP checks, UDP connect source selection và interface address verification. Giữ `GZ_IP`, campaign `GZ_PARTITION` và bounded one-shot publish probe trước guard. Invocation_009 giữ nguyên là pre-acquire failure `GZ_TRANSPORT_HOST_CAPABILITY_UNAVAILABLE:DEFAULT_ROUTE_EXIT_NONZERO`; không gán nguyên nhân sâu hơn và không retry.

Evidence ceiling là source/offline test only. Guard chưa consume; runtime authorization chưa được cấp; không có Gate B hoặc runtime PASS. Next action: independent audit exact corrective commit; runtime cần Owner authorization riêng.


Verification snapshot: focused runner/guard/scope 180 passed; full Step-7 tools 310 passed; `mecanum_nav_bringup/test` 251 passed; `mecanum_nav_rl/test` 715 passed with external install base; six-package external colcon build passed; observer 13 and ROSIDL 8 passed; `py_compile` passed; installed/source runtime artifact equality 15/15. Run005 keeps 37 unique pins. All evidence is offline-only; independent audit remains required.

## Run005 attempt_002 L1 corrective — 2026-10-22

The review candidate based on `a383f258b02a0f9a22b2dc72fb937dbcaba6973a` corrects required Nav2 costmap dimension YAML types and records post-SIGINT SIGTERM/SIGKILL escalation as non-graceful teardown. Historical invocation_010 remains FAIL and immutable. Phase A source checks passed before freeze, including Step-7 tools, RL, external build and installed/source equality; the Owner-authorized cleanup removed only the verified generated `log/` directory, after which bringup passed 253 tests. Actual direct diff is 11 paths; the authorized allowlist is 12 paths and contains one unchanged permitted path (`test_step07_run005_runtime_guard.py`). Full Step-7 tools passed 311 after the one-time pin refresh. Delivery checks are being completed before commit/push. Run005 guard stays PENDING/capacity 1/acquisition 0/NOT_GRANTED, Gate B NOT_STARTED, and runtime remains unapproved. Evidence ceiling: source/offline only; independent audit remains required.

## Run005 attempt_002 — QoS evidence-chain source-freeze snapshot (2026-10-22)

Review base `9fad09f333b93c8f63d9c4044af41d04d40be8c0`; branch `step07-integrated-nav2-gateb-campaign-f7f98c6`. `SOURCE_FREEZE=TRUE` is offline-only. No runtime authorization or acceptance transition is recorded.

Run005 has 38 unique source pins. The added pin identifies the existing runtime QoS implementation `safety_lifecycle_node.py`; test-only observer source remains unpinned. Actual direct path set is 14; authorized allowlist is 15, with the decision document unchanged.

Verification: focused runner/validator/guard 181; Step-7 313; bringup 254; RL 715; six-package external build; observer 14 and ROSIDL 8; Python compile; installed/source equality 15 data artifacts + 2 QoS modules; 38/38 pins; canonical parsing, historical scope/Git-blob preservation, exact path scope and diff checks PASS. Invocation_011 remains immutable historical FAIL. Guard PENDING/capacity 1/acquisition 0/NOT_GRANTED; Gate B NOT_STARTED; RUNTIME_APPROVED NOT_APPROVED.


## 2026-10-23 — Run005 L1 collector corrective plan note

The evidence-collection ordering correction on base `a04ec4d317830e01a4613fc5251f2152b9e9946e` is source-frozen for independent review after offline verification. This note does not advance Gate B, runtime approval, or integration. Next action: independent audit of the exact candidate commit; runtime requires separate explicit one-run authorization.


### Verification correction

The five legacy-scope dispatch assertions were extended to recognize the current exact L1 reconciled path set. Full bringup verification now passes; this remains offline source/test evidence only. Gate B, runtime approval, and integration status are unchanged.
