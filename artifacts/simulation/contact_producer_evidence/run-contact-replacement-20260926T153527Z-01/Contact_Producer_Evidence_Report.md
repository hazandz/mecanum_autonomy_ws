# S3 D3 Contact Producer Evidence Report

Run: `run-contact-replacement-20260926T153527Z-01`

Classification: **INVALID**

## Final state

The S3.3.15 approval-bound guard was atomically consumed with `final_status: INVALID`, run ID `run-contact-replacement-20260926T153527Z-01`, and the recorded completion timestamp. No further execution may acquire this approval identity.

## Preflight evidence

| Gate | Result |
| --- | --- |
| Approval guard | Consumed after this run as `INVALID`. |
| World identity / post-edit SHA | PASS: `world_demo`, source and installed SHA match `1c50f90d151a12559d426796c5d153c829b8777a5b4e8ef94c007a2023f6e271`. |
| XML world-name validation | PASS: exactly one `world_demo`. |
| Xacro / named collision / sensor / topic | PASS: rendered collision count `2`, sensor count `1`, topic count `1`; source literal counts are each `1`. |
| Collector/analyzer source scan | PASS: no publisher, service client, or action client pattern. |
| Runtime GZ raw topic/type | **FAIL**: the passive `gz topic -l` preflight listing did not contain `/s3_d3/contact/raw`; therefore `gz.msgs.Contacts` could not be verified. |

The failure occurred before the temporary one-topic bridge and collector were started. No ROS raw Contacts graph/type snapshot exists, because the raw GZ endpoint gate did not pass.

## Capture and boundary observations

| Item | Observation |
| --- | --- |
| Raw `Contacts` payloads | `0`; no capture began. |
| `/clock` messages | `0`; collector did not start. |
| Aggregate header/timestamp | Not observed. |
| Entity/scoped names | Not observed. |
| Cardinality, duplicate, simultaneous-contact behavior | Not observed. |
| Temporary bridge | Not started. |
| `/cmd_vel` publication by measurement | `0`. |
| Simulator-control service/action by measurement | `0`. |
| Hardware operation | `0`. |
| Shutdown | Complete; measurement-created Gazebo launch process group received SIGINT and exited cleanly. |

## Raw GZ graph evidence

The retained [GZ topic preflight listing](logs/gz_topic_info.log) includes `/clock`, `/cmd_vel`, `/ground_truth/odom`, `/odom`, `/scan`, and other existing endpoints, but not `/s3_d3/contact/raw`. This is an `INVALID` runtime endpoint gate, not evidence of collision absence, collision policy, ContactLatch behavior, or contact-delivery semantics.

## Records

- [manifest](manifest.json)
- [static robot validation](static_robot_validation.json)
- [tool source scan](tool_source_scan.json)
- [run result](run_result.json)
- [shutdown record](shutdown_record.json)
- [GZ topic listing](logs/gz_topic_info.log)

## Retained non-claims

This run does not establish Gazebo Contact-system loading behavior, ContactSensor output, bridge delivery, timestamp behavior, collision identity, collision policy/filtering, ContactLatch, reset semantics, reward, termination, Gym/SB3/training, command behavior, or hardware readiness. The absence of this configured raw endpoint in this run does not justify any inference about collision occurrence or absence.
