# Timing Evidence Report — Multi-Run

Execution timestamp UTC: 2026-09-22T08:44:23.067927+00:00

## Scope

- 6 independent idle-Gazebo captures. Collector subscribed only to `/scan` and `/odom`.
- No `/cmd_vel`, reset, teleop, entity/service control, UART, or hardware operation was issued.
- All numeric options below are `PROPOSED_FROM_MEASUREMENT_PENDING_USER_APPROVAL`.

## Per-run summary

| Run | Duration ns | Scan | Odom | Odom/scan rate | Exact pairs | Nonzero skew | Skew p95 ns | Skew p99 ns | Skew max ns | Positive wait p99 ns |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| run_01 | 60000119412 | 553 | 2759 | 4.991966732708534 | 551 | 2 | 0 | 0 | 140000000 | 19088869 |
| run_02 | 60005962111 | 544 | 2716 | 4.994662811416674 | 543 | 1 | 0 | 0 | 100000000 | 19625389 |
| run_03 | 60006348016 | 583 | 2912 | 4.999196386486483 | 582 | 1 | 0 | 0 | 60000000 | 10378867 |
| run_04 | 60007639843 | 575 | 2876 | 4.999397128879979 | 574 | 1 | 0 | 0 | 20000000 | None |
| run_05 | 60015732485 | 584 | 2923 | 5.000465936834757 | 584 | 0 | 0 | 0 | 0 | None |
| run_06 | 60016713377 | 580 | 2895 | 4.992842677543601 | 579 | 1 | 0 | 0 | 100000000 | 964808 |

## Aggregate pairing evidence

- Aggregate nearest-by-stamp skew: `{"count": 3419, "max": 140000000, "min": 0, "p50": 0, "p95": 0, "p99": 0}`.
- Aggregate positive receive wait: `{"count": 5, "max": 19625389, "min": 964808, "p50": 18318743, "p95": 19625389, "p99": 19625389}`.
- Nonzero-skew occurrence: 6/3419 (0.1755%).
- 60 ms skew occurrence: 1 pair(s) across 1 of 6 runs (0.0292% of nearest-by-stamp pairs).
- Interpretation: The 60 ms outlier occurred in one run only and is rare in this set.
- Exact-only pairing accepts only exact stamp pairs; any nonzero skew is dropped, so exact-only is not robust whenever nonzero skew occurs.

## Aggregate tolerance options — not approved

| Status | Option | Tolerance ns | Accepted pairs | Dropped pairs | Temporal-mismatch risk |
| --- | --- | --- | --- | --- |
| PROPOSED_FROM_MEASUREMENT_PENDING_USER_APPROVAL | exact_only | 0 | 3413 | 6 | No temporal mismatch accepted; vulnerable to any timestamp phase offset. |
| PROPOSED_FROM_MEASUREMENT_PENDING_USER_APPROVAL | p99_plus_analysis_margin | 1000000 | 3413 | 6 | p99 nearest skew plus 1000000 ns analysis margin; must be remeasured under load. |
| PROPOSED_FROM_MEASUREMENT_PENDING_USER_APPROVAL | max_observed | 140000000 | 3419 | 0 | Accepts every nearest-by-stamp pair in this trace; largest temporal mismatch is retained. |

## Aggregate nonzero-skew outliers

| Run | Scan stamp ns | Odom stamp ns | Absolute skew ns | Signed receive wait ns |
| --- | --- | --- | --- | --- |
| run_01 | 12000000000 | 12140000000 | 140000000 | 19088869 |
| run_01 | 12100000000 | 12140000000 | 40000000 | 18318743 |
| run_02 | 90100000000 | 90200000000 | 100000000 | 19625389 |
| run_03 | 210200000000 | 210260000000 | 60000000 | 10378867 |
| run_04 | 310700000000 | 310720000000 | 20000000 | -387196 |
| run_06 | 489300000000 | 489400000000 | 100000000 | 964808 |

## Evidence still required before approval

- Repeat under reset, simulator delay/dropout, CPU contention, and command-motion scenarios.
- Decide receive-age budgets and buffer capacities separately; this report does not approve them.
- Gazebo timing is not deploy-real or hardware evidence.
