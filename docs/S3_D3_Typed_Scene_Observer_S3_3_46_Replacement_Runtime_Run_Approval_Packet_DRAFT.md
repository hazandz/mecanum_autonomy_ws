# S3 D3 — Typed Scene Observer S3.3.46 Replacement Runtime Run Approval Packet

**Status: DRAFT — REPLACEMENT RUNTIME RUN PENDING USER APPROVAL**

## Authority boundary

This is the only pending candidate for one future Typed Scene observer run.
S3.3.45 is superseded and was not acquired; S3.3.44 and all historical guards
remain untouched. This packet and its guard create no execution authority until
explicit user approval names the approval ID below.

## Approval ID and immutable run contract

| Item | Locked value |
| --- | --- |
| Approval ID | `S3.3.46_TYPED_SCENE_OBSERVER_REPLACEMENT_RUNTIME_RUN` |
| World / entity | `world_demo` / `ROBOT_URDF_final` |
| Scene request | `/world/world_demo/scene/info`: `gz::msgs::Empty → gz::msgs::Scene` |
| Exact hierarchy | `ROBOT_URDF_final → base_link → s3_d3_base_contact_sensor` |
| Collision literal | `s3_d3_base_contact_collision` |
| Ownership | `SUPERVISOR_OWNED_CREATE_V1` |
| Direct create | `/opt/ros/jazzy/lib/ros_gz_sim/create` with `-topic /robot_description -name ROBOT_URDF_final -allow_renaming false -x 0 -y 0 -z 0.1 -Y 0` |
| Timings | create `90000 ms`; post-create `2000 ms`; SIGINT grace `5000 ms`; helper preflight/request/poll `90000/5000/10 ms` |
| Candidate-A semantics | `SCENE_*_NOT_OBSERVED_AFTER_DELAY`, never `SCENE_*_ABSENT` |
| One-shot / shutdown | One create; one `RequestRaw`; no retry; capacity `1`; SIGINT-only |

## Trusted live context — mandatory source of truth

The future guard may receive only an explicit workspace root and its guard path.
`build_trusted_context(workspace_root)` itself resolves and hashes the packet,
supervisor, dedicated launch, typed helper, guard helper, world, and the exact
direct executable. Callers cannot supply hashes or literals.

Workspace-relative paths must stay beneath the explicit root, be regular files,
and contain no final or intermediate symlink. The direct executable must be the
exact absolute literal above, regular, and non-symlinked. Missing files,
traversal, symlink, non-regular file, hash drift, packet drift, or literal drift
fail closed before lock acquisition.

| Input | SHA-256 |
| --- | --- |
| Supervisor | `e2ac8919b4ebded391d13f77283b1948b33191828d9d0a80d6425f2936cb6919` |
| Dedicated launch | `b6acf767471527f37c4e2d7c67cc46b693298cb4bf7028afb96be8d00c4f255d` |
| Typed Scene helper | `f8a56927f523deb0dd0b59eed30cab5bd571773176e45d6447bf1c62247d014d` |
| Guard helper | `76ba43668af08b06e8048e01f81cec77e3d50c754f52eeb6c838e80f969f1d2f` |
| World SDF | `1c50f90d151a12559d426796c5d153c829b8777a5b4e8ef94c007a2023f6e271` |
| Direct create executable | `549a91ca31d5b943457b1fa6ae25cc726867b6afa69d789e1afbd2af139fe02d` |
| Packet | Bound by the initialized S3.3.46 guard after final packet bytes. |

## Lease ownership — mandatory

`acquire_trusted(guard_path, workspace_root)` builds trusted context, validates
the guard, creates an exclusive lock directory, and writes exclusive
`lease.json` metadata containing approval ID, canonical-context digest, and a
cryptographically random nonce. It returns immutable `ApprovalLease` with those
same bindings.

`consume_trusted(...)` rebuilds trusted context and requires exact lease
approval ID, lock path, context digest, nonce, and matching metadata. Missing or
tampered metadata, token mismatch, drift, lock collision, malformed record, or
atomic-write failure fail closed. A crash-left lock remains a blocker and is
never removed or bypassed automatically.

## Future operation — only after user approval

```text
dedicated bootstrap launch
→ one supervisor-owned direct create child
→ Candidate-A exit-zero operational convention + 2000 ms guard
→ one typed ServiceList preflight
→ exactly one Empty → Scene RequestRaw
→ SIGINT-only shutdown
```

No `/cmd_vel`, ROS/Gazebo bridge, parameter bridge, static TF, pose/reset/delete/
pause/step/world-control, second spawn, teleop, Nav2, PPO, Gymnasium, SB3,
raw-contact collection, UART, STM32, Pi, motor, firmware, or hardware is
permitted. Exit `0` and timing guards are operational only, not Scene/entity,
reset, or settled-state receipts.

## Required user approval

The user must approve exact ID `S3.3.46_TYPED_SCENE_OBSERVER_REPLACEMENT_RUNTIME_RUN`, all literals and hashes above,
the trusted-context/lease contract, capacity one, one create, one `RequestRaw`,
no retry, and SIGINT-only. This draft is not execution authority.

## Non-claims

A future Scene response cannot by itself prove raw-contact delivery, collision,
ContactLatch, collision policy, reward, termination, Gym/training, TF authority,
reset/settle receipt, or hardware readiness.

## Conclusion

**DRAFT — REPLACEMENT RUNTIME RUN PENDING USER APPROVAL**
