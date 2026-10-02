# S3.3.54 Typed Scene Observer Post-Run Evidence Reconciliation

Status: `POST-RUN READ-ONLY RECONCILIATION — NO RUNTIME APPROVAL`

## Scope and evidence boundary

This read-only reconciliation examines the consumed S3.3.54 guard, the sole
run directory, its preserved supervisor metadata and launch logs, plus a
static trace of the supervisor and helper source. It neither reruns the
observer nor changes any recorded artifact. A source trace identifies what a
component was designed to do; it is not a substitute for a preserved runtime
receipt.

Evidence read:

- [Consumed S3.3.54 guard](../artifacts/simulation/contact_producer_evidence/approval_guards/S3.3.54_TYPED_SCENE_OBSERVER_FINAL_EXECUTION_RUN.json)
- [Run metadata](../artifacts/simulation/contact_producer_evidence/run-typed-scene-20260928T071008Z/supervisor_metadata.json)
- [Bootstrap stdout](../artifacts/simulation/contact_producer_evidence/run-typed-scene-20260928T071008Z/bootstrap_launch_stdout.log)
- [Bootstrap stderr](../artifacts/simulation/contact_producer_evidence/run-typed-scene-20260928T071008Z/bootstrap_launch_stderr.log)
- [Supervisor static trace](../artifacts/simulation/contact_producer_evidence/tools/run_typed_scene_observer.py)
- [Typed Scene helper static trace](../artifacts/simulation/contact_producer_evidence/tools/typed_scene_observer.cpp)

No separate ROS launch-log file is listed inside the artifact directory. The
launch log path printed on stdout is external to this artifact and is not a
durable S3.3.54 evidence item here.

## 1. Execution facts

| Question | Evidence | Finding |
| --- | --- | --- |
| Was Gazebo/launch started? | `bootstrap_launch_stdout.log` lines 3--5 record `gazebo-1` and `robot_state_publisher-2` process starts; lines 18--21 record the installed `tugbot_depot.sdf` being received and loaded; line 235 records `world_demo` initialized. | **Yes, independently evidenced by the preserved launch log.** |
| Is one robot creation evidenced? | Line 283 records one `UserCommands` creation event for entity `ROBOT_URDF_final` (entity 143). The metadata fixes the approved create argv, while the static supervisor has only one `create_phase` call and no retry branch. | **One creation event is observed.** There is no preserved direct-create PID, exit code, or per-invocation record, so an exact process-invocation count of one is not independently auditable. |
| Is one Typed Scene `RequestRaw` evidenced? | The helper source has one `Node::RequestRaw` call, but helper stdout/stderr are redirected to `DEVNULL`; the artifact has no `scene_response.pb`, `scene_summary.json`, `request_metadata.json`, or helper process record. Metadata merely reports `helper_status`. | **No independent request count evidence.** At most, it is supervisor-reported that the helper returned a diagnostic status. |
| Did the Contact system load? | Launch stdout line 25: `Loaded system [gz::sim::systems::Contact] for entity [1]`. | **Yes, the world-scope Contact system loaded.** This is not an observation of a contact event or ContactSensor payload. |
| Did this supervisor create bridge, `/cmd_vel`, pose/reset/world-control, or hardware action? | Static supervisor route launches only `ros2 launch ... typed_scene_observer.launch.py`, the direct `ros_gz_sim/create` child, and the C++ helper; no bridge or hardware invocation exists in that route. The dedicated launch has no bridge or control node. The preserved log contains no supervisor-created bridge process or `/cmd_vel` publication. | **No such supervisor action is observed or statically routed.** The world itself loads existing Gazebo plugins that *subscribe* to `/cmd_vel` (lines 273 and 276) and advertises world-control services (line 235); subscription/advertisement is not a supervisor publish or control request. |

The consumed guard is schema `s3_d3_typed_scene_final_execution_guard/v2`, has
capacity 1, and records `run_id` `run-typed-scene-20260928T071016Z`,
`final_status` `SHUTDOWN_INCOMPLETE`, and a non-null consumption timestamp.
Those fields establish that the one-shot authority was consumed; they do not
replace missing runtime evidence files.

## 2. Scene result admissibility

`supervisor_metadata.json` records
`helper_status = SCENE_SENSOR_PRESENT_IDENTITY_ONLY`. The classification is:

```text
SUPERVISOR_REPORTED_ONLY
```

The result is not independently verifiable because the run artifact retains
only the metadata plus bootstrap logs. It does not retain the helper's
canonical `scene_summary.json`, `request_metadata.json`, raw
`scene_response.pb`, or raw-response SHA-256. The missing material prevents an
auditor from rechecking the exact model/link/sensor hierarchy, response
decoding, type/status schema, timestamps, or request provenance.

This status must not be upgraded to a collision observation, an operating raw
contact endpoint, ContactLatch evidence, a collision-policy decision, reward
evidence, termination evidence, Gym/training evidence, or hardware evidence.

## 3. Cleanup reconciliation

The source's `shutdown_sigint_only()` sends `SIGINT` to each supervisor-owned
launch/helper process group and waits at most
`MEASUREMENT_SHUTDOWN_GRACE_MS = 5000`. It returns false if group signaling or
the bounded wait raises an error/timeout; `execute_guarded()` then overwrites
the terminal result with `SHUTDOWN_INCOMPLETE` before guard consumption.

The preserved launch log independently shows the following sequence:

1. Lines 337--339: the launch receives SIGINT and forwards SIGINT to
   `robot_state_publisher-2` and `gazebo-1`.
2. Line 341: `robot_state_publisher-2` exits cleanly.
3. Line 343: `gazebo-1` has not terminated five seconds after SIGINT.
4. Lines 343--345: **the ROS launch process itself** escalates its Gazebo child
   to SIGTERM; Gazebo exits with code `-15`.

Therefore, the supervisor's final `SHUTDOWN_INCOMPLETE` is consistent with its
five-second bounded wait on the bootstrap launch process. The preserved record
does **not** identify which top-level process group remained unconfirmed at the
supervisor deadline, nor does it provide the supervisor's wait result/PID
record. It is incorrect to infer that a process remained alive after a later
inspection merely because cleanup was incomplete at the deadline.

Conversely, the log proves that end-to-end cleanup was not SIGINT-only: the
child-management behavior inside `ros2 launch` issued SIGTERM after its own
five-second grace. The supervisor source contains no direct SIGTERM call, but
the actual child cleanup record is still material and cannot be described as a
completed SIGINT-only shutdown.

## 4. Provenance and retention defects

| Item | Static/runtime evidence | Reconciliation |
| --- | --- | --- |
| Guard run ID versus artifact directory | `consume_trusted()` obtains its run ID from `dependencies.run_id()` at consumption. `RuntimeDependencyFactory._ensure_artifact_directory()` independently formats its directory name at first bootstrap launch. | The directory was first made at `071008Z`; the consumed guard run ID was produced later at `071016Z`. This is an **evidence/provenance defect**, not merely presentation: no durable field binds the two identifiers. |
| Helper temporary files | `prepare()` makes a `TemporaryDirectory`; `execute_guarded()` enters it only around helper invocation and exits the context before final cleanup. | Temporary helper output is removed on context exit. |
| Why Scene evidence is absent from the durable artifact | `persist_artifact()` writes only `supervisor_metadata.json`; it does not copy `scene_summary.json`, `request_metadata.json`, `scene_response.pb`, or a SHA file from the temporary directory. | The current artifact cannot independently audit the reported Scene status. This is a material evidence-retention defect. |

The smallest future-run repair, if a new authority is ever considered, is to
make the durable run directory and guard run ID one immutable shared identity,
and atomically persist the helper's canonical summary, metadata, raw protobuf
when present, and raw SHA-256 before cleanup. This report neither creates nor
approves such a run.

## 5. Warning classification

| Preserved warning or log family | Classification | Reason |
| --- | --- | --- |
| `SDFFeatures` reports that geometry for `base_link_collision` could not be created (lines 285--287). | `RELEVANT_TO_S3_D3` | It may affect collision geometry in the spawned model, but does not establish the approved named collision, ContactSensor identity, an event, or any policy outcome. |
| Unknown `frame_id` child under the existing RPLiDAR sensor (lines 256 and 329). | `RELEVANT_TO_S3_D3` | It is conversion/spawn evidence relevant to sensor preservation generally, but is not evidence about the ContactSensor. |
| Ogre material-script and unsupported-material warnings. | `INFORMATIONAL` | Rendering/material compatibility only; no collision/contact conclusion follows. |
| QML binding-loop and GUI rendering warnings. | `INFORMATIONAL` | GUI layout/rendering diagnostics; no Scene hierarchy or contact conclusion follows. |
| Deprecated `ignition-*` plugin-name warnings. | `INFORMATIONAL` | Compatibility warning for existing world plugins; it does not establish ContactSensor behavior. |
| Existing Gazebo subscriptions to `/cmd_vel`, world-control service advertisement, GUI Spawn/WorldControl plugins, and unrelated tugbot/Depot joint-controller messages. | `OUT_OF_SCOPE` | These are pre-existing world/GUI/plugin capabilities visible after launch, not supervisor-issued command/control actions and not Typed Scene identity evidence. |
| Launch escalation from SIGINT to SIGTERM (lines 343--345). | `RELEVANT_TO_S3_D3` | It directly contradicts any end-to-end claim that cleanup completed SIGINT-only. |

## 6. Final reconciliation

```text
S3_D3_EXECUTION_OCCURRED_BUT_SENSOR_EVIDENCE_NOT_INDEPENDENTLY_AUDITABLE
```

The launch, world initialization, world-scope Contact system load, one observed
robot entity creation event, and Scene service advertisement are preserved.
The claimed `SCENE_SENSOR_PRESENT_IDENTITY_ONLY` result is not: it survives only
as supervisor metadata without the canonical helper evidence required to audit
it. Cleanup is formally incomplete, and the preserved launch log records an
internal SIGTERM escalation after the allowed SIGINT grace.

No runtime operation, command/control operation, or hardware operation was
performed during this reconciliation.
