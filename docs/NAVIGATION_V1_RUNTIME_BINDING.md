# Navigation V1 Runtime Binding — Target Contract

**Work package:** `WP05-NAVIGATION-V1-RUNTIME-BINDING-ARCHITECTURE-DECISION`<br>
**Architecture authority:** `docs/MECANUM_NAV_DRL_Architecture.docx`, SHA-256 `432eeac363a595cfcf7e81c4b66054fb674dba140a2ef3cffecd617ab8136204`<br>
**Companion ACR:** `docs/architecture/ACR_NAVIGATION_V1_RUNTIME_BINDING.md`

## 1. Scope and state

This document specifies five L2 target-binding groups for a future Navigation V1 profile. It is not an executable profile, source selection, source pin, map approval, runtime approval, or evidence of a running ROS graph. The candidate is not active at its source base. After independent audit PASS for the exact candidate, separate explicit User authorization for that exact commit, fast-forward, and remote-ref verification, it becomes `ACTIVE_L2_NAVIGATION_V1_RUNTIME_BINDING_TECHNICAL_AUTHORITY_FOR_TARGET_BINDINGS_ONLY`; no separate activation candidate is required.

The Authority at all times is subject to the Architecture DOCX. The integrated WP-04 L2 authority supplies only the direct shared scan/TF/lifecycle target dependency described in §3. It does not select WP-05 executable source files or runtime pins.

## 2. Terminology

- **Target binding:** Owner-selected interface/ownership constraint; it does not assert implementation or runtime conformance.
- **Implementation source pin:** Exact immutable Git source identity (full commit, repository-relative path, SHA-256) or explicitly approved exact package/version evidence for an external package.
- **Pending:** Required information is absent, unselected, or not verified; no default or inference is permitted.
- **Resolved profile:** A future complete, internally consistent, immutable static source/value closure bound to the exact map subject and with a valid Architecture-defined complete `ResolvedConfig.config_hash`. No partial profile/hash exists.

## 3. Target bindings

### 3.1 Map artifact

Map Server input is confined to `artifacts/maps/<map_id>/`. A resolved profile must bind the exact artifact path, `map_id`, `artifact_identity`, and `map_content_hash`, and pass the Architecture §48 artifact identity/hash/path checks. ROS package/source-tree map copies are not eligible. `warehouse_map2` currently exists as an integration-resident draft artifact; it is not approved, selected for navigation/localization, or navigation-ready. A target binding to it does not approve it.

The payload hash boundary stays exactly the Architecture §48 RFC 8785 projection of `map.yaml` then `map.pgm`. `metadata.yaml`, `map_manifest.json`, evidence, pose graph, result fields, and the resulting hash remain outside that payload.

### 3.2 Localization / AMCL

In `NAV2_BASELINE`, AMCL is the sole target owner for `map → odom`, with `robot_model_type=nav2_amcl::OmniMotionModel`. SLAM Toolbox is restricted to `MAPPING`; it must not concurrently act as localization or publish `map → odom` in `NAV2_BASELINE` or `HYBRID_AI_LOCAL`. Parameter values, AMCL config, package version, launch composition, covariance, tolerances, particle count, and runtime evidence are not selected here.

### 3.3 EKF odometry

One `robot_localization` EKF is the sole target owner for `odom → base_link`. It consumes target inputs `/wheel/odometry_raw` and `/imu/data`, and emits `/odometry/filtered` as `nav_msgs/msg/Odometry` with `header.frame_id=odom` and `child_frame_id=base_link`. Gazebo `/odom`, simulated odometry, and Ground Truth are not substitutes for this target runtime input. No EKF source/config/package pin or concrete filter/covariance/timing value is selected.

### 3.4 LiDAR, TF, and remapping

The target scan endpoint is `/scan`, type `sensor_msgs/msg/LaserScan`, and exact `header.frame_id=lidar_frame`. `robot_state_publisher` is the sole target owner for `base_link → lidar_frame`. There is no implicit alias among `lidar_frame`, `RPLiDAR_A1M8_1`, `base_scan`, `rplidar_link`, or variants. No static-transform workaround is permitted to conceal a mismatch. Exact remap and namespace tables must be selected and pinned in a future profile; legacy launch remaps do not resolve them.

### 3.5 Lifecycle and startup

Use the Architecture §49 order: robot description → drivers/bridge → EKF → Map Server → AMCL → healthy LocalizationMonitor → Planner/global costmap → Safety → selected controller/manager → mission acceptance. Every downstream motion source remains inhibited until all upstream lifecycle and contract health checks are healthy. Map Server, AMCL, EKF, and Nav2 each require an explicit lifecycle contract and pinned implementation source before bring-up. A legacy `autostart` setting alone does not meet this condition.

## 4. Required source pins and measurements

All items below remain `PENDING_IMPLEMENTATION_SOURCE_PIN` until selected and pinned:

1. Nav2, AMCL, Map Server, `robot_localization`, and bridge package/version/dependency closure.
2. Map Server, AMCL, EKF and Nav2 config files, exact launch composition, and package ownership.
3. Complete AMCL parameter set; complete EKF configuration and input-source closure.
4. Canonical scan/TF adapter source; base-to-sensor geometry source; explicit remap/namespace policy.
5. Lifecycle/startup implementation, per-component lifecycle contracts, health gates, and inhibition source.
6. Complete profile closure and Architecture-defined global `ResolvedConfig.config_hash`.

The following remain `PENDING_MEASUREMENT`: TF alignment and unique actual publishers; actual scan header frame/cadence/latency/freshness; EKF output/freshness/covariance; lifecycle health; localization quality; map/runtime compatibility. Missing or conflicting required pins/evidence fail closed. No profile is resolved, no profile hash is emitted, and no bring-up is allowed by this document.

## 5. Evidence classes

**Offline/static:** Git-pinned source bytes, selected package versions, schema consistency, exact map identity/hash, declared frame names, explicit remaps, and declared lifecycle/source closure can be checked statically. Static evidence does not prove runtime behavior.

**Runtime:** actual TF graph and publisher uniqueness, observed `/scan` header frame, selected source/package versions in use, map loading and loaded identity/hash, AMCL localization freshness/quality, EKF output/freshness, remap/topic graph, lifecycle health, startup inhibition, and compatibility require a separately authorized runtime work package. This document records none of them as observed.

Map approval, world-frame validation, runtime compatibility, profile resolution, Gate B, and code/runtime authorization remain independent. The current map remains `approval_status: draft`, `world_frame: NOT_DECLARED`, and `runtime_compatibility: NOT_VALIDATED`. No equivalence, transform, alignment, approval, or navigation-ready claim follows from the target binding.

## 6. Source-base inventory (provenance only)

At exact base `5249a11e69408abf845e8568258989a70edefb35`, the following legacy files are recorded only as `REFERENCE_ONLY_LEGACY`; their hashes do not make them selected pins or authority:

| Path | SHA-256 |
|---|---|
| `ros2_ws/src/ROBOT_URDF_final_description/config/nav2_params.yaml` | `26c37806f98e131e5993672122dee7efc5a4de1011f0bcb69e4c3a6e273ef4af` |
| `ros2_ws/src/ROBOT_URDF_final_description/launch/nav2_bringup.launch.py` | `97f70679cb107411e882e387a49c87ec80243c3fa43d70846083f8be1b3e143e` |
| `ros2_ws/src/ROBOT_URDF_final_description/config/mapper_params_online_async.yaml` | `8e363a5e141cb275f201ea78b84f2816b5b56c087a2435b2bd4f094fbd150c7a` |
| `ros2_ws/src/ROBOT_URDF_final_description/launch/slam.launch.py` | `28bf46d825fdcdaf79081897d1f0933dcf6946b4df17008c5a158563d03fe728` |
| `ros2_ws/src/ROBOT_URDF_final_description/config/ros_gz_bridge_gazebo.yaml` | `374eb90b302cc1968ab84617d3f61f9954e2665f32982c3867e352c238433feb` |
| `ros2_ws/src/ROBOT_URDF_final_description/launch/gazebo.launch.py` | `2f0e2b329b4ad600e777a4a1b0578f3cc08fd9aea3a93705875e7a5afddae325` |
| `ros2_ws/src/ROBOT_URDF_final_description/urdf/ROBOT_URDF_final.gazebo` | `6c7d0b9e90c2ed87a1de7aaf83b2c3ad07a897b5b1d1b2d26737054020d3f0fc` |

V3 `frames.yaml`, `topics.yaml`, and `modes/nav2_baseline.yaml` are contract/intention inputs only. Xacro/SDF are geometry/provenance only. None is an executable profile, alias authority, or runtime evidence. No tracked `mecanum_nav_bringup` profile config or exact Nav2/AMCL/Map Server/EKF package-version lock exists at this base.
