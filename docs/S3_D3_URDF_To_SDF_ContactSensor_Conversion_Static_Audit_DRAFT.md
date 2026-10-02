# S3 D3 — URDF-to-SDF ContactSensor Conversion Static Audit

**Status: DRAFT — STATIC CONVERSION EVIDENCE AUDIT — NO RUNTIME APPROVAL**

## Scope and method

This is a read-only, version-matched static audit of the current robot-spawn path. It does not launch Gazebo, ROS, `gz`, a bridge, or a collector; it does not run a command/service/action path or touch hardware. It changes no source, tooling, artifact, approval packet, or consumed guard.

The question is deliberately narrow: does local evidence establish that the `ContactSensor` declared in the Xacro-included URDF Gazebo extension is retained through the **actual** `ros_gz_sim create -topic /robot_description` spawn path? Native SDF ContactSensor support alone is not sufficient evidence for that claim.

The local stack identified by package metadata is `ros_gz_sim` `1.0.22`, Gazebo Sim `8.11.0` (Harmonic), `sdformat14`, and `gz-sensors8`. Paths below name the installed files inspected.

## 1. Current spawn pipeline

```text
ROBOT_URDF_final.xacro
  -> xacro.process_file(...).toxml()
  -> /robot_description parameter on robot_state_publisher
  -> ros_gz_sim create -topic /robot_description
  -> Gazebo EntityFactory / possible URDF-to-SDF interpretation
  -> Gazebo model entity ROBOT_URDF_final
```

| Arrow | Local source/tool and version-matched evidence | Status | What the evidence actually establishes |
| --- | --- | --- | --- |
| Xacro source -> rendered robot description | [`gazebo.launch.py`](../ros2_ws/src/ROBOT_URDF_final_description/launch/gazebo.launch.py) calls `xacro.process_file(robot_description_file)` then `toxml()`. [`ROBOT_URDF_final.xacro`](../ros2_ws/src/ROBOT_URDF_final_description/urdf/ROBOT_URDF_final.xacro) includes [`ROBOT_URDF_final.gazebo`](../ros2_ws/src/ROBOT_URDF_final_description/urdf/ROBOT_URDF_final.gazebo). That included file contains `<gazebo reference="base_link">` with the exact contact-sensor, collision, and topic literals. | `CONFIRMED` | The launch's input XML is produced from this Xacro inclusion graph; it does not establish the form accepted by Gazebo after spawn. |
| Rendered description -> ROS/Gazebo spawn entry point | The same launch passes the generated XML as `robot_description`, and its `ros_gz_sim create` node uses `-topic /robot_description`, `-name ROBOT_URDF_final`, and `-allow_renaming false`. Installed [`gz_spawn_model.launch.py`](/opt/ros/jazzy/share/ros_gz_sim/launch/gz_spawn_model.launch.py) documents `topic` as “Get XML from this topic”. | `CONFIRMED` | The selected spawn entry obtains XML from `/robot_description`; it does not label that topic XML as SDF. |
| Spawn entry point -> URDF-to-SDF conversion, if any | Installed `ros_gz_sim` `create` is a stripped ELF binary at [`create`](/opt/ros/jazzy/lib/ros_gz_sim/create). Its local launch source documents `model_string` as `XML(SDF) string`, but provides no source or schema showing how topic-provided `<robot>` XML is classified, converted, or how `<gazebo reference>` extensions are handled. [`parser.hh`](/opt/ros/jazzy/opt/sdformat_vendor/include/gz/sdformat14/sdf/parser.hh) documents that libsdformat can convert a **URDF file** to SDF; this does not prove that `create -topic` invokes that path. | `INSUFFICIENT_EVIDENCE` | General libsdformat URDF conversion exists; use by this topic-based spawner and preservation of this extension are not established. |
| Conversion/spawn request -> Gazebo model entity | The retained S3.3.17 launch log, cited by [Contact Endpoint Root-Cause Audit](S3_D3_Contact_Endpoint_Root_Cause_Audit_DRAFT.md), records creation of `ROBOT_URDF_final`; the installed `create` binary links an `gz::msgs::EntityFactory` request path. | `CONFIRMED` | The model entity was observed to spawn in the historical run. It does not prove which contact-sensor elements survived in the resulting model. |

## 2. ContactSensor conversion questions

| Question | Version-matched local evidence | Status | What the evidence actually proves |
| --- | --- | --- | --- |
| Does `<gazebo reference="base_link">` enter rendered URDF? | Xacro source includes the `.gazebo` file without a condition; the extension is under the included root `<robot>`. Existing static-validation evidence described in [Contact Endpoint Root-Cause Audit](S3_D3_Contact_Endpoint_Root_Cause_Audit_DRAFT.md) also retained the literals after Xacro validation. | `CONFIRMED` | The extension is part of the Xacro-rendered robot XML input. It does not prove a spawned SDF sensor. |
| Does the converter accept `<sensor type="contact">` in this extension? | Local native-SDF schema and examples support a link-owned `<sensor type="contact">`. No inspected version-matched source or documentation specifies that `ros_gz_sim create` or Gazebo's topic spawn path consumes a URDF `<gazebo reference>` extension containing that sensor. | `INSUFFICIENT_EVIDENCE` | Native SDF contact-sensor syntax is valid. No extension-converter support claim follows. |
| Does the converter retain `<contact><collision>...<topic>...`? | [`contact.sdf`](/opt/ros/jazzy/opt/sdformat_vendor/share/sdformat14/1.11/contact.sdf) defines native SDF `contact/collision` and `contact/topic`. The Gazebo Sim 8 native example [`contact_sensor.sdf`](/opt/ros/jazzy/opt/gz_sim_vendor/share/gz/gz-sim8/worlds/contact_sensor.sdf) places those elements within a link-owned sensor. No local evidence maps the project's URDF extension to these final SDF nodes. | `INSUFFICIENT_EVIDENCE` | The final SDF fields are valid, not that the current input produces them. |
| Is the sensor placed in the final SDF `<link name="base_link">`? | Native SDF places sensors below `<link>`, and `base_link` is a current URDF link. No generated spawned SDF, Factory request payload after conversion, or read-only ECS component record was captured. | `INSUFFICIENT_EVIDENCE` | Neither link placement nor sensor absence can be determined statically for this spawn pipeline. |
| Can the Contact system bind the sensor after conversion? | The world has the built-in `gz::sim::systems::Contact` plugin and S3.3.17 logged it as loaded. The native Sim 8 example pairs that system with a native SDF sensor. The run did not observe the configured endpoint. | `INSUFFICIENT_EVIDENCE` | Contact-system availability is established; binding to this unproven spawned sensor configuration is not. |

## 3. Required distinctions

- The native SDF examples prove Sim 8 SDF syntax and demonstrate a Contact system paired with a link-owned contact sensor. They **do not** prove conversion support for the project's URDF/Xacro `<gazebo reference="base_link">` extension.
- The Xacro inclusion graph and retained literal validation prove an input contains the ContactSensor literal. They **do not** prove the spawned Gazebo SDF contains a sensor.
- The S3.3.17 endpoint was not observed. That is runtime evidence that the configured endpoint was unavailable in that run; it does **not** identify conversion, collision-target resolution, or advertisement as the cause.
- The installed `sdformat_urdf` package is directionally `SDFormat -> URDF` by its public header and plugin description. It is not evidence that the `create -topic` implementation performs the inverse conversion or preserves Gazebo extension content.

## 4. Static evidence boundaries

| Local artifact or API | Relevant finding | Why it does not close the conversion question |
| --- | --- | --- |
| `/opt/ros/jazzy/opt/gz_sim_vendor/share/gz/gz-sim8/worlds/contact_sensor.sdf` | Native SDF contact sensor uses `<sensor>` under a `<link>`, with contact collision and topic children. | It bypasses URDF/Xacro and the ROS topic spawner. |
| `/opt/ros/jazzy/opt/sdformat_vendor/include/gz/sdformat14/sdf/parser.hh` | libsdformat documents URDF-file conversion to SDF. | A topic-provided XML string and the stripped `ros_gz_sim create` executable are a different integration path not statically exposed here. |
| `/opt/ros/jazzy/lib/ros_gz_sim/create` | Binary contains EntityFactory-related symbols and accepts the launch's topic-driven spawn request. | The installed binary lacks readable source or a declared conversion/extension-preservation contract. |
| `/opt/ros/jazzy/include/sdformat_urdf/sdformat_urdf.hpp` | The package exposes `sdf_to_urdf`, not a documented URDF-extension-to-SDF API for this flow. | It cannot establish the missing inverse conversion behavior. |

## 5. Consequence and next step

No source correction is justified by this audit. The missing evidence is a representation of what Gazebo receives or instantiates from the actual `/robot_description` topic path, together with a read-only, parseable model/link/sensor inspection method. A future **approved** diagnostic must capture one or both without control actions:

1. a lossless Factory/spawn payload or generated SDF if the installed spawn path exposes one; and/or
2. a version-matched, read-only Gazebo entity/component/sensor observation whose output grammar is verified before interpretation.

That future evidence must not infer collision events, ContactLatch state, sensor-to-collision filtering, reward, termination, Gym/training readiness, or hardware behavior. It must not treat a missing endpoint as collision absence.

## Conclusion

**C. CONVERSION_PATH_STATICALLY_UNRESOLVED**

The source-to-Xacro-to-topic-spawn path and historical model creation are confirmed. Native SDF ContactSensor support and generic libsdformat URDF conversion are also locally evidenced. However, no local, version-matched source or contract establishes that the active `ros_gz_sim create -topic /robot_description` path converts and preserves this particular URDF `<gazebo reference="base_link">` ContactSensor extension into a final SDF link sensor. Therefore neither support nor contradiction can be assigned from static evidence alone.

## Non-claims

This audit establishes no collision event, ContactLatch, filter policy, raw-contact delivery, reward, termination, Gym/training, runtime approval, or hardware readiness.
