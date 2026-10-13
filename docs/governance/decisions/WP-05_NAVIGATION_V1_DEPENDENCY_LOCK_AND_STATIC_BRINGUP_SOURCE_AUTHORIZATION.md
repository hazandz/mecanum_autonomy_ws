# WP-05 — Navigation V1 dependency-lock schema and static bringup source authorization

| Field | Value |
|---|---|
| Work package | `WP05-NAVIGATION-V1-DEPENDENCY-LOCK-AND-STATIC-BRINGUP-SOURCE-AUTHORIZATION` |
| Change class | `L1_IMPLEMENTATION_SOURCE_AUTHORIZATION_WITHIN_ACTIVE_L2_NAVIGATION_ENVELOPE` |
| Exact integration base | `2a537a9cfa9f9c5b0bec1f9c629fec8e2f98a225` |
| Architecture authority | `docs/MECANUM_NAV_DRL_Architecture.docx`; SHA-256 `432eeac363a595cfcf7e81c4b66054fb674dba140a2ef3cffecd617ab8136204` |
| WP-05 active L2 ACR | `docs/architecture/ACR_NAVIGATION_V1_RUNTIME_BINDING.md`; SHA-256 `3e74cdcb6136f60a6ad2822a853f2ae9926cf971059f3c2470c874802d6fae0d` |
| WP-05 active L2 semantic manifest | `docs/architecture/NAVIGATION_V1_RUNTIME_BINDING_SEMANTIC_MANIFEST.json`; SHA-256 `33855c9c95f9c0594ddd8805514658e4f5cb8255a219938a7913438470edbf31` |
| WP-04 active ingress-source authorization | `docs/governance/decisions/WP-04_OIC_V3_NONEXECUTING_OBSERVATION_INGRESS_SOURCE_AUTHORIZATION.md`; SHA-256 `d6df3bf6811918adb044ea890f8be8b3ed67342820641f9b46e47f6fbd1ddde4` |
| Map subject fingerprint | `artifacts/maps/warehouse_map2/map_manifest.json`; `map_content_hash` `2bd9ff0a40eaeb61c2359aab4bb213da623ab56746debe591edd4a54c2229f90` |
| Candidate status at base | Review-only governance candidate; no authorization extension before exact-candidate audit, separate User authorization, fast-forward, and remote-ref verification |

## 1. Decision scope and authority boundary

This candidate records the Owner decisions for a future Navigation V1 dependency-lock schema, the future package ownership/layout of `mecanum_nav_bringup`, and a conditional, bounded source-level authorization. It creates only this decision, the JSON schema, Registry/PEP routing, and an append-only Ledger entry. It creates no package, source, launch, runtime YAML, dependency-lock instance, package/version pin, resolved profile, profile `config_hash`, map approval, or runtime evidence.

The active Architecture DOCX has precedence. The integrated WP-05 L2 runtime-binding authority supplies target bindings only. This L1 decision does not alter those bindings or their activation state, and does not resolve any pending implementation source or measurement.

## 2. Package ownership and future source layout

The Owner-selected future package ownership is:

- `mecanum_nav_bringup`: Navigation V1 launch, Map Server, AMCL/localization, EKF, lifecycle/startup, Nav2, and mode configuration.
- `mecanum_nav_rl`: DRL, pure core, and observation adapters; no DRL/training ownership is moved into bringup.
- `mecanum_base_bridge`: Pi–STM32 transport and future raw wheel-odometry source; it does not publish TF.
- `ROBOT_URDF_final_description`: robot geometry and future canonical `base_link → lidar_frame` robot-description source.
- Map bytes remain solely under `artifacts/maps/<map_id>/`; no ROS package map copy is permitted.

After this exact authorization becomes effective, the bounded future static-source candidate may use only this layout:

```text
ros2_ws/src/mecanum_nav_bringup/
├── package.xml
├── setup.py
├── resource/mecanum_nav_bringup
├── mecanum_nav_bringup/__init__.py
├── launch/navigation_v1.launch.py
├── launch/navigation_v1_lifecycle.launch.py
├── config/state_estimation/ekf_sim.yaml
├── config/state_estimation/ekf_real.yaml
├── config/localization/amcl_omni.yaml
├── config/navigation/nav2_baseline.yaml
├── config/lifecycle/navigation_v1_startup.yaml
├── config/remaps/navigation_v1.yaml
└── test/
    ├── test_package_layout.py
    ├── test_dependency_lock_schema.py
    ├── test_map_artifact_reference.py
    ├── test_tf_owner_contract.py
    ├── test_navigation_v1_static_config.py
    ├── test_remap_namespace_schema.py
    ├── test_lifecycle_startup_contract.py
    └── test_legacy_exclusion.py
```

This is a future allowlist only. No path above is created by this governance candidate. Its authorization is for static source and static acceptance tests; it does not authorize invoking launch files or running ROS/Nav2/AMCL/EKF/Gazebo.

## 3. Dependency-lock schema

`docs/governance/evidence/WP-05_NAVIGATION_V1_DEPENDENCY_LOCK_SCHEMA.json` defines the structure for a future lock document. It is a schema, not a package lock or resolved profile. Its fixed direct dependency roots are exactly:

`nav2_bringup`, `nav2_amcl`, `nav2_map_server`, `nav2_lifecycle_manager`, `nav2_planner`, `nav2_controller`, `nav2_bt_navigator`, `nav2_costmap_2d`, `robot_localization`, `tf2_ros`, `robot_state_publisher`, `sensor_msgs`, `nav_msgs`, and `geometry_msgs`.

`slam_toolbox` is a separate MAPPING dependency and is excluded from the common Navigation V1 runtime lock. `ros_gz_bridge` and `ros_gz_sim` are profile-specific dependencies and must not be silently added to that common lock.

Every future external package-lock entry must contain `ros_distribution`, `ubuntu_release`, `ros_package_name`, `debian_package_name`, `installed_version`, `architecture`, `apt_repository_origin`, `deb_sha256`, `dependency_closure_sha256`, and `evidence_capture_method`. Every future workspace-source-lock entry must contain `repository_commit`, `repository_relative_path`, `source_file_sha256`, `owner_package`, `role`, and `status`.

No actual package version, installed version, `.deb` hash, source SHA, geometry, AMCL/EKF parameter, or launch composition is selected or populated here. Outstanding external package evidence is `PENDING_EXTERNAL_PACKAGE_LOCK`; workspace source selection/pinning is `PENDING_IMPLEMENTATION_SOURCE_PIN`. Evidence must identify immutable bytes and capture provenance. Mutable branch/tag references cannot serve as immutable source locks. Legacy material is excluded as an implementation lock unless a later authority explicitly selects and pins it.

## 4. Static acceptance criteria for a later code candidate

A later, separately reviewed static-source candidate must provide checks for:

1. package-layout completeness against the bounded layout above;
2. dependency-lock schema validity and required-field completeness;
3. rejection of mutable branch/tag references as locks;
4. canonical-artifact-root-only map reference;
5. consistency with declared TF-owner contracts;
6. static AMCL/EKF/Nav2 target consistency;
7. an explicit remap/namespace table;
8. lifecycle startup order and health-inhibition completeness;
9. exclusion of legacy sources from canonical configuration.

These are static acceptance expectations, not tests run by this candidate and not runtime evidence.

## 5. Conditional bounded source authorization

At exact base `2a537a9cfa9f9c5b0bec1f9c629fec8e2f98a225`, the currently integrated WP-04 authorization is:

```text
CODE_AUTHORIZATION: GRANTED_BOUNDED_FAIL_CLOSED_INTERNAL_SEAMS_AND_NONEXECUTING_OBSERVATION_INGRESS_ADAPTER_SOURCES_ONLY
RUNTIME_APPROVED: NOT_APPROVED
```

This candidate conditionally extends only the static-source scope. Only after independent audit PASS for the exact candidate, separate explicit User authorization for that exact commit, fast-forward, and remote integration-ref verification does the status become:

```text
CODE_AUTHORIZATION: GRANTED_BOUNDED_FAIL_CLOSED_INTERNAL_SEAMS_NONEXECUTING_OBSERVATION_INGRESS_AND_STATIC_NAVIGATION_V1_BRINGUP_SOURCES_ONLY
RUNTIME_APPROVED: NOT_APPROVED
```

After those conditions, the new scope permits creation of static bringup sources and static acceptance tests only within the listed layout. It does not permit running launch/ROS/Nav2/AMCL/EKF/Gazebo, creating a runtime node graph, resolving a profile or global `config_hash`, approving a map, or HIL/hardware/deploy. It does not replace the existing internal-seam and nonexecuting-ingress boundaries.

## 6. Fail-closed rules and pending work

Missing required lock, source pin, measurement, or evidence means: no resolved Navigation V1 profile, no profile `config_hash`, no Map Server/AMCL/EKF/Nav2 bring-up, no map approval, and no runtime authorization. No default, alias, legacy fallback, inferred package version, or fabricated pin may close a gap.

The following remain pending: external package lock evidence; implementation-source pins; AMCL/EKF parameters; geometry and scan/TF adapter sources; remap/namespace; lifecycle/startup sources; and required runtime measurements. `warehouse_map2` remains draft and not approved/navigation-ready; `WORLD_FRAME: NOT_DECLARED`; `RUNTIME_COMPATIBILITY: NOT_VALIDATED`; WP-05 `OPEN`; WP-04 `BLOCKED_BY_CONTRACT`, Gate A `PASSED`, Gate B `NOT_STARTED`.

## 7. Activation and non-goals

This candidate is review-only at base `2a537a9…`. Review push, ancestry, or a status string in this candidate alone does not activate the extension. The post-integration token is conditional on all four exact-candidate lifecycle events stated above. Integration would be an L1 source-authorization/lock-schema governance record only; it would not mean external package locks are complete, an executable profile exists, runtime is approved, or runtime evidence exists.

No Architecture, L2 binding, map bytes/metadata/manifest/hash, WP-04 file, code, test, ROSIDL, package manifest, launch file, runtime config, WP status/dependency, or runtime authority is changed by this candidate.
