# S3 D3 — Option A+C Passive Contact Evidence Run Approval Packet

**Status: COMPLETED_INVALID_RUN — EVIDENCE_RETAINED — NEW_WORLD_HASH_APPROVAL_REQUIRED**

## Purpose and narrow scope

## Recorded S3.3.10 outcome

The approved implementation surface was applied once: the existing `base_link` box collision is named `s3_d3_base_contact_collision`; exactly one `s3_d3_base_contact_sensor` targets it; and exactly one world-scope `gz-sim-contact-system` Contact system was added. Static Xacro/source validation found those literals exactly as approved.

The one approved passive-run attempt, `run-contact-20260926T143804Z-01`, is **INVALID**. It stopped before Gazebo, the temporary bridge, or the collector started because this packet's approved source-world gate was `a5e9c9b1e9b8ad11e0399855f06de687f04c702258b8b74ce563523d78ed55fe`, while the post-edit `tugbot_depot.sdf` hash was `1c50f90d151a12559d426796c5d153c829b8777a5b4e8ef94c007a2023f6e271`. The Contact-system world edit changed the file bytes. The attempt sent no command, called no control service, performed no hardware operation, and captured zero raw Contacts payloads. Shutdown was complete with no measurement-created processes.

This factual outcome does not approve a collision policy, ContactLatch, runtime producer, bridge delivery, timestamp semantics, reward, termination, Gym/training, or hardware. The one-run approval is consumed. A different run requires explicit approval of the post-edit world hash and a separate new-run approval; it is not an automatic retry.

This packet requests approval for **one passive Gazebo simulation evidence run** using only the statically feasible Option A+C path:

```text
one built-in Gazebo Contact system
+ exactly one ContactSensor
+ exactly one GZ-to-ROS raw Contacts bridge
+ an artifact-owned collector subscribing only to raw contacts, /clock, and graph metadata
```

It does not approve implementation, collision classification, a ContactLatch, a terminal decision, reward, training, Gymnasium, a command publisher, simulator control, or hardware operation. It does not modify the current project configuration.

The static feasibility basis is [S3 D3 Static Contact API Feasibility Audit](S3_D3_Static_Contact_API_Feasibility_Audit_DRAFT.md). The required D3 fact/latch contract remains [S3 D3 ContactLatch and Collision Fact Contract](S3_D3_ContactLatch_And_Collision_Fact_Contract_DRAFT.md). Static geometry evidence is limited by [S3 World Geometry and Entity Inventory](S3_World_Geometry_And_Entity_Inventory_DRAFT.md).

## 1. Proposed changes after approval — not applied by this packet

| Proposed surface | Proposed change | Evidence basis | Approval boundary |
| --- | --- | --- | --- |
| `ROBOT_URDF_final_description/launch/tugbot_depot.sdf` | Add `filename="gz-sim-contact-system"`, `name="gz::sim::systems::Contact"` once to the launched `world_demo` world. | Installed Gazebo Sim 8 example `contact_sensor.sdf` uses this exact plugin/system pair. | `PROPOSED`; no world file is changed by this packet. |
| `ROBOT_URDF_final_description/urdf/ROBOT_URDF_final.gazebo` or the authoritative robot-description location selected at implementation review | Configure exactly one `<sensor type="contact">` under the approved robot collision-bearing link. | Installed example establishes syntax; the current robot has no contact sensor. | `PROPOSED`; exact link/collision literal remains a user decision. |
| Existing bridge launch/config, or a temporary artifact-owned bridge approved separately | Add exactly one GZ-to-ROS mapping from `gz::msgs::Contacts` to `ros_gz_interfaces/msg/Contacts`. | Installed `ros_gz_bridge` declares this conversion. | `PROPOSED`; no mapping exists today. |
| `artifacts/simulation/contact_producer_evidence/` | Create passive collector/analyzer and a new evidence-run directory only after approval. | D3 evidence plan. | `PROPOSED`; not created by this packet. |

### Proposed raw-event endpoint

| Item | Proposed value | Status and limitation |
| --- | --- | --- |
| Gazebo message type | `gz::msgs::Contacts` | `STATICALLY_VERIFIED_TYPE`; not a current project topic. |
| ROS message type | `ros_gz_interfaces/msg/Contacts` | `STATICALLY_VERIFIED_TYPE`; not a current project topic. |
| Bridge direction | `GZ_TO_ROS` | `PROPOSED`; raw source must flow from Gazebo ContactSensor to the passive collector. |
| GZ raw topic candidate | `/s3_d3/contact/raw` | `PROPOSED`; not inferred from existing source, not configured, and must be selected/verified in the graph before capture. |
| ROS raw topic candidate | `/s3_d3/contact/raw` | `PROPOSED`; not configured; same spelling is a proposal, not a claim of identity across transport domains. |
| World identity gate | `world_demo` | `OBSERVED_STATIC_SOURCE`; must be verified at runtime together with the world-file SHA-256. |
| World-file SHA-256 gate | `a5e9c9b1e9b8ad11e0399855f06de687f04c702258b8b74ce563523d78ed55fe` for `launch/tugbot_depot.sdf` | Current static-file evidence; mismatch invalidates the run before capture. |

The proposed topic literal does not define an official topic contract. Its sole purpose is to make the requested one-topic scope reviewable before any future implementation.

## 2. Exactly-one sensor target decision

### Static chassis/base evidence

`ROBOT_URDF_final.xacro` defines robot link `base_link` with one box collision element. This is a chassis/base candidate and is preferable to a wheel collision for the proposed passive evidence path because normal wheel–ground support contact would otherwise dominate raw observations.

However, that `<collision>` element has **no explicit `name` attribute** in the static Xacro. The installed ContactSensor example requires a `<contact><collision>...</collision></contact>` target. Gazebo conversion/scoping could assign a name, but this packet must not guess it.

| Candidate | Static source fact | Recommendation | Decision status |
| --- | --- | --- | --- |
| `base_link` collision element | A box collision exists under `link name="base_link"`; collision name is absent. | Preferred category: a single chassis/base collision target, to avoid normal wheel-ground support observations. | `REQUIRED_USER_DECISION` for the exact collision literal and implementation location. |
| `Wheel_LF_1`, `Wheel_RF_1`, `Wheel_RB_1`, `Wheel_LB_1` collision elements | Four wheel collision elements exist; each is unnamed in the Xacro. | Not recommended for the first passive run because wheel-ground events are expected candidates and filtering is not approved. | Not selected. |
| Camera/LiDAR collision elements | Static collision geometry exists on camera and LiDAR links. | Not recommended; accessory-contact policy is not selected. | Not selected. |

This is a sensor-target recommendation only. It does not approve a chassis collision policy, wheel exclusion, or any terminal classification.

## 3. Passive run boundary

### Allowed observation scope

The future collector may subscribe only to:

```text
one raw ros_gz_interfaces/msg/Contacts topic
/clock
graph metadata
```

The run observes raw payloads. It does not classify contacts, decide collision, consume a latch, or generate a transition.

### Explicit prohibitions

The run must not:

- publish `/cmd_vel` or any other command topic;
- use teleop, Nav2, PPO, Gymnasium, Stable-Baselines3, or training;
- call pose, reset, pause, step, spawn, delete, or any world-control service/action;
- create a collision filter, terminal decision, ContactLatch, reward, or termination evaluator;
- access UART, Pi, STM32, motor, firmware, or any hardware.

## 4. Mandatory preflight and fail-closed gates

Before the collector accepts any payload, the future run must verify all items below. Failure of any gate marks the run invalid and prevents interpretation of contacts as evidence.

| Gate | Required check | Fail-closed result |
| --- | --- | --- |
| World identity | Running Gazebo world is `world_demo`. | Invalid; do not capture evidence. |
| World content | SHA-256 of the selected world file matches the literal in this packet. | Invalid; do not capture evidence. |
| Contact system | Exact built-in Contact system/plugin is present and loaded. | Invalid; do not treat a topic as equivalent. |
| Exactly-one sensor | Graph/config evidence identifies exactly one approved ContactSensor and its approved target. | Invalid; no implicit multi-sensor capture. |
| GZ endpoint | Exact proposed/approved GZ raw topic and `gz::msgs::Contacts` type are present. | Invalid; no type substitution. |
| ROS bridge | Exact ROS endpoint has `ros_gz_interfaces/msg/Contacts`, is GZ-to-ROS, and is the only raw-contact bridge approved for this run. | Invalid; no bridge fallback. |
| Graph snapshot | Capture pre-run producer/subscriber/type metadata for contact, `/clock`, and `/cmd_vel`. | Invalid if incomplete. |
| `/cmd_vel` boundary | Freeze the actual pre-run publisher allowlist; collector has no publisher. | Do not start/stop capture if an out-of-allowlist publisher appears. The allowlist proves only collector non-publication, not global absence of commands. |
| Collector source scan | Confirm collector creates no publisher, service client, or action client. | Invalid before capture. |

## 5. Required capture record

Every received `Contacts` message must be retained losslessly. The capture must not discard empty aggregates, individual contact entries, duplicated entries, or simultaneous entries.

| Evidence | Required record | Interpretation boundary |
| --- | --- | --- |
| Aggregate payload | Full raw `Contacts` payload, including aggregate header and every nested contact entry. | Raw observation only; no collision result. |
| Contact identity | For both collision entities: ID, name, type, and available nested header fields. | Name/scoped-name stability must be measured, not assumed. |
| Contact geometry | All positions, normals, depths, and wrenches when present. | Not a clearance metric or collision severity rule. |
| Time | Producer simulation timestamp only if actually populated; local steady receive timestamp recorded separately. | Do not subtract or compare across clock domains without an approved rule. |
| Multiplicity | Per-payload contact count, point counts, receive index, repeated raw entries, and concurrent entries. | Evidence for later duplicate/simultaneous policy; no aggregation is selected here. |
| Endpoint provenance | GZ topic/type, ROS topic/type, bridge process identity/version where observable, and graph snapshots before/after. | Does not prove transition membership. |
| Shutdown | Process ownership, SIGINT attempts, completion/timeout state, and post-run graph snapshot. | No force-kill fallback. |

An idle passive run cannot prove absence of contact, a collision policy, collision-free operation, action interval alignment, reset semantics, or ContactLatch behavior.

## 6. Shutdown rule

Only processes created by the approved measurement run may be stopped, and only through SIGINT to their process groups. If any process remains after the bounded graceful wait:

```text
SHUTDOWN_INCOMPLETE
-> preserve artifact and blocker record
-> do not start another evidence run
-> require a separate user/operator decision
```

No SIGTERM, SIGKILL, `.kill()`, `kill -9`, or force-kill fallback is allowed.

## 7. Decisions explicitly requested from the user

| User approval | Exact scope to approve | Still outside the approval |
| --- | --- | --- |
| Option A+C | One built-in Contact system plus one ContactSensor plus one raw GZ-to-ROS Contacts bridge. | Contact classification, terminal behavior, and runtime ContactLatch. |
| Sensor target | One exact chassis/base collision literal after review of the unnamed `base_link` collision conversion issue. | Wheel/sensor/world-object filter policy. |
| Proposed literals | Plugin/system, sensor name/target, GZ topic, ROS topic, and bridge direction/type. | Permanent runtime topic contract or package ownership change. |
| One passive evidence run | One Gazebo simulation-only run under the boundary in this packet. | Command, pose, reset, pause, world control, training, or hardware operation. |
| Type migration | This remains **not decided**: explicit versioned extension of the test-only `ContactCandidateSnapshot`, or a separate runtime provenance type. | Silent semantic change to the current test-only type. |
| Deferred D3 decisions | Filter policy, duplicate/simultaneous aggregation, action-barrier owner, and ContactLatch semantics remain outside this run. | Any collision/termination decision. |

## Conclusion

**PENDING_USER_APPROVAL_FOR_ONE_PASSIVE_CONTACT_EVIDENCE_RUN.** This packet requests only a tightly bounded Option A+C raw-contact observation path. It grants no implementation, runtime collision, reward, termination, Gymnasium/training, or hardware approval.
