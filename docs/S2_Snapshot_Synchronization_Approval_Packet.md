# S2 Snapshot Synchronization Approval Packet

Status: `PENDING_USER_APPROVAL`

Scope: `sim_train` core-only temporal policy. This packet is derived from
[ACR S2](ACR_S2_Snapshot_Synchronization_Temporal_Contract.md) and the
[multi-run timing evidence](../artifacts/simulation/snapshot_synchronization_timing/Timing_Evidence_Report_MultiRun.md).
It does not approve runtime integration, deploy-real behavior, or hardware.

## Evidence summary

The idle-Gazebo measurement set contains six independent captures. The
collector subscribed only to `/scan` and `/odom`; it issued no `/cmd_vel`,
reset, teleop, service-control, UART, or hardware operation.

| Evidence item | Measured result |
| --- | --- |
| Nearest-by-stamp scan–odometry pairs | 3,419 |
| Exact timestamp matches | 3,413 |
| Nonzero timestamp skew | 6 (0.1755%) |
| Maximum observed skew | 140 ms |
| 60 ms skew occurrence | 1 pair in 1 of 6 runs (0.0292%) |

This is Gazebo idle timing evidence only. It is not deploy-real, hardware,
reset, delay/dropout, CPU-contention, or command-motion evidence.

## Proposed sim_train decision

The proposed policy is:

```text
pairing_policy = exact_timestamp_only
sync_tolerance_ns = 0
```

Under this proposal, a nonzero timestamp skew is `DROP_OR_PENDING`: a scan may
remain pending while its matching-timestamp odometry candidate could still
arrive within a later-approved receive-age policy, but it MUST NOT be
nearest-paired to odometry with a 20/40/60/100/140 ms timestamp difference.

Rationale: the observed outliers indicate a missing, delayed, or otherwise
unavailable exact candidate somewhere in the trace, bridge, or collector
pipeline. They do not authorize the policy to consume sensor state measured at
a different simulation time. This recommendation applies only to the current
`sim_train` core-only contract; it does not apply to `deploy_real`.

## Decision table for user approval

| Option | Evidence acceptance / drop | Temporal-mismatch risk | Recommendation or reject rationale | Decision |
| --- | --- | --- | --- | --- |
| Exact-only, `0 ns` | 3,413 accepted / 6 dropped or pending | No timestamp mismatch reaches policy; unavailable exact candidates reduce readiness. | **PROPOSED for sim_train.** Preserves temporal provenance and makes missing data explicit. | `[ ] APPROVED` `[ ] DEFERRED` |
| Nearest within percentile plus margin, `1,000,000 ns` | 3,413 accepted / 6 dropped | Allows a positive contract tolerance if future evidence requires it; this idle evidence still accepts no additional pair. | Not recommended now: adds policy surface without resolving measured outliers. | `[ ] APPROVED` `[ ] DEFERRED` |
| Nearest within maximum observed, `140,000,000 ns` | 3,419 accepted / 0 dropped | Can combine measurements up to 140 ms apart. | Rejected as current sim_train recommendation: it hides missing temporal correspondence and can inject policy-state mismatch. | `[ ] APPROVED` `[ ] DEFERRED` |

The table records choices for user review; no row becomes active unless the
user explicitly approves it and the DRAFT ACR is updated accordingly.

## Decisions still lacking evidence

The following remain outside this pairing decision and are not approved:

- scan and odometry steady receive-age budgets;
- scan and odometry buffer capacities;
- overflow recovery;
- authoritative `reset_epoch` and `runtime_generation` sources;
- ingress delivery ID;
- action/reset barrier source and lifecycle;
- delay/dropout and motion/CPU-contention timing evidence.

## Exit criteria

### READY FOR CORE-ONLY S.2.2A

All of the following are required:

- [ ] User approves `exact_timestamp_only` with `sync_tolerance_ns = 0` for
      the current `sim_train` core-only scope, or supplies an approved
      alternative.
- [ ] User explicitly permits test-only metadata/config needed to exercise the
      approved pairing contract without a ROS or Gazebo runtime adapter.
- [ ] The resulting implementation remains fail-closed: no nearest fallback,
      Ground Truth fallback, or fabricated synchronized sample.

### READY FOR RUNTIME INTEGRATION

Core-only implementation alone is insufficient. All of the following must be
approved and evidenced first:

- [ ] receive-age budgets, buffer capacities, and overflow recovery;
- [ ] lifecycle metadata sources (`reset_epoch`, `runtime_generation`, ingress
      delivery ID) and action/reset barriers;
- [ ] timing behavior under reset, delay/dropout, motion, and CPU contention;
- [ ] the runtime graph/config changes needed to carry that metadata.

No code, runtime graph, configuration, or hardware behavior changes merely by
creating this approval packet.
