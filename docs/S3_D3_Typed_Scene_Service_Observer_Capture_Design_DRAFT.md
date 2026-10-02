# S3 D3 — Typed Scene-Service Observer Capture Design

**Status: DRAFT — TYPED SCENE OBSERVER DESIGN ONLY — PENDING USER APPROVAL**

## Purpose and scope

This document designs, but does not create or authorize, one future
machine-readable and read-only observer. Its sole purpose is to determine
whether the spawned scene contains the exact identity chain:

```text
ROBOT_URDF_final → base_link → s3_d3_base_contact_sensor
```

The observer would query the existing Gazebo Scene service exactly once:

```text
service:  /world/world_demo/scene/info
request:  gz::msgs::Empty
response: gz::msgs::Scene
```

It is explicitly not a ROS bridge, ROS collector, raw-contact collector,
contact analyzer, ContactLatch, collision evaluator, or simulation-control
tool. It does not parse `gz service` or `gz model` output.

## Local, version-matched typed-client capability

| Capability | Local evidence | Result |
| --- | --- | --- |
| Gazebo Transport C++ client | `/opt/ros/jazzy/opt/gz_transport_vendor/lib/pkgconfig/gz-transport13.pc` reports `gz-transport13` `13.5.0`; its headers include `gz/transport/Node.hh` and the library is `libgz-transport13.so.13.5.0`. | CONFIRMED |
| Typed request API | `Node.hh` declares `Node::Request<RequestT, ReplyT>(topic, request, timeout, reply, result)` and `Node::RequestRaw(topic, request_bytes, request_type, response_type, timeout, response_bytes, result)`. | CONFIRMED |
| Required protobuf C++ types | `empty.pb.h` and `scene.pb.h` are installed under `/opt/ros/jazzy/opt/gz_msgs_vendor/include/gz/msgs10/gz/msgs/`. | CONFIRMED |
| Service name and response contract | Gazebo Sim 8 `Server.hh` documents `/world/<world_name>/scene/info` as `(none) → gz::msgs::Scene`; the current world is `world_demo`. | CONFIRMED |
| Service request representation | The installed SceneBroadcaster binary contains an `gz::msgs::Empty → gz::msgs::Scene` service instantiation; `Node::Request` also supplies `msgs::Empty` for its no-input overload. | CONFIRMED |
| Python `gz.transport*` binding | No version-matched Python transport binding was found under the installed Jazzy vendor package or Python site-packages during this static audit. | NOT CONFIRMED — not selected |

### Selected future client

A minimal temporary **C++ helper** is the only locally confirmed client path.
It would link the installed `gz-transport13` and `gz-msgs10` C++ packages and
use their generated protobuf classes. No build or helper source is created in
this phase.

`RequestRaw` is the preferred one-shot call because the installed API
explicitly returns the serialized response protobuf bytes. The helper would:

1. construct `gz::msgs::Empty` and serialize it as the request bytes;
2. pass request and response type names derived from the generated
   `gz::msgs::Empty` and `gz::msgs::Scene` types, not hand-maintained strings;
3. make exactly one `Node::RequestRaw` request to
   `/world/world_demo/scene/info` after typed service discovery; and
4. persist the returned response bytes unchanged, then call
   `gz::msgs::Scene::ParseFromString` on a separate in-memory copy.

This is a typed protobuf transport operation, even though raw bytes are
retained losslessly for audit. It is not generic text parsing and does not call
the `gz` CLI.

## Data contract available in the local protobuf schema

| Hierarchy level | Exact fields available locally | Required exact check | What it proves if present |
| --- | --- | --- | --- |
| Scene | `Scene.model[]` in `scene.proto` | Decode succeeds as `gz::msgs::Scene`. | The response is a typed Scene payload. |
| Model | `Model.name`, `Model.id`, `Model.link[]` in `model.proto` | Exactly one `name == "ROBOT_URDF_final"`. | The named model is represented in this Scene response. |
| Link | `Link.name`, `Link.id`, `Link.collision[]`, `Link.sensor[]` in `link.proto` | Within that model, exactly one `name == "base_link"`. | The named link is represented under the exact model. |
| Sensor | `Sensor.name`, `Sensor.parent`, `Sensor.parent_id`, `Sensor.type`, `Sensor.contact`, and `Sensor.topic` in `sensor.proto` | Within that link, exactly one `name == "s3_d3_base_contact_sensor"`. | The named sensor is represented under the exact link. |
| Contact association | `Sensor.contact.collision_name` in `contactsensor.proto`; `Collision.name` in `collision.proto` | `type == "contact"`, contact field is present, its exact collision name is `s3_d3_base_contact_collision`, and that collision occurs exactly once in the same link's `collision[]`. | The typed scene response carries the requested sensor-to-collision association. |

The source configuration requests `type="contact"`, sensor
`s3_d3_base_contact_sensor`, collision
`s3_d3_base_contact_collision`, and topic `/s3_d3/contact/raw` in
[`ROBOT_URDF_final.gazebo`](../ros2_ws/src/ROBOT_URDF_final_description/urdf/ROBOT_URDF_final.gazebo).
That source literal remains a hypothesis until a future Scene response proves
the relevant typed fields after spawn.

## Future observer behavior

### Read-only sequence

1. Validate the locked world name `world_demo` and world SHA-256
   `1c50f90d151a12559d426796c5d153c829b8777a5b4e8ef94c007a2023f6e271`
   before launching any future measurement process.
2. Launch Gazebo only after those static gates pass. The observer has no ROS
   initialization, bridge, publisher, subscriber, service server, action
   client, or mutation capability.
3. Use the typed Transport `ServiceList`/service-discovery API only to wait for
   the exact service name `/world/world_demo/scene/info`. The future approval
   packet must define any bounded preflight wait as a stop guard; this design
   chooses no timeout value.
4. Issue exactly one `RequestRaw` call with a serialized `gz::msgs::Empty` and
   expected `gz::msgs::Scene` response type. No retry and no second request is
   permitted.
5. Store the raw returned response byte sequence before parsing. Decode only
   from an in-memory copy and validate the hierarchy by exact equality; never
   by substring, prefix, suffix, fuzzy match, or inferred scoped name.
6. Stop only processes created by the future measurement via SIGINT. A future
   approval must treat incomplete shutdown as `SHUTDOWN_INCOMPLETE` and must
   not permit force-kill or automatic retry.

### Deterministic capture outputs

| Output | Content | Deterministic / lossless rule |
| --- | --- | --- |
| `scene_response.pb` | Exact `std::string` response bytes returned by `RequestRaw`. | Lossless binary write; retain SHA-256 in metadata. |
| `scene_summary.json` | Schema version, fixed service/type literals, response SHA-256, exact-match counts, typed IDs/names, sensor type, and association outcome. | Canonical UTF-8 JSON: sorted keys, ordered hierarchy arrays by numeric ID then exact name, compact separators, no wall-clock fields. |
| `request_metadata.json` | Service discovery result, request/result booleans, service/client metadata, steady timestamps, and terminal diagnostic status. | Separate operational metadata; it must not alter `scene_summary.json`. |
| process and shutdown records | Command/process identity, SIGINT result, and exit status for processes created by the future run. | Preserve raw output and exit status; no mutation operation is allowed. |

The raw `scene_response.pb` is evidence of one service response, not a
snapshot receipt, atomic-reset receipt, or proof that Gazebo will expose a raw
contact endpoint.

## Fail-closed states

| Status | Exact condition | Not permitted inference |
| --- | --- | --- |
| `SCENE_SERVICE_UNAVAILABLE` | The typed service-discovery path cannot establish exact availability of `/world/world_demo/scene/info` before the single request. | Sensor absence, endpoint absence, or Gazebo failure cause. |
| `SCENE_REQUEST_INCOMPLETE` | The one permitted typed request is not executed, times out, or returns transport/service result `false`. | Sensor absence or a malformed Scene payload. |
| `SCENE_RESPONSE_UNDECODABLE` | Returned bytes cannot parse as `gz::msgs::Scene`, are structurally invalid for this observer, or contain an ambiguous duplicate at any exact identity level. | Model/link/sensor absence. |
| `SCENE_MODEL_ABSENT` | A valid, decoded Scene contains zero exact `ROBOT_URDF_final` model entries. | Link or sensor absence. |
| `SCENE_LINK_ABSENT` | Exactly one model is present, but its valid typed hierarchy contains zero exact `base_link` entries. | Sensor absence. |
| `SCENE_SENSOR_ABSENT` | Exactly one model and one link are present in a valid decoded hierarchy, but the link contains zero exact `s3_d3_base_contact_sensor` entries. | Collision association absence or raw contact endpoint failure. |
| `SCENE_SENSOR_PRESENT_IDENTITY_ONLY` | Exact one model/link/sensor identity is present, but `Sensor.type`, contact-field presence, `contact.collision_name`, or the same-link exact collision association cannot be proven from the typed response. Record `DIAGNOSTIC_INCOMPLETE_COLLISION_IDENTITY` as the associated reason. | Correct contact semantics, raw contact delivery, collision event, or filter policy. |
| `SCENE_SENSOR_PRESENT` | Exact one model/link/sensor identity is present and the typed response proves `type == "contact"`, the exact `contact.collision_name`, and exactly one matching same-link `Collision.name`. | Contact event, ContactLatch, endpoint advertisement, or collision-policy readiness. |

No `*_ABSENT` state may be emitted after a discovery failure, request failure,
decode failure, malformed hierarchy, or duplicate exact identity. Those cases
remain incomplete/undecodable and fail closed.

### Outer evidence-persistence status

`INVALID_EVIDENCE_PERSISTENCE_FAILURE` is an outer run status, not a new
`SCENE_*` classification. If the helper cannot persist raw response bytes
before parsing, or cannot commit the required operational metadata, it must not
emit or retain an absence/presence claim. The raw response, summary, and
metadata contract is incomplete; a future approval must treat this as a
fail-closed blocker.

## Fixed future run boundary

| Permitted only after separate approval | Forbidden |
| --- | --- |
| Launch Gazebo for the locked `world_demo` revision; temporary C++ typed Scene observer; one typed `Empty → Scene` request; typed service discovery; lossless files; SIGINT-only shutdown. | `/cmd_vel`; pose, reset, pause, step, spawn, delete, or world control; Contact bridge; raw-contact collector; ROS bridge/publisher/service/action; `gz model` output parser; UART, STM32, Pi, motor, or any hardware operation. |

The observer may inspect only the Scene service. It must neither subscribe to
nor bridge `/s3_d3/contact/raw`. Any ROS graph that happens to exist is outside
the observer's data path and is not a substitute for the typed Scene result.

## Non-claims

Even `SCENE_SENSOR_PRESENT` does not prove that:

- `/s3_d3/contact/raw` is advertised or delivers raw Contacts payloads;
- any collision event happened, is classified, or is filtered correctly;
- a ContactLatch, transition/action-interval provenance, reset semantics,
  reward, termination, Gym environment, or training runtime exists; or
- any hardware behavior is ready or authorized.

The observer does not determine why the old contact endpoint was absent. It
only narrows the post-spawn identity layer using typed evidence.

## Conclusion

**READY_FOR_USER_APPROVAL_OF_ONE_TYPED_READ_ONLY_SCENE_OBSERVER_RUN**

The local, version-matched C++ Gazebo Transport and protobuf APIs confirm a
typed, read-only `Empty → Scene` client implementation path. A future
one-request observer run still requires a separate user approval packet and an
approval-bound capacity guard. This document creates neither.
