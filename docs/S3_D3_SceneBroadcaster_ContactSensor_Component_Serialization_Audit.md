# S3 D3 SceneBroadcaster / ContactSensor Component Serialization Audit

## Scope and result

This is a static, read-only audit of the version-matched Gazebo Sim 8 serialization path used by `/world/world_demo/scene/info`. It created no Transport node, did not call `RequestRaw`, and did not start Gazebo, ROS, `gz`, a spawn, bridge, command/control path, hardware, packet, guard, or run. It changes no source, raw artifact, or consumed guard.

**Overall verdict: `SCENE_BROADCASTER_OMITS_CONTACT_CONFIGURATION_BY_DESIGN`.** The same implementation also omits collision children from `gz::msgs::Link` by construction. Therefore this Scene service is suitable for the captured model/link/sensor hierarchy and contact-sensor *type*, but not for retrieving the configured collision target.

## Authority and version table

| Authority | Version / identity | Evidence used |
| --- | --- | --- |
| Gazebo Sim | `gz-sim8` official source branch, corresponding to installed Gazebo Sim 8 API | Official [`SdfEntityCreator.cc`](https://github.com/gazebosim/gz-sim/blob/gz-sim8/src/SdfEntityCreator.cc) and [`SceneBroadcaster.cc`](https://github.com/gazebosim/gz-sim/blob/gz-sim8/src/systems/scene_broadcaster/SceneBroadcaster.cc) source. The installed package provides the matching ECS component headers under `/opt/ros/jazzy/opt/gz_sim_vendor/include/gz/sim8/`. |
| `gz-msgs10` | Installed generated proto/header API used by S3.3.72 | `/opt/ros/jazzy/opt/gz_msgs_vendor/share/gz/gz-msgs10/protos/gz/msgs/{scene,link,sensor,contactsensor,collision}.proto` and generated headers under `include/gz/msgs10/gz/msgs/`. |
| SDFormat | Installed SDFormat 1.11 schema | `/opt/ros/jazzy/opt/sdformat_vendor/share/sdformat14/1.11/contact.sdf`. It defines `<contact><collision>` as the name of a collision within the link. |
| Gazebo contact example | Installed Gazebo Sim 8 example | `/opt/ros/jazzy/opt/gz_sim_vendor/share/gz/gz-sim8/worlds/contact_sensor.sdf`; it places collision and contact sensor in one link and loads `gz::sim::systems::Contact`. |
| S3.3.72 immutable evidence | Consumed native run | [post-run evidence audit](S3_D3_Native_Contact_Endpoint_S3_3_72_Post_Run_Evidence_Audit.md), including `Sensor.type = "contact_sensor"`, absent `Sensor.contact`, and `base_link_collision_count = 0`. |

The external source links are official Gazebo source for the required Gazebo Sim 8 implementation that is not shipped as local `.cc` source. No blog, forum, or inferred CLI behavior was used.

## Native SDF to ECS to Scene path

```text
native SDF <link><collision> / <sensor type="contact"><contact>...
    |
    | SdfEntityCreator
    v
ECS collision entity: Collision + Name + Pose + Geometry + CollisionElement(sdf::Collision)
ECS sensor entity:    Sensor + Name + Pose + ContactSensor(sdf::ElementPtr)
    |
    | SceneBroadcaster::SceneGraphAddEntities
    v
scene graph: msgs::Link vertex; msgs::Sensor vertex
    |
    | ContactSensor component present => sensorMsg.type = "contact_sensor"
    | no collision vertex path; no Sensor.contact construction path
    v
SceneInfoService: msgs::Scene -> Model -> Link -> Sensor
```

`SdfEntityCreator` creates `components::Collision`, name, pose, geometry, and `components::CollisionElement(*_collision)` for each native SDF collision. It separately creates `components::Sensor`, name, and pose for every sensor; for `sdf::SensorType::CONTACT`, it creates `components::ContactSensor` from the source sensor element. See the official [`Collision creation`](https://github.com/gazebosim/gz-sim/blob/gz-sim8/src/SdfEntityCreator.cc#L968-L990) and [`CONTACT creation`](https://github.com/gazebosim/gz-sim/blob/gz-sim8/src/SdfEntityCreator.cc#L994-L1006) / [`#L1129-L1136`](https://github.com/gazebosim/gz-sim/blob/gz-sim8/src/SdfEntityCreator.cc#L1129-L1136) paths. The local component headers identify `ContactSensor` as `Component<sdf::ElementPtr>` and `CollisionElement` as `Component<sdf::Collision>`.

The Contact system is separate from SceneBroadcaster. Its official implementation reads `<contact><collision>` from `components::ContactSensor`, looks up child entities by `components::Collision` plus exact `components::Name`, and creates `ContactSensorData` on matched collision entities. It then advertises/publishes `gz::msgs::Contacts` only when contacts exist. See [`Contact.cc` CreateSensors](https://github.com/gazebosim/gz-sim/blob/gz-sim8/src/systems/contact/Contact.cc#L166-L216) and [`Publish`](https://github.com/gazebosim/gz-sim/blob/gz-sim8/src/systems/contact/Contact.cc#L147-L164). That is a separate runtime behavior and is not serialized by SceneBroadcaster's Scene response.

`SceneBroadcaster` exposes `scene/info` under the `/world/<world-name>` namespace, hence `/world/world_demo/scene/info`, and its service response calls `AddModels` over its own scene graph. See [`SetupTransport`](https://github.com/gazebosim/gz-sim/blob/gz-sim8/src/systems/scene_broadcaster/SceneBroadcaster.cc#L582-L603) and [`SceneInfoService`](https://github.com/gazebosim/gz-sim/blob/gz-sim8/src/systems/scene_broadcaster/SceneBroadcaster.cc#L677-L692).

## Component-to-protobuf mapping

| Requested field | Native producer / ECS source | SceneBroadcaster condition and implementation | Scene response contract | S3.3.72 observation |
| --- | --- | --- | --- | --- |
| `Model` / `Link` hierarchy | `components::Model` or `components::Link`, plus `Name`, `ParentEntity`, `Pose` | `EachNew` makes `msgs::Model` and `msgs::Link` graph vertices. | Serialized through `AddModels` then `AddLinks`. | Exact `ROBOT_URDF_final` and `base_link` were present. |
| `Link.collision[]` | Native collision entity has `Collision`, `Name`, `Pose`, `Geometry`, and `CollisionElement`. | No collision header is included in SceneBroadcaster; no collision `EachNew` creates a `msgs::Collision` graph vertex; `AddLinks` calls only visuals, lights, sensors, particle emitters, and projectors. | `link.proto` is schema-capable (`repeated Collision collision = 12`), but this SceneBroadcaster implementation does not populate it. | Count was zero, which is expected from this serializer and is not evidence that the native SDF collision was absent. |
| `Sensor.type` | A generic `Sensor` component plus a type-specific component, including `ContactSensor`. | For a `ContactSensor` component, the implementation sets `sensorMsg->set_type("contact_sensor")`. | Serialized because `AddSensors` copies the graph's `msgs::Sensor` into `Link.sensor[]`. | Exact sensor had type `contact_sensor`. This is consistent with the ContactSensor ECS component being observed by SceneBroadcaster. |
| `Sensor.contact` | `ContactSensor` contains the original SDF element, including `<contact><collision>`. | The contact branch sets only `Sensor.type`; it never calls `mutable_contact()` or writes a collision name. | `sensor.proto` is schema-capable (`ContactSensor contact = 11`), but SceneBroadcaster leaves it absent. | Field absent. This is expected from the serializer and is not proof that the source SDF lacked the contact configuration. |
| `ContactSensor.collision_name` | SDFormat `<contact><collision>` held in the ContactSensor element; Contact system consumes that element for its exact collision lookup. | No SceneBroadcaster conversion from `components::ContactSensor::Data()` into `msgs::Sensor.contact` exists. | `contactsensor.proto` is schema-capable (`string collision_name = 2`), but it is not populated in this service response. | No value exists in the raw Scene message. It cannot identify `s3_d3_base_contact_collision`. |

The type-specific behavior is directly visible in official [`SceneGraphAddEntities`](https://github.com/gazebosim/gz-sim/blob/gz-sim8/src/systems/scene_broadcaster/SceneBroadcaster.cc#L855-L921): the generic sensor fields are built, and the contact branch assigns only the type string. `AddSensors` copies that message to the link, while [`AddLinks`](https://github.com/gazebosim/gz-sim/blob/gz-sim8/src/systems/scene_broadcaster/SceneBroadcaster.cc#L1216-L1229) and [`#L1267-L1295`](https://github.com/gazebosim/gz-sim/blob/gz-sim8/src/systems/scene_broadcaster/SceneBroadcaster.cc#L1267-L1295) enumerate no collision addition routine.

## Claim, evidence, and verdict matrix

| Claim | Evidence | Verdict |
| --- | --- | --- |
| A native SDF contact sensor is represented in ECS | Official SdfEntityCreator creates `components::ContactSensor` for `sdf::SensorType::CONTACT`; local header preserves the sensor SDF element. | `CONFIRMED` as the static creation contract; it does not establish that any particular runtime spawn succeeded. |
| A native SDF collision is represented in ECS | Official SdfEntityCreator creates `Collision` and `CollisionElement` from each SDF collision. | `CONFIRMED` as the static creation contract; it does not establish any particular runtime collision entity. |
| `Sensor.type` is expected in Scene for a ContactSensor ECS component | Official SceneBroadcaster tests `components::ContactSensor` and assigns `contact_sensor`; sensor graph nodes are copied to `Link.sensor[]`. | `CONFIRMED` |
| `Link.collision[]` is expected to list native collisions in `scene/info` | Schema has the field, but official SceneBroadcaster has no collision graph/addition path and `AddLinks` omits collisions. | `SCENE_BROADCASTER_OMITS_COLLISION_BY_DESIGN` (field-level result) |
| `Sensor.contact.collision_name` is expected to carry the configured target in `scene/info` | Schema has `Sensor.contact` and `ContactSensor.collision_name`, but official contact branch serializes only the type string. | `SCENE_BROADCASTER_OMITS_CONTACT_CONFIGURATION_BY_DESIGN` |
| Captured absent contact field means the SDF ContactSensor was not created | The serializer intentionally omits configuration after seeing the ContactSensor component. | `UNKNOWN` — the inference is invalid. |
| Captured absent collision list means the native collision was not created | The serializer intentionally does not add collision children. | `UNKNOWN` — the inference is invalid. |
| Captured Scene determines whether the Contact endpoint was advertised or a collision occurred | Endpoint advertisement/contact publication is owned by the Contact system and is not a SceneBroadcaster Scene field. | `UNKNOWN` — no endpoint/event inference is admissible. |

## Consequence for S3.3.72

S3.3.72 remains valid hierarchy evidence: the raw protobuf independently contains the exact model, `base_link`, exact sensor name, and the type string `contact_sensor`. The final type is the positive hierarchy-level claim permitted by `SCENE_SENSOR_PRESENT_IDENTITY_ONLY`.

The same evidence cannot answer whether the configured target was `s3_d3_base_contact_collision`: both the zero `Link.collision[]` count and absent `Sensor.contact` are expected serialization omissions. It also cannot answer whether the Contact system advertised `/s3_d3/contact/raw`, whether physics populated `ContactSensorData`, whether any collision event occurred, or whether ContactLatch, collision policy, reward, termination, Gym/training, or hardware behavior is ready.

## Narrow next step

The smallest follow-on is a design-only audit of an official ECM/component inspection interface or a minimal diagnostic system that can read `components::ContactSensor` and the exact `components::Collision`/`Name` children after spawn. The candidate data source is the documented ECS components used by the official Contact system, not `/world/world_demo/scene/info`; no producer, code change, approval packet, guard, or runtime run is selected by this audit.

## Non-mutation confirmation

This audit did not run runtime software and did not mutate source, raw evidence, packets, guards, or historical records.
