# S3 D3 Native SDF ContactSensor Migration Design

Status: `IMPLEMENTED_STATIC_ONLY — RUNTIME NOT APPROVED`

## Scope and decision boundary

This is a read-only migration design. It neither changes the current URDF,
Xacro, SDF world, launch route, ContactSensor, plugin configuration, bridge,
guard, packet, or historical evidence, nor authorizes a runtime run. It does
not select collision policy, create ContactLatch, or establish a contact event,
termination, reward, training, or hardware behavior.

The narrow design objective is a future simulation representation in which
`s3_d3_base_contact_sensor` and `s3_d3_base_contact_collision` are native SDF
siblings under the same SDF `<link>`. This removes the ContactSensor target's
dependency on a collision name that a URDF-to-SDF conversion may rewrite during
fixed-joint lumping.

## 0. S3.3.61B static implementation and official schema authority

The installed official SDFormat 1.11 schema [contact.sdf](/opt/ros/jazzy/opt/sdformat_vendor/share/sdformat14/1.11/contact.sdf) defines `contact/collision` and required `contact/topic`. Its companion [sensor.sdf](/opt/ros/jazzy/opt/sdformat_vendor/share/sdformat14/1.11/sensor.sdf) defines `always_on` and `update_rate` as sensor children. The installed official Gazebo Sim 8 native example [contact_sensor.sdf](/opt/ros/jazzy/opt/gz_sim_vendor/share/gz/gz-sim8/worlds/contact_sensor.sdf) uses the same hierarchy. The local authorities agree, so no schema ambiguity remains.

S3.3.61B creates only these static artifacts:

- [model.sdf](../ros2_ws/src/ROBOT_URDF_final_description/models/ROBOT_URDF_final/model.sdf), with one native model, `base_link`, named box collision, and native contact sensor;
- [model.config](../ros2_ws/src/ROBOT_URDF_final_description/models/ROBOT_URDF_final/model.config), explicitly marked `STATIC_CONTACT_TWIN_NOT_RUNTIME_READY`; and
- [static checker](../ros2_ws/src/ROBOT_URDF_final_description/test/check_native_sdf_contact_twin.py), which XML-parses the model and world and rejects disallowed topology and literals.

`setup.py` installs this exact model directory. No package build is performed by S3.3.61B. The user-approved raw-evidence update rate is `100` Hz, with this exact sensor structure:

```xml
<sensor name="s3_d3_base_contact_sensor" type="contact">
  <always_on>true</always_on>
  <update_rate>100</update_rate>
  <contact>
    <collision>s3_d3_base_contact_collision</collision>
    <topic>/s3_d3/contact/raw</topic>
  </contact>
</sensor>
```

The model deliberately has no parity for inertial properties, wheel links/joints, Mecanum or other model plugins, LiDAR/camera, visuals, ROS `robot_description`/TF, or mesh/resource URIs. It must not be launched or treated as a runnable robot.

Static validation passes for the native `model.sdf` through both XML parsing and the installed non-server `gz sdf -k` validator. The checker’s package/model and negative fixtures also pass. S3.3.62 corrected the current `tugbot_depot.sdf` declaration from `ASCII` to `UTF-8` after byte-level UTF-8 verification; the standard XML parser and the checker now verify exactly one world Contact system. `gz sdf -k` still cannot complete world validation because its two remote Fuel includes are unavailable offline (`REMOTE_INCLUDE_UNRESOLVED`), which is separate from XML validity.

Inputs audited:

- [Robot Xacro](../ros2_ws/src/ROBOT_URDF_final_description/urdf/ROBOT_URDF_final.xacro)
- [Gazebo extension](../ros2_ws/src/ROBOT_URDF_final_description/urdf/ROBOT_URDF_final.gazebo)
- [World](../ros2_ws/src/ROBOT_URDF_final_description/launch/tugbot_depot.sdf)
- [Dedicated typed-Scene launch](../ros2_ws/src/ROBOT_URDF_final_description/launch/typed_scene_observer.launch.py)
- [S3.3.58 static conversion audit](S3_D3_Base_Collision_ContactSensor_Static_Conversion_Audit.md)
- [URDF-to-SDF conversion audit](S3_D3_URDF_To_SDF_ContactSensor_Conversion_Static_Audit_DRAFT.md)
- [ContactLatch contract](S3_D3_ContactLatch_And_Collision_Fact_Contract_DRAFT.md)

## 1. Current source route and fixed-joint inventory

`base_link` is the Xacro root link. It has mass `2` and one explicitly named
box collision, `s3_d3_base_contact_collision`, at the link origin with size
`0.4 0.28 0.10`. The Xacro's four wheel joints are `continuous`, not fixed.
The only fixed joints directly below `base_link` are:

| Fixed joint | Parent | Child | Child mass | Existing Gazebo extension |
| --- | --- | --- | ---: | --- |
| `Camera_Joint` | `base_link` | `IntelRealsense_D435_Multibody_1` | `0.35` | `<preserveFixedJoint>true</preserveFixedJoint>` |
| `Lidar_Joint` | `base_link` | `RPLiDAR_A1M8_1` | `0.7` | `<preserveFixedJoint>true</preserveFixedJoint>` |

The child links each have an inertial element and collision geometry. The
camera uses a mesh collision; the LiDAR uses its source-defined geometry. The
fixed-joint path is therefore:

```text
base_link
├── Camera_Joint (fixed) → IntelRealsense_D435_Multibody_1
└── Lidar_Joint  (fixed) → RPLiDAR_A1M8_1
```

The current Gazebo extension places the contact sensor under
`<gazebo reference="base_link">` and gives it the approved source literals:

| Field | Current value |
| --- | --- |
| Sensor | `s3_d3_base_contact_sensor` |
| Source target | `s3_d3_base_contact_collision` |
| Topic | `/s3_d3/contact/raw` |
| Sensor mode | `contact`, `always_on=true` |

The world already declares the built-in world-scope
`gz::sim::systems::Contact` system. The robot extension also declares the
existing VelocityControl, MecanumDrive, OdometryPublisher, and
JointStatePublisher model plugins. Their presence is inventory only: this
design does not claim that they are compatible with any future native-SDF
twin without separate validation.

## 2. Why the current route is unsuitable as a stable target-name contract

The dedicated typed-Scene route renders the Xacro to `/robot_description`, then
the supervisor-owned `ros_gz_sim create` consumes that description. The source
and rendered URDF each contain the exact approved collision and sensor
literals. However, the S3.3.58 temporary local conversion using `gz sdf -p`
produced this collision name:

```text
base_link_fixed_joint_lump__s3_d3_base_contact_collision_collision
```

while retaining the sensor's source target literal
`s3_d3_base_contact_collision`. That is an observed conversion-level name
rewrite. It does not prove that `ros_gz_sim create -topic /robot_description`
uses that identical conversion path, nor does it prove the spawned collision
or sensor was absent.

It does prove a design hazard: source-name equality and converter-output-name
equality cannot both be assumed. The historical S3.3.54 DART warning named
`base_link_collision`, a different literal from both the approved source name
and the printed converted name. It is not evidence that any of those three
names denote the same runtime collision.

No exact fixed joint can be identified from static evidence as *the* joint
that causes this output-name rewrite. Both relevant fixed joints already have
`preserveFixedJoint=true`, yet the local conversion still rewrites the base
collision name. The existing preserve directives therefore do not establish a
stable collision-name contract for the topic-driven spawn route.

## 3. Options assessed

| Option | Design | Static evidence and required conditions | Main risks |
| --- | --- | --- | --- |
| A. Native SDF simulation model/twin | Define the simulation robot in native SDF. Put the named box collision and contact sensor in the same SDF `<link name="base_link">`; target the exact local collision name. | The installed Gazebo Sim 8 `contact_sensor.sdf` example uses this native structure, and the current world already declares the Contact system. Exact identity is authored directly in the representation Gazebo consumes. | The native model must reproduce required inertial, joint, plugin, resource, and spawn behavior without silently changing ROS description, TF, wheel, or motion semantics. |
| B. Keep URDF spawn and preserve fixed joints | Retain URDF/Xacro and add or alter conversion-preservation directives so the final collision name remains usable by the sensor. | `Camera_Joint` and `Lidar_Joint` are the only fixed joints direct from `base_link`; both already have preserve directives and nonzero inertials/masses. No local evidence identifies an additional exact joint directive that would make the collision name stable in the actual `ros_gz_sim create` conversion. | It may change link/inertia aggregation or physics behavior; it may still fail to preserve the sensor extension or collision name. Targeting a generated/lumped name would couple the contract to an unproven converter implementation. |

### Option B fail-closed boundary

There is no statically evidenced exact joint to add to or remove from
`preserveFixedJoint` for this purpose. Any future B proposal would first need
to establish all of the following without using an auto-generated collision
name as a contract:

1. the exact conversion behavior of the installed topic-spawn route;
2. the responsible fixed-joint transformation, if any;
3. preservation of the link's and child links' mass, inertial, pose, and
   collision semantics; and
4. unchanged behavior of wheel, motion, sensor, and TF-related paths.

Those conditions are not presently demonstrated. This document therefore does
not recommend B and does not propose a generated-name target.

## 4. Recommendation — native SDF simulation twin (Option A)

**Recommendation: Option A, a native SDF simulation twin, subject to explicit
user approval.** It is preferred because the source already shows that the
only direct fixed joints have preservation directives, while the static
conversion nevertheless rewrites the collision name. Option A makes the
contact target local, explicit, and independent of that unproven conversion
behavior.

The simulation twin remains owned by `ROBOT_URDF_final_description`, the
existing owner of robot description, Gazebo model/world, and static geometry.
The ROS URDF/Xacro remains the separate source for `robot_description` and
TF-facing use. This is not a claim that the two representations are already
equivalent; the future implementation must make each shared identity and
physics/motion assumption explicit and validate it.

### Proposed native SDF shape — not implementation

The following is a shape constraint, not a patch. The collision and sensor
must be authored under the *same* native SDF link, with the target equal to the
locally authored collision name:

```xml
<model name="ROBOT_URDF_final">
  <link name="base_link">
    <!-- future approved inertial, visual, and other link content -->
    <collision name="s3_d3_base_contact_collision">
      <pose>0 0 0 0 0 0</pose>
      <geometry><box><size>0.4 0.28 0.10</size></box></geometry>
    </collision>
    <sensor name="s3_d3_base_contact_sensor" type="contact">
      <contact>
        <collision>s3_d3_base_contact_collision</collision>
        <topic>/s3_d3/contact/raw</topic>
      </contact>
      <always_on>true</always_on>
    </sensor>
  </link>
</model>
```

The world-level `gz::sim::systems::Contact` declaration is a required paired
configuration. Its existing presence does not prove endpoint advertisement or
message delivery. The future implementation must keep the raw topic as raw
producer evidence only. `TouchPlugin` is not an alternative here: it would not
provide the raw `Contacts` fact required for the later ContactLatch evidence
path.

## 5. Identity, bootstrap, and plugin constraints

The native simulation model must preserve the externally approved spawn
identity `ROBOT_URDF_final`; a changed Gazebo model name would invalidate the
typed Scene identity chain. It must not be assumed that a native SDF model can
continue to use `/robot_description`, satisfy the existing ROS TF path, or
operate the current VelocityControl/MecanumDrive/OdometryPublisher/
JointStatePublisher settings without reconciliation.

Before implementation, the user must approve how the dedicated bootstrap route
will select exactly one representation:

| Concern | Required future decision/evidence |
| --- | --- |
| Robot bootstrap | Whether the dedicated simulation launch spawns/loads the native SDF model instead of topic-spawning the URDF. It must never create both representations. |
| ROS description and TF | How `robot_state_publisher` continues to serve ROS-only description/TF needs without becoming a second Gazebo spawn source. |
| Base, wheel, and sensor properties | An explicit parity inventory of masses/inertias, joints, poses, visuals, collisions, camera/LiDAR configuration, and resource URIs. |
| Motion plugins | Static configuration review and a future bounded runtime proof that the model plugins bind the intended joints and do not introduce a command/bridge path. |
| Contact system/topic | Exact native SDF placement, world Contact system identity, raw topic/type, and only later a bounded raw producer evidence plan. |

## 6. Future implementation surface and rollback boundary

No file is changed by this design. Subject to a separate implementation
approval, the minimal *candidate* surface is:

| Candidate file/location | Proposed responsibility | Approval/validation boundary |
| --- | --- | --- |
| `ros2_ws/src/ROBOT_URDF_final_description/models/ROBOT_URDF_final/model.sdf` (new, proposed) | Native Gazebo simulation twin, including the same-link base collision and ContactSensor. | Must be schema-validated and parity-reviewed before any runtime use. |
| `ros2_ws/src/ROBOT_URDF_final_description/models/ROBOT_URDF_final/model.config` (new, proposed) | Gazebo model metadata/resource discovery for the native twin. | Exact package/install handling requires review. |
| `ros2_ws/src/ROBOT_URDF_final_description/launch/typed_scene_observer.launch.py` (future edit, proposed) | Select exactly one approved native-SDF bootstrap route rather than the current topic-URDF spawn for this diagnostic. | Must remain free of bridge, `/cmd_vel`, control, retry, and duplicate spawn paths. |
| `ros2_ws/src/ROBOT_URDF_final_description/setup.py` (future edit only if needed) | Install any approved new model resource. | Static install/source hash parity must be demonstrated. |
| `ros2_ws/src/ROBOT_URDF_final_description/launch/tugbot_depot.sdf` (inspect first; edit only if necessary) | Retain one Contact system and select/load one native model route. | Do not duplicate the Contact system or change world geometry without a separate approved scope. |
| `ros2_ws/src/ROBOT_URDF_final_description/urdf/ROBOT_URDF_final.gazebo` (inspect/reconcile first) | Avoid having a second competing ContactSensor source when native SDF is selected. | No deletion or alteration is authorized by this document. |

Rollback is representation selection, not collision-policy rollback: until a
future migration is statically validated and separately approved, the current
URDF route remains untouched. A future runtime test must load one model
representation only. It must not retain a partial native model alongside the
topic-spawned URDF, and it must not translate an observed contact into a
ContactLatch, reward, terminal transition, or command action.

## 7. Required future evidence

Before any collision policy or ContactLatch work, a separately approved,
bounded run would need durable evidence for:

1. actual spawned Scene hierarchy: model, `base_link`, sensor, collision name,
   and sensor target;
2. model-plugin and joint binding, without command publication;
3. Contact system loading and the actual raw endpoint/type;
4. raw payload provenance, timestamp behavior, and duplicate/simultaneous
   contact behavior; and
5. source/install identity of the native model and launch route.

That evidence is not a contact classification policy. It cannot establish
collision termination, ContactLatch, reward, Gym/training, or hardware
readiness by itself.

## Decision required

```text
IMPLEMENTED_STATIC_ONLY — RUNTIME NOT APPROVED
```

The static-only skeleton and checker are implemented. User approval remains required before any native-SDF bootstrap selection, parity completion, model-plugin reconciliation, package build/install, or runtime evidence run.

