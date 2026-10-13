# WP-04 OIC V3 Nonexecuting Observation-Ingress Source Authorization

## Decision identity

| Field | Value |
|---|---|
| Work package | `WP04-OIC-V3-NONEXECUTING-OBSERVATION-INGRESS-SOURCE-AUTHORIZATION` |
| Change class | `L1_IMPLEMENTATION_SOURCE_AUTHORIZATION_WITHIN_ACTIVE_L2_ENVELOPE` |
| Exact integration/source base | `346138368a5a3599779f36d629c6fc0e0233338a` |
| Architecture authority | `docs/MECANUM_NAV_DRL_Architecture.docx`, SHA-256 `432eeac363a595cfcf7e81c4b66054fb674dba140a2ef3cffecd617ab8136204` |
| Candidate scope | Four governance paths only: this decision, Registry, PEP-001, and one append-only Ledger entry. No source or test files are created or changed. |

## Authority and dependency fingerprints

This decision records the Owner-approved bounded source-level authorization under the active OIC v3 and runtime-binding envelope. The fingerprints below identify inputs; they do not create new authority or infer runtime evidence.

| Authority/evidence | Exact identity and SHA-256 |
|---|---|
| OIC v3 contract source | `docs/OBSERVATION_INPUT_CONTRACT_V3.md` — `d44d33843c32d1f0d5c747522f3add09bfde21fcb0884e21da93a52476cb4dfc` |
| OIC v3 semantic manifest | `docs/architecture/OBSERVATION_INPUT_CONTRACT_V3_SEMANTIC_MANIFEST.json` — `175a1af789b6641cfe455daeee8fedac80aaf80ad8c00792ba0a287c41acc0bb` |
| WP-04 runtime-binding semantic manifest | `docs/architecture/OBSERVATION_RUNTIME_BINDING_V3_SEMANTIC_MANIFEST.json` — `e800f7169304624d81334c26a638c27c9cbaa11a6df0ba5531b1718ee914f76f` |
| WP-05 Navigation V1 runtime-binding ACR | `docs/architecture/ACR_NAVIGATION_V1_RUNTIME_BINDING.md` — `3e74cdcb6136f60a6ad2822a853f2ae9926cf971059f3c2470c874802d6fae0d` |
| WP-05 Navigation V1 runtime-binding semantic manifest | `docs/architecture/NAVIGATION_V1_RUNTIME_BINDING_SEMANTIC_MANIFEST.json` — `33855c9c95f9c0594ddd8805514658e4f5cb8255a219938a7913438470edbf31` |
| Bounded pure-core source candidate, integrated | `16e4d81296f5db0fb322349bfe673cb5bd2c1534` |
| Receipt/QoS | Final-issued receipt v2, QoS6 transport contract and established pins; unchanged. |

## Owner decision and bounded scope

The existing bounded authorization at the source base is `GRANTED_BOUNDED_FAIL_CLOSED_INTERNAL_SEAMS_ONLY`. Subject only to the lifecycle below, this decision extends the source-level scope to creating nonexecuting observation-ingress adapter sources within the existing `mecanum_nav_rl` package:

1. `mecanum_nav_rl` owns those adapter sources and their related static/unit tests.
2. Future source files may be placed only under `ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/observations/` or `ros2_ws/src/mecanum_nav_rl/test/`. Exact files must be pinned in a later code/source-closure candidate. This candidate creates no file in either directory.
3. An adapter may accept a ROS message object as typed input. It must not instantiate a node, executor, subscription, publisher, timer, service/action client, TF lookup/broadcast, launch, or runtime graph.
4. LiDAR target input is `sensor_msgs/msg/LaserScan` from `/scan`, with exact `header.frame_id = lidar_frame`. `RPLiDAR_A1M8_1`, `base_scan`, and every other name are not aliases.
5. LocalReference target input is a Nav2 global path that has already been validated and transformed upstream. The adapter performs no TF lookup and publishes no TF.
6. Measured-twist target input is `nav_msgs/msg/Odometry` from `/odometry/filtered`. The adapter creates no EKF and does not publish `odom → base_link`.
7. Receipt/lifecycle inputs are consumed only as already-valid typed receipt/context. The adapter does not change the ROS receipt interface and does not create or own reset/action barriers.
8. Missing input or any contract-identity, frame, lifecycle-tuple, config-context, type, or validity mismatch fails closed: emit no typed snapshot, no 81D vector, and no fallback.

These target bindings are bounded by the active OIC v3, WP-04 runtime-binding authority, WP-05 Navigation V1 authority where applicable, established receipt v2/QoS6 pins, and frozen Architecture. They do not select a new source file, package/version pin, profile, measurement, or runtime fact.

## Explicit exclusions

This authorization does not permit creating code or tests in this governance candidate. A later source-closure/code candidate must identify exact paths and remain within the two allowed directories. It does not resolve a profile, create global `config_hash`, pin package/version, record a measurement, approve a map, or provide runtime evidence. It grants no ROS graph, launch, ROSIDL/public-interface, runtime, HIL, hardware, deployment, or Gate B authority. WP-05 status is unchanged.

## Status lifecycle

At exact source-base/review snapshot `346138368a5a3599779f36d629c6fc0e0233338a`, before integration of this exact candidate:

```text
CODE_AUTHORIZATION: GRANTED_BOUNDED_FAIL_CLOSED_INTERNAL_SEAMS_ONLY
RUNTIME_APPROVED: NOT_APPROVED
```

Only after independent audit PASS for the exact candidate, separate exact-commit User authorization, fast-forward, and remote-ref verification, the post-integration status becomes:

```text
CODE_AUTHORIZATION: GRANTED_BOUNDED_FAIL_CLOSED_INTERNAL_SEAMS_AND_NONEXECUTING_OBSERVATION_INGRESS_ADAPTER_SOURCES_ONLY
RUNTIME_APPROVED: NOT_APPROVED
```

Review push or Git ancestry alone does not grant the extension. After those four conditions, this is an integrated L1 bounded implementation-source authorization only—not runtime approval, implementation completion, or runtime evidence.

WP-04 remains `BLOCKED_BY_CONTRACT`; Gate A structural primitives remain `PASSED`; Gate B remains `NOT_STARTED`; WP-05 remains `OPEN`. No status transition beyond the conditional code-authorization token above is authorized.
