# Snapshot Synchronization Timing Evidence

Execution timestamp UTC: 2026-09-22T08:44:23.014566+00:00

## Scope

- Collector subscriptions only: `/scan` and `/odom`; no publisher, `/cmd_vel`, reset, or service-control operation.
- Header (ROS/simulation) stamps and steady receive times remain separate time domains.
- Capture duration steady ns: 60000119412; scans: 553; odometry: 2759.

## Stream and pair statistics (nanoseconds)

| Metric | Count | Min | P50 | P95 | P99 | Max |
| --- | --- | --- | --- | --- | --- | --- |
| scan ROS stamp interval | 552 | 100000000 | 100000000 | 100000000 | 100000000 | 100000000 |
| scan steady receive inter-arrival | 552 | 770126 | 106267125 | 128697741 | 139199981 | 162946312 |
| odom ROS stamp interval | 2758 | 20000000 | 20000000 | 20000000 | 20000000 | 20000000 |
| odom steady receive inter-arrival | 2758 | 4640851 | 20412777 | 33720541 | 42879231 | 58750598 |
| nearest-by-stamp absolute skew | 553 | 0 | 0 | 0 | 0 | 140000000 |
| signed steady receive wait | 553 | -73402734 | -32938117 | -13436096 | -10058586 | 19088869 |
| positive steady receive wait | 2 | 18318743 | 18703806 | 19088869 | 19088869 | 19088869 |

## Pairability evidence

- Nearest-by-stamp candidates: 553; scans with no odom record available at all: 0.
- The latter is trace availability only, **not** evidence that a scan is pairable under a future tolerance.
- Exact stamp matches: 551; nonzero-skew pairs: 2.
- Candidate received before/with scan: 551; after scan (buffer wait needed): 2.

## Tolerance options — not approved

| Status | Option | Tolerance ns | Accepted pairs | Dropped pairs | Temporal-mismatch risk |
| --- | --- | --- | --- | --- |
| PROPOSED_FROM_MEASUREMENT_PENDING_USER_APPROVAL | exact_only | 0 | 551 | 2 | No temporal mismatch accepted; vulnerable to any timestamp phase offset. |
| PROPOSED_FROM_MEASUREMENT_PENDING_USER_APPROVAL | p99_plus_analysis_margin | 1000000 | 551 | 2 | p99 nearest skew plus 1000000 ns analysis margin; must be remeasured under load. |
| PROPOSED_FROM_MEASUREMENT_PENDING_USER_APPROVAL | max_observed | 140000000 | 553 | 0 | Accepts every nearest-by-stamp pair in this trace; largest temporal mismatch is retained. |

## Full nonzero-skew outliers

| Scan stamp ns | Odom stamp ns | Absolute skew ns | Scan receive steady ns | Odom receive steady ns | Signed receive wait ns |
| --- | --- | --- | --- | --- | --- |
| 12000000000 | 12140000000 | 140000000 | 86118401147928 | 86118420236797 | 19088869 |
| 12100000000 | 12140000000 | 40000000 | 86118401918054 | 86118420236797 | 18318743 |

## Limitations

- Idle Gazebo only; no reset, delay/dropout, CPU contention, or command-motion evidence.
- This report does not select a synchronizer tolerance, receive-age budget, or buffer capacity.
- It is not deploy-real or hardware evidence and does not approve S.2.2A.
