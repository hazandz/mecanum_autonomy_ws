# WP-05 — Navigation V1 L2 runtime-binding decision

| Field | Value |
|---|---|
| Work package | `WP05-NAVIGATION-V1-RUNTIME-BINDING-ARCHITECTURE-DECISION` |
| Change class | `L2_PUBLIC_RUNTIME_INTERFACE_TF_LIFECYCLE_BINDING` |
| Exact integration base | `16e4d81296f5db0fb322349bfe673cb5bd2c1534` |
| Architecture authority | `docs/MECANUM_NAV_DRL_Architecture.docx`; SHA-256 `432eeac363a595cfcf7e81c4b66054fb674dba140a2ef3cffecd617ab8136204` |
| Companion ACR / contract / manifest | `docs/architecture/ACR_NAVIGATION_V1_RUNTIME_BINDING.md`; `docs/NAVIGATION_V1_RUNTIME_BINDING.md`; `docs/architecture/NAVIGATION_V1_RUNTIME_BINDING_SEMANTIC_MANIFEST.json` |
| Candidate state at base | Review candidate; pending independent audit and separate User authorization for exact candidate |
| WP-05 | `OPEN` |

## 1. Decision and scope

This refreshed candidate is based directly on `16e4d81296f5db0fb322349bfe673cb5bd2c1534`. The prior review commit `4ff6b96783c940e7f4c523ed553d3ad75f8a5a55` on `wp05-navigation-v1-runtime-binding-architecture-5249a11` (direct parent `5249a11e69408abf845e8568258989a70edefb35`) is source-content/provenance only, not the current candidate/base and not integrated by this refresh. This candidate records the Owner's L2 target-binding decision for a future Navigation V1 profile. No executable Navigation V1 profile is canonical at the exact base. It does not choose a canonical executable profile or runtime source, resolve any pending field, create a profile/config hash, approve a map, validate world/frame alignment, or authorize bring-up. Architecture DOCX remains the highest authority. Existing files and their hashes remain evidence/provenance unless expressly selected and pinned in a later decision.

After independent audit PASS for the exact final candidate, separate explicit User authorization for that exact commit, fast-forward, and remote-ref verification, that exact candidate becomes `ACTIVE_L2_NAVIGATION_V1_RUNTIME_BINDING_TECHNICAL_AUTHORITY_FOR_TARGET_BINDINGS_ONLY`. No separate activation candidate is required. Candidate integration does not resolve the profile, select source pins, approve `warehouse_map2`, validate runtime compatibility/world frame, start/pass Gate B, or close WP-05.

## 2. Recorded target bindings

| Group | Binding recorded by this Owner decision | Still pending |
|---|---|---|
| Map artifact | Map Server reads only `artifacts/maps/<map_id>/`; future profile binds exact map path, `map_id`, `artifact_identity`, `map_content_hash`. No ROS package map copy. | `warehouse_map2` is draft, not selected or navigation-approved; no profile subject is activated. Map approval remains separate. |
| Localization / AMCL | `NAV2_BASELINE` provider AMCL with `nav2_amcl::OmniMotionModel`; AMCL is sole target owner `map → odom`. SLAM Toolbox is `MAPPING` only and must not concurrently localize/publish this edge in Navigation modes. | AMCL params, package/version, source/launch, particle/covariance/tolerance values and runtime proof. |
| EKF odometry | One `robot_localization` EKF is sole target owner `odom → base_link`; inputs `/wheel/odometry_raw`, `/imu/data`; output `/odometry/filtered` as `nav_msgs/msg/Odometry`, `odom`/`base_link`. Simulated `/odom` and Ground Truth are excluded. | EKF configuration, package/version, exact sources, covariance/timing and runtime freshness. |
| LiDAR / TF / remap | `/scan`, `sensor_msgs/msg/LaserScan`, exact `header.frame_id=lidar_frame`; `robot_state_publisher` sole target owner `base_link → lidar_frame`. No alias among `RPLiDAR_A1M8_1`, `base_scan`, `rplidar_link`, or variants; no static-transform workaround. | Adapter/geometry source pin, explicit profile-specific namespace/remap policy, actual header and TF evidence. |
| Lifecycle / startup | Architecture §49 order and health/inhibition gates govern future bring-up. Each of Map Server, AMCL, EKF, Nav2 needs its own lifecycle contract/source pin. Legacy `autostart` alone is insufficient. | Executable startup/lifecycle pins and runtime health/inhibition evidence. |

Architecture §48 hash boundary is unchanged: only `map.yaml` and `map.pgm` are in the JCS payload. Metadata, manifest, evidence, optional pose graph, result fields, and resulting hash are outside that payload. The current artifact remains `approval_status: draft`, `world_frame: NOT_DECLARED`, `runtime_compatibility: NOT_VALIDATED`.

## 3. WP-04 dependency and source evidence

The integrated WP-04 L2 authority is used only for the direct shared target dependency: scan contract, TF edge ownership, and lifecycle/action-reset barriers. Its target binding is not a WP-05 executable source pin, runtime graph, or measurement. Receipt v2 and QoS6 remain unchanged. The bounded code authorization remains `GRANTED_BOUNDED_FAIL_CLOSED_INTERNAL_SEAMS_ONLY`; it is not expanded to ROS endpoints, launch/runtime configuration, Navigation bring-up, or profile resolution.

The V3 `frames.yaml`, `topics.yaml`, and `modes/nav2_baseline.yaml` remain contract/intention inputs only. Legacy Nav2/AMCL/launch/SLAM/Gazebo sources remain `REFERENCE_ONLY_LEGACY`; robot Xacro/SDF are geometry/provenance only. No path, filename, repeated spelling, or installed environment establishes canonical source selection or alias equivalence.

## 4. Pending pins, measurements, and fail-closed rule

`PENDING_IMPLEMENTATION_SOURCE_PIN`: Nav2, AMCL, Map Server, `robot_localization`, and bridge package/version/dependency pins; exact config/launch sources; AMCL parameter set; EKF config; canonical scan/TF adapter source; remap/namespace policy; lifecycle/startup source.

`PENDING_MEASUREMENT`: TF alignment and publisher uniqueness; actual scan header frame, cadence, latency, and freshness; EKF output/freshness/covariance; lifecycle health; localization quality; map/runtime compatibility.

If any required pin, measurement, or evidence is missing, conflicting, or unverifiable: no resolved Navigation V1 profile, no profile `config_hash`, no Map Server/AMCL/EKF/Navigation bring-up, no map approval, and no runtime authorization. No defaults, implicit aliases, legacy fallback, or inferred values may close a gap.

Offline source/schema/hash/remap/lifecycle-intent checks cannot prove runtime TF graph, publisher uniqueness, map loading, sensor frame, freshness, localization quality, lifecycle health, or compatibility. Runtime validation, world-frame validation, map approval, profile resolution, and WP-04 Gate B remain independent.

## 5. Status and non-goals

At exact base and in this review candidate: WP-05 `OPEN`; `warehouse_map2` draft/not approved/not navigation-ready; `WORLD_FRAME: NOT_DECLARED`; `RUNTIME_COMPATIBILITY: NOT_VALIDATED`; WP-04 `BLOCKED_BY_CONTRACT`; Gate A `PASSED`; Gate B `NOT_STARTED`; `CODE_AUTHORIZATION: GRANTED_BOUNDED_FAIL_CLOSED_INTERNAL_SEAMS_ONLY`; `RUNTIME_APPROVED: NOT_APPROVED`.

No map artifact bytes/metadata/manifest/hash, WP-04 interface or status, code, tests, ROSIDL, package manifest, runtime YAML, launch, hardware artifact, or runtime evidence is changed or created. This candidate grants no new authorization.
