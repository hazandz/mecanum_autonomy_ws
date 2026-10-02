# S3 D3 — Spawn Readiness User Decision Packet

**Status: DRAFT — OPTION A IMPLEMENTED OFFLINE ONLY — NO_EXECUTION_AUTHORITY**

## Purpose

This packet asks for one decision about bootstrap readiness before a replacement
typed Scene runtime packet or new guard can be created. It does not authorize
launch, Gazebo, ROS, `gz`, `ros_gz_sim create`, helper runtime, `RequestRaw`,
bridge, command/control, guard operation, or hardware.

The authority is the [spawn-completion and Scene-readiness design](S3_D3_Spawn_Completion_And_Scene_Readiness_Design_DRAFT.md). The dedicated launch is
already static-validated and now contains no launch-owned create. The
supervisor-owned create contract and its delay gate remain only offline
implementation; neither proves that the initial entity is represented in a
Scene response.

## Available choices

| Candidate | Status | What it permits if chosen | What it cannot prove |
| --- | --- | --- | --- |
| **A — create exit-success + fixed delay** | The only currently describable operational option. | One Scene `RequestRaw` only after the user-approved create-exit convention and `post_create_delay_ms`. | Entity/Scene existence, reset receipt, settled state, atomic insertion, collision, or ContactLatch. |
| **B — machine-readable bootstrap receipt** | `NO_LOCAL_MACHINE_READABLE_BOOTSTRAP_RECEIPT_CONFIRMED`. | Nothing now. It can be reconsidered only after a separate static evidence/design effort proves the approved bootstrap route’s exact receipt semantics. | Any current replacement-run readiness claim. |

Candidate A was selected only for S3.3.40 offline implementation and validation.
Candidate B must not be selected implicitly or treated as available merely
because other `ros_gz_sim` utilities exist.

## S3.3.40 decision record

**USER_DECISION_FOR_OPTION_A_OFFLINE_IMPLEMENTATION_ONLY**

| Decision | Recorded value |
| --- | --- |
| Ownership | `SUPERVISOR_OWNED_CREATE_V1` |
| Create timeout | `90000 ms` |
| Post-create delay | `2000 ms` |
| Exit-zero meaning | Candidate-A operational convention only, never a Scene/entity/reset/settled-state receipt. |
| Negative taxonomy | `*_NOT_OBSERVED_AFTER_DELAY` only; never Candidate-A `*_ABSENT`. |
| One-shot boundary | One create, one `RequestRaw`, no retry, capacity `1`, SIGINT-only. |

This record authorizes no runtime execution, guard creation/acquisition, launch,
create child, helper invocation, or request.

## Historical required choices — resolved for offline implementation

| Decision | User must provide or confirm |
| --- | --- |
| Readiness mechanism | Candidate A for offline implementation only; Candidate B remains unavailable. |
| Candidate A delay | `post_create_delay_ms=2000`; an operational guard, not a default or settle/freshness/reset policy. |
| Candidate A negative taxonomy | Accept that zero exact hierarchy members become `SCENE_MODEL_NOT_OBSERVED_AFTER_DELAY`, `SCENE_LINK_NOT_OBSERVED_AFTER_DELAY`, or `SCENE_SENSOR_NOT_OBSERVED_AFTER_DELAY`, never `*_ABSENT`. |
| One-shot boundary | Confirm exactly one `RequestRaw`, no retry, capacity `1`, and SIGINT-only shutdown. |

## Already locked literals — not decisions reopened here

| Literal | Locked value |
| --- | --- |
| `preflight_wait_ms` | `90000` |
| `request_timeout_ms` | `5000` |
| `polling_interval_ms` | `10` |
| Capacity | `1` |
| Shutdown | `SIGINT-only` |

These are replacement packet/guard literals. They are not a readiness decision,
settle threshold, freshness policy, reset policy, or retry permission.

## Candidate A state and result contract

```text
create outcome missing/error/unverifiable
→ SCENE_BOOTSTRAP_UNCONFIRMED
→ do not call RequestRaw

create exit-success convention + approved post_create_delay_ms
→ SCENE_BOOTSTRAP_READY_FOR_ONE_REQUEST
→ exactly one RequestRaw
```

After Candidate A, a decoded response can positively report
`SCENE_SENSOR_PRESENT_IDENTITY_ONLY` only when its exact hierarchy is present.
Negative hierarchy outcomes must use the `NOT_OBSERVED_AFTER_DELAY` taxonomy.
Malformed, duplicate, or undecodable responses remain
`SCENE_RESPONSE_UNDECODABLE`.

`SCENE_MODEL_ABSENT`, `SCENE_LINK_ABSENT`, and `SCENE_SENSOR_ABSENT` remain
reserved for a future Candidate B only after its machine-readable receipt is
proven and user-approved.


## S3.3.39 create-outcome ownership gate

The former create-outcome ownership blocker is resolved only at offline
implementation scope. See the [bootstrap create-outcome ownership design](S3_D3_Bootstrap_Create_Outcome_Ownership_Design_DRAFT.md). A future runtime packet and new guard must bind the supervisor-owned mode and exact timeout/delay literals. No log parsing is permitted.

## Required next step

Create one replacement runtime approval packet and one new capacity-one guard
that bind the dedicated launch, helper, world revision, supervisor-owned
readiness mechanism, approved delay, one-request rule, and all locked literals.
This packet itself creates neither.

## Non-claims

No choice here proves a reset receipt, settled state, collision event,
ContactLatch, collision policy, reward, termination, Gym/training, raw-contact
delivery, TF authority, or hardware readiness.
