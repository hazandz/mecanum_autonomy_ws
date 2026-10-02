# S3 Trusted Scenario Session Binding Design

Status: DRAFT — CORE-ONLY DESIGN, RUNTIME NOT APPROVED

## Purpose and authority

This document designs a narrow pure-core contract that lets \`EpisodeLifecycle\`
hold a trusted scenario-session anchor before \`commit_reset\`. Its purpose is to
reject a \`GoalOracleFact\` whose SHA-256 is syntactically valid but belongs to a
different scenario. It creates no source code, scenario artifact, runtime
producer, or approval beyond a future core-only increment.

Authority is [MECANUM_NAV_DRL_Architecture.docx](MECANUM_NAV_DRL_Architecture.docx),
schema \`3.0\`, SHA-256
\`f0fb1ebede5f4fa18604610c04bb13587d456173b4fd942dba77e44d49777860\`.
The applicable reward schema remains \`reward-v3-baseline\`; this design supplies
only provenance-safe goal-progress inputs and does not calculate reward.

This document reconciles the implemented pure-core artifact and goal-fact work
with [Scenario Artifact Core Implementation Design](S3_Scenario_Artifact_Core_Implementation_Design_DRAFT.md),
[Scenario V1 User Decision Packet](S3_Scenario_V1_User_Decision_Packet_DRAFT.md),
and [Goal Oracle Lifecycle Join Design](S3_Goal_Oracle_Lifecycle_Join_Design_DRAFT.md).
The two-mode fact contract and the independent reset anchor described here are
implemented as a core-only value-contract increment. Runtime producers and
runtime evidence remain unapproved.

## Implementation reconciliation (S3.2.8C.1 complete)

The implementation now owns the shared values in `core/lifecycle_types.py`,
`core/scenario_session.py`, and `core/goal_facts.py`.
`scenario_session_binding_from_ready_artifact()` copies scalar identity values
from a READY artifact result; it performs no file I/O and retains no artifact
reference. `EpisodeLifecycle.begin_reset(identity, binding)` validates the
binding before mutation, retains it only as pending during reset, and commits it
only after an exact reset fact with value-equal full binding succeeds. Step facts
must match the committed full binding. New reset generations clear both pending
and committed bindings before observation0.

`EpisodeLifecycle` imports only shared core contracts and has no top-level or
local `tasks.*` import. `TrainingTaskOracle` consumes the shared contracts and
compares every binding field against the READY artifact identity. These are
core-only contracts: no ROS/Gazebo ingress, runtime artifact loading, reward,
termination, collision, bounds, command, or hardware behavior is implemented or
approved.

## Scope and non-goals

In scope:

- immutable scalar-only session binding before reset commit;
- reset and step equality checks between the committed binding and derived
  goal-fact provenance;
- removal of the logical \`core\` to \`tasks\` dependency currently used for
  lifecycle goal-result type checking;
- a test-only, pure-core implementation path and its test matrix.

Out of scope: artifact YAML or JSON creation; a \`/ground_truth/odom\` ingress;
ROS, Gazebo, TF, Gymnasium, SB3, command publication, reset receipt, settled
state, \`valid_area\` or bounds decisions, collision, clearance, STUCK, reward,
termination, and hardware.

\`GT_ODOM_2D\` remains a hidden-oracle coordinate-reference identity only. It
does not enter \`SnapshotSynchronizer\`, \`ObservationAssembler\`,
\`ObservationEncoder\`, PPO, policy input, or a policy ROS topic.

## Current evidence and gap

| Current item | Evidence in current core | Gap this design closes |
| --- | --- | --- |
| \`ScenarioArtifactLoadResult\` | A \`READY\` result carries a fully validated immutable \`ScenarioArtifact\` and its identity. | Lifecycle does not receive or retain an expected artifact identity before reset. |
| \`GoalFactProvenance\` | Carries lifecycle identity, exact observation provenance, source timestamp, join mode, optional transition identity, and scenario content hash. | Only the hash is available to lifecycle; scenario ID/version, world identity, and coordinate reference are absent. |
| \`GoalOracleFact\` / \`TaskOracleResult\` | Derived distance/reached fact is fail-closed and contains no raw pose or artifact object. | A manually constructed \`READY\` result can carry another syntactically valid hash at reset because there is no independently committed expected binding. |
| \`CommittedRewardBaseline\` | Retains lifecycle, exact observation, finite distance/time, and scenario hash; only advances at successful step commit. | It records a hash learned from the reset fact, not a pre-reset trusted session anchor. |
| \`EpisodeLifecycle._require_ready_goal_fact\` | Locally imports \`tasks.training_task_oracle\` to recognize \`TaskOracleResult\` and \`GoalFactJoinMode\`. | \`tasks.training_task_oracle\` already imports lifecycle identities, creating a logical \`core ↔ tasks\` cycle. It is currently import-safe only because the core import is local. |

Thus, a valid hash *syntax* is not proof of the selected scenario. This is a
\`MISSING_CONTRACT\` in the pure-core reset boundary, not a runtime-ingress
problem that may be deferred.

## Proposed shared value-types boundary

### ScenarioSessionBinding

Create one immutable scalar-only value type in a future shared pure-core module,
proposed path \`mecanum_nav_rl/core/scenario_session.py\`:

~~~text
ScenarioSessionBinding
  lifecycle_identity: EpisodeLifecycleIdentity
  scenario_id: str
  scenario_version: str
  scenario_content_sha256: str
  gazebo_world_name: str
  world_file_sha256: str
  coordinate_reference_id: str
~~~

All identifier fields must be non-empty trimmed strings. Both digest fields
must be lowercase full SHA-256 strings. \`lifecycle_identity\` must be an
\`EpisodeLifecycleIdentity\`; booleans, coercions, missing fields, and malformed
hashes fail at construction. The type contains neither a \`ScenarioArtifact\`,
task definition, raw Ground Truth pose, ROS/Gazebo object, timestamp, reset
receipt, nor runtime handle.

The binding is a value copy of the trusted identity from one
\`ScenarioArtifactLoadResult READY\`; it is not an artifact reference. Equality
of bindings therefore compares the entire selected session identity, not merely
a content hash.

### Goal-fact shared values

Move only shared *value contracts*, not task computation, to the same
core-owned boundary or a sibling such as \`core/goal_facts.py\`:

| Proposed shared type | Ownership and use |
| --- | --- |
| \`GoalFactJoinMode\` | Core value enum for \`RESET_OBSERVATION0\` and \`STEP_TRANSITION\`. |
| \`GoalFactProvenance\` | Core value contract: \`scenario_session_binding\`, \`ExactObservationProvenance\`, \`source_timestamp_ns\`, join mode, and optional \`TransitionIdentity\`. |
| \`GoalOracleFact\` | Derived scalar fact: finite non-negative distance, bool reached flag, and shared provenance. It must not hold raw pose or artifact. |
| \`TaskOracleStatus\` / \`TaskOracleResult\` | Core result value contract. \`READY\` requires a fact; non-ready requires \`fact=None\`. |

\`TrainingTaskOracle\` remains in \`tasks\` and imports these shared values. It
may still import \`ScenarioArtifactLoadResult\` to perform task-side validation,
but \`EpisodeLifecycle\` must depend only on the shared core values. It must not
perform a top-level or local import of \`tasks.training_task_oracle\` or
\`tasks.scenario_artifact\` to check types.

### Dependency graph

Pre-S3.2.8C.1 logical dependency (resolved):

~~~text
tasks.scenario_artifact ───────► tasks.training_task_oracle ───────► core.episode_lifecycle
                                      ▲                                      │
                                      └──── local type check in lifecycle ────┘
~~~

Implemented dependency after S3.2.8C.1:

~~~text
core.scenario_session + core.goal_facts ◄── core.episode_lifecycle
              ▲                                      ▲
              │                                      │
tasks.scenario_artifact ───► tasks.training_task_oracle ───────────┘
~~~

The caller/factory sits above both packages. It converts a \`READY\` artifact
identity into a \`ScenarioSessionBinding\`; neither lifecycle nor oracle reads a
file, ROS parameter, or simulator object. This is implemented only as an in-memory pure-core boundary. It does not grant
runtime approval.

## Session creation and reset contract

### Binding creation

Before \`begin_reset\`, a caller-side pure-core factory must do all of the
following:

1. Require \`ScenarioArtifactLoadResult.status == READY\` and a non-null,
   validated artifact.
2. Copy exactly the artifact identity scalars plus the new
   \`EpisodeLifecycleIdentity\` into \`ScenarioSessionBinding\`.
3. Reject any malformed input instead of deriving an anchor from a goal fact,
   an old baseline, a cache, or a previous session.
4. Call the proposed lifecycle entry point
   \`begin_reset(identity, scenario_session_binding)\`.

\`begin_reset\` must validate
\`identity == scenario_session_binding.lifecycle_identity\` before mutating
lifecycle state. It must clear every prior episode fact, including the
previously committed session binding, only after the new binding is accepted
for the new generation. A caller must not bind a session midway through
\`WAITING_FOR_INITIAL_OBSERVATION\` or after \`commit_reset\`.

### Reset validation and commit

\`commit_reset(ResetCommitCandidate(...))\` must validate a reset-mode ready goal
fact against the pending binding. The fact's provenance must carry a value-equal
\`ScenarioSessionBinding\`, not a bare hash. Required equalities are:

| Check | Required equality or invariant |
| --- | --- |
| Lifecycle | Candidate identity, exact observation identity, binding lifecycle identity, and goal-fact provenance lifecycle identity are all equal. |
| Scenario session | \`scenario_id\`, \`scenario_version\`, \`scenario_content_sha256\`, \`gazebo_world_name\`, \`world_file_sha256\`, and \`coordinate_reference_id\` are equal through binding equality. |
| Observation0 | Goal fact is \`RESET_OBSERVATION0\`; exact provenance is exact and value-equal to candidate observation provenance. |
| Token | Reset-mode goal fact has no \`TransitionIdentity\`; no step-zero token is fabricated. |
| Time | \`source_timestamp_ns == observation_timestamp_ns\`; this initializes \`previous_committed_sim_time_ns\`. |
| Numeric and command | Goal distance is finite and non-negative; previous issued command is exactly zero. |

Any failure is \`RESET_ABORT\` and \`FAULT\`: lifecycle must not write a baseline,
scenario hash, reset facts, command history, progress fact, or committed session
binding. A goal fact cannot make itself a trusted anchor merely because it
carries a valid-looking hash or a self-consistent binding.

On success, atomically persist the binding in \`ResetCommitFacts\`,
\`CommittedRewardBaseline\`, and the lifecycle snapshot. Keeping the complete
binding rather than only its hash makes the anchor inspectable in tests without
returning an artifact or any raw Ground Truth.

## Step contract

Only the session binding committed by reset is eligible for a later step:

1. \`begin_step\` retains the existing active \`TransitionIdentity\` rules and
   requires a committed baseline *and* committed session binding.
2. A \`STEP_TRANSITION\` fact must have a binding value-equal to the committed
   session binding, the active lifecycle, active transition identity, current
   exact observation provenance, and matching source timestamp.
3. The baseline and fact must therefore agree on all session fields as well as
   the exact current transition. A hash-only match is insufficient.
4. Only a successful atomic step commit advances goal distance, committed
   simulation time, and the binding-carrying baseline. \`GoalProgressInput\` may
   carry the same binding (or a non-ambiguous immutable reference to it) but is
   core-internal and never a policy observation.
5. \`STEP_ABORT\`, stale/future/replayed transition identity, or any mismatch
   enters \`FAULT\` under the current operation model and leaves baseline,
   binding, step index, command receipt, contact consumption, and committed
   transition IDs unadvanced.

A new \`begin_reset\` generation clears the old binding before observation0. It
then accepts only a newly created binding whose lifecycle identity is the new
generation. No old scenario session, goal fact, baseline, or fallback value is
reusable.

## Proposed diagnostics and state exposure

The external lifecycle outcomes remain \`RESET_ABORT\` and \`STEP_ABORT\`, which
are not Gym transitions. A future implementation may expose a typed
core-internal reason such as \`SCENARIO_SESSION_UNAVAILABLE\`,
\`SCENARIO_SESSION_LIFECYCLE_MISMATCH\`, or \`SCENARIO_SESSION_MISMATCH\`; it must
not turn an error into an inferred scenario selection.

\`EpisodeLifecycleSnapshot\` should expose only
\`scenario_session_binding: ScenarioSessionBinding | None\`, along with existing
committed facts, so tests can prove clear/commit behavior. It must not expose a
\`ScenarioArtifact\`, raw task geometry, raw pose, raw Ground Truth, or a policy
route.

## Implemented test coverage

| Test | Required evidence |
| --- | --- |
| Valid binding, reset, and step | A binding made from one ready artifact identity and active lifecycle permits matching reset fact, then matching step fact and one atomic advance. |
| Different valid hash | A ready fact with a syntactically valid but different hash produces \`RESET_ABORT\`/\`FAULT\`; no baseline or binding commits. |
| ID/version mismatch | A fact binding with a different \`scenario_id\` or \`scenario_version\`, even if a valid hash string is supplied, fails closed. |
| World/reference mismatch | Different \`gazebo_world_name\`, \`world_file_sha256\`, or \`coordinate_reference_id\` fails closed; \`world_demo\` is never equated with metadata frame \`world\`. |
| Lifecycle mismatch | Stale/future/different episode, reset epoch, or runtime generation fails before reset or step commit. |
| Observation/token mismatch | Reset fact carrying a token, step fact lacking/altering token, inexact/different observation provenance, or source timestamp mismatch aborts without partial mutation. |
| Session clearing | New reset generation clears old binding, baseline, progress, receipt/contact consumption, and active token before observation0. |
| No self-anchoring | Passing a fact without a pending caller-created binding, or attempting to bind from a fact, is rejected. |
| Commit-only advance | Invalid/aborted step leaves binding, baseline, time, distance, step index, receipt/contact state, and transition IDs unchanged; success advances exactly once. |
| Dependency and isolation scan | \`core/episode_lifecycle.py\` imports neither \`tasks.training_task_oracle\` nor \`tasks.scenario_artifact\`, including local imports; shared/core and tasks modules import no ROS, Gazebo, TF, Gymnasium, SB3, Ground Truth runtime type, observation/policy module, reward, termination, bounds, collision, or clearance code. |

## Non-goals and retained blockers

This contract does not create an artifact file or approve runtime artifact
loading. It does not resolve Ground Truth runtime ingress, a reset or pose
application receipt, settled-state policy, LiDAR-frame reconciliation,
clearance evidence, ContactLatch/collision source and filtering, STUCK, D6,
reward, termination, Gym/SB3 integration, command runtime, TF authority, or
hardware. \`candidate_task_bounds\` remains candidate metadata and is never used
as \`valid_area\` or out-of-bounds logic.

## Conclusion

CORE-ONLY IMPLEMENTATION COMPLETED — RUNTIME NOT APPROVED

The existing immutable identities, canonical scenario hash, two-mode goal-fact
provenance, and lifecycle atomicity are sufficient for a small pure-core
increment. The increment must first move shared value contracts out of the
current logical \`core ↔ tasks\` cycle, then require a caller-created binding
before reset. It does not grant any runtime, reward, termination, or hardware
approval.

