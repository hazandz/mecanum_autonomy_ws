# S3 D3 Native Contact Endpoint One-Shot Execution-Readiness Audit

Status: `OFFLINE_EXECUTION_CONTRACT_REPAIRED — RUNTIME NOT APPROVED`

## S3.3.71 reconciliation scope

S3.3.71 repaired only the offline execution contract for the already selected native route. It created no approval packet, guard record, authorization record, durable run directory, or persistent helper binary. It did not start Gazebo, ROS, `gz`, a launch, `create`, a helper runtime mode, `RequestRaw`, a bridge, command/control path, service/action call, or hardware.

Historical S3.3.54 remains read-only and byte-identical (SHA-256 `2e115ce24253129caabcb9daf1e33b62cfc9964fe94fa38d46f4dfa2363a6e50`). It is not a native-route authority.

## Dependency graph now represented by the supervisor and guard

```text
native_sdf_contact_diagnostic.launch.py
  -> locked Gazebo world tugbot_depot.sdf / world_demo
  -> one direct /opt/ros/jazzy/lib/ros_gz_sim/create
       -world world_demo -file <installed model.sdf>
       -name ROBOT_URDF_final -allow_renaming false -x 0 -y 0 -z 0.1 -Y 0
  -> one typed_scene_observer --runtime-once
  -> durable evidence directory keyed by one shared run_id
```

This is an offline contract, not evidence that any edge has executed.

## Locked native assets

| Input | Source / installed path | SHA-256 | Status |
| --- | --- | --- | --- |
| Supervisor | [`run_typed_scene_observer.py`](../artifacts/simulation/contact_producer_evidence/tools/run_typed_scene_observer.py) | `8d5a2954481bc85a0fa5085a8f9a4680c8271cce0542ce5d676de895250244ec` | `CONFIRMED` |
| Imported guard helper | [`typed_scene_final_run_guard.py`](../artifacts/simulation/contact_producer_evidence/tools/typed_scene_final_run_guard.py) | `0159b4cce97525e7a3f13b7e57f0fe905b14b8e1e3e0f14616b201871f40ebd5` | `CONFIRMED` |
| Typed Scene helper source | [`typed_scene_observer.cpp`](../artifacts/simulation/contact_producer_evidence/tools/typed_scene_observer.cpp) | `e0785bf6802348138576bae27e0027b7560e9f2eaaa4b71227e0b7de33c23589` | `CONFIRMED` |
| Native launch, source and installed | [`native_sdf_contact_diagnostic.launch.py`](../ros2_ws/src/ROBOT_URDF_final_description/launch/native_sdf_contact_diagnostic.launch.py) | `1719f29d11f235b7a7c24e5bb0dfd0fb269559d3930497a446c0f8edfac3657f` | `CONFIRMED` |
| Native model, source and installed | [`model.sdf`](../ros2_ws/src/ROBOT_URDF_final_description/models/ROBOT_URDF_final/model.sdf) | `809af5a0f0305eda00569c5c9dbbc9161e23b4ad95c6e19319a934c1d7e5a18e` | `CONFIRMED` |
| Locked world | [`tugbot_depot.sdf`](../ros2_ws/src/ROBOT_URDF_final_description/launch/tugbot_depot.sdf) | `a4b6253340baa866d89640d62a94d04fbea51425e9af1deca591422a0a36d91d` | `CONFIRMED` |
| Direct create executable | `/opt/ros/jazzy/lib/ros_gz_sim/create` | `549a91ca31d5b943457b1fa6ae25cc726867b6afa69d789e1afbd2af139fe02d` | `CONFIRMED` |

The installed native model is exactly under `ros2_ws/install/ROBOT_URDF_final_description/share/ROBOT_URDF_final_description/models/ROBOT_URDF_final/model.sdf`. The resource root remains the installed package-share parent.

## Dedicated launch and direct-create contract

The native launch static checker passed against source and installed launch, including 10 negative fixtures. Its graph is exactly:

```text
SetEnvironmentVariable(GZ_SIM_RESOURCE_PATH)
  -> IncludeLaunchDescription(ros_gz_sim/gz_sim.launch.py, tugbot_depot.sdf)
```

It has no `Node`, URDF description provider, `ros_gz_sim create`, bridge, static TF, `/cmd_vel`, teleop, Nav2, PPO/Gym, collector, service/action control client, retry, or respawn. The repaired supervisor and guard now reject the legacy launch name, `-topic`, and `/robot_description` before a runtime callback is possible.

The sole future create argv is:

```text
-world world_demo
-file <installed ROBOT_URDF_final/model.sdf>
-name ROBOT_URDF_final
-allow_renaming false
-x 0 -y 0 -z 0.1 -Y 0
```

The fixed timing contract remains create timeout `90000 ms`, post-create delay `2000 ms`, create and measurement cleanup grace `5000 ms`, helper preflight `90000 ms`, helper request timeout `5000 ms`, and polling `10 ms`. The cleanup wording is `supervisor-initiated SIGINT-only; launcher-managed escalation may occur`; it is not an end-to-end SIGINT-only claim.

## Repaired blockers

| Former blocker | S3.3.71 repair evidence | Status |
| --- | --- | --- |
| Supervisor launched legacy world route | `DEDICATED_LAUNCH_ARGUMENTS` now selects `native_sdf_contact_diagnostic.launch.py`; mock launch argv test passed | `CONFIRMED` |
| Supervisor used URDF topic-spawn | `native_create_argv()` binds installed native `model.sdf` and the exact `-world/-file` argv; one-create mock test passed | `CONFIRMED` |
| Guard locked legacy source/install launch and create literal | Native source launch, installed launch, source model, installed model, and exact argv are part of `build_trusted_context`; two synthetic approval-spec tests passed | `CONFIRMED` |
| Prepared helper binary had no immutable receipt | `prepare()` records `PreparedHelper.binary_sha256`; `helper_once()` requires same path, regular file, and unchanged SHA before callback. Missing, mismatch, and mutation tests passed before `subprocess.run` | `CONFIRMED` |
| Fallback evidence was non-canonical | Fallback summary writes `s3_d3_typed_scene_summary/v4`; metadata writes `s3_d3_typed_scene_metadata/v3`, service, outer status, shared `run_id`, and `raw_response_sha256: null` with no synthetic raw protobuf | `CONFIRMED` |

`PreparedHelper` is held in the temporary compile ownership state. Production construction derives create argv from its workspace; the narrow injected argv seam accepts only the module’s locked native tuple and is used solely by temporary-workspace offline tests.

## Durable evidence contract

The statically enforced orchestration remains:

```text
run_id -> prepare temporary helper -> begin durable run/manifest
-> trusted context -> acquire -> launch -> one create -> one helper
-> persist -> supervisor-initiated SIGINT cleanup -> consume
```

A shared `run_id` is required in the manifest, create record, helper summary/metadata, helper-process record, shutdown record, and future guard consumption. Service-unavailable or incomplete-request outcomes may legitimately have no `scene_response.pb` / SHA pair and must record `raw_response_sha256: null`; a response requires both the raw protobuf and matching SHA. Existing no-overwrite and symlink rejection contracts remain in force.

The helper status allowlist remains:

- `SCENE_SERVICE_UNAVAILABLE`
- `SCENE_REQUEST_INCOMPLETE`
- `SCENE_RESPONSE_UNDECODABLE`
- `SCENE_MODEL_NOT_OBSERVED_AFTER_DELAY`
- `SCENE_LINK_NOT_OBSERVED_AFTER_DELAY`
- `SCENE_SENSOR_NOT_OBSERVED_AFTER_DELAY`
- `SCENE_SENSOR_PRESENT_IDENTITY_ONLY`

`SCENE_SENSOR_PRESENT` is intentionally unreachable.

## Offline validation evidence

| Check | Evidence | Status |
| --- | --- | --- |
| Supervisor and guard tests | 43 tests passed, including native binding, legacy rejection, two synthetic approval IDs, capacity-one fixture behavior, binary receipt integrity, fallback schemas, shared run ID, and S3.3.54 read-only hash check | `CONFIRMED` |
| C++ helper compile | Temporary `g++ -std=c++17 -Wall -Wextra -Werror` build passed with `gz-transport13`, `gz-msgs10`, and OpenSSL closure | `CONFIRMED` |
| Helper offline modes | `--offline-self-test` and `--offline-artifact-self-test` passed; runtime mode was not called | `CONFIRMED` |
| Native model checker | Installed model contract and negative fixtures passed | `CONFIRMED` |
| Native launch checker | Installed launch contract and 10 negative fixtures passed | `CONFIRMED` |
| Historical S3.3.54 | SHA remains `2e115ce24253129caabcb9daf1e33b62cfc9964fe94fa38d46f4dfa2363a6e50` | `CONFIRMED` |
| Live Gazebo model insertion, Scene service, hierarchy, ContactSensor, endpoint | Requires separately approved runtime execution | `UNKNOWN_RUNTIME_ONLY` |

## Gate matrix

| Gate | Evidence | Status |
| --- | --- | --- |
| Native source/install assets have matching content | SHA equality and static checkers | `CONFIRMED` |
| Dedicated route is world-only and control-free | AST checker and negative fixtures | `CONFIRMED` |
| Native create contract is represented by supervisor and guard | Exact mock argv and synthetic trusted-context tests | `CONFIRMED` |
| Legacy URDF/topic route is rejected | Production source scan and offline rejection tests | `CONFIRMED` |
| Prepared binary receipt is validated before helper callback | Missing/mismatch/mutation tests with zero callback | `CONFIRMED` |
| Fallback terminal evidence is schema v4/v3 and no-response-safe | Offline durable-record tests | `CONFIRMED` |
| Toolchain compiles helper offline | Temporary build and both offline helper modes | `CONFIRMED` |
| Actual Gazebo/Scene/hierarchy/contact endpoint behavior | Not observable without one approved runtime run | `UNKNOWN_RUNTIME_ONLY` |

Counts: `CONFIRMED=7`, `BLOCKED=0`, `DRIFT=0`, `UNKNOWN_RUNTIME_ONLY=1`.

## Runtime-only unknowns and non-claims

This repair does not establish Gazebo startup, live resource loading, native model insertion, Scene service advertisement, actual model/link/sensor/collision hierarchy, ContactSensor endpoint advertisement, raw contacts delivery, a collision event, ContactLatch behavior, reward/termination behavior, training readiness, or hardware readiness.

## Conclusion

`OFFLINE_EXECUTION_CONTRACT_REPAIRED — RUNTIME NOT APPROVED`

The only remaining prerequisite before a new packet and capacity-one guard is authorization to create those new artifacts bound to the final native supervisor and guard hashes. No execution authority exists in this increment.
