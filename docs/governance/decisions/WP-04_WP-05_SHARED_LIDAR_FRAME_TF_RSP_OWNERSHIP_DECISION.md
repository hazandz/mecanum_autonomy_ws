# WP-04/WP-05 Shared LiDAR Frame and TF/RSP Ownership Decision

## Decision identity and lifecycle

- Work package: `WP04-WP05-SHARED-LIDAR-FRAME-TF-RSP-OWNERSHIP-DECISION`.
- Change class: `L2_PUBLIC_RUNTIME_INTERFACE_AND_TF_OWNERSHIP_GOVERNANCE`.
- Exact source base: `de71ae4d4ecb86724b1a02bdccad6f70315de7bc`.
- Architecture: `docs/MECANUM_NAV_DRL_Architecture.docx`, verified from the exact base Git blob at SHA-256 `432eeac363a595cfcf7e81c4b66054fb674dba140a2ef3cffecd617ab8136204`.
- Decision provenance: `USER_SUPPLIED_ARCHITECT_OWNER_DECISION`; no decision is inferred from Git ancestry.
- Before audit/integration: review candidate only.
- After independent audit PASS for this exact candidate, separate exact-commit User authorization, fast-forward, and remote-ref verification: `ACTIVE_L2_SHARED_TF_RSP_GOVERNANCE_FOR_FRAME_ID_AND_OWNERSHIP_ONLY`.

The conditional post-integration status is limited to public frame identity and ownership. It is not runtime authorization, runtime evidence, a source pin, or geometry verification.

## Fixed decision

1. Literal `lidar_frame` is the sole canonical public frame identity for Navigation V1 `/scan`, Observation Input Contract V3, and Observation Runtime Binding V3.
2. `robot_state_publisher` is the sole target owner of the direct fixed edge `base_link → lidar_frame`.
3. `RPLiDAR_A1M8_1` is `LEGACY_GEOMETRY_PROVENANCE_ONLY`. It is not canonical, an alias, a target runtime frame, a source pin, or evidence for the `/scan` frame ID.
4. `static_transform_publisher`, alias/remap equating the legacy frame with `lidar_frame`, a TF bridge between them, multiple direct-edge publishers, and treating legacy Xacro geometry as measurement-verified geometry are prohibited.
5. The existing legacy fixed-joint transform remains `PENDING_MEASUREMENT_AND_CANONICAL_SOURCE_SELECTION`. No legacy `xyz/rpy` is copied or pinned as canonical extrinsic.
6. A future, separate canonical RSP description source must directly define `base_link → lidar_frame` and be created and pinned only in a later candidate with suitable measurement/provenance.

## Fail-closed conditions

Missing canonical RSP source pin or verified extrinsic evidence, a `/scan` frame ID other than literal `lidar_frame`, any alias/bridge/static-transform workaround, or an ownership conflict blocks Navigation V1 and Observation V3 profile resolution, global `config_hash`, Nav2 baseline execution, Observation V3 runtime-vector creation, and Gate B start/pass.

## Scope exclusions and unchanged status

This candidate changes no Architecture DOCX, robot description, geometry, runtime source, map artifact, receipt/QoS, package lock, profile, measurement, `config_hash`, map approval, world-frame declaration, runtime evidence, or runtime authorization. It does not begin or pass Gate B.

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
