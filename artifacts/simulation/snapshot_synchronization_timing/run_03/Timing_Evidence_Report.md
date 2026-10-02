# Snapshot Synchronization Timing Evidence

Execution timestamp UTC: 2026-09-22T08:44:23.035168+00:00

## Scope

- Collector subscriptions only: `/scan` and `/odom`; no publisher, `/cmd_vel`, reset, or service-control operation.
- Header (ROS/simulation) stamps and steady receive times remain separate time domains.
- Capture duration steady ns: 60006348016; scans: 583; odometry: 2912.

## Stream and pair statistics (nanoseconds)

| Metric | Count | Min | P50 | P95 | P99 | Max |
| --- | --- | --- | --- | --- | --- | --- |
| scan ROS stamp interval | 582 | 100000000 | 100000000 | 100000000 | 100000000 | 100000000 |
| scan steady receive inter-arrival | 582 | 53487932 | 102093923 | 122876840 | 132096512 | 141136869 |
| odom ROS stamp interval | 2911 | 20000000 | 20000000 | 20000000 | 20000000 | 20000000 |
| odom steady receive inter-arrival | 2911 | 6295932 | 20130108 | 27631027 | 36216116 | 53124170 |
| nearest-by-stamp absolute skew | 583 | 0 | 0 | 0 | 0 | 60000000 |
| signed steady receive wait | 583 | -63737904 | -25293445 | -10050924 | -7660511 | 10378867 |
| positive steady receive wait | 1 | 10378867 | 10378867 | 10378867 | 10378867 | 10378867 |

## Pairability evidence

- Nearest-by-stamp candidates: 583; scans with no odom record available at all: 0.
- The latter is trace availability only, **not** evidence that a scan is pairable under a future tolerance.
- Exact stamp matches: 582; nonzero-skew pairs: 1.
- Candidate received before/with scan: 582; after scan (buffer wait needed): 1.

## Tolerance options — not approved

| Status | Option | Tolerance ns | Accepted pairs | Dropped pairs | Temporal-mismatch risk |
| --- | --- | --- | --- | --- |
| PROPOSED_FROM_MEASUREMENT_PENDING_USER_APPROVAL | exact_only | 0 | 582 | 1 | No temporal mismatch accepted; vulnerable to any timestamp phase offset. |
| PROPOSED_FROM_MEASUREMENT_PENDING_USER_APPROVAL | p99_plus_analysis_margin | 1000000 | 582 | 1 | p99 nearest skew plus 1000000 ns analysis margin; must be remeasured under load. |
| PROPOSED_FROM_MEASUREMENT_PENDING_USER_APPROVAL | max_observed | 60000000 | 583 | 0 | Accepts every nearest-by-stamp pair in this trace; largest temporal mismatch is retained. |

## Full nonzero-skew outliers

| Scan stamp ns | Odom stamp ns | Absolute skew ns | Scan receive steady ns | Odom receive steady ns | Signed receive wait ns |
| --- | --- | --- | --- | --- | --- |
| 210200000000 | 210260000000 | 60000000 | 86332576714589 | 86332587093456 | 10378867 |

## Limitations

- Idle Gazebo only; no reset, delay/dropout, CPU contention, or command-motion evidence.
- This report does not select a synchronizer tolerance, receive-age budget, or buffer capacity.
- It is not deploy-real or hardware evidence and does not approve S.2.2A.
