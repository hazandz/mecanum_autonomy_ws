# S3 D3 Native SDF Load / Spawn Route Feasibility Audit

Status: `DEDICATED_NATIVE_WORLD_LAUNCH_STATICALLY_VALIDATED — RUNTIME NOT APPROVED`

## Scope and decision boundary

This is a static feasibility audit only. It neither creates a launch file nor starts Gazebo, ROS, `gz`, a model spawn, a bridge, a Scene request, a command/control path, or hardware. It does not approve a runtime run.

The target is a future, dedicated diagnostic route that loads the installed native SDF twin directly. It must not use `/robot_description` and must not topic-spawn the URDF. Its only future evidence objective is the native spawned hierarchy and ContactSensor endpoint; it is not an operational robot route.

## Authorities inspected

| Authority | Version / local evidence | What it establishes |
| --- | --- | --- |
| [`gz_spawn_model.launch.py`](/opt/ros/jazzy/share/ros_gz_sim/launch/gz_spawn_model.launch.py) | Installed `ros_gz_sim` 1.0.22, Jazzy | The official Jazzy wrapper accepts `world`, `file`, `entity_name`, `allow_renaming`, and pose inputs, then configures `ros_gz_sim/create` with `file`, `name`, and pose parameters. |
| `/opt/ros/jazzy/lib/ros_gz_sim/create` embedded usage text | Installed Jazzy executable | The local usage contract is `create -world [arg] [-file FILE] [-param PARAM] [-topic TOPIC] [-string STRING] [-name NAME] [-allow_renaming RENAMING] [-x X] [-y Y] [-z Z] [-R R] [-P P] [-Y Y]`; it also requires one of file, param, string, or topic. |
| [`gz_sim.launch.py`](/opt/ros/jazzy/share/ros_gz_sim/launch/gz_sim.launch.py) | Installed Jazzy | The wrapper retains an existing `GZ_SIM_RESOURCE_PATH` and appends package-exported resource paths before it launches Gazebo. |
| [Gazebo Harmonic ROS 2 model-spawn documentation](https://gazebosim.org/docs/harmonic/ros2_spawn_model/) | Official Gazebo; Jazzy section | Jazzy and later provide `gz_spawn_model.launch.py`, with `file:=.../model.sdf`, `entity_name:=...`, and pose inputs for a model in an existing simulation. |
| [Gazebo Sim 8 resource lookup reference](https://gazebosim.org/api/sim/8/resources.html) | Official Gazebo Sim 8 | A model can be created from an SDF path via `/world/<world_name>/create`; model/world includes accept URI paths; model and mesh resource lookup consult `GZ_SIM_RESOURCE_PATH`. |
| [`model.config`](../ros2_ws/install/ROBOT_URDF_final_description/share/ROBOT_URDF_final_description/models/ROBOT_URDF_final/model.config) and installed [`model.sdf`](../ros2_ws/install/ROBOT_URDF_final_description/share/ROBOT_URDF_final_description/models/ROBOT_URDF_final/model.sdf) | Package-install parity validated in S3.3.65/S3.3.67 | The installed model identity is `ROBOT_URDF_final`, and `model.config` selects `model.sdf` under the installed package model directory. |

The official Jazzy page is used only for the documented `file` route. The exact direct executable flags are additionally grounded in the local executable’s installed usage text and local Jazzy launch wrapper; no flag was inferred from a forum or an unrelated ROS distribution.

## Installed native model and resource roots

| Item | Exact path / value | Static result |
| --- | --- | --- |
| Native SDF file | `/home/hazan/mecanum_autonomy_ws/ros2_ws/install/ROBOT_URDF_final_description/share/ROBOT_URDF_final_description/models/ROBOT_URDF_final/model.sdf` | Regular file; SHA-256 `809af5a0f0305eda00569c5c9dbbc9161e23b4ad95c6e19319a934c1d7e5a18e`, matching source at audit time. |
| Model metadata | `/home/hazan/mecanum_autonomy_ws/ros2_ws/install/ROBOT_URDF_final_description/share/ROBOT_URDF_final_description/models/ROBOT_URDF_final/model.config` | Regular file; model name `ROBOT_URDF_final`; SDF entry `model.sdf`. |
| Required future `GZ_SIM_RESOURCE_PATH` entry | `/home/hazan/mecanum_autonomy_ws/ros2_ws/install/ROBOT_URDF_final_description/share` | Required so package-relative visual URIs such as `ROBOT_URDF_final_description/meshes/IntelRealsense_D435_Multibody_1.stl` and `.../RPLiDAR_A1M8_1.stl` resolve from installed resources. |
| Optional model-URI root for an include design only | `/home/hazan/mecanum_autonomy_ws/ros2_ws/install/ROBOT_URDF_final_description/share/ROBOT_URDF_final_description/models` | Required only if a future world `<include><uri>model://ROBOT_URDF_final</uri>` route is chosen. It is not needed by the selected absolute-`-file` route. |

The selected route passes the installed `model.sdf` as an absolute file input. Thus it does not rely on a `model://` lookup to locate the model file, while it still requires the package-share resource root for the approved visual mesh URIs.

## Candidate routes

| Candidate | Exact future input form established by authority | `/robot_description` / `robot_state_publisher` needed? | Requires world edit? | Dual-spawn / boundary assessment | D3 passive diagnostic suitability |
| --- | --- | --- | --- | --- | --- |
| **A. Direct, supervisor-owned `ros_gz_sim create -file` — selected** | `/opt/ros/jazzy/lib/ros_gz_sim/create -world world_demo -file /home/hazan/mecanum_autonomy_ws/ros2_ws/install/ROBOT_URDF_final_description/share/ROBOT_URDF_final_description/models/ROBOT_URDF_final/model.sdf -name ROBOT_URDF_final -allow_renaming false -x 0 -y 0 -z 0.1 -Y 0` | **No.** The local CLI’s `-file` input is an SDF filename; no topic input is supplied. A future native route must not launch `robot_state_publisher`. | No; the existing `tugbot_depot.sdf` is loaded as the world, then exactly one create request inserts the model. | One direct child process is owned by the future supervisor. It must omit the existing URDF topic-create route and reject an existing entity named `ROBOT_URDF_final` before creating one. No bridge is part of this route. | **Suitable**, subject to a future dedicated-launch implementation, static audit, approval packet, and capacity-one guard. It is the narrowest route consistent with existing supervisor-owned create ownership. |
| B. Native model as world `<include>` | Future world content would need `<include><uri>model://ROBOT_URDF_final</uri>` with the model URI root above, or an explicit local SDF URI/path supported by the Sim 8 resource contract. | No. | **Yes.** The present `tugbot_depot.sdf` has no native twin include; adding one would change a locked world artifact. | World-start insertion cannot coexist with any URDF create process. A modified or copied diagnostic world would need separate review and hash locking. | **Not selected.** It expands scope into a world change and makes a future one-create ownership receipt unavailable. |
| C. Jazzy `gz_spawn_model.launch.py` wrapper | Official example: `ros2 launch ros_gz_sim gz_spawn_model.launch.py world:=world_demo file:=<installed-model.sdf> entity_name:=ROBOT_URDF_final x:=0 y:=0 z:=0.1`; local wrapper maps these to `create` parameters. | No. File input is distinct from `topic`. | No. | It is a supported Jazzy wrapper but adds launch-managed child ownership. The existing supervision design needs direct create exit ownership, and the bridge-inclusive `ros_gz_spawn_model.launch.py` variant is prohibited. | **Viable but not selected.** It does not improve the dedicated passive boundary over A. |

## Selected future dedicated route

The following is a design input, **not a command authorized or run by this audit**:

```text
set GZ_SIM_RESOURCE_PATH=/home/hazan/mecanum_autonomy_ws/ros2_ws/install/ROBOT_URDF_final_description/share[:existing permitted resource entries]

future dedicated native-world launch
  -> Gazebo Sim 8 loads locked tugbot_depot.sdf / world_demo

future supervisor-owned direct child
  -> /opt/ros/jazzy/lib/ros_gz_sim/create
       -world world_demo
       -file /home/hazan/mecanum_autonomy_ws/ros2_ws/install/ROBOT_URDF_final_description/share/ROBOT_URDF_final_description/models/ROBOT_URDF_final/model.sdf
       -name ROBOT_URDF_final
       -allow_renaming false
       -x 0 -y 0 -z 0.1 -Y 0

future typed Scene helper
  -> one typed Empty -> Scene request to /world/world_demo/scene/info
```

The direct `create` input must be the installed `model.sdf`, never the URDF `/robot_description` topic. The final dedicated implementation must resolve and hash-lock each executable and input before any subprocess is started.

## Dedicated-route graph and prohibited boundary

```text
future supervisor
  ├─ dedicated native-world launcher ──> Gazebo Sim / world_demo
  ├─ one direct ros_gz_sim create -file ──> native ROBOT_URDF_final
  └─ one typed Scene observer ──> /world/world_demo/scene/info
```

The graph intentionally has **no** `robot_state_publisher`, `/robot_description`, `ros_gz_bridge`, `parameter_bridge`, TF bridge, `/cmd_vel`, teleop, Nav2, PPO/Gym, raw-contact bridge, ROS collector, control service/action client, pause/reset/step/delete/spawn after the initial create, or hardware process. The `create` process is the sole allowed bootstrap mutation; the later Scene request is read-only observation.

The native model currently has no drive, velocity, odometry, joint-state, sensor-system, camera, LiDAR, bridge, or ROS plugin. This audit does not infer their future behavior or add any command/control path.

## Dual-spawn prevention rule

A future route must satisfy all of the following before it can issue its one native `-file` create:

1. Select exactly one robot bootstrap mode: native SDF `-file` **or** legacy URDF topic-spawn, never both.
2. Use a dedicated launch that loads only the locked world; it must not create `/robot_description`, `robot_state_publisher`, or a URDF create child.
3. Set `-name ROBOT_URDF_final -allow_renaming false` for the one native create and fail closed if an entity with that exact name is already observed by the approved future readiness mechanism.
4. Do not add a native `<include>` to the world while the direct create route is selected.
5. Keep the broad `gazebo.launch.py` out of the diagnostic route because it retains the legacy URDF bootstrap and ROS bridge / command mappings.

## What remains runtime-only

The following cannot be established by static route evidence and must remain unknown until a separately approved one-shot run:

- Gazebo startup and world readiness;
- acceptance and final insertion of the native SDF model;
- installed-resource resolution by the live process;
- existence of the Scene service and actual Scene hierarchy;
- ContactSensor entity construction and raw Contacts endpoint advertisement;
- any collision event, ContactLatch behavior, reward, termination, training, or hardware readiness.

## Conclusion

`DEDICATED_NATIVE_WORLD_LAUNCH_STATICALLY_VALIDATED — RUNTIME NOT APPROVED`

Official Jazzy and local installed wrapper evidence establish a native SDF file route that does not require `/robot_description`: one direct `ros_gz_sim create -file` child after a dedicated world-only launch. S3.3.69 has now implemented and AST-validated the dedicated world-only launch at [`native_sdf_contact_diagnostic.launch.py`](../ros2_ws/src/ROBOT_URDF_final_description/launch/native_sdf_contact_diagnostic.launch.py): its graph is exactly `set_resource_path → gazebo`, it has no robot entity or ROS node, and source/install SHA-256 is `1719f29d11f235b7a7c24e5bb0dfd0fb269559d3930497a446c0f8edfac3657f`. A separate approval and guard remain required before any native `create -file` execution.
