# S3 D3 Model-List Parser Repair Validation Report

## Scope

This is an offline-only repair validation for the spawned ContactSensor diagnostic supervisor. It did not launch Gazebo, ROS, `gz`, a bridge, a collector, a command/service/action path, or hardware. It created no approval guard, authorization record, or diagnostic run.

## Defect and observed raw grammar

The consumed S3.3.20 artifact retained a successful `gz model --list` query with this relevant stdout structure:

```text
Requesting state for world [world_demo]...

Available models:
    - ground_plane
    - Depot
    - depot_collision
    - tugbot
    - ROBOT_URDF_final
```

The former parser compared stripped whole lines directly to `ROBOT_URDF_final`, so it rejected the observed list-entry prefix `-` and produced a fail-closed incomplete result. The retained raw query record is unchanged at [01_models.json](../run-spawned-contactsensor-diagnostic-20260926T161318Z-01/queries/01_models.json).

The repaired parser accepts only this local observed grammar:

```text
one exact `Available models:` header
followed by zero or more non-empty entries matching:
^[ \t]*-[ \t]+([^ \t\r\n]+)[ \t]*$
```

`MODEL_IDENTITY_CONFIRMED` is produced only when the captured entry token equals exactly `ROBOT_URDF_final` exactly once. It rejects substrings, prefixes, suffixes, scoped-name guesses, duplicate exact entries, malformed entries, missing headers, invalid output types, nonzero exits, and timeouts. Every reject remains `DIAGNOSTIC_INCOMPLETE_ROBOT_ENTITY`; it never becomes `SENSOR_ABSENT_AFTER_SPAWN`.

## Files changed

| File | Change |
| --- | --- |
| [`run_spawned_contactsensor_diagnostic.py`](../tools/run_spawned_contactsensor_diagnostic.py) | Replaced whole-line comparison with the observed header-and-dash-entry exact parser; added `MODEL_IDENTITY_CONFIRMED`, fail-closed robot-entity status, and an offline parser self-test mode. |
| [`s3_d3_model_list_parser_self_test.json`](s3_d3_model_list_parser_self_test.json) | Immutable output of the offline self-test. |
| [`s3_d3_model_list_parser_self_test.exit_code`](s3_d3_model_list_parser_self_test.exit_code) | Recorded self-test exit code `0`. |

## Offline fixtures and results

| Fixture | Expected | Result |
| --- | --- | --- |
| Retained S3.3.20 raw stdout with one `- ROBOT_URDF_final` entry | Confirm exactly once | PASS — `MODEL_IDENTITY_CONFIRMED` |
| Two exact entries | Reject ambiguous | PASS — `DIAGNOSTIC_INCOMPLETE_ROBOT_ENTITY` |
| No exact entry | Reject | PASS — `DIAGNOSTIC_INCOMPLETE_ROBOT_ENTITY` |
| `ROBOT_URDF_final_backup` and `prefix_ROBOT_URDF_final` | Reject near matches | PASS — `DIAGNOSTIC_INCOMPLETE_ROBOT_ENTITY` |
| Empty output | Reject | PASS — `DIAGNOSTIC_INCOMPLETE_ROBOT_ENTITY` |
| Header followed by malformed non-entry | Reject | PASS — `DIAGNOSTIC_INCOMPLETE_ROBOT_ENTITY` |
| Nonzero exit code | Reject before parsing | PASS — `DIAGNOSTIC_INCOMPLETE_ROBOT_ENTITY` |
| Timeout | Reject before parsing | PASS — `DIAGNOSTIC_INCOMPLETE_ROBOT_ENTITY` |
| Non-string/invalid encoding representation | Reject | PASS — `DIAGNOSTIC_INCOMPLETE_ROBOT_ENTITY` |

The self-test executed `9` fixtures; all `9` passed. It used the retained raw record as a read-only fixture and no live command.

## Immutable retained evidence

The following hashes were rechecked before and after repair and are unchanged:

| Protected evidence | SHA-256 |
| --- | --- |
| S3.3.20 raw model-query record | `a8f45ad873d4692df7a56f15689c897d57d02857d5ec2ed3a73d29a42993e2cf` |
| S3.3.20 run result | `1bff6b97921175cd56fa3045b37ceb2547849d4f2b0a2ddb38a26fd688554a5c` |
| Consumed S3.3.20 approval guard | `1e5cddbec3531cbf4a8a78f97a0c6425d51f38c629162f2aa309b5aa1fdb13d5` |
| Completed S3.3.20 approval packet | `22ccba7533b8e679ed6eddc6a0e6d25e0d563a7bf311dea4912e676b951f8445` |

No retained S3.3.20 artifact, consumed approval record, or completed packet was edited. This repair does not revive or expand the consumed one-run authority.

## Validation commands

```text
python3 -m py_compile artifacts/simulation/contact_producer_evidence/tools/run_spawned_contactsensor_diagnostic.py
python3 artifacts/simulation/contact_producer_evidence/tools/run_spawned_contactsensor_diagnostic.py --offline-model-list-parser-self-test
```

Both completed with exit code `0`. JSON parse validation and scoped `git diff --check` also passed.

## Conclusion

**READY_FOR_NEW_USER_APPROVAL_PACKET_ONLY**

The parser repair is offline evidence only. A new user approval packet is required before any future diagnostic execution; no runtime, source robot, bridge, collector, or hardware approval is implied.
