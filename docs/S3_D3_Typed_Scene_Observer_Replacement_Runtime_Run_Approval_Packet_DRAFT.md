# S3 D3 — Typed Scene Observer Replacement Runtime Run Approval Packet

**Status: DRAFT — REPLACEMENT RUNTIME RUN PENDING USER APPROVAL**

## Purpose and authority

This is the sole proposed authority for one future replacement typed Scene
observer runtime run. It supersedes neither consumed historical records nor the
historical [Typed Scene Observer Run Approval Packet](S3_D3_Typed_Scene_Observer_Run_Approval_Packet_DRAFT.md); that older packet is retained as design/history only.

This packet grants no current execution authority. The new capacity-one guard is
initialized only as `authorized_not_consumed`; it must not be acquired or
consumed unless the user separately approves this exact packet with its bound
hashes and literals.

## Approval identity and immutable content

| Item | Locked value |
| --- | --- |
| Approval ID | `S3.3.44_TYPED_SCENE_OBSERVER_REPLACEMENT_RUNTIME_RUN` |
| World | `world_demo` |
| Entity | `ROBOT_URDF_final` |
| Scene service | `/world/world_demo/scene/info` |
| Typed request / response | `gz::msgs::Empty → gz::msgs::Scene` |
| Identity chain | `ROBOT_URDF_final → base_link → s3_d3_base_contact_sensor` |
| Collision literal | `s3_d3_base_contact_collision` |
| Ownership mode | `SUPERVISOR_OWNED_CREATE_V1` |
| Direct create executable | `/opt/ros/jazzy/lib/ros_gz_sim/create` |
| Create argv | `-topic /robot_description -name ROBOT_URDF_final -allow_renaming false -x 0 -y 0 -z 0.1 -Y 0` |
| Create timeout | `create_timeout_ms=90000` |
| Post-create guard | `post_create_delay_ms=2000` — operational Candidate-A guard only |
| Create shutdown grace | `create_shutdown_grace_ms=5000` |
| Helper preflight / request timeout / poll | `90000 ms` / `5000 ms` / `10 ms` |
| Candidate-A negative taxonomy | `SCENE_*_NOT_OBSERVED_AFTER_DELAY` only; never `SCENE_*_ABSENT` |
| Cardinality | One create; one `RequestRaw`; no retry; capacity `1`; SIGINT-only |

## Hash-locked inputs

| Input | Path | SHA-256 |
| --- | --- | --- |
| Supervisor adapter | `artifacts/simulation/contact_producer_evidence/tools/run_typed_scene_observer.py` | `e2ac8919b4ebded391d13f77283b1948b33191828d9d0a80d6425f2936cb6919` |
| Dedicated bootstrap launch | `ros2_ws/src/ROBOT_URDF_final_description/launch/typed_scene_observer.launch.py` | `b6acf767471527f37c4e2d7c67cc46b693298cb4bf7028afb96be8d00c4f255d` |
| Typed Scene helper source | `artifacts/simulation/contact_producer_evidence/tools/typed_scene_observer.cpp` | `f8a56927f523deb0dd0b59eed30cab5bd571773176e45d6447bf1c62247d014d` |
| World SDF revision | `ros2_ws/src/ROBOT_URDF_final_description/launch/tugbot_depot.sdf` | `1c50f90d151a12559d426796c5d153c829b8777a5b4e8ef94c007a2023f6e271` |
| Direct create executable | `/opt/ros/jazzy/lib/ros_gz_sim/create` | `549a91ca31d5b943457b1fa6ae25cc726867b6afa69d789e1afbd2af139fe02d` |

Any packet, source, world, executable, hash, literal, ownership, timing, or
capacity mismatch is fail-closed before launch. The future supervisor must
recompute the create executable hash immediately before child spawn as already
designed; its initial guard check does not replace that runtime integrity gate.

## Future one-shot operation — only if separately approved

```text
dedicated bootstrap launch
→ one supervisor-owned direct create child
→ exit-zero Candidate-A operational convention + 2000 ms guard
→ one typed Scene service discovery/preflight
→ exactly one Empty → Scene RequestRaw
→ SIGINT-only shutdown of measurement-created process groups
```

The direct child uses only the allowlisted executable and exact argv above. A
create timeout sends only SIGINT to the supervisor-owned child process group and
waits exactly 5000 ms. A clean exit retains
`SCENE_CREATE_OUTCOME_UNCONFIRMED` / `SCENE_BOOTSTRAP_UNCONFIRMED`; a still-live
child is `SHUTDOWN_INCOMPLETE`. Neither branch permits helper execution,
`RequestRaw`, a retry, a second create, or another run.

## Explicit prohibitions

This proposal does not permit `/cmd_vel`, any ROS/Gazebo bridge, parameter
bridge, static TF, pose/reset/delete/pause/step/world-control, a second spawn,
teleop, Nav2, PPO, Gymnasium, SB3, raw-contact collector, `gz model` parsing,
UART, STM32, Pi, motor, firmware, or hardware activity.

It does not alter Candidate-A semantics: exit code `0` and the 2000 ms delay
are not an entity/Scene receipt, reset receipt, settled-state proof, or atomic
insertion proof. `SCENE_SENSOR_PRESENT_IDENTITY_ONLY` remains the maximum
positive Scene classification under the generated-protobuf limitation.

## Guard requirements

The [S3.3.44 approval-bound guard](../artifacts/simulation/contact_producer_evidence/approval_guards/S3.3.44_TYPED_SCENE_OBSERVER_REPLACEMENT_RUNTIME_RUN.json) binds this packet's SHA-256 after this packet was finalized, every table literal, all five content hashes, capacity one, and its own approval ID. It starts `authorized_not_consumed` and must atomically acquire through a lock only after direct user approval. Any future terminal outcome must atomically consume this exact approval ID; no consumed historical guard may be reused.

## Required user approval

Before any runtime operation, the user must explicitly approve all locked
literals, all listed SHA-256 values, the one-shot boundary, Candidate-A taxonomy,
capacity one, no retry, and SIGINT-only shutdown. Approval must name
`S3.3.44_TYPED_SCENE_OBSERVER_REPLACEMENT_RUNTIME_RUN`. This draft itself is not executable.

## Non-claims

Even a future successful Scene response would not prove raw-contact endpoint
delivery, collision event, ContactLatch, collision policy, reward, termination,
Gym/training, TF authority, reset/settle receipt, or hardware readiness.

## Conclusion

**DRAFT — REPLACEMENT RUNTIME RUN PENDING USER APPROVAL**
