# S3 First Simulation Scenario Candidate And Evidence Plan

**Status:** `DRAFT — CANDIDATE SELECTION AND MEASUREMENT PLAN, NO SCENARIO VALUES APPROVED`

## 1. Purpose and current prerequisites

This document prepares the smallest set of user decisions and simulation-only
evidence needed before one concrete immutable scenario artifact can be
approved. It does not select a coordinate, create an artifact/hash, or
authorize a measurement run.

The following prerequisites are recorded, with their limits intact:

| Prerequisite | What is available | What it does not establish |
| --- | --- | --- |
| `GT_ODOM_2D` | User-approved only for core-only `TrainingTaskOracle` interface design. | Runtime GT ingress, a scenario frame conversion, policy use, or a ready oracle fact. |
| Scenario contract | [S3 Simulation Scenario Artifact Contract](S3_Simulation_Scenario_Artifact_Contract_DRAFT.md) defines proposed schema/validation. | Concrete values, an artifact file, canonical serialization, or a SHA-256 identity. |
| P0/P1/P2 replacement run | Request-to-GT numerical correspondence was observed after the local post-response barrier. | Valid starts, a goal, a safe/valid area, reset readiness, collision safety, or settled state. |
| Static world inventory | World/entity names and geometry references are known from source. | Task bounds, forbidden zones, coordinate conversion, collision policy, or TF authority. |

The reference evidence is the `VALID` replacement run documented in the
[controlled-coordinate evidence report](../artifacts/simulation/controlled_coordinate_reset_measurement/Controlled_Coordinate_Reset_Measurement_Evidence_Report.md).
Its P0/P1/P2 probes remain measurement probes only, not implicit scenario
members.

## 2. Proposed minimum viable scenario scope

The first scenario is deliberately smaller than a warehouse-wide task policy.
It is proposed to bind one fixed world revision to one 2D goal and one simple
valid training area. Version one has no randomization fields. Forbidden zones
are absent only if the user explicitly selects “none for v1”; otherwise their
geometry and semantics require a separate decision before the artifact can be
valid.

| Scope member | Proposed v1 boundary | Not included or not implied |
| --- | --- | --- |
| World | One user-selected `gazebo_world_name` and exact `world_file_sha256`. | A conclusion that `world_demo` equals GT metadata `world`, a TF relation, or a world-coordinate conversion. |
| Goal | One user-selected 2D x/y point, radius/tolerance, and explicit goal-reached semantic. | A value inherited from P0/P1/P2, legacy waypoints, or visual/SDF inspection. |
| Valid area | One simple, user-selected 2D shape with numeric bounds and an explicit inclusion rule. | An inferred world boundary, obstacle clearance policy, collision boundary, or forbidden-zone substitute. |
| Starts | A user-selected fixed start or catalog decision. | Implicit use of launch spawn or P0/P1/P2. |
| Randomization | Excluded from v1. | Permission to add an unversioned seed, sampled parameter, or scenario mutation later. |
| Forbidden zones | Explicitly “none for v1” only after user decision, or separately specified/validated zones. | Automatic conversion of SDF/visual/collision geometry into task rules. |
| Runtime behavior | None. | Collision, STUCK, reward, termination, reset, Gymnasium/SB3, or policy runtime. |

This is a **minimum viable scenario contract**, not an operational safety map
or complete warehouse policy.

## 3. Required user decisions

No row below has a selected value. Each must be approved before a concrete
artifact is created.

| Decision | Required user selection | State | Evidence needed before an artifact is approved |
| --- | --- | --- | --- |
| Scenario identity | `scenario_id` and `scenario_version` for the first case. | `REQUIRED_USER_DECISION` | Chosen immutable naming/canonical-hash convention and world revision. |
| Goal | 2D x/y, radius/tolerance, and goal-reached semantics. | `REQUIRED_USER_DECISION` | Controlled suitability evidence in `GT_ODOM_2D`; no legacy or SDF inference. |
| Valid area | Shape/type, numeric bounds, and boundary inclusion rule. | `REQUIRED_USER_DECISION` | Same coordinate-provenance evidence and an explicit non-collision claim boundary. |
| Forbidden zones | Choose “none for v1” or provide zone IDs, shape/type, numeric bounds, and semantics. | `REQUIRED_USER_DECISION` | If present, coordinate suitability evidence for each zone and explicit boundary semantics. |
| Start-pose catalog | Choose one fixed start or multiple approved start poses with selection policy. | `REQUIRED_USER_DECISION` | Controlled suitability evidence for every selected pose; no implicit launch/probe adoption. |
| Artifact-change policy | Define whether/how a different artifact takes effect between episodes/generations. | `REQUIRED_USER_DECISION` | Lifecycle invalidation/replay design; no mid-episode replacement. |
| Randomization fields | Confirm exclusion from v1 or select a future versioned extension. | `REQUIRED_USER_DECISION` | Seed/reproducibility and scenario-hash impact design. |

## 4. Controlled scenario-suitability evidence plan

Only after the user selects values and approves a separate run may a
controlled scenario-suitability collector be created and executed. The run is
simulation-only and may use the audited temporary one-service `SetEntityPose`
bridge, subject to a new, literal approval packet. It does not reuse the
already-consumed P0/P1/P2 request authority.

### 4.1 Allowed future observation and control boundary

| Boundary | Proposed rule for the later approved run |
| --- | --- |
| Target | Only the exact user-approved entity; the current known candidate is `ROBOT_URDF_final`, but the new packet must name it explicitly. |
| Passive streams | Collector observes only `/ground_truth/odom`, `/scan`, `/clock`, and graph metadata required to verify owner/type/allowlist. |
| Pose control | Only declared, user-approved `SetEntityPose` requests through the temporary audited bridge; no retry, supplemental pose, or z adjustment. |
| Forbidden operations | No `/cmd_vel`, teleop, Nav2, PPO/Gymnasium/SB3, world control, reset/pause/step, spawn/delete, hardware, firmware, Pi, STM32, UART, or motor operation. |
| Shutdown | SIGINT only for Gazebo/bridge processes created by the approved run. |

Every approved probe must retain, on one local steady clock:

```text
pre_call_steady_ns
ros_request_dispatched_steady_ns
ros_response_received_steady_ns
post_response_barrier_steady_ns
```

Only a GT sample with `received_steady_ns > post_response_barrier_steady_ns`
may be described as `POST_RESPONSE_CANDIDATE`. `/scan` and GT samples received
after response are **suitability evidence only**. They are not a reset receipt,
collision proof, settled-state proof, freshness/settlement threshold, or
coordinate-frame authority.

### 4.2 Fail-closed criteria for the later run

| Condition | Required result |
| --- | --- |
| World name/hash differs from the user-approved scenario candidate | Do not send a pose request; mark the run invalid for scenario suitability. |
| Service unavailable/type mismatch, request failure, or `success=false` | Stop; do not send remaining probes; no retry. |
| Required GT post-response candidate absent | Record no suitability conclusion for that probe; do not substitute a pre-response/older GT sample. |
| GT frame metadata mismatches the selected `GT_ODOM_2D` evidence contract | Stop; do not infer a frame conversion. |
| `/scan` invalid, missing, or metadata/type/graph evidence is incomplete | Mark the run invalid for the intended sensor suitability claim; do not invent sensor health. |
| Graph/control boundary violated, including a new non-allowlisted command publisher or prohibited control operation | Stop; mark run invalid; preserve evidence and shut down approved child processes. |

No numeric settle time, clearance threshold, residual tolerance, collision rule,
or reset policy is chosen by this plan.

## 5. Evidence classification

| Evidence class | Current state | Permitted interpretation |
| --- | --- | --- |
| Request-to-GT numeric correspondence | `AVAILABLE` for P0/P1/P2 as post-response candidates. | Supports only the narrow `GT_ODOM_2D` core-design reference. |
| Coordinate suitability for selected goal/start/bounds | `NOT_AVAILABLE`. | Requires user-selected values and a separately approved controlled run. |
| Reset/collision/termination readiness | `NOT_AVAILABLE`. | Requires independent reset receipt, contact, terminal-source, D6, and STUCK decisions/evidence. |

## 6. Exact handoff

After the user chooses the concrete scenario values in Section 3 and approves
the measurement plan, the next step may create **one approval packet for one
controlled scenario-suitability run**. That packet must fix the exact probes,
world hash, target entity, bridge argument, control allowlist, artifact format,
and fail-closed stop conditions.

It must not create the actual scenario artifact/hash or `TrainingTaskOracle`
source, and it must not authorize a Gazebo runtime/reset/collision path beyond
the explicitly approved suitability probes.

## 7. Explicit non-claims

This plan does not claim `world_demo = world`, derive bounds from geometry/SDF/
visual maps, or allow GT into PPO observation or any policy path. It does not
approve Gazebo runtime, Gymnasium/SB3, reset, collision/ContactLatch, reward,
termination, hardware, firmware, STM32, Pi, UART, motor, launch, or
configuration changes.
