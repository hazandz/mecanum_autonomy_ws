# Proposed Bundled Approval Record — QoS Revision 6 / ACR Revision 8

**Record status:** `DRAFT`
**Approval status:** `PENDING_USER_DECISION`
**Approval date:** `PENDING_USER_DECISION`
**Baseline:** `integration/implementation@9a4c0d233e8237f01a04880fe99e8a3114528f4`
**Effect:** None before explicit approval and canonical integration.

This draft proposes a single approval record for a QoS revision 6 / ACR revision 8 bundle. It does not record that approval has occurred. The canonical QoS revision 5 / ACR revision 7 bundle remains in force at the baseline.

## 1. Expected canonical targets

| Artifact | Expected canonical target | Status of target selection |
|---|---|---|
| Receipt Topic QoS Contract revision 6 | `docs/RECEIPT_TOPIC_QOS_CONTRACT.md` | Existing canonical contract path. |
| ACR V3 Observation Boundary Closure revision 8 | `docs/ACR_V3_OBSERVATION_BOUNDARY_CLOSURE.md` | Existing canonical ACR path. |
| ROS receipt interface v2 | Proposed path: `ros2_ws/src/mecanum_nav_rl_interfaces/msg/FinalIssuedCommandReceipt.msg`; exact canonical target path: `PENDING_USER_DECISION` | Registry identifies the canonical interface directory family, while this proposal does not establish an exact canonical file path. The candidate `.msg` remains under the proposal directory. |
| Dependency-closure manifest | `PENDING_USER_DECISION` | Registry does not specify a canonical manifest path. Candidate file path is listed below. |
| Transport manifest | Embedded canonical representation in `docs/RECEIPT_TOPIC_QOS_CONTRACT.md` §4; standalone JSON target `PENDING_USER_DECISION`. | Candidate JSON file path is listed below. |
| Bundled approval record | `PENDING_USER_DECISION` (proposed path: `docs/governance/decisions/QOS_REVISION_6_ACR_REVISION_8_BUNDLE_APPROVAL.md`) | The existing governance decisions directory provides precedent; exact target requires governance decision. |

## 2. Exact artifacts proposed for review

| Role | Candidate path | Revision / identity | SHA-256 |
|---|---|---|---|
| Full QoS document | `docs/architecture/proposals/wp-03-contract-closure/WP-03_RECEIPT_TOPIC_QOS_CONTRACT_REVISION_6_DRAFT.md` | QoS Contract revision `6` | `e8077a93340d99b6cb2ed691fa00f093fb2c3d54a2a8ddff1547f4e928b1d1a1` |
| Full ACR document | `docs/architecture/proposals/wp-03-contract-closure/WP-03_ACR_V3_OBSERVATION_BOUNDARY_CLOSURE_REVISION_8_DRAFT.md` | ACR revision `8` | `f489d996255ea032657cf88157c90c5163f78491c0951e8dc3819046f03e3c49` |
| Receipt message schema | `docs/architecture/proposals/wp-03-contract-closure/WP-03_RECEIPT_INTERFACE_V2_DRAFT.msg` | Interface ID `mecanum.final-issued-receipt/v2`, schema revision `2` | `0c6446674bf17373ec646519043f506a9a7a15f95d5fdd10829b0cedb956500a` |
| Dependency-closure manifest | `docs/architecture/proposals/wp-03-contract-closure/WP-03_RECEIPT_INTERFACE_DEPENDENCY_CLOSURE_MANIFEST_V1.json` | Closure manifest version `1` | `0872fa8c10179f69c2e9e9546392ac734a4f4e94ade176a8be431f06905ecf73` |
| Transport manifest | `docs/architecture/proposals/wp-03-contract-closure/WP-03_RECEIPT_TOPIC_QOS_TRANSPORT_MANIFEST_V2_DRAFT.json` | Transport ID `mecanum.final-issued-receipt-topic-qos/v2`, version `2` | `338bea1b7350d3b82146c7e728516ec7947471ee68db0f8871ddb72071b79620` |

These hashes identify different byte sets: schema file, closure manifest, transport manifest, full QoS document, and full ACR document. None is interchangeable with another.

## 3. Dependency closure

The schema references `std_msgs/Header` and `geometry_msgs/Twist`. Its closure manifest pins the exact transitive message definitions by official repository, immutable source commit, path, and file SHA-256:

| Dependency file | Source commit | SHA-256 |
|---|---|---|
| `std_msgs/msg/Header.msg` (`ros2/common_interfaces`) | `a941f14bb318d8d904505ed935ccbb97f24a70a4` | `d2cea14630e39ed0fa5b432ba9160a7c38855b9427d3344f99e83e83facb53c2` |
| `builtin_interfaces/msg/Time.msg` (`ros2/rcl_interfaces`) | `7aa3caf43377ea6ad615bc1040832e2c7566bfbe` | `dc5a01ddde3aecffee21eb24974fe77cc969f873218a2b1811aa0ac8a456b8bd` |
| `geometry_msgs/msg/Twist.msg` (`ros2/common_interfaces`) | `a941f14bb318d8d904505ed935ccbb97f24a70a4` | `ed471ef861f65af991b1f64d66ef941dd41dd4c0702f6222512b1a16c62d58b0` |
| `geometry_msgs/msg/Vector3.msg` (`ros2/common_interfaces`) | `a941f14bb318d8d904505ed935ccbb97f24a70a4` | `d8b9ea9aad1f424faf4d2b94dae1e1368af1e5d59de11aeed019399cff7f9e1d` |

## 4. Transport and historical disposition

The proposed transport manifest v2 contains receipt interface ID `mecanum.final-issued-receipt/v2`, the schema SHA-256, and dependency-closure SHA-256. QoS policy values and transport behavior are carried forward unchanged from revision 5.

Historical values remain recorded and unmodified:

```text
Receipt interface v1: mecanum.final-issued-receipt/v1
Receipt interface v1 SHA-256: 90348664c4563997b93de7f10e278b10d4053fcb96909b6bb85c1319db76c40e
Transport v1 ID: mecanum.final-issued-receipt-topic-qos/v1
Transport v1 manifest SHA-256: a3bc1a965fc6885825ab961289fa4028862aa7af4b3f3156bc40542f7ee08f62
```

The v2 proposal does not claim to recover or match the v1 schema. No revision 6 / revision 8 document, v2 pin, date, or status change is approved by this draft.

## 5. Pending decision and authority boundary

```text
APPROVAL_STATUS: PENDING_USER_DECISION
QOS_REVISION_5: CURRENT_CANONICAL_AUTHORITY
ACR_REVISION_7: CURRENT_CANONICAL_AUTHORITY
WP-02: CLOSED
WP-03: BLOCKED_BY_CONTRACT
WP-04: BLOCKED_BY_CONTRACT
CODE_AUTHORIZATION: NOT_GRANTED
RUNTIME_APPROVED: NOT_APPROVED
```

Only after independent audit and explicit user decision may governance prepare canonical integration. This proposal is not an approval record with effect, does not change PEP or the Progress Ledger, and authorizes no code, ROS, runtime, HIL, hardware, or `deploy_real` activity.
