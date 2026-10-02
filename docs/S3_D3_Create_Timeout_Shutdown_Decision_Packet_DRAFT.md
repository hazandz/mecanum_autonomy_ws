# S3 D3 — Create Timeout Shutdown Decision Packet

**Status: USER_DECIDED_FOR_FUTURE_RUNTIME_BOUNDARY**

## Purpose

This packet records the user-selected literal for the future cleanup boundary
after a supervisor-owned `ros_gz_sim create` timeout. It does not authorize
launch, Gazebo, ROS, `ros_gz_sim create`, helper execution, `RequestRaw`,
bridge, command/control, guard acquisition, or hardware activity.

S3.3.42 has implemented and offline-validated the injected timeout/shutdown
contract. It does not implement a runtime execution path. The authority is the [bootstrap create-outcome ownership design](S3_D3_Bootstrap_Create_Outcome_Ownership_Design_DRAFT.md).

## Locked prior literals

| Literal | Value | Meaning limited to |
| --- | --- | --- |
| Ownership mode | `SUPERVISOR_OWNED_CREATE_V1` | Future supervisor directly owns one bootstrap create child. |
| Create timeout | `create_timeout_ms=90000` | Maximum wait for the one child’s exit outcome. |
| Post-create delay | `post_create_delay_ms=2000` | Candidate-A operational guard after exit `0`; not a Scene receipt. |
| Cardinality | One create, one Scene `RequestRaw`, no retry, capacity `1` | Future approved run only. |
| Shutdown signal | `SIGINT-only` | Only a measurement-created direct child process group. |

## S3.3.42 user decision record

**USER_DECIDED_FOR_FUTURE_RUNTIME_BOUNDARY**

| Decision | User-selected value | Scope |
| --- | --- | --- |
| `create_shutdown_grace_ms` | `5000 ms` | Future runtime timeout cleanup only; not execution authority. |

## Future timeout boundary — implemented offline only

```text
one directly owned create child exceeds create_timeout_ms
→ record SCENE_CREATE_OUTCOME_UNCONFIRMED and SCENE_BOOTSTRAP_UNCONFIRMED
→ send SIGINT only to that measurement-created direct child process group
→ wait exactly `create_shutdown_grace_ms=5000`
→ child exited: retain timeout outcome; no helper and no RequestRaw
→ child still alive: outer SHUTDOWN_INCOMPLETE; retain blocker; no future run
```

A timeout, an exit during cleanup, or an incomplete shutdown is not a
Gazebo acceptance receipt, entity/Scene receipt, reset receipt, settled-state
proof, or explanation of spawn behavior. The supervisor may not use SIGTERM,
SIGKILL, `.kill()`, `kill -9`, a force-kill fallback, a helper call, a second
create, or any retry.

## Guard and replacement-packet impact

A future replacement execution packet and capacity-one guard must bind the
chosen grace literal alongside the create executable path/SHA-256, exact argv,
world/launch/helper hashes, Candidate-A taxonomy, one-request rule, and
SIGINT-only policy. If execution later consumes that authority, every terminal
outcome—including timeout or `SHUTDOWN_INCOMPLETE`—must consume the approval and
prevent automatic rerun.

The timeout grace decision is now recorded, but the typed Scene path remains:

```text
READY_FOR_REPLACEMENT_RUNTIME_PACKET_AND_NEW_GUARD
→ no replacement execution packet yet
→ no new guard yet
→ no runtime operation
```

## Non-claims

This packet does not approve a runtime run, launch, create child, helper,
`RequestRaw`, Scene observation, raw contact endpoint, collision event,
ContactLatch, reward, termination, Gym/training, or hardware operation.

## Conclusion

**USER_DECIDED_FOR_FUTURE_RUNTIME_BOUNDARY — RUNTIME_NOT_APPROVED**
