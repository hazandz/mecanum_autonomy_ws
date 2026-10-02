# S3 Candidate B Replacement Evidence Review

**Status: DRAFT — EVIDENCE REVIEW ONLY, NO SCENARIO APPROVAL**

## Scope and evidence reviewed

This is an offline review of the valid replacement run `run-candidate-b-replacement-20260925T143309Z-02`. It does not approve a scenario, a coordinate transform, reset behavior, collision handling, or any runtime component.

Reviewed evidence:

- [Replacement run directory](../artifacts/simulation/candidate_b_controlled_suitability/run-candidate-b-replacement-20260925T143309Z-02/)
- [Aggregate evidence report](../artifacts/simulation/candidate_b_controlled_suitability/Candidate_B_Controlled_Suitability_Evidence_Report.md)
- [Replacement approval packet](S3_Candidate_B_Replacement_Run_Approval_Packet_DRAFT.md)
- [Original Candidate B packet](S3_Candidate_B_Controlled_Suitability_Run_Approval_Packet_DRAFT.md)
- [Immutable Candidate B manifest](../artifacts/simulation/candidate_b_controlled_suitability/measurement_manifest.json)

## Readiness conclusion

**`READY_FOR_SCENARIO_DECISION_PACKET_ONLY`**

The replacement run supplies controlled operational and receive-order evidence. It does not supply the missing decisions or runtime evidence required to approve a scenario artifact.

## Evidence classification

### Operationally established

- Preflight passed for `world_demo` and the immutable world-file SHA-256 recorded by the manifest.
- The temporary bridge exposed the exact approved ROS service `/world/world_demo/set_pose` with type `ros_gz_interfaces/srv/SetEntityPose`.
- The frozen `/cmd_vel` publisher allowlist was captured from the live graph; the collector recorded no publisher and no control client other than the exact `SetEntityPose` client.
- All six immutable requests were sent exactly once, in order B0 through B5, and every recorded service response has `success=true`.
- Every sent probe has `pre_call_steady_ns`, `ros_request_dispatched_steady_ns`, `ros_response_received_steady_ns`, and `post_response_barrier_steady_ns` recorded on the local steady clock.
- Each probe has Ground Truth odometry received strictly after its post-response barrier and a newly observed, valid scan after that barrier.
- The artifact records temporary bridge and Gazebo shutdown by SIGINT process group as complete, with no `SHUTDOWN_INCOMPLETE` blocker.

### Observed only

- Each first `POST_RESPONSE_CANDIDATE` Ground Truth sample below contains observed x/y/yaw values after the local post-response receive barrier.
- The recorded post-response scans pass the predefined message/frame/timestamp/range sanity checks.
- `OBSERVED_POSE_CHANGE` is a trace description only; it is not a settled-state finding and does not approve a pose match.

### Not established

- A Gazebo pose-application receipt, atomic reset, reset receipt, or settled state.
- A new coordinate transform, SDF/model-local to GT conversion, or TF authority.
- Free space, clearance, collision-free motion, valid area, forbidden zones, or an obstacle map.
- A scenario artifact or an approved scenario start, goal, radius, boundary, or forbidden-zone definition.
- ContactLatch/collision policy, TrainingTaskOracle runtime, reward/termination, Gymnasium/SB3/Nav2 integration, or hardware readiness.

## Per-probe evidence

| Probe | Immutable request literal `(x, y, z, yaw)` | Service response | First `POST_RESPONSE_CANDIDATE` GT `(x, y, z, yaw)` | Post-response scan sanity | Evidence classification |
| --- | --- | --- | --- | --- | --- |
| B0_START_P0 | `(-4.0, -3.0, 0.1, 0.0)` | `success=true` | `(-4.0, -3.0, 0.0, -2.212259731545569e-22)` | Valid; new scan; frame `ROBOT_URDF_final/RPLiDAR_A1M8_1/rplidar` | Operational + observed candidate only |
| B1_GOAL_P2 | `(-2.0, -3.0, 0.1, -1.57079632679)` | `success=true` | `(-2.0, -3.000000000000001, 0.0, -1.57079632679)` | Valid; new scan; frame `ROBOT_URDF_final/RPLiDAR_A1M8_1/rplidar` | Operational + observed candidate only |
| B2_RECT_LL | `(-4.5, -3.5, 0.1, 0.0)` | `success=true` | `(-4.5, -3.5, 0.0, -2.9331328242039358e-22)` | Valid; new scan; frame `ROBOT_URDF_final/RPLiDAR_A1M8_1/rplidar` | Operational + observed candidate only |
| B3_RECT_LR | `(-1.5, -3.5, 0.1, 0.0)` | `success=true` | `(-1.5, -3.5, 0.0, -2.227914974498509e-22)` | Valid; new scan; frame `ROBOT_URDF_final/RPLiDAR_A1M8_1/rplidar` | Operational + observed candidate only |
| B4_RECT_UR | `(-1.5, -2.5, 0.1, 0.0)` | `success=true` | `(-1.5, -2.5, 0.0, -1.251312338967097e-22)` | Valid; new scan; frame `ROBOT_URDF_final/RPLiDAR_A1M8_1/rplidar` | Operational + observed candidate only |
| B5_RECT_UL | `(-4.5, -2.5, 0.1, 0.0)` | `success=true` | `(-4.5, -2.5, 0.0, 5.83717996978665e-22)` | Valid; new scan; frame `ROBOT_URDF_final/RPLiDAR_A1M8_1/rplidar` | Operational + observed candidate only |

No residual tolerance is introduced here. The table is not a pose-match approval. In particular, request `z=0.1` and observed GT `z=0.0` remain an unresolved limitation outside the 2D receive-order observation.

## Provenance limits

- `ros_request_dispatched_steady_ns` is a local call-submission timestamp, not a Gazebo receipt.
- A `POST_RESPONSE_CANDIDATE` only establishes that the collector received that GT sample locally after `post_response_barrier_steady_ns`.
- `success=true` is not a Gazebo pose-application receipt.
- Scan sanity is not an obstacle map, clearance metric, or collision evidence.
- Collision is out of scope and must not be inferred from scan, GT odometry, a pose request, or a service response.

## Decisions and evidence still required for a scenario v1

| Missing item | Why this evidence review cannot supply it | Required next authority or evidence |
| --- | --- | --- |
| Start, goal, goal radius, and valid-area literals | The six probes are controlled observations, not adopted task values. | User scenario decision with an immutable scenario artifact. |
| Scan-clearance metric and threshold | Scan sanity validates only structural usability, not clearance. | Separate metric, threshold, and validation decision/evidence. |
| Reset receipt and settle policy | Post-response receive order is not an application or reset receipt. | Reset/lifecycle contract and runtime evidence. |
| ContactLatch and collision policy | No approved contact source was observed in this run. | Contact source, filter/latch contract, and runtime evidence. |
| Lifecycle scenario hash/change policy | The run manifest is not a per-episode scenario artifact contract. | Artifact identity and episode-generation change decision. |

## Preserved non-claims

This review does not approve a scenario artifact, TrainingTaskOracle runtime, policy observation access to Ground Truth, reward or termination behavior, Gymnasium/SB3/Nav2 operation, TF authority, collision behavior, reset behavior, deployed robot behavior, or hardware operation.

## Handoff

The next permissible design step is a scenario decision packet that asks the user to select concrete scenario-v1 values and the remaining policy contracts. It must not treat this evidence as a free-space, valid-area, collision, or reset approval.
