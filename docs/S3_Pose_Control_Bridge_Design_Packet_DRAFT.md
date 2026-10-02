# S3 Pose-Control Bridge Design Packet

**Status:** `USER_APPROVED_FOR_ONE_CONTROLLED_SIMULATION_MEASUREMENT — EXECUTION_COMPLETED`

## 1. Context and observed failure

The one approved controlled-coordinate measurement was attempted with no
production-code or launch modification. It is recorded as `INVALID` in
[Controlled Coordinate Reset Measurement Evidence Report](../artifacts/simulation/controlled_coordinate_reset_measurement/Controlled_Coordinate_Reset_Measurement_Evidence_Report.md):

- `0/3` approved probes were sent; `P0`, `P1`, and `P2` were not retried.
- The collector did not find ROS service
  `/world/world_demo/set_pose` with type
  `ros_gz_interfaces/srv/SetEntityPose`.
- The collector created no `/cmd_vel` publisher, published no command, and
  called no control service.
- Gazebo log reporting a transport pose service at
  `/world/world_demo/set_pose` is not evidence that a ROS service exists.

The initial run metadata and graph snapshots are retained in
[`run-controlled-20260924T170000Z-01`](../artifacts/simulation/controlled_coordinate_reset_measurement/run-controlled-20260924T170000Z-01/).

A separate, newly created measurement run with the temporary Option B bridge is
recorded as `VALID`: [`run-controlled-20260924T180000Z-02`](../artifacts/simulation/controlled_coordinate_reset_measurement/run-controlled-20260924T180000Z-02/). It observed the exact ROS service type, sent only `P0 → P1 → P2`, and then stopped the artifact-owned bridge and Gazebo processes by SIGINT recovery. Its evidence remains subject to every non-claim in this packet.

## 2. Three distinct layers

| Layer | Observed or installed evidence | Current state | Non-claim |
| --- | --- | --- | --- |
| Gazebo transport service | Gazebo launch log reports async `/world/world_demo/set_pose`; the SDF world name is `world_demo` | `OBSERVED_DURING_INVALID_RUN` | A Gazebo transport endpoint is not a ROS graph service. |
| `ros_gz_bridge` service mapping | Installed `ros_gz_bridge` version `1.0.22` `parameter_bridge --help` documents Gazebo-service-to-ROS-service exposure only; installed library contains `ServiceFactory<SetEntityPose, gz.msgs.Pose, gz.msgs.Boolean>` | `INSTALLED_CAPABILITY` | Capability does not mean the existing launch instantiates the mapping. |
| ROS client | `ros_gz_interfaces/srv/SetEntityPose` is installed; its request is `Entity` plus `geometry_msgs/Pose`, and response is `bool success` | `INSTALLED_INTERFACE_ONLY` | A client cannot call an absent ROS service. |

Installed binary symbols provide local evidence for the following type mapping
on this exact Jazzy installation:

| Endpoint | Name | Type |
| --- | --- | --- |
| Gazebo request | `/world/world_demo/set_pose` | `gz.msgs.Pose` |
| Gazebo response | `/world/world_demo/set_pose` | `gz.msgs.Boolean` |
| ROS service | `/world/world_demo/set_pose` | `ros_gz_interfaces/srv/SetEntityPose` |

The bridge conversion is ROS `SetEntityPose.Request` (entity identity plus
pose) to Gazebo `Pose`, and Gazebo `Boolean` to ROS `success`. The exact
runtime service name/type must still be observed after starting the bridge;
this packet does not treat static binary evidence as a runtime proof.

## 3. Audited bridge options

| Option | Gazebo ↔ ROS service mapping | Configuration and owner | Graph/lifecycle impact | Boundary assessment |
| --- | --- | --- | --- | --- |
| A. Add one service bridge to existing `gazebo.launch.py` | `/world/world_demo/set_pose`, `gz.msgs.Pose` / `gz.msgs.Boolean` ↔ same ROS name, `SetEntityPose` | Modify robot-description launch; launch owns bridge for every invocation | Persistent extra ROS service whenever the normal simulation launch runs | Technically feasible, but changes a shared launch/runtime surface and is disproportionate for one measurement. |
| B. Start a separate one-service `parameter_bridge` process for the controlled measurement | Same mapping, using explicit service types | Measurement artifact owns the process; no production package or launch change | One temporary ROS service; starts after Gazebo, stops by SIGINT before/with measurement shutdown | Can retain the three-request boundary if the process has exactly one service argument and collector preflight verifies type/name. |
| C. Measurement-local YAML/`ros_gz_bridge.launch.py` service configuration | Same mapping if service configuration syntax resolves to the installed converter | Temporary artifact config and launch wrapper own bridge | Same intended graph as B, but adds config parsing and another artifact to audit | Feasible only after syntax is verified for this installed version; unnecessary compared with direct `parameter_bridge`. |
| D. Direct Gazebo-transport caller | Gazebo request/response only; no ROS `SetEntityPose` service | New custom Gazebo transport client | Avoids ROS service graph, but bypasses the approved collector client contract | Not selected: requires a new conversion/caller design and weakens the stated ROS-service preflight. |
| E. Bridge command/world-control services too | Would add `/cmd_vel` or world-control related endpoints | Any owner | Broadens mutable graph surface | Prohibited for this measurement. |

## 4. Preferred option

**`USER_APPROVED_FOR_ONE_CONTROLLED_SIMULATION_MEASUREMENT`: Option B, an
ephemeral process that bridges exactly one Gazebo service.**

After the existing Gazebo launch is healthy, the measurement supervisor would
start one separate process with this single service argument:

```bash
ros2 run ros_gz_bridge parameter_bridge \
  /world/world_demo/set_pose@ros_gz_interfaces/srv/SetEntityPose@gz.msgs.Pose@gz.msgs.Boolean
```

The installed `parameter_bridge --help` documents this service form and states
that it exposes a Gazebo service as a ROS service. No topic bridge, command
bridge, `ControlWorld`, reset, pause, step, spawn, delete, or additional pose
service is part of this proposed process.

Before the collector is permitted to send `P0`, it must observe both:

```bash
ros2 service type /world/world_demo/set_pose
# expected: ros_gz_interfaces/srv/SetEntityPose

ros2 service find ros_gz_interfaces/srv/SetEntityPose
# expected to include only /world/world_demo/set_pose for this measurement bridge
```

The collector's existing graph/type preflight remains authoritative: a failed
name/type check means no probe is sent. A service bridge does not create a
`/cmd_vel` publisher and must not be passed any `/cmd_vel` bridge argument.

## 5. Required changes for a later, separately approved increment

| Item | Proposed location/owner | Required change | Verification and shutdown |
| --- | --- | --- | --- |
| Measurement supervisor command | `artifacts/simulation/controlled_coordinate_reset_measurement/` only | Add documented process orchestration that launches the existing Gazebo launch and then the one-service `parameter_bridge` command | Capture executable arguments/PID/log; stop only the bridge and Gazebo processes created by the run using SIGINT. |
| Collector preflight | Existing artifact collector | Record `get_service_names_and_types()` result and require the exact ROS service type before any probe | Save pre/post service graph snapshots and reject before `P0` if missing/mismatched. |
| Artifact manifest | Measurement artifact only | Record installed `ros_gz_bridge` and `ros_gz_interfaces` versions plus literal bridge argument | Verify no additional service/topic arguments; retain command/log hashes. |
| Existing production launch/config | `ROBOT_URDF_final_description` | **No change proposed** for Option B | The temporary process disappears on SIGINT; no persistent bridge remains after measurement. |

The next increment must not silently reuse the invalid run or send replacement
probes. It must start a new approved measurement run and preserve the fixed
order `P0 → P1 → P2` if, and only if, preflight succeeds.

## 6. Operational guard registry

| Guard or value | Present evidence | Classification | Non-claim |
| --- | --- | --- | --- |
| Warm-up `10 s` | Approved controlled-measurement plan | `ADMINISTRATIVE_STOP_GUARD` | Not a settling/freshness/reset threshold. |
| Post-probe capture `10 s` | Approved plan and artifact manifest | `ADMINISTRATIVE_STOP_GUARD` | Not a timeout policy, response SLA, or measurement acceptance threshold. |
| `topic_wait_seconds=90` | Existing collector CLI default/validation | `USER_APPROVED_PREFLIGHT_STOP_GUARD` | User-approved only as a preflight stop guard; it is not a settle, freshness, or reset policy. |
| Service response wait | Existing collector currently shares the post-probe guard window | `IMPLEMENTATION_DETAIL_REQUIRING_RECONCILIATION` | A successful response remains neither a reset receipt nor proof of atomic state. |
| Reset/freshness/settlement thresholds | No approved authority | `REQUIRED_DECISION` | This bridge packet does not choose any value. |

## 7. Approval checklist

- [x] Approve an ephemeral, measurement-owned one-service `parameter_bridge`
  process using the literal argument in this packet.
- [x] Confirm that the bridge owns no topic mapping and exposes no service other
  than `/world/world_demo/set_pose` as `SetEntityPose`.
- [x] Approve and record the `90 s` preflight stop guard in the artifact
  manifest; do not treat it as a settle policy.
- [x] Require pre/post ROS service graph/type snapshots and frozen `/cmd_vel`
  publisher allowlist before any probe.
- [x] Require SIGINT shutdown of only measurement-created bridge and Gazebo
  processes, with logs retained.

## 8. Conclusion

`USER_APPROVED_FOR_BRIDGE_IMPLEMENTATION_AND_ONE_MEASUREMENT_RUN`.

The installed bridge supports the needed service conversion, while the existing
launch simply does not instantiate it. This limited approval does not expand the measurement beyond the one temporary
bridge and the three declared P0/P1/P2 pose requests.

### Explicit non-claims

This packet is not approval for a reset contract, TF authority, collision
contract, task oracle, Gym environment, reward/termination behavior, production
runtime, firmware, or hardware. It does not approve more than the original
three P0/P1/P2 pose requests, and it does not authorize any pose request beyond the separately approved
controlled measurement run.
