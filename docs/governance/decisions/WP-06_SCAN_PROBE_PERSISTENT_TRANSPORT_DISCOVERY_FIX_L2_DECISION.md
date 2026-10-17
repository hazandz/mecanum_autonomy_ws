# WP06 Run 005 persistent Gazebo Transport discovery — L2 decision

## Classification and scope

`L2_SIM_EVAL_SCAN_PROBE_PERSISTENT_TRANSPORT_DISCOVERY_FIX` authorizes one
offline source, test, and build candidate for a future Run 005. The source
replaces short-lived `gz service --list` readiness polling with one persistent
`gz.transport.Node` and an exact service-name check. No runtime is authorized
or executed by this candidate.

## Finding and correction

The reported Run 004 failure was a service-readiness false negative in the
short-lived CLI discovery mechanism. It is not evidence that the LiDAR failed.
`gz service --list` creates a short-lived discovery process and is unsuitable
as this readiness gate. Run 005 delays importing
`from gz.transport import Node, NodeOptions` until session execution, checks
that import before consuming its guard, creates exactly one options object and
one `Node`, sets partition `wp06_scan_probe_run_005`, and polls
`Node.service_list()` on that same node for the exact
`/world/wp06_scan_probe_world/create` service. Discovery snapshots and bounded
attempt metadata are retained in a future run directory; scan endpoints are
not inspected during readiness.

After exact service readiness, the future session may run one robot creation
command and one probe under its own pending capacity-one guard. Create
readiness requires exit code zero and the exact bytes
`Entity creation successful.`. Create process-group accounting is performed
in `finally`, including failed create outcomes. Process teardown is limited
to the process groups created by Run 005 and records live and zombie members
separately.

## Historical boundary

Run 004 historical evidence is not modified or reinterpreted as a pass. Run
002 and Run 003 are also outside this candidate. Their Git source artifacts
remain unchanged.

## Runtime and evidence boundary

The Run 005 guard starts at
`PENDING_EXACT_INTEGRATION_AND_USER_AUTHORIZATION`, capacity one. This
candidate does not authorize runtime and does not consume the guard. A future
session requires independent audit, integration of the exact candidate, and
separate Owner authorization for the exact integration commit.

Even a future successful observation means only
`GZ_LASERSCAN_ENDPOINT_OBSERVED_NOT_PINNED`. It does not establish ROS
`/scan`, a `ros_gz_bridge`, TF, AMCL, EKF, Nav2, runtime compatibility, Gate B,
or `RUNTIME_APPROVED`. No endpoint pin, ROS publisher, bridge, TF evidence,
runtime evidence, `ResolvedConfigV3`, or `config_hash` is created here.

`WP-04: BLOCKED_BY_CONTRACT`; `WP-05: OPEN`; `Gate A: PASSED`;
`Gate B: NOT_STARTED`; `RUNTIME_APPROVED: NOT_APPROVED` remain unchanged.
Evidence ceiling: `IMPLEMENTED_OFFLINE_GUARD_AND_SESSION_SOURCE_ONLY`.
