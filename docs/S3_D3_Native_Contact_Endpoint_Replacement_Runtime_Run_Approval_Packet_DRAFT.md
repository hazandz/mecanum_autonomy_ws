# S3 D3 Native Contact Endpoint Replacement Runtime Run Approval Packet

Status: `DRAFT — PENDING_USER_APPROVAL`

## Authority identity and scope

Approval ID: `S3.3.72_NATIVE_CONTACT_ENDPOINT_REPLACEMENT_RUNTIME_RUN`

This packet proposes exactly one future native-SDF, passive Scene observation. It is not execution authority. Only an explicit user approval of this packet may allow a separately guarded one-shot run.

The sole future sequence is:

```text
native_sdf_contact_diagnostic.launch.py
-> world_demo
-> one supervisor-owned direct create of ROBOT_URDF_final from installed model.sdf
-> one typed Scene RequestRaw(Empty -> Scene)
-> durable evidence persistence
-> supervisor-initiated SIGINT-only cleanup
```

The initial direct create is the only permitted bootstrap mutation. It uses Candidate A: a create exit code of zero followed by a 2000 ms delay is an operational convention permitting one request. It is not proof of entity existence, reset completion, settle state, or atomic insertion.

## Locked filesystem inputs

| Input | Workspace-relative path or system path | SHA-256 |
| --- | --- | --- |
| Supervisor | `artifacts/simulation/contact_producer_evidence/tools/run_typed_scene_observer.py` | `8d5a2954481bc85a0fa5085a8f9a4680c8271cce0542ce5d676de895250244ec` |
| Generic guard module | `artifacts/simulation/contact_producer_evidence/tools/typed_scene_final_run_guard.py` | `0159b4cce97525e7a3f13b7e57f0fe905b14b8e1e3e0f14616b201871f40ebd5` |
| Typed Scene helper source | `artifacts/simulation/contact_producer_evidence/tools/typed_scene_observer.cpp` | `e0785bf6802348138576bae27e0027b7560e9f2eaaa4b71227e0b7de33c23589` |
| Source native launch | `ros2_ws/src/ROBOT_URDF_final_description/launch/native_sdf_contact_diagnostic.launch.py` | `1719f29d11f235b7a7c24e5bb0dfd0fb269559d3930497a446c0f8edfac3657f` |
| Installed native launch | `ros2_ws/install/ROBOT_URDF_final_description/share/ROBOT_URDF_final_description/launch/native_sdf_contact_diagnostic.launch.py` | `1719f29d11f235b7a7c24e5bb0dfd0fb269559d3930497a446c0f8edfac3657f` |
| Source native model | `ros2_ws/src/ROBOT_URDF_final_description/models/ROBOT_URDF_final/model.sdf` | `809af5a0f0305eda00569c5c9dbbc9161e23b4ad95c6e19319a934c1d7e5a18e` |
| Installed native model | `ros2_ws/install/ROBOT_URDF_final_description/share/ROBOT_URDF_final_description/models/ROBOT_URDF_final/model.sdf` | `809af5a0f0305eda00569c5c9dbbc9161e23b4ad95c6e19319a934c1d7e5a18e` |
| Locked world | `ros2_ws/src/ROBOT_URDF_final_description/launch/tugbot_depot.sdf` | `a4b6253340baa866d89640d62a94d04fbea51425e9af1deca591422a0a36d91d` |
| Direct create executable | `/opt/ros/jazzy/lib/ros_gz_sim/create` | `549a91ca31d5b943457b1fa6ae25cc726867b6afa69d789e1afbd2af139fe02d` |
| `/usr/bin/pkg-config` canonical target | `/usr/bin/pkgconf` | `7e8152db1b0c7e49d47b4b82a70dc9997b557951c5d4d938b0e7f208ce9eb10b` |
| `/usr/bin/g++` canonical target | `/usr/bin/x86_64-linux-gnu-g++-13` | `1353e9bdd29a7295c7226bf6c63abccce056d8cac31f112e5cdbecc3f28c2769` |

The generic guard must independently re-hash every workspace asset and the direct create executable, reject symlinks or path escape, and bind its own loaded module identity. The source and installed native launch and model must continue to match byte-for-byte.

## Locked literals and toolchain closure

| Field | Exact locked value |
| --- | --- |
| World / entity / link | `world_demo` / `ROBOT_URDF_final` / `base_link` |
| Sensor / configured collision target | `s3_d3_base_contact_sensor` / `s3_d3_base_contact_collision` |
| Scene service and types | `/world/world_demo/scene/info`; `gz::msgs::Empty -> gz::msgs::Scene` |
| Create argv | `-world world_demo -file /home/hazan/mecanum_autonomy_ws/ros2_ws/install/ROBOT_URDF_final_description/share/ROBOT_URDF_final_description/models/ROBOT_URDF_final/model.sdf -name ROBOT_URDF_final -allow_renaming false -x 0 -y 0 -z 0.1 -Y 0` |
| Create ownership / timings | `SUPERVISOR_OWNED_CREATE_V1`; `90000/2000/5000 ms` (timeout/delay/grace) |
| Helper timings | `90000/5000/10 ms` (preflight/request/polling) |
| Capacity / request / retry | `1`; one `RequestRaw`; retry forbidden |
| Cleanup policy | `supervisor-initiated SIGINT-only; launcher-managed escalation may occur` |
| pkg-config closure | `gz-transport13=13.5.0`, `gz-msgs10=10.3.2`; vendor directories locked by the generic guard |

`/usr/bin/pkg-config` is a system symlink to the stated canonical target; the guard’s fail-closed regular/non-symlink policy applies to its locked vendor directories and `.pc` files, not to this invocation alias. The helper compile environment is the guard-locked `PKG_CONFIG_PATH` closure.

## Durable evidence contract

One opaque `run_id` must be generated once and used in the guard consumption, durable run directory, manifest, create-process record, helper-process record, summary, request metadata, and shutdown record. The output directory must not be a symlink. Temporary compilation storage is not permitted to be the only Scene evidence location.

Every terminal outcome must atomically retain:

- `run_manifest.json`
- `scene_summary.json` using `s3_d3_typed_scene_summary/v4`
- `request_metadata.json` using `s3_d3_typed_scene_metadata/v3`
- create-process, helper-process, and shutdown-outcome records

When response bytes exist, `scene_response.pb` and its matching SHA-256 receipt are both mandatory. For service unavailable or request-incomplete outcomes, both files may be absent and `raw_response_sha256` must be `null`; no empty raw artifact may be fabricated.

## Permitted terminal diagnostic statuses

- `SCENE_SERVICE_UNAVAILABLE`
- `SCENE_REQUEST_INCOMPLETE`
- `SCENE_RESPONSE_UNDECODABLE`
- `SCENE_MODEL_NOT_OBSERVED_AFTER_DELAY`
- `SCENE_LINK_NOT_OBSERVED_AFTER_DELAY`
- `SCENE_SENSOR_NOT_OBSERVED_AFTER_DELAY`
- `SCENE_SENSOR_PRESENT_IDENTITY_ONLY`

The highest positive result is `SCENE_SENSOR_PRESENT_IDENTITY_ONLY`. Negative Candidate-A outcomes use `NOT_OBSERVED_AFTER_DELAY`, never `ABSENT`. `SCENE_SENSOR_PRESENT` remains unreachable.

## Prohibitions and non-claims

The future run must not use `typed_scene_observer.launch.py`, `-topic`, `/robot_description`, URDF topic-spawn, `robot_state_publisher`, a bridge, `/cmd_vel`, static TF, raw-contact bridge, teleop, Nav2, PPO/Gym, a second spawn, pose/reset/delete/pause/step/world-control, shell execution, retry, SIGTERM, SIGKILL, or hardware operation.

No outcome proves a contact event, collision policy, ContactLatch behavior, reward, termination, training/Nav2 readiness, or hardware readiness. A sensor and exact collision identity observed in raw Scene protobuf is hierarchy evidence only.

## Guard requirement

The future record must use `s3_d3_typed_scene_runtime_guard/v1`, capacity one, state `pending_user_approval`, and null `run_id`, `final_status`, and `consumed_at_utc`. It must bind this packet SHA, the entire trusted context, exact literals above, and the generic approval specification. It must not be activated, acquired, or consumed until explicit user approval.

`PENDING_USER_APPROVAL — NO EXECUTION AUTHORITY`
