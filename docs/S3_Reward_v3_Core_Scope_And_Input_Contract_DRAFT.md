# S3 Reward v3 Core Scope and Input Contract

Status: DRAFT — CORE-ONLY DESIGN, RUNTIME NOT APPROVED

## Purpose and authority

This document defines the narrow input boundary required before a pure Reward-v3
evaluator can be implemented. It does not implement an evaluator, select a
runtime producer, change a coefficient, or authorize simulation runtime.

The authority is [MECANUM NAV DRL Architecture](MECANUM_NAV_DRL_Architecture.docx),
schema `3.0`, SHA-256
`f0fb1ebede5f4fa18604610c04bb13587d456173b4fd942dba77e44d49777860`.
The authority locks `reward-v3-baseline`; this packet does not create a new
reward schema. It reconciles the S3 episode design with the implemented
core-only Goal Oracle to lifecycle join and trusted scenario-session binding.

## Scope and non-goals

In scope is an immutable, provenance-checked reward-input contract for a future
pure evaluator. The contract has a separate derive and validate stage followed
by a commit-only reward stage. A missing, stale, non-finite, or mismatched fact
must cause a typed operation abort rather than a fabricated reward.

Out of scope are ROS, Gazebo, TF, Gymnasium, SB3, callbacks, topics, command
publication, runtime Ground Truth ingress, artifact file loading, reward code,
termination code, collision runtime, clearance computation, bounds, STUCK,
configuration edits, and hardware.

## Authoritative Reward v3 baseline

The locked baseline is:

```text
delta_d      = previous.goal_distance - current.goal_distance
r_progress   = clip(2.00 * delta_d, -1.00, 1.00)
r_time       = -0.10 * dt_sim_s
r_clearance  = -0.20 * max(0, (d_safe - c) / d_safe) * dt_sim_s / 0.10
du           = normalized_applied - normalized_previous_applied
r_smooth     = clip(-0.005 * dot(du, du) / max(dt_sim_s, 1e-6), -1.0, 0.0)
r_terminal   = +15 goal | -15 collision | -3 stuck | 0 otherwise
r_total      = sum(terms)
abs(r_total - logged_sum) <= 1e-6
```

The formula and coefficients are `APPROVED_FOR_CORE` by the architecture. This
does not mean every input has an approved producer. `d_safe`, clearance
semantics, STUCK semantics, episode-limit mode and values, final-issued command
normalization, and runtime receipt evidence remain unresolved.

## Reward-term readiness

| Reward term | Required derived inputs | Classification | Evidence and limit |
| --- | --- | --- | --- |
| Progress | `GoalProgressInput`: committed previous distance, current distance, exact provenance, lifecycle, transition, and scenario session | `IMPLEMENTED_INPUT_AVAILABLE` | The lifecycle join makes `delta_d` provenance-safe and commit-bound. It is not a computed reward. |
| Time cost | Positive `dt_sim_s` from committed previous and current simulation-time points | `CORE_INPUT_DESIGNABLE_BUT_DECISION_REQUIRED` | Core stores committed timestamps, but the runtime simulation-time producer and D6 time policy are not approved. |
| Clearance | Clearance `c`, `d_safe`, exact frame and timestamp relation | `BLOCKED_BY_MISSING_RUNTIME_EVIDENCE` | D10 has no approved metric, source, frame relation, or threshold. |
| Smoothness | Two final-issued normalized command receipts for adjacent committed transitions | `BLOCKED_BY_MISSING_RUNTIME_EVIDENCE` | D2 final-issued receipt and physical-to-normalized rule are absent. Decoder-accepted action is not a receipt. |
| Goal terminal | Derived `GoalOracleFact.goal_reached` with full scenario and transition provenance | `IMPLEMENTED_INPUT_AVAILABLE` | The goal-only Oracle produces a derived fact. Runtime Oracle ingress and goal-settle policy remain unapproved. |
| Collision terminal | Read-only active-transition contact candidate | `BLOCKED_BY_MISSING_RUNTIME_EVIDENCE` | D3 token join exists core-only, but no ContactLatch producer or action-interval evidence exists. |
| STUCK terminal | Approved derived stuck fact, window, metric, threshold, and reset rule | `CORE_INPUT_DESIGNABLE_BUT_DECISION_REQUIRED` | No approved metric, window, threshold, or producer exists. |
| Episode limit | Approved step and or simulation-time limit fact | `CORE_INPUT_DESIGNABLE_BUT_DECISION_REQUIRED` | D6 limit mode, numeric values, and lifecycle producer remain pending. |
| Reward evaluator and breakdown | Every applicable validated term plus one selected terminal decision | `NOT_IMPLEMENTED` | No pure evaluator, breakdown, or commit interface is implemented in this phase. |

The architecture terminal precedence is `collision > goal_reached >
out_of_bounds > stuck > episode_limit`. It governs a future termination decision
and does not let a reward evaluator invent a terminal fact.

## Input provenance contract

Every fact below must be immutable and belong to the same active
`TransitionIdentity`, `EpisodeLifecycleIdentity`, exact observation provenance,
and committed `ScenarioSessionBinding`. The binding includes scenario identity,
version, content hash, Gazebo world name, world-file hash, coordinate reference,
and lifecycle identity. Equality of content hash alone is insufficient.

| Reward input | Required provenance and owner | Current core status | Forbidden substitution |
| --- | --- | --- | --- |
| Goal progress and delta distance | `GoalProgressInput` from `EpisodeLifecycle`, joined from READY step-mode `GoalOracleFact` and committed reset baseline | Implemented core input | Raw GT pose, old fact, policy pose, or a distance across generations |
| Goal reached | READY `GoalOracleFact` from `TrainingTaskOracle`, full binding and exact observation provenance | Implemented core input | Noisy observation goal feature or raw GT object |
| Elapsed simulation time | Previous committed simulation timestamp plus current same-transition timestamp, strictly positive delta | Test-only core values; runtime producer unresolved | Steady receive time, wall time, action duration, or zero default |
| Final issued command and smoothness | Two receipt-backed final issued physical commands and an approved normalization rule | D2 core token mechanics only; runtime evidence missing | PPO desired action, decoder-accepted action, prior history, or measured twist |
| Collision | Active `ContactCandidateSnapshot` with lifecycle and transition provenance, read before commit and consumed only on successful commit | Test-only core token mechanics only; runtime producer missing | Scan, GT pose, service response, missing contact pulse, or inferred collision |
| Clearance | Approved scalar `c` and `d_safe`, source/frame/timestamp tied to the exact transition | Not implemented | Raw LiDAR minimum, privileged geometry, or old clearance without approval |
| Bounds | Approved oracle-derived bounds fact with full binding and transition provenance | Not implemented | `candidate_task_bounds`, SDF geometry, visual map, or raw GT position |
| Stuck | Approved derived detector fact tied to active transition and window lifecycle | Not implemented | Measured twist alone, zero command, or arbitrary step count |
| Episode limit | Approved step or simulation-time fact tied to active lifecycle and current transition | Not implemented | Callback timeout, steady time, or implicit default limit |

`GoalProgressInput` is provenance-safe input only. It is not a reward value, a
terminal decision, a policy observation, or a raw Ground Truth route.
`GoalOracleFact` and any future reward result must hold derived scalar facts
only: no raw GT pose, reachable GT object, `ScenarioArtifact` reference, or
policy-observation object. Ground Truth remains hidden to the simulation task
oracle and never enters PPO or policy observation.

## Commit boundary

1. A transition builder derives and validates each immutable fact before reward
   evaluation. It validates lifecycle identity, active transition token, exact
   observation provenance, complete scenario-session binding, scenario hash,
   finite scalar values, and source timestamp consistency.
2. A future pure evaluator receives only one validated `RewardInput`. It has no
   callback, ROS, Gazebo, policy, or global mutable-state access.
3. A future lifecycle transaction may commit a `RewardResult` only together with
   the already validated transition and selected termination decision.
4. Any invalid input is `STEP_ABORT`, not a zero reward, a penalty, a fallback
   to old values, or a Gym transition. Abort does not advance distance/time
   baseline, receipt history, contact consumption, or reward-consumed state.

## Proposed core-only API for a later increment

This is a proposal only; no source is created by this document.

| Proposed type | Responsibility | Required invariants |
| --- | --- | --- |
| `RewardInput` | Immutable fully validated bundle for one candidate transition | Full lifecycle, transition, exact observation, and scenario-session equality; finite scalar inputs; no raw GT or artifact reference |
| `RewardInputStatus` | Typed validation outcome such as READY, MISSING_INPUT, PROVENANCE_MISMATCH, NUMERIC_INVALID, or DECISION_UNAVAILABLE | Non-ready has no partial input and cannot commit reward |
| `RewardInputResult` | Immutable result of derive and validate stage | READY holds exactly one `RewardInput`; non-ready holds none |
| `RewardResult` | Immutable future evaluator output | Finite term values, logged sum equality, schema ID, transition identity, and no policy or runtime handle |
| `RewardCommitCandidate` | Lifecycle-facing candidate that joins a validated reward result to an already valid transition | Commit only after reward, terminal decision, observation, and info are all valid |

No weight, timeout, threshold, clamp, fallback, or formula is proposed beyond
the locked architecture baseline. A later implementation must not silently omit
a blocked term or invent a substitute.

## Required decisions and evidence before implementation

| Blocker | Minimum decision or evidence required |
| --- | --- |
| D2 | Define final-issued receipt owner, receipt evidence after final limiting, command identity, and physical-to-normalized conversion for smoothness. |
| D3 | Define ContactLatch source, contact filtering, active action-interval provenance, and commit-time consume owner. |
| D6 | Select step limit, simulation-time limit, or both; approve numeric values and reset or discontinuity semantics. |
| D10 | Define clearance metric and source, frame and timestamp relation, `d_safe`, and measured evidence. |
| Bounds | Approve an oracle-derived bounds contract and source. `candidate_task_bounds` is not a valid-area or bounds fact. |
| STUCK | Approve progress metric, window domain, threshold, simultaneous-event handling, and reset semantics. |
| Runtime oracle | Approve GT ingress, scenario session binding at runtime, reset observation0 source, and goal-settle semantics. |
| Coefficients and schema delivery | Preserve the locked baseline through an approved typed configuration and reward hash path; any schema change requires an ACR. |
| Terminal precedence | Use the authoritative precedence in a later evaluator; do not construct precedence from incomplete inputs. |

## Conclusion

BLOCKED_BY_REQUIRED_DECISIONS

The goal-progress and goal-reached derived inputs are available in core-only
form, with full lifecycle, transition, exact-observation, and scenario-session
provenance. A Reward-v3 evaluator cannot safely begin while D2, D3, D6, D10,
bounds, STUCK, runtime oracle, and required terminal input contracts remain
unresolved. This conclusion does not authorize runtime, training, or hardware.
