# WP06 sim_eval scan endpoint probe — deterministic bootstrap remediation

## Decision

- Classification: `L2_SIM_EVAL_SCAN_ENDPOINT_PROBE_DETERMINISTIC_BOOTSTRAP_REMEDIATION`
- Exact source base: `be5f63e7a01be0bca0b838e1ae5265bbb7145be8`
- Evidence level: `IMPLEMENTED_OFFLINE_GUARD_AND_BOOTSTRAP_SOURCE_ONLY`
- Review branch: `wp06-scan-probe-deterministic-bootstrap-be5f63e`

This L2 candidate replaces only the future probe bootstrap boundary. The prior Run 001 bootstrap referenced the legacy `tugbot_depot.sdf`, whose remote Fuel includes for Depot and Tugbot made server readiness depend on network/cache state. Its `ros_gz_sim create` action also had to discover the world name. This candidate supplies a small local, Fuel-free probe world and names the world explicitly at creation.

## Bounded source behavior

The new `sim_eval_scan_probe.world.sdf` contains only the required physics, user-command, scene-broadcaster and `ogre2` sensor systems, plus an inline local ground plane. It contains no includes, URIs, network URLs, remote assets, Tugbot, Depot or navigation environment. It is only a probe bootstrap world and makes no navigation-fidelity or Nav2-readiness claim. `tugbot_depot.sdf` is unchanged.

The bootstrap unconditionally sets `GZ_PARTITION=wp06_scan_probe_run_002`, starts one `robot_state_publisher` with `use_sim_time: True`, includes one server-only Gazebo launch using `-r -s -v 4` and the local world, and asks one `ros_gz_sim create` action for world `wp06_scan_probe_world` and entity `ROBOT_URDF_final` with renaming disabled. It has no fixed-delay readiness substitute. A future runtime bootstrap is ready only after the create process reports the exact line `Entity creation successful.`; this candidate does not run launch or establish that evidence.

## Guard lineage and future-only conditions

Run 001's guard remains byte-identical to the source base and unconsumed. After this exact replacement candidate is integrated, Run 001 is `NOT_CONSUMED_AND_INVALIDATED_BY_EXACT_INTEGRATION_MISMATCH`, because its source/partition context is bound to the previous integration and bootstrap. Run 002 is seeded only as `PENDING_EXACT_INTEGRATION_AND_USER_AUTHORIZATION`, capacity one. This review candidate is not a runtime authorization; only the Owner may authorize a future runtime after integration.

A future Run 002 requires all of the following before its compatible one-shot supervisor is called once: exact integrated commit; clean worktree; Run 002 guard still pending; and the bootstrap log's `Entity creation successful.` line. Any source, integration, command or partition mismatch must fail closed. A consumed guard may never be retried. The existing Run 001 supervisor is not changed by this candidate; any later Run 002 supervisor use must be compatible with the exact Run 002 guard and separately authorized.

## Non-claims

This candidate creates no endpoint pin, ROS `/scan`, ROS–Gazebo bridge, TF publisher or measurement, runtime evidence, runtime authorization, runtime profile, `ResolvedConfigV3`, `config_hash`, Gate B transition or general runtime approval. WP06-6E remains the sole owner of canonical ROS–Gazebo bridge implementation. Run 002 is future-only and not runtime-authorized. WP-04 remains `BLOCKED_BY_CONTRACT`; WP-05 remains `OPEN`; Gate A remains `PASSED`; Gate B remains `NOT_STARTED`; `RUNTIME_APPROVED: NOT_APPROVED`.
