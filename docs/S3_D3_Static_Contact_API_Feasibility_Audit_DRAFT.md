# S3 D3 — Static Gazebo Contact API Feasibility Audit

**Status: READY_FOR_CONTACT_PRODUCER_DECISION_PACKET**

## Scope and evidence rules

This is a static, read-only audit of the installed Gazebo Sim 8 / ROS Jazzy stack and the current workspace source. It neither selects a collision filter nor creates a contact sensor, system plugin, bridge mapping, topic, ContactLatch, or runtime. It does not establish collision detection, termination, reward, Gymnasium, training, command, or hardware readiness.

The D3 provenance requirement remains defined in [S3 D3 ContactLatch and Collision Fact Contract](S3_D3_ContactLatch_And_Collision_Fact_Contract_DRAFT.md); the previous options inventory is [S3 D3 Gazebo Contact Producer Options and Evidence Plan](S3_D3_Gazebo_Contact_Producer_Options_And_Evidence_Plan_DRAFT.md). Static collision identities remain only inventory candidates under [S3 World Geometry and Entity Inventory](S3_World_Geometry_And_Entity_Inventory_DRAFT.md).

## 1. Installed-stack evidence

| Static evidence | Local path / package | What it proves | What it does not prove |
| --- | --- | --- | --- |
| Contact system is installed | `/opt/ros/jazzy/opt/gz_sim_vendor/lib/gz-sim-8/plugins/libgz-sim8-contact-system.so`; `gz-sim8-contact-system.pc`, version `8.11.0` | A loadable `gz::sim::systems::Contact` system exists on this stack. | That the project world loads it, or that its output satisfies D3 provenance. |
| ContactSensor component exists | `.../include/gz/sim8/gz/sim/components/ContactSensor.hh` and `ContactSensorData.hh` | Gazebo Sim has a ContactSensor component and contact data component with `msgs::Contacts`. | The project robot has a sensor of this type or a runtime topic. |
| Minimal SDF example exists | `.../share/gz/gz-sim8/worlds/contact_sensor.sdf` | The example loads `gz-sim-contact-system` / `gz::sim::systems::Contact` and configures `<sensor type=contact>` with `<contact><collision>...` and `<topic>...`. | Compatibility with this specific robot/world, correct collision filter, or event semantics under the project workload. |
| Gazebo contact protobuf types exist | `.../share/gz/gz-msgs10/protos/gz/msgs/contact.proto` and `contacts.proto` | `gz::msgs::Contact` and `gz::msgs::Contacts` are installed message types. | Producer timestamp population, sequence behavior, or a topic name in this project. |
| ROS contact types and bridge conversion exist | `/opt/ros/jazzy/share/ros_gz_interfaces/msg/Contact.msg`, `Contacts.msg`; `/opt/ros/jazzy/include/ros_gz_bridge/ros_gz_bridge/convert/ros_gz_interfaces.hpp` | `ros_gz_interfaces/msg/Contacts` exists and explicit `convert_gz_to_ros` declarations exist for `gz::msgs::Contact`/`Contacts`. | A configured bridge endpoint, actual conversion behavior on a live graph, or source-event provenance. |
| Current project configuration | `ROBOT_URDF_final.gazebo`, `launch/tugbot_depot.sdf`, `config/ros_gz_bridge_gazebo.yaml`, `launch/gazebo.launch.py` | The actual source has physics, sensors, static collision geometry, camera/LiDAR, and the listed motion/odometry systems. | A contact system, `<sensor type=contact>`, or contact bridge mapping; none is present in the audited configuration. |

Installed ROS package metadata observed during this audit: `ros-jazzy-ros-gz`, `ros-jazzy-ros-gz-bridge`, `ros-jazzy-ros-gz-interfaces`, and `ros-jazzy-ros-gz-sim`, each release family version `1.0.22`. This confirms the locally audited package set only; it is not a runtime graph observation.

## 2. Static ContactSensor configuration and message payload

### Verified minimal SDF pattern

The installed `contact_sensor.sdf` example gives the following minimum static pattern:

```xml
<plugin filename="gz-sim-contact-system" name="gz::sim::systems::Contact"/>

<sensor name="sensor_contact" type="contact">
  <contact>
    <collision>collision_sphere</collision>
    <topic>/contact_example</topic>
  </contact>
  <always_on>1</always_on>
  <update_rate>100</update_rate>
</sensor>
```

This is an example of installed Gazebo Sim 8 syntax, not an approved change to the project world or robot. It neither selects the named project collision geometry nor establishes a project topic name/rate.

### Verified Gazebo payload fields

The installed `gz::msgs::Contact` protobuf defines:

| Payload item | Static finding | D3 interpretation |
| --- | --- | --- |
| `header` | Optional `gz::msgs::Header`; header schema has `Time stamp` and repeated key/value `data`. | A timestamp field is representable, but static definitions do not prove Contact system populates it in this project. `data` is not a guaranteed command/lifecycle sequence. |
| `collision1`, `collision2` | `gz::msgs::Entity` fields. Entity has `id`, `name`, and `type`; proto says a name is not guaranteed unique. | Pair identities are representable. Stable fully scoped names are **not** guaranteed by the protobuf schema. |
| `position`, `normal`, `depth`, `wrench` | Repeated fields. | A message may carry multiple contact points and related vectors/depths/wrenches. This represents payload multiplicity, not a selected aggregation policy. |
| `world` | `gz::msgs::Entity` field. | A world identity can be represented; it is not proof that `world_demo` equals a ROS coordinate frame. |
| `Contacts.header` and repeated `contact` | Optional aggregate header plus repeated contacts. | Aggregate timestamp and multiple contact entries are representable; producer population/order must be measured. |
| Dedicated sequence field | No dedicated sequence field appears in `contact.proto`, `contacts.proto`, or `header.proto`. | `NOT_AVAILABLE_IN_MESSAGE_SCHEMA`; a producer/adaptor sequence or deterministic event-ID rule requires an explicit design. |

The installed ROS type mirrors contact pairs and repeated positions/normals/depths/wrenches. `ros_gz_interfaces/msg/Contacts` has a ROS header and repeated contacts. Bridge conversion declarations prove compilation-level type conversion support, not the exact header/identity values emitted at runtime.

## 3. Feasibility of the four D3 options

| D3 option | Static status | Local evidence | What remains unknown or required |
| --- | --- | --- | --- |
| A. Gazebo ContactSensor | `STATICALLY_FEASIBLE` | Installed Contact system library, ContactSensor component, and `contact_sensor.sdf` show required plugin plus `<sensor type=contact>` configuration. | Need an approved world/URDF change, source collision selection, runtime topic/type, timestamp population, entity identity format, duplication/multiplicity, and filter evidence. |
| B. Gazebo system/plugin creates contact events | `STATICALLY_FEASIBLE` for the built-in `gz::sim::systems::Contact`; `CUSTOM_IMPLEMENTATION_REQUIRED` only if a new producer-specific schema is selected. | `libgz-sim8-contact-system.so` and example world prove a built-in system exists. | The current project does not load it. Built-in output has no dedicated sequence or transition/lifecycle fields. Whether a custom producer is needed depends on the approved adapter/provenance design. |
| C. Gazebo Transport `Contacts` plus `ros_gz_bridge` | `STATICALLY_FEASIBLE` conditional on Option A/B producing a compatible GZ topic. | Gazebo `gz::msgs::Contacts`, ROS `ros_gz_interfaces/msg/Contacts`, and bridge conversion declarations are installed. | Need approved GZ topic name and direction, parameter-bridge mapping, live type verification, and evidence that fields survive conversion as required. No contact bridge is currently configured. |
| D. Minimal custom producer/system | `CUSTOM_IMPLEMENTATION_REQUIRED` | No project custom contact producer exists; installed plugin API/component packages make a future Gazebo system technically linkable. | Requires approved ownership, package placement, schema/version, build dependencies, producer semantics, and runtime evidence. |

None of these status labels means the present project configuration has a collision source. The active world does not load the Contact system, does not configure a contact sensor, and does not bridge contacts.

## 4. Is ContactSensor plus bridge sufficient for D3?

**It is sufficient only as a statically feasible raw-contact observation path, not as a complete D3 provenance contract.**

Static evidence supports a chain of the form:

```text
Gazebo Contact system + configured ContactSensor
  -> gz::msgs::Contacts Transport topic
  -> optional GZ-to-ROS ros_gz_bridge conversion
  -> future runtime ContactLatch/adaptor
```

It does not establish the following mandatory D3 properties:

| D3 requirement | Static result | Minimum future producer/adapter responsibility |
| --- | --- | --- |
| Simulation timestamp is populated and interpreted | `UNKNOWN_REQUIRES_RUNTIME` | Preserve the source header timestamp when actually present; otherwise fail closed. |
| Unique producer sequence/event ID | No dedicated protobuf field. | Supply an explicit producer sequence or deterministic event-ID derivation with versioned semantics. |
| Stable collision identities | Entity `id`/`name`/`type` are representable, but name uniqueness and scoped-name stability are not guaranteed. | Define identity representation and capture runtime evidence for resolved names/IDs. |
| Duplicate semantics | Repeated entries are representable; delivery/repetition semantics are unknown. | Specify and test deduplication/replay policy. |
| Simultaneous-contact aggregation | Repeated contacts/points are representable; no policy is encoded. | Define deterministic aggregation without changing raw evidence. |
| Active action interval / transition binding | Not in the Contact/Contacts protobuf schema. | Obtain binding from a separately approved action-barrier owner; do not fabricate it from receive time. |
| Filter policy/version/hash | Not in the raw message schema. | Apply a versioned, approved filter policy in a future adapter/latch. |

A custom Gazebo system/plugin is **not proven to be the only possible route** to simulation timestamp, producer sequence, and identity contract. The installed Contact system can potentially provide raw `Contacts`; a future bridge-adjacent or ROS-side adapter could add validated event identity and join metadata after an approved action barrier. Static source alone cannot determine which placement best preserves event order or source semantics. A custom producer becomes necessary only if the user requires producer-native fields that the built-in event path cannot prove or preserve.

## 5. Conditional V1 recommendation

**Recommendation: Option A + C, conditionally and only for a passive raw-contact evidence run.**

The condition is that the user separately approves:

1. loading the installed `gz::sim::systems::Contact` system and configuring one precisely scoped ContactSensor;
2. one GZ-to-ROS `gz::msgs::Contacts` to `ros_gz_interfaces/msg/Contacts` bridge boundary, with a topic name selected in a later decision packet;
3. a passive observation run that captures raw payloads and graph/type evidence without commands or world control.

This recommendation is based only on static local evidence: the installed Contact system library, installed example SDF syntax, installed `Contacts` protobuf, and installed bridge conversion declarations. It does **not** recommend a collision policy or a complete ContactLatch. Runtime evidence still must establish topic/type, producer timestamp behavior, entity IDs/names, bridge retention, ordering, duplicates, simultaneous contacts, and source behavior after ordinary start/reset lifecycle events.

## 6. Minimal future implementation surface — not created here

| Future surface | Possible location/owner | Potential change | Potential dependency |
| --- | --- | --- | --- |
| Contact-system/SDF configuration | `ROBOT_URDF_final_description` world or robot description | Add the approved built-in Contact system and a scoped contact sensor only after architecture/user approval. | Existing `gz-sim8-contact-system` runtime plugin. |
| GZ-to-ROS bridge mapping | Existing bridge launch/config or an isolated approved measurement bridge | Add exactly the approved `Contacts` mapping, direction, and type. | Existing `ros_gz_bridge`, `ros_gz_interfaces`. |
| Raw-contact collector | Artifact-owned passive measurement tooling | Capture raw contact payloads, clock/receive metadata, graph/type snapshots, and SIGINT-only shutdown evidence. | ROS client and only approved observation endpoints. |
| Runtime ContactLatch/adaptor | Future `mecanum_nav_rl` runtime boundary, ownership pending | Validate source fields, bind action interval/transition, apply filter policy, emit immutable candidate. | Shared core types plus an approved runtime ingress boundary. |
| Custom producer, only if selected | A future Gazebo plugin/system package with clear ownership | Emit a versioned source event with exact required source semantics. | `gz-sim8`, `gz-msgs10`, and corresponding package/build dependencies. |

These are possible surfaces, not authorized edits. In particular, no package dependency, world/URDF, YAML, bridge, or runtime module is modified by this audit.

## 7. Runtime evidence checklist before a collision contract increment

- Confirm the loaded Contact system and configured sensor exist in the actual runtime graph.
- Record exact GZ and ROS topic names, types, directions, producer/bridge identities, and world/hash.
- Capture raw payloads losslessly, including all contact entries and any headers.
- Record source simulation timestamp if present and local steady receive time separately.
- Capture actual entity IDs/names/types and resolve scoped-name stability against the static inventory.
- Measure duplicate and simultaneous-contact behavior without issuing `/cmd_vel`, pose, reset, pause, step, spawn, delete, or other world control.
- Establish, in a separately approved design, the action-barrier owner and legal transition binding.
- Keep collision classification/filter decisions out of this passive evidence run.

## Conclusion

**READY_FOR_CONTACT_PRODUCER_DECISION_PACKET.** The installed Gazebo Sim 8 stack statically supports a Contact system, ContactSensor SDF syntax, `gz::msgs::Contacts`, and ROS bridge conversion. That is enough to ask the user to decide whether to pursue the narrowly scoped Option A+C passive evidence path, but it is not enough to claim a D3 runtime producer, ContactLatch, collision fact, reward, termination, Gymnasium, or training implementation is ready.
