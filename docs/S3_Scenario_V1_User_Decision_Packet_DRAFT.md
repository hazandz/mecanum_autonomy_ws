# S3 Scenario V1 User Decision Packet

**Status: `DRAFT — PENDING_USER_DECISIONS, NO SCENARIO ARTIFACT OR RUNTIME APPROVAL`**

## 1. Purpose and authority

This packet asks the user to select provisional scenario-v1 values for later core/design work. It does not create a scenario artifact, approve a runtime, or convert controlled-measurement evidence into free-space, clearance, collision, valid-area, or reset evidence.

Authority and evidence reviewed:

- [MECANUM_NAV_DRL_Architecture.docx](MECANUM_NAV_DRL_Architecture.docx), schema `3.0`, SHA-256 `f0fb1ebede5f4fa18604610c04bb13587d456173b4fd942dba77e44d49777860`.
- [Candidate B replacement evidence review](S3_Candidate_B_Replacement_Evidence_Review_DRAFT.md).
- [Simulation scenario artifact contract](S3_Simulation_Scenario_Artifact_Contract_DRAFT.md).
- [First simulation scenario candidate and evidence plan](S3_First_Simulation_Scenario_Candidate_And_Evidence_Plan_DRAFT.md).
- [First scenario candidate review](S3_First_Scenario_Candidate_Review_DRAFT.md).
- [Candidate B replacement approval packet](S3_Candidate_B_Replacement_Run_Approval_Packet_DRAFT.md), [original Candidate B packet](S3_Candidate_B_Controlled_Suitability_Run_Approval_Packet_DRAFT.md), and the [immutable manifest](../artifacts/simulation/candidate_b_controlled_suitability/measurement_manifest.json).
- [Candidate B replacement evidence report](../artifacts/simulation/candidate_b_controlled_suitability/Candidate_B_Controlled_Suitability_Evidence_Report.md).

Candidate B is a proposal only. Its controlled run established operational scope and local post-response receive-order observations; it did not establish free space, collision-free behavior, a valid area, or reset readiness.

## 2. User decision record

**Decision date:** `2026-09-25`  
**Decision class:** `USER_DECISION_FOR_PROVISIONAL_SCENARIO_VALUES`

The user selected the following values only for provisional scenario values and
later core-design work. This record is not `RUNTIME_SCENARIO_APPROVAL`; it does
not authorize a scenario artifact, Gazebo runtime, reset, collision handling,
clearance, policy input, reward/termination, Gymnasium/SB3, Nav2, or hardware.

| Decision | User-selected provisional value | Scope limit |
| --- | --- | --- |
| Scenario identity | `world_demo_candidate_b_v1`, version `1.0.0` | A future artifact identity only; no artifact is created here. |
| World identity | `world_demo`, SHA-256 `a5e9c9b1e9b8ad11e0399855f06de687f04c702258b8b74ce563523d78ed55fe` | Does not establish a coordinate conversion or TF authority. |
| Coordinate reference | `GT_ODOM_2D`, hidden `TrainingTaskOracle` only | Absolutely prohibited from PPO observation, policy input, and `ObservationAssembler`. |
| Start | P0: `(-4.0 m, -3.0 m, yaw 0.0 rad)` | Provisional value only; not reset-ready evidence. |
| Goal | P2: `(-2.0 m, -3.0 m)` | Provisional value only. |
| Goal radius | `0.25 m` | Provisional goal rule value only. |
| Goal rule | `goal_rule_id = "distance_to_goal_lte_radius_2d"`; `sqrt((x-goal_x)^2 + (y-goal_y)^2) <= goal_radius_m` | `USER_DECISION_FOR_PROVISIONAL_SCENARIO_VALUES` only; no evaluator or runtime approval. |
| Bounds name and literals | `candidate_task_bounds`: `x in [-4.5 m, -1.5 m]`, `y in [-3.5 m, -2.5 m]` | Not `valid_area`; not clearance, collision, or reset approval. |
| Boundary semantics | Boundary invalid | Applies only to the provisional candidate bounds. |
| Forbidden zones | `none provisional` | Not a collision policy or proof that no forbidden geometry exists. |
| Randomization | Disabled for v1 | Does not approve future randomization behavior. |
| Artifact-change policy | A SHA-256 change is effective only in a new runtime generation; mismatch fails closed. | Lifecycle binding and runtime implementation remain blocked. |

## 3. Candidate B decision table

This pre-decision proposal table is retained only as evidence lineage. The user-selected values in section 2 control where the two sections differ.

| Decision | Candidate proposal | User must choose |
| --- | --- | --- |
| Scenario ID/version | A clear scenario-v1 name and explicit version; no name is adopted by this packet. | Approve a supplied ID/version or replace it. |
| World identity | `world_demo` and world-file SHA-256 `a5e9c9b1e9b8ad11e0399855f06de687f04c702258b8b74ce563523d78ed55fe`. | Approve or replace. |
| Coordinate reference | `GT_ODOM_2D`, hidden-oracle-only. | Approve or reject. |
| Start candidate | P0: `(-4.0 m, -3.0 m, yaw 0.0 rad)`. | Approve or replace. |
| Goal candidate | P2: `(-2.0 m, -3.0 m)`. | Approve or replace. |
| Goal radius | `0.25 m` hypothesis only. | Select an explicit value or replace the rule. |
| Candidate task rectangle | `x in [-4.5 m, -1.5 m]`, `y in [-3.5 m, -2.5 m]`. | Approve only as `candidate_task_bounds`, revise, or reject. |
| Boundary semantics | Boundary-is-invalid hypothesis. | Choose the rule explicitly. |
| Forbidden zones | Not established. | Choose `none provisional` or provide zone definitions and boundary semantics. |
| Randomization | Disabled for v1 hypothesis. | Approve or replace. |
| Artifact-change policy | A hash change must take effect only in a new generation and otherwise fail closed. | Approve or replace. |

## 4. Required terminology and evidence boundary

The rectangle above is **`candidate_task_bounds`** only. It must not be called `valid_area` until the user separately approves it and clearance/collision evidence exists. The request-to-GT evidence does not prove that its interior, edges, or paths are free space, collision-free, or reset-ready.

`GT_ODOM_2D` is an oracle-only 2D reference identity. It is distinct from runtime GT metadata string `world` and from Gazebo/SDF world identity `world_demo`; this packet does not assert those values are equal or establish a TF authority or coordinate conversion. Ground Truth remains prohibited from the PPO observation, policy, and `ObservationAssembler` paths.

## 5. Blockers not solved by selecting literals

| Runtime/design blocker | Why user coordinate selection is insufficient |
| --- | --- |
| Clearance metric, threshold, and evidence | Scan sanity confirms structural usability only; it is not a clearance calculation or obstacle map. |
| ContactLatch/collision source and filter policy | The run had no approved contact source, and collision must not be inferred from scan, GT, pose, or service response. |
| Reset receipt and settle policy | `success=true` and local post-response receive order are neither application nor reset receipts. |
| Runtime LiDAR-frame reconciliation | Observed scan frame is `ROBOT_URDF_final/RPLiDAR_A1M8_1/rplidar`; it must not be silently treated as any older configured frame. |
| Lifecycle binding | Scenario hash, reset epoch, and runtime generation require an explicit lifecycle binding and change policy. |

These are independent blockers to `RUNTIME_SCENARIO_APPROVAL`; none is resolved by approving a start, goal, or rectangle.

## 6. Two distinct approval types

| Approval type | Permitted consequence | Not granted |
| --- | --- | --- |
| `USER_DECISION_FOR_PROVISIONAL_SCENARIO_VALUES` | Records user-selected candidate literals for a later core/design increment. | No scenario artifact, Gazebo runtime, reset, collision, clearance, policy, reward, termination, Gymnasium/SB3, Nav2, or hardware authorization. |
| `RUNTIME_SCENARIO_APPROVAL` | Not granted by this packet. It requires separately approved blockers and runtime evidence. | It cannot be inferred from Candidate B measurements or the provisional-value decision. |

## 7. User decision checklist

The selections below record the user's provisional-value decision. They do not
grant runtime approval and do not resolve the blocker registry.

- [x] Select scenario ID `world_demo_candidate_b_v1` and version `1.0.0`.
- [x] Retain `world_demo` and its recorded world-file SHA-256.
- [x] Select hidden-oracle-only `GT_ODOM_2D`; policy/observation use remains prohibited.
- [x] Select start P0 `(-4.0, -3.0, yaw 0.0)`.
- [x] Select goal P2 `(-2.0, -3.0)` and radius `0.25 m`.
- [x] Select `goal_rule_id = "distance_to_goal_lte_radius_2d"` with 2D Euclidean distance less than or equal to `goal_radius_m`.
- [x] Retain `candidate_task_bounds` rectangle `x[-4.5,-1.5]`, `y[-3.5,-2.5]`.
- [x] Select boundary invalid.
- [x] Select `none provisional` forbidden zones.
- [x] Select disabled randomization for v1.
- [x] Select fail-closed SHA-256 change policy for a new runtime generation only.
- [x] Acknowledge that none of the selections grants runtime scenario approval before the blocker registry is resolved.

## 8. Explicit non-claims

This packet does not create YAML, JSON, or any other scenario artifact; change configuration or contracts; approve an oracle runtime; approve reset, settle, collision, ContactLatch, reward, termination, STUCK, D6, Gymnasium/SB3/Nav2, ROS/Gazebo runtime, TF authority, firmware, or hardware. It does not promote `candidate_task_bounds` to `valid_area`.
