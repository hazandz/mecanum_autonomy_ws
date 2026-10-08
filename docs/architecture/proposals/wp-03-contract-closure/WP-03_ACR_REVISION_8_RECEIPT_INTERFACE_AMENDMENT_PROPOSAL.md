# ACR Revision 8 Receipt Interface Amendment Proposal

**Status:** `DRAFT_FOR_INDEPENDENT_AUDIT_AND_USER_DECISION`
**Current authority at baseline:** ACR revision 7 / QoS revision 5
**Full-text draft:** `docs/architecture/proposals/wp-03-contract-closure/WP-03_ACR_V3_OBSERVATION_BOUNDARY_CLOSURE_REVISION_8_DRAFT.md`
**ACR revision:** `8`
**Full-document SHA-256:** `f489d996255ea032657cf88157c90c5163f78491c0951e8dc3819046f03e3c49`

This amendment proposal accompanies the QoS revision 6 proposal. It is not authoritative until the full QoS6/ACR8 bundle is independently audited, explicitly user-approved, and canonically integrated. The existing QoS revision 5 / ACR revision 7 bundle remains current.

## Proposed exact receipt pins

| Pin | Proposed value |
|---|---|
| Receipt interface ID | `mecanum.final-issued-receipt/v2` |
| Schema path | `docs/architecture/proposals/wp-03-contract-closure/WP-03_RECEIPT_INTERFACE_V2_DRAFT.msg` |
| Schema revision | `2` |
| Schema SHA-256 | `0c6446674bf17373ec646519043f506a9a7a15f95d5fdd10829b0cedb956500a` |
| Dependency-closure manifest path | `docs/architecture/proposals/wp-03-contract-closure/WP-03_RECEIPT_INTERFACE_DEPENDENCY_CLOSURE_MANIFEST_V1.json` |
| Dependency-closure manifest SHA-256 | `0872fa8c10179f69c2e9e9546392ac734a4f4e94ade176a8be431f06905ecf73` |
| Transport ID | `mecanum.final-issued-receipt-topic-qos/v2` |
| Transport manifest version/path | `2` / `docs/architecture/proposals/wp-03-contract-closure/WP-03_RECEIPT_TOPIC_QOS_TRANSPORT_MANIFEST_V2_DRAFT.json` |
| Transport-manifest SHA-256 | `338bea1b7350d3b82146c7e728516ec7947471ee68db0f8871ddb72071b79620` |

These values must exactly match the proposed QoS revision 6 and bundled approval-record draft. The full ACR document hash is external; this document does not embed its own hash.

## Historical pins and effect

Keep the existing receipt interface v1 pin and transport v1 ID/hash as historical provenance; do not rewrite either record or treat the new schema as the old v1 artifact. QoS policy values and transport behavior are unchanged by this proposed pin update.

The proposed canonical ACR target remains `docs/ACR_V3_OBSERVATION_BOUNDARY_CLOSURE.md`. The current Gate A/B wording, WP-03/WP-04 statuses, and WP-04 dependency on WP-03 are carried forward without change. Any status or dependency transition requires its own governance process. This amendment grants no code, ROS, runtime, HIL, hardware, or `deploy_real` authorization.
