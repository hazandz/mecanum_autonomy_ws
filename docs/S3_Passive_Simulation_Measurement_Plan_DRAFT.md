# S3 Passive Simulation Measurement Plan

Status: **DRAFT — PENDING_USER_APPROVAL**

## Purpose and authority

This plan defines a passive evidence collection procedure for the currently
configured Gazebo simulation streams. It is a measurement plan only. It does
not approve a task oracle, a collision/contact source, termination limits, a
Gymnasium environment, or any runtime implementation.

Authority and constraints:

- [MECANUM_NAV_DRL_Architecture.docx](MECANUM_NAV_DRL_Architecture.docx),
  schema `3.0`, remains authoritative.
- [ACR S1](ACR_S1_Simulated_Odometry_And_Ground_Truth_Isolation.md) permits
  hidden Ground Truth (GT) for oracle purposes, but forbids it from policy
  observation/runtime.
- [ACR S2](ACR_S2_Snapshot_Synchronization_Temporal_Contract.md) remains
  `DRAFT — PENDING_USER_APPROVAL`; its core-only exact pairing does not grant
  runtime approval.
- [S3 termination-input packet](S3_Termination_Inputs_And_Limits_Decision_Packet_DRAFT.md)
  leaves collision source, task/world facts, D6, and STUCK inputs pending.

The configured launch currently bridges `/clock`, `/ground_truth/odom`,
`/odom`, `/scan`, and `/tf`. The model configuration identifies
`OdometryPublisher` as the intended producer of `/ground_truth/odom` in
`world -> base_link`, while `MecanumDrive` is the legacy `/odom` path. These
are source-configuration facts, not runtime evidence and not a claim that
either path is canonical policy odometry.

## 1. Scope and safety boundary

The approved future measurement process may only observe these streams:

```text
/clock
/ground_truth/odom
/odom
/scan
/tf
```

It may subscribe to or inspect metadata for them, then write evidence outside
production packages. It SHALL NOT:

- publish `/cmd_vel` or any other command;
- reset, pause, step, set pose, spawn, delete, or otherwise change simulator
  state;
- call a control service, run teleoperation, or load a policy;
- modify the world, robot, bridge, launch configuration, or any source file;
- contact Pi, UART, STM32, firmware, or real hardware.

The measurement collector itself creates no `/cmd_vel` publisher. A pre-run
`/cmd_vel` graph snapshot defines the immutable allowlist for that one run.
Every allowlist entry SHALL record publisher name, node name and namespace when
the graph exposes them, message type, and publisher count. The two-way
`ros_gz_bridge` may be allowlisted only when that pre-run snapshot actually
identifies the observed owner and type; it is not allowlisted merely because a
launch file names the bridge. The allowlist SHALL NOT be expanded during the
warm-up or capture. The collector records `/cmd_vel` metadata only and never
publishes to the topic. If this plan starts Gazebo, it SHALL terminate Gazebo
cleanly with `SIGINT` after the capture or on any safety/protocol failure.

Allowlisting a pre-existing `ros_gz_bridge` publisher does not prove that no
other process sent a command through it or another path. The evidence can only
prove that the collector did not create a publisher or invoke a control action,
and that the recorded graph did or did not change during the run.

An idle trace is intentionally insufficient to evaluate collision,
goal-reached, out-of-bounds, STUCK, or episode-limit behavior. It only
characterizes the delivery and temporal properties of existing streams while
no intentional robot command is sent.

## 2. Evidence questions

The collector SHALL record an immutable per-message receive record. It may
record local `time.monotonic_ns()` at callback receipt, but it SHALL NOT
subtract, compare, or convert that value against a ROS/simulation timestamp.
Those are different clock domains.

| Stream | Source configuration to verify at runtime | Evidence questions | Required metadata |
| --- | --- | --- | --- |
| `/clock` | Gazebo clock bridged to `rosgraph_msgs/msg/Clock` | Is a clock publisher present? Is the simulation timestamp continuous, monotonic, non-duplicated as expected, and what are observed message rate and receive inter-arrival statistics? | Message index, `clock_ns`, local steady receive timestamp, publisher/type snapshot |
| `/ground_truth/odom` | Gazebo `OdometryPublisher` topic, bridged as `nav_msgs/msg/Odometry` | Is the runtime publisher/type present? Do `header.frame_id=world` and `child_frame_id=base_link` match configuration? What are stamp monotonicity, duplicates/regressions, rate, and receive inter-arrival? | Index, header stamp ns, frame IDs, pose/twist presence, local steady receive timestamp, publisher/type snapshot |
| `/odom` | Gazebo `MecanumDrive` legacy topic, bridged as `nav_msgs/msg/Odometry` | Is the runtime publisher/type present? Do its frame IDs match its configured `odom -> base_link` relation? What are stamp integrity, rate, and receive inter-arrival? | Same odometry metadata as above |
| `/scan` | GPU LiDAR topic, bridged as `sensor_msgs/msg/LaserScan` | Is the runtime publisher/type present? Are frame ID, header stamp, scan dimensions, declared angle/range metadata, and timestamp/rate behavior usable for later passive synchronization evidence? | Index, header stamp ns, frame ID, range count, angle/range metadata, local steady receive timestamp, publisher/type snapshot |
| `/tf` | Current Gazebo/bridge transform flow; graph may have multiple ROS TF publishers | Which publishers are present? Which dynamic transform records establish `world`, `odom`, and `base_link` relationships? Are header stamps/frame IDs coherent with the observed odometry streams? | TF message index, each transform parent/child/stamp, local steady receive timestamp, publisher/type snapshot |

Offline analysis SHALL calculate, in the ROS/simulation timestamp domain only:

- `/ground_truth/odom` ↔ `/odom` absolute stamp skew;
- `/scan` ↔ nearest `/odom` absolute stamp skew;
- `/scan` ↔ nearest `/ground_truth/odom` absolute stamp skew;
- per-stream duplicate/regression counts and stamp intervals.

It SHALL separately calculate, in the local steady-clock domain only,
per-stream receive inter-arrival minimum, median, p95, p99, and maximum.
No metric may mix the two domains.

## 3. Proposed measurement protocol

The following is a **PROPOSED measurement protocol**, not a D6 episode limit,
STUCK window, timeout, or approved runtime threshold.

1. Launch the existing default Gazebo launch unchanged, then wait for the ROS
   graph to expose all five scoped streams. Do not send a command, reset, or
   call any service.
2. Record a graph/type/publisher snapshot for every scoped stream. Record a
   complete `/cmd_vel` publisher snapshot and freeze it as the per-run
   allowlist; do not publish to `/cmd_vel`.
3. Allow a **PROPOSED 10-second warm-up** after all scoped streams appear. Do
   not include warm-up records in timing statistics.
4. Capture **PROPOSED six independent idle runs**, each for at least
   **PROPOSED 60 seconds**. A run is independent only after a clean shutdown
   and a fresh launch; it must not overwrite any earlier trace.
5. For each callback, append exactly one structured record containing stream
   name, per-stream index, ROS/simulation stamp where the message has one,
   frame metadata, and local steady receive time. For `/tf`, append one record
   for each contained transform plus its enclosing message index.
6. Stop capture cleanly, flush the trace, capture graph metadata again, and
   stop Gazebo with `SIGINT` if the measurement process started it.
7. Analyze each run independently before producing a cross-run aggregate.

A run is invalid and SHALL be retained only as an invalid record, excluded
from summary statistics, when any of these occur:

- a scoped stream is absent, has an unexpected message type, or produces no
  usable records after warm-up;
- required header/frame metadata cannot be parsed or recorded;
- the collector process creates any `/cmd_vel` publisher;
- a `/cmd_vel` publisher absent from the frozen pre-capture allowlist appears
  during warm-up or capture;
- there is evidence that the collector publishes a command or invokes a
  simulator-control action;
- the pre- or post-run graph/type snapshot is incomplete, so the allowlist
  cannot be recorded or compared;
- collector/launch failure prevents a clean trace boundary from being known;
- trace records mix runs, lose their run identifier, or cannot be decoded
  losslessly by the offline analyzer.

An observed timestamp regression, duplicate, skew, or TF discrepancy is an
evidence result, not by itself an invalidation. It must be reported verbatim.

## 4. Proposed artifact contract

No artifact or script is created by this plan. A later, separately approved
passive collector SHALL write only below:

```text
artifacts/simulation/passive_stream_timing/
├── README.md                                  # Scope, safety restriction, schema version
├── measurement_manifest.json                  # Immutable plan/run schema and tool versions
├── run-<utc-id>/
│   ├── capture_metadata.json                  # Launch, host, clock-domain and graph snapshots
│   ├── stream_trace.jsonl                     # Lossless callback/TF-transform records
│   ├── launch.log                             # Launch/process output for the run
│   ├── collector.log                          # Collector diagnostics only
│   └── summary.json                           # Per-run validated statistics and anomalies
└── Passive_Stream_Timing_Evidence_Report.md   # Cross-run aggregate and limitations
```

`capture_metadata.json` SHALL include: immutable run ID, UTC start/end,
launch invocation identity, scoped topic/type/publisher snapshots, the frozen
pre-capture `/cmd_vel` allowlist, post-run `/cmd_vel` publisher snapshot and
comparison, explicit statement that the collector issued no command/reset/
service call, and whether Gazebo was started/stopped by the measurement
process. `stream_trace.jsonl` SHALL retain the separate ROS/simulation and
steady-clock fields without coercing either through floating-point timestamps.

The aggregate report SHALL list all excluded/invalid runs, per-stream counts,
frame relations, timestamp/reception statistics, all nonzero timestamp-skew
outliers, every `/cmd_vel` publisher observed before and after each run, and
every graph change. It SHALL state explicitly that a permitted pre-existing
bridge publisher is not evidence that no external command was sent. Any
operational value inferred from the trace remains
`PROPOSED_FROM_MEASUREMENT`, never `APPROVED`.

## 5. Acceptance criteria and non-claims

### Candidate evidence for future `TrainingTaskOracle`

Passive evidence is sufficient only to identify `/ground_truth/odom` as a
runtime **candidate** when all of the following are observed and retained:

- the configured ROS type is `nav_msgs/msg/Odometry` and a stable publisher
  owner can be identified in the runtime graph;
- records consistently expose the configured `world` parent and `base_link`
  child frame relationship;
- timestamps are usable in the simulation/ROS domain, with all duplicates,
  regressions, gaps, and delivery skew explicitly reported;
- the stream can be observed independently of the legacy `/odom` path; and
- the evidence report states that GT is isolated from policy observation and
  policy runtime, per ACR S1.

Even a successful result does **not** create `TrainingTaskOracle`, prove its
goal-distance calculations, supply a task goal, establish world bounds, or
authorize GT to enter policy observation.

### What timing evidence can establish

The measurement may establish actual stream availability, message type,
publisher graph, frame metadata, timestamp behavior, arrival jitter, pairing
candidate distributions, and current TF relationships. It may support later
runtime-source and temporal-contract decisions.

### What this measurement cannot establish

An idle passive trace cannot prove any of the following:

- a contact source, collision pulse, ContactLatch, or action-interval join;
- goal definition, goal-reached semantics, task scenario, or out-of-bounds
  boundary;
- STUCK progress source, evaluation window, or threshold;
- D6 mode or numeric episode limit;
- correct actuator behavior, reset correctness, policy behavior, reward,
  termination, Gym transition semantics, or real-robot safety.

## 6. Handoff and approval gate

The next phase may begin only when the user approves this plan's passive-only
boundary and artifact contract. Its allowable scope is strictly:

- create a collector and offline analyzer outside the production package;
- launch the existing Gazebo launch unchanged;
- subscribe passively to `/clock`, `/ground_truth/odom`, `/odom`, `/scan`, and
  `/tf`;
- save the proposed evidence artifacts and a factual report; and
- stop Gazebo cleanly.

That next phase SHALL NOT publish commands, call simulator-control services,
reset the world, create a task oracle or contact source, modify production
code/configuration, or infer D6/STUCK values from an idle trace.

**Final status: DRAFT — PENDING_USER_APPROVAL.**
