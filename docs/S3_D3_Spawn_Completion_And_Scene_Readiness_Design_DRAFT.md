# S3 D3 — Spawn Completion and Scene Readiness Design

**Status: DRAFT — CANDIDATE A IMPLEMENTED OFFLINE ONLY — RUNTIME NOT APPROVED**

## Scope

This packet is a static/offline audit of the handoff between the approved
bootstrap-only launch and the one permitted typed Scene request. It creates no
guard or execution authority and does not authorize launch, Gazebo, ROS, `gz`,
bridge, helper runtime, service request, command/control, or hardware activity.

The issue is narrow: a typed `Empty → Scene` response can classify exact model,
link, and sensor hierarchy only after a separately established bootstrap
readiness condition. The historical `TimerAction(period=3.0)` invocation schedule was not a spawn
receipt. S3.3.40 removes it; direct create exit `0` plus delay remains only an
operational convention, not a spawn receipt.

## Static evidence for `ros_gz_sim create`

| Question | Local evidence | What the evidence establishes | What it does not establish |
| --- | --- | --- | --- |
| How is create owned after S3.3.40? | [typed_scene_observer.launch.py](../ros2_ws/src/ROBOT_URDF_final_description/launch/typed_scene_observer.launch.py) now provides only the locked world/resource/Xacro/description bootstrap. [run_typed_scene_observer.py](../artifacts/simulation/contact_producer_evidence/tools/run_typed_scene_observer.py) defines the supervisor-owned, exact allowlisted create contract. | A future supervisor can directly own one create child and record opaque OS completion metadata without parsing logs. | That the process received a description, sent a request, or that Gazebo created an entity. The launch and create contract were not run. |
| Does installed `create` consume a topic description? | `/opt/ros/jazzy/lib/ros_gz_sim/create` contains `set_XML_from_topic`, `Waiting messages on topic [%s].`, `Failed to get XML from topic [%s].`, and the usage literal `-topic TOPIC`. Its symbols include a `std_msgs::msg::String` subscription path. | The installed executable has a topic-description acquisition path and builds an `gz::msgs::EntityFactory`. | DDS delivery timing, the exact received payload, or successful Gazebo insertion in this particular future run. |
| Does installed `create` use a Gazebo request path? | The same executable contains `Node::Request(): Error discovering service`, `Waiting for service [%s] to become available ...`, `Entity creation successful.`, and `Entity creation failed.`; its embedded source path is `./src/create.cpp`. | The installed binary has a service-discovery/request path and distinct success/failure reporting. | Exact return-code implementation, whether a success report is a Gazebo acceptance receipt versus a completed ECS/Scene insertion, or entity visibility timing. |
| Is a source-level exit-code contract installed locally? | No readable installed `src/create.cpp` source or version-matched API documentation specifying `main()` return semantics was found; only the executable, symbols, headers, package metadata, and launch examples are installed. | `ros_gz_sim` version `1.0.22` and the executable location are identified. | That exit code `0` has any specific semantic beyond process-level success. |
| Does create prove Scene presence? | No local source/API contract found ties process exit, output text, or request success to a subsequent `/world/world_demo/scene/info` response containing `ROBOT_URDF_final`. | None. | Exact model/link/sensor presence in Scene. |

The related local header
`/opt/ros/jazzy/include/ros_gz_sim/spawn_entity.hpp` describes a different
`EntitySpawner` ROS service-client utility. It is not the approved
`ros_gz_sim create -topic` bootstrap route and is not selected as evidence.

## Historical and retained race

```text
historical TimerAction(3.0), or future direct create exit 0 + delay
    ≠ description was received / proves only an operational convention
    ≠ Gazebo accepted an entity-factory request
    ≠ ROBOT_URDF_final exists in a typed Scene response

Scene service appears
    ≠ ROBOT_URDF_final has been inserted
```

The helper's `ServiceList` preflight proves only exact availability of
`/world/world_demo/scene/info`; it does not order that service against initial
entity creation. Without an independent readiness barrier, a single early Scene
response reporting zero exact models is ambiguous. It must not be labeled
`SCENE_MODEL_ABSENT`, `SCENE_LINK_ABSENT`, or `SCENE_SENSOR_ABSENT`. Candidate A
does not change that limitation: its fixed delay is only an operational barrier.

## Fail-closed state contract

| Outer status | Preconditions / meaning | Prohibited interpretation |
| --- | --- | --- |
| `SCENE_BOOTSTRAP_UNCONFIRMED` | The required bootstrap readiness mechanism is absent, fails, times out, or cannot prove its own defined condition before the one Scene request. The helper must not send `RequestRaw` in this state. | Model, link, sensor, endpoint, or collision absence. |
| `SCENE_BOOTSTRAP_READY_FOR_ONE_REQUEST` | With Candidate A only: the approved create process completed with the selected exit-success convention and the user-approved fixed delay elapsed. It permits exactly one request. | Entity existence, reset receipt, settled state, atomic insertion, or Scene receipt. |
| Existing `SCENE_SERVICE_UNAVAILABLE` | Bootstrap readiness was established, but exact typed Scene service discovery failed before the sole request. | Model/link/sensor absence. |
| `SCENE_*_NOT_OBSERVED_AFTER_DELAY` | Candidate A was used, the one decoded Scene response lacks an exact hierarchy member at the relevant level, and no malformed/duplicate condition applies. | Actual absence, failed spawn, conversion failure, or sensor failure. |
| Existing `SCENE_*_ABSENT` statuses | Reserved for a future approved Candidate B with a machine-readable readiness receipt whose semantics and ordering are proven. | Any Candidate A conclusion. |
| Positive exact identity status | `SCENE_SENSOR_PRESENT_IDENTITY_ONLY` may be emitted when the exact identity exists in the one typed response. | Any claim beyond typed-response content, including collision event or reset receipt. |

`INVALID_EVIDENCE_PERSISTENCE_FAILURE` and `SHUTDOWN_INCOMPLETE` remain outer
fail-closed outcomes. None permits a retry or a second Scene request.

## Candidate readiness barriers — S3.3.40 decision record

| Candidate | Static support | Limited semantics | Open evidence / user decision |
| --- | --- | --- | --- |
| **A. Create process exit-success plus fixed post-create delay** | The installed binary has a topic-subscription/request path and success/failure output, but no installed source-level exit-code contract was located. S3.3.40 implements this as an injected offline-only supervisor contract. | At most: the process completed successfully under the approved operational convention, then the fixed `post_create_delay_ms=2000` guard elapsed. It is not a Scene receipt. | Runtime remains unapproved. The delay is not settle/freshness/reset policy. The future packet/guard must bind `create_timeout_ms=90000` and the exact ownership contract. |
| **B. Machine-readable readiness receipt** | `spawn_entity.hpp` proves another service-client utility exists, but does not prove it applies to the approved `create -topic` route or proves Scene insertion. No locally confirmed machine-readable receipt was found for that route. | Could be used only if a future static audit proves exact request/response semantics and ordering for the approved bootstrap path. | `NO_LOCAL_MACHINE_READABLE_BOOTSTRAP_RECEIPT_CONFIRMED`. Do not select or implement it without a separate design/approval. |

No candidate authorizes a second Scene request, polling Scene for the entity, or
any retry. Candidate A is the only currently describable operational path. It is
implemented and validated offline only and must not be treated as an
entity-existence proof or runtime execution authority.

### Candidate A negative-result taxonomy

| One decoded Scene response after Candidate A exit-success + delay | Required status | Never call it |
| --- | --- | --- |
| Zero exact `ROBOT_URDF_final` model | `SCENE_MODEL_NOT_OBSERVED_AFTER_DELAY` | `SCENE_MODEL_ABSENT` |
| Exactly one model but zero exact `base_link` | `SCENE_LINK_NOT_OBSERVED_AFTER_DELAY` | `SCENE_LINK_ABSENT` |
| Exactly one model/link but zero exact sensor | `SCENE_SENSOR_NOT_OBSERVED_AFTER_DELAY` | `SCENE_SENSOR_ABSENT` |
| Duplicate, malformed, or undecodable response | `SCENE_RESPONSE_UNDECODABLE` | Any observation/absence status |
| Exact model/link/sensor identity exists | `SCENE_SENSOR_PRESENT_IDENTITY_ONLY` | Collision, reset, or full Contact-type proof |

The `*_ABSENT` taxonomy is reserved for a future approved Candidate B only
when a machine-readable readiness receipt is both proven and bound into the
replacement packet/guard.

## Replacement packet and guard impact

A replacement runtime packet and new capacity-one guard remain required. They
must bind, in addition to the existing
world/helper/dedicated-launch literals:

- the selected readiness mechanism and its version/semantics;
- if Candidate A is selected, the exact post-create delay in milliseconds;
- the rule that the helper is not invoked if bootstrap readiness is unconfirmed;
- `SCENE_BOOTSTRAP_UNCONFIRMED` as a terminal outer status;
- exactly one helper invocation and exactly one `RequestRaw`; no retry;
- the already decided `preflight_wait_ms=90000`, `request_timeout_ms=5000`,
  polling `10 ms`, capacity `1`, and SIGINT-only shutdown;
- `create_shutdown_grace_ms=5000`. On create timeout, future runtime code may
  send only SIGINT to the directly owned process group, wait that exact grace,
  retain `SCENE_CREATE_OUTCOME_UNCONFIRMED` / `SCENE_BOOTSTRAP_UNCONFIRMED` if
  the child exits, or report `SHUTDOWN_INCOMPLETE` and block further runs if it
  remains alive. It may not send SIGTERM/SIGKILL, invoke the helper, retry, or
  infer a spawn receipt.

## Non-claims

No readiness outcome is a reset receipt, settled-state proof, collision event,
ContactLatch fact, filter-policy decision, reward/termination input, Gym or
training readiness, raw-contact-topic proof, or hardware readiness. It does
not permit Ground Truth or any task fact into policy observation.

## Conclusion

**IMPLEMENTED_OFFLINE_ONLY — RUNTIME_NOT_APPROVED**

The one Scene request must remain gated behind an explicit readiness mechanism.
Current static evidence cannot safely interpret historical `TimerAction(3.0)`,
Scene service availability, or the S3.3.40 operational create-exit convention
as proof that the locked entity is already represented in Scene.
