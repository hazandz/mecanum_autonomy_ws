# S3 D2 Final Issued Command Receipt Design

Status: DRAFT — PENDING_USER_DECISION

## Purpose and authority

This document designs the decision boundary for a future final-issued command
receipt. It creates no receipt type, publisher, SafetySupervisor,
FinalTwistPublisher, transport client, UART activity, or runtime command path.

Authority is [MECANUM NAV DRL Architecture](MECANUM_NAV_DRL_Architecture.docx),
schema `3.0`, SHA-256
`f0fb1ebede5f4fa18604610c04bb13587d456173b4fd942dba77e44d49777860`.
It is reconciled with [S3 Control Step And Simulation Time Contract](S3_Control_Step_And_Simulation_Time_Contract_DRAFT.md),
[S3 Reward v3 Core Scope And Input Contract](S3_Reward_v3_Core_Scope_And_Input_Contract_DRAFT.md),
[S3 Episode Reward Termination Design](S3_Episode_Reward_Termination_Design_DRAFT.md),
and [S3 Transition Provenance Decision Packet](S3_Transition_Provenance_Decision_Packet_DRAFT.md).

D2-B, explicit `transition_id`, is user-selected for core-only implementation.
That selection does not choose a runtime receipt owner or prove a command was
published.

## Existing ownership evidence

| Layer | Existing source or authority | What is established | What is not established |
| --- | --- | --- | --- |
| PPO desired action | PPO caller and `PpoActionDecoder` input | Core decoder accepts only a finite normalized three-axis action | No PPO runtime/environment owner or action schedule |
| Decoder-accepted command | `actions/ppo_decoder.py` returns `NormalizedPpoAction` and scaled `VelocityCommand` | Fixed axis order and fail-closed bounds/scaling | No safety acceptance, arbitration, publish, or handoff |
| Previous action history | `actions/previous_action_history.py` | Stores decoder-accepted normalized action for current core phase | Not final issued command history; cannot be receipt evidence |
| Safety limiting and arbitration | Architecture assigns final selection and limiting to `SafetySupervisor` | Architecture ownership is locked | No runtime source or implemented arbitration semantics in `mecanum_nav_rl` |
| Final publish boundary | Architecture assigns `/cmd_vel` publication to `FinalTwistPublisher` | Intended final command boundary is named | No runtime publisher, receipt, action barrier, or graph evidence |
| Safety state interface | `SafetyState.msg` contains raw, limited, final Twist and active command source | A future safety status can expose command snapshots | No `TransitionIdentity`, receipt ID, publish result, command sequence, normalization version, or barrier timestamp |
| Bridge command semantics | `mecanum_base_bridge/command_semantics.py` validates configured epoch and command sequence in pure tests | A protocol-level acceptance gate exists | It is not serial runtime, final publish evidence, actuator acknowledgement, or motor movement proof |
| Lifecycle receipt fact | `CommandReceiptSnapshot` in `core/episode_lifecycle.py` | Test-only token/receipt replay join and normalized issued-command staging | It has no final physical command, source owner, barrier, publish result, or runtime provenance |

The authoritative future chain is:

```text
PPO desired normalized action
  -> decoder-accepted desired physical command
  -> SafetySupervisor arbitration, validation, limiting, and smoothing
  -> final issued physical command
  -> FinalTwistPublisher publish or approved transport handoff
  -> immutable final-issued receipt
```

Only the last stage is a receipt candidate. A decoder-ready value,
`PreviousActionHistory`, measured twist, bridge codec acceptance, UART response,
or motor movement must not be renamed or treated as final-issued receipt.

## Four distinct command objects

| Object | Meaning | Permitted use | Explicitly not |
| --- | --- | --- | --- |
| PPO desired action | Raw normalized `[vx, vy, wz]` proposed by policy at one control boundary | Decoder input | A physical command, safety decision, receipt, or observation history source |
| Decoder-accepted command | Validated normalized action and scaled desired `VelocityCommand` | Candidate input to future command path | Safety-limited, issued, published, transported, or acknowledged command |
| Final-issued command | Physical `vx_mps`, `vy_mps`, `wz_radps` after approved safety arbitration, limit, and smoothing; accepted at final publish or handoff boundary | Future previous-issued observation history, smoothness reward, transition record | Actuator or motor acknowledgement |
| Measured twist | Robot velocity measurement from simulated odometry or estimator | Measured-twist observation and diagnostics | Command receipt, proof of publish, or proof that requested velocity was achieved |

The current observation previous-command block and `PreviousActionHistory` remain
core-phase decoder-accepted history. Replacing them with receipt-backed
final-issued normalized command changes observation semantics and must follow
the architecture schema/hash and checkpoint migration process.

## Proposed immutable receipt contract

A future receipt must be immutable and created only after the final safety path
has accepted the final physical command and its final publish or approved
transport handoff has succeeded. It is not an actuator acknowledgement.

| Proposed field | Required contract |
| --- | --- |
| `lifecycle_identity` | Exact `EpisodeLifecycleIdentity`, including episode, reset, and runtime generation |
| `transition_identity` | The active explicit D2-B `TransitionIdentity`; receipt token must equal the transition awaiting commit |
| `receipt_owner_id` | Versioned identity of the final-publish or handoff owner; no implicit ownership from a topic name |
| `command_source` | Typed final source selected by the safety path, such as policy, Nav2, teleop, safe stop, or e-stop; must agree with arbitration result |
| `final_physical_command` | Finite physical `vx_mps`, `vy_mps`, `wz_radps` after all final limiting and smoothing |
| `normalized_final_command` | Finite normalized three-axis value derived from final physical command using an explicitly versioned conversion rule and limits/hash |
| `receipt_id` or `command_sequence` | Unique receipt identity and or monotonic source sequence with stated uniqueness scope; not interchangeable with `transition_id` |
| `action_barrier_ros_ns` | ROS or simulation timestamp marking the final accepted handoff boundary in the same domain as later exact observations |
| `publish_or_handoff_status` | Explicit successful publish or handoff outcome; failure never carries a ready receipt |
| `provenance_version` | Receipt schema, normalization rule version, safety/config hash, and any required command-path identity |

The receipt may separately carry local steady receive time for diagnostics, but
it must not subtract, compare, or derive a simulation interval with
`action_barrier_ros_ns`. ROS or simulation timestamp and steady receive time
remain different clock domains.

## Required semantics and fail-closed rules

- Receipt creation occurs only after Safety path acceptance and successful final
  publish or approved transport handoff. It cannot be produced at PPO decode,
  history update, odometry measurement, or motor acknowledgement.
- One active transition can have at most one ready receipt. Duplicate receipt,
  replayed receipt ID, reused sequence, stale or future token, lifecycle
  mismatch, source mismatch, failed handoff, invalid physical value, or
  normalization mismatch fails closed.
- `transition_id` identifies a transition; `receipt_id` identifies a receipt.
  Neither implicitly replaces the other.
- Final physical values and normalized values must agree exactly with the
  approved conversion rule. No silent clamp, substitution, use of desired
  action, or reuse of an older receipt is permitted.
- If a command has already published and later scan, Oracle, reward,
  observation, or termination validation fails, the command is not rollbackable.
  Lifecycle enters `STEP_ABORT` or `FAULT`. Zero or inhibit request and
  post-publish recovery remain a separately approved runtime policy.

## Future uses after receipt validation

| Consumer or phase | Receipt use | Guard |
| --- | --- | --- |
| Committed PPO control step | Required command-side fact before candidate can progress to atomic transition commit | Receipt binding must match active lifecycle, active transition, and action barrier. Scenario session linkage is indirect: EpisodeLifecycle is its trusted owner, so receipt carries no separate ScenarioSessionBinding. |
| Previous-issued observation block | Copy only normalized final command from a receipt committed with the prior transition | Do not update on decode, failed handoff, aborted step, or replay |
| Reward smoothness | Compare two adjacent committed normalized final-issued receipts | No desired/decoder action substitution; both conversion versions must be compatible |
| Rollout and checkpoint provenance | Persist receipt identity, owner, source, physical/normalized command representation, conversion/config version, action barrier, and lifecycle/transition identities | Any receipt-schema or observation-semantic migration participates in checkpoint/hash compatibility |

No reward, observation runtime, command history, or checkpoint implementation is
created by this document.

## Decisions and evidence still required

| Item | Required status |
| --- | --- |
| Receipt owner | `REQUIRED_USER_DECISION`: select the final-publish or final-handoff owner and its lifecycle responsibility |
| Publish or handoff boundary | `REQUIRED_USER_DECISION`: define the exact successful boundary in simulation and deploy profiles |
| Safety and arbitration semantics | `REQUIRED_USER_DECISION`: select validation, arbitration, limiting, smoothing, source selection, and safe-stop behavior relevant to receipt creation |
| Normalized conversion | `REQUIRED_USER_DECISION`: define physical-to-normalized rule, axis order, limits/config version, hash, and migration behavior |
| Receipt ID and sequence | `REQUIRED_USER_DECISION`: define source, uniqueness scope, replay handling, reset/runtime-generation relation, and retention |
| Failure and recovery | `REQUIRED_USER_DECISION`: define post-publish fault, zero/inhibit owner, diagnostic retention, reset/restart handling; no rollback claim |
| ROS, Gazebo, and UART evidence | `REQUIRED_EVIDENCE`: prove final boundary, wrong-generation/replay rejection, failed handoff, barrier alignment, and profile-specific transport behavior |

`Heartbeat.sequence` is a heartbeat sequence, not a command sequence.
`SafetyState.msg` contains no receipt ID, transition token, publish or handoff
outcome, action barrier, or command sequence. `Heartbeat.msg` and
`SafetyState.msg` therefore do not by themselves satisfy this receipt contract.
Neither message changes the proposal that `FinalIssuedCommandReceipt` binds
directly to `EpisodeLifecycleIdentity` and `TransitionIdentity`, without a
separate ScenarioSessionBinding field: a valid lifecycle and transition link
indirectly to the session binding owned by EpisodeLifecycle.

## Future core test matrix

A later core-only increment must test at minimum:

| Test | Required evidence |
| --- | --- |
| Valid receipt | One finite, fully normalized receipt joins exactly one active lifecycle and transition |
| Duplicate and replay | Duplicate receipt, reused receipt ID, and reused sequence fail before commit and do not mutate history |
| Stale, future, and token mismatch | Wrong transition relation or same-step different token causes `STEP_ABORT` without receipt consumption |
| Lifecycle mismatch and indirect session link | Different episode/reset/runtime identity cannot join the active transition; lifecycle is the trusted indirect link to its committed scenario session, so receipt carries no separate session binding |
| Invalid values | Bool, NaN, infinity, non-finite physical command, invalid normalized command, and conversion mismatch fail closed |
| Abort after receipt | A later validation failure records no committed history or reward and does not claim the publish rolled back |
| Reset clearing | New generation clears pending and committed receipt state; old receipt cannot join the new episode |
| Isolation | Receipt core imports no ROS, Gazebo, TF, Gymnasium, SB3, policy observation, Ground Truth runtime object, or hardware transport code |

## Conclusion

PENDING_USER_DECISION

The core can already test transition-token and replay mechanics with a
`CommandReceiptSnapshot`, but it cannot represent or prove final issue. Receipt
owner, final boundary, safety semantics, normalization/versioning, sequence,
recovery policy, and runtime evidence are still required before D2 core or
runtime implementation approval. This document grants no ROS topic, Gazebo,
UART, motor, command, or hardware authority.
