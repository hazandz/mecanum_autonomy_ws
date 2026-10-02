# S3 Candidate B Controlled Suitability Run Approval Packet

**Status: COMPLETED_INVALID_RUN — EVIDENCE_RETAINED**

## 1. Completed-run outcome

The one user-approved Candidate B controlled suitability run completed as
`INVALID` in `run-candidate-b-20260925T140736Z-01`. The collector failed at
bootstrap with `NameError: name 'sys' is not defined` before graph preflight,
before a service future, and before any pose request. Therefore `0 / 6` probes
were sent; no retry is authorized by this completed approval.

The expected temporary one-service bridge was started. Its service creation was
logged, but no collector-side ROS service validation, frozen `/cmd_vel`
allowlist, GT/scan record, response, or post-response provenance exists for this
invalid run. The evidence is retained at
`artifacts/simulation/candidate_b_controlled_suitability/run-candidate-b-20260925T140736Z-01/`.

This status records the actual operational outcome only. It does not elevate
evidence to a reset receipt, collision proof, valid-area proof, scenario
artifact, oracle runtime, reward/termination, Gym/SB3, or hardware approval.

## 2. Purpose and strict scope

This packet proposes exactly one future, Gazebo-simulation-only controlled
suitability measurement for the user-selected *candidate* `P0_TO_P2`. It is
limited to observing whether declared pose requests produce post-response GT
and scan evidence at the requested candidate locations. It is not a scenario
artifact, reset contract, collision test, policy run, or runtime approval.

Every literal and every pose probe in this document remains pending explicit
user approval. No request is authorized by this draft.

`GT_ODOM_2D` remains a hidden core-design reference only. The observed GT
metadata string `world` and Gazebo world identity `world_demo` are not asserted
to be equal, and no conversion is proposed in this packet.

## 3. Proposed candidate literals

| Item | Proposed value | Approval state |
| --- | --- | --- |
| Temporary scenario candidate | `P0_TO_P2` | `PENDING_USER_APPROVAL` |
| Entity | `ROBOT_URDF_final` | `PENDING_USER_APPROVAL` |
| Gazebo world identity | `world_demo` | `PENDING_USER_APPROVAL` |
| World SDF SHA-256 | `a5e9c9b1e9b8ad11e0399855f06de687f04c702258b8b74ce563523d78ed55fe` | `PENDING_USER_APPROVAL` |
| Start hypothesis | `(-4.0 m, -3.0 m, yaw 0.0 rad)` / P0 | `PENDING_USER_APPROVAL` |
| Goal hypothesis | `(-2.0 m, -3.0 m)` / P2 | `PENDING_USER_APPROVAL` |
| Goal radius hypothesis | `0.25 m` | `PENDING_USER_APPROVAL` |
| Valid-area hypothesis | Axis-aligned rectangle | `PENDING_USER_APPROVAL` |
| Rectangle x extent | `[-4.5 m, -1.5 m]` | `PENDING_USER_APPROVAL` |
| Rectangle y extent | `[-3.5 m, -2.5 m]` | `PENDING_USER_APPROVAL` |
| Boundary rule | Boundary is invalid | `PENDING_USER_APPROVAL` |
| Forbidden zones | `none for v1` hypothesis | `PENDING_USER_APPROVAL` |
| Randomization | Excluded from v1 | `PENDING_USER_APPROVAL` |

These are suitability hypotheses only. In particular, the rectangle is not an
approved valid area and the goal radius is not an approved goal-reached rule.

## 4. Proposed operational boundary

The only proposed bridge is the temporary, artifact-owned, one-service bridge:

```text
/world/world_demo/set_pose@ros_gz_interfaces/srv/SetEntityPose@gz.msgs.Pose@gz.msgs.Boolean
```

The proposed collector may observe only:

```text
/ground_truth/odom
/scan
/clock
graph metadata
```

It must not use `/cmd_vel`, teleop, Nav2, PPO, Gymnasium, SB3, world control,
spawn/delete, pause/reset/step world, firmware, or hardware. It must not bridge
any topic or service other than the literal pose service above.

Before capture, the collector must snapshot graph metadata, including every
`/cmd_vel` publisher and the ROS pose-service name and type. It must freeze the
`/cmd_vel` publisher allowlist from that observed pre-capture snapshot; it must
not construct an allowlist from the launch file or expand it during capture.
The collector must create no publishers, including no `/cmd_vel` publisher, and
no service or action client other than the exact `SetEntityPose` client. A
missing graph snapshot, or a `/cmd_vel` publisher outside the frozen allowlist,
is fail-closed at the time it is detected. The allowlist can establish only that
the collector did not create a control path; it cannot prove that no other
process publishes a command message.

Preflight must confirm exactly the following ROS service identity:

```text
name: /world/world_demo/set_pose
type: ros_gz_interfaces/srv/SetEntityPose
```

Each request response is valid only after its future completes and reports
`success=true`. No response condition authorizes a retry, an additional request,
or a change to any probe's `z` or yaw literal.

## 5. Exact proposed pose-probe manifest

All rows below are labeled **`CANDIDATE_ONLY — NOT_APPROVED — NO RETRY`**. They
are the complete proposed probe list: no probe may be added, retried, reordered,
or altered during a future run. Rectangle-corner requests are reference probes;
because the proposed boundary is invalid, they are not claims of valid start or
goal poses.

| Order | Probe ID | x (m) | y (m) | z (m) | yaw (rad) | Role | Status |
| ---: | --- | ---: | ---: | ---: | ---: | --- | --- |
| 1 | `B0_START_P0` | -4.0 | -3.0 | 0.1 | 0.0 | Start hypothesis P0 | `CANDIDATE_ONLY — NOT_APPROVED — NO RETRY` |
| 2 | `B1_GOAL_P2` | -2.0 | -3.0 | 0.1 | -1.57079632679 | Goal hypothesis P2 | `CANDIDATE_ONLY — NOT_APPROVED — NO RETRY` |
| 3 | `B2_RECT_LL` | -4.5 | -3.5 | 0.1 | 0.0 | Lower-left rectangle reference | `CANDIDATE_ONLY — NOT_APPROVED — NO RETRY` |
| 4 | `B3_RECT_LR` | -1.5 | -3.5 | 0.1 | 0.0 | Lower-right rectangle reference | `CANDIDATE_ONLY — NOT_APPROVED — NO RETRY` |
| 5 | `B4_RECT_UR` | -1.5 | -2.5 | 0.1 | 0.0 | Upper-right rectangle reference | `CANDIDATE_ONLY — NOT_APPROVED — NO RETRY` |
| 6 | `B5_RECT_UL` | -4.5 | -2.5 | 0.1 | 0.0 | Upper-left rectangle reference | `CANDIDATE_ONLY — NOT_APPROVED — NO RETRY` |

The `z=0.1 m` request value preserves the approved controlled-measurement
convention. Earlier evidence observed GT `z=0.0 m` for requests at `z=0.1 m`;
this packet neither changes `z` nor proposes an offset or pose-origin mapping.

## 6. Required provenance and limited interpretation

For every request, the future artifact must retain these lossless fields from
one steady-clock domain:

```text
pre_call_steady_ns
ros_request_dispatched_steady_ns
ros_response_received_steady_ns
post_response_barrier_steady_ns
```

A GT record may be labeled `POST_RESPONSE_CANDIDATE` only when:

```text
gt.received_steady_ns > post_response_barrier_steady_ns
```

This establishes only local receive-order provenance. Scan and GT records after
that barrier can be used for limited candidate-suitability review. They are not
Gazebo-application receipts, reset receipts, settled-state evidence,
collision-free proof, obstacle maps, TF-authority evidence, or final proof of a
valid area.

Scan is sanity evidence only, not an obstacle map, collision signal, or
clearance proof. It is eligible only if the expected ROS message type is present,
frame and timestamp metadata are present, ranges are not malformed under the
existing scan contract, and graph/source evidence is complete. No numeric
clearance threshold, settle time, freshness timeout, or collision threshold is
introduced here. A missing or invalid scan makes the run
`INVALID_FOR_SCAN_SUITABILITY`; it must not be replaced with an older scan.

Collision is neither observable nor evaluated in this run: the approved streams
provide no ContactLatch, contact topic, or other collision source. Collision
must not be inferred from GT, scan, entity pose, or a service response.
ContactLatch/collision provenance remains a separate blocker for a later phase.

## 7. Fail-closed stop conditions

| Condition | Required response |
| --- | --- |
| World name or world-file hash differs from the approved literal | Send zero probes; mark run invalid; clean shutdown. |
| ROS pose service name differs from `/world/world_demo/set_pose`, or type differs from `ros_gz_interfaces/srv/SetEntityPose` | Send zero probes; mark run invalid; clean shutdown. |
| Service unavailable, response future missing or incomplete, or `success != true` | Stop immediately; do not send remaining probes; no retry. |
| Any required provenance timestamp is absent | Stop immediately; mark run invalid for suitability evidence; no retry. |
| No GT record after the post-response barrier | Stop immediately; mark run invalid for suitability evidence; no retry. |
| `/scan` lacks the expected type, frame/timestamp metadata, well-formed ranges, or complete graph/source evidence | Stop immediately; mark `INVALID_FOR_SCAN_SUITABILITY`; no retry and no old-scan substitution. |
| Required graph metadata is missing | Send zero probes when detected preflight; otherwise stop immediately and mark invalid. |
| A `/cmd_vel` publisher outside the frozen pre-capture allowlist appears | Send zero probes when detected preflight; otherwise stop immediately and mark invalid. |
| Collector creates any publisher, including `/cmd_vel`, or a service/action client other than exact `SetEntityPose` | Stop immediately; mark run invalid; do not send remaining probes. |
| Collision evidence | Not observable and not evaluated in this run; do not infer it from the permitted streams. |

Warm-up and post-response capture periods, if later approved, are administrative
guards only. They are not settle, freshness, collision, or reset policies.

## 8. User approval checklist

Before a run can be implemented or executed, the user must explicitly approve:

- [ ] all six pose literals and their exact order `B0_START_P0` through `B5_RECT_UL`;
- [ ] the `0.25 m` goal-radius hypothesis;
- [ ] the rectangle extents `x in [-4.5, -1.5]`, `y in [-3.5, -2.5]`;
- [ ] the rule that rectangle boundaries are invalid;
- [ ] the `none for v1` forbidden-zone hypothesis;
- [ ] the no-retry rule and the full fail-closed stop-condition table;
- [ ] use of only the temporary one-service bridge literal above;
- [ ] the frozen, pre-capture `/cmd_vel` publisher allowlist and graph snapshot
  rule, including its limit that it cannot prove other processes send commands;
- [ ] exact service validation and per-request response requirement:
  `/world/world_demo/set_pose`, `ros_gz_interfaces/srv/SetEntityPose`, and
  completed future with `success=true`;
- [ ] the minimal scan sanity criteria (type, frame/timestamp metadata,
  non-malformed ranges, and complete graph/source evidence), without a numeric
  clearance, freshness, settle, or collision threshold;
- [ ] collision is out of scope and unobservable for this run; no collision or
  ContactLatch conclusion may be inferred from GT, scan, pose, or response;
- [ ] that this is a Gazebo-only controlled suitability measurement, not a
  scenario-artifact, oracle-runtime, reset, collision, reward, termination,
  Gym/SB3, or hardware approval.

## 9. Evidence lineage and non-claims

Candidate B derives only from the read-only Candidate B review and prior
P0/P1/P2 request-to-GT correspondence evidence. The latter established
post-response candidates for those three probes; it did not establish free
space, a collision-free path, a coordinate conversion, or scenario suitability.

This packet does not create a scenario artifact or hash, approve a
`TrainingTaskOracle` runtime source, approve reset semantics, collision or
ContactLatch behavior, STUCK/D6, reward, termination, Gym/SB3, TF authority, or
any hardware behavior. It also does not equate `world_demo` with `world`.

## 10. Source references

- [Candidate review](S3_First_Scenario_Candidate_Review_DRAFT.md)
- [First scenario evidence plan](S3_First_Simulation_Scenario_Candidate_And_Evidence_Plan_DRAFT.md)
- [Scenario artifact contract](S3_Simulation_Scenario_Artifact_Contract_DRAFT.md)
- [GT 2D decision packet](S3_GT_2D_Coordinate_Relation_Decision_Packet_DRAFT.md)
- [Replacement-run packet](S3_Post_Response_Provenance_Replacement_Run_Packet_DRAFT.md)
- [Controlled-measurement evidence report](../artifacts/simulation/controlled_coordinate_reset_measurement/Controlled_Coordinate_Reset_Measurement_Evidence_Report.md)

