# S3 Candidate B Replacement Run Approval Packet

**Status: DRAFT — PENDING_USER_APPROVAL_FOR_ONE_REPLACEMENT_RUN**

## 1. Request scope and prior invalid run

This packet requests approval for exactly **one** Candidate B replacement run after
offline tool repair. It is not an automatic retry. It must create a new run
directory and must not overwrite or alter the completed invalid evidence:

`run-candidate-b-20260925T140736Z-01`

That old run sent `0 / 6` requests because the collector lacked `import sys`.
Its raw logs, metadata, report, and `COMPLETED_INVALID_RUN` status remain
immutable.

Offline repair validation passed `py_compile`, collector `--help`, and
`--offline-bootstrap-self-test`. This only establishes offline readiness; it
does not authorize Gazebo, ROS, bridge, service, command, or hardware runtime.

## 2. Immutable replacement inputs

The following values are copied directly from the completed Candidate B approval
packet and its immutable measurement manifest; no coordinate was re-derived.

| Field | Literal |
| --- | --- |
| Entity | `ROBOT_URDF_final` |
| Gazebo world name | `world_demo` |
| World file SHA-256 | `a5e9c9b1e9b8ad11e0399855f06de687f04c702258b8b74ce563523d78ed55fe` |
| Exact bridge argument | `/world/world_demo/set_pose@ros_gz_interfaces/srv/SetEntityPose@gz.msgs.Pose@gz.msgs.Boolean` |
| ROS service name | `/world/world_demo/set_pose` |
| ROS service type | `ros_gz_interfaces/srv/SetEntityPose` |
| Gazebo request / response types | `gz.msgs.Pose` / `gz.msgs.Boolean` |
| Retry policy | No retry, no extra request, no altered literal. |

## 3. Exact one-run pose manifest

Every row is immutable for this proposed run. The collector may send each row
once, in this order only, after all preflight gates pass.

| Order | Probe ID | x (m) | y (m) | z (m) | yaw (rad) |
| ---: | --- | ---: | ---: | ---: | ---: |
| 1 | `B0_START_P0` | -4.0 | -3.0 | 0.1 | 0.0 |
| 2 | `B1_GOAL_P2` | -2.0 | -3.0 | 0.1 | -1.57079632679 |
| 3 | `B2_RECT_LL` | -4.5 | -3.5 | 0.1 | 0.0 |
| 4 | `B3_RECT_LR` | -1.5 | -3.5 | 0.1 | 0.0 |
| 5 | `B4_RECT_UR` | -1.5 | -2.5 | 0.1 | 0.0 |
| 6 | `B5_RECT_UL` | -4.5 | -2.5 | 0.1 | 0.0 |

No change to `z` or yaw is permitted. No seventh probe, retry, or alternative
pose request is permitted.

## 4. Runtime boundary

The replacement is Gazebo-simulation-only. It may target only
`ROBOT_URDF_final`, create only the one temporary artifact-owned bridge in
section 2, and observe only:

```text
/ground_truth/odom
/scan
/clock
graph metadata
```

It must not publish `/cmd_vel`, use teleop, Nav2, PPO, Gymnasium, SB3,
`ControlWorld`, any reset service, pause/step world, spawn/delete, UART,
STM32, Pi, firmware, motor, or hardware operation. No control publisher or
action client is permitted; the only service client is the exact
`SetEntityPose` client above.

## 5. Required preflight and fail-closed behavior

Before the first probe, the run must verify all of the following:

| Gate | Required evidence | Failure response |
| --- | --- | --- |
| World identity | Local world file hash equals the literal in section 2; launched Gazebo world is `world_demo`. | Send 0 probes; retain an invalid artifact; SIGINT shutdown only. |
| Exact service | `/world/world_demo/set_pose` exists with exactly `ros_gz_interfaces/srv/SetEntityPose`. | Send 0 probes; invalid. |
| Frozen command graph | Snapshot every `/cmd_vel` publisher from the live graph before capture and freeze that list. | Missing snapshot or later publisher outside the list: invalid; no remaining probes. |
| Collector boundary | Static tooling evidence shows no publisher, no action client, and no control client other than exact `SetEntityPose`. | Send 0 probes; invalid. |
| Repair evidence | Repair-validation report, help capture, exit-code record, and PASS self-test artifact all exist. | Send 0 probes; invalid. |
| Shutdown blocker | Artifact root contains no `SHUTDOWN_INCOMPLETE` blocker. | Send 0 probes; block run pending user/operator decision. |

The frozen allowlist can show only that the collector did not create a command
path. It cannot prove that another process never publishes a command message.

## 6. Per-probe provenance and scan sanity

For every sent request, record these values losslessly in a single steady-clock
domain:

```text
pre_call_steady_ns
ros_request_dispatched_steady_ns
ros_response_received_steady_ns
post_response_barrier_steady_ns
```

A response is acceptable only if the future completes and `success=true`. A GT
record may receive the label `POST_RESPONSE_CANDIDATE` only if:

```text
gt.received_steady_ns > post_response_barrier_steady_ns
```

This is receive-order evidence only, not a Gazebo pose-application receipt.

Scan is sanity evidence only. For each probe, a newly received scan after its
post-response barrier must have the expected ROS type, frame and timestamp
metadata, non-malformed ranges under the existing scan contract, and complete
graph/source evidence. Missing or invalid scan makes the run
`INVALID_FOR_SCAN_SUITABILITY`; an older scan must not be substituted. This
packet adds no clearance threshold, settle time, freshness timeout, or collision
threshold.

## 7. Collision and shutdown boundaries

Collision is outside this run. There is no ContactLatch or approved contact
source; collision must not be inferred from GT odometry, scan, entity pose,
response, or `success=true`.

Shutdown applies only to measurement-created process groups:

```text
SIGINT
→ bounded graceful wait
→ SHUTDOWN_INCOMPLETE if still alive
→ write blocker and retain artifact
→ block any further replacement run
→ user/operator decision required
```

No SIGTERM, SIGKILL, `.kill()`, `kill -9`, or other force-kill fallback is
permitted.

## 8. Permitted success claims only

A completed valid run may claim only:

- the six requests were sent once in the exact listed order and each response
  had `success=true`;
- the graph/control boundary evidence passed;
- post-response local receive-order evidence was retained;
- scan suitability passed the predeclared sanity criteria.

It may not claim reset atomicity, Gazebo pose-application receipt, settled
state, collision-free motion, approved valid area, scenario artifact,
TrainingTaskOracle runtime, reward/termination, Gym/SB3, Nav2, TF authority, or
hardware readiness.

## 9. User approval required

- [ ] Approve exactly one new replacement run; it is not automatic and does not
  alter the old invalid artifact.
- [ ] Approve the complete six-row literal manifest and fixed order in section 3.
- [ ] Approve the single temporary bridge literal and exact ROS service/type.
- [ ] Approve the preflight, frozen `/cmd_vel` allowlist, fail-closed, and
  no-retry rules.
- [ ] Approve the four timestamp provenance fields and GT
  `POST_RESPONSE_CANDIDATE` rule.
- [ ] Approve the scan sanity boundary and `INVALID_FOR_SCAN_SUITABILITY`
  outcome without old-scan fallback.
- [ ] Acknowledge collision is out of scope and unobservable.
- [ ] Approve SIGINT-only process-group shutdown and the
  `SHUTDOWN_INCOMPLETE` blocker policy.
- [ ] Acknowledge that no prohibited runtime, reset, collision, scenario,
  oracle, reward, Gym/SB3, Nav2, firmware, or hardware approval follows.

## 10. References

- [Completed Candidate B packet](S3_Candidate_B_Controlled_Suitability_Run_Approval_Packet_DRAFT.md)
- [Candidate B immutable manifest](../artifacts/simulation/candidate_b_controlled_suitability/measurement_manifest.json)
- [Completed invalid-run report](../artifacts/simulation/candidate_b_controlled_suitability/Candidate_B_Controlled_Suitability_Evidence_Report.md)
- [Offline repair validation](../artifacts/simulation/candidate_b_controlled_suitability/repair_validation/Tool_Repair_Validation_Report.md)

