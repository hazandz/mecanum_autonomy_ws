# WP-04 Gate A — implementation-authorization packet (refreshed draft)

**Packet status:** `DRAFT_CANDIDATE_PENDING_INDEPENDENT_AUDIT_AND_SEPARATE_USER_AUTHORIZATION`
**Work package:** `WP-04-POLICY-CORE-P0`
**Candidate branch:** `wp-04-gate-a-preimplementation-governance-bundle-401593a`
**Integration base:** `origin/integration/implementation@401593a4268af572ef4690177539360b1c15410a`
**Source packet:** `wp-04-gate-a-implementation-authorization-packet-f9987be@8ef93277502b9cc7282a544459ae3aa495b2f049`; path `docs/WP-04_GATE_A_IMPLEMENTATION_AUTHORIZATION_PACKET_DRAFT.md`; SHA-256 `431c993a837a156ea2af2e6cad3e6b6d886caa544fd466f524c6bfe4dd662d11`
**Canonical Gate A structural schema at base:** `docs/OBSERVATION_GATE_A_STRUCTURAL_SCHEMA.md`; SHA-256 `43537b8f0edafbe809e6f70bda86808f87b12f146ed45509c4bfbacd26956ad3`
**Error-carrier decision source:** `docs/governance/decisions/WP-04_GATE_A_ERROR_CARRIER_DECISION.md`, copied from `wp-04-gate-a-error-carrier-decision-record-401593a@f5f0a4a0351d40335ad585afa36430f3b639cea3`; SHA-256 `72a2c94df548cb00557b1777e10d11b96b386329894edaf34e1d81c07ed4e94d`; user-supplied focused audit verdict `READINESS_FOR_CANONICAL_INTEGRATION: PASS`.

This packet refreshes the audited implementation-scope proposal using the exact structural schema and the error-carrier decisions captured in the cited decision record. The record is included byte-identically in this four-path candidate. The entire governance bundle remains pending independent audit and a separate explicit user decision on its exact final commit. This packet does not authorize implementation, create a code candidate, establish Gate A as passed, or change any work-package status or dependency. A later, separate explicit `CODE_AUTHORIZATION` is required for an exact code/test candidate after focused audit.

## 1. Authority and exact inputs

| Source | Status and exact identity | Use and boundary in this packet |
|---|---|---|
| `docs/governance/PROJECT_EXECUTION_PLAN.md` | PEP-001 rev.0.5.0 at the base | Controls WP sequencing and permits preparation/audit of the constrained primitive-only Gate A packet. WP-04 remains `BLOCKED_BY_CONTRACT`; WP-03 is `CLOSED` at this base. |
| `docs/OBSERVATION_GATE_A_STRUCTURAL_SCHEMA.md` | Exact selected schema bytes at the base; full-document SHA-256 `43537b8f0edafbe809e6f70bda86808f87b12f146ed45509c4bfbacd26956ad3` | Governs structural fields, types, value semantics, reference pairs, validation and the two fail-closed mappings. Activation provenance is reconciled by the Registry proposal in this candidate; this packet does not change schema bytes. |
| `docs/ACR_V3_OBSERVATION_BOUNDARY_CLOSURE.md` | ACR rev.8; full SHA-256 `03fef021f6b9731f811f83a5e53aae1c430bdc2ea76815a8ada416f1a5bf772c` | Approved Gate A boundary and exclusions, according to the current approved bundle. |
| `docs/RECEIPT_TOPIC_QOS_CONTRACT.md` | QoS rev.6; full SHA-256 `4200cd2fbdc81a19400f168dd3526eb7871ac2251049fc7c4f5d5c2fddfd2022` | Approved bundle context only; transport contract is not a model member or behavior implemented by this packet. |
| `docs/governance/decisions/QOS_REVISION_6_ACR_REVISION_8_BUNDLE_APPROVAL.md` and `docs/governance/CANONICAL_SOURCE_REGISTRY.md` | Approval record SHA-256 `4d740559f850f179387db802df845748068f75a21266fd1edb52402b2c72c529`; Registry at the base | Select/pin the canonical receipt message schema path, ID and SHA stated below. |
| S2 rev.2 and Observation Input Contract V3 rev.6 | PEP provenance pins only; S2 `DRAFT`, OIC `REVISED_DRAFT` | Provenance only; neither supplies defaults or independently authorizes fields or behavior. |
| V3 Observation Boundary Specification rev.7 | Supporting design provenance under PEP-001 | Provenance only; it does not replace current authority. |
| `docs/governance/decisions/WP-04_GATE_A_ERROR_CARRIER_DECISION.md` | Source commit/hash above; audit PASS reported by User; copied unchanged into this candidate | Captures accepted error-carrier decisions. Until this exact governance bundle is separately audited and integrated, the copied record and refreshed packet remain candidate documentation. |

The selected receipt schema is `ros2_ws/src/mecanum_nav_rl_interfaces/msg/FinalIssuedCommandReceipt.msg`, contract ID `mecanum.final-issued-receipt/v2`, schema SHA-256 `0c6446674bf17373ec646519043f506a9a7a15f95d5fdd10829b0cedb956500a`. `docs/RECEIPT_INTERFACE_DEPENDENCY_CLOSURE_MANIFEST.json` records transitive ROS message-definition provenance; it does not select the receipt schema.

### 1.1 Structural-schema activation evidence and boundary

The exact schema file is present at the base with the SHA above. Its review provenance is `wp-04-gate-a-receipt-selector-attribution-correction@f9987be4429349ef9110c45cf97a89728a5e4229`; that correction is a descendant of `988a74b529fdb4bcf77f341db5c6d115e8511a9b`, and `f9987be…` is an ancestor of the required integration base `401593a…`. The focused static re-audit report `INDEPENDENT_FOCUSED_STATIC_REAUDIT_WP04_F01_RECEIPT_SELECTOR_ATTRIBUTION_F9987BE4.md` (SHA-256 `6902ebce5ec874a5922e06c2623cba7edb09083f493d7aa8242ecc715c1f60c5`) reported PASS. The Project Owner/User subsequently explicitly authorized fast-forward of that exact candidate into `integration/implementation`; ancestry at this base and the exact file bytes/hash provide the integration evidence.

Accordingly, the Registry change in this candidate reconciles the structural schema's source-selection/activation status as active at the stated integration base. The schema file's original candidate-status wording and hash are preserved unchanged as pre-integration document history; the Registry reconciliation is limited to activation status/source selection. It does not change schema semantics, pass Gate A, close WP-04, or grant implementation/runtime authorization. This current four-path candidate, including its refreshed packet and Registry/Ledger changes, remains candidate-only until it passes its own independent audit, receives separate user authorization for its exact final commit, and that commit is fast-forwarded with the remote ref verified.

## 2. Baseline inventory and proposed future paths

The following paths were checked at the exact base. “Existing” means the path exists at the baseline; it does not imply approval to modify it in this packet.

| Path | Baseline state | Proposed Gate A disposition |
|---|---|---|
| `ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/core/types.py` | Existing pure-domain `Pose2D` and `VelocityCommand` value objects | Reference only; no change proposed. |
| `ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/core/exceptions.py` | Existing project exception hierarchy; no `GateASchemaValidationError` | Reference only; do not modify. The Gate A error type is proposed in the new primitive module below. |
| `ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/core/snapshots.py` | Existing `SensorSnapshot`, including synchronized sensor data and array handling | Existing but outside Gate A; do not modify or reuse as the cutoff/input-contract model. |
| `ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/core/__init__.py` | Existing core exports | Do not modify or add an export/serialization surface in Gate A. |
| `ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/observations/synchronizer.py`, `assembly.py`, `encoder.py` | Existing connected observation components | Prohibited from modification or use to add Gate A behavior. |
| `ros2_ws/src/mecanum_nav_rl/test/test_observation_assembly.py`, `test/test_snapshot_synchronizer.py` | Existing integration-oriented observation tests | Reference only; do not extend them for this primitive. |
| `ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/core/v3_observation_contracts.py` | Absent at the baseline | Proposed-to-create only in a later, separately authorized code candidate; contains the three structural value types and typed Gate A error carrier. |
| `ros2_ws/src/mecanum_nav_rl/test/test_v3_observation_contract_primitives.py` | Absent at the baseline | Proposed-to-create only in that later code candidate; focused pure-Python tests. |

These two proposed-to-create paths are the future exact code/test allowlist proposal, not permission to create them now. No package metadata, `__init__.py`, configuration, interface, or runtime path is included.

## 3. Narrow implementation scope proposed for later authorization

Only these definitions and structural checks are proposed:

- `ObservationCutoffV3`;
- `ContractReferenceV3`;
- `ObservationInputContractV3`;
- typed `GateASchemaValidationError` with the accepted typed-detail API in §3.3;
- construction-time structural validation and the two existing status mappings in the canonical schema.

No clock, lifecycle, receipt, or synchronization operation is proposed. The types only hold and validate caller-supplied structural values.

### 3.1 `ObservationCutoffV3`

The future implementation must use exactly seven keyword-only fields:

```python
ObservationCutoffV3(
    *,
    lifecycle_identity: str,
    epoch: int,
    generation: int,
    time_domain: str,
    cutoff_time_ns: int,
    action_barrier_time_ns: int,
    reset_barrier_time_ns: int,
)
```

- `lifecycle_identity` and `time_domain`: exact built-in `str`, non-empty, opaque, exact comparison, no normalization.
- `epoch`, `generation`, and all three timestamps: exact built-in `int`; reject `bool`, subclasses, and numeric coercion; non-negative; no upper bound.
- Timestamps are nanoseconds in the profile ROS-time domain.
- Require `cutoff_time_ns > action_barrier_time_ns` and `cutoff_time_ns > reset_barrier_time_ns`. Do not impose an ordering between the two barriers.
- Do not add `transaction_id`, `creation_owner`, `schema_id`, or `config_hash`.

### 3.2 Reference-only input contract

```python
ContractReferenceV3(*, contract_id: str, contract_sha256: str)
ObservationInputContractV3(
    *,
    s2_provenance_reference: ContractReferenceV3,
    receipt_interface_reference: ContractReferenceV3,
)
```

- Each string is exact built-in `str`, non-empty, compared exactly, and not normalized. The two models are strict immutable structural values; no defaults or coercion.
- Validate only the exact selected ID/SHA pairs; no aliasing, fallback, lookup, normalization, or additional generic syntax validation.
- S2 pair: `mecanum.snapshot-synchronization-temporal/v1` / `1be31c1915fedd86f269cee5214d794da0899a0d69dbb0ba5392e619813d4a8f`; its role remains provenance-only.
- Receipt pair: `mecanum.final-issued-receipt/v2` / `0c6446674bf17373ec646519043f506a9a7a15f95d5fdd10829b0cedb956500a`.
- Do not add QoS transport, ACR, approval-record, or Registry hashes to the model.

### 3.3 Value and accepted error-carrier semantics

The three value types use `@dataclass(frozen=True, slots=True, kw_only=True)`, reject subclasses and unknown fields, use field-wise value equality and generated field-wise hash, and retain default `repr`. They have no defaults, coercion, alias/fallback, or serialization/export API.

`GateASchemaValidationError` exposes a typed `detail` carrier:

- A mapped failure is `GateASchemaMappedFailure`; its public detail fields carry the exact existing ACR8 `status`, the accepted diagnostic-only `failure_kind`, and `field_name`.
- A construction failure is `GateASchemaConstructionFailure`; it has diagnostic-only `reason` and `field_name`, and has no ACR8 status member.
- Public detail fields are not reassignable through ordinary attribute assignment after creation. This is not absolute/deep immutability and does not promise protection against reflective or low-level mutation.
- `field_name` is exact built-in `str` or `None`; it names a schema field when determinable and is `None` otherwise. No additional multi-error precedence rule is introduced by this packet.
- The accepted diagnostic labels are classification only, not ACR8 statuses and not new status vocabulary:

| Failure | `failure_kind` / `reason` | Status |
|---|---|---|
| Cutoff does not pass one or both barriers | `CUTOFF_BARRIER_ORDER` | `CUTOFF_BARRIER_ORDER_NON_READY` |
| Exact contract ID/SHA pair mismatch | `CONTRACT_REFERENCE_MISMATCH` | `LIFECYCLE_OR_CONTRACT_MISMATCH_NON_READY` |
| Missing constructor field | `MISSING_FIELD` | None |
| Unknown constructor field | `UNKNOWN_FIELD` | None |
| Wrong exact type | `WRONG_TYPE` | None |
| `bool` supplied for integer | `BOOL_AS_INT` | None |
| Negative integer | `NEGATIVE_VALUE` | None |
| Empty string | `EMPTY_STRING` | None |

Mapped details carry only the applicable existing status; construction details carry no status. No new status is created, and fail-closed semantics are unchanged. Raw input values are not retained. `Exception.args`, `str(exc)`, `repr(exc)`, exception notes, and direct caller construction of `GateASchemaValidationError` are outside the public carrier contract (`NON_CONTRACTUAL`); callers rely only on the documented `detail` and its public fields.

The error-carrier choices above are recorded in the cited decision record. Until this documentation bundle is separately audited and integrated, this refreshed packet remains candidate evidence; it does not itself make the record canonical or authorize implementation.

## 4. Acceptance criteria and checks for a later authorized code candidate

These checks are expected for a later code candidate. They were **not run** for this documentation work package.

### Positive construction and value semantics

- Construct a valid cutoff with all seven required keyword arguments and exact built-in values; cover valid barrier pairs in both relative orderings while cutoff remains greater than both.
- Construct valid `ContractReferenceV3` and `ObservationInputContractV3` values using the exact S2 provenance pair and canonical receipt v2 pair.
- Verify keyword-only construction, exact dataclass field/member sets, frozen assignment failure, slots/no instance `__dict__`, field-wise equality/hash behavior, and default `repr` without a custom serializer.
- Verify no implicit defaults and no extra cutoff or input-contract members.
- Verify the accepted `GateASchemaValidationError.detail` variant, diagnostic label, `field_name`, and mapped-vs-construction status presence/absence; verify mapped status literals exactly.
- Verify public detail fields reject ordinary attribute reassignment and that raw input values are not retained. Do not test reflective/low-level mutation as a promised guarantee.
- Do not make conformance depend on `Exception.args`, `str(exc)`, `repr(exc)`, notes, or direct caller construction; these are `NON_CONTRACTUAL`.

### Fail-closed validation matrix

- For each required constructor field, test missing and unknown arguments.
- Test wrong exact types, `bool` for each integer field, integer/string subclasses, numeric objects/coercion candidates, negative epoch/generation/timestamps, and empty identity/domain/reference strings.
- Test each cutoff/barrier boundary independently: equality and earlier cutoff against action barrier and against reset barrier. Verify the selected order mapping; do not require one barrier to precede the other.
- Mutate each reference ID and SHA independently and test cross-paired values; verify exact-pair mismatch mapping and no alias/fallback/normalization.
- Verify construction failures produce `GateASchemaConstructionFailure` without an ACR8 status; verify mapped failures produce `GateASchemaMappedFailure` with only the exact existing status mappings.
- Assert diagnostic-only labels and `field_name` behavior as recorded; do not add an unapproved precedence rule for multiple simultaneous errors.

### Static/import-purity/no-regression

- Statically verify the exact seven cutoff fields, two input-contract members, two reference fields, keyword-only/no-default signatures, strict exact-type policy, and exact accepted ID/SHA pairs.
- Statically inspect imports of the new primitive module for absence of `rclpy`, ROS/ROSIDL-generated messages, Gazebo, configuration/compiler/profile modules, or runtime adapters.
- Import the module in a pure-Python test context and verify import does not import ROS packages or perform I/O, clock reads, repository lookups, or message construction.
- Verify existing observation assembly/synchronization, config, interface, and package files remain unchanged in the later code candidate diff.

No Gate A ROS/ROSIDL integration or connected integration test is proposed here. A future implementation work package may run only checks explicitly authorized for its exact code candidate. This packet authorizes none of those checks.

## 5. Explicit exclusions, dependencies, and remaining constraints

Out of scope: `rclpy`, ROS/ROSIDL, QoS/TF/DDS, clock conversion, freshness, synchronization, buffers, receipt bridge/history, assembler/encoder, 81D construction, LiDAR, LocalReference, measured twist, PPO/training, runtime, HIL, hardware, `deploy_sim`, and `deploy_real`. Also excluded: `ResolvedConfigV3`, configuration/compiler/profile, YAML, V1 observation, Ground Truth, S2/OIC/V3-draft-derived defaults, and all WP-05 artifacts/findings.

PEP-001 rev.0.5.0 remains sequencing authority: WP-04 is `BLOCKED_BY_CONTRACT`; WP-03 is `CLOSED` at this base and the recorded WP-04 dependency is unchanged. This packet does not alter PEP, status, dependency, architecture, contract semantics, or WP-05. No Gate A pass or implementation eligibility is inferred from schema/decision provenance.

The candidate bundle itself requires focused independent audit and a separate explicit Project Owner/User authorization for its exact final commit before canonical integration. Even integration of this documentation bundle would not grant `CODE_AUTHORIZATION` or pass Gate A. A separate exact code/test candidate must be prepared, audited, and explicitly authorized before implementation. Runtime, HIL, hardware, `deploy_sim`, and `deploy_real` authority remain separate and are not granted here.

## 6. Future code-candidate deliverables and authorization gate

A later code candidate, if separately authorized, must provide:

1. Only these exact code/test paths, unless a new user decision changes scope:
   - `ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/core/v3_observation_contracts.py`
   - `ros2_ws/src/mecanum_nav_rl/test/test_v3_observation_contract_primitives.py`
2. Focused unit-test source and complete test output, recording Python/interpreter and command.
3. Static field/member-set and import-purity evidence, plus `git diff --check` and `git diff --cached --check`.
4. Exact source/test hashes and reviewable diff for focused independent code audit.
5. A separate explicit Project Owner/User `CODE_AUTHORIZATION` decision for that exact audited code candidate and exact scope.

This packet authorizes none of these implementation or test actions. It does not authorize or define Gate B. Connected/profile-resolving implementation requires its own applicable ACR gates, profile evidence, exact packet, audit, and approval. Runtime authorization remains a separate decision.

```text
WP-04: BLOCKED_BY_CONTRACT
GATE_A: NOT_PASSED
CODE_AUTHORIZATION: NOT_GRANTED
RUNTIME_APPROVED: NOT_APPROVED
```
