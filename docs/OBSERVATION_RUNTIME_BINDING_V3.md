# Observation Runtime Binding V3

**Document revision:** `1`
**Change class:** `L2_PUBLIC_RUNTIME_INTERFACE_TF_LIFECYCLE_BINDING`
**Source-base snapshot:** `7e72998c7bc8f9fb0a042672a9444879cd9baedd`
**Status at source base:** review candidate; not yet active runtime-binding authority
**Semantic manifest:** `docs/architecture/OBSERVATION_RUNTIME_BINDING_V3_SEMANTIC_MANIFEST.json`
**Semantic-manifest SHA-256:** `e800f7169304624d81334c26a638c27c9cbaa11a6df0ba5531b1718ee914f76f`

This document records the Owner-selected target ROS endpoints, adapter ownership, TF ownership, and lifecycle/receipt binding for the OIC V3 boundary. It is an L2 technical contract candidate, not an implementation or concrete immutable runtime source pin. The semantic manifest identifies these binding semantics; it does not identify executable source bytes, a resolved profile, or runtime evidence.

## 1. Authority and activation

The frozen Architecture remains highest authority. OIC V3 remains the active abstract typed-boundary contract at source base `7e72998c7bc8f9fb0a042672a9444879cd9baedd`, identified by source-file SHA-256 `d44d33843c32d1f0d5c747522f3add09bfde21fcb0884e21da93a52476cb4dfc` and semantic-manifest SHA-256 `175a1af789b6641cfe455daeee8fedac80aaf80ad8c00792ba0a287c41acc0bb`. The integrated static reference manifest is `docs/governance/evidence/WP-04_OBSERVATION_INPUT_PROFILE_V3_STATIC_REFERENCE_MANIFEST.json`, SHA-256 `639a83454fe9a1e1bf49f98334ba81aa5a78944644d99dfbe599082f4b5918d6`. Receipt v2 and QoS6 remain established and unchanged.

At the exact source base, this document and its companion ACR/manifest/decision are review-candidate snapshots. After independent audit PASS, separate exact-commit User authorization, fast-forward, and remote-ref verification for this exact candidate, the candidate becomes active L2 runtime-binding technical authority for the target bindings recorded here. No separate activation candidate is required. This activation does not implement an adapter, resolve a profile, start/pass Gate B, or grant code/runtime authorization.

## 2. Target binding contract

### 2.1 LiDAR ingress

- Target ROS type: `sensor_msgs/msg/LaserScan`.
- Target topic: `/scan`.
- `header.frame_id` must equal exactly `lidar_frame`; no alias or implicit remap is admitted by this contract.
- Future ingress owner: `LidarIngressAdapterV3`.
- The input is the raw angular scan before sectorization; OIC V3 observation output remains exactly 72 finite sectors.
- `RPLiDAR_A1M8_1`, `base_scan`, `lidar_link`, and legacy variants are `REFERENCE_ONLY_LEGACY`, not aliases.

This is a target interface decision, not a selected driver, package version, executable source pin, or runtime validation. Range, cadence, latency, freshness, buffer/timeout, and physical geometry/extrinsic remain pending evidence/measurement.

### 2.2 LocalReference ingress

- Future owner: `Nav2PlanReferenceAdapterV3`.
- Source event: successful result of `nav2_msgs/action/ComputePathToPose`, carrying `nav_msgs/msg/Path`.
- The path header frame must be exactly `map`.
- The adapter uses verified TF to express LocalReference in `base_link` and produces `distance`, `sin_bearing`, and `cos_bearing`.
- No new plan topic is selected. Simulation goal/odometry sources are not runtime sources.

The target input/action type and frames do not select a concrete Nav2 package/version, planner configuration, launch source, path-provider implementation, transform evidence, or freshness value.

### 2.3 Measured-twist ingress

- Target ROS type: `nav_msgs/msg/Odometry`.
- Target topic: `/odometry/filtered`.
- Required `header.frame_id`: `odom`; required `child_frame_id`: `base_link`.
- Future owner: one `robot_localization` EKF publisher only.
- Gazebo `/odom`, simulated odometry, and Ground Truth are not eligible runtime sources.

This selects no EKF configuration, package version, launch/source pin, covariance policy, validity bound, freshness threshold, or measurement. Invalid/unverified values fail closed; no clipping, zero-fill, or fallback is introduced.

### 2.4 TF ownership

The target sole owners are:

| TF edge | Target sole owner |
|---|---|
| `map -> odom` | selected localization provider |
| `odom -> base_link` | one `robot_localization` EKF |
| `base_link -> lidar_frame` | `robot_state_publisher` |

No static-transform workaround between legacy LiDAR aliases is permitted. The contract does not prove runtime publisher uniqueness, physical alignment, extrinsic, transform freshness, or selected profile-specific source files.

### 2.5 Lifecycle and final-issued receipt

- `SafetyLifecycle` is the sole owner of action/reset barriers and the lifecycle tuple `(episode_generation, reset_epoch, runtime_generation)`.
- The established receipt v2/QoS6 endpoint remains `/mecanum/final_issued_command` with type `mecanum_nav_rl_interfaces/msg/FinalIssuedCommandReceipt`; existing publisher/subscriber and transport authority remain unchanged.
- Future `V3ObservationIngress` binds the applicable global `config_hash` through an internal typed ingress context. No `config_hash` field or wrapper is added to the receipt ROS message.
- A receipt is eligible only when it matches the lifecycle tuple and global configuration binding exactly, is strictly after the applicable action and reset barriers, and is not later than the observation cutoff.
- Missing, mismatched, pre-barrier, post-cutoff, stale, invalidated, or unverifiable receipt/input yields non-ready/no-vector under existing authority; no new status is introduced.

Barrier occurrences, lifecycle values, timestamps, sequence values, receipt instances/payloads, freshness results, and live QoS delivery are runtime facts—not static profile/config-hash values.

## 3. Immutable legacy provenance, not source authority

The SHA-pinned files listed in the semantic manifest are recorded only to identify existing legacy, simulation, pure-algorithm, or architecture-intent evidence at the source base. They are not selected runtime source pins, canonical owners, operational endpoints, proof of live behavior, or defaults. In particular, `frames.yaml`, `topics.yaml`, the listed observation modules, URDF/Gazebo files, and legacy launch/config files cannot override this decision or silently supply a missing runtime pin.

## 4. Pending source pins, measurements, and fail-closed rule

Still unselected are driver/source files, package/version locks, EKF and Nav2 configuration/launch source closure, adapter/node implementation source, and a concrete immutable `ObservationInputProfileV3` instance. Still pending are LiDAR range/cadence/latency/freshness/extrinsic, scan-to-twist synchronization/skew, measured-twist validity/covariance/freshness/provenance, TF alignment/freshness/publisher evidence, and lifecycle/receipt timeout measurements. No value is inferred from legacy or simulation provenance.

If any required implementation source pin, measurement, or evidence is missing or unverifiable, the future compiler must fail closed: no profile resolution, no global `config_hash`, and no Gate B bring-up. `PENDING_MEASUREMENT` remains pending. No default, alias, legacy source, simulation source, Ground Truth, or coercion can substitute.

## 5. Acceptance boundary and status

The semantic manifest is `docs/architecture/OBSERVATION_RUNTIME_BINDING_V3_SEMANTIC_MANIFEST.json`; its canonical JCS SHA-256 is `e800f7169304624d81334c26a638c27c9cbaa11a6df0ba5531b1718ee914f76f`. This candidate changes no receipt v2/QoS6 bytes, OIC v3 semantics, static-reference manifest, global 16-root config-hash policy, or `observation.input_profile` shape. The contract does not claim implementation, runtime graph, TF/QoS verification, measurements, or adapter acceptance evidence.

At source base `7e72998c7bc8f9fb0a042672a9444879cd9baedd`, this is a review snapshot. After the exact candidate satisfies independent audit PASS, separate exact User authorization, fast-forward, and remote-ref verification, it is the active L2 runtime-binding technical authority for the target bindings only; implementation source pins and measurements remain separately pending. WP-04 remains `BLOCKED_BY_CONTRACT`; Gate A is `PASSED`; Gate B remains `NOT_STARTED`; WP-05 remains `OPEN`; `CODE_AUTHORIZATION: NOT_GRANTED`; `RUNTIME_APPROVED: NOT_APPROVED`.
