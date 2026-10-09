# WP-04 Gate A — implementation-authorization packet (draft)

**Packet status:** `DRAFT_FOR_FOCUSED_INDEPENDENT_AUDIT_AND_LATER_USER_CODE_AUTHORIZATION_DECISION`
**Work package:** `WP-04-POLICY-CORE-P0`
**Candidate branch:** `wp-04-gate-a-implementation-authorization-packet-f9987be`
**Base:** `origin/integration/implementation@f9987be4429349ef9110c45cf97a89728a5e4229`
**Canonical Gate A schema:** `docs/OBSERVATION_GATE_A_STRUCTURAL_SCHEMA.md`; SHA-256 `43537b8f0edafbe809e6f70bda86808f87b12f146ed45509c4bfbacd26956ad3`

This packet proposes a narrow pure-Python implementation scope and the evidence expected for a future Project Owner/User decision. It does not authorize implementation, create a code candidate, establish Gate A as passed, or change any work-package status or dependency. A later, separate explicit `CODE_AUTHORIZATION` is required for an exact code/test candidate after focused audit.

## 1. Authority and exact inputs

| Source | Status and exact identity | Use in this packet |
|---|---|---|
| `docs/governance/PROJECT_EXECUTION_PLAN.md` | PEP-001 rev.0.5.0 at the base | Controls WP sequencing and permits preparation/audit of the constrained primitive-only Gate A packet; WP-04 remains `BLOCKED_BY_CONTRACT` and depends on WP-03, which is `CLOSED` at this base. |
| `docs/OBSERVATION_GATE_A_STRUCTURAL_SCHEMA.md` | Canonical at the base; SHA-256 `43537b8f0edafbe809e6f70bda86808f87b12f146ed45509c4bfbacd26956ad3` | Governs exact structural fields, types, value semantics, reference pairs, validation and fail-closed mapping proposed below. |
| `docs/ACR_V3_OBSERVATION_BOUNDARY_CLOSURE.md` | ACR rev.8; full SHA-256 `03fef021f6b9731f811f83a5e53aae1c430bdc2ea76815a8ada416f1a5bf772c` | Approved Gate A boundary and exclusions, as selected by Registry and bundled approval. |
| `docs/RECEIPT_TOPIC_QOS_CONTRACT.md` | QoS rev.6; full SHA-256 `4200cd2fbdc81a19400f168dd3526eb7871ac2251049fc7c4f5d5c2fddfd2022` | Approved bundle context only. The transport contract is not a model member or implemented behavior in this packet. |
| `docs/governance/decisions/QOS_REVISION_6_ACR_REVISION_8_BUNDLE_APPROVAL.md` and `docs/governance/CANONICAL_SOURCE_REGISTRY.md` | Bundle approval dated 2026-10-08; Registry selects the canonical receipt interface | Select/pin the receipt message schema path, ID, and SHA stated below. |
| S2 rev.2, OIC rev.6, V3 Observation Boundary Specification rev.7 | PEP-001 provenance pins only; S2 is `DRAFT`, OIC is `REVISED_DRAFT`; V3 Spec is supporting provenance | Context only. These do not supply defaults or independently authorize fields or behavior. |

The receipt schema pin is `ros2_ws/src/mecanum_nav_rl_interfaces/msg/FinalIssuedCommandReceipt.msg`, contract ID `mecanum.final-issued-receipt/v2`, schema SHA-256 `0c6446674bf17373ec646519043f506a9a7a15f95d5fdd10829b0cedb956500a`. The dependency-closure manifest records transitive ROS message-definition provenance; it does not select the receipt schema.

## 2. Baseline inventory and proposed future paths

The following paths were checked directly at the exact base. “Existing” means the path exists at the baseline; it does not imply that it is approved for modification by this packet.

| Path | Baseline state | Proposed Gate A disposition |
|---|---|---|
| `ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/core/types.py` | Existing pure-domain `Pose2D` and `VelocityCommand` value objects | Reference only; no change proposed. |
| `ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/core/exceptions.py` | Existing project exception hierarchy; no `GateASchemaValidationError` | Reference only; do not modify. The Gate A error type is proposed in the new primitive module below, avoiding an unrelated exception-hierarchy change. |
| `ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/core/snapshots.py` | Existing `SensorSnapshot`, including synchronized sensor data and array handling | Existing but outside Gate A; do not modify or reuse as the cutoff/input-contract model. |
| `ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/core/__init__.py` | Existing core exports | Do not modify or add an export/serialization surface in Gate A. |
| `ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/observations/synchronizer.py`, `assembly.py`, `encoder.py` | Existing connected observation components | Prohibited from modification or use to add Gate A behavior. |
| `ros2_ws/src/mecanum_nav_rl/test/test_observation_assembly.py`, `test/test_snapshot_synchronizer.py` | Existing integration-oriented observation tests | Reference only; do not extend them for this primitive packet. |
| `ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/core/v3_observation_contracts.py` | Absent at the baseline | Proposed-to-create in a later, separately authorized code candidate; contains only the three immutable structural value types and `GateASchemaValidationError`. |
| `ros2_ws/src/mecanum_nav_rl/test/test_v3_observation_contract_primitives.py` | Absent at the baseline | Proposed-to-create in that later code candidate; focused pure-Python tests only. |

The two proposed-to-create paths are a future exact code/test allowlist proposal, not permission to create them now. No package metadata, `__init__.py`, configuration, interface, or runtime path is included.

## 3. Narrow implementation scope proposed for later authorization

Only these definitions and structural checks are proposed:

- `ObservationCutoffV3`;
- `ContractReferenceV3`;
- `ObservationInputContractV3`;
- typed `GateASchemaValidationError`;
- construction-time structural validation and the two status mappings already specified by the canonical schema.

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

`ContractReferenceV3(*, contract_id: str, contract_sha256: str)` contains only those two fields. `ObservationInputContractV3(*, s2_provenance_reference: ContractReferenceV3, receipt_interface_reference: ContractReferenceV3)` contains only those two references.

- Each string must be exact built-in `str`, non-empty, compared exactly, and not normalized.
- Validate only the selected exact ID/SHA pairs; do not add aliasing, fallback, lookup, normalization, or generic syntax validation.
- S2 pair: `mecanum.snapshot-synchronization-temporal/v1` / `1be31c1915fedd86f269cee5214d794da0899a0d69dbb0ba5392e619813d4a8f`. Its role remains provenance-only.
- Receipt pair: `mecanum.final-issued-receipt/v2` / `0c6446674bf17373ec646519043f506a9a7a15f95d5fdd10829b0cedb956500a`.
- Do not add QoS transport, ACR, approval-record, or Registry hashes to the model.

### 3.3 Value and error semantics

All three value types use `@dataclass(frozen=True, slots=True, kw_only=True)`, reject subclasses and unknown fields, use field-wise value equality and generated field-wise hash, and retain default `repr`. No defaults, coercion, alias/fallback, or serialization/export API are allowed.

Structural validation is fail-closed and uses `GateASchemaValidationError`:

| Condition | Required semantic outcome |
|---|---|
| Cutoff is not strictly later than either barrier | Existing `CUTOFF_BARRIER_ORDER_NON_READY` mapping |
| Supplied contract ID/SHA pair differs from its exact selected pair | Existing `LIFECYCLE_OR_CONTRACT_MISMATCH_NON_READY` mapping |
| Missing/unknown fields, wrong exact type, bool-as-int, negative integer, or empty string | Construction-time typed exception; do not create or assign a new ACR8 status |

The schema does not specify the public carrier shape (for example, exception attributes) for exposing a mapped status. That API detail is `PENDING_USER_DECISION` for the exact code authorization; implementation must not invent a new status or alter the selected mappings. No generic ID/SHA syntax validator is proposed. No future/stale/synchronization/buffer/generation-invalidation behavior is in scope.

## 4. Acceptance criteria and checks to run only after separate authorization

These are expected checks for a later code candidate. They were **not run** for this documentation packet.

### Positive construction and value semantics

- Construct a valid cutoff using all seven required keyword arguments and exact built-in values; cover valid barrier pairs in both relative orderings while cutoff remains greater than both.
- Construct valid `ContractReferenceV3` and `ObservationInputContractV3` values using the exact S2 provenance pair and canonical receipt v2 pair.
- Verify keyword-only constructor behavior, exact dataclass fields/member sets, frozen assignment failure, slots/no instance `__dict__`, field-wise equality/hash behavior, and default `repr` without a custom serializer.
- Verify no implicit defaults and no extra cutoff or input-contract members.

### Fail-closed validation matrix

- For every required field, test missing and unknown constructor arguments.
- Test wrong exact types, `bool` for every integer field, integer subclasses, `str` subclasses, numeric objects/coercion candidates, negative epoch/generation/timestamps, and empty identity/domain/reference strings.
- Test each cutoff/barrier boundary independently: equality and earlier cutoff against the action barrier; equality and earlier cutoff against the reset barrier. Verify the selected order mapping; do not require one barrier to precede the other.
- Mutate the reference ID and SHA independently for each reference and test cross-paired values; verify exact-pair mismatch mapping and no alias/fallback/normalization.
- Verify construction failures raise the selected typed exception and do not introduce a new canonical status. Once the error-status carrier API is separately decided, assert its exact status representation without adding statuses.

### Static/import-purity/no-regression

- Statically verify the exact seven cutoff fields, the two input members, the two reference fields, keyword-only/no-default signatures, and the two exact accepted ID/SHA pairs.
- Statically inspect the new primitive module’s imports to verify it has no dependency on `rclpy`, ROS/ROSIDL-generated messages, Gazebo, configuration/compiler/profile modules, or runtime adapters.
- Import the new module in a pure Python test context and verify importing it does not import ROS packages or perform I/O, clock reads, repository lookups, or message construction.
- Verify existing observation assembly/synchronization, config, interface and package files remain unchanged in the later candidate diff.

No Gate A ROS/ROSIDL integration or connected integration test is proposed. The implementation work package may run only the specifically authorized static/unit checks; this packet authorizes none of them.

## 5. Explicit exclusions and blockers

Out of scope: `rclpy`, ROS/ROSIDL, QoS/TF/DDS, clock conversion, freshness, synchronization, buffers, receipt bridge/history, assembler/encoder, 81D construction, LiDAR, LocalReference, measured twist, PPO/training, runtime, HIL, hardware, `deploy_sim`, and `deploy_real`. Also excluded: `ResolvedConfigV3`, configuration/compiler/profile, YAML, V1 observation, Ground Truth, S2/OIC/V3-draft-derived defaults, and all WP-05 artifacts or findings.

Open decision before a fully exact code authorization: how `GateASchemaValidationError` exposes the two already-selected ACR8 mappings to callers. Its type name, fail-closed behavior, and mapping semantics are selected; a public attribute/result shape is not. Do not infer it from existing exceptions or draft provenance.

## 6. Future deliverables and authorization gate

A later code candidate, if separately authorized, must provide:

1. Only the exact code/test allowlist proposed in §2, unless a new user decision explicitly changes it.
2. The focused unit-test source and complete test output, with the Python/interpreter and command recorded.
3. Static import-purity and field/member-set evidence, plus `git diff --check` and `git diff --cached --check`.
4. Exact source/test hashes and a reviewable diff for focused independent code audit.
5. A separate explicit Project Owner/User decision granting `CODE_AUTHORIZATION` to that exact audited code candidate and exact scope. Packet audit/pass, commit, or this user-selected schema does not grant that authorization.

This Gate A packet does not authorize or define Gate B. Any connected/profile-resolving implementation requires its own applicable ACR gates, profile evidence, exact packet, audit, and approval. Runtime authorization remains a separate decision and is not requested here.

```text
WP-04: BLOCKED_BY_CONTRACT
GATE_A: NOT_PASSED
CODE_AUTHORIZATION: NOT_GRANTED
RUNTIME_APPROVED: NOT_APPROVED
```
