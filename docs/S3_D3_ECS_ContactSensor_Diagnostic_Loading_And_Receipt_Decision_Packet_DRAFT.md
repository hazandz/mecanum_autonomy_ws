# S3 D3 ECS ContactSensor Diagnostic Loading and Receipt Decision Packet

`DRAFT — DECISION ONLY, IMPLEMENTATION AND RUNTIME NOT APPROVED`

## Decision scope

This document chooses the future *categories* of loading surface, receipt mechanism, and timeout ownership for the minimal read-only ECS ContactSensor diagnostic described in [S3.3.75](S3_D3_ECS_ContactSensor_Diagnostic_System_Approval_Spec_DRAFT.md). It creates no code, package, plugin, SDF/world/launch change, collector, packet, guard, artifact, or run.

It does not revise the native SDF twin, the working URDF/Xacro → ROS 2 → Nav2 route, the consumed S3.3.72 record, or any non-claim. S3.3.72 is consumed and cannot be retried.

## Authority

| Authority | Locked evidence | Relevance |
| --- | --- | --- |
| Gazebo Sim | [`gz-sim8_8.11.0`](https://github.com/gazebosim/gz-sim/releases/tag/gz-sim8_8.11.0), commit [`1be3cc376fec778cc725b4eeea463245affa56d3`](https://github.com/gazebosim/gz-sim/commit/1be3cc376fec778cc725b4eeea463245affa56d3) | Official System lifecycle, world/model plugin scope, ECM visibility, and Transport integration boundary. |
| Local Gazebo Sim 8 / Transport 13 headers | `/opt/ros/jazzy/opt/gz_sim_vendor/include/gz/sim8/gz/sim/{System,EntityComponentManager}.hh`; `/opt/ros/jazzy/opt/gz_transport_vendor/include/gz/transport13/gz/transport/Node.hh` | `PostUpdate(const EntityComponentManager &)`, exact ECM queries, and one-way topic publication/subscription API. |
| Local SDFormat 1.11 | `/opt/ros/jazzy/opt/sdformat_vendor/share/sdformat14/1.11/{world,model,plugin}.sdf` | SDF world/model plugin placement rules. |
| Prior D3 authority | [S3.3.73](S3_D3_SceneBroadcaster_ContactSensor_Component_Serialization_Audit.md), [S3.3.74](S3_D3_ECS_ContactSensor_Component_Inspection_Design_Audit.md), [S3.3.75](S3_D3_ECS_ContactSensor_Diagnostic_System_Approval_Spec_DRAFT.md), [S3.3.72 post-run audit](S3_D3_Native_Contact_Endpoint_S3_3_72_Post_Run_Evidence_Audit.md), and [native load/spawn route audit](S3_D3_Native_SDF_Load_Spawn_Route_Feasibility_Audit_DRAFT.md) | Native dedicated route, SceneBroadcaster limitation, exact ECM contract, and durable-evidence failure history. |

The official Gazebo contact example proves that a system plugin can be declared under a world and the Contact system is a world-scope system. The future diagnostic is not the Contact system and must not publish `gz::msgs::Contacts` or attach a raw-contact bridge.

## A. Loading-surface decision

### Candidate comparison

| Candidate | Official API / schema evidence | ECM visibility for spawned model | Future files/surfaces | Impact on URDF/Xacro → ROS/Nav2 route | Boundary result | Decision |
| --- | --- | --- | --- | --- | --- | --- |
| 1. World-scope plugin in a dedicated native diagnostic world | SDFormat 1.11 permits `<plugin>` under `<world>`; Gazebo Sim 8 System `Configure` / `PostUpdate` receives the simulation ECM. The installed `contact_sensor.sdf` is a local official world-scope-system example. | Full world ECM; can exact-query the model after direct native `-file` create, then immediate link/sensor/collision children. | A new isolated diagnostic-system package, its build/install metadata, and a new dedicated diagnostic-world loading surface. The current `tugbot_depot.sdf` is not changed by this decision. | None. The dedicated native route remains separate; it has no `/robot_description`, URDF spawn, bridge, TF, Nav2, or `/cmd_vel`. | One world launch plus exactly one supervisor-owned native `create -file`; no world include and no dual spawn. | **`FEASIBLE — SELECTED`** |
| 2. Model-scope plugin in native `model.sdf` | SDFormat supports model-scope plugin declarations and a model-scoped system receives an ECM callback. | Technically can query global ECM, but it loads only with the robot model and entangles a temporary diagnostic observer with the native twin. | Requires changing `models/ROBOT_URDF_final/model.sdf` and its source/install parity. | Does not alter URDF route directly, but changes the native model artifact whose sole scope is already tightly controlled. | No direct bridge/control issue, but it expands the model contract and makes later non-diagnostic native use inherit the observer. | `FEASIBLE` but **not selected** because world scope isolates diagnostic behavior from the model. |
| 3. Other mechanism | No additional version-matched official mechanism was found that gives an external process direct ECM access without a Gazebo System. SceneBroadcaster is insufficient by S3.3.73. | Not proven. | Would require a separately audited official API. | Unknown. | Cannot be accepted on CLI, moving-branch, or inferred behavior. | `UNRESOLVED` |

### Selected loading surface

The selected future surface is **one world-scope diagnostic plugin loaded only by a new dedicated native diagnostic world**. It must not be declared in `ROBOT_URDF_final/model.sdf`, the working `tugbot_depot.sdf`, the broad URDF launch, or the Nav2 route.

The future world is only a loading surface: it must preserve the locked `world_demo` environment and load no robot include. The existing dedicated native world-only launch remains the only future launch boundary. The supervisor remains the sole owner of exactly one direct:

```text
/opt/ros/jazzy/lib/ros_gz_sim/create
  -world world_demo
  -file <installed native model.sdf>
  -name ROBOT_URDF_final
  -allow_renaming false
  -x 0 -y 0 -z 0.1 -Y 0
```

Thus a world-scope diagnostic System has visibility into the spawned model but does not create it, delete it, control it, bridge it, or change its ContactSensor configuration.

## B. Immutable receipt/persistence decision

### Candidate comparison

| Candidate | In-process → artifact transfer | Run ID / build identity | Terminal / timeout behavior | Independent auditability | Decision |
| --- | --- | --- | --- | --- | --- |
| 1. Plugin writes JSON directly to an artifact directory | Standard C++ filesystem operations, not a Gazebo Sim receipt API. The plugin would need a host path, ownership, atomic write policy, and durable directory passed through a loading configuration. | Plugin would need externally supplied run ID and plugin/source hash binding; no audited official Gazebo contract supplies these safely. | Plugin would also own filesystem failure handling; no durable process-level evidence is available if its write path fails. | Weak: a plugin-side writer has no independently verified supervisor receipt without more machinery. | `UNRESOLVED` — not selected. |
| 2. Plugin emits one diagnostic-only Gazebo Transport receipt; a read-only collector persists it | `gz::transport::Node::Advertise` / `Publisher::Publish` and `Subscribe` are official local APIs. A bounded, versioned immutable receipt can cross from the in-process System to a separate read-only collector without giving the collector ECM access. | Supervisor generates one run ID before launch; it is provided as immutable plugin configuration and must equal collector expectation. Plugin binary/source hash, collector binary/source hash, schema version, topic literal, and receipt digest are all later hash-bound. | The **System owns the diagnostic timeout** in simulation time from its first `PostUpdate`, with a future approved duration and start provenance. It emits exactly one terminal receipt (`READY` or fault) then seals. Collector has no diagnostic retry; it only has a separately approved receipt-wait/process deadline and records no-receipt as persistence/observation incomplete. | Stronger: raw received receipt bytes, digest, parsed canonical JSON/protobuf, collector metadata, and atomic durable copies can all be preserved. | **`FEASIBLE — SELECTED`** |
| 3. Supervisor-owned receipt from an unspecified handoff | No official, typed direct handoff from an in-process System to the existing supervisor was identified. A supervisor cannot access ECM as an external process. | Cannot bind a receipt source or guarantee receipt origin without defining another interface. | Timeout and no-stale policy are undefined without an exporter. | Insufficient until a specific typed handoff is designed. | `UNRESOLVED` — not selected. |

### Selected receipt contract

The selected future mechanism is **one diagnostic-only Gazebo Transport receipt followed by one read-only collector persistence operation**. The receipt is not a raw Contacts message, service/action request, ROS bridge payload, or command/control endpoint.

The future System may create one publisher only after it seals an immutable terminal snapshot. The future collector may subscribe only to that receipt topic, accept only the active run ID and schema version, receive at most one valid receipt, and persist it into the pre-created durable run directory. A duplicate receipt, wrong run ID, stale timestamp/provenance, malformed schema, wrong digest, or persistence failure must fail closed; it cannot be treated as a Scene/ECS status.

The selected **timeout owner is the System**:

1. On its first `PostUpdate`, it records copied simulation-time and steady-time provenance.
2. It remains `WAITING_FOR_TARGET` until its separately approved simulation-time waiting deadline.
3. It seals exactly one success/fault receipt using the S3.3.75 allowlist and never retries or publishes again.
4. The external collector does not reinterpret the System status. If it receives no valid receipt before its own later process/watch deadline, it records an outer receipt/persistence failure only.

The timeout duration, the diagnostic-topic literal, receipt wire schema (custom protobuf versus an existing official message carrying canonical versioned data), collector implementation, and collector receipt-wait deadline are deliberately **not** chosen by this document. They need a design/implementation approval and later packet binding; no implicit default is permitted.

## Required immutable receipt metadata

The future receipt must be self-describing and copied before persistence. At minimum it must include:

| Group | Mandatory fields |
| --- | --- |
| Identity | `schema_version`, `run_id`, `world_name`, exact model/link/sensor names and entity IDs, exact parent IDs, and exact-count fields. |
| Target evidence | `configured_collision_target`, collision entity ID/name/parent ID when safely known, and the terminal status/reason from S3.3.75. |
| Lifecycle provenance | Literal `PostUpdate`, first-observation steady/sim-time, terminal steady/sim-time, System waiting-timeout literal/unit, and sealed-once indicator. |
| Build/provenance | Gazebo tag/commit, plugin source hash, plugin binary hash, collector source/binary hash, dedicated-world hash, native model hash, and receipt topic literal. |
| Integrity/persistence | Canonical receipt-byte SHA-256, collector receive timestamp, atomic destination name, no-overwrite result, and collector terminal persistence status. |

The collector must write to a pre-created, non-symlink durable run directory using unique same-filesystem temporary files, flush/close, atomic no-overwrite commit, and directory synchronization when supported. It must retain raw receipt bytes and a canonical parsed representation together. It must not write an apparent successful parsed receipt if the raw bytes or digest are absent.

## Safety and non-claims

The only positive status is `ECS_SENSOR_TARGET_COLLISION_CHILD_OBSERVED`. It proves that one exact ContactSensor configuration target text matches one exact immediate `Collision` child under the exact `base_link` in the System's snapshot. It does not prove `ContactSensorData`, Contact-system resolution, topic advertisement, a `gz::msgs::Contacts` event, ContactLatch, collision policy, reward, termination, Nav2, training, or hardware readiness.

The selected plugin and collector are diagnostic-only. They must have no `/cmd_vel`, bridge, ROS, TF, teleop, Nav2, PPO/Gym, world-control, pose/reset/delete/pause/step, raw-contact subscriber, hardware, retry, or mutation capability.

## Required approvals before any implementation

1. Approve the isolated diagnostic-system package ownership and a **new** dedicated native diagnostic world as the sole world-scope loading surface.
2. Approve the receipt wire schema/topic, plugin timeout literal, collector receipt-wait deadline, atomic durability contract, and source/build hash-binding scheme.
3. Approve implementation and offline validation only.
4. After final code/world/collector hashes exist, approve a new runtime packet and capacity-one guard.
5. Approve one runtime run separately.

No execution authority exists at any point in this decision packet.

## Decision

`WORLD_SCOPE_DEDICATED_NATIVE_DIAGNOSTIC_WORLD + ONE_DIAGNOSTIC_TRANSPORT_RECEIPT + READ_ONLY_COLLECTOR_PERSISTENCE + SYSTEM_OWNED_TIMEOUT`

This is a design decision only. It does not authorize implementation or runtime.

## Non-mutation confirmation

No runtime operation, source change, raw-artifact mutation, guard operation, packet/guard creation, or hardware operation occurred.
