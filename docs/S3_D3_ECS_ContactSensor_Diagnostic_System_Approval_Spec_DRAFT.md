# S3 D3 ECS ContactSensor Diagnostic System Approval Specification

`DRAFT — DESIGN ONLY, IMPLEMENTATION AND RUNTIME NOT APPROVED`

## Scope and authority

This document specifies a future minimal, read-only Gazebo Sim System that may take one ECS snapshot after a direct native-SDF spawn. It does not approve implementation, package loading, world edits, a packet, a guard, or a runtime run. It neither replaces nor retries consumed S3.3.72.

| Authority | Locked identity | Use in this specification |
| --- | --- | --- |
| Gazebo Sim | [`gz-sim8_8.11.0`](https://github.com/gazebosim/gz-sim/releases/tag/gz-sim8_8.11.0), commit [`1be3cc376fec778cc725b4eeea463245affa56d3`](https://github.com/gazebosim/gz-sim/commit/1be3cc376fec778cc725b4eeea463245affa56d3) | `ISystemPostUpdate`, `EntityComponentManager`, SDF entity creation, and official Contact lookup behavior. |
| Local public API | `/opt/ros/jazzy/opt/gz_sim_vendor/include/gz/sim8/gz/sim/{System,EntityComponentManager}.hh` and component headers | The in-process, read-only ECM interface. |
| `gz-msgs10` / SDFormat | Installed `gz-msgs10` 10.3.2 protos and SDFormat 1.11 `contact.sdf` | Typed identity names and the `<contact><collision>` structure. |
| Prior audit | [S3.3.73 SceneBroadcaster audit](S3_D3_SceneBroadcaster_ContactSensor_Component_Serialization_Audit.md) and [S3.3.74 ECS inspection audit](S3_D3_ECS_ContactSensor_Component_Inspection_Design_Audit.md) | Scene service omission boundary and exact component queries. |

The official Contact-system reference behavior is [`ContactPrivate::CreateSensors`](https://github.com/gazebosim/gz-sim/blob/1be3cc376fec778cc725b4eeea463245affa56d3/src/systems/contact/Contact.cc#L166-L216). It reads the ContactSensor SDF element and uses exact `ChildrenByComponents(link, Collision, Name)` lookup. The proposed diagnostic must only observe an equivalent identity chain; it must not create `ContactSensorData`, advertise a contact endpoint, or publish contact data.

## 1. Lifecycle state machine

Only `ISystemPostUpdate::PostUpdate(const UpdateInfo &, const EntityComponentManager &)` is permitted for future observation. `Configure`, `PreUpdate`, and `Update` are outside this diagnostic snapshot contract. The `const` ECM reference is mandatory; no mutable component API may be called.

```text
WAITING_FOR_TARGET
  |  PostUpdate: exact model/link/sensor chain not yet proven
  |  -> remain waiting, with no output and no mutation
  |
  |  PostUpdate: one exact chain reaches terminal evaluation
  +--> SNAPSHOT_READY --seal immutable receipt--> SEALED
  |
  +--> SNAPSHOT_FAULT --seal immutable receipt--> SEALED

SEALED
  -> all later PostUpdate calls perform no query result publication,
     no retry, and no ECS mutation.
```

| State | Entry condition | Permitted operation | Prohibited operation |
| --- | --- | --- | --- |
| `WAITING_FOR_TARGET` | System construction; no terminal snapshot has been sealed. | Read exact ECM identities in `PostUpdate`. | Cached/old snapshot reuse, identity fallback, component creation/defaulting, output publication, retry counter. |
| `SNAPSHOT_READY` | All exact chain checks pass once. | Construct the immutable success payload once. | A second snapshot, contact lookup side effects, endpoint inspection, command/control. |
| `SNAPSHOT_FAULT` | One terminal fail-closed status is reached once. | Construct the immutable fault payload once. | Treating a fault as absence outside its stated status, retrying, mutation. |
| `SEALED` | Ready/fault receipt has been handed to the future approved output/persistence boundary. | No-op only. | Any later publication, new snapshot, retry, or ECS mutation. |

Direct `ros_gz_sim create` exit code zero plus a post-create delay is only Candidate-A operational permission to evaluate one snapshot. It is not an entity-existence, insertion, reset, settled-state, or ECM snapshot receipt. A future runtime design must separately bind runtime provenance for the first successful `PostUpdate` evaluation and preserve that provenance in evidence.

## 2. Exact snapshot query contract

The only accepted hierarchy is:

```text
ROBOT_URDF_final
  -> immediate base_link
       -> immediate s3_d3_base_contact_sensor
            -> components::ContactSensor
            -> <contact><collision> exact target literal
       -> immediate Collision + Name(target literal)
```

Every name comparison is exact equality. No substring, prefix/suffix, guessed scoped name, recursive descendant substitution, or default identity is permitted.

| Step | Read-only query / check | Exact success condition | Failure status |
| --- | --- | --- | --- |
| 1 | `EntitiesByComponents(Model(), Name("ROBOT_URDF_final"))` | Exactly one model | `ECS_MODEL_UNCONFIRMED` |
| 2 | `ChildrenByComponents(model, Link(), Name("base_link"))` and link `ParentEntity` | Exactly one immediate link; parent equals selected model | `ECS_LINK_UNCONFIRMED` |
| 3 | `ChildrenByComponents(link, Sensor(), Name("s3_d3_base_contact_sensor"))` and sensor `ParentEntity` | Exactly one immediate sensor; parent equals selected link | `ECS_SENSOR_UNCONFIRMED` |
| 4 | `Component<ContactSensor>(sensor)` | Non-null | `ECS_CONTACT_COMPONENT_MISSING` |
| 5 | `ContactSensor::Data()` then exact SDF element reads `contact` and `collision`, followed by non-empty string parse | One parseable target literal | `ECS_CONTACT_CONFIGURATION_INCOMPLETE` |
| 6 | `ChildrenByComponents(link, Collision(), Name(target))` and collision `ParentEntity` | Exactly one immediate collision; parent equals selected link | `ECS_TARGET_COLLISION_CHILD_UNCONFIRMED` |
| 7 | Seal snapshot | All prior conditions hold | `ECS_SENSOR_TARGET_COLLISION_CHILD_OBSERVED` |

`components::ContactSensor` stores `sdf::ElementPtr` for the whole sensor element, not typed contact data. The future code must therefore check, in order, non-null component, non-null SDF element, `contact` presence, `collision` presence, successful string extraction, and non-empty target. It must not dereference missing elements or assume SDFormat default text. Any malformed/missing structure is `ECS_CONTACT_CONFIGURATION_INCOMPLETE`.

## 3. Terminal-status payload and non-claims

| Status | Trigger | Permitted snapshot payload | Explicit non-claim |
| --- | --- | --- | --- |
| `ECS_MODEL_UNCONFIRMED` | Model exact count is zero or not one. | Model exact count; no invented model ID. | Not a sensor/collision absence conclusion. |
| `ECS_LINK_UNCONFIRMED` | Model confirmed but immediate link count/parent is not exactly one/correct. | Confirmed model identity; link count and observed parent IDs if safely available. | Not a sensor/collision absence conclusion. |
| `ECS_SENSOR_UNCONFIRMED` | Model/link confirmed but immediate sensor count/parent is not exactly one/correct. | Confirmed model/link identities; sensor count and safe parent IDs. | Not a ContactSensor-component or configured-target conclusion. |
| `ECS_CONTACT_COMPONENT_MISSING` | Exact sensor exists but has no `ContactSensor` component. | Confirmed model/link/sensor IDs/names and component-present false. | Not proof of endpoint failure, event absence, or source SDF cause. |
| `ECS_CONTACT_CONFIGURATION_INCOMPLETE` | ContactSensor exists but its element/contact/collision text is missing, malformed, or empty. | Confirmed upstream IDs/names; only safe structure-presence booleans; no fabricated target. | Not a target-mismatch or endpoint/event conclusion. |
| `ECS_TARGET_COLLISION_CHILD_UNCONFIRMED` | Parseable target exists but exact immediate collision count/parent is not exactly one/correct. | Confirmed target literal, exact count, and safe collision IDs/names/parents. | Not proof that Contact system failed, endpoint is absent, or contact cannot occur. |
| `ECS_SENSOR_TARGET_COLLISION_CHILD_OBSERVED` | Every exact query above passes. | Full immutable identity/configuration snapshot. | Not proof of `ContactSensorData`, Contact-system resolution, endpoint advertisement, `gz::msgs::Contacts`, collision event, ContactLatch, policy, reward/termination, Nav2/training, or hardware readiness. |

Once either ready or fault is sealed, the diagnostic must issue no more snapshot output. A `WAITING_FOR_TARGET` period must not emit a partial success/fault; the future runtime boundary must define its single timeout/terminal conversion separately.

## 4. Immutable evidence schema

The future diagnostic's in-memory snapshot and durable receipt must use a versioned, immutable schema. It must contain only copied scalar values; it must not retain a raw ECM pointer, `sdf::ElementPtr`, component pointer/reference, ROS data, PPO/training data, ground truth, or command/control payload.

| Field | Requirement |
| --- | --- |
| `schema_version` | Fixed future diagnostic schema version. |
| `run_id` / `runtime_identity` | Required placeholders bound by the future supervisor/guard; no generated replacement ID in the System. |
| `world_name`, `model_name`, `link_name`, `sensor_name` | Fixed strings recorded exactly as queried. |
| `world_id`, `model_id`, `link_id`, `sensor_id`, `collision_id` | Numeric entity identifiers or `null` only when the corresponding entity was not safely confirmed. |
| `model_parent_id`, `link_parent_id`, `sensor_parent_id`, `collision_parent_id` | Copied parent IDs or `null` when unavailable. |
| `configured_collision_target` | Exact extracted literal or `null` only for an incomplete configuration status. |
| `model_exact_count`, `link_exact_count`, `sensor_exact_count`, `collision_exact_count` | Integers from the exact queries; never inferred. |
| `hook_name` | Literal `PostUpdate`. |
| `steady_time`, `sim_time` | Future runtime placeholders whose unit/origin must be bound before implementation. |
| `terminal_status`, `reason` | One allowlisted terminal status and deterministic reason. |
| `source_identity`, `plugin_build_identity` | Future source/binary hash placeholders; both must be bound by a later approval. |

The success status establishes only configuration plus immediate-child identity. It does not transform a static component snapshot into a contact producer, collision event, or control/learning claim.

## 5. Output and persistence boundary: options audited, none selected

| Future option | Official/API basis | What it could carry | Unresolved work / boundary |
| --- | --- | --- | --- |
| Diagnostic-only Gazebo Transport output | Local `gz-transport13` `Node::Advertise` / `Publisher::Publish` API. | One typed immutable receipt. | A message schema, topic namespace, discoverability, one-shot delivery, and lifecycle ownership require a separate design and approval. It must be read-only and cannot be a command/control endpoint. |
| Supervisor-owned durable receipt | Existing project evidence pattern, not a Gazebo ECS API. | A copied immutable receipt persisted alongside run provenance. | Requires a separately approved bridge from in-process System output to supervisor and atomic/no-overwrite persistence contract. It cannot treat missing output as a collision conclusion. |
| Existing Scene / generic state projection | SceneBroadcaster and ECM state APIs audited in S3.3.73/S3.3.74. | Hierarchy/type or generic state only. | Not selected: no official typed contract was confirmed for exact `ContactSensor` SDF configuration target. |

No output option is chosen, implemented, or approved by this specification. Any future transport output must not advertise raw contacts, subscribe to contacts, command the world, create an endpoint that can alter simulation, or become a bridge.

## 6. Future integration boundary and approvals

The native SDF diagnostic route remains isolated from the existing URDF/Xacro/Nav2 route. No current file is changed by this draft. If implementation is later approved, the following surfaces require explicit review and hash-binding:

| Surface | Future change scope, not approved here |
| --- | --- |
| New diagnostic-system package/source | A new minimal C++ Gazebo Sim System that compiles against `gz-sim8_8.11.0`, reads only `PostUpdate` ECM state, and has no ROS/control dependency. Package ownership must be approved before creation. |
| Build/package metadata | Only metadata required to build/install that isolated system; no alteration to robot behavior packages without explicit approval. |
| System loading surface | One dedicated native diagnostic world or another version-matched loading mechanism must be selected and audited before any load declaration. The existing native model, world, and launch remain unchanged now. |
| Future supervisor/evidence boundary | A later approved run contract must bind the plugin binary, its source, output/persistence mechanism, exact run ID provenance, and one-shot terminal receipt. |
| Runtime authority | A new packet and capacity-one guard are required only after implementation/offline validation and separate user approval. |

Required decision gates are sequential: (1) approve an implementation architecture including the loading and output/persistence mechanism; (2) approve implementation plus offline validation; (3) review resulting hashes/contracts and approve a new runtime packet/guard; (4) approve one runtime run. S3.3.72 remains consumed and cannot be rerun.

## One narrow next step

Seek user approval for a design choice covering only the future diagnostic System's loading surface and immutable output/persistence mechanism. No code, world change, packet, guard, or run should begin before that decision.

## Non-mutation confirmation

This increment performed zero runtime activity and zero source, raw-artifact, guard, packet, launch, model, world, or configuration mutation.
