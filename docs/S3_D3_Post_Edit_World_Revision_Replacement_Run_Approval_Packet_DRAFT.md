# S3 D3 — Post-Edit World Revision Replacement Passive Contact Run Approval Packet

**Status: COMPLETED_INVALID_RUN — EVIDENCE_RETAINED — NEW_REPAIR_AND_APPROVAL_REQUIRED**

## Purpose and scope

## Superseded execution state and repair record

This packet is no longer pending execution: its one S3.3.12 replacement-run approval was consumed by the completed invalid run `run-contact-replacement-20260926T145616Z-01`. The packet grants no current authority to execute another run.

The world-name parser repair is recorded in [Contact Preflight Repair Validation Report](../artifacts/simulation/contact_producer_evidence/repair_validation/Contact_Preflight_Repair_Validation_Report.md). It was validated offline only. A further run needs a new approval packet after repair; it is not authorized by this historical packet.

## Recorded S3.3.12 outcome

The single approved replacement attempt, `run-contact-replacement-20260926T145616Z-01`, is **INVALID** and is retained. The approved post-edit SHA-256 matched both source and installed world files; the named collision, one ContactSensor/topic, Contact-system declaration, rendered Xacro literals, and collector/analyzer source scan also passed.

It stopped before Gazebo, the temporary one-topic bridge, and the collector because the tool's source-level world-name check only accepted a double-quoted attribute. The current SDF correctly declares `<world name='world_demo'>`, so the check recorded `world_name_count: 0` and failed closed. No raw Contacts or `/clock` payload, graph snapshot, scoped-name, bridge-delivery, duplicate, or multiplicity evidence exists. No `/cmd_vel` publication, control service/action, or hardware operation occurred; shutdown was complete with no measurement-created process.

This is a tool-preflight defect, not evidence against Gazebo, the Contact system, the ContactSensor, or GZ-to-ROS bridge delivery. The one-run approval is consumed. Any new run requires offline repair/validation of the preflight parser and a separate user approval; it is not an automatic retry. No D3 collision policy, ContactLatch, runtime, reward/termination, Gym/training, command, or hardware approval is created by this result.

This completed packet is retained as historical scope and evidence for the post-edit source-world revision. Its one replacement-run approval is consumed; it does not request or authorize another execution.

The earlier run was `INVALID` before Gazebo, the bridge, or the collector started because its SHA-256 gate belonged to the source-world revision before the approved world-scope Contact system was added. That preflight mismatch is not evidence of a Gazebo, ContactSensor, or bridge failure. The preserved result is documented in [Contact Producer Evidence Report](../artifacts/simulation/contact_producer_evidence/Contact_Producer_Evidence_Report.md); neither that report nor the old raw artifact is changed by this packet.

This packet corrects terminology: the temporary endpoint is a **one-topic raw Contacts bridge**, not a one-service bridge. The raw topic is measurement-only and is not an official runtime topic contract.

## 1. Post-edit revision audit

### Mandatory source-world gate

| Item | Current source evidence | Gate for a replacement run |
| --- | --- | --- |
| World name | `world_demo` in [`tugbot_depot.sdf`](../ros2_ws/src/ROBOT_URDF_final_description/launch/tugbot_depot.sdf) | Must match exactly. |
| Current world-file SHA-256 | `1c50f90d151a12559d426796c5d153c829b8777a5b4e8ef94c007a2023f6e271` | Must match exactly before Gazebo launch/capture. |
| Prior consumed-run SHA-256 | `a5e9c9b1e9b8ad11e0399855f06de687f04c702258b8b74ce563523d78ed55fe` | Historical only; it must not be reused for this replacement run. |

The new digest was computed from the current bytes of `ros2_ws/src/ROBOT_URDF_final_description/launch/tugbot_depot.sdf`. It is a source-revision identity gate only; it does not establish a runtime world load or a Gazebo application receipt.

### Scoped source-diff evidence

A review of the current scoped source diff finds only the three approved Option A+C changes below. No diff hunk changes `/cmd_vel`, a control service, motion plugin configuration, existing collision geometry, or world entities. No official runtime bridge configuration was changed.

| Approved surface | Current evidence | Scope result |
| --- | --- | --- |
| Existing base box collision | [`ROBOT_URDF_final.xacro`](../ros2_ws/src/ROBOT_URDF_final_description/urdf/ROBOT_URDF_final.xacro) names the existing collision `s3_d3_base_contact_collision`; its existing origin and `0.4 0.28 0.10` box remain unchanged. | Exactly one approved name addition. |
| ContactSensor | [`ROBOT_URDF_final.gazebo`](../ros2_ws/src/ROBOT_URDF_final_description/urdf/ROBOT_URDF_final.gazebo) has exactly one `s3_d3_base_contact_sensor` in the existing `base_link` extension, targeting that literal and `/s3_d3/contact/raw`. | Exactly one approved sensor addition. |
| World Contact system | [`tugbot_depot.sdf`](../ros2_ws/src/ROBOT_URDF_final_description/launch/tugbot_depot.sdf) has exactly one world-scope `filename="gz-sim-contact-system"`, `name="gz::sim::systems::Contact"` declaration. | Exactly one approved system addition. |
| Official bridge runtime config | No diff hunk in the audited source revision. | Unchanged; the bridge remains temporary and artifact-owned. |

This is a static-source audit. It does not prove Gazebo accepts the generated description, loads the system, resolves sensor/collision scoped names, or publishes a topic.

## 2. Immutable literals for the proposed replacement run

| Field | Required literal |
| --- | --- |
| Gazebo world | `world_demo` |
| World-file SHA-256 | `1c50f90d151a12559d426796c5d153c829b8777a5b4e8ef94c007a2023f6e271` |
| Collision target | `s3_d3_base_contact_collision` |
| ContactSensor | `s3_d3_base_contact_sensor` |
| GZ raw topic | `/s3_d3/contact/raw` |
| ROS raw topic | `/s3_d3/contact/raw` |
| Gazebo message | `gz::msgs::Contacts` |
| ROS message | `ros_gz_interfaces/msg/Contacts` |
| Bridge direction | `GZ_TO_ROS` |
| Temporary bridge argument | `/s3_d3/contact/raw@ros_gz_interfaces/msg/Contacts[gz.msgs.Contacts` |

The `[` marker is the locally documented `parameter_bridge` syntax for Gazebo-to-ROS. The replacement-run preflight must still verify that the actual running bridge process exposes only this one Contacts mapping with the exact topic/type/direction; static command syntax is not runtime delivery evidence.

## 3. Passive replacement-run boundary

The artifact-owned collector may observe only:

```text
/s3_d3/contact/raw
/clock
graph metadata
```

It must not create a publisher, service client, or action client. The replacement run must not use or invoke:

```text
/cmd_vel
teleop
Nav2
PPO, Gymnasium, or Stable-Baselines3
pose, reset, pause, step, spawn, delete, or world control
UART, STM32, Pi, motor, firmware, or hardware
```

The run captures raw payloads only. It does not classify collision, construct a ContactLatch, consume an event, create a reward/termination/Gym transition, or decide a collision filter policy.

## 4. Mandatory replacement preflight

Every gate below must pass before capture begins. Any failure records `INVALID` before payload interpretation; it does not authorize a retry.

| Gate | Required evidence | Fail-closed behavior |
| --- | --- | --- |
| World revision | Current source world name is `world_demo` and SHA-256 is the post-edit literal in this packet. | `INVALID`; do not launch/capture beyond the applicable safe preflight point. |
| Generated robot description | Xacro render contains the approved collision and exactly one approved ContactSensor/topic literal. | `INVALID`; no topic substitute. |
| Contact configuration | Running world has the exact Contact system and exactly one approved sensor target. | `INVALID`; do not infer from a raw topic alone. |
| Raw bridge | Actual one-topic bridge is exact `gz::msgs::Contacts` to `ros_gz_interfaces/msg/Contacts`, one-way `GZ_TO_ROS`. | `INVALID`; no bidirectional or alternate bridge. |
| Graph/type | Pre-run graph records raw topic/type, `/clock`, and relevant producer/consumer metadata. | `INVALID` if incomplete or mismatched. |
| `/cmd_vel` boundary | Freeze a publisher allowlist from the actual pre-run graph; collector is not a publisher. | Stop/fail closed if an out-of-allowlist publisher appears. The allowlist only establishes collector non-publication, not global absence of message traffic. |
| Collector boundary | Source scan proves no publisher, service client, or action client. | `INVALID` before capture. |

## 5. Capture and interpretation limits

If preflight passes, retain each full raw `ros_gz_interfaces/msg/Contacts` aggregate, all nested contact entries, available IDs/names/types, positions/normals/depths/wrenches, producer simulation timestamp only when populated, and a separate steady receive timestamp. Record raw cardinality, repeated observations, simultaneous entries, bridge process provenance, and pre/post graph snapshots.

Neither a present nor an absent raw payload establishes collision policy, collision severity, action-interval membership, ContactLatch behavior, reset semantics, reward/termination, or any training/runtime readiness.

## 6. Shutdown and one-run rule

Only process groups created by the measurement may receive SIGINT. No SIGTERM, SIGKILL, `.kill()`, `kill -9`, or force-kill fallback is allowed.

```text
SIGINT → bounded graceful wait
still alive → SHUTDOWN_INCOMPLETE
             → retain artifact/blocker
             → prohibit another run
             → require a separate user/operator decision
```

This approval requests one replacement run only. Any failure, including preflight failure, consumes it; a later run needs another explicit user approval.

## 7. Historical approval checklist — superseded

This historical checklist was consumed by S3.3.12. It is retained for provenance only and grants no authority for another run:

- the post-edit SHA-256 `1c50f90d151a12559d426796c5d153c829b8777a5b4e8ef94c007a2023f6e271` for `world_demo`;
- exactly one passive replacement run using the literals in Section 2;
- exactly one temporary **one-topic raw Contacts bridge** with the stated one-way direction;
- raw observation only, with the preflight, `/cmd_vel` allowlist, collector, and SIGINT-only shutdown rules above.

## Retained non-claims

This packet does not approve a permanent bridge/topic contract, Gazebo Contact runtime delivery, contact timestamp/identity behavior, collision policy or filtering, ContactLatch, reset semantics, reward, termination, Gym/SB3/training, command publication, UART, or hardware operation.

**COMPLETED_INVALID_RUN — EVIDENCE_RETAINED — NEW_REPAIR_AND_APPROVAL_REQUIRED.**
