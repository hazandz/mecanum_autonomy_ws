# WP-05 Concrete Artifact Decision Packet

**Status:** `DRAFT — PROJECT OWNER/USER SCOPE DECISION REQUESTED`

**Baseline:** `origin/integration/implementation@c37a5bff9dd6cc32fc503cdd796b31720a58a616`

**Purpose:** ask the Project Owner/User which independent WP-05 follow-on scope to prepare. The choices below do not themselves select an artifact or approve measurements, implementation, or runtime.

## 1. Provenance and decision boundary

This packet follows the inventory/readiness packet `wp-05-artifact-inventory-readiness-packet-c37a5bff@fa1af08b2c1220be1838e779b5059cb5673f0344`, SHA-256 `e91bffe9878926366850e5c0b5f25a34bd0487436d75470f58a3b754437311d9`. The Project Owner/User supplied its independent audit result as `PASS`. That packet inventoried tracked evidence and gaps; it did not select concrete artifacts or perform measurements.

The active WP-05 foundation decision preserves the map, scenario, and hardware provenance/hash boundaries described below. WP-05 remains open. PEP-001 rev.0.5.0 continues to list WP-05 as `BLOCKED_BY_CONTRACT`; this packet does not change PEP, Registry, Ledger, WP status, or dependencies.

### Independent scope choice

The Project Owner/User may choose A, B, and C separately, choose any combination, or defer all three. Choosing a letter identifies only a future work-package scope. It does not fill the missing values, create an artifact, authorize physical measurement, or approve runtime. Any selected scope will still need its own precise decisions, authorization, review, and acceptance before execution.

| Option | Select scope for a later work package | Defer |
| --- | --- | --- |
| A — Prepare one canonical map instance from a user-selected legacy/reference source | ☐ | ☐ |
| B — Prepare one canonical scenario instance | ☐ | ☐ |
| C — Prepare a standalone hardware measurement plan; no measurements in that work | ☐ | ☐ |

No option is preselected by this packet.

## 2. Option A — prepare a canonical map instance

### Current evidence and authority

The inventory packet found two legacy ROS-package map YAML/PGM pairs:

- `ros2_ws/src/ROBOT_URDF_final_description/maps/warehouse_map.yaml` and `warehouse_map.pgm`
- `ros2_ws/src/ROBOT_URDF_final_description/maps/warehouse_map2.yaml` and `warehouse_map2.pgm`

These filenames identify existing reference assets only. Neither is a selected source or canonical map ID; file presence does not establish provenance, suitability, approval, or a request to copy it.

The canonical destination is `artifacts/maps/<map_id>/`. Architecture §48 and the active WP-05 foundation decision govern the map boundary. The Project Owner/User is `MapCustodian` and map approver unless a delegate and its authority are named in the immutable map record.

### Decisions still required from the user

- Choose one of the existing reference sources, identify a different approved source, or defer/reject map preparation.
- If proceeding, explicitly select an immutable `<map_id>` and decide its change-control policy; do not add an unapproved version field to the map contract.
- Confirm the source provenance and intended map use; decide whether any source conversion or regeneration is permitted and what evidence must be retained.
- Review the source YAML's map metadata and decide what metadata must be retained or re-established for the canonical instance.
- Decide whether an optional SLAM pose graph is needed. If included, approve its separate identity, provenance, and hash treatment.
- Approve map acceptance criteria, map approval record requirements, and any future navigation-use gate. No map frame, map-server behavior, or equivalence to a world/scenario frame is inferred here.

### Expected files, provenance, hash, and acceptance

Expected artifact path: `artifacts/maps/<map_id>/`, containing `map.yaml`, `map.pgm`, `map_manifest.json`, and `metadata.yaml`; optional `slam_pose_graph.posegraph` only if separately selected and approved.

`map_content_hash` covers **only** `map.yaml` and `map.pgm`: the `mecanum_map_hash/v1` canonical JSON manifest pins each file's role, relative name, byte size, and raw-file SHA-256; the `map_content_hash` result field is excluded from its own digest input. `metadata.yaml`, manifest result fields, and an optional pose graph remain outside this boundary. Any optional pose graph requires separate provenance/hash handling. This packet computes no hash and creates no map files.

Before a future instance could be accepted, its source chain and any transformation must be reviewable; required map files must be present and internally consistent; the manifest entries and recomputed result must match the bytes; metadata and approval provenance must identify the same immutable instance; and the recorded map approver must approve it. Architecture §48 requires an approved map state for navigation use. Exact content acceptance criteria and any tolerances remain for the user/approver to decide.

### Limits

No map source, ID, bytes, coordinates, frame values, pose graph, map-server behavior, or approval is selected here. Legacy package maps remain reference evidence, not mutable canonical copies or automatic artifacts.

## 3. Option B — prepare one canonical scenario instance

### Current evidence and authority

The canonical destination is `artifacts/scenarios/<scenario_id>/scenario.json`. The scenario contract records `RFC8785_JCS_UTF8` as the serialization convention only. The WP-03 decision record names the Project Owner/User as `ScenarioCustodian` and scenario approver unless a delegate is explicitly named.

The inventory identified static world sources, DRAFT scenario contract/review/decision documents, and historical Candidate B suitability/reset evidence. Their Candidate B and other provisional values are **non-canonical and not selected by this packet**. A DRAFT document's provisional-value statement or a simulation observation does not create a selected scenario or a canonical scenario instance.

### Decisions and evidence still required from the user

- Select or defer a scenario identity and version; approve the exact world source/revision and provide provenance for its content hash.
- Explicitly decide the coordinate-reference ID and provide evidence for any coordinate relationship required by the scenario. Do not infer equivalence between a Gazebo world name, an observed frame string, and `GT_ODOM_2D`.
- Select or defer each concrete scenario member: start policy/catalog, goal and goal rule, valid-area geometry and boundary rule, forbidden-zone choice/geometry, and randomization policy/seed treatment.
- Decide immutable artifact change/lifecycle policy, approval provenance, schema compatibility policy, and how a future artifact is invalidated or replaced.
- Approve validation and acceptance criteria, including how coordinate suitability is evidenced without promoting legacy waypoints, SDF geometry, or probe values into task semantics.

### Expected file, identity, hash, and acceptance

Expected path: `artifacts/scenarios/<scenario_id>/scenario.json`.

A future instance must have immutable identity and artifact version, content SHA-256 over the agreed RFC8785 JCS UTF-8 serialization, world identity and exact world-file hash, coordinate-reference ID, approval provenance, and lifecycle-change policy. `RFC8785_JCS_UTF8` remains a convention, not an artifact selection or runtime approval.

Acceptance for a later candidate should require all required fields and user decisions to be explicit; geometric data to be finite, unit-bearing, and tied to the declared scenario/world/reference identity; canonical serialization/hash to match exact bytes; provenance/approval to name the same immutable instance; and lifecycle-change behavior to be reviewable. Missing, mismatched, or unapproved identity/evidence must fail closed. The DRAFT contract and this packet do not approve an oracle runtime or training scenario.

`GT_ODOM_2D` remains evaluator/oracle-only. Raw Ground Truth must not enter PPO, policy input, `ObservationAssembler`, `ObservationEncoder`, or the observation core. No transformation or equivalence from `world_demo`, `world`, SDF-local geometry, or any other frame is inferred.

### Limits

No scenario ID, world/frame equivalence, world revision, goal, start, bounds, zones, seed, randomization value, or scenario JSON is selected or created here. Any simulation run remains a separate WP-11/user-approved runtime decision; this option does not authorize Gazebo or a task oracle.

## 4. Option C — prepare a separate hardware measurement plan

### Current evidence and authority

The existing profile is under `artifacts/hardware/mecanum_f411_tb6612_ga25_370_rev_a/`, with `hardware_manifest.yaml` and a distinct `approval.yaml`. The manifest declares the `RFC8785_JCS_UTF8`/SHA-256 `mecanum_hardware_config_hash/v1` contract. The approval record remains `approval_status: DRAFT`, `motor_enable_allowed: false`, with no approved hardware-config hash. Required physical values remain `TBD_MEASURED`/null and required evidence is `PENDING`.

The Project Owner/User is the Hardware Measurement Owner and Hardware Technical Approver unless a delegate and authority are named in the immutable hardware record. PEP-001 routes hardware measurements and HIL to WP-12/Gate 3/4; WP-07 owns relevant bridge/firmware integration work under its existing dependencies.

### Decisions needed before a plan can be finalized

- Select which measurement groups to plan and their order; the approval record currently lists geometry, encoder/quadrature, wheel signs, UART/reconnect, E-stop gate, command watchdog, driver current/thermal, and power integrity.
- Approve test methods, instrument/fixture requirements, calibration and uncertainty records, operating conditions, data retention, independent review, and stop criteria.
- Set acceptance thresholds and tolerances from the applicable approved engineering/manufacturer basis. This packet supplies no numeric threshold.
- Confirm owner/approver roles or name delegates, and choose the later evidence record locations under the immutable hardware-profile record.
- Decide which preparation deliverable constitutes a reviewable measurement plan. A possible draft-document location is `docs/WP-05_HARDWARE_MEASUREMENT_PLAN_DRAFT.md`; this is a proposal only and is not created here.

The inventory packet §4.2 provides the more detailed proposed evidence plan. At decision level, the plan would cover:

| Measurement group | Plan should define method/evidence | Acceptance decision needed before any future measurement |
| --- | --- | --- |
| Geometry | Calibrated-tool method, fixture/reference surfaces, repeated readings, units, uncertainty, instrument/calibration identity, and photos. | User-approved tolerance and consistency rule. |
| Encoder scale/quadrature | Known rotation procedure, raw channel/count records, decode setting, gear-ratio provenance, calculation, and direction. | Approved formula/tolerance and reconciliation criteria. |
| Wheel command/encoder signs | Authorized low-energy fixture sequence, wheel identity, raw command/tick traces, and review evidence. | Approved sign convention, per-wheel pass rule, and safe test limits. |
| UART/reconnect | Protocol/version traces, sequence/checksum records, disconnect/reconnect steps, timeout and recovery logs. | Approved protocol, failure response, and timing criteria. |
| E-stop gate/watchdog | Approved electrical test procedure, E-stop/gate signal capture, command-loss trace, and recovery record. | Safety-approved fail-safe behavior and approved response limits. |
| Driver current/thermal and power integrity | Declared load/environment, current and temperature logs, voltage/ripple/transient captures, instruments, supply identity, and calibration. | Manufacturer/engineering basis, approved margin, load conditions, and thresholds. |

All exact limits, tolerances, repetitions, operating conditions, and stop criteria remain user/technical-approver decisions; this table supplies no numerical values and authorizes no test.

### Evidence, hash, and acceptance

A future plan should define every measurand, method, units, instruments and calibration identity, fixture, conditions, repetitions/uncertainty, raw evidence to retain, result format, reviewer, acceptance threshold source, stop condition, and destination. Later measurements must retain provenance sufficient to connect results to the exact hardware profile and manifest revision.

The hardware configuration hash is eligible for approval only after all required measured values are present and approved. The existing JCS/SHA-256 contract and distinct approval record remain in force. `TBD_MEASURED`/null stays unavailable until valid evidence and approval are recorded; the measurement plan itself cannot change approval status or enable motors.

Acceptance of a future **plan** means that all requested measurements and evidence routes are covered, thresholds and safety controls are approved before any procedure, ownership/delegation is explicit, and no values are fabricated. Acceptance of a plan is not acceptance of measurement results or hardware approval.

### Limits

Option C prepares a plan only. It performs no measurement, bench test, HIL, hardware connection, motor operation, hash approval, or change to `approval.yaml`/`hardware_manifest.yaml`. Any later execution requires its own explicit authorization and applicable WP-12/Gate 3/4 controls.

## 5. Cross-option safeguards

- A, B, and C are independent scope choices; no selection is bundled or implied by another.
- No option authorizes code, ROS, runtime, HIL, hardware operation, motor enable, `deploy_sim`, or `deploy_real`.
- `TBD_MEASURED`/null remains unavailable; `approval_status` stays `DRAFT`; `motor_enable_allowed` stays `false`.
- No status or dependency changes. WP-05 is not closed, and WP-04 remains `BLOCKED_BY_CONTRACT`.
- The map hash boundary, scenario serialization/identity convention, and Ground Truth isolation remain unchanged.

## 6. Project Owner/User decision

Select any subset of A/B/C or defer all. For each selected option, the next work-package prompt must identify the exact authorized deliverable and any further decisions required before artifact creation or measurement. This packet itself grants no such authority.
