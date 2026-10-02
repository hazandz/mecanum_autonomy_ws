# Snapshot Synchronization Timing Evidence

Execution timestamp UTC: 2026-09-22T08:44:23.045671+00:00

## Scope

- Collector subscriptions only: `/scan` and `/odom`; no publisher, `/cmd_vel`, reset, or service-control operation.
- Header (ROS/simulation) stamps and steady receive times remain separate time domains.
- Capture duration steady ns: 60007639843; scans: 575; odometry: 2876.

## Stream and pair statistics (nanoseconds)

| Metric | Count | Min | P50 | P95 | P99 | Max |
| --- | --- | --- | --- | --- | --- | --- |
| scan ROS stamp interval | 574 | 100000000 | 100000000 | 100000000 | 100000000 | 100000000 |
| scan steady receive inter-arrival | 574 | 71583079 | 102990323 | 123783771 | 132123079 | 140613373 |
| odom ROS stamp interval | 2875 | 20000000 | 20000000 | 20000000 | 20000000 | 20000000 |
| odom steady receive inter-arrival | 2875 | 5522196 | 20171869 | 29681781 | 39093708 | 49188122 |
| nearest-by-stamp absolute skew | 575 | 0 | 0 | 0 | 0 | 20000000 |
| signed steady receive wait | 575 | -68761311 | -27845179 | -10800588 | -8150595 | -387196 |
| positive steady receive wait | 0 | None | None | None | None | None |

## Pairability evidence

- Nearest-by-stamp candidates: 575; scans with no odom record available at all: 0.
- The latter is trace availability only, **not** evidence that a scan is pairable under a future tolerance.
- Exact stamp matches: 574; nonzero-skew pairs: 1.
- Candidate received before/with scan: 575; after scan (buffer wait needed): 0.

## Tolerance options — not approved

| Status | Option | Tolerance ns | Accepted pairs | Dropped pairs | Temporal-mismatch risk |
| --- | --- | --- | --- | --- |
| PROPOSED_FROM_MEASUREMENT_PENDING_USER_APPROVAL | exact_only | 0 | 574 | 1 | No temporal mismatch accepted; vulnerable to any timestamp phase offset. |
| PROPOSED_FROM_MEASUREMENT_PENDING_USER_APPROVAL | p99_plus_analysis_margin | 1000000 | 574 | 1 | p99 nearest skew plus 1000000 ns analysis margin; must be remeasured under load. |
| PROPOSED_FROM_MEASUREMENT_PENDING_USER_APPROVAL | max_observed | 20000000 | 575 | 0 | Accepts every nearest-by-stamp pair in this trace; largest temporal mismatch is retained. |

## Full nonzero-skew outliers

| Scan stamp ns | Odom stamp ns | Absolute skew ns | Scan receive steady ns | Odom receive steady ns | Signed receive wait ns |
| --- | --- | --- | --- | --- | --- |
| 310700000000 | 310720000000 | 20000000 | 86435242469858 | 86435242082662 | -387196 |

## Limitations

- Idle Gazebo only; no reset, delay/dropout, CPU contention, or command-motion evidence.
- This report does not select a synchronizer tolerance, receive-age budget, or buffer capacity.
- It is not deploy-real or hardware evidence and does not approve S.2.2A.
