# WP-04 Gate A Exact Schema Decision — candidate record

**Record status:** `CANDIDATE_ONLY_PENDING_FOCUSED_INDEPENDENT_AUDIT_AND_SEPARATE_USER_INTEGRATION_AUTHORIZATION`
**Work package:** `WP-04-GATE-A-EXACT-SCHEMA-RECONCILIATION`
**Integration base:** `origin/integration/implementation@988a74b529fdb4bcf77f341db5c6d115e8511a9b`
**Candidate branch:** `wp-04-gate-a-exact-schema-reconciliation-988a74b`
**Source decision packet:** `wp-04-gate-a-exact-schema-decision-packet-c37a5bff@fc7833d0a491190c88f93d8fdd59da2feb263169`; SHA-256 `e69f0a06b6189a6558d7ee46f6c2c0f645abd6df62c618c39761b2733731042c`
**Decision authority:** Explicit Project Owner/User decision in this conversation; decision date `2026-10-09`.

## 1. Decision recorded

The Project Owner/User selected the exact Gate A structural schema captured in `docs/OBSERVATION_GATE_A_STRUCTURAL_SCHEMA.md`:

1. `ObservationCutoffV3` is flat and keyword-only, with exactly `lifecycle_identity: str`, `epoch: int`, `generation: int`, `time_domain: str`, `cutoff_time_ns: int`, `action_barrier_time_ns: int`, and `reset_barrier_time_ns: int`.
2. Identity/domain strings are exact built-in `str`, non-empty, opaque, compared exactly, and not normalized. Epoch, generation and timestamps are exact built-in `int`, reject `bool`, subclasses and numeric coercion, are non-negative, and have no upper bound. Timestamps are nanoseconds in the profile ROS-time domain. The cutoff is strictly greater than each barrier; there is no ordering requirement between barriers. No transaction ID, creation owner, schema ID, or config hash is included.
3. `ObservationInputContractV3` is a reference-only keyword-only container with exactly `s2_provenance_reference` and `receipt_interface_reference`, each a `ContractReferenceV3` containing `contract_id` and `contract_sha256`. Strings are exact built-in `str`, non-empty, and compared exactly. Validation checks only exact selected ID/SHA pairs; there is no alias, fallback, lookup, normalization, or additional generic syntax validation.
4. S2 is explicitly provenance-only. The receipt reference pins canonical `mecanum.final-issued-receipt/v2` and schema SHA-256 `0c6446674bf17373ec646519043f506a9a7a15f95d5fdd10829b0cedb956500a`. QoS transport, ACR, approval-record, and Registry hashes are not model members.
5. The representation is `@dataclass(frozen=True, slots=True, kw_only=True)`, rejects subclasses and unknown fields, uses field-wise value equality and generated field-wise hash, default `repr`, and defines no Gate A serialization/export API.
6. Typed `GateASchemaValidationError` is fail-closed. Cutoff/barrier order violations map to `CUTOFF_BARRIER_ORDER_NON_READY`; exact contract ID/SHA mismatch maps to `LIFECYCLE_OR_CONTRACT_MISMATCH_NON_READY`. Missing/unknown/wrong-type/bool-as-int/range/syntax construction failures do not create or map to a new ACR8 status. No future/stale/synchronization/buffer/generation-invalidation behavior is selected for implementation in this scope.

## 2. Authority and provenance

PEP-001 rev.0.5.0 remains the sequencing authority and keeps WP-04 `BLOCKED_BY_CONTRACT`, with dependency `WP-04 → WP-03`; WP-03 is `CLOSED` at the integration base. QoS revision 6 and ACR revision 8 remain the approved contract authorities for their recorded scope, as selected by the Canonical Source Registry and bundle approval. S2 revision 2 and Observation Input Contract revision 6 remain draft/provenance-only pins as explicitly stated by PEP-001; this user schema decision does not promote either source. V3 Observation Boundary Specification revision 7 remains supporting provenance, not replacement authority.

The decision packet at `fc7833d0a491190c88f93d8fdd59da2feb263169` is the provenance for the choices presented to the user. This record preserves the user’s exact selection; it does not independently establish technical authority or change a canonical contract.

## 3. Candidate-only effect and activation condition

This record and the associated schema document are documentation candidates only. They are not canonical or operative before focused independent audit, separate explicit user authorization to integrate the exact audited candidate commit, and fast-forward of that exact commit to `integration/implementation` with remote-ref verification. A later integration decision must identify the exact audited commit; no candidate commit SHA is self-embedded here.

The recorded schema decision is not `CODE_AUTHORIZATION`. It does not establish Gate A as passed, make WP-04 implementation-eligible, close WP-04, change WP-03/WP-04 status or dependencies, or authorize code, ROS, runtime, HIL, hardware, `deploy_sim`, or `deploy_real`.

```text
WP-03: CLOSED
WP-04: BLOCKED_BY_CONTRACT
GATE_A: NOT_PASSED
CODE_AUTHORIZATION: NOT_GRANTED
RUNTIME_APPROVED: NOT_APPROVED
```
