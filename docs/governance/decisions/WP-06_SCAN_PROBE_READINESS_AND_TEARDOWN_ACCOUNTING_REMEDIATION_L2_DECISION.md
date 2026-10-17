# WP06 6D Scan Probe Run 004 — readiness and teardown accounting remediation

**Classification:** `L2_RUNTIME_OBSERVABILITY_AND_PROCESS_OWNERSHIP_REMEDIATION`
**Evidence level:** `IMPLEMENTED_OFFLINE_GUARD_AND_SESSION_SOURCE_ONLY`
**Source base:** `db464f741e24a81b3f9587f827fc145c533d8d6c`
**Run:** `WP06_6D_SIM_EVAL_SCAN_ENDPOINT_PROBE_RUN_004`
**Partition:** `wp06_scan_probe_run_004`

## Decision

Create a new, independent capacity-one Run 004 session contract. Run 002 and Run 003 are immutable historical runs and are outside this candidate's source and runtime scope. Run 003 remains a historical failure because its probe was not executed and it produced no endpoint result. Its `bootstrap_readiness: false` is a readiness-accounting false negative in the presence of buffered/shared bootstrap output; it is not evidence that LiDAR failed. Its `STILL_RUNNING_AFTER_SIGKILL_WAIT` accounting did not reap the direct child or enumerate `/proc` process-group members, so it is not proof that a Run 003 process remained alive. Neither finding changes or reinterprets the original Run 003 record.

Run 004 replaces log-based readiness with service-gated creation. The new server-only launch starts the existing Fuel-free local probe world, sets the exact partition before Gazebo startup, and starts `robot_state_publisher`; it does not spawn the robot. The session runner polls only the bounded `gz service --list` command for the exact `/world/wp06_scan_probe_world/create` service. It then invokes one `ros2 run ros_gz_sim create` process group. Spawn readiness requires both exit code zero and the exact bytes `Entity creation successful.` in that command's own raw transcript. Server logs are not used to infer spawn readiness.

The runner writes bootstrap and create stdout directly to files, records bounded service-list attempts and hashes, and never uses a pipe reader for readiness. Teardown verifies the newly created process-group identity, reaps direct children, and snapshots Linux `/proc/<pid>/stat` members using the text after the final `)` delimiter. Live and zombie members are reported separately. Teardown passes only when the direct leader is reaped and the exact group has no live members; a zombie alone is not classified as live. A missing `/proc` view fails closed.

## Guard and future authorization boundary

Run 004 is future-only. Its capacity-one guard seed is `PENDING_EXACT_INTEGRATION_AND_USER_AUTHORIZATION`. This candidate does not consume the guard and grants no runtime authorization. A future invocation requires independent audit, integration of the exact candidate, verified exact integration refs, a clean worktree, and a separate Owner authorization for that exact integration commit. The guard is consumed immediately before starting the session and cannot be retried after consumption, including on timeout or error.

A future result can establish at most `GZ_LASERSCAN_ENDPOINT_OBSERVED_NOT_PINNED`. It does not pin a Gazebo endpoint or establish ROS `/scan`, `ros_gz_bridge`, TF, AMCL, EKF, Nav2, runtime compatibility, runtime evidence beyond the bounded probe session, `ResolvedConfigV3`, `config_hash`, Gate B transition, or `RUNTIME_APPROVED`.

## Fixed source pins

| Role | Repository path | SHA-256 |
|---|---|---|
| Existing local probe world | `ros2_ws/src/ROBOT_URDF_final_description/launch/sim_eval_scan_probe.world.sdf` | `9978241fe970a24bb2b5f0aefcba41f69164bf5784e3bf6440596f6a975e2736` |
| Gazebo LiDAR sensor source | `ros2_ws/src/ROBOT_URDF_final_description/urdf/ROBOT_URDF_final.gazebo` | `1e97b6ea340adc9aecaf320cc432007c6bb37f5922cdc0366dbee50a9a26ff0e` |
| Static probe descriptor | `ros2_ws/src/mecanum_nav_bringup/config/bridge/sim_eval_scan_endpoint_probe.static.yaml` | `7e61c620fa03643b4b834ac4a804b252126cde4b224f59bd56c4a431abf20343` |
| Static probe module | `ros2_ws/src/mecanum_nav_bringup/mecanum_nav_bringup/sim_eval_scan_endpoint_probe.py` | `6584ac43ec68080c5915c934b01b52a08a9c48d4d2fb5c3b279bf238326000b2` |
| Run 004 server-only launch | `ros2_ws/src/ROBOT_URDF_final_description/launch/sim_eval_scan_probe_run004_server.launch.py` | `343ec10823e1e3907f158b2025855025468fd18595957c0bda071cad614fb6f8` |

The authority decision is separately pinned by the Run 004 manifest and guard after this decision file is finalized. Its digest is intentionally not embedded in this file.

## Status

This is a review candidate containing source, offline tests, and offline build evidence only. Run 003 artifacts are not reset, edited, copied, or reinterpreted. No ROS, Gazebo, `gz`, launch, probe, bridge, Nav2, AMCL, EKF, or Map Server process was run while preparing this candidate.

Statuses remain unchanged: `WP-04: BLOCKED_BY_CONTRACT`; `WP-05: OPEN`; `GATE_A: PASSED`; `GATE_B: NOT_STARTED`; `RUNTIME_APPROVED: NOT_APPROVED`. WP06-6E remains the sole owner of canonical ROS–Gazebo bridge implementation.
