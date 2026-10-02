# S3 D3 ECS ContactSensor Diagnostic: Offline Implementation Approval Packet

`DEDICATED_WORLD_INTEGRATION_STATICALLY_IMPLEMENTED — RUNTIME NOT APPROVED`

## Scope

This is a compile-only feasibility and offline-implementation record for the read-only ECS ContactSensor diagnostic designed in [S3.3.74](S3_D3_ECS_ContactSensor_Component_Inspection_Design_Audit.md), [S3.3.75](S3_D3_ECS_ContactSensor_Diagnostic_System_Approval_Spec_DRAFT.md), [S3.3.76](S3_D3_ECS_ContactSensor_Diagnostic_Loading_And_Receipt_Decision_Packet_DRAFT.md), and [S3.3.77](S3_D3_ECS_ContactSensor_Diagnostic_Receipt_Wire_Delivery_And_Persistence_Contract_DRAFT.md). S3.3.79 created the approved isolated ament_cmake package and passed its offline build/tests. It authorizes no runtime, packet, guard, artifact, or execution authority. S3.3.80 adds only a separate rendered diagnostic-world template and no production-world change.

The sole future observation is `ROBOT_URDF_final → immediate base_link → immediate s3_d3_base_contact_sensor → components::ContactSensor → <contact><collision> literal → one immediate Collision child with exact Name`. It must not claim ContactSystemData, raw Contacts endpoint, collision event, ContactLatch, reward, termination, Nav2/training, or hardware readiness.

## Version-matched authority

| Authority | Exact identity / local path | Used contract |
| --- | --- | --- |
| Gazebo Sim | Official [`gz-sim8_8.11.0`](https://github.com/gazebosim/gz-sim/releases/tag/gz-sim8_8.11.0), commit [`1be3cc376fec778cc725b4eeea463245affa56d3`](https://github.com/gazebosim/gz-sim/commit/1be3cc376fec778cc725b4eeea463245affa56d3); local `/opt/ros/jazzy/opt/gz_sim_vendor/lib/cmake/gz-sim8/gz-sim8-config.cmake` says `8.11.0` | `gz-sim8::gz-sim8`, `ISystemConfigure`, `ISystemPostUpdate`, plugin registration. |
| Transport | Local `gz-transport13` `13.5.0`; `.../include/gz/transport13/gz/transport/Node.hh` | Typed advertise, publish, connection, subscription. |
| Messages | Local `gz-msgs10` `10.3.2`; target `gz-msgs10::gz-msgs10` | Shared dependency closure. |
| SDFormat | Local `sdformat14` `14.9.0`, schema `1.11`; `.../share/sdformat14/1.11/contact.sdf` | Future ContactSensor input; no SDF changed. |
| Protobuf | `/usr/bin/protoc`, `libprotoc 3.21.12`; `protobuf::libprotobuf` | Generated custom message linkage. |

## A. Compile-only ABI/API result

A unique `/tmp` `mktemp -d` directory held only a minimal `receipt.proto`, a System plugin skeleton, a collector skeleton, and CMake. It generated `s3_d3.ecs_contact.EcsContactSensorDiagnosticReceipt`, built the generated protobuf static library position-independent, and linked it into one temporary plugin shared library and one temporary collector shared library. Neither library was loaded or run.

```bash
source /opt/ros/jazzy/setup.bash
cmake -S /tmp/s3-3-78-probe.<unique> -B /tmp/s3-3-78-probe.<unique>/build -DCMAKE_BUILD_TYPE=Release
cmake --build /tmp/s3-3-78-probe.<unique>/build --parallel 2
```

The project used `find_package(... EXACT REQUIRED)` for `gz-sim8 8.11.0`, `gz-transport13 13.5.0`, and `gz-msgs10 10.3.2`, the installed imported targets plus `protobuf::libprotobuf`, and `-Wall -Wextra -Werror` on generated-protobuf, plugin, and collector targets. Final configure/link exit code was 0.

| Required fact | Exact local evidence | Result |
| --- | --- | --- |
| `Node::Advertise<CustomProto>()` | `Node.hh` lines 283–294; plugin probe compiled `Advertise<EcsContactSensorDiagnosticReceipt>`. | `CONFIRMED` |
| `Publisher::HasConnections()` | `Node.hh` lines 179–181; plugin probe type-checked it. | `CONFIRMED` |
| `Publisher::Publish(custom_message)` | `Node.hh` lines 132–137 accepts `const ProtoMsg &`; plugin probe type-checked it. | `CONFIRMED` |
| `Node::Subscribe<CustomProto>()` | `Node.hh` lines 362–376; collector probe compiled the explicit custom message type with the free callback carrying `MessageInfo`. | `CONFIRMED` |
| Generated protobuf links in both binaries | One generated PIC protobuf library linked into both temporary shared libraries. | `CONFIRMED` |
| System lifecycle types | `System.hh` lines 120–124 define mutable-ECM `Configure`; lines 176–179 define const-ECM `PostUpdate`; both overrides compiled. | `CONFIRMED` |
| Registration and CMake target | `Register.hh` lines 42–54 and 56–75 define `GZ_ADD_PLUGIN` / alias; plugin linked `gz-sim8::gz-sim8`. | `CONFIRMED` |

The probe also fixed two future build constraints rather than discovering version mismatch: explicit custom-type subscription must use the free-function overload because member callback templates are `<ClassT, MessageT>`; and a generated static protobuf library must be PIC before it links into a shared plugin (`POSITION_INDEPENDENT_CODE ON`).

## B. Sealed-state reconciliation

| State | Permitted work | Prohibited work | Meaning |
| --- | --- | --- | --- |
| `WAITING_FOR_TARGET` | Exact read-only const-ECM queries only in `PostUpdate`; simulation-time accounting. | Mutation, publication, fallback identity, second target. | No receipt. |
| `snapshot_sealed` | Retain exactly one immutable terminal payload; read only `Publisher::HasConnections()` until delivery deadline. | Any ECM query, replacement, terminal-status change, or new snapshot. | One in-memory terminal ECS result. |
| `delivery_sealed` | One `Publish()` happened, or delivery deadline elapsed without publishing; System becomes a no-op. | Second publish, retry, fresh snapshot, ECM access. | Attempted delivery or unavailable delivery, not persistence. |
| collector sealed | Raw-byte capture, strict validation, atomic durable commit or outer failure record. | Inventing ECS result, accepting duplicate/stale receipt, overwrite. | Only raw bytes, collector digest, parsed data, and matching run ID prove persistence. |

`Configure` only advertises the publisher; it performs no ECM query and no publish. `HasConnections()` only says subscribers connected; it is not a delivery receipt. Thus post-`snapshot_sealed` connection polling cannot alter the snapshot, and only the collector's raw bytes plus independent digest and atomic bundle can prove delivery/persistence.

## C. Proposed offline implementation contract

| Surface | Proposal / status | Future responsibility |
| --- | --- | --- |
| Package owner | `PROPOSED: s3_d3_ecs_contact_diagnostic`, diagnostic-only and outside URDF/Xacro, ROS/Nav2, ContactLatch, reward, hardware packages. | Own proto generation, System, collector, tests; explicit package-ownership approval required. |
| Proto | `PROPOSED: proto/ecs_contact_sensor_diagnostic_receipt.proto`; package `PROPOSED: s3_d3.ecs_contact`; message `PROPOSED: EcsContactSensorDiagnosticReceipt`; schema `PROPOSED: 1`. | Generate once for System and collector. |
| Library and registration | `PROPOSED: libS3D3EcsContactSensorDiagnosticSystem.so`; alias `PROPOSED: s3_d3::ecs_contact::ContactSensorDiagnosticSystem`. | PIC build; `GZ_ADD_PLUGIN` for `System`, `ISystemConfigure`, `ISystemPostUpdate`. |
| Dedicated-world declaration | Static-only template: `<plugin filename="S3D3EcsContactSensorDiagnosticSystem" name="s3_d3::ecs_contact::ContactSensorDiagnosticSystem">`; all child config fields are caller-rendered exactly once with no defaults. | Dedicated-world-only loading; no URDF/Xacro → ROS/Nav2 route change. |
| Transport topic | `PROPOSED: /s3_d3/diagnostic/ecs_contact_sensor_receipt`. | Gazebo Transport only; not ROS, raw Contacts, service/action, or command/control. |
| Collector and layout | Selected by S3.3.77: separate read-only collector; raw protobuf, external raw SHA-256, normalized protobuf, JSON projection, metadata, or outer failure record. | No self-referential payload hash, no bridge, no raw-contact subscriber, no control client. |

| Required literal | Owner / clock | Decision still required |
| --- | --- | --- |
| `SYSTEM_WAIT_TIMEOUT_SIM_TIME_NS` | System / simulation time | Duration, unit, pause/regression semantics. |
| `SYSTEM_DELIVERY_WAIT_TIMEOUT_STEADY_NS` | System / steady clock | Duration from snapshot seal to delivery seal. |
| `COLLECTOR_RECEIPT_WAIT_TIMEOUT_STEADY_NS` | Collector / steady clock | One-receipt deadline. |
| `COLLECTOR_PERSIST_TIMEOUT_STEADY_NS` | Collector / steady clock | Atomic persistence deadline. |

All package/proto/library/alias/loading/topic values are `PROPOSED`, not approved. A later packet/guard must hash-bind approved values plus proto source/generated code, System source/binary, collector source/binary, CMake/package manifests, dedicated-world declaration, world, native model, and persistence schema version.


## S3.3.80 static loading integration

The local SDFormat 1.11 authority [`plugin.sdf`](/opt/ros/jazzy/opt/sdformat_vendor/share/sdformat14/1.11/plugin.sdf) permits a plugin as a child of `world`, requires `filename`, and states that a non-absolute library filename is searched in configuration paths. The installed Gazebo Sim 8 `touch_plugin.sdf` example uses world-scope `filename` / `name` pairs for Physics and Contact; installed `ros_gz_sim/launch/gz_sim.launch.py` composes `GZ_SIM_SYSTEM_PLUGIN_PATH` and `GZ_SIM_RESOURCE_PATH` from inherited values, `LD_LIBRARY_PATH`, and package exports.

S3.3.80 therefore adds only a separate template named `world_demo`, with Physics, exactly one Contact System, and exactly one `S3D3EcsContactSensorDiagnosticSystem`; it contains no model or include. Its companion launch requires a caller-supplied rendered world path, adds the installed diagnostic package `lib` directory to the official system-plugin search variable, preserves inherited paths, and includes the official `gz_sim.launch.py`. It creates no robot, ROS node, bridge, TF, command, control, or runtime authority. `base_world_template_sha256` is the SHA-256 of this immutable template before rendering. Any rendered-world digest is external manifest metadata only.


## S3.3.81: native diagnostic-world System completeness

`SYSTEM_COMPLETENESS_STATICALLY_CONFIRMED — RUNTIME NOT APPROVED`

The dedicated world remains exactly three Systems: `gz::sim::systems::Physics`, exactly one `gz::sim::systems::Contact`, and `s3_d3::ecs_contact::ContactSensorDiagnosticSystem`. It intentionally does **not** load `gz::sim::systems::Sensors` or a render engine.

Version-matched evidence is direct. The installed Gazebo Sim 8 world [`contact_sensor.sdf`](/opt/ros/jazzy/opt/gz_sim_vendor/share/gz/gz-sim8/worlds/contact_sensor.sdf) declares a native `<sensor type='contact'>` under a world containing Physics and Contact but no Sensors System. Official [`Contact.cc` at `gz-sim8_8.11.0`](https://raw.githubusercontent.com/gazebosim/gz-sim/gz-sim8_8.11.0/src/systems/contact/Contact.cc) calls `EachNew<components::ContactSensor>` in `CreateSensors`, reads the stored `<contact><collision>` element, resolves immediate collision children, and creates `ContactSensorData` for the resolved collision. The local [`ContactSensor.hh`](/opt/ros/jazzy/opt/gz_sim_vendor/include/gz/sim8/gz/sim/components/ContactSensor.hh) defines `components::ContactSensor` as the complete `sdf::ElementPtr` for the sensor. Conversely, official [`Sensors.cc` at `gz-sim8_8.11.0`](https://raw.githubusercontent.com/gazebosim/gz-sim/gz-sim8_8.11.0/src/systems/sensors/Sensors.cc) owns a rendering-sensor manager and rendering components such as camera and GPU LiDAR; it is not the ContactSensor configuration producer.

Thus Physics + Contact + the read-only diagnostic System is the minimum System topology for the future native spawn to expose the ContactSensor component/configuration to the diagnostic query. This static conclusion does not prove that a spawn succeeds, that Contact system data is populated, that a contact endpoint is usable, or that any collision event occurs. The integration checker rejects missing/duplicate Contact, any Sensors System or `render_engine` configuration, and every System outside the three-item allowlist.

## S3.3.82 offline supervisor/collector integration

`OFFLINE_SUPERVISOR_COLLECTOR_INTEGRATION_IMPLEMENTED — RUNTIME NOT APPROVED`

The new dedicated supervisor is an injected, future-only orchestration boundary. Its immutable `EcsDiagnosticRunPlan` binds the run ID, source/install template and native-model hashes, plugin and collector source/binary hashes, installed renderer and collector executables, dedicated rendered-world launch, exact native create path/argv, identities, and all four timeout values. It does not accept defaults or a fallback route.

Its verified future ordering is: preflight → render the installed template with the C++ `RenderDiagnosticWorld` bridge → write a durable manifest carrying the base-template and external rendered-world digests → start one read-only collector → require collector readiness → start one dedicated-world launch → start one direct native create → receive the collector terminal outcome → supervisor-initiated SIGINT cleanup. The cleanup record deliberately says only that the supervisor initiated SIGINT; launcher-managed escalation, if observed later, is recorded separately and is not labelled end-to-end SIGINT-only.

The command-line `--execute` entrypoint remains an unconditional `NO_EXECUTION_AUTHORITY` rejection before any preflight, rendering, child construction, guard interaction, or runtime I/O. Offline tests use only injected fake collaborators and cover ordering, every pre-child failure boundary, collector-readiness blocking, exact no-shell/new-session commands, run-ID continuity, one invocation per future child, and cleanup records.

## Conclusion

`COLLECTOR_RUNTIME_CONTRACT_IMPLEMENTED_OFFLINE — RUNTIME NOT APPROVED`

The version-matched custom protobuf API/ABI probe passed and the approved isolated package now builds and passes offline tests. Dedicated-world/launch integration is now static-only complete. Remaining work is final hash review, a new runtime packet and capacity-one guard, then separate explicit user approval before any run.

No Gazebo, ROS graph, Transport runtime, plugin binary, collector binary, spawn, bridge, RequestRaw, command/control, hardware, guard, or runtime-artifact operation occurred. The temporary probe directory was deleted; no probe source, binary, or CMake file remains in this repository.

## S3.3.83 renderer-result provenance binding

`RENDERER_RESULT_RECEIPT_IMPLEMENTED_OFFLINE — RUNTIME NOT APPROVED`

The renderer now requires an absolute `--result` path in the same caller-owned run directory as the rendered SDF. On a successful filesystem-only render it commits `renderer_result.json` with schema `s3_d3_renderer_result/v1`, the exact run ID, canonical absolute template and rendered-world paths, immutable base-template SHA-256, and rendered-world SHA-256. The receipt is exclusive/no-overwrite and atomically committed after the rendered SDF; no renderer stdout or stderr is evidence.

The supervisor's injected boundary now accepts a render only after a strict receipt has the exact plan run ID, canonical plan paths, base-template SHA, and a rendered-world SHA that matches a fresh file hash. Missing, malformed, stale, path-drifted, or hash-drifted result evidence produces `INVALID_RENDER_RESULT_PROVENANCE` before manifest, collector, launch, or create. Renderer CLI parsing rejects unknown/duplicate/missing fields, relative or traversal paths, invalid SHA/run ID, and signed, zero, overflow, or trailing-garbage timeouts.
