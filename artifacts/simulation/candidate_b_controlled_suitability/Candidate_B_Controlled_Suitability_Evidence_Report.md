# Candidate B Controlled Suitability Evidence Report

## Run status

- Run: `run-candidate-b-replacement-20260925T143309Z-02`
- Status: `VALID`
- Sent probes: `B0_START_P0 → B1_GOAL_P2 → B2_RECT_LL → B3_RECT_LR → B4_RECT_UR → B5_RECT_UL`
- Entity: `ROBOT_URDF_final`
- Pose service: `/world/world_demo/set_pose` (`ros_gz_interfaces/srv/SetEntityPose`)
- Timestamp provenance complete: `True`
- `ros_request_dispatched_steady_ns` is a **local call-submission timestamp**:
  it records when the client obtained the future from `call_async`; it is not a
  Gazebo receipt or pose-application timestamp.

## Scan sanity evidence

For each of the six committed request records, the collector retained a scan
received strictly after that probe's `post_response_barrier_steady_ns`. Every
such scan had the expected type, present frame/timestamp metadata, well-formed
ranges under the existing scan contract, and `scan_sanity.valid=true`. No older
scan was substituted. This is only predeclared scan-suitability sanity evidence;
it is not an obstacle map, clearance threshold, collision inference, or
settled-state proof.

## Post-response provenance classification

| Probe | Response success | PRE_RESPONSE_CANDIDATE | POST_RESPONSE_CANDIDATE | OBSERVED_POSE_CHANGE | NO_POST_RESPONSE_GT | First post-response candidate |
| --- | --- | ---: | ---: | ---: | --- | --- |
| B0_START_P0 | True | 1 | 490 | 151 | False | stamp=2020000000 steady=87653034095477 pose=-4.000000000/-3.000000000/0.000000000/-0.00000000000 |
| B1_GOAL_P2 | True | 0 | 490 | 135 | False | stamp=11820000000 steady=87662934047943 pose=-2.000000000/-3.000000000/0.000000000/-1.57079632679 |
| B2_RECT_LL | True | 1 | 493 | 151 | False | stamp=21640000000 steady=87672952468696 pose=-4.500000000/-3.500000000/0.000000000/-0.00000000000 |
| B3_RECT_LR | True | 1 | 491 | 151 | False | stamp=31520000000 steady=87682956523852 pose=-1.500000000/-3.500000000/0.000000000/-0.00000000000 |
| B4_RECT_UR | True | 1 | 490 | 152 | False | stamp=41360000000 steady=87692970144122 pose=-1.500000000/-2.500000000/0.000000000/-0.00000000000 |
| B5_RECT_UL | True | 1 | 489 | 151 | False | stamp=51180000000 steady=87702978275481 pose=-4.500000000/-2.500000000/0.000000000/0.00000000000 |

## Provenance meaning and limitations

- `PRE_RESPONSE_CANDIDATE` is received after local dispatch but not strictly after the post-response barrier.
- `POST_RESPONSE_CANDIDATE` is received strictly after the local post-response barrier; it is the only candidate class used in this report's request–GT relation.
- `OBSERVED_POSE_CHANGE` is a descriptive trace change, not a settle threshold or receipt.
- `NO_POST_RESPONSE_GT` means no retained GT row passed the local post-response test; it must not be replaced with an older or pre-response sample.
- The request z remains `0.1` and observed GT z may remain `0.0`. This is reported only as an observation, not a mapping adjustment.
- No conclusion is made about Gazebo pose application receipt, atomic reset, scenario frame, TF authority, collision, task oracle, Gym, reward, termination, runtime deployment, firmware, or hardware.
