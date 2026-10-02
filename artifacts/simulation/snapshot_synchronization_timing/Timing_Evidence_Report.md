# Snapshot Synchronization Timing Evidence

Execution timestamp UTC: 2026-09-22T08:31:05.718096+00:00

## Scope

- Collector subscriptions only: `/scan` and `/odom`; no publisher, `/cmd_vel`, reset, or service-control operation.
- Header (ROS/simulation) stamps and steady receive times remain separate time domains.
- Capture duration steady ns: 60014439179; scans: 556; odometry: 2777.

## Stream and pair statistics (nanoseconds)

| Metric | Count | Min | P50 | P95 | P99 | Max |
| --- | --- | --- | --- | --- | --- | --- |
| scan ROS stamp interval | 555 | 100000000 | 100000000 | 100000000 | 100000000 | 100000000 |
| scan steady receive inter-arrival | 555 | 71109677 | 105877455 | 130176545 | 140954403 | 149801655 |
| odom ROS stamp interval | 2776 | 20000000 | 20000000 | 20000000 | 20000000 | 20000000 |
| odom steady receive inter-arrival | 2776 | 5769254 | 20325909 | 33442913 | 42718210 | 54882106 |
| nearest-by-stamp absolute skew | 556 | 0 | 0 | 0 | 0 | 60000000 |
| signed steady receive wait | 556 | -75098358 | -32383555 | -15237908 | -10885418 | 3844969 |
| positive steady receive wait | 1 | 3844969 | 3844969 | 3844969 | 3844969 | 3844969 |

## Pairability evidence

- Nearest-by-stamp candidates: 556; scans with no odom record available at all: 0.
- The latter is trace availability only, **not** evidence that a scan is pairable under a future tolerance.
- Exact stamp matches: 555; nonzero-skew pairs: 1.
- Candidate received before/with scan: 555; after scan (buffer wait needed): 1.

## Tolerance options — not approved

| Status | Option | Tolerance ns | Accepted pairs | Dropped pairs | Temporal-mismatch risk |
| --- | --- | --- | --- | --- |
| PROPOSED_FROM_MEASUREMENT_PENDING_USER_APPROVAL | exact_only | 0 | 555 | 1 | No temporal mismatch accepted; vulnerable to any timestamp phase offset. |
| PROPOSED_FROM_MEASUREMENT_PENDING_USER_APPROVAL | p99_plus_analysis_margin | 1000000 | 555 | 1 | p99 nearest skew plus 1000000 ns analysis margin; must be remeasured under load. |
| PROPOSED_FROM_MEASUREMENT_PENDING_USER_APPROVAL | max_observed | 60000000 | 556 | 0 | Accepts every nearest-by-stamp pair in this trace; largest temporal mismatch is retained. |

## Full nonzero-skew outliers

| Scan stamp ns | Odom stamp ns | Absolute skew ns | Scan receive steady ns | Odom receive steady ns | Signed receive wait ns |
| --- | --- | --- | --- | --- | --- |
| 150100000000 | 150160000000 | 60000000 | 84872417680417 | 84872421525386 | 3844969 |

## Limitations

- Idle Gazebo only; no reset, delay/dropout, CPU contention, or command-motion evidence.
- This report does not select a synchronizer tolerance, receive-age budget, or buffer capacity.
- It is not deploy-real or hardware evidence and does not approve S.2.2A.
