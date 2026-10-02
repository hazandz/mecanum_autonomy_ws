# S3 D3 — Post-Repair Passive Raw-Contact Evidence Run Approval Packet

**Status: COMPLETED_INVALID_RUN — EVIDENCE_RETAINED — NO_EXECUTION_AUTHORITY_REMAINS**

## Purpose and authority

## Recorded S3.3.17 outcome

The one S3.3.15 execution authority was consumed atomically by `run-contact-replacement-20260926T153527Z-01` with final status `INVALID`. All offline approval-guard, packet-hash, source/install SHA, XML world-name, rendered Xacro, collision/sensor/topic-literal, and collector source-scan gates passed.

The run failed at the GZ raw endpoint preflight: `/s3_d3/contact/raw` was absent from the passive `gz topic -l` listing, so its required `gz::msgs::Contacts` type could not be verified. The temporary one-topic bridge and collector were not started; zero raw Contacts and `/clock` payloads were captured. The measurement-created Gazebo launch group shut down cleanly by SIGINT. No `/cmd_vel` publication, simulator-control action, or hardware operation occurred.

The evidence report is [Contact Producer Evidence Report](../artifacts/simulation/contact_producer_evidence/Contact_Producer_Evidence_Report.md). This completed packet no longer grants execution authority. Its recorded packet hash is retained in the already-consumed guard as the pre-execution authority identity; this post-consumption outcome update must not be used for a new acquisition.

This completed packet is retained as the historical pre-execution authority for S3.3.15. Its one execution authority is consumed and it does not request or authorize another run.

This packet does not approve a collision policy, ContactLatch, reward, termination, Gym/training, command publication, simulator control, UART, or hardware operation.

## 1A. Approval-bound one-run guard

This packet authorizes only approval identity:

```text
S3.3.15_POST_REPAIR_PASSIVE_CONTACT_RUN
```

Before any future execution, the artifact-owned supervisor must validate a separate authorization record for that identity. The record is bound to the SHA-256 of this exact packet, the post-edit world SHA-256, and every immutable literal in Section 2. It has capacity `1` and may be only `authorized_not_consumed` or `consumed`.

The historical `replacement_run_consumed.json` belongs to S3.3.12 and remains immutable evidence. It neither authorizes nor blocks this distinct S3.3.15 approval identity. A missing, malformed, packet-hash-mismatched, literal-mismatched, locked, or already-consumed S3.3.15 record must fail closed. The guard is marked `consumed` atomically after any future S3.3.15 run outcome, including `INVALID`.

This guard section does not execute or consume the approval. At this document revision, S3.3.15 remains `authorized_not_consumed` with exactly one possible execution.

## 1. Historical runs and repair evidence

| Run | Result | Why it stopped | What it does not show |
| --- | --- | --- | --- |
| `run-contact-20260926T143804Z-01` | `INVALID`, before runtime | Its SHA gate identified the pre-edit world revision rather than the world revision after the approved Contact-system edit. | No evidence of a Gazebo, Contact-system, sensor, or bridge failure. |
| `run-contact-replacement-20260926T145616Z-01` | `INVALID`, before runtime | Its world-name parser accepted only a double-quoted XML attribute, while the valid SDF uses a single-quoted `world_demo` attribute. | No evidence of a Gazebo, Contact-system, sensor, or bridge failure. |

The repair is recorded in [Contact Preflight Repair Validation Report](../artifacts/simulation/contact_producer_evidence/repair_validation/Contact_Preflight_Repair_Validation_Report.md). Its offline evidence is:

- standard XML parsing accepts the current single-quoted SDF and an equivalent double-quoted fixture;
- malformed XML, missing/wrong world name, and multiple `<world>` elements are rejected fail-closed;
- future preflight records distinguish `world_name`, `world_sha256`, and `xacro_validation` stages/reasons;
- the current post-edit source-world digest is:

```text
1c50f90d151a12559d426796c5d153c829b8777a5b4e8ef94c007a2023f6e271
```

Repair validation is offline only; it is not runtime evidence and it does not itself authorize a run.

## 2. Immutable scope of the one proposed run

| Field | Required literal |
| --- | --- |
| Gazebo world | `world_demo` |
| World-file SHA-256 | `1c50f90d151a12559d426796c5d153c829b8777a5b4e8ef94c007a2023f6e271` |
| Collision target | `s3_d3_base_contact_collision` |
| ContactSensor | `s3_d3_base_contact_sensor` |
| Raw Gazebo topic | `/s3_d3/contact/raw` |
| Raw ROS topic | `/s3_d3/contact/raw` |
| GZ message type | `gz::msgs::Contacts` |
| ROS message type | `ros_gz_interfaces/msg/Contacts` |
| Temporary bridge | Exactly one **one-topic** raw Contacts bridge |
| Bridge direction | `GZ_TO_ROS` only |
| Bridge argument | `/s3_d3/contact/raw@ros_gz_interfaces/msg/Contacts[gz.msgs.Contacts` |

The raw topic is measurement-only. It is not an official runtime topic contract.

The artifact-owned collector may subscribe only to raw Contacts, `/clock`, and graph metadata. It may not create a publisher, service client, or action client.

## 3. Strict prohibitions

The run must not publish `/cmd_vel` or use teleop, Nav2, PPO, Gymnasium, Stable-Baselines3, pose, reset, pause, step, spawn, delete, or world-control operations. It must not access UART, STM32, Pi, motor, firmware, or hardware.

The collector captures raw observations only. It does not classify collision, construct or consume a ContactLatch, create a reward/termination/Gym transition, or select a collision filter policy.

## 4. Mandatory fail-closed runtime preflight

Every gate must pass before capture. Any failure is `INVALID`, stops the run, and does not authorize a retry.

| Gate | Required evidence |
| --- | --- |
| Source/install world revision | XML world name is exactly `world_demo`; source and installed SHA-256 match the literal in Section 2. |
| Generated robot description | Xacro render contains the named collision and exactly one approved ContactSensor/topic. |
| Contact configuration | Running Gazebo has the approved Contact system and exactly one approved sensor target. |
| GZ raw endpoint | Exact `/s3_d3/contact/raw` endpoint has type `gz::msgs::Contacts`. |
| Bridge | Exactly one temporary raw Contacts mapping with exact ROS type and one-way `GZ_TO_ROS` direction. |
| Graph/type snapshot | Raw contact and `/clock` graph/type metadata are complete. |
| `/cmd_vel` boundary | A pre-capture publisher allowlist is frozen from the actual graph; the collector is not a publisher. |
| Collector source scan | No publisher, service client, or action client is found. |

The allowlist establishes only the collector's non-publication and visible graph change detection; it does not prove global absence of message traffic.

## 5. Capture and result classification

Capture retains every received raw `Contacts` aggregate and all nested entries losslessly, plus steady receive time, `/clock`, graph snapshots, and bridge provenance. Aggregate header/timestamp, IDs/names/types, contact positions/normals/depths/wrenches, cardinality, duplicate payloads, and simultaneous entries are retained only when populated by the raw message.

| Classification | Criteria | Interpretation limit |
| --- | --- | --- |
| `VALID_WITH_RAW_CONTACT` | All gates and shutdown pass; at least one raw Contacts payload is received. | Raw producer observation only; not collision policy or transition evidence. |
| `VALID_NO_RAW_CONTACT` | All gates and shutdown pass; no raw Contacts payload is received. | Does not prove delivery failure or absence of contact; the base sensor may not contact an object while stationary. |
| `INVALID` | Any preflight, boundary, capture, or shutdown gate fails. | No contact payload interpretation. |

No result automatically approves collision policy, ContactLatch, reward, termination, Gym/training, or any runtime deployment behavior.

## 6. Shutdown and one-run rule

Only process groups created by this measurement may receive SIGINT. SIGTERM, SIGKILL, `.kill()`, `kill -9`, and any force-kill fallback are forbidden.

```text
SIGINT → bounded graceful wait
still alive → SHUTDOWN_INCOMPLETE
             → preserve artifact and blocker
             → prohibit another run
             → require a separate user/operator decision
```

This packet approves at most one run. A failure consumes it; a later attempt requires another explicit approval packet.

## Historical approval scope — consumed

The pre-execution scope above was consumed by S3.3.17 and remains only for provenance. A further run requires a separate new approval packet after analysis of this invalid endpoint gate.

## Retained non-claims

This packet does not establish Gazebo Contact-system loading, sensor delivery, contact timestamps/identity, scoped-name stability, duplicate behavior, collision classification, ContactLatch, reset semantics, reward, termination, command behavior, Gym/SB3/training, or hardware readiness.
