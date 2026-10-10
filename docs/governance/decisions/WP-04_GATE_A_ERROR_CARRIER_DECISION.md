# WP-04 Gate A — Error-Carrier Decision Record

**Record date:** 2026-10-10
**Status:** CANDIDATE_FOR_FOCUSED_AUDIT_AND_SEPARATE_CANONICAL_INTEGRATION
**Integration base:** origin/integration/implementation@401593a4268af572ef4690177539360b1c15410a
**Review branch:** wp-04-gate-a-error-carrier-decision-record-401593a

## 1. Decision provenance

This record captures the Project Owner/User decisions supplied for work package WP-04-GATE-A-ERROR-CARRIER-DECISION-RECORD. The source decision packet is:

- Branch: wp-04-gate-a-error-carrier-user-decision-f9987be
- Commit: 52d392f3336a1bc614f60c40bdea2ba0276a8ef5
- Path: docs/WP-04_GATE_A_ERROR_CARRIER_DECISION_PACKET_DRAFT.md
- SHA-256: 08a73e1c3a5e7dbd435ac00c1ffb8200d673eaeaa0974f45d9501ba07de30ae2

The source packet content and SHA-256 were verified at the stated commit. The User reports that its focused re-audit concluded PASS with no correction required. The audit report identity/hash was not supplied with this decision and is not asserted or invented here.

The canonical structural schema cited by the packet is docs/OBSERVATION_GATE_A_STRUCTURAL_SCHEMA.md at SHA-256 43537b8f0edafbe809e6f70bda86808f87b12f146ed45509c4bfbacd26956ad3. The implementation-authorization packet remains provenance on its separate review branch; it is not included in this candidate.

## 2. Accepted error-carrier decisions

The Project Owner/User selected **Option B: a typed, read-only detail carrier**:

- GateASchemaValidationError exposes the documented detail member.
- A mapped failure uses GateASchemaMappedFailure and carries its applicable existing ACR8 status.
- A construction failure uses GateASchemaConstructionFailure and has no ACR8 status member.
- Callers distinguish mapped from construction failures by the detail type and rely on its documented public fields.

The Project Owner/User accepted the diagnostic labels proposed in the source packet, strictly for diagnostic classification. They are not ACR8 status values and do not create new statuses:

| Failure | Accepted diagnostic label | Status treatment |
|---|---|---|
| Cutoff does not pass one or both barriers | CUTOFF_BARRIER_ORDER | Existing CUTOFF_BARRIER_ORDER_NON_READY |
| Exact contract ID/SHA pair mismatch | CONTRACT_REFERENCE_MISMATCH | Existing LIFECYCLE_OR_CONTRACT_MISMATCH_NON_READY |
| Missing constructor field | MISSING_FIELD | No ACR8 status |
| Unknown constructor field | UNKNOWN_FIELD | No ACR8 status |
| Wrong exact type | WRONG_TYPE | No ACR8 status |
| bool supplied for integer | BOOL_AS_INT | No ACR8 status |
| Negative integer | NEGATIVE_VALUE | No ACR8 status |
| Empty string | EMPTY_STRING | No ACR8 status |

The accepted field_name rule is the one stated by the source packet: field_name is exact built-in str or None; it carries the schema field name when that field can be determined, and None otherwise. This record does not add a per-failure attribution table or a new precedence rule beyond that source wording.

The Project Owner/User accepted that the error carrier does **not** retain raw input values. Construction failures remain typed, fail-closed failures without an ACR8 status.

## 3. Status mappings retained

The two mapped failures remain exactly:

| Failure | Retained status |
|---|---|
| cutoff_time_ns is not strictly after either action_barrier_time_ns or reset_barrier_time_ns | CUTOFF_BARRIER_ORDER_NON_READY |
| Either supplied contract ID/SHA pair does not exactly match its selected pair | LIFECYCLE_OR_CONTRACT_MISMATCH_NON_READY |

No status name, value, meaning, or fail-closed behavior is changed. No new ACR8 status is created.

## 4. Public-field reassignment and Python exception surface

The accepted immutability boundary is limited to the documented public fields: ordinary attribute assignment must not allow those fields to be reassigned after the exception/detail has been created. This is not a claim of absolute or deep immutability of all Python object state, and does not promise protection against reflective or low-level mutation.

Within this error-carrier contract, Exception.args, str(exc), repr(exc), exception notes, and direct caller construction of GateASchemaValidationError are outside the public carrier contract. Callers rely on the documented detail fields and the two mappings above, not on those Python behaviors.

## 5. Candidate and authority boundary

This decision record is a documentation candidate for focused independent audit. It has no canonical or operative effect until that audit, a separate explicit user authorization to integrate the exact reviewed candidate, and canonical integration through the authorized workflow are complete.

Recording these decisions does not make the structural schema active, pass Gate A, close WP-04, change any status or dependency, or authorize implementation. It grants no CODE_AUTHORIZATION, ROS, runtime, HIL, hardware, deploy_sim, or deploy_real authority.

~~~text
WP-04: BLOCKED_BY_CONTRACT
GATE_A: NOT_PASSED
CODE_AUTHORIZATION: NOT_GRANTED
RUNTIME_APPROVED: NOT_APPROVED
~~~
