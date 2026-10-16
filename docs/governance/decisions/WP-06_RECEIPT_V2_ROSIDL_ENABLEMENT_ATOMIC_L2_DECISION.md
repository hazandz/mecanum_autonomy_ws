# WP-06 Receipt v2 ROSIDL Enablement — Atomic L2 Decision

## Decision class and lifecycle

Classification: `L2_PUBLIC_INTERFACE_BUILD_ENABLEMENT_AND_HISTORICAL_STATUS_SUPERSESSION`.

This decision is supplied for this exact candidate based on `c8b178a2f1feee115a3a01553afaec616cabf737`. It resolves the historical source annotations only for the ROSIDL build-generation status and authorizes adding the already-approved receipt v2 schema to the interface package's generated-interface list in this atomic candidate. Before audit and integration this is a review candidate. Only after audit PASS, separate User authorization for the exact commit, fast-forward integration, and remote-ref verification does its post-integration status apply.

## Canonical receipt and historical annotation disposition

- Receipt ID: `mecanum.final-issued-receipt/v2`.
- Schema revision: `2`.
- Canonical source: `ros2_ws/src/mecanum_nav_rl_interfaces/msg/FinalIssuedCommandReceipt.msg`.
- Canonical source SHA-256: `0c6446674bf17373ec646519043f506a9a7a15f95d5fdd10829b0cedb956500a` (unchanged).
- Dependency closure remains `docs/RECEIPT_INTERFACE_DEPENDENCY_CLOSURE_MANIFEST.json`, SHA-256 `0872fa8c10179f69c2e9e9546392ac734a4f4e94ade176a8be431f06905ecf73`.
- QoS6 remains unchanged: contract `docs/RECEIPT_TOPIC_QOS_CONTRACT.md`, SHA-256 `4200cd2fbdc81a19400f168dd3526eb7871ac2251049fc7c4f5d5c2fddfd2022`; transport manifest `docs/RECEIPT_TOPIC_QOS_TRANSPORT_MANIFEST.json`, SHA-256 `338bea1b7350d3b82146c7e728516ec7947471ee68db0f8871ddb72071b79620`.

The source comments `DRAFT public receipt schema, proposed interface ID: mecanum.final-issued-receipt/v2` and `Not installed in a ROSIDL package; no implementation or runtime authorization.` are historical annotations. `DRAFT` does not downgrade the already established canonical receipt v2. “Not installed in a ROSIDL package” was true at this candidate's base; after this exact candidate is audited, separately authorized, and integrated, that clause is superseded only for ROSIDL build-generation status. The phrase “no implementation or runtime authorization” remains effective for every runtime receipt producer/consumer, ROS node, publisher, subscriber, topic, runtime QoS, SafetySupervisor, FinalTwistPublisher, and command path.

ROSIDL generation is build/interface enablement only; it is not runtime implementation.

## Exact implementation boundary

The candidate may change only these ten paths:

1. `ros2_ws/src/mecanum_nav_rl_interfaces/CMakeLists.txt`
2. `ros2_ws/src/mecanum_nav_rl_interfaces/package.xml`
3. `ros2_ws/src/mecanum_nav_rl_interfaces/CHANGELOG.md`
4. `ros2_ws/src/mecanum_nav_rl_interfaces/test/test_interface_contracts.py`
5. `ros2_ws/src/mecanum_nav_rl_interfaces/test/test_final_issued_command_receipt_rosidl_enablement.py`
6. `docs/governance/decisions/WP-06_RECEIPT_V2_ROSIDL_ENABLEMENT_ATOMIC_L2_DECISION.md`
7. `docs/governance/evidence/WP-06_RECEIPT_V2_ROSIDL_ENABLEMENT_ATOMIC_L2_EVIDENCE.json`
8. `docs/governance/CANONICAL_SOURCE_REGISTRY.md`
9. `docs/governance/PROJECT_EXECUTION_PLAN.md`
10. `docs/governance/PROJECT_PROGRESS_LEDGER.md`

The receipt `.msg` bytes, receipt v2 identity, QoS6, and dependency closure do not change. This decision does not create `/mecanum/final_issued_command`, a publisher/subscriber, runtime QoS validation, runtime receipt evidence, `ResolvedConfigV3`, `config_hash`, Gate B transition, or runtime authorization. `RUNTIME_APPROVED: NOT_APPROVED` remains unchanged. WP-04, WP-05, Gate A, and Gate B statuses are not changed by this record.

## Evidence fingerprints

The exact source-base fingerprints and the conditional lifecycle are machine-recorded in `docs/governance/evidence/WP-06_RECEIPT_V2_ROSIDL_ENABLEMENT_ATOMIC_L2_EVIDENCE.json`. The evidence record does not self-reference its own hash or commit.
