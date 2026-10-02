# S3 D3 Spawned Collision Identity Runtime Run Approval Packet

Status: `DRAFT — PENDING_USER_APPROVAL — NO EXECUTION AUTHORITY`

## Approval identity and purpose

- Approval ID: `S3.3.61_SPAWNED_COLLISION_IDENTITY_RUNTIME_RUN`
- Guard schema: `s3_d3_typed_scene_runtime_guard/v1`
- Packet path: `docs/S3_D3_Spawned_Collision_Identity_Runtime_Run_Approval_Packet_DRAFT.md`
- Guard path: `artifacts/simulation/contact_producer_evidence/approval_guards/S3.3.61_SPAWNED_COLLISION_IDENTITY_RUNTIME_RUN.json`
- Capacity: `1`

This packet proposes exactly one future runtime observation after the approved
initial spawn. Its sole evidence objective is the durable raw Scene response
needed to inspect this spawned hierarchy:

```text
ROBOT_URDF_final
→ base_link
→ s3_d3_base_contact_sensor
→ actual collision name(s) and sensor contact target
```

This draft does not authorize execution. The guard remains
`pending_user_approval` until a later explicit user approval activates it.

## Immutable runtime binding

The S3.3.60 data-driven guard must hash-bind this packet and the current:

- generic supervisor `run_typed_scene_observer.py`;
- runtime-imported generic guard helper `typed_scene_final_run_guard.py`;
- typed Scene helper `typed_scene_observer.cpp`, including durable-evidence
  schemas `s3_d3_typed_scene_summary/v4` and
  `s3_d3_typed_scene_metadata/v3`;
- source and installed dedicated `typed_scene_observer.launch.py`;
- world `tugbot_depot.sdf`;
- direct create executable `/opt/ros/jazzy/lib/ros_gz_sim/create`; and
- Gazebo/pkg-config vendor identity recorded by the generic trusted context.

The source and installed launch hashes must be equal. Any packet, source,
launch, world, direct-executable, package identity, literal, schema, or path
drift is fail-closed before runtime dependency construction, `Popen`, guard
acquisition, or a request.

## Locked literals

| Field | Locked value |
| --- | --- |
| World / entity | `world_demo` / `ROBOT_URDF_final` |
| Link / sensor | `base_link` / `s3_d3_base_contact_sensor` |
| Configured sensor collision target | `s3_d3_base_contact_collision` |
| Scene service | `/world/world_demo/scene/info` |
| Request / response types | `gz::msgs::Empty` → `gz::msgs::Scene` |
| Create argv | `-topic /robot_description -name ROBOT_URDF_final -allow_renaming false -x 0 -y 0 -z 0.1 -Y 0` |
| Create timeout / post-create delay / shutdown grace | `90000 ms` / `2000 ms` / `5000 ms` |
| Helper preflight / request timeout / polling | `90000 ms` / `5000 ms` / `10 ms` |
| Retry / capacity | Forbidden / `1` |
| Cleanup wording | `supervisor-initiated SIGINT-only; launcher-managed escalation may occur` |

## Permitted future one-shot sequence

Only after explicit approval and authorization of this exact guard, the future
run may perform this sequence once:

1. launch the dedicated bootstrap route;
2. create exactly one initial `ROBOT_URDF_final`;
3. make exactly one typed Scene `RequestRaw`;
4. persist durable evidence; and
5. shut down under the locked cleanup policy.

It must not create a second robot, retry the request/run, or mutate source or
world state after bootstrap.

## Prohibited future operations

The future run must not use a bridge, `/cmd_vel`, teleop, Nav2, PPO, Gym,
pose/reset/delete, second spawn, world control, pause/step, raw-contact bridge,
UART, motor, or hardware operation.

## Durable evidence and interpretation

The shared `run_id` must match the guard consumption, run directory, manifest,
Scene summary, request metadata, create/helper/shutdown records, and supervisor
metadata. `scene_summary.json`, `request_metadata.json`, process records, and
the shutdown record are mandatory for every terminal outcome. When response
bytes exist, `scene_response.pb` and its SHA-256 are mandatory and must be
retained for offline collision-name review. The output directory may not be a
symlink; `TemporaryDirectory` may only hold the compiled helper, never the sole
Scene evidence.

| Future evidence condition | Admissible interpretation |
| --- | --- |
| One exact collision identity and exact sensor target in raw Scene evidence | `SPAWNED_COLLISION_IDENTITY_OBSERVED`; identity only, not a collision event. |
| Sensor exists but configured collision is absent from the Scene hierarchy | `SPAWNED_COLLISION_IDENTITY_MISMATCH_CANDIDATE`; retain raw protobuf for offline review and do not edit Xacro automatically. |
| Service unavailable, incomplete request, or undecodable response | No conclusion about collision or ContactSensor health. |

No outcome establishes a contact event, ContactLatch, collision termination,
reward, Gym/training, or hardware readiness.

## Preconditions and decision

Offline preflight must show a pending capacity-one guard with null run fields,
valid generic spec/context/packet/guard binding, matching source/install launch
hashes, passing temporary C++ compile and helper offline tests, and unchanged
consumed S3.3.54 historical guard SHA-256
`2e115ce24253129caabcb9daf1e33b62cfc9964fe94fa38d46f4dfa2363a6e50`.

```text
PENDING_USER_APPROVAL_FOR_ONE_SPAWNED_COLLISION_IDENTITY_RUNTIME_RUN
```
