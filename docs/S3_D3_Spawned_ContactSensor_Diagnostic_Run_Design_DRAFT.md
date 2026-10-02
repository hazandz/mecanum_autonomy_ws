# S3 D3 — Spawned ContactSensor Diagnostic Run Design

**Status: DRAFT — DIAGNOSTIC RUN DESIGN ONLY — PENDING USER APPROVAL**

## Scope and single diagnostic question

This document designs one future, approval-gated, read-only spawn diagnostic. It does not authorize or create an execution approval, guard, collector, bridge, or source change. It does not run Gazebo, ROS, `gz`, a bridge, a collector, a command path, a service, or hardware.

The single question is: **at which layer between robot spawn and Gazebo Transport advertisement is `s3_d3_base_contact_sensor` lost, unavailable, or advertised under an unobserved endpoint?** The diagnostic is limited to establishing the presence of the spawned robot/model, its `base_link`, the named collision where a locally verified method exists, the ContactSensor, and any actual GZ endpoint/type. It does not induce, classify, or infer collision.

This design follows the retained S3.3.17 result: the requested `/s3_d3/contact/raw` endpoint was absent from the passive GZ topic listing, although the source literal, Xacro render, and world-level `gz::sim::systems::Contact` load were confirmed. See [Contact Endpoint Root-Cause Audit](S3_D3_Contact_Endpoint_Root_Cause_Audit_DRAFT.md) and the retained [S3.3.17 run](../artifacts/simulation/contact_producer_evidence/run-contact-replacement-20260926T153527Z-01/).

## 1. Locally verified read-only inspection methods

The following command forms are evidenced by local installed Gazebo Sim 8 / Transport 13 command registrations and completion metadata; they are information queries, not mutation commands:

| Method | Local evidence | Read-only purpose | Explicit limit |
| --- | --- | --- | --- |
| `gz model --list` | [`cmdmodel8.rb`](/opt/ros/jazzy/opt/gz_sim_vendor/lib/ruby/gz/cmdmodel8.rb) registers `--list` as “Get a list of the available models.” | List spawned models and locate `ROBOT_URDF_final`. | Does not establish a link, collision, or sensor by itself. |
| `gz model -m ROBOT_URDF_final -l base_link` | The same local command implementation documents `-l/--link` as “Select a link to show its properties.” | Query the named link beneath the selected model. | Does not prove a specific collision entity/component unless the command output actually includes it. |
| `gz model -m ROBOT_URDF_final -l base_link -s s3_d3_base_contact_sensor` | The local implementation documents `-s/--sensor` as an information query requiring selected model and link. | Query the exact sensor by model/link/name. | Must not be treated as proof of an endpoint until Transport endpoint query also succeeds. |
| `gz topic -l` | The installed Transport 13 completion declares `-l/--list`; the retained S3.3.17 artifact actually used it passively. | Enumerate advertised GZ Transport endpoints. | An absent requested endpoint does not prove absence of contact. |
| `gz topic -i -t <discovered-topic>` | The installed Transport 13 completion declares `-i/--info` and `-t/--topic`; retained contact tooling uses this exact information-query form. | Query a discovered endpoint's runtime type before any bridge is considered. | It cannot inspect an endpoint that is not listed. |

**No local read-only method confirmed:** the installed `gz model` command exposes model, link, sensor, joint, and pose information, but its local implementation does not document a collision/component query. Gazebo headers expose `components::ContactSensor` and `components::ContactSensorData`, but that is a C++ ECS API, not an installed standalone CLI inspection contract. This diagnostic must record the collision layer as incomplete unless an approved run captures a reliable read-only collision identity from the documented model/link query output or a separately verified local read-only API is identified before execution. It must not fabricate a collision result.

## 2. Query-record contract and fail-closed classification

Every future query record must retain all of the following, including when the query fails:

- exact command literal;
- process exit code;
- raw stdout and raw stderr without replacement or summary;
- explicit timeout flag;
- parse status (`PARSED`, `NOT_PARSED`, or a typed parser failure);
- query timestamp from one declared local clock; and
- the model/link identity values supplied to the command, where applicable.

No status that contains `ABSENT` may be produced from a nonzero exit code, timeout, unavailable Transport server, malformed or unparseable output, or an unconfirmed upstream identity. Those conditions are diagnostic-tool/query failures, not evidence of a missing spawned object or endpoint.

| Situation | Required classification | Minimum evidence boundary |
| --- | --- | --- |
| Sensor query exits successfully; the robot model and `base_link` are confirmed; parsed output is valid but does not contain exact literal `s3_d3_base_contact_sensor`. | `SENSOR_ABSENT_AFTER_SPAWN` | Only after all upstream identity/query gates have passed. |
| Sensor query fails, times out, cannot reach Transport, has unparseable output, or model/link identity is not confirmed. | `DIAGNOSTIC_INCOMPLETE_SENSOR_QUERY` | Preserve raw query evidence; do not infer sensor absence. |
| Sensor is confirmed; topic enumeration exits successfully and parses; no candidate `Contacts` endpoint is discoverable for type query. | `SENSOR_PRESENT_ENDPOINT_ABSENT` | Record the full enumerated topic set and the explicit candidate-discovery result; do not test only `/s3_d3/contact/raw`. |
| `gz topic -l` or any required `gz topic -i` query fails, times out, cannot reach Transport, has unparseable output, or does not finish type inspection. | `DIAGNOSTIC_INCOMPLETE_ENDPOINT_QUERY` | Preserve raw query evidence; do not infer endpoint absence. |
| Sensor and endpoint are confirmed; type query completes and reports exact `gz.msgs.Contacts`. | `SENSOR_PRESENT_ENDPOINT_DISCOVERED` | Retain exact endpoint literal and type-query output. |

## 3. Required post-spawn evidence chain

All commands below are proposed for a future approved run only. The exact current source revision and its approved world identity/hash must be verified before launch. Any missing required evidence stops the diagnostic without bridge startup, ROS collection, command publication, service/action calls, or world control.

| Check | Evidence to retain | Locally verified read-only command/tool | Expected evidence | Fail-closed result |
| --- | --- | --- | --- | --- |
| Robot entity | Full query record plus raw command output and Gazebo launch-log correlation | `gz model --list`; existing launch log already records `Created entity ... named [ROBOT_URDF_final]` for S3.3.17 | Exactly one parsed/discoverable `ROBOT_URDF_final` model identity. | `DIAGNOSTIC_INCOMPLETE_ROBOT_ENTITY`; do not infer downstream link/sensor state. |
| `base_link` | Full query record plus raw link-query output bound to the one confirmed robot-model identity | `gz model -m ROBOT_URDF_final -l base_link` | A successful, parseable link-information response for `base_link`. | `DIAGNOSTIC_INCOMPLETE_BASE_LINK`; do not query a guessed alternate link. |
| Collision `s3_d3_base_contact_collision` | Any raw, read-only evidence that names the collision and binds it to the discovered `base_link` | `NO_LOCAL_READ_ONLY_METHOD_CONFIRMED` for direct collision/component inspection on the installed CLI | Only accept explicit runtime identity evidence if a separately verified local read-only method is available before execution. | `DIAGNOSTIC_INCOMPLETE_COLLISION_IDENTITY`; do not treat source/Xacro text as spawned-collision proof. |
| ContactSensor `s3_d3_base_contact_sensor` | Full query record with selected model/link and exact sensor literal | `gz model -m ROBOT_URDF_final -l base_link -s s3_d3_base_contact_sensor` | Successful, parseable sensor information for the exact literal, associated with the confirmed selected model/link. | `DIAGNOSTIC_INCOMPLETE_SENSOR_QUERY` on query failure/timeout/unparseable output or unconfirmed model/link; otherwise `SENSOR_ABSENT_AFTER_SPAWN` only when valid output omits the exact literal. |
| GZ endpoint and type | Full query records for `gz topic -l` and every attempted type query; retain every listed endpoint selected as a candidate and each type result | `gz topic -l`; then `gz topic -i -t <discovered-topic>` for every actually listed candidate endpoint. `/s3_d3/contact/raw` is queried only if it is listed; another listed candidate is retained verbatim, never renamed. | An actual endpoint literal and a successful exact `gz.msgs.Contacts` type result, if advertised. | `DIAGNOSTIC_INCOMPLETE_ENDPOINT_QUERY` on enumeration/type-query failure, timeout, unavailable Transport, unparseable output, or unfinished candidate inspection; otherwise `SENSOR_PRESENT_ENDPOINT_ABSENT` only when enumeration parses and no `Contacts` endpoint is discoverable. |

The source-configured endpoint `/s3_d3/contact/raw` is a hypothesis to test, not a name to force. The diagnostic must retain the complete parsed topic enumeration and every actual candidate endpoint selected for `gz topic -i -t`; it must not inspect only the configured literal. No bridge is included: endpoint discovery and type inspection end on the Gazebo Transport side.

## 4. Future-run boundary and retained artifacts

The future diagnostic must launch only the current approved source revision of Gazebo and retain:

- Gazebo launch command and logs, current world name/hash gate, and static source/Xacro gate outputs;
- raw output and exit status for each read-only `gz model` and `gz topic` inspection command;
- the exact order of inspection, steady wall/receive metadata for administrative traceability, and the final diagnostic classification;
- process ownership and SIGINT-only shutdown record.

It must not start a ROS bridge, ROS collector, raw-contact collector, or contact analyzer. It must not publish `/cmd_vel`; invoke teleop, Nav2, PPO, Gymnasium, SB3, pose/reset/pause/step/spawn/delete/world-control; or interact with UART, STM32, Pi, motor, or any hardware.

If a ROS graph exists because the approved existing launch creates one, the diagnostic may snapshot publisher metadata and freeze the pre-existing `/cmd_vel` publisher allowlist for boundary evidence. This is observation only: the allowlist does not authorize publication and does not prove that another process sent no message.

Shutdown is SIGINT-only for measurement-created process groups. `SHUTDOWN_INCOMPLETE` must preserve the artifact and block a later run; no SIGTERM, SIGKILL, `.kill()`, `kill -9`, or force-kill fallback is permitted.

## 5. Valid diagnostic outcome branches

| Result | Required evidence | Meaning | Next design step | Non-claim |
| --- | --- | --- | --- | --- |
| `DIAGNOSTIC_INCOMPLETE_SENSOR_QUERY` | Any model/link/sensor query fails, times out, cannot connect to Transport, or cannot be parsed; all raw records are retained. | The diagnostic cannot establish sensor presence or absence. | Repair and validate the diagnostic tooling offline before seeking approval for another run. | Does not establish a source, spawn, sensor, Contact-system, or endpoint defect. |
| `SENSOR_ABSENT_AFTER_SPAWN` | `ROBOT_URDF_final` appears exactly once; `base_link` query succeeds and parses; the sensor query succeeds and parses but omits exact literal `s3_d3_base_contact_sensor`. | The source/Xacro literal did not become an observable spawned sensor through this path. | Only now revisit the root-cause audit's conditional correction candidate: a conversion-supported sensor representation may be designed for approval. | Does not establish collision, ContactLatch behavior, collision policy, or any bridge defect. |
| `DIAGNOSTIC_INCOMPLETE_ENDPOINT_QUERY` | Sensor is confirmed, but topic enumeration or any required type query fails, times out, cannot connect to Transport, cannot be parsed, or does not finish. | The diagnostic cannot establish endpoint presence or absence. | Repair and validate endpoint-query tooling offline before seeking approval for another run. | Does not establish a Contact-system, sensor, endpoint, or bridge defect. |
| `SENSOR_PRESENT_ENDPOINT_ABSENT` | Sensor is confirmed; `gz topic -l` succeeds and parses; full enumeration is retained; no candidate `Contacts` endpoint is discoverable to type-query. | Sensor presence is separated from endpoint advertisement; sensor/Contact-system runtime semantics require a focused design/evidence step. | Design endpoint-advertisement/contact-system diagnostics; do not change robot source automatically. | Does not establish that no contact occurred or that the configured topic name is invalid. |
| `SENSOR_PRESENT_ENDPOINT_DISCOVERED` | Exact sensor information plus a discovered endpoint whose `gz topic -i -t` output reports `gz.msgs.Contacts`. | A GZ-side sensor endpoint/type is observed. | Create a separate, narrowly scoped bridge/topic design using the observed literal; do not assume `/s3_d3/contact/raw` if another endpoint was observed. | Does not establish raw payload delivery, timestamps, collision filtering, ContactLatch, reward, termination, or runtime approval. |

If direct collision identity cannot be established using a locally verified read-only method, the run may still record the robot/link/sensor/endpoint observations, but it must carry `DIAGNOSTIC_INCOMPLETE_COLLISION_IDENTITY` and cannot claim completion of the full five-layer evidence chain.

## 6. Relationship to the existing correction candidate

The conditional correction candidate in the [root-cause audit](S3_D3_Contact_Endpoint_Root_Cause_Audit_DRAFT.md) may become a source-change candidate only after `SENSOR_ABSENT_AFTER_SPAWN`, or evidence equivalent in strength, is recorded. It remains `REQUIRES_USER_APPROVAL — DO NOT IMPLEMENT`.

If the sensor is present but an endpoint is absent, source correction is not justified by this result alone. If the sensor is present and an endpoint is discovered under a different literal, the next step is a bridge/topic design update around the observed endpoint—not an automatic source rename or change. No implementation is proposed or authorized by this document.

## Conclusion

**READY_FOR_USER_APPROVAL_OF_ONE_FAIL-CLOSED_READ-ONLY_SPAWN_DIAGNOSTIC_RUN**

The installed CLI provides local evidence for read-only model/link/sensor and GZ endpoint/type inspection. It does not provide a locally confirmed standalone collision-component inspection method. A one-run diagnostic can therefore resolve the source-to-spawn-to-sensor-to-endpoint branch while preserving the collision-identity limitation explicitly and without creating a bridge, collector, command path, or collision policy.
