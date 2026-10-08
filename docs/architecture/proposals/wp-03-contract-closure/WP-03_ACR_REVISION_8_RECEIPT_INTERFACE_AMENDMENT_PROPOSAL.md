# WP-03 — ACR Revision 8 Receipt Interface Amendment Proposal

**Status:** `DRAFT_FOR_INDEPENDENT_AUDIT_AND_USER_DECISION`
**Baseline:** `integration/implementation@9a4c0d233e8237f01a04880fe99e8a3114528f4`
**Amends:** ACR V3 Observation Boundary Closure revision 7, receipt interface pin
**Proposed schema artifact:** `docs/architecture/proposals/wp-03-contract-closure/WP-03_RECEIPT_INTERFACE_V2_DRAFT.msg`
**Proposed interface revision:** `2`
**Proposed interface ID:** `mecanum.final-issued-receipt/v2`
**Proposed schema SHA-256:** `0c6446674bf17373ec646519043f506a9a7a15f95d5fdd10829b0cedb956500a`

This is a companion amendment proposal to be reviewed and decided together with the proposed QoS Contract revision 6. It has no authority until the bundle is independently audited, explicitly approved by the user, and canonically integrated. ACR revision 7 remains canonical authority until then.

## Proposed §5.2 receipt interface pin disposition

If approved, update the receipt-interface reference to the exact candidate artifact path above, revision `2`, ID `mecanum.final-issued-receipt/v2`, and full schema SHA-256 stated here. The corresponding QoS reference must carry exactly the same path, revision, ID, and hash.

The prior `mecanum.final-issued-receipt/v1` / SHA-256 `90348664c4563997b93de7f10e278b10d4053fcb96909b6bb85c1319db76c40e` pin remains historical provenance. This proposal does not claim that v2 is the v1 artifact, that it matches the v1 hash, or that a missing v1 schema has been recovered. Only the explicit approved bundle may disposition that old pin.

The schema-content SHA is independent of the QoS transport-manifest SHA. Preserve transport ID `mecanum.final-issued-receipt-topic-qos/v1` and manifest SHA-256 `a3bc1a965fc6885825ab961289fa4028862aa7af4b3f3156bc40542f7ee08f62`; no transport semantics or manifest content are amended here.

## Preserved authority boundaries

This amendment proposal records only the schema identity/path/revision/hash disposition. It does not change Architecture semantics, QoS delivery behavior, the WP-03/WP-04 dependency or status, or the D2 receipt boundary and ownership decisions. It does not claim interface implementation or runtime evidence and grants no code, ROS, HIL, hardware, `deploy_real`, or runtime authorization.

```text
WP-02: CLOSED
WP-03: BLOCKED_BY_CONTRACT
WP-04: BLOCKED_BY_CONTRACT
CODE_AUTHORIZATION: NOT_GRANTED
RUNTIME_APPROVED: NOT_APPROVED
```
