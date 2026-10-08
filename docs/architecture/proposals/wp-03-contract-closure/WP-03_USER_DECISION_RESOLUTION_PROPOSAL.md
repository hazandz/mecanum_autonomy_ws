# WP-03 Contract Closure — Proposed User Decision Resolution

**Work package:** WP-03-CONTRACT-CLOSURE-DECISION-RESOLUTION-PROPOSAL
**Status:** DRAFT_FOR_USER_APPROVAL_AND_INDEPENDENT_AUDIT
**Mode:** DOCUMENTATION_ONLY
**Integration baseline:** origin/integration/implementation@9a4c0d233e8237f01a04880fe99e8a3114528f4c
**Baseline packet reviewed:** wp-03-user-decision-packet-baseline-9a4c0d2@15009ee9c374661d3ab6018ffa46292e096dceff
**Architecture SHA-256:** f0fb1ebede5f4fa18604610c04bb13587d456173b4fd942dba77e44d49777860

## 1. Purpose and effect

This document turns the open questions recorded in the baseline WP-03 user
decision packet into one proposed decision set for review by the Project
Owner/User.

It is a proposal. It has no authority until an independent audit, explicit user
approval, and separate canonical integration record its approved dispositions.
It does not alter PEP-001, the Progress Ledger, the Canonical Source Registry,
any contract, or a work-package status.

The historical WP-03 packet remains an immutable pre-work snapshot. This
proposal relies on its refreshed baseline review; it does not overwrite that
packet.

## 2. Fixed baseline facts

At the pinned integration baseline:

- PEP-001 revision 0.3.0 records WP-02 as **CLOSED**.
- WP-03 remains **BLOCKED_BY_CONTRACT**.
- WP-04 remains **BLOCKED_BY_CONTRACT**.
- Receipt Topic QoS Contract revision 5 is canonically recorded with
  full-document SHA-256
  **9f87f4d09ec50aacf8c0cf69e11bff8bceb4219b8d09f68998288907afb8302b**.
- ACR V3 Observation Boundary Closure revision 7 is canonically recorded with
  full-document SHA-256
  **cb111c84c3b8f7d1393256b4c15f28c5f0bcafa1d2a84dde08e2cb0cd823ce0f**.
- The Receipt Topic QoS transport identity remains
  **mecanum.final-issued-receipt-topic-qos/v1**; its canonical manifest SHA-256
  is
  **a3bc1a965fc6885825ab961289fa4028862aa7af4b3f3156bc40542f7ee08f62**.
- The QoS/ACR bundled approval is limited to its stated governance and
  design-document scope. It does not resolve the D2 receipt decisions below,
  close WP-03, satisfy WP-04 implementation prerequisites, authorize code, or
  approve runtime activity.

The proposed decisions below respect those facts.

## 3. Proposed D2 final-issued receipt decisions

### D2-1 — Logical receipt owner

**Proposed decision:** **FinalTwistPublisher** owns creation of
**FinalIssuedCommandReceipt** after the selected final command crosses the
applicable successful final boundary.

**SafetySupervisor** remains the sole owner of final safety arbitration,
validation, limiting, smoothing, and final-command selection. The receipt owner
records the resulting safety-selected command and its provenance; it does not
repeat or bypass safety arbitration.

**Reason:** the Architecture assigns **FinalTwistPublisher** sole final
**/cmd_vel** publication, while safety selection is a separate responsibility.

### D2-2 — Profile boundary

**Proposed decision:**

| Profile | Proposed successful boundary | Receipt meaning |
| --- | --- | --- |
| Simulation | **FinalTwistPublisher** has successfully locally issued the final selected **Twist** through the approved simulation **/cmd_vel** boundary. Starting a publish call is insufficient. | The final selected command crossed the defined local ROS publication boundary for the active transition. |
| **deploy_real** | No final handoff boundary is approved in this proposal. The profile remains unavailable for receipt use until a later approved D2 contract defines a ROS-to-transport handoff role and success condition. | No claim about UART delivery, MCU acknowledgement, watchdog refresh, motor-driver actuation, or motion is permitted. |

A simulation receipt is never proof of Gazebo application time, robot movement,
collision state, actuator acknowledgement, or achieved velocity.

### D2-3 — Identity, source, and sequence

**Proposed decision:**

1. A receipt binds directly to the active **EpisodeLifecycleIdentity** and
   **TransitionIdentity**.
2. It carries no **ScenarioSessionBinding**. The committed scenario session is
   linked indirectly through **EpisodeLifecycle**.
3. **source**, **sequence**, **reset_epoch**, **runtime_generation**, and
   **source_instance_id** mirror the approved **CommandEnvelope** fields and
   constants. Accepted sources are **POLICY**, **NAV2**, **TELEOP**, and
   **SAFE_STOP**; **UNKNOWN** is non-ready.
4. **FinalTwistPublisher** owns **final_publisher_instance_id**. It changes
   when that publisher process restarts.
5. **final_publish_sequence** starts at 1 for each
   **final_publisher_instance_id** and increases strictly for every emitted
   receipt. It does not reset at **reset_epoch**.
6. The pair **(final_publisher_instance_id, final_publish_sequence)** is the
   receipt transport identity. It is separate from **TransitionIdentity** and
   cannot substitute for it.
7. **CommandArbiter**, under **SafetySupervisor** authority, creates a new
   epoch **SOURCE_SAFE_STOP** zero envelope. **FinalTwistPublisher** does not
   fabricate an envelope.

Duplicate identity, replay, non-monotonic sequence, stale or future transition,
lifecycle mismatch, source mismatch, or invalid identity is fail-closed.

### D2-4 — Command representation and normalization

**Proposed decision:**

- The receipt's physical command is the final safety-selected
  **base_link** planar command **(vx, vy, wz)**. All components are finite;
  **linear.z**, **angular.x**, and **angular.y** are zero.
- A normalized final command may be used only when the controlling
  profile/configuration contract provides an exact conversion rule, axis order,
  limits, version, and hash/provenance reference.
- No numeric limit, **config_hash**, resolved configuration, or profile value
  is invented by this decision.
- If the exact conversion reference is unavailable or incompatible, no ready
  normalized receipt is admitted.

This records a rule for later contract work. It does not create a resolved
configuration, select profile values, or authorize a receipt interface.

### D2-5 — Failure and recovery

**Proposed decision:**

- A failed publish or handoff never produces a ready receipt.
- If a final command has already crossed the selected boundary and a later
  observation, task fact, reward, or termination validation fails, the
  transition becomes **STEP_ABORT** or **FAULT**; it does not claim that the
  already-issued command was rolled back.
- **SafetySupervisor** owns the selection of any zero/inhibit safe action.
  **CommandArbiter** creates its envelope, and **FinalTwistPublisher** may
  issue it only through a separately approved command path.
- The failure record retains lifecycle identity, transition identity, command
  source, receipt transport identity, boundary result, and the diagnostic
  reason. A reset or new runtime generation clears staged and committed receipt
  state before another lifecycle uses it.

### D2-6 — Evidence disposition

The following are future obligations, not evidence claimed by this proposal:

- simulation final-boundary behavior;
- duplicate, replay, generation, and transition-mismatch rejection;
- failed publish/handoff behavior;
- action-barrier alignment;
- profile-specific transport behavior;
- any **deploy_real** handoff behavior.

The controlling D2 receipt contract and interface record must be updated through
a separate approved documentation work package before any implementation
proposal depends on these choices.

## 4. Proposed D3 collision/contact decisions

### D3-1 — Simulation-only source boundary

**Proposed decision:** collision is a hidden evaluator-side fact. For the
simulation profile, the only accepted future source is an authoritative
physics-contact event stream delivered through a logical
**SimulationContactIngress** role.

**SimulationContactIngress** creates typed contact candidates with producer
identity, event identity, lifecycle and transition identity, source timestamp
and time domain, involved entity/link identities, and filter-policy
identity/version/hash. **EpisodeEvaluator** owns **ContactLatch** and
per-transition aggregation into **CollisionFact**.

These are role decisions for a future contract. They do not claim that a module,
Gazebo plugin, bridge, ROS topic, or runtime contact producer exists.

No **deploy_real** collision producer is approved. It remains a separate future
hardware contract and evidence item.

### D3-2 — Collision classification policy

**Proposed decision:**

| Contact class | Proposed classification |
| --- | --- |
| Wheel–ground support | Exclude. Normal support contact is not a collision fact. |
| Robot self-contact | Exclude. It is not a training collision fact for the fixed robot model. |
| LiDAR, camera, and other sensor-link contact with non-ground external world objects | Include. External impact involving an attached sensor is a collision fact. |
| Base/chassis contact with non-ground external world objects | Include. |
| External world contacts from walls, boxes, shelves, pallets, stairs, or other non-ground objects | Include. |
| Ground contact through a non-wheel robot link | Include. |

A future filter contract must identify contact classes from emitted runtime
entity/link identities. Static SDF names are not enough to produce or match a
runtime collision event.

### D3-3 — Ordering, aggregation, and lifecycle

**Proposed decision:**

- Deduplicate with **(producer_instance_id, event_id)** within one active
  lifecycle and transition.
- Any accepted collision-class event in the active action interval produces one
  aggregate **CollisionFact(collision=true)** for that transition.
- Simultaneous accepted events retain a stable ordered diagnostic list of their
  identities; the aggregate collision result does not depend on arrival order.
- A candidate is accepted only after the action barrier and only if it matches
  the active lifecycle, transition, time domain, and filter-policy identity.
- Reset or new runtime generation clears staged candidates, deduplication state,
  consumed-event state, and latch state.
- Missing, stale, malformed, mismatched, or unavailable contact provenance is
  not **no collision**. When the fact is required, the outcome is
  **STEP_ABORT** and **FAULT**.

The existing precedence remains
**collision > goal_reached > out_of_bounds > stuck > episode_limit**.

### D3-4 — Future evidence plan

Before runtime work can rely on the future D3 contract, its evidence plan must
cover contact and non-contact behavior, event identity stability,
duplicate/replay behavior, simultaneous events, timestamp/lifecycle binding,
action-interval alignment, reset clearing, and end-to-end provenance.

This proposal does not claim that this evidence exists.

## 5. Proposed map, scenario, and hardware intake decisions

### MSH-1 — Map intake

**Proposed decision:**

- **artifacts/maps/<map_id>/** remains the only canonical map root.
- A future **MapCustodian** role prepares **map.yaml**, **map.pgm**,
  **map_manifest.json**, and **metadata.yaml** with the required map identity
  and **map_content_hash**.
- The Project Owner/User approves a map only through its immutable manifest and
  evidence record.
- ROS-package map copies may be used as noncanonical inputs during preparation
  but never become the canonical map source by themselves.
- No map ID, map coordinates, map hash, navigation approval, or runtime map
  evidence is selected by this decision.

### MSH-2 — Scenario artifact convention

**Proposed decision:**

- The canonical scenario root is **artifacts/scenarios/<scenario_id>/**.
- A scenario has an explicit **scenario_id**, **scenario_version**,
  **scenario_content_sha256**, selected Gazebo/SDF world identity and hash, and
  **GT_ODOM_2D** coordinate reference.
- The future scenario contract must name its canonical serialization and exact
  filename before a concrete scenario is admitted. It must compute the
  scenario-content hash over that selected serialization.
- A **ScenarioCustodian** role prepares an artifact; the Project Owner/User
  approves it.
- Concrete goal, valid-area, forbidden-zone, start-pose, and randomization
  values remain absent until coordinate provenance is reviewed. Randomization is
  deferred to a later versioned extension.

This resolves the ownership and admission boundary without fabricating a first
scenario or its values.

### MSH-3 — Hardware profile and measurement governance

**Proposed decision:**

- The current profile remains
  **mecanum_f411_tb6612_ga25_370_rev_a**.
- Every field marked **TBD_MEASURED** or null stays unavailable and must fail
  closed. No value may be copied from simulation, a visual estimate, or another
  robot.
- A **Hardware Measurement Owner** role is accountable for physical
  measurements and bench evidence. A **Hardware Technical Approver** role,
  designated by the Project Owner/User, reviews the evidence and the canonical
  hardware-config hash.
- Required later evidence remains the existing geometry measurement,
  encoder-scale/quadrature verification, wheel/motor/encoder sign bench test,
  UART reconnect test, hardware e-stop test, command-watchdog test, TB6612
  current/thermal test, and power-integrity test.
- **approval_status: DRAFT** and **motor_enable_allowed: false** remain in
  force until their approved evidence record changes them.

## 6. Required downstream records

If the Project Owner/User approves this decision set after independent audit,
a separate documentation work package must update and reconcile the following
records before a WP-03 closure transition is considered:

| Decision group | Controlling record to update or create | Required outcome |
| --- | --- | --- |
| D2 receipt | **docs/S3_D2_Final_Issued_Command_Receipt_Design_DRAFT.md** and **docs/S3_D2_Receipt_Ownership_User_Decision_Packet_DRAFT.md**; any required versioned receipt interface/contract record | Record owner, profile boundary, identity/sequence, conversion-reference rule, and failure behavior without claiming implementation. |
| D3 contact | **docs/S3_D3_ContactLatch_And_Collision_Fact_Contract_DRAFT.md** | Record the simulation producer/evaluator roles, classification policy, aggregation, lifecycle rule, and future evidence plan. |
| Map and scenario | Scenario contract and the approved canonical-source record, if a new source path/classification is needed | Record artifact convention, accountable roles, hash/provenance requirements, and absence of concrete values until approved evidence exists. |
| Hardware | **artifacts/hardware/mecanum_f411_tb6612_ga25_370_rev_a/approval.yaml** or an approved successor record | Record accountable roles and retain all measurement obligations and fail-closed **TBD_MEASURED** treatment. |
| WP-03 governance | PEP change-control and append-only Progress Ledger only after the controlling records are canonically integrated and their decisions are audited | Record a status transition only if every in-scope WP-03 decision is resolved and cross-record references are reconciled. |

## 7. Explicit non-authorizations

This proposal does not:

- close or formally start WP-03;
- modify WP-04's dependency on WP-03;
- authorize a Gate A implementation packet;
- authorize source-code edits, builds, tests, ROS, Gazebo, Nav2, PPO, HIL,
  hardware, **deploy_real**, or real-robot operation;
- assert that a receipt interface, contact producer, map, scenario artifact,
  hardware measurement, or runtime evidence exists.

    WP-02: CLOSED
    WP-03: BLOCKED_BY_CONTRACT
    WP-04: BLOCKED_BY_CONTRACT
    CODE_AUTHORIZATION: NOT_GRANTED
    RUNTIME_NOT_APPROVED

## 8. User decision block

The Project Owner/User may approve, reject, or amend each proposed group below
only after its independent audit reports that this proposal faithfully preserves
the Architecture and current canonical contracts.

| Decision group | Proposed disposition | User disposition |
| --- | --- | --- |
| D2 final-issued receipt | Sections 3.1–3.6 | PENDING_USER_DECISION |
| D3 collision/contact | Sections 4.1–4.4 | PENDING_USER_DECISION |
| Map/scenario/hardware intake | Sections 5.1–5.3 | PENDING_USER_DECISION |
| Record-routing and future evidence obligations | Section 6 | PENDING_USER_DECISION |

A later user approval must cite this proposal's branch, commit, and exact file
SHA-256, then authorize the separate contract-reconciliation work package.