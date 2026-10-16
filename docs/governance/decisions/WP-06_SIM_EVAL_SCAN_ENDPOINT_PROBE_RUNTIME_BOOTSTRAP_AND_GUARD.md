# WP06 sim_eval scan endpoint probe runtime bootstrap and capacity-one guard

## Classification

`L2_SIM_EVAL_SCAN_ENDPOINT_PROBE_RUNTIME_BOOTSTRAP_AND_CAPACITY_ONE_GUARD`

## Base and source boundary

This review candidate is based directly on integration commit
`bfc1ef3cfe4ba98beefbe7f18607b97a41e52d15`. The Architecture DOCX SHA-256 is
`432eeac363a595cfcf7e81c4b66054fb674dba140a2ef3cffecd617ab8136204`.
The already integrated probe module, probe descriptor, and Gazebo LiDAR source
are pinned in the accompanying runtime guard manifest and single-run packet.

The declaration `<topic>scan</topic>` is a relative sensor topic and is not a
full Gazebo Transport endpoint. An observed endpoint remains
`OBSERVED_NOT_PINNED`; it requires a separate Owner decision before WP06-6E.
WP06-6E remains the sole owner of canonical ROS–Gazebo bridge implementation.

## Bounded implementation

The new bootstrap launch source has one responsibility: prepare an isolated
Gazebo Harmonic world with exactly one `robot_state_publisher`, exactly one
`ros_gz_sim/gz_sim.launch.py` include, and exactly one `ros_gz_sim create` for
the `ROBOT_URDF_final` entity sourced from `/robot_description`. The RSP uses
the current Xacro and `use_sim_time: false`; it exists for robot description
and static TF ownership only. This candidate does not measure, observe,
conclude, or pin TF. The existing `gazebo.launch.py` is not modified or used.

The standard-library capacity-one guard validates the exact packet digest,
source pins, command template, partition, run ID, and context. Its initial
`AUTHORIZED_NOT_CONSUMED` value is only the guard's local capacity state. It is
a guard seed, not a runtime approval. Acquire atomically changes it to
`CONSUMED` before subprocess start, so interruption or process crash cannot
leave a retryable run. Finalization records pass, fail, timeout, or interruption
while preserving `CONSUMED`.

The one-shot supervisor verifies the pinned Gazebo source, probe module, and
probe descriptor before acquire. It runs only the exact `env GZ_PARTITION=…
PYTHONPATH=… python3 -m mecanum_nav_bringup.sim_eval_scan_endpoint_probe`
argument vector with `shell=False` and a 75-second timeout. Probe execution
must occur separately from the bootstrap launch. Timeout cleanup is
launcher-managed escalation, not SIGINT-only. The supervisor creates a new,
unique run directory, records stdout/stderr, exit code, UTC timestamps, source
pins and result JSON, and never retries or chooses an endpoint.

## Runtime gate and outcome

This candidate does not execute the bootstrap, supervisor, probe, or guard and
does not consume the guard. After integration of this exact candidate, its
guard status is `RUNTIME_GUARD_IMPLEMENTED_NOT_CONSUMED`. A future runtime
execution still requires independent audit, integration of the exact
candidate, and explicit User authorization for that exact integration ref.
The guard seed itself does not satisfy that authorization requirement.

The only future pass is `EXACTLY_ONE_MATCH` with one exact
`gz.msgs.LaserScan` endpoint. All other probe outcomes, wrapper timeout,
preflight failure after acquire, and interruption fail and remain consumed.
A pass records only `OBSERVED_NOT_PINNED` and still requires a separate Owner
decision before WP06-6E.

## Explicit non-claims

No endpoint pin, bridge implementation/configuration, ROS `/scan` publisher,
TF measurement, cadence/latency/frame/no-return validation, profile resolution,
`ResolvedConfigV3`, `config_hash`, Gate B transition, runtime evidence, or
general runtime approval is created. WP-04 remains `BLOCKED_BY_CONTRACT`,
WP-05 remains `OPEN`, Gate A remains `PASSED`, Gate B remains `NOT_STARTED`,
and `RUNTIME_APPROVED: NOT_APPROVED`.

Evidence ceiling for this candidate: `IMPLEMENTED_OFFLINE_GUARD_AND_BOOTSTRAP_SOURCE_ONLY`.
