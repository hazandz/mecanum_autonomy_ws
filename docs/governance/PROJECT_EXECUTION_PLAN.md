# Project Execution Plan — Mecanum Nav2 DRL

## Metadata

| Field | Value |
|---|---|
| Plan ID | `PEP-001` |
| Revision | `0.4.0` |
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
| 04 | WP-04-POLICY-CORE-P0 | V3 policy-observation core. First constrained deliverable: non-integrated immutable V3 contract primitives — ObservationCutoffV3 core type/validation and ObservationInputContractV3 structural models. Any LiDAR/LocalReference normalization, final-issued receipt integration, V3 assembler/encoder, compiler/profile closure or runtime bridge requires a separate independently approved implementation packet. | WP-03; user-approved V3 scope closure; semantic bundle closure for S2 rev.2, Observation Input Contract rev.6 and V3 Observation Boundary rev.7; separate exact implementation packet | BLOCKED_BY_CONTRACT |
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

WP-04 remains `BLOCKED_BY_CONTRACT` until semantic-bundle closure for S2 rev.2,
Observation Input Contract rev.6 and V3 Observation Boundary rev.7 is recorded
in its governing documents and a separate exact implementation packet is
approved.


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
