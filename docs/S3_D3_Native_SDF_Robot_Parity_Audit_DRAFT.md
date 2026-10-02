# S3 D3 Native SDF Robot Parity Audit

Status: `VISUAL_RESOURCE_PARITY_VALIDATED — RUNTIME NOT APPROVED`

## Scope and authority order

This audit inventories the route from the current URDF/Xacro topic-spawned
robot to a possible native SDF simulation model. Its S3.3.64 and S3.3.64R
appendices record the separately approved static-only model/checker changes;
they do not establish a runnable model. This document does not build, run
Gazebo/ROS/`gz`, spawn an entity, use a bridge, issue `RequestRaw`, publish a
command, invoke control, or touch hardware.

Authority was applied in this order:

1. installed official Gazebo Sim 8 / SDFormat 1.11 schemas, examples, shared
   libraries, package metadata, and `ros_gz_sim` Jazzy installation;
2. version-labelled official Gazebo Sim 8 API pages only where the installed
   material does not describe a system parameter; and
3. workspace source as inventory, never as proof of an undocumented Gazebo or
   ROS contract.

The key official local authorities are:

- SDFormat 1.11 [`sensor.sdf`](/opt/ros/jazzy/opt/sdformat_vendor/share/sdformat14/1.11/sensor.sdf) and [`contact.sdf`](/opt/ros/jazzy/opt/sdformat_vendor/share/sdformat14/1.11/contact.sdf);
- Gazebo Sim 8 [`contact_sensor.sdf`](/opt/ros/jazzy/opt/gz_sim_vendor/share/gz/gz-sim8/worlds/contact_sensor.sdf), [`mecanum_drive.sdf`](/opt/ros/jazzy/opt/gz_sim_vendor/share/gz/gz-sim8/worlds/mecanum_drive.sdf), and [`velocity_control.sdf`](/opt/ros/jazzy/opt/gz_sim_vendor/share/gz/gz-sim8/worlds/velocity_control.sdf); and
- installed plugin packages including `gz-sim8-mecanum-drive-system`,
  `gz-sim8-velocity-control-system`, `gz-sim8-odometry-publisher-system`, and
  `gz-sim8-joint-state-publisher-system`.

The official online Sim 8 API confirms the published system contracts for
[MecanumDrive](https://gazebosim.org/api/sim/8/classgz_1_1sim_1_1systems_1_1MecanumDrive.html)
and [VelocityControl](https://gazebosim.org/api/sim/8/classgz_1_1sim_1_1systems_1_1VelocityControl.html).

## 1. Current representations and route

| Representation | Current source | What it supplies | Parity consequence |
| --- | --- | --- | --- |
| ROS description | [ROBOT_URDF_final.xacro](../ros2_ws/src/ROBOT_URDF_final_description/urdf/ROBOT_URDF_final.xacro), with `.gazebo`, `.ros2control`, and materials includes | Links, joints, inertials, visual/collision geometry, and Gazebo-extension settings. | It is not a native SDF model and cannot be assumed to retain names after topic-spawn conversion. |
| Current Gazebo extensions | [ROBOT_URDF_final.gazebo](../ros2_ws/src/ROBOT_URDF_final_description/urdf/ROBOT_URDF_final.gazebo) | Model plugins plus camera, GPU LiDAR, and the current URDF-extension ContactSensor. | Every relevant extension must be represented or explicitly excluded in a future native model. |
| Current topic-spawn route | [gazebo.launch.py](../ros2_ws/src/ROBOT_URDF_final_description/launch/gazebo.launch.py) | Xacro → `/robot_description` → `ros_gz_sim create -topic`; also starts bridge and static TF. | It is not the native-twin route and contains command/bridge paths prohibited for a future D3 observation route. |
| Native skeleton | [model.sdf](../ros2_ws/src/ROBOT_URDF_final_description/models/ROBOT_URDF_final/model.sdf) and [model.config](../ros2_ws/src/ROBOT_URDF_final_description/models/ROBOT_URDF_final/model.config) | Exact model name, one named base box collision, and one native ContactSensor. | Explicitly `STATIC_CONTACT_TWIN_NOT_RUNTIME_READY`; it is not a robot replacement. |
| World systems | [tugbot_depot.sdf](../ros2_ws/src/ROBOT_URDF_final_description/launch/tugbot_depot.sdf) | Physics, Contact, Sensors, SceneBroadcaster, Imu, and world geometry. | A future native model must use the existing world systems without duplicating or assuming their runtime binding. |

## 2. Mandatory parity matrix

Status meanings:

- `CONFIRMED`: source inventory plus version-matched official schema/example/API
  establishes a direct native-SDF representation or stated system parameter.
- `UNRESOLVED`: no sufficient official version-matched contract was found for a
  safe source-to-native mapping.
- `NEEDS_RUNTIME_EVIDENCE`: static mapping can be written, but binding,
  delivery, identity, or behavior needs an approved runtime observation.

| Group | Source URDF/Xacro/Gazebo field | Native SDF target | Official authority | Status |
| --- | --- | --- | --- | --- |
| Identity/resources | URDF robot and current `model.config` name: `ROBOT_URDF_final` | `<model name="ROBOT_URDF_final">` plus `model.config` reference to `model.sdf` | Native skeleton parsed by installed SDFormat; Gazebo resource packaging semantics for the workspace install route are not otherwise documented locally. | `CONFIRMED` for literal identity; `UNRESOLVED` for end-to-end resource discovery. |
| Identity/resources | `file://$(find ...)/meshes/*.stl` URDF mesh references | Native SDF mesh URI strategy and installed resource path | SDF geometry is schema-supported; no official local contract maps these ROS substitution URIs to native-model discovery. | `UNRESOLVED` |
| Physics | `base_link`: mass `2`, full inertia matrix, mesh visual, named `0.4 0.28 0.10` box collision | Native `<link>`, `<inertial>`, `<visual>`, named `<collision>`, poses | SDFormat link/geometry syntax; current static SDF contact twin confirms only the box collision. | `CONFIRMED` for representability; `NEEDS_RUNTIME_EVIDENCE` for physics equivalence. |
| Physics | Four wheel links: each mass `0.15`, inertial matrix, mesh visual, cylinder collision (`r=0.0485`, `l=0.04`) | Four native links with exact inertials, joint-relative frames, and primitive cylinder collisions; visuals remain excluded | Installed SDFormat 1.11 `link.sdf`, `inertial.sdf`, and `geometry.sdf`; S3.3.64R checker verifies exact literals. | `CONFIRMED` for static primitive/inertial representation; `DEFERRED_RESOURCE_PARITY` for visuals. |
| Physics | Camera mass `0.35`, mesh visual/collision; LiDAR mass `0.7`, mesh visual and cylinder collision | Native links with exact inertials, fixed-joint-relative frames, and the two approved visual meshes | SDFormat 1.11 link/inertial/pose schema supports the structural literals; S3.3.67 establishes the two installed visual mesh URIs; historical DART mesh warning does not establish a native-twin geometry result. | `CONFIRMED` for static inertial/frame and approved visual-resource representation; `DEFERRED_RESOURCE_PARITY` only for camera mesh collision, LiDAR collision beyond approved primitives, and remaining resource details; `NEEDS_RUNTIME_EVIDENCE` for live loader/rendering behavior. |
| Physics | Gazebo extension on `base_link`: `mu1=0.2`, `mu2=0.2`, `self_collide=false`, `gravity=true`; wheel `mu1=mu2=0.0`, `self_collide=false` | Native SDF surface friction, self-collide, gravity equivalents if semantically matched | No version-matched official local mapping from these URDF Gazebo-extension fields to the exact native Sim 8 behavior was found. | `UNRESOLVED` |
| Kinematics | `Wheel_LF_Joint`, `Wheel_RF_Joint`, `Wheel_RB_Joint`, `Wheel_LB_Joint`: continuous, each parent `base_link`, specified pose, child wheel, axis `0 1 0` | Four named native SDF continuous joints: joint pose `relative_to="base_link"`; child-link zero pose `relative_to` its joint; axis `expressed_in="base_link"` | SDFormat 1.11 `joint.sdf` and `pose.sdf`; installed Sim 8 joint-tree example uses parent-relative joint and joint-relative child-link poses. | `CONFIRMED` for static pose/frame syntax and copied literals; limits/damping/friction remain unresolved. |
| Kinematics | Source has no explicit `<limit>` or `<dynamics>` for the four continuous wheel joints | Explicit decision whether native SDF relies on schema defaults or receives an approved equivalent | No source value exists to copy; no default may be assumed equivalent to current runtime behavior. | `UNRESOLVED` |
| Kinematics | `Camera_Joint` and `Lidar_Joint`: fixed, parent `base_link`, specified child poses; current extension asks `preserveFixedJoint=true` | Native fixed joints with parent-relative joint poses and joint-relative zero child poses | SDFormat 1.11 `joint.sdf` and `pose.sdf` validate the explicit frame graph. Fixed-joint preservation behavior and runtime identity remain unproven. | `CONFIRMED` for static frame representation; `NEEDS_RUNTIME_EVIDENCE` for runtime behavior. |
| MecanumDrive | Plugin `gz-sim-mecanum-drive-system` / `gz::sim::systems::MecanumDrive` under current model extension | Native model-scope `<plugin>` with exact four joint names | Official Sim 8 MecanumDrive API and installed `mecanum_drive.sdf`: model scope; all four wheel-joint element groups required at least once. | `CONFIRMED` for scope/joint dependency. |
| MecanumDrive | `wheel_separation=0.22218`, `wheelbase=0.216`, `wheel_radius=0.0485` | Same plugin parameters, after parity review | Official Sim 8 API: optional but recommended MecanumDrive parameters. | `CONFIRMED` for parameter names; `NEEDS_RUNTIME_EVIDENCE` for motion equivalence. |
| MecanumDrive | `/cmd_vel`, `/odom`, `/tf`, `frame_id=odom`, `child_frame_id=base_link`; no explicit `odom_publish_frequency` | Same parameters only if future approved runtime boundary permits them | Official Sim 8 API confirms `<topic>` subscribes to command velocity and `<odom_topic>`, `<tf_topic>`, `<frame_id>`, `<child_frame_id>` configure outputs. | `CONFIRMED`: raw command path exists in the current plugin configuration; `UNRESOLVED` whether it may be retained in a D3-native route. |
| VelocityControl | Plugin `gz-sim-velocity-control-system` / `gz::sim::systems::VelocityControl`, `<topic>/cmd_vel</topic>` | Model-scope native plugin only after a separate command-authority decision | Official Sim 8 API: model-attached system; `<topic>` receives commands, default model `cmd_vel`. | `CONFIRMED`: current raw command path exists; `UNRESOLVED`: coexistence with MecanumDrive and approved final-command ownership. |
| OdometryPublisher | Plugin `gz-sim-odometry-publisher-system` / `gz::sim::systems::OdometryPublisher`; `world`, `base_link`, `50`, `/ground_truth/odom`, `dimensions=2`, zero noise | Model-attached native plugin with exact parameter mapping | Official Sim 8 namespace/API establishes model/entity odometry publishing. No local version-matched parameter reference was found for every current field. | `UNRESOLVED` |
| JointStatePublisher | Plugin `gz-sim-joint-state-publisher-system` / `gz::sim::systems::JointStatePublisher`; topic `/joint_states` | Model-scope native plugin with exact topic and joint selection policy | Installed Sim 8 examples show model-scoped plugin; the available official parameter page found was not version-matched to Sim 8. | `UNRESOLVED` |
| World systems | Physics, Contact, Sensors exist at world scope; Sensors has `ogre2` | Retain one world-level system set; native model must not duplicate these plugins | Installed Sim 8 contact example places Physics and Contact at world scope; current world is XML-parseable after S3.3.62. | `CONFIRMED` for world-system scope; `NEEDS_RUNTIME_EVIDENCE` for binding. |
| Contact sensor | Exact native base link collision/sensor: target `s3_d3_base_contact_collision`, topic `/s3_d3/contact/raw`, `always_on=true`, `update_rate=100` | Keep unchanged in same native `base_link` | SDFormat 1.11 `sensor.sdf` / `contact.sdf` and installed Sim 8 contact example. | `CONFIRMED` structurally; `NEEDS_RUNTIME_EVIDENCE` for endpoint and payload. |
| LiDAR | GPU LiDAR `rplidar`: topic `/scan`, rate `10`, pose `0 0 0.05 0 0 0`, frame ID, ray scan/range fields | Link-owned native `gpu_lidar` sensor with equivalent fields/resources | Native Sim 8 GPU-LiDAR example is installed, but no source-to-native model mapping has been specified or validated. | `UNRESOLVED` |
| Camera | Camera `realsense_camera`: `camera/image_raw`, rate `30`, FOV/image/clip, visualization | Link-owned native camera sensor with equivalent fields/resources | Native camera example is installed, but source-to-native model mapping and rendering/resource behavior are unverified. | `UNRESOLVED` |
| ROS description/TF | `robot_state_publisher` receives Xacro `/robot_description`; current broad launch also creates static TF | ROS-only description/TF plan kept separate from native Gazebo model loading | `robot_state_publisher` is a ROS process, not an SDF model feature. Existing launch source is inventory only. | `UNRESOLVED` |
| ROS/Gazebo boundary | Broad launch `ros_gz_bridge` maps `/cmd_vel`, odom, GT odom, scan, camera, TF, clock, joint states; dedicated typed-scene launch deliberately has none | Explicitly separate future bridge policy; no bridge may be inferred from model parity | Existing source proves configured mappings, not approval or correct delivery. | `UNRESOLVED` |
| Spawn | Topic route: `ros_gz_sim create -topic /robot_description -name ROBOT_URDF_final` | Future native model load/spawn method and resource resolution | Local `ros_gz_sim create` binary and launch sources prove the current topic route, but no approved native-model route exists. | `UNRESOLVED` |

## 3. Plugin/system inventory and command boundary

| System | Current source scope | Native SDF scope evidenced by official material | Parameters observed in source | Command/raw path evidence |
| --- | --- | --- | --- | --- |
| `VelocityControl` | URDF Gazebo model extension | Model | `/cmd_vel` | Its official Sim 8 `<topic>` contract is command input; current source therefore has a raw `/cmd_vel` path. |
| `MecanumDrive` | URDF Gazebo model extension | Model | Four wheel joints, dimensions/radius, `/cmd_vel`, odom/TF topics and frames | Its official Sim 8 `<topic>` contract is command input; current source therefore has a second raw `/cmd_vel` path. |
| `OdometryPublisher` | URDF Gazebo model extension | Entity/model attachment is official; exact source-field mapping unresolved | world/base frame, 50 Hz, GT odom, dimensions, zero noise | Publishes Gazebo odometry; no ROS bridge or TF parity is inferred. |
| `JointStatePublisher` | URDF Gazebo model extension | Model in installed examples | `/joint_states` | Publishes Gazebo model joint state; no ROS delivery is inferred. |
| `Contact` | World | World | no model-local configuration | It manages contact sensors; endpoint/payload still require runtime evidence. |
| `Sensors` | World | World | `ogre2` render engine | Manages sensors; does not prove camera/LiDAR/contact configuration survived or published. |

The authoritative architecture permits only FinalTwistPublisher to publish ROS
`/cmd_vel`. This audit does not change that locked contract. It records only
that the existing Gazebo plugins are separately configured with a raw topic
literal; no native-twin route may retain, bridge, publish, or test that path
without a separate architecture decision and bounded evidence.

## 4. ROS-facing identity boundary

| Concern | ROS-only responsibility | Native SDF responsibility | Current parity state |
| --- | --- | --- | --- |
| `ROBOT_URDF_final` identity | `robot_description` and robot_state_publisher naming | Native `<model name>` | Same literal is static; dual-spawn avoidance is unresolved. |
| `/robot_description` | Produced from current Xacro by ROS launch | None unless a future native-load route expressly consumes it | Native model does not replace this ROS parameter automatically. |
| TF | ROS robot_state_publisher / bridge / localization authority | Link and joint names/poses only | Static link names can be mirrored; TF edges and publisher authority are unresolved. |
| Odom and joint states | ROS bridge/consumers determine ROS endpoints | Gazebo plugin messages and topic settings only | Existing source mapping is not a native-model parity guarantee. |
| Scan and camera | ROS bridge/consumers determine ROS endpoints | Native sensor configuration only | Sensor topic/frame/render parity is unresolved. |

## 5. Required parity inventory before any runnable model claim

The current native skeleton intentionally omits every item in this table:

| Required group | Exact source inventory to reconcile | Why static source alone is insufficient |
| --- | --- | --- |
| Inertials and poses | Seven links: base, four wheels, camera, LiDAR; all source inertias and link/joint poses | Static literal/frame mapping is implemented; physical equivalence still requires later evidence. |
| Wheel train | Four links, four continuous joints, axes, cylinder geometry, all wheel plugins' joint references | Mecanum system binding and wheel behavior need model-level and runtime proof. |
| Sensor frames/resources | Camera and LiDAR visual/collision meshes, sensor pose/frame/topic/update fields, `ogre2` dependency | Rendering/sensor output and URI resolution cannot be inferred from XML presence. |
| Plugin coexistence | VelocityControl, MecanumDrive, OdometryPublisher, JointStatePublisher | Existing dual command topic and plugin behavior cannot be adopted into the native route without an approved command/ownership decision. |
| ROS-facing topology | Description, TF, bridge directions, odom, joint state, scan, camera | Native SDF does not own ROS publishers or bridges. |
| Contact producer evidence | World Contact system, native sensor, actual endpoint/type/payload | A static sensor is not raw contact delivery and not a collision fact. |

## 5A. S3.3.64 implemented static kinematics

S3.3.64 used the installed SDFormat 1.11 [`link.sdf`](/opt/ros/jazzy/opt/sdformat_vendor/share/sdformat14/1.11/link.sdf), [`joint.sdf`](/opt/ros/jazzy/opt/sdformat_vendor/share/sdformat14/1.11/joint.sdf), [`inertial.sdf`](/opt/ros/jazzy/opt/sdformat_vendor/share/sdformat14/1.11/inertial.sdf), and [`geometry.sdf`](/opt/ros/jazzy/opt/sdformat_vendor/share/sdformat14/1.11/geometry.sdf). They establish link-owned inertial/collision elements and the `continuous` and `fixed` joint forms used here. The installed Sim 8 `mecanum_drive.sdf` was read only to keep future wheel-joint names aligned; no plugin was added.

The native model now contains exactly these seven links and six joints:

```text
links:  base_link, Wheel_LF_1, Wheel_RF_1, Wheel_RB_1, Wheel_LB_1,
        IntelRealsense_D435_Multibody_1, RPLiDAR_A1M8_1
joints: Wheel_LF_Joint, Wheel_RF_Joint, Wheel_RB_Joint, Wheel_LB_Joint,
        Camera_Joint, Lidar_Joint
```

Every source inertial pose, mass, and six inertia components is copied as the exact source literal. The base box and four wheel cylinder collisions are the only primitive collision parity now implemented. The existing native ContactSensor literals remain unchanged. The checker rejects a missing link, wrong wheel parent/child, wrong axis, changed inertial, or any plugin.

| Parity category | S3.3.64 state | Boundary |
| --- | --- | --- |
| Link/joint topology, joint poses/axes, inertial literals, base box, wheel cylinders | `IMPLEMENTED_STATIC_KINEMATICS` | XML/SDF validity does not prove physics behavior. |
| Camera/LiDAR visual meshes; camera mesh collision and non-visual resource parity | `VISUAL_RESOURCE_PARITY_VALIDATED` for the two approved visual mesh URIs; `DEFERRED_RESOURCE_PARITY` for camera mesh collision and remaining resource details | S3.3.67 added only the two authority-backed native visuals. Camera mesh collision, LiDAR collision/resource details beyond those visuals, and sensor/resource behavior remain deferred. |
| Friction, `mu1`/`mu2`, gravity, self-collision, limits, damping, plugin parameters, and all model plugins | `DEFERRED_PHYSICS_OR_PLUGIN_PARITY` | No default or extension-to-native mapping is assumed. |
| Contact endpoint, Mecanum/plugin binding, odometry, joint state, scan, camera, ROS description/TF, bridge behavior, and motion | `RUNTIME_EVIDENCE_REQUIRED` or separate official-contract decision | No runtime claim follows. |

## 5B. S3.3.64R pose-frame semantics repair

The initial S3.3.64 model was XML/SDF-valid but had `SYNTAX_VALID_BUT_POSE_SEMANTICS_INCOMPLETE`: SDFormat 1.11 [`joint.sdf`](/opt/ros/jazzy/opt/sdformat_vendor/share/sdformat14/1.11/joint.sdf) states that a joint pose defaults to the child-link frame, whereas the source URDF `<joint><origin>` is the zero-configuration transform from the parent link to the child link. [`pose.sdf`](/opt/ros/jazzy/opt/sdformat_vendor/share/sdformat14/1.11/pose.sdf) supports `relative_to` in SDFormat 1.11, and `joint.sdf` supports `axis/xyz@expressed_in`. The installed Sim 8 [`joint_trajectory_controller.sdf`](/opt/ros/jazzy/opt/gz_sim_vendor/share/gz/gz-sim8/worlds/joint_trajectory_controller.sdf) provides a native joint-tree example with parent-relative joint poses and child-link poses relative to their joints.

The corrected static mapping is:

```text
URDF joint origin: parent base_link → child link at zero configuration
  → SDF joint pose relative_to=base_link with the exact URDF origin literal
  → SDF child-link pose relative_to=<exact joint name> set to 0 0 0 0 0 0
```

For each wheel, the unmodified source vector `0.0 1.0 0.0` is now explicit as `axis/xyz expressed_in="base_link"`. All six URDF origins have zero RPY, so the joint and `base_link` axes have the same zero-configuration orientation. The checker rejects absent/wrong joint `relative_to`, a wrong wheel/camera/LiDAR child-link frame relation, and an incorrect wheel axis expression. It also continues to reject literal changes, plugins, ROS/control paths, unapproved visual/mesh entries, and generated/lumped collision names.

## 5C. S3.3.65 package-install parity

`setup.py` already declares `data_files` for `models/ROBOT_URDF_final/*` at the exact ament Python destination `share/ROBOT_URDF_final_description/models/ROBOT_URDF_final`. No packaging-source change was required. A single package-only `python3 -m colcon build --packages-select ROBOT_URDF_final_description --symlink-install` completed; `python` itself is not installed in this environment, so the equivalent Python 3 invocation was necessary.

After sourcing the generated install setup, `ros2 pkg prefix ROBOT_URDF_final_description` resolved to `/home/hazan/mecanum_autonomy_ws/ros2_ws/install/ROBOT_URDF_final_description`. The installed files are regular files at:

```text
install/ROBOT_URDF_final_description/share/ROBOT_URDF_final_description/
  models/ROBOT_URDF_final/model.sdf
  models/ROBOT_URDF_final/model.config
```

The resolved installed content exactly matches source:

| File | Source/install SHA-256 | Result |
| --- | --- | --- |
| `model.sdf` | `6e188db9f318b6ca9ea460e7a07d5ea468b010a59c448a015b66bf2e9211533f` | Exact content parity |
| `model.config` | `3f5637ce2177dd1ecc8eaa4bc0ef2b104fba794f692697adfb7578eae374e4ed` | Exact content parity |

The static checker now has an explicit `--installed-package-share` mode. It fixes the two installed file names beneath `models/ROBOT_URDF_final`, rejects missing/non-regular files, rejects an unexpected symlink target, rejects a resolved model directory outside the package share, compares SHA-256 content, and re-runs the native contact and pose-frame contract on the installed SDF/config. Source and installed XML parsing plus `gz sdf -k` pass. This establishes install artifact parity only; it does not authorize model discovery, native spawning, Gazebo, ROS, plugins, bridge, or any runtime behavior.

## 5D. S3.3.67 visual-resource parity

S3.3.67 used the installed SDFormat 1.11 [`visual.sdf`](/opt/ros/jazzy/opt/sdformat_vendor/share/sdformat14/1.11/visual.sdf), [`geometry.sdf`](/opt/ros/jazzy/opt/sdformat_vendor/share/sdformat14/1.11/geometry.sdf), [`mesh_shape.sdf`](/opt/ros/jazzy/opt/sdformat_vendor/share/sdformat14/1.11/mesh_shape.sdf), and [`pose.sdf`](/opt/ros/jazzy/opt/sdformat_vendor/share/sdformat14/1.11/pose.sdf), plus the S3.3.66 installed-resource evidence. `visual.sdf` requires a unique name per parent link and geometry; `mesh_shape.sdf` requires `uri` and supports `scale`; `pose.sdf` supports the explicit link-relative frame relation used here.

Exactly two native visuals are now present, with no native material, texture, sensor, or collision addition:

| Link | Static visual identity | URI | Pose relative to link | Scale | Source authority |
| --- | --- | --- | --- | --- | --- |
| `IntelRealsense_D435_Multibody_1` | `s3_d3_camera_visual` | `ROBOT_URDF_final_description/meshes/IntelRealsense_D435_Multibody_1.stl` | `-0.043208 0.0 -0.095165 0 0 0` | `0.001 0.001 0.001` | Exact source URDF visual origin and mesh scale; installed mesh lookup evidence in S3.3.66. |
| `RPLiDAR_A1M8_1` | `s3_d3_lidar_visual` | `ROBOT_URDF_final_description/meshes/RPLiDAR_A1M8_1.stl` | `-0.0432 0.0 -0.107565 0 0 0` | `0.001 0.001 0.001` | Exact source URDF visual origin and mesh scale; installed mesh lookup evidence in S3.3.66. |

The source URDF visuals have no visual names. The two deterministic SDF names above are static XML identities required by SDFormat, not ROS, Gazebo transport, or entity identities. The checker requires exactly those two visuals, rejects changed URI/pose/scale, a missing or second visual, a wheel/base visual, a camera/LiDAR collision addition, and all previously prohibited plugin/control/generated-collision changes.

`model.config` remains unchanged by explicit scope; its historical static-twin prose does not grant runtime readiness. Camera mesh collision, LiDAR collision/resource parity beyond this visual, materials/textures, physics, plugins, ROS, and all runtime behavior remain deferred.

## 6. Conclusion and smallest safe next increment

```text
VISUAL_RESOURCE_PARITY_VALIDATED — RUNTIME NOT APPROVED
```

The native ContactSensor shape, seven-link/six-joint topology, explicit URDF-to-SDF pose-frame relations, permitted primitive collisions, source inertial literals, and the two installed-resource visual meshes are now statically implemented and validated. A runnable native robot still cannot be claimed:
resource parity, plugin contracts, command ownership, ROS-facing topology, and
sensor/plugin binding remain deferred or runtime-only.

The S3.3.69 dedicated native world-only launch is now statically validated. Camera mesh collision, LiDAR collision/resource details beyond the installed visual mesh, physics/plugin/ROS-boundary work, and all runtime behavior each still require separate approval and evidence; no runtime execution follows from this audit.

## Non-claims

This audit does not establish that the native twin replaces the URDF route,
that any plugin binds correctly, that TF/odom/scan are preserved, that raw
Contacts are published, or that collision, ContactLatch, reward, termination,
Gym/training, or hardware behavior is ready.
