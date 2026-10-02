# S3 D3 — Typed Scene Observer S3.3.45 Replacement Runtime Run Approval Packet

**Status: DRAFT — REPLACEMENT RUNTIME RUN PENDING USER APPROVAL**

## Purpose

This is the proposed sole authority for one future Typed Scene observer runtime
run. It replaces S3.3.44 as the candidate because S3.3.45 adds trusted live
filesystem context and lease ownership. S3.3.44 and all historical/consumed
guards remain immutable and are not modified by this packet.

This document creates no execution authority. Its S3.3.45 guard is initialized
only as `authorized_not_consumed` and may not be acquired or consumed until the
user explicitly approves this exact packet and approval ID.

## Approval identity, literals, and cardinality

| Item | Locked value |
| --- | --- |
| Approval ID | `S3.3.45_TYPED_SCENE_OBSERVER_REPLACEMENT_RUNTIME_RUN` |
| World / entity | `world_demo` / `ROBOT_URDF_final` |
| Scene request | `/world/world_demo/scene/info`: `gz::msgs::Empty → gz::msgs::Scene` |
| Exact hierarchy | `ROBOT_URDF_final → base_link → s3_d3_base_contact_sensor` |
| Collision literal | `s3_d3_base_contact_collision` |
| Ownership mode | `SUPERVISOR_OWNED_CREATE_V1` |
| Direct executable | `/opt/ros/jazzy/lib/ros_gz_sim/create` |
| Exact create argv | `-topic /robot_description -name ROBOT_URDF_final -allow_renaming false -x 0 -y 0 -z 0.1 -Y 0` |
| Create timings | `90000 ms` timeout; `2000 ms` Candidate-A guard; `5000 ms` SIGINT grace |
| Helper timings | `90000 ms` preflight; `5000 ms` request; `10 ms` polling |
| Taxonomy | Candidate A `SCENE_*_NOT_OBSERVED_AFTER_DELAY`; never `SCENE_*_ABSENT` |
| One-shot boundary | One create; one `RequestRaw`; no retry; capacity `1`; SIGINT-only |

## Trusted live-context inputs

The future guard must build context itself from the workspace root; callers may
not pass arbitrary hash/literal contexts. Each workspace-relative input must
remain under the explicit root, be non-symlinked, exist, and be a regular file.
The fixed direct executable must be exactly the absolute path above, non-symlinked,
and regular. Any violation fails closed before lock acquisition.

| Input | Locked path | SHA-256 |
| --- | --- | --- |
| Packet | `docs/S3_D3_Typed_Scene_Observer_S3_3_45_Replacement_Runtime_Run_Approval_Packet_DRAFT.md` | Bound externally by guard after final packet bytes are finalized |
| Supervisor adapter | `artifacts/simulation/contact_producer_evidence/tools/run_typed_scene_observer.py` | `e2ac8919b4ebded391d13f77283b1948b33191828d9d0a80d6425f2936cb6919` |
| Dedicated launch | `ros2_ws/src/ROBOT_URDF_final_description/launch/typed_scene_observer.launch.py` | `b6acf767471527f37c4e2d7c67cc46b693298cb4bf7028afb96be8d00c4f255d` |
| Typed Scene helper | `artifacts/simulation/contact_producer_evidence/tools/typed_scene_observer.cpp` | `f8a56927f523deb0dd0b59eed30cab5bd571773176e45d6447bf1c62247d014d` |
| Guard helper | `artifacts/simulation/contact_producer_evidence/tools/typed_scene_replacement_approval_guard.py` | `10e0a641e283cfdb08c9b0e1492a4a181adc44fe5c0281c6e6bf58e1b85bbc9f` |
| World SDF | `ros2_ws/src/ROBOT_URDF_final_description/launch/tugbot_depot.sdf` | `1c50f90d151a12559d426796c5d153c829b8777a5b4e8ef94c007a2023f6e271` |
| Direct create executable | `/opt/ros/jazzy/lib/ros_gz_sim/create` | `549a91ca31d5b943457b1fa6ae25cc726867b6afa69d789e1afbd2af139fe02d` |

## Lease-bound guard requirement

The S3.3.45 guard must hash these live inputs itself, then compare them against
its immutable record. `acquire()` creates a new lock directory and an exclusive
`lease.json` containing the approval ID, canonical context digest, and a random
secret nonce. It returns an immutable lease containing the same three values.

Future `consume()` must rebuild trusted context and require exact approval ID,
lock path, context digest, nonce, and untampered lock metadata. Lock absence,
malformation, tampering, context drift, token mismatch, lock collision, or
atomic-write failure is fail-closed. A crash-left lock remains a blocker; it is
not automatically removed or bypassed.

## Future operation boundary — only after separate approval

```text
dedicated bootstrap launch
→ one supervisor-owned direct create child
→ Candidate-A exit-zero operational convention + 2000 ms guard
→ one typed ServiceList preflight
→ exactly one Empty → Scene RequestRaw
→ SIGINT-only shutdown
```

No approval is granted for `/cmd_vel`, ROS/Gazebo bridge, parameter bridge,
static TF, pose/reset/delete/pause/step/world-control, second spawn, teleop,
Nav2, PPO, Gymnasium, SB3, raw-contact collection, UART, STM32, Pi, motor,
firmware, or hardware. Exit `0` and delay remain operational only, not a Scene,
entity, reset, or settled-state receipt.

## Required user approval

The user must explicitly approve `S3.3.45_TYPED_SCENE_OBSERVER_REPLACEMENT_RUNTIME_RUN`, every literal and hash above,
the trusted-context/lease mechanism, one-create/one-request cardinality,
Candidate-A taxonomy, no retry, and SIGINT-only shutdown. This draft has no
runtime authority.

## Non-claims

A future Scene response still cannot prove raw-contact delivery, collision event,
ContactLatch, collision policy, reward, termination, Gym/training, TF authority,
reset/settle receipt, or hardware readiness.

## Conclusion

**DRAFT — REPLACEMENT RUNTIME RUN PENDING USER APPROVAL**

## S3.3.46 supersession record

**SUPERSEDED — NOT ACQUIRED.** S3.3.45 was a pending candidate only. Its guard
was never acquired or consumed and remains immutable. S3.3.46 supersedes it
because the guard source now exposes the explicit `build_trusted_context`,
`acquire_trusted`, and `consume_trusted` interfaces required for the next
candidate. This statement grants no runtime authority.
