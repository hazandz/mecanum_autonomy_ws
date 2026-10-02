# ACR S2 Snapshot Synchronization Temporal Contract

Status: DRAFT — PENDING_USER_APPROVAL

Authority: This is a decision draft derived from the authoritative
`MECANUM_NAV_DRL_Architecture.docx` and approved ACR S1. It does not modify
the architecture, configuration schema, runtime graph, or implementation.

## Scope and non-goals

This record defines the proposed temporal and lifecycle contract for the
core-only `SnapshotSynchronizer` planned between policy-safe LiDAR input and
the internal `SimulatedOdometryEmulator` output in `sim_train`.

The synchronizer SHALL remain pure Python. It SHALL NOT import ROS, Gazebo,
TF, or Ground Truth types; publish a topic or TF; implement a reset
transaction; or select an actuator command. No implementation is created by
this draft.

## Time-domain contract

`scan_stamp_ros_ns` and `odom_stamp_ros_ns` are exact integer simulation/ROS
timestamps. They are used only for temporal alignment and barrier ordering:

```text
abs(scan_stamp_ros_ns - odom_stamp_ros_ns) <= sync_tolerance_ns
stamp_ros_ns > action_barrier_ros_ns
stamp_ros_ns > reset_barrier_ros_ns
```

`received_steady_ns` is a local monotonic receive-time sample. It is used only
for freshness against a steady-clock age budget:

```text
now_steady_ns - received_steady_ns <= max_receive_age_ns
```

The two clock domains SHALL NOT be subtracted from each other or converted to
one another. Timestamps and steady receive times must be carried separately by
future ingress metadata.

## Decision draft

The measured idle-Gazebo timing evidence is recorded in
[`Timing_Evidence_Report_MultiRun.md`](../artifacts/simulation/snapshot_synchronization_timing/Timing_Evidence_Report_MultiRun.md).
The associated review choices are in
[`S2_Snapshot_Synchronization_Approval_Packet.md`](S2_Snapshot_Synchronization_Approval_Packet.md).
Both records remain pending user approval and do not apply their conclusion to
`deploy_real`.

| Decision | Options | Advantages and disadvantages | Recommendation | Current value | Evidence required before approval |
| --- | --- | --- | --- | --- | --- |
| Pairing policy | Exact timestamps; nearest candidate within a tolerance | Exact matching makes unavailable correspondence explicit. Nearest pairing can tolerate cadence skew but may combine temporally inconsistent measurements. | For current `sim_train`, propose exact timestamps only; nonzero skew is pending or dropped, never nearest-paired. | PROPOSED — PENDING_USER_APPROVAL | Multi-run idle-Gazebo trace, deterministic exact-only replay test, and user approval. |
| `sync_tolerance_ns` | Zero; a configured positive value | Zero requires an exact candidate. A positive value can combine temporally inconsistent inputs if too large. | For current `sim_train`, propose explicit `0`; do not infer a positive tolerance from observed outliers. | PROPOSED — PENDING_USER_APPROVAL | User approval for exact-only, plus later evidence before any positive value is considered. |
| Maximum scan and odometry receive age | One shared budget; separate budgets | A shared budget is simpler. Separate budgets express asymmetric sensor timing but add configuration surface. | Carry distinct explicit steady-clock age budgets until evidence justifies a shared value. | REQUIRED_MEASUREMENT | End-to-end receive-age distributions and stale-sensor fault scenarios. |
| Scan and odometry buffer capacity | Fixed equal capacity; independently configured capacities | Fixed equal capacity is simpler. Independent capacities match different rates but require more validation. | Independently configured positive capacities; do not set counts here. | REQUIRED_MEASUREMENT | Rate ratio, maximum jitter, delay/dropout traces, and memory bound evidence. |
| Buffer-overflow recovery | Evict oldest; reject newest; clear buffers and require lifecycle recovery | Eviction can silently alter temporal provenance. Clear-and-recover is fail-closed but interrupts observation production. | Clear both buffers, report explicit overflow, and inhibit pairing until the approved recovery action occurs. | PROPOSED | Overflow injection test and recovery/lifecycle evidence. |
| Pending scan after `DELAYED` or `DROPPED` | Clear pending scan; retain until receive-age expiry | Clearing immediately loses a scan that could still pair with a later, genuinely delayed valid measurement. Retaining requires strict freshness checks. | Keep unmatched scans only until their steady receive-age expiry; do not pair them with cached old odometry. | PROPOSED | Delay-queue trace demonstrating no stale or fabricated pair. |
| Duplicate and out-of-order identity | Timestamp only; source sequence; ingress delivery ID plus candidate identity | Timestamp alone cannot identify all events. Odometry sequence is meaningful for valid measurements but may appear to move backward across delayed delivery events. | Scan identity: lifecycle plus scan timestamp. Valid-odometry identity: lifecycle plus valid sequence and measurement timestamp. Status-event identity: monotonic ingress delivery ID. | PROPOSED | Replay test with delayed, dropped, duplicate, and reordered events. |
| `reset_epoch` and `runtime_generation` | Infer from timestamps; inject active lifecycle metadata | Timestamp inference is ambiguous across reset/restart. Explicit lifecycle metadata matches the architecture and permits fail-closed validation. | Future adapter injects both values with every ingress item and exposes the active values to the synchronizer. | PROPOSED | Reset/restart trace and epoch/generation transition tests. |
| Action/reset barrier provenance | Ignore barriers in core; inject receipt barriers | Ignoring barriers violates the architecture. Injected barriers retain core-only separation but require an owner. | Future reset/action transaction layer supplies `action_barrier_ros_ns` and `reset_barrier_ros_ns` through active lifecycle context. | PROPOSED | Transaction ordering tests around reset and action receipt. |

No receive-age or capacity value is selected by this draft. The exact-only
`sim_train` pairing recommendation remains a proposal until the user approves
the linked approval packet.

## Event-order policy

`DELAYED` and `DROPPED` odometry snapshots are diagnostic delivery events. They
MUST NOT create a pair and MUST NOT automatically clear a valid-odometry
buffer. A later `VALID` snapshot can carry a measurement timestamp older than
the order in which events were delivered because the emulator uses a delay
queue.

Therefore, a synchronizer MUST NOT apply a single monotonically increasing
timestamp or sequence check across every odometry event. It shall validate
ordering separately for valid measurement candidates and use a separate
monotonic ingress delivery ID to identify diagnostic-event duplicates or
reordering. This delivery ID does not exist in the current input types.

The synchronizer must never replace an unavailable measurement with Ground
Truth, a previous valid odometry sample, or a previous scan.

## API impact for Phase S.2.2A

The following are proposed new core-only types; none exists yet:

| Proposed type | Required fields or responsibility | Current source status |
| --- | --- | --- |
| `SynchronizationConfig` | `sync_tolerance_ns`, scan/odometry max receive ages, scan/odometry capacities, overflow policy | Not present in `config/models.py` or `sim_train.yaml`. |
| `IngressMetadata` | `reset_epoch`, `runtime_generation`, `received_steady_ns`, `ingress_delivery_id` | Not present on `RawLidarScan` or `SimulatedOdometrySnapshot`. |
| `ActiveLifecycleContext` | Active epoch/generation and action/reset ROS-time barriers | No current producer in `sim_train`. |
| `SynchronizedSensorInput` | A copied `RawLidarScan`, a `VALID` `SimulatedOdometrySnapshot`, matching metadata, and both ROS stamps | Not present. It must not carry Ground Truth. |
| `SynchronizationStatus` and `SynchronizationResult` | Explicit ready, pending, stale, skew, lifecycle-mismatch, duplicate, out-of-order, and overflow outcomes | Not present; existing `ObservationEncodingStatus` cannot express scan synchronization states. |

`RawLidarScan` has an exact timestamp but no sequence or lifecycle/receive
metadata. `SimulatedOdometrySnapshot` has timestamp, status, and sequence but
no lifecycle/receive metadata or ingress delivery ID. `SensorSnapshot` already
contains epoch/generation and scan/odom stamps, but lacks explicit status,
candidate identity, receive metadata, and an implementation connection to the
new policy-safe input types.

After a valid synchronization result, a later composition layer—not the
synchronizer—will pass scan data to `LidarAngularBinner`, odometry to the goal
and measured-twist extractors, and a separately supplied prior issued command
to the previous-command extractor before calling `ObservationEncoder`.

## Exit criteria

The project becomes `READY FOR CORE-ONLY S.2.2A IMPLEMENTATION` only when all
conditions below are met:

- [ ] The user approves exact-only pairing with `sync_tolerance_ns = 0` for the
      current `sim_train` core-only scope, or supplies an approved alternative.
- [ ] The user permits only the test-only metadata/config needed to exercise
      that pairing policy without a runtime adapter.
- [ ] Core-only tests prove no nearest fallback, Ground Truth fallback, or
      fabricated synchronized input.

`READY FOR RUNTIME INTEGRATION` requires separate approval and evidence for
receive ages, buffer capacities, overflow recovery, epoch/generation and
ingress-delivery sources, action/reset barriers, and reset/delay/dropout/
motion/CPU-contention behavior.

Until then, SnapshotSynchronizer remains design-only and no runtime adapter,
ROS subscription, Gazebo integration, or policy observation assembly may be
implemented from this draft.
