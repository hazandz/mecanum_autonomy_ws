# S3 D3 — Typed Scene Diagnostic Launch Reconciliation Design

**Status: READY_FOR_REPLACEMENT_RUNTIME_PACKET_AND_NEW_GUARD — NO EXECUTION AUTHORITY**

## Purpose and boundary

This design reconciles the typed Scene observer's strict capture boundary with
the existing launch that is necessary to create `world_demo` and one
`ROBOT_URDF_final` entity. It proposes a future dedicated diagnostic launch;
it records the completed dedicated-launch implementation and its static validation. It does not authorize a runtime run, restore, acquire, or consume the historical S3.3.31 guard.

The one diagnostic question remains limited to the typed Scene hierarchy:

```text
ROBOT_URDF_final → base_link → s3_d3_base_contact_sensor
```

## Current `gazebo.launch.py` audit

The current [gazebo.launch.py](../ros2_ws/src/ROBOT_URDF_final_description/launch/gazebo.launch.py)
resolves the robot package, processes
[`ROBOT_URDF_final.xacro`](../ros2_ws/src/ROBOT_URDF_final_description/urdf/ROBOT_URDF_final.xacro),
and launches the world
[`tugbot_depot.sdf`](../ros2_ws/src/ROBOT_URDF_final_description/launch/tugbot_depot.sdf).
The current world identity is `world_demo`; the typed-observer world revision
must remain separately SHA-256 gated.

| Existing action / process | Current source evidence | Needed for locked world + exactly one initial entity? | Dedicated diagnostic disposition |
| --- | --- | --- | --- |
| Resource-path setup | `SetEnvironmentVariable(GZ_SIM_RESOURCE_PATH)` in `gazebo.launch.py` | Yes, subject to static resource audit. | Retain only if required to resolve the locked world/model resources. |
| Xacro render | `xacro.process_file(ROBOT_URDF_final.xacro)` | Required by the current topic-based spawn route. | Bootstrap-only candidate; do not infer it proves spawned SDF contents. |
| Gazebo world process | Includes `ros_gz_sim/launch/gz_sim.launch.py` with `-r -v 4 <tugbot_depot.sdf>`. | Yes. | Retain, with the locked world file and world-name/SHA gate. |
| Robot description publisher | `robot_state_publisher` holds the rendered description; current create action reads `/robot_description`. | Required by the approved dedicated bootstrap route. | **Approved bootstrap exception:** it exists only to provide `/robot_description` to the one initial create; it is not a Scene observer or command path. |
| Initial robot spawn | Delayed `ros_gz_sim create -topic /robot_description -name ROBOT_URDF_final -allow_renaming false -x 0 -y 0 -z .1 -Y 0`. | Yes, for the current known route. | Retain as the one permitted deterministic bootstrap spawn only. |
| `ros_gz_bridge parameter_bridge` | Created with multiple mappings. | No. | Omit. |
| Static lidar TF publisher | `tf2_ros static_transform_publisher`. | No. | Omit. |

### Existing bridge and command/control surface

The current `parameter_bridge` has these explicit mappings:

| Mapping | Direction syntax present in source | Reconciliation consequence |
| --- | --- | --- |
| `/cmd_vel@geometry_msgs/msg/Twist@gz.msgs.Twist` | Bare mapping; neither one-way bracket is present. | Command path exists and is incompatible with the typed-Scene diagnostic boundary. |
| `/odom@nav_msgs/msg/Odometry[gz.msgs.Odometry` | Gazebo-to-ROS syntax. | Not needed; omit. |
| `/ground_truth/odom@nav_msgs/msg/Odometry[gz.msgs.Odometry` | Gazebo-to-ROS syntax. | Not needed; omit. |
| `/scan@sensor_msgs/msg/LaserScan[gz.msgs.LaserScan` | Gazebo-to-ROS syntax. | Not needed; omit. |
| `/camera/image_raw@sensor_msgs/msg/Image@gz.msgs.Image` | Gazebo-to-ROS syntax. | Not needed; omit. |
| `/tf@tf2_msgs/msg/TFMessage@gz.msgs.Pose_V` | Bare mapping. | Not needed; omit. |
| `/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock` | Gazebo-to-ROS syntax. | Not needed by the typed helper; omit. |
| `/joint_states@sensor_msgs/msg/JointState[gz.msgs.Model` | Gazebo-to-ROS syntax. | Not needed; omit. |

No `ControlWorld`, pose, reset, pause, step, spawn/delete service mapping is
constructed by this launch source. Its `ros_gz_sim create` action is nevertheless
a mutation used for initial entity creation, not a read-only observation API.

## Dedicated diagnostic launch — implemented and static-validated

Proposed future file name:

```text
ros2_ws/src/ROBOT_URDF_final_description/launch/typed_scene_observer.launch.py
```

The dedicated launch is implemented as
[`typed_scene_observer.launch.py`](../ros2_ws/src/ROBOT_URDF_final_description/launch/typed_scene_observer.launch.py). Static AST validation confirms its only Node actions are the bootstrap description provider and one initial `ros_gz_sim create`; it has exactly one Gazebo include and one `GZ_SIM_RESOURCE_PATH` action. The typed helper remains a separately launched temporary process and is not launched by this file.

| Future action | Allowed purpose | Prohibited behavior |
| --- | --- | --- |
| Set resource path | Resolve locked Gazebo resources. | Mutating or adding a bridge. |
| Render locked Xacro | Supply the exact initial entity description. | Treating a rendered literal as runtime sensor proof. |
| Launch `gz_sim.launch.py` | Start the locked `tugbot_depot.sdf` revision. | Any world-control call after startup. |
| Initial deterministic `ros_gz_sim create` | Create exactly one `ROBOT_URDF_final` with `-allow_renaming false`; this is the sole bootstrap mutation. | A second spawn, delete, pose change, reset, pause, step, or post-bootstrap world control. |
| Scene helper | Independently discover one typed service and send one `Empty → Scene` request. | ROS bridge, ROS collector, raw-contact collector, or a second request. |

The future launch must omit `ros_gz_bridge`, `parameter_bridge`, the `/cmd_vel`
mapping, static TF publication, teleop, Nav2, PPO, raw-contact bridge, and any
control node. It must not create an observer ROS publisher, subscriber, service,
or action client.

### Approved bootstrap exception

Option 1 is approved and implemented: `robot_state_publisher` supplies
`/robot_description` only to the one initial `ros_gz_sim create`, with no
parameter bridge and no `/cmd_vel`. It is a bootstrap mutation path, not a
read-only capture path. After bootstrap completes, no spawn/delete/pose/reset/
pause/step/world-control operation is permitted for the capture interval.

## Packet reconciliation

The existing [typed Scene observer approval packet](S3_D3_Typed_Scene_Observer_Run_Approval_Packet_DRAFT.md)
correctly remains blocked. A future replacement packet must distinguish:

- **permitted initial deterministic spawn:** exactly one pre-capture creation
  of `ROBOT_URDF_final` by the approved launch route; and
- **forbidden capture-time mutations:** every additional spawn/delete, pose,
  reset, pause, step, or world-control operation.

The following items require explicit user approval before implementing the
launch or producing a replacement capacity-one guard:

| Required literal or semantic | Reason |
| --- | --- |
| Bootstrap route | **Resolved:** the narrow `robot_state_publisher → ros_gz_sim create` route is approved only for initial bootstrap. |
| Initial entity pose and `-allow_renaming false` semantics | It must remain deterministic and create exactly one locked entity. |
| Exact dedicated-launch path and SHA-256 | A future guard must bind the implementation, not the current broad launch. |
| World and Xacro source hashes | Detect source revision drift before launch. |
| Capture boundary after bootstrap | Explicitly preserve no bridge, no `/cmd_vel`, no control mutation, and one Scene request. |
| Startup/readiness evidence | Still required in the replacement runtime packet; it must not be treated as a reset receipt. |
| SIGINT bounded-wait behavior | Still required in the replacement runtime packet; SIGINT-only with no force-kill fallback. |


## S3.3.34 implementation record — completed and static-validated

**OPTION 1 APPROVED FOR DEDICATED-LAUNCH IMPLEMENTATION ONLY**

The approved narrow exception permits `robot_state_publisher` only to supply
`/robot_description` to the one initial `ros_gz_sim create`. The dedicated
launch implementation is
[`typed_scene_observer.launch.py`](../ros2_ws/src/ROBOT_URDF_final_description/launch/typed_scene_observer.launch.py). It contains the locked world launch,
resource-path setup, one description provider with only `robot_description`,
and one delayed initial entity creation. It contains no bridge, command mapping,
static TF publisher, typed Scene helper, capture-time control action, or retry.

This approval does not authorize a typed Scene runtime run, a new guard, or an
acquire/consume operation. The initial spawn is the sole bootstrap mutation;
every capture-time spawn/delete/pose/reset/pause/step/world-control action
remains prohibited.

## Replacement-packet validation and one-shot flow

```text
Dedicated launch implementation
→ static/offline validation
→ replacement packet and capacity-one guard bind launch + helper + world
→ one approved runtime run
```

Static validation must prove that the dedicated launch has no
`ros_gz_bridge`, `parameter_bridge`, `/cmd_vel`, static-TF, raw-contact, teleop,
Nav2, PPO, or control-node action. The runtime graph snapshot is only evidence
of processes/endpoints observed at that time; it cannot prove that no external
process can ever issue a command.

The helper must still service-discover the exact Scene endpoint, invoke exactly
one `RequestRaw`, persist its evidence fail-closed, make no retry, and receive
no ROS data. Shutdown may send SIGINT only to process groups created by the
future supervisor. `SHUTDOWN_INCOMPLETE` remains a blocker and never enables a
retry or force-kill.

## Non-claims

A dedicated launch design cannot prove the ContactSensor exists after spawn,
that a raw contact topic is advertised, a collision event, ContactLatch,
filtering, reward, termination, Gym/training, or hardware readiness. It does
not establish a reset receipt, settled state, TF authority, or a policy input.


## S3.3.37 bootstrap-readiness gate

The replacement runtime packet and new guard are blocked by the
[spawn-completion and Scene-readiness design](S3_D3_Spawn_Completion_And_Scene_Readiness_Design_DRAFT.md). `TimerAction(3.0)` and typed Scene-service availability do not prove
that `ROBOT_URDF_final` exists in the Scene response. Until a user selects a
readiness mechanism, the outer status `SCENE_BOOTSTRAP_UNCONFIRMED` must prevent
the sole `RequestRaw`; no model/link/sensor absence classification is allowed.

## Conclusion

**READY_FOR_REPLACEMENT_RUNTIME_PACKET_AND_NEW_GUARD — NO EXECUTION AUTHORITY**

The concrete broad-launch conflict is resolved for the typed Scene diagnostic:
[`gazebo.launch.py`](../ros2_ws/src/ROBOT_URDF_final_description/launch/gazebo.launch.py) is excluded from this diagnostic route, while the dedicated launch omits its `parameter_bridge` and `/cmd_vel` mapping. The approved Option 1 bootstrap route is implemented and static-validated. The initial `ros_gz_sim create` remains the sole bootstrap mutation; all mutations after bootstrap remain forbidden. A replacement runtime packet and new guard must bind the new launch, helper, world revision, literals, timing, capacity, and SIGINT-only shutdown before a one-shot run can be authorized.
