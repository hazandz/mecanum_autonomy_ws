# WP-04/WP-05 Canonical RSP source pin provenance closure

## Decision identity and scope

- Work package: `WP04-WP05-CANONICAL-RSP-SOURCE-PIN-CLOSURE`.
- Classification: `L1_CANONICAL_DESCRIPTION_SOURCE_PIN_PROVENANCE_CLOSURE_WITHIN_ACTIVE_L2_TF_SEMANTICS`.
- Exact integration/source base: `d4ae75e34a62730da0576f51c1a49dd67b9d8d3b`.
- Architecture Git-blob SHA-256: `432eeac363a595cfcf7e81c4b66054fb674dba140a2ef3cffecd617ab8136204`.
- Shared L2 authority: `docs/architecture/ACR_SHARED_LIDAR_FRAME_TF_OWNERSHIP_V1.md` and `docs/SHARED_LIDAR_FRAME_TF_OWNERSHIP_V1.md`.
- Source-creation authorization is integration-resident at the exact base; this candidate only records provenance pins for the four already-integrated source/test files.
- Before audit and integration of this exact candidate, the new manifest and decision are review-candidate records at the exact source-base snapshot.

This is source-pin provenance closure only. Each entry is classified `PINNED_CANONICAL_DESCRIPTION_SOURCE_ONLY` and has boundary `NOT_A_RUNTIME_SOURCE_PIN`. The manifest does not pin runtime dependencies or the LiDAR driver, `/scan` runtime profile, AMCL, EKF, map, or runtime package configuration. It does not change the active L2 frame or TF semantics.

## Pinned source provenance

The companion manifest records exactly four sources at commit `d4ae75e34a62730da0576f51c1a49dd67b9d8d3b`: the canonical robot-description Xacro, the Gazebo LiDAR-absence guard, the dedicated RSP launch source, and the static LiDAR TF contract test. `ROBOT_URDF_final_description` owns these sources. Their consumer scope is WP-04 Observation V3 and WP-05 Navigation V1 source provenance only.

## Frame, ownership, and CAD packet boundary

The active shared L2 contract remains literal public frame `lidar_frame`; `robot_state_publisher` is the sole target owner of the direct fixed edge `base_link → lidar_frame`.

The source contains the Owner-accepted CAD nominal transform `xyz=(-0.031765, 0, 0.140) m`, `rpy=(0, 0, 0) rad`, associated with packet `WP04-WP05-YDLIDAR-X3PRO-CAD-EXTRINSIC-V1`, fingerprint SHA-256 `40fe44cb3647376b3b1f793761091e101051d7e141e4687e67e2f03632e430de`. This is `OWNER_ACCEPTED_CAD_NOMINAL_EXTRINSIC_FOR_PHYSICAL_INSTALLATION`; it is not `HARDWARE_MEASURED_EXTRINSIC`. `HARDWARE_AS_BUILT_VERIFICATION_PENDING` remains in force. The packet's raw images are not copied or created as repository artifacts.

The integrated Gazebo source has no active LiDAR sensor/profile. `RPLiDAR_A1M8_1` remains legacy geometry provenance only: it is not canonical, an alias, or a TF bridge. A future `/scan` runtime requires a separate candidate with suitable YDLIDAR X3 Pro source/pin and measurement evidence.

## Explicit non-effects and status

This provenance closure creates no runtime authorization or runtime evidence, map approval, resolved profile, global `config_hash`, Gate B start/pass, or runtime graph. It does not claim hardware-as-built verification or runtime TF validation. WP-04 remains `BLOCKED_BY_CONTRACT`; Gate A `PASSED`; Gate B `NOT_STARTED`; WP-05 remains `OPEN`; `RUNTIME_APPROVED: NOT_APPROVED`.

Evidence level for the integrated source inputs is `INTEGRATED_SOURCE_PROVENANCE_AND_STATIC_TEST_EVIDENCE_ONLY`; the pytest result is static evidence, not runtime evidence. This exact candidate remains review-only until independently audited and separately authorized for integration.
