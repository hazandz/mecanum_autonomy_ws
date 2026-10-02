# S3 D3 Durable-Evidence Contract Completion — Offline Validation

Status: `PASS — OFFLINE ONLY — RUNTIME NOT APPROVED`

## Scope

S3.3.57 changed only the typed-Scene supervisor, the temporary typed-Scene
helper, their adjacent offline tests, and the remediation audit. No guard was
read for mutation, acquired, or consumed; no Gazebo, ROS, `gz`, launch, create,
helper runtime mode, bridge, command, control API, or hardware operation ran.

## Validated contract

| Contract | Offline evidence | Result |
| --- | --- | --- |
| Shared identity | `run_id` is generated before helper preparation; after successful preparation it is used for the durable directory, manifest, helper argv, summary, metadata, supervisor records, shutdown record, and future guard-consumption argument. | PASS |
| Prepare ordering | A mocked `PrepareFailure` occurs before `begin_run`, trusted context, acquire, consume, or durable directory creation. | PASS |
| Helper identity | Runtime argument parsing requires `--run-id`; empty, slash/traversal, and malformed IDs reject. The helper requires a matching durable `run_manifest.json`; the supervisor requires matching summary and metadata IDs. | PASS |
| No-overwrite persistence | C++ uses exclusive unique sibling files, `fsync`, `renameat2(RENAME_NOREPLACE)`, and directory `fsync`; existing and symlink targets reject. | PASS |
| Raw receipt pair | SHA failure removes the just-written raw protobuf; duplicate persistence, target collisions, symlink target, and temporary-file cleanup are fixtures. | PASS |
| Mandatory terminal records | No-response terminal finalization writes manifest, summary, metadata, create record, helper record, and shutdown record; it creates no placeholder raw response. | PASS |

## Commands and results

- `python3 -m py_compile artifacts/simulation/contact_producer_evidence/tools/run_typed_scene_observer.py`: PASS.
- `python3 -m unittest test_supervisor_owned_create.py` from the tools directory: **35 passed**.
- Temporary `/usr/bin/g++ -std=c++17 -Wall -Wextra -Werror` build using
  version-matched `gz-transport13`, `gz-msgs10`, and OpenSSL pkg-config flags: PASS.
- Temporary helper `--offline-self-test`: PASS.
- Temporary helper `--offline-artifact-self-test`: PASS.

The temporary compiler directory and binary were removed after validation. The
source has exactly one `RequestRaw`, in the unreachable future runtime path.
No `Sensor.type()` string comparison, shell, retry, SIGTERM, SIGKILL, or
`.kill()` path was introduced.

## Remaining blocker

The only blocker before a future packet, guard, or run is the separate static
collision/conversion investigation of the historical `base_link_collision`
warning versus `s3_d3_base_contact_collision`. This validation does not claim
collision behavior, ContactLatch readiness, reward, termination, training, or
hardware readiness.
