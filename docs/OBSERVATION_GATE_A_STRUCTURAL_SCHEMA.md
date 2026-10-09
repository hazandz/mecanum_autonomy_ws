# Gate A V3 Structural Schema — candidate

**Status:** `CANDIDATE_ONLY_PENDING_FOCUSED_INDEPENDENT_AUDIT_AND_SEPARATE_USER_INTEGRATION_AUTHORIZATION`
**Work package:** `WP-04-POLICY-CORE-P0`
**Decision source:** Project Owner/User decision recorded for `WP-04-GATE-A-EXACT-SCHEMA-RECONCILIATION`
**Integration base:** `origin/integration/implementation@988a74b529fdb4bcf77f341db5c6d115e8511a9b`
**Source decision packet:** `wp-04-gate-a-exact-schema-decision-packet-c37a5bff@fc7833d0a491190c88f93d8fdd59da2feb263169`; packet SHA-256 `e69f0a06b6189a6558d7ee46f6c2c0f645abd6df62c618c39761b2733731042c`

This document records the exact structural schema selected by the Project Owner/User for focused audit. It is a documentation candidate, not an active canonical contract. It becomes active only after focused independent audit, separate explicit user authorization to integrate the exact candidate commit, and fast-forward of that exact commit to `integration/implementation` with the remote ref verified. It does not grant code or runtime authorization, establish Gate A as passed, or close WP-04.

## 1. Authority and provenance boundary

- PEP-001 rev.0.5.0 controls WP sequencing and the constrained Gate A scope. It keeps WP-04 `BLOCKED_BY_CONTRACT` and retains the `WP-04 → WP-03` dependency; WP-03 is `CLOSED` at the stated integration base.
- QoS revision 6 and ACR revision 8 are used according to their current approved status in the Canonical Source Registry and bundled approval record. Their exact full-document SHA-256 values are respectively `4200cd2fbdc81a19400f168dd3526eb7871ac2251049fc7c4f5d5c2fddfd2022` and `03fef021f6b9731f811f83a5e53aae1c430bdc2ea76815a8ada416f1a5bf772c`.
- The canonical receipt interface is `docs/RECEIPT_INTERFACE_DEPENDENCY_CLOSURE_MANIFEST.json`-selected `FinalIssuedCommandReceipt.msg`, path `ros2_ws/src/mecanum_nav_rl_interfaces/msg/FinalIssuedCommandReceipt.msg`, SHA-256 `0c6446674bf17373ec646519043f506a9a7a15f95d5fdd10829b0cedb956500a`; its contract ID is `mecanum.final-issued-receipt/v2`.
- PEP-001 pins S2 revision 2 as immutable `DRAFT` provenance: source `origin/docs-v3-observation-contract-import@d3ca85536e35b38f7f3dffcf1dfd1bc16983aae9`, path `docs/architecture/proposals/v3-observation-contracts/ACR_S2_SNAPSHOT_SYNCHRONIZATION_TEMPORAL_CONTRACT.md`, full-document SHA-256 `e1468d0373922a1806e14da91e7cc0336bcc7d70c4cd3ec4fc749078d86b70ab`; its contract ID/manifest pin is `mecanum.snapshot-synchronization-temporal/v1` / `1be31c1915fedd86f269cee5214d794da0899a0d69dbb0ba5392e619813d4a8f`. This reference is provenance-only and does not implement synchronization behavior.
- Observation Input Contract V3 revision 6 is immutable `REVISED_DRAFT` provenance only: the same source branch/commit, path `docs/architecture/proposals/v3-observation-contracts/OBSERVATION_INPUT_CONTRACT_V3_DESIGN.md`, full-document SHA-256 `200703949d6b326a30ee8e2f75cd2cd14054576e6772ddc6ae3ff670e48eb76c`. It is not independently approved or canonical and does not add fields to the selected reference-only Gate A model.
- V3 Observation Boundary Specification revision 7 remains supporting design provenance, not promoted or treated here as replacing active authority: the same source branch/commit, path `docs/architecture/proposals/v3-observation-contracts/V3_OBSERVATION_BOUNDARY_SPECIFICATION.md`, full-document SHA-256 `47ba6c432cc53798e9f8a97f3c0a97aae586d24bef98113716a4493e57ad4eeb`.

The exact schema below is the user-selected structural design for the candidate. The S2 pair records provenance; the receipt pair pins the canonical receipt interface. The model contains no QoS transport, ACR, approval-record, or Registry hashes.

## 2. `ObservationCutoffV3`

The selected schema is flat, keyword-only, and has exactly these fields:

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

### Field and validation rules

| Field | Exact accepted type | Required validation |
|---|---|---|
| `lifecycle_identity` | exact built-in `str` | Non-empty; opaque; exact comparison; no normalization |
| `epoch` | exact built-in `int` | Non-negative; reject `bool`, subclasses, and numeric coercion; no upper bound |
| `generation` | exact built-in `int` | Non-negative; reject `bool`, subclasses, and numeric coercion; no upper bound |
| `time_domain` | exact built-in `str` | Non-empty; opaque; exact comparison; no normalization |
| `cutoff_time_ns` | exact built-in `int` | Non-negative nanoseconds in the profile ROS-time domain; reject `bool`, subclasses, and numeric coercion; no upper bound |
| `action_barrier_time_ns` | exact built-in `int` | Non-negative nanoseconds in the same profile ROS-time domain; reject `bool`, subclasses, and numeric coercion; no upper bound |
| `reset_barrier_time_ns` | exact built-in `int` | Non-negative nanoseconds in the same profile ROS-time domain; reject `bool`, subclasses, and numeric coercion; no upper bound |

The constructor must require `cutoff_time_ns > action_barrier_time_ns` and `cutoff_time_ns > reset_barrier_time_ns`. No ordering is imposed between the two barrier timestamps. This value is a structural container for caller-supplied facts; it does not create, advance, compare across, or convert clocks or lifecycle events.

The schema has no `transaction_id`, `creation_owner`, `schema_id`, or `config_hash` field. It does not compute, normalize, validate, or bind a configuration hash.

## 3. `ContractReferenceV3` and `ObservationInputContractV3`

The selected input contract is a minimum, reference-only container:

```python
ContractReferenceV3(
    *,
    contract_id: str,
    contract_sha256: str,
)

ObservationInputContractV3(
    *,
    s2_provenance_reference: ContractReferenceV3,
    receipt_interface_reference: ContractReferenceV3,
)
```

`contract_id` and `contract_sha256` must each be exact built-in `str` values and non-empty. Comparison is exact; there is no alias, fallback, lookup, normalization, or additional generic syntax validation. The only reference validation is exact contract-ID/SHA-pair matching against the two selected pairs:

| Member | Exact pair | Authority meaning |
|---|---|---|
| `s2_provenance_reference` | `mecanum.snapshot-synchronization-temporal/v1` / `1be31c1915fedd86f269cee5214d794da0899a0d69dbb0ba5392e619813d4a8f` | Immutable S2 revision 2 provenance pin only; not canonical authority or synchronization implementation |
| `receipt_interface_reference` | `mecanum.final-issued-receipt/v2` / `0c6446674bf17373ec646519043f506a9a7a15f95d5fdd10829b0cedb956500a` | Canonical receipt-interface schema ID/SHA pin selected at the baseline |

No QoS transport, ACR, approval-record, or Registry hash is a model member. The reference model does not resolve a path, load a document, or verify a hash by reading repository files; it checks only the exact ID/SHA pairs supplied to it.

## 4. Value and API semantics

All three value types use the selected representation:

```python
@dataclass(frozen=True, slots=True, kw_only=True)
```

The intended implementation rejects subclasses and unknown fields, uses field-wise value equality and generated field-wise hash, and retains the default representation (`repr`). IDs and hashes are not secret values. Gate A defines no serialization or export API. No coercion, implicit defaults, aliases, fallback references, or additional schema members are permitted.

Missing fields, unknown fields, wrong exact types, `bool` supplied where an `int` is required, negative integer values, and empty strings fail at construction through the typed `GateASchemaValidationError` policy below. This is a schema decision; implementation mechanics remain subject to the exact implementation packet and its separate authorization.

## 5. Fail-closed error boundary

Structural failures use typed `GateASchemaValidationError` behavior and fail closed. No new canonical status is created.

| Failure | Selected outcome |
|---|---|
| `cutoff_time_ns` is not strictly after either barrier | Map to existing `CUTOFF_BARRIER_ORDER_NON_READY` |
| Either supplied contract ID/SHA pair does not exactly match its selected pair | Map to existing `LIFECYCLE_OR_CONTRACT_MISMATCH_NON_READY` |
| Missing/unknown constructor field, wrong type, `bool`-as-`int`, negative integer, or empty string | Construction-time typed exception; do not assign a new ACR8 status |

No generic contract-ID/SHA syntax validator is added; reference validation is exact pair matching only. Constructor/schema-shape syntax failures use the typed construction-time exception boundary above. The selected Gate A schema does not implement future/stale input handling, synchronization, buffering, clock conversion, receipt processing, or generation invalidation. The status mapping does not authorize any connected behavior named by other ACR8 statuses.

## 6. Scope, activation, and authorization

This schema is limited to immutable structural primitives. It excludes configuration, compiler/profile work, ROS/ROSIDL, adapters, runtime, freshness/synchronization, receipt bridge/history, S2 synchronizer/buffer, assembler/encoder, 81D construction, V1, Ground Truth, HIL, hardware, `deploy_sim`, and `deploy_real`.

This file is candidate documentation only. Activation requires all of the following: focused independent audit of the exact candidate; a separate explicit Project Owner/User authorization to integrate that exact candidate; and fast-forward of that exact commit to `integration/implementation` followed by remote-ref verification. Until then this candidate does not alter canonical source selection or WP status/dependencies.

```text
WP-03: CLOSED
WP-04: BLOCKED_BY_CONTRACT
GATE_A: NOT_PASSED
CODE_AUTHORIZATION: NOT_GRANTED
RUNTIME_APPROVED: NOT_APPROVED
```
