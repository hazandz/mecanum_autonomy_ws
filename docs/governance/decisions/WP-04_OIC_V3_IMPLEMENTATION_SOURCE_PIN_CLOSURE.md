# WP-04 OIC V3 Implementation Source Pin Closure

## Classification and scope

`L1_IMPLEMENTATION_SOURCE_PIN_CLOSURE_DOCUMENTATION_ONLY` records implementation-source byte provenance present at exact integration/source base `8675047aa61835621f6d1e31aff567b75c87094c`. The companion manifest, `docs/governance/evidence/WP-04_OIC_V3_IMPLEMENTATION_SOURCE_PIN_MANIFEST.json`, is a provenance inventory, not a runtime source selection or resolved profile.

This record changes no OIC semantics, active L2 runtime-binding authority, TF/lifecycle/safety ownership, public interface, or global `config_hash` policy. It creates no code, test, runtime config, map disposition, package-lock instance, measurement, or runtime evidence.

## Authority and evidence boundary

The frozen Architecture remains the highest authority. OIC V3 and its semantic manifest, WP-04 runtime-binding authority, the static-reference manifest, bounded WP-04 authorization decisions, and WP-05 Navigation V1 L2 runtime-binding authority are fingerprinted in the companion manifest. These fingerprints identify referenced bytes; they do not create or activate authority.

Every listed source is `PINNED_IMPLEMENTATION_SOURCE_ONLY`, with runtime implication `NOT_A_RUNTIME_SOURCE_PIN`. The entries establish exact path/bytes/source provenance at the base only; they do not establish ROS-graph, navigation, TF, or robot behavior.

- The eight `mecanum_nav_rl` pure-core and nonexecuting ingress files do not prove actual `/scan`, global-path, EKF-output, or TF runtime behavior.
- The seven `mecanum_nav_bringup` workspace scaffold/template/validator/launch files are not Nav2, Map Server, AMCL, `robot_localization`, RSP, TF2, ROS-distribution, or other external package-version locks.
- Test files are intentionally not represented as runtime-source pins.

## Pending groups and fail-closed boundary

- `PENDING_EXTERNAL_PACKAGE_LOCK`: Nav2, Map Server, AMCL, `robot_localization`, RSP, TF2, and other external dependencies.
- `PENDING_RUNTIME_SOURCE_PIN`: LiDAR driver, Nav2 path producer, concrete AMCL/EKF/RSP config or launch, lifecycle/startup source, remap/namespace policy, and map binding.
- `PENDING_MEASUREMENT`: LiDAR cadence/latency/range/extrinsic, scan–twist skew, buffer, TF graph, publisher uniqueness, lifecycle health, and localization quality.

Any missing required pending group remains fail-closed: no resolved profile, no global `config_hash`, no Gate B bring-up, and no acceptance/runtime conclusion. No default, alias, external package version, `.deb` digest, ROS-distribution lock, driver pin, runtime-node config, map approval, or measurement is inferred or supplied here.

WP-05 source provenance does not change target ownership: AMCL remains target owner of `map → odom`, EKF of `odom → base_link`, and RSP of `base_link → lidar_frame`. It does not imply `map == world` or approve `warehouse_map2`.

## Lifecycle and status

At source base `8675047aa61835621f6d1e31aff567b75c87094c`, this record is a review-candidate snapshot. Only after independent audit PASS for the exact candidate, separate exact-commit User authorization, fast-forward, and remote-ref verification is it an integrated L1 implementation-source-pin governance record. That lifecycle does not alter active L2 semantics or grant runtime authorization.

Status remains: WP-04 `BLOCKED_BY_CONTRACT`; Gate A structural primitives `PASSED`; Gate B `NOT_STARTED`; WP-05 `OPEN`; map artifact `DRAFT_ON_INTEGRATION_NOT_APPROVED`; `WORLD_FRAME: NOT_DECLARED`; `RUNTIME_COMPATIBILITY: NOT_VALIDATED`; `RUNTIME_APPROVED: NOT_APPROVED`. This record grants or expands no `CODE_AUTHORIZATION`.
