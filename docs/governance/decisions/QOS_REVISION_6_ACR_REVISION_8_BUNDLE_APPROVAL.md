# QoS Revision 6 / ACR Revision 8 Bundled Approval Record

**Record status:** `APPROVED_FOR_CANONICAL_BUNDLED_INTEGRATION_CANDIDATE`
**Decision:** `APPROVED_FOR_CANONICAL_BUNDLED_INTEGRATION`
**Approval date:** `2026-10-08` (Asia/Ho_Chi_Minh)
**Approver role:** `Project Owner/User`
**Work package:** `WP-03-RECEIPT-INTERFACE-V2-CANONICAL-BUNDLE-INTEGRATION-CANDIDATE`
**Candidate branch:** `wp-03-qos6-acr8-canonical-bundle-integration-candidate`
**Integration base:** `9a4c0d233e8237f01a04880fe99e8a3114528f4c`
**Approved source candidate:** `8600f4c6b1bd58aa0f1976bf606dbd07b6594822`
**Activation:** Pending fast-forward of this exact candidate to `integration/implementation`.

## Decision and scope

The Project Owner/User approved the exact QoS revision 6 / ACR revision 8 bundle at source candidate `8600f4c6b1bd58aa0f1976bf606dbd07b6594822`, including the technical target paths below and byte-identical copy rule. This candidate records that approval for governance/contract integration. The decision becomes active canonical source selection only when this approval record, the pinned artifacts, the Registry update, and the append-only Ledger candidate entry are integrated on `integration/implementation`. Until then, integration remains at the revision 5 / revision 7 baseline.

The approved scope is governance and contract-document integration only. It does not authorize implementation, code changes, ROSIDL generation/build, tests, ROS/runtime, HIL, hardware, `deploy_real`, or changes to WP-03/WP-04 status or dependencies.

## Exact approved bundle and target paths

| Artifact | Canonical target path | Revision / identity | Approved SHA-256 | Source candidate path |
|---|---|---|---|---|
| Receipt Topic QoS Contract | `docs/RECEIPT_TOPIC_QOS_CONTRACT.md` | Revision `6`; transport ID `mecanum.final-issued-receipt-topic-qos/v2` | `4200cd2fbdc81a19400f168dd3526eb7871ac2251049fc7c4f5d5c2fddfd2022` | `docs/architecture/proposals/wp-03-contract-closure/WP-03_RECEIPT_TOPIC_QOS_CONTRACT_REVISION_6_DRAFT.md` |
| ACR V3 Observation Boundary Closure | `docs/ACR_V3_OBSERVATION_BOUNDARY_CLOSURE.md` | Revision `8` | `03fef021f6b9731f811f83a5e53aae1c430bdc2ea76815a8ada416f1a5bf772c` | `docs/architecture/proposals/wp-03-contract-closure/WP-03_ACR_V3_OBSERVATION_BOUNDARY_CLOSURE_REVISION_8_DRAFT.md` |
| Receipt interface schema | `ros2_ws/src/mecanum_nav_rl_interfaces/msg/FinalIssuedCommandReceipt.msg` | ID `mecanum.final-issued-receipt/v2`; schema revision `2` | `0c6446674bf17373ec646519043f506a9a7a15f95d5fdd10829b0cedb956500a` | `docs/architecture/proposals/wp-03-contract-closure/WP-03_RECEIPT_INTERFACE_V2_DRAFT.msg` |
| Dependency-closure manifest | `docs/RECEIPT_INTERFACE_DEPENDENCY_CLOSURE_MANIFEST.json` | Closure version `1` | `0872fa8c10179f69c2e9e9546392ac734a4f4e94ade176a8be431f06905ecf73` | `docs/architecture/proposals/wp-03-contract-closure/WP-03_RECEIPT_INTERFACE_DEPENDENCY_CLOSURE_MANIFEST_V1.json` |
| Transport manifest JSON | `docs/RECEIPT_TOPIC_QOS_TRANSPORT_MANIFEST.json` | ID `mecanum.final-issued-receipt-topic-qos/v2`; version `2` | `338bea1b7350d3b82146c7e728516ec7947471ee68db0f8871ddb72071b79620` | `docs/architecture/proposals/wp-03-contract-closure/WP-03_RECEIPT_TOPIC_QOS_TRANSPORT_MANIFEST_V2_DRAFT.json` |
| This bundled approval record | `docs/governance/decisions/QOS_REVISION_6_ACR_REVISION_8_BUNDLE_APPROVAL.md` | Approval decision dated `2026-10-08` | Recorded by this exact file in Git history | — |

Each technical target must be byte-identical to the source candidate artifact identified in this table and match its approved full SHA-256. The standalone transport JSON must also be byte-identical to the manifest bytes embedded in QoS revision 6 §4. No path substitution or content regeneration is permitted under this approval.

The full-document hashes identify the complete QoS and ACR files; the schema SHA identifies only the `.msg`; the dependency-closure SHA identifies only its JSON; and the transport-manifest SHA identifies only its JSON. These hashes are distinct and are not interchangeable.

## Canonical source selection and status effect

This candidate's Registry selects these exact target paths and hashes for activation on integration. The pre-integration `DRAFT_FOR_INDEPENDENT_AUDIT_AND_USER_DECISION` labels on the approved QoS6/ACR8 source bytes are superseded for document authority/status only when this exact bundle, approval record, Registry update, and Ledger entry are canonically integrated. This follows the status treatment recorded for the prior QoS5/ACR7 bundled approval; it does not change the approved technical bytes or semantics.

The approved change scope updates receipt-interface identity/pins and transport-contract ID/version/manifest bytes. QoS policy values and transport behavior remain unchanged. The historical QoS revision 5 / ACR revision 7 approval and v1 pins remain preserved:

```text
Historical approval record: docs/governance/decisions/QOS_REVISION_5_ACR_REVISION_7_BUNDLE_APPROVAL.md
Historical QoS revision 5 SHA-256: 9f87f4d09ec50aacf8c0cf69e11bff8bceb4219b8d09f68998288907afb8302b
Historical ACR revision 7 SHA-256: cb111c84c3b8f7d1393256b4c15f28c5f0bcafa1d2a84dde08e2cb0cd823ce0f
Historical receipt-interface ID/SHA-256: mecanum.final-issued-receipt/v1 / 90348664c4563997b93de7f10e278b10d4053fcb96909b6bb85c1319db76c40e
Historical transport ID/SHA-256: mecanum.final-issued-receipt-topic-qos/v1 / a3bc1a965fc6885825ab961289fa4028862aa7af4b3f3156bc40542f7ee08f62
```

This bundle does not close WP-03 or WP-04, change PEP status/dependencies, satisfy any implementation gate, or grant code/runtime authorization. WP-03 and WP-04 remain `BLOCKED_BY_CONTRACT`; code authorization remains not granted and runtime remains not approved.

```text
WP-02: CLOSED
WP-03: BLOCKED_BY_CONTRACT
WP-04: BLOCKED_BY_CONTRACT
CODE_AUTHORIZATION: NOT_GRANTED
RUNTIME_APPROVED: NOT_APPROVED
```

## Candidate provenance

This approval record is part of a candidate branch based on `9a4c0d233e8237f01a04880fe99e8a3114528f4c`; it is not active on the integration line yet. The candidate commit identity is available from Git history and is not embedded in this record to avoid a self-referential commit hash.
