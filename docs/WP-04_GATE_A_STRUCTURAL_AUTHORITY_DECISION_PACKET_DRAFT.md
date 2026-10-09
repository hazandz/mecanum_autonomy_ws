# WP-04 Gate A — structural authority decision packet

**Status:** DRAFT_FOR_PROJECT_OWNER_USER_DECISION_AND_FOCUSED_INDEPENDENT_AUDIT
**Work package:** WP-04-POLICY-CORE-P0
**Candidate base:** origin/integration/implementation at c37a5bff9dd6cc32fc503cdd796b31720a58a616
**Implementation-scope packet provenance:** branch wp-04-gate-a-implementation-packet-c37a5bff, commit b70da187885418323d1f3bbd7ed088248fc80884, path docs/WP-04_GATE_A_IMPLEMENTATION_PACKET_DRAFT.md, SHA-256 08323e002cb1768cac95bb149089181b7eaf2119e96a999f73f81ffa4c94fb09. Per the supplied work-package authority, that scope packet passed audit. This decision packet does not reproduce or expand that audit.

## 1. Purpose and decision boundary

This packet asks the Project Owner/User to resolve structural details that remain PENDING for a possible later Gate A implementation packet covering only:

1. immutable ObservationCutoffV3 core type and structural fail-closed validation; and
2. immutable structural ObservationInputContractV3 model shapes, including exact approved contract references.

It presents choices but selects none. No choice below is effective until explicitly decided and recorded through the applicable governance process. This is not CODE_AUTHORIZATION, does not assert that Gate A has passed, does not close or unblock WP-04, and grants no ROS, runtime, HIL, hardware, deploy_sim, or deploy_real authority.

The PEP-001 dependency remains WP-04 → WP-03. At this baseline WP-03 is CLOSED; WP-04 remains BLOCKED_BY_CONTRACT. This packet makes no status or dependency transition.

## 2. Authority and provenance map

| Source | Exact identity at the reviewed baseline | What it can establish here |
|---|---|---|
| Architecture | docs/MECANUM_NAV_DRL_Architecture.docx, SHA-256 f0fb1ebede5f4fa18604610c04bb13587d456173b4fd942dba77e44d49777860 | Highest architecture authority, including the fixed 81D observation boundary and Ground Truth isolation. It does not specify the Python field layout or constructor API for these two primitives. |
| PEP-001 | rev. 0.5.0, docs/governance/PROJECT_EXECUTION_PLAN.md, SHA-256 ffcf5cbbbd25d174ff2ed97dd7fe4297ccefe5eaaf0f95d00b69aba1a820807b | Controls sequencing and constrained Gate A scope. It permits preparation/audit of an exact packet after canonical integration; it does not grant implementation authorization. |
| ACR8 | docs/ACR_V3_OBSERVATION_BOUNDARY_CLOSURE.md, rev. 8, SHA-256 03fef021f6b9731f811f83a5e53aae1c430bdc2ea76815a8ada416f1a5bf772c | Current approved ACR authority for active Gate A/Gate B scope. §5.1 requires cutoff strictly after both barriers, consistent lifecycle identity/epoch/generation/profile ROS-time domain, stated owners, typed fail-closed behavior, and canonical statuses. §5.2 makes config_hash opaque caller-supplied provenance and prohibits primitive generation, calculation, verification, or promotion into a config field. |
| QoS6 / ACR8 approval provenance | docs/governance/decisions/QOS_REVISION_6_ACR_REVISION_8_BUNDLE_APPROVAL.md, SHA-256 4d740559f850f179387db802df845748068f75a21266fd1edb52402b2c72c529 | Records the approved bundle and document/status authority; it is not code authorization. |
| QoS6 | docs/RECEIPT_TOPIC_QOS_CONTRACT.md, rev. 6, SHA-256 4200cd2fbdc81a19400f168dd3526eb7871ac2251049fc7c4f5d5c2fddfd2022; transport ID mecanum.final-issued-receipt-topic-qos/v2, manifest SHA-256 338bea1b7350d3b82146c7e728516ec7947471ee68db0f8871ddb72071b79620 | Approved transport-contract identity and pinned receipt-related provenance; does not prescribe Python model constructors. |
| Registry | docs/governance/CANONICAL_SOURCE_REGISTRY.md, SHA-256 75d63ea7500f1a0c442100bb3d9dd9291ed27358e6061e5ac1fcc25ac0afe879 | Selects ACR8, QoS6 and receipt v2 interface/dependency/transport artifacts as canonical sources. |
| Gate A PEP change control | docs/governance/decisions/WP-04_GATE_A_SEMANTIC_BUNDLE_PEP_CHANGE_CONTROL.md, SHA-256 4876a0ad5afbe355ce5f410b9e5dbb2ef669455deedf2e2b2c9ca864c7425bb2 | Explains the PEP provenance-versus-authority boundary; adds no field/API semantics. |
| S2 rev.2 provenance only | origin/docs-v3-observation-contract-import at d3ca85536e35b38f7f3dffcf1dfd1bc16983aae9, docs/architecture/proposals/v3-observation-contracts/ACR_S2_SNAPSHOT_SYNCHRONIZATION_TEMPORAL_CONTRACT.md; full-document SHA-256 e1468d0373922a1806e14da91e7cc0336bcc7d70c4cd3ec4fc749078d86b70ab; embedded contract/manifest ID mecanum.snapshot-synchronization-temporal/v1, SHA-256 1be31c1915fedd86f269cee5214d794da0899a0d69dbb0ba5392e619813d4a8f | Immutable semantic-design provenance labeled DRAFT — PENDING_INDEPENDENT_ARCHITECTURE_REVIEW_AND_USER_APPROVAL. Pinning in PEP does not promote or independently approve it. |
| OIC rev.6 provenance only | Same source branch/commit; docs/architecture/proposals/v3-observation-contracts/OBSERVATION_INPUT_CONTRACT_V3_DESIGN.md; full-document SHA-256 200703949d6b326a30ee8e2f75cd2cd14054576e6772ddc6ae3ff670e48eb76c | Design provenance labeled REVISED_DRAFT — PENDING_INDEPENDENT_ARCHITECTURE_REVIEW_AND_USER_APPROVAL; not canonical field/API authority. |
| V3 Boundary Specification rev.7 supporting provenance | Same source branch/commit; docs/architecture/proposals/v3-observation-contracts/V3_OBSERVATION_BOUNDARY_SPECIFICATION.md; full-document SHA-256 47ba6c432cc53798e9f8a97f3c0a97aae586d24bef98113716a4493e57ad4eeb | Supporting design provenance only; does not replace ACR8 or independently determine these primitive APIs. |

PEP explicitly says it pins the S2/OIC bytes without approving, canonicalizing, promoting, or treating either draft as independently satisfying an architecture/approval gate. Neither draft grants implementation authorization. Any field, literal, alias, status mapping, or model shape found only in a draft is reported here as provenance only.

Registry/approval select receipt v2 artifacts as canonical sources, while ACR8 §5.2 retains proposal-era labels for some receipt pins. This packet does not silently reconcile or amend that wording. The exact receipt-interface identity and its applicability to a structural reference should be confirmed in the focused audit/decision record; no receipt bridge or integration behavior is in Gate A.

## 3. Approved invariants versus unresolved representation

The following are requirements from approved ACR8/PEP scope, not decisions about Python spelling or object layout:

- The cutoff is strictly later than both action and reset barriers.
- Cutoff/barriers share lifecycle identity, epoch/reset epoch, generation/runtime generation, and active profile ROS-time domain.
- SafetyLifecycle is the sole owner of action/reset barriers. RobotRuntimeAdapter.wait_transition_snapshot(after=receipt) is the sole operational creator of one cutoff per transition. A pure-core primitive accepts and validates caller-supplied facts; it does not create, revise, infer, round, or replace operational facts.
- Validation is immutable, typed and fail-closed. ACR8 preserves these canonical status names: INPUT_MISSING_NON_READY, LIFECYCLE_OR_CONTRACT_MISMATCH_NON_READY, BARRIER_NOT_PASSED_NON_READY, CUTOFF_BARRIER_ORDER_NON_READY, FUTURE_STAMP_CONTRACT_ERROR, INPUT_STALE_NON_READY, SENSOR_SYNC_MISS_NON_READY, REFERENCE_SYNC_MISS_NON_READY, ORDERING_CONTRACT_AMBIGUITY_NON_READY, BUFFER_OVERFLOW_NON_READY, and GENERATION_INVALIDATED_NON_READY.
- config_hash is opaque caller-supplied provenance only. The primitive must not create, calculate, verify, or promote it into configuration.
- Exact references must not be aliased, substituted, silently defaulted, or resolved through fallback.

Approved material does not decide whether those facts are represented as direct dataclass fields, a nested identity value, constructor-only context, a result object, an exception, or a status enum. It also does not decide coercion, keyword/positional rules, equality/hash behavior, or exact primitive-level mapping from a structural failure to the ACR8 status vocabulary. These are the decisions requested below.

## 4. ObservationCutoffV3 — field/API decision matrix

The S2 draft’s field proposal is listed to expose choices, not to adopt it. Draft proposal means only bytes at the pinned S2/OIC provenance in §2. Pure-core/test impact describes a future exact implementation; no implementation is part of this packet.

| Item still PENDING | Approved authority says | Draft-only proposal / not authority | User decision needed | Future pure-core and test impact |
|---|---|---|---|---|
| Immutability and object form | PEP requires an immutable core type; ACR requires structural fail-closed validation. | S2 calls it immutable and transaction-scoped. | Choose frozen dataclass, another immutable value type, or defer representation to a separately reviewed packet. | Determines mutation tests, construction surface and whether nested values must also be immutable. |
| transaction_id presence/type/identity scope | ACR requires one cutoff object created operationally once per transition; PEP names the operational owner. No approved scalar representation or uniqueness algorithm is stated. | S2/OIC proposes transaction_id: IdentifierV3, opaque and unique within (reset_epoch, runtime_generation); adapter owns it. | Decide whether a direct field is required, accepted Python type/validation and uniqueness scope; core must not generate identifiers. | Field/immutability/equality tests; core validates representation only and does not mint IDs. |
| creation_owner | PEP assigns the sole operational creator to RobotRuntimeAdapter.wait_transition_snapshot(after=receipt). Core does not create operational facts. | S2/OIC proposes a literal field exactly "RobotRuntimeAdapter.wait_transition_snapshot(after=receipt)". | Decide whether owner is encoded as a field/literal or enforced at an API boundary/provenance; no adapter is in this Gate A implementation. | If a field: exact-literal and mismatch tests. If omitted: core validates other supplied fields only; operational ownership remains outside Gate A. |
| Lifecycle identity | ACR requires cutoff and barriers to share lifecycle identity. PEP does not define a field name/type. | S2/OIC has no distinct lifecycle-identity field; it uses epoch/generation and source/contract identity language. | Decide explicit identity field/type or document which approved fields collectively establish identity; do not silently infer absent identity. | Cross-identity mismatch tests; exact type and comparison rule must be fixed. |
| reset_epoch | ACR requires matching epoch/reset epoch. PEP does not specify concrete Python type/range. | S2/OIC proposes StrictNonNegativeInt, rejecting bool, floats and non-integers. | Decide accepted type (including bool/subclass treatment), bounds, and whether normalization is forbidden. | Boundary and invalid-type tests; no runtime epoch tracker. |
| runtime_generation | ACR requires matching generation/runtime generation. PEP does not specify concrete Python range/type. | S2/OIC proposes StrictNonNegativeInt. | Decide accepted type/range and mismatch behavior; no generation advancement logic. | Boundary/type/mismatch tests; no clock rollback or buffer behavior. |
| schema_id presence/type/value | ACR/Architecture constrain V3 semantics and exact references; PEP does not select field spelling or schema literal for this primitive. | S2/OIC proposes schema_id: IdentifierV3 referring to active V3 schema. Architecture names obs-v3-l72-g3-t3-c3-f32 for the 81D observation, but Gate A does not build that vector. | Decide whether schema ID belongs in cutoff; if so, exact ID/type. Do not infer 81D construction is included. | Exact-string/identifier tests; no 81D encoder or vector fixture. |
| config_hash presence/type/value treatment | ACR8 says caller-supplied opaque provenance and forbids primitive generation/calculation/verification or config-field promotion. | S2/OIC proposes config_hash: Sha256V3 associated with active resolved config. | Decide whether the primitive carries this opaque value and, if carried, whether validation is only structural string shape. It may not compute, resolve, verify, default, or bind a config. | Tests can assert preservation/shape only; tests must prove no hashing/config dependency is introduced. |
| cut_off_ros_ns name/type/range and time-domain representation | ACR requires active profile ROS-time domain and strict ordering after both barriers; no integer width or sentinel rule is specified. | S2/OIC proposes StrictNonNegativeInt and cut_off_ros_ns. | Decide exact field name/type/range and how the common profile ROS-time domain is represented (explicit domain field, shared context, or another approved mechanism). No clock conversion is implied. | Integer boundary/type tests and equal-domain tests; no ROS clock access or unit conversion. |
| action_barrier_ros_ns and reset_barrier_ros_ns | ACR requires both barriers, same lifecycle/epoch/generation/time domain; SafetyLifecycle is their sole owner. | S2/OIC proposes two nonnegative integer fields supplied by SafetyLifecycle. | Decide exact field names/types and whether core value carries each barrier or validates them through a nested immutable value. Core cannot create/advance/replace them. | Presence, provenance-boundary and matching-domain tests; no lifecycle implementation. |
| Strict ordering | ACR explicitly requires cutoff > action barrier and cutoff > reset barrier; equality fails closed. | S2 draft maps at-or-before either barrier to CUTOFF_BARRIER_ORDER_NON_READY. | The invariant is fixed. Decide whether constructor failure, typed validation result, or status-bearing error expresses violation. | Tests for before/equal/after against each barrier and both; no usable object escapes a failed validation. |
| Cross-object schema/identity comparisons | ACR requires same lifecycle identity/domain; config hash remains opaque. | S2 describes a downstream assemble_at consumer comparing transaction/lifecycle/schema/config/barrier values; that consumer is outside Gate A. | Decide which comparisons belong in the structural type versus a future caller. No cross-object assembler is included. | Gate A tests only local structural invariants; no snapshot selection or assembly tests. |
| Constructor and validation API | ACR/PEP require structural validation, not a Python signature. | Drafts do not establish binding Python constructor or canonical exception/result API. | Choose direct constructor vs named factory, keyword-only vs positional arguments, validation method (if any), and coercion rules. | Signature, required-argument, invalid-type/value, immutability, and no-side-effect tests. |
| Equality, hashing, repr/serialization | No approved rule for equality/hash/serialization of this primitive. | Drafts describe an internal value but do not establish approved Python serialization API. | Decide value equality, hashability and whether serialization is prohibited/deferred. | Deterministic equality/hash tests and serialization-boundary tests only if selected. |

### 4.1 Error behavior for ObservationCutoffV3

ACR8 canonicalizes the status vocabulary above, but does not fully specify the Python carrier for structural validation. S2 draft uses CUTOFF_BARRIER_ORDER_NON_READY for barrier-order failure and LIFECYCLE_OR_CONTRACT_MISMATCH_NON_READY for owner/lifecycle mismatch in its downstream flow. That flow is provenance only and includes S2 behavior outside this primitive.

For each failure class, choose: (a) raise a typed domain exception carrying an approved status; (b) return a typed validation result/status; or (c) another explicitly chosen typed interface. Also decide whether wrong Python type is a caller/programming error distinct from a validly typed but non-ready fact. Existing generic TypeError/ValueError use in core is implementation evidence, not authority. Existing core/exceptions.py has no Gate-A-specific observation status type. No choice is made here.

The later exact packet must map at least: missing required fact; wrong type/range; lifecycle/epoch/generation mismatch; time-domain mismatch; cutoff equal to/before either barrier; and invalid exact identifier/hash representation. Other ACR8 statuses for stale/synchronization/buffer/future-input conditions must not become synchronizer behavior in Gate A.

## 5. ObservationInputContractV3 — structural-model decision matrix

PEP authorizes preparing immutable structural model shapes and exact approved references; it does not adopt OIC rev.6’s proposed schema. The field names below inventory the pinned OIC draft model proposal. Every listed OIC type/rule is draft provenance only. Profile-resolving and connected nested models are outside Gate A unless future authority and a future packet explicitly change scope.

| Draft model / field(s) still PENDING | Approved authority says | OIC rev.6 draft proposes | User decision and future pure-core/test impact |
|---|---|---|---|
| ContractReferenceV3.contract_id, .contract_sha256 | PEP requires exact S2 and final-issued receipt ID/SHA structural references; Registry/QoS6/approval select receipt interface v2, QoS6 transport v2 and S2 provenance pin. Exact Python field names, aliases, casing and validation API are not established. | IdentifierV3, Sha256V3. | Decide exact fields, type aliases and structural syntax validation; pin exact approved pairs from Registry/approval, not OIC draft. Test exact match, mismatch, casing/empty/shape behavior; no alias/fallback. |
| Reference identities and paths | S2: mecanum.snapshot-synchronization-temporal/v1 / 1be31c1915fedd86f269cee5214d794da0899a0d69dbb0ba5392e619813d4a8f at docs/architecture/proposals/v3-observation-contracts/ACR_S2_SNAPSHOT_SYNCHRONIZATION_TEMPORAL_CONTRACT.md (provenance-only source). Receipt interface selected by Registry/approval: mecanum.final-issued-receipt/v2 / schema SHA 0c6446674bf17373ec646519043f506a9a7a15f95d5fdd10829b0cedb956500a at ros2_ws/src/mecanum_nav_rl_interfaces/msg/FinalIssuedCommandReceipt.msg. QoS transport: mecanum.final-issued-receipt-topic-qos/v2 / manifest SHA 338bea1b7350d3b82146c7e728516ec7947471ee68db0f8871ddb72071b79620 at docs/RECEIPT_TOPIC_QOS_TRANSPORT_MANIFEST.json. | OIC §5.2 carries proposed interface/QoS references; S2 draft describes them as consumed by connected ingress/history. | Confirm which exact references are fields in the primitive model versus provenance constants, and resolve ACR8 §5.2 proposal-era labels relative to Registry/approval in audit/decision record. No bridge, endpoint, message behavior or history is Gate A. |
| ObservationInputContractV3.lidar, .goal, .measured_twist, .timing, .receipt_bridge | PEP names structural models but not these five top-level fields. ACR8 bars profile/compiler/connected implementation in Gate A. | OIC makes all five required top-level members. | Decide whether Gate A defines a smaller structural container holding exact contract references only, or adopts an explicitly approved structural subset. Do not adopt these five merely because they appear in a draft. Tests depend on chosen required-field set/nesting. |
| InputProvenanceV3.source_class, .source_id, .source_sha256 | No Gate A authority requires this provenance union or these fields. | source_class union of SIM_BASELINE, MEASURED_REGISTRY, and APPROVED_CONTRACT; identifier and SHA aliases. | Decide to exclude/defer for Gate A or seek separate authority. Tests cover enum membership and source pins only if authorized. |
| TopicQosSelectorV3.name, .message_type, .publisher_owner, .subscriber_owner, .qos_profile_id, .frame_contract_id, .freshness_policy_id | PEP excludes QoS/runtime/config/profile integration; QoS6 does not make a Python selector model part of Gate A. | Seven-field full selector of IdentifierV3, later matched against resolved config. | Gate A should not implement or resolve this selector under current scope; user may confirm explicit deferral. No selector-matching tests in Gate A. |
| Transform2DV3.parent_frame, .child_frame, .translation_x_m, .translation_y_m, .yaw_rad, .contract, .provenance | Architecture fixes TF authority/frames; Gate A excludes TF/transform/profile integration and does not decide measured extrinsics. | Identifier, finite-float, contract-reference and provenance members. | Explicitly defer. Future values/units/validation require applicable approved contract and profile evidence. No transform math or X3 extrinsic tests in Gate A. |
| LidarInputContractV3.source_topic, .sensor_model_id, .header_frame, .T_base_lidar, .raw_geometry_contract, .sector_boundaries_rad, .sector_interval_policy, .sector_reduction, .range_unit, .range_min_m, .range_max_m, .range_sanitization_contract, .source_provenance | Gate A excludes LiDAR ingress, sectorization, profile values, X3 frame/range/extrinsic and 81D construction. | Selector/model/frame IDs, transform/reference/provenance, exactly 73 boundaries, interval/reduction literals, meters and range bounds. | All beyond Gate A; pending for later profile/connected authority. Do not introduce fixture values or choose a sensor/profile. No LiDAR/normalization/sector tests in Gate A. |
| GoalInputContractV3 / SimTrainInternalGoalInputV3 fields: source_kind, reference_builder_owner, episode_goal_contract, emulator_snapshot_contract, point_semantics_frame, point_unit, reference_stamp_policy, barrier_clock_policy, lifecycle_policy, goal_distance_scale_m, validity_contract, source_provenance | Gate A excludes LocalReference creation/normalization, runtime, profile and goal semantics. Architecture’s 81D boundary does not approve OIC draft fields. | Discriminated union, draft literals/references and positive finite scale. | Defer all fields. Future packet must establish source/lifecycle/frame/unit/scale/validity from approved authority; no goal/reference behavior tests in Gate A. |
| NavigationLocalReferenceGoalInputV3 fields: source_kind, local_reference_contract, localization_provider, point_frame, point_unit, goal_distance_scale_m, source_provenance | No Gate A authority selects navigation reference provider, normalization scale or profile. | Navigation variant with frame/unit/contract/provenance and positive scale. | Defer; do not choose provider, frame alias, scale or profile value. No navigation adapter tests in Gate A. |
| MeasuredTwistInputContractV3 / SimTrainInternalMeasuredTwistInputV3 fields: source_kind, snapshot_owner, snapshot_contract, stamp_policy, barrier_clock_policy, body_semantics_frame, component_order, linear_unit, angular_unit, validity_contract, normalization_policy, out_of_range_policy, source_provenance | Gate A excludes measured-twist ingestion, validity/covariance/provenance and normalization/profile decisions. | Sim-train variant with emulator owner, vx/vy/wz order, units, policy literals and contract/provenance. | Defer every field; no emulator integration, normalization or range logic. No measured-twist profile fixtures/tests in Gate A. |
| EkfTopicMeasuredTwistInputV3 fields: source_kind, source_topic, state_estimation_owner, body_frame, component_order, stamp_policy, linear_unit, angular_unit, validity_contract, normalization_policy, out_of_range_policy, source_provenance | Gate A excludes ROS topic, EKF, frame and measured validity/covariance decisions. | EKF-topic variant with explicit selectors and policy literals. | Defer; no ROS/EKF/QoS/frame/model behavior in Gate A. No topic/profile tests. |
| ObservationTimingPolicyV3 fields: sensor_sync_contract, sensor_sync_tolerance_ns, scan_max_receive_age_ns, odom_max_receive_age_ns, reference_max_receive_age_ns, max_reference_snapshot_skew_ns, future_stamp_tolerance_ns, max_scan_buffer_items, max_motion_buffer_items, max_reference_buffer_items, ordered_insert_policy, overflow_policy, selection_policy, freshness_clock_policy, barrier_clock_policy, receipt_after_barrier_timeout_ns | Gate A excludes profile timing values, freshness, buffers, synchronizer and receipt-after-barrier behavior. ACR8 statuses do not authorize these mechanisms. | ContractReferenceV3, strict integer aliases, policy literals and numeric policy values. | Defer all fields and values to connected/profile work after required authority/evidence. No timing, buffer, freshness or synchronizer tests in Gate A. |
| ReceiptBridgeReferenceV3.receipt_interface, .receipt_topic_qos | PEP excludes receipt interface/bridge/history runtime. It requires exact references structurally but does not authorize a bridge model or endpoint. | Two ContractReferenceV3 members. | Decide whether exact refs belong in a small non-operational reference container; no bridge, history, publisher/subscriber or message handling. Tests limited to exact immutable reference values if selected. |
| Python model style and nesting | PEP requires immutable structural model shapes; it does not choose library, constructors or coercion policy. | OIC sketches strict aliases and model structures but remains REVISED_DRAFT. | Choose dataclasses/another pure-Python form, requiredness, nested immutability, unknown-field policy, signature and no-coercion rule. Tests: immutability, exact shape, missing/extra/invalid-field behavior, deterministic nesting. |

### 5.1 Error behavior for ObservationInputContractV3

Approved sources require exact references and fail-closed typed behavior but do not specify whether malformed structural models raise exceptions or return a typed result. OIC draft supplies no approved Gate A mapping. Decide separately the handling of:

- missing or unexpected field;
- wrong Python type, including bool-as-int and numeric coercion;
- malformed/unknown ID or SHA representation;
- exact ID with wrong SHA, or SHA with wrong ID;
- unsupported enum/literal or union variant;
- lifecycle/contract identity mismatch if represented;
- programmer-invalid construction versus validly typed non-ready facts.

Choices may be a typed exception carrying an approved ACR8 status, a typed result/status value, or another explicitly selected API. Do not invent a canonical status name or map every schema error to a synchronization status without decision. The later packet must give one exhaustive, non-overlapping mapping and tests for every case.

## 6. Existing implementation evidence (not authority)

At the exact base, the implementation-scope packet identifies these file facts: core/types.py, core/exceptions.py, and core/snapshots.py exist; core/v3_observation_contracts.py and test/test_v3_observation_contract_primitives.py are absent; no tracked source path for RobotRuntimeAdapter.wait_transition_snapshot(after=receipt) was identified. The proposed future file map places both primitive families in ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/core/v3_observation_contracts.py and structural tests in ros2_ws/src/mecanum_nav_rl/test/test_v3_observation_contract_primitives.py. This is packet provenance, not permission to create them now.

Direct source inspection at the base found frozen/slotted Pose2D and VelocityCommand dataclasses in core/types.py; generic project exceptions but no Gate-A observation-status type in core/exceptions.py; and frozen/slotted SensorSnapshot plus a nonnegative-integer validator that rejects bool in core/snapshots.py. These are existing implementation conventions only. They do not resolve the new primitive’s field types, API, exception mapping, or authority.

## 7. Explicit decision options for Project Owner/User

No option is preselected. The decision record should state a choice or DEFERRED for each group.

1. **Cutoff field set**
   - A. Adopt S2/OIC’s proposed nine fields (transaction_id, creation_owner, reset_epoch, runtime_generation, schema_id, config_hash, cut_off_ros_ns, action_barrier_ros_ns, reset_barrier_ros_ns) only after the relevant draft semantics have separately been elevated/approved; this packet alone does not elevate them.
   - B. Specify a smaller field set directly from approved ACR8/PEP invariants, explicitly representing lifecycle identity and time domain without operational behavior.
   - C. Defer the field schema and require a contract/PEP amendment or additional approved authority before an implementation packet.

2. **Input-contract shape**
   - A. Gate A container holds only immutable exact contract references required by PEP; all OIC nested profile/connected models are deferred.
   - B. Select a named subset of OIC rev.6 structural members for Gate A, with each selected member separately approved and all profile/connected fields excluded.
   - C. Defer all ObservationInputContractV3 field structure until OIC is revised, audited, approved and made applicable by governance.

3. **Type/constructor policy:** choose immutable representation, exact Python types/ranges, bool/subclass treatment, strictness/coercion, requiredness/defaults, constructor/factory signature, unknown-field policy, equality/hash and serialization disposition. No profile defaults or fabricated values are authorized.

4. **Validation/error API:** choose exception vs typed result/status and exact mapping for each structural failure. Preserve ACR8 canonical status spellings where applicable; decide which are relevant to primitive validation without implementing S2 behavior.

5. **Exact references:** confirm which exact S2 and Registry/approval-selected receipt references are structural model members, and decide whether they are immutable caller-supplied values, fixed constants, or both. No alias or fallback is permitted. Resolve ACR8 §5.2 proposal-era receipt-label wording in the decision/audit record rather than silently editing canonical artifacts here.

## 8. Future acceptance criteria for an exact implementation-authorization candidate

Only after decisions are recorded and any required authority/governance changes are separately approved may a new exact Gate A implementation packet be prepared. At minimum, it must require:

- a complete approved field/type/requiredness matrix for each permitted model;
- immutable constructor/factory signature, coercion/range rules, equality/hash and serialization disposition;
- explicit mapping of every invalid/missing/mismatched value to a typed failure surface, using canonical ACR8 names exactly where applicable;
- exact source ID/SHA references and tests proving no alias, substitution, fallback, hash computation or config integration;
- cutoff-order tests covering less-than/equal/greater-than against each barrier; lifecycle/epoch/generation/time-domain mismatch tests; immutability and no-side-effect tests;
- structural fixture tests only, with no profile values, measurements, provenance claims, runtime evidence, map/scenario/hardware artifacts or 81D vectors;
- static scope review proving no ResolvedConfigV3, config/compiler/profile, ROS/ROSIDL, adapter, synchronizer, buffer, receipt bridge/history, assembler/encoder, V1 or Ground Truth path was added;
- exact file allowlist, base/commit/hash and separate focused independent audit;
- later explicit user decision granting CODE_AUTHORIZATION for that exact audited code candidate. This packet’s decisions/checks do not grant it.

Gate B or a later connected/profile-resolving work package remains separate and needs its own authority, profile-specific evidence and approval. No profile timing, buffer, freshness, measured-twist validity/covariance/provenance, LiDAR X3 extrinsic/range/frame, or other unresolved value is selected here.

## 9. Fixed exclusions and status

This packet does not authorize or describe implementation of configuration/compiler/profile resolution; ROS/runtime adapters; receipt bridge/history or runtime integration; S2 receipt/synchronizer/buffer integration; assembler/encoder or construction of the 81D observation; V1 observation/decoder/snapshot reuse; Ground Truth; HIL; hardware; deploy_sim; or deploy_real. It creates no schema, config, module or test file.

    DECISION_PACKET: DRAFT_FOR_PROJECT_OWNER_USER_DECISION_AND_FOCUSED_INDEPENDENT_AUDIT
    WP-03: CLOSED (unchanged at the stated baseline)
    WP-04: BLOCKED_BY_CONTRACT
    GATE_A: NOT_PASSED; STRUCTURAL_DECISIONS_PENDING
    CODE_AUTHORIZATION: NOT_GRANTED
    RUNTIME_APPROVED: NOT_APPROVED
