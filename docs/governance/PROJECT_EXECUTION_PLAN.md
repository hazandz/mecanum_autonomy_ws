# Project Execution Plan — Mecanum Nav2 DRL

## Metadata

| Field | Value |
|---|---|
| Plan ID | `PEP-001` |
| Revision | `0.5.0` |
| Architecture status | `ARCHITECTURE_FROZEN`, `IMPLEMENTATION_READY`, `NOT_YET_REAL_ROBOT_VALIDATED` |
| Immutable baseline | `baseline/architecture-frozen-20261002` at `86beff623dba3683f643c851a4a1374c635178b3` |
| Integration line | `integration/implementation` |
| Initial integration commit | `99de9d1839b0d5b1a2da95fc0958b49bac2483a0` |
| Activation rule | This plan is active only when its reviewed commit is present on `integration/implementation`. On a work branch it is a pending proposal. |
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
| Canonical maps at `artifacts/maps/<map_id>` | Missing | ROS-package maps are not canonical map artifacts |
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
