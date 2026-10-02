# S3 D3 ECS ContactSensor Component Inspection Design Audit

## Scope and verdict

This is a static, read-only design audit. It did not start Gazebo, ROS, `gz`, a Transport node, a Scene request, spawn, bridge, command/control path, hardware, packet, guard, or run. It did not modify native SDF, the world, launch, helper, supervisor, raw evidence, packet, or guard.

**Verdict: `MINIMAL_DIAGNOSTIC_SYSTEM_REQUIRED`.** The installed public ECM API gives an in-process Gazebo system direct, typed access to the required components. This audit found no existing externally callable, read-only Gazebo Sim 8.11.0 interface with an official, typed contract that exposes the exact `components::ContactSensor` SDF element and its configured collision target. `/world/world_demo/scene/info` is specifically insufficient by the S3.3.73 serializer audit.

## Exact authority

| Authority | Exact version / revision | Evidence |
| --- | --- | --- |
| Gazebo Sim | `gz-sim8_8.11.0`, commit [`1be3cc376fec778cc725b4eeea463245affa56d3`](https://github.com/gazebosim/gz-sim/commit/1be3cc376fec778cc725b4eeea463245affa56d3) | Official [release tag](https://github.com/gazebosim/gz-sim/releases/tag/gz-sim8_8.11.0) identifies the tag and commit. The release revision changes `gz-sim8` to version `8.11.0`. |
| Local Gazebo Sim public API | Installed Sim 8 headers | `/opt/ros/jazzy/opt/gz_sim_vendor/include/gz/sim8/gz/sim/{System,EntityComponentManager}.hh` and `components/{ContactSensor,Collision,Link,Model,Name,ParentEntity,Sensor}.hh`. |
| Exact upstream source needed for implementation bodies | Official `gz-sim8_8.11.0` revision | [`SdfEntityCreator.cc`](https://github.com/gazebosim/gz-sim/blob/1be3cc376fec778cc725b4eeea463245affa56d3/src/SdfEntityCreator.cc), [`Contact.cc`](https://github.com/gazebosim/gz-sim/blob/1be3cc376fec778cc725b4eeea463245affa56d3/src/systems/contact/Contact.cc), and [`SceneBroadcaster.cc`](https://github.com/gazebosim/gz-sim/blob/1be3cc376fec778cc725b4eeea463245affa56d3/src/systems/scene_broadcaster/SceneBroadcaster.cc). The installed vendor package does not ship these `.cc` files. |
| `gz-msgs10` | Installed 10.3.2 schema used by S3.3.72 | `/opt/ros/jazzy/opt/gz_msgs_vendor/share/gz/gz-msgs10/protos/gz/msgs/{scene,link,sensor,contactsensor}.proto`. |
| SDFormat | Installed 1.11 | `/opt/ros/jazzy/opt/sdformat_vendor/share/sdformat14/1.11/contact.sdf`. `<contact><collision>` is required and names the collision within the link. |

## A. ECM access boundary

`EntityComponentManager` is an in-process server API. `ISystemConfigure::Configure` receives a mutable ECM after SDF world entities/components load and before simulation execution; `ISystemPreUpdate`, `ISystemUpdate`, and `ISystemPostUpdate` receive it at their respective lifecycle stages. `ISystemPostUpdate` receives `const EntityComponentManager &`, which is the minimal read-only callback surface for a future diagnostic snapshot.

The installed ECM header documents `Component`, `ComponentData`, `EntityByComponents`, `EntitiesByComponents`, `ChildrenByComponents`, and `Each`/`EachNoCache`; its `Each` documentation warns that these calls must occur only in a System callback. Therefore an external Transport client cannot obtain the ECM object via this public API.

Existing transport projections do not change that boundary:

- `SceneBroadcaster` exposes `/world/world_demo/scene/info`, but S3.3.73 proves it serializes the contact sensor type only, not collision children or `Sensor.contact` configuration.
- `SceneBroadcaster` also has a generic serialized-state service implementation, but this audit found no official typed external inspection contract that decodes `components::ContactSensor`'s `sdf::ElementPtr` into the required `<contact><collision>` identity. The component uses the default serializer rather than an explicit `sdf::Sensor -> msgs::Sensor` serializer. It is not an admissible substitute for an exact ContactSensor configuration inspection without a separately version-locked serialization audit.
- No local Gazebo Sim 8.11.0 header/source inspected here exposes an external read-only ECM query service for the exact component chain.

Consequently, no non-plugin ECS inspection API is confirmed for this fact. A future diagnostic system is required; this audit neither selects how it is loaded nor implements it.

## B. Exact identity and component lookup contract

| Required fact | Official read-only ECM query | Exact match condition | Fail-closed result |
| --- | --- | --- | --- |
| Model `ROBOT_URDF_final` | `EntitiesByComponents(components::Model(), components::Name("ROBOT_URDF_final"))` | Exactly one entity | Zero or more than one is not a model identity confirmation. |
| Immediate link child `base_link` | `ChildrenByComponents(model, components::Link(), components::Name("base_link"))` | Exactly one child link | Zero or multiple exact children is not link confirmation. |
| Immediate sensor child `s3_d3_base_contact_sensor` | `ChildrenByComponents(link, components::Sensor(), components::Name("s3_d3_base_contact_sensor"))` | Exactly one child sensor | Zero or multiple exact children is not sensor confirmation. |
| Contact-sensor component | `Component<components::ContactSensor>(sensorEntity)` | Non-null component | Missing component is not inferred from name/type alone. |
| Configured collision literal | `contactSensor->Data()` returns `sdf::ElementPtr`; query exact child `contact`, then exact child `collision`, then `Get<std::string>()` | Element, contact child, collision child, and non-empty exact text all exist and parse | Any missing/parse failure is incomplete configuration evidence, not a mismatch conclusion. |
| Collision child targeted by sensor | `ChildrenByComponents(link, components::Collision(), components::Name(target))` | Exactly one child collision with the same exact target | Zero or multiple entities is not a resolved target confirmation. |
| Parent relationship provenance | `ParentEntity` on link/sensor/collision, plus the immediate-child query above | Every discovered entity's parent equals its expected model/link entity | Parent mismatch or missing component invalidates the snapshot. |

These are equality-based component queries: `components::Name` explicitly has no scoped-name concept, so the diagnostic must not accept a prefix, suffix, substring, or guessed scope. `ChildrenByComponents` is expressly documented as an immediate-parent query. The official `ContactSensor` typedef is `Component<sdf::ElementPtr>` and its header states that it currently holds the whole `<sensor>` element; it is not a typed `sdf::Contact` object. The SDF element access therefore needs the explicit missing-element checks in the table.

## C. Contact-system relation

The exact 8.11.0 Contact-system logic is the appropriate semantic comparison:

1. It visits new `components::ContactSensor` entities.
2. It verifies the parent entity has `components::Link`.
3. It reads `<contact><collision>` from the stored SDF element.
4. For each configured collision literal, it uses `ChildrenByComponents(parentLink, components::Collision(), components::Name(collisionName))`.
5. For a found collision entity, it creates `ContactSensorData`; its later update/publish path consumes that data.

This is shown by the official [`ContactPrivate::CreateSensors`](https://github.com/gazebosim/gz-sim/blob/1be3cc376fec778cc725b4eeea463245affa56d3/src/systems/contact/Contact.cc#L166-L216). A future diagnostic may compare its snapshot to this lookup contract, but must not claim to execute or replace the Contact system.

| Evidence level | What it can establish | What it cannot establish |
| --- | --- | --- |
| `SENSOR_CONFIGURATION_TARGET_OBSERVED` | Exact sensor ECS component contains an exact configured collision literal. | That a collision entity exists, that Contact resolved it, that a topic is advertised, or that an event occurred. |
| `SENSOR_TARGET_COLLISION_CHILD_OBSERVED` | Exact configured literal matches exactly one immediate link child with `Collision` and `Name`. | That the Contact system has created `ContactSensorData`, that physics has populated it, endpoint publication, or an event. |
| `CONTACT_SYSTEM_RESOLUTION_UNVERIFIED` | No stronger conclusion than the prior static snapshot. | It must not be turned into endpoint/event failure. |
| Contact endpoint advertised | Requires separate evidence from the Contact system/transport at runtime. | Does not itself prove a contact event. |
| Contact event | Requires actual `gz::msgs::Contacts` data from the Contact system. | Does not prove ContactLatch, collision policy, reward, termination, training, or hardware readiness. |

## Minimal future diagnostic-system design boundary

Only the following design is justified by the audited API; it is not an implementation or runtime approval:

- A Gazebo Sim `System` uses `ISystemPostUpdate` and its `const EntityComponentManager &` to take one immutable, exact-name snapshot after the already-approved bootstrap condition.
- It uses only the component queries listed above and emits a bounded typed result containing entity IDs, exact names, target text, exact counts, parent IDs, lifecycle hook name, and a fail-closed status/reason.
- It must not create, remove, edit, or default components; publish command/control; invoke ROS; bridge; subscribe to raw contacts; or imply that it observed a contact event.
- Suggested statuses are configuration/identity-only: `ECS_MODEL_UNCONFIRMED`, `ECS_LINK_UNCONFIRMED`, `ECS_SENSOR_UNCONFIRMED`, `ECS_CONTACT_COMPONENT_MISSING`, `ECS_CONTACT_CONFIGURATION_INCOMPLETE`, `ECS_TARGET_COLLISION_CHILD_UNCONFIRMED`, and `ECS_SENSOR_TARGET_COLLISION_CHILD_OBSERVED`.

`PostUpdate` is selected only as the minimal read-only lifecycle hook; the future design must separately bind its snapshot timing and evidence persistence. No plugin filename, world modification, output transport, or execution architecture is selected here.

## Why this does not revise S3.3.72

S3.3.72 remains valid for the narrower Scene hierarchy claim: SceneBroadcaster saw the exact model, link, sensor, and contact-sensor type. Its missing collision/configuration fields are explained by the serializer, not converted into evidence that SDF creation failed. This audit does not change the S3.3.72 raw artifact, guard, final `SHUTDOWN_INCOMPLETE`, or its non-claims.

## One narrow next step

Create a design-only approval specification for one minimal read-only Gazebo Sim 8.11.0 diagnostic System that takes the exact `PostUpdate` ECM snapshot described above. It must define its evidence schema and fail-closed statuses before any implementation, world edit, packet, guard, or runtime run.

## Non-mutation confirmation

Zero runtime activity occurred. No source, raw artifact, guard, packet, launch, model, world, or configuration was mutated.
