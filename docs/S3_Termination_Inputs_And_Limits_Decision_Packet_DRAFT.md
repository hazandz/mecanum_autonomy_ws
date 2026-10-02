# S3 Termination Inputs And Limits Decision Packet

Status: **DRAFT — PENDING_USER_APPROVAL**

This packet identifies the immutable facts, source boundaries, and decisions
needed before a pure `S3.2` termination evaluator can be implemented. It is a
decision document only: it does not create an evaluator, reset a simulator,
publish an inhibit or zero command, or create a Gymnasium transition.

## Authority and scope

- [Architecture](MECANUM_NAV_DRL_Architecture.docx), schema `3.0`, is the
  authoritative source. Sections 19 and 22–23 define transition commit,
  reward/terminal semantics, and the termination ordering used below.
- [S3 episode design](S3_Episode_Reward_Termination_Design_DRAFT.md) remains
  `DRAFT — PENDING_USER_APPROVAL`; it records D1–D10 and existing core scope.
- [S3 transition provenance packet](S3_Transition_Provenance_Decision_Packet_DRAFT.md)
  records D2-B/D3-B as `USER_SELECTED_FOR_CORE_ONLY_IMPLEMENTATION`, not as
  runtime approval.
- [ACR S1](ACR_S1_Simulated_Odometry_And_Ground_Truth_Isolation.md) is
  `APPROVED`; [ACR S2](ACR_S2_Snapshot_Synchronization_Temporal_Contract.md)
  remains `DRAFT — PENDING_USER_APPROVAL`.

The evaluator considered here consumes caller-supplied immutable, derived
facts and returns only a decision. It must not read raw Ground Truth, a Gazebo
object, a ROS message, a decoder-ready action, or mutable callback state.
It must not own simulator reset, command inhibit, terminal publishing, or Gym
runtime behavior.

## 1. Authoritative precedence

The architecture locks the following order for simultaneous candidate events:

```text
collision > goal_reached > out_of_bounds > stuck > episode_limit
```

This is `APPROVED_FOR_CORE`: the existing S3 design records it as D4, and the
architecture also states that a terminal MDP event wins an external timeout in
the same candidate step. The evaluator may select exactly one reason from this
order after all required facts have been validated. It must not sum terminal
outcomes, select callback arrival order, reset the simulator, publish a zero
command, or itself create a Gym transition.

`STEP_ABORT`/`FAULT` is required when the required input bundle is unavailable,
invalid, or has mismatched provenance. It is an operation outcome, not a
fabricated `terminated` or `truncated` result.

## 2. Required inputs by termination reason

| Reason | Minimum immutable fact needed by evaluator | Expected owner/source | Required lifecycle and `TransitionIdentity` provenance | Fact now present in core | Missing runtime source | Status |
| --- | --- | --- | --- | --- | --- | --- |
| `COLLISION` | Read-only collision/contact candidate and its selected event state | Future contact source plus ContactLatch/runtime owner | Must bind active lifecycle and active transition token; event must be proven within the action interval; candidate is consumed only at successful lifecycle commit | `ContactCandidateSnapshot(transition_identity, event_id)` can test token join and consume-once | Generated collision contract, contact sensor/bridge, latch, event-time/action-interval proof | D3-B `USER_SELECTED_FOR_CORE_ONLY_IMPLEMENTATION`; source and evidence `REQUIRED_DECISION`, `RUNTIME_EVIDENCE_REQUIRED`, `NOT_IMPLEMENTED` |
| `GOAL_REACHED` | Derived goal-reached fact and finite goal-distance/task-state evidence | Future `TrainingTaskOracle` | Same active lifecycle and transition token as exact observation; derived at the candidate transition point | Reset baseline validates a test-only distance only; no current goal fact or evaluator input | Oracle implementation, goal-settle semantic, frame/time/token alignment | ACR S1 permission `APPROVED`; producer/contract `REQUIRED_DECISION`, `NOT_IMPLEMENTED` |
| `OUT_OF_BOUNDS` | Derived boolean/result from approved task/world boundary semantics | Future `TrainingTaskOracle` or separately approved task-boundary owner | Same active lifecycle and transition token; source must identify task/world contract and transition point | No out-of-bounds fact in lifecycle, transition, or emulator core | Boundary definition, oracle/owner, frame and transition-time evidence | `REQUIRED_DECISION`, `NOT_IMPLEMENTED` |
| `STUCK` | Derived stuck fact or an explicit unavailable result | Future pure detector fed by approved derived facts | Same active lifecycle and transition token; evaluation window must belong only to that episode and reset clears it | No stuck type, window, threshold, or detector; `TerminationReason` does not yet enumerate it | Progress source, window domain, threshold/config, reset and simultaneous-event policy | `REQUIRED_DECISION`, `NOT_IMPLEMENTED` |
| `EPISODE_LIMIT` | Current committed candidate step count and/or simulation-time fact, plus approved limit configuration | Episode lifecycle owner plus future limit/config owner | Same active lifecycle and transition token; sim time must use the exact-observation simulation domain and exceed the previous committed time | Lifecycle has `step_index`; reset/step candidates carry test-only simulation times with strict increase | Approved mode, numeric limit(s), config/schema, clock/discontinuity/reset handling | D6 `REQUIRED_DECISION`; numeric values `REQUIRED_DECISION`, `NOT_IMPLEMENTED` |

The current `core/enums.py` only defines `GOAL_REACHED`, `COLLISION`,
`OUT_OF_BOUNDS`, and a `TIME_LIMIT` truncation reason. This is partial core
evidence, not permission to invent `STUCK`, limit semantics, or a runtime
producer. `core/transition.py` has a skeleton `TransitionContext`, but its
`previous_applied_command`/`applied_command` fields are not final-issued
receipts and are not a valid substitute for any termination fact.

## 3. D3 source boundary

ACR S1 authorizes hidden Ground Truth only for oracle purposes: the
`SimulatedOdometryEmulator`, `TrainingTaskOracle`, reset validation, reward,
success/termination, and evaluator. That authority does **not** create a
`TrainingTaskOracle`, a task-boundary implementation, collision instrumentation,
or a runtime ContactLatch.

D3-B selects an explicit transition-token join for a core-only contact
candidate. It does not select the collision source, prove a physical or Gazebo
action interval, or make `ContactCandidateSnapshot` runtime evidence.

| Fact family | Source options requiring a user choice | Required evidence before runtime use |
| --- | --- | --- |
| Goal reached | A. `TrainingTaskOracle` derives distance/settle fact from hidden GT; B. another dedicated oracle with the same isolation boundary | Goal-frame/task contract, settle semantics, lifecycle/token/time alignment, reset trace |
| Out of bounds | A. `TrainingTaskOracle` derives from approved world/task boundary; B. a dedicated task-boundary oracle | Canonical boundary geometry/frame, scenario linkage, lifecycle/token/time alignment, reset/replay tests |
| Collision | A. generated Gazebo collision contract and ContactLatch; B. another explicit contact source/latch contract | Expanded-description checksum, controlled pulse/sustained-contact tests, old-epoch rejection, action-interval proof, consume-once/reset tests |

No option permits raw GT or a GT-reachable object to enter policy observation,
policy runtime, or an evaluator input bundle. LiDAR silence and a
decoder-accepted action are not collision facts.

## 4. D6 episode-limit modes

All numeric values are `REQUIRED_DECISION`; this packet proposes no number of
steps, simulation seconds, or timeout.

| Mode | Determinism and reproducibility | Simulator-rate effect | Relation to `dt_sim_s` and exact observation time | Required validation | Reset/discontinuity risk |
| --- | --- | --- | --- | --- | --- |
| Step count only | Deterministic when control-step contract is deterministic | Changes effective task duration if control cadence changes | Does not itself measure elapsed simulation time; `dt_sim_s` reward still needs committed simulation timestamps | Positive integer limit, versioned config, monotonic committed step index, terminal precedence test | Reset must clear count; duplicate/missing commits must not advance it |
| Simulation time only | Deterministic with a valid simulation clock and identical trace | Independent of wall-clock speed; depends on robust sim-clock behavior | Limit compares committed exact-observation simulation time to reset baseline; never steady/wall time | Finite positive duration, same clock domain, strictly increasing committed time, clock-jump policy | Reset must establish a new baseline; discontinuity/runtime-generation policy must fail closed |
| Both | Bounds transition count and simulated duration | Remains robust to cadence changes while retaining a count bound | Either approved threshold can request truncation; a true terminal reason still wins on the same transition | All validation from both modes plus deterministic tie/precedence tests | Both counters/times must reset atomically; partial reset cannot retain old values |

The architecture permits a terminal event to win an external timeout in the
same candidate transition. Whether `EPISODE_LIMIT` is implemented as the
existing `TIME_LIMIT` truncation reason, how both limit modes are named, and
the configuration/hash migration are part of D6 approval rather than a change
this packet can make.

## 5. STUCK decisions still required

No heuristic is selected here. Before a `STUCK` fact or evaluator branch can
exist, the following must be approved:

- Progress source: oracle goal distance, pose displacement, measured twist, or
  an explicit combination. Measured twist is policy-safe but is not
  automatically authoritative task progress.
- Evaluation window domain: simulation time, committed steps, or another
  explicitly versioned domain; it must have reset and discontinuity semantics.
- Concurrent events: collision, goal reached, and out-of-bounds are evaluated
  first by the locked precedence; a stuck decision cannot override them.
- Numeric threshold(s), minimum progress/motion definitions, treatment of
  commanded versus final-issued action, and scenario/difficulty implications.
- Reset behavior: every stuck window/cache must clear with lifecycle reset and
  must never borrow state across `reset_epoch`, `runtime_generation`, or
  episode generation.

Thresholds and windows are `REQUIRED_DECISION`; architecture notes they are
versioned configuration, with real values remaining measurement/project-
acceptance inputs where applicable.

## 6. Minimum future evaluator contract

A later core-only evaluator may receive a conceptual, immutable test-only
bundle only after the relevant decisions are approved:

| Bundle member | Required condition |
| --- | --- |
| `TransitionIdentity` | Active lifecycle plus positive step and caller/runtime-issued token; no implicit conversion or token generation inside evaluator |
| Exact observation provenance | Exact scan–odometry timestamp and active lifecycle; any runtime barrier/freshness evidence is supplied by the approved owner |
| Contact candidate | Read-only candidate bound to the same token; evaluator observes but does not consume it |
| Goal and out-of-bounds oracle facts | Derived, finite/valid facts bound to the same lifecycle/token/transition point; no raw GT object |
| Time and step facts | Committed step index and simulation-time point in one approved domain, with D6 config/version |
| Stuck fact | Approved derived fact bound to the same token, or an explicit unavailable state that prevents evaluator use |

If a required member is missing, malformed, unavailable where mandatory, or
cannot join the active `TransitionIdentity`, the lifecycle path is
`STEP_ABORT`/`FAULT`; it must not manufacture a terminal result. If all inputs
are valid, the pure evaluator can return one decision according to the locked
precedence. Only lifecycle commit may then set `RUNNING`, `TERMINATED`, or
`TRUNCATED`. The operation abort is not a Gym transition.

This bundle is deliberately conceptual. It is not an API proposal, does not
add fields to existing types, and does not imply a producer exists.

## 7. User approval checklist

- [ ] Select source and immutable provenance contract for goal-reached facts.
- [ ] Select source and immutable provenance contract for out-of-bounds facts.
- [ ] Select collision/contact source, ContactLatch owner, and required
      action-interval evidence; retain D3-B token join as core-only until then.
- [ ] Select D6 mode: step count, simulation time, or both.
- [ ] Approve versioned numeric limit value(s), validation, and reset/clock
      discontinuity behavior.
- [ ] Select STUCK progress source, evaluation-window domain, threshold/config,
      simultaneous-event handling, and reset semantics.
- [ ] Approve runtime evidence before Gazebo use: oracle alignment, generated
      collision contract, pulse/sustained-contact and reset tests, token/receipt
      replay tests, exact-pair/barrier/freshness evidence, and limit/stuck
      discontinuity tests.

## Exit condition for S3.2 core-only

`S3.2` can begin only after D3 source contracts, D6 mode and numeric values,
and the STUCK policy have been approved sufficiently to provide test-only
immutable facts without guessing. Runtime/Gazebo integration remains blocked
until the separate producer, temporal, reset, and evidence requirements above
are approved and verified.

**Final status: DRAFT — PENDING_USER_APPROVAL.**

