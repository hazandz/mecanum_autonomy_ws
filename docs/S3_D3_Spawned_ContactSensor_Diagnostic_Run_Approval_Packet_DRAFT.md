# S3 D3 — Spawned ContactSensor Diagnostic Run Approval Packet

**Status: COMPLETED — DIAGNOSTIC_INCOMPLETE_SENSOR_QUERY — EVIDENCE_RETAINED — NO EXECUTION AUTHORITY REMAINS**

## Purpose and authority boundary

## Recorded S3.3.20 outcome

The one execution authority was consumed atomically by `run-spawned-contactsensor-diagnostic-20260926T161318Z-01` with final classification `DIAGNOSTIC_INCOMPLETE_SENSOR_QUERY`. The approval-bound guard `S3.3.20_SPAWNED_CONTACTSENSOR_DIAGNOSTIC_RUN` was bound to this packet's pre-execution SHA-256 `2f5cca9ed0c81e541d385e9107d2cea4f5850eacb5d8bda06e77c0531d61d3d4`, the world hash, and all immutable literals; it now records `consumed`.

The source/install world hash, world identity, Xacro render, and source literal gates passed. Gazebo launched and shut down cleanly by SIGINT. `gz model --list` exited `0`, but its retained output used list entries prefixed with `-`; the diagnostic parser did not parse that output as an exactly-once `ROBOT_URDF_final` identity. Per the locked fail-closed contract, no link, sensor, topic, or type query was run and the run did not conclude sensor absence.

No separate diagnostic/raw-contact bridge, ROS collector, raw-contact collector, analyzer, publisher, service/action client, or control action was started. The existing launch-owned `ros_gz_bridge` was observed as the pre-existing `/cmd_vel` publisher/subscriber in the retained graph snapshot; the diagnostic did not configure it or publish through it. The artifact and report are retained at [S3.3.20 diagnostic artifact](../artifacts/simulation/contact_producer_evidence/run-spawned-contactsensor-diagnostic-20260926T161318Z-01/). This packet is historical evidence only and cannot authorize another run.

This packet proposes exactly one future, read-only, spawned-ContactSensor diagnostic run designed in [Spawned ContactSensor Diagnostic Run Design](S3_D3_Spawned_ContactSensor_Diagnostic_Run_Design_DRAFT.md). It is separate from the consumed S3.3.17 passive raw-contact run recorded in [Post-Repair Passive Contact Run Packet](S3_D3_Post_Repair_Passive_Contact_Run_Approval_Packet_DRAFT.md). It does not create execution authority, an approval guard, a bridge, a collector, or a runtime process.

The only question is whether the approved ContactSensor source literals become observable after the existing robot spawn and, if so, which Gazebo Transport `gz.msgs.Contacts` endpoint is actually advertised. This is not a collision-evidence run and it does not establish ContactLatch, collision policy, reward, termination, training, or hardware readiness.

## 1. Immutable proposed run scope

| Field | Required literal |
| --- | --- |
| Gazebo world | `world_demo` |
| World-file SHA-256 | `1c50f90d151a12559d426796c5d153c829b8777a5b4e8ef94c007a2023f6e271` |
| Robot model | `ROBOT_URDF_final` |
| Link | `base_link` |
| Collision literal | `s3_d3_base_contact_collision` |
| ContactSensor literal | `s3_d3_base_contact_sensor` |
| Configured topic hypothesis | `/s3_d3/contact/raw` |
| ROS bridge | None |
| ROS collector | None |
| Raw-contact analyzer | None |
| Capacity if approved | Exactly one diagnostic run |

The world hash is the post-edit source revision retained by S3.3.17. A mismatch in world name or hash is fail-closed before any diagnostic query. The topic literal is a hypothesis only: it must not be forced, renamed, or treated as an official runtime topic contract.

## 2. Allowed read-only operations and evidence

After the source-revision/hash gate and Gazebo launch, the future run may use only the following locally verified read-only inspection commands:

```text
gz model --list
gz model -m ROBOT_URDF_final -l base_link
gz model -m ROBOT_URDF_final -l base_link -s s3_d3_base_contact_sensor
gz topic -l
gz topic -i -t <candidate-topic>
```

The run must retain, for every query regardless of outcome:

- exact command literal and query sequence number;
- process exit code;
- raw stdout and stderr;
- timeout flag;
- parse status;
- timestamp on one declared local clock; and
- supplied/resolved model and link identity where applicable.

The topic enumeration must be retained in full. The run must query type for every candidate topic actually selected from the successfully parsed enumeration under the discovery policy in the design document. It must not only test `/s3_d3/contact/raw`. Each candidate literal and its raw `gz topic -i -t` result must be retained exactly as observed.

The future artifact must also retain launch log, source/world/Xacro gate results, `/cmd_vel` graph snapshot if a ROS graph already exists from the launch, frozen pre-existing publisher allowlist, and SIGINT-only shutdown record. The allowlist is boundary observation only: it authorizes no publication and does not establish absence of traffic from any other process.

## 3. Strict prohibitions

The proposed run must not:

- publish `/cmd_vel` or use teleop, Nav2, PPO, Gymnasium, or SB3;
- invoke pose, reset, pause, step, spawn, delete, world-control, service, or action operations;
- start a ROS bridge, ROS collector, raw-contact collector, or contact analyzer;
- modify robot/world source, runtime source, bridge configuration, tooling, or historical approval/run records; or
- access UART, firmware, Pi, STM32, motor, or hardware.

No query is permitted after an upstream fail-closed gate has failed. There is no retry, alternate model/link guess, or second run under a future one-run approval.

## 4. Locked fail-closed classification

| Result | Exact required condition |
| --- | --- |
| `DIAGNOSTIC_INCOMPLETE_SENSOR_QUERY` | Any model/link/sensor query fails, times out, cannot reach Transport, is unparseable, or an upstream model/link identity is not confirmed. |
| `SENSOR_ABSENT_AFTER_SPAWN` | `ROBOT_URDF_final` is confirmed exactly once; `base_link` query succeeds and parses; sensor query succeeds and parses but omits exact `s3_d3_base_contact_sensor`. |
| `DIAGNOSTIC_INCOMPLETE_ENDPOINT_QUERY` | Sensor is confirmed, but topic enumeration or any required type query fails, times out, cannot reach Transport, is unparseable, or candidate inspection is unfinished. |
| `SENSOR_PRESENT_ENDPOINT_ABSENT` | Sensor is confirmed; topic enumeration succeeds and parses; the full enumerated topic set and candidate-discovery result are retained; no `Contacts` candidate is discoverable for type query. |
| `SENSOR_PRESENT_ENDPOINT_DISCOVERED` | Sensor is confirmed and successful `gz topic -i -t` output for an observed candidate reports exact `gz.msgs.Contacts`. |

`DIAGNOSTIC_INCOMPLETE_COLLISION_IDENTITY` must always be retained if no separately verified, read-only collision/ECS-component inspection API is available at execution time. Source or Xacro collision text must not be substituted for spawned-collision evidence.

No classification is evidence of a collision event, ContactLatch, collision filter/policy, reward, termination, Gym/training, or runtime readiness. In particular, endpoint absence does not establish that no contact occurred, and endpoint discovery does not establish raw-payload delivery or contact semantics.

## 5. Shutdown and future approval-bound guard requirement

Only process groups created by the diagnostic may receive SIGINT. SIGTERM, SIGKILL, `.kill()`, `kill -9`, and force-kill fallback are prohibited.

```text
SIGINT → bounded graceful wait
still alive → SHUTDOWN_INCOMPLETE
             → retain artifact and blocker
             → prohibit another run
             → require separate user/operator decision
```

If the user approves this packet, the future supervisor/authorization mechanism must use an approval-specific identity and bind it to this exact packet SHA-256, the world SHA-256, and every literal in Section 1. The guard must have capacity `1`, permit acquisition only once, atomically consume that same approval identity after any final outcome, and fail closed on a missing, malformed, stale, hash-mismatched, literal-mismatched, locked, or consumed record. This is a design requirement only: **no guard or authorization record is created by this packet.**

## 6. Required user approval statement

Before execution, the user must explicitly approve all of the following as one bounded operation:

- exactly one read-only spawned ContactSensor diagnostic run;
- the world/hash and all literals in Section 1;
- the five command forms in Section 2 and query-all-discovered-candidates policy;
- the locked classifications in Section 4, including incomplete results for query failure; and
- SIGINT-only shutdown and one-run capacity.

No earlier consumed S3.3.15 or S3.3.17 artifact/packet grants this authority.

## Conclusion

**COMPLETED — DIAGNOSTIC_INCOMPLETE_SENSOR_QUERY — NO EXECUTION AUTHORITY REMAINS**
