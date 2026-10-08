# S3 D2 Final Issued Command Receipt Design

Status: DRAFT — APPROVED DISPOSITIONS RECORDED; WP-03 CLOSURE ACTIVATION GOVERNED BY PEP-001 REV.0.4.0

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

D2-B, explicit `transition_id`, remains user-selected for core-only token joining.
The Project Owner/User-authorized D2 dispositions are recorded in
`docs/governance/decisions/WP-03_CONTRACT_CLOSURE_DECISIONS.md`; canonical
WP-03 closure activation is governed by PEP-001 rev.0.4.0.

Source decision packet: `WP-03_USER_DECISION_RESOLUTION_PROPOSAL.md`; branch `wp-03-decision-packet-baseline-2e7a2980`; commit `473d1cc6265dc14230fa47a89546b14a9de2a6eb`; SHA-256 `3559f21a07520f10ac1dceb0c2e6f888597a0215a63a5b8b91fce10d340e583c`.
Independent focused audit: `INDEPENDENT_FOCUSED_STATIC_AUDIT_WP03_DECISION_CONTRACT_RECONCILIATION_B234C2FE.md`; SHA-256 `7db8347459af8762da1b74afd99c765a9121e43c2453363049c3f00c0256110f`; `READINESS_FOR_CANONICAL_INTEGRATION: PASS`.

The dispositions are authorized and recorded. Their canonical WP-03 closure
effect follows the PEP-001 rev.0.4.0 activation rule. They do not prove a command
was published or authorize implementation or runtime.

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

| Receipt contract element | Recorded candidate disposition / v2 schema mapping |
| --- | --- |
| Lifecycle identity | Bind directly using the v2 primitive fields `episode_generation`, `reset_epoch`, and `runtime_generation`; do not add a nested identity message. |
| Transition identity | Bind directly using `step_index` and explicit `transition_id` (D2-B). |
| Logical owner | `FinalTwistPublisher` owns receipt creation after the approved profile boundary; this is a logical ownership decision, not an added wire field. |
| Safety and source provenance | `SafetySupervisor` remains the sole safety selector. The receipt's `source`, `sequence`, and `source_instance_id` retain their `CommandEnvelope` semantics; `CommandArbiter` creates the new-epoch `SOURCE_SAFE_STOP` zero envelope under SafetySupervisor authority. |
| Final command | The v2 `final_command` is the finite physical `base_link` planar Twist (`linear.x=vx`, `linear.y=vy`, `angular.z=wz`; other components zero) after final safety limiting/smoothing. |
| Receipt transport identity | `final_publisher_instance_id` plus `final_publish_sequence`; the latter starts at 1 per publisher instance, increases strictly, and does not reset at `reset_epoch`. It does not replace `TransitionIdentity`. |
| Timestamp and barriers | `header.stamp` records the receipt timestamp. `SafetyLifecycle` owns action/reset barriers; readiness uses the QoS6 predicate against those externally supplied barriers. No `action_barrier_ros_ns` wire field is added. |
| Normalized command | The v2 schema carries the physical `final_command`; it adds no normalized-command field. Any normalized use requires an exact approved profile/config conversion rule, axis order, limits, version and provenance. No value or config hash is selected here. |
| Failure outcome | Failed publish/handoff never produces a ready receipt. Later validation failure after issuance is `STEP_ABORT` or `FAULT`, without a rollback claim. |

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

## Approved dispositions and remaining evidence

The user-authorized choices are recorded in the governing decision record; they are not a
standalone status transition or implementation approval.

| Item | Approved disposition | Remaining evidence or unresolved value |
| --- | --- | --- |
| Receipt owner | `FinalTwistPublisher` creates the receipt after the successful profile boundary. `SafetySupervisor` alone owns arbitration, validation, limiting, smoothing, and final selection. | No runtime publisher or graph evidence is claimed. |
| Profile boundary | Simulation: successful local issuance through the approved `/cmd_vel` boundary; merely starting publish is insufficient. `deploy_real`: no approved handoff boundary and no receipt capability until a separate D2 contract defines and approves one. | Simulation boundary evidence and any future deploy handoff evidence remain obligations. |
| Identity and sequence | Bind direct lifecycle and transition identities; retain v2 primitive identity/source fields and separate publisher-instance/final-publish sequence semantics. Scenario/session linkage remains indirect via `EpisodeLifecycle`. | Runtime replay, lifecycle, sequence, and barrier evidence remain pending. |
| Command representation | `final_command` is physical planar Twist after safety selection; normalized reuse requires a separately exact, versioned and hashed conversion rule. | No limits, profile, `config_hash`, or resolved configuration are selected here. |
| Failure and recovery | No ready receipt on failed publish/handoff. A later validation failure after issuance is `STEP_ABORT` or `FAULT`, without rollback claim. SafetySupervisor selects safe action; CommandArbiter constructs the envelope; reset clears staged/committed receipt state before another lifecycle. | Runtime failure/restart/reset behavior is not evidenced; any profile-specific recovery value remains future contract work. |
| Evidence | Preserve the packet's future obligations: simulation boundary, duplicate/replay/generation/transition rejection, failure behavior, action-barrier alignment, profile-specific transport, and any future deploy handoff. | These are obligations, not evidence claimed to exist. |

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

`APPROVED_DISPOSITIONS_RECORDED; WP-03 CLOSURE ACTIVATION PER PEP-001 REV.0.4.0`

The authorized D2 dispositions are recorded in the governing decision record. The core can
still test only its existing transition-token/replay mechanics; it does not
represent or prove final issue. Profile values and runtime evidence remain
unresolved obligations. This document grants no code, ROS topic, ROSIDL,
Gazebo, UART, motor, command, hardware, or runtime authority.
