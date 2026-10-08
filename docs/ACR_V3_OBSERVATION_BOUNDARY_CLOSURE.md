# Đề xuất ACR V3 Observation Boundary Closure — revision 8

**Status:** `ACR_REVISION_8: DRAFT_FOR_INDEPENDENT_AUDIT_AND_USER_DECISION`
**Work package:** `WP-03-RECEIPT-INTERFACE-V2-BUNDLE-CORRECTION`
**Source authority:** ACR revision 7 at baseline, full-document SHA-256 `cb111c84c3b8f7d1393256b4c15f28c5f0bcafa1d2a84dde08e2cb0cd823ce0f`
**Integration baseline:** `origin/integration/implementation@9a4c0d233e8237f01a04880fe99e8a3114528f4`
**Architecture authority:** `docs/MECANUM_NAV_DRL_Architecture.docx`
**Runtime status:** `RUNTIME_NOT_APPROVED`

## 1. Tính chất và hiệu lực của đề xuất

Đây là full-text proposal cho ACR revision 8, dẫn xuất từ ACR revision 7 tại baseline. Nó chỉ đề xuất cập nhật receipt-interface/dependency pins và bundled manifest references; không có hiệu lực trước independent audit, explicit user approval, và canonical integration. ACR revision 7 tiếp tục là authority hiện hành cho tới khi bundle revision 6/revision 8 được tích hợp.

Phân tích audit của candidate `7e0486bceda97bdf4ed02d02a175f958e0b1f063` được giữ như lịch sử giải thích cho Gate A/B trong ACR revision 7. Tại baseline hiện tại, revision 7 là canonical authority; Gate A/B wording được tiếp tục nguyên nghĩa trong draft revision 8. Observation Input Contract revision 6 §8.1 chỉ cho phép readiness review, không phải implementation authorization.

## 2. Historical source: ACR revision 6 §8 cited during revision 7 review

> Before a V3 core implementation packet may be issued:
>
> 1. record this approved ACR in architecture/governance and update the V3 observation specification;
> 2. approve the bundled Receipt Topic QoS Contract with its canonical ID/hash, delivery/coalescing/action-bound readiness behavior, and `TopicQosContractV3` record; this is separate from S2;
> 3. design `ObservationInputContractV3` model, canonical source, compiler and composition validation with no unresolved values in resolved config;
> 4. add receipt message/topic, version/hash compatibility checks and its canonical topic/QoS record;
> 5. define pure-Python ingress seams for typed snapshots and receipt data; and
> 6. obtain an independent audit that 81D layout and process/safety isolation remain preserved.
>
> Only then may a later work package implement the connected pure-Python V3 assembler/encoder/history path. Runtime integration is a separate gate.

### 2.1 Vì sao câu cuối không tạo ngoại lệ primitive-only

Đây là kết luận của lần review revision 7 về cách đọc revision 6 §8; nó được giữ làm lịch sử. Tại baseline hiện tại, ACR revision 7 là authority và Gate A/B wording của nó được carried forward trong draft revision 8.

## 3. Proposed revision 8 receipt-pin amendment and bundled change control

At the stated integration baseline, ACR revision 7 and QoS Contract revision 5 are the canonical bundle. This proposed revision 8 updates the receipt-interface/dependency pins, proposes exact target paths for the related artifacts, and carries a versioned transport-manifest reference; it does not make the revision effective. The companion full-text QoS revision 6 draft and this full-text ACR revision 8 draft must be audited and decided as one bundle.

The prior revision 7 / revision 5 approval record and all values it pinned remain historical provenance. In particular, the prior receipt interface v1 pin and transport v1 manifest are not rewritten. Historical pins: `mecanum.final-issued-receipt/v1` / `90348664c4563997b93de7f10e278b10d4053fcb96909b6bb85c1319db76c40e`, and `mecanum.final-issued-receipt-topic-qos/v1` / `a3bc1a965fc6885825ab961289fa4028862aa7af4b3f3156bc40542f7ee08f62`. The proposed next bundle carries the following new pins:

```text
QoS full-text proposal: docs/architecture/proposals/wp-03-contract-closure/WP-03_RECEIPT_TOPIC_QOS_CONTRACT_REVISION_6_DRAFT.md
QoS revision: 6
ACR full-text proposal: docs/architecture/proposals/wp-03-contract-closure/WP-03_ACR_V3_OBSERVATION_BOUNDARY_CLOSURE_REVISION_8_DRAFT.md
ACR revision: 8
Receipt interface ID: mecanum.final-issued-receipt/v2
Receipt schema path: docs/architecture/proposals/wp-03-contract-closure/WP-03_RECEIPT_INTERFACE_V2_DRAFT.msg
Receipt schema revision: 2
Receipt schema SHA-256: 0c6446674bf17373ec646519043f506a9a7a15f95d5fdd10829b0cedb956500a
Dependency-closure manifest path: docs/architecture/proposals/wp-03-contract-closure/WP-03_RECEIPT_INTERFACE_DEPENDENCY_CLOSURE_MANIFEST_V1.json
Dependency-closure manifest SHA-256: 0872fa8c10179f69c2e9e9546392ac734a4f4e94ade176a8be431f06905ecf73
Transport ID: mecanum.final-issued-receipt-topic-qos/v2
Transport manifest version: 2
Transport manifest path: docs/architecture/proposals/wp-03-contract-closure/WP-03_RECEIPT_TOPIC_QOS_TRANSPORT_MANIFEST_V2_DRAFT.json
Transport manifest SHA-256: 338bea1b7350d3b82146c7e728516ec7947471ee68db0f8871ddb72071b79620
```

### 3.1 Proposed canonical target paths

The following exact paths are proposed for user/governance decision. Registry entry `ros2_ws/src/mecanum_nav_rl_interfaces/msg/**` establishes the canonical interface directory family, while the exact new message path and manifest locations are not currently defined. These path proposals do not create or canonicalize files:

| Artifact | Proposed target path | Status and integration identity rule |
|---|---|---|
| Receipt interface schema | `ros2_ws/src/mecanum_nav_rl_interfaces/msg/FinalIssuedCommandReceipt.msg` | `PROPOSED_FOR_USER_DECISION`; if approved and integrated, bytes must be identical to proposal schema SHA-256 `0c6446674bf17373ec646519043f506a9a7a15f95d5fdd10829b0cedb956500a`. |
| Dependency-closure manifest | `docs/RECEIPT_INTERFACE_DEPENDENCY_CLOSURE_MANIFEST.json` | `PROPOSED_FOR_USER_DECISION`; if approved and integrated, bytes must be identical to proposal closure-manifest SHA-256 `0872fa8c10179f69c2e9e9546392ac734a4f4e94ade176a8be431f06905ecf73`. |
| Transport manifest JSON | `docs/RECEIPT_TOPIC_QOS_TRANSPORT_MANIFEST.json` (standalone companion to the manifest embedded in QoS §4) | `PROPOSED_FOR_USER_DECISION`; if approved and integrated, bytes must be identical to proposal transport-manifest SHA-256 `338bea1b7350d3b82146c7e728516ec7947471ee68db0f8871ddb72071b79620`, and to the embedded QoS §4 manifest. |

The named proposal artifacts remain under `docs/architecture/proposals/wp-03-contract-closure/`. These paths remain proposed targets only; no artifact is copied to them by this candidate.

QoS policy values and transport behavior are carried forward unchanged. The interface schema, dependency-closure manifest, transport manifest, full QoS document, and full ACR document each have distinct SHA-256 values. Full-document hashes are external in the bundled approval-record draft, avoiding self-reference.

The proposed canonical targets for QoS and this ACR are `docs/RECEIPT_TOPIC_QOS_CONTRACT.md` and `docs/ACR_V3_OBSERVATION_BOUNDARY_CLOSURE.md`. The expected approval-record target follows the existing governance record path convention: `docs/governance/decisions/QOS_REVISION_6_ACR_REVISION_8_BUNDLE_APPROVAL.md`. For the schema and manifests, §3.1 supplies concrete proposed target paths and marks each `PROPOSED_FOR_USER_DECISION`; those paths are not canonicalized or created by this draft. The standalone transport JSON proposal is a companion copy of the same manifest bytes embedded in QoS §4. Any later approved integration must use bytes identical to the proposal hashes recorded in §3 and the bundled approval record.

This proposal does not supply an approval date, claim approval, or make any artifact canonical. QoS revision 5 and ACR revision 7 remain authority until an exact revision 6 / revision 8 bundle is audited, user-approved, and integrated.

## 4. §8 carried forward in the proposed ACR revision 8

> **DRAFT — ACR §8 carried forward in proposed revision 8. Not effective unless this full-text ACR revision 8 and QoS Contract revision 6 pass independent audit, receive explicit bundled user approval with their full-document SHA-256 values recorded in the approval record, and are canonically integrated. Until then ACR revision 7 and QoS revision 5 remain current authority. Proposed receipt pins: interface v2 `0c6446674bf17373ec646519043f506a9a7a15f95d5fdd10829b0cedb956500a`, dependency closure `0872fa8c10179f69c2e9e9546392ac734a4f4e94ade176a8be431f06905ecf73`, transport v2 `338bea1b7350d3b82146c7e728516ec7947471ee68db0f8871ddb72071b79620`.**
>
> ### 8. Gates after approval
>
> This section separates (A) the constrained, non-integrated primitive-only first deliverable defined by `PEP-001` revision `0.3.0` for `WP-04-POLICY-CORE-P0`, from (B) connected and/or profile-resolving V3 observation implementation. Gate A wording is carried forward from the current ACR revision 7 without semantic change; this proposed revision 8 changes only receipt pins and bundle metadata. Neither gate changes the PEP dependency, package ownership, approved semantic contracts, or runtime status.
>
> #### Gate A — primitive-only, non-integrated deliverable
>
> After the preconditions below have been satisfied, a separate exact implementation packet may be submitted for consideration only for the constrained first deliverable in `PEP-001` revision `0.3.0`:
>
> 1. immutable `ObservationCutoffV3` core type and structural fail-closed validation; and
> 2. immutable structural `ObservationInputContractV3` models and structural validation, including exact approved contract references.
>
> Gate A is limited to type shape and structural validation. It does not resolve profiles, create operational facts, integrate configuration, or implement connected observation behavior. It does not waive or amend the dependency `WP-04 → WP-03`. Under the current PEP, WP-03 must be closed before WP-04 proceeds; only a separate, independently audited and explicitly approved PEP/governance amendment may change that dependency or sequencing.
>
> A Gate A packet may be considered only after all of the following have occurred:
>
> 1. the ACR revision 8 amendment and Receipt Topic QoS Contract document revision 6 (with exact full-document SHAs recorded in the approval record) have passed independent audit, received explicit bundled user approval, and been canonically integrated under the repository workflow;
> 2. the approved semantic bundle is recorded canonically under the applicable PEP/governance workflow, without altering its approved identities, hashes, revisions, or semantics;
> 3. the WP-03 dependency is closed, or its treatment is changed by a separate, independently audited and explicitly approved PEP/governance amendment; and
> 4. the exact implementation packet has passed independent audit and received separate explicit user approval.
>
> These conditions allow only consideration of a later packet. They do not authorize source edits by themselves; implementation authorization must be granted separately for that exact packet.
>
> Gate A prohibits `ResolvedConfigV3` changes; compiler, validator, composition, YAML, profile, config-hash generation or configuration changes; ROS/ROSIDL, QoS, TF, DDS or runtime integration; receipt bridge/history; S2 synchronizer or buffer; assembler or encoder; construction of the policy vector, including a vector of 81 dimensions; V1 observation, decoder, history, snapshot, wrapper, alias or fallback use; and Ground Truth in the policy path.
>
> #### Gate B — connected and/or profile-resolving implementation
>
> Before a connected or profile-resolving V3 implementation packet may be issued, all six existing ACR revision 7 §8 gates remain required:
>
> 1. record the approved ACR in architecture/governance and update the V3 observation specification;
> 2. approve the bundled Receipt Topic QoS Contract with its canonical ID/hash, delivery/coalescing/action-bound readiness behavior, and `TopicQosContractV3` record; this is separate from S2;
> 3. design the `ObservationInputContractV3` model, canonical source, compiler and composition validation with no unresolved values in resolved config;
> 4. add the receipt message/topic, version/hash compatibility checks and its canonical topic/QoS record;
> 5. define pure-Python ingress seams for typed snapshots and receipt data; and
> 6. obtain an independent audit that the 81D layout and process/safety isolation remain preserved.
>
> Connected assembler/encoder/history implementation may be considered only after these gates and review/approval of its exact packet. Profile resolution additionally requires evidence for the applicable profile; no unresolved profile-specific evidence is supplied or waived by this section. Runtime integration remains a separate gate.

## 5. Invariants kỹ thuật phải giữ cho packet Gate A tương lai

Các invariants dưới đây chỉ là ràng buộc kỹ thuật để đánh giá packet tương lai. Chúng không phải code authorization được proposal này cấp.

### 5.1 Cutoff, lifecycle và time domain

- Cutoff phải strictly after cả action barrier và reset barrier.
- Cutoff và hai barrier phải dùng cùng lifecycle identity, epoch/reset epoch, generation/runtime generation và profile ROS-time domain.
- `SafetyLifecycle` là owner của action/reset barriers. `RobotRuntimeAdapter.wait_transition_snapshot(after=receipt)` là operational creator của cutoff cho transition. Primitive chỉ nhận/validate facts caller cung cấp; không tạo, sửa hoặc thay thế barrier/cutoff facts.
- Status và error behavior phải fail closed, typed, và giữ đúng canonical statuses của S2 revision 2:

```text
INPUT_MISSING_NON_READY
LIFECYCLE_OR_CONTRACT_MISMATCH_NON_READY
BARRIER_NOT_PASSED_NON_READY
CUTOFF_BARRIER_ORDER_NON_READY
FUTURE_STAMP_CONTRACT_ERROR
INPUT_STALE_NON_READY
SENSOR_SYNC_MISS_NON_READY
REFERENCE_SYNC_MISS_NON_READY
ORDERING_CONTRACT_AMBIGUITY_NON_READY
BUFFER_OVERFLOW_NON_READY
GENERATION_INVALIDATED_NON_READY
```

Structural primitive chỉ giữ type/status contract; không hiện thực synchronizer, buffer hoặc vận hành S2.

### 5.2 `config_hash` và exact contract references

- `config_hash` chỉ là opaque provenance do caller cung cấp. Primitive không tạo, tính hoặc xác minh hash; không biến nó thành config field hay config implementation.
- Exact references không được alias, thay hash, fallback hoặc diễn giải lại:

```text
S2 contract ID:       mecanum.snapshot-synchronization-temporal/v1
S2 SHA-256:           1be31c1915fedd86f269cee5214d794da0899a0d69dbb0ba5392e619813d4a8f
Receipt interface ID: mecanum.final-issued-receipt/v2 (proposed)
Receipt interface path: docs/architecture/proposals/wp-03-contract-closure/WP-03_RECEIPT_INTERFACE_V2_DRAFT.msg
Receipt interface revision: 2
Receipt interface schema SHA-256: 0c6446674bf17373ec646519043f506a9a7a15f95d5fdd10829b0cedb956500a
Dependency-closure manifest path: docs/architecture/proposals/wp-03-contract-closure/WP-03_RECEIPT_INTERFACE_DEPENDENCY_CLOSURE_MANIFEST_V1.json
Dependency-closure manifest SHA-256: 0872fa8c10179f69c2e9e9546392ac734a4f4e94ade176a8be431f06905ecf73
Receipt QoS ID:       mecanum.final-issued-receipt-topic-qos/v2 (proposed)
Receipt transport-manifest version: 2
Receipt transport-manifest SHA-256: 338bea1b7350d3b82146c7e728516ec7947471ee68db0f8871ddb72071b79620
```

### 5.3 Exclusions và profile evidence chưa giải quyết

Gate A không bao gồm V1, compiler/profile integration, ROS/runtime, receipt bridge/history, S2 synchronizer/buffer, assembler/encoder hoặc vector 81D. Gate A cũng không chọn hoặc suy diễn timing, buffer, freshness, measured-twist validity/covariance/provenance, hoặc YDLIDAR X3 extrinsic/range/frame. Các evidence profile-specific này vẫn là yêu cầu chưa giải quyết cho Gate B khi áp dụng.

## 6. Dependency, authority và các bước không được gộp

Theo PEP-001 revision `0.3.0` trên integration baseline, `WP-04-POLICY-CORE-P0` phụ thuộc WP-03; WP-03 và WP-04 đều `BLOCKED_BY_CONTRACT`. Gate A không miễn, đóng hoặc sửa dependency đó, không đổi status và không đổi sequencing. Chỉ closure WP-03 hoặc một PEP/governance amendment riêng, được audit và duyệt độc lập, mới có thể xử lý dependency.

Các bước authority tách biệt theo thứ tự; không bước nào tự hàm ý bước sau:

```text
ACR revision 8 proposal
→ independent audit
→ explicit bundled user approval of ACR revision 8 and QoS document revision 6
→ canonical integration of the approved bundle
→ WP-03 dependency closure or separately approved PEP/governance amendment
→ exact implementation packet independent review and separate user approval
→ implementation authorization for that exact packet, if explicitly granted
```

Proposal, audit, approval bundle, canonical integration, dependency closure và packet approval là các trạng thái riêng. Không trạng thái nào trong số đó tự tạo runtime approval.

## 7. Trạng thái của proposal

```text
ACR_REVISION_8: DRAFT_PENDING_INDEPENDENT_AUDIT_AND_USER_DECISION
ACR_REVISION_7: CURRENT_CANONICAL_AUTHORITY_UNTIL_REVISION_8_BUNDLE_INTEGRATED
QOS_REVISION_6: DRAFT_PENDING_INDEPENDENT_AUDIT_AND_USER_DECISION
QOS_REVISION_5: CURRENT_CANONICAL_AUTHORITY_UNTIL_REVISION_6_BUNDLE_INTEGRATED
RECEIPT_INTERFACE_V1: HISTORICAL_PIN_RETAINED
RECEIPT_INTERFACE_V2: PROPOSED; PENDING_USER_DECISION
TRANSPORT_V1: HISTORICAL_PROVENANCE_RETAINED
TRANSPORT_V2: PROPOSED; PENDING_USER_DECISION
WP-02: CLOSED
WP-03: BLOCKED_BY_CONTRACT
WP-04: BLOCKED_BY_CONTRACT
CODE_AUTHORIZATION: NOT_GRANTED
RUNTIME_NOT_APPROVED
```

Đây chỉ là proposal cho audit và user decision. Nó không sửa canonical ACR revision 7, QoS revision 5, PEP-001 hoặc ledger; không canonical-integrate QoS revision 6; không tạo implementation packet; không tuyên bố WP-04 sẵn sàng viết code; và không cấp code hay runtime authorization.
