# S3 D3 — Base-Link Contact Target Implementation Decision Packet

**Status: IMPLEMENTED_SURFACE — COMPLETED_INVALID_EVIDENCE_RUN — NEW_WORLD_HASH_APPROVAL_REQUIRED**

## Purpose and boundary

## Recorded S3.3.10 outcome

The previously approved minimal source surface is now present: the existing `base_link` box collision has the explicit name `s3_d3_base_contact_collision`; the existing `base_link` Gazebo extension contains exactly one `s3_d3_base_contact_sensor`; and `tugbot_depot.sdf` contains exactly one world-scope built-in Contact system. Collision geometry, inertial, visual, motor, and non-contact plugin settings were not changed.

The sole approved passive evidence-run attempt, `run-contact-20260926T143804Z-01`, failed closed at the source-world SHA gate. The pre-edit approved hash `a5e9c9b1e9b8ad11e0399855f06de687f04c702258b8b74ce563523d78ed55fe` differs from the post-edit source hash `1c50f90d151a12559d426796c5d153c829b8777a5b4e8ef94c007a2023f6e271`, because the approved Contact-system declaration changes the world file. Gazebo, bridge, and collector were not started; no raw contact payload, runtime scoped name, or bridge-delivery evidence was produced. The run is retained as invalid evidence and may not be retried under the consumed approval.

This outcome only records source-surface implementation and a preflight blocker. It does not establish ContactSensor runtime operation, collision detection/policy, ContactLatch semantics, timing, reset behavior, reward/termination, Gym/training, `/cmd_vel` behavior, or hardware behavior. A later run requires explicit approval of the new world hash and a separately approved run.

This packet prepares the smallest future implementation surface for the Option A+C raw-contact evidence path. It proposes one named chassis/base collision and exactly one ContactSensor target, but applies nothing. No source, Xacro, URDF, SDF, launch, bridge, test, runtime, or hardware behavior is modified by this packet.

The pending Option A+C evidence boundary is [S3 D3 Option A+C Passive Contact Evidence Run Approval Packet](S3_D3_Option_A_C_Passive_Contact_Evidence_Run_Approval_Packet_DRAFT.md). Static API feasibility is recorded in [S3 D3 Static Contact API Feasibility Audit](S3_D3_Static_Contact_API_Feasibility_Audit_DRAFT.md). This packet does not supersede the D3 contact/latch contract in [S3 D3 ContactLatch and Collision Fact Contract](S3_D3_ContactLatch_And_Collision_Fact_Contract_DRAFT.md).

## 1. Static implementation-surface audit

| Audit subject | Static evidence | Consequence for future change |
| --- | --- | --- |
| Robot description entry point | [`launch/gazebo.launch.py`](../ros2_ws/src/ROBOT_URDF_final_description/launch/gazebo.launch.py) selects `urdf/ROBOT_URDF_final.xacro`, runs `xacro.process_file`, and spawns `ROBOT_URDF_final` from `/robot_description`. | `ROBOT_URDF_final.xacro` is the source entry point for the spawned robot description. |
| Extension inclusion | [`ROBOT_URDF_final.xacro`](../ros2_ws/src/ROBOT_URDF_final_description/urdf/ROBOT_URDF_final.xacro) includes `materials.xacro`, `ROBOT_URDF_final.ros2control`, and `ROBOT_URDF_final.gazebo`. | A future sensor extension can be placed in the existing Gazebo extension file without creating a second robot description. |
| Chassis collision | `link name="base_link"` has one `<collision>` at Xacro lines 22–27, geometry `box size="0.4 0.28 0.10"`, origin `0 0 0`. It has no `name` attribute. | The chassis category exists, but no collision literal is available for a ContactSensor target. |
| Existing base Gazebo extension | [`ROBOT_URDF_final.gazebo`](../ros2_ws/src/ROBOT_URDF_final_description/urdf/ROBOT_URDF_final.gazebo) already has `<gazebo reference="base_link">` for material, friction, self-collision, and gravity. No contact sensor is inside it. | Smallest proposed sensor placement is this existing `base_link` extension block. |
| Existing robot sensors/plugins | Current extension declares camera, GPU LiDAR, VelocityControl, MecanumDrive, OdometryPublisher, and JointStatePublisher; no contact sensor or contact system declaration is present. | No static sensor/plugin duplication conflicts with one new ContactSensor. |
| World/Contact system | [`launch/tugbot_depot.sdf`](../ros2_ws/src/ROBOT_URDF_final_description/launch/tugbot_depot.sdf) defines `world_demo` and Physics/UserCommands/SceneBroadcaster/Imu/Sensors; it does not load `gz::sim::systems::Contact`. | The Contact system must be added once at world scope only after approval. |
| Existing bridge | [`config/ros_gz_bridge_gazebo.yaml`](../ros2_ws/src/ROBOT_URDF_final_description/config/ros_gz_bridge_gazebo.yaml) has only `/clock`; launch bridge arguments have no Contacts mapping. | Exactly one raw contact mapping would be a new, separately visible change. |
| Literal collision-name conflict | Repository-wide static scan finds no existing `s3_d3_base_contact_collision`. | The proposed literal has no static duplicate in the audited workspace. |

The actual runtime scoped Gazebo name, entity ID, sensor topic expansion, or transport topic is not established by this audit.

## 2. Proposed target literals — not applied

| Field | Proposed literal | Static justification | Status |
| --- | --- | --- | --- |
| Target category | chassis/base | `base_link` owns a dedicated box collision; wheels are distinct links. | `PROPOSED` |
| Explicit collision name | `s3_d3_base_contact_collision` | Unique in the audited source; attaches a stable source-level literal to the existing unnamed `base_link` box. | `PROPOSED` |
| ContactSensor name | `s3_d3_base_contact_sensor` | Unique in the audited source and clearly scoped to D3 evidence. | `PROPOSED` |
| Raw GZ topic | `/s3_d3/contact/raw` | Matches the existing approval packet proposal; no current source config proves it exists. | `PROPOSED` |
| Raw ROS topic | `/s3_d3/contact/raw` | A proposed bridge endpoint only; identical spelling does not prove identity across Gazebo Transport and ROS. | `PROPOSED` |
| GZ message type | `gz::msgs::Contacts` | Installed contact-system/example/protobuf evidence. | `STATICALLY_FEASIBLE` |
| ROS message type | `ros_gz_interfaces/msg/Contacts` | Installed message and bridge conversion declaration. | `STATICALLY_FEASIBLE` |
| Bridge direction | `GZ_TO_ROS` | Required for a passive ROS collector to observe a Gazebo-origin raw contact stream. | `PROPOSED` |

`base_link` is recommended only as a raw-sensor target category. The proposed name does not classify base contact as terminal, nor does it decide whether wheel, self, sensor, or world-object contacts are included by a later collision policy.

## 3. Exact minimal future edit locations — after approval only

| File | Proposed future edit | Preservation requirement |
| --- | --- | --- |
| [`urdf/ROBOT_URDF_final.xacro`](../ros2_ws/src/ROBOT_URDF_final_description/urdf/ROBOT_URDF_final.xacro) | Change only the existing `base_link` collision opening tag from unnamed to `name="s3_d3_base_contact_collision"`. | Preserve its origin, `0.4 0.28 0.10` box geometry, inertial block, visual mesh/material, links, joints, wheel setup, and all other collisions. |
| [`urdf/ROBOT_URDF_final.gazebo`](../ros2_ws/src/ROBOT_URDF_final_description/urdf/ROBOT_URDF_final.gazebo) | Add exactly one ContactSensor declaration in the existing `<gazebo reference="base_link">` block, targeting the approved explicit collision literal and proposed raw topic. | Preserve material, `mu1`, `mu2`, `self_collide`, gravity, existing sensors, motion/odometry plugins, `/cmd_vel` configuration, and all non-contact behavior. |
| [`launch/tugbot_depot.sdf`](../ros2_ws/src/ROBOT_URDF_final_description/launch/tugbot_depot.sdf) | Add exactly one world-scope built-in Contact system declaration: `filename="gz-sim-contact-system"`, `name="gz::sim::systems::Contact"`. | Preserve world identity `world_demo`, world geometry, physics, all existing systems, includes, and entities. |
| Bridge configuration or an explicitly approved temporary measurement bridge | Add exactly one raw `Contacts` GZ-to-ROS mapping for the approved topic/type. | Do not add `/cmd_vel`, control, pose, reset, spawn/delete, or other bridge endpoints. |
| Artifact-owned passive collector | Add a collector only after the run is separately approved. | Subscribe only raw Contacts, `/clock`, and graph metadata; create no publisher, service client, or action client. |

The future implementation must be reviewed as an architecture-sensitive change before editing because it adds a sensor/system/bridge boundary. This document supplies no approval to make those edits.

## 4. Why the proposed literal does not conflict statically

- `s3_d3_base_contact_collision` is absent from the audited robot/world/config source and existing D3 documents before this packet.
- `base_link` has exactly one source-level collision element and it is unnamed, so assigning the literal does not add a second collision element or alter collision geometry.
- No existing `<sensor type="contact">`, ContactSensor name, `gz-sim-contact-system` declaration, or `Contacts` bridge mapping exists in the robot description, launched world, or bridge config.
- The proposed ContactSensor name `s3_d3_base_contact_sensor` is also absent from the static source.

These facts only establish no static duplicate. They do not prove Gazebo runtime accepts the generated URDF/SDF form, assigns a particular scoped name, publishes any event, or preserves the proposed raw topic.

## 5. Non-claims and retained boundaries

Adding an explicit source-level collision name would **not** prove:

- a Gazebo runtime scoped collision name, entity ID, Contact system load, or contact-topic delivery;
- timestamp population, producer sequence, duplicate behavior, simultaneous-contact behavior, or bridge retention;
- action-interval or `TransitionIdentity` provenance;
- collision classification, wheel-ground filtering, self-contact policy, sensor-contact policy, terminal behavior, reward, or reset semantics;
- ContactLatch existence or correctness;
- a change in the meaning of the existing test-only `ContactCandidateSnapshot`;
- Gymnasium/training behavior, `/cmd_vel` behavior, motor behavior, UART, or hardware behavior.

The explicit collision name is solely a proposed source-level handle for a future raw passive contact-evidence sensor.

## 6. User approvals required

Before a future implementation/run, the user must explicitly approve:

1. the proposed name `s3_d3_base_contact_collision` on the existing `base_link` box collision;
2. the proposed `s3_d3_base_contact_sensor` and its exact contact-sensor syntax/location;
3. the one world Contact-system declaration;
4. the one raw GZ-to-ROS Contacts bridge literal and direction;
5. one passive Gazebo-only evidence run, including its graph/preflight/shutdown contract.

The user has **not** selected type migration, collision filters, duplicate/simultaneous aggregation, action-barrier ownership, ContactLatch semantics, or terminal/reward behavior through this packet.

## Conclusion

**PENDING_USER_APPROVAL_FOR_NAMED_BASE_COLLISION_AND_ONE_PASSIVE_CONTACT_EVIDENCE_RUN.** A chassis/base target can be made source-identifiable with one non-conflicting explicit collision-name literal and one sensor, while preserving static geometry and robot behavior. Runtime identity, Contact-system delivery, timestamp/provenance, and all collision semantics remain unproven and outside this packet.
