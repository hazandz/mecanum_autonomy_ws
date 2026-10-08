# WP-03 — QoS Contract Revision 6 Receipt Interface Amendment Proposal

**Status:** `DRAFT_FOR_INDEPENDENT_AUDIT_AND_USER_DECISION`
**Baseline:** `integration/implementation@9a4c0d233e8237f01a04880fe99e8a3114528f4`
**Amends:** Receipt Topic QoS Contract revision 5, §4 and exact interface pin references
**Proposed schema artifact:** `docs/architecture/proposals/wp-03-contract-closure/WP-03_RECEIPT_INTERFACE_V2_DRAFT.msg`
**Proposed interface revision:** `2`
**Proposed interface ID:** `mecanum.final-issued-receipt/v2`
**Proposed schema SHA-256:** `0c6446674bf17373ec646519043f506a9a7a15f95d5fdd10829b0cedb956500a`

This is a companion amendment proposal only. Until the amendment and its ACR companion are independently audited, explicitly approved as a bundle, and canonically integrated, QoS revision 5 remains canonical authority.

## Proposed §4 pin disposition

If approved, update the interface pin in QoS revision 5 to identify the candidate schema artifact above by its exact path, revision `2`, interface ID `mecanum.final-issued-receipt/v2`, and full schema SHA-256 stated here. Do not assign the v1 ID or its pinned SHA-256 to the v2 bytes. Record the old v1 pin as superseded only by this explicit approved amendment; do not erase its historical value.

The v2 field names, widths, and identity constraints are defined by the companion `WP-03_RECEIPT_INTERFACE_V2_CONTRACT_PROPOSAL.md` and the exact `.msg` bytes. This proposal does not amend QoS transport semantics.

## Preserved transport identity and semantics

Keep unchanged:

```text
Transport contract ID: mecanum.final-issued-receipt-topic-qos/v1
Transport manifest SHA-256: a3bc1a965fc6885825ab961289fa4028862aa7af4b3f3156bc40542f7ee08f62
```

The manifest hash identifies the transport JSON, not the interface schema. Preserve QoS revision 5's `RELIABLE`, `TRANSIENT_LOCAL`, `KEEP_LAST(1)`, coalescing/order classification, action/reset barrier eligibility, disabled/infinite deadline and lifespan, and automatic infinite-lease liveliness semantics. Do not change topic, manifest bytes, delivery policy, or transport behavior in this amendment.

The interface schema SHA is a separate pin over the `.msg` proposal file bytes. No hash is embedded in that file.

## Authority and effect

This proposed revision 6 does not take effect by being drafted or pushed. QoS revision 5 remains canonical until the QoS revision 6 / ACR revision 8 bundle completes independent audit, user approval, and canonical integration. No implementation, WP status transition, code authorization, or runtime authorization follows from this proposal.
