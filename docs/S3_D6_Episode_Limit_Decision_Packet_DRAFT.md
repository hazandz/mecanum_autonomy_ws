# S3 D6 Episode Limit Decision Packet

Status: DRAFT — PENDING_USER_DECISION

## Purpose and authority

This packet isolates D6, the episode-limit decision required before a future
core-only truncation evaluator can be designed or implemented. It creates no
source, configuration, runtime producer, or simulation behavior.

Authority is [MECANUM NAV DRL Architecture](MECANUM_NAV_DRL_Architecture.docx),
schema `3.0`, SHA-256
`f0fb1ebede5f4fa18604610c04bb13587d456173b4fd942dba77e44d49777860`.
It is reconciled with [S3 Episode Reward Termination Design](S3_Episode_Reward_Termination_Design_DRAFT.md),
[S3 Termination Inputs And Limits Decision Packet](S3_Termination_Inputs_And_Limits_Decision_Packet_DRAFT.md),
and [S3 Reward v3 Core Scope And Input Contract](S3_Reward_v3_Core_Scope_And_Input_Contract_DRAFT.md).

## Three distinct concepts

| Concept | Purpose | Required time or counter domain | What it does not decide |
| --- | --- | --- | --- |
| `dt_sim_s` | Reward-v3 time penalty and time-scaled clearance term | Positive difference between previous committed and current same-transition simulation timestamps | It does not truncate an episode and D6 does not itself establish its runtime source. |
| Episode simulation-time limit | Requests truncation after an approved elapsed simulation duration | Reset baseline and current committed simulation timestamp from one simulation-time domain | It does not determine reward `dt_sim_s` validity, action cadence, or a wall-clock timeout. |
| Step-count limit | Requests truncation after an approved number of committed steps | Committed lifecycle step index | It does not measure simulation duration or supply `dt_sim_s`. |

The existing lifecycle stores a committed step index and simulation timestamp
for pure-core provenance tests. It does not constitute an approved limit mode,
numeric limit, clock owner, or runtime source.

## Authoritative truncation semantics

`TRUNCATED` is distinct from `TERMINATED`. An episode limit produces a future
truncation reason `EPISODE_LIMIT`; it is neither success nor task failure.
It must not be converted into collision, goal success, STUCK, or a fabricated
reward term.

The authority locks simultaneous-event precedence:

```text
collision > goal_reached > out_of_bounds > stuck > episode_limit
```

A limit evaluator may request `EPISODE_LIMIT` only after its own fact has been
validated. If a higher-precedence fact is unavailable, this does not permit an
evaluator to manufacture that terminal fact or assume that a limit wins. An
incomplete same-transition bundle remains `STEP_ABORT` or `FAULT`, not a
terminal or truncated Gym transition.

## D6 mode options

All literals below remain `REQUIRED_USER_DECISION`. This packet proposes no
number of steps, simulation seconds, action rate, timeout, or fallback.

| Option | Deterministic training and experiment reproducibility | Pause or slow simulation behavior | Reset and discontinuity implications | Decision status |
| --- | --- | --- | --- | --- |
| Step-count only | Reproducible when the committed control-step contract and scenario/config hashes are identical | Wall-clock slowdowns do not change step count; changed action cadence changes simulated task duration | Reset clears count; duplicate, skipped, stale, or aborted commits must not advance count | `REQUIRED_USER_DECISION` |
| Simulation-time only | Reproducible with the same valid simulation-clock trace, scenario, and configuration | Independent of wall-clock speed and pauses; requires a defined simulation-clock discontinuity policy | Reset needs a new committed start timestamp; clock regression, generation change, or source mismatch must fail closed | `REQUIRED_USER_DECISION` |
| Both | Can bound both committed actions and simulated duration if both contracts are reproducible | Avoids relying on a single cadence or clock condition, but adds two sources to validate | Reset must atomically clear both; same-transition precedence and tie behavior must be explicit | `REQUIRED_USER_DECISION` |

No option permits comparison between steady receive time and simulation timestamps.
No option turns an administrative timeout or callback wait into episode elapsed
simulation time.

## Minimal future core fact contract

This is a conceptual contract only, not an API or code change.

| Proposed member | Required purpose and validation |
| --- | --- |
| `EpisodeLifecycleIdentity` | Must equal the active episode, reset epoch, and runtime generation. |
| `TransitionIdentity` | Must equal the active committed candidate transition; no implicit token generation. |
| `current_step_index` | Non-negative committed candidate step index; no advance for abort, replay, or duplicate. |
| `current_simulation_timestamp_ns` | Non-negative exact-observation simulation timestamp in one approved domain; not steady or wall time. |
| `EpisodeLimitMode` | Typed explicit choice: step count, simulation time, or both. |
| `configured_step_limit` and or `configured_simulation_time_limit_ns` | Finite positive values only when required by selected mode; versioned configuration identity must be available to logging/checkpointing. |
| `EpisodeLimitStatus` | Typed READY, MISSING_CONFIGURATION, PROVENANCE_MISMATCH, NUMERIC_INVALID, CLOCK_DISCONTINUITY, or UNAVAILABLE outcome. |
| `EpisodeLimitReason` | `EPISODE_LIMIT` only when a validated selected limit is reached according to the approved boundary rule. |

A non-ready outcome contains no partial decision. It cannot be silently
converted to false, zero elapsed time, an unbounded episode, or an inferred
termination result.

## Required user decisions

| Decision | Required user choice | Status |
| --- | --- | --- |
| D6 mode | Step-count only, simulation-time only, or both | `REQUIRED_USER_DECISION` |
| Numeric limit | Exact number of committed steps and or simulation duration | `REQUIRED_USER_DECISION` |
| Units and boundary | SI duration unit representation and whether limit is reached at `>=` or `>` | `REQUIRED_USER_DECISION` |
| Simulation-time discontinuity | Clock rollback, reset, pause, generation change, and timestamp mismatch behavior | `REQUIRED_USER_DECISION` |
| Relation to action rate | Whether action cadence is fixed, versioned, or otherwise part of experiment identity | `REQUIRED_USER_DECISION` |
| Checkpoint and logging | Limit mode/value, boundary rule, action-rate contract, scenario/config/reward hashes, lifecycle generation, committed step index, and simulation timestamps to persist | `REQUIRED_USER_DECISION` |
| Precedence integration | How the later evaluator handles valid simultaneous facts under the locked precedence | `APPROVED_FOR_CORE` precedence; producer completeness remains required |

The architecture does not supply the missing D6 literals. They must not be
inferred from existing profile YAML, action defaults, observed simulator rate,
or wall-clock measurement.

## Acceptance criteria for a later D6 core increment

After user approval, a core-only increment must demonstrate at minimum:

- a validated selected limit fact binds one active lifecycle, transition, and
  exact observation provenance;
- step count and simulation timestamp are never advanced on `STEP_ABORT`;
- reset and a new runtime generation clear prior limit state;
- each selected mode rejects missing or irrelevant numeric values fail closed;
- strict boundary behavior matches the approved `>=` or `>` rule exactly;
- a valid higher-precedence fact is selected over `EPISODE_LIMIT` only through
  the future complete termination contract;
- source scans confirm no ROS, Gazebo, Gymnasium, SB3, command, or hardware
  dependency enters the pure evaluator.

## Conclusion

PENDING_USER_DECISION

D6 cannot proceed to core implementation approval until the user selects a
limit mode, numeric limit or limits, boundary relation, discontinuity/reset
semantics, action-rate relationship, and reproducibility metadata. This packet
does not resolve `dt_sim_s` sourcing and does not authorize runtime, training,
or hardware.
