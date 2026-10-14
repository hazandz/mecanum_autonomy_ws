# WP-04/WP-05 Runtime Measurement Plan and Evidence Schema

| Field | Value |
|---|---|
| Work package | `WP04-WP05-RUNTIME-MEASUREMENT-PLAN-AND-EVIDENCE-SCHEMA` |
| Classification | `L1_RUNTIME_MEASUREMENT_GOVERNANCE_PLAN_ONLY` |
| Exact source/integration base | `cc0018560b20a52fa6d3c9cf26abbe0ef4c6227a` |
| Architecture authority | `docs/MECANUM_NAV_DRL_Architecture.docx`; SHA-256 `432eeac363a595cfcf7e81c4b66054fb674dba140a2ef3cffecd617ab8136204` |
| Companion schema | `docs/governance/evidence/WP-04_WP-05_RUNTIME_MEASUREMENT_EVIDENCE_SCHEMA.json`; schema ID `mecanum.wp04-wp05.runtime-measurement-evidence`; revision `1` |
| Source-base lifecycle | Review-candidate snapshot; not effective from branch/commit ancestry or review push |
| Conditional post-integration status | After independent audit PASS for the exact candidate, separate exact-commit User authorization, fast-forward, and remote-ref verification: `INTEGRATED_L1_RUNTIME_MEASUREMENT_GOVERNANCE_PLAN_ONLY` |

## 1. Purpose, authority, and limits

This L1 record standardizes a measurement plan, ownership boundaries, fail-closed evidence admission, exploratory-versus-acceptance classification, and a reusable evidence-packet schema for WP-04 and WP-05. It is not an active runtime-binding technical authority, measurement result, runtime graph observation, map approval, Gate B acceptance, or proof of contract compliance. It does not create a measurement harness or authorize running one. A passive measurement harness requires its own later L1 authorization.

The Architecture DOCX remains highest authority. Active OIC V3, WP-04 runtime-binding, WP-05 Navigation V1 runtime-binding, dependency-lock/static-bringup authorization, and bounded implementation authorization retain their pinned scope. This plan cannot change TF ownership, lifecycle/barrier semantics, safety, public interfaces, map identity, global `ResolvedConfig.config_hash`, source selection, or approval status. If a future harness would alter TF ownership, lifecycle, safety, a public interface, or `config_hash` semantics, stop and require L2 change-control before implementation.

No numerical acceptance threshold is introduced here. Every required measured value remains `PENDING_MEASUREMENT` until captured and admitted through an independently authorized process. No profile instance, resolved configuration, source pin, package/version lock instance, `config_hash`, runtime authorization, or runtime evidence is created by this candidate.

## 2. Measurement plans

The inventory below specifies what a future authorized collector may observe and record. It does not set rates, tolerances, timeouts, bounds, pass criteria, or limits. Clock comparisons and age calculations are valid only under a separately pinned, declared clock policy; ROS, steady-monotonic, and UTC timestamps must not be mixed by implicit conversion.

### 2.1 WP-04 Observation V3

| Area | Planned observations (no thresholds assigned) |
|---|---|
| LiDAR `/scan` | Expected endpoint identity is `sensor_msgs/msg/LaserScan` with exact `header.frame_id=lidar_frame`; record observed type/frame, cadence and inter-arrival gaps, invalid/no-return ratio, arrival timestamp, and scan age/latency only when the applicable clock policy is valid. |
| LocalReference | Record path frame, provenance of upstream transform to `base_link`, projection success/failure, path age, and availability. The adapter boundary does not perform TF lookup or choose the path source. |
| Measured twist | Record wheel/IMU input cadence, `/odometry/filtered` cadence, exact header/child frames, covariance presence, and input-to-output age. The target is one EKF publisher; this plan does not identify a concrete source pin. |
| Synchronization | Record scan–twist skew, buffer depth/overflow, rejection reason, and valid-vector rate. No skew or buffer threshold is set. |
| Lifecycle/receipt | Record action/reset barrier start/end, epoch/generation, delay from applicable barrier to eligible receipt, observation cutoff relationship, and rejection reason. No barrier/receipt timeout is set. |

### 2.2 WP-05 Navigation V1

| Area | Planned observations (no thresholds assigned) |
|---|---|
| Map Server | Record selected artifact ID/hash, artifact-root-only path identity, lifecycle health, and load result. A load result does not approve the map. |
| AMCL | Record exact scan type/frame, lifecycle state, pose/covariance publication, and observed `map → odom` publisher uniqueness. AMCL is the target owner of this edge in Navigation V1; observation does not prove ownership by itself. |
| EKF | Record wheel/IMU cadence, `/odometry/filtered`, observed `odom → base_link` publisher uniqueness, age, and covariance presence/content provenance. The EKF is the target sole owner; no numeric covariance criterion is set. |
| TF graph | Record graph snapshot, observed owner for each declared edge, transform availability/gap, and provenance for `base_link → lidar_frame` geometry. Runtime observation does not create or authorize TF. |
| Lifecycle/startup | Record activation order, health-gate result, failed transition, and remap/namespace identity. Missing/failed upstream health remains a bring-up inhibit, not a pass. |
| Localization quality | Record recovery events, covariance trend, scan-match availability, and pose-update gaps. No quality threshold is specified. |

## 3. Ownership and fail-closed boundaries

| Concern | Existing target owner / authority | Measurement-harness boundary |
|---|---|---|
| `map → odom` | AMCL in Navigation V1; localization authority remains mode-specific under Architecture | Observe/log graph and lifecycle evidence only; never publish or claim ownership. |
| `odom → base_link` | One EKF | Observe/log publisher and output evidence only; never publish or configure the EKF. |
| `base_link → lidar_frame` | Robot description / `robot_state_publisher` | Observe/log transform and geometry provenance only; never broadcast or repair TF. |
| Barrier/reset identity | `SafetyLifecycle` owns action/reset barriers, reset epoch, and generation | Observe/log supplied lifecycle evidence only; never create, advance, or own a barrier. |
| Selected map | Map Server serves the selected map artifact; map approval remains a separate authority decision | Observe/log artifact identity/load result only; Map Server or a successful load does not approve a map. |
| WP-04 input conversion | Authorized nonexecuting WP-04 adapters convert verified input to typed snapshots | Adapters do not select measurements, judge runtime acceptance, or turn observations into approval. |
| Measurement harness | No TF, lifecycle, map, command, policy, or safety ownership | Passive observe/log boundary only, after separate authorization; no graph control or actuation. |

Fail-closed boundaries:

- Reject a packet with unknown schema/version, duplicate JSON keys, missing required identity, malformed or mismatched immutable fingerprint, unverifiable clock policy, digest mismatch, incomplete raw-log provenance, or invalid status/value pairing.
- `exploratory` evidence is always `NON_ACCEPTANCE_EXPLORATORY_EVIDENCE_ONLY`; it may document pending source/dependency pins or measurements and cannot establish Gate B, map approval, runtime approval, or contract compliance.
- `acceptance` mode is only a structurally complete packet eligible for gate-specific review. The schema does not decide pass/fail, authorize runtime, approve a map, or waive a separately approved acceptance criterion. Any pending required pin or measurement makes an acceptance packet invalid and it must be rejected.
- Preserve raw logs and their digest as immutable evidence. A summary without the corresponding raw-log digest/provenance is insufficient for acceptance admission.
- `artifacts/maps/<map_id>/` remains the only map artifact root. Do not infer `map == world`, a transform/alignment, map approval, or runtime compatibility from a load, pose, metadata, or measurement session.
- Legacy or simulation sources are not acceptance evidence for runtime ownership or measured behavior unless an active authority explicitly defines that use; no such use is created here.
- Do not invent range, freshness, skew, buffer, receipt timeout, geometry, or other numeric thresholds. Keep absent values `PENDING_MEASUREMENT`.

## 4. Evidence packet modes and admission

The JSON Schema defines packet shape, not a populated packet. It separates immutable dependency fingerprints, source pins, package-version locks, profile/config identity, clock policy, runtime graph identity, optional WP-05 map identity, raw-log digest/summary, metrics inventory, rejection inventory, classification, and structural acceptance eligibility. The schema intentionally contains no lock/version/source instance, measurement result, threshold, or session instance.

`exploratory` permits incomplete dependency/source pins and pending metrics, but is permanently non-acceptance evidence. `acceptance` requires complete immutable fingerprints, at least one source pin and package-version lock, a resolved profile identity with the applicable global `config_hash`, declared clock policy, runtime graph endpoint/remap/namespace identity, collector version, code commit, harness-configuration hash, raw-log digest and summary, and a complete rejection histogram. If WP-05 is in scope, it also requires map identity under the canonical artifact root. All required metrics must be present as `VALID`, without pending measurement entries. Consumers must reject unknown fields and duplicate keys; JSON Schema validation alone cannot detect duplicate object keys after a permissive parser has collapsed them.

Even a schema-valid acceptance packet is only structurally eligible for separate gate-specific review. It is not an acceptance conclusion, Gate B pass, map approval, runtime approval, or authorization. The schema contains no project threshold values; applicable approved criteria must be referenced as immutable evidence and evaluated under their own authority.

## 5. Lifecycle, PEP routing, and unchanged status

At exact source base `cc0018560b20a52fa6d3c9cf26abbe0ef4c6227a`, this decision/schema pair is a review-candidate snapshot. Only after independent audit PASS, separate exact-commit User authorization, fast-forward, and remote-ref verification for the exact candidate may the records be described as `INTEGRATED_L1_RUNTIME_MEASUREMENT_GOVERNANCE_PLAN_ONLY`. Integration does not make them technical runtime-binding authority, runtime evidence, runtime authorization, map approval, or Gate B acceptance.

The PEP critical path is: integrate this measurement-plan/schema governance record → separately authorize a passive measurement harness → collect exploratory evidence if useful → close required immutable source/package/profile pins and measurements → separately authorize any acceptance-grade collection/validation needed by Gate B or WP-05 → independent gate-specific review. A harness that changes architecture or public/runtime ownership requires L2 change-control. This ordering does not authorize any of those steps.

```text
WP-04: BLOCKED_BY_CONTRACT
GATE_A_STRUCTURAL_PRIMITIVES: PASSED
GATE_B: NOT_STARTED
WP-05: OPEN
MAP_ARTIFACT: DRAFT_ON_INTEGRATION_NOT_APPROVED
WORLD_FRAME: NOT_DECLARED
RUNTIME_COMPATIBILITY: NOT_VALIDATED
CODE_AUTHORIZATION: GRANTED_BOUNDED_FAIL_CLOSED_INTERNAL_SEAMS_NONEXECUTING_OBSERVATION_INGRESS_AND_STATIC_NAVIGATION_V1_BRINGUP_SOURCES_ONLY
RUNTIME_APPROVED: NOT_APPROVED
```

## 6. F-01 schema correction and status provenance

Finding `F-01` is recorded as `USER_SUPPLIED_INDEPENDENT_AUDIT_EVIDENCE`; no audit-report hash is asserted. The source-parent review candidate `5b8ac68f51814f9520e1e72a28da5ad35fcfacea` had an acceptance-conditional schema rule that placed `minItems: 1` under the schema for each metric item. This correction moves `minItems: 1` to the `metrics_inventory` array schema inside the `session_mode: acceptance` conditional, so an empty acceptance inventory is rejected. `schema_id` and revision `1` remain unchanged; this corrects the same intended schema revision, not a new schema revision.

At source parent `5b8ac68…`, the records represent the prior review-candidate snapshot. This correction is itself a review snapshot and does not become effective from ancestry or review push. Only after independent audit PASS for this exact correction candidate, separate exact-commit User authorization, fast-forward, and remote-ref verification may the records be described as `INTEGRATED_L1_RUNTIME_MEASUREMENT_GOVERNANCE_PLAN_ONLY`.

The correction changes no measurement plan, ownership, L1/L2 boundary, source/package pin, lock instance, threshold, harness, profile, `config_hash`, map approval, runtime authorization, or acceptance conclusion. WP-04 remains `BLOCKED_BY_CONTRACT`; Gate A `PASSED`; Gate B `NOT_STARTED`; WP-05 `OPEN`; map remains draft/not approved; `WORLD_FRAME: NOT_DECLARED`; `RUNTIME_COMPATIBILITY: NOT_VALIDATED`; code authorization is unchanged; `RUNTIME_APPROVED: NOT_APPROVED`.
