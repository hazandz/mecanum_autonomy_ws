# Shared LiDAR Frame and TF Ownership V1

## Status

This contract is a review-only candidate at source base `de71ae4d4ecb86724b1a02bdccad6f70315de7bc`, based on `USER_SUPPLIED_ARCHITECT_OWNER_DECISION`. It is not active before independent audit PASS, separate exact-commit User authorization, fast-forward, and remote-ref verification. After those conditions for the exact candidate, its scope is only `ACTIVE_L2_SHARED_TF_RSP_GOVERNANCE_FOR_FRAME_ID_AND_OWNERSHIP_ONLY`.

The status does not grant runtime authorization or provide runtime evidence, source pins, or geometry verification.

## Shared contract

- Canonical public LiDAR frame identity: literal `lidar_frame`.
- Applies to: Navigation V1 `/scan`, Observation Input Contract V3, and Observation Runtime Binding V3.
- Expected direct fixed TF edge: `base_link → lidar_frame`.
- Sole target owner of that edge: `robot_state_publisher`.
- `RPLiDAR_A1M8_1`: `LEGACY_GEOMETRY_PROVENANCE_ONLY`; not canonical, not an alias, not a target runtime frame, not a source pin, and not evidence for the `/scan` frame ID.
- Existing legacy fixed-joint transform: `PENDING_MEASUREMENT_AND_CANONICAL_SOURCE_SELECTION`. Do not copy or pin legacy `xyz/rpy` as canonical extrinsics.
- Future source rule: a separate canonical robot-description source must define `base_link → lidar_frame` directly and be created/pinned only in a later candidate with appropriate measurement and provenance.

## Prohibitions

Do not use `static_transform_publisher`, an alias/remap that equates `RPLiDAR_A1M8_1` with `lidar_frame`, a TF bridge between those frames, multiple publishers for the direct edge, or legacy Xacro geometry as measurement-verified geometry.

## Fail-closed behavior

If the canonical RSP source pin or verified extrinsic evidence is absent, `/scan` has any frame ID other than literal `lidar_frame`, an alias/bridge/static-transform workaround is present, or ownership conflicts, do not resolve the Navigation V1 or Observation V3 profile, do not resolve global `config_hash`, do not run Nav2 baseline, do not create an Observation V3 runtime vector, and do not start or pass Gate B.

This contract selects no geometry values and creates no source, pin, measurement, runtime graph, profile, hash, map approval, world-frame declaration, runtime evidence, or runtime authorization.
