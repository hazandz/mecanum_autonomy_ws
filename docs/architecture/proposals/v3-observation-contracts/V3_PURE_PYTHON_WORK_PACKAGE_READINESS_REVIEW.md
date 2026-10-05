# Đánh giá readiness cho primitive V3 pure-Python

**Revision:** `4 — reconciliation sau semantic approval`
**Ngày:** `2026-10-05`
**Mode:** `ARCHITECTURE_READINESS_REVIEW` (static only)
**Integration reference:** `integration/implementation@f8933bcff2bb30b1dad57d71d91678e36746326f`
**PEP authority tại integration reference:** `PEP-001`, revision `0.2.0`
**Proposal evidence:** branch `wp-04-v3-contract-evidence-import`, commit `5cb311c1f48c507254a536c0499f638fd533ce81`
**Architecture authority:** `docs/MECANUM_NAV_DRL_Architecture.docx`, SHA-256 `f0fb1ebede5f4fa18604610c04bb13587d456173b4fd942dba77e44d49777860`
**Runtime status:** `RUNTIME_NOT_APPROVED`

## 1. Kết luận và trạng thái

Revision này cập nhật kết luận theo integration reference và các quyết định được ghi nhận trong proposal bundle. Đây là reconciliation tài liệu, không phải ACR amendment, không phải implementation packet và không cấp quyền sửa code.

```text
SCOPE_CLOSURE: USER_APPROVED
SEMANTIC_BUNDLE: USER_APPROVED_FOR_FOLLOW_ON_DESIGN_ONLY
PEP_MAPPING: WP-04-POLICY-CORE-P0 / PEP-001 rev.0.2.0
CANONICAL_RECORDING: PENDING_INTEGRATION_REVIEW
ACR_SCOPE_INTERPRETATION: PENDING_INDEPENDENT_AUDIT
CONTRACT_AMBIGUITY: PRESENT — ACR §8 chưa xác định rõ phạm vi primitive-only
IMPLEMENTATION_PACKET: NOT_AUTHORIZED
WP-04: BLOCKED_BY_CONTRACT
CODE_AUTHORIZATION: NOT_GRANTED
RUNTIME_NOT_APPROVED
```

Không ghi `READY_FOR_CODE` hoặc `APPROVED_FOR_IMPLEMENTATION`. Approval record hiện là proposal evidence trong candidate branch; sự hiện diện của nó tại commit `5cb311c` không tự biến record thành canonical integration authority.

## 2. Scope closure, semantic bundle và PEP mapping

Canonical work-package ID là `WP-04-POLICY-CORE-P0`, theo `PEP-001` revision `0.2.0` tại integration reference `f8933bcff2bb30b1dad57d71d91678e36746326f`. Không tạo `WP-05A`, `WP-05B` hoặc ID thay thế. WP-04 vẫn `BLOCKED_BY_CONTRACT`.

Scope closure cho primitive đã được user chấp thuận. Semantic bundle gồm S2 revision 2 (`mecanum.snapshot-synchronization-temporal/v1`, SHA-256 `1be31c1915fedd86f269cee5214d794da0899a0d69dbb0ba5392e619813d4a8f`), Observation Input Contract revision 6 và V3 Observation Boundary revision 7 được user chấp thuận cho `FOLLOW_ON_DESIGN_ONLY`. Quyết định này không chấp thuận profile values, implementation, test, runtime hoặc hardware.

Các tài liệu và approval record đã import vẫn ở proposal/candidate history cho đến khi được audit và tích hợp theo workflow riêng. Bản review này ghi nhận evidence đó nhưng không tuyên bố canonical recording đã hoàn tất.

## 3. Phạm vi A — primitive độc lập, không resolve hoặc kết nối profile

Deliverable primitive hẹp được PEP-001 revision `0.2.0` mô tả gồm:

1. `ObservationCutoffV3`: immutable V3 core type và structural fail-closed validation. Type chỉ xác thực transaction facts do caller cung cấp; không tạo action/reset barrier, lifecycle identity, cut-off timestamp, receipt hoặc config hash.
2. `ObservationInputContractV3`: immutable structural model shapes và validation cho các nhánh/contract references. Đây không phải resolved profile, compiler input mới hay operational provenance record.
3. Exact contract references được kiểm tra theo design: S2 ID/SHA ở trên; receipt interface `mecanum.final-issued-receipt/v1` / `90348664c4563997b93de7f10e278b10d4053fcb96909b6bb85c1319db76c40e`; receipt QoS `mecanum.final-issued-receipt-topic-qos/v1` / `a3bc1a965fc6885825ab961289fa4028862aa7af4b3f3156bc40542f7ee08f62`.

PEP phân quyền sở hữu: `SafetyLifecycle` là owner của barrier; `RobotRuntimeAdapter.wait_transition_snapshot(after=receipt)` là operational creator duy nhất của một cutoff mỗi transition; primitive chỉ định nghĩa type và validation.

Primitive-only không kết nối compiler/profile, receipt bridge/history hay S2 synchronizer và không tạo vector 81D. File dự kiến cho một work package code sau (chỉ là dự kiến, chưa được tạo hoặc cho phép ở revision này):

```text
ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/core/v3_observation_contracts.py
ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/config/v3_observation_input_models.py
ros2_ws/src/mecanum_nav_rl/test/test_v3_observation_contract_primitives.py
```

Fixture tương lai chỉ là dữ liệu structural in-memory, không phải profile, provenance, measurement hoặc runtime evidence.

## 4. Phạm vi B — connected/profile-resolving implementation vẫn bị chặn

Connected V3 assembler/encoder/history path và profile-resolving work tiếp tục chịu các gate tại ACR §8 và Observation Input Contract Design §8.2. Phạm vi đó bao gồm composition/compiler/profile closure, receipt interface/topic/ingress integration, S2 synchronizer, assembler/encoder, vector construction và các profile/evidence cụ thể. Không phần nào trong số đó được mở bởi readiness review này.

Các thông tin vẫn unresolved gồm profile timing, buffer, freshness, measured-twist validity/fault/covariance/provenance evidence và các giá trị X3 như extrinsic/range/frame. Không chọn hoặc suy diễn giá trị; không chuyển fixture thành profile evidence.

## 5. Cách đọc ACR §8 và ambiguity còn lại

ACR `ACR_V3_OBSERVATION_BOUNDARY_CLOSURE.md` §8 mở đầu bằng điều kiện “Before a V3 core implementation packet may be issued” rồi liệt kê các gate về canonical recording, receipt protocol/QoS/config binding, `ObservationInputContractV3` cùng compiler/composition validation, receipt ingress và independent audit. Câu kết của section nói sau các gate đó một work package mới có thể triển khai **connected pure-Python V3 assembler/encoder/history path**.

Observation Input Contract Design §8.1 tách một `non-resolving primitive readiness review`: unresolved profile timing, measured-twist evidence và profile composition không tự chặn việc đánh giá primitive; nhưng §8.1 cũng nói rõ đây không phải implementation authorization và vẫn cần exact implementation packet cùng approval. PEP-001 revision `0.2.0` mô tả primitive-only deliverable riêng, ngoài connected path và profile/compiler closure.

Vì vậy, cách đọc hẹp đang được đưa ra để audit là: các yêu cầu tích hợp đầy đủ ở ACR §8 phù hợp với phạm vi connected/profile-resolving B; primitive-only A có thể được đánh giá readiness riêng theo Input Design §8.1 và PEP-001. Tuy nhiên, câu mở đầu ACR §8 không giới hạn rõ “V3 core implementation packet” vào connected path. Không thể coi cách đọc hẹp này là đã được giải quyết hoặc là amendment cho ACR. Do đó:

```text
ACR_SCOPE_INTERPRETATION: ARCHITECTURE_INTERPRETATION_PENDING_INDEPENDENT_AUDIT
CONTRACT_AMBIGUITY: PRESENT
```

Independent audit phải quyết định liệu ACR §8 có cho phép phát hành một implementation packet primitive-only trước khi hoàn thành toàn bộ các gate được liệt kê hay không. Cho tới khi ambiguity được xử lý bằng audit/authority phù hợp, giữ `WP-04: BLOCKED_BY_CONTRACT`, không phát hành packet code và không sửa ACR đã duyệt.

## 6. Điều kiện tiếp theo và giới hạn evidence

- Cần independent audit riêng cho interpretation boundary tại §5 và candidate proposal records.
- Cần canonical integration review/recording riêng; proposal branch không tự nâng authority.
- Cần một implementation packet chính xác được audit độc lập và được user phê duyệt riêng trước mọi source edit.
- Profile values/evidence vẫn là gate riêng; sự chấp thuận semantic bundle chỉ là `FOLLOW_ON_DESIGN_ONLY`.
- Không có test, build, ROS, Gazebo, Nav2, PPO, HIL, hardware hoặc runtime evidence từ review này.

```text
IMPLEMENTATION_PACKET: NOT_AUTHORIZED
WP-04: BLOCKED_BY_CONTRACT
CODE_AUTHORIZATION: NOT_GRANTED
RUNTIME_NOT_APPROVED
```
