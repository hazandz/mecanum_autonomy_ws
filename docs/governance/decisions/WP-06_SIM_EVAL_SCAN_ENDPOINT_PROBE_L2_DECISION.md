# WP06 sim_eval Scan Endpoint Probe — L2 Decision

## Classification and lifecycle

- Classification: `L2_SIM_EVAL_SCAN_ENDPOINT_PROBE_SOURCE_IMPLEMENTATION`.
- Exact source base: `4f491edca1d46dee259d57350ad520a0334e4049`.
- Review branch: `wp06-sim-eval-scan-endpoint-probe-4f491ed`.
- Evidence ceiling: `IMPLEMENTED_OFFLINE_BUILD_AND_TEST_ONLY`.
- The candidate adds only a future probe executable source, its static descriptor, offline tests, package registration, and governance records. The probe was not run while creating this candidate.

## Endpoint observation boundary

The sensor's SDF `<topic>scan</topic>` is a declared relative topic and is not a full Gazebo Transport endpoint. The probe does not derive an endpoint from this value, a basename/suffix, world/model name, frame, or sensor name. It discovers the available topic list using the configured `gz topic -l` command and inspects every discovered absolute topic with `gz topic -i -t <topic>`. Selection uses only the exact message-type token `gz.msgs.LaserScan`; a unique match is returned as `OBSERVED_NOT_PINNED`, never as a source pin.

A future probe execution is permitted only under a separate `APPROVED_RUNTIME` packet that is capacity-one and states the exact command, pass/fail criteria, stop conditions, and explicit User approval. Any observed endpoint requires separate Owner review/decision before WP06-6E may implement the ROS–Gazebo bridge. WP06-6E remains the sole owner of canonical ROS–Gazebo bridge implementation.

## Static authority and prohibitions

At the exact base, the unchanged LiDAR source declares `lidar_frame`, `YDLIDAR_X3_PRO`, `gpu_lidar`, relative topic `scan`, 6.0 Hz, 500 horizontal samples, and range 0.10–8.00 m. The existing static bridge contract still leaves the Gazebo endpoint and profile-specific bridge implementation pending. The legacy `ros_gz_bridge_gazebo.yaml` is a clock-only bridge config and is not scan-bridge evidence.

This candidate creates no `gz_transport_endpoint` pin, bridge config, `ros_gz_bridge` implementation, `/scan` ROS publisher, TF, header/frame validation, cadence/latency/no-return validation, runtime evidence, runtime profile, `ResolvedConfigV3`, `config_hash`, Gate B transition, or runtime authorization. No ROS publisher/subscriber, Map Server, AMCL, EKF, or Nav2 component is added. WP04/WP05, Gate A, Gate B, and `RUNTIME_APPROVED: NOT_APPROVED` are unchanged.
