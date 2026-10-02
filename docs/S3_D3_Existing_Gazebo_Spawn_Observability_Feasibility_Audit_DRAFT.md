# S3 D3 — Existing Gazebo Machine-Readable Spawn Observability Feasibility Audit

**Status: DRAFT — STATIC OBSERVABILITY FEASIBILITY AUDIT — NO RUNTIME APPROVAL**

## Scope and question

This is a local, version-matched static audit only. It identifies whether the
currently configured Gazebo stack exposes a typed, read-only interface that a
future approved diagnostic can use to inspect spawned model, link, collision,
and sensor identity without treating `gz model` text as a machine-readable
contract. It does not launch Gazebo, create an observer, bridge a topic, or
change any source or runtime configuration.

The narrow question is: after a future spawn, can an approved observer obtain
typed data proving the exact hierarchy
`ROBOT_URDF_final → base_link → s3_d3_base_contact_sensor`? This audit does
not ask whether a contact event occurs.

## Static baseline and version boundary

| Item | Static evidence | Status | Meaning |
| --- | --- | --- | --- |
| Gazebo world identity | [`tugbot_depot.sdf`](../ros2_ws/src/ROBOT_URDF_final_description/launch/tugbot_depot.sdf) declares `<world name='world_demo'>`. | CONFIRMED | The service-name placeholder `<world_name>` resolves statically to `world_demo`; it is not a ROS frame assertion. |
| Gazebo Sim generation | `/opt/ros/jazzy/opt/gz_sim_vendor/lib/pkgconfig/gz-sim8.pc` reports `gz-sim8` version `8.11.0`. | CONFIRMED | This audit applies to the locally installed Harmonic / Gazebo Sim 8 stack. |
| Spawn path | [`gazebo.launch.py`](../ros2_ws/src/ROBOT_URDF_final_description/launch/gazebo.launch.py) renders Xacro, starts `ros_gz_sim create` from `/robot_description`, and supplies entity name `ROBOT_URDF_final`. | CONFIRMED | It establishes the intended spawn inputs, not a post-spawn entity observation. |
| URDF-to-SDF ContactSensor retention | [S3 URDF-to-SDF conversion audit](S3_D3_URDF_To_SDF_ContactSensor_Conversion_Static_Audit_DRAFT.md) concluded `C. CONVERSION_PATH_STATICALLY_UNRESOLVED`. | CONFIRMED LIMITATION | A typed post-spawn observation is still needed; Xacro literals do not prove the spawned SDF retained the sensor. |

## Systems actually declared by the current world and launch

The following table inventories only systems explicitly declared by the
currently launched world or launch file. An installed plugin is not treated as
loaded merely because it exists under `/opt/ros`.

| System or launch component | Declared source | Static read-only output relevant to spawned identity | Assessment |
| --- | --- | --- | --- |
| `gz::sim::systems::Physics` | [`tugbot_depot.sdf`](../ros2_ws/src/ROBOT_URDF_final_description/launch/tugbot_depot.sdf) | No local public identity-inspection endpoint was established by this audit. | Not an observer candidate. |
| `gz::sim::systems::Contact` | Same world file | May support contact processing, but no general typed model/link/sensor inventory interface was established from its declaration. | Not an observer candidate. Its presence does not prove a ContactSensor entity or endpoint. |
| `gz::sim::systems::UserCommands` | Same world file | Command services are mutation-capable. | Explicitly excluded: not read-only. |
| `gz::sim::systems::SceneBroadcaster` | Same world file; installed library `/opt/ros/jazzy/opt/gz_sim_vendor/lib/libgz-sim8-scene-broadcaster-system.so.8.11.0` | Local Gazebo Sim Server API documents a typed current-scene service. | Candidate evaluated below. |
| `gz::sim::systems::Imu` | Same world file | IMU data is not a model/link/sensor hierarchy interface. | Not an observer candidate. |
| `gz::sim::systems::Sensors` | Same world file | Per-sensor output would presuppose that a sensor was retained and configured; no general sensor-entity inventory is established by its declaration. | Not an observer candidate. |
| `ros_gz_sim create` | [`gazebo.launch.py`](../ros2_ws/src/ROBOT_URDF_final_description/launch/gazebo.launch.py) | Spawn entry point, not an observation interface. | Not an observer candidate. |
| Main `ros_gz_bridge` | Same launch file | Existing mappings cover command, odometry, scan, and clock; no Scene service or raw contact bridge is declared. | Not an observer candidate; no bridge is proposed by this audit. |

## Candidate interface assessment

| Candidate interface | Đang được world/launch load? | Message/service type | Machine-readable? | Read-only? | Có thể chứng minh model/link/sensor không? | Evidence cục bộ |
| --- | --- | --- | --- | --- | --- | --- |
| Gazebo Server / SceneBroadcaster scene information service, `/world/world_demo/scene/info` | Yes: `SceneBroadcaster` is explicitly declared at world scope. | Local Server API: `(none) → gz::msgs::Scene`; installed SceneBroadcaster library symbols instantiate `gz::msgs::Empty → gz::msgs::Scene`. | Yes. `gz::msgs::Scene` is a protobuf message, not CLI text. | Yes by documented semantics: “Returns the current scene information.” | Yes, conditionally on a successful typed response: `Scene.model[] → Model.link[] → Link.sensor[]` carries exact string and numeric identities. | `/opt/ros/jazzy/opt/gz_sim_vendor/include/gz/sim8/gz/sim/Server.hh`; installed SceneBroadcaster library; `scene.proto`, `model.proto`, `link.proto`, and `sensor.proto` under `/opt/ros/jazzy/opt/gz_msgs_vendor/share/gz/gz-msgs10/protos/gz/msgs/`. |
| SceneBroadcaster state / asynchronous-state endpoints | SceneBroadcaster is loaded, but this audit found only binary symbol fragments such as `/state` and `state_async`, not a public, version-matched contract establishing endpoint derivation, request/response types, and ContactSensor component decoding. | Insufficiently established. | Potentially structured internally, but no supported identity payload contract was established. | Not established by this audit. | No: cannot safely assert ContactSensor presence without a documented component schema and typed decode path. | SceneBroadcaster binary strings only. |
| `gz model --list`, `gz model -m … -l … -s …` | CLI is installed, but it is not a world-loaded typed observer. | Human-oriented text output. | No. The consumed diagnostic required text parsers and exposed grammar ambiguity. | Intended as query-only, but output is not a machine-readable contract. | No, not to the required fail-closed standard. | [spawn diagnostic design](S3_D3_Spawned_ContactSensor_Diagnostic_Run_Design_DRAFT.md) and its later parser-hardening history. |
| `gz topic -l` / `gz topic -i` | CLI availability is not a publisher or system-load proof. | Human-oriented endpoint listing/type text. | No as an identity observer. | Intended as query-only. | No. At most it discovers advertised endpoints and a type; it cannot prove a spawned ContactSensor component. | [contact endpoint root-cause audit](S3_D3_Contact_Endpoint_Root_Cause_Audit_DRAFT.md). |
| `/s3_d3/contact/raw` `gz::msgs::Contacts` endpoint | Not observed in the consumed S3.3.17 evidence run. | `gz::msgs::Contacts` only if advertised. | Payload protobuf would be typed, but endpoint absence means there is no existing observable interface at this revision/run. | Subscriber observation would be read-only. | No. A raw contact payload is event data, not a model/link/sensor inventory, and no endpoint was observed. | [contact endpoint root-cause audit](S3_D3_Contact_Endpoint_Root_Cause_Audit_DRAFT.md). |
| In-process Gazebo ECS (`EntityComponentManager`, `Model`, `Link`, `Sensor`, and `ContactSensor` components) | No diagnostic system using it is declared by world or launch. | C++ component API, not an existing external observer endpoint. | Yes in a future custom system. | Could be read-only if deliberately implemented. | Potentially yes, but only after new implementation and separate approval. | Gazebo Sim 8 installed headers; no currently loaded observer system in the source inventory. |

## Why the scene service meets the static feasibility threshold

The Scene service is the only existing candidate for which the local
version-matched evidence establishes all required static elements:

1. **Non-ambiguous discovery/name derivation.** `Server.hh` documents
   `/world/<world_name>/scene/info`; the current SDF declares exactly
   `world_demo`, yielding `/world/world_demo/scene/info` without guessing a
   scoped sensor topic.
2. **Typed service and payload.** The installed API documents the response as
   `gz::msgs::Scene`. The installed SceneBroadcaster binary contains the
   `gz::msgs::Empty` / `gz::msgs::Scene` service instantiation. A future
   observer must use a typed Gazebo Transport client and protobuf decode, not
   parse the textual output of `gz service`.
3. **Exact identity fields.** Local protobuf definitions provide `Model.name`
   and `Model.id`; `Link.name`, `Link.id`, `Link.collision[]`, and
   `Link.sensor[]`; and `Sensor.name`, `Sensor.id`, `Sensor.parent`,
   `Sensor.parent_id`, `Sensor.type`, `Sensor.contact`, and `Sensor.topic`.
   `ContactSensor.collision_name` and `Collision.name` are also explicit
   fields. A future observer can require exact equality for
   `ROBOT_URDF_final`, `base_link`, and
   `s3_d3_base_contact_sensor`, with no substring, prefix, suffix, or
   inferred scoped-name match.
4. **Non-mutating semantics.** The local Server API describes the service as
   returning current scene information. It is distinct from the loaded
   `UserCommands` system and from all world-control operations.

Static feasibility is not runtime availability. A future approved capture
must still verify that the service is advertised, the request succeeds, the
response decodes as `gz::msgs::Scene`, and the relevant hierarchy is actually
present after the current spawn pipeline.

## Required distinctions

- `gz topic -l` can list endpoints; it does **not** establish that the spawned
  model retains a ContactSensor component.
- `gz model` textual output is not a machine-readable contract and must not be
  promoted to one through substring, fuzzy, or error-text parsing.
- Scene or visual data must be examined specifically through the typed
  `Link.sensor[]` and `Sensor` fields. Visual geometry alone does not prove a
  ContactSensor component.
- Model/link/sensor identity evidence does not establish a collision event,
  ContactLatch behavior, collision filter policy, action interval, reward,
  termination, or training readiness.

## Future read-only observer capture: design boundary only

Because an existing typed service is statically feasible, the next design
increment may describe **one separately approved, read-only observer capture**
that:

- launches the locked source revision only after its world-name and hash gates
  pass;
- calls the existing typed `/world/world_demo/scene/info` service using a
  machine-readable Gazebo Transport/protobuf client;
- stores the raw protobuf/binary response or a lossless typed representation,
  service metadata, exact identity comparisons, timestamps, command exit or
  client result, and SIGINT-only shutdown record;
- has no ROS bridge, no ROS collector, no raw-contact collector/analyzer, no
  command publisher, and no service/action/world-control mutation; and
- treats an absent or undecodable service/response as an incomplete diagnostic,
  never as sensor absence.

That future observer must be designed and separately approved. This audit does
not create it and grants no execution authority.

## Result and limits

**A. EXISTING_MACHINE_READABLE_OBSERVER_STATICALLY_FEASIBLE**

The existing, world-loaded SceneBroadcaster plus the documented typed Scene
service is a statically feasible path for an exact post-spawn model/link/sensor
inspection. This conclusion is limited to static interface feasibility. It
does not confirm that this world run will advertise the service, that the
spawned model contains the approved ContactSensor, or that a configured raw
Contacts endpoint will exist.

No statement in this audit is collision-event evidence, ContactLatch evidence,
filter-policy approval, reward/termination approval, Gym/training approval, or
hardware readiness.
