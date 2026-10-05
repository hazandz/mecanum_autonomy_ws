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

## 3. Approval bundle đề xuất với Receipt Topic QoS Contract revision 5

ACR revision 6 và `RECEIPT_TOPIC_QOS_CONTRACT` revision 4 vẫn là authority/bundle hiện hành. Theo disposition versioning được đề xuất sau audit, vehicle cho thay đổi normative §10(3) là một draft document revision 5 mới, không phải sửa lịch sử revision 4 hoặc giữ amendment như sidecar. ACR revision 7 và QoS Contract document revision 5 phải được audit và user-approved cùng nhau rồi canonical-integrated theo workflow. Cho đến khi điều đó hoàn tất, QoS revision 4 cùng ACR revision 6 tiếp tục là authority hiện hành.

Draft document được đề xuất trong bundle:

```text
Document:       docs/architecture/proposals/v3-observation-contracts/RECEIPT_TOPIC_QOS_CONTRACT_REVISION_5_PROPOSAL.md
Document rev:   5 (draft)
Document SHA-256: 9f87f4d09ec50aacf8c0cf69e11bff8bceb4219b8d09f68998288907afb8302b
```

Document SHA-256 ở trên nhận diện byte của draft QoS revision 5; nó khác với manifest hash chỉ nhận diện transport contract. Hash tài liệu được ghi bên ngoài file QoS để tránh self-reference.

Các định danh transport phải giữ nguyên chính xác:

```text
Transport contract ID:     mecanum.final-issued-receipt-topic-qos/v1 (unchanged)
Transport manifest SHA-256: a3bc1a965fc6885825ab961289fa4028862aa7af4b3f3156bc40542f7ee08f62
Current document authority: revision 4 until revision 5 bundle approval/integration
```

Transport-manifest SHA-256 tiếp tục là `a3bc1a965fc6885825ab961289fa4028862aa7af4b3f3156bc40542f7ee08f62`, chỉ khi JSON canonical byte-identical với revision 4 và hash tính lại khớp. Semantics vận chuyển không đổi: `RELIABLE`, `TRANSIENT_LOCAL`, `KEEP_LAST(1)`; latest-state/coalescing và delivery-order classification; receipt readiness theo action/reset barrier; deadline, lifespan và liveliness lease vô hạn; liveliness không dùng để kết luận dead-writer. Không thêm alias, fallback hoặc giá trị QoS mới.

Document revision 5 chỉ là proposed vehicle cho thay đổi approval-scope §10(3); không đổi transport manifest, contract ID `/v1`, public protocol, QoS profile hoặc transport semantics. Manifest byte identity/hash phải được kiểm tra trực tiếp cho packet này; nếu không đạt, dừng thay vì đổi ID/hash trong phạm vi này.

### 3.1 Disposition traceability kế thừa nhãn R4-E2 — chỉ trong QoS revision 5 draft

R4-E2 không được áp dụng hoặc gắn vào historical QoS revision 4. Thay vào đó, draft QoS revision 5 tại §10.2 đã ghi current operative companion reference là ACR revision 7. Đây là disposition đề xuất thay thế R4-E2 propositionally; nó chỉ áp dụng nếu revision 5 bundle được audited, approved và canonically integrated. QoS revision 4 §1 historical approval và R4-E1 được giữ nguyên.

**Wording tham chiếu prospective trong QoS revision 5 draft (không áp dụng cho revision 4):**

> **Superseded draft disposition — not applied to revision 4:** In the proposed QoS Contract document revision 5 §10.2, set the current operative companion reference to `ACR_V3_OBSERVATION_BOUNDARY_CLOSURE` revision `7`. This proposed reference is effective only if ACR revision 7 and QoS Contract document revision 5 are explicitly approved together and canonically integrated. Preserve revision 4's historical §1 approval and R4-E1 unchanged.

QoS revision 5 draft giữ nguyên như historical context record approval `2026-10-03` gắn với ACR revision 6 và R4-E1; điều đó không phải approval của revision 5. Không viết lại history để hàm ý ACR revision 7 hoặc QoS revision 5 đã được phê duyệt ngày đó. Nếu bundle mới được chấp thuận, ghi một sự kiện mới với ngày thực tế.

Tham chiếu đề xuất ở QoS revision 5 §10.2 chỉ có thể có hiệu lực sau khi ACR revision 7 và QoS revision 5 được user phê duyệt cùng nhau và tích hợp canonical. Không được coi ACR revision 7, QoS revision 5 hay reference draft là đã được duyệt hoặc có hiệu lực chỉ vì xuất hiện trong proposal.

Reference trong revision 5 §10.2 chỉ là traceability của current operative reference; approval-scope change ở §10.3 được tích hợp riêng vào chính QoS revision 5 draft. Không dùng traceability update để ngụy trang hoặc miễn điều kiện normative.

### 3.2 QoS §10(3) — disposition tích hợp vào draft QoS revision 5

QoS revision 4 §10(3) hiện hành yêu cầu “the resulting public-interface version/hash and resolved-config binding.” Audit nhận thấy Gate A/Gate B applicability chưa được phân định. Proposed wording Gate A/Gate B được đặt trong §10.3 của draft QoS revision 5 ở file và SHA nêu trên; file `RECEIPT_QOS_SECTION_10_3_GATE_SCOPE_AMENDMENT_PROPOSAL.md` chỉ là supporting rationale cho audit, không còn được đề xuất như sidecar amendment có authority độc lập. Cho đến khi revision 5 bundle được approved/canonical-integrated, QoS revision 4 §10(3) vẫn nguyên hiệu lực.

Thay đổi normative §10(3) được mang bởi QoS revision 5 document (R4-A1 đã được incorporate vào §10.3), bundle cùng ACR revision 7. R4-A1 không có sidecar authority riêng và R4-E2 không áp dụng lên revision 4.

### 3.3 Disposition version/hash được đề xuất — R4-E2 và R4-A1

Theo finding F-04, disposition đề xuất tách rõ transport identity khỏi approval-scope change:

- **Transport identity:** SHA-256 của draft document QoS revision 5 là `9f87f4d09ec50aacf8c0cf69e11bff8bceb4219b8d09f68998288907afb8302b`; transport ID `/v1` và manifest SHA `a3bc1a965fc6885825ab961289fa4028862aa7af4b3f3156bc40542f7ee08f62` là hai định danh riêng. Chỉ giữ manifest nếu byte-identical và hash tính lại khớp.
- **Disposition R4-E2:** không áp dụng lên QoS revision 4 lịch sử; tham chiếu prospective được thể hiện tại QoS revision 5 §10.2. Sự kiện §1 lịch sử và R4-E1 giữ nguyên.
- **Disposition R4-A1:** wording Gate scope đã được tích hợp vào draft revision 5 §10.3. File proposal companion chỉ là rationale/evidence; R4-A1 không có authority độc lập hoặc canonical hash riêng trừ khi governance yêu cầu.
- **Bundle:** ACR revision 7 + QoS document revision 5 được nhận diện bằng chính xác document SHA + transport ID/manifest hash không đổi. Approval phải là sự kiện mới, ghi ngày thực tế, qua audit, được user phê duyệt bundled và canonical-integrated.

Việc dùng document revision 5 là versioning vehicle theo quyết định được đề xuất cho audit trong work package này; không phải approval nội dung Gate A/Gate B. Draft vẫn pending audit/user decision. Nếu audit yêu cầu thay đổi manifest/transport semantics, dừng `STOPPED_VERSION_HASH_DISPOSITION_UNRESOLVED` thay vì tự đổi ID/hash.

## 4. Wording thay thế §8 được đề xuất cho ACR revision 7

> **DRAFT — proposed replacement for ACR §8, revision 7. Not effective unless independently audited, explicitly approved by the user together with Receipt Topic QoS Contract document revision 5 (document SHA-256 `9f87f4d09ec50aacf8c0cf69e11bff8bceb4219b8d09f68998288907afb8302b`; transport ID/manifest unchanged), and canonically integrated. Until then ACR revision 6 and QoS revision 4 remain current authority.**
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
> 1. the ACR revision 7 amendment and Receipt Topic QoS Contract document revision 5 (with exact document SHA recorded in the approval record) have passed independent audit, received explicit bundled user approval, and been canonically integrated under the repository workflow;
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
→ explicit bundled user approval of ACR revision 7 and QoS document revision 5
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
QOS_REVISION_4: CURRENT_AUTHORITY_UNTIL_REVISION_5_BUNDLE_APPROVED_AND_CANONICALLY_INTEGRATED
QOS_REVISION_5: DRAFT_PENDING_INDEPENDENT_AUDIT_AND_USER_APPROVAL
R4_E2: PROPOSED_REFERENCE_IN_REVISION_5_ONLY; NOT_APPLIED_TO_HISTORICAL_REVISION_4
R4_A1: INCORPORATED_IN_DRAFT_REVISION_5_SECTION_10_3; NO_SEPARATE_AUTHORITY
WP-03: BLOCKED_BY_CONTRACT
WP-04: BLOCKED_BY_CONTRACT
CODE_AUTHORIZATION: NOT_GRANTED
RUNTIME_NOT_APPROVED
```

Đây chỉ là proposal cho audit và user decision. Nó không sửa ACR revision 6, QoS revision 4, PEP-001 hoặc ledger; không canonical-integrate QoS revision 5; không tạo implementation packet; không tuyên bố WP-04 sẵn sàng viết code; và không cấp code hay runtime authorization.
