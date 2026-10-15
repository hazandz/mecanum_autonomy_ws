# ACR: Shared LiDAR Frame and TF Ownership V1

## Record status and scope

- Change class: `L2_PUBLIC_RUNTIME_INTERFACE_AND_TF_OWNERSHIP_GOVERNANCE`.
- Exact source-base snapshot: `de71ae4d4ecb86724b1a02bdccad6f70315de7bc`.
- Architecture authority at that base: `docs/MECANUM_NAV_DRL_Architecture.docx`, SHA-256 `432eeac363a595cfcf7e81c4b66054fb674dba140a2ef3cffecd617ab8136204`.
- Provenance: `USER_SUPPLIED_ARCHITECT_OWNER_DECISION`. This decision is supplied by the User and is not inferred from Git ancestry.
- Before independent audit and exact-commit User authorization, this record is review-only and does not alter active authority.
- Only after independent audit PASS for the exact candidate, separate User authorization for that exact commit, fast-forward, and remote-ref verification does it become `ACTIVE_L2_SHARED_TF_RSP_GOVERNANCE_FOR_FRAME_ID_AND_OWNERSHIP_ONLY`.

That post-integration status covers public frame identity and target TF ownership only. It is not runtime authorization, runtime evidence, a runtime source pin, or geometry verification.

## Public frame identity and target ownership

`lidar_frame` is the sole canonical public LiDAR frame identity for Navigation V1 `/scan`, Observation Input Contract V3, and Observation Runtime Binding V3. The target direct fixed edge is `base_link → lidar_frame`; `robot_state_publisher` is its sole target owner.

The target identity does not establish that a matching source, publisher, physical extrinsic, or runtime TF edge exists. A future canonical robot-description source must define the direct edge and be separately pinned after suitable measurement and provenance are available.

## Legacy disposition

`RPLiDAR_A1M8_1` is `LEGACY_GEOMETRY_PROVENANCE_ONLY`. It is not the canonical frame, an alias of `lidar_frame`, a target runtime frame, a source pin, or evidence that `/scan` uses the required frame ID.

The existing legacy fixed-joint transform is `PENDING_MEASUREMENT_AND_CANONICAL_SOURCE_SELECTION`. Its `xyz` and `rpy` values are not copied, selected, or pinned as canonical extrinsics. Legacy Xacro geometry is not measurement-verified geometry.

## Prohibited substitutions and fail-closed boundary

The following are prohibited: `static_transform_publisher`; alias/remap that treats `RPLiDAR_A1M8_1` as `lidar_frame`; a TF bridge from `RPLiDAR_A1M8_1` to `lidar_frame`; multiple publishers of `base_link → lidar_frame`; and use of legacy Xacro geometry as measurement-verified geometry.

If the canonical robot-state-publisher source pin or verified extrinsic evidence is missing, the frame ID differs from literal `lidar_frame`, an alias/bridge/static-transform workaround exists, or ownership conflicts, fail closed: do not resolve the Navigation V1 profile or Observation V3 profile; do not resolve global `config_hash`; do not run Nav2 baseline; do not create an Observation V3 runtime vector; and do not start or pass Gate B.

This record creates no runtime source, robot-description change, geometry pin, measurement, profile, hash, map approval, world-frame declaration, runtime evidence, or runtime authorization.
