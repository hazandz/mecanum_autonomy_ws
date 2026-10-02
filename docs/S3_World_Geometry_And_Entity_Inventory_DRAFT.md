# S3 World Geometry And Entity Inventory

Status: **DRAFT — PENDING_USER_APPROVAL**

## Scope and authority

This is a static-source inventory for future T1, T2, and T5 user decisions.
It records names, geometry, and source-declared poses from the currently
launched simulation. It does **not** define a valid area, forbidden zone, goal,
collision policy, `ContactLatch`, reset transaction, or scenario artifact.

Authority and constraints:

- [MECANUM_NAV_DRL_Architecture.docx](MECANUM_NAV_DRL_Architecture.docx),
  schema `3.0`, SHA-256
  `f0fb1ebede5f4fa18604610c04bb13587d456173b4fd942dba77e44d49777860`.
- [ACR S1: Simulated Odometry And Ground Truth Isolation](ACR_S1_Simulated_Odometry_And_Ground_Truth_Isolation.md).
- [S3 Training Task, Reset And Collision Design Packet](S3_Training_Task_Reset_And_Collision_Design_Packet_DRAFT.md).
- [S3 Episode, Reward And Termination Design](S3_Episode_Reward_Termination_Design_DRAFT.md).

Status labels used below:

- `OBSERVED_STATIC_SOURCE`: directly declared by a checked source file.
- `OBSERVED_RUNTIME_METADATA`: observed in a runtime message/report; it does
  not itself establish static identity, coordinate conversion, or TF authority.
- `NON_AUTHORITATIVE_CANDIDATE`: present only in legacy/prototype code; not adopted.
- `GEOMETRY_REFERENCE_ONLY`: source geometry, not a selected task boundary.
- `REQUIRED_DECISION`: cannot be selected from static evidence.
- `NOT_ESTABLISHED_RUNTIME`: static source does not prove live Gazebo behavior,
  scoped names, topic delivery, or TF authority.

## 1. World identity

| Property | Static-source value | Source | Status |
| --- | --- | --- | --- |
| Launch entry point | `ROBOT_URDF_final_description/launch/gazebo.launch.py` | [gazebo.launch.py](../ros2_ws/src/ROBOT_URDF_final_description/launch/gazebo.launch.py) | `OBSERVED_STATIC_SOURCE` |
| World SDF selected by launch | `ROBOT_URDF_final_description/launch/tugbot_depot.sdf` | [gazebo.launch.py](../ros2_ws/src/ROBOT_URDF_final_description/launch/gazebo.launch.py) | `OBSERVED_STATIC_SOURCE` |
| Gazebo/SDF world identity/name | `world_demo`; not a proven ROS coordinate frame | [tugbot_depot.sdf](../ros2_ws/src/ROBOT_URDF_final_description/launch/tugbot_depot.sdf) | `OBSERVED_STATIC_SOURCE` |
| World-file SHA-256 | `a5e9c9b1e9b8ad11e0399855f06de687f04c702258b8b74ce563523d78ed55fe` | `sha256sum` of [tugbot_depot.sdf](../ros2_ws/src/ROBOT_URDF_final_description/launch/tugbot_depot.sdf) | `OBSERVED_STATIC_SOURCE` |
| Physics declaration | `max_step_size=0.01`, `real_time_factor=1` | [tugbot_depot.sdf](../ros2_ws/src/ROBOT_URDF_final_description/launch/tugbot_depot.sdf) | `OBSERVED_STATIC_SOURCE` |
| World systems | `Physics`, `UserCommands`, `SceneBroadcaster`, `Imu`, `Sensors` | [tugbot_depot.sdf](../ros2_ws/src/ROBOT_URDF_final_description/launch/tugbot_depot.sdf) | `OBSERVED_STATIC_SOURCE` |
| Robot source description | `urdf/ROBOT_URDF_final.xacro`, expanded by launch into `/robot_description` | [gazebo.launch.py](../ros2_ws/src/ROBOT_URDF_final_description/launch/gazebo.launch.py) | `OBSERVED_STATIC_SOURCE` |
| Spawned robot entity name | `ROBOT_URDF_final`, `-allow_renaming false` | [gazebo.launch.py](../ros2_ws/src/ROBOT_URDF_final_description/launch/gazebo.launch.py) | `OBSERVED_STATIC_SOURCE` |
| Startup spawn pose | `(x=0, y=0, z=0.1, yaw=0)` | [gazebo.launch.py](../ros2_ws/src/ROBOT_URDF_final_description/launch/gazebo.launch.py) | `OBSERVED_STATIC_SOURCE`; not an episode start contract |

The world systems prove only that these systems are configured in source.
They do not establish a reset API, a contact topic, a collision event, or any
runtime behavior.

### Static world entities

| Source-declared entity | Static identity / pose | Status | Notes |
| --- | --- | --- | --- |
| `ground_plane` | Static model at `0 0 0 0 0 0`, link `link` | `OBSERVED_STATIC_SOURCE` | Floor geometry only. |
| Depot include | Fuel URI `OpenRobotics/models/Depot`, pose `7.19009 1.09982 0 0 0 0`; no explicit `<name>` in this SDF | `OBSERVED_STATIC_SOURCE` | Exact Gazebo model/entity name is `NOT_ESTABLISHED_RUNTIME`. |
| `depot_collision` | Static model at `7.19009 1.09982 0 0 0 0`, link `collision_link` | `OBSERVED_STATIC_SOURCE` | Contains explicit world-collision primitives below. |
| `tugbot` include | Fuel URI `MovAi/models/Tugbot`, pose `2.75268 1.0014 0.132279 0 0 0` | `OBSERVED_STATIC_SOURCE` | Separate included model; its expanded collision names are not established here. |
| `ROBOT_URDF_final` | Spawned by launch after world start | `OBSERVED_STATIC_SOURCE` | Robot entity, not an SDF model declared inside `tugbot_depot.sdf`. |

## 2. Coordinate and frame inventory

| Name | Kind | Static-source evidence / pose or transform | Policy frame? | Status |
| --- | --- | --- | --- | --- |
| `world_demo` | Gazebo/SDF world identity/name | SDF `<world name='world_demo'>`; may be used by Gazebo service paths | No. It is not a ROS frame proven by this inventory. | `OBSERVED_STATIC_SOURCE`; coordinate-frame relation `REQUIRED_DECISION` |
| `world` | GT odometry runtime `header.frame_id` metadata | Passive timing report observed `/ground_truth/odom` metadata `world` to `base_link` | No. Hidden oracle/source frame candidate only under ACR S1. | `OBSERVED_RUNTIME_METADATA`; not the Gazebo world name and not TF-authority evidence |
| `ROBOT_URDF_final` | Spawned Gazebo model/entity | Launch `create -name ROBOT_URDF_final` at startup pose above | No | `OBSERVED_STATIC_SOURCE` |
| `base_link` | Robot link; child frame configured for odometry plugins | Root robot link; `MecanumDrive` and GT `OdometryPublisher` use `base_link` | No independent policy frame decision. | `OBSERVED_STATIC_SOURCE`; TF authority `NOT_ESTABLISHED_RUNTIME` |
| `odom` | MecanumDrive odometry frame configuration | `MecanumDrive` sets `frame_id=odom`, `child_frame_id=base_link` | No. ACR S1 says this legacy odometry is not canonical policy odometry. | `OBSERVED_STATIC_SOURCE`; TF authority `NOT_ESTABLISHED_RUNTIME` |
| `RPLiDAR_A1M8_1` | Robot LiDAR link and configured Gazebo sensor frame | Fixed `Lidar_Joint` from `base_link`; sensor config `frame_id=RPLiDAR_A1M8_1` | No canonical policy-frame selection is made here. | `OBSERVED_STATIC_SOURCE` |
| `ROBOT_URDF_final/RPLiDAR_A1M8_1/rplidar` | Runtime-observed scan `frame_id` | Passive timing evidence, not the static sensor configuration | No | `NOT_ESTABLISHED_RUNTIME` by source alone; reconciliation remains `REQUIRED_DECISION` |
| `Wheel_LF_1`, `Wheel_RF_1`, `Wheel_RB_1`, `Wheel_LB_1` | Wheel links / continuous-joint children of `base_link` | Xacro joint origins: LF `(0.108, 0.11109, -0.0175)`, RF `(0.108, -0.11109, -0.0175)`, RB `(-0.108, -0.11109, -0.0175)`, LB `(-0.108, 0.11109, -0.0175)` | No | `OBSERVED_STATIC_SOURCE`; runtime TF scope/name `NOT_ESTABLISHED_RUNTIME` |
| `IntelRealsense_D435_Multibody_1` | Fixed camera link | Fixed `Camera_Joint` origin `(0.043208, 0, 0.095165)` from `base_link` | No | `OBSERVED_STATIC_SOURCE` |
| `ground_plane`, `depot_collision`, `tugbot`, Depot include | World entities | Poses in Section 1 | No | `OBSERVED_STATIC_SOURCE`; runtime scoping `NOT_ESTABLISHED_RUNTIME` |

No row asserts an owner for any TF edge. In particular, odometry metadata
`world` to `base_link` is not a `world` to `odom` transform.

### Identity versus coordinate-frame mapping

| Value | Domain | Evidence | Is coordinate frame? | Is TF authority evidence? | Status |
| --- | --- | --- | --- | --- | --- |
| `world_demo` | Gazebo/SDF world identity/name | SDF world declaration and launch-selected world file | No: not proven as a ROS frame | No | `OBSERVED_STATIC_SOURCE` |
| `world` | ROS odometry message metadata | Passive report: `/ground_truth/odom.header.frame_id` | It is an observed frame ID, not a selected scenario frame | No | `OBSERVED_RUNTIME_METADATA` |
| `odom` | Legacy MecanumDrive odometry frame configuration | Robot Gazebo description config | It is a configured frame ID for legacy odometry metadata | No | `OBSERVED_STATIC_SOURCE`; runtime transform/owner `NOT_ESTABLISHED_RUNTIME` |
| `base_link` | Robot link and child-frame configuration | Xacro and odometry-plugin configuration | It is a source-declared link/frame name | No | `OBSERVED_STATIC_SOURCE`; runtime transform/owner `NOT_ESTABLISHED_RUNTIME` |

## 3. Static geometry inventory

All poses in `depot_collision/collision_link` below are SDF/model-local
geometry references relative to `depot_collision`, whose source-declared model
pose is `7.19009 1.09982 0 0 0 0`. They are not asserted to be coordinates in
the ROS frame ID `world`, and are not converted into an approved global task
region. Any conversion from SDF/model-local geometry to a future scenario
coordinate frame is `REQUIRED_DECISION` plus runtime evidence.

| Geometry group | Model/link/collision names | Geometry and static source detail | Classification |
| --- | --- | --- | --- |
| Floor | `ground_plane/link/collision` | Plane, normal `0 0 1`, size `1 1`; model pose `0 0 0 0 0 0` | `GEOMETRY_REFERENCE_ONLY`; candidate world collision, not a task boundary |
| Boundary walls | `depot_collision/collision_link/wall1`–`wall4` | Boxes: `wall1` and `wall2` size `30.167 0.08 9`, local poses `(0, -7.6129, 4.5)` and `(0, 7.2875, 4.5)`; `wall3` and `wall4` size `0.08 15.360 9`, local poses `(-15, 0, 4.5)` and `(15, 0, 4.5)` | `GEOMETRY_REFERENCE_ONLY`; candidate world collisions, not approved bounds |
| Box obstacles | `depot_collision/collision_link/boxes1`–`boxes11` | Boxes, each size `1.288 1.422 1.288`; local centers: `boxes1` `(0.22268,-4.7268,0.68506)`, `boxes2` `(3.1727,-4.7268,0.68506)`, `boxes3` `(5.95268,-4.7268,0.68506)`, `boxes4` `(8.55887,-4.7268,0.68506)`, `boxes5` `(11.326,-4.7268,0.68506)`, `boxes6` `(0.22268,-2.37448,0.68506)`, `boxes7` `(3.1727,-2.37448,0.68506)`, `boxes8` `(5.95268,-2.37448,0.68506)`, `boxes9` `(8.55887,-2.37448,0.68506)`, `boxes10` `(11.326,-2.37448,0.68506)`, `boxes11` `(-1.2268,4.1557,0.68506)` with yaw `-1.02799893` | `GEOMETRY_REFERENCE_ONLY`; candidate world collisions |
| Pillars | `depot_collision/collision_link/pilar1`–`pilar4` | Boxes, each size `0.465 0.465 2`; local centers `(-7.5402,3.6151,1)`, `(7.4575,3.6151,1)`, `(-7.5402,-3.8857,1)`, `(7.4575,-3.8857,1)` | `GEOMETRY_REFERENCE_ONLY`; candidate world collisions |
| Pallet movers | `depot_collision/collision_link/pallet_mover1`, `pallet_mover2` | Boxes: `pallet_mover1` size `0.363 0.440 0.719`, local center `(-0.6144,-2.389,0.41838)`; `pallet_mover2` size `0.363 0.244 0.719`, local center `(-1.6004,4.8225,0.41838)` | `GEOMETRY_REFERENCE_ONLY`; candidate world collisions |
| Stairs | `depot_collision/collision_link/stairs` | Box size `1.299 0.6 0.5`, local center `(13.018,3.1652,0.25)` | `GEOMETRY_REFERENCE_ONLY`; candidate world collision |
| Shelf/rack primitives | `depot_collision/collision_link/shelfs1`–`shelfs18` | Cylinders, each radius `0.03`, length `1`; local centers: x=`1.4662, 2.6483, 5.3247, 6.5063, 9.0758, 10.258` crossed with y=`-0.017559, 2.5664, 5.1497`, z=`0.5` | `GEOMETRY_REFERENCE_ONLY`; candidate world collisions |
| Depot visual include | Fuel Depot include, no collision primitives declared in this source file | Remote model URI and static include pose only | `GEOMETRY_REFERENCE_ONLY`; expanded geometry/names `NOT_ESTABLISHED_RUNTIME` |
| Robot base | `base_link` unnamed collision | Box size `0.4 0.28 0.10`, collision origin `0 0 0` | `GEOMETRY_REFERENCE_ONLY`; candidate robot collision |
| Robot wheels | `Wheel_LF_1`, `Wheel_RF_1`, `Wheel_RB_1`, `Wheel_LB_1`, each unnamed collision | Cylinders, radius `0.0485`, length `0.04`, collision rpy `1.5708 0 0` | `GEOMETRY_REFERENCE_ONLY`; candidate robot collision; wheel–ground policy unresolved |
| Robot camera | `IntelRealsense_D435_Multibody_1` unnamed collision | Mesh `IntelRealsense_D435_Multibody_1.stl`, collision origin `-0.043208 0 -0.095165` | `GEOMETRY_REFERENCE_ONLY`; candidate non-wheel robot collision |
| Robot LiDAR | `RPLiDAR_A1M8_1` unnamed collision | Cylinder radius `0.035`, length `0.03`, collision origin `0 0 -0.02` | `GEOMETRY_REFERENCE_ONLY`; candidate non-wheel robot collision |

The source geometry may support a future generated collision-name manifest.
It cannot be used to derive valid area, forbidden zones, clearance semantics,
or the collision policy. Any primitive extents calculable from the listed
boxes are **GEOMETRY_REFERENCE_ONLY — NOT_TASK_BOUNDARY**.

## 4. Robot identity and collision-manifest candidate

### 4.1 Static robot identity

| Category | Static names | Status |
| --- | --- | --- |
| Robot model/entity | Xacro robot name and launch spawn name: `ROBOT_URDF_final` | `OBSERVED_STATIC_SOURCE` |
| Base collision link | `base_link` with one unnamed box collision | `OBSERVED_STATIC_SOURCE` |
| Wheel collision links | `Wheel_LF_1`, `Wheel_RF_1`, `Wheel_RB_1`, `Wheel_LB_1`, each with one unnamed cylinder collision | `OBSERVED_STATIC_SOURCE` |
| Non-wheel robot collision links | `IntelRealsense_D435_Multibody_1` mesh collision; `RPLiDAR_A1M8_1` cylinder collision | `OBSERVED_STATIC_SOURCE` |
| Explicit world-collision candidates | `ground_plane/link/collision`, `depot_collision/collision_link/{wall1..wall4, boxes1..boxes11, pilar1..pilar4, pallet_mover1..pallet_mover2, stairs, shelfs1..shelfs18}` | `OBSERVED_STATIC_SOURCE` |

The exact scoped collision names emitted by Gazebo are
`NOT_ESTABLISHED_RUNTIME`: unnamed Xacro collision elements, model nesting,
remote includes, and Gazebo expansion determine their final scope. Therefore,
the table is a **manifest candidate**, not the requested/generated manifest.

### 4.2 Required collision ambiguities

| Ambiguity | Why static source cannot resolve it | Required decision/evidence |
| --- | --- | --- |
| Wheel–ground contact | Wheel cylinders and ground plane collide physically, but no policy says whether they count | User selects inclusion/exclusion; controlled runtime contact evidence validates it. |
| Self-contact | Xacro/Gazebo references set `self_collide=false` on base and wheels, but final runtime behavior/scope is not proven here | Confirm expanded model and contact-event behavior. |
| Sensor/body contacts | Camera and LiDAR links have collision geometry; source does not state whether their world contact is terminal | Explicit robot-versus-world filtering policy. |
| Visual-only and remote objects | Depot/tugbot include expansion is external to this file | Expanded-description checksum and scoped-name inventory. |
| Entity/collision scoping | Gazebo creates scopes after expansion/spawn | Runtime instrumentation evidence before a `ContactLatch` producer exists. |

No contact filter, plugin, bridge, topic, or `ContactLatch` policy is selected
by this inventory.

## 5. Existing start and goal evidence

| Evidence | Source value | Source | Status | Non-adoption boundary |
| --- | --- | --- | --- | --- |
| Launch startup pose | `ROBOT_URDF_final`: `(0, 0, 0.1, yaw 0)` | [gazebo.launch.py](../ros2_ws/src/ROBOT_URDF_final_description/launch/gazebo.launch.py) | `OBSERVED_STATIC_SOURCE` | It is startup configuration, not a scenario start set. |
| Legacy scenario mode | `fixed_waypoint` default; optional continuous free-space/map sampling | [mecanum_env.py](../ros2_ws/src/ROBOT_URDF_final_description/ROBOT_URDF_final_description/mecanum_env.py) | `NON_AUTHORITATIVE_CANDIDATE — NOT_ADOPTED` | Must not define the official scenario contract. |
| Legacy fixed waypoints | `(0,0)`, `(0,1.2)`, `(0,3.8)`, `(0,-1.0)`, `(0,-6.0)`, `(4,1.2)`, `(8,1.2)`, `(4,3.8)`, `(8,3.8)`, `(4,-1.0)`, `(8,-1.0)`, `(4,-6.0)`, `(8,-6.0)`, `(-2,1.2)`, `(-2,-1.0)`, `(-2,-6.0)` | [mecanum_env.py](../ros2_ws/src/ROBOT_URDF_final_description/ROBOT_URDF_final_description/mecanum_env.py) | `NON_AUTHORITATIVE_CANDIDATE — NOT_ADOPTED` | These coordinates are not copied into a scenario artifact. |
| Legacy goal/start distance and goal radius | Legacy fields include start-goal distance bounds and `goal_radius` | [mecanum_env.py](../ros2_ws/src/ROBOT_URDF_final_description/ROBOT_URDF_final_description/mecanum_env.py) | `NON_AUTHORITATIVE_CANDIDATE — NOT_ADOPTED` | No numerical threshold is adopted. |
| Legacy map sampling | Legacy package maps and optional map YAML path | Legacy environment source and `ROBOT_URDF_final_description/maps/` | `NON_AUTHORITATIVE_CANDIDATE — NOT_ADOPTED` | Architecture requires approved map/scenario artifacts outside mutable package source. |

## 6. Decision-ready handoff

| Decision | Evidence now available | Missing information | User decision | Runtime evidence before implementation |
| --- | --- | --- | --- | --- |
| T1: scenario/world identity | Launch path, SDF path, Gazebo/SDF world name `world_demo`, world SHA-256, static entities | Scenario artifact schema/location/version and allowed world revision | Select first training world and artifact identity; artifact must declare `gazebo_world_name` and `world_file_sha256` | Validate selected world/artifact hash before loading. |
| T2: start/goal/valid area/forbidden zones | Startup pose; static SDF/model-local primitive reference; legacy candidates not adopted | Approved coordinates/regions, `scenario_coordinate_frame`, sampling semantics, clearance/goal semantics, and source-geometry provenance | Select start region, goal region, valid area, forbidden zones, and the scenario coordinate frame | Validate poses/regions against the approved scenario and observed reset/oracle facts; prove any SDF/model-local-to-scenario-frame conversion. |
| T5: collision source/latch ownership | Candidate robot/world collision-link names and geometry | Contact source, scoped-name manifest, event timestamps, action interval, filtering | Decide which robot–world contacts are collisions and wheel–ground treatment | Controlled pulse/sustained-contact/reset/replay tests and generated scoped-name manifest. |

### User choices needed

1. The first world/scenario to train.
2. Start region.
3. Goal region.
4. Forbidden regions.
5. The official coordinate frame for start pose, goal, valid area, and forbidden zones.
6. The required authority/evidence if that frame requires conversion from Gazebo SDF/model-local coordinates.
7. Whether wall/rack contacts count as collision.
8. Whether wheel–ground contacts are excluded from collision.

Until those selections and the associated runtime evidence are approved, this
inventory is not a scenario artifact and cannot authorize a task oracle,
reset adapter, collision source, or Gymnasium environment.
