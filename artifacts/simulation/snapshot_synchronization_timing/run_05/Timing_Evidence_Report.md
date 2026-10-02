# Snapshot Synchronization Timing Evidence

Execution timestamp UTC: 2026-09-22T08:44:23.056707+00:00

## Scope

- Collector subscriptions only: `/scan` and `/odom`; no publisher, `/cmd_vel`, reset, or service-control operation.
- Header (ROS/simulation) stamps and steady receive times remain separate time domains.
- Capture duration steady ns: 60015732485; scans: 584; odometry: 2923.

## Stream and pair statistics (nanoseconds)

| Metric | Count | Min | P50 | P95 | P99 | Max |
| --- | --- | --- | --- | --- | --- | --- |
| scan ROS stamp interval | 583 | 100000000 | 100000000 | 100000000 | 100000000 | 100000000 |
| scan steady receive inter-arrival | 583 | 70421589 | 101501474 | 119444887 | 129792994 | 139362839 |
| odom ROS stamp interval | 2922 | 20000000 | 20000000 | 20000000 | 20000000 | 20000000 |
| odom steady receive inter-arrival | 2922 | 5418365 | 20162343 | 27449564 | 34141612 | 47011284 |
| nearest-by-stamp absolute skew | 584 | 0 | 0 | 0 | 0 | 0 |
| signed steady receive wait | 584 | -57743150 | -27216010 | -13281776 | -9622123 | -7038759 |
| positive steady receive wait | 0 | None | None | None | None | None |

## Pairability evidence

- Nearest-by-stamp candidates: 584; scans with no odom record available at all: 0.
- The latter is trace availability only, **not** evidence that a scan is pairable under a future tolerance.
- Exact stamp matches: 584; nonzero-skew pairs: 0.
- Candidate received before/with scan: 584; after scan (buffer wait needed): 0.

## Tolerance options — not approved

| Status | Option | Tolerance ns | Accepted pairs | Dropped pairs | Temporal-mismatch risk |
| --- | --- | --- | --- | --- |
| PROPOSED_FROM_MEASUREMENT_PENDING_USER_APPROVAL | exact_only | 0 | 584 | 0 | No temporal mismatch accepted; vulnerable to any timestamp phase offset. |
| PROPOSED_FROM_MEASUREMENT_PENDING_USER_APPROVAL | p99_plus_analysis_margin | 1000000 | 584 | 0 | p99 nearest skew plus 1000000 ns analysis margin; must be remeasured under load. |
| PROPOSED_FROM_MEASUREMENT_PENDING_USER_APPROVAL | max_observed | 0 | 584 | 0 | Accepts every nearest-by-stamp pair in this trace; largest temporal mismatch is retained. |

## Full nonzero-skew outliers

No nonzero nearest-by-stamp skew occurred in this capture.

## Limitations

- Idle Gazebo only; no reset, delay/dropout, CPU contention, or command-motion evidence.
- This report does not select a synchronizer tolerance, receive-age budget, or buffer capacity.
- It is not deploy-real or hardware evidence and does not approve S.2.2A.
