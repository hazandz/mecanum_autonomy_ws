# Snapshot Synchronization Timing Evidence

Execution timestamp UTC: 2026-09-22T08:44:23.024547+00:00

## Scope

- Collector subscriptions only: `/scan` and `/odom`; no publisher, `/cmd_vel`, reset, or service-control operation.
- Header (ROS/simulation) stamps and steady receive times remain separate time domains.
- Capture duration steady ns: 60005962111; scans: 544; odometry: 2716.

## Stream and pair statistics (nanoseconds)

| Metric | Count | Min | P50 | P95 | P99 | Max |
| --- | --- | --- | --- | --- | --- | --- |
| scan ROS stamp interval | 543 | 100000000 | 100000000 | 100000000 | 100000000 | 100000000 |
| scan steady receive inter-arrival | 543 | 47860747 | 108969178 | 130542082 | 142626823 | 161668450 |
| odom ROS stamp interval | 2715 | 20000000 | 20000000 | 20000000 | 20000000 | 20000000 |
| odom steady receive inter-arrival | 2715 | 2498670 | 20562592 | 36110003 | 44960802 | 55297781 |
| nearest-by-stamp absolute skew | 544 | 0 | 0 | 0 | 0 | 100000000 |
| signed steady receive wait | 544 | -72517225 | -36046606 | -13979958 | -11220491 | 19625389 |
| positive steady receive wait | 1 | 19625389 | 19625389 | 19625389 | 19625389 | 19625389 |

## Pairability evidence

- Nearest-by-stamp candidates: 544; scans with no odom record available at all: 0.
- The latter is trace availability only, **not** evidence that a scan is pairable under a future tolerance.
- Exact stamp matches: 543; nonzero-skew pairs: 1.
- Candidate received before/with scan: 543; after scan (buffer wait needed): 1.

## Tolerance options — not approved

| Status | Option | Tolerance ns | Accepted pairs | Dropped pairs | Temporal-mismatch risk |
| --- | --- | --- | --- | --- |
| PROPOSED_FROM_MEASUREMENT_PENDING_USER_APPROVAL | exact_only | 0 | 543 | 1 | No temporal mismatch accepted; vulnerable to any timestamp phase offset. |
| PROPOSED_FROM_MEASUREMENT_PENDING_USER_APPROVAL | p99_plus_analysis_margin | 1000000 | 543 | 1 | p99 nearest skew plus 1000000 ns analysis margin; must be remeasured under load. |
| PROPOSED_FROM_MEASUREMENT_PENDING_USER_APPROVAL | max_observed | 100000000 | 544 | 0 | Accepts every nearest-by-stamp pair in this trace; largest temporal mismatch is retained. |

## Full nonzero-skew outliers

| Scan stamp ns | Odom stamp ns | Absolute skew ns | Scan receive steady ns | Odom receive steady ns | Signed receive wait ns |
| --- | --- | --- | --- | --- | --- |
| 90100000000 | 90200000000 | 100000000 | 86201986203982 | 86202005829371 | 19625389 |

## Limitations

- Idle Gazebo only; no reset, delay/dropout, CPU contention, or command-motion evidence.
- This report does not select a synchronizer tolerance, receive-age budget, or buffer capacity.
- It is not deploy-real or hardware evidence and does not approve S.2.2A.
