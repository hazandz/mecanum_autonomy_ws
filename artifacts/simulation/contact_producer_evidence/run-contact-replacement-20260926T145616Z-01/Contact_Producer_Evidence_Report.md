# S3 D3 Contact Producer Evidence Report

Run: `run-contact-replacement-20260926T145616Z-01`

Classification: **INVALID — static preflight fail-closed; no runtime capture**

## Result

This was the single S3.3.12 replacement passive raw-contact evidence-run attempt. It stopped before Gazebo launch, temporary bridge creation, collector start, or any payload capture.

The post-edit SHA gate passed for both source and installed `tugbot_depot.sdf`:

```text
1c50f90d151a12559d426796c5d153c829b8777a5b4e8ef94c007a2023f6e271
```

The generated Xacro check also passed: collision occurrences `2` (definition plus sensor target), ContactSensor occurrences `1`, and raw topic occurrences `1`.

The invalidating check was the supervisor's exact-string world-name counter. The SDF uses the valid source spelling `<world name='world_demo'>`, while that counter only matched the double-quoted spelling. The record therefore has `world_name_count: 0` and the supervisor correctly fail-closed under its implemented gate. This is a tooling preflight defect, not runtime evidence about Gazebo, the Contact system, sensor delivery, or the bridge.

## Static and boundary evidence

| Item | Observed result |
| --- | --- |
| Source/install SHA-256 | Both match the approved post-edit digest. |
| Contact system declaration | Count `1`. |
| Named collision | Count `1` in source; count `2` in rendered robot description due to definition and sensor reference. |
| ContactSensor and raw topic | Each count `1`. |
| Collector/analyzer source scan | No publisher, service-client, or action-client pattern found. |
| Gazebo / one-topic bridge / collector | Not started. |
| Raw `Contacts` payloads | `0`. |
| `/clock` messages and runtime graph snapshots | `0` / unavailable. |
| `/cmd_vel` publication by measurement | `0`. |
| Control service or action call | `0`. |
| Hardware operation | `0`. |
| Shutdown | Complete; no measurement-created process existed. |

## Bridge and contact evidence

The approved temporary bridge was never started. Its literal remains:

```text
/s3_d3/contact/raw@ros_gz_interfaces/msg/Contacts[gz.msgs.Contacts
```

The `[` marker is static local `parameter_bridge` syntax for Gazebo-to-ROS. It is not runtime graph or delivery evidence for this invalid run.

There is no aggregate header/timestamp, entity/scoped-name, contact cardinality, duplicate, or simultaneous-contact observation because no raw message was received.

## Artifact records

- [immutable manifest](manifest.json)
- [run result](run_result.json)
- [static robot validation](static_robot_validation.json)
- [tool source scan](tool_source_scan.json)
- [shutdown record](shutdown_record.json)

## Retained non-claims

This invalid run does not establish Gazebo Contact-system loading, sensor target resolution, bridge delivery, timestamp behavior, contact identity, collision policy, ContactLatch, reset semantics, reward/termination, Gym/SB3/training, command publication, or hardware readiness.

The one approved replacement-run scope is consumed. A subsequent run requires offline repair/validation of the world-name preflight parser and a separate explicit user approval; it must not be treated as an automatic retry.
