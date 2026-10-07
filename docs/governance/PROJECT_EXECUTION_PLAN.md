# Project Execution Plan — Mecanum Nav2 DRL

## Metadata

| Field | Value |
|---|---|
| Plan ID | `PEP-001` |
| Revision | `0.3.0` |
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


## Proposed plan change-control record — PEP-001 rev.0.3.0 (candidate only)

This section is a governance candidate on a work branch. Under the Metadata
`Activation rule`, this revision is not active until its reviewed commit is
canonically integrated on `integration/implementation`. It does not enact a
WP-02 status transition while under review.

| Change-control field | Candidate value |
|---|---|
| Plan ID; old/new revision | `PEP-001`; `0.2.0` -> `0.3.0` |
| Work package | `WP-02-PEP-CLOSURE-TRANSITION-CANDIDATE` |
| Candidate branch | `wp-02-pep-closure-transition-candidate-3f4a114` |
| Integration base SHA | `3f4a1147d97143995d3cd9c56097a0fb414a40ca` |
| Candidate commit SHA | The exact PEP-content commit and candidate branch-tip/audit-target SHA are intentionally cross-referenced by the future append-only ledger entry `WP-02-CLOSE-CANONICAL-SOURCE-SELECTION`; this avoids a self-referential SHA inside the PEP content. The candidate delivery/audit metadata must report the same commit identities explicitly. No commit is represented as effective status evidence here. |
| Exact proposed status transition | `WP-02: BLOCKED_BY_GOVERNANCE -> CLOSED` (`CLOSED` is the user-approved proposed token; it was not defined as a canonical terminal token by PEP-001 rev.0.2.0.) |
| Candidate/effective status boundary | This transition is proposed and approved for preparation only. The canonical status remains `BLOCKED_BY_GOVERNANCE` until this candidate is audited, integration is explicitly approved by the user, and the revision is canonically integrated. |
| Approver role | `Project Owner/User`, designated by the user for this status decision. Integration approval is still pending. |
| Evidence and scope basis | Ledger entry `WP-02I-INTEGRATE-CANONICAL-SOURCE-SELECTION`, candidate commit `eed009d926e721ed37f27f675bbbe27e04cc14fe`, evidence `IMPLEMENTED_OFFLINE_ONLY`; the delivered registry rules cover V3 selection, legacy boundary, and source-registry enforcement at governance/source-selection level, not automated runtime enforcement. |
| Additional evidence condition | No runtime, HIL, hardware, or physical-measurement evidence is required for WP-02 unless a controlling WP-02 authority explicitly requires it. No such requirement was identified in PEP-001 rev.0.2.0. |
| Dependency/evidence impact | WP-03 remains `BLOCKED_BY_CONTRACT`, with dependency on WP-02 and required user decisions unchanged. A WP-02 transition alone neither resolves WP-03 decisions nor authorizes WP-03 work. WP-04 remains `BLOCKED_BY_CONTRACT` with all existing WP-03, V3-scope, semantic-bundle, and implementation-packet dependencies unchanged. |
| Architecture/ACR impact | None proposed; this is a PEP/governance status-control change only. No architecture contract is amended. |
| User approval | User has approved preparation of this candidate, the proposed `CLOSED` token, and the proposed transition. Explicit approval to integrate this candidate remains required. |
| Ledger entry to append | Proposed entry `WP-02-CLOSE-CANONICAL-SOURCE-SELECTION`, only after PEP transition approval and canonical integration; expected contents are recorded below. |

The `Ordered work packages` table above intentionally retains its historical
`Initial status` column and all initial-status values, including WP-02
`BLOCKED_BY_GOVERNANCE`, WP-03 `BLOCKED_BY_CONTRACT`, and WP-04
`BLOCKED_BY_CONTRACT`. The proposed transition above is a separate candidate
record, not a rewrite of those initial values or a present-tense status
transition.

### Expected append-only ledger entry after approved integration

The following is proposed content for a future ledger append, not an entry
being added by this candidate. `Date`, integrated revision/commit, and any
approval reference must be filled from the actual authorized decision and
canonical integration event; do not infer or predate them.

```yaml
entry_id: WP-02-CLOSE-CANONICAL-SOURCE-SELECTION
date: PENDING_ACTUAL_CANONICAL_INTEGRATION
work_package: WP-02-CANONICAL-SOURCE-SELECTION
pep_revision: 0.3.0
transition: "BLOCKED_BY_GOVERNANCE -> CLOSED"
terminal_status_token: CLOSED  # user-approved proposal; effective only after authorized integration
approver_role: Project Owner/User
evidence_status: IMPLEMENTED_OFFLINE_ONLY
pep_content_commit: PENDING_ACTUAL_CANDIDATE_COMMIT
candidate_branch_tip_audit_target: PENDING_ACTUAL_AUDIT_TARGET
evidence:
  - ledger_entry: WP-02I-INTEGRATE-CANONICAL-SOURCE-SELECTION
    candidate_commit: eed009d926e721ed37f27f675bbbe27e04cc14fe
  - scope_coverage: V3 selection; legacy boundary; source-registry enforcement at governance/source-selection level
runtime_hil_hardware_measurement_evidence: NOT_REQUIRED_BY_REVIEWED_WP02_SCOPE
  # Revisit only if a controlling WP-02 authority explicitly requires it.
dependency_impact:
  WP-03: remains BLOCKED_BY_CONTRACT; WP-02 disposition and required user decisions recorded separately
  WP-04: remains BLOCKED_BY_CONTRACT; existing dependencies unchanged
integration_commit: PENDING_ACTUAL_CANONICAL_INTEGRATION
approval_reference: PENDING_ACTUAL_USER_AND_GOVERNANCE_APPROVAL
```

The future ledger entry must replace each pending commit field with its exact
SHA after the relevant event. `pep_content_commit` identifies the commit that
contains this PEP revision; `candidate_branch_tip_audit_target` identifies the
exact candidate reviewed by the independent auditor; and `integration_commit`
identifies the commit actually present on `integration/implementation`. These
are separate traceability roles even if fast-forward integration makes their
SHA values identical.

This expected ledger content does not authorize an append or transition. Per the
ledger's append-only rule, the future entry must be appended after the
transition is authorized and integrated; historical entries, including the
WP-02I evidence entry, remain unchanged.
