# S3 D3 — Typed Scene Observer S3.3.47 Replacement Runtime Run Approval Packet

**Status: DRAFT — REPLACEMENT RUNTIME RUN PENDING USER APPROVAL**

## Authority boundary

This is the sole pending candidate for one future Typed Scene observer run. It
supersedes the S3.3.46 candidate because the final supervisor source now has an
injectable, guard-gated orchestration path. S3.3.46 was not acquired or
consumed; its guard remains immutable. This packet and its new guard create no
execution authority until the user explicitly approves the approval ID below.

## Approval ID and immutable contract

| Item | Locked value |
| --- | --- |
| Approval ID | `S3.3.47_TYPED_SCENE_OBSERVER_REPLACEMENT_RUNTIME_RUN` |
| World / entity | `world_demo` / `ROBOT_URDF_final` |
| Scene request | `/world/world_demo/scene/info`: `gz::msgs::Empty → gz::msgs::Scene` |
| Exact hierarchy | `ROBOT_URDF_final → base_link → s3_d3_base_contact_sensor` |
| Collision literal | `s3_d3_base_contact_collision` |
| Ownership mode | `SUPERVISOR_OWNED_CREATE_V1` |
| Direct create | `/opt/ros/jazzy/lib/ros_gz_sim/create` with `-topic /robot_description -name ROBOT_URDF_final -allow_renaming false -x 0 -y 0 -z 0.1 -Y 0` |
| Create timings | timeout `90000 ms`; Candidate-A post-create delay `2000 ms`; SIGINT grace `5000 ms` |
| Helper timings | ServiceList preflight/request/poll `90000/5000/10 ms` |
| Candidate-A taxonomy | `SCENE_*_NOT_OBSERVED_AFTER_DELAY`, never `SCENE_*_ABSENT` |
| Cardinality / shutdown | One dedicated bootstrap launch, one direct create, one `RequestRaw`, no retry, capacity `1`, SIGINT-only |

## Locked filesystem context

Before any future subprocess, the supervisor must call
`build_trusted_context(workspace_root)` and then
`acquire_trusted(guard_path, workspace_root)`. Neither the command line nor an
external caller may supply hashes, literals, or an alternate context. The
context builder resolves the locked paths below under the explicit workspace
root, rejects traversal, missing/non-regular files, final symlinks, and
intermediate symlinks, then hashes each source. The direct executable must be
exactly the stated absolute path, a non-symlinked regular file.

| Input | Locked path | SHA-256 |
| --- | --- | --- |
| Packet | `docs/S3_D3_Typed_Scene_Observer_S3_3_47_Replacement_Runtime_Run_Approval_Packet_DRAFT.md` | Bound after final bytes by the S3.3.47 guard |
| Supervisor | `artifacts/simulation/contact_producer_evidence/tools/run_typed_scene_observer.py` | `4eb499c5a29b880b82b352521854e691ece9f361e58f9baca989386ffa3a9a4d` |
| Dedicated launch | `ros2_ws/src/ROBOT_URDF_final_description/launch/typed_scene_observer.launch.py` | `b6acf767471527f37c4e2d7c67cc46b693298cb4bf7028afb96be8d00c4f255d` |
| Typed Scene helper | `artifacts/simulation/contact_producer_evidence/tools/typed_scene_observer.cpp` | `f8a56927f523deb0dd0b59eed30cab5bd571773176e45d6447bf1c62247d014d` |
| Guard helper | `artifacts/simulation/contact_producer_evidence/tools/typed_scene_replacement_approval_guard.py` | `e117f205f81866a7ccac8f4a5942e2794aa73cea0ed1c3bf26aa0abcb55d47a1` |
| World SDF | `ros2_ws/src/ROBOT_URDF_final_description/launch/tugbot_depot.sdf` | `1c50f90d151a12559d426796c5d153c829b8777a5b4e8ef94c007a2023f6e271` |
| Direct create executable | `/opt/ros/jazzy/lib/ros_gz_sim/create` | `549a91ca31d5b943457b1fa6ae25cc726867b6afa69d789e1afbd2af139fe02d` |

Any packet/source/world/executable hash or literal mismatch fails closed before
launch or create. This table is not evidence that the future run is approved.

## Guard and lease ownership

The S3.3.47 guard is capacity one and initially `authorized_not_consumed`.
`acquire_trusted` validates the live context, creates one exclusive lock, and
writes `lease.json` containing the approval ID, canonical context digest, and a
cryptographically random nonce. It returns an immutable lease with those same
bindings. `consume_trusted` rebuilds context and requires exact approval ID,
context digest, nonce, lock path, and untampered lock metadata.

Any malformed record, mismatch, atomic-write failure, lock collision, missing
metadata, lease-token error, source drift, or crash-left lock fails closed. A
crash-left lock is never removed or bypassed automatically. Every terminal
result after successful acquire—including `INVALID`, persistence failure, and
`SHUTDOWN_INCOMPLETE`—must attempt consumption. A failed consume remains an
explicit blocker, never reusable authority.

## Future sequence — only after explicit user approval

```text
dedicated bootstrap launch
→ one supervisor-owned direct create child
→ exit-zero Candidate-A operational convention + 2000 ms delay
→ compile helper in a temporary directory
→ one typed ServiceList preflight
→ exactly one Empty → Scene RequestRaw
→ persist run artifact
→ SIGINT-only shutdown of measurement-created process groups
→ consume this approval guard
```

The sequence is injectable and has only been mock-tested. `--execute` requires
`--workspace-root`, `--approval-id`, and `--guard-path`; it accepts only this
approval ID. Without a future user-approved runtime dependency binding it exits
before trusted-context construction, guard acquisition, `Popen`, launch, or any
runtime I/O. No command-line switch bypasses that condition.

## Strict exclusions

No authority is granted for `/cmd_vel`, ROS/Gazebo bridge, parameter bridge,
static TF, pose/reset/delete/pause/step/world-control, a second spawn, teleop,
Nav2, PPO, Gymnasium, SB3, raw-contact collection, UART, STM32, Pi, motor,
firmware, or hardware. There is no shell invocation, stdout/stderr parsing,
retry, `SIGTERM`, `SIGKILL`, or force-kill fallback.

Exit `0` plus the delay is only an operational Candidate-A barrier. It is not a
Scene/entity, reset, atomic insertion, or settled-state receipt. A future
`SCENE_SENSOR_PRESENT_IDENTITY_ONLY` only describes an exact identity found in
one typed Scene response; it does not prove raw contact delivery or collision.

## Required user approval

The user must explicitly approve exact ID
`S3.3.47_TYPED_SCENE_OBSERVER_REPLACEMENT_RUNTIME_RUN`, every hash and literal
above, trusted-context and lease ownership, one-create/one-request cardinality,
Candidate-A taxonomy, capacity one, no retry, and SIGINT-only shutdown. This
draft is not execution authority.

## Non-claims

A future Scene response cannot prove raw-contact endpoint delivery, collision
event, ContactLatch, collision policy, reward, termination, Gym/training, TF
authority, reset/settle receipt, or hardware readiness.

## Conclusion

**DRAFT — REPLACEMENT RUNTIME RUN PENDING USER APPROVAL**
