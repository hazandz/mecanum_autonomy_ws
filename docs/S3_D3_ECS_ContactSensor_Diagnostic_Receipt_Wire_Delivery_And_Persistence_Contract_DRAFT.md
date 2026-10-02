# S3 D3 ECS ContactSensor Diagnostic Receipt: Wire, Delivery, and Persistence Contract

`DEDICATED_WORLD_INTEGRATION_STATICALLY_IMPLEMENTED — RUNTIME NOT APPROVED`

## Scope and authority

This document completes the future receipt contract selected by [S3.3.76](S3_D3_ECS_ContactSensor_Diagnostic_Loading_And_Receipt_Decision_Packet_DRAFT.md). It does not authorize a Gazebo run, transport execution, packet, guard, or runtime evidence. The package and an isolated rendered-world integration are implemented and static-validated offline only.

| Authority | Exact identity / local path | Contract consequence |
| --- | --- | --- |
| Gazebo Sim | [`gz-sim8_8.11.0`](https://github.com/gazebosim/gz-sim/releases/tag/gz-sim8_8.11.0), commit [`1be3cc376fec778cc725b4eeea463245affa56d3`](https://github.com/gazebosim/gz-sim/commit/1be3cc376fec778cc725b4eeea463245affa56d3) | System `Configure` may set up an endpoint; all ECM observation remains in `PostUpdate`. |
| Transport | Local `gz-transport13` `Node.hh` at `/opt/ros/jazzy/opt/gz_transport_vendor/include/gz/transport13/gz/transport/Node.hh` | `Advertise`, `Subscribe`, `Publisher::Publish`, and `Publisher::HasConnections` are the inspected pub/sub API. |
| Existing message schema | Local `gz-msgs10` 10.3.2 `stringmsg.proto` | `gz::msgs::StringMsg` contains only optional header plus opaque string `data`; it is not a typed ECS receipt schema. |
| Protobuf deterministic API | Local protobuf `google/protobuf/io/coded_stream.h` | `CodedOutputStream::SetSerializationDeterministic(true)` is available; ordinary `SerializeToString` is not asserted to be canonical. |
| Prior decisions | [S3.3.75](S3_D3_ECS_ContactSensor_Diagnostic_System_Approval_Spec_DRAFT.md), [S3.3.76](S3_D3_ECS_ContactSensor_Diagnostic_Loading_And_Receipt_Decision_Packet_DRAFT.md), [S3.3.74](S3_D3_ECS_ContactSensor_Component_Inspection_Design_Audit.md), [S3.3.73](S3_D3_SceneBroadcaster_ContactSensor_Component_Serialization_Audit.md), and [S3.3.72 post-run audit](S3_D3_Native_Contact_Endpoint_S3_3_72_Post_Run_Evidence_Audit.md) | Exact ECM data, isolated world-scope System, one diagnostic Transport receipt, collector persistence, and prior evidence-retention limits. |

## A. Receipt wire schema decision

### Candidate comparison

| Option | Type safety / evolution | Raw-byte retention and auditability | Packaging implication | Result |
| --- | --- | --- | --- | --- |
| Existing Gazebo message carrying the whole receipt | No inspected `gz-msgs10` message has fields for run identity, hierarchy counts/IDs, configured target, terminal status, build provenance, and lifecycle timestamps. `Scene` is known insufficient. | It would require overloading unrelated semantics or opaque extensions. | No new proto, but no adequate typed contract. | `NOT_FEASIBLE` |
| `gz::msgs::StringMsg` containing a versioned payload | `StringMsg.data` is untyped opaque text. The inspected API provides no official canonical JSON contract. | Retaining raw bytes is possible, but semantic schema validation and canonical representation would be project-defined text parsing. | No new proto. | `NOT_FEASIBLE` for this evidence contract; opaque JSON is not accepted as a substitute for a typed, versioned receipt. |
| Custom protobuf `EcsContactSensorDiagnosticReceipt` | Exact scalar/enum fields are generated and versioned. Additive field evolution follows protobuf compatibility rules; unknown fields are retained only as raw evidence, not silently interpreted. | Collector retains raw received frame bytes, parses a typed message, and may write a separate explicitly deterministic normalized protobuf representation. | A small diagnostic-only proto and generated library must be owned, built, and hash-bound with plugin/collector later. | **`FEASIBLE — SELECTED`** |

### Selected wire type

The future wire type is one new, diagnostic-only protobuf message named:

```text
s3_d3.ecs_contact.EcsContactSensorDiagnosticReceipt
schema_version = 1
```

The package/proto ownership is implemented offline only; no runtime loading or execution authority is granted by this document. The topic literal is intentionally a required placeholder:

```text
REQUIRED_USER_DECISION_DIAGNOSTIC_RECEIPT_TOPIC
```

It must be a dedicated Gazebo Transport **topic**, namespace-bound in a later packet, and may not be a ROS topic, raw Contacts topic, service/action endpoint, command/control topic, or bridge endpoint.

### Receipt schema v1

| Field | Protobuf type | Requirement |
| --- | --- | --- |
| `schema_version` | `uint32` | Required; exact `1`. |
| `run_id` | `string` | Required opaque run identity; exact collector expectation; no slash/traversal semantics. |
| `terminal_status` | enum | Exactly one status from the allowlist below. |
| `reason_code` | enum | Deterministic reason matching the status; no free-form log text as evidence. |
| `world_name`, `model_name`, `link_name`, `sensor_name` | `string` | Exact queried values or empty only when the corresponding upstream entity was unconfirmed. |
| `world_id`, `model_id`, `link_id`, `sensor_id`, `collision_id` | `uint64` plus explicit `*_present` booleans | Entity identity; zero is never used as an implicit missing sentinel. |
| `model_parent_id`, `link_parent_id`, `sensor_parent_id`, `collision_parent_id` | `uint64` plus explicit presence booleans | Copied parent provenance. |
| `configured_collision_target`, `collision_name` | `string` | Target is non-empty only when parsed; collision name only when collision entity is observed. |
| `model_exact_count`, `link_exact_count`, `sensor_exact_count`, `collision_exact_count` | `uint32` | Counts from exact equality/immediate-child queries. |
| `hook_name` | `string` | Required literal `PostUpdate`. |
| `first_postupdate_sim_time_ns`, `terminal_sim_time_ns` | `int64` | Simulation-time provenance, with explicit presence booleans. |
| `first_postupdate_steady_time_ns`, `terminal_steady_time_ns` | `int64` | Process-monotonic provenance, with explicit presence booleans. |
| `system_wait_timeout_sim_time_ns` | `int64` | Approved future System waiting literal; exact copied value. |
| `plugin_source_sha256`, `plugin_binary_sha256`, `base_world_template_sha256`, `native_model_sha256` | `string` | 64-lowercase-hex SHA-256 values required by the later packet/guard. `base_world_template_sha256` is the immutable pre-render template authority, never a digest of the generated world containing it. |
| `sealed_once` | `bool` | Required true. |

No map field, raw ECM pointer, SDF pointer/element, mutable component reference, `ContactSensorData`, raw Contacts payload, ROS/TF/PPO/ground-truth data, or command/control field is permitted.

### Terminal-status allowlist

```text
ECS_MODEL_UNCONFIRMED
ECS_LINK_UNCONFIRMED
ECS_SENSOR_UNCONFIRMED
ECS_CONTACT_COMPONENT_MISSING
ECS_CONTACT_CONFIGURATION_INCOMPLETE
ECS_TARGET_COLLISION_CHILD_UNCONFIRMED
ECS_SENSOR_TARGET_COLLISION_CHILD_OBSERVED
```

The last status is the only positive status. It proves configuration plus exact immediate collision-child identity in one `PostUpdate` snapshot. It does not prove ContactSystemData, raw Contacts endpoint advertisement, a collision event, ContactLatch, reward, termination, Nav2/training, or hardware readiness.

## B. One-shot delivery ordering and race closure

`Subscribe` returning true confirms that the collector registered a local subscription. It does **not** itself prove that the future System publisher exists or that an interprocess delivery path is connected. The local Transport 13 API explicitly provides `Publisher::HasConnections()` for the publisher-side condition that subscribers have connected. This is the only connection-readiness fact used here.

`Configure` may create/advertise the receipt publisher because endpoint setup has no ECM query and does not publish evidence. All model/link/sensor/contact/collision ECM reads remain exclusively in `PostUpdate` as required by S3.3.75.

### Future-only ordered flow

```text
1. Supervisor allocates one run_id and creates a non-symlink durable run directory.
2. Collector starts, validates its immutable expected run_id/schema/topic, and Subscribe() succeeds.
3. Dedicated diagnostic world launches; System Configure advertises the diagnostic receipt topic only.
4. Collector readiness remains UNCONFIRMED until System Publisher::HasConnections() is true.
5. Supervisor performs one direct native create under its separately approved authority.
6. System first PostUpdate records its timing baseline; it evaluates only exact ECM queries.
7. System seals one immutable terminal snapshot.
8. If HasConnections() is true before the approved delivery-wait deadline, System Publish() is called exactly once.
9. Collector receives one raw transport payload, validates it, atomically persists its evidence bundle, then seals.
10. Supervisor records the collector outcome and performs approved shutdown/guard consumption.
```

No ready-handshake topic, service, action, or control channel is selected. The publisher-side `HasConnections()` gate avoids treating collector process startup or a successful `Subscribe()` call as a delivery guarantee.

| Condition | Required fail-closed behavior |
| --- | --- |
| Collector `Subscribe()` fails | No native create; outer pre-observation failure; no System receipt expected. |
| System publisher invalid / cannot advertise | No ECM receipt publish; collector records no receipt only after its deadline; outer delivery failure, not an ECS status. |
| Terminal snapshot seals while `HasConnections()` is false | The sealed snapshot remains unchanged; System waits only for connection until its later approved delivery-wait deadline and performs no second ECM snapshot. |
| No connection by System delivery-wait deadline | System performs zero receipt publishes and seals delivery failure internally; collector must record an outer no-receipt failure after its own deadline. No retry/new run. |
| Valid connection | Exactly one `Publish()` call, then System never publishes again. |
| Duplicate receipt | Collector persists the first valid committed receipt only; any later receipt is a fail-closed duplicate-delivery violation, not a second diagnostic result. |
| Wrong run ID, schema version, topic, or build provenance | Collector rejects before durable success commit; outer integrity failure only. |
| Stale timing/provenance | Collector rejects before durable success commit; it must not reclassify the embedded ECS status. |
| Collector no-receipt deadline | Collector commits an outer `ECS_RECEIPT_UNCONFIRMED`/persistence record only; it must not invent a terminal ECM status. |

## C. Timeout registry and semantics

No numeric literal is selected here. Each item below is `REQUIRED_USER_DECISION` and must be bound by a future packet/guard with its clock domain and unit.

| Literal placeholder | Owner | Clock | Semantics |
| --- | --- | --- |
| `SYSTEM_WAIT_TIMEOUT_SIM_TIME_NS` | System | Simulation time | Begins at the first `PostUpdate`; bounds `WAITING_FOR_TARGET` evaluation and produces one allowlisted unconfirmed terminal status. |
| `SYSTEM_DELIVERY_WAIT_TIMEOUT_STEADY_NS` | System | Steady clock | Bounds post-seal waiting for `HasConnections()`. It governs delivery only and cannot change the sealed ECS status. |
| `COLLECTOR_RECEIPT_WAIT_TIMEOUT_STEADY_NS` | Collector | Steady clock | Bounds waiting for one valid transport payload; expiration is an outer receipt/persistence failure. |
| `COLLECTOR_PERSIST_TIMEOUT_STEADY_NS` | Collector | Steady clock | Bounds local atomic persistence; expiration is an outer persistence failure. |

System waiting timeout uses simulation time only. If simulation time pauses, does not advance, regresses, or `PostUpdate` is not invoked, it does not synthesize a wall-clock terminal status. The collector's independent steady-clock deadline eventually records no receipt as an outer failure. A simulation-time regression must be recorded in receipt provenance if a receipt can still be produced; it must never be silently treated as elapsed wait time. No wall-clock fallback is added to the System.

## D. Integrity, raw evidence, and atomic persistence

### Non-self-referential hash model

The receipt payload contains **no hash of its own complete bytes**. `base_world_template_sha256` is explicitly the SHA-256 of the immutable base template before per-run rendering; the rendered-world SHA, when recorded, belongs only in external run metadata. In particular, it does not carry `receipt_sha256`, because that would be self-referential. Instead:

1. The System constructs and publishes the typed receipt payload without a payload-byte digest field.
2. The collector uses Transport 13 `Node::SubscribeRaw` with the exact protobuf descriptor full name; its callback receives `(const char *, size_t, MessageInfo)`, documented locally as serialized protobuf bytes. It copies exactly those `size` bytes before parsing, checks `MessageInfo::Topic()` and `MessageInfo::Type()` against the immutable expected topic/type, and preserves that byte sequence as the raw artifact.
3. The collector computes `raw_transport_payload_sha256` over those raw bytes and places that digest in separate collector metadata.
4. The collector parses the raw bytes as schema v1 and validates run ID, status, counts, fields, and provenance.
5. The collector writes a separately normalized protobuf representation only by using an explicitly deterministic protobuf serialization path (`CodedOutputStream::SetSerializationDeterministic(true)`). It is labelled normalized and is never substituted for the raw transport payload.

This contract makes raw evidence integrity independent of a self-referential field and does not claim default protobuf or JSON serialization is canonical.

### Required durable bundle

| Artifact | Required condition |
| --- | --- |
| `ecs_contact_receipt.raw.pb` | Required for every accepted receipt; exact bytes captured by collector. |
| `ecs_contact_receipt.raw.sha256` | Required with raw bytes; digest over exactly that file's bytes. |
| `ecs_contact_receipt.normalized.pb` | Required with accepted receipt; deterministic reserialization of successfully parsed v1 message. |
| `ecs_contact_receipt.json` | Required with accepted receipt; deterministic, schema-validated human-readable projection. It is not the raw evidence and carries no authority beyond matching normalized fields. |
| `ecs_contact_receipt_collector_metadata.json` | Required for every collector terminal path; expected run/schema/topic/build identities, receive/provenance timings, raw digest when bytes exist, and outer persistence result. |
| `ecs_contact_receipt_failure.json` | Required instead of the three receipt representations when no receipt is accepted; must identify only outer delivery/integrity/persistence failure. |

All durable paths must be inside the pre-created run directory and have no symlink in any path component. The collector writes the complete five-file success set into one unique, exclusive staging directory on the same filesystem; each file is `O_EXCL`/`O_NOFOLLOW`, write-all handles `EINTR`, and file plus staging-directory `fsync`/single-close must succeed. It commits staging only with Linux `renameat2(..., RENAME_NOREPLACE)` into `ecs_contact_receipt_bundle/`; unsupported no-replace semantics, a collision, or any write/sync/close/commit failure is fail-closed and cleans staging. No check-then-rename fallback is permitted. A separately named failure record is outer persistence evidence, never an ECS terminal status.

An accepted receipt is a persisted success only when `raw.pb`, raw SHA-256, normalized protobuf, JSON projection, metadata, and matching `run_id` all exist and validate together. A partial write, hash mismatch, parser failure, output symlink, target already existing, duplicate, or commit failure is an outer `INVALID_EVIDENCE_PERSISTENCE_FAILURE`; it does not rewrite the embedded ECS terminal status and does not authorize retry.

## Future-only delivery/persistence flow

```text
collector parsed config success (before Node construction)
  -> SubscribeRaw exact topic + exact protobuf full name
  -> System publisher advertised in Configure
  -> Publisher HasConnections true
  -> one direct native create and first PostUpdate
  -> one sealed ECS snapshot
  -> exactly one transport publish
  -> collector raw-byte capture
  -> raw SHA-256 metadata (outside payload)
  -> parse + validate + deterministic normalization
  -> atomic no-overwrite durable commit
  -> collector seal
```

This flow is future-only. It does not create an execution authority or imply that any receipt/topic exists today.

## Required user approvals before implementation

1. Custom protobuf package ownership, schema v1, and exact diagnostic receipt topic literal.
2. All four timeout literals in the registry, including units and clock-domain semantics.
3. Read-only collector process ownership, exact receipt-wait deadline, and failure-status handling.
4. Atomic persistence contract, durable artifact layout, and source/plugin/collector hash binding.
5. Dedicated world-scope loading surface and isolated diagnostic package/loading plan selected in S3.3.76.
6. Implementation plus offline validation only; later, a new hash-locked runtime packet, capacity-one guard, and one separately approved run.


## S3.3.80 static loading integration

The local SDFormat 1.11 authority [`plugin.sdf`](/opt/ros/jazzy/opt/sdformat_vendor/share/sdformat14/1.11/plugin.sdf) permits a plugin as a child of `world`, requires `filename`, and states that a non-absolute library filename is searched in configuration paths. The installed Gazebo Sim 8 `touch_plugin.sdf` example uses world-scope `filename` / `name` pairs for Physics and Contact; installed `ros_gz_sim/launch/gz_sim.launch.py` composes `GZ_SIM_SYSTEM_PLUGIN_PATH` and `GZ_SIM_RESOURCE_PATH` from inherited values, `LD_LIBRARY_PATH`, and package exports.

S3.3.80 therefore adds only a separate template named `world_demo`, with Physics, exactly one Contact System, and exactly one `S3D3EcsContactSensorDiagnosticSystem`; it contains no model or include. Its companion launch requires a caller-supplied rendered world path, adds the installed diagnostic package `lib` directory to the official system-plugin search variable, preserves inherited paths, and includes the official `gz_sim.launch.py`. It creates no robot, ROS node, bridge, TF, command, control, or runtime authority. `base_world_template_sha256` is the SHA-256 of this immutable template before rendering. Any rendered-world digest is external manifest metadata only.

## Conclusion

`DEDICATED_WORLD_INTEGRATION_STATICALLY_IMPLEMENTED — RUNTIME NOT APPROVED`

S3.3.80 adds a caller-rendered, robot-free `world_demo` template with one world-scope diagnostic System and an offline renderer. The wire type, publisher-side delivery readiness, non-self-referential raw digest model, terminal delivery behavior, and atomic evidence requirements are no longer ambiguous at design level. Numeric/topic/package decisions remain explicit user approvals listed above; no default may be chosen during implementation.

## Non-claims and non-mutation confirmation

This contract does not prove ContactSystemData, a raw Contacts endpoint, collision event, ContactLatch, reward, termination, Nav2/training, or hardware readiness. No runtime operation, source modification, raw-artifact mutation, guard operation, packet/guard creation, or hardware operation occurred.

## S3.3.82 supervisor handoff boundary

`OFFLINE_SUPERVISOR_COLLECTOR_INTEGRATION_IMPLEMENTED — RUNTIME NOT APPROVED`

The future supervisor renders through the installed C++ renderer before it starts any collector, launcher, or create child. It records `base_world_template_sha256` and the rendered-world SHA only in the durable manifest; the latter is never written back into the rendered SDF. It starts exactly one collector and requires its explicit readiness before the dedicated world launch and the one direct native create. The collector remains the sole future receipt persistence owner. This integration does not create execution authority and no runtime child was started while validating it.

## S3.3.83 renderer-result provenance binding

`RENDERER_RESULT_RECEIPT_IMPLEMENTED_OFFLINE — RUNTIME NOT APPROVED`

The renderer now requires an absolute `--result` path in the same caller-owned run directory as the rendered SDF. On a successful filesystem-only render it commits `renderer_result.json` with schema `s3_d3_renderer_result/v1`, the exact run ID, canonical absolute template and rendered-world paths, immutable base-template SHA-256, and rendered-world SHA-256. The receipt is exclusive/no-overwrite and atomically committed after the rendered SDF; no renderer stdout or stderr is evidence.

The supervisor's injected boundary now accepts a render only after a strict receipt has the exact plan run ID, canonical plan paths, base-template SHA, and a rendered-world SHA that matches a fresh file hash. Missing, malformed, stale, path-drifted, or hash-drifted result evidence produces `INVALID_RENDER_RESULT_PROVENANCE` before manifest, collector, launch, or create. Renderer CLI parsing rejects unknown/duplicate/missing fields, relative or traversal paths, invalid SHA/run ID, and signed, zero, overflow, or trailing-garbage timeouts.
