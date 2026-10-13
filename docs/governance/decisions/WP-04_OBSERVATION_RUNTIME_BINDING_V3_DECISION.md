# WP-04 Observation Runtime Binding V3 — Owner Decision Record

| Field | Value |
|---|---|
| Work package | `WP04-OIC-V3-RUNTIME-BINDING-ARCHITECTURE-DECISION` |
| Change class | `L2_PUBLIC_RUNTIME_INTERFACE_TF_LIFECYCLE_BINDING` |
| Exact source/integration base | `7e72998c7bc8f9fb0a042672a9444879cd9baedd` |
| Architecture authority | `docs/MECANUM_NAV_DRL_Architecture.docx`; SHA-256 `432eeac363a595cfcf7e81c4b66054fb674dba140a2ef3cffecd617ab8136204` |
| Candidate authority | At the source base, this record is candidate-only. After exact-candidate independent audit PASS, separate exact User authorization, fast-forward, and remote-ref verification, the candidate becomes active L2 runtime-binding technical authority for target bindings only; no separate activation candidate is required. |
| Technical state | WP-04 `BLOCKED_BY_CONTRACT`; Gate A `PASSED`; Gate B `NOT_STARTED`; WP-05 `OPEN`; `CODE_AUTHORIZATION: NOT_GRANTED`; `RUNTIME_APPROVED: NOT_APPROVED`. |

## Owner decision

The Owner selected five target runtime bindings for the public OIC V3 ingress boundary. They define target types/endpoints, frame ownership and adapter ownership, but do not select executable source files, package versions, driver/config/launch pins, or runtime evidence.

| Group | Owner-selected target binding |
|---|---|
| LiDAR | `sensor_msgs/msg/LaserScan` on `/scan`; `header.frame_id` must equal exactly `lidar_frame`; future owner `LidarIngressAdapterV3`. `RPLiDAR_A1M8_1`, `base_scan`, `lidar_link`, and legacy variants are `REFERENCE_ONLY_LEGACY`, never aliases. Raw angular scan precedes sectorization; the output remains exactly 72 finite sectors. |
| LocalReference | Future owner `Nav2PlanReferenceAdapterV3`; successful `nav2_msgs/action/ComputePathToPose` result carrying `nav_msgs/msg/Path`, with path frame exactly `map`. Verified TF expresses the reference at `base_link` as `distance`, `sin_bearing`, `cos_bearing`. No new plan topic; simulation goal/odometry is not a runtime source. |
| Measured twist | `nav_msgs/msg/Odometry` on `/odometry/filtered`; `header.frame_id == odom`, `child_frame_id == base_link`; one future `robot_localization` EKF publisher. Gazebo `/odom`, simulated odometry, and Ground Truth are not eligible. |
| TF | Localization is sole owner of `map -> odom`; one EKF is sole owner of `odom -> base_link`; `robot_state_publisher` is sole owner of `base_link -> lidar_frame`. No static-transform workaround between legacy LiDAR aliases. |
| Lifecycle/receipt | `SafetyLifecycle` solely owns action/reset barriers and lifecycle tuple `(episode_generation, reset_epoch, runtime_generation)`. Established final-issued receipt v2/QoS6 endpoint is retained. Future `V3ObservationIngress` uses internal typed ingress context; no receipt ROS field/wrapper is added for `config_hash`. Missing, mismatched, pre-barrier, post-cutoff, stale, or unverifiable input/receipt yields no vector. |

The runtime-binding contract is `docs/OBSERVATION_RUNTIME_BINDING_V3.md`, source-file SHA-256 `ce2c979788658b45facbabdc3f7063f8663bf71380ab839531afcf7e204173b1`. Its canonical semantic manifest is `docs/architecture/OBSERVATION_RUNTIME_BINDING_V3_SEMANTIC_MANIFEST.json`, semantic-manifest SHA-256 `e800f7169304624d81334c26a638c27c9cbaa11a6df0ba5531b1718ee914f76f`. The document source hash and manifest semantic digest identify different byte sets and must not be conflated.

## Authority and unchanged dependencies

At source base `7e72998c7bc8f9fb0a042672a9444879cd9baedd`, OIC V3 abstract typed-boundary authority remains active: source `docs/OBSERVATION_INPUT_CONTRACT_V3.md`, source-file SHA-256 `d44d33843c32d1f0d5c747522f3add09bfde21fcb0884e21da93a52476cb4dfc`; semantic manifest `docs/architecture/OBSERVATION_INPUT_CONTRACT_V3_SEMANTIC_MANIFEST.json`, SHA-256 `175a1af789b6641cfe455daeee8fedac80aaf80ad8c00792ba0a287c41acc0bb`. The integrated seven-group static-reference manifest is `docs/governance/evidence/WP-04_OBSERVATION_INPUT_PROFILE_V3_STATIC_REFERENCE_MANIFEST.json`, SHA-256 `639a83454fe9a1e1bf49f98334ba81aa5a78944644d99dfbe599082f4b5918d6`.

Receipt v2 and QoS6 remain established pins, not pending and not changed here. Receipt interface source SHA-256 is `0c6446674bf17373ec646519043f506a9a7a15f95d5fdd10829b0cedb956500a`, receipt dependency closure SHA-256 is `0872fa8c10179f69c2e9e9546392ac734a4f4e94ade176a8be431f06905ecf73`; QoS6 document SHA-256 is `4200cd2fbdc81a19400f168dd3526eb7871ac2251049fc7c4f5d5c2fddfd2022`, transport-manifest SHA-256 is `338bea1b7350d3b82146c7e728516ec7947471ee68db0f8871ddb72071b79620`.

No change is made to the OIC abstract contract, OIC semantic manifest, static reference manifest, receipt v2, QoS6, global Architecture 16-root `ResolvedConfig.config_hash` policy, or nested `observation.input_profile` semantics. The receipt schema is not extended with a `config_hash` member or wrapper.

## Legacy provenance — source-base bytes only

The following exact source-base files are recorded only to recognize possible legacy/configuration conflicts. Their hashes do not make them runtime authority, selected implementation pins, aliases, or defaults:

| Source-base path | SHA-256 | Boundary |
|---|---|---|
| `ros2_ws/src/mecanum_nav_rl/config/v3/frames.yaml` | `815bff5df49f6de07a48e61275a21c728904ff699b771a0c970507483d0ff9da` | Architecture-intent input only; no inferred frame contract ID, alias, geometry, or digest. |
| `ros2_ws/src/mecanum_nav_rl/config/v3/topics.yaml` | `7dc2156aef44e83ca767528774fff6acd543814be3a0d9eb0b6373c4f5217a2d` | Architecture-intent input only; no inferred topic/QoS or freshness authority. |
| `ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/observations/lidar.py` | `9422bfb38bb56140114792662f25ca7019ab95c1d4af1471dd4b3f874deedb8a` | Pure 72-sector algorithm provenance only, not LiDAR runtime snapshot or ROS ingress contract. |
| `ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/observations/goal_features.py` | `2f6e966bf1f5969536128dc2aef24aa47be3e0e16b0994e862ce971349437ed8` | Simulation/provenance only, not LocalReference runtime authority. |
| `ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/observations/measured_twist.py` | `a11f7eeea3db6539b6ee35633666f4a2e00b9ced174e02edc67163d546529e1a` | Simulation/provenance only, not measured-twist runtime authority. |
| `ros2_ws/src/ROBOT_URDF_final_description/urdf/ROBOT_URDF_final.xacro` | `7a8f72894d024598f908b12b5a867c4c90e7e6ba167d9130e3e941e0129b5477` | Robot-description provenance only; no measured physical extrinsic/alignment evidence. |
| `ros2_ws/src/ROBOT_URDF_final_description/urdf/ROBOT_URDF_final.gazebo` | `6c7d0b9e90c2ed87a1de7aaf83b2c3ad07a897b5b1d1b2d26737054020d3f0fc` | Gazebo provenance only, not runtime source or measurement evidence. |
| `ros2_ws/src/ROBOT_URDF_final_description/launch/gazebo.launch.py` | `2f0e2b329b4ad600e777a4a1b0578f3cc08fd9aea3a93705875e7a5afddae325` | Legacy launch provenance only; no selected runtime launch pin. |
| `ros2_ws/src/ROBOT_URDF_final_description/config/nav2_params.yaml` | `26c37806f98e131e5993672122dee7efc5a4de1011f0bcb69e4c3a6e273ef4af` | Legacy configuration provenance only; no selected planner/profile source pin. |
| `ros2_ws/src/ROBOT_URDF_final_description/launch/nav2_bringup.launch.py` | `97f70679cb107411e882e387a49c87ec80243c3fa43d70846083f8be1b3e143e` | Legacy launch provenance only; no selected runtime launch pin. |

## Pending evidence and fail-closed rule

This decision selects no driver or package version, EKF/Nav2 config, launch/source closure, adapter implementation source, concrete profile, geometry/extrinsic, range policy, cadence, latency, covariance, timeout, freshness, skew, buffer limit, or runtime measurement. Such required implementation pins remain `PENDING_IMPLEMENTATION_SOURCE_PIN`; physical/timing/validity evidence remains `PENDING_MEASUREMENT`. No static reference, legacy source, simulation source, alias, default, or fabricated value may resolve a pending item.

If any required pin, source, measurement, or evidence is absent or unverifiable, the future compiler fails closed: no `ObservationInputProfileV3` resolution, no global `config_hash`, and no Gate B bring-up. Runtime publisher uniqueness, TF alignment/freshness, QoS delivery, receipt timing, and adapter behavior require their own allowed future evidence; none is established by this documentation candidate.

## Activation and non-goals

At the exact source base, this record is candidate-only and does not change active authority. After the exact candidate passes independent audit, receives separate exact-commit User authorization, is fast-forwarded, and its remote ref is verified, this L2 target-binding decision becomes active technical authority for the five target bindings only. It does not create a concrete profile or implementation pin and does not require another activation candidate.

No Gate B start/pass, WP-04 closure, code authorization, ROS/ROSIDL implementation authorization, runtime/HIL/hardware/deployment approval, profile resolution, or status transition is granted. WP-04 remains `BLOCKED_BY_CONTRACT`; Gate A remains `PASSED`; Gate B remains `NOT_STARTED`; WP-05 remains `OPEN`; `CODE_AUTHORIZATION: NOT_GRANTED`; `RUNTIME_APPROVED: NOT_APPROVED`.
