# Đề xuất amendment ACR §8 — revision 6 lên revision 7

**Status:** `ACR_REVISION_7: DRAFT_FOR_INDEPENDENT_AUDIT`
**Ngày:** `2026-10-05`
**Work package:** `WP-04-ACR-REVISION-7-FORMAL-AMENDMENT-PROPOSAL`
**Base candidate:** `wp-04-acr-section-8-scope-clarification@7e0486bceda97bdf4ed02d02a175f958e0b1f063`
**Integration reference:** `origin/integration/implementation@f8933bcff2bb30b1dad57d71d91678e36746326f`
**Architecture authority:** `docs/MECANUM_NAV_DRL_Architecture.docx`
**Runtime status:** `RUNTIME_NOT_APPROVED`

## 1. Tính chất và hiệu lực của đề xuất

Đây là **đề xuất amendment ACR §8 từ revision 6 lên revision 7**, được lập để independent audit và user decision. Đây không phải clarification có hiệu lực ngay, không sửa nội dung ACR revision 6 và không tự thay đổi authority hiện hành. ACR revision 6 tiếp tục là authority cho tới khi amendment revision 7 được independent audit, được user phê duyệt và được canonical integration theo đúng workflow.

Audit độc lập của candidate `7e0486bceda97bdf4ed02d02a175f958e0b1f063` xác định rằng câu mở đầu ACR §8 áp các gate trước khi phát hành “a V3 core implementation packet”, trong khi câu kết chỉ giới hạn thời điểm triển khai connected assembler/encoder/history. Câu kết không nói các gate trước chỉ áp dụng cho connected path và không tạo ngoại lệ primitive-only. Observation Input Contract revision 6 §8.1 chỉ cho phép readiness review; nó không phải implementation authorization. Vì vậy, Gate A dưới đây chỉ là wording được đề xuất cho ACR revision 7 và chưa có hiệu lực theo ACR revision 6.

## 2. ACR revision 6 §8 hiện hành — trích nguyên văn

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

Câu mở đầu áp sáu gate trước khi phát hành bất kỳ “V3 core implementation packet” nào, không giới hạn đối tượng đó vào connected hoặc profile-resolving implementation. Các gate 2–5 bao gồm QoS, compiler/composition, receipt message/topic và ingress, vượt ra ngoài primitive-only scope. Câu cuối chỉ nói connected assembler/encoder/history được triển khai sau các gate; nó không miễn các gate đó cho một packet primitive-only. Do đó không thể dựa vào câu cuối để coi Gate A đã được cho phép theo ACR revision 6.

## 3. Approval bundle với Receipt Topic QoS Contract revision 4

ACR revision 6 và `RECEIPT_TOPIC_QOS_CONTRACT` revision 4 hiện là một approval bundle. Đề xuất này giữ quan hệ bundle đó cho amendment: việc user approval cho ACR revision 7 phải được thực hiện cùng với việc **re-acknowledge Receipt Topic QoS Contract revision 4**, như một quyết định bundled approval được ghi nhận rõ. Re-acknowledgment không tạo revision QoS mới và không thay đổi tài liệu QoS revision 4.

Các định danh phải giữ nguyên chính xác:

```text
Receipt QoS contract ID: mecanum.final-issued-receipt-topic-qos/v1
Receipt QoS SHA-256:     a3bc1a965fc6885825ab961289fa4028862aa7af4b3f3156bc40542f7ee08f62
Receipt QoS revision:    4 (unchanged)
```

Semantics của revision 4 được giữ nguyên: `RELIABLE`, `TRANSIENT_LOCAL`, `KEEP_LAST(1)`; latest-state/coalescing và delivery-order classification như hợp đồng hiện hành; receipt readiness gắn với action/reset barrier; deadline, lifespan và liveliness lease không có giá trị hữu hạn, và liveliness không được dùng để kết luận dead-writer. Không thêm alias, fallback, giá trị QoS mới hoặc hash mới.

Audit evidence hiện có không chỉ ra rằng QoS revision 4 cần thay đổi. Nếu audit sau này tìm thấy evidence cho thấy contract QoS cần sửa, việc đó là finding và quyết định riêng cần user/auditor xử lý; dừng phần thay đổi QoS tại đó. Proposal này không thiết kế, sửa hoặc tạo hash/revision QoS.

## 4. Wording thay thế §8 được đề xuất cho ACR revision 7

> **DRAFT — proposed replacement for ACR §8, revision 7. Not effective unless independently audited, explicitly approved by the user together with re-acknowledgment of Receipt Topic QoS Contract revision 4, and canonically integrated. Until then ACR revision 6 remains the current authority.**
>
> ### 8. Gates after approval
>
> This section separates (A) the constrained, non-integrated primitive-only first deliverable defined by `PEP-001` revision `0.2.0` for `WP-04-POLICY-CORE-P0`, from (B) connected and/or profile-resolving V3 observation implementation. Gate A is a proposed amendment and is not operative under ACR revision 6. Neither gate changes the PEP dependency, package ownership, approved semantic contracts, or runtime status.
>
> #### Gate A — primitive-only, non-integrated deliverable
>
> After the preconditions below have been satisfied, a separate exact implementation packet may be submitted for consideration only for the constrained first deliverable in `PEP-001` revision `0.2.0`:
>
> 1. immutable `ObservationCutoffV3` core type and structural fail-closed validation; and
> 2. immutable structural `ObservationInputContractV3` models and structural validation, including exact approved contract references.
>
> Gate A is limited to type shape and structural validation. It does not resolve profiles, create operational facts, integrate configuration, or implement connected observation behavior. It does not waive or amend the dependency `WP-04 → WP-03`. Under the current PEP, WP-03 must be closed before WP-04 proceeds; only a separate, independently audited and explicitly approved PEP/governance amendment may change that dependency or sequencing.
>
> A Gate A packet may be considered only after all of the following have occurred:
>
> 1. the ACR revision 7 amendment has passed independent audit, received explicit user approval as part of the bundle with re-acknowledgment of Receipt Topic QoS Contract revision 4, and been canonically integrated under the repository workflow;
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
> Before a connected or profile-resolving V3 implementation packet may be issued, all six existing ACR revision 6 §8 gates remain required:
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
Receipt interface ID: mecanum.final-issued-receipt/v1
Receipt interface SHA-256:
                      90348664c4563997b93de7f10e278b10d4053fcb96909b6bb85c1319db76c40e
Receipt QoS ID:       mecanum.final-issued-receipt-topic-qos/v1
Receipt QoS SHA-256:  a3bc1a965fc6885825ab961289fa4028862aa7af4b3f3156bc40542f7ee08f62
```

### 5.3 Exclusions và profile evidence chưa giải quyết

Gate A không bao gồm V1, compiler/profile integration, ROS/runtime, receipt bridge/history, S2 synchronizer/buffer, assembler/encoder hoặc vector 81D. Gate A cũng không chọn hoặc suy diễn timing, buffer, freshness, measured-twist validity/covariance/provenance, hoặc YDLIDAR X3 extrinsic/range/frame. Các evidence profile-specific này vẫn là yêu cầu chưa giải quyết cho Gate B khi áp dụng.

## 6. Dependency, authority và các bước không được gộp

Theo PEP-001 revision `0.2.0` trên integration reference, `WP-04-POLICY-CORE-P0` phụ thuộc WP-03; WP-03 và WP-04 đều `BLOCKED_BY_CONTRACT`. Gate A không miễn, đóng hoặc sửa dependency đó, không đổi status và không đổi sequencing. Chỉ closure WP-03 hoặc một PEP/governance amendment riêng, được audit và duyệt độc lập, mới có thể xử lý dependency.

Các bước authority tách biệt theo thứ tự; không bước nào tự hàm ý bước sau:

```text
ACR revision 7 amendment proposal
→ independent audit
→ explicit user approval, bundled with re-acknowledgment of QoS revision 4
→ canonical integration of the approved bundle
→ WP-03 dependency closure or separately approved PEP/governance amendment
→ exact implementation packet independent review and separate user approval
→ implementation authorization for that exact packet, if explicitly granted
```

Proposal, audit, approval bundle, canonical integration, dependency closure và packet approval là các trạng thái riêng. Không trạng thái nào trong số đó tự tạo runtime approval.

## 7. Trạng thái của proposal

```text
ACR_REVISION_7: DRAFT_FOR_INDEPENDENT_AUDIT
ACR_REVISION_6: CURRENT_AUTHORITY_UNTIL_SUPERSEDED
RECEIPT_QOS_REVISION_4: UNCHANGED; RE-ACK REQUIRED WITH ACR REVISION 7
WP-03: BLOCKED_BY_CONTRACT
WP-04: BLOCKED_BY_CONTRACT
CODE_AUTHORIZATION: NOT_GRANTED
RUNTIME_NOT_APPROVED
```

Đây chỉ là proposal cho audit và user decision. Nó không sửa ACR revision 6, Receipt Topic QoS Contract revision 4, PEP-001 hoặc ledger; không tạo implementation packet; không tuyên bố WP-04 sẵn sàng viết code; và không cấp code hay runtime authorization.
