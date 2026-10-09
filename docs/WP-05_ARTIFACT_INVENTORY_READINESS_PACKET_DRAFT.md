# WP-05 Artifact Inventory and Readiness Packet

**Status:** `DRAFT — INVENTORY AND FUTURE-DECISION SUPPORT ONLY`

**Baseline:** `origin/integration/implementation@c37a5bff9dd6cc32fc503cdd796b31720a58a616`

**Purpose:** inventory repository-tracked map, scenario/world, and hardware evidence; identify prerequisites and decision gaps before any future canonical artifact instance is prepared. This packet selects no artifact and does not authorize measurement, code, ROS, simulation runtime, HIL, hardware operation, or deployment.

## 1. Evidence labels and current boundary

- **SOURCE_FACT** means a path, field, status, or statement observed directly in the tracked baseline or an authority document. A source fact does not by itself mean the content is approved for canonical use.
- **INFERENCE** means a conclusion drawn by comparing source facts with the active foundation contract.
- **RECOMMENDATION** means a proposed future review, decision, or evidence step; it is not an approval or an instruction to execute it now.

**SOURCE_FACT:** the WP-05 foundation decision is active on `integration/implementation`, recorded by the approval record, registry, and Ledger. PEP-001 remains revision 0.5.0; its ordered-work-package table lists WP-05 as `BLOCKED_BY_CONTRACT`. The active foundation record says no concrete map, scenario, or hardware values are selected. `CODE_AUTHORIZATION: NOT_GRANTED`; `RUNTIME_APPROVED: NOT_APPROVED`.

**INFERENCE:** active foundation conventions define where future canonical artifacts belong; they do not promote existing package assets, DRAFT proposals, or simulation evidence into canonical artifact instances.

**RECOMMENDATION:** use this packet to obtain separate user decisions and later work-package scope before preparing any concrete artifact or performing any measurement.

This inventory covers files tracked at the stated baseline. It does not claim that an untracked or external copy is absent. `artifacts/simulation/**` and legacy ROS-package maps are historical/reference evidence only and never become canonical automatically.

## 2. Map inventory

### 2.1 Observed map assets

| SOURCE_FACT: tracked location | Observed contents | Provenance and classification |
| --- | --- | --- |
| `ros2_ws/src/ROBOT_URDF_final_description/maps/warehouse_map.yaml` and `warehouse_map.pgm` | A ROS-package map YAML and its referenced occupancy image are present. The YAML carries map metadata such as resolution, origin, mode, and thresholds. | Legacy package asset; not under the canonical artifact root. Repository history does not establish it as an approved immutable map instance. |
| `ros2_ws/src/ROBOT_URDF_final_description/maps/warehouse_map2.yaml` and `warehouse_map2.pgm` | A second ROS-package map YAML and referenced image are present. | Same legacy/reference classification; no canonical map approval or manifest is established by file presence. |
| `ros2_ws/src/ROBOT_URDF_final_description/maps/keep.txt` | A package-directory marker is present. | Not map provenance or a map artifact manifest. |

**SOURCE_FACT:** no tracked `artifacts/maps/<map_id>/` directory or canonical map instance exists at the baseline. Consequently, the inventory found no canonical-root `map_manifest.json`, `metadata.yaml`, or optional `slam_pose_graph.posegraph` to inspect. The two legacy YAML/image pairs are not copied or nominated here.

### 2.2 Contract comparison and gaps

The active canonical root is `artifacts/maps/<map_id>/`. A future selected instance is expected to provide `map.yaml`, `map.pgm`, `map_manifest.json`, and `metadata.yaml`; a SLAM pose graph is optional and requires separate identity/provenance if present.

Architecture §48 defines `map_content_hash` as SHA-256 over the canonical JSON map manifest that pins the role, relative filename, byte size, and raw-file SHA-256 of **only** `map.yaml` and `map.pgm`. The manifest's result field is not part of its own digest input. `metadata.yaml`, manifest result fields, and an optional pose graph remain outside this content-hash boundary. The WP-05 approval record preserves this boundary; this packet does not calculate a hash or create a manifest.

**INFERENCE — gaps:** no canonical map identity, immutable canonical files, canonical manifest/result, metadata record, map approval, or approved relationship between either package map and a future map instance is present in the tracked baseline. The absence of an optional pose graph is not itself a blocker unless a later approved map decision requires one.

**RECOMMENDATION:** before a future map candidate is made, the Project Owner/User in the `MapCustodian`/map-approver role should decide whether to use an existing source or another source, establish provenance and immutable identity, and approve any required map-specific metadata and acceptance criteria. A separate user-authorized artifact work package should create and review the instance. No map ID, map bytes, frame values, server behavior, or approval is selected here.

## 3. Scenario, world, and configuration inventory

### 3.1 Observed sources and provenance

| SOURCE_FACT: tracked location | What is present | Classification and limits |
| --- | --- | --- |
| `ros2_ws/src/ROBOT_URDF_final_description/launch/tugbot_depot.sdf` and its launch references | A static SDF world source and source-level launch reference are present. | World/configuration evidence only; not a selected scenario identity or coordinate conversion. |
| `ros2_ws/src/ROBOT_URDF_final_description/launch/warehouse_world.sdf` | A second static world source is present. | Historical/static source evidence; no scenario selection is inferred from its name. |
| `docs/S3_Simulation_Scenario_Artifact_Contract_DRAFT.md` | A DRAFT contract records the authorized storage/serialization convention and proposed identity/provenance fields. | Contract shape only. It explicitly says concrete values and runtime are not approved. `RFC8785_JCS_UTF8` is a serialization convention only. |
| `docs/S3_First_Scenario_Candidate_Review_DRAFT.md`; `docs/S3_First_Simulation_Scenario_Candidate_And_Evidence_Plan_DRAFT.md`; `docs/S3_Scenario_V1_User_Decision_Packet_DRAFT.md` | Candidate reviews and provisional scenario values/decision proposals are recorded. | DRAFT/provisional material, not a canonical scenario instance or selection by this packet. |
| `docs/S3_Candidate_B_Controlled_Suitability_Run_Approval_Packet_DRAFT.md`; `docs/S3_Candidate_B_Replacement_Run_Approval_Packet_DRAFT.md`; `docs/S3_Candidate_B_Replacement_Evidence_Review_DRAFT.md` | Candidate B approval/evidence review documents are present. | Historical/DRAFT evidence lineage; not approval of a scenario artifact. |
| `docs/S3_World_Geometry_And_Entity_Inventory_DRAFT.md` and related world/entity design documents | Static geometry, frame-name, and runtime-observation discussions are recorded. | Geometry/frame references do not establish task bounds, forbidden zones, or world/frame equivalence. |
| `artifacts/simulation/candidate_b_controlled_suitability/` and `artifacts/simulation/controlled_coordinate_reset_measurement/` | Reports, manifests, and run evidence are tracked. | Historical simulation evidence. A run/manifest does not create a canonical scenario artifact or authorize runtime. |

**SOURCE_FACT:** no tracked `artifacts/scenarios/<scenario_id>/scenario.json` exists at the baseline. The active convention is that exact root, with `RFC8785_JCS_UTF8` as serialization convention only. The active WP-05 foundation and WP-03 decision record leave scenario identity and concrete values unselected.

### 3.2 Provisional-value and Ground Truth boundaries

The Candidate B, Candidate A/B/C, P0/P1/P2, and other provisional values appearing in the DRAFT documents listed above are classified here as **non-canonical and not selected by this packet**. This applies even where a DRAFT document describes a provisional user selection or a controlled suitability observation. This packet intentionally does not reproduce those coordinates, goals, bounds, radii, zones, IDs, seeds, or randomization choices. The documents remain unchanged as historical/DRAFT sources.

Values and observations retained in `artifacts/simulation/candidate_b_controlled_suitability/**` are likewise run-specific historical evidence, not adopted scenario values or a canonical scenario artifact. Their existence does not change the active Registry statement that no scenario instance is selected.

The DRAFT scenario contract identifies missing foundation data including immutable `scenario_id` and artifact version, scenario content SHA-256, exact world identity and world-file hash, coordinate-reference ID, approval provenance, and lifecycle-change policy. A future scenario also requires user decisions and evidence for start semantics, goal/rule, valid-area geometry and boundary semantics, forbidden-zone choice/geometry, and whether/version how randomization is represented. It must not infer any of these from SDF geometry, launch spawn, visual inspection, or a probe observation.

`GT_ODOM_2D` remains evaluator/oracle-only. Raw Ground Truth must not enter PPO, policy input, `ObservationAssembler`, `ObservationEncoder`, or the observation core. The recorded `world_demo` identity and an observed `world` frame string are not evidence that those identifiers are equivalent or that a coordinate transform exists.

**INFERENCE — gaps:** there is no canonical scenario ID/version, serialized scenario, canonical content hash, approved world identity/hash binding, approved coordinate relation, scenario approval record, or lifecycle-bound artifact instance in the tracked baseline. The DRAFT materials contain useful decision and evidence lineage but do not satisfy those gaps.

**RECOMMENDATION:** the Project Owner/User in the `ScenarioCustodian`/scenario-approver role should review and explicitly choose or reject each future scenario decision. After an authorized instance-preparation scope, scenario/task contract work can be routed to the relevant PEP work package; any simulation execution remains a separate WP-11/user-approved runtime decision. No scenario ID, world/frame equivalence, start, goal, bounds, zones, seed, or randomization value is selected here.

## 4. Hardware evidence inventory and proposed measurement plan

### 4.1 Existing record state

**SOURCE_FACT:** the canonical profile directory contains:

- `artifacts/hardware/mecanum_f411_tb6612_ga25_370_rev_a/hardware_manifest.yaml`
- `artifacts/hardware/mecanum_f411_tb6612_ga25_370_rev_a/approval.yaml`

The manifest declares the profile identity, wheel ordering, some locked design/configuration fields, motor-driver/encoder/UART pin mappings, and the JCS/SHA-256 `hardware_config_hash` contract. These are manifest declarations; they are not a substitute for physical measurement evidence.

The manifest keeps required measured quantities unavailable, including wheel diameter/radius, wheelbase, track, encoder scale inputs/derived ticks, and per-wheel command/encoder signs (`value: null`, `status: TBD_MEASURED`). The approval record has `approval_status: DRAFT`, `motor_enable_allowed: false`, no approved hardware-config hash, and `required_field_policy: fail_closed_on_tbd_measured`. Its required evidence items remain `PENDING`, including geometry measurement, encoder/quadrature verification, sign bench test, UART/reconnect, E-stop gate, command watchdog, driver current/thermal, and power integrity.

Under the active foundation contract, a configuration hash can be computed for approval only after every required measured value is present and the required approval has been recorded. The current missing values prevent that state. This packet does not fill values, compute a profile hash, or change either record.

### 4.2 Proposed future measurement plan — not authorized for execution

The table is a plan for user review only. No measurement, bench test, HIL, or hardware connection is performed by this packet. Exact numeric limits, tolerances, test conditions, and pass thresholds must be approved before execution; none are invented here.

| Required evidence | Proposed method and retained evidence | Proposed acceptance condition (thresholds TBD) | Owner / approver role | Later route |
| --- | --- | --- | --- | --- |
| Geometry: wheel diameter, wheelbase, track | Measure the identified assembly with calibrated tools; record method, units, instrument/calibration identifiers, repeated readings, uncertainty, photographs, operator, and reviewer. | Required fields complete, finite, internally consistent, repeatable within a separately approved tolerance, and approved in the immutable hardware record. | Project Owner/User as Hardware Measurement Owner and Hardware Technical Approver, unless a named delegate is recorded. | WP-12 measurement evidence and applicable Gate 3/4 review. |
| Encoder scale and quadrature | On an approved controlled fixture, record motor/wheel turns, raw counts, channel/decode configuration, gear ratio evidence, calculation, and direction. | Measured inputs and derived ticks reconcile under the manifest formula and an approved tolerance; unresolved ambiguity blocks the value. | Same roles, or explicitly recorded delegate/approver. | WP-12; coordinate with WP-07 bridge/firmware contract work. |
| Per-wheel motor-command and encoder signs | Later authorized low-energy bench procedure; retain wiring/fixture identity, command sequence, raw tick trace, video or equivalent evidence, and review. | Each wheel mapping is unambiguous and consistent with the approved wheel order and sign convention; test limits are approved beforehand. | Same roles, or explicitly recorded delegate/approver. | WP-12; relevant WP-07 integration evidence. |
| UART protocol and reconnect | Capture protocol/version, representative frame traces, checksums/sequence behavior, disconnect/reconnect steps, timeout behavior, and logs. | Protocol and failure/reconnect behavior meet separately approved contract criteria; no invented timing threshold. | Project Owner/User or named technical delegate; final hardware approver remains the recorded role. | WP-07 offline/bridge scope, then WP-12 where physical/HIL evidence is required. |
| E-stop hardware gate and command watchdog | Under a separately approved safety test procedure, instrument the normally-closed E-stop path and motor-driver safe-state signal; capture command-loss response and recovery. | E-stop forces the declared safe gate independently of software, MCU cannot override it, and watchdog behavior meets pre-approved limits. | Project Owner/User as Hardware Technical Approver; safety owner/delegate must be explicitly recorded. | WP-12 and applicable Gate 3/4; no authorization is granted here. |
| Driver current/thermal and power integrity | On an approved fixture/load profile, record current, driver/board temperatures, supply voltage/ripple/transients, ambient conditions, battery/supply identity, instruments, and synchronized logs. | Results remain inside manufacturer limits plus user-approved engineering margin under predeclared conditions; limits and margins must be set before measurement. | Project Owner/User or named hardware delegate; technical approval recorded in the immutable record. | WP-12 measurement/HIL and Gate 3/4 review. |

## 5. Readiness matrix

| Group | SOURCE_FACT: evidence present | INFERENCE: gap/readiness | User/gate decision needed | Proposed owner | Recommended next step |
| --- | --- | --- | --- | --- | --- |
| Map | Two legacy ROS-package YAML/PGM pairs; active canonical map/hash convention. | No canonical map instance, manifest, metadata, or approval. Legacy files cannot be promoted automatically. | Choose source/identity and approve required provenance/metadata; decide if a pose graph is needed. | Project Owner/User as `MapCustodian` and map approver. | Review this inventory, then authorize a separate concrete-map work package if desired. |
| Scenario/world | Static world sources, DRAFT scenario contract/reviews, and historical simulation reports/manifests. | No canonical scenario JSON or approved world/frame binding. DRAFT Candidate B/provisional values remain non-canonical and unselected here. | Select/reject scenario identity, world revision/hash, coordinate reference, start/goal/regions/zones, and lifecycle/randomization policy through an explicit decision. | Project Owner/User as `ScenarioCustodian` and scenario approver. | Resolve decisions and evidence requirements first; route task/runtime work under PEP only with separate approval. |
| Hardware profile | Canonical manifest and distinct approval record; static declarations and hash contract. | Required `TBD_MEASURED`/null values and pending evidence prevent an approved hash; approval remains fail-closed. | Approve measurement protocol, acceptance limits, delegates, and later hardware/HIL authorization. | Project Owner/User as Hardware Measurement Owner and Hardware Technical Approver, unless recorded delegation. | Review plan; schedule measurements only under a separate authorized WP-12/Gate 3/4 scope. |
| Cross-boundary provenance | Active foundation references and Architecture §48; simulation evidence and legacy maps are identifiable. | Presence of reports/configs does not establish canonical approval, runtime evidence, or artifact identity. | Decide which future work package owns any proposed instance and how its review/approval will be recorded. | Project Owner/User and designated technical approvers. | Keep this packet as review input; do not change PEP, Registry, Ledger, or WP status here. |

## 6. Explicit non-decisions and authorization boundary

This packet does not select a map or scenario ID; map bytes; world/frame equivalence; scenario start, goal, bounds, zones, seed, or randomization; a hardware measurement; or a hardware approval. It creates no `map_manifest.json`, `scenario.json`, measurement record, or canonical artifact instance. It does not revise the active hash boundary, scenario/GT isolation, or hardware fail-closed contract.

WP-05 remains open. WP-04 remains `BLOCKED_BY_CONTRACT`; no status or dependency is changed. `CODE_AUTHORIZATION: NOT_GRANTED`; `RUNTIME_APPROVED: NOT_APPROVED`. No code, ROS, runtime, HIL, hardware, motor-enable, `deploy_sim`, or `deploy_real` authorization is granted.

## 7. Sources read at the baseline

- `AGENTS.md`
- `docs/MECANUM_NAV_DRL_Architecture.docx`, §48 and relevant artifact/GT constraints
- `docs/governance/PROJECT_EXECUTION_PLAN.md`, PEP-001 rev.0.5.0
- `docs/governance/CANONICAL_SOURCE_REGISTRY.md`
- `docs/governance/PROJECT_PROGRESS_LEDGER.md`
- `docs/governance/decisions/WP-05_CANONICAL_ARTIFACT_FOUNDATION_APPROVAL.md`
- `docs/governance/decisions/WP-03_CONTRACT_CLOSURE_DECISIONS.md`
- `docs/S3_Simulation_Scenario_Artifact_Contract_DRAFT.md` and the scenario/world DRAFT documents listed above
- The canonical hardware manifest and approval record named in §4.1
- Relevant tracked legacy map files, world sources, and simulation evidence paths named above
