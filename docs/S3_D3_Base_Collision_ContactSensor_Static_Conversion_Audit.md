# S3 D3 Base Collision / ContactSensor Static Conversion Audit

Status: `CONVERSION_PATH_STATICALLY_UNRESOLVED`

## Scope

This is a read-only, static audit for the historical S3.3.54 warning that
DART could not create geometry for `base_link_collision`. It used source
inspection, Xacro rendering, XML parsing, local `gz sdf` conversion/validation,
and retained S3.3.54 logs. It did not launch Gazebo or ROS, spawn an entity,
call a service, create a bridge, acquire/consume a guard, or modify robot,
world, launch, helper, or historical evidence.

Sources inspected:

- [Current Xacro](../ros2_ws/src/ROBOT_URDF_final_description/urdf/ROBOT_URDF_final.xacro)
- [Gazebo extension](../ros2_ws/src/ROBOT_URDF_final_description/urdf/ROBOT_URDF_final.gazebo)
- [Dedicated typed-Scene launch](../ros2_ws/src/ROBOT_URDF_final_description/launch/typed_scene_observer.launch.py)
- [World with Contact system](../ros2_ws/src/ROBOT_URDF_final_description/launch/tugbot_depot.sdf)
- [S3.3.54 bootstrap log](../artifacts/simulation/contact_producer_evidence/run-typed-scene-20260928T071008Z/bootstrap_launch_stdout.log)
- [S3.3.54 post-run reconciliation](S3_D3_Typed_Scene_Observer_S3_3_54_Post_Run_Evidence_Reconciliation.md)
- [Post-run remediation audit](S3_D3_Post_Run_Remediation_Decision_Audit_DRAFT.md)

## 1. Source inventory

The current Xacro includes `materials.xacro`, `ROBOT_URDF_final.ros2control`,
and `ROBOT_URDF_final.gazebo`. `base_link` is defined in the main Xacro, not
in an additional base-link include. It has exactly one source `<collision>`:

| Link | Source collision name | Geometry | Origin | Material |
| --- | --- | --- | --- | --- |
| `base_link` | `s3_d3_base_contact_collision` | `<box size="0.4 0.28 0.10"/>` | `xyz="0 0 0"`, `rpy="0 0 0"` | No collision material element; the separate visual uses `chassis_dark_grey`. |

The Gazebo extension has exactly one `<gazebo reference="base_link">` with
exactly one contact sensor:

| Field | Current source literal |
| --- | --- |
| Reference/link scope | `base_link` |
| Sensor name/type | `s3_d3_base_contact_sensor` / `contact` |
| Contact collision target | `s3_d3_base_contact_collision` |
| Raw topic | `/s3_d3/contact/raw` |
| `always_on` | `true` |

`base_link_collision` occurs neither in the current Xacro nor in the current
Gazebo extension. It is therefore not equivalent to
`s3_d3_base_contact_collision` by source evidence. The world does declare one
world-scope `gz::sim::systems::Contact` plugin, but plugin declaration does not
prove a spawned endpoint or a runtime contact event.

## 2. Rendered URDF evidence

The dedicated launch calls `xacro.process_file()` on the current Xacro to form
`/robot_description`. The following non-runtime command used the same Xacro
input and resolved workspace installation:

```text
/opt/ros/jazzy/bin/xacro ros2_ws/src/ROBOT_URDF_final_description/urdf/ROBOT_URDF_final.xacro
```

The output was XML-parsed in a temporary directory and then removed. SHA-256
values at audit time were:

| Input/output | SHA-256 |
| --- | --- |
| Current Xacro | `7a8f72894d024598f908b12b5a867c4c90e7e6ba167d9130e3e941e0129b5477` |
| Current Gazebo extension | `6c7d0b9e90c2ed87a1de7aaf83b2c3ad07a897b5b1d1b2d26737054020d3f0fc` |
| Dedicated launch | `b6acf767471527f37c4e2d7c67cc46b693298cb4bf7028afb96be8d00c4f255d` |
| World SDF | `1c50f90d151a12559d426796c5d153c829b8777a5b4e8ef94c007a2023f6e271` |
| Temporary rendered URDF | `27ad0de40c1970eaef0ef409b5418f381de186dc7baf958642fbdaabc29b6644` |

XML evidence confirms exactly one rendered `base_link`, with exactly one
collision named `s3_d3_base_contact_collision`, using the same box and origin
as source. It also confirms one rendered `gazebo` extension for `base_link`
with one `s3_d3_base_contact_sensor`, target
`s3_d3_base_contact_collision`, topic `/s3_d3/contact/raw`, and
`always_on=true`. The rendered URDF contains the sensor literal once, target
literal twice (collision definition plus sensor target), and no
`base_link_collision` literal.

This proves source-to-render identity only. It does not prove what a spawned
Gazebo entity retained.

## 3. Offline SDF/conversion evidence

The installed non-server tool reports `gz sdf` version `14.9.0`. It was used
only to print a temporary SDF from the rendered URDF and then check that SDF:

```text
/opt/ros/jazzy/opt/gz_tools_vendor/bin/gz sdf -p <temporary-rendered-urdf>
/opt/ros/jazzy/opt/gz_tools_vendor/bin/gz sdf -k <temporary-converted-sdf>
```

Both conversion and SDF validation exited `0`. The converted temporary SDF
SHA-256 was `784fa406c7d33493e4ed5df6c314561a0363ea22925996e5d0f13c45ab831136`.
The only conversion warning concerned the unrelated RPLiDAR `frame_id` field.

The converted model was `ROBOT_URDF_final`; its converted `base_link` showed:

| Converted element | Exact value |
| --- | --- |
| Collision name | `base_link_fixed_joint_lump__s3_d3_base_contact_collision_collision` |
| Collision geometry | SDF box, `0.40000000000000002 0.28000000000000003 0.10000000000000001` |
| Sensor name/type | `s3_d3_base_contact_sensor` / `contact` |
| Sensor `<contact><collision>` target | `s3_d3_base_contact_collision` |
| Sensor `<topic>` | `/s3_d3/contact/raw` |

Thus this local conversion preserves the sensor identity and box geometry, but
it rewrites the collision element name through fixed-joint lumping while
leaving the sensor target literal unchanged. This is a concrete static
conversion observation, not an assertion about the spawned entity or a repair
recommendation.

The local `ros_gz_sim` package is `1.0.22`; its installed `create` is a stripped
ELF binary linked to Gazebo Transport and Messages vendors. No locally
inspectable, version-matched source or typed receipt was found that proves that
`gz sdf -p` is the identical conversion path used when `ros_gz_sim create`
submits `/robot_description` to the running Gazebo server. Consequently the
printed SDF cannot be substituted for spawn evidence.

## 4. DART/geometry assessment by evidence layer

| Layer | Identity/geometry result | Relationship to historical warning |
| --- | --- | --- |
| Source | Approved named box exists; no `base_link_collision` literal. | Contradicts treating the warning name as a current source name. |
| Rendered URDF | Same named box and ContactSensor target survive rendering. | Does not explain a runtime DART name or geometry decision. |
| `gz sdf -p` output | Box geometry is present, but fixed-joint lumping rewrites its collision name while the sensor target remains source-named. | A plausible conversion-level naming concern, but not proven to be the S3.3.54 spawn conversion. |
| Spawned runtime entity | No independently retained SDF/Scene receipt for collision geometry/name. | `base_link_collision` warning remains historical runtime evidence only. |

The retained log places the warning immediately after a DART message that mesh
construction from SDF is not implemented, and it also reports a similar issue
for the RealSense mesh collision. This supports classifying the warning as
relevant to geometry compatibility, but it does **not** prove that the approved
box collision failed, that the ContactSensor target was absent, or that contact
delivery failed. In particular, source-level box geometry itself has no static
mesh limitation.

## 5. Source versus installed artifact check

After sourcing the workspace installation, source and installed SHA-256 values
matched for the Xacro, Gazebo extension, and dedicated launch. Therefore this
audit found no current source/install drift that explains the historical name.
That result still cannot reconstruct the exact robot-description bytes or
spawn-side conversion behavior from S3.3.54.

## 6. Conclusion and non-claims

```text
CONVERSION_PATH_STATICALLY_UNRESOLVED
```

Static source and rendered-URDF identities are confirmed: the ContactSensor
still targets the approved named box. The local SDF tool demonstrates a
fixed-joint-lumping rename that merits future bounded investigation, but its
relationship to `ros_gz_sim create -topic /robot_description` is not locally
proven. Therefore neither a static configuration mismatch nor a static geometry
problem is confirmed for the actual spawn path.

This audit does not establish a contact event, a raw contact endpoint,
collision termination, ContactLatch, reward, Gym/training, or hardware
readiness. It performed zero runtime operation and zero guard operation.
