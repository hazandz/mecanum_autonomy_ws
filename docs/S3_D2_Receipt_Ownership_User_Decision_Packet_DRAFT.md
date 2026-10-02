# S3 D2 Receipt Ownership User Decision Packet

Status: DRAFT — PENDING_USER_DECISION

## Purpose and authority

This packet asks the user to select the ownership and boundary for a future
final-issued command receipt. It does not create a receipt type, publish a
command, open a transport, alter an interface, or authorize runtime behavior.

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

## Conditional recommendation

**PROPOSED — PENDING_USER_APPROVAL:** `FinalTwistPublisher` owns
`FinalIssuedCommandReceipt` after all SafetySupervisor arbitration, validation,
limiting, and smoothing have completed and after the selected final command has
successfully crossed the profile-specific final boundary.

`SafetySupervisor` remains owner of the safety decision and final command
selection. It is not by itself the publish receipt owner. The receipt owner
must record the selected Safety result and its provenance rather than repeat or
bypass safety arbitration.

| Profile boundary | Proposed receipt moment | What the receipt proves | What it does not prove |
| --- | --- | --- | --- |
| Simulation final `/cmd_vel` boundary | `FinalTwistPublisher` successfully publishes the final selected Twist through the approved simulation command boundary | Final selected command was accepted at the final ROS publish boundary for the active transition | Gazebo application time, robot movement, collision state, reset receipt, or actuator acknowledgement |
| Deployment transport handoff boundary | `FinalTwistPublisher` successfully hands the final selected command to the approved bridge transport boundary | Final selected command crossed the defined ROS-to-transport handoff for the active transition | MCU ACK, UART delivery, watchdog refresh, motor driver action, or motor movement |

The deployment transport may add independent transport or MCU diagnostics later,
but those are not this receipt unless a separate authority explicitly changes
the boundary. A receipt is never MCU ACK or proof of motor motion.

## Proposed core-only binding rule

A future `FinalIssuedCommandReceipt` binds directly to:

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

## Decisions required from the user

| Decision | Required approval |
| --- | --- |
| Receipt owner | Approve or replace the conditional recommendation that FinalTwistPublisher owns the receipt after successful final boundary crossing |
| Exact final boundary | Define simulation `/cmd_vel` publish boundary and deployment ROS-to-transport handoff boundary separately |
| Command source and sequence | Define allowed source identity, source selection relation to SafetySupervisor, receipt ID and or command sequence, uniqueness scope, replay behavior, and reset/runtime-generation relation |
| Normalization | Define final physical-to-normalized conversion, axis order, limits/config version/hash, and observation/checkpoint migration |
| Failure recovery | Define post-publish `STEP_ABORT`/`FAULT`, zero or inhibit owner, diagnostic retention, reset/restart policy, and explicit non-rollback behavior |
| Runtime evidence | Require proof of final boundary behavior, wrong-generation/replay rejection, failed publish/handoff, action-barrier alignment, and profile-specific simulation/deployment behavior |

## Approval checklist

- [ ] Approve `FinalTwistPublisher` as receipt owner, or identify another owner.
- [ ] Approve the distinct simulation final publish and deployment transport
      handoff boundaries.
- [ ] Approve receipt ID and command-sequence ownership and replay scope.
- [ ] Approve final physical-to-normalized conversion and its version/hash.
- [ ] Approve source/arbitration and SafetySupervisor-to-receipt provenance.
- [ ] Approve post-publish zero/inhibit and recovery ownership without rollback.
- [ ] Approve required runtime evidence before any receipt implementation is
      relied upon by observation, reward, rollout, or checkpoint logic.

## Conclusion

PENDING_USER_DECISION

The architecture supports a conditional FinalTwistPublisher receipt-owner
recommendation, while SafetySupervisor remains the safety decision owner. The
exact owner, profile boundaries, conversion, replay rules, recovery policy, and
runtime evidence remain user decisions. This packet grants no ROS, Gazebo,
`/cmd_vel`, UART, MCU, motor, or hardware approval.
