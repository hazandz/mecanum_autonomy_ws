# WP06 sim_eval Scan endpoint probe runtime bootstrap and capacity-one guard

## Classification and evidence boundary

- Classification: `L2_SIM_EVAL_SCAN_ENDPOINT_PROBE_RUNTIME_BOOTSTRAP_AND_CAPACITY_ONE_GUARD`.
- Evidence level: `IMPLEMENTED_OFFLINE_GUARD_AND_BOOTSTRAP_SOURCE_ONLY`.
- Exact source base: `bfc1ef3cfe4ba98beefbe7f18607b97a41e52d15`.
- This record is the authority packet for the exact future one-shot supervisor context. It is not an `APPROVED_RUNTIME` packet and does not authorize execution from this review candidate.

## Exact future runtime boundary

The future run ID is exactly `WP06_6D_SIM_EVAL_SCAN_ENDPOINT_PROBE_RUN_001`, capacity is one, and the partition is exactly `wp06_scan_probe_run_001`. The future command literal is:

```text
env GZ_PARTITION=wp06_scan_probe_run_001 PYTHONPATH={repo_root}/ros2_ws/src/mecanum_nav_bringup python3 -m mecanum_nav_bringup.sim_eval_scan_endpoint_probe
```

The expected Gazebo type is `gz.msgs.LaserScan`; the future ROS boundary is `GZ_TO_ROS /scan sensor_msgs/msg/LaserScan`. The Bootstrap source sets `GZ_PARTITION` unconditionally before including exactly one `ros_gz_sim/gz_sim.launch.py`, creates exactly one `robot_state_publisher` with `use_sim_time: false`, and creates exactly one entity named `ROBOT_URDF_final` with renaming disabled. It remains bridge-free.

The authority packet and all locked source/context bytes must be re-verified from the exact integrated commit before a supervisor can consume the guard. The required caller argument is an exact 40-hex integration commit and represents the future user's exact-commit authorization. A review checkout, a HEAD that differs from that commit, or an `origin/integration/implementation` ref that differs from it is rejected before any state transition, run directory creation, or subprocess call.

## Capacity-one state machine

The seed state is exactly `PENDING_EXACT_INTEGRATION_AND_USER_AUTHORIZATION`. After all preconditions pass, the supervisor atomically changes it to `CONSUMED` immediately before the probe subprocess. It stays `CONSUMED` for pass, fail, timeout, interruption, and supervisor errors; retry is forbidden. The launcher timeout is 75 seconds and any timeout cleanup is launcher-managed escalation, not SIGINT-only.

An `EXACTLY_ONE_MATCH` result can create only an `OBSERVED_NOT_PINNED` observation. It creates no endpoint pin, `ros_gz_bridge`, ROS `/scan` publisher, TF measurement, cadence/latency evidence, resolved profile, `ResolvedConfigV3`, `config_hash`, Gate B transition, or runtime authorization. An Owner decision remains required before WP06-6E, which remains the sole owner of canonical ROS–Gazebo bridge implementation.

## Preserved project status

`WP-04: BLOCKED_BY_CONTRACT`; `WP-05: OPEN`; Gate A: `PASSED`; Gate B: `NOT_STARTED`; `RUNTIME_APPROVED: NOT_APPROVED`.

After independent audit, exact integration, remote-ref verification, and a separate future exact-commit User authorization, the guard status may be recorded only as `RUNTIME_GUARD_IMPLEMENTED_AWAITING_EXACT_USER_AUTHORIZATION`. This candidate itself creates no runtime evidence.
