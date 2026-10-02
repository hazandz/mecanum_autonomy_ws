# S3 D3 Post-Run Remediation Decision Audit

Status: `DRAFT — EVIDENCE CONTRACT COMPLETE OFFLINE ONLY — RUNTIME NOT APPROVED`

## Scope and authority

This document is a read-only design decision audit after the consumed S3.3.54
one-shot run. It does not amend the consumed authority, create a replacement
authority, or authorize a second run. S3.3.54 remains consumed with final
status `SHUTDOWN_INCOMPLETE` and must not be rerun.

Inputs reviewed:

- [S3.3.54 post-run reconciliation](S3_D3_Typed_Scene_Observer_S3_3_54_Post_Run_Evidence_Reconciliation.md)
- [Consumed S3.3.54 guard](../artifacts/simulation/contact_producer_evidence/approval_guards/S3.3.54_TYPED_SCENE_OBSERVER_FINAL_EXECUTION_RUN.json)
- [S3.3.54 supervisor metadata](../artifacts/simulation/contact_producer_evidence/run-typed-scene-20260928T071008Z/supervisor_metadata.json)
- [S3.3.54 bootstrap stdout](../artifacts/simulation/contact_producer_evidence/run-typed-scene-20260928T071008Z/bootstrap_launch_stdout.log)
- [S3.3.54 bootstrap stderr](../artifacts/simulation/contact_producer_evidence/run-typed-scene-20260928T071008Z/bootstrap_launch_stderr.log)
- [Current typed-Scene supervisor](../artifacts/simulation/contact_producer_evidence/tools/run_typed_scene_observer.py)
- [Current typed-Scene helper](../artifacts/simulation/contact_producer_evidence/tools/typed_scene_observer.cpp)
- [Dedicated typed-Scene launch](../ros2_ws/src/ROBOT_URDF_final_description/launch/typed_scene_observer.launch.py)
- [Dedicated-launch static checker](../artifacts/simulation/contact_producer_evidence/tools/check_typed_scene_diagnostic_launch.py)

The S3.3.54 reconciliation confirmed two remediation obligations:

1. the claimed Scene result has no retained canonical evidence; and
2. the observed cleanup path was not end-to-end SIGINT-only, because the
   `ros2 launch` process escalated its Gazebo child to SIGTERM.

## A. Evidence-retention repair design

### One immutable run identity

S3.3.57 now generates one opaque `run_id` before helper preparation. Helper
preparation remains temporary-only; the durable artifact directory is created
only after preparation succeeds and before trusted-context validation, guard
acquisition, bootstrap, create, or helper invocation. That exact value must be immutable and appear
in all of the following:

- the acquired/consumed guard record;
- the durable artifact directory name and its top-level manifest;
- supervisor metadata;
- create-process and helper-process records;
- helper request metadata and Scene summary; and
- the shutdown outcome record.

The guard must consume that pre-created value, not obtain a second timestamped
ID at the end of orchestration. The durable directory is created from the same value before launch, so
`run_id` and directory cannot diverge as they did in S3.3.54 (`071016Z` in the
guard versus `071008Z` in the directory). The helper receives the exact value
through mandatory `--run-id`; its summary and request metadata are rejected by
the supervisor unless both values match the active durable-run identity.

### Durable helper-output boundary

The helper may still be compiled in a temporary build directory, but its
future `--output-dir` must be a pre-created, non-symlink durable run-artifact
directory. The only canonical Scene evidence must not be written exclusively
to `TemporaryDirectory`. The supervisor may validate files in place and must
not delete or overwrite them during cleanup.

S3.3.57 implements each C++ helper output as an exclusive, unique sibling
temporary file in the durable output filesystem, followed by file `fsync`, a
no-overwrite atomic commit, and directory `fsync` where supported. Existing or
symlink targets fail closed and temporary files are removed on failure. A raw
protobuf and its SHA-256 are a pair: a SHA commit failure removes the raw file,
so no partial raw receipt is admissible. A terminal summary is committed only
after its mandatory companion evidence. This remains offline-only and is not
runtime approval.

### Required terminal-evidence set

| Evidence item | Required for every terminal outcome? | Conditions and semantics |
| --- | --- | --- |
| `run_manifest.json` (or equivalent immutable authority snapshot) | Yes | Contains `run_id`, approval/guard identity, locked source/world hashes, literals, and durable directory identity. |
| `scene_summary.json` | Yes | Canonical terminal diagnostic status, reason, `request_raw_called`, raw SHA or `null`, and the declared schema/version. |
| `request_metadata.json` | Yes | Contains the shared `run_id`, service/type literals, preflight and request timestamp fields with `null` where request did not occur, and helper process identity. |
| Create-process record | Yes | Exact create argv, executable identity/SHA, PID or explicitly unavailable PID, start/end steady timestamps, exit/timeout result, and one-invocation count. |
| Helper-process record | Yes | Exact helper argv/binary SHA, PID or explicitly unavailable PID, start/end steady timestamps, exit status, and request count. |
| Shutdown-outcome record | Yes | Per supervisor-owned group: SIGINT attempt, grace value, deadline result, any child-manager escalation observed, and final cleanup classification. |
| `scene_response.pb` | Conditional | Required exactly when a complete response byte sequence exists. It is legitimately absent for `SCENE_SERVICE_UNAVAILABLE`, request serialization failure, or `SCENE_REQUEST_INCOMPLETE` without response bytes. |
| Raw-response SHA-256 | Conditional | Required exactly with `scene_response.pb`; it must equal the immutable raw bytes. It is `null` when no response bytes exist. |

`SCENE_SERVICE_UNAVAILABLE` and an incomplete request without response bytes
are valid terminal outcomes, not permission to fabricate an empty `.pb` file
or a hash. Conversely, they still require the manifest, summary, request
metadata, process records, and shutdown outcome. A helper exit failure or any
partial-write failure is not eligible to claim a Scene status; it must be
recorded as an evidence/persistence failure by the future implementation.

### Why this repair is mandatory

S3.3.54's `persist_artifact()` retained only `supervisor_metadata.json`; its
helper files lived in a `TemporaryDirectory` and were removed on context exit.
The retained `SCENE_SENSOR_PRESENT_IDENTITY_ONLY` is therefore
`SUPERVISOR_REPORTED_ONLY`, not independently auditable. The repair above is
required before a future packet/guard/run can use a Scene status as evidence.

## B. Cleanup-policy reconciliation

The S3.3.54 log shows the actual chain: supervisor sends SIGINT to the
`ros2 launch` process group; launch sends SIGINT to Gazebo; after five seconds
launch escalates its Gazebo child to SIGTERM. The supervisor source did not
issue SIGTERM directly, but that distinction does not make the end-to-end run
SIGINT-only.

| Option | Can the resulting policy truthfully be called “SIGINT-only”? | Dedicated launch/create/artifact/guard impact | Evidence and work required | Risks and change scope |
| --- | --- | --- | --- | --- |
| 1. Correct the policy wording: the supervisor sends only SIGINT; launcher internals may escalate. | **No**, not end-to-end. The only truthful phrase is “supervisor-initiated SIGINT-only; launcher-managed escalation may occur.” | Dedicated launch and supervisor ownership can remain. Artifact/guard must record the actual per-process cleanup path, including an escalation field, rather than assert a SIGINT-only result. | Static review of launcher child-management behavior and a future artifact schema that records launch-manager escalation. A future approval must explicitly permit the revised policy wording. | Smallest implementation scope, but does not preserve the previous end-to-end safety claim. It also leaves `ros2 launch` as the child lifecycle owner. |
| 2. Change bootstrap ownership so the measurement does not depend on `ros2 launch` child escalation. | **Potentially yes**, but only after all measurement-created bootstrap processes are directly supervised and runtime evidence proves they exited within the SIGINT grace without escalation. | Requires a redesigned bootstrap route: the supervisor (or another explicitly approved owner) must own every relevant process group, including Gazebo/world and the description provider, while preserving one initial create and no bridge/control path. Dedicated launch is likely replaced or reduced; guard must bind the new ownership graph and artifact per-process records. | Static design, implementation, offline tests, and a future approved run that preserves process identities and shutdown receipts. | Broader ownership/launch change with a larger regression surface. It must not accidentally introduce a bridge, control API, second spawn, or retry path. |

Option 1 is selected and **IMPLEMENTED_OFFLINE_ONLY — RUNTIME NOT APPROVED**
for the future evidence contract. The authoritative wording is now
“supervisor-initiated SIGINT-only; launcher-managed escalation may occur.” It
must not be shortened to “end-to-end SIGINT-only.” Option 2 remains unselected
and would require a separate ownership/launch decision.

## C. Collision/contact warning: required static investigation

The S3.3.54 launch log reports that geometry for `base_link_collision` could
not be created. Current static source separately contains the approved Xacro
literal `s3_d3_base_contact_collision` and configures
`s3_d3_base_contact_sensor` to reference it. The mismatch between the observed
log literal and the approved literal is a **REQUIRED_STATIC_INVESTIGATION**.

It does not demonstrate that the ContactSensor was removed, that the contact
endpoint failed, that the named collision was absent, or that ContactLatch
could make any decision. A separate static increment must inspect, without
runtime inference:

1. the rendered URDF/Xacro hierarchy and exact base-link collision name;
2. the URDF-to-SDF/spawn conversion path and resulting collision names;
3. whether `s3_d3_base_contact_collision` survives as the exact target of
   `s3_d3_base_contact_sensor`;
4. the spawned/converted geometry representation and DART compatibility for
   that exact collision; and
5. sensor identity preservation separately from collision geometry creation.

No collision endpoint, contact event, filter policy, ContactLatch, reward, or
termination conclusion follows from this warning.

## D. Decision gate

The mandatory remediation sequence before any replacement packet, guard, or
run is:

1. approve and implement the durable, atomic evidence-retention contract with
   one pre-launch shared `run_id`;
2. resolve the cleanup-policy choice below and implement/validate its matching
   ownership and evidence contract; and
3. complete the separate required static investigation of the named collision,
   conversion, sensor identity, and geometry compatibility.

Cleanup Option 1 has been selected and the durable-evidence contract is
**EVIDENCE CONTRACT COMPLETE OFFLINE ONLY**: shared identity, durable helper
output, mandatory records, and no-overwrite persistence have offline tests.
S3.3.54 remains consumed and cannot be reused. The remaining blocker before a
new packet, guard, or run is only the separate static collision/conversion
investigation for `base_link_collision` versus
`s3_d3_base_contact_collision`; it was intentionally not changed here.

```text
BLOCKED_BY_REQUIRED_STATIC_COLLISION_CONVERSION_INVESTIGATION
```

No runtime operation, guard operation, source/configuration change, or
historical-artifact mutation was performed for this audit.
