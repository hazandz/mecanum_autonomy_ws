# S3 D3 — Gazebo Contact Producer Options and Evidence Plan

**Status: NO_PRODUCER_SELECTED**

## Scope

This is a read-only options audit and a proposed passive runtime-evidence plan. It creates no producer, bridge, plugin, ROS node, contact latch, policy observation, reward, termination evaluator, Gymnasium environment, command path, or hardware behavior. No contact policy is selected.

The authoritative architecture is [MECANUM NAV DRL Architecture](MECANUM_NAV_DRL_Architecture.docx), schema 3.0. The D3 fact boundary is defined by [S3 D3 ContactLatch and Collision Fact Contract](S3_D3_ContactLatch_And_Collision_Fact_Contract_DRAFT.md). Static identity constraints are recorded in [S3 World Geometry and Entity Inventory](S3_World_Geometry_And_Entity_Inventory_DRAFT.md), and committed-step/barrier gaps in [S3 Control Step and Simulation Time Contract](S3_Control_Step_And_Simulation_Time_Contract_DRAFT.md).

## 1. Stack and current-source audit

| Item | Read-only evidence | Result |
| --- | --- | --- |
| ROS/Gazebo integration packages | Installed `ros-jazzy-ros-gz`, `ros-jazzy-ros-gz-bridge`, `ros-jazzy-ros-gz-interfaces`, and `ros-jazzy-ros-gz-sim` are version `1.0.22` on this Jazzy installation. | `OBSERVED_LOCAL_PACKAGE_METADATA` |
| Contact message and bridge conversion | Local `ros_gz_interfaces` supplies `Contact` and `Contacts`; `ros_gz_bridge` headers declare conversions for `gz::msgs::Contact`/`Contacts` and ROS `ros_gz_interfaces/msg/Contact`/`Contacts`. A ROS `Contact` exposes `collision1`, `collision2`, positions, and normals. | Conversion support exists; this does not create a producer, topic, timestamp, sequence, or scoped-name contract. |
| Actual launch world | `gazebo.launch.py` launches `tugbot_depot.sdf`, whose world name is `world_demo`. | `OBSERVED_STATIC_SOURCE` |
| Existing world systems | The SDF configures Physics, UserCommands, SceneBroadcaster, Imu, and Sensors systems. | No audited contact system/plugin is configured. |
| Existing robot systems/sensors | `ROBOT_URDF_final.gazebo` configures VelocityControl, MecanumDrive, OdometryPublisher, JointStatePublisher, camera, and GPU LiDAR. | No audited contact sensor or contact plugin is configured. |
| Existing bridge configuration | `config/ros_gz_bridge_gazebo.yaml` contains only `/clock`; the launch-owned bridge has no contact mapping. | No contact bridge is configured. |
| Static collision geometry | World and robot collision geometry exists; static candidate names are catalogued in the inventory. | Geometry is not a runtime contact event source. |

The `<contact/>` surface element for `ground_plane` is not a contact sensor or an event publisher. Legacy `mecanum_env.py` imports ROS `Contacts`, but it is non-authoritative legacy code and is not evidence that the current architecture exposes a contact topic.

## 2. Candidate producer options on the installed stack

| Option | Event/message and publication point | Entity/link identities | Timestamp and sequence | Duplicates and simultaneous contacts | Future ContactLatch ingress | ROS bridge impact | Evidence gap / status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A. Gazebo contact sensor | A future SDF/URDF contact sensor could publish a Gazebo contact event. Exact sensor configuration, topic, and emitted type are not present in the audited source. | `UNKNOWN — RUNTIME_EVIDENCE_REQUIRED`; a raw contact message may carry collision entities, but the runtime scoped-name format is not yet demonstrated. | `UNKNOWN — RUNTIME_EVIDENCE_REQUIRED`; local ROS `Contacts` definitions do not establish a header timestamp or producer sequence. | `UNKNOWN — RUNTIME_EVIDENCE_REQUIRED`; must be captured rather than inferred. | A future adapter/latch may validate raw events into immutable candidates after a selected policy/filter. | If a compatible Gazebo `gz::msgs::Contacts` topic exists, local bridge conversion support is present; a topic name and direction still require approval and proof. | Requires an approved sensor configuration, bridge boundary, and passive runtime trace. |
| B. Gazebo system/plugin producing contact events | A future Gazebo system/plugin could observe physics contacts and publish a dedicated event. No such system is in the current world or robot source. | Can be designed to emit identities, but their runtime format is unknown until producer design/evidence exists. | Can be designed to emit simulation time and sequence, but neither is currently available. | Can be designed to preserve raw multiplicity, but this needs an approved aggregation contract. | Direct source for a future ContactLatch after explicit provenance validation. | Could be Gazebo-only with a core/runtime adapter, or bridged; either boundary needs approval. | `NOT_IMPLEMENTED`; producer semantics, deployment, and evidence are absent. |
| C. Gazebo Transport contact topic plus `ros_gz_bridge` | A Gazebo Transport `gz::msgs::Contacts` topic may be bridged to `ros_gz_interfaces/msg/Contacts` if an actual producer publishes it. | Message conversion can carry two collision entities; scoped names remain unproven. | `UNKNOWN — RUNTIME_EVIDENCE_REQUIRED`; local interface does not make a timestamp/sequence guarantee. | Payload cardinality is bridgeable in principle; delivery ordering and duplicate behavior are unmeasured. | A ROS-side future ContactLatch could subscribe after the exact source/topic contract is approved. | Requires an explicit GZ-to-ROS bridge mapping. Existing bridge has none. | No topic/produder name, runtime graph, or semantic evidence exists. |
| D. Minimal custom producer plus raw-event contract | A narrowly scoped custom Gazebo system/plugin could produce a versioned raw event with the fields D3 needs. | Could explicitly emit fully scoped collision identities, subject to evidence of Gazebo identity stability. | Could explicitly emit simulation timestamp and producer sequence. | Could retain each raw pair and expose multiplicity for deterministic latch policy. | Best fit for a provenance-complete future latch, but only after an approved design and implementation increment. | Bridge optional; any bridge must expose only the approved event boundary. | `NOT_IMPLEMENTED`; adds ownership, code, and runtime validation work. |

### Option-selection result

**NO_PRODUCER_SELECTED.** The local stack proves only that ROS/Gazebo contact message conversion types are installed. It does not prove a built-in producer configuration compatible with the required identity, timestamp, sequence, duplicate, simultaneous-contact, and action-interval provenance. Selecting Option A, B, C, or D requires user approval and a runtime evidence plan.

## 3. Conditions common to every option

A V1 producer cannot be treated as a collision decision until it proves all of the following:

- source and `filter_policy_id`/version/hash are identifiable;
- an event can be bound to the active `EpisodeLifecycleIdentity` and `TransitionIdentity` through an approved action-barrier owner;
- simulation timestamp is captured in its own domain, separate from steady receive time;
- raw collision identities are available in a stable, documented form;
- duplicate and simultaneous events are retained or deterministically classified under an approved rule;
- reset/new generation clearing prevents prior-lifecycle event reuse.

No option permits deriving collision from LiDAR, GT odometry, `/odom`, pose response, wheel motion, or motor state.

## 4. Proposed passive runtime evidence plan

This is a proposal for a separately approved future run, not authorization to launch Gazebo.

### Preconditions and safety boundary

- Verify the exact launched world identity and world-file SHA-256 before capture.
- Snapshot the ROS and Gazebo graph, including the candidate contact topic/service endpoints, message types, producers, subscribers, and any bridge process.
- Subscribe/observe only the approved contact source and needed graph/clock metadata.
- Do not publish `/cmd_vel`; do not use teleop, Nav2, PPO, Gymnasium, or SB3.
- Do not call pose, reset, pause, step, spawn, delete, or any world-control service/action.
- Do not touch UART, MCU, motor, Pi, STM32, firmware, or hardware.
- Shutdown only measurement-created processes by SIGINT; preserve logs and report incomplete shutdown rather than force-killing.

### Capture content

For each raw event, capture losslessly:

| Field group | Proposed captured evidence |
| --- | --- |
| Source identity | Gazebo topic and type; bridge direction/type if present; producer process/plugin identity and version where observable. |
| Event payload | Full raw payload or a lossless encoded record; both collision entity/link values; contact positions/normals if exposed; payload cardinality. |
| Time domains | Raw simulation/ROS timestamp if the producer provides it; local steady receive timestamp; no direct subtraction across domains. |
| Ordering | Per-stream receive index; any producer sequence if actually supplied; simultaneous payload grouping; duplicate payload observations. |
| Lifecycle context | Observation/action-barrier metadata only if an approved owner exists; otherwise mark unavailable rather than fabricate binding. |
| Reset evidence | Pre/post reset-generation graph/event state only if reset is separately approved; this passive plan does not call reset. |

Suggested artifact root for a future approved measurement:

```text
artifacts/simulation/contact_producer_evidence/<run_id>/
  manifest.json
  graph_pre.json
  graph_post.json
  raw_contacts.jsonl
  clock_trace.jsonl
  bridge_and_producer_logs/
  summary.json
  Contact_Producer_Evidence_Report.md
  shutdown_record.json
```

The run can establish only source/payload/timing/ordering observations. It must not label a contact as terminal, derive collision policy, prove an action interval, or approve a ContactLatch.

## 5. Contact candidate type migration

The existing `core/episode_lifecycle.py` `ContactCandidateSnapshot` is a two-field, immutable test-only type. It must not silently acquire runtime semantics.

| Migration choice | Description | Benefits | Required decision |
| --- | --- | --- | --- |
| A. Version/extend the existing type with explicit migration | Introduce a new explicit version and migrate all consumers/tests from the test-only shape to full provenance fields. | One nominal type after a deliberate migration. | `REQUIRED_USER_DECISION`; requires ownership and compatibility plan. |
| B. Introduce a separate runtime provenance type | Keep current test-only snapshot unchanged; a future runtime producer/latch maps raw events to a distinct immutable provenance-rich type. | Avoids changing the meaning of existing core test fixtures; boundary remains visible. | `REQUIRED_USER_DECISION`; requires an explicit join contract. |

Neither choice is approved here.

## 6. User decisions required before runtime evidence

| Decision | Why it must be selected before evidence/implementation |
| --- | --- |
| V1 producer option (A, B, C, or D) | Determines where raw events originate and what must be measured. |
| ROS/Gazebo bridge boundary | Determines whether a contact topic is bridged, its type/direction, and the observable graph. |
| Entity/link identity policy | Determines how raw entities are represented and how unresolved/Fuel-scoped names are handled. |
| Wheel-ground, self-contact, and sensor filters | Prevents normal/support or accessory events from being silently classified. |
| World-object filter policy | Defines treatment of walls, boxes, shelves, pallets, and future objects. |
| Duplicate and simultaneous-contact aggregation | Makes collision candidate behavior deterministic and replayable. |
| Action-interval/barrier owner | Required to bind a raw event to a particular transition. |
| Type migration policy | Preserves the existing test-only snapshot semantics during runtime integration. |

## Conclusion

**NO_PRODUCER_SELECTED.** An installed message conversion path is not a producer contract. The project has static collision geometry and compatible ROS/Gazebo contact interface types, but lacks an approved producer, source topic, scoped-name policy, timestamp/sequence semantics, action-interval binding, and runtime evidence.

Therefore collision detection, ContactLatch, reward, termination, Gymnasium, and training remain not ready. A next phase must first obtain user decisions above and approval for a passive, no-command contact-producer evidence run.
