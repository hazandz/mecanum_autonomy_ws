# S3 D3 Native Contact Endpoint S3.3.72 Post-Run Evidence Audit

## Scope and immutable inputs

This is a read-only, offline audit of the consumed S3.3.72 run. It did not start Gazebo, ROS, `gz`, a Transport node, `RequestRaw`, a spawn, bridge, command/control path, or hardware. It did not create an approval, guard, or run, and did not modify the consumed guard or any raw artifact.

The inspected artifact is [`run-typed-scene-2b333f65cd8843079e20b5f5375d7e6d`](../artifacts/simulation/contact_producer_evidence/run-typed-scene-2b333f65cd8843079e20b5f5375d7e6d). The consumed guard remains [`S3.3.72_NATIVE_CONTACT_ENDPOINT_REPLACEMENT_RUNTIME_RUN.json`](../artifacts/simulation/contact_producer_evidence/approval_guards/S3.3.72_NATIVE_CONTACT_ENDPOINT_REPLACEMENT_RUNTIME_RUN.json).

## A. Artifact integrity and execution receipts

`scene_response.pb` recomputes to:

```text
643408f3c88471c2c3552fd5cd3a243a31c71cdf9b276a9386a47338bcfe19b8
```

This exactly matches both `scene_response.sha256` and `scene_summary.json.raw_response_sha256`.

All seven JSON records carrying `run_id` contain `run-typed-scene-2b333f65cd8843079e20b5f5375d7e6d`. Timestamp ordering is internally consistent:

```text
preflight_start 15649909037952
<= preflight_end 15651909355281
<= request_start 15651909355934
<= request_end 15652011643344
```

The summary and metadata carry the same four timestamp values. The create record has one invocation, the exact native `-world/-file` argv, and exit code zero. This is Candidate-A operational evidence only; it is not an entity, reset, or settled-state receipt.

`shutdown_outcome.json` is the terminal cleanup fact: `final_classification` is `SHUTDOWN_INCOMPLETE`, `deadline_result` is `INCOMPLETE`, and its grace is 5000 ms. The bootstrap log independently records that `ros2 launch` sent SIGINT to `gazebo-1`, waited five seconds, then escalated that child to SIGTERM; Gazebo exited with code `-15`. This is launcher-managed escalation, not an end-to-end SIGINT-only cleanup result.

There is exactly one durable `helper_process.json` record and `request_metadata.json.request_raw_called` is `true`. There is no durable numeric `helper_invocation_count` or `request_raw_invocation_count` field. Therefore the artifact independently proves one persisted helper-process receipt and a request receipt, but does not itself supply a numeric cardinality proof beyond those records.

## B. Actual world provenance

The bootstrap log names the world actually loaded by Gazebo as:

```text
/home/hazan/mecanum_autonomy_ws/ros2_ws/install/ROBOT_URDF_final_description/share/ROBOT_URDF_final_description/launch/tugbot_depot.sdf
```

Both the locked source file and that installed file are regular, non-symlink files. Their bytes are equal and their SHA-256 is:

```text
a4b6253340baa866d89640d62a94d04fbea51425e9af1deca591422a0a36d91d
```

This equals the world hash locked by the S3.3.72 packet/guard. Therefore the actual installed-world path can be connected to the locked revision without a `WORLD_PROVENANCE_GAP`.

The separately hash-locked source/install native model establishes model-input provenance only. It does not substitute for this independent world source/install parity check.

## C. Version-matched Scene protobuf audit

### Local official authority

- `gz-msgs10` 10.3.2 generated schema sources:
  - `/opt/ros/jazzy/opt/gz_msgs_vendor/share/gz/gz-msgs10/protos/gz/msgs/scene.proto`
  - `/opt/ros/jazzy/opt/gz_msgs_vendor/share/gz/gz-msgs10/protos/gz/msgs/link.proto`
  - `/opt/ros/jazzy/opt/gz_msgs_vendor/share/gz/gz-msgs10/protos/gz/msgs/sensor.proto`
  - `/opt/ros/jazzy/opt/gz_msgs_vendor/share/gz/gz-msgs10/protos/gz/msgs/contactsensor.proto`
  - `/opt/ros/jazzy/opt/gz_msgs_vendor/share/gz/gz-msgs10/protos/gz/msgs/collision.proto`
- SDFormat 1.11 contact schema: `/opt/ros/jazzy/opt/sdformat_vendor/share/sdformat14/1.11/contact.sdf`.
- Gazebo Sim 8 official installed example: `/opt/ros/jazzy/opt/gz_sim_vendor/share/gz/gz-sim8/worlds/contact_sensor.sdf`.

The SDFormat authority defines `<contact><collision>` as the collision name within the link and `<contact><topic>` as the contacts topic. The Gazebo Sim example places a contact sensor and its named collision under the same link and loads `gz::sim::systems::Contact`.

### Schema capability

`gz::msgs::Scene` has repeated `Model` field 9. `Model` has repeated `Link` field 7. `Link` has repeated `Sensor` field 13 and repeated `Collision` field 12. These are official generated protobuf fields.

`gz::msgs::Sensor.type` is field 6 of protobuf type `string`; it is **not an enum**, so there is no enum numeric value to extract. `gz::msgs::Sensor.contact` is message field 11. Its message type is `gz::msgs::ContactSensor`, whose `collision_name` is string field 2. Thus this Scene schema can represent a configured collision target when the contact submessage and its value are present.

### Temporary decoder result

A temporary C++ decoder was compiled with the locked `gz-msgs10` pkg-config closure, read only `scene_response.pb`, parsed `gz::msgs::Scene`, and used generated descriptor/reflection APIs. It did not construct `gz::transport::Node`, call `RequestRaw`, or write an artifact.

```text
scene_model_count=5
exact_model_name=ROBOT_URDF_final
exact_model_link_count=7
exact_link_name=base_link
base_link_collision_count=0
base_link_sensor_count=1
exact_sensor_name=s3_d3_base_contact_sensor
sensor_type_field_number=6
sensor_type_field_proto_type=string
sensor_type_raw_value=contact_sensor
contact_field_number=11
contact_field_present=false
```

Because `contact` is absent in the raw message, no `contact.collision_name` value exists in this capture. The schema is sufficient to carry it, but the captured Scene does not provide the configured collision identity. The exact configured literal `s3_d3_base_contact_collision` is not present as a Scene collision or contact target in this raw response.

## Claim matrix

| Claim | Evidence | Verdict |
| --- | --- | --- |
| Raw response integrity | Recomputed SHA equals receipt and summary | `CONFIRMED` |
| Shared artifact identity and timestamp order | All JSON run IDs and summary/metadata timestamp ordering match | `CONFIRMED` |
| One create receipt | `create_process.json.invocation_count = 1`, exact argv, exit code 0 | `CONFIRMED` |
| Numeric cardinality of helper invocations / RequestRaw calls | One helper record and boolean request receipt exist; no numeric counter exists | `UNKNOWN` |
| Terminal cleanup classification | Shutdown record says `SHUTDOWN_INCOMPLETE`; bootstrap log documents SIGINT then launcher SIGTERM escalation | `CONFIRMED` |
| Actual Gazebo world provenance | Bootstrap log installed path; source/installed world are equal regular files with locked SHA | `CONFIRMED` |
| Exact model `ROBOT_URDF_final` in captured Scene | Descriptor/reflection decoded exact model | `CONFIRMED` |
| Exact link `base_link` in captured Scene | Descriptor/reflection decoded exact link | `CONFIRMED` |
| Exact sensor `s3_d3_base_contact_sensor` in captured Scene | Descriptor/reflection decoded exact sensor | `CONFIRMED` |
| Sensor type field and raw value | Official field 6 is string; reflection decoded `contact_sensor`; no enum exists | `CONFIRMED` |
| Scene schema can carry configured collision identity | Official `Sensor.contact` field 11 and `ContactSensor.collision_name` field 2 exist | `CONFIRMED` |
| Exact configured collision identity in this Scene response | `contact` is absent and `base_link_collision_count = 0` | `UNKNOWN` — `COLLISION_IDENTITY_NOT_PRESENT_IN_CAPTURED_SCENE` |
| Contact event, ContactLatch, collision policy, reward, termination, training/Nav2, or hardware readiness | Not represented by this passive Scene response | `UNKNOWN` |

## Narrow next step

The smallest next increment is a static, read-only Gazebo Sim 8 SceneBroadcaster/component-serialization audit: trace whether a spawned native SDF ContactSensor component is expected to populate `gz::msgs::Sensor.contact` and `Link.collision[]` in `/world/world_demo/scene/info`. It should not modify the helper or SDF and should not create an approval, guard, or run.

## Conclusion

S3.3.72 independently preserves valid raw Scene hierarchy evidence for the exact model, link, sensor, and raw `Sensor.type` field. It does **not** preserve configured collision identity in the captured Scene message, despite the version-matched schema having a field capable of carrying that identity. The evidence therefore supports `SCENE_SENSOR_PRESENT_IDENTITY_ONLY` with the stated collision-identity limitation, and the final run cleanup remains `SHUTDOWN_INCOMPLETE`.
