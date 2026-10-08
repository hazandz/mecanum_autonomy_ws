# QoS Revision 6 Receipt Interface Amendment Proposal

**Status:** `DRAFT_FOR_INDEPENDENT_AUDIT_AND_USER_DECISION`
**Current authority at baseline:** QoS revision 5 / ACR revision 7
**Full-text draft:** `docs/architecture/proposals/wp-03-contract-closure/WP-03_RECEIPT_TOPIC_QOS_CONTRACT_REVISION_6_DRAFT.md`
**QoS revision:** `6`
**Full-document SHA-256:** `4200cd2fbdc81a19400f168dd3526eb7871ac2251049fc7c4f5d5c2fddfd2022`

This amendment proposal is not independently authoritative. It must be audited and decided together with the ACR revision 8 full-text draft. QoS revision 5 remains canonical until an approved bundle is integrated.

## Proposed exact interface and dependency pins

| Pin | Proposed value |
|---|---|
| Receipt interface ID | `mecanum.final-issued-receipt/v2` |
| Schema path | `docs/architecture/proposals/wp-03-contract-closure/WP-03_RECEIPT_INTERFACE_V2_DRAFT.msg` |
| Schema revision | `2` |
| Schema SHA-256 | `0c6446674bf17373ec646519043f506a9a7a15f95d5fdd10829b0cedb956500a` |
| Dependency-closure manifest | `docs/architecture/proposals/wp-03-contract-closure/WP-03_RECEIPT_INTERFACE_DEPENDENCY_CLOSURE_MANIFEST_V1.json` |
| Closure-manifest SHA-256 | `0872fa8c10179f69c2e9e9546392ac734a4f4e94ade176a8be431f06905ecf73` |
| Transport ID | `mecanum.final-issued-receipt-topic-qos/v2` |
| Transport manifest version/path | `2` / `docs/architecture/proposals/wp-03-contract-closure/WP-03_RECEIPT_TOPIC_QOS_TRANSPORT_MANIFEST_V2_DRAFT.json` |
| Transport-manifest SHA-256 | `338bea1b7350d3b82146c7e728516ec7947471ee68db0f8871ddb72071b79620` |

The standalone transport JSON pin includes the interface ID, schema SHA, and closure-manifest SHA. The full QoS document carries the same manifest bytes and all corresponding values.

## Preserved transport behavior and history

Carry forward the QoS policy values, endpoint, message type name, latest-state/coalescing behavior, ordering classifications, action/reset readiness behavior, and failure classifications from revision 5. Only the versioned receipt/transport identities and manifest bytes are proposed to change.

Preserve the prior v1 historical values exactly: receipt interface `mecanum.final-issued-receipt/v1` / SHA-256 `90348664c4563997b93de7f10e278b10d4053fcb96909b6bb85c1319db76c40e`; transport ID `mecanum.final-issued-receipt-topic-qos/v1` / manifest SHA-256 `a3bc1a965fc6885825ab961289fa4028862aa7af4b3f3156bc40542f7ee08f62`. The v2 schema is not claimed to be the v1 artifact.

The schema SHA, closure-manifest SHA, transport-manifest SHA, and full-document SHA of this QoS draft are distinct. The QoS document's own full-document SHA is recorded externally in the bundled approval-record draft, not embedded here. No approval date is assigned; status remains `PENDING_USER_DECISION`.
