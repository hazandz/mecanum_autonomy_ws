# S3 Control Step And Simulation Time Contract

Status: DRAFT — PENDING_USER_DECISION

## Purpose and authority

This document defines the decision boundary for a future committed PPO control
step and its simulation-time provenance. It is documentation only. It creates
no action scheduler, ROS node, command path, receipt, environment, or runtime
policy.

Authority is [MECANUM NAV DRL Architecture](MECANUM_NAV_DRL_Architecture.docx),
schema `3.0`, SHA-256
`f0fb1ebede5f4fa18604610c04bb13587d456173b4fd942dba77e44d49777860`.
It is read with [S3 D6 Episode Limit Decision Packet](S3_D6_Episode_Limit_Decision_Packet_DRAFT.md),
[S3 Reward v3 Core Scope And Input Contract](S3_Reward_v3_Core_Scope_And_Input_Contract_DRAFT.md),
and [S3 Episode Reward Termination Design](S3_Episode_Reward_Termination_Design_DRAFT.md).

## Definition of a committed PPO control step

A future control step is one candidate transition, not merely a sensor callback,
PPO inference call, command publish, or simulation-clock tick. The following
sequence is the proposed minimum contract:

1. The step begins from a previously committed policy-safe observation `O_k`.
   Its scan and simulated odometry must form an exact pair with active
   lifecycle, reset, runtime-generation, and barrier provenance.
2. PPO receives only `O_k` and produces one normalized action `[vx, vy, wz]`.
   The core decoder validates that action. Decoder acceptance is not a final
   issued command and is not a publish receipt.
3. A future safety and smoothing path may convert that action into the final
   issued physical command. Only an approved final-issued command receipt for
   the active `TransitionIdentity` can permit candidate progression toward
   commit. D2 remains unresolved.
4. The future runtime waits for a next policy-safe exact observation `O_k+1`
   that is strictly after the approved action barrier and belongs to the same
   active lifecycle. Its ROS or simulation timestamp is the candidate current
   simulation-time point.
5. Derived Oracle, contact, limit, reward, termination, observation, and info
   facts must all validate against the same transition before lifecycle commit.
   Only then does `O_k+1` become committed, the step index advance, and a
   simulation-time delta become eligible for reward.

If any input is missing, mismatched, duplicated, stale, non-finite, or invalid,
the result is `STEP_ABORT` or `FAULT`; there is no fabricated PPO transition,
command rollback claim, old observation reuse, or inferred reward.

## Clock and counter domains

| Domain | Owner or observation point | Allowed comparisons | Forbidden comparisons or inferences |
| --- | --- | --- | --- |
| ROS or simulation timestamp | Header and exact-observation provenance, action/reset barriers, committed simulation-time points | Equality for exact pairing; ordered comparisons only within the same approved simulation-time domain | Subtracting from steady receive time or wall time; using callback order as simulation order |
| Steady receive time | Runtime ingress at local callback receipt | Receive-age, bounded wait, and local arrival ordering only when approved | Treating it as ROS time, simulation duration, action interval, or D6 elapsed time |
| Wall time | Operator/process execution and administrative guards | Launch, preflight, and operational timeout logging | Reward `dt_sim_s`, episode elapsed simulation time, freshness by ROS stamp, or control-step identity |
| Committed step index | EpisodeLifecycle after atomic commit | Integer progression, step-count limit, replay and duplicate detection | Measuring simulation duration, replacing timestamps, or inferring action rate |

No direct arithmetic or ordering rule may bridge distinct domains without an
explicit owner and approved conversion. A control policy must not use a sensor
stream rate as an implicit clock.

## Evidence inventory

The passive idle-Gazebo evidence in
[Passive Stream Timing Evidence Report](../artifacts/simulation/passive_stream_timing/Passive_Stream_Timing_Evidence_Report.md)
observed six runs with approximate stream-rate ranges:

| Stream | Observed idle range | Observed timing property | What it does not establish |
| --- | --- | --- | --- |
| `/clock` | about 93.3 to 97.5 Hz | No duplicate or regression in those six passive runs | Control trigger, action rate, limit clock owner, or behavior under reset/load |
| `/ground_truth/odom` | about 46.7 to 48.8 Hz | Runtime metadata and receive inter-arrival were recorded | Policy input permission, action cadence, Oracle runtime, or GT-to-policy route |
| `/odom` | about 46.7 to 48.8 Hz | Exact scan-to-odom timestamp pairs were observed in those runs | Final odometry architecture, action receipt, or freshness policy |
| `/scan` | about 9.3 to 9.8 Hz | Exact scan-to-odom timestamp pairs were observed in those passive runs | PPO cadence, scan suitability under motion, settle behavior, or clearance evidence |

The earlier six-run scan-to-odom audit also recorded mostly exact pairs and
rare nonzero nearest-by-stamp outliers. Exact pairing is a separate approved
core semantic; receive age, queues, overflow, and runtime ingress lifecycle
remain unresolved. Neither report recorded PPO actions, final-issued command
receipts, action barriers from a command owner, action-to-observation latency,
or a control-step trigger. Therefore no action rate can be inferred from scan,
odometry, clock, bridge, or idle timing rates.

Existing pure core offers action decoding, previous decoder-accepted action
history, exact scan-odometry gating, observation assembly, lifecycle step index,
and committed test-only simulation timestamps. It has no action scheduler,
SafetySupervisor, smoother, FinalTwistPublisher, runtime receipt producer, or
policy environment. In particular, `PreviousNormalizedCommand` is not a final
issued command receipt.

## Candidate control-step policies

All alternatives are `REQUIRED_USER_DECISION`. None selects a numeric cadence,
wait bound, timeout, or fallback.

| Candidate policy | Trigger and deterministic behavior | Relation to LiDAR rate | Skip and duplicate risk | Step-count-limit effect | Required unresolved contract |
| --- | --- | --- | --- | --- | --- |
| Fixed simulation-time cadence | One candidate action boundary per approved simulation-time interval | May sample fewer or more observations than scan callbacks; must specify exact-pair selection and missing-observation behavior | Clock discontinuity, skipped interval, duplicate stamp, and unavailable pair need fail-closed rules | Count represents fixed simulation intervals only if every interval contract is committed | Numeric cadence, scheduler owner, clock barrier, pairing/queue/freshness, D2 receipt |
| Event-driven by exact observation pair | One candidate action only when a new eligible exact scan-odometry pair arrives | Naturally follows eligible pair availability without assuming a nominal scan rate | Duplicate pair, skipped pair, late delivery, and variable cadence need explicit identity/consume rules | Count represents eligible observation-driven actions, not uniform simulated time | Pair delivery identity, observation consumption, action barrier, D2 receipt, D6 relation to variable intervals |
| Hybrid fixed cadence with freshness gate | Fixed simulation-time boundaries request a candidate only when an eligible fresh exact pair is available | Can bound control opportunities while keeping sensor gate explicit | Missing/late/duplicate pair and gate failure must abort or follow an approved no-action policy; no old-pair fallback | Count only advances for committed candidates; missed boundaries require an approved accounting rule | Numeric cadence, approved freshness/queue policy, action barrier, D2 receipt, D6 accounting |

Pause or slow simulation must be described in the selected policy using the
correct domain. A wall-clock slowdown does not by itself advance simulation time
or committed step index. A simulation pause must not create duplicate action
commits, fabricate `dt_sim_s`, or be silently interpreted as a D6 limit.

## Minimum contract before D6 literals can be selected

A later approval needs all of the following, with owners and hashes recorded:

| Contract item | Required behavior |
| --- | --- |
| Action trigger policy | Select one candidate policy or another explicitly defined policy; define when an action may be attempted. |
| Observation relation | Define `O_k` and `O_k+1` identity, exact-pair consumption, action and reset barriers, and skipped/duplicate-pair handling. |
| Command receipt | Bind final-issued receipt to the active transition; decoder-ready action and prior PPO history cannot substitute. |
| Simulation-time lifecycle | Define source domain, initial reset point, pause/slow behavior, clock regression, duplicate timestamp, and runtime-generation handling. |
| Abort behavior | Define `STEP_ABORT` for missing pair, receipt, invalid timestamp, duplicate/replay, skipped observation, or discontinuity without advance or fallback. |
| D6 accounting | Define whether a limit counts committed transitions, elapsed simulation time, or both; preserve the approved precedence. |
| Reproducibility metadata | Persist policy ID/version, selected cadence settings, action trigger source, observation and barrier identifiers, scenario/config/reward hashes, lifecycle IDs, committed step index, and committed simulation timestamps in rollout/checkpoint records. |

## D2 boundary retained

D2 is not solved here. A final-issued command receipt remains a precondition of
a committed control step, but this document creates no receipt owner, ROS
publisher, SafetySupervisor, smoother, command adapter, or runtime path. It
also does not claim that an issued command can be rolled back after a later
abort.

## User decisions required

- [ ] Choose the control-step trigger policy.
- [ ] Approve the numerical action cadence only after the trigger and required
      timing evidence are defined.
- [ ] Define pair consumption and behavior for skipped or duplicate observations.
- [ ] Define pause, slow simulation, clock regression, reset, and runtime
      generation behavior in the selected clock domain.
- [ ] Approve D2 final-issued receipt and action-barrier ownership.
- [ ] Choose D6 mode, numerical limit or limits, and strict boundary relation.
- [ ] Approve rollout and checkpoint metadata required to reproduce the policy.

## Conclusion

PENDING_USER_DECISION

The workspace has passive sensor timing evidence and pure-core observation and
lifecycle primitives, but it has no measured or approved action cadence and no
runtime receipt or trigger owner. A numeric action rate and D6 literals must
remain unselected until the listed decisions and evidence are approved. This
document grants no ROS, Gazebo, Gymnasium, training, or hardware authority.
