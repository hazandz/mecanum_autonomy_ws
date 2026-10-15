# WP-04 YDLIDAR X3 Pro static simulation scan source-creation authorization

## Decision identity and review boundary

- Work package: `WP04-YDLIDAR-X3-PRO-STATIC-SIMULATION-SCAN-SOURCE-CREATION-AUTHORIZATION`.
- Classification: `L1_STATIC_SOURCE_CREATION_AUTHORIZATION_ONLY`.
- Exact source-base snapshot: `53d56e1787487fd90c6d92e8f4f51a3eca23773f`.
- Architecture Git-blob SHA-256 at that base: `432eeac363a595cfcf7e81c4b66054fb674dba140a2ef3cffecd617ab8136204`.
- Before independent audit and separate authorization/integration of this exact candidate, this record and its manifest are review-candidate material only.
- The immutable vendor source and static values are recorded in `docs/governance/evidence/WP-04_YDLIDAR_X3_PRO_STATIC_SIMULATION_SCAN_SOURCE_CREATION_AUTHORIZATION_MANIFEST.json`.

This candidate authorizes a later, separate static-source candidate only. It creates no Gazebo, Xacro, launch, test, driver, bridge, ROS node, runtime profile, or executable behavior in this work package.

## Vendor source and bounded static derivation

The vendor facts are taken from `doc/Dataset.md` in `https://github.com/YDLIDAR/YDLidar-SDK` at immutable commit `42a82ed10d2304094c111fc63dee8e4a229b79b7`; the exact file SHA-256 is `ec5e27ab30b1e4d13a4b25bc4770a106d05f54ba5b191f21374af11a6d2b4897`. Its `X3/X3 Pro` row specifies baud rate 115200, sample rate 3 K samples/s, range 0.10–8.0 m, scan frequency 4–8 Hz (PWM), and single-channel operation. These are static vendor-document facts, not measurements of this repository's future simulation or hardware runtime.

A future static Gazebo source candidate is authorized to describe model identity `YDLIDAR_X3_PRO` on literal `lidar_frame`, a 360° scan, range 0.10–8.00 m, nominal simulation rate 6.0 Hz, and 500 samples, using the specified derivation `3000 samples/s ÷ 6.0 Hz = 500 samples/scan`. The sensor source must not create TF; `robot_state_publisher` remains sole owner of the existing direct `base_link → lidar_frame` edge. The Gazebo transport topic may be `scan`; this does not establish ROS `/scan` or `sensor_msgs/msg/LaserScan`.

## Conditional next-candidate authorization

Only after this exact governance candidate passes independent audit, receives separate explicit User authorization, is fast-forwarded, and its remote ref is verified, a subsequent static-source candidate may create or modify exactly:

1. `ros2_ws/src/ROBOT_URDF_final_description/urdf/ROBOT_URDF_final.gazebo`
2. `ros2_ws/src/ROBOT_URDF_final_description/test/test_navigation_v1_lidar_frame_tf_contract.py`

That candidate must preserve active L2 authority: public LiDAR frame `lidar_frame`; `robot_state_publisher` as sole owner of `base_link → lidar_frame`; `RPLiDAR_A1M8_1` as legacy provenance only, with no alias, bridge, or fallback. It must not create a TF edge, ROS-Gazebo bridge, driver, ROS node, launch execution, runtime profile, `config_hash`, runtime evidence, Gate B transition, map approval, or runtime authorization.

## Pending evidence and fail-closed boundary

All of the following remain pending and are not satisfied by this authorization:

- `YDLIDAR_X3_PRO_RUNTIME_SOURCE_PIN: PENDING`
- `ROS_GAZEBO_SCAN_BRIDGE_SOURCE_PIN: PENDING`
- `SCAN_RUNTIME_PROFILE: PENDING`
- `LIDAR_CADENCE_MEASUREMENT: PENDING_MEASUREMENT`
- `LIDAR_LATENCY_FRESHNESS_MEASUREMENT: PENDING_MEASUREMENT`
- `NO_RETURN_BEHAVIOR_MEASUREMENT: PENDING_MEASUREMENT`
- `HARDWARE_AS_BUILT_EXTRINSIC_VERIFICATION: PENDING`

This is not a runtime source pin or runtime evidence. It does not equate Gazebo transport `scan` with ROS `/scan` or `sensor_msgs/msg/LaserScan`, and it does not alter map, world-frame, profile, Gate B, or authorization status. Runtime, map approval, and hardware-as-built conclusions require their own authority and evidence.

## Status routing

The current candidate remains review-only. After audit PASS for this exact candidate, separate exact-commit User authorization, fast-forward, and remote-ref verification, it may be recorded only as an integrated L1 static source-creation authorization. It still does not grant runtime approval. WP-04 remains `BLOCKED_BY_CONTRACT`; Gate A `PASSED`; Gate B `NOT_STARTED`; WP-05 `OPEN`; map remains `DRAFT_ON_INTEGRATION_NOT_APPROVED`; `WORLD_FRAME: NOT_DECLARED`; `RUNTIME_COMPATIBILITY: NOT_VALIDATED`; `RUNTIME_APPROVED: NOT_APPROVED`.
