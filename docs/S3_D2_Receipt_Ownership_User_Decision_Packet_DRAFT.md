# S3 D2 Receipt Ownership User Decision Packet

Status: DRAFT — APPROVED DISPOSITIONS RECORDED; AUDIT AND CANONICAL INTEGRATION PENDING

## Purpose and authority

This packet records the Project Owner/User-authorized ownership and boundary
dispositions for reconciliation in this candidate. It does not create a receipt
type, publish a command, open a transport, alter the canonical interface, or
authorize implementation or runtime behavior.

Source decision packet: `WP-03_USER_DECISION_RESOLUTION_PROPOSAL.md`; branch `wp-03-decision-packet-baseline-2e7a2980`; commit `473d1cc6265dc14230fa47a89546b14a9de2a6eb`; SHA-256 `3559f21a07520f10ac1dceb0c2e6f888597a0215a63a5b8b91fce10d340e583c`.
Independent audit verdict supplied with the authorization: `READINESS_FOR_USER_REVIEW: APPROVABLE` (audit report SHA was not provided).

The selected dispositions remain a draft candidate until independent audit and
canonical integration.

Authority is [MECANUM NAV DRL Architecture](MECANUM_NAV_DRL_Architecture.docx),
schema `3.0`, SHA-256
`f0fb1ebede5f4fa18604610c04bb13587d456173b4fd942dba77e44d49777860`.
It follows [S3 D2 Final Issued Command Receipt Design](S3_D2_Final_Issued_Command_Receipt_Design_DRAFT.md),
[S3 Control Step And Simulation Time Contract](S3_Control_Step_And_Simulation_Time_Contract_DRAFT.md),
and [S3 Reward v3 Core Scope And Input Contract](S3_Reward_v3_Core_Scope_And_Input_Contract_DRAFT.md).

D2-B explicit `transition_id` remains user-selected for core-only token joining.
It does not select a receipt owner, a final boundary, or runtime approval.

## Candidate-owner audit

| Candidate | Existing authority or evidence | Strength | Limitation |
| --- | --- | --- | --- |
| `SafetySupervisor` | Architecture owns final selection, validation, arbitration, limiting, and smoothing | Knows which command is safe and selected | Safety acceptance is not itself evidence that the selected command crossed a final publish or transport boundary |
| `FinalTwistPublisher` | Architecture assigns it sole final `/cmd_vel` publication ownership | Natural owner for a post-final-publish receipt in profiles using final ROS command publication | It needs an explicit simulation and deployment handoff contract; no implementation or graph evidence exists today |
| Bridge transport | Existing `mecanum_base_bridge` has pure codec and sequence-gate tests | May observe a deployment transport handoff after ROS final publisher boundary | Codec acceptance is neither Safety arbitration, final ROS publish, MCU ACK, nor motor-motion proof |

`SafetyState.msg` is a future safety-status interface with raw, limited, and
final Twist snapshots plus source/state fields. It does not carry a receipt ID,
transition token, publish outcome, action barrier, or command sequence.
`Heartbeat.sequence` is heartbeat sequencing, not command sequencing. These
messages cannot substitute for a receipt.

## Approved disposition for this reconciliation candidate

`FinalTwistPublisher` owns `FinalIssuedCommandReceipt` only after the selected
final command has successfully crossed the applicable approved profile
boundary. `SafetySupervisor` remains the sole owner of safety arbitration,
validation, limiting, smoothing, and final-command selection. Receipt creation
records that result and cannot bypass or repeat safety selection.

| Profile | Approved receipt boundary | Explicit non-claim |
| --- | --- | --- |
| Simulation | `FinalTwistPublisher` has successfully locally issued the final selected `Twist` through the approved simulation `/cmd_vel` boundary. Starting the publish call is insufficient. | No DDS delivery, Gazebo application, robot movement, collision state, actuator acknowledgement, or achieved velocity is proven. |
| `deploy_real` | No handoff boundary is approved. Receipt use remains unavailable until a separate D2 contract defines and approves a ROS-to-transport handoff role and success condition. | No UART delivery, MCU acknowledgement, watchdog refresh, motor-driver action, or motion claim. |

## Proposed core-only binding rule

The approved candidate binding for `FinalIssuedCommandReceipt` is directly to:

```text
EpisodeLifecycleIdentity
TransitionIdentity
```

It contains no separate `ScenarioSessionBinding`. `EpisodeLifecycle` is the
trusted owner of the committed scenario session. Therefore, a receipt that
matches the active lifecycle and active transition has the required indirect
session link; the lifecycle must reject lifecycle or transition mismatch before
receipt commit. This does not allow a receipt to self-anchor a lifecycle or
scenario session.

## Objects that must not substitute for a receipt

| Object | Why it is not a final-issued receipt |
| --- | --- |
| PPO desired action | Policy proposal precedes decoder and every safety or publish decision |
| Decoder-accepted command | Validated candidate has not passed Safety arbitration or final boundary |
| `PreviousActionHistory` | Current core history stores decoder-accepted action, not receipt-backed final issue |
| `SafetyState.final_command` | A status snapshot lacks transition token, receipt ID, handoff outcome, barrier, and command sequence |
| `Heartbeat.sequence` | Heartbeat sequence is not command sequence or publish provenance |
| UART codec acceptance | Codec test gate does not prove Safety selection, final boundary handoff, MCU ACK, or movement |
| MCU ACK | Transport acknowledgement is not final ROS publish receipt and does not prove motor movement |
| Measured twist or motor movement | Measurement occurs after command path and does not prove which command crossed the final boundary |

## Approved identity, command, and failure dispositions

The receipt binds directly to the active `EpisodeLifecycleIdentity` and
`TransitionIdentity`; scenario/session linkage is indirect through
`EpisodeLifecycle`, with no separate `ScenarioSessionBinding`. The v2 schema
uses its existing primitive fields and this packet adds no wire fields.
`source`, `sequence`, `reset_epoch`, `runtime_generation`, and
`source_instance_id` retain the approved `CommandEnvelope` meanings.
`FinalTwistPublisher` owns `final_publisher_instance_id` and its strictly
increasing `final_publish_sequence` (starting at 1 per publisher instance and
not reset by `reset_epoch`). The pair is receipt transport identity, not a
substitute for `TransitionIdentity`.

The receipt's `final_command` is the final physical `base_link` planar command
`(vx, vy, wz)` after safety limiting/smoothing. A normalized value may be used
only when an exact approved profile/config contract supplies conversion,
axis-order, limits, version, and hash/provenance; this candidate selects no
numeric or configuration value. A failed publish/handoff never yields a ready
receipt. A later failure after issuance is `STEP_ABORT` or `FAULT`, without a
rollback claim. `SafetySupervisor` owns safe-action selection;
`CommandArbiter` creates the envelope. Reset clears staged/committed receipt
state before a new lifecycle uses it.

## Remaining evidence and unresolved values

| Obligation | Status |
| --- | --- |
| Simulation final-boundary behavior; duplicate/replay and generation/transition rejection; failed publish/handoff; action-barrier alignment | Future runtime evidence required; not claimed to exist. |
| Profile/config-specific normalized conversion, limits, version and hash | No values selected; requires an exact controlling contract before normalized use. |
| `deploy_real` receipt/handoff | Unavailable pending a separate approved contract and future evidence. |

## Conclusion

`DRAFT_FOR_INDEPENDENT_AUDIT_AND_CANONICAL_INTEGRATION`

The authorized dispositions are recorded for this candidate; no implementation
or runtime evidence is claimed. This packet grants no code, ROS, ROSIDL, Gazebo,
`/cmd_vel`, UART, MCU, motor, hardware, `deploy_real`, or runtime approval.
