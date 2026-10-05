# Proposal làm rõ phạm vi ACR §8 cho primitive V3

**Status:** `DRAFT_FOR_INDEPENDENT_AUDIT`
**Ngày:** `2026-10-05`
**Work package:** `WP-04-ACR-SECTION-8-SCOPE-CLARIFICATION-PROPOSAL`
**Base candidate:** `wp-04-v3-primitive-readiness-reconciliation@2395b1b3b2de6303f156e22d43d04efb9ce5fb9c`
**Integration reference:** `origin/integration/implementation@f8933bcff2bb30b1dad57d71d91678e36746326f`
**Architecture authority:** `docs/MECANUM_NAV_DRL_Architecture.docx`
**Runtime status:** `RUNTIME_NOT_APPROVED`

## 1. Mục đích và ranh giới quyết định

Đây là proposal để independent audit và user decision về phạm vi áp dụng các gate tại §8 của `ACR_V3_OBSERVATION_BOUNDARY_CLOSURE.md` revision 6. Proposal không sửa ACR đã được duyệt, không thay PEP canonical, không đóng dependency WP-03, không phải implementation packet và không cấp quyền code.

Các trạng thái và bước authority phải được phân biệt:

| Bước | Ý nghĩa | Trạng thái trong proposal này |
|---|---|---|
| ACR clarification proposal | Wording dự kiến làm rõ scope A/B | Draft |
| Independent audit | Đánh giá với Architecture, ACR và PEP | Chưa thực hiện |
| User approval | Quyết định có chấp thuận clarification | Chưa có |
| Canonical integration | Tích hợp theo workflow sau audit/approval | Chưa thực hiện |
| WP-03 dependency closure | Đóng WP-03 hoặc xử lý bằng governance amendment riêng | Chưa thực hiện; WP-03 vẫn blocked |
| Implementation authorization | Phê duyệt một packet code chính xác riêng biệt | Chưa có |

Không bước nào được suy ra tự động từ bước trước. Audit, approval hoặc canonical integration của clarification cũng không tự cấp quyền source edit.

## 2. ACR §8 hiện hành — trích nguyên văn

ACR revision 6 §8 hiện hành ghi:

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

### 2.1 Vì sao câu cuối chưa đủ tạo ngoại lệ primitive-only

Câu mở đầu đặt điều kiện trước khi “a V3 core implementation packet” được phát hành nhưng không giới hạn rõ packet đó vào connected path. Các gate 2–5 đề cập QoS/config binding, compiler/composition, receipt message/topic và ingress — rộng hơn primitive-only. Câu cuối xác định connected assembler/encoder/history chỉ được implement sau các gate; câu đó không nói các gate trước chỉ áp dụng cho connected path, cũng không nêu primitive-only packet được miễn.

Observation Input Contract Design §8.1 cho phép một readiness review riêng cho non-resolving primitives, nhưng nêu rõ review đó không phải implementation authorization và vẫn cần exact packet cùng approval. PEP-001 revision `0.2.0` mô tả primitive-only deliverable riêng nhưng vẫn giữ `WP-04-POLICY-CORE-P0` phụ thuộc WP-03 và yêu cầu separate exact implementation packet. Các nguồn này hỗ trợ phân biệt hai scope thiết kế; chúng chưa tự sửa được câu mở đầu rộng của ACR §8.

Vì vậy không thể suy luận ngoại lệ primitive-only chỉ từ câu cuối. Cần clarification được audit/duyệt; trong thời gian đó không coi Gate A dưới đây đã được ACR hiện hành cho phép.

## 3. Wording revision đề xuất cho ACR §8

> **DRAFT — proposed replacement for ACR §8; not effective unless independently audited, approved by the user, and canonically integrated.**

### 8. Gates after approval

This section distinguishes a non-resolving primitive-only work package from the connected and/or profile-resolving V3 observation implementation. This distinction does not waive the PEP dependency on WP-03, create implementation authorization, or change any approved semantic contract. A primitive-only packet must not include connected or profile-resolving work listed under Gate B.

#### Gate A — primitive-only scope

A future primitive-only packet may be considered only for the exact constrained deliverable in `PEP-001` revision `0.2.0` under `WP-04-POLICY-CORE-P0`:

1. immutable `ObservationCutoffV3` type and structural fail-closed validation; and
2. immutable structural `ObservationInputContractV3` models and their structural validation, including exact approved contract references.

Gate A excludes profile resolution/configuration composition; compiler, validator, YAML, profile, `ResolvedConfigV3` or config-hash implementation; ROS/ROSIDL, QoS, TF, DDS or runtime integration; receipt bridge or receipt history; S2 synchronizer/buffers; assembler, encoder or construction of the 81D vector. It permits no V1 observation, decoder, history, snapshot, wrapper, alias or fallback use.

Before a Gate A implementation packet can be considered, all of the following must hold:

1. this scope clarification has passed independent audit, received explicit user approval, and been canonically integrated under the repository workflow;
2. the approved semantic bundle has been recorded canonically under the applicable PEP/governance workflow, without changing its approved IDs, hashes, revisions or semantics;
3. WP-03 is closed, or its dependency on WP-04 has been changed by a separate, explicitly approved PEP/governance amendment; and
4. an exact implementation packet naming the base, branch, allowed files, static checks, any permitted tests, stop conditions and evidence requirements has passed independent audit and received separate explicit user approval.

These are gates to *consider* a later packet, not automatic approval to write code. No Gate A implementation begins solely because the conditions are recorded as satisfied; the separate packet and its approval remain controlling.

#### Gate B — connected and/or profile-resolving V3 implementation

Before a connected or profile-resolving V3 implementation packet may be issued, all of the following existing gates remain required:

1. record this approved ACR in architecture/governance and update the V3 observation specification;
2. approve the bundled Receipt Topic QoS Contract with its canonical ID/hash, delivery/coalescing/action-bound readiness behavior, and `TopicQosContractV3` record; this is separate from S2;
3. design `ObservationInputContractV3` model, canonical source, compiler and composition validation with no unresolved values in resolved config;
4. add receipt message/topic, version/hash compatibility checks and its canonical topic/QoS record;
5. define pure-Python ingress seams for typed snapshots and receipt data; and
6. obtain an independent audit that 81D layout and process/safety isolation remain preserved.

The packet must additionally identify the applicable profile and provide that profile's required evidence before resolving profile-specific values. S2 timing, buffer and freshness evidence; measured-twist validity/fault/covariance/provenance evidence; canonical source records; and concrete profile values, including YDLIDAR X3 extrinsic/range/frame evidence for `deploy_real`, remain applicable gates. A later work package may implement a connected pure-Python V3 assembler/encoder/history path only after these gates and its exact packet approval. Runtime integration remains a separate gate.

#### Dependency and authority rule

Neither Gate A nor this proposed ACR clarification changes the PEP dependency `WP-04 → WP-03`. Under current `PEP-001` revision `0.2.0`, WP-03 and WP-04 remain `BLOCKED_BY_CONTRACT`. Only a separate, explicitly approved PEP/governance amendment may change that dependency or status. This ACR proposal must not be read as a waiver, substitution or closure of WP-03.

## 4. Invariants bắt buộc được giữ cho packet primitive-only tương lai

Các điều kiện dưới đây chỉ là ràng buộc kỹ thuật để audit một packet tương lai; chúng không phải quyền code do proposal này cấp.

### 4.1 Transaction, lifecycle và clock

- `ObservationCutoffV3.cut_off_ros_ns` phải strictly greater than cả action barrier và reset barrier.
- Cutoff và hai barrier phải cùng lifecycle identity, `reset_epoch`, `runtime_generation`, và profile ROS-time domain/unit/epoch.
- `SafetyLifecycle` là owner duy nhất của action/reset barriers. `RobotRuntimeAdapter.wait_transition_snapshot(after=receipt)` là operational creator duy nhất của một cutoff mỗi transition; primitive chỉ nhận và validate facts caller cung cấp, không tạo hoặc sửa chúng.
- `config_hash` chỉ là provenance/session binding do caller cung cấp. Primitive không tạo/tính hash; không biến nó thành config field.

### 4.2 Typed fail-closed và contract binding

Status/error behavior phải giữ semantics fail-closed của S2 revision 2, gồm các trạng thái canonical sau khi tương ứng:

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

Primitive phải giữ chính xác các reference sau, không alias hoặc fallback:

```text
S2: mecanum.snapshot-synchronization-temporal/v1
    1be31c1915fedd86f269cee5214d794da0899a0d69dbb0ba5392e619813d4a8f
Receipt interface: mecanum.final-issued-receipt/v1
    90348664c4563997b93de7f10e278b10d4053fcb96909b6bb85c1319db76c40e
Receipt Topic QoS: mecanum.final-issued-receipt-topic-qos/v1
    a3bc1a965fc6885825ab961289fa4028862aa7af4b3f3156bc40542f7ee08f62
```

### 4.3 Ngoài phạm vi primitive-only

Không V1 observation/decoder/history/snapshot; không compiler/profile/`ResolvedConfigV3` integration; không ROS/ROSIDL/QoS/TF/DDS/runtime; không receipt bridge/history; không S2 synchronizer/buffers; không assembler/encoder; không vector 81D. Không chọn profile timing, buffer, freshness, measured-twist evidence, LiDAR range/extrinsic/frame hoặc giá trị X3. Không biến structural fixture thành profile, measurement, provenance hoặc runtime evidence.

## 5. Dependency WP-03 và trạng thái hiện hành

PEP-001 revision `0.2.0` trên integration reference `f8933bcff2bb30b1dad57d71d91678e36746326f` quy định WP-04 phụ thuộc WP-03 và ghi cả WP-03 lẫn WP-04 là `BLOCKED_BY_CONTRACT`. Proposal này chỉ đề nghị làm rõ ACR §8; nó không đổi plan, dependency, canonical status hoặc thứ tự authority. WP-03 phải được đóng hoặc dependency được giải quyết bằng governance amendment riêng trước khi xét packet primitive-only theo điều kiện đề xuất tại §3.

Phải phân biệt rõ:

- **ACR amendment/clarification proposal:** nội dung draft ở §3, chưa có hiệu lực.
- **User approval:** quyết định riêng, chưa được suy ra từ việc yêu cầu soạn proposal.
- **Independent audit:** review proposal và boundary với Architecture/PEP, chưa thực hiện.
- **Canonical integration:** chỉ sau audit và approval theo workflow riêng; hiện chưa có.
- **WP-03 dependency closure:** điều kiện riêng hoặc governance amendment riêng; proposal này không phải waiver.
- **Implementation authorization:** chỉ packet code riêng sau audit và user approval; hiện `NOT_GRANTED`.

## 6. Kết luận proposal

```text
ACR_SCOPE_CLARIFICATION: DRAFT_FOR_INDEPENDENT_AUDIT
WP-03: BLOCKED_BY_CONTRACT
WP-04: BLOCKED_BY_CONTRACT
CODE_AUTHORIZATION: NOT_GRANTED
RUNTIME_NOT_APPROVED
```

Proposal này không tuyên bố WP-04 sẵn sàng viết code, không phát hành implementation packet và không sửa ACR revision 6. Cần independent audit và user decision tiếp theo; mọi code, integration hoặc runtime vẫn ngoài phạm vi.
