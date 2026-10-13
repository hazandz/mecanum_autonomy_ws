# Architecture Change Record: Navigation V1 Runtime Binding

| Field | Value |
|---|---|
| Record ID | `ACR-NAVIGATION-V1-RUNTIME-BINDING` |
| Record revision | `1` |
| Change class | `L2_PUBLIC_RUNTIME_INTERFACE_TF_LIFECYCLE_BINDING` |
| Work package | `WP05-NAVIGATION-V1-RUNTIME-BINDING-ARCHITECTURE-DECISION` |
| Exact source/integration base | `16e4d81296f5db0fb322349bfe673cb5bd2c1534` |
| Architecture authority | `docs/MECANUM_NAV_DRL_Architecture.docx`; SHA-256 `432eeac363a595cfcf7e81c4b66054fb674dba140a2ef3cffecd617ab8136204`; unchanged and highest authority |
| Source-base status | Review-candidate snapshot; not active at the stated base |
| Target status | After independent audit PASS, separate exact-commit User authorization, fast-forward, and remote-ref verification: `ACTIVE_L2_NAVIGATION_V1_RUNTIME_BINDING_TECHNICAL_AUTHORITY_FOR_TARGET_BINDINGS_ONLY` |

## 1. Purpose and authority boundary

Architecture §§4, 13–14, 41–43, 48–50 and Appendix A define Navigation V1, map identity, runtime ownership and lifecycle requirements. The integrated WP-05 source-selection record states that no executable Navigation V1 profile qualifies as canonical. This L2 amendment records the Owner-selected target runtime bindings that constrain a future profile. It does not select executable sources, package versions, parameter values, launch composition, or measurements.

This refreshed ACR is a review candidate at exact source base `16e4d81296f5db0fb322349bfe673cb5bd2c1534`. Earlier wording/content provenance comes from `wp05-navigation-v1-runtime-binding-architecture-5249a11@4ff6b96783c940e7f4c523ed553d3ad75f8a5a55` (parent `5249a11e69408abf845e8568258989a70edefb35`); that commit is source-content provenance only, not this candidate parent, not the current base, and not integrated by this refresh. Its target bindings become technical authority only after all of these events occur for the same exact candidate: independent audit PASS, separate explicit Project Owner/User authorization for that commit, fast-forward integration, and remote integration-ref verification. No separate activation candidate is required. Review publication, ancestry, or a claimed audit alone does not activate it.

After activation the authority is limited to the five target-binding groups in §2. It does not create a resolved profile, source pin, profile `config_hash`, executable bring-up, map approval, world-frame validation, runtime compatibility, Gate B progress, WP-05 closure, or runtime authorization.

## 2. Owner-selected target bindings

These bindings are target contracts. A target owner/type/endpoint does not identify an implementation publisher or prove that a runtime graph conforms.

| Binding group | Target binding |
|---|---|
| Map artifact | Map Server reads only `artifacts/maps/<map_id>/`; no package/source-tree map copy. A future resolved profile binds exact artifact path, `map_id`, `artifact_identity`, and `map_content_hash`. `warehouse_map2` at this base is draft, not selected for navigation/localization, not approved, and not navigation-ready. Architecture §48 hash input remains only the ordered `map.yaml` and `map.pgm` projection; metadata, manifest, evidence, and result hashes remain outside it. |
| Localization / AMCL | `NAV2_BASELINE` uses AMCL as the sole target owner of `map → odom`, with motion model `nav2_amcl::OmniMotionModel`. SLAM Toolbox belongs to `MAPPING` only and must not concurrently publish `map → odom` in `NAV2_BASELINE`. No AMCL parameter file, package version, launch source, covariance, tolerance, or particle count is selected. |
| EKF odometry | `robot_localization` EKF is the sole target owner of `odom → base_link`. Target inputs are `/wheel/odometry_raw` and `/imu/data`; target output is `/odometry/filtered`, type `nav_msgs/msg/Odometry`, `header.frame_id=odom`, `child_frame_id=base_link`. Gazebo `/odom`, simulated odometry, and Ground Truth are not canonical runtime inputs. No EKF YAML, package version, covariance/timing value, or launch source is selected. |
| LiDAR / TF / remap | Target scan is `/scan`, type `sensor_msgs/msg/LaserScan`, with exact `header.frame_id=lidar_frame`. `robot_state_publisher` is the sole target owner of `base_link → lidar_frame`. `RPLiDAR_A1M8_1`, `base_scan`, `rplidar_link`, and legacy variants are not aliases; no static-transform workaround is allowed. Namespace/remap policy is a later profile-specific pinned decision. |
| Lifecycle / startup | Follow Architecture §49 startup order and §50 verification obligations. Description, drivers/bridge, EKF, Map Server, AMCL, healthy LocalizationMonitor, planner/global costmap, Safety, selected controller/manager, then mission acceptance. Downstream motion remains inhibited until upstream lifecycle and contract health gates pass. Map Server, AMCL, EKF, and Nav2 require distinct lifecycle contracts and implementation pins before bring-up. Legacy `autostart` is not sufficient evidence. Missing health/source/evidence fails closed. |

The active WP-04 L2 runtime-binding authority is a direct dependency only for the shared target scan, TF-edge ownership, and lifecycle/barrier boundary. Its target contract does not provide the executable Nav2/Map Server/AMCL/EKF sources or pins required by WP-05. Receipt v2, QoS6, OIC/receipt semantics, and WP-04 status are unchanged.

## 3. Required pins and measurements remain pending

The following remain `PENDING_IMPLEMENTATION_SOURCE_PIN`: exact package/version/dependency pins for Nav2, AMCL, Map Server, `robot_localization`, and bridge; exact config/launch sources and ownership; AMCL parameter set; EKF configuration; canonical scan/TF adapter source; remap/namespace policy; and lifecycle/startup source. A pin must identify immutable source bytes (full commit, repository-relative path, SHA-256) or an explicitly approved exact package/version source. A branch/tag or a legacy file hash alone is not a selected pin.

The following remain `PENDING_MEASUREMENT`: TF alignment and actual publisher uniqueness; observed scan header frame, cadence, latency, and freshness; EKF output/freshness/covariance; lifecycle health; localization quality; and map/runtime compatibility. User-supplied provenance or a Git-pinned SDF identifies a source association/bytes only; it does not establish `map == world`, a transform, metric alignment, or runtime behavior.

Missing, conflicting, or unverifiable required source, pin, measurement, or evidence means fail closed: no resolved Navigation V1 profile, no profile `config_hash`, no Map Server/AMCL/EKF/Navigation bring-up, no map approval, and no runtime authorization. Do not fill gaps with defaults, aliases, legacy sources, or inferred values.

## 4. Evidence and independent status boundaries

Offline evidence can establish source bytes/pins, binding/schema consistency, artifact identity/hash, declared frame names, explicit remap declarations, and lifecycle intent. It cannot establish actual TF graph/unique publishers, observed scan header frame, map loading, localization freshness/quality, EKF output, lifecycle health, or runtime compatibility. These require separately authorized runtime evidence.

Map approval under Architecture §48, world-frame validation, profile resolution, runtime compatibility, and WP-04 Gate B are separate decisions/evidence tracks. At this candidate's base: `warehouse_map2` remains `draft`; `WORLD_FRAME: NOT_DECLARED`; `RUNTIME_COMPATIBILITY: NOT_VALIDATED`; WP-05 `OPEN`; WP-04 `BLOCKED_BY_CONTRACT`; Gate A `PASSED`; Gate B `NOT_STARTED`; `CODE_AUTHORIZATION: GRANTED_BOUNDED_FAIL_CLOSED_INTERNAL_SEAMS_ONLY`; `RUNTIME_APPROVED: NOT_APPROVED`.

## 5. Compatibility and non-goals

This ACR does not amend the Architecture DOCX, alter map bytes/hash boundary, select an executable profile or source pin, apply a legacy frame alias, create a transform claim, approve `warehouse_map2`, validate runtime, start/pass Gate B, or change WP/dependency status. The bounded WP-04 code authorization remains limited to internal fail-closed seams; it does not authorize public ROS/runtime interfaces, Navigation bring-up, or the source/config work pending here.
