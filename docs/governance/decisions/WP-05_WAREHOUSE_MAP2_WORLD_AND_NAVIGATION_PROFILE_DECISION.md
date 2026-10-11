# WP-05 `warehouse_map2` World Declaration and Navigation Profile Decision

**State:** review candidate; pending consolidated independent audit, separate User authorization for the exact candidate, fast-forward, and remote-ref verification.

## Decision provenance

The Project Owner/User supplied the decisions recorded below for this candidate. The Git pin identifies the exact simulation-world file bytes at the stated repository revision. The assertion that `warehouse_map2` was produced through SLAM using this world is a `USER_SUPPLIED_DECISION`; the Git pin alone does not prove that association, a coordinate transform, or runtime behavior.

- Repository: `https://github.com/hazandz/mecanum_autonomy_ws.git`
- Integration base: `e89aeda5ca78859bfeedac4e7b94bcd6c7dcc7f0`
- World file: `ros2_ws/src/ROBOT_URDF_final_description/launch/tugbot_depot.sdf`
- World-file SHA-256: `a4b6253340baa866d89640d62a94d04fbea51425e9af1deca591422a0a36d91d`
- Map artifact: `artifacts/maps/warehouse_map2/`; `map_id: warehouse_map2`
- `map_content_hash`: `2bd9ff0a40eaeb61c2359aab4bb213da623ab56746debe591edd4a54c2229f90`

## World/frame declaration

The candidate metadata changes `world_frame.state` to `DECLARED_UNVERIFIED` and pins the SDF using the active schema's immutable `git_file` evidence-reference shape: repository, full commit, repository-relative path, and SHA-256. This records the selected source-world identity and the User-supplied SLAM provenance decision. It does **not** assert `map == world`, an identity transform, metric alignment, or a measured/validated `world → map` transform. No transform value is recorded.

The map's declared global frame name is `map`. That name does not establish equivalence with a Gazebo world frame. `runtime_compatibility` remains `NOT_VALIDATED`; the map's `approval_status` remains `draft`. Map approval is a separate decision and is not granted here.

## Navigation V1 target profile (not implemented or validated)

The User-selected target is Map Server plus AMCL using `nav2_amcl::OmniMotionModel`. SLAM Toolbox is for MAPPING only and is not a concurrent localization authority in `NAV2_BASELINE` or `HYBRID_AI_LOCAL`. Target TF ownership is AMCL `map → odom`, EKF `odom → base_link`, and robot-state-publisher/fixed joint `base_link → lidar_frame`. The scan target is `/scan` with exact header frame `lidar_frame`; there is no implicit alias to `RPLiDAR_A1M8_1`, `base_scan`, or a namespaced alias.

A future resolved profile must pin the artifact path, `map_id`, `map_content_hash`, Map Server and AMCL settings, `OmniMotionModel`, EKF settings, TF ownership, scan topic/frame, explicit remaps, and lifecycle/startup expectations. It must also identify the exact launch/config revisions and hashes, map-file selection, initial-pose source and handling, and time configuration. These are target-profile requirements, not claims that such a profile exists, has been selected as runtime configuration, or has been run. Existing legacy package configurations are not promoted to this profile by this decision.

Runtime compatibility evidence and validation remain outstanding. No ROS, Nav2, AMCL, Gazebo, HIL, hardware, or runtime validation is authorized by this record.

## Hash and approval boundaries

The active map-hash boundary is unchanged: `map_content_hash` covers only `map.yaml` and `map.pgm` through the §48 projection. Metadata and the full manifest remain outside that payload. This candidate updates the manifest's metadata descriptor to match the changed metadata bytes; it does not change the map projection or resulting `map_content_hash`.

The artifact remains a draft and is not approved for navigation. This candidate's world declaration and target profile become part of the integration record only after the exact candidate passes independent audit, receives separate User authorization, is fast-forwarded, and the remote integration ref is verified.

## Authorization and work-package status

No code, runtime, HIL, hardware, motor-enable, `deploy_sim`, or `deploy_real` authorization is granted. WP-05 remains OPEN. WP-04 remains `BLOCKED_BY_CONTRACT`; Gate A structural primitives remain PASSED and Gate B remains NOT_STARTED.
