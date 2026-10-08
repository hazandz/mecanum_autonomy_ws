# WP-03 Contract Closure — Authorized Decision Dispositions

**Record status:** `DRAFT_FOR_INDEPENDENT_AUDIT_AND_CANONICAL_INTEGRATION`
**Work package:** `WP-03-APPROVED-DECISION-CONTRACT-RECONCILIATION`
**Integration baseline:** `2e7a2980cb75f0567182ea694c04328d7d8643e0`
**Candidate branch:** `wp-03-decision-contract-reconciliation-2e7a2980`
**Decision authority:** `Project Owner/User` authorized the assistant to select and record the dispositions below.
**Decision date:** `2026-10-08`

## 1. Provenance and effect

The authorized dispositions are taken from the audited user decision packet:

- Path: `docs/architecture/proposals/wp-03-contract-closure/WP-03_USER_DECISION_RESOLUTION_PROPOSAL.md`
- Branch: `wp-03-decision-packet-baseline-2e7a2980`
- Commit: `473d1cc6265dc14230fa47a89546b14a9de2a6eb`
- SHA-256: `3559f21a07520f10ac1dceb0c2e6f888597a0215a63a5b8b91fce10d340e583c`
- Independent-audit verdict supplied by the Project Owner/User: `READINESS_FOR_USER_REVIEW: APPROVABLE`.

This record is a candidate. Its dispositions become part of the canonical
contract records only after this candidate is independently audited and
canonically integrated. The supplied audit verdict concerns readiness for user
review; it is not an audit of this reconciliation candidate.

## 2. D2 — final-issued command receipt

**Authorized disposition:** packet §§3.1–3.6.

- `FinalTwistPublisher` owns receipt creation after the final selected command
  crosses the applicable successful boundary. `SafetySupervisor` remains the
  sole owner of arbitration, validation, limiting, smoothing, and final-command
  selection.
- Simulation receipt creation follows successful local issuance at the approved
  simulation `/cmd_vel` boundary; starting a publish call is insufficient.
  This receipt does not prove DDS delivery, Gazebo application, actuator
  acknowledgement, or robot movement.
- `deploy_real` has no approved receipt/handoff boundary. Receipt use remains
  unavailable until a separate D2 contract defines and approves a
  ROS-to-transport handoff role and success condition.
- Bind directly to `EpisodeLifecycleIdentity` and `TransitionIdentity`, using
  the pinned v2 schema's primitive fields. Scenario/session linkage is indirect
  through `EpisodeLifecycle`; no `ScenarioSessionBinding` is added.
- Preserve `CommandEnvelope` source/sequence and lifecycle semantics. The
  `FinalTwistPublisher` instance and `final_publish_sequence` provide separate
  transport identity; final publish sequence starts at 1 per publisher
  instance, increases strictly, and does not reset at `reset_epoch`.
- `final_command` is the finite physical `base_link` planar command after
  safety selection. Normalized reuse requires an exact approved conversion
  rule and provenance; this record selects no limits, profile value, or
  `config_hash`, and does not add wire fields.
- A failed publish/handoff never produces a ready receipt. A later failure
  after issuance is `STEP_ABORT` or `FAULT` without a rollback claim.
  `SafetySupervisor` selects any safe action; `CommandArbiter` creates its
  envelope. Reset clears staged/committed receipt state before another
  lifecycle uses it.
- Future obligations remain: simulation boundary, duplicate/replay and
  generation/transition rejection, failed publish/handoff, action-barrier
  alignment, profile-specific transport, and any future deploy handoff
  behavior. These are not evidence claims.

The canonical v2 schema remains at
`ros2_ws/src/mecanum_nav_rl_interfaces/msg/FinalIssuedCommandReceipt.msg`,
SHA-256 `0c6446674bf17373ec646519043f506a9a7a15f95d5fdd10829b0cedb956500a`.
This decision record does not modify that schema or the already integrated
QoS6/ACR8 bundle.

## 3. D3 — collision/contact

**Authorized disposition:** packet §§4.1–4.4; Architecture §§15–16 remain the
controlling authority.

- `SimulationContactIngress` is only a proposed logical ingress role receiving
  the simulator's authoritative physics-contact event stream and creating
  typed candidates. It does not replace or bypass generated contact
  instrumentation → Gazebo `gz.msgs.Contacts` → `ros_gz_bridge` →
  `/mecanum/contacts` → `ContactLatch`.
- `EpisodeEvaluator` owns `ContactLatch` and per-transition `CollisionFact`
  aggregation as logical roles; no module or runtime producer is claimed to
  exist.
- Valid current-epoch contact sets `contact_active = True` and
  `collision_pulse_pending = True`. During normal observation updates, only a
  valid explicit-empty observation for the current epoch may set
  `contact_active = False`; it does not clear a pending pulse.
- Silence, missing/delayed/stale messages, or invalid provenance are not
  no-contact and do not clear latch state. Transition consumption evaluates
  `contact_active OR collision_pulse_pending` and clears only the pulse,
  leaving `contact_active` unchanged.
- `RESET_BEGIN(new_epoch)` remains the separate atomic lifecycle reset that
  switches epoch, clears both latch states and stamps, and rejects old-epoch
  events. No reset, failure, lifecycle, or transition behavior is reinterpreted
  or weakened.
- Simulation classification: exclude wheel-ground support and robot self-
  contact; include non-ground external contact for sensor links, base/chassis,
  and world objects; include ground contact through a non-wheel robot link.
  Do not infer collision from LiDAR, odometry, pose, raw GT policy input, or
  images. Do not select static collision names or an implementation/plugin/API.
- `deploy_real` has no approved contact producer; missing events do not mean
  no collision. Future evidence must cover contact/no-contact, identity,
  duplicate/conflicting and out-of-order events, simultaneous events,
  timestamp/lifecycle binding, reset clearing, action interval, and provenance.
  None of this evidence is claimed to exist.

## 4. Map, scenario, and hardware intake

**Authorized dispositions:** packet §§5.1–5.3.

### Map

`artifacts/maps/<map_id>` remains the only canonical map root. The
Project Owner/User is `MapCustodian` and map approver unless a delegate and its
authority are named in the immutable map record. No map ID, map, coordinates,
hash, approval, or runtime evidence is selected or created.

### Scenario

The approved convention is `artifacts/scenarios/<scenario_id>/scenario.json`,
serialized as `RFC8785_JCS_UTF8`. The Project Owner/User is
`ScenarioCustodian` and scenario approver unless a delegate is named in the
immutable scenario record. `GT_ODOM_2D` is only an evaluator/ground-truth
coordinate reference. Raw GT must not enter PPO, policy input,
`ObservationAssembler`, `ObservationEncoder`, or the observation core. No
scenario ID, coordinates, goal, spawn, obstacle, randomization value, or
scenario artifact is created.

### Hardware

The Project Owner/User is the `Hardware Measurement Owner` and `Hardware
Technical Approver` unless a delegate and authority are named in the immutable
hardware record. All `TBD_MEASURED`/null values remain unavailable and
fail-closed. `approval_status: DRAFT`, `motor_enable_allowed: false`, and all
measurement/evidence obligations remain unchanged. No measurement or physical
operation is claimed.

## 5. Record routing

The approved routing is packet §6:

| Disposition group | Record route |
| --- | --- |
| WP-02 closure criteria/approver/status transition | PEP/governance amendment; append-only Ledger records evidence only after an authorized transition. No WP-02 change is in this work package. |
| D2 receipt | `docs/S3_D2_Final_Issued_Command_Receipt_Design_DRAFT.md`, `docs/S3_D2_Receipt_Ownership_User_Decision_Packet_DRAFT.md`, and any separately authorized receipt contract/interface record. |
| D3 collision/contact | `docs/S3_D3_ContactLatch_And_Collision_Fact_Contract_DRAFT.md`; runtime evidence remains a separate obligation. |
| Map/scenario | Scenario artifact contract and Registry convention/provenance; no concrete artifact values. |
| Hardware | Existing hardware approval/measurement record; retain draft/fail-closed state and route physical/HIL evidence to the applicable later gate. |
| WP status transition | PEP change control establishes a transition; append-only Ledger records the evidence/result and does not itself make the transition. |

## 6. Status and authorization boundary

This candidate records documentation dispositions only. It does not close or
formally start WP-03, change WP-04 status/dependency, update PEP or Ledger,
authorize code/ROSIDL/build/test, or approve runtime, HIL, hardware operation,
`deploy_real`, or deployment. All future runtime/physical evidence remains
pending.

```text
WP-02: CLOSED
WP-03: BLOCKED_BY_CONTRACT
WP-04: BLOCKED_BY_CONTRACT
CODE_AUTHORIZATION: NOT_GRANTED
RUNTIME_APPROVED: NOT_APPROVED
```
