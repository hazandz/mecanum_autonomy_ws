# Controlled Coordinate Reset Measurement Evidence Report

## Run status

- Run: `run-replacement-post-response-20260924T191000Z-03`
- Status: `VALID`
- Sent probes: `P0 → P1 → P2`
- Entity: `ROBOT_URDF_final`
- Pose service: `/world/world_demo/set_pose` (`ros_gz_interfaces/srv/SetEntityPose`)
- Timestamp provenance complete: `True`

## Operational boundary and shutdown

- The bridge was temporary, artifact-owned, and had exactly one approved `SetEntityPose` service argument.
- Collector scope audit is `PASS`: no publisher or action client; only the literal SetEntityPose client/call and fixed P0 → P1 → P2.
- No `/cmd_vel` publisher was created by the collector; the pre-existing `/ros_gz_bridge` allowlist remained frozen by collector assertions.
- The supervisor finalizer did not run; recorded SIGINT recovery targeted only measurement-created bridge/Gazebo descendants and later process inspection found no matching process.

## Post-response provenance classification

| Probe | Response success | PRE_RESPONSE_CANDIDATE | POST_RESPONSE_CANDIDATE | OBSERVED_POSE_CHANGE | NO_POST_RESPONSE_GT | First post-response candidate |
| --- | --- | ---: | ---: | ---: | --- | --- |
| P0 | True | 1 | 449 | 151 | False | stamp=1540000000 steady=3235596689389 pose=-4.000000000/-3.000000000/0.000000000/-0.00000000000 |
| P1 | True | 1 | 457 | 152 | False | stamp=10540000000 steady=3245408937419 pose=-4.000000000/-0.000000000/0.000000000/1.57079632679 |
| P2 | True | 1 | 462 | 135 | False | stamp=19700000000 steady=3255418797267 pose=-2.000000000/-3.000000000/0.000000000/-1.57079632679 |

## Provenance meaning and limitations

- `PRE_RESPONSE_CANDIDATE` is received after local dispatch but not strictly after the post-response barrier.
- `POST_RESPONSE_CANDIDATE` is received strictly after the local post-response barrier; it is the only candidate class used in this report's request–GT relation.
- `OBSERVED_POSE_CHANGE` is a descriptive trace change, not a settle threshold or receipt.
- `NO_POST_RESPONSE_GT` means no retained GT row passed the local post-response test; it must not be replaced with an older or pre-response sample.
- The request z remains `0.1` and observed GT z may remain `0.0`. This is reported only as an observation, not a mapping adjustment.
- No conclusion is made about Gazebo pose application receipt, atomic reset, scenario frame, TF authority, collision, task oracle, Gym, reward, termination, runtime deployment, firmware, or hardware.
