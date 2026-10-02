# S3 D3 — Typed Scene Guard Preparation Validation Report

**Status: OFFLINE VALIDATION COMPLETE — EXECUTION NOT STARTED**

## Scope and authority

This report records offline preparation for `S3.3.31_TYPED_SCENE_OBSERVER_RUN`.
It does not authorize or record a Gazebo, ROS, `gz`, helper-runtime, bridge,
service-request, command, or hardware operation.

| Bound authority | Verified value |
| --- | --- |
| Approval ID | `S3.3.31_TYPED_SCENE_OBSERVER_RUN` |
| Approval packet | [typed Scene observer run approval packet](../../../../docs/S3_D3_Typed_Scene_Observer_Run_Approval_Packet_DRAFT.md) |
| Packet SHA-256 after decision record | `613d4ea1360ca0c64636f4368a3be759c657db8b2d6c040d4d43a5a83d6b7204` |
| Helper source | [typed_scene_observer.cpp](../tools/typed_scene_observer.cpp) |
| Helper SHA-256 | `f8a56927f523deb0dd0b59eed30cab5bd571773176e45d6447bf1c62247d014d` |
| World / world SHA-256 | `world_demo` / `1c50f90d151a12559d426796c5d153c829b8777a5b4e8ef94c007a2023f6e271` |
| Service and typed messages | `/world/world_demo/scene/info`; `gz::msgs::Empty → gz::msgs::Scene` |
| Locked timing inputs | preflight `90000 ms`; request `5000 ms`; polling `10 ms` |
| Capacity / shutdown | `1`; `SIGINT-only` |

The guard is [S3.3.31_TYPED_SCENE_OBSERVER_RUN.json](../approval_guards/S3.3.31_TYPED_SCENE_OBSERVER_RUN.json). It is currently `authorized_not_consumed`; no acquire was attempted against that live record.

## Tooling created

| File | Responsibility | Runtime behavior in this phase |
| --- | --- | --- |
| [typed_scene_approval_guard.py](../tools/typed_scene_approval_guard.py) | Canonical JSON validation, atomic capacity-one acquire/consume primitives, and offline fixtures. | Only temporary-directory fixtures were used. |
| [run_typed_scene_observer.py](../tools/run_typed_scene_observer.py) | Builds the locked static authority context and provides non-mutating source/world/guard preflight validation. | Runtime execution is deliberately unavailable in this guard-preparation phase. |

The supervisor validates packet and helper digests, world SHA-256, the exact
single `world_demo` element using UTF-8 text supplied to `xml.etree.ElementTree`,
and the guard record. Supplying UTF-8 text is necessary because the existing SDF
contains UTF-8 comment text while declaring ASCII; it reuses the workspace's
previously validated XML-parser approach. It does not alter the SDF.

## Offline checks

| Check | Result |
| --- | --- |
| `python3 -m py_compile` for both Python tools | PASS |
| Guard self-test: initialize, acquire once, consume temporary fixture | PASS |
| Second acquire after temporary consumption | PASS — rejected |
| Packet/helper/world/literal mismatch fixtures | PASS — rejected |
| Malformed guard and lock fixtures | PASS — rejected |
| Atomic-write failure fixture | PASS — rejected without crash |
| Old-record byte preservation fixture | PASS |
| Supervisor non-mutating authority preflight on the live record | PASS |
| Supervisor offline self-test | PASS |
| C++ helper compile (`gz-transport13 13.5.0`, `gz-msgs10 10.3.2`, `-Wall -Wextra -Werror`) | PASS |
| C++ helper `--offline-self-test` | PASS |
| C++ helper `--offline-artifact-self-test` | PASS |
| Source scan of Python guard/supervisor | PASS — no `subprocess`, `Popen`, `rclpy`, bridge, `/cmd_vel`, ROS client, SIGTERM, SIGKILL, or force-kill token |

The C++ compilation and both helper modes operated on fixture data only. No
Transport Node or `RequestRaw` runtime path was invoked.

## Guard semantics

The future supervisor must fail closed before launch on a packet, helper, world,
or literal mismatch. A future execution may acquire the guard exactly once and
must atomically consume it for every terminal result, including `INVALID`,
`SHUTDOWN_INCOMPLETE`, or `INVALID_EVIDENCE_PERSISTENCE_FAILURE`. It has no
retry path and allows only SIGINT for process groups it creates.

The existing historical guards and artifacts were not read for mutation or
changed by the validation fixtures. The live S3.3.31 guard remains separate and
unconsumed.

## Conclusion

`S3.3.31_TYPED_SCENE_OBSERVER_RUN` has exactly one remaining execution
capacity. The only next operational step is a separately authorized execution
under this already-bound authority. This report is not that authorization and
contains no runtime evidence.

## S3.3.32 launcher-boundary audit and implementation result

The future execution state machine was deliberately **not** enabled. Static audit
of [gazebo.launch.py](../../../../ros2_ws/src/ROBOT_URDF_final_description/launch/gazebo.launch.py) found that it is the current launch path which loads `tugbot_depot.sdf` and spawns `ROBOT_URDF_final` (`ros_gz_sim create`, `-name ROBOT_URDF_final`). That same launch description creates `ros_gz_bridge parameter_bridge` and contains the bare mapping `/cmd_vel@geometry_msgs/msg/Twist@gz.msgs.Twist`.

This is a launcher-created bridge, not a bridge the supervisor would create.
Nevertheless, it conflicts with the packet's strict no-ROS-bridge and no-command
path boundary. The packet is consequently `REQUIRED_USER_RECONCILIATION —
EXECUTION BLOCKED`. The supervisor's `--execute` route refuses before authority
preflight, guard acquisition, subprocess construction, launch, helper build, or
helper call. No mock subprocess state-machine test was run because implementing
or simulating an execution ordering under an incompatible launch boundary would
misrepresent an unapproved runtime path.

| S3.3.32 offline check | Result |
| --- | --- |
| Launcher audit | Conflict confirmed: `ros_gz_bridge parameter_bridge` plus bare `/cmd_vel` mapping |
| `run_typed_scene_observer.py --offline-self-test` | PASS |
| `--execute` refusal before acquire | PASS — `REQUIRED_USER_RECONCILIATION` |
| Live guard state | `authorized_not_consumed` |
| Live guard SHA-256 | `6a5d9d138d3fbb5c37b13dfa7e69732a0c4d47f03ec3e7ac4ce7ac6672576710` |
| Live guard mutation/acquire/consume | None |
| C++ helper offline compile and both offline modes | Retained PASS from S3.3.31 validation; not a runtime helper call |

The reconciled packet SHA-256 is `50cbfa9d2712415dfea79d661c7a10e2b3b673ade50ff5672279b2ce1f7447a8`. It no longer equals the live guard's immutable bound packet SHA-256, so `validate(..., authorized=True)` must fail closed if attempted. This is intentional and means the existing guard is not usable for launch.

**Required next decision:** approve a reconciled boundary which either explicitly
permits the audited launcher-created bridge/command path or supplies a separately
audited spawn path that keeps the strict no-bridge boundary. Only then may a new
packet hash and new approval-bound guard be prepared.
