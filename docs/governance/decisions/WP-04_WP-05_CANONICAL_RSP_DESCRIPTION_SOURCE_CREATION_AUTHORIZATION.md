# WP-04/WP-05 Canonical RSP Description Source Creation Authorization

## Decision identity and lifecycle

- Work package: `WP04-WP05-CANONICAL-RSP-DESCRIPTION-SOURCE-CREATION-AUTHORIZATION`.
- Classification: `L1_IMPLEMENTATION_SOURCE_CREATION_AUTHORIZATION_WITHIN_ACTIVE_L2_TF_SEMANTICS`.
- Exact integration/source base: `fa862f26eed6cfa30a553ccf6f1befcad532a1f9`.
- Architecture Git-blob SHA-256 at that base: `432eeac363a595cfcf7e81c4b66054fb674dba140a2ef3cffecd617ab8136204`.
- Shared L2 dependency: `docs/architecture/ACR_SHARED_LIDAR_FRAME_TF_OWNERSHIP_V1.md` and `docs/SHARED_LIDAR_FRAME_TF_OWNERSHIP_V1.md`.
- Provenance: `USER_SUPPLIED_ARCHITECT_OWNER_DECISION`; not inferred from Git ancestry.
- Before audit and integration of this exact candidate, this is a review-only conditional authorization record.
- Only after independent audit PASS for this exact candidate, separate User authorization for its exact commit, fast-forward, and remote-ref verification does the record become `INTEGRATED_L1_CANONICAL_RSP_DESCRIPTION_SOURCE_CREATION_AUTHORIZATION_ONLY`.

This L1 authorization operates within the already integrated L2 public-frame and TF-ownership semantics. It does not change those semantics. Once integrated, it permits only a later source candidate in the four paths listed below, and only if the required extrinsic evidence packet has been explicitly accepted by the Owner. It is not itself a source pin, geometry verification, runtime evidence, profile resolution, `config_hash`, Gate B authorization, or runtime authorization. `RUNTIME_APPROVED` remains `NOT_APPROVED`.

## Conditionally authorized future source candidate

`ROBOT_URDF_final_description` is the owner of the future robot-description source. After this authorization is integrated and the Owner-accepted extrinsic evidence packet is available, a separate future candidate may create or modify only:

1. `ros2_ws/src/ROBOT_URDF_final_description/urdf/ROBOT_URDF_final.xacro`
2. `ros2_ws/src/ROBOT_URDF_final_description/urdf/ROBOT_URDF_final.gazebo`
3. `ros2_ws/src/ROBOT_URDF_final_description/launch/navigation_v1_robot_state_publisher.launch.py`
4. `ros2_ws/src/ROBOT_URDF_final_description/test/test_navigation_v1_lidar_frame_tf_contract.py`

This authorization does not permit changes to `package.xml`, `setup.py`, `mecanum_nav_bringup`, Nav2 launch, AMCL, EKF, maps, QoS, receipt, or WP-04 ingress sources. It does not itself create or modify any of the four future paths.

## Required source invariants

The future source candidate must define exactly one direct fixed edge `base_link → lidar_frame`, with `robot_state_publisher` as its sole owner. The public scan frame remains the literal `lidar_frame`. `RPLiDAR_A1M8_1` must not appear in the target robot-description tree.

The future candidate must not create an alias, remap equivalence, TF bridge, or `static_transform_publisher`, and must not execute ROS, Gazebo, Nav2, launch, or runtime. It may not resolve a source pin, profile, global `config_hash`, Nav2 baseline, Observation V3 vector, or Gate B.

## Extrinsic evidence prerequisite

The future source candidate is fail-closed until an Owner-approved extrinsic evidence packet is available. The packet must include all of the following:

- robot and LiDAR identity;
- the coordinate convention for `base_link`;
- finite values for all six components `x`, `y`, `z`, `roll`, `pitch`, and `yaw`;
- measurement method, instrument, measurement date, and operator;
- repeated observations;
- uncertainty;
- raw evidence digest;
- explicit Owner acceptance.

If any item is missing or the Owner has not accepted the packet, do not create or modify the four source paths. Do not pin a source, resolve a profile or `config_hash`, run Nav2 baseline, create an Observation V3 vector, or start/pass Gate B.

## Legacy disposition and boundary

`RPLiDAR_A1M8_1` and its existing `xyz/rpy` remain `LEGACY_GEOMETRY_PROVENANCE_ONLY` and `PENDING_MEASUREMENT_AND_CANONICAL_SOURCE_SELECTION`. Do not copy, default, interpolate, or pin legacy values as the canonical extrinsic. Existing package, Xacro, Gazebo, and legacy launch content is provenance/reference material, not approval of a future source.

This record creates no robot-description or Gazebo source, launch, test source, runtime profile, runtime graph, source pin, measurement, geometry verification, map approval, world-frame declaration, runtime evidence, or runtime authorization.

## Status at the source base

```text
WP-04: BLOCKED_BY_CONTRACT
GATE_A_STRUCTURAL_PRIMITIVES: PASSED
GATE_B: NOT_STARTED
WP-05: OPEN
MAP_ARTIFACT: DRAFT_ON_INTEGRATION_NOT_APPROVED
WORLD_FRAME: NOT_DECLARED
RUNTIME_COMPATIBILITY: NOT_VALIDATED
RUNTIME_APPROVED: NOT_APPROVED
```
