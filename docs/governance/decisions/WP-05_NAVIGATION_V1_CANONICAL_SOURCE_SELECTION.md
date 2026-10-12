# WP-05 — Canonical source-selection boundary for Navigation V1 / `warehouse_map2`

**Work package:** `WP05-NAVIGATION-V1-CANONICAL-SOURCE-SELECTION-REFRESH`
**Exact integration base:** `71f5db2b2bd1a04a1a3a087fed2ae6547f156fb1`
**Review branch:** `wp05-navigation-v1-canonical-source-selection-71f5db2`
**Candidate state:** documentation-only review candidate; pending independent audit, separate User authorization for this exact commit, fast-forward, and remote-ref verification.
**WP-05:** `OPEN`

## 1. Decision and scope

This record captures the Project Owner/User source-selection boundary for a future Navigation V1 profile. It does not define or select an executable profile, create a resolved configuration, approve a map, validate world/frame alignment, authorize bring-up, or change runtime status.

The Owner decision for this boundary is that **no executable Navigation V1 profile currently qualifies as canonical**. A path or familiar filename is not a source-selection decision. Until every required source and pin below is selected and verified, the profile is unresolved and fail-closed: no resolved profile, no profile `config_hash`, and no Navigation V1 bring-up.

The target architecture remains Map Server plus AMCL using `nav2_amcl::OmniMotionModel`. SLAM Toolbox belongs to MAPPING and must not also act as localization in `NAV2_BASELINE` or `HYBRID_AI_LOCAL`. The intended map/global frame is `map`. These selections do not show `map == world`, a world-to-map transform, metric alignment, runtime TF, localization correctness, map approval, or runtime compatibility.

## 2. Subject and authority boundary

At the exact integration base, the map subject is:

| Field | Value at base | Meaning |
|---|---|---|
| Artifact path | `artifacts/maps/warehouse_map2/` | Canonical map-artifact root under Architecture §48 |
| `map_id` | `warehouse_map2` | Existing draft artifact identity label |
| `artifact_identity` | `4a8a23d0-7e27-4a50-8201-dd1abf1a3db4` | Immutable artifact identity |
| `map_content_hash` | `2bd9ff0a40eaeb61c2359aab4bb213da623ab56746debe591edd4a54c2229f90` | Architecture §48 hash of the ordered `map.yaml`/`map.pgm` projection only |
| `approval_status` | `draft` | Not approved for Navigation |
| `world_frame.state` | `NOT_DECLARED` | No world/frame transition is made here |
| `runtime_compatibility.state` | `NOT_VALIDATED` | No runtime compatibility claim is made |

A future profile may bind this exact subject by artifact path, `map_id`, `artifact_identity`, and `map_content_hash`. Its Map Server must read the canonical `artifacts/maps/<map_id>/` artifact and verify expected identity/hash; a ROS-package map copy is not an alternate source. Binding a profile to a draft subject does not approve that subject. Architecture §48 requires an approved map before Navigation.

## 3. Source classification at the exact base

The inventory below is evidence of bytes/configuration at commit `71f5db2b2bd1a04a1a3a087fed2ae6547f156fb1`, not a promotion of those sources. Each digest is SHA-256 of the file bytes at that commit. The files in groups 3.1 and 3.2 are explicitly **not** canonical executable Navigation V1 profile sources.

### 3.1 Contract and intention inputs only

These V3 files can inform contract intent, ownership, or input names. They are not a resolved or executable Navigation V1 profile, do not pin installed package versions, and do not establish a complete source closure:

| Path at base | SHA-256 | Permitted interpretation |
|---|---|---|
| `ros2_ws/src/mecanum_nav_rl/config/v3/frames.yaml` | `815bff5df49f6de07a48e61275a21c728904ff699b771a0c970507483d0ff9da` | Contract/intention inputs: `map`, `odom`, `base_link`, generic `lidar_frame`, and target ownership tokens; no alias/geometry or runtime TF proof |
| `ros2_ws/src/mecanum_nav_rl/config/v3/topics.yaml` | `7dc2156aef44e83ca767528774fff6acd543814be3a0d9eb0b6373c4f5217a2d` | Contract/intention input naming `/scan` and other endpoints; no observed `LaserScan.header.frame_id` |
| `ros2_ws/src/mecanum_nav_rl/config/v3/modes/nav2_baseline.yaml` | `8b62ce6595c8545fa6b73a020872b08df3403d87f9ea5ea99ccd11eb449725ae` | Contract/intention ownership for Nav2 planner/controller; no Map Server, AMCL, EKF or lifecycle instance |

### 3.2 Legacy references only

The following legacy Nav2/AMCL/launch/SLAM/Gazebo material is `REFERENCE_ONLY_LEGACY`. It may expose historical or implementation details for later review, but must not be copied or selected directly as the canonical profile. No canonicality is inferred from package location, filename, or repeated frame/topic spelling.

| Path at base | SHA-256 | Limitation |
|---|---|---|
| `ros2_ws/src/ROBOT_URDF_final_description/config/nav2_params.yaml` | `26c37806f98e131e5993672122dee7efc5a4de1011f0bcb69e4c3a6e273ef4af` | Legacy AMCL/Nav2 parameters; includes Omni model but inconsistent relative/absolute scan references, `/odom`, legacy `base_scan`/`rplidar_link` references, and a commented Map Server stanza |
| `ros2_ws/src/ROBOT_URDF_final_description/launch/nav2_bringup.launch.py` | `97f70679cb107411e882e387a49c87ec80243c3fa43d70846083f8be1b3e143e` | Legacy launch defaults to a package map copy and autostart; not the artifact-root-bound canonical bring-up |
| `ros2_ws/src/ROBOT_URDF_final_description/config/mapper_params_online_async.yaml` | `8e363a5e141cb275f201ea78b84f2816b5b56c087a2435b2bd4f094fbd150c7a` | Legacy MAPPING parameters, not a Navigation localization profile |
| `ros2_ws/src/ROBOT_URDF_final_description/launch/slam.launch.py` | `28bf46d825fdcdaf79081897d1f0933dcf6946b4df17008c5a158563d03fe728` | Legacy SLAM launch, not concurrent Navigation localization |
| `ros2_ws/src/ROBOT_URDF_final_description/config/ros_gz_bridge_gazebo.yaml` | `374eb90b302cc1968ab84617d3f61f9954e2665f32982c3867e352c238433feb` | Legacy bridge configuration; not a selected Navigation remap or runtime graph |
| `ros2_ws/src/ROBOT_URDF_final_description/launch/gazebo.launch.py` | `2f0e2b329b4ad600e777a4a1b0578f3cc08fd9aea3a93705875e7a5afddae325` | Legacy simulation launch/static bridge and TF declarations; not runtime TF evidence |
| `ros2_ws/src/ROBOT_URDF_final_description/urdf/ROBOT_URDF_final.gazebo` | `6c7d0b9e90c2ed87a1de7aaf83b2c3ad07a897b5b1d1b2d26737054020d3f0fc` | Legacy Gazebo plugin/sensor declarations; not selected as a Navigation profile or runtime evidence |

### 3.3 Geometry/provenance evidence only

| Path at base | SHA-256 | Limitation |
|---|---|---|
| `ros2_ws/src/ROBOT_URDF_final_description/urdf/ROBOT_URDF_final.xacro` | `7a8f72894d024598f908b12b5a867c4c90e7e6ba167d9130e3e941e0129b5477` | Robot-description geometry/source evidence; does not select canonical sensor frame or prove runtime publication |
| `ros2_ws/src/ROBOT_URDF_final_description/launch/tugbot_depot.sdf` | `a4b6253340baa866d89640d62a94d04fbea51425e9af1deca591422a0a36d91d` | Source-world bytes at the pinned source revision; the User-supplied SLAM association is provenance, not proof of map/world equivalence or transform |

The source inventory recorded by the prior profile-resolution decision was compared against this base: the map artifact, listed V3 inputs, legacy Nav2/AMCL/SLAM launches and parameters, robot description, Gazebo sensor declarations, and Gazebo launch are byte-identical to that inventory. The bridge YAML is separately pinned above at this exact base. No tracked `mecanum_nav_bringup` Map Server/EKF profile configuration, `ekf_sim.yaml`/`ekf_real.yaml`, or exact ROS/Nav2 package-version lock exists at this base.

## 4. Required source-selection closure

Until an explicit source selection and immutable pin exists for every required item, the corresponding item remains pending. A pin must identify an immutable full Git commit, repository-relative path, and SHA-256, or an approved exact package/version source where Git bytes are not the source. Branch/tag names alone are not immutable pins.

| Executable profile component | Current state |
|---|---|
| Map Server config and launch ownership; artifact-root path injection and checks of expected `map_id`/`map_content_hash` | `PENDING_OWNER_SOURCE_SELECTION` / `PENDING_PIN` |
| AMCL parameter source and all concrete parameters, including `nav2_amcl::OmniMotionModel` under the selected package version | `PENDING_OWNER_SOURCE_SELECTION` / `PENDING_PIN` |
| EKF configuration, inputs and source ownership | `PENDING_OWNER_SOURCE_SELECTION` / `PENDING_PIN` |
| Launch composition/ownership and exact Nav2, Map Server, AMCL, EKF and dependent package/version pins | `PENDING_OWNER_SOURCE_SELECTION` / `PENDING_PIN` |
| Canonical scan topic and actual expected `LaserScan.header.frame_id` | `PENDING_OWNER_SOURCE_SELECTION` / `PENDING_EVIDENCE` |
| `base_link → lidar` child frame and static geometry source | `PENDING_OWNER_SOURCE_SELECTION` / `PENDING_PIN` |
| Realization of TF edge ownership (`map → odom` from AMCL; `odom → base_link` from EKF; robot description/fixed joint for `base_link → lidar`) | Architecture sets target ownership; exact selected source pins and single-publisher runtime evidence remain pending |
| Explicit remaps and namespace table, without implicit aliases | `PENDING_OWNER_SOURCE_SELECTION` / `PENDING_PIN` |
| Lifecycle/startup implementation and exact health/inhibition declarations | Architecture §49 supplies the required ordering; implementation source pins and runtime lifecycle evidence remain pending |
| Complete resolved profile/source closure and deterministic `config_hash` | Pending until every required decision, value, and pin is selected and validated; missing/conflicting inputs fail closed |

There is no implicit equivalence or alias among `lidar_frame`, `RPLiDAR_A1M8_1`, `base_scan`, `rplidar_link`, `sim_lidar`, `real_lidar`, or namespaced/scoped variants. Repeated spelling in V3, Xacro, URDF, SDF, launch or legacy parameters does not establish equivalence.

## 5. Resolution and evidence boundaries

A future profile can be called statically resolved only after every required executable component has a selected authority/source, exact immutable pin, complete value set, and consistency check; the selected artifact subject is bound by path/ID/identity/hash; and the complete static `ResolvedConfig` has a valid `config_hash` under Architecture §4. Until then, do not emit a partial profile hash and do not start Navigation V1 bring-up.

Offline checks after source selection must cover source closure, exact pins, schema/field completeness, artifact identity/hash, declared frame names and remaps, TF ownership uniqueness on paper, lifecycle declarations, package versions, and deterministic resolution. They cannot prove runtime behavior.

The Architecture §49 startup order remains the required target: robot description → drivers/bridge → EKF → Map Server → AMCL → healthy LocalizationMonitor → Planner/global costmap → Safety → selected controller/manager → mission acceptance. Downstream motion stays inhibited until upstream lifecycle and contract checks are healthy. Exact implementation sources and lifecycle pins remain pending. Separate later runtime evidence is required for actual TF graph and unique publishers; observed scan header frame; Map Server loading the exact artifact; AMCL lifecycle and localization quality/freshness; EKF output and freshness; remap/topic graph; startup inhibition and lifecycle health; and identity/hash of the map actually loaded. Such validation requires a separately authorized runtime work package.

Map approval under Architecture §48, world-frame validation, profile resolution, and runtime compatibility are separate decisions/evidence tracks. This record does not satisfy or combine them.

## 6. Candidate and authority status

This exact source-selection decision and Registry routing are review-candidate content only. They become current governance authority only after independent audit of the exact commit, separate explicit Project Owner/User authorization for that exact commit, fast-forward integration, and remote-ref verification. No audit PASS or integration is claimed by this candidate.

No status/dependency transition is made. WP-05 remains `OPEN`; `warehouse_map2` remains `draft` and not approved/navigation-ready; `world_frame: NOT_DECLARED`; `runtime_compatibility: NOT_VALIDATED`; `CODE_AUTHORIZATION: NOT_GRANTED`; `RUNTIME_APPROVED: NOT_APPROVED`. WP-04 is unchanged.
