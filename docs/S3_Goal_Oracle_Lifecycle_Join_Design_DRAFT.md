# S3 Goal Oracle Lifecycle Join Design

Status: DRAFT — CORE-ONLY DESIGN, RUNTIME NOT APPROVED

## Purpose and authority

This document records the pure-core Goal Oracle to EpisodeLifecycle join. The
two-mode provenance and commit-bound baseline/progress input are implemented
core-only; it does not create a runtime producer, reward value, terminal
decision, simulator integration, or policy input.

Authority is [MECANUM_NAV_DRL_Architecture.docx](MECANUM_NAV_DRL_Architecture.docx),
schema 3.0, SHA-256
f0fb1ebede5f4fa18604610c04bb13587d456173b4fd942dba77e44d49777860.
The applicable reward schema remains reward-v3-baseline. Its locked progress
input is delta_d = previous.goal_distance - current.goal_distance. This design
only supplies provenance-safe inputs; it does not calculate reward.

This design also follows
[S3 Episode Reward Termination Design Draft](S3_Episode_Reward_Termination_Design_DRAFT.md)
and
[S3 Training Task Oracle Core Design Draft](S3_Training_Task_Oracle_Core_Design_DRAFT.md).

## Scope and non-goals

In scope:

- join one immutable ready derived goal fact to reset observation0 or one active step;
- establish the committed previous-distance/time baseline and a derived progress-input candidate;
- reject lifecycle, scenario, timestamp, and token mismatch before numeric extraction.

Out of scope: raw Ground Truth ingress, ROS or Gazebo objects, policy or observation access,
Gymnasium, SB3, reward calculation, termination, out-of-bounds, candidate_task_bounds,
collision, clearance, STUCK, command receipt ownership, and runtime recovery policy.

## Existing evidence and ownership

| Fact or component | Current owner | Reusable evidence | Join limitation |
| --- | --- | --- | --- |
| EpisodeLifecycleIdentity | core/lifecycle_types.py (re-exported by episode_lifecycle.py) | Immutable episode, reset, runtime generations; stale/future checks | Does not identify an observation point. |
| TransitionIdentity | core/lifecycle_types.py (re-exported by episode_lifecycle.py) | Lifecycle, positive step index, non-empty token; replay protection | Cannot represent observation0 because step index zero is invalid. |
| ExactObservationProvenance | core/lifecycle_types.py (re-exported by episode_lifecycle.py) | Lifecycle plus exact scan, odom, observation timestamp | Has no scenario hash or transition token. |
| CommittedRewardBaseline | core/episode_lifecycle.py | Finite previous distance/time tied to exact provenance; advances only on successful commit and retains ScenarioSessionBinding | Runtime session ingress remains unimplemented. |
| ResetCommitCandidate | core/episode_lifecycle.py | Atomically commits observation0 baseline after RESET_OBSERVATION0 GoalOracleFact validation | Runtime caller/provenance producer remains unimplemented. |
| StepCommitCandidate | core/episode_lifecycle.py | Active token, exact observation, full session binding, finite current distance, strict time increase | Runtime caller/provenance producer remains unimplemented. |
| GoalOracleFact | core/goal_facts.py | Immutable finite distance, reached flag, full binding and exact two-mode provenance; no raw pose/artifact output | Runtime producer remains unimplemented. |
| TrainingTaskOracle | tasks/training_task_oracle.py | Goal-rule-only computation and explicit non-ready status | Stateless; has no reset-mode output or lifecycle cache. |

core/transition.py contains an older TransitionContext skeleton. Its TaskState and
command fields do not establish Goal Oracle provenance. It is not the join owner
for the next increment.

## Required two-mode goal-fact contract

The two-mode model is an implemented core-only contract; it is not runtime approval.
An initial baseline exists before a step token can exist.

| Join mode | Required evidence | Transition-token rule | Lifecycle use |
| --- | --- | --- | --- |
| RESET_OBSERVATION0 | Active EpisodeLifecycleIdentity, exact ExactObservationProvenance, matching scenario hash, source timestamp equal to observation timestamp | No TransitionIdentity; do not fabricate a step-zero token | Create the first distance/time baseline during reset commit only. |
| STEP_TRANSITION | Active lifecycle, exact current observation provenance, active TransitionIdentity, matching scenario hash, source timestamp equal to current observation timestamp | Required; must equal the token bound by begin_step | Form one current-distance/progress candidate for that step only. |

Therefore the current GoalOracleFact cannot safely serve reset unchanged: it
always has a positive-step TransitionIdentity. The next core increment must
make the join mode explicit rather than invent a reset token.

Recommended minimal evolution: add immutable GoalFactProvenance to
GoalOracleFact.

~~~text
join_mode: RESET_OBSERVATION0 | STEP_TRANSITION
lifecycle_identity: EpisodeLifecycleIdentity
observation_provenance: ExactObservationProvenance
transition_identity: TransitionIdentity | None
scenario_content_sha256: str
source_timestamp_ns: int
~~~

For RESET_OBSERVATION0, transition_identity must be absent. For
STEP_TRANSITION, it must be present and equal the active token. This retains
the fact name and its derived-only output while preserving the existing
no-fabricated-token rule.

## Reset join sequence

1. begin_reset clears all prior baseline and fact state, as current lifecycle
   code already does.
2. The caller obtains exact observation0 provenance for the active lifecycle.
   The future Oracle request uses RESET_OBSERVATION0.
3. A ready reset fact is accepted only if lifecycle, exact provenance, source
   timestamp, and scenario hash all match observation0. Distance must be finite
   and non-negative.
4. The candidate uses the exact observation timestamp as
   previous_committed_sim_time. It does not derive simulation time from steady
   receive time or subtract clock domains.
5. A proposed ResetGoalBaselineJoinCandidate supplies the ready fact, exact
   provenance, zero previous issued command, and timestamp to commit_reset.
6. Only reset commit writes previous_goal_distance_m and
   previous_committed_sim_time, then enters RUNNING with step index zero.

A missing/non-ready fact, a reset fact carrying a transition token, inexact
provenance, wrong lifecycle/hash/timestamp, or non-finite distance produces
RESET_ABORT and FAULT. No older baseline may survive.

## Step join sequence and progress input

1. begin_step binds one active TransitionIdentity.
2. A STEP_TRANSITION Oracle fact is usable only if it carries the same active
   lifecycle, token, exact current observation provenance, source timestamp,
   and scenario hash.
3. The join owner reads the committed baseline and creates an immutable
   GoalProgressInput candidate.

~~~text
transition_identity
scenario_content_sha256
previous_goal_distance_m
current_goal_distance_m
delta_d = previous_goal_distance_m - current_goal_distance_m
previous_observation_timestamp_ns
current_observation_timestamp_ns
~~~

4. GoalProgressInput is a future reward input only. It is not a reward,
   terminal decision, policy feature, raw pose, or raw Ground Truth reference.
5. The current timestamp must equal the current exact observation timestamp and
   be strictly newer than the committed baseline timestamp.

The join rejects a fact from an old episode, stale/future generation, replayed
token, same-step different token, mismatched hash, or different observation.
It never derives out-of-bounds from candidate_task_bounds.

## Commit and abort semantics

| Operation | Required behavior | Baseline effect |
| --- | --- | --- |
| Reset commit | All reset-mode fact and observation0 checks succeed atomically. | Write first distance/time/hash once. |
| Step validation | Current fact joins active token, exact observation, and committed scenario hash. | None before commit. |
| Step commit | Existing atomic commit succeeds. | Replace distance/time/hash exactly once. |
| RESET_ABORT | Reset fact unavailable or invalid; state becomes FAULT and facts clear. | No partial or old baseline. |
| STEP_ABORT | Current fact or provenance failure before commit; state becomes FAULT. | Baseline, step index, and command history do not advance. |
| New reset generation | Existing generation rules advance and clear episode facts. | Clear baseline, fact provenance, and progress candidate before observation0. |

Current lifecycle has numeric atomicity: it builds a new CommittedRewardBaseline
only after step validation succeeds. It does not yet have Oracle-fact atomicity,
because reset and step candidates accept bare distance fields.

## Proposed fail-closed diagnostics

The lifecycle operation outcome remains RESET_ABORT or STEP_ABORT. The next
increment should provide a typed join diagnostic without creating a Gym
transition.

| Proposed diagnostic | Condition | Required outcome |
| --- | --- | --- |
| GOAL_FACT_UNAVAILABLE | Oracle result is non-ready or has no fact | Abort; no fallback. |
| GOAL_FACT_MODE_MISMATCH | Reset receives a step fact or step receives a reset fact | Abort; never synthesize a token. |
| GOAL_FACT_LIFECYCLE_MISMATCH | Episode, reset, or runtime generation differs, including stale/future | Abort; no advance. |
| GOAL_FACT_TRANSITION_MISMATCH | Step token absent, replayed, stale/future, or differs for same step | STEP_ABORT; no advance. |
| GOAL_FACT_OBSERVATION_MISMATCH | Fact source timestamp/provenance is not exact observation0/current observation | Abort; no numeric extraction. |
| GOAL_FACT_SCENARIO_MISMATCH | Fact hash differs from committed scenario identity | Abort; no scenario fallback. |
| GOAL_FACT_NUMERIC_INVALID | Distance or delta_d is non-finite | Abort; no clamp or substitution. |

## Implemented core-only delta

| File | Implemented responsibility | Change class |
| --- | --- | --- |
| mecanum_nav_rl/tasks/training_task_oracle.py | Emits reset or step join provenance with the existing goal-only computation and full binding validation. | Implemented pure-core API. |
| mecanum_nav_rl/core/episode_lifecycle.py | Validates mode/provenance/full session binding before extracting baseline/current distance; persists binding with baseline. | Implemented pure-core lifecycle join. |
| mecanum_nav_rl/test/test_training_task_oracle.py | Test reset-mode and step-mode fact construction and isolation. | Unit test. |
| mecanum_nav_rl/test/test_episode_lifecycle.py | Test reset/step joins, commit-only advance, abort/reset clear, and replay rejection. | Unit test. |
| mecanum_nav_rl/core/transition.py | No change in this increment. | Explicitly deferred. |

No configuration, scenario artifact file, policy observation, or runtime file
was added for this narrow increment.

## Required test matrix

| Test | Required evidence |
| --- | --- |
| Valid reset join | Ready reset fact, active lifecycle, exact observation0, matching time/hash, zero initial command; reset commits baseline. |
| Reset rejection | Missing/non-ready, step-mode, wrong lifecycle/timestamp/hash, NaN/Inf distance, or nonzero reset command gives RESET_ABORT and no baseline. |
| Valid step join | Ready step fact matches active token, exact current observation, committed hash; progress candidate has expected delta_d. |
| Step replay and staleness | Old episode, stale/future, reused token, or same-step-different-token produces STEP_ABORT without advance. |
| Commit-only advance | Successful step advances distance/time/hash once; validation failure or explicit STEP_ABORT leaves all three unchanged. |
| Consecutive resets | New lifecycle clears prior baseline/progress/fact state before observation0; it requires a new baseline. |
| Isolation | Progress output has no raw pose, artifact object, Ground Truth object, or policy-observation route. Source scan forbids ROS, Gazebo, Gymnasium, SB3, reward, termination, bounds, and collision logic. |

## Ground Truth isolation and non-claims

Only the hidden Oracle-side caller may turn caller-supplied 2D scalars into a
derived goal fact. GoalOracleFact, its baseline, and GoalProgressInput must not
carry raw pose fields, ROS messages, Gazebo objects, scenario artifact objects,
or reachable references. They must not pass to ObservationAssembler,
ObservationEncoder, PPO, or policy ROS topics.

This design does not approve runtime Oracle or Ground Truth topic ingress,
reward/termination, collision/contact, bounds, clearance, STUCK, D6, command
receipt, reset receipt, Gymnasium, SB3, Gazebo, or hardware.

## Conclusion

CORE-ONLY IMPLEMENTATION COMPLETED — RUNTIME NOT APPROVED

The completed bounded increment provides explicit two-mode fact provenance and
lifecycle join validation, with tests for atomic baseline advance. It retains
the architecture rule that reset uses exact observation0 provenance and does
not fabricate a TransitionIdentity.
