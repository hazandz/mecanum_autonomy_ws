# S3 D3 — Typed Scene Observer Run Approval Packet

**Status: READY_FOR_REPLACEMENT_RUNTIME_PACKET_AND_NEW_GUARD — NO EXECUTION AUTHORITY**

## Authority, purpose, and immutable literals

This packet requests approval for exactly one future, typed, read-only Gazebo
Scene-service observer run. It creates no execution authority, capacity guard,
helper, binary, bridge, or runtime process in its present draft state.

| Authority item | Locked literal |
| --- | --- |
| Gazebo world | `world_demo` |
| Post-edit world SHA-256 | `1c50f90d151a12559d426796c5d153c829b8777a5b4e8ef94c007a2023f6e271` |
| Scene service | `/world/world_demo/scene/info` |
| Typed request / response | `gz::msgs::Empty → gz::msgs::Scene` |
| Required exact identity chain | `ROBOT_URDF_final → base_link → s3_d3_base_contact_sensor` |
| Expected collision literal | `s3_d3_base_contact_collision` |

The sole diagnostic question is whether one typed `gz::msgs::Scene` response,
received after spawn, represents the locked model, link, and sensor identities.
This question is narrower than contact-topic advertisement and is not a
collision-event test.

The basis for the one-request observer design is the [typed Scene observer
capture design](S3_D3_Typed_Scene_Service_Observer_Capture_Design_DRAFT.md)
and the [existing machine-readable observability audit](S3_D3_Existing_Gazebo_Spawn_Observability_Feasibility_Audit_DRAFT.md).
The earlier [contact endpoint root-cause audit](S3_D3_Contact_Endpoint_Root_Cause_Audit_DRAFT.md)
remains the authority for the fact that endpoint absence was observed before
bridge/collector startup; it is not evidence of sensor absence.

## Generated-protobuf semantics: verified constraints

The following findings come from locally installed generated C++ headers under
`/opt/ros/jazzy/opt/gz_msgs_vendor/include/gz/msgs10/gz/msgs/details/`, not
from SDF text or runtime behavior.

| Required question | Generated-header evidence | Required future helper rule |
| --- | --- | --- |
| Does `Sensor.type` have a Contact enum constant? | `sensor.proto` and generated `sensor.pb.h` declare `type` as `std::string`. There is **no** `SensorType` enum and no C++/protobuf `CONTACT` constant in `gz::msgs::Sensor`. | Do not compare `sensor.type()` to the literal string `"contact"`; no enum-based type comparison is available in this installed schema. |
| Is contact submessage presence observable? | Generated `Sensor::has_contact() const` tests whether the `ContactSensor` message pointer is non-null; `contact()` returns the submessage. | Use `sensor.has_contact()` only as field-presence evidence. It is not elevated into an unverified enum-type equivalence. |
| Is `contact.collision_name` presence observable? | Generated `ContactSensor::collision_name()` returns a proto3 string scalar. The generated header has no `has_collision_name()`. | Require a non-empty exact value equal to `s3_d3_base_contact_collision`. Do not claim wire-level presence separately from that exact non-default value. |
| Is same-link collision membership observable? | Generated `Link::collision_size()` and indexed/repeated `Link::collision()` access a repeated `Collision` field; generated `Collision::name()` provides each name. | Require exactly one same-link `Collision.name() == s3_d3_base_contact_collision`; zero or more than one fails closed. |
| Is sensor membership observable? | Generated `Link::sensor_size()` and repeated `Link::sensor()` provide typed sensor entries. | Require exactly one `Sensor.name() == s3_d3_base_contact_sensor`; no substring, scoped-name inference, prefix, or suffix matching. |

### Consequence for full contact-sensor classification

The requested prohibition on comparing the type string `"contact"` is
compatible with the generated headers, but the required enum alternative does
not exist. Therefore, this packet **does not authorize** the terminal state
`SCENE_SENSOR_PRESENT` as a full type-confirmed result. If exact
model/link/sensor identity, `has_contact()`, and the exact collision association
are visible, the only permitted positive result is:

```text
SCENE_SENSOR_PRESENT_IDENTITY_ONLY
associated reason: DIAGNOSTIC_INCOMPLETE_CONTACT_TYPE_ENUM
```

`DIAGNOSTIC_INCOMPLETE_COLLISION_IDENTITY` must additionally be recorded if
`has_contact()`, non-empty exact `collision_name()`, or exactly-one same-link
collision membership cannot be proven. This preserves fail-closed behavior and
does not reinterpret `has_contact()` as a verified replacement for a missing
Contact type enum.

## Proposed one-run procedure — requires approval

After user approval only, a temporary C++ helper may be built and run outside
the robot packages. The helper receives the locked service, world, and
identity literals above and emits only typed diagnostic files.

1. Verify the world name and SHA-256 before launch.
2. Launch only the locked Gazebo revision.
3. Use only the installed `gz-transport13` and `gz-msgs10` C++ APIs. The
   helper must receive `--preflight-wait-ms`, `--timeout-ms`, and `--output-dir`
   explicitly, create its output directory before metadata, poll typed
   `Node::ServiceList(std::vector<std::string> &) const` for exactly one service
   equality match, and only then send exactly one `Node::RequestRaw` request.
   It serializes a
   `gz::msgs::Empty`, derives protobuf type names from generated message types,
   requests a `gz::msgs::Scene`, and never invokes `gz service` or `gz model`.
4. Store the raw returned response bytes as `scene_response.pb`; decode a
   separate in-memory copy as `gz::msgs::Scene`; validate exact hierarchy
   counts and the generated-header field rules above.
5. Write deterministic `scene_summary.json`, `request_metadata.json`, and
   process/shutdown records. The summary must include response SHA-256,
   literal inputs, exact-match counts, typed IDs/names, header-semantic checks,
   terminal status, and associated incomplete reasons.
6. Do not retry, issue a second request, or use any output parser for
   `gz model`.

The replacement runtime packet and new guard must bind the already decided
`preflight_wait_ms=90000`, `request_timeout_ms=5000`, and polling interval
`10 ms`. These are stop-guard/runtime literals, not settle, freshness, reset,
or retry policy.

## Terminal status contract

| Terminal status | Strict condition | Explicitly not proven |
| --- | --- | --- |
| `SCENE_SERVICE_UNAVAILABLE` | Exact typed service discovery cannot establish `/world/world_demo/scene/info` before the sole request. | Sensor absence, endpoint absence, or Gazebo failure cause. |
| `SCENE_REQUEST_INCOMPLETE` | The sole `RequestRaw` call cannot execute, times out, or reports a false transport/service result. | Any hierarchy absence or malformed Scene. |
| `SCENE_RESPONSE_UNDECODABLE` | Returned bytes cannot decode as `gz::msgs::Scene`, or the decoded hierarchy is ambiguous/invalid for exact matching. | Model, link, or sensor absence. |
| `SCENE_MODEL_NOT_OBSERVED_AFTER_DELAY` | **Candidate A only:** after approved create exit-success convention and delay, a valid decoded Scene has zero exact `Model.name() == "ROBOT_URDF_final"` entries. | Actual model absence or spawn failure. |
| `SCENE_LINK_NOT_OBSERVED_AFTER_DELAY` | **Candidate A only:** exactly one model exists, but the response has zero exact `Link.name() == "base_link"`. | Actual link absence. |
| `SCENE_SENSOR_NOT_OBSERVED_AFTER_DELAY` | **Candidate A only:** exactly one model/link exists, but the response has zero exact sensor identity. | Actual sensor absence, conversion failure, or endpoint failure. |
| `SCENE_*_ABSENT` | Reserved only for future approved Candidate B with a proven machine-readable bootstrap receipt. | Any Candidate A conclusion. |
| `SCENE_SENSOR_PRESENT_IDENTITY_ONLY` | Exactly one model/link/sensor identity exists, while complete contact type proof is unavailable because the local generated schema exposes no Contact enum; or collision association cannot be fully proven. | Full contact-type confirmation, raw endpoint, contact event, or collision policy. |
| `SCENE_SENSOR_PRESENT` | **Not an allowed successful outcome for this run.** It requires a locally verified enum-based Contact type comparison that the installed `gz-msgs10` schema does not provide. | No implementation may emit this state under this packet. |

Duplicate exact model, link, sensor, or expected collision matches are
`SCENE_RESPONSE_UNDECODABLE`, not a positive or absent result. No absent status
may be emitted after discovery, request, decode, or hierarchy-validation
failure.

`INVALID_EVIDENCE_PERSISTENCE_FAILURE` is a separate outer run status. If raw
response bytes cannot be written before parse, or the required summary or
metadata cannot be committed, the run must not retain a scene absence/presence
claim. It does not alter any locked `SCENE_*` terminal semantic.

The helper's fixed 10 ms service-list polling interval is only an implementation
detail to prevent busy-spin; it does not select either user-approved timeout.
`request_metadata.json` must keep `preflight_start_steady_ns` and
`preflight_end_steady_ns` separate from request timestamps. A
`SCENE_SERVICE_UNAVAILABLE` record has request timestamps `null`; request and
classification branches carry both timestamp groups.

## Strict operational boundary

| Permitted only in a separately approved execution | Prohibited absolutely |
| --- | --- |
| **Bootstrap only:** dedicated launch starts locked Gazebo; `robot_state_publisher` provides `/robot_description`; one initial `ros_gz_sim create` creates `ROBOT_URDF_final`. **Capture only:** bootstrapped Gazebo; one temporary C++ helper; typed `ServiceList`; one `Empty → Scene` `RequestRaw`; lossless files; SIGINT-only shutdown for processes created by the run. | `ros_gz_bridge`; `parameter_bridge`; `/cmd_vel`; static TF; raw-contact bridge/collector; any ROS publisher/subscriber/service/action **other than the locked bootstrap description provider**; teleop; Nav2; PPO; Gymnasium; SB3; every capture-time pose/reset/spawn/delete/pause/step/world-control action; retry; `gz model` parser; UART, STM32, Pi, motor, firmware, or hardware operation. |

Shutdown may use only SIGINT for process groups created by the run. There is no
SIGTERM, SIGKILL, force-kill, or automatic retry path. Any incomplete shutdown
is `SHUTDOWN_INCOMPLETE`, retained as a blocker, and prevents another run until
a separate user/operator decision.

## Replacement runtime packet requirements

| Required decision | Why it remains open |
| --- | --- |
| Create one replacement runtime packet | It must explicitly grant one execution authority; this historical packet does not. |
| Bind locked artifacts and literals | Bind dedicated-launch hash, helper hash, world revision, service/message types, hierarchy, and collision literal into a new guard. |
| Bind already decided timing | `preflight_wait_ms=90000`, `request_timeout_ms=5000`, polling `10 ms`. |
| Preserve enum limitation | `SCENE_SENSOR_PRESENT` remains unavailable; the maximum positive outcome is `SCENE_SENSOR_PRESENT_IDENTITY_ONLY`. |
| Bind capacity and shutdown | Capacity `1`, no retry, SIGINT-only, and consumption on every terminal result. |


## S3.3.37/S3.3.40 bootstrap-readiness record

S3.3.40 selected and implemented Candidate A only for offline validation. See the
[spawn-completion and Scene-readiness design](S3_D3_Spawn_Completion_And_Scene_Readiness_Design_DRAFT.md) and the
[spawn-readiness user decision packet](S3_D3_Spawn_Readiness_User_Decision_Packet_DRAFT.md). The dedicated launch now has no `TimerAction` or launch-owned create. The future supervisor-owned one-create contract uses `create_timeout_ms=90000`, `post_create_delay_ms=2000`, and exit zero only as an operational convention. It does not prove that `ROBOT_URDF_final` exists in the Scene response. `SCENE_BOOTSTRAP_UNCONFIRMED` must prevent the sole `RequestRaw` whenever the contract is not fulfilled.


## S3.3.40 create-outcome ownership implementation record

The [bootstrap create-outcome ownership design](S3_D3_Bootstrap_Create_Outcome_Ownership_Design_DRAFT.md) now records `SUPERVISOR_OWNED_CREATE_V1` as implemented offline only. The dedicated launch has zero create Nodes; a future supervisor directly owns the one allowlisted create child and records opaque process metadata without log parsing. This resolves no runtime authority: a replacement runtime packet and a new guard are still required before launch, create, helper, or request execution.

## S3.3.41 executable-integrity and timeout-shutdown gate

The supervisor now performs an offline-tested, pre-spawn integrity check for the
exact allowlisted create executable: regular-file requirement, valid lowercase
plan SHA-256, and fresh equal SHA-256 immediately before spawn. The historical
S3.3.31 guard/context is not imported or reachable from this supervisor.

The user has selected `create_shutdown_grace_ms=5000` only for this future
runtime boundary. The offline-tested timeout contract permits only SIGINT to the
direct child process group, then waits that exact grace. A clean exit retains
`SCENE_CREATE_OUTCOME_UNCONFIRMED` / `SCENE_BOOTSTRAP_UNCONFIRMED`; a live child
becomes outer `SHUTDOWN_INCOMPLETE`. Neither permits helper execution,
`RequestRaw`, retry, second create, SIGTERM, or SIGKILL. This cleanup outcome is
not a spawn receipt.

A replacement runtime packet and a new capacity-one guard remain required; no
execution authority has been created.

## S3.3.43 future runtime-adapter record

The supervisor now contains a separately test-injected `RuntimeCreateAdapter`
for future hash binding. It permits only the exact create executable and locked
argv, uses `Popen` with `shell=False` and a new session, exposes only the
minimal `CreateProcess` interface, and targets SIGINT only at its owned child
process group. Its streams are discarded and never parsed. The adapter has no
helper, `RequestRaw`, bridge, command/control, retry, or force-kill path.

`--execute` remains an unconditional `NO_EXECUTION_AUTHORITY` failure before
any `Popen`, guard acquisition, launch, or runtime I/O. A replacement runtime
packet and new capacity-one guard must bind the SHA-256 of this supervisor
adapter source, the dedicated launch, helper, exact create executable, world,
all typed-scene literals, `create_timeout_ms=90000`,
`post_create_delay_ms=2000`, `create_shutdown_grace_ms=5000`, and the one-create
/ one-request rule.

## Non-claims

Even `SCENE_SENSOR_PRESENT_IDENTITY_ONLY` would not prove a raw contact topic,
raw Contacts delivery, a collision event, ContactLatch behavior, collision
filter policy, action/transition provenance, reward, termination, Gym,
training, or hardware readiness. It also does not prove atomic reset,
settlement, a scenario contract, or any policy-observation path.


## S3.3.34 dedicated-launch implementation record — completed and static-validated

**OPTION 1 APPROVED FOR DEDICATED-LAUNCH IMPLEMENTATION ONLY — RUNTIME NOT APPROVED**

The narrowly approved bootstrap exception allows `robot_state_publisher` solely
to provide `/robot_description` to one initial `ros_gz_sim create` for
`ROBOT_URDF_final`. The new dedicated launch is
[`typed_scene_observer.launch.py`](../ros2_ws/src/ROBOT_URDF_final_description/launch/typed_scene_observer.launch.py). It omits every `ros_gz_bridge`,
`parameter_bridge`, `/cmd_vel` mapping, static TF publisher, raw-contact bridge,
and control node.

This resolves the broad-launch bridge conflict at implementation scope only. It
does not approve a runtime Typed Scene run, helper execution, a new guard, or
reuse of the obsolete S3.3.31 guard. The one initial spawn is the sole bootstrap
mutation; all capture-time spawn/delete/pose/reset/pause/step/world-control
operations remain forbidden. A static review and a new packet/guard are required
before any one-shot runtime run.

## S3.3.32 historical broad-launch conflict — superseded for the typed Scene diagnostic

The following is retained as historical audit evidence only. Static audit of the former broad launch path that loaded
`tugbot_depot.sdf` and spawns `ROBOT_URDF_final` found
`ros2_ws/src/ROBOT_URDF_final_description/launch/gazebo.launch.py`. It starts
`ros_gz_bridge parameter_bridge` and includes the bare mapping
`/cmd_vel@geometry_msgs/msg/Twist@gz.msgs.Twist`, in addition to ROS nodes and
the robot spawn operation. The supervisor would not create a separate bridge,
but this existing launcher-created bridge and command path conflict with this
packet's strict “no ROS bridge” and no-command boundary.

The dedicated launch now resolves this specific conflict by excluding the broad launch from the typed Scene route. The S3.3.31 live guard remains byte-unchanged and obsolete because its packet-hash binding does not match the reconciled packet; it must fail closed. No authority to execute has been restored. A replacement runtime packet and new guard are still required.

## S3.3.31 guard-preparation decision record

**USER_APPROVED_FOR_GUARD_PREPARATION_ONLY**

This decision authorizes offline preparation of one approval-bound guard and
supervisor only. It does not authorize Gazebo, ROS, `gz`, the helper runtime,
or any service request. The immutable execution inputs, if a separate later
execution approval is granted, are:

| Input | Approved value |
| --- | --- |
| `preflight_wait_ms` | `90000` — mandatory replacement packet/guard literal |
| `request_timeout_ms` | `5000` — mandatory replacement packet/guard literal |
| `polling_interval_ms` | `10` — mandatory implementation-detail literal |
| Capacity | `1` — mandatory replacement guard literal |
| Shutdown | `SIGINT-only` — mandatory replacement packet/guard literal |

The guard must bind this packet after this decision record, the helper source,
world and all typed-scene literals. Its required initial state is
`authorized_not_consumed`; this document is not a completed-run record.

## Packet conclusion

**READY_FOR_REPLACEMENT_RUNTIME_PACKET_AND_NEW_GUARD — NO EXECUTION AUTHORITY**

The broad launch is excluded from the typed Scene diagnostic route. No execution authority exists under this historical packet: a replacement runtime packet and a new capacity-one guard must bind the static-validated dedicated launch, the helper, world revision, literals, and approved timing. This packet makes no runtime or hardware claim.

## S3.3.44 supersession record

This historical/design packet is **obsolete as runtime authority**. The pending
[S3.3.44 replacement runtime packet](S3_D3_Typed_Scene_Observer_Replacement_Runtime_Run_Approval_Packet_DRAFT.md) carries a new approval ID and fresh hash/literal bindings. This statement does not alter any historical or consumed authority record.
