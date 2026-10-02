# Snapshot Synchronization Timing Evidence

Execution timestamp UTC: 2026-09-22T08:44:23.067271+00:00

## Scope

- Collector subscriptions only: `/scan` and `/odom`; no publisher, `/cmd_vel`, reset, or service-control operation.
- Header (ROS/simulation) stamps and steady receive times remain separate time domains.
- Capture duration steady ns: 60016713377; scans: 580; odometry: 2895.

## Stream and pair statistics (nanoseconds)

| Metric | Count | Min | P50 | P95 | P99 | Max |
| --- | --- | --- | --- | --- | --- | --- |
| scan ROS stamp interval | 579 | 100000000 | 100000000 | 100000000 | 100000000 | 100000000 |
| scan steady receive inter-arrival | 579 | 20106876 | 101918455 | 118853834 | 129554438 | 139737702 |
| odom ROS stamp interval | 2894 | 20000000 | 20000000 | 20000000 | 20000000 | 20000000 |
| odom steady receive inter-arrival | 2894 | 6235193 | 20177828 | 28489691 | 34285613 | 47772848 |
| nearest-by-stamp absolute skew | 580 | 0 | 0 | 0 | 0 | 100000000 |
| signed steady receive wait | 580 | -56818510 | -29626628 | -12423713 | -9674322 | 964808 |
| positive steady receive wait | 1 | 964808 | 964808 | 964808 | 964808 | 964808 |

## Pairability evidence

- Nearest-by-stamp candidates: 580; scans with no odom record available at all: 0.
- The latter is trace availability only, **not** evidence that a scan is pairable under a future tolerance.
- Exact stamp matches: 579; nonzero-skew pairs: 1.
- Candidate received before/with scan: 579; after scan (buffer wait needed): 1.

## Tolerance options — not approved

| Status | Option | Tolerance ns | Accepted pairs | Dropped pairs | Temporal-mismatch risk |
| --- | --- | --- | --- | --- |
| PROPOSED_FROM_MEASUREMENT_PENDING_USER_APPROVAL | exact_only | 0 | 579 | 1 | No temporal mismatch accepted; vulnerable to any timestamp phase offset. |
| PROPOSED_FROM_MEASUREMENT_PENDING_USER_APPROVAL | p99_plus_analysis_margin | 1000000 | 579 | 1 | p99 nearest skew plus 1000000 ns analysis margin; must be remeasured under load. |
| PROPOSED_FROM_MEASUREMENT_PENDING_USER_APPROVAL | max_observed | 100000000 | 580 | 0 | Accepts every nearest-by-stamp pair in this trace; largest temporal mismatch is retained. |

## Full nonzero-skew outliers

| Scan stamp ns | Odom stamp ns | Absolute skew ns | Scan receive steady ns | Odom receive steady ns | Signed receive wait ns |
| --- | --- | --- | --- | --- | --- |
| 489300000000 | 489400000000 | 100000000 | 86618560461413 | 86618561426221 | 964808 |

## Limitations

- Idle Gazebo only; no reset, delay/dropout, CPU contention, or command-motion evidence.
- This report does not select a synchronizer tolerance, receive-age budget, or buffer capacity.
- It is not deploy-real or hardware evidence and does not approve S.2.2A.
