# WP-03 User Decision Packet — Baseline 9A4C0D2

**Work package:** `WP-03-USER-DECISION-PACKET-BASELINE-9A4C0D2-DRAFT`
**Status:** `DRAFT_FOR_USER_REVIEW`
**Mode:** `DOCUMENTATION_ONLY_PRE-WORK`
**Evidence base:** `origin/integration/implementation@9a4c0d233e8237f01a04880fe99e8a3114528f4c`
**Source packet:** `docs/architecture/proposals/wp-03-contract-closure/WP-03_USER_DECISION_PACKET_DRAFT.md`; SHA-256 `cb1df42d3f7ef3ccf9d947a9073bb621312e781ca022b047f5e428035f652d15`
**PEP:** PEP-001 rev.0.3.0; SHA-256 `e691e1c7ced69a3b0ca01828932adc7dc21f27d82f150535abad976f59206100`
**Architecture SHA-256:** `f0fb1ebede5f4fa18604610c04bb13587d456173b4fd942dba77e44d49777860`

This new packet preserves the historical packet identified above and updates
its baseline facts. It organizes only the remaining WP-03 decisions for user review. It does
not formally start or close WP-03, alter PEP/ledger/registry, approve another
contract change, authorize code, or approve runtime activity. It is a
proposal-area document, not canonical authority. WP-02 is already `CLOSED` at
the stated integration baseline and is not an open decision in this packet.

## 1. Authority and evidence boundary

The integration baseline is pinned to commit
`9a4c0d233e8237f01a04880fe99e8a3114528f4c`. At this baseline the Canonical
Source Registry and the bundled approval record identify the following
canonical design/governance documents:

- `[SOURCE_FACT]` `docs/RECEIPT_TOPIC_QOS_CONTRACT.md`, Receipt Topic QoS
  Contract rev.5, full-document SHA-256
  `9f87f4d09ec50aacf8c0cf69e11bff8bceb4219b8d09f68998288907afb8302b`.
- `[SOURCE_FACT]` `docs/ACR_V3_OBSERVATION_BOUNDARY_CLOSURE.md`, ACR rev.7,
  full-document SHA-256
  `cb111c84c3b8f7d1393256b4c15f28c5f0bcafa1d2a84dde08e2cb0cd823ce0f`.
- `[SOURCE_FACT]` `docs/governance/decisions/QOS_REVISION_5_ACR_REVISION_7_BUNDLE_APPROVAL.md`
  (SHA-256 `8058273e144a2cc8703ea43ab544b854e1caa66f0785301e52b90027256acdd4`)
  records bundled approval dated `2026-10-06`. The transport contract ID is
  `mecanum.final-issued-receipt-topic-qos/v1`; the canonical JSON manifest
  SHA-256 is `a3bc1a965fc6885825ab961289fa4028862aa7af4b3f3156bc40542f7ee08f62`.
  The manifest hash was recomputed from the canonical JSON block in the QoS
  contract at this baseline.
- `[SOURCE_FACT]` Registry entries classify QoS rev.5 as
  `CANONICAL_APPROVED_DESIGN_CONTRACT`, ACR rev.7 as `CANONICAL_APPROVED_ACR`,
  and the approval record as `CANONICAL_GOVERNANCE_APPROVAL_RECORD`.

The approved bundle covers its recorded QoS/ACR design scope. It does not settle
the separate D2 user decisions about receipt lifecycle/creation ownership,
profile-specific issuance or transport-handoff boundary, failure/recovery, or
whether a future `deploy_real` handoff capability exists. Those questions remain
open below. Canonical document approval does not assert implementation or
runtime evidence.

Labels used below:

- `[SOURCE_FACT]`: directly stated by the cited integration source.
- `[ARCHITECTURE_FACT]`: requirement in the frozen Architecture DOCX.
- `[INFERENCE]`: conclusion from the facts, not wording explicitly stated by
  an authority.
- `[RECOMMENDATION]`: suggested review or acceptance criterion; not a PEP
  requirement or user decision.
- `UNAVAILABLE_FOR_REVIEW`: the reviewed authority does not identify the
  required owner, value, decision, or evidence.

The authoritative source order remains Architecture DOCX, approved contracts
or explicit decisions, then PEP/registry/ledger for sequencing and status. Drafts,
reports, candidate branches, and source artifacts do not silently become
contract authority.

## 2. WP-02 dependency disposition — resolved at this baseline

### 2.1 Canonical status and evidence

`[SOURCE_FACT]` PEP-001 rev.0.3.0 is active at this integration baseline. Its
“Ordered work packages” table keeps the historical `Initial status` values:
WP-02 `BLOCKED_BY_GOVERNANCE`, WP-03 `BLOCKED_BY_CONTRACT`, and WP-04
`BLOCKED_BY_CONTRACT`. The separate change-control section “WP-02 closure status
transition — PEP-001 rev.0.3.0” records `WP-02:
BLOCKED_BY_GOVERNANCE -> CLOSED` and states the current WP-02 status is `CLOSED`
on activation.

`[SOURCE_FACT]` The append-only ledger entry
`WP-02-CLOSE-CANONICAL-SOURCE-SELECTION` records the authorized transition
under PEP-001 rev.0.3.0. The PEP change-control record identifies the evidence
basis as WP-02I `IMPLEMENTED_OFFLINE_ONLY` covering V3 selection, the legacy
boundary, and source-registry enforcement at governance/source-selection level.
It explicitly distinguishes that evidence from automated runtime enforcement.

`[SOURCE_FACT]` PEP keeps WP-03 dependent on WP-02 (`02`) and required user
decisions. The WP-02 dependency is now recorded as satisfied; WP-03 remains
`BLOCKED_BY_CONTRACT` while its own required decisions remain unresolved. The
WP-02 transition did not change WP-03/WP-04 status, dependency, or authorization.

### 2.2 Packet finding

`[INFERENCE]` This packet has no remaining WP-02 closure question to ask. The
baseline PEP and ledger record WP-02 as `CLOSED`; this fact does not itself
close or formally start WP-03. The user decisions in §3 remain open.

## 3. WP-03 decision matrix

The PEP scopes WP-03 to final-issued receipt, collision/contact, and
map/scenario/hardware intake decisions. For each row, acceptance criteria below
are explicitly recommendations for user review; PEP does not provide detailed
group-level closure criteria.

### 3.1 Final-issued receipt

**Authority and status**

- `[ARCHITECTURE_FACT]` Architecture assigns final command selection/limiting
  to `SafetySupervisor` and sole `/cmd_vel` publication to
  `FinalTwistPublisher`. The previous-command observation is the physical
  final-issued command that has passed safety and been published. PPO action,
  decoded candidate, final-issued command, and measured twist have distinct
  semantics.
- `[SOURCE_FACT]` `docs/S3_D2_Final_Issued_Command_Receipt_Design_DRAFT.md`
  is `DRAFT — PENDING_USER_DECISION`; it says no receipt implementation or
  runtime path is created. `docs/S3_D2_Receipt_Ownership_User_Decision_Packet_DRAFT.md`
  labels its `FinalTwistPublisher` ownership choice as conditional/proposed.
- `[SOURCE_FACT]` PEP WP-04's constrained primitive deliverable permits exact
  receipt ID/SHA structural references, but prohibits receipt interface,
  bridge/history, safety/final-publisher runtime work in that deliverable.
- `[SOURCE_FACT]` At the baseline, the Canonical Source Registry and approval
  record identify QoS Topic Contract rev.5 and ACR rev.7 as a canonical,
  user-approved bundle (document hashes and transport-manifest hash are in §1).
  The QoS contract pins topic-level publisher/subscriber roles and the expected
  receipt-interface ID/SHA reference.
- `[SOURCE_FACT]` The D2 receipt design and ownership decision packet remain
  `DRAFT — PENDING_USER_DECISION`. Their lifecycle/creation ownership and
  profile-specific boundary decisions are not resolved merely by canonicalizing
  the topic-QoS/ACR bundle or recording a receipt-interface reference.

| Decision question for user | Source-listed options or current gap | Consequence/trade-off stated by sources | Evidence that can establish a decision | Suggested acceptance criterion |
|---|---|---|---|---|
| Who owns creation of the receipt? | Canonical QoS rev.5 names `FinalTwistPublisher` as the topic publisher and `V3ObservationIngress` as subscriber. The D2 user decision about the logical receipt-creation owner, its lifecycle responsibility, and its approver remains open; the topic publisher field alone does not settle that decision. D2 considers `SafetySupervisor`, `FinalTwistPublisher`, and bridge transport, with a conditional `FinalTwistPublisher` recommendation. | Safety acceptance alone does not prove crossing publish/handoff; topic publisher identity does not establish a created receipt or runtime path; bridge codec acceptance is not safety selection, ROS publish, MCU acknowledgement, or motor movement. | Static: approved D2/receipt record naming receipt owner and responsibilities while remaining consistent with canonical QoS. Runtime/profile evidence is separate. | `[RECOMMENDATION]` Select one logical receipt owner and explicit handoff from safety selection; do not infer implementation from the canonical topic role. |
| What event counts as a successful final boundary, for each profile? | For simulation, receipt creation is proposed only after `FinalTwistPublisher` successfully completes the local publish-issuance boundary once that boundary is defined and approved in the controlling D2 receipt contract; merely starting the publish call is insufficient. For `deploy_real`, the proposed boundary is a separately approved ROS-to-transport handoff owned by a logical transport egress/handoff role. That deployment boundary must be defined and approved in the D2/receipt contract before `deploy_real` can rely on it; it is not inferred from local `/cmd_vel` issuance, and the current contract does not establish support for it. | Successful local publish issuance does not prove DDS delivery, transport handoff, MCU acknowledgement, or actuator movement. A separate deployment handoff can establish only that the command crossed that approved handoff boundary. | Static: separately defined and approved simulation and deployment boundary semantics in the controlling receipt contract. Runtime/profile evidence remains a later obligation; none is claimed here. | `[RECOMMENDATION]` Define one successful boundary per profile, require successful completion before a ready receipt, and keep the `deploy_real` boundary pending until its contract approval. |
| How are identity, sequence and replay handled? | D2 binds the receipt directly to `EpisodeLifecycleIdentity` and `TransitionIdentity`; scenario/session linkage is indirect through `EpisodeLifecycle`, with no separate `ScenarioSessionBinding` field. D2 also asks for receipt ID and/or command sequence, uniqueness scope, replay handling, and reset/runtime-generation relation. Use `config_hash` only if the exact receipt/interface contract defines its semantics and provenance; do not assume a field or create a new hash. | Receipt identity and transition identity are not interchangeable; stale, duplicate, replayed, mismatched or future receipt must fail closed. Adding a session field would change the proposed D2 binding contract and require separate approval. | Static: versioned schema/identity rule and explicit provenance semantics for any approved hash field. Runtime: wrong-generation, duplicate/replay and barrier-alignment evidence if runtime use is later approved. | `[RECOMMENDATION]` Preserve direct lifecycle-plus-transition binding, indirect session linkage, and explicit uniqueness/replay/reset rules; add no session field or hash without an approved contract definition. |
| What physical-to-normalized rule supplies previous-issued observation values? | D2 draft requires axis order, limits/config version and hash, and migration behavior; no values or approved conversion rule are supplied. | Decoder-accepted action or raw PPO action cannot substitute for final-issued history. | Static: conversion specification and exact version/hash references. Any profile values require their own approved source. | `[RECOMMENDATION]` Conversion is deterministic, versioned, hash-bound and explicitly applied only to the post-safety final command. |
| What is the failure/recovery policy after publish but before transition commit? | D2 draft lists `STEP_ABORT`/`FAULT`, zero/inhibit owner, diagnostics retention, reset/restart policy, and non-rollback semantics as decisions. | A command already published cannot be represented as rolled back. | Static: approved lifecycle and responsibility contract. Runtime recovery claims require separately approved runtime evidence. | `[RECOMMENDATION]` Explicit fail-closed behavior, owner, retained evidence and reset/generation boundary; no fabricated successful receipt. |

`UNAVAILABLE_FOR_REVIEW`: D2 does not establish the user-selected receipt
creation owner/approver or resolve the complete lifecycle/provenance semantics.
QoS rev.5 pins a topic-level receipt-interface ID/SHA reference, but that
reference alone does not resolve the open D2 decisions. Do not treat QoS/ACR
bundle canonicalization as receipt implementation or `deploy_real` approval.

### 3.2 Collision/contact

**Authority and status**

- `[ARCHITECTURE_FACT]` Collision/contact is task/evaluator-side evidence, not
  policy observation. Missing or invalid required evidence must not be turned
  into a fabricated “no collision” fact. Architecture defines termination
  precedence with collision ahead of goal, bounds, stuck, and episode limit.
- `[SOURCE_FACT]` `docs/S3_D3_ContactLatch_And_Collision_Fact_Contract_DRAFT.md`
  is marked `BLOCKED_BY_RUNTIME_EVIDENCE`. It says static collision geometry
  does not establish a contact event, source, latch, or policy.
- `[SOURCE_FACT]` The contract lists user decisions for contact classes and
  behaviors, and separately lists runtime evidence needed for stable scoped
  names, event ordering, reset clearing, timestamps, and end-to-end behavior.

| Decision question for user | Source-listed options or current gap | Consequence/trade-off stated by sources | Evidence that can establish a decision | Suggested acceptance criterion |
|---|---|---|---|---|
| Which contacts count as collision: wheel–ground, self-contact, sensor links, chassis, and world objects? | The draft lists exclude/include/classify-separately options for wheel–ground; exclude/include selected/all for self-contact and sensor links; chassis by counterpart; world objects all/allowlist/category rules. No option is selected. | Classification affects which contacts become collision facts; normal support, accessory contact, and world contact cannot be assumed equivalent. | Static: approved filter decision and policy ID/version/hash. Runtime: actual contact identity/message evidence validates selected classes. | `[RECOMMENDATION]` Every relevant class has an explicit include/exclude/classification rule, with no unlisted default. |
| What are the simulation producer/evaluator roles and source boundary? | `[RECOMMENDATION — PROPOSED FOR USER DECISION]` Assign `SimulationContactIngress` as the logical producer role receiving the simulator's authoritative physics-contact event stream and creating a typed candidate with producer identity/sequence, lifecycle/transition identity, source timestamp/time domain, entity/link identity, and filter-policy ID/version/hash. Assign `EpisodeEvaluator` as the logical owner of `ContactLatch` and per-transition aggregation into a collision fact. These are role proposals, not claims that modules exist. No contact producer is approved for `deploy_real` until a hardware producer and its evidence are separately defined and approved. | The source is physics-contact events, not an inference from LiDAR, odometry, pose, raw Ground Truth policy input, or imagery. Missing event/provenance is not “no collision.” Static names remain candidates; no implementation/plugin/API is selected. | Static: approve or replace the logical roles, source boundary, typed fields, and filter identity. Future evidence plan must cover contact/no-contact, duplicate/conflicting identity, out-of-order and simultaneous events, timestamp/lifecycle binding, reset clearing, and provenance. These checks have not been performed or evidenced here. | `[RECOMMENDATION]` Approve a simulation producer/evaluator role split and explicit source/provenance contract; leave `deploy_real` producer pending until its hardware source and evidence are approved. |
| How should duplicates and simultaneous contacts be represented? | Draft options include event-identity/producer-sequence deduplication and one aggregate fact/ordered list/priority rule. No rule selected. | Deterministic consume-once and replay behavior is required for reliable transition association. | Static: selected ordering/dedup rule. Runtime: repeated-event and same-tick multi-contact evidence. | `[RECOMMENDATION]` A deterministic, versioned rule covers duplicate IDs and simultaneous events. |
| How do action interval, reset and generation boundaries work? | Draft requires an action barrier, active `TransitionIdentity`, reset/new-generation clearing and simulation-time provenance. These are not complete runtime contracts. | A contact from another action/episode cannot be reused; missing required fact leads to abort/fault rather than “no collision.” | Static: lifecycle/transition and clock-domain contract. Runtime: interval alignment, stale/replay rejection, reset clearing. | `[RECOMMENDATION]` Exact interval/barrier and clearing rules are written and map to one transition; evidence shows no cross-generation reuse before any runtime claim. |

`[SOURCE_FACT]` D3 does not name an approved contact producer or evaluator
owner. The `SimulationContactIngress` / `EpisodeEvaluator` assignment above is
only a proposed logical-role disposition for user review; it does not claim an
existing module, approved producer, or completed evidence plan. `deploy_real`
has no approved contact producer in the reviewed authority.

### 3.3 Map, scenario and hardware intake

**Authority and status**

- `[ARCHITECTURE_FACT]` `artifacts/maps/<map_id>` is the sole map source of
  truth. Architecture specifies `map.yaml`, `map.pgm`, `map_manifest.json`,
  `metadata.yaml`, optional pose-graph material, canonical manifest fields and
  SHA-256 `map_content_hash`; a draft map is not an approved navigation map.
- `[SOURCE_FACT]` Registry marks canonical map location
  `REQUIRED_CANONICAL_MAP_LOCATION_MISSING`; ROS-package maps are not canonical.
- `[SOURCE_FACT]` Registry marks
  `artifacts/hardware/<hardware_profile_id>/hardware_manifest.yaml` as
  `CANONICAL_LOCATION_PRESENT_VALIDITY_PENDING`.
- `[SOURCE_FACT]` Existing
  `artifacts/hardware/mecanum_f411_tb6612_ga25_370_rev_a/hardware_manifest.yaml`
  keeps multiple physical geometry/encoder/sign values at `TBD_MEASURED` or
  null. Its `approval.yaml` is `DRAFT`, with null approved hash and required
  evidence pending. No value is supplied or inferred by this packet.
- `[SOURCE_FACT]` `docs/S3_Simulation_Scenario_Artifact_Contract_DRAFT.md`
  proposes `artifacts/scenarios/`, but says exact directory convention,
  canonical serialization and registry process remain `REQUIRED_DECISION`;
  no scenario artifact exists by virtue of the draft.

| Decision question for user | Source-listed options or current gap | Consequence/trade-off stated by sources | Evidence that can establish a decision | Suggested acceptance criterion |
|---|---|---|---|---|
| What is the first map intake and approval boundary? | Canonical path is locked by Architecture, but no canonical map artifact, map ID, manifest or `approval_status=approved` is present in the registry. | Mutable ROS-package copies cannot serve as source of truth; map content and identity must be checked against manifest/hash. | Static: selected map artifact identity, canonical manifest schema/hash and approval record. Map survey/validation evidence is separate where required. | `[RECOMMENDATION]` Intake rule names canonical directory, required files/roles, hash procedure, map owner and approval authority; an actual artifact is not fabricated in this packet. |
| What scenario artifact location/schema and first scenario should be selected? | Draft lists scenario ID/version, world name/file SHA, coordinate reference, goal, valid area/boundary rule, forbidden zones, optional start catalog, randomization extension and artifact-change policy as decisions. It proposes `artifacts/scenarios/` but leaves convention/registry unresolved. | Scenario values cannot be inferred from legacy waypoints, visual maps, SDF/world geometry, or an assumed frame relation; values bind to scenario/world identity and hashes. | Static: approved schema, serialization/path and provenance rules. Runtime/world evidence and user-reviewed coordinate suitability are separate for concrete values. | `[RECOMMENDATION]` Approve location/schema and a no-default, hash-bound intake rule; keep concrete coordinates and bounds absent until their evidence and approval exist. |
| What hardware profile/measurement and approval evidence is required? | Registry identifies the hardware-manifest path, but the existing manifest has `TBD_MEASURED`/null values including wheel dimensions, wheelbase/track, encoder scale/gear ratio/ticks and wheel signs. Approval remains draft. | Architecture requires geometry/configuration hash agreement across bridge, firmware and generated geometry; no value may be guessed or copied from simulation/another robot. | Static: manifest schema, hash/canonicalization and evidence-to-field rules. Physical measurement/bench/HIL evidence is required for measured fields and hardware approval. | `[RECOMMENDATION]` Identify measurement owner/approver, required evidence per field, hash/approval sequence and fail-closed treatment of TBD; retain every unavailable value as `TBD_MEASURED`. |

`UNAVAILABLE_FOR_REVIEW`: User/architect, map custodian, scenario author,
hardware measurement owner and approver are not assigned by the reviewed PEP,
registry, or contracts. The user/architect should name accountable roles; this
packet assigns no person, profile, map, scenario, producer, or measured value.

### 3.4 Decision-to-record and change-control mapping

The mappings below identify existing records where verified. A draft or
proposed vehicle is not canonical authority. Where no approved record exists,
the vehicle is explicitly `PROPOSED/PENDING_AUTHORITY` until identified and
approved through the applicable governance process.

| Disposition | Record/change-control vehicle | Current status and boundary |
|---|---|---|
| WP-02 closure/status transition (historical routing only; not an open decision here) | `docs/governance/PROJECT_EXECUTION_PLAN.md` PEP-001 rev.0.3.0, “WP-02 closure status transition”; append-only `docs/governance/PROJECT_PROGRESS_LEDGER.md` entry `WP-02-CLOSE-CANONICAL-SOURCE-SELECTION`. | WP-02 is `CLOSED` at this baseline; the historical `Initial status` remains `BLOCKED_BY_GOVERNANCE`. No further WP-02 disposition is requested in this packet. |
| Receipt lifecycle boundary, ownership, binding/schema decisions | Canonical topic-QoS vehicle: `docs/RECEIPT_TOPIC_QOS_CONTRACT.md` rev.5 and bundled `docs/ACR_V3_OBSERVATION_BOUNDARY_CLOSURE.md` rev.7, recorded by `docs/governance/decisions/QOS_REVISION_5_ACR_REVISION_7_BUNDLE_APPROVAL.md`. Separate D2 decision vehicles: `docs/S3_D2_Final_Issued_Command_Receipt_Design_DRAFT.md` and `docs/S3_D2_Receipt_Ownership_User_Decision_Packet_DRAFT.md`. | QoS/ACR bundle is canonical for its approved design scope. D2 records remain drafts; the QoS topic role/reference does not resolve receipt creation ownership, profile boundary details, lifecycle/failure policy, or support for `deploy_real`. Use approved ACR change control only if a future decision changes public/frozen Architecture contract. |
| Collision/contact policy, producer roles, and fact contract | `docs/S3_D3_ContactLatch_And_Collision_Fact_Contract_DRAFT.md`. | D3 is a draft marked `BLOCKED_BY_RUNTIME_EVIDENCE`; role assignment remains proposed. Runtime evidence is a separate later obligation and is not claimed present. |
| Map intake | Architecture §48 defines `artifacts/maps/<map_id>/map_manifest.json` and map hash semantics. `docs/governance/CANONICAL_SOURCE_REGISTRY.md` is the verified registry record for the missing canonical map location. | The canonical map artifact/location is currently classified missing. A future manifest/artifact is not created or approved by this packet; registry changes require an approved work package. |
| Scenario root, schema, values, and provenance policy | `docs/S3_Simulation_Scenario_Artifact_Contract_DRAFT.md`; `docs/governance/CANONICAL_SOURCE_REGISTRY.md` for any approved source-location/classification update. | Scenario contract is draft; `artifacts/scenarios/` is proposed, with convention/serialization/registry process still `REQUIRED_DECISION`. Canonical effect is pending contract and registry authority. |
| Hardware measurements and approval | Existing `artifacts/hardware/mecanum_f411_tb6612_ga25_370_rev_a/hardware_manifest.yaml` and `artifacts/hardware/mecanum_f411_tb6612_ga25_370_rev_a/approval.yaml`; physical/HIL evidence must be assigned to its applicable later gate/work package. | The manifest retains `TBD_MEASURED` values; approval is `DRAFT` with required evidence pending. The measurement owner and hardware technical-authority/approver role must be defined in the approval record; no person or value is assigned here. |
| Any WP status transition, including WP-03 | `docs/governance/PROJECT_EXECUTION_PLAN.md` (“Plan change control”) establishes the authorized PEP transition; `docs/governance/PROJECT_PROGRESS_LEDGER.md` receives an append-only evidence/result entry after approval. | A proposal or ledger entry alone does not enact a transition. This packet makes no status change. |

`[RECOMMENDATION]` Treat this table as a routing proposal for user review.
It does not amend any listed record, make a draft canonical, or imply that a
future runtime, HIL, or physical-measurement obligation has been fulfilled.

## 4. Work order and status boundaries

### 4.1 Pre-work in this packet

This file is only a draft decision aid for user review. It neither opens WP-03
formally nor satisfies a dependency or acceptance criterion.

### 4.2 Conditions to begin WP-03 formally

`[SOURCE_FACT]` PEP-001 rev.0.3.0 lists WP-03 dependency `02` and required
user decisions, and keeps the historical `Initial status` as
`BLOCKED_BY_CONTRACT`. The current PEP change-control record and ledger record
WP-02 as `CLOSED`. PEP does not define a separate design-only start gate.

`[INFERENCE]` The WP-02 dependency is satisfied at this baseline. The required
WP-03 user decisions remain open, so WP-03 is still `BLOCKED_BY_CONTRACT`; this
pre-work packet does not itself formally start WP-03.

`[RECOMMENDATION]` Before proposing formal WP-03 start, settle the in-scope
contract decisions and identify accountable logical owner roles. This
recommendation does not prevent the user from reviewing this pre-work draft.

### 4.3 Conditions to propose group and WP-03 closure

`[SOURCE_FACT]` PEP defines WP-03 scope and dependency, but does not state
item-by-item acceptance criteria or explicitly say that draft completion closes
the work package.

`[RECOMMENDATION]` For WP-03 contract closure, record each in-scope decision,
the exact controlling contract/record, and any future evidence obligation with
its owner/role and later gate or work package. Listing an obligation does not
resolve an in-scope contract decision, and it must not imply that runtime, HIL,
or physical-measurement evidence already exists.

Execution or collection of runtime, HIL, or physical-measurement evidence
belongs to the corresponding later gate or work package. The fact that such
future evidence has not yet been collected does not by itself prevent closing
the WP-03 contract decisions. If a contract decision within WP-03 scope remains
unresolved, WP-03 must remain open.

Propose overall WP-03 closure only after all three groups have approved
dispositions and their cross-document references have been reconciled, with no
unresolved decision inside WP-03 scope. Record any status transition through
the authorized governance process; this packet does not update PEP or ledger.

### 4.4 Separate WP-04 conditions

`[SOURCE_FACT]` PEP keeps WP-04 `BLOCKED_BY_CONTRACT` and requires WP-03,
user-approved V3 scope closure, recorded semantic-bundle closure for S2 rev.2,
Observation Input Contract rev.6 and V3 Observation Boundary rev.7, and a
separate exact implementation packet. The constrained first deliverable is
non-integrated structural primitives only and is not code authorization.

The canonical QoS rev.5 / ACR rev.7 bundle has its own approved design scope,
but its approval record says it does not close WP-03, change status/dependency,
or make a Gate A implementation packet eligible. This packet does not change
WP-04's dependency on WP-03, extend that bundle approval, authorize Gate A
implementation, or grant code/runtime permission. WP-04 remains
`BLOCKED_BY_CONTRACT` under PEP-001 rev.0.3.0.

## 5. User review questions summary

1. Which logical role owns receipt creation and its lifecycle/provenance
   responsibility, given that canonical QoS rev.5 already identifies the topic
   publisher/subscriber roles? What profile-specific successful boundary,
   identity/binding, normalization and post-publish failure/recovery rules do
   you approve? For `deploy_real`, do not infer a handoff capability from local
   `/cmd_vel` issuance; the separate handoff boundary remains to be defined and
   approved.
2. Which contact classes count as collisions? Do you approve or replace the
   proposed simulation roles `SimulationContactIngress` and
   `EpisodeEvaluator`, authoritative physics-contact source boundary, typed
   provenance, and future evidence plan? What filter, deduplication, interval,
   clock and reset rules should govern them, and what remains pending for
   `deploy_real`?
3. What map intake/approval rule, scenario location/schema/decision set, and
   hardware measurement/approval responsibility should be adopted? Who owns
   each evidence item? Keep unavailable physical values as `TBD_MEASURED`.
4. For each disposition, do you agree with the proposed record/change-control
   vehicle in §3.4, or should another authorized record be identified?
5. After the in-scope decisions are resolved, what evidence obligations and
   responsible logical roles should be recorded for their later gates/work
   packages before a WP-03 closure transition is proposed?

## 6. Canonical PEP status and packet finding

### Current canonical status at the pinned integration baseline

`[SOURCE_FACT]` PEP-001 rev.0.3.0, “WP-02 closure status transition” and
“Ordered work packages”, together with ledger entry
`WP-02-CLOSE-CANONICAL-SOURCE-SELECTION`, records:

```yaml
CURRENT_PEP_STATUS:
  WP-02: CLOSED
  WP-03: BLOCKED_BY_CONTRACT
  WP-04: BLOCKED_BY_CONTRACT
```

The WP-02 transition is `BLOCKED_BY_GOVERNANCE -> CLOSED`. PEP's `Ordered work
packages` table retains historical `Initial status` values: WP-02
`BLOCKED_BY_GOVERNANCE`, WP-03 `BLOCKED_BY_CONTRACT`, and WP-04
`BLOCKED_BY_CONTRACT`. Those historical values are not current WP-02 status and
were not rewritten.

### Packet finding — not a status transition

`[INFERENCE]` WP-02's dependency is recorded as satisfied at this integration
baseline. WP-03 remains blocked on its required contract decisions. This packet
reports those facts for user review; it makes no status transition and does
not formally open or close WP-03.

```text
CODE_AUTHORIZATION: NOT_GRANTED
RUNTIME_NOT_APPROVED
```

This packet remains `DRAFT_FOR_USER_REVIEW`. It is not canonical authority.
