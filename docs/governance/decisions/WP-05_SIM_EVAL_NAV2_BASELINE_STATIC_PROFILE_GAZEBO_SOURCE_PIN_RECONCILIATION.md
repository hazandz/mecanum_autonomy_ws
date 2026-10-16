# WP05 sim_eval + NAV2_BASELINE static profile Gazebo source-pin reconciliation

## Classification and lifecycle

- Classification: `L1_STATIC_PROFILE_CURRENT_SOURCE_PIN_RECONCILIATION_ONLY`.
- Exact source base: `4f491edca1d46dee259d57350ad520a0334e4049`.
- Architecture authority SHA-256: `432eeac363a595cfcf7e81c4b66054fb674dba140a2ef3cffecd617ab8136204`.
- Review branch: `wp05-sim-eval-static-profile-gazebo-pin-reconcile-4f491ed`.
- Evidence: static profile input provenance only; this record is review-only pending independent audit and separate User authorization for the exact candidate.

## Reconciled pre-existing drift

At the exact integration base, `ros2_ws/src/ROBOT_URDF_final_description/urdf/ROBOT_URDF_final.gazebo` has SHA-256 `1e97b6ea340adc9aecaf320cc432007c6bb37f5922cdc0366dbee50a9a26ff0e` and retains the static LiDAR declaration (`lidar_frame`, `YDLIDAR_X3_PRO`, `gpu_lidar`, relative topic `scan`, 6.0 Hz, 500 samples, range 0.10–8.00 m). The current Step 5A profile YAML, Python descriptor and JSON manifest still carried the earlier source base `2864a215782cc1901aa259a49d885fa0c132cf7a` and Gazebo provenance SHA-256 `a97b092f7343d04679ed1417539e47d217b20d18afc3364a27cf14110d9dece8`. This mismatch is pre-existing at the source base and makes the current profile input descriptor inconsistent with the checked-in source bytes.

This candidate changes only two values in each of those three current descriptors: `source_commit` becomes `4f491edca1d46dee259d57350ad520a0334e4049`, and the `gazebo_lidar_source` entry SHA-256 becomes `1e97b6ea340adc9aecaf320cc432007c6bb37f5922cdc0366dbee50a9a26ff0e`. All other descriptor values and semantics are preserved. The old `a97b092f7343d04679ed1417539e47d217b20d18afc3364a27cf14110d9dece8` value in `docs/governance/evidence/WP-05_NAVIGATION_V1_WORKSPACE_SOURCE_ROLE_INVENTORY.json` is a historical snapshot and is intentionally not rewritten.

## Boundary and status

No Gazebo source, LiDAR contract, sensor semantics, TF, ROS `/scan`, bridge, map, or runtime contract is changed. The source commit value identifies the current reconciliation source base; it does not make this a resolved runtime profile. If integrated, Step 5A is self-consistent again only as a static profile input closure.

No endpoint pin, runtime source pin, bridge, runtime profile resolution, `ResolvedConfigV3`, `config_hash`, runtime evidence, or runtime authorization is created. WP-05 remains `OPEN`; WP-04 remains `BLOCKED_BY_CONTRACT`; Gate A remains `PASSED`; Gate B remains `NOT_STARTED`; `RUNTIME_APPROVED: NOT_APPROVED`. No conclusion about WP06-6D audit or integration is made.

## Allowlist

The exact nine-path candidate scope is recorded in the accompanying evidence JSON. No candidate commit hash is self-referenced.
