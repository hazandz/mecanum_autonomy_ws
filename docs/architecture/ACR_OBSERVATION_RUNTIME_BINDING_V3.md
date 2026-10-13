# Architecture Change Record: Observation Runtime Binding V3

| Field | Value |
|---|---|
| Record ID | `ACR-OBSERVATION-RUNTIME-BINDING-V3` |
| Record revision | `1` |
| Change class | `L2_PUBLIC_RUNTIME_INTERFACE_TF_LIFECYCLE_BINDING` |
| Work package | `WP04-OIC-V3-RUNTIME-BINDING-ARCHITECTURE-DECISION` |
| Exact source/integration base | `7e72998c7bc8f9fb0a042672a9444879cd9baedd` |
| Architecture authority | `docs/MECANUM_NAV_DRL_Architecture.docx`; SHA-256 `432eeac363a595cfcf7e81c4b66054fb674dba140a2ef3cffecd617ab8136204`; unchanged and highest authority |
| Source-base status | Review-candidate snapshot; not active at the stated base |
| Target status | After independent audit PASS, separate exact User authorization, fast-forward, and remote-ref verification for the exact candidate: `ACTIVE_L2_RUNTIME_BINDING_TECHNICAL_AUTHORITY_FOR_TARGET_BINDINGS_ONLY` |

## 1. Reason and authority boundary

The active OIC V3 contract and integrated static-reference manifest establish abstract typed contracts and immutable reference groups, but do not select concrete target ROS endpoints and runtime ownership for LiDAR, LocalReference, measured twist, TF, and lifecycle/receipt ingress. This L2 amendment records the Owner-selected target bindings for those public boundaries.

At the exact source base, this ACR and its companion contract/manifest/decision/Registry/PEP/Ledger updates are a review-candidate snapshot. The candidate becomes active L2 runtime-binding technical authority for target bindings only after all four conditions are met for that exact candidate: independent audit PASS, separate exact-commit User authorization, fast-forward to `integration/implementation`, and remote-ref verification. No separate activation candidate is required. Neither audit nor authorization is inferred from Git ancestry.

## 2. Dependencies and immutable fingerprints

The OIC V3 abstract contract remains active at the source base:

- `docs/OBSERVATION_INPUT_CONTRACT_V3.md`, source-file SHA-256 `d44d33843c32d1f0d5c747522f3add09bfde21fcb0884e21da93a52476cb4dfc`.
- `docs/architecture/OBSERVATION_INPUT_CONTRACT_V3_SEMANTIC_MANIFEST.json`, semantic-manifest SHA-256 `175a1af789b6641cfe455daeee8fedac80aaf80ad8c00792ba0a287c41acc0bb`.
- Integrated `docs/governance/evidence/WP-04_OBSERVATION_INPUT_PROFILE_V3_STATIC_REFERENCE_MANIFEST.json`, SHA-256 `639a83454fe9a1e1bf49f98334ba81aa5a78944644d99dfbe599082f4b5918d6`.

Receipt v2 and QoS6 are established pins and are unchanged: receipt interface source SHA-256 `0c6446674bf17373ec646519043f506a9a7a15f95d5fdd10829b0cedb956500a`, receipt dependency-closure SHA-256 `0872fa8c10179f69c2e9e9546392ac734a4f4e94ade176a8be431f06905ecf73`; QoS6 document SHA-256 `4200cd2fbdc81a19400f168dd3526eb7871ac2251049fc7c4f5d5c2fddfd2022`, transport-manifest SHA-256 `338bea1b7350d3b82146c7e728516ec7947471ee68db0f8871ddb72071b79620`. These fingerprints identify separate byte sets and are not changed by this amendment.

## 3. Target runtime bindings

The companion contract `docs/OBSERVATION_RUNTIME_BINDING_V3.md` has source-file SHA-256 `ce2c979788658b45facbabdc3f7063f8663bf71380ab839531afcf7e204173b1`. Its canonical semantic manifest is `docs/architecture/OBSERVATION_RUNTIME_BINDING_V3_SEMANTIC_MANIFEST.json`, semantic-manifest SHA-256 `e800f7169304624d81334c26a638c27c9cbaa11a6df0ba5531b1718ee914f76f`. The source-file digest and semantic-manifest digest have different evidence roles.

| Binding | Target contract |
|---|---|
| LiDAR | ROS type `sensor_msgs/msg/LaserScan`; topic `/scan`; exact header frame `lidar_frame`; future owner `LidarIngressAdapterV3`. `RPLiDAR_A1M8_1`, `base_scan`, `lidar_link`, and legacy variants are `REFERENCE_ONLY_LEGACY`, not aliases. Raw angular scan precedes sectorization; output policy representation remains exactly 72 finite sectors. |
| LocalReference | Future owner `Nav2PlanReferenceAdapterV3`; successful result of `nav2_msgs/action/ComputePathToPose`, carrying `nav_msgs/msg/Path`; path frame exactly `map`; verified TF produces `distance`, `sin_bearing`, `cos_bearing` at `base_link`. No new plan topic is selected. |
| Measured twist | ROS type `nav_msgs/msg/Odometry`; topic `/odometry/filtered`; `header.frame_id == odom`, `child_frame_id == base_link`; one future `robot_localization` EKF publisher. Gazebo `/odom`, simulated odometry, and Ground Truth are excluded as sources. |
| TF ownership | Localization solely owns `map -> odom`; EKF solely owns `odom -> base_link`; `robot_state_publisher` solely owns `base_link -> lidar_frame`. No static-transform workaround between legacy LiDAR aliases. |
| Lifecycle and receipt | `SafetyLifecycle` solely owns action/reset barriers and lifecycle tuple `(episode_generation, reset_epoch, runtime_generation)`. The established receipt v2/QoS6 endpoint remains exact. Future `V3ObservationIngress` uses internal typed ingress context and does not add a `config_hash` field or wrapper to the receipt ROS message. Receipt/input missing, mismatched, pre-barrier, post-cutoff, stale, invalidated, or unverifiable yields no vector. |

## 4. Required evidence and fail-closed behavior

This amendment selects target public interfaces, not executable implementation sources. It does not pin a driver, package version, publisher source, EKF configuration, Nav2 configuration, launch file, adapter/node source, or concrete runtime profile. It does not select geometry/extrinsic, range policy, covariance, timeout, cadence, latency, freshness threshold, skew, buffer limit, or runtime value. Required implementation-source pins remain `PENDING_IMPLEMENTATION_SOURCE_PIN`; required measurement/evidence remains `PENDING_MEASUREMENT`.

Legacy files/hashes in the companion contract and semantic manifest are source-base provenance only. They do not become authority, alias, fallback, or default. Receipt v2/QoS6 remain established; no receipt interface or transport change is made.

If any required implementation pin, source evidence, or measurement is missing or unverifiable, resolution fails closed: no `ObservationInputProfileV3`, no global `ResolvedConfig.config_hash`, and no Gate B bring-up. This amendment neither resolves the profile nor changes the Architecture 16-root global hash, RFC 8785 JCS, `observation.input_profile` location/shape, OIC semantics, or static reference manifest.

## 5. Compatibility, migration, and non-goals

Existing code/config files are not presumed conformant merely because they exist. Future implementation must be separately authorized and establish source pins, compiler rejection behavior, pure-core/adapter boundary, TF and receipt admission, and the applicable offline/runtime evidence. This ACR changes no code, ROSIDL, launch, runtime configuration, receipt v2, QoS6, ACR8, OIC document, OIC semantic manifest, or WP-05/map artifact.

No Gate B start/pass, WP-04 closure, profile resolution, code authorization, runtime/HIL/hardware/deployment approval, or status transition is granted. Status remains WP-04 `BLOCKED_BY_CONTRACT`; Gate A `PASSED`; Gate B `NOT_STARTED`; WP-05 `OPEN`; `CODE_AUTHORIZATION: NOT_GRANTED`; `RUNTIME_APPROVED: NOT_APPROVED`.
