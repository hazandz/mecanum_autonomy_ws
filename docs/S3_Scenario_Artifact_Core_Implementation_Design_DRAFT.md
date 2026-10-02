# S3 Scenario Artifact Core Implementation Design

**Status: `DRAFT — CORE-ONLY IMPLEMENTATION DESIGN, RUNTIME NOT APPROVED`**

## 1. Purpose and authority

This document designs a later pure-Python increment that parses and validates an immutable scenario artifact. It creates no artifact, source code, configuration, runtime ingress, or simulation process.

Authority and inputs:

- [MECANUM_NAV_DRL_Architecture.docx](MECANUM_NAV_DRL_Architecture.docx), schema `3.0`, SHA-256 `f0fb1ebede5f4fa18604610c04bb13587d456173b4fd942dba77e44d49777860`.
- [Scenario v1 user decision packet](S3_Scenario_V1_User_Decision_Packet_DRAFT.md).
- [Scenario artifact contract](S3_Simulation_Scenario_Artifact_Contract_DRAFT.md).
- [Training task oracle core design](S3_Training_Task_Oracle_Core_Design_DRAFT.md).

The architecture permits hidden Ground Truth only for the simulation task/oracle, reset validation, reward/success/termination, and evaluation boundaries. It remains prohibited from `SnapshotSynchronizer`, `ObservationAssembler`, `ObservationEncoder`, PPO, policy input, and policy runtime.

## 2. Scope and non-goals

`ScenarioArtifact` is data-only, immutable, versioned, and verified against a canonical content hash. `candidate_task_bounds` is deliberately candidate metadata, not `valid_area`. `GT_ODOM_2D` is only a hidden-oracle reference identity; it is not a ROS topic, policy feature, frame conversion, or PPO input.

This increment must not import ROS, Gazebo, TF, Gymnasium, Stable-Baselines3, Ground Truth message/object types, or policy-observation modules. It must not implement runtime ingress, reset, collision, clearance, reward, termination, a Gym environment, or any hardware path.

## 3. Ownership and proposed API

The future owner is a pure task/scenario data boundary inside `mecanum_nav_rl`; it receives untrusted artifact text or a mapping and explicit expected world identity, and returns only immutable validated data or an explicit load result. It emits no ROS object, command, or task fact.

| Type or component | Proposed responsibility |
| --- | --- |
| `ScenarioArtifactIdentity` | Immutable identity: artifact schema version, `scenario_id`, `scenario_version`, `scenario_content_sha256`, `gazebo_world_name`, `world_file_sha256`, and `coordinate_reference_id`. |
| `ScenarioTaskDefinition` | Immutable task values: 2D goal, goal radius/rule identifier, named `candidate_task_bounds`, boundary semantics, forbidden-zone declaration, start catalog, and randomization declaration. |
| `ScenarioArtifact` | Immutable composition of identity and task definition; it has no timestamp, local path, reset epoch, runtime generation, raw GT, or runtime receipt. |
| `ScenarioArtifactLoadStatus` | Explicit result status: `READY`, `INVALID_INPUT`, `UNKNOWN_SCHEMA_VERSION`, `HASH_MISMATCH`, `WORLD_IDENTITY_MISMATCH`, `COORDINATE_REFERENCE_MISMATCH`, `MALFORMED_TASK_DEFINITION`, or `FORBIDDEN_ZONE_INVALID`. |
| `ScenarioArtifactLoadResult` | Immutable status plus `artifact: ScenarioArtifact \| None` and a non-sensitive diagnostic code; never returns a partial artifact. |
| `ScenarioArtifactLoader` / validator | Pure parser and validator. It verifies schema, types, canonical hash, and caller-supplied expected world/reference values. It does not read a ROS parameter, topic, or simulator state. |

Use Pydantic models following the existing `ConfigModel` convention: frozen models, `extra="forbid"`, default validation, strict field validators, and explicit model-level cross-field validation. The loader follows the existing `config.loader` boundary by accepting a mapping or artifact text, not by letting arbitrary runtime code read a file independently.

## 4. Proposed artifact schema

The following is a future data shape only. It records the user-selected values for core validation tests; it does not make them runtime-ready.

| Member | Proposed value or rule | Validation |
| --- | --- | --- |
| `artifact_schema_version` | `s3_scenario_artifact/v1` | Exact known literal; unknown version is rejected. |
| `scenario_id` | `world_demo_candidate_b_v1` | Non-empty trimmed string. |
| `scenario_version` | `1.0.0` | Non-empty explicit version string; no implicit latest version. |
| `gazebo_world_name` | `world_demo` | Exact caller-expected identity; not a ROS frame. |
| `world_file_sha256` | `a5e9c9b1e9b8ad11e0399855f06de687f04c702258b8b74ce563523d78ed55fe` | Lowercase 64-hex SHA-256 and exact caller-expected value. |
| `coordinate_reference_id` | `GT_ODOM_2D` | Exact known hidden-oracle-only literal. |
| `goal` | P2 x/y `(-2.0 m, -3.0 m)`, radius `0.25 m`, explicit goal-rule identifier | Finite real x/y; finite positive radius; no z. |
| `start_pose_catalog` | One explicit P0 item `(-4.0 m, -3.0 m, yaw 0.0 rad)` | Finite x/y/yaw, unique start ID, no default/silent sampling rule. |
| `candidate_task_bounds` | Axis-aligned rectangle: x `[-4.5 m, -1.5 m]`, y `[-3.5 m, -2.5 m]`, `boundary_invalid` | Finite bounds with strict min < max; preserved name must not become `valid_area`. |
| `forbidden_zones` | Empty list plus explicit `none_provisional` declaration | Empty is valid only with the matching declaration; any supplied zone needs unique ID, known shape, finite geometry, and explicit boundary rule. |
| `randomization` | Explicit `disabled` for v1 | Only the known disabled declaration is accepted in this increment. |
| `scenario_content_sha256` | Full computed SHA-256 | Verified; never trusted merely because supplied. |

No `z`, obstacle map, clearance result, contact event, collision rule, reset receipt, simulation timestamp, runtime generation, reset epoch, path, host name, or hardware metadata belongs in this artifact.

## 5. Canonical serialization and hash contract

The proposed artifact hash is deterministic and testable within the project implementation:

1. Validate untrusted input against the Pydantic artifact schema, except for the supplied `scenario_content_sha256` field.
2. Build `hash_payload` with exactly `artifact_hash_version: "s3_scenario_artifact_hash/v1"` and `artifact`, where `artifact` contains every validated logical member listed in section 4 except `scenario_content_sha256` itself.
3. Serialize `hash_payload` as UTF-8 JSON using `sort_keys=True`, `separators=(",", ":")`, `ensure_ascii=True`, and `allow_nan=False`, matching the existing config-hash convention.
4. Compute lowercase full SHA-256 over those UTF-8 bytes. The supplied hash must equal the computed 64-character digest exactly; otherwise return `HASH_MISMATCH` and no artifact.

The hash therefore includes schema/version, scenario identity/version, world identity/hash, coordinate-reference ID, goal, start catalog, candidate-bounds name/type/literals/boundary semantics, forbidden-zone declaration/data, and randomization declaration. It excludes its own digest, approval prose, timestamps, local/absolute paths, process IDs, environment variables, runtime generation, reset epoch, service receipts, and all runtime evidence. A hash change is a different artifact and may take effect only in a new runtime generation under the user-selected fail-closed policy; this increment does not implement that lifecycle enforcement.

## 6. Fail-closed validation

| Condition | Required result |
| --- | --- |
| Missing/extra field, wrong container/type, bool where a number is required, NaN, infinity, empty identifier, or malformed SHA | `INVALID_INPUT` or `MALFORMED_TASK_DEFINITION`; no partial artifact. |
| Unknown artifact schema or hash-contract version | `UNKNOWN_SCHEMA_VERSION`; no best-effort migration. |
| Supplied hash differs from canonical hash | `HASH_MISMATCH`; no fallback to a previous artifact. |
| Supplied world name/hash differs from explicit expected world context | `WORLD_IDENTITY_MISMATCH`; no world-name/frame conversion. |
| Coordinate reference differs from expected `GT_ODOM_2D` | `COORDINATE_REFERENCE_MISMATCH`; no alternate reference/default. |
| Invalid candidate bounds, goal, start pose, randomization declaration, or forbidden-zone rule | `MALFORMED_TASK_DEFINITION` or `FORBIDDEN_ZONE_INVALID`; no default values. |

The loader must never reuse an old artifact after a failed load, infer values from SDF/visual geometry/legacy waypoints, convert `world_demo` to `world`, or expose scenario internals to policy observation.

## 7. Expected code increment and tests

No files are created by this design. A separately authorized core-only increment would be limited to:

| Expected path | Responsibility |
| --- | --- |
| `ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/tasks/__init__.py` | Future pure task-data package export; currently absent. |
| `ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/tasks/scenario_artifact.py` | Future immutable Pydantic schema, canonical serializer/hash helper, and loader/validator. |
| `ros2_ws/src/mecanum_nav_rl/test/test_scenario_artifact.py` | Future focused pure-Python tests. |
| `ros2_ws/src/mecanum_nav_rl/test/test_colcon_runner.py` | Register the new test only if the existing runner requires it. |

| Test | Required assertion |
| --- | --- |
| Valid Candidate B parse | Test-only fixture with the selected values yields one immutable artifact and full canonical hash. |
| Canonical-hash stability | Equivalent mappings with different input key order serialize to identical canonical JSON and SHA-256. |
| Hash mismatch | One changed logical value or supplied digest mismatch returns `HASH_MISMATCH`, with no artifact. |
| Unknown schema | Unknown schema/hash-contract versions return `UNKNOWN_SCHEMA_VERSION`; no migration. |
| Numeric/type rejection | Malformed coordinates, bools, NaN, infinities, and invalid min/max fail closed. |
| Forbidden-zone validation | Empty `none_provisional` declaration is distinct from malformed/duplicate/unknown-shape zone data. |
| Candidate-bounds terminology | Schema and result preserve `candidate_task_bounds`; no field/property called `valid_area`. |
| World/reference mismatch | Expected `world_demo`/hash and `GT_ODOM_2D` mismatches return explicit non-ready statuses. |
| Ground-Truth and policy isolation | Source scan proves no ROS/Gazebo/Gymnasium/SB3/GT/policy-observation imports and no raw GT field/reference in the artifact/result. |

## 8. Runtime boundary retained

A successful core parse would not make an artifact runtime usable. The following remain blocked: clearance metric/threshold/evidence; ContactLatch collision source and filter policy; reset receipt and settle policy; runtime LiDAR-frame reconciliation for observed `ROBOT_URDF_final/RPLiDAR_A1M8_1/rplidar`; and lifecycle binding among scenario hash, reset epoch, and runtime generation. No reward, termination, Gymnasium, Gazebo, ROS, or hardware work follows from this design.

## 9. Conclusion

**`READY_FOR_CORE_IMPLEMENTATION_APPROVAL`**

The selected provisional values and existing Pydantic/canonical-hash conventions are sufficient for a narrowly scoped, test-only parser/validator increment. That approval would cover only pure-core data validation and tests. It would not authorize creating a runtime scenario artifact or resolving any retained runtime blocker.
