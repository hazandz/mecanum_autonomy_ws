# WP06_6D Scan Probe Observation and Teardown Remediation

## Classification and lifecycle

- Classification: `L2_RUNTIME_OBSERVABILITY_AND_PROCESS_OWNERSHIP_REMEDIATION`.
- Exact integration/source base: `b15e0fd6e83f840822b8ba11f68dbdf31de0978e`.
- Review branch: `wp06-scan-probe-observation-teardown-b15e0fd`.
- Evidence ceiling: `IMPLEMENTED_OFFLINE_GUARD_AND_SESSION_SOURCE_ONLY`.
- Future run: `WP06_6D_SIM_EVAL_SCAN_ENDPOINT_PROBE_RUN_003`, partition `wp06_scan_probe_run_003`, local world `wp06_scan_probe_world`.
- Run 003 remains future-only, guard-pending, and not runtime-authorized. A separate exact-integration User authorization is required after independent audit and integration.

## Decision

The probe source shall discover topics with `gz topic -l`, validate every listed name as an absolute Gazebo topic, and inspect only topics whose exact leaf is `scan` using `gz topic -i -t <topic>`. It shall accept only either the legacy `Type: gz.msgs.LaserScan` line or a valid `Publishers [Address, Message Type]:` section containing that exact publisher type. Subscriber-only type listings do not count. Arbitrary substring search is prohibited.

The static descriptor fixes the maximum candidate count at 16 and the maximum raw stdout or stderr stream at 1,048,576 bytes. Exceeding the transcript cap returns `TRANSCRIPT_LIMIT_EXCEEDED`; complete raw bytes remain in the transcript and their full size and SHA-256 are recorded. The transcript is written only inside the future run directory. Candidate creation does not create a run directory or transcript.

The Run 003 bootstrap is a separate, bridge-free launch using the existing local Fuel-free probe world, `-r -s -v 4`, `use_sim_time: true`, and exactly one robot creation in `wp06_scan_probe_world`. It hard-sets `GZ_PARTITION=wp06_scan_probe_run_003`. Future readiness requires the exact log line `Entity creation successful.`; elapsed time alone is not readiness.

The session runner is import-inert and uses a capacity-one pending guard. Before consumption it checks the exact integrated `HEAD` and `origin/integration/implementation`, a clean worktree, the authority decision, canonical manifest, pending guard, fixed command/run context, and every source hash against both local bytes and the exact integrated Git blobs. It consumes the guard immediately before starting the bootstrap in a new session/process group. The probe is invoked once and only after readiness. Teardown is limited to that runner-created process group and escalates `SIGINT` (10 seconds), `SIGTERM` (10 seconds), then `SIGKILL` (10 seconds). There is no retry after consumption.

## Evidence and non-claims

This candidate changes probe observability and process ownership. It does not create a bridge. A future `EXACTLY_ONE_MATCH` remains `OBSERVED_NOT_PINNED` and requires a separate Owner decision before WP06-6E. The future ROS boundary `GZ_TO_ROS /scan sensor_msgs/msg/LaserScan` is a non-claim, not an endpoint binding or bridge authorization.

Run 002 is outside this candidate's scope. This decision does not reset, modify, copy, or reinterpret Run 002 evidence. Run 002 source, launch, guard, manifest, tools, and world remain untouched.

No ROS `/scan`, `ros_gz_bridge`, TF evidence, runtime profile resolution, `ResolvedConfigV3`, `config_hash`, Gate B transition, runtime evidence, or runtime authorization is created. The candidate does not establish runtime compatibility or `RUNTIME_APPROVED`.

The project status remains:

```text
WP-04: BLOCKED_BY_CONTRACT
WP-05: OPEN
Gate A: PASSED
Gate B: NOT_STARTED
RUNTIME_APPROVED: NOT_APPROVED
```

## Runtime authorization boundary

Any future Run 003 requires independent audit, integration of the exact candidate, remote-ref verification, and a separate User authorization naming the exact integrated commit. Runtime readiness must then be established by the exact create log before the one-shot session runner is invoked. This review candidate itself performs no runtime operation.
